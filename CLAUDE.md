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
- **SP 重裝**：10 SP 深度（含 Kelly IL 歸隊中 + López SUSP），40 IP 門檻輕鬆過
- **BN 配置**：1 打者（Albies/Jazz 輪替）+ 2 SP（López SUSP + 機動）。打者深度換投手產量（2026-04-12 確立，Week 2-3 IP 倒數第 3 驅動）
- **目標**：每週穩拿 R/HR/RBI/BB/AVG/OPS + IP/W/K/QS/ERA/WHIP 共 12 項中的 8+
- **BB 結構性偏低**（2026-04-09 觀察，Week 1-3 排 5th/10th/8th）：OPS 穩定前 2-4 但 BB 中後段，Tovar/Chisholm BB% 極低拉低整隊。同等條件優先高 BB% 打者
- **串流 SP**：預設不串流，具體依下方決策規則判斷（FA 池品質、對手強弱、比率餘裕）

### 進行中補強行動

> 每週 weekly-review Phase 1C 更新狀態。已驗證/失敗 2 週後移除（git log 留痕）。新項目觸發即加入。

**Nola drop 候選觀察**（啟動 2026-04-20，04-23 降級為 hold）
- 原觸發：2026 Sum 11 + 2025 Sum 15 + 速度 90.7 mph = 2025 災難年水準
- 04-23 三視角重評修正：
  - 2025 Sum 15 實為 P45-50 中段，非「結構性確認」要求的雙年雙低
  - 純 counting 類別 Nola 5 GS 略勝 Meyer（IP 26.2 / K 29 / QS 2 vs 25.0/28/0）
  - xERA 真實差距 Meyer 4.39 vs Nola 4.70 僅 0.31，20 週會被樣本噪音淹沒
- Meyer add 從 "slam dunk" 降級為 "邊際升級"：ERA/WHIP 小贏，QS/W/IP/K 略輸
- **hold → cut 條件**（下 2 場任一）：速度仍 ≤91 mph + xwOBA 季線 >.340 + 連 2 場 <5 IP 或 3+ ER
- **hold → continue 條件**（下 2 場任一）：速度回升 92+ mph / xwOBA <.320 / 新增 1+ QS
- 窗口風險：Meyer 18% owned 3d+5 可能被搶，但 MIA 弱隊 + 0 QS 降低聯盟搶人意願
- 候選池（保留備查）：Meyer (MIA) 首選 / Griffin (WSH) 備案（運氣 +1.04 ERA 會回升）/ Pfaadt (AZ) 等 K 起來
- 狀態：hold 2 場觀察，~05-01 前重評

**Ragans Slump 觀察**（啟動 2026-04-20 下午，先前定位修正）
- 觸發：2026 Sum 16（xERA 5.18 / xwOBA .358 / HH% 34.1% >P90）+ 2025 Sum 27（2.67 / .256 / 39.4%）
- 判定：「當季低 + 前一年高 → Slump 候選」（2025 菁英底，2025 xERA 2.67 >P90）
- 運氣 -0.82 運氣差，實際水準 ~P40-50，不是 ERA 6.00 這麼爛
- 行動：**不急 cut**，按框架等樣本回歸
- H2H 短期止血：當週拖比率嚴重時可排 BN（非 drop）
- 風險：drop 後回歸菁英 = 賣低吐血
- 狀態：觀察中，不條件式 drop

> **已驗證（2 週後清理）**：
> - BB 結構性補強（Grisham，04-09）✅ Week 4 BB 單週 #2 / 2 週合併 #4 ⬆️
> - IP 結構性補強（BN 改 1bat+2SP + Detmers，04-12）✅ Week 4 IP 單週 #5 / 2 週合併 #8 ⬆️
> - Whitlock 軟 cut（04-13）✅ 已 drop，Kelly 在 BN

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
- **FAAB 餘額**：$100（2026-04-12 更新，Detmers $0 取得）
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

