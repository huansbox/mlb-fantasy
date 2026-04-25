# Phase 6 Multi-Agent Spike 計畫

> **Status**：Spike 計畫（2026-04-25）。供 Phase 6 cutover 動工前 Wave 1.5 執行使用。
> **目標**：用最小代價取得 Phase 6 multi-agent orchestration 的 cost / latency / 行為實測數字，避免「實作完才發現負擔不起」。
> **預估投入**：1-2 天（含執行 + 分析 + 寫 report）。
> **產出**：本文件 + spike 跑完的 raw log 與分析報告（後者寫到 `docs/phase6-multi-agent-spike-results.md`）。

---

## 1. Spike 目標

回答 4 個 cutover 卡點問題：

| Q | 量測項 | 決策影響 |
|---|--------|---------|
| **1. 月成本可接受嗎？** | 單次 SP 線完整流程的 input/output token 總量 + Sonnet pricing | 若超 $30/月 → 改 Haiku 或縮 review 步驟 |
| **2. 延遲可接受嗎？** | 3 agent 平行 `claude -p` 的 wall-clock 總時間 | 若 > 5 min daily 影響 cron 排程 |
| **3. P1 一致率多高？** | 3 agent step 1 排序中 P1 一致的比例 | 影響 §7.2 同意定義的合理性 + re-eval 預期觸發率 |
| **4. Re-eval 收斂率？** | 1 輪 review 後 P1 是否仍一致 | 影響 §7.3 「上限 1 輪 + degradation」是否合理 |

---

## 2. 選 Case

### 2.1 推薦：2026-04-22 Nola vs Meyer vs Pfaadt（fa_scan #98）

**理由**：
- 真實歷史 case，data 已 archive（GitHub Issue + waiver-log）
- 已驗證多視角分歧存在（04-23 三視角 2/3 反對 v3 判斷）— 這個 case 自帶「分歧 ground truth」可校準 multi-agent 行為
- 涉及多個 ⚠️ 警示組合（López 雙警示 / Kelly swingman / Pfaadt 邊際升級）— 測試 multi-agent 處理複雜訊號的能力
- 04-24 v4 框架已給「正確答案」（Nola hold 正確，Pfaadt Sum 37 大勝 +18）→ multi-agent 結果可比對

**Reference data**：
- `docs/nola-lopez-holmes-triview-2026-04-23.md`（三視角 raw evaluations）
- `docs/sp-decisions-backtest.md` §4-§6（決策歷程）
- 我方 4 SP 當時：Skubal / Nola / López / Cantillo / Kelly（4-5 SP，視當天 active）
- FA 候選：Max Meyer (MIA) / Foster Griffin (WSH) / Brandon Pfaadt (AZ)

### 2.2 備選：今日 / 近期 fa_scan archive

從 GitHub Issue 抓最近 7 天的 fa_scan SP 報告：
- 至少 4 個 SP 上 anchor 池
- 至少 3 個 FA 候選有 v4 完整指標

備選的 value：data 較新但 ground truth 不明（未經 multi-view 驗證）。

### 2.3 推薦組合：先跑 2.1 主 case + 1 個 2.2 隨機 case

主 case 用「已知有分歧」case 驗 multi-agent 能否抓到分歧；
隨機 case 用「未知」case 驗 default 一致率（baseline）。

---

## 3. Prompt 草稿

### 3.1 Step 1 prompt（3 agent 平行用）

```
你是 fantasy baseball SP 評估 agent。

任務：對以下 4 位 SP 排序 P1（最該 drop）→ P4（最該保留）。

材料：
- 我方陣容（4 SP）：[name / 5-slot v4 Sum / 5-slot 各分 / 21d Δ xwOBACON / urgency 4 因子 / tags]
- 評估框架：完整 v4 規則（從 docs/sp-framework-v4-balanced.md 摘要）
- 警告：你的判斷將與其他 2 個 agent 並行進行，會由主 Claude 整合 + 3 agent review。

輸出（JSON）：
{
  "ranking": ["P1 name", "P2 name", "P3 name", "P4 name"],
  "rationale": {
    "P1": "為什麼最該 drop（≤80 字，引用具體數值）",
    "P2": "...",
    "P3": "...",
    "P4": "..."
  },
  "agent_id": "agent_1"  // 由 orchestrator 指派
}

注意：
- 不要提「其他 agent 可能怎麼想」
- 不要 hedge（如「也可能 P1 是 X」），每位置給確定答案
- 引用具體 5-slot 分數 + 21d Δ + tag
```

### 3.2 Step 2 主決策 prompt（Claude 整合用）

