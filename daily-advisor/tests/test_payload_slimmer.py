"""Tests for payload_slimmer — B2 thin schema.

B2 schema (vs. B1):
- prior_v4 field removed entirely (2026-only data path).
- _ALLOWED_TAGS expanded: 2026-based + 21d-based evaluation tags now pass through.
- Still forbidden: machine anchors (score / sum / urgency / factors) and the
  2025-prior tags (✅ 雙年菁英 / ⚠️ Breakout 待驗).
"""

import pytest

import payload_slimmer


FORBIDDEN_KEYS = {
    "score",
    "urgency",
    "factors",
    "sum",
    "sum_diff",
    "breakdown_diff",
    "win_gate_passed",
    "anchor_name",
    "prior_v4",
    "prior_sum",
    "prior_ip",
    "prior_breakdown",
}
# Tags that B2 _ALLOWED_TAGS gates OUT (must never reach LLM payload).
FORBIDDEN_TAGS = {
    "✅ 雙年菁英",
    "⚠️ Breakout 待驗",
}
# Tags that B2 _ALLOWED_TAGS PASSES through (must remain visible).
ALLOWED_TAGS = {
    "✅ 球隊主力",
    "⚠️ 上場有限",
    "⚠️ 樣本小",
    "⚠️ 短局",
    "⚠️ IL 短期",
    "⚠️ Swingman 角色",
    "✅ 深投型",
    "✅ GB 重型",
    "✅ K 壓制",
    "✅ 撿便宜運氣",
    "✅ 近況確認",
    "⚠️ xwOBACON 極端",
    "⚠️ K 壓制不足",
    "⚠️ Command 警示",
    "⚠️ 賣高運氣",
    "⚠️ 近況下滑",
}


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _all_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _all_strings(value)


def _assert_no_forbidden_schema(obj):
    for d in _walk(obj):
        assert not (set(d) & FORBIDDEN_KEYS), f"forbidden key in {d}"
        if "breakdown" in d:
            assert "sum" not in (d.get("breakdown") or {})
    assert not (set(_all_strings(obj)) & FORBIDDEN_TAGS)


def _full_entry(**overrides):
    entry = {
        "name": "Test Arm",
        "team": "SEA",
        "position": "SP",
        "selected_pos": "BN",
        "status": "DTD",
        "score": 14,
        "breakdown": {
            "IP/GS": 3,
            "Whiff%": 5,
            "BB/9": 1,
            "GB%": 3,
            "xwOBACON": 1,
            "sum": 14,
        },
        "savant_v4": {
            "ip_gs": 5.2,
            "whiff_pct": 24.2,
            "bb9": 3.6,
            "gb_pct": 47.0,
            "xwobacon": 0.390,
            "xera": 4.9,
            "era": 3.7,
            "bbe": 42,
            "ip": 32.1,
            "g": 7,
            "gs": 6,
            "k9": 8.2,
            "whip": 1.33,
        },
        "prior_stats": {
            "ip": 110.0,
            "ip_gs": 5.8,
            "whiff_pct": 27.0,
            "bb9": 2.4,
            "gb_pct": 45.0,
            "xwobacon": 0.352,
        },
        "prior_sum": 38,
        "prior_ip": 110.0,
        "prior_breakdown": {"IP/GS": 8, "sum": 38},
        "rolling_21d": {"xwobacon": 0.410, "bbe": 21},
        "rolling_delta_xwobacon": 0.020,
        "rolling_bbe": 21,
        "urgency": 9,
        "factors": {"sum_2026": 5, "sum_2025": 2},
        "add_tags": [
            "✅ 球隊主力",
            "✅ 雙年菁英",
            "✅ 深投型",
            "✅ GB 重型",
            "✅ K 壓制",
            "✅ 撿便宜運氣",
            "✅ 近況確認",
        ],
        "warn_tags": [
            "⚠️ 樣本小",
            "⚠️ 短局",
            "⚠️ IL 短期",
            "⚠️ Swingman 角色",
            "⚠️ Breakout 待驗",
            "⚠️ 賣高運氣",
            "⚠️ xwOBACON 極端",
            "⚠️ K 壓制不足",
            "⚠️ Command 警示",
            "⚠️ 近況下滑",
        ],
        "notes": ["manual context"],
    }
    entry.update(overrides)
    return entry


