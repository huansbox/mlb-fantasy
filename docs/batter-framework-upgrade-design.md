# Batter Framework 升級 Design — Raw Data + Multi-Agent 自由 Reasoning

> **Status**: 設計定稿（2026-04-28）。本文對齊不寫 code — 機械層精簡可立即動工，多 agent 層待 SP v4 multi-agent infrastructure 證明穩定後接續。
>
> **Background**: 2026-04-28 session 中兩輪 ad-hoc 3 agent 投票實驗暴露 fa_scan 季 Sum 對 H2H 一週決策的盲點。FA 端（Cam Smith 季 Sum 28 但 14d OPS .340）與 Anchor 端（Albies 季 Sum 8 但 14d OPS .947）兩個 case 同時印證問題。

---

## 1. 結論 / 設計核心

本升級的核心是把**機械評分壓到最少 — 只剩 Sum + 必要的 hard rule**，把所有「權衡判斷」全交給 **multi-agent 自由 reasoning**。

### 1.1 機械層 vs Agent 層分工

| 層 | 職責 | 輸出 |
|---|---|---|
| **機械層**（Python）| 縮小 anchor pool / hard rule 排除 / 補充 raw 數據結構 | 6 候選 + 完整 raw + percentile / FA pool + 同樣 enrich |
| **Multi-Agent 層** | 排序 / 權衡 / 決策（drop / add / watch） | 共識 + dissent flag + 動作建議 |

### 1.2 拋棄的設計

| 拋棄 | 為什麼 |
|---|---|
| **urgency 4-factor 計分** | 三個 factor 的門檻都是經驗值（14d Δ ±0.035/0.050 / PA-TG ≥3.5 / 2025 Sum ≥24）— 沒實證 calibration，false precision |
| **2×2 矩陣強制框架** | 強加單一判斷邏輯反而限制 agent 思維；let agents 從 raw 看資料各自 reasoning |
| **✅/⚠️ tag 層** | binary summary 損失訊息（P75 跟 P95 都是 ✅）；raw + percentile 給 agent 反而更精準 |
| **PA/TG 進 urgency** | 隊上 active batter 同質性高（PA/TG 都在 3.5-4.5）→ 此 factor 對所有人 +2 = 沒區分能力。FA 端 add 邏輯仍保留作 context |

### 1.3 保留的機械層

| 保留 | 為什麼 |
|---|---|
| **Sum**（3 metric × 0-10）| 用作 pick_weakest 的粗排序錨點，不是最終決策 |
| **pick_weakest 排序** | 必須機械方式縮 pool（不可能讓 agent 看 11 個 batter）|
| **Slump hold 檢核**（2025 Sum ≥24 exclude）| Hard rule — 「不要 cut 去年菁英」是 floor protection，不交 agent |
| **BBE 小樣本排除**（batter <40，新加，跟 SP <30 對齊）| Hard rule — 剛 call up / 受傷 1 週球員不該作 anchor |
| **cant_cut 排除** | Hard rule — 從 league config |

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

### 2.3 為什麼 raw + percentile + 自由 reasoning

| 設計選擇 | 理由 |
|---|---|
| **raw 數值不計分** | 計分桶（如 1/3/5/6/7/8/9/10）有資訊損失 + 邊界球員兩側 1 桶差被放大 / 縮小不對稱 |
| **百分位 rank 給** | 提供「跟全聯盟比站哪」的 anchor，agent 不需自己 calibrate 量級 |
| **不強制 2×2 矩陣** | 強加判斷框架反而限制 agent 思維；發散後共識 = 高信心，分歧 = 該 case 真的模糊 |
| **不加 tag** | binary summary 損失訊息；raw + percentile + season + 14d 完整脈絡讓 agent reason |
| **不機械算 urgency** | 4-factor 公式三個門檻都未實證 calibration，false precision；agent 有 raw + percentile 可自行權衡 |

---

## 3. 機械層職責（精簡後）

### 3.1 pick_weakest_v4_batter

