# MLB Fantasy Baseball 2026 賽季管理

## 專案概述

2026 Yahoo Fantasy Baseball 聯賽 — 選秀已完成，目前為 in-season 管理階段。

## 聯賽設定（開季確認版 2026-03-26）

- **平台**：Yahoo Fantasy Baseball
- **賽制**：H2H **One Win 勝負制**（14 類別合計，贏 8+ = 1 週勝）
- **隊伍數**：12 隊，無分區
- **名單配置**：
  - 打者：C / 1B / 2B / 3B / SS / **LF / CF / RF** / UTIL×2（共 10 人）
  - 投手：SP×4 / RP×2 / P×3（共 9 人）
  - BN×3 / IL×2 / NA×1
- **計分類別（7×7）**：
  - 打者：R, HR, RBI, SB, BB, AVG, OPS
  - 投手：IP, W, K, ERA, WHIP, QS, SV+H
- **限制與規則**：
  - 每週最低 **40** 投球局數（Min IP = 40，未達 → ERA + WHIP 判負）
  - 每週最多 6 次異動（Max Acquisition = 6）
  - Waiver：**FAB**（Free Agent Budget）+ Continual rolling list tiebreak
  - Lineup 鎖定：**Daily - Tomorrow**（每天要設隔日先發）
  - Trade Review：Commissioner，Reject Time 2 天
- **季後賽**：4 隊，Week 24-25（至 9/20）

## 核心球員

不可動的核心（can't cut 等級）：
- **Tarik Skubal**（DET, SP）— 全聯盟 #1
- **Jazz Chisholm Jr.**（NYY, 2B/3B）— 2B 稀缺
- **Manny Machado**（SD, 3B）— 穩定輸出

> 完整陣容見 `daily-advisor/roster_config.json`（唯一名單來源）。

## 執行中策略

- **Punt SV+H**：不為 SV+H 多拿 RP（維持 2 位），但現有 RP 有 SV+H 是加分
- **軟 Punt SB**：不刻意追速度，靠陣容中有速度的打者偶爾贏
- **SP 重裝**：9 SP 深度，40 IP 門檻輕鬆過
- **目標**：每週穩拿 R/HR/RBI/BB/AVG/OPS + IP/W/K/QS/ERA/WHIP 共 12 項中的 8+
- **串流 SP**：預設不串流，具體依下方決策規則判斷（FA 池品質、對手強弱、比率餘裕）

### 串流 SP 決策規則（2026-03-30 確立）

| 情境 | 做法 |
|------|------|
| 週四發現 IP 差 40 很遠（< 30 IP 且只剩 1 場先發） | 撿 1 個 matchup 好的串流 SP |
| 某項 counting stat 接近翻盤（K 差 3-5 個） | 精準撿 1 場高 K 率 SP |
| ERA/WHIP 已大幅領先（ERA < 2.50） | 比率有餘裕，可冒險加 1 場 |
| 對手弱到本週穩贏 | 可用 2-3 次異動測試串流效果 |
| **預設** | **不串流，留異動額度給傷兵替補和 hot bat** |

### 串流 SP 操作流程（2026-04-06 確立）

**查先發日程的正確方法**：
```bash
# 用 MLB API 逐日查 probable pitcher（只提前 1-2 天公布）
curl -s "https://statsapi.mlb.com/api/v1/schedule?date=2026-04-08&sportId=1&hydrate=probablePitcher"
```
- ⚠️ **不要用 FanGraphs/FantasyPros 的 probables grid 推測**（常有錯誤，例如把 5 天間隔排成 3 天）
- **正確方式**：查球員 game log 最後一場日期 + 5 天推算，再用 MLB API 確認
- MLB API 只提前 1-2 天公布 probable，更遠的日期需用輪值間隔推算

**FAAB 時效與串流時程**：
1. 提交 FAAB claim（在每日 TW 15:00 前）
2. 當日 TW 15:00（= ET 3AM）處理
3. 處理後當晚設 Daily-Tomorrow lineup
4. **隔天上場（前置 1 天）**
5. → 串流 SP 需在目標先發日的**前一天** TW 15:00 前 claim
6. ⚠️ 若 claim 在 TW 15:00 後提交，順延到次日處理（多等 1 天）

