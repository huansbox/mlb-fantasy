"""TDD tests for _backtest_lib — pure functions only.

Production fetchers (Savant / Yahoo / MLB Stats API) are not covered here —
they are system boundaries validated by e2e backtest_track.py runs against
real GitHub Issues.
"""

from datetime import date

import pytest

from _backtest_lib import (
    B2Verdict,
    ResolvedPlayer,
    VerdictOutcome,
    aggregate_hit_rate,
    build_roster_name_index,
    parse_b2_verdict,
    parse_issue_date,
    resolve_player,
)


# ── parse_b2_verdict ──

# Body template mirrors actual _phase6_sp._emit_b2_final format: parts joined
# by "\n\n", so the gap between the === header and the JSON object is a blank
# line (two newlines). Earlier regression: regex required single \n and missed
# every real Issue body silently.
_VALID_BODY_TEMPLATE = """
[SP-v4] B2 verdict: drop_X_add_Y

Pfaadt structurally better.

=== SP-v4 B2 Step A ===

{step_a_json}

=== SP-v4 B2 Step B (final verdict) ===

{step_b_json}
"""


def _body(step_b_obj: dict, step_a_obj: dict | None = None) -> str:
    import json
    sa = step_a_obj or {"my_team_rank": [], "fa_classify": []}
    return _VALID_BODY_TEMPLATE.format(
        step_a_json=json.dumps(sa, ensure_ascii=False),
        step_b_json=json.dumps(step_b_obj, ensure_ascii=False),
    )


def _body_from_emit(step_b_obj: dict, step_a_obj: dict | None = None) -> str:
    """Recreate the exact byte-for-byte format that _emit_b2_final produces.

    Direct mirror of _phase6_sp.py line 442 (`"\\n\\n".join(full_raw_parts)`).
    Regression test against the regex's actual production input shape.
    """
    import json
    sa = step_a_obj or {"my_team_rank": [], "fa_classify": []}
    parts = [
        "=== SP-v4 B2 Step A ===",
        json.dumps(sa, ensure_ascii=False, indent=2, default=str),
        "=== SP-v4 B2 Step B (final verdict) ===",
        json.dumps(step_b_obj, ensure_ascii=False, indent=2, default=str),
    ]
    return "\n\n".join(parts)


class TestParseB2Verdict:
    def test_drop_add_action(self):
        body = _body({"action": "drop_X_add_Y", "drop": "Nola",
                      "add": "Pfaadt", "watch_target": None,
                      "reason": "Sum +18"})
        v = parse_b2_verdict(body, date(2026, 5, 27))
        assert v is not None
        assert v.action == "drop_X_add_Y"
        assert v.drop == "Nola"
        assert v.add == "Pfaadt"
        assert v.watch_target is None
        assert v.reason == "Sum +18"
        assert v.issue_date == date(2026, 5, 27)

    def test_watch_action(self):
        body = _body({"action": "watch", "drop": None, "add": None,
                      "watch_target": "Lambert", "reason": "trending"})
        v = parse_b2_verdict(body, date(2026, 5, 27))
        assert v is not None
        assert v.action == "watch"
        assert v.watch_target == "Lambert"
        assert v.drop is None

    def test_pass_action(self):
        body = _body({"action": "pass", "drop": None, "add": None,
                      "watch_target": None, "reason": "no upgrade"})
        v = parse_b2_verdict(body, date(2026, 5, 27))
        assert v is not None
        assert v.action == "pass"

    def test_empty_body_returns_none(self):
        assert parse_b2_verdict("", date(2026, 5, 27)) is None
        assert parse_b2_verdict(None, date(2026, 5, 27)) is None

    def test_body_without_step_b_block_returns_none(self):
        body = "[SP-v4] B2 verdict: pass\nNo step block here."
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_invalid_action_returns_none(self):
        body = _body({"action": "weird_action", "drop": None, "add": None,
                      "watch_target": None, "reason": ""})
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_malformed_json_returns_none(self):
        body = """
=== SP-v4 B2 Step B (final verdict) ===
{not valid json,
"""
        assert parse_b2_verdict(body, date(2026, 5, 27)) is None

    def test_b1_pre_cutover_issue_returns_none(self):
        # B1 issues used Phase 6 multi-agent format, not Step B
        b1_body = "[FA Scan SP-v4] drop Nola add Pfaadt — Phase 6 multi-agent"
        assert parse_b2_verdict(b1_body, date(2026, 5, 20)) is None

    def test_matches_actual_emit_format_with_double_newline(self):
        """Regression: _emit_b2_final joins parts with '\\n\\n'. Earlier
        regex required single '\\n' after === header and silently dropped
        every real production Issue body."""
        body = _body_from_emit({
            "action": "drop_X_add_Y", "drop": "Nola",
            "add": "Pfaadt", "watch_target": None,
            "reason": "Sum +18",
        })
        v = parse_b2_verdict(body, date(2026, 5, 27))
        assert v is not None
        assert v.action == "drop_X_add_Y"
        assert v.drop == "Nola"
        assert v.add == "Pfaadt"


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


