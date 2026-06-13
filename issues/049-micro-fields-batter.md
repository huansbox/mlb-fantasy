## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

兩個近零成本打者欄位，各自一個小函式進現有計算層 + payload 行：

1. **chase / zone-contact delta**：追打壞球率 + 好球帶內接觸率的年度變化 — BB%（本格式雙重計算的最高槓桿類別）的上游先行指標，比 BB% 早幾週可見。加進既有 Savant leaderboard fetch 欄位。
2. **post-hype 新秀標記**：前百大新秀出身 + 年輕 + 過往成績差 → tag，給 LLM「折價爛 prior」授權（反 Walker 誤殺）。靜態年度 JSON（mlb_id → best_rank/year）+ dict join + 年齡（既有 /people 欄位）。

post-hype JSON 是本系統第一個需人工維護的資料資產：每年 3 月更新；若忘記更新自動標 stale 並在報告註明，不靜默用舊資料。

詳見 PRD Implementation Decisions「micro-fields」M-bat。

## Acceptance criteria

- [x] chase/zone-contact delta 純函式 + percentile + YoY delta（`batter_discipline.py` + `calc_discipline_pctiles.py`，PR #334）— 前提修正：兩欄不在現有 statcast/expected batter CSV，加 1 bulk custom CSV/年（非 per-player round；同 M-sp savant_rolling）
- [x] post-hype tag = JSON dict join + 年齡 + 生涯成績門檻（weak_signal proxy）；JSON stale 偵測 + 報告註明（`prospect_pedigree.py` + `build_prospect_json.py` + `prospect_pedigree.json`，PR #333）
- [ ] 兩 tag 注入 batter payload，受 039 payload_budget 守門 → **移交 318b 全注入批**（見 issue 039；與 #322-#327 同批上 VPS A/B，需 payload_budget gate + 行格式 + 配對 A/B）
- [x] 單元測試：delta 計算邊界 + pedigree join 命中/未命中 + stale 偵測（discipline 20 + post-hype 32 + builder 17 = 69 tests）

## Progress（2026-06-13）

兩半引擎全部完成、測過、merge 進 master（PR #333 post-hype / PR #334 chase-discipline）。
**唯一剩項 = payload 注入**，依 issue 039 架構不獨立做，已歸入 318b 全注入批（line-format
+ payload_budget gate + VPS 配對 A/B 都在那批）。pattern 同 #322-#327（引擎進 master、注入留
318b）。設計/維護文件：post-hype 見 `docs/prospect-pedigree.md`；discipline baseline 見 CLAUDE.md
百分位段 + `calc_discipline_pctiles.py`。

## Blocked by

None - can start immediately

## User stories addressed

- User story 14
- User story 15
