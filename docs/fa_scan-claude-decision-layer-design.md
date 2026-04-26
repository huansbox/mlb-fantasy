# fa_scan Claude 決策層設計（Phase 6）

> **Status**：設計討論中（2026-04-25 對齊）。前置：v4 cutover（prior_stats backfill + 21d xwOBACON fetch + production 切換）。建議與 v4 cutover **同一波**完成（反正 prompt 都要改）。
> **取代**：Phase 5「Python 主決策、AI 翻譯」模式（見 `docs/fa_scan-python-compute-design.md`）。
> **不取代**：Phase 5 的 Python 機械層仍有效（Sum / urgency / tag 計算、單元測試覆蓋），只是「decision」職責從 Python 移到 Claude。

---

## 1. 設計動機

### 1.1 Phase 5 現況與其侷限

Phase 5（2026-04-21 上線）把「規則計算」全部 Python 化：
- `compute_sum_score` / `compute_urgency` / `compute_fa_tags` 全機械算
- `_decision_from_tags` 直接給 `"立即取代" / "取代" / "觀察" / "pass"`
- Claude 只負責「翻譯 Python decision + flag 邊界 case」

**侷限**：
- Decision 純靠 tag 組合（≥2 ✅ 無 ⚠️ → 立即取代 / 強警示 → 觀察 / ...），**沒有跨候選綜合判斷**
- 「邊界 case」要靠 Claude 在定性中加註才能修正 — 後門機制，主敘事仍是「Python 已決策」
- 缺少**對齊我方陣容需求**的判斷（例如：FA 是 SP 但我方 SP 已過剩）
- 缺少**跨 FA 排序**的判斷（FA 候選彼此誰更值得 add 沒明確規則）

### 1.2 Phase 6 目標

把 decision 職責**明確還給 Claude**：
- Python 提供「足夠但不過量」的材料 + 訊號（Sum / urgency / tag / sum_diff）
- Claude 看完所有材料 + 額外脈絡（watch 觸發、%owned 動向、傷勢、角色變化）→ 給最終決策
- 決策過程透過 multi-agent review 提高穩定度（避免單次 Claude 呼叫的隨機性）

---

## 2. 角色定位轉變

| 層級 | Phase 5 現況 | Phase 6 目標 |
|---|---|---|
| Python 機械層 | 撈資料 + 算 Sum / urgency / tag + **給 decision** | 撈資料 + 算 Sum / urgency / tag — **不給 decision** |
| Claude 層 | 翻譯 decision + flag 邊界 + 寫 watch 變化 + 組 waiver-log | **多 agent 排序 + 最終決策** + 寫 reason + 組 waiver-log |

實作上的具體 contract 變更見 §5。

---

## 3. 修正版簡化流程

> 我方、FA 大方向已確認，每個步驟的細節（v4 過濾規則 / %owned riser 合併位置 / RP 過濾位置等）之後再對齊。本節只列骨架。

### 3.1 我方
1. 撈資料（Savant + MLB stats + 21d rolling）
2. 挑最弱 4 人（Sum 升冪，**v4 五指標**）
3. 算 urgency 4 因子排序得 P1-P4

### 3.2 FA
1. 撈候選（Yahoo snapshot + %owned riser + watchlist 三源合併、去重、去 watch、`rotation_gate_v4` 排掉純 RP）
2. 品質過濾（v4 規則**待設計**）
3. 收集額外資料（Layer 3 + v4 新指標）
4. 跟 anchor 比較：算 sum_diff + ✅/⚠️ tag — **只給訊號，不給 decision**

### 3.3 Claude 決策層（最後一步，§4 詳述）
看完我方 P1-P4 + FA 候選 + watch 觸發 + %owned 動向 → multi-agent 流程 → 最終決策 + waiver-log 更新。

---

## 4. Claude 決策層細節（核心新設計）

### 4.1 我方 SP drop 順序（4 SP 固定）

