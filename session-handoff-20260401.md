# Session Handoff — 2026-04-01

> 下個 session 先讀這份，再讀 CLAUDE.md。

## 本次 Session 完成事項

### 程式碼（已 commit + push + VPS 部署）

1. **投手 Statcast 整合**（`feat/pitcher-statcast` → merged）
   - `main.py`: `fetch_savant_statcast/expected` 加 `player_type` 參數，新增 `fetch_savant_for_pitchers` + format 函式
   - 速報 Section 1 加對方 SP Savant（HH%/Barrel% allowed），Section 2 加我方 SP Savant（xERA/xwOBA/HH%/Barrel%）
   - `roster_stats.py`: 投手表新增 7 欄（xERA/xwOBA/HH%/Barrel%/BBE + 去年基準）
   - `yahoo_query.py savant`: 自動偵測投手，batter 找不到 fallback pitcher

2. **投手評估框架統一**（`feat/pitcher-eval-framework` → merged）
   - CLAUDE.md / player-eval / waiver-scan / roster-scan / 3 個 prompt 模板全部對齊
   - 投手核心 3 指標：xERA / xwOBA allowed / HH% allowed（同打者邏輯）
   - SP 門檻：xERA < P60 (4.04) + IP > 180（正選）；xERA < P50 (4.33) + IP > 150（FA）

3. **百分位表升級**（已 commit）
   - 4 格 → 9 格（P25/P40/P45/P50/P55/P60/P70/P80/P90）
   - 投打通用，P90 = 菁英（投手 P90 = 低值 = 好）
   - 顯著性：差距 ≥ 10 百分位點 = 有意義

4. **百分位自動標籤**（`feat/pctile-tags` → merged）
   - `pctile_tag()` 函式，輸出 `(P70-80)` / `(>P90)` / `(<P25)` 格式
   - 已整合到：format_savant_stats / format_pitcher_savant / format_opp_sp_savant / roster_stats.py / yahoo_query.py

### 陣容異動（已在 Yahoo 執行 + CLAUDE.md/waiver-log 更新）

| Out | In | 理由 |
|-----|-----|------|
| Zack Littell (WSH, SP) | **Parker Messick** (CLE, SP) | Littell: WSH 弱隊 + 低 K + xERA P50（2025 是運氣）。Messick: Savant P80-90, CLE 保證先發 |
| Steven Kwan (CLE, LF) | **Jordan Walker** (STL, LF/RF) | Kwan: HH% <P25 / Barrel% <P25 = 零 power + 7×7 格式錯配。Walker: 23 歲 everyday + HH% >P90 breakout 候選 |

### 發現 / 洞見

- **Canzone (SEA, LF/RF)** 舊框架 Pass 在新 Statcast 框架下翻轉：187 BBE 三項全 >P90。但確認**硬 platoon**（只打 RHP，82 G/2025）。移回 Watchlist，等 BN 有空位。13% owned 不會被搶
- **Kwan 87% rostered 是市場慣性**：傳統 stats 看 .281 AVG 覺得好，Statcast 看 HH% 19% / Barrel% 1.9% 是全聯盟底層
- **3 agent 評審模式**有效：投手和打者各跑一次，共識+分歧清楚。投手 Littell 全員末位、打者 Kwan 全員末位 = 高信心 drop

---

## 未完成 / 下次接手的待辦

### 高優先（影響自動化品質）

#### 1. roster_config.json 未同步
今天 add Walker/Messick、drop Kwan/Littell，但 **roster_config.json 還是舊陣容**。所有自動化腳本（速報/FA Watch/Weekly Scan）都讀這個檔案。

**動作**：更新 roster_config.json → push → VPS `git pull`。

需要：
- 加 Walker(STL): mlb_id 691023, positions [LF, RF]
- 加 Messick(CLE): mlb_id 800048, positions [SP]
- 移除 Kwan, 移除 Littell

#### 2. fa_watch.py 弱點位置硬編碼
目前 `DAILY_QUERIES` 固定查 CF / SP / 1B。但 CF 已有 3 人覆蓋，**真正零替補的是 C / 1B / SS**。

**動作**：改為動態計算——從 roster_config.json 算每個位置覆蓋人數，0-1 人的自動加入查詢。

#### 3. prompt_fa_watch.txt 缺位置深度資訊
Claude 不知道哪些位置沒替補，所以會忽略 C/1B 雙棲球員這種結構性價值。

**動作**：在 `build_fa_watch_data()` 裡加一段「位置深度分析」，標記哪些位置零替補。讓 Claude 知道「C/1B 雙棲 FA = 填補兩個零替補位置的結構性價值」。

### 中優先（觀察驗證）

