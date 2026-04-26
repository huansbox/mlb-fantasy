# Phase 6 Multi-Agent Simplified Spike Results（2026-04-26）

> **Spike type**：D2=C 簡化版（spike doc §3.1 step 1 only — 3 agent 平行排序，不測 step 2/3/main decision/review）
> **Status**：Result Category A（最佳）→ cutover 可進行
> **Raw data**：本機 `/tmp/spike_stdout.json` + `/tmp/spike_stderr.log`（單次運行，未保留）
> **Spike runner**：commit `0873e2b`（`daily-advisor/_tools/multi_agent_spike.py` + fixture + prompt）

---

## 1. 量測結果

### 1.1 性能

| 指標 | 值 | 解讀 |
|------|----|----|
| Wall-clock 並行總時間 | 40.29s | 最長 agent 主導；fa_scan 12:30 cron 完全可接受 |
| Per-agent latency max / avg | 40.29 / 27.6s | agent_1 最慢 40s, agent_2 最快 20s — 訂閱 latency 有 2x variance |
| Parallelism speedup | 2.06x | 3 agent 平行 vs 序列（80.8s）— threading 效率合理但非 3x（claude -p subprocess 啟動有 overhead） |
| JSON parse 成功率 | 100% (3/3) | Prompt 嚴格 JSON 約束有效，無 fallback parse 觸發 |
| Subscription rate limit | 未踩 | 3 個並行未觸發 throttle |

### 1.2 共識

| 指標 | 值 |
|------|----|
| P1 consensus | **all agree — Reynaldo López** |
| 完整 ranking pairwise match | 3/3 |
| 一致 ranking | López → Nola → Cantillo → Holmes |
| key_uncertainty 自我標注 | 3 agent 都未標注高度不確定（各自承認「Cantillo vs Holmes」是次優先序爭議） |

### 1.3 Rationale 觀察

3 agent 的數據引用幾乎一字不差，都集中在同樣的關鍵 datapoint：

- **López P1**：Whiff% 10.2 << P25 21.3 / xwOBACON .466 << P25 .386 / BB/9 4.57 / 0 QS in 5 GS
- **Nola P2**：Sum 23 中段 + xwOBACON .424 <P25 + FB velo 91.2 vs 2025 disaster baseline 91.0（速度物理訊號）
- **Cantillo P3**：Sum 27 + BBE 35 <40 gate + swingman + IP/GS 4.50 (<P25 5.21)
- **Holmes P4**：Sum 32 全綠 + Whiff% 31.1 >P90 + ERA 3.42 / WHIP 1.10 比率穩定器

3 agent 對 luck signal 的處理也完全一致：López 的 xera-era -1.11「撿便宜」tag 都被否決（用 xwOBACON .466 反證 luck 不是 BABIP noise）。

---

## 2. 核心 finding 與解讀

### 2.1 完美一致是 mixed signal

**正面**：v4 框架材料夠豐富時，mechanical Sum + tag 結構已能讓 LLM 收斂到一致判斷。下游 production 可預期 P1 一致率高 → re-eval 觸發率低 → 月訂閱 call 量比 design doc §7.6 估計（15-23 calls/day）更接近下限。

**負面**：3 agent 是 same Claude + same prompt → 一致是 LLM prior 重複，不是 diversity 驗證。**真正的 multi-agent value（diversity 抓邊界 case）這個 spike 沒測到**。

對比 2026-04-23 Nola/López/Holmes triview：
- Triview：3 agent 各用「進階 / 傳統 / 印象」**不同 prior** 評估同樣球員 → 2/3 反對 v3 判斷 → 揭露 v3 結構訊號缺失
- 本次 spike：3 agent 同 prior 同 prompt 評估 → 完全一致 → 沒揭露任何結構訊號

### 2.2 這個 case 不是真 borderline

| 比較 | 結果 |
|------|------|
| López Sum 7 vs Nola Sum 23 | 差 **16 分**（v4 滿分 50 的 32%）|
| López Whiff% 10.2 vs P25 21.3 | 差 **11.1 pp**（>P10 territory）|
| López xwOBACON .466 vs P25 .386 | 差 **80 points**（極端）|

López 是「結構性最弱」的明顯候選，不是 trade-off case。multi-agent 在這個 case 沒機會展現分歧。

