# SP B2 Cutover Design — Thin Mechanical Layer + 2-Step Single-LLM

> **Status**: Design source of truth (post issue 022 / pre issue 025 cutover).
> Supersedes [`docs/sp-b1-cutover-design.md`](sp-b1-cutover-design.md), [`docs/sp-b1-observation.md`](sp-b1-observation.md), [`docs/sp-b1-baseline.md`](sp-b1-baseline.md).
>
> **B1 reference hash**: `<filled by issue 025 pre-cutover>` (pre-B2 master HEAD; used only for post-revert verification, NOT as rollback target — rollback uses `git revert <B2 merge commit>`).

## Problem Statement

The B1 SP pipeline (v4 5-slot mechanical + Phase 6 multi-agent, production since 2026-05-26) carries three layers of dead weight that no longer serve decision quality:

1. **Mechanical layer is too thick.** Slump hold auto-protects "slumping elites" the user prefers to manage manually. Urgency 4-factor (2026 Sum / 2025 Sum / 21d Δ / IP/Team_G) is computed but never reaches the LLM — only feeds an internal pre-sort that Sum alone could drive. FA tags `✅ 雙年菁英` / `⚠️ Breakout 待驗` depend on 2025 prior data that dilutes more than informs as 2026 BBE matures (~150 typical by late May). Sum exposed to LLM creates anchoring bias by compressing 5 orthogonal slots into one number. Sum ≥40 hard floor is redundant — Sum-asc sort already pushes elites to the bottom. P1-P4 candidate pool oversized — user's anchor filtering reduces eligible pool to 3-5 SPs, P4 forces ranking of non-realistic drop targets.

2. **Multi-agent layer is over-engineered for current pool size.** Across 10 reports 2026-05-17 to 2026-05-26, step1 P1 dissent rate is **0%** — all 3 agents always converge on P1. B2 anchor filtering further compresses eligible pool to 3-5 SPs; 3-agent consensus is statistically near-guaranteed regardless of pipeline health. Multi-agent step1 + master integration consumes ~60% of Phase 6 token budget with zero measurable benefit.

3. **B1 observation infrastructure cannot validate B2.** M1 (agent step1 consensus) and M4' (top-pair borderline rate) both saturate near 100% at B2 pool size regardless of pipeline health. The rollback thresholds (M1 < 0.036 / M4' > 75% for 2 weeks) would never trigger at B2 pool sizes for the right reason — observation period would have no functioning safety net.

## Solution Overview

Two simultaneous refactors deployed atomically:

### Refactor 1 — Thin mechanical layer (mirrors Batter v4 thin, production since 2026-04-28)

```
my-team SPs → anchor_filter → BBE<30 filter → Sum ascending → top-3
              (fa_compute.pick_weakest_v4_sp)                   │
                                                                ▼
                                                          eligible pool
                                                       (LLM sees only this)

FA candidates → Rotation Gate (GS=0 / IP-per-GS<3) → quality filter → FA pool
                (_phase6_sp.py Layer 1.5)                              │
                                                                       ▼
                                                                LLM-visible FAs
```

Rotation Gate is applied to the FA pool only; my-team SPs are sourced from `roster_config.json` and trusted to be SP-eligible (so a roster entry like a swingman or RP-eligible player is not auto-filtered out).

- **Anchors invisible to LLM**: `cant_cut` (lifetime) and `weekly_anchor_sp` (weekly-mutable) both routed through a single `anchor_filter.filter_anchors()` call at the entry of `pick_weakest_v4_sp`. Anchors never appear in roster snapshot, never enter candidate pool, never reach LLM context.
- **2026-only data**: 2025 prior reading removed from SP path. `compute_2025_sum` retained for batter (already batter-only via hardcoded `key_map`).
- **Urgency machinery deleted**: `compute_urgency_v4_sp`, `_factor_2026_sum_v4`, `_factor_2025_sum_v4`, `_factor_luck_regression_v4` removed. Slump hold removed (was inside `compute_urgency_v4_sp`).
- **Sum kept internal-only**: candidate pool sort key. Never exposed to LLM. No borderline trigger needs it (no multi-agent).
- **Sum ≥40 hard floor removed**: redundant with Sum-asc + anchor protection. The user's "fair game" philosophy means non-anchored SPs are drop-eligible regardless of Sum.
- **2025-based FA tags removed**: `✅ 雙年菁英`, `⚠️ Breakout 待驗`. 2026-based tags preserved: `✅ 深投型` / `✅ GB 重型` / `✅ K 壓制` / `✅ 撿便宜運氣` (2026 xERA-ERA) / `✅ 近況確認` (21d-based) / `⚠️ 短局` / `⚠️ Swingman 角色` / `⚠️ xwOBACON 極端` / `⚠️ K 壓制不足` / `⚠️ Command 警示` / `⚠️ 賣高運氣` / `⚠️ 樣本小` / `⚠️ IL 短期` / `⚠️ 近況下滑`.
- **`compute_fa_tags_v4_sp` win_gate short-circuit removed**: tags computed for all FAs; filtering moves entirely to `payload_slimmer._ALLOWED_TAGS`.

