"""One-off script: look up fantasy team owners for trade targets."""
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import urllib.parse
from yahoo_query import load_env, refresh_token, load_config, api_get, extract_player_info, parse_player_stats  # noqa

env = load_env()
config = load_config()
league_key = config["league"]["league_key"]
access_token = refresh_token(env)

targets = ["Maikel Garcia", "Brendan Donovan", "Alec Burleson", "Ozzie Albies"]

for name in targets:
    try:
        encoded = urllib.parse.quote(name)
        data = api_get(
            f"/league/{league_key}/players;search={encoded};status=T;sort=AR;sort_type=season;count=1",
            access_token,
        )
        players = data["fantasy_content"]["league"][1]["players"]
    except Exception as e:
        print(f"=== {name}: lookup failed ({e}) ===\n")
        continue

    for k, v in players.items():
        if k == "count":
            continue
        p = v["player"]
        info = extract_player_info(p)

        # Get owner team name
        owner = ""
        for idx in range(len(p)):
            if isinstance(p[idx], dict) and "ownership" in p[idx]:
                owner = p[idx]["ownership"].get("owner_team_name", "")

        # Get stats
        pkey = info.get("player_key")
        stats = {}
        if pkey:
            try:
                sd = api_get(
                    f"/league/{league_key}/players;player_keys={pkey}/stats",
                    access_token,
                )
                sp = sd["fantasy_content"]["league"][1]["players"]["0"]["player"]
                stats = parse_player_stats(sp)
            except Exception:
                pass

        print(f"=== {info['name']} ({info['team']}, {info['position']}) ===")
        print(f"Fantasy Owner: {owner}")
        print(f"Rostered: {info.get('percent_owned', '?')}%")
        if stats:
            for sn, sv in stats.items():
                print(f"  {sn}: {sv}")
        print()
