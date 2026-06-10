# 036 — FA 候選排序鍵去 sum_diff 偏置

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「判斷流程去偏」）

## What to build

batter FA 候選在 payload 的呈現順序改用 **%owned 降序**（與系統自身判斷無關的外部市場訊號），取代現行的 vs-P1 sum_diff 降序 — 消除「P1 特別弱時整批候選的機械分差一起膨脹、注意力順序被偏置」的問題。與 batter v4 thin「Sum 不暴露、hint 非 verdict」哲學一致。

## Acceptance criteria

- [x] FA 候選排序鍵改 %owned 降序（同分 name 升序 / 缺 pct 排末 / pct=0 視為真值）✅ 2026-06-10
- [x] sum_diff 不再影響呈現順序（win_gate 提示等其餘用途不動）✅ 2026-06-10
- [x] fixture 回歸驗證新排序（`tests/test_fa_sort_key.py` 8 cases，含 sum_diff 不影響順序 / 不變異輸入）✅ 2026-06-10
- [ ] 部署後隔日 issue payload 順序符合新鍵 — ⏳ 6/11 12:30 cron 後驗證

> 實作備註（2026-06-10，雲端 session，PR #308，merge `7e8bc91`）：純函式 `_sort_fa_by_owned`（fa_scan.py）；只動 batter `_build_pass2_data_batter_v4` 的 FA 候選段，SP 路徑（decision_order 排序）不在範圍。

## Blocked by

None - can start immediately

## User stories addressed

- User story 23
