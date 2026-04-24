# SP 評分框架 v4 — Balanced 5-Slot Scoring

> **Status**: 設計定稿（2026-04-24）。取代 v3 設計稿，未實作前 CLAUDE.md 的 v2 仍是 live rules（Phase C 實作完成後切換）。

## 設計動機

### v2 / v3 的共同問題：單一維度吃掉整體判斷

v2（xERA + xwOBA + HH%）三指標**全是 contact quality 家族**：
- 彼此相關性 r ~0.7-0.95 → 真實獨立維度僅 1.3-1.5 個
- 產量類別（IP / K / QS）完全沒抓

v3 試著補 K 和 IP（加入 K/9 + IP/GS），但 **2026-04-23 三視角回測**（Nola/López/Holmes）揭露 v3 仍有結構訊號缺失。

2026-04-24 session 中進一步追問：**Nola 是否真的該 drop？**

重新審視 Nola 當下數據：
- IP/GS 5.33（正常深度）
- Whiff% 26.5（P70-80 K 壓制仍在）
- BB/9 3.38（中下但沒崩）
- GB% 40.8（中等）
- xwOBACON .424（<P25 極差）

5 項中 3 項 P50+，1 項中下，1 項極差。**整體「當下 not that bad」**，但 v2/v3 只看 contact quality → 三項都中下 → Sum 極低 → 誤判為「結構性弱」。

### v4 核心判斷

**當下產量 vs 潛在惡化**在 SP 評估是兩種**不同時間尺度**的訊號，不該塞進同一個 Sum。

- Sum = 當下產量快照（5 個**獨立軸**反映真實產出水準）
- Tag / flag = 時序訊號（運氣、近況、速度、角色變化等，供人工判斷輔助）

## 核心設計

### Pre-filter：Rotation Gate（撈名單階段）

**不進 Sum，不進 urgency**。是資格過濾器，在撈 FA 候選清單時直接分流：

| 類別 | 條件 | 處理 |
|------|------|------|
| 🟢 **Active SP** | GS/G ≥ 0.6 **且** GS ≥ 3 | 進入 Sum 評分 |
| ⚠️ **Swingman / 新晉** | 0.3 ≤ GS/G < 0.6 或 GS ∈ {1, 2} | 進入 Sum 但附註「角色不穩 / 樣本待驗」 |
| 🚫 **Pure RP / Long relief** | GS/G < 0.3 **或** GS = 0 | 直接從 SP 池排除 |

**設計原理**：
- IP/GS 的爆點是「1 場長局的假象」（Myers 1 GS / 8 G → IP/GS 17.33 但實為 long relief）。資格過濾在源頭處理，Sum 公式不用扭曲
- v3 原本把 Rotation gate 當 Sum 因子 → 2026-04-24 session 改為 pre-filter，語意更乾淨

### Sum 評分（5 slot × 0-10 分，滿分 50）

每個指標對應 2025 MLB SP 百分位（2026 賽季中期更新為 2026 分布）：

| 百分位 | 分數 |
|--------|:---:|
| > P90 | 10 |
| P80-90 | 9 |
| P70-80 | 8 |
| P60-70 | 7 |
| P50-60 | 6 |
| P40-50 | 5 |
| P25-40 | 3 |
| < P25 | 1 |

#### 五個指標

| # | 指標 | 方向 | 主要覆蓋類別 | 角色 |
|---|------|:---:|-------------|------|
| 1 | **IP/GS** | 高越好 | IP + QS（6 IP 門檻）| 深度 |
| 2 | **Whiff%**（CSW% 代理）| 高越好 | K | K 壓制 |
| 3 | **BB/9** | 低越好 | WHIP BB 端 + ERA 間接 | 控球 |
| 4 | **GB%** | 高越好 | ERA + WHIP + QS（HR 壓制、雙殺、省球）| 球風 |
| 5 | **xwOBACON** | 低越好 | ERA + WHIP H 端 | on-contact 品質 |

**為何這五個**（乾淨版 5 agents 共識 + 與用戶討論後定案）：

| 選擇 | 落選者 | 理由 |
|------|------|------|
| Whiff% > K% > K-BB% > CSW% | | K% 是結果層 noise 大；K-BB% 和 Whiff% + BB/9 重複；CSW% 抓不到便捷資料（Savant 無單一端點），Whiff% 高相關近似 |
| BB/9 > BB% | | WHIP 公式對齊（BB/IP 直接對應 BB/9）、v2 已有腳本一致性 |
| xwOBACON > xwOBA > xERA > SIERA | | xwOBA 含 K/BB 稀釋 on-contact；xERA / SIERA 的 input 和其他 slot 重複投票 |
| GB% 獨立軸 | | 乾淨版 5 agents 之 3 獨立想到，是 v2/v3 完全沒抓的面向 |
| IP/GS > Pitches/IP | | Pitches/IP 要 pitch-level data，取得成本高；IP/GS 直觀對應 QS 門檻 |

