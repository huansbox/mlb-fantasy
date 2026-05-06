# Handoff: SP v4 Cutover Completion (2026-05-06)

> **狀態**：⏳ 待辦（7 項 production v2 殘留待修；估 5-7 hr / 5-7 commits）
>
> **觸發**：2026-05-06 完成 `yahoo_query.py savant` v4 升級（[handoff-il-na-filter](handoff-il-na-filter.md) Part 2）後，因該案是 v4 cutover 第二個漏網（5/4 framework lens 是第一個），決定做系統性 v2 grep 掃描。發現 v4 cutover 實際上**僅 Phase 6 multi-agent + 5 個 SP prompt 真的對齊 v4**，其他多個 production 路徑（每日戰報資料層 / FA 過濾 gate / Phase 6 context 建構 / 週覆盤 / FA prior 寫入）仍是 v2。
>
> **審查記錄**：本清單由 feature-dev:code-reviewer agent 獨立驗證 + 補漏（2026-05-06 session）。原本 6 項，補 3 漏抓、移除 1 false positive。

## 背景：v4 cutover 範圍盤點

### ✅ 已對齊 v4
- `fa_compute.py` v4 SP scoring helpers（`compute_sum_score_v4_sp` / `rotation_gate_v4` / `luck_tag_v4` / `v4_add_tags_sp` / `v4_warn_tags_sp`）
- `_phase6_sp.py` 8-step multi-agent orchestrator
- 5 個 `prompt_phase6_sp_*.txt`（commit `dbac88e` 2026-04-26）
- `daily_advisor.py PITCHER_V4_PCTILES` 常數（commit `673b4cf` 2026-05-06，跟 yahoo_query.py savant 一起）
- `yahoo_query.py savant` SP 路徑（commit `673b4cf` 2026-05-06）

### ❌ 仍是 v2（本 handoff 範圍）
詳見下方 7 項清單。

### 🟡 By design 仍是 v2（不動）
- `daily_advisor.py PITCHER_PCTILES` — RP 用
- `prompt_fa_scan_rp.txt` — RP prompt
- `fa_scan.py _fmt_roster_pitcher(pt="rp")` — RP 顯示
- `yahoo_query.py savant` RP path — RP framework 還沒升級
- `roster_config.json prior_stats` v2 欄位 — 與 v4 欄位**並存**（v2 供 fallback / RP 路徑讀，v4 供 SP scoring 讀）

> RP 框架 v4 升級已單獨進 CLAUDE.md TODO（1-2 週工作量）。

---

## 7 項 v2 殘留（按優先序）

### P1 — `daily_advisor.py` 每日戰報 SP 資料路徑（最上游）

**檔案**：`daily-advisor/daily_advisor.py`
- L587-610 `fetch_savant_for_pitchers()` — 抓 SP Savant 資料
- L613-635 `format_pitcher_savant()` — 格式化給 prompt
- 輸出消費點：L1216-1220 「SP 先發」區塊送進每日速報 prompt

**問題**：資料結構只抓 `xera / xwoba / hh_pct / barrel_pct`，**v4 5-slot（whiff_pct / bb9 / gb_pct / xwobacon / ip_gs）完全沒抓**。即使 prompt 改了 v4，資料層也餵不出來。

**修正方向**：
1. `fetch_savant_for_pitchers` 補抓 v4 5-slot（複用 `fa_scan_v4.assemble_data` 或新寫 single-pitcher fetcher，類似 yahoo_query.py 的 `_fetch_pitcher_v4`）
2. `format_pitcher_savant` 加 v4 5-slot 顯示（含 `pctile_tag(..., 'sp_v4')` 標籤）
3. 保留 `xera` 給 luck signal（xERA-ERA Δ）— 這在 v4 仍是合法輔助訊號
4. **HH% / Barrel% allowed 不再顯示**（CLAUDE.md L124 規則「不在 5-slot 的百分位只是 context，不是 first-order signal」）

**注意**：「對方 SP 評估」與「我方 SP 自我評估」是同一框架（都是 SP 品質評估），不要被 reviewer 提到的「對方 vs 自我」迷惑。v4 是 unified 框架。

**估時**：1.5-2 hr

---

### P2 — `fa_scan.py` SP_THRESHOLDS（FA 池 v2 預過濾，最隱形 bug）

**檔案**：`daily-advisor/fa_scan.py`
- L568-572 `SP_THRESHOLDS = [...]` — v2 三指標 quality gate
- L800-801 `_check_thresholds(metrics, SP_THRESHOLDS) < 2` — 過濾邏輯

