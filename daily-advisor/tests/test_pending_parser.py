"""TDD tests for pending_parser.py — markdown H2 section parser for stream-sp-pending.md."""

from pathlib import Path

from pending_parser import parse_pending


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
        assert evals == [{"name": "Griffin Canning", "team": "SD", "is_home": True}]

    def test_single_eval_row_away(self):
        text = self._wrap(
            "| Jason Alexander | HOU away | TEX (.740) | — | 21/12 | foo | ❌ 不推 | reason |\n"
        )
        evals = parse_pending(text)["2026-05-26"]["evaluations"]
        assert evals == [{"name": "Jason Alexander", "team": "HOU", "is_home": False}]

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
        assert evals == [{"name": "Two Cells", "team": "NYY", "is_home": True}]


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
        assert out["evaluations"] == [{"name": "Real SP", "team": "NYY", "is_home": True}]


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
        assert out["2026-05-26"]["evaluations"] == [{"name": "Alpha", "team": "NYY", "is_home": True}]
        assert out["2026-05-26"]["tbd_games"] == []
        assert out["2026-05-27"]["evaluations"] == [{"name": "Beta", "team": "LAD", "is_home": False}]
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
