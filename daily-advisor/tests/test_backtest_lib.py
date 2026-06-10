"""TDD tests for _backtest_lib — pure functions only.

Production fetchers (Savant / gh / MLB Stats API) are not covered here —
they are injected boundaries (see test_backtest_track.py for pipeline tests).

FIXTURE IRON RULE (PRD Testing Decisions, issue 027): all parse tests run
against REAL production issue bodies archived via
`gh issue view <N> -R huansbox/mlb-fantasy --json number,title,createdAt,body`
into tests/fixtures/issue_<N>_sp_v4.json. Hand-written template samples are
forbidden as primary fixtures — the original `_STEP_B_BLOCK_RE` passed 33
hand-written tests while matching ZERO production bodies (code fence +
</details> wrapper; "tests green, production dead", found 2026-06-10).
Synthetic bodies below are demoted to boundary cases only and are explicitly
marked as NOT representative of production format.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from _backtest_lib import (
    B2Verdict,
    Episode,
    ResolvedPlayer,
    VerdictOutcome,
    aggregate_hit_rate,
    build_roster_name_index,
    dedupe_episodes,
    parse_b2_verdict,
    parse_issue_date,
    resolve_player,
    select_due_episodes,
    verdict_episode_key,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(number: int):
    """Load a real production issue fixture → (body, issue_date)."""
    raw = (FIXTURE_DIR / f"issue_{number}_sp_v4.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    return data["body"], parse_issue_date(data["createdAt"])


# ── parse_b2_verdict — REAL production fixtures (primary suite) ──

class TestParseB2VerdictProductionFixtures:
    """Each fixture is a verbatim `gh issue view --json body` archive and
    covers one Step B action. The wrapper-chrome assertions lock in the
    premise that production bodies are fenced + folded — if a future format
    change un-wraps them, these tests will still pass (parser is anchored
    on the header only) but the premise assertions document today's shape."""

    def test_fixture_bodies_really_are_fence_wrapped(self):
        # Regression premise: Step B JSON sits inside ``` fence + <details>.
        for number in (259, 276, 280, 305):
            body, _ = _load_fixture(number)
            assert "</details>" in body, f"#{number} lost <details> wrapper?"
            assert "```" in body, f"#{number} lost code fence?"
            assert "=== SP-v4 B2 Step B (final verdict) ===" in body

    def test_issue_259_drop_add(self):
        body, d = _load_fixture(259)
        v = parse_b2_verdict(body, d)
        assert v is not None
        assert v.action == "drop_X_add_Y"
        assert v.drop == "Coleman Crow"
        assert v.add == "Trevor McDonald"
        assert v.watch_target is None
        assert v.issue_date == date(2026, 5, 29)
        assert "McDonald" in v.reason

    def test_issue_276_pass(self):
        body, d = _load_fixture(276)
        v = parse_b2_verdict(body, d)
        assert v is not None
        assert v.action == "pass"
        assert v.drop is None
        assert v.add is None
        assert v.watch_target is None
        assert v.issue_date == date(2026, 6, 2)

    def test_issue_280_watch(self):
        body, d = _load_fixture(280)
        v = parse_b2_verdict(body, d)
        assert v is not None
        assert v.action == "watch"
        assert v.watch_target == "Zebby Matthews"
        assert v.drop is None
        assert v.issue_date == date(2026, 6, 3)

    def test_issue_305_watch(self):
        # The exact body the 2026-06-10 shell-finding was reproduced against.
        body, d = _load_fixture(305)
        v = parse_b2_verdict(body, d)
        assert v is not None
        assert v.action == "watch"
        assert v.watch_target == "Shane Drohan"
        assert v.issue_date == date(2026, 6, 10)

    def test_issue_254_no_step_b_block_returns_none(self):
        # Real SP-v4 issue from B2-deploy morning (2026-05-28 04:34) that
        # predates the Step B raw dump — must be silently skipped.
        body, d = _load_fixture(254)
        assert "Step B (final verdict)" not in body
        assert parse_b2_verdict(body, d) is None


# ── parse_b2_verdict — synthetic boundary cases (NOT production format) ──