**串流測試策略**（適用於觀察中候選 SP）：
- 搶先發日最近的候選 → 看一場結果
- 好就留（轉為正式 roster），不好就 drop 換下一位候選
- 每週 6 次異動上限需預留 1-2 次給傷兵替補

### Waiver 操作規則（聯賽設定確認 2026-03-30）

- **所有撿人走 FAAB**（waiver_rule: all），無即時 FA
- **處理時間**：每日 ET 3AM（= TW 15:00）
- **上場時效**：claim（TW 15:00 前）→ 當日 TW 15:00 處理 → 當晚設 Daily-Tomorrow lineup → 隔天上場（前置 1 天）
- **被 drop 球員**：1 天 waiver period
- **FAAB 預算**：$100 全季，同額 tiebreak = continual rolling list
- **FAAB 餘額**：$100（2026-04-02 更新，異動後手動更新此數字）
- **每週上限**：6 次 add（add/drop 一組算 1 次）

### 陣容風險

由自動化腳本從 `roster_config.json` + 即時數據動態計算（見 `fa_watch.py` / `weekly_scan.py` 輸出）。
包含位置深度（零替補位置）和球員表現急迫性。

> FA 觀察追蹤見 `waiver-log.md`（觀察中 / 觸發條件 / 已結案）。

## 球員評估框架

> 唯一定義。Skills（/player-eval、/waiver-scan）引用此處，不複製。

### 通用規則

- 所有指標參照百分位表（2025 MLB 數據），差距 ≥ 10 百分位點 = 有意義
- 取當季 + 前一年數據對照，附樣本量（PA / BBE / IP）
- **賽季數據加權**（投打通用，BBE 為準）：
  - 當季為主要評估依據，前一年為輔助脈絡
  - BBE 標示信心水準：BBE < 30 = 低信心（樣本噪音大）、30-50 = 中等、> 50 = 高信心
  - 當季高 + 前一年高 → 值得行動（品質確認）
  - 當季高 + 前一年低 → 觀察，breakout 候選（待樣本驗證）
  - 當季高 + 前一年無數據 → 觀察，新人待驗證
  - 設計取向：寧可早期抓到 breakout 再驗證，不要等穩定後被搶走
- 「不動也是策略」— FA 未明顯優於現有球員 → 不換
- 轉隊確認：球員目前球隊 = 數據球隊？不符就重新評估
- 12 隊聯賽 xwOBA > P90 的 FA 基本不存在 → 出現代表 drop 失誤

### 打者評估

**評估流程**：
1. 品質 + 產量指標排序全隊打者 → 產出「最弱 5 人」（不看守位）
2. FA/交易候選只跟這 5 人比較 → 這步加入脈絡

**核心 3 指標**（品質，2 項勝出 = 值得行動）：
- **xwOBA** — 打擊品質總指標，取代 AVG
- **BB%** — 最高效指標（BB 欄 + OPS 的 OBP 端，7×7 雙重計算）
- **Barrel%** — HR 最佳預測指標，7×7 無 K 懲罰下 power 是核心價值

**產量指標**：
- **PA / Team_G** — 同時反映上場率、打序位置、球隊進攻環境

**輔助指標**：
- HH%（確認整體接觸品質，Barrel% 的上層指標）
- OPS（計分類別直接影響）

**樣本量加權**：見通用規則「賽季數據加權」。另外上季 < 80 場 → 需查 career stats，不可只看單季。

**7×7 格式規則**：
- 無 K 類別 → 高 K 打者無懲罰
- Punt SB → 速度價值打折，但非零
- 不使用 hot/cold streaks（零預測力）
- 不使用 BvP 歷史對戰（樣本太小）

**陣容脈絡**（Step 2 時考慮）：
- 守位需求：填什麼位？升級、backup、重複？
- 單點故障：是否解決零替補位置風險？
- 邊際遞減：陣容已有強項再加同類型，效益低
- BN 只有 3 格，每格珍貴

### SP 評估

**評估流程**：同打者邏輯，排出隊上最弱 4 位 SP → FA 只跟最弱的比

**核心 3 指標**（品質，2 項勝出 = 值得行動）：
- **xERA** — 取代 ERA，排除 BABIP/運氣噪音
- **xwOBA allowed** — 被打品質總指標
- **HH% allowed** — 核心（ERA/WHIP 受所有硬接觸影響，比 Barrel% 更廣）

