"""Platoon-share classifier (issue 044 / #323).

Detects whether a batter is everyday / strong-side platoon / weak-side / bench
from per-game start records split by the opposing starter's handedness. Directly
mechanizes the Arraez→Pederson -28% weekly-PA blind spot (retrospective 失誤型
3): a strong-side platoon bat (plays vs RHP, sits vs LHP) loses ~28% of weekly
PA versus an everyday bat, which the quality-only framework never saw.

`classify_platoon` is pure (a list of {started, opp_hand} records → label + tag
+ per-hand start rates). `collect_platoon_games` builds that list from injected
boxscore + pitch-hand fetchers with a per-gamePk / per-pitcher cache so the same
team game is fetched once (the cache-hit count is a machine-checkable AC).
"""

from __future__ import annotations

EVERYDAY_MIN = 0.80     # start rate at/above this on a side = "plays that side"
PLATOON_OFF_MAX = 0.40  # start rate below this on a side = "sits that side"
BENCH_MAX = 0.40        # overall start rate below this = bench

LABEL_EVERYDAY = "everyday"
LABEL_STRONG = "strong_side"
LABEL_WEAK = "weak_side"
LABEL_BENCH = "bench"
LABEL_PART = "part_time"
LABEL_UNKNOWN = "unknown"

_TAGS = {
    LABEL_EVERYDAY: None,
    LABEL_STRONG: "⚠️ 強側平台 (vs RHP)",
    LABEL_WEAK: "⚠️ 弱側平台 (vs LHP only)",
    LABEL_BENCH: "⚠️ 替補 (少先發)",
    LABEL_PART: "⚠️ 部分先發",
    LABEL_UNKNOWN: None,
}


def _rate(games):
    if not games:
        return None
    return sum(1 for g in games if g.get("started")) / len(games)


def classify_platoon(games) -> dict:
    """games: [{"started": bool, "opp_hand": "R"|"L"}]. Returns a dict with
    label, tag, and per-hand + overall start rates."""
    overall = _rate(games)
    r_rate = _rate([g for g in games if g.get("opp_hand") == "R"])
    l_rate = _rate([g for g in games if g.get("opp_hand") == "L"])

    label = _label(overall, r_rate, l_rate)
    return {
        "label": label,
        "tag": _TAGS[label],
        "start_rate_vs_r": r_rate,
        "start_rate_vs_l": l_rate,
        "overall_start_rate": overall,
    }


def _label(overall, r_rate, l_rate) -> str:
    if overall is None:
        return LABEL_UNKNOWN
    if r_rate is not None and l_rate is not None:
        # Platoon patterns first: a weak-side bat has a low OVERALL rate (it
        # only plays ~30% of games vs LHP) but still starts its side reliably,
        # so it must be caught before the bench check.
        if r_rate >= EVERYDAY_MIN and l_rate >= EVERYDAY_MIN:
            return LABEL_EVERYDAY
        if r_rate >= EVERYDAY_MIN and l_rate < PLATOON_OFF_MAX:
            return LABEL_STRONG
        if l_rate >= EVERYDAY_MIN and r_rate < PLATOON_OFF_MAX:
            return LABEL_WEAK
        if r_rate < PLATOON_OFF_MAX and l_rate < PLATOON_OFF_MAX:
            return LABEL_BENCH  # sits regardless of hand
        return LABEL_PART
    # only one hand faced in the window — lean on overall
    if overall < BENCH_MAX:
        return LABEL_BENCH
    if overall >= EVERYDAY_MIN:
        return LABEL_EVERYDAY
    return LABEL_PART


def collect_platoon_games(team_games, *, get_started, get_pitch_hand):
    """Build the {started, opp_hand} record list for one player.

    team_games: [{"game_pk", "opp_starter_id"}] for the player's team in the
    window. get_started(game_pk) → bool (did the player start that game).
    get_pitch_hand(pitcher_id) → "R"|"L". Both are cached by key so each
    game/pitcher is fetched once; returns (games, fetch_counts) where
    fetch_counts = {"boxscore", "pitch_hand"} miss counts (machine-checkable
    cache AC)."""
    box_cache, hand_cache = {}, {}
    counts = {"boxscore": 0, "pitch_hand": 0}
    games = []
    for tg in team_games:
        gpk = tg.get("game_pk")
        pid = tg.get("opp_starter_id")
        if gpk not in box_cache:
            box_cache[gpk] = get_started(gpk)
            counts["boxscore"] += 1
        if pid not in hand_cache:
            hand_cache[pid] = get_pitch_hand(pid)
            counts["pitch_hand"] += 1
        games.append({"started": box_cache[gpk], "opp_hand": hand_cache[pid]})
    return games, counts