#### 刻意排除的指標

| 不用 | 理由 |
|------|------|
| **FB 速度** | 用戶 2026-04-24 決策：不列入評分（結構性退化訊號讓人工判斷用）|
| **W / 球隊強弱** | 用戶 2026-04-24 決策：不考慮 |
| **HH% allowed**（v2 留用）| 和 xwOBACON 重複（r ~0.7）；xwOBACON 更純 |
| **Barrel% allowed**（v3 考慮）| 乾淨版只 1/5 票，已被 xwOBACON 部分含 launch angle 抓到 |
| **xERA / SIERA** | input 和其他 slot 重複投票（身高 + 體重 + BMI 類比）|
| **GS/Team_G** | 用戶 2026-04-24 決策：當後續篩選項目，不進 Sum（新秀/傷後復出會失真）|

### Pass 2 Flags / Tags（不進 Sum）

時序與結構訊號當 flag 附在 data row，供人工判斷使用：

**✅ 加分 tag**
- ✅ 雙年菁英 — 2025 Sum ≥ 40 且 2025 IP ≥ 50（v4 滿分 50，門檻約等比例 v3 的 24/30）
- ✅ 深投型 — IP/GS > 5.7
- ✅ GB 重型 — GB% > 50（壓 HR + 雙殺省球）
- ✅ K 壓制 — Whiff% > P70
- ✅ 撿便宜運氣 — xERA − ERA ≤ -0.81（P70+ 顯著）
- ✅ 近況確認 — 21d Δ xwOBACON ≤ -0.035

**⚠️ 警示 tag**
- ⚠️ 短局 — IP/GS < 5.0
- ⚠️ Swingman 角色 — Rotation gate = 黃色
- ⚠️ 新晉待驗 — GS ≤ 2
- ⚠️ 樣本小 — BBE < 30 或 IP < 20（強警示，否決 FA 升級判定）
- ⚠️ Breakout 待驗 — 2025 Sum < 25 或無 prior
- ⚠️ K 壓制不足 — Whiff% < P40
- ⚠️ Command 警示 — BB/9 > 3.5
- ⚠️ xwOBACON 極端 — <P25（Nola case）
- ⚠️ 賣高運氣 — xERA − ERA ≥ +0.81
- ⚠️ 近況下滑 — 21d Δ xwOBACON ≥ +0.035

### Step 2 — Urgency 排序（最弱 N 人內部）

保留 v2/v3 的四因子架構，但 IP/Team_G 被 Rotation gate 取代（gate 已在 pre-filter 用了，不在這裡重複）：

| 因子 | 條件 | 分數 |
|------|------|:---:|
| **2026 Sum** | < 15 / 15-22 / 23-30 / 31-38 / 39-44 | +5/+4/+3/+2/+1 |
| **2025 Sum** | ≥ 40 且 IP ≥ 50 | **Slump hold**（移出排序）|
| | ≥ 40 但 IP < 50 | +0（菁英底但低樣本）|
| | 35-39 | +0（灰色帶）|
| | 28-34 | +1 |
| | < 28 | +2（結構性確認）|
| **21d Δ xwOBACON** | ≤ -0.050（🔥強回升）| -2 |
| | -0.050 < Δ ≤ -0.035（🔥弱回升）| -1 |
| | -0.035 < Δ < +0.035（持平）| 0 |
| | +0.035 ≤ Δ < +0.050（❄️弱劣化）| +1 |
| | Δ ≥ +0.050（❄️強劣化）| +2 |
| **運氣回歸**（xERA − ERA）| ≤ -0.81 | -2（會回升）|
| | -0.81 < ... < +0.81 | 0 |
| | ≥ +0.81 | +2（會下滑）|

**2026-04-24 新增第 4 因子「運氣回歸」**：triview 教訓 — López xERA-ERA -1.11 意味短期 ERA 會回歸，不該急 drop。用 urgency 吸收這個訊號，Sum 保持純粹。

### Step 3 — FA 勝出門檻

FA 候選 Sum vs 現有最弱隊員 Sum 的差距判斷：

| Rotation Gate | 勝出條件 |
|--------------|----------|
| 🟢 Active | Sum 差 ≥ 5 **且** ≥ 3 項正向（5 項中）|
| ⚠️ Swingman / 新晉 | Sum 差 ≥ 8 **且** ≥ 4 項正向 + 附 ⚠️ tag |

