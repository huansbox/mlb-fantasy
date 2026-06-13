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

- [x] **擴充 `savant_rolling` 聚合保留 pitch-level（merge `ea4b9e3`）**：`_pitch_level_metrics` 逐球遍歷算 CSW%（called+swinging strikes / 總球）+ velo by pitch_type + primary fastball velo，merge 進 pitcher result（batter 不變）。真實 CSV 欄名已對 2025 Savant 驗證（`description`/`release_speed`/`pitch_type` 皆在）。+6 tests。**環境註記**：本機抓 2026 窗回 0 rows（模擬季無真實 Savant 資料），2025 窗正常 — VPS 端視其資料源。
- [ ] CSW% 21d delta vs season / velo 三窗 delta / K-BB% ladder 各為純函式 + payload 行（CSW 永遠 context 行不進 Sum）— **計算用聚合已備的 csw_pct/velo_fb**
- [ ] 三 tag 注入 SP payload，受 039 payload_budget 守門 — **併 318b 批**

## Blocked by

None - can start immediately

## User stories addressed

- User story 16
- User story 17
