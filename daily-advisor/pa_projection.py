"""Next-week PA projection — P-b (issue 045 / #324).

Turns a batter's platoon profile + the team's upcoming schedule into an
expected weekly PA, then (via the shared 043 arithmetic) into per-category
counting expectations. This is what makes the volume blind spot visible: a
strong-side platoon bat facing a week of same-side starters projects far fewer
PA than an everyday bat, so 047's swap vector can surface the −28%-PA trade the
retrospective lost (Arraez→Pederson).

Pure — the schedule (game days + opposing-starter hands) and the platoon profile
are passed in; reuses `weekly_projection.project` rather than re-deriving the
rate×volume math.
"""

from __future__ import annotations

from weekly_projection import project


def expected_starts(games, platoon) -> float:
    """Expected started games over the window: sum of the player's start rate
    for each game's opposing-starter hand. Falls back to the overall start rate
    when a hand is unknown or that-hand rate is missing."""
    overall = platoon.get("overall_start_rate") or 0.0
    total = 0.0
    for g in games:
        hand = g.get("opp_hand")
        if hand == "R":
            rate = platoon.get("start_rate_vs_r")
        elif hand == "L":
            rate = platoon.get("start_rate_vs_l")
        else:
            rate = None
        total += overall if rate is None else rate
    return total


def project_weekly_pa(games, platoon, pa_per_start) -> dict:
    """Project next-week PA from schedule × platoon × PA/start."""
    es = expected_starts(games, platoon)
    pa = es * (pa_per_start or 0.0)
    return {
        "games": len(games),
        "expected_starts": round(es, 2),
        "projected_pa": round(pa, 1),
    }


def project_weekly_categories(per_pa_rates, projected_pa) -> dict:
    """Per-category weekly expectation from per-PA rates × projected PA, via the
    shared 043 arithmetic (counting scale, ratio passthrough)."""
    return project(per_pa_rates, projected_pa)
