# 執行中計畫

> 快照日期：2026-08-05。**Source of truth = repo `CLAUDE.md` 待辦段 + GitHub [#316](https://github.com/huansbox/mlb-fantasy/issues/316) 進度看板**，本頁為導覽快照，衝突時以 repo 為準。

## 現況：工程投資暫停，降級運作

Yahoo 於 2026-07-28 撤銷本專案的 API 存取後，**所有以 Yahoo 資料為輸入的開發線都無法推進也無法驗證**。本季賽績已無望（季後賽 4 隊，Week 24-25），因此不做趕工，改為維持不依賴 Yahoo 的日報單線運作。

當前唯一的主動事項是**等一個外部答案**，見下方決策點。

## 決策點：Yahoo API 申請（2026-08-19 後回查）

已決定**先不送新申請**，改用社群回報當判斷依據。

- **回查動作**：看 [uberfastman/yfpy#84](https://github.com/uberfastman/yfpy/issues/84) 有無人回報新制申請成功 — 有個人開發者於 2026-07-29 用 App ID 綁定既有 app 送件，8/19 滿 3 週（= 目前唯一已知核准案例的審核週期）
- **判準**：有人成功 → 參考其填法再決定是否送；仍無人成功 → 認定個人開發者已被排除，關掉這條路
- **先不送的理由**：截至 2026-08-05 全網 0 個成功案例；唯一走完新制的專案（企業身分）拿到 credentials 用了 7 週後同樣被斷。等待成本為零

## 凍結中的開發線

以下全部因 Yahoo 中斷而停在原地，程式碼與設計文件皆已 merge，等平台恢復即可續跑：

| 項目 | 停在哪 |
|---|---|
| fa_scan 決策執行層 + 量修復（[#316](https://github.com/huansbox/mlb-fantasy/issues/316)，14 切片） | 14 片實質收官，唯一開放 #321（暫緩）。規格見 [`issues/prd-decision-execution.md`](https://github.com/huansbox/mlb-fantasy/blob/master/issues/prd-decision-execution.md) |
| fa_scan batter 判斷品質（027-037） | 11 片全 merge + C1 對帳回路 production 驗證完成（2026-07-08）。剩 037 觸發 schema 的被動 spot-check |
| `/emerging-batter` + deep skill | Step 1 機械層完成（TDD 40 tests）；Step 2-7 未做。見 [`docs/emerging-batter-design.md`](https://github.com/huansbox/mlb-fantasy/blob/master/docs/emerging-batter-design.md) §落地進度 |
| Backtest Use Case B（xwOBACON 校準） | 等數據累積 — 而 Yahoo 中斷後不再產生新 verdict，計時實質暫停 |
| 百分位表 2026 化 | 逾期未做（見 [Tech-Debt](Tech-Debt)）；`calc_percentiles_2026.py` 已備好 |

## 仍在運作的線

- **日報**：2026-08-05 改為行動清單格式（今天不要上 / 今天可以上 / SP），全文 10 行內，讀者只需執行不需判斷
- **日報健康檢查**：heartbeat 48h 門檻 + Telegram 警告，防止日報再次靜默停擺
- 兩者都只吃 MLB Stats API + Baseball Savant，不受 Yahoo 影響

## 被動觀察

- 日報首班自動執行（2026-08-06 TW 05:30）與後續品質
- 健康檢查首次自動執行（2026-08-06 TW 07:00）應回 OK
- `roster_config.json` 凍結於 2026-07-22 — 若人工做過名單異動，日報建議會有偏差，需人工同步

## 開工守則

1. 動任何 Yahoo 相關的線之前，先確認平台狀態（本頁決策點）
2. 開工先讀 GitHub [#316](https://github.com/huansbox/mlb-fantasy/issues/316) 看板或對應 PRD 的「進度看板」段
3. 完工回寫狀態到同一看板
