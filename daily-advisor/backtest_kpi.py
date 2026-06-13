"""KPI instrumentation for the weekly batter backtest (issue 051 / #330).

Closes the measurement loop the PRD demands ("先建尺再調刀") by joining the
decision ledger (stars from 318a) onto the existing episode rows and deriving
the four acceptance KPIs:

  - star-bucket hit-rate — do 4★/5★ recommendations hit more than ≤3★? (the
    direct test of whether star_rating's formula is calibrated). 5★ stays an
    empty bucket until 318b makes 5★ reachable; ≤3★ / 4★ populate now.
  - trigger→execution median — days from an episode's first-trigger date to
    the roster execution date (git-timeline `matched_date`, the source 051
    adopts since executed_ts has no production writer). Target ≤2 days.
  - regret rate — a player who was added (matched_date) and then re-recommended
    as a replace within the window = the Hicks/Clemens/Steer churn signal.

All functions are pure over (rows, ledger_histories); the weekly pipeline
injects the ledger so this stays unit-testable without disk.
"""

from __future__ import annotations

from datetime import date, timedelta

_ACTIONABLE = ("取代", "立即取代")

# Star buckets, evaluated in order; a row falls in the first matching bucket.
STAR_BUCKETS = (
    ("5★", lambda s: s == 5),
    ("4★", lambda s: s == 4),
    ("≤3★", lambda s: s is not None and s <= 3),
)


def _stars_at(history, start_date_iso):
    """The star rating in effect at an episode's start: the latest stars-bearing
    entry on/before start_date; fall back to the earliest available stars."""
    best = None
    for e in history:
        if e.stars is None:
            continue
        if e.ts <= start_date_iso:
            best = e.stars        # history chronological → last ≤ start wins
    if best is not None:
        return best
    for e in history:             # fallback: nearest available stars
        if e.stars is not None:
            return e.stars
    return None


def attach_ledger_stars(rows, ledger_histories):
    """Attach `stars` to each episode row from the ledger. Mutates + returns
    rows. Legacy rows whose player has no stars stay `stars=None`."""
    for row in rows:
        hist = ledger_histories.get(row.get("player"), [])
        row["stars"] = _stars_at(hist, row.get("start_date", ""))
    return rows


def aggregate_hit_rate_by_stars(rows):
    """Hit-rate split by star bucket (judged denominator = hit/miss only, so
    rates appear once the judge panel upgrades outcomes — mirrors
    aggregate_executed_split)."""
    out = {}
    for label, pred in STAR_BUCKETS:
        bucket = [r for r in rows if pred(r.get("stars"))]
        judged = [r for r in bucket if r.get("outcome") in ("hit", "miss")]
        hits = [r for r in judged if r["outcome"] == "hit"]
        out[label] = {
            "n": len(bucket),
            "n_judged": len(judged),
            "n_hits": len(hits),
            "hit_rate": (len(hits) / len(judged)) if judged else None,
        }
    return out


def aggregate_execution_delay(rows):
    """trigger→execution delay in days (start_date → git-timeline matched_date)
    for executed episodes; returns count + median + the raw delays."""
    delays = []
    for r in rows:
        md = (r.get("execution") or {}).get("matched_date")
        start = r.get("start_date")
        if not md or not start:
            continue
        d = (date.fromisoformat(md) - date.fromisoformat(start)).days
        if d >= 0:
            delays.append(d)
    delays.sort()
    median = None
    if delays:
        n = len(delays)
        mid = n // 2
        median = delays[mid] if n % 2 else (delays[mid - 1] + delays[mid]) / 2
    return {"n_executed": len(delays), "median_days": median, "delays": delays}


def count_regret_events(rows, ledger_histories, window_days=30):
    """Players added (execution.matched_date) then re-recommended as a replace
    within `window_days` — the churn-regret signal. One event per player."""
    events = []
    seen = set()
    for r in rows:
        player = r.get("player")
        md = (r.get("execution") or {}).get("matched_date")
        if not md or player in seen:
            continue
        added = date.fromisoformat(md)
        for e in ledger_histories.get(player, []):
            if e.verdict in _ACTIONABLE and e.ts > md:
                if added < date.fromisoformat(e.ts) <= added + timedelta(days=window_days):
                    events.append({"player": player, "added": md,
                                   "re_recommended": e.ts})
                    seen.add(player)
                    break
    return events


def format_kpi_lines(stats):
    """Render the 051 KPI block as markdown lines for the weekly doc."""
    lines = ["", "Decision KPIs (issue 051):"]
    sb = stats.get("hit_rate_by_stars") or {}
    parts = []
    for label in ("5★", "4★", "≤3★"):
        b = sb.get(label) or {}
        rate = b.get("hit_rate")
        rate_s = f"{rate:.0%}" if rate is not None else "—"
        parts.append(f"{label} {b.get('n_hits', 0)}/{b.get('n_judged', 0)} ({rate_s})")
    lines.append(f"- ⭐ star-bucket 命中率: {' / '.join(parts)}")
    delay = stats.get("execution_delay") or {}
    med = delay.get("median_days")
    med_s = f"{med:g} 天" if med is not None else "—"
    lines.append(
        f"- ⏱ 觸發→執行延遲中位: {med_s}（n={delay.get('n_executed', 0)}；目標 ≤2 天）")
    regret = stats.get("regret_events") or []
    if regret:
        names = ", ".join(e["player"] for e in regret)
        lines.append(f"- 🔁 regret（撿入後 30 天內再推薦）: {len(regret)} — {names}")
    else:
        lines.append("- 🔁 regret（撿入後 30 天內再推薦）: 0")
    return lines
