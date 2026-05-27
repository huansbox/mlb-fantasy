# 019 — metrics_reader disposition

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Out of Scope" — `metrics_reader.py` Phase 1 grep check)

## What to build

Determine whether `daily-advisor/metrics_reader.py` has a batter path or is SP-only. Take action accordingly: delete entirely if SP-only, prune SP-related logic if batter path exists.

`metrics_reader.py` reads M1/M4' metric emit blocks from fa-scan GitHub Issues. After B2 multi-agent collapse, M1/M4' metrics are retired for SP path. If batter has no separate metric path, the entire file is dead code.

## Acceptance criteria

- [ ] Grep result documented in commit message or inline comment: does `metrics_reader.py` have a batter-specific code path?
- [ ] If SP-only:
  - [ ] Delete `daily-advisor/metrics_reader.py`
  - [ ] Delete `daily-advisor/tests/test_metrics_reader.py`
  - [ ] Remove any cron job entry that invokes `metrics_reader.py`
- [ ] If batter path exists:
  - [ ] Prune SP-related logic only; preserve batter path intact
  - [ ] Update `test_metrics_reader.py` — delete SP tests; preserve batter tests
- [ ] Full test suite green after changes
- [ ] CLAUDE.md "檔案索引" entry update deferred to issue 023 (will be amended in same commit as CLAUDE.md SP section rewrite) — NOT done in this slice to avoid merge conflict

## Blocked by

None — can start immediately.

## User stories addressed

- User story 17
