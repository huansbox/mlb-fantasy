# 維運手冊

## 當前運作範圍（2026-08-05 起）

Yahoo 於 2026-07-28 對本專案的 app 全面撤銷 Fantasy API 存取，所有端點回 app-level 403（連公開的 `/game/mlb` 都擋）。OAuth token 照常 mint 與 refresh，**問題不在憑證，重新授權無效**。全業界事件，非本專案個案 — 證據見 [uberfastman/yfpy#84](https://github.com/uberfastman/yfpy/issues/84)。

| | 內容 |
|---|---|
| **還在跑** | 日報（平日 / 假日）、`savant_rolling`、日報健康檢查 — 全部只吃 MLB Stats API + Baseball Savant |
| **已停用** | `fa_scan`、`fa_scan --snapshot-only`、`weekly_review --prepare`、`roster_sync`（每 15 分 + reconcile）、B2 backtest |
| **不能用的 skill** | `/waiver-scan`、`/rp-svh`、`/stream-sp`、`/stream-sp-deep`、`/weekly-review`、`/sync-roster`、`/xingxiu`；`/player-eval` 打者流程可用，SP 流程部分步驟需 Yahoo |
| **還原方式** | VPS 上 `mv /etc/cron.d/daily-advisor.disabled-20260805 /etc/cron.d/daily-advisor` — 該檔是斷線前的原始版本，未經修改 |

`roster_config.json` 凍結在 2026-07-22，不再自動同步，名單異動需人工編輯。

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

生效中（`/etc/cron.d/daily-advisor`）：

| 排程 | UTC | 台灣 | 內容 |
|---|---|---|---|
| 日報（平日） | 21:30 Mon–Fri | 05:30 | ET 夜場 — 行動清單格式（今天不要上 / 今天可以上 / SP） |
| 日報（假日） | 14:30 Sat–Sun | 22:30 | ET 日場版本 |
| Savant Rolling | 04:00 每日 | 12:00 | 14d rolling 快照，日報的近況訊號來源 |
| 日報健康檢查 | 23:00 每日 | 07:00 | heartbeat 超過 48h 未更新就推 Telegram 警告 |

停用中（`/etc/cron.d/daily-advisor.disabled-20260805`）：FA Scan、FA Snapshot、Weekly Review 資料、Roster Sync（每 15 分）、Roster Reconcile、B2 Backtest — 全部依賴 Yahoo API。

報告自動存檔為 GitHub Issue（日報 label `week-N`）。

## 日報健康檢查（監控「沒發生的事」）

`daily_advisor` 每次成功送出 Telegram 後，在 `/var/lib/mlb-fantasy/last_report_success` 寫時間戳；`heartbeat_check.py` 由獨立 cron 每天檢查其年齡，超過 48h 推 Telegram 警告。

兩個刻意的隔離設計，動這塊前先讀 [`heartbeat_check.py`](https://github.com/huansbox/mlb-fantasy/blob/master/daily-advisor/heartbeat_check.py) 的模組 docstring：

- 檢查是**獨立腳本**而非 `daily_advisor` 內的分支 — 那支若整個沒跑（cron 被刪、VPS 重開、直譯器崩潰），不可能回報自己的缺席
- 兩支腳本**互不 import** — 任一方 import 對方，都會讓一邊的故障拖垮另一邊，偏偏就在最需要監控的時候。代價只是重複一個路徑常數

48h 門檻的推導：正常最長間隔是週日 14:30 → 週一 21:30（檢查時年齡 32.5h），連錯兩天的最緊情境是 49.5h。錯一天安靜、錯兩天出聲。

## Roster 新鮮度 pipeline（目前停用）

陣容唯一來源是 `daily-advisor/roster_config.json`，原本分兩層維護：

1. **Yahoo → origin**：VPS `roster_sync.py` cron 每 15 分 poll Yahoo transactions，有異動才更新 config + git push
2. **origin → 本機**：`hooks/sync-mirror.mjs` SessionStart hook 開場 `git fetch`，在 master + working tree 乾淨 + 可 fast-forward 時自動 `pull --ff-only`

第 1 層因 Yahoo API 中斷而停用，config 凍結於 2026-07-22。第 2 層仍運作（純 git，不碰 Yahoo）。

## 部署更新

VPS 端拉新版**不可裸 `git pull`**（roster cron 每 15 分 push 會 race）：

```bash
bash bin/vps-run.sh --no-retry 'cd /opt/mlb-fantasy/daily-advisor && python3 git_sync.py /opt/mlb-fantasy'
```

`git_sync.py` 的 `pull_rebase_with_recovery()` 會自動修復「未追蹤檔與上游同路徑碰撞」（內容相同才移除重試，不同則中止報警）。

> roster cron 停用期間 race 風險消失，`git pull --ff-only` 暫時安全；但 Yahoo 恢復、cron 還原後必須回到 `git_sync.py`。

## 每日 / 每週人工 SOP

降級期間（Yahoo 中斷中）：

| 頻率 | 動作 |
|---|---|
| 每日 07:00 | 看日報行動清單 → 在 Yahoo App 上照著調整 lineup（Daily - Tomorrow 制），約 2 分鐘 |
| 事件觸發 | 想撿的球員自己在 App 上看到 → `/player-eval` 手動評估（打者流程不需 Yahoo） |

Yahoo 恢復後回到完整 SOP：週一 `/rp-svh` + `/weekly-review`、週四查 IP 進度、按需 `/player-eval` 與 `/waiver-scan` — 定義見 repo [`CLAUDE.md`](https://github.com/huansbox/mlb-fantasy/blob/master/CLAUDE.md)「賽季運營 SOP」段。

## 已知地雷（Gotchas）

皆為實際踩過、已記錄於 CLAUDE.md / issues 的教訓——本段是人類可讀摘要，動手前讀對應追蹤檔。

### 系統面

- **第三方 API 是平台風險不是技術風險**：Yahoo 先在 2025-10 靜默移除 write scope，再於 2026-07 分波撤銷所有 legacy app 的 read access，全程無通知、無 support channel。連走完新審核制拿到 credentials 的專案也一起被斷 — 押注單一封閉 API 的系統，天花板由對方的產品決策決定
- **認證失效是靜默故障**：`claude -p` 的 OAuth token 於 2026-07-22 過期（`refreshToken` 欄位是空字串，續期鏈斷掉），日報默默停發兩週無人察覺。「沒收到訊息」比「收到錯訊息」難發現得多 — 這是日報健康檢查的由來
- **Yahoo read-after-write lag × 浮水印**：交易寫入後 roster 查詢有延遲窗；watermark 在 lag 窗內推進會**永久漏交易**（踩過三次才根治為 monotonic watermark + 每日 reconcile）。動同步邏輯前先讀 `issues/roster-sync-watermark-feed-lag.md`
- **Daily-Tomorrow 次日生效 claim**：waiver claim 以當天時間戳記錄 successful，但 roster 效果 ET 隔日才反映——同步窗口不足 30h 會在生效前放棄並跳過該交易（commit `1a56c6f` 教訓）
- **`claude -p` 的 thinking 誘發**：在 prompt 加「只在實質變化時才 UPDATE」這類 skip 規則，實測誘發 ~12K thinking token、output 3 倍、cost +68%——「省 output」的直覺操作會 backfire（lever 2 已放棄，動 master prompt 前先做配對 A/B）
- **backtest「no verdicts」≠ 沒有 verdict**：曾因 parse regex 不匹配 production 格式 + outcome fetch 是 stub，兩班 cron 靜默空跑；單元測試全綠（手寫假樣本測不出）。驗收自動化必須拿 production 真實資料實測

### 決策面

- **SP 的 selected_pos 不是品質訊號**：投手在 SP/BN 間輪換調度，BN ≠ 非主力；drop 理由只能來自結構面（v4 5-slot / 雙年 prior / 樣本 / 21d 趨勢）
- **v2 退役指標（HH% / xERA / xwOBA）不可判 SP**：2026-05-04 曾用 HH% P5 反向誤判結構性弱；不在 5-slot 的百分位只是 context，不是 first-order signal
- **投手 drop 前查 probable starts**：BN ≠ 本週沒先發，用實證輪值取代 selected_pos 推測貢獻

## 故障排查

- **日報沒來**：先看 Telegram 有無健康檢查警告；VPS `/var/log/daily-advisor.log` 與 `/var/log/daily-advisor-heartbeat.log`。認證問題跑 `cd /tmp && claude -p "Reply with exactly: PONG"` 驗證
- **Yahoo 403**：預期行為（見本頁「當前運作範圍」），非可修復故障
- **SSH 卡死**：根因（間歇丟包）見 `issues/vps-ssh-handshake-hang.md`；確保指令走 `bin/vps-run.sh`
- **歷史報告**：`gh issue list -R huansbox/mlb-fantasy --label fa-scan`（或 `week-N` / `[日報]`）
