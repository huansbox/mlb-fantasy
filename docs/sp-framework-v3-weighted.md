# SP 評估框架 v3 — Impact-Weighted Scoring

> **Status**: 設計階段（2026-04-23 提出）。實作前需確認 BB 指標選擇、百分位表、回測結果。未實作前，CLAUDE.md 的 v2 框架仍是 live rules。

## 動機

### v2 框架的兩層問題

**問題 1：核心 3 指標不獨立**（維度重複投票）

v2 Sum 使用 xERA + xwOBA + HH%，三者底層輸入高度相似：

| 指標對 | 相關性 | 獨立訊息 |
|--------|--------|---------|
| xERA vs xwOBA | r ~0.95+ | ~5% |
| xwOBA vs HH% | r ~0.7-0.8 | ~25-30% |

真實獨立維度 ≈ 1.3-1.5 個「contact-adjusted quality」，不是 3 個。Sum 最大 30 分裡有 ~15 分是重複計算。

**問題 2：產量維度缺失**

核心 3 指標全是「被打品質」單一面向，忽略 7×7 H2H 計分類別結構：

| 計分類別 | v2 框架有捕捉嗎？ |
|----------|-----------------|
| ERA | ✅ xERA / xwOBA |
| WHIP | ⚠️ 部分（xwOBA 含 BB 但 weight 低）|
| K | ❌ K/9 僅為「輔助指標」 |
| IP | ❌ IP/GS 僅為 urgency 因子 |
| QS | ❌ 間接（IP/GS 透過 urgency）|
| W | ❌ 球隊強弱不計入 |

### Nola vs Meyer 實戰揭露

04-22 fa_scan 判 Meyer Sum 17 vs Nola 11 = 差 +6，推薦「取代」。但實際比較：

| 面向 | Nola | Meyer | v2 Sum 反映？ |
|------|------|-------|--------------|
| Contact 品質 | xERA 4.70 | xERA 4.39 | ✅ Meyer 勝 |
| K 產能 | K/9 9.79 | K/9 10.08 | ❌ 只差 0.3，Sum 沒抓 |
| IP 產能 | IP/GS 5.24 | IP/GS 4.86 | ❌ Nola 贏沒反映 |
| QS 產能 | 2/5 | 0/5 | ❌ 結構差異沒反映 |

結果：Sum 看到 Meyer 品質略勝 → 「slam dunk 升級」；實際 counting 類別 Nola 贏。三視角重評後降為「邊際升級 → hold 觀察」。

## 核心設計

### 四指標 Impact-Weighted Sum

每個指標權重 = 影響類別數 × 影響強度：

| 指標 | 權重 | 涵蓋類別 | 角色 |
|------|------|---------|------|
| **xwOBA allowed** | 10 | ERA + QS 品質 + WHIP H 端 | 品質主軸 |
| **IP/GS** | 7 | QS 深度 + IP 單場 | 深度主軸 |
| **K/9** | 7 | K rate（核心計分類別）| K 產能 |
| **BB/9** | 5 | WHIP BB 端 | Command 補強 |

**總分 0-29**（不整齊但合理 — 反映實際影響力而非視覺整齊）

### 打分表

**xwOBA allowed**（10 分，數值越低越好）— 沿用 2025 SP 百分位：

| 百分位 | xwOBA | 分數 |
|--------|-------|------|
| >P90 | <.270 | 10 |
| P80-90 | .270-.289 | 9 |
| P70-80 | .289-.301 | 8 |
| P60-70 | .301-.312 | 7 |
| P50-60 | .312-.322 | 6 |
| P40-50 | .322-.332 | 5 |
| P25-40 | .332-.361 | 3 |
| <P25 | >.361 | 1 |

**IP/GS**（7 分）— 2025 分布集中，用三級 + 細分：

| IP/GS | 等級 | 分數 |
|-------|------|------|
| >6.0 | 深投 | 7 |
| 5.7-6.0 | 偏深 | 6 |
| 5.3-5.7 | 一般 | 5 |
| 5.0-5.3 | 短局邊緣 | 3 |
| 4.5-5.0 | 短局 | 1 |
| <4.5 | 極短 | 0 |

**K/9**（7 分，數值越高越好）— 2025 SP 百分位：

