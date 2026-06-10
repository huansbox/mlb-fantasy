# 032 — payload 觀察歷史截斷 + 機械 counter 摘要行

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「機械工作回收」）

## What to build

payload 組裝時對 waiver-log 觀察歷史做讀取端機械截斷：每條觀察保留觸發條件 + 里程碑（[eval]）行 + 最近 5 天，其餘以一行「中略 N 行」標記；同時注入機械 counter 摘要行（counter day X/N、已連續建議結案 N 天等），LLM 只引用不計算。waiver-log.md 檔案本身不動。零 prompt 變動（純機械裁切，無 lever 2 thinking induction 風險）。

A/B 已實證（payload doc）：payload −45.9% chars、cost −17%、核心決策不變；摘要行正是「長歷史觸發紀律弱化」的品質緩解。

## Acceptance criteria

- [x] 截斷純函式：觸發 + [eval] + 最近 5 天保留，其餘「中略 N 行」；TDD 含邊界（不足 5 天 / 無 [eval] 行 / 空條目）— `truncate_entry_history`（中略 marker 按連續 run 折疊，[eval] 無條件保留）
- [x] counter 摘要行由程式從條目歷史推導注入，格式固定 — `compute_history_counters`：`[機械計數] counter day X/N（引自 MM-DD）`（僅引最近 5 個日行內的 token，過窗即視為 stale 不引用，防錨點已換仍引舊計數）+ `[機械計數] 已連續建議結案 N 個掃描日`（從完整歷史算 trailing streak，028 CLOSE 自動化下常態為 0，非 0 = LLM 一直建議卻不發 CLOSE 的警訊）
- [x] waiver-log.md 檔案內容不變（僅讀取端裁切）— 純函式接在 `inject_replace_streaks` 之後、僅 batter payload 組裝路徑（SP 端依 PRD Out of Scope 不動）
- [x] 真實 payload fixture 配對驗證：截斷正確 + 總字元數下降可量測 — 凍結 fixture `waiver_log_2026-06-10.md` 觀察中段 18,295 → 7,366 chars（**−59.7%**）
- [x] prompt 檔零變動

## 實作備註（2026-06-10 完工）

- 18 tests（`tests/test_payload_history_truncation.py`），全套 770 綠。生成歷史行走 `apply_waiver_log_block`（production writer），不手寫樣本。
- 注入順序：`_filter_waiver_log_by_group` → `inject_replace_streaks`（028，從完整歷史算）→ `truncate_watch_history`（032，counter 先從完整歷史推導、再截斷、最後注入 header 後）。028 的 `[機械計數] 已連續推薦取代` 行為非日行，截斷自然保留。
- 截斷常數 `TRUNCATE_KEEP_RECENT = 5`（A/B 驗證值，payload doc 2026-06-10）。
- 日行正則同時吃 `- MM-DD：` 與 `- YYYY-MM-DD：` 兩種真實形式（028 的 `_DATE_LINE_RE` 只吃前者，[eval] 行屬後者）。隊上觀察條目的非日期 bullet（傷情/對策等脈絡行）不算歷史、全保留。

## Blocked by

None - can start immediately（軟排序：`issues/028` 已 2026-06-10 部署 — 建議讓 CLOSE 結案自動化跑一段時間縮小歷史段後，再重測省幅）

## User stories addressed

- User story 14（計數機械化 — counter 摘要行）
- User story 15（歷史截斷）
