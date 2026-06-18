"""Unit tests for issue 041 / #320 — decision_gate pure logic.

Covers:
    gate — slow lane for replace verdicts (needs 2 consecutive actionable
        days), fast-lane exceptions (5★ or %owned explosive/rising),
        4★+ notify threshold, 5★ daily re-escalation while unexecuted vs 4★
        notify-once, executed short-circuit, watch/closed = no action.
    _trailing_actionable_days — trailing consecutive recommend-days helper.
"""

from decision_gate import (
    ACT_NOW,
    DONE,
    GateResult,
    PENDING,
    WATCH,
    collect_unexecuted,
    gate,
)
from decision_ledger import (
    LedgerEntry,
    VERDICT_CLOSED,
    VERDICT_REPLACE,
    VERDICT_REPLACE_NOW,
    VERDICT_WATCH,
)
from ledger_enrich import CandidateEnrichment


def _hist(*rows):
    """rows: (ts, verdict[, executed_ts]) → [LedgerEntry]."""
    out = []
    for r in rows:
        ts, verdict = r[0], r[1]
        ex = r[2] if len(r) > 2 else None
        out.append(LedgerEntry("X", verdict, ts, executed_ts=ex))
    return out


# ── non-actionable verdicts ──

def test_watch_is_no_action():
    h = _hist(("2026-06-13", VERDICT_WATCH))
    r = gate(h, VERDICT_WATCH, stars=5, owned_trend=None)
    assert r.action == WATCH and r.notify is False


def test_closed_is_no_action():
    h = _hist(("2026-06-13", VERDICT_CLOSED))
    r = gate(h, VERDICT_CLOSED, stars=2, owned_trend=None)
    assert r.action == WATCH and r.notify is False


# ── slow lane: replace needs 2 consecutive days ──

def test_replace_day1_is_pending():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend=None)
    assert r.action == PENDING
    assert r.notify is False        # day 1 of slow lane, not yet escalated
    assert r.consecutive_days == 1


def test_replace_day2_is_act_now():
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend=None)
    assert r.action == ACT_NOW
    assert r.notify is True         # 4★ escalation day → notify once
    assert r.consecutive_days == 2


def test_4star_notifies_once_not_daily():
    h = _hist(("2026-06-11", VERDICT_REPLACE), ("2026-06-12", VERDICT_REPLACE),
              ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend=None)
    assert r.action == ACT_NOW
    assert r.notify is False        # day 3+ at 4★: already escalated, silent
    assert r.consecutive_days == 3


def test_4star_slow_lane_silent_days_4_and_5():
    days = ["2026-06-1" + d for d in "012345"]  # 06-10..06-15
    for n in (4, 5):
        h = _hist(*[(days[i], VERDICT_REPLACE) for i in range(n)])
        r = gate(h, VERDICT_REPLACE, stars=4, owned_trend=None)
        assert r.action == ACT_NOW and r.notify is False, f"day {n}"


def test_4star_owned_rising_re_notifies_daily():
    # fast-lane (owned rising) is urgent → notify every day, not once
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend="rising")
    assert r.action == ACT_NOW and r.notify is True   # day 2, still pinging


def test_4star_mid_streak_flip_to_fast_notifies():
    # regression: pending day 1 (no shape), %owned flips to rising day 2 →
    # fast-lane escalation on day 2 must NOT be silently swallowed
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    day1 = gate(_hist(("2026-06-12", VERDICT_REPLACE)),
                VERDICT_REPLACE, stars=4, owned_trend=None)
    assert day1.action == PENDING and day1.notify is False
    day2 = gate(h, VERDICT_REPLACE, stars=4, owned_trend="rising")
    assert day2.action == ACT_NOW and day2.notify is True


# ── fast lane: 5★ or %owned rising ──

def test_5star_fast_lane_day1():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=5, owned_trend=None)
    assert r.action == ACT_NOW and r.notify is True   # 5★ skips slow lane


def test_5star_re_escalates_daily():
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=5, owned_trend=None)
    assert r.action == ACT_NOW and r.notify is True   # 5★ notifies every day
    assert r.unexecuted_days == 2


def test_owned_rising_fast_lane_day1():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend="rising")
    assert r.action == ACT_NOW and r.notify is True


def test_owned_explosive_fast_lane():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend="explosive")
    assert r.action == ACT_NOW and r.notify is True


def test_owned_plateau_no_fast_lane():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend="plateau")
    assert r.action == PENDING       # plateau is not a fast shape


# ── notify threshold: only 4★+ ──

def test_3star_act_now_does_not_notify():
    # 2 consecutive days → act_now, but 3★ stays below the notify floor
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=3, owned_trend=None)
    assert r.action == ACT_NOW and r.notify is False  # silent: anti-cry-wolf


# ── executed short-circuit ──

def test_executed_is_done_no_notify():
    h = _hist(("2026-06-12", VERDICT_REPLACE), ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=5, owned_trend="rising", executed=True)
    assert r.action == DONE and r.notify is False


def test_executed_via_ledger_executed_ts():
    h = _hist(("2026-06-12", VERDICT_REPLACE),
              ("2026-06-13", VERDICT_REPLACE, "2026-06-13"))
    r = gate(h, VERDICT_REPLACE, stars=5, owned_trend=None)
    assert r.action == DONE and r.notify is False


# ── trailing-day counting with gaps / mixed verdicts ──

