"""TDD tests for rp_svh_scan.py — mechanical layer of the /rp-svh skill."""

from datetime import date, timedelta

import pytest

from rp_svh_scan import (
    WINDOW_14D,
    WINDOW_30D,
    FAEntry,
    Fetchers,
    RosterPitcher,
    SvhProducer,
    _normalize,
    count_team_games,
    filter_fa_candidates,
    parse_svh_leaderboard,
    pick_incumbent,
    rank_avg,
    rank_sum_select,
    recent_svh,
    scan,
)


# ── builders ──

def _leaderboard(*rows):
    """rows: (pid, name, team_id, saves, holds) → byDateRange-shaped json."""
    return {"stats": [{"splits": [
        {
            "player": {"id": pid, "fullName": name},
            "team": {"id": tid, "name": "Some Team"},
            "stat": {"saves": sv, "holds": h},
        }
        for pid, name, tid, sv, h in rows
    ]}]}


def _schedule(*rows):
    """rows: (away_team_id, home_team_id) → schedule-shaped json (one date)."""
    return {"dates": [{"games": [
        {"teams": {
            "away": {"team": {"id": a}},
            "home": {"team": {"id": h}},
        }}
        for a, h in rows
    ]}]}


# ── parse_svh_leaderboard ──

class TestParseSvhLeaderboard:
    def test_parses_player_team_and_svh(self):
        out = parse_svh_leaderboard(_leaderboard(
            (650556, "Bryan Abreu", 117, 1, 0),
        ))
        assert len(out) == 1
        p = out[0]
        assert p.mlb_id == 650556
        assert p.name == "Bryan Abreu"
        assert p.team_id == 117
        assert p.team == "HOU"
        assert p.saves == 1 and p.holds == 0
        assert p.svh == 1

    def test_returns_all_splits_unfiltered(self):
        # parser does not apply the floor — caller does
        out = parse_svh_leaderboard(_leaderboard(
            (1, "A", 135, 3, 2),
            (2, "B", 114, 0, 0),
        ))
        assert len(out) == 2

    def test_split_missing_player_id_skipped(self):
        json_ = {"stats": [{"splits": [
            {"team": {"id": 117}, "stat": {"saves": 1, "holds": 1}},
            {"player": {"id": 5, "fullName": "Real"}, "team": {"id": 117},
             "stat": {"saves": 0, "holds": 3}},
        ]}]}
        out = parse_svh_leaderboard(json_)
        assert [p.mlb_id for p in out] == [5]

    def test_missing_stat_fields_default_zero(self):
        out = parse_svh_leaderboard({"stats": [{"splits": [
            {"player": {"id": 7, "fullName": "X"}, "team": {"id": 117},
             "stat": {}},
        ]}]})
        assert out[0].svh == 0

    def test_empty_json_returns_empty(self):
        assert parse_svh_leaderboard({}) == []


# ── _normalize ──

class TestNormalize:
    @pytest.mark.parametrize("raw,expected", [
        ("Luis García", "luis garcia"),
        ("Riley O'Brien", "riley obrien"),
        ("Riley O’Brien", "riley obrien"),
        ("Jason Adam", "jason adam"),
    ])
    def test_strips_accents_and_apostrophes(self, raw, expected):
        assert _normalize(raw) == expected


# ── filter_fa_candidates ──

class TestFilterFaCandidates:
    def test_keeps_only_fa_producers(self):
        producers = [
            SvhProducer(1, "FA Guy", 135, "SD", 0, 4),
            SvhProducer(2, "Rostered Guy", 114, "CLE", 1, 3),
        ]
        pairs = filter_fa_candidates(producers, [FAEntry("FA Guy", "5%")])
        assert len(pairs) == 1
        assert pairs[0][0].mlb_id == 1
        assert pairs[0][1].percent_owned == "5%"

    def test_accent_mismatch_still_matches(self):
        # Step 1 (MLB) "Luis García" vs Step 2 (Yahoo) "Luis Garcia"
        producers = [SvhProducer(9, "Luis García", 135, "SD", 0, 5)]
        pairs = filter_fa_candidates(producers, [FAEntry("Luis Garcia", "3%")])
        assert len(pairs) == 1
        assert pairs[0][0].mlb_id == 9

    def test_no_fa_returns_empty(self):
        producers = [SvhProducer(1, "Someone", 135, "SD", 0, 4)]
        assert filter_fa_candidates(producers, []) == []


