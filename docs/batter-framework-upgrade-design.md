# Batter Framework 升級 Design — Raw Data + Multi-Agent 自由 Reasoning

> **Status**: 設計定稿（2026-04-28）。本文對齊不寫 code — 機械層精簡可立即動工，多 agent 層待 SP v4 multi-agent infrastructure 證明穩定後接續。
>
> **Background**: 2026-04-28 session 中兩輪 ad-hoc 3 agent 投票實驗暴露 fa_scan 季 Sum 對 H2H 一週決策的盲點。FA 端（Cam Smith 季 Sum 28 但 14d OPS .340）與 Anchor 端（Albies 季 Sum 8 但 14d OPS .947）兩個 case 同時印證問題。

---

## 1. 結論 / 設計核心

本升級的核心是把**機械評分壓到最少 — 機械層只負責 hard rule 排除 + Sum 用作門檻 filter，但 Sum 不出現在 output**，把所有「權衡判斷」全交給 **multi-agent 自由 reasoning**，讓 agent 純看 raw + percentile + 14d trad 自行排序。

### 1.1 機械層 vs Agent 層分工

| 層 | 職責 | 輸出給 agent 看的 |
|---|---|---|
| **機械層**（Python）| Hard rule 排除 / 計算 Sum 作 ≥25 filter / enrich raw + percentile | **無 Sum，無 score** — 只給 raw 數值 + 各 metric percentile + 14d trad |
| **Multi-Agent 層** | 排序 / 權衡 / 決策（drop / add / watch） | 共識 + dissent flag + 動作建議 |

Sum **只在機械層內部使用**（過濾門檻），不暴露給 agent — 強制 agent 從 raw + percentile 自行判斷，不依賴 aggregated 數字。

### 1.2 拋棄的設計

| 拋棄 | 為什麼 |
|---|---|
| **urgency 4-factor 計分** | 三個 factor 的門檻都是經驗值（14d Δ ±0.035/0.050 / PA-TG ≥3.5 / 2025 Sum ≥24）— 沒實證 calibration，false precision |
| **2×2 矩陣強制框架** | 強加單一判斷邏輯反而限制 agent 思維；let agents 從 raw 看資料各自 reasoning |
| **✅/⚠️ tag 層** | binary summary 損失訊息（P75 跟 P95 都是 ✅）；raw + percentile 給 agent 反而更精準 |
| **PA/TG 進 urgency** | 隊上 active batter 同質性高（PA/TG 都在 3.5-4.5）→ 此 factor 對所有人 +2 = 沒區分能力 |
| **Sum / score 出現在 anchor output** | Sum 是 aggregated proxy，會 anchor agent 思維；agent 應從 3 metric raw + percentile 自行 reason |
| **守位 / selected_pos / status 進 anchor 評估** | 評價只看打擊數據；BN 與否、DTD 狀態跟當天比賽有關，不是球員品質判斷 |
| **Slump hold 自動偵測（2025 Sum ≥24）** | 改為 hardcoded `cant_cut` 名單統一管理（不區分「skill cant_cut」vs「slump hold cant_cut」）|

### 1.3 保留的機械層

| 保留 | 為什麼 |
|---|---|
| **Sum 計算**（內部用）| 用作 pick_weakest 的 ≥25 門檻 filter，但**不暴露** |
| **`cant_cut` 名單排除** | 從 league config（hardcoded：Jazz Chisholm + Manny Machado + Skubal-SP-only）|
| **BBE 小樣本排除**（batter <40） | Hard rule — 剛 call up / 受傷 1 週球員不該作 anchor。跟 SP <30 對齊提高為 batter <40 |
| **2026 Sum ≥25 排除** | Hard rule — 當下表現 P75+ 全方位 = 不該列 drop 候選 |

---

## 2. 為什麼（Motivation）

### 2.1 今天兩輪 ad-hoc 投票對比

**Round 1 — 僅 fa_scan context（Sum + xwOBA + tag）**：
- 共識 ADD_CAM_SMITH 3-0（confidence high）
- 理由：Sum 28 vs Albies 8 全面碾壓 + BB% 11.3 補結構性 BB 弱

**Round 2 — 加 14d trad / K% spike / %owned trend**：
- 共識 WATCH 3-0（confidence medium）
- 理由：Albies 14d OPS .947 火燙不該 drop / Cam Smith 14d .340 接刀

**同一群 agent，相同提問模板，僅差 context 完整度，結論完全反轉**。證實 14d trad 對 H2H 一週決策是 first-order signal。

### 2.2 暴露的 5 個盲點

| # | 盲點 | 證據 | 對決策影響 |
|---|---|---|---|
| 1 | Sum 季線滯後 | Albies Sum 8 但 14d .947 / Cam Smith Sum 28 但 14d .340 | drop hot / add slumping |
| 2 | K% spike 警訊未進 fa_scan | C. Walker +5.9pp 沒被 flag / Cam Smith +1.7pp 邊界沒查 | 添加正在受傷球員 |
| 3 | %owned 看 snapshot 不看 trend | Ramos 46→47 plateau vs Cortes 1→14 explosive vs Cam Smith 45→41 dropping | 看不到聯盟動態 |
| 4 | Anchor 純 season Sum 排序 | Altuve 14d OPS .559 ❄️ 隊上最弱但季 Sum 不夠低，不在 P1-P4 | 真實當週傷口隱形 |
| 5 | 單 LLM 易被「窗口壓力」拉走 | Round 1 全 ADD_CAM_SMITH（接刀） | 失去 multi-agent 共識保護 |

