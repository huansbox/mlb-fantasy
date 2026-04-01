"""Yahoo Fantasy API query tool — FA player search, player lookup, and Savant stats."""

import argparse
import csv
import io
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

# Yahoo stat_id → display name (matches league's 14 scoring categories)
YAHOO_STAT_MAP = {
    "60": ("H/AB", None),
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


def refresh_token(env):
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


def api_get(path, access_token):
    url = f"{YAHOO_API}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}format=json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        return json.load(f)


def extract_player_info(player_data):
    """Extract player fields from Yahoo's nested player structure."""
    info = player_data[0]
    name = team = position = status = percent_owned = None
    player_key = None
    for item in info:
        if isinstance(item, dict):
            if "name" in item:
                name = item["name"].get("full")
            if "editorial_team_abbr" in item:
                team = item["editorial_team_abbr"].upper()
            if "display_position" in item:
                position = item["display_position"]
            if "status" in item:
                status = item["status"]
            if "player_key" in item:
                player_key = item["player_key"]
    # percent_owned and ownership may be at any index after 0
    ownership_type = waiver_date = None
    for idx in range(1, len(player_data)):
        po_data = player_data[idx]
        if isinstance(po_data, dict):
            if "percent_owned" in po_data:
                po_list = po_data["percent_owned"]
                if isinstance(po_list, list):
                    for po in po_list:
                        if isinstance(po, dict) and "value" in po:
                            percent_owned = po["value"]
                elif isinstance(po_list, dict):
                    percent_owned = po_list.get("value")
            if "ownership" in po_data:
                own = po_data["ownership"]
                ownership_type = own.get("ownership_type", "")
                waiver_date = own.get("waiver_date", "")
    return {
        "name": name or "?",
        "team": team or "?",
        "position": position or "?",
        "status": status or "",
        "percent_owned": percent_owned,
        "player_key": player_key,
        "ownership_type": ownership_type or "",
        "waiver_date": waiver_date or "",
    }


def parse_player_stats(player_data):
    """Extract stats from player data that includes /stats sub-resource."""
    stats = {}
    for idx in range(1, len(player_data)):
        ps = player_data[idx]
        if isinstance(ps, dict) and "player_stats" in ps:
            for s in ps["player_stats"].get("stats", []):
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid in YAHOO_STAT_MAP:
                    name, _ = YAHOO_STAT_MAP[sid]
                    stats[name] = val
            break
    return stats


def cmd_fa(args, access_token, config):
    """Query FA players."""
    league_key = config["league"]["league_key"]

    filters = [f"status={args.status}"]
    if args.position:
        filters.append(f"position={args.position}")
    filters.append(f"sort={args.sort}")
    if args.sort_type:
        filters.append(f"sort_type={args.sort_type}")
    filters.append(f"count={args.count}")
    if args.start:
        filters.append(f"start={args.start}")

    filter_str = ";".join(filters)
    path = f"/league/{league_key}/players;{filter_str};out=stats,percent_owned,ownership"

    data = api_get(path, access_token)
    league_data = data["fantasy_content"]["league"]
    if len(league_data) < 2 or "players" not in league_data[1]:
        print("查無結果")
        return
    players_data = league_data[1]["players"]

    players = []
    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        p["stats"] = parse_player_stats(v["player"])
        players.append(p)

    # Output
    pos_filter = args.position or "ALL"
    print(f"=== FA 查詢 (position={pos_filter}, sort={args.sort}, count={args.count}) ===\n")
    for i, p in enumerate(players, 1):
        po = f"{p['percent_owned']}%" if p["percent_owned"] else "—"
        st = p["status"] if p["status"] else ""
        waiver_tag = f"W {p['waiver_date']}" if p.get("waiver_date") else ""
        status_tag = f"{st} {waiver_tag}".strip()
        stats = p.get("stats", {})
        if "ERA" in stats:
            stat_str = f"ERA {stats.get('ERA', '—')} | WHIP {stats.get('WHIP', '—')} | K {stats.get('K', '—')} | IP {stats.get('IP', '—')}"
        elif "AVG" in stats:
            stat_str = f"AVG {stats.get('AVG', '—')} | OPS {stats.get('OPS', '—')} | HR {stats.get('HR', '—')} | BB {stats.get('BB', '—')}"
        else:
            stat_str = ""
        print(f"{i:3}  {p['name']:20}  {p['team']:5}  {p['position']:12}  {po:>7}  {stat_str}  {status_tag}")


def _search_players(search_name, league_key, access_token):
    """Search for players, with apostrophe fallback."""
    queries = [search_name]
    if "'" in search_name:
        queries.append(search_name.replace("'", ""))
        parts = search_name.replace("'", " ").split()
        if parts:
            queries.append(parts[-1])

    for q in queries:
        encoded = urllib.parse.quote(q)
        path = f"/league/{league_key}/players;search={encoded}"
        try:
            data = api_get(path, access_token)
        except Exception:
            continue
        league_data = data["fantasy_content"]["league"]
        if len(league_data) < 2 or "players" not in league_data[1]:
            continue
        players_data = league_data[1]["players"]
        if isinstance(players_data, list) or players_data.get("count", 0) == 0:
            continue
        return players_data
    return None


def cmd_player(args, access_token, config):
    """Look up a specific player with stats and percent_owned via two-step query."""
    league_key = config["league"]["league_key"]
    search_name = args.player
    players_data = _search_players(search_name, league_key, access_token)
    if players_data is None:
        print(f"找不到球員: {search_name}")
        return

    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        player_key = p.get("player_key")

        # Two-step: use player_key to get stats + percent_owned
        stats = {}
        percent_owned = None
        if player_key:
            try:
                sd = api_get(
                    f"/league/{league_key}/players;player_keys={player_key}/stats",
                    access_token,
                )
                sp = sd["fantasy_content"]["league"][1]["players"]["0"]["player"]
                stats = parse_player_stats(sp)
            except Exception:
                pass
            try:
                pd = api_get(
                    f"/league/{league_key}/players;player_keys={player_key}/percent_owned",
                    access_token,
                )
                pp = pd["fantasy_content"]["league"][1]["players"]["0"]["player"]
                for item in pp[1].get("percent_owned", []):
                    if isinstance(item, dict) and "value" in item:
                        percent_owned = item["value"]
            except Exception:
                pass

        po_str = f"{percent_owned}%" if percent_owned is not None else "—"
        print(f"=== {p['name']} ===")
        print(f"隊伍: {p['team']}")
        print(f"位置: {p['position']}")
        print(f"持有率: {po_str}")
        print(f"狀態: {p['status'] or '健康'}")
        if stats:
            print("--- 本季數據 ---")
            for name, val in stats.items():
                print(f"  {name}: {val}")
        print()


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


def _normalize(name):
    """Strip accents for fuzzy matching (Jesús → Jesus)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    ).lower()


def _fetch_savant_csv(url):
    """Fetch a Baseball Savant CSV leaderboard."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode("utf-8-sig")


def _match_player(rows, query):
    """Find a player in Savant CSV rows by fuzzy name match."""
    q = _normalize(query)
    q_parts = q.split()
    matches = []
    for row in rows:
        raw_name = row.get("\ufefflast_name, first_name") or row.get("last_name, first_name", "")
        if not raw_name:
            continue
        # CSV format: "LastName, FirstName"
        parts = [p.strip().strip('"') for p in raw_name.split(",")]
        if len(parts) < 2:
            continue
        last = _normalize(parts[0])
        first = _normalize(parts[1])
        full = f"{first} {last}"
        # Match: exact full name, or last name + first initial
        if q == full or q == f"{last} {first}":
            matches.append((row, 0))
        elif last in q_parts and first.startswith(q_parts[0][:3]):
            matches.append((row, 1))
        elif last in q_parts:
            matches.append((row, 2))
    matches.sort(key=lambda x: x[1])
    return matches[0][0] if matches else None


def _savant_lookup(query, year, player_type):
    """Fetch Savant data for a single player from CSV.

    Returns dict with found data, or None if player not found.
    """
    sc_url = (
        f"https://baseballsavant.mlb.com/leaderboard/statcast"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    ex_url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )

    hh_pct = barrel_pct = bbe = xwoba = xera = None

    try:
        sc_text = _fetch_savant_csv(sc_url)
        sc_rows = list(csv.DictReader(io.StringIO(sc_text)))
        sc_match = _match_player(sc_rows, query)
        if sc_match:
            hh_pct = float(sc_match.get("ev95percent", 0) or 0)
            barrel_pct = float(sc_match.get("brl_percent", 0) or 0)
            bbe = int(sc_match.get("attempts", 0) or 0)
    except Exception as e:
        print(f"  Statcast CSV error ({year}): {e}", file=sys.stderr)

    try:
        ex_text = _fetch_savant_csv(ex_url)
        ex_rows = list(csv.DictReader(io.StringIO(ex_text)))
        ex_match = _match_player(ex_rows, query)
        if ex_match:
            xwoba = float(ex_match.get("est_woba", 0) or 0)
            if bbe is None:
                bbe = int(ex_match.get("bip", 0) or 0)
            if player_type == "pitcher":
                raw = ex_match.get("xera")
                xera = float(raw) if raw else None
    except Exception as e:
        print(f"  Expected CSV error ({year}): {e}", file=sys.stderr)

    if hh_pct is None and xwoba is None:
        return None
    return {
        "hh_pct": hh_pct, "barrel_pct": barrel_pct,
        "bbe": bbe, "xwoba": xwoba, "xera": xera,
    }


def _print_savant_line(label, data, player_type):
    """Print one year's Savant data line."""
    parts = [f"{label}:"]
    if player_type == "pitcher" and data.get("xera") is not None:
        parts.append(f"xERA {data['xera']:.2f}")
    if data.get("xwoba"):
        tag = "xwOBA allowed" if player_type == "pitcher" else "xwOBA"
        parts.append(f"{tag} {data['xwoba']:.3f}")
    if data.get("hh_pct") is not None:
        tag = "HH% allowed" if player_type == "pitcher" else "HH%"
        parts.append(f"{tag} {data['hh_pct']:.1f}%")
    if data.get("barrel_pct") is not None:
        tag = "Barrel% allowed" if player_type == "pitcher" else "Barrel%"
        parts.append(f"{tag} {data['barrel_pct']:.1f}%")
    if data.get("bbe"):
        parts.append(f"BBE {data['bbe']}")
    print("  " + " | ".join(parts))


def cmd_savant(args):
    """Look up a player's Statcast data from Baseball Savant CSV.

    Tries batter first; if not found, falls back to pitcher.
    """
    query = args.player
    years = [int(args.year)] if args.year else [2026, 2025]

    print(f"=== {query} — Statcast ===\n")

    # Detect player type: try batter first, fallback to pitcher
    detected_type = None
    for player_type in ["batter", "pitcher"]:
        test = _savant_lookup(query, years[0], player_type)
        if test:
            detected_type = player_type
            break

    if not detected_type:
        print(f"  Player not found in batter or pitcher CSV for {years[0]}")
        print()
        return

    if detected_type == "pitcher":
        print(f"  (detected as pitcher)\n")

    for year in years:
        label = "本季" if year == 2026 else str(year)
        data = _savant_lookup(query, year, detected_type)
        if data:
            _print_savant_line(label, data, detected_type)
        else:
            print(f"  {label}: no data found")

    print()


def main():
    parser = argparse.ArgumentParser(description="Yahoo Fantasy API Query Tool")
    sub = parser.add_subparsers(dest="command")

    # FA query
    fa_parser = sub.add_parser("fa", help="Search free agents")
    fa_parser.add_argument("--position", "-p", help="Position filter (C, 1B, 2B, SS, LF, CF, RF, SP, RP, B, P)")
    fa_parser.add_argument("--sort", "-s", default="AR", help="Sort by: AR (actual rank), OR (overall rank) (default: AR)")
    fa_parser.add_argument("--sort-type", default="season", help="Sort period: season, lastweek, lastmonth (default: season)")
    fa_parser.add_argument("--count", "-n", type=int, default=25, help="Number of results (default: 25)")
    fa_parser.add_argument("--start", type=int, default=0, help="Pagination offset (default: 0)")
    fa_parser.add_argument("--status", default="A", help="Player status: A (all available, default), FA (free agents only), W (waivers only)")

    # Player lookup
    player_parser = sub.add_parser("player", help="Look up a specific player")
    player_parser.add_argument("player", help="Player name to search")

    # Savant Statcast lookup
    savant_parser = sub.add_parser("savant", help="Look up Statcast data from Baseball Savant")
    savant_parser.add_argument("player", help="Player name to search")
    savant_parser.add_argument("--year", "-y", help="Specific year (default: 2026 + 2025)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Savant command doesn't need Yahoo auth
    if args.command == "savant":
        cmd_savant(args)
        return

    env = load_env()
    if not os.path.exists(YAHOO_TOKEN_FILE):
        print("Yahoo token not found. Run yahoo_auth.py first.", file=sys.stderr)
        sys.exit(1)

    access_token = refresh_token(env)
    config = load_config()

    if args.command == "fa":
        cmd_fa(args, access_token, config)
    elif args.command == "player":
        cmd_player(args, access_token, config)


if __name__ == "__main__":
    main()