```
你是 fantasy baseball SP 主決策 Claude。

任務：整合 3 agent 的排序與理由，給最終 P1-P4 順序 + 整合理由。

輸入：
- 3 agent 各自的 ranking + rationale（JSON）
- 完整原始材料

輸出（JSON）：
{
  "final_ranking": ["P1", "P2", "P3", "P4"],
  "rationale": {
    "P1": "整合理由（≤120 字，可引用 agent 觀點 + 你的判斷）",
    ...
  },
  "agent_consensus_summary": "3 agent 的分歧點（如有，否則 'consensus'）"
}

注意：
- 不必跟任何 agent 完全一致，但偏離共識需有理由
- 如果 3 agent 各有不同 P1 → 你需要解釋為什麼選你的 P1
- 不要 weakly aggregate（單純多數決）— 你看到完整數據，可以判斷哪個 agent 看漏什麼
```

### 3.3 Step 3 Review prompt（3 agent 平行用）

```
你是先前 step 1 的 agent_{N}。

任務：看主 Claude 的最終 ranking，判斷你是否同意。

輸入：
- 主 Claude final_ranking + rationale
- 你 step 1 的 ranking + rationale（提醒你原本怎麼判）
- 完整原始材料

輸出（JSON）：
{
  "agree": true/false,
  "agree_on_p1": true/false,  // 只看 P1 是否一致
  "dissent_reason": "若不同意，具體哪裡覺得有問題（≤80 字）",
  "willing_to_concede": "若主 Claude 點出你 step 1 沒看到的訊號 → true"
}

注意：
- 主 Claude 的 ranking 不是 ground truth，但他看了所有 agent 的觀點
- 你不必為了同意而同意；但若主 Claude 解釋合理就 concede
- 不要看其他 agent 的意見（隔離）
```

### 3.4 Step 4 收斂判定（Python 邏輯，不是 prompt）

```python
def consensus_check(master_p1, reviews):
    p1_disagreements = sum(1 for r in reviews if not r["agree_on_p1"])
    return p1_disagreements < 2  # 2 票以上 P1 反對才 re-eval
```

### 3.5 Step 5 FA 二分 prompt（3 agent 平行用）

```
任務：對以下每個 FA 候選 vs 我方 anchor SP（{anchor_name}），分類為「值得研究取代」/「不值得取代」/「邊界」。

材料：
- Anchor: {anchor v4 全套指標 + tags}
- FA 候選: [{name / v4 全套指標 / tags / sum_diff}]

輸出（JSON）：
{
  "classifications": {
    "FA_name_1": "worth" | "not_worth" | "borderline",
    ...
  },
  "rationale": {
    "FA_name_1": "≤60 字理由",
    ...
  }
}

規則：
- worth = 至少 2 ✅ 無 ⚠️
- not_worth = 1 ⚠️ 強警示（短局 / 上場有限 / 樣本小）+ Sum 差 < 5
- borderline = 介於兩者，需主 Claude 排序時細看
- 禁止 maybe / 50% / 不確定
```

### 3.6 Step 6 主決策排序 prompt（同 step 2 結構，省略）

### 3.7 Step 7 Final Decision prompt

```
任務：對「我方最弱 SP（{p1_name}）vs FA1 / FA2 / FA3」一一比較，給最終 action。

輸入：完整材料 + Step 4 排序

輸出（JSON）：
{
  "action": "drop_X_add_Y" | "watch" | "pass",
  "drop": "{name}" | null,
  "add": "{name}" | null,
  "reason": "≤200 字理由（解讀脈絡，不重述規則）",
  "watch_triggers": ["若 watch，列出具體觸發條件"],
  "waiver_log_updates": [
    {"action": "NEW" | "UPDATE", "name": "...", "note": "..."}
  ]
}
```

---

## 4. 執行步驟

### 4.1 環境準備

VPS 應已具備條件：`claude -p` 可呼叫（Phase 5 已用）、Python threading 可用。

本機跑 spike 也可（不需 VPS），但需確認本機 `claude -p` token 不會被誤算到 daily quota。

### 4.2 Spike runner 腳本

寫 `daily-advisor/_tools/multi_agent_spike.py`（新工具，非 production）：

```python
"""multi_agent_spike — measure Phase 6 multi-agent orchestration cost/latency.

Usage:
  python3 _tools/multi_agent_spike.py --case nola_meyer_pfaadt_2026_04_22
  python3 _tools/multi_agent_spike.py --case latest_archive
"""

import argparse, json, subprocess, threading, time
from pathlib import Path

def run_claude_p(prompt: str, stdin_data: str, timeout=300) -> dict:
    """spawn claude -p subprocess, return {output, latency, exit_code}."""
    t0 = time.time()
    proc = subprocess.run(
        ["claude", "-p", prompt],
        input=stdin_data,
        capture_output=True, text=True, timeout=timeout,
    )
    return {
        "output": proc.stdout,
        "stderr": proc.stderr,
        "latency_s": time.time() - t0,
        "exit_code": proc.returncode,
    }

def parallel_agents(prompt_template: str, contexts: list[str], n_agents: int = 3) -> list[dict]:
    """Run n_agents claude -p in parallel via threading."""
    results = [None] * n_agents
    def worker(idx):
        # Inject agent_id into prompt
        prompt = prompt_template.format(agent_id=f"agent_{idx+1}")
        results[idx] = run_claude_p(prompt, contexts[idx])
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_agents)]
    t0 = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    wall_time = time.time() - t0
    return results, wall_time

# 主流程：跑 §3 七個 step，記錄每步 latency / token / output
```

