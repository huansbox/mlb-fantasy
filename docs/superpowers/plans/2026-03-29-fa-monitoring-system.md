# FA Monitoring System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立三層 FA 監控系統 — Daily FA Watch（每日 07:00）+ Weekly Deep Scan（每週一 19:30）+ %owned 歷史追蹤，搭配週二 manual /waiver-scan 提醒。

**Architecture:** 兩個新 Python 腳本（`fa_watch.py` + `weekly_scan.py`），共用 `yahoo_query.py` 的 Yahoo API 函式。%owned 快照存 JSON，24h/3d 雙窗口變動排行。Weekly Deep Scan 摘要存檔供 Daily FA Watch 讀取作為 claude -p context。

**Tech Stack:** Python 3.10+ / urllib（零外部依賴）/ Claude Code CLI / Telegram Bot API / GitHub Issue

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
| `daily-advisor/fa_watch.py` | Create | Daily FA Watch 主腳本 |
| `daily-advisor/weekly_scan.py` | Create | Weekly Deep Scan 主腳本 |
| `daily-advisor/prompt_fa_watch.txt` | Create | Daily FA Watch prompt template |
| `daily-advisor/prompt_weekly_scan.txt` | Create | Weekly Deep Scan prompt template |
| `daily-advisor/fa_history.json` | Auto-generated | %owned 每日快照 |
| `daily-advisor/weekly_scan_summary.txt` | Auto-generated | 最新 Weekly Deep Scan 摘要 |
| `daily-advisor/yahoo_query.py` | Modify | 提取共用函式供其他腳本 import |
| `.claude/commands/waiver-scan.md` | Modify | 加入週二提醒規則 |
| `CLAUDE.md` | Modify | 加入 FA 監控說明 + 週二檢查 |
| `README.md` | Modify | 更新排程說明 |

---

### Task 1: 從 yahoo_query.py 提取共用模組

`fa_watch.py` 和 `weekly_scan.py` 都需要 Yahoo API 函式（`refresh_token`、`api_get`、`load_env`、`load_config`、`YAHOO_STAT_MAP`、`extract_player_info`、`parse_player_stats`）。目前這些全在 `yahoo_query.py` 裡，需要能被 import。

**Files:**
- Modify: `daily-advisor/yahoo_query.py`

- [ ] **Step 1: 確認 yahoo_query.py 可被 import**

`yahoo_query.py` 已有 `if __name__ == "__main__": main()` guard，所以 import 時不會自動執行 CLI。但 `SCRIPT_DIR` 用 `__file__` 計算，import 時會指向 yahoo_query.py 的位置而非呼叫方，這對 `.env` 和 `yahoo_token.json` 路徑是正確的（它們都在 `daily-advisor/` 下）。

驗證：
```bash
python -c "from daily-advisor.yahoo_query import refresh_token, load_env; print('ok')"
```

如果失敗（`daily-advisor` 含連字號不能作 Python module name），需要用 `importlib` 或 `sys.path` workaround。

- [ ] **Step 2: 建立 import helper**

在 `fa_watch.py` 和 `weekly_scan.py` 頂部用相同的 import pattern：

```python
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import (
    refresh_token, load_env, load_config, api_get,
    YAHOO_STAT_MAP, extract_player_info, parse_player_stats,
)
```

驗證可 import 後 commit。

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/yahoo_query.py
git commit -m "refactor: ensure yahoo_query.py is importable"
```

（如果不需要改動 yahoo_query.py，跳過此 commit）

---

### Task 2: %owned 歷史追蹤模組

**Files:**
- Create: `daily-advisor/fa_watch.py`（先建立 %owned 快照功能）

- [ ] **Step 1: 建立 FA 快照收集函式**

```python
def collect_fa_snapshot(access_token, config):
    """Query FA players across key positions, return {name: {team, pos, pct, stats}}."""
    league_key = config["league"]["league_key"]
    snapshot = {}

    # Query multiple positions + overall
    queries = [
        ("ALL", "status=FA;sort=AR;count=30"),
        ("CF", "status=FA;position=CF;sort=AR;count=10"),
        ("SP", "status=FA;position=SP;sort=AR;count=10"),
        ("1B", "status=FA;position=1B;sort=AR;count=10"),
    ]

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
                        "pct": int(p["percent_owned"]) if p["percent_owned"] else 0,
                        "stats": stats,
                    }
        except Exception as e:
            print(f"FA query error ({label}): {e}", file=sys.stderr)

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

