# SP B1 Cutover Design — Phase 6 對齊 Batter v4 Thin

> **Superseded** by [`docs/sp-b2-cutover-design.md`](sp-b2-cutover-design.md) (B2 thin + multi-agent collapse). Kept for archival reference.

**狀態**：設計定稿（grill-me session 2026-05-06）
**前置依賴**：v4 cutover 已完成（commits 至 `71aa6d9`）；Phase 6 multi-agent SP 已 production
**對應 CLAUDE.md TODO**：
- 「框架對稱性檢視」
- 「SP Phase 6 prompt 拿掉 Sum 暴露對齊 batter v4 thin」

---

## TL;DR

把 SP Phase 6 從「機械層厚（urgency + tags + Sum 暴露 + multi-agent）」收薄成「機械層只做 boolean filter，排序與標籤都交 LLM」，與 batter v4 thin 對稱。保留 multi-agent 但加 dissent 監控門檻；觸發後降回 single LLM call。

---

## 為什麼

**根因**：2026-05-04 觀察 SP Phase 6 三 agent 在 prompt 中 lazy 引用 `sum: 14` / `sum: 19` 數字 — 機械層的 Sum 數字成為 anchor，三 agent 都收斂到同一排序，Phase 6 spike 「P1 共識率 100%」可能是 anchor 鎖共識，不是真共識。

**設計後果**：multi-agent 的 dissent surface 機制空轉。1-10 分桶失真（P89 vs P91 跳 1 分；P79.5 vs P75 同分），加總喪失維度資訊。

**對稱缺口**：batter v4 thin 已把 Sum 內部當 `≥25 filter` 不暴露給 LLM。SP 應對齊。

---

## 設計決策樹（grill-me 對齊結果）

| Q | 決策 | 哲學 |
|---|---|---|
| Q1 | **B**：SP 對齊 Batter v4 thin（薄機械層）| 機械層只做 boolean filter，排序與標籤交 LLM |
| Q2 | **B1**：拿掉 Sum + urgency 排序 + evaluation tags（雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣）；保留 PA-based / 樣本訊號 tags（短局 / 樣本小 / IL 短期 / 上場有限）+ low_confidence | 移除所有「機械層在做 LLM 該做的評估性判斷」 |
| Q3 | **C2**：保留 multi-agent，加 dissent rate 監控 + 撤退門檻 | 一次只動一個變數，multi-agent 命運由 B1 上線實測決定，不一刀殺 |
| Q4 | **D3 + M1 主 / M4 副**：spike fixture 跑 baseline 共識率，依此設門檻；M1 = step1 三 agent P1 match rate；M4 = master borderline trigger rate | 觀察期不靠記性，spike fixture 已存在 cost 低 |
| Q5 | **E1**：5 個 prompt 全改 + SP Sum ≥40 hard 排除（對應 batter Sum≥25 等價 P75+ 全方位）| 對稱原則徹底，不選擇性對齊 |
| Q6 | **F1**：Phase 6 dissent metric 寫進每日 fa-scan GitHub Issue body 結尾 HTML 註解 | reuse 現有 issue 流程，零新 infra |
| Q7 | **G1 + G-pre2**：撤退 fallback = single LLM call（對齊 batter v4 thin）；觸發後再寫 prompt（避免提早寫浪費）| 撤退要可預期收斂，半套 multi-agent 沒意義 |
| Q8 | **H3**：master 從 raw 自判 borderline（非「sum diff <5」這種 mechanical rule） | borderline 判定本質是評估性判斷，該交 LLM |

---

## 核心機制

### 1. 機械層（Python `fa_compute.py` + `_phase6_sp.py`）

**保留**：
- `cant_cut` 排除（從 league config）
- Rotation Gate（GS=0 或 game-log IP/GS<3）
- BBE <30 → `low_confidence_excluded`
- Slump hold（2025 Sum ≥24 且 IP ≥50）
- **新增**：`SP Sum ≥40` hard 排除（對應 batter Sum≥25 等價 P75+ 全方位）

