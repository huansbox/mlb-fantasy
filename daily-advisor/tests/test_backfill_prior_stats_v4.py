"""Unit tests for backfill_prior_stats_v4 helpers."""
from backfill_prior_stats_v4 import (
    V4_KEYS,
    collect_sp_ids,
    has_all_v4_keys,
)


def test_has_all_v4_keys_complete():
    prior = {"whiff_pct": 25.0, "gb_pct": 45.0, "xwobacon": 0.350,
             "xera": 3.5, "era": 3.2}
    assert has_all_v4_keys(prior) is True


def test_has_all_v4_keys_missing_one():
    prior = {"whiff_pct": 25.0, "gb_pct": 45.0,  # xwobacon missing
             "xera": 3.5}
    assert has_all_v4_keys(prior) is False


def test_has_all_v4_keys_none_values_count_as_present():
    """Once a key is in the dict (even None), backfill skips it."""
    prior = {"whiff_pct": None, "gb_pct": None, "xwobacon": None}
    assert has_all_v4_keys(prior) is True


def test_has_all_v4_keys_handles_empty_dict():
    assert has_all_v4_keys({}) is False


def test_has_all_v4_keys_handles_non_dict():
    assert has_all_v4_keys(None) is False


def test_collect_sp_ids_picks_sp_missing_v4():
    config = {
        "pitchers": [
            {
                "name": "OldSP",
                "mlb_id": 100,
                "positions": ["SP"],
                "prior_stats": {"xera": 3.5},  # no v4 keys
            },
            {
                "name": "NewSP",
                "mlb_id": 101,
                "positions": ["SP"],
                "prior_stats": {
                    "xera": 3.0,
                    "whiff_pct": 25.0,
                    "gb_pct": 45.0,
                    "xwobacon": 0.350,
                },  # all v4 keys present, skip
            },
        ],
    }
    todo = collect_sp_ids(config)
    assert len(todo) == 1
    assert todo[0]["name"] == "OldSP"
    assert todo[0]["mlb_id"] == 100


def test_collect_sp_ids_skips_pure_rp():
    config = {
        "pitchers": [
            {
                "name": "Closer",
                "mlb_id": 200,
                "positions": ["RP"],  # not SP, skip
                "prior_stats": {"xera": 2.5},
            },
        ],
    }
    assert collect_sp_ids(config) == []


def test_collect_sp_ids_picks_swingman():
    """SP+RP eligible (swingman) is treated as SP for v4."""
    config = {
        "pitchers": [
            {
                "name": "Swingman",
                "mlb_id": 300,
                "positions": ["SP", "RP"],
                "prior_stats": {"xera": 3.5},
            },
        ],
    }
    todo = collect_sp_ids(config)
    assert len(todo) == 1
    assert todo[0]["name"] == "Swingman"


def test_collect_sp_ids_skips_no_mlb_id():
    config = {
        "pitchers": [
            {
                "name": "Mystery",
                "positions": ["SP"],
                "prior_stats": {},
                # no mlb_id
            },
        ],
    }
    assert collect_sp_ids(config) == []


def test_collect_sp_ids_handles_no_prior_stats():
    config = {
        "pitchers": [
            {
                "name": "RawAdd",
                "mlb_id": 400,
                "positions": ["SP"],
                # no prior_stats key at all
            },
        ],
    }
    todo = collect_sp_ids(config)
    assert len(todo) == 1
    assert todo[0]["name"] == "RawAdd"


def test_v4_keys_constant_matches_design():
    """Lock the three v4 metrics in this constant; if framework changes, update."""
    assert V4_KEYS == ("whiff_pct", "gb_pct", "xwobacon")
