"""Weekly projection arithmetic — shared deep module (issue 043 / #322).

Turns per-unit rates into a week's expected 7×7 category vector. Three
downstream slices share it (045 PA projection, 047 swap-batter, 048 swap-SP)
so the rate×volume math lives in exactly one place.

Counting categories accumulate linearly with volume (rate × projected PA or
starts). Ratio categories (AVG/OPS, ERA/WHIP) are rates that do NOT accumulate
— `project` passes the rate through, and consumers damp a ratio DIFF by
`ratio_weight(volume)` (sqrt of the smaller volume) so a hot OPS over a few PA
counts less than the same OPS over a full week.

Pure, no fetch, no LLM — fully offline-testable.
"""

from __future__ import annotations

# 7×7 category kinds (batter + pitcher).
BATTER_COUNTING = ("R", "HR", "RBI", "SB", "BB")
BATTER_RATIO = ("AVG", "OPS")
SP_COUNTING = ("IP", "W", "K", "QS", "SVH")
SP_RATIO = ("ERA", "WHIP")

COUNTING = frozenset(BATTER_COUNTING + SP_COUNTING)
RATIO = frozenset(BATTER_RATIO + SP_RATIO)


def project(rates: dict, volume) -> dict:
    """Project per-unit ``rates`` onto a week's ``volume``.

    Counting category → rate × volume (expected count). Ratio category → rate
    passed through unchanged (a rate doesn't accumulate; damp its weight via
    ``ratio_weight``). A category not in either set is treated as a passthrough
    rate (safe default). ``None`` rates are skipped. ``volume`` may be 0 →
    counting projects to 0, ratios stay at their rate.
    """
    out = {}
    for cat, rate in rates.items():
        if rate is None:
            continue
        out[cat] = rate * volume if cat in COUNTING else rate
    return out


def ratio_weight(volume) -> float:
    """Volume damping for ratio-category diffs: sqrt(volume). 0 for a
    non-positive/None volume (no plate appearances → no ratio influence)."""
    if not volume or volume <= 0:
        return 0.0
    return volume ** 0.5
