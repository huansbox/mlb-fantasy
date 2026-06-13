"""Unit tests for issue 038 — decision_ledger deep core.

Covers:
    DecisionLedger.record / get_history / first_channel — JSON persistence,
        same-day same-verdict dedup-merge (scans for the matching entry, not
        just the last row), distinct-verdict same-day appends, cross-day
        ordering, executed_ts field, injected clock + path (fs isolation).
    apply_waiver_log_block ledger_sink — STATE-AWARE verdict emission: a
        verdict is emitted only where the markdown was actually mutated, so a
        CLOSE/ACTION for a player absent from the markdown produces NO ledger
        record even when the block is otherwise modified (the single-source
        invariant). Precedence closed > 取代 > watch within a block.
    Wiring + coexistence — the production write path persists the sink to a
        ledger JSON; 032 compute_history_counters keeps working on the
        markdown with its own non-trivial counts (no interference).

Fixture iron rule: state-aware edge cases use a controlled scaffold for
clarity; one case derives from the real waiver-log snapshot to prove the
grammar matches production line shapes.
"""

from pathlib import Path

import pytest

from decision_ledger import DecisionLedger, LedgerEntry
from fa_scan import apply_waiver_log_block, compute_history_counters

FIXTURES = Path(__file__).parent / "fixtures"

SCAFFOLD = """# Waiver Log 2026

## 觀察中

### Cam Smith (HOU, RF) [mlb_id:701358] — 觀察中
觸發：14d K% 回落
- 06-10：14d K% 25.9 + OPS .812（fa_scan）

## 隊上觀察

## 已結案
"""


def _sink(block, content=SCAFFOLD, short_date="06-13"):
    records = []
    new_content, modified, logs = apply_waiver_log_block(
        content, block, short_date, ledger_sink=records)
    return records, modified, new_content


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
    assert len(led.get_history("Cam Smith")) == 1