**產量指標**：
- **IP/GS** — 每次先發平均局數，涵蓋 IP/QS/W 產量天花板

**輔助指標**：
- Barrel% allowed（確認 HR 被打風險）
- ERA（計分類別直接影響）
- |xERA - ERA| 運氣標記（百分位判斷幅度，P70+ = 顯著）：
  - ERA < xERA（運氣好）→ ERA 預期回升，表現會變差（例：ERA 1.84 / xERA 3.36）
  - ERA > xERA（運氣差）→ ERA 預期回降，撿便宜訊號（例：ERA 5.00 / xERA 3.50）

**樣本量加權**：見通用規則「賽季數據加權」。另外上季 < 80 IP → 用預期值區間而非單點估計。

**7×7 格式規則**：
- IP 是獨立類別 → 局數怪物 > 精品短局型
- QS 需 6+ IP → IP/GS 低的投手 QS 打折
- W 受球隊影響 → 強隊 SP 有 W 加成
- 串流 SP：下週有 2 先發 + 對戰後段打線，不看全季指標

### RP 評估

**策略前提**：Punt SV+H（不主動追），但 RP 仍貢獻 ERA/WHIP/K。維持 2 位 RP，不會加到 3-4 位。

**評估流程**：只有 2 人，不排最弱清單。FA 有無優於目前 2 位 RP → 有就換。

**品質指標**（核心，2 項勝出 = 值得行動）：xERA、xwOBA allowed、HH% allowed（同 SP）
**輔助**：Barrel% allowed、ERA、|xERA - ERA| 運氣標記（同 SP：ERA < xERA = 運氣好會回升，ERA > xERA = 運氣差可撿便宜）
**產量**：K/9、IP / Team_G
**加分項**：SV+H — 品質小輸也值得換（RP 只佔 2 格，比率影響有限；但 SV+H 是獨立類別，多贏 1 類 = 多 1 勝，且多隊 punt SV+H → 門檻低）

注意：RP 百分位分布和 SP 不同，需分開計算。

### 2025 MLB 百分位分布（P90 = 菁英）

打者（數值越高越好）：

| 百分位 | xwOBA | BB% | Barrel% | HH% | PA/Team_G |
|--------|-------|-----|---------|------|-----------|
| P25 | .261 | 5.8% | 4.7% | 34.6% | 0.88 |
| P40 | .286 | 7.0% | 6.5% | 38.3% | 1.37 |
| P45 | .293 | 7.4% | 7.1% | 39.0% | 1.71 |
| **P50** | **.297** | **7.8%** | **7.8%** | **40.4%** | **1.96** |
| P55 | .302 | 8.2% | 8.5% | 41.5% | 2.16 |
| P60 | .307 | 8.7% | 9.1% | 42.6% | 2.47 |
| P70 | .321 | 9.6% | 10.3% | 44.7% | 2.90 |
| P80 | .331 | 10.8% | 12.0% | 46.7% | 3.39 |
| P90 | .349 | 12.2% | 14.0% | 49.7% | 3.96 |

SP（品質指標：數值越低越好，P90 = 菁英 = 低值）：

| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | \|xERA-ERA\| |
|--------|------|---------------|-------------|-----------------|-------------|
| P25 | 5.62 | .361 | 44.2% | 10.1% | 0.28 |
| P40 | 4.64 | .332 | 42.2% | 9.1% | 0.43 |
| P45 | 4.48 | .327 | 41.6% | 8.9% | 0.49 |
| **P50** | **4.33** | **.322** | **40.8%** | **8.5%** | **0.53** |
| P55 | 4.16 | .316 | 40.2% | 8.1% | 0.59 |
| P60 | 4.04 | .312 | 39.4% | 7.9% | 0.66 |
| P70 | 3.74 | .301 | 38.0% | 7.1% | 0.81 |
| P80 | 3.43 | .289 | 36.4% | 6.3% | 1.03 |
| P90 | 2.98 | .270 | 34.1% | 4.9% | 1.31 |

SP IP/GS 三級分類（分布集中，不適合百分位）：

| IP/GS | 等級 | 意義 |
|-------|------|------|
| > 5.7 | 深投型 | QS 機率高，IP/W 貢獻穩定 |
| 5.3 - 5.7 | 一般 | 多數 SP 落在這裡 |
| < 5.3 | 短局型 | QS 打折，IP 貢獻受限 |