### 4.3 Token / Cost 量測

`claude -p` 每次呼叫的 stderr 通常含 token usage（驗證後寫入腳本）。如不含：
- 替代方案 1：手動 `wc -c` input/output 估算（粗略）
- 替代方案 2：用 Anthropic SDK 跑 spike 取代 `claude -p` 取得精確 token count

### 4.4 量測欄位

每次 step 跑完記錄：

```json
{
  "step": "step_1_agent_1",
  "input_tokens_est": 8123,
  "output_tokens_est": 1456,
  "latency_s": 12.4,
  "exit_code": 0,
  "output_parsed": {...},
  "errors": []
}
```

整次 spike 結束聚合：

```json
{
  "case": "nola_meyer_pfaadt_2026_04_22",
  "total_calls": 15,
  "total_input_tokens": 121845,
  "total_output_tokens": 21678,
  "total_wall_time_s": 187.3,
  "p1_consensus_step1": "Nola 3/3" | "Nola 2/3, López 1/3",
  "p1_consensus_after_review": "agreed" | "1 dissent" | "2 dissent re-eval",
  "reeval_triggered": true/false,
  "final_action": "watch" | "drop_X_add_Y" | "pass",
  "estimated_monthly_cost_usd": 24.50
}
```

---

## 5. 預期 Result Categories

| Result | 解讀 | Cutover 影響 |
|--------|------|-------------|
| **A. 月 < $20 + P1 高一致 + 1 輪收斂** | 最佳：multi-agent 預期效果達成 | 直接走 §7.8 推薦設定，cutover 進行 |
| **B. 月 $20-30 + 行為合理** | 預算內，cutover 可進行 | 同 A |
| **C. 月 > $30 + P1 高一致** | 成本過高但行為可控 | 改 Haiku 跑 step 1 / step 3 review；或縮 review 為 1 agent |
| **D. 月 < $30 + P1 不一致 + 經常 re-eval** | 成本 OK 但收斂不佳 | 鬆綁 §7.2 同意規則（改成 P1 + 多數票）/ 增加 step 1 prompt 約束 |
| **E. 月 > $30 + 收斂不佳** | 雙差，stop and reconsider | 退回純 v4 cutover（不上 Phase 6），或大幅簡化 multi-agent（去 step 3 review）|
| **F. 任何 step 失敗 / Claude 不返 JSON** | Prompt 結構問題 | 修 prompt + 重跑 spike |

---

## 6. Spike → Cutover 之間的 Gate

Spike 完成後寫 `docs/phase6-multi-agent-spike-results.md` 含：

1. 4 個 spike Q 的實測答案
2. Result category（A-F）
3. 推薦的 cutover 設定（若有調整 §7 推薦）
4. **Go / No-Go 建議**

User review 後決定：
- **Go**：依 `docs/v4-cutover-plan.md` Stage A-F 進行
- **No-Go**：退回純 v4 cutover（保 Phase 5 機械決策）+ 把 Phase 6 design 標 deferred

---

## 7. 不在這個 spike 範圍內的事

- **Batter 線**：design doc §8 已決定 batter 暫不套，spike 也不測 batter
- **Anthropic API 直接呼叫測試**：本 spike 用 `claude -p` subprocess（Option B），如果 spike 結果想試 Option C（API），另跑 follow-up spike
- **完整 prod orchestrator 實作**：spike 用 ad-hoc runner，正式 implementation 在 Stage D
- **Failure injection**：不測「Claude timeout 怎麼處理」這類 edge case，留給 implementation
- **長期成本驗證**：spike 是單日測，月成本是估算；真實月成本要 Stage E parallel 期間累計

---

## 8. Action Items

執行 spike 時：

- [ ] 寫 `daily-advisor/_tools/multi_agent_spike.py`
- [ ] 準備 case context（`docs/phase6-multi-agent-spike-fixtures/nola_meyer_pfaadt_2026_04_22.json`）
- [ ] 跑主 case + 1 隨機 case
- [ ] 寫 `docs/phase6-multi-agent-spike-results.md` 含 §5 result category 判定 + cutover 建議

不在電腦前時不要跑 spike — 需要 user 在場 supervise（避免 token 燒過量 / 無法 Ctrl-C）。
