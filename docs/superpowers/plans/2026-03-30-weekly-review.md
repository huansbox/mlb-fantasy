# Weekly Review System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly review system with automated data preparation (cron) and interactive retrospective + prediction (skill).

**Architecture:** `weekly_review.py --prepare` runs on VPS cron Monday TW 18:00, fetches Yahoo/MLB data, writes `weekly-data/week-{N}.json` and git pushes. `/weekly-review` skill reads the JSON interactively for Phase 1 (retrospective) and Phase 2 (prediction).

**Tech Stack:** Python 3.12, Yahoo Fantasy API, MLB Stats API, GitHub CLI (`gh`), git

**Spec:** `docs/superpowers/specs/2026-03-30-weekly-review-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `daily-advisor/weekly_review.py` | Create | Data preparation script (cron) |
| `.claude/commands/weekly-review.md` | Create | Interactive skill definition |
| `daily-advisor/weekly-data/` | Create dir | Week JSON storage |
| `week-reviews.md` | Create | Cumulative review log |
| `daily-advisor/weekly_scan.py` | Modify | Append reminder line |
| `/etc/cron.d/daily-advisor` (VPS) | Modify | Add cron entry |
| `CLAUDE.md` | Modify | Add file references |
| `README.md` | Modify | Add schedule entry |

---

### Task 1: Scaffold `weekly_review.py` with helpers and CLI

**Files:**
- Create: `daily-advisor/weekly_review.py`
- Read: `daily-advisor/main.py` (reuse patterns)

- [ ] **Step 1: Create script with imports, constants, and shared helpers**

```python
"""Weekly Review — 週覆盤資料準備腳本"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MLB_API = "https://statsapi.mlb.com/api/v1"
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")
WEEKLY_DATA_DIR = os.path.join(SCRIPT_DIR, "weekly-data")

YAHOO_STAT_MAP = {
    "7": ("R", False), "12": ("HR", False), "13": ("RBI", False),
    "16": ("SB", False), "18": ("BB", False), "3": ("AVG", False),
    "55": ("OPS", False), "50": ("IP", False), "28": ("W", False),
    "42": ("K", False), "26": ("ERA", True), "27": ("WHIP", True),
    "83": ("QS", False), "89": ("SV+H", False),
}

# Categories where lower is better
LOWER_IS_BETTER = {"ERA", "WHIP"}


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
    return env


def get_yahoo_token(env):
    """Refresh Yahoo OAuth token, return access_token."""
    token_data = {}
    if os.path.exists(YAHOO_TOKEN_FILE):
        with open(YAHOO_TOKEN_FILE, encoding="utf-8") as f:
            token_data = json.load(f)

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print("No refresh_token found in yahoo_token.json", file=sys.stderr)
        return None

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": env.get("YAHOO_CLIENT_ID", ""),
        "client_secret": env.get("YAHOO_CLIENT_SECRET", ""),
    }).encode()
    req = urllib.request.Request(YAHOO_TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())

    token_data["access_token"] = result["access_token"]
    if "refresh_token" in result:
        token_data["refresh_token"] = result["refresh_token"]
    with open(YAHOO_TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f)

    return result["access_token"]


def yahoo_api_get(path, access_token):
    sep = "&" if "?" in path else "?"
    url = f"{YAHOO_API}{path}{sep}format=json"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def mlb_api_get(path):
    url = f"{MLB_API}{path}"
    resp = urllib.request.urlopen(url, timeout=15)
    return json.loads(resp.read())


def get_fantasy_week(target_date, config):
    """Return (week_start, week_end, week_number) for the given date."""
    opening = date.fromisoformat(config["league"]["opening_day"])
    # Week 1: opening_day to first Sunday
    first_sunday = opening
    while first_sunday.weekday() != 6:
        first_sunday += timedelta(days=1)

    if target_date <= first_sunday:
        return opening, first_sunday, 1

    # Week 2+: Monday to Sunday
    week_start = first_sunday + timedelta(days=1)
    week_num = 2
    while True:
        week_end = week_start + timedelta(days=6)
        if week_start <= target_date <= week_end:
            return week_start, week_end, week_num
        week_start = week_end + timedelta(days=1)
        week_num += 1


def main():
    parser = argparse.ArgumentParser(description="Weekly Review Data Preparation")
    parser.add_argument("--prepare", action="store_true", help="Prepare weekly data JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout, don't write file or git push")
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
    print(f"[Weekly Review] Preparing data for week {week_number} ({week_start} ~ {week_end})", file=sys.stderr)

    access_token = get_yahoo_token(env)
    if not access_token:
        print("Failed to get Yahoo token", file=sys.stderr)
        return

    league_key = config["league"]["league_key"]

    # TODO: Task 2 — fetch review data
    # TODO: Task 3 — fetch preview data
    # TODO: Task 4 — assemble JSON, write file, git push

    print("[Weekly Review] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `weekly-data/` directory**

```bash
mkdir -p daily-advisor/weekly-data
```

- [ ] **Step 3: Verify script runs**

```bash
cd daily-advisor
python weekly_review.py --prepare --dry-run
```

Expected: `[Weekly Review] Preparing data for week 1 (...) ` then `[Weekly Review] Done.`

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/weekly_review.py daily-advisor/weekly-data/
git commit -m "feat(weekly-review): scaffold script with helpers and CLI"
```

---

### Task 2: Implement review data fetching

**Files:**
- Modify: `daily-advisor/weekly_review.py`

Adds functions to fetch last week's scoreboard (all 12 teams), standings, category ranks, and daily report metadata.

- [ ] **Step 1: Add `fetch_league_scoreboard()` — all 12 teams' category stats for a given week**

```python
def fetch_league_scoreboard(league_key, access_token, week):
    """Fetch scoreboard for all matchups in a given week.

    Returns:
        my_matchup: {"opponent_name", "categories": [{"name","mine","opp","result"}], "wins", "losses", "draws"}
        all_teams: {team_name: {"R": val, "HR": val, ...}}
    """
    import time
    data = yahoo_api_get(f"/league/{league_key}/scoreboard;week={week}", access_token)

    scoreboard = data["fantasy_content"]["league"][1]["scoreboard"]
    matchups = scoreboard["0"]["matchups"]
    matchup_count = int(matchups["count"])

    my_team_name = None
    try:
        # Fetch my team name from config or API
        team_data = yahoo_api_get(f"/league/{league_key}/teams", access_token)
        teams_list = team_data["fantasy_content"]["league"][1]["teams"]
        team_count = int(teams_list["count"])
        for i in range(team_count):
            t = teams_list[str(i)]["team"][0]
            for item in t:
                if isinstance(item, dict) and "name" in item:
                    # Check if this is my team via config
                    pass
            # Find by team_key matching
            team_key_parts = [item for item in t if isinstance(item, dict) and "team_key" in item]
            name_parts = [item for item in t if isinstance(item, dict) and "name" in item]
            if name_parts:
                name = name_parts[0]["name"]
                if name == "99 940":
                    my_team_name = name
                    break
    except Exception:
        my_team_name = "99 940"  # fallback

    if not my_team_name:
        my_team_name = "99 940"

    all_teams = {}
    my_matchup = None

    for i in range(matchup_count):
        matchup = matchups[str(i)]["matchup"]
        teams_in_matchup = matchup.get("0", {}).get("teams", matchup.get("teams", {}))

        # Parse two teams in this matchup
        pair = []
        for ti in range(2):
            team_node = teams_in_matchup[str(ti)]["team"]
            # team_node[0] = team info list, team_node[1] = team_stats
            info = team_node[0]
            stats_node = team_node[1].get("team_stats", {}).get("stats", [])

            team_name = None
            for item in info:
                if isinstance(item, dict) and "name" in item:
                    team_name = item["name"]
                    break

            stats = {}
            for s in stats_node:
                stat = s.get("stat", s)
                sid = str(stat.get("stat_id", ""))
                val = stat.get("value", "0")
                if sid in YAHOO_STAT_MAP:
                    cat_name, _ = YAHOO_STAT_MAP[sid]
                    try:
                        stats[cat_name] = float(val) if "." in str(val) else int(val)
                    except (ValueError, TypeError):
                        stats[cat_name] = val

            pair.append({"name": team_name, "stats": stats})
            all_teams[team_name] = stats

        # Check if my team is in this matchup
        if pair[0]["name"] == my_team_name or pair[1]["name"] == my_team_name:
            if pair[0]["name"] == my_team_name:
                me, opp = pair[0], pair[1]
            else:
                me, opp = pair[1], pair[0]

            categories = []
            wins = losses = draws = 0
            for cat_name in ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS",
                             "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]:
                mv = me["stats"].get(cat_name, 0)
                ov = opp["stats"].get(cat_name, 0)
                if cat_name in LOWER_IS_BETTER:
                    result = "W" if mv < ov else ("L" if mv > ov else "D")
                else:
                    result = "W" if mv > ov else ("L" if mv < ov else "D")
                if result == "W":
                    wins += 1
                elif result == "L":
                    losses += 1
                else:
                    draws += 1
                categories.append({"name": cat_name, "mine": mv, "opp": ov, "result": result})

            my_matchup = {
                "opponent_name": opp["name"],
                "categories": categories,
                "final_record": {"wins": wins, "losses": losses, "draws": draws},
            }

        time.sleep(0.3)  # gentle rate limit

    return my_matchup, all_teams


def compute_category_ranks(all_teams, my_team_name="99 940"):
    """Compute per-category rank for my team among all 12 teams.

    Returns: {"R": 3, "HR": 1, ...} (1 = best)
    """
    ranks = {}
    categories = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS",
                   "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]

    for cat in categories:
        values = []
        for team_name, stats in all_teams.items():
            values.append((team_name, stats.get(cat, 0)))

        reverse = cat not in LOWER_IS_BETTER
        values.sort(key=lambda x: x[1], reverse=reverse)

        for rank_idx, (name, _) in enumerate(values, 1):
            if name == my_team_name:
                ranks[cat] = rank_idx
                break

    return ranks
```

- [ ] **Step 2: Add `fetch_league_standings()`**

```python
def fetch_league_standings(league_key, access_token):
    """Fetch league standings (W-L record and rank).

    Returns: [{"team": name, "wins": n, "losses": n, "rank": n}, ...]
    """
    data = yahoo_api_get(f"/league/{league_key}/standings", access_token)
    standings_node = data["fantasy_content"]["league"][1]["standings"][0]["teams"]
    team_count = int(standings_node["count"])

    standings = []
    for i in range(team_count):
        team_node = standings_node[str(i)]["team"]
        info = team_node[0]
        team_name = None
        for item in info:
            if isinstance(item, dict) and "name" in item:
                team_name = item["name"]
                break

        standings_data = team_node[1].get("team_standings", {})
        record = standings_data.get("outcome_totals", {})
        rank = standings_data.get("rank", 0)

        standings.append({
            "team": team_name,
            "wins": int(record.get("wins", 0)),
            "losses": int(record.get("losses", 0)),
            "rank": int(rank),
        })

    standings.sort(key=lambda x: x["rank"])
    return standings
```

- [ ] **Step 3: Add `fetch_daily_reports_metadata()`**

```python
def fetch_daily_reports_metadata(week_number):
    """Fetch GitHub Issue metadata for daily reports of a given week.

    Returns: [{"date": str, "issue_number": int, "title": str}, ...]
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", "huansbox/mlb-fantasy",
             "--label", f"week-{week_number}",
             "--state", "all",
             "--json", "number,title,createdAt",
             "--limit", "20"],
            capture_output=True, text=True, encoding="utf-8", timeout=30
        )
        if result.returncode != 0:
            print(f"gh issue list failed: {result.stderr}", file=sys.stderr)
            return []

        issues = json.loads(result.stdout)
        reports = []
        for issue in issues:
            # Extract date from title like "[速報] Daily Report 2026-03-30"
            title = issue.get("title", "")
            date_str = ""
            parts = title.split(" ")
            for p in parts:
                if len(p) == 10 and p[4] == "-" and p[7] == "-":
                    date_str = p
                    break
            reports.append({
                "date": date_str,
                "issue_number": issue["number"],
                "title": title,
            })
        reports.sort(key=lambda x: x["date"])
        return reports

    except Exception as e:
        print(f"fetch_daily_reports error: {e}", file=sys.stderr)
        return []
