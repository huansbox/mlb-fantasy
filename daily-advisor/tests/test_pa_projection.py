"""Unit tests for issue 045 / #324 — pa_projection."""

from pa_projection import (
    expected_starts,
    project_weekly_categories,
    project_weekly_pa,
)

EVERYDAY = {"start_rate_vs_r": 0.95, "start_rate_vs_l": 0.95,
            "overall_start_rate": 0.95}
STRONG_SIDE = {"start_rate_vs_r": 0.90, "start_rate_vs_l": 0.10,
               "overall_start_rate": 0.55}  # Pederson-type


def _week(r, l):
    return [{"opp_hand": "R"}] * r + [{"opp_hand": "L"}] * l


def test_expected_starts_everyday():
    # 7-game week, all start ~0.95
    assert round(expected_starts(_week(4, 3), EVERYDAY), 2) == round(7 * 0.95, 2)


def test_expected_starts_strong_side_loses_lhp_games():
    # 4 RHP (0.90) + 3 LHP (0.10) = 3.6 + 0.3 = 3.9 starts
    assert round(expected_starts(_week(4, 3), STRONG_SIDE), 2) == 3.9


def test_unknown_hand_uses_overall():
    games = [{"opp_hand": None}, {"opp_hand": "R"}]
    assert round(expected_starts(games, STRONG_SIDE), 2) == 1.45  # 0.55 + 0.90


def test_project_weekly_pa_everyday_vs_strong_side():
    pa_e = project_weekly_pa(_week(4, 3), EVERYDAY, pa_per_start=4.3)
    pa_s = project_weekly_pa(_week(4, 3), STRONG_SIDE, pa_per_start=4.3)
    assert pa_e["projected_pa"] > pa_s["projected_pa"]   # the volume blind spot
    # everyday ~6.65 starts × 4.3 ≈ 28.6; strong-side 3.9 × 4.3 ≈ 16.8
    assert pa_s["projected_pa"] < pa_e["projected_pa"] * 0.75  # ~28% fewer PA


def test_project_weekly_pa_shape():
    out = project_weekly_pa(_week(4, 3), EVERYDAY, pa_per_start=4.3)
    assert out["games"] == 7 and out["expected_starts"] > 0


def test_project_weekly_categories_uses_shared_arithmetic():
    cats = project_weekly_categories(
        {"HR": 0.05, "R": 0.15, "OPS": 0.850}, projected_pa=28)
    assert cats["HR"] == 0.05 * 28      # counting scaled
    assert cats["OPS"] == 0.850         # ratio passthrough


def test_zero_pa_per_start():
    out = project_weekly_pa(_week(4, 3), EVERYDAY, pa_per_start=0)
    assert out["projected_pa"] == 0.0


def test_empty_schedule():
    out = project_weekly_pa([], EVERYDAY, pa_per_start=4.3)
    assert out["games"] == 0 and out["projected_pa"] == 0.0
