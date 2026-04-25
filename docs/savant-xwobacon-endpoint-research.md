# 21d xwOBACON Savant 端點研究

> **Status**：研究完成（2026-04-25）。**主要 finding：不需新 endpoint，現有 `savant_rolling.py` statcast_search/csv 抓的 pitch-level 資料已足夠，只需在 aggregate 步驟加 1 欄計算。**
> **配套**：v4 cutover 前置工作之一，配合 `backfill_prior_stats_v4.py`（季全 xwOBACON）+ 本擴充（21d rolling xwOBACON）即可解鎖 v4 框架的時序訊號（urgency 第 3 因子原始 Δ）。

---

## 1. 背景與問題

### 1.1 為什麼需要 21d xwOBACON

v4 框架（`docs/sp-framework-v4-balanced.md`）的 5 個 Sum slot 之一是 **xwOBACON**（on-contact xwOBA，排除 K/BB），原因見 CLAUDE.md 評估框架章節：

> **xwOBACON vs xwOBA 的關鍵區別**：xwOBA 含 K/BB 會被高 K 率稀釋，xwOBACON 是 on-contact 純粹 H 端預測。Nola / López xwOBA 幾乎一樣（.342 vs .347）但 xwOBACON .424 vs .388 — Nola 被打更紮實，只是被 K% 25.2 掩蓋。

v4 urgency Step 2 第 3 因子是「21d Δ xwOBACON」（最近 3-4 場先發 vs 季全的差異）。CLAUDE.md TODO 與 Phase 6 design doc 都標記此前置工作未完成：

> **21d rolling xwOBACON fetch**：savant_rolling.py 目前只抓 xwOBA allowed，v4 時序訊號用 xwOBACON 要擴充（pitch-level CSV 聚合，排除 K/BB 只算 on-contact）

### 1.2 既有疑慮（已解除）

撰寫此研究前的假設：
- 以為要研究新 endpoint，特別是 `baseballsavant.mlb.com/leaderboard/custom?selections=xwobacon` 是否能逐日窗口參數化
- 預期端點穩定性風險高（custom leaderboard 是非標準 URL）

**研究後確認**：上述假設**錯誤**。實際只需擴充本地 aggregate 邏輯。

---

## 2. 既有架構摸底

### 2.1 `savant_rolling.py` 流程（line 47-198）

```
input: mlb_id list + end_date + window_days + player_type
  ↓
_fetch_player_pitches(): GET statcast_search/csv → pitch-level CSV rows
  ↓
_aggregate_pitches(): 把 pitch rows aggregate 成 player metrics
  ↓
output: {player_id: {xwoba, barrel_pct, hh_pct, bbe, pa}}
```

### 2.2 Endpoint 規格（line 73）

```python
url = "https://baseballsavant.mlb.com/statcast_search/csv?" + urlencode(params)
```

`params` 結構：

| Key | 值 | 說明 |
|-----|-----|------|
| `all` | `"true"` | 顯示全部欄位 |
| `hfSea` | `"{year}\|"` | 賽季篩選（pipe 必要） |
| `player_type` | `"batter"` 或 `"pitcher"` | 視角 |
| `batters_lookup[]` 或 `pitchers_lookup[]` | mlb_id | 球員 ID（單人） |
| `game_date_gt` | `"YYYY-MM-DD"` | 起始日（含） |
| `game_date_lt` | `"YYYY-MM-DD"` | 結束日（含） |
| `min_pitches` / `min_results` / `min_pas` | `"0"` | 不過濾下限 |
| `type` | `"details"` | 完整 pitch-level（含 events / launch_speed / estimated_woba） |

**穩定性**：`statcast_search/csv` 是 Savant 公開搜尋介面的 export，不是非標準 leaderboard URL — 多年穩定。本檔已 production cron 跑數週無 endpoint 失誤。

### 2.3 Pitch-level CSV 已含的欄位（line 122-147 解析）

每個 pitch row 含：

| CSV 欄位 | 用途 |
|----------|------|
| `game_date` + `at_bat_number` | 識別 PA（line 123-126，去重得 `pa` 計數） |
| `events` | 該 PA 的最終結果（mid-PA pitch 為空字串）|
| `estimated_woba_using_speedangle` | **每球 BBE 的 xwOBA 值**（line 138 — 這就是 xwOBACON 的素材） |
| `launch_speed` | ≥95 mph → HH (line 142) |
| `launch_speed_angle` | =6 → Barrel (line 145) |

**關鍵**：`estimated_woba_using_speedangle` 是 Savant 公開的 contact-level xwOBA 估計值（基於 launch speed + launch angle 的模型），這正是 xwOBACON 的構成元素。

### 2.4 既有 `_aggregate_pitches()` 已算到一半（line 122-157）

```python
sum_xwoba_on_bbe = 0.0
...
elif event in BBE_EVENTS:
    bbe_count += 1
    xw = _safe_float(row.get("estimated_woba_using_speedangle"))
    if xw is not None:
        sum_xwoba_on_bbe += xw
    ...

# Final xwOBA total (含 BB/HBP 加權)
xwoba = (XWOBA_BB_WEIGHT * bb_count + XWOBA_HBP_WEIGHT * hbp_count + sum_xwoba_on_bbe) / pa
```

`sum_xwoba_on_bbe` 已逐球累加，現只 output `xwoba`（含 walks 加權的 PA-base）— 沒 output 「contact-base」的 `xwobacon`。

---

## 3. xwOBACON 計算定義（驗證 vs Savant 公開值）

### 3.1 數學形式