```

- [ ] **Step 4: Wire review functions into `main()`**

Add after `league_key = ...` in main():

```python
    # ── Review: last week's data ──
    prev_week = week_number - 1
    review_data = {}
    if prev_week >= 1:
        print(f"  Fetching week {prev_week} scoreboard...", file=sys.stderr)
        my_matchup, all_teams = fetch_league_scoreboard(league_key, access_token, prev_week)

        print(f"  Computing category ranks...", file=sys.stderr)
        category_ranks = compute_category_ranks(all_teams)

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
```

- [ ] **Step 5: Test with `--dry-run`**

```bash
python weekly_review.py --prepare --dry-run --date 2026-04-06
```

Expected: prints review data fetching progress to stderr. No file written.

- [ ] **Step 6: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly-review): add review data fetching (scoreboard, ranks, standings)"
```

---

### Task 3: Implement preview data fetching

**Files:**
- Modify: `daily-advisor/weekly_review.py`
- Read: `daily-advisor/main.py` (`fetch_yahoo_roster`, `fetch_schedule` patterns)

- [ ] **Step 1: Add `fetch_opponent_roster()`**

```python
def fetch_opponent_roster(opponent_key, access_token, config):
    """Fetch opponent's full roster.

    Returns: {"batters": [...], "pitchers": [...]}
    """
    data = yahoo_api_get(f"/team/{opponent_key}/roster", access_token)
    roster = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    player_count = int(roster["count"])

    batters = []
    pitchers = []
    season = config["league"]["season"]

    for i in range(player_count):
        player = roster[str(i)]["player"]
        info = player[0]

        name = ""
        team = ""
        positions = []
        selected_pos = ""
        status = ""

        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full", "")
                elif "editorial_team_abbr" in item:
                    team = item["editorial_team_abbr"].upper()
                elif "eligible_positions" in item:
                    for pos in item["eligible_positions"]:
                        p = pos.get("position", "")
                        if p and p not in ("Util", "BN", "IL", "IL+", "NA", "DL"):
                            positions.append(p)
                elif "selected_position" in item:
                    sp = item["selected_position"]
                    if isinstance(sp, list):
                        for s in sp:
                            if isinstance(s, dict) and "position" in s:
                                selected_pos = s["position"]
                    elif isinstance(sp, dict):
                        selected_pos = sp.get("position", "")
                elif "status" in item:
                    status = item["status"]
                elif "status_full" in item:
                    status = item.get("status", status)

        is_pitcher = selected_pos in ("SP", "RP", "P") or (not positions or positions == ["P"])
        role = "IL" if selected_pos in ("IL", "IL+", "DL", "DL+") else (
            "bench" if selected_pos == "BN" else "starter")

        if is_pitcher or "SP" in positions or "RP" in positions:
            sp_type = "SP" if "SP" in positions else "RP"
            pitchers.append({"name": name, "team": team, "type": sp_type, "role": role})
        else:
            batters.append({"name": name, "team": team, "positions": positions, "role": role})

    return {"batters": batters, "pitchers": pitchers}
```

