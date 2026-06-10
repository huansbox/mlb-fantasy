# 030 — 裁判合議端到端（HITL）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」裁判合議契約 + 觀察類鏡像判定）

## What to build

把 `issues/029` 骨架的 `pending-judge` 升級為合議判定：整週帳打包成 payload（純函式）→ 兩位 LLM 裁判各 1 次 claude -p 呼叫（同一份指示、自 neutral cwd）→ 強制二選一 +「明顯/勉強」標註 → 合議純函式收斂 → 週報輸出 採用/難分 判定，機械比數底稿並列保留作稽核。觀察類帳走鏡像方向（Y 明顯較好 = 看走眼太保守；難分或 X 較好 = 看對）。

HITL 點：裁判 prompt 是新的 LLM 用法，第一批輸出必須人工抽查、對照機械比數底稿 — 系統性唱反調 → 回頭修裁判 prompt（PRD §Further Notes 風險備忘）。

## Acceptance criteria

- [x] 週帳打包 payload builder 為純函式：raw 六類別產出（無 SB、無 PA），兩位裁判同一份指示 — `_backtest_lib.build_judge_payload`（匿名 A/B、claim-blind：無姓名/帳種/PA/G，單測斷言 payload 不洩漏）
- [x] 裁判輸出契約結構化可解析：每筆帳 = 選誰（強制二選一，不准棄權）+ 明顯/勉強 — `parse_judge_response`（棄權值/缺帳/多帳/重複帳/壞 margin 全判 contract violation → None）
- [x] 合議純函式組合窮舉單測：同人+至少一明顯=採用 / 同人+雙勉強=難分 / 分歧=難分 — `judge_consensus`，16 種組合全窮舉
- [x] 觀察類鏡像方向正確：撿人帳與觀察帳的 hit/miss 對應表分開驗證 — `map_judge_outcome`（replace 3 cases + watch 鏡像 3 cases；watch 難分 → hit 計入分母）
- [x] claude -p 呼叫每週固定 2 次（打包、非逐筆），自 neutral cwd — `run_judge_panel` 整週 1 payload × 2 judges（單測斷言 N 帳仍 2 calls）；`_claude_judge_runner` 走 `_multi_agent.run_single_agent`（lever 1a neutral cwd）；契約違反各 1 retry，連續失敗 fail-open 留 pending-judge
- [x] 週報 pending-judge 全數升級為合議 verdict；機械類別比數並列保留 — 每帳行並列「機械比數 + J1/J2 判定 + 合議 + outcome」；新增命中率行（replace 量太衝動 / watch 鏡像量太保守）
- [x] 第一批裁判輸出人工抽查通過（vs 機械比數無系統性唱反調）— 2026-06-10 真 claude demo（`_tools/_judge_demo_runner.py`，真實 05-15→06-04 MLB 產出）：Pederson vs Arraez（機械 4W-2L）雙裁判 A·明顯 → replace hit；Clemens vs Arraez（機械 1W-4L-1T）雙裁判 B·明顯 → watch 鏡像 hit。零 retry、契約全合規、與機械比數方向一致。**殘留觀察項：首個非空 production 週日段（預期 2026-07-05）再人工抽查一次**（demo 皆明顯案例，勉強/難分路徑尚未被真裁判走過）

## 實作備註（2026-06-10 完工）

- **純函式層（`_backtest_lib.py`）**：`build_judge_payload` / `parse_judge_response` / `judge_consensus` / `map_judge_outcome`；**Sum 同款哲學 — 機械比數不暴露給裁判**，裁判只看 raw 六類別。
- **邊界層（`backtest_batter.py`）**：`run_judge_panel`（mutate rows in place；scorecard 缺 → `no-data`）+ `_claude_judge_runner` + `aggregate_outcome_by_kind`。`run_weekly_summary` 的 `_judge_runner=None` 預設 = skip（library/測試永不 subprocess claude），CLI 預設接真 runner、`--no-judge` 跳過。
- **VPS 部署**：零動作 — `cron_backtest.sh` 開頭 git pull 自動帶上；cron entry 已含 `PATH=/root/.local/bin`（claude 所在，2026-06-10 實機驗證）。
- **失敗模式**：panel fail（單裁判 2 attempt 全違約）→ outcomes 留 pending-judge + 週報 ⚠️ 行；該批帳會老化出 [21,28) 窗，需 `--age-min/--age-max` 手動補判。
- 測試：`tests/test_judge_panel.py` 31 cases。裁判 response fixture 為 synthetic（新 LLM 契約無 production archive 可取 — 真實 fixture 鐵律適用對象是 issue body 解析，該側 test_backtest_batter 已用真 fixture 覆蓋）；以真 claude demo 補位驗證。

## Blocked by

- Blocked by `issues/029-batter-backtest-skeleton.md`（✅ 2026-06-10 完工 — 本片已解鎖）
- ⚠️ 軟衝突（非依賴 — 與 031 順序仍可互換）：兩片都會動 `backtest_batter.py` 同兩處；031 規劃走雲端 Claude Code（PR 產出）— **不要與 031 同時動工**，建議先 merge 031 再開本片（詳見主 issue Handoff）

## User stories addressed

- User story 1（命中率 — 完整判定）
- User story 6（合議 + 幅度標註 + 難分空間）
- User story 7（稽核底稿對照）
- User story 8（觀察鏡像、太衝動 vs 太保守）
- User story 27（合議純函式）