- [ ] **Step 3: 建立變動排行榜函式**

```python
def calc_owned_changes(today_snapshot, history, today_str):
    """Calculate %owned changes for 24h and 3d windows.
    Returns list of {name, team, pos, pct, d1, d3, stats} sorted by abs change.
    """
    dates = sorted(history.keys())

    # Find reference dates
    ref_1d = None  # yesterday
    ref_3d = None  # 3 days ago
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
            "name": name,
            "team": info["team"],
            "position": info["position"],
            "pct": pct,
            "d1": d1,
            "d3": d3,
            "stats": info.get("stats", {}),
        })

    return changes
```

- [ ] **Step 4: 格式化排行榜輸出**

```python
def format_change_rankings(changes, top_n=5):
    """Format top risers and fallers."""
    lines = []

    # Filter to players with 24h data
    with_d1 = [c for c in changes if c["d1"] is not None and c["d1"] != 0]

    risers = sorted(with_d1, key=lambda x: x["d1"], reverse=True)[:top_n]
    fallers = sorted(with_d1, key=lambda x: x["d1"])[:top_n]

    if risers:
        lines.append("升幅前 5:")
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

- [ ] **Step 1: 建立 prompt template**

```
你是 Fantasy Baseball FA 市場監控顧問。根據以下數據，產出今日 FA 市場快報。

聯賽：12 隊 H2H One Win 7×7，Punt SV+H + 軟 Punt SB
陣容弱點：CF 深度（Buxton 傷病風險）、Kwan 最弱（VOR +2）

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

- [ ] **Step 2: 建立 main 流程**

```python
def build_fa_watch_data(today_str, snapshot, changes, config):
    """Build data summary for claude -p."""
    lines = [f"=== FA Watch ({today_str}) ===\n"]

    # %owned changes
    rankings = format_change_rankings(changes)
    if rankings:
        lines.append(rankings)
    else:
        lines.append("（首次執行或無歷史數據，無變動排行）")

    # Key position FA top players (from snapshot, filter by position)
    lines.append("\n--- 弱點位置 FA ---")
    for pos in ["CF", "SP", "1B"]:
        pos_players = [
            (n, i) for n, i in snapshot.items()
            if pos in i["position"].split(",")
        ]
        pos_players.sort(key=lambda x: x[1]["pct"], reverse=True)
        top = pos_players[:3]
        if top:
            names = ", ".join(
                f"{n}({i['pct']}%)" for n, i in top
            )
            lines.append(f"  {pos}: {names}")

    # Weekly scan summary (if exists)
    summary_path = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            summary = f.read().strip()
        lines.append(f"\n--- 本週 Deep Scan 摘要 ---\n{summary}")
    else:
        lines.append("\n（尚無 Weekly Deep Scan 摘要）")

    # Watchlist status from waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            log_content = f.read()
        # Extract "觀察中" section names
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
                # Check if in today's snapshot
                pct = snapshot.get(player_name, {}).get("pct", "N/A")
                in_watch.append(f"  {player_name}: {pct}%")
        if in_watch:
            lines.append(f"\n--- 觀察中球員 %owned ---")
            lines.extend(in_watch)

    # Tuesday reminder
    day_of_week = datetime.strptime(today_str, "%Y-%m-%d").weekday()
    if day_of_week == 1:  # Tuesday
        lines.append("\n📌 今天是週二，建議開 Claude Code 跑 /waiver-scan")

    return "\n".join(lines)


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


def send_telegram(message, env):
    """Same as main.py's send_telegram."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
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
        print(f"Telegram error: {e}", file=sys.stderr)
        return False
```

- [ ] **Step 3: 建立 CLI + main()**

