# 024 — Backtest automation Use Case A (decision tracking)

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"New module — backtest automation"; PRD User story 22)

Design source: `docs/sp-decisions-backtest-automation.md` Use Case A only. Use Case B (xwOBACON threshold calibration) explicitly deferred — see issue 023 acceptance criteria for backlog entry.

## What to build

Implement Use Case A from the existing backtest automation design — reads B2 fa-scan SP GitHub Issues, extracts verdict + reasoning, joins with subsequent player performance, appends weekly hit-rate + marginal benefit summary to `docs/sp-decisions-backtest.md`.

Quality monitoring layer for B2 — replaces retired M1/M4' metrics with retrospective verdict-vs-outcome tracking. Builds on existing 9-decision living log.

## Acceptance criteria

- [ ] `daily-advisor/_backtest_lib.py` shared module per `docs/sp-decisions-backtest-automation.md` §7 priority order
- [ ] `daily-advisor/backtest_track.py` Use Case A implementation:
  - [ ] Reads GitHub Issues with `fa-scan` label, filters to B2 2-step SP-v4 format (post-cutover)
  - [ ] Extracts verdict (`action`, `drop`, `add`, `reason`) from Step B output
  - [ ] Joins with subsequent player performance data (Statcast / Yahoo)
  - [ ] Player ID resolution per design doc §3.4 fallback chain (handles homonym risk)
- [ ] Cron schedule defined — weekly Sunday consistent with `/weekly-review` cadence
- [ ] Output appendable to `docs/sp-decisions-backtest.md`: weekly hit-rate, average marginal benefit, surfaced systematic biases
- [ ] Unit tests for `_backtest_lib.py` pure functions (issue parser, ID resolver, hit-rate calc)
- [ ] Integration test on 1-2 historical issues (manually crafted B2-format fixture if no real B2 issues yet exist pre-cutover)
- [ ] Use Case B explicitly NOT implemented — `calibrate_xwobacon_threshold.py` not created
- [ ] Cron job entry added but disabled until issue 025 deploys B2 — first real run after cutover

## Blocked by

- `issues/021-phase6-sp-2step-pipeline.md` — needs B2 issue body format stable (Step A/B JSON schemas locked) to write parser

## User stories addressed

- User story 13
- User story 22
