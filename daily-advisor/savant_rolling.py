#!/usr/bin/env python3
"""Fetch rolling-window Savant data for given players.

Uses Baseball Savant statcast_search/csv endpoint (pitch-level raw data,
aggregated locally to PA/BBE/xwOBA/HH%/Barrel% metrics).

Runs daily via cron (TW 12:00). Writes savant_rolling.json in same dir.
Window: last N calendar days ending on today (default 14d).
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


def _fetch_player_pitches(mlb_id, start_date, end_date):
    """Fetch pitch-level CSV for one player.

    Args:
        mlb_id: int — MLB player ID
        start_date: str "YYYY-MM-DD" (inclusive)
        end_date: str "YYYY-MM-DD" (inclusive)

    Returns:
        list of CSV row dicts (empty on error)
    """
    year = end_date[:4]
    params = {
        "all": "true",
        "hfSea": f"{year}|",
        "player_type": "batter",
        "batters_lookup[]": str(mlb_id),
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
        print(f"Fetch failed for player {mlb_id}: {e}", file=sys.stderr)
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


def _aggregate_pitches(rows):
    """Aggregate pitch-level rows into player metrics.

    Args:
        rows: list[dict] — CSV rows from _fetch_player_pitches

    Returns:
        dict — {xwoba, barrel_pct, hh_pct, bbe, pa} or {} if no usable data
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

    return {
        "xwoba": round(xwoba, 3),
        "barrel_pct": round(barrel_count / bbe_count * 100, 1),
        "hh_pct": round(hh_count / bbe_count * 100, 1),
        "bbe": bbe_count,
        "pa": pa,
    }


def fetch_savant_rolling(player_ids, end_date, window_days=14):
    """Fetch rolling Savant data for given players.

    Args:
        player_ids: list[int] — MLB player IDs
        end_date: str "YYYY-MM-DD"
        window_days: int — lookback window (default 14)

    Returns:
        dict[int, dict] — {player_id: {xwoba, barrel_pct, hh_pct, bbe, pa}}
        Players with no data in window are omitted.
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=window_days)
    start_str = start_dt.strftime("%Y-%m-%d")

    result = {}
    for pid in player_ids:
        rows = _fetch_player_pitches(pid, start_str, end_date)
        metrics = _aggregate_pitches(rows)
        if metrics:
            result[pid] = metrics
    return result