```python
def main():
    parser = argparse.ArgumentParser(description="Daily FA Watch")
    parser.add_argument("--dry-run", action="store_true", help="Print data only, skip claude and telegram")
    parser.add_argument("--no-send", action="store_true", help="Run claude but don't send to Telegram")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()
    access_token = refresh_token(env)
    config = load_config()

    today_str = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    print(f"[FA Watch] Collecting snapshot for {today_str}...", file=sys.stderr)
    snapshot = collect_fa_snapshot(access_token, config)

    # Load history, calc changes, save today's snapshot
    history = load_fa_history()
    changes = calc_owned_changes(snapshot, history, today_str)

    # Save snapshot (only pct, not full stats — keep file small)
    history[today_str] = {name: {"pct": info["pct"]} for name, info in snapshot.items()}
    # Keep only last 14 days
    sorted_dates = sorted(history.keys())
    if len(sorted_dates) > 14:
        for old_date in sorted_dates[:-14]:
            del history[old_date]
    save_fa_history(history)

    # Build data summary
    data_summary = build_fa_watch_data(today_str, snapshot, changes, config)

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


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test dry-run**

```bash
python daily-advisor/fa_watch.py --dry-run
python daily-advisor/fa_watch.py --dry-run --date 2026-03-29
```

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
SP 門檻：預測 IP > 150 + ERA < 4.00（in-season 放寬版）
跳過：純速度型（punt SB）、RP/CL（punt SV+H）

根據以下數據，產出本週 FA 市場分析：

1. *新發現* — 本週值得關注的新球員（條列：球員名、位置、為什麼值得注意）
2. *觀察中更新* — waiver-log 觀察中球員的本週狀態變化
3. *%owned 趨勢異常* — 3 天升/降幅最大的球員，判斷是否為行動訊號
4. *本週建議* — 有無需要立即行動的？有無建議跑 /player-eval 深入評估的？

輸出格式：
- Telegram Markdown
- 控制在 3000 字元以內
- 末尾列出建議本週跑 /player-eval 的球員名（如有）

不要解釋規則，直接給分析。
```

- [ ] **Step 2: 建立 weekly_scan.py**

結構類似 fa_watch.py，但數據更完整：

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
)

# Reuse fa_watch's snapshot functions
from fa_watch import (
    collect_fa_snapshot, load_fa_history, save_fa_history,
    calc_owned_changes, format_change_rankings, send_telegram,
)

SUMMARY_FILE = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")


def build_weekly_data(today_str, snapshot, changes, config):
    """Build comprehensive data summary for claude -p."""
    lines = [f"=== Weekly Deep Scan ({today_str}) ===\n"]

    # Full FA rankings by position (more detailed than daily)
    for pos, count in [("ALL", 20), ("CF", 10), ("SP", 15), ("1B", 10), ("LF", 10)]:
        lines.append(f"\n--- FA: {pos} (top {count}) ---")
        if pos == "ALL":
            pos_players = sorted(snapshot.items(), key=lambda x: x[1]["pct"], reverse=True)[:count]
        else:
            pos_players = [
                (n, i) for n, i in snapshot.items()
                if pos in i["position"].split(",")
            ]
            pos_players.sort(key=lambda x: x[1]["pct"], reverse=True)
            pos_players = pos_players[:count]

        for name, info in pos_players:
            stats = info.get("stats", {})
            if "ERA" in stats:
                stat_str = f"ERA {stats.get('ERA', '—')} WHIP {stats.get('WHIP', '—')} K {stats.get('K', '—')} IP {stats.get('IP', '—')}"
            elif "AVG" in stats:
                stat_str = f"AVG {stats.get('AVG', '—')} OPS {stats.get('OPS', '—')} HR {stats.get('HR', '—')} BB {stats.get('BB', '—')}"
            else:
                stat_str = ""
            lines.append(f"  {name:20} {info['team']:5} {info['position']:12} {info['pct']:>3}%  {stat_str}")

    # %owned changes
    rankings = format_change_rankings(changes, top_n=10)
    if rankings:
        lines.append(f"\n--- %owned 變動排行（3d） ---\n{rankings}")

    # Current waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            lines.append(f"\n--- waiver-log.md ---\n{f.read()}")

    # Current roster-baseline weaknesses
    baseline_path = os.path.join(SCRIPT_DIR, "..", "roster-baseline.md")
    if os.path.exists(baseline_path):
        with open(baseline_path, encoding="utf-8") as f:
            content = f.read()
        # Extract weakness sections only
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
    # Extract a condensed version (first ~500 chars or up to first section)
    summary = advice[:800] if len(advice) > 800 else advice
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Summary saved to {SUMMARY_FILE}", file=sys.stderr)