- [ ] **Step 2: Add `fetch_sp_schedules()` — both my and opponent SP schedules for the week**

```python
def fetch_sp_schedules(config, opponent_roster, week_start, week_end):
    """Fetch SP probable pitcher schedules for both teams.

    Returns: (my_sp_schedule, opp_sp_schedule)
    Each: [{"date", "pitcher", "team", "vs", "confirmed"}]
    """
    import time

    my_sps = {p["name"]: p["team"] for p in config.get("pitchers", [])
              if p.get("type") == "SP" and p.get("role") != "IL"}
    opp_sps = {p["name"]: p["team"] for p in opponent_roster.get("pitchers", [])
               if p.get("type") == "SP" and p.get("role") != "IL"}

    all_sp_names = set(my_sps.keys()) | set(opp_sps.keys())

    my_schedule = []
    opp_schedule = []

    d = week_start
    while d <= week_end:
        date_str = d.isoformat()
        try:
            url = f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
            data = mlb_api_get(url)
            for dd in data.get("dates", []):
                for g in dd["games"]:
                    for side in ["away", "home"]:
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
            print(f"  Schedule fetch error for {date_str}: {e}", file=sys.stderr)
        time.sleep(0.3)
        d += timedelta(days=1)

    my_schedule.sort(key=lambda x: x["date"])
    opp_schedule.sort(key=lambda x: x["date"])
    return my_schedule, opp_schedule
```