### Refactor 2 — Collapse Phase 6 multi-agent → single-LLM 2-step

```
Step A (single LLM call) → rank P1-P3 in eligible pool
                         → classify each FA (worth / borderline / not_worth)
                         → structured JSON output
                              │
                              ▼
Step B (single LLM call) → reads Step A JSON + same full slimmed pools Step A saw
                         → final verdict (drop_X_add_Y / watch / pass) + rationale + watch_target
```

- **7 prompts → 2**: 6-step flow (3 step1 agents → master integrate → borderline review → fa_classify → fa_rank → final master) collapses to Step A + Step B.
- **Step A reads ONLY the anchor-filtered `weakest`** (output of `pick_weakest_v4_sp`), never raw `my_roster` (which still contains anchor data after `_attach_v4_to_my_roster`). Failure mode prevention: payload builder accidentally referencing `my_roster` would leak anchors into LLM context.
- **Step B reads Step A JSON PLUS the full slimmed pools** — not just JSON summary. Step B needs original metrics to reason about, not just Step A's compressed verdict.
- **M1/M4' metric emit retired**: no multi-agent → no consensus signal → `metrics_reader.py` becomes obsolete for SP path (deleted in issue 019 since no batter path existed).

## Anchor Model

| Anchor type | Source | Lifetime | LLM visibility | User edit cadence |
|---|---|---|---|---|
| `cant_cut` | `roster_config.json` `league.cant_cut` | Lifetime hard no-touch | None | Rare (long-term commitment changes) |
| `weekly_anchor_sp` | `roster_config.json` `league.weekly_anchor_sp` | This week only | None | Weekly during `/weekly-review` |

Both lists are name strings, matched case-insensitive with accent + apostrophe normalization (via `name_match.normalize_name`, same primitive as `rp_svh_scan.py`).

**Semantics**:
- `cant_cut` = "lifetime hard no-touch". Current entries: Skubal / Jazz Chisholm / Manny Machado.
- `weekly_anchor_sp` = "this week I've committed to protecting" — slumping elites I'm riding out, recent trade-ins still settling, breakout candidates I want time to verify. Default seed: `["Cole Ragans", "Chris Sale", "Parker Messick"]`.
- **Both invisible to LLM**: anchors never appear in roster snapshot with an "anchor tag", never enter candidate pool. The LLM's view of the team is exactly the eligible-pool top-3.

**Why entirely invisible** (vs. "tagged anchor visible in roster"):
- "Fair game" philosophy: not on a list = drop-eligible. No conflation between "I trust this player" and "this player is mechanically protected".
- Simpler prompt: LLM never wastes reasoning on "should I drop the anchored player?"
- Correct FA threshold calibration: "FA worth picking up" is judged against the weakest realistic drop target (worst non-anchor), not against elite anchors the user won't drop regardless.

## Phase 6 Multi-Agent Retirement Rationale

**Observed dissent**: 0% across 10 SP reports (2026-05-17 to 2026-05-26). All 3 step1 agents always picked the same P1. Lower-position dissent (~60% on P3/P4) had no actionable consequence — master integrate always converged on the same P1 anchor and same FA classification.

**Pool-size saturation argument**: B2 anchor filtering reduces eligible pool to 3-5 SPs. With pool that small, 3-agent consensus is statistically near-guaranteed regardless of pipeline health. The signal "agents disagree" cannot exist when the answer is obvious.

**Cost**: Multi-agent step1 + master integration consumes ~60% of Phase 6 token budget with zero measurable benefit at B2 pool sizes.

**Design always anticipated this**: `docs/sp-b1-observation.md` "After observation period" section explicitly stated *"if dissent surface is rare → consider permanent collapse to single-call"*. B2 acts on that signal.

## Step A → Step B Contract

### Step A — single LLM call

**Input**: anchor-filtered `weakest` (top-3 from `pick_weakest_v4_sp`) + slimmed FA pool.

**Output schema** (structured JSON, validated by Python):

```json
{
  "my_team_rank": [
    {"name": "<SP name>", "rank": 1, "rationale": "<≤80 char>"},
    {"name": "<SP name>", "rank": 2, "rationale": "<≤80 char>"},
    {"name": "<SP name>", "rank": 3, "rationale": "<≤80 char>"}
  ],
  "fa_classify": [
    {"name": "<FA name>", "verdict": "worth" | "borderline" | "not_worth", "rationale": "<≤80 char>"}
  ]
}
```

### Step B — single LLM call

**Input**: Step A JSON output **plus the same full slimmed pools Step A saw**. Step B reasons over original metrics, not Step A's compressed verdict.

