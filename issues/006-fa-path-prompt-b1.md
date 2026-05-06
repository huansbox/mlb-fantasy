## Parent PRD

`issues/prd.md`

## What to build

改寫 FA path 三個 prompt 對齊 B1 schema，並清理 final decision prompt 中 sum 引用。

**改動範圍**：
- `prompt_phase6_fa_step1_classify.txt`：拿掉 sum_diff / breakdown_diff / win_gate_passed 引用；保留 add_tags / warn_tags（前提是 evaluation tags 已從 fa_compute 拿掉）
- `prompt_phase6_fa_step2_rank.txt`：同上邏輯，rank 改交 LLM 從 raw 排
- `prompt_phase6_fa_step3_review.txt`：清掉 sum 引用文字
- `prompt_phase6_final_decision.txt`：清掉 sum 引用文字（input 已從 `_build_final_payload` 拿掉 sum_diff）

**驗證方式**：spike fixture 跑同 005 的 case，看 FA classify / rank 是否 LLM 從 raw 自由判斷而非引用 sum_diff。

詳見 PRD `Implementation Decisions` 段「Prompt Layer」+ `docs/sp-b1-cutover-design.md` §LLM 層 §2.4-2.5。

## Acceptance criteria

- [ ] fa_step1_classify.txt 不再引用 sum_diff / breakdown_diff / win_gate_passed
- [ ] fa_step1_classify.txt 指引 LLM 從 raw + 5-slot percentile + tags 自判 replace / watch / pass
- [ ] fa_step2_rank.txt 移除 sum 引用，改 LLM 從 raw 排
- [ ] fa_step3_review.txt 清掉 sum 引用文字
- [ ] final_decision.txt 清掉 sum 引用文字
- [ ] Spike fixture：FA classify 三 agent reasoning 引用 raw stat / percentile，**不**出現 `sum_diff: N` 字樣
- [ ] Spike fixture：FA master rank 排序依據 raw 訊號（非 sum diff）
- [ ] HITL：用戶手動 review spike output 確認 FA 路徑 LLM reasoning 品質

## Blocked by

- Blocked by `issues/002-payload-slimmer-deep-module.md`

## User stories addressed

- User story 1
- User story 4
- User story 5