RP（品質指標同 SP 方向；K/9 和 IP/Team_G 越高越好）：

| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | K/9 | IP/Team_G | \|xERA-ERA\| |
|--------|------|---------------|-------------|-----------------|-----|-----------|-------------|
| P25 | 5.62 | .361 | 44.2% | 10.1% | 7.51 | 0.24 | 0.28 |
| P40 | 4.64 | .332 | 42.2% | 9.1% | 8.24 | 0.29 | 0.43 |
| P45 | 4.48 | .327 | 41.6% | 8.9% | 8.44 | 0.31 | 0.52 |
| **P50** | **4.33** | **.322** | **40.8%** | **8.5%** | **8.70** | **0.34** | **0.57** |
| P55 | 4.16 | .316 | 40.2% | 8.1% | 8.88 | 0.35 | 0.63 |
| P60 | 4.04 | .312 | 39.4% | 7.9% | 9.23 | 0.37 | 0.72 |
| P70 | 3.74 | .301 | 38.0% | 7.1% | 9.75 | 0.40 | 0.88 |
| P80 | 3.43 | .289 | 36.4% | 6.3% | 10.39 | 0.42 | 1.06 |
| P90 | 2.98 | .270 | 34.1% | 4.9% | 11.47 | 0.45 | 1.24 |

（2025 全季。打者 min 50 BBE, n=537。SP: GS>50%G, n=216。RP: GS≤50%G, n=284。xERA 交叉 Savant min 50 BBE）
注意：SP IP/GS 分布極集中（P40-P60 僅差 0.27 局），區辨力有限。
注意：RP 品質指標（xERA/xwOBA/HH%/Barrel%）複用 SP 百分位表，K/9 和 IP/Team_G 為 RP 專用。

**數據來源**：傳統 stats = MLB Stats API / Yahoo API；Statcast = Baseball Savant CSV。取當季 + 前一年，附樣本量。

## 賽季運營 SOP

### 每日

| 時間 (TW) | 做什麼 | 說明 |
|-----------|--------|------|
| 22:15 | 收速報 → 設隔日 lineup → 睡覺 | 自動推送 |
| 05:00 | 最終報產出 | 自動推送（睡眠中） |
| 07:00 | 起床看最終報 + FA Watch → 微調（如需要） | 兩份一起看 |

### 每週（週一）

| 順序 | 做什麼 | 說明 |
|------|--------|------|
| 1 | 收 Weekly Scan 報告（19:30 自動） | 自動推送 |
| 2 | `/weekly-review`：覆盤上週 + 預測本週 | 手動 session |
| 3 | 按需：`/player-eval` 或 `/waiver-scan` | 手動 session |

### 週中決策點

| 時間 | 做什麼 |
|------|--------|
| 週四 | 檢查 IP 進度（速報會提醒），不夠才考慮串流 |
| 任何時候 | waiver-log.md 觸發條件達成 → 執行行動 |

### 低頻（2-3 週一次）

| 做什麼 | 條件 |
|--------|------|
| 聯賽偵察更新 | 對手有大幅異動時 |

### 事件觸發

| 事件 | 動作 |
|------|------|
| 球員受傷/表現差 | 查 waiver-log.md 有無候選 → 有：`/player-eval` 確認 → 執行。沒有：`/waiver-scan` 找人 → `/player-eval` → 執行 |
| Add/Drop 執行後 | 自動：roster_sync.py（cron TW 15:10）偵測 → 更新 config → git push → Telegram 通知 |
| FAAB 出價 | 更新 roster_config.json 的 faab_remaining + 本文件 FAAB 餘額 |
| waiver-log.md 觸發條件達成 | `/player-eval` 深入評估 → 決定行動 |

### 系統架構

