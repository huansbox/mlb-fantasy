"""Unit tests for savant_rolling._aggregate_pitches.

Focus: xwOBACON computation (added 2026-04-26 for v4 framework's urgency
Step 2 third factor). Other aggregations (xwoba/barrel_pct/hh_pct/pa/bbe)
have implicit coverage via production cron output.
"""
from savant_rolling import _aggregate_pitches


def _row(game_date, at_bat_number, events="", xwoba=None, launch_speed=None,
         launch_speed_angle=None):
    """Build a minimal pitch-level CSV row dict for tests."""
    return {
        "game_date": game_date,
        "at_bat_number": str(at_bat_number),
        "events": events,
        "estimated_woba_using_speedangle": "" if xwoba is None else str(xwoba),
        "launch_speed": "" if launch_speed is None else str(launch_speed),
        "launch_speed_angle": "" if launch_speed_angle is None else str(launch_speed_angle),
    }


def test_aggregate_xwobacon_pure_contact():
    """All BBE no walks — xwobacon should equal xwoba × pa / bbe (no BB/HBP weight)."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5),
        _row("2026-04-01", 2, events="field_out", xwoba=0.3),
        _row("2026-04-02", 1, events="double", xwoba=0.4),
    ]
    result = _aggregate_pitches(rows)
    # xwobacon = (0.5 + 0.3 + 0.4) / 3 = 0.4
    assert result["xwobacon"] == 0.4
    # xwoba = (0×0.69 + 0×0.72 + 1.2) / 3 = 0.4 — same since no BB/HBP
    assert result["xwoba"] == 0.4
    assert result["bbe"] == 3
    assert result["pa"] == 3


def test_aggregate_xwobacon_diverges_from_xwoba_with_walks():
    """K/BB inflates PA in xwoba but not xwobacon — xwobacon > xwoba when K-heavy."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5),
        _row("2026-04-01", 2, events="walk"),
        _row("2026-04-01", 3, events="strikeout"),
    ]
    result = _aggregate_pitches(rows)
    # xwobacon = 0.5 / 1 = 0.5 (only the BBE counts)
    assert result["xwobacon"] == 0.5
    # xwoba = (1×0.69 + 0×0.72 + 0.5) / 3 ≈ 0.397
    assert result["xwoba"] == 0.397
    # xwobacon > xwoba — strikeout dilutes xwoba but not xwobacon
    assert result["xwobacon"] > result["xwoba"]
    assert result["bbe"] == 1
    assert result["pa"] == 3


def test_aggregate_returns_empty_when_bbe_zero():
    """All K/BB no contact — function returns {} (no xwobacon to compute)."""
    rows = [
        _row("2026-04-01", 1, events="walk"),
        _row("2026-04-01", 2, events="strikeout"),
        _row("2026-04-01", 3, events="hit_by_pitch"),
    ]
    result = _aggregate_pitches(rows)
    assert result == {}


def test_aggregate_xwobacon_single_bbe():
    """Edge: 1 BBE → xwobacon == that single value."""
    rows = [
        _row("2026-04-01", 1, events="home_run", xwoba=0.95),
    ]
    result = _aggregate_pitches(rows)
    assert result["xwobacon"] == 0.95
    assert result["bbe"] == 1


def test_aggregate_xwobacon_skips_missing_xwoba_value():
    """BBE rows with empty estimated_woba (rare data quality issue) — sum skips them.

    Documents existing behavior: bbe count includes these rows but
    xwobacon denominator is bbe_count, so a row with no xwoba effectively
    contributes 0 to numerator. Slight downward bias when this happens,
    but matches savant_rolling's pre-existing xwoba aggregation behavior.
    """
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5),
        _row("2026-04-01", 2, events="field_out"),  # no xwoba (data missing)
    ]
    result = _aggregate_pitches(rows)
    # bbe_count=2, sum_xwoba_on_bbe=0.5 → xwobacon = 0.5 / 2 = 0.25
    assert result["xwobacon"] == 0.25
    assert result["bbe"] == 2


def test_aggregate_xwobacon_present_for_pitcher_view():
    """Pitcher player_type also gets xwobacon (symmetric output)."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.4),
        _row("2026-04-01", 2, events="field_out", xwoba=0.2),
    ]
    result = _aggregate_pitches(rows, player_type="pitcher")
    assert "xwobacon" in result
    assert result["xwobacon"] == 0.3
