"""TDD tests for stream_sp_scan.py — Step 2-6 of /stream-sp pipeline."""

import pytest

from stream_sp_scan import (
    Fetchers,
    GameLog,
    StarterRef,
    _enrich_v4,
    classify_opener,
    cross_check_fa,
    parse_schedule,
    scan,
    tier_opponent,
)


class TestClassifyOpener:
    def test_six_clear_starts_returns_true_starter(self):
        games = [
            GameLog(date="2026-04-08", gs=1, ip=5.0),
            GameLog(date="2026-04-15", gs=1, ip=5.0),
            GameLog(date="2026-04-21", gs=1, ip=6.0),
            GameLog(date="2026-04-26", gs=1, ip=5.0),
            GameLog(date="2026-05-02", gs=1, ip=6.0),
            GameLog(date="2026-05-08", gs=1, ip=5.0),
        ]
        assert classify_opener(games) == "true_starter"

    def test_two_games_returns_small_sample(self):
        games = [
            GameLog(date="2026-05-01", gs=1, ip=5.0),
            GameLog(date="2026-05-07", gs=1, ip=5.0),
        ]
        assert classify_opener(games) == "small_sample"

    def test_pure_opener_all_relief_short_ip(self):
        # 全 GS=0 且 IP <= 3 → 典型 opener / pure reliever 排成 starter
        games = [
            GameLog(date="2026-04-20", gs=0, ip=1.0),
            GameLog(date="2026-04-23", gs=0, ip=1.2),
            GameLog(date="2026-04-27", gs=0, ip=2.0),
            GameLog(date="2026-05-01", gs=0, ip=1.0),
            GameLog(date="2026-05-05", gs=0, ip=1.1),
            GameLog(date="2026-05-09", gs=0, ip=2.0),
        ]
        assert classify_opener(games) == "opener_suspect"

    def test_piggyback_mixed_role_short_avg_ip(self):
        # 3 GS + 3 relief, 平均 IP 約 3.0 (<4) → piggyback / 限局
        games = [
            GameLog(date="2026-04-20", gs=1, ip=4.0),
            GameLog(date="2026-04-23", gs=0, ip=2.0),
            GameLog(date="2026-04-27", gs=1, ip=4.0),
            GameLog(date="2026-05-01", gs=0, ip=2.0),
            GameLog(date="2026-05-05", gs=1, ip=4.0),
            GameLog(date="2026-05-09", gs=0, ip=2.0),
        ]
        assert classify_opener(games) == "opener_suspect"

    def test_starter_with_one_bulk_relief_game_still_true_starter(self):
        # Sean Burke 2026-04-26: GS=0 但 IP=7.1（bulk reliever 一場）
        # 其餘 5 場都是 GS + IP ≥ 4.1，平均 IP 5.6 → 仍是真先發
        games = [
            GameLog(date="2026-04-08", gs=1, ip=5.0),
            GameLog(date="2026-04-15", gs=1, ip=5.1),
            GameLog(date="2026-04-21", gs=1, ip=6.0),
            GameLog(date="2026-04-26", gs=0, ip=7.1),
            GameLog(date="2026-05-02", gs=1, ip=6.0),
            GameLog(date="2026-05-08", gs=1, ip=4.1),
        ]
        assert classify_opener(games) == "true_starter"


class TestTierOpponent:
    def test_strong_offense_returns_red(self):
        assert tier_opponent(0.800) == "🔴"

    def test_weak_offense_returns_green(self):
        # KC 14d .715 / CHC 14d .702 都標 🟢
        assert tier_opponent(0.702) == "🟢"

    def test_average_offense_returns_yellow(self):
        # 聯盟均值附近 .740 → 🟡
        assert tier_opponent(0.740) == "🟡"

    @pytest.mark.parametrize(
        "ops,expected",
        [
            (0.719, "🟢"),  # 緊接 🟡 下緣
            (0.720, "🟡"),  # 🟡 下緣含
            (0.754, "🟡"),  # 緊接 🔴 下緣
            (0.755, "🔴"),  # 🔴 下緣含
        ],
    )
    def test_tier_boundaries(self, ops, expected):
        assert tier_opponent(ops) == expected


