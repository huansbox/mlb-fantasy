"""Star rating — mechanical 1-5★ (issue 040).

A pre-LLM deterministic score so the LLM consumes a rating it never invents.
Stars drive the notification threshold (041 pushes only 4★+) and swap-vector
pre-filter (047/048 emit only for 4★+).

Design (PRD `issues/prd-decision-execution.md`, 「star_rating」):
  - Frozen interface `score(factors: dict) → StarResult`. Factors are a NAMED
    bag and the weights are a DATA TABLE, so adding a factor later is a data
    change, not a signature change (the deep-module churn fix).
  - Four factors, each 0/0.5/1.0; Σ ∈ [0,4]; stars = 1 + round(Σ) (half-up).
  - day-0 variant: only the 3 pre-trigger factors count, scaled to [0,4] and
    capped at 4★ (a 5★ must be earned through trigger completeness).
  - Calibrated against the retrospective: the discovery-channel structure/heat
    split is the load-bearing discriminator separating the ≥4★ winners
    (Vargas/Horwitz/O'Hearn) from the ≤3★ losers (Sheets/Pederson). See
    docs/fa-scan-decision-retrospective-2026h1.md §4 and test_star_rating.py.

Factor extraction from raw stats (channel from pool source, percentiles,
PA/TG, trigger-met count) lives in the 039 consumer; this module owns the
bucketers + the weight table + the arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass

# Data-driven weight table: {factor: {level: points}}. Add a factor by adding
# a row here — score()'s signature never changes.
WEIGHTS: dict[str, dict[str, float]] = {
    "channel": {"structure": 1.0, "market": 0.5, "news": 0.5,
                "unknown": 0.5, "heat": 0.0},
    "dual_year": {"full": 1.0, "partial": 0.5, "none": 0.0},
    "playing_time": {"high": 1.0, "mid": 0.5, "low": 0.0},
    "trigger": {"full": 1.0, "partial": 0.5, "none": 0.0},
}

# day-0 (newly-surfaced FA) uses the pre-trigger factors only and caps at 4★.
DAY0_FACTORS = ("channel", "dual_year", "playing_time")
DAY0_MAX_STARS = 4

_STAR_FULL = "★"
_STAR_EMPTY = "☆"
_BREAKDOWN_LABELS = {
    "channel": "路徑", "dual_year": "雙年",
    "playing_time": "上場", "trigger": "觸發",
}


@dataclass
class StarResult:
    stars: int
    total: float
    breakdown: dict  # factor -> points awarded


def _round_half_up(x: float) -> int:
    return int(x + 0.5)


def score(factors: dict, day0: bool = False) -> StarResult:
    """Score a candidate's factor levels into 1-5★.

    ``factors`` maps factor name → level string (e.g. ``{"channel":
    "structure", "dual_year": "full", ...}``). Unknown factor names are
    ignored; unknown levels score 0 (defensive — a typo never inflates).
    ``day0=True`` selects the 3-factor scaled variant capped at 4★.
    """
    breakdown: dict[str, float] = {}
    for factor, level in factors.items():
        table = WEIGHTS.get(factor)
        if table is None:
            continue
        breakdown[factor] = table.get(level, 0.0)

    if day0:
        raw = sum(breakdown.get(f, 0.0) for f in DAY0_FACTORS)
        scaled = raw * (4.0 / len(DAY0_FACTORS))
        stars = min(DAY0_MAX_STARS, 1 + _round_half_up(scaled))
        return StarResult(stars=stars, total=round(scaled, 3),
                          breakdown=breakdown)

    total = sum(breakdown.values())
    stars = max(1, min(5, 1 + _round_half_up(total)))
    return StarResult(stars=stars, total=total, breakdown=breakdown)


# ── bucketers: raw → level (consumed by the 039 factor extractor) ──

def bucket_playing_time(pa_tg) -> str:
    """PA/Team-game → playing-time level. SP callers map IP/GS + Rotation
    Gate to the same levels before calling score()."""
    if pa_tg is None:
        return "low"
    if pa_tg >= 3.5:
        return "high"
    if pa_tg >= 2.5:
        return "mid"
    return "low"


def bucket_dual_year(prior_percentiles, sample_ok: bool) -> str:
    """Prior-year core percentiles → dual-year confirmation level.

    Full = ≥2 core metrics at P70+ AND an adequate prior sample; a
    dual-elite line on a thin sample is at most partial (the Curtis-Mead
    "P0 in 150 PA ≠ P0 in 600 PA" lesson, inverted)."""
    strong = sum(1 for p in (prior_percentiles or []) if p is not None and p >= 70)
    if strong >= 2 and sample_ok:
        return "full"
    if strong >= 1 or (strong >= 2 and not sample_ok):
        return "partial"
    return "none"


def bucket_trigger(met: int, total: int) -> str:
    """Trigger-condition completeness → level."""
    if total <= 0 or met <= 0:
        return "none"
    if met >= total:
        return "full"
    return "partial"


def format_stars(result: StarResult) -> str:
    """Compact payload string: filled/empty stars + factor breakdown."""
    bar = _STAR_FULL * result.stars + _STAR_EMPTY * (5 - result.stars)
    parts = []
    for factor, pts in result.breakdown.items():
        label = _BREAKDOWN_LABELS.get(factor, factor)
        parts.append(f"{label}+{pts:g}")
    return f"{bar} ({'/'.join(parts)})" if parts else bar
