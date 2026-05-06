# MLB Fantasy Baseball 2026 賽季管理

## 專案概述

2026 Yahoo Fantasy Baseball 聯賽 — 選秀已完成，目前為 in-season 管理階段。

## 聯賽設定

- **平台**：Yahoo Fantasy Baseball
- **賽制**：H2H **One Win 勝負制**（14 類別中贏的類別 > 輸的類別 = 1 W；相等 = T；平手類別雙方都不計）
  - **majority rule，不是 8+ 門檻**：6-6-2 = T，7-5-2 = 1 W，差 1 個類別就決定 W/T/L
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
- **Tarik Skubal**（DET, SP）
- **Jazz Chisholm Jr.**（NYY, 2B/3B）
- **Manny Machado**（SD, 3B）

> 完整陣容見 `daily-advisor/roster_config.json`（唯一名單來源）。

> **文檔分工原則**：本檔只寫類型 / 規則 / 策略，**不點名具體球員**（核心球員段的 cant_cut 3 人例外）。具體球員觀察（傷勢、角色變化、限局跡象、borderline anchor 驗證等）一律進 `waiver-log.md`「隊上觀察」段；已執行 add/drop 理由看 git log。原因：球員會被 drop / 換隊 / 變更角色，CLAUDE.md 留具體球員會變孤兒（如 04-09 寫的 Tovar BB% 弱點，04-27 換 Correa 後孤兒近 1 週才被發現）。

## 執行中策略

- **Punt SV+H**：不為 SV+H 多拿 RP（最多 2 位），但現有 RP 有 SV+H 是加分
- **軟 Punt SB**：不刻意追速度，靠陣容中有速度的打者偶爾贏
- **目標**：每週「贏的類別 > 輸的類別」拿 1 W；contested 類別（差距 ≤ 1 場操作能翻）優先搶
- **串流 SP**：預設不串流。要用時見 [`docs/streaming-sp-playbook.md`](docs/streaming-sp-playbook.md)（mental model / 決策規則 / 操作流程）— 觸發判斷依「Week 中 H2H 決策框架」的 contested 類別 + controllable 變數推算

### Week 中 H2H 決策框架（One Win majority rule）

**Contested 類別判斷**（決定哪些值得用 acquisition 搶）：

| 類別 | Contested 門檻 | 判斷 |
|------|---|---|
| Counting（K / R / SB / BB / HR / RBI / W / QS / SV+H）| 差距 ≤ 5 | 1-2 場操作可翻 |
| Ratio（AVG / OPS）| 差距 ≤ 0.030 | 數場打席可翻 |
| Ratio（ERA / WHIP）| 差距 ≤ 0.30 / 0.05 | 1 場好投可翻 |
| 已輸定 | 差距 > 上述 1.5 倍 | 不掙扎 |

**Controllable vs Random 變數**（決定哪些可預測進翻盤路徑）：

- **Controllable**（有期望值算式，可精準預測）：
  - K = K9 × 預期 IP（FA SP 季線 K9 × 5 IP）
  - IP / QS / SV+H — SP/RP 場次直接累加
  - HR / RBI / R 對特定 platoon → 有結構訊號
- **Random**（單週 swing 太大，**不該納入翻盤路徑算式**）：
  - BB / 短期 R / SB — 受 lineup / 對戰 / 配球大量影響
  - 一場 OPS / AVG spike — noise

**已輸定類別的零邊際成本原則**：
- ERA / WHIP / IP 等比率/累積類別已差超過 contested 門檻 1.5 倍 → 撿爛 SP 多虧 0.05 ERA / 0.02 WHIP **不算戰術損失**（已輸的不會變更輸）
- 不該成為阻止撿 contested 類別補強的理由

**判斷例**：K -2 + Kay K9 5.4 × 5 IP 期望 +3 K → 翻 K = +1 win 期望，撿。
**反例**（錯誤判斷）：「ERA 會從 4.70→4.78 拉爛」→ 已輸定（差 -1.32 遠超門檻），多 0.08 不影響輸贏，不該阻止撿。

### Waiver 操作規則

