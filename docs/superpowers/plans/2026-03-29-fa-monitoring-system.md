# FA Monitoring System Implementation Plan (v2 — review 修正版)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立三層 FA 監控系統 — Daily FA Watch（每日 07:00）+ Weekly Deep Scan（每週一 19:30）+ %owned 歷史追蹤，搭配週二 manual /waiver-scan 提醒。

**Architecture:** 兩個新 Python 腳本（`fa_watch.py` + `weekly_scan.py`），共用 `yahoo_query.py` 的 Yahoo API 函式 + `send_telegram`。%owned 快照存 JSON，24h/3d 雙窗口變動排行。Weekly Deep Scan 摘要存檔供 Daily FA Watch 讀取作為 claude -p context。時區：FA 追蹤用 `Asia/Taipei`（使用者日曆日），非 MLB 日期。

**Tech Stack:** Python 3.10+ / urllib（零外部依賴）/ Claude Code CLI / Telegram Bot API / GitHub Issue

---

## Review 修正清單

| # | 來源 | 修正 | 位置 |
|---|------|------|------|
| R1 | Critical | `load_env` 擴充包含 Telegram key | Task 1 |
| R2 | Critical | `today_str` 改用 `Asia/Taipei` | Task 2, 3, 4 |
| R3 | Important | snapshot 查詢 ALL 50 + 新增 lastweek 查詢 | Task 2 |
| R4 | Important | `collect_fa_snapshot` 接受可配置查詢參數 | Task 2, 4 |
| R5 | Important | `send_telegram` 搬到 `yahoo_query.py` 統一 | Task 1 |
| R6 | Important | FA Watch prompt 加入陣容 context | Task 3 |
| R7 | Important | `.gitignore` 提前到 Task 1 | Task 1 |
| R8 | Important | API request 間加 `time.sleep(1)` | Task 2 |
| R9 | Suggestion | `weekly_scan_summary.txt` 過期檢查（>7d） | Task 3 |
| R10 | Suggestion | 錯誤通知（cron 失敗送 Telegram） | Task 3, 4 |
| R11 | Suggestion | 3d 窗口前幾天無數據時提示 | Task 2 |
| R12 | Suggestion | SP in-season 放寬門檻寫入 CLAUDE.md | Task 5 |
| R13 | Code | `int(float(p["percent_owned"] or 0))` 防禦性轉換 | Task 2 |

---

## 時間軸

```
週一 19:30  Weekly Deep Scan（本週策略基調）
     21:45  速報
每日 05:00  最終報
     07:00  Daily FA Watch（市場監控）
週二 07:00  Daily FA Watch 末尾加 /waiver-scan 提醒
```

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `daily-advisor/yahoo_query.py` | Modify | 擴充 `load_env`(R1) + 搬入 `send_telegram`(R5) |
| `daily-advisor/fa_watch.py` | Create | Daily FA Watch 主腳本 |
| `daily-advisor/weekly_scan.py` | Create | Weekly Deep Scan 主腳本 |
| `daily-advisor/prompt_fa_watch.txt` | Create | Daily FA Watch prompt template |
| `daily-advisor/prompt_weekly_scan.txt` | Create | Weekly Deep Scan prompt template |
| `daily-advisor/fa_history.json` | Auto-generated | %owned 每日快照（不入 git） |
| `daily-advisor/weekly_scan_summary.txt` | Auto-generated | 最新 Weekly Deep Scan 摘要（不入 git） |
| `.gitignore` | Modify | 加入 fa_history.json + weekly_scan_summary.txt |
| `.claude/commands/waiver-scan.md` | Modify | 加入週二提醒規則 |
| `CLAUDE.md` | Modify | FA 監控說明 + 週二檢查 + SP in-season 門檻(R12) |
| `README.md` | Modify | 更新排程說明 |

---

### Task 1: yahoo_query.py 擴充（共用函式 + send_telegram + load_env + .gitignore）

**Files:**
- Modify: `daily-advisor/yahoo_query.py`
- Modify: `.gitignore`

- [ ] **Step 1: 擴充 `load_env` 包含 Telegram key (R1)**

```python
def load_env():
    env = {}
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env
```

- [ ] **Step 2: 搬入 `send_telegram` (R5)**