**兩步分工**（fa_scan 機械化處理主流，特殊情況手動處理）：
- **Step 1**（Pass 1）：挑最弱 4 人作為 FA 比較錨點（Sum 分數排序）
- **Step 2**（Pass 2）：最弱 4 人內部 urgency 排序，決定 drop 優先序（P1 最該 drop）

**核心 3 指標**（Step 1 Sum 用，2 項勝出 = 值得行動）：
- **xwOBA** — 打擊品質總指標，取代 AVG
- **BB%** — 最高效指標（BB 欄 + OPS 的 OBP 端，7×7 雙重計算）
- **Barrel%** — HR 最佳預測指標，7×7 無 K 懲罰下 power 是核心價值

**產量指標**（Step 2 urgency 用）：
- **PA / Team_G** — drop 觀點的拖累放大器（越主力 urgency 越高）

**輔助指標**（警示/附註）：
- HH%（Barrel% 上層接觸品質）
- OPS（計分類別直接影響）
- K%（14d 激升 = 傷勢警訊，daily sit/start 用）

#### Step 1 — 挑最弱 4 人（Sum 排序）

對全隊打者用 3 核心指標打分 → 按 Sum 升冪排序取最弱 4 人。

**打分表**：

| 百分位 | 分數 |
|--------|------|
| >P90 | 10 |
| P80-90 | 9 |
| P70-80 | 8 |
| P60-70 | 7 |
| P50-60 | 6 |
| P40-50 | 5 |
| P25-40 | 3 |
| <P25 | 1 |

Sum 範圍 3-30。BBE <40 標 confidence='低'（識別小樣本，不影響 Sum）。

#### Step 2 — urgency 排序（最弱 4 人內部）

四因子加總 urgency 分數，降冪排序得 drop 優先序（P1 最該 drop）。

| 因子 | 條件 | 分數 |
|------|------|------|
| **2026 Sum** | <9 | +5 |
|  | 9-11 | +4 |
|  | 12-14 | +3 |
|  | 15-17 | +2 |
|  | 18-21 | +1 |
| **2025 Sum**（雙年檢核）| **≥24** | **Slump hold**（移出 drop 排序）|
|  | 22-23 | +0（灰色帶，給機會）|
|  | 18-21 | +1 |
|  | <18 | +2 |
| **14d 近況**（BBE ≥25 才啟用）| Δ ≥ +0.050（🔥強回升）| -2 |
|  | +0.035 ≤ Δ < +0.050（🔥弱回升）| -1 |
|  | -0.035 < Δ < +0.035（持平）| 0 |
|  | -0.050 < Δ ≤ -0.035（❄️弱下滑）| +1 |
|  | Δ ≤ -0.050（❄️強下滑）| +2 |
| **2026 PA/Team_G** | ≥3.5 | +2 |
|  | 3.0-3.5 | +1 |
|  | 2.5-3.0 | +0 |
|  | <2.5 | +0 |

Δ = 14d xwOBA - season xwOBA（絕對差值）。14d 資料缺值時該因子算 0，不影響其他因子。

**Slump hold 特例**：2025 Sum ≥24 獨立標註「菁英底，slump 候選」，不參與 urgency 排序。14d 🔥 附註「回升中」強化 hold 信心。

#### FA 勝出門檻（add/drop 決策）

- **Sum 差 ≥ 3 分**（整體明顯勝）
- **且**至少 2 項指標正向（每項 ≥ 0），避免單項爆表誤判
- `+5 +1 -3 = +3` **不算勝出**（一項大輸）
- `+1 +1 +1 = +3` 算勝出（三項都贏）
- `+2 +2 -1 = +3` 算勝出（兩項明顯勝）

#### PA/Team_G 方向說明

- **Drop 觀點**（最弱 4 人 urgency）：PA/TG 越高 = 每天拖累 stats 越多 = urgency 越高（主力弱是流血傷口）
- **Add 觀點**（FA 候選評估）：PA/TG ≥3.5 → ✅ 球隊主力（信心提升）；PA/TG <2.5 → ⚠️ 上場有限（強警示，球隊不愛數據轉不成累積）
- 兩方向相反，因意義不同：drop 看「每天傷害」，add 看「能否輸出」

