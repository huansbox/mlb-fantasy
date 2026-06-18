"""Unit tests for issue 039 / 318b (B1b) — LLM payload injection of the ledger
note (prev-verdict + add-reason + star) under a per-candidate line budget.

The note answers "what did we last decide, and why did we pick him" so a drop
suggestion confronts the original add reason instead of one bad day.
``_inject_318b_lines`` is the single injection point later slices
(platoon/PA/swap/micro) register their pools into; the ``_fmt_*_batter_v4``
blocks call it before returning. Pure given a CandidateEnrichment — no Yahoo /
ledger IO.
"""

from fa_scan import (
    _fmt_anchor_block_batter_v4,
    _fmt_fa_block_batter_v4,
    _inject_318b_lines,
)
from ledger_enrich import CandidateEnrichment


def _fa_entry(**ov):
    e = {
        "name": "Test FA", "mlb_id": 123456, "team": "HOU", "pct": 12,
        "status": "",
        "savant_2026": {"xwoba": 0.320, "bb_pct": 8.0, "barrel_pct": 9.0,
                        "hh_pct": 42.0, "bbe": 60},
        "prior_stats": {"xwoba": 0.310, "bb_pct": 7.5, "barrel_pct": 8.0,
                        "pa": 520},
        "derived": {"pa_per_tg": 3.8}, "rolling_14d": {},
        "add_tags": [], "warn_tags": [],
    }
    e.update(ov)
    return e


def _anchor_entry(**ov):
    e = {
        "name": "My Guy", "mlb_id": 654321, "team": "NYY",
        "savant_2026": {"xwoba": 0.300, "bb_pct": 7.0, "barrel_pct": 7.0,
                        "hh_pct": 40.0, "bbe": 80},
        "prior_stats": {"xwoba": 0.305, "bb_pct": 7.2, "barrel_pct": 7.5,
                        "pa": 600},
        "derived": {"pa_per_tg": 3.5}, "rolling_14d": {},
        "mlb_2026": {"plateAppearances": 250},
    }
    e.update(ov)
    return e


# ── _inject_318b_lines (pure) ──

def test_inject_none_enrichment_empty():
    assert _inject_318b_lines("X", None, "   ") == []


def test_inject_empty_notes_empty():
    # enrichment present but no notes (enrich produced nothing) → no lines
    assert _inject_318b_lines("X", CandidateEnrichment(stars=3), "   ") == []


def test_inject_renders_notes_with_indent():
    enr = CandidateEnrichment(stars=4, note_lines=[
        "[記事] 前判「取代」5天前 ★★★★", "[原撿因] xwOBA .349/BB% 12"])
    out = _inject_318b_lines("X", enr, "   ")
    assert out == ["   [記事] 前判「取代」5天前 ★★★★",
                   "   [原撿因] xwOBA .349/BB% 12"]


def test_inject_day0_single_line_respects_other_indent():
    enr = CandidateEnrichment(stars=4, note_lines=["[記事] 新候選 ★★★★"])
    assert _inject_318b_lines("X", enr, "  ") == ["  [記事] 新候選 ★★★★"]


def test_inject_within_three_line_budget_does_not_drop():
    # ledger alone is ≤2 lines — comfortably under the ≤3 per-candidate ceiling.
    enr = CandidateEnrichment(stars=5, note_lines=["a", "b"])
    out = _inject_318b_lines("X", enr, "")
    assert out == ["a", "b"]


# ── _fmt_fa_block_batter_v4 wiring (FA + watch) ──

def test_fa_block_appends_note_when_enrichment_given():
    enr = CandidateEnrichment(stars=4,
                              note_lines=["[記事] 前判「取代」5天前 ★★★★"])
    lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None,
                                    age=28, enrichment=enr)
    assert any("[記事] 前判「取代」" in l for l in lines)
    # injected after the existing prior line — note is the block's tail
    assert "[記事]" in lines[-1]


def test_fa_block_default_no_enrichment_unchanged():
    # backward-compatible: omitting enrichment renders exactly as before.
    plain = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None, age=28)
    explicit = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None,
                                       age=28, enrichment=None)
    assert plain == explicit
    assert not any("[記事]" in l for l in plain)


# ── _fmt_anchor_block_batter_v4 wiring (my-team drop pool) ──

def test_anchor_block_appends_note():
    enr = CandidateEnrichment(stars=3,
                              note_lines=["[記事] 前判「觀察」3天前 ★★★"])
    lines = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None,
                                        enrichment=enr)
    assert any("[記事] 前判「觀察」" in l for l in lines)


def test_anchor_block_default_unchanged():
    plain = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None)
    explicit = _fmt_anchor_block_batter_v4(_anchor_entry(), "P1", None,
                                           enrichment=None)
    assert plain == explicit
    assert not any("[記事]" in l for l in plain)


# ── B5 / 318b: post-hype inline tag ──

import datetime as _dt

from fa_scan import _compute_inline_tags


def _ped(mlb_id=123456, rank=5, year=2024, updated="2026-03-01"):
    from prospect_pedigree import parse_pedigree
    return parse_pedigree({
        "meta": {"updated": updated, "stale_after_month": 3},
        "prospects": {str(mlb_id): {"best_rank": rank, "best_rank_year": year,
                                    "name": "Test FA"}},
    })