在 `yahoo_query.py` 底部（`main()` 前）加入：

```python
def send_telegram(message, env):
    """Send message via Telegram Bot API."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing", file=sys.stderr)
        return False
    MAX_LEN = 4096
    if len(message) > MAX_LEN:
        message = message[:MAX_LEN - 20] + "\n\n(訊息截斷)"
    payload = json.dumps({
        "chat_id": chat_id, "text": message, "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False
```

- [ ] **Step 3: 更新 .gitignore (R7)**

```bash
echo "daily-advisor/fa_history.json" >> .gitignore
echo "daily-advisor/weekly_scan_summary.txt" >> .gitignore
```

- [ ] **Step 4: 驗證 import**

```bash
cd daily-advisor && python -c "from yahoo_query import refresh_token, load_env, send_telegram, YAHOO_STAT_MAP; print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/yahoo_query.py .gitignore
git commit -m "refactor: add send_telegram + expand load_env in yahoo_query.py"
```

---

### Task 2: %owned 歷史追蹤模組

**Files:**
- Create: `daily-advisor/fa_watch.py`（%owned 快照功能）

- [ ] **Step 1: 建立 FA 快照收集函式（可配置查詢參數）(R3, R4, R8, R13)**

```python
"""Daily FA Watch — %owned tracking + market monitoring."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import (
    refresh_token, load_env, load_config, api_get,
    YAHOO_STAT_MAP, extract_player_info, parse_player_stats,
    send_telegram,
)

TPE = ZoneInfo("Asia/Taipei")  # (R2) FA 追蹤用台灣時區

# Default queries for daily watch
DAILY_QUERIES = [
    ("ALL", "status=FA;sort=AR;count=50"),
    ("ALL-lastweek", "status=FA;sort=AR;sort_type=lastweek;count=20"),
    ("CF", "status=FA;position=CF;sort=AR;count=10"),
    ("SP", "status=FA;position=SP;sort=AR;count=10"),
    ("1B", "status=FA;position=1B;sort=AR;count=10"),
]

# Expanded queries for weekly scan (R4)
WEEKLY_QUERIES = [
    ("ALL", "status=FA;sort=AR;count=50"),
    ("ALL-lastweek", "status=FA;sort=AR;sort_type=lastweek;count=30"),
    ("CF", "status=FA;position=CF;sort=AR;count=15"),
    ("SP", "status=FA;position=SP;sort=AR;count=20"),
    ("1B", "status=FA;position=1B;sort=AR;count=10"),
    ("LF", "status=FA;position=LF;sort=AR;count=10"),
    ("2B", "status=FA;position=2B;sort=AR;count=10"),
]


def collect_fa_snapshot(access_token, config, queries=None):
    """Query FA players across positions. Returns {name: {team, position, pct, stats}}.

    Args:
        queries: list of (label, filter_str) tuples. Defaults to DAILY_QUERIES.
    """
    if queries is None:
        queries = DAILY_QUERIES
    league_key = config["league"]["league_key"]
    snapshot = {}

    for label, filters in queries:
        path = f"/league/{league_key}/players;{filters};out=stats,percent_owned"
        try:
            data = api_get(path, access_token)
            league_data = data["fantasy_content"]["league"]
            if len(league_data) < 2 or "players" not in league_data[1]:
                continue
            players_data = league_data[1]["players"]
            for k, v in players_data.items():
                if k == "count":
                    continue
                p = extract_player_info(v["player"])
                stats = parse_player_stats(v["player"])
                name = p["name"]
                if name not in snapshot:
                    snapshot[name] = {
                        "team": p["team"],
                        "position": p["position"],
                        "pct": int(float(p["percent_owned"] or 0)),  # (R13)
                        "stats": stats,
                    }
        except Exception as e:
            print(f"FA query error ({label}): {e}", file=sys.stderr)
        time.sleep(1)  # (R8) API rate limit 禮貌

    return snapshot
```

- [ ] **Step 2: 建立快照存讀函式**

