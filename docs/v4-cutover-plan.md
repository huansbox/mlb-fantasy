# v4 Production Cutover — Detailed Implementation Plan

> **Status**：實作計畫（2026-04-25）。把 `docs/sp-framework-v4-balanced.md` §「實作計畫（Phase C）」高層描述展開為 step-by-step。
> **前提**：已完成項目 — fa_compute.py v4 函式、fa_scan_v4.py CLI parallel 工具、62 v4 unit tests、backfill_prior_stats_v4.py 工具（未跑）、21d xwOBACON 端點研究（4 行 patch 設計完）。
> **若同波執行 Phase 6**：讀此文檔 + `docs/fa_scan-claude-decision-layer-design.md`。Phase 6 與 v4 cutover 共用 prompt 重寫窗口（design doc §6 已說明）。

---

## 1. Cutover 階段總覽（A-F）

依 design doc §6 的 A-F 框架，每階段加上 deliverable + 測試 + 風險點：

| Stage | 名稱 | 主要輸出 | 風險 |
|-------|------|---------|------|
| **A** | 資料層到位 | roster_config.json 含 v4 prior_stats + savant_rolling.json 含 21d xwobacon | Savant endpoint 失誤 |
| **B** | fa_compute v4 整合 | _decision-less_ 版 v4 tag 函式（為 Phase 6 鋪路）+ tests | 雙重邏輯路徑混淆 |
| **C** | prompt 重寫 | prompt_fa_scan_pass2_sp.txt v4 版 | Claude 行為改變 |
| **D** | _process_group("sp") 改寫 | fa_scan.py SP 線跑 v4 機械 + v4 prompt | production 推送中斷 |
| **E** | Feature flag 並行驗證 | VPS cron 同跑 v2 (live Telegram) + v4 (log only) 1-2 週 | 雙倍 Savant fetch 負載 |
| **F** | 切換 + 清 v2 | `SP_FRAMEWORK_VERSION=v4` 設為 default + 移除 v2 SP 分支 | 回滾路徑消失 |

---

## 2. Stage A — 資料層到位

### A.1 跑 backfill_prior_stats_v4

```bash
# 本機（先看名單，安全）
cd daily-advisor
python3 backfill_prior_stats_v4.py --dry-run

# 確認名單合理後寫入
python3 backfill_prior_stats_v4.py
```

**Deliverable**：`roster_config.json` 中所有 SP 的 `prior_stats` 多三欄 `whiff_pct` / `gb_pct` / `xwobacon`。

**驗證**：
- `git diff daily-advisor/roster_config.json` 範圍只含 prior_stats 三欄 + 縮排
- 抽 3 位 SP 對照 Baseball Savant 網站 player page 的 2025 stats（whiff_pct 對 pitch-arsenal-stats 加權後值；gb_pct 對 batted-ball 顯示值；xwobacon 對 custom leaderboard 值）
- 跑 `python3 -m pytest tests/test_backfill_prior_stats_v4.py` 仍 11 通過

**驗證腳本（建議）**：寫個 ad-hoc `verify_v4_backfill.py` 取 3 位 SP 從 Savant 抓即時值對照（差距 ≤0.005 視為通過）。

**回滾**：`git checkout daily-advisor/roster_config.json`（檔案被改但無 push 時可直接回退）。

### A.2 savant_rolling.py 加 21d xwobacon

按 `docs/savant-xwobacon-endpoint-research.md` §4.1 的 4 行 patch：

```python
# savant_rolling.py _aggregate_pitches() 末段
if bbe_count > 0:
    result["xwobacon"] = round(sum_xwoba_on_bbe / bbe_count, 3)
```

**Deliverable**：
- `savant_rolling.py` 加 4 行
- 新檔 `daily-advisor/tests/test_savant_rolling.py` 含 4 測試（見研究 doc §4.3）

**驗證**：
- 跑 `python3 savant_rolling.py` 一次 → `savant_rolling.json` 中 pitchers 區段每位都有 `xwobacon` 欄位
- 抽一位 SP（如 Skubal）跑全季窗口 → 校準 vs 季全 xwobacon（研究 doc §4.4）
- pytest 過

**Cron 變更**：無 — savant_rolling 已 cron TW 12:00 跑，patch 後當日下次跑就有 xwobacon。

**回滾**：revert commit。

### A.3 Stage A commit 順序

1. `feat(savant_rolling): add 21d xwOBACON via aggregate-side computation` + tests
2. （手動跑 backfill，無需 commit code，但需 commit `roster_config.json` diff）
3. `chore(roster): backfill 2025 SP v4 metrics (whiff/gb/xwobacon)`

兩個 commit 互不依賴，可並行；但驗證上順序如此。

---

## 3. Stage B — fa_compute v4 整合（去 decision，鋪 Phase 6）

### B.1 目前狀態