**Output schema**:

```json
{
  "action": "drop_X_add_Y" | "watch" | "pass",
  "drop": "<SP name or null>",
  "add": "<FA name or null>",
  "watch_target": "<FA name or null (for watch action)>",
  "reason": "<rationale paragraph>"
}
```

### Validation + Retry + Telegram Alert

- Python calls `json.loads()` on Step A output inside `try/except`.
- **Parse failure**: log error + Telegram alert `"Step A JSON parse failed"` + 1 retry (re-call Step A with same payload).
- **Schema failure** (missing top-level keys / wrong types): same handling.
- **Retry also fails**: final verdict = `pass` + alert. Pipeline never crashes cron silently.

Rationale: B1 multi-agent had graceful degrade via `_multi_agent.py` `all_parsed` / `consensus_check_key`; B2 collapse preserves equivalent resilience.

## Quality Monitoring (replaces retired M1/M4')

**Two layers** running at different cadences:

### Layer 1 — Retrospective backtest automation (Use Case A only for B2)

- Implementation: `daily-advisor/backtest_track.py` + `daily-advisor/_backtest_lib.py` (issue 024).
- Source: GitHub Issues with `fa-scan` label, B2 2-step SP format (post-cutover).
- Extract: verdict (`action` / `drop` / `add` / `reason`) from Step B output.
- Join: subsequent player performance data (Statcast / Yahoo) with the verdict.
- Output: weekly hit-rate, average marginal benefit, surfaced systematic biases → appended to [`docs/sp-decisions-backtest.md`](sp-decisions-backtest.md).
- Cron: weekly Sunday (consistent with `/weekly-review` cadence).
- First run: after issue 025 cutover.

**Use Case B explicitly deferred**: xwOBACON threshold calibration (`calibrate_xwobacon_threshold.py`) — see CLAUDE.md backlog entry. Triggered 4-6 weeks after B2 cutover when sufficient data accumulates.

### Layer 2 — `/weekly-review` human spot check (issue 026)

- New step in `/weekly-review` skill: read last 7 days of fa-scan SP-v4 GitHub Issues, gut-check each verdict's reasoning.
- New step: review `roster_config.json` `league.weekly_anchor_sp` list — confirm names still need protection this week. Edit if changes needed.

**Why two layers**: backtest is slow but high-signal (weeks to surface bias); spot check is fast but subjective (catches obvious misjudgments within hours). Together they cover daily and seasonal timescales.

## Rollback Procedure

- **Only operation**: `git revert <B2 merge commit>` on master, VPS pull, re-enable cron.
- **B1 reference hash** captured pre-cutover for **verification only** (NOT rollback target). After revert, confirm working tree matches B1 state via `git diff <B1 hash> HEAD` should be empty modulo unrelated commits that landed during B2 development.
- **Never** use `git reset --hard <B1 hash>` or `git checkout <B1 hash>` — these discard intervening unrelated commits.
- **If revert hits conflict** (intervening unrelated commits modified same files): resolve manually then revert.

## Configuration Schema

`daily-advisor/roster_config.json` `league` section:

```json
{
  "league": {
    "cant_cut": [
      "Tarik Skubal",
      "Jazz Chisholm Jr.",
      "Manny Machado"
    ],
    "weekly_anchor_sp": [
      "Cole Ragans",
      "Chris Sale",
      "Parker Messick"
    ]
  }
}
```

Code reading `weekly_anchor_sp` uses `.get("weekly_anchor_sp", [])` with empty-list default to handle partial-deploy race.

## Out of Scope

- **`/weekly-anchor` skill**: deferred. Manual JSON edit acceptable initially.
- **Batter framework changes**: already thin, no parallel work.
- **RP-SV+H SOP**: independent track via `issues/rp-svh-sop.md`.
- **`prior_stats` removal from roster_config.json**: batter still consumes; SP read path stops consuming; data stays populated.
- **Backtest Use Case B (xwOBACON calibration)**: backlog, triggered 4-6 weeks post-cutover.
- **Multi-agent reintroduction**: permanently retired for SP path. Future reintroduction requires new design.

## Cross-References

- PRD: [`issues/prd-sp-b2-thin.md`](../issues/prd-sp-b2-thin.md)
- Issues: [`issues/017`](../issues/017-anchor-filter-deep-module.md) – [`026`](../issues/026-weekly-review-sp-spot-check.md)
- Backtest design (Use Case A + B): [`docs/sp-decisions-backtest-automation.md`](sp-decisions-backtest-automation.md)
- Decisions living log: [`docs/sp-decisions-backtest.md`](sp-decisions-backtest.md)
- Superseded B1 design: [`docs/sp-b1-cutover-design.md`](sp-b1-cutover-design.md)
- Batter v4 thin (architectural reference): [`docs/batter-framework-upgrade-design.md`](batter-framework-upgrade-design.md)