class TestParseSchedule:
    def test_parses_single_game_both_pitchers_published(self):
        schedule_json = {
            "dates": [{
                "games": [{
                    "teams": {
                        "away": {
                            "team": {"id": 115, "name": "Colorado Rockies"},
                            "probablePitcher": {"id": 801403, "fullName": "Chase Dollander"},
                        },
                        "home": {
                            "team": {"id": 134, "name": "Pittsburgh Pirates"},
                            "probablePitcher": {"id": 669387, "fullName": "Carmen Mlodzinski"},
                        },
                    },
                }],
            }],
        }
        games = parse_schedule(schedule_json)
        assert len(games) == 1
        g = games[0]
        assert g.away_team == "COL"
        assert g.home_team == "PIT"
        assert g.away_sp.mlb_id == 801403
        assert g.away_sp.name == "Chase Dollander"
        assert g.home_sp.mlb_id == 669387
        assert g.home_sp.name == "Carmen Mlodzinski"

    def test_both_tbd_returns_none_for_both_sp(self):
        schedule_json = {
            "dates": [{
                "games": [{
                    "teams": {
                        "away": {"team": {"id": 143, "name": "PHI"}},
                        "home": {"team": {"id": 134, "name": "PIT"}},
                    },
                }],
            }],
        }
        games = parse_schedule(schedule_json)
        assert len(games) == 1
        assert games[0].away_sp is None
        assert games[0].home_sp is None
        assert games[0].away_team == "PHI"
        assert games[0].home_team == "PIT"

    def test_probable_pitcher_value_null_treated_as_tbd(self):
        # 某些 API 回傳：probablePitcher key 存在但 value 是 null
        schedule_json = {
            "dates": [{
                "games": [{
                    "teams": {
                        "away": {
                            "team": {"id": 116, "name": "DET"},
                            "probablePitcher": None,
                        },
                        "home": {
                            "team": {"id": 121, "name": "NYM"},
                            "probablePitcher": {"id": 690997, "fullName": "Nolan McLean"},
                        },
                    },
                }],
            }],
        }
        games = parse_schedule(schedule_json)
        assert games[0].away_sp is None
        assert games[0].home_sp.name == "Nolan McLean"

    def test_one_side_tbd_other_published(self):
        schedule_json = {
            "dates": [{
                "games": [{
                    "teams": {
                        "away": {
                            "team": {"id": 146, "name": "MIA"},
                            "probablePitcher": {"id": 702281, "fullName": "Robby Snelling"},
                        },
                        "home": {"team": {"id": 142, "name": "MIN"}},
                    },
                }],
            }],
        }
        games = parse_schedule(schedule_json)
        assert games[0].away_team == "MIA"
        assert games[0].home_team == "MIN"
        assert games[0].away_sp.name == "Robby Snelling"
        assert games[0].home_sp is None

    def test_multiple_games_preserve_order(self):
        schedule_json = {
            "dates": [{
                "games": [
                    {"teams": {
                        "away": {"team": {"id": 115}, "probablePitcher": {"id": 1, "fullName": "P1"}},
                        "home": {"team": {"id": 134}, "probablePitcher": {"id": 2, "fullName": "P2"}},
                    }},
                    {"teams": {
                        "away": {"team": {"id": 120}, "probablePitcher": {"id": 3, "fullName": "P3"}},
                        "home": {"team": {"id": 113}, "probablePitcher": {"id": 4, "fullName": "P4"}},
                    }},
                ],
            }],
        }
        games = parse_schedule(schedule_json)
        assert len(games) == 2
        assert games[0].away_team == "COL"
        assert games[1].away_team == "WSH"
        assert games[1].home_team == "CIN"