- **所有撿人走 FAAB**（waiver_rule: all），無即時 FA
- **處理時間**：每日 ET 3AM（= TW 15:00）
- **上場時效**：claim（TW 15:00 前）→ 當日 TW 15:00 處理 → 當晚設 Daily-Tomorrow lineup → 隔天上場（前置 1 天）
- **被 drop 球員**：1 天 waiver period
- **FAAB 預算**：$100 全季，同額 tiebreak = continual rolling list
- **FAAB 餘額**：$100（至 2026-05-02 仍滿；Detmers / Junk / Severino 皆 $0 取得）
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
- **投手 selected_pos（SP/BN/P/RP）不影響品質評估** — 投手會在 SP/BN 間輪換調度（當天先發放 SP、已先發過放 BN 等下次輪值），BN ≠「非主力」「占位」。drop 理由只能來自結構面（v4 Sum / 雙年 prior / 樣本可信度 / 運氣訊號 / 21d 趨勢 / Rotation gate）。打者才適用「BN = 角色脈絡」判斷
- **SP 評估必用 v4 5-slot（IP/GS / Whiff% / BB/9 / GB% / xwOBACON）** — HH% / xERA / xwOBA 是 v2 已退役指標（2026-04-28 cutover），不可作 SP drop 判斷依據；任何不在 5-slot 的百分位只是 context，**不是 first-order signal**。Why：2026-05-04 用 HH% P5 反向誤判 Holmes 結構性弱，但 v4 xwOBACON 只 P40，當天 Phase 6 也沒排 worst 4。How to apply：判 SP 前先讀同一天 fa-scan SP-v4 GitHub Issue（`gh issue list -R huansbox/mlb-fantasy --label fa-scan`）作 anchor；逆向質疑 Phase 6 需要強反證（如 IL 標籤遺漏這類具體事件），**不是百分位 lens 差異**。

### 打者評估（v4 thin — raw + agent 自由 reasoning）

> 設計依據：`docs/batter-framework-upgrade-design.md`（2026-04-28 對齊定稿）。SP 走 v4 5-slot + Phase 6 multi-agent，batter 走 v4 thin。

**兩層分工**：
- **機械層（Python）**：只做 hard rule 排除（cant_cut / BBE<40 / 2026 Sum ≥25 排除），**不算 urgency / 不打 ✅⚠️ tag / 不預判 decision**。Sum 內部用作 ≥25 filter，**不暴露給 LLM**。
- **LLM 層**（Phase 6 將升級為 multi-agent，過渡期單 LLM）：拿 raw + percentile + 14d trad + %owned trend，自由 reasoning 排 drop 優先序 + 標 FA 取代/觀察。

**核心 3 指標**（機械層 Sum filter 用，LLM 層也看其 percentile）：
- **xwOBA** — 打擊品質總指標
- **BB%** — 最高效指標（BB 欄 + OPS 的 OBP 端，7×7 雙重計算）
- **Barrel%** — HR 最佳預測指標，7×7 無 K 懲罰下 power 是核心價值

**LLM 層額外看的訊號**（過去機械層硬編碼的 factor 改交 LLM 自判）：
- **14d trad**：OPS / AVG / HR / RBI / R / SB / BB / K / K% spike — 當週 H2H 決策的 first-order signal
- **%owned trend**：3d / 7d delta + shape（explosive/rising/plateau/dropping）— 聯盟動態
- **2025 prior**：xwOBA / BB% / Barrel% percentile — 區分 breakout 真假 / slump 候選
- **Production**：PA、PA/Team_G、BBE — 樣本可信度 + 隊內角色

#### 機械層 hard rules（pick_weakest batter）

| 規則 | 對象 | 原因 |
|------|------|------|
| **cant_cut 名單排除** | 從 league config（Skubal / Jazz Chisholm / Manny Machado）| 不想動的核心，含 skill cant_cut + slump hold 統一管理 |
| **BBE <40 → low_confidence_excluded** | 全隊 batter | 樣本噪音大，剛 call up / 受傷 1 週球員不該作 anchor |
| **2026 Sum ≥25 排除** | 全隊 batter | 當下表現 P75+ 全方位 = 不該列 drop 候選 |
| **不限 n 人** | 全隊 batter | Sum<25 全進池，由 LLM 自判排序（不再 n=4 cap）|

