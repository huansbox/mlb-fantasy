"""Unit tests for fa_compute.py — Phase 5 Python compute layer."""

import pytest

from fa_compute import (
    compute_2025_sum,
    compute_fa_tags,
    compute_sum_score,
    compute_sum_score_v4_sp,
    compute_urgency,
    format_sp_breakdown_human,
    metric_to_score,
    pick_weakest,
    score_to_percentile_label,
    value_to_pctile,
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


class TestValueToPctileBatter:
    """Reverse-lookup percentile rank used by docs/batter-framework-upgrade-design.md §3.7."""

    @pytest.mark.parametrize(
        "xwoba,expected",
        [
            (0.200, 0),    # well below P25 → 0
            (0.260, 0),
            (0.261, 25),   # exactly P25
            (0.285, 25),
            (0.286, 40),
            (0.297, 50),
            (0.321, 70),
            (0.331, 80),
            (0.349, 95),   # P90 collapses to 95
            (0.400, 95),   # above-elite still 95
        ],
    )
    def test_xwoba_pctile(self, xwoba, expected):
        assert value_to_pctile(xwoba, "xwoba", "batter") == expected

    def test_none_returns_none(self):
        assert value_to_pctile(None, "xwoba", "batter") is None

    def test_unknown_metric_returns_none(self):
        assert value_to_pctile(0.300, "nonexistent", "batter") is None


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


# ── Phase 5.1: compute_2025_sum (batter prior_stats) ──
class TestCompute2025Sum:
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
        score, _ = compute_2025_sum({}, "batter")
        assert score == 0

    def test_none_prior(self):
        score, _ = compute_2025_sum(None, "batter")
        assert score == 0


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


class TestPickWeakestBatter:
    """Batter v4 thin (raw + multi-agent free reasoning) behavior.

    Hard rules: cant_cut excluded / BBE<40 → low_confidence_excluded /
    Sum ≥25 → strong, drop candidate excluded. n is ignored for batter —
    return all surviving Sum<25 entries sorted asc.
    See docs/batter-framework-upgrade-design.md §3.1.
    """

    def test_picks_all_below_sum_25(self):
        players = [
            _mk_batter("Elite1", 0.380, 13.0, 15.0),    # Sum 30 (≥25 → exclude)
            _mk_batter("Strong", 0.320, 10.0, 11.0),    # Sum 7+9+8=24 (<25 → keep)
            _mk_batter("Avg1", 0.300, 8.0, 8.0),        # Sum 6+6+6=18
            _mk_batter("Avg2", 0.295, 7.5, 7.5),        # Sum 5+5+5=15
            _mk_batter("Weak1", 0.280, 6.5, 6.0),       # Sum 3+3+3=9
            _mk_batter("Weak2", 0.270, 5.5, 5.0),       # Sum 3+1+3=7
            _mk_batter("Weak3", 0.260, 5.0, 4.5),       # Sum 1+1+1=3
        ]
        weakest, excluded = pick_weakest(players, "batter", n=4)
        names = [w["name"] for w in weakest]
        # All Sum<25, sorted asc; Elite1 (Sum 30) hard-floor excluded.
        assert names == ["Weak3", "Weak2", "Weak1", "Avg2", "Avg1", "Strong"]
        assert excluded == []  # all have BBE ≥40 default

    def test_batter_low_bbe_excluded(self):
        # Batter v4 thin: BBE<40 → low_confidence_excluded (not in pool).
        players = [
            _mk_batter("LowBbe", 0.280, 6.0, 5.0, bbe=20),  # Sum low but BBE<40 → excluded
            _mk_batter("Weak2", 0.270, 5.0, 4.0, bbe=60),
            _mk_batter("Avg1", 0.310, 9.0, 10.0, bbe=80),
        ]
        weakest, excluded = pick_weakest(players, "batter", n=4)
        names = [w["name"] for w in weakest]
        assert "LowBbe" not in names
        assert any(e["name"] == "LowBbe" for e in excluded)
        assert excluded[0]["bbe"] == 20

    def test_batter_sum_floor_25_excluded(self):
        # Sum ≥25 → strong, not a drop candidate.
        players = [
            _mk_batter("Mvp", 0.380, 13.0, 15.0),     # Sum 30 ≥25 → exclude
            _mk_batter("Strong", 0.350, 12.0, 14.0),  # ≈ Sum 30 ≥25 → exclude
            _mk_batter("Weak", 0.270, 5.0, 4.5),      # Sum ~3 → keep
        ]
        weakest, _ = pick_weakest(players, "batter", n=4)
        names = [w["name"] for w in weakest]
        assert names == ["Weak"]

    def test_no_n_cap(self):
        # 5 batters all Sum<25, all surviving (no n=4 cap).
        players = [
            _mk_batter(f"P{i}", 0.260 + i * 0.005, 5.0, 5.0)
            for i in range(5)
        ]
        weakest, _ = pick_weakest(players, "batter", n=4)
        assert len(weakest) == 5

    def test_cant_cut_excluded(self):
        players = [
            _mk_batter("Skubal", 0.220, 4.0, 3.0),
            _mk_batter("Jazz", 0.230, 4.5, 3.5),
            _mk_batter("Good", 0.320, 10.0, 11.0),  # Sum 7+9+8=24 (<25 → keep)
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
        players = [_mk_batter("P", 0.290, 7.0, 7.0)]  # Sum 5+5+5=15 (<25)
        weakest, _ = pick_weakest(players, "batter", n=4)
        assert weakest[0]["score"] > 0
        assert "xwOBA" in weakest[0]["breakdown"]
        assert "BB%" in weakest[0]["breakdown"]
        assert "Barrel%" in weakest[0]["breakdown"]


# ── Phase 5.3: compute_urgency ──
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


class TestUrgencyBatter:
    """Batter v4 thin: compute_urgency is passthrough — no factors, no ranking,
    no Slump hold detection (handled by cant_cut list).
    See docs/batter-framework-upgrade-design.md §1.2 + §1.3.
    """

    def test_batter_passthrough_no_factors(self):
        prior = {"xwoba": 0.280, "bb_pct": 6.0, "barrel_pct": 5.0}
        p = _mk_weakest_batter("P", 10, prior, None, pa_per_tg=3.5)
        res = compute_urgency([p], "batter")
        entry = res["weakest_ranked"][0]
        assert entry["urgency"] is None
        assert entry["factors"] == {}
        assert res["slump_hold"] == []

    def test_batter_no_slump_hold_detection(self):
        # Even with elite prior (Sum ≥24), batter compute_urgency does NOT
        # split into slump_hold — that's now handled by cant_cut list.
        elite_prior = {"xwoba": 0.380, "bb_pct": 13.0, "barrel_pct": 16.0}
        p = _mk_weakest_batter("Slumper", sum_2026=5, prior_stats=elite_prior)
        res = compute_urgency([p], "batter")
        assert res["slump_hold"] == []
        assert len(res["weakest_ranked"]) == 1

    def test_batter_prior_sum_preserved(self):
        # prior_sum is still computed (informational, useful for report layer).
        prior = {"xwoba": 0.380, "bb_pct": 13.0, "barrel_pct": 16.0}  # ~elite
        p = _mk_weakest_batter("P", 10, prior)
        res = compute_urgency([p], "batter")
        assert res["weakest_ranked"][0]["prior_sum"] >= 24  # elite prior

    def test_batter_order_preserved_from_pick_weakest(self):
        # passthrough preserves input order (pick_weakest already sorted asc).
        p1 = _mk_weakest_batter("First", sum_2026=3)
        p2 = _mk_weakest_batter("Second", sum_2026=8)
        p3 = _mk_weakest_batter("Third", sum_2026=15)
        res = compute_urgency([p1, p2, p3], "batter")
        names = [e["name"] for e in res["weakest_ranked"]]
        assert names == ["First", "Second", "Third"]


# ── Phase 5.4: compute_fa_tags ──
# v2 SP FA tag tests (TestFaTagsSp / _mk_fa_sp helper) removed in v2 SP cleanup
# commit. v4 SP FA tag tests live in tests/test_fa_compute_v4.py and
# tests/test_phase6_sp.py.


class TestFaTagsBatter:
    """Batter v4 thin: only PA-based ✅ 球隊主力 + ⚠️ 上場有限 retained.
    Other batter tags (✅ 雙年菁英 / ✅ 近況確認 / ⚠️ Breakout 待驗 / ⚠️ 近況下滑 /
    ⚠️ 樣本小) removed — multi-agent layer handles those signals from raw data.
    See docs/batter-framework-upgrade-design.md §7.1.
    """

    def _anchor_weak_batter(self):
        return {
            "name": "Tovar",
            "score": 11,
            "breakdown": {"xwOBA": 7, "BB%": 1, "Barrel%": 6},
            "savant_2026": {"xwoba": 0.320, "bb_pct": 5.0, "barrel_pct": 9.0, "bbe": 50},
        }

    def test_batter_replace_only_pa_gate(self):
        # 1 ✅ 球隊主力 + 0 ⚠️ → 取代 (was 立即取代 with old multi-tag set)
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
        assert "✅ 球隊主力" in result["add_tags"]
        # Removed: 雙年菁英 / 近況確認
        assert "✅ 雙年菁英" not in result["add_tags"]
        assert "✅ 近況確認" not in result["add_tags"]
        assert len(result["warn_tags"]) == 0
        # Only 1 ✅ → 取代 (per _decision_from_tags: ≥2 ✅ AND 0 ⚠️ → 立即取代)
        assert result["decision"] == "取代"

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

    def test_batter_no_legacy_warn_tags(self):
        # Removed warns must not fire even when their old preconditions hold.
        anchor = self._anchor_weak_batter()
        fa = {
            "name": "WeakPrior",
            "savant_2026": {"xwoba": 0.360, "bb_pct": 12.0, "barrel_pct": 14.0, "bbe": 25},  # BBE<30
            "prior_stats": {"xwoba": 0.250, "bb_pct": 4.0, "barrel_pct": 3.0},  # prior Sum <18
            "rolling_14d": {"xwoba": 0.300, "bbe": 30},  # Δ ≤ -0.035 (down)
            "derived": {"pa_per_tg": 3.5},
        }
        r = compute_sum_score(fa["savant_2026"], "batter")
        fa["score"] = r[0]
        fa["breakdown"] = r[1]

        result = compute_fa_tags(fa, anchor, "batter")
        # All these warns must be gone — agent layer handles via raw context.
        assert "⚠️ 樣本小" not in result["warn_tags"]
        assert "⚠️ Breakout 待驗" not in result["warn_tags"]
        assert "⚠️ 近況下滑" not in result["warn_tags"]


class TestBatterIlShortWarn:
    """Yahoo IL10/IL15 → ⚠️ IL 短期 warn tag → decision=觀察 (strong warn).

    Rationale: claim 後必須佔 IL slot，無法立即上場。LLM 看到 tag 自動降級
    至觀察，避免 Mize-style 兩天連推 IL FA。
    """

    def _anchor(self):
        return {
            "name": "Tovar",
            "score": 11,
            "breakdown": {"xwOBA": 7, "BB%": 1, "Barrel%": 6},
            "savant_2026": {"xwoba": 0.320, "bb_pct": 5.0, "barrel_pct": 9.0, "bbe": 50},
        }

    def _strong_fa(self, status):
        # Otherwise-strong FA so warn tag is the only differentiator.
        fa = {
            "name": "ILGuy",
            "savant_2026": {"xwoba": 0.370, "bb_pct": 14.0, "barrel_pct": 14.0, "bbe": 80},
            "prior_stats": {"xwoba": 0.370, "bb_pct": 14.1, "barrel_pct": 14.2},
            "rolling_14d": None,
            "derived": {"pa_per_tg": 3.6},
            "status": status,
        }
        score, breakdown = compute_sum_score(fa["savant_2026"], "batter")
        fa["score"] = score
        fa["breakdown"] = breakdown
        return fa

    @pytest.mark.parametrize("status", ["IL10", "IL15"])
    def test_short_il_tagged_and_decision_observes(self, status):
        result = compute_fa_tags(self._strong_fa(status), self._anchor(), "batter")
        assert "⚠️ IL 短期" in result["warn_tags"]
        assert result["decision"] == "觀察"

    @pytest.mark.parametrize("status", ["IL60", "DTD", "", None])
    def test_no_tag_for_other_status(self, status):
        result = compute_fa_tags(self._strong_fa(status), self._anchor(), "batter")
        assert "⚠️ IL 短期" not in result["warn_tags"]


# ── score → percentile label (v4 SP human display helper) ──
class TestScoreToPercentileLabel:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (10, ">P90"),
            (9, "P80-90"),
            (8, "P70-80"),
            (7, "P60-70"),
            (6, "P50-60"),
            (5, "P40-50"),
            (3, "P25-40"),
            (1, "<P25"),
            (0, "—"),  # input value was None
        ],
    )
    def test_known_scores(self, score, expected):
        assert score_to_percentile_label(score) == expected

    @pytest.mark.parametrize("score", [2, 4, 11, -1, 99])
    def test_unknown_scores_fallback(self, score):
        # v4_metric_to_score never returns 2/4/11+ — defensive fallback
        assert score_to_percentile_label(score) == "—"


