# 023 — CLAUDE.md SP section rewrite (deploy-locked)

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Documentation — CLAUDE.md")

## What to build

Rewrite CLAUDE.md SP evaluation section to reflect B2 thin design + 2-step single-LLM pipeline. Update 「檔案索引」and 「待辦」 sections accordingly.

**Deploy-locked**: content prepared in this issue but commit NOT pushed until issue 025 cutover commit (or amended into that commit). Honors PRD's "documentation never describes a non-deployed pipeline state" rule.

## Acceptance criteria

- [ ] CLAUDE.md SP framework section (currently titled "SP 評估 (v4 — 5-slot Sum + Phase 6 multi-agent)") rewritten:
  - [ ] Title changed to reflect B2 (e.g., "SP 評估 (B2 — 5-slot thin mechanical + 2-step single-LLM)")
  - [ ] Remove all urgency / slump hold / 2025 prior references
  - [ ] Remove Phase 6 multi-agent references
  - [ ] Remove M1/M4' metric references
  - [ ] Add thin mechanical layer description: anchor_filter → BBE<30 filter → Rotation Gate → Sum ascending → top-3
  - [ ] Add 2-step single-LLM pipeline description: Step A (rank P1-P3 + FA classify) → Step B (final verdict)
  - [ ] Add anchor mechanism: cant_cut (lifetime hard) vs weekly_anchor_sp (weekly-mutable, user-managed); LLM invisibility of both
  - [ ] Add Step A JSON validation + retry + Telegram alert + fall-through to pass
- [ ] CLAUDE.md 「檔案索引」 section updated:
  - [ ] Add entry: `daily-advisor/anchor_filter.py` — anchor filtering pure function (cant_cut + weekly_anchor_sp)
  - [ ] Add entry: `docs/sp-b2-cutover-design.md` — current SP design source of truth
  - [ ] Update or remove: `daily-advisor/_phase6_sp.py` — describe as B2 2-step orchestrator (or rename if file renamed)
  - [ ] Update or remove: `daily-advisor/metrics_reader.py` — based on issue 019 disposition (deleted or pruned)
  - [ ] Remove obsolete 7 prompt file references; add 2 new prompt file references
- [ ] CLAUDE.md 「待辦」 section updated:
  - [ ] Close B1 cutover observation item (issue 009 era)
  - [ ] Add backlog item: "**Backtest Use Case B (xwOBACON 校準)** — 4-6 週數據累積後觸發實作。設計參考 `docs/sp-decisions-backtest-automation.md` Use Case B。"
- [ ] Content prepared on `feat/sp-b2-collapse` branch; commit NOT pushed to master until issue 025 cutover commit

## Blocked by

- `issues/021-phase6-sp-2step-pipeline.md` — needs final design + prompt schemas locked in to describe accurately

## User stories addressed

- User story 14
- User story 20