```
Step 1 — 平行：3 agent 各自獨立排序
  輸入：我方 4 SP 的完整材料（Sum / urgency 4 因子 / tag / 21d / 角色 / status）
  輸出：每 agent 給一份 P1-P4 順序 + 每位的理由

Step 2 — 收斂：Claude 主決策
  輸入：3 agent 的順序與理由
  輸出：最終 P1-P4 順序 + 整合後的理由

Step 3 — Review：3 agent 投票
  輸入：Claude 主決策的最終順序
  輸出：每 agent 同意 / 不同意 + 不同意的理由

Step 4 — 收斂判定：
  - 2/3+ 同意 → 結案
  - <2/3 同意 → Claude 根據 agent 不同意理由重新評估 → 回 Step 3 review
  - 迴圈直到 2/3+ 同意（需設上限避免無限迴圈，見 §6 open questions）

Step 5 — 抽出 anchor：最終 P1 = FA 比較對象
```

### 4.2 FA 篩選與排序（人數不定）

```
Step 1 — 二分篩選：3 agent 平行
  輸入：FA 候選 + 我方最弱 SP（Step 1 結束的 anchor）
  任務：每位 FA 定性二分為「值得研究取代」/「不值得取代」
  輸出：每 agent 給一份 FA 二分清單 + 每位的理由

Step 2 — 投票：
  - 2/3+ 評不值得取代 → 該 FA 直接 pass
  - 2/3+ 評值得研究取代 → 進入 Step 3
  - 1/3 邊緣案 → 看實作決定（保守起見可進 Step 3，由 Claude 主判斷）

Step 3 — 排序：Claude 主決策
  輸入：通過 Step 2 的 FA 候選 + 完整材料
  輸出：最值得 add 前 3 名（FA1 / FA2 / FA3）+ 每位的理由

Step 4 — Review：3 agent 投票（同 §4.1 Step 3）

Step 5 — 收斂判定：同 §4.1 Step 4
```

### 4.3 最終決策

```
輸入：我方最弱 SP（§4.1 P1）+ FA1 / FA2 / FA3（§4.2）

Claude 對「最弱 SP vs FA1, FA2, FA3」**一一比較**，給出三種結論之一：
  - 直接 drop X / add Y：FA 明顯優於我方 P1 → 立即執行
  - 觀察：FA 接近但未明顯優 → 列具體觸發條件等驗證
  - pass：FA 都不夠好 → 不動

寫定性 reason 解釋為何此決策（不重述規則，解讀脈絡）

組 waiver-log 更新（NEW / UPDATE 行，後面 _update_waiver_log 自動寫入）
```

### 4.4 為什麼用 multi-agent

- **降低單次 Claude 呼叫的隨機性** — 同一份輸入跑三次得不同答案的情況在 LLM 常見
- **強迫更深思考** — Review 機制讓決策不能「機械湊答案」，要能說服 reviewer
- **可解釋性** — 不同意的理由本身是 debug 訊號（agent 看到了主決策沒看到的東西）
- **配適 H2H one-win** — drop/add 決策每週只能 6 次，每次都很貴 → 值得多花 token 換準確度

---

## 5. 上線前 contract 變更

### 5.1 fa_compute.py
- `compute_fa_tags` 輸出**移除 `decision` 欄位** — 只保留 `sum_diff` / `breakdown_diff` / `add_tags` / `warn_tags` / `win_gate_passed` / `anchor_name`
- `_decision_from_tags` 函數**整個移除** — 規則交給 Claude prompt 描述
- `_factor_rolling`（urgency 第 3 因子）暫返回 0（門檻校準前），保留 function 結構待校準完成後復用 — 見 `sp-framework-v4-balanced.md` §「Step 2 — Urgency 排序」決策 1/4
- urgency 第 4 因子（運氣回歸）加 `_LUCK_TAG_BBE_MIN = 40` BBE gate（複用同常數，見決策 2/4）
- urgency 並列時不挑 P1，露出並列名單給 Claude 決策層挑（決策 3/4）
- Slump hold 完全移出排序，獨立列「菁英底，slump 候選」，不參與 P1-P4 編號（決策 4/4）

