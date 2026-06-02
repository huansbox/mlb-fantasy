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
  - Waiver：被 drop 球員走 **FAB** 競標（Free Agent Budget，同額 tiebreak = Continual rolling list）；已清 waiver 的 FA 先搶先得、免費
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
- **串流 SP**：預設不串流。要用時見 [`docs/streaming-sp-playbook.md`](docs/streaming-sp-playbook.md)（mental model / 決策規則 / 操作流程）— 觸發判斷依「Week 中 H2H 決策框架」的 contested 類別 + controllable 變數推算。實際操作呼叫 `/stream-sp`（顯式給 ET 日期或讓 skill 列未來 3 天讓你挑），自動跑 probable → FA 篩 → opener 排除 → v4 5-slot 評估

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

- **兩種撿人途徑**：
  - **Waiver claim** — 對象為近期被 drop、仍在 waiver period 內的球員，**需 FAAB 出價**；每日 ET 3AM（= TW 15:00）統一處理，同額 tiebreak = continual rolling list
  - **FA add** — 已清 waiver 的自由球員，**先搶先得、免費（$0）、即時生效**
- **被 drop 球員**：1 天 waiver period，期滿未被 claim → 落入 FA 池
- **上場時效**：waiver claim（TW 15:00 前）→ 當日 15:00 處理；FA add 即時生效 → 當晚設 Daily-Tomorrow lineup → 隔天上場（前置 1 天）
- **FAAB 預算**：$100 全季，**僅 waiver claim 消耗**；同額 tiebreak = continual rolling list
- **FAAB 餘額**：$100（至 2026-05-19 仍滿；Detmers / Junk / Severino / Kody Clemens 皆走 FA $0 取得）
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

### SP 評估（B2 — 5-slot thin mechanical + 2-step single-LLM）

> 設計依據：`docs/sp-b2-cutover-design.md`。Production live since 2026-05-28 = B2 thin + 2-step single-LLM。B1 multi-agent 已退役（2025 prior + urgency + slump hold + M1/M4' metrics 全清）— rollback 走 `git revert -m 1 <B2 merge commit>`（merge commit hash 見 design doc 標頭），不可 reset/checkout 到 hash（會丟失 B2 開發期間其他無關 commit）。

**兩層分工**：
- **機械層（Python，`fa_compute.py` + `anchor_filter.py`）**：我方 pipeline — anchor_filter（cant_cut + weekly_anchor_sp）→ BBE<30 filter → 5-slot Sum 排序 → top-3。FA pipeline 在 `_phase6_sp.py` Layer 1.5 加 Rotation Gate（GS=0 / game-log IP/GS<3 排除）作 pure RP filter。Sum 是內部排序鍵，**不暴露 LLM**；無 urgency / 無 slump hold / 無 Sum 硬門檻。
- **LLM 層（`_phase6_sp.py`，2-step single-LLM）**：Step A 一次 call 排我方 P1-P3 + classify 每位 FA（worth / borderline / not_worth）→ structured JSON；Step B 一次 call 讀 Step A JSON + 同樣 slim pool → 最終 verdict `drop_X_add_Y` / `watch` / `pass`。Step A JSON 失敗會 1 retry + Telegram alert + fall-through 到 pass（cron 不會 silently crash）。

**核心 5 指標**（5-slot balanced Sum）：

| 指標 | 為什麼重要 |
|------|-----------|
| **IP/GS** | IP + QS 產量（H2H 7×7 計分類別）|
| **Whiff%** | K 前驅訊號，比 K/9 更早反映 stuff |
| **BB/9** | WHIP 的 BB 端 + 爆局風險 |
| **GB%** | HR/長打抑制、省球、雙殺 |
| **xwOBACON** | on-contact damage（避開 xwOBA 被 K/BB 稀釋）|

設計目的：v2 的 xERA / xwOBA / HH% 三指標家族高度相關（contact quality 重複投票），會讓「被打品質差」過度支配判斷，低估 fantasy SP 真正需要的 IP / K / QS / 控球。v4 把 SP 拆成 5 個較獨立的 fantasy 軸（產量 / K stuff / 控球 / GB / contact damage），降低重複投票。

#### Anchor 機制（B2 新增）

| Anchor 類型 | 來源 | 時效 | LLM 可見性 | 編輯頻率 |
|---|---|---|---|---|
| `cant_cut` | `roster_config.json` `league.cant_cut` | 終身不動 | 完全不可見 | 罕見（長期承諾改變）|
| `weekly_anchor_sp` | `roster_config.json` `league.weekly_anchor_sp` | 本週 | 完全不可見 | 每週 `/weekly-review` 檢視 |

