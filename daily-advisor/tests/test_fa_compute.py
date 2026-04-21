"""Unit tests for fa_compute.py — Phase 5 Python compute layer."""

import pytest

from fa_compute import (
    compute_2025_sum,
    compute_sum_score,
    metric_to_score,
)


# ── Phase 5.1: metric_to_score per-bucket ──
# 2025 batter xwoba percentile thresholds:
#   P25 .261, P40 .286, P45 .293, P50 .297, P55 .302, P60 .307,
#   P70 .321, P80 .331, P90 .349
class TestMetricToScoreBatter:
    @pytest.mark.parametrize(
        "xwoba,expected",
        [
            (0.200, 1),   # <P25
            (0.260, 1),   # still <P25
            (0.261, 3),   # exactly P25 → P25-40
            (0.285, 3),   # P25-40
            (0.286, 5),   # exactly P40 → P40-50
            (0.296, 5),   # P40-50
            (0.297, 6),   # exactly P50 → P50-60
            (0.306, 6),   # P50-60
            (0.307, 7),   # exactly P60 → P60-70
            (0.320, 7),   # P60-70
            (0.321, 8),   # exactly P70 → P70-80
            (0.330, 8),   # P70-80
            (0.331, 9),   # exactly P80 → P80-90
            (0.348, 9),   # P80-90
            (0.349, 10),  # exactly P90 → >P90
            (0.400, 10),  # way above P90
        ],
    )
    def test_xwoba_buckets(self, xwoba, expected):
        assert metric_to_score(xwoba, "xwoba", "batter") == expected

    def test_none_returns_zero(self):
        assert metric_to_score(None, "xwoba", "batter") == 0


# 2025 SP xERA percentile thresholds (reverse direction: lower = better):
#   P25 5.62, P40 4.64, P45 4.48, P50 4.33, P55 4.16, P60 4.04,
#   P70 3.74, P80 3.43, P90 2.98
class TestMetricToScoreSp:
    @pytest.mark.parametrize(
        "xera,expected",
        [
            (7.00, 1),    # >P25 threshold (worse)
            (5.63, 1),    # still <P25 (worse than 5.62)
            (5.62, 3),    # exactly P25 → P25-40
            (4.65, 3),    # P25-40
            (4.64, 5),    # exactly P40 → P40-50
            (4.34, 5),    # P40-50
            (4.33, 6),    # exactly P50 → P50-60
            (4.05, 6),    # P50-60
            (4.04, 7),    # exactly P60 → P60-70
            (3.75, 7),    # P60-70
            (3.74, 8),    # exactly P70 → P70-80
            (3.44, 8),    # P70-80
            (3.43, 9),    # exactly P80 → P80-90
            (2.99, 9),    # P80-90
            (2.98, 10),   # exactly P90 → >P90
            (2.50, 10),   # better than P90
        ],
    )
    def test_xera_buckets(self, xera, expected):
        assert metric_to_score(xera, "xera", "sp") == expected


# ── Phase 5.1: compute_sum_score ──
class TestComputeSumBatter:
    def test_weak_hitter(self):
        # All <P25: 1+1+1 = 3
        metrics = {"xwoba": 0.200, "bb_pct": 4.0, "barrel_pct": 3.0}
        score, breakdown = compute_sum_score(metrics, "batter")
        assert score == 3
        assert breakdown == {"xwOBA": 1, "BB%": 1, "Barrel%": 1}

    def test_elite_hitter(self):
        # All >P90: 10+10+10 = 30
        metrics = {"xwoba": 0.400, "bb_pct": 15.0, "barrel_pct": 16.0}
        score, breakdown = compute_sum_score(metrics, "batter")
        assert score == 30
        assert breakdown == {"xwOBA": 10, "BB%": 10, "Barrel%": 10}

    def test_tovar_like(self):
        # Tovar 2025 prior: xwoba .319, bb_pct 5.4, barrel_pct 9.3
        # → xwoba P60-70=7, bb_pct <P25=1, barrel_pct P60-70=7 → 15
        metrics = {"xwoba": 0.319, "bb_pct": 5.4, "barrel_pct": 9.3}
        score, _ = compute_sum_score(metrics, "batter")
        assert score == 15

    def test_missing_metrics_give_zero(self):
        metrics = {"xwoba": 0.300}  # bb_pct and barrel_pct missing
        score, breakdown = compute_sum_score(metrics, "batter")
        assert breakdown["xwOBA"] == 6
        assert breakdown["BB%"] == 0
        assert breakdown["Barrel%"] == 0
        assert score == 6


