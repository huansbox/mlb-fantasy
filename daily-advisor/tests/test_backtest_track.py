"""Tests for backtest_track — pipeline with injected system boundaries.

External boundaries (gh CLI, Savant CSV fetch, MLB Stats API search) are
injected; no test touches the network. Parse fixtures follow the same iron
rule as test_backtest_lib.py: real production issue archives only.
"""

import json
from datetime import date
from pathlib import Path

import pytest

import backtest_track
from _backtest_lib import B2Verdict, Episode, verdict_episode_key
from backtest_track import (
    build_episode_outcomes,
    classify_outcome,
    collect_verdicts,
    fetch_post_verdict_xwobacon,
    format_weekly_section,
    run_weekly_summary,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_issue(number: int) -> dict:
    """Real production issue dict, exactly as `gh ... --json` emits it."""
    raw = (FIXTURE_DIR / f"issue_{number}_sp_v4.json").read_text(encoding="utf-8")
    return json.loads(raw)


# ── collect_verdicts on real production fixtures ──

class TestCollectVerdicts:
    def test_collect_from_real_issue_archive(self):
        issues = [_fixture_issue(n) for n in (254, 259, 276, 280, 305)]
        verdicts = collect_verdicts(issues)
        # #254 has no Step B block → skipped; the other 4 parse
        assert len(verdicts) == 4
        by_action = {v.action for v in verdicts}
        assert by_action == {"drop_X_add_Y", "pass", "watch"}
        drop_add = next(v for v in verdicts if v.action == "drop_X_add_Y")
        assert (drop_add.drop, drop_add.add) == ("Coleman Crow", "Trevor McDonald")

    def test_missing_body_skipped_without_crash(self):
        issues = [{"createdAt": "2026-05-29T12:00:00Z", "body": ""},
                  {"createdAt": "2026-05-29T12:00:00Z"}]
        assert collect_verdicts(issues) == []


# ── fetch_post_verdict_xwobacon with injected pitch fetcher ──

def _bbe_row(game_date: str, ab: str, xwoba: str) -> dict:
    return {"game_date": game_date, "at_bat_number": ab, "events": "single",
            "estimated_woba_using_speedangle": xwoba,
            "launch_speed": "92.0", "launch_speed_angle": "3"}


class TestFetchPostVerdictXwobacon:
    def test_window_dates_and_value(self):
        calls = []

        def fake_fetch(mlb_id, start, end, player_type):
            calls.append((mlb_id, start, end, player_type))
            return [_bbe_row("2026-05-30", "1", "0.90"),
                    _bbe_row("2026-05-31", "2", "0.10")]

        val = fetch_post_verdict_xwobacon(
            123, date(2026, 5, 29), window_days=21, fetch_pitches=fake_fetch)
        # half-open [start, start+21) → inclusive Savant end = start + 20
        assert calls == [(123, "2026-05-29", "2026-06-18", "pitcher")]
        assert val == pytest.approx(0.5)  # (0.90 + 0.10) / 2 BBE

    def test_no_data_returns_none(self):
        val = fetch_post_verdict_xwobacon(
            123, date(2026, 5, 29), fetch_pitches=lambda *a: [])
        assert val is None


# ── classify_outcome (unchanged contract) ──

def _v(action: str) -> B2Verdict:
    return B2Verdict(
        issue_date=date(2026, 5, 29), action=action,
        drop="Crow" if action == "drop_X_add_Y" else None,
        add="McDonald" if action == "drop_X_add_Y" else None,
        watch_target="W" if action == "watch" else None, reason="")


class TestClassifyOutcome:
    def test_drop_add_hit(self):
        outcome = classify_outcome(_v("drop_X_add_Y"),
                                   post_drop=0.395, post_add=0.360)
        assert outcome.outcome_label == "hit"
        assert outcome.marginal_benefit == pytest.approx(0.035)

    def test_drop_add_miss(self):
        outcome = classify_outcome(_v("drop_X_add_Y"),
                                   post_drop=0.345, post_add=0.400)
        assert outcome.outcome_label == "miss"
        assert outcome.marginal_benefit == pytest.approx(-0.055)

    def test_pass_neutral(self):
        outcome = classify_outcome(_v("pass"), post_drop=None, post_add=None)
        assert outcome.outcome_label == "neutral"

    def test_missing_data_neutral(self):
        outcome = classify_outcome(_v("drop_X_add_Y"),
                                   post_drop=None, post_add=0.345)
        assert outcome.outcome_label == "neutral"

    def test_watch_hit_below_threshold(self):
        outcome = classify_outcome(_v("watch"), post_drop=None, post_add=0.350)
        assert outcome.outcome_label == "hit"

    def test_watch_miss_above_threshold(self):
        outcome = classify_outcome(_v("watch"), post_drop=None, post_add=0.400)
        assert outcome.outcome_label == "miss"


# ── build_episode_outcomes — observation window anchored on episode start ──

class TestBuildEpisodeOutcomes:
    def _episode(self, *verdicts: B2Verdict) -> Episode:
        return Episode(key=verdict_episode_key(verdicts[0]),
                       start_date=verdicts[0].issue_date,
                       end_date=verdicts[-1].issue_date,
                       occurrences=tuple(verdicts))

    def test_window_anchored_on_episode_start_not_last_occurrence(self):
        v1 = B2Verdict(date(2026, 5, 29), "drop_X_add_Y", "Crow", "McDonald", None, "")
        v2 = B2Verdict(date(2026, 5, 30), "drop_X_add_Y", "Crow", "McDonald", None, "")
        ep = self._episode(v1, v2)
        fetched = []

        def fake_xwobacon(mlb_id, start):
            fetched.append((mlb_id, start))
            return {11: 0.400, 22: 0.350}[mlb_id]

        search = {"Coleman Crow": 11, "Crow": 11,
                  "Trevor McDonald": 22, "McDonald": 22}
        outcomes = build_episode_outcomes(
            [ep], {}, fetch_xwobacon=fake_xwobacon,
            search_fn=lambda name: search.get(name))
        assert fetched == [(11, date(2026, 5, 29)), (22, date(2026, 5, 29))]
        assert outcomes[0].outcome_label == "hit"
        assert outcomes[0].marginal_benefit == pytest.approx(0.05)

    def test_unresolvable_names_classify_neutral(self):
        v = B2Verdict(date(2026, 5, 29), "drop_X_add_Y", "Ghost A", "Ghost B", None, "")
        outcomes = build_episode_outcomes(
            [self._episode(v)], {},
            fetch_xwobacon=lambda *a: pytest.fail("must not fetch without id"),
            search_fn=lambda name: None)
        assert outcomes[0].outcome_label == "neutral"

    def test_roster_index_preferred_over_search(self):
        v = B2Verdict(date(2026, 5, 29), "watch", None, None, "Aaron Nola", "")
        outcomes = build_episode_outcomes(
            [self._episode(v)], {"aaron nola": 605400},
            fetch_xwobacon=lambda mlb_id, start: 0.300 if mlb_id == 605400 else None,
            search_fn=lambda name: pytest.fail("search must not be called"))
        assert outcomes[0].outcome_label == "hit"


# ── run_weekly_summary — full pipeline, all boundaries injected ──

@pytest.fixture
def isolated_roster(tmp_path, monkeypatch):
    """Point backtest_track at a controlled roster_config so tests don't
    depend on the live roster file's current contents."""
    cfg = tmp_path / "roster_config.json"
    cfg.write_text(json.dumps({"batters": [], "pitchers": []}), encoding="utf-8")
    monkeypatch.setattr(backtest_track, "_ROSTER_CONFIG", cfg)
    return cfg


class TestRunWeeklySummary:
    def test_strict_default_window_on_young_archive_yields_zero(self, isolated_roster):
        """2026-06-10 reality: oldest B2 verdict is 13 days old → strict
        [21, 28) window must select nothing and stay graceful."""
        issues = [_fixture_issue(n) for n in (254, 259, 276, 280, 305)]
        stats = run_weekly_summary(
            today=date(2026, 6, 10),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_xwobacon=lambda *a: pytest.fail("nothing due → no fetch"),
            _search_mlb_id=lambda name: pytest.fail("nothing due → no search"),
        )
        assert stats["n_total"] == 0
        assert stats["hit_rate"] is None
        assert stats["age_window"] == [21, 28]
        assert stats["age_window_is_override"] is False
        assert stats["n_episodes_in_lookback"] > 0
        # And the markdown render must not crash on the empty case
        md = format_weekly_section(stats)
        assert "no due episodes" in md

    def test_age_window_selects_only_due_episodes(self, isolated_roster):
        # today = 2026-06-20: #259 (05-29) age 22 → due;
        # #276 (06-02) age 18, #280 (06-03) age 17, #305 (06-10) age 10 → not due
        issues = [_fixture_issue(n) for n in (254, 259, 276, 280, 305)]
        ids = {"Coleman Crow": 11, "Trevor McDonald": 22}
        stats = run_weekly_summary(
            today=date(2026, 6, 20),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_xwobacon=lambda mlb_id, start: {11: 0.40, 22: 0.35}[mlb_id],
            _search_mlb_id=lambda name: ids.get(name),
        )
        assert stats["n_total"] == 1
        assert stats["episodes"][0]["action"] == "drop_X_add_Y"
        assert stats["episodes"][0]["start_date"] == "2026-05-29"
        assert stats["episodes"][0]["outcome"] == "hit"
        assert stats["hit_rate"] == 1.0

    def test_override_age_min_zero_reconciles_everything(self, isolated_roster):
        issues = [_fixture_issue(n) for n in (254, 259, 276, 280, 305)]
        ids = {"Coleman Crow": 11, "Trevor McDonald": 22,
               "Zebby Matthews": 33, "Shane Drohan": 44}
        vals = {11: 0.40, 22: 0.35, 33: 0.360, 44: 0.380}
        stats = run_weekly_summary(
            age_min=0,
            today=date(2026, 6, 10),
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_xwobacon=lambda mlb_id, start: vals.get(mlb_id),
            _search_mlb_id=lambda name: ids.get(name),
        )
        # 4 verdicts → 4 distinct episodes (different keys / actions)
        assert stats["n_total"] == 4
        assert stats["age_window_is_override"] is True
        # drop_add hit + watch(Matthews .360 ≤ .370) hit +
        # watch(Drohan .380 > .370) miss + pass neutral
        assert stats["n_actionable"] == 3
        assert stats["n_hits"] == 2
        md = format_weekly_section(stats)
        assert "OVERRIDE DEMO RUN" in md

    def test_consecutive_duplicate_verdicts_reconcile_once(self, isolated_roster):
        # Same drop/add combo on three adjacent days = one episode, anchored
        # on the first day — the cross-week double-count guard.
        base = _fixture_issue(259)
        issues = []
        for day in ("2026-05-29", "2026-05-30", "2026-05-31"):
            dup = dict(base)
            dup["createdAt"] = f"{day}T04:33:00Z"
            issues.append(dup)
        ids = {"Coleman Crow": 11, "Trevor McDonald": 22}
        starts = []

        def fake_fetch(mlb_id, start):
            starts.append(start)
            return {11: 0.40, 22: 0.35}[mlb_id]

        stats = run_weekly_summary(
            today=date(2026, 6, 21),  # 05-29 age 23 → due
            _fetch_issues=lambda days, repo, label: issues,
            _fetch_xwobacon=fake_fetch,
            _search_mlb_id=lambda name: ids.get(name),
        )
        assert stats["n_total"] == 1
        assert stats["episodes"][0]["n_occurrences"] == 3
        assert set(starts) == {date(2026, 5, 29)}

    def test_days_overrides_fetch_lookback_only(self, isolated_roster):
        seen = {}

        def fake_issues(days, repo, label):
            seen["days"] = days
            return []

        stats = run_weekly_summary(
            days=60, today=date(2026, 6, 10),
            _fetch_issues=fake_issues,
            _fetch_xwobacon=lambda *a: None,
            _search_mlb_id=lambda name: None,
        )
        assert seen["days"] == 60
        assert stats["fetch_lookback_days"] == 60

    def test_default_lookback_covers_age_window_plus_slack(self, isolated_roster):
        seen = {}

        def fake_issues(days, repo, label):
            seen["days"] = days
            return []

        run_weekly_summary(
            today=date(2026, 6, 10),
            _fetch_issues=fake_issues,
            _fetch_xwobacon=lambda *a: None,
            _search_mlb_id=lambda name: None,
        )
        assert seen["days"] == 28 + 14


# ── format_weekly_section ──

class TestFormatWeeklySection:
    def _stats(self, **overrides):
        stats = {
            "age_window": [21, 28],
            "age_window_is_override": False,
            "fetch_lookback_days": 42,
            "observation_window_days": 21,
            "run_date": "2026-06-21",
            "n_episodes_in_lookback": 5,
            "date_range": ["2026-05-29", "2026-05-29"],
            "n_total": 1,
            "n_actionable": 1,
            "n_hits": 1,
            "hit_rate": 1.0,
            "avg_marginal_benefit": 0.05,
            "by_action": {
                "drop_X_add_Y": {"n": 1, "n_actionable": 1, "hit_rate": 1.0},
                "watch": {"n": 0, "n_actionable": 0, "hit_rate": None},
                "pass": {"n": 0, "n_actionable": 0, "hit_rate": None},
            },
            "episodes": [{
                "start_date": "2026-05-29", "end_date": "2026-05-31",
                "n_occurrences": 3, "action": "drop_X_add_Y",
                "drop": "Coleman Crow", "add": "Trevor McDonald",
                "watch_target": None, "outcome": "hit",
                "marginal_benefit": 0.05,
            }],
        }
        stats.update(overrides)
        return stats

    def test_includes_essentials(self):
        md = format_weekly_section(self._stats())
        assert "Weekly Backtest 2026-06-21" in md
        assert "[21, 28)" in md
        assert "Hit rate: 100%" in md
        assert "drop Coleman Crow → add Trevor McDonald" in md
        assert "OVERRIDE" not in md

    def test_override_run_is_marked(self):
        md = format_weekly_section(self._stats(
            age_window=[0, 28], age_window_is_override=True))
        assert "OVERRIDE DEMO RUN" in md
        assert "--age-min 0" in md