兩種 anchor 都走同一個 `anchor_filter.filter_anchors()` 純函式（accent / apostrophe / case-insensitive 名稱比對），在 `pick_weakest_v4_sp` 入口一次篩掉。**LLM 完全看不到 anchor**（不在 roster snapshot、不在候選池）— 「fair game」哲學：不在 list 上 = 可 drop 候選。

`cant_cut` 語意正式收窄為「終身不動」。`weekly_anchor_sp` 給 menls in slump / 新交易進來還在 settle / 想觀察 breakout 候選 — 由用戶每週手動編輯 JSON。

#### 機械層 hard rules

| 規則 | 對象 | 套用層 | 原因 |
|------|------|------|------|
| **anchor_filter** | 我方 SP 名單 vs cant_cut + weekly_anchor_sp | `fa_compute.pick_weakest_v4_sp` | 用戶層級保護，LLM 完全不見 |
| **BBE <30 → low_confidence_excluded** | 我方 SP | `fa_compute.pick_weakest_v4_sp` | 樣本噪音大 |
| **Sum ascending 排序** | 倖存我方 SP | `fa_compute.pick_weakest_v4_sp` | 內部排序，取 top-3 入候選池 |
| **Rotation Gate** | FA pool（GS=0 或 game-log IP/GS<3）| `_phase6_sp.py` Layer 1.5 | 排除 pure RP / long relief — 我方 SP 不過此 gate（信任 roster_config）|

Sum 範圍 5-50（5 指標各取百分位 → 1-10 分加總）。**Sum 只用作機械層內部排序，不暴露 LLM**，不作 borderline trigger（沒有 multi-agent），不作 hard floor。

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

#### LLM 層自由 reasoning

Step A 一次 call 處理 my-team rank（P1-P3）+ FA classify。讀 raw + percentile + 14d trad + 21d Δ + tags，自由 reasoning，輸出 structured JSON。

Step B 一次 call 讀 Step A JSON **加上同樣 slim pool**（不是只看 Step A 壓縮 summary — Step B 用原始 metrics 推理）→ 最終 verdict + rationale。

不給 binary 升級 matrix。LLM 從 raw + percentile + 5-slot + tags + 21d trend + 新聞脈絡 自行 reasoning：
- 結構性弱（5 指標多項 P30 以下）→ drop 候選
- 5 指標 P30+ 但 ERA 5+（運氣差）→ buy-low（看 xERA-ERA 差）
- BBE 邊緣（30-50）→ Step B 偏 watch

#### FA tag 設計（2026-only，B2 拿掉 2025 prior tags）

`fa_compute.compute_fa_tags_v4_sp` 為所有 FA 算 tags（B2 拿掉 win_gate short-circuit）；`payload_slimmer._ALLOWED_TAGS` whitelist 控制哪些 tag 進入 LLM payload。

**保留的 tags**（2026 + 21d-based）：
- ✅ 球隊主力 / 深投型 / GB 重型 / K 壓制 / 撿便宜運氣 / 近況確認
- ⚠️ 上場有限 / 樣本小 / 短局 / IL 短期 / Swingman 角色 / xwOBACON 極端 / K 壓制不足 / Command 警示 / 賣高運氣 / 近況下滑

**移除的 tags**（2025 prior-based）：
- ~~✅ 雙年菁英~~（2025 v4 Sum ≥40 + IP ≥50）
- ~~⚠️ Breakout 待驗~~（2025 Sum <25 或無 prior）

#### xERA-ERA 運氣標記（2026 only，輔助訊號）

- **+1.52**：xERA 3.52 / ERA 2.00 → 運氣好，ERA 預期回升（賣高訊號 ⚠️ 賣高運氣）
- **-1.50**：xERA 3.50 / ERA 5.00 → 運氣差，撿便宜訊號（buy-low ✅ 撿便宜運氣）
- 絕對值 ≥0.81（P70+）才標記顯著；BBE ≥40 才啟用（避免崩盤中誤判）

#### 品質監控（取代退役的 M1/M4'）

兩層機制：
- **Backtest 自動化（Use Case A，issue 024 + 025）**：週日 UTC 06:00 = TW 14:00 cron 跑 `cron_backtest.sh` wrapper（git pull → `daily-advisor/backtest_track.py --days 7 --update-doc` → 若 doc 變更則 commit/push）→ 算 hit-rate + marginal benefit 追加進 `docs/sp-decisions-backtest.md`（隔天 Monday `/weekly-review` 人工 session 即可看到新增段）。首跑 2026-05-31。慢但高訊號（週級）。
- **`/weekly-review` 人工 spot check（issue 026）**：每週看過去 7 天 SP verdict gut check + 檢視 `league.weekly_anchor_sp` list 是否還有效。快但主觀（日級）。

