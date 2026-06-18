"""Unit tests for issue 039 / 318b (B1b) — LLM payload injection of the ledger
note (prev-verdict + add-reason + star) under a per-candidate line budget.

The note answers "what did we last decide, and why did we pick him" so a drop
suggestion confronts the original add reason instead of one bad day.
``_inject_318b_lines`` is the single injection point later slices
(platoon/PA/swap/micro) register their pools into; the ``_fmt_*_batter_v4``
blocks call it before returning. Pure given a CandidateEnrichment — no Yahoo /
ledger IO.
"""

from fa_scan import (
    _fmt_anchor_block_batter_v4,
    _fmt_fa_block_batter_v4,
    _inject_318b_lines,
)
from ledger_enrich import CandidateEnrichment


def _fa_entry(**ov):
    e = {
        "name": "Test FA", "mlb_id": 123456, "team": "HOU", "pct": 12,
        "status": "",
        "savant_2026": {"xwoba": 0.320, "bb_pct": 8.0, "barrel_pct": 9.0,
                        "hh_pct": 42.0, "bbe": 60},
        "prior_stats": {"xwoba": 0.310, "bb_pct": 7.5, "barrel_pct": 8.0,
                        "pa": 520},
        "derived": {"pa_per_tg": 3.8}, "rolling_14d": {},
        "add_tags": [], "warn_tags": [],
    }
    e.update(ov)
    return e


def _anchor_entry(**ov):
    e = {
        "name": "My Guy", "mlb_id": 654321, "team": "NYY",
        "savant_2026": {"xwoba": 0.300, "bb_pct": 7.0, "barrel_pct": 7.0,
                        "hh_pct": 40.0, "bbe": 80},
        "prior_stats": {"xwoba": 0.305, "bb_pct": 7.2, "barrel_pct": 7.5,
                        "pa": 600},
        "derived": {"pa_per_tg": 3.5}, "rolling_14d": {},
        "mlb_2026": {"plateAppearances": 250},
    }
    e.update(ov)
    return e


# ── _inject_318b_lines (pure) ──

def test_inject_none_enrichment_empty():
    assert _inject_318b_lines("X", None, "   ") == []


def test_inject_empty_notes_empty():
    # enrichment present but no notes (enrich produced nothing) → no lines
    assert _inject_318b_lines("X", CandidateEnrichment(stars=3), "   ") == []


def test_inject_renders_notes_with_indent():
    enr = CandidateEnrichment(stars=4, note_lines=[
        "[記事] 前判「取代」5天前 ★★★★", "[原撿因] xwOBA .349/BB% 12"])
    out = _inject_318b_lines("X", enr, "   ")
    assert out == ["   [記事] 前判「取代」5天前 ★★★★",
                   "   [原撿因] xwOBA .349/BB% 12"]


def test_inject_day0_single_line_respects_other_indent():
    enr = CandidateEnrichment(stars=4, note_lines=["[記事] 新候選 ★★★★"])
    assert _inject_318b_lines("X", enr, "  ") == ["  [記事] 新候選 ★★★★"]


def test_inject_within_three_line_budget_does_not_drop():
    # ledger alone is ≤2 lines — comfortably under the ≤3 per-candidate ceiling.
    enr = CandidateEnrichment(stars=5, note_lines=["a", "b"])
    out = _inject_318b_lines("X", enr, "")
    assert out == ["a", "b"]


# ── _fmt_fa_block_batter_v4 wiring (FA + watch) ──

def test_fa_block_appends_note_when_enrichment_given():
    enr = CandidateEnrichment(stars=4,
                              note_lines=["[記事] 前判「取代」5天前 ★★★★"])
    lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None,
                                    age=28, enrichment=enr)
    assert any("[記事] 前判「取代」" in l for l in lines)
    # injected after the existing prior line — note is the block's tail
    assert "[記事]" in lines[-1]


def test_fa_block_default_no_enrichment_unchanged():
    # backward-compatible: omitting enrichment renders exactly as before.
    plain = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None, age=28)
    explicit = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None,
                                       age=28, enrichment=None)
    assert plain == explicit
    assert not any("[記事]" in l for l in plain)


# ── _fmt_anchor_block_batter_v4 wiring (my-team drop pool) ──

def test_anchor_block_appends_note():
    enr = CandidateEnrichment(stars=3,
                              note_lines=["[記事] 前判「觀察」3天前 ★★★"])
    lines = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None,
                                        enrichment=enr)
    assert any("[記事] 前判「觀察」" in l for l in lines)


def test_anchor_block_default_unchanged():
    plain = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None)
    explicit = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None,
                                           enrichment=None)
    assert plain == explicit
    assert not any("[記事]" in l for l in plain)
