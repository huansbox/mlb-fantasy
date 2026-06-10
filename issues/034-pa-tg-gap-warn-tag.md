# 034 — PA-TG 落差警示 tag（platoon 陷阱輕版攔截）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「Payload 誠實度」PA-TG 落差警示）

## What to build

FA 與其比較 anchor 的上場量（PA/Team_G）差距達門檻（初版 ≥1.0）時，機械層打 ⚠️ 警示 tag 進 payload — 攔截「品質好但上場少」的換人建議（實證案例：建議用平台型打者換每日先發，週 PA 量 -28% 無人處理）。這是 platoon 訊號的輕版；vs L/R splits 重版為 Out of Scope 另案。

## Acceptance criteria

- [x] tag 計算為純函式（落差 ≥1.0 → ⚠️），單測含邊界（剛好 1.0 / 任一側缺 PA-TG / 落差反向不打）✅ 2026-06-10
- [x] Pederson 型 fixture 驗證：FA PA-TG 3.06 vs anchor 4.27 → 打出警示 ✅ 2026-06-10
- [x] tag 納入 payload 顯示（batter 路徑 warn_tags 直通 `_fmt_fa_block_batter_v4` minimal_tags；payload_slimmer whitelist 為 SP-only 不適用）✅ 2026-06-10
- [ ] 部署後隔日 issue payload 對符合條件的 FA 可見該 tag — ⏳ 6/11 12:30 cron 後驗證

> 實作備註（2026-06-10，merge `57abeec`）：`fa_compute.pa_tg_gap_warn` 純函式（tag 內嵌數值 `⚠️ 上場量落差 (PA-TG 3.06 vs anchor 4.27)`）；wire 在 `compute_fa_tags`，win gate 兩側都打（誠實 tag 不受 gate 影響，watch/pass 條目也可見）；屬一般 ⚠️（非 strong）→ 擋 立即取代、不強制 觀察。已知侷限（B3，036 處理）：anchor 固定 vs P1。

## Blocked by

None - can start immediately

## User stories addressed

- User story 21