def test_trailing_run_breaks_on_gap_day():
    # an intervening watch day breaks the consecutive replace run
    h = _hist(("2026-06-11", VERDICT_REPLACE), ("2026-06-12", VERDICT_WATCH),
              ("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=4, owned_trend=None)
    assert r.consecutive_days == 1   # only today; 06-12 watch broke the run


def test_same_day_watch_and_replace_counts_actionable():
    # a day with both watch and an upgrade to replace counts as actionable
    h = _hist(("2026-06-12", VERDICT_REPLACE),
              ("2026-06-13", VERDICT_WATCH), ("2026-06-13", VERDICT_REPLACE_NOW))
    r = gate(h, VERDICT_REPLACE_NOW, stars=4, owned_trend=None)
    assert r.consecutive_days == 2


def test_gateresult_reason_present():
    h = _hist(("2026-06-13", VERDICT_REPLACE))
    r = gate(h, VERDICT_REPLACE, stars=5, owned_trend=None)
    assert isinstance(r, GateResult) and r.reason


# ── collect_unexecuted (weekly-review consumer) ──

def _ent(player, ts, verdict, stars=4, executed_ts=None):
    return LedgerEntry(player, verdict, ts, stars=stars, executed_ts=executed_ts)


def test_collect_unexecuted_lists_overdue_first():
    histories = {
        "A": [_ent("A", "2026-06-11", VERDICT_REPLACE),
              _ent("A", "2026-06-12", VERDICT_REPLACE),
              _ent("A", "2026-06-13", VERDICT_REPLACE)],   # 3 days overdue
        "B": [_ent("B", "2026-06-13", VERDICT_REPLACE)],   # day 1 pending
        "C": [_ent("C", "2026-06-13", VERDICT_WATCH)],     # not actionable
    }
    out = collect_unexecuted(histories, roster_names=set())
    names = [p for p, _ in out]
    assert names == ["A", "B"]           # C excluded; A before B (more overdue)
    assert out[0][1].consecutive_days == 3


def test_collect_unexecuted_excludes_rostered():
    histories = {"A": [_ent("A", "2026-06-13", VERDICT_REPLACE)]}
    assert collect_unexecuted(histories, roster_names={"A"}) == []


def test_collect_unexecuted_excludes_executed_ts():
    histories = {"A": [_ent("A", "2026-06-13", VERDICT_REPLACE,
                             executed_ts="2026-06-13")]}
    assert collect_unexecuted(histories, roster_names=set()) == []


# ── weekly-review consumer (reads ledger file + roster) ──

def test_collect_unexecuted_recommendations_from_file(tmp_path):
    from decision_ledger import DecisionLedger
    from weekly_review import collect_unexecuted_recommendations
    path = tmp_path / "ledger.json"
    led = DecisionLedger(path)
    led.record("A", VERDICT_REPLACE, ts="2026-06-12", stars=4)
    led.record("A", VERDICT_REPLACE, ts="2026-06-13", stars=4)
    led.record("B", VERDICT_REPLACE, ts="2026-06-13", stars=4)  # rostered
    config = {"batters": [{"name": "B"}], "pitchers": []}
    out = collect_unexecuted_recommendations(config, ledger_path=str(path))
    assert [r["player"] for r in out] == ["A"]   # B excluded (on roster)
    assert out[0]["recommend_days"] == 2


def test_collect_unexecuted_recommendations_missing_file():
    from weekly_review import collect_unexecuted_recommendations
    assert collect_unexecuted_recommendations(
        {"batters": []}, ledger_path="/no/such/ledger.json") == []


def test_collect_unexecuted_stars_none_still_listed():
    # legacy ledger rows (pre-318a) have stars=None → 0★; they never NOTIFY
    # but a 2-day actionable run still belongs in the unexecuted list
    histories = {"A": [_ent("A", "2026-06-12", VERDICT_REPLACE, stars=None),
                       _ent("A", "2026-06-13", VERDICT_REPLACE, stars=None)]}
    out = collect_unexecuted(histories, roster_names=set())
    assert [p for p, _ in out] == ["A"] and out[0][1].consecutive_days == 2


# ── _gate_notifications wiring (injection-based) ──

class _FakeLedger:
    def __init__(self, histories):
        self._h = histories

    def get_history(self, name):
        return self._h.get(name, [])


def test_gate_notifications_pushes_4star_actionable_today():
    from fa_scan import _gate_notifications
    histories = {
        "Hot": [_ent("Hot", "2026-06-12", VERDICT_REPLACE),
                _ent("Hot", "2026-06-13", VERDICT_REPLACE)],   # day2 4★ → notify
        "New": [_ent("New", "2026-06-13", VERDICT_REPLACE)],   # day1 pending → no
        "Watched": [_ent("Watched", "2026-06-13", VERDICT_WATCH)],  # not actionable
    }
    enrich_map = {n: CandidateEnrichment(channel="structure", stars=4)
                  for n in ("Hot", "New", "Watched")}
    msgs = _gate_notifications(enrich_map, set(), _FakeLedger(histories), "2026-06-13")
    assert len(msgs) == 1 and msgs[0].startswith("⚡ Hot")


def test_gate_notifications_skips_rostered_and_stale():
    from fa_scan import _gate_notifications
    histories = {
        "Rostered": [_ent("Rostered", "2026-06-12", VERDICT_REPLACE),
                     _ent("Rostered", "2026-06-13", VERDICT_REPLACE)],
        "Stale": [_ent("Stale", "2026-06-10", VERDICT_REPLACE)],  # not today
    }
    enrich_map = {n: CandidateEnrichment(channel="structure", stars=5)
                  for n in ("Rostered", "Stale")}
    msgs = _gate_notifications(
        enrich_map, {"Rostered"}, _FakeLedger(histories), "2026-06-13")
    assert msgs == []  # rostered=executed (DONE); stale=not today
