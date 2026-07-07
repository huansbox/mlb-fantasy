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

from dataclasses import dataclass, field
from datetime import date

import fa_compute
from daily_advisor import BATTER_PCTILES
from star_rating import (
    StarResult,
    bucket_dual_year,
    bucket_playing_time,
    bucket_playing_time_sp,
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


@dataclass
class CandidateEnrichment:
    """The full 318b injection bundle for one candidate — what the payload
    builder renders and what the ledger persists.

    B1 fills channel / stars / add_reason / note_lines. Later slices
    (platoon / PA / swap / micro) append their own *trailing-optional* fields
    here, so enrich_map's value shape stays frozen for consumers: they read
    ``.stars`` / ``.note_lines`` by name and never unpack a positional tuple
    whose arity shifts every slice."""
    channel: str | None = None
    stars: int | None = None
    add_reason: str | None = None
    note_lines: list = field(default_factory=list)   # B1: ledger note (budgeted)
    inline_tags: list = field(default_factory=list)  # B2/B5: header tags (not budgeted)
    owned_shape: str | None = None                   # B8: %owned shape → gate fast-lane
    pa_line: str | None = None                       # B3: next-week PA proj (budgeted)
    swap_line: str | None = None                     # B4: per-category swap (budgeted)


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


def first_add_reason(history) -> str | None:
    """Earliest recorded add_reason in a player's ledger history — the
    "why we first picked/watched him" set at first contact, which a later
    drop suggestion must be confronted with (PRD user story 1/9). Symmetric
    to first_channel; None if no row carries one (e.g. legacy pre-318b rows)."""
    for entry in history:
        ar = getattr(entry, "add_reason", None)
        if ar is not None:
            return ar
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


# ── 318b B6: SP-side channel + stars (the SP mirror of the batter section) ──
#
# Same taxonomy, same first-contact-never-re-judged rule, SP-shaped signals:
# season strength reads the v4 5-slot, heat reads the 21d xwOBACON surge, and
# playing time is IP/GS + Rotation Gate (PRD 040). Prior-year confirmation
# uses the three quality slots obtainable in bulk for any pitcher (whiff /
# bb9 / xwobacon — past-year GB% is broken at the Savant endpoint and prior
# IP/GS needs per-pid game logs).

SEASON_STRONG_MIN_SP = 3        # ≥3 of 5 v4 slots at P60+ (batter: 2 of 3)
HOT_21D_XWOBACON_DELTA = 0.040  # 21d xwOBACON ≥ .040 BELOW season = surge
                                # (mirrors the batter +.040 xwOBA spike)
PRIOR_SAMPLE_IP_SP = 50         # prior-year IP floor (the retired ✅雙年菁英 line)


@dataclass
class SPSignals:
    source: str
    ip_gs: float | None = None        # 2026 v4 slot raws
    whiff_pct: float | None = None
    bb9: float | None = None
    gb_pct: float | None = None
    xwobacon: float | None = None
    rolling_xwobacon: float | None = None   # 21d rolling (heat proxy)
    prior_whiff_pct: float | None = None    # 2025 prior quality slots
    prior_bb9: float | None = None
    prior_xwobacon: float | None = None
    prior_ip: float | None = None
    rotation_ok: bool = True


# The single v4 band walk lives in fa_compute (one place to touch when the
# 2026 percentile table lands); re-exported under the SP-section name.
sp_percentile_of = fa_compute.v4_percentile_of


def is_season_strong_sp(sig: SPSignals) -> bool:
    pcts = [
        sp_percentile_of(sig.ip_gs, "ip_gs"),
        sp_percentile_of(sig.whiff_pct, "whiff_pct"),
        sp_percentile_of(sig.bb9, "bb9"),
        sp_percentile_of(sig.gb_pct, "gb_pct"),
        sp_percentile_of(sig.xwobacon, "xwobacon"),
    ]
    return sum(1 for p in pcts if p >= SEASON_STRONG_P) >= SEASON_STRONG_MIN_SP


def is_hot_21d_sp(rolling_xwobacon, season_xwobacon) -> bool:
    """A 21d contact-damage surge (xwOBACON well below season) — heat-led."""
    if rolling_xwobacon is None or season_xwobacon is None:
        return False
    return (season_xwobacon - rolling_xwobacon) >= HOT_21D_XWOBACON_DELTA


def build_star_factors_sp(sig: SPSignals, channel: str) -> dict:
    prior_pcts = [
        sp_percentile_of(sig.prior_whiff_pct, "whiff_pct"),
        sp_percentile_of(sig.prior_bb9, "bb9"),
        sp_percentile_of(sig.prior_xwobacon, "xwobacon"),
    ]
    sample_ok = (sig.prior_ip or 0) >= PRIOR_SAMPLE_IP_SP
    return {
        "channel": channel,
        "dual_year": bucket_dual_year(prior_pcts, sample_ok=sample_ok),
        "playing_time": bucket_playing_time_sp(sig.ip_gs, sig.rotation_ok),
    }


def compute_candidate_stars_sp(sig: SPSignals, history) -> tuple[int, str, StarResult]:
    """SP mirror of compute_candidate_stars: first-contact channel honored,
    day-0 path (cap 4★) for empty history, trigger deferred to 'none'."""
    channel = first_channel(history) or classify_channel(
        sig.source,
        is_season_strong_sp(sig),
        is_hot_21d_sp(sig.rolling_xwobacon, sig.xwobacon),
    )
    factors = build_star_factors_sp(sig, channel)
    if not history:
        result = score(factors, day0=True)
    else:
        factors["trigger"] = "none"
        result = score(factors, day0=False)
    return result.stars, channel, result


def snapshot_add_reason_sp(sig: SPSignals) -> str:
    """Compact 5-slot "why we picked him" snapshot, persisted at first
    contact. '?' if nothing is known (never empty)."""
    parts = []
    if sig.ip_gs is not None:
        parts.append(f"IP/GS {sig.ip_gs:.2f}")
    if sig.whiff_pct is not None:
        parts.append(f"Whiff% {sig.whiff_pct:.1f}")
    if sig.bb9 is not None:
        parts.append(f"BB/9 {sig.bb9:.2f}")
    if sig.gb_pct is not None:
        parts.append(f"GB% {sig.gb_pct:.1f}")
    if sig.xwobacon is not None:
        parts.append(f"xwOBACON {_fmt_xwoba3(sig.xwobacon)}")
    return " / ".join(parts) if parts else "?"


def enrich_candidate_sp(sig: SPSignals, history, today_str) -> CandidateEnrichment:
    """SP mirror of enrich_candidate — stars/channel computed (persisted +
    gate/KPI), ledger note rendered, star itself never injected (doc Q1)."""
    stars, channel, _ = compute_candidate_stars_sp(sig, history)
    add_reason = first_add_reason(history) or snapshot_add_reason_sp(sig)
    note_lines = format_ledger_note(history, today_str,
                                    add_reason_fallback=add_reason)
    return CandidateEnrichment(channel=channel, stars=stars,
                               add_reason=add_reason, note_lines=note_lines)


# ── B1 / 318b: payload note injection (prev-verdict + add-reason + star) ──
#
# These render the ledger context into LLM-payload lines. Every line carries a
# bracketed `[...]` prefix so the read-back / backtest parser can locate it
# (the 028/032 grammar already keys on bracketed milestones). The note answers
# "what did we last decide, and why did we pick him" so a drop suggestion must
# confront the original add reason instead of reacting to one bad day.


def _fmt_xwoba3(v) -> str:
    """xwOBA convention: 3 decimals, no leading zero (.349 not 0.349)."""
    s = f"{v:.3f}"
    return s[1:] if s.startswith("0.") else s


def _days_between(earlier, later) -> int | None:
    """Whole days between two ISO date strings; None on bad/absent input."""
    try:
        return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
    except (ValueError, TypeError):
        return None


def snapshot_add_reason(sig: CandidateSignals) -> str:
    """A compact "why we picked him" snapshot from current signals, persisted
    once at first contact. Mirrors the three core batter metrics; appends the
    14d xwOBA when a heat spike is what surfaced the pickup. '?' if nothing is
    known (never empty — the field is the anchor a later drop is confronted
    with)."""
    parts = []
    if sig.xwoba is not None:
        parts.append(f"xwOBA {_fmt_xwoba3(sig.xwoba)}")
    if sig.bb_pct is not None:
        parts.append(f"BB% {sig.bb_pct}")
    if sig.barrel_pct is not None:
        parts.append(f"Barrel% {sig.barrel_pct}")
    if is_hot_14d(sig.xwoba_14d, sig.xwoba):
        parts.append(f"14d xwOBA {_fmt_xwoba3(sig.xwoba_14d)}")
    return " / ".join(parts) if parts else "?"


def format_ledger_note(history, today_str, add_reason_fallback=None) -> list[str]:
    """Render a candidate's ledger MEMORY into payload lines.

    Per design doc Q1, this injects the system's *memory* — what it last
    decided and why it first picked him — NOT the star rating. The star (1-5★)
    is a mechanical aggregate; surfacing it to the LLM walks back into the v2
    "Sum exposed to the LLM" path that batter v4 thin retired. The star stays
    pre-LLM (payload pre-screen + 041 gate + 051 KPI), never in the payload.

    Empty history = first contact → NO lines (the player has no memory yet;
    day-0 candidates get a looser budget). Established → two lines: the last
    verdict + the ORIGINAL add reason (first_add_reason, never re-judged;
    falls back to the live snapshot for legacy rows predating add_reason).
    """
    if not history:
        return []
    prev = history[-1]
    days = _days_between(getattr(prev, "ts", None), today_str)
    when = f"{days} 天前" if days is not None else getattr(prev, "ts", "?")
    reason = first_add_reason(history) or add_reason_fallback
    lines = [f"[記事] 上次 {getattr(prev, 'verdict', '?')}（{when}）"]
    if reason:
        lines.append(f"[原撿因] {reason}")
    return lines


def enrich_candidate(sig: CandidateSignals, history, today_str) -> CandidateEnrichment:
    """Assemble one candidate's full injection bundle.

    Combines the mechanical stars + first-contact channel
    (``compute_candidate_stars``), the never-re-judged ``add_reason``
    (the persisted first-contact reason, or a fresh snapshot when none is on
    record — first contact or a legacy pre-318b row), and the rendered ledger
    note lines. Pure given ``history`` + ``today_str`` — unit-tested without
    any fa_scan wiring; the fa_scan layer only extracts ``sig`` from an entry
    and persists/injects the result."""
    # stars are still computed (041 gate + 051 KPI read them) but NOT injected
    # into note_lines — design doc Q1 keeps the mechanical aggregate pre-LLM.
    stars, channel, _ = compute_candidate_stars(sig, history)
    add_reason = first_add_reason(history) or snapshot_add_reason(sig)
    note_lines = format_ledger_note(history, today_str,
                                    add_reason_fallback=add_reason)
    return CandidateEnrichment(channel=channel, stars=stars,
                               add_reason=add_reason, note_lines=note_lines)
