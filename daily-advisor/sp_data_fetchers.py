"""SP v4 Savant + MLB Stats API fetcher module.

Provides ``assemble_data(pitcher_ids, year)`` and the four underlying fetchers
(``fetch_savant_custom`` / ``fetch_savant_batted_ball`` /
``fetch_savant_arsenal_whiff`` / ``fetch_mlb_season_stats``) used by the Phase 6
SP pipeline (``_phase6_sp.py``) and the one-shot backfill script
(``backfill_prior_stats_v4.py``).

History: previously named ``fa_scan_v4.py`` and shipped with an ad-hoc CLI
front-end. The CLI was retired in B1 cutover (issue 004) once Phase 6 became
the production decision layer; the fetcher functions stayed because they are
the canonical Savant URL definitions for v4 5-slot data (xwOBACON / GB% /
Whiff% / IP/GS / BB/9).

See docs/sp-framework-v4-balanced.md for framework rationale.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request


MLB_API = "https://statsapi.mlb.com/api/v1"
YEAR_DEFAULT = 2026


def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8-sig")


def safe_float(v, default=None):
    if v in (None, "", "null", "None", "-", "--", "-.--"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def safe_int(v, default=0):
    if v in (None, "", "null", "None"):
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _ip_str_to_real(ip_str) -> float:
    """Convert MLB IP notation (5.1 = 5⅓, 5.2 = 5⅔) to real innings."""
    v = safe_float(ip_str, 0.0)
    return int(v) + (v - int(v)) * 10 / 3


def _ip_per_gs_gamelog(pid: int, year: int):
    """IP/GS from per-start game log only (excludes relief outings).

    MLB API season stats's ip_gs is naive (total_ip / gs) which inflates for
    swingmen who relieve between starts. This walks the game log and only
    counts splits where gamesStarted=1.

    Returns float or None. None on API failure or no starts; downstream
    metric_to_score handles None as score 0 (fail-loud, visible in breakdown).
    """
    url = f"{MLB_API}/people/{pid}/stats?stats=gameLog&season={year}&group=pitching"
    try:
        data = json.loads(fetch_url(url, timeout=20))
    except Exception:
        return None
    splits = (data.get("stats") or [{}])[0].get("splits", []) or []
    starts = [s for s in splits if int(s.get("stat", {}).get("gamesStarted", 0)) == 1]
    if not starts:
        return None
    total_ip = sum(_ip_str_to_real(s["stat"].get("inningsPitched", "0"))
                   for s in starts)
    return round(total_ip / len(starts), 2)


# ── Data fetch ──

def fetch_savant_custom(year: int) -> dict:
    """Returns {pid: {xwoba_allowed, xwobacon, xera, era}}."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=pitcher&filter=&min=1"
        "&selections=pa,bip,xwoba,xwobacon,xera,era&csv=true"
    )
    text = fetch_url(url)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        out[pid] = {
            "xwoba_allowed": safe_float(row.get("xwoba")),
            "xwobacon": safe_float(row.get("xwobacon")),
            "xera": safe_float(row.get("xera")),
            "era": safe_float(row.get("era")),
        }
    return out


def fetch_savant_batted_ball(year: int) -> dict:
    """Returns {pid: {bbe, gb_pct}}."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/batted-ball"
        f"?year={year}&type=pitcher&min=1&csv=true"
    )
    text = fetch_url(url)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("id"), 0)
        if not pid:
            continue
        bbe = safe_int(row.get("bbe"), 0)
        gb_rate = safe_float(row.get("gb_rate"))
        out[pid] = {
            "bbe": bbe,
            "gb_pct": gb_rate * 100 if gb_rate is not None else None,
        }
    return out


def fetch_savant_arsenal_whiff(year: int) -> dict:
    """Returns {pid: {whiff_pct, arsenal_pitches}} weighted by pitch usage."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
        f"?type=pitcher&year={year}&min=1&csv=true"
    )
    text = fetch_url(url)
    agg = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        pitches = safe_int(row.get("pitches"), 0)
        whiff = safe_float(row.get("whiff_percent"))
        if not pitches or whiff is None:
            continue
        if pid not in agg:
            agg[pid] = {"pitches": 0, "wsum": 0.0}
        agg[pid]["pitches"] += pitches
        agg[pid]["wsum"] += whiff * pitches
    return {
        pid: {
            "whiff_pct": a["wsum"] / a["pitches"],
            "arsenal_pitches": a["pitches"],
        }
        for pid, a in agg.items()
        if a["pitches"] > 0
    }