| 百分位 | K/9 | 分數 |
|--------|-----|------|
| >P90 | >11.47 | 7 |
| P80-90 | 10.39-11.47 | 6 |
| P70-80 | 9.75-10.39 | 5 |
| P60-70 | 9.23-9.75 | 4 |
| P50-60 | 8.70-9.23 | 3 |
| P40-50 | 8.24-8.70 | 2 |
| P25-40 | 7.51-8.24 | 1 |
| <P25 | <7.51 | 0 |

**BB/9**（5 分，數值越低越好）— 2025 SP 百分位（需驗證確切值，暫估）：

| BB/9 | 分數 |
|------|------|
| <2.0 | 5 |
| 2.0-2.5 | 4 |
| 2.5-3.0 | 3 |
| 3.0-3.5 | 2 |
| 3.5-4.0 | 1 |
| >4.0 | 0 |

> **TODO**: BB/9 百分位表用 2025 MLB SP 實際分布計算（`calc_percentiles_2026.py` 擴充）

### Rotation Active Gate（分流機制）

**不進 Sum 打分**，而是資格分流標籤。從 MLB API game log 計算：

- `recent_gs_14d` = 近 14 個球隊場次內 GS=1 的場次數
- `season_gs` = 季總 GS
- `debut_date` = 最早 GS 日期
- `gap_days` = 最近兩次 GS 間隔

| 狀態 | 條件 | FA 升級處理 |
|------|------|-----------|
| 🟢 **穩定** | recent_gs_14d ≥2 + season_gs ≥4 | 標準勝出門檻 |
| 🆕 **新晉** | recent_gs_14d ≥1 + season_gs ≤3 | 標準門檻 + ⚠️ 待驗 |
| 🏥 **IL 歸隊** | gap_days ≥10 + recent_gs_14d ≥1 | 標準門檻 + ⚠️ 驗證中 |
| ⚠️ **間歇** | season_gs ≥5 + recent_gs_14d <2 | 勝出門檻 **+3**（Sum 差 ≥6）|
| 🚫 **非 active** | recent_gs_14d = 0 | 不評估 add/drop |

**設計原理**：深度（IP/GS）和頻率（recent GS）分別處理，避免 IP/TG 在 debut/IL 場景被誤罰。

## 使用規則

### Step 1 — 挑最弱 N 人（Sum 升冪）

和 v2 相同流程，用新 4 指標 Sum 排序隊上 SP（排除 cant_cut + IL/NA）。取最弱 4 人作 FA 比較錨點。

**BBE 信心標記**：BBE <30 移出排序（放 `low_confidence_excluded`）。

### Step 2 — Urgency 排序（最弱 4 人內部）

四因子加總，降冪排序：

| 因子 | 條件 | 分數 |
|------|------|------|
| **2026 Sum** | <10 / 10-14 / 15-18 / 19-22 / 23-26 | +5/+4/+3/+2/+1 |
| **2025 Sum**（需 2025 IP ≥50）| ≥24 且 IP ≥50 | **Slump hold** |
|  | ≥24 但 IP <50 | +0 |
|  | 22-23 | +0 |
|  | 18-21 | +1 |
|  | <18 | +2 |
| **21d 近況**（xwOBA Δ，BBE ≥20） | 沿用 v2 ±0.035/±0.050 門檻 | -2/-1/0/+1/+2 |
| **Rotation gate**（取代 v2 的 IP/TG）| 🟢 穩定 | +2 |
|  | 🆕 新晉 / 🏥 IL 歸隊 | +0 |
|  | ⚠️ 間歇 | +1 |
|  | 🚫 非 active | 移出（不評估 drop 也不評估 add）|

**Slump hold 特例**：2025 Sum ≥24 + IP ≥50 → 獨立標註，不參與 urgency。

### Step 3 — FA 勝出門檻

| Rotation Gate | 勝出條件 |
|--------------|----------|
| 🟢 穩定 | Sum 差 ≥ 3 + ≥3 項正向（4 項中） |
| 🆕 新晉 / 🏥 IL 歸隊 | Sum 差 ≥ 3 + ≥3 項正向 + 附 ⚠️ 待驗 tag |
| ⚠️ 間歇 | Sum 差 ≥ 6 + 4 項全正向 |

「項正向」= 單項 breakdown（FA 得分 - Nola 得分）≥ 0。

