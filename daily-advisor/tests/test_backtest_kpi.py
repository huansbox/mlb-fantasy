"""Unit tests for issue 051 / #330 — backtest_kpi pure functions.

Covers:
    attach_ledger_stars / _stars_at — star at episode start (latest ≤ start),
        fallback, legacy None.
    aggregate_hit_rate_by_stars — bucket split, judged denominator, 5★ empty.
    aggregate_execution_delay — median (odd/even), negative skip, none.
    count_regret_events — add→re-recommend within window, dedup, out-of-window.
    format_kpi_lines — renders the three KPI lines.
"""

from decision_ledger import LedgerEntry
from backtest_kpi import (
    aggregate_execution_delay,
    aggregate_hit_rate_by_stars,
    attach_ledger_stars,
    count_regret_events,
    format_kpi_lines,
)


def _e(player, ts, verdict, stars=None):
    return LedgerEntry(player, verdict, ts, stars=stars)


# ── attach_ledger_stars / _stars_at ──

def test_attach_stars_latest_on_or_before_start():
    hist = {"A": [_e("A", "2026-05-10", "watch", stars=3),
                  _e("A", "2026-05-12", "watch", stars=4),
                  _e("A", "2026-05-20", "watch", stars=5)]}
    rows = [{"player": "A", "start_date": "2026-05-12"}]
    attach_ledger_stars(rows, hist)
    assert rows[0]["stars"] == 4  # latest ≤ start, not the later 5★


def test_attach_stars_fallback_when_all_after_start():
    hist = {"A": [_e("A", "2026-05-20", "watch", stars=5)]}
    rows = [{"player": "A", "start_date": "2026-05-12"}]
    attach_ledger_stars(rows, hist)
    assert rows[0]["stars"] == 5  # nearest available


def test_attach_stars_none_when_no_stars():
    rows = [{"player": "A", "start_date": "2026-05-12"}]
    attach_ledger_stars(rows, {"A": [_e("A", "2026-05-10", "watch")]})
    assert rows[0]["stars"] is None


# ── aggregate_hit_rate_by_stars ──

def test_hit_rate_by_stars_buckets_and_denominator():
    rows = [
        {"stars": 4, "outcome": "hit"},
        {"stars": 4, "outcome": "miss"},
        {"stars": 4, "outcome": "pending-judge"},   # not judged
        {"stars": 3, "outcome": "hit"},
        {"stars": 5, "outcome": "hit"},
    ]
    agg = aggregate_hit_rate_by_stars(rows)
    assert agg["4★"]["n"] == 3 and agg["4★"]["n_judged"] == 2
    assert agg["4★"]["hit_rate"] == 0.5
    assert agg["≤3★"]["n_judged"] == 1 and agg["≤3★"]["hit_rate"] == 1.0
    assert agg["5★"]["n"] == 1


def test_hit_rate_by_stars_empty_bucket_none_rate():
    agg = aggregate_hit_rate_by_stars([{"stars": 4, "outcome": "pending-judge"}])
    assert agg["5★"]["n"] == 0 and agg["5★"]["hit_rate"] is None
    assert agg["4★"]["n"] == 1 and agg["4★"]["hit_rate"] is None  # unjudged


# ── aggregate_execution_delay ──

def _row(start, matched):
    return {"start_date": start,
            "execution": {"matched_date": matched}}


def test_execution_delay_median_odd():
    rows = [_row("2026-05-10", "2026-05-11"),   # 1
            _row("2026-05-10", "2026-05-13"),   # 3
            _row("2026-05-10", "2026-05-12")]   # 2
    out = aggregate_execution_delay(rows)
    assert out["n_executed"] == 3 and out["median_days"] == 2


def test_execution_delay_median_even():
    rows = [_row("2026-05-10", "2026-05-11"),   # 1
            _row("2026-05-10", "2026-05-15")]   # 5
    assert aggregate_execution_delay(rows)["median_days"] == 3.0


def test_execution_delay_skips_unexecuted_and_negative():
    rows = [_row("2026-05-10", None),
            {"start_date": "2026-05-10"},                     # no execution
            _row("2026-05-10", "2026-05-08")]                 # negative → skip
    out = aggregate_execution_delay(rows)
    assert out["n_executed"] == 0 and out["median_days"] is None


# ── count_regret_events ──

def test_regret_add_then_re_recommend_in_window():
    rows = [{"player": "Hicks", "execution": {"matched_date": "2026-05-01"}}]
    hist = {"Hicks": [_e("Hicks", "2026-05-01", "取代"),
                      _e("Hicks", "2026-05-12", "取代")]}  # re-rec 11d later
    events = count_regret_events(rows, hist, window_days=30)
    assert len(events) == 1 and events[0]["player"] == "Hicks"


def test_regret_out_of_window_excluded():
    rows = [{"player": "X", "execution": {"matched_date": "2026-05-01"}}]
    hist = {"X": [_e("X", "2026-06-15", "取代")]}  # 45d later
    assert count_regret_events(rows, hist, window_days=30) == []


def test_regret_dedup_by_player():
    rows = [{"player": "X", "execution": {"matched_date": "2026-05-01"}},
            {"player": "X", "execution": {"matched_date": "2026-05-01"}}]
    hist = {"X": [_e("X", "2026-05-10", "立即取代")]}
    assert len(count_regret_events(rows, hist)) == 1


def test_regret_needs_execution():
    rows = [{"player": "X", "execution": {"matched_date": None}}]
    hist = {"X": [_e("X", "2026-05-10", "取代")]}
    assert count_regret_events(rows, hist) == []


# ── format_kpi_lines ──

def test_format_kpi_lines():
    stats = {
        "hit_rate_by_stars": {
            "5★": {"n": 0, "n_judged": 0, "n_hits": 0, "hit_rate": None},
            "4★": {"n": 3, "n_judged": 2, "n_hits": 1, "hit_rate": 0.5},
            "≤3★": {"n": 1, "n_judged": 1, "n_hits": 0, "hit_rate": 0.0},
        },
        "execution_delay": {"n_executed": 2, "median_days": 3.0, "delays": [1, 5]},
        "regret_events": [{"player": "Hicks", "added": "2026-05-01",
                           "re_recommended": "2026-05-12"}],
    }
    text = "\n".join(format_kpi_lines(stats))
    assert "star-bucket" in text and "50%" in text
    assert "3 天" in text
    assert "regret" in text and "Hicks" in text


def test_format_kpi_lines_zero_regret():
    stats = {"hit_rate_by_stars": {}, "execution_delay": {}, "regret_events": []}
    text = "\n".join(format_kpi_lines(stats))
    assert "regret" in text and ": 0" in text