盲點 1+2+3+4 是「資料層」 — 解法是補 raw context。盲點 5 是「決策層」 — 解法是 multi-agent。本升級兩者都做。

### 2.3 為什麼 raw + percentile + 自由 reasoning + 不暴露 Sum

| 設計選擇 | 理由 |
|---|---|
| **raw 數值不計分** | 計分桶（如 1/3/5/6/7/8/9/10）有資訊損失 + 邊界球員兩側 1 桶差被放大 / 縮小不對稱 |
| **百分位 rank 給** | 提供「跟全聯盟比站哪」的 anchor，agent 不需自己 calibrate 量級 |
| **不暴露 Sum** | Sum 是 aggregate，會 anchor agent 思維；強迫 agent 從 3 metric raw + percentile 自行權衡 |
| **不強制 2×2 矩陣** | 強加判斷框架反而限制 agent 思維；發散後共識 = 高信心，分歧 = 該 case 真的模糊 |
| **不加 tag** | binary summary 損失訊息；raw + percentile + season + 14d 完整脈絡讓 agent reason |
| **不機械算 urgency** | 4-factor 公式三個門檻都未實證 calibration，false precision；agent 有 raw + percentile 可自行權衡 |
| **守位 / status 不進 anchor 評估** | 評價只看打擊數據；BN/DTD 跟當天有沒有比賽有關，不是品質訊號 |

---

## 3. 機械層職責（精簡後）

### 3.1 pick_weakest_v4_batter

```python
def pick_weakest_v4_batter(players, cant_cut: set[str]):
    """Mechanical pre-filter only. No Sum-based ranking, no urgency.

    Filters (in order):
        1. Exclude by name from cant_cut (e.g. Jazz Chisholm, Manny Machado).
           Hardcoded in league config — no separate slump_hold mechanism.
        2. Exclude BBE <40 → low_confidence_excluded (跟 SP <30 對齊調為 batter <40)
        3. Compute 2026 Sum internally; exclude Sum ≥25 (current strong, not drop candidate).
        4. Output ALL remaining batters with Sum <25 (no count cap) — 不限人數.

    Note: IL/NA/BN/DTD 等 selected_pos / status **不過濾** — 評價只看打擊數據，
          守位/出場狀態與當天比賽有關，不是品質訊號，留給 agent 自行判斷。

    Returns:
        (weakest_pool, low_confidence_excluded)
        weakest_pool: list of enriched dicts (見 §3.2)
        low_confidence_excluded: BBE<40 移出者，僅作 metadata
    """
```

**特殊情況處理**：

| pool size | 處理 |
|---|---|
| **0 人** | 整隊 Sum 都 ≥25（隊強），fa_scan 跳過 batter drop scan，不產 P1 |
| **1-3 人** | Multi-agent step 1 任務改為「排所有」（不要求 top 3）|
| **>3 人** | 標準流程 — agent 排 top 3 |

### 3.2 enrich_for_multi_agent — anchor output schema

對每個 weakest_pool 球員 attach 完整 raw + percentile：

```json
{
  "name": "Albies",
  "team": "ATL",

  "season_2026": {
    "xwoba":      {"value": 0.290, "pctile": 35},
    "bb_pct":     {"value": 5.6,   "pctile": 22},
    "barrel_pct": {"value": 3.1,   "pctile": 18},
    "hh_pct":     {"value": 38.0,  "pctile": 40},
    "k_pct":      {"value": 12.1,  "pctile": 70},
    "ops":        {"value": 0.799, "pctile": 60},
    "pa":         320,
    "bbe":        92,
    "pa_per_tg":  4.28
  },

  "rolling_14d": {
    "ops":          {"value": 0.947, "pctile_vs_season": 88},
    "avg":          {"value": 0.363, "pctile_vs_season": 92},
    "obp":          0.383,
    "slg":          0.563,
    "hr":           2,
    "rbi":          10,
    "r":            11,
    "bb_pct":       {"value": 5.0,   "pctile_vs_season": 18},
    "k_pct":        {"value": 5.0,   "pctile_vs_season": 95},
    "k_spike_pp":   -7.1,
    "delta_xwoba":  -0.012,
    "pa":           60,
    "bbe":          30
  },

  "prior_2025": {
    "xwoba":      {"value": 0.310, "pctile": 50},
    "bb_pct":     {"value": 6.2,   "pctile": 35},
    "barrel_pct": {"value": 6.5,   "pctile": 45},
    "hh_pct":     {"value": 40.5,  "pctile": 50},
    "ops":        0.752,
    "pa":         600
  }
}
```