def _starter(name, mlb_id=1, team="CWS", opponent="CHC", is_home=True):
    return StarterRef(
        mlb_id=mlb_id, name=name, team=team, opponent=opponent, is_home=is_home,
    )


class TestCrossCheckFA:
    def test_fa_pitcher_goes_to_candidates(self):
        burke = _starter("Sean Burke", mlb_id=680732, team="CWS", opponent="CHC")
        result = cross_check_fa(
            probable=[burke],
            fa_names={"Sean Burke"},
            my_pitcher_names=set(),
        )
        assert result.candidates == [burke]
        assert result.owned_by_me == []
        assert result.owned_by_others == []

    def test_my_pitcher_goes_to_owned_by_me(self):
        junk = _starter("Janson Junk", mlb_id=676083, team="MIA", opponent="TB")
        result = cross_check_fa(
            probable=[junk],
            fa_names=set(),
            my_pitcher_names={"Janson Junk"},
        )
        assert result.candidates == []
        assert result.owned_by_me == [junk]
        assert result.owned_by_others == []

    def test_pitcher_not_fa_and_not_mine_goes_to_owned_by_others(self):
        bibee = _starter("Tanner Bibee", mlb_id=676440, team="CLE", opponent="CIN")
        result = cross_check_fa(
            probable=[bibee],
            fa_names=set(),
            my_pitcher_names=set(),
        )
        assert result.candidates == []
        assert result.owned_by_me == []
        assert result.owned_by_others == [bibee]

    def test_homonym_pitchers_classified_independently(self):
        # 邊界：Clay Holmes (NYM, 別隊 own) vs Grant Holmes (ATL, 本隊) — 不能 substring 比對
        clay = _starter("Clay Holmes", mlb_id=605280, team="NYM", opponent="NYY")
        grant = _starter("Grant Holmes", mlb_id=656550, team="ATL", opponent="BOS")
        result = cross_check_fa(
            probable=[clay, grant],
            fa_names=set(),
            my_pitcher_names={"Grant Holmes"},
        )
        assert result.candidates == []
        assert result.owned_by_me == [grant]
        assert result.owned_by_others == [clay]

    def test_mixed_pool_routes_three_starters_correctly(self):
        burke = _starter("Sean Burke", mlb_id=680732)
        junk = _starter("Janson Junk", mlb_id=676083, team="MIA")
        bibee = _starter("Tanner Bibee", mlb_id=676440, team="CLE")
        result = cross_check_fa(
            probable=[burke, junk, bibee],
            fa_names={"Sean Burke", "Dustin May"},
            my_pitcher_names={"Janson Junk", "Tarik Skubal"},
        )
        assert result.candidates == [burke]
        assert result.owned_by_me == [junk]
        assert result.owned_by_others == [bibee]


class TestEnrichV4:
    def test_empty_raw_returns_empty(self):
        assert _enrich_v4({}) == {}

    def test_full_raw_adds_sum_breakdown_gate_luck(self):
        # Sean Burke 2026 actual snapshot from VPS run
        raw = {
            "ip_gs": 5.11, "whiff_pct": 19.5, "bb9": 2.04,
            "gb_pct": 41.5, "xwobacon": 0.354,
            "g": 8, "gs": 6, "ip": 44.0, "bbe": 130,
            "era": 3.68, "xera": 3.79,
        }
        out = _enrich_v4(raw)
        # raw 欄位保留
        assert out["ip_gs"] == 5.11
        # enrich 加上的四個欄位
        assert isinstance(out["sum_score"], int)
        assert 5 <= out["sum_score"] <= 50
        assert isinstance(out["breakdown_pct"], dict)
        assert set(out["breakdown_pct"].keys()) == {"IP/GS", "Whiff%", "BB/9", "GB%", "xwOBACON"}
        assert out["rotation_gate"] in {"🟢", "🟡", "🚫"}
        # luck_tag 可能是 None（差距未達 P70 顯著門檻），但 key 必須存在
        assert "luck_tag" in out