```python
FA_HISTORY_FILE = os.path.join(SCRIPT_DIR, "fa_history.json")


def load_fa_history():
    if os.path.exists(FA_HISTORY_FILE):
        with open(FA_HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_fa_history(history):
    with open(FA_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 3: 建立變動排行榜函式（含參考日期顯示）**

```python
def calc_owned_changes(today_snapshot, history, today_str):
    """Calculate %owned changes for 24h and 3d windows."""
    dates = sorted(history.keys())

    ref_1d = None
    ref_3d = None
    for d in reversed(dates):
        if d < today_str:
            if ref_1d is None:
                ref_1d = d
            days_diff = (
                datetime.strptime(today_str, "%Y-%m-%d")
                - datetime.strptime(d, "%Y-%m-%d")
            ).days
            if days_diff >= 3 and ref_3d is None:
                ref_3d = d
                break

    snap_1d = history.get(ref_1d, {}) if ref_1d else {}
    snap_3d = history.get(ref_3d, {}) if ref_3d else {}

    changes = []
    for name, info in today_snapshot.items():
        pct = info["pct"]
        d1 = pct - snap_1d.get(name, {}).get("pct", pct) if snap_1d else None
        d3 = pct - snap_3d.get(name, {}).get("pct", pct) if snap_3d else None
        changes.append({
            "name": name, "team": info["team"],
            "position": info["position"], "pct": pct,
            "d1": d1, "d3": d3,
            "stats": info.get("stats", {}),
        })

    return changes, ref_1d, ref_3d  # return ref dates for display
```

- [ ] **Step 4: 格式化排行榜輸出（含日期和缺數據提示）(R11)**

```python
def format_change_rankings(changes, ref_1d, ref_3d, top_n=5):
    """Format top risers and fallers with reference date info."""
    lines = []

    # (R11) 提示數據窗口
    if ref_1d:
        header = f"24h (vs {ref_1d})"
    else:
        return "（需累積至少 2 天數據才有變動排行）"
    if ref_3d:
        header += f" | 3d (vs {ref_3d})"
    else:
        header += " | 3d (需累積 3 天以上)"
    lines.append(header)

    with_d1 = [c for c in changes if c["d1"] is not None and c["d1"] != 0]

    risers = sorted(with_d1, key=lambda x: x["d1"], reverse=True)[:top_n]
    fallers = sorted(with_d1, key=lambda x: x["d1"])[:top_n]

    if risers:
        lines.append("\n升幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in risers:
            d1 = f"+{c['d1']}" if c["d1"] > 0 else str(c["d1"])
            d3 = f"+{c['d3']}" if c["d3"] and c["d3"] > 0 else (str(c["d3"]) if c["d3"] is not None else "—")
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}")

    if fallers and fallers[0]["d1"] < 0:
        lines.append("\n降幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in fallers:
            if c["d1"] >= 0:
                break
            d1 = str(c["d1"])
            d3 = str(c["d3"]) if c["d3"] is not None else "—"
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}")

    return "\n".join(lines)
```

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/fa_watch.py
git commit -m "feat: add %owned snapshot and change rankings"
```

---

### Task 3: Daily FA Watch prompt + claude -p 流程

**Files:**
- Create: `daily-advisor/prompt_fa_watch.txt`
- Modify: `daily-advisor/fa_watch.py`（加 main 流程）

- [ ] **Step 1: 建立 prompt template（含陣容 context）(R6)**

```
你是 Fantasy Baseball FA 市場監控顧問。根據以下數據，產出今日 FA 市場快報。

聯賽：12 隊 H2H One Win 7×7，Punt SV+H + 軟 Punt SB
陣容弱點：CF 深度（Buxton 傷病風險）、Kwan 最弱（VOR +2）

我的陣容摘要（會附在數據區段）。

你的任務：
1. 從 %owned 變動排行榜中，標記值得注意的球員（升 = 被搶中，降 = 可能撿便宜）
2. 檢查弱點位置的 FA 市場有無新面孔
3. 根據本週 Deep Scan 摘要，更新觀察中球員的狀態判斷
4. 如有緊急行動建議（好的 FA 快被搶光），明確標記

輸出格式：
- Telegram Markdown，控制在 1500 字元以內
- 多數日子只需確認「無異常」，不要硬湊內容
- 只列需要注意的項目

不要解釋規則，直接給結論。
```

