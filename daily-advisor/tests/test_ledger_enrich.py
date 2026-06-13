"""Unit tests for issue 039 / 318a — ledger_enrich pure logic.

Covers:
    percentile_of / is_season_strong / is_hot_14d — raw → signal buckets.
    classify_channel — structure > heat > market > unknown precedence.
    first_channel — never-re-judge lookup over ledger history.
    compute_candidate_stars — day-0 vs established path, channel honours
        first contact, retro faithfulness (heat-led weak-structure → ≤3★).
"""

import pytest

from decision_ledger import LedgerEntry
from ledger_enrich import (
    CandidateSignals,
    CHANNEL_HEAT,
    CHANNEL_MARKET,
    CHANNEL_STRUCTURE,
    CHANNEL_UNKNOWN,
    SOURCE_OWNED_RISER,
    SOURCE_SCAN,
    classify_channel,
    compute_candidate_stars,
    first_channel,
    is_hot_14d,
    is_season_strong,
    percentile_of,
)


# ── percentile_of ──

def test_percentile_of_brackets():
    assert percentile_of(0.349, "xwoba") == 90    # exactly P90
    assert percentile_of(0.321, "xwoba") == 70
    assert percentile_of(0.250, "xwoba") == 0     # below P25
    assert percentile_of(None, "xwoba") == 0
    assert percentile_of(0.30, "unknown_metric") == 0


# ── season-strong / hot ──

def test_is_season_strong():
    # xwOBA P70 (.321) + Barrel% P70 (10.3) + weak BB% → 2 of 3 ≥P60 → strong
    assert is_season_strong(0.321, 5.0, 10.3) is True
    # only one metric strong → not strong
    assert is_season_strong(0.321, 5.0, 4.0) is False
    assert is_season_strong(None, None, None) is False


def test_is_hot_14d():
    # 14d xwOBA at least 0.040 above season → hot
    assert is_hot_14d(0.360, 0.300) is True
    assert is_hot_14d(0.330, 0.300) is False
    assert is_hot_14d(None, 0.300) is False
    assert is_hot_14d(0.360, None) is False


# ── classify_channel ──

def test_classify_structure_wins():
    assert classify_channel(SOURCE_OWNED_RISER, season_strong=True,
                            hot_14d=True) == CHANNEL_STRUCTURE


def test_classify_heat_when_weak_and_hot():
    assert classify_channel(SOURCE_SCAN, season_strong=False,
                            hot_14d=True) == CHANNEL_HEAT


def test_classify_market_when_weak_not_hot_owned_riser():
    assert classify_channel(SOURCE_OWNED_RISER, season_strong=False,
                            hot_14d=False) == CHANNEL_MARKET


def test_classify_unknown_fallback():
    assert classify_channel(SOURCE_SCAN, season_strong=False,
                            hot_14d=False) == CHANNEL_UNKNOWN


# ── first_channel (never re-judge) ──

def test_first_channel_returns_earliest_set():
    hist = [
        LedgerEntry("X", "watch", "2026-05-09", channel=None),
        LedgerEntry("X", "watch", "2026-05-10", channel="structure"),
        LedgerEntry("X", "watch", "2026-05-11", channel="heat"),
    ]
    assert first_channel(hist) == "structure"


def test_first_channel_none_when_unset():
    assert first_channel([LedgerEntry("X", "watch", "2026-05-09")]) is None
    assert first_channel([]) is None


# ── compute_candidate_stars ──

def test_day0_new_candidate_structure_caps_four():
    # brand-new, structurally strong, everyday → day-0 path caps at 4★
    sig = CandidateSignals(
        source=SOURCE_SCAN, xwoba=0.349, bb_pct=12.2, barrel_pct=14.0,
        xwoba_14d=0.360, prior_xwoba=0.349, prior_bb_pct=12.2,
        prior_barrel_pct=14.0, prior_pa=600, pa_tg=3.9)
    stars, channel, _ = compute_candidate_stars(sig, history=[])
    assert channel == CHANNEL_STRUCTURE
    assert stars == 4  # day-0 cap (5★ needs a validated trigger)


def test_heat_led_weak_structure_capped_three():
    # weak season structure + hot 14d xwOBA → heat → ≤3★ even with strong prior
    sig = CandidateSignals(
        source=SOURCE_SCAN, xwoba=0.290, bb_pct=6.0, barrel_pct=5.0,
        xwoba_14d=0.360, prior_xwoba=0.349, prior_bb_pct=12.2,
        prior_barrel_pct=14.0, prior_pa=600, pa_tg=3.9)
    stars, channel, _ = compute_candidate_stars(sig, history=[])
    assert channel == CHANNEL_HEAT
    assert stars <= 3


