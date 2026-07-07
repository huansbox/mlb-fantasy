"""SP micro-fields — CSW 21d / velocity deltas / K-BB% ladder (issue 050 / #329).

Three leading-indicator fields for the SP payload, weeks ahead of the result
stats they anticipate:
  - CSW% 21d (called + swinging strikes / pitches) — the K precursor. Season
    CSW is NOT obtainable (the Savant custom leaderboard accepts a
    csw_percent selection but returns an empty column via CSV — verified
    2026-07-07), so this stays a 21d LEVEL, context-only, never in Sum.
  - Fastball velocity deltas — 21d vs season and YoY, breakout + injury
    precursor in both directions. Season per-pitch-type speeds come from the
    /leaderboard/pitch-arsenals CSV (ff_avg_speed, si_avg_speed, ...), the
    same pitch-type definition as the rolling velo_fb, so deltas compare like
    with like.
  - K-BB% small-sample ladder — the BBE<30 dead zone stops being a blanket
    abstention: K-BB% per batter faced + a stabilization tier (K% is
    research-consensus stable around ~70 BF).

Layers mirror batter_discipline: this module = bulk Savant fetch + pure
compute + tag, stdlib only, no project imports, no Yahoo. The _phase6_sp
wiring joins per-entry rolling/season data and attaches the fields, validated
on the VPS (段③ A/B).
"""

from __future__ import annotations

import csv
import io
import urllib.request

# A fastball move of ±1.0 mph between windows is the conventional
# injury/breakout alarm line; smaller moves are day-to-day noise.
VELO_DELTA_SIG = 1.0

# K% stabilizes around ~70 BF (research consensus); below ~40 BF even the
# direction is unreliable.
BF_STABLE = 70
BF_EARLY = 40

# The rolling velo_fb key ("FF"/"SI"/"FC") ↔ pitch-arsenals CSV column.
_ARSENAL_SPEED_COLS = {
    "FF": "ff_avg_speed", "SI": "si_avg_speed", "FC": "fc_avg_speed",
}


# ── network (thin) ──

def fetch_season_velo_bulk(year: int) -> dict[int, dict]:
    """One league-bulk pitch-arsenals CSV → {pid: {"FF": mph, "SI": mph,
    "FC": mph}} (fastball types only — the micro-field tracks the primary
    fastball)."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/pitch-arsenals"
        f"?year={year}&min=10&type=avg_speed&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    out: dict[int, dict] = {}
    for r in csv.DictReader(io.StringIO(raw)):
        try:
            pid = int(r["pitcher"])
        except (ValueError, KeyError, TypeError):
            continue
        speeds = {}
        for ptype, col in _ARSENAL_SPEED_COLS.items():
            v = _f(r.get(col))
            if v is not None:
                speeds[ptype] = v
        if speeds:
            out[pid] = speeds
    return out


def _f(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── pure compute ──

def compute_velo(rolling: dict | None, season_speeds: dict | None,
                 prior_speeds: dict | None) -> dict | None:
    """Fastball velocity field for one SP.

    rolling: the 21d rolling metrics (needs velo_fb + velo_fb_type; may carry
    velo_fb_last_game once the rolling aggregation ships it). season/prior:
    per-pitch-type season speeds for the current and prior year. Deltas only
    compare the SAME pitch type; None when either side is missing (no
    fabricated YoY). Returns None when there is no usable 21d velo."""
    if not rolling or rolling.get("velo_fb") is None:
        return None
    fb_type = rolling.get("velo_fb_type")
    velo_21d = rolling["velo_fb"]
    season = (season_speeds or {}).get(fb_type)
    prior = (prior_speeds or {}).get(fb_type)

    def _delta(a, b):
        return round(a - b, 1) if a is not None and b is not None else None

    return {
        "fb_type": fb_type,
        "velo_21d": velo_21d,
        "velo_season": season,
        "velo_prior_season": prior,
        "d21_vs_season": _delta(velo_21d, season),
        "yoy": _delta(season, prior),
        "last_game": rolling.get("velo_fb_last_game"),
    }


def velo_tag(velo: dict | None) -> str | None:
    """One whitelisted payload tag when the 21d fastball moved ≥1.0 mph off
    the season level — down = injury precursor, up = stuff gain."""
    if not velo:
        return None
    d = velo.get("d21_vs_season")
    if d is None or abs(d) < VELO_DELTA_SIG:
        return None
    head = "⚠️ 球速下滑" if d < 0 else "✅ 球速上升"
    return f"{head} ({velo.get('fb_type') or 'FB'} {d:+.1f} vs season)"


def kbb_ladder(k, bb, bf) -> dict | None:
    """K-BB% + stabilization tier for the small-sample dead zone.

    Returns {kbb_pct, k_pct, bb_pct, bf, tier} — tier "stable" (BF≥70, K%
    trustworthy), "early" (40≤BF<70, directional), "noise" (BF<40). None when
    BF is missing/zero (no PAs faced → no rate)."""
    if not bf:
        return None
    k = k or 0
    bb = bb or 0
    if bf >= BF_STABLE:
        tier = "stable"
    elif bf >= BF_EARLY:
        tier = "early"
    else:
        tier = "noise"
    return {
        "kbb_pct": round((k - bb) / bf * 100, 1),
        "k_pct": round(k / bf * 100, 1),
        "bb_pct": round(bb / bf * 100, 1),
        "bf": bf,
        "tier": tier,
    }


def csw_context(rolling: dict | None) -> dict | None:
    """CSW% 21d level (context-only — no season baseline exists, see module
    docstring). Returns {csw_pct, pitches} or None."""
    if not rolling or rolling.get("csw_pct") is None:
        return None
    return {"csw_pct": rolling["csw_pct"], "pitches": rolling.get("pitches")}
