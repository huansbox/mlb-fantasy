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

- [x] `gate` 純函式：drop/replace 慢軌（連 2 天）、add 快軌例外（5★ / owned 急升）— `decision_gate.gate`（owned-rising 快軌已實作，wiring 端 owned_trend 暫 None 待 318b 串接 shape）
- [x] 4★+ 才推 Telegram（複用 send_telegram）；5★ 未執行逐日升級含天數、4★ 升級日通知一次；<4★ 靜默（anti-cry-wolf）
- [x] 「已執行」判定讀 roster_config 名單 + ledger executed_ts；pending（waiver 次日生效）≤1 天假升級已文件化
- [x] weekly-review 未處理清單消費端（`collect_unexecuted` + `weekly_review.collect_unexecuted_recommendations` 注入 review JSON `unexecuted_recommendations`）
- [x] 單元測試：慢/快軌 + 通知門檻 + 5★ 逐日 vs 4★ 一次 + executed 短路 + trailing 天數 + weekly consumer（22 cases，873 全綠）
- [ ] 上線後一週觀察推播噪音（被動）

## 狀態

✅ 完成（`daily-advisor/decision_gate.py`，TDD 27 tests，879 全綠零回歸）+ **三審硬化（#320 review）**。每日通知 wiring 進 `_process_group`（`_notify_gate_actions`，純函式 `_gate_notifications` 可注入測試）；weekly-review consumer 注入 output JSON。

**三審修正**：
- **`escalation_day` bug 修復**：原邏輯讓「4★ 第 1 天 pending、第 2 天 owned 轉 rising」永不通知（兩分支都不中）。改為「fast（5★ 或 owned-rising）= 每日；slow-lane 4★ = day 2 一次」，語意明確化。
- **誠實降調（claims honesty）**，三點寫進 docstring：
  1. **churn 範圍**：gate 慢軌降 churn（drop 經 replace、慢軌需 2 天）；但「drop 須面對原 add 理由」是 **042 prompt 契約**、不是 gate（gate 不讀 add_reason）。
  2. **5★ 在 318a 下 unreachable**（established cap 4★ / day-0 cap 4★）→ 5★ 快軌 + 逐日升級是 **built-but-inert，待 318b 觸發評估**。今天 Vargas 型拿 4★ notify-once，非 5★ 逐日；完整執行洞補救隨 318b 落地。
  3. **executed_ts 無 production writer**（見下 051 註）→ 目前唯一有效「已執行」訊號是 roster 名單比對。
- **D2 死區 carve-out 未做**（刻意，三審確認誠實）：everyday（PA/TG≥3.5）structure 球員 full **與 partial** dual-year 都達 4★（2.5 half-up→4★）；3★ 殘餘僅 mid-PA / dual 全崩的窄角，靜默合理。邊界靠 half-up rounding（已有測試 pin）。

**剩餘**：owned-rising 快軌 shape 串接（gate 已支援，wiring 待 318b）+ 一週推播噪音被動觀察。**318b 噪音懸崖警示**：5★ 變 reachable 後多個滯留 5★ 會每日多行推播，無 cap/decay；若實測吵則加 backoff（記入 039 318b）。

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
