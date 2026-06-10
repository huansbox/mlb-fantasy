"""Unit tests for issue 033 — batter payload hygiene pack.

Covers:
    ① _check_player_ownership returns true %owned (no fabricated 0%)
    ② FA prior line carries PA + age (_fmt_fa_block_batter_v4 / _fetch_ages_bulk)
    ③ 14d Savant BBE floor gate (_fmt_14d_savant_line)
    pct=None renders as "?%" (honest unknown, not fake 0%)

Background: docs/fa-scan-batter-judgment-quality.md A1/A2/A5/A6.
"""

import pytest

import fa_scan
from fa_scan import (
    _check_player_ownership,
    _fetch_ages_bulk,
    _fmt_14d_savant_line,
    _fmt_fa_block_batter_v4,
    _SAVANT_14D_BBE_FLOOR,
)


# ── ③ 14d Savant BBE floor gate ──


class TestFmt14dSavantLine:
    def test_below_floor_prints_sample_warning_without_delta(self):
        line = _fmt_14d_savant_line({"xwoba": 0.420, "bbe": 1}, 0.300, "   ")
        assert "樣本不足" in line
        assert "BBE 1" in line
        assert "0.420" not in line  # noisy xwOBA suppressed
        assert "Δ" not in line.replace("Δ 不顯示", "")  # no delta value

    def test_at_floor_prints_normal_line(self):
        line = _fmt_14d_savant_line(
            {"xwoba": 0.350, "bbe": _SAVANT_14D_BBE_FLOOR}, 0.300, "   ")
        assert "樣本不足" not in line
        assert "xwOBA 0.350" in line
        assert f"BBE {_SAVANT_14D_BBE_FLOOR}" in line
        assert "Δ+0.050" in line

    def test_above_floor_prints_normal_line(self):
        line = _fmt_14d_savant_line({"xwoba": 0.280, "bbe": 40}, 0.300, "  ")
        assert "樣本不足" not in line
        assert "Δ-0.020" in line

    def test_no_rolling_xwoba_returns_none(self):
        assert _fmt_14d_savant_line({}, 0.300, "  ") is None
        assert _fmt_14d_savant_line(None, 0.300, "  ") is None

    def test_indent_prefix_respected(self):
        line = _fmt_14d_savant_line({"xwoba": 0.350, "bbe": 40}, 0.300, "  ")
        assert line.startswith("  14d Savant:")


# ── ② FA block prior PA + age / pct=None rendering ──


def _fa_entry(**overrides):
    entry = {
        "name": "Test FA",
        "mlb_id": 123456,
        "team": "HOU",
        "pct": 12,
        "status": "",
        "savant_2026": {"xwoba": 0.320, "bb_pct": 8.0, "barrel_pct": 9.0,
                        "hh_pct": 42.0, "bbe": 60},
        "prior_stats": {"xwoba": 0.310, "bb_pct": 7.5, "barrel_pct": 8.0,
                        "pa": 520},
        "derived": {"pa_per_tg": 3.8},
        "rolling_14d": {},
        "add_tags": [],
        "warn_tags": [],
    }
    entry.update(overrides)
    return entry


class TestFaBlockPriorPaAge:
    def test_prior_line_has_pa_and_age(self):
        lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None, age=24)
        prior_line = next(l for l in lines if "Prior 2025" in l)
        assert "PA 520" in prior_line
        assert "年齡 24" in prior_line

    def test_prior_line_without_age_omits_age(self):
        lines = _fmt_fa_block_batter_v4(_fa_entry(), 1, None, None)
        prior_line = next(l for l in lines if "Prior 2025" in l)
        assert "PA 520" in prior_line
        assert "年齡" not in prior_line

    def test_no_prior_still_carries_age(self):
        lines = _fmt_fa_block_batter_v4(
            _fa_entry(prior_stats={}), 1, None, None, age=22)
        prior_line = next(l for l in lines if "Prior 2025" in l)
        assert "無資料" in prior_line
        assert "年齡 22" in prior_line

    def test_prior_without_pa_omits_pa(self):
        entry = _fa_entry(prior_stats={"xwoba": 0.310, "bb_pct": 7.5,
                                       "barrel_pct": 8.0, "pa": None})
        lines = _fmt_fa_block_batter_v4(entry, 1, None, None)
        prior_line = next(l for l in lines if "Prior 2025" in l)
        assert "PA" not in prior_line

    def test_pct_none_renders_unknown_not_zero(self):
        lines = _fmt_fa_block_batter_v4(_fa_entry(pct=None), None, None, None)
        header = lines[0]
        assert "?%" in header
        assert "0%" not in header

    def test_low_bbe_rolling_marked_in_block(self):
        entry = _fa_entry(rolling_14d={"xwoba": 0.450, "bbe": 3})
        lines = _fmt_fa_block_batter_v4(entry, 1, None, None)
        savant_line = next(l for l in lines if "14d Savant" in l)
        assert "樣本不足" in savant_line


