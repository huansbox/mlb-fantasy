# 025 — VPS gray rollout (cutover)

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Deployment")

## What to build

Atomic cutover with gray rollout safety. Capture B1 reference hash, merge `feat/sp-b2-collapse` to master, VPS pull, cron pause, manual trigger verification, cron re-enable. Includes issue 023's CLAUDE.md commit as part of the cutover commit (lockstep).

**HITL** — manual verification gate between cron pause and re-enable is the safety mechanism that the entire B2 design relies on (M1/M4' retired).

## Acceptance criteria

### Pre-cutover

- [ ] All upstream issues completed and merged into `feat/sp-b2-collapse`:
  - [ ] 017 (anchor_filter)
  - [ ] 018 (payload_slimmer thin)
  - [ ] 019 (metrics_reader disposition)
  - [ ] 020 (fa_compute thin refactor)
  - [ ] 021 (_phase6_sp 2-step pipeline + 2 prompts)
  - [ ] 022 (sp-b2-cutover-design.md + B1 superseded markings)
  - [ ] 024 (backtest automation Use Case A)
- [ ] Issue 023 CLAUDE.md content prepared on branch but NOT yet committed to master
- [ ] B1 reference hash captured: `git log -1 --format=%H master` BEFORE B2 merge — record into `docs/sp-b2-cutover-design.md` "B1 reference hash" section

### Cutover

- [ ] Single atomic commit on master includes:
  - [ ] B2 code merge (issues 017-022, 024)
  - [ ] CLAUDE.md SP section rewrite (from issue 023)
  - [ ] CLAUDE.md 「檔案索引」+「待辦」 updates
- [ ] VPS pull: `bash bin/vps-run.sh 'cd /opt/mlb-fantasy && git pull --rebase --no-retry'`
- [ ] Stop fa-scan cron job(s) on VPS — verify with `bash bin/vps-run.sh 'crontab -l'`
- [ ] Backtest cron (from issue 024) remains paused until first run after verification

### Gray rollout verification

- [ ] Manual trigger 1-2 fa-scan runs: `bash bin/vps-run.sh 'cd /opt/mlb-fantasy/daily-advisor && python3 fa_scan.py'`
- [ ] Verify per PRD §"Gray rollout validation":
  - [ ] Script completes without exception
  - [ ] GitHub Issue posted with valid body structure
  - [ ] Telegram summary posted
  - [ ] Verdict (`drop_X_add_Y` / `watch` / `pass`) is structurally valid JSON
  - [ ] Reasoning text references eligible-pool SPs (not anchors)
  - [ ] FA classification + ranking present
- [ ] If any criterion fails: leave cron paused, investigate, revert if needed (rollback path below)

### Post-verification

- [ ] Re-enable fa-scan cron
- [ ] Enable backtest cron (from issue 024) — first real run accumulates B2 verdict data
- [ ] Monitor first 24-48h for unexpected behavior
- [ ] Update `docs/sp-b2-cutover-design.md` with actual cutover date

### Rollback path (documented for incident response)

- [ ] `git revert <B2 merge commit>` on master (NOT `reset` / `checkout` to hash)
- [ ] VPS pull
- [ ] Verification post-revert: `git diff <B1 reference hash> HEAD` should show only unrelated intervening commits — confirms B2 changes reversed without disturbing other work
- [ ] Re-enable cron

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
