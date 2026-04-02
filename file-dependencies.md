# 檔案依賴關係地圖

> 目的：釐清各檔案的同步關係與斷裂點，規劃整合方案。
> 建立於 2026-04-02，Phase 1（逐檔盤點）完成。

---

## Phase 1：CLAUDE.md 逐區段盤點結果

### 保留的區段

| # | 區段 | 決定 | 備註 |
|---|------|------|------|
| 1 | 專案概述 | 保留原樣 | |
| 2 | 聯賽設定 | 保留，移除「vs 選秀前變更」表 | 整季不變 |
| 4 | 執行中策略 | 保留，不綁球員名 | 串流 SP 改中性描述 |
| 5 | 串流 SP 決策規則 | 保留原樣 | |
| 6 | Waiver 操作規則 | 保留，加 FAAB 餘額 | |

### 改造的區段

| # | 區段 | 決定 | 新內容 |
|---|------|------|--------|
| 3 | 現役陣容 | 瘦身 | 核心 3 人（Skubal/Chisholm/Machado）+ 連結 roster_config.json |
| 7 | 陣容風險 | 改為指引 | 由自動化腳本動態計算（config + 即時數據），不寫死 |
| 14+15 | 文件結構 + 每週 SOP | 合併為「賽季運營 SOP」 | 每日/每週/低頻/事件觸發 + 檔案索引 |
| 15 | 評估框架 | 統一為打者/SP/RP 三段 | 唯一定義，skills 引用 |

### 移除的區段

| # | 區段 | 原因 | 去處 |
|---|------|------|------|
| 8 | Week 1 複盤 | 歷史快照 | `week-reviews.md` |
| 9 | Watchlist | 與 waiver-log.md 重複 | `waiver-log.md` |
| 10 | 行動觸發規則 | 與 Watchlist 配套 | `waiver-log.md` |
| 11 | 格式狀態 + 7×7 特性 | 選秀分析 | `7x7-選秀分析.md` |
| 12 | 核心分析框架 + 分析結論 | 選秀分析 | `7x7-選秀分析.md` |
| 13 | 45 秒速查決策規則 | 被 #15 篩選框架涵蓋 | 合併到 #15 |
| 16 | 選秀日工具 + 數據來源 | 選秀期產物 | repo 內保留，CLAUDE.md 不引用 |

### CLAUDE.md 改造後的目標結構

```
1. 專案概述
2. 聯賽設定（移除 vs 選秀前變更表）
3. 核心球員（3 人 + 連結 roster_config.json）
4. 執行中策略（不綁球員名）
5. 串流 SP 決策規則
6. Waiver 操作規則（加 FAAB 餘額）
7. 陣容風險（指引到動態計算）
8. 球員評估框架（打者 / SP / RP，唯一定義）
9. 賽季運營 SOP（每日/每週/低頻/事件觸發 + 檔案索引）
```

---

## 球員評估框架（統一定義，skills 引用）

> 整合自 CLAUDE.md #15、player-eval skill、waiver-scan skill。
> CLAUDE.md 為唯一定義，skills 引用不複製。

### 通用規則

- 所有指標參照百分位表（2025 MLB 數據），差距 ≥ 10 百分位點 = 有意義
- 取當季 + 前一年數據對照，附樣本量（PA / BBE / IP）
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

**樣本量加權**：
- 當季 PA < 50 / BBE < 30 → 前一年為主
- 上季 < 80 場 → 查 career stats

**7×7 格式規則**：
- 無 K → 高 K 打者無懲罰
- Punt SB → 速度價值打折但非零
- 不使用 hot/cold streaks、BvP 歷史對戰

**陣容脈絡**（Step 2）：
- 守位需求、單點故障、邊際遞減、BN 限制（3 格）

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
- ERA（計分類別）
- |xERA - ERA| 差距用百分位判斷，差距大 = 回歸風險

**樣本量加權**：
- 當季 BBE < 30 / IP < 15 → 前一年為主
- 上季 < 80 IP → 用預期值區間

**7×7 格式規則**：
- IP 是獨立類別 → 局數怪物 > 精品短局型
- QS 需 6+ IP → IP/GS 低的投手 QS 打折
- W 受球隊影響 → 強隊 SP 有 W 加成
- 串流 SP：下週有 2 先發 + 對戰後段打線，不看全季指標

### RP 評估

**策略前提**：Punt SV+H（不主動追），但 RP 仍貢獻 ERA/WHIP/K。

**評估流程**：只有 2 人，不排最弱清單。FA 有無優於目前 2 位 RP → 有就換。