def test_channel_honours_first_contact():
    # history already classified structure; current signals look heat —
    # must keep structure (never re-judge)
    hist = [LedgerEntry("X", "watch", "2026-05-09", channel="structure")]
    sig = CandidateSignals(
        source=SOURCE_SCAN, xwoba=0.290, bb_pct=6.0, barrel_pct=5.0,
        xwoba_14d=0.360, prior_xwoba=0.300, prior_bb_pct=8.0,
        prior_barrel_pct=8.0, prior_pa=600, pa_tg=3.9)
    _, channel, _ = compute_candidate_stars(sig, history=hist)
    assert channel == "structure"


def test_established_player_uses_four_factor_path():
    # non-empty history → trigger="none" (deferred), 4-factor scoring
    hist = [LedgerEntry("X", "watch", "2026-05-09", channel="structure")]
    sig = CandidateSignals(
        source=SOURCE_SCAN, xwoba=0.349, bb_pct=12.2, barrel_pct=14.0,
        xwoba_14d=0.355, prior_xwoba=0.349, prior_bb_pct=12.2,
        prior_barrel_pct=14.0, prior_pa=600, pa_tg=3.9)
    stars, _, result = compute_candidate_stars(sig, history=hist)
    assert "trigger" in result.breakdown
    assert stars == 4  # structure+full+high+trigger-none = 3.0 → 4★


def test_thin_prior_sample_not_full_dual_year():
    # dual-elite prior percentiles but only 120 PA → dual_year partial
    sig = CandidateSignals(
        source=SOURCE_SCAN, xwoba=0.290, bb_pct=6.0, barrel_pct=5.0,
        xwoba_14d=0.295, prior_xwoba=0.349, prior_bb_pct=12.2,
        prior_barrel_pct=14.0, prior_pa=120, pa_tg=2.0)
    _, _, result = compute_candidate_stars(sig, history=[])
    assert result.breakdown["dual_year"] == 0.5  # partial, not full


# ── wiring: build_ledger_enrich_map + entry extraction (issue 318a) ──

class _FakeLedger:
    def __init__(self, hist=None):
        self._h = hist or {}

    def get_history(self, name):
        return self._h.get(name, [])


def test_build_enrich_map_extracts_entry_and_scores():
    from fa_scan import build_ledger_enrich_map
    entries = [{
        "name": "New Guy", "source": SOURCE_SCAN,
        "savant_2026": {"xwoba": 0.349, "bb_pct": 12.2, "barrel_pct": 14.0},
        "derived": {"pa_per_tg": 3.9},
        "prior_stats": {"xwoba": 0.349, "bb_pct": 12.2,
                        "barrel_pct": 14.0, "pa": 600},
        "rolling_14d": {"xwoba": 0.355},
    }]
    emap = build_ledger_enrich_map(entries, _FakeLedger())
    channel, stars = emap["New Guy"]
    assert channel == CHANNEL_STRUCTURE and stars == 4


def test_build_enrich_map_honours_existing_channel():
    from fa_scan import build_ledger_enrich_map
    hist = {"X": [LedgerEntry("X", "watch", "2026-05-09", channel="structure")]}
    entries = [{
        "name": "X", "source": SOURCE_SCAN,
        "savant_2026": {"xwoba": 0.290, "bb_pct": 6.0, "barrel_pct": 5.0},
        "derived": {"pa_per_tg": 3.9},
        "prior_stats": {"xwoba": 0.300, "bb_pct": 8.0,
                        "barrel_pct": 8.0, "pa": 600},
        "rolling_14d": {"xwoba": 0.360},  # looks hot now
    }]
    channel, _ = build_ledger_enrich_map(entries, _FakeLedger(hist))["X"]
    assert channel == "structure"  # never re-judged to heat


def test_build_enrich_map_skips_nameless_and_handles_missing_keys():
    from fa_scan import build_ledger_enrich_map
    entries = [{"source": SOURCE_SCAN}, {"name": "Sparse"}]
    emap = build_ledger_enrich_map(entries, _FakeLedger())
    assert "Sparse" in emap and len(emap) == 1  # nameless skipped, sparse ok
