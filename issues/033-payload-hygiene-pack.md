# 033 — payload hygiene 包（假值修真 + 缺值補齊 + 噪音治理）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「Payload 誠實度」前五項）

## What to build

五個微型修復捆一包（共用同一個 demo 載體 = 隔日 production issue 對照）：① watch 球員 %owned 改取真值 — 既有的逐人 ownership 查詢補 percent_owned 欄位，消除假 0%；② FA prior 行補 PA + 年齡；③ 14d Savant BBE 過低不顯示或標「樣本不足」；④ 兩種 14d 視窗（最近 14 場 vs 日曆 14 天）標註區分；⑤ prompt 加一行「%owned 為 Yahoo 全平台值非本聯盟」靜態說明。

## Acceptance criteria

- [ ] watch 球員 payload 顯示真實 %owned（不在 snapshot top 結果內者亦然），無假 0%
- [ ] FA 候選 prior 行含 PA 與年齡（與我方候選區塊對稱）
- [ ] 14d Savant BBE <15 不印 Δ 或標「樣本不足」
- [ ] 14d trad 與 14d Savant 的視窗差異在 payload 有標註
- [ ] prompt 含 %owned 語意說明一行（靜態資料字典類，非判斷規則）
- [ ] 部署後隔日 issue payload 逐項可見；cost spot-check 無異常（input/output tokens 與前日同量級）
- [ ] 受影響格式函式 fixture 回歸更新

## Blocked by

None - can start immediately

## User stories addressed

- User story 16（%owned 真值）
- User story 17（prior PA + 年齡）
- User story 18（BBE gate）
- User story 19（視窗標註）
- User story 20（%owned 語意說明）
