# Batter v4 升級可行性研究

> **Status**：可行性 study（2026-04-25）。non-blocking — 先 SP v4 cutover 跑通再決定是否套 batter。
> **背景**：上次 session「腦中還有什麼」明確問及「v4 沉澱的方法（Impact-Weighted 思維 + 乾淨版 agent 討論 + Rotation gate pre-filter）是否遷移到 batter Sum」。本文不寫 code，只研究遷移性 + 列出 gotcha + 給推薦時程。

---

## 1. 結論先行

| 問題 | 答案 |
|------|------|
| Batter Sum 該升 v4 嗎？ | **暫不升**。SP v4 升級的痛點（contact-quality 三指標相關度過高 + IP/K/QS 缺）batter 不對等存在 |
| 為什麼？ | 現有 3 指標（xwOBA / BB% / Barrel%）相關度比 SP v2 三指標低，Sum 已能反映多維品質；7×7 計分缺 SB 速度欄位 — 這是真正的設計缺口，但用 v4 風格升 5-slot 解不了 |
| 什麼情境下重評？ | (1) SP v4 production 跑通且月成本可控 → batter 套用「決策層」可能比 batter Sum 升 5-slot 更有 ROI；(2) batter 出現 ≥2 次「多視角分歧」事件 |
| Rotation gate pre-filter 的 batter 對應物？ | **是 PA gate**（PA/Team_G）+ **位置 gate**（C only / OF flex / SS scarcity 等）— 但這些已在 manual judgment 處理（CLAUDE.md「fa_scan 不做的事」），是否值得 mechanize 仍 open |

---

## 2. SP v4 升級為何成功（先理解動機）

回顧 `docs/sp-framework-v4-balanced.md` 的核心動機：

### 2.1 問題 1：相關度過高

v2 SP Sum 用 xERA + xwOBA allowed + HH% allowed → 三項相關度 r ~0.7-0.95，真實獨立維度只有 1.3-1.5 個。

### 2.2 問題 2：產量缺失

v2 SP Sum 完全沒抓 K / IP / QS（7×7 三個獨立計分類別）。打 contact 弱但 K 多 + 局數深的 SP 被低估（如 Skubal）。

### 2.3 v4 解法

- 5 slot 強制覆蓋多維（IP/GS / Whiff% / BB/9 / GB% / xwOBACON）
- 把 contact quality 縮成 1 slot（xwOBACON），釋出 4 slot 給其他維度
- Rotation gate 把「資格問題」（pure RP / swingman）抽出 Sum 之外

---

## 3. Batter Sum 對應 audit

對 batter 現況做相同 audit：

### 3.1 現況：xwOBA + BB% + Barrel%

3 個指標的功能拆解：

| 指標 | 主要訊號 | 計分類別覆蓋 |
|------|---------|-------------|
| **xwOBA** | 整體打擊品質（含 K/BB 稀釋）| AVG（弱關聯）+ OPS（強關聯）|
| **BB%** | 上壘能力 | BB（直接）+ OPS 的 OBP 端 |
| **Barrel%** | 強力擊球 | HR（直接）+ RBI（間接）|

### 3.2 相關度 audit

xwOBA、BB%、Barrel% 三者關係：
- xwOBA 是 multi-dim 結果（contact + walks + K 稀釋），不是純 contact quality
- BB% 是 walk-rate，與 xwOBA 部分相關（高 BB% 推高 OBP 推高 xwOBA），但相關係數 r ~0.3-0.4（弱）— Tovar 高 xwOBA 但 BB% 極低 / Soto 中 xwOBA 但 BB% 極高 兩種典型分歧
- Barrel% 與 xwOBA 高相關（r ~0.6），但 Barrel% 是極值事件，xwOBA 是平均 — Aaron Judge / Stanton 類型高 Barrel% 但 K% 高拖累 xwOBA

**真實獨立維度估計**：~2.2-2.5 個（vs SP v2 的 1.3-1.5）— **顯著高於 SP v2**。

### 3.3 計分類別覆蓋 audit

7×7 batter 計分：R / HR / RBI / SB / BB / AVG / OPS

| 類別 | xwOBA 覆蓋 | BB% 覆蓋 | Barrel% 覆蓋 |
|------|-----------|----------|--------------|
| R | 弱（OBP 推 R，xwOBA 含 OBP）| 中（高 BB% → 上壘 → R）| 弱 |
| HR | 中（含在 xwOBA）| 0 | **強** |
| RBI | 弱（隊友狀況依賴）| 0 | 中 |
| SB | **0** | 0 | 0 |
| BB | 中（xwOBA 含）| **強** | 0 |
| AVG | 中（xwOBA proxy）| 弱（負相關 - BB 高的 AB 少）| 中 |
| OPS | **強** | **中**（OBP 端）| **中**（SLG 端）|

**結論**：除了 SB 完全沒覆蓋，3 個指標把其他 6 個類別都至少 partial 覆蓋。

### 3.4 SB 缺口的真實性