### 5.2 prompt_fa_scan_pass2_sp.txt
- 從「翻譯 Python decision」改寫為「給最終決策 + 寫 reason」
- 新增 multi-agent 流程的 orchestration（或拆成多個 prompt 檔，依實作決定）
- **必須加段提醒 Claude / agent 看具體數值不只看 Sum 分**（v4 百分位制 known limitation 緩衝；見 `sp-framework-v4-balanced.md` §「Known Limitations」方案 1）— 例如「Sum 差 5 但 IP/GS 實質差 0.15」這類桶邊界鈍器情況要能識別
- **加段絕對量級提示給 21d Δ xwOBACON 判斷**（門檻校準前 Python 不打分，全靠 Claude 看原始數字）：
  - `|Δ| < 0.030` = 小變動，多數是 sample noise，不影響判斷
  - `0.030 ≤ |Δ| < 0.050` = 中等變動，配合其他訊號參考
  - `|Δ| ≥ 0.050` = 明顯變動，方向對就計入 drop/hold 判斷
  - `BBE < 20` = 樣本不足，整個訊號忽略
- urgency 並列 tiebreaker 規則：當 P1 並列時，看完並列球員材料（breakdown / prior / 21d Δ / 運氣 / IP-K-W 累積）後挑出最該 drop 的一個，給理由

### 5.3 _build_pass2_data_v2 機械報告
- 移除「機械決策已算好」字樣
- 改稱「機械訊號：tag / sum_diff / urgency / 各因子」
- urgency 第 3 因子位置改露出**原始 Δ xwOBACON + BBE**（不算分、不給池參照分布）：
  ```
  21d Δ xwOBACON：
    Kelly  Δ +0.038 (BBE 23)
    Nola   Δ -0.005 (BBE 28)
    López  Δ -0.020 (BBE 31)
  ```
- urgency 並列時露出並列名單 + 各自完整材料供 Claude tiebreak

### 5.4 _process_group("sp")
- Layer 5 從單次 `_call_claude` 改為 multi-agent orchestration
- 需新工具函數處理 agent 平行呼叫 + 投票收斂

### 5.5 輸出契約
Claude 必須輸出明確 action（drop X add Y / 觀察 / pass），格式更嚴格便於後續 waiver-log 自動寫入。

### 5.6 測試影響
- `test_fa_compute.py` 中所有 `assert result["decision"] == ...` 要移除
- 新增 multi-agent 流程的整合測試（mock Claude 回應）

---

## 6. 與 v4 cutover 的關係

建議**同一波**完成，避免 prompt 改兩次。順序：

```
A. 資料層先到位
   ├─ v4 prior_stats backfill（roster_config.json 加 whiff_pct / gb_pct / xwobacon）
   └─ 21d xwOBACON fetch（savant_rolling.py 擴充）
   ↓
B. fa_compute v4 函數補齊
   ├─ 已有 v4_add_tags_sp / v4_warn_tags_sp / v4_decision_sp
   └─ 新增「無 decision」版本（tag-only output）
   ↓
C. prompt_fa_scan_pass2_sp.txt 重寫
   ├─ v4 規則描述
   ├─ Claude 決策層定位
   └─ Multi-agent orchestration
   ↓
D. _process_group("sp") 改寫
   ├─ Layer 5 從單呼叫 → multi-agent 流程
   └─ 投票收斂邏輯
   ↓
E. Feature flag 並行驗證 1-2 週
   ├─ 環境變數開關 v4 + 決策層
   └─ VPS cron 同跑 v2 production + v4+決策層 log only
   ↓
F. 切換 + 清 v2 SP code
```

Batter 暫不動（v2 + Phase 5 機械決策保留），未來視效果再決定要不要把決策層也套用到 batter。

---

## 7. Open questions（2026-04-25 詳化）

實作前需要決定。每題給「選項 × tradeoff × 推薦」三段式，方便 cutover 動工時直接落地。

---

### 7.1 Multi-agent 怎麼跑？

