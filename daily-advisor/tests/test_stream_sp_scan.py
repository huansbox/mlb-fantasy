"""TDD tests for stream_sp_scan.py — Step 2-6 of /stream-sp pipeline."""

import pytest

from stream_sp_scan import (
    FAEntry,
    Fetchers,
    GameLog,
    GameRef,
    ProbablePitcher,
    StarterRef,
    _apply_vs_hand_gate,
    _enrich_v4,
    _flatten_to_starters,
    _starter_to_summary,
    apply_projected,
    classify_opener,
    compute_pending_diff,
    compute_sample_warning,
    cross_check_fa,
    parse_projected_arg,
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
    id_resolver=None,
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
        id_resolver_fn=lambda team_abbr, name: (id_resolver or {}).get((team_abbr, name)),
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


class TestComputeSampleWarning:
    """2026 sample-confidence warning (issue 013, AND-for-low).

    - "low": BBE<30 AND GS<6 (both critically thin → every structural axis suspect)
    - "medium": BBE≤80 OR GS≤12 (at least one axis sample concerning)
    - "none": BBE>80 AND GS>12 (both reliable)
    """

    def test_alexander_both_thin_returns_low(self):
        # Alexander 2026: BBE 0 + GS 1 → both fail → low
        assert compute_sample_warning(bbe=0, gs=1) == "low"

    def test_mcdonald_bbe_mid_gs_thin_returns_medium(self):
        # McDonald 2026: BBE 65 + GS 4 → BBE not <30 so not double-thin → medium
        assert compute_sample_warning(bbe=65, gs=4) == "medium"

    def test_springs_bbe_full_gs_mid_returns_medium(self):
        # Springs 2026: BBE 183 + GS 11 → BBE pass, GS in 6-12 → medium
        assert compute_sample_warning(bbe=183, gs=11) == "medium"

    def test_both_pass_returns_none(self):
        # BBE 100 + GS 15 → both pass → none
        assert compute_sample_warning(bbe=100, gs=15) == "none"

    @pytest.mark.parametrize(
        "bbe,gs,expected",
        [
            # BBE boundary at 29/30 (with non-thin GS so only BBE axis matters)
            (29, 15, "medium"),  # BBE<30 alone → not low (GS pass) → medium
            (30, 15, "medium"),  # BBE=30 in 30-80 → medium
            # BBE boundary at 80/81 (with high GS so only BBE axis matters)
            (80, 13, "medium"),  # BBE=80 still ≤80 → medium
            (81, 13, "none"),    # BBE>80 and GS>12 → none
            # GS boundary at 5/6 (with high BBE so only GS axis matters)
            (100, 5, "medium"),  # GS<6 alone → not low (BBE pass) → medium
            (100, 6, "medium"),  # GS=6 in 6-12 → medium
            # GS boundary at 12/13 (with high BBE)
            (100, 12, "medium"),  # GS=12 still ≤12 → medium
            (100, 13, "none"),    # GS>12 and BBE>80 → none
            # AND-low boundary: BBE=29 + GS=5 → both thin → low
            (29, 5, "low"),
            # AND-low boundary: BBE=29 + GS=6 → only BBE thin → medium
            (29, 6, "medium"),
            # AND-low boundary: BBE=30 + GS=5 → only GS thin → medium
            (30, 5, "medium"),
        ],
    )
    def test_boundary_buckets(self, bbe, gs, expected):
        assert compute_sample_warning(bbe=bbe, gs=gs) == expected

    def test_none_inputs_return_none_warning(self):
        # v4 unavailable / missing bbe-or-gs → caller should pass None, we return None
        assert compute_sample_warning(bbe=None, gs=10) is None
        assert compute_sample_warning(bbe=50, gs=None) is None
        assert compute_sample_warning(bbe=None, gs=None) is None


class TestScanSampleWarning:
    """e2e scan emits sample_warning top-level key on each candidate."""

    def _basic_schedule(self):
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

    def test_candidate_with_full_sample_emits_none(self):
        # Burke 2026 snapshot: BBE 130 + GS 6 → BBE pass, GS=6 in 6-12 → medium
        burke_v4 = {
            "ip_gs": 5.11, "whiff_pct": 19.5, "bb9": 2.04,
            "gb_pct": 41.5, "xwobacon": 0.354,
            "g": 8, "gs": 6, "ip": 44.0, "bbe": 130,
            "era": 3.68, "xera": 3.79,
        }
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            v4_data={680732: burke_v4},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["sample_warning"] == "medium"

    def test_candidate_low_warning_when_both_axes_thin(self):
        # Alexander-shaped: BBE 0 + GS 1
        v4 = {
            "ip_gs": 4.0, "whiff_pct": 20.0, "bb9": 5.0,
            "gb_pct": 38.0, "xwobacon": 0.380,
            "g": 1, "gs": 1, "ip": 4.0, "bbe": 0,
            "era": 6.00, "xera": 5.50,
        }
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            v4_data={680732: v4},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["sample_warning"] == "low"

    def test_candidate_none_warning_when_both_pass(self):
        # Full-rotation late-season: BBE 200 + GS 20
        v4 = {
            "ip_gs": 6.0, "whiff_pct": 28.0, "bb9": 2.5,
            "gb_pct": 48.0, "xwobacon": 0.340,
            "g": 20, "gs": 20, "ip": 120.0, "bbe": 200,
            "era": 3.50, "xera": 3.60,
        }
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            v4_data={680732: v4},
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["sample_warning"] == "none"

    def test_candidate_with_v4_unavailable_emits_none_warning(self):
        # v4 data 抓不到 → bbe/gs 不存在 → sample_warning=None（不是 "low"）
        fetchers = _build_fetchers(
            schedule=self._basic_schedule(),
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
            v4_data={},  # 沒 Burke 的 v4 → _enrich_v4 走 unavailable 路徑
        )
        result = scan(["2026-05-15"], fetchers=fetchers)
        c = result["2026-05-15"]["candidates"][0]
        assert c["v4_2026"]["v4_available"] is False
        # v4 unavailable 時 sample_warning 也應該是 None — 沒材料判斷信心
        assert c["sample_warning"] is None


# ── Pending diff (issue 014) ────────────────────────────────────────────────


def _scan_day(
    *,
    candidates=(),
    owned_by_me=(),
    owned_by_others=(),
    tbd_games=(),
):
    """Stub a scan_result_for_date dict for compute_pending_diff tests."""
    def _starter_summary(name, team, is_home):
        return {
            "name": name, "mlb_id": 0, "team": team,
            "opponent": "XXX", "is_home": is_home,
        }
    return {
        "tbd_games": list(tbd_games),
        "candidates": [_starter_summary(*c) for c in candidates],
        "owned_by_me": [_starter_summary(*c) for c in owned_by_me],
        "owned_by_others": [_starter_summary(*c) for c in owned_by_others],
    }


class TestComputePendingDiff:
    def test_still_starting_when_pending_sp_in_candidates(self):
        # Alexander 在 candidates 仍是 FA + 仍 starter
        pending = [{"name": "Jason Alexander", "team": "HOU", "is_home": False}]
        day = _scan_day(candidates=[("Jason Alexander", "HOU", False)])
        diff = compute_pending_diff(pending, day)
        assert diff == {
            "still_starting": ["Jason Alexander"],
            "lost_to_others": [],
            "replaced": [],
            "no_longer_scheduled": [],
        }

    def test_lost_to_others_when_pending_sp_in_owned_by_others(self):
        # Burke 被聯盟認領 → 出現在 owned_by_others
        pending = [{"name": "Sean Burke", "team": "CWS", "is_home": True}]
        day = _scan_day(owned_by_others=[("Sean Burke", "CWS", True)])
        diff = compute_pending_diff(pending, day)
        assert diff["lost_to_others"] == ["Sean Burke"]
        assert diff["still_starting"] == []

    def test_replaced_when_slot_has_different_starter(self):
        # Canning (SD home) 原評估，但 SD home 今天換 Vásquez
        pending = [{"name": "Griffin Canning", "team": "SD", "is_home": True}]
        day = _scan_day(candidates=[("Randy Vásquez", "SD", True)])
        diff = compute_pending_diff(pending, day)
        assert diff["replaced"] == [
            {"old": "Griffin Canning", "new": "Randy Vásquez", "team": "SD"},
        ]
        assert diff["still_starting"] == []

    def test_no_longer_scheduled_when_team_absent(self):
        # 該 SP 的球隊今天根本沒比賽（雨延等）
        pending = [{"name": "Some SP", "team": "BAL", "is_home": True}]
        day = _scan_day(candidates=[("Other SP", "NYY", False)])
        diff = compute_pending_diff(pending, day)
        assert diff["no_longer_scheduled"] == ["Some SP"]

    def test_replaced_with_null_new_when_slot_becomes_tbd(self):
        # 原 starter 拉下但替補未公布 → slot TBD → 視為 replaced, new=null
        pending = [{"name": "Pulled SP", "team": "NYY", "is_home": True}]
        day = _scan_day(tbd_games=[{"away": "BOS", "home": "NYY", "side": "home"}])
        diff = compute_pending_diff(pending, day)
        assert diff["replaced"] == [
            {"old": "Pulled SP", "new": None, "team": "NYY"},
        ]

    def test_homonym_disambiguated_by_team_slot(self):
        # 邊界：pending = Clay Holmes (NYM home)，今天 Grant Holmes 在 ATL away (FA)
        # 不可因「Holmes 在 candidates」就標 still_starting
        pending = [{"name": "Clay Holmes", "team": "NYM", "is_home": True}]
        day = _scan_day(
            candidates=[("Grant Holmes", "ATL", False)],
            owned_by_others=[("Replacement", "NYM", True)],
        )
        diff = compute_pending_diff(pending, day)
        # NYM home 今天是 Replacement (不是 Clay)，視為 replaced
        assert diff["replaced"] == [
            {"old": "Clay Holmes", "new": "Replacement", "team": "NYM"},
        ]
        assert diff["still_starting"] == []
        assert diff["lost_to_others"] == []

    def test_multiple_pending_sps_routed_to_correct_buckets(self):
        # 5/26 場景：4 位 pending，3 still + 1 lost + 1 replaced + 0 gone
        pending = [
            {"name": "Jason Alexander", "team": "HOU", "is_home": False},
            {"name": "Kyle Freeland", "team": "COL", "is_home": False},
            {"name": "Sean Burke", "team": "CWS", "is_home": True},
            {"name": "Griffin Canning", "team": "SD", "is_home": True},
        ]
        day = _scan_day(
            candidates=[
                ("Jason Alexander", "HOU", False),
                ("Kyle Freeland", "COL", False),
                ("Randy Vásquez", "SD", True),
            ],
            owned_by_others=[("Sean Burke", "CWS", True)],
        )
        diff = compute_pending_diff(pending, day)
        assert sorted(diff["still_starting"]) == ["Jason Alexander", "Kyle Freeland"]
        assert diff["lost_to_others"] == ["Sean Burke"]
        assert diff["replaced"] == [
            {"old": "Griffin Canning", "new": "Randy Vásquez", "team": "SD"},
        ]
        assert diff["no_longer_scheduled"] == []


class TestScanPendingDiffEmission:
    """Top-level `pending_diff` key emission in scan() output (issue 014)."""

    def _basic_fetchers_with_burke_as_fa(self):
        schedule = {"dates": [{"games": [{
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
        return _build_fetchers(
            schedule=schedule,
            fa_entries=[FAEntry(name="Sean Burke", percent_owned="25%")],
            game_logs={680732: [GameLog("d", 1, 5.0)] * 6},
            team_ops={"CHC": 0.702},
        )

    def test_no_pending_data_omits_pending_diff_key(self):
        # 不給 pending_data → JSON 不含 pending_diff key
        fetchers = self._basic_fetchers_with_burke_as_fa()
        result = scan(["2026-05-15"], fetchers=fetchers)
        assert "pending_diff" not in result

    def test_pending_data_given_emits_pending_diff_with_overlap_date(self):
        # 給 pending_data + ET 日重疊 → diff 被計算
        fetchers = self._basic_fetchers_with_burke_as_fa()
        pending_data = {
            "2026-05-15": {
                "tbd_games": [],
                "evaluations": [{"name": "Sean Burke", "team": "CWS", "is_home": False}],
            },
        }
        result = scan(["2026-05-15"], fetchers=fetchers, pending_data=pending_data)
        assert "pending_diff" in result
        assert result["pending_diff"]["2026-05-15"]["still_starting"] == ["Sean Burke"]

    def test_pending_data_given_but_no_overlap_emits_empty_dict(self):
        # 給 pending_data 但無日期重疊 → emit empty dict（表示 pending mode 開啟但無對應）
        fetchers = self._basic_fetchers_with_burke_as_fa()
        pending_data = {
            "2026-05-30": {
                "tbd_games": [],
                "evaluations": [{"name": "Other", "team": "NYY", "is_home": True}],
            },
        }
        result = scan(["2026-05-15"], fetchers=fetchers, pending_data=pending_data)
        assert result["pending_diff"] == {}


# ── Projected injection (L1: manual projected starter feed) ──


def _game(away="COL", home="PIT", away_sp=None, home_sp=None):
    return GameRef(away_team=away, home_team=home, away_sp=away_sp, home_sp=home_sp)


class TestParseProjectedArg:
    def test_empty_or_none_returns_empty_dict(self):
        assert parse_projected_arg("") == {}
        assert parse_projected_arg(None) == {}

    def test_single_entry(self):
        out = parse_projected_arg("2026-06-20:WSH:MacKenzie Gore")
        assert out == {"2026-06-20": [("WSH", "MacKenzie Gore")]}

    def test_multiple_entries_grouped_by_date(self):
        out = parse_projected_arg(
            "2026-06-20:WSH:MacKenzie Gore,2026-06-20:CHC:Jameson Taillon,"
            "2026-06-21:TB:Ryan Pepiot"
        )
        assert out == {
            "2026-06-20": [("WSH", "MacKenzie Gore"), ("CHC", "Jameson Taillon")],
            "2026-06-21": [("TB", "Ryan Pepiot")],
        }

    def test_name_with_accent_and_punctuation_preserved(self):
        # parse 不 normalize（resolver 才做）— 原樣保留含重音 / 句點
        out = parse_projected_arg("2026-06-20:STL:José Ramírez Jr.")
        assert out == {"2026-06-20": [("STL", "José Ramírez Jr.")]}

    def test_name_containing_colon_splits_only_first_two(self):
        # 防呆：name 段內若含冒號只切前兩個分隔
        out = parse_projected_arg("2026-06-20:WSH:Foo: Bar")
        assert out == {"2026-06-20": [("WSH", "Foo: Bar")]}

    def test_whitespace_trimmed_around_segments(self):
        out = parse_projected_arg(" 2026-06-20 : WSH : MacKenzie Gore ")
        assert out == {"2026-06-20": [("WSH", "MacKenzie Gore")]}

    def test_blank_entries_between_commas_skipped(self):
        out = parse_projected_arg("2026-06-20:WSH:MacKenzie Gore,,")
        assert out == {"2026-06-20": [("WSH", "MacKenzie Gore")]}

    def test_malformed_entry_too_few_segments_raises(self):
        with pytest.raises(ValueError):
            parse_projected_arg("2026-06-20:WSH")  # 缺 name 段


class TestApplyProjected:
    _IDS = {
        "MacKenzie Gore": 681190,
        "Jameson Taillon": 592791,
        "Grant Holmes": 656550,
        "Clay Holmes": 605280,
    }

    def _resolver(self, team_abbr, name):
        return self._IDS[name]

    def test_fills_empty_away_side_marks_projected(self):
        games = [_game(away="WSH", home="TB", home_sp=ProbablePitcher(99, "Ryan Pepiot"))]
        out = apply_projected(games, [("WSH", "MacKenzie Gore")], self._resolver)
        assert out[0].away_sp == ProbablePitcher(681190, "MacKenzie Gore", projected=True)
        # 官方 home side 不動（projected 預設 False）
        assert out[0].home_sp == ProbablePitcher(99, "Ryan Pepiot")
        assert out[0].home_sp.projected is False

    def test_fills_empty_home_side(self):
        games = [_game(away="CIN", home="NYY", away_sp=ProbablePitcher(5, "Rhett Lowder"))]
        out = apply_projected(games, [("NYY", "Clay Holmes")], self._resolver)
        assert out[0].home_sp.name == "Clay Holmes"
        assert out[0].home_sp.mlb_id == 605280
        assert out[0].home_sp.projected is True

    def test_does_not_overwrite_official_probable(self):
        games = [_game(away="WSH", home="TB", away_sp=ProbablePitcher(42, "Official Guy"))]
        out = apply_projected(games, [("WSH", "MacKenzie Gore")], self._resolver)
        assert out[0].away_sp == ProbablePitcher(42, "Official Guy")
        assert out[0].away_sp.projected is False

    def test_team_not_in_schedule_skipped(self):
        games = [_game(away="WSH", home="TB")]
        out = apply_projected(games, [("LAD", "Some Pitcher")], self._resolver)
        assert out[0].away_sp is None and out[0].home_sp is None

    def test_homonym_resolved_by_team(self):
        # Grant Holmes (ATL) vs Clay Holmes (NYM) — team 定位場次 + resolver 拿 team+name
        games = [
            _game(away="ATL", home="BOS"),
            _game(away="NYM", home="PHI"),
        ]
        out = apply_projected(
            games,
            [("ATL", "Grant Holmes"), ("NYM", "Clay Holmes")],
            self._resolver,
        )
        assert out[0].away_sp.name == "Grant Holmes" and out[0].away_sp.mlb_id == 656550
        assert out[1].away_sp.name == "Clay Holmes" and out[1].away_sp.mlb_id == 605280

    def test_resolver_not_called_when_side_already_official(self):
        # 已官方 side → 不解析 id（避免無謂 API call + 不覆蓋）
        calls = []

        def tracking_resolver(team_abbr, name):
            calls.append((team_abbr, name))
            return 999

        games = [_game(away="WSH", home="TB", away_sp=ProbablePitcher(42, "Official"))]
        apply_projected(games, [("WSH", "MacKenzie Gore")], tracking_resolver)
        assert calls == []

    def test_projected_flag_flows_to_flatten_and_summary(self):
        games = [_game(away="WSH", home="TB", home_sp=ProbablePitcher(99, "Ryan Pepiot"))]
        out = apply_projected(games, [("WSH", "MacKenzie Gore")], self._resolver)
        starters = _flatten_to_starters(out)
        gore = next(s for s in starters if s.name == "MacKenzie Gore")
        assert gore.projected is True
        assert _starter_to_summary(gore)["projected"] is True
        pepiot = next(s for s in starters if s.name == "Ryan Pepiot")
        assert pepiot.projected is False
        assert _starter_to_summary(pepiot)["projected"] is False


class TestScanProjected:
    def _gore_v4(self):
        return {
            "ip_gs": 5.0, "whiff_pct": 25.0, "bb9": 3.0, "gb_pct": 44.0,
            "xwobacon": 0.36, "g": 15, "gs": 15, "ip": 80.0, "bbe": 120,
            "era": 4.0, "xera": 4.0,
        }

    def _schedule_wsh_tb_away_tbd(self):
        # WSH @ TB — away (WSH) 無 probablePitcher → TBD；home (TB) 官方 Pepiot
        return {"dates": [{"games": [{
            "teams": {
                "away": {"team": {"id": 120}},
                "home": {"team": {"id": 139}, "probablePitcher": {"id": 99, "fullName": "Ryan Pepiot"}},
            },
        }]}]}

    def test_projected_candidate_enriched_and_removed_from_tbd(self):
        fetchers = _build_fetchers(
            schedule=self._schedule_wsh_tb_away_tbd(),
            fa_entries=[FAEntry(name="MacKenzie Gore", percent_owned="40%")],
            game_logs={681190: [GameLog(f"2026-06-1{i}", 1, 5.0) for i in range(5)]},
            team_ops={"TB": 0.652},
            v4_data={681190: self._gore_v4()},
            id_resolver={("WSH", "MacKenzie Gore"): 681190},
        )
        result = scan(
            ["2026-06-20"], fetchers=fetchers,
            projected={"2026-06-20": [("WSH", "MacKenzie Gore")]},
        )
        day = result["2026-06-20"]
        cand = [c for c in day["candidates"] if c["name"] == "MacKenzie Gore"]
        assert len(cand) == 1
        assert cand[0]["projected"] is True
        assert cand[0]["mlb_id"] == 681190
        assert cand[0]["team"] == "WSH" and cand[0]["opponent"] == "TB"
        # away 注入 + home 官方 → 整場 confirmed，tbd_games 清空
        assert day["tbd_games"] == []

    def test_official_starters_have_projected_false(self):
        fetchers = _build_fetchers(
            schedule=self._schedule_wsh_tb_away_tbd(),
            fa_entries=[FAEntry(name="MacKenzie Gore", percent_owned="40%")],
            game_logs={681190: [GameLog(f"2026-06-1{i}", 1, 5.0) for i in range(5)]},
            team_ops={"TB": 0.652},
            v4_data={681190: self._gore_v4()},
            id_resolver={("WSH", "MacKenzie Gore"): 681190},
        )
        result = scan(
            ["2026-06-20"], fetchers=fetchers,
            projected={"2026-06-20": [("WSH", "MacKenzie Gore")]},
        )
        # Pepiot 非 FA / 非本隊 → owned_by_others，且 projected False
        pepiot = next(s for s in result["2026-06-20"]["owned_by_others"] if s["name"] == "Ryan Pepiot")
        assert pepiot["projected"] is False

    def test_no_projected_arg_leaves_tbd_intact(self):
        # projected=None → 行為與舊版一致（regression）：away 仍 TBD
        fetchers = _build_fetchers(schedule=self._schedule_wsh_tb_away_tbd())
        result = scan(["2026-06-20"], fetchers=fetchers)
        day = result["2026-06-20"]
        assert day["tbd_games"] == [{"away": "WSH", "home": "TB", "side": "away"}]
        assert all(c["name"] != "MacKenzie Gore" for c in day["candidates"])

    def test_projected_for_other_date_does_not_affect_this_date(self):
        fetchers = _build_fetchers(
            schedule=self._schedule_wsh_tb_away_tbd(),
            id_resolver={("WSH", "MacKenzie Gore"): 681190},
        )
        result = scan(
            ["2026-06-20"], fetchers=fetchers,
            projected={"2026-06-21": [("WSH", "MacKenzie Gore")]},
        )
        # projected 綁在 06-21，06-20 的 away 仍 TBD
        assert result["2026-06-20"]["tbd_games"] == [{"away": "WSH", "home": "TB", "side": "away"}]
