# Savant 14d Rolling Recency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 14d Savant rolling 資料抓取並整合至 fa_scan Pass 2 urgency 計算與 daily_advisor Section 1 近況旗標。

**Architecture:** 新增獨立 script `savant_rolling.py` 每日 TW 12:00 cron 抓取我方 11 名打者的 14 日 rolling Savant 數據，輸出 `savant_rolling.json` 單檔。fa_scan.py 的 `_build_pass2_data` 與 daily_advisor.py 的 Section 1 都從此檔讀取，消費端現算 Δ（14d xwOBA − season xwOBA）。

**Tech Stack:** Python 3 / urllib / Baseball Savant CSV leaderboard API / Linux cron

---

## Context

Step 1-3（CLAUDE.md 規則重寫 + fa_scan Pass 1/2 prompt 改版）已在 commits `1fc1817` / `8c23630` / `1836edb` 完成：
- CLAUDE.md 打者評估節已含 Step 2 urgency 規則（14d 因子 -2 到 +2）
- `prompt_fa_scan_pass2_batter.txt` 已含 14d 規則，但**資料缺值時規則說「該因子算 0」**
- 本 plan 補齊資料供應，讓 14d 因子實際生效

## File Structure

**Create:**
- `daily-advisor/savant_rolling.py` — 14d 抓取 script（獨立執行，cron 每日 TW 12:00）
- `daily-advisor/savant_rolling.json` — 產出資料（cron 每日覆蓋，`.gitignore` 排除）

**Modify:**
- `daily-advisor/fa_scan.py` — `_build_pass2_data()` 讀 savant_rolling.json，注入最弱打者 14d 行
- `daily-advisor/daily_advisor.py` — Section 1 批次載入 14d 資料，為每位打者輸出近況第三行
- `.gitignore` — 加入 `daily-advisor/savant_rolling.json`

**Infra（VPS 手動操作，不在 repo 裡）:**
- `/etc/cron.d/daily-advisor` — 加一條 TW 12:00（UTC 04:00）cron

## Function Interface Table

| 函式 | 簽名 | 檔案 | 呼叫者 |
|------|------|------|--------|
| `fetch_savant_rolling` | `(player_ids: list[int], end_date: str, window_days: int = 14) -> dict[int, dict]` | savant_rolling.py | main |
| `_fetch_player_pitches` | `(mlb_id: int, start_date: str, end_date: str) -> list[dict]` | savant_rolling.py | fetch_savant_rolling |
| `_aggregate_pitches` | `(rows: list[dict]) -> dict` | savant_rolling.py | fetch_savant_rolling |
| `_safe_float` | `(val) -> float \| None` | savant_rolling.py | _aggregate_pitches |
| `main` | `() -> None` | savant_rolling.py | CLI entry |
| `_load_savant_rolling` | `() -> dict[str, dict]` | fa_scan.py | `_build_pass2_data` |
| `compute_recency_flags` | `(r14: dict \| None, season_savant: dict \| None, bbe_gate: int = 25) -> dict \| None` | daily_advisor.py | `build_advisor_report` Section 1 |

## Data Schema

`savant_rolling.json`:
```json
{
  "generated_at": "2026-04-20T12:00:00+08:00",
  "window_days": 14,
  "date_range": ["2026-04-07", "2026-04-20"],
  "players": {
    "621439": {
      "name": "Byron Buxton",
      "xwoba": 0.384,
      "barrel_pct": 16.2,
      "hh_pct": 48.3,
      "bbe": 42,
      "pa": 54
    }
  }
}
```

**指標集**：xwOBA / Barrel% / HH% / BBE / PA（PA 為新增，從 statcast_search/csv 聚合時順手算，供下游 debug）

**為何不含 BB% 與 K%**（架構決策）：
- BB% 需從 MLB Stats API gameLog 另抓（Savant CSV 無此欄位），實作成本高；且 14d 規則中 Sum 計算用全季 Sum，不需要 14d BB%
- K% 使用者選擇 B 方案（2026-04-20 Q&A）：actionability 低、噪音大，砍掉簡化抓取
- 保留 Barrel% 為備援（同 CSV 順手抓，未來可能用）

## Tasks

---

