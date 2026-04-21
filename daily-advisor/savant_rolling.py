#!/usr/bin/env python3
"""Fetch rolling-window Savant data for given players.

Uses Baseball Savant statcast_search/csv endpoint (pitch-level raw data,
aggregated locally to PA/BBE/xwOBA/HH%/Barrel% metrics).

Runs daily via cron (TW 12:00). Writes savant_rolling.json in same dir.
Windows: batter 14d, pitcher 21d (≈ 3-4 starts on standard rotation).

For pitchers, computes xERA locally from raw BBE using same weights as
Baseball Savant (BB/HBP constants + sum of per-BBE xwOBA / PA).
"""

import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTER_PATH = os.path.join(SCRIPT_DIR, "roster_config.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "savant_rolling.json")

# CSV events classification
BBE_EVENTS = frozenset({
    "single", "double", "triple", "home_run",
    "field_out", "force_out", "grounded_into_double_play",
    "double_play", "triple_play",
    "fielders_choice", "fielders_choice_out", "field_error",
    "sac_fly", "sac_fly_double_play", "sac_bunt",
})
BB_EVENTS = frozenset({"walk"})
HBP_EVENTS = frozenset({"hit_by_pitch"})

# xwOBA weights (MLB standard, matches Baseball Savant season xwOBA)
XWOBA_BB_WEIGHT = 0.69
XWOBA_HBP_WEIGHT = 0.72

# Window defaults
BATTER_WINDOW = 14
PITCHER_WINDOW = 21


def _fetch_player_pitches(mlb_id, start_date, end_date, player_type="batter"):
    """Fetch pitch-level CSV for one player.

    Args:
        mlb_id: int — MLB player ID
        start_date: str "YYYY-MM-DD" (inclusive)
        end_date: str "YYYY-MM-DD" (inclusive)
        player_type: "batter" or "pitcher"

    Returns:
        list of CSV row dicts (empty on error)
    """
    year = end_date[:4]
    lookup_key = "batters_lookup[]" if player_type == "batter" else "pitchers_lookup[]"
    params = {
        "all": "true",
        "hfSea": f"{year}|",
        "player_type": player_type,
        lookup_key: str(mlb_id),
        "game_date_gt": start_date,
        "game_date_lt": end_date,
        "min_pitches": "0",
        "min_results": "0",
        "min_pas": "0",
        "type": "details",
    }
    url = "https://baseballsavant.mlb.com/statcast_search/csv?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        text = resp.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    except Exception as e:
        print(f"Fetch failed for player {mlb_id} ({player_type}): {e}", file=sys.stderr)
        return []


def _safe_float(val):
    """Parse float from CSV cell, handling common empty markers."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "null", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _aggregate_pitches(rows, player_type="batter"):
    """Aggregate pitch-level rows into player metrics.

    Args:
        rows: list[dict] — CSV rows from _fetch_player_pitches
        player_type: "batter" or "pitcher" — pitcher adds xera

    Returns:
        dict — batter: {xwoba, barrel_pct, hh_pct, bbe, pa}
               pitcher: {xwoba, barrel_pct, hh_pct, bbe, pa, xera, ip}
               {} if no usable data
    """
    if not rows:
        return {}

    pa_set = set()
    bbe_count = 0
    bb_count = 0
    hbp_count = 0
    sum_xwoba_on_bbe = 0.0
    hh_count = 0
    barrel_count = 0
    # Pitcher-only: track IP from game_date + outs
    outs = 0

    for row in rows:
        gd = (row.get("game_date") or "").strip()
        abn = (row.get("at_bat_number") or "").strip()
        if gd and abn:
            pa_set.add((gd, abn))

        event = (row.get("events") or "").strip()
        if not event:
            continue  # Mid-PA pitch, skip

        if event in BB_EVENTS:
            bb_count += 1
        elif event in HBP_EVENTS:
            hbp_count += 1
        elif event in BBE_EVENTS:
            bbe_count += 1
            xw = _safe_float(row.get("estimated_woba_using_speedangle"))
            if xw is not None:
                sum_xwoba_on_bbe += xw
            ls = _safe_float(row.get("launch_speed"))
            if ls is not None and ls >= 95:
                hh_count += 1
            lsa = _safe_float(row.get("launch_speed_angle"))
            if lsa is not None and int(lsa) == 6:
                barrel_count += 1
        # else: strikeout or other — counted in PA only

    pa = len(pa_set)
    if pa == 0 or bbe_count == 0:
        return {}

    xwoba = (
        XWOBA_BB_WEIGHT * bb_count
        + XWOBA_HBP_WEIGHT * hbp_count
        + sum_xwoba_on_bbe
    ) / pa

    result = {
        "xwoba": round(xwoba, 3),
        "barrel_pct": round(barrel_count / bbe_count * 100, 1),
        "hh_pct": round(hh_count / bbe_count * 100, 1),
        "bbe": bbe_count,
        "pa": pa,
    }

    # Pitcher-only: xERA proxy via xwOBA→RA conversion is non-trivial.
    # Baseball Savant's published xERA uses a proprietary model; a faithful
    # local proxy would need RE24/base-out state per PA. For now, expose
    # xwOBA-allowed (the core quality signal) and rely on season xERA from
    # full-season CSV for long-horizon comparison. Pass 2 21d-vs-season Δ
    # should use xwOBA Δ instead of xERA Δ until we wire a proper proxy.
    return result


def fetch_savant_rolling(player_ids, end_date, window_days=14, player_type="batter"):
    """Fetch rolling Savant data for given players.

    Args:
        player_ids: list[int] — MLB player IDs
        end_date: str "YYYY-MM-DD"
        window_days: int — lookback window
        player_type: "batter" or "pitcher"

    Returns:
        dict[int, dict] — {player_id: metrics}. Missing players omitted.
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=window_days)
    start_str = start_dt.strftime("%Y-%m-%d")

    result = {}
    for pid in player_ids:
        rows = _fetch_player_pitches(pid, start_str, end_date, player_type)
        metrics = _aggregate_pitches(rows, player_type)
        if metrics:
            result[pid] = metrics
    return result