| 方案 | 機制 | 延遲 / 並行 | Debug 難度 | 依賴 / 成本 |
|------|------|-------------|------------|-------------|
| **A. Claude Code Task subagent** | 同 session Agent tool 呼叫 | 並行（單 user query 內可同時跑多 agent，runtime 自動排程）| 高（subagent stdout 不直接可見，需主 agent 收結果）| 走 Claude Code session 額度，依用戶 plan 計 |
| **B. `claude -p` subprocess** | 獨立 OS 進程，stdout/stderr 完全乾淨 | **序列**（除非自己用 threading/asyncio 並行）| 低（每個 process log 獨立）| 走 user 的 Claude Code 額度（subprocess 共用 token），需 PATH 有 `claude` |
| **C. Anthropic API（Messages API 直接呼叫）** | `anthropic.Anthropic().messages.create()` | 並行（async/threading 即可）| 中（自己處理 retry / rate limit）| 需 ANTHROPIC_API_KEY，billing 走 API tier 不走 Code 額度 |

**Production fa_scan 環境的 hard constraint**：
- 跑在 VPS cron，**沒有 Claude Code 環境**（Claude Code 是 desktop CLI），所以 **Option A 在 production 不可行** — Phase 5 現況也是 `claude -p` subprocess。
- Option B 已驗證可行（Phase 5 fa_scan 用同樣機制呼叫 Claude）— 但**本質序列**：3 agent 平行跑要自己 spawn 3 個 subprocess + asyncio/threading 收尾。

**推薦**：**Option B + threading 並行 subprocess**（沿用 Phase 5 既有 `claude -p` infra，加 threading wrapper）。理由：
- 不破壞 production cron 模式（VPS 已部署）
- 不引入新 SDK 依賴
- threading 並行 3 agent 在 I/O-bound `claude -p` 上效率夠用（fa_scan_v4.py 已示範 batter+SP threading）
- Option C 留給 future：若 daily 月成本超預算，遷 API tier 享 batch 折扣（Anthropic batch API 50% off）

**Spike 要驗的事**（Wave 1.5）：
- 3 個 `claude -p` 並行 spawn 的 wall-clock latency vs 序列（預期 ~1/3）
- subprocess token 帳是否正確進 Claude Code 額度
- 失敗模式：某個 agent timeout 時主流程怎麼降級

---

### 7.2 「同意」的定義？

| 方案 | 規則 | 嚴格度 | 失敗模式 |
|------|------|--------|----------|
| **A. 完全相同順序** | P1-P4 排列 100% 一致 | 高 | 太嚴格，多數情況進 re-evaluate 迴圈，月成本爆炸 |
| **B. P1 相同就算** | 只看排首誰，P2-P4 不問 | 低 | drop 順序若 P1 並列無法區分時失準（P1 是 anchor，這個錯了所有 FA 比較都歪） |
| **C. P1 + P2 相同**（design doc 原建議）| 排首兩位一致 | 中 | 還算合理；但 P2 相同對 anchor 結果無影響（anchor 永遠是 P1）|
| **D. Kendall tau ≥ 0.67**（4-permutation 中最多 1 對逆序）| 排列相似度 | 中-高 | 數學上嚴謹但對 4-elem permutation 過 fine-grained，且 Claude 不直接給 tau 值 |
| **E. P1 相同 + 反對票 ≥2 才回 re-eval** | P1 一致就放行；只要 ≥2 reviewer 提實質反對才重評 | 中-低 | 偏向結束迴圈，靠主 Claude 整合好就放行 |

**關鍵洞察**：design doc §4.1 Step 5「最終 P1 = FA 比較對象」— **P1 是唯一影響下游的位置**，P2-P4 只是 backup 順序。
- 既然 P1 是 critical decision，「同意」應該以 P1 為核心
- P2-P4 是 nice-to-have（萬一 P1 add/drop 後下週還想動）

**原推薦**：**E（P1 相同 + 反對票 ≥2 才回 re-eval）**。

**2026-04-26 Spike 後修訂為更寬鬆的 B'（P1 match 即收斂）**：

