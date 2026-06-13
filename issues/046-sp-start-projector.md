## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

SP 下週先發場次投影 — 推算每位 SP 候選/被換者下週投 {0,1,2} 場 + payload 行，讓「量」成為 SP 換人的第一排序鍵（IP/QS/K/W 全隨場次線性放大），並機械化週四 Min-40-IP 檢查。

機制：輪值 cadence（game log 最後先發日 + 中位休息天）+ 球隊賽程 forward walk + probables 確認 → 場次數。核心為注入式純函式（schedule/probable 注入）。fetcher 復用 stream_sp_scan / mlb_query。per-start 產出向量留給 048。

詳見 PRD Implementation Decisions「sp_start_projector」。

## Acceptance criteria

- [ ] 場次投影核心為純函式，schedule/probable 注入式（可離線測）
- [ ] 輸出域 {0,1,2}，doubleheader / skip / 六人輪值邊界處理
- [ ] retro 驗收 gate：對季初至今逐週「用當週一可得資料投影 vs 實際 game log」準確率 ≥85%（機器可判）
- [ ] 單元測試：cadence 推算 + 賽程 walk + probable 覆蓋
- [ ] payload 行注入，受 039 payload_budget 守門

## Blocked by

None - can start immediately

## User stories addressed

- User story 12
