# Handoff — Roster Freshness Pipeline（2026-05-31）

> 下個 session 接著做：**驗證整合/部署行為**（單元邏輯已測過，剩「真實 fire」要實證）。
> 落地脈絡見 `CLAUDE.md`「執行環境 → Roster 新鮮度 pipeline」段。

## 這是什麼

讓每個本機 session 開場拿到最新 `roster_config.json`，不靠本機 call Yahoo。兩層 + 一個手動逃生口：

| 層 | 機制 | 檔案 |
|---|---|---|
| 第 2 層 Yahoo→origin | VPS `roster_sync.py` cron `7,22,37,52 * * * *`（每 15 分，offset 避 git race）+ 浮水印 bug 修正 | `roster_sync.py`（VPS `/etc/cron.d/daily-advisor`）|
| 第 1 層 origin→本機 | SessionStart hook：fetch → master+乾淨+ff 時 auto `pull --ff-only`，否則只警告 | `hooks/sync-mirror.mjs`（註冊於 `.claude/settings.json`）|
| 逃生口 | `/sync-roster` 手動即時刷新（VPS roster_sync → 本機 pull）| `.claude/commands/sync-roster.md` |

**為何沒有「預測未來 roster」**：FA add 即時生效（Yahoo 端當下就變）→ 同步快就有；waiver TW 15:00 後才定 + 可能失敗 → 不該預測，15:00 後拉結果即知。所以整件事是「同步」不是「預測」。

## 當前狀態（session 結束時）

- **本機 / origin = `dcc1d75`**。**VPS ≥ `c388738`**（pipeline 全部 code + cron 已在；`dcc1d75` 是 local-only command 檔，VPS 不需執行，下班 cron 也會自動 pull）。
- VPS cron 已改 `7,22,37,52`，備份在 `/etc/cron.d/daily-advisor.bak-20260531`。
- Commits：`9e8b26d`(bug fix) → `4eca6bf`(hook) → merge `4520f7e` → `c388738`(cron doc) → `dcc1d75`(/sync-roster)。

## 已驗證（this session）

- ✅ `classify_empty_diff` 8 單測 + 537 全套 pass。
- ✅ VPS `roster_sync.py --dry-run` + 真實 run 乾淨（module import/runtime OK）。
- ✅ **Cron 真在新排程 fire**：log mtime 落在分鐘 `:07`（= offset，舊 `:10` 不可能產生）。
- ✅ **Hook auto-pull**：reset 退 1 commit → source=startup → 真的 `pull --ff-only` 拉回。
- ✅ **Hook mid-session 安全 gate**：source=resume → 只警告、HEAD 沒被動。
- ✅ Hook warn / behind==0 路徑（feature branch / detached / 最新）。

## 下個 session 要測（核心交付）

### 1. Hook 真的在 SessionStart fire（最重要，無法在上個 session 測）

讀這份 handoff 的**此刻**，session 開場應已注入一行 `[roster-sync]` 狀態。確認：
- [ ] 開場有沒有看到 `✅/⚠️ [roster-sync] ...` 那行？內容是什麼？
  - 看到 `✅ ...已自動同步 N 個 commit` 或 `✅ ...已是最新` → **hook fire 成功**，整條 pipeline 端到端通。
  - 看到 `⚠️ ...origin 領先...` → 也算 fire 成功（只是當下在 feature branch / dirty / 有未推 commit，照設計只警告不 pull，正常）。
  - **完全沒看到** → hook 沒 fire，debug：
    1. `cat .claude/settings.json` 確認 `SessionStart` 區塊在。
    2. `echo '{"source":"startup"}' | node hooks/sync-mirror.mjs` 手動跑，看 script 本身有無錯。
    3. 確認這台機器的 Claude Code 有啟用 hooks（設定 / 版本）。

### 2. `/sync-roster` 端到端實跑（上個 session 只分別驗了 VPS run + 本機 pull 兩半，沒串起來跑）

- [ ] 直接打 `/sync-roster`，觀察：VPS roster_sync 有跑（印 transaction 結果或「No new transactions」）→ 本機 `git pull --rebase --autostash` → 回報變動。
- [ ] 無新異動時應為乾淨 no-op；若剛好你前一刻做了異動，應抓到並回報 +X -Y。
- 預期 ~10-40s（含 1 次 VPS SSH）。

### 3. Cron 持續 fire（抽查，可選）

- [ ] `bash bin/vps-run.sh "stat -c %y /var/log/roster-sync.log && tail -3 /var/log/roster-sync.log"` — mtime 分鐘數應在 {7,22,37,52}。

## 殘留（無法主動測，被動觀察）

- **`classify_empty_diff` 的 `retry` / `advance_alert` production 分支**：只在真實 Yahoo read-after-write lag（做異動後 cron 撞「tx log 已更新、roster snapshot 未更新」窗）才觸發。邏輯已被 8 單測覆蓋。被動觀察：未來某次異動後若 `/var/log/roster-sync.log` 出現 `roster snapshot not yet reflecting ... will retry`（而非誤推進浮水印漏抓），即真實驗證成功。對照舊 bug：5/8 May→Lambert 當年就是被誤推進浮水印漏抓。

## 無關事項（別誤判成本次 regression）

- `tests/test_pending_parser.py::test_real_pending_file_parses_5_26_evaluations` 失敗 = pre-existing fixture drift（`4abca32` 把 `stream-sp-pending.md` 更新到 5/29+5/30、移掉 5/26 段）。屬 /stream-sp 子系統，與 freshness pipeline 無關。要修就把那個脆弱的 hard-coded 5/26 斷言改掉。

## Rollback

整套：`git revert -m 1 4520f7e`（merge commit）+ VPS cron 改回 `10 7 * * *`（或 `cp /etc/cron.d/daily-advisor.bak-20260531 /etc/cron.d/daily-advisor`）。`/sync-roster`（`dcc1d75`）與 cron doc（`c388738`）可獨立 revert，互不依賴。