- [ ] **Step 2: 建立 `build_fa_watch_data` 函式（含陣容 context + weekly summary 過期檢查）(R6, R9)**

```python
def build_fa_watch_data(today_str, snapshot, changes, ref_1d, ref_3d, config):
    """Build data summary for claude -p."""
    lines = [f"=== FA Watch ({today_str}) ===\n"]

    # %owned changes
    rankings = format_change_rankings(changes, ref_1d, ref_3d)
    lines.append(rankings)

    # (R6) 陣容摘要 from roster_config.json
    lines.append("\n--- 我的陣容 ---")
    for b in config.get("batters", []):
        role = "BN" if b["role"] == "bench" else b["role"]
        lines.append(f"  [{role}] {b['name']} ({b['team']}, {'/'.join(b['positions'])})")
    for p in config.get("pitchers", []):
        role = "BN" if p["role"] == "bench" else ("IL" if p["role"] == "IL" else p["type"])
        lines.append(f"  [{role}] {p['name']} ({p['team']}, {p['type']})")

    # Key position FA top players
    lines.append("\n--- 弱點位置 FA ---")
    for pos in ["CF", "SP", "1B"]:
        pos_players = [
            (n, i) for n, i in snapshot.items()
            if pos in i["position"].split(",")
        ]
        pos_players.sort(key=lambda x: x[1]["pct"], reverse=True)
        top = pos_players[:3]
        if top:
            names = ", ".join(f"{n}({i['pct']}%)" for n, i in top)
            lines.append(f"  {pos}: {names}")

    # (R9) Weekly scan summary with freshness check
    summary_path = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")
    if os.path.exists(summary_path):
        mtime = os.path.getmtime(summary_path)
        age_days = (datetime.now().timestamp() - mtime) / 86400
        with open(summary_path, encoding="utf-8") as f:
            summary = f.read().strip()
        if age_days > 7:
            lines.append(f"\n--- 本週 Deep Scan 摘要（⚠️ {int(age_days)} 天前，可能過期） ---\n{summary}")
        else:
            lines.append(f"\n--- 本週 Deep Scan 摘要 ---\n{summary}")
    else:
        lines.append("\n（尚無 Weekly Deep Scan 摘要）")

    # Watchlist status from waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            log_content = f.read()
        in_watch = []
        in_section = False
        for line in log_content.split("\n"):
            if line.startswith("## 觀察中"):
                in_section = True
                continue
            if line.startswith("## ") and in_section:
                break
            if in_section and line.startswith("### "):
                player_name = line.replace("### ", "").split("(")[0].strip()
                pct = snapshot.get(player_name, {}).get("pct", "N/A")
                in_watch.append(f"  {player_name}: {pct}%")
        if in_watch:
            lines.append("\n--- 觀察中球員 %owned ---")
            lines.extend(in_watch)

    # Tuesday reminder
    day_of_week = datetime.strptime(today_str, "%Y-%m-%d").weekday()
    if day_of_week == 1:
        lines.append("\n今天是週二，建議開 Claude Code 跑 /waiver-scan")

    return "\n".join(lines)
```

- [ ] **Step 3: 建立 main() 含錯誤通知 (R2, R10)**

