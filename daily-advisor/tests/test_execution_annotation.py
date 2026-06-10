"""Tests for the execution annotation (issue 031).

Covers the pure judgment layer in _backtest_lib (parse_roster_snapshot /
judge_executed), the executed/not-executed split aggregation, the pipeline
wiring in backtest_batter, and fetch_roster_timeline against a throwaway
real git repo (prior art: test_git_sync — no network, local repo only).

Kept in its own file (not test_backtest_batter.py) because issue 030
(judge panel) develops against that file in parallel.

FIXTURE NOTE: parse_roster_snapshot runs against the real repo
roster_config.json (live source of truth — membership asserted via shape
+ cant_cut players, not a frozen roster list). judge_executed timelines
are synthetic by necessity: they encode roster membership over time,
which no single archived file represents.
"""

import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from _backtest_lib import (
    EXECUTION_GRACE_DAYS,
    judge_executed,
    parse_roster_snapshot,
)
from backtest_batter import (
    aggregate_executed_split,
    fetch_roster_timeline,
    format_batter_weekly_section,
    run_weekly_summary,
)

_REAL_ROSTER_CONFIG = (
    Path(__file__).resolve().parent.parent / "roster_config.json")


def _snap(d: date, players: list[tuple[int, str]]):
    """Synthetic snapshot via the real parser (one shape, one code path)."""
    config = {"batters": [{"mlb_id": i, "name": n} for i, n in players]}
    return parse_roster_snapshot(config, d)


# ── parse_roster_snapshot ──


class TestParseRosterSnapshot:
    def test_real_roster_config_parses_both_sections(self):
        config = json.loads(_REAL_ROSTER_CONFIG.read_text(encoding="utf-8"))
        snap = parse_roster_snapshot(config, date(2026, 6, 10))
        assert snap.snap_date == date(2026, 6, 10)
        assert len(snap.mlb_ids) == len(config["batters"]) + len(config["pitchers"])
        # cant_cut core (CLAUDE.md) — names normalized, pitchers included.
        assert "tarik skubal" in snap.names
        assert "manny machado" in snap.names

    def test_names_are_normalized(self):
        snap = _snap(date(2026, 6, 1), [(1, "Heriberto Hernández")])
        assert snap.names == frozenset({"heriberto hernandez"})

    def test_empty_config_yields_empty_sets(self):
        snap = parse_roster_snapshot({}, date(2026, 6, 1))
        assert snap.mlb_ids == frozenset()
        assert snap.names == frozenset()


# ── judge_executed ──


BASE = date(2026, 6, 12)  # window_start in most cases below
END = date(2026, 6, 16)   # window_end (episode end + grace)