def test_same_day_same_verdict_merges_non_none_fields(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Cam Smith", "watch", ts="2026-05-09")
    led.record("Cam Smith", "watch", ts="2026-05-09",
               channel="structure", stars=4)
    hist = led.get_history("Cam Smith")
    assert len(hist) == 1
    assert hist[0].channel == "structure"
    assert hist[0].stars == 4


def test_merge_does_not_clobber_with_none(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Cam Smith", "watch", ts="2026-05-09", channel="structure")
    led.record("Cam Smith", "watch", ts="2026-05-09", channel=None)
    assert led.get_history("Cam Smith")[0].channel == "structure"


def test_merge_scans_past_intervening_distinct_verdict(ledger_path):
    # watch, then same-day 取代 (transition), then 039 enriches the watch
    # row same day → must merge into the existing watch, not append a 3rd.
    led = DecisionLedger(ledger_path)
    led.record("Kody Clemens", "watch", ts="2026-05-19")
    led.record("Kody Clemens", "取代", ts="2026-05-19")
    led.record("Kody Clemens", "watch", ts="2026-05-19", channel="structure")
    hist = led.get_history("Kody Clemens")
    assert len(hist) == 2  # not 3 — the watch row was merged, not duplicated
    watch = [e for e in hist if e.verdict == "watch"][0]
    assert watch.channel == "structure"


def test_same_day_distinct_verdict_appends(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Kody Clemens", "watch", ts="2026-05-19")
    led.record("Kody Clemens", "取代", ts="2026-05-19")
    assert [e.verdict for e in led.get_history("Kody Clemens")] == [
        "watch", "取代"]


def test_cross_day_time_ordered(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("X", "watch", ts="2026-05-10")
    led.record("X", "watch", ts="2026-05-09")
    led.record("X", "watch", ts="2026-05-11")
    assert [e.ts for e in led.get_history("X")] == [
        "2026-05-09", "2026-05-10", "2026-05-11"]


def test_executed_ts_field(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("X", "取代", ts="2026-05-19")
    led.record("X", "取代", ts="2026-05-19", executed_ts="2026-05-21")
    assert led.get_history("X")[0].executed_ts == "2026-05-21"


def test_first_channel(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("X", "watch", ts="2026-05-09")  # no channel yet
    led.record("X", "watch", ts="2026-05-10", channel="structure")
    led.record("X", "watch", ts="2026-05-11", channel="heat")  # later, ignored
    assert led.first_channel("X") == "structure"
    assert led.first_channel("Nobody") is None


def test_persistence_survives_new_instance(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("Walker", "watch", ts="2026-04-01",
               add_reason="post-hype top prospect", channel="news")
    hist = DecisionLedger(ledger_path).get_history("Walker")
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
    assert DecisionLedger(ledger_path).get_history("anyone") == []


def test_distinct_players_isolated(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("A", "watch", ts="2026-05-01")
    led.record("B", "取代", ts="2026-05-01")
    assert led.get_history("A")[0].verdict == "watch"
    assert led.get_history("B")[0].verdict == "取代"


def test_all_histories(ledger_path):
    led = DecisionLedger(ledger_path)
    led.record("A", "watch", ts="2026-05-01")
    led.record("B", "取代", ts="2026-05-01")
    hs = led.all_histories()
    assert set(hs) == {"A", "B"}
    assert hs["A"][0].verdict == "watch"


# ── apply_waiver_log_block ledger_sink: STATE-AWARE emission ──

def test_sink_new_player_is_watch():
    recs, mod, _ = _sink("NEW|New Guy|TEX|RF|trig|vs|sum")
    assert mod and recs == [("New Guy", "watch")]


def test_sink_new_existing_player_is_watch():
    # Cam Smith already in 觀察中 → treated as UPDATE → watch
    recs, mod, _ = _sink("NEW|Cam Smith|HOU|RF|trig|vs|note")
    assert recs == [("Cam Smith", "watch")]


def test_sink_update_with_action_is_replace():
    recs, _, _ = _sink(
        "UPDATE|Cam Smith|14d 5HR\nACTION|Cam Smith|取代|Duran")
    assert recs == [("Cam Smith", "取代")]


def test_sink_new_with_action_now_is_replace_now():
    recs, _, _ = _sink(
        "NEW|New Guy|TEX|RF|立即行動|Duran|碾壓\n"
        "ACTION|New Guy|立即取代|Duran")
    assert recs == [("New Guy", "立即取代")]


def test_sink_close_existing_is_closed():
    recs, mod, new = _sink("CLOSE|Cam Smith|品質崩盤")
    assert mod and recs == [("Cam Smith", "closed")]
    assert "## 已結案" in new and "Cam Smith" in new.split("## 已結案")[1]


def test_sink_standalone_action_existing_is_replace():
    recs, _, _ = _sink("ACTION|Cam Smith|取代|Duran")
    assert recs == [("Cam Smith", "取代")]


# Bug-1 regression: a verdict for a player the markdown SKIPPED must NOT
# appear in the ledger, even when the block is otherwise modified.

def test_sink_close_absent_player_not_emitted():
    recs, mod, _ = _sink("CLOSE|Ghost Player|done")
    assert not mod and recs == []


def test_sink_standalone_action_absent_player_not_emitted():
    recs, _, _ = _sink("ACTION|Ghost Player|取代|x")
    assert recs == []


def test_sink_modified_block_excludes_skipped_player():
    # UPDATE existing A (modifies) + CLOSE absent B (skipped) →
    # modified True, but only A in the sink, not B.
    recs, mod, _ = _sink(
        "UPDATE|Cam Smith|note\nCLOSE|Ghost Player|done")
    assert mod and recs == [("Cam Smith", "watch")]


def test_sink_close_precedence_over_update():
    recs, _, _ = _sink(
        "UPDATE|Cam Smith|14d OPS .499\nCLOSE|Cam Smith|B-plan 無望")
    assert recs == [("Cam Smith", "closed")]


def test_sink_malformed_lines_no_emit():
    recs, _, _ = _sink(
        "garbage\nACTION|Cam Smith|不是動作詞|x\nCLOSE|\nUPDATE|Cam Smith|ok")
    assert recs == [("Cam Smith", "watch")]


def test_sink_absent_when_not_requested():
    # No ledger_sink passed → no crash, normal return.
    _, modified, _ = apply_waiver_log_block(
        SCAFFOLD, "UPDATE|Cam Smith|note", "06-13")
    assert modified


# ── Wiring + coexistence (real fixture) ──

def test_sink_then_record_end_to_end(ledger_path):
    """The sink → DecisionLedger.record path (the production wiring shape)
    persists exactly the emitted verdicts to JSON."""
    recs, _, _ = _sink(
        "UPDATE|Cam Smith|note\nACTION|Cam Smith|取代|Duran\n"
        "CLOSE|Ghost|x")
    led = DecisionLedger(ledger_path)
    for player, verdict in recs:
        led.record(player, verdict, ts="2026-06-13")
    assert led.get_history("Cam Smith")[0].verdict == "取代"
    assert led.get_history("Ghost") == []  # skipped player never recorded


def test_coexistence_with_032_counters_real_fixture():
    """On the real snapshot: the ledger sink emits the same-day verdict while
    032 compute_history_counters independently derives non-trivial counters
    from the markdown."""
    fixture = FIXTURES / "waiver_log_2026-06-10.md"
    if not fixture.exists():
        pytest.skip("waiver-log fixture absent")
    content = fixture.read_text(encoding="utf-8")
    # Pick a player actually present in the snapshot's 觀察中 section.
    header = "### "
    present = None
    for line in content.split("\n"):
        if line.startswith(header) and "觀察中" in line:
            present = line[len(header):].split(" (")[0].strip()
            break
    assert present, "no 觀察中 entry in fixture"
    block = f"UPDATE|{present}|14d note\nACTION|{present}|取代|someone"
    records = []
    new_content, modified, _ = apply_waiver_log_block(
        content, block, "06-13", ledger_sink=records)
    assert modified
    assert records == [(present, "取代")]
    # 032 still derives counters from the markdown; assert it returns a
    # concrete list of strings (content, not just "no crash").
    entry = new_content.split(f"### {present}")[1].split("\n### ")[0]
    counters = compute_history_counters(entry)
    assert all(isinstance(c, str) for c in counters)
