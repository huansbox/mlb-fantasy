# 029 — batter 對帳骨架端到端（機械底稿 + cron）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」+「上線順序的硬約束」）

## What to build

batter 決策對帳的完整垂直骨架：從 issue 存檔抽取 verdict episodes（讀 `issues/028` 的新文法，重用 `issues/027` 的 episode 去重函式）→ 21 天窗口六類別實際產出聚合（R/HR/RBI/BB/AVG/OPS，無 SB，MLB gameLog 日期窗）→ 機械類別比數底稿 → 週報 append 到獨立 batter 對帳 doc → 掛進既有週日 cron 班次（一次跑 SP + batter）。

骨架階段 outcome 一律標 `pending-judge`（裁判合議由 `issues/030` 升級）。**初期資料未熟時輸出「0 筆可對帳」也是合格 demo** — tracer bullet 哲學：骨架第一次就打穿到部署。

## Acceptance criteria

- [ ] 從真實 issue 存檔抽出 batter verdict episodes：ACTION / NEW 行含 vs 對象，episode 去重重用 027 共用函式
- [ ] 只取「取代/立即取代」+「觀察」兩類帳（PRD §C2 定案）；帳齡 21-28 天窗口、每筆恰對一次
- [ ] 六類別 21 天實際產出由 MLB gameLog 日期窗聚合（add 對象 vs drop 對象兩側）
- [ ] 機械類別比數底稿產出（贏 X 輸 Y 平 Z），outcome 標 `pending-judge`
- [ ] 週日 cron 擴充為一次跑 SP + batter；batter 週報自動 append + commit 到獨立對帳 doc
- [ ] 資料未熟時輸出「0 筆可對帳」section（cron 正常 append）即為合格 demo
- [ ] 純函式層（抽取 / 聚合 / 比數 / 帳齡）單元測試；解析 fixture 用真實 issue body；MLB API 注入式

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
