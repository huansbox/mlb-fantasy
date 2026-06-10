# 034 — PA-TG 落差警示 tag（platoon 陷阱輕版攔截）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「Payload 誠實度」PA-TG 落差警示）

## What to build

FA 與其比較 anchor 的上場量（PA/Team_G）差距達門檻（初版 ≥1.0）時，機械層打 ⚠️ 警示 tag 進 payload — 攔截「品質好但上場少」的換人建議（實證案例：建議用平台型打者換每日先發，週 PA 量 -28% 無人處理）。這是 platoon 訊號的輕版；vs L/R splits 重版為 Out of Scope 另案。

## Acceptance criteria

- [ ] tag 計算為純函式（落差 ≥1.0 → ⚠️），單測含邊界（剛好 1.0 / 任一側缺 PA-TG / 落差反向不打）
- [ ] Pederson 型 fixture 驗證：FA PA-TG 3.06 vs anchor 4.27 → 打出警示
- [ ] tag 納入 payload 顯示（含 tag whitelist 若適用）
- [ ] 部署後隔日 issue payload 對符合條件的 FA 可見該 tag

## Blocked by

None - can start immediately

## User stories addressed

- User story 21
