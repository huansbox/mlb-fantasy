# 029 — batter 對帳骨架端到端（機械底稿 + cron）

> **狀態：✅ 完工 merge 2026-06-10（merge `0e94cf7`）**。對真實 archive dry-run 過（42 天 ~80 份 issue body 零誤報、輸出「0 筆可對帳」段）。曆法：首筆新文法帳 06-11 產生，首個可能非空週日段 = **2026-07-05**。待辦移交：06-11 後補一份真實 production 新文法 issue fixture 進 `test_backtest_batter.py`（目前以 028 配對 A/B 的真實 LLM 輸出代位）。

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」+「上線順序的硬約束」）

## What to build

batter 決策對帳的完整垂直骨架：從 issue 存檔抽取 verdict episodes（讀 `issues/028` 的新文法，重用 `issues/027` 的 episode 去重函式）→ 21 天窗口六類別實際產出聚合（R/HR/RBI/BB/AVG/OPS，無 SB，MLB gameLog 日期窗）→ 機械類別比數底稿 → 週報 append 到獨立 batter 對帳 doc → 掛進既有週日 cron 班次（一次跑 SP + batter）。

骨架階段 outcome 一律標 `pending-judge`（裁判合議由 `issues/030` 升級）。**初期資料未熟時輸出「0 筆可對帳」也是合格 demo** — tracer bullet 哲學：骨架第一次就打穿到部署。

## Acceptance criteria

- [x] 從真實 issue 存檔抽出 batter verdict episodes：ACTION / NEW 行含 vs 對象，episode 去重重用 027 共用函式（`_backtest_lib.dedupe_episodes`；取代/立即取代強度不拆帳）
- [x] 只取「取代/立即取代」+「觀察」兩類帳（PRD §C2 定案）；帳齡 21-28 天窗口、每筆恰對一次（UPDATE / CLOSE / 舊 6 欄 NEW 不可對帳）
- [x] 六類別 21 天實際產出由 MLB 日期窗聚合（add 對象 vs drop 對象兩側）— 實作走 person `byDateRange`（gameLog 的服務端日期窗聚合，repo 既有 pattern）；重複相同 splits API quirk 去重 + 跨隊交易比率重算
- [x] 機械類別比數底稿產出（贏 X 輸 Y 平 Z），outcome 標 `pending-judge`
- [x] 週日 cron 擴充為一次跑 SP + batter（`cron_backtest.sh`，單邊失敗仍 commit 健康側）；batter 週報自動 append + commit 到獨立 `docs/batter-decisions-backtest.md`
- [x] 資料未熟時輸出「0 筆可對帳」section（cron 正常 append）即為合格 demo — 2026-06-10 本機對真實 archive dry-run 驗證
- [x] 純函式層（抽取 / 聚合 / 比數 / 帳齡）單元測試（41 cases）；解析 fixture 用真實 issue body（#306 pre-028 零誤報）+ 028 A/B 真實 LLM 輸出（production 新文法 fixture 待 06-11 後補）；MLB API 注入式

## Blocked by

- Blocked by `issues/027-sp-backtest-repair-e2e.md`（共用去重函式 + 帳齡邏輯）
- Blocked by `issues/028-waiver-log-grammar-extension.md`（verdict 來源文法；且部署後需 21 天資料成熟期才有第一筆可對的帳）

## User stories addressed

- User story 1（命中率基線 — 骨架部分）
- User story 3（帳齡）
- User story 4（去重）
- User story 5（六類別實際產出）
- User story 7（機械比數底稿）
- User story 10（週日自動週報）
- User story 25（真實 fixture)
- User story 27（純函式 + 注入邊界）