Baseball Savant 對 xwOBACON 的定義（[Glossary](https://baseballsavant.mlb.com/csv-docs)）：

```
xwOBACON = sum(estimated_woba on contact) / count(BBE)
```

亦即只計入 `events ∈ BBE_EVENTS`（field_out / single / double / triple / home_run / sac_fly / 等），**排除 walk / hit_by_pitch / strikeout / catcher_interference**。

### 3.2 對應到既有變數

```python
xwobacon = sum_xwoba_on_bbe / bbe_count
```

**已 100% 在 `_aggregate_pitches()` 局部範圍內可算** — 不需新 fetch、不需新 endpoint、不需重抓 CSV。

### 3.3 樣本量考量

21d 窗口 SP 通常 3-4 場先發 → BBE 約 60-100。但：
- 短局 RP / 非主力 SP / 受傷剛回的 SP → BBE 可能 < 30
- Savant 對 xwOBACON 一般要求 BBE ≥50 才登季排行榜

**建議閾值**（沿用既有 batter rolling 的 confidence 標記模式）：
- BBE ≥ 50 → 高信心
- BBE 30-49 → 中信心（rolling 反映個別場次強度）
- BBE < 30 → 低信心，CLAUDE.md TODO 已決定 v4 cutover 後 Python `_factor_rolling` 暫返 0，原始 Δ + BBE 餵 Claude（門檻校準前不打分）

---

## 4. 實作建議（v4 cutover 期執行）

### 4.1 最小改動

```python
# savant_rolling.py _aggregate_pitches() 末段
result = {
    "xwoba": round(xwoba, 3),
    "barrel_pct": round(barrel_count / bbe_count * 100, 1),
    "hh_pct": round(hh_count / bbe_count * 100, 1),
    "bbe": bbe_count,
    "pa": pa,
}
# +++ 新增 +++
if bbe_count > 0:
    result["xwobacon"] = round(sum_xwoba_on_bbe / bbe_count, 3)
# --- 新增 ---
return result
```

`savant_rolling.json` schema 自動帶上 `xwobacon` 欄位（既有 consumer 讀不到該 key 直接 None-handling 即可，向下相容）。

### 4.2 對 fa_scan / fa_scan_v4 的影響

- `savant_rolling.py` cron job 跑出的 `savant_rolling.json` 多一欄 `xwobacon`
- `fa_scan.py` 的 `load_savant_rolling()` 自動帶上（dict pass-through）
- v4 cutover 時 `_factor_rolling`（v4-specific）讀 `entry["xwobacon"] - prior_stats["xwobacon"]` 算 Δ
- batter v2 線完全不受影響（batter rolling 仍只用 xwoba）

### 4.3 unit test 涵蓋點

新增 test for `_aggregate_pitches`：

| Case | 期望 |
|------|------|
| 全 BBE 場（無 K/BB） | `xwobacon == xwoba × pa / bbe_count`（純 contact 一致） |
| 含 K/BB 場 | `xwobacon ≠ xwoba`（K/BB 稀釋 xwoba 但不影響 xwobacon） |
| BBE = 0（全 K/BB） | `xwobacon` 不在 result（既有邏輯 line 150 已 `return {}`） |
| 單場 1 BBE xwoba 0.5 | `xwobacon == 0.5` |

### 4.4 校準 vs Savant 季全 xwOBACON

實作後立即驗證：拿一位 SP（如 Skubal）跑 Mar-Sep 全季窗口 → 比對 Savant 公開的 2025 季全 xwOBACON 值。若差距 > 0.005（rounding 容忍）則表示 events 分類有缺漏（如 sac_bunt、catcher_interference 處理）。

`backfill_prior_stats_v4.py` 用 custom leaderboard CSV 抓季全 xwOBACON — 這是「Savant 官方算法」的 ground truth。本擴充應和該值對齊。

---

## 5. 為什麼此前以為要研究新 endpoint（檢討）

CLAUDE.md TODO 措辭「pitch-level CSV 聚合，排除 K/BB 只算 on-contact」其實已暗示方向，但設計討論時被 Phase 6 design doc §6.A「21d xwOBACON fetch（savant_rolling.py 擴充）」的「擴充」一字誤導為「新 endpoint」。

**教訓**：開新 endpoint 前先看現有 fetch 的 raw data 包含什麼。Pitch-level CSV 含 `estimated_woba_using_speedangle` 已是最細粒度，aggregate 端可衍生任何 contact-quality 指標。這個 lesson 也適用未來其他 v4 metrics（如 xISO, xSLG）：很可能也是 aggregate-side derivable，不必新 endpoint。

---

## 6. Action items（下次 cutover 動工時）

- [ ] `daily-advisor/savant_rolling.py:_aggregate_pitches()` 加 `xwobacon` 計算（line 159 result dict 後 4 行）
- [ ] `daily-advisor/tests/` 加 `test_savant_rolling.py` 涵蓋 §4.3 4 個 case
- [ ] 驗證一位 SP（Skubal/Skubal）跑全季 vs `backfill_prior_stats_v4.py` 抓的 custom leaderboard `xwobacon` 對齊（差距 ≤0.005）
- [ ] `fa_scan.py` 不需動（dict pass-through）；v4 cutover 時 `fa_compute._factor_rolling` 讀此欄位
- [ ] CLAUDE.md TODO「21d xwOBACON fetch」更新為「已擴充 _aggregate_pitches」+ remove 假設「新 endpoint」描述

---

## 7. 不變的部分

- `statcast_search/csv` endpoint 規格 — 不變
- `_fetch_player_pitches()` 邏輯 — 不變
- savant_rolling cron schedule（TW 12:00）— 不變
- `savant_rolling.json` 既有 schema — 不變（只追加 `xwobacon` 欄位，向下相容）
- batter 線（14d xwoba rolling）— 完全不影響
