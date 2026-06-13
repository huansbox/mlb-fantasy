## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

慢快軌 gate（post-LLM 純函式，零 prompt 變更）+ 通知政策 + weekly-review 未處理清單：

- `gate(history, verdict, stars, owned_trend) → action_level`：放人一律慢軌（連 2 天同 verdict + 須面對原 add 理由）；撿人預設慢軌，5★ 或 %owned 急升走快軌。
- **通知政策**：只有 4★+ 發 Telegram；5★ 未執行逐日升級（「第 N 天未執行」）；搭既有 12:30 scan，零新 cron。
- **「已執行」語意**：以當前 roster_config 為準（roster_sync 15 分保鮮）；waiver pending 期 ≤1 天假升級，文件化不當 bug。
- weekly-review 自動列出「已建議未處理」清單消費端。

詳見 PRD Implementation Decisions「gate + 通知」。

## Acceptance criteria

- [ ] `gate` 純函式：drop 慢軌（連 2 天 + 原 add 理由比對）、add 快軌例外（5★ / owned 急升）
- [ ] 4★+ 才推 Telegram（複用既有 send_telegram）；5★ 未執行逐日升級含天數
- [ ] 「已執行」判定讀當前 roster_config；pending 假升級行為文件化
- [ ] weekly-review 未處理清單消費端
- [ ] 單元測試：慢軌連 2 天邏輯 + 快軌兩例外 + 升級天數計算（注入 history/roster）
- [ ] 上線後一週觀察推播噪音（被動）

## 審查補充（來自 #317/#319 三審，開工必讀）

- **結構型 everyday + 觸發未達的「死區」風險（D2）**：星等標準路徑下，structure + 部分雙年 + 中等上場 + 觸發未達 = 2.0 → 3★ → 不會通知，但這正是 Vargas/Manzardo「看到了卻沒執行」最貴的洞。041 gate 設計要考慮：是否給「structure-led + everyday + 觸發逼近」一個 carve-out（例如降一級門檻或單獨追蹤），不要讓觸發因子單獨把有資格的結構型 everyday 打者壓在通知線下。決策寫進本片。
- **executed 時間戳已備**：038 `LedgerEntry.executed_ts` 欄位已加，5★ 逐日升級 + 051 KPI 直接用，不需再改 frozen 介面。

## Blocked by

- Blocked by `issues/040-star-rating.md`

## User stories addressed

- User story 2
- User story 4
- User story 5
- User story 6
- User story 8