兩層覆蓋日與季的時間尺度。

#### fa_scan 不做的事（手動處理）

單點故障 / 邊際遞減 / 陣容需求 / FAAB 預算策略 → 由 `/player-eval` 或 `/weekly-review` 手動判斷。

#### 7×7 格式規則

- IP 是獨立類別 → 局數怪物 > 精品短局型
- QS 需 6+ IP → IP/GS 低的投手 QS 打折
- W 受球隊影響 → 強隊 SP 有 W 加成
- 串流 SP：下週 2 先發 + 對戰後段打線，不看全季指標

### RP 評估（RP-SV+H SOP）

**策略前提**：Punt SV+H（不主動追），但放 1 個 RP 主攻 SV+H。維持 2 位 RP，不會加到 3-4 位。

**評估流程**：走 RP-SV+H **production-first** SOP — MLB 全聯盟 14d SV+H 排行找產出者 → Yahoo FA 交叉 → 三軸 rank-sum（BB/9 升序 · whiff% 降序 · 30d SV+H 降序，等權）選 top-N（cutoff 並列納入）→ LLM 角色安全 news check → verdict（換 incumbent / hold / 選 1 / pass，預設 hold）。

- **機械層**：`rp_svh_scan.py`（TDD 43 tests）；**LLM 層**：`/rp-svh` skill。
- **唯一規格依據**：`docs/rp-svh-metrics.md`。球員追蹤：`waiver-log-rp.md`。落地規劃：`issues/rp-svh-sop.md`。
- 取代舊 `fa_scan.py --rp` 週掃（v2 指標 xERA / xwOBA / HH%）— 並行 1-2 週驗證後退役。
- 三軸 rank-sum 是 pool 內相對排名，**不需絕對百分位門檻**（不必算 RP 百分位表）。
- contact-quality 指標（Barrel% / xwOBACON / xERA-ERA）**不進機械層** — RP 季中 BBE 噪音過大；交 LLM 層 context-only。

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
| 2 | `/rp-svh`：RP-SV+H 掃描（手動 session）| 取代舊 `--rp` 週掃；舊 `--rp` cron 並行 1-2 週驗證中 |
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
| 週中需要串流補 QS/W/IP | `/stream-sp`（顯式 ET 日期或選未來 3 天）→ 看候選報告 → 用戶 claim（前一天 TW 15:00 前）|
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
  bash bin/vps-run.sh 'cd /opt/mlb-fantasy/daily-advisor && python3 yahoo_query.py <cmd>'
  ```
- ⚠️ **本機↔VPS 路徑間歇封包遺失** → SSH handshake 偶發卡死 ~30-40s（根因確認見 `issues/vps-ssh-handshake-hang.md`）。VPS 指令一律走 `bash bin/vps-run.sh '<remote cmd>'`（timeout + retry wrapper）；純讀指令免旗標、寫檔 / git 指令加 `--no-retry`。`rp-svh` / `stream-sp` / `stream-sp-deep` / `weekly-review` 的 SSH step 已改走 wrapper；`docs/player-eval-sp.md` 4 處 SSH（含 here-doc）待轉 VPS 端腳本後再納入。
- **本機取歷史數據（daily report / fa_scan 存檔）**：
  ```bash
  gh issue view <N> -R huansbox/mlb-fantasy
  ```
- ⚠️ **不要 scp Yahoo token 回本機** — yahoo_query.py 會自動 refresh token，雙邊不同步會讓 VPS 原本 token 失效，cron 全斷
- ⚠️ **不要本機跑會 call Yahoo 的腳本** — 同前因；`hooks/block-local-yahoo.mjs` PreToolUse hook 機械化執行（攔截 Bash + PowerShell tool，名單：yahoo_query / daily_advisor / fa_scan / emerging_batter_scan / stream_sp_scan / rp_svh_scan / roster_sync / roster_stats / weekly_review / _trade_lookup / _trade_batter_rank。pytest / vps-run.sh / ssh / scp / 引號內字串 / heredoc body 都會放行）。違反規範下次 session 會被擋；hook 註冊在 `.claude/settings.json`（git tracked，跨機器同步），同檔另註冊 SessionStart 的 `hooks/sync-mirror.mjs`
- **Roster 新鮮度 pipeline（兩層同步）**：名單唯一來源 `roster_config.json` 的新鮮度分兩層維護。**第 2 層 [Yahoo → origin]**：VPS `roster_sync.py` cron **每 15 分**（`7,22,37,52 * * * *` — offset 避開其他 cron 的 :00/:10/:15/:30/:45 並行 git push race）poll Yahoo transactions → 有異動才更新 config + push（空跑提早 return，~1-2s，不 commit）。waiver TW 15:00（UTC 07:00）後第一班在 07:07。**第 1 層 [origin → 本機]**：`hooks/sync-mirror.mjs` SessionStart hook 開場 `git fetch`，在 `master` + working tree 乾淨 + 可 fast-forward 時自動 `pull --ff-only`，否則（feature branch / dirty / 有未推 commit / 非全新 session）只注入警告不動 working tree。FA add 即時生效、waiver TW 15:00 後同步 — 兩者都靠「VPS poll → origin → 本機 pull」拿到，**不需也不可本機 call Yahoo**。**無「預測未來 roster」機制**：waiver 結果 15:00 後拉即知，pending claim 本就可能失敗不該預測。高頻 poll 的硬前提是 `classify_empty_diff` 浮水印修正（Yahoo read-after-write lag 窗不誤推進浮水印）。需 sub-15-min 即時刷新（剛做異動想立刻評估新人 / session 開很久中途換人）→ `/sync-roster` 手動逃生口（VPS 跑 roster_sync → 本機 pull，見 `.claude/commands/sync-roster.md`）
- VPS 連線資訊見 `~/.claude/projects/-Users-linshuhuan-mywork-mlb-fantasy/memory/reference_vps.md`

### 檔案索引

> 本表只列耐久檔（腳本 / evergreen 設計 / source-of-truth doc）。handoff 等過渡文件**不進此表** — active 進「待辦」、done 即刪、`glob docs/handoff-*` 可尋。

| 文件 | 用途 |
|------|------|
| `bin/vps-run.sh` | SSH 到 VPS 的 timeout + retry wrapper（本機↔VPS 路徑間歇丟包，見 `issues/vps-ssh-handshake-hang.md`）。`bash bin/vps-run.sh [--no-retry] '<remote cmd>'`，純讀指令會 retry、寫檔/git 走 `--no-retry`。skill 的 SSH step 與本機手動 VPS 指令都走它 |
| `hooks/sync-mirror.mjs` | SessionStart hook（roster 新鮮度 pipeline 第 1 層）— 開場 `git fetch origin master`，master+乾淨+可 ff 時自動 `pull --ff-only` 拉進 VPS cron 已同步的最新 roster_config.json，否則只警告。純 git 走 GitHub、不碰 VPS SSH / Yahoo。註冊於 `.claude/settings.json`。詳見「執行環境」段 |
| `daily-advisor/daily_advisor.py` | 每日戰報（速報 TW 22:15 + 最終報 TW 05:00） |
| `daily-advisor/fa_scan.py` | FA 市場分析唯一入口（每日 Batter+SP 並行 / 週一 RP / snapshot-only） |
| `daily-advisor/fa_compute.py` | Python 機械計算層（B2 thin SP：anchor_filter + 5-slot Sum 排序 + 2026-only ✅⚠️ tags / Batter v4 thin：Sum ≥25 filter） |
| `daily-advisor/anchor_filter.py` | SP B2 thin pure function（cant_cut + weekly_anchor_sp 名單，accent/apostrophe/case-insensitive 名稱比對）— `pick_weakest_v4_sp` 入口單一 call site |
| `daily-advisor/_phase6_sp.py` | SP B2 2-step single-LLM orchestrator（Step A rank+classify → Step B verdict；JSON validation + 1 retry + Telegram alert + fall-through pass）|
| `daily-advisor/prompt_sp_b2_step_a.txt` | B2 Step A prompt — my-team rank P1-P3 + FA classify worth/borderline/not_worth |
| `daily-advisor/prompt_sp_b2_step_b.txt` | B2 Step B prompt — 讀 Step A JSON + full slim pool → drop_X_add_Y / watch / pass verdict |
| `daily-advisor/git_sync.py` | cron 腳本共用的 git 同步 helper — `pull_rebase_with_recovery()` 自動修復「未追蹤檔與上游同路徑碰撞」（內容相同才整批移除重試，不同則中止報警）。fa_scan / roster_sync / weekly_review import 用，`cron_capture_payload.sh` + `cron_backtest.sh` 走 CLI（`python3 git_sync.py REPO_ROOT`，exit 0=ok / 2=fail）。背景見 `docs/handoff-vps-git-sync-fix.md` |
| `daily-advisor/cron_backtest.sh` | B2 backtest 週日 cron wrapper（issue 025 補上）— git_sync.py pull → `backtest_track.py --days 7 --update-doc` → 若 `docs/sp-decisions-backtest.md` 變更則 commit/push origin master。Exit code: 0 ok / 2 pull failure / 3 push failure。Cron: `0 6 * * 0 root ...`（UTC，= TW 14:00 週日）|
| `daily-advisor/tests/test_git_sync.py` | git_sync 單元 + 整合測試（11 cases — parse_blocking_files 純函式 5 + 真 git repo 整合 6 涵蓋 clean pull / 同檔自動修復 / 異檔中止 / all-or-nothing 部分相符 / CLI exit code） |
| `daily-advisor/tests/test_fa_compute.py` | fa_compute 單元測試（85 cases 覆蓋百分位分桶 + 四因子 + 標籤 + fixture 回歸） |
| `daily-advisor/stream_sp_scan.py` | `/stream-sp` skill Step 2-6 機械層（TDD 72 tests）— schedule parse + Yahoo FA cross-check + v4 5-slot enrich + opener filter + 對手 14d + 對手 vs SP 慣用手 OPS（`vs_hand_2026`，PA<400 自動 fallback 季全 OPS + `low_pa_fallback` flag）+ `sample_warning` 2026 樣本信心 tag（BBE<30 AND GS<6 → `"low"`；其餘 BBE≤80 OR GS≤12 → `"medium"`；BBE>80 AND GS>12 → `"none"`；v4 unavailable → null。AND-for-low，**機械層不 demote verdict**，僅供 LLM 信心校正用）+ `--pending-file` 補查模式自動 diff（issue 014，emit top-level `pending_diff` key — 4 桶 still_starting/lost_to_others/replaced/no_longer_scheduled）→ JSON。CLI: `python3 stream_sp_scan.py --et-dates YYYY-MM-DD[,YYYY-MM-DD] [--pending-file PATH]`。skill 觸發 / 非 cron。e2e ~5s |
| `daily-advisor/tests/test_stream_sp_scan.py` | stream_sp_scan 單元測試（72 cases 覆蓋 classify_opener / tier_opponent / parse_schedule / cross_check_fa / _enrich_v4 / _apply_vs_hand_gate / compute_sample_warning AND-for-low + 三軸邊界 / scan 注入 Fetchers 端到端 + vs_hand sample gate boundary + sample_warning low/medium/none/v4-unavailable + compute_pending_diff 四桶 + homonym 同名邊界 + pending_diff emission contract）|
| `daily-advisor/pending_parser.py` | `/stream-sp` 補查模式 pending file parser（issue 014，TDD 16 tests）— pure-function 解析 `stream-sp-pending.md` 的 H2 `## ET YYYY-MM-DD` section 結構，輸出 `{et_date: {tbd_games, evaluations}}`，stream_sp_scan.py `--pending-file` 用來算 pending_diff。Corrupt schema graceful skip（free-form 備註 / 缺欄 row / malformed markdown 不 raise）|
| `daily-advisor/tests/test_pending_parser.py` | pending_parser 單元測試（16 cases 覆蓋 empty / no-H2 / H2 無 subsection / 非 ET H2 ignored / eval row home+away / 多 row 順序 / header+separator skipped / malformed team cell skipped / 太少 cells skipped / TBD home+away+both / 空 TBD 標記 skipped / 備註段 bullet 不誤抓 / 多 ET dates isolated / 真實 stream-sp-pending.md fixture 回歸）|
| `daily-advisor/mlb_query.py` | `/stream-sp-deep` skill 用的 MLB Stats API helper — `gamelog_with_qs(mlb_id, season)` 加 ip_decimal+qs 欄；`opponent_context(team_id, end_date, sp_id)` 一次回 7d/14d/30d 趨勢 + vs SP 慣用手 split（pitchHand 內部 resolve）；`deep_batch(players)` orchestrator（issue 016）把 N 位 SP 深評壓成 1 個 SSH 批次（loop call 既有 helpers，不重寫 fetch）+ emit 7-column `comparison_table` raw JSON 讓 deep skill §4 不再手填。CLI: `python3 mlb_query.py deep --players ID1,ID2 --et-dates D1,D2 [--opp-teams T1,T2] [--sp-names "N1\|N2"] [--opp-abbrs A1,A2] [--sum26 S1,S2] [--sum25 S1,S2] [--pretty]`。Partial failure: 單 SP fetch 失敗 → 該 SP `by_player[id]={"error":...}`；`MlbIdNotFoundError` 整批 raise（避免靜默丟失）。Pure functions: parse_ip / is_quality_start 可單測。Skill 觸發 / 非 cron。 |
| `daily-advisor/tests/test_mlb_query.py` | mlb_query 單元測試（23 cases 覆蓋 parse_ip 5 boundary / is_quality_start 3 boundary 含 (5.667, 0 ER)→False 防 5⅔ IP 誤判為 QS / gamelog_with_qs + opponent_context orchestrators 注入 mock fetcher / deep_batch 11 cases — shape + headers 固定順序 + 空 input + 順序保證 + 多 et-date / MlbIdNotFoundError raise / partial failure isolation / TimeoutError isolation / 30d→7d Δ + vs hand 格式 / floor risk hint 兩 collapse vs 一 collapse 高 ERA）|
| `daily-advisor/rp_svh_scan.py` | `/rp-svh` skill 機械層（TDD 43 tests）— production-first：MLB byDateRange 全聯盟 14d SV+H≥floor → Yahoo FA 交叉 → 三軸 rank-sum（BB/9 · whiff% · 30d SV+H）top-N → incumbent benchmark + 角色訊號 → JSON。CLI: `python3 rp_svh_scan.py [--floor N] [--top N] [--date YYYY-MM-DD] --pretty`。skill 觸發 / 非 cron |
| `daily-advisor/tests/test_rp_svh_scan.py` | rp_svh_scan 單元測試（43 cases 覆蓋 parse_svh_leaderboard / _normalize / filter_fa_candidates / rank_avg 含 tie+None / rank_sum_select 含 cutoff 並列 / pick_incumbent / recent_svh / count_team_games / scan 注入 Fetchers 端到端） |
| `daily-advisor/savant_rolling.py` | 14d Savant rolling 抓取（cron TW 12:00，產出 `savant_rolling.json` 供 fa_scan + daily_advisor 讀取） |
| `daily-advisor/roster_config.json` | 陣容唯一來源（球員名單 + ID + 位置 + 去年數據 + Yahoo 格位 + MLB 狀態） |
| `waiver-log.md` | 球員追蹤（FA 觀察中 / 隊上觀察 / 已結案）— 打者 / SP |
| `waiver-log-rp.md` | RP-SV+H 子系統球員追蹤（隊上 RP / FA 觀察中 / 已結案）|
| `week-reviews.md` | 累積式週覆盤記錄 |
| `league-scouting.md` | 聯賽 12 隊 GM 策略分析 |
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點 |
| `docs/architecture.md` | 系統架構資料流圖（CLAUDE.md / daily_advisor / fa_scan / roster_config / waiver-log 讀寫關係） |
| `docs/streaming-sp-playbook.md` | 串流 SP 詳細手冊（mental model / 決策規則 / 操作流程） — 預設不串流，需要時才查 |
| `docs/rp-svh-metrics.md` | **RP-SV+H 評估 SOP 唯一規格依據** — production-first 大名單產生 / 三軸 rank-sum 候選池縮減 / LLM 層輸入設計。`/rp-svh` skill 引用此處 |
| `issues/rp-svh-sop.md` | RP-SV+H SOP 落地規劃 issue（A 機械層 / B skill / C 整合退役）— 8 個開放決策 2026-05-19 定案 |
| `docs/player-eval-sp.md` | `/player-eval` skill 的 SP 子流程（2026-05-09 從 SKILL.md 抽出 + 升級）— 21d xwOBACON Δ / IP/Team_G / 3 年 pitch arsenal / vs L/R splits 為必做；SP brand bias 觸發 + 5 條 decisive signals 走雙條件確認（避免 RP↔SP 角色變化誤判）|
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考 |
| `daily-advisor/calc_percentiles_2026.py` | 百分位分布計算工具（Week 6-8 更新 2026 百分位表時使用） |
| `daily-advisor/calc_v4_percentiles.py` | v4 框架 2025 SP 百分位計算（IP/GS / Whiff% / BB/9 / GB% / xwOBACON；n=178/115）|
| `daily-advisor/sp_data_fetchers.py` | Savant + MLB Stats API fetcher 模組（`assemble_data` + 4 個 fetcher），供 `_phase6_sp.py` + `backfill_prior_stats_v4.py` 使用。前身為 `fa_scan_v4.py` CLI 工具（issue 004 退役 CLI，留下 fetcher） |
| `daily-advisor/backfill_prior_stats_v4.py` | v4 cutover 前置：把 2025 `whiff_pct` / `gb_pct` / `xwobacon` backfill 進 roster_config.json（reuse `sp_data_fetchers`，idempotent，新進 SP 也可跑） |
| `daily-advisor/_tools/_trade_lookup.py` | 聯盟 roster 掃描（隊伍查詢 / 守位覆蓋 / 位置過剩掃描 / 球員 7-cat 比較） |
| `daily-advisor/_tools/_trade_batter_rank.py` | 交易打者排名掃描（目標打者 vs 11 隊全打者 wRC+ 排名，找交易候選隊伍） |
| `docs/sp-framework-v4-balanced.md` | **SP 評估 v4 設計定稿（5-slot balanced Sum + Rotation gate pre-filter + 時間尺度分層）— B2 仍用此 5-slot 指標** |
| `docs/sp-b2-cutover-design.md` | **SP B2 cutover 設計定稿（current source of truth）— thin mechanical + 2-step single-LLM + anchor (cant_cut + weekly_anchor_sp) + backtest 監控** |
| `docs/sp-decisions-backtest.md` | SP 決策 living log（9 筆歷史決策 + 元回測機制，每 2-4 週更新「後續走勢」）|
| `docs/sp-decisions-backtest-automation.md` | SP 決策 backtest 自動化 design（2026-04-25）— Use Case B（xwOBACON 校準）待辦引用 |
| `issues/prd-sp-b2-thin.md` + `issues/017-026-*.md` | **B2 cutover PRD + 10 個 vertical slice issues**（2026-05-27 prd-to-issues 拆出）|
| 歷史設計文件（已 superseded/退役，內容仍在 disk，glob `docs/`+`issues/` 可尋）| `fa_scan-claude-decision-layer-design`（Phase 6 multi-agent → B2 已改 single-LLM）· `v4-cutover-plan`（v4→B1→B2 早過完）· `phase6-multi-agent-spike` · `savant-xwobacon-endpoint-research`（finding 已實作 `621a5d2`）· `savant-smoke-test-design` · `sp-b1-cutover-design` · `issues/prd.md`+`001-009`（B1 cutover）|

