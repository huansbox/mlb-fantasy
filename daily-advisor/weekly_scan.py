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

    try:
        access_token = refresh_token(env)
        config = load_config()

        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")  # (R2)

        print(f"[Weekly Scan] {today_str}...", file=sys.stderr)

        snapshot = collect_fa_snapshot(access_token, config, queries=WEEKLY_QUERIES)  # (R4)

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
        # (R10)
        print(f"Weekly Scan error: {e}", file=sys.stderr)
        try:
            send_telegram(f"Weekly Scan failed: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
