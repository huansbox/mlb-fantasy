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
- **BB 結構性偏低**（2026-04-09 觀察，Week 1-3 排 5th/10th/8th）：OPS 穩定前 2-4 但 BB 中後段，Tovar/Chisholm BB% 極低拉低整隊。同等條件優先高 BB% 打者
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

由自動化腳本從 `roster_config.json` + 即時數據動態計算（見 `fa_scan.py` 輸出）。
包含位置深度（零替補位置）和球員表現急迫性。

> FA 觀察 + 隊上球員追蹤見 `waiver-log.md`（觀察中 / 隊上觀察 / 已結案）。
> 「隊上觀察」記錄數據看不出的脈絡：傷勢追蹤、角色變化、限局跡象等。

## 球員評估框架

> 唯一定義。Skills（/player-eval、/waiver-scan）引用此處，不複製。

### 通用規則

- 所有指標參照百分位表（2025 MLB 數據），差距 ≥ 10 百分位點 = 有意義
- 取當季 + 前一年數據對照，附樣本量（PA / BBE / IP）
- **賽季數據加權**（投打通用，BBE 為準）：
  - 當季為主要評估依據，前一年為輔助脈絡
  - BBE 標示信心水準：BBE < 30 = 低信心（樣本噪音大）、30-50 = 中等、> 50 = 高信心

  **加分側（add / hold / breakout 偵測）**：
  - 當季高 + 前一年高 → 值得行動（品質確認）
  - 當季高 + 前一年低 → 觀察，breakout 候選（待樣本驗證）
  - 當季高 + 前一年無數據 → 觀察，新人待驗證

  **減分側（cut / drop / sell-high）**：
  - 當季低 + 前一年低 → **結構性確認**（高信心 cut/sell 候選）
  - 當季低 + 前一年高 → **slump 候選**（不急 cut，等樣本回歸）
  - 當季 Savant 高（上修）+ 前一年低 + Trad 差 → **BABIP 噪音**（不算 cut，反而是 buy-low）
  - 當季 Trad 高 + 當季 Savant 低 → **賣高窗口**（trade value 最大化但結構不佳）

  - 設計取向：寧可早期抓到 breakout 再驗證，不要等穩定後被搶走；
    cut 寧可雙年雙確認後再動，不要單年噪音就誤殺
- **「最弱 N 人」清單** = FA/交易候選的比較**錨點**，**不是 cut 候選清單**
  - Cut 候選需通過「賽季數據加權」減分側檢核（雙年雙重確認弱）
  - 「最弱」可能是當季噪音、可能是 slump、可能是真結構性弱 — 三種處理方式不同
- 「不動也是策略」— FA 未明顯優於現有球員 → 不換
- 轉隊確認：球員目前球隊 = 數據球隊？不符就重新評估
- 12 隊聯賽 xwOBA > P90 的 FA 基本不存在 → 出現代表 drop 失誤

### 打者評估

**評估流程**（FA/交易比較用）：
1. 品質 + 產量指標排序全隊打者 → 產出「最弱 5 人」（不看守位）
2. FA/交易候選只跟這 5 人比較 → 這步加入脈絡

**Cut 評估流程**（drop 決策用，與「最弱 5 人」分開）：
1. 排最弱清單（同上 Step 1）
2. 對最弱清單**逐人做雙年檢核**（套用「賽季數據加權」減分側矩陣）：
   - 雙年雙確認弱 → 真結構性 cut 候選
   - 單年弱（另一年強或無數據）→ 不 cut，標記為觀察
3. 通過檢核者，再加角色脈絡：
   - **Active starter** cut → 高 urgency（active 出賽即時拖累 stats，流血傷口）
   - **Backup / BN-only** cut → 低 urgency（占位但每週 stats 影響 ~0，死重，等好替代再做）

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

**評估流程**（FA/交易比較用）：同打者邏輯，排出隊上最弱 4 位 SP → FA 只跟最弱的比

**Cut 評估流程**（drop 決策用）：同打者「Cut 評估流程」邏輯：
1. 排最弱 4 SP
2. 雙年檢核（套用「賽季數據加權」減分側矩陣）— 雙年雙確認弱才算結構性 cut 候選
3. 角色脈絡：active 輪值 SP cut = 高 urgency（每場拖比率），BN/IL stash SP cut = 低 urgency

**核心 3 指標**（品質，2 項勝出 = 值得行動）：
- **xERA** — 取代 ERA，排除 BABIP/運氣噪音
- **xwOBA allowed** — 被打品質總指標
- **HH% allowed** — 核心（ERA/WHIP 受所有硬接觸影響，比 Barrel% 更廣）

**產量指標**：
- **IP/GS** — 每次先發平均局數，涵蓋 IP/QS/W 產量天花板

**輔助指標**：
- Barrel% allowed（確認 HR 被打風險）
- ERA（計分類別直接影響）
- xERA-ERA 運氣標記（正=運氣好小心，負=運氣差撿便宜，百分位判斷絕對值幅度，P70+ = 顯著）：
  - +1.52：xERA 3.52 / ERA 2.00 → 運氣好，ERA 預期回升
  - -1.50：xERA 3.50 / ERA 5.00 → 運氣差，撿便宜訊號

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
**輔助**：Barrel% allowed、ERA、xERA-ERA 運氣標記（同 SP：正=運氣好會回升，負=運氣差可撿便宜）
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

| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | xERA-ERA |
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

| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | K/9 | IP/Team_G | xERA-ERA |
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
| 12:30 | FA Scan 報告產出 | 自動推送（Batter + SP） |
| 15:15 | %owned 快照 + watchlist 清理 | 自動（--snapshot-only） |
| 22:15 | 收速報 → 設隔日 lineup → 睡覺 | 自動推送 |
| 05:00 | 最終報產出 | 自動推送（睡眠中） |
| 07:00 | 起床看最終報 + FA Scan → 微調（如需要） | 兩份一起看 |

### 每週（週一）

| 順序 | 做什麼 | 說明 |
|------|--------|------|
| 1 | FA Scan 報告已在 12:30 自動產出（含打者 + SP） | 自動推送 |
| 2 | FA Scan --rp（12:45 自動，週一限定） | 自動推送 |
| 3 | `/weekly-review`：覆盤上週 + 預測本週 | 手動 session |
| 4 | 按需：`/player-eval` 或 `/waiver-scan` | 手動 session |

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

daily_advisor.py（每日戰報）
  ├─ 速報（TW 22:15）：隔日 lineup 建議 + H2H 態勢 + SP matchup
  ├─ 最終報（TW 05:00，--morning）：確認 lineup + 比率更新
  └─ 輸出：Telegram 推送 + GitHub Issue 存檔

fa_scan.py（FA 市場分析唯一入口）
  ├─ 每日：Batter + SP 兩階段 Claude（Pass 1 挑最弱 + Pass 2 比較）
  ├─ 週一：--rp 模式（RP 獨立掃描）
  ├─ 每日 TW 15:15：--snapshot-only（%owned 快照 + watchlist 清理）
  ├─ 被讀取：weekly_review.py（scan_summary）
  └─ 被更新：waiver-log.md（觀察中球員追蹤）

roster_config.json（陣容唯一來源）
  ├─ 球員名 / mlb_id / yahoo_player_key / positions / team / prior_stats
  ├─ selected_pos（Yahoo 格位：IL/IL+/BN/NA/位置）/ status（MLB 狀態：IL10/IL60/DTD/NA/空=健康）
  ├─ 被讀取：daily_advisor.py / fa_scan.py / roster_stats.py / weekly_review.py
  └─ 被更新：roster_sync.py（cron TW 15:10，偵測 add/drop + 更新狀態 → auto sync + git push）

waiver-log.md（球員追蹤唯一來源）
  ├─ 觀察中（FA）/ 隊上觀察（自家球員非數據脈絡）/ 已結案
  ├─ 被讀取：fa_scan.py / skills
  └─ 被更新：/player-eval / /waiver-scan skill / 傷病事件時手動

資料流：MLB Stats API + Yahoo Fantasy API + Baseball Savant CSV
  → Python 腳本組裝 → claude -p 分析 → Telegram 推送 + GitHub Issue 存檔
```

### 檔案索引

| 文件 | 用途 |
|------|------|
| `daily-advisor/daily_advisor.py` | 每日戰報（速報 TW 22:15 + 最終報 TW 05:00） |
| `daily-advisor/fa_scan.py` | FA 市場分析唯一入口（每日 Batter+SP / 週一 RP / snapshot-only） |
| `daily-advisor/roster_config.json` | 陣容唯一來源（球員名單 + ID + 位置 + 去年數據 + Yahoo 格位 + MLB 狀態） |
| `waiver-log.md` | 球員追蹤（FA 觀察中 / 隊上觀察 / 已結案） |
| `week-reviews.md` | 累積式週覆盤記錄 |
| `league-scouting.md` | 聯賽 12 隊 GM 策略分析 |
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |
| `daily-advisor/calc_percentiles_2026.py` | 百分位分布計算工具（Week 6-8 更新 2026 百分位表時使用） |
| `daily-advisor/_trade_lookup.py` | 聯盟 roster 掃描（隊伍查詢 / 守位覆蓋 / 位置過剩掃描 / 球員 7-cat 比較） |

## 待辦

- [ ] **preview 加入對手近期異動**：從 Yahoo API league transactions 過濾對手 add/drop，判斷對手 build 策略（囤 SP / 串流 / 正常）
- [ ] **preview 加入聯盟 scoreboard**：用 `yahoo_query.py scoreboard` 邏輯存入 JSON，預測時有數據基礎
- [ ] **roster_sync --init 不 backfill 新欄位**：當沒有 add/drop 也沒有 key/stats 缺失時，`run_init` 提前 return，不走 `update_config()`，導致 `selected_pos`/`status` 等新欄位不會被寫入。日常 cron 有異動時正常 backfill，僅手動 `--init` 無異動時觸發
- [ ] **被 drop 球員的週累計問題**：`calc_weekly_ip` 用現有陣容遍歷 game log，被 drop 的球員貢獻被遺漏。速報 IP 已改用 Yahoo scoreboard 值。檢查其他地方是否有類似問題（weekly_review 等）
- [ ] Week 4-5（~04-14）：回顧新指標框架（feedback_metrics_framework_observations.md 的 3 個觀察點）
- [ ] Week 6-8：更新百分位表為 2026 賽季數據（CLAUDE.md + daily_advisor.py + prompt 檔，腳本 `calc_percentiles_2026.py` 已備好）
- [ ] **交易掃描工具**：類似 fa_scan 的聯盟交易機會掃描。掃描 12 隊 roster 的守位深度 + 7-cat 傳統數據，找出「我方過剩 vs 對方過剩」的 win-win 交易對象。工具基礎已建好：`daily-advisor/_trade_lookup.py`（聯盟 roster 查詢 + 守位覆蓋 + 球員 7-cat 比較）
- [ ] **追蹤 Carlos Rodón IL 狀況**（992330 潛在 Albies 1:1 買低目標）：確認 IL 類型 + 預計回歸時間，判斷折價窗口是否存在。詳見 `league-scouting.md` 992330 交易候選區段
