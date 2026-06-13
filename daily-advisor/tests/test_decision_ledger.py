"""Unit tests for issue 038 — decision_ledger deep core.

Covers:
    DecisionLedger.record / get_history — JSON persistence, same-day
        same-verdict dedup-merge, distinct-verdict same-day appends,
        cross-day time ordering, injected clock + path (fs isolation).
    derive_ledger_records — pure mapping from a ```waiver-log``` block to
        (player, verdict) records, sharing the 028 line grammar +
        ACTION-annotation precedence used by apply_waiver_log_block (single
        source of truth — no second parse path).
    Coexistence — applying a real block via apply_waiver_log_block leaves
        compute_history_counters (032) working on the markdown while the
        ledger derives independently from the same block (no double count,
        no interference).

Fixture iron rule: the real waiver-log.md snapshot for the coexistence test;
generated history goes through apply_waiver_log_block (the production writer).
"""

from pathlib import Path

import pytest

from decision_ledger import (
    DecisionLedger,
    LedgerEntry,
    derive_ledger_records,
)
from fa_scan import apply_waiver_log_block, compute_history_counters

FIXTURES = Path(__file__).parent / "fixtures"


# ── DecisionLedger: record / get_history / persistence ──

@pytest.fixture()
def ledger_path(tmp_path):
    return tmp_path / "ledger.json"


