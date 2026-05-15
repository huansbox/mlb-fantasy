"""TDD tests for mlb_query.py — gamelog_with_qs + opponent_context helpers."""

import pytest

from mlb_query import gamelog_with_qs, is_quality_start, opponent_context, parse_ip


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