def test_inline_tags_post_hype_fires_young_weak_pedigreed():
    # top-5 prospect, age 23, weak season Sum → discount tag fires
    entry = _fa_entry(mlb_id=123456, score=12)
    tags = _compute_inline_tags(entry, age=23, ped=_ped(),
                                today=_dt.date(2026, 6, 18))
    assert any("post-hype 新秀" in t and "#5" in t for t in tags)


def test_inline_tags_not_young_no_fire():
    entry = _fa_entry(mlb_id=123456, score=12)
    tags = _compute_inline_tags(entry, age=30, ped=_ped(),
                                today=_dt.date(2026, 6, 18))
    assert not any("post-hype" in t for t in tags)


def test_inline_tags_strong_sum_no_fire():
    # good Sum = results not weak → no discount needed
    entry = _fa_entry(mlb_id=123456, score=26)
    tags = _compute_inline_tags(entry, age=23, ped=_ped(),
                                today=_dt.date(2026, 6, 18))
    assert not any("post-hype" in t for t in tags)


def test_inline_tags_stale_list_marks_overdue():
    # list 2 years behind → stale wording, never silently trusted
    entry = _fa_entry(mlb_id=123456, score=12)
    tags = _compute_inline_tags(entry, age=23, ped=_ped(updated="2024-03-01"),
                                today=_dt.date(2026, 6, 18))
    assert any("post-hype 名單過期" in t for t in tags)


def test_inline_tags_no_ped_empty():
    assert _compute_inline_tags(_fa_entry(), 23, None,
                                _dt.date(2026, 6, 18)) == []


def test_fa_block_header_shows_inline_tags():
    enr = CandidateEnrichment(stars=3,
                              inline_tags=["✅ post-hype 新秀 (#5 2024)"])
    lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None,
                                    age=23, enrichment=enr)
    assert "post-hype 新秀" in lines[0]  # appears in the header line


def test_fa_block_header_no_inline_tags_when_absent():
    lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None, age=23)
    assert "post-hype" not in lines[0]


# ── B5 / 318b: chase / zone-contact YoY discipline inline tag ──

def test_inline_tags_chase_zone_improvement_fires():
    # chase -6.0 (sig) + zone-contact +5.0 (sig) → discipline-improving tag
    entry = _fa_entry(mlb_id=123456, score=26)  # strong Sum → no post-hype
    cur = {"chase": 24.0, "zone_contact": 88.0, "pa": 300}
    prior = {"chase": 30.0, "zone_contact": 83.0, "pa": 400}
    tags = _compute_inline_tags(entry, age=28, ped=None,
                                today=_dt.date(2026, 6, 18),
                                disc_cur=cur, disc_prior=prior)
    assert any("選球進化" in t and "chase -6.0" in t for t in tags)


def test_inline_tags_discipline_absent_without_data():
    entry = _fa_entry(mlb_id=123456, score=26)
    tags = _compute_inline_tags(entry, 28, None, _dt.date(2026, 6, 18))
    assert not any("選球" in t or "擊球接觸" in t for t in tags)


def test_inline_tags_thin_current_sample_no_discipline():
    # cur PA below CUR_PA_FLOOR (40) → compute_discipline returns None → no tag
    entry = _fa_entry(mlb_id=123456, score=26)
    cur = {"chase": 24.0, "zone_contact": 88.0, "pa": 20}
    prior = {"chase": 30.0, "zone_contact": 83.0, "pa": 400}
    tags = _compute_inline_tags(entry, 28, None, _dt.date(2026, 6, 18),
                                disc_cur=cur, disc_prior=prior)
    assert not any("選球" in t for t in tags)


def test_inline_tags_combines_post_hype_and_discipline():
    # a young weak post-hype prospect who is ALSO improving discipline → both
    entry = _fa_entry(mlb_id=123456, score=12)
    cur = {"chase": 24.0, "zone_contact": 88.0, "pa": 300}
    prior = {"chase": 30.0, "zone_contact": 83.0, "pa": 400}
    tags = _compute_inline_tags(entry, 23, _ped(), _dt.date(2026, 6, 18),
                                disc_cur=cur, disc_prior=prior)
    assert any("post-hype" in t for t in tags)
    assert any("選球進化" in t for t in tags)


# ── B2 / 318b: platoon-share inline tag ──

def test_inline_tags_strong_side_platoon_warns():
    # the Arraez→Pederson -28% weekly-PA blind spot: a strong-side platoon bat
    # gets the warning so a quality-only swap doesn't silently lose PA.
    entry = _fa_entry(mlb_id=123456, score=26)
    platoon = {"label": "strong_side", "tag": "⚠️ 強側平台 (vs RHP)",
               "start_rate_vs_r": 0.9, "start_rate_vs_l": 0.1,
               "overall_start_rate": 0.55}
    tags = _compute_inline_tags(entry, 28, None, _dt.date(2026, 6, 18),
                                platoon=platoon)
    assert any("強側平台" in t for t in tags)