```python
def call_claude(data_summary):
    prompt_path = os.path.join(SCRIPT_DIR, "prompt_fa_watch.txt")
    with open(prompt_path, encoding="utf-8") as f:
        prompt = f.read()
    full_prompt = f"{prompt}\n\n---\n以下是今日 FA 數據：\n\n{data_summary}"
    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    if result.returncode != 0:
        print(f"claude -p error: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Daily FA Watch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()

    try:
        access_token = refresh_token(env)
        config = load_config()

        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")  # (R2) 台灣時區

        print(f"[FA Watch] {today_str}...", file=sys.stderr)
        snapshot = collect_fa_snapshot(access_token, config)

        history = load_fa_history()
        changes, ref_1d, ref_3d = calc_owned_changes(snapshot, history, today_str)

        history[today_str] = {name: {"pct": info["pct"]} for name, info in snapshot.items()}
        sorted_dates = sorted(history.keys())
        if len(sorted_dates) > 14:
            for old_date in sorted_dates[:-14]:
                del history[old_date]
        save_fa_history(history)

        data_summary = build_fa_watch_data(today_str, snapshot, changes, ref_1d, ref_3d, config)

        if args.dry_run:
            print(data_summary)
            return

        print("Calling claude -p...", file=sys.stderr)
        advice = call_claude(data_summary)
        if not advice:
            print("Claude returned no output.", file=sys.stderr)
            print("\n--- Raw data ---")
            print(data_summary)
            return

        print(advice)

        if args.no_send:
            return

        print("Sending to Telegram...", file=sys.stderr)
        ok = send_telegram(advice, env)
        print("Sent." if ok else "Failed.", file=sys.stderr)

    except Exception as e:
        # (R10) 錯誤通知
        print(f"FA Watch error: {e}", file=sys.stderr)
        try:
            send_telegram(f"⚠️ FA Watch 執行失敗: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test dry-run**

```bash
python daily-advisor/fa_watch.py --dry-run
```

Expected: snapshot data + "首次執行" (no history yet) + 陣容摘要 + 弱點位置 FA

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/fa_watch.py daily-advisor/prompt_fa_watch.txt
git commit -m "feat: add Daily FA Watch with %owned tracking + claude -p"
```

---

### Task 4: Weekly Deep Scan 腳本

**Files:**
- Create: `daily-advisor/weekly_scan.py`
- Create: `daily-advisor/prompt_weekly_scan.txt`

- [ ] **Step 1: 建立 prompt template**

```
你是 Fantasy Baseball waiver wire 分析顧問。這是每週一次的 FA 市場深度掃描。

聯賽：12 隊 H2H One Win 7×7，Punt SV+H + 軟 Punt SB
打者替補門檻：BB% > 8%、OPS > .720、AVG > .240（兩項通過）
SP in-season 門檻：預測 IP > 150 + ERA < 4.00（開季正選門檻 IP>180/ERA<3.50 的放寬版）
跳過：純速度型（punt SB）、RP/CL（punt SV+H）

我的陣容和弱點會附在數據區段中。

根據以下數據，產出本週 FA 市場分析：

1. *新發現* — 本週值得關注的新球員（條列：球員名、位置、為什麼值得注意）
2. *觀察中更新* — waiver-log 觀察中球員的本週狀態變化
3. *%owned 趨勢異常* — 升/降幅最大的球員，判斷是否為行動訊號
4. *本週建議* — 有無需要立即行動的？有無建議跑 /player-eval 深入評估的？

輸出格式：
- Telegram Markdown
- 控制在 3000 字元以內
- 末尾列出建議本週跑 /player-eval 的球員名（如有）

不要解釋規則，直接給分析。
```

- [ ] **Step 2: 建立 weekly_scan.py (R2, R4, R10)**

