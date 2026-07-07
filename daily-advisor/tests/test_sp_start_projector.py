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


# ── retro-gate rules (2026-07-07: 85.0% on 2354 cells) ──

def test_probable_anchors_walk_no_same_turn_double_count():
    # last 06-10 cad 5 alone → {06-15, 06-20}; probable says the turn actually
    # falls 06-16. Old union counted 06-15 AND 06-16 (same turn, 2354-cell
    # retro: pred-2/actual-1 4×'d). New: walk continues FROM the probable.
    out = project_starts(
        date(2026, 6, 10), 5, MON, SUN,
        probable_dates=[date(2026, 6, 16)])
    assert out["projected_dates"] == [date(2026, 6, 16), date(2026, 6, 21)]
    assert out["starts"] == 2


def test_stale_last_start_suppresses_walk():
    # last start 06-01, cadence 5 → by 06-15 he has visibly missed a turn
    # (14 > 5+2): IL/demotion. No probables → 0, source "stale".
    out = project_starts(date(2026, 6, 1), 5, MON, SUN)
    assert out["starts"] == 0
    assert out["source"] == "stale"


def test_stale_with_probable_still_counts():
    # returning pitcher: stale by cadence but probable-listed → probable wins
    # and the walk continues from it (he is back on turn).
    out = project_starts(
        date(2026, 6, 1), 5, MON, SUN,
        probable_dates=[date(2026, 6, 16)])
    assert out["projected_dates"] == [date(2026, 6, 16), date(2026, 6, 21)]
    assert out["source"] == "probable"


def test_horizon_absence_suppresses_visibly_skipped_turn():
    # probables published through 06-19; candidate 06-15 sits ≥2 days inside
    # that horizon with no probable for him → visibly skipped. The 06-20
    # candidate is beyond the horizon → kept.
    out = project_starts(
        date(2026, 6, 10), 5, MON, SUN,
        probable_horizon_end=date(2026, 6, 19))
    assert out["projected_dates"] == [date(2026, 6, 20)]
    assert out["starts"] == 1


def test_gap_game_days_all_star_break_not_stale():
    # last start 06-04 = 11 calendar days before week_start (would be stale),
    # but the team only played 4 games in the gap (league-wide break) — the
    # pitcher has NOT visibly missed a turn.
    gap_days = [date(2026, 6, 6), date(2026, 6, 7),
                date(2026, 6, 13), date(2026, 6, 14)]
    out = project_starts(date(2026, 6, 4), 5, MON, SUN,
                         gap_game_days=gap_days)
    assert out["source"] == "cadence"
    assert out["starts"] >= 1


def test_gap_game_days_true_miss_still_stale():
    # team played 8 games since his last start without him → visibly off turn
    gap_days = [date(2026, 6, d) for d in range(5, 13)]
    out = project_starts(date(2026, 6, 4), 5, MON, SUN,
                         gap_game_days=gap_days)
    assert out["starts"] == 0
    assert out["source"] == "stale"


def test_horizon_edge_candidate_kept():
    # candidate 06-17 with horizon 06-18: a 1-2 day push would fall beyond
    # the horizon and be invisible → do not suppress.
    out = project_starts(
        date(2026, 6, 12), 5, MON, SUN,
        probable_horizon_end=date(2026, 6, 18))
    assert out["projected_dates"] == [date(2026, 6, 17)]