```python
def pick_weakest_v4_batter(players, n=6, cant_cut=None):
    """Mechanical pre-filter only.

    Filters (in order):
        1. Exclude cant_cut by name
        2. Exclude IL/NA by selected_pos (already done upstream)
        3. Exclude BBE <40 → low_confidence_excluded (沿用 SP <30 原則調為 batter <40)
        4. Exclude 2025 Sum ≥24 → slump_hold (excluded from rank, not P1-P4 anchor)
        5. Sort by 2026 Sum asc, take first n (default 6)

    Returns:
        (weakest, low_confidence_excluded, slump_hold)
    """
```

`n=6` 比現役 4 多 — 給 multi-agent 較多選擇空間，避免 mechanical filter 把真正最弱漏掉（盲點 4）。

### 3.2 enrich_for_multi_agent

把每個候選 attach 完整 raw + percentile 結構：

```json
{
  "name": "Albies",
  "mlb_id": 645277,
  "team": "ATL",
  "positions": ["2B"],
  "selected_pos": "2B",

  "season_2026": {
    "xwoba":     {"value": 0.290, "pctile": 35},
    "bb_pct":    {"value": 5.6,   "pctile": 22},
    "barrel_pct":{"value": 3.1,   "pctile": 18},
    "hh_pct":    {"value": 38.0,  "pctile": 40},
    "k_pct":     {"value": 12.1,  "pctile": 70},
    "ops":       {"value": 0.799, "pctile": 60},
    "pa":        320,
    "bbe":       92,
    "pa_per_tg": 4.28,
    "sum":       8
  },

  "rolling_14d": {
    "ops":          {"value": 0.947, "pctile_vs_season": 88},
    "avg":          {"value": 0.363, "pctile_vs_season": 92},
    "obp":          0.383,
    "slg":          0.563,
    "hr":           2,
    "rbi":          10,
    "r":            11,
    "bb_pct":       {"value": 5.0, "pctile_vs_season": 18},
    "k_pct":        {"value": 5.0, "pctile_vs_season": 95},
    "k_spike_pp":   -7.1,
    "delta_xwoba":  -0.012,
    "pa":           60,
    "bbe":          30
  },

  "prior_2025": {
    "sum":         15,
    "pa":          600,
    "ops":         0.752,
    "xwoba":       0.310,
    "bb_pct":      6.2,
    "barrel_pct":  6.5,
    "hh_pct":      40.5
  }
}
```

對 FA candidate 額外 attach：

```json
{
  "owned": {
    "current_pct": 41,
    "delta_3d":    -4,
    "delta_7d":    -8,
    "shape":       "dropping"
  }
}
```

`shape` ∈ {"plateau", "rising", "explosive", "dropping"} — heuristic 分類但純資訊用，agent 自行判斷重要性。

### 3.3 不做的事（機械層）

- ❌ 不算 urgency（無 4-factor sum）
- ❌ 不打 ✅/⚠️ tag
- ❌ 不應用 2×2 矩陣分類
- ❌ 不算「Sum 差 vs anchor」（讓 agent 自己看 raw 比）
- ❌ 不寫 14d Δ / K% spike / %owned 門檻判斷

機械層**只負責資料整理**，不做評估。

---

## 4. 多 Agent 層職責

複用 SP v4 multi-agent infrastructure（`_multi_agent.py` + `_phase6_sp.py` template），改成 batter 專屬 prompt。

### 4.1 8-step orchestrator

| Step | 角色 | 輸入 | 輸出 |
|---|---|---|---|
| 1 | 3 agent 平行 rank P1-P6 | 6 候選完整 raw + percentile | 各自 ranking + reasoning |
| 2 | Master integrate | 3 個 ranking + 各自 reasoning | final_ranking + borderline_pairs |
| 3 | 3 reviewer（borderline gate）| Master 決定 + 自己 step 1 意見 | agree_on_p1 + 反駁論述 |
| 4 | 3 agent 平行 classify FA | FA pool 完整 raw | 各 FA 標 worth / borderline / not_worth |
| 5 | Master rank FA survivors | 通過 classify 的 FA | ranked_top + borderline_pairs |
| 6 | 3 reviewer FA（borderline gate）| Master FA rank + 各自 classify | agree_on_top1 |
| 7 | Re-eval（dissent ≥2 才跑）| review feedback | revised ranking |
| 8 | Final decision | anchor + fa_top + non_data context | action: drop_X_add_Y / watch / pass |