#### fa_scan 不做的事（手動處理）

守位判斷 / Active 或 BN 角色脈絡 / 單點故障 / 邊際遞減 / 陣容需求
→ 特殊情況由 /player-eval 或 /weekly-review 手動判斷

#### 7×7 格式規則

- 無 K 類別 → 高 K 打者無懲罰
- Punt SB → 速度價值打折，但非零
- 不使用 hot/cold streaks（零預測力）
- 不使用 BvP 歷史對戰（樣本太小）

#### 樣本量加權

BBE 標示信心：BBE <30 低（樣本噪音大）/ 30-50 中 / >50 高。低信心標記但不排除判斷。

### SP 評估

**兩步分工**（對齊打者 v2 框架）：
- **Step 1**（Pass 1）：挑最弱 4 人作為 FA 比較錨點（Sum 分數排序，BBE <30 移出）
- **Step 2**（Pass 2）：最弱 4 人內部 urgency 排序，決定 drop 優先序（P1 最該 drop）

**核心 3 指標**（Step 1 Sum 用，反向打分：數值越低越好 → 分數越高）：
- **xERA** — 取代 ERA，排除 BABIP/運氣噪音
- **xwOBA allowed** — 被打品質總指標
- **HH% allowed** — 核心（ERA/WHIP 受所有硬接觸影響，比 Barrel% 更廣）

**產量指標**（Step 2 urgency 用）：
- **IP/Team_G** — drop 觀點拖累放大器（active 輪值越多每場越拖比率）

**輔助指標**（警示/附註）：
- **IP/GS** — QS/IP 產量天花板（Step 2 task B ✅/⚠️ 標籤用）
- Barrel% allowed（HR 被打風險）
- ERA（計分類別直接影響）
- xERA-ERA 運氣標記（P70+ 絕對值 ≥0.81 顯著）：
  - +1.52：xERA 3.52 / ERA 2.00 → 運氣好，ERA 預期回升
  - -1.50：xERA 3.50 / ERA 5.00 → 運氣差，撿便宜訊號

#### Step 1 — 挑最弱 4 人（Sum 排序）

對隊上 SP（排除 cant_cut + IL/NA）用 3 核心指標**反向**打分 → 按 Sum 升冪排序取最弱 4 人。

**打分表**（SP 反向：百分位越高 = 越菁英 = 分數越高）：

| 百分位 | 分數 |
|--------|------|
| >P90 | 10 |
| P80-90 | 9 |
| P70-80 | 8 |
| P60-70 | 7 |
| P50-60 | 6 |
| P40-50 | 5 |
| P25-40 | 3 |
| <P25 | 1 |

Sum 範圍 3-30。BBE <30 標 confidence='低' 並**移出排序**（放 `low_confidence_excluded`，驗證期噪音大）。

#### Step 2 — urgency 排序（最弱 4 人內部）

四因子加總 urgency 分數，降冪排序得 drop 優先序（P1 最該 drop）。

| 因子 | 條件 | 分數 |
|------|------|------|
| **2026 Sum** | <9 / 9-11 / 12-14 / 15-17 / 18-21 | +5/+4/+3/+2/+1 |
| **2025 Sum**（雙年檢核，需 2025 IP ≥50）| **≥24 且 IP ≥50** | **Slump hold**（移出排序）|
|  | ≥24 但 IP <50 | +0（菁英但低樣本，附註）|
|  | 22-23 | +0（灰色帶）|
|  | 18-21 | +1 |
|  | <18 | +2（結構性確認）|
| **21d 近況**（Δ xwOBA allowed，21d BBE ≥20 才啟用）| Δ ≤ -0.050（🔥強回升）| **-2** |
|  | -0.050 < Δ ≤ -0.035（🔥弱回升）| **-1** |
|  | -0.035 < Δ < +0.035（持平）| 0 |
|  | +0.035 ≤ Δ < +0.050（❄️弱劣化）| **+1** |
|  | Δ ≥ +0.050（❄️強劣化）| **+2** |
| **2026 IP/Team_G** | ≥1.0（active 輪值）| +2 |
|  | 0.5-1.0（部分 active/swingman）| +1 |
|  | <0.5（IL/stash）| 0 |