## 待辦

- [ ] **Roster freshness pipeline — 確認 6/3 次日生效 claim 自動同步**（2026-06-02 修復後被動觀察）：`classify_empty_diff` 的 advance_alert 分支 2026-06-02 在 prod 首次觸發（Telegram 警告），但根因**不是** read-after-write lag，而是先前沒考慮到的 **Daily-Tomorrow 次日生效 claim**：Walker Buehler waiver claim（drop Trevor McDonald）於 6/2 07:12 UTC 以當天時間戳記錄為 successful，但 roster 效果到 ET 6/3 才反映（`fetch_full_roster` 預設查 today-in-ET，swap 在日期翻轉前對 diff 隱形）。原 `MAX_ROSTER_LAG_SECONDS=2h` 在次日生效前就放棄、推進浮水印越過該交易 → 會永久漏掉。**已修**（commit `1a56c6f`）：窗口拉到 30h（次日生效 + slack），retry path 靜默重試到 ET 日期翻轉；已回退 VPS `.last_sync` 到 1780384367 重新曝光該交易，dry-run 確認走 retry 不 advance_alert。**剩餘被動觀察**：6/3 04:07 UTC（= 12:07 TW）首班 cron 後，確認 config 自動 +Buehler / -McDonald + git auto-commit + Telegram 通知（查 `/var/log/roster-sync.log` 或 git log）。若沒同步，查 log。
- [ ] **/emerging-batter + /emerging-batter-deep skill 落地**（2026-05-14 設計定稿，跨電腦進行中）：對稱 SP 路徑，補 batter 短期決策 gap（主軸 role change detection，非 hot streak）。**進度**：Step 1（機械層 `emerging_batter_scan.py` TDD 40 tests）✅；Step 2-7（skill md / pending 檔 / e2e / 觀察期）⏳。完整 Step 進度 + 跨電腦續做 gotchas（position_saturated / team_games_window / 門檻常數）見 [`docs/emerging-batter-design.md`](docs/emerging-batter-design.md) §「落地進度」。
- [ ] **RP-SV+H SOP — 並行驗證 + 退役舊 --rp**（2026-05-19 落地）：機械層 `rp_svh_scan.py`（TDD 43 tests）+ `/rp-svh` skill 已實作（A2 `--names` accent/apostrophe 正規化 / A3 `sp_data_fetchers` saves-holds-blownSaves-SVO parse 同波完成）。8 個開放決策定案：rank-sum 軸 3 = **30d SV+H 累積**（非球隊勝率/場次數 — 3 agent 發想後選定，player-level 且與 BB/9 / whiff% 正交）、三軸等權、top-4（cutoff 並列納入）、純 skill 觸發無 cron、incumbent 比較交 LLM 自由 reasoning、趨勢訊號 out-of-scope。**剩餘**：① VPS 部署 + e2e 驗證（feat 分支 merge 後 VPS git pull）② 與舊 `fa_scan.py --rp` cron 並行 1-2 週比對（驗收：新 SOP 是否漏掉舊 scan 抓到的真候選 + verdict 是否合理）③ 通過後 C1 完全退役 `fa_scan.py` RP 殘留（grep `_run_rp_scan` / `RP_QUERIES` / `_build_rp_data` / `_fmt_roster_pitcher_rp` / `prompt_fa_scan_rp.txt` / `--rp` flag）。完整脈絡見 [`issues/rp-svh-sop.md`](issues/rp-svh-sop.md)。
- [ ] **waiver-log 新進條目 mlb_id 正確性驗證**（進階，已根治 auto-close 端，但 NEW 入口仍可能寫錯 mlb_id）：`_update_waiver_log_locked` NEW 行走 `search_mlb_id(name)` 補 mlb_id，同名同姓仍可能取到第一個（錯的）。建議 NEW 時走 Yahoo API 交叉驗證 team / position 匹配
- [ ] **Backtest Use Case B（xwOBACON 校準）**（4-6 週數據累積後觸發）：設計參考 `docs/sp-decisions-backtest-automation.md` Use Case B。校準路徑：累積後從 GitHub Issue archive 反推 SP 21d Δ xwOBACON **絕對門檻**（例如「|Δ| ≥0.040 後續 70% 應驗 → 改門檻 0.040」），改 prompt 文字不改 code。
- [ ] **B2 backtest cron 首跑驗證（2026-05-31 TW 14:00 首跑）**：SP B2 cutover + 24-48h 監控已收尾（issue 025 closed 2026-05-31 — #255/#259/#263 三天乾淨、anchor 隱形、無 rollback）。`cron_backtest.sh`（commit `e55fbd5`，Sun 06:00 UTC）首跑就在今天 TW 14:00。**剩餘**：今晚或明早確認首跑成功 — `docs/sp-decisions-backtest.md` 應有新增段（目前最後更新 04-30）+ VPS git log 應有自動 commit；若無變更或 cron 沒跑，查 backtest log。明天週一 `/weekly-review` session 即可看到新增段。Rollback（contingency，未觸發）: `git revert -m 1 95f879a`。
- [ ] **011 stream-sp-deep e2e parity**（HITL，2026-05-26 補追蹤）：010 已 merged 半個月但 011 parity 驗證未做。對齊 2026-05-16 prior session 三 SP 深評（Cade Cavalli vs BAL / Chris Paddack vs CLE / Chris Bassitt vs WSH）— 重跑 refactored skill 與當時手算數字比對（game log / 對手 7d-14d-30d OPS / vs RHP split）。Divergence 要 root cause 文件化。詳見 [`issues/011-stream-sp-deep-e2e-parity.md`](issues/011-stream-sp-deep-e2e-parity.md)。
- [ ] **player-eval-sp.md 4 處 SSH 改 vps-run.sh wrapper**（2026-05-20 拆出 issue，2026-05-26 補追蹤）：F2 wrapper 已上但 `docs/player-eval-sp.md` 4 處裸 SSH（含 2 處 `python3 << EOF` here-doc）未納入。`/player-eval` 是高頻 skill 受同一 SSH handshake 卡死影響。Here-doc 經多層解析 quoting 存活率低，需轉 VPS 端腳本後再納入。詳見 [`issues/player-eval-sp-ssh-wrapper.md`](issues/player-eval-sp-ssh-wrapper.md)。
- [ ] **SP / Batter 框架對稱性檢視**：SP 走過 2026-05-26 B1 cutover（multi-agent + 5-slot v4）→ 2026-05-28 B2 cutover（thin mechanical + 2-step single-LLM）。Batter 仍是 v4 thin。原 batter Phase 6 multi-agent 計畫上線時要重評：是否仍按原計畫升 batter，或 batter 留 thin（已對稱於 B2，無需動）。
- [ ] **preview 加入聯盟 scoreboard**：用 `yahoo_query.py scoreboard` 邏輯存入 JSON，預測時有數據基礎
- [ ] Week 6-8：更新百分位表為 2026 賽季數據（CLAUDE.md + daily_advisor.py + prompt 檔，腳本 `calc_percentiles_2026.py` 已備好）
- [ ] **交易掃描工具**：`_trade_batter_rank.py` 已完成（wRC+ 排名掃描）。待擴充：SP 端掃描（目標 SP vs 對方隊 SP 排名）、自動交叉比對「我方打者在對方排 ≤8 + 對方 SP 品質 > Detmers」
