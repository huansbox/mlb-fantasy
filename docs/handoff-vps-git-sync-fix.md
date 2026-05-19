# VPS Git 同步中斷修復計畫（2026-05-19）

## 狀態

✅ **已執行完成（2026-05-19）** — 第一、二階段完成，VPS git 同步恢復。第三階段（預防程式碼）未做，非緊急。

執行結果：
- 第一階段：`mlb_query.py` 衝突解除 → rebase 成功 → week-9 資料推回（`687fc53`）→ 6 個 b1_baseline fixture 拆 3 commit 推回（`eecb054`/`79d58d1`/`3da9fc0`）
- 第二階段：`roster_sync.py --init` 補回遺漏異動（drop Sean Burke / add Joey Cantillo + Andre Pallante），`roster_config.json` 已提交推送（`fd8199d`）
- 驗證：`git status` 乾淨且與 origin 同步、`mlb_query.py` 已追蹤、roster 正確、cron 已自然解除阻塞（下次 04:30 UTC fa_scan 會更新 waiver-log）
- 執行時 UTC 02:46，距下個動 git 的 cron 逾 1 小時，緩衝充足故未停 cron（第零階段略過）

## 問題摘要

2026-05-16 起 Telegram 每天收到：

```
fa_scan pre-edit pull --rebase failed — skipping waiver-log update. Needs manual fix.
```

VPS 上所有走 git 同步的 cron 腳本全部中斷。

## 根本原因

VPS 上 `daily-advisor/mlb_query.py` 是一個 **untracked 檔案**，而 origin/master 已把**同一路徑**納入版控（commit `12ba860 feat(mlb-query): add gamelog_with_qs + opponent_context helpers`，issue 010）。

每次 cron 腳本執行 `git pull --rebase origin master`，git 在 checkout 上游時偵測到會覆蓋這個未追蹤檔案，於是中止：

```
error: The following untracked working tree files would be overwritten by merge:
	daily-advisor/mlb_query.py
Please move or remove them before you merge.
Aborting
```

`fa_scan.py` 的 `_sync_waiver_log_before_edit()` 捕捉到 `CalledProcessError` → `git rebase --abort` → 發 Telegram 警告 → 跳過 waiver-log 更新。

### 為什麼會出現未追蹤檔

`mlb_query.py` 在 issue 010（`/stream-sp-deep` helper）開發期間，先以未追蹤狀態被放上 VPS（scp 或本地建立）。之後 commit `12ba860` 從開發機把**內容完全相同**的檔案 commit 進 git。`12ba860` 推上 origin 的那一刻（約 5/15-5/16），VPS 所有 git 同步開始失敗 —— 與 Telegram 5/16 起報錯時間吻合。

### 關鍵驗證

```
VPS 工作區 mlb_query.py hash = e6fc5b8c2a82c35c373e1a3aa3aeb4dd67b525f7
origin/master 追蹤 blob       = e6fc5b8c2a82c35c373e1a3aa3aeb4dd67b525f7
```

**位元組完全相同** → 移除 VPS 未追蹤檔零內容損失，pull 後會帶回被追蹤版本。

## 影響範圍（5/16 起全斷）

所有走 `_sync_*_before_edit` 前置 pull 的 cron 腳本都中招：

| 腳本 | 後果 |
|------|------|
| `fa_scan.py` | waiver-log 自動更新跳過（5/16-5/19 未更新） |
| `roster_sync.py` | roster 同步跳過 — 5/16 後若有 add/drop，`roster_config.json` 未反映；log 出現 `could not detach HEAD` |
| `cron_capture_payload.sh` | b1_baseline fixture（5/16/17/18 共 6 檔）已產出但卡在 VPS untracked，未推上 git |
| `weekly_review.py` | week-9 資料已本地 commit（`795cbed`）但推不出去 |

### 當前 VPS git 狀態（修復前快照）