**明確不出現的欄位**：
- ❌ `score` / `sum`（任何年）— Sum 內部用，不暴露
- ❌ `breakdown`（per-slot scores）
- ❌ `urgency` / `factors` — 機械不算 urgency
- ❌ `add_tags` / `warn_tags` — 不加 tag 層
- ❌ `positions` / `selected_pos` — 守位資訊不進評估
- ❌ `status`（DTD/IL）— 出場狀態不進評估

### 3.3 FA pool pre-filter

跟 anchor pool 同精神，機械層 hard rule 縮 pool：

```python
def filter_fa_pool_v4_batter(yahoo_fa_list):
    """Mechanical pre-filter for FA pool.

    Filters (in order):
        1. Already rostered → 自然由 Yahoo FA list 排除（不會出現）
        2. BBE <40 → 小樣本 exclude
        3. Compute 2026 Sum internally; exclude Sum <21 (沿用 v2 P40×2 邏輯，太弱不撿)

    Note: 不依守位 filter — 多守位資格球員不該被誤排（如 Cam Smith RF + UTIL）。
          守位 fit 留給 agent 在 final decision 自行判斷。

    Returns:
        fa_pool: list of FAs surviving filters，typically 8-15 人
    """
```

**FA 跟 anchor 的 mechanical filter 差異**：

| Filter | Anchor | FA |
|---|---|---|
| `cant_cut` 名單排除 | ✅ 適用 | ❌ 不適用（FA 本來就不在我隊）|
| BBE <40 | ✅ | ✅ |
| 2026 Sum 門檻 | ≥25（強到不該 drop） | <21（弱到不該撿） |
| 守位 / selected_pos / status | ❌ 不過濾 | ❌ 不過濾 |

### 3.4 FA candidate output schema

對通過 pre-filter 的 FA attach 完整 raw + percentile（同 anchor §3.2 schema，加 FA 專屬欄位）：

```json
{
  "name": "Cam Smith",
  "team": "HOU",

  "season_2026": {...同 anchor 結構...},
  "rolling_14d": {...同 anchor 結構...},
  "prior_2025": {...同 anchor 結構...},

  "owned": {                       // ← FA 專屬
    "current_pct": 41,
    "delta_3d":    -4,
    "delta_7d":    -8,
    "shape":       "dropping"
  }
}
```

`shape` ∈ {"plateau", "rising", "explosive", "dropping"} — 純 heuristic 分類給 agent 看趨勢，不打分。

**明確不出現的欄位**（同 anchor §3.2）：
- ❌ `score` / `sum` / `breakdown` / `urgency` / tags
- ❌ `positions` — **完全無需考慮守位**，連 final decision 也不靠位置 fit 判斷

### 3.5 不做的事（機械層）

- ❌ 不算 urgency（無 4-factor sum）
- ❌ 不打 ✅/⚠️ tag
- ❌ 不應用 2×2 矩陣分類
- ❌ 不算「Sum 差 vs anchor」（讓 agent 自己看 raw 比）
- ❌ 不寫 14d Δ / K% spike / %owned 門檻判斷
- ❌ 不暴露 Sum / score 給 agent（anchor + FA 都不暴露）
- ❌ 不依守位 / selected_pos / status / positions 過濾或標記
- ❌ 不算 FA 跟 anchor 的 verdict / 不預先標 worth/borderline/not_worth（這些由 agent 在 step 3 classify 標）

---

## 4. 多 Agent 層職責

複用 SP v4 multi-agent infrastructure（`_multi_agent.py` + `_phase6_sp.py` template），改成 batter 專屬 prompt。

### 4.1 流程概觀

**Anchor 線**：

```
Step 1: 3 agent 平行 rank top 3 (most-drop-worthy first)
   ↓
Step 2: Master 整合 (純整合，不跑自己 ranking)
   ├─ P1 共識 (3-0 / 2-1) → 推 P1（master 仍可看 reasoning 提反向）
   ├─ P1 全分歧 (1-1-1) → step 2.5 re-review
   ↓
Step 2.5: re-review (僅 1-1-1 觸發)
   ├─ NEW 3 agent，同 prompt，pool 縮為「3 個 P1 候選」
   ├─ 仍 1-1-1 → master 看完所有 reasoning 自行排序 + ⚠️ flag
```

**FA 線**（**Option B 設計：rank 階段也用 3 agent，跟 anchor 端對稱**）：

```
Step 3: 3 agent 平行 classify 每個 FA
   ├─ 對每個 FA 給 verdict: worth / borderline / not_worth
   ├─ 比較對象 = anchor master 推的候選
   ↓
Step 3.5: 機械整理 survivors
   ├─ Majority verdict per FA（aggregate 3 agent 投票）
   ├─ Survivors = worth + borderline 的 FA
   ├─ 1-1-1 (worth/borderline/not_worth 各 1) 預設 borderline 進 pool
   ↓
Step 4: 3 agent 平行 rank top 3 from survivors
   ├─ 同 anchor step 1 設計，從 survivors 內部排 top 3
   ├─ Pool 1-3 人 → 排所有
   ↓
Step 5: Master 整合 FA rank (含 2-1 dissent)
   ├─ Top 1 共識 (3-0 / 2-1) → 推 top 1（master 可推 minority）
   ├─ Top 1 全分歧 (1-1-1) → step 5.5 re-review
   ↓
Step 5.5: FA re-review (僅 1-1-1 觸發)
   ├─ NEW 3 agent，同 prompt，pool 縮為「3 個 top 1 候選」
   ├─ 仍 1-1-1 → master 自判 + ⚠️ flag
```

