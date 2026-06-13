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

## 開工必讀（來自 #320 三審）

- **execution timestamp 沒有 writer — 051 首要工作是決定來源**：`LedgerEntry.executed_ts` 欄位存在但 **production 無任何程式寫它**（041 gate 只用 roster 名單比對判 executed）。兩條路：① 051 自建 writer（如 roster_sync 在球員落地 roster 時 stamp ledger）；② 直接用既有 `_backtest_lib.judge_executed().matched_date`（roster_config git 時間線，`EXECUTION_GRACE_DAYS=3`）當執行日，把 executed_ts 視為 vestigial。**推薦 ②**（不另建 writer，沿用已驗證的 git 時間線）。「觸發→執行延遲中位數」KPI 靠這個算。
- **stars 已備**（318a 寫進 ledger entry），star-bucket 命中率輸入就緒。但 **5★ 在 318b 前 unreachable**（established cap 4★）→ star-bucket 對帳初期只有 ≤4★ 分桶，5★ 桶要等 318b 觸發評估上線才有資料。
- **episode 切分要 051 自建**：`all_histories()` 給的是逐日 raw rows，不是去重 episode。KPI（觸發→執行中位、regret add→drop→再推薦）需要 episode 邊界（首次觸發日 per verdict run）+ regret-loop 偵測，041 的 gate 只給「當前未執行」現況視圖，不給歷史 episode 重建。比照既有 `_backtest_lib` 的相鄰同 verdict 去重。

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`
- Blocked by `issues/040-star-rating.md`
- Blocked by `issues/041-gate-notify.md`

## User stories addressed

- User story 19
- User story 21
