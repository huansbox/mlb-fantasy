# 030 — 裁判合議端到端（HITL）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」裁判合議契約 + 觀察類鏡像判定）

## What to build

把 `issues/029` 骨架的 `pending-judge` 升級為合議判定：整週帳打包成 payload（純函式）→ 兩位 LLM 裁判各 1 次 claude -p 呼叫（同一份指示、自 neutral cwd）→ 強制二選一 +「明顯/勉強」標註 → 合議純函式收斂 → 週報輸出 採用/難分 判定，機械比數底稿並列保留作稽核。觀察類帳走鏡像方向（Y 明顯較好 = 看走眼太保守；難分或 X 較好 = 看對）。

HITL 點：裁判 prompt 是新的 LLM 用法，第一批輸出必須人工抽查、對照機械比數底稿 — 系統性唱反調 → 回頭修裁判 prompt（PRD §Further Notes 風險備忘）。

## Acceptance criteria

- [ ] 週帳打包 payload builder 為純函式：raw 六類別產出（無 SB、無 PA），兩位裁判同一份指示
- [ ] 裁判輸出契約結構化可解析：每筆帳 = 選誰（強制二選一，不准棄權）+ 明顯/勉強
- [ ] 合議純函式組合窮舉單測：同人+至少一明顯=採用 / 同人+雙勉強=難分 / 分歧=難分
- [ ] 觀察類鏡像方向正確：撿人帳與觀察帳的 hit/miss 對應表分開驗證
- [ ] claude -p 呼叫每週固定 2 次（打包、非逐筆），自 neutral cwd
- [ ] 週報 pending-judge 全數升級為合議 verdict；機械類別比數並列保留
- [ ] 第一批 production 裁判輸出人工抽查通過（vs 機械比數無系統性唱反調）

## Blocked by

- Blocked by `issues/029-batter-backtest-skeleton.md`（✅ 2026-06-10 完工 — 本片已解鎖）
- ⚠️ 軟衝突（非依賴 — 與 031 順序仍可互換）：兩片都會動 `backtest_batter.py` 同兩處；031 規劃走雲端 Claude Code（PR 產出）— **不要與 031 同時動工**，建議先 merge 031 再開本片（詳見主 issue Handoff）

## User stories addressed

- User story 1（命中率 — 完整判定）
- User story 6（合議 + 幅度標註 + 難分空間）
- User story 7（稽核底稿對照）
- User story 8（觀察鏡像、太衝動 vs 太保守）
- User story 27（合議純函式）
