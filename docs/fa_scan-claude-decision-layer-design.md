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

## 7. Open questions

實作前需要決定：

1. **Multi-agent 怎麼跑**
   - Option A：用 Claude Code Task tool 的 subagent（同 session 內，share context window）
   - Option B：獨立的 `claude -p` subprocess 呼叫（不 share context，乾淨但較慢）
   - Option C：Anthropic API 直接呼叫（控制度最高，需 API key 管理）
   - 建議：先試 B，若太慢再優化

2. **「同意」的定義**
   - 順序完全相同？
   - P1 相同就算？
   - 用「P1-P4 排列的 Kendall tau 相似度 > 0.X」？
   - 建議：先試「P1 相同 + P2 相同就算同意」，實測再校準

3. **Re-evaluate 上限**
   - 避免無限迴圈
   - 建議：上限 3 輪，超過 → 取最後一版 + log warning

4. **Agent 是否要 share 對方的理由**
   - Step 1 完全獨立 → 確保 diversity
   - Step 3 review 時看到主決策 + 各自原本意見？還是只看主決策？
   - 建議：Step 1 獨立，Step 3 看到主決策 + 自己原本意見（不互相 share 理由，保持獨立判斷）

5. **FA Step 2 邊緣案處理**
   - 1 票同意、2 票反對 → 確定 pass
   - 2 票同意、1 票反對 → 進 Step 3
   - 1.5 票同意（agent 給「prob 50%」這種模糊回答）→ 怎麼算？
   - 建議：強制 agent 二分回答，禁止 maybe，從源頭避免

6. **效能 / 成本**
   - 一次 fa_scan SP 線：Step 1 (3 agent) + Step 2 (1 Claude) + Step 3 review (3 agent) × N 輪 + Step 4 FA 篩選 (3 agent) + Step 5 排序 (1 Claude) + Step 6 review × N 輪 + 最終決策 (1 Claude)
   - 估計 8-15 次 Claude 呼叫（vs 現況單次）
   - Daily 跑 → 月成本可控嗎？需試算

7. **Batter 要不要也套用**
   - Batter 候選人多（10 名單），multi-agent 成本更高
   - Batter 決策模式跟 SP 不同（位置鎖定 / UTIL 彈性 / 速度權衡）
   - 建議：先 SP 跑通再決定 batter

---

## 8. 不變的部分

- 整體 fa_scan 入口、Cron 排程、Yahoo snapshot 邏輯、Layer 1/2、watch ownership check、savant CSV download：**不變**
- Python 機械層 Sum / urgency / tag 計算：**不變**（只是不給 decision）
- waiver-log 更新機制（`_WAIVER_LOG_LOCK` + git pull/edit/commit/push）：**不變**
- Telegram + GitHub Issue 推送：**不變**
- Batter 線（Phase 5 機械決策）：**暫不動**
