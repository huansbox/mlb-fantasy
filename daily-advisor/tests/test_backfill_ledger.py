"""Unit tests for 318b B7 — backfill_ledger (issue 039 / #318).

Parse fixtures follow the real-fixture rule: waiver_log_2026-07-07.md is the
verbatim production waiver-log on the backfill design date, containing the
actual gap entries (Robert Gasser SP / Victor Bericoto) the script targets.
"""

from pathlib import Path

import pytest

from backfill_ledger import (
    BACKFILL_TAG,
    NO_DATA_SNAPSHOT,
    VERDICT_HOLD,
    acceptance_failures,
    classify_channel_from_text,
    format_batter_snapshot,
    format_pitcher_snapshot,
    parse_active_watchlist,
    plan_backfill,
)
from decision_ledger import DecisionLedger

FIXTURES = Path(__file__).parent / "fixtures"
REAL_LOG = (FIXTURES / "waiver_log_2026-07-07.md").read_text(encoding="utf-8")


# ── parse_active_watchlist (real fixture) ──

def test_parse_watchlist_real_fixture_names():
    entries = parse_active_watchlist(REAL_LOG)
    names = [e["name"] for e in entries]
    assert names == [
        "Cam Smith", "J.P. Crawford", "Kyle Karros", "Spencer Torkelson",
        "Royce Lewis", "Robert Gasser", "Kerry Carpenter", "Tommy Edman",
        "Josh Bell", "Victor Bericoto",
    ]


def test_parse_watchlist_excludes_other_sections():
    names = {e["name"] for e in parse_active_watchlist(REAL_LOG)}
    # 隊上觀察 (roster context) and 已結案 (closed) are not watchlist
    assert "Luis Arraez" not in names
    assert "Andrew Benintendi" not in names


def test_parse_watchlist_fields():
    entries = {e["name"]: e for e in parse_active_watchlist(REAL_LOG)}
    gasser = entries["Robert Gasser"]
    assert gasser["team"] == "MIL"
    assert gasser["position"] == "SP"
    assert gasser["mlb_id"] == 688107
    assert "B2 2-step watch" in gasser["body"]
    # body stops at the next entry
    assert "Kerry Carpenter" not in gasser["body"]


def test_parse_watchlist_no_section():
    assert parse_active_watchlist("# nothing here\n## 已結案\n") == []


# ── classify_channel_from_text ──

def test_classify_real_gasser_is_heat():
    """Season line ugly, surfaced on a 21d surge → heat."""
    body = {e["name"]: e for e in parse_active_watchlist(REAL_LOG)}["Robert Gasser"]["body"]
    assert classify_channel_from_text(body) == "heat"


def test_classify_real_bericoto_is_heat():
    """One >P90 mention (not two) + 14d luck-inflated hot stretch → heat."""
    body = {e["name"]: e for e in parse_active_watchlist(REAL_LOG)}["Victor Bericoto"]["body"]
    assert classify_channel_from_text(body) == "heat"


def test_classify_structure_dual_year():
    body = "### X (T, 1B)\n觸發：foo\n- 07-01：雙年 P80/P95 結構確認（fa_scan）\n"
    assert classify_channel_from_text(body) == "structure"


def test_classify_structure_two_strong_percentiles():
    body = "### X (T, 1B)\n- 07-01：xwOBA P70/Barrel% P80 季線強（fa_scan）\n"
    assert classify_channel_from_text(body) == "structure"


def test_classify_structure_beats_heat():
    body = "### X (T, 1B)\n- 07-01：xwOBA P70/Barrel% P90 + 14d OPS .900（fa_scan）\n"
    assert classify_channel_from_text(body) == "structure"


def test_classify_market():
    body = "### X (T, 1B)\n- 07-01：%owned 3d+12 持有壓力升（fa_scan）\n"
    assert classify_channel_from_text(body) == "market"


def test_classify_unknown_plain_text():
    body = "### X (T, 1B)\n觸發：先發量確認\n- 07-01：升上大聯盟後每日先發（fa_scan）\n"
    assert classify_channel_from_text(body) == "unknown"


def test_classify_ignores_trigger_line_heat_condition():
    """Trigger lines state future conditions — 「14d OPS ≥.850連5天」 must not
    classify the entry as heat when the first bullet says otherwise."""
    body = ("### X (T, 1B)\n觸發：14d OPS ≥.850連5天\n"
            "- 07-01：xwOBA P70/BB% P80 季線結構（fa_scan）\n")
    assert classify_channel_from_text(body) == "structure"


def test_classify_no_bullet_falls_back_to_body():
    body = "### X (T, 1B)\n觸發：21d surge 觀察\n"
    assert classify_channel_from_text(body) == "heat"


# ── snapshot formatters ──

def test_batter_snapshot_full():
    row = {"pa": 250.0, "xwoba": 0.312, "bb_pct": 8.4, "barrel_pct": 9.1}
    assert format_batter_snapshot(row) == "xwOBA .312 / BB% 8.4 / Barrel% 9.1 / PA 250"


def test_batter_snapshot_partial():
    assert format_batter_snapshot({"bb_pct": 8.4}) == "BB% 8.4"


def test_batter_snapshot_empty():
    assert format_batter_snapshot(None) is None
    assert format_batter_snapshot({}) is None
    assert format_batter_snapshot({"pa": 100.0}) is None  # PA alone is not a snapshot