class TestParseB2VerdictSyntheticBoundaries:
    """Hand-written bodies for malformed-input boundaries that cannot be
    sourced from the archive. None of these represent production format —
    production-format coverage lives in the fixture class above."""

    def test_empty_body_returns_none(self):
        assert parse_b2_verdict("", date(2026, 5, 27)) is None
        assert parse_b2_verdict(None, date(2026, 5, 27)) is None

    def test_body_without_step_b_block_returns_none(self):
        body = "[SP-v4] B2 verdict: pass\nNo step block here."
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_invalid_action_returns_none(self):
        body = ('=== SP-v4 B2 Step B (final verdict) ===\n\n'
                '{"action": "weird_action", "drop": null, "add": null,'
                ' "watch_target": null, "reason": ""}')
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_malformed_json_returns_none(self):
        body = """
=== SP-v4 B2 Step B (final verdict) ===
{not valid json,
"""
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_truncated_json_returns_none(self):
        # Object never closes — brace scanner must not hang or crash.
        body = ('=== SP-v4 B2 Step B (final verdict) ===\n\n'
                '{"action": "watch", "reason": "truncated')
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_b1_pre_cutover_issue_returns_none(self):
        b1_body = "[FA Scan SP-v4] drop Nola add Pfaadt — Phase 6 multi-agent"
        assert parse_b2_verdict(b1_body, date(2026, 5, 20)) is None

    def test_bare_emit_format_still_supported(self):
        """Backward compat: the raw '\\n\\n'.join() shape _emit_b2_final
        produces BEFORE markdown wrapping (header + JSON, no fence)."""
        step_b = {"action": "drop_X_add_Y", "drop": "Nola", "add": "Pfaadt",
                  "watch_target": None, "reason": "Sum +18"}
        parts = [
            "=== SP-v4 B2 Step A ===",
            json.dumps({"my_team_rank": [], "fa_classify": []}, indent=2),
            "=== SP-v4 B2 Step B (final verdict) ===",
            json.dumps(step_b, indent=2),
        ]
        v = parse_b2_verdict("\n\n".join(parts), date(2026, 5, 27))
        assert v is not None
        assert v.action == "drop_X_add_Y"
        assert v.drop == "Nola"
        assert v.add == "Pfaadt"

    def test_braces_inside_reason_string_do_not_break_extraction(self):
        step_b = {"action": "watch", "drop": None, "add": None,
                  "watch_target": "X",
                  "reason": 'tricky {braces} and "quote \\" escapes" inside'}
        body = ("=== SP-v4 B2 Step B (final verdict) ===\n\n"
                + json.dumps(step_b) + "\n```\n\n</details>\n")
        v = parse_b2_verdict(body, date(2026, 5, 27))
        assert v is not None
        assert v.watch_target == "X"


# ── parse_issue_date ──

class TestParseIssueDate:
    def test_iso_with_z_timezone(self):
        assert parse_issue_date("2026-05-27T12:34:56Z") == date(2026, 5, 27)

    def test_iso_with_offset(self):
        assert parse_issue_date("2026-05-27T12:34:56+00:00") == date(2026, 5, 27)

    def test_invalid_returns_today(self):
        # We tolerate invalid timestamps (rare GitHub edge cases); caller decides
        result = parse_issue_date("garbage")
        assert isinstance(result, date)


# ── Player ID resolution ──

@pytest.fixture
def roster_index():
    config = {
        "batters": [
            {"name": "Jazz Chisholm Jr.", "mlb_id": 665862},
            {"name": "Manny Machado", "mlb_id": 592518},
        ],
        "pitchers": [
            {"name": "Tarik Skubal", "mlb_id": 669373},
            {"name": "Aaron Nola", "mlb_id": 605400},
            {"name": "Jesús Luzardo", "mlb_id": 666158},
        ],
    }
    return build_roster_name_index(config)


class TestBuildRosterNameIndex:
    def test_combines_batters_and_pitchers(self, roster_index):
        assert "tarik skubal" in roster_index
        assert "jazz chisholm jr." in roster_index
        assert len(roster_index) == 5

    def test_normalizes_accents(self, roster_index):
        # José Luzardo entry uses accented form; lookup via stripped form works
        assert "jesus luzardo" in roster_index

    def test_handles_missing_sections(self):
        index = build_roster_name_index({})
        assert index == {}

    def test_handles_missing_name_or_mlb_id(self):
        config = {
            "pitchers": [
                {"mlb_id": 1},  # no name
                {"name": "Anon"},  # no mlb_id
                {"name": "Valid", "mlb_id": 100},
            ],
        }
        index = build_roster_name_index(config)
        assert index == {"valid": 100}


