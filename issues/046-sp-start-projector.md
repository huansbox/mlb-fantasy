## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

SP 下週先發場次投影 — 推算每位 SP 候選/被換者下週投 {0,1,2} 場 + payload 行，讓「量」成為 SP 換人的第一排序鍵（IP/QS/K/W 全隨場次線性放大），並機械化週四 Min-40-IP 檢查。

機制：輪值 cadence（game log 最後先發日 + 中位休息天）+ 球隊賽程 forward walk + probables 確認 → 場次數。核心為注入式純函式（schedule/probable 注入）。fetcher 復用 stream_sp_scan / mlb_query。per-start 產出向量留給 048。

詳見 PRD Implementation Decisions「sp_start_projector」。

## Acceptance criteria

- [x] 場次投影核心為純函式，schedule/probable 注入式（可離線測）
- [x] 輸出域 {0,1,2}，doubleheader / skip / 六人輪值邊界處理
- [x] retro 驗收 gate（2026-07-07，192 SP × 14 週 = 2354 cells）：**85.3%**（production config：probable 錨定 walk + 球隊比賽日 staleness slack 0 + per-team horizon-absence；日曆協議 85.0%）。基線 66.0% → 三規則各 +9pp / 修 probable 重複計數 / +1.5pp
- [x] 單元測試：cadence 推算 + 賽程 walk + probable 覆蓋 + staleness/horizon/gap-game-days（30 tests）
- [x] payload 注入（318b B6 merge `7ecdfd1`）：`next_week_starts` dict，受 039 payload_budget 守門；窗口 = 明天 ET 起算當週剩餘（Daily-Tomorrow 語意，過去場次不計）

## Blocked by

None - can start immediately

## User stories addressed

- User story 12