def test_pitcher_snapshot_full():
    v4 = {"ip_gs": 5.42, "whiff_pct": 24.0, "bb9": 2.951, "gb_pct": 43.2,
          "xwobacon": 0.370, "ip": 80.2}
    assert format_pitcher_snapshot(v4) == (
        "IP/GS 5.42 / Whiff% 24.0 / BB/9 2.95 / GB% 43.2 / xwOBACON .370 / IP 80.2")


def test_pitcher_snapshot_empty():
    assert format_pitcher_snapshot(None) is None
    assert format_pitcher_snapshot({"ip": 10.0}) is None


# ── plan_backfill ──

class _E:
    """Minimal LedgerEntry stand-in."""
    def __init__(self, verdict="watch", ts="2026-07-01",
                 add_reason=None, channel=None):
        self.verdict = verdict
        self.ts = ts
        self.add_reason = add_reason
        self.channel = channel


ROSTER = [
    {"name": "Bat A", "mlb_id": 1, "role": "batter"},
    {"name": "Bat B", "mlb_id": 2, "role": "batter"},
    {"name": "Pit C", "mlb_id": 3, "role": "pitcher"},
]
WATCH = [
    {"name": "Watch D", "body": "### Watch D (T, 1B)\n- 07-01：21d surge（fa_scan）\n"},
    {"name": "Watch E", "body": "### Watch E (T, 1B)\n- 07-01：plain\n"},
]


def test_plan_skips_covered_players():
    histories = {
        "Bat A": [_E(add_reason="真實理由")],          # roster covered
        "Watch D": [_E(channel="structure")],           # watchlist covered
    }
    actions = plan_backfill(ROSTER, WATCH, histories, "2026-07-07",
                            {2: {"xwoba": 0.3, "bb_pct": 8.0, "barrel_pct": 7.0}},
                            {3: {"ip_gs": 5.0, "bb9": 3.0}})
    players = [a["player"] for a in actions]
    assert players == ["Bat B", "Pit C", "Watch E"]


def test_plan_roster_action_shape():
    actions = plan_backfill(
        [{"name": "Bat B", "mlb_id": 2, "role": "batter"}], [], {}, "2026-07-07",
        {2: {"xwoba": 0.301, "bb_pct": 8.0, "barrel_pct": 7.0, "pa": 200.0}}, {})
    (a,) = actions
    assert a["verdict"] == VERDICT_HOLD
    assert a["ts"] == "2026-07-07"
    assert a["channel"] is None
    assert a["add_reason"].startswith(BACKFILL_TAG + " ")
    assert "xwOBA .301" in a["add_reason"]


def test_plan_roster_no_data_snapshot():
    actions = plan_backfill(
        [{"name": "Pit C", "mlb_id": 3, "role": "pitcher"}], [], {}, "2026-07-07",
        {}, {})
    (a,) = actions
    assert a["add_reason"] == f"{BACKFILL_TAG} {NO_DATA_SNAPSHOT}"


def test_plan_watchlist_verdict_from_history():
    histories = {"Watch D": [_E(verdict="watch"), _E(verdict="取代", ts="2026-07-02")]}
    actions = plan_backfill([], WATCH[:1], histories, "2026-07-07", {}, {})
    (a,) = actions
    assert a["verdict"] == "取代"      # latest history verdict, not a default
    assert a["channel"] == "heat"
    assert a["add_reason"] is None


def test_plan_watchlist_empty_history_defaults_watch():
    actions = plan_backfill([], WATCH[1:], histories={}, today="2026-07-07",
                            batter_rows={}, pitcher_v4={})
    (a,) = actions
    assert a["verdict"] == "watch"
    assert a["channel"] == "unknown"


# ── end-to-end against a real DecisionLedger (tmp) + acceptance ──

def test_apply_and_acceptance_roundtrip(tmp_path):
    ledger = DecisionLedger(tmp_path / "ledger.json")
    ledger.record("Bat A", "watch", ts="2026-07-01", add_reason="真實理由")

    names = {p["name"] for p in ROSTER} | {w["name"] for w in WATCH}
    histories = {n: ledger.get_history(n) for n in names}
    failures = acceptance_failures(histories, ROSTER, WATCH)
    assert len(failures) == 4  # Bat B / Pit C reasons + Watch D / Watch E channels

    actions = plan_backfill(ROSTER, WATCH, histories, "2026-07-07",
                            {2: {"xwoba": 0.3, "bb_pct": 8.0, "barrel_pct": 7.0}},
                            {3: {"ip_gs": 5.0, "bb9": 3.0}})
    for a in actions:
        ledger.record(**a)

    fresh = {n: ledger.get_history(n) for n in names}
    assert acceptance_failures(fresh, ROSTER, WATCH) == []

    # idempotent: a second plan on the fresh state is empty
    assert plan_backfill(ROSTER, WATCH, fresh, "2026-07-08", {}, {}) == []


def test_same_day_merge_fills_channel_without_new_row(tmp_path):
    """A scan already recorded today's watch → backfill merges channel into
    that row instead of appending (decision_ledger dedup-merge)."""
    ledger = DecisionLedger(tmp_path / "ledger.json")
    ledger.record("Watch D", "watch", ts="2026-07-07")

    histories = {"Watch D": ledger.get_history("Watch D")}
    actions = plan_backfill([], WATCH[:1], histories, "2026-07-07", {}, {})
    for a in actions:
        ledger.record(**a)

    hist = ledger.get_history("Watch D")
    assert len(hist) == 1
    assert hist[0].channel == "heat"
