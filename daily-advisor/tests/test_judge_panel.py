"""Tests for the batter judge panel (issue 030).

Covers the pure layer in _backtest_lib (build_judge_payload /
parse_judge_response / judge_consensus exhaustive combinations /
map_judge_outcome mirror table) and the orchestration in backtest_batter
(run_judge_panel call discipline — 2 calls/week, 1 retry, fail-open to
pending-judge — plus run_weekly_summary wiring and section rendering).

FIXTURE NOTE: judge responses are a NEW LLM output contract — no production
archive exists yet (the real-fixture iron rule applies to *issue-body*
parsing, which test_backtest_batter already covers with real fixtures).
First-batch production judge outputs get a manual HITL audit instead
(issue 030 acceptance; PRD §Further Notes 風險備忘).
"""

import json
from datetime import date

from _backtest_lib import (
    BATTER_CATEGORIES,
    JUDGE_MARGIN_CLEAR,
    JUDGE_MARGIN_NARROW,
    build_judge_payload,
    judge_consensus,
    map_judge_outcome,
    parse_judge_response,
)
from backtest_batter import (
    aggregate_outcome_by_kind,
    format_batter_weekly_section,
    run_judge_panel,
    run_weekly_summary,
)


def _scorecard(player_vals: dict, vs_vals: dict) -> dict:
    cats = {}
    wins = losses = ties = 0
    for cat in BATTER_CATEGORIES:
        a, b = player_vals.get(cat), vs_vals.get(cat)
        if a is None or b is None:
            cats[cat] = {"player": a, "vs": b, "result": "no-data"}
            continue
        result = "win" if a > b else ("loss" if a < b else "tie")
        wins += result == "win"
        losses += result == "loss"
        ties += result == "tie"
        cats[cat] = {"player": a, "vs": b, "result": result}
    return {"wins": wins, "losses": losses, "ties": ties, "categories": cats}


STATS_HOT = {"R": 14, "HR": 5, "RBI": 16, "BB": 9, "AVG": 0.310, "OPS": 0.940}
STATS_COLD = {"R": 6, "HR": 1, "RBI": 4, "BB": 5, "AVG": 0.215, "OPS": 0.601}


def _row(kind="replace", player="FA Guy", vs="My Guy", scorecard="default",
         outcome="pending-judge"):
    if scorecard == "default":
        scorecard = _scorecard(STATS_HOT, STATS_COLD)
    return {"kind": kind, "replace_type": "取代" if kind == "replace" else None,
            "player": player, "vs": vs, "outcome": outcome,
            "scorecard": scorecard, "start_date": "2026-06-12",
            "end_date": "2026-06-13", "n_occurrences": 2,
            "executed": None, "execution": None, "missing": []}


# ── build_judge_payload ──


class TestBuildJudgePayload:
    def test_payload_shape_and_anonymity(self):
        rows = [_row(), _row(kind="watch", player="Watch Guy", vs="Mine 2")]
        payload, idx = build_judge_payload(rows, window_days=21)
        assert idx == [0, 1]
        data = json.loads(payload)
        assert data["window_days"] == 21
        assert [a["account_id"] for a in data["accounts"]] == [1, 2]
        for account in data["accounts"]:
            assert set(account) == {"account_id", "A", "B"}
            assert set(account["A"]) == set(BATTER_CATEGORIES)
            assert set(account["B"]) == set(BATTER_CATEGORIES)
        # Anonymous + claim-blind: no names, kinds, or playing-time fields
        # (PRD C1 #4: no PA; same judging machine for replace and watch).
        for forbidden in ("FA Guy", "My Guy", "Watch Guy", "replace", "watch",
                          "PA", '"G"', "kind"):
            assert forbidden not in payload

    def test_values_map_player_to_a_vs_to_b(self):
        payload, _ = build_judge_payload([_row()], window_days=21)
        account = json.loads(payload)["accounts"][0]
        assert account["A"]["RBI"] == STATS_HOT["RBI"]
        assert account["B"]["RBI"] == STATS_COLD["RBI"]

    def test_null_category_preserved(self):
        cold = dict(STATS_COLD, AVG=None)
        rows = [_row(scorecard=_scorecard(STATS_HOT, cold))]
        payload, _ = build_judge_payload(rows, window_days=21)
        assert json.loads(payload)["accounts"][0]["B"]["AVG"] is None

    def test_rows_without_scorecard_skipped(self):
        rows = [_row(scorecard=None), _row()]
        payload, idx = build_judge_payload(rows, window_days=21)
        assert idx == [1]
        assert [a["account_id"] for a in json.loads(payload)["accounts"]] == [1]

    def test_no_judgeable_rows(self):
        payload, idx = build_judge_payload([_row(scorecard=None)],
                                           window_days=21)
        assert payload is None
        assert idx == []