**移除/不暴露給 LLM**：
- urgency 4-factor 排序（仍可內部算作 backup，但 payload 不傳）
- Sum 加總數字（仍可內部算作 ≥40 filter，但 payload 不傳）
- evaluation tags（雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣 / 深投型）

**仍暴露給 LLM**：
- 5-slot 各自 percentile 數值（不是加總）
- 雙年 prior（raw + percentile）
- 21d xwOBACON Δ（rolling）
- 14d trad（如有）
- %owned trend（FA 路徑）
- PA-based / 樣本訊號 tags：✅ 球隊主力 / ⚠️ 上場有限 / ⚠️ 短局 / ⚠️ 樣本小 / ⚠️ IL 短期 / ⚠️ Swingman 角色

### 2. LLM 層（5 個 prompt 全改）

#### 2.1 `prompt_phase6_sp_step1_rank.txt`（必改大）
- **input 改**：`_slim_my_team_entry` payload 拿掉 `score` / `breakdown.sum`（仍傳 5-slot percentile）/ `urgency` / `factors`
- **prompt 改**：
  - 拿掉所有「依 Sum 排序」「依 urgency 提示」字樣
  - 拿掉 evaluation tags 的解釋（雙年菁英定義、GB 重型定義 etc）
  - 強調「從 raw + 5-slot percentile + 雙年 prior + 21d 趨勢自由 reasoning」
  - 保留 PA-based tags 解釋

#### 2.2 `prompt_phase6_sp_step2_master.txt`（必改中）
- **input 改**：`_build_step2_payload` material 拿掉 sum / urgency
- **prompt 改 — H3 borderline 判定**：
  - 移除「sum diff <5 → borderline」rule
  - 新增 LLM 自判：「看完三 agent step1 後，從 raw 訊號矛盾或實質差距小自己判 borderline」
  - 例：「P1 候選 xwOBACON P30 但 IP/GS P85 = 內部訊號矛盾 → borderline」/「P1 vs P2 raw 看起來差距不大 → borderline」

#### 2.3 `prompt_phase6_sp_step3_review.txt`（半改小）
- **input 改**：material 拿掉 sum
- **prompt 改**：清掉 sum 引用文字。review 仍是 sanity check master（master 是 single call 可能 hallucinate）

#### 2.4 `prompt_phase6_fa_step1_classify.txt` / `fa_step2_rank.txt` / `fa_step3_review.txt`（必改中）
- 同 SP 邏輯，FA 路徑也拿掉 sum / urgency 暴露
- **input 改**：`_slim_fa_entry` 拿掉 `score` / `breakdown.sum`；`_build_fa_classify_payload` 移除 `sum_diff` / `breakdown_diff` / `win_gate_passed`（這幾個是 mechanical anchor）；保留 `add_tags` / `warn_tags`（前提是 evaluation tags 已從 fa_compute 拿掉）

#### 2.5 `prompt_phase6_final_decision.txt`（改小）
- **input 改**：`_build_final_payload` ranked_top 拿掉 `sum_diff`
- **prompt 改**：清掉 sum 引用

### 3. 監控（dissent metric）

**寫入位置**：每日 fa-scan GitHub Issue body 結尾加：

```html
<!-- phase6_metrics:
{
  "date": "2026-05-06",
  "sp_p1_match": true,         // M1: 三 agent step1 P1 是否同球員
  "sp_review_triggered": false, // M4: master 是否標 borderline 觸發 step3
  "sp_anchor_name": "Detmers",
  "fa_p1_match": true,
  "fa_review_triggered": false,
  "fa_top_name": "Junk"
}
-->
```

**寫入點**：`_phase6_sp.py` `_emit_final` / `_emit_pass`（issue body 組裝處）。

**讀取方式**：每週日手動或 cron 跑：
```bash
gh issue list -R huansbox/mlb-fantasy --label fa-scan --limit 14 --json body | \
  jq '[.[].body | capture("phase6_metrics:\\s*(?<m>\\{[^}]+\\})") | .m | fromjson]'
```
→ 算 7-day / 14-day P1 match rate + review trigger rate。

