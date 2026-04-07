# FA Scan Batch 3: Deployment & Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy fa_scan.py to VPS, update cron schedule, clean up deprecated files (fa_watch.py, prompt_fa_watch.txt, weekly_scan.py references), update CLAUDE.md and skills.

**Architecture:** No new code — this batch is deployment, documentation, and cleanup. All logic changes were done in Batch 1-2.

**Tech Stack:** VPS cron, git, SSH

**Branch:** `chore/fa-scan-deployment`

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `CLAUDE.md` | Modify | Update system architecture, file index, SOP schedule, mark TODOs |
| `.claude/commands/waiver-scan.md` | Modify | Update references from weekly_scan/fa_watch to fa_scan |
| `daily-advisor/fa_watch.py` | **Delete** | Fully replaced by fa_scan.py |
| `daily-advisor/prompt_fa_watch.txt` | **Delete** | Replaced by prompt_fa_scan_*.txt |
| `daily-advisor/weekly_scan.py` | Verify deleted | Should already be deleted in Batch 2 |

---

### Task 1: Delete deprecated files

**Files:**
- Delete: `daily-advisor/fa_watch.py`
- Delete: `daily-advisor/prompt_fa_watch.txt`

- [ ] **Step 1: Verify weekly_scan.py already deleted (Batch 2)**

```bash
ls daily-advisor/weekly_scan.py 2>/dev/null && echo "ERROR: still exists" || echo "OK: already deleted"
```

- [ ] **Step 2: Verify no imports of fa_watch remain**

```bash
cd D:/mywork/_mynote/mlb-fantasy && grep -r "from fa_watch import\|import fa_watch" daily-advisor/*.py
```

Expected: No matches (fa_scan.py should have absorbed all functions, not import fa_watch).

- [ ] **Step 3: Delete fa_watch.py and prompt_fa_watch.txt**

```bash
git rm daily-advisor/fa_watch.py daily-advisor/prompt_fa_watch.txt
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete deprecated fa_watch.py and prompt_fa_watch.txt"
```

---

### Task 2: Update /waiver-scan skill

**Files:**
- Modify: `.claude/commands/waiver-scan.md`

The manual /waiver-scan skill references weekly_scan and fa_watch. Update to reference fa_scan.

- [ ] **Step 1: Read current skill file**

Read `.claude/commands/waiver-scan.md` and find all references to `weekly_scan`, `fa_watch`, `weekly scan`, `FA Watch`.

- [ ] **Step 2: Update references**

In the skill description (line 14):
```
> 自動化的 Weekly Scan（週一 19:30）+ Daily FA Watch（每日 07:00）已覆蓋基本 FA 監控，本 skill 用於補充 WebSearch 新聞面和深度評估。
```

Replace with:
```
> 自動化的 FA Scan（每日 12:30）已覆蓋基本 FA 監控，本 skill 用於補充 WebSearch 新聞面和深度評估。
```

Search for any other `weekly_scan` or `fa_watch` references and update accordingly.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/waiver-scan.md
git commit -m "docs(waiver-scan skill): update references from weekly_scan/fa_watch to fa_scan"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Multiple sections need updating. Read the full file first, then make all changes.

- [ ] **Step 1: Update 陣容風險 section (~line 90)**

Replace:
```
由自動化腳本從 `roster_config.json` + 即時數據動態計算（見 `fa_watch.py` / `weekly_scan.py` 輸出）。
```

With:
```
由自動化腳本從 `roster_config.json` + 即時數據動態計算（見 `fa_scan.py` 輸出）。
```

- [ ] **Step 2: Update 賽季運營 SOP — 每日 schedule**

Find the daily schedule table and update:
- Remove FA Watch 07:00 row
- Add fa_scan 12:30 row

The table should become:

```markdown
| 時間 (TW) | 做什麼 | 說明 |
|-----------|--------|------|
| 12:30 | FA Scan 報告產出 | 自動推送（Batter + SP） |
| 14:15 | 收速報 → 設隔日 lineup → 睡覺 | 自動推送 |
| 05:00 | 最終報產出 | 自動推送（睡眠中） |
| 07:00 | 起床看最終報 + FA Scan → 微調（如需要） | 兩份一起看 |
```

Note: The exact current table content may differ — read the file and adjust accordingly.

- [ ] **Step 3: Update 每週 schedule**

Update the Monday workflow to reflect:
- fa_scan --rp runs on Monday (TW 12:30 with daily scan, or separate)
- weekly_review reads fa_scan results

- [ ] **Step 4: Update 系統架構 diagram**

Replace references to `fa_watch.py` / `weekly_scan.py` with `fa_scan.py` in the architecture block:

```
fa_scan.py（FA 市場分析唯一入口）
  ├─ 每日：Batter + SP 兩階段 Claude（Pass 1 挑最弱 + Pass 2 比較）
  ├─ 週一：--rp 模式（RP 獨立掃描）
  ├─ 每日 TW 15:15：--snapshot-only（%owned 快照 + watchlist 清理）
  ├─ 被讀取：weekly_review.py（scan_summary）
  └─ 被更新：waiver-log.md（觀察中球員追蹤）
```

- [ ] **Step 5: Update 檔案索引 table**

