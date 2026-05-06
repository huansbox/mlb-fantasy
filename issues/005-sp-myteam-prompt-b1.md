## Parent PRD

`issues/prd.md`

## What to build

改寫 SP my-team path 三個 prompt 對齊 B1 schema，並把 master step2 borderline 判定從 mechanical rule 改為 LLM 自判（H3）。

**改動範圍**：
- `prompt_phase6_sp_step1_rank.txt`：拿掉 sum / urgency / evaluation tags 引用；強調從 raw + 5-slot percentile + 雙年 prior + 21d 趨勢自由 reasoning
- `prompt_phase6_sp_step2_master.txt`：移除「sum diff <5 → borderline」rule；新增 LLM 自判 borderline 指引（raw 訊號矛盾 / 候選間實質差距小，例「P1 候選 xwOBACON P30 但 IP/GS P85 = 內部矛盾 → borderline」）
- `prompt_phase6_sp_step3_review.txt`：清掉 sum 引用文字；review 仍是 sanity check master

**驗證方式**：spike fixture 跑 fa-scan #149 + 1-2 個近期 case，看三 agent 是否從 raw reasoning 不再 lazy 引用 sum 數字；master 是否 surface 真實 raw 矛盾作 borderline。

詳見 PRD `Implementation Decisions` 段「Prompt Layer」+ `docs/sp-b1-cutover-design.md` §LLM 層 §2.1-2.3。

## Acceptance criteria

- [ ] step1_rank.txt 完成改寫，不再出現 sum / urgency / evaluation tags 引用
- [ ] step1_rank.txt 明確指引 LLM 從 raw + 5-slot percentile + 雙年 prior 自由 reasoning
- [ ] step2_master.txt 移除 sum diff rule
- [ ] step2_master.txt 加 H3 borderline 自判指引 + 至少 2 個範例（raw 訊號矛盾 / 實質差距小）
- [ ] step3_review.txt 清掉 sum 引用文字
- [ ] Spike fixture 跑 fa-scan #149 + ≥1 個近期 case：三 agent step1 reasoning 引用 raw stat / percentile，**不**出現 `sum: N` 字樣
- [ ] Spike fixture：master 標 borderline 時引用 raw 訊號（非 sum diff）
- [ ] HITL：用戶手動 review spike output 確認 LLM reasoning 品質（非 lazy / 非 hallucinate）

## Blocked by

- Blocked by `issues/002-payload-slimmer-deep-module.md`

## User stories addressed

- User story 1
- User story 7
- User story 19
- User story 20
- User story 21
- User story 22
