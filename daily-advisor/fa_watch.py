"""Daily FA Watch — %owned tracking + Statcast quality monitoring."""

import argparse
import json
import os
import re
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
    send_telegram, _normalize, _search_players,
    pitcher_type, calc_position_depth,
)

TPE = ZoneInfo("Asia/Taipei")

# Base queries (always included)
BASE_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=20"),
    ("SP", "status=A;position=SP;sort=AR;count=10"),
]

BASE_WEEKLY_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=30"),
    ("SP", "status=A;position=SP;sort=AR;count=20"),
]


def build_position_queries(config, weekly=False):
    """Build FA queries dynamically: base + thin positions from config."""
    base = list(BASE_WEEKLY_QUERIES if weekly else BASE_QUERIES)
    thin = calc_position_depth(config)
    count = 15 if weekly else 10
    for pos in thin:
        base.append((pos, f"status=A;position={pos};sort=AR;count={count}"))
    return base


# ── Snapshot collection ──


def collect_fa_snapshot(access_token, config, queries=None):
    """Query FA players across positions. Returns {name: {team, position, pct, stats}}.

    Args:
        queries: list of (label, filter_str) tuples. Defaults to dynamic position queries.
    """
    if queries is None:
        queries = build_position_queries(config)
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


# ── Candidate collection (from fa_history + waiver-log, no broad Yahoo query) ──

# Regex: "### Player Name (TEAM, Position)" — half-width parens, 2-3 char team abbr
_WAIVER_PLAYER_RE = re.compile(r"^### (.+?) \((\w{2,3}), (.+?)\)")


def parse_waiver_log_watchlist():
    """Parse waiver-log.md '觀察中' section for player names + team + position."""
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if not os.path.exists(waiver_log_path):
        return []
    with open(waiver_log_path, encoding="utf-8") as f:
        content = f.read()
    players = []
    in_section = False
    for line in content.split("\n"):
        if line.startswith("## 觀察中"):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            break
        if in_section and line.startswith("### "):
            if "已在陣容" in line or "條件 Pass" in line:
                continue
            m = _WAIVER_PLAYER_RE.match(line)
            if m:
                players.append({
                    "name": m.group(1).strip(),
                    "team": m.group(2),
                    "position": m.group(3).split(")")[0].strip(),
                })
    return players


def collect_candidates(history, today_str, top_n=5):
    """Combine %owned risers (from fa_history) + waiver-log watchlist.

    Returns list of dicts {name, team, position, pct} for Statcast pipeline.
    Does NOT require a live Yahoo snapshot — reads accumulated fa_history.
    """
    # Find latest two dates in history for %owned delta
    dates = sorted(d for d in history.keys() if d <= today_str)
    latest = dates[-1] if dates else None
    prev = dates[-2] if len(dates) >= 2 else None

    risers = []
    if latest and prev:
        snap_now = history[latest]
        snap_prev = history[prev]
        for name, info in snap_now.items():
            pct_now = info.get("pct", 0)
            pct_prev = snap_prev.get(name, {}).get("pct", pct_now)
            delta = pct_now - pct_prev
            if delta > 0:
                risers.append({
                    "name": name,
                    "team": info.get("team", ""),
                    "position": info.get("position", ""),
                    "pct": pct_now,
                    "d1": delta,
                })
        risers.sort(key=lambda x: x["d1"], reverse=True)
        risers = risers[:top_n]

    # Waiver-log watchlist
    watchlist = parse_waiver_log_watchlist()

    # Merge + deduplicate (normalize names for accent matching)
    seen = set()
    candidates = []
    for item in risers:
        key = _normalize(item["name"])
        if key not in seen:
            seen.add(key)
            candidates.append(item)
    for item in watchlist:
        key = _normalize(item["name"])
        if key not in seen:
            seen.add(key)
            # Add pct from latest history if available
            pct = 0
            if latest:
                for hname, hinfo in history[latest].items():
                    if _normalize(hname) == key:
                        pct = hinfo.get("pct", 0)
                        break
            candidates.append({**item, "pct": pct})

    print(f"  Candidates: {len(risers)} risers + {len(watchlist)} watchlist "
          f"→ {len(candidates)} total", file=sys.stderr)
    return candidates


