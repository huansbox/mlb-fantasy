## Parent PRD

`issues/prd-stream-sp-optimization.md`

## What to build

`mlb_query.py` 加 `deep_batch(...)` orchestrator 把 N 位 SP 深評從「2N 個 SSH 並行」壓成「1 個 SSH 批次」+ emit 比較表 raw JSON 讓 deep skill 不再手填表格。

Stage 2 優先 — latency 優化，不解評價痛點；Stage 1 (012-015) 完成後再做。

### 實作層

1. **`daily-advisor/mlb_query.py` 加 CLI mode**：
   ```bash
   python3 mlb_query.py deep --players ID1,ID2,... --et-dates D1,D2,...
   ```
   - 參數：`--players` 多 SP ID（逗號分隔）+ `--et-dates` 多 ET 日期（與 players 一一對應）
   - 一次拉所有 SP 的 game_log + opponent_context（reuse existing helpers）
   - emit 結構：
     ```json
     {
       "by_player": {
         "686790": {"game_log": [...], "opponent_context": {...}, "sp_meta": {"name": "Trevor McDonald", "team": "SF", "hand": "R"}},
         "605488": {...}
       },
       "comparison_table": {
         "headers": ["7d OPS", "30d→7d Δ", "vs hand OPS", "近 6 場 ERA", "Floor risk hint", "Sum26", "雙年 prior"],
         "rows": [
           {"sp": "Trevor McDonald vs AZ", "values": [".769", "+.067", ".686 (R)", "4.76", "中-高", "40", "40/46"]},
           {"sp": "Jeffrey Springs vs SEA", "values": [".700", "+.025", ".592 (L)", "3.94", "中", "25", "25/22"]}
         ]
       }
     }
     ```

2. **`.claude/commands/stream-sp-deep.md` 改動**：
   - Step 1-2 改成單一批次命令（取代並行 N 次 SSH）
   - Step 5 §4 比較表改成讀 `comparison_table` raw JSON（LLM 只填 verdict + 排序文字）

3. **deep_batch 內部風格約束**：
   - `deep_batch(players, et_dates)` 內部 **loop call 既有 helpers** (`gamelog_with_qs` + `opponent_context`)，不重寫 fetch 邏輯
   - 與 mlb_query.py 既有 single-ID helpers 風格分層：外觀 batch（list 輸入）/ 內部 single（loop helpers）

## Acceptance criteria

### Orchestrator + CLI
- [ ] `daily-advisor/mlb_query.py` 加 `deep_batch(players, et_dates)` orchestrator（reuse `gamelog_with_qs` + `opponent_context`，**內部 loop call 不重寫 fetch 邏輯**）
- [ ] tests（~8-10 cases）：
  - [ ] batch 注入 fetcher mock（不依賴外部 API）
  - [ ] comparison_table headers 順序固定
  - [ ] comparison_table rows 對應 players × et_dates 一一映射
  - [ ] **順序保證**：players 順序 = comparison_table.rows 順序（顯式 assertion）
  - [ ] 不同 et_dates（每位 SP 不同日）正確處理
  - [ ] 空 players list 退回空 JSON
  - [ ] **SP MLB ID 找不到 → raise**（決策：raise 而非 skip，避免部分結果靜默丟失）
  - [ ] **Partial failure**：N 位 SP 中 1 位 game_log API 失敗 → 該 SP 在 `by_player` 顯式 emit `{"error": "..."}`，其他 SP 結果正常回傳（不整批 abort）
  - [ ] **per-SP timeout 隔離**：單 SP fetch ≥30 秒 → 標 timeout，繼續下一位（不拖全批）
- [ ] CLI 模式 `python3 mlb_query.py deep --players ... --et-dates ...` 可跑（補 argparse + main 入口）

### Skill 層
- [ ] `.claude/commands/stream-sp-deep.md` Step 1-2 改成單一批次命令（範例 ssh 改為一行）
- [ ] `.claude/commands/stream-sp-deep.md` Step 5 §4 比較表改成讀 comparison_table raw JSON（LLM 不再手填 7 維度）

### E2E sanity check
- [ ] e2e 驗證 4 位 SP 批次跑 < 30 秒（vs 目前 4-8 SSH 並行 ~60-80 秒，本 session 經驗）
- [ ] **與 011 e2e parity 比對**：batch 結果（4 位 SP）vs 個別跑 `gamelog_with_qs` + `opponent_context` 4 次，game_log 每場欄位逐 byte 相符 + opponent_context 各窗口 OPS 到小數第 3 位相符
- [ ] CLAUDE.md「檔案索引」更新 mlb_query.py 條目（新增 `deep` CLI mode 說明）

## Blocked by

None - can start immediately（可平行 Stage 1，但建議照 PRD 順序排在最後做：015 → 012 → 013 → 014 → 016，避免 016 改 stream-sp-deep.md Step 1-2 範例命令後讓 013/015 改的 prompt 指引變 stale）

## User stories addressed

- **US6** — Deep eval N 位 = 2N 個 SSH + 比較表 LLM 手填 latency