class TestJudgeExecuted:
    def _judge(self, timeline, player_id=1001, name="Joc Pederson",
               start=BASE, end=END):
        return judge_executed(timeline, player_name=name, player_id=player_id,
                              window_start=start, window_end=end)

    def test_executed_in_window(self):
        timeline = [
            _snap(date(2026, 6, 10), [(2001, "Luis Arraez")]),
            _snap(date(2026, 6, 13), [(2001, "Luis Arraez"),
                                      (1001, "Joc Pederson")]),
        ]
        result = self._judge(timeline)
        assert result["executed"] is True
        assert result["status"] == "executed"
        assert result["matched_date"] == "2026-06-13"
        assert result["match_by"] == "mlb_id"

    def test_not_executed_other_adds_in_window(self):
        timeline = [
            _snap(date(2026, 6, 10), [(2001, "Luis Arraez")]),
            _snap(date(2026, 6, 14), [(2001, "Luis Arraez"),
                                      (3001, "Someone Else")]),
        ]
        result = self._judge(timeline)
        assert result["executed"] is False
        assert result["status"] == "not-executed"

    def test_not_executed_no_commits_in_window(self):
        # No commits in window = roster unchanged — absence holds from
        # the baseline alone; this must NOT degrade to unknown.
        timeline = [_snap(date(2026, 6, 8), [(2001, "Luis Arraez")])]
        result = self._judge(timeline)
        assert result["executed"] is False

    def test_delayed_effect_lands_inside_grace(self):
        # Daily-Tomorrow waiver claim: recommendation episode ends, roster
        # commit lands days later — still inside end + grace.
        episode_end = date(2026, 6, 13)
        grace_end = episode_end + timedelta(days=EXECUTION_GRACE_DAYS)
        timeline = [
            _snap(date(2026, 6, 10), []),
            _snap(grace_end, [(1001, "Joc Pederson")]),
        ]
        result = self._judge(timeline, end=grace_end)
        assert result["executed"] is True
        assert result["status"] == "executed"

    def test_entry_after_window_end_is_not_executed(self):
        timeline = [
            _snap(date(2026, 6, 10), []),
            _snap(END + timedelta(days=1), [(1001, "Joc Pederson")]),
        ]
        result = self._judge(timeline)
        assert result["executed"] is False

    def test_window_endpoints_inclusive(self):
        for d in (BASE, END):
            timeline = [_snap(date(2026, 6, 10), []),
                        _snap(d, [(1001, "Joc Pederson")])]
            assert self._judge(timeline)["executed"] is True, d

    def test_homonym_same_name_different_id_does_not_match(self):
        # search_mlb_id first-hit homonym is the documented failure mode:
        # when the id is known, a same-name different-id roster entry must
        # NOT count as execution (no silent name fallback).
        timeline = [
            _snap(date(2026, 6, 10), []),
            _snap(date(2026, 6, 13), [(9999, "Joc Pederson")]),
        ]
        result = self._judge(timeline, player_id=1001)
        assert result["executed"] is False

    def test_name_fallback_only_when_id_unresolved(self):
        timeline = [
            _snap(date(2026, 6, 10), []),
            _snap(date(2026, 6, 13), [(9999, "Joc Pederson")]),
        ]
        result = self._judge(timeline, player_id=None)
        assert result["executed"] is True
        assert result["match_by"] == "name"

    def test_accent_drift_matches_by_name(self):
        timeline = [
            _snap(date(2026, 6, 10), []),
            _snap(date(2026, 6, 13), [(8888, "Heriberto Hernández")]),
        ]
        result = self._judge(timeline, player_id=None,
                             name="Heriberto Hernandez")
        assert result["executed"] is True

    def test_already_rostered_before_window(self):
        timeline = [_snap(date(2026, 6, 10), [(1001, "Joc Pederson")])]
        result = self._judge(timeline)
        assert result["executed"] is True
        assert result["status"] == "already-rostered"
        assert result["matched_date"] == "2026-06-10"

    def test_empty_timeline_is_unknown(self):
        result = self._judge([])
        assert result["executed"] is None
        assert result["status"] == "unknown"

    def test_no_baseline_before_window_is_unknown(self):
        # Shallow history: earliest snapshot is inside the window — prior
        # absence cannot be established, must NOT report a wrong False.
        timeline = [_snap(date(2026, 6, 13), [(2001, "Luis Arraez")])]
        result = self._judge(timeline)
        assert result["executed"] is None
        assert result["status"] == "unknown"

    def test_baseline_is_latest_snapshot_before_window(self):
        # Player added 6/9, dropped 6/11 (both pre-window): the 6/11
        # snapshot is the baseline, so a re-add in window = executed.
        timeline = [
            _snap(date(2026, 6, 9), [(1001, "Joc Pederson")]),
            _snap(date(2026, 6, 11), []),
            _snap(date(2026, 6, 14), [(1001, "Joc Pederson")]),
        ]
        result = self._judge(timeline)
        assert result["status"] == "executed"
        assert result["matched_date"] == "2026-06-14"


# ── aggregate_executed_split ──


def _row(executed, outcome="pending-judge"):
    return {"executed": executed, "outcome": outcome}


class TestAggregateExecutedSplit:
    def test_pending_judge_counts_but_no_rates(self):
        split = aggregate_executed_split(
            [_row(True), _row(True), _row(False), _row(None)])
        assert split["executed"]["n"] == 2
        assert split["not_executed"]["n"] == 1
        assert split["unknown"]["n"] == 1
        assert split["executed"]["hit_rate"] is None
        assert split["not_executed"]["hit_rate"] is None

    def test_rates_appear_once_outcomes_judged(self):
        # Forward-compat with issue 030: hit/miss enter the denominator,
        # 難分 stays out (like pending-judge).
        split = aggregate_executed_split([
            _row(True, "hit"), _row(True, "miss"),
            _row(False, "hit"), _row(False, "難分"),
        ])
        assert split["executed"]["hit_rate"] == 0.5
        assert split["executed"]["n_judged"] == 2
        assert split["not_executed"]["hit_rate"] == 1.0
        assert split["not_executed"]["n_judged"] == 1

    def test_empty_rows(self):
        split = aggregate_executed_split([])
        assert all(split[g]["n"] == 0 for g in split)


# ── pipeline wiring (run_weekly_summary + section format) ──


REPLACE_LINES = ("NEW|Joc Pederson|TEX||立即行動|Luis Arraez|摘要\n"
                 "ACTION|Joc Pederson|立即取代|Luis Arraez")
STATS_FA = {"R": 14, "HR": 4, "RBI": 12, "BB": 9,
            "AVG": 0.305, "OPS": 0.959, "G": 15}


