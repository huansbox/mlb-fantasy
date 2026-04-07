"""Weekly Review — 週覆盤資料準備腳本

Usage:
    python weekly_review.py --prepare [--dry-run] [--date YYYY-MM-DD]

Cron: 每週一 TW 18:00 (UTC 10:00)，在 Weekly Scan 之前執行。
輸出: daily-advisor/weekly-data/week-{N}.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Shared helpers from yahoo_query.py (same pattern as weekly_scan.py / fa_watch.py)
from yahoo_query import (
    refresh_token, load_env, load_config, api_get as yahoo_api_get,
    send_telegram, YAHOO_STAT_MAP,
    pitcher_type,
)
from daily_advisor import (
    fetch_batter_gamelog, fetch_pitcher_gamelog,
    fetch_savant_statcast, fetch_savant_expected,
    fetch_savant_for_pitchers,
    pctile_tag,
)
from roster_stats import fetch_batter_full, fetch_pitcher_full

ET = ZoneInfo("America/New_York")
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MLB_API = "https://statsapi.mlb.com/api/v1"
WEEKLY_DATA_DIR = os.path.join(SCRIPT_DIR, "weekly-data")

LOWER_IS_BETTER = {"ERA", "WHIP"}

CATEGORY_ORDER = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS",
                   "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]

# Single-point risk positions (only 1 eligible player on roster)
# Single-slot positions with thin depth — if all eligible batters have off-day, it's a dead slot
RISK_POSITIONS = ["C", "1B", "SS"]


# ── API Helpers ──


def mlb_api_get(path):
    """MLB Stats API GET request."""
    url = f"{MLB_API}{path}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def get_fantasy_week(target_date, config):
    """Return (week_start, week_end, week_number) for the given date."""
    opening = date.fromisoformat(config["league"]["opening_day"])
    first_sunday = opening
    while first_sunday.weekday() != 6:
        first_sunday += timedelta(days=1)
    if target_date <= first_sunday:
        return opening, first_sunday, 1
    week_start = first_sunday + timedelta(days=1)
    week_num = 2
    while True:
        week_end = week_start + timedelta(days=6)
        if week_start <= target_date <= week_end:
            return week_start, week_end, week_num
        week_start = week_end + timedelta(days=1)
        week_num += 1


# ── Review Data Fetching ──


def fetch_league_scoreboard(league_key, access_token, week, team_name="99 940"):
    """Fetch scoreboard for all matchups in a given week.

    Returns:
        my_matchup: dict with categories, final_record, opponent_name (or None)
        all_teams: {team_name: {"R": val, ...}}
    """
    sb = yahoo_api_get(f"/league/{league_key}/scoreboard;week={week}", access_token)
    matchups = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    all_teams = {}
    my_matchup = None

    for k, v in matchups.items():
        if k == "count":
            continue

        teams_node = v["matchup"]["0"]["teams"]

        # Parse both teams in this matchup
        pair = []
        for ti in ("0", "1"):
            team_info = teams_node[ti]["team"][0]
            team_stats_raw = teams_node[ti]["team"][1]["team_stats"]["stats"]

            name = "?"
            for item in team_info:
                if isinstance(item, dict) and "name" in item:
                    name = item["name"]
                    break

            # Parse stats using YAHOO_STAT_MAP
            stats = {}
            for s in team_stats_raw:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid not in YAHOO_STAT_MAP:
                    continue
                cat_name, _ = YAHOO_STAT_MAP[sid]
                try:
                    stats[cat_name] = float(val)
                except (ValueError, TypeError):
                    stats[cat_name] = 0.0

            pair.append({"name": name, "stats": stats})
            all_teams[name] = stats

        # Check if my team is in this matchup
        my_idx = None
        if pair[0]["name"] == team_name:
            my_idx = 0
        elif pair[1]["name"] == team_name:
            my_idx = 1

        if my_idx is not None:
            me = pair[my_idx]
            opp = pair[1 - my_idx]

            categories = []
            wins = losses = draws = 0
            for cat in CATEGORY_ORDER:
                mv = me["stats"].get(cat, 0.0)
                ov = opp["stats"].get(cat, 0.0)
                if cat in LOWER_IS_BETTER:
                    result = "W" if mv < ov else ("L" if mv > ov else "D")
                else:
                    result = "W" if mv > ov else ("L" if mv < ov else "D")
                if result == "W":
                    wins += 1
                elif result == "L":
                    losses += 1
                else:
                    draws += 1
                categories.append({"name": cat, "mine": mv, "opp": ov, "result": result})

            my_matchup = {
                "opponent_name": opp["name"],
                "categories": categories,
                "final_record": {"wins": wins, "losses": losses, "draws": draws},
            }

    return my_matchup, all_teams


def compute_category_ranks(all_teams, team_name="99 940"):
    """Compute per-category rank for my team among all teams. 1 = best."""
    ranks = {}
    for cat in CATEGORY_ORDER:
        values = [(name, stats.get(cat, 0.0)) for name, stats in all_teams.items()]
        values.sort(key=lambda x: x[1], reverse=(cat not in LOWER_IS_BETTER))
        for rank_idx, (name, _) in enumerate(values, 1):
            if name == team_name:
                ranks[cat] = rank_idx
                break
    return ranks



def fetch_daily_reports_metadata(week_number):
    """Fetch GitHub Issue metadata for daily reports of a given week."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", "huansbox/mlb-fantasy",
             "--label", f"week-{week_number}",
             "--state", "all",
             "--json", "number,title,createdAt",
             "--limit", "20"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode != 0:
            print(f"  gh issue list failed: {result.stderr}", file=sys.stderr)
            return []

        issues = json.loads(result.stdout)
        reports = []
        for issue in issues:
            title = issue.get("title", "")
            # Extract date from title like "[速報] Daily Report 2026-03-30"
            date_str = ""
            for part in title.split():
                if len(part) == 10 and part[4:5] == "-" and part[7:8] == "-":
                    date_str = part
                    break
            reports.append({
                "date": date_str,
                "issue_number": issue["number"],
                "title": title,
            })
        reports.sort(key=lambda x: x["date"])
        return reports
    except Exception as e:
        print(f"  fetch_daily_reports error: {e}", file=sys.stderr)
        return []


