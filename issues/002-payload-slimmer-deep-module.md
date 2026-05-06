## Parent PRD

`issues/prd.md`

## What to build

把現有 `_phase6_sp._slim_my_team_entry` / `_slim_fa_entry` 兩個函式重構為單一深模組「payload_slimmer」，責任：給定完整 entry，輸出 LLM-safe payload。模組接口 `slim_entry(full_entry, role)`，role 為 `'my_team'` 或 `'fa'`。

B1 schema 強制：
- **不出現的欄位**：`score`（v4 Sum 加總）/ `breakdown.sum`（加總分）/ `urgency` / `factors` / evaluation tags（雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣 / 深投型）
- **必出現的欄位**：`name` / `team` / `position` / 5-slot raw + percentile（IP/GS, Whiff%, BB/9, GB%, xwOBACON 各自分數）/ 雙年 prior raw + percentile / 21d xwOBACON Δ + BBE / PA-based tags / sample tags / `low_confidence` / `selected_pos` / `status`

Schema 測試覆蓋 B1 defenders（防未來改 fa_compute 時把 sum/urgency/tags 漏進 LLM payload）。

詳見 PRD `Implementation Decisions` 段「Payload Slimmer」+ `docs/sp-b1-cutover-design.md` §LLM 層 §1。

## Acceptance criteria

- [ ] 抽出 `payload_slimmer.slim_entry(entry, role)` 為單一深模組（同檔案內或獨立 module 皆可，但接口統一）
- [ ] 既有 `_build_*_payload` 函式改用新 slim_entry 接口（行為等價，僅 schema 不同）
- [ ] Schema test：給 full entry（含 sum / urgency / evaluation tags），slim 後不應有 `score` / `breakdown.sum` / `urgency` / `factors` / 任一 evaluation tag
- [ ] Schema test：給 full entry，slim 後應有 5-slot percentile / PA-based tags / sample tags / low_confidence
- [ ] my_team role vs fa role 兩個分支獨立測試
- [ ] FA-only 欄位（`d1` / `d3` / `waiver_date` / `pct`）只在 role='fa' 出現
- [ ] my_team-only 欄位（`urgency` 已移除；`prior_*` 雙年 prior）只在 role='my_team' 出現（如有差異）
- [ ] 既有 `tests/test_phase6_sp.py` 端對端測試全綠（payload schema 變了但 dispatcher 行為應仍 OK，因為 prompt 還沒改）

## Blocked by

None - can start immediately

## User stories addressed

- User story 2
- User story 3
- User story 4
- User story 5
- User story 23