### ✅/⚠️ FA Add 標籤（沿用 v2 並擴充）

**✅ 加分項**：
- ✅ 雙年菁英 — 2025 Sum ≥24 且 2025 IP ≥50
- ✅ 深投型 — IP/GS ≥6.0
- ✅ 球隊主力 — Rotation gate = 🟢
- ✅ 近況確認 — 21d Δ xwOBA ≤ -0.035
- ✅ K 壓制 — K/9 >P70（>9.75）
- ✅ 撿便宜運氣 — xERA-ERA ≤ -0.81

**⚠️ 警示項**：
- ⚠️ 短局 — IP/GS <5.0
- ⚠️ 新晉待驗 — Rotation gate = 🆕
- ⚠️ IL 驗證中 — Rotation gate = 🏥
- ⚠️ 間歇角色 — Rotation gate = ⚠️
- ⚠️ 樣本小 — BBE <30 或 IP <20（強警示，否決升級）
- ⚠️ Breakout 待驗 — 2025 Sum <18 或無 prior
- ⚠️ K 產能不足 — K/9 <P40（<8.24）
- ⚠️ Command 警示 — BB/9 >3.5
- ⚠️ 賣高運氣 — xERA-ERA ≥ +0.81
- ⚠️ 近況下滑 — 21d Δ xwOBA ≥ +0.035

**升級判斷**：≥2 ✅ 無強警示 = 立即取代；1 ✅ 無強警示 = 取代；其他 = 觀察。

## 對比 v2 框架

| 面向 | v2 | v3 |
|------|----|----|
| Sum 指標數 | 3（xERA + xwOBA + HH%） | 4（xwOBA + IP/GS + K/9 + BB/9）|
| 真實獨立維度 | ~1.3-1.5 | ~3.5-4 |
| 最大 Sum | 30 | 29 |
| 各指標權重 | 10 / 10 / 10 | 10 / 7 / 7 / 5 |
| IP 產量反映 | 僅 urgency 因子 | 直接進 Sum |
| K 產能反映 | 輔助指標（不評分）| 直接進 Sum |
| Command 反映 | xwOBA 間接 | BB/9 直接 |
| Debut/IL 處理 | IP/TG 會誤罰 | Rotation gate 分流 |

## 實作計畫

### 階段 1：設計定稿（本文件）

- [x] 指標選擇（xwOBA + IP/GS + K/9 + BB/9）
- [x] 權重設定（10/7/7/5）
- [x] Rotation gate 規則
- [ ] BB/9 百分位表（待 2025 SP 資料計算）
- [ ] 實戰樣本評估（隊上 SP + watch-list SP）← 下一步

### 階段 2：實作（下個 session）

- [ ] `fa_compute.py` 重構 `compute_sum_score` + rotation gate
- [ ] `calc_percentiles_2026.py` 補 BB/9 百分位計算
- [ ] 單元測試 (`test_fa_compute.py`) 更新 fixtures
- [ ] `fa_scan.py` Pass 2 data row 加 K/9 / BB/9 / recent_gs
- [ ] CLAUDE.md「SP 評估」章節改寫為 v3

### 階段 3：上線後校準

- [ ] 對比 v2/v3 Sum 對歷史決策影響（Nola / Meyer / Pfaadt / Patrick）
- [ ] Rotation gate 閾值微調（14d 或 21d 哪個更準）
- [ ] ⚠️ 間歇的 Sum 差 +3 懲罰是否過嚴

## 結構訊號缺失（2026-04-23 三視角回測揭露的 gaps）

用 Nola / López / Holmes 三位隊上 SP 做三 agent 平行評估（進階數據 / 傳統數據 / 印象 + 逐場），結果 **2/3 視角不同意 v3 的 drop 優先序**。詳細報告見 `docs/nola-lopez-holmes-triview-2026-04-23.md`。

v3 未涵蓋的三類訊號：

### 1. xwOBACON（on-contact xwOBA）缺失

xwOBA 是整體打席期望值（含 K + BB + 擊球），xwOBACON 專指「擊中的球」期望值。WHIP 的 H 端純粹由 xwOBACON 決定，但被 K/BB 訊號稀釋到 xwOBA 時會遮蔽真相。

實證：
- Nola xwOBA .342 / **xwOBACON .424（<P25 爛）**
- López xwOBA .347 / xwOBACON .388（<P25）
- Holmes xwOBA .300 / **xwOBACON .323（P55-60）**

