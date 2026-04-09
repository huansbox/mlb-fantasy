"""Daily Advisor — Fantasy Baseball 每日陣容建議產生器"""

import argparse
import csv
import io
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

# ── 2025 MLB Statcast percentile breakpoints (P90 = elite for both) ──
# Batters: higher value = better
BATTER_PCTILES = {
    "xwoba":      [(25,.261),(40,.286),(45,.293),(50,.297),(55,.302),(60,.307),(70,.321),(80,.331),(90,.349)],
    "bb_pct":     [(25,5.8),(40,7.0),(45,7.4),(50,7.8),(55,8.2),(60,8.7),(70,9.6),(80,10.8),(90,12.2)],
    "barrel_pct": [(25,4.7),(40,6.5),(45,7.1),(50,7.8),(55,8.5),(60,9.1),(70,10.3),(80,12.0),(90,14.0)],
    "hh_pct":     [(25,34.6),(40,38.3),(45,39.0),(50,40.4),(55,41.5),(60,42.6),(70,44.7),(80,46.7),(90,49.7)],
    "pa_per_tg":  [(25,0.88),(40,1.37),(45,1.71),(50,1.96),(55,2.16),(60,2.47),(70,2.90),(80,3.39),(90,3.96)],
}
# Pitchers: lower value = better, but P90 = elite = lowest value
# SP and RP share quality metrics; RP has additional K/9 and IP/Team_G
PITCHER_PCTILES = {
    "xera":       [(25,5.62),(40,4.64),(45,4.48),(50,4.33),(55,4.16),(60,4.04),(70,3.74),(80,3.43),(90,2.98)],
    "xwoba":      [(25,.361),(40,.332),(45,.327),(50,.322),(55,.316),(60,.312),(70,.301),(80,.289),(90,.270)],
    "hh_pct":     [(25,44.2),(40,42.2),(45,41.6),(50,40.8),(55,40.2),(60,39.4),(70,38.0),(80,36.4),(90,34.1)],
    "barrel_pct": [(25,10.1),(40,9.1),(45,8.9),(50,8.5),(55,8.1),(60,7.9),(70,7.1),(80,6.3),(90,4.9)],
    # IP/GS: not in percentile table (distribution too concentrated, P40-P60 only 0.27 IP apart)
    # Use 3-tier classification instead: <5.3 short / 5.3-5.7 average / >5.7 deep
    "era_diff":   [(25,0.28),(40,0.43),(45,0.49),(50,0.53),(55,0.59),(60,0.66),(70,0.81),(80,1.03),(90,1.31)],
}
RP_PCTILES = {
    "k_per_9":    [(25,7.51),(40,8.24),(45,8.44),(50,8.70),(55,8.88),(60,9.23),(70,9.75),(80,10.39),(90,11.47)],
    "ip_per_tg":  [(25,0.24),(40,0.29),(45,0.31),(50,0.34),(55,0.35),(60,0.37),(70,0.40),(80,0.42),(90,0.45)],
    "era_diff":   [(25,0.28),(40,0.43),(45,0.52),(50,0.57),(55,0.63),(60,0.72),(70,0.88),(80,1.06),(90,1.24)],
}

# Yahoo slot codes that mean "not in active lineup pool"
# Mirror of yahoo_query.INACTIVE_SLOTS — kept here to avoid circular import.
INACTIVE_SLOTS = ("IL", "IL+", "NA")


def is_active(player):
    """Return True if player is active (not on IL/IL+/NA).

    Mirrors yahoo_query.is_active — kept here to avoid circular import.
    Checks both 'role' (set during roster parsing) and 'selected_pos'.
    """
    if player.get("role") == "IL":
        return False
    if player.get("selected_pos", "") in INACTIVE_SLOTS:
        return False
    return True


