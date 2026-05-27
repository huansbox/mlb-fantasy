# 020 — fa_compute thin refactor

## Parent PRD

`issues/prd-sp-b2-thin.md` (§"Modified module — `fa_compute.py`")

## What to build

Single-file refactor of `daily-advisor/fa_compute.py`. Deletes urgency machinery, simplifies `pick_weakest_v4_sp` to use `anchor_filter`, removes Sum ≥40 hard floor + win_gate short-circuit, removes 2025-based FA tags, audits `test_fa_compute_v4.py` accordingly.

This is the largest single slice (8 user stories) but kept as one file because splitting would cause merge conflicts on `fa_compute.py`. Acceptance criteria are staged so a developer can verify code changes (a) and test changes (b) separately.

**Note**: After this slice, `_phase6_sp.py` will not compile because it imports `compute_urgency_v4_sp`. This is expected on `feat/sp-b2-collapse` branch — issue 021 restores integration.

## Acceptance criteria

### (a) Code deletes

- [ ] `compute_urgency_v4_sp` (current line 986) deleted entirely
- [ ] `_factor_2026_sum_v4` (852) deleted
- [ ] `_factor_2025_sum_v4` (871) deleted
- [ ] `_factor_luck_regression_v4` (893) deleted
- [ ] Module constant `_PRIOR_IP_SLUMP_HOLD_MIN` (line 239) deleted
- [ ] Module constant `_SP_SUM_HARD_FLOOR` (~line 840) deleted
- [ ] `pick_weakest_v4_sp` (line 919): `n=4` → `n=3` default; lines 970-972 (hard floor `if score >= _SP_SUM_HARD_FLOOR: continue`) deleted
- [ ] `pick_weakest_v4_sp`: inline `cant_cut` filtering replaced with `from anchor_filter import filter_anchors; filtered = filter_anchors(players, cant_cut, weekly_anchor)` call (accepts new `weekly_anchor` parameter)
- [ ] `compute_fa_tags_v4_sp` win_gate short-circuit (current lines 823-831) removed — `add_tags` / `warn_tags` computed for all FAs; filtering responsibility moves entirely to `payload_slimmer._ALLOWED_TAGS`
- [ ] `v4_add_tags_sp` (line 627): `✅ 雙年菁英` block (lines 640-652) removed; preserve `✅ 深投型`, `✅ GB 重型`, `✅ K 壓制`, `✅ 撿便宜運氣`, `✅ 近況確認`
- [ ] `v4_warn_tags_sp` (line 681): `⚠️ Breakout 待驗` block (lines 729-742) removed; preserve `⚠️ 樣本小`, `⚠️ 短局`, `⚠️ Swingman 角色`, `⚠️ xwOBACON 極端`, `⚠️ K 壓制不足`, `⚠️ Command 警示`, `⚠️ 賣高運氣`, `⚠️ 近況下滑`, `⚠️ IL 短期`
- [ ] `compute_2025_sum` (line 432): unchanged (already batter-only)
- [ ] `compute_sum_score_v4_sp`: unchanged (still computes Sum for internal use)

### (b) Test audit (test_fa_compute_v4.py)

- [ ] Delete tests for `compute_urgency_v4_sp`, `_factor_*_v4`, slump_hold gate paths
- [ ] Delete tests for Sum ≥40 hard floor
- [ ] Delete tests for `✅ 雙年菁英`, `⚠️ Breakout 待驗` tags
- [ ] Update `pick_weakest_v4_sp` tests for new signature (n=3 default, `weekly_anchor` parameter, `anchor_filter` integration)
- [ ] Add regression tests:
  - [ ] Sum ascending order preserved
  - [ ] Both cant_cut + weekly_anchor names absent from output
  - [ ] N defaults to 3
  - [ ] BBE<30 still filtered via existing low_confidence logic
  - [ ] Rotation Gate (GS=0 or IP/GS<3) still applied
- [ ] Final test count: 25-35 (down from 47)
- [ ] `pytest daily-advisor/tests/test_fa_compute_v4.py` all green
- [ ] `pytest daily-advisor/tests/test_fa_compute.py` (32 batter tests) still all green — minor edits only if shared helpers touched

## Blocked by

- `issues/017-anchor-filter-deep-module.md` — needs `anchor_filter.filter_anchors` interface defined and importable

## User stories addressed

- User story 2
- User story 3
- User story 4
- User story 5
- User story 6
- User story 7
- User story 8
- User story 9
- User story 11