**問題**：FA SP 候選必須通過 v2 三指標 P40 中至少 2 項才能進入 Phase 6 池。**v4 elite 但 v2 borderline 的 FA 被預過濾**，Phase 6 multi-agent 根本看不到。違背 v4 cutover「Phase 6 看 v4 候選」的設計前提。

**修正方向**：
1. 把 SP_THRESHOLDS 換成 v4 5-slot Sum 門檻（例如 Sum ≥ X，X 待定）
2. 或改用 `compute_sum_score_v4_sp` 取 Sum 後過濾，類似 batter 的 `_calc_batter_sum + BATTER_SUM_THRESHOLD` pattern
3. 候選池資料抓取也要對應升級（L780 附近 metrics dict 只有 v2 欄位）

**Sum 門檻待定**：v4 Sum 範圍 5-50。「P40 中至少 2 項」≈ Sum ≥ 25 左右？需校準（`fa_compute.py` 已有 batter Sum 21 為 P55+ 的對應，SP v4 需重算）。

**估時**：0.5-1 hr（單點改但需校準門檻）

---

### P3 — `fa_scan.py` Phase 6 context 建構（顯示 + 排序）

**檔案**：`daily-advisor/fa_scan.py`
- L1098-1102 `_get_sort_key_sp` — 用 `xera` 排序
- L1119 `_fmt_roster_pitcher(p, "pitcher", ...)` — SP 顯示路徑
- L1183-1234 `_fmt_roster_pitcher` 函式本體 — 2026/2025 雙路徑都輸出 v2

**問題**：`build_roster_summary` 是 Phase 6 multi-agent 的 input prompt 製作。SP 排序用 v2 xERA、SP 顯示也是 v2。**Phase 6 拿到的「我方最弱 SP」清單和顯示資料全是 v2 lens**。

**修正方向**：
1. `_get_sort_key_sp` 改用 v4 Sum 排序（`compute_sum_score_v4_sp` 已存在）
2. `_fmt_roster_pitcher` 對 SP（pt="pitcher"）路徑改 v4 5-slot 輸出 — 保留 RP 分支不動
3. 2026 primary 路徑用 live savant_2026 + game-log IP/GS，2025 fallback 路徑改用 roster_config 的 v4 prior_stats

**注意**：RP 分支（pt="rp"）保持 v2，本 PR 不動。`_get_sort_key_sp` 是 SP 專用，可直接改。

**估時**：1-1.5 hr

---

### P4 — `fa_scan.py` FA `prior_stats` 寫入只有 v2 欄位

**檔案**：`daily-advisor/fa_scan.py` L2338-2348（SP 分支）

**問題**：`prior_stats = {"xera": ..., "xwoba_allowed": ..., "hh_pct_allowed": ..., "ip": ...}`，沒寫入 v4 欄位。Phase 6 FA classify 看到的 2025 prior 只有 v2 lens。

**修正方向**：
1. `savant_25` 增加 v4 欄位（whiff_pct / gb_pct / xwobacon — 但注意 Savant batted-ball endpoint 對歷史年份失效，gb_pct 可能拿不到，參考 yahoo_query.py 的 fallback：past year skip batted-ball + 標 `—`）
2. `prior_stats` 寫入 v4 欄位 + 保留 v2（並存設計）
3. 確認 IP/GS prior：MLB API game log 對歷史年份應該有效（fa_scan_v4 已驗證）

**Gotcha**：FA 球員的 2025 v4 prior 必須**動態抓**（不在 roster_config）。Savant batted-ball endpoint 歷史年份失效 → 部分 v4 欄位（gb_pct / bbe）對 2025 抓不到 — 接受並標 `—`，類似 yahoo_query.py 設計。

**估時**：0.5-1 hr

---

### P5 — `weekly_review.py` SP 顯示 v2

**檔案**：`daily-advisor/weekly_review.py`
- L760-779 季 dict 寫入 + 百分位計算 — `xera / xwoba / hh_pct / barrel_pct` v2

**問題**：每週覆盤 SP 顯示是 v2，每週 Monday 跑。

**修正方向**：對齊 P3 的 SP 顯示模式 — v4 5-slot 主表 + xera-era luck 輔助。

**估時**：0.5-1 hr

---

### P6 — `prompt_template.txt` / `prompt_template_morning.txt` SP matchup 文字

**檔案**：
- `daily-advisor/prompt_template.txt` L15-16, L27-28
- `daily-advisor/prompt_template_morning.txt` L19-20

**問題**：`HH% allowed > 40.8%` / `Barrel% allowed > 8.5%` 等門檻文字。

**修正方向**：改 v4 5-slot 描述。例如 Whiff% / xwOBACON 高 = 投手被打不爽 → 打者有利。

