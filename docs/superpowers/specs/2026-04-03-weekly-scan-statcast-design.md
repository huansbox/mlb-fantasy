# Weekly Scan Statcast 升級 Design Spec

## Goal

修復 weekly_scan.py 的 prompt-data 脫節：prompt 要求 Claude 用 Statcast 指標評估 FA，但資料只有 Yahoo 傳統 stats。同時重構 FA 撈取邏輯和 %owned 快照機制。

## 改動範圍

| 檔案 | 改動 |
|------|------|
| `daily-advisor/weekly_scan.py` | 主要改動：三層漏斗、Savant 整合、我方陣容摘要 |
| `daily-advisor/fa_watch.py` | 加 `--snapshot-only` flag；%owned 快照邏輯拆分 |
| `daily-advisor/prompt_weekly_scan.txt` | 已更新（本 session 完成） |
| `CLAUDE.md` | 已更新：BBE 加權、RP SV+H、|xERA-ERA| 方向（本 session 完成） |
| `/etc/cron.d/daily-advisor` | 新增 15:10 snapshot cron |

## 三層漏斗設計

### 第 1 層：Yahoo API 多角度撈 FA

三個來源去重合併：

**AR rank（本季累計表現）**

| 位置 | count |
|------|-------|
| 打者（position=B） | 50 |
| SP | 30 |
| RP | 20 |

**Lastweek（上週單週爆發，sort_type=lastweek）**

| 位置 | count |
|------|-------|
| 打者 | 30 |
| SP | 20 |
| RP | 10 |

**%owned 升幅（3d 變動排序，從快照歷史算）**

| 位置 | top N |
|------|-------|
| 打者 | 20 |
| SP | 20 |
| RP | 5 |

去重後預估 ~100-130 人。不再有零替補位置專查（AR 打者 50 已涵蓋）。只保留升幅排行，移除降幅。

### 第 2 層：Savant CSV 品質篩選

**資料來源**：批次下載 4 個 Savant CSV（一次性）：
- batter statcast（HH%, Barrel%）
- batter expected（xwOBA, PA）
- pitcher statcast（HH% allowed, Barrel% allowed）
- pitcher expected（xERA, xwOBA allowed）

**匹配**：name matching（0 API call，覆蓋 ~95%）。

**BBE 加權規則**（CLAUDE.md 通用規則）：
- BBE < 30 → 只看 2025（當季純噪音）
- BBE 30-50 → 兩年並看（任一年 2/3 達標即通過）
- BBE > 50 → 當季為主

**篩選門檻**：

| 類型 | 核心 3 指標 | 門檻 | 理由 |
|------|-----------|------|------|
| **RP** | xERA / xwOBA allowed / HH% allowed | 2/3 >= **P50** | 2 格，現有品質 P60-P90 |
| **SP** | xERA / xwOBA allowed / HH% allowed | 2/3 >= **P40** | 7-8 格，最弱 SP 約 P40-P50 |
| **打者** | xwOBA / BB% / Barrel% | 2/3 >= **P40** | 10 格，FA 池品質有限 |

P40 / P50 具體數值：

| 指標 | P40 | P50 |
|------|-----|-----|
| xERA | 4.64 | 4.33 |
| xwOBA allowed | .332 | .322 |
| HH% allowed | 42.2% | 40.8% |
| xwOBA（打者） | .286 | .297 |
| BB% | 7.0% | 7.8% |
| Barrel% | 6.5% | 7.8% |

**打者 BB% 計算**：Yahoo stats 的 BB（計數）÷ Savant CSV 的 PA，零額外 API call。

**%owned 升幅 top 但 name matching 失敗**：也用 search_mlb_id 補救（第 1 層市場訊號強的不該因匹配失敗而遺漏）。

預估通過：~20-30 人（打者 ~10-15，SP ~5-10，RP ~5-10）。

### 第 3 層：Claude 評估

通過第 2 層的球員，用 search_mlb_id 拿精確 mlb_id，然後：
1. 用 mlb_id 從 Savant CSV 重取精確數據（取代 name matching 結果）
2. 查 MLB Stats API（2025 + 2026 兩年）拿產量指標

**給 Claude 的資料格式**：

