#!/usr/bin/env python3
"""Scout ALL teams: for every team in the league, list each week's H2H opponent
and that opponent's weekly team-level totals, annotated with the opponent's rank
among all teams that week (1 = best). Emits JSON for downstream HTML rendering.

Self-contained — stdlib only; reads .env / yahoo_token.json / roster_config.json
from its own directory. Does NOT import project modules.

Usage (run on VPS, in daily-advisor/):
    python3 _scout_all.py [--from-week 2]
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# .env / yahoo_token.json / roster_config.json live in daily-advisor/ (parent of
# _tools/) on both VPS and dev — resolve them relative to DATA_DIR, not SCRIPT_DIR.
DATA_DIR = os.path.dirname(SCRIPT_DIR)
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
TOKEN_FILE = os.path.join(DATA_DIR, "yahoo_token.json")

PITCHING = [("50", "IP"), ("28", "W"), ("42", "K"), ("26", "ERA"),
            ("27", "WHIP"), ("83", "QS"), ("89", "SV+H")]
BATTING = [("7", "R"), ("12", "HR"), ("13", "RBI"), ("16", "SB"),
           ("18", "BB"), ("3", "AVG"), ("55", "OPS")]
LOWER_BETTER = {"26", "27"}  # ERA, WHIP


def load_env():
    env = {}
    p = os.path.join(DATA_DIR, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for k in ("YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET"):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def refresh_token(env):
    with open(TOKEN_FILE, encoding="utf-8") as f:
        tok = json.load(f)
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
        "client_id": env["YAHOO_CLIENT_ID"],
        "client_secret": env["YAHOO_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        YAHOO_TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read())
    tok["access_token"] = res["access_token"]
    if "refresh_token" in res:
        tok["refresh_token"] = res["refresh_token"]
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)
    return res["access_token"]


def api_get(path, token):
    url = f"{YAHOO_API}{path}"
    url += ("&" if "?" in path else "?") + "format=json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def first_sunday(opening):
    d = opening
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d


def week_bounds(week, opening):
    fs = first_sunday(opening)
    if week == 1:
        return opening, fs
    start = fs + timedelta(days=1 + 7 * (week - 2))
    return start, start + timedelta(days=6)


def compute_current_week(today, opening):
    fs = first_sunday(opening)
    if today <= fs:
        return 1
    w = 2
    while True:
        s, e = week_bounds(w, opening)
        if s <= today <= e:
            return w
        if today < s:
            return w - 1
        w += 1


def parse_week(sb):
    """Return (pairs, all_teams): pairs=[(A,B),...]; all_teams={name:{sid:raw}}."""
    mus = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]
    pairs = []
    all_teams = {}
    for k, v in mus.items():
        if k == "count":
            continue
        tn = v["matchup"]["0"]["teams"]
        names = []
        for ti in ("0", "1"):
            info = tn[ti]["team"][0]
            stats_raw = tn[ti]["team"][1]["team_stats"]["stats"]
            name = "?"
            for it in info:
                if isinstance(it, dict) and "name" in it:
                    name = it["name"]
                    break
            all_teams[name] = {s["stat"]["stat_id"]: s["stat"]["value"] for s in stats_raw}
            names.append(name)
        pairs.append((names[0], names[1]))
    return pairs, all_teams


def rank_maps(all_teams):
    """Return {sid: {name: rank, '_of': n}} for every tracked sid. 1 = best."""
    rmap = {}
    for sid, _ in PITCHING + BATTING:
        vals = {}
        for nm, st in all_teams.items():
            try:
                vals[nm] = float(st.get(sid, ""))
            except (ValueError, TypeError):
                continue
        lower = sid in LOWER_BETTER
        rmap[sid] = {"_of": len(vals)}
        for nm, tv in vals.items():
            better = sum(1 for x in vals.values() if (x < tv if lower else x > tv))
            rmap[sid][nm] = better + 1
    return rmap


def cell(all_teams, rmap, team, sid):
    return {
        "v": all_teams.get(team, {}).get(sid, ""),
        "rank": rmap.get(sid, {}).get(team),
        "of": rmap.get(sid, {}).get("_of", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-week", type=int, default=2)
    args = ap.parse_args()

    with open(os.path.join(DATA_DIR, "roster_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    league_key = cfg["league"]["league_key"]
    opening = date.fromisoformat(cfg["league"]["opening_day"])

    token = refresh_token(load_env())
    cur = compute_current_week(date.today(), opening)

    teams_out = {}
    for wk in range(args.from_week, cur + 1):
        s, e = week_bounds(wk, opening)
        sb = api_get(f"/league/{league_key}/scoreboard;week={wk}", token)
        pairs, all_teams = parse_week(sb)
        rmap = rank_maps(all_teams)
        oppmap = {}
        for a, b in pairs:
            oppmap[a] = b
            oppmap[b] = a
        for team in all_teams:
            opp = oppmap.get(team)
            row = {"week": wk, "dates": [s.isoformat(), e.isoformat()],
                   "in_progress": wk == cur, "opponent": opp}
            if opp is not None:
                row["pitching"] = {disp: cell(all_teams, rmap, opp, sid) for sid, disp in PITCHING}
                row["batting"] = {disp: cell(all_teams, rmap, opp, sid) for sid, disp in BATTING}
            teams_out.setdefault(team, []).append(row)

    for t in teams_out:
        teams_out[t].sort(key=lambda r: r["week"], reverse=True)

    print(json.dumps({"current_week": cur, "teams": teams_out}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