# ── Preview Data Fetching ──


def fetch_next_opponent(league_key, access_token, week, team_name="99 940"):
    """Get this week's opponent and my team_key.

    Returns: (opponent_dict, my_team_key) or (None, None).
    """
    sb = yahoo_api_get(f"/league/{league_key}/scoreboard;week={week}", access_token)
    matchups = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for k, v in matchups.items():
        if k == "count":
            continue
        teams_node = v["matchup"]["0"]["teams"]

        pair = []
        for ti in ("0", "1"):
            info = teams_node[ti]["team"][0]
            name = key = ""
            for item in info:
                if isinstance(item, dict):
                    if "name" in item:
                        name = item["name"]
                    if "team_key" in item:
                        key = item["team_key"]
            pair.append({"name": name, "key": key})

        if pair[0]["name"] == team_name:
            return pair[1], pair[0]["key"]
        elif pair[1]["name"] == team_name:
            return pair[0], pair[1]["key"]

    return None, None


def _parse_roster_players(roster_data):
    """Parse Yahoo roster API response into batters/pitchers lists."""
    players = roster_data["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    batters = []
    pitchers = []
    for k, v in players.items():
        if k == "count":
            continue
        player = v["player"]
        info = player[0]
        pos_data = player[1]

        name = team_val = display_pos = ""
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full", "")
                if "editorial_team_abbr" in item:
                    team_val = item["editorial_team_abbr"].upper()
                if "display_position" in item:
                    display_pos = item["display_position"]

        selected_pos = "BN"
        sel = pos_data.get("selected_position", [{}])
        for s in sel:
            if isinstance(s, dict) and "position" in s:
                selected_pos = s["position"]

        if not name or not display_pos:
            continue

        if selected_pos in ("IL", "IL+", "NA"):
            role = "IL"
        elif selected_pos == "BN":
            role = "bench"
        else:
            role = "starter"

        positions = [p.strip() for p in display_pos.split(",")]

        if any(p in ("SP", "RP") for p in positions):
            p_type = "SP" if "SP" in positions else "RP"
            pitchers.append({"name": name, "team": team_val, "type": p_type, "role": role})
        else:
            batters.append({"name": name, "team": team_val, "positions": positions, "role": role})

    return {"batters": batters, "pitchers": pitchers}


def fetch_roster(team_key, access_token, date=None):
    """Fetch a team's roster. Supports date parameter for historical snapshots."""
    endpoint = f"/team/{team_key}/roster"
    if date:
        endpoint += f";date={date}"
    roster_data = yahoo_api_get(endpoint, access_token)
    return _parse_roster_players(roster_data)


def fetch_sp_schedules(my_roster, opp_roster, week_start, week_end):
    """Fetch SP probable pitcher schedules for both teams.

    Returns: (my_sp_schedule, opp_sp_schedule)
    """
    my_sps = {p["name"]: p["team"] for p in my_roster.get("pitchers", [])
              if p.get("type") == "SP" and p.get("role") != "IL"}
    opp_sps = {p["name"]: p["team"] for p in opp_roster.get("pitchers", [])
               if p.get("type") == "SP" and p.get("role") != "IL"}
    all_sp_names = set(my_sps.keys()) | set(opp_sps.keys())

    my_schedule = []
    opp_schedule = []

    d = week_start
    while d <= week_end:
        date_str = d.isoformat()
        try:
            data = mlb_api_get(f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher")
            for dd in data.get("dates", []):
                for g in dd["games"]:
                    for side in ("away", "home"):
                        sp_name = g["teams"][side].get("probablePitcher", {}).get("fullName", "")
                        if sp_name in all_sp_names:
                            opp_side = "home" if side == "away" else "away"
                            vs_team = g["teams"][opp_side]["team"]["name"]
                            entry = {
                                "date": date_str,
                                "pitcher": sp_name,
                                "team": my_sps.get(sp_name, opp_sps.get(sp_name, "")),
                                "vs": vs_team,
                                "confirmed": True,
                            }
                            if sp_name in my_sps:
                                my_schedule.append(entry)
                            else:
                                opp_schedule.append(entry)
        except Exception as e:
            print(f"  SP schedule error for {date_str}: {e}", file=sys.stderr)
        time.sleep(0.3)
        d += timedelta(days=1)

    my_schedule.sort(key=lambda x: x["date"])
    opp_schedule.sort(key=lambda x: x["date"])
    return my_schedule, opp_schedule


def compute_positional_coverage(my_roster, config, week_start, week_end):
    """Check daily positional coverage, identify dead slots (C/1B/SS).

    Uses Yahoo API roster (my_roster) for active batters, config for team ID map.
    """
    batters = [b for b in my_roster.get("batters", []) if b.get("role") != "IL"]
    team_id_map = config.get("teams", {})
    # Reverse map: mlb_team_id → config abbreviation
    id_to_abbr = {v: k for k, v in team_id_map.items()}

    coverage = {}
    d = week_start
    while d <= week_end:
        date_str = d.isoformat()
        try:
            data = mlb_api_get(f"/schedule?sportId=1&date={date_str}")
            teams_playing = set()
            for dd in data.get("dates", []):
                for g in dd["games"]:
                    for side in ("away", "home"):
                        tid = g["teams"][side]["team"].get("id")
                        if tid and tid in id_to_abbr:
                            teams_playing.add(id_to_abbr[tid])

            with_games = [b["name"] for b in batters if b["team"] in teams_playing]
            no_game = [b["name"] for b in batters if b["team"] not in teams_playing]

            dead_slots = []
            for pos in RISK_POSITIONS:
                has_eligible = any(
                    pos in b.get("positions", []) and b["team"] in teams_playing
                    for b in batters
                )
                if not has_eligible:
                    dead_slots.append(pos)

            coverage[date_str] = {
                "players_with_games": with_games,
                "players_no_game": no_game,
                "dead_slots": dead_slots,
            }
        except Exception as e:
            print(f"  Coverage error for {date_str}: {e}", file=sys.stderr)
            coverage[date_str] = {"players_with_games": [], "players_no_game": [], "dead_slots": []}

        time.sleep(0.3)
        d += timedelta(days=1)

    return coverage


# ── JSON Output & Git ──


def git_push(json_path, week_number, env=None):
    """Git add, commit, pull --rebase, and push the weekly data file."""
    rel_path = os.path.relpath(json_path, REPO_ROOT)

    # Step 1: commit (clean working tree so rebase can work)
    try:
        subprocess.run(["git", "add", rel_path], cwd=REPO_ROOT, check=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m", f"data: weekly review data for week {week_number}"],
            cwd=REPO_ROOT, check=True, timeout=10,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Git commit failed: {e}", file=sys.stderr)
        return

    # Step 2: pull --rebase to get on top of remote
    try:
        subprocess.run(["git", "pull", "--rebase", "origin", "master"],
                       cwd=REPO_ROOT, check=True, timeout=30)
    except subprocess.CalledProcessError:
        subprocess.run(["git", "rebase", "--abort"], cwd=REPO_ROOT,
                       capture_output=True, timeout=10)
        msg = "[weekly_review] git pull --rebase failed — skipping push. Needs manual fix."
        print(f"  {msg}", file=sys.stderr)
        if env:
            send_telegram(msg, env)
        return

    # Step 3: push (should be fast-forward after rebase)
    try:
        subprocess.run(["git", "push", "origin", "master"],
                       cwd=REPO_ROOT, check=True, timeout=30)
        print("  Git push succeeded", file=sys.stderr)
    except subprocess.CalledProcessError:
        msg = "[weekly_review] git push failed — resolve manually."
        print(f"  {msg}", file=sys.stderr)
        if env:
            send_telegram(msg, env)


# ── Roster Performance ──


def _aggregate_batter_weekly(gamelog, week_start, week_end):
    """Aggregate batter game log entries within a date range.

    Returns dict with PA, R, HR, RBI, SB, BB, AVG, OPS or None if no games.
    """
    start_str = week_start.isoformat()
    end_str = week_end.isoformat()
    games = [g for g in gamelog if start_str <= g["date"] <= end_str]
    if not games:
        return None

    pa = sum(g["pa"] for g in games)
    ab = sum(g["ab"] for g in games)
    h = sum(g["h"] for g in games)
    r = sum(g["r"] for g in games)
    hr = sum(g["hr"] for g in games)
    rbi = sum(g["rbi"] for g in games)
    sb = sum(g["sb"] for g in games)
    bb = sum(g["bb"] for g in games)
    doubles = sum(g["doubles"] for g in games)
    triples = sum(g["triples"] for g in games)
    hbp = sum(g["hbp"] for g in games)
    sf = sum(g["sf"] for g in games)

    avg = round(h / ab, 3) if ab > 0 else 0
    # OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    obp_denom = ab + bb + hbp + sf
    obp = (h + bb + hbp) / obp_denom if obp_denom > 0 else 0
    # SLG = TB / AB, TB = H + 2B + 2*3B + 3*HR
    tb = h + doubles + 2 * triples + 3 * hr
    slg = tb / ab if ab > 0 else 0
    ops = round(obp + slg, 3)

    return {
        "games": len(games),
        "pa": pa, "r": r, "hr": hr, "rbi": rbi,
        "sb": sb, "bb": bb, "avg": avg, "ops": ops,
    }


def _aggregate_pitcher_weekly(gamelog, week_start, week_end):
    """Aggregate pitcher game log entries within a date range.

    Returns dict with starts, IP, W, K, ERA, WHIP, QS or None if no games.
    """
    start_str = week_start.isoformat()
    end_str = week_end.isoformat()
    games = [g for g in gamelog if start_str <= g["date"] <= end_str]
    if not games:
        return None

    ip = sum(g["ip"] for g in games)
    er = sum(g["er"] for g in games)
    k = sum(g["k"] for g in games)
    w = sum(g["w"] for g in games)
    h = sum(g["h"] for g in games)
    bb = sum(g["bb"] for g in games)
    qs = sum(1 for g in games if g["ip"] >= 6.0 and g["er"] <= 3)

    era = round(er * 9 / ip, 2) if ip > 0 else 0
    whip = round((h + bb) / ip, 2) if ip > 0 else 0
    return {
        "starts": len(games),
        "ip": round(ip, 1), "w": w, "k": k, "qs": qs,
        "era": era, "whip": whip,
    }


def compute_roster_performance(config, prev_week_start, prev_week_end, season):
    """Compute per-player performance for the previous week + season-to-date.

    Returns dict: {"batters": [...], "pitchers": [...]}
    """
    batters_cfg = config.get("batters", [])
    pitchers_cfg = config.get("pitchers", [])

    # Collect all mlb_ids for batch Savant download
    batter_ids = [b["mlb_id"] for b in batters_cfg if b.get("mlb_id")]
    pitcher_ids = [p["mlb_id"] for p in pitchers_cfg
                   if p.get("mlb_id") and pitcher_type(p) == "SP"]

    # Savant batch download (4 CSVs total — 2 batter, 2 pitcher)
    print("  Fetching Savant CSV for roster...", file=sys.stderr)
    bat_sc = fetch_savant_statcast(season, batter_ids, player_type="batter")
    bat_ex = fetch_savant_expected(season, batter_ids, player_type="batter")
    pit_savant = fetch_savant_for_pitchers(pitcher_ids, season)

    # ── Batters ──
    batter_results = []
    for b in batters_cfg:
        mid = b.get("mlb_id")
        if not mid:
            continue

        print(f"    Batter: {b['name']}...", file=sys.stderr)
        # Weekly game log
        try:
            gamelog = fetch_batter_gamelog(mid, season)
        except Exception as e:
            print(f"      gamelog error: {e}", file=sys.stderr)
            gamelog = []
        weekly = _aggregate_batter_weekly(gamelog, prev_week_start, prev_week_end)

        # Season totals (MLB API)
        season_mlb = fetch_batter_full(mid, season)

        # Savant data
        sc = bat_sc.get(mid, {})
        ex = bat_ex.get(mid, {})
        xwoba = ex.get("xwoba")
        hh_pct = sc.get("hh_pct")
        barrel_pct = sc.get("barrel_pct")
        bbe = sc.get("bbe", 0)
        bb_pct = season_mlb.get("bb_pct") if season_mlb else None

        pctiles = {}
        if xwoba:
            pctiles["xwoba"] = pctile_tag(xwoba, "xwoba")
        if bb_pct is not None:
            pctiles["bb_pct"] = pctile_tag(bb_pct, "bb_pct")
        if barrel_pct:
            pctiles["barrel_pct"] = pctile_tag(barrel_pct, "barrel_pct")
        if hh_pct:
            pctiles["hh_pct"] = pctile_tag(hh_pct, "hh_pct")

        entry = {
            "name": b["name"],
            "team": b["team"],
            "positions": b.get("positions", []),
            "selected_pos": b.get("selected_pos", ""),
            "weekly": weekly,
            "season": {
                **(season_mlb or {}),
                "xwoba": xwoba,
                "hh_pct": hh_pct,
                "barrel_pct": barrel_pct,
                "bbe": bbe,
            },
            "pctiles": pctiles,
        }
        batter_results.append(entry)
        time.sleep(0.2)

    # ── SP only (CLAUDE.md: RP 只有 2 人不評估) ──
    pitcher_results = []
    for p in pitchers_cfg:
        mid = p.get("mlb_id")
        if not mid or pitcher_type(p) != "SP":
            continue

        print(f"    SP: {p['name']}...", file=sys.stderr)
        # Weekly game log
        try:
            gamelog = fetch_pitcher_gamelog(mid, season)
        except Exception as e:
            print(f"      gamelog error: {e}", file=sys.stderr)
            gamelog = []
        weekly = _aggregate_pitcher_weekly(gamelog, prev_week_start, prev_week_end)

        # Season totals (MLB API)
        season_mlb = fetch_pitcher_full(mid, season)

        # Savant data — fetch_savant_for_pitchers returns 0 (not None) as default,
        # so use `or None` to normalize falsy-zero to None for pctile guard
        sv = (pit_savant.get(mid) or {}).get("current") or {}
        xera = sv.get("xera") or None
        xwoba_a = sv.get("xwoba") or None
        hh_pct_a = sv.get("hh_pct") or None
        barrel_pct_a = sv.get("barrel_pct") or None
        bbe = sv.get("bbe", 0)

        pctiles = {}
        if xera is not None:
            pctiles["xera"] = pctile_tag(xera, "xera", "pitcher")
        if xwoba_a is not None:
            pctiles["xwoba_allowed"] = pctile_tag(xwoba_a, "xwoba", "pitcher")
        if hh_pct_a is not None:
            pctiles["hh_pct_allowed"] = pctile_tag(hh_pct_a, "hh_pct", "pitcher")

        entry = {
            "name": p["name"],
            "team": p["team"],
            "selected_pos": p.get("selected_pos", ""),
            "weekly": weekly,
            "season": {
                **(season_mlb or {}),
                "xera": xera,
                "xwoba_allowed": xwoba_a,
                "hh_pct_allowed": hh_pct_a,
                "barrel_pct_allowed": barrel_pct_a,
                "bbe": bbe,
            },
            "pctiles": pctiles,
        }
        pitcher_results.append(entry)
        time.sleep(0.2)

    return {"batters": batter_results, "pitchers": pitcher_results}


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Weekly Review Data Preparation")
    parser.add_argument("--prepare", action="store_true", help="Prepare weekly data JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout, skip file write and git push")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today in ET)")
    args = parser.parse_args()

    if not args.prepare:
        print("Usage: weekly_review.py --prepare [--dry-run] [--date YYYY-MM-DD]", file=sys.stderr)
        return

    config = load_config()
    env = load_env()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(ET).date()

    week_start, week_end, week_number = get_fantasy_week(target_date, config)
    league_key = config["league"]["league_key"]
    team_name = config["league"]["team_name"]

    print(f"[Weekly Review] Week {week_number} ({week_start} ~ {week_end})", file=sys.stderr)

    access_token = refresh_token(env)

    # ── Review: last week's data ──
    prev_week = week_number - 1
    review_data = {}
    if prev_week >= 1:
        print(f"  Fetching week {prev_week} scoreboard (all teams)...", file=sys.stderr)
        my_matchup, all_teams = fetch_league_scoreboard(
            league_key, access_token, prev_week, team_name)

        print(f"  Computing category ranks...", file=sys.stderr)
        category_ranks = compute_category_ranks(all_teams, team_name)

        print(f"  Fetching daily report metadata...", file=sys.stderr)
        daily_reports = fetch_daily_reports_metadata(prev_week)

        review_data = {
            **(my_matchup or {}),
            "league_category_ranks": category_ranks,
            "daily_reports": daily_reports,
        }
    else:
        print("  Week 1 — no previous week to review", file=sys.stderr)

    # ── Preview: this week's data ──
    print(f"  Fetching week {week_number} opponent...", file=sys.stderr)
    next_opp, my_team_key = fetch_next_opponent(league_key, access_token, week_number, team_name)

    preview_data = {}
    if next_opp:
        print(f"  Opponent: {next_opp['name']}", file=sys.stderr)

        roster_date = week_start.isoformat()
        print(f"  Fetching my roster (date={roster_date})...", file=sys.stderr)
        my_roster = fetch_roster(my_team_key, access_token, date=roster_date)

        print(f"  Fetching opponent roster (date={roster_date})...", file=sys.stderr)
        opp_roster = fetch_roster(next_opp["key"], access_token, date=roster_date)

        print(f"  Fetching SP schedules ({week_start} ~ {week_end})...", file=sys.stderr)
        my_sp_sched, opp_sp_sched = fetch_sp_schedules(my_roster, opp_roster, week_start, week_end)

        print(f"  Computing positional coverage...", file=sys.stderr)
        pos_coverage = compute_positional_coverage(my_roster, config, week_start, week_end)

        preview_data = {
            "opponent_name": next_opp["name"],
            "opponent_key": next_opp["key"],
            "opponent_roster": opp_roster,
            "my_sp_schedule": my_sp_sched,
            "opp_sp_schedule": opp_sp_sched,
            "probable_as_of": datetime.now(ET).isoformat(),
            "positional_coverage": pos_coverage,
            "predicted_outcome": None,
        }
    else:
        print("  Could not determine this week's opponent", file=sys.stderr)

    # ── Assemble & output ──
    output = {
        "week": week_number,
        "dates": [week_start.isoformat(), week_end.isoformat()],
        "generated": datetime.now(ET).isoformat(),
        "review": review_data,
        "preview": preview_data,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False, default=str)

    if args.dry_run:
        print(json_str)
        print("[Weekly Review] Done (dry-run).", file=sys.stderr)
        return

    os.makedirs(WEEKLY_DATA_DIR, exist_ok=True)
    json_path = os.path.join(WEEKLY_DATA_DIR, f"week-{week_number}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"  Written to {json_path}", file=sys.stderr)

    git_push(json_path, week_number, env=env)
    print("[Weekly Review] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
