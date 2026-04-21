"""fa_compute — Python compute layer for fa_scan.

Mechanical rules (Sum / urgency / ✅⚠️ tags / upgrade) extracted from Claude
prompts into deterministic, unit-testable Python. See
`docs/fa_scan-python-compute-design.md` §3 for architecture.

Single source of truth for rule definitions remains CLAUDE.md. This module
implements those rules 1:1.
"""

from __future__ import annotations

from typing import Literal

from daily_advisor import BATTER_PCTILES, PITCHER_PCTILES

PlayerType = Literal["batter", "sp"]

# Metric → prior_stats key mapping (SP prior uses _allowed suffix)
_PRIOR_KEY_MAP = {
    "batter": {
        "xwoba": "xwoba",
        "bb_pct": "bb_pct",
        "barrel_pct": "barrel_pct",
    },
    "sp": {
        "xera": "xera",
        "xwoba": "xwoba_allowed",
        "hh_pct": "hh_pct_allowed",
    },
}

# Human-readable breakdown labels (preserve prompt casing: "xwOBA", "BB%", ...)
_BREAKDOWN_LABELS = {
    "batter": {"xwoba": "xwOBA", "bb_pct": "BB%", "barrel_pct": "Barrel%"},
    "sp": {"xera": "xERA", "xwoba": "xwOBA", "hh_pct": "HH%"},
}

# Metric order for Sum (xwOBA / BB% / Barrel% for batter; xERA / xwOBA / HH% for SP)
_METRIC_ORDER = {
    "batter": ("xwoba", "bb_pct", "barrel_pct"),
    "sp": ("xera", "xwoba", "hh_pct"),
}


def _pctile_table(player_type: PlayerType):
    if player_type == "batter":
        return BATTER_PCTILES
    if player_type == "sp":
        return PITCHER_PCTILES
    raise ValueError(f"unknown player_type: {player_type}")


def metric_to_score(value, metric: str, player_type: PlayerType) -> int:
    """Convert metric value to 1-10 score per CLAUDE.md Sum 打分表.

    >P90=10, P80-90=9, P70-80=8, P60-70=7, P50-60=6, P40-50=5, P25-40=3, <P25=1.
    Auto-detects higher_better from percentile table direction.
    Returns 0 if value is None.
    """
    if value is None:
        return 0
    bp = _pctile_table(player_type).get(metric)
    if not bp:
        return 0
    higher_better = bp[-1][1] > bp[0][1]
    matched_pct = 0
    for pct, thresh in bp:
        if (higher_better and value >= thresh) or (not higher_better and value <= thresh):
            matched_pct = pct
    if matched_pct >= 90:
        return 10
    if matched_pct >= 80:
        return 9
    if matched_pct >= 70:
        return 8
    if matched_pct >= 60:
        return 7
    if matched_pct >= 50:
        return 6
    if matched_pct >= 40:
        return 5
    if matched_pct >= 25:
        return 3
    return 1


def compute_sum_score(metrics: dict, player_type: PlayerType) -> tuple[int, dict]:
    """3-metric Sum per CLAUDE.md Step 1 規則.

    Args:
        metrics: batter {"xwoba", "bb_pct", "barrel_pct"}
                 sp     {"xera",  "xwoba",  "hh_pct"}
        player_type: "batter" or "sp"

    Returns:
        (sum_score, breakdown) where breakdown is {"xwOBA": n, "BB%": n, ...}.
        sum_score range 3-30 (or 0-30 if values are None).
    """
    labels = _BREAKDOWN_LABELS[player_type]
    breakdown = {}
    total = 0
    for metric in _METRIC_ORDER[player_type]:
        score = metric_to_score(metrics.get(metric), metric, player_type)
        breakdown[labels[metric]] = score
        total += score
    return total, breakdown


def compute_2025_sum(prior_stats: dict | None, player_type: PlayerType) -> tuple[int, dict]:
    """Same as compute_sum_score but maps SP prior_stats keys (_allowed suffix).

    Args:
        prior_stats: roster_config prior_stats dict (or None for no prior)

    Returns:
        (sum_score, breakdown). Returns (0, zero-filled breakdown) if prior is
        empty/None — caller handles "no prior" semantics.
    """
    if not prior_stats:
        labels = _BREAKDOWN_LABELS[player_type]
        return 0, {label: 0 for label in labels.values()}

    key_map = _PRIOR_KEY_MAP[player_type]
    metrics = {metric: prior_stats.get(prior_key) for metric, prior_key in key_map.items()}
    return compute_sum_score(metrics, player_type)