def _build_fetchers(
    *,
    schedule=None,
    fa_names=None,
    roster=None,
    game_logs=None,
    team_ops=None,
    v4_data=None,
):
    return Fetchers(
        schedule_fn=lambda d: schedule or {"dates": []},
        fa_pool_fn=lambda: list(fa_names or []),
        roster_pitchers_fn=lambda: list(roster or []),
        game_log_fn=lambda mid, season: (game_logs or {}).get(mid, []),
        team_14d_ops_fn=lambda team_abbr: (team_ops or {}).get(team_abbr, 0.720),
        v4_data_fn=lambda ids, season: v4_data or {},
    )


class TestScan:
    def test_single_fa_candidate_enriched_end_to_end(self):
        schedule = {"dates": [{"games": [{
            "teams": {
                "away": {
                    "team": {"id": 145, "name": "CWS"},
                    "probablePitcher": {"id": 680732, "fullName": "Sean Burke"},
                },
                "home": {
                    "team": {"id": 112, "name": "CHC"},
                    "probablePitcher": {"id": 9999, "fullName": "Some Owned Cub"},
                },
            },
        }]}]}
        burke_log = [
            GameLog(date="2026-04-08", gs=1, ip=5.0),
            GameLog(date="2026-04-15", gs=1, ip=5.0),
            GameLog(date="2026-04-21", gs=1, ip=6.0),
            GameLog(date="2026-04-26", gs=1, ip=5.0),
            GameLog(date="2026-05-02", gs=1, ip=6.0),
            GameLog(date="2026-05-08", gs=1, ip=5.0),
        ]
        burke_v4_26 = {
            "ip_gs": 5.11, "whiff_pct": 19.5, "bb9": 2.04,
            "gb_pct": 41.5, "xwobacon": 0.354,
            "g": 8, "gs": 6, "ip": 44.0, "bbe": 130,
            "era": 3.68, "xera": 3.79,
        }
        burke_v4_25 = {
            "ip_gs": 5.0, "whiff_pct": 25.0, "bb9": 3.5,
            "gb_pct": 42.0, "xwobacon": 0.395,
            "g": 28, "gs": 22, "ip": 134.0, "bbe": 130,
            "era": 4.22, "xera": 4.30,
        }
        v4_data_by_season = {2026: {680732: burke_v4_26}, 2025: {680732: burke_v4_25}}
        fetchers = Fetchers(
            schedule_fn=lambda d: schedule,
            fa_pool_fn=lambda: ["Sean Burke"],
            roster_pitchers_fn=lambda: [],
            game_log_fn=lambda mid, season: {680732: burke_log}.get(mid, []),
            team_14d_ops_fn=lambda abbr: {"CHC": 0.702}.get(abbr, 0.720),
            v4_data_fn=lambda ids, season: v4_data_by_season.get(season, {}),
        )
        result = scan(["2026-05-15"], fetchers=fetchers)

        assert "2026-05-15" in result
        day = result["2026-05-15"]
        assert len(day["candidates"]) == 1
        c = day["candidates"][0]
        assert c["name"] == "Sean Burke"
        assert c["mlb_id"] == 680732
        assert c["team"] == "CWS"
        assert c["opponent"] == "CHC"
        assert c["is_home"] is False
        assert c["opener_verdict"] == "true_starter"
        assert c["opponent_14d"]["ops"] == 0.702
        assert c["opponent_14d"]["tier"] == "🟢"

        # v4_2026 enriched
        assert c["v4_2026"]["ip_gs"] == 5.11  # raw passthrough
        assert isinstance(c["v4_2026"]["sum_score"], int)
        assert c["v4_2026"]["rotation_gate"] == "🟢"  # 8 G / 6 GS, IP/GS > 3
        assert set(c["v4_2026"]["breakdown_pct"].keys()) == {
            "IP/GS", "Whiff%", "BB/9", "GB%", "xwOBACON",
        }
        # v4_2025 prior 也要被 fetch + enrich
        assert c["v4_2025"]["ip_gs"] == 5.0
        assert isinstance(c["v4_2025"]["sum_score"], int)

    def test_tbd_games_and_owned_segments_populated(self):
        schedule = {"dates": [{"games": [
            {  # game 1: away FA candidate (Burke), home owned by others
                "teams": {
                    "away": {
                        "team": {"id": 145},
                        "probablePitcher": {"id": 680732, "fullName": "Sean Burke"},
                    },
                    "home": {
                        "team": {"id": 112},
                        "probablePitcher": {"id": 9999, "fullName": "Owned Cub"},
                    },
                },
            },
            {  # game 2: my pitcher (Junk) away, home TBD
                "teams": {
                    "away": {
                        "team": {"id": 146},
                        "probablePitcher": {"id": 676083, "fullName": "Janson Junk"},
                    },
                    "home": {"team": {"id": 139}},
                },
            },
            {  # game 3: both TBD
                "teams": {
                    "away": {"team": {"id": 143}},
                    "home": {"team": {"id": 134}},
                },
            },
        ]}]}
        fetchers = _build_fetchers(
            schedule=schedule,
            fa_names={"Sean Burke"},
            roster={"Janson Junk"},
            game_logs={680732: [GameLog(date="d", gs=1, ip=5.0)] * 6},
            team_ops={"CHC": 0.702},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        day = result["2026-05-15"]

        # tbd_games
        tbd_descs = [(t["away"], t["home"], t["side"]) for t in day["tbd_games"]]
        assert ("MIA", "TB", "home") in tbd_descs
        assert ("PHI", "PIT", "both") in tbd_descs
        assert len(day["tbd_games"]) == 2

        # owned segments
        assert [s["name"] for s in day["owned_by_me"]] == ["Janson Junk"]
        assert [s["name"] for s in day["owned_by_others"]] == ["Owned Cub"]

    def test_multiple_dates_query_schedule_per_date(self):
        # 不同日不同 schedule — schedule_fn 由 et_date 決定
        sched_d1 = {"dates": [{"games": [{"teams": {
            "away": {"team": {"id": 145}, "probablePitcher": {"id": 1, "fullName": "Pitcher D1"}},
            "home": {"team": {"id": 112}, "probablePitcher": {"id": 2, "fullName": "Opponent D1"}},
        }}]}]}
        sched_d2 = {"dates": [{"games": [{"teams": {
            "away": {"team": {"id": 138}, "probablePitcher": {"id": 3, "fullName": "Pitcher D2"}},
            "home": {"team": {"id": 118}, "probablePitcher": {"id": 4, "fullName": "Opponent D2"}},
        }}]}]}
        schedules = {"2026-05-14": sched_d1, "2026-05-15": sched_d2}

        fetchers = Fetchers(
            schedule_fn=lambda d: schedules[d],
            fa_pool_fn=lambda: ["Pitcher D1", "Pitcher D2"],
            roster_pitchers_fn=lambda: [],
            game_log_fn=lambda mid, season: [GameLog(date="d", gs=1, ip=5.0)] * 6,
            team_14d_ops_fn=lambda abbr: 0.700,
            v4_data_fn=lambda ids, season: {},
        )
        result = scan(["2026-05-14", "2026-05-15"], fetchers=fetchers)

        assert set(result.keys()) == {"2026-05-14", "2026-05-15"}
        assert [c["name"] for c in result["2026-05-14"]["candidates"]] == ["Pitcher D1"]
        assert [c["name"] for c in result["2026-05-15"]["candidates"]] == ["Pitcher D2"]