class TestResolvePlayer:
    def test_hand_tag_wins(self, roster_index):
        result = resolve_player("Nola", roster_index, hand_tags={"nola": 999})
        assert result.mlb_id == 999
        assert result.source == "hand_tag"

    def test_roster_lookup(self, roster_index):
        result = resolve_player("Aaron Nola", roster_index)
        assert result.mlb_id == 605400
        assert result.source == "roster_config"

    def test_case_insensitive(self, roster_index):
        result = resolve_player("AARON NOLA", roster_index)
        assert result.mlb_id == 605400

    def test_accent_normalized(self, roster_index):
        # Verdict text may lack accent; index normalized form matches
        result = resolve_player("Jesus Luzardo", roster_index)
        assert result.mlb_id == 666158

    def test_unknown_returns_unresolved(self, roster_index):
        result = resolve_player("Phantom Player", roster_index)
        assert result.mlb_id is None
        assert result.source == "unresolved"

    def test_empty_name(self, roster_index):
        result = resolve_player("", roster_index)
        assert result.mlb_id is None
        assert result.source == "unresolved"


# ── Episode dedup ──

def _verdict_on(d: date, action: str = "drop_X_add_Y",
                drop: str | None = "Crow", add: str | None = "McDonald",
                watch: str | None = None) -> B2Verdict:
    if action != "drop_X_add_Y":
        drop = add = None
    return B2Verdict(issue_date=d, action=action, drop=drop, add=add,
                     watch_target=watch, reason="r")


class TestDedupeEpisodes:
    KW = dict(key_fn=verdict_episode_key, date_fn=lambda v: v.issue_date)

    def test_consecutive_days_merge_into_one_episode(self):
        vs = [_verdict_on(date(2026, 5, 29)),
              _verdict_on(date(2026, 5, 30)),
              _verdict_on(date(2026, 5, 31))]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 1
        assert eps[0].start_date == date(2026, 5, 29)
        assert eps[0].end_date == date(2026, 5, 31)
        assert len(eps[0].occurrences) == 3
        assert eps[0].first is vs[0]

    def test_gap_of_two_days_still_merges(self):
        # Scan missed one day: 5/29 then 5/31 (gap 2) → same episode
        vs = [_verdict_on(date(2026, 5, 29)), _verdict_on(date(2026, 5, 31))]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 1
        assert eps[0].start_date == date(2026, 5, 29)

    def test_gap_of_three_days_breaks_episode(self):
        vs = [_verdict_on(date(2026, 5, 29)), _verdict_on(date(2026, 6, 1))]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 2
        assert eps[0].start_date == date(2026, 5, 29)
        assert eps[1].start_date == date(2026, 6, 1)

    def test_different_combinations_never_merge(self):
        vs = [_verdict_on(date(2026, 5, 29), add="McDonald"),
              _verdict_on(date(2026, 5, 30), add="Pfaadt")]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 2

    def test_same_day_duplicates_merge(self):
        # Real case: two SP-v4 issues on 2026-05-28 (#254 + #255)
        vs = [_verdict_on(date(2026, 5, 28)), _verdict_on(date(2026, 5, 28))]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 1
        assert len(eps[0].occurrences) == 2

    def test_unsorted_input_is_sorted_by_date(self):
        vs = [_verdict_on(date(2026, 5, 31)), _verdict_on(date(2026, 5, 29)),
              _verdict_on(date(2026, 5, 30))]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 1
        assert eps[0].first.issue_date == date(2026, 5, 29)

    def test_watch_and_drop_add_have_distinct_keys(self):
        vs = [_verdict_on(date(2026, 5, 29)),
              _verdict_on(date(2026, 5, 29), action="watch", watch="Drohan")]
        eps = dedupe_episodes(vs, **self.KW)
        assert len(eps) == 2

    def test_generic_key_and_date_fns(self):
        # Batter side (issue 029) will pass plain dicts — must work unchanged.
        items = [
            {"d": date(2026, 6, 1), "k": ("replace", "A", "B")},
            {"d": date(2026, 6, 2), "k": ("replace", "A", "B")},
        ]
        eps = dedupe_episodes(items, key_fn=lambda i: i["k"],
                              date_fn=lambda i: i["d"])
        assert len(eps) == 1
        assert eps[0].key == ("replace", "A", "B")