def _issue(body_lines: str, created: str) -> dict:
    return {"body": f"```waiver-log\n{body_lines}\n```",
            "createdAt": created, "number": 999}


class TestPipelineExecution:
    def _run(self, timeline):
        issues = [_issue(REPLACE_LINES, "2026-06-12T04:30:00Z"),
                  _issue(REPLACE_LINES, "2026-06-13T04:30:00Z")]
        return run_weekly_summary(
            today=date(2026, 7, 5),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_stats=lambda mlb_id, start: STATS_FA,
            _search_mlb_id=lambda name: {"Joc Pederson": 1001,
                                         "Luis Arraez": 2001}.get(name),
            _roster_index={},
            _roster_timeline=timeline,
        )

    def test_executed_row_and_section(self):
        # Episode 6/12-6/13; roster commit 6/15 = end + 2, inside grace 3.
        timeline = [
            _snap(date(2026, 6, 10), [(2001, "Luis Arraez")]),
            _snap(date(2026, 6, 15), [(1001, "Joc Pederson")]),
        ]
        stats = self._run(timeline)
        ep = stats["episodes"][0]
        assert ep["executed"] is True
        assert ep["execution"]["matched_date"] == "2026-06-15"
        assert stats["executed_split"]["executed"]["n"] == 1
        section = format_batter_weekly_section(stats)
        assert "〔executed 2026-06-15〕" in section
        assert "Executed split" in section
        assert "executed 1（hit-rate —）" in section

    def test_not_executed_row_and_section(self):
        timeline = [_snap(date(2026, 6, 10), [(2001, "Luis Arraez")])]
        stats = self._run(timeline)
        assert stats["episodes"][0]["executed"] is False
        assert stats["executed_split"]["not_executed"]["n"] == 1
        assert "〔not executed〕" in format_batter_weekly_section(stats)

    def test_unknown_timeline_row_and_section(self):
        stats = self._run([])
        assert stats["episodes"][0]["executed"] is None
        section = format_batter_weekly_section(stats)
        assert "〔execution unknown〕" in section
        assert "unknown 1" in section

    def test_zero_due_section_still_renders_split_line(self):
        stats = run_weekly_summary(
            today=date(2026, 7, 5),
            _fetch_issues=lambda days, repo, label: [],
            _fetch_stats=lambda mlb_id, start: None,
            _search_mlb_id=lambda name: None,
            _roster_index={}, _roster_timeline=[],
        )
        section = format_batter_weekly_section(stats)
        assert "Executed split" in section
        assert "executed 0" in section


# ── fetch_roster_timeline (real throwaway git repo) ──


def _git(args, cwd, env_dates=None):
    import os
    env = dict(os.environ)
    if env_dates:
        env["GIT_AUTHOR_DATE"] = env_dates
        env["GIT_COMMITTER_DATE"] = env_dates
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _commit_config(repo, players, when):
    cfg_path = repo / "daily-advisor" / "roster_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({
        "batters": [{"mlb_id": i, "name": n} for i, n in players],
        "pitchers": [],
    }), encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", f"roster @ {when}"], repo, env_dates=when)


class TestFetchRosterTimeline:
    @pytest.fixture()
    def repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(["init", "-q"], repo)
        _git(["config", "user.email", "t@t"], repo)
        _git(["config", "user.name", "tester"], repo)
        _git(["config", "commit.gpgsign", "false"], repo)
        _commit_config(repo, [(2001, "Luis Arraez")],
                       "2026-06-01T12:00:00+00:00")
        _commit_config(repo, [(2001, "Luis Arraez"), (1001, "Joc Pederson")],
                       "2026-06-05T07:07:00+00:00")
        _commit_config(repo, [(1001, "Joc Pederson")],
                       "2026-06-08T07:22:00+00:00")
        return repo

    def test_timeline_includes_baseline_before_since(self, repo):
        timeline = fetch_roster_timeline(date(2026, 6, 4), repo_root=repo)
        assert [s.snap_date for s in timeline] == [
            date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 8)]
        assert 1001 not in timeline[0].mlb_ids
        assert 1001 in timeline[1].mlb_ids
        assert 2001 not in timeline[2].mlb_ids

    def test_end_to_end_with_judge(self, repo):
        timeline = fetch_roster_timeline(date(2026, 6, 4), repo_root=repo)
        result = judge_executed(
            timeline, player_name="Joc Pederson", player_id=1001,
            window_start=date(2026, 6, 4), window_end=date(2026, 6, 7))
        assert result["status"] == "executed"
        assert result["matched_date"] == "2026-06-05"

    def test_non_repo_degrades_to_empty(self, tmp_path):
        assert fetch_roster_timeline(
            date(2026, 6, 4), repo_root=tmp_path / "not-a-repo") == []
