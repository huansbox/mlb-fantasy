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

TPE = ZoneInfo("Asia/Taipei")

# Default queries for daily watch (R3: ALL 50 + lastweek)
DAILY_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=20"),
    ("CF", "status=A;position=CF;sort=AR;count=10"),
    ("SP", "status=A;position=SP;sort=AR;count=10"),
    ("1B", "status=A;position=1B;sort=AR;count=10"),
]

# Expanded queries for weekly scan (R4)
WEEKLY_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=30"),
    ("CF", "status=A;position=CF;sort=AR;count=15"),
    ("SP", "status=A;position=SP;sort=AR;count=20"),
    ("1B", "status=A;position=1B;sort=AR;count=10"),
    ("LF", "status=A;position=LF;sort=AR;count=10"),
    ("2B", "status=A;position=2B;sort=AR;count=10"),
]


# ── Snapshot collection ──


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
        path = f"/league/{league_key}/players;{filters};out=stats,percent_owned,ownership"
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
                        "waiver_date": p.get("waiver_date", ""),
                    }
        except Exception as e:
            print(f"FA query error ({label}): {e}", file=sys.stderr)
        time.sleep(1)  # (R8) API rate limit

    return snapshot


# ── %owned history ──


FA_HISTORY_FILE = os.path.join(SCRIPT_DIR, "fa_history.json")


def load_fa_history():
    if os.path.exists(FA_HISTORY_FILE):
        with open(FA_HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_fa_history(history):
    with open(FA_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def calc_owned_changes(today_snapshot, history, today_str):
    """Calculate %owned changes for 24h and 3d windows.

    Returns (changes_list, ref_1d_date, ref_3d_date).
    """
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
            "waiver_date": info.get("waiver_date", ""),
        })

    return changes, ref_1d, ref_3d


def format_change_rankings(changes, ref_1d, ref_3d, top_n=5):
    """Format top risers and fallers with reference date info."""
    lines = []

    # (R11) data window hint
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
            wtag = f" [W {c['waiver_date']}]" if c.get("waiver_date") else ""
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}{wtag}")

    if fallers and fallers[0]["d1"] < 0:
        lines.append("\n降幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in fallers:
            if c["d1"] >= 0:
                break
            d1 = str(c["d1"])
            d3 = str(c["d3"]) if c["d3"] is not None else "—"
            wtag = f" [W {c['waiver_date']}]" if c.get("waiver_date") else ""
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}{wtag}")

    return "\n".join(lines)


# ── Data summary for claude -p ──


def build_fa_watch_data(today_str, snapshot, changes, ref_1d, ref_3d, config):
    """Build data summary for claude -p."""
    lines = [f"=== FA Watch ({today_str}) ===\n"]

    # %owned changes
    rankings = format_change_rankings(changes, ref_1d, ref_3d)
    lines.append(rankings)

    # (R6) Roster summary
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


# ── Claude + Telegram ──


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

        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")  # (R2)

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
        # (R10)
        print(f"FA Watch error: {e}", file=sys.stderr)
        try:
            send_telegram(f"FA Watch failed: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