### 4. 撤退門檻（C2）

- **M1 條件**：連續 2 週 P1 match rate < (spike fixture baseline -1σ)
- **M4 條件**：連續 2 週 review trigger rate > 75%（master 自我承認 ambiguous 太頻繁）
- **任一觸發** → 降 G1 single LLM call（fallback）

### 5. Fallback (G1) — 觸發後實作

只在撤退觸發時才寫，先不 commit：
- 新建 `prompt_phase6_sp_single.txt` — 1 個 prompt 看 my-team SP 池 + FA 池 + raw + 5-slot percentile + tags + 14d trad + %owned，輸出 `drop_X_add_Y` / `watch` / `pass`
- `_phase6_sp.process_sp_v4` 加 dispatch flag — 若 fallback enabled 直接走 single call，不跑 8-step pipeline
- batter v4 thin 已是這形態，可參考其 prompt 骨架

---

## 完整流程（B1 後）

```
Layer 1.5 (Python): Rotation Gate 排除 pure RP
Layer 4 (Python): hard filter
  - cant_cut 排除
  - BBE <30 → low_confidence_excluded
  - Slump hold (2025 Sum ≥24 且 IP ≥50)
  - SP Sum ≥40 排除（新增）
  - pick_weakest_v4_sp 取剩餘最弱 4 人
Layer 5 (LLM, multi-agent):
  step1×3 (rank) → step2 master (整合 + LLM 自判 borderline)
    → [if borderline] step3×3 (review) → re-eval (gated)
  classify×3 → master rank → review×3 (gated) → re-eval (gated)
  final master (1 call) → action

Issue body footer: phase6_metrics HTML 註解
```

---

## 實作骨架

### Commit 拆分（建議）

| # | 內容 | 檔案 | 測試 |
|---|---|---|---|
| 1 | `fa_compute.py` 加 SP Sum ≥40 排除 + `pick_weakest_v4_sp` 過濾邏輯 | `fa_compute.py` | `tests/test_fa_compute_v4.py` 加 case |
| 2 | `_phase6_sp.py` `_slim_my_team_entry` / `_slim_fa_entry` 拿掉 sum / urgency / evaluation tags 欄位 | `_phase6_sp.py:110-178` | `tests/test_phase6_sp.py` 加 schema test（payload 不應有 `sum` 欄位）|
| 3 | 5 個 prompt 改寫（拿掉 sum / urgency / evaluation tags 引用 + master borderline 改 LLM 自判）| `prompt_phase6_*.txt` × 5 | spike fixture 重跑 verify schema |
| 4 | Issue body 加 `phase6_metrics` HTML 註解 | `_phase6_sp.py` `_emit_final` / `_emit_pass` | unit test verify metric block 結構 |
| 5 | spike fixture 重跑 baseline + 文件化 | `tests/multi_agent_spike.py` | 跑 5-10 case 算 baseline P1 match rate / review trigger rate，記入 `docs/sp-b1-baseline.md` |
| 6 | 上線（merge 到 master）+ 觀察期開始 | — | — |

可合併成 1 個 PR（B1 cutover），或 commit 1-2 + commit 3-5 + commit 6 三波。

### 觀察期 SOP（B1 上線後）

- **Week 1-2**：每週日 `gh api` 抓最近 7 天 fa-scan issue → 算 P1 match rate / review trigger rate → 記入 `waiver-log.md` 觀察段或新檔 `docs/sp-b1-observation.md`
- **撤退觸發** → 寫 G1 fallback prompt + dispatch flag → 切換
- **觀察期結束（4 週後）** → review baseline 是否要重設 / multi-agent 是否保留決議

---

## 尚待決定的細節（AI 自答 + 待用戶 verify）

