"""Unit tests for _multi_agent — Phase 6 multi-agent orchestration helpers."""

import json
import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest

from _multi_agent import (
    AgentResult,
    aggregate_classifications,
    all_parsed,
    any_parsed,
    consensus_check_key,
    count_dissent,
    extract_json,
    run_parallel_agents,
    run_single_agent,
)


# ── extract_json ──

class TestExtractJson:
    def test_fenced_json(self):
        s = 'Some prose\n```json\n{"a": 1, "b": 2}\n```\nMore prose'
        assert extract_json(s) == {"a": 1, "b": 2}

    def test_fenced_json_no_lang(self):
        s = '```\n{"a": 1}\n```'
        assert extract_json(s) == {"a": 1}

    def test_bare_json(self):
        s = 'No fence here {"a": 1, "b": [1, 2]} trailing text'
        assert extract_json(s) == {"a": 1, "b": [1, 2]}

    def test_invalid_json(self):
        assert extract_json("```json\n{not valid}\n```") is None

    def test_empty_string(self):
        assert extract_json("") is None

    def test_no_braces(self):
        assert extract_json("just text no braces") is None

    def test_nested_object_in_fence(self):
        s = '```json\n{"outer": {"inner": [1, 2, 3]}, "flag": true}\n```'
        assert extract_json(s) == {"outer": {"inner": [1, 2, 3]}, "flag": True}

    def test_chinese_unicode(self):
        s = '```json\n{"name": "Nola", "reason": "近況下滑"}\n```'
        assert extract_json(s) == {"name": "Nola", "reason": "近況下滑"}


# ── run_single_agent (mocked subprocess) ──

