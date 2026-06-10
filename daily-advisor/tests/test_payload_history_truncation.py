"""Unit tests for issue 032 — payload read-side history truncation +
derived counter summary lines.

Covers:
    truncate_entry_history — trigger/[eval]/last-5 kept, runs of omitted day
        lines collapse to one（中略 N 行）marker; ≤5-day and no-day entries
        pass through unchanged
    compute_history_counters — latest `day X/N` token quoted only from the
        recent window (stale tokens suppressed); trailing 建議結案 streak
        counted from FULL history
    truncate_watch_history — orchestration (counters before truncation),
        coexistence with the 028 replace-streak line, measurable size drop
        on the real snapshot

Fixture iron rule: the real waiver-log.md snapshot
(tests/fixtures/waiver_log_2026-06-10.md). Generated history lines go through
apply_waiver_log_block (the production writer) — never hand-written.

waiver-log.md itself is untouched by design: these are pure read-side
functions on the payload assembly path; no test (and no production caller)
writes the file.
"""

import re
from pathlib import Path

import pytest

from fa_scan import (
    _filter_waiver_log_by_group,
    apply_waiver_log_block,
    compute_history_counters,
    inject_replace_streaks,
    truncate_entry_history,
    truncate_watch_history,
    TRUNCATE_KEEP_RECENT,
)

FIXTURES = Path(__file__).parent / "fixtures"

_DAY_RE = re.compile(r"^- (?:\d{4}-)?\d{2}-\d{2}：", re.MULTILINE)


@pytest.fixture()
def snapshot():
    return (FIXTURES / "waiver_log_2026-06-10.md").read_text(encoding="utf-8")


@pytest.fixture()
def watch_section(snapshot):
    # Same slicing as the production call site (觀察中 → 已結案, which
    # deliberately includes 隊上觀察), then the batter group filter.
    section = snapshot.split("## 觀察中")[1].split("## 已結案")[0]
    return _filter_waiver_log_by_group(section, "batter")


def _entry_of(content, name):
    m = re.search(
        rf"### {re.escape(name)} \([^)]+\)[^\n]*\n(?:(?!### |## ).*\n)*",
        content,
        re.MULTILINE,
    )
    return m.group(0) if m else None


def _day_lines(text):
    return _DAY_RE.findall(text)


def _apply_days(snapshot, blocks_by_date):
    content = snapshot
    for short_date, block in blocks_by_date:
        content, _, _ = apply_waiver_log_block(
            content, block, short_date, mlb_id_lookup=lambda n: None)
    return content


# ── truncate_entry_history ──


class TestTruncateEntryHistory:
    def test_long_entry_keeps_trigger_and_last_5(self, snapshot):
        entry = _entry_of(snapshot, "Cam Smith")
        assert len(_day_lines(entry)) == 30  # real entry, weeks of history
        out = truncate_entry_history(entry)
        assert out.startswith(
            "### Cam Smith (HOU, RF) [mlb_id:701358] — 觀察中")
        assert "觸發：14d K% 回落 <28% + OPS 回升 >.700 → 升級取代候選" in out
        assert len(_day_lines(out)) == TRUNCATE_KEEP_RECENT
        for date in ("06-06", "06-07", "06-08", "06-09", "06-10"):
            assert f"- {date}：" in out
        assert "- 05-09：" not in out
        assert "（中略 25 行）" in out
        # Marker sits between the trigger line and the kept recent block.
        assert out.index("觸發：") < out.index("（中略 25 行）") \
            < out.index("- 06-06：")

    def test_eval_milestone_kept_unconditionally(self, snapshot):
        entry = _entry_of(snapshot, "J.P. Crawford")
        assert len(_day_lines(entry)) == 24  # [eval] + 23 daily lines
        out = truncate_entry_history(entry)
        assert "- 2026-05-15：[eval]" in out
        # Multi-line trigger (continuation row) preserved in full.
        assert "觸發：Swanson 14d xwOBA Δ ≥-0.080 連 5 天" in out
        assert "或 Crawford 後 15 場 BB% 退至 <10%" in out
        # eval + last 5 kept, the contiguous middle collapses to one marker.
        assert len(_day_lines(out)) == TRUNCATE_KEEP_RECENT + 1
        assert "（中略 18 行）" in out
        assert "- 05-19：" not in out

    def test_entry_at_keep_limit_unchanged(self, snapshot):
        entry = _entry_of(snapshot, "Heriberto Hernández")
        assert len(_day_lines(entry)) == TRUNCATE_KEEP_RECENT
        assert truncate_entry_history(entry) == entry

    def test_entry_below_keep_limit_unchanged(self, snapshot):
        entry = _entry_of(snapshot, "Garrett Mitchell")
        assert len(_day_lines(entry)) == 1
        assert truncate_entry_history(entry) == entry

    def test_entry_without_day_lines_unchanged(self, snapshot):
        # Header + trigger only (a just-created entry before its first
        # daily UPDATE) — derived from the real header to stay in-format.
        entry = _entry_of(snapshot, "Garrett Mitchell")
        header, trigger = entry.split("\n")[:2]
        bare = f"{header}\n{trigger}\n"
        assert truncate_entry_history(bare) == bare

    def test_non_day_context_lines_survive(self, snapshot):
        # 隊上觀察 entries carry non-day context bullets (傷情 / 對策 / …)
        # that must never be counted as history nor dropped.
        entry = _entry_of(snapshot, "Ryan Jeffers")
        assert len(_day_lines(entry)) == 8
        out = truncate_entry_history(entry)
        assert "- 啟動 2026-05-19（用戶 news check 觸發）" in out
        assert "- 風險脈絡：" in out
        assert len(_day_lines(out)) == TRUNCATE_KEEP_RECENT
        assert "（中略 3 行）" in out


