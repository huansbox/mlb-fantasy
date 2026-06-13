## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

三個 SP 先行指標欄位 + payload 行。**此片為對前一輪 PRD「SP payload 不動」的有意 scope 變更**。

1. **CSW% 21d 滾動**：called + swinging strikes / pitches，K 的先行指標（比 season 快照 Whiff% 早幾週）。
2. **球速 delta**：YoY / 21d / 最近一場三窗 — 突破前兆 + 傷勢前兆雙向，保護自家 SP 的 ERA/WHIP。
3. **K-BB% 小樣本快篩**：BBE<30 死區從「純棄權」改為 K-BB%（per BF）+ stabilization 框架（K% ~70 BF 可信）。

**資料前提修正（已驗證）**：`savant_rolling.py` 每日抓 pitch-level CSV，但聚合後 JSON 只留 BBE 級欄位，**丟掉了 CSW 需要的 `description` 與 velo 需要的 `release_speed`**。本片需**擴充聚合保留此 2 欄**，非「讀現有 rows」。

詳見 PRD Implementation Decisions「micro-fields」M-sp。

## Acceptance criteria

- [ ] 擴充 `savant_rolling` 聚合保留 `description` + `release_speed`（pitch-level），不破壞既有 BBE 級輸出
- [ ] CSW% 21d / velo 三窗 delta / K-BB% ladder 各為純函式 + payload 行（CSW 永遠 context 行不進 Sum — 21d<穩定點）
- [ ] 單元測試：CSW 分子聚合 / velo delta 三窗 / K-BB stabilization 框架文字
- [ ] 三 tag 注入 SP payload，受 039 payload_budget 守門

## Blocked by

None - can start immediately

## User stories addressed

- User story 16
- User story 17