**Slump hold 特例**：2025 Sum ≥24 **且** 2025 IP ≥50 獨立標註「菁英底，slump 候選」，不參與 urgency 排序。Ragans 2025 Sum 27 / 62 IP 是典型例子。

**21d Δ 用 xwOBA 不用 xERA**：Savant xERA 為專有模型無法本地重算；xwOBA 是 xERA 的前驅指標，方向一致。門檻 ±0.035/±0.050 沿用 batter 14d（Phase 2 後 2 週收集 SP 21d 實測再校準，見待辦）。

#### FA 勝出門檻（Step 2 task B）

- **Sum 差 ≥ 3 分**（整體明顯勝）**且**至少 2 項指標正向（每項 ≥ 0）
- `+5 +1 -3 = +3` 不算勝出（一項大輸）
- `+1 +1 +1 = +3` 算勝出

**✅ Add 加分標籤**：
- **✅ 雙年菁英** — 2025 Sum ≥24 且 2025 IP ≥50
- **✅ 深投型** — IP/GS >5.7
- **✅ 球隊主力** — 2026 IP/Team_G ≥1.0
- **✅ 近況確認** — 21d Δ xwOBA ≤ -0.035
- **✅ 撿便宜運氣** — xERA-ERA ≤ -0.81（P70+）

**⚠️ Add 警示**：
- **⚠️ 短局**（強警示）— IP/GS <5.0
- **⚠️ 上場有限**（強警示）— 2026 IP/Team_G <0.5
- **⚠️ 樣本小**（強警示）— BBE <30 或 IP <20（信心不足以行動，否決升級）
- **⚠️ Breakout 待驗** — 2025 Sum <18 或無 prior
- **⚠️ 賣高運氣** — xERA-ERA ≥ +0.81（P70+）
- **⚠️ 近況下滑** — 21d Δ xwOBA ≥ +0.035

**升級判斷**：≥2 ✅ 無 ⚠️ = 立即取代；1 ✅ 無強警示 = 取代；其他 = 觀察。

#### IP/Team_G 方向說明

- **Drop 觀點**（任務 A）：IP/TG 越高 → urgency 越高（active 輪值每場拖比率）
- **Add 觀點**（任務 B）：IP/TG 越高 → 信心越高（球隊輪值固定 → 數據能累積）
- 兩方向相反，因意義不同：drop 看「每天傷害」，add 看「能否輸出」

#### fa_scan 不做的事（手動處理）

單點故障 / 邊際遞減 / 陣容需求 → 特殊情況由 /player-eval 或 /weekly-review 手動判斷。

#### 7×7 格式規則

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

SP v4 百分位（2025 MLB SP, GS/G > 0.5 且 GS ≥ 10，n=178。GB%/xwOBACON 需 BBE ≥ 50, n=115。Whiff% 需 pitch-arsenal 總球數 ≥ 500）— **P90 = 菁英方向**（reverse 指標如 BB/9 / xwOBACON 顯示低值）：

| 百分位 | IP/GS | Whiff% | BB/9 | GB% | xwOBACON |
|--------|:---:|:---:|:---:|:---:|:---:|
| P25 | 5.21 | 21.3% | 3.47 | 38.3% | .386 |
| P40 | 5.35 | 23.1% | 3.17 | 40.5% | .375 |
| P45 | 5.41 | 23.5% | 3.06 | 41.4% | .374 |
| **P50** | **5.46** | **24.0%** | **2.95** | **43.2%** | **.370** |
| P55 | 5.55 | 24.6% | 2.83 | 44.1% | .367 |
| P60 | 5.61 | 25.1% | 2.73 | 44.7% | .364 |
| P70 | 5.73 | 26.5% | 2.38 | 46.7% | .356 |
| P80 | 5.89 | 27.9% | 2.18 | 51.4% | .350 |
| P90 | 6.11 | 30.0% | 1.96 | 54.6% | .341 |