```
CLAUDE.md（策略大腦 + 評估框架唯一定義）
  ├─ 評估框架（打者/SP/RP）+ 百分位表 + 賽季運營 SOP
  ├─ 被讀取：所有 skill（/player-eval, /waiver-scan, /weekly-review）
  └─ 被更新：策略調整時手動改（唯一來源，skills 引用不複製）

roster_config.json（陣容唯一來源）
  ├─ 球員名 / mlb_id / yahoo_player_key / positions / team / prior_stats
  ├─ selected_pos（Yahoo 格位：IL/IL+/BN/NA/位置）/ status（MLB 狀態：IL10/IL60/DTD/NA/空=健康）
  ├─ 被讀取：daily_advisor.py / fa_watch.py / weekly_scan.py / roster_stats.py / weekly_review.py
  └─ 被更新：roster_sync.py（cron TW 15:10，偵測 add/drop + 更新狀態 → auto sync + git push）

waiver-log.md（FA 追蹤唯一來源）
  ├─ 觀察中 / 條件 Pass / 已結案
  ├─ 被讀取：fa_watch.py / weekly_scan.py / skills
  └─ 被更新：/player-eval / /waiver-scan skill

資料流：MLB Stats API + Yahoo Fantasy API + Baseball Savant CSV
  → Python 腳本組裝 → claude -p 分析 → Telegram 推送 + GitHub Issue 存檔
```

### 檔案索引

| 文件 | 用途 |
|------|------|
| `daily-advisor/roster_config.json` | 陣容唯一來源（球員名單 + ID + 位置 + 去年數據 + Yahoo 格位 + MLB 狀態） |
| `waiver-log.md` | FA 觀察追蹤（觀察中 / 條件 Pass / 已結案） |
| `week-reviews.md` | 累積式週覆盤記錄 |
| `league-scouting.md` | 聯賽 12 隊 GM 策略分析 |
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |

## 待辦

### ~~fa_watch Statcast 升級~~ ✅ 完成（2026-04-03）

fa_watch 從 Yahoo-only 日報升級為窄追 ~10 人的 Statcast 監控。候選從 fa_history + waiver-log 產生（不廣撈），複用 weekly_scan 的 Savant pipeline。`enrich_layer3` 加 `savant_prior` 開關（預設 True），之後 2026 樣本夠時 fa_watch + weekly_scan 一起關。

### ~~Prompt / Skills 對齊~~ ✅ 完成（2026-04-03）

- [x] `prompt_fa_watch.txt`：隨 fa_watch 升級完整改寫
- [x] `.claude/commands/` skills：已驗證全部正確引用 CLAUDE.md
- [x] `prompt_template.txt`：修正對手 SP 指標（移除 HR9/BB9，Savant 優先）
- [x] `prompt_template_morning.txt`：已驗證無問題
- [x] `roster_stats.py`：BB% 加百分位標記
- [x] `weekly_review.py`：已驗證無衝突

### ~~評估流程優化~~ ✅ 完成（2026-04-06）

> 來源：Week 2 SP drop/add 實戰，完整紀錄見 `daily-advisor/roster_stats_manual_20260406.md`
> Branch: `refactor/eval-pipeline-optimization`

- [x] SOP: waiver-scan Step 1 加 `roster_stats.py` 雙年數據 + `yahoo_query.py scoreboard` 類別排名
- [x] SOP: player-eval Step 1 加球員狀態驗證 + 當季數據要求 + WebSearch 年份提醒
- [x] Bug: VPS git push 403 — 根因是 divergence 非 auth；已加 rebase-abort + Telegram 通知
- [x] Bug: `yahoo_query.py` savant type detection — 查兩邊 CSV 比較 BBE 取高的
- [x] Bug: falsy-zero 全掃（`daily_advisor.py` / `weekly_scan.py` / `yahoo_query.py` / `roster_stats.py`）
- [x] Feature: `yahoo_query.py scoreboard [--pitching|--batting]` — 全聯盟 12 隊類別排名
- [x] Feature: `yahoo_query.py player` 加 MLB API roster status 交叉驗證

### 排程與流程改進

