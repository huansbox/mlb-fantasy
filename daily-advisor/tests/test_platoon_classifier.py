"""Unit tests for issue 044 / #323 — platoon_classifier."""

from platoon_classifier import (
    LABEL_BENCH,
    LABEL_EVERYDAY,
    LABEL_PART,
    LABEL_STRONG,
    LABEL_UNKNOWN,
    LABEL_WEAK,
    classify_platoon,
    collect_platoon_games,
)


def _games(r_started, r_total, l_started, l_total):
    g = [{"started": i < r_started, "opp_hand": "R"} for i in range(r_total)]
    g += [{"started": i < l_started, "opp_hand": "L"} for i in range(l_total)]
    return g


def test_everyday():
    out = classify_platoon(_games(18, 20, 8, 8))   # plays both sides
    assert out["label"] == LABEL_EVERYDAY and out["tag"] is None


def test_strong_side_vs_rhp():
    # Pederson-type: starts vs RHP, sits vs LHP
    out = classify_platoon(_games(18, 20, 1, 8))   # vs R .90, vs L .125
    assert out["label"] == LABEL_STRONG
    assert "強側平台" in out["tag"]


def test_weak_side_vs_lhp():
    out = classify_platoon(_games(2, 20, 7, 8))     # vs R .10, vs L .875
    assert out["label"] == LABEL_WEAK and "弱側平台" in out["tag"]


def test_bench():
    out = classify_platoon(_games(2, 20, 1, 8))     # overall ~.107
    assert out["label"] == LABEL_BENCH


def test_part_time_in_between():
    out = classify_platoon(_games(12, 20, 4, 8))    # vs R .60, vs L .50
    assert out["label"] == LABEL_PART


def test_unknown_no_games():
    out = classify_platoon([])
    assert out["label"] == LABEL_UNKNOWN and out["tag"] is None


def test_single_hand_everyday():
    # only RHP faced, plays nearly all → everyday (provisional)
    out = classify_platoon(_games(19, 20, 0, 0))
    assert out["label"] == LABEL_EVERYDAY


def test_single_hand_part_time():
    out = classify_platoon(_games(10, 20, 0, 0))    # only R, .50
    assert out["label"] == LABEL_PART


def test_rates_reported():
    out = classify_platoon(_games(18, 20, 1, 8))
    assert out["start_rate_vs_r"] == 0.9
    assert out["start_rate_vs_l"] == 0.125
    assert round(out["overall_start_rate"], 3) == round(19 / 28, 3)


def test_pederson_retro_replay():
    # Retrospective Arraez→Pederson: strong-side platoon must be flagged so the
    # -28% weekly-PA loss is visible at decision time.
    pederson = _games(r_started=22, r_total=24, l_started=2, l_total=10)
    out = classify_platoon(pederson)
    assert out["label"] == LABEL_STRONG
    assert out["tag"] and "強側平台" in out["tag"]


# ── collect_platoon_games: cache ──

def test_collect_caches_boxscore_and_hand():
    # same game_pk + same pitcher repeated → fetched once each
    team_games = [
        {"game_pk": 1, "opp_starter_id": 100},
        {"game_pk": 1, "opp_starter_id": 100},  # dup game (cache hit)
        {"game_pk": 2, "opp_starter_id": 100},  # new game, same pitcher
        {"game_pk": 3, "opp_starter_id": 200},  # new game + pitcher
    ]
    box_calls, hand_calls = [], []

    def get_started(gpk):
        box_calls.append(gpk)
        return True

    def get_pitch_hand(pid):
        hand_calls.append(pid)
        return "R" if pid == 100 else "L"

    games, counts = collect_platoon_games(
        team_games, get_started=get_started, get_pitch_hand=get_pitch_hand)
    assert len(games) == 4
    assert counts["boxscore"] == 3   # game_pk 1,2,3 — dup 1 cached
    assert counts["pitch_hand"] == 2  # pitcher 100,200 — repeats cached
    assert games[-1]["opp_hand"] == "L"
