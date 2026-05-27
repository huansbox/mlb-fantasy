# 017 — anchor_filter deep module

## Parent PRD

`issues/prd-sp-b2-thin.md`

## What to build

Build `daily-advisor/anchor_filter.py` per PRD §"New deep module — `anchor_filter`". Add `weekly_anchor_sp` field to `roster_config.json` with initial seed. Add pure-function unit tests.

This is a foundation slice — module is built standalone, but consumers (fa_compute in issue 020) won't integrate until later. Following the codebase's existing pattern of standalone modules (`pending_parser.py`, `rp_svh_scan.py`).

## Acceptance criteria

- [ ] `daily-advisor/anchor_filter.py` created with signature `filter_anchors(roster: list[dict], cant_cut_names: list[str] | None, weekly_anchor_names: list[str] | None) -> list[dict]`
- [ ] Pure function — no I/O, no side effects
- [ ] No `player_type` parameter (PRD explicit YAGNI — add only when batter anchor mechanism is built)
- [ ] Case-insensitive name match
- [ ] Accent + apostrophe normalization (align with `_normalize` pattern in `daily-advisor/rp_svh_scan.py`)
- [ ] `None` and `[]` for anchor list params treated identically (roster unchanged)
- [ ] Order of non-anchored players preserved
- [ ] Idempotent (calling twice gives same result)
- [ ] `daily-advisor/tests/test_anchor_filter.py` created with 8-12 cases per PRD §"Testing Decisions":
  - [ ] Empty roster → empty output
  - [ ] Both anchor lists `None` → roster unchanged
  - [ ] Both anchor lists `[]` → roster unchanged
  - [ ] Single cant_cut match → that player removed
  - [ ] Single weekly_anchor match → that player removed
  - [ ] Overlap (name in both lists) → removed once, no duplication
  - [ ] Case-insensitive match (`"tarik skubal"` matches `"Tarik Skubal"`)
  - [ ] Accent normalization
  - [ ] Apostrophe normalization
  - [ ] Order preservation for non-anchors
  - [ ] Idempotent
  - [ ] Anchor name not in roster → no-op, no error
- [ ] `roster_config.json` adds `league.weekly_anchor_sp: ["Cole Ragans", "Chris Sale", "Parker Messick"]`
- [ ] All tests green in isolation (no integration with `fa_compute` yet — integration comes in issue 020)

## Blocked by

None — can start immediately.

## User stories addressed

- User story 1
- User story 11
- User story 15
- User story 16
