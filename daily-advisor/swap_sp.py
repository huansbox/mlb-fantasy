"""Swap-vector — SP (issue 048 / #326's pitcher sibling, #327).

For a 4★+ SP candidate, the per-pitcher-category weekly delta versus the named
incumbent (add ⇄ drop). The volume lever for SP is START COUNT (046): IP, K,
QS, W all scale with starts, so a 2-start mid SP can out-produce a 1-start
better SP across four contested pitching categories.

per_start_vector turns an SP's rates into one start's production; project_sp_
weekly multiplies the counting part by the projected starts (via the shared 043
arithmetic) and passes ERA/WHIP through as ratios; swap_vector_sp differences
two weekly projections. Emission reuses the 4★ gate from swap_batter. Payload
injection is 318b.
"""

from __future__ import annotations

from swap_batter import should_emit_swap  # shared 4★ emission gate
from weekly_projection import RATIO, project

# An SP factors into a decision on roughly half their starts; W per start ≈
# team win% × this. Rough coefficient — a context estimate, not a projection.
W_DECISION_RATE = 0.5

_ORDER = ("IP", "W", "K", "QS", "SVH", "ERA", "WHIP")


def per_start_vector(rates) -> dict:
    """One start's expected production from an SP's rates.
    rates: {ip_per_gs, k9, qs_rate, team_win_pct, era, whip}. IP/K/QS/W are
    counting; ERA/WHIP ride along as the SP's ratio rates."""
    ip = rates.get("ip_per_gs") or 0.0
    return {
        "IP": ip,
        "K": (rates.get("k9") or 0.0) * ip / 9,
        "QS": rates.get("qs_rate") or 0.0,
        "W": (rates.get("team_win_pct") or 0.0) * W_DECISION_RATE,
        "ERA": rates.get("era"),
        "WHIP": rates.get("whip"),
    }


def project_sp_weekly(rates, starts) -> dict:
    """Weekly SP category expectation = per-start counting × starts (043
    arithmetic), ERA/WHIP passthrough."""
    return project(per_start_vector(rates), starts)


def swap_vector_sp(cand_weekly, inc_weekly) -> dict:
    """Per-category weekly delta = candidate − incumbent. Counting 1dp, ratio
    (ERA/WHIP) 3dp — a negative ERA/WHIP delta means the candidate is better."""
    vec = {}
    for cat in set(cand_weekly) | set(inc_weekly):
        delta = (cand_weekly.get(cat) or 0) - (inc_weekly.get(cat) or 0)
        vec[cat] = round(delta, 3 if cat in RATIO else 1)
    return vec


def format_swap_line_sp(drop_name, add_name, vec) -> str:
    parts = [f"{cat} {vec[cat]:+g}" for cat in _ORDER if cat in vec]
    parts += [f"{cat} {vec[cat]:+g}" for cat in vec if cat not in _ORDER]
    return f"swap {drop_name}→{add_name}/week: " + ", ".join(parts)