**品質指標**：xERA、xwOBA allowed、HH% allowed（同 SP）
**輔助**：Barrel% allowed、ERA、|xERA - ERA| 百分位
**產量**：K/9、IP / Team_G、SV+H（留意但不追）

注意：RP 百分位分布和 SP 不同，需分開計算。

---

## roster_config.json 目標 schema

### 球員欄位（投打統一結構）

| 欄位 | 狀態 | 來源 | 說明 |
|------|------|------|------|
| `name` | 保留 | Yahoo API 自動 | |
| `mlb_id` | 保留 | 同步腳本自動查（MLB API search） | Statcast 查詢必要，查不到標記 null |
| `yahoo_player_key` | **新增** | Yahoo API 自動 | 精確比對，避免名字問題 |
| `team` | 保留 | Yahoo API 自動 | |
| `positions` | **投打統一** | Yahoo API `display_position` | 打者：`["2B","3B"]`，投手：`["SP"]` |
| `prior_stats` | **新增** | 去年數據，一次寫入 | 具體欄位見下方 |
| `type` | **移除** | — | 從 positions 推導 |
| `role` | **移除** | — | 從 API `selected_position` 即時取得 |
| `proj` | **移除** | — | Steamer 預測，in-season 無用 |

### prior_stats 具體欄位（待確認）

打者：
- xwOBA、BB%、Barrel%、HH%、OPS、PA/Team_G
- PA、G（樣本量參考）

投手（SP）：
- xERA、xwOBA allowed、HH% allowed、Barrel% allowed、ERA
- IP/GS、IP（全季）
- BBE（樣本量參考）

投手（RP）：
- 同 SP + K/9、IP/Team_G

### league 區段

- 維持現有（整季不變）
- 加 `faab_remaining`（手動更新，之後試 API 自動化）

### 維護方式

- **自動化為主**：同步腳本（roster_sync.py）從 Yahoo API 拉即時陣容
- 新球員自動查 mlb_id（MLB API people/search），查不到標記 null
- prior_stats 在球員首次加入時寫入，之後不更新
- 偶爾手動確認

---

## 陣容風險（動態計算）

- CLAUDE.md 不寫死，改為指引
- 由 fa_watch.py / weekly_scan.py 在每次執行時動態計算：
  - **結構面**：從 config 的 positions 算位置深度（零替補位置）
  - **表現面**：從即時 API/Savant 數據判斷急迫性（弱但無替代 vs 弱但不急）
- 產出風險摘要餵給 Claude，取代寫死的 prompt 弱點描述

---

## 賽季運營 SOP（草稿）

### 每日

| 時間 (TW) | 做什麼 | 自動/手動 | 相關檔案 |
|-----------|--------|----------|----------|
| 22:15 | 收速報 → 設隔日 lineup | 自動推送 | `main.py` |
| 05:00 | 收最終報 → 確認/微調 lineup | 自動推送 | `main.py` |
| 07:00 | 看 FA Watch → 有異常才行動 | 自動推送 | `fa_watch.py` |

### 每週（週一）

| 順序 | 做什麼 | 自動/手動 | 相關檔案 |
|------|--------|----------|----------|
| 1 | 收 Weekly Scan 報告（19:30 自動） | 自動推送 | `weekly_scan.py` |
| 2 | `/weekly-review`：覆盤上週 + 預測本週 | 手動 session | `weekly_review.py`, `week-reviews.md` |
| 3 | 按需：`/player-eval` 或 `/waiver-scan` | 手動 session | skill |

### 週中決策點

| 時間 | 做什麼 |
|------|--------|
| 週四 | 檢查 IP 進度（速報會提醒），不夠才考慮串流 |
| 任何時候 | waiver-log.md 觸發條件達成 → 執行行動 |

### 低頻（2-3 週一次）

| 做什麼 | 條件 | 相關檔案 |
|--------|------|----------|
| `/roster-scan` 陣容健檢 | 30+ PA 累積後 | `roster-baseline.md` |
| 聯賽偵察更新 | 對手有大幅異動時 | `league-scouting.md` |

### 事件觸發

| 事件 | 動作 | 相關檔案 |
|------|------|----------|
| Add/Drop | 跑同步腳本更新 config → push → VPS pull | `roster_config.json` |
| FAAB 出價 | 更新 config 的 faab_remaining | `roster_config.json` |
| Watchlist 觸發 | `/player-eval` 深入評估 → 決定行動 | `waiver-log.md` |

### 檔案索引