def pctile_tag(value, metric, player_type="batter"):
    """Return percentile range tag like '(P70-80)' or '(>P90)'."""
    if player_type == "batter":
        table = BATTER_PCTILES
    elif player_type == "rp":
        table = {**PITCHER_PCTILES, **RP_PCTILES}
    else:
        table = PITCHER_PCTILES
    bp = table.get(metric)
    if not bp or value is None:
        return ""
    # Auto-detect direction: if P90 > P25, higher value = better percentile
    higher_better = bp[-1][1] > bp[0][1]
    # Find the highest percentile bracket the value qualifies for
    matched = None
    for pct, thresh in reversed(bp):
        if (higher_better and value >= thresh) or (not higher_better and value <= thresh):
            matched = pct
            break
    if matched is None:
        return "(<P25)"
    if matched == 90:
        return "(>P90)"
    # Find next bracket above
    for i, (pct, _) in enumerate(bp):
        if pct == matched and i + 1 < len(bp):
            return f"(P{matched}-{bp[i+1][0]})"
    return f"(P{matched})"
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
    # Derive role/type for config entries (Yahoo API path generates these at runtime)
    for b in config.get("batters", []):
        if "role" not in b:
            sp = b.get("selected_pos", "")
            b["role"] = "IL" if sp in ("IL", "IL+", "NA") else ("bench" if sp == "BN" else "starter")
        if "positions" not in b:
            b["positions"] = []
    for p in config.get("pitchers", []):
        if "role" not in p:
            sp = p.get("selected_pos", "")
            p["role"] = "IL" if sp in ("IL", "IL+", "NA") else ("bench" if sp == "BN" else "starter")
        if "type" not in p:
            positions = p.get("positions", [])
            p["type"] = "SP" if "SP" in positions else ("RP" if "RP" in positions else "SP")
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


# ── Park Factors (runs, 100 = neutral) ──
# Source: ESPN Park Factors (5-year avg), updated 2025 offseason.
# >100 = hitter-friendly, <100 = pitcher-friendly.
PARK_FACTORS = {
    # venue_id: (abbr, factor)
    15: ("AZ", 104),     # Chase Field
    680: ("ATL", 99),    # Truist Park
    2: ("BAL", 101),     # Camden Yards
    3: ("BOS", 104),     # Fenway Park
    17: ("CHC", 100),    # Wrigley Field
    4: ("CWS", 101),     # Guaranteed Rate Field
    2602: ("CIN", 106),  # Great American Ball Park
    5: ("CLE", 96),      # Progressive Field
    19: ("COL", 114),    # Coors Field
    2394: ("DET", 97),   # Comerica Park
    2392: ("HOU", 100),  # Minute Maid Park
    7: ("KC", 101),      # Kauffman Stadium
    1: ("LAA", 97),      # Angel Stadium
    22: ("LAD", 96),     # Dodger Stadium
    4169: ("MIA", 93),   # LoanDepot Park
    32: ("MIL", 101),    # American Family Field
    3312: ("MIN", 100),  # Target Field
    3289: ("NYM", 96),   # Citi Field
    3313: ("NYY", 107),  # Yankee Stadium
    10: ("ATH", 96),     # Oakland Coliseum (or Sacramento)
    2681: ("PHI", 103),  # Citizens Bank Park
    31: ("PIT", 96),     # PNC Park
    2680: ("SD", 93),    # Petco Park
    2395: ("SF", 95),    # Oracle Park
    3309: ("SEA", 95),   # T-Mobile Park
    14: ("STL", 97),     # Busch Stadium
    12: ("TB", 95),      # Tropicana Field
    5325: ("TEX", 103),  # Globe Life Field
    2536: ("TOR", 100),  # Rogers Centre
    3714: ("WSH", 99),   # Nationals Park
}


def get_park_factor(venue_id):
    """Return park factor label for a venue. Empty string if neutral/unknown."""
    if not venue_id:
        return ""
    pf = PARK_FACTORS.get(venue_id)
    if not pf:
        return ""
    _, factor = pf
    if factor >= 106:
        return f"PF {factor} (打者有利)"
    elif factor <= 95:
        return f"PF {factor} (投手有利)"
    return ""


