"""Tests for the batter decision backtest (issue 029) — lib + pipeline.

Covers the batter additions in _backtest_lib (waiver-log verdict parsing,
episode keys, byDateRange parsing, six-category scorecard) and the
backtest_batter pipeline with injected boundaries (gh / MLB API).

FIXTURE IRON RULE (PRD Testing Decisions): parse tests run against real
artifacts —
  - issue_306_batter.json: verbatim production batter issue archive
    (pre-028 grammar → must yield ZERO reconcilable verdicts)
  - ab_028_b_result.json: verbatim claude -p result from the issue-028
    paired A/B run on the real 2026-06-10 payload — the only real
    new-grammar (7-field NEW / ACTION / CLOSE) output that exists
    pre-deploy. First production new-grammar issue lands 2026-06-11;
    a production fixture should be added once archived.
  - mlb_bydaterange_hitting_669127.json / _empty.json: verbatim MLB
    statsapi person byDateRange responses (note: the API returns
    DUPLICATE identical splits for a single-team player — the parser
    must not double-count).
Synthetic lines below are boundary cases only, derived from the real
fixtures' shapes, and are explicitly marked as such.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from _backtest_lib import (
    BatterVerdict,
    batter_episode_key,
    compare_batter_categories,
    dedupe_episodes,
    extract_waiver_log_block,
    parse_batter_verdicts,
    parse_bydaterange_hitting,
    select_due_episodes,
)
import backtest_batter
from backtest_batter import (
    collect_batter_verdicts,
    format_batter_weekly_section,
    run_weekly_summary,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture()
def issue_306_body() -> str:
    """Verbatim production batter issue body (pre-028 grammar)."""
    return _load_json("issue_306_batter.json")["body"]


@pytest.fixture()
def ab_028_b_text() -> str:
    """Verbatim claude -p output text from the 028 paired A/B B-run."""
    return _load_json("ab_028_b_result.json")["result"]


# ── extract_waiver_log_block ──


class TestExtractBlock:
    def test_production_issue_block_extracted(self, issue_306_body):
        block = extract_waiver_log_block(issue_306_body)
        assert block is not None
        assert "NEW|Joc Pederson" in block
        assert "```" not in block

    def test_real_llm_output_block_extracted(self, ab_028_b_text):
        block = extract_waiver_log_block(ab_028_b_text)
        assert block is not None
        assert block.startswith("NEW|Joc Pederson")
        assert "CLOSE|Dansby Swanson" in block

    def test_sp_issue_has_no_block(self):
        body = _load_json("issue_305_sp_v4.json")["body"]
        assert extract_waiver_log_block(body) is None

    def test_crlf_body_still_extracts(self, ab_028_b_text):
        # gh --json body may carry \r\n (real-fixture-derived boundary).
        block = extract_waiver_log_block(ab_028_b_text.replace("\n", "\r\n"))
        assert block is not None
        assert "ACTION|Joc Pederson" in block

    def test_empty_block_returns_empty_string(self):
        # Prompt spec: 無任何行動 → 輸出空 ```waiver-log``` 區塊 (synthetic).
        assert extract_waiver_log_block("text\n```waiver-log\n```\nafter") == ""


# ── parse_batter_verdicts — real fixtures (primary suite) ──


class TestParseBatterVerdictsRealFixtures:
    def test_pre_028_production_issue_yields_zero_verdicts(self, issue_306_body):
        # #306 is pre-028: 6-field NEW rows (no vs column), no ACTION lines.
        # Nothing is reconcilable — the calendar pole starts at 028 deploy.
        assert parse_batter_verdicts(issue_306_body, date(2026, 6, 10)) == []

    def test_real_new_grammar_output_parses_replace_and_watch(self, ab_028_b_text):
        verdicts = parse_batter_verdicts(ab_028_b_text, date(2026, 6, 10))
        assert [
            (v.kind, v.player, v.vs, v.replace_type) for v in verdicts
        ] == [
            ("replace", "Joc Pederson", "Luis Arraez", "立即取代"),
            ("watch", "Kody Clemens", "Luis Arraez", None),
            ("watch", "Curtis Mead", "Luis Arraez", None),
        ]
        assert all(v.issue_date == date(2026, 6, 10) for v in verdicts)

    def test_action_consumes_new_no_duplicate_watch(self, ab_028_b_text):
        # Pederson has BOTH a 7-field NEW (vs Arraez) and an ACTION line —
        # he must appear once, as replace, never additionally as watch.
        verdicts = parse_batter_verdicts(ab_028_b_text, date(2026, 6, 10))
        pederson = [v for v in verdicts if v.player == "Joc Pederson"]
        assert len(pederson) == 1
        assert pederson[0].kind == "replace"

    def test_update_and_close_lines_emit_nothing(self, ab_028_b_text):
        # 11 UPDATE + 7 CLOSE lines in the real block → no verdicts from them.
        verdicts = parse_batter_verdicts(ab_028_b_text, date(2026, 6, 10))
        names = {v.player for v in verdicts}
        assert "Cam Smith" not in names       # UPDATE only
        assert "Dansby Swanson" not in names  # CLOSE only

    def test_body_without_block_returns_empty(self):
        body = _load_json("issue_305_sp_v4.json")["body"]
        assert parse_batter_verdicts(body, date(2026, 6, 9)) == []


class TestParseBatterVerdictsBoundaries:
    """Synthetic boundary lines — derived from the real grammar, NOT
    representative of any archived production block."""

    @staticmethod
    def _parse(lines: str):
        return parse_batter_verdicts(
            f"```waiver-log\n{lines}\n```", date(2026, 6, 11))

    def test_action_invalid_type_skipped(self):
        assert self._parse("ACTION|Cam Smith|觀察|Jarren Duran") == []

    def test_action_empty_vs_skipped(self):
        assert self._parse("ACTION|Cam Smith|取代|") == []

    def test_action_too_few_fields_skipped(self):
        assert self._parse("ACTION|Cam Smith|取代") == []

    def test_new_6_field_pre028_skipped(self):
        assert self._parse("NEW|Cam Smith|HOU||立即行動|Season P80 摘要") == []

    def test_new_7_field_empty_vs_skipped(self):
        assert self._parse("NEW|Cam Smith|HOU||觸發||摘要") == []

    def test_duplicate_action_lines_dedupe(self):
        verdicts = self._parse(
            "ACTION|Cam Smith|取代|Jarren Duran\n"
            "ACTION|Cam Smith|立即取代|Jarren Duran")
        assert len(verdicts) == 1
        assert verdicts[0].replace_type == "取代"  # first occurrence wins

    def test_summary_with_pipes_does_not_break_new_parse(self):
        verdicts = self._parse("NEW|Cam Smith|HOU||觸發|Jarren Duran|摘要 a|b|c")
        assert len(verdicts) == 1
        assert verdicts[0].kind == "watch"
        assert verdicts[0].vs == "Jarren Duran"


# ── batter_episode_key ──


class TestBatterEpisodeKey:
    @staticmethod
    def _v(kind="replace", player="Joc Pederson", vs="Luis Arraez",
           replace_type="取代", d=date(2026, 6, 11)):
        return BatterVerdict(issue_date=d, kind=kind, player=player, vs=vs,
                             replace_type=replace_type)

    def test_replace_type_intensity_does_not_split_episodes(self):
        a = self._v(replace_type="取代")
        b = self._v(replace_type="立即取代", d=date(2026, 6, 12))
        assert batter_episode_key(a) == batter_episode_key(b)

    def test_watch_and_replace_same_pair_are_distinct_accounts(self):
        watch = self._v(kind="watch", replace_type=None)
        rep = self._v(kind="replace")
        assert batter_episode_key(watch) != batter_episode_key(rep)

    def test_accent_drift_same_key(self):
        a = self._v(player="Heriberto Hernández")
        b = self._v(player="Heriberto Hernandez")
        assert batter_episode_key(a) == batter_episode_key(b)

    def test_different_vs_target_different_key(self):
        a = self._v(vs="Luis Arraez")
        b = self._v(vs="Ozzie Albies")
        assert batter_episode_key(a) != batter_episode_key(b)

    def test_dedupe_episodes_integration(self):
        # Same replace pair across 3 adjacent days = ONE episode anchored on
        # the first day (shared dedupe from issue 027 reused unchanged).
        verdicts = [self._v(d=date(2026, 6, 11)),
                    self._v(replace_type="立即取代", d=date(2026, 6, 12)),
                    self._v(d=date(2026, 6, 13))]
        episodes = dedupe_episodes(
            verdicts, key_fn=batter_episode_key,
            date_fn=lambda v: v.issue_date)
        assert len(episodes) == 1
        assert episodes[0].start_date == date(2026, 6, 11)
        assert len(episodes[0].occurrences) == 3


# ── parse_bydaterange_hitting — real MLB API fixtures ──


class TestParseByDateRange:
    def test_real_response_parses_six_categories(self):
        data = _load_json("mlb_bydaterange_hitting_669127.json")
        stats = parse_bydaterange_hitting(data)
        assert stats == {
            "R": 14, "HR": 4, "RBI": 12, "BB": 9,
            "AVG": 0.305, "OPS": 0.959, "G": 15,
        }

    def test_duplicate_identical_splits_not_double_counted(self):
        # The verbatim fixture really does contain two identical splits —
        # the API quirk this test pins down.
        data = _load_json("mlb_bydaterange_hitting_669127.json")
        assert len(data["stats"][0]["splits"]) == 2
        assert parse_bydaterange_hitting(data)["R"] == 14

    def test_empty_window_returns_none(self):
        data = _load_json("mlb_bydaterange_hitting_empty.json")
        assert parse_bydaterange_hitting(data) is None

    def test_mid_window_trade_two_distinct_splits_combined(self):
        # Synthetic two-team variant derived from the real fixture shape.
        data = _load_json("mlb_bydaterange_hitting_669127.json")
        first = data["stats"][0]["splits"][0]
        second = json.loads(json.dumps(first))
        second["team"] = {"id": 147, "name": "New York Yankees"}
        st = second["stat"]
        st.update({"gamesPlayed": 5, "runs": 3, "homeRuns": 1, "rbi": 2,
                   "baseOnBalls": 4, "hits": 6, "atBats": 18,
                   "hitByPitch": 0, "sacFlies": 1, "totalBases": 9})
        data["stats"][0]["splits"] = [first, second]
        stats = parse_bydaterange_hitting(data)
        assert (stats["R"], stats["HR"], stats["RBI"], stats["BB"],
                stats["G"]) == (17, 5, 14, 13, 20)
        # Ratios recomputed from summed components, not averaged.
        f = first["stat"]
        hits = int(f["hits"]) + 6
        ab = int(f["atBats"]) + 18
        assert stats["AVG"] == pytest.approx(hits / ab, abs=1e-4)
        assert stats["OPS"] is not None


# ── compare_batter_categories ──


class TestCompareCategories:
    A = {"R": 14, "HR": 4, "RBI": 12, "BB": 9, "AVG": 0.305, "OPS": 0.959, "G": 15}
    B = {"R": 8, "HR": 5, "RBI": 12, "BB": 4, "AVG": 0.250, "OPS": 0.700, "G": 14}

    def test_scorecard_counts_wins_losses_ties(self):
        card = compare_batter_categories(self.A, self.B)
        # A wins R/BB/AVG/OPS, loses HR, ties RBI.
        assert (card["wins"], card["losses"], card["ties"]) == (4, 1, 1)
        assert card["categories"]["RBI"]["result"] == "tie"
        assert card["categories"]["HR"]["result"] == "loss"
        assert card["categories"]["OPS"]["result"] == "win"

    def test_six_categories_no_sb(self):
        card = compare_batter_categories(self.A, self.B)
        assert set(card["categories"]) == {"R", "HR", "RBI", "BB", "AVG", "OPS"}

    def test_missing_side_returns_none(self):
        assert compare_batter_categories(None, self.B) is None
        assert compare_batter_categories(self.A, None) is None

    def test_unparseable_ratio_excluded_from_counts(self):
        a = dict(self.A, AVG=None)
        card = compare_batter_categories(a, self.B)
        assert card["categories"]["AVG"]["result"] == "no-data"
        assert card["wins"] + card["losses"] + card["ties"] == 5


# ── pipeline: collect / run_weekly_summary with injected boundaries ──


def _issue(body: str, created: str, number: int = 999) -> dict:
    return {"body": body, "createdAt": created, "number": number,
            "title": "[FA Scan 打者] test"}


def _block_body(lines: str) -> str:
    return f"analysis text\n\n```waiver-log\n{lines}\n```\n"


REPLACE_LINES = ("NEW|Joc Pederson|TEX||立即行動|Luis Arraez|摘要\n"
                 "ACTION|Joc Pederson|立即取代|Luis Arraez")
WATCH_LINES = "NEW|Kody Clemens|MIN||14d 維持|Luis Arraez|摘要"

STATS_FA = {"R": 14, "HR": 4, "RBI": 12, "BB": 9, "AVG": 0.305, "OPS": 0.959, "G": 15}
STATS_MY = {"R": 8, "HR": 5, "RBI": 12, "BB": 4, "AVG": 0.250, "OPS": 0.700, "G": 14}


class TestPipeline:
    def test_collect_batter_verdicts_across_issues(self, ab_028_b_text):
        issues = [
            _issue(ab_028_b_text, "2026-06-10T04:30:00Z", 306),
            _issue(_load_json("issue_305_sp_v4.json")["body"],
                   "2026-06-09T04:30:00Z", 305),
        ]
        verdicts = collect_batter_verdicts(issues)
        assert len(verdicts) == 3  # SP issue contributes nothing

    def _run(self, issues, today, ids=None, stats=None):
        ids = ids or {"Joc Pederson": 1001, "Kody Clemens": 1002,
                      "Luis Arraez": 2001}
        stats = stats if stats is not None else {
            1001: STATS_FA, 1002: STATS_FA, 2001: STATS_MY}
        return run_weekly_summary(
            today=today,
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_stats=lambda mlb_id, start: stats.get(mlb_id),
            _search_mlb_id=lambda name: ids.get(name),
            # Real roster_config contains the very players these verdicts
            # name (Arraez is on-roster) — inject empty for determinism.
            _roster_index={},
        )

    def test_due_replace_episode_gets_pending_judge_scorecard(self):
        today = date(2026, 7, 5)
        issues = [
            _issue(_block_body(REPLACE_LINES), "2026-06-12T04:30:00Z"),
            _issue(_block_body(REPLACE_LINES), "2026-06-13T04:30:00Z"),
        ]
        stats = self._run(issues, today)
        assert stats["n_total"] == 1  # episode-deduped (2 adjacent days)
        ep = stats["episodes"][0]
        assert ep["kind"] == "replace"
        assert ep["replace_type"] == "立即取代"
        assert ep["player"] == "Joc Pederson"
        assert ep["vs"] == "Luis Arraez"
        assert ep["start_date"] == "2026-06-12"
        assert ep["n_occurrences"] == 2
        assert ep["outcome"] == "pending-judge"
        assert (ep["scorecard"]["wins"], ep["scorecard"]["losses"],
                ep["scorecard"]["ties"]) == (4, 1, 1)

    def test_age_window_excludes_immature_episodes(self):
        today = date(2026, 7, 5)
        issues = [
            _issue(_block_body(REPLACE_LINES), "2026-06-12T04:30:00Z"),  # age 23
            _issue(_block_body(WATCH_LINES), "2026-06-20T04:30:00Z"),    # age 15
        ]
        stats = self._run(issues, today)
        assert stats["n_total"] == 1
        assert stats["n_episodes_in_lookback"] == 2
        assert stats["episodes"][0]["kind"] == "replace"

    def test_watch_episode_reconciled_with_mirror_note(self):
        today = date(2026, 7, 11)
        issues = [_issue(_block_body(WATCH_LINES), "2026-06-18T04:30:00Z")]
        stats = self._run(issues, today)
        assert stats["n_total"] == 1
        ep = stats["episodes"][0]
        assert ep["kind"] == "watch"
        assert ep["outcome"] == "pending-judge"

    def test_unresolved_player_yields_none_scorecard(self):
        today = date(2026, 7, 5)
        issues = [_issue(_block_body(REPLACE_LINES), "2026-06-12T04:30:00Z")]
        stats = self._run(issues, today, ids={"Luis Arraez": 2001})
        ep = stats["episodes"][0]
        assert ep["outcome"] == "pending-judge"
        assert ep["scorecard"] is None
        assert "Joc Pederson" in " ".join(ep["missing"])

    def test_zero_due_episodes_is_valid_output(self):
        stats = self._run([], date(2026, 7, 5))
        assert stats["n_total"] == 0
        section = format_batter_weekly_section(stats)
        assert "no due episodes" in section
        assert "0 筆可對帳" in section

    def test_pre_028_issue_alone_yields_zero(self, issue_306_body):
        # Real production pre-028 issue inside the lookback → still 0 due.
        issues = [_issue(issue_306_body, "2026-06-10T04:30:00Z", 306)]
        stats = self._run(issues, date(2026, 7, 3))
        assert stats["n_total"] == 0
        assert stats["n_episodes_in_lookback"] == 0


# ── weekly section formatting ──


class TestFormatSection:
    def _stats(self):
        issues = [
            _issue(_block_body(REPLACE_LINES), "2026-06-12T04:30:00Z"),
            _issue(_block_body(WATCH_LINES), "2026-06-12T04:30:00Z"),
        ]
        return run_weekly_summary(
            today=date(2026, 7, 5),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_stats=lambda mlb_id, start: (
                STATS_FA if mlb_id in (1001, 1002) else STATS_MY),
            _search_mlb_id=lambda name: {
                "Joc Pederson": 1001, "Kody Clemens": 1002,
                "Luis Arraez": 2001}.get(name),
            _roster_index={},
        )

    def test_section_lists_episodes_with_scorecards(self):
        section = format_batter_weekly_section(self._stats())
        assert section.startswith("## Weekly Batter Backtest 2026-07-05")
        assert "pending-judge" in section
        assert "4W-1L-1T" in section
        assert "add Joc Pederson ⇄ drop Luis Arraez" in section
        assert "watch Kody Clemens vs Luis Arraez" in section

    def test_override_run_is_marked(self):
        stats = run_weekly_summary(
            today=date(2026, 7, 5), age_min=0,
            _fetch_issues=lambda days, repo, label: [],
            _fetch_stats=lambda mlb_id, start: None,
            _search_mlb_id=lambda name: None,
            _roster_index={},
        )
        assert "OVERRIDE DEMO RUN" in format_batter_weekly_section(stats)


# ── doc append ──


class TestAppendDoc:
    def test_appends_section_to_doc(self, tmp_path):
        doc = tmp_path / "batter-decisions-backtest.md"
        doc.write_text("# header\n", encoding="utf-8")
        backtest_batter.append_to_batter_doc("## section\n", doc_path=doc)
        text = doc.read_text(encoding="utf-8")
        assert text.startswith("# header\n")
        assert text.endswith("## section\n")

    def test_missing_doc_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            backtest_batter.append_to_batter_doc(
                "x", doc_path=tmp_path / "nope.md")
