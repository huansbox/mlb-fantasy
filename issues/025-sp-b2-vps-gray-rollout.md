# 025 — VPS gray rollout (cutover)

> **Status: CLOSED — 2026-05-31.** Cutover live 2026-05-28 (commit `95f879a`, TW 15:24). 24-48h monitoring window passed clean: three consecutive structurally-valid B2 production runs — #255 (5/28, manual-verified `pass`), #259 (5/29 auto, `drop_X_add_Y`), #263 (5/30 auto, `drop_X_add_Y`). Anchor invisible throughout (Skubal never surfaces in eligible pool / reasoning). Backtest cron installed, first real run scheduled 2026-05-31 06:00 UTC = TW 14:00 (accumulates B2 verdict data going forward — tracked separately, not a gate for closing this issue). Rollback path never triggered. See closeout summary below.

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Deployment")

## What to build

Atomic cutover with gray rollout safety. Capture B1 reference hash, merge `feat/sp-b2-collapse` to master, VPS pull, cron pause, manual trigger verification, cron re-enable. Includes issue 023's CLAUDE.md commit as part of the cutover commit (lockstep).

**HITL** — manual verification gate between cron pause and re-enable is the safety mechanism that the entire B2 design relies on (M1/M4' retired).

## Acceptance criteria

### Pre-cutover

- [x] All upstream issues completed and merged into `feat/sp-b2-collapse`:
  - [x] 017 (anchor_filter)
  - [x] 018 (payload_slimmer thin)
  - [x] 019 (metrics_reader disposition)
  - [x] 020 (fa_compute thin refactor)
  - [x] 021 (_phase6_sp 2-step pipeline + 2 prompts)
  - [x] 022 (sp-b2-cutover-design.md + B1 superseded markings)
  - [x] 024 (backtest automation Use Case A)
- [x] Issue 023 CLAUDE.md content prepared on branch but NOT yet committed to master
- [x] B1 reference hash captured: `git log -1 --format=%H master` BEFORE B2 merge — record into `docs/sp-b2-cutover-design.md` "B1 reference hash" section → `a9967c5`

### Cutover

- [x] Single atomic commit on master includes:
  - [x] B2 code merge (issues 017-022, 024)
  - [x] CLAUDE.md SP section rewrite (from issue 023)
  - [x] CLAUDE.md 「檔案索引」+「待辦」 updates
- [x] VPS pull: `bash bin/vps-run.sh 'cd /opt/mlb-fantasy && git pull --rebase --no-retry'`
- [x] Stop fa-scan cron job(s) on VPS — verify with `bash bin/vps-run.sh 'crontab -l'`
- [x] Backtest cron (from issue 024) remains paused until first run after verification

### Gray rollout verification

- [x] Manual trigger 1-2 fa-scan runs: `bash bin/vps-run.sh 'cd /opt/mlb-fantasy/daily-advisor && python3 fa_scan.py'`
- [x] Verify per PRD §"Gray rollout validation" (all confirmed via GitHub Issue #255):
  - [x] Script completes without exception
  - [x] GitHub Issue posted with valid body structure
  - [x] Telegram summary posted
  - [x] Verdict (`drop_X_add_Y` / `watch` / `pass`) is structurally valid JSON
  - [x] Reasoning text references eligible-pool SPs (not anchors)
  - [x] FA classification + ranking present
- [x] If any criterion fails: leave cron paused, investigate, revert if needed — N/A, no criterion failed

### Post-verification

- [x] Re-enable fa-scan cron
- [x] Enable backtest cron (from issue 024) — first real run scheduled 2026-05-31 06:00 UTC; accumulates B2 verdict data going forward
- [x] Monitor first 24-48h for unexpected behavior — clean (#255 / #259 / #263 all structurally valid, anchor invisible)
- [x] Update `docs/sp-b2-cutover-design.md` with actual cutover date — `Status: Production live since 2026-05-28`

### Rollback path (documented for incident response)

> **Not executed.** B2 stable through monitoring window; no rollback triggered. Steps retained for future incident reference.

- [ ] `git revert -m 1 <B2 merge commit>` on master (NOT `reset` / `checkout` to hash) — `git revert -m 1 95f879a`
- [ ] VPS pull
- [ ] Verification post-revert: `git diff <B1 reference hash> HEAD` (`a9967c5`) should show only unrelated intervening commits — confirms B2 changes reversed without disturbing other work
- [ ] Re-enable cron

## Closeout summary (2026-05-31)

| Item | Result |
|------|--------|
| Cutover commit | `95f879a` (no-ff merge, 2026-05-28 TW 15:24) |
| B1 reference hash | `a9967c5` (verification only, not rollback target) |
| First B2 production run | #255 (5/28) — `pass`, manual-verified all sub-criteria |
| Auto-run day 1 | #259 (5/29) — `drop_X_add_Y`, structurally valid |
| Auto-run day 2 | #263 (5/30) — `drop_X_add_Y` (drop Severino → add Trevor McDonald), structurally valid |
| Anchor invisibility | Confirmed across all 3 runs (Skubal never in pool/reasoning) |
| Backtest cron | Installed (`cron_backtest.sh`, commit `e55fbd5`); first run 2026-05-31 TW 14:00 — ongoing data accumulation, tracked under issue 024 |
| Rollback | Never triggered |

**Follow-on (not gating this issue):**
- Backtest first-run success verification → today TW 14:00 onward (issue 024 / `docs/sp-decisions-backtest.md`)
- `#263` live signal `drop Severino → add Trevor McDonald`: resolved — user dropped Severino (added José A. Ferrer + Bryan King, NOT McDonald; roster_sync commit `365dbae`). Severino transformation watch closed.

## Blocked by

- `issues/017-anchor-filter-deep-module.md`
- `issues/018-payload-slimmer-thin-b2.md`
- `issues/019-metrics-reader-disposition.md`
- `issues/020-fa-compute-thin-refactor.md`
- `issues/021-phase6-sp-2step-pipeline.md`
- `issues/022-sp-b2-design-docs.md`
- `issues/023-claude-md-sp-section-rewrite.md`
- `issues/024-backtest-automation-decision-tracking.md`

(`issues/026-weekly-review-sp-spot-check.md` is parallel — does not gate VPS deploy.)

## User stories addressed

- User story 12
- User story 18
- User story 19
