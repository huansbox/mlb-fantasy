"""TDD tests for pending_parser.py — markdown H2 section parser for stream-sp-pending.md."""

from pathlib import Path

from pending_parser import parse_pending


def _ev(name, team, is_home, mlb_id=None, sum26=None, sum25=None, opp_abbr=None):
    """Full evaluation dict — schema contract for parse_pending output."""
    return {
        "name": name, "team": team, "is_home": is_home,
        "mlb_id": mlb_id, "sum26": sum26, "sum25": sum25, "opp_abbr": opp_abbr,
    }


class TestEmptyAndMalformed:
    def test_empty_string_returns_empty_dict(self):
        assert parse_pending("") == {}

    def test_no_h2_section_returns_empty_dict(self):
        text = "just some prose\n\n- and a bullet\n"
        assert parse_pending(text) == {}

    def test_h2_with_no_subsections_yields_empty_eval_and_tbd(self):
        text = "## ET 2026-05-30\n- recorded_at: 2026-05-29T13:00:00+08:00\n- last_recheck_at: —\n"
        out = parse_pending(text)
        assert out == {"2026-05-30": {"tbd_games": [], "evaluations": []}}

    def test_non_et_h2_is_ignored(self):
        # 別的 H2 標題（不是 `## ET YYYY-MM-DD`）不會建立 entry
        text = "## Some other section\n| Foo | Bar |\n"
        assert parse_pending(text) == {}