# ── parse_judge_response ──


def _resp(*pairs):
    return {"judgments": [
        {"account_id": i + 1, "better": better, "margin": margin}
        for i, (better, margin) in enumerate(pairs)]}


class TestParseJudgeResponse:
    def test_valid(self):
        parsed = parse_judge_response(
            _resp(("A", JUDGE_MARGIN_CLEAR), ("B", JUDGE_MARGIN_NARROW)),
            expected_ids=[1, 2])
        assert parsed == {
            1: {"better": "A", "margin": JUDGE_MARGIN_CLEAR},
            2: {"better": "B", "margin": JUDGE_MARGIN_NARROW},
        }

    def test_order_independent(self):
        resp = {"judgments": [
            {"account_id": 2, "better": "B", "margin": JUDGE_MARGIN_CLEAR},
            {"account_id": 1, "better": "A", "margin": JUDGE_MARGIN_NARROW},
        ]}
        parsed = parse_judge_response(resp, expected_ids=[1, 2])
        assert parsed[1]["better"] == "A"
        assert parsed[2]["better"] == "B"

    def test_missing_account_invalid(self):
        assert parse_judge_response(
            _resp(("A", JUDGE_MARGIN_CLEAR)), expected_ids=[1, 2]) is None

    def test_extra_account_invalid(self):
        assert parse_judge_response(
            _resp(("A", JUDGE_MARGIN_CLEAR), ("B", JUDGE_MARGIN_CLEAR)),
            expected_ids=[1]) is None

    def test_duplicate_account_invalid(self):
        resp = {"judgments": [
            {"account_id": 1, "better": "A", "margin": JUDGE_MARGIN_CLEAR},
            {"account_id": 1, "better": "B", "margin": JUDGE_MARGIN_CLEAR},
        ]}
        assert parse_judge_response(resp, expected_ids=[1]) is None

    def test_abstain_value_invalid(self):
        # Forced choice — anything outside A/B (tie, abstain) is a
        # contract violation, not a soft fallback.
        for bad in ("tie", "難分", "", None):
            resp = {"judgments": [
                {"account_id": 1, "better": bad, "margin": JUDGE_MARGIN_CLEAR}]}
            assert parse_judge_response(resp, expected_ids=[1]) is None

    def test_bad_margin_invalid(self):
        resp = {"judgments": [
            {"account_id": 1, "better": "A", "margin": "clearly"}]}
        assert parse_judge_response(resp, expected_ids=[1]) is None

    def test_none_or_malformed_invalid(self):
        assert parse_judge_response(None, expected_ids=[1]) is None
        assert parse_judge_response({}, expected_ids=[1]) is None
        assert parse_judge_response({"judgments": "x"}, expected_ids=[1]) is None


# ── judge_consensus — exhaustive 16 combinations (acceptance criterion) ──


class TestJudgeConsensus:
    def test_all_sixteen_combinations(self):
        for pick1 in ("A", "B"):
            for margin1 in (JUDGE_MARGIN_CLEAR, JUDGE_MARGIN_NARROW):
                for pick2 in ("A", "B"):
                    for margin2 in (JUDGE_MARGIN_CLEAR, JUDGE_MARGIN_NARROW):
                        result = judge_consensus(
                            {"better": pick1, "margin": margin1},
                            {"better": pick2, "margin": margin2})
                        combo = (pick1, margin1, pick2, margin2)
                        if pick1 != pick2:
                            assert result["consensus"] == "難分", combo
                            assert result["winner"] is None, combo
                        elif JUDGE_MARGIN_CLEAR in (margin1, margin2):
                            assert result["consensus"] == "adopted", combo
                            assert result["winner"] == pick1, combo
                        else:  # same pick, both 勉強
                            assert result["consensus"] == "難分", combo
                            assert result["winner"] is None, combo


# ── map_judge_outcome — mirror table (acceptance criterion) ──


ADOPTED_A = {"consensus": "adopted", "winner": "A"}
ADOPTED_B = {"consensus": "adopted", "winner": "B"}
NANFEN = {"consensus": "難分", "winner": None}


class TestMapJudgeOutcome:
    def test_replace_direction(self):
        # replace claim: A (the FA) will outproduce B.
        assert map_judge_outcome("replace", ADOPTED_A) == "hit"
        assert map_judge_outcome("replace", ADOPTED_B) == "miss"
        assert map_judge_outcome("replace", NANFEN) == "難分"

    def test_watch_mirror_direction(self):
        # watch claim: A has NOT clearly outproduced B (PRD C1 #8) —
        # A clearly better = 看走眼 (too conservative); 難分 or B better = 看對.
        assert map_judge_outcome("watch", ADOPTED_A) == "miss"
        assert map_judge_outcome("watch", ADOPTED_B) == "hit"
        assert map_judge_outcome("watch", NANFEN) == "hit"