def save_github_issue(today_str, data_summary, advice):
    """Archive as GitHub Issue with waiver-scan label."""
    repo = "huansbox/mlb-fantasy"
    title = f"[Weekly Scan] {today_str}"
    body = f"""## Analysis

{advice}

---

<details>
<summary>Raw Data</summary>

```
{data_summary}
```

</details>
"""
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
    access_token = refresh_token(env)
    config = load_config()

    today_str = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    print(f"[Weekly Scan] {today_str}...", file=sys.stderr)

    # Collect comprehensive snapshot
    snapshot = collect_fa_snapshot(access_token, config)

    # Update history + calc changes
    history = load_fa_history()
    changes = calc_owned_changes(snapshot, history, today_str)
    history[today_str] = {name: {"pct": info["pct"]} for name, info in snapshot.items()}
    sorted_dates = sorted(history.keys())
    if len(sorted_dates) > 14:
        for old_date in sorted_dates[:-14]:
            del history[old_date]
    save_fa_history(history)

    data_summary = build_weekly_data(today_str, snapshot, changes, config)

    if args.dry_run:
        print(data_summary)
        return

    # Claude analysis
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

    # Save summary for daily FA watch
    save_summary(advice)

    # Archive to GitHub Issue
    save_github_issue(today_str, data_summary, advice)

    if args.no_send:
        return

    print("Sending to Telegram...", file=sys.stderr)
    ok = send_telegram(advice, env)
    print("Sent." if ok else "Failed.", file=sys.stderr)


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

在 SOP 頂部加入：

```markdown
> **建議頻率**：至少每週二跑一次（在 Monday Weekly Deep Scan 隔天，補 WebSearch 新聞面）。
> Daily FA Watch（每日 07:00 Telegram）和 Weekly Deep Scan（週一 19:30）會自動提醒需要跑的時機。
```

- [ ] **Step 2: CLAUDE.md 更新文件結構 + 週二檢查**

在文件結構表加入新工具：
```markdown
| `daily-advisor/fa_watch.py` | Daily FA Watch（每日 07:00，%owned 追蹤 + claude -p） | ✅ 完成 |
| `daily-advisor/weekly_scan.py` | Weekly Deep Scan（每週一 19:30，完整 FA 分析） | ✅ 完成 |
```

在「每週檢查清單」加入：
```markdown
5. 週二：跑 `/waiver-scan`（互動 session，補 WebSearch）
```

- [ ] **Step 3: CLAUDE.md 開場 `/s` 週二提醒**

確認 `/s` skill 的 Step 4 能檢查到 CLAUDE.md 的週二規則。不需改 `/s` 本身 — 它已經讀 CLAUDE.md 待辦。只需確保 CLAUDE.md 寫清楚。

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/waiver-scan.md CLAUDE.md
git commit -m "docs: add Tuesday waiver-scan reminder + FA monitoring to CLAUDE.md"
```

---

### Task 6: 更新 README.md + VPS 部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新排程說明**

```markdown
  - Cron 排程：
    - **速報** UTC 13:45（台灣 21:45）：SP 排程 + 對戰分析
    - **Weekly Scan** UTC 11:30（台灣 19:30，每週一）：FA 市場深度掃描
    - **最終報** UTC 21:00（台灣 05:00）：lineup 確認 + 調整建議
    - **FA Watch** UTC 23:00（台灣 07:00）：%owned 追蹤 + FA 快報
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add FA Watch + Weekly Scan to README schedule"
```

- [ ] **Step 3: VPS cron 部署**

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

- [ ] **Step 1: fa_watch.py dry-run**

```bash
python daily-advisor/fa_watch.py --dry-run
```

Expected: FA snapshot + change rankings (first run = no history, should show "首次執行")

- [ ] **Step 2: Run again to test %owned history**

```bash
python daily-advisor/fa_watch.py --dry-run --date 2026-03-30
```

Expected: should show 24h changes vs first run

- [ ] **Step 3: weekly_scan.py dry-run**

```bash
python daily-advisor/weekly_scan.py --dry-run
```

Expected: comprehensive FA data + waiver-log + baseline weaknesses

- [ ] **Step 4: Verify main.py not broken**

```bash
python daily-advisor/main.py --dry-run --date 2026-03-29
```

- [ ] **Step 5: Verify fa_history.json is in .gitignore**

```bash
echo "daily-advisor/fa_history.json" >> .gitignore
echo "daily-advisor/weekly_scan_summary.txt" >> .gitignore
git add .gitignore
git commit -m "chore: add fa_history.json and weekly_scan_summary.txt to gitignore"
```