**Final decision 線**：

```
Step 6: Master final decision
   ├─ 輸入: anchor master 結果（可能 2 候選 / 3 候選 if dissent / 1-1-1）
   ├─       FA master 結果（同上）
   ├─       FAAB 餘額 / 本週 transaction 額度等 context
   ├─ 輸出 action: drop_X_add_Y / watch / pass
   ├─ 雙候選都 surface 在最終報告（給用戶判斷空間）
```

### 4.2 Step 1 prompt 哲學

**不給判斷框架**。不寫「整季強+14d 強 → hold」這類 2×2 矩陣指引。

prompt 給：
- League rules（H2H 一週 / 計分類別）
  - **不**強調「BB 結構性偏低」這類策略偏好（規則本來就含 BB/OPS 計分）
- Pool 完整 raw + percentile + 14d trad + prior 2025 raw + percentile
- Hard constraints（cant_cut / BBE<40 / Sum ≥25 已 exclude，不需重判）
- 任務：「排出**最該 drop 三人**，最該 drop 排第一，附 reasoning」
  - Pool 1-3 人時 → 排所有
- 要求 reasoning（每位排名附 1-2 句理由）

**讓 3 個 agent 從同一資料各自發散**：
- Agent A 可能重視 long-term skill → P1 = season metric 最差
- Agent B 可能重視短期 H2H → P1 = 14d 最爛
- Agent C 可能權衡兩者 → P1 = 雙重低

### 4.3 Step 2 master 整合

Master **純整合，不跑自己的 ranking**。任務：

1. 統計 P1 distribution（如 `{"Player A": 2, "Player B": 1}`）
2. 看完 3 個 agent reasoning（**重要：即使 majority 共識也要看**）
3. 決定 master_recommendation：
   - **3-0 共識** → master 跟 majority 一致，附 1 句 rationale
   - **2-1 majority** → 預設跟 majority，但**若 master 認為 minority reasoning 更有說服力 → 推 minority**。**兩個候選都列出**並各附 reasoning summary
   - **1-1-1 全分歧** → 觸發 step 2.5 re-review

**Master 2-1 dissent 輸出範例**：

```json
{
  "p1_distribution": {"Player A": 2, "Player B": 1},
  "master_recommendation": "Player B",
  "majority_reasoning_summary": "2 agent 支持 A 因為...",
  "minority_reasoning_summary": "1 agent 支持 B 因為...",
  "master_rationale": "我建議 B，因為 minority 看到 A 是 14d 火燙賣高訊號，drop 會吃虧",
  "candidates_in_report": ["Player A", "Player B"]
}
```

對應到 final report，呈現：
> **隊上最該 drop**：3 agent 投票 2:1（A 2 票 / B 1 票）
> **Master 建議**：drop B（理由：minority 看到 A 是 14d 火燙賣高訊號）
> **A 也值得考慮**：majority 認為 A 結構性弱應結案
> ⚠️ 給用戶判斷空間

### 4.4 Step 2.5 re-review（僅 1-1-1 觸發）

| 設計 | 細節 |
|---|---|
| **Trigger** | Step 1 P1 全分歧（每個 agent 各投不同人） |
| **Agent** | NEW 3 agent（claude -p 每次 fresh subprocess，本來就是新 agent）|
| **Prompt** | 同 Step 1 prompt |
| **Pool** | 縮為「第一輪 3 個 P1 候選」（共 3 人）|
| **Task** | 同 Step 1 — 排 top 3（即排所有 3 人）|

**第二輪結果處理**：
- **3-0 / 2-1** → 同 Step 2 master 整合邏輯（master 純整合，2-1 可 dissent）
- **仍 1-1-1** → master 看完**第一輪 + 第二輪共 6 個 reasoning** 自行排序 + 標 ⚠️ flag「P1 分歧未收斂」

**第二輪仍分歧的 master 輸出範例**：

```json
{
  "first_round": "1-1-1 (A/B/C)",
  "second_round": "1-1-1 (A/B/C, different agents)",
  "master_recommendation": "Player A",
  "master_rationale": "看完 6 個 reasoning，A 在 14d / season / prior 三線都有最弱證據累積",
  "convergence_flag": "⚠️ P1 分歧未收斂（2 輪共 6 agent vote 1:1:1）",
  "candidates_in_report": ["Player A", "Player B", "Player C"]
}
```

**為什麼 master 仍出 ranking 不卡死**：fa_scan 不能因分歧停擺；給用戶看「分歧 + master 自判」比沒有結論好，⚠️ flag 明確告知信心低。

### 4.5 為什麼「2-1 master 可 dissent」很關鍵

H2H one-week 賽制下，「賣高 vs 結構性弱」這類判斷常 borderline。Majority vote 會有 false confidence — 比如：
- Albies case: 2 agent 看「Sum 8 雙年弱」推 P1，1 agent 看「14d OPS .947 不該 drop」反對
- Majority 推 P1 = Albies，但 minority 的 reasoning 可能對

