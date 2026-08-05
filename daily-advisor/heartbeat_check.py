#!/usr/bin/env python3
"""日報健康檢查 — 偵測「日報沒送出」這件沒發生的事。

daily_advisor.py 每次成功送出 Telegram 後寫一次 HEARTBEAT_FILE（epoch 秒）。
本腳本由**獨立的 cron** 每天跑一次，檢查該檔年齡；超過門檻代表日報連續兩天
沒送成功，推一則 Telegram 警告。

為什麼是獨立腳本而不是寫在 daily_advisor.py 裡：daily_advisor.py 若整個沒跑
（cron 失效、VPS 重開、Python 崩潰、claude -p 認證過期），它自己不可能發出
警告 —— 2026-07 那次就是日報默默死了兩週沒人發現。偵測「沒發生的事」的機制
必須在外面。同理本檔**刻意不 import daily_advisor**：那支若壞掉（syntax
error、依賴問題），import 會讓本檔一起死在最需要它的時刻。所以 load_env 和
send_telegram 在這裡各自重寫一份，stdlib only。

門檻 48 小時的推導（日報排程：平日 21:30 UTC / 假日 14:30 UTC；本檢查 23:00 UTC）：
- 正常最長間隔 = 週日 14:30 → 週一 21:30 = 31h；週一 23:00 檢查時年齡 32.5h
  < 48 → 不誤報
- 只錯一天的最壞情境 = 年齡 32.5h < 48 → 不觸發（符合「連續兩天才報」）
- 連錯兩天的最短情境（平日）= 週二 21:30 成功後週三、週四都失敗，週四 23:00
  檢查時年齡 49.5h > 48 → 觸發

CLI: python3 heartbeat_check.py [--dry-run]
Exit code: 0 正常或警告已送出 / 1 警告該送但送失敗
"""
import argparse
import json
import os
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT_FILE = os.environ.get(
    "DAILY_ADVISOR_HEARTBEAT", "/var/lib/mlb-fantasy/last_report_success"
)
THRESHOLD_HOURS = 48


def load_env():
    """讀 .env — 刻意不 import daily_advisor，見模組 docstring。"""
    env = {}
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def read_heartbeat(path=None):
    """上次成功送報的 epoch 秒；檔案不存在或內容無法解析時回 None。"""
    path = path or HEARTBEAT_FILE
    try:
        with open(path, encoding="utf-8") as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def should_alert(last_success_epoch, now_epoch, threshold_hours=THRESHOLD_HOURS):
    """回傳 (是否該警告, 距上次成功的小時數)。

    last_success_epoch 為 None（沒有紀錄 / 檔案壞掉）一律警告 — fail loud，
    寧可誤報一次也不要在紀錄遺失時靜默失能。此時小時數回 None。
    """
    if last_success_epoch is None:
        return True, None
    age_hours = (now_epoch - last_success_epoch) / 3600
    return age_hours > threshold_hours, age_hours


def build_alert_message(age_hours, threshold_hours=THRESHOLD_HOURS):
    if age_hours is None:
        head = "找不到日報成功紀錄（heartbeat 檔不存在或內容損毀）。"
    else:
        head = f"已 {age_hours:.1f} 小時沒有成功送出日報（門檻 {threshold_hours}h）。"
    return (
        "日報異常\n\n"
        f"{head}\n\n"
        "查法：\n"
        "  tail -40 /var/log/daily-advisor.log\n"
        "  cd /tmp && claude -p \"Reply with exactly: PONG\"\n\n"
        "常見原因：Claude token 過期、cron 被停用、VPS 重開後服務沒起來。"
    )


def send_telegram(message, env):
    """純文字送出（不設 parse_mode，避免訊息內容被 Markdown 解析出錯）。"""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing in .env", file=sys.stderr)
        return False

    payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Daily report heartbeat check")
    parser.add_argument("--dry-run", action="store_true",
                        help="只印判斷結果，不送 Telegram")
    args = parser.parse_args()

    last = read_heartbeat()
    alert, age = should_alert(last, time.time())

    if not alert:
        print(f"OK — last successful report {age:.1f}h ago", file=sys.stderr)
        return 0

    message = build_alert_message(age)
    if args.dry_run:
        print(message)
        return 0

    print("ALERT — sending Telegram...", file=sys.stderr)
    if send_telegram(message, load_env()):
        print("Sent.", file=sys.stderr)
        return 0
    print("Failed to send alert.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
