"""Unit tests for issue 043 / #322 — weekly_projection arithmetic."""

import math

from weekly_projection import project, ratio_weight


def test_counting_is_linear():
    out = project({"HR": 0.05, "R": 0.15, "RBI": 0.12}, volume=28)
    assert out["HR"] == 0.05 * 28
    assert out["R"] == 0.15 * 28
    assert out["RBI"] == 0.12 * 28


def test_ratio_passthrough():
    out = project({"OPS": 0.850, "AVG": 0.290}, volume=28)
    assert out["OPS"] == 0.850 and out["AVG"] == 0.290  # not scaled


def test_mixed_counting_and_ratio():
    out = project({"HR": 0.05, "OPS": 0.850}, volume=20)
    assert out["HR"] == 1.0 and out["OPS"] == 0.850


def test_volume_zero():
    out = project({"HR": 0.05, "OPS": 0.850}, volume=0)
    assert out["HR"] == 0.0 and out["OPS"] == 0.850  # counting→0, ratio stays


def test_none_rate_skipped():
    out = project({"HR": None, "R": 0.15}, volume=10)
    assert "HR" not in out and out["R"] == 1.5


def test_unknown_category_passthrough():
    out = project({"MYSTERY": 0.3}, volume=10)
    assert out["MYSTERY"] == 0.3  # safe default: treat as rate


def test_sp_counting_categories():
    out = project({"K": 1.0, "IP": 6.0, "QS": 0.6}, volume=2)  # 2 starts
    assert out["K"] == 2.0 and out["IP"] == 12.0 and out["QS"] == 1.2


def test_sp_ratio_passthrough():
    out = project({"ERA": 3.50, "WHIP": 1.10}, volume=2)
    assert out["ERA"] == 3.50 and out["WHIP"] == 1.10


def test_ratio_weight_sqrt():
    assert ratio_weight(25) == 5.0
    assert ratio_weight(28) == math.sqrt(28)


def test_ratio_weight_zero_and_none():
    assert ratio_weight(0) == 0.0
    assert ratio_weight(None) == 0.0
    assert ratio_weight(-5) == 0.0