CLAUDE.md 策略已明確「軟 Punt SB」：
- 不刻意追速度，靠陣容中有速度的打者偶爾贏
- 同等條件優先高 BB% 打者

**SB 不在 Sum 是 by design**（軟 punt 策略）。這個 ≠ SP v2 缺 IP/K/QS（後者是設計失誤，不是策略選擇）。

---

## 4. 套 v4 風格 5-slot 的可行性分析

假設套 SP v4 風格設計 batter 5 slot：

### 4.1 候選 slot 列表

| 候選 | 為什麼考慮 | 為什麼可能不選 |
|------|-----------|---------------|
| xwOBA | 整體 proxy | 已在；和 BB%/Barrel% 雙計算 |
| BB% | 7×7 BB 類別 + OBP | 已在 |
| Barrel% | 7×7 HR + 強力擊球 | 已在 |
| HH% | contact 強度 | 與 Barrel% r ~0.6 高相關（重複票，SP v4 反例） |
| ISO | power 純度（HR + 2B/3B） | 和 Barrel% r ~0.7 高相關 |
| **K%** | 戰略訊號（avg-killer） | 但 7×7 無 K 類別！對 7×7 hitter 沒直接價值（CLAUDE.md「7×7 格式規則：無 K 類別 → 高 K 打者無懲罰」） |
| **PA/Team_G** | 主力指標 | **已在 urgency Step 2 用作放大器** — 進 Sum 會雙重計算 |
| Sprint Speed | SB 預測 | 軟 punt SB → 進 Sum 違背策略 |
| **OPS** | 計分類別直接 | 與 xwOBA r ~0.85 高相關 |
| **wRC+** | 全方位 + 公園修正 | 已在 `_trade_batter_rank.py` 用，但和 xwOBA r ~0.8 高相關 |
| Pitches/PA | 耐心 | 和 BB% r ~0.6 相關 |
| Contact% | 接觸率 | 和 xwOBA contact 端相關 |
| Pull% / Oppo% | spray | 對 fantasy 7×7 影響邊際（除非 ballpark factor 反向） |

**結論**：能找到 5 個**真正獨立**且**對 7×7 有意義**的 slot 很困難。多數候選都和現有 3 指標高相關，或是策略已 punt 的維度。

### 4.2 假設要硬選 5 slot

最不重複的組合：xwOBA + BB% + Barrel% + ?Sprint Speed? + ?ISO? — 後兩者違背策略 / 高相關。

或：xwOBA + BB% + Barrel% + **K%（拉低）** + **PA/Team_G** — K% 對 7×7 無懲罰價值，PA/TG 與 urgency 雙計。

**沒有像 SP v4 IP/GS + Whiff% + BB/9 + GB% + xwOBACON 那麼乾淨的「5 個獨立軸」可選**。

### 4.3 Impact-Weighted 思維的遷移性

SP v4 的另一啟發：放棄等權打分，給每個 slot 按「對 7×7 產出影響權重」加權。

對 batter 等權的 problem 不大：
- xwOBA / BB% / Barrel% 對 7×7 6 類覆蓋度大致平衡
- 不像 SP 的 IP（影響 IP/W/QS/K 4 個類別）vs Barrel% allowed（只影響 HR 1 個類別）失衡

所以即使升 5 slot，Impact-Weighted 加權的提升空間也有限。

---

## 5. Rotation Gate 對應物：Batter PA / 位置 Gate

### 5.1 SP Rotation gate 解的是什麼

SP rotation gate 把「資格問題」前置處理：
- pure RP 不該進 SP 池（IP/GS 算法錯）
- swingman 該標警告（樣本不穩）

這是 **role-mismatch filter**，避免 Sum 公式被扭曲。

### 5.2 Batter 對應問題

| Batter case | 是否類似 SP rotation gate？ |
|-------------|-----------------------------|
| Platoon 球員（vs L only / vs R only）| 是 — fantasy 折扣明顯但 Sum 不反映（PA 偏低就會被 urgency 抓到，但 Sum 不打折）|
| Position-locked 嚴重短缺（如純 C 季中受傷）| **位置覆蓋問題**，不是球員品質問題，不是 Sum 範圍 |
| 長期傷兵 short-term return | 已用 IL/NA selected_pos 排除 — 已 by-design 處理 |
| Bench / 板凳輪轉 | PA/Team_G 偏低，在 urgency 已抓到 |

**Platoon 是唯一真正 unhandled 的 mismatch**，但它表現為 PA 偏低，已在 urgency 因子捕捉。沒有 SP rotation gate 那麼乾淨需要「pre-filter 不算分」的 case。

### 5.3 位置 Gate 的特殊性

CLAUDE.md「fa_scan 不做的事（手動處理）」：
- 守位判斷
- Active 或 BN 角色脈絡
- 單點故障
- 邊際遞減
- 陣容需求

位置覆蓋（如 SS 唯一坑 / OF 三坑 / UTIL 彈性）是 batter 特有的決策維度，但**這不是 Sum 該解的事** — 是 final decision 層（drop/add 判斷）的脈絡。

