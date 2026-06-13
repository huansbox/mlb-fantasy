"""Unit tests for issue 048 / #327 — swap_sp."""

from swap_sp import (
    format_swap_line_sp,
    per_start_vector,
    project_sp_weekly,
    should_emit_swap,
    swap_vector_sp,
)

RATES = {"ip_per_gs": 6.0, "k9": 9.0, "qs_rate": 0.6,
         "team_win_pct": 0.55, "era": 3.50, "whip": 1.10}


def test_per_start_vector():
    v = per_start_vector(RATES)
    assert v["IP"] == 6.0
    assert v["K"] == 9.0 * 6.0 / 9   # 6.0 K per start
    assert v["QS"] == 0.6
    assert v["W"] == 0.55 * 0.5      # team win% × decision rate
    assert v["ERA"] == 3.50 and v["WHIP"] == 1.10


def test_per_start_vector_missing_fields_zero():
    v = per_start_vector({"ip_per_gs": 5.0})
    assert v["IP"] == 5.0 and v["K"] == 0.0 and v["W"] == 0.0


def test_project_sp_weekly_two_starts():
    w = project_sp_weekly(RATES, starts=2)
    assert w["IP"] == 12.0          # 6.0 × 2
    assert w["K"] == 12.0           # 6.0 × 2
    assert w["QS"] == 1.2           # 0.6 × 2
    assert w["ERA"] == 3.50         # ratio passthrough (not × starts)
    assert w["WHIP"] == 1.10


def test_volume_lever_two_start_beats_one_start_better_sp():
    # mid SP 2 starts vs better SP 1 start → mid wins IP/K/QS volume
    mid = project_sp_weekly(RATES, starts=2)
    better = project_sp_weekly(
        {"ip_per_gs": 6.3, "k9": 10.5, "qs_rate": 0.7,
         "team_win_pct": 0.6, "era": 3.0, "whip": 1.0}, starts=1)
    vec = swap_vector_sp(mid, better)
    assert vec["IP"] > 0 and vec["K"] > 0 and vec["QS"] > 0  # volume wins
    assert vec["ERA"] > 0           # mid's ERA worse (higher) — the trade-off


def test_swap_vector_sp_ratio_negative_when_candidate_better():
    cand = project_sp_weekly({**RATES, "era": 3.0, "whip": 1.0}, starts=1)
    inc = project_sp_weekly(RATES, starts=1)
    vec = swap_vector_sp(cand, inc)
    assert vec["ERA"] == -0.5 and vec["WHIP"] < 0   # candidate better


def test_emit_gate_shared():
    assert should_emit_swap(4) and not should_emit_swap(3)


def test_format_swap_line_sp():
    vec = {"IP": 5.2, "K": 4.0, "QS": 0.3, "W": 0.1, "ERA": -0.40, "WHIP": -0.05}
    line = format_swap_line_sp("Incumbent", "Candidate", vec)
    assert line.startswith("swap Incumbent→Candidate/week: ")
    assert "IP +5.2" in line and "ERA -0.4" in line
    assert line.index("IP") < line.index("ERA")   # counting before ratio
