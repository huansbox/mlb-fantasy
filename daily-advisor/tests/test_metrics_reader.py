"""Tests for metrics_reader."""

from __future__ import annotations

import json

import pytest

from metrics_reader import aggregate_metrics, parse_metric_block


_VALID_BLOCK = """[Phase 6 Final] drop Nola add Pfaadt — xwOBACON 明顯勝出。

<!-- phase6_metrics:
{
  "date": "2026-05-06",
  "sp_p1_match": true,
  "sp_review_triggered": false,
  "sp_anchor_name": "Nola",
  "fa_p1_match": true,
  "fa_review_triggered": false,
  "fa_top_name": "Pfaadt"
}
-->
"""

_NO_BLOCK = "Just plain advice with no metric block here."

_MALFORMED = """Advice text.

<!-- phase6_metrics:
{ this is not valid json }
-->
"""


def _block(date, sp_p1, sp_rev, fa_p1, fa_rev,
           sp_anchor="Nola", fa_top="Pfaadt",
           sp_p1_pair=False, fa_top1_pair=False,
           include_pair_fields=True):
    body = {
        "date": date,
        "sp_p1_match": sp_p1,
        "sp_review_triggered": sp_rev,
        "sp_anchor_name": sp_anchor,
        "fa_p1_match": fa_p1,
        "fa_review_triggered": fa_rev,
        "fa_top_name": fa_top,
    }
    if include_pair_fields:
        body["sp_p1_pair_borderline"] = sp_p1_pair
        body["fa_top1_pair_borderline"] = fa_top1_pair
    payload = json.dumps(body, indent=2)
    return f"advice text\n<!-- phase6_metrics:\n{payload}\n-->"


# ── parse_metric_block ──────────────────────────────────────────

class TestParseMetricBlock:
    def test_valid_block_parses(self):
        m = parse_metric_block(_VALID_BLOCK)
        assert m["date"] == "2026-05-06"
        assert m["sp_p1_match"] is True
        assert m["fa_top_name"] == "Pfaadt"

    def test_no_block_returns_none(self):
        assert parse_metric_block(_NO_BLOCK) is None

    def test_malformed_json_returns_none(self):
        assert parse_metric_block(_MALFORMED) is None

    def test_empty_body_returns_none(self):
        assert parse_metric_block("") is None
        assert parse_metric_block(None) is None


# ── aggregate_metrics ────────────────────────────────────────────

class TestAggregateMetrics:
    def test_empty_input(self):
        s = aggregate_metrics([])
        assert s["n_samples"] == 0
        assert s["p1_match_rate"] is None
        assert s["sp_breakdown"]["p1_match_rate"] is None
        assert s["date_range"] is None

    def test_no_blocks_skipped(self):
        s = aggregate_metrics([_NO_BLOCK, _NO_BLOCK])
        assert s["n_samples"] == 0

    def test_malformed_skipped_others_kept(self):
        s = aggregate_metrics([
            _MALFORMED,
            _block("2026-05-06", True, False, True, False),
        ])
        assert s["n_samples"] == 1
        assert s["sp_breakdown"]["p1_match_rate"] == 1.0

    def test_acceptance_seven_bodies_p1_match_rate(self):
        # Acceptance: 7 fixtures (5 sp_p1 True + 2 sp_p1 False) → 5/7 ≈ 0.714
        bodies = (
            [_block(f"2026-05-{d:02d}", True, False, True, False)
             for d in range(1, 6)]
            + [_block(f"2026-05-{d:02d}", False, False, False, False)
               for d in range(6, 8)]
        )
        s = aggregate_metrics(bodies)
        assert s["n_samples"] == 7
        assert s["sp_breakdown"]["p1_match_rate"] == pytest.approx(5 / 7, abs=1e-3)
        assert s["fa_breakdown"]["p1_match_rate"] == pytest.approx(5 / 7, abs=1e-3)
        assert s["date_range"] == ["2026-05-01", "2026-05-07"]

    def test_review_trigger_rate(self):
        bodies = [
            _block("2026-05-01", True, True, True, False),    # sp review True
            _block("2026-05-02", True, False, True, True),    # fa review True
            _block("2026-05-03", True, False, True, False),
        ]
        s = aggregate_metrics(bodies)
        assert s["sp_breakdown"]["review_trigger_rate"] == pytest.approx(1 / 3)
        assert s["fa_breakdown"]["review_trigger_rate"] == pytest.approx(1 / 3)

    def test_sp_fa_breakdown_independent(self):
        # SP all match, FA never match
        bodies = [
            _block(f"2026-05-{d:02d}", True, False, False, False)
            for d in range(1, 4)
        ]
        s = aggregate_metrics(bodies)
        assert s["sp_breakdown"]["p1_match_rate"] == 1.0
        assert s["fa_breakdown"]["p1_match_rate"] == 0.0
        assert s["p1_match_rate"] == 0.5  # avg of sp + fa

    def test_mixed_with_noise_bodies(self):
        # 3 valid blocks mixed with 2 noise bodies → still aggregate the 3
        bodies = [
            _NO_BLOCK,
            _block("2026-05-01", True, False, True, False),
            _MALFORMED,
            _block("2026-05-02", True, False, False, False),
            _block("2026-05-03", False, True, True, True),
        ]
        s = aggregate_metrics(bodies)
        assert s["n_samples"] == 3
        assert s["sp_breakdown"]["p1_match_rate"] == pytest.approx(2 / 3)
        assert s["fa_breakdown"]["p1_match_rate"] == pytest.approx(2 / 3)
        assert s["sp_breakdown"]["review_trigger_rate"] == pytest.approx(1 / 3)


