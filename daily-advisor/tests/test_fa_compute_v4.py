"""Unit tests for fa_compute.py v4 SP framework (parallel to v2).

v4 scoring uses 2025 real-data percentile bands for IP/GS, Whiff%, BB/9, GB%,
xwOBACON. BB/9 and xwOBACON are reverse-direction (lower = better).

See docs/sp-framework-v4-balanced.md.
"""

import pytest

from fa_compute import (
    PITCHER_V4_PCTILES,
    compute_sum_score_v4_sp,
    luck_tag_v4,
    rotation_gate_v4,
    v4_add_tags_sp,
    v4_decision_sp,
    v4_metric_to_score,
    v4_warn_tags_sp,
)


# ── v4_metric_to_score: forward metric (higher=better) ──

class TestV4ForwardMetric:
    @pytest.mark.parametrize("val,expected", [
        (5.20, 1),    # <P25 (P25=5.21)
        (5.21, 3),    # exactly P25
        (5.34, 3),    # P25-40
        (5.35, 5),    # exactly P40
        (5.40, 5),    # P40-50 (still < P45)
        (5.46, 6),    # P50
        (5.55, 6),    # still P50-60
        (5.61, 7),    # P60
        (5.73, 8),    # P70
        (5.89, 9),    # P80
        (6.11, 10),   # P90+
        (7.00, 10),   # way above P90
    ])
    def test_ip_gs(self, val, expected):
        assert v4_metric_to_score(val, "ip_gs") == expected


# ── v4_metric_to_score: reverse metric (lower=better) ──

class TestV4ReverseMetric:
    @pytest.mark.parametrize("val,expected", [
        (3.50, 1),    # above P25 (P25=3.47, lower=better so >P25 = <P25 elite = worst)
        (3.47, 3),    # exactly P25
        (3.17, 5),    # P40 (between P25 3.47 and P40 3.17)
        (2.95, 6),    # P50
        (2.38, 8),    # P70
        (1.96, 10),   # P90
        (1.50, 10),   # way better than P90
    ])
    def test_bb9(self, val, expected):
        assert v4_metric_to_score(val, "bb9") == expected

    @pytest.mark.parametrize("val,expected", [
        (0.424, 1),   # above P25 (0.386) = worst
        (0.386, 3),   # P25
        (0.375, 5),   # P40
        (0.370, 6),   # P50
        (0.356, 8),   # P70
        (0.341, 10),  # P90
        (0.300, 10),  # elite
    ])
    def test_xwobacon(self, val, expected):
        assert v4_metric_to_score(val, "xwobacon") == expected


class TestV4NoneHandling:
    def test_none_returns_zero(self):
        assert v4_metric_to_score(None, "ip_gs") == 0
        assert v4_metric_to_score(None, "bb9") == 0

    def test_unknown_metric_returns_zero(self):
        assert v4_metric_to_score(5.0, "unknown_metric") == 0


# ── compute_sum_score_v4_sp ──

class TestV4SumSP:
    def test_nola_2026(self):
        """Nola 2026-04-24: IP/GS 5.33 / Whiff 26.5 / BB/9 3.38 / GB% 40.8 / xwOBACON .424
        Expected: Sum 20 (middle-lower); Whiff% 26.5 exactly at P70 threshold → score 8"""
        data = {"ip_gs": 5.33, "whiff_pct": 26.5, "bb9": 3.38,
                "gb_pct": 40.8, "xwobacon": 0.424}
        total, bd = compute_sum_score_v4_sp(data)
        # 3 (IP/GS P25) + 8 (Whiff exactly P70) + 3 (BB/9 P25) + 5 (GB% P40) + 1 (xwOBACON<P25) = 20
        assert total == 20
        assert bd == {"IP/GS": 3, "Whiff%": 8, "BB/9": 3, "GB%": 5, "xwOBACON": 1}

    def test_lopez_2026(self):
        """Lopez 04-24: 5/5 indicators all at <P25 level → Sum minimal"""
        data = {"ip_gs": 4.33, "whiff_pct": 21.8, "bb9": 4.57,
                "gb_pct": 34.9, "xwobacon": 0.388}
        total, _ = compute_sum_score_v4_sp(data)
        # 1+3+1+1+1 = 7
        assert total == 7

    def test_skubal_2026(self):
        """Skubal — #1 SP. IP/GS 6.06 / Whiff 28.1 / BB/9 1.49 / GB% 46.4 / xwOBACON .381"""
        data = {"ip_gs": 6.06, "whiff_pct": 28.1, "bb9": 1.49,
                "gb_pct": 46.4, "xwobacon": 0.381}
        total, bd = compute_sum_score_v4_sp(data)
        # 9 (P80) + 9 (P80) + 10 (P90) + 7 (P60) + 3 (xwOBACON .381 just above P25=.386)
        assert total == 38
        assert bd["BB/9"] == 10
        assert bd["xwOBACON"] == 3

    def test_all_none_zero_sum(self):
        data = {"ip_gs": None, "whiff_pct": None, "bb9": None,
                "gb_pct": None, "xwobacon": None}
        total, _ = compute_sum_score_v4_sp(data)
        assert total == 0

    def test_partial_data(self):
        """Missing GB% (Horton BBE<30 case) scores 0 on that metric, others still work."""
        data = {"ip_gs": 3.67, "whiff_pct": 20.8, "bb9": 2.45,
                "gb_pct": None, "xwobacon": 0.298}
        total, bd = compute_sum_score_v4_sp(data)
        assert bd["GB%"] == 0
        # 1 + 1 + 8 + 0 + 10 = 20... wait let me compute:
        # Horton IP/GS 3.67 < P25 5.21 → 1
        # Whiff 20.8 < P25 21.3 → 1
        # BB/9 2.45 < P60 2.73 AND ≤ P70 2.38? No 2.45 > 2.38. So P60 = 7
        # GB% None → 0
        # xwOBACON .298 ≤ P90 .341 → 10
        assert total == 1 + 1 + 7 + 0 + 10