- [x] **weekly_review.py cron 提早到 TW 12:30**（UTC 04:30）：已更新 VPS cron（2026-04-06）
- [x] **weekly_review.py 改用 Yahoo API `roster;date={date}` 取陣容**：我方 + 對手都改用 `fetch_roster()` + date 參數（2026-04-06）
- [x] **weekly_scan.py cron 配合提早**：TW 19:30 → TW 13:00（UTC 05:00）（2026-04-06）
- [x] **weekly_review.py 守位覆蓋邏輯**：改用 Yahoo API roster + 排除 IL/NA（2026-04-06）
- [x] **IL / NA 狀態區分**：roster_config.json 有 `selected_pos` + `status`；`daily_advisor.py` config fallback 用 `selected_pos` 推算 role；`weekly_review.py` 排除 IL/NA；NA 格正確映射為 role="IL"（2026-04-06）
- [ ] **preview 加入對手近期異動**：從 Yahoo API league transactions 過濾對手 add/drop，判斷對手 build 策略（囤 SP / 串流 / 正常）
- [ ] **preview 加入聯盟 scoreboard**：用 `yahoo_query.py scoreboard` 邏輯存入 JSON，預測時有數據基礎
- [ ] **SP 排程推估**：對 MLB API 未公布 probable 的日期（+3 天以後），用 game log 最後先發日 +5 天推算，標記「推估」
- [ ] **IP/GS 指標失準**：有時先發有時中繼的 swingman（如 Liberatore），GS 只算先發場次但 IP 含全部出場，導致 IP/GS 虛高（以為每次先發投很多局）。需改為只算先發場次的 IP
- [ ] **roster_sync --init 不 backfill 新欄位**：當沒有 add/drop 也沒有 key/stats 缺失時，`run_init` 提前 return，不走 `update_config()`，導致 `selected_pos`/`status` 等新欄位不會被寫入。日常 cron 有異動時正常 backfill，僅手動 `--init` 無異動時觸發

### weekly_review 加入隊上球員表現評估

> 讓 Phase 1 覆盤有結構化的「誰拖累、誰撐場」資料，不用手動跑 roster_stats.py

**位置**：`weekly_review.py --prepare` 新增 `review.my_roster_performance` 區段

**打者每人**：
- 當週（MLB API game log 按日期過濾）：PA, R, HR, RBI, SB, BB, AVG, OPS
- 開季至今（MLB API + Savant CSV）：同上 + xwOBA, BB%, Barrel%, HH%

**SP 每人**（RP 只有 2 人，不評估）：
- 當週（MLB API game log）：GS, IP, W, K, ERA, WHIP, QS
- 開季至今（MLB API + Savant CSV）：同上 + xERA, xwOBA allowed, HH% allowed

**實作**：複用 `daily_advisor.py` 的 game log + `roster_stats.py` 的 Savant 函式，新增 `compute_roster_performance()`

### weekly_review 整合 weekly_scan 結果

> 讓 /weekly-review 一個 session 完成「覆盤 → 預測 → FA 行動決策」完整循環

**改動 1：cron 順序調換**
- weekly_scan 先跑（TW 12:30）→ weekly_review 後跑（TW 13:00）
- 語義：先掃 FA 市場，再準備覆盤資料（含 scan 結果）

**改動 2：weekly_review.py 加 `scan_summary` 欄位**
- 讀 VPS 上的 `weekly_scan_summary.txt` 或 GitHub Issue
- 塞進 week-N.json 供 skill 引用

**改動 3：/weekly-review skill 加 Step 4（FA 行動決策）**
- 讀 scan 建議的候選球員
- 搭配 Phase 1 覆盤 insight（誰拖累）+ Phase 2 預測（需要補強什麼）
- 決定是否跑 /player-eval 或直接行動

### weekly_scan 品質優化

> Layer 2 通過 73 人，全部送 Claude 分析。可行但有稀釋注意力風險。

- [ ] **分批送 Claude**：bat / SP / RP 分三次，各自用對應的評估框架 prompt
- [ ] **或拉高門檻**：目前 2/3 核心指標通過即可，考慮加 BBE 最低門檻（如 BBE ≥ 15）刷掉極端噪音
- [ ] **RP 過濾**：維持 2 RP 不加到 3-4 位，scan 只需找「優於現有 2 RP」的替換候選。SP/RP swingman 低 owned + 極小 BBE 無用，可刷掉。有 SV+H 產量的純 RP 仍有價值（加分項）

### 功能開發

- [x] 04-06 週一：觀察首次真實 weekly_scan 自動跑 — Layer 2 通過率 85%（86→73），Layer 3 耗時正常，Claude 品質 OK
- [ ] Week 4-5（~04-14）：回顧新指標框架（feedback_metrics_framework_observations.md 的 3 個觀察點）
- [ ] Week 6-8：更新百分位表為 2026 賽季數據（CLAUDE.md + daily_advisor.py + prompt 檔）
- [ ] 交易策略：有需要時再建