**FA 打者**：
- 品質（核心）：xwOBA / BB% / Barrel% + 百分位 tag
- 輔助：HH% / OPS
- 產量：PA/Team_G（2025 ÷ 162，2026 ÷ 球隊 gamesPlayed）
- Yahoo stats：AVG / OPS / HR / BB（計分類別參考）
- 市場：%owned + 3d/24h 變動
- 樣本：BBE

**FA SP**：
- 品質（核心）：xERA / xwOBA allowed / HH% allowed + 百分位 tag
- 輔助：Barrel% allowed / ERA / |xERA-ERA| 方向+幅度
- 產量：IP/GS
- Yahoo stats：ERA / WHIP / K / IP
- 市場：%owned + 3d/24h 變動
- 樣本：BBE

**FA RP**：
- 品質（核心）：xERA / xwOBA allowed / HH% allowed + 百分位 tag
- 輔助：Barrel% allowed / ERA / |xERA-ERA| 方向+幅度
- 產量：K/9 / IP/Team_G
- 加分項：SV+H（品質小輸也值得換）
- Yahoo stats：ERA / WHIP / K / IP / SV+H
- 市場：%owned + 3d/24h 變動
- 樣本：BBE

**球隊 gamesPlayed 來源**：`/api/v1/standings?leagueId=103,104&season=2026`，1 次 API call 拿全部 30 隊。

## 我方陣容摘要

從 roster_config.json 的 prior_stats 讀取（零 API call）。由弱到強排序，隱藏最強的（Claude 只看可能被替換的人）。

| 類型 | 排序依據 | 隱藏 | 顯示 |
|------|---------|------|------|
| 打者 | xwOBA | 前 5 強 | 7 人 |
| SP | xERA | 前 3 強 | 6 人 |
| RP | 不排 | 無 | 全部 2 人 |

顯示欄位：
- 打者：xwOBA / BB% / Barrel% / HH% / OPS / PA/Team_G
- SP：xERA / xwOBA / HH% / Barrel% / ERA / IP/GS
- RP：xERA / xwOBA / HH% / Barrel% / ERA / K/9 / IP/Team_G / SV+H

## %owned 快照機制改動

### 快照時間：07:00 → TW 15:10

- Yahoo waiver 統一 ET 3AM（TW 15:00）處理，%owned 變動集中在該時間點
- 15:10 存的快照 = 當天定值，之後到隔天幾乎不動
- 比較窗口精確：15:10 vs 15:10 = 精確 24h / 72h

### 實作

- fa_watch.py 加 `--snapshot-only` flag：只執行 `collect_fa_snapshot` + `save_fa_history`，不跑 claude / telegram
- 新 cron：TW 15:10 跑 `fa_watch.py --snapshot-only`
- 07:00 的 fa_watch 和 19:30 的 weekly_scan：讀已存的快照做分析，不即時查 Yahoo %owned

### %owned 升幅排行

- weekly_scan 用 **3d** 排序（看趨勢），fa_watch 維持 **24h**
- 按位置分開（打者 / SP / RP）
- 只保留升幅，移除降幅
- 同時附 24h 變動（看加速度）

## API Call 預算

| 階段 | API | 次數 | 用時 |
|------|-----|------|------|
| 第 1 層 | Yahoo FA queries | ~9 次（3 位置 × 3 排序） | ~9 秒（含 rate limit sleep） |
| 第 2 層 | Savant CSV download | 4 次 | ~8 秒 |
| 第 3 層 | MLB API search_mlb_id | ~20-30 次 | ~6 秒 |
| 第 3 層 | MLB Stats API（產量） | ~40-60 次（×2 年） | ~12 秒 |
| 第 3 層 | MLB standings（gamesPlayed） | 1 次 | ~0.2 秒 |
| Claude | claude -p | 1 次 | ~30-60 秒 |
| **合計** | | ~75-105 次 | **~65-95 秒** |

一週一次，完全可接受。

## 已完成的配套改動（本 session）

- [x] CLAUDE.md：BBE 加權規則（< 30 / 30-50 / > 50）
- [x] CLAUDE.md：RP SV+H 加分邏輯（品質小輸也值得換）
- [x] CLAUDE.md：|xERA-ERA| 方向標記（運氣好 vs 撿便宜）
- [x] prompt_weekly_scan.txt：配合新資料結構全面更新

## 不在範圍

- fa_watch.py Statcast 整合（先做 weekly_scan，之後複用相同邏輯）
- Yahoo API 寫入功能（自動 add/drop）
