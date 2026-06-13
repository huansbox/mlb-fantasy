## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

平台輪替分類器 — 偵測打者是 everyday / 強側 platoon / 弱側 / bench，產出 payload tag。直接修補 Arraez→Pederson -28% 週 PA 盲區（回溯失誤型 3）。

機制：boxscore `battingOrder`（先發/替補）× 對方先發 `pitchHand` → 季 + 30d 各手性先發率 → 分類 + tag（如「⚠️ 強側平台 (vs RHP only)」）。fetcher 部分已存在（`mlb_query` 已 resolve pitchHand、`stream_sp_scan` 已 hydrate probables）；新增 boxscore battingOrder 抓取，按「球隊×日」cache。

詳見 PRD Implementation Decisions「platoon 拆兩片」P-a。

## Acceptance criteria

- [ ] classifier 純函式（battingOrder × pitchHand → 分類 + tag），注入式 fetcher
- [ ] 「球隊×日」cache，fetch 次數上限為機器可判驗收（assert cache-hit count，非散文）
- [ ] 回溯重放 Pederson 案：分類標籤 = 強側 platoon（驗證能標出該失誤）
- [ ] 單元測試：everyday / 強側 / 弱側 / bench 四分類邊界 + 同名球員邊界
- [ ] payload tag 注入，受 039 payload_budget 守門

## Blocked by

None - can start immediately

## User stories addressed

- User story 10