（腳本：`daily-advisor/calc_v4_percentiles.py`。Whiff% 用 pitch-arsenal-stats 按球種 pitches 加權平均。v4 框架 Sum 打分的 2025 分布基線。）

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
| 週四 | 查 IP 進度（`ssh VPS ... yahoo_query.py scoreboard`），不夠才考慮串流 |
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
  ├─ 每日：Batter + SP 並行 threading（Python compute + Claude 文字化）
  │   └─ fa_compute.py: pick_weakest / compute_urgency / compute_fa_tags (Layer 4)
  │   └─ Claude 只做 定性 reason + 邊界 case flag + 觀察中變化 (Layer 5)
  ├─ 週一：--rp 模式（RP 獨立掃描；仍保留 Claude Pass 1 單階段）
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

### 執行環境

- **所有腳本跑在 VPS**（`/opt/mlb-fantasy`），cron 自動排程 + 手動觸發皆在 VPS。本機只做開發與 git push
- **Yahoo API token 只存在 VPS**（`daily-advisor/yahoo_token.json`），本機無 — `yahoo_query.py` 本機直接跑會報 `Yahoo token not found`
- **本機取即時數據（scoreboard / matchup / 異動紀錄）**：
  ```bash
  ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && python3 yahoo_query.py <cmd>"
  ```
- **本機取歷史數據（daily report / fa_scan 存檔）**：
  ```bash
  gh issue view <N> -R huansbox/mlb-fantasy
  ```
- ⚠️ **不要 scp Yahoo token 回本機** — yahoo_query.py 會自動 refresh token，雙邊不同步會讓 VPS 原本 token 失效，cron 全斷
- VPS 連線資訊見 `~/.claude/projects/-Users-linshuhuan-mywork-mlb-fantasy/memory/reference_vps.md`

### 檔案索引

| 文件 | 用途 |
|------|------|
| `daily-advisor/daily_advisor.py` | 每日戰報（速報 TW 22:15 + 最終報 TW 05:00） |
| `daily-advisor/fa_scan.py` | FA 市場分析唯一入口（每日 Batter+SP 並行 / 週一 RP / snapshot-only） |
| `daily-advisor/fa_compute.py` | Python 機械計算層（Sum/urgency/✅⚠️ 標籤/升級判定，Phase 5） |
| `daily-advisor/tests/test_fa_compute.py` | fa_compute 單元測試（85 cases 覆蓋百分位分桶 + 四因子 + 標籤 + fixture 回歸） |
| `daily-advisor/savant_rolling.py` | 14d Savant rolling 抓取（cron TW 12:00，產出 `savant_rolling.json` 供 fa_scan + daily_advisor 讀取） |
| `daily-advisor/roster_config.json` | 陣容唯一來源（球員名單 + ID + 位置 + 去年數據 + Yahoo 格位 + MLB 狀態） |
| `waiver-log.md` | 球員追蹤（FA 觀察中 / 隊上觀察 / 已結案） |
| `week-reviews.md` | 累積式週覆盤記錄 |
| `league-scouting.md` | 聯賽 12 隊 GM 策略分析 |
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |
| `daily-advisor/calc_percentiles_2026.py` | 百分位分布計算工具（Week 6-8 更新 2026 百分位表時使用） |
| `daily-advisor/calc_v4_percentiles.py` | v4 框架 2025 SP 百分位計算（IP/GS / Whiff% / BB/9 / GB% / xwOBACON；n=178/115）|
| `daily-advisor/fa_scan_v4.py` | **v4 框架分析工具（parallel 於 fa_scan.py v2 production cron）— 隊上 SP + FA 候選 5-slot Sum 排序 + Rotation gate + 升級建議；stdout 不推送** |
| `daily-advisor/_trade_lookup.py` | 聯盟 roster 掃描（隊伍查詢 / 守位覆蓋 / 位置過剩掃描 / 球員 7-cat 比較） |
| `daily-advisor/_trade_batter_rank.py` | 交易打者排名掃描（目標打者 vs 11 隊全打者 wRC+ 排名，找交易候選隊伍） |
| `docs/fa_scan-python-compute-design.md` | Phase 5 重構 design + plan（架構參考，未來 fa_scan 大改時讀） |
| `docs/sp-framework-v4-balanced.md` | **SP 評估 v4 設計定稿（5-slot balanced Sum + Rotation gate pre-filter + 時間尺度分層）— 取代 v3，未實作前 v2 仍 live rules** |
| `docs/sp-framework-v3-weighted.md` | SP 評估 v3 設計（已被 v4 取代，保留作設計演進紀錄）|
| `docs/nola-lopez-holmes-triview-2026-04-23.md` | 三視角 Nola/López/Holmes drop 評估回測材料（2/3 視角反對 v3 判斷）|
| `docs/sp-decisions-backtest.md` | SP 決策 living log（9 筆歷史決策 + 元回測機制，每 2-4 週更新「後續走勢」）|

