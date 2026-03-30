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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MLB_API = "https://statsapi.mlb.com/api/v1"
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")
WEEKLY_DATA_DIR = os.path.join(SCRIPT_DIR, "weekly-data")

# Yahoo stat_id → (display_name, lower_is_better)
YAHOO_STAT_MAP = {
    "7": ("R", False), "12": ("HR", False), "13": ("RBI", False),
    "16": ("SB", False), "18": ("BB", False), "3": ("AVG", False),
    "55": ("OPS", False), "50": ("IP", False), "28": ("W", False),
    "42": ("K", False), "26": ("ERA", True), "27": ("WHIP", True),
    "83": ("QS", False), "89": ("SV+H", False),
}

LOWER_IS_BETTER = {"ERA", "WHIP"}

CATEGORY_ORDER = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS",
                   "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]

# Single-point risk positions (only 1 eligible player on roster)
RISK_POSITIONS = ["C", "1B", "SS"]


# ── Config & Env ──


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        config = json.load(f)
    config["mlb_id_map"] = {}
    for p in config.get("batters", []) + config.get("pitchers", []):
        if p.get("mlb_id"):
            config["mlb_id_map"][p["name"]] = p["mlb_id"]
    return config


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


# ── API Helpers (match main.py patterns) ──


def yahoo_refresh_token(env):
    """Refresh Yahoo OAuth token. Returns access_token."""
    with open(YAHOO_TOKEN_FILE, encoding="utf-8") as f:
        tokens = json.load(f)
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": env["YAHOO_CLIENT_ID"],
        "client_secret": env["YAHOO_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        YAHOO_TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    tokens["access_token"] = result["access_token"]
    if "refresh_token" in result:
        tokens["refresh_token"] = result["refresh_token"]
    with open(YAHOO_TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    return result["access_token"]


def yahoo_api_get(path, access_token):
    """Yahoo Fantasy API GET request."""
    url = f"{YAHOO_API}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}format=json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


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

        time.sleep(0.5)

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


def fetch_league_standings(league_key, access_token):
    """Fetch league standings (W-L record and rank)."""
    data = yahoo_api_get(f"/league/{league_key}/standings", access_token)
    teams_node = data["fantasy_content"]["league"][1]["standings"][0]["teams"]

    standings = []
    for k, v in teams_node.items():
        if k == "count":
            continue
        team_info = v["team"][0]
        team_standings = v["team"][1].get("team_standings", {})

        name = "?"
        for item in team_info:
            if isinstance(item, dict) and "name" in item:
                name = item["name"]
                break

        record = team_standings.get("outcome_totals", {})
        standings.append({
            "team": name,
            "wins": int(record.get("wins", 0)),
            "losses": int(record.get("losses", 0)),
            "rank": int(team_standings.get("rank", 0)),
        })

    standings.sort(key=lambda x: x["rank"])
    return standings


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
    """Get this week's opponent name and team_key."""
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
            return pair[1]
        elif pair[1]["name"] == team_name:
            return pair[0]

    return None


def fetch_opponent_roster(team_key, access_token):
    """Fetch opponent's full roster. Returns {"batters": [...], "pitchers": [...]}."""
    roster_data = yahoo_api_get(f"/team/{team_key}/roster", access_token)
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

        if selected_pos in ("IL", "IL+"):
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


def fetch_sp_schedules(config, opp_roster, week_start, week_end):
    """Fetch SP probable pitcher schedules for both teams.

    Returns: (my_sp_schedule, opp_sp_schedule)
    """
    my_sps = {p["name"]: p["team"] for p in config.get("pitchers", [])
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


def compute_positional_coverage(config, week_start, week_end):
    """Check daily positional coverage, identify dead slots (C/1B/SS)."""
    batters = config.get("batters", [])
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


# ── JSON Assembly ──
# TODO: Task 4


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

    access_token = yahoo_refresh_token(env)

    # ── Review: last week's data ──
    prev_week = week_number - 1
    review_data = {}
    if prev_week >= 1:
        print(f"  Fetching week {prev_week} scoreboard (all teams)...", file=sys.stderr)
        my_matchup, all_teams = fetch_league_scoreboard(
            league_key, access_token, prev_week, team_name)

        print(f"  Computing category ranks...", file=sys.stderr)
        category_ranks = compute_category_ranks(all_teams, team_name)

        print(f"  Fetching standings...", file=sys.stderr)
        standings = fetch_league_standings(league_key, access_token)

        print(f"  Fetching daily report metadata...", file=sys.stderr)
        daily_reports = fetch_daily_reports_metadata(prev_week)

        review_data = {
            **(my_matchup or {}),
            "league_standings": standings,
            "league_category_ranks": category_ranks,
            "daily_reports": daily_reports,
        }
    else:
        print("  Week 1 — no previous week to review", file=sys.stderr)

    # ── Preview: this week's data ──
    print(f"  Fetching week {week_number} opponent...", file=sys.stderr)
    next_opp = fetch_next_opponent(league_key, access_token, week_number, team_name)

    preview_data = {}
    if next_opp:
        print(f"  Opponent: {next_opp['name']}", file=sys.stderr)

        print(f"  Fetching opponent roster...", file=sys.stderr)
        opp_roster = fetch_opponent_roster(next_opp["key"], access_token)

        print(f"  Fetching SP schedules ({week_start} ~ {week_end})...", file=sys.stderr)
        my_sp_sched, opp_sp_sched = fetch_sp_schedules(config, opp_roster, week_start, week_end)

        print(f"  Computing positional coverage...", file=sys.stderr)
        pos_coverage = compute_positional_coverage(config, week_start, week_end)

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

    # TODO: Task 4 — assemble + output
    output = {
        "week": week_number,
        "dates": [week_start.isoformat(), week_end.isoformat()],
        "generated": datetime.now(ET).isoformat(),
        "review": review_data,
        "preview": preview_data,
    }

    if args.dry_run:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))

    print("[Weekly Review] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