```python
"""Weekly Deep Scan — FA market analysis every Monday."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import (
    refresh_token, load_env, load_config, api_get,
    YAHOO_STAT_MAP, extract_player_info, parse_player_stats,
    send_telegram,
)
from fa_watch import (
    collect_fa_snapshot, load_fa_history, save_fa_history,
    calc_owned_changes, format_change_rankings,
    WEEKLY_QUERIES, TPE,
)

SUMMARY_FILE = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")


def build_weekly_data(today_str, snapshot, changes, ref_1d, ref_3d, config):
    """Build comprehensive data summary for claude -p."""
    lines = [f"=== Weekly Deep Scan ({today_str}) ===\n"]

    # Roster summary (R6)
    lines.append("--- 我的陣容 ---")
    for b in config.get("batters", []):
        role = "BN" if b["role"] == "bench" else b["role"]
        lines.append(f"  [{role}] {b['name']} ({b['team']}, {'/'.join(b['positions'])})")
    for p in config.get("pitchers", []):
        role = "BN" if p["role"] == "bench" else ("IL" if p["role"] == "IL" else p["type"])
        lines.append(f"  [{role}] {p['name']} ({p['team']}, {p['type']})")

    # Full FA rankings by position
    for pos in ["CF", "SP", "LF", "1B", "2B"]:
        pos_players = [
            (n, i) for n, i in snapshot.items()
            if pos in i["position"].split(",")
        ]
        pos_players.sort(key=lambda x: x[1]["pct"], reverse=True)
        top = pos_players[:15]
        if top:
            lines.append(f"\n--- FA: {pos} ---")
            for name, info in top:
                stats = info.get("stats", {})
                if "ERA" in stats:
                    stat_str = f"ERA {stats.get('ERA', '—')} WHIP {stats.get('WHIP', '—')} K {stats.get('K', '—')} IP {stats.get('IP', '—')}"
                elif "AVG" in stats:
                    stat_str = f"AVG {stats.get('AVG', '—')} OPS {stats.get('OPS', '—')} HR {stats.get('HR', '—')} BB {stats.get('BB', '—')}"
                else:
                    stat_str = ""
                lines.append(f"  {name:20} {info['team']:5} {info['position']:12} {info['pct']:>3}%  {stat_str}")

    # %owned changes
    rankings = format_change_rankings(changes, ref_1d, ref_3d, top_n=10)
    lines.append(f"\n--- %owned 變動 ---\n{rankings}")

    # waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            lines.append(f"\n--- waiver-log.md ---\n{f.read()}")

    # roster-baseline weaknesses
    baseline_path = os.path.join(SCRIPT_DIR, "..", "roster-baseline.md")
    if os.path.exists(baseline_path):
        with open(baseline_path, encoding="utf-8") as f:
            content = f.read()
        for section in ["打者弱點摘要", "SP 弱點摘要", "替換門檻速查"]:
            start = content.find(section)
            if start != -1:
                end = content.find("\n---", start)
                if end == -1:
                    end = len(content)
                lines.append(f"\n--- {section} ---\n{content[start:end].strip()}")

    return "\n".join(lines)


def save_summary(advice):
    """Save scan summary for Daily FA Watch to reference."""
    summary = advice[:800] if len(advice) > 800 else advice
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Summary saved to {SUMMARY_FILE}", file=sys.stderr)


def save_github_issue(today_str, data_summary, advice):
    """Archive as GitHub Issue with waiver-scan label."""
    repo = "huansbox/mlb-fantasy"
    title = f"[Weekly Scan] {today_str}"
    body = f"""## Analysis\n\n{advice}\n\n---\n\n<details>\n<summary>Raw Data</summary>\n\n```\n{data_summary}\n```\n\n</details>"""
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", repo,
             "--title", title, "--body", body,
             "--label", "waiver-scan"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode == 0:
            print(f"Issue created: {result.stdout.strip()}", file=sys.stderr)
        else:
            print(f"GitHub Issue error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"GitHub Issue failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Weekly Deep Scan")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()

    try:
        access_token = refresh_token(env)
        config = load_config()

        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")  # (R2) 台灣時區

        print(f"[Weekly Scan] {today_str}...", file=sys.stderr)

        snapshot = collect_fa_snapshot(access_token, config, queries=WEEKLY_QUERIES)  # (R4) 更大查詢

        history = load_fa_history()
        changes, ref_1d, ref_3d = calc_owned_changes(snapshot, history, today_str)
        history[today_str] = {name: {"pct": info["pct"]} for name, info in snapshot.items()}
        sorted_dates = sorted(history.keys())
        if len(sorted_dates) > 14:
            for old_date in sorted_dates[:-14]:
                del history[old_date]
        save_fa_history(history)

        data_summary = build_weekly_data(today_str, snapshot, changes, ref_1d, ref_3d, config)

        if args.dry_run:
            print(data_summary)
            return

        prompt_path = os.path.join(SCRIPT_DIR, "prompt_weekly_scan.txt")
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
        full_prompt = f"{prompt}\n\n---\n\n{data_summary}"
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        if result.returncode != 0:
            print(f"claude -p error: {result.stderr}", file=sys.stderr)
            print("\n--- Raw data ---")
            print(data_summary)
            return
        advice = result.stdout.strip()
        print(advice)

        save_summary(advice)
        save_github_issue(today_str, data_summary, advice)

        if args.no_send:
            return

        print("Sending to Telegram...", file=sys.stderr)
        ok = send_telegram(advice, env)
        print("Sent." if ok else "Failed.", file=sys.stderr)

    except Exception as e:
        # (R10) 錯誤通知
        print(f"Weekly Scan error: {e}", file=sys.stderr)
        try:
            send_telegram(f"⚠️ Weekly Scan 執行失敗: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test dry-run**

```bash
python daily-advisor/weekly_scan.py --dry-run
```

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/weekly_scan.py daily-advisor/prompt_weekly_scan.txt
git commit -m "feat: add Weekly Deep Scan with comprehensive FA analysis"
```

