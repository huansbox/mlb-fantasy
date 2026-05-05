"""Unit tests for fa_scan.py FA status filter (IL/NA hard filter)."""

import pytest

from fa_scan import is_inactive_fa


class TestIsInactiveFa:
    """Yahoo status filter: IL60 / NA → exclude; IL10/IL15/DTD/empty → keep.

    Rationale (handoff-il-na-filter.md): 2026-05-05 Mize (IL15) was recommended
    two days in a row. IL60/NA = ≥2 months unusable, hard exclude. IL10/IL15
    soft-tag in fa_compute layer; DTD/empty = healthy enough to evaluate.
    """

    @pytest.mark.parametrize("status", ["IL60", "NA"])
    def test_excluded_when_long_term_inactive(self, status):
        player = {"status": status}
        assert is_inactive_fa(player) is True

    @pytest.mark.parametrize("status", ["IL10", "IL15", "DTD", ""])
    def test_kept_when_short_term_or_healthy(self, status):
        player = {"status": status}
        assert is_inactive_fa(player) is False

    def test_kept_when_status_missing(self):
        assert is_inactive_fa({}) is False

    def test_kept_when_status_none(self):
        assert is_inactive_fa({"status": None}) is False

    def test_include_inactive_keeps_il60(self):
        # --include-inactive flag = stash mode, keep everything
        player = {"status": "IL60"}
        assert is_inactive_fa(player, include_inactive=True) is False

    def test_include_inactive_keeps_na(self):
        player = {"status": "NA"}
        assert is_inactive_fa(player, include_inactive=True) is False

    def test_status_lowercase_normalized(self):
        # Yahoo sometimes emits mixed case; treat consistently
        assert is_inactive_fa({"status": "il60"}) is True
        assert is_inactive_fa({"status": "na"}) is True

    def test_status_with_whitespace(self):
        assert is_inactive_fa({"status": " IL60 "}) is True