# ── compute_history_counters ──


class TestComputeHistoryCounters:
    def test_day_counter_quoted_from_most_recent_line(self, snapshot):
        # Real Cam Smith 06-10 line carries 計數器重置 day 0/3.
        facts = compute_history_counters(_entry_of(snapshot, "Cam Smith"))
        assert facts == ["counter day 0/3（引自 06-10）"]

    def test_no_counter_token_no_fact(self, snapshot):
        # Goldschmidt's trigger has no day-counter mechanics at all.
        facts = compute_history_counters(
            _entry_of(snapshot, "Paul Goldschmidt"))
        assert facts == []

    def test_stale_counter_outside_window_suppressed(self, snapshot):
        # J.P. Crawford last carried `day 4/5` on 05-24 — the anchor has
        # since changed (Swanson left), so quoting it would mislead.
        entry = _entry_of(snapshot, "J.P. Crawford")
        assert "day 4/5" in entry  # stale token really exists upstream
        assert compute_history_counters(entry) == []

    def test_close_suggestion_streak_counted(self, snapshot):
        content = _apply_days(snapshot, [
            ("06-11", "UPDATE|Kyle Manzardo|14d 冷卻 建議結案"),
            ("06-12", "UPDATE|Kyle Manzardo|觸發無望 建議結案"),
        ])
        facts = compute_history_counters(_entry_of(content, "Kyle Manzardo"))
        assert "已連續建議結案 2 個掃描日" in facts

    def test_close_streak_broken_by_normal_day(self, snapshot):
        content = _apply_days(snapshot, [
            ("06-11", "UPDATE|Kyle Manzardo|14d 冷卻 建議結案"),
            ("06-12", "UPDATE|Kyle Manzardo|14d OPS .900 回溫持續觀察"),
        ])
        facts = compute_history_counters(_entry_of(content, "Kyle Manzardo"))
        assert not any("建議結案" in f for f in facts)


# ── truncate_watch_history (orchestrator) ──


class TestTruncateWatchHistory:
    def test_counters_derive_from_full_history_before_truncation(
            self, snapshot):
        # 7 trailing close-suggestion days — longer than the kept window.
        days = [(f"06-1{i}", "UPDATE|Kyle Manzardo|觸發無望 建議結案")
                for i in range(1, 8)]
        content = _apply_days(snapshot, days)
        section = content.split("## 觀察中")[1].split("## 已結案")[0]
        out = truncate_watch_history(
            _filter_waiver_log_by_group(section, "batter"))
        entry = _entry_of(out, "Kyle Manzardo")
        assert "[機械計數] 已連續建議結案 7 個掃描日" in entry
        assert len(_day_lines(entry)) == TRUNCATE_KEEP_RECENT

    def test_counter_lines_injected_after_header(self, watch_section):
        out = truncate_watch_history(watch_section)
        entry = _entry_of(out, "Cam Smith")
        assert entry.split("\n")[1] == (
            "[機械計數] counter day 0/3（引自 06-10）")

    def test_entries_without_facts_get_no_derived_line(self, watch_section):
        out = truncate_watch_history(watch_section)
        assert "[機械計數]" not in _entry_of(out, "Paul Goldschmidt")

    def test_coexists_with_028_replace_streak_line(self, snapshot):
        content = _apply_days(snapshot, [
            ("06-11", "UPDATE|Cam Smith|摘要一\nACTION|Cam Smith|取代|Jarren Duran"),
            ("06-12", "UPDATE|Cam Smith|摘要二\nACTION|Cam Smith|取代|Jarren Duran"),
        ])
        section = content.split("## 觀察中")[1].split("## 已結案")[0]
        filtered = inject_replace_streaks(
            _filter_waiver_log_by_group(section, "batter"))
        out = truncate_watch_history(filtered)
        entry = _entry_of(out, "Cam Smith")
        assert ("[機械計數] 已連續推薦取代 2 個掃描日"
                "（自 06-11 起，vs Jarren Duran）") in entry
        assert len(_day_lines(entry)) == TRUNCATE_KEEP_RECENT

    def test_preamble_and_subsection_headers_survive(self, watch_section):
        out = truncate_watch_history(watch_section)
        assert "## 隊上觀察" in out
        assert "自家球員的非數據脈絡" in out

    def test_size_drop_measurable_on_real_snapshot(self, watch_section):
        out = truncate_watch_history(watch_section)
        # A/B baseline: history segment shrank −45.9% on the full payload;
        # the watch section alone (pure history) should drop well past 40%.
        assert len(out) <= 0.6 * len(watch_section)

    def test_read_side_only(self, watch_section):
        out = truncate_watch_history(watch_section)
        # Source section retains the full history; only the returned payload
        # view is cut.
        assert "- 05-09：" in watch_section
        assert "- 05-09：" not in out