## 待辦

<!-- 已完成 2026-04-21 commit 3ce1eae：
- waiver-log auto-close mlb_id 驗證 — _check_player_ownership 加 expected_team
  參數交叉驗證 Yahoo editorial_team_abbr，同名同姓不會再誤關（Muncy LAD vs
  ATH 兩次誤關事件：afbe6ca / 39170c9 → 已根治）
-->
- [ ] **waiver-log 新進條目 mlb_id 正確性驗證**（進階，已根治 auto-close 端，但 NEW 入口仍可能寫錯 mlb_id）：`_update_waiver_log_locked` NEW 行走 `search_mlb_id(name)` 補 mlb_id，同名同姓仍可能取到第一個（錯的）。建議 NEW 時走 Yahoo API 交叉驗證 team / position 匹配
- [ ] **SP 21d Δ xwOBA 門檻校準**（2026-04-21 SP 框架 v2 上線，Phase 2 完成後 2 週）：目前沿用 batter 14d Δ 門檻 ±0.035/±0.050。等 savant_rolling pitcher 累積 2 週實測數據（隊上 10 SP + FA 池 SP）再按 P25/P50/P75 分布調整。batter 14d Δ 門檻 ±0.035/±0.050 是 2026-04-17 這樣實測來的，SP 依樣辦理。**v4 上線後改校準 21d Δ xwOBACON 門檻**
- [ ] **v4 框架上線前置（4 項，2026-04-24 設計完成後列出）**：
  - **v4 prior_stats backfill**：roster_config.json 加 2025 `whiff_pct` / `gb_pct` / `xwobacon` 欄位，供 `v4_add_tags_sp` 的「✅ 雙年菁英」tag 使用（目前只有 xera/xwoba/hh_pct）
  - **21d rolling xwOBACON fetch**：savant_rolling.py 目前只抓 xwOBA allowed，v4 時序訊號用 xwOBACON 要擴充（pitch-level CSV 聚合，排除 K/BB 只算 on-contact）
  - **v4 production cutover 決策**：目前 `fa_scan_v4.py` 是 parallel CLI 工具（stdout only），prod cron `fa_scan.py` 仍 v2。需 feature flag 環境變數 + VPS 部署 + 1-2 週並行驗證 + 最終清 v2 SP 代碼（batter 保留 v2）
  - **CLAUDE.md「SP 評估」章節改寫 v4**：目前章節仍 v2 規則，待 production cutover 時一起改寫