def _check_player_ownership(name, league_key, access_token):
    """Check if a player is FA or rostered via Yahoo API (2 calls).

    Returns ownership_type: 'freeagents', 'waivers', 'team', or None on error.
    """
    players_data = _search_players(name, league_key, access_token)
    if not players_data:
        return None
    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        player_key = p.get("player_key")
        if not player_key:
            return None
        od = api_get(
            f"/league/{league_key}/players;player_keys={player_key}"
            f";out=ownership",
            access_token,
        )
        p2 = extract_player_info(
            od["fantasy_content"]["league"][1]["players"]["0"]["player"])
        return p2.get("ownership_type", "")
    return None


def check_fa_status(candidates, access_token, config):
    """Filter out candidates that have been rostered. Returns FA-only list."""
    league_key = config["league"]["league_key"]
    fa_candidates = []
    for c in candidates:
        try:
            ownership = _check_player_ownership(
                c["name"], league_key, access_token)
            if ownership == "team":
                print(f"  SKIP {c['name']}: rostered", file=sys.stderr)
            else:
                fa_candidates.append(c)
            time.sleep(0.5)
        except Exception as e:
            print(f"  FA check failed for {c['name']}: {e}", file=sys.stderr)
            fa_candidates.append(c)
    print(f"  FA check: {len(candidates)} → {len(fa_candidates)} still FA",
          file=sys.stderr)
    return fa_candidates


# ── Waiver-log auto-cleanup ──


def cleanup_rostered_watchlist(access_token, config, today_str):
    """Check watchlist players' FA status, auto-move rostered ones to 已結案.

    Runs during --snapshot-only (TW 15:15). Modifies waiver-log.md + git commit.
    Only checks active watchlist (not 條件 Pass — those track "被 drop 回 FA").
    """
    watchlist = parse_waiver_log_watchlist()
    if not watchlist:
        return

    league_key = config["league"]["league_key"]
    rostered = []
    for w in watchlist:
        try:
            ownership = _check_player_ownership(
                w["name"], league_key, access_token)
            if ownership == "team":
                rostered.append(w)
                print(f"  Rostered: {w['name']}", file=sys.stderr)
            time.sleep(0.5)
        except Exception as e:
            print(f"  Ownership check failed for {w['name']}: {e}",
                  file=sys.stderr)

    if not rostered:
        print("  Watchlist cleanup: all still FA", file=sys.stderr)
        return

    # Modify waiver-log.md: move rostered players from 觀察中 → 已結案
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    with open(waiver_log_path, encoding="utf-8") as f:
        content = f.read()

    closed_entries = []
    for player in rostered:
        name = re.escape(player["name"])
        # Match: ### Name (Team, Pos)...\n + all lines until next ### or ##
        pattern = re.compile(
            rf"### {name} \([^)]+\)[^\n]*\n(?:(?!### |## ).*\n)*",
            re.MULTILINE,
        )
        match = pattern.search(content)
        if match:
            content = content[:match.start()] + content[match.end():]
            closed_entries.append(
                f"### {player['name']} ({player['team']}, {player['position']})"
                f" — 被搶（自動偵測）\n"
                f"- {today_str}：Yahoo ownership_type=team，從觀察中移除。\n"
            )

    if not closed_entries:
        return

    # Insert at top of 已結案 section
    closed_marker = "## 已結案\n"
    if closed_marker in content:
        pos = content.index(closed_marker) + len(closed_marker)
        insert = "\n" + "\n".join(closed_entries)
        content = content[:pos] + insert + content[pos:]

    # Clean up excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    with open(waiver_log_path, "w", encoding="utf-8") as f:
        f.write(content)

    names = ", ".join(p["name"] for p in rostered)
    print(f"  Watchlist cleanup: moved {len(rostered)} to 已結案 ({names})",
          file=sys.stderr)

    # Git commit + push
    try:
        repo_root = os.path.join(SCRIPT_DIR, "..")
        subprocess.run(
            ["git", "add", "waiver-log.md"],
            cwd=repo_root, capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"chore(waiver-log): auto-close rostered players ({names})"],
            cwd=repo_root, capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "push"],
            cwd=repo_root, capture_output=True, timeout=30,
        )
        print("  Git push OK", file=sys.stderr)
    except Exception as e:
        print(f"  Git push failed: {e}", file=sys.stderr)


# ── Statcast pipeline (lazy import weekly_scan to avoid circular dependency) ──


