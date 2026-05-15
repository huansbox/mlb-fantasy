## Parent PRD

`issues/prd-mlb-query.md`

## What to build

A human-in-the-loop validation pass on the refactored `/stream-sp-deep` skill against the three SP candidates from the prior session (ET 2026-05-16): Cade Cavalli vs BAL, Chris Paddack vs CLE, Chris Bassitt vs WSH. The skill — now consuming the helpers shipped in 010 — is re-run end-to-end and its numerical findings compared against the manually produced deep evaluation in the prior session (recorded in `daily-advisor/stream-sp-pending.md` and the conversation report).

The user reviews the comparison and signs off on whether parity is acceptable. Divergence is treated as the regression signal per the PRD's **Testing Decisions** section: either reconciled (helper fix → re-run) or explicitly accepted (rounding tolerance / upstream data update) before closing this slice.

This slice is **HITL** because "same enough" is a judgment call, not a mechanical assertion.

## Acceptance criteria

- [ ] Refactored skill invoked against Cavalli / Paddack / Bassitt produces a deep evaluation report with game log, opponent windows, and recommendations
- [ ] Game log entries for each SP match the prior session's tables: same dates, same IP / ER / K / BB / HR / PC values; QS column matches manual annotations from prior report
- [ ] Opponent multi-window OPS (BAL / CLE / WSH for 7d / 14d / 30d) match prior session values to two decimal places
- [ ] Season vs-RHP split values for BAL / CLE / WSH match prior session values to two decimal places
- [ ] User reviews the comparison and records sign-off (in `daily-advisor/stream-sp-pending.md` 備註, or the commit message closing this slice)
- [ ] If divergence is observed, root cause is documented and either fixed (with re-run) or explicitly accepted with reasoning, before sign-off

## Blocked by

- `issues/010-mlb-query-helper-and-skill-refactor.md`

## User stories addressed

Reference by number from `issues/prd-mlb-query.md`:

- User story 1 (QS counts validated against prior manual counts)
- User story 2 (decimal innings validated implicitly via QS match)
- User story 3 (multi-window opponent trends validated)
- User story 4 (handedness-aware split validated)
- User story 5 (manager-facing QS correctness — final validation gate)
