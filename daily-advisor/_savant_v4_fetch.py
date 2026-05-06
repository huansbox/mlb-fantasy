"""Shared SP v4 5-slot fetcher.

Single-pitcher Savant + MLB API fetcher for v4 framework metrics
(IP/GS / Whiff% / BB/9 / GB% / xwOBACON). Used by yahoo_query.py savant CLI,
daily_advisor.py opposing/own SP enrichment, and fa_scan.py FA prior_stats
backfill.

Each metric independently degrades to None if its source fails — caller
displays '—' for missing fields rather than aborting. Savant batted-ball
endpoint ignores the year query param and always returns current-season
data; for past years we skip that fetch (gb_pct / bbe stay None).
"""

import csv
import datetime
import io
import json
import sys
import urllib.request

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def _fetch_savant_csv(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode("utf-8-sig")


def _safe_float(v, default=None):
    if v in (None, "", "null", "None", "-", "--", "-.--"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _ip_str_to_real(ip_str) -> float:
    """Convert MLB IP notation (5.1 = 5⅓, 5.2 = 5⅔) to real innings."""
    v = _safe_float(ip_str, 0.0) or 0.0
    return int(v) + (v - int(v)) * 10 / 3


def fetch_pitchers_custom_bulk(year: int) -> dict:
    """League-wide pitcher xwOBACON / xERA / xwOBA-allowed / ERA from Savant custom CSV.

    Returns {pid: {xwoba_allowed, xwobacon, xera, era}}.
    """
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=pitcher&filter=&min=1"
        "&selections=pa,bip,xwoba,xwobacon,xera,era&csv=true"
    )
    out = {}
    try:
        text = _fetch_savant_csv(url)
        for row in csv.DictReader(io.StringIO(text)):
            pid = int(_safe_float(row.get("player_id"), 0) or 0)
            if not pid:
                continue
            out[pid] = {
                "xwoba_allowed": _safe_float(row.get("xwoba")),
                "xwobacon": _safe_float(row.get("xwobacon")),
                "xera": _safe_float(row.get("xera")),
                "era": _safe_float(row.get("era")),
            }
    except Exception as e:
        print(f"  Savant custom bulk error ({year}): {e}", file=sys.stderr)
    return out


def fetch_pitchers_batted_ball_bulk(year: int) -> dict:
    """League-wide pitcher GB% / BBE from Savant batted-ball CSV.

    Returns {pid: {gb_pct, bbe}}. Endpoint ignores year (always returns
    current-season data); caller decides whether to use for past years.
    """
    url = (
        "https://baseballsavant.mlb.com/leaderboard/batted-ball"
        f"?year={year}&type=pitcher&min=1&csv=true"
    )
    out = {}
    try:
        text = _fetch_savant_csv(url)
        for row in csv.DictReader(io.StringIO(text)):
            pid = int(_safe_float(row.get("id"), 0) or 0)
            if not pid:
                continue
            bbe = int(_safe_float(row.get("bbe"), 0) or 0)
            gb_rate = _safe_float(row.get("gb_rate"))
            out[pid] = {
                "bbe": bbe,
                "gb_pct": gb_rate * 100 if gb_rate is not None else None,
            }
    except Exception as e:
        print(f"  Savant batted-ball bulk error ({year}): {e}", file=sys.stderr)
    return out


def fetch_pitchers_arsenal_whiff_bulk(year: int) -> dict:
    """League-wide pitch-weighted Whiff% from Savant arsenal CSV.

    Returns {pid: {whiff_pct, arsenal_pitches}}. Aggregates multiple pitch-type
    rows per pitcher into a single pitches-weighted average.
    """
    url = (
        "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
        f"?type=pitcher&year={year}&min=1&csv=true"
    )
    agg = {}
    try:
        text = _fetch_savant_csv(url)
        for row in csv.DictReader(io.StringIO(text)):
            pid = int(_safe_float(row.get("player_id"), 0) or 0)
            if not pid:
                continue
            pitches = int(_safe_float(row.get("pitches"), 0) or 0)
            whiff = _safe_float(row.get("whiff_percent"))
            if not pitches or whiff is None:
                continue
            if pid not in agg:
                agg[pid] = {"pitches": 0, "wsum": 0.0}
            agg[pid]["pitches"] += pitches
            agg[pid]["wsum"] += whiff * pitches
    except Exception as e:
        print(f"  Savant arsenal bulk error ({year}): {e}", file=sys.stderr)
    return {
        pid: {
            "whiff_pct": a["wsum"] / a["pitches"],
            "arsenal_pitches": a["pitches"],
        }
        for pid, a in agg.items()
        if a["pitches"] > 0
    }


def fetch_pitcher_v4(pid: int, year: int) -> dict:
    """Fetch SP v4 5-slot for a single pitcher.

    Returns dict with v4 fields (ip_gs / whiff_pct / bb9 / gb_pct / xwobacon)
    + context (g / gs / ip / bbe / xera / era). Missing fields stay None.
    """
    current_year = datetime.datetime.now().year

    out = {
        "ip_gs": None, "whiff_pct": None, "bb9": None,
        "gb_pct": None, "xwobacon": None,
        "g": 0, "gs": 0, "ip": 0.0, "bbe": None,
        "xera": None, "era": None,
    }

    # 1. Savant custom — xwOBACON, xERA (year-aware)
    try:
        url = (
            "https://baseballsavant.mlb.com/leaderboard/custom"
            f"?year={year}&type=pitcher&filter=&min=1"
            "&selections=pa,bip,xwoba,xwobacon,xera,era&csv=true"
        )
        text = _fetch_savant_csv(url)
        for row in csv.DictReader(io.StringIO(text)):
            if int(row.get("player_id", 0) or 0) == pid:
                out["xwobacon"] = _safe_float(row.get("xwobacon"))
                out["xera"] = _safe_float(row.get("xera"))
                break
    except Exception as e:
        print(f"  Savant custom error ({year}): {e}", file=sys.stderr)

    # 2. Savant batted-ball — GB%, BBE (current-year only; endpoint ignores year)
    if year == current_year:
        try:
            url = (
                "https://baseballsavant.mlb.com/leaderboard/batted-ball"
                f"?year={year}&type=pitcher&min=1&csv=true"
            )
            text = _fetch_savant_csv(url)
            for row in csv.DictReader(io.StringIO(text)):
                if int(row.get("id", 0) or 0) == pid:
                    gb_rate = _safe_float(row.get("gb_rate"))
                    out["gb_pct"] = gb_rate * 100 if gb_rate is not None else None
                    out["bbe"] = int(_safe_float(row.get("bbe"), 0) or 0)
                    break
        except Exception as e:
            print(f"  Savant batted-ball error ({year}): {e}", file=sys.stderr)

    # 3. Savant pitch-arsenal — Whiff% weighted by pitch usage
    try:
        url = (
            "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
            f"?type=pitcher&year={year}&min=1&csv=true"
        )
        text = _fetch_savant_csv(url)
        wsum = 0.0
        pitches_total = 0
        for row in csv.DictReader(io.StringIO(text)):
            if int(row.get("player_id", 0) or 0) == pid:
                p = int(_safe_float(row.get("pitches"), 0) or 0)
                w = _safe_float(row.get("whiff_percent"))
                if p and w is not None:
                    pitches_total += p
                    wsum += w * p
        if pitches_total > 0:
            out["whiff_pct"] = wsum / pitches_total
    except Exception as e:
        print(f"  Savant pitch-arsenal error ({year}): {e}", file=sys.stderr)

    # 4. MLB API season stats — G, GS, IP, BB, ERA
    try:
        url = (
            f"{MLB_API_BASE}/people?personIds={pid}"
            f"&hydrate=stats(group=[pitching],type=[season],season={year})"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        for person in data.get("people", []):
            for sg in person.get("stats", []):
                splits = sg.get("splits", [])
                if not splits:
                    continue
                stat = splits[0].get("stat", {})
                out["g"] = int(stat.get("gamesPlayed", 0) or 0)
                out["gs"] = int(stat.get("gamesStarted", 0) or 0)
                ip_real = _ip_str_to_real(stat.get("inningsPitched", "0"))
                out["ip"] = ip_real
                bb = int(_safe_float(stat.get("baseOnBalls"), 0) or 0)
                if ip_real:
                    out["bb9"] = 9 * bb / ip_real
                out["era"] = _safe_float(stat.get("era"))
                break
    except Exception as e:
        print(f"  MLB season stats error ({year}): {e}", file=sys.stderr)

    # 5. IP/GS from per-start game log (excludes relief outings)
    if out["gs"] >= 1:
        try:
            url = (
                f"{MLB_API_BASE}/people/{pid}/stats"
                f"?stats=gameLog&season={year}&group=pitching"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
            splits = (data.get("stats") or [{}])[0].get("splits", []) or []
            starts = [s for s in splits
                      if int(s.get("stat", {}).get("gamesStarted", 0)) == 1]
            if starts:
                total_ip = sum(_ip_str_to_real(s["stat"].get("inningsPitched", "0"))
                               for s in starts)
                out["ip_gs"] = round(total_ip / len(starts), 2)
        except Exception as e:
            print(f"  Game log error ({year}): {e}", file=sys.stderr)

    return out