- 分支：`master`，與 origin **分歧 1/11**（VPS 領先 1 commit，落後 11 commit）
- VPS 本地領先 commit：`795cbed data: weekly review data for week 9`（新增 `daily-advisor/weekly-data/week-9.json`，1685 行）
- merge base：`fae0d64`
- origin 領先的 11 個 commit（`fae0d64..origin/master`）：
  ```
  761fa41 docs(player-eval): split SP path into docs/player-eval-sp.md
  c3e6b81 docs(stream-sp-pending): 5/17 deep eval ...
  2fc8d58 docs(stream-sp-pending): expire ET 5/15 ...
  8c09d05 fix(stream-sp-deep): replace arbitrary numeric thresholds ...
  73be312 docs(waiver-log): add Crawford watch ...
  18b3b9c docs(claude-md): add mlb_query.py + test_mlb_query.py to file index
  8522762 docs(stream-sp-deep): clarify et_date ...
  7b52e51 refactor(stream-sp-deep): replace inline heredoc with mlb_query helpers
  12ba860 feat(mlb-query): add gamelog_with_qs + opponent_context helpers
  fd235e1 chore(stream-sp): pending 5/16 14:00 deep refresh ...
  d857cfd chore(stream-sp): update pending ...
  ```
- 工作區未追蹤檔（7 個）：
  ```
  daily-advisor/mlb_query.py                                  ← 衝突源
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-16_fa_classify.json
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-16_sp_step1.json
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-17_fa_classify.json
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-17_sp_step1.json
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-18_fa_classify.json
  daily-advisor/_tools/fixtures/b1_baseline/2026-05-18_sp_step1.json
  ```
- 無進行中的 rebase（`rebase --abort` 已清乾淨），`roster_config.json` / `waiver-log.md` 無本地修改

## 修復計畫

