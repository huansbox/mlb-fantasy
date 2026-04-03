# Session Handoff — 2026-04-03

> 下個 session 先讀這份，再讀 `CLAUDE.md`。
> 系統架構圖在 CLAUDE.md「系統架構」區段。

## 本次 Session 完成事項

### 1. roster_sync.py（全新腳本，從設計到部署）

- brainstorming → spec → plan → agent review × 2 → 實作 → code review → merge → 部署
- 功能：Yahoo 陣容自動同步到 roster_config.json
  - `--init`：全量 bootstrap（23 人 yahoo_player_key + 2025 prior_stats 全部寫入）
  - Daily cron TW 15:10：transactions gate → 有 add/drop 才 sync → auto git push + Telegram
  - `--dry-run`：預覽不寫入
- VPS 部署完成：cron + log 都設好
- 實作中發現並修正 4 個 bug

### 2. GitHub Issue 修復

- `week-2` label 不存在導致 03-30 起 issue 建不出來 → 自動 `gh label create --force`
- `--no-send` 仍建 issue → 移到 return 之前
- 補建 7 個遺漏 issue（#5-#11）

### 3. CLAUDE.md 評估框架更新

- 系統架構圖（四層文件依賴 + 讀寫標注）
- RP 評估：SV+H 從產量拆為加分項（品質小輸也值得換）
- |xERA-ERA| 運氣標記：加入方向（好運 vs 撿便宜）
- BBE 加權規則統一：< 30 只看去年 / 30-50 兩年並看 / > 50 當季為主
- Add/Drop 事件觸發改為「自動（roster_sync.py）」

### 4. weekly_scan Statcast 升級 — 設計完成

完整 spec 在 `docs/superpowers/specs/2026-04-03-weekly-scan-statcast-design.md`。
討論筆記在 `docs/superpowers/specs/2026-04-03-weekly-scan-statcast-notes.md`。
prompt 已更新（`prompt_weekly_scan.txt`）。

**下個 session 的主要工作：寫 implementation plan → 實作。**

### 5. 文檔整理

- Obsidian 專案筆記：架構圖（文件依賴層 + 腳本資料流）、Tasks 更新、近期更新、學習筆記
- 新 Worklog：`roster_sync — Yahoo 陣容自動同步`
- Worklog 兩階段報告：04-03 更新（Issue fix + 百分位驗證）
- file-dependencies.md：roster_sync + config schema 標記完成
- session-handoff-20260401/02：待辦標記完成

---

## 未完成 / 下次接手的待辦

### 功能開發（優先）

#### 1. weekly_scan.py Statcast 升級

**狀態**：spec 完成，待 implementation plan + 實作

核心改動：
- 三層漏斗（Yahoo 撈 FA → Savant 品質篩 → Claude 評估）
- FA 附 Statcast + 百分位 tag + %owned 變動
- 我方陣容附 prior_stats 摘要（由弱到強，隱藏最強幾位）
- %owned 快照改到 TW 15:10（fa_watch.py 加 --snapshot-only）

詳見 spec：`docs/superpowers/specs/2026-04-03-weekly-scan-statcast-design.md`

#### 2. fa_watch.py Statcast 整合

weekly_scan 做完後複用相同邏輯。目前 fa_watch 也沒有 Statcast（prompt 有要求但 data 沒有）。

### 觀察中（賽季進行）

#### 3. Hancock 第二場（4/3-4/4 vs LAA）
觸發：xERA < P60 (4.04) + K/9 > 8 → drop Singer, add Hancock。
注意：Bryce Miller 回歸可能擠掉 Hancock rotation 位置。

#### 4. Walker(STL) 開季驗證
- breakout 確認：xwOBA > P50 (.297) + HH% > P70 (44.7%)
- drop 評估：連 3 週 xwOBA < P25 (.261)

#### 5. Messick 開季驗證
Savant P80-90 是否持續。CLE 是否限制局數。

#### 6. Canzone 後續
BN 有空位時撿當 RHP matchup 武器。13% owned 不急。

### 時間觸發

#### 7. Week 4-5（~04-14）：回顧新指標框架
feedback_metrics_framework_observations.md 的 3 個觀察點。

#### 8. Week 6-8：更新百分位表為 2026 數據

---

## 關鍵改動提醒（給下次 session 的 AI）

- **CLAUDE.md 有系統架構圖了**——四層文件依賴 + 讀寫標注
- **roster_sync.py 已部署**——TW 15:10 cron，transactions gate，auto git push
- **roster_config.json 有 yahoo_player_key + prior_stats**——23 人全部有
- **BBE 加權規則已統一**——< 30 / 30-50 / > 50，寫在 CLAUDE.md 通用規則
- **RP SV+H 是加分項不是篩選條件**——品質小輸也值得換
- **prompt_weekly_scan.txt 已更新**——配合三層漏斗設計，但 weekly_scan.py 程式碼還沒改
- **打者 BB% = Yahoo BB ÷ Savant PA**——零額外 API call 的解法
- **%owned 快照要改到 TW 15:10**——fa_watch.py 加 --snapshot-only，是 weekly_scan 升級的一部分
