## Parent PRD

`issues/prd-stream-sp-optimization.md`

## What to build

`stream_sp_scan.py` candidates JSON 加 vs hand season OPS 欄。把目前要 `/stream-sp-deep` 才看到的 vs hand split 訊號前移到 scan 階段，並對應改 SOP 強弱表。

### 實作層

1. **scan candidates schema 擴張**：每個 SP 加：
   ```json
   "vs_hand_2026": {
     "pa": 1356,
     "ops": ".686",
     "k_pct": 21.8,
     "bb_pct": 8.2,
     "hand": "R",
     "low_pa_fallback": false
   }
   ```
   - 對手 = SP team 那場的對手；hand = SP 慣用手（從 MLB API 抓）
   - **Sample gate**：對手隊 vs hand PA <400 時改 emit 全 OPS（fallback to season OPS）+ `"low_pa_fallback": true` 旗標

2. **新 fetcher / glue**：reuse `mlb_query.opponent_context` 內 vs_hand 抓取邏輯（具體：reuse `_default_split_fetch` line 97-117 取 `statSplits` API 的 vr/vl split），但結構不同（per candidate 而非 per opponent team）
   - **PA <400 sample gate 語義釐清**：PA 指**對手隊全季 vs SP 慣用手累積 PA**（即 `statSplits.stats.plateAppearances`）。對手隊整季 vs LHP/RHP 通常 ≥1000 PA，<400 主要發生在 5 月初季初期樣本不足
   - **MLB API 失敗 fallback**：若 statSplits 端點 timeout / 5xx → emit `vs_hand_2026: null` + log warning（不 raise，scan 仍跑完）
   - **SP 慣用手未知（雙手投 / API 缺欄）**：emit `"hand": null` + fallback 全 OPS + `low_pa_fallback: true`

3. **SOP 改動**：
   - `.claude/commands/stream-sp-deep.md` Step 1b 強弱表：改用 vs hand OPS 為主錨（≤.680 弱 / .680-.720 中 / .720-.770 中強 / ≥.770 強）；PA<400 退回全 OPS sample gate（保留現表作 fallback）
   - `.claude/commands/stream-sp.md` Step 7 FA 真先發候選表：加「對手 vs SP hand OPS」欄

## Acceptance criteria

- [ ] `stream_sp_scan.py` 加 vs_hand fetcher + glue code（emit 對手 vs SP hand 的 PA/OPS/K%/BB%）+ tests
- [ ] tests 含（~6-8 cases）：
  - [ ] normal path (PA ≥400) 取 vs hand
  - [ ] PA <400 sample gate fallback（emit 全 OPS + low_pa_fallback=true）
  - [ ] SP 慣用手 resolution（左投 / 右投 / 雙手投或未知 → null + fallback）
  - [ ] MLB API statSplits 失敗 fallback（emit null + log warning）
  - [ ] fetcher mock 注入（無外部 API 依賴）
  - [ ] PA 邊界 case（PA=399 fallback / PA=400 取 vs hand）
- [ ] candidates JSON schema 含 `vs_hand_2026` 欄 + `low_pa_fallback` 旗標
- [ ] `.claude/commands/stream-sp-deep.md` Step 1b 強弱表改 vs hand OPS（保留全 OPS 作 PA<400 fallback 提示）
- [ ] `.claude/commands/stream-sp.md` Step 7 主表加 vs hand OPS 欄（位置：在「對手 14d OPS / tier」欄旁邊）
- [ ] CLAUDE.md「檔案索引」更新 stream_sp_scan.py 條目（新增 vs_hand_2026 欄位說明）
- [ ] 跑一次 e2e 驗證至少 4 個 SP 有 vs_hand 數據（含至少 1 RHP + 1 LHP 覆蓋兩 hand）
- [ ] sanity check 1：跑出來的 vs hand OPS 與本 session 觀察 Springs SEA vs LHP .592 / McDonald AZ vs RHP .686 / Cameron NYY vs LHP .788 對齊
- [ ] sanity check 2：跑 5/26 + 5/27 兩天候選統計 `low_pa_fallback` 觸發率 ≤30%（驗證 PA<400 門檻不會讓大多數 SP 走 fallback；若 >30% → 門檻過嚴，調低至 PA≥300）

## Blocked by

None - can start immediately.

## User stories addressed

- **US1** — vs hand OPS 訊號要 deep eval 才看到