未來真 borderline case（如 Sum 差 < 5 + 某項 ✅ 某項 ⚠️ 互有勝負）才能驗證 multi-agent 是否能 surface 出有意義的分歧。

### 2.3 Multi-agent 真 value 在 step 3，不在 step 1

簡化 spike 結論「step 1 高一致」實際暗示：
- Step 1（3 agent 平行排序）：mechanical 已收斂，diversity 價值低
- Step 3（review main Claude）：是抓「main Claude 整合 3 agent 後可能誤讀」的關鍵 — 這個價值簡化 spike **沒驗證**

---

## 3. 對 §7 設計的調整建議

| 條目 | 原推薦 | Spike 後建議 | 變更理由 |
|------|--------|-------------|---------|
| §7.1 Multi-agent runtime | claude -p + threading | **不變** | 訂閱涵蓋 + 40s 並行 + 100% JSON parse 已驗證可行 |
| §7.2 「同意」定義 | P1 match + dissent ≥2 才 re-eval | **放寬：P1 match 即收斂** | 簡化 spike 100% P1 一致 → 過嚴的 dissent 條件對非 borderline case 浪費 review call。改 P1 match 即視為同意，少 dissent count check |
| §7.3 Re-eval 上限 | 1 輪 + degrade | **不變** | spike 沒踩到 re-eval；保留 1 輪 + degrade 作為邊界 case 安全網 |
| §7.4 Step 3 visibility | 主決策 + 自己 step 1 原本意見 | **不變** | spike 不測 step 3；當下推薦保留，未來 Stage E parallel 期觀察 |
| §7.5 FA Step 2 邊界 | 三分（值得/不值得/邊界）+ 邊界進 step 3 | **不變** | spike 不測 FA 線；保留 |

---

## 4. 對應 spike doc §5 result category

**Result Category A — 最佳**：
- 月成本 N/A（訂閱涵蓋）
- P1 高一致（3/3）
- 1 輪收斂預期：non-borderline case 0 觸發；borderline case 待 Stage E 驗

→ **Go**：依 `docs/v4-cutover-plan.md` Stage A-F 進行 cutover。Stage A 已完成；下一步 Stage B（fa_compute SP decision 移除 → tag-only output）。

---

## 5. Spike 沒回答的事

簡化 spike 故意只跑 step 1，以下仍是 unknown：

1. **真 borderline case 的 P1 共識率**：本次 case 差距太大；下次 fa_scan 跑出真 borderline（Sum 差 < 5）時應再跑一次 spike
2. **Step 3 review 的價值**：reviewer 是否真能抓 main Claude 整合誤讀？簡化 spike 跳過 main Claude 整合
3. **Re-eval 收斂率**：spike 沒踩 re-eval，無法量化
4. **長期月訂閱 rate limit**：單次 spike 3 calls 沒 stress；daily 跑（15+ calls/day）穩定性需 Stage E parallel 期實測

這些 deferred 到 Stage E 1-2 週 parallel 驗證自然驗

---

## 6. Action items

- [x] **跑 spike** — 完成 2026-04-26
- [x] **寫 results doc** — 本檔
- [ ] **`docs/fa_scan-claude-decision-layer-design.md` §7.2 改寫**：依本 spike finding 把「P1 match + dissent ≥2」放寬為「P1 match 即同意」
- [ ] **動 Stage B**（fa_compute 移除 SP decision → tag-only output）— 下一個動工項目
- [ ] **未來 Stage E parallel 期** 觀察真 borderline case 的 multi-agent 行為，校準 §7.2 / §7.3 / §7.4 設定

---

## 7. 與其他文件的關聯

| 本 doc | 連到 |
|--------|------|
| Spike runner / fixture / prompt | commit `0873e2b`（`daily-advisor/_tools/multi_agent_spike.py` + `_tools/fixtures/spike_2026_04_22_4sp.json` + `_tools/prompts/spike_step1.txt`）|
| Spike 設計 | `docs/phase6-multi-agent-spike.md` §3.1 + §5 result category 表 |
| §7 推薦調整 | `docs/fa_scan-claude-decision-layer-design.md` §7.8 quick-ref（待更新）|
| Cutover 下一步 | `docs/v4-cutover-plan.md` Stage B |
| 對比 triview 結果 | `docs/nola-lopez-holmes-triview-2026-04-23.md`（多 prior 才會分歧）|