- [ ] **Step 3: Add `compute_positional_coverage()` — dead slot detection**

```python
def compute_positional_coverage(config, week_start, week_end):
    """Check each day's positional coverage, identify dead slots.

    Returns: {"2026-04-06": {"players_with_games": [...], "players_no_game": [...], "dead_slots": [...]}, ...}
    """
    import time
    batters = config.get("batters", [])
    # Build team → players mapping
    team_players = {}
    for b in batters:
        team_players.setdefault(b["team"], []).append(b)

    # Single-point risk positions (only 1 eligible player on roster)
    RISK_POSITIONS = ["C", "1B", "SS"]

    coverage = {}
    d = week_start
    while d <= week_end:
        date_str = d.isoformat()
        try:
            data = mlb_api_get(f"/schedule?sportId=1&date={date_str}")
            teams_playing = set()
            for dd in data.get("dates", []):
                for g in dd["games"]:
                    for side in ["away", "home"]:
                        # Use team abbreviation lookup
                        team_name = g["teams"][side]["team"]["name"]
                        team_id = g["teams"][side]["team"].get("id")
                        # Map full name to config abbreviation
                        for abbr, tid in config.get("teams", {}).items():
                            if tid == team_id:
                                teams_playing.add(abbr)

            with_games = []
            no_game = []
            for b in batters:
                if b["team"] in teams_playing:
                    with_games.append(b["name"])
                else:
                    no_game.append(b["name"])

            # Check dead slots for risk positions
            dead_slots = []
            for pos in RISK_POSITIONS:
                has_eligible = False
                for b in batters:
                    if pos in b.get("positions", []) and b["team"] in teams_playing:
                        has_eligible = True
                        break
                if not has_eligible:
                    dead_slots.append(pos)

            coverage[date_str] = {
                "players_with_games": with_games,
                "players_no_game": no_game,
                "dead_slots": dead_slots,
            }
        except Exception as e:
            print(f"  Coverage check error for {date_str}: {e}", file=sys.stderr)
            coverage[date_str] = {"players_with_games": [], "players_no_game": [], "dead_slots": []}

        time.sleep(0.3)
        d += timedelta(days=1)

    return coverage
```

