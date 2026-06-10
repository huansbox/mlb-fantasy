# 035 — wOBA−xwOBA 運氣欄位 + 2025 分布門檻推導

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「Payload 誠實度」運氣欄位）

## What to build

打者版的運氣量化訊號（對稱 SP 端既有的 xERA−ERA luck tag）：season 與 14d 各補 wOBA−xwOBA gap 數字進 payload，讓「實際 vs 預期」量化、BABIP 噪音 vs 真品質變化不再靠 LLM 從 AVG 腦補。顯著門檻由 2025 全季分布推導（沿用既有百分位計算腳本模式），低 BBE 抑制（避免崩盤中誤判，仿 SP 端 BBE gate 前例）。

## Acceptance criteria

- [ ] season + 14d wOBA−xwOBA gap 欄位進 payload（方向標註：正 = 實際優於預期 = 運氣偏多）
- [ ] 顯著門檻由 2025 分布推導，推導結果與門檻值記錄於 doc（百分位表同處）
- [ ] BBE 低於門檻時抑制標記
- [ ] gap 計算 + 門檻判定純函式單測；格式函式 fixture 回歸
- [ ] 部署後隔日 issue payload 可見

## Blocked by

None - can start immediately

## User stories addressed

- User story 22