class TestRunSingleAgent:
    def _make_completed(self, stdout, returncode=0, stderr=""):
        m = MagicMock()
        m.stdout = stdout
        m.stderr = stderr
        m.returncode = returncode
        return m

    @patch("_multi_agent.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = self._make_completed('```json\n{"x": 1}\n```')
        ar = run_single_agent("prompt text", "agent_1", timeout=10)
        assert ar.agent_id == "agent_1"
        assert ar.exit_code == 0
        assert ar.error is None
        assert ar.parsed == {"x": 1}

    @patch("_multi_agent.subprocess.run")
    def test_nonzero_exit(self, mock_run):
        mock_run.return_value = self._make_completed("garbage", returncode=1, stderr="oops")
        ar = run_single_agent("prompt", "agent_2", timeout=10)
        assert ar.exit_code == 1
        assert ar.error == "exit_code 1"
        assert ar.parsed is None  # extract_json returns None on bad input
        assert ar.stderr == "oops"

    @patch("_multi_agent.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=10)
        ar = run_single_agent("prompt", "agent_3", timeout=10)
        assert ar.error == "timeout"
        assert ar.parsed is None
        assert ar.exit_code == -1

    @patch("_multi_agent.subprocess.run")
    def test_generic_exception(self, mock_run):
        mock_run.side_effect = OSError("fork failed")
        ar = run_single_agent("prompt", "agent_4", timeout=10)
        assert ar.error.startswith("exception: OSError")
        assert ar.parsed is None


# ── run_parallel_agents (mocked) ──

class TestRunParallelAgents:
    @patch("_multi_agent.subprocess.run")
    def test_three_agents_parallel(self, mock_run):
        # Each agent returns its own ID embedded in the JSON, so we can verify
        # ordering and threading.
        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args")
            prompt = cmd[2] if len(cmd) > 2 else ""
            agent_id = "unknown"
            for cand in ["agent_1", "agent_2", "agent_3"]:
                if cand in prompt:
                    agent_id = cand
                    break
            m = MagicMock()
            m.stdout = f'```json\n{{"agent": "{agent_id}"}}\n```'
            m.stderr = ""
            m.returncode = 0
            return m

        mock_run.side_effect = side_effect
        prompt_template = "I am {agent_id}, please rank."
        results = run_parallel_agents(prompt_template, "fixture", n_agents=3, timeout=10)
        assert len(results) == 3
        assert [r.agent_id for r in results] == ["agent_1", "agent_2", "agent_3"]
        assert [r.parsed["agent"] for r in results] == ["agent_1", "agent_2", "agent_3"]
        # Verify each subprocess saw the right placeholder substitution
        all_calls = [c.args[0][2] for c in mock_run.call_args_list]
        assert any("agent_1" in c for c in all_calls)
        assert any("agent_2" in c for c in all_calls)
        assert any("agent_3" in c for c in all_calls)

    @patch("_multi_agent.subprocess.run")
    def test_partial_failure(self, mock_run):
        # agent_1 succeeds, agent_2 times out, agent_3 succeeds
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            cmd = args[0] if args else kwargs.get("args")
            prompt = cmd[2] if len(cmd) > 2 else ""
            if "agent_2" in prompt:
                raise subprocess.TimeoutExpired(cmd=["claude"], timeout=10)
            m = MagicMock()
            m.stdout = '```json\n{"ok": true}\n```'
            m.stderr = ""
            m.returncode = 0
            return m

        mock_run.side_effect = side_effect
        results = run_parallel_agents("I am {agent_id}", "fixture", n_agents=3, timeout=10)
        assert len(results) == 3
        assert results[0].error is None
        assert results[1].error == "timeout"
        assert results[2].error is None


# ── consensus_check_key ──

def _ar(parsed, agent_id="agent_x"):
    """Helper: build a fake AgentResult with given parsed dict."""
    return AgentResult(
        agent_id=agent_id, stdout="", stderr="",
        latency_s=0.1, exit_code=0, error=None, parsed=parsed,
    )


class TestConsensusCheckKey:
    def test_all_agree_on_p1(self):
        results = [
            _ar({"ranking": ["X", "Y", "Z", "W"]}),
            _ar({"ranking": ["X", "Z", "Y", "W"]}),
            _ar({"ranking": ["X", "Y", "W", "Z"]}),
        ]
        all_match, info = consensus_check_key(results, ["ranking", 0])
        assert all_match is True
        assert info["distribution"] == {"X": 3}
        assert info["parsed_count"] == 3
        assert info["parse_failures"] == 0

    def test_split_p1(self):
        results = [
            _ar({"ranking": ["X"]}),
            _ar({"ranking": ["Y"]}),
            _ar({"ranking": ["X"]}),
        ]
        all_match, info = consensus_check_key(results, ["ranking", 0])
        assert all_match is False
        assert info["distribution"] == {"X": 2, "Y": 1}

    def test_parse_failure_excluded(self):
        results = [
            _ar({"ranking": ["X"]}),
            _ar(None),  # parse failure
            _ar({"ranking": ["X"]}),
        ]
        all_match, info = consensus_check_key(results, ["ranking", 0])
        assert all_match is True  # 2/2 parsed agree
        assert info["parsed_count"] == 2
        assert info["parse_failures"] == 1

    def test_missing_key_path_counted_as_failure(self):
        results = [
            _ar({"ranking": ["X"]}),
            _ar({"other_key": "..."}),  # missing ranking
            _ar({"ranking": ["X"]}),
        ]
        all_match, info = consensus_check_key(results, ["ranking", 0])
        assert all_match is True
        assert info["parsed_count"] == 2
        assert info["parse_failures"] == 1

    def test_all_parse_fail(self):
        results = [_ar(None), _ar(None)]
        all_match, info = consensus_check_key(results, ["ranking", 0])
        assert all_match is False
        assert info["parsed_count"] == 0
        assert info["parse_failures"] == 2

    def test_nested_path(self):
        results = [
            _ar({"ranked_top": [{"name": "A"}]}),
            _ar({"ranked_top": [{"name": "A"}]}),
        ]
        all_match, info = consensus_check_key(results, ["ranked_top", 0, "name"])
        assert all_match is True
        assert info["distribution"] == {"A": 2}


# ── aggregate_classifications ──

class TestAggregateClassifications:
    def _classify_result(self, classifications):
        return _ar({"classifications": classifications})

    def test_three_worth_unanimous(self):
        results = [
            self._classify_result([{"name": "X", "verdict": "worth"}]),
            self._classify_result([{"name": "X", "verdict": "worth"}]),
            self._classify_result([{"name": "X", "verdict": "worth"}]),
        ]
        out = aggregate_classifications(results, ["X"])
        assert out == {"X": "worth"}

    def test_three_not_worth_unanimous(self):
        results = [
            self._classify_result([{"name": "Y", "verdict": "not_worth"}]),
            self._classify_result([{"name": "Y", "verdict": "not_worth"}]),
            self._classify_result([{"name": "Y", "verdict": "not_worth"}]),
        ]
        assert aggregate_classifications(results, ["Y"]) == {"Y": "not_worth"}

    def test_two_worth_one_borderline(self):
        results = [
            self._classify_result([{"name": "Z", "verdict": "worth"}]),
            self._classify_result([{"name": "Z", "verdict": "worth"}]),
            self._classify_result([{"name": "Z", "verdict": "borderline"}]),
        ]
        assert aggregate_classifications(results, ["Z"]) == {"Z": "worth"}

    def test_two_not_worth_one_worth(self):
        results = [
            self._classify_result([{"name": "Z", "verdict": "worth"}]),
            self._classify_result([{"name": "Z", "verdict": "not_worth"}]),
            self._classify_result([{"name": "Z", "verdict": "not_worth"}]),
        ]
        assert aggregate_classifications(results, ["Z"]) == {"Z": "not_worth"}

    def test_split_1_1_1_to_borderline(self):
        results = [
            self._classify_result([{"name": "M", "verdict": "worth"}]),
            self._classify_result([{"name": "M", "verdict": "not_worth"}]),
            self._classify_result([{"name": "M", "verdict": "borderline"}]),
        ]
        assert aggregate_classifications(results, ["M"]) == {"M": "borderline"}

    def test_two_borderline_one_worth_to_borderline(self):
        # 2 borderline doesn't push to worth or not_worth — stays borderline
        results = [
            self._classify_result([{"name": "B", "verdict": "borderline"}]),
            self._classify_result([{"name": "B", "verdict": "borderline"}]),
            self._classify_result([{"name": "B", "verdict": "worth"}]),
        ]
        assert aggregate_classifications(results, ["B"]) == {"B": "borderline"}

    def test_parse_failure_counts_as_zero_votes(self):
        # 1 worth + 1 parse fail + 1 worth = 2 worth → "worth"
        results = [
            self._classify_result([{"name": "P", "verdict": "worth"}]),
            _ar(None),
            self._classify_result([{"name": "P", "verdict": "worth"}]),
        ]
        assert aggregate_classifications(results, ["P"]) == {"P": "worth"}

    def test_missing_fa_in_classifications_stays_borderline(self):
        # If an agent skips a FA, that FA gets 0 votes → borderline default
        results = [
            self._classify_result([{"name": "A", "verdict": "worth"}]),
            self._classify_result([{"name": "A", "verdict": "worth"}]),
            self._classify_result([]),  # agent skipped
        ]
        # A: 2 worth → worth
        # B: 0 votes → borderline
        out = aggregate_classifications(results, ["A", "B"])
        assert out == {"A": "worth", "B": "borderline"}

    def test_unknown_verdict_ignored(self):
        results = [
            self._classify_result([{"name": "X", "verdict": "garbage"}]),
            self._classify_result([{"name": "X", "verdict": "worth"}]),
            self._classify_result([{"name": "X", "verdict": "worth"}]),
        ]
        # garbage not counted; 2 worth → worth
        assert aggregate_classifications(results, ["X"]) == {"X": "worth"}

    def test_multiple_fas(self):
        results = [
            self._classify_result([
                {"name": "A", "verdict": "worth"},
                {"name": "B", "verdict": "not_worth"},
                {"name": "C", "verdict": "borderline"},
            ]),
            self._classify_result([
                {"name": "A", "verdict": "worth"},
                {"name": "B", "verdict": "not_worth"},
                {"name": "C", "verdict": "worth"},
            ]),
            self._classify_result([
                {"name": "A", "verdict": "borderline"},
                {"name": "B", "verdict": "worth"},
                {"name": "C", "verdict": "borderline"},
            ]),
        ]
        out = aggregate_classifications(results, ["A", "B", "C"])
        assert out == {"A": "worth", "B": "not_worth", "C": "borderline"}


# ── count_dissent ──

class TestCountDissent:
    def test_no_dissent(self):
        results = [
            _ar({"agree_on_p1": True}),
            _ar({"agree_on_p1": True}),
            _ar({"agree_on_p1": True}),
        ]
        assert count_dissent(results, "agree_on_p1") == 0

    def test_one_dissent(self):
        results = [
            _ar({"agree_on_p1": True}),
            _ar({"agree_on_p1": False}),
            _ar({"agree_on_p1": True}),
        ]
        assert count_dissent(results, "agree_on_p1") == 1

    def test_two_dissent_triggers_reeval(self):
        results = [
            _ar({"agree_on_p1": False}),
            _ar({"agree_on_p1": False}),
            _ar({"agree_on_p1": True}),
        ]
        assert count_dissent(results, "agree_on_p1") >= 2

    def test_top1_key_for_fa_review(self):
        results = [
            _ar({"agree_on_top1": False}),
            _ar({"agree_on_top1": True}),
            _ar({"agree_on_top1": False}),
        ]
        assert count_dissent(results, "agree_on_top1") == 2

    def test_parse_failure_not_counted_as_dissent(self):
        # Conservative: failed parses don't push toward re-eval
        results = [
            _ar({"agree_on_p1": False}),
            _ar(None),  # parse fail
            _ar(None),
        ]
        assert count_dissent(results, "agree_on_p1") == 1

    def test_missing_key_not_counted_as_dissent(self):
        results = [
            _ar({"agree_on_p1": False}),
            _ar({"other": "stuff"}),  # missing agree_on_p1
            _ar({"agree_on_p1": False}),
        ]
        assert count_dissent(results, "agree_on_p1") == 2


# ── all_parsed / any_parsed ──

class TestParsedHelpers:
    def test_all_parsed_true(self):
        assert all_parsed([_ar({"a": 1}), _ar({"b": 2})]) is True

    def test_all_parsed_false_one_missing(self):
        assert all_parsed([_ar({"a": 1}), _ar(None)]) is False

    def test_all_parsed_empty_list_false(self):
        # all([]) is True natively, but for our gate, empty results = nothing parsed
        assert all_parsed([]) is False

    def test_any_parsed_true(self):
        assert any_parsed([_ar(None), _ar({"a": 1})]) is True

    def test_any_parsed_false(self):
        assert any_parsed([_ar(None), _ar(None)]) is False

    def test_any_parsed_empty(self):
        assert any_parsed([]) is False