`fa_compute.py` 已有 v4 函式：
- `compute_sum_score_v4_sp` / `rotation_gate_v4` / `luck_tag_v4`
- `v4_add_tags_sp` / `v4_warn_tags_sp` / `v4_decision_sp`

但 v2 的 `_decision_from_tags`（line 待查）也仍在 — 切換時要決定保留還是移除。

### B.2 Phase 6 同波 vs 純 v4 cutover 兩條路

| 路徑 | 改動 |
|------|------|
| **純 v4**（保 Phase 5 機械決策模式）| 把 v4 函式整合進 fa_scan.py SP 線；保留 `v4_decision_sp` 直接給 decision；prompt 只「翻譯」decision |
| **Phase 6 同波**（推薦，design doc §6 建議）| 移除 `v4_decision_sp`（或停用其 callsite）；prompt 改為 multi-agent orchestration；fa_compute 只給 tag 訊號 |

**推薦路徑**：Phase 6 同波。理由：design doc 已分析「prompt 改一次比改兩次便宜」+ `fa_scan-claude-decision-layer-design.md` §7 已詳化決策。

### B.3 純 v4 路徑 deliverables（若選擇分波）

如果要分波先做純 v4：
- 不動 `v4_decision_sp` 或 `v2_decision_from_tags`
- B 階段空集合，直接跳 C

### B.4 Phase 6 同波 deliverables

- `fa_compute.py` 移除 SP 線的 `_decision_from_tags` 呼叫（保留函式但 callsite 切到 tag-only output）
- 新函式 `compute_sp_signals(fa, anchor)` 回傳 `{sum_diff, breakdown_diff, add_tags, warn_tags, win_gate_passed, anchor_name}` — 無 decision
- 移除 SP 相關的 tests `assert result["decision"] == ...`，改 assert tag set
- batter 線**完全不動**（v2 機械決策保留）

**驗證**：147+ tests pass（v4 tests 已 62 個，移除 SP decision assertion 後不應失敗）。

### B.5 Stage B commit

`refactor(fa_compute): remove SP decision from compute_fa_tags (Phase 6 prep)`

---

## 4. Stage C — prompt 重寫

### C.1 目前狀態

`daily-advisor/prompt_fa_scan_pass2_sp.txt` 是 v2 + Phase 5 機械決策模式 prompt。

### C.2 純 v4 路徑（不推薦）

只把規則描述從 v2 改 v4，prompt 結構不變。

### C.3 Phase 6 同波路徑

依 `docs/fa_scan-claude-decision-layer-design.md` §5.2：
- 從「翻譯 Python decision」改寫為「給最終決策 + 寫 reason」
- 加 multi-agent orchestration 段（或拆多個 prompt 檔）
- 加「看具體數值不只看 Sum 分」段（v4 百分位分桶 known limitation 緩衝）
- 加 21d Δ xwOBACON 絕對量級提示（|Δ|<0.030 / 0.030-0.050 / ≥0.050 / BBE<20）
- 加 urgency 並列 tiebreak 規則

**Deliverables**：
- `daily-advisor/prompt_fa_scan_pass2_sp.txt` v4 版（保留 v2 為 `prompt_fa_scan_pass2_sp.v2.txt` 備份）
- 若 Phase 6 多 prompt：新建 `prompt_fa_scan_pass2_sp_step1.txt` / `_step3review.txt` 等

**驗證**：
- 手動 `claude -p "$(cat prompt_fa_scan_pass2_sp.txt)" < sample_data.json` 跑一次 04-22 Nola/Meyer/Pfaadt 案例
- 確認輸出含預期欄位（最終 decision / reason / waiver-log NEW/UPDATE 行）

### C.4 Stage C commit

`docs(prompts): rewrite SP Pass 2 prompt for v4 framework + Phase 6 decision layer`

---

## 5. Stage D — `_process_group("sp")` 改寫

### D.1 整合層（fa_scan.py）

依 `docs/fa_scan-claude-decision-layer-design.md` §5.4：
- Layer 4（fa_compute 機械層）：呼叫 v4 函式，讀 v4 prior_stats + 21d xwobacon
- Layer 5（Claude 層）：multi-agent orchestration（按 §7.1 推薦用 `claude -p` subprocess + threading）

### D.2 Multi-agent orchestrator 工具函數

新增模組 `daily-advisor/_multi_agent.py`（或內嵌 fa_scan.py）：

```python
def run_parallel_agents(prompt_template: str, contexts: list[dict], n_agents: int = 3) -> list[dict]:
    """spawn n_agents x claude -p subprocess in threading, collect structured outputs."""

def consensus_check(rankings: list[list[str]]) -> tuple[bool, str | None]:
    """
    Returns (agreed, dissent_reason).
    Agreement rule: P1 match + dissent_count < 2.
    """

def reevaluate_loop(initial_rankings, master_decision, max_rounds=1):
    """One round of review; on disagreement, return last version + flag."""
```

