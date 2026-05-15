## Parent PRD

`issues/prd-mlb-query.md`

## What to build

A single Python module under `daily-advisor/` exposing the two helpers described in the PRD's **Solution** section (`gamelog_with_qs`, `opponent_context`), backed by the pure functions described in **Implementation Decisions** (innings parser, Quality Start derivation). Concurrent with the helper module, the `.claude/commands/stream-sp-deep.md` skill is rewritten so Step 1 and Step 2 invoke the helpers in place of inline Python heredoc, per the PRD's last Implementation Decision bullet.

End-to-end completion: an AI session running the refactored skill on VPS can fetch a SP's game log (with QS / decimal innings enriched) and an opponent's multi-window + handedness context via two helper invocations — without ever writing inline heredoc Python. Numerical parity against the prior session's manual report is **out of scope for this slice** and handled by `issues/011-stream-sp-deep-e2e-parity.md`.

## Acceptance criteria

- [ ] Innings parser pure function maps "0.0" / "5.0" / "5.2" / "6.0" / "7.1" to the expected float (treating frac as thirds); covered by unit tests
- [ ] Quality Start derivation pure function returns true for (6.0, 3 ER) and false for (5.2, 0 ER); boundary cases covered by unit tests
- [ ] `gamelog_with_qs` returns a list of appearances where every entry carries `ip_decimal` (float) and `qs` (bool) fields; other raw API fields pass through unchanged
- [ ] `opponent_context` returns a dict containing entries for 7d / 14d / 30d windows plus a vs-handedness split entry; SP handedness is resolved internally from the SP identifier, not passed by caller
- [ ] `.claude/commands/stream-sp-deep.md` contains zero inline Python heredoc; Step 1 and Step 2 invoke the helpers
- [ ] The "Quoting hint" warning block in `stream-sp-deep.md` is removed
- [ ] The game log table template in `stream-sp-deep.md` includes a QS column
- [ ] Helper module is deployed to `/opt/mlb-fantasy/daily-advisor/` on VPS
- [ ] Smoke check: invoking the helpers on VPS against Cavalli (mlb_id 676917) returns a non-empty gamelog list and a populated `opponent_context` dict — this slice does NOT assert numerical correctness against prior session

## Blocked by

None - can start immediately

## User stories addressed

Reference by number from `issues/prd-mlb-query.md`:

- User story 1 (QS boolean in gamelog)
- User story 2 (decimal innings)
- User story 3 (multi-window opponent trend)
- User story 4 (auto handedness resolution)
- User story 5 (mechanical QS counts — feature delivered; correctness verified in 011)