# ── rotation_gate_v4 ──

class TestRotationGate:
    @pytest.mark.parametrize("g,gs,expected_icon", [
        (5, 5, "🟢"),   # pure SP
        (4, 3, "🟢"),   # GS/G=0.75, GS=3 — meets both thresholds
        (6, 4, "🟢"),   # GS/G=0.67, GS=4
        (4, 2, "⚠️"),   # GS=2 → new-up
        (3, 1, "⚠️"),   # single start
        (8, 1, "🚫"),   # 1 GS / 8 G ratio 0.125 → long relief
        (8, 0, "🚫"),   # pure RP
        (10, 3, "⚠️"),  # ratio 0.3 — exactly at boundary, still swingman (< 0.6)
        (0, 0, "🚫"),   # bench
    ])
    def test_gate(self, g, gs, expected_icon):
        icon, desc = rotation_gate_v4(g, gs)
        assert icon == expected_icon

    def test_descriptor(self):
        _, desc = rotation_gate_v4(5, 5)
        assert desc == "rotation-SP"


# ── luck_tag_v4 ──

class TestLuckTag:
    def test_lucky_negative_diff(self):
        # xera < era → luck will regress up → ✅ 撿便宜 (currently low ERA too lucky)
        # Actually: xera 2.72 vs ERA 4.08 — xera - era = -1.36 ≤ -0.81 → ✅ 撿便宜運氣
        # (ERA running higher than xERA suggests, will regress down)
        assert luck_tag_v4(2.72, 4.08) == "✅ 撿便宜運氣"

    def test_unlucky_positive_diff(self):
        # xera 3.14 / era 1.76 — diff +1.38 ≥ +0.81 → ⚠️ 賣高運氣
        assert luck_tag_v4(3.14, 1.76) == "⚠️ 賣高運氣"

    def test_neutral(self):
        # Nola xera 4.67 / era 5.06 — diff -0.39, within ±0.81
        assert luck_tag_v4(4.67, 5.06) is None

    def test_boundary_exact(self):
        # Exactly -0.81 = ✅; exactly +0.81 = ⚠️
        assert luck_tag_v4(2.0, 2.81) == "✅ 撿便宜運氣"
        assert luck_tag_v4(4.0, 3.19) == "⚠️ 賣高運氣"

    def test_none_handling(self):
        assert luck_tag_v4(None, 3.0) is None
        assert luck_tag_v4(3.0, None) is None
        assert luck_tag_v4(None, None) is None


# ── v4 tag generation ──

class TestV4AddTags:
    def test_deep_starter(self):
        fa = {"savant_v4": {"ip_gs": 6.0, "whiff_pct": 25.0, "bb9": 3.0,
                             "gb_pct": 45.0, "xwobacon": 0.360,
                             "xera": 3.5, "era": 3.5, "bbe": 80, "ip": 40.0}}
        tags = v4_add_tags_sp(fa)
        assert "✅ 深投型" in tags

    def test_gb_heavy(self):
        fa = {"savant_v4": {"ip_gs": 5.0, "whiff_pct": 20.0, "bb9": 3.5,
                             "gb_pct": 55.0, "xwobacon": 0.380,
                             "xera": 4.0, "era": 4.0, "bbe": 80, "ip": 30.0}}
        tags = v4_add_tags_sp(fa)
        assert "✅ GB 重型" in tags

    def test_k_suppression(self):
        fa = {"savant_v4": {"ip_gs": 5.5, "whiff_pct": 28.0, "bb9": 3.0,
                             "gb_pct": 40.0, "xwobacon": 0.365,
                             "xera": 3.8, "era": 3.8, "bbe": 80, "ip": 40.0}}
        tags = v4_add_tags_sp(fa)
        assert "✅ K 壓制" in tags

    def test_lucky_add_tag(self):
        fa = {"savant_v4": {"ip_gs": 5.5, "whiff_pct": 24.0, "bb9": 3.0,
                             "gb_pct": 42.0, "xwobacon": 0.370,
                             "xera": 2.72, "era": 4.08, "bbe": 80, "ip": 30.0}}
        tags = v4_add_tags_sp(fa)
        assert "✅ 撿便宜運氣" in tags