所有指令在 VPS（`/opt/mlb-fantasy`）執行，本機透過 SSH 觸發：

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy && <command>"
```

### 第零階段 — 規避 cron 競態（review 補充）

修復跨多個 SSH 步驟，期間若 cron 觸發（UTC 04:30 capture / 07:10 roster_sync / 07:15 snapshot 等）會與手動操作搶 git。**修復前先暫時停用 cron**：

- 選 cron 空窗執行；或
- `git`-不影響地暫時把 `/etc/cron.d/daily-advisor` 相關行註解掉，修復完成後復原。
- 注意 `/etc/cron.d/` 內 4 個 `.bak` 檔不會被執行（run-parts 忽略含點檔名），無須處理。

### 第一階段 — 恢復 VPS git 同步

1. **移除衝突源**
   ```
   mv daily-advisor/mlb_query.py /tmp/mlb_query.py.bak
   ```
   內容與 origin 完全一致（雜湊已驗證），用 `mv` 到 `/tmp` 而非 `rm` —— 保守起見保留備份，第一階段全部成功後再刪。

2. **Rebase 取得 origin 11 個 commit**
   ```
   git pull --rebase origin master
   ```
   預期無衝突：
   - 移除 `mlb_query.py` 後，剩餘 6 個 untracked 檔全在 `b1_baseline/` 目錄，origin 11 個 commit **不追蹤此目錄**（已驗證）→ 不擋 rebase。
   - 本地 `795cbed` 是純新增 `week-9.json`，origin 11 個 commit **未觸碰此檔**（已驗證 `git log fae0d64..origin/master -- .../week-9.json` 為空）→ rebase 乾淨。

3. **推回 week-9 資料**
   ```
   git push origin master
   ```

4. **保存 b1_baseline fixture（6 檔，拆 3 個 daily commit）**
   對齊 `cron_capture_payload.sh` 既有慣例 `chore(b1-baseline): capture fixture <date>`，按日期各 commit 一次：
   ```
   git add daily-advisor/_tools/fixtures/b1_baseline/2026-05-16_*.json
   git commit -m "chore(b1-baseline): capture fixture 2026-05-16"
   git add daily-advisor/_tools/fixtures/b1_baseline/2026-05-17_*.json
   git commit -m "chore(b1-baseline): capture fixture 2026-05-17"
   git add daily-advisor/_tools/fixtures/b1_baseline/2026-05-18_*.json
   git commit -m "chore(b1-baseline): capture fixture 2026-05-18"
   git pull --rebase origin master   ← push 前必做，防 cron 競態拒絕 push
   git push origin master
   ```
   這些是 issue 008 SP B1 baseline 素材，需保留。

5. **確認備份可刪**
   第一階段全部成功後 `rm /tmp/mlb_query.py.bak`。

### 第二階段 — 修復遺漏的同步（依賴第一階段已完成）

> `roster_sync.py` 開頭自帶 `pull --rebase`，第一階段未完成則此階段一樣會失敗退出。

6. **先 dry-run 確認 diff**
   ```
   cd /opt/mlb-fantasy/daily-advisor && python3 roster_sync.py --init --dry-run
   ```
   印出 added/dropped diff 但不寫檔。人眼確認 5/16-5/19 遺漏的 add/drop 合理。

7. **正式跑 --init 補回異動**
   ```
   python3 roster_sync.py --init
   ```
   `--init` 不靠 watermark、全量 name-matching diff，能自癒遺漏的 add/drop。
   **注意（review 修正）**：`--init` 模式（`run_init`）**不會自動 git commit/push** —— 它只 `save_config` + `write_last_sync`。跑完需手動提交：
   ```
   cd /opt/mlb-fantasy && git pull --rebase origin master && \
     git add daily-advisor/roster_config.json && \
     git commit -m "roster: sync missed transactions (5/16-5/19 sync break recovery)" && \
     git push origin master
   ```
   另注意 `--init` 會 backfill 所有現有球員的 `prior_stats` / `yahoo_player_key` / `team` / `positions`，`roster_config.json` 的 diff 範圍可能比「只補 add/drop」更大 —— 屬資料更新，非異常。

8. **手動觸發一次 fa_scan**（可選，或等隔日 cron）
   讓 waiver-log 回到最新狀態。

9. **復原第零階段停用的 cron**

### 第三階段 — 預防再發（另開 branch，非緊急）

根因是「VPS 出現未追蹤檔 → 之後同路徑被別處 commit」。`_sync_*_before_edit` 目前只 abort + 報警，不自癒。

**程式碼層**（`fix/sync-untracked-collision` branch）：
- 把碰撞解析寫成**單一共用 helper**（`daily-advisor/_tools/resolve_untracked_collision`，python 或 shell），讓 `fa_scan.py` / `roster_sync.py` / `cron_capture_payload.sh`（bash）三者共用，避免三份實作。
- helper 邏輯：pull 失敗且 stderr 含 `untracked working tree files would be overwritten` 時，解析出**全部**衝突檔清單，逐檔比對 `git hash-object <file>` vs 上游 blob（比對 ref 用 `FETCH_HEAD`，因 rebase 失敗時 `origin/master` 是否已更新視 fetch/rebase 拆分方式而定，`FETCH_HEAD` 較確定）：
  - **全部**衝突檔雜湊都相同 → 才整批 `rm` 後重試一次 pull
  - **任一**檔雜湊不同 → 整批不動，維持現行 abort + 報警
  - 理由：逐檔 rm 會出現「刪了一半、剩下不同的檔仍擋 pull」的中間狀態 → 必須全有全無。
- 重試一次即可；重試後仍失敗維持 abort + 報警。

**流程層**：
- 往後 VPS 不應出現未追蹤的腳本檔。新腳本一律「先 commit 進 git → VPS `git pull` 同步」，不 scp 散檔上 VPS。

## 風險與回滾

- 第一階段步驟 1：用 `mv` 到 `/tmp` 而非 `rm`，雜湊已驗證相同，且保留備份，零風險。
- 步驟 2 rebase 若意外衝突：`git rebase --abort` 即回到當前狀態，不會丟資料（`795cbed` 仍在 reflog；`git reflog` 確認 `795cbed HEAD@{0}`，必要時 `git reset --hard 795cbed` 復原）。
- 第二階段 `roster_sync.py --init`：`--dry-run` 先驗證 diff；正式跑只更新 `roster_config.json`，不破壞既有資料（diff 範圍含 prior_stats backfill，屬正常）。
- 修復期間 cron 已於第零階段停用，無競態。

## review 結論（2026-05-19）

agent 用 VPS 唯讀指令驗證根因分析**全部屬實**，並修正計畫 4 處（已併入上方）：

1. 步驟 4 commit 後、push 前補 `git pull --rebase` —— 防 cron 競態拒絕 push。
2. 步驟 7 修正：`roster_sync.py --init` **不會自動 commit/push**，需手動提交 `roster_config.json`。
3. 步驟 6 新增 `--init --dry-run` 先行人眼確認 diff。
4. 新增第零階段：修復期間規避 cron。

第三階段預防方案修正：多衝突檔改「全部雜湊相同才整批 rm」（非逐檔），比對 ref 指定 `FETCH_HEAD`。

「待 review 的問題」三題回答：
- Q1：fixture 拆 3 個 daily commit，對齊 `cron_capture_payload.sh` 慣例與「一天一 commit」可追溯性 → 已採納入步驟 4。
- Q2：不需另查 Yahoo，`--init` 本身就是「抓 Yahoo 即時 roster vs config diff」；改用 `--dry-run` 先驗證即可 → 已採納入步驟 6。
- Q3：重試一次足夠；多衝突檔必須全有全無，不可逐檔 rm → 已採納入第三階段。
