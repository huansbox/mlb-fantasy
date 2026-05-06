import json

import pytest

import payload_slimmer
from _phase6_sp import _build_fa_classify_payload, _build_step1_payload


FORBIDDEN_KEYS = {
    "score",
    "urgency",
    "factors",
    "sum",
    "sum_diff",
    "breakdown_diff",
    "win_gate_passed",
    "anchor_name",
}
FORBIDDEN_TAGS = {
    "✅ 雙年菁英",
    "✅ 深投型",
    "✅ GB 重型",
    "✅ K 壓制",
    "✅ 撿便宜運氣",
    "✅ 近況確認",
    "⚠️ 賣高運氣",
    "⚠️ xwOBACON 極端",
    "⚠️ K 壓制不足",
    "⚠️ Command 警示",
    "⚠️ 近況下滑",
    "⚠️ Breakout 待驗",
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
        assert not (set(d) & FORBIDDEN_KEYS)
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
        ],
        "warn_tags": [
            "⚠️ 樣本小",
            "⚠️ 短局",
            "⚠️ IL 短期",
            "⚠️ Swingman 角色",
            "⚠️ 賣高運氣",
            "⚠️ xwOBACON 極端",
            "⚠️ Command 警示",
        ],
        "notes": ["manual context"],
    }
    entry.update(overrides)
    return entry


@pytest.mark.parametrize("role", ["my_team", "fa"])
def test_slim_entry_removes_b1_anchor_fields_and_evaluation_tags(role):
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
    assert slim["prior_v4"]["slots"]["IP/GS"] == {"raw": 5.8, "percentile": 70}
    assert slim["prior_v4"]["slots"]["xwOBACON"] == {"raw": 0.352, "percentile": 70}
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


def test_phase6_builders_keep_b1_schema_clean_for_my_team_and_fa():
    anchor = _full_entry(name="Anchor Arm")
    fa = _full_entry(
        name="FA Arm",
        pct=18,
        d1=2,
        d3=5,
        waiver_date="",
        sum_diff=10,
        breakdown_diff={"IP/GS": 2},
        win_gate_passed=True,
        anchor_name="Anchor Arm",
    )
    urgency_result = {
        "weakest_ranked": [anchor],
        "slump_hold": [
            {
                "name": "Slump Hold",
                "prior_sum": 42,
                "prior_ip": 150.0,
                "prior_breakdown": {"sum": 42},
                "sum_2026": 16,
                "note": "菁英底，slump 候選",
            }
        ],
    }

    step1_payload = json.loads(_build_step1_payload(urgency_result, low_conf=[]))
    fa_payload = json.loads(_build_fa_classify_payload(anchor, [fa]))

    _assert_no_forbidden_schema(step1_payload)
    _assert_no_forbidden_schema(fa_payload)
    assert fa_payload["fa_candidates"][0]["pct"] == 18
    assert fa_payload["fa_candidates"][0]["d3"] == 5