# ── Data fetching ──


def fetch_schedule(date_str):
    """Fetch games + probable pitchers for a date (YYYY-MM-DD)."""
    data = api_get(f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher")
    games = []
    for d in data.get("dates", []):
        for g in d["games"]:
            away = g["teams"]["away"]
            home = g["teams"]["home"]
            venue = g.get("venue", {})
            games.append({
                "away_team": away["team"]["name"],
                "home_team": home["team"]["name"],
                "away_pitcher": away.get("probablePitcher", {}).get("fullName"),
                "home_pitcher": home.get("probablePitcher", {}).get("fullName"),
                "away_pitcher_id": away.get("probablePitcher", {}).get("id"),
                "home_pitcher_id": home.get("probablePitcher", {}).get("id"),
                "game_time": g.get("gameDate", ""),
                "venue_name": venue.get("name", ""),
                "venue_id": venue.get("id"),
                "game_state": g.get("status", {}).get("abstractGameState", ""),
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
            "w": int(s["stat"].get("wins", 0)),
            "h": int(s["stat"].get("hits", 0)),
            "bb": int(s["stat"].get("baseOnBalls", 0)),
            "gs": int(s["stat"].get("gamesStarted", 0)),
        }
        for s in splits
    ]


def fetch_batter_gamelog(player_id, season):
    """Fetch batting game log for the season."""
    data = api_get(
        f"/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    return [
        {
            "date": s["date"],
            "opponent": s.get("opponent", {}).get("name", "?"),
            "pa": int(s["stat"].get("plateAppearances", 0)),
            "ab": int(s["stat"].get("atBats", 0)),
            "r": int(s["stat"].get("runs", 0)),
            "h": int(s["stat"].get("hits", 0)),
            "hr": int(s["stat"].get("homeRuns", 0)),
            "rbi": int(s["stat"].get("rbi", 0)),
            "sb": int(s["stat"].get("stolenBases", 0)),
            "bb": int(s["stat"].get("baseOnBalls", 0)),
            "doubles": int(s["stat"].get("doubles", 0)),
            "triples": int(s["stat"].get("triples", 0)),
            "hbp": int(s["stat"].get("hitByPitch", 0)),
            "sf": int(s["stat"].get("sacrificeFlies", 0)),
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


def _parse_pitcher_stats(data):
    """Parse pitcher stats from API response into dict."""
    stat_groups = data.get("stats", [])
    splits = stat_groups[0].get("splits", []) if stat_groups else []
    if not splits:
        return None
    s = splits[0]["stat"]
    ip = parse_ip(s.get("inningsPitched", 0))
    return {
        "era": s.get("era", "—"),
        "ip": s.get("inningsPitched", "0"),
    }


def fetch_pitcher_season_stats(pitcher_id, season):
    """Fetch pitcher's current + prior season stats (ERA, HR/9, BB/9)."""
    try:
        data = api_get(
            f"/people/{pitcher_id}/stats?stats=season&season={season}&group=pitching"
        )
        current = _parse_pitcher_stats(data)
        # Fetch prior year for small-sample context
        prior = None
        try:
            data_prev = api_get(
                f"/people/{pitcher_id}/stats?stats=season&season={season - 1}&group=pitching"
            )
            prior = _parse_pitcher_stats(data_prev)
        except Exception:
            pass
        return {"current": current, "prior": prior}
    except Exception as e:
        print(f"Pitcher stats fetch failed ({pitcher_id}): {e}", file=sys.stderr)
        return None


def format_pitcher_stats(stats):
    """Format pitcher stats dict into display string (prior + current)."""
    if not stats:
        return ""
    parts = []
    prior = stats.get("prior")
    current = stats.get("current")
    if prior:
        parts.append(f"去年: {prior['era']} ERA, {prior['ip']} IP")
    if current:
        parts.append(f"本季: {current['era']} ERA, {current['ip']} IP")
    return " | ".join(parts)


def fetch_batter_season_stats(player_id, season):
    """Fetch batter's season hitting stats (OPS, HR/AB, BB%)."""
    try:
        data = api_get(
            f"/people/{player_id}/stats?stats=season&season={season}&group=hitting"
        )
        stat_groups = data.get("stats", [])
        splits = stat_groups[0].get("splits", []) if stat_groups else []
        if not splits:
            return None
        s = splits[0]["stat"]
        ab = int(s.get("atBats", 0))
        pa = int(s.get("plateAppearances", 0))
        hr = int(s.get("homeRuns", 0))
        bb = int(s.get("baseOnBalls", 0))
        ops = s.get("ops", "—")
        hr_ab = round(hr / ab, 3) if ab > 0 else 0
        bb_pct = round(bb / pa * 100, 1) if pa > 0 else 0
        return {"ops": ops, "hr_ab": hr_ab, "bb_pct": bb_pct, "pa": pa}
    except Exception as e:
        print(f"Batter stats fetch failed ({player_id}): {e}", file=sys.stderr)
        return None


def format_batter_stats(current, prior, proj):
    """Format batter stats: prior year + projection + current season."""
    parts = []
    if prior:
        parts.append(f"去年: {prior['ops']} OPS / {prior['hr_ab']:.3f} HR/AB / {prior['bb_pct']}% BB ({prior['pa']} PA)")
    if proj:
        parts.append(f"預測: {proj['ops']:.3f} OPS / {proj['hr_ab']:.3f} HR/AB / {proj['bb_pct']}% BB")
    if current:
        parts.append(f"本季: {current['ops']} OPS / {current['hr_ab']:.3f} HR/AB / {current['bb_pct']}% BB ({current['pa']} PA)")
    return " | ".join(parts)


def fetch_savant_statcast(year, roster_ids, player_type="batter"):
    """Fetch Statcast data (Hard-Hit%, Barrel%) from Baseball Savant CSV.

    Works for both batters and pitchers (same CSV structure).
    For pitchers, values represent "allowed" metrics.
    Returns dict: player_id → {hh_pct, barrel_pct, bbe}
    """
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/statcast"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        result = {}
        id_set = set(str(i) for i in roster_ids)
        for row in reader:
            pid = row.get("player_id", "").strip()
            if pid in id_set:
                bip = int(row.get("attempts", 0) or 0)
                result[int(pid)] = {
                    "hh_pct": float(row.get("ev95percent", 0) or 0),
                    "barrel_pct": float(row.get("brl_percent", 0) or 0),
                    "bbe": bip,
                }
        return result
    except Exception as e:
        print(f"Savant statcast fetch failed ({year}): {e}", file=sys.stderr)
        return {}


def fetch_savant_expected(year, roster_ids, player_type="batter"):
    """Fetch expected stats (xwOBA, and xERA for pitchers) from Baseball Savant CSV.

    Returns dict: player_id → {xwoba, pa} (batter) or {xwoba, xera, pa} (pitcher)
    """
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        result = {}
        id_set = set(str(i) for i in roster_ids)
        for row in reader:
            pid = row.get("player_id", "").strip()
            if pid in id_set:
                entry = {
                    "xwoba": float(row.get("est_woba", 0) or 0),
                    "pa": int(row.get("pa", 0) or 0),
                }
                if player_type == "pitcher":
                    xera = row.get("xera")
                    entry["xera"] = float(xera) if xera else 0
                result[int(pid)] = entry
        return result
    except Exception as e:
        print(f"Savant expected fetch failed ({year}): {e}", file=sys.stderr)
        return {}


def fetch_savant_for_pitchers(pitcher_ids, season):
    """Fetch Savant data for pitchers: current + prior year.

    Returns dict: player_id → {current: {hh_pct, barrel_pct, bbe, xwoba, xera},
                                prior: {...}}
    """
    result = {}
    for year in [season, season - 1]:
        label = "current" if year == season else "prior"
        sc = fetch_savant_statcast(year, pitcher_ids, player_type="pitcher")
        ex = fetch_savant_expected(year, pitcher_ids, player_type="pitcher")
        for pid in pitcher_ids:
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
                    "xera": e.get("xera", 0),
                }
    return result


def format_pitcher_savant(savant_data):
    """Format my SP's Savant stats with percentile tags."""
    if not savant_data:
        return ""
    parts = []
    for label, key in [("去年", "prior"), ("本季", "current")]:
        d = savant_data.get(key)
        if not d:
            continue
        items = []
        if d.get("xera") is not None:
            items.append(f"{d['xera']:.2f} xERA {pctile_tag(d['xera'], 'xera', 'pitcher')}")
        if d.get("xwoba") is not None:
            items.append(f"{d['xwoba']:.3f} xwOBA {pctile_tag(d['xwoba'], 'xwoba', 'pitcher')}")
        if d.get("hh_pct") is not None:
            items.append(f"{d['hh_pct']:.0f}% HH {pctile_tag(d['hh_pct'], 'hh_pct', 'pitcher')}")
        if d.get("barrel_pct") is not None:
            items.append(f"{d['barrel_pct']:.1f}% Barrel {pctile_tag(d['barrel_pct'], 'barrel_pct', 'pitcher')}")
        if d.get("bbe"):
            items.append(f"{d['bbe']} BBE")
        if items:
            parts.append(f"{label}: {' / '.join(items)}")
    return " | ".join(parts)


def format_opp_sp_savant(savant_data):
    """Format opponent SP's Savant stats with percentile tags (aligned with CLAUDE.md framework)."""
    if not savant_data:
        return ""
    d = savant_data.get("current")
    if not d or (d.get("hh_pct") is None and d.get("xera") is None):
        d = savant_data.get("prior")
    if not d:
        return ""
    items = []
    if d.get("xera") is not None:
        items.append(f"xERA {d['xera']:.2f} {pctile_tag(d['xera'], 'xera', 'pitcher')}")
    if d.get("xwoba") is not None:
        items.append(f"xwOBA {d['xwoba']:.3f} {pctile_tag(d['xwoba'], 'xwoba', 'pitcher')}")
    if d.get("hh_pct") is not None:
        items.append(f"HH% {d['hh_pct']:.0f}% {pctile_tag(d['hh_pct'], 'hh_pct', 'pitcher')}")
    if d.get("barrel_pct") is not None:
        items.append(f"Barrel% {d['barrel_pct']:.1f}% {pctile_tag(d['barrel_pct'], 'barrel_pct', 'pitcher')}")
    if d.get("bbe"):
        items.append(f"{d['bbe']} BBE")
    return " / ".join(items) if items else ""


def fetch_savant_for_roster(roster_ids, season):
    """Fetch Savant data for current + prior year, return merged dict per player."""
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


def format_savant_stats(savant_data):
    """Format batter Savant stats with percentile tags."""
    if not savant_data:
        return ""
    parts = []
    for label, key in [("去年", "prior"), ("本季", "current")]:
        d = savant_data.get(key)
        if d and (d["bbe"] > 0 or d["xwoba"] > 0):
            hh_tag = pctile_tag(d["hh_pct"], "hh_pct")
            brl_tag = pctile_tag(d["barrel_pct"], "barrel_pct")
            xw_tag = pctile_tag(d["xwoba"], "xwoba")
            parts.append(
                f"{label}: {d['hh_pct']:.0f}% HH {hh_tag} / {d['barrel_pct']:.1f}% Barrel {brl_tag}"
                f" / {d['xwoba']:.3f} xwOBA {xw_tag} ({d['bbe']} BBE)"
            )
    return " | ".join(parts)


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
        if selected_pos in ("IL", "IL+", "NA"):
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
    active_pitchers = [p for p in src if is_active(p)]

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
                # Merge static config fields (proj) into Yahoo roster data
                config_batters = {b["name"]: b for b in config["batters"]}
                for b in batters:
                    cb = config_batters.get(b["name"], {})
                    if "proj" in cb and "proj" not in b:
                        b["proj"] = cb["proj"]
        except Exception as e:
            print(f"Yahoo roster fetch failed, using config: {e}", file=sys.stderr)

    games = fetch_schedule(date_str)
    # target_date = today in ET; games on this date may be in progress
    games_in_progress = [g for g in games if g.get("game_state") == "Live"]

    # Build set of teams playing
    teams_playing = set()
    # Map: team_abbr → opponent_team_abbr
    matchup_map = {}
    # Map: team_abbr → opposing probable pitcher info
    opp_sp_map = {}
    for g in games:
        a = team_abbr(g["away_team"], season)
        h = team_abbr(g["home_team"], season)
        teams_playing.add(a)
        teams_playing.add(h)
        matchup_map[a] = h
        matchup_map[h] = a
        # Away team faces home pitcher, and vice versa
        if g.get("home_pitcher"):
            opp_sp_map[a] = {
                "name": g["home_pitcher"],
                "id": g.get("home_pitcher_id"),
            }
        if g.get("away_pitcher"):
            opp_sp_map[h] = {
                "name": g["away_pitcher"],
                "id": g.get("away_pitcher_id"),
            }

    # Fetch season stats for opposing SPs that my batters will face
    my_teams = {b["team"] for b in batters}
    opp_pitcher_ids_seen = set()
    for team in my_teams:
        sp_info = opp_sp_map.get(team)
        if sp_info and sp_info["id"] and sp_info["id"] not in opp_pitcher_ids_seen:
            opp_pitcher_ids_seen.add(sp_info["id"])
            stats = fetch_pitcher_season_stats(sp_info["id"], season)
            if stats:
                sp_info["stats"] = stats

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
                sp_starts.append({
                    "name": name,
                    "opponent": opp,
                    "info": my_sp_names[name],
                    "venue_id": g.get("venue_id"),
                    "venue_name": g.get("venue_name", ""),
                })

    # ── Pre-fetch batter stats (current + prior year) ──
    batter_stats_cache = {}
    for b in batters:
        mlb_id = b.get("mlb_id")
        if mlb_id:
            current = fetch_batter_season_stats(mlb_id, season)
            prior = fetch_batter_season_stats(mlb_id, season - 1)
            batter_stats_cache[mlb_id] = {"current": current, "prior": prior}

    # ── Pre-fetch Savant Statcast data (batters) ──
    roster_ids = [b["mlb_id"] for b in batters if b.get("mlb_id")]
    savant_cache = fetch_savant_for_roster(roster_ids, season)

    # ── Pre-fetch Savant Statcast data (pitchers: my SP + opponent SP) ──
    all_pitcher_ids = [p["mlb_id"] for p in pitchers if p.get("mlb_id")]
    opp_sp_ids = [
        sp_info["id"] for sp_info in opp_sp_map.values()
        if sp_info.get("id")
    ]
    all_pitcher_ids_set = list(set(all_pitcher_ids + opp_sp_ids))
    pitcher_savant_cache = fetch_savant_for_pitchers(all_pitcher_ids_set, season)

    # ── Section 1: Batters ──
    lines = [f"=== {date_str} ({weekday}) ===\n"]

    # Calculate bench requirement: active batters with games - 10 starting slots
    batters_with_games = sum(
        1 for b in batters
        if b["team"] in teams_playing and is_active(b)
    )
    batter_bn_needed = max(0, batters_with_games - 10)
    lines.append(f"今日 {batters_with_games} 名打者有比賽，最多需 {batter_bn_needed} 人板凳\n")

    lines.append("我的打者：")
    for b in batters:
        pos = "/".join(b["positions"])
        slot = b.get("selected_pos", b["role"])
        tag = "板凳" if b["role"] == "bench" else slot
        if b["team"] in teams_playing:
            opp = matchup_map.get(b["team"], "?")
            sp_info = opp_sp_map.get(b["team"])
            if sp_info:
                sp_label = sp_info["name"]
                st = sp_info.get("stats")
                stat_str = format_pitcher_stats(st)
                if stat_str:
                    sp_label += f" — {stat_str}"
                # Opponent SP Savant (HH%/Barrel% allowed)
                opp_sp_id = sp_info.get("id")
                opp_savant_str = format_opp_sp_savant(pitcher_savant_cache.get(opp_sp_id)) if opp_sp_id else ""
                if opp_savant_str:
                    sp_label += f" | Savant: {opp_savant_str}"
                lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → vs {opp} ({sp_label})")
            else:
                lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → vs {opp} (SP TBD)")
        else:
            lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → 休兵")
        # Batter's own stats line
        mlb_id = b.get("mlb_id")
        if mlb_id:
            bs = batter_stats_cache.get(mlb_id, {})
            proj = b.get("proj")
            batter_line = format_batter_stats(bs.get("current"), bs.get("prior"), proj)
            if batter_line:
                lines.append(f"    {batter_line}")
            savant_line = format_savant_stats(savant_cache.get(mlb_id))
            if savant_line:
                lines.append(f"    Statcast: {savant_line}")

    # ── Section 2: SP starts ──
    lines.append("\n我的 SP 明日先發：")
    if sp_starts:
        for sp in sp_starts:
            opp_team_id = config["teams"].get(sp["opponent"])
            hitting = fetch_team_hitting(opp_team_id, season) if opp_team_id else None
            # Line 1: name vs opponent
            parts = [f"  {sp['name']} ({sp['info']['team']}) vs {sp['opponent']}"]
            # Park factor
            pf_label = get_park_factor(sp.get("venue_id"))
            if pf_label:
                parts.append(pf_label)
            lines.append(" — ".join(parts))
            # Line 2: SP's own stats (prior + current)
            mlb_id = sp["info"].get("mlb_id")
            if mlb_id:
                sp_own_stats = fetch_pitcher_season_stats(mlb_id, season)
                stat_str = format_pitcher_stats(sp_own_stats)
                if stat_str:
                    lines.append(f"    {stat_str}")
                # Line 2b: SP's Savant stats (xERA, xwOBA allowed, HH%, Barrel%)
                sp_savant = pitcher_savant_cache.get(mlb_id)
                sp_savant_str = format_pitcher_savant(sp_savant)
                if sp_savant_str:
                    lines.append(f"    Savant: {sp_savant_str}")
            # Line 3: opponent hitting
            if hitting:
                lines.append(f"    對手打線 AVG {hitting['avg']} / OPS {hitting['ops']}")
            if mlb_id:
                try:
                    gamelog = fetch_pitcher_gamelog(mlb_id, season)
                    recent = gamelog[-3:] if len(gamelog) >= 3 else gamelog
                    if recent:
                        lines.append(f"    近 {len(recent)} 場：")
                        for gl in reversed(recent):
                            lines.append(
                                f"      {gl['date']} vs {team_abbr(gl['opponent'], season)}"
                                f": {gl['ip']:.1f} IP / {gl['er']} ER / {gl['k']} K"
                            )
                except Exception:
                    pass
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

    # ── Pre-fetch Yahoo scoreboard (needed for IP + H2H sections) ──
    sb = None
    if env:
        try:
            sb = fetch_yahoo_scoreboard(config, env)
        except Exception as e:
            print(f"Yahoo scoreboard fetch failed: {e}", file=sys.stderr)

    # ── Section 4: Weekly IP ──
    _, _, week_number = get_fantasy_week(target_date, config)
    min_ip = config["league"]["min_ip"]
    lines.append(f"\n本週 IP 進度（Week {week_number}）：")

    # Use Yahoo scoreboard IP (includes dropped players' contributions)
    yahoo_ip = None
    if sb:
        for cat in sb.get("categories", []):
            if cat["name"] == "IP":
                try:
                    yahoo_ip = float(cat["mine"])
                except (ValueError, TypeError):
                    pass
                break

    if yahoo_ip is not None:
        total_ip = yahoo_ip
    else:
        # Fallback: calc from game log (may miss dropped players)
        total_ip, _ = calc_weekly_ip(config, target_date, pitchers)

    # Always show per-pitcher breakdown for context
    _, ip_entries = calc_weekly_ip(config, target_date, pitchers)
    if ip_entries:
        lines.extend(ip_entries)

    if games_in_progress:
        live_teams = []
        for g in games_in_progress:
            live_teams.append(f"{team_abbr(g['away_team'], season)}@{team_abbr(g['home_team'], season)}")
        lines.append(f"  ⚠️ 比賽進行中（{', '.join(live_teams)}），以上數據非最終，IP/比率仍會變動")

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
            if cat["name"] in ("SB", "SV+H"):
                tag += "（punt）"
            lines.append(f"  {cat['name']:>6}  {cat['mine']:>8}  {cat['opp']:>8}  {tag}")
        if games_in_progress:
            lines.append(f"  ⚠️ 比賽進行中，以上數據非最終")

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

    # ── Section 8: Lineup confirmation ──
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

    # ── Section 9: Evening advice (morning mode only) ──
    if morning:
        _, _, wk = get_fantasy_week(target_date, config)
        evening_advice = fetch_evening_advice(target_date, wk)
        if evening_advice:
            lines.append("\n=== 速報建議（前一晚） ===")
            lines.append(evening_advice)
        else:
            lines.append("\n（速報未找到，請獨立判斷）")

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
        # target_date = ET 的「今天」。
        # 速報 TW 22:15 = ET 10:15 → 比賽還沒開始，用來預覽今日 matchup
        # 最終報 TW 05:00 = ET 17:00（前一天）→ 比賽可能進行中，用來確認結果
        # 兩者的 target_date 都是「ET 當天」，不是「明天」。
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

    if args.no_send:
        return

    # Archive to GitHub Issue
    _, _, week_number = get_fantasy_week(target_date, config)
    save_github_issue(target_date, week_number, data_summary, advice, morning=args.morning)

    print("\nSending to Telegram...", file=sys.stderr)
    ok = send_telegram(advice, env)
    if ok:
        print("Sent.", file=sys.stderr)
    else:
        print("Failed to send.", file=sys.stderr)


def fetch_evening_advice(target_date, week_number):
    """Fetch the evening report's advice from GitHub Issues for the same date."""
    repo = "huansbox/mlb-fantasy"
    title_query = f"[速報] Daily Report — {target_date}"
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", repo,
             "--label", f"week-{week_number}",
             "--search", title_query,
             "--json", "body", "--limit", "1"],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        if result.returncode != 0:
            return None
        issues = json.loads(result.stdout)
        if not issues:
            return None
        body = issues[0]["body"]
        # Extract advice between "## Claude Advice" and "---"
        marker = "## Claude Advice"
        start = body.find(marker)
        if start == -1:
            return None
        start += len(marker)
        end = body.find("\n---\n", start)
        return body[start:end].strip() if end != -1 else body[start:].strip()
    except Exception as e:
        print(f"Failed to fetch evening advice: {e}", file=sys.stderr)
        return None


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
    label = f"week-{week_number}"
    try:
        # Ensure label exists (ignore failure if already exists)
        subprocess.run(
            ["gh", "label", "create", label, "--repo", repo,
             "--color", "0E8A16", "--force"],
            capture_output=True, text=True, timeout=10,
        )
        result = subprocess.run(
            ["gh", "issue", "create",
             "--repo", repo,
             "--title", title,
             "--body", body,
             "--label", label],
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
