# 018 — payload_slimmer thin (B2)

## Parent PRD

`issues/prd-sp-b2-thin.md`

## What to build

Per PRD §"Modified module — `payload_slimmer.py`". Remove `prior_v4` field from `slim_entry`. Expand `_ALLOWED_TAGS` whitelist to include all 2026-based and 21d-based tags that should reach LLM.

After this slice, the slimmed payload that downstream consumers see no longer carries 2025 prior data and exposes the full set of currently-meaningful tags.

## Acceptance criteria

- [ ] `payload_slimmer.slim_entry` no longer emits `prior_v4` key in output
- [ ] `prior = full_entry.get("prior_stats") or {}` assignment removed from `slim_entry`
- [ ] `_slot_metrics(prior)` call removed
- [ ] `_ALLOWED_TAGS` whitelist expanded — current 6-tag set `{✅ 球隊主力, ⚠️ 上場有限, ⚠️ 樣本小, ⚠️ 短局, ⚠️ IL 短期, ⚠️ Swingman 角色}` extends to add:
  - [ ] `✅ 深投型`
  - [ ] `✅ GB 重型`
  - [ ] `✅ K 壓制`
  - [ ] `✅ 撿便宜運氣`
  - [ ] `✅ 近況確認`
  - [ ] `⚠️ xwOBACON 極端`
  - [ ] `⚠️ K 壓制不足`
  - [ ] `⚠️ Command 警示`
  - [ ] `⚠️ 賣高運氣`
  - [ ] `⚠️ 近況下滑`
- [ ] `daily-advisor/tests/test_payload_slimmer.py` — verify file exists; if not, create with basic coverage of `slim_entry` field selection
- [ ] Test cases cover: `prior_v4` absent from output; allowed tags pass through; disallowed tags filtered out
- [ ] All tests green

## Blocked by

None — can start immediately.

## User stories addressed

- User story 5
- User story 8
- User story 21
