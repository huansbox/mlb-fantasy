## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

決策記事本的深核心模組 — 唯一封裝「每球員歷次判斷 + 當初撿人理由 + 發現路徑」的持久層，穩定介面供所有下游消費端讀寫。

對外介面（凍結，後續片不得改）：
- `record(player, verdict, add_reason, channel, ts, stars=None)` — 寫一筆 ledger entry
- `get_history(player) → [LedgerEntry]` — 讀某球員時序判斷史

封裝：JSON 持久化 IO + 與 waiver-log 同一寫入點（`apply_waiver_log_block`）derive 的單一真相源 + 同日同 verdict dedup。**不含** payload 注入、發現路徑分類、行數預算、backfill（那些是 039 的薄消費端）。

**032 分工裁定**：ledger 為 gate 計數的權威來源；既有 `compute_history_counters` 產出的 `[機械計數]` 行短期照舊運作（同寫入點 derive，避免雙套計數打架），長期改讀 ledger。本片不動 032，只確立 ledger 寫入點與 032 共存不衝突。

詳見 PRD Implementation Decisions「decision_ledger 深核心」。

## Acceptance criteria

- [ ] `record` / `get_history` 純介面 + JSON 持久化，與 waiver-log 寫入點同步 derive（不另開第二寫入路徑）
- [ ] 同日同 verdict dedup，時序正確
- [ ] 單元測試：注入 clock/fs，覆蓋寫入、讀取、dedup、空歷史（house style：rp_svh_scan 注入式）
- [ ] 與既有 032 `compute_history_counters` 並存無衝突（同寫入點，不重複計數）— 真實 waiver-log fixture 回歸
- [ ] 介面凍結文件化（039/040 依賴它，不得在後續片變更簽章）

## Blocked by

None - can start immediately（037 已部署）

## User stories addressed

- User story 1
- User story 7
- User story 9