### D.3 _process_group("sp") 改寫骨架

```python
def _process_group_sp_v4(group_data, args, env):
    # Layer 4: mechanical
    weakest, low_conf = fa_compute.pick_weakest_v4(group_data["roster"])
    urgency = fa_compute.compute_urgency_v4(weakest)

    # Layer 5: multi-agent decision
    rankings = run_parallel_agents(prompt_step1, ..., n_agents=3)
    master = run_master_decision(prompt_step2, rankings)
    reviews = run_parallel_agents(prompt_step3review, ..., n_agents=3)
    agreed, _ = consensus_check([master.ranking] + [r.ranking for r in reviews])

    if not agreed:
        master = reevaluate_loop(rankings, master, max_rounds=1)
        # 即使 reeval 不收斂，degradation 走 master.last + flag

    # FA line（同結構）
    ...

    # Final decision (drop X / add Y / 觀察 / pass)
    final = run_final_decision(prompt_final, master, fa_ranked)
    return final
```

### D.4 Feature flag

新環境變數 `SP_FRAMEWORK_VERSION` (`v2` 或 `v4`)：

```python
# fa_scan.py
SP_FRAMEWORK = os.environ.get("SP_FRAMEWORK_VERSION", "v2")  # v2 default for safety

if SP_FRAMEWORK == "v4":
    return _process_group_sp_v4(...)
else:
    return _process_group_sp_v2(...)
```

### D.5 Stage D commit 順序

1. `feat(fa_scan): _multi_agent helper for parallel claude -p orchestration`
2. `feat(fa_scan): _process_group_sp_v4 with multi-agent decision layer`
3. `feat(fa_scan): SP_FRAMEWORK_VERSION env flag for v2/v4 dispatch`

---

## 6. Stage E — Feature flag 並行驗證

### E.1 並行模式

VPS cron 加第二份 fa_scan：

```cron
# /etc/cron.d/daily-advisor
# Existing v2 (live Telegram + GitHub Issue + waiver-log)
30 12 * * * mlb cd /opt/mlb-fantasy/daily-advisor && python3 fa_scan.py >> /var/log/fa_scan_v2.log 2>&1

# New v4 parallel (log only — no Telegram, no Issue, no waiver-log)
35 12 * * * mlb cd /opt/mlb-fantasy/daily-advisor && SP_FRAMEWORK_VERSION=v4 python3 fa_scan.py --no-send --no-issue --no-waiver-log >> /var/log/fa_scan_v4.log 2>&1
```

⚠️ **注意**：`--no-issue` / `--no-waiver-log` 需要實作（目前 fa_scan.py 只有 `--no-send`）— 加進 Stage D。

### E.2 並行期間（1-2 週）每天人工對照

對照工具：寫 `daily-advisor/_tools/diff_v2_v4_outputs.py`（仿 _trade_lookup 結構）：
- 從 GitHub Issue archive 抓當天 v2 輸出
- 從 v4 log 抓當天 v4 輸出
- diff 兩份的 (a) drop P1 (b) FA 推薦 (c) action

每天人工檢視差異，記錄到 `docs/v4-cutover-parallel-log.md`。

**綠燈條件**（決定 cutover）：
- 連續 5+ 天 v4 行為合理（不出現「明顯誤判」）
- v4 cost / latency 在預算內（依 Phase 6 §7.6 spike 結果）
- v4 對 04-22 Nola/Meyer/Pfaadt 等歷史 case 的判斷符合事後正確答案

**紅燈條件**（暫停 cutover）：
- v4 任何一天判 P1 = cant_cut 球員
- v4 月成本超預算 50%
- v4 三輪 re-eval 仍不收斂的次數 > 1 次

### E.3 Stage E commit 順序

1. `feat(fa_scan): --no-issue + --no-waiver-log flags for parallel v4 run`
2. `feat(_tools): diff_v2_v4_outputs.py for cutover parallel comparison`
3. `chore(cron): add v4 parallel cron entry on VPS`（VPS-side 修改，不在 git repo）

---

## 7. Stage F — 切換 + 清 v2 code

### F.1 Cutover 動作

```bash
# 1. 改 cron default
# /etc/cron.d/daily-advisor:
# 把 v4 改為主 cron（live Telegram），v2 行刪除或註解

# 2. 改 fa_scan.py default
# SP_FRAMEWORK = os.environ.get("SP_FRAMEWORK_VERSION", "v4")  # was "v2"
```

### F.2 v2 code 清理

