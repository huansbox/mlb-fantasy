"""League roster scanner — view any team's roster, positional depth, and 7-cat stats.

Usage:
  python3 _tools/_trade_lookup.py                          # List all 12 teams
  python3 _tools/_trade_lookup.py "Droptheball"            # Show roster + depth for one team
  python3 _tools/_trade_lookup.py "Droptheball" --pos SS   # Focus on a position (show depth + stats)
  python3 _tools/_trade_lookup.py --scan SS,CF             # Scan all teams for positional surplus
  python3 _tools/_trade_lookup.py --stats "Ozzie Albies" "CJ Abrams"  # Compare players' 7-cat stats
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from yahoo_query import api_get, load_config, load_env, refresh_token

ALL_BATTER_POS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def get_league_teams(league_key, token):
    data = api_get(f"/league/{league_key}/teams", token)
    teams_raw = data["fantasy_content"]["league"][1]["teams"]
    teams = []
    for k, v in teams_raw.items():
        if k == "count":
            continue
        t = v["team"][0]
        team_key = team_name = None
        for item in t:
            if isinstance(item, dict):
                if "team_key" in item:
                    team_key = item["team_key"]
                if "name" in item:
                    team_name = item["name"]
        if team_key:
            teams.append({"key": team_key, "name": team_name})
    return teams


def get_roster(team_key, token):
    roster_data = api_get(f"/team/{team_key}/roster/players", token)
    players_raw = roster_data["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    roster = []
    for pk, pv in players_raw.items():
        if pk == "count":
            continue
        pinfo = pv["player"][0]
        name = ""
        positions = []
        selected_pos = ""
        for item in pinfo:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full", "")
                if "eligible_positions" in item:
                    pos_list = item["eligible_positions"]
                    if isinstance(pos_list, list):
                        for pp in pos_list:
                            if isinstance(pp, dict) and "position" in pp:
                                positions.append(pp["position"])
                if "selected_position" in item:
                    sp = item["selected_position"]
                    if isinstance(sp, list):
                        for spp in sp:
                            if isinstance(spp, dict) and "position" in spp:
                                selected_pos = spp["position"]
                    elif isinstance(sp, dict):
                        selected_pos = sp.get("position", "")
        field_pos = [p for p in positions if p not in
                     ("Util", "BN", "IL", "IL+", "NA", "DL", "SP", "RP", "P")]
        is_pitcher = any(x in positions for x in ("SP", "RP", "P"))
        roster.append({
            "name": name,
            "positions": field_pos,
            "all_positions": positions,
            "selected_pos": selected_pos,
            "is_pitcher": is_pitcher,
        })
    return roster


def build_pos_map(roster):
    batters = [p for p in roster if not p["is_pitcher"]]
    pos_map = {}
    for p in batters:
        for pos in p["positions"]:
            pos_map.setdefault(pos, []).append(p["name"])
    return pos_map


def print_roster(team_name, roster):
    print(f"\n=== {team_name} Roster ===")
    for p in roster:
        pos_str = ",".join(p["positions"])
        role = "P" if p["is_pitcher"] else "B"
        print(f"  [{p['selected_pos']:4s}] {p['name']:25s} ({pos_str}) {role}")


def print_depth(pos_map):
    print("\n=== 守位覆蓋 ===")
    for pos in ALL_BATTER_POS:
        players = pos_map.get(pos, [])
        count = len(players)
        marker = " *** SURPLUS" if count >= 3 else (
            " * THIN" if count <= 1 else "")
        print(f"  {pos}({count}): {', '.join(players)}{marker}")


def fetch_player_stats(name, years=(2026, 2025)):
    encoded = urllib.parse.quote(name)
    url = (f"https://statsapi.mlb.com/api/v1/people/search"
           f"?names={encoded}&sportIds=1")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    people = result.get("people", [])
    if not people:
        print(f"  {name}: not found in MLB API")
        return
    pid = people[0]["id"]
    pname = people[0]["fullName"]
    pos = people[0].get("primaryPosition", {}).get("abbreviation", "")
    for year in years:
        stat_url = (f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
                    f"?stats=season&season={year}&group=hitting")
        sreq = urllib.request.Request(
            stat_url, headers={"User-Agent": "Mozilla/5.0"})
        sresp = urllib.request.urlopen(sreq, timeout=10)
        sdata = json.loads(sresp.read())
        splits = sdata["stats"][0].get("splits", [])
        if splits:
            s = splits[0]["stat"]
            g = str(s['gamesPlayed'])
            r = str(s['runs'])
            hr = str(s['homeRuns'])
            rbi = str(s['rbi'])
            sb = str(s['stolenBases'])
            bb = str(s['baseOnBalls'])
            avg = s.get('avg', '-')
            ops = s.get('ops', '-')
            print(f"  {pname:22s} ({pos:3s}) {year}: "
                  f"{g:>3s}G | "
                  f"R:{r:>3s} HR:{hr:>2s} RBI:{rbi:>3s} "
                  f"SB:{sb:>2s} BB:{bb:>3s} "
                  f"AVG:{avg} OPS:{ops}")
        else:
            print(f"  {pname:22s} ({pos:3s}) {year}: no data")


# ── Commands ──


def cmd_list_teams(teams, my_team_key):
    print("=== League Teams ===")
    for t in teams:
        me = " (ME)" if t["key"] == my_team_key else ""
        print(f"  {t['name']}{me}")


def cmd_show_team(team_name, teams, token, focus_pos=None):
    team = next(
        (t for t in teams if t["name"].lower() == team_name.lower()), None)
    if not team:
        team = next(
            (t for t in teams if team_name.lower() in t["name"].lower()), None)
    if not team:
        print(f"Team '{team_name}' not found")
        return
    roster = get_roster(team["key"], token)
    print_roster(team["name"], roster)
    pos_map = build_pos_map(roster)
    print_depth(pos_map)

    if focus_pos:
        focus_positions = [p.strip().upper() for p in focus_pos.split(",")]
        names = set()
        for pos in focus_positions:
            names.update(pos_map.get(pos, []))
        if names:
            print(f"\n=== 7-cat Stats ({','.join(focus_positions)}) ===")
            for name in sorted(names):
                try:
                    fetch_player_stats(name)
                except Exception as e:
                    print(f"  {name}: failed ({e})")


def cmd_scan(teams, token, scan_positions, my_team_key):
    positions = [p.strip().upper() for p in scan_positions.split(",")]
    print(f"=== Scanning all teams for: {', '.join(positions)} ===\n")
    for team in teams:
        is_mine = " (ME)" if team["key"] == my_team_key else ""
        roster = get_roster(team["key"], token)
        pos_map = build_pos_map(roster)

        relevant = {}
        for pos in positions:
            players = pos_map.get(pos, [])
            if players:
                relevant[pos] = players

        if relevant:
            print(f"{team['name']}{is_mine}")
            for pos, players in relevant.items():
                count = len(players)
                marker = " *** SURPLUS" if count >= 3 else ""
                print(f"  {pos}({count}): {', '.join(players)}{marker}")


def cmd_stats(player_names):
    print("=== 7-cat Stats Comparison ===")
    for name in player_names:
        try:
            fetch_player_stats(name)
        except Exception as e:
            print(f"  {name}: failed ({e})")
        print()


def main():
    parser = argparse.ArgumentParser(description="League roster scanner")
    parser.add_argument("team", nargs="?", help="Team name (or partial match)")
    parser.add_argument("--pos",
                        help="Focus position(s), comma-separated (e.g. SS,2B)")
    parser.add_argument("--scan",
                        help="Scan all teams for position surplus (e.g. SS,CF)")
    parser.add_argument("--stats", nargs="+",
                        help="Compare players' 7-cat stats")
    args = parser.parse_args()

    config = load_config()
    league_key = config["league"]["league_key"]
    my_team_key = config["league"].get("team_key", "")
    env = load_env()
    token = refresh_token(env)
    teams = get_league_teams(league_key, token)

    if args.stats:
        cmd_stats(args.stats)
    elif args.scan:
        cmd_scan(teams, token, args.scan, my_team_key)
    elif args.team:
        cmd_show_team(args.team, teams, token, focus_pos=args.pos)
    else:
        cmd_list_teams(teams, my_team_key)


if __name__ == "__main__":
    main()
