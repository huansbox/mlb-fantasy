"""TDD tests for anchor_filter.py — pure function for SP B2 anchor removal."""

from anchor_filter import filter_anchors


# ── builders ──

def _player(name: str, **extra) -> dict:
    return {"name": name, **extra}


# ── tests ──

def test_empty_roster_returns_empty():
    assert filter_anchors([], ["Tarik Skubal"], ["Cole Ragans"]) == []


def test_both_anchor_lists_none_returns_roster_unchanged():
    roster = [_player("Tarik Skubal"), _player("Cole Ragans")]
    out = filter_anchors(roster, None, None)
    assert out == roster
    assert out is not roster  # new list, not aliased


def test_both_anchor_lists_empty_returns_roster_unchanged():
    roster = [_player("Tarik Skubal"), _player("Cole Ragans")]
    out = filter_anchors(roster, [], [])
    assert out == roster


def test_single_cant_cut_match_removes_that_player():
    roster = [
        _player("Tarik Skubal"),
        _player("Logan Webb"),
        _player("Jacob deGrom"),
    ]
    out = filter_anchors(roster, ["Tarik Skubal"], None)
    assert [p["name"] for p in out] == ["Logan Webb", "Jacob deGrom"]


def test_single_weekly_anchor_match_removes_that_player():
    roster = [
        _player("Tarik Skubal"),
        _player("Cole Ragans"),
        _player("Logan Webb"),
    ]
    out = filter_anchors(roster, None, ["Cole Ragans"])
    assert [p["name"] for p in out] == ["Tarik Skubal", "Logan Webb"]


def test_overlap_in_both_lists_removed_once():
    roster = [_player("Tarik Skubal"), _player("Logan Webb")]
    out = filter_anchors(roster, ["Tarik Skubal"], ["Tarik Skubal"])
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_case_insensitive_match():
    roster = [_player("Tarik Skubal"), _player("Logan Webb")]
    out = filter_anchors(roster, ["tarik skubal"], None)
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_accent_normalization():
    roster = [_player("Jesús Luzardo"), _player("Logan Webb")]
    out = filter_anchors(roster, ["Jesus Luzardo"], None)
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_accent_in_roster_anchor_no_accent():
    roster = [_player("José Quintana"), _player("Logan Webb")]
    out = filter_anchors(roster, None, ["Jose Quintana"])
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_apostrophe_curly_vs_straight_normalized():
    roster = [_player("Riley O’Brien"), _player("Logan Webb")]
    out = filter_anchors(roster, ["Riley O'Brien"], None)
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_apostrophe_straight_vs_curly_normalized():
    roster = [_player("Riley O'Brien"), _player("Logan Webb")]
    out = filter_anchors(roster, None, ["Riley O’Brien"])
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_order_preserved_for_non_anchors():
    roster = [
        _player("Logan Webb"),
        _player("Tarik Skubal"),
        _player("Jacob deGrom"),
        _player("Cole Ragans"),
        _player("Spencer Strider"),
    ]
    out = filter_anchors(roster, ["Tarik Skubal"], ["Cole Ragans"])
    assert [p["name"] for p in out] == ["Logan Webb", "Jacob deGrom", "Spencer Strider"]


def test_idempotent():
    roster = [_player("Tarik Skubal"), _player("Logan Webb"), _player("Cole Ragans")]
    once = filter_anchors(roster, ["Tarik Skubal"], ["Cole Ragans"])
    twice = filter_anchors(once, ["Tarik Skubal"], ["Cole Ragans"])
    assert once == twice


def test_anchor_name_not_in_roster_no_error():
    roster = [_player("Logan Webb"), _player("Jacob deGrom")]
    out = filter_anchors(roster, ["Tarik Skubal"], ["Cole Ragans"])
    assert [p["name"] for p in out] == ["Logan Webb", "Jacob deGrom"]


def test_mixed_case_accent_apostrophe_combination():
    roster = [
        _player("Jesús O’Brien"),
        _player("Logan Webb"),
    ]
    out = filter_anchors(roster, ["JESUS O'BRIEN"], None)
    assert [p["name"] for p in out] == ["Logan Webb"]


def test_player_extra_fields_preserved():
    roster = [
        _player("Tarik Skubal", team="DET", mlb_id=669373),
        _player("Logan Webb", team="SF", mlb_id=657277),
    ]
    out = filter_anchors(roster, ["Tarik Skubal"], None)
    assert out == [{"name": "Logan Webb", "team": "SF", "mlb_id": 657277}]
