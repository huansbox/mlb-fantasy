"""Swap-vector — batter (issue 047 / #326).

The literal answer to the murky middle: for a 4★+ candidate, the per-category
weekly delta versus the NAMED incumbent it would replace (add candidate ⇄ drop
incumbent), with a PA column so volume loss can't be ignored. add/drop value in
H2H categories is candidate-minus-incumbent, never "better overall" — and the
PA delta is exactly what the Arraez→Pederson swap lost (−28% weekly PA).

Pure: each side's projected category dict (from 045 / 043) is differenced.
Emission is gated on the candidate's mechanical stars (4★+), so the cost-bearing
payload line only appears for real action candidates. The actual payload
injection is 318b; this slice computes + formats the vector.
"""

from __future__ import annotations

from weekly_projection import RATIO

MIN_STARS_TO_EMIT = 4
# Display order: counting first, then ratios, PA last (the un-ignorable column).
_ORDER = ("R", "HR", "RBI", "SB", "BB", "AVG", "OPS", "PA")


def should_emit_swap(stars, min_stars=MIN_STARS_TO_EMIT) -> bool:
    """Only 4★+ candidates emit a swap line (star pre-filter, payload budget)."""
    return stars is not None and stars >= min_stars


def swap_vector_batter(cand_cats, cand_pa, inc_cats, inc_pa) -> dict:
    """Per-category weekly delta = candidate − incumbent, plus a PA delta.

    cand_cats / inc_cats: projected category dicts (counting = expected count,
    ratio = rate). Counting deltas round to 1 dp, ratio deltas to 3 dp."""
    vec = {}
    for cat in set(cand_cats) | set(inc_cats):
        delta = (cand_cats.get(cat) or 0) - (inc_cats.get(cat) or 0)
        vec[cat] = round(delta, 3 if cat in RATIO else 1)
    vec["PA"] = round((cand_pa or 0) - (inc_pa or 0), 1)
    return vec


def format_swap_line(drop_name, add_name, vec) -> str:
    """`swap {drop}→{add}/week: BB +2.1, HR +0.4, ..., PA -7` (signed)."""
    parts = []
    for cat in _ORDER:
        if cat not in vec:
            continue
        v = vec[cat]
        parts.append(f"{cat} {v:+g}")
    for cat in vec:  # any extra categories not in the fixed order
        if cat not in _ORDER:
            parts.append(f"{cat} {vec[cat]:+g}")
    return f"swap {drop_name}→{add_name}/week: " + ", ".join(parts)