**鎖死依賴**：**必須 P1 先做**。否則 prompt 寫了 v4 指標但 daily_advisor.py 資料層沒抓 v4 欄位 = LLM 看不到資料。

**估時**：0.5 hr（純 prompt 文字，但需 P1 完成）

---

### P7 — `roster_stats.py` CLI 顯示 v2

**檔案**：`daily-advisor/roster_stats.py` L180-208

**問題**：每週覆盤前手動跑的 CLI 工具，輸出 v2 指標。低頻但漏。

**修正方向**：對齊 v4 5-slot 顯示。

**估時**：0.5 hr（可能能 batch 進 P3 共享 helper）

---

## 序列依賴

```
P1 ─────┐
         ├─→ P6（prompt 改文字）依賴 P1（資料層先有 v4 欄位）
P2 ─── 獨立
P3 ─── 獨立（但和 P7 可能 share helper）
P4 ─── 獨立
P5 ─── 獨立（但和 P3 可能 share helper）
P7 ─── 可 batch 進 P3
```

## 建議 commit 分組

| Commit | 範圍 | 估時 |
|---|---|---|
| 1 | **P1** + P6 — 每日戰報資料層 + prompt 配套 | 2-2.5 hr |
| 2 | **P2** — fa_scan SP_THRESHOLDS v4 升級 | 0.5-1 hr |
| 3 | **P3** + P7 — fa_scan Phase 6 context + roster_stats CLI（共享 helper）| 1.5-2 hr |
| 4 | **P4** — FA prior_stats v4 欄位 | 0.5-1 hr |
| 5 | **P5** — weekly_review SP v4 顯示 | 0.5-1 hr |

合計 5 commits / 5-7 hr。

## 待決問題（下個 session 確認）

1. **P2 的 v4 Sum 門檻校準**：直接用「Sum ≥ 25」（≈P50 中間）還是更嚴 / 更鬆？需看 2026 季中 Phase 6 拿到的池組成決定。建議跑一次 dry-run 比對舊池 vs 新池差異。

2. **HH% / Barrel% allowed 完全移除 vs 保留作 context**：CLAUDE.md L124 講「context only, not first-order」— 是顯示但標 context only，還是直接不顯示？建議統一**不顯示**（對齊 yahoo_query.py savant 設計），減少 LLM 注意力浪費。

3. **`fetch_savant_for_pitchers` 設計**：是 reuse `fa_scan_v4.assemble_data`（已驗證 4 個 CSV + game log call 對單人查詢慢但可接受），還是新寫 single-pitcher fetcher（已在 yahoo_query.py 寫過 `_fetch_pitcher_v4`，可考慮提取共享 helper）？建議**提取共享**：把 yahoo_query.py 的 `_fetch_pitcher_v4` 移到 daily-advisor 模組（例如 `_savant_v4_fetch.py`），yahoo_query.py + daily_advisor.py 都 import。

4. **P4 處理 Savant batted-ball 歷史年份失效**：FA 2025 prior 的 gb_pct 抓不到，標 `—` 或跳過？建議標 `—`（同 yahoo_query.py 設計），LLM 知道是「不可抓」而非「真的差」。

5. **本 handoff 範圍是否需要包含「opposing SP 評估」對齊**：reviewer 質疑過這是「對方 SP 評估」與「自我評估」是否同一框架 — 我認為是同一框架（CLAUDE.md 沒有區分「對方 vs 我方」），但需要在動 P1 / P6 時再對齊一次。

## 風險

- **P2 改 SP_THRESHOLDS 後 FA 池組成可能大變** — Phase 6 收到的候選名單會與過去不一樣，需 1-2 天觀察 cron 行為避免漏推 / 誤推
- **P1/P6 同步改的 prompt + 資料層**需先本機 dry-run（`python3 daily_advisor.py --no-send`）確認 prompt 渲染正確，避免上 production 才發現 LLM 看不懂
- **roster_config.json v2 prior_stats 欄位**保留 — 不要在 P3/P4 順手刪除，因為 RP 路徑 / fallback 路徑仍會讀（並存設計是 by design）

## 相關檔案 / 參考

- 評估框架定義：`CLAUDE.md` 「SP 評估」段（L124-200 附近）
- v4 cutover 設計：`docs/sp-framework-v4-balanced.md`
- Phase 6 multi-agent 設計：`docs/fa_scan-claude-decision-layer-design.md`
- 前置 cutover 過程：`docs/v4-cutover-plan.md`
- 觸發 session 對話：2026-05-06 yahoo_query.py savant Part 2 完成後 v2 grep + reviewer audit