# ── rank_avg ──

class TestRankAvg:
    def test_ascending_smaller_is_rank_one(self):
        assert rank_avg([3.0, 1.0, 2.0], ascending=True) == [3.0, 1.0, 2.0]

    def test_descending_larger_is_rank_one(self):
        assert rank_avg([3.0, 1.0, 2.0], ascending=False) == [1.0, 3.0, 2.0]

    def test_ties_get_average_rank(self):
        # two values tie for ranks 1-2 → both 1.5
        assert rank_avg([1.0, 1.0, 2.0], ascending=True) == [1.5, 1.5, 3.0]

    def test_triple_tie_averages_ranks(self):
        # three tie for ranks 1-2-3 → all 2.0
        assert rank_avg([5.0, 5.0, 5.0], ascending=True) == [2.0, 2.0, 2.0]

    def test_none_values_rank_worst(self):
        assert rank_avg([1.0, None, 2.0], ascending=True) == [1.0, 3.0, 2.0]

    def test_multiple_none_share_worst_average(self):
        # two None share ranks 2-3 → both 2.5
        assert rank_avg([1.0, None, None], ascending=True) == [1.0, 2.5, 2.5]

    def test_empty_list(self):
        assert rank_avg([], ascending=True) == []


# ── rank_sum_select ──

def _cand(name, bb9, whiff, svh30):
    return {"name": name, "bb9": bb9, "whiff_pct": whiff, "svh_30d": svh30}


class TestRankSumSelect:
    def test_computes_axes_and_rank_sum(self):
        cands = [
            _cand("Best", 1.0, 30.0, 10),
            _cand("Mid", 2.0, 28.0, 8),
            _cand("Worst", 3.0, 26.0, 6),
        ]
        ranked, top = rank_sum_select(cands, n=3)
        best = next(c for c in ranked if c["name"] == "Best")
        assert best["axes"]["bb9"]["rank"] == 1.0
        assert best["axes"]["whiff_pct"]["rank"] == 1.0
        assert best["axes"]["svh_30d"]["rank"] == 1.0
        assert best["rank_sum"] == 3.0
        assert best["rank_sum_place"] == 1

    def test_top_n_returns_best_by_rank_sum(self):
        cands = [
            _cand("A", 1.0, 30.0, 10),  # sum 3
            _cand("B", 2.0, 28.0, 8),   # sum 6
            _cand("C", 3.0, 26.0, 6),   # sum 9
            _cand("D", 4.0, 24.0, 4),   # sum 12
        ]
        _, top = rank_sum_select(cands, n=2)
        assert [c["name"] for c in top] == ["A", "B"]

    def test_ties_at_cutoff_all_included(self):
        # B and C identical → tie at rank-sum cutoff; n=2 returns 3
        cands = [
            _cand("A", 1.0, 40.0, 20),
            _cand("B", 2.0, 30.0, 10),
            _cand("C", 2.0, 30.0, 10),
        ]
        _, top = rank_sum_select(cands, n=2)
        assert {c["name"] for c in top} == {"A", "B", "C"}

    def test_fewer_candidates_than_n_returns_all(self):
        cands = [_cand("A", 1.0, 30.0, 10), _cand("B", 2.0, 28.0, 8)]
        _, top = rank_sum_select(cands, n=4)
        assert len(top) == 2

    def test_ranked_is_sorted_by_rank_sum(self):
        cands = [
            _cand("C", 3.0, 26.0, 6),
            _cand("A", 1.0, 30.0, 10),
            _cand("B", 2.0, 28.0, 8),
        ]
        ranked, _ = rank_sum_select(cands, n=3)
        assert [c["name"] for c in ranked] == ["A", "B", "C"]