### Task 1: API endpoint 選擇（已由 Architect 驗證，無需執行）

**Status:** ✅ Resolved 2026-04-20 by Architect

**背景**：原計畫測試 `leaderboard/statcast` + `leaderboard/expected_statistics` 的 `game_date_gt` / `game_date_lt` 參數。Builder 前次 run（2026-04-20 早先）確認**兩 endpoint 完全忽略日期參數**（單日範圍返回與全季相同 CSV bytes），不可行。

**新方案（來自上次 session 2026-04-18 實測紀錄 + 本次 curl 重驗）**：改用 `statcast_search/csv` endpoint。

- URL：`https://baseballsavant.mlb.com/statcast_search/csv`
- **支援** `game_date_gt` / `game_date_lt` 日期過濾
- 返回 **pitch-level raw CSV**（每球員一次 HTTP，需本地聚合為 PA/BBE/xwOBA/HH%/Barrel%）
- Buxton (621439) 2026-04-04 ~ 04-17 測試：176 行 CSV（175 pitches + header），欄位完整
- 必要欄位位置：`game_date` (欄 2), `events` (欄 9), `launch_speed` (欄 53), `estimated_woba_using_speedangle` (欄 69), `launch_speed_angle` (欄 74), `at_bat_number` (欄 75)

**Builder 動作**：跳過此 Task，直接進 Task 2（已按新 endpoint + 聚合邏輯重寫）。

**原 Step 1-4（leaderboard 測試）不再執行，保留記錄以免未來重蹈覆轍**：

- ~~Step 1-4：leaderboard endpoint date range 調研~~ — **已證實不可行**，跳過

---

### Task 2: savant_rolling.py — fetch 與聚合計算（statcast_search/csv）

**Files:**
- Create: `daily-advisor/savant_rolling.py`

**Architecture Change**：由於 leaderboard endpoints 不支援日期過濾，改用 `statcast_search/csv` 的 pitch-level raw data，本地聚合為 PA/BBE/xwOBA/HH%/Barrel%。每球員一次 HTTP request（11 人 ≈ 11 requests / ~30 秒）。

#### 關鍵常數與計算邏輯

**CSV `events` 欄位分類**（用於分辨 BBE / BB / HBP / K）：

- **BBE_EVENTS**（算 BBE count）：
  `single, double, triple, home_run, field_out, force_out, grounded_into_double_play, double_play, triple_play, fielders_choice, fielders_choice_out, field_error, sac_fly, sac_fly_double_play, sac_bunt`
- **BB_EVENTS**：`walk`
- **HBP_EVENTS**：`hit_by_pitch`
- **（排除）**：`strikeout, strikeout_double_play`（算 PA 但不算 BBE 且 xwOBA 分子為 0）

**PA 識別**：unique `(game_date, at_bat_number)` tuple

**xwOBA 完整公式**（必須匹配 Baseball Savant season xwOBA 尺度）：
```
sum_xwoba_on_bbe = Σ estimated_woba_using_speedangle (for rows where events ∈ BBE_EVENTS)
xwOBA = (0.69 × BB_count + 0.72 × HBP_count + sum_xwoba_on_bbe) / PA
```

**HH% / Barrel% on BBE**：
```
HH%     = count(launch_speed ≥ 95  AND events ∈ BBE_EVENTS) / BBE × 100
Barrel% = count(launch_speed_angle == 6 AND events ∈ BBE_EVENTS) / BBE × 100
```

**🚨 三大踩坑預警**（上次 session 2026-04-18 實測踩過）：
- **v1 坑**：`if launch_speed is not None` 算 BBE → foul ball 也有 launch_speed，會被誤計。正確做法：先過濾 `events ∈ BBE_EVENTS`
- **v2 坑**：只對 BBE 行平均 `estimated_woba_using_speedangle` 當 xwOBA → 那是 `xwOBA_on_contact` 尺度，跟 season xwOBA（含 BB/HBP/K 權重）不可比。必須套完整公式 `(0.69×BB + 0.72×HBP + Σ) / PA`
- **v3 坑**：CSV 空值 `""` / `"null"` / `"-"` / `" "` 多樣，parse 要 try/except ValueError

#### 實作

