"""Daily Advisor — Fantasy Baseball 每日陣容建議產生器"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MLB_API = "https://statsapi.mlb.com/api/v1"
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

# Yahoo stat_id (str) → (display_name, lower_is_better)
YAHOO_STAT_MAP = {
    "7": ("R", False),
    "12": ("HR", False),
    "13": ("RBI", False),
    "16": ("SB", False),
    "18": ("BB", False),
    "3": ("AVG", False),
    "55": ("OPS", False),
    "50": ("IP", False),
    "28": ("W", False),
    "42": ("K", False),
    "26": ("ERA", True),
    "27": ("WHIP", True),
    "83": ("QS", False),
    "89": ("SV+H", False),
}


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        config = json.load(f)
    # Build name → mlb_id lookup from config
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
    # os.environ overrides .env (op run injects real values over op:// references)
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def load_prompt_template():
    with open(os.path.join(SCRIPT_DIR, "prompt_template.txt"), encoding="utf-8") as f:
        return f.read()


def api_get(path):
    url = f"{MLB_API}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"API error: {url} — {e}", file=sys.stderr)
        raise


def parse_ip(val):
    """Convert baseball IP notation (6.1 = 6⅓, 6.2 = 6⅔) to decimal."""
    s = str(val)
    if "." in s:
        whole, frac = s.split(".", 1)
        return int(whole) + int(frac) / 3
    return float(s)


# ── MLB team full name → abbreviation mapping ──

_team_abbr_cache = {}


def build_team_abbr_map(season):
    if _team_abbr_cache:
        return _team_abbr_cache
    data = api_get(f"/teams?sportId=1&season={season}")
    for t in data["teams"]:
        _team_abbr_cache[t["name"]] = t["abbreviation"]
        _team_abbr_cache[t["abbreviation"]] = t["abbreviation"]
        _team_abbr_cache[str(t["id"])] = t["abbreviation"]
    return _team_abbr_cache


def team_abbr(name_or_id, season=2026):
    m = build_team_abbr_map(season)
    return m.get(str(name_or_id), str(name_or_id))


# ── Data fetching ──


def fetch_schedule(date_str):
    """Fetch games + probable pitchers for a date (YYYY-MM-DD)."""
    data = api_get(f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher")
    games = []
    for d in data.get("dates", []):
        for g in d["games"]:
            away = g["teams"]["away"]
            home = g["teams"]["home"]
            games.append({
                "away_team": away["team"]["name"],
                "home_team": home["team"]["name"],
                "away_pitcher": away.get("probablePitcher", {}).get("fullName"),
                "home_pitcher": home.get("probablePitcher", {}).get("fullName"),
                "away_pitcher_id": away.get("probablePitcher", {}).get("id"),
                "home_pitcher_id": home.get("probablePitcher", {}).get("id"),
                "game_time": g.get("gameDate", ""),
            })
    return games


def fetch_pitcher_gamelog(player_id, season):
    """Fetch pitching game log for the season."""
    data = api_get(
        f"/people/{player_id}/stats?stats=gameLog&season={season}&group=pitching"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    return [
        {
            "date": s["date"],
            "opponent": s.get("opponent", {}).get("name", "?"),
            "ip": parse_ip(s["stat"].get("inningsPitched", 0)),
            "er": int(s["stat"].get("earnedRuns", 0)),
            "k": int(s["stat"].get("strikeOuts", 0)),
        }
        for s in splits
    ]


def fetch_lineups(date_str, season):
    """Fetch actual batting lineups for all games on a date.

    Returns dict: team_abbr → list of {name, id, position, batting_order}
    """
    data = api_get(
        f"/schedule?sportId=1&date={date_str}&hydrate=lineups,probablePitcher"
    )
    team_lineups = {}
    for d in data.get("dates", []):
        for g in d["games"]:
            lineups = g.get("lineups", {})
            for side, team_key in [
                ("homePlayers", "home"),
                ("awayPlayers", "away"),
            ]:
                players = lineups.get(side, [])
                if not players:
                    continue
                t = team_abbr(g["teams"][team_key]["team"]["name"], season)
                team_lineups[t] = [
                    {
                        "name": p["fullName"],
                        "id": p["id"],
                        "position": p.get("primaryPosition", {}).get(
                            "abbreviation", "?"
                        ),
                        "batting_order": i + 1,
                    }
                    for i, p in enumerate(players)
                ]
    return team_lineups


def fetch_team_hitting(team_id, season):
    """Fetch team season hitting stats."""
    data = api_get(
        f"/teams/{team_id}/stats?stats=season&season={season}&group=hitting"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    if not splits:
        return None
    s = splits[0]["stat"]
    return {
        "avg": s.get("avg", "—"),
        "obp": s.get("obp", "—"),
        "ops": s.get("ops", "—"),
        "hr": s.get("homeRuns", "—"),
    }


# ── Yahoo Fantasy API ──


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

    # Preserve old refresh_token if response doesn't include a new one
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


def fetch_yahoo_scoreboard(config, env):
    """Fetch current week H2H scoreboard. Returns dict or None on failure."""
    if not os.path.exists(YAHOO_TOKEN_FILE):
        return None

    league_key = config["league"].get("league_key")
    team_name = config["league"].get("team_name")
    if not league_key:
        return None

    access_token = yahoo_refresh_token(env)

    # Fetch scoreboard
    sb = yahoo_api_get(f"/league/{league_key}/scoreboard", access_token)
    matchups = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for k, v in matchups.items():
        if k == "count":
            continue

        teams = v["matchup"]["0"]["teams"]
        t0_info = teams["0"]["team"][0]
        t1_info = teams["1"]["team"][0]

        # Extract team names, keys, and find which is mine
        n0 = n1 = "?"
        k0 = k1 = None
        my_idx = None
        for item in t0_info:
            if isinstance(item, dict):
                if "name" in item:
                    n0 = item["name"]
                if "team_key" in item:
                    k0 = item["team_key"]
                if "is_owned_by_current_login" in item:
                    my_idx = 0
        for item in t1_info:
            if isinstance(item, dict):
                if "name" in item:
                    n1 = item["name"]
                if "team_key" in item:
                    k1 = item["team_key"]
                if "is_owned_by_current_login" in item:
                    my_idx = 1

        # Fallback: match by team_name from config
        if my_idx is None:
            if n0 == team_name:
                my_idx = 0
            elif n1 == team_name:
                my_idx = 1
            else:
                continue

        opp_idx = 1 - my_idx
        my_name = n0 if my_idx == 0 else n1
        opp_name = n1 if my_idx == 0 else n0
        opp_key = k1 if my_idx == 0 else k0

        my_stats = teams[str(my_idx)]["team"][1]["team_stats"]["stats"]
        opp_stats = teams[str(opp_idx)]["team"][1]["team_stats"]["stats"]

        categories = []
        wins = losses = draws = 0

        for i in range(len(my_stats)):
            stat_id = my_stats[i]["stat"]["stat_id"]
            if stat_id not in YAHOO_STAT_MAP:
                continue  # skip display-only stats like H/AB
            cat_name, lower_is_better = YAHOO_STAT_MAP[stat_id]
            my_val = my_stats[i]["stat"]["value"]
            opp_val = opp_stats[i]["stat"]["value"]

            try:
                fm, fo = float(my_val), float(opp_val)
                if lower_is_better:
                    result = "W" if fm < fo else ("L" if fm > fo else "D")
                else:
                    result = "W" if fm > fo else ("L" if fm < fo else "D")
            except (ValueError, TypeError):
                result = "D"

            if result == "W":
                wins += 1
            elif result == "L":
                losses += 1
            else:
                draws += 1

            categories.append({
                "name": cat_name,
                "mine": my_val,
                "opp": opp_val,
                "result": result,
            })

        return {
            "my_team": my_name,
            "opponent": opp_name,
            "opponent_key": opp_key,
            "categories": categories,
            "wins": wins,
            "losses": losses,
            "draws": draws,
        }

    return None


def fetch_yahoo_roster(team_key, access_token, mlb_id_map):
    """Fetch roster from Yahoo API, return batters and pitchers lists."""
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

        name = team_val = display_pos = None
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full")
                if "editorial_team_abbr" in item:
                    team_val = item["editorial_team_abbr"].upper()
                if "display_position" in item:
                    display_pos = item["display_position"]

        # Get selected position (where they're slotted)
        selected_pos = "BN"
        sel = pos_data.get("selected_position", [{}])
        for s in sel:
            if isinstance(s, dict) and "position" in s:
                selected_pos = s["position"]

        if not name or not display_pos:
            continue

        # Determine role from selected position
        if selected_pos == "IL" or selected_pos == "IL+":
            role = "IL"
        elif selected_pos == "BN":
            role = "bench"
        else:
            role = "starter"

        positions = [p.strip() for p in display_pos.split(",")]
        mlb_id = mlb_id_map.get(name)

        if any(p in ("SP", "RP") for p in positions):
            p_type = "SP" if "SP" in positions else "RP"
            pitchers.append({
                "name": name, "mlb_id": mlb_id, "team": team_val,
                "type": p_type, "role": role, "selected_pos": selected_pos,
            })
        else:
            batters.append({
                "name": name, "mlb_id": mlb_id, "team": team_val,
                "positions": positions, "role": role, "selected_pos": selected_pos,
            })

    return batters, pitchers


def fetch_opponent_sp_schedule(opp_key, access_token, target_date, week_end):
    """Fetch opponent's SP roster and cross-reference with MLB schedule for remaining days."""
    # Get opponent roster
    roster_data = yahoo_api_get(f"/team/{opp_key}/roster", access_token)
    players = roster_data["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    # Extract opponent's SP names and MLB teams
    opp_sps = []
    for k, v in players.items():
        if k == "count":
            continue
        player = v["player"]
        info = player[0]
        name = None
        mlb_team = None
        position = None
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full")
                if "editorial_team_abbr" in item:
                    mlb_team = item["editorial_team_abbr"].upper()
                if "display_position" in item:
                    position = item["display_position"]
        # Only include SPs (not RP)
        if position and "SP" in position and name:
            opp_sps.append({"name": name, "team": mlb_team})

    if not opp_sps:
        return []

    # Check MLB schedule for each remaining day this week
    opp_sp_names = {sp["name"] for sp in opp_sps}
    opp_sp_teams = {sp["team"] for sp in opp_sps}
    schedule_entries = []

    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    current = target_date
    while current <= week_end:
        date_str = current.strftime("%Y-%m-%d")
        wd = weekday_en[current.weekday()]
        try:
            games = fetch_schedule(date_str)
        except Exception:
            current += timedelta(days=1)
            continue
        day_starts = []
        for g in games:
            for pk in ("away_pitcher", "home_pitcher"):
                pitcher = g.get(pk)
                if pitcher and pitcher in opp_sp_names:
                    day_starts.append(pitcher)
        if day_starts:
            schedule_entries.append(f"  {date_str} ({wd}): {', '.join(day_starts)}")
        current += timedelta(days=1)

    return schedule_entries


# ── Analysis logic ──


def get_fantasy_week(target_date, config):
    """Return (week_start, week_end, week_number) for the fantasy week containing target_date.

    Week 1 starts on opening_day and ends on the first Sunday.
    Week 2+ are Monday-Sunday.
    """
    opening_day = datetime.strptime(config["league"]["opening_day"], "%Y-%m-%d").date()
    # First Sunday after opening day
    first_sunday = opening_day + timedelta(days=(6 - opening_day.weekday()))
    if target_date <= first_sunday:
        return opening_day, first_sunday, 1
    # Week 2+: Monday-Sunday
    days_since_monday = target_date.weekday()  # 0=Mon
    monday = target_date - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    week_number = 2 + (monday - (first_sunday + timedelta(days=1))).days // 7
    return monday, sunday, week_number


def calc_weekly_ip(config, target_date, pitchers_list=None):
    """Calculate total IP for the fantasy week containing target_date."""
    week_start, week_end, _ = get_fantasy_week(target_date, config)
    season = config["league"]["season"]
    src = pitchers_list if pitchers_list else config["pitchers"]
    active_pitchers = [p for p in src if p["role"] != "IL"]

    entries = []
    total_ip = 0.0
    for p in active_pitchers:
        try:
            logs = fetch_pitcher_gamelog(p["mlb_id"], season)
        except Exception:
            continue
        for log in logs:
            log_date = datetime.strptime(log["date"], "%Y-%m-%d").date()
            if week_start <= log_date <= week_end:
                total_ip += log["ip"]
                entries.append(
                    f"  {p['name']}: {log['ip']:.1f} IP ({log['date']} vs {team_abbr(log['opponent'])})"
                )
    return total_ip, entries


def analyze(config, target_date, env=None, morning=False):
    """Build the full data summary for claude -p."""
    season = config["league"]["season"]
    date_str = target_date.strftime("%Y-%m-%d")
    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday = weekday_en[target_date.weekday()]

    # Fetch live roster from Yahoo if available, fallback to config
    batters = config["batters"]
    pitchers = config["pitchers"]
    if env and env.get("YAHOO_CLIENT_ID") and os.path.exists(YAHOO_TOKEN_FILE):
        try:
            access_token = yahoo_refresh_token(env)
            league_key = config["league"]["league_key"]
            # Find my team key
            teams_data = yahoo_api_get(f"/league/{league_key}/teams", access_token)
            teams_list = teams_data["fantasy_content"]["league"][1]["teams"]
            my_key = None
            for k, v in teams_list.items():
                if k == "count":
                    continue
                for item in v["team"][0]:
                    if isinstance(item, dict) and "is_owned_by_current_login" in item:
                        for it in v["team"][0]:
                            if isinstance(it, dict) and "team_key" in it:
                                my_key = it["team_key"]
                        break
            if my_key:
                batters, pitchers = fetch_yahoo_roster(
                    my_key, access_token, config["mlb_id_map"]
                )
                print("Using live Yahoo roster.", file=sys.stderr)
        except Exception as e:
            print(f"Yahoo roster fetch failed, using config: {e}", file=sys.stderr)

    games = fetch_schedule(date_str)

    # Build set of teams playing
    teams_playing = set()
    # Map: team_abbr → opponent_team_abbr
    matchup_map = {}
    for g in games:
        a = team_abbr(g["away_team"], season)
        h = team_abbr(g["home_team"], season)
        teams_playing.add(a)
        teams_playing.add(h)
        matchup_map[a] = h
        matchup_map[h] = a

    # Identify my SP starts tomorrow
    my_sp_names = {p["name"]: p for p in pitchers if p["type"] == "SP"}
    sp_starts = []
    for g in games:
        for pitcher_key, side, opp_side in [
            ("away_pitcher", "away_team", "home_team"),
            ("home_pitcher", "home_team", "away_team"),
        ]:
            name = g.get(pitcher_key)
            if name and name in my_sp_names:
                opp = team_abbr(g[opp_side], season)
                sp_starts.append({"name": name, "opponent": opp, "info": my_sp_names[name]})

    # ── Section 1: Batters ──
    lines = [f"=== {date_str} ({weekday}) ===\n"]
    lines.append("我的打者：")
    for b in batters:
        pos = "/".join(b["positions"])
        slot = b.get("selected_pos", b["role"])
        tag = "板凳" if b["role"] == "bench" else slot
        if b["team"] in teams_playing:
            opp = matchup_map.get(b["team"], "?")
            lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → vs {opp}")
        else:
            lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → 休兵")

    # ── Section 2: SP starts ──
    lines.append("\n我的 SP 明日先發：")
    if sp_starts:
        for sp in sp_starts:
            opp_team_id = config["teams"].get(sp["opponent"])
            hitting = fetch_team_hitting(opp_team_id, season) if opp_team_id else None
            if hitting:
                lines.append(
                    f"  {sp['name']} ({sp['info']['team']}) vs {sp['opponent']}"
                    f" — 對手打線 AVG {hitting['avg']} / OPS {hitting['ops']}"
                )
            else:
                lines.append(f"  {sp['name']} ({sp['info']['team']}) vs {sp['opponent']}")
    else:
        lines.append("  (無)")

    # ── Section 3: Pitcher-batter conflicts ──
    lines.append("\n投打衝突：")
    conflicts = []
    for sp in sp_starts:
        for b in batters:
            if b["team"] == sp["opponent"]:
                conflicts.append(
                    f"  {sp['name']} 先發 vs {sp['opponent']}"
                    f" → 你的 {b['name']} ({'/'.join(b['positions'])}) 是對手打者"
                )
    if conflicts:
        lines.extend(conflicts)
    else:
        lines.append("  (無)")

    # ── Section 4: Weekly IP ──
    _, _, week_number = get_fantasy_week(target_date, config)
    min_ip = config["league"]["min_ip"]
    lines.append(f"\n本週 IP 進度（Week {week_number}）：")
    total_ip, ip_entries = calc_weekly_ip(config, target_date, pitchers)
    if ip_entries:
        lines.extend(ip_entries)
    if week_number == 1:
        lines.append(f"  合計: {total_ip:.1f} IP（Week 1 無最低局數限制）")
    else:
        lines.append(f"  合計: {total_ip:.1f} / {min_ip} IP")
        remaining = min_ip - total_ip
        if remaining > 0:
            lines.append(f"  還需: {remaining:.1f} IP")
        else:
            lines.append("  已達標")

    # ── Section 5: H2H Scoreboard ──
    sb = None
    if env:
        try:
            sb = fetch_yahoo_scoreboard(config, env)
            if sb:
                lines.append(f"\n=== 本週 H2H 對戰態勢 ===")
                lines.append(f"對手：{sb['opponent']}")
                lines.append(f"目前比分：{sb['wins']}W-{sb['losses']}L-{sb['draws']}D（需 8+ 贏）\n")
                lines.append(f"  {'類別':>6}  {'我方':>8}  {'對手':>8}  狀態")
                for cat in sb["categories"]:
                    if cat["result"] == "W":
                        tag = "✅ 贏"
                    elif cat["result"] == "L":
                        tag = "❌ 輸"
                    else:
                        tag = "➖ 平"
                    # Mark punt categories
                    if cat["name"] in ("SB", "SV+H"):
                        tag += "（punt）"
                    lines.append(f"  {cat['name']:>6}  {cat['mine']:>8}  {cat['opp']:>8}  {tag}")
        except Exception as e:
            print(f"Yahoo API error (skipping scoreboard): {e}", file=sys.stderr)

    # ── Section 6: My SP schedule (rest of week) ──
    _, week_end, _ = get_fantasy_week(target_date, config)
    schedule_cache = {date_str: games}
    lines.append("\n本週剩餘我方 SP 排程：")
    current = target_date
    while current <= week_end:
        cur_str = current.strftime("%Y-%m-%d")
        cur_wd = weekday_en[current.weekday()]
        try:
            cur_games = schedule_cache.get(cur_str) or fetch_schedule(cur_str)
            schedule_cache[cur_str] = cur_games
        except Exception:
            current += timedelta(days=1)
            continue
        day_starts = []
        for g in cur_games:
            for pk in ("away_pitcher", "home_pitcher"):
                if g.get(pk) in my_sp_names:
                    day_starts.append(g[pk])
        if day_starts:
            lines.append(f"  {cur_str} ({cur_wd}): {', '.join(day_starts)}")
        else:
            lines.append(f"  {cur_str} ({cur_wd}): (無)")
        current += timedelta(days=1)

    # ── Section 7: Opponent SP schedule (rest of week) ──
    if env and sb and sb.get("opponent_key"):
        try:
            access_token = yahoo_refresh_token(env)
            opp_entries = fetch_opponent_sp_schedule(
                sb["opponent_key"], access_token, target_date, week_end
            )
            lines.append(f"\n本週剩餘對手 SP 排程（{sb['opponent']}）：")
            if opp_entries:
                lines.extend(opp_entries)
            else:
                lines.append("  (無已確認先發)")
        except Exception as e:
            print(f"Opponent SP schedule error (skipping): {e}", file=sys.stderr)

    # ── Section 8: Lineup confirmation (morning mode only) ──
    if morning:
        try:
            team_lineups = fetch_lineups(date_str, season)
        except Exception as e:
            print(f"Lineup fetch error: {e}", file=sys.stderr)
            team_lineups = {}

        lines.append("\n=== 實際 Lineup 確認 ===")

        # Starters
        confirmed = []
        not_in_lineup = []
        lineup_unknown = []
        for b in batters:
            if b["role"] != "starter":
                continue
            if b["team"] not in teams_playing:
                continue  # off-day, already covered above
            lu = team_lineups.get(b["team"])
            if lu is None:
                lineup_unknown.append(f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → Lineup 未公布")
                continue
            match = next((p for p in lu if p["id"] == b.get("mlb_id")), None)
            if match:
                confirmed.append(
                    f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → 第 {match['batting_order']} 棒 ({match['position']})"
                )
            else:
                not_in_lineup.append(
                    f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → 不在先發名單 ⚠️"
                )

        if confirmed:
            lines.append("\n已確認先發：")
            lines.extend(confirmed)
        if not_in_lineup:
            lines.append("\n未進 Lineup：")
            lines.extend(not_in_lineup)
        if lineup_unknown:
            lines.append("\nLineup 未公布：")
            lines.extend(lineup_unknown)

        # Bench batters
        bench_lines = []
        for b in batters:
            if b["role"] != "bench":
                continue
            if b["team"] not in teams_playing:
                continue
            lu = team_lineups.get(b["team"])
            if lu is None:
                bench_lines.append(f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → Lineup 未公布")
                continue
            match = next((p for p in lu if p["id"] == b.get("mlb_id")), None)
            if match:
                bench_lines.append(
                    f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → 第 {match['batting_order']} 棒 ← 有先發"
                )
            else:
                bench_lines.append(
                    f"  {b['name']} ({'/'.join(b['positions'])}, {b['team']}) → 不在先發名單"
                )
        if bench_lines:
            lines.append("\n板凳球員 Lineup 狀態：")
            lines.extend(bench_lines)

    return "\n".join(lines)


def call_claude(data_summary, morning=False):
    """Call claude -p with the data summary and prompt template."""
    if morning:
        tmpl_path = os.path.join(SCRIPT_DIR, "prompt_template_morning.txt")
        with open(tmpl_path, encoding="utf-8") as f:
            prompt = f.read()
    else:
        prompt = load_prompt_template()
    full_prompt = f"{prompt}\n\n---\n以下是今日數據：\n\n{data_summary}"

    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        print(f"claude -p error: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip()


def send_telegram(message, env):
    """Send message via Telegram Bot API."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing in .env", file=sys.stderr)
        return False

    MAX_LEN = 4096
    if len(message) > MAX_LEN:
        message = message[:MAX_LEN - 20] + "\n\n(訊息截斷)"

    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Fantasy Baseball Daily Advisor")
    parser.add_argument("--dry-run", action="store_true", help="Only fetch data and print summary, skip claude and telegram")
    parser.add_argument("--no-send", action="store_true", help="Run claude but don't send to Telegram")
    parser.add_argument("--morning", action="store_true", help="Morning mode: include lineup data, use morning prompt")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today in ET)")
    args = parser.parse_args()

    config = load_config()
    env = load_env()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(ET).date()

    mode_label = "最終報" if args.morning else "速報"
    print(f"[{mode_label}] Fetching data for {target_date}...", file=sys.stderr)
    data_summary = analyze(config, target_date, env, morning=args.morning)

    if args.dry_run:
        print(data_summary)
        return

    print("Calling claude -p...", file=sys.stderr)
    advice = call_claude(data_summary, morning=args.morning)
    if not advice:
        print("Claude returned no output.", file=sys.stderr)
        print("\n--- Raw data summary ---")
        print(data_summary)
        return

    print(advice)

    # Archive to GitHub Issue
    _, _, week_number = get_fantasy_week(target_date, config)
    save_github_issue(target_date, week_number, data_summary, advice, morning=args.morning)

    if args.no_send:
        return

    print("\nSending to Telegram...", file=sys.stderr)
    ok = send_telegram(advice, env)
    if ok:
        print("Sent.", file=sys.stderr)
    else:
        print("Failed to send.", file=sys.stderr)


def save_github_issue(target_date, week_number, data_summary, advice, morning=False):
    """Save daily report as a GitHub Issue for future review."""
    repo = "huansbox/mlb-fantasy"
    tag = "最終報" if morning else "速報"
    title = f"[{tag}] Daily Report — {target_date}"
    body = f"""## Claude Advice

{advice}

---

<details>
<summary>Raw Data Summary</summary>

```
{data_summary}
```

</details>
"""
    try:
        result = subprocess.run(
            ["gh", "issue", "create",
             "--repo", repo,
             "--title", title,
             "--body", body,
             "--label", f"week-{week_number}"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode == 0:
            print(f"Issue created: {result.stdout.strip()}", file=sys.stderr)
        else:
            print(f"GitHub Issue error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"GitHub Issue failed (non-blocking): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