**Sum 計算**（內部 filter 用，不暴露）：3 核心指標各取 percentile 打 1-10 分，加總 3-30。Sum ≥25 過 hard floor。

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

#### LLM 層自由 reasoning

**不給判斷框架**。沒有「整季強+14d 強 → hold」這類 2×2 矩陣。LLM 從 raw + percentile + 14d trad + %owned 自行 reasoning：

- 結構性弱（雙年低）→ 結構性確認，drop 候選
- 14d 火燙（OPS ≥.850）但 season Sum 低 → 賣低風險，hold
- K% 短期跳 +5pp 以上 → 傷勢警訊
- BBE 在排除門檻邊緣（剛過 40）→ 信心仍低，hedge

> Phase 6 將拆 multi-agent（3 agent rank → master 整合 → 1-1-1 才 re-review），給 dissent surface 跟雙候選空間。詳見 `docs/batter-framework-upgrade-design.md` §4。

#### FA 勝出門檻（過渡期）

過渡期沿用 fa_compute 計算 Sum 差作為 LLM 排序提示（不是 verdict）：
- Sum 差 ≥3 + 至少 2 項 metric 正向 → 機械標 win_gate_passed
- 但最終取代/觀察判斷由 LLM 自由 reasoning 決定，不卡 binary tag

**保留的 FA tag**（PA-based gate）：
- ✅ 球隊主力（PA/TG ≥3.5）— 信心提升
- ⚠️ 上場有限（PA/TG <2.5）— 強警示

**移除的 FA tag**（交 LLM 從 raw 判斷）：✅ 雙年菁英 / ✅ 近況確認 / ⚠️ Breakout 待驗 / ⚠️ 近況下滑 / ⚠️ 樣本小

#### fa_scan 不做的事（手動處理）

守位判斷 / Active 或 BN 角色脈絡 / 單點故障 / 邊際遞減 / 陣容需求
→ 特殊情況由 /player-eval 或 /weekly-review 手動判斷

守位 / selected_pos / status / IL/BN/DTD **不影響評價** — 評估只看打擊數據；上場狀態跟當天比賽有關，不是品質訊號。

#### 7×7 格式規則

- 無 K 類別 → 高 K 打者無懲罰
- Punt SB → 速度價值打折，但非零
- 不使用 hot/cold streaks（零預測力）
- 不使用 BvP 歷史對戰（樣本太小）

#### 樣本量加權

BBE <40 從 anchor 池排除（low_confidence_excluded）— 跟 SP <30 對齊提高至 40。LLM 仍可看到 14d 訊號但被告知「BBE <40 信心低」。

### SP 評估（v4 — 5-slot Sum + Phase 6 multi-agent）

> 設計依據：`docs/sp-framework-v4-balanced.md`。Production live = v4 + Phase 6 multi-agent。v2 已完整移除（2026-05-05 cleanup commits）— rollback 只能走 git revert（v4 production 已穩跑 8 天）。

**兩層分工**：
- **機械層（Python，`fa_compute.py` + `_phase6_sp.py`）**：Rotation Gate 排除 pure RP（GS=0 / IP/GS<3）/ 5-slot Sum 排序 / urgency 4-factor / ✅⚠️ tags / Slump hold 標記。Sum / urgency 是材料，**不是 verdict**。
- **LLM 層（Phase 6 multi-agent）**：3 agent 排我方 P1-P4 → master 整合 → borderline review/re-eval → FA classify → master rank → review → final master 輸出 `drop_X_add_Y` / `watch` / `pass`。

**核心 5 指標**（5-slot balanced Sum）：

| 指標 | 為什麼重要 |
|------|-----------|
| **IP/GS** | IP + QS 產量（H2H 7×7 計分類別）|
| **Whiff%** | K 前驅訊號，比 K/9 更早反映 stuff |
| **BB/9** | WHIP 的 BB 端 + 爆局風險 |
| **GB%** | HR/長打抑制、省球、雙殺 |
| **xwOBACON** | on-contact damage（避開 xwOBA 被 K/BB 稀釋）|