| 待驗項 | AI 推薦 | Verification 方法 |
|---|---|---|
| **SP Sum ≥40 數字校準** | 40（P75+ 全方位 ≈ 5 slot × 8 分 = 40，對齊 batter Sum≥25 = 3 slot × 8.3 分）| 跑 `daily-advisor/calc_v4_percentiles.py` 看 2025 SP 池 Sum 分布；若 P75 落 35-38 → 改 36；若落 42-45 → 改 42 |
| **spike fixture 樣本選擇** | 用 `_tools/multi_agent_spike.py` 跑 5-10 case：fa-scan #149（已知 anchor 失效案例）+ 過去 1-2 週 5-7 個 daily issue | 樣本太小信賴區間寬，可考慮 mixed strategy（spike fixture 設「初始門檻」+ 上線第 1 週實測校準）|
| **M4 baseline 設定法** | spike fixture 算 master 標 borderline 比例 → ±20% 作 baseline 區間；上線第 1 週若實測 trigger rate 落區間外 → 重設 | 第 1 週仍記錄不撤退，第 2 週起套門檻 |
| **fa_scan_v4.py 命運** | 趁 B1 cutover 同步退役（CLAUDE.md TODO 三選一決定為「退役」）— v4 已 production，CLI 工具 frontend 命運不需保留 | retire commit 1-2 行（mv 進 archive/ 或 git rm）|

---

## Rollback Plan

- **方式**：git revert（v4 cutover Stage F-3 已建議路徑）
- **理由**：v4 主流程已穩跑 8+ 天，B1 是漸進改動。引入 feature flag 增加維護面，不划算
- **粒度**：commit 拆分 #1-#6，rollback 可選擇性 revert
  - 若 spike fixture baseline 跑出來共識率掉到 <30%（極端 dissent，疑似 raw 訊號本身 ambiguous）→ revert commits #2-#5，保留 #1 SP Sum≥40 + 監控 metadata
  - 若上線後 1 週內 daily issue body 解析失敗 → revert commit #4 重寫
  - 若觀察期結論 multi-agent 沒價值 → 不 revert，跑 G1 fallback path

---

## 與其他 CLAUDE.md TODO 的交互

| TODO | 與本 cutover 的關係 |
|---|---|
| 框架對稱性檢視 | ✅ 本 cutover 主目標 |
| SP Phase 6 prompt 拿掉 Sum 暴露 | ✅ 本 cutover Q5 涵蓋 |
| RP 框架 v4 升級 | 不在本 scope。RP 仍走 v2，B1 只動 SP path |
| SP 21d Δ xwOBACON 絕對門檻校準 | 不在本 scope。仍是 prompt 文字校準題，與 B1 改動正交 |
| Severino transformation 驗證 | 不在本 scope |
| Batter Phase 6 multi-agent 上線時觸發 SP 對齊評估 | **倒序執行**：原計畫是 batter Phase 6 上線後再評估 SP；本 cutover 反向先動 SP（基於 2026-05-04 SP Sum lazy 引用觀察）。Batter Phase 6 上線時要重評：是否仍按原計畫升 batter，或 batter 留 thin（已對稱無需動）|
| Phase 5 minor refactor finding D | 不在本 scope。fa_compute vs fa_scan 雙重 batter Sum 實作可後續處理 |
| CLAUDE.md cleanup Task 2 | 不在本 scope |

---

## 預期效果

- **正向**：multi-agent dissent surface 機制真正啟動；M1 / M4 監控提供撤退邊界，避免無限觀察期 drift；SP / batter 框架對稱降未來維護面
- **風險**：B1 上線初期共識率可能下降（從 100% 假共識變成 60-80% 真共識），daily SP 決策建議可能偶有變化（master 的 borderline 判定變得依 raw 矛盾，不再是 deterministic）— 但這是設計目的，非缺陷
- **觀察期可能浮現的問題**：master 從 raw 自判 borderline 太敏感（review trigger 過高）/ 太遲鈍（review 從不觸發但實際決策有偏）→ 需 prompt 微調
