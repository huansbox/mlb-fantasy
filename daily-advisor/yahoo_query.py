"""Yahoo Fantasy API query tool — FA player search and player lookup."""

import argparse
import json
import os
import sys
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
    # percent_owned may be at any index after 0 (depends on sub-resources requested)
    for idx in range(1, len(player_data)):
        po_data = player_data[idx]
        if isinstance(po_data, dict) and "percent_owned" in po_data:
            po_list = po_data["percent_owned"]
            if isinstance(po_list, list):
                for po in po_list:
                    if isinstance(po, dict) and "value" in po:
                        percent_owned = po["value"]
            elif isinstance(po_list, dict):
                percent_owned = po_list.get("value")
            break
    return {
        "name": name or "?",
        "team": team or "?",
        "position": position or "?",
        "status": status or "",
        "percent_owned": percent_owned,
        "player_key": player_key,
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
    path = f"/league/{league_key}/players;{filter_str};out=stats,percent_owned"

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
        stats = p.get("stats", {})
        if "ERA" in stats:
            stat_str = f"ERA {stats.get('ERA', '—')} | WHIP {stats.get('WHIP', '—')} | K {stats.get('K', '—')} | IP {stats.get('IP', '—')}"
        elif "AVG" in stats:
            stat_str = f"AVG {stats.get('AVG', '—')} | OPS {stats.get('OPS', '—')} | HR {stats.get('HR', '—')} | BB {stats.get('BB', '—')}"
        else:
            stat_str = ""
        print(f"{i:3}  {p['name']:20}  {p['team']:5}  {p['position']:12}  {po:>7}  {stat_str}  {st}")


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

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
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
