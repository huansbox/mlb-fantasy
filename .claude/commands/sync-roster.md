---
name: sync-roster
description: "Fantasy Baseball 手動強制刷新陣容名單 — 立刻叫 VPS 跑一次 roster_sync（poll Yahoo → 更新 roster_config.json → push）再 pull 進本機，把『最多等 15 分 cron + session 開場才 pull』壓成『現在』。用戶說「刷新名單」「現在抓最新 roster」「我剛換人更新一下」「sync roster」「force roster sync」「/sync-roster」時觸發。給自動 pipeline 來不及的少數時刻：(1) 剛在 Yahoo 做完異動想立刻評估新人 (2) session 開很久了中途做了換人。不用於評估球員（那是 /player-eval）、不用於 FA 掃描（那是 /waiver-scan）。平常不需要它 — roster 新鮮度由 VPS cron（每 15 分）+ SessionStart hook 自動維護。"
---

# 手動刷新陣容名單（roster freshness 逃生口）

把「VPS 每 15 分 poll + 本機開場才 pull」這兩個等待點手動打破，立刻拿到最新名單。

> **背景**：名單唯一來源 `daily-advisor/roster_config.json` 由 VPS `roster_sync.py`（cron `7,22,37,52 * * * *`）維護，本機靠 SessionStart hook `git pull` 拿到。詳見 `CLAUDE.md`「Roster 新鮮度 pipeline」段。本指令 = 不等 cron、不等下次開 session，立刻同步。
> **不碰 Yahoo 本機**：所有 Yahoo 存取都在 VPS（token 只在 VPS）。本指令本機只做 git pull。

## Step 1：叫 VPS 立刻跑一次 roster_sync

```bash
bash bin/vps-run.sh --no-retry "cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py 2>&1 | tail -20"
```

- **`--no-retry`**：side-effecting（會 git commit/push），timeout 重試可能 double-run，所以不重試。
- VPS 上 roster_sync 自己會 `git pull` → poll Yahoo transactions → 有 add/drop 才更新 config + commit + push origin；無新異動則印「No new transactions. Done.」直接結束（不 commit）。
- **讀輸出判斷**：
  - 看到 `Roster changes: +[...] -[...]` + `Config updated.` → 有異動且已 push origin，進 Step 2 拉下來。
  - 看到 `No new transactions. Done.` → 名單沒變，本機已是最新，**仍跑 Step 2 一次**（確保本機跟上 origin 上其他 cron 的 commit）。
  - 看到 `roster snapshot not yet reflecting`（Yahoo lag retry）→ 異動剛做、Yahoo 還沒反映到 roster snapshot，**等 1-2 分鐘再跑一次本指令**（下次就抓得到）。
  - SSH timeout / 輸出被截斷 → 別慌，VPS 端可能已 commit+push；直接進 Step 2 用 git 確認到底有沒有 landing。

## Step 2：本機 pull 進來

```bash
git pull --rebase --autostash origin master
```

- `--autostash`：若本機有未 commit 變更，自動 stash → rebase → 還原，不被擋。
- 若 rebase 衝突 → 停手，回報衝突檔，讓用戶決定（不要硬解）。

## Step 3：回報實際變動

- 比對 pull 前後：若有新的 `roster: +X -Y` commit → 回報「名單已更新：+X -Y」+ 該球員守位。
- 若無變動 → 回報「名單無變動，本機已是最新（@ <short hash>，roster_config 最後異動 <相對時間>）」。
- 用 `git log --oneline -3 -- daily-advisor/roster_config.json` 看最近的 roster commit 佐證。

## 不做的事

- 不評估新撿球員值不值得（接著要評 → 用 `/player-eval`）。
- 不設 lineup（名單同步好後，設先發是另一步）。
- 不主動掃 FA 市場（那是 `/waiver-scan`）。
