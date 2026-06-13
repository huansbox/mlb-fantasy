## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

兩個近零成本打者欄位，各自一個小函式進現有計算層 + payload 行：

1. **chase / zone-contact delta**：追打壞球率 + 好球帶內接觸率的年度變化 — BB%（本格式雙重計算的最高槓桿類別）的上游先行指標，比 BB% 早幾週可見。加進既有 Savant leaderboard fetch 欄位。
2. **post-hype 新秀標記**：前百大新秀出身 + 年輕 + 過往成績差 → tag，給 LLM「折價爛 prior」授權（反 Walker 誤殺）。靜態年度 JSON（mlb_id → best_rank/year）+ dict join + 年齡（既有 /people 欄位）。

post-hype JSON 是本系統第一個需人工維護的資料資產：每年 3 月更新；若忘記更新自動標 stale 並在報告註明，不靜默用舊資料。

詳見 PRD Implementation Decisions「micro-fields」M-bat。

## Acceptance criteria

- [ ] chase/zone-contact delta 純函式 + percentile + YoY delta，加進既有 leaderboard fetch（不新增 fetch round）
- [ ] post-hype tag = JSON dict join + 年齡 + 生涯成績門檻；JSON stale 偵測 + 報告註明
- [ ] 兩 tag 注入 batter payload，受 039 payload_budget 守門
- [ ] 單元測試：delta 計算邊界 + pedigree join 命中/未命中 + stale 偵測

## Blocked by

None - can start immediately

## User stories addressed

- User story 14
- User story 15