# ── pick_incumbent ──

class TestPickIncumbent:
    def test_rp_with_highest_svh_is_incumbent(self):
        roster = [
            RosterPitcher(104, "Kevin Kelly", ("RP",)),
            RosterPitcher(200, "Other RP", ("RP",)),
            RosterPitcher(669373, "Tarik Skubal", ("SP",)),
        ]
        season = {
            104: {"saves": 1, "holds": 4},
            200: {"saves": 0, "holds": 2},
            669373: {"saves": 0, "holds": 0},
        }
        inc = pick_incumbent(roster, season)
        assert inc.mlb_id == 104

    def test_no_rp_eligible_returns_none(self):
        roster = [RosterPitcher(669373, "Tarik Skubal", ("SP",))]
        assert pick_incumbent(roster, {669373: {"saves": 0, "holds": 0}}) is None

    def test_rp_with_zero_svh_returns_none(self):
        # all RP have 0 SV+H → case B (no incumbent)
        roster = [RosterPitcher(300, "Setup Nobody", ("RP",))]
        assert pick_incumbent(roster, {300: {"saves": 0, "holds": 0}}) is None

    def test_dual_eligible_sp_rp_counts_as_rp(self):
        roster = [RosterPitcher(301, "Swingman", ("SP", "RP"))]
        inc = pick_incumbent(roster, {301: {"saves": 0, "holds": 3}})
        assert inc.mlb_id == 301


# ── recent_svh ──

class TestRecentSvh:
    def test_sums_last_ten_games(self):
        logs = [{"saves": 1, "holds": 0}] * 12  # 12 games
        out = recent_svh(logs, limit=10)
        assert out["games"] == 10
        assert out["sv"] == 10 and out["h"] == 0
        assert out["svh"] == 10

    def test_fewer_than_limit_uses_all(self):
        logs = [{"saves": 0, "holds": 1}, {"saves": 1, "holds": 0}]
        out = recent_svh(logs, limit=10)
        assert out["games"] == 2
        assert out["svh"] == 2

    def test_empty_log(self):
        out = recent_svh([], limit=10)
        assert out == {"games": 0, "sv": 0, "h": 0, "svh": 0}


# ── count_team_games ──

class TestCountTeamGames:
    def test_counts_games_and_opponents_per_team(self):
        sched = _schedule((135, 114), (139, 135))  # SD@CLE, TB@SD
        out = count_team_games(sched)
        assert out[135]["games"] == 2
        assert sorted(out[135]["opponents"]) == ["CLE", "TB"]
        assert out[114]["games"] == 1
        assert out[114]["opponents"] == ["SD"]

    def test_empty_schedule(self):
        assert count_team_games({"dates": []}) == {}


# ── scan (end-to-end) ──

def _scan_fetchers(*, lb14, lb30, fa_entries, roster, season_stats,
                   whiff, game_logs, schedule, today=date(2026, 5, 19)):
    fa_list = list(fa_entries)
    # Dispatch on the computed window starts — a wrong start raises KeyError
    # (fails loud) instead of silently routing both calls to one leaderboard.
    windows = {
        (today - timedelta(days=WINDOW_14D)).isoformat(): lb14,
        (today - timedelta(days=WINDOW_30D)).isoformat(): lb30,
    }
    return Fetchers(
        svh_leaderboard_fn=lambda s, e: windows[s],
        fa_pool_fn=lambda names: [e for e in fa_list
                                  if any(_normalize(e.name) == _normalize(n)
                                         for n in names)],
        roster_pitchers_fn=lambda: list(roster),
        season_stats_fn=lambda ids, season: season_stats,
        whiff_fn=lambda season: whiff,
        game_log_fn=lambda pid, season: game_logs.get(pid, []),
        week_schedule_fn=lambda s, e: schedule,
    )


