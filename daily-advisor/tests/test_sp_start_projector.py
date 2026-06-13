"""Unit tests for issue 046 / #325 — sp_start_projector."""

from datetime import date

from sp_start_projector import infer_cadence, project_starts

MON = date(2026, 6, 15)   # week_start
SUN = date(2026, 6, 21)   # week_end


def test_infer_cadence_median():
    starts = [date(2026, 6, 1), date(2026, 6, 6), date(2026, 6, 11)]  # gaps 5,5
    assert infer_cadence(starts) == 5


def test_infer_cadence_six_man():
    starts = [date(2026, 6, 1), date(2026, 6, 7), date(2026, 6, 13)]  # gaps 6,6
    assert infer_cadence(starts) == 6


def test_infer_cadence_default_when_too_few():
    assert infer_cadence([date(2026, 6, 1)]) == 5
    assert infer_cadence([]) == 5


def test_two_starts_in_window():
    # last start 06-10, cadence 5 → 06-15 + 06-20, both in [06-15, 06-21]
    out = project_starts(date(2026, 6, 10), 5, MON, SUN)
    assert out["starts"] == 2
    assert out["projected_dates"] == [date(2026, 6, 15), date(2026, 6, 20)]
    assert out["source"] == "cadence"


def test_one_start_in_window():
    # last start 06-12, cadence 5 → 06-17 (next 06-22 is out)
    out = project_starts(date(2026, 6, 12), 5, MON, SUN)
    assert out["starts"] == 1 and out["projected_dates"] == [date(2026, 6, 17)]


def test_zero_starts_when_cadence_skips_window():
    # last start 06-14, cadence 5 → 06-19 in window = 1; push last earlier
    out = project_starts(date(2026, 6, 9), 8, MON, SUN)  # next 06-17 only → 1
    assert out["starts"] == 1
    out0 = project_starts(date(2026, 6, 8), 14, MON, SUN)  # next 06-22 out → 0
    assert out0["starts"] == 0 and out0["source"] == "none"


def test_capped_at_two():
    # absurdly short cadence → still capped at 2
    out = project_starts(date(2026, 6, 13), 2, MON, SUN)
    assert out["starts"] == 2


def test_probable_overrides_and_is_authoritative():
    out = project_starts(
        date(2026, 6, 10), 5, MON, SUN,
        probable_dates=[date(2026, 6, 16)])
    assert date(2026, 6, 16) in out["projected_dates"]
    assert out["source"] == "probable"


def test_schedule_snap_to_game_day():
    # cadence lands 06-17 but team plays 06-18 (off-day 06-17) → snap +1
    out = project_starts(
        date(2026, 6, 12), 5, MON, SUN,
        schedule_dates=[date(2026, 6, 18), date(2026, 6, 19)])
    assert out["projected_dates"] == [date(2026, 6, 18)]


def test_schedule_no_game_near_drops_candidate():
    # cadence lands 06-17 but no game within ±1 → candidate dropped
    out = project_starts(
        date(2026, 6, 12), 5, MON, SUN,
        schedule_dates=[date(2026, 6, 21)])
    assert out["starts"] == 0


def test_probable_outside_window_ignored():
    out = project_starts(
        date(2026, 6, 10), 5, MON, SUN,
        probable_dates=[date(2026, 6, 25)])  # next week — ignored
    assert date(2026, 6, 25) not in out["projected_dates"]
