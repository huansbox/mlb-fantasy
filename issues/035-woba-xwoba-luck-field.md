# 035 — wOBA−xwOBA 運氣欄位 + 2025 分布門檻推導

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「Payload 誠實度」運氣欄位）

## What to build

打者版的運氣量化訊號（對稱 SP 端既有的 xERA−ERA luck tag）：season 與 14d 各補 wOBA−xwOBA gap 數字進 payload，讓「實際 vs 預期」量化、BABIP 噪音 vs 真品質變化不再靠 LLM 從 AVG 腦補。顯著門檻由 2025 全季分布推導（沿用既有百分位計算腳本模式），低 BBE 抑制（避免崩盤中誤判，仿 SP 端 BBE gate 前例）。

## Acceptance criteria

- [x] season + 14d wOBA−xwOBA gap 欄位進 payload（方向標註：正 = 實際優於預期 = 運氣偏多；payload 開頭 legend 行 + Season 行 `運氣 {gap:+.3f}(顯著)` + 14d Savant 行 `運氣 {gap:+.3f}`）✅ 2026-06-10
- [x] 顯著門檻由 2025 分布推導（`calc_woba_gap_pctiles.py`，bip ≥50 n=486：|gap| P50 0.014 / P70 0.023 / P90 0.040 → 門檻 0.023），記錄於 CLAUDE.md 百分位表同處 ✅ 2026-06-10
- [x] BBE 低於門檻時抑制標記（season <40 整欄不顯示；14d 沿用行 gate 15，且只列值不標顯著 — 季分布門檻對 14d 噪音基底不可比）✅ 2026-06-10
- [x] gap 計算 + 門檻判定純函式單測（`compute_woba_gap` 8 cases）；格式函式回歸（`test_woba_luck_field.py` 11 cases + `test_savant_rolling.py` woba 3 cases）✅ 2026-06-10
- [ ] 部署後隔日 issue payload 可見 — ⏳ 6/11 12:30 cron 後驗證（注意：我方 roster 的 14d 運氣需 VPS savant_rolling cron（TW 12:00）先以新 code 跑過一輪才有 woba 欄；FA 端 `_fetch_fa_rolling` 即時計算當天即有）

> 實作備註（2026-06-10，merge `8a651ae`）：season woba 來源 = expected_statistics CSV `woba` 欄（`_extract_savant_row` 順手抽，零額外 API）；14d woba = statcast_search 逐球 CSV `woba_value/woba_denom` 聚合（`_aggregate_pitches`）。

## Blocked by

None - can start immediately

## User stories addressed

- User story 22
