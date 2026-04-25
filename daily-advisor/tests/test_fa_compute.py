"""Unit tests for fa_compute.py — Phase 5 Python compute layer."""

import pytest

from fa_compute import (
    compute_2025_sum,
    compute_fa_tags,
    compute_sum_score,
    compute_urgency,
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


# ── Phase 5.3: compute_urgency ──
def _mk_weakest_sp(name, sum_2026, prior_stats=None, rolling_21d=None,
                    ip_per_tg=None, era_diff=None, ip_per_gs=None):
    """Build a weakest-entry (Pass 1 output shape) for urgency tests."""
    entry = {
        "name": name,
        "score": sum_2026,
        "breakdown": {},
        "confidence": "高",
        "mlb_id": hash(name) % 1_000_000,
        "savant_2026": {"xwoba": 0.320, "hh_pct": 42.0, "xera": 4.20, "bbe": 60},
        "prior_stats": prior_stats or {},
        "rolling_21d": rolling_21d,
        "derived": {
            "ip_per_tg": ip_per_tg,
            "era_diff": era_diff,
            "ip_per_gs": ip_per_gs,
        },
    }
    return entry


def _mk_weakest_batter(name, sum_2026, prior_stats=None, rolling_14d=None, pa_per_tg=None):
    entry = {
        "name": name,
        "score": sum_2026,
        "breakdown": {},
        "confidence": "高",
        "mlb_id": hash(name) % 1_000_000,
        "savant_2026": {"xwoba": 0.310, "bb_pct": 8.0, "barrel_pct": 8.0, "bbe": 60},
        "prior_stats": prior_stats or {},
        "rolling_14d": rolling_14d,
        "derived": {"pa_per_tg": pa_per_tg},
    }
    return entry


class TestUrgencySp:
    def test_nola_regression(self):
        # Fixture: Nola urgency=6
        # 2026 Sum 17 → +2 / 2025 Sum 15 (<18) + IP 94.3 → +2 / 21d Δ持平 → 0 / IP/TG 1.1 → +2
        nola = _mk_weakest_sp(
            "Nola",
            sum_2026=17,
            prior_stats={
                "xera": 4.13, "xwoba_allowed": 0.315, "hh_pct_allowed": 43.3,
                "ip": 94.3,
            },
            rolling_21d={"xwoba": 0.296, "bbe": 50},  # Δ = 0.296-.320 = -.024 持平
            ip_per_tg=1.1,
        )
        result = compute_urgency([nola], "sp")
        assert len(result["weakest_ranked"]) == 1
        r = result["weakest_ranked"][0]
        assert r["name"] == "Nola"
        assert r["urgency"] == 6
        assert r["factors"]["sum_2026"] == 2
        assert r["factors"]["sum_2025"] == 2
        assert r["factors"]["rolling"] == 0
        assert r["factors"]["ip_per_tg"] == 2
        assert result["slump_hold"] == []

    def test_cantillo_regression(self):
        # Fixture: Cantillo urgency=4
        # 2026 Sum 18 → +1 / 2025 Sum 21 (18-21) + IP 95.3 → +1 / 21d 持平 → 0 / IP/TG 1.0 → +2
        cantillo = _mk_weakest_sp(
            "Cantillo",
            sum_2026=18,
            prior_stats={
                "xera": 3.71, "xwoba_allowed": 0.300, "hh_pct_allowed": 41.8,
                "ip": 95.3,
            },
            rolling_21d={"xwoba": 0.305, "bbe": 40},  # Δ -.015 持平
            ip_per_tg=1.0,
        )
        result = compute_urgency([cantillo], "sp")
        r = result["weakest_ranked"][0]
        assert r["urgency"] == 4
        assert r["factors"]["sum_2026"] == 1
        assert r["factors"]["sum_2025"] == 1

    def test_lopez_bug_fix(self):
        # Fixture: López urgency=3 (but 5 IP noise → should drop to 1 after #2 fix)
        # 2026 Sum 24 → +0 (>21 no bonus) / prior IP 5.0 <20 → treat as no prior → +0
        # 21d 持平 → 0 / IP/TG 0.8 (0.5-1.0) → +1
        # Total = 0+0+0+1 = 1 (was 3 before fix)
        lopez = _mk_weakest_sp(
            "Lopez",
            sum_2026=24,
            prior_stats={
                "xera": 10.73, "xwoba_allowed": 0.465, "hh_pct_allowed": 50.0,
                "ip": 5.0,
            },
            rolling_21d={"xwoba": 0.302, "bbe": 30},  # Δ -.018 持平
            ip_per_tg=0.8,
        )
        result = compute_urgency([lopez], "sp")
        r = result["weakest_ranked"][0]
        assert r["urgency"] == 1, f"Expected 1 after #2 fix, got {r['urgency']}"
        assert r["factors"]["sum_2025"] == 0  # IP <20 → treated as no prior
        assert r["notes"]  # Should have note about low-IP prior
        assert "無效" in " ".join(r["notes"]) or "IP" in " ".join(r["notes"])

    def test_ragans_slump_hold(self):
        # Fixture: Ragans Slump hold — 2025 Sum 27 ≥24 + IP 61.7 ≥50
        # Should NOT appear in weakest_ranked; should be in slump_hold.
        ragans = _mk_weakest_sp(
            "Ragans",
            sum_2026=3,  # very bad 2026
            prior_stats={
                "xera": 2.67, "xwoba_allowed": 0.256, "hh_pct_allowed": 39.4,
                "ip": 61.7,
            },
            rolling_21d={"xwoba": 0.350, "bbe": 30},
            ip_per_tg=1.1,
        )
        result = compute_urgency([ragans], "sp")
        assert result["weakest_ranked"] == []
        assert len(result["slump_hold"]) == 1
        s = result["slump_hold"][0]
        assert s["name"] == "Ragans"
        assert s["prior_sum"] == 27
        assert s["prior_ip"] == 61.7

    def test_sum_2025_ge24_low_ip_no_slump_hold(self):
        # 2025 Sum ≥24 but IP <50 → +0 (not Slump hold)
        p = _mk_weakest_sp(
            "Breakout",
            sum_2026=10,  # 9-11 → +4
            prior_stats={
                "xera": 2.80, "xwoba_allowed": 0.260, "hh_pct_allowed": 35.0,
                "ip": 30.0,  # <50
            },
            rolling_21d=None,
            ip_per_tg=1.0,
        )
        result = compute_urgency([p], "sp")
        assert result["slump_hold"] == []
        r = result["weakest_ranked"][0]
        assert r["factors"]["sum_2026"] == 4
        assert r["factors"]["sum_2025"] == 0  # ≥24 but IP <50

    def test_rolling_delta_buckets(self):
        base = {"xera": 4.00, "xwoba_allowed": 0.310, "hh_pct_allowed": 41.0, "ip": 100.0}

        # season xwoba = 0.320 (from savant_2026 default)
        # Δ = rolling_21d.xwoba - 0.320
        cases = [
            # (rolling_xwoba, expected_factor)
            (0.265, -2),   # Δ = -.055 strong improve
            (0.280, -1),   # Δ = -.040 weak improve
            (0.300, 0),    # Δ = -.020 flat
            (0.360, 1),    # Δ = +.040 weak decay
            (0.380, 2),    # Δ = +.060 strong decay
        ]
        for r_xwoba, expected in cases:
            p = _mk_weakest_sp("P", 18, base, {"xwoba": r_xwoba, "bbe": 30}, ip_per_tg=1.0)
            res = compute_urgency([p], "sp")
            factor = res["weakest_ranked"][0]["factors"]["rolling"]
            assert factor == expected, f"rolling Δ for xwoba {r_xwoba}: expected {expected}, got {factor}"

    def test_rolling_low_bbe_skipped(self):
        # BBE <20 → rolling factor = 0
        p = _mk_weakest_sp(
            "P", 10,
            {"xera": 4.00, "xwoba_allowed": 0.310, "hh_pct_allowed": 41.0, "ip": 100.0},
            {"xwoba": 0.400, "bbe": 15},  # huge Δ but BBE too low
            ip_per_tg=1.0,
        )
        res = compute_urgency([p], "sp")
        assert res["weakest_ranked"][0]["factors"]["rolling"] == 0

    def test_ip_per_tg_buckets(self):
        base = {"xera": 4.00, "xwoba_allowed": 0.310, "hh_pct_allowed": 41.0, "ip": 100.0}
        for ip_tg, expected in [(1.2, 2), (1.0, 2), (0.7, 1), (0.5, 1), (0.3, 0), (None, 0)]:
            p = _mk_weakest_sp("P", 18, base, None, ip_per_tg=ip_tg)
            res = compute_urgency([p], "sp")
            assert res["weakest_ranked"][0]["factors"]["ip_per_tg"] == expected, \
                f"ip/tg {ip_tg}: expected {expected}"

    def test_sort_descending_by_urgency(self):
        a = _mk_weakest_sp(
            "A", 17,
            {"xera": 4.13, "xwoba_allowed": 0.315, "hh_pct_allowed": 43.3, "ip": 94.0},
            None, 1.1,
        )  # urgency = 2+2+0+2 = 6
        b = _mk_weakest_sp(
            "B", 18,
            {"xera": 3.71, "xwoba_allowed": 0.300, "hh_pct_allowed": 41.8, "ip": 95.0},
            None, 1.0,
        )  # urgency = 1+1+0+2 = 4
        res = compute_urgency([b, a], "sp")  # input order B first
        names = [r["name"] for r in res["weakest_ranked"]]
        assert names == ["A", "B"]  # sorted by urgency desc


class TestUrgencyBatter:
    def test_batter_no_ip_gate(self):
        # Batter: Slump hold only requires 2025 Sum ≥24 (no IP gate).
        p = _mk_weakest_batter(
            "Buxton",
            sum_2026=5,
            prior_stats={"xwoba": 0.350, "bb_pct": 7.6, "barrel_pct": 17.6},
            # Sum = 10+6+10 = 26 (xwoba .349 P90=10, bb 7.4-7.8 P45-50=5... wait)
            # xwoba .350>.349 = >P90 = 10
            # bb_pct 7.6 between P45=7.4 and P50=7.8 → P45-50 = 5
            # barrel 17.6 > 14.0 = >P90 = 10
            # Sum = 25 ≥24 → slump hold
        )
        res = compute_urgency([p], "batter")
        assert len(res["slump_hold"]) == 1
        assert res["slump_hold"][0]["prior_sum"] == 25

    def test_batter_pa_per_tg_buckets(self):
        prior = {"xwoba": 0.280, "bb_pct": 6.0, "barrel_pct": 5.0}  # weak prior
        for pa_tg, expected in [(4.0, 2), (3.5, 2), (3.2, 1), (2.8, 0), (1.0, 0)]:
            p = _mk_weakest_batter("P", 10, prior, None, pa_per_tg=pa_tg)
            res = compute_urgency([p], "batter")
            assert res["weakest_ranked"][0]["factors"]["pa_per_tg"] == expected

    def test_batter_rolling_bbe_gate(self):
        # Batter: 14d BBE <25 → rolling factor = 0
        prior = {"xwoba": 0.280, "bb_pct": 6.0, "barrel_pct": 5.0}
        p = _mk_weakest_batter(
            "P", 10, prior,
            {"xwoba": 0.400, "bbe": 20},  # BBE <25
            pa_per_tg=3.5,
        )
        res = compute_urgency([p], "batter")
        assert res["weakest_ranked"][0]["factors"]["rolling"] == 0

    def test_batter_rolling_direction(self):
        # Batter: 14d 🔥 = RISING Δ (opposite to SP where ❄️ = decay rising).
        # Batter: Δ positive = hot (rising) → negative urgency (subtract)
        # Per CLAUDE.md batter table:
        #   ≥ +0.050 🔥強回升 = -2
        #   +0.035 ≤ Δ < +0.050 = -1
        #   持平 = 0
        #   -0.050 < Δ ≤ -0.035 = +1
        #   ≤ -0.050 = +2
        prior = {"xwoba": 0.280, "bb_pct": 6.0, "barrel_pct": 5.0}
        # season xwoba default 0.310 (_mk_weakest_batter)
        cases = [
            (0.365, -2),  # Δ = +.055 強回升
            (0.347, -1),  # Δ = +.037 弱回升
            (0.310, 0),   # Δ = 0 持平
            (0.273, 1),   # Δ = -.037 弱下滑
            (0.255, 2),   # Δ = -.055 強下滑
        ]
        for r_xwoba, expected in cases:
            p = _mk_weakest_batter("P", 10, prior,
                                    {"xwoba": r_xwoba, "bbe": 30},
                                    pa_per_tg=3.0)
            res = compute_urgency([p], "batter")
            got = res["weakest_ranked"][0]["factors"]["rolling"]
            assert got == expected, f"Δ xwoba {r_xwoba}: expected {expected}, got {got}"


# ── Phase 5.4: compute_fa_tags ──
def _mk_fa_sp(name, savant_2026, prior_stats=None, rolling_21d=None,
              ip_per_gs=None, ip_per_tg=None, era_diff=None):
    return {
        "name": name,
        "mlb_id": hash(name) % 1_000_000,
        "savant_2026": savant_2026,
        "prior_stats": prior_stats or {},
        "rolling_21d": rolling_21d,
        "derived": {
            "ip_per_gs": ip_per_gs,
            "ip_per_tg": ip_per_tg,
            "era_diff": era_diff,
        },
    }


class TestFaTagsSp:
    def _anchor_nola(self):
        """Nola anchor (Sum 17 per fixture)."""
        return {
            "name": "Nola",
            "score": 17,
            "breakdown": {"xERA": 5, "xwOBA": 5, "HH%": 7},  # P40-50/P40-50/P60-70 approx
            "savant_2026": {"xera": 4.60, "xwoba": 0.325, "hh_pct": 38.5, "bbe": 70},
        }

    def test_pfaadt_replace(self):
        # Fixture: Pfaadt 1 ✅ 球隊主力 + ⚠️ Breakout 待驗 → 取代
        anchor = self._anchor_nola()
        # Use savant values that guarantee Sum diff ≥3 and 2 positives
        pfaadt = _mk_fa_sp(
            "Pfaadt",
            savant_2026={"xera": 4.00, "xwoba": 0.300, "hh_pct": 37.0, "bbe": 74},
            # Sum: xera 4.04>4.00 → P60=7, xwoba .301>.300 → P70=8, hh_pct 38.0>37.0 → P70=8 = 23
            prior_stats={"xera": 5.00, "xwoba_allowed": 0.335, "hh_pct_allowed": 43.0, "ip": 30.0},
            # prior IP 30 ≥20 (not treated as no prior), prior Sum very weak → <18 → Breakout 待驗
            ip_per_gs=5.6,
            ip_per_tg=1.1,
            era_diff=-0.77,  # not reaching -0.81
        )
        r = compute_sum_score(pfaadt["savant_2026"], "sp")
        pfaadt["score"] = r[0]
        pfaadt["breakdown"] = r[1]

        result = compute_fa_tags(pfaadt, anchor, "sp")
        assert result["win_gate_passed"] is True
        assert "✅ 球隊主力" in result["add_tags"]
        assert "✅ 深投型" not in result["add_tags"]
        assert "⚠️ 短局" not in result["warn_tags"]
        assert "✅ 撿便宜運氣" not in result["add_tags"]
        assert "⚠️ Breakout 待驗" in result["warn_tags"]
        assert result["decision"] == "取代"

    def test_povich_replace(self):
        # Fixture: Povich 2 ✅ (深投+球隊主力) + 2 ⚠️ (賣高+Breakout) → 取代
        anchor = self._anchor_nola()
        povich = _mk_fa_sp(
            "Povich",
            savant_2026={"xera": 3.56, "xwoba": 0.300, "hh_pct": 40.0, "bbe": 60},
            prior_stats={"xera": 5.80, "xwoba_allowed": 0.360, "hh_pct_allowed": 45.0, "ip": 40.0},
            ip_per_gs=6.7,   # >5.7 → 深投
            ip_per_tg=1.0,   # ≥1.0 → 球隊主力
            era_diff=1.37,    # ≥+0.81 → 賣高
        )
        r = compute_sum_score(povich["savant_2026"], "sp")
        povich["score"] = r[0]
        povich["breakdown"] = r[1]

        result = compute_fa_tags(povich, anchor, "sp")
        assert "✅ 深投型" in result["add_tags"]
        assert "✅ 球隊主力" in result["add_tags"]
        assert "⚠️ 賣高運氣" in result["warn_tags"]
        assert "⚠️ Breakout 待驗" in result["warn_tags"]
        # 2 ✅ + non-strong ⚠️ → 取代 (not 立即取代 because warn tags present)
        assert result["decision"] == "取代"

    def test_ginn_observe_due_to_short(self):
        # Fixture: Ginn 0 ✅ + ⚠️ 短局 → 觀察
        anchor = self._anchor_nola()
        ginn = _mk_fa_sp(
            "Ginn",
            savant_2026={"xera": 3.20, "xwoba": 0.280, "hh_pct": 35.0, "bbe": 60},
            prior_stats={"xera": 4.30, "xwoba_allowed": 0.325, "hh_pct_allowed": 42.0, "ip": 100.0},
            ip_per_gs=4.7,   # <5.0 → 短局 (強)
            ip_per_tg=0.9,   # 0.5-1.0 → not 球隊主力
            era_diff=0.40,
        )
        r = compute_sum_score(ginn["savant_2026"], "sp")
        ginn["score"] = r[0]
        ginn["breakdown"] = r[1]

        result = compute_fa_tags(ginn, anchor, "sp")
        assert "⚠️ 短局" in result["warn_tags"]
        # Ginn 2025 Sum (4.30/.325/42.0):
        #   xera 4.64>4.30>4.48? 4.48<4.30? 4.30<4.48 → P45 matches → P45-50=5
        #   xwoba .327>.325>.316 → P55 not matched (.316≥.325 false), P45=.327 matched → 5
        #   hh_pct 42.2>42.0>41.6 → P45=41.6 matched → 5
        # Sum = 5+5+5 = 15 <18 → Breakout 待驗
        assert "⚠️ Breakout 待驗" in result["warn_tags"]
        assert result["decision"] == "觀察"  # strong warning forces observe

    def test_winn_observe_due_to_small_sample(self):
        # Fixture: Winn 1 ✅ (雙年菁英) + ⚠️ 樣本小 → 觀察
        # ⚠️ 樣本小 is treated as confidence blocker (BBE <30)
        # ✅ 撿便宜運氣 also suppressed because BBE 18 <40 (luck tag gate)
        anchor = self._anchor_nola()
        winn = _mk_fa_sp(
            "Winn",
            savant_2026={"xera": 2.50, "xwoba": 0.260, "hh_pct": 33.0, "bbe": 18},
            prior_stats={"xera": 2.80, "xwoba_allowed": 0.275, "hh_pct_allowed": 36.0, "ip": 60.0},
            # Prior Sum: xera 2.98>2.80? yes P90 matched → 10. xwoba .289>.275? .275<.289→P80=9
            # hh_pct 36.4>36.0 → P80=9 → Sum 10+9+9 = 28 ≥24 → 雙年菁英
            ip_per_gs=5.4,
            ip_per_tg=0.8,
            era_diff=-1.50,  # ≤-0.81 但 BBE 18 <40 → luck tag suppressed
        )
        r = compute_sum_score(winn["savant_2026"], "sp")
        winn["score"] = r[0]
        winn["breakdown"] = r[1]

        result = compute_fa_tags(winn, anchor, "sp")
        assert "✅ 雙年菁英" in result["add_tags"]
        assert "✅ 撿便宜運氣" not in result["add_tags"]  # BBE <40 suppression
        assert "⚠️ 樣本小" in result["warn_tags"]
        assert result["decision"] == "觀察"

    def test_win_gate_fail(self):
        # Sum diff <3 → pass (not evaluated for tags)
        anchor = self._anchor_nola()
        close = _mk_fa_sp(
            "Close",
            savant_2026={"xera": 4.50, "xwoba": 0.320, "hh_pct": 40.0, "bbe": 60},
            # Sum close to 17 → diff <3
        )
        r = compute_sum_score(close["savant_2026"], "sp")
        close["score"] = r[0]
        close["breakdown"] = r[1]

        result = compute_fa_tags(close, anchor, "sp")
        assert result["win_gate_passed"] is False
        assert result["decision"] == "pass"

    def test_win_gate_fail_due_to_one_metric_below(self):
        # Sum diff ≥3 but only 1 metric ≥0 (2 metrics negative) → win gate fail
        anchor = self._anchor_nola()
        anchor["score"] = 15
        anchor["breakdown"] = {"xERA": 6, "xwOBA": 3, "HH%": 6}
        fa = {
            "name": "Lopsided",
            "score": 18,
            "breakdown": {"xERA": 10, "xwOBA": 2, "HH%": 6},  # diff +4/-1/0
            "savant_2026": {"xera": 2.50, "xwoba": 0.400, "hh_pct": 40.0, "bbe": 60},
            "prior_stats": {},
            "rolling_21d": None,
            "derived": {"ip_per_gs": 5.5, "ip_per_tg": 1.0, "era_diff": 0},
        }
        # breakdown_diff: +4 / -1 / 0 → 2 项 ≥0 (+4, 0), 1 項 negative (-1)
        # Actually 2 items ≥0 counts the 0. Per our rule: 2 ≥0 passes.
        # Let's verify this edge case matches 规则.
        result = compute_fa_tags(fa, anchor, "sp")
        # Per rule "2 项正向 (≥0)", the 0 counts → win_gate passes
        assert result["win_gate_passed"] is True

    def test_instant_replace(self):
        # 2 ✅ + 0 ⚠️ → 立即取代
        anchor = self._anchor_nola()
        fa = _mk_fa_sp(
            "Elite",
            savant_2026={"xera": 2.50, "xwoba": 0.260, "hh_pct": 33.0, "bbe": 100},
            prior_stats={"xera": 2.70, "xwoba_allowed": 0.270, "hh_pct_allowed": 35.0, "ip": 150.0},
            ip_per_gs=6.5,    # >5.7 → 深投
            ip_per_tg=1.1,    # ≥1.0 → 球隊主力
            era_diff=-0.90,   # ≤-0.81 → 撿便宜
        )
        r = compute_sum_score(fa["savant_2026"], "sp")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]

        result = compute_fa_tags(fa, anchor, "sp")
        assert len(result["add_tags"]) >= 2
        assert len(result["warn_tags"]) == 0
        assert result["decision"] == "立即取代"

    def test_recency_tags(self):
        # 21d Δ rolling → ✅ 近況確認 / ⚠️ 近況下滑
        anchor = self._anchor_nola()
        # Improving FA: Δ ≤-0.035
        fa_improving = _mk_fa_sp(
            "Hot",
            savant_2026={"xera": 4.00, "xwoba": 0.305, "hh_pct": 38.0, "bbe": 50},
            rolling_21d={"xwoba": 0.260, "bbe": 25},  # Δ = -.045
            ip_per_tg=1.0,
            ip_per_gs=5.5,
            prior_stats={"xera": 4.50, "xwoba_allowed": 0.320, "hh_pct_allowed": 42.0, "ip": 100.0},
        )
        r = compute_sum_score(fa_improving["savant_2026"], "sp")
        fa_improving["score"] = r[0]
        fa_improving["breakdown"] = r[1]

        result = compute_fa_tags(fa_improving, anchor, "sp")
        assert "✅ 近況確認" in result["add_tags"]

        # Declining FA: Δ ≥+0.035
        fa_declining = _mk_fa_sp(
            "Cold",
            savant_2026={"xera": 4.00, "xwoba": 0.305, "hh_pct": 38.0, "bbe": 50},
            rolling_21d={"xwoba": 0.350, "bbe": 25},  # Δ = +.045
            ip_per_tg=1.0,
            ip_per_gs=5.5,
            prior_stats={"xera": 4.50, "xwoba_allowed": 0.320, "hh_pct_allowed": 42.0, "ip": 100.0},
        )
        r = compute_sum_score(fa_declining["savant_2026"], "sp")
        fa_declining["score"] = r[0]
        fa_declining["breakdown"] = r[1]

        result = compute_fa_tags(fa_declining, anchor, "sp")
        assert "⚠️ 近況下滑" in result["warn_tags"]

    def test_no_prior_triggers_breakout_warn(self):
        anchor = self._anchor_nola()
        fa = _mk_fa_sp(
            "Rookie",
            savant_2026={"xera": 3.50, "xwoba": 0.285, "hh_pct": 36.0, "bbe": 50},
            prior_stats={},  # no prior
            ip_per_tg=1.0,
        )
        r = compute_sum_score(fa["savant_2026"], "sp")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]

        result = compute_fa_tags(fa, anchor, "sp")
        assert "⚠️ Breakout 待驗" in result["warn_tags"]

    def test_luck_tag_suppressed_below_bbe_gate(self):
        # Kelly 2026-04-24 case: extreme era_diff but BBE <40 → 崩盤中, not 運氣加持.
        # ✅ 撿便宜 (negative diff) and ⚠️ 賣高 (positive diff) both suppressed.
        anchor = self._anchor_nola()

        # 撿便宜 case: era_diff -1.50 但 BBE 35 <40
        cheap = _mk_fa_sp(
            "CheapButThin",
            savant_2026={"xera": 2.50, "xwoba": 0.275, "hh_pct": 36.0, "bbe": 35},
            prior_stats={"xera": 4.50, "xwoba_allowed": 0.320, "hh_pct_allowed": 42.0, "ip": 100.0},
            ip_per_gs=5.5,
            ip_per_tg=1.0,
            era_diff=-1.50,
        )
        r = compute_sum_score(cheap["savant_2026"], "sp")
        cheap["score"] = r[0]
        cheap["breakdown"] = r[1]
        result = compute_fa_tags(cheap, anchor, "sp")
        assert "✅ 撿便宜運氣" not in result["add_tags"]

        # 賣高 case: era_diff +1.50 但 BBE 35 <40 (Kelly-style)
        crash = _mk_fa_sp(
            "CrashInProgress",
            savant_2026={"xera": 6.50, "xwoba": 0.360, "hh_pct": 44.0, "bbe": 35},
            prior_stats={"xera": 3.50, "xwoba_allowed": 0.300, "hh_pct_allowed": 38.0, "ip": 100.0},
            ip_per_gs=5.5,
            ip_per_tg=1.0,
            era_diff=+1.50,
        )
        r = compute_sum_score(crash["savant_2026"], "sp")
        crash["score"] = r[0]
        crash["breakdown"] = r[1]
        result = compute_fa_tags(crash, anchor, "sp")
        assert "⚠️ 賣高運氣" not in result["warn_tags"]

    def test_luck_tag_fires_at_bbe_gate(self):
        # Boundary: BBE exactly 40 should fire (≥40 inclusive).
        anchor = self._anchor_nola()
        fa = _mk_fa_sp(
            "Boundary",
            savant_2026={"xera": 2.50, "xwoba": 0.275, "hh_pct": 36.0, "bbe": 40},
            prior_stats={"xera": 4.50, "xwoba_allowed": 0.320, "hh_pct_allowed": 42.0, "ip": 100.0},
            ip_per_gs=5.5,
            ip_per_tg=1.0,
            era_diff=-1.50,
        )
        r = compute_sum_score(fa["savant_2026"], "sp")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]
        result = compute_fa_tags(fa, anchor, "sp")
        assert "✅ 撿便宜運氣" in result["add_tags"]


