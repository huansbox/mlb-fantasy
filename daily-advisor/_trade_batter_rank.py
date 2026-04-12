"""Trade Batter Rank — scan all opponent teams, rank where a target batter fits.

Shows 7 batter scoring categories (R, HR, RBI, SB, BB, AVG, OPS) + wRC+
for each opponent team's batters, inserts the target player, and reports rank.

Usage:
    python _trade_batter_rank.py "Ozzie Albies"
    python _trade_batter_rank.py "Ozzie Albies" --threshold 8
    python _trade_batter_rank.py "Ozzie Albies" --sort OPS
"""

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import load_env, load_config, refresh_token, api_get

YAHOO_BATTER_STATS = {
    "7": "R", "12": "HR", "13": "RBI", "16": "SB",
    "18": "BB", "3": "AVG", "55": "OPS",
}

MLB_CTX = ssl.create_default_context()


def mlb_get(url):
    return json.loads(urllib.request.urlopen(url, context=MLB_CTX).read())


def search_mlb_id(name):
    safe = (name.replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    url = ("https://statsapi.mlb.com/api/v1/people/search"
           f"?names={urllib.parse.quote(safe)}&sportId=1")
    try:
        d = mlb_get(url)
        people = d.get("people", [])
        return people[0]["id"] if people else None
    except Exception:
        return None


def fetch_wrc_plus(mlb_id, season=2026):
    try:
        url = (f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
               f"?stats=sabermetrics&season={season}&group=hitting")
        d = mlb_get(url)
        splits = d.get("stats", [{}])[0].get("splits", [])
        if splits:
            val = splits[0]["stat"].get("wRcPlus")
            return round(val, 1) if val is not None else None
    except Exception:
        pass
    return None


def fetch_all_teams(league_key, token):
    data = api_get(f"/league/{league_key}/teams", token)
    teams = []
    td = data["fantasy_content"]["league"][1]["teams"]
    for k, v in td.items():
        if k == "count":
            continue
        info = v["team"][0]
        name = key = ""
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"]
                if "team_key" in item:
                    key = item["team_key"]
        teams.append({"name": name, "key": key})
    return teams


def fetch_roster_batters(team_key, token):
    data = api_get(f"/team/{team_key}/roster", token)
    players = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    batters = []
    for k, v in players.items():
        if k == "count":
            continue
        p = v["player"]
        info = p[0]
        name = pos_str = player_key = ""
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full", "")
                if "display_position" in item:
                    pos_str = item["display_position"]
                if "player_key" in item:
                    player_key = item["player_key"]
        positions = [x.strip() for x in pos_str.split(",")]
        if any(p in ("SP", "RP") for p in positions):
            continue
        batters.append({
            "name": name, "positions": positions, "player_key": player_key,
        })
    return batters


def fetch_batter_stats(player_keys, league_key, token):
    results = {}
    chunks = [player_keys[i:i + 25] for i in range(0, len(player_keys), 25)]
    for chunk in chunks:
        keys_str = ",".join(chunk)
        data = api_get(
            f"/league/{league_key}/players;player_keys={keys_str}/stats;type=season",
            token,
        )
        players_node = data["fantasy_content"]["league"][1]["players"]
        for k, v in players_node.items():
            if k == "count":
                continue
            p = v["player"]
            info = p[0]
            stats_node = p[1]["player_stats"]["stats"]
            player_key = ""
            for item in info:
                if isinstance(item, dict) and "player_key" in item:
                    player_key = item["player_key"]
            stats = {}
            for s in stats_node:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid in YAHOO_BATTER_STATS:
                    cat = YAHOO_BATTER_STATS[sid]
                    try:
                        stats[cat] = float(val)
                    except (ValueError, TypeError):
                        stats[cat] = 0.0
            results[player_key] = stats
    return results


def main():
    parser = argparse.ArgumentParser(description="Trade Batter Rank Scanner")
    parser.add_argument("player", help="Target player name to evaluate")
    parser.add_argument("--threshold", type=int, default=8,
                        help="Rank threshold for trade candidacy (default: 8)")
    parser.add_argument("--sort", default="wRC+",
                        help="Sort by: wRC+ (default), OPS, AVG, HR, BB, etc.")
    args = parser.parse_args()

    env = load_env()
    config = load_config()
    token = refresh_token(env)
    league_key = config["league"]["league_key"]
    season = config["league"].get("season", 2026)
    my_team_name = config["league"].get("team_name", "99 940")

    target_name = args.player
    target_key = None
    sort_cat = args.sort
    print(f"Scanning for: {target_name}", file=sys.stderr)
    print(f"Sort by: {sort_cat} | Threshold: rank ≤ {args.threshold}", file=sys.stderr)

    teams = fetch_all_teams(league_key, token)
    print(f"Teams: {len(teams)}", file=sys.stderr)

    # ── Find target player ──
    my_team = next((t for t in teams if t["name"] == my_team_name), None)
    if my_team:
        my_batters = fetch_roster_batters(my_team["key"], token)
        for b in my_batters:
            if target_name.lower() in b["name"].lower():
                target_key = b["player_key"]
                target_name = b["name"]
                break

    if not target_key:
        print(f"WARNING: '{target_name}' not found on roster", file=sys.stderr)
        sys.exit(1)

    # ── Fetch target Yahoo stats + wRC+ ──
    target_yahoo = fetch_batter_stats([target_key], league_key, token)
    target_stats = target_yahoo.get(target_key, {})
    if not target_stats:
        print(f"ERROR: Could not fetch stats for {target_name}", file=sys.stderr)
        sys.exit(1)

    target_mlb_id = search_mlb_id(target_name)
    target_wrc = fetch_wrc_plus(target_mlb_id, season) if target_mlb_id else None
    target_stats["wRC+"] = target_wrc or 0

    cats_display = ("R", "HR", "RBI", "SB", "BB", "AVG", "OPS")
    print(f"\n[Target] {target_name}: " +
          "  ".join(f"{c}={target_stats.get(c, 0):.0f}" if c not in ("AVG", "OPS")
                    else f"{c}={target_stats.get(c, 0):.3f}" for c in cats_display) +
          f"  wRC+={target_wrc or '?'}")

    # ── Scan each opponent team ──
    summary = []
    for team in teams:
        if team["name"] == my_team_name:
            continue

        print(f"\nFetching {team['name']}...", file=sys.stderr)
        batters = fetch_roster_batters(team["key"], token)
        if not batters:
            continue

        keys = [b["player_key"] for b in batters if b["player_key"]]
        stats_map = fetch_batter_stats(keys, league_key, token)

        # Build rows with wRC+
        rows = []
        for b in batters:
            s = stats_map.get(b["player_key"], {})
            if not s:
                continue
            mlb_id = search_mlb_id(b["name"])
            wrc = fetch_wrc_plus(mlb_id, season) if mlb_id else None
            rows.append({
                "name": b["name"],
                "positions": ",".join(b["positions"]),
                "wRC+": wrc or 0,
                **{c: s.get(c, 0.0) for c in cats_display},
            })

        # Insert target
        target_row = {
            "name": f">>> {target_name} <<<",
            "positions": "—",
            "wRC+": target_stats.get("wRC+", 0),
            **{c: target_stats.get(c, 0.0) for c in cats_display},
        }
        rows.append(target_row)

        # Sort
        sk = sort_cat if sort_cat != "wRC+" else "wRC+"
        rows.sort(key=lambda r: r.get(sk, 0), reverse=True)

        # Find rank
        rank = next(
            (i for i, r in enumerate(rows, 1) if r["name"] == target_row["name"]),
            len(rows),
        )
        total = len(rows)

        # Print
        print(f"\n{'=' * 105}")
        print(f"  {team['name']} ({total - 1} batters) — "
              f"{target_name} ranks #{rank}/{total} by {sort_cat}")
        print(f"{'=' * 105}")
        print(f"  {'#':>2} {'Player':<25} {'Pos':<12} {'wRC+':>5} "
              f"{'R':>4} {'HR':>3} {'RBI':>4} {'SB':>3} {'BB':>3} "
              f"{'AVG':>6} {'OPS':>6}")

        for i, r in enumerate(rows, 1):
            marker = " ★" if ">>>" in r["name"] else ""
            display_name = target_name if ">>>" in r["name"] else r["name"]
            wrc_str = f"{r['wRC+']:.0f}" if r["wRC+"] else "—"
            print(f"  {i:>2} {display_name:<25} {r['positions']:<12} {wrc_str:>5} "
                  f"{r['R']:>4.0f} {r['HR']:>3.0f} {r['RBI']:>4.0f} "
                  f"{r['SB']:>3.0f} {r['BB']:>3.0f} {r['AVG']:>6.3f} "
                  f"{r['OPS']:>6.3f}{marker}")

        is_candidate = rank <= args.threshold
        summary.append({
            "team": team["name"],
            "rank": rank,
            "total": total,
            "candidate": is_candidate,
        })

    # ── Summary ──
    print(f"\n\n{'=' * 65}")
    print(f"=== SUMMARY: {target_name} rank across {len(summary)} "
          f"teams (by {sort_cat}) ===")
    print(f"{'=' * 65}")
    print(f"  Threshold: rank ≤ {args.threshold} = trade candidate\n")

    summary.sort(key=lambda x: x["rank"])
    candidates = 0
    for s in summary:
        tag = "✅ CANDIDATE" if s["candidate"] else "—"
        print(f"  #{s['rank']:>2}/{s['total']} {s['team']:<22} {tag}")
        if s["candidate"]:
            candidates += 1

    print(f"\n  Trade candidates: {candidates}/{len(summary)} teams")
    ranks = sorted(s["rank"] for s in summary)
    print(f"  {target_name} median rank: #{ranks[len(ranks) // 2]}")


if __name__ == "__main__":
    main()