class TestV4WarnTags:
    def test_small_sample(self):
        fa = {"savant_v4": {"ip_gs": 5.0, "whiff_pct": 25.0, "bb9": 3.0,
                             "gb_pct": 42.0, "xwobacon": 0.370,
                             "xera": 3.7, "era": 3.7, "bbe": 20, "ip": 10.0}}
        tags = v4_warn_tags_sp(fa)
        assert "⚠️ 樣本小" in tags

    def test_xwobacon_extreme(self):
        fa = {"savant_v4": {"ip_gs": 5.3, "whiff_pct": 26.0, "bb9": 3.0,
                             "gb_pct": 40.0, "xwobacon": 0.424,
                             "xera": 4.5, "era": 5.0, "bbe": 76, "ip": 27.0}}
        tags = v4_warn_tags_sp(fa)
        assert "⚠️ xwOBACON 極端" in tags

    def test_command_warning(self):
        fa = {"savant_v4": {"ip_gs": 5.0, "whiff_pct": 25.0, "bb9": 4.0,
                             "gb_pct": 42.0, "xwobacon": 0.370,
                             "xera": 4.0, "era": 4.0, "bbe": 60, "ip": 30.0}}
        tags = v4_warn_tags_sp(fa)
        assert "⚠️ Command 警示" in tags

    def test_swingman_role(self):
        fa = {"savant_v4": {"ip_gs": 5.0, "whiff_pct": 25.0, "bb9": 3.0,
                             "gb_pct": 42.0, "xwobacon": 0.370,
                             "xera": 3.8, "era": 3.8, "bbe": 60, "ip": 25.0},
              "rotation_gate": "⚠️"}
        tags = v4_warn_tags_sp(fa)
        assert "⚠️ Swingman 角色" in tags


# ── v4 decision logic ──

class TestV4Decision:
    def test_fail_sum_gate(self):
        # Sum diff < 5 → pass
        decision = v4_decision_sp(
            sum_diff=3,
            breakdown_diff={"IP/GS": 1, "Whiff%": 0, "BB/9": 1, "GB%": 1, "xwOBACON": 0},
            add_tags=["✅ 深投型"],
            warn_tags=[],
        )
        assert decision == "pass"

    def test_fail_positive_gate(self):
        # Sum diff ≥ 5 but only 2/5 positive → pass
        decision = v4_decision_sp(
            sum_diff=10,
            breakdown_diff={"IP/GS": 5, "Whiff%": -1, "BB/9": 6, "GB%": -3, "xwOBACON": 3},
            add_tags=["✅ 深投型"],
            warn_tags=[],
        )
        # positive count = 3 (IP/GS 5, BB/9 6, xwOBACON 3 — actually only 3 positive)
        # Wait: IP/GS 5, BB/9 6, xwOBACON 3 are positive, Whiff -1 GB -3 negative. 3/5.
        # So ≥3 positive, passes positive gate. With 1 ✅ no strong warn = 取代
        assert decision == "取代"

    def test_strong_warn_blocks(self):
        decision = v4_decision_sp(
            sum_diff=20,
            breakdown_diff={"IP/GS": 5, "Whiff%": 3, "BB/9": 4, "GB%": 5, "xwOBACON": 3},
            add_tags=["✅ 深投型", "✅ GB 重型"],
            warn_tags=["⚠️ 樣本小"],  # strong warn
        )
        assert decision == "觀察"

    def test_two_checks_no_warn_immediate(self):
        decision = v4_decision_sp(
            sum_diff=15,
            breakdown_diff={"IP/GS": 3, "Whiff%": 4, "BB/9": 3, "GB%": 2, "xwOBACON": 3},
            add_tags=["✅ 深投型", "✅ K 壓制"],
            warn_tags=[],
        )
        assert decision == "立即取代"

    def test_one_check_no_strong_warn_replace(self):
        decision = v4_decision_sp(
            sum_diff=10,
            breakdown_diff={"IP/GS": 2, "Whiff%": 3, "BB/9": 2, "GB%": 1, "xwOBACON": 2},
            add_tags=["✅ 深投型"],
            warn_tags=["⚠️ Command 警示"],  # non-strong warn
        )
        assert decision == "取代"

    def test_no_checks_observe(self):
        decision = v4_decision_sp(
            sum_diff=8,
            breakdown_diff={"IP/GS": 2, "Whiff%": 2, "BB/9": 2, "GB%": 1, "xwOBACON": 1},
            add_tags=[],
            warn_tags=[],
        )
        assert decision == "觀察"