| 文件 | 用途 |
|------|------|
| `daily-advisor/roster_config.json` | 陣容唯一來源（球員名單 + ID + 位置） |
| `waiver-log.md` | FA 觀察追蹤（觀察中 / 條件 Pass / 已結案） |
| `roster-baseline.md` | 陣容基準卡（全員數據，eval 比較用） |
| `week-reviews.md` | 累積式週覆盤記錄 |
| `league-scouting.md` | 聯賽 12 隊 GM 策略分析 |
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |

---

## 待計算的新百分位表

從 2025 MLB 全季數據計算：

| 指標 | 對象 | 用途 |
|------|------|------|
| PA / Team_G | 打者 | 產量指標 |
| IP / GS | SP | 產量指標 |
| K/9 | RP（和 SP 分開） | RP 產量指標 |
| IP / Team_G | RP | RP 上場頻率 |
| \|xERA - ERA\| | SP 和 RP 分開 | 運氣標記 |

---

## 下游檔案同步問題（原路徑分析）

### 路徑 2：陣容弱點 → prompt_fa_watch.txt

- 現狀：第 4 行寫死「Kwan 最弱」→ 已過時
- 決定：不再寫死弱點。由 fa_watch.py 動態計算位置深度 + 即時數據產出風險摘要

### 路徑 3：弱點位置查詢 → DAILY_QUERIES 硬編碼

- 現狀：固定查 CF/SP/1B，漏掉 C/SS
- 決定：改為從 config 動態計算零替補位置，自動產生查詢清單

### 路徑 4：聯賽規則 + 策略 → 4 個 prompt 檔

- 現狀：同步
- 決定：維持（整季不變）

### 路徑 5：百分位表 → prompt 檔 + main.py

- 現狀：同步
- 決定：CLAUDE.md 為唯一定義，prompt 檔和 main.py 引用
- 新增百分位表（PA/Team_G、IP/GS、K/9、|xERA-ERA|）時需同步到 main.py

### 路徑 6：Watchlist → waiver-log.md

- 現狀：CLAUDE.md Watchlist 移除，waiver-log.md 為唯一來源
- 決定：skills 不再同步 CLAUDE.md watchlist，只更新 waiver-log.md

---

## 待執行變更總表

### CLAUDE.md

- [ ] 移除「vs 選秀前變更」表（#2）
- [ ] 陣容改為核心 3 人 + 連結 config（#3）
- [ ] 執行中策略不綁球員名，串流 SP 改中性描述（#4）
- [ ] Waiver 規則加 FAAB 餘額（#6）
- [ ] 陣容風險改為指引到動態計算（#7）
- [ ] 移除 Week 1 複盤（#8）
- [ ] 移除 Watchlist（#9）→ 指引到 waiver-log.md
- [ ] 移除行動觸發規則（#10）→ 合併到 waiver-log.md
- [ ] 移除格式狀態 + 7×7 特性（#11）
- [ ] 移除核心分析框架 + 分析結論（#12）
- [ ] 移除 45 秒速查決策規則（#13）
- [ ] 移除選秀日工具 + 數據來源（#16）
- [ ] 篩選框架統一為打者/SP/RP 三段（#15）
- [ ] 文件結構 + SOP 合併為賽季運營 SOP（#14+#15）

### roster_config.json

- [ ] 移除 Kwan、Littell
- [ ] 新增 Walker(STL)、Messick
- [ ] 移除 `role`、`type`、`proj` 欄位
- [ ] 新增 `yahoo_player_key` 欄位
- [ ] 新增 `prior_stats` 欄位（去年數據）
- [ ] 投打統一用 `positions`
- [ ] league 加 `faab_remaining`

### 新腳本（roster_sync.py）

- [ ] 從 Yahoo API 拉即時陣容更新 config
- [ ] 新球員自動查 mlb_id
- [ ] prior_stats 在球員首次加入時寫入

### 程式碼修改

- [ ] fa_watch.py：DAILY_QUERIES 改為動態計算零替補位置
- [ ] fa_watch.py：build_fa_watch_data() 動態產出位置深度 + 風險摘要
- [ ] weekly_scan.py：同上
- [ ] prompt_fa_watch.txt：移除寫死的弱點描述（第 4 行）
- [ ] 各腳本移除 `role` 依賴
- [ ] main.py / prompt 檔：新增百分位表（PA/Team_G、IP/GS 等）

### Skills

- [ ] player-eval：評估標準改為引用 CLAUDE.md（不複製）
- [ ] waiver-scan：同上 + 移除同步 CLAUDE.md watchlist 的指引
- [ ] roster-scan：加指引讀 roster_config.json
