"""Unit tests for FA batter candidate sort key (issue 036).

Presentation order is the LLM's attention prior, so it must use an external
market signal (%owned desc), not the system's own vs-P1 sum_diff. See
issues/036-fa-sort-key-debias.md.
"""

from fa_scan import _sort_fa_by_owned


def _names(entries):
    return [e["name"] for e in entries]


def test_orders_by_owned_descending():
    fa = [
        {"name": "Low", "pct": 5, "sum_diff": 99},
        {"name": "High", "pct": 60, "sum_diff": 0},
        {"name": "Mid", "pct": 30, "sum_diff": 50},
    ]
    assert _names(_sort_fa_by_owned(fa)) == ["High", "Mid", "Low"]


def test_sum_diff_does_not_influence_order():
    # P1-weak scenario: huge sum_diff on a barely-owned player must NOT
    # float it to the top.
    fa = [
        {"name": "Owned", "pct": 45, "sum_diff": 2},
        {"name": "Inflated", "pct": 1, "sum_diff": 40},
    ]
    assert _names(_sort_fa_by_owned(fa)) == ["Owned", "Inflated"]


def test_tie_break_by_name_ascending():
    fa = [
        {"name": "Zeb", "pct": 20, "sum_diff": 10},
        {"name": "Abe", "pct": 20, "sum_diff": 1},
        {"name": "Mac", "pct": 20, "sum_diff": 99},
    ]
    assert _names(_sort_fa_by_owned(fa)) == ["Abe", "Mac", "Zeb"]


def test_missing_pct_sorts_last():
    fa = [
        {"name": "NoPct", "sum_diff": 99},
        {"name": "NonePct", "pct": None, "sum_diff": 50},
        {"name": "HasPct", "pct": 3, "sum_diff": 0},
    ]
    # HasPct (even at 3%) precedes both pct-less entries; pct-less broken by name.
    assert _names(_sort_fa_by_owned(fa)) == ["HasPct", "NoPct", "NonePct"]


def test_zero_pct_treated_as_real_value_not_missing():
    fa = [
        {"name": "Missing"},
        {"name": "Zero", "pct": 0},
    ]
    # pct=0 is a real market value → ahead of a missing pct.
    assert _names(_sort_fa_by_owned(fa)) == ["Zero", "Missing"]


def test_float_pct_supported():
    fa = [
        {"name": "A", "pct": 12.5},
        {"name": "B", "pct": 12.4},
    ]
    assert _names(_sort_fa_by_owned(fa)) == ["A", "B"]


def test_empty_input():
    assert _sort_fa_by_owned([]) == []


def test_does_not_mutate_input():
    fa = [
        {"name": "B", "pct": 10},
        {"name": "A", "pct": 90},
    ]
    original = list(fa)
    _sort_fa_by_owned(fa)
    assert fa == original  # original list order untouched
