"""TDD tests for stream_sp_scan.py — Step 2-6 of /stream-sp pipeline."""

import pytest

from stream_sp_scan import (
    FAEntry,
    Fetchers,
    GameLog,
    StarterRef,
    _apply_vs_hand_gate,
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

    @pytest.mark.parametrize(
        "games_data,expected",
        [
            # 3-game minimum-valid boundary (just past small_sample cutoff)
            ([(1, 5.0), (1, 5.0), (1, 5.0)], "true_starter"),
            ([(0, 1.0), (0, 1.2), (0, 2.0)], "opener_suspect"),
        ],
    )
    def test_three_game_minimum_sample_boundary(self, games_data, expected):
        games = [
            GameLog(date=f"2026-05-{i+1:02d}", gs=gs, ip=ip)
            for i, (gs, ip) in enumerate(games_data)
        ]
        assert classify_opener(games) == expected

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
    def test_empty_raw_returns_unavailable_placeholder(self):
        # 之前回 {} 害 LLM 過濾規則查 .rotation_gate / .sum_score KeyError；
        # 改回明確 placeholder 帶 v4_available=False 讓 LLM 知道要排除/標註
        out = _enrich_v4({})
        assert out == {
            "v4_available": False,
            "sum_score": None,
            "breakdown_pct": {},
            "rotation_gate": None,
            "luck_tag": None,
        }

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
        # enrich 加上的五個欄位
        assert out["v4_available"] is True
        assert isinstance(out["sum_score"], int)
        assert 5 <= out["sum_score"] <= 50
        assert isinstance(out["breakdown_pct"], dict)
        assert set(out["breakdown_pct"].keys()) == {"IP/GS", "Whiff%", "BB/9", "GB%", "xwOBACON"}
        # rotation_gate_v4 回三種 icon：🟢 / ⚠️ / 🚫（不是 🟡）
        assert out["rotation_gate"] in {"🟢", "⚠️", "🚫"}
        # luck_tag 可能是 None（差距未達 P70 顯著門檻 或 BBE<40），但 key 必須存在
        assert "luck_tag" in out

    def test_swingman_role_returns_warning_gate(self):
        # GS/G ratio 0.3-0.6 → ⚠️ swingman（rotation_gate_v4 specific path）
        # 之前 test set 用 🟡 是 typo，這個 case 直接 exercise ⚠️ 路徑防 regression
        raw = {
            "ip_gs": 4.5, "whiff_pct": 22.0, "bb9": 3.0,
            "gb_pct": 40.0, "xwobacon": 0.370,
            "g": 10, "gs": 4, "ip": 38.0, "bbe": 90,
            "era": 4.20, "xera": 4.30,
        }
        out = _enrich_v4(raw)
        assert out["rotation_gate"] == "⚠️"


def _build_fetchers(
    *,
    schedule=None,
    fa_entries=None,
    roster=None,
    game_logs=None,
    team_ops=None,
    v4_data=None,
    vs_hand=None,
):
    fa_list = list(fa_entries or [])
    return Fetchers(
        schedule_fn=lambda d: schedule or {"dates": []},
        fa_pool_fn=lambda starter_names: [e for e in fa_list if e.name in starter_names],
        roster_pitchers_fn=lambda: list(roster or []),
        game_log_fn=lambda mid, season: (game_logs or {}).get(mid, []),
        team_14d_ops_fn=lambda team_abbr, end_date: (team_ops or {}).get(team_abbr, 0.720),
        v4_data_fn=lambda ids, season: v4_data or {},
        vs_hand_fn=lambda opp_abbr, sp_id: (vs_hand or {}).get(sp_id),
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
            fa_pool_fn=lambda names: (
                [FAEntry(name="Sean Burke", percent_owned="25%")]
                if "Sean Burke" in names else []
            ),
            roster_pitchers_fn=lambda: [],
            game_log_fn=lambda mid, season: {680732: burke_log}.get(mid, []),
            team_14d_ops_fn=lambda abbr, end_date: {"CHC": 0.702}.get(abbr, 0.720),
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
        assert c["percent_owned"] == "25%"  # 從 FAEntry 帶到 candidate

        # v4_2026 enriched
        assert c["v4_2026"]["v4_available"] is True
        assert c["v4_2026"]["ip_gs"] == 5.11  # raw passthrough
        assert isinstance(c["v4_2026"]["sum_score"], int)
        assert c["v4_2026"]["rotation_gate"] == "🟢"  # 8 G / 6 GS, IP/GS > 3
        assert set(c["v4_2026"]["breakdown_pct"].keys()) == {
            "IP/GS", "Whiff%", "BB/9", "GB%", "xwOBACON",
        }
        # v4_2025 prior 也要被 fetch + enrich
        assert c["v4_2025"]["v4_available"] is True
        assert c["v4_2025"]["ip_gs"] == 5.0
        assert isinstance(c["v4_2025"]["sum_score"], int)

        # vs_hand_2026 key 一定存在（schema contract）；fetcher 未注入 → None
        assert c["vs_hand_2026"] is None

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
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
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

    def test_empty_et_dates_returns_empty_dict(self):
        # CLI 用戶可能 `--et-dates ,` 過濾後留空 list
        fetchers = _build_fetchers()
        assert scan([], fetchers=fetchers) == {}

    def test_team_14d_ops_called_with_scanned_et_date(self):
        # W1 fix: 14d 對手強度視窗以掃描的 ET 日期錨點，不是 date.today()
        # （否則 backtest / 跨日 scan 14d 窗口錯位）
        captured = []
        schedule = {"dates": [{"games": [{
            "teams": {
                "away": {"team": {"id": 145}, "probablePitcher": {"id": 1, "fullName": "P1"}},
                "home": {"team": {"id": 112}, "probablePitcher": {"id": 2, "fullName": "P2"}},
            },
        }]}]}
        fetchers = Fetchers(
            schedule_fn=lambda d: schedule,
            fa_pool_fn=lambda names: [FAEntry("P1", "10%")] if "P1" in names else [],
            roster_pitchers_fn=lambda: [],
            game_log_fn=lambda mid, season: [GameLog("d", 1, 5.0)] * 6,
            team_14d_ops_fn=lambda team_abbr, end_date: (
                captured.append((team_abbr, end_date)) or 0.700
            ),
            v4_data_fn=lambda ids, season: {},
        )
        scan(["2026-05-15"], fetchers=fetchers)
        assert captured == [("CHC", "2026-05-15")]

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

        all_fa = [
            FAEntry(name="Pitcher D1", percent_owned="5%"),
            FAEntry(name="Pitcher D2", percent_owned="3%"),
        ]
        fetchers = Fetchers(
            schedule_fn=lambda d: schedules[d],
            fa_pool_fn=lambda names: [e for e in all_fa if e.name in names],
            roster_pitchers_fn=lambda: [],
            game_log_fn=lambda mid, season: [GameLog(date="d", gs=1, ip=5.0)] * 6,
            team_14d_ops_fn=lambda abbr, end_date: 0.700,
            v4_data_fn=lambda ids, season: {},
        )
        result = scan(["2026-05-14", "2026-05-15"], fetchers=fetchers)

        assert set(result.keys()) == {"2026-05-14", "2026-05-15"}
        assert [c["name"] for c in result["2026-05-14"]["candidates"]] == ["Pitcher D1"]
        assert [c["name"] for c in result["2026-05-15"]["candidates"]] == ["Pitcher D2"]


class TestApplyVsHandGate:
    """Pure gate logic — fetcher returns raw, scan transforms to final emit dict."""

    def test_normal_path_pa_above_threshold_emits_split_ops(self):
        raw = {
            "pa": 1356, "split_ops": 0.686,
            "k_pct": 21.8, "bb_pct": 8.2,
            "hand": "R", "season_ops": 0.720,
        }
        out = _apply_vs_hand_gate(raw)
        assert out == {
            "pa": 1356, "ops": 0.686,
            "k_pct": 21.8, "bb_pct": 8.2,
            "hand": "R", "low_pa_fallback": False,
        }

    def test_pa_at_boundary_400_uses_split_ops(self):
        # PA=400 邊界含 → 仍取 vs hand split
        raw = {
            "pa": 400, "split_ops": 0.650,
            "k_pct": 20.0, "bb_pct": 7.5,
            "hand": "L", "season_ops": 0.715,
        }
        out = _apply_vs_hand_gate(raw)
        assert out["ops"] == 0.650
        assert out["low_pa_fallback"] is False

    def test_pa_just_below_399_falls_back_to_season_ops(self):
        # PA=399 邊界 → fallback
        raw = {
            "pa": 399, "split_ops": 0.640,
            "k_pct": 19.5, "bb_pct": 7.0,
            "hand": "L", "season_ops": 0.730,
        }
        out = _apply_vs_hand_gate(raw)
        assert out["ops"] == 0.730  # season fallback
        assert out["pa"] == 399  # PA 保留原 split 數
        assert out["low_pa_fallback"] is True
        assert out["hand"] == "L"

    def test_low_pa_emits_season_ops_with_fallback_flag(self):
        # 5 月初典型情境：對手 vs hand 累積 PA 不足 400
        raw = {
            "pa": 250, "split_ops": 0.580,
            "k_pct": 22.5, "bb_pct": 6.8,
            "hand": "R", "season_ops": 0.705,
        }
        out = _apply_vs_hand_gate(raw)
        assert out["pa"] == 250
        assert out["ops"] == 0.705
        assert out["low_pa_fallback"] is True

    def test_unknown_hand_falls_back_with_null_hand(self):
        # 雙手投 / API 無 pitchHand → fetcher 回 hand=None → fallback
        raw = {
            "pa": 0, "split_ops": None,
            "k_pct": None, "bb_pct": None,
            "hand": None, "season_ops": 0.725,
        }
        out = _apply_vs_hand_gate(raw)
        assert out["hand"] is None
        assert out["ops"] == 0.725
        assert out["low_pa_fallback"] is True

    def test_none_raw_returns_none(self):
        # MLB API 失敗 → fetcher 回 None → gate 直接 passthrough None
        assert _apply_vs_hand_gate(None) is None


class TestScanVsHand:
    """e2e scan with vs_hand fetcher injected."""

    def _basic_schedule(self):
        # CWS @ CHC: Burke (FA) vs Owned Cub (owned by others)
        return {"dates": [{"games": [{
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
        }]}]}

    def test_scan_emits_vs_hand_2026_for_candidate(self):
        # Springs SEA vs LHP .592 ground truth case
        raw = {
            "pa": 1100, "split_ops": 0.592,
            "k_pct": 24.5, "bb_pct": 8.1,
            "hand": "L", "season_ops": 0.715,
        }
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            vs_hand={680732: raw},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["vs_hand_2026"]["ops"] == 0.592
        assert c["vs_hand_2026"]["hand"] == "L"
        assert c["vs_hand_2026"]["low_pa_fallback"] is False
        assert c["vs_hand_2026"]["pa"] == 1100

    def test_scan_emits_vs_hand_with_low_pa_fallback(self):
        raw = {
            "pa": 300, "split_ops": 0.640,
            "k_pct": 21.0, "bb_pct": 7.5,
            "hand": "R", "season_ops": 0.720,
        }
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            vs_hand={680732: raw},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["vs_hand_2026"]["ops"] == 0.720  # season fallback
        assert c["vs_hand_2026"]["low_pa_fallback"] is True

    def test_scan_emits_vs_hand_none_on_api_failure(self):
        # fetcher 回 None (API 失敗) → vs_hand_2026 也 None，scan 不中斷
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            vs_hand={680732: None},  # explicit None
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["vs_hand_2026"] is None

    def test_scan_calls_vs_hand_fn_with_opponent_abbr_and_sp_id(self):
        # 確認 fetcher 收到正確 args：對手 abbr + SP mlb_id
        captured = []
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
        )
        # 覆寫 vs_hand_fn 捕捉 args
        fetchers.vs_hand_fn = lambda opp_abbr, sp_id: (
            captured.append((opp_abbr, sp_id)) or None
        )
        scan(["2026-05-15"], fetchers=fetchers)
        assert captured == [("CHC", 680732)]