簡化 spike（4 SP fixture，commit `0873e2b`）3 agent 對 P1 完全一致（all 3 → López），完整 ranking 也 3/3 pairwise match。Rationale 內容幾乎一字不差引用同樣數據點，**證明 same-Claude 同 prior 在 v4 框架材料豐富的情況下會強烈收斂**。原推薦 E 的「反對票 ≥2 才 re-eval」對非 borderline case 過於保守，會白白觸發 review 而沒有實質 dissent 訊號。

**修訂推薦**：**B'（P1 match 即視為同意，直接收斂進 step 5 抽 anchor）**。理由：
- non-borderline case（Sum 差 ≥10）3 agent 同 prior 會強烈收斂 → review step 浪費 token
- borderline case 才該觸發 review — 用 Sum 差作為 borderline gate（Sum 差 < 5 才強制 step 3 review）
- 詳見 `docs/phase6-multi-agent-spike-results.md` §3 對 §7.2 的調整建議

**spike 沒回答的事**：真 borderline case（Sum 差 < 5）的 P1 一致率仍不知；待 Stage E parallel 期觀察校準。

---

### 7.3 Re-evaluate 上限？

| 方案 | 上限 | Tradeoff |
|------|------|----------|
| **A. 1 輪**（design doc 原建議）| 1 次 review，不一致直接降級 | 不會無限迴圈，但「一意見 vs 三 reviewer」不平等：1 輪後若分歧仍高，沒機會收斂 |
| **B. 2 輪** | 多給一次機會 | 平均成本翻倍但分歧 case 可收斂 |
| **C. 3 輪**（design doc 草案建議）| 上限 3 輪 | 月成本上漲明顯（最壞 case 3× review 成本）|
| **D. 動態上限**：分歧度低（≥2/3 同意）= 1 輪 / 中（1/3 同意）= 2 輪 / 高（0 同意）= 直接終止 + flag 人工 | 看分歧投資成本 | 邏輯複雜，但 token 投放最 reasonable |

**關鍵洞察**：fa_scan 是**daily** cron，分歧 case 不解決今天可以**明天再跑**（next-day data 進來會自然 break tie）。沒必要當下一定收斂到 100%。
- 失敗時：給最後一版 + flag「分歧未收斂」進 Telegram，人工看一眼即可
- 別把 LLM 當 oracle 求穩定性

**推薦**：**A（1 輪）+ 失敗時降級**：1 輪 review 後若 P1 仍不一致 → 取**主 Claude 最後一版** + 在最終決策 reason 加「⚠️ 分歧未收斂」標記 + Telegram 通知時放最前。下游 add/drop 動作仍走 anchor=P1，但人工 review 訊號更強。

理由：daily cron 容錯空間大；節省成本；失敗訊號 surfacing 比強行收斂有用。

---

### 7.4 Agent 是否 share 對方的理由？

| 方案 | Step 1 | Step 3 review | Diversity 損失 |
|------|--------|---------------|----------------|
| **A. 全程獨立** | 各自獨立 | 只看主決策，不看對方 review 理由 | 最低 |
| **B. Step 3 見主決策 + 自己原本理由**（design doc 建議）| 各自獨立 | 看主決策 + 翻自己 step 1 筆記 | 低 |
| **C. Step 3 全部公開**：見主決策 + 三 agent 原始排序 | 各自獨立 | 看所有 agent 的 step 1 結果 | 中（後手 agent 可能受群體效應影響）|
| **D. Step 3 公開 + 主決策 reasoning**：所有材料 + 主 Claude 整合理由 | 各自獨立 | 最大 context | 高（agent 可能直接 endorse 主 Claude）|

**關鍵洞察**：multi-agent 的 value 是 **diversity**（不同 perspective 的 sanity check）。一旦 agents 開始 anchor 在彼此的判斷上，就退化成「multi-call same Claude」。

