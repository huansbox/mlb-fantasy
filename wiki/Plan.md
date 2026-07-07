# 執行中計畫

> 快照日期：2026-07-07。**Source of truth = repo `CLAUDE.md` 待辦段 + GitHub [#316](https://github.com/huansbox/mlb-fantasy/issues/316) 進度看板**，本頁為導覽快照，衝突時以 repo 為準。

## 主戰場：fa_scan 決策執行層 + 量修復（#316，14 切片）

規格：[`issues/prd-decision-execution.md`](https://github.com/huansbox/mlb-fantasy/blob/master/issues/prd-decision-execution.md) + `issues/038`-`051`。子 issue #317-#330。

- **關鍵路徑**：#317 decision ledger → #319 機械星等 → #320 慢快軌 gate →（#330 KPI）
- **可立即平行**：#317 / #322 / #323 / #325 / #328 / #329
- **HITL（需人工介入）唯一**：#321
- 已部署地基：037 觸發 schema（merge `585a736`）；#328 引擎兩半已 merge（post-hype + chase/zone-contact delta），剩 payload 注入移交 318b 批
- 318b 進度：batter 注入已 merge + VPS A/B 通過；**剩 B6（SP dict 注入）+ B7（legacy backfill）**；042 暫緩

## 其他 active

| 項目 | 狀態 |
|---|---|
| `/emerging-batter` + deep skill | Step 1 機械層完成（TDD 40 tests）；Step 2-7（skill md / pending 檔 / e2e / 觀察期）未做。見 `docs/emerging-batter-design.md` §落地進度 |
| fa_scan batter 判斷品質（`issues/prd-fa-scan-batter-quality.md`） | 11 切片（027-037），027/028/032/033 已結；C1 backtest 引擎設計已定稿待施工 |
| Backtest Use Case B | 等 4-6 週數據累積後觸發 |
| Week 6-8 百分位表 2026 更新 | 逾期未做（列入技術債） |

## 被動觀察（不需主動施工）

- 週日 backtest cron：027 修復後首個非空 regular 段預期 2026-06-21 起（確認 `docs/sp-decisions-backtest.md` 有新增段）
- `/rp-svh` 作為唯一 RP 週掃 production 途徑
- 假日早報首班（TW 22:30）與 lever 1a 後續班次品質
- **stream-sp 優化批首航觀察**（#404-#408 已於 2026-07-07 全數落地並關閉）：registry 沿用路徑尚未實戰觸發（首航候選被 Sum floor 先擋）；floor cap 首次以 hard rule 進 scan 推薦標準；「機械判 true_starter × registry 記載 role cap」盲邊已入技術債 — 細節見 CLAUDE.md 待辦

## 開工守則

1. 開工先讀 GitHub #316 看板（主戰場）或對應 PRD 的「進度看板」段
2. 完工回寫狀態到同一看板
3. 曆法長竿注意：028 文法擴充部署後 +21 天資料成熟期，batter 才有第一筆可對的帳
