# SP B2 Thin Collapse PRD

> Supersedes B1 cutover design (`docs/sp-b1-cutover-design.md`) as the active SP framework target. Aborts B1 observation period (live 2026-05-26 through planned 2026-06-22) by replacing the pipeline being observed.

## Problem Statement

The in-season manager runs a 12-team H2H 7×7 Yahoo league. The SP evaluation pipeline (v4 5-slot + Phase 6 multi-agent, B1 cutover live since 2026-05-26) carries complexity that no longer serves decision quality. Three layers identified:

**Layer 1 — Mechanical layer carries dead weight**:
- Slump hold mechanism (gates SPs with 2025 v4 Sum ≥40 + IP ≥50 out of urgency ranking) auto-protects "menls in slump" the user prefers to manage manually via a weekly list.
- Urgency 4-factor (2026 Sum / 2025 Sum / 21d Δ / IP/Team_G) is computed but never reaches LLM context — LLM ranks from raw + percentile directly. Urgency output is consumed only by mechanical pre-sort, which Sum alone could drive.
- FA tags ✅ 雙年菁英 / ⚠️ Breakout 待驗 depend on 2025 prior; as 2026 BBE accumulates (~150 typical by late May), 2025 dilutes more than informs.
- Sum exposed to LLM compresses 5 orthogonal slots into one number, creating anchoring bias on the conflated score and hiding slot-level signal.
- Sum ≥40 hard floor exclude is redundant — Sum-ascending sort already pushes elite SPs to the bottom of the candidate pool.
- P1-P4 candidate pool is oversized — after user's anchor filtering reduces eligible pool to 3-5 SPs, P4 forces ranking of a non-realistic drop target.

**Layer 2 — Multi-agent layer is over-engineered for current pool size**:
- Across 10 recent reports (2026-05-17 to 2026-05-26), step1 P1 dissent rate is 0% — all 3 agents always converge on the same P1.
- B2 anchor filtering further reduces eligible pool to 3-5 SPs. With pool that small, 3-agent consensus is statistically near-guaranteed regardless of pipeline health.
- Multi-agent step1 + master integration consumes ~60% of Phase 6 token budget with zero measurable benefit at current pool sizes.
- Phase 6 design always anticipated this: `docs/sp-b1-observation.md` "After observation period" section explicitly states "if dissent surface is rare → consider permanent collapse to single-call".