Remove `fa_watch.py` row, add/update `fa_scan.py` row, remove `weekly_scan.py` row.

- [ ] **Step 6: Mark fa_watch / weekly_scan TODOs as cancelled**

Find these TODO sections and mark them:

The `### fa_watch 對齊調整` section — replace with:
```markdown
### ~~fa_watch 對齊調整~~ ❌ 取消（fa_watch 已被 fa_scan 取代，2026-04-07）
```

The `### weekly_scan 品質優化` section — replace relevant items:
- `分批送 Claude` → done (fa_scan uses separate Pass 1/2 per batter/SP)
- `RP SV+H ≥ 2 門檻動態化` → cancelled (biweekly rolling window, no need)

- [ ] **Step 7: Update roster_config.json 被讀取 list (~line 295)**

Replace `fa_watch.py / weekly_scan.py` with `fa_scan.py`.

- [ ] **Step 8: Update waiver-log 被讀取 list (~line 300)**

Replace `fa_watch.py / weekly_scan.py` with `fa_scan.py`.

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE.md): update for fa_scan.py — architecture, SOP, file index, TODOs"
```

---

### Task 4: Update VPS cron

**Files:** VPS `/etc/cron.d/daily-advisor`

- [ ] **Step 1: Read current VPS cron**

```bash
ssh root@107.175.30.172 'cat /etc/cron.d/daily-advisor'
```

- [ ] **Step 2: Update cron entries**

Changes needed:
1. **Remove** fa_watch TW 07:00 (UTC 23:00) entry
2. **Replace** weekly_scan TW 12:30 (UTC 04:30, Monday only) with fa_scan TW 12:30 (UTC 04:30, **daily**)
3. **Add** fa_scan --rp TW 12:45 (UTC 04:45, Monday only) — runs after daily scan
4. **Replace** fa_watch --snapshot-only TW 15:15 (UTC 07:15) with fa_scan --snapshot-only

New entries should be:

```
# FA Scan — 台灣 12:30 每天 = UTC 04:30 Daily
30 4 * * * root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/fa_scan.py >> /var/log/fa-scan.log 2>&1"

# FA Scan RP — 台灣 12:45 每週一 = UTC 04:45 Monday
45 4 * * 1 root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/fa_scan.py --rp >> /var/log/fa-scan-rp.log 2>&1"

# FA Scan Snapshot — 台灣 15:15 每天 = UTC 07:15 (waiver 處理後)
15 7 * * * root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/fa_scan.py --snapshot-only >> /var/log/fa-snapshot.log 2>&1"
```

Remove these old entries:
- `# Daily FA Watch` (TW 07:00)
- `# FA Snapshot` that references `fa_watch.py`
- `# Weekly Deep Scan` that references `weekly_scan.py`

Keep all other entries unchanged (daily_advisor, roster_sync, weekly_review).

- [ ] **Step 3: Verify cron syntax**

```bash
ssh root@107.175.30.172 'grep -c "fa_scan\|fa_watch\|weekly_scan" /etc/cron.d/daily-advisor'
```

Expected: 3 lines with fa_scan, 0 with fa_watch, 0 with weekly_scan.

- [ ] **Step 4: Pull latest code to VPS**

```bash
ssh root@107.175.30.172 'cd /opt/mlb-fantasy && git pull origin master'
```

- [ ] **Step 5: Verify fa_scan.py runs on VPS**

```bash
ssh root@107.175.30.172 'cd /opt/mlb-fantasy && python3 daily-advisor/fa_scan.py --dry-run 2>&1 | head -10'
```

Expected: Layer 1-2 output, no import errors.

- [ ] **Step 6: No git commit needed (VPS config only)**

---

### Task 5: Update memory file

**Files:**
- Modify: `C:\Users\linshuhuan\.claude\projects\D--mywork--mynote-mlb-fantasy\memory\reference_vps.md`

- [ ] **Step 1: Update cron table in memory**

Replace the fa_watch and weekly_scan rows with fa_scan entries:

| Job | UTC | TW | Log |
|-----|-----|-----|-----|
| FA Scan (daily) | 04:30 | 12:30 | `/var/log/fa-scan.log` |
| FA Scan RP (Mon) | 04:45 | 12:45 | `/var/log/fa-scan-rp.log` |
| Weekly Review Prep | Mon 05:00 | Mon 13:00 | `/var/log/weekly-review.log` |
| FA Snapshot | 07:15 | 15:15 | `/var/log/fa-snapshot.log` |

Remove FA Watch and Weekly Scan rows.

- [ ] **Step 2: No git commit (memory is outside repo)**

---

## Verification Checklist

After all tasks:

- [ ] `fa_watch.py` deleted from repo
- [ ] `prompt_fa_watch.txt` deleted from repo
- [ ] `weekly_scan.py` deleted from repo (Batch 2)
- [ ] No `fa_watch` or `weekly_scan` references in CLAUDE.md (except historical ✅ entries)
- [ ] No `fa_watch` or `weekly_scan` references in VPS cron
- [ ] `/waiver-scan` skill references fa_scan
- [ ] VPS has latest code (`fa_scan.py` exists)
- [ ] `fa_scan.py --dry-run` works on VPS
