"""Unit tests for heartbeat_check — 日報「沒送出」偵測。

should_alert / read_heartbeat / build_alert_message 都是純函式（後者只碰
tmp_path 上的檔案），不需要 mock 網路。門檻邊界的幾個 case 直接對應
heartbeat_check 模組 docstring 裡的排程推導，是這支腳本的行為契約：
只錯一天不吵、連錯兩天要吵。
"""

import pytest

from heartbeat_check import (
    THRESHOLD_HOURS,
    build_alert_message,
    read_heartbeat,
    should_alert,
)

H = 3600.0
NOW = 1_800_000_000.0


# ── should_alert ──

def test_no_record_alerts_fail_loud():
    """heartbeat 遺失時寧可誤報一次，也不要靜默失能。"""
    assert should_alert(None, NOW) == (True, None)


@pytest.mark.parametrize("age_h, expected", [
    (0.0, False),
    (24.0, False),      # 平日正常間隔
    (31.0, False),      # 週日 14:30 → 週一 21:30 的實際最長間隔
    (32.5, False),      # 同上，週一 23:00 檢查時的年齡 — 最容易誤報的一點
    (47.9, False),
    (48.0, False),      # 剛好門檻不觸發（用 > 而非 >=）
    (48.1, True),
    (49.5, True),       # 連錯兩天（平日）最短情境
    (120.0, True),
])
def test_threshold_boundaries(age_h, expected):
    alert, age = should_alert(NOW - age_h * H, NOW)
    assert alert is expected
    assert age == pytest.approx(age_h)


def test_custom_threshold_is_honoured():
    assert should_alert(NOW - 10 * H, NOW, threshold_hours=8)[0] is True
    assert should_alert(NOW - 10 * H, NOW, threshold_hours=12)[0] is False


def test_default_threshold_is_48():
    assert THRESHOLD_HOURS == 48


def test_future_timestamp_does_not_alert():
    """時鐘回撥 / 未來時間戳 → 負年齡，不該觸發。"""
    alert, age = should_alert(NOW + 5 * H, NOW)
    assert alert is False
    assert age < 0


# ── read_heartbeat ──

def test_missing_file_returns_none(tmp_path):
    assert read_heartbeat(str(tmp_path / "nope")) is None


def test_corrupt_content_returns_none(tmp_path):
    p = tmp_path / "hb"
    p.write_text("not-a-number", encoding="utf-8")
    assert read_heartbeat(str(p)) is None


def test_empty_file_returns_none(tmp_path):
    p = tmp_path / "hb"
    p.write_text("", encoding="utf-8")
    assert read_heartbeat(str(p)) is None


def test_reads_epoch_with_surrounding_whitespace(tmp_path):
    p = tmp_path / "hb"
    p.write_text("  1800000000.5\n", encoding="utf-8")
    assert read_heartbeat(str(p)) == pytest.approx(1_800_000_000.5)


def test_integer_epoch_reads_as_float(tmp_path):
    p = tmp_path / "hb"
    p.write_text("1800000000", encoding="utf-8")
    assert read_heartbeat(str(p)) == pytest.approx(1_800_000_000.0)


# ── build_alert_message ──

def test_message_without_age_says_record_missing():
    msg = build_alert_message(None)
    assert "找不到日報成功紀錄" in msg
    assert "daily-advisor.log" in msg


def test_message_with_age_reports_hours_and_threshold():
    msg = build_alert_message(49.5)
    assert "49.5 小時" in msg
    assert "48h" in msg
    assert "claude -p" in msg