**Master 加層**：master 看 reasoning quality，不只看票數。讓「少數派但 reasoning 強」有機會推翻 majority。
**雙候選列出**：用戶看到完整論述空間，不是單一 push。

### 4.6 Step 3 — FA classify prompt 哲學

3 agent 平行收到：
- **Anchor 候選清單**（從 anchor master 出來的，可能 1 / 2 / 3 人 視 dissent 而定）
- **FA pool 完整 raw + percentile + 14d trad + %owned**
- League rules（H2H 一週）
- 任務：「對每個 FA 標 verdict — 跟 anchor 比是否值得 swap」

**Verdict 三分類**：
- `worth` — 明顯比 anchor 強，且無重大警訊（14d 沒崩 / 樣本夠 / %owned 不在 free fall）
- `borderline` — 某些 metric 強但有警訊（如 14d 死亡組 / 賣高運氣 / %owned 急降）
- `not_worth` — 不顯著勝 anchor / 警訊太多

每個 agent 對每個 FA 給 1 個 verdict + 1-2 句 reasoning。

### 4.7 Step 3.5 — 機械整理 survivors

對每個 FA 彙整 3 個 verdict：

```python
def aggregate_fa_verdicts(classify_results) -> dict:
    """For each FA, take majority of 3 agent verdicts.

    Outcomes:
        - 3 same verdict → that verdict
        - 2-1 → majority verdict
        - 1-1-1 (worth/borderline/not_worth各1) → 預設 borderline (進 pool 觀察)

    Returns: {fa_name: aggregated_verdict}
    """

# Survivors = aggregated verdict ∈ {worth, borderline}
# not_worth majority → 不進 step 4 rank
```

### 4.8 Step 4 — 3 agent rank top 3 from survivors

跟 anchor step 1 對稱設計。3 agent 平行收到：
- Survivors pool（4-8 人 typical）
- 各 FA 的 classify reasoning summary（avg of 3 agent reasonings per FA）
- League rules / anchor identity（要排序的對象）
- 任務：「排出 top 3 — 最該 add 排第一」
  - Pool 1-3 人 → 排所有

讓 3 agent 自由 reasoning，不給 ranking 框架。

**為什麼 classify 已經 3 agent 了還要 rank 3 agent？**

| 階段 | 任務 | 比較對象 |
|---|---|---|
| Classify | 「這個 FA 比 anchor 值得 swap 嗎？」 | FA vs anchor（每個 FA 跟 anchor 比，獨立）|
| Rank | 「survivors 中誰 top 1 / 2 / 3？」 | FA vs FA（survivors 內部比較）|

不同視角。Classify 共識 ≠ Rank 共識（如：Ramos 跟 Cortes 都 worth，但誰 top 1 是另一個判斷）。

### 4.9 Step 5 — Master 整合 FA rank（含 2-1 dissent）

跟 anchor step 2 同邏輯：

- 3-0 共識 → master 跟 majority 一致
- 2-1 majority → 預設跟 majority，但 master 可推 minority（看 reasoning quality）
- 1-1-1 → step 5.5 re-review

**Master 2-1 dissent 範例**（FA top 1）：

```json
{
  "top1_distribution": {"Carlos Cortes": 2, "Heliot Ramos": 1},
  "master_recommendation": "Heliot Ramos",
  "majority_reasoning_summary": "2 agent 推 Cortes 因為 14d OPS 1.165 + %owned 1→14 explosive",
  "minority_reasoning_summary": "1 agent 推 Ramos 因為 47% owned 已驗證 + 2025 prior 紮實",
  "master_rationale": "我建議 Ramos — Cortes 雖 14d 火燙但 PA 偏低 + 2025 BB% breakdown 待驗，accept 不確定性風險高",
  "candidates_in_report": ["Carlos Cortes", "Heliot Ramos"]
}
```

**呈現給用戶**：
> **最強 FA 候選**：3 agent 投票 2:1（Cortes 2 票 / Ramos 1 票）
> **Master 建議**：add Ramos（理由：...）
> **Cortes 也值得考慮**：majority 認為 14d 火燙 + 窗口收窄
> ⚠️ 給用戶判斷空間

### 4.10 Step 5.5 — FA re-review（僅 1-1-1 觸發）

跟 anchor step 2.5 對稱：

| 設計 | 細節 |
|---|---|
| Trigger | Step 4 top 1 全分歧（每個 agent 各推不同 FA 為 top 1）|
| Agent | NEW 3 agent（fresh subprocess）|
| Prompt | 同 step 4 prompt |
| Pool | 縮為「第一輪 3 個 top 1 候選」 |
| 仍 1-1-1 | master 看完 6 個 reasoning 自判 + ⚠️ flag「FA top 排序未收斂」|

### 4.11 Step 6 — Master final decision

最後 master 整合 anchor + FA 決定 action。

**輸入**：
- Anchor 端 master 結果（含 candidates_in_report，可能 1/2/3 人）
- FA 端 master 結果（含 candidates_in_report，可能 1/2/3 人）
- League context（FAAB 餘額 / 本週 transaction 已用次數 / cant_cut 名單）
- ⚠️ flags from anchor / FA convergence 失敗