設計目的：v2 的 xERA / xwOBA / HH% 三指標家族高度相關（contact quality 重複投票），會讓「被打品質差」過度支配判斷，低估 fantasy SP 真正需要的 IP / K / QS / 控球。v4 把 SP 拆成 5 個較獨立的 fantasy 軸（產量 / K stuff / 控球 / GB / contact damage），降低重複投票。

#### 機械層 hard rules

| 規則 | 對象 | 原因 |
|------|------|------|
| **cant_cut 排除** | 從 league config | 不想動的核心 |
| **Rotation Gate** | GS=0 或 game-log IP/GS<3 | 排除 pure RP / long relief |
| **BBE <30 → low_confidence_excluded** | 全隊 SP | 樣本噪音大 |
| **Slump hold** | 2025 Sum ≥24 且 IP ≥50 | 菁英底，slump 不參與 urgency |

Sum 範圍 5-50（5 指標各取百分位 → 1-10 分加總）。

**打分表**（SP 反向：百分位越高 = 越菁英 = 分數越高；reverse 指標如 BB/9 / xwOBACON 顯示低值對應菁英側）：

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

#### Urgency 4-factor（最弱 SP 內部 drop 排序）

| 因子 | 說明 |
|------|------|
| **2026 Sum** | 越低 urgency 越高 |
| **2025 Sum**（IP ≥50 才啟用）| 雙年檢核；<18 結構性 +2 / ≥24 slump hold 移出 |
| **21d xwOBACON Δ** | 趨勢；強劣化 +2 / 強回升 -2（門檻校準中，見待辦）|
| **2026 IP/Team_G** | active 輪值放大；≥1.0 +2 / 0.5-1.0 +1 |

Urgency 高 → 可能成 multi-agent step 1 候選 P1。但 final action 仍由 LLM 決定。

#### LLM 層自由 reasoning

不給 binary 升級 matrix。LLM 從 raw + percentile + 5-slot signals + tags + slump-hold + 21d trend + 新聞脈絡 自行 reasoning：
- 結構性弱（雙年雙低）→ drop 候選
- 5 指標 P30+ 但 ERA 5+（運氣差）→ buy-low
- BBE 邊緣（30-50）→ 信心警示

#### FA 勝出門檻（過渡期沿用，作 LLM 排序提示）

- Sum 差 ≥3 + 至少 2 項 metric 正向 → 機械標 `win_gate_passed`
- 但最終取代/觀察判斷由 LLM 自由 reasoning 決定，不卡 binary tag

**保留的 FA tag**（PA-based / 樣本 gate）：
- ✅ 雙年菁英 / 深投型 / 球隊主力 / 撿便宜運氣 / GB 重型 / K 壓制
- ⚠️ 短局 / 上場有限 / 樣本小 / Breakout 待驗 / 賣高運氣

#### IP/Team_G 方向說明

- **Drop 觀點**：IP/TG 越高 → urgency 越高（active 輪值每場拖比率）
- **Add 觀點**：IP/TG 越高 → 信心越高（球隊輪值固定 → 數據能累積）
- 兩方向相反，因意義不同

#### xERA-ERA 運氣標記（輔助訊號）

- **+1.52**：xERA 3.52 / ERA 2.00 → 運氣好，ERA 預期回升（賣高訊號）
- **-1.50**：xERA 3.50 / ERA 5.00 → 運氣差，撿便宜訊號（buy-low）
- 絕對值 ≥0.81（P70+）才標記顯著

#### fa_scan 不做的事（手動處理）

單點故障 / 邊際遞減 / 陣容需求 / FAAB 預算策略 → 由 `/player-eval` 或 `/weekly-review` 手動判斷。

#### 7×7 格式規則

