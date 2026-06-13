"""SP next-week start-count projector (issue 046 / #325).

Projects how many times an SP starts in the coming Mon–Sun window ({0,1,2}) so
"volume" becomes the first-order sort key for SP add/drop — IP, QS, K, W all
scale linearly with starts, and the weekly 40-IP floor is start-count driven.

Pure core: `project_starts` walks the rotation cadence forward from the last
start, optionally snapping to real game days and overriding with published
probables. `infer_cadence` derives the median rest from a game log. Schedule /
probable data are injected, so the projector is fully offline-testable; the
per-start production vector (IP/K/QS/W) lives in 048 (swap-SP).

The ≥85% retro-accuracy gate (AC) is a historical-data validation run, not a
unit test — it reconciles past-Monday projections against actual game logs and
is run on the VPS where the data lives.
"""

from __future__ import annotations

from datetime import timedelta

MAX_STARTS_PER_WEEK = 2   # a 5/6-man rotation gives at most 2 starts in 7 days
_SNAP_SLACK_DAYS = 1      # a projected start may slide ±1 day to a real game day


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
                   *, probable_dates=(), schedule_dates=None) -> dict:
    """Project starts in [week_start, week_end].

    last_start: SP's most recent start date. cadence_days: rest between starts.
    probable_dates: confirmed starts (MLB probables, ~5 days out) — authoritative
    within their range. schedule_dates: team game days in the window — when
    given, cadence candidates must snap to a real game day. Returns
    {starts (0..2), projected_dates, source}.
    """
    dates = {d for d in probable_dates if week_start <= d <= week_end}

    if last_start and cadence_days and cadence_days > 0:
        nxt = last_start + timedelta(days=round(cadence_days))
        while nxt <= week_end:
            if nxt >= week_start:
                snapped = _snap(nxt, schedule_dates)
                if snapped is not None and week_start <= snapped <= week_end:
                    dates.add(snapped)
            nxt = nxt + timedelta(days=round(cadence_days))

    starts = min(MAX_STARTS_PER_WEEK, len(dates))
    if probable_dates and any(week_start <= d <= week_end for d in probable_dates):
        source = "probable"
    elif dates:
        source = "cadence"
    else:
        source = "none"
    return {"starts": starts, "projected_dates": sorted(dates), "source": source}
