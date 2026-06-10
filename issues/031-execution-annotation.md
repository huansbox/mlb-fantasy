# 031 — 執行標註（executed vs not 分組命中率）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」執行標註）

## What to build

每筆對帳紀錄補「是否實際執行」標註：由名單設定檔的 git 歷史機械判定（建議日後短窗內 add 對象是否進入我方名單），不靠人工。週報加 executed / not-executed 分組命中率 — 量「用戶人工否決是在加值還是誤殺好建議」。

## Acceptance criteria

- [x] 執行判定為純函式（注入 git 歷史數據），單元測試覆蓋：執行 / 未執行 / 邊界（同名、延遲生效）— `_backtest_lib.judge_executed`（+ `parse_roster_snapshot`），13 cases 含同名不同 id 不匹配 / 延遲生效 grace 窗 / 窗端點 inclusive / 無 baseline → unknown
- [x] 每筆帳在對帳紀錄含 executed 欄位 — `build_episode_rows` 每 row 帶 `executed`（True/False/None）+ `execution` 詳情（status / matched_date / match_by）
- [x] 週報出現 executed / not-executed 分組 hit-rate — `aggregate_executed_split` + 週報「Executed split」行（030 裁判上線前分母 0 顯示「—」，hit/miss 進分母後自動出現數值）+ 每 episode 行尾執行標記
- [x] 對歷史真實案例 spot-check 標註正確 — Ceddanne Rafaela（06-07 實際 add）→ `executed @ 2026-06-07`；Joc Pederson（被搶未 add）→ `not-executed`；Luis Arraez（長期在籍）→ `already-rostered`（2026-06-10 對真 repo git 歷史驗證）

## 實作備註（2026-06-10 完工）

- **git 邊界**：`backtest_batter.fetch_roster_timeline(since)` — 取 `roster_config.json` 自 `since` 起每個 commit 的快照 + `since` 前最後一個 commit 作 baseline（確立窗前不在籍）。任何失敗（shallow clone 歷史不足 / 非 repo）降級為空 timeline → executed=unknown，**寧可 unknown 不給錯的 False**。
- **執行窗**：episode 首日 → 末日 + 3 天 grace（`EXECUTION_GRACE_DAYS`）— 建議未執行會連日重複，真執行落在 episode 尾附近；grace 涵蓋 waiver claim Daily-Tomorrow 延遲生效（06-02 Buehler 案）。
- **同名防護**：player_id 已解析時只認 mlb_id（search_mlb_id first-hit 同名誤判是已記載的失誤模式）；id 未解析才退 normalized name 比對。
- 測試獨立放 `tests/test_execution_annotation.py`（26 cases，含真 throwaway git repo 整合測試）— 避免與平行開發的 030 在 `test_backtest_batter.py` 撞檔。

## Blocked by

- Blocked by `issues/029-batter-backtest-skeleton.md`（✅ 2026-06-10 完工 — 本片已解鎖，可與 `issues/030` 平行）

## User stories addressed

- User story 9