**升級判斷規則**：
- ≥ 2 ✅ 且無強警示 = 立即取代
- 1 ✅ 無強警示 = 取代
- 其他 = 觀察

強警示 = ⚠️ 樣本小 / ⚠️ 短局 / ⚠️ 新晉待驗 其中任一。

## 對比 v2 / v3

| 面向 | v2 | v3 | v4 |
|------|----|----|----|
| Sum 指標 | xERA + xwOBA + HH% | xwOBA + IP/GS + K/9 + BB/9 | **IP/GS + Whiff% + BB/9 + GB% + xwOBACON** |
| Sum 最大 | 30 | 29 | **50** |
| 真實獨立維度 | ~1.3-1.5 | ~3.5-4 | ~4.5-5 |
| Contact quality 處理 | xwOBA（含 K/BB 稀釋）| xwOBA（同樣問題）| **xwOBACON（排除 K/BB，最純）**|
| K 面向 | ❌ 無 | K/9（結果）| **Whiff%（前驅，比 K/9 穩）**|
| 控球 | ❌ 無 | BB/9 | BB/9 |
| 球風 | ❌ 無 | ❌ 無 | **GB%（v2/v3 盲點）**|
| 產量 | 🔸 urgency 有 IP/TG | IP/GS + GS/TG | IP/GS（GS/TG 改 pre-filter）|
| 角色處理 | 無機制 | Rotation gate（進 urgency）| **Rotation gate 改 pre-filter（不扭曲 Sum）**|
| 運氣訊號 | ✅/⚠️ tag | ✅/⚠️ tag | **進 urgency（第 4 因子）+ tag**|
| 速度退化 | 人工 | 人工 | 人工（用戶排除進 Sum）|

## 2026-04-24 全 18 SP 實戰驗證

使用 Savant `custom` + `batted-ball` + `pitch-arsenal-stats` + MLB Stats API 資料，v4 Sum 排序：

```
隊上前段（Sum ≥ 40）：Messick 44 / Skubal 43 / Sale 42 / Detmers 41
隊上中段：Holmes 31
隊上低段：Cantillo 25 / Nola 23 / Ragans 16 / Lopez 14 / Kelly 14
(以上都是 🟢 active SP 狀態排序；Kelly BBE 35 低信心附註)

FA Active 候選：Griffin 31 / Fedde 33（Rotation gate 邊緣）
FA Swingman（附警示）：Pfaadt 40 / Ginn 40（IP/GS 高但 GS/G < 0.6）
FA Pure RP / Long relief（排除）：Brown, Myers, Urena, Horton
```

### 驗證結論

1. **Nola 案（triview 原始分歧）**：v4 Sum 23，比 López 14 高 9 分 → 判定「hold, not cut」
   - 和用戶 2026-04-24 決策一致（hold 2 場觀察）
   - v2/v3 因過度依賴 contact quality 家族會誤判 Nola 為「結構性弱」，v4 反映真實「當下中下但還可用」
2. **Messick 44 / Skubal 43 / Sale 42 / Detmers 41**：菁英 SP 仍在 Sum 前段，GB% 的納入沒戲劇性打亂排序
3. **Detmers 41**：$0 FAAB 取得後三項 P80+ → v4 確認「大勝 add」歷史判斷
4. **Ragans 16**：Slump hold 候選，BB/9 7.71 極端 + xwOBACON .452 極差 → Sum 低符合預期，但 2025 Sum ≥40 會觸發 Slump hold 特例
5. **Lopez 14**：當下 4/5 指標輸 Nola → Sum 最低，但 xERA-ERA -1.11 → urgency 第 4 因子會減 2 分，降低 drop 優先度

## 實作計畫（Phase C）

### 階段 5.1：資料抓取擴充（fa_scan.py）

- [ ] 新增 `fetch_savant_custom_xwobacon()` — 從 custom leaderboard 抓 xwOBACON
- [ ] 新增 `fetch_savant_batted_ball_gb()` — 從 batted-ball endpoint 抓 gb_rate
- [ ] 新增 `fetch_savant_whiff_aggregated()` — 從 pitch-arsenal-stats 按球種加權 Whiff%
- [ ] 延用現有 `fetch_pitcher_game_log()` 算 IP/GS 和 BB/9（已有基礎）
- [ ] 保留 xERA / xwOBA allowed / HH% / Barrel% 欄位作為 Pass 2 data row（不進 Sum）

### 階段 5.2：Sum 邏輯重寫（fa_compute.py）

