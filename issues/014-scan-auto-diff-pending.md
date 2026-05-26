## Parent PRD

`issues/prd-stream-sp-optimization.md`

## What to build

`stream_sp_scan.py` 加 `--pending-file PATH` 參數，自動 diff pending file 中的 evaluations vs 當天 scan 結果，省下 LLM 補查模式手動掃 schedule 變動 / 失效 SP 的 friction。

### 實作層

1. **新 module `daily-advisor/pending_parser.py`**：解析 `daily-advisor/stream-sp-pending.md` 的 H2 section 結構
   - 對每個 `## ET YYYY-MM-DD` H2 section 抽：ET 日期 / TBD 場次 list / `### 已評估` 表格 row（SP 名 / 隊 / 對手 / verdict）
   - 純 pure-function，輸入 markdown 字串、輸出 dict

2. **`stream_sp_scan.py` glue**：接 `--pending-file PATH` 後讀檔，對每個 ET 日期 比對 candidates / owned_by_me / owned_by_others 與 pending evaluations，產 diff
   - emit 結構：
     ```json
     {
       "pending_diff": {
         "2026-05-26": {
           "still_starting": ["Jason Alexander", "Kyle Freeland"],
           "lost_to_others": ["Sean Burke"],
           "replaced": [{"old": "Griffin Canning", "new": "Randy Vásquez", "team": "SD"}],
           "no_longer_scheduled": []
         }
       }
     }
     ```

3. **`.claude/commands/stream-sp.md` Step 2 + Step 7 補查模式**：
   - Step 2 範例命令加 `--pending-file daily-advisor/stream-sp-pending.md`
   - Step 7 補查模式邏輯改：LLM 從 pending_diff 直接讀失效 SP（不再手動 cross-check candidates / owned_by_others）

## Acceptance criteria

### Parser 層
- [ ] `daily-advisor/pending_parser.py` 新檔 + TDD tests（~10-12 cases 覆蓋）：
  - [ ] H2 section parser（空檔 / 多 ET 日 / H2 標題 malformed）
  - [ ] TBD 場次 list parser（單行 / 多行 / 空列表 `_（無 TBD）_`）
  - [ ] evaluations 表格 row parser（含 markdown `|` escape / 缺欄）
  - [ ] 整檔 fixture 回歸（讀現有 `stream-sp-pending.md`）
  - [ ] **Corrupt schema graceful degradation**：parser 對未識別 line（free-form 備註 / 缺欄 row / malformed markdown）安全 skip 不 raise
  - [ ] **Empty file**：空檔回 `{}`（不是 raise）

### Scan glue 層
- [ ] `stream_sp_scan.py` 加 `--pending-file` 參數 + glue code + tests（~6 cases）：
  - [ ] still_starting 分類（pending SP 在 candidates 內）
  - [ ] lost_to_others 分類（pending SP 在 owned_by_others 內）
  - [ ] replaced 分類（pending SP 那場 schedule 換 starter）
  - [ ] no_longer_scheduled 分類（pending SP 那場已不在當天 schedule）
  - [ ] **無 `--pending-file` 參數時 fallback**：scan 仍跑得起來，JSON 不含 `pending_diff` key（不是 emit empty dict）
  - [ ] **檔案路徑錯時 graceful**：log warning + fallback 無 `pending_diff`（不 raise）
- [ ] scan 輸出 JSON 加 `pending_diff` key（每個 ET 日下含 4 個 list）
- [ ] **同隊不同名同姓 SP edge case**：用 `(SP 名 + team)` 作 key 比對，不只 SP 名

### Skill 層
- [ ] `.claude/commands/stream-sp.md` Step 2 範例命令加 `--pending-file`
- [ ] `.claude/commands/stream-sp.md` Step 7 補查模式邏輯改成從 pending_diff 讀（≤30 字補充說明）
- [ ] **Backward compat**：scan JSON 缺 `pending_diff` key 時 skill Step 7 fallback 舊邏輯（手動掃 candidates / owned_by_others），不 break

### E2E sanity check
- [ ] 跑一次補查模式 e2e 驗證 5/26 Canning→Vásquez / Burke 認領被自動偵測，預期 `pending_diff` JSON 內容：
  ```json
  {
    "2026-05-26": {
      "still_starting": ["Jason Alexander", "Kyle Freeland"],
      "lost_to_others": ["Sean Burke"],
      "replaced": [{"old": "Griffin Canning", "new": "Randy Vásquez", "team": "SD"}],
      "no_longer_scheduled": []
    }
  }
  ```
- [ ] CLAUDE.md「檔案索引」加 `pending_parser.py` 條目

## Blocked by

None - can start immediately.

## User stories addressed

- **US2** — schedule change / 失效 SP 手動偵測 friction