def run_statcast_pipeline(candidates, config):
    """Download Savant CSVs, quality filter, enrich candidates.

    Returns (enriched_list, savant_2026_csvs). enriched_list may be empty.
    """
    # Lazy import: weekly_scan imports fa_watch at module level
    from weekly_scan import (
        download_savant_csvs, filter_by_savant, enrich_layer3,
    )

    # Build snapshot-like dict for filter_by_savant
    candidate_snapshot = {
        c["name"]: {
            "team": c["team"],
            "position": c["position"],
            "pct": c.get("pct", 0),
            "stats": {},
            "waiver_date": "",
        }
        for c in candidates
    }

    print("  Downloading 2026 Savant CSVs...", file=sys.stderr)
    savant_2026 = download_savant_csvs(2026)

    # Quality filter (P40/P50 thresholds, 2/3 pass)
    filtered = filter_by_savant(candidate_snapshot, savant_2026)

    if not filtered:
        print("  No candidates passed quality filter", file=sys.stderr)
        return [], savant_2026

    # Enrichment (savant_prior=True for early season 2025 context)
    enriched = enrich_layer3(filtered, savant_2026, config, savant_prior=True)

    return enriched, savant_2026


# ── Data summary for claude -p ──


def build_fa_watch_data(today_str, enriched, changes, ref_1d, ref_3d,
                        config, savant_2026, history):
    """Build Statcast-enriched data summary for claude -p."""
    # Lazy import: weekly_scan imports fa_watch at module level
    from weekly_scan import (
        build_roster_summary, _format_fa_batter, _format_fa_pitcher,
        _extract_eval_framework,
    )

    lines = [f"=== FA Watch ({today_str}) ===\n"]

    # 1. Evaluation framework from CLAUDE.md
    framework = _extract_eval_framework()
    if framework:
        lines.append(f"--- 評估框架（from CLAUDE.md）---\n{framework}\n")

    # 2. Roster summary (with 2026 Statcast)
    lines.append(build_roster_summary(config, savant_2026))

    # 3. FA candidates (Statcast enriched)
    if enriched:
        fa_batters = [p for p in enriched if p["fa_type"] == "batter"]
        fa_sps = [p for p in enriched if p["fa_type"] == "sp"]
        fa_rps = [p for p in enriched if p["fa_type"] == "rp"]

        if fa_batters:
            lines.append(f"\n--- FA 打者候選 ({len(fa_batters)} 人) ---")
            for p in fa_batters:
                lines.append(_format_fa_batter(p))
        if fa_sps:
            lines.append(f"\n--- FA SP 候選 ({len(fa_sps)} 人) ---")
            for p in fa_sps:
                lines.append(_format_fa_pitcher(p))
        if fa_rps:
            lines.append(f"\n--- FA RP 候選 ({len(fa_rps)} 人) ---")
            for p in fa_rps:
                lines.append(_format_fa_pitcher(p))

        lines.append(f"\n（共 {len(enriched)} 人通過品質門檻，"
                     f"來源：%owned risers + waiver-log 觀察中）")
    else:
        lines.append("\n--- FA 候選 ---\n（無候選通過 Statcast 品質門檻）")

    # 4. %owned changes overview
    rankings = format_change_rankings(changes, ref_1d, ref_3d)
    lines.append(f"\n--- %owned 變動 ---\n{rankings}")

    # 5. Watchlist status
    watchlist = parse_waiver_log_watchlist()
    if watchlist:
        enriched_names = {_normalize(p["name"]) for p in enriched} if enriched else set()
        latest_date = sorted(history.keys())[-1] if history else None
        latest_snap = history.get(latest_date, {}) if latest_date else {}
        lines.append("\n--- 觀察中球員 %owned ---")
        for w in watchlist:
            key = _normalize(w["name"])
            # Look up %owned from history
            pct = "N/A"
            for hname, hinfo in latest_snap.items():
                if _normalize(hname) == key:
                    pct = f"{hinfo.get('pct', 0)}%"
                    break
            tag = " [Statcast ✓]" if key in enriched_names else ""
            lines.append(f"  {w['name']} ({w['team']}, {w['position']}): {pct}{tag}")

    # 6. Weekly scan summary (reference)
    summary_path = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")
    if os.path.exists(summary_path):
        mtime = os.path.getmtime(summary_path)
        age_days = (datetime.now().timestamp() - mtime) / 86400
        with open(summary_path, encoding="utf-8") as f:
            summary = f.read().strip()
        freshness = f"⚠️ {int(age_days)} 天前" if age_days > 7 else f"{int(age_days)}d ago"
        lines.append(f"\n--- 本週 Deep Scan 摘要（{freshness}）---\n{summary}")

    # 7. Tuesday reminder
    day_of_week = datetime.strptime(today_str, "%Y-%m-%d").weekday()
    if day_of_week == 1:
        lines.append("\n今天是週二，建議開 Claude Code 跑 /waiver-scan")

    return "\n".join(lines)


