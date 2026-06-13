## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

共用的「週投影算術」深模組 — 把 per-PA / per-start rate 乘上投影量，產出逐類別週期望向量。三個下游片（045 P-b PA 投影、047 swap-batter、048 swap-SP）共用同一份算術，避免各寫一遍。

對外介面（凍結）：`project(rates: dict, volume) → {category: expected}`，輸入 per-unit rate 與投影量，輸出 7×7 各 counting 類別的週期望（ratio 類別走 volume-damped 變體）。

純函式、零 fetch、零 LLM。**前置於 045**（修正原稿把算術埋在 swap-batter 內、導致 045 P-b 需要尚未建出模組的潛在順序 bug）。

詳見 PRD Implementation Decisions「weekly_projection 共用算術深模組」。

## Acceptance criteria

- [ ] `project()` 純函式，counting 類別線性、ratio 類別 volume-damped
- [ ] 介面凍結（045/047/048 依賴）
- [ ] 單元測試：邊界（量=0、缺 rate 欄、ratio vs counting 分支）
- [ ] 無任何 fetch / 外部依賴（可離線測）

## Blocked by

None - can start immediately

## User stories addressed

- User story 11
- User story 13
