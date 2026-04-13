"""Merge 2-week scoreboard data for rolling analysis."""
import sys, json
sys.path.insert(0, ".")
from yahoo_query import load_env, load_config, refresh_token, api_get, YAHOO_STAT_MAP


def ip_float(x):
    try:
        s = str(x); parts = s.split(".")
        return int(parts[0]) + (int(parts[1]) / 3 if len(parts) > 1 else 0)
    except Exception:
        return 0.0


def fetch_week(league_key, token, wk):
    sb = api_get(f"/league/{league_key}/scoreboard;week={wk}", token)
    matchups = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]
    teams = {}
    for k, v in matchups.items():
        if k == "count":
            continue
        for tidx in ["0", "1"]:
            tinfo = v["matchup"]["0"]["teams"][tidx]["team"][0]
            tstats = v["matchup"]["0"]["teams"][tidx]["team"][1]["team_stats"]["stats"]
            name = "?"
            for item in tinfo:
                if isinstance(item, dict) and "name" in item:
                    name = item["name"]
            row = {}
            for s in tstats:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid in YAHOO_STAT_MAP:
                    cat, _ = YAHOO_STAT_MAP[sid]
                    row[cat] = val
            teams[name] = row
    return teams


def merge_two(w2, w3):
    def f(k, w):
        try:
            return float(w.get(k, 0) or 0)
        except Exception:
            return 0.0

    def hab(w):
        s = w.get("H/AB", "0/0")
        try:
            h, ab = s.split("/")
            return int(h), int(ab)
        except Exception:
            return 0, 0

    h2, ab2 = hab(w2); h3, ab3 = hab(w3)
    H, AB = h2 + h3, ab2 + ab3
    AVG = H / AB if AB else 0
    OPS = (f("OPS", w2) * ab2 + f("OPS", w3) * ab3) / AB if AB else 0
    ip2 = ip_float(w2.get("IP", 0)); ip3 = ip_float(w3.get("IP", 0))
    IP = ip2 + ip3
    ERA = (f("ERA", w2) * ip2 + f("ERA", w3) * ip3) / IP if IP else 0
    WHIP = (f("WHIP", w2) * ip2 + f("WHIP", w3) * ip3) / IP if IP else 0
    return {
        "R": int(f("R", w2) + f("R", w3)),
        "HR": int(f("HR", w2) + f("HR", w3)),
        "RBI": int(f("RBI", w2) + f("RBI", w3)),
        "SB": int(f("SB", w2) + f("SB", w3)),
        "BB": int(f("BB", w2) + f("BB", w3)),
        "AVG": round(AVG, 3),
        "OPS": round(OPS, 3),
        "IP": round(IP, 1),
        "W": int(f("W", w2) + f("W", w3)),
        "K": int(f("K", w2) + f("K", w3)),
        "ERA": round(ERA, 2),
        "WHIP": round(WHIP, 2),
        "QS": int(f("QS", w2) + f("QS", w3)),
        "SV+H": int(f("SV+H", w2) + f("SV+H", w3)),
    }


def main():
    env = load_env()
    token = refresh_token(env)
    cfg = load_config()
    league_key = cfg["league"]["league_key"]
    w2 = fetch_week(league_key, token, 2)
    w3 = fetch_week(league_key, token, 3)
    merged = {name: merge_two(w2.get(name, {}), w3.get(name, {})) for name in w2}

    cats = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS", "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]
    print("== Week 2+3 Merged ==")
    hdr = f"{'Team':22} " + " ".join(f"{c:>6}" for c in cats)
    print(hdr)
    for name, m in sorted(merged.items(), key=lambda kv: -kv[1]["OPS"]):
        line = f"{name[:22]:22} " + " ".join(f"{str(m[c]):>6}" for c in cats)
        print(line)

    print()
    print("== Category Ranks (99 940 and RALLY MONKEY) ==")
    me = "99 940"
    opp = "RALLY MONKEY\u00ae"
    print(f"{'Cat':6} {'me':>6} {'me#':>5} {'opp':>6} {'opp#':>5}")
    for cat in cats:
        rev = cat not in ["ERA", "WHIP"]
        sorted_teams = sorted(merged.items(), key=lambda kv: kv[1][cat], reverse=rev)
        rank_of = {name: i + 1 for i, (name, _) in enumerate(sorted_teams)}
        my_rank = rank_of.get(me, "?")
        opp_rank = rank_of.get(opp, "?")
        my_val = merged.get(me, {}).get(cat, "-")
        opp_val = merged.get(opp, {}).get(cat, "-")
        print(f"{cat:6} {str(my_val):>6} #{my_rank:<4} {str(opp_val):>6} #{opp_rank:<4}")


if __name__ == "__main__":
    main()
