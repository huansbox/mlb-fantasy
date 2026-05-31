"""Unit tests for roster_sync helpers."""
from unittest.mock import patch

from roster_sync import (
    _count_missing_fields,
    classify_empty_diff,
    search_mlb_id,
)


# ── classify_empty_diff: watermark-advance bug guard ──
#
# When new transactions exist but the roster diff is empty, decide whether the
# watermark may advance. Guards the documented bug (5/8 May→Lambert) where a
# Yahoo add/drop visible in the transaction log but not yet reflected in the
# roster snapshot got its watermark advanced and was permanently skipped.

NOW = 1_000_000
LAG = 7200  # 2h default mirror of MAX_ROSTER_LAG_SECONDS


def _tx(ts, *actions):
    """Build a transaction dict with given player actions."""
    return {"timestamp": ts, "type": "add/drop",
            "players": [{"name": f"P{i}", "action": a} for i, a in enumerate(actions)]}


def test_classify_addrop_within_lag_window_retries():
    """add/drop tx seen seconds ago but not reflected → retry (don't advance)."""
    txns = [_tx(NOW - 60, "add")]
    assert classify_empty_diff(txns, NOW, LAG) == "retry"


def test_classify_addrop_past_lag_window_alerts():
    """add/drop tx unreflected beyond the lag window → give up + alert."""
    txns = [_tx(NOW - LAG - 1, "add")]
    assert classify_empty_diff(txns, NOW, LAG) == "advance_alert"


def test_classify_addrop_at_exact_boundary_still_retries():
    """now - oldest == max_lag is NOT past the window (strict >), so retry."""
    txns = [_tx(NOW - LAG, "drop")]
    assert classify_empty_diff(txns, NOW, LAG) == "retry"


def test_classify_no_addrop_action_advances():
    """A transaction with no add/drop player action has no roster impact."""
    txns = [_tx(NOW - 60, "trade")]
    assert classify_empty_diff(txns, NOW, LAG) == "advance"


def test_classify_empty_players_advances():
    """No players at all → nothing to reflect → advance."""
    txns = [{"timestamp": NOW - 60, "type": "commish", "players": []}]
    assert classify_empty_diff(txns, NOW, LAG) == "advance"


def test_classify_action_case_insensitive():
    """Yahoo action casing must not defeat the add/drop detection."""
    txns = [_tx(NOW - 60, "Add")]
    assert classify_empty_diff(txns, NOW, LAG) == "retry"
    txns = [_tx(NOW - 60, "DROP")]
    assert classify_empty_diff(txns, NOW, LAG) == "retry"


def test_classify_uses_oldest_unreflected_tx():
    """With multiple txns, the OLDEST add/drop drives the lag decision."""
    # newest is recent, oldest is past the window → past window wins (alert)
    txns = [_tx(NOW - 30, "add"), _tx(NOW - LAG - 100, "drop")]
    assert classify_empty_diff(txns, NOW, LAG) == "advance_alert"


def test_classify_missing_action_key_treated_as_no_impact():
    """A player dict without an 'action' key must not crash; counts as no impact."""
    txns = [{"timestamp": NOW - 60, "type": "add/drop",
             "players": [{"name": "X"}]}]
    assert classify_empty_diff(txns, NOW, LAG) == "advance"


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