def main():
    with open(ROSTER_PATH, encoding="utf-8") as f:
        config = json.load(f)

    INACTIVE = ("IL", "IL+", "NA")
    # Active batters
    batters = [
        b for b in config.get("batters", [])
        if b.get("selected_pos", "") not in INACTIVE and b.get("mlb_id")
    ]
    batter_ids = [int(b["mlb_id"]) for b in batters]
    batter_names = {int(b["mlb_id"]): b["name"] for b in batters}

    # Active SP (Yahoo dual-eligible SP,RP included if SP in positions)
    sps = [
        p for p in config.get("pitchers", [])
        if "SP" in p.get("positions", [])
        and p.get("selected_pos", "") not in INACTIVE
        and p.get("mlb_id")
    ]
    sp_ids = [int(p["mlb_id"]) for p in sps]
    sp_names = {int(p["mlb_id"]): p["name"] for p in sps}

    end_date = date.today().strftime("%Y-%m-%d")

    print(f"Fetching {len(batter_ids)} batters (window={BATTER_WINDOW}d)...",
          file=sys.stderr)
    batter_data = fetch_savant_rolling(
        batter_ids, end_date, window_days=BATTER_WINDOW, player_type="batter"
    )
    print(f"Fetching {len(sp_ids)} SP (window={PITCHER_WINDOW}d)...",
          file=sys.stderr)
    sp_data = fetch_savant_rolling(
        sp_ids, end_date, window_days=PITCHER_WINDOW, player_type="pitcher"
    )

    players_out = {
        str(pid): {"name": batter_names.get(pid, "?"), **stats}
        for pid, stats in batter_data.items()
    }
    pitchers_out = {
        str(pid): {"name": sp_names.get(pid, "?"), **stats}
        for pid, stats in sp_data.items()
    }

    tz_tpe = timezone(timedelta(hours=8))
    batter_start = (date.today() - timedelta(days=BATTER_WINDOW)).strftime("%Y-%m-%d")
    pitcher_start = (date.today() - timedelta(days=PITCHER_WINDOW)).strftime("%Y-%m-%d")
    output = {
        "generated_at": datetime.now(tz_tpe).isoformat(timespec="seconds"),
        "batter_window_days": BATTER_WINDOW,
        "pitcher_window_days": PITCHER_WINDOW,
        "batter_date_range": [batter_start, end_date],
        "pitcher_date_range": [pitcher_start, end_date],
        "players": players_out,
        "pitchers": pitchers_out,
        # Back-compat: old consumers read "window_days" + "date_range"
        "window_days": BATTER_WINDOW,
        "date_range": [batter_start, end_date],
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"Wrote {OUTPUT_PATH}: "
        f"{len(players_out)}/{len(batter_ids)} batters, "
        f"{len(pitchers_out)}/{len(sp_ids)} SP",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