def fetch_mlb_season_stats(pitcher_ids, year: int) -> dict:
    """Returns {pid: {g, gs, ip, ip_gs, bb9, era, whip, qs, k}}.

    Batches 50 per call via /people?personIds=...
    """
    out = {}
    ids = list(pitcher_ids)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        id_str = ",".join(str(x) for x in batch)
        url = (
            f"{MLB_API}/people?personIds={id_str}"
            f"&hydrate=stats(group=[pitching],type=[season],season={year})"
        )
        try:
            data = json.loads(fetch_url(url, timeout=30))
            for person in data.get("people", []):
                pid = person.get("id")
                for sg in person.get("stats", []):
                    splits = sg.get("splits", [])
                    if not splits:
                        continue
                    stat = splits[0].get("stat", {})
                    g = int(stat.get("gamesPlayed", 0))
                    gs = int(stat.get("gamesStarted", 0))
                    ip_str = stat.get("inningsPitched", "0.0")
                    ip_real = _ip_str_to_real(ip_str)
                    bb = safe_int(stat.get("baseOnBalls"), 0)
                    k = safe_int(stat.get("strikeOuts"), 0)
                    # ip_gs from per-start game log (correct for swingmen);
                    # falls through to None if API fails or no starts.
                    ip_gs = _ip_per_gs_gamelog(pid, year) if gs else None
                    out[pid] = {
                        "g": g, "gs": gs, "ip": ip_real, "bb": bb, "k": k,
                        "ip_gs": ip_gs,
                        "bb9": 9 * bb / ip_real if ip_real else 0,
                        "k9": 9 * k / ip_real if ip_real else 0,
                        "era": safe_float(stat.get("era")),
                        "whip": safe_float(stat.get("whip")),
                    }
                    break
        except Exception as e:
            print(f"[warn] MLB API batch {i} failed: {e}", file=sys.stderr)
    return out


def assemble_data(pitcher_ids, year: int) -> dict:
    """Pull all data + merge into per-pitcher dict with v4 fields."""
    print(f"Fetching Savant custom (xwOBA/xwOBACON/xERA)...", file=sys.stderr)
    custom = fetch_savant_custom(year)
    print(f"Fetching Savant batted-ball (GB%)...", file=sys.stderr)
    bb_ball = fetch_savant_batted_ball(year)
    print(f"Fetching Savant pitch-arsenal (Whiff%)...", file=sys.stderr)
    arsenal = fetch_savant_arsenal_whiff(year)
    print(f"Fetching MLB Stats API season stats...", file=sys.stderr)
    mlb = fetch_mlb_season_stats(pitcher_ids, year)

    merged = {}
    for pid in pitcher_ids:
        c = custom.get(pid, {})
        b = bb_ball.get(pid, {})
        a = arsenal.get(pid, {})
        m = mlb.get(pid, {})
        merged[pid] = {
            # v4 Sum inputs
            "ip_gs": m.get("ip_gs"),
            "whiff_pct": a.get("whiff_pct"),
            "bb9": m.get("bb9"),
            "gb_pct": b.get("gb_pct"),
            "xwobacon": c.get("xwobacon"),
            # Gate + luck + context
            "g": m.get("g", 0),
            "gs": m.get("gs", 0),
            "ip": m.get("ip", 0),
            "bbe": b.get("bbe", 0),
            "xera": c.get("xera"),
            # ERA: MLB API is authoritative; Savant custom's era column is empty
            # when passed through `selections` params
            "era": m.get("era"),
            "xwoba_allowed": c.get("xwoba_allowed"),
            "k9": m.get("k9"),
            "whip": m.get("whip"),
            "arsenal_pitches": a.get("arsenal_pitches", 0),
        }
    return merged
