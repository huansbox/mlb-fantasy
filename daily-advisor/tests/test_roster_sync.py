"""Unit tests for roster_sync helpers."""
from unittest.mock import patch

from roster_sync import _count_missing_fields, search_mlb_id


def test_count_missing_fields_all_complete():
    """No missing fields when every player has all keys backfilled."""
    config = {
        "batters": [
            {
                "name": "Foo",
                "mlb_id": "1",
                "yahoo_player_key": "k1",
                "prior_stats": {"avg": 0.3},
                "selected_pos": "C",
                "status": "",
            },
        ],
        "pitchers": [
            {
                "name": "Bar",
                "mlb_id": "2",
                "yahoo_player_key": "k2",
                "prior_stats": {"era": 3.5},
                "selected_pos": "BN",
                "status": "IL10",
            },
        ],
    }
    missing = _count_missing_fields(config)
    assert missing == {
        "yahoo_player_key": 0,
        "prior_stats": 0,
        "selected_pos": 0,
        "status": 0,
    }


def test_count_missing_fields_empty_string_is_valid_status():
    """status="" is a valid value (healthy player), not a missing field."""
    config = {
        "batters": [
            {
                "name": "Healthy",
                "mlb_id": "1",
                "yahoo_player_key": "k1",
                "prior_stats": {"avg": 0.3},
                "selected_pos": "C",
                "status": "",  # explicit empty = healthy
            },
        ],
        "pitchers": [],
    }
    missing = _count_missing_fields(config)
    assert missing["status"] == 0


def test_count_missing_fields_selected_pos_missing_key():
    """Missing selected_pos / status keys are detected for backfill."""
    config = {
        "batters": [
            {
                "name": "OldSchema",
                "mlb_id": "1",
                "yahoo_player_key": "k1",
                "prior_stats": {"avg": 0.3},
                # no selected_pos, no status (pre-schema-update entry)
            },
        ],
        "pitchers": [],
    }
    missing = _count_missing_fields(config)
    assert missing["selected_pos"] == 1
    assert missing["status"] == 1
    assert missing["yahoo_player_key"] == 0
    assert missing["prior_stats"] == 0


def test_count_missing_fields_yahoo_key_missing():
    """yahoo_player_key absent or empty string both count as missing."""
    config = {
        "batters": [
            {
                "name": "NoKey",
                "mlb_id": "1",
                "yahoo_player_key": "",  # falsy = missing
                "prior_stats": {"avg": 0.3},
                "selected_pos": "C",
                "status": "",
            },
            {
                "name": "AlsoNoKey",
                "mlb_id": "2",
                # yahoo_player_key absent entirely
                "prior_stats": {"avg": 0.3},
                "selected_pos": "C",
                "status": "",
            },
        ],
        "pitchers": [],
    }
    missing = _count_missing_fields(config)
    assert missing["yahoo_player_key"] == 2


def test_count_missing_fields_prior_stats_skipped_without_mlb_id():
    """A player without mlb_id can't be backfilled, so don't count it."""
    config = {
        "batters": [
            {
                "name": "NoMlbId",
                # no mlb_id
                "yahoo_player_key": "k1",
                # no prior_stats
                "selected_pos": "C",
                "status": "",
            },
        ],
        "pitchers": [],
    }
    missing = _count_missing_fields(config)
    assert missing["prior_stats"] == 0  # skipped because no mlb_id


def test_count_missing_fields_aggregates_across_sections():
    """Counts batters + pitchers together."""
    config = {
        "batters": [
            {"name": "B1", "mlb_id": "1", "yahoo_player_key": "k1",
             "prior_stats": {"x": 1}},  # missing selected_pos + status
        ],
        "pitchers": [
            {"name": "P1", "mlb_id": "2", "yahoo_player_key": "k2",
             "prior_stats": {"x": 1}},  # missing selected_pos + status
        ],
    }
    missing = _count_missing_fields(config)
    assert missing["selected_pos"] == 2
    assert missing["status"] == 2


@patch("roster_sync.mlb_api_get")
def test_search_mlb_id_strips_yahoo_two_way_pitcher_suffix(mock_get):
    """Yahoo splits two-way players into '<name> (Pitcher)' / '(Batter)'
    entities; search_mlb_id must strip the suffix to find the mlb_id."""
    mock_get.side_effect = [
        {"people": []},                       # first try with suffix fails
        {"people": [{"id": 547179}]},         # stripped name succeeds
    ]
    assert search_mlb_id("Michael Lorenzen (Pitcher)") == 547179
    assert mock_get.call_count == 2
    # Second call should query the stripped name
    second_url = mock_get.call_args_list[1][0][0]
    assert "Michael%20Lorenzen" in second_url
    assert "Pitcher" not in second_url


@patch("roster_sync.mlb_api_get")
def test_search_mlb_id_strips_yahoo_two_way_batter_suffix(mock_get):
    mock_get.side_effect = [
        {"people": []},
        {"people": [{"id": 660271}]},
    ]
    assert search_mlb_id("Shohei Ohtani (Batter)") == 660271


@patch("roster_sync.mlb_api_get")
def test_search_mlb_id_normal_name_no_extra_calls(mock_get):
    """No regression: names without parens still resolve in one API call."""
    mock_get.return_value = {"people": [{"id": 547179}]}
    assert search_mlb_id("Michael Lorenzen") == 547179
    assert mock_get.call_count == 1


@patch("roster_sync.mlb_api_get")
def test_search_mlb_id_returns_none_when_all_fallbacks_fail(mock_get):
    mock_get.return_value = {"people": []}
    assert search_mlb_id("Nonexistent Player (Pitcher)") is None
