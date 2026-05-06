## Parent PRD

`issues/prd.md`

## What to build

用 `tests/multi_agent_spike.py`（或現有 spike infra）對 B1 改寫後的 5 個 prompt 跑 baseline 共識率測試，產出 baseline 數字並文件化撤退門檻。

**樣本選擇**：
- fa-scan #149（已知 anchor 失效案例）
- 過去 1-2 週 5-7 個 daily fa-scan issue
- 共 5-10 case

**baseline 指標**：
- M1：spike sample 中 SP step1 三 agent P1 match rate（百分比 + 標準差）
- M4：spike sample 中 SP master borderline trigger rate
- 同步算 FA 路徑兩個 rate

**撤退門檻設定**：
- M1 條件：上線後連 2 週 P1 match rate < (baseline -1σ) → 觸發 G1 fallback
- M4 條件：上線後連 2 週 review trigger rate > 75%（master 自判 borderline 過頻繁）→ 觸發

**文件化**：產出 `docs/sp-b1-baseline.md`，含 spike 結果分布、選用門檻數字、觸發後 G-pre2 fallback 啟動 SOP。

詳見 PRD `Further Notes` + `docs/sp-b1-cutover-design.md` §4 撤退門檻。

## Acceptance criteria

- [ ] 用 multi_agent_spike infra 跑 5-10 case（含 fa-scan #149）
- [ ] 每 case 記錄 SP P1 match / SP review triggered / FA P1 match / FA review triggered
- [ ] 算 baseline 數字：M1 SP / M1 FA / M4 SP / M4 FA 各自 mean + std
- [ ] 設定撤退門檻：(baseline -1σ) 數字明確化，例「M1 SP <55% 連 2 週 → 撤退」
- [ ] 產出 `docs/sp-b1-baseline.md` 含：spike 結果分布表 / baseline 數字 / 撤退門檻 / G-pre2 fallback 啟動 SOP
- [ ] HITL：用戶 review baseline 數字是否 reasonable（極端情境：若 P1 match rate <30% 平均 → 暫緩 cutover，疑似 raw 訊號本身 ambiguous）

## Blocked by

- Blocked by `issues/005-sp-myteam-prompt-b1.md`
- Blocked by `issues/006-fa-path-prompt-b1.md`

## User stories addressed

- User story 11
- User story 12
- User story 13
