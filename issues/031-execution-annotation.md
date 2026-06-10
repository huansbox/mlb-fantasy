# 031 — 執行標註（executed vs not 分組命中率）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」執行標註）

## What to build

每筆對帳紀錄補「是否實際執行」標註：由名單設定檔的 git 歷史機械判定（建議日後短窗內 add 對象是否進入我方名單），不靠人工。週報加 executed / not-executed 分組命中率 — 量「用戶人工否決是在加值還是誤殺好建議」。

## Acceptance criteria

- [ ] 執行判定為純函式（注入 git 歷史數據），單元測試覆蓋：執行 / 未執行 / 邊界（同名、延遲生效）
- [ ] 每筆帳在對帳紀錄含 executed 欄位
- [ ] 週報出現 executed / not-executed 分組 hit-rate
- [ ] 對歷史真實案例 spot-check 標註正確（如近期實際 add 過的球員）

## Blocked by

- Blocked by `issues/029-batter-backtest-skeleton.md`（✅ 2026-06-10 完工 — 本片已解鎖，可與 `issues/030` 平行）

## User stories addressed

- User story 9
