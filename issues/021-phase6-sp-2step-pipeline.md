# 021 — _phase6_sp.py 2-step pipeline + 2 new prompts (HITL)

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Major rewrite — `_phase6_sp.py`")

## What to build

Drop all multi-agent orchestration in `daily-advisor/_phase6_sp.py`. Implement single-LLM 2-step pipeline with strict Step A → Step B contract, JSON validation + retry + Telegram alert, anchor leak prevention. Create 2 new prompt templates. Delete 7 obsolete prompt files.

**HITL** because prompt content design and Step A JSON schema lock-in require human review for hallucination risk, reasoning structure, and contract correctness.

## Acceptance criteria

### Deletes

- [ ] Delete payload builders in `_phase6_sp.py`:
  - [ ] `_build_step1_payload` (line 139)
  - [ ] `_build_step2_payload` (line 153)
  - [ ] `_build_step3_review_payload` (line 173)
  - [ ] `_build_fa_classify_payload` (line 190)
  - [ ] `_build_fa_rank_payload` (line 198)
  - [ ] `_build_fa_review_payload` (line 212)
  - [ ] `_build_final_payload` (line 226)
  - [ ] `_run_personalized_reviewers` (line 537)
  - [ ] `_build_reeval_payload` (line 560)
- [ ] Delete dissent integration logic
- [ ] Delete 7 obsolete prompt files in `daily-advisor/`:
  - [ ] `prompt_phase6_sp_step1_rank.txt`
  - [ ] `prompt_phase6_sp_step2_master.txt`
  - [ ] `prompt_phase6_sp_step3_review.txt`
  - [ ] `prompt_phase6_fa_step1_classify.txt`
  - [ ] `prompt_phase6_fa_step2_rank.txt`
  - [ ] `prompt_phase6_fa_step3_review.txt`
  - [ ] `prompt_phase6_final_decision.txt`

### New 2-step orchestration

- [ ] `_build_step_a_payload(weakest, fa_pool)` — reads ONLY `weakest` (anchor-filtered output of `pick_weakest_v4_sp`), NEVER `my_roster` (which still contains anchor data after `_attach_v4_to_my_roster`)
- [ ] `_build_step_b_payload(step_a_result, weakest, fa_pool)` — payload contains Step A JSON output PLUS the full slimmed pools Step A saw (NOT just JSON summary — Step B needs original metrics to reason about)
- [ ] Step A output schema (locked in prompt design):
  - Top-level: `my_team_rank: list[{name, rank, rationale}]`, `fa_classify: list[{name, verdict ∈ {worth, borderline, not_worth}, rationale}]`
- [ ] Step B output schema:
  - Top-level: `action ∈ {drop_X_add_Y, watch, pass}`, `drop`, `add`, `reason`, `watch_target`
- [ ] `json.loads()` Step A output inside try/except
- [ ] Parse failure handling: log error + Telegram alert "Step A JSON parse failed" + 1 retry (re-call Step A with same payload); if retry also fails → final verdict = `pass` + alert (do NOT crash cron)
- [ ] Schema validation: required top-level keys present, types correct; failure → same treatment as parse failure
- [ ] M1/M4' metric emit removed — `phase6_metrics` block no longer in final payload

### New prompt files

- [ ] `daily-advisor/prompt_sp_b2_step_a.txt` — instructs LLM to rank P1-P3 in my-team + classify each FA, returning structured JSON per Step A schema
- [ ] `daily-advisor/prompt_sp_b2_step_b.txt` — instructs LLM to read Step A JSON + full pool data and produce final verdict per Step B schema

### Other updates

- [ ] `_emit_final` (line 591-657): update hardcoded `"Phase 6 multi-agent watch"` trigger string (line 627) to `"B2 2-step watch"` so waiver-log entries carry accurate pipeline-version context
- [ ] `process_sp_v4` simplified — anchor_filter applied inside `pick_weakest_v4_sp`, so this function receives `weakest` ready for Step A
- [ ] `_slim_my_team_entry` / `_slim_fa_entry` — keep as thin wrappers over `payload_slimmer.slim_entry` (no change beyond what payload_slimmer outputs)
- [ ] `_attach_v4_to_my_roster` (line 86) — no change; still fetches v4 data for all my_roster including anchors; anchor exclusion happens via `pick_weakest_v4_sp` output

### Verification (no unit tests for orchestrator per codebase convention)

- [ ] Human review of `prompt_sp_b2_step_a.txt` + `prompt_sp_b2_step_b.txt` content for: hallucination risk, anchor leak risk in prompt language, reasoning structure clarity
- [ ] Local smoke test via `bash bin/vps-run.sh` (or equivalent) — verify script runs without exception, posts valid GitHub Issue, posts Telegram summary
- [ ] Full unit-test coverage validation deferred to gray rollout in issue 025

## Blocked by

- `issues/017-anchor-filter-deep-module.md`
- `issues/018-payload-slimmer-thin-b2.md`
- `issues/020-fa-compute-thin-refactor.md`

## User stories addressed

- User story 2
- User story 5
- User story 10
- User story 12
- User story 21