class TestFormatSpBreakdownHuman:
    def test_v4_sp_breakdown_shape(self):
        # 模擬 compute_sum_score_v4_sp 產出的 5-slot breakdown
        breakdown = {
            "IP/GS": 7,
            "Whiff%": 1,
            "BB/9": 10,
            "GB%": 5,
            "xwOBACON": 9,
        }
        human = format_sp_breakdown_human(breakdown)
        assert human == {
            "IP/GS": "P60-70",
            "Whiff%": "<P25",
            "BB/9": ">P90",
            "GB%": "P40-50",
            "xwOBACON": "P80-90",
        }

    def test_round_trip_with_compute_sum_score_v4_sp(self):
        # 用 v4 elite SP 數據（每軸 P90+）跑完整管線
        elite_data = {
            "ip_gs": 6.20,    # >P90 (P90=6.11)
            "whiff_pct": 31.0,  # >P90 (P90=30.0)
            "bb9": 1.80,        # >P90 reverse (P90=1.96)
            "gb_pct": 55.0,     # >P90 (P90=54.6)
            "xwobacon": 0.335,  # >P90 reverse (P90=.341)
        }
        _, breakdown = compute_sum_score_v4_sp(elite_data)
        human = format_sp_breakdown_human(breakdown)
        assert all(v == ">P90" for v in human.values())

    def test_none_inputs_show_dash(self):
        # raw value None → score 0 → label "—"
        _, breakdown = compute_sum_score_v4_sp(
            {"ip_gs": None, "whiff_pct": None, "bb9": None,
             "gb_pct": None, "xwobacon": None}
        )
        human = format_sp_breakdown_human(breakdown)
        assert all(v == "—" for v in human.values())


