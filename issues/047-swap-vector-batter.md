## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

打者換人逐類別週差額表 — murky middle 的字面解答。對 4★+ 候選輸出「vs 指名 incumbent」的逐類別週 delta（含 PA 欄，讓量損失無法被忽略）。

範例：`swap X→Y/week: BB +2.1, HR +0.4, R -0.8, SB +0.1, AVG -0.006, OPS +0.011, PA -7`。

機制：候選與被換者各走 043 weekly_projection（吃 045 的 PA 投影），相減得逐類別向量。**只對 4★+ 候選 emit**（040 星等預篩，payload 紀律）。

詳見 PRD Implementation Decisions「swap-batter」。

## Acceptance criteria

- [ ] 逐類別週 delta 純函式（候選 − incumbent），含 PA 欄
- [ ] 只對 4★+ 候選 emit（讀 040 星等），受 039 payload_budget 守門
- [ ] 回溯重放：對 2026 全部已執行 swap 回算，Arraez→Pederson 必須被標出（AVG/PA 負向顯著，機器可判）
- [ ] 單元測試：差額計算 + 4★ gate + ratio vs counting

## Blocked by

- Blocked by `issues/043-weekly-projection-arithmetic.md`
- Blocked by `issues/045-pa-projection.md`
- Blocked by `issues/040-star-rating.md`

## User stories addressed

- User story 13