class TestSelectDueEpisodes:
    @staticmethod
    def _ep(start: date) -> Episode:
        v = _verdict_on(start)
        return Episode(key=verdict_episode_key(v), start_date=start,
                       end_date=start, occurrences=(v,))

    def test_age_window_boundaries(self):
        today = date(2026, 6, 28)
        eps = [self._ep(date(2026, 6, 8)),   # age 20 → too young
               self._ep(date(2026, 6, 7)),   # age 21 → due
               self._ep(date(2026, 6, 1)),   # age 27 → due
               self._ep(date(2026, 5, 31))]  # age 28 → already reconciled
        due = select_due_episodes(eps, on_date=today)
        # input order preserved (pipeline feeds pre-sorted episodes)
        assert {e.start_date for e in due} == {date(2026, 6, 1), date(2026, 6, 7)}

    def test_weekly_stride_covers_each_episode_exactly_once(self):
        # Two Sunday runs 7 days apart: every episode start lands in
        # exactly one [21, 28) window.
        run1, run2 = date(2026, 6, 28), date(2026, 7, 5)
        eps = [self._ep(date(2026, 6, 1) + timedelta(days=i))
               for i in range(14)]
        due1 = {e.start_date for e in select_due_episodes(eps, on_date=run1)}
        due2 = {e.start_date for e in select_due_episodes(eps, on_date=run2)}
        assert due1.isdisjoint(due2)
        assert len(due1) == 7 and len(due2) == 7

    def test_override_age_min_zero_for_demo(self):
        today = date(2026, 6, 10)
        eps = [self._ep(date(2026, 6, 10)), self._ep(date(2026, 5, 29))]
        due = select_due_episodes(eps, on_date=today, age_min=0)
        assert len(due) == 2


# ── Hit-rate aggregation ──

def _v(action: str, name: str = "X") -> B2Verdict:
    return B2Verdict(
        issue_date=date(2026, 5, 27),
        action=action,
        drop=name if action == "drop_X_add_Y" else None,
        add="FA" if action == "drop_X_add_Y" else None,
        watch_target="W" if action == "watch" else None,
        reason="",
    )


class TestAggregateHitRate:
    def test_empty_outcomes(self):
        stats = aggregate_hit_rate([])
        assert stats["n_total"] == 0
        assert stats["n_actionable"] == 0
        assert stats["hit_rate"] is None

    def test_all_hits(self):
        outcomes = [
            VerdictOutcome(_v("drop_X_add_Y"), "hit", 0.5),
            VerdictOutcome(_v("watch"), "hit", 0.3),
        ]
        stats = aggregate_hit_rate(outcomes)
        assert stats["hit_rate"] == 1.0
        assert stats["n_hits"] == 2

    def test_mixed_with_neutrals(self):
        outcomes = [
            VerdictOutcome(_v("drop_X_add_Y"), "hit", 0.4),
            VerdictOutcome(_v("drop_X_add_Y"), "miss", -0.2),
            VerdictOutcome(_v("pass"), "neutral", None),
        ]
        stats = aggregate_hit_rate(outcomes)
        # neutral excluded from rate denominator
        assert stats["n_actionable"] == 2
        assert stats["hit_rate"] == 0.5

    def test_marginal_benefit_average(self):
        outcomes = [
            VerdictOutcome(_v("drop_X_add_Y"), "hit", 0.4),
            VerdictOutcome(_v("drop_X_add_Y"), "miss", -0.2),
        ]
        stats = aggregate_hit_rate(outcomes)
        assert stats["avg_marginal_benefit"] == pytest.approx(0.1)

    def test_by_action_breakdown(self):
        outcomes = [
            VerdictOutcome(_v("drop_X_add_Y"), "hit", 0.4),
            VerdictOutcome(_v("drop_X_add_Y"), "hit", 0.5),
            VerdictOutcome(_v("watch"), "miss", None),
            VerdictOutcome(_v("pass"), "neutral", None),
        ]
        stats = aggregate_hit_rate(outcomes)
        assert stats["by_action"]["drop_X_add_Y"]["hit_rate"] == 1.0
        assert stats["by_action"]["watch"]["hit_rate"] == 0.0
        assert stats["by_action"]["pass"]["hit_rate"] is None
        assert stats["by_action"]["pass"]["n_actionable"] == 0
