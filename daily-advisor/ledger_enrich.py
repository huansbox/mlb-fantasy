"""Ledger enrichment — pure logic for issue 039 / 318a.

Bridges a candidate's raw signals to (a) a discovery channel and (b) a
mechanical star rating, so the 039 wiring can persist channel + stars onto
the decision ledger (read later by 041 gate / 051 KPI). No payload mutation
here — that LLM-facing injection is 318b.

Discovery channel is THE discriminator the retrospective identified
(docs/fa-scan-decision-retrospective-2026h1.md §4): a structurally strong
candidate is structure-led; a weak-structure candidate surfaced by a 14d
spike is heat-led (Sheets/Pederson); one surfaced only by ownership movement
is market-led. Channel is set at FIRST contact and never re-judged — the
caller passes the player's ledger history and we reuse the earliest recorded
channel if present (issue 038 `first_channel`).

Trigger-completeness (the 4th star factor) requires evaluating a 037-grammar
trigger against current stats — deferred. 318a scores established watch
players with trigger="none" (a safe under-rate: never inflates) and brand-new
candidates via the day-0 3-factor path (capped 4★). The 5★ precision arrives
when trigger evaluation is built.
"""

from __future__ import annotations

from dataclasses import dataclass

from daily_advisor import BATTER_PCTILES
from star_rating import (
    StarResult,
    bucket_dual_year,
    bucket_playing_time,
    score,
)

# Channel taxonomy (must match star_rating.WEIGHTS["channel"] keys).
CHANNEL_STRUCTURE = "structure"
CHANNEL_HEAT = "heat"
CHANNEL_MARKET = "market"
CHANNEL_NEWS = "news"
CHANNEL_UNKNOWN = "unknown"

# Candidate pool sources (tagged at pool collection by the 039 wiring).
SOURCE_SCAN = "scan-query"
SOURCE_OWNED_RISER = "owned-riser"
SOURCE_WATCH = "watch"

# Heat = a 14d xwOBA spike over the season baseline. Using rolling xwOBA (on
# every candidate entry already) instead of 14d OPS avoids a second trad fetch;
# 0.040 mirrors the daily_advisor "heating" recency band.
HOT_14D_XWOBA_DELTA = 0.040
SEASON_STRONG_P = 60       # a core metric at P60+ counts toward "strong"
SEASON_STRONG_MIN = 2      # ≥2 of the 3 core metrics P60+ → season strong
PRIOR_SAMPLE_PA = 200      # prior-year PA floor for dual-year "full" credit


@dataclass
class CandidateSignals:
    source: str
    xwoba: float | None = None        # 2026 season raws
    bb_pct: float | None = None
    barrel_pct: float | None = None
    xwoba_14d: float | None = None    # 14d rolling Savant xwOBA (heat proxy)
    prior_xwoba: float | None = None  # 2025 prior raws
    prior_bb_pct: float | None = None
    prior_barrel_pct: float | None = None
    prior_pa: int | None = None
    pa_tg: float | None = None


def percentile_of(value, metric) -> int:
    """Numeric percentile = the highest 2025-batter bracket ``value`` clears;
    0 below P25 or for unknown/None inputs."""
    bp = BATTER_PCTILES.get(metric)
    if not bp or value is None:
        return 0
    matched = 0
    for pct, thresh in bp:  # ascending breakpoints
        if value >= thresh:
            matched = pct
    return matched


def is_season_strong(xwoba, bb_pct, barrel_pct) -> bool:
    pcts = [
        percentile_of(xwoba, "xwoba"),
        percentile_of(bb_pct, "bb_pct"),
        percentile_of(barrel_pct, "barrel_pct"),
    ]
    return sum(1 for p in pcts if p >= SEASON_STRONG_P) >= SEASON_STRONG_MIN


def is_hot_14d(xwoba_14d, xwoba_season) -> bool:
    """A 14d xwOBA spike over the season baseline (heat-led signal)."""
    if xwoba_14d is None or xwoba_season is None:
        return False
    return (xwoba_14d - xwoba_season) >= HOT_14D_XWOBA_DELTA


def classify_channel(source, season_strong, hot_14d) -> str:
    """Map surfacing signals → discovery channel. Structure wins when present
    (we don't penalise a genuinely strong bat for also being owned/hot); else
    a 14d spike is heat; else ownership movement is market; else unknown."""
    if season_strong:
        return CHANNEL_STRUCTURE
    if hot_14d:
        return CHANNEL_HEAT
    if source == SOURCE_OWNED_RISER:
        return CHANNEL_MARKET
    return CHANNEL_UNKNOWN


def first_channel(history) -> str | None:
    """Earliest recorded channel in a player's ledger history (the
    never-re-judge value); None if none set."""
    for entry in history:
        ch = getattr(entry, "channel", None)
        if ch is not None:
            return ch
    return None


def build_star_factors(sig: CandidateSignals, channel: str) -> dict:
    """Assemble the named factor dict star_rating.score consumes (3 pre-trigger
    factors; trigger added by the caller for established players)."""
    prior_pcts = [
        percentile_of(sig.prior_xwoba, "xwoba"),
        percentile_of(sig.prior_bb_pct, "bb_pct"),
        percentile_of(sig.prior_barrel_pct, "barrel_pct"),
    ]
    sample_ok = (sig.prior_pa or 0) >= PRIOR_SAMPLE_PA
    return {
        "channel": channel,
        "dual_year": bucket_dual_year(prior_pcts, sample_ok=sample_ok),
        "playing_time": bucket_playing_time(sig.pa_tg),
    }


def compute_candidate_stars(sig: CandidateSignals, history) -> tuple[int, str, StarResult]:
    """Returns (stars, channel, StarResult). Channel honours first-contact;
    a brand-new candidate (empty history) scores via the day-0 path (cap 4★),
    an established one on 4 factors with trigger deferred to 'none'."""
    channel = first_channel(history) or classify_channel(
        sig.source,
        is_season_strong(sig.xwoba, sig.bb_pct, sig.barrel_pct),
        is_hot_14d(sig.xwoba_14d, sig.xwoba),
    )
    factors = build_star_factors(sig, channel)
    if not history:  # day-0: brand-new, no trigger yet
        result = score(factors, day0=True)
    else:            # established: trigger-completeness deferred (safe under-rate)
        factors["trigger"] = "none"
        result = score(factors, day0=False)
    return result.stars, channel, result
