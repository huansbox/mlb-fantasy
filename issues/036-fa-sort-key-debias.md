# 036 — FA 候選排序鍵去 sum_diff 偏置

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「判斷流程去偏」）

## What to build

batter FA 候選在 payload 的呈現順序改用 **%owned 降序**（與系統自身判斷無關的外部市場訊號），取代現行的 vs-P1 sum_diff 降序 — 消除「P1 特別弱時整批候選的機械分差一起膨脹、注意力順序被偏置」的問題。與 batter v4 thin「Sum 不暴露、hint 非 verdict」哲學一致。

## Acceptance criteria

- [ ] FA 候選排序鍵改 %owned 降序（同分穩定次序明確定義）
- [ ] sum_diff 不再影響呈現順序（其餘用途如 win_gate 提示不在本片範圍）
- [ ] fixture 回歸驗證新排序
- [ ] 部署後隔日 issue payload 順序符合新鍵

## Blocked by

None - can start immediately

## User stories addressed

- User story 23
