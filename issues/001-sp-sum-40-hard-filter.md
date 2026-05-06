## Parent PRD

`issues/prd.md`

## What to build

在 SP 機械層 `pick_weakest_v4_sp` 既有 filter chain（cant_cut / Rotation Gate / BBE<30 / Slump hold）後加入 `Sum ≥40` hard 排除規則。對應 batter Sum≥25 的 P75+ 全方位排除哲學。觸發後 SP 候選池不會列入 5-slot 全 P70+ 的菁英 SP，避免浪費 LLM 算力。

數值 40 為設計初稿，需先用 `daily-advisor/calc_v4_percentiles.py` 跑 2025 SP 池實證 Sum 分布校準（若實際 P75 落 35-38 → 改 36；落 42-45 → 改 42）。

詳見 PRD `Implementation Decisions` 段「機械層」+ `docs/sp-b1-cutover-design.md` §機械層。

## Acceptance criteria

- [ ] 跑 `calc_v4_percentiles.py` 驗算 2025 SP 池 Sum 分布，確認 P75 對應數值，校準閾值（40 或調整）
- [ ] `fa_compute.pick_weakest_v4_sp` 加入 Sum≥{校準值} 排除規則，順序在 cant_cut / Rotation Gate / BBE<30 / Slump hold 之後
- [ ] Boundary case test：Sum=39 入池 / Sum=40 排除 / Sum=41 排除（用實際校準後數值對應 ±1）
- [ ] 組合 case test：cant_cut 球員 Sum=20 仍排除（cant_cut 優先）；Sum=45 但 BBE<30 標 low_confidence（BBE filter 優先，不被 Sum filter 替代）
- [ ] 既有測試（`test_fa_compute_v4.py`）全綠
- [ ] 排除規則命中時不影響 urgency / tags 內部計算（仍保留 backup 用途）

## Blocked by

None - can start immediately

## User stories addressed

- User story 6
- User story 26