- IP 是獨立類別 → 局數怪物 > 精品短局型
- QS 需 6+ IP → IP/GS 低的投手 QS 打折
- W 受球隊影響 → 強隊 SP 有 W 加成
- 串流 SP：下週 2 先發 + 對戰後段打線，不看全季指標

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
注意：RP 品質指標（xERA/xwOBA/HH%/Barrel%）採用本表（SP/RP 共用同樣聯盟分布），K/9 和 IP/Team_G 為 RP 專用。

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

腳本資料流圖見 [`docs/architecture.md`](docs/architecture.md)（CLAUDE.md / daily_advisor / fa_scan / roster_config / waiver-log 之間的讀寫關係）。

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
| `docs/architecture.md` | 系統架構資料流圖（CLAUDE.md / daily_advisor / fa_scan / roster_config / waiver-log 讀寫關係） |
| `docs/handoff-il-na-filter.md` | FA IL/NA 過濾機制 handoff（2026-05-05）— ✅ Part 1 已完成 merged（commits `87bf243` / `e69555b` / `5113932`）；附加 Task `yahoo_query.py savant v4 SP 升級` 仍待辦 |
| `docs/streaming-sp-playbook.md` | 串流 SP 詳細手冊（mental model / 決策規則 / 操作流程） — 預設不串流，需要時才查 |
| `docs/handoff-claude-md-cleanup.md` | CLAUDE.md cleanup handoff（2026-05-04）— Task 1（v2 SP code 完整移除）✅ 2026-05-05 完成；Task 2（playbook 段抽出）待辦 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |
| `daily-advisor/calc_percentiles_2026.py` | 百分位分布計算工具（Week 6-8 更新 2026 百分位表時使用） |
| `daily-advisor/calc_v4_percentiles.py` | v4 框架 2025 SP 百分位計算（IP/GS / Whiff% / BB/9 / GB% / xwOBACON；n=178/115）|
| `daily-advisor/fa_scan_v4.py` | **v4 ad-hoc CLI 工具（純 stdlib + 公開 API，本機 / VPS 皆可跑）— 隊上 SP + FA 候選 5-slot Sum 排序 + Rotation gate；不入 production cron。Stage F 一起決命運（退役 / 偵錯 / Phase 6 manual frontend）** |
| `daily-advisor/backfill_prior_stats_v4.py` | v4 cutover 前置：把 2025 `whiff_pct` / `gb_pct` / `xwobacon` backfill 進 roster_config.json（reuse fa_scan_v4 fetchers，idempotent，新進 SP 也可跑） |
| `daily-advisor/_tools/_trade_lookup.py` | 聯盟 roster 掃描（隊伍查詢 / 守位覆蓋 / 位置過剩掃描 / 球員 7-cat 比較） |
| `daily-advisor/_tools/_trade_batter_rank.py` | 交易打者排名掃描（目標打者 vs 11 隊全打者 wRC+ 排名，找交易候選隊伍） |
| `docs/fa_scan-claude-decision-layer-design.md` | **Phase 6 設計（Claude 決策層 + multi-agent review）+ §7 七題詳化（2026-04-26）— 與 v4 cutover 同波完成（D1=A 鎖定）** |
| `docs/sp-framework-v4-balanced.md` | **SP 評估 v4 設計定稿（5-slot balanced Sum + Rotation gate pre-filter + 時間尺度分層）** |
| `docs/sp-decisions-backtest.md` | SP 決策 living log（9 筆歷史決策 + 元回測機制，每 2-4 週更新「後續走勢」）|
| `docs/v4-cutover-plan.md` | **v4 cutover Stage A-F step-by-step 實作計畫（2026-04-25）— Stage A-D 完成，E parallel 並行中（04-28 起），動 Stage F 前讀** |
| `docs/savant-xwobacon-endpoint-research.md` | 21d xwOBACON 端點研究（2026-04-25）— **驚喜 finding：不需新 endpoint，savant_rolling.py 4 行 patch 即可**（已實作 commit `621a5d2`）|
| `docs/phase6-multi-agent-spike.md` | Phase 6 multi-agent spike 計畫 + 結果（2026-04-25 plan / 04-26 跑完）— P1 共識 100%，§7.2 放寬為「P1 match 即收斂」（borderline gate Sum 差 <5 才強制 step 3 review） |
| `docs/sp-decisions-backtest-automation.md` | SP 決策 backtest 自動化 design（2026-04-25）— v4 cutover 後 1-2 月觸發實作 |
| `docs/savant-smoke-test-design.md` | Savant 端點 daily smoke test design（2026-04-25）— v4 cutover 前後實作 |

