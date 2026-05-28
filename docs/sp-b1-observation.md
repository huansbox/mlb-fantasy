# SP B1 Cutover — Observation Period SOP

> **Superseded** by [`docs/sp-b2-cutover-design.md`](sp-b2-cutover-design.md). B1 observation period aborted at B2 cutover — M1/M4' metrics retired with multi-agent collapse. Kept for archival reference.

> Issue: `issues/009-b1-production-cutover.md` · Baseline: `docs/sp-b1-baseline.md` · Design: `docs/sp-b1-cutover-design.md`

## Status

🟢 **Observation period running** — cutover 2026-05-26. Week 1-2 baseline accumulation; Week 3-4 threshold enforcement.

## Cutover summary

- 2026-05-26 commit `4454825` pushed; VPS pulled same day.
- Production daily fa-scan cron (TW 12:30) starts emitting new metric fields from 2026-05-27 onward: `sp_p1_pair_borderline` + `fa_top1_pair_borderline`.
- B1 prompts (issues 005 / 006) already production since 2026-05-07.

## Retreat thresholds (from baseline)

| Trigger | Condition | Action |
|---------|-----------|--------|
| **G1 — M1 collapse** | M1 SP weekly rate < **0.036** for 2 consecutive weeks | Fallback to single-LLM SP (G-pre2). Open `fix/g-pre2-sp-fallback` branch and follow `docs/sp-b1-baseline.md` §G-pre2 SOP. |
| **G1 alt — M4' over-trigger** | M4' SP weekly rate > **75%** (top1-pair) for 2 consecutive weeks | Same as above. |

Both rules are OR-combined: either firing trips the retreat. M4 (any-pair) rule retired — baseline saturated 100%.

## Weekly review SOP (every Sunday) — RETIRED

> **Retired**: `metrics_reader.py` deleted in B2 cutover (issue 019, commit `050dc82`). M1/M4' metrics retired with Phase 6 multi-agent collapse. The commands below no longer run. Replaced by `backtest_track.py` (issue 024) + `/weekly-review` Phase 1D human spot check (issue 026). See `docs/sp-b2-cutover-design.md` §"Quality Monitoring".

```bash
# RETIRED — no longer runnable post-B2:
# cd /opt/mlb-fantasy/daily-advisor
# python3 metrics_reader.py --days 7
```

Output is JSON. Compare against thresholds:

| Field | Compare to | Trigger? |
|-------|-----------|----------|
| `sp_breakdown.p1_match_rate` | 0.036 | < threshold → bank as Week N M1 fail |
| `sp_breakdown.p1_pair_borderline_rate` | 0.75 | > threshold → bank as Week N M4' fail |
| `fa_breakdown.p1_match_rate` | (informational) | track but not gating |
| `fa_breakdown.p1_pair_borderline_rate` | (informational) | track but not gating |

Record weekly result at the bottom of this file (see §Weekly log).

If **two consecutive weeks** fail the same M1 or M4' trigger → execute G-pre2 fallback (`docs/sp-b1-baseline.md` §G-pre2 SOP).

If one week fails, next week passes → reset counter, observation continues.

## Observation period plan (4 weeks)

| Week | Dates | Goal |
|------|-------|------|
| 1 | 2026-05-26 → 2026-06-01 | Smoke check: new fields emitted, reader runs clean. No threshold enforcement. |
| 2 | 2026-06-02 → 2026-06-08 | First real weekly comparison. Set baseline expectation. |
| 3 | 2026-06-09 → 2026-06-15 | Begin threshold enforcement. One failure starts the counter. |
| 4 | 2026-06-16 → 2026-06-22 | Second consecutive failure → execute G-pre2. Otherwise pass observation. |

## After observation period

If no retreat triggered through Week 4:
- B1 cutover formally accepted.
- Move baseline doc to "Reference" status.
- Re-evaluate whether multi-agent pipeline gives net value vs single-call (Phase 6 design originally said "if dissent surface is rare → consider permanent collapse to single-call").
- Decision recorded in `docs/sp-b1-cutover-design.md` §Long-term.

If retreated:
- Document trigger date, week-by-week numbers, root cause hypothesis in `docs/sp-b1-cutover-design.md`.
- Open new issue for permanent fallback evaluation.

## Weekly log

> Format: `## Week N (YYYY-MM-DD → YYYY-MM-DD)` heading, then JSON metric output + verdict (pass / M1 fail / M4' fail).

(populate from Sunday onwards)