# ── M4' (p1_pair_borderline) aggregation ────────────────────────

class TestP1PairBorderlineAggregation:
    def test_baseline_7_case_replay(self):
        # Re-emit baseline result: 3/7 SP P1-P2 + 3/7 FA top1-top2 borderline
        bodies = [
            _block("2026-05-04", True, True, True, True, sp_p1_pair=False, fa_top1_pair=False),
            _block("2026-05-20", True, True, False, True, sp_p1_pair=False, fa_top1_pair=True),
            _block("2026-05-21", True, True, False, True, sp_p1_pair=False, fa_top1_pair=False),
            _block("2026-05-22", False, True, True, True, sp_p1_pair=True, fa_top1_pair=True),
            _block("2026-05-23", False, True, False, True, sp_p1_pair=True, fa_top1_pair=False),
            _block("2026-05-24", True, True, True, True, sp_p1_pair=False, fa_top1_pair=False),
            _block("2026-05-25", False, True, False, True, sp_p1_pair=True, fa_top1_pair=True),
        ]
        s = aggregate_metrics(bodies)
        assert s["sp_breakdown"]["p1_pair_borderline_rate"] == pytest.approx(3 / 7)
        assert s["fa_breakdown"]["p1_pair_borderline_rate"] == pytest.approx(3 / 7)
        assert s["sp_breakdown"]["p1_pair_borderline_n"] == 7
        assert s["fa_breakdown"]["p1_pair_borderline_n"] == 7

    def test_backward_compat_missing_field(self):
        # Legacy issue body without the new fields — denominator excludes those
        bodies = [
            _block("2026-05-01", True, False, True, False, include_pair_fields=False),
            _block("2026-05-02", True, False, True, False, include_pair_fields=False),
            _block("2026-05-03", True, True, True, True, sp_p1_pair=True, fa_top1_pair=True),
            _block("2026-05-04", True, True, True, True, sp_p1_pair=False, fa_top1_pair=False),
        ]
        s = aggregate_metrics(bodies)
        # only 2 blocks have the new fields → denominator = 2, not 4
        assert s["sp_breakdown"]["p1_pair_borderline_n"] == 2
        assert s["fa_breakdown"]["p1_pair_borderline_n"] == 2
        assert s["sp_breakdown"]["p1_pair_borderline_rate"] == pytest.approx(0.5)
        assert s["fa_breakdown"]["p1_pair_borderline_rate"] == pytest.approx(0.5)

    def test_all_legacy_no_pair_field(self):
        bodies = [
            _block(f"2026-05-{d:02d}", True, False, True, False, include_pair_fields=False)
            for d in range(1, 4)
        ]
        s = aggregate_metrics(bodies)
        assert s["sp_breakdown"]["p1_pair_borderline_n"] == 0
        assert s["fa_breakdown"]["p1_pair_borderline_n"] == 0
        assert s["sp_breakdown"]["p1_pair_borderline_rate"] is None
        assert s["fa_breakdown"]["p1_pair_borderline_rate"] is None

    def test_empty_input_pair_rate_none(self):
        s = aggregate_metrics([])
        assert s["sp_breakdown"]["p1_pair_borderline_rate"] is None
        assert s["fa_breakdown"]["p1_pair_borderline_rate"] is None
        assert s["sp_breakdown"]["p1_pair_borderline_n"] == 0
