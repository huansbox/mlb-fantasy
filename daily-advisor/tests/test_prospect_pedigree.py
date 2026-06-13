"""Unit tests for prospect_pedigree.py — issue 049 post-hype 新秀標記 engine.

Covers the durable runtime layer (load / stale detection / pedigree join /
post-hype predicate). The data asset itself (prospect_pedigree.json) is built
by build_prospect_json.py and not exercised here — these tests use synthetic
fixtures so they never touch the network or the on-disk JSON.
"""

import datetime as dt

import pytest

from prospect_pedigree import (
    DEFAULT_AGE_THRESHOLD,
    DEFAULT_RANK_THRESHOLD,
    Pedigree,
    PostHypeResult,
    default_weak_signal,
    evaluate_post_hype,
    is_stale,
    lookup,
    parse_pedigree,
    post_hype_tag,
)


def _raw(updated="2026-03-15", stale_after_month=3):
    """A minimal valid raw pedigree dict (string mlb_id keys, as JSON would have)."""
    return {
        "meta": {
            "updated": updated,
            "source": "MLB Pipeline preseason Top 100",
            "source_years": [2022, 2023, 2024, 2025, 2026],
            "stale_after_month": stale_after_month,
        },
        "prospects": {
            "669357": {"best_rank": 2, "best_rank_year": 2023, "name": "Jordan Walker"},
            "700000": {"best_rank": 55, "best_rank_year": 2024, "name": "Sample Guy"},
        },
    }


# ── parse_pedigree ──
class TestParsePedigree:
    def test_valid_parses_and_coerces_int_keys(self):
        ped = parse_pedigree(_raw())
        assert isinstance(ped, Pedigree)
        assert ped.updated_year == 2026
        assert ped.updated_date == "2026-03-15"
        assert ped.stale_after_month == 3
        # string keys coerced to int
        assert 669357 in ped.prospects
        assert "669357" not in ped.prospects
        assert ped.prospects[669357]["best_rank"] == 2

    def test_missing_meta_raises(self):
        with pytest.raises(ValueError):
            parse_pedigree({"prospects": {}})

    def test_missing_updated_raises(self):
        bad = _raw()
        del bad["meta"]["updated"]
        with pytest.raises(ValueError):
            parse_pedigree(bad)

    def test_missing_prospects_defaults_empty(self):
        raw = _raw()
        del raw["prospects"]
        ped = parse_pedigree(raw)
        assert ped.prospects == {}

    def test_stale_after_month_defaults_to_3_when_absent(self):
        raw = _raw()
        del raw["meta"]["stale_after_month"]
        ped = parse_pedigree(raw)
        assert ped.stale_after_month == 3


# ── is_stale ──
class TestIsStale:
    def _ped(self, updated="2026-03-15", sam=3):
        return parse_pedigree(_raw(updated=updated, stale_after_month=sam))

    def test_same_year_is_fresh(self):
        ped = self._ped("2026-03-15")
        assert is_stale(ped, dt.date(2026, 12, 31)) is False

    def test_future_updated_is_fresh(self):
        ped = self._ped("2027-03-15")
        assert is_stale(ped, dt.date(2026, 6, 1)) is False

    def test_one_year_behind_before_march_window_is_fresh(self):
        # updated 2026, now Feb 2027 — this year's March refresh window not yet missed
        ped = self._ped("2026-03-15")
        assert is_stale(ped, dt.date(2027, 2, 28)) is False

    def test_one_year_behind_at_window_month_is_fresh(self):
        # March itself (month == stale_after_month) is still within the window
        ped = self._ped("2026-03-15")
        assert is_stale(ped, dt.date(2027, 3, 31)) is False

    def test_one_year_behind_after_window_is_stale(self):
        # April 2027 with a 2026 list — missed the 2027 March refresh
        ped = self._ped("2026-03-15")
        assert is_stale(ped, dt.date(2027, 4, 1)) is True

    def test_two_years_behind_is_stale_regardless_of_month(self):
        ped = self._ped("2025-03-15")
        assert is_stale(ped, dt.date(2027, 1, 1)) is True

    def test_custom_stale_after_month_override(self):
        ped = self._ped("2026-03-15", sam=3)
        # override window to month 6 → April 2027 now still fresh
        assert is_stale(ped, dt.date(2027, 4, 1), stale_after_month=6) is False
        assert is_stale(ped, dt.date(2027, 7, 1), stale_after_month=6) is True


