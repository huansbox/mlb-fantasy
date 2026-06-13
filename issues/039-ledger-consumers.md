## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

decision_ledger 的薄消費端三件 + 全域行數預算守門：

1. **發現路徑分類**：pool assembly 時依候選來源（SCAN_QUERIES / owned risers / watchlist）判定 structure / heat / market / news，**首次接觸時持久化一次**（經 038 `record` 寫入 channel 欄），star 只讀不重判 — 防 heat-led 球員養出季線後洗白。
2. **payload 注入**：經 038 `get_history` 讀出「上次 verdict + 幾天前 + 理由」與「原 add 理由」兩行注入候選 payload。
3. **legacy backfill 一次性腳本**：存量 watchlist 從 git 歷史/觸發文字推回發現路徑（推不出標 unknown）；既有 roster 球員以上線日季線快照充 add 理由 — 上線第一天即保護全名單。
4. **payload_budget 守門模組**（獨立深模組）：`register(slice_id, lines)` / `assert_within(candidate)`，行數預算（每候選 ≤3 新行）是橫跨 7 片的全域不變量，獨立而非埋在 ledger 內。

詳見 PRD Implementation Decisions「ledger 消費端」。

## Acceptance criteria

- [ ] 發現路徑於首次接觸持久化、不重判（heat-led 球員不會因季線成熟洗白為 structure-led）
- [ ] payload 注入 prev-verdict + add-reason 兩行，格式機械可解析
- [ ] legacy backfill 覆蓋率：跑後無「缺 add 理由」的 roster 球員、無「缺 channel」的 watchlist 條目（機器可判）
- [ ] payload_budget `register`/`assert_within` 純函式 + 超限 assert（≤3 行/候選），獨立於 ledger
- [ ] 單元測試：channel 分類四來源 + 注入格式 + backfill 推導 + budget 超限/通過；真實 waiver-log fixture
- [ ] 上線前後量 payload input/output token delta

## 審查補充（來自 #317/#319 三審，開工必讀）

- **發現路徑「永不重判」用 `DecisionLedger.first_channel(player)`**：038 已提供此 helper（回傳最早一筆有 channel 的值）。039 寫 channel 前先查 first_channel，非 None 就沿用，不可重判 — 這是 user story 9 的不變量，務必在這層強制。同日多次 enrich 也不可用不同 channel 覆蓋。
- **day0 路徑選擇是 039 的責任（PRD 未指派，本片補上）**：star `score(factors, day0=?)` 的 day0 由 039 決定，規則 = `day0 = (get_history(player) == [] )` 或「該球員從無觸發驗證過的 entry」。day0=True 走三因子上限 4★（5★ 須經觸發驗證）。把此規則寫進本片 AC + 測試。
- **stars 要回寫 ledger**：039 算完 star 後 `record(..., stars=)` 持久化，供 041/051 直接讀，不重算。

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`

## User stories addressed

- User story 1
- User story 9
- User story 18
- User story 20