**Layer 3 — Observation infrastructure built for B1 cannot validate B2**:
- M1 metric = agent step1 consensus rate. Calibrated against B1 pool size; saturates near 100% at B2 pool size regardless of pipeline health.
- M4' metric = top-pair borderline rate. Same saturation issue.
- Rollback thresholds (M1 < 0.036 / M4' > 75% for 2 consecutive weeks) would never trigger at B2 pool sizes for the right reason — observation period would have no functioning safety net.

## Solution

Two simultaneous refactors deployed atomically:

**Refactor 1 — Thin mechanical layer** (mirrors Batter v4 thin design, production since 2026-04-28):
- Mechanical pipeline: anchor_filter → BBE<30 filter → Rotation Gate (GS=0 or IP/GS<3 excluded) → Sum ascending sort → return top-3.
- Anchors (cant_cut lifetime + weekly_anchor_sp weekly-mutable) entirely invisible to LLM — not in roster snapshot, not in candidate pool.
- 2026-only data; remove 2025 prior reading from SP evaluation path entirely.
- Delete urgency mechanism (compute_urgency_v4_sp + all _factor_* helpers).
- Sum kept internal-only — used for candidate pool sort. Not exposed to LLM. Not used for any borderline trigger (no multi-agent to need it).
- Sum ≥40 hard floor exclude removed (redundant + conflicts with user's "fair game" philosophy).
- 2025-based FA tags removed (✅ 雙年菁英, ⚠️ Breakout 待驗). 2026-based tags preserved (✅ 撿便宜運氣 / ⚠️ 賣高運氣 use 2026 xERA-ERA, kept; ✅ 深投型 / ✅ GB 重型 / ✅ K 壓制 / ⚠️ 短局 / ⚠️ Swingman 角色 / ⚠️ xwOBACON 極端 / ⚠️ K 壓制不足 / ⚠️ Command 警示 / ⚠️ 樣本小 / ⚠️ IL 短期 / ⚠️ 近況下滑 / ✅ 近況確認 all kept).

**Refactor 2 — Collapse Phase 6 multi-agent → single-LLM 2-step pipeline**:
- Replace 6-step multi-agent flow (3 step1 agents → master integrate → borderline review → fa_classify → fa_rank → final master) with 2-step single-LLM flow.
- Step A: Single LLM call — rank P1-P3 in my-team eligible pool + classify each FA (worth / borderline / not_worth) → structured JSON output.
- Step B: Single LLM call — read Step A output + full data → final verdict (drop_X_add_Y / watch / pass) + rationale.
- 7 prompt templates → 2 prompt templates.
- `_phase6_sp.py` largely rewritten (drops 3-agent orchestration, dissent integration, borderline review trigger).
- M1/M4' metric emit infrastructure retired (no multi-agent → no consensus signal). `metrics_reader.py` becomes obsolete for SP path.
- Quality monitoring replaced by retrospective backtest automation (builds on existing `docs/sp-decisions-backtest.md` + `docs/sp-decisions-backtest-automation.md` design) plus `/weekly-review` human spot check.

**User layer responsibilities** (unchanged from PRD v1):
- Maintain `league.weekly_anchor_sp` (name list) in `roster_config.json`.
- Review list weekly during `/weekly-review`.
- Accept fair-game default: not on the list = drop-eligible.
- `league.cant_cut` semantics formally narrow to "lifetime hard no-touch" only.

## User Stories

1. As an in-season manager, I want a weekly-mutable "do not drop" SP list separate from the lifetime cant_cut list, so that I can flag SPs I've committed to protecting this week (menls in slump, recent trade-ins, breakout candidates I'm riding out) without conflating them with my lifetime untouchables.

2. As an in-season manager, I want anchor SPs (cant_cut + weekly_anchor_sp) entirely hidden from the LLM's view of the team, so that the single-LLM reasoning focuses only on drop-eligible SPs and never wastes context window on protected players.

3. As an in-season manager, I want the LLM to compare FA candidates against my non-anchor eligible SPs only, so that the "FA worth picking up" threshold is calibrated against my weakest realistic drop target — not against my elite anchors which I won't drop regardless.

4. As an in-season manager, I want SP evaluation to use 2026 data exclusively, so that the system reflects current form without 2025 noise diluting judgment now that 2026 BBE samples are mature.

5. As an in-season manager, I want the LLM prompt to contain only raw stats + 5-slot percentile + 21d Δ + 14d traditional (no Sum, no urgency, no machine-computed tags from 2025), so that LLM reasoning is grounded in observable data rather than anchored on compressed machine scores.

6. As an in-season manager, I want the SP candidate pool sized to P1-P3 instead of P1-P4, so that pool size matches realistic eligible SP count after anchor filtering and removes the synthetic P4 noise slot.

7. As an in-season manager, I want the Sum metric retained as an internal signal solely for candidate pool ranking (not for any LLM-facing or borderline-trigger purpose), so that the mechanical sort produces deterministic ordering without leaking machine bias into LLM context.

8. As an in-season manager, I want 2025-based FA tags removed (✅ 雙年菁英, ⚠️ Breakout 待驗) while 2026-based tags are preserved (full list in Implementation Decisions), so that tag surface reflects only currently meaningful signal.

9. As an in-season manager, I want the urgency mechanism (compute_urgency_v4_sp + all _factor_* helpers) entirely removed from the codebase, so that no dead 4-factor logic accumulates after pipeline collapse.

10. As an in-season manager, I want the Phase 6 multi-agent pipeline collapsed to a single-LLM 2-step flow (Step A: rank+classify, Step B: final verdict), so that the pipeline matches the actual decision complexity and stops paying multi-agent overhead for zero measurable benefit.

11. As an in-season manager, I want anchor filtering implemented as a separate, pure-function module (`anchor_filter.py`) with a simple signature, so that filtering logic is isolated, testable in isolation, and called from exactly one site (`fa_compute.pick_weakest_v4_sp`) to avoid double-application.

12. As an in-season manager, I want all changes developed on a dedicated branch (`feat/sp-b2-collapse`) and deployed atomically to VPS, so that the daily fa-scan report pipeline never enters a half-old half-new state.

13. As an in-season manager, I want the existing B1 observation period explicitly aborted and replaced by retrospective backtest automation + `/weekly-review` human spot check, so that pipeline quality monitoring continues with mechanisms that actually work for the new pool size.

14. As an in-season manager, I want a `sp-b2-cutover-design.md` created, B1 design / observation / baseline docs marked superseded, and CLAUDE.md SP section rewritten, so that future-me reads a single current source of truth on SP framework.

15. As an in-season manager, I want the existing tests across both `test_fa_compute.py` (32 cases, batter-heavy) and `test_fa_compute_v4.py` (47 cases, SP v4) audited and updated to match the new mechanical layer, so that test coverage stays meaningful after deletion of urgency/slump_hold/hard_floor logic.

16. As a developer (future-me), I want `anchor_filter.py` shipped with 8-12 unit test cases covering empty / single / multi / overlap / case-insensitive / accent-normalization / order-preservation / idempotence, so that the filtering primitive is robust before downstream consumers depend on it.

17. As an in-season manager, I want the fa-scan SP report output shape backwards-compatible for downstream consumers (waiver-log auto-close for roster reconciliation), so that the refactor doesn't cascade into unrelated systems. The `metrics_reader.py` reader is explicitly out of scope for compatibility since M1/M4' metrics are retired.

18. As an in-season manager, I want VPS deploy executed as a gray rollout (push to VPS → stop cron → manual trigger 1-2 fa-scan runs → verify output structure + verdict quality → enable cron), so that the first cron run after deploy doesn't risk a silent breakage day.

19. As an in-season manager, I want the B1 commit hash captured in writing before development begins, so that `git revert` rollback has an unambiguous target if a post-deploy issue emerges.

20. As an in-season manager, I want CLAUDE.md updated in lockstep with the code deploy (single commit pushes both), so that documentation never describes a non-deployed pipeline state.

21. As an in-season manager, I want `payload_slimmer.py` updated (drop `prior_v4` field from slimmed payload, refresh `_ALLOWED_TAGS` whitelist to match the kept 2026-based tag set), so that the actual LLM-facing payload schema reflects the thin design intent.

22. As an in-season manager, I want retrospective backtest automation implemented as part of Phase 3 deploy (builds on existing `docs/sp-decisions-backtest-automation.md` design), so that quality monitoring has a mechanism running by the time the cutover is live — not deferred indefinitely.

## Implementation Decisions

**New deep module — `anchor_filter`**:
- Interface: `filter_anchors(roster: list[dict], cant_cut_names: list[str] | None, weekly_anchor_names: list[str] | None) -> list[dict]`.
- Pure function. Returns roster minus anchored players, preserving original order. Idempotent. Treats `None` and `[]` identically (empty anchor list → roster unchanged).
- Name matching: case-insensitive with accent/apostrophe normalization (alignment with existing `_normalize` pattern in `daily-advisor/rp_svh_scan.py`).
- `player_type` parameter explicitly NOT included (YAGNI — no current code path needs it; add only when batter anchor mechanism is built).
- Single call site: invoked from `fa_compute.pick_weakest_v4_sp` only. `_phase6_sp.py` does NOT call directly — receives already-filtered candidate pool.

**Modified module — `fa_compute.py`**:
- Delete `compute_urgency_v4_sp` (current line 986) entirely. With it: `_factor_2026_sum_v4` (852), `_factor_2025_sum_v4` (871), `_factor_luck_regression_v4` (893), and the entire slump_hold list construction + gate (currently inside `compute_urgency_v4_sp` lines ~1050-1061, NOT in `pick_weakest_v4_sp`).
- Delete module-level constant `_PRIOR_IP_SLUMP_HOLD_MIN` (current line 239) — only consumed by the deleted slump_hold gate.
- Delete module-level constant `_SP_SUM_HARD_FLOOR` (current ~line 840 area) — only consumed by the deleted hard floor check in `pick_weakest_v4_sp`.
- Simplify `pick_weakest_v4_sp` (current line 919, signature `(players, n=4, cant_cut=None)`): actual delta is (a) `n` default changes 4 → 3, (b) delete lines 970-972 (`if score >= _SP_SUM_HARD_FLOOR: continue`), (c) replace inline `cant_cut` filtering with `anchor_filter.filter_anchors(roster, cant_cut, weekly_anchor)` call. Flow becomes anchor_filter → BBE<30 filter → Rotation Gate → Sum ascending → top-N.
- Remove `compute_fa_tags_v4_sp` win_gate short-circuit (current lines 823-831) — `add_tags` / `warn_tags` should be computed for all FAs regardless of win_gate; filtering responsibility moves entirely to `payload_slimmer._ALLOWED_TAGS`. Boundary: `fa_compute` computes everything, slimmer filters what reaches LLM.
- In `v4_add_tags_sp` (current line 627): remove `✅ 雙年菁英` (prior-based). Keep `✅ 深投型`, `✅ GB 重型`, `✅ K 壓制`, `✅ 撿便宜運氣` (2026 xERA-ERA based), `✅ 近況確認` (21d-based).
- In `v4_warn_tags_sp` (current line 681): remove `⚠️ Breakout 待驗` (prior-based). Keep `⚠️ 樣本小`, `⚠️ 短局`, `⚠️ Swingman 角色`, `⚠️ xwOBACON 極端`, `⚠️ K 壓制不足`, `⚠️ Command 警示`, `⚠️ 賣高運氣` (2026-based), `⚠️ 近況下滑` (21d-based), `⚠️ IL 短期`.
- `compute_2025_sum` (line 432): no change. Function is already batter-only (hardcoded `key_map = _PRIOR_KEY_MAP["batter"]`). The PRD v1 worry about an "SP path" was based on misread; no action needed.
- `compute_sum_score_v4_sp`: keep — still computes Sum for internal use in `pick_weakest_v4_sp`.

**Modified module — `payload_slimmer.py`**:
- `slim_entry` (current line ~101-144): remove `prior_v4` field entirely from output payload (currently emits `"prior_v4": {"ip": ..., "slots": _slot_metrics(prior)}` at ~line 120-123).
- `_ALLOWED_TAGS` whitelist (current line 26-28): expand to include 2026-based tags that should reach LLM. Current whitelist `{"✅ 球隊主力", "⚠️ 上場有限", "⚠️ 樣本小", "⚠️ 短局", "⚠️ IL 短期", "⚠️ Swingman 角色"}` extends to add `✅ 深投型`, `✅ GB 重型`, `✅ K 壓制`, `✅ 撿便宜運氣`, `✅ 近況確認`, `⚠️ xwOBACON 極端`, `⚠️ K 壓制不足`, `⚠️ Command 警示`, `⚠️ 賣高運氣`, `⚠️ 近況下滑`.

**Major rewrite — `_phase6_sp.py`**:
- Delete multi-agent orchestration: `_build_step1_payload`, `_build_step2_payload`, `_build_step3_review_payload`, `_build_fa_classify_payload`, `_build_fa_rank_payload`, `_build_fa_review_payload`, `_build_final_payload`, `_run_personalized_reviewers`, `_build_reeval_payload`, dissent integration logic.
- New 2-step flow:
  - `_build_step_a_payload(weakest, fa_pool)` → single LLM call → **structured JSON output** with fixed schema (top-level keys: `my_team_rank` array of {`name`, `rank`, `rationale`}; `fa_classify` array of {`name`, `verdict` ∈ {`worth`, `borderline`, `not_worth`}, `rationale`}).
  - `_build_step_b_payload(step_a_result, weakest, fa_pool)` → reads Step A JSON **plus the same full slimmed pools that Step A saw** (NOT just the JSON summary — Step B needs original metrics to reason about). Returns final verdict {`action` ∈ {`drop_X_add_Y`, `watch`, `pass`}, `drop`, `add`, `reason`, `watch_target`}.
- `_build_step_a_payload` MUST read only the `weakest` list (anchor-filtered output of `pick_weakest_v4_sp`), never the raw `my_roster` variable in `process_sp_v4`. The `_attach_v4_to_my_roster` (line 86) fetches v4 data for all SPs including anchors; anchors remain in `my_roster` scope after `pick_weakest_v4_sp` returns the filtered `weakest`. Failure mode: payload builder accidentally references `my_roster` → anchors leak into LLM context.
- **Step A JSON validation + retry**: After Step A returns, call `json.loads()` inside try/except. On parse failure: log error + Telegram alert "Step A JSON parse failed" + final verdict = `pass` (do not crash cron). On schema validation failure (missing top-level keys / wrong types): same handling. One retry on first parse failure (re-call Step A with same payload); if retry also fails, pass + alert. Rationale: B1 multi-agent had graceful degrade via `_multi_agent.py` `all_parsed` / `consensus_check_key`; B2 collapse must preserve equivalent resilience.
- `process_sp_v4`: drastically simplified; anchor_filter already applied inside `pick_weakest_v4_sp`, so `process_sp_v4` receives candidate pool ready for Step A.
- `_slim_my_team_entry` / `_slim_fa_entry`: keep as thin wrappers over `payload_slimmer.slim_entry` (no change needed beyond what `payload_slimmer` itself outputs).
- M1/M4' metric emit: remove. Final payload no longer carries `phase6_metrics` block.
- `_emit_final` (current line 591-657): update hardcoded "Phase 6 multi-agent watch" trigger string (current line 627) to "B2 2-step watch" so waiver-log entries carry accurate pipeline-version context.

**New prompt templates** (replace 7 existing files):
- Delete: `prompt_phase6_sp_step1_rank.txt`, `prompt_phase6_sp_step2_master.txt`, `prompt_phase6_sp_step3_review.txt`, `prompt_phase6_fa_step1_classify.txt`, `prompt_phase6_fa_step2_rank.txt`, `prompt_phase6_fa_step3_review.txt`, `prompt_phase6_final_decision.txt`.
- Create: `prompt_sp_b2_step_a.txt` (rank P1-P3 in my-team + classify FAs into worth/borderline/not_worth → structured JSON).
- Create: `prompt_sp_b2_step_b.txt` (read Step A JSON output + full payload context → drop_X_add_Y / watch / pass verdict + rationale).

**Configuration schema — `roster_config.json`**:
- Add `league.weekly_anchor_sp: ["Cole Ragans", "Chris Sale", "Parker Messick"]` (initial seed).
- `league.cant_cut`: no schema change. Current Skubal / Jazz / Manny entries remain. Semantics documented as "lifetime hard no-touch" in CLAUDE.md.
- Code reading `weekly_anchor_sp`: must use `.get("weekly_anchor_sp", [])` with empty-list default to handle partial deploy race.

**New module — backtest automation**:
- Implement `docs/sp-decisions-backtest-automation.md` design as part of Phase 3.
- Reads GitHub Issues with `fa-scan` label, extracts verdict + reasoning, joins with subsequent SP performance data (Statcast / Yahoo).
- Outputs weekly: hit rate, average marginal benefit, surfaced systematic biases.
- Specific schema + cron details: defined in the implementation issue (deferred from this PRD).

**Test files**:
- `test_fa_compute.py` (32 batter-heavy tests): minor edits — only if shared helpers are affected. Most cases unchanged.
- `test_fa_compute_v4.py` (47 SP v4 tests): major audit — delete tests for `compute_urgency_v4_sp`, `_factor_*_v4`, slump_hold gate paths, Sum ≥40 hard floor, ✅ 雙年菁英, ⚠️ Breakout 待驗. Update tests for `pick_weakest_v4_sp` new simplified signature. Add regression tests for new candidate pool behavior.
- `test_anchor_filter.py` (new): 8-12 cases per Testing Decisions section.
- `_phase6_sp.py`: no unit test (existing convention; multi-LLM orchestrator validated via gray rollout instead).
- `test_metrics_reader.py`: if `metrics_reader.py` is fully deleted (decided in Phase 1 per `metrics_reader.py` disposition check), delete this file too. If `metrics_reader.py` is kept for batter path, prune SP-related tests only.

**Documentation**:
- New: `docs/sp-b2-cutover-design.md` — current design source of truth. Documents thin mechanical + 2-step single-LLM + user-managed anchor + backtest monitoring.
- New: `docs/sp-b2-baseline.md` — populated post-deploy Week 4 with initial backtest hit-rate baseline.
- Superseded: `docs/sp-b1-cutover-design.md`, `docs/sp-b1-observation.md`, `docs/sp-b1-baseline.md` — add header pointing to B2.
- Updated: `CLAUDE.md` — SP evaluation section rewritten (remove urgency / slump hold / 2025 prior / multi-agent references; add thin mechanical + 2-step single-LLM + anchor mechanism; clarify cant_cut vs weekly_anchor_sp semantics; remove M1/M4' metric references).

**Architectural decisions**:
- Anchor SPs entirely invisible to LLM (not displayed in roster snapshot with anchor tag, not in candidate pool). Rationale: user's "fair game" philosophy + simpler prompt + LLM doesn't waste reasoning on protected players + FA threshold correctly calibrated against eligible-pool worst.
- Sum kept internal-only for candidate pool sort. NOT used for borderline trigger (no multi-agent). NOT exposed to LLM. Rationale: deterministic mechanical sort + zero anchoring bias.
- Single atomic VPS deploy with gray rollout. Rationale: 8+ deeply coupled changes (mechanical + prompt + orchestrator + payload + metric retirement); half-deployed state would be hard to diagnose; gray rollout (cron paused → manual verify → enable) catches obvious failures before silent breakage.
- Multi-agent → single-LLM 2-step (not 1-step, not 3-step): 1-step bundles too much reasoning into one call (rationale/verdict misalignment risk); 3-step adds latency with no benefit since fa_classify + fa_rank can co-occur. 2-step (rank+classify → verdict) preserves reasoning structure with minimal call count.
- M1/M4' metric infrastructure retired (no functional replacement). Quality monitoring replaced by backtest automation (slow but high-signal) + `/weekly-review` human spot check (fast but subjective). Both layers together cover daily and seasonal timescales.

**Sequencing** (3 phases, internal serial dependencies noted):
- **Phase 1 — Foundation**:
  - 1a: `anchor_filter.py` + `test_anchor_filter.py` (parallel-safe).
  - 1b: `roster_config.json` schema update + initial seed (parallel-safe).
  - 1c: `payload_slimmer.py` update + tests (parallel-safe — independent module).
  - 1d: `fa_compute.py` refactor (depends on 1a anchor_filter being defined; simplifies `pick_weakest_v4_sp`, removes urgency machinery, updates FA tags).
- **Phase 2 — Pipeline rewrite**:
  - 2a: `_phase6_sp.py` rewrite — drops multi-agent orchestration, implements 2-step single-LLM flow (depends on Phase 1 completion).
  - 2b: 2 new prompt templates (`prompt_sp_b2_step_a.txt`, `prompt_sp_b2_step_b.txt`) (depends on 2a payload schema).
- **Phase 3 — Deploy + monitoring**:
  - 3a: Documentation update — `sp-b2-cutover-design.md` (new), CLAUDE.md SP section rewrite, superseded markings on B1 docs.
  - 3b: Backtest automation implementation per `sp-decisions-backtest-automation.md`.
  - 3c: VPS gray rollout — push to feat branch, capture B1 commit hash, merge to master, VPS pull, stop cron, manual trigger 1-2 runs, verify output structure + verdict reasonableness, enable cron.
  - 3d: Weekly_review SOP update to include backtest review step.

**Deployment**:
- Branch: `feat/sp-b2-collapse`.
- VPS continues running B1 pipeline through development.
- Cutover sequence: branch merged to master → VPS pull → `pkill cron` (or disable specific job) → `bash bin/vps-run.sh 'cd /opt/mlb-fantasy/daily-advisor && python3 fa_scan.py ...'` 1-2 runs → review output GitHub Issue + Telegram → re-enable cron.
- **Rollback mechanism**: `git revert <B2 merge commit>` on master, VPS pull, re-enable cron. This is the only rollback operation — does NOT involve `git reset` or `git checkout` to any hash (which would discard unrelated commits that landed during B2 development).
- **B1 commit hash captured for verification** (NOT as rollback target): record the pre-B2 master HEAD in `docs/sp-b2-cutover-design.md` "B1 reference hash" section. Used post-revert to verify the working tree matches B1 state (`git diff <B1 hash> HEAD` should be empty modulo unrelated commits). If revert hits merge conflict (intervening unrelated commits modified same files), resolve manually then revert.

## Testing Decisions

**Testing philosophy**: Test external behavior only. `anchor_filter` external contract is "given roster + anchor name lists, return filtered roster preserving order". Tests assert input→output correspondence, not internal mechanism. `fa_compute.py` tests validate observable outputs (Sum values, candidate pool composition, tag presence/absence), not internal computation steps. `_phase6_sp.py` rewrite is validated via gray rollout, not unit tests (existing convention for multi-LLM orchestrators).

**Modules under unit test**:

1. **`anchor_filter.py`** (new, deep module) — `daily-advisor/tests/test_anchor_filter.py`:
   - Empty roster → empty output.
   - Empty anchor lists (both `None` and `[]`) → roster unchanged.
   - Single cant_cut anchor matches → that player removed.
   - Single weekly_anchor matches → that player removed.
   - Overlap (player in both lists) → removed once, no duplication.
   - Case-insensitive name match ("tarik skubal" matches "Tarik Skubal").
   - Accent normalization (alignment with `_normalize` in `rp_svh_scan.py`).
   - Apostrophe normalization.
   - Roster order preserved for non-anchors.
   - Idempotent (applying twice gives same result).
   - Anchor name not in roster → no-op, no error.
   - Mixed case + accent + apostrophe combinations.
   - Prior art: `daily-advisor/tests/test_rp_svh_scan.py` (43 pure-function cases), `daily-advisor/tests/test_pending_parser.py` (16 cases).

2. **`fa_compute.py`** (modified) — `daily-advisor/tests/test_fa_compute_v4.py` (47 existing SP v4 tests) and `daily-advisor/tests/test_fa_compute.py` (32 existing batter-heavy tests):
   - In `test_fa_compute_v4.py`: delete tests for removed functions (`compute_urgency_v4_sp`, `_factor_2026_sum_v4`, `_factor_2025_sum_v4`, `_factor_luck_regression_v4`, slump_hold gate paths, Sum ≥40 hard floor, ✅ 雙年菁英 tag, ⚠️ Breakout 待驗 tag). Update `pick_weakest_v4_sp` tests for simplified signature. Add regression tests for new behavior: Sum ascending order, anchors absent from output (anchor_filter integration), N defaults to 3, BBE<30 still filtered, Rotation Gate still applied.
   - In `test_fa_compute.py`: minimal edits, only if shared helpers (e.g., `compute_2025_sum` for batter) are touched. Most batter tests unchanged.
   - Expected final SP v4 test count: 25-35 (down from 47).
   - Prior art: existing tests in same files.

3. **`payload_slimmer.py`** (modified):
   - Existing test coverage status: verify via Glob during Phase 1; if tests exist, update for `prior_v4` removal and `_ALLOWED_TAGS` expansion. If no tests exist, add basic coverage for `slim_entry` field selection.

**Modules NOT under unit test** (per existing convention):
- `_phase6_sp.py` — multi-LLM orchestrator (now single-LLM 2-step). Validation via VPS gray rollout (Phase 3c).
- 2 new prompt templates — content-only, validated via gray rollout.
- `roster_config.json` — configuration data, no logic.
- Backtest automation module — separate test plan defined in its own issue.

**Gray rollout validation** (Phase 3c):
- Manual trigger 1-2 fa-scan runs on VPS after deploy, before re-enabling cron.
- Acceptance criteria: (a) script completes without exception; (b) GitHub Issue posted with valid body structure; (c) Telegram summary posted; (d) verdict (drop_X_add_Y / watch / pass) is structurally valid JSON; (e) reasoning text references the eligible-pool SPs (not anchors); (f) FA classification + ranking present.
- If any criterion fails: leave cron paused, investigate, revert if needed.

**Post-deploy monitoring**:
- Daily fa-scan continues via cron.
- `/weekly-review` skill updated to include "SP verdict spot check" step — surface any decisions that look wrong intuitively.
- Backtest automation accumulates verdict-vs-outcome data; first baseline reading at Week 4 post-deploy → `docs/sp-b2-baseline.md`.

## Out of Scope

- `/weekly-anchor` skill for managing `weekly_anchor_sp` list — deferred. Manual JSON edit acceptable initially.
- Batter v4 framework changes — already thin, no parallel work needed.
- RP-SV+H SOP changes — independent track via `issues/rp-svh-sop.md`.
- Removal of `prior_stats` from `roster_config.json` data structure — batter path still consumes; only SP read path stops consuming; data stays populated.
- Yahoo IL/NA status tag (`⚠️ IL 短期` etc.) — orthogonal, kept as-is.
- `backfill_prior_stats_v4.py` script — kept for batter use and potential future SP re-introduction.
- 2025 percentile table in CLAUDE.md — kept as reference; no longer consumed by SP code path.
- `metrics_reader.py` backward compatibility — explicitly out of scope since M1/M4' metrics are retired with multi-agent collapse. Phase 1 includes a grep check to determine whether `metrics_reader.py` has a batter path: if SP-only, delete the file + `test_metrics_reader.py`; if batter path exists, prune SP-related logic only.
- Re-introduction of multi-agent for any SP path in the future — Phase 6 multi-agent is permanently retired. Re-introduction would require new design.

## Further Notes

**Background context**:
- B1 cutover went live 2026-05-26 with planned 4-week observation through 2026-06-22. This work aborts B1 observation; documentation (`sp-b1-cutover-design.md`, `sp-b1-observation.md`, `sp-b1-baseline.md`) marked superseded for archival reference.
- Observed pattern (5/17-5/26 across 10 SP reports): step1 P1 dissent rate 0%; lower-position dissent ~60% with no actionable consequence. Multi-agent measurable value concentrated only in step3 borderline review, not step1 ranking — and step3 trigger relies on Sum diff which itself becomes meaningless once Sum is mechanical-internal only. Combined: multi-agent has no net value at current pool size.
- The user's "fair game" philosophy (Q1/Q5/Q6 grill) drives several decisions: removal of slump hold, removal of Sum ≥40 hard floor, complete invisibility of anchor SPs to LLM. Together these put the user in explicit control of "what's protected this week".
- The user's preference for thin design (Q3b/Q4 grill) drives Sum being internal-only, urgency being deleted entirely (not refactored to 3-factor), and the multi-agent → single-LLM collapse (Q9).

**Why now, not after 6/22**:
- User explicitly chose immediate execution (Q7 grill).
- 2025 sample marginal value diminishes as 2026 BBE accumulates (~150 typical); waiting 4 weeks doesn't add baseline value.
- M1/M4' observation infrastructure was already going to be retired post-cutover; bringing the collapse forward eliminates the observation phase that has no functioning safety net at B2 pool sizes.
- B1 baseline was a calibration milestone, not a permanent commitment. Pipeline iteration is expected per the B1 observation doc's "After observation period" section.

**Risk mitigation**:
- Atomic deploy + gray rollout: no half-state, manual verification catches obvious failures.
- Branch-based development: VPS pipeline unaffected during build.
- Rollback via `git revert <B2 merge commit>` (NOT reset/checkout to hash) — preserves intervening unrelated commits.
- Backtest automation in Phase 3: quality monitoring active by cutover, not deferred.
- 2-step single-LLM (not 1-step): preserves reasoning structure, reduces rationale/verdict misalignment risk.
- Step A JSON validation + retry + Telegram alert + fall-through to `pass` verdict: preserves B1 graceful-degrade behavior; pipeline never crashes cron silently.
- `_build_step_a_payload` reads only anchor-filtered `weakest`, never raw `my_roster`: eliminates anchor leak path into LLM context.
- `roster_config.json` `.get("weekly_anchor_sp", [])` with default: handles partial-pull race during VPS update.

**Related work (no direct dependency)**:
- 2026-05-26 metric emit infrastructure (issues 008/009) — retired by this PRD.
- Batter v4 thin design (production since 2026-04-28) — architectural reference for SP B2 thin mechanical layer.
- `docs/sp-decisions-backtest.md` (existing 9-decision living log) — extended by Phase 3 backtest automation.
- `docs/sp-decisions-backtest-automation.md` (existing design, unimplemented) — triggered by this PRD's Phase 3.
- RP-SV+H SOP (`issues/rp-svh-sop.md`) — independent simplification track on RP side; B2 does not interact.

**Fact corrections from architectural review** (integrated above):
- 3-agent review of PRD v1 surfaced 8 fact errors which are corrected in this revision: tag classification (`⚠️ 賣高運氣` / `✅ 撿便宜運氣` are 2026-based, kept), test file references (both `test_fa_compute.py` + `test_fa_compute_v4.py`), prompt file count and naming (7 actual files with correct names), `payload_slimmer.py` as the real touch point for `prior_v4` removal and `_ALLOWED_TAGS` updates, slump_hold actual location (inside `compute_urgency_v4_sp`, deleted with it), `compute_2025_sum` has no SP path (no action needed), `anchor_filter` signature simplified (no `player_type` parameter), `anchor_filter` single call site documented.

**Open questions intentionally deferred**:
- Exact backtest automation cron schedule + GitHub Issue label query mechanism — defined in implementation issue, not PRD.
- Specific 2-step LLM prompt content (rank+classify JSON schema, final verdict format) — designed in Phase 2b implementation issue.
- `/weekly-anchor` skill — Out of Scope, future work.
- Whether to fully delete `metrics_reader.py` or just stop reading SP metrics — implementation issue decides.
