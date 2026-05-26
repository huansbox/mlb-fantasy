"""TDD tests for mlb_query.py — gamelog_with_qs + opponent_context + deep_batch helpers."""

import pytest

from mlb_query import (
    MlbIdNotFoundError,
    deep_batch,
    gamelog_with_qs,
    is_quality_start,
    opponent_context,
    parse_ip,
)


# ---- shared mock fetchers for TestDeepBatch ----

def _ok_gamelog(mlb_id, season):
    return [
        {"date": "2026-04-29", "opp": "NYM", "h_a": "A", "ip": "6.0", "h": 4, "r": 2,
         "er": 2, "bb": 2, "k": 10, "hr": 1, "pc": 97, "era": "3.00"},
    ]


def _ok_meta(sp_id):
    return {"throws": "R"}


def _ok_range(team_id, end_date, days):
    return {"ops": ".700", "g": days // 2 or 1, "avg": ".240", "obp": ".310",
            "rg": 4.0, "k_pct": 22.0, "bb_pct": 8.0}


def _ok_split(team_id, hand):
    return {"ops": ".680", "pa": 1200, "avg": ".235", "obp": ".305",
            "k_pct": 24.0, "bb_pct": 10.0, "hand": hand}


def _ok_fetchers():
    return {"gamelog": _ok_gamelog, "meta": _ok_meta, "range": _ok_range, "split": _ok_split}


class TestParseIp:
    def test_five_two_means_five_and_two_thirds(self):
        # "5.2" in MLB innings format = 5 and 2/3 innings, NOT 5.2 decimal
        assert parse_ip("5.2") == pytest.approx(5.667, abs=0.001)

    def test_zero_zero_is_zero(self):
        assert parse_ip("0.0") == 0.0

    def test_five_zero_is_five(self):
        assert parse_ip("5.0") == 5.0

    def test_six_zero_is_six(self):
        assert parse_ip("6.0") == 6.0

    def test_seven_one_is_seven_and_one_third(self):
        assert parse_ip("7.1") == pytest.approx(7.333, abs=0.001)


class TestIsQualityStart:
    def test_six_innings_three_er_is_qs(self):
        # Lower boundary: exactly 6 IP and exactly 3 ER qualifies
        assert is_quality_start(6.0, 3) is True

    def test_five_and_two_thirds_zero_er_is_not_qs(self):
        # Critical: "5.2" innings = 5.667, must NOT qualify even with 0 ER
        assert is_quality_start(parse_ip("5.2"), 0) is False

    def test_six_innings_four_er_is_not_qs(self):
        # ER boundary: 4 ER disqualifies regardless of innings
        assert is_quality_start(6.0, 4) is False


class TestGamelogWithQs:
    def test_enriches_each_entry_with_ip_decimal_and_qs(self):
        # Mock fetcher returns 3 starts: one QS (6.0, 2 ER), one short (5.2, 1 ER), one bombed (4.0, 6 ER)
        def mock_fetch(mlb_id, season):
            return [
                {"date": "2026-04-29", "opp": "NYM", "ip": "6.0", "er": 2, "k": 10, "bb": 2},
                {"date": "2026-05-05", "opp": "MIN", "ip": "5.2", "er": 1, "k": 5, "bb": 3},
                {"date": "2026-04-13", "opp": "PIT", "ip": "4.0", "er": 6, "k": 2, "bb": 3},
            ]

        result = gamelog_with_qs(676917, 2026, fetch_fn=mock_fetch)

        assert len(result) == 3
        assert result[0]["ip_decimal"] == 6.0
        assert result[0]["qs"] is True
        assert result[1]["ip_decimal"] == pytest.approx(5.667, abs=0.001)
        assert result[1]["qs"] is False  # 5.2 IP is NOT QS even with 1 ER
        assert result[2]["ip_decimal"] == 4.0
        assert result[2]["qs"] is False

    def test_raw_fields_pass_through(self):
        def mock_fetch(mlb_id, season):
            return [{"date": "2026-04-29", "opp": "NYM", "ip": "6.0", "er": 2, "k": 10, "bb": 2, "hr": 1, "pc": 97}]

        result = gamelog_with_qs(676917, 2026, fetch_fn=mock_fetch)

        assert result[0]["date"] == "2026-04-29"
        assert result[0]["opp"] == "NYM"
        assert result[0]["k"] == 10
        assert result[0]["hr"] == 1
        assert result[0]["pc"] == 97