**輸出 action**：
- `drop_X_add_Y` — 明確 swap，X 從 anchor 候選挑、Y 從 FA 候選挑
- `watch` — FA 接近但不夠強 / anchor 火燙不該動 → 列 watch_triggers
- `pass` — 全 FA 都不值得 / anchor 沒可動的 → 不動

**處理雙候選 / 多候選 case**：

如果 anchor 端 master 推 2 人（dissent case）+ FA 端 master 推 2 人：
- 4 種 swap 組合（A→X / A→Y / B→X / B→Y）
- Master final 選最有邏輯的組合，附 rationale
- 其他組合在 report 列出讓用戶看

**範例輸出**：

```json
{
  "action": "drop_X_add_Y",
  "drop": "Albies",
  "add": "Heliot Ramos",
  "alternative_combos": [
    {"drop": "Altuve", "add": "Heliot Ramos", "rationale": "2-1 anchor minority 推 Altuve"},
    {"drop": "Albies", "add": "Carlos Cortes", "rationale": "2-1 FA majority 推 Cortes"}
  ],
  "telegram_summary": "[Phase 6] drop Albies add Ramos — Sum +12 + 14d 雙穩 + 47% owned 驗證",
  "convergence_flags": ["⚠️ anchor 2-1 dissent: Albies vs Altuve"]
}
```

---

## 5. 不做的事（明確排除）

| 不做 | 理由 |
|---|---|
| 重設 5-slot Sum | 已實證 batter 找不到 5 個獨立軸（feasibility doc）|
| 加 ✅/⚠️ tag 層 | binary summary 丟訊息，raw 給 agent 自判 |
| 加 2×2 矩陣強制框架 | 強加邏輯限制 agent 思維 |
| 加 SB-related 指標進 Sum | 違背軟 punt SB 策略 |
| PA/TG 進 urgency 計分 | 隊上同質性高無區分能力 |
| 機械算 14d Δ 分數 / K% spike 分數 | 門檻未實證，false precision；raw 給 agent |
| 14d 重新校準百分位 | 沿用季線百分位，agent 看 raw + 跟季線比即可 |
| 改 pick_weakest 機械層引入 14d | 14d 訊號交 agent 處理（盲點 4 由 multi-agent step 1 解）|
| Park factor 調整 | xwOBA 已 ~90% park-neutral，殘餘偏差 fantasy 不修 |
| 重做百分位表 | 沿用現有 2025 表，2026 mid-season 更新已是 CLAUDE.md TODO |
| **暴露 Sum / score 給 agent** | Sum 是 aggregate proxy，會 anchor 思維；強迫 raw + percentile reasoning |
| **守位 / selected_pos / status 進評估** | 評價只看打擊數據；出場狀態跟當天比賽有關，不是品質訊號 |
| **Slump hold 自動偵測**（2025 Sum ≥24）| 統一改用 `cant_cut` 名單，不分 skill/slump 兩類 |
| **Strategy context 進 step 1 prompt**（如「BB 結構性偏低」）| H2H 規則本來就含 BB 計分，不需引導 agent |

---

## 6. 完整流程

```
fa_scan.py daily run (batter path)
  Layer 1-3: Yahoo FA + Savant filter + enrich (不變)

  Layer 3.5 [新增]: enrich_14d_trad
    對 my-team batter + FA candidate 撈 MLB Stats API gameLog
    last 14 games trad（OPS / AVG / HR / RBI / R / SB / BB / K）
    + season K% baseline + 14d K% spike
    + 14d BBE 估算
    + 14d Δ xwOBA raw 數值

  Layer 3.6 [新增]: enrich_owned_trend (FA only)
    從 fa_history.json 撈 last 7-day %owned series
    計算 delta_3d / delta_7d / shape

  Layer 4 [簡化]: 機械 pre-filter
    pick_weakest_v4_batter (anchor):
      cant_cut（Jazz + Machado）+ BBE <40 + 2026 Sum ≥25
      輸出 weakest_pool（不限人數，全部 Sum <25）
      特殊：pool 0 → 跳過 batter scan / pool 1-3 → step 1 排所有

    filter_fa_pool_v4_batter (FA):
      BBE <40 + 2026 Sum <21
      不依守位 / status filter
      輸出 fa_pool（typical 8-15 人）

    Sum 內部計算後丟掉，不出現在 output

  Layer 4.5 [新增]: enrich_for_multi_agent
    對 weakest_pool + fa_pool 組裝 raw + percentile 結構
    Anchor schema（§3.2）+ FA schema（§3.4，加 owned block，無 positions）

  Layer 5 [改]: phase6 batter multi-agent
    [Anchor 線]
      step 1: 3 agent 平行 rank top 3 anchor
      step 2: master 整合（含 2-1 dissent）
      step 2.5: re-review（僅 1-1-1 觸發，NEW 3 agent，pool 縮為 3 P1 候選）

    [FA 線] — Option B 對稱設計
      step 3: 3 agent 平行 classify 每個 FA (worth/borderline/not_worth)
      step 3.5: 機械整理 survivors（majority verdict per FA）
      step 4: 3 agent 平行 rank top 3 from survivors
      step 5: master 整合 FA rank（含 2-1 dissent）
      step 5.5: re-review（僅 1-1-1 觸發，NEW 3 agent，pool 縮為 3 top1 候選）

    [Final]
      step 6: master final decision (action + 雙候選 surface)
      輸出 action（drop_X_add_Y / watch / pass）+ alternative_combos + reasoning

  Layer 6: 推送 + waiver-log 更新（不變）
```