# ── Integration: collect_verdicts on crafted B2 fixture ──

class TestCollectVerdictsIntegration:
    """Exercises the end-to-end issue body → verdict list pipeline on hand-
    crafted B2-format fixtures (no real B2 issues exist pre-cutover)."""

    def test_collect_from_mixed_issue_list(self):
        from backtest_track import collect_verdicts

        issues = [
            {
                "createdAt": "2026-05-27T12:00:00Z",
                "body": _body({
                    "action": "drop_X_add_Y", "drop": "Nola",
                    "add": "Pfaadt", "watch_target": None,
                    "reason": "5-slot edge",
                }),
            },
            {
                "createdAt": "2026-05-28T12:00:00Z",
                "body": _body({
                    "action": "watch", "drop": None, "add": None,
                    "watch_target": "Lambert", "reason": "trending",
                }),
            },
            {
                # B1-format — should be silently skipped
                "createdAt": "2026-05-20T12:00:00Z",
                "body": "[FA Scan SP-v4] B1 multi-agent verdict",
            },
            {
                # Missing body — skipped without crash
                "createdAt": "2026-05-29T12:00:00Z",
                "body": "",
            },
        ]

        verdicts = collect_verdicts(issues)
        assert len(verdicts) == 2
        assert verdicts[0].action == "drop_X_add_Y"
        assert verdicts[0].drop == "Nola"
        assert verdicts[1].action == "watch"
        assert verdicts[1].watch_target == "Lambert"

    def test_classify_outcome_drop_add_hit(self):
        from backtest_track import classify_outcome

        v = _v("drop_X_add_Y")
        # post_drop xwOBACON .395 (worse), post_add .360 (better) → hit
        outcome = classify_outcome(v, post_drop=0.395, post_add=0.360)
        assert outcome.outcome_label == "hit"
        assert outcome.marginal_benefit == pytest.approx(0.035)

    def test_classify_outcome_drop_add_miss(self):
        from backtest_track import classify_outcome

        v = _v("drop_X_add_Y")
        # post_drop .345 (better), post_add .400 (worse) → miss
        outcome = classify_outcome(v, post_drop=0.345, post_add=0.400)
        assert outcome.outcome_label == "miss"
        assert outcome.marginal_benefit == pytest.approx(-0.055)

    def test_classify_outcome_pass_neutral(self):
        from backtest_track import classify_outcome

        v = _v("pass")
        outcome = classify_outcome(v, post_drop=None, post_add=None)
        assert outcome.outcome_label == "neutral"

    def test_classify_outcome_missing_data_neutral(self):
        from backtest_track import classify_outcome

        v = _v("drop_X_add_Y")
        outcome = classify_outcome(v, post_drop=None, post_add=0.345)
        assert outcome.outcome_label == "neutral"

    def test_format_weekly_section_includes_essentials(self):
        from backtest_track import format_weekly_section

        stats = {
            "window_days": 7,
            "observation_window_days": 21,
            "date_range": ["2026-05-27", "2026-05-29"],
            "n_total": 2,
            "n_actionable": 1,
            "n_hits": 1,
            "hit_rate": 1.0,
            "avg_marginal_benefit": 0.035,
            "by_action": {
                "drop_X_add_Y": {"n": 1, "n_actionable": 1, "hit_rate": 1.0},
                "watch": {"n": 1, "n_actionable": 0, "hit_rate": None},
                "pass": {"n": 0, "n_actionable": 0, "hit_rate": None},
            },
            "verdicts": [],
        }
        md = format_weekly_section(stats)
        assert "Weekly Backtest" in md
        assert "Hit rate" in md
        assert "drop_X_add_Y" in md
        assert "marginal benefit" in md