def _full_scan_fixture():
    lb14 = _leaderboard(
        (101, "Adrian Morejon", 135, 0, 5),  # FA, svh 5
        (102, "Matt Festa", 114, 1, 3),      # FA, svh 4
        (103, "Jason Adam", 135, 2, 2),      # FA, svh 4
        (104, "Kevin Kelly", 139, 1, 4),     # incumbent (rostered), svh 5
        (105, "Ryne Stanek", 138, 0, 3),     # FA, svh 3
        (106, "Low Guy", 158, 0, 1),         # below floor 3
    )
    lb30 = _leaderboard(
        (101, "Adrian Morejon", 135, 0, 9),
        (102, "Matt Festa", 114, 2, 6),
        (103, "Jason Adam", 135, 3, 5),
        (104, "Kevin Kelly", 139, 2, 8),
        (105, "Ryne Stanek", 138, 1, 5),
        (106, "Low Guy", 158, 0, 2),
    )
    fa_entries = [
        FAEntry("Adrian Morejon", "8%"),
        FAEntry("Matt Festa", "2%"),
        FAEntry("Jason Adam", "5%"),
        FAEntry("Ryne Stanek", "1%"),
        # Kevin Kelly intentionally absent — rostered, not FA
    ]
    roster = [
        RosterPitcher(104, "Kevin Kelly", ("RP",)),
        RosterPitcher(669373, "Tarik Skubal", ("SP",)),
    ]
    season_stats = {
        101: {"bb9": 2.35, "era": 2.10, "ip": 30.0, "saves": 0, "holds": 9,
              "blown_saves": 1, "save_opportunities": 2},
        102: {"bb9": 2.14, "era": 3.00, "ip": 25.0, "saves": 2, "holds": 6,
              "blown_saves": 0, "save_opportunities": 1},
        103: {"bb9": 2.87, "era": 1.15, "ip": 15.7, "saves": 3, "holds": 5,
              "blown_saves": 4, "save_opportunities": 5},
        105: {"bb9": 7.45, "era": 5.00, "ip": 20.0, "saves": 1, "holds": 5,
              "blown_saves": 2, "save_opportunities": 3},
        104: {"bb9": 1.61, "era": 2.50, "ip": 22.0, "saves": 2, "holds": 8,
              "blown_saves": 1, "save_opportunities": 2},
    }
    whiff = {
        101: {"whiff_pct": 24.0, "arsenal_pitches": 300},
        102: {"whiff_pct": 20.0, "arsenal_pitches": 280},
        103: {"whiff_pct": 22.0, "arsenal_pitches": 290},
        105: {"whiff_pct": 31.0, "arsenal_pitches": 310},
        104: {"whiff_pct": 21.0, "arsenal_pitches": 300},
    }
    game_logs = {pid: [{"saves": 0, "holds": 1}] * 11 for pid in (101, 102, 103, 105, 104)}
    schedule = _schedule((135, 114), (139, 135), (138, 114), (135, 138))
    return _scan_fetchers(
        lb14=lb14, lb30=lb30, fa_entries=fa_entries, roster=roster,
        season_stats=season_stats, whiff=whiff, game_logs=game_logs,
        schedule=schedule,
    )