---

### Task 5: 更新 waiver-scan skill + CLAUDE.md

**Files:**
- Modify: `.claude/commands/waiver-scan.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: waiver-scan 加週二提醒**

在 SOP 頂部（`主動搜尋 FA 市場...` 下方）加入：

```markdown
> **建議頻率**：至少每週二跑一次（在 Monday Weekly Deep Scan 隔天，補 WebSearch 新聞面）。
> Daily FA Watch（每日 07:00 Telegram）和 Weekly Deep Scan（週一 19:30）會自動提醒需要跑的時機。
```

- [ ] **Step 2: CLAUDE.md 更新文件結構 + 週二檢查 + SP in-season 門檻 (R12)**

文件結構表加入：
```markdown
| `daily-advisor/fa_watch.py` | Daily FA Watch（每日 07:00，%owned 追蹤 + claude -p） | ✅ 完成 |
| `daily-advisor/weekly_scan.py` | Weekly Deep Scan（每週一 19:30，完整 FA 分析） | ✅ 完成 |
```

每週檢查清單加入：
```markdown
5. 週二：跑 `/waiver-scan`（互動 session，補 WebSearch）
```

In-Season 管理決策規則加入 SP in-season 放寬門檻：
```markdown
### SP In-Season FA 門檻（放寬版）
- IP > 150 + ERA < 4.00（vs 選秀期 IP > 180 + ERA < 3.50）
- 放寬理由：in-season FA 整體質量低於選秀池，門檻不變會篩不到人
```

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/waiver-scan.md CLAUDE.md
git commit -m "docs: add Tuesday waiver-scan reminder + SP in-season threshold to CLAUDE.md"
```

---

### Task 6: 更新 README.md + VPS 部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新排程說明**

```markdown
  - Cron 排程：
    - **Weekly Scan** UTC 11:30 每週一（台灣 19:30）：FA 市場深度掃描
    - **速報** UTC 13:45（台灣 21:45）：SP 排程 + 對戰分析
    - **最終報** UTC 21:00（台灣 05:00）：lineup 確認 + 調整建議
    - **FA Watch** UTC 23:00（台灣 07:00）：%owned 追蹤 + FA 快報
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add FA Watch + Weekly Scan to README schedule"
```

- [ ] **Step 3: VPS 部署**

```bash
ssh root@107.175.30.172 'cd /opt/mlb-fantasy && git pull'
```

Add to `/etc/cron.d/daily-advisor`:
```
# Weekly Deep Scan — 台灣 19:30 每週一 = UTC 11:30 Monday
30 11 * * 1 root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/weekly_scan.py >> /var/log/weekly-scan.log 2>&1"

# Daily FA Watch — 台灣 07:00 = UTC 23:00
0 23 * * * root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/fa_watch.py >> /var/log/fa-watch.log 2>&1"
```

---

### Task 7: Integration test

- [ ] **Step 1: fa_watch.py dry-run（首次，無歷史）**

```bash
python daily-advisor/fa_watch.py --dry-run
```

Expected: snapshot + "需累積至少 2 天數據" + 陣容摘要 + 弱點位置 FA

- [ ] **Step 2: 再跑一次模擬隔天（驗證 %owned 歷史）**

```bash
python daily-advisor/fa_watch.py --dry-run --date 2026-03-30
```

Expected: 24h 變動排行出現

- [ ] **Step 3: weekly_scan.py dry-run**

```bash
python daily-advisor/weekly_scan.py --dry-run
```

Expected: 完整 FA 數據（多位置）+ waiver-log + baseline 弱點

- [ ] **Step 4: 驗證 main.py 無 regression**

```bash
python daily-advisor/main.py --dry-run --date 2026-03-29
```

- [ ] **Step 5: 驗證 .gitignore**

```bash
git status
```

Expected: `fa_history.json` 和 `weekly_scan_summary.txt` 不出現在 untracked files
