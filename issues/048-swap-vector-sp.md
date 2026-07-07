## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

SP 換人逐類別週差額表 + per-start 產出向量。對 4★+ SP 候選輸出「vs 指名 incumbent」的逐 pitcher 類別週 delta（IP/W/K/QS/ERA/WHIP/SV+H）。

機制：per-start 產出向量（IP/GS、K=K9×IP/GS/9、QS 率、W≈隊勝率×係數、ER for ERA/WHIP）× 046 的下週先發場次 → 走 043 weekly_projection → 候選與 incumbent 相減。**只對 4★+ emit**。

詳見 PRD Implementation Decisions「swap-SP」。

## Acceptance criteria

- [x] per-start 產出向量 + 逐類別週 delta 純函式（吃 046 場次 + 043 算術）— `swap_sp.py`
- [x] 只對 4★+ 候選 emit（SP stars = 318b B6 新增 ledger_enrich SP wiring），受 039 payload_budget 獨立 swap pool 守門（merge `7ecdfd1`）
- [x] 單元測試：per-start 向量 + 場次乘算 + 差額 + 4★ gate
- [x] 回溯抽樣：live smoke（Skubal↔Messick swap line 方向與量級合理；stale SP 正確不 emit）

## Blocked by

- Blocked by `issues/043-weekly-projection-arithmetic.md`
- Blocked by `issues/046-sp-start-projector.md`
- Blocked by `issues/040-star-rating.md`

## User stories addressed

- User story 12
- User story 13