- [ ] 改 `_SP_METRICS` 從 `(xera, xwoba, hh_pct)` → `(ipgs, whiff, bb9, gb_pct, xwobacon)`
- [ ] 改百分位分桶表（2025 實算值，Phase B 產出）
- [ ] 改 `compute_sum_score()` SP 分支為 5 slot × 10 分
- [ ] 改 `compute_urgency()` — 移除 IP/TG 因子，加「運氣回歸」因子
- [ ] 改 `compute_fa_tags()` — 新增 GB% / xwOBACON / Swingman / 運氣方向相關 tag
- [ ] 加 Rotation gate pre-filter 函式（前置於 pick_weakest）

### 階段 5.3：資料結構變更

v2 data row：
```json
{ "xera": 4.67, "xwoba": 0.342, "hh_pct": 42.1, "bbe": 76 }
```

v4 data row：
```json
{
  "ip_gs": 5.33, "whiff_pct": 26.5, "bb9": 3.38,
  "gb_pct": 40.8, "xwobacon": 0.424,
  "bbe": 76, "ip": 26.67, "gs": 5, "g": 5,
  "xera": 4.67, "era": 5.06,  // tag only, not in Sum
  "rotation_gate": "active"
}
```

### 階段 5.4：測試 + 切換

- [ ] 更新 `test_fa_compute.py`（85 cases 多數會需要改 SP 相關的 fixture）
- [ ] 加 feature flag `SP_FRAMEWORK_VERSION = "v4"` 環境變數（"v2" fallback 備用）
- [ ] v4 上線前並行跑 v2 / v4 Sum 2-3 天，人工對照
- [ ] Cutover 後移除 v2 code

### 階段 5.5：CLAUDE.md 更新

- [ ] 「SP 評估」章節改寫為 v4
- [ ] 百分位表補 Whiff% / GB% / xwOBACON / BB/9 / IP/GS 的 2025 SP 分布
- [ ] 進行中補強行動章節更新為 v4 解讀

## 未決問題（v4.x roadmap）

1. **Whiff% vs CSW%**：目前選 Whiff%（Savant pitch-arsenal-stats 有現成端點）。CSW% 需要 pitch-level 資料，成本高。若 Whiff% 驗證出現偏差（例如 called strike 主導的投手被低估），再考慮轉 CSW%
2. **BB/9 百分位表 live 校準**：v4 上線後 2-4 週看實測分布，調整閾值
3. **21d Δ xwOBACON 門檻**：沿用 v2/v3 的 ±0.035/±0.050，Phase 2 後 2 週收集實測校準
4. **Slump hold 門檻調整**：v4 滿分從 30 → 50，2025 Sum ≥ 40 是 v3 的 24/30 等比例，但 2025 SP 分布可能不等比例 → 實算後微調
5. **🟢/🟡 Rotation gate 門檻**：0.6 和 0.3 是初版，需看 2025/2026 分布調整
6. **FA 勝出門檻 Sum 差 ≥ 5**：v4 最大差距比 v3 大（滿分 50 vs 29），需驗證 5 分是否合理「有意義差距」

## 結構訊號分層（v4 定案）

2026-04-23 triview 揭露 SP 評估有三個時間尺度，v4 各自分到不同層：

| 時間尺度 | 訊號 | v4 放哪 |
|---------|------|---------|
| **當下產量**（本週 H2H） | 5 slot Sum | Sum 直接反映 |
| **中期回歸**（2-4 週） | xERA-ERA 運氣 / 21d Δ xwOBACON | Urgency 因子 + Pass 2 tag |
| **長期結構**（整季） | FB 速度 / xwOBACON 歷史趨勢 / 傷病角色 | 人工判斷層（waiver-log 隊上觀察）|

**分層原則**：Sum 不混時間尺度，每層有自己的機制。triview 的分歧來自三視角各自看不同時間尺度，v4 把這些訊號分配到對應層級。

## 相關文件

- `CLAUDE.md` — 現行 v2 框架（live rules，Phase C 實作前）
- `docs/sp-framework-v3-weighted.md` — v3 設計稿（已被 v4 取代）
- `docs/nola-lopez-holmes-triview-2026-04-23.md` — 三視角回測材料
- `docs/sp-decisions-backtest.md` — SP 決策 living log
- `daily-advisor/fa_compute.py` — Python 機械計算層（待 Phase C 改寫）
- `daily-advisor/fa_scan.py` — 資料抓取 + Claude 文字化（待 Phase C 擴充）
- `daily-advisor/calc_percentiles_2026.py` — 百分位計算工具（Phase B 擴充）