# ── GitHub Issue archive ──


def save_github_issue(today_str, data_summary, advice):
    """Archive as GitHub Issue with fa-watch label."""
    repo = "huansbox/mlb-fantasy"
    title = f"[FA Watch] {today_str}"
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
             "--label", "fa-watch"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode == 0:
            print(f"Issue created: {result.stdout.strip()}", file=sys.stderr)
        else:
            print(f"GitHub Issue error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"GitHub Issue failed: {e}", file=sys.stderr)


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
    parser = argparse.ArgumentParser(description="Daily FA Watch (with Statcast)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true",
                        help="Collect and save FA snapshot only (no Statcast/Claude/Telegram)")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()

    try:
        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")
        config = load_config()

        # ── --snapshot-only: broad Yahoo query → save history → exit ──
        if args.snapshot_only:
            access_token = refresh_token(env)
            print(f"[FA Watch snapshot] {today_str}...", file=sys.stderr)
            queries = build_position_queries(config)
            snapshot = collect_fa_snapshot(access_token, config, queries)
            history = load_fa_history()
            history[today_str] = {
                name: {"pct": info["pct"], "team": info["team"],
                       "position": info["position"]}
                for name, info in snapshot.items()
            }
            sorted_dates = sorted(history.keys())
            if len(sorted_dates) > 14:
                for old_date in sorted_dates[:-14]:
                    del history[old_date]
            save_fa_history(history)
            print(f"[FA Watch] Snapshot saved ({len(snapshot)} players)",
                  file=sys.stderr)

            # Auto-cleanup: move rostered watchlist players to 已結案
            cleanup_rostered_watchlist(access_token, config, today_str)
            return

        # ── Analysis mode: read fa_history + waiver-log → Statcast pipeline ──
        print(f"[FA Watch] {today_str}...", file=sys.stderr)
        access_token = refresh_token(env)

        # Phase 1: Collect candidates, then filter out rostered players
        history = load_fa_history()
        candidates = collect_candidates(history, today_str)
        if candidates:
            candidates = check_fa_status(candidates, access_token, config)

        # Compute %owned changes from history (for format_change_rankings)
        dates = sorted(history.keys())
        latest = dates[-1] if dates else None
        latest_snap = history.get(latest, {})
        # Build a snapshot-like structure for calc_owned_changes
        pseudo_snapshot = {
            name: {
                "pct": info.get("pct", 0),
                "team": info.get("team", ""),
                "position": info.get("position", ""),
            }
            for name, info in latest_snap.items()
        }
        changes, ref_1d, ref_3d = calc_owned_changes(
            pseudo_snapshot, history, latest or today_str)

        # Phase 2: Statcast pipeline
        enriched = []
        savant_2026 = None
        if candidates:
            result = run_statcast_pipeline(candidates, config)
            enriched, savant_2026 = result
            # Attach d1/d3 from history changes
            changes_by_norm = {
                _normalize(c["name"]): c for c in changes
            }
            for p in enriched:
                c = changes_by_norm.get(_normalize(p["name"]), {})
                p["d1"] = c.get("d1")
                p["d3"] = c.get("d3")
        else:
            print("  No candidates to evaluate", file=sys.stderr)

        # Phase 3: Build data for Claude
        data_summary = build_fa_watch_data(
            today_str, enriched, changes, ref_1d, ref_3d,
            config, savant_2026, history)

        if args.dry_run:
            print(data_summary)
            return

        # Phase 4: Claude analysis → Telegram + GitHub Issue
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

        save_github_issue(today_str, data_summary, advice)

        print("Sending to Telegram...", file=sys.stderr)
        ok = send_telegram(advice, env)
        print("Sent." if ok else "Failed.", file=sys.stderr)

    except Exception as e:
        print(f"FA Watch error: {e}", file=sys.stderr)
        try:
            send_telegram(f"FA Watch failed: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