- [ ] **Step 1: 建立 savant_rolling.py（import + 常數 + fetch）**

Create `daily-advisor/savant_rolling.py`:

```python
#!/usr/bin/env python3
"""Fetch rolling-window Savant data for given players.

Uses Baseball Savant statcast_search/csv endpoint (pitch-level raw data,
aggregated locally to PA/BBE/xwOBA/HH%/Barrel% metrics).

Runs daily via cron (TW 12:00). Writes savant_rolling.json in same dir.
Window: last N calendar days ending on today (default 14d).
"""

import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTER_PATH = os.path.join(SCRIPT_DIR, "roster_config.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "savant_rolling.json")

# CSV events classification
BBE_EVENTS = frozenset({
    "single", "double", "triple", "home_run",
    "field_out", "force_out", "grounded_into_double_play",
    "double_play", "triple_play",
    "fielders_choice", "fielders_choice_out", "field_error",
    "sac_fly", "sac_fly_double_play", "sac_bunt",
})
BB_EVENTS = frozenset({"walk"})
HBP_EVENTS = frozenset({"hit_by_pitch"})

# xwOBA weights (MLB standard, matches Baseball Savant season xwOBA)
XWOBA_BB_WEIGHT = 0.69
XWOBA_HBP_WEIGHT = 0.72


def _fetch_player_pitches(mlb_id, start_date, end_date):
    """Fetch pitch-level CSV for one player.

    Args:
        mlb_id: int — MLB player ID
        start_date: str "YYYY-MM-DD" (inclusive)
        end_date: str "YYYY-MM-DD" (inclusive)

    Returns:
        list of CSV row dicts (empty on error)
    """
    year = end_date[:4]
    params = {
        "all": "true",
        "hfSea": f"{year}|",
        "player_type": "batter",
        "batters_lookup[]": str(mlb_id),
        "game_date_gt": start_date,
        "game_date_lt": end_date,
        "min_pitches": "0",
        "min_results": "0",
        "min_pas": "0",
        "type": "details",
    }
    url = "https://baseballsavant.mlb.com/statcast_search/csv?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        text = resp.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    except Exception as e:
        print(f"Fetch failed for player {mlb_id}: {e}", file=sys.stderr)
        return []


def _safe_float(val):
    """Parse float from CSV cell, handling common empty markers."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "null", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _aggregate_pitches(rows):
    """Aggregate pitch-level rows into player metrics.

    Args:
        rows: list[dict] — CSV rows from _fetch_player_pitches

    Returns:
        dict — {xwoba, barrel_pct, hh_pct, bbe, pa} or {} if no usable data
    """
    if not rows:
        return {}

    pa_set = set()
    bbe_count = 0
    bb_count = 0
    hbp_count = 0
    sum_xwoba_on_bbe = 0.0
    hh_count = 0
    barrel_count = 0

    for row in rows:
        gd = (row.get("game_date") or "").strip()
        abn = (row.get("at_bat_number") or "").strip()
        if gd and abn:
            pa_set.add((gd, abn))

        event = (row.get("events") or "").strip()
        if not event:
            continue  # Mid-PA pitch, skip

        if event in BB_EVENTS:
            bb_count += 1
        elif event in HBP_EVENTS:
            hbp_count += 1
        elif event in BBE_EVENTS:
            bbe_count += 1
            xw = _safe_float(row.get("estimated_woba_using_speedangle"))
            if xw is not None:
                sum_xwoba_on_bbe += xw
            ls = _safe_float(row.get("launch_speed"))
            if ls is not None and ls >= 95:
                hh_count += 1
            lsa = _safe_float(row.get("launch_speed_angle"))
            if lsa is not None and int(lsa) == 6:
                barrel_count += 1
        # else: strikeout or other — counted in PA only

    pa = len(pa_set)
    if pa == 0 or bbe_count == 0:
        return {}

    xwoba = (
        XWOBA_BB_WEIGHT * bb_count
        + XWOBA_HBP_WEIGHT * hbp_count
        + sum_xwoba_on_bbe
    ) / pa

    return {
        "xwoba": round(xwoba, 3),
        "barrel_pct": round(barrel_count / bbe_count * 100, 1),
        "hh_pct": round(hh_count / bbe_count * 100, 1),
        "bbe": bbe_count,
        "pa": pa,
    }


def fetch_savant_rolling(player_ids, end_date, window_days=14):
    """Fetch rolling Savant data for given players.

    Args:
        player_ids: list[int] — MLB player IDs
        end_date: str "YYYY-MM-DD"
        window_days: int — lookback window (default 14)

    Returns:
        dict[int, dict] — {player_id: {xwoba, barrel_pct, hh_pct, bbe, pa}}
        Players with no data in window are omitted.
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=window_days)
    start_str = start_dt.strftime("%Y-%m-%d")

    result = {}
    for pid in player_ids:
        rows = _fetch_player_pitches(pid, start_str, end_date)
        metrics = _aggregate_pitches(rows)
        if metrics:
            result[pid] = metrics
    return result
```