### 4.2 Step 1 prompt 哲學

**不給判斷框架**。不寫「整季強+14d 強 → hold」這類 2×2 矩陣指引。

prompt 給：
- League rules（H2H 一週 / 計分類別 / BB 結構性偏低 等策略 context）
- 6 候選的完整 raw + percentile + 14d trad + %owned
- Hard constraints（cant_cut / slump hold 已 exclude，不需重判）
- 任務：「請按你的判斷排 P1-P6 — 最該 drop 排第一，最不該 drop 排第六」
- 要求 reasoning（每位排名附 1-2 句理由）

**讓 3 個 agent 從同一資料各自發散**：
- Agent A 可能重視 long-term skill → P1 = season Sum 最低
- Agent B 可能重視短期 H2H → P1 = 14d 最爛
- Agent C 可能權衡兩者 → P1 = 雙重低

**Dissent 是訊號**：
- 3-0 共識 → 高信心 P1
- 1-1-1 全分歧 → 該 case 真模糊（dissent gate 觸發 review）
- 2-1 → borderline_pair，看 reasoning 釐清

### 4.3 Step 8 final decision 行動類別

跟 SP phase6 一致：
- `drop_X_add_Y` — anchor X drop + FA Y add
- `watch` — FA 接近但不夠 / 給 watch_triggers
- `pass` — 全部 FA 都不值得，hold anchor

---

## 5. 不做的事（明確排除）

| 不做 | 理由 |
|---|---|
| 重設 5-slot Sum | 已實證 batter 找不到 5 個獨立軸（feasibility doc）|
| 加 ✅/⚠️ tag 層 | binary summary 丟訊息，raw 給 agent 自判 |
| 加 2×2 矩陣強制框架 | 強加邏輯限制 agent 思維 |
| 加 SB-related 指標進 Sum | 違背軟 punt SB 策略 |
| PA/TG 進 urgency 計分 | 隊上同質性高無區分能力（FA add 端 PA/TG 仍作 context）|
| 機械算 14d Δ 分數 / K% spike 分數 | 門檻未實證，false precision；raw 給 agent |
| 14d 重新校準百分位 | 沿用季線百分位，agent 看 raw + 跟季線比即可 |
| 改 pick_weakest 機械層引入 14d | 14d 訊號交 agent 處理（盲點 4 由 multi-agent step 1 解）|
| Park factor 調整 | xwOBA 已 ~90% park-neutral，殘餘偏差 fantasy 不修 |
| 重做百分位表 | 沿用現有 2025 表，2026 mid-season 更新已是 CLAUDE.md TODO |

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

  Layer 3.6 [新增]: enrich_owned_trend
    從 fa_history.json 撈 last 7-day %owned series
    計算 delta_3d / delta_7d / shape

  Layer 4 [簡化]: pick_weakest_v4_batter
    機械 pre-filter only:
      cant_cut + IL/NA + BBE <40 + Slump hold ≥24
    Sort by 2026 Sum asc → 取最弱 6 位
    輸出 weakest_pool（不算 urgency）

  Layer 4.5 [新增]: enrich_for_multi_agent
    對 weakest_pool 6 + FA pool 8-12 attach raw + percentile 結構

  Layer 5 [改]: phase6 batter multi-agent
    8-step orchestrator: anchor rank → master → review → FA classify → FA rank → review → final
    輸出 action（drop_X_add_Y / watch / pass）+ 共識 dissent flag

  Layer 6: 推送 + waiver-log 更新（不變）
