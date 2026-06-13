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

## Blocked by

- Blocked by `issues/040-star-rating.md`

## User stories addressed

- User story 2
- User story 4
- User story 5
- User story 6
- User story 8
