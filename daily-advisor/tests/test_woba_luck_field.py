"""Unit tests for issue 035 — batter wOBA−xwOBA luck field in payload.

Covers:
    - roster_sync._extract_savant_row picks up actual woba from the
      expected_statistics CSV (alongside est_woba)
    - season luck field on the Season 2026 line (BBE ≥40 gate, 顯著 marker
      at |gap| ≥ 0.023 = 2025 |gap| P70)
    - 14d luck field on the 14d Savant line (line's own BBE ≥15 gate)

Threshold derivation: calc_woba_gap_pctiles.py (2025, bip ≥ 50, n=486).
"""

from fa_scan import _fmt_14d_savant_line, _fmt_fa_block_batter_v4
from roster_sync import _extract_savant_row


# ── _extract_savant_row woba extraction ──


class TestExtractSavantRowWoba:
    def test_expected_csv_row_yields_woba_and_xwoba(self):
        row = {"est_woba": "0.345", "woba": "0.310", "pa": "520"}
        out = _extract_savant_row(row, "batter")
        assert out["xwoba"] == 0.345
        assert out["woba"] == 0.310

    def test_statcast_csv_row_has_no_woba(self):
        # statcast leaderboard CSV (ev95percent block) carries no woba column
        row = {"ev95percent": "42.0", "brl_percent": "9.0", "attempts": "60"}
        out = _extract_savant_row(row, "batter")
        assert "woba" not in out

    def test_empty_woba_cell_stays_absent(self):
        row = {"est_woba": "0.345", "woba": "", "pa": "520"}
        out = _extract_savant_row(row, "batter")
        assert out.get("woba") is None


# ── payload rendering ──


def _entry(savant_2026=None, rolling_14d=None):
    return {
        "name": "Test FA",
        "mlb_id": 123456,
        "team": "ATL",
        "pct": 10,
        "status": "",
        "savant_2026": savant_2026 or {},
        "prior_stats": {},
        "derived": {"pa_per_tg": 3.8},
        "rolling_14d": rolling_14d or {},
        "add_tags": [],
        "warn_tags": [],
    }


def _season_line(lines):
    return next(l for l in lines if "Season 2026" in l)


class TestSeasonLuckField:
    def test_significant_positive_gap_marked(self):
        sv = {"xwoba": 0.300, "woba": 0.346, "bb_pct": 8.0, "barrel_pct": 9.0,
              "hh_pct": 42.0, "bbe": 60}
        line = _season_line(_fmt_fa_block_batter_v4(_entry(sv), 1, None, None))
        assert "運氣 +0.046" in line
        assert "顯著" in line

    def test_significant_negative_gap_marked(self):
        # Albies-type: actual under expected → buy-low direction
        sv = {"xwoba": 0.330, "woba": 0.290, "bb_pct": 8.0, "barrel_pct": 9.0,
              "hh_pct": 42.0, "bbe": 60}
        line = _season_line(_fmt_fa_block_batter_v4(_entry(sv), 1, None, None))
        assert "運氣 -0.040" in line
        assert "顯著" in line

    def test_small_gap_unmarked(self):
        sv = {"xwoba": 0.320, "woba": 0.330, "bb_pct": 8.0, "barrel_pct": 9.0,
              "hh_pct": 42.0, "bbe": 60}
        line = _season_line(_fmt_fa_block_batter_v4(_entry(sv), 1, None, None))
        assert "運氣 +0.010" in line
        assert "顯著" not in line

    def test_low_bbe_suppresses_luck(self):
        sv = {"xwoba": 0.300, "woba": 0.380, "bb_pct": 8.0, "barrel_pct": 9.0,
              "hh_pct": 42.0, "bbe": 30}  # < 40 floor
        line = _season_line(_fmt_fa_block_batter_v4(_entry(sv), 1, None, None))
        assert "運氣" not in line

    def test_missing_woba_suppresses_luck(self):
        sv = {"xwoba": 0.300, "bb_pct": 8.0, "barrel_pct": 9.0,
              "hh_pct": 42.0, "bbe": 60}
        line = _season_line(_fmt_fa_block_batter_v4(_entry(sv), 1, None, None))
        assert "運氣" not in line


class TestRolling14dLuckField:
    def test_gap_printed_when_rolling_woba_present(self):
        line = _fmt_14d_savant_line(
            {"xwoba": 0.350, "woba": 0.410, "bbe": 22}, 0.300, "   ")
        assert "運氣 +0.060" in line
        # season-derived 顯著 threshold not comparable on 14d noise — no marker
        assert "顯著" not in line

    def test_no_gap_without_rolling_woba(self):
        line = _fmt_14d_savant_line({"xwoba": 0.350, "bbe": 22}, 0.300, "   ")
        assert "運氣" not in line
        assert "xwOBA 0.350" in line  # line itself unchanged

    def test_low_bbe_line_already_gated(self):
        # below the line's own floor (15) → 樣本不足, no luck either
        line = _fmt_14d_savant_line(
            {"xwoba": 0.350, "woba": 0.500, "bbe": 10}, 0.300, "   ")
        assert "樣本不足" in line
        assert "運氣" not in line