- [ ] **Luck tag BBE 小樣本 edge case**（2026-04-24 實戰發現）：Kelly xERA 13.4 / ERA 9.31 → diff +4.09 觸發「⚠️ 賣高運氣」但實際語意是「崩盤進行中」不是「運氣加持」。考慮加規則 BBE <40 禁用 luck tag，或 diff > +3 時改標「崩盤中」tag
- [ ] **Phase 5 minor refactor**（2026-04-21 Architect 審查 finding，不影響功能）：
  - finding C：`fa_scan.py:2161` Slump hold 訊息「≥50」寫死 → 改用 `_PRIOR_IP_SLUMP_HOLD_MIN` 常數
  - finding D：`fa_scan.py:683` `_calc_batter_sum`（Layer 2 filter）與 `fa_compute.py compute_sum_score` 雙重實作 batter Sum → 統一使用 fa_compute（要小心 input dict shape 略不同）
  - finding E：`fa_scan.py:1637` `_publish` 在 `--no-send` mode 用 `print(advice)` 沒 flush，threading + nohup 環境下 stdout buffered 看不到 advice → 加 `print(advice, flush=True)` 或改 `sys.stderr.write`
- [ ] **preview 加入對手近期異動**：從 Yahoo API league transactions 過濾對手 add/drop，判斷對手 build 策略（囤 SP / 串流 / 正常）
- [ ] **preview 加入聯盟 scoreboard**：用 `yahoo_query.py scoreboard` 邏輯存入 JSON，預測時有數據基礎
- [ ] **roster_sync --init 不 backfill 新欄位**：當沒有 add/drop 也沒有 key/stats 缺失時，`run_init` 提前 return，不走 `update_config()`，導致 `selected_pos`/`status` 等新欄位不會被寫入。日常 cron 有異動時正常 backfill，僅手動 `--init` 無異動時觸發
- [ ] Week 4-5（~04-14）：回顧新指標框架（feedback_metrics_framework_observations.md 的 3 個觀察點）
- [ ] Week 6-8：更新百分位表為 2026 賽季數據（CLAUDE.md + daily_advisor.py + prompt 檔，腳本 `calc_percentiles_2026.py` 已備好）
- [ ] **交易掃描工具**：`_trade_batter_rank.py` 已完成（wRC+ 排名掃描）。待擴充：SP 端掃描（目標 SP vs 對方隊 SP 排名）、自動交叉比對「我方打者在對方排 ≤8 + 對方 SP 品質 > Detmers」
- [ ] **追蹤 Liberatore drop 後表現**（驗證運氣回歸判斷）：是否被別隊撿走 + 接下來幾場是否被打。ERA 3.38 / xERA 5.61 運氣 +2.23 是賣高訊號，需實際結果驗證模型
- [ ] **Yahoo 查詢工具集中**（2026-04-13 識別）
  - 待移動的檔案（都在 `daily-advisor/`）：`_trade_batter_rank.py` / `_trade_lookup.py`（`_merge_weeks.py` 已移除 — 功能併入 `weekly_review.py::fetch_two_week_merge`）
  - 目標：新建 `daily-advisor/_tools/` 目錄，把這 2 個檔案移進去
  - 注意 import：兩個檔案都用 `sys.path.insert(0, ".")` 然後 `from yahoo_query import ...`，移動後 path 從 `daily-advisor/_tools/` 看 `yahoo_query.py` 在 `..`，要改成 `sys.path.insert(0, "..")` 或更乾淨的 `from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent))`
  - 連動更新：
    - `CLAUDE.md` 檔案索引的 `_trade_lookup.py` / `_trade_batter_rank.py` 路徑
    - `daily-advisor/yahoo-api-reference.md` 加 toolbox 索引 section
  - 不影響 cron（兩個都是 ad-hoc 手動工具，不在 `/etc/cron.d/daily-advisor`）
  - 驗證：在 VPS 跑 `python3 daily-advisor/_tools/_trade_batter_rank.py` 無 import error