---

## 7. 實作骨架

### 7.1 機械層精簡（可立即動工）

**改動檔案**：

| 檔案 | 改動 |
|---|---|
| `daily-advisor/roster_config.json` league.cant_cut | 加 Manny Machado（目前已有 Jazz Chisholm + Skubal-SP）|
| `daily-advisor/fa_compute.py` | `compute_urgency` batter 分支：移除 `_factor_rolling`、`_factor_batter_pa_per_tg`、`_factor_2026_sum`、`_factor_2025_sum`（batter 用法）— batter 改為**只回傳 enriched entries**（無 ranking、無 urgency 數字）|
| `daily-advisor/fa_compute.py` | `pick_weakest` batter 分支：加 `_batter_bbe_excluded(bbe < 40)` filter；加 2026 Sum ≥25 排除；移除 `n=4` cap，改回傳全部 Sum <25 |
| `daily-advisor/fa_compute.py` | 移除 batter slump hold 自動偵測（2025 Sum ≥24）— 改靠 cant_cut 名單 |
| `daily-advisor/fa_compute.py` | `compute_fa_tags` batter 分支：保留 `✅ 球隊主力 / ⚠️ 上場有限`（PA-based gate）但**移除其他 14d / xwOBA / luck 相關 tag**（這些交 agent）|
| `daily-advisor/fa_scan.py` | 加 `enrich_14d_trad(player, season=2026)` 函式 |
| `daily-advisor/fa_scan.py` | 加 `enrich_owned_trend(player_name, fa_history_data)` 函式（FA only）|
| `daily-advisor/fa_scan.py` | 加 `enrich_for_multi_agent(weakest, fa_pool, ...)` 函式 — 組裝 §3.2 schema（無 sum/score）|
| `daily-advisor/tests/test_fa_compute.py` | 改 batter pick_weakest expectations（無 score / 無 urgency / 含 Sum<25 filter / 無 4-人 cap）|
| CLAUDE.md「打者評估」§Step 2 | 改寫 — 機械層不再算 urgency，交 multi-agent；移除 slump hold 機制描述，改提 cant_cut |

### 7.2 Multi-Agent 層

**新增檔案**：
- `daily-advisor/_phase6_batter.py` — orchestrator（複製 `_phase6_sp.py` template，改 batter 專屬 helper）

Anchor 線 prompt:
- `daily-advisor/prompt_phase6_batter_anchor_step1_rank.txt` — 3 agent rank top 3 anchor
- `daily-advisor/prompt_phase6_batter_anchor_step2_master.txt` — master integrate（含 2-1 dissent 規則）
- `daily-advisor/prompt_phase6_batter_anchor_step2_5_rereview.txt` — anchor re-review

FA 線 prompt（Option B：classify + rank 各 3 agent）:
- `daily-advisor/prompt_phase6_batter_fa_step3_classify.txt` — 3 agent 標 worth/borderline/not_worth
- `daily-advisor/prompt_phase6_batter_fa_step4_rank.txt` — 3 agent rank top 3 from survivors
- `daily-advisor/prompt_phase6_batter_fa_step5_master.txt` — master integrate FA rank（含 2-1 dissent）
- `daily-advisor/prompt_phase6_batter_fa_step5_5_rereview.txt` — FA re-review

Final:
- `daily-advisor/prompt_phase6_batter_final_decision.txt` — step 6 action（含雙候選 surface 規則）

**改動**：
- `daily-advisor/fa_scan.py` — 加 `BATTER_FRAMEWORK_VERSION` env var dispatch（同 SP_FRAMEWORK_VERSION 模式）

### 7.3 複用度

| 元件 | 來源 | 複用方式 |
|---|---|---|
| `_multi_agent.py` | SP v4 已有 | 直接 import（generic helper）|
| `_phase6_sp.py` 8-step pattern | SP v4 已有 | 複製 + 改 batter 專屬 helper |
| `consensus_check_key` / `count_dissent` | `_multi_agent.py` | 直接複用 |
| Step 2.5 re-review 機制 | **新設計**（SP 是「同 agent re-eval with feedback」）| Batter 改為「NEW 3 agent + 縮 pool」 |

---

## 8. 尚待決定（open questions）