**推薦**：**B（Step 3 看主決策 + 自己原本意見）**。理由：
- 「自己原本意見」讓 agent 能有**自我比較**錨點：「我原本選 X 但主決策選 Y，X 真的更好嗎？」
- 不看其他 agent 的理由保持原始 diversity
- 主決策的 reasoning 是 agent 唯一的 cross-reference 來源，足以判斷「主 Claude 是否誤讀某個訊號」

實作細節：每個 agent 在 step 1 就要 emit **structured rationale**（不只 P1-P4 順序，還有「為什麼 P1 是 X」），便於 step 3 review 時自我對照。

---

### 7.5 FA Step 2 邊緣案處理？

design doc §4.2 Step 2 是 FA 候選二分（值得研究 vs 不值得）。

| 方案 | 規則 | 風險 |
|------|------|------|
| **A. 強制二分**（design doc 建議）| Prompt 禁止「maybe / 50%」回答 | Agent 可能仍 hedge — prompt-engineering 戰，不一定可靠 |
| **B. 三分（值得 / 不值得 / 邊界）+ 邊界進 Step 3** | Agent 可標 borderline，全 borderline 進排序 | Step 3 排序負擔變大；但符合 LLM 自然輸出 |
| **C. Score-based**（每個 FA 給 0-100 分）+ 閾值切分 | 量化但難解釋 | LLM scoring 不穩定，閾值校準困難 |
| **D. 投票主決策**：3 agent 二分 → 多數票決 / 1.5 票按主 Claude 決定 | 純規則邏輯 | 1.5 票 case 仍要主 Claude，回到原問題 |

**關鍵洞察**：「邊界 case」本質是有用訊號，不是 bug。強制二分丟掉資訊。

**推薦**：**B（三分 + 邊界進 Step 3）**。理由：
- 與 LLM 輸出習慣一致，prompt 簡單
- 邊界 case 本來就值得多看一眼
- Step 3 排序時若 borderline FA 排到後段，主 Claude 自然會 deprioritize
- 計票規則：「不值得 ≥2 → 直接 pass」「值得 + 邊界合計 ≥2 → 進 Step 3」「3 個都不值得 → pass」「3 個都邊界 → 進 Step 3 但排序時加 ⚠️ borderline tag」

---

### 7.6 效能 / 成本試算（**Wave 1.5 spike 必跑**）

design doc §4 一次 SP 線完整流程：
```
我方 4-SP drop 排序：
  Step 1: 3 agent 平行排序        = 3 calls
  Step 2: 主 Claude 收斂            = 1 call
  Step 3: 3 agent review           = 3 calls
  Step 4: 收斂判定（迴圈 ≤1 輪）   = 0~4 calls（按 7.3 推薦 1 輪）

FA 線：
  Step 1: 3 agent 二分             = 3 calls
  Step 2: （無，純計票）           = 0 calls
  Step 3: 主 Claude 排序            = 1 call
  Step 4: 3 agent review           = 3 calls
  Step 5: 收斂判定                 = 0~4 calls

最終決策：
  最弱 SP vs FA1/FA2/FA3 比較 + reason = 1 call
```

**最少**：3+1+3+0 + 3+1+3+0 + 1 = **15 calls / day**
**最多**（1 輪 re-eval）：3+1+3+4 + 3+1+3+4 + 1 = **23 calls / day**

**月估**（30 天）：450~690 calls / month。

**成本變數**：
- 每 call input tokens：完整材料（4 SP × Sum/urgency/tag + 3-5 FA × 全套指標 + 21d Δ + watch）→ 估 6k-10k tokens
- 每 call output tokens：rationale + structured ranking → 估 1k-2k tokens
- 模型：Sonnet（cost-efficient）= ~$3/M input + $15/M output

**保守估算（每 call 8k in / 1.5k out）**：
- Daily：23 × 8000 × $3 / 1M = $0.55 input + 23 × 1500 × $15 / 1M = $0.52 output → **~$1.07/day**
- Monthly：~$32/month
- Best case（15 calls）：~$0.70/day → **~$21/month**

**和現況比**：Phase 5 單 call ~30k input + 4k output → ~$0.15/day → ~$4.5/month。Phase 6 約 **5-7×** 成本上升。