class TestScan:
    def test_windows_and_pool_size(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        assert result["scan_date"] == "2026-05-19"
        assert result["window_14d"] == {"start": "2026-05-05", "end": "2026-05-19"}
        assert result["window_30d"] == {"start": "2026-04-19", "end": "2026-05-19"}
        assert result["floor"] == 3
        # 4 FA candidates (Kelly rostered, Low Guy below floor)
        assert result["candidate_pool_size"] == 4

    def test_top_candidate_is_best_rank_sum(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        top = result["top_candidates"]
        assert len(top) == 4  # default top_n=4, all 4 FA returned
        assert top[0]["name"] == "Adrian Morejon"
        assert top[0]["rank_sum_place"] == 1

    def test_top_n_smaller_than_pool(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture(),
                      top_n=2)
        assert [c["name"] for c in result["top_candidates"]] == [
            "Adrian Morejon", "Matt Festa"]

    def test_candidate_carries_axes_and_profile(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        morejon = result["top_candidates"][0]
        assert morejon["mlb_id"] == 101
        assert morejon["team"] == "SD"
        assert morejon["percent_owned"] == "8%"
        assert morejon["axes"]["bb9"]["value"] == 2.35
        assert morejon["axes"]["svh_30d"]["value"] == 9
        assert morejon["profile"]["svh_14d"] == 5
        assert morejon["profile"]["sv_14d"] == 0
        assert morejon["profile"]["h_14d"] == 5
        assert morejon["profile"]["era"] == 2.10

    def test_role_signals_on_top_candidates(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        sig = result["top_candidates"][0]["role_signals"]
        assert sig["recent_10g"]["games"] == 10  # 11 logs capped to 10
        assert sig["recent_10g"]["svh"] == 10
        assert sig["blown_saves"] == 1
        assert sig["save_opportunities"] == 2
        assert sig["week_schedule"]["games"] == 3  # SD plays 3 in fixture

    def test_whiff_low_sample_flagged(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        # all fixture RP have <500 arsenal pitches → low-sample caveat
        assert result["top_candidates"][0]["whiff_low_sample"] is True

    def test_incumbent_is_rostered_svh_rp(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        inc = result["incumbent"]
        assert inc is not None
        assert inc["name"] == "Kevin Kelly"
        assert inc["in_pool"] is False
        assert inc["svh_30d"] == 10
        assert inc["profile"]["svh_14d"] == 5
        assert inc["role_signals"]["blown_saves"] == 1

    def test_all_candidates_lists_full_pool(self):
        result = scan(today=date(2026, 5, 19), fetchers=_full_scan_fixture())
        allc = result["all_candidates"]
        assert len(allc) == 4
        assert allc[0]["name"] == "Adrian Morejon"
        assert allc[0]["rank_sum_place"] == 1
        assert [c["rank_sum_place"] for c in allc] == [1, 2, 3, 4]

    def test_empty_leaderboard_no_crash(self):
        fetchers = _scan_fetchers(
            lb14={"stats": []}, lb30={"stats": []}, fa_entries=[],
            roster=[], season_stats={}, whiff={}, game_logs={},
            schedule={"dates": []},
        )
        result = scan(today=date(2026, 5, 19), fetchers=fetchers)
        assert result["candidate_pool_size"] == 0
        assert result["top_candidates"] == []
        assert result["incumbent"] is None

    def test_no_incumbent_when_no_svh_rp(self):
        # roster has only an SP → case B
        fx = _full_scan_fixture()
        fx.roster_pitchers_fn = lambda: [
            RosterPitcher(669373, "Tarik Skubal", ("SP",))]
        result = scan(today=date(2026, 5, 19), fetchers=fx)
        assert result["incumbent"] is None

    def test_incumbent_excluded_from_candidates_even_if_in_fa_pool(self):
        # Yahoo roster-sync lag can briefly list a just-added RP as FA.
        # The incumbent must never appear in both top_candidates and incumbent.
        fx = _full_scan_fixture()
        pool = [
            FAEntry("Adrian Morejon", "8%"), FAEntry("Matt Festa", "2%"),
            FAEntry("Jason Adam", "5%"), FAEntry("Ryne Stanek", "1%"),
            FAEntry("Kevin Kelly", "12%"),  # incumbent leaked into FA pool
        ]
        fx.fa_pool_fn = lambda names: [
            e for e in pool
            if any(_normalize(e.name) == _normalize(n) for n in names)
        ]
        result = scan(today=date(2026, 5, 19), fetchers=fx)
        assert 104 not in {c["mlb_id"] for c in result["top_candidates"]}
        assert result["candidate_pool_size"] == 4  # Kelly excluded
        assert result["incumbent"]["mlb_id"] == 104
        assert result["incumbent"]["in_pool"] is False
