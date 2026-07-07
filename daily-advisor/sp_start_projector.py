"""SP next-week start-count projector (issue 046 / #325).

Projects how many times an SP starts in a Mon–Sun window ({0,1,2}) so
"volume" becomes the first-order sort key for SP add/drop — IP, QS, K, W all
scale linearly with starts, and the weekly 40-IP floor is start-count driven.

Pure core: `project_starts` walks the rotation cadence forward, snapping to
real game days and honoring published probables. `infer_cadence` derives the
median rest from a game log. Schedule / probable data are injected, so the
projector is fully offline-testable; the per-start production vector (IP/K/
QS/W) lives in 048 (swap-SP).

Three rules earned by the retro gate (2026-07-07, 192 SPs × 14 weeks = 2354
cells, Monday-knowable data only):
  1. probable-anchored walk — an in-window probable is the pitcher's known
     next turn; cadence continues FROM it. Unioning cadence candidates with
     probables double-counted the same turn when they differed by 1-2 days
     (retro: pred-2/actual-1 errors 4×'d without this).
  2. staleness guard — a last start already more than cadence+2 days before
     week_start means the pitcher visibly missed a turn by Monday (IL /
     demotion); the cadence walk is suppressed (probables still count).
     Retro: +9pp accuracy.
  3. horizon-absence suppression — when probables are published through
     `probable_horizon_end` and the pitcher has none in the window, a cadence
     candidate at least PUSH_SLACK days inside that horizon is a visibly
     skipped turn (a merely pushed-back start would still show up within the
     slack). Retro: +1.5pp.

Gate result: 85.0% exact-match with a 5-day Monday-morning probable horizon
(sensitivity: 4-day 83.7%, 6-day 86.7%; no probables at all: 75.1%). The
production scan at TW 12:30 Monday = ET Sunday night projects the ET week
starting the next day, where probables genuinely cover ~5 days.
"""

from __future__ import annotations

from datetime import timedelta

MAX_STARTS_PER_WEEK = 2   # a 5/6-man rotation gives at most 2 starts in 7 days
_SNAP_SLACK_DAYS = 1      # a projected start may slide ±1 day to a real game day
STALE_SLACK_DAYS = 2      # calendar-day staleness slack (retro fallback path)
# Game-day staleness needs NO slack: "team played more than round(cadence)
# games since his last start" already excludes off-days/breaks. Retro
# 2026-07-07 (2354 cells): game-day slack 0 → 85.3% vs calendar slack 2 →
# 85.0%, and only the game-day form survives the All-Star break week.
STALE_GAP_GAMES_SLACK = 0
PUSH_SLACK_DAYS = 2       # a pushed (not skipped) turn resurfaces within this


def infer_cadence(start_dates, default=5):
    """Median days between consecutive starts; `default` (5-man rotation) when
    there are fewer than two starts."""
    ds = sorted(d for d in start_dates if d is not None)
    if len(ds) < 2:
        return default
    gaps = sorted((ds[i + 1] - ds[i]).days for i in range(len(ds) - 1))
    mid = len(gaps) // 2
    if len(gaps) % 2:
        return gaps[mid]
    return (gaps[mid - 1] + gaps[mid]) / 2


def _snap(candidate, schedule_dates):
    """Snap a cadence candidate to a real game day within ±slack; None if the
    team has no game near it (off-day stretch). No schedule → trust the date."""
    if schedule_dates is None:
        return candidate
    sched = set(schedule_dates)
    if candidate in sched:
        return candidate
    for off in range(1, _SNAP_SLACK_DAYS + 1):
        for d in (candidate + timedelta(days=off), candidate - timedelta(days=off)):
            if d in sched:
                return d
    return None


def project_starts(last_start, cadence_days, week_start, week_end,
                   *, probable_dates=(), schedule_dates=None,
                   probable_horizon_end=None, gap_game_days=None) -> dict:
    """Project starts in [week_start, week_end].

    last_start: SP's most recent start date. cadence_days: rest between starts.
    probable_dates: confirmed starts (MLB probables) — authoritative; the
    cadence walk continues from the LAST in-window probable. schedule_dates:
    team game days in the window — when given, cadence candidates must snap to
    a real game day. probable_horizon_end: last date the pitcher's TEAM has
    probables published through (per-team, not league-wide — teams publish to
    different depths and an absence only means something once the team itself
    has announced that far). gap_game_days: the team's game dates in
    (last_start, week_start) — when given, staleness counts games the team
    played without him starting instead of calendar days, so a league-wide
    break (All-Star) doesn't mark every healthy SP stale.
    Returns {starts (0..2), projected_dates, source} where source is
    "probable" / "cadence" / "stale" (walk suppressed by staleness) / "none".
    """
    dates = {d for d in probable_dates if week_start <= d <= week_end}
    has_probables = bool(dates)

    if gap_game_days is not None and last_start:
        gap = sum(1 for d in gap_game_days if last_start < d < week_start)
        slack = STALE_GAP_GAMES_SLACK
    elif last_start:
        gap = (week_start - last_start).days
        slack = STALE_SLACK_DAYS
    else:
        gap = 0
        slack = STALE_SLACK_DAYS
    stale = bool(
        last_start and cadence_days and cadence_days > 0
        and gap > round(cadence_days) + slack
    )

    if has_probables:
        anchor = max(dates)          # known next turn; walk continues from it
    elif stale:
        anchor = None                # visibly off turn by Monday — no walk
    else:
        anchor = last_start

    if anchor and cadence_days and cadence_days > 0:
        step = round(cadence_days)
        nxt = anchor + timedelta(days=step)
        while nxt <= week_end:
            if nxt >= week_start:
                snapped = _snap(nxt, schedule_dates)
                if (snapped is not None and week_start <= snapped <= week_end
                        and snapped > anchor):
                    visibly_skipped = (
                        probable_horizon_end is not None and not has_probables
                        and snapped + timedelta(days=PUSH_SLACK_DAYS)
                        <= probable_horizon_end
                    )
                    if not visibly_skipped:
                        dates.add(snapped)
            nxt = nxt + timedelta(days=step)

    starts = min(MAX_STARTS_PER_WEEK, len(dates))
    if has_probables:
        source = "probable"
    elif dates:
        source = "cadence"
    elif stale:
        source = "stale"
    else:
        source = "none"
    return {"starts": starts, "projected_dates": sorted(dates), "source": source}
