# 037 — 觸發條件 schema 約束 prompt 段（HITL）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「判斷流程去偏」觸發條件 schema 約束）

## What to build

prompt 約束觀察觸發條件的書寫文法：只能引用 payload 既有欄位 + 明確比較運算 + 明確視窗（「14d OPS ≥.850 連 7 天」合格；「品質維持」「prior-adjusted xwOBA」不合格）— 讓隔天的 LLM 與未來的機械 counter 能無歧義判定觸發是否達成。為觸發條件 DSL 完全體（Out of Scope）鋪路。

HITL 點：屬「往 prompt 加判斷規則」類變更 — lever 2 backfire 的正主類型，配對 A/B 必做且人工審結果。**與 `issues/028` 分開上線**（兩者改同一份 prompt，分批才能讓 A/B 的 cost/thinking 歸因乾淨）。

## Acceptance criteria

- [ ] prompt 觸發條件約束段定稿（合格/不合格範例各列）
- [ ] 配對 A/B（同 payload、同模型、neutral cwd）：新輸出的觸發條件全部機械可判定 + output_tokens 無 lever 2 式暴增
- [ ] 與 028 不同批部署（A/B 歸因隔離）
- [ ] 部署後一週 production 觸發條件 spot-check：無模糊措辭回流

## Blocked by

- Blocked by `issues/028-waiver-log-grammar-extension.md`（✅ 2026-06-10 已部署 — 技術上已解鎖，但「分批上線」軟約束仍在：與 028 的 prompt 變更隔開觀察窗，A/B 歸因才乾淨）

## User stories addressed

- User story 24
- User story 26（prompt 變更配對 A/B）
