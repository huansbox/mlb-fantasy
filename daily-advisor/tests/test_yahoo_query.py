"""Tests for yahoo_query.query_fa() importable helper.

Mocks `_fetch_fa_page` so we don't hit Yahoo API. Verifies paging /
filter / early-stop semantics of the paging wrapper.
"""

from unittest.mock import patch

import pytest

import yahoo_query


def _player(name, pct=None):
    """Build a minimal extract_player_info-shaped dict for tests."""
    return {
        "name": name,
        "team": "XXX",
        "position": "SP",
        "status": "",
        "percent_owned": pct,
        "player_key": f"key_{name}",
        "ownership_type": "",
        "waiver_date": "",
        "stats": {},
    }


def _make_fetch_page(pages):
    """Build a fake _fetch_fa_page closure that returns ``pages[i]`` for the
    i-th call (start = i * page_size). Beyond len(pages) returns empty list."""
    calls = []

    def fake(start, **kwargs):
        calls.append({"start": start, **kwargs})
        idx = start // kwargs.get("page_size", 25)
        if idx < len(pages):
            return pages[idx]
        return []

    fake.calls = calls
    return fake


class TestQueryFaSinglePage:
    def test_default_single_page_no_auto_page(self):
        """Without --names or --auto-page, returns just one page (cmd_fa legacy)."""
        page0 = [_player(f"P{i}") for i in range(25)]
        fake = _make_fetch_page([page0, []])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                position="SP", status="A",
            )

        assert len(out) == 25
        assert len(fake.calls) == 1
        assert fake.calls[0]["start"] == 0


class TestQueryFaAutoPage:
    def test_auto_page_until_empty(self):
        """auto_page=True loops through pages until empty page hits."""
        page0 = [_player(f"A{i}") for i in range(25)]
        page1 = [_player(f"B{i}") for i in range(10)]  # partial → stops next
        fake = _make_fetch_page([page0, page1, []])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                auto_page=True,
            )

        assert len(out) == 35
        # Partial last page (<page_size) means caller can stop — but
        # implementation may also keep fetching once more to confirm empty.
        # Either is acceptable; just verify it stops before max_pages.
        assert len(fake.calls) <= 3

    def test_auto_page_respects_max_pages_cap(self):
        """If every page is full, max_pages caps the loop."""
        full = [_player(f"X{i}") for i in range(25)]
        fake = _make_fetch_page([full] * 20)  # plenty of full pages

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                auto_page=True, max_pages=3,
            )

        assert len(fake.calls) == 3
        assert len(out) == 75


class TestQueryFaNamesFilter:
    def test_names_filter_returns_only_hits(self):
        """names={...} returns only matching players, drops the rest."""
        page0 = [_player("Sean Burke"), _player("Other1"), _player("Other2")]
        fake = _make_fetch_page([page0, []])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                names={"Sean Burke"},
            )

        assert len(out) == 1
        assert out[0]["name"] == "Sean Burke"

    def test_names_implies_auto_page(self):
        """Passing names should auto-page through until all hits found."""
        page0 = [_player(f"X{i}") for i in range(25)]
        page1 = [_player("Target"), _player("Z1")]
        fake = _make_fetch_page([page0, page1, []])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                names={"Target"},
            )

        # Should have fetched both pages
        assert len(fake.calls) >= 2
        assert len(out) == 1
        assert out[0]["name"] == "Target"

    def test_names_early_stop_when_all_found(self):
        """Once all wanted names are collected, stop paging early."""
        page0 = [_player("A"), _player("B"), _player("noise")]
        page1 = [_player("more_noise")]  # never reached
        fake = _make_fetch_page([page0, page1])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                names={"A", "B"},
            )

        assert len(fake.calls) == 1  # early-stop after page 0
        assert {p["name"] for p in out} == {"A", "B"}

    def test_names_with_no_match_still_returns_empty(self):
        """Searching for names that don't exist returns [] without crash."""
        page0 = [_player(f"X{i}") for i in range(25)]
        fake = _make_fetch_page([page0, []])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            out = yahoo_query.query_fa(
                access_token="t", league_key="lk",
                names={"Nonexistent Pitcher"},
                max_pages=2,
            )

        assert out == []


class TestQueryFaPassthrough:
    def test_position_status_sort_passed_to_fetch_page(self):
        """Filter args propagate to _fetch_fa_page kwargs."""
        fake = _make_fetch_page([[]])

        with patch.object(yahoo_query, "_fetch_fa_page", fake):
            yahoo_query.query_fa(
                access_token="t", league_key="lk",
                position="SP", status="FA", sort="OR", sort_type="lastweek",
                page_size=10,
            )

        assert len(fake.calls) == 1
        c = fake.calls[0]
        assert c["position"] == "SP"
        assert c["status"] == "FA"
        assert c["sort"] == "OR"
        assert c["sort_type"] == "lastweek"
        assert c["page_size"] == 10
        assert c["league_key"] == "lk"
        assert c["access_token"] == "t"
