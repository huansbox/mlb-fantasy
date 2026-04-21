"""Unit tests for fa_compute.py — Phase 5 Python compute layer."""

import pytest

from fa_compute import (
    compute_2025_sum,
    compute_sum_score,
    metric_to_score,
    pick_weakest,
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


# ── Phase 5.2: pick_weakest ──
def _mk_batter(name, xwoba, bb_pct, barrel_pct, bbe=60, **kwargs):
    """Helper: build synthetic batter player dict with embedded savant_2026."""
    return {
        "name": name,
        "mlb_id": kwargs.get("mlb_id", hash(name) % 1_000_000),
        "savant_2026": {
            "xwoba": xwoba,
            "bb_pct": bb_pct,
            "barrel_pct": barrel_pct,
            "bbe": bbe,
            **kwargs.get("extra_savant", {}),
        },
        **{k: v for k, v in kwargs.items() if k not in ("mlb_id", "extra_savant")},
    }


def _mk_sp(name, xera, xwoba, hh_pct, bbe=60, **kwargs):
    """Helper: build synthetic SP player dict with embedded savant_2026."""
    return {
        "name": name,
        "mlb_id": kwargs.get("mlb_id", hash(name) % 1_000_000),
        "savant_2026": {
            "xera": xera,
            "xwoba": xwoba,
            "hh_pct": hh_pct,
            "bbe": bbe,
            **kwargs.get("extra_savant", {}),
        },
        **{k: v for k, v in kwargs.items() if k not in ("mlb_id", "extra_savant")},
    }


class TestPickWeakestBatter:
    def test_picks_bottom_4_by_sum(self):
        players = [
            _mk_batter("Elite1", 0.380, 13.0, 15.0),    # Sum 30
            _mk_batter("Strong", 0.320, 10.0, 11.0),    # Sum 7+9+8=24
            _mk_batter("Avg1", 0.300, 8.0, 8.0),        # Sum 6+6+6=18
            _mk_batter("Avg2", 0.295, 7.5, 7.5),        # Sum 5+5+5=15
            _mk_batter("Weak1", 0.280, 6.5, 6.0),       # Sum 3+3+3=9
            _mk_batter("Weak2", 0.270, 5.5, 5.0),       # Sum 3+1+3=7
            _mk_batter("Weak3", 0.260, 5.0, 4.5),       # Sum 1+1+1=3
        ]
        weakest, excluded = pick_weakest(players, "batter", n=4)
        names = [w["name"] for w in weakest]
        # Sum asc: Weak3(3), Weak2(7), Weak1(9), Avg2(15)
        assert names == ["Weak3", "Weak2", "Weak1", "Avg2"]
        assert excluded == []  # batter has no BBE filter

    def test_batter_low_bbe_still_included(self):
        # Batter: BBE<40 marked low_confidence but stays in rank (per CLAUDE.md).
        # fa_compute attaches confidence label; pick_weakest does not exclude.
        players = [
            _mk_batter("Weak1", 0.280, 6.0, 5.0, bbe=20),   # Sum ~7, BBE<40
            _mk_batter("Weak2", 0.270, 5.0, 4.0, bbe=60),   # Sum ~3
            _mk_batter("Avg1", 0.310, 9.0, 10.0, bbe=80),   # Sum ~21
        ]
        weakest, excluded = pick_weakest(players, "batter", n=4)
        # All included, but Weak1 should have confidence='低'
        assert len(weakest) == 3
        assert len(excluded) == 0
        weak1 = next(w for w in weakest if w["name"] == "Weak1")
        assert weak1["confidence"] == "低"

    def test_cant_cut_excluded(self):
        players = [
            _mk_batter("Skubal", 0.220, 4.0, 3.0),   # Worst Sum but cant_cut
            _mk_batter("Jazz", 0.230, 4.5, 3.5),     # 2nd worst but cant_cut
            _mk_batter("Good", 0.320, 10.0, 11.0),
            _mk_batter("Weak", 0.270, 5.5, 5.0),
        ]
        weakest, _ = pick_weakest(
            players, "batter", n=4,
            cant_cut={"Skubal", "Jazz"},
        )
        names = [w["name"] for w in weakest]
        assert "Skubal" not in names
        assert "Jazz" not in names
        assert names[0] == "Weak"

    def test_breakdown_in_output(self):
        players = [_mk_batter("P", 0.290, 7.0, 7.0)]
        weakest, _ = pick_weakest(players, "batter", n=4)
        assert weakest[0]["score"] > 0
        assert "xwOBA" in weakest[0]["breakdown"]
        assert "BB%" in weakest[0]["breakdown"]
        assert "Barrel%" in weakest[0]["breakdown"]


class TestPickWeakestSp:
    def test_low_bbe_moved_to_excluded(self):
        # Kelly-like: BBE 17 → low_confidence_excluded (not in weakest)
        players = [
            _mk_sp("Kelly", 4.00, 0.300, 40.0, bbe=17),
            _mk_sp("Nola", 4.20, 0.320, 43.0, bbe=80),
            _mk_sp("Cantillo", 4.00, 0.310, 42.0, bbe=70),
            _mk_sp("Lopez", 3.50, 0.290, 37.0, bbe=60),
            _mk_sp("Sale", 3.00, 0.275, 35.0, bbe=100),
        ]
        weakest, excluded = pick_weakest(players, "sp", n=4)
        names = [w["name"] for w in weakest]
        assert "Kelly" not in names
        assert any(e["name"] == "Kelly" for e in excluded)
        assert excluded[0]["bbe"] == 17

    def test_sp_sorted_by_sum_ascending(self):
        # SP sum reversed (lower xera = higher score).
        # Provide 5 SP, one with very high xera (weak) should come first.
        players = [
            _mk_sp("Nola", 4.20, 0.320, 43.0, bbe=80),    # Sum ≈ low
            _mk_sp("Sale", 3.00, 0.275, 35.0, bbe=100),   # Sum ≈ high
            _mk_sp("Cantillo", 4.00, 0.310, 42.0, bbe=70),
            _mk_sp("Skubal", 2.80, 0.260, 33.0, bbe=150),  # Elite
            _mk_sp("Weak", 5.50, 0.360, 46.0, bbe=60),    # Weakest
        ]
        weakest, _ = pick_weakest(players, "sp", n=4)
        # Ascending by Sum → Weak first
        assert weakest[0]["name"] == "Weak"
        # Skubal (elite) should not be in weakest 4 out of 5
        assert "Skubal" not in [w["name"] for w in weakest]

    def test_cant_cut_plus_bbe_low(self):
        players = [
            _mk_sp("Skubal", 2.70, 0.255, 32.0, bbe=150),
            _mk_sp("Kelly", 4.00, 0.300, 40.0, bbe=17),
            _mk_sp("Nola", 4.20, 0.320, 43.0, bbe=80),
            _mk_sp("Cantillo", 4.00, 0.310, 42.0, bbe=70),
        ]
        weakest, excluded = pick_weakest(
            players, "sp", n=4,
            cant_cut={"Skubal"},
        )
        names = [w["name"] for w in weakest]
        assert "Skubal" not in names
        assert "Kelly" not in names  # moved to excluded
        assert [e["name"] for e in excluded] == ["Kelly"]
        # Weakest should have Nola + Cantillo (only 2 left after cant_cut/excluded)
        assert set(names) == {"Nola", "Cantillo"}

    def test_confidence_labels(self):
        # SP: BBE ≥50 high; 30-50 medium; <30 excluded (not low)
        players = [
            _mk_sp("High", 4.00, 0.310, 42.0, bbe=60),
            _mk_sp("Med", 4.00, 0.310, 42.0, bbe=40),
        ]
        weakest, excluded = pick_weakest(players, "sp", n=4)
        by_name = {w["name"]: w for w in weakest}
        assert by_name["High"]["confidence"] == "高"
        assert by_name["Med"]["confidence"] == "中"
        assert excluded == []