---

## 6. 真正的 batter 升級機會（替代 v4 風格）

如果不套 v4 5-slot，batter 還有什麼進步空間？

### 6.1 機會 A：Phase 6 決策層擴展到 batter

不動 Sum + urgency（兩者已 working）→ 把 Phase 5 機械決策（`_decision_from_tags`）改成 multi-agent 決策層。

**好處**：
- 沿用 SP cutover 完成的 multi-agent infrastructure
- 解決位置覆蓋 / Platoon / 戰略需求等 contextual 判斷（這些 LLM 比規則強）
- 不需重寫 Sum / urgency / 百分位表

**前置**：SP Phase 6 跑通 + 月成本實測 < $50（約 1.5× SP 成本，因 batter 候選更多）

### 6.2 機會 B：Sum 加 14d Δ xwOBA 為第 4 因子（非 5-slot 重設計）

現在 batter Sum 是 3 個全季指標。可以**加 1 個時間訊號**：
- 14d Δ xwOBA（已有 rolling fetch）
- 加分規則：14d Δ ≥ +0.030 → +1 / Δ ≤ -0.030 → -1 / 否則 0

這對應 SP v4 的「時序訊號」分層：當下產量 vs 近況變化分開呈現。

但目前 14d Δ 已在 batter urgency Step 2 第 3 因子使用 — 進 Sum 會雙重計算。所以這不是 v4 風格，是「在 urgency 之上的 weight 調整」。

### 6.3 機會 C：強化 Platoon 標籤

現在 Platoon 球員（如部分 C 或 vs-LHP only 球員）的 fantasy 折扣（CLAUDE.md 學習筆記提到 ~70%）只在 manual judgment 時被考慮。

可以加 **platoon flag**：從 MLB API 抓 PA vs L / vs R 分布 → 若一邊 < 20% → flag platoon → Sum 後加標籤但不打折（保持資訊完整給 Claude）。

這是局部改進，不是框架重設計。

---

## 7. 推薦時程

### 7.1 短期（v4 cutover 期間）：不動 batter

理由：
- 雙線改動風險高（attribution 困難）
- 沒有同等密度的「batter 誤判」事件迫使必須動
- SP 升級已驗證需要 multi-agent 解 — batter 的 contextual 維度也適合用同樣方法解，但要在 SP 跑通後再延伸

### 7.2 中期（SP cutover 後 1-2 月）：評估 batter 機會 A

如果 SP Phase 6 月成本 < $50 預算 → 套 batter 決策層（不動 Sum/urgency）。

如果預算超 → 評估「降級用 Haiku 跑 batter step 3 review」的成本控制方案。

### 7.3 長期（≥3 月後）：Sum 局部加強

機會 B（14d Δ 進 Sum）和機會 C（Platoon flag）可作為微調，不需大設計。

### 7.4 永遠不做（明確排除）

- batter Sum 改 5-slot：不解設計問題，反增複雜度
- Sum 加 SB-related 指標：違背軟 punt 策略
- Sum 加 PA/TG：和 urgency 雙計

---

## 8. 重評觸發條件

未來 1-2 月內若出現以下任一，重評本研究結論：

| 事件 | 重評焦點 |
|------|---------|
| Batter cut/drop 出現「多視角分歧」≥2 次（類似 Nola 04-23 三視角）| 是否需要 multi-agent 決策層（機會 A 提早） |
| 連續 3 週 BB 排名後段（< 6th）| BB% 在 Sum 比重是否該拉高（Sum 加權重設） |
| 連續 3 週 SB 全聯盟最後（明確 punt 失敗）| 軟 punt 策略是否該改硬 punt（影響 Sum 設計） |
| MLB 季中規則改變（如打點規則變動，2026 賽季暫無）| 計分類別比重變 → Sum 設計可能要動 |

---

## 9. 不變的部分

- batter Sum 3 指標（xwOBA / BB% / Barrel%）
- batter urgency 4 因子（包含 14d Δ）
- batter 百分位表（CLAUDE.md 章節）
- batter rolling 14d fetch（savant_rolling.py）
- 軟 punt SB 策略
- 「fa_scan 不做的事」清單（位置 / 單點故障等手動處理）

---

## 10. 與 SP v4 / Phase 6 文件的關係

| 本文件 | 關聯文件 |
|--------|---------|
| 結論「暫不升」呼應 | `docs/fa_scan-claude-decision-layer-design.md` §8「Batter 暫不動」、`docs/v4-cutover-plan.md` Stage F「batter 不變」、`docs/phase6-multi-agent-spike.md` §7「Batter 不在 spike 範圍」|
| 機會 A 引用 | Phase 6 design doc multi-agent 機制 |
| 機會 B 14d Δ 已在 urgency | CLAUDE.md「打者評估」§Step 2 第 3 因子 |
| 重評條件「多視角分歧」呼應 | `docs/nola-lopez-holmes-triview-2026-04-23.md` 三視角機制 |
