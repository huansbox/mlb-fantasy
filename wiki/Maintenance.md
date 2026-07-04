# 維運手冊

## 執行環境

- **所有腳本跑在 VPS**（RackNerd Ubuntu 24.04，`/opt/mlb-fantasy`，Python 3.12 + Claude Code 原生版）。本機只做開發與 git push。
- **Yahoo API token 只存在 VPS**（`daily-advisor/yahoo_token.json`）。兩條鐵律：
  - 不要 scp token 回本機 — `yahoo_query.py` 會自動 refresh，雙邊不同步會讓 VPS token 失效、cron 全斷
  - 不要本機跑會 call Yahoo 的腳本 — 由 PreToolUse hook `hooks/block-local-yahoo.mjs` 機械化攔截
- **本機 → VPS 指令**一律走 timeout + retry wrapper（本機↔VPS 路徑有間歇封包遺失，SSH handshake 偶發卡死 30-40s）：

  ```bash
  bash bin/vps-run.sh '<remote cmd>'            # 純讀，會 retry
  bash bin/vps-run.sh --no-retry '<remote cmd>' # 寫檔 / git，不 retry
  ```

## Cron 排程（VPS）

| 排程 | UTC | 台灣 | 內容 |
|---|---|---|---|
| FA Scan | 04:30 每日 | 12:30 | Batter + SP 並行分析 + waiver-log 自動寫入 |
| Weekly Review 資料 | 05:00 週一 | 13:00 | 覆盤資料準備 |
| Roster Sync | 每 15 分（min 7,22,37,52） | — | poll Yahoo transactions，有異動才更新 config + push |
| Roster Reconcile | — | 11:50 每日 | 全量 roster 對帳防呆網 |
| FA Snapshot | 07:15 每日 | 15:15 | %owned 快照 + watchlist 清理 |
| 日報（平日） | 21:30 Mon–Fri | 05:30 | ET 夜場 lineup + matchup + SP 確認（單一 adaptive 報） |
| 日報（假日） | 14:30 Sat–Sun | 22:30 | ET 日場版本 |
| Savant Rolling | — | 12:00 | 14d rolling 快照供 fa_scan / daily_advisor 讀取 |
| B2 Backtest | 06:00 週日 | 14:00 | `cron_backtest.sh` — SP 決策帳齡 [21, 28) 對帳 → 更新 `docs/sp-decisions-backtest.md` |

報告自動存檔為 GitHub Issue（日報 label `week-N`、FA 掃描 label `fa-scan`）。

## Roster 新鮮度 pipeline（兩層同步）

陣容唯一來源是 `daily-advisor/roster_config.json`，新鮮度分兩層：

1. **Yahoo → origin**：VPS `roster_sync.py` cron 每 15 分 poll Yahoo transactions，有異動才更新 config + git push（空跑 ~1-2s 提早 return）
2. **origin → 本機**：`hooks/sync-mirror.mjs` SessionStart hook 開場 `git fetch`，在 master + working tree 乾淨 + 可 fast-forward 時自動 `pull --ff-only`

需要立即刷新（剛做完異動想馬上評估）→ `/sync-roster` 手動逃生口。

## 部署更新

VPS 端拉新版**不可裸 `git pull`**（roster cron 每 15 分 push 會 race），走：

```bash
bash bin/vps-run.sh --no-retry 'cd /opt/mlb-fantasy/daily-advisor && python3 git_sync.py /opt/mlb-fantasy'
```

`git_sync.py` 的 `pull_rebase_with_recovery()` 會自動修復「未追蹤檔與上游同路徑碰撞」（內容相同才移除重試，不同則中止報警）。

## 每日 / 每週人工 SOP

| 頻率 | 動作 |
|---|---|
| 每日 07:00 | 看日報 + FA Scan 報告 → 需要時微調 lineup（Daily - Tomorrow 制） |
| 週一 | `/rp-svh` RP 週掃 → `/weekly-review` 覆盤 + 預測 → 按需 `/player-eval`、`/waiver-scan` |
| 週四 | 查 IP 進度（scoreboard），不夠才考慮 `/stream-sp` 串流 |
| 事件觸發 | 球員受傷 / 表現差 → 查 `waiver-log.md` → `/player-eval` → 執行 |

## 已知地雷（Gotchas）

皆為實際踩過、已記錄於 CLAUDE.md / issues 的教訓——本段是人類可讀摘要，動手前讀對應追蹤檔。

### 系統面

- **Yahoo read-after-write lag × 浮水印**：交易寫入後 roster 查詢有延遲窗；watermark 在 lag 窗內推進會**永久漏交易**（踩過三次才根治為 monotonic watermark + 每日 reconcile）。動同步邏輯前先讀 `issues/roster-sync-watermark-feed-lag.md`
- **Daily-Tomorrow 次日生效 claim**：waiver claim 以當天時間戳記錄 successful，但 roster 效果 ET 隔日才反映——同步窗口不足 30h 會在生效前放棄並跳過該交易（commit `1a56c6f` 教訓）
- **`claude -p` 的 thinking 誘發**：在 prompt 加「只在實質變化時才 UPDATE」這類 skip 規則，實測誘發 ~12K thinking token、output 3 倍、cost +68%——「省 output」的直覺操作會 backfire（lever 2 已放棄，動 master prompt 前先做配對 A/B）
- **backtest「no verdicts」≠ 沒有 verdict**：曾因 parse regex 不匹配 production 格式 + outcome fetch 是 stub，兩班 cron 靜默空跑；單元測試全綠（手寫假樣本測不出）。驗收自動化必須拿 production 真實資料實測

### 決策面

- **SP 的 selected_pos 不是品質訊號**：投手在 SP/BN 間輪換調度，BN ≠ 非主力；drop 理由只能來自結構面（v4 5-slot / 雙年 prior / 樣本 / 21d 趨勢）
- **v2 退役指標（HH% / xERA / xwOBA）不可判 SP**：2026-05-04 曾用 HH% P5 反向誤判結構性弱；不在 5-slot 的百分位只是 context，不是 first-order signal
- **投手 drop 前查 probable starts**：BN ≠ 本週沒先發，用實證輪值取代 selected_pos 推測貢獻

## 故障排查

- **roster 沒同步**：查 VPS `/var/log/roster-sync.log` 與 git log；watermark 案例史見 `issues/roster-sync-watermark-feed-lag.md`
- **fa_scan 異常**:GitHub Issue label `fa-scan-error` + Telegram alert；SP Step A JSON 失敗有 1 retry + fall-through pass，cron 不會 silently crash
- **SSH 卡死**：根因（間歇丟包）見 `issues/vps-ssh-handshake-hang.md`；確保指令走 `bin/vps-run.sh`
- **歷史報告**：`gh issue list -R huansbox/mlb-fantasy --label fa-scan`（或 `week-N` / `[日報]`）