- [ ] **Step 4: Add `fetch_next_opponent()` — get this week's opponent from scoreboard**

```python
def fetch_next_opponent(league_key, access_token, week):
    """Fetch current week's opponent name and key.

    Returns: {"name": str, "key": str} or None
    """
    data = yahoo_api_get(f"/league/{league_key}/scoreboard;week={week}", access_token)
    scoreboard = data["fantasy_content"]["league"][1]["scoreboard"]
    matchups = scoreboard["0"]["matchups"]
    matchup_count = int(matchups["count"])

    for i in range(matchup_count):
        matchup = matchups[str(i)]["matchup"]
        teams_node = matchup.get("0", {}).get("teams", matchup.get("teams", {}))

        names_keys = []
        for ti in range(2):
            team_node = teams_node[str(ti)]["team"]
            info = team_node[0]
            name = key = ""
            for item in info:
                if isinstance(item, dict):
                    if "name" in item:
                        name = item["name"]
                    elif "team_key" in item:
                        key = item["team_key"]
            names_keys.append({"name": name, "key": key})

        if names_keys[0]["name"] == "99 940":
            return names_keys[1]
        elif names_keys[1]["name"] == "99 940":
            return names_keys[0]

    return None
```

- [ ] **Step 5: Wire preview functions into `main()`**

