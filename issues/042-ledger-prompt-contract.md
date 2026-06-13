## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

把兩條判斷規則加進 batter pass2 prompt，讓 LLM 利用注入的 ledger 紀錄：
- 翻供（改變 verdict）必須指認自上次理由以來「什麼變了」，否則維持。
- drop 建議必須面對「當初撿這個人的理由是否已失效」。

**HITL — lever 2 風險正主**（往 prompt 加判斷規則易誘發 billed thinking）。比照 037：配對 A/B（同 payload、同模型、neutral cwd）量 output_tokens + 人工審輸出品質，與其他 prompt 變更分批上線隔離歸因。規則文字務必精簡（避免「逐項比對才能決定」式誘發）。

詳見 PRD Implementation Decisions「ledger prompt 契約」。

## Acceptance criteria

- [ ] prompt 兩規則定稿（翻供指認變因 + drop 面對原 add 理由），措辭精簡
- [ ] 配對 A/B（複用 037 runner 模式，VPS）：output_tokens 無 lever 2 式暴增 + 核心決策不變 + 翻供/drop 行為符合規則
- [ ] 與 039（ledger 注入上線）+ 037 分批，A/B 歸因隔離
- [ ] 部署後一週 production spot-check：翻供確有指認變因、drop 確有面對原理由

## Blocked by

- Blocked by `issues/039-ledger-consumers.md`（注入行上線後規則才有資料可引用）

## User stories addressed

- User story 1
- User story 7
- User story 9
