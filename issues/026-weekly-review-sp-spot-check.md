# 026 — /weekly-review SP spot check + anchor list review

## Parent PRD

`issues/prd-sp-b2-thin.md` (User story 1, 13; Q11 grill decision)

## What to build

Update `/weekly-review` skill content to include two new steps:
1. Review `roster_config.json` `league.weekly_anchor_sp` list — is it still accurate this week?
2. Spot-check last 7 days of fa-scan SP-v4 GitHub Issues for any decisions that look intuitively wrong (human safety net for B2 quality monitoring, complementing backtest automation in issue 024).

Pure skill content slice — no code, no tests.

## Acceptance criteria

- [ ] `/weekly-review` skill markdown (`.claude/commands/weekly-review.md` or wherever skill is defined) updated to include:
  - [ ] Step: "Review `roster_config.json` `league.weekly_anchor_sp` list — confirm names still need protection this week. Edit JSON if changes needed."
  - [ ] Step: "Read last 7 days of fa-scan SP-v4 GitHub Issues (`gh issue list -R huansbox/mlb-fantasy --label fa-scan --search 'SP-v4'`). For each verdict (drop_X_add_Y / watch / pass), apply gut check: does the reasoning hold up? Surface anything that smells off."
- [ ] Skill references B2 design doc (`docs/sp-b2-cutover-design.md`) and anchor mechanism instead of B1 multi-agent / M1-M4' references
- [ ] No code changes

## Blocked by

- `issues/017-anchor-filter-deep-module.md` — needs `weekly_anchor_sp` field to exist in `roster_config.json`

## User stories addressed

- User story 1
- User story 13
