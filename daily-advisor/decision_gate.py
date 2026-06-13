"""Decision gate — slow/fast lane + notify policy (issue 041 / #320).

A post-LLM pure function (zero prompt change) that decides whether an
actionable verdict is escalated to ACT-NOW and pushed to Telegram. It encodes
the retrospective's two opposite lessons:

  - Drops/replaces cost when too fast (Hicks/Clemens/Steer churned a
    correctly-picked player on a single-day signal) → SLOW lane: a replace
    needs 2 consecutive recommend-days before it escalates. Since a drop here
    only happens as part of a replace (drop X to add Y), slowing the replace
    cadence dampens the churn. NOTE: the other half of the churn fix — "a drop
    must confront the original add reason" — is the prompt contract in issue
    042, not this gate; the gate does not read add_reason.
  - Adds cost when too slow (Vargas, a 5★ miss) → FAST lane exceptions: a 5★
    rating or a fast-rising %owned shape skips the wait.

Notify policy (anti-cry-wolf): only 4★+ pushes Telegram. An URGENT
recommendation (5★, or a fast-rising %owned shape) re-escalates DAILY while
unexecuted ("第 N 天未執行"); a slow-lane 4★ (2-day-confirmed, not urgent)
notifies ONCE on the escalation day and then stays silent. "Executed" (the
candidate is now on the roster, or the ledger carries an execution timestamp)
short-circuits to DONE.

Caveat (318a): with trigger-completeness deferred, 5★ is currently unreachable
(established players cap at 4★, day-0 caps at 4★), so the daily-escalation path
is built but INERT until 318b builds trigger evaluation. Today the live path is
the 4★ slow-lane notify-once and the 4★ %owned-rising daily (once shape is
plumbed in 318b). A Vargas-type gets the 4★ notify-once today, not a 5★ daily
ping — the full execution-hole remedy lands with 318b.

The gate is fed `stars` (040, persisted by 318a) and the player's ledger
history (038). It does NOT read channel/playing_time directly: with 318a's
scoring an everyday structure-led bat already reaches 4★ (it never sits in the
3★ dead zone D2 feared — that residual is mid-PA / partial-credential cases,
a defensible silence). If a backtest later shows real 3★ misses, lower
NOTIFY_MIN_STARS or add a channel carve-out here.
"""

from __future__ import annotations

from dataclasses import dataclass

from decision_ledger import VERDICT_REPLACE, VERDICT_REPLACE_NOW

# Action levels.
ACT_NOW = "act_now"   # escalated; eligible for notify
PENDING = "pending"   # recommended, awaiting slow-lane confirmation (day 1)
WATCH = "watch"       # observation only / non-actionable verdict
DONE = "done"         # already executed — stop

ACTIONABLE = (VERDICT_REPLACE, VERDICT_REPLACE_NOW)
NOTIFY_MIN_STARS = 4                      # only 4★+ pushes Telegram
FAST_STARS = 5                            # 5★ skips the slow lane + daily re-escalate
OWNED_FAST = ("explosive", "rising")      # %owned shapes that fast-lane an add
SLOW_LANE_DAYS = 2                        # consecutive recommend-days before escalating


@dataclass
class GateResult:
    action: str
    notify: bool
    consecutive_days: int   # trailing consecutive recommend-days (incl today)
    unexecuted_days: int    # recommend-days still unexecuted (0 if not act_now)
    reason: str


def _trailing_actionable_days(history) -> int:
    """Trailing consecutive dates whose verdict set includes a replace."""
    by_date: dict[str, bool] = {}
    for e in history:
        by_date.setdefault(e.ts, False)
        if e.verdict in ACTIONABLE:
            by_date[e.ts] = True
    count = 0
    for date in sorted(by_date, reverse=True):
        if by_date[date]:
            count += 1
        else:
            break
    return count


def _is_executed(history) -> bool:
    return any(getattr(e, "executed_ts", None) for e in history
               if e.verdict in ACTIONABLE)


def gate(history, verdict, stars, owned_trend=None, executed=False) -> GateResult:
    """Decide action level + whether to notify for today's verdict.

    history: the player's ledger entries (chronological, INCLUDING today's).
    verdict/stars: today's verdict + mechanical star rating.
    owned_trend: today's %owned shape string (explosive/rising/...), or None.
    executed: candidate already on the roster (caller checks roster_config);
        the ledger's executed_ts is also honoured.
    """
    if executed or _is_executed(history):
        return GateResult(DONE, False, 0, 0, "已執行")

    if verdict not in ACTIONABLE:
        return GateResult(WATCH, False, 0, 0, "觀察")

    consecutive = _trailing_actionable_days(history)
    fast = stars >= FAST_STARS or (owned_trend in OWNED_FAST)
    act = fast or consecutive >= SLOW_LANE_DAYS

    if not act:
        return GateResult(
            PENDING, False, consecutive, 0,
            f"慢軌待確認（第 {consecutive}/{SLOW_LANE_DAYS} 天）")

    # Escalated. Notify policy:
    #   below 4★ → silent (anti-cry-wolf)
    #   5★      → re-notify daily while unexecuted
    #   4★      → notify once on the escalation day
    if stars < NOTIFY_MIN_STARS:
        notify = False           # below the notify floor (anti-cry-wolf)
    elif fast:
        notify = True            # urgent (5★ or %owned rising) → re-notify daily
    else:
        # Slow-lane 4★: notify ONCE, on the escalation day (day 2). Days 3+ stay
        # silent — a deliberately 2-day-confirmed add isn't worth daily nagging.
        notify = (consecutive == SLOW_LANE_DAYS)

    lane = "快軌" if fast else "慢軌"
    reason = f"ACT NOW（{lane}，{stars}★，已推薦 {consecutive} 天未執行）"
    return GateResult(ACT_NOW, notify, consecutive, consecutive, reason)


def collect_unexecuted(histories, roster_names):
    """For weekly-review (issue 041): players whose latest verdict is an
    actionable replace and who are NOT yet executed (not on the roster, no
    execution timestamp). Returns [(player, GateResult)] sorted most-overdue
    first. ``histories``: {player: [LedgerEntry]} (chronological)."""
    roster = set(roster_names or ())
    out = []
    for player, hist in histories.items():
        if not hist:
            continue
        executed = player in roster or _is_executed(hist)
        if executed:
            continue
        latest = hist[-1]
        r = gate(hist, latest.verdict, latest.stars or 0, executed=False)
        if r.action in (ACT_NOW, PENDING):
            out.append((player, r))
    out.sort(key=lambda pr: pr[1].consecutive_days, reverse=True)
    return out