## 待辦

<!-- 已完成 2026-04-21 commit 3ce1eae：
- waiver-log auto-close mlb_id 驗證 — _check_player_ownership 加 expected_team
  參數交叉驗證 Yahoo editorial_team_abbr，同名同姓不會再誤關（Muncy LAD vs
  ATH 兩次誤關事件：afbe6ca / 39170c9 → 已根治）
  -->
- [ ] **SP v4 cutover 補完**（高優先，2026-05-06 系統性 v2 grep 發現 7 項殘留）：v4 cutover 實際只 Phase 6 multi-agent + 5 個 SP prompt 對齊；每日戰報資料層 / FA SP_THRESHOLDS gate / Phase 6 context 排序與顯示 / FA prior_stats 寫入 / 週覆盤 / opposing SP prompt 文字 全仍 v2。詳見 [`docs/handoff-sp-v4-cutover-completion.md`](docs/handoff-sp-v4-cutover-completion.md)（reviewer audit 確認 + 排序依賴 + commit 分組）。預估 5-7 hr / 5 commits。**P1（daily_advisor.py）必須先做才能改 P6 prompt**。
- [ ] **RP 框架 v4 升級**（SP v4 觀察期 1-2 個月後啟動）：當前 RP 仍走 v2 指標（xERA / xwOBA allowed / HH% allowed / Barrel% allowed），SP 已 cutover 至 v4 5-slot。RP 升級**不是換指標**，是框架重設計：(a) IP/GS 對 RP 無意義，要重決定 5-slot 第 5 軸；(b) `calc_v4_percentiles.py` 要重跑 RP n=284 的百分位（RP Whiff% 分布通常高於 SP）；(c) RP 目前無 Phase 6 / urgency / Sum，整套決策邏輯要設計。同步更新 `yahoo_query.py savant` RP path（已留 TODO comment）+ CLAUDE.md「RP 評估」段 + `prompt_*_rp.txt`（若有）。預估 1-2 週工作量。
- [ ] **CLAUDE.md cleanup Task 2（剩餘）**：抽出其他「不常用 + 多行」段成 playbook。本 session 已抽 系統架構（→ `docs/architecture.md`）+ 壓縮 v4 cutover archive（-49 行）。剩候選：檔案索引（~30 lines，每天查得到不建議拉）/ 執行環境（~15 lines，行數不夠）。Task 1 ✅ 2026-05-05 完成。詳見 [`docs/handoff-claude-md-cleanup.md`](docs/handoff-claude-md-cleanup.md)。
- [ ] **Severino transformation 驗證**（觀察中，啟動 2026-05-02）：v4 機械層季線 Sum 25 被前 5 場污染，近 2 場 transformation level（ERA 1.32 / BB/9 1.97 P80+ / IP/GS 6.83 P90+）。下 2 場驗證 BB ≤2 / IP ≥6 / 主場 ER ≤2，全通過從 borderline 轉正式 anchor；任一失守降回觀察。詳見 `waiver-log.md` 「隊上觀察」段
- [ ] **waiver-log 新進條目 mlb_id 正確性驗證**（進階，已根治 auto-close 端，但 NEW 入口仍可能寫錯 mlb_id）：`_update_waiver_log_locked` NEW 行走 `search_mlb_id(name)` 補 mlb_id，同名同姓仍可能取到第一個（錯的）。建議 NEW 時走 Yahoo API 交叉驗證 team / position 匹配
- [ ] **SP 21d Δ xwOBACON 絕對門檻校準**（v4 cutover 後 1-2 個月）：v4 上線後 Python `_factor_rolling` 暫返回 0（門檻借 batter 風險太大、SP 池 n~18 算 P25/P50/P75 不可信），原始 Δ + BBE 餵 Claude 用絕對量級提示判斷（|Δ| <0.030 / 0.030-0.050 / ≥0.050）。校準路徑：累積 1-2 個月後從 GitHub Issue archive 反推全期 SP 21d Δ xwOBACON **絕對門檻**（例如「|Δ| ≥0.040 後續 70% 應驗 → 改門檻 0.040」），改 prompt 文字不改 code。詳見 `docs/sp-framework-v4-balanced.md` §「Step 2 — Urgency 排序」決策 1/4。
- [ ] **fa_scan_v4.py CLI 命運**（v4 cutover 完成後仍待決）：退役 / ad-hoc 偵錯 / Phase 6 manual frontend 三選一。v4 cutover Stage A-F 全完成（2026-04-26 ~ 2026-05-05；Phase 6 §7.1-7.7 設計鎖定見 `docs/fa_scan-claude-decision-layer-design.md` §7；歷史 commits 見 git log + `docs/v4-cutover-plan.md`）。
- [ ] **SP / Batter 框架對稱性檢視**（batter Phase 6 multi-agent 上線時觸發）：目前 SP（v4 + Phase 6）與 Batter（v4 thin + single LLM）機械層厚度不一致 — SP 機械層算 urgency 4-factor + ✅⚠️ data-based tags + Sum 暴露給 LLM，Batter 機械層只 hard filter 不算 urgency / 不打 data-based tag / Sum 不暴露。差異有 intentional 部分（樣本門檻 BBE <40 vs <30、slump hold 機械 vs LLM、14d vs 21d 趨勢視窗 — 投打打數累積與時間尺度不同）也有「演化未完」部分（urgency / tags / Sum 暴露三項可能該下放給 multi-agent 自由 reasoning）。Batter Phase 6 multi-agent 上線後重評 SP 是否拆薄（option X：對齊 batter / option Y：保留 SP anchor）。詳見 2026-04-29 session 對照表。
- [ ] **SP Phase 6 prompt 拿掉 Sum 暴露對齊 batter v4 thin**（用戶觀察 2026-05-04）：當前 SP v4 Phase 6 prompt 暴露 Sum 給 LLM（fa-scan #149 三 agent 直接寫「Sum 14 / Sum 19」），lazy 引用 Sum 數字而非從 raw + percentile 自由 reasoning。Batter v4 thin 已把 Sum 內部當 ≥25 filter 不暴露（CLAUDE.md「打者評估」段），SP 應對齊。改 5 個 `prompt_phase6_sp_*.txt` 拿掉 Sum，只給 raw + percentile + 5-slot 訊號。Sum 1-10 分桶失真（P89 vs P91 跳 1 分而 P79.5 vs P75 同分），加總喪失 dimension（哪個 slot 強看不到）。「框架對稱性檢視」的具體 actionable 子項。
- [ ] **Phase 5 minor refactor**（2026-04-21 Architect 審查 finding，不影響功能）：
  - ~~finding C~~：✅ 2026-04-26 完成（commit `fca8cb2`，改用 `_PRIOR_IP_SLUMP_HOLD_MIN` 常數）
  - finding D：`fa_scan.py:683` `_calc_batter_sum`（Layer 2 filter）與 `fa_compute.py compute_sum_score` 雙重實作 batter Sum → 統一使用 fa_compute（要小心 input dict shape 略不同）
  - ~~finding E~~：✅ 2026-04-26 完成（commit `95c9713`，`--no-send` mode `print(advice, flush=True)`）
- [ ] **preview 加入聯盟 scoreboard**：用 `yahoo_query.py scoreboard` 邏輯存入 JSON，預測時有數據基礎
- [ ] Week 6-8：更新百分位表為 2026 賽季數據（CLAUDE.md + daily_advisor.py + prompt 檔，腳本 `calc_percentiles_2026.py` 已備好）
- [ ] **交易掃描工具**：`_trade_batter_rank.py` 已完成（wRC+ 排名掃描）。待擴充：SP 端掃描（目標 SP vs 對方隊 SP 排名）、自動交叉比對「我方打者在對方排 ≤8 + 對方 SP 品質 > Detmers」