class TestOpponentContext:
    def test_returns_three_windows_plus_split(self):
        def mock_meta(sp_id):
            return {"throws": "R"}

        def mock_range(team_id, end_date, days):
            # Returns different OPS per window so we can verify correct key
            return {"ops": f".{700 - days}", "g": days // 2, "k_pct": 24.0, "bb_pct": 9.0}

        def mock_split(team_id, hand):
            return {"ops": ".702", "pa": 1182, "k_pct": 24.3, "bb_pct": 10.6, "hand": hand}

        result = opponent_context(
            team_id=110,
            end_date="2026-05-16",
            sp_id=676917,
            fetch_meta_fn=mock_meta,
            fetch_range_fn=mock_range,
            fetch_split_fn=mock_split,
        )

        assert "7d" in result and "14d" in result and "30d" in result
        assert "vs_hand" in result
        assert result["7d"]["ops"] == ".693"
        assert result["14d"]["ops"] == ".686"
        assert result["30d"]["ops"] == ".670"

    def test_handedness_resolved_internally_from_sp_id(self):
        # SP is left-handed → split fetcher must receive "L" without caller passing it
        captured_hand = []

        def mock_meta(sp_id):
            return {"throws": "L"}

        def mock_range(team_id, end_date, days):
            return {"ops": ".700"}

        def mock_split(team_id, hand):
            captured_hand.append(hand)
            return {"ops": ".700", "hand": hand}

        opponent_context(
            team_id=110,
            end_date="2026-05-16",
            sp_id=999999,
            fetch_meta_fn=mock_meta,
            fetch_range_fn=mock_range,
            fetch_split_fn=mock_split,
        )

        assert captured_hand == ["L"]


class TestDeepBatch:
    def test_returns_by_player_and_comparison_table_shape(self):
        result = deep_batch(
            players=[{"mlb_id": 686790, "et_date": "2026-05-27", "opp_team_id": 109,
                      "sp_name": "Trevor McDonald", "opp_abbr": "AZ",
                      "sum26": 40, "sum25": 46}],
            fetchers=_ok_fetchers(),
        )

        assert set(result) == {"by_player", "comparison_table"}
        assert "686790" in result["by_player"]
        bp = result["by_player"]["686790"]
        assert {"game_log", "opponent_context", "sp_meta"} <= set(bp)
        assert bp["sp_meta"]["name"] == "Trevor McDonald"
        assert bp["sp_meta"]["hand"] == "R"

    def test_comparison_table_headers_fixed_order(self):
        # Headers present and order fixed even with empty players
        result = deep_batch(players=[], fetchers=_ok_fetchers())
        assert result["comparison_table"]["headers"] == [
            "7d OPS", "30d→7d Δ", "vs hand OPS", "近 6 場 ERA",
            "Floor risk hint", "Sum26", "雙年 prior",
        ]

    def test_empty_players_returns_empty_structure(self):
        result = deep_batch(players=[], fetchers=_ok_fetchers())
        assert result["by_player"] == {}
        assert result["comparison_table"]["rows"] == []
        # Headers still present
        assert len(result["comparison_table"]["headers"]) == 7

    def test_preserves_input_order_in_rows(self):
        players = [
            {"mlb_id": 111, "et_date": "2026-05-27", "opp_team_id": 109,
             "sp_name": "Alpha", "opp_abbr": "AZ"},
            {"mlb_id": 222, "et_date": "2026-05-28", "opp_team_id": 110,
             "sp_name": "Bravo", "opp_abbr": "BAL"},
            {"mlb_id": 333, "et_date": "2026-05-29", "opp_team_id": 111,
             "sp_name": "Charlie", "opp_abbr": "BOS"},
        ]
        result = deep_batch(players=players, fetchers=_ok_fetchers())

        # by_player keys in insertion order
        assert list(result["by_player"].keys()) == ["111", "222", "333"]
        # comparison_table rows preserve player order (explicit assertion)
        rows = result["comparison_table"]["rows"]
        assert [r["sp"] for r in rows] == ["Alpha vs AZ", "Bravo vs BAL", "Charlie vs BOS"]

    def test_handles_different_et_dates_per_player(self):
        captured = []

        def range_fn(team_id, end_date, days):
            captured.append((team_id, end_date, days))
            return {"ops": ".700"}

        players = [
            {"mlb_id": 111, "et_date": "2026-05-15", "opp_team_id": 109,
             "sp_name": "A", "opp_abbr": "X"},
            {"mlb_id": 222, "et_date": "2026-05-20", "opp_team_id": 110,
             "sp_name": "B", "opp_abbr": "Y"},
        ]
        deep_batch(players=players, fetchers={
            "gamelog": _ok_gamelog, "meta": _ok_meta,
            "range": range_fn, "split": _ok_split,
        })

        dates_109 = {d for tid, d, _ in captured if tid == 109}
        dates_110 = {d for tid, d, _ in captured if tid == 110}
        assert dates_109 == {"2026-05-15"}
        assert dates_110 == {"2026-05-20"}

    def test_mlb_id_not_found_raises(self):
        def gamelog_fn(mlb_id, season):
            raise MlbIdNotFoundError(f"ID {mlb_id} not found")

        with pytest.raises(MlbIdNotFoundError):
            deep_batch(
                players=[{"mlb_id": 999999, "et_date": "2026-05-27", "opp_team_id": 109,
                          "sp_name": "Ghost", "opp_abbr": "X"}],
                fetchers={"gamelog": gamelog_fn, "meta": _ok_meta,
                          "range": _ok_range, "split": _ok_split},
            )

    def test_partial_failure_one_sp_errors_others_continue(self):
        def gamelog_fn(mlb_id, season):
            if mlb_id == 222:
                raise ConnectionError("API unavailable")
            return _ok_gamelog(mlb_id, season)

        players = [
            {"mlb_id": 111, "et_date": "2026-05-27", "opp_team_id": 109,
             "sp_name": "Good", "opp_abbr": "X"},
            {"mlb_id": 222, "et_date": "2026-05-27", "opp_team_id": 110,
             "sp_name": "Bad", "opp_abbr": "Y"},
            {"mlb_id": 333, "et_date": "2026-05-27", "opp_team_id": 111,
             "sp_name": "Good2", "opp_abbr": "Z"},
        ]
        result = deep_batch(players=players, fetchers={
            "gamelog": gamelog_fn, "meta": _ok_meta,
            "range": _ok_range, "split": _ok_split,
        })

        # Bad SP marked with error, others have full payload
        assert "error" in result["by_player"]["222"]
        assert "API unavailable" in result["by_player"]["222"]["error"]
        assert "game_log" in result["by_player"]["111"]
        assert "game_log" in result["by_player"]["333"]
        # comparison_table preserves row order (3 rows, Bad row still in position 1)
        rows = result["comparison_table"]["rows"]
        assert len(rows) == 3
        assert rows[1]["sp"] == "Bad vs Y"

    def test_per_sp_timeout_isolated(self):
        def gamelog_fn(mlb_id, season):
            if mlb_id == 222:
                raise TimeoutError("fetch exceeded 30s")
            return _ok_gamelog(mlb_id, season)

        players = [
            {"mlb_id": 111, "et_date": "2026-05-27", "opp_team_id": 109,
             "sp_name": "A", "opp_abbr": "X"},
            {"mlb_id": 222, "et_date": "2026-05-27", "opp_team_id": 110,
             "sp_name": "Slow", "opp_abbr": "Y"},
            {"mlb_id": 333, "et_date": "2026-05-27", "opp_team_id": 111,
             "sp_name": "C", "opp_abbr": "Z"},
        ]
        result = deep_batch(players=players, fetchers={
            "gamelog": gamelog_fn, "meta": _ok_meta,
            "range": _ok_range, "split": _ok_split,
        })

        err = result["by_player"]["222"]["error"].lower()
        assert "timeout" in err
        # Others unaffected
        assert "game_log" in result["by_player"]["111"]
        assert "game_log" in result["by_player"]["333"]

    def test_comparison_table_delta_and_vs_hand_format(self):
        # 30d .702 → 7d .769 → +.067 ; vs hand .686 (R)
        def range_fn(team_id, end_date, days):
            return {"ops": {7: ".769", 14: ".720", 30: ".702"}[days]}

        def split_fn(team_id, hand):
            return {"ops": ".686", "pa": 1200, "hand": hand}

        result = deep_batch(
            players=[{"mlb_id": 686790, "et_date": "2026-05-27", "opp_team_id": 109,
                      "sp_name": "McDonald", "opp_abbr": "AZ",
                      "sum26": 40, "sum25": 46}],
            fetchers={"gamelog": _ok_gamelog, "meta": _ok_meta,
                      "range": range_fn, "split": split_fn},
        )

        row = result["comparison_table"]["rows"][0]
        # values order matches headers order
        assert row["values"][0] == ".769"           # 7d OPS
        assert row["values"][1] == "+.067"          # 30d→7d Δ
        assert row["values"][2] == ".686 (R)"       # vs hand OPS
        assert row["values"][5] == "40"             # Sum26
        assert row["values"][6] == "40/46"          # 雙年 prior

    def test_floor_risk_hint_high_when_two_collapses(self):
        # 2 collapses (ER>=4) in last 6 starts → "高"
        def gamelog_fn(mlb_id, season):
            return [
                {"date": "2026-04-01", "opp": "X", "h_a": "H", "ip": "5.0", "h": 6,
                 "r": 4, "er": 4, "bb": 2, "k": 5, "hr": 1, "pc": 90, "era": "6.00"},
                {"date": "2026-04-08", "opp": "Y", "h_a": "A", "ip": "6.0", "h": 5,
                 "r": 2, "er": 2, "bb": 2, "k": 7, "hr": 0, "pc": 88, "era": "5.00"},
                {"date": "2026-04-15", "opp": "Z", "h_a": "H", "ip": "5.2", "h": 7,
                 "r": 5, "er": 5, "bb": 3, "k": 4, "hr": 2, "pc": 95, "era": "5.50"},
                {"date": "2026-04-22", "opp": "A", "h_a": "A", "ip": "6.0", "h": 5,
                 "r": 2, "er": 2, "bb": 2, "k": 6, "hr": 1, "pc": 90, "era": "4.80"},
                {"date": "2026-04-29", "opp": "B", "h_a": "H", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 85, "era": "4.60"},
                {"date": "2026-05-06", "opp": "C", "h_a": "A", "ip": "6.1", "h": 4,
                 "r": 2, "er": 2, "bb": 1, "k": 8, "hr": 0, "pc": 92, "era": "4.40"},
            ]

        result = deep_batch(
            players=[{"mlb_id": 686790, "et_date": "2026-05-27", "opp_team_id": 109,
                      "sp_name": "X", "opp_abbr": "Y"}],
            fetchers={"gamelog": gamelog_fn, "meta": _ok_meta,
                      "range": _ok_range, "split": _ok_split},
        )

        # Floor risk hint = column index 4
        assert result["comparison_table"]["rows"][0]["values"][4] == "高"

    def test_floor_risk_hint_mid_high_when_one_collapse_high_era(self):
        # 1 collapse + recent ERA >= 4.50 (4+3+3+3+3+3 = 19 ER / 30 IP = 5.70) → "中-高"
        def gamelog_fn(mlb_id, season):
            return [
                {"date": "2026-04-01", "opp": "X", "h_a": "H", "ip": "5.0", "h": 6,
                 "r": 4, "er": 4, "bb": 2, "k": 5, "hr": 1, "pc": 90, "era": "7.20"},
                {"date": "2026-04-08", "opp": "Y", "h_a": "A", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 88, "era": "6.30"},
                {"date": "2026-04-15", "opp": "Z", "h_a": "H", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 88, "era": "5.85"},
                {"date": "2026-04-22", "opp": "A", "h_a": "A", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 88, "era": "5.63"},
                {"date": "2026-04-29", "opp": "B", "h_a": "H", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 88, "era": "5.50"},
                {"date": "2026-05-06", "opp": "C", "h_a": "A", "ip": "5.0", "h": 5,
                 "r": 3, "er": 3, "bb": 2, "k": 5, "hr": 0, "pc": 88, "era": "5.40"},
            ]

        result = deep_batch(
            players=[{"mlb_id": 686790, "et_date": "2026-05-27", "opp_team_id": 109,
                      "sp_name": "X", "opp_abbr": "Y"}],
            fetchers={"gamelog": gamelog_fn, "meta": _ok_meta,
                      "range": _ok_range, "split": _ok_split},
        )

        # Floor risk hint = column index 4 ; recent ERA = 19*9/30 = 5.70
        assert result["comparison_table"]["rows"][0]["values"][4] == "中-高"
        # And recent ERA cell (column 3) = "5.70"
        assert result["comparison_table"]["rows"][0]["values"][3] == "5.70"
