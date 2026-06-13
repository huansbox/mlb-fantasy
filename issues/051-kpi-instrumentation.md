## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

KPI 對帳接線 — 把四個驗收 KPI 接到既有週日 backtest cron，確保「量得到」（避免重蹈 SP backtest 空殼）。

- 星等寫進 backtest 資料列 + ledger 記執行時間戳。
- 既有週日 cron 計算：star-bucket 命中率（4★/5★ 是否顯著 > 3★）、觸發→執行延遲中位數。
- regret rate（add→drop→系統再推薦回，30 天內）由 ledger 直接可算。
- payload growth 由各片上線前後量測彙總。

跨模組整合片，不強制單測，走 dry-run 驗收（比照 029「0 筆可對帳 = 合格 demo」）。

詳見 PRD Implementation Decisions「KPI 對帳接線」+ Further Notes 驗收 KPI。

## Acceptance criteria

- [ ] backtest 資料列新增 stars 欄 + ledger execution timestamp
- [ ] 既有週日 cron 計算 star-bucket 命中率 + 執行延遲中位數，追加進 backtest doc
- [ ] regret rate 由 ledger 計算（30 天內 add→drop→再推薦回事件數）
- [ ] dry-run 驗收：對帳引擎能讀 stars 欄、0 筆達標窗 = 合格 demo（資料成熟前）
- [ ] 四 KPI 在 weekly-review / backtest doc 可見

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`
- Blocked by `issues/040-star-rating.md`
- Blocked by `issues/041-gate-notify.md`

## User stories addressed

- User story 19
- User story 21
