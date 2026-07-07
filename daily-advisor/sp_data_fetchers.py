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
    """Returns {pid: {g, gs, ip, ip_gs, bb9, k9, era, whip, k,
                      saves, holds, blown_saves, save_opportunities}}.

    Batches 50 per call via /people?personIds=...

    saves/holds/blown_saves/save_opportunities support the RP-SV+H scan
    (rp_svh_scan.py): saves+holds is the realized SV+H production, and
    blown_saves pairs with save_opportunities for the LLM role-safety read.
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
                        # batters faced — K-BB% denominator (050 small-sample ladder)
                        "bf": safe_int(stat.get("battersFaced"), 0),
                        "ip_gs": ip_gs,
                        "bb9": 9 * bb / ip_real if ip_real else 0,
                        "k9": 9 * k / ip_real if ip_real else 0,
                        "era": safe_float(stat.get("era")),
                        "whip": safe_float(stat.get("whip")),
                        "saves": safe_int(stat.get("saves"), 0),
                        "holds": safe_int(stat.get("holds"), 0),
                        "blown_saves": safe_int(stat.get("blownSaves"), 0),
                        "save_opportunities": safe_int(
                            stat.get("saveOpportunities"), 0),
                    }
                    break
        except Exception as e:
            print(f"[warn] MLB API batch {i} failed: {e}", file=sys.stderr)
    return out


# ── 318b B6 fetchers (046 start projection / 048 swap context) ──

def fetch_gamelog_starts(pid: int, year: int) -> dict | None:
    """One game-log call → the 046/048 per-pitcher context: start dates for
    the cadence walk, the team as of the last start (schedule lookup key), and
    the QS rate for the per-start production vector.

    Returns {start_dates: [ISO...] (sorted), team_id, qs_rate} or None when
    the pitcher has no starts / the API fails (best-effort callers skip)."""
    from mlb_query import is_quality_start, parse_ip

    url = (f"{MLB_API}/people/{pid}/stats"
           f"?stats=gameLog&group=pitching&season={year}")
    try:
        data = json.loads(fetch_url(url, timeout=30))
        splits = (data.get("stats") or [{}])[0].get("splits", [])
    except Exception:
        return None
    dates, team_id, qs = [], None, 0
    for s in splits:
        stat = s.get("stat", {})
        if safe_int(stat.get("gamesStarted"), 0) < 1:
            continue
        dates.append(s.get("date"))
        team_id = (s.get("team") or {}).get("id") or team_id
        try:
            ip_dec = parse_ip(str(stat.get("inningsPitched", "0.0")))
        except (ValueError, AttributeError):
            ip_dec = 0.0
        if is_quality_start(ip_dec, safe_int(stat.get("earnedRuns"), 0)):
            qs += 1
    if not dates:
        return None
    dates.sort()
    return {"start_dates": dates, "team_id": team_id,
            "qs_rate": qs / len(dates)}


def fetch_week_schedule(start_date: str, end_date: str) -> dict:
    """ONE league schedule call for [start_date, end_date] with probables.

    Returns {team_days: {team_id: [ISO...]}, probables: {pid: [ISO...]},
    horizon_end: ISO|None} — horizon_end is the last date with ANY published
    probable, feeding the projector's visibly-skipped-turn suppression."""
    url = (f"{MLB_API}/schedule?sportId=1&startDate={start_date}"
           f"&endDate={end_date}&hydrate=probablePitcher")
    data = json.loads(fetch_url(url, timeout=30))
    team_days: dict[int, list] = {}
    probables: dict[int, list] = {}
    horizon_end = None
    for day in data.get("dates", []):
        d = day.get("date")
        for g in day.get("games", []):
            for side in ("home", "away"):
                t = g.get("teams", {}).get(side, {})
                tid = (t.get("team") or {}).get("id")
                if tid:
                    days = team_days.setdefault(tid, [])
                    if d not in days:
                        days.append(d)
                pp = (t.get("probablePitcher") or {}).get("id")
                if pp:
                    probables.setdefault(pp, []).append(d)
                    if horizon_end is None or d > horizon_end:
                        horizon_end = d
    return {"team_days": team_days, "probables": probables,
            "horizon_end": horizon_end}


def fetch_standings_winpct(season: int) -> dict:
    """{team_id: win_pct} from league standings — the W coefficient input for
    the 048 per-start vector."""
    url = f"{MLB_API}/standings?leagueId=103,104&season={season}"
    data = json.loads(fetch_url(url, timeout=30))
    out = {}
    for rec in data.get("records", []):
        for tr in rec.get("teamRecords", []):
            tid = (tr.get("team") or {}).get("id")
            pct = safe_float(tr.get("winningPercentage"))
            if tid and pct is not None:
                out[tid] = pct
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
            # raw counting for the 050 K-BB% small-sample ladder
            "k": m.get("k"),
            "bb": m.get("bb"),
            "bf": m.get("bf"),
        }
    return merged