#### 4. Walker 開季驗證
觸發：3 週後（~4/21）xwOBA > P50 (.297) + HH% > P70 (44.7%) = breakout 確認。
失敗：連 3 週 xwOBA < P25 (.261) → 評估 drop，Canzone 或 FA 替補。

#### 5. Messick 開季驗證
Savant P80-90 是否持續。Steamer 113 IP 是否過度保守。注意 CLE 是否限制局數。

#### 6. Hancock 第二場（4/3-4/4 vs LAA）
觸發：xERA < P60 (4.04) + K/9 > 8 → drop Singer, add Hancock。
注意：Bryce Miller 回歸可能擠掉 Hancock rotation 位置。

#### 7. 百分位標籤 commit 驗證
`pctile_tag()` 已整合到所有 format 函式，但 `feat/pctile-tags` 分支的最終狀態需確認——VPS `--no-send` 驗證百分位標籤在速報中正確顯示。

### 低優先（可延後）

#### 8. weekly_scan.py 投手 Statcast
跟 fa_watch.py 同理——目前只餵傳統 stats 給 Claude，沒有 Savant 數據。

#### 9. Canzone 後續
BN 有空位時（例如 Walker 穩定後 drop Frelick，或 Buxton 不再需要 CF 保險）→ 撿 Canzone 當 RHP matchup 武器。13% owned，不急。

---

## 當前陣容快照（2026-04-01）

### 打者
| 位置 | 球員 | 隊伍 | 資格 | 備註 |
|------|------|------|------|------|
| C | Shea Langeliers | ATH | C | **零替補** |
| 1B | Christian Walker | HOU | 1B | **零替補** |
| 2B | Jazz Chisholm Jr. | NYY | 2B/3B | |
| 3B | Manny Machado | SD | 3B | |
| SS | Ezequiel Tovar | COL | SS | **零替補** |
| LF | Jose Altuve | HOU | 2B/LF | |
| CF | Byron Buxton | MIN | CF | 玻璃體質 |
| RF | Lawrence Butler | ATH | CF/RF | |
| Util | Ozzie Albies | ATL | 2B | |
| Util | **Jordan Walker** | STL | LF/RF | **NEW** 04-01 |
| BN | Sal Frelick | MIL | LF/CF/RF | CF 保險 |
| BN | Giancarlo Stanton | NYY | LF/RF | 純砲 |

### 投手
| 位置 | 球員 | 隊伍 | 備註 |
|------|------|------|------|
| SP | Tarik Skubal | DET | 王牌 |
| SP | Chris Sale | ATL | |
| SP | Cole Ragans | KC | |
| SP | Aaron Nola | PHI | 工作馬 |
| RP | Robert Garcia | TEX | 比率用 |
| RP | Garrett Whitlock | BOS | 比率用 |
| P | Brayan Bello | BOS | 觀察中 |
| P | **Parker Messick** | CLE | **NEW** 04-01，Savant P80-90 |
| P | Brady Singer | CIN | Hancock 替換候選 |
| BN | Chris Bassitt | BAL | SP 深度 |
| IL | Merrill Kelly | AZ | IL15 |

### 位置深度風險
| 零替補 | 覆蓋球員 | 風險 |
|--------|---------|------|
| **C** | Langeliers only | 傷退 = C 空洞 |
| **1B** | Walker(HOU) only | 傷退 = 1B 空洞 |
| **SS** | Tovar only | 傷退 = SS 空洞 |

---

## 系統文件依賴關係圖

```
CLAUDE.md（策略大腦）
  ├─ 陣容 / Watchlist / 行動觸發 / 百分位表 / 篩選標準
  ├─ 讀取者：全部 skill
  └─ 更新時機：陣容異動、策略變更

roster_config.json（球員 ID 中樞）⚠️ 需手動同步
  ├─ 球員名 / mlb_id / Yahoo key / positions / team
  ├─ 讀取者：main.py / fa_watch.py / weekly_scan.py / roster_stats.py
  └─ 更新時機：add/drop 後手動改 ← 今天還沒做

waiver-log.md（FA 追蹤）
  ├─ 觀察中 / 條件 Pass / 已結案
  ├─ 讀取者：fa_watch.py / weekly_scan.py / skill
  └─ 更新時機：player-eval / waiver-scan 後

roster-baseline.md（陣容基準卡）
  ├─ 全員 stats + Statcast + 趨勢
  ├─ 讀取者：waiver-scan / roster-scan
  └─ 更新時機：roster-scan skill（2-3 週一次）

fa_history.json（VPS 上，不同步回 repo）
  ├─ %owned 每日快照，保留 14 天
  └─ 讀寫者：fa_watch.py only

weekly_scan_summary.txt（VPS 上）
  ├─ 上一次 Weekly Scan 的摘要
  ├─ 寫入者：weekly_scan.py
  └─ 讀取者：fa_watch.py（作為 Claude context）
```