class TestComputeSumSp:
    def test_elite_sp(self):
        # All >P90: 10+10+10 = 30
        metrics = {"xera": 2.50, "xwoba": 0.250, "hh_pct": 30.0}
        score, breakdown = compute_sum_score(metrics, "sp")
        assert score == 30
        assert breakdown == {"xERA": 10, "xwOBA": 10, "HH%": 10}

    def test_weak_sp(self):
        # All <P25: 1+1+1 = 3
        metrics = {"xera": 7.00, "xwoba": 0.400, "hh_pct": 50.0}
        score, breakdown = compute_sum_score(metrics, "sp")
        assert score == 3

    def test_nola_2025_like(self):
        # Nola 2025 prior per CLAUDE.md: xera 4.13, xwoba .315, hh_pct 43.3
        # → xera 4.04<4.13<4.33 = P50-60=6
        #   xwoba .312<.315<.316 = P55-60=6 (per table P55=.316, P60=.312)
        #     Actually .316 is P55; value .315 just under it → treated as P50-55=6
        #     (our bucket is P50-60, score 6, so both work)
        #   hh_pct 42.2<43.3<44.2 = P25-40=3
        # Sum = 6+6+3 = 15 (matches fixture)
        metrics = {"xera": 4.13, "xwoba": 0.315, "hh_pct": 43.3}
        score, breakdown = compute_sum_score(metrics, "sp")
        assert score == 15
        assert breakdown["xERA"] == 6
        assert breakdown["xwOBA"] == 6
        assert breakdown["HH%"] == 3


# ── Phase 5.1: compute_2025_sum (key mapping for SP prior_stats) ──
class TestCompute2025Sum:
    def test_sp_prior_key_mapping(self):
        # SP prior_stats uses xwoba_allowed / hh_pct_allowed keys.
        # Nola 2025: xera 4.13, xwoba_allowed 0.315, hh_pct_allowed 43.3
        # → Sum should match 15 per fixture
        prior = {
            "xera": 4.13,
            "xwoba_allowed": 0.315,
            "hh_pct_allowed": 43.3,
        }
        score, _ = compute_2025_sum(prior, "sp")
        assert score == 15

    def test_batter_prior(self):
        # Tovar 2025 prior_stats
        prior = {
            "xwoba": 0.319,
            "bb_pct": 5.4,
            "barrel_pct": 9.3,
        }
        score, _ = compute_2025_sum(prior, "batter")
        assert score == 15

    def test_empty_prior(self):
        score, _ = compute_2025_sum({}, "sp")
        assert score == 0

    def test_none_prior(self):
        score, _ = compute_2025_sum(None, "sp")
        assert score == 0

    def test_skubal_elite_2025(self):
        # Skubal 2025 prior: xera 2.71, xwoba_allowed .258, hh_pct_allowed 33.0
        # → 2.98>2.71 = >P90 = 10
        #   .258<.270 = >P90 = 10
        #   33.0<34.1 = >P90 = 10  → Sum 30
        prior = {"xera": 2.71, "xwoba_allowed": 0.258, "hh_pct_allowed": 33.0}
        score, _ = compute_2025_sum(prior, "sp")
        assert score == 30

    def test_ragans_elite_slump_base(self):
        # Ragans 2025 prior: xera 2.67, xwoba_allowed .256, hh_pct_allowed 39.4
        # → xera 2.67<2.98 = >P90 = 10
        #   xwoba .256<.270 = >P90 = 10
        #   hh_pct 39.4<40.2 but >38.0 = P55-60 bucket... wait
        #     P55 40.2, P60 39.4 (reverse). 39.4=P60 → P60-70=7
        # Sum = 10+10+7 = 27 (matches fixture "Ragans 2025 Sum 27")
        prior = {"xera": 2.67, "xwoba_allowed": 0.256, "hh_pct_allowed": 39.4}
        score, _ = compute_2025_sum(prior, "sp")
        assert score == 27
