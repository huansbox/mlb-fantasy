# 037 — 觸發條件 schema 約束 prompt 段（HITL）

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「判斷流程去偏」觸發條件 schema 約束）

## What to build

prompt 約束觀察觸發條件的書寫文法：只能引用 payload 既有欄位 + 明確比較運算 + 明確視窗（「14d OPS ≥.850 連 7 天」合格；「品質維持」「prior-adjusted xwOBA」不合格）— 讓隔天的 LLM 與未來的機械 counter 能無歧義判定觸發是否達成。為觸發條件 DSL 完全體（Out of Scope）鋪路。

HITL 點：屬「往 prompt 加判斷規則」類變更 — lever 2 backfire 的正主類型，配對 A/B 必做且人工審結果。**與 `issues/028` 分開上線**（兩者改同一份 prompt，分批才能讓 A/B 的 cost/thinking 歸因乾淨）。

## Acceptance criteria

- [x] prompt 觸發條件約束段定稿（合格/不合格範例各列）— 2026-06-13，「觸發條件書寫文法」三要素節（欄位/比較/視窗）+ 合格 4 例 + 不合格→改寫 4 例
- [x] 配對 A/B（同 payload、同模型、neutral cwd）：新輸出的觸發條件全部機械可判定 + output_tokens 無 lever 2 式暴增 — VPS A/B（#306 payload）：A out 10784 tok $0.524 / B out 9498 tok $0.495（**−12%**，反而更省）；B 觸發全為 field/comparison/window（`BBE 達 120 + xwOBA pctile ≥P70`）vs A 的 `品質維持`/`prior 確認` 模糊；核心決策不變
- [x] 與 028 不同批部署（A/B 歸因隔離）— 028 於 2026-06-10 部署，037 於 2026-06-13 獨立部署（merge `585a736`）
- [ ] 部署後一週 production 觸發條件 spot-check：無模糊措辭回流 — 被動觀察至 ~2026-06-20

## 狀態

✅ 已部署（merge `585a736`，2026-06-13）。A/B runner = `daily-advisor/_tools/_ab_037_runner.py`（throwaway，比照 028）。剩一週 spot-check 被動觀察。

## Blocked by

- Blocked by `issues/028-waiver-log-grammar-extension.md`（✅ 2026-06-10 已部署 — 技術上已解鎖，但「分批上線」軟約束仍在：與 028 的 prompt 變更隔開觀察窗，A/B 歸因才乾淨）

## User stories addressed

- User story 24
- User story 26（prompt 變更配對 A/B）