@pytest.mark.parametrize("role", ["my_team", "fa"])
def test_slim_entry_removes_b2_anchor_fields_and_2025_tags(role):
    slim = payload_slimmer.slim_entry(
        _full_entry(
            pct=18,
            d1=1,
            d3=4,
            waiver_date="2026-05-07",
            sum_diff=12,
            breakdown_diff={"IP/GS": 3},
            win_gate_passed=True,
            anchor_name="Anchor Arm",
        ),
        role,
    )

    _assert_no_forbidden_schema(slim)
    assert slim["season_v4"]["slots"]["IP/GS"] == {"raw": 5.2, "percentile": 0}
    assert slim["season_v4"]["slots"]["Whiff%"] == {"raw": 24.2, "percentile": 50}
    assert slim["season_v4"]["slots"]["BB/9"] == {"raw": 3.6, "percentile": 0}
    assert slim["season_v4"]["slots"]["GB%"] == {"raw": 47.0, "percentile": 70}
    assert slim["season_v4"]["slots"]["xwOBACON"] == {"raw": 0.39, "percentile": 0}
    assert slim["rolling_21d"] == {
        "xwobacon": 0.410,
        "season_xwobacon": 0.390,
        "delta": 0.020,
        "bbe": 21,
    }
    assert slim["pa_tags"] == ["✅ 球隊主力"]
    assert slim["sample_tags"] == ["⚠️ 樣本小", "⚠️ 短局", "⚠️ IL 短期", "⚠️ Swingman 角色"]
    assert slim["low_confidence"] is False
    assert slim["selected_pos"] == "BN"
    assert slim["status"] == "DTD"


@pytest.mark.parametrize("role", ["my_team", "fa"])
def test_prior_v4_field_absent_from_output(role):
    slim = payload_slimmer.slim_entry(_full_entry(pct=18, d1=1, d3=4), role)
    assert "prior_v4" not in slim


def test_b2_allowed_tags_pass_through():
    """All B2-whitelisted tags reach the slimmed payload."""
    slim = payload_slimmer.slim_entry(_full_entry(), "my_team")
    actual_tags = set(slim["add_tags"]) | set(slim["warn_tags"])
    # Every fixture tag that is allowed must appear in output.
    fixture_allowed = (
        set(_full_entry()["add_tags"]) | set(_full_entry()["warn_tags"])
    ) & ALLOWED_TAGS
    assert fixture_allowed.issubset(actual_tags)


def test_b2_forbidden_tags_filtered_out():
    """2025-prior tags ✅ 雙年菁英 / ⚠️ Breakout 待驗 must not reach LLM."""
    slim = payload_slimmer.slim_entry(_full_entry(), "my_team")
    actual_tags = set(slim["add_tags"]) | set(slim["warn_tags"])
    assert not (actual_tags & FORBIDDEN_TAGS)


def test_slim_entry_fa_only_fields_are_role_scoped():
    my_team = payload_slimmer.slim_entry(_full_entry(pct=18, d1=1, d3=4), "my_team")
    fa = payload_slimmer.slim_entry(
        _full_entry(pct=18, d1=1, d3=4, waiver_date="2026-05-07"),
        "fa",
    )

    for field in ("pct", "d1", "d3", "waiver_date"):
        assert field not in my_team
        assert field in fa


def test_slim_entry_marks_low_confidence_from_bbe():
    slim = payload_slimmer.slim_entry(
        _full_entry(savant_v4={**_full_entry()["savant_v4"], "bbe": 24}),
        "my_team",
    )

    assert slim["low_confidence"] is True


def test_slim_entry_unknown_role_raises():
    with pytest.raises(ValueError):
        payload_slimmer.slim_entry(_full_entry(), "bench")  # type: ignore[arg-type]
