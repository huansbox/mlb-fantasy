# 022 — SP B2 design docs (static)

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Documentation")

## What to build

Create `docs/sp-b2-cutover-design.md` as the new current design source of truth. Mark B1 design / observation / baseline docs superseded with pointer headers.

This is a static-doc slice — content describes the design, not the deployed state — so it can ship before VPS rollout without violating the PRD's "documentation never describes a non-deployed pipeline" rule. The CLAUDE.md update (which DOES describe deployed state) is in issue 023.

## Acceptance criteria

- [ ] `docs/sp-b2-cutover-design.md` created. Sections:
  - [ ] Problem statement (recap from PRD)
  - [ ] Solution overview (thin mechanical + 2-step single-LLM)
  - [ ] B1 reference hash placeholder (filled in by issue 025 pre-cutover)
  - [ ] Anchor model (cant_cut lifetime vs weekly_anchor_sp weekly-mutable; LLM invisibility)
  - [ ] Phase 6 multi-agent retirement rationale (P1 dissent observed 0% across 10 reports; pool-size saturation argument)
  - [ ] Step A → Step B contract (JSON schemas, validation/retry behavior)
  - [ ] Rollback procedure (`git revert <B2 merge>` only; B1 hash for verification)
  - [ ] Quality monitoring (backtest automation Use Case A + `/weekly-review` spot check)
- [ ] `docs/sp-b1-cutover-design.md`: header note added at top — `> **Superseded** by `docs/sp-b2-cutover-design.md` (B2 thin + multi-agent collapse, 2026-XX-XX). Kept for archival reference.`
- [ ] `docs/sp-b1-observation.md`: same header treatment
- [ ] `docs/sp-b1-baseline.md`: same header treatment
- [ ] No code changes — pure documentation slice

## Blocked by

None — can start immediately.

## User stories addressed

- User story 14