# ── run_judge_panel orchestration ──


def _good_judgment(payload_prompt: str, better="A", margin=None):
    """Build a contract-valid response covering every account in the prompt."""
    margin = margin or JUDGE_MARGIN_CLEAR
    data = json.loads(payload_prompt.split("\n\n---\n\n", 1)[1])
    return {"judgments": [
        {"account_id": a["account_id"], "better": better, "margin": margin}
        for a in data["accounts"]]}


class TestRunJudgePanel:
    def test_happy_path_two_calls_upgrades_outcomes(self):
        rows = [_row(kind="replace"), _row(kind="watch")]
        calls = []

        def runner(prompt, agent_id):
            calls.append(agent_id)
            return _good_judgment(prompt)

        status = run_judge_panel(rows, _run_judge=runner)
        assert status["status"] == "ok"
        assert status["n_calls"] == 2  # packed weekly — never per-account
        assert len(calls) == 2
        assert rows[0]["outcome"] == "hit"       # replace, adopted A
        assert rows[1]["outcome"] == "miss"      # watch mirror, adopted A
        for row in rows:
            assert row["judge"]["consensus"] == "adopted"
            assert row["judge"]["j1"]["better"] == "A"
            assert row["judge"]["j2"]["better"] == "A"

    def test_split_judges_yield_nanfen(self):
        rows = [_row(kind="replace")]
        responses = iter(["A", "B"])

        def runner(prompt, agent_id):
            return _good_judgment(prompt, better=next(responses))

        run_judge_panel(rows, _run_judge=runner)
        assert rows[0]["outcome"] == "難分"
        assert rows[0]["judge"]["consensus"] == "難分"

    def test_both_narrow_yield_nanfen(self):
        rows = [_row(kind="watch")]

        def runner(prompt, agent_id):
            return _good_judgment(prompt, margin=JUDGE_MARGIN_NARROW)

        run_judge_panel(rows, _run_judge=runner)
        # watch mirror: 難分 → 看對 → hit, consensus stays audited as 難分.
        assert rows[0]["outcome"] == "hit"
        assert rows[0]["judge"]["consensus"] == "難分"

    def test_retry_once_then_success(self):
        rows = [_row()]
        calls = []

        def runner(prompt, agent_id):
            calls.append(agent_id)
            if len(calls) == 1:
                return {"garbage": True}
            return _good_judgment(prompt)

        status = run_judge_panel(rows, _run_judge=runner)
        assert status["status"] == "ok"
        assert status["n_calls"] == 3  # judge_1 retried once
        assert rows[0]["outcome"] == "hit"

    def test_persistent_failure_fails_open_to_pending(self):
        rows = [_row(), _row(kind="watch")]

        def runner(prompt, agent_id):
            return None

        status = run_judge_panel(rows, _run_judge=runner)
        assert status["status"] == "failed"
        assert status["n_calls"] == 2  # judge_1: first try + 1 retry, then stop
        for row in rows:
            assert row["outcome"] == "pending-judge"
            assert "judge" not in row

    def test_unjudgeable_rows_marked_no_data(self):
        rows = [_row(scorecard=None), _row()]

        def runner(prompt, agent_id):
            return _good_judgment(prompt)

        run_judge_panel(rows, _run_judge=runner)
        assert rows[0]["outcome"] == "no-data"
        assert rows[1]["outcome"] == "hit"

    def test_zero_judgeable_rows_makes_zero_calls(self):
        rows = [_row(scorecard=None)]
        calls = []

        def runner(prompt, agent_id):
            calls.append(agent_id)
            return None

        status = run_judge_panel(rows, _run_judge=runner)
        assert status["status"] == "no-accounts"
        assert status["n_calls"] == 0
        assert calls == []
        assert rows[0]["outcome"] == "no-data"

    def test_empty_rows(self):
        status = run_judge_panel([], _run_judge=lambda p, a: None)
        assert status["status"] == "no-accounts"
        assert status["n_calls"] == 0


# ── aggregate_outcome_by_kind ──


