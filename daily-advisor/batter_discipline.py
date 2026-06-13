"""Chase / zone-contact YoY delta field (issue 049 M-bat / GitHub #328).

Plate discipline moves *before* BB% does. BB% is the single highest-leverage
category in this 7×7 (it scores twice — the BB column and the OBP half of OPS),
so a YoY shift in chase rate (swings at pitches out of the zone) or in-zone
contact is an early read on a hitter's discipline evolving or decaying, weeks
before the rate stats confirm it.

Layers (mirrors prospect_pedigree.py):
  - this module — bulk Savant fetch + pure compute (delta / percentile /
    significance) + tag. stdlib only, no project imports, no Yahoo.
  - calc_discipline_pctiles.py — derives the 2025 baselines below.
  - fa_scan wiring — joins current+prior bulk CSVs per batter, attaches the
    field to the payload (039 whitelist), validated on the VPS.

**Data-premise correction** (same shape as the M-sp savant_rolling fix): the
brainstorm assumed chase/zone-contact were already in a fetched batter CSV. They
are NOT — the statcast + expected_statistics batter leaderboards carry no
plate-discipline columns. This field adds ONE bulk /leaderboard/custom CSV per
year (current + prior), not a per-player round.

Direction: chase LOWER = better (selective); zone-contact HIGHER = better.
Savant columns: chase = oz_swing_percent, zone-contact = iz_contact_percent.
"""

from __future__ import annotations

import csv
import io
import urllib.request

# ── 2025 baselines (PA>=250, n=309) from calc_discipline_pctiles.py ──
# value → population percentile rank (thresholds ascend with percentile).
_CHASE_PCTILES = {10: 21.5, 25: 24.0, 40: 26.5, 50: 27.9, 55: 28.8,
                  60: 29.6, 70: 31.0, 80: 32.5, 90: 35.6}
_ZCON_PCTILES = {10: 77.0, 25: 79.9, 40: 82.1, 50: 83.1, 55: 83.8,
                 60: 84.5, 70: 86.0, 80: 87.4, 90: 90.4}

# Significant YoY move = P70 of the 2024→2025 |delta| test-retest distribution
# (n=225, both years PA>=250) — same P70 precedent as the SP xERA / batter wOBA
# luck thresholds. |chase Δ| P70 3.6, |zone-contact Δ| P70 3.1.
CHASE_DELTA_SIG = 3.6
ZCON_DELTA_SIG = 3.1

# A rate needs this much current-season PA to mean anything, and this much
# prior-season PA for a stable YoY baseline. Below the prior floor → level only,
# no delta.
CUR_PA_FLOOR = 40
PRIOR_PA_FLOOR = 150

_SEL = "pa,oz_swing_percent,iz_contact_percent"


# ── network (thin) ──
def fetch_batter_discipline_bulk(year: int) -> dict[int, dict]:
    """One league-bulk Savant custom CSV → {pid: {chase, zone_contact, pa}}."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=batter&filter=&min=1&selections={_SEL}&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    out: dict[int, dict] = {}
    for r in csv.DictReader(io.StringIO(raw)):
        try:
            pid = int(r["player_id"])
        except (ValueError, KeyError, TypeError):
            continue
        out[pid] = {
            "pa": _f(r.get("pa")),
            "chase": _f(r.get("oz_swing_percent")),
            "zone_contact": _f(r.get("iz_contact_percent")),
        }
    return out


def _f(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── pure compute ──
def pctile_rank(value, table: dict) -> int | None:
    """Population percentile rank of a value (thresholds ascend with pct).

    Returns the highest percentile whose threshold the value reaches, or 5 when
    below the lowest band. Reported as LLM context only — direction-agnostic,
    so the caller annotates lower/higher = better.
    """
    if value is None:
        return None
    rank = 5
    for p in sorted(table):
        if value >= table[p]:
            rank = p
        else:
            break
    return rank


def compute_discipline(cur: dict | None, prior: dict | None) -> dict | None:
    """Pure field compute. cur/prior are {chase, zone_contact, pa} or None.

    Returns None when there is no usable current sample (the field simply does
    not appear). When prior is missing/thin, levels + percentiles still report
    but deltas are None (no fabricated YoY).
    """
    if not cur or cur.get("pa") is None or cur["pa"] < CUR_PA_FLOOR:
        return None
    chase, zcon = cur.get("chase"), cur.get("zone_contact")
    if chase is None and zcon is None:
        return None

    have_prior = bool(prior) and prior.get("pa") is not None and prior["pa"] >= PRIOR_PA_FLOOR

    def _delta(key, sig):
        if not have_prior or cur.get(key) is None or prior.get(key) is None:
            return None, False
        d = round(cur[key] - prior[key], 1)
        return d, abs(d) >= sig

    chase_delta, chase_sig = _delta("chase", CHASE_DELTA_SIG)
    zcon_delta, zcon_sig = _delta("zone_contact", ZCON_DELTA_SIG)

    return {
        "chase": chase,
        "chase_pctile": pctile_rank(chase, _CHASE_PCTILES),
        "chase_delta": chase_delta,
        "chase_delta_sig": chase_sig,
        "zone_contact": zcon,
        "zone_contact_pctile": pctile_rank(zcon, _ZCON_PCTILES),
        "zone_contact_delta": zcon_delta,
        "zone_contact_delta_sig": zcon_sig,
        "has_prior": have_prior,
    }


def discipline_tag(result: dict | None) -> str | None:
    """One payload tag for the discipline trend, or None.

    Chase is the headline (it leads BB%, the double-counted category); a
    significant zone-contact move is appended when present, or stands alone if
    chase is quiet. No significant move → no tag.
    """
    if not result:
        return None

    frags = []
    cd, zd = result.get("chase_delta"), result.get("zone_contact_delta")
    chase_good = result.get("chase_delta_sig") and cd is not None and cd < 0
    chase_bad = result.get("chase_delta_sig") and cd is not None and cd > 0
    zcon_good = result.get("zone_contact_delta_sig") and zd is not None and zd > 0
    zcon_bad = result.get("zone_contact_delta_sig") and zd is not None and zd < 0

    if chase_good or chase_bad:
        head = "✅ 選球進化" if chase_good else "⚠️ 選球崩壞"
        frags.append(f"chase {cd:+.1f}")
        if zcon_good or zcon_bad:
            frags.append(f"zone-contact {zd:+.1f}")
        return f"{head} ({', '.join(frags)})"

    if zcon_good or zcon_bad:
        head = "✅ 擊球接觸升" if zcon_good else "⚠️ 擊球接觸降"
        return f"{head} (zone-contact {zd:+.1f})"

    return None