def test_record_then_get_history(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Jordan Walker", "watch", ts="2026-04-01")
    hist = led.get_history("Jordan Walker")
    assert len(hist) == 1
    assert hist[0].player == "Jordan Walker"
    assert hist[0].verdict == "watch"
    assert hist[0].ts == "2026-04-01"


def test_get_history_unknown_player_empty(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("A", "watch", ts="2026-04-01")
    assert led.get_history("Nobody") == []


def test_same_day_same_verdict_dedup(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Cam Smith", "watch", ts="2026-05-09")
    led.record("Cam Smith", "watch", ts="2026-05-09")
    hist = led.get_history("Cam Smith")
    assert len(hist) == 1  # deduped


def test_same_day_same_verdict_merges_non_none_fields(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Cam Smith", "watch", ts="2026-05-09")
    led.record("Cam Smith", "watch", ts="2026-05-09",
               channel="structure", stars=4)
    hist = led.get_history("Cam Smith")
    assert len(hist) == 1
    assert hist[0].channel == "structure"  # 039 can enrich same-day record
    assert hist[0].stars == 4


def test_merge_does_not_clobber_with_none(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Cam Smith", "watch", ts="2026-05-09", channel="structure")
    led.record("Cam Smith", "watch", ts="2026-05-09", channel=None)
    assert led.get_history("Cam Smith")[0].channel == "structure"


def test_same_day_distinct_verdict_appends(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Kody Clemens", "watch", ts="2026-05-19")
    led.record("Kody Clemens", "取代", ts="2026-05-19")
    hist = led.get_history("Kody Clemens")
    assert len(hist) == 2  # mid-day upgrade is a real transition
    assert [e.verdict for e in hist] == ["watch", "取代"]


def test_cross_day_time_ordered(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("X", "watch", ts="2026-05-10")
    led.record("X", "watch", ts="2026-05-09")
    led.record("X", "watch", ts="2026-05-11")
    assert [e.ts for e in led.get_history("X")] == [
        "2026-05-09", "2026-05-10", "2026-05-11"]


def test_persistence_survives_new_instance(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Walker", "watch", ts="2026-04-01",
               add_reason="post-hype top prospect", channel="news")
    led2 = DecisionLedger(ledger_path)
    hist = led2.get_history("Walker")
    assert len(hist) == 1
    assert hist[0].add_reason == "post-hype top prospect"
    assert hist[0].channel == "news"


def test_injected_clock_default_ts(ledger_path):
    led = DecisionLedger(ledger_path, clock=lambda: "2026-06-13")
    led.record("Y", "watch")
    assert led.get_history("Y")[0].ts == "2026-06-13"


def test_record_returns_entry(ledger_path):
    led = DecisionLedger(ledger_path)
    e = led.record("Z", "closed", ts="2026-06-12", stars=2)
    assert isinstance(e, LedgerEntry)
    assert e.verdict == "closed"
    assert e.stars == 2


def test_empty_file_load_is_safe(ledger_path):
    ledger_path.write_text("", encoding="utf-8")
    led = DecisionLedger(ledger_path)
    assert led.get_history("anyone") == []


def test_distinct_players_isolated(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("A", "watch", ts="2026-05-01")
    led.record("B", "取代", ts="2026-05-01")
    assert len(led.get_history("A")) == 1
    assert led.get_history("A")[0].verdict == "watch"
    assert led.get_history("B")[0].verdict == "取代"


# ── derive_ledger_records: block → [(player, verdict)] ──

def test_derive_empty_block():
    assert derive_ledger_records("", "2026-06-13") == []


def test_derive_single_new_is_watch():
    block = "NEW|Heriberto Hernández|MIA||PA-TG ≥2.5 連 5 天|隊上UTIL|14d OPS 1.0"
    assert derive_ledger_records(block, "2026-06-13") == [
        ("Heriberto Hernández", "watch")]


def test_derive_new_with_action_is_replace():
    block = (
        "NEW|Joc Pederson|TEX||立即行動|Arraez|14d 5HR 碾壓\n"
        "ACTION|Joc Pederson|立即取代|Arraez"
    )
    assert derive_ledger_records(block, "2026-06-13") == [
        ("Joc Pederson", "立即取代")]


def test_derive_update_with_action_is_replace():
    block = (
        "UPDATE|Kody Clemens|14d 5HR/OPS .971\n"
        "ACTION|Kody Clemens|取代|Albies"
    )
    assert derive_ledger_records(block, "2026-06-13") == [
        ("Kody Clemens", "取代")]


def test_derive_update_only_is_watch():
    assert derive_ledger_records("UPDATE|Cam Smith|14d K% 25.9", "2026-06-13") == [
        ("Cam Smith", "watch")]


def test_derive_close_is_closed():
    assert derive_ledger_records("CLOSE|Gavin Sheets|品質崩盤", "2026-06-13") == [
        ("Gavin Sheets", "closed")]


def test_derive_close_precedence_over_update():
    block = (
        "UPDATE|Gavin Sheets|14d OPS .499\n"
        "CLOSE|Gavin Sheets|B-plan 已無升級可能"
    )
    assert derive_ledger_records(block, "2026-06-13") == [
        ("Gavin Sheets", "closed")]


def test_derive_standalone_action():
    assert derive_ledger_records("ACTION|Isaac Paredes|取代|Albies", "2026-06-13") == [
        ("Isaac Paredes", "取代")]


def test_derive_pre028_six_field_new_is_watch():
    block = "NEW|Old Guy|TEX||14d OPS ≥.800|summary no vs col"
    assert derive_ledger_records(block, "2026-06-13") == [("Old Guy", "watch")]


def test_derive_summary_with_pipe_parses_player():
    block = "UPDATE|Cam Smith|14d K% 25.9 + OPS .812 | Duran .826 計數重置"
    assert derive_ledger_records(block, "2026-06-13") == [("Cam Smith", "watch")]


def test_derive_malformed_lines_skipped():
    block = (
        "garbage line\n"
        "ACTION|BadAction|不是動作詞|x\n"
        "CLOSE|\n"
        "NEW|Good Player|TEX||trig|vs|sum"
    )
    assert derive_ledger_records(block, "2026-06-13") == [("Good Player", "watch")]


def test_derive_multiple_players_mixed():
    block = (
        "NEW|A|TEX||trig|vs|sum\n"
        "UPDATE|B|note\n"
        "ACTION|B|取代|C\n"
        "CLOSE|D|done"
    )
    got = dict(derive_ledger_records(block, "2026-06-13"))
    assert got == {"A": "watch", "B": "取代", "D": "closed"}


# ── Coexistence with 032 compute_history_counters (real fixture) ──

def test_coexistence_with_032_counters():
    """Applying a block updates markdown for 032; the ledger derives from the
    same block. Neither double-counts the other."""
    fixture = FIXTURES / "waiver_log_2026-06-10.md"
    if not fixture.exists():
        pytest.skip("waiver-log fixture absent")
    content = fixture.read_text(encoding="utf-8")
    block = (
        "UPDATE|Cam Smith|14d K% 25.9 觸發持續達成\n"
        "ACTION|Cam Smith|取代|Duran"
    )
    new_content, modified, _ = apply_waiver_log_block(
        content, block, "06-13")
    assert modified
    # 032 still derives counters from the markdown (independent read path).
    entry = new_content.split("### Cam Smith")[1].split("###")[0]
    counters = compute_history_counters(entry)
    assert isinstance(counters, list)  # no crash, independent of ledger
    # Ledger derives the same-day verdict from the same block, once.
    recs = derive_ledger_records(block, "2026-06-13")
    assert recs == [("Cam Smith", "取代")]
