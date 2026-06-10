# 032 — payload 觀察歷史截斷 + 機械 counter 摘要行

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「機械工作回收」）

## What to build

payload 組裝時對 waiver-log 觀察歷史做讀取端機械截斷：每條觀察保留觸發條件 + 里程碑（[eval]）行 + 最近 5 天，其餘以一行「中略 N 行」標記；同時注入機械 counter 摘要行（counter day X/N、已連續建議結案 N 天等），LLM 只引用不計算。waiver-log.md 檔案本身不動。零 prompt 變動（純機械裁切，無 lever 2 thinking induction 風險）。

A/B 已實證（payload doc）：payload −45.9% chars、cost −17%、核心決策不變；摘要行正是「長歷史觸發紀律弱化」的品質緩解。

## Acceptance criteria

- [ ] 截斷純函式：觸發 + [eval] + 最近 5 天保留，其餘「中略 N 行」；TDD 含邊界（不足 5 天 / 無 [eval] 行 / 空條目）
- [ ] counter 摘要行由程式從條目歷史推導注入，格式固定
- [ ] waiver-log.md 檔案內容不變（僅讀取端裁切）
- [ ] 真實 payload fixture 配對驗證：截斷正確 + 總字元數下降可量測
- [ ] prompt 檔零變動

## Blocked by

None - can start immediately（軟排序：建議在 `issues/028` 部署後重測省幅 — 結案自動化會先縮小歷史段）

## User stories addressed

- User story 14（計數機械化 — counter 摘要行）
- User story 15（歷史截斷）