| 問題 | 預設值 / 處理 |
|---|---|
| `cant_cut` 是否區分 SP/batter？ | 目前共用一個 list — Skubal 對 batter scan 自然不 match（他是 SP）。簡單夠用 |
| 14d 滾動範圍是否該調整？（vs 7d / 21d / 多窗口）| 預設 14d 一個窗口；觀察期決定是否加 7d / 21d |
| %owned shape heuristic 門檻 | 預設：explosive ≥+10pp 3d / dropping ≤-3pp 3d / rising +3-10pp 3d / plateau 其他 |
| Multi-agent 月成本 cap | 訂閱涵蓋（同 SP），無 cap，超 $50 觀察期重評 |
| Step 2.5 re-review 跑 1 輪上限 | 沿用 SP phase6 設計（最多 1 輪 re-review，仍分歧 → master 自判 + flag）|
| Master 2-1 dissent 頻率 | 預設無上限 — agent reasoning 質量決定。觀察期統計 dissent 比率，過高 → 重審 prompt 質量 |

---

## 9. 風險 / 緩衝

| 風險 | 緩衝 |
|---|---|
| 14d sample noise（小樣本誤判）| 14d BBE 進 agent context，prompt 提示「BBE <25 弱化 14d 訊號」|
| %owned trend 反向訊號（聯盟錯）| 不直接驅動 add，僅當 LLM context |
| 3 agent 全分歧（1-1-1）| step 2.5 re-review 觸發；仍分歧 → master 自判 + ⚠️ flag |
| Master dissent 過度 | 統計 master vs majority 不一致比率；若 >30% → 檢查 prompt 是否誤導 master |
| 失去 urgency 數字可解釋性 | Multi-agent 各自 reasoning + master rationale 取代 urgency 數字 |
| Multi-agent prompt 質量影響判斷 | 上線前用今天兩輪實驗的 case（Albies / Cam Smith / Cortes / Altuve）做 fixture 測試 |
| 機械防線繞過（agent 推 cant_cut）| 機械層 hard rule 在 enrich 前就排除，agent 看不到這些人 |
| Pool 過小（0 人）造成 cron 跳過 batter scan | 預期行為 — 隊強當下不需 drop |

---

## 10. 成功指標

| 指標 | 目標 | 衡量方式 |
|---|---|---|
| 接刀防護率 | 上線後零接刀（add 後 7 天 OPS <.500）| 月度人工檢核 fa_scan 推薦 vs 後續 14d 結果 |
| 真實 anchor 識別 | 不 drop 14d 火燙球員 | 統計 14d OPS ≥.850 的 P1 推薦次數 |
| 共識率 | ≥ 70%（3 agent 至少 2 同意 P1）| step 1 P1 distribution log |
| Re-review 觸發率 | <30%（1-1-1 不該頻繁）| step 2.5 觸發 log |
| Master dissent 率 | <30%（不該過度反 majority）| step 2 master 輸出 log |
| 月成本 | ≤ $50（SP 約 1.5×）| 上線後實測 |

---

## 11. 相關文件

| 文件 | 關聯 |
|---|---|
| `docs/batter-framework-v4-feasibility.md` | 04-25 寫的 batter 5-slot 不可行性研究 — 本 doc 接續結論「不重設 Sum」|
| `docs/sp-framework-v4-balanced.md` | SP v4 設計稿 — 本 doc 借用「raw + 不打分 + agent 判斷」哲學 |
| `docs/v4-cutover-plan.md` | SP v4 cutover 計畫 — 本 doc 多 agent 層複用其完成的 multi-agent infrastructure |
| `docs/phase6-multi-agent-spike.md` | SP multi-agent 設計稿 — 本 doc 8-step orchestrator 直接複用 |
| `daily-advisor/_phase6_sp.py` | SP multi-agent 實作 — 本 doc `_phase6_batter.py` 仿造 |
| `daily-advisor/_multi_agent.py` | multi-agent helper — 本 doc 直接 import 複用 |
| `CLAUDE.md` 「打者評估」章節 | 現役 batter 框架 — 本 doc 機械層精簡會 update 此章節（urgency 公式拿掉 + slump hold 機制改 cant_cut）|

---

## 12. 跟 SP v4 的設計哲學對應 + 差異

| 哲學 | SP v4 應用 | Batter 升級應用 |
|---|---|---|
| **減少 false precision** | 21d Δ xwOBACON 不打分（raw 給 Claude）| **更徹底**：urgency 全部 factor 不打分；Sum 也不暴露給 agent |
| **層級分工：Python 給材料、Claude 給決策** | 部分 — Sum 仍機械算且暴露 | **更純**：Sum 機械算（內部 filter）後丟掉；output 純 raw + percentile |
| **Hard rule vs soft judgment 分離** | cant_cut + slump hold 機械擋；rank/decision 走 agent | **同邏輯延伸**：cant_cut 統一管理、再加 BBE <40 + Sum ≥25 機械擋 |
| **Multi-agent 共識 + dissent** | step 3 reviewer + 1 round re-eval | **Master 2-1 dissent 機制 + step 2.5 NEW 3 agent re-review**（更靈活）|

Batter 升級在「raw + agent 自由 reasoning」這個 axis 上**比 SP v4 更徹底** — SP 還暴露 Sum + 4-factor urgency，batter 連這層都拿掉。

合理性：batter 比 SP 少結構性問題（feasibility doc 已實證），所以可以更激進地把判斷推給 agent；同時 master dissent 機制給用戶更多參考訊號（不是單一 push）。