Nola 和 López 的 xwOBA 幾乎一樣，但拆解後 Nola **on-contact 被打更慘**。xwOBA 被 Nola 較高 K% 救回來了。

**建議**：考慮用 xwOBACON 取代或補充 xwOBA 在 Sum 中的角色。需 Statcast CSV 額外欄位。

### 2. 速度變化 flag 缺失

Nola 2026 FB 90.7-91.7 mph = 完全等於 2025 災難年（春訓曾回到 92.9 但已消失）。這是**物理永久退化**的證據，不會因 BABIP / slump 而回升。

v3 的 Sum 和 Step 2 urgency 都沒有速度因子。一個 BBE 76 樣本的 xwOBA 變化可能被視為 slump 或 breakout，但速度訊號可區分：
- 速度 hold + Savant 惡化 → 可能 slump（mechanics）
- 速度掉 + Savant 惡化 → 結構性退化（structural）

**建議**：加「🔻 速度警訊 flag」— 當 2026 FB 速度較 2025 全季降 ≥1.5 mph → 附結構性退化 tag，不進 Sum 但 urgency 加 +2 懲罰。

### 3. 運氣指標只做 tag 不進 Sum 的盲點

xERA-ERA 在 v2/v3 都只當 ✅/⚠️ 輔助 tag，但對 **下 2-4 週 ERA/WHIP 預測**有實質 signal：
- López xERA 3.74 / ERA 4.85 = **-1.11（P70+ 顯著撿便宜）** → ERA 會回升到 ~4
- Nola xERA 4.70 / ERA 5.06 = -0.36（中性）→ ERA 就是真實水準
- Holmes xERA 3.52 / ERA 3.42 = +0.10（中性）→ 持續

v3 用 2026 Sum 排序會把 López 排最弱（因 ERA 5.06 + BB/9 4.57），但底層 xERA 3.74 + HH% 34.9%（P85+）顯示他是**短期傷害但中期會修復**。Nola 反而是「看起來 OK 其實無法修復」的危險類型。

**建議**：Step 2 urgency 加第五因子「運氣回歸方向」：
- xERA-ERA ≤ -0.81：ERA 會回升（short-term pain）→ urgency -2
- -0.81 < xERA-ERA < +0.81：中性 → 0
- xERA-ERA ≥ +0.81：ERA 會下滑（short-term gain）→ urgency +2

## 未決問題（v3.0 → v3.1 roadmap）

1. **BB% vs BB/9**：選 BB/9（資料容易取、2025 百分位可算）。BB% 的優點是對「BB 發生頻率」更直接但需要 PA 分母，計算成本略高。
2. **xwOBA vs xERA**：選 xwOBA（不做 scale 轉換，noise 少一點）。報告顯示可並列。**v3.1 考量**：以 xwOBACON 取代 xwOBA（H 端更純粹）。
3. **HH% 去向**：降為輔助指標，不進 Sum 但 Pass 2 data row 保留（作為 WHIP H 端預警）。
4. **Rotation gate 時間窗**：14d 還是 21d？14d 對「間歇」判斷較敏感，但可能誤判剛跳過 1 場的正常 SP。待實戰校準。
5. **Step 2 urgency 的 rotation gate 分數**：+2/+1/+0 是初版，需看樣本分布調整。
6. **（新）結構訊號整合**（v3.1）：xwOBACON / 速度 flag / 運氣 urgency 三項是否納入。每個都有資料取得成本（xwOBACON 需 Savant custom CSV、速度需 pitch-level 資料、運氣已在 fa_compute）。
7. **（新）時間尺度平衡**：三視角顯示 v3 偏「當下產量」，漏了「中期回歸」和「長期結構」兩個尺度。v3.1 要嘗試把三尺度都納入（urgency factors 是 natural 家 — 近況 Δ 是中期、速度 flag 是長期、運氣是 short-term 修正）。

## 相關文件

- `CLAUDE.md` — 現行 v2 框架（live rules）
- `daily-advisor/fa_compute.py` — Sum / urgency / tags 機械層
- `daily-advisor/calc_percentiles_2026.py` — 百分位計算工具
- `daily-advisor/fa_scan.py` — 資料組裝 + Claude 文字化層