Add after review_data block in main():

```python
    # ── Preview: this week's data ──
    print(f"  Fetching week {week_number} opponent...", file=sys.stderr)
    next_opp = fetch_next_opponent(league_key, access_token, week_number)

    preview_data = {}
    if next_opp:
        print(f"  Opponent: {next_opp['name']}", file=sys.stderr)

        print(f"  Fetching opponent roster...", file=sys.stderr)
        opp_roster = fetch_opponent_roster(next_opp["key"], access_token, config)

        print(f"  Fetching SP schedules...", file=sys.stderr)
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
```

- [ ] **Step 6: Test with `--dry-run`**

```bash
python weekly_review.py --prepare --dry-run --date 2026-04-06
```

Expected: progress messages for all fetch steps.

- [ ] **Step 7: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly-review): add preview data fetching (opponent, SP schedule, coverage)"
```

---

### Task 4: JSON assembly, file write, and git push

**Files:**
- Modify: `daily-advisor/weekly_review.py`

- [ ] **Step 1: Add JSON assembly and output at end of `main()`**

Replace the TODO comments and add after preview_data block:

```python
    # ── Assemble JSON ──
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
        return

    # Write JSON file
    os.makedirs(WEEKLY_DATA_DIR, exist_ok=True)
    json_path = os.path.join(WEEKLY_DATA_DIR, f"week-{week_number}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"  Written to {json_path}", file=sys.stderr)

    # Git add + commit + push
    git_push(json_path, week_number)

    print("[Weekly Review] Done.", file=sys.stderr)
```

- [ ] **Step 2: Add `git_push()` helper**

```python
def git_push(json_path, week_number):
    """Git add, commit, and push the weekly data file."""
    repo_root = os.path.dirname(SCRIPT_DIR)
    rel_path = os.path.relpath(json_path, repo_root)

    try:
        subprocess.run(["git", "add", rel_path], cwd=repo_root, check=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m", f"data: weekly review data for week {week_number}"],
            cwd=repo_root, check=True, timeout=10
        )
    except subprocess.CalledProcessError as e:
        print(f"  Git commit failed: {e}", file=sys.stderr)
        return

    try:
        subprocess.run(["git", "pull", "--rebase", "origin", "master"],
                       cwd=repo_root, timeout=30)
    except Exception as e:
        print(f"  Git pull --rebase failed: {e}", file=sys.stderr)

    try:
        subprocess.run(["git", "push", "origin", "master"],
                       cwd=repo_root, check=True, timeout=30)
        print("  Git push succeeded", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"  Git push failed (resolve manually): {e}", file=sys.stderr)
```

- [ ] **Step 3: Full test with `--dry-run`**

```bash
python weekly_review.py --prepare --dry-run --date 2026-04-06
```

Expected: full JSON output to stdout with review + preview sections.

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly-review): add JSON assembly, file write, git push"
```

---

### Task 5: Create `/weekly-review` skill

**Files:**
- Create: `.claude/commands/weekly-review.md`

- [ ] **Step 1: Write the skill file**

```markdown
# Weekly Review — 週覆盤 + 週預測

每週一執行。Phase 1 覆盤上週，Phase 2 預測本週。

## Step 1：讀取資料

1. 用 Bash 確認當前 fantasy week：
   ```bash
   python -c "
   import sys; sys.path.insert(0,'daily-advisor')
   from weekly_review import load_config, get_fantasy_week
   from datetime import datetime
   from zoneinfo import ZoneInfo
   config = load_config()
   today = datetime.now(ZoneInfo('America/New_York')).date()
   ws, we, wn = get_fantasy_week(today, config)
   print(f'Current week: {wn} ({ws} ~ {we})')
   "
   ```
2. 讀 `daily-advisor/weekly-data/week-{N}.json`（本週資料，含 review + preview）
3. 讀 `week-reviews.md`（上週的 predicted_outcome，用於覆盤對照）

若 JSON 不存在，提示用戶在 VPS 跑 `python daily-advisor/weekly_review.py --prepare`，或本地跑 `python daily-advisor/weekly_review.py --prepare --dry-run` 即時拉取。

## Step 2（Phase 1）：覆盤上週

> 如果是 Week 1（無上週資料），跳過 Phase 1，直接進 Phase 2。

1. 從 JSON `review` 區塊讀取 14 類別 mine/opp/result
2. 從 `week-reviews.md` 讀取上週的 `predicted_outcome`（strong/toss_up/weak）
3. 顯示對照表：

   | 類別 | 預測 | 實際 | ✓/✗ | mine | opp |
   |------|------|------|------|------|-----|

4. 計算準確率
5. 顯示聯盟排名變動（league_category_ranks）
6. 掃描日報品質：
   - 用 `gh issue view {number}` 讀取 daily_reports 中的 issues
   - 統計速報→最終報推翻次數
   - 統計「Lineup 未公布」出現比例
7. **詢問用戶**：預測偏差的原因（逐項或整體）
8. 寫入 `week-reviews.md` 的覆盤區塊（格式見下方模板）

## Step 3（Phase 2）：預測本週

1. 從 JSON `preview` 區塊讀取：
   - 對手陣容（batters + pitchers）
   - 雙方 SP 排程
   - 守位覆蓋 + dead_slots
2. 顯示分析：
   - 對手打者/投手陣容摘要（位置、關鍵球員）
   - SP 排程對比表（我方 vs 對手，確認/推估標記）
   - 守位死格警告（哪天 C/1B/SS 沒人）
3. 產出 14 類別預測：
   - 結合上週覆盤的 insight（如有）
   - 分 strong / toss_up / weak
   - 整體預測比分 + 策略建議（攻擊/保守/正常）
4. **詢問用戶**：確認或修正策略
5. 將 predicted_outcome 寫回 JSON 的 `preview.predicted_outcome`：
   ```json
   {
     "strong": ["HR", "IP", ...],
     "toss_up": ["R", "W", ...],
     "weak": ["SB", "SV+H"],
     "projected_record": "10-4",
     "strategy": "正常打，保護比率"
   }
   ```
6. 寫入 `week-reviews.md` 的預測區塊
7. Commit JSON + week-reviews.md

## `week-reviews.md` 模板

```
## Week {N} vs {對手名}

### 預測（{日期} 產出）
| 類別 | 預測 | 信心 | 理由 |
|------|------|------|------|
| {cat} | W/L | 高/中/低 | {一句話} |
| ...

整體：{projected_record}，{strategy}

### 覆盤（{日期} 回顧）
| 類別 | 預測 | 實際 | ✓/✗ | 偏差原因 |
|------|------|------|------|---------|
| {cat} | W/L | W/L | ✓/✗ | {原因或空} |
| ...

準確率：{correct}/{total}（{pct}%）

### 日報品質
- 速報→最終報推翻：{N} 次（{類型}）
- Lineup 未公布比例：速報 {N}%、最終報 {N}%
- Prompt 調整建議：{建議或「無」}

### 學到什麼
- {insight}
```

## 輸出

- 更新 `week-reviews.md`（追加本週預測 + 上週覆盤）
- 更新 `daily-advisor/weekly-data/week-{N}.json`（寫入 predicted_outcome）
- Commit 兩個檔案
```

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/weekly-review.md
git commit -m "feat(weekly-review): add interactive skill definition"
```

---

### Task 6: Create initial `week-reviews.md`

**Files:**
- Create: `week-reviews.md`

- [ ] **Step 1: Create the file with header**

```markdown
# 週對戰覆盤
```

This is intentionally minimal — content is appended by the `/weekly-review` skill each week.

- [ ] **Step 2: Commit**

```bash
git add week-reviews.md
git commit -m "feat(weekly-review): create week-reviews.md"
```

---

### Task 7: Weekly Scan reminder + Cron + Docs

**Files:**
- Modify: `daily-advisor/weekly_scan.py`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `/etc/cron.d/daily-advisor` (VPS)

- [ ] **Step 1: Add reminder to `weekly_scan.py`**

Find the Telegram message construction in `weekly_scan.py` and append before sending:

```python
# After advice is generated, before send_telegram:
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weekly_review import load_config, get_fantasy_week
from datetime import datetime
from zoneinfo import ZoneInfo

config_wr = load_config()
today_et = datetime.now(ZoneInfo("America/New_York")).date()
_, _, wn = get_fantasy_week(today_et, config_wr)
advice += f"\n\n---\n📋 Week {wn} 覆盤資料已備好，開 session 跑 /weekly-review"
```

Exact insertion point depends on `weekly_scan.py`'s structure — find where `advice` is finalized before `send_telegram(advice, env)`.

- [ ] **Step 2: Update CLAUDE.md file table**

Add rows to the In-Season 管理 file table:

```markdown
| `daily-advisor/weekly_review.py` | 週覆盤資料準備（cron 週一 TW 18:00） | ✅ 完成 |
| `daily-advisor/weekly-data/` | 週覆盤 JSON 資料（week-N.json） | 🔄 自動產生 |
| `.claude/commands/weekly-review.md` | 週覆盤互動 SOP（`/weekly-review`） | ✅ 完成 |
| `week-reviews.md` | 累積式週覆盤記錄（預測 + 覆盤 + 學習） | 🔄 進行中 |
```

- [ ] **Step 3: Update README.md schedule**

Add to the Cron 排程 section:

```markdown
    - **Weekly Review** UTC 10:00 每週一（台灣 18:00）：覆盤資料準備
```

- [ ] **Step 4: Add VPS cron entry**

```bash
ssh root@<VPS_IP> "cat >> /etc/cron.d/daily-advisor << 'EOF'

# Weekly Review Data Prep — 台灣 18:00 每週一 = UTC 10:00 Monday
0 10 * * 1 root export \$(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=\$(op item get \"GitHub PAT - Claude Code\" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c \"cd /opt/mlb-fantasy && python3 daily-advisor/weekly_review.py --prepare >> /var/log/weekly-review.log 2>&1\"
EOF"
```

- [ ] **Step 5: Deploy code to VPS**

```bash
git push origin master
ssh root@<VPS_IP> 'cd /opt/mlb-fantasy && git pull'
```

- [ ] **Step 6: Commit docs changes**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add weekly review to file table and schedule"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Scaffold + helpers | `weekly_review.py` (create) |
| 2 | Review data fetching | `weekly_review.py` (modify) |
| 3 | Preview data fetching | `weekly_review.py` (modify) |
| 4 | JSON assembly + git push | `weekly_review.py` (modify) |
| 5 | Skill definition | `.claude/commands/weekly-review.md` (create) |
| 6 | Initial week-reviews.md | `week-reviews.md` (create) |
| 7 | Reminder + cron + docs | `weekly_scan.py`, `CLAUDE.md`, `README.md`, VPS cron |