| 移除 | 保留（不動）|
|------|-------------|
| `fa_compute.compute_sum_score(...) ` SP 分支 | batter 分支 |
| `fa_compute._SP_METRICS_V2` | `_BATTER_METRICS` |
| `fa_compute._decision_from_tags` SP 分支 | batter 分支 |
| `_process_group_sp_v2()` | `_process_group_batter_v2()` |
| `prompt_fa_scan_pass2_sp.v2.txt` | batter prompt |
| 相關 v2 SP tests | batter tests |
| `fa_scan_v4.py` CLI（已 production 整合，不需 parallel 工具） | — |

### F.3 CLAUDE.md 更新

依 `docs/sp-framework-v4-balanced.md` §「階段 5.5」：
- 「SP 評估」章節改寫為 v4
- 百分位表補 Whiff% / GB% / xwOBACON / BB/9 / IP/GS 分布
- 進行中補強行動章節更新為 v4 解讀

### F.4 Stage F commit 順序

1. `feat(fa_scan): default to v4 SP framework (cutover complete)`
2. `chore: remove v2 SP framework (fa_compute, fa_scan, prompts, tests)`
3. `docs(CLAUDE): rewrite SP evaluation section for v4`
4. `chore(cron): remove v2 parallel cron, v4 is now main`

### F.5 Rollback path

若 cutover 後 7 天內出現問題：
- `git revert` Stage F commits
- 恢復 cron entry
- 改 default `SP_FRAMEWORK_VERSION=v2`

7 天後 v2 code 應徹底清除（不再 maintain）。

---

## 8. 排程預估

| Stage | 工時 | 阻塞點 |
|-------|------|--------|
| A | 1-2 hr | Savant fetch（需網路） |
| B | 2-3 hr | 雙重邏輯小心整理 |
| C | 3-5 hr（Phase 6 同波）/ 1 hr（純 v4）| prompt 設計 |
| D | 4-6 hr | multi-agent orchestrator 寫 |
| E | 1 hr 設置 + **7-14 天**自然驗證 | 並行期觀察 |
| F | 1-2 hr | 清理 + 文檔 |

**total active dev time**：~12-18 hr (Phase 6 同波) / ~5-8 hr (純 v4)
**total elapsed time**：~10-14 天（含 E 並行期）

建議分 4-5 個 session：
1. Session 1：Stage A（資料層）
2. Session 2：Stage B + C（fa_compute + prompt）
3. Session 3：Stage D（orchestrator）
4. Session 4-5：Stage E 期間每日 review + Stage F cutover

---

## 9. 風險與緩解

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| Savant endpoint 失誤期間 backfill 失敗 | 低 | 中 | 重試 retry，記入 `docs/savant-smoke-test-design.md`（task G） |
| v4 月成本超預算 | 中 | 中 | Phase 6 §7.6 spike 先確認；改 Haiku 跑 review；改 batch API |
| Multi-agent re-eval 迴圈卡住 | 低 | 高 | §7.3 推薦 1 輪上限，自動 degradation |
| Cutover 後當天 fa_scan 推送中斷 | 低 | 高（影響日常決策） | Feature flag rollback；保留 `fa_scan_v2.py` symlink 一週 |
| v4 prompt 改寫期間 Claude 行為偏移 | 中 | 中 | E 階段並行 1-2 週，人工 5+ 天綠燈才切 |
| Phase 6 multi-agent 共識規則太嚴 → 月成本爆 | 中 | 中 | §7.2 推薦寬鬆規則（P1 match + dissent ≥2） |

---

## 10. Checkpoint：開始動工前的最終 review

動 Stage A 前確認：
- [ ] 是否選 Phase 6 同波 OR 純 v4 cutover？（推薦同波）
- [ ] `docs/fa_scan-claude-decision-layer-design.md` §7.8 推薦摘要是否同意？
- [ ] Phase 6 spike 是否先跑（task B 計畫）？
- [ ] 預算是否確認可接受 $20-32/月（Phase 6 同波）？

動 Stage E 前確認：
- [ ] VPS cron 並行加進去後，雙倍 Savant fetch 是否觸發 rate limit？（pre-test 用 fa_scan_v4 已知不會）
- [ ] `--no-issue` / `--no-waiver-log` 已實作？
- [ ] `diff_v2_v4_outputs.py` 已寫？

動 Stage F 前確認：
- [ ] 並行 ≥7 天 v4 行為一致？
- [ ] Cost / latency 在預算內？
- [ ] CLAUDE.md SP 章節改寫稿準備好？

---

## 11. 不變的部分

- batter 線（v2 + Phase 5 機械決策保留，design doc §8）
- waiver-log 自動更新機制（`_WAIVER_LOG_LOCK` + git pull/edit/commit/push）
- Telegram 推送格式（v4 內容變但格式不變）
- GitHub Issue archive 格式
- Cron 排程時間（雖加新 entry，主推送時間不變）
- `_factor_rolling` Python 暫返 0 + 原始 Δ + BBE 餵 Claude 的決定（CLAUDE.md TODO 已鎖定）