```

---

## 7. 實作骨架

### 7.1 機械層精簡（可立即動工）

**改動檔案**：

| 檔案 | 改動 |
|---|---|
| `daily-advisor/fa_compute.py` | `compute_urgency` batter 分支：移除 `_factor_rolling`、移除 `_factor_batter_pa_per_tg`、移除 `_factor_2026_sum`、移除 `_factor_2025_sum` 的 batter 用法 — batter 改為**只回傳 enriched entries**（無 ranking、無 urgency 數字）|
| `daily-advisor/fa_compute.py` | `pick_weakest` batter 分支：加 `_batter_bbe_excluded(bbe < 40)` filter，跟 SP `<30` 對齊 |
| `daily-advisor/fa_compute.py` | `compute_fa_tags` batter 分支：保留 `✅ 球隊主力 / ⚠️ 上場有限`（PA-based gate）但**移除其他 14d / xwOBA / luck 相關 tag**（這些交 agent）|
| `daily-advisor/fa_scan.py` | 加 `enrich_14d_trad(player, season=2026)` 函式 |
| `daily-advisor/fa_scan.py` | 加 `enrich_owned_trend(player_name, fa_history_data)` 函式 |
| `daily-advisor/fa_scan.py` | 加 `enrich_for_multi_agent(weakest, fa_pool, ...)` 函式 — 組裝最終資料結構 |
| `daily-advisor/tests/test_fa_compute.py` | 改 batter urgency expectations（4-factor → 無 urgency）|
| CLAUDE.md「打者評估」§Step 2 | 改寫 — 機械層不再算 urgency，交 multi-agent |

### 7.2 Multi-Agent 層

**新增檔案**：
- `daily-advisor/_phase6_batter.py` — 8-step orchestrator（複製 `_phase6_sp.py` template，改 batter 專屬 helper）
- `daily-advisor/prompt_phase6_batter_step1_rank.txt` — 3 agent rank P1-P6
- `daily-advisor/prompt_phase6_batter_step2_master.txt` — master integrate
- `daily-advisor/prompt_phase6_batter_step3_review.txt` — reviewer (gated)
- `daily-advisor/prompt_phase6_batter_fa_step1_classify.txt` — FA worth/borderline/not_worth
- `daily-advisor/prompt_phase6_batter_fa_step2_rank.txt` — FA master rank
- `daily-advisor/prompt_phase6_batter_fa_step3_review.txt` — FA review (gated)
- `daily-advisor/prompt_phase6_batter_final_decision.txt` — step 8 action

**改動**：
- `daily-advisor/fa_scan.py` — 加 `BATTER_FRAMEWORK_VERSION` env var dispatch（同 SP_FRAMEWORK_VERSION 模式）

### 7.3 複用度

| 元件 | 來源 | 複用方式 |
|---|---|---|
| `_multi_agent.py` | SP v4 已有 | 直接 import（generic helper）|
| `_phase6_sp.py` 8-step pattern | SP v4 已有 | 複製 + 改 batter 專屬 helper（_build_step1_payload 等）|
| `consensus_check_key` / `count_dissent` | `_multi_agent.py` | 直接複用 |
| Borderline gate / re-eval 1-round 上限 | SP phase6 | 同邏輯 |

---

## 8. 尚待決定（open questions）

| 問題 | 預設值 / 處理 |
|---|---|
| pick_weakest 取多少？（4 / 6 / 8）| 預設 6 — 比 SP 的 4 多，給 agent 較多選擇空間 |
| Step 1 prompt 是否完全不給判斷框架？ | 預設不給，僅給 league rules / 策略 context；觀察期看 agent 是否需要更多 anchor |
| 14d 滾動範圍是否該調整？（vs 7d / 21d / 多窗口）| 預設 14d 一個窗口；觀察期決定是否加 7d / 21d |
| %owned shape heuristic 門檻 | 預設：explosive ≥+10pp 3d / dropping ≤-3pp 3d / rising +3-10pp 3d / plateau 其他 |
| Multi-agent 月成本 cap | 訂閱涵蓋（同 SP），無 cap，超 $50 觀察期重評 |
| Step 1 是否要看 Sum 數字（vs 純百分位）？ | 預設給 Sum + 百分位 + 各 metric raw — agent 自選用哪個 |

---

## 9. 風險 / 緩衝

| 風險 | 緩衝 |
|---|---|
| 14d sample noise（小樣本誤判）| 14d BBE 進 agent context，prompt 提示「BBE <25 弱化 14d 訊號」|
| %owned trend 反向訊號（聯盟錯）| 不直接驅動 add，僅當 LLM context |
| 3 agent 全分歧（1-1-1）| dissent gate 觸發 step 3 review；review 仍分歧 → ⚠️ flag 推 watch（同 SP 設計）|
| 失去 urgency 數字可解釋性 | Multi-agent 各自 reasoning 取代 urgency 數字當解釋 — 更具體 |
| Multi-agent prompt 質量影響判斷 | 上線前用今天兩輪實驗的 case（Albies / Cam Smith / Cortes / Altuve）做 fixture 測試 |
| 機械防線繞過（agent 推 cant_cut / slump hold）| 機械層 hard rule 在 enrich 前就排除，agent 看不到這些人 |

---

## 10. 成功指標

| 指標 | 目標 | 衡量方式 |
|---|---|---|
| 接刀防護率 | 上線後零接刀（add 後 7 天 OPS <.500）| 月度人工檢核 fa_scan 推薦 vs 後續 14d 結果 |
| 真實 anchor 識別 | 不 drop 14d 火燙球員 | 統計 14d OPS ≥.850 的 P1 推薦次數 |
| 共識率（multi-agent）| ≥ 70%（3 agent 至少 2 同意 P1）| step 1 P1 distribution log |
| Re-eval 次數 | ≤1 輪 / 天 | step 7 觸發 log |
| 月成本 | ≤ $50（SP 約 1.5×）| 上線後實測 |

---

## 11. 相關文件

| 文件 | 關聯 |
|---|---|
| `docs/batter-framework-v4-feasibility.md` | 04-25 寫的 batter 5-slot 不可行性研究 — 本 doc 接續結論「不重設 Sum」|
| `docs/sp-framework-v4-balanced.md` | SP v4 設計稿 — 本 doc 借用「raw + 不打分 + agent 判斷」哲學（SP 21d Δ xwOBACON 也是這樣）|
| `docs/v4-cutover-plan.md` | SP v4 cutover 計畫 — 本 doc 多 agent 層複用其完成的 multi-agent infrastructure |
| `docs/phase6-multi-agent-spike.md` | SP multi-agent 設計稿 — 本 doc 8-step orchestrator 直接複用 |
| `daily-advisor/_phase6_sp.py` | SP multi-agent 實作 — 本 doc `_phase6_batter.py` 仿造 |
| `daily-advisor/_multi_agent.py` | multi-agent helper — 本 doc 直接 import 複用 |
| `CLAUDE.md` 「打者評估」章節 | 現役 batter 框架 — 本 doc 機械層精簡會 update 此章節（urgency 公式拿掉）|

---

## 12. 跟 SP v4 的設計哲學對應

| 哲學 | SP v4 應用 | Batter 升級應用 |
|---|---|---|
| **減少 false precision** | 21d Δ xwOBACON 不打分（raw 給 Claude）| **更徹底**：urgency 全部 factor 不打分，全 raw 給 agent |
| **層級分工：Python 給材料、Claude 給決策** | 部分 — Sum 仍機械算 | **更純**：Sum 機械算（pick_weakest 用），其他全 agent |
| **Hard rule vs soft judgment 分離** | cant_cut / slump hold 機械擋；rank/decision 走 agent | **同邏輯延伸**：再加 BBE <40 機械擋 |
| **Multi-agent 共識 + dissent** | 8-step orchestrator | **直接複用** |

Batter 升級在「raw + agent 自由 reasoning」這個 axis 上**比 SP v4 更徹底** — SP 還有 4-factor urgency，batter 連這層都拿掉。

合理性：batter 比 SP 少結構性問題（feasibility doc 已實證），所以可以更激進地把判斷推給 agent。
