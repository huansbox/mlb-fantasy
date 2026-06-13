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

- [x] `record` / `get_history` 純介面 + JSON 持久化，與 waiver-log 寫入點同步 derive（`derive_ledger_records` 讀同一 block，wiring 在 `_update_waiver_log_locked` best-effort，不另開第二寫入路徑）
- [x] 同日同 verdict dedup-merge（idempotent + 非 None 欄位合併供 039 enrich），不同 verdict 同日 append，跨日時序正確
- [x] 單元測試：注入 path/clock，25 cases 覆蓋寫入/讀取/dedup/merge/空檔/持久化/derive 文法+precedence
- [x] 與既有 032 `compute_history_counters` 並存無衝突（ledger 走獨立 JSON、不碰 markdown）— 真實 waiver-log fixture 共存測試
- [x] 介面凍結（`record(player, verdict, ts, add_reason, channel, stars)` / `get_history(player)`，docstring 標注 039/040 不得改簽章）

## 狀態

✅ 完成（merge `ec832fd`）+ **三審硬化（`49e9741`）**。模組 `daily-advisor/decision_ledger.py`，production 已運作（cron 已記 13 球員，git tracked）。

三審（#317/#319）修正：
- **Bug 1（單一真相源）**：改由 `apply_waiver_log_block` 的 state-aware `ledger_sink` emit verdict（只在真正改 markdown 時），消除「skip 球員仍記幽靈 verdict」。取代原純文法 deriver。
- **dedup 反向掃描**：找匹配 (ts, verdict) 列而非只看最後一列 → 039 同日 enrich 不被中間的 distinct verdict 打斷。
- **凍結介面補強**：加 `executed_ts` 欄（051 用）+ `first_channel()` helper（039 永不重判用）。
- **corrupt ledger**：改 Telegram 警報，不再無聲永久跳過。
- 29 ledger tests（含 sink state-aware 邊界 + 真實 fixture 共存），834 全綠。

## Blocked by

None - can start immediately（037 已部署）

## User stories addressed

- User story 1
- User story 7
- User story 9