- [ ] **Step 2: 對齊驗證（復現上次 session 2026-04-18 Buxton 數字）**

Run:
```bash
cd daily-advisor/
python3 -c "
from savant_rolling import fetch_savant_rolling
import json
# Buxton 621439, 複用上次 session 窗口 2026-04-04 ~ 2026-04-17
# window_days=13 使 end_date 2026-04-17 對應 start 2026-04-04
result = fetch_savant_rolling([621439], '2026-04-17', window_days=13)
print(json.dumps(result, indent=2))
"
```

**Expected（對照上次 session 記錄）**：
- Buxton 14d xwOBA **≈ 0.384**（上次紀錄值，season 0.315 Δ +0.069）
- BBE **介於 26-40**（v1 修正後範圍；若 60+ 代表 foul 誤算）
- PA 約 50-60
- 若 xwOBA **顯著 > 0.500** → v2 坑未修（xwOBA_on_contact 尺度），檢查 XWOBA_* 常數與公式

**決策節點**：此 Step 必須通過才能繼續。若 xwOBA 與預期偏差 > ±0.050 → **STOP**，回報 Architect 檢查計算邏輯。

- [ ] **Step 3: 多球員煙霧測試**

Run:
```bash
python3 -c "
from savant_rolling import fetch_savant_rolling
import json
# 3 主力，用當前日期
result = fetch_savant_rolling([621439, 592518, 645277], '2026-04-20')
print(json.dumps(result, indent=2))
"
```