def test_inline_tags_everyday_platoon_no_warn():
    entry = _fa_entry(mlb_id=123456, score=26)
    platoon = {"label": "everyday", "tag": None, "start_rate_vs_r": 0.95,
               "start_rate_vs_l": 0.92, "overall_start_rate": 0.94}
    tags = _compute_inline_tags(entry, 28, None, _dt.date(2026, 6, 18),
                                platoon=platoon)
    assert not any("平台" in t for t in tags)


def test_inline_tags_no_platoon_no_tag():
    entry = _fa_entry(mlb_id=123456, score=26)
    tags = _compute_inline_tags(entry, 28, None, _dt.date(2026, 6, 18))
    assert not any("平台" in t or "替補" in t for t in tags)


# ── B2 / 318b: team schedule parse (pure; the fetch path is VPS-validated) ──

def test_parse_team_schedule_picks_opponent_starter_by_side():
    from fa_scan import _parse_team_schedule
    sched = {"dates": [{"games": [{
        "gamePk": 1,
        "teams": {
            "home": {"team": {"id": 10}, "probablePitcher": {"id": 100}},
            "away": {"team": {"id": 20}, "probablePitcher": {"id": 200}},
        }}]}]}
    # our team home → opponent is away (starter 200); our team away → starter 100
    assert _parse_team_schedule(sched, 10) == [{"game_pk": 1, "opp_starter_id": 200}]
    assert _parse_team_schedule(sched, 20) == [{"game_pk": 1, "opp_starter_id": 100}]


def test_parse_team_schedule_skips_missing_probable():
    from fa_scan import _parse_team_schedule
    sched = {"dates": [{"games": [{
        "gamePk": 1,
        "teams": {"home": {"team": {"id": 10}}, "away": {"team": {"id": 20}}},
    }]}]}
    assert _parse_team_schedule(sched, 10) == []  # no opponent starter → skip


def test_parse_team_schedule_skips_unrelated_game():
    from fa_scan import _parse_team_schedule
    sched = {"dates": [{"games": [{
        "gamePk": 1,
        "teams": {
            "home": {"team": {"id": 30}, "probablePitcher": {"id": 100}},
            "away": {"team": {"id": 40}, "probablePitcher": {"id": 200}},
        }}]}]}
    assert _parse_team_schedule(sched, 10) == []  # our team not in this game


def test_parse_team_schedule_empty_inputs():
    from fa_scan import _parse_team_schedule
    assert _parse_team_schedule(None, 10) == []
    assert _parse_team_schedule({}, 10) == []
    assert _parse_team_schedule({"dates": []}, 10) == []


# ── B3 / 318b: PA projection line + per-candidate budget eviction ──

def test_inject_evicts_lowest_priority_over_budget():
    # ledger 2 + pa 1 = 3 (full); swap is lowest priority → yields.
    enr = CandidateEnrichment(note_lines=["[記事] a", "[原撿因] b"],
                              pa_line="[下週量] c", swap_line="[換算] d")
    out = _inject_318b_lines("X", enr, "")
    assert out == ["[記事] a", "[原撿因] b", "[下週量] c"]
    assert "[換算] d" not in out  # swap evicted (lowest priority)


def test_inject_keeps_pa_and_swap_when_ledger_one_line():
    # day-0 ledger = 1 line → pa + swap both fit (1+1+1 = 3).
    enr = CandidateEnrichment(note_lines=["[記事] new"],
                              pa_line="[下週量] pa", swap_line="[換算] sw")
    out = _inject_318b_lines("X", enr, "")
    assert out == ["[記事] new", "[下週量] pa", "[換算] sw"]


def test_compute_pa_line_projects_weekly_pa():
    from fa_scan import _compute_pa_line
    future = [{"opp_hand": "R"}] * 4 + [{"opp_hand": "L"}] * 2
    platoon = {"start_rate_vs_r": 0.95, "start_rate_vs_l": 0.92,
               "overall_start_rate": 0.94}
    line = _compute_pa_line(future, platoon)
    assert line.startswith("[下週量]") and "PA" in line and "6 場" in line


def test_compute_pa_line_strong_side_projects_fewer_pa():
    # the volume blind spot, made visible: a strong-side bat facing mostly LHP
    # projects fewer PA than an everyday bat over the same schedule.
    from pa_projection import project_weekly_pa
    future = [{"opp_hand": "L"}] * 5 + [{"opp_hand": "R"}]
    strong = {"start_rate_vs_r": 0.9, "start_rate_vs_l": 0.1,
              "overall_start_rate": 0.5}
    everyday = {"start_rate_vs_r": 0.95, "start_rate_vs_l": 0.92,
                "overall_start_rate": 0.94}
    assert (project_weekly_pa(future, strong, 4.3)["projected_pa"]
            < project_weekly_pa(future, everyday, 4.3)["projected_pa"])


def test_compute_pa_line_none_on_insufficient_input():
    from fa_scan import _compute_pa_line
    assert _compute_pa_line([], {"overall_start_rate": 0.9}) is None
    assert _compute_pa_line([{"opp_hand": "R"}], None) is None