# ── ② _fetch_ages_bulk ──


class TestFetchAgesBulk:
    def test_bulk_fetch_maps_ids_to_age(self, monkeypatch):
        captured = {}

        def fake_api(path):
            captured["path"] = path
            return {"people": [
                {"id": 650333, "currentAge": 29},
                {"id": 596019, "currentAge": 32},
            ]}

        monkeypatch.setattr(fa_scan, "mlb_api_get", fake_api)
        ages = _fetch_ages_bulk([{"mlb_id": 650333}, {"mlb_id": 596019}])
        assert ages == {"650333": 29, "596019": 32}
        assert "personIds=596019,650333" in captured["path"]  # sorted, one call

    def test_empty_players_no_api_call(self, monkeypatch):
        monkeypatch.setattr(
            fa_scan, "mlb_api_get",
            lambda path: pytest.fail("no players → must not call API"))
        assert _fetch_ages_bulk([]) == {}
        assert _fetch_ages_bulk([{"name": "no id"}]) == {}

    def test_api_error_returns_empty(self, monkeypatch):
        def boom(path):
            raise RuntimeError("network down")

        monkeypatch.setattr(fa_scan, "mlb_api_get", boom)
        assert _fetch_ages_bulk([{"mlb_id": 1}]) == {}

    def test_missing_age_skipped(self, monkeypatch):
        monkeypatch.setattr(
            fa_scan, "mlb_api_get",
            lambda path: {"people": [{"id": 1}, {"id": 2, "currentAge": 25}]})
        assert _fetch_ages_bulk([{"mlb_id": 1}, {"mlb_id": 2}]) == {"2": 25}


# ── ① _check_player_ownership true %owned ──


def _player_info_stub(name="Cam Smith", team="HOU", player_key="mlb.p.999",
                      percent_owned=None, ownership_type="freeagents",
                      status=""):
    """Build the minimal Yahoo nested player structure extract_player_info
    understands: [info_list, {percent_owned}, {ownership}]."""
    info = [
        {"name": {"full": name}},
        {"editorial_team_abbr": team},
        {"display_position": "3B"},
        {"player_key": player_key},
    ]
    if status:
        info.append({"status": status})
    blocks = [info]
    if percent_owned is not None:
        blocks.append({"percent_owned": [{"value": percent_owned}]})
    blocks.append({"ownership": {"ownership_type": ownership_type,
                                 "waiver_date": ""}})
    return blocks


class TestCheckPlayerOwnership:
    def _patch(self, monkeypatch, search_result, league_player):
        monkeypatch.setattr(
            fa_scan, "_search_players",
            lambda name, lk, tok: search_result)
        captured = {}

        def fake_api_get(path, tok):
            captured["path"] = path
            return {"fantasy_content": {"league": [
                {}, {"players": {"0": {"player": league_player}}},
            ]}}

        monkeypatch.setattr(fa_scan, "api_get", fake_api_get)
        return captured

    def test_returns_true_pct_and_ownership(self, monkeypatch):
        search = {"0": {"player": _player_info_stub()}, "count": 1}
        league_player = _player_info_stub(percent_owned="37",
                                          ownership_type="freeagents")
        captured = self._patch(monkeypatch, search, league_player)

        res = _check_player_ownership("Cam Smith", "458.l.1", "tok",
                                      expected_team="HOU")
        assert res == {"ownership_type": "freeagents", "pct": 37, "status": ""}
        # The request must ask for percent_owned (A1 fix: was out=ownership)
        assert "out=percent_owned,ownership" in captured["path"]

    def test_pct_none_when_yahoo_omits_percent_owned(self, monkeypatch):
        search = {"0": {"player": _player_info_stub()}, "count": 1}
        league_player = _player_info_stub(percent_owned=None)
        self._patch(monkeypatch, search, league_player)

        res = _check_player_ownership("Cam Smith", "458.l.1", "tok")
        assert res["pct"] is None  # unknown stays None, never fake 0

    def test_rostered_player_reports_team(self, monkeypatch):
        search = {"0": {"player": _player_info_stub()}, "count": 1}
        league_player = _player_info_stub(percent_owned="92",
                                          ownership_type="team")
        self._patch(monkeypatch, search, league_player)

        res = _check_player_ownership("Cam Smith", "458.l.1", "tok")
        assert res["ownership_type"] == "team"
        assert res["pct"] == 92

    def test_team_mismatch_returns_none(self, monkeypatch):
        search = {"0": {"player": _player_info_stub(team="LAD")}, "count": 1}
        self._patch(monkeypatch, search, _player_info_stub())

        res = _check_player_ownership("Max Muncy", "458.l.1", "tok",
                                      expected_team="ATH")
        assert res is None

    def test_no_search_result_returns_none(self, monkeypatch):
        monkeypatch.setattr(fa_scan, "_search_players",
                            lambda name, lk, tok: None)
        assert _check_player_ownership("Nobody", "458.l.1", "tok") is None