**Tradeoff 判斷**：
- 月 $20-32 對個人副業專案不算貴，但比現況 4.5× 是有感
- H2H one-win 6 異動 / 週 = 24 次 / 月，每次決策成本 $1-1.5 換更穩判斷 — **價值面合理**
- 若用 Anthropic batch API（50% off）→ 月降到 $10-16

**推薦**：**先用 Sonnet 跑 spike 取得實測數字**（非估算）。如果月 $30+ 不可接受，方案：
1. 改 Haiku（10x 便宜）跑 step 1 / step 3 review（簡單投票任務），主決策用 Sonnet
2. 改用 batch API
3. 簡化流程：去掉 Step 3 review（只主決策一次）

---

### 7.7 Batter 要不要也套用？

| 方案 | 適用範圍 | 額外成本 |
|------|----------|----------|
| **A. 永遠不套**（design doc §8 現況）| 只 SP | $0 |
| **B. 套用全 batter**（10 名單）| 所有 batter 線 | 額外 $20-30/month（同 SP 規模）|
| **C. 套用「最弱 4 位 + FA 比較」**（同 SP 結構）| Batter 線複用 SP 流程 | 同 SP，~$20-30/month |
| **D. 套但簡化**：去掉 multi-agent review，只用主 Claude 1 call 取代 Phase 5 機械決策 | 中度升級 | 微增（每 call 大致同 Phase 5）|

**關鍵差異**（batter vs SP）：
- Batter 候選池大（10 名單 vs 4 SP）+ 位置鎖定（C/SS/CF 等）讓 cut 邏輯複雜（不是 Sum 最低就 drop，要看位置覆蓋）
- Batter punt SB 戰略需要在 prompt 里教 — multi-agent 反而可能放大這個 noise（agent 各自誤判 SB 重要性）
- Batter Phase 5 機械決策**現在運作良好**（Muncy / Albies / Grisham / Detmers 多次 call 都對）— 沒有迫切的 pain point

**推薦**：**A（暫不套，與 design doc §8 一致）+ 觀察 SP cutover 1-2 月 → 視 incident rate 決定**。理由：
- SP cutover 是更有 fiber 的 case（Nola/López/Holmes/Pfaadt 04-22~04-24 一連串近 misjudgment 是 multi-agent 動機）
- Batter 沒有同等密度的近期決策爭議
- 先驗證 SP 投資 ROI 再擴張，避免一次改太多面難 attribution

**未來重評觸發條件**：
- Batter cut 出現像 Nola triview 那樣的「多視角分歧」事件 ≥2 次 → 重新考慮套用
- SP Phase 6 月成本實測 < 預算 50% → 有預算空間擴張

---

### 7.8 整體推薦摘要（cutover 動工時直接抓）

| Q | 決策 |
|---|------|
| 7.1 | **Option B + threading 並行 subprocess** |
| 7.2 | **「P1 match 即收斂」**（2026-04-26 spike 後放寬，原 E → B'）— borderline gate（Sum 差 <5）才強制 step 3 review |
| 7.3 | **上限 1 輪，失敗降級 + flag** |
| 7.4 | **Step 3 看主決策 + 自己原本意見** |
| 7.5 | **三分（值得/不值得/邊界）+ 邊界進 Step 3** |
| 7.6 | **Sonnet 跑 spike 實測，預算 $30/月可接受** |
| 7.7 | **Batter 暫不套，SP 跑 1-2 月再評** |

---

## 8. 不變的部分

- 整體 fa_scan 入口、Cron 排程、Yahoo snapshot 邏輯、Layer 1/2、watch ownership check、savant CSV download：**不變**
- Python 機械層 Sum / urgency / tag 計算：**不變**（只是不給 decision）
- waiver-log 更新機制（`_WAIVER_LOG_LOCK` + git pull/edit/commit/push）：**不變**
- Telegram + GitHub Issue 推送：**不變**
- Batter 線（Phase 5 機械決策）：**暫不動**