Expected: 3 位都有 xwoba / barrel_pct / hh_pct / bbe / pa 五欄位。PA 合理（主力 45-60）。執行時間 <15 秒（3 × 5 秒 HTTP timeout 內）。

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/savant_rolling.py
git commit -m "feat(savant-rolling): add pitch-level aggregate for 14d rolling"
```

---

### Task 3: savant_rolling.py — `main()` entry 與 JSON 寫出

**Files:**
- Modify: `daily-advisor/savant_rolling.py`（append main function）
- Modify: `.gitignore`

- [ ] **Step 1: 加 main function 到 savant_rolling.py 末尾**

```python
def main():
    with open(ROSTER_PATH, encoding="utf-8") as f:
        config = json.load(f)

    # Active batters only (exclude IL/NA)
    INACTIVE = ("IL", "IL+", "NA")
    batters = [
        b for b in config.get("batters", [])
        if b.get("selected_pos", "") not in INACTIVE and b.get("mlb_id")
    ]
    player_ids = [int(b["mlb_id"]) for b in batters]
    id_to_name = {int(b["mlb_id"]): b["name"] for b in batters}

    end_date = date.today().strftime("%Y-%m-%d")
    data = fetch_savant_rolling(player_ids, end_date, window_days=14)

    # Add player names to output
    players_out = {
        str(pid): {"name": id_to_name.get(pid, "?"), **stats}
        for pid, stats in data.items()
    }

    start_date = (date.today() - timedelta(days=14)).strftime("%Y-%m-%d")
    tz_tpe = timezone(timedelta(hours=8))
    output = {
        "generated_at": datetime.now(tz_tpe).isoformat(timespec="seconds"),
        "window_days": 14,
        "date_range": [start_date, end_date],
        "players": players_out,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"Wrote {OUTPUT_PATH}: {len(players_out)}/{len(player_ids)} players with data",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 執行 main**

Run:
```bash
cd daily-advisor/
python3 savant_rolling.py
cat savant_rolling.json | python3 -m json.tool | head -40
```

Expected:
- stderr: `Wrote .../savant_rolling.json: 8-11/11 players with data`（視傷病狀況，主力全覆蓋）
- JSON 含 `generated_at` / `window_days=14` / `date_range` (2 日期) / `players` dict
- 每位 player 有 name + xwoba + barrel_pct + hh_pct + bbe

- [ ] **Step 3: 加 savant_rolling.json 到 .gitignore**

Edit `.gitignore`，在 `daily-advisor/fa_history.json` 那行之後加：

```
daily-advisor/savant_rolling.json
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore daily-advisor/savant_rolling.py
# 注意：不 add savant_rolling.json（被 .gitignore 排除）
git commit -m "feat(savant-rolling): add main entry, write JSON output"
```

---

### Task 4: VPS cron 排程設定

**Files:**
- Modify on VPS: `/etc/cron.d/daily-advisor`（不在 repo 裡）

**Note:** 此 Task 需 SSH VPS root 操作，Builder 若無權限需回報 Architect 手動完成。

- [ ] **Step 1: Push 本地 commit 到 origin，VPS pull 更新**

Run (local):
```bash
git push origin master
```

Run (VPS):
```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy && git pull"
```

- [ ] **Step 2: VPS 手動測試 savant_rolling.py**

Run:
```bash
ssh root@107.175.30.172 'export PATH=/root/.local/bin:$PATH && cd /opt/mlb-fantasy/daily-advisor && python3 savant_rolling.py'
ssh root@107.175.30.172 "ls -la /opt/mlb-fantasy/daily-advisor/savant_rolling.json"
ssh root@107.175.30.172 "cat /opt/mlb-fantasy/daily-advisor/savant_rolling.json | head -20"
```

Expected:
- stderr 顯示成功訊息
- JSON 檔存在，格式正確

- [ ] **Step 3: 編輯 VPS crontab，加 TW 12:00 條目**

Run (VPS):
```bash
ssh root@107.175.30.172
# 查看現況
cat /etc/cron.d/daily-advisor
# 編輯加入（TW 12:00 = UTC 04:00）：
echo "0 4 * * * root export PATH=/root/.local/bin:\$PATH && cd /opt/mlb-fantasy/daily-advisor && /usr/bin/python3 savant_rolling.py >> /var/log/mlb-fantasy.log 2>&1" | sudo tee -a /etc/cron.d/daily-advisor
# 驗證
grep savant_rolling /etc/cron.d/daily-advisor
sudo systemctl status cron
```

Expected:
- crontab 新增行存在
- cron service `active (running)`

- [ ] **Step 4: 次日 TW 12:05 驗證自動執行**

Run next day after 12:05:
```bash
ssh root@107.175.30.172 "grep savant /var/log/mlb-fantasy.log | tail -5"
ssh root@107.175.30.172 "ls -la /opt/mlb-fantasy/daily-advisor/savant_rolling.json"
```

Expected:
- log 有成功記錄
- JSON 檔 mtime 為今日 12:00 附近（UTC 04:00）

---

### Task 5: fa_scan.py — `_build_pass2_data` 注入 14d 資料

**Files:**
- Modify: `daily-advisor/fa_scan.py`

- [ ] **Step 1: 加 `_load_savant_rolling` helper**

在 fa_scan.py 找適當位置（建議放在 `_extract_eval_framework` 旁，約行 1340 附近），加：

```python
def _load_savant_rolling():
    """Load savant_rolling.json if exists, else return empty dict.

    Returns:
        dict[str, dict] — {player_id_str: {name, xwoba, hh_pct, barrel_pct, bbe}}
    """
    path = os.path.join(SCRIPT_DIR, "savant_rolling.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("players", {})
    except Exception as e:
        print(f"Failed to load savant_rolling.json: {e}", file=sys.stderr)
        return {}
```

- [ ] **Step 2: `_build_pass2_data` 最弱打者輸出區段加 14d 行**

**A. 在迴圈外一次載入**（避免每人重讀檔案）

找到 `_build_pass2_data` 函式中 `for w in pass1_weakest:` 這行**之前**（約行 1738-1739 之間），加：

```python
    # 14d rolling data (batter only, loaded once)
    rolling = _load_savant_rolling() if group_type == "batter" else {}
```

**B. 迴圈內輸出 14d 行**

找到 `parts.append(f"BBE {s26.get('bbe', 0)}")`（約行 1767）之後、`# Prior year stats`（約行 1769）之前，插入：

```python
        # 14d rolling data — only if batter + BBE ≥ 25
        if group_type == "batter":
            mlb_id_str = str(p.get("mlb_id", ""))
            r14 = rolling.get(mlb_id_str) if mlb_id_str else None
            if r14 and r14.get("bbe", 0) >= 25:
                s26_xwoba = s26.get("xwoba") if s26 else None
                r14_xwoba = r14.get("xwoba")
                delta_str = ""
                if s26_xwoba and r14_xwoba:
                    delta = r14_xwoba - s26_xwoba
                    delta_str = f" Δ{delta:+.3f}"
                parts.append(
                    f"14d: xwOBA {r14_xwoba:.3f}{delta_str} | "
                    f"HH% {r14.get('hh_pct', 0):.1f}% | BBE {r14.get('bbe', 0)}"
                )
```

- [ ] **Step 3: 本地 dry-run 測試**

先手動建立 test fixture（若本地沒有 savant_rolling.json）：
```bash
cat > daily-advisor/savant_rolling.json <<'EOF'
{
  "generated_at": "2026-04-20T12:00:00+08:00",
  "window_days": 14,
  "date_range": ["2026-04-07", "2026-04-20"],
  "players": {
    "621439": {"name": "Byron Buxton", "xwoba": 0.384, "barrel_pct": 16.2, "hh_pct": 48.3, "bbe": 42},
    "617676": {"name": "Ozzie Albies", "xwoba": 0.243, "barrel_pct": 3.1, "hh_pct": 33.8, "bbe": 38}
  }
}
EOF
```

Run:
```bash
cd daily-advisor/
python3 fa_scan.py --dry-run 2>&1 | grep -A1 "14d:" | head -10
```

Expected: 最弱打者輸出中含 14d 行，如：
```
  Byron Buxton(MIN) | [Pass1 Sum 20 (xwOBA:7 / BB%:3 / Barrel%:10)] | xwOBA ... | 14d: xwOBA 0.384 Δ+0.069 | HH% 48.3% | BBE 42
```

- [ ] **Step 4: Commit**

```bash
# 注意不要 add savant_rolling.json（本地 fixture）
git add daily-advisor/fa_scan.py
git commit -m "feat(fa-scan): inject 14d rolling data to Pass 2 weakest batter output"
```

---

### Task 6: daily_advisor.py — Section 1 近況旗標第三行

**Files:**
- Modify: `daily-advisor/daily_advisor.py`

- [ ] **Step 1: 加 `compute_recency_flags` helper**

在 daily_advisor.py 找適當位置（建議放在 `pctile_tag` 函式之後，約行 91 附近），加：

```python
def compute_recency_flags(r14, season_savant, bbe_gate=25):
    """Compute recency flags for Section 1 third line.

    Args:
        r14: dict | None — 14d rolling data with xwoba/hh_pct/bbe
        season_savant: dict | None — season Savant with xwoba/hh_pct
        bbe_gate: int — 低於此 BBE 不輸出旗標（噪音太大）

    Returns:
        dict | None — {flag, delta_xwoba, line} or None if no signal
    """
    if not r14 or r14.get("bbe", 0) < bbe_gate:
        return None

    season_xwoba = season_savant.get("xwoba") if season_savant else None
    r14_xwoba = r14.get("xwoba")
    if not (season_xwoba and r14_xwoba):
        return None

    delta = r14_xwoba - season_xwoba

    # Flag classification per CLAUDE.md 打者評估 14d 規則
    if delta >= 0.050:
        flag = "🔥強回升"
    elif delta >= 0.035:
        flag = "🔥弱回升"
    elif delta <= -0.050:
        flag = "❄️強下滑"
    elif delta <= -0.035:
        flag = "❄️弱下滑"
    else:
        flag = "持平"

    # HH% warning (per CLAUDE.md: 14d HH% - season ≤ -10pp)
    season_hh = season_savant.get("hh_pct") if season_savant else None
    r14_hh = r14.get("hh_pct")
    hh_warning = ""
    if season_hh and r14_hh is not None:
        hh_delta = r14_hh - season_hh
        if hh_delta <= -10:
            hh_warning = f" | ⚠️ HH%下修 {hh_delta:+.1f}pp"

    line = (
        f"14d: {flag} xwOBA {r14_xwoba:.3f} Δ{delta:+.3f} | "
        f"HH% {r14_hh:.1f}% | BBE {r14['bbe']}{hh_warning}"
    )
    return {"flag": flag, "delta_xwoba": delta, "line": line}
```

- [ ] **Step 2: build_advisor_report 開始處載入 14d 資料**

找 `build_advisor_report` 中 `savant_cache` 載入附近（Grep `savant_cache` 查位置）。在 batter savant 載入後加：

```python
    # 14d rolling savant (for Section 1 recency flags)
    rolling_path = os.path.join(SCRIPT_DIR, "savant_rolling.json")
    rolling_14d = {}
    if os.path.exists(rolling_path):
        try:
            with open(rolling_path, encoding="utf-8") as f:
                rolling_14d = json.load(f).get("players", {})
        except Exception as e:
            print(f"Failed to load savant_rolling.json: {e}", file=sys.stderr)
```

**Note:** `SCRIPT_DIR` 已於 daily_advisor.py 行 18 定義，直接使用即可。

- [ ] **Step 3: Section 1 批次輸出第三行**

在 Section 1 `for b in batters:` 循環中（行 ~1113 附近 `Statcast: ...` 之後），加：

```python
        # 14d recency flags (third line, only if signal)
        r14 = rolling_14d.get(str(mlb_id)) if mlb_id else None
        season_s = savant_cache.get(mlb_id)
        recency = compute_recency_flags(r14, season_s)
        if recency:
            lines.append(f"    {recency['line']}")
```

**插入位置**：在現有 `if savant_line: lines.append(f"    Statcast: {savant_line}")` 這行**之後**。

- [ ] **Step 4: 手動測試 daily_advisor 輸出**

Run:
```bash
cd daily-advisor/
python3 daily_advisor.py --morning --dry-run 2>&1 | grep -B1 "14d:" | head -20
```

Expected: 主力打者（BBE ≥25）有 14d 第三行，如：
```
    Statcast: xwOBA .315 (P60-70) | Barrel% 12.3% (P60-70)
    14d: 🔥強回升 xwOBA 0.384 Δ+0.069 | HH% 48.3% | BBE 42
```

BBE <25 的球員（例如傷後復出、輪替）不輸出 14d 行（可接受）。

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/daily_advisor.py
git commit -m "feat(daily-advisor): add Section 1 recency flags from 14d rolling"
```

---

### Task 7: 整合驗證

**Files:** 無（smoke test）

- [ ] **Step 1: Push 所有 commits，VPS pull**

Run:
```bash
git push origin master
ssh root@107.175.30.172 "cd /opt/mlb-fantasy && git pull"
```

- [ ] **Step 2: VPS 手動觸發三個流程**

Run:
```bash
ssh root@107.175.30.172 'export PATH=/root/.local/bin:$PATH && cd /opt/mlb-fantasy/daily-advisor && bash -c "
  echo \"=== 1. savant_rolling ===\"
  python3 savant_rolling.py
  echo \"---\"
  echo \"=== 2. daily_advisor morning Section 1 ===\"
  python3 daily_advisor.py --morning --dry-run 2>&1 | grep -B1 \"14d:\" | head -20
  echo \"---\"
  echo \"=== 3. fa_scan dry-run Pass 2 data ===\"
  python3 fa_scan.py --dry-run 2>&1 | grep \"14d:\" | head -10
"'
```

Expected:
- `savant_rolling.json` 產出，8-11 球員有資料
- daily_advisor Section 1 主力打者有 14d 第三行
- fa_scan Pass 2 資料組裝含 14d 行（Pass 1 最弱 4 人中主力會有）

- [ ] **Step 3: 生產環境 end-to-end 驗證**

次日 fa_scan 12:30 自動觸發後，查 GitHub Issue：
```bash
gh issue list -R huansbox/mlb-fantasy --limit 3
# 取最新 FA Scan issue，查 Pass 2 輸出
gh issue view <N> -R huansbox/mlb-fantasy | grep -A2 "urgency"
```

Expected: Pass 2 Claude 輸出的「我方最弱打者」urgency 分數包含 14d 加分（-2 / -1 / 0 / +1 / +2），而非全部 0（資料缺值時的 fallback 行為）。

- [ ] **Step 4: 回報給 Architect**

無 commit。將以下 smoke test 結果彙整回報：
- savant_rolling.json 幾位球員有資料
- daily_advisor Section 1 14d 第三行範例（貼 2-3 行）
- fa_scan Pass 2 Claude 實際使用 14d 因子的範例（從 GitHub Issue）
- 任何異常或 edge case

---

## Pre-conditions（Plan 依賴的已存在狀態）

- ✅ `fa_scan.py:_build_pass2_data` 已改動（commit `1836edb`），能讀 Pass 1 score/breakdown，最弱打者輸出已加 BB% 欄位
- ✅ `CLAUDE.md` 打者評估節已含 Step 2 urgency 規則（commit `1fc1817`）
- ✅ `prompt_fa_scan_pass2_batter.txt` 已含 14d 規則（commit `1836edb`），等資料供應生效
- ✅ VPS 現有 cron `/etc/cron.d/daily-advisor` 正常運作（fa_scan / daily_advisor 排程穩定）
- ⚠️ Task 1 前置：Baseball Savant leaderboard date range 支援狀態**未驗證**，若 fail 需走 fallback 架構

## 風險與回退

| 風險 | 機率 | 緩解 |
|------|------|------|
| ~~Savant leaderboard 不支援 date range~~ | ✅ Resolved | 改用 `statcast_search/csv`，Architect 已驗證 |
| 聚合邏輯 bug（v1/v2/v3 踩坑重現） | 中 | Task 2 Step 2 必跑 Buxton 對齊驗證（xwOBA ≈ 0.384 + BBE 26-40）|
| `statcast_search/csv` rate limit | 低 | 11 球員串行 HTTP ~30 秒，不衝突 Savant UI 使用模式 |
| 14d 資料抓取失敗（單球員超時） | 中 | `_fetch_player_pitches` 內 try/except + print stderr；該球員 drop，其餘照常 |
| savant_rolling.json 不小心被 commit | 中 | Task 3 優先加 .gitignore |
| cron 時間與既有排程衝突 | 低 | TW 12:00 目前無其他排程，緩衝充足 |
| BBE gate 讓太多球員無 14d 行輸出 | 中 | 若主力（PA/TG ≥3.0）BBE <25 代表資料異常，而非 gate 過嚴；驗證階段觀察比例 |

**回退路徑**：每個 Task 獨立 commit，可逐步 revert。最保守回退 = 刪除 `savant_rolling.json` 或 cron 停用，fa_scan / daily_advisor 自動回歸 Step 1-3 行為（14d 因子算 0，Section 1 不輸出第三行）。

## Known Limitations（驗證期觀察，不在本 plan 修）

- BB% 缺：14d 不包含 BB%（雖然 `statcast_search/csv` 的 walk 事件有記錄，但聚合為 BB% 需另算 `bb_count / pa`，本 plan 暫未輸出此欄；Pass 2 prompt 的「14d 近況 Δ」僅看 xwOBA，規則本身已如此設計）
- 14d 場次不均：14 曆日對不同球員代表不同場次數（主力 ~12 場 / 輪替 ~6-8 場），樣本量用 BBE gate 統一
- Savant 日期邊界：`game_date_gt` / `game_date_lt` 為閉區間（inclusive），驗證 Buxton 窗口時第一球 `2026-04-17` 與 `game_date_lt=2026-04-17` 對齊
- 每球員一次 HTTP：11 人串行 ~30 秒，可接受；未來若擴展到 FA 50+ 球員需考慮並行（`concurrent.futures`）或 batched endpoint
