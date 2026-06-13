"""Unit tests for savant_rolling._aggregate_pitches.

Focus: xwOBACON computation (added 2026-04-26 for v4 framework's urgency
Step 2 third factor). Other aggregations (xwoba/barrel_pct/hh_pct/pa/bbe)
have implicit coverage via production cron output.
"""
from savant_rolling import _aggregate_pitches


def _row(game_date, at_bat_number, events="", xwoba=None, launch_speed=None,
         launch_speed_angle=None, woba_value=None, woba_denom=None):
    """Build a minimal pitch-level CSV row dict for tests."""
    return {
        "game_date": game_date,
        "at_bat_number": str(at_bat_number),
        "events": events,
        "estimated_woba_using_speedangle": "" if xwoba is None else str(xwoba),
        "launch_speed": "" if launch_speed is None else str(launch_speed),
        "launch_speed_angle": "" if launch_speed_angle is None else str(launch_speed_angle),
        "woba_value": "" if woba_value is None else str(woba_value),
        "woba_denom": "" if woba_denom is None else str(woba_denom),
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


# ── Issue 035: actual rolling wOBA (woba_value / woba_denom) ──


def test_aggregate_woba_from_woba_value_denom():
    """woba = Σ woba_value / Σ woba_denom over PA-ending events."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5,
             woba_value=0.9, woba_denom=1),
        _row("2026-04-01", 2, events="strikeout", woba_value=0.0, woba_denom=1),
        _row("2026-04-01", 3, events="walk", woba_value=0.69, woba_denom=1),
    ]
    result = _aggregate_pitches(rows)
    # woba = (0.9 + 0.0 + 0.69) / 3 = 0.53
    assert result["woba"] == 0.53


def test_aggregate_woba_none_when_columns_missing():
    """Old fixtures / CSVs without woba columns → woba stays None (graceful)."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5),
    ]
    result = _aggregate_pitches(rows)
    assert result.get("woba") is None


def test_aggregate_woba_skips_zero_denom_events():
    """woba_denom=0 events (e.g. sac bunt) excluded from denominator."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.5,
             woba_value=0.9, woba_denom=1),
        _row("2026-04-01", 2, events="sac_bunt", woba_value=0.0, woba_denom=0),
    ]
    result = _aggregate_pitches(rows)
    assert result["woba"] == 0.9


def test_aggregate_xwobacon_present_for_pitcher_view():
    """Pitcher player_type also gets xwobacon (symmetric output)."""
    rows = [
        _row("2026-04-01", 1, events="single", xwoba=0.4),
        _row("2026-04-01", 2, events="field_out", xwoba=0.2),
    ]
    result = _aggregate_pitches(rows, player_type="pitcher")
    assert "xwobacon" in result
    assert result["xwobacon"] == 0.3


# ── issue #329: per-pitch CSW% + velocity aggregation ──

from savant_rolling import _pitch_level_metrics  # noqa: E402


def _pitch(description="", pitch_type="", release_speed=None,
           game_date="2026-04-01", at_bat_number=1, events=""):
    return {
        "description": description,
        "pitch_type": pitch_type,
        "release_speed": "" if release_speed is None else str(release_speed),
        "game_date": game_date,
        "at_bat_number": str(at_bat_number),
        "events": events,
        "estimated_woba_using_speedangle": "",
        "launch_speed": "", "launch_speed_angle": "",
        "woba_value": "", "woba_denom": "",
    }


def test_pitch_level_csw_counts_called_and_swinging():
    rows = [
        _pitch(description="called_strike"),
        _pitch(description="swinging_strike"),
        _pitch(description="swinging_strike_blocked"),
        _pitch(description="foul_tip"),
        _pitch(description="ball"),
        _pitch(description="foul"),       # foul (not foul_tip) is NOT CSW
    ]
    m = _pitch_level_metrics(rows)
    assert m["pitches"] == 6
    assert m["csw_pct"] == round(4 / 6 * 100, 1)   # 4 CSW of 6


def test_pitch_level_velocity_by_type_and_primary_fastball():
    rows = [
        _pitch(pitch_type="FF", release_speed=97.0, description="ball"),
        _pitch(pitch_type="FF", release_speed=99.0, description="called_strike"),
        _pitch(pitch_type="SI", release_speed=96.0, description="ball"),
        _pitch(pitch_type="SL", release_speed=88.0, description="swinging_strike"),
    ]
    m = _pitch_level_metrics(rows)
    assert m["velo_by_type"]["FF"] == 98.0
    assert m["velo_by_type"]["SL"] == 88.0
    assert m["velo_fb_type"] == "FF"   # most-thrown fastball type
    assert m["velo_fb"] == 98.0


def test_pitch_level_empty():
    assert _pitch_level_metrics([]) == {}


def test_pitch_level_missing_velo_skipped():
    rows = [_pitch(pitch_type="FF", release_speed=None, description="ball"),
            _pitch(pitch_type="FF", release_speed=98.0, description="ball")]
    m = _pitch_level_metrics(rows)
    assert m["velo_by_type"]["FF"] == 98.0   # the None one skipped from avg
    assert m["pitches"] == 2                  # but still counted as a pitch


def test_pitcher_aggregate_merges_csw_and_velo():
    # rows that pass the BBE gate AND carry pitch-level fields
    rows = [
        _pitch(description="called_strike", pitch_type="FF", release_speed=97.0,
               at_bat_number=1),
        _pitch(description="swinging_strike", pitch_type="FF", release_speed=98.0,
               at_bat_number=1),
        _pitch(description="hit_into_play", pitch_type="SI", release_speed=96.0,
               at_bat_number=1, events="field_out"),
    ]
    result = _aggregate_pitches(rows, player_type="pitcher")
    assert result.get("csw_pct") == round(2 / 3 * 100, 1)
    assert result.get("velo_fb") == 97.5
    assert result.get("pitches") == 3


def test_batter_aggregate_has_no_csw():
    rows = [_pitch(description="called_strike", at_bat_number=1),
            _pitch(events="single", at_bat_number=1,
                   description="hit_into_play")]
    result = _aggregate_pitches(rows, player_type="batter")
    assert "csw_pct" not in result   # pitch-level metrics are pitcher-only
