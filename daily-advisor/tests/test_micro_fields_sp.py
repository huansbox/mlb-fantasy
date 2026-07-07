"""Unit tests for issue 050 / #329 — micro_fields_sp pure compute."""

from micro_fields_sp import (
    compute_velo,
    kbb_ladder,
    velo_tag,
)


# ── compute_velo ──

ROLLING = {"velo_fb": 94.2, "velo_fb_type": "FF", "velo_fb_last_game": 93.5}


def test_velo_full_windows():
    v = compute_velo(ROLLING, {"FF": 95.5, "SI": 93.0}, {"FF": 96.1})
    assert v == {
        "fb_type": "FF", "velo_21d": 94.2, "velo_season": 95.5,
        "velo_prior_season": 96.1, "d21_vs_season": -1.3, "yoy": -0.6,
        "last_game": 93.5,
    }


def test_velo_same_pitch_type_only():
    # season has SI but the rolling primary FB is FF → no cross-type delta
    v = compute_velo(ROLLING, {"SI": 93.0}, None)
    assert v["velo_season"] is None
    assert v["d21_vs_season"] is None
    assert v["yoy"] is None


def test_velo_no_rolling():
    assert compute_velo(None, {"FF": 95.0}, None) is None
    assert compute_velo({"velo_fb": None}, {"FF": 95.0}, None) is None


def test_velo_no_prior_no_fabricated_yoy():
    v = compute_velo(ROLLING, {"FF": 95.0}, {})
    assert v["yoy"] is None
    assert v["d21_vs_season"] == -0.8


# ── velo_tag ──

def test_velo_tag_down():
    v = compute_velo(ROLLING, {"FF": 95.5}, None)   # d21 = -1.3
    assert velo_tag(v) == "⚠️ 球速下滑 (FF -1.3 vs season)"


def test_velo_tag_up():
    v = compute_velo({"velo_fb": 96.6, "velo_fb_type": "SI"}, {"SI": 95.5}, None)
    assert velo_tag(v) == "✅ 球速上升 (SI +1.1 vs season)"


def test_velo_tag_below_threshold_none():
    v = compute_velo({"velo_fb": 95.0, "velo_fb_type": "FF"}, {"FF": 95.5}, None)
    assert velo_tag(v) is None      # -0.5 < 1.0 mph


def test_velo_tag_no_season_none():
    v = compute_velo(ROLLING, None, None)
    assert velo_tag(v) is None


# ── kbb_ladder ──

def test_kbb_stable_tier():
    out = kbb_ladder(k=25, bb=8, bf=90)
    assert out["tier"] == "stable"
    assert out["kbb_pct"] == 18.9
    assert out["k_pct"] == 27.8
    assert out["bb_pct"] == 8.9
    assert out["bf"] == 90


def test_kbb_early_and_noise_tiers():
    assert kbb_ladder(10, 5, 50)["tier"] == "early"
    assert kbb_ladder(5, 2, 20)["tier"] == "noise"


def test_kbb_boundaries():
    assert kbb_ladder(1, 0, 70)["tier"] == "stable"
    assert kbb_ladder(1, 0, 69)["tier"] == "early"
    assert kbb_ladder(1, 0, 40)["tier"] == "early"
    assert kbb_ladder(1, 0, 39)["tier"] == "noise"


def test_kbb_no_bf_none():
    assert kbb_ladder(5, 2, 0) is None
    assert kbb_ladder(5, 2, None) is None


def test_kbb_none_counts_treated_zero():
    out = kbb_ladder(None, None, 50)
    assert out["kbb_pct"] == 0.0