class TestEvalRowParsing:
    def _wrap(self, table_rows: str) -> str:
        return (
            "## ET 2026-05-26\n"
            "- recorded_at: 2026-05-25T13:01:00+08:00\n"
            "- last_recheck_at: —\n\n"
            "### 已評估\n"
            "| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot | Verdict | 理由 |\n"
            "|---|---|---|---|---|---|---|---|\n"
            f"{table_rows}"
        )

    def test_single_eval_row_home(self):
        text = self._wrap(
            "| Griffin Canning | SD home | PHI (.621) | 1% | 27/20 | <P25·**>P90**·<P25·**P80-90**·P50-60 | ❌ 不推 | because |\n"
        )
        out = parse_pending(text)
        evals = out["2026-05-26"]["evaluations"]
        assert evals == [_ev("Griffin Canning", "SD", True,
                             sum26=27, sum25=20, opp_abbr="PHI")]

    def test_single_eval_row_away(self):
        text = self._wrap(
            "| Jason Alexander | HOU away | TEX (.740) | — | 21/12 | foo | ❌ 不推 | reason |\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        assert evals == [_ev("Jason Alexander", "HOU", False,
                             sum26=21, sum25=12, opp_abbr="TEX")]

    def test_multiple_eval_rows_preserve_order(self):
        text = self._wrap(
            "| Griffin Canning | SD home | PHI | 1% | 27 | foo | ❌ | r1 |\n"
            "| Jason Alexander | HOU away | TEX | — | 21 | foo | ❌ | r2 |\n"
            "| Sean Burke | CWS home | MIN | 11% | 17 | foo | ❌ | r3 |\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        assert [e["name"] for e in evals] == ["Griffin Canning", "Jason Alexander", "Sean Burke"]
        assert [e["team"] for e in evals] == ["SD", "HOU", "CWS"]
        assert [e["is_home"] for e in evals] == [True, False, True]

    def test_header_and_separator_rows_skipped(self):
        # 純表格只有 header + separator，無 data row → eval 空
        text = (
            "## ET 2026-05-26\n\n"
            "### 已評估\n"
            "| SP | 隊 | 對手 | %own |\n"
            "|---|---|---|---|\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        assert evals == []

    def test_malformed_team_cell_skipped(self):
        # team cell 不是 "ABC home/away" 格式 → 該 row 跳過不 raise
        text = self._wrap(
            "| Good Guy | NYY home | OK | 5% | 20 | foo | ✅ | r1 |\n"
            "| Bad Guy | not-a-team | foo | 1% | 10 | foo | ❌ | r2 |\n"
            "| Other Good | LAD away | BAR | 2% | 15 | foo | ❌ | r3 |\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        assert [e["name"] for e in evals] == ["Good Guy", "Other Good"]

    def test_too_few_cells_skipped(self):
        # row 缺欄（只有 SP + 隊，沒其他欄）→ 仍能 parse name/team；如果只有 1 欄則跳過
        text = self._wrap(
            "| Just One |\n"
            "| Two Cells | NYY home |\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        # Two Cells 雖然 cells 數少但 name+team 都齊 → 應接受
        assert evals == [_ev("Two Cells", "NYY", True)]


class TestEvalRowNewSchema:
    """issue #406 — mlb_id / 近況 欄 + header-driven 欄位解析。"""

    _NEW_HEADER = (
        "| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 "
        "| 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | 近況 | Verdict | 一行理由 | mlb_id |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )

    def _wrap(self, table_rows: str) -> str:
        return (
            "## ET 2026-07-07\n"
            "- recorded_at: 2026-07-06T09:19:00+08:00\n\n"
            "### 已評估\n"
            f"{self._NEW_HEADER}"
            f"{table_rows}"
        )

    def test_new_format_row_extracts_all_fields(self):
        text = self._wrap(
            "| Trevor McDonald | SF home | TOR (.570 🟢 / vs RHP .701) | 5% | 29/46 "
            "| <P25·P25-40·P40-50·**>P90**·**>P90** | 4.50 / 2崩 / 高 | ⚠️ 條件推 | 理由 | 669952 |\n"
        )
        evals = parse_pending(text)["2026-07-07"]["evaluations"]
        assert evals == [_ev("Trevor McDonald", "SF", True,
                             mlb_id=669952, sum26=29, sum25=46, opp_abbr="TOR")]

    def test_mlb_id_cell_non_digit_yields_none(self):
        text = self._wrap(
            "| Old Row | SF home | TOR (.570) | 5% | 29/46 | foo | — | ⚠️ | 理由 | — |\n"
        )
        evals = parse_pending(text)["2026-07-07"]["evaluations"]
        assert evals[0]["mlb_id"] is None

    def test_sum_cell_partial_dash(self):
        text = self._wrap(
            "| Rookie Guy | SF home | TOR (.570) | 5% | -/25 | foo | — | ⚠️ | 理由 | 123456 |\n"
        )
        ev = parse_pending(text)["2026-07-07"]["evaluations"][0]
        assert ev["sum26"] is None
        assert ev["sum25"] == 25

    def test_projected_prefix_name_kept_raw(self):
        text = self._wrap(
            "| 🔮 MacKenzie Gore | WSH home | CHC (.700) | 9% | 30/33 | foo | — | ✅ (projected) | 理由 | 669022 |\n"
        )
        ev = parse_pending(text)["2026-07-07"]["evaluations"][0]
        assert ev["name"] == "🔮 MacKenzie Gore"
        assert ev["mlb_id"] == 669022

    def test_column_order_shuffled_still_resolves_by_header(self):
        # header-driven：欄序不同也解析正確
        text = (
            "## ET 2026-07-07\n\n"
            "### 已評估\n"
            "| mlb_id | SP | 隊 | Sum26/25 | 對手 (14d OPS) |\n"
            "|---|---|---|---|---|\n"
            "| 669952 | Trevor McDonald | SF home | 29/46 | TOR (.570) |\n"
        )
        evals = parse_pending(text)["2026-07-07"]["evaluations"]
        assert evals == [_ev("Trevor McDonald", "SF", True,
                             mlb_id=669952, sum26=29, sum25=46, opp_abbr="TOR")]


class TestTbdSectionParsing:
    def test_home_tbd_line(self):
        text = (
            "## ET 2026-05-26\n\n"
            "### TBD 場次（待補查）\n"
            "- MIA @ TOR (TOR home TBD)\n"
        )
        tbd = parse_pending(text)["2026-05-26"]["tbd_games"]
        assert tbd == [{"away": "MIA", "home": "TOR", "side": "home"}]

    def test_away_and_both_tbd_lines(self):
        text = (
            "## ET 2026-05-26\n\n"
            "### TBD 場次（待補查）\n"
            "- COL @ PHI (COL away TBD)\n"
            "- PHI @ PIT (both TBD)\n"
        )
        tbd = parse_pending(text)["2026-05-26"]["tbd_games"]
        assert tbd == [
            {"away": "COL", "home": "PHI", "side": "away"},
            {"away": "PHI", "home": "PIT", "side": "both"},
        ]

    def test_empty_tbd_marker_line_skipped(self):
        # 用戶手寫 "_（無 TBD）_" 標記 → 不是 - bullet，安全 skip
        text = (
            "## ET 2026-05-26\n\n"
            "### TBD 場次（待補查）\n"
            "_（無 TBD）_\n"
        )
        tbd = parse_pending(text)["2026-05-26"]["tbd_games"]
        assert tbd == []


class TestSectionDispatch:
    def test_note_section_bullets_not_parsed_as_tbd_or_eval(self):
        # 備註段的 `- ` bullet 不會誤抓進 tbd_games / evaluations
        text = (
            "## ET 2026-05-26\n\n"
            "### TBD 場次（待補查）\n"
            "- CIN @ NYM (NYM home TBD)\n\n"
            "### 已評估\n"
            "| SP | 隊 | 對手 | %own |\n"
            "|---|---|---|---|\n"
            "| Real SP | NYY home | BOS | 5% |\n\n"
            "### 備註\n"
            "- 2026-05-26 07:00 首次評估\n"
            "- 排序：Real SP > others\n"
            "- _（free-form 區）_\n"
        )
        out = parse_pending(text)["2026-05-26"]
        assert out["tbd_games"] == [{"away": "CIN", "home": "NYM", "side": "home"}]
        assert out["evaluations"] == [_ev("Real SP", "NYY", True, opp_abbr="BOS")]


class TestMultipleDates:
    def test_multiple_et_dates_isolated(self):
        text = (
            "## ET 2026-05-26\n\n"
            "### 已評估\n"
            "| SP | 隊 | 對手 |\n"
            "|---|---|---|\n"
            "| Alpha | NYY home | BOS |\n\n"
            "## ET 2026-05-27\n\n"
            "### TBD 場次（待補查）\n"
            "- LAD @ SF (SF home TBD)\n\n"
            "### 已評估\n"
            "| SP | 隊 | 對手 |\n"
            "|---|---|---|\n"
            "| Beta | LAD away | SF |\n"
        )
        out = parse_pending(text)
        assert set(out.keys()) == {"2026-05-26", "2026-05-27"}
        assert out["2026-05-26"]["evaluations"] == [_ev("Alpha", "NYY", True, opp_abbr="BOS")]
        assert out["2026-05-26"]["tbd_games"] == []
        assert out["2026-05-27"]["evaluations"] == [_ev("Beta", "LAD", False, opp_abbr="SF")]
        assert out["2026-05-27"]["tbd_games"] == [{"away": "LAD", "home": "SF", "side": "home"}]


class TestFixtureRegression:
    def test_real_pending_file_parses_5_26_evaluations(self):
        # 真實 production 檔凍結版（git f1de52f 的 stream-sp-pending.md）。
        # 原本直接讀活檔，但 /stream-sp 過期清理會刪掉舊 ET section →
        # 測試隨時間漂移 fail（2026-06-10 修正：凍結進 fixtures/）。
        fixture = (Path(__file__).resolve().parent / "fixtures"
                   / "stream_sp_pending_2026-05-26.md")
        out = parse_pending(fixture.read_text(encoding="utf-8"))
        # ET 5/26 應該有 Canning / Alexander / Burke / Freeland 4 位
        d = out.get("2026-05-26", {})
        names = {e["name"] for e in d.get("evaluations", [])}
        assert {"Griffin Canning", "Jason Alexander", "Sean Burke", "Kyle Freeland"} <= names
        # ET 5/26 TBD 應有 MIA@TOR + CIN@NYM
        tbd_pairs = {(t["away"], t["home"]) for t in d.get("tbd_games", [])}
        assert ("MIA", "TOR") in tbd_pairs
        assert ("CIN", "NYM") in tbd_pairs