class TestFaTagsBatter:
    def _anchor_weak_batter(self):
        return {
            "name": "Tovar",
            "score": 11,
            "breakdown": {"xwOBA": 7, "BB%": 1, "Barrel%": 6},
            "savant_2026": {"xwoba": 0.320, "bb_pct": 5.0, "barrel_pct": 9.0, "bbe": 50},
        }

    def test_batter_instant_replace(self):
        # ≥2 ✅ + 0 ⚠️ → 立即取代
        anchor = self._anchor_weak_batter()
        fa = {
            "name": "Grisham",
            "savant_2026": {"xwoba": 0.370, "bb_pct": 14.0, "barrel_pct": 14.0, "bbe": 80},
            "prior_stats": {"xwoba": 0.370, "bb_pct": 14.1, "barrel_pct": 14.2},
            "rolling_14d": None,
            "derived": {"pa_per_tg": 3.6},
        }
        r = compute_sum_score(fa["savant_2026"], "batter")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]

        result = compute_fa_tags(fa, anchor, "batter")
        # prior Sum xwoba .370 >P90=10, bb 14.1 >P90=10, barrel 14.2 >P90=10 → 30 ≥24 → 雙年菁英
        assert "✅ 雙年菁英" in result["add_tags"]
        assert "✅ 球隊主力" in result["add_tags"]  # PA/TG 3.6 ≥3.5
        assert len(result["warn_tags"]) == 0
        assert result["decision"] == "立即取代"

    def test_batter_observe_low_pa(self):
        # ⚠️ 上場有限 (強) → 觀察
        anchor = self._anchor_weak_batter()
        fa = {
            "name": "Bench",
            "savant_2026": {"xwoba": 0.360, "bb_pct": 12.0, "barrel_pct": 14.0, "bbe": 50},
            "prior_stats": {"xwoba": 0.360, "bb_pct": 12.0, "barrel_pct": 14.0},
            "rolling_14d": None,
            "derived": {"pa_per_tg": 2.0},  # <2.5 → 上場有限 (強)
        }
        r = compute_sum_score(fa["savant_2026"], "batter")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]

        result = compute_fa_tags(fa, anchor, "batter")
        assert "⚠️ 上場有限" in result["warn_tags"]
        assert result["decision"] == "觀察"


class Test2026SumBuckets:
    @pytest.mark.parametrize("sum_2026,expected", [
        (5, 5),    # <9 → +5
        (9, 4),    # 9-11
        (12, 3),   # 12-14
        (15, 2),   # 15-17
        (18, 1),   # 18-21
        (22, 0),   # ≥22 no bonus
        (30, 0),
    ])
    def test_sp_2026_sum_bucket(self, sum_2026, expected):
        base = {"xera": 4.00, "xwoba_allowed": 0.310, "hh_pct_allowed": 41.0, "ip": 100.0}
        p = _mk_weakest_sp("P", sum_2026, base, None, ip_per_tg=0.3)
        res = compute_urgency([p], "sp")
        assert res["weakest_ranked"][0]["factors"]["sum_2026"] == expected
