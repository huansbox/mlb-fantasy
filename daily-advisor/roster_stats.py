"""Roster Stats — automated data collection for roster-scan.

Replaces manual WebSearch by fetching all roster player stats from
MLB Stats API + Baseball Savant CSV in one run.

Usage:
    python daily-advisor/roster_stats.py
    python daily-advisor/roster_stats.py --season 2026
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from main import (
    load_config,
    api_get,
    fetch_savant_statcast,
    fetch_savant_expected,
    fetch_pitcher_gamelog,
    parse_ip,
)


def fetch_batter_full(player_id, season):
    """Fetch batter season stats with all needed fields."""
    try:
        data = api_get(
            f"/people/{player_id}/stats?stats=season&season={season}&group=hitting"
        )
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return None
        s = splits[0]["stat"]
        pa = int(s.get("plateAppearances", 0))
        ab = int(s.get("atBats", 0))
        hr = int(s.get("homeRuns", 0))
        bb = int(s.get("baseOnBalls", 0))
        g = int(s.get("gamesPlayed", 0))
        return {
            "g": g, "pa": pa,
            "ops": s.get("ops", "—"),
            "hr": hr,
            "bb_pct": round(bb / pa * 100, 1) if pa > 0 else 0,
        }
    except Exception as e:
        print(f"  Batter stats error ({player_id}): {e}", file=sys.stderr)
        return None


def fetch_pitcher_full(player_id, season):
    """Fetch pitcher season stats + gamelog for QS calculation."""
    try:
        data = api_get(
            f"/people/{player_id}/stats?stats=season&season={season}&group=pitching"
        )
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return None
        s = splits[0]["stat"]
        gamelog = fetch_pitcher_gamelog(player_id, season)
        gs = int(s.get("gamesStarted", 0))
        qs = sum(1 for g in gamelog if g["ip"] >= 6.0 and g["er"] <= 3) if gamelog else 0
        return {
            "gs": gs,
            "ip": s.get("inningsPitched", "0"),
            "era": s.get("era", "—"),
            "whip": s.get("whip", "—"),
            "k": int(s.get("strikeOuts", 0)),
            "w": int(s.get("wins", 0)),
            "qs": qs,
        }
    except Exception as e:
        print(f"  Pitcher stats error ({player_id}): {e}", file=sys.stderr)
        return None


def fetch_savant_all(roster_ids, season):
    """Fetch Savant data for current + prior year."""
    result = {}
    for year in [season, season - 1]:
        label = "current" if year == season else "prior"
        sc = fetch_savant_statcast(year, roster_ids)
        ex = fetch_savant_expected(year, roster_ids)
        for pid in roster_ids:
            if pid not in result:
                result[pid] = {}
            s = sc.get(pid, {})
            e = ex.get(pid, {})
            if s or e:
                result[pid][label] = {
                    "hh_pct": s.get("hh_pct", 0),
                    "barrel_pct": s.get("barrel_pct", 0),
                    "bbe": s.get("bbe", 0),
                    "xwoba": e.get("xwoba", 0),
                }
    return result


def fmt(val, spec=".3f"):
    """Format a numeric value, return '—' if zero/None."""
    if val is None or val == 0:
        return "—"
    return f"{val:{spec}}"


def main():
    parser = argparse.ArgumentParser(description="Roster Stats — automated data collection")
    parser.add_argument("--season", type=int, default=None)
    args = parser.parse_args()

    config = load_config()
    season = args.season or config["league"]["season"]
    batters = config["batters"]
    pitchers = config["pitchers"]

    print(f"Collecting data for {season}...", file=sys.stderr)

    # ── Batters ──
    roster_ids = [b["mlb_id"] for b in batters if b.get("mlb_id")]

    print("Fetching batter MLB API stats...", file=sys.stderr)
    batter_stats = {}
    for b in batters:
        mid = b.get("mlb_id")
        if mid:
            batter_stats[mid] = {
                "current": fetch_batter_full(mid, season),
                "prior": fetch_batter_full(mid, season - 1),
            }

    print("Fetching Savant CSV...", file=sys.stderr)
    savant = fetch_savant_all(roster_ids, season)

    print(f"\n=== 打者（{season} 本季 + {season-1} 基準）===\n")
    header = f"| 球員 | 位置 | G | PA | xwOBA | HH% | Barrel% | OPS | HR | BB% | BBE | xwOBA({season-1}) | HH%({season-1}) |"
    print(header)
    print("|------|------|---|----|-------|------|---------|-----|----|-----|-----|-----------|---------|")

    for b in batters:
        mid = b.get("mlb_id")
        if not mid:
            continue
        pos = "/".join(b["positions"])
        cur = (batter_stats.get(mid) or {}).get("current") or {}
        sv_cur = (savant.get(mid) or {}).get("current") or {}
        sv_pri = (savant.get(mid) or {}).get("prior") or {}

        g = cur.get("g", 0)
        pa = cur.get("pa", 0)
        ops = cur.get("ops", "—")
        hr = cur.get("hr", 0)
        bb_pct = f"{cur['bb_pct']:.1f}%" if cur.get("bb_pct") is not None else "—"
        xwoba = fmt(sv_cur.get("xwoba"))
        hh = f"{sv_cur['hh_pct']:.1f}%" if sv_cur.get("hh_pct") is not None else "—"
        barrel = f"{sv_cur['barrel_pct']:.1f}%" if sv_cur.get("barrel_pct") is not None else "—"
        bbe = sv_cur.get("bbe", 0)
        xwoba_pri = fmt(sv_pri.get("xwoba"))
        hh_pri = f"{sv_pri['hh_pct']:.1f}%" if sv_pri.get("hh_pct") is not None else "—"

        print(f"| {b['name']} | {pos} | {g} | {pa} | {xwoba} | {hh} | {barrel} | {ops} | {hr} | {bb_pct} | {bbe} | {xwoba_pri} | {hh_pri} |")

    # ── Pitchers ──
    print(f"\n=== 投手（{season}）===\n")
    print("| 球員 | 隊伍 | Type | GS | IP | ERA | WHIP | K | W | QS |")
    print("|------|------|------|----|----|-----|------|---|---|----|")

    print("Fetching pitcher stats...", file=sys.stderr)
    for p in pitchers:
        mid = p.get("mlb_id")
        if not mid:
            continue
        d = fetch_pitcher_full(mid, season)
        if not d:
            role = "IL" if p.get("role") == "IL" else p["type"]
            print(f"| {p['name']} | {p['team']} | {role} | — | — | — | — | — | — | — |")
            continue
        print(f"| {p['name']} | {p['team']} | {p['type']} | {d['gs']} | {d['ip']} | {d['era']} | {d['whip']} | {d['k']} | {d['w']} | {d['qs']} |")


if __name__ == "__main__":
    main()