# ── lookup ──
class TestLookup:
    def test_hit_returns_record(self):
        ped = parse_pedigree(_raw())
        rec = lookup(ped, 669357)
        assert rec["best_rank"] == 2
        assert rec["best_rank_year"] == 2023

    def test_miss_returns_none(self):
        ped = parse_pedigree(_raw())
        assert lookup(ped, 111111) is None

    def test_string_id_input_works(self):
        ped = parse_pedigree(_raw())
        assert lookup(ped, "669357")["best_rank"] == 2

    def test_none_id_returns_none(self):
        ped = parse_pedigree(_raw())
        assert lookup(ped, None) is None


# ── default_weak_signal ──
class TestDefaultWeakSignal:
    def test_below_threshold_is_weak(self):
        assert default_weak_signal(14) is True

    def test_at_threshold_is_not_weak(self):
        assert default_weak_signal(20) is False

    def test_above_threshold_is_not_weak(self):
        assert default_weak_signal(27) is False

    def test_none_is_not_weak(self):
        # no fabricated signal on missing data
        assert default_weak_signal(None) is False

    def test_custom_threshold(self):
        assert default_weak_signal(22, threshold=25) is True


# ── evaluate_post_hype / post_hype_tag ──
FRESH = dt.date(2026, 6, 1)
STALE = dt.date(2028, 6, 1)  # 2 years past a 2026 list


class TestEvaluatePostHype:
    def _ped(self):
        return parse_pedigree(_raw())

    def test_all_gates_pass_fresh(self):
        r = evaluate_post_hype(self._ped(), 669357, age=23, weak_signal=True, today=FRESH)
        assert r.is_post_hype is True
        assert r.best_rank == 2
        assert r.best_rank_year == 2023
        assert r.stale is False
        assert r.reason  # non-empty explanation

    def test_pedigree_miss_not_post_hype(self):
        r = evaluate_post_hype(self._ped(), 111111, age=23, weak_signal=True, today=FRESH)
        assert r.is_post_hype is False
        assert r.best_rank is None

    def test_age_above_threshold_not_post_hype(self):
        r = evaluate_post_hype(self._ped(), 669357, age=30, weak_signal=True, today=FRESH)
        assert r.is_post_hype is False

    def test_age_none_not_post_hype(self):
        r = evaluate_post_hype(self._ped(), 669357, age=None, weak_signal=True, today=FRESH)
        assert r.is_post_hype is False

    def test_not_weak_not_post_hype(self):
        r = evaluate_post_hype(self._ped(), 669357, age=23, weak_signal=False, today=FRESH)
        assert r.is_post_hype is False

    def test_rank_threshold_param_excludes_low_pedigree(self):
        # Sample Guy ranked #55 — with a stricter top-30 threshold he no longer qualifies
        r = evaluate_post_hype(
            self._ped(), 700000, age=22, weak_signal=True, today=FRESH, rank_threshold=30
        )
        assert r.is_post_hype is False

    def test_age_at_threshold_inclusive(self):
        r = evaluate_post_hype(
            self._ped(), 669357, age=DEFAULT_AGE_THRESHOLD, weak_signal=True, today=FRESH
        )
        assert r.is_post_hype is True

    def test_stale_list_still_evaluates_but_flags(self):
        r = evaluate_post_hype(self._ped(), 669357, age=23, weak_signal=True, today=STALE)
        assert r.is_post_hype is True
        assert r.stale is True


class TestPostHypeTag:
    def _ped(self):
        return parse_pedigree(_raw())

    def test_fresh_fires_check_tag(self):
        tag = post_hype_tag(self._ped(), 669357, age=23, weak_signal=True, today=FRESH)
        assert tag == "✅ post-hype 新秀 (#2 2023)"

    def test_stale_fires_warn_tag(self):
        tag = post_hype_tag(self._ped(), 669357, age=23, weak_signal=True, today=STALE)
        assert tag == "⚠️ post-hype 名單過期 (#2 2023)"

    def test_no_fire_returns_none(self):
        assert post_hype_tag(self._ped(), 669357, age=30, weak_signal=True, today=FRESH) is None
        assert post_hype_tag(self._ped(), 111111, age=23, weak_signal=True, today=FRESH) is None