class TestAggregateOutcomeByKind:
    def test_split_rates(self):
        rows = [
            _row(kind="replace", outcome="hit"),
            _row(kind="replace", outcome="miss"),
            _row(kind="replace", outcome="難分"),
            _row(kind="watch", outcome="hit"),
            _row(kind="watch", outcome="hit"),
        ]
        agg = aggregate_outcome_by_kind(rows)
        assert agg["replace"] == {"n": 3, "n_judged": 2, "n_hits": 1,
                                  "n_nanfen": 1, "hit_rate": 0.5}
        assert agg["watch"] == {"n": 2, "n_judged": 2, "n_hits": 2,
                                "n_nanfen": 0, "hit_rate": 1.0}

    def test_pending_and_no_data_excluded(self):
        rows = [_row(outcome="pending-judge"), _row(outcome="no-data")]
        agg = aggregate_outcome_by_kind(rows)
        assert agg["replace"]["n"] == 2
        assert agg["replace"]["n_judged"] == 0
        assert agg["replace"]["hit_rate"] is None


# ── run_weekly_summary wiring + section rendering ──


REPLACE_LINES = ("NEW|Joc Pederson|TEX||立即行動|Luis Arraez|摘要\n"
                 "ACTION|Joc Pederson|立即取代|Luis Arraez")
WATCH_LINES = "NEW|Kody Clemens|MIL||觀察|Luis Arraez|摘要"


def _issue(body_lines: str, created: str) -> dict:
    return {"body": f"```waiver-log\n{body_lines}\n```",
            "createdAt": created, "number": 999}


def _stats_for(name):
    return {"Joc Pederson": dict(STATS_HOT, G=15),
            "Kody Clemens": dict(STATS_COLD, G=12),
            "Luis Arraez": dict(STATS_COLD, G=14)}[name]


class TestWeeklySummaryWiring:
    def _run(self, judge_runner):
        issues = [_issue(f"{REPLACE_LINES}\n{WATCH_LINES}",
                         "2026-06-12T04:30:00Z")]
        ids = {"Joc Pederson": 1001, "Kody Clemens": 1002, "Luis Arraez": 2001}
        names = {v: k for k, v in ids.items()}
        return run_weekly_summary(
            today=date(2026, 7, 5),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_stats=lambda mlb_id, start: _stats_for(names[mlb_id]),
            _search_mlb_id=lambda name: ids.get(name),
            _roster_index={},
            _roster_timeline=[],
            _judge_runner=judge_runner,
        )

    def test_judged_end_to_end(self):
        stats = self._run(lambda prompt, agent_id: _good_judgment(prompt))
        outcomes = {r["kind"]: r["outcome"] for r in stats["episodes"]}
        assert outcomes == {"replace": "hit", "watch": "miss"}
        assert stats["judge_panel"]["status"] == "ok"
        assert stats["judge_panel"]["n_calls"] == 2
        assert stats["outcome_by_kind"]["replace"]["hit_rate"] == 1.0
        assert stats["outcome_by_kind"]["watch"]["hit_rate"] == 0.0
        section = format_batter_weekly_section(stats)
        assert "Judge panel" in section
        assert "**hit**" in section and "**miss**" in section
        assert "J1 A·明顯" in section and "J2 A·明顯" in section
        # 031 executed split rates light up once hit/miss exist (unknown
        # bucket here — empty timeline).
        assert "unknown 2" in section

    def test_no_runner_keeps_pending_judge(self):
        # Hermetic default: tests / --no-judge never subprocess claude.
        stats = self._run(None)
        for row in stats["episodes"]:
            assert row["outcome"] == "pending-judge"
        assert stats["judge_panel"]["status"] == "skipped"
        section = format_batter_weekly_section(stats)
        assert "pending-judge" in section

    def test_failed_panel_renders_warning(self):
        stats = self._run(lambda prompt, agent_id: None)
        assert stats["judge_panel"]["status"] == "failed"
        section = format_batter_weekly_section(stats)
        assert "pending-judge" in section
        assert "⚠️" in section


# ── default runner wiring (neutral cwd via _multi_agent) ──


class TestDefaultRunner:
    def test_claude_judge_runner_delegates_to_run_single_agent(self, monkeypatch):
        import backtest_batter

        seen = {}

        class FakeResult:
            parsed = {"judgments": []}
            error = None

        def fake_run_single_agent(prompt, agent_id, timeout=600):
            seen["prompt"] = prompt
            seen["agent_id"] = agent_id
            return FakeResult()

        monkeypatch.setattr(backtest_batter, "run_single_agent",
                            fake_run_single_agent)
        out = backtest_batter._claude_judge_runner("PROMPT", "judge_1")
        assert out == {"judgments": []}
        assert seen == {"prompt": "PROMPT", "agent_id": "judge_1"}


# ── prompt file contract smoke ──


class TestPromptFile:
    def test_prompt_exists_and_pins_contract(self):
        from backtest_batter import _JUDGE_PROMPT_PATH

        text = _JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
        for token in ("account_id", '"better"', '"margin"',
                      JUDGE_MARGIN_CLEAR, JUDGE_MARGIN_NARROW, "judgments"):
            assert token in text
