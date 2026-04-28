"""Unit tests for waiver-log position lookup (batter v4 thin follow-up).

Covers fa_scan._build_position_lookup — the helper that fills the position
field for batter v4 thin NEW rows where the LLM is instructed to leave it
blank (per docs/batter-framework-upgrade-design.md §1.2 + §3.4).
"""

from fa_scan import _build_position_lookup


def _config(batter_specs=None):
    return {"batters": batter_specs or []}


class TestBuildPositionLookup:
    def test_returns_none_for_sp_group(self):
        assert _build_position_lookup("sp", [], [], _config()) is None

    def test_returns_none_for_rp_group(self):
        assert _build_position_lookup("rp", [], [], _config()) is None

    def test_batter_collects_from_roster_config(self):
        config = _config([
            {"name": "Albies", "positions": ["2B"]},
            {"name": "Stanton", "positions": ["LF", "RF"]},
        ])
        lookup = _build_position_lookup("batter", [], [], config)
        assert lookup == {"Albies": "2B", "Stanton": "LF/RF"}

    def test_batter_collects_from_fa_candidates(self):
        fa = [{"name": "Cole Young", "position": "2B"},
              {"name": "Heliot Ramos", "position": "LF/CF/RF"}]
        lookup = _build_position_lookup("batter", fa, [], _config())
        assert lookup["Cole Young"] == "2B"
        assert lookup["Heliot Ramos"] == "LF/CF/RF"

    def test_batter_collects_from_watch_candidates(self):
        watch = [{"name": "Cam Smith", "position": "RF"}]
        lookup = _build_position_lookup("batter", [], watch, _config())
        assert lookup["Cam Smith"] == "RF"

    def test_yahoo_overrides_roster_config(self):
        # Yahoo FA list represents current state; if a player surfaces in
        # both sources we trust Yahoo.
        config = _config([{"name": "Albies", "positions": ["2B"]}])
        fa = [{"name": "Albies", "position": "2B/SS"}]  # hypothetical multi-pos
        lookup = _build_position_lookup("batter", fa, [], config)
        assert lookup["Albies"] == "2B/SS"

    def test_skips_entries_missing_name_or_position(self):
        config = _config([
            {"name": "Has Pos", "positions": ["1B"]},
            {"name": "No Pos", "positions": []},
            {"positions": ["3B"]},  # no name
        ])
        fa = [
            {"name": "FA No Pos", "position": ""},
            {"position": "OF"},  # no name
        ]
        lookup = _build_position_lookup("batter", fa, [], config)
        assert lookup == {"Has Pos": "1B"}

    def test_handles_empty_inputs(self):
        assert _build_position_lookup("batter", [], [], _config()) == {}

    def test_handles_none_inputs(self):
        # Defensive: caller may pass None for optional list fields.
        assert _build_position_lookup("batter", None, None, {}) == {}
