# 打者評估框架改版計畫

**狀態**：草稿，待使用者審閱
**日期**：2026-04-19
**觸發 session**：2026-04-17 / 2026-04-19

---

## 背景

Session 內討論累積的改動，分三部分：
- **Part A**（✅ 已完成）：Daily Advisor 精簡（砍 H2H 比分 + IP 進度）
- **Part B**（✅ 已完成）：FA Scan prompt 調整（Pass 1 錨點宣告 + Pass 2 觀察/Pass 區塊精簡 + 連續取代警示）
- **Part C**（⏸ 待決定）：打者評估框架全面改版（本計畫主體）

---

## Part A — Daily Advisor 已完成改動

**Commit**：`7a17197 refactor(daily-advisor): drop H2H scoreboard + IP progress sections`

移除：
- `fetch_yahoo_scoreboard` 的 IP 進度 section（週 40 IP 門檻追蹤）
- H2H Scoreboard 14 項比分 section
- Prompt 中「攻守模式」「H2H 預測」決策邏輯
- 孤兒函式 `calc_weekly_ip` + 變數 `games_in_progress`

保留：
- 雙方 SP 排程（Section 4/5）— 作備查資料
- `fetch_yahoo_scoreboard` 呼叫（Section 5 仍需 opponent_key）
- Matchup / Lineup / 投打衝突判斷邏輯
- CLAUDE.md SOP 改為「週四手動查 `yahoo_query.py scoreboard`」

---

## Part B — FA Scan Prompt 已完成改動

**Commit**：`ebdf595 refactor(fa-scan): tighten prompt output rules for signal density`

### Pass 1（錨點挑選）
- 新增「⚠️ 比較錨點清單，非 cut 決策」宣告
- Reason 嚴格限制：只准核心 3 品質指標 + BBE 樣本量
- 禁止：角色脈絡、傷病、速度、守位、打序、2025 prior、陣容需求

### Pass 2（FA 比較）
- **觀察中更新**：只列 4 類狀態變化（⚠️品質惡化 / ✅即將觸發 BBE<10 / ❌%owned 急升 / 🔄角色變化），常態追蹤省略
- **Pass 區塊**：只列特殊說明（接近觸發但 pass / 高 %owned 被過濾 / 之前推薦後翻案），例行 pass 省略
- **連續「取代」警示**：≥2 天未執行自動加警示行（推測原因：FAAB / 陣容異動 / 用戶 override）

---

## Part C — 打者評估框架改版（待決定）

### C.1 Pass 1 Sum Scoring 取代 Tier 制

**動機**：Tier 制（T1-T5）分層過粗，同 Tier 內需二次排序。Sum 分數制連續可比、AI 理解成本更低。

**指標打分表**（每項 3 核心指標）：

| 百分位 | 分數 |
|--------|------|
| >P90 | 10 |
| P80-90 | 9 |
| P70-80 | 8 |
| P60-70 | 7 |
| P50-60 | 6 |
| P40-50 | 5 |
| P25-40 | 3 |
| <P25 | 1 |

**核心 3 指標**（相加，分數範圍 3-30）：
- xwOBA（打擊品質總指標）
- BB%（7×7 雙重計算）
- Barrel%（HR 最佳預測）

**描述性標籤**（不計入分數，供 Pass 2 判斷）：
- **Profile**：全能 / 準全能 / 純打線 / 純 power / 特殊 / 全弱
- **警示**：短板（任一項 <P25）/ 低信心（BBE <40）

**Pass 1 JSON 輸出範例**：
```json
{
  "weakest": [
    {"name": "Ozzie Albies", "score": 9, "profile": "全弱",
     "warnings": ["短板 Barrel% <P25"], "confidence": "高"},
    {"name": "Jazz Chisholm Jr.", "score": 10, "profile": "全弱",
     "warnings": ["短板 xwOBA <P25"], "confidence": "中"},
    {"name": "Ezequiel Tovar", "score": 16, "profile": "特殊",
     "warnings": ["短板 BB% <P25"], "confidence": "中"},
    {"name": "Byron Buxton", "score": 20, "profile": "純 power",
     "warnings": [], "confidence": "中"}
  ]
}
```

### C.2 Pass 2 改動

**勝出量化**：
- 差距 ≥ 10 百分位點 = 明顯勝出
- Sum score 差 ≥ 2 分 作為快速判斷（約對應 10 百分位點）
- 2 項勝出 = 值得行動

**雙年檢核矩陣**（保留現行，明確化）：
- 當季弱 + 2025 弱 → 結構性確認（cut 候選）
- 當季弱 + 2025 >P60 → slump 候選（**不 cut**）
- 當季上修 + 2025 低 → breakout 候選（觀察等樣本）
- 當季 Trad 高 + 當季 Savant 低 → 賣高窗口

**Cut 最終規則**（4 項全通過）：
1. Pass 1 Sum 分數偏低（排前 3）
2. 雙年檢核為「結構性確認」
3. 有可行 FA 替代
4. 角色脈絡：active starter 高 urgency / backup 低 urgency

**PA/Team_G**（FA 分類用，不參與 Sum）：
- ≥3.5 穩定主力 / 2.5-3.5 半主力 / <2.5 backup
- 我方打者全 P80+，此指標無區辨力

**SB**（tiebreak）：Sum 差 ≤1 分時加分輔助，不抵消品質差距

**陣容脈絡分離**：
- fa_scan **不做**守位、單點故障、邊際遞減判斷
- 由 /player-eval、/weekly-review 處理
- CLAUDE.md 需加註說明

### C.3 sit/start 近況修正（新增層）

**動機**：14d rolling 數據揭露 season 看不到的訊號（Buxton 近況↑、Altuve/Langeliers 近況↓、Stanton K% 激升）。

**使用規則**：
- 僅用於 daily_advisor 的 sit/start 決策
- **不用於 add/drop**（避免追 short-term noise）
- 輔助 matchup 判斷，**不取代**

**近況訊號**：
| 訊號 | 條件 | 決策影響 |
|------|------|----------|
| 🔥 近況↑ | 14d xwOBA - season ≥ +0.050 | start 優先 |
| ❄️ 近況↓ | 14d xwOBA - season ≤ -0.040 | sit 優先 |
| ⚠️ K% 激升 | 14d K% - season ≥ +5pp | 傷勢/機制警訊 |
| ⚠️ HH% 下修 | 14d HH% - season ≤ -10pp | 接觸品質退化 |

**決策使用**：
- Matchup 相近 → 近況↑者優先
- ❄️ 近況↓ + unfavorable matchup → sit
- 🔥 近況↑ + unfavorable matchup → 仍可用（matchup 首要）
- 14d BBE <25 時不輸出旗標（樣本太小噪音大）

### C.4 刪除的舊規則

| 規則 | 刪除理由 |
|------|---------|
| 「上季 <80 場查 career stats」 | 資料流無 career stats，實作缺失 |
| 「陣容脈絡」寫在打者評估節 | 移至 /player-eval、/weekly-review，fa_scan 不做 |
| 「最弱 5 人」 → 改 4 人 | 統一 fa_scan 現行 Pass 1 設定 |
| 「2 項勝出」無量化 | 改為 Sum score 差 ≥ 2 分 |

---

## Part D — 數據驗證

### D.1 我隊 11 名打者 Sum 排序（2026 當季）

| # | 球員 | xwOBA | BB% | Barrel% | Sum | Profile | BBE |
|---|------|-------|-----|---------|-----|---------|-----|
| 1 | **Albies** | 5 | 3 | 1 | **9** | 全弱 | 61 高 |
| 2 | **Chisholm** | 1 | 6 | 3 | **10** | 全弱 | 43 中 |
| 3 | **Tovar** | 9 | 1 | 6 | **16** | 特殊 | 48 中 |
| 4 | **Buxton** | 7 | 3 | 10 | **20** | 純 power | 49 中 |
| 5 | **Stanton** | 8 | 6 | 10 | **24** | 準全能偏 power | 41 中 |
| 6 | **Machado** | 10 | 10 | 5 | **25** | 純打線 | 43 中 |
| 6 | **Altuve** | 10 | 10 | 5 | **25** | 純打線 | 52 高 |
| 8 | **J.Walker** | 10 | 6 | 10 | **26** | 準全能偏 power | 48 中 |
| 9 | **Langeliers** | 10 | 8 | 9 | **27** | 全能 | 46 中 |
| 10 | **Grisham** | 10 | 10 | 8 | **28** | 全能 | 42 中 |
| 11 | **Walker** | 10 | 10 | 10 | **30** | 全能 | 56 高 |

**雙年檢核結果**：
- 🔴 結構弱（雙年雙確認）：**Albies** — cut 候選
- 🟡 Slump 候選（雙年救援）：**Chisholm / Buxton** — 不 cut
- ⚠️ 持續觀察：**Tovar**（BB% 雙年 <P25）/ **Stanton**（HH% elbow 退化）/ **J.Walker / Altuve**（breakout 待驗）
- ✅ 菁英主力：**Walker / Grisham / Langeliers / Machado**

### D.2 FA 候選分數

| 球員 | 位置 | Sum | 2025 prior 確認 | BBE | 備註 |
|------|------|-----|----------------|-----|------|
| **Jeffers** | C | 30 | xwOBA/BB% 確認，Barrel% 待驗 | 35 | 三項菁英但 power breakout 未確 |
| **Alvarez** | C | 29 | ✅ 雙年 P70-80 | 37 | 窗口關閉中（44% owned +7/3d）|
| **Carson Kelly** | C | 29 | ✅ 雙年 P70-80 | 37 | Alvarez 備案 |
| **Julien** | 1B/2B | 26 | ✅ 雙年 P70-80 | 28 | COL 主場加成 |
| **Evan Carter** | LF/CF/RF | 25 | xwOBA 確認，BB% breakout 待驗 | 36 | BB% 8.6→17% 跳升 |
| **Austin Martin** | 2B/LF/CF | 25 | ✅ xwOBA/BB% 雙年菁英 | 30 | Barrel% 天花板低 |
| **Canzone** | LF/RF | 23 | ⚠️ BB% 雙年 <P25 結構弱 | 32 | 硬 platoon |
| **Vargas** | 1B/3B | 23 | ✅ 雙年 P70-80 | 45 | 準觸發達成 |
| **Carter Jensen** | C | 21 | xwOBA/Barrel% 待驗 | 32 | 觸發半達成 |
| **Dominic Smith** | 1B | 18 | ⚠️ 2025 全低 breakout 候選 | 37 | BB% <P25 短板 |

### D.3 直接比較結論

**vs Albies (9)**：全部 FA 碾壓升級（差 9-21 分）→ 該 cut
**vs Chisholm (10)**：雖然 14 FA 都分數更高，但 Chisholm 2025 雙年救援（P80-90）→ slump 不 cut
**vs Tovar (16)**：多數 FA 勝，但 SS 守位保護
**vs Buxton (20)**：9 個 FA 勝，但 Buxton 2025 全 >P90 + 14d 近況↑ 回升中 → hold

**當前執行優先**：
1. 🔴 立即：add Alvarez / drop Albies
2. 🟡 備案：Alvarez 被搶 → Carson Kelly (29, 雙年確認)
3. 🟢 低優先：其他候選都是 Alvarez 備案，不建議同時動

### D.4 14d 近況數據（sit/start 驗證）

| 球員 | 14d xwOBA | Season xwOBA | Δ | 訊號 |
|------|-----------|--------------|---|------|
| Chisholm | .206 | .199 | +0.007 | 穩定（slump 延續）|
| Albies | .243 | .276 | -0.033 | 持平偏下 |
| Altuve | .272 | .341 | **-0.069** | ❄️ 近況↓（breakout 回歸） |
| Langeliers | .307 | .367 | **-0.059** | ❄️ 近況↓ |
| Walker | .307 | .348 | -0.041 | ❄️ 近況↓（HH% 大下修） |
| Stanton | .311 | .312 | -0.002 | 品質持平（K% +5.4pp 警訊） |
| Tovar | .316 | .331 | -0.015 | 穩定 |
| Machado | .334 | .338 | -0.004 | 穩定 |
| Grisham | .355 | .351 | +0.005 | 穩定菁英 |
| Buxton | .384 | .315 | **+0.069** | 🔥 近況↑（slump 回升）|
| J.Walker | .486 | .447 | +0.039 | 菁英持續 |

**關鍵洞察**：
- **用戶直覺「Stanton 最差」→ 數據不完全一致**（品質持平，K% 激升是警訊來源）
- 真近況最差三人：Altuve / Langeliers / Walker（都是 breakout 回歸中 → sell-high 窗口）
- Buxton 近況↑ 驗證「不該 cut」的判斷

---

## 實施計畫

### 分段執行

| Step | 內容 | 檔案 | 複雜度 |
|------|------|------|-------|
| 1 | CLAUDE.md 打者評估節重寫 | `CLAUDE.md` | 低（純文件）|
| 2 | Pass 1 prompt 更新（Sum 算法 + Profile + 警示）| `prompt_fa_scan_pass1_batter.txt` | 低 |
| 3 | Pass 2 prompt 更新（雙年矩陣明確化 + 陣容脈絡分離）| `prompt_fa_scan_pass2_batter.txt` | 低 |
| 4 | 驗證 1-2 週 fa_scan 輸出 | —（觀察）| — |
| 5 | 14d Savant 抓取實作 | 新增 `rolling_stats.py` 或擴充 `roster_stats.py` | 中 |
| 6 | daily_advisor Section 1 加近況旗標 | `daily_advisor.py` | 中 |
| 7 | 近況旗標整合 prompt | `prompt_template.txt` / `prompt_template_morning.txt` | 低 |
| 8 | 整體回顧 | —（觀察）| — |

### 建議執行順序

- **第 1 批（文件層）**：Step 1+2+3 → 即時生效，驗證成本低
- **第 2 批（程式層）**：Step 5+6+7 → 視 Step 4 結果決定
- **Step 4/8** 為觀察期，不需動手

---

## 風險與回退

| 風險 | 機率 | 緩解 |
|------|------|------|
| Sum 分數丟失 profile 差異 | 中 | Profile 標籤保留為描述性欄位 |
| 雙年檢核矩陣 AI 執行不穩 | 低 | 現行 fa_scan 已文字化且實戰穩定 |
| 14d Savant 抓取變動 | 低 | Fallback：抓不到時跳過近況訊號 |
| 14d 樣本量太小判斷噪音 | 中 | BBE <25 時不輸出旗標 |
| Step 1-3 prompt 改動後 AI 輸出退化 | 中 | 改動純文字，可 revert commit |

**回退成本**：低 — Prompt / CLAUDE.md 改動可隨時 revert；程式改動獨立模組，關閉旗標即回歸舊行為。

---

## 待決問題 / Open Questions

- [ ] Profile 分類的邊界是否需微調？（例：準全能的 1 分 P40-50 門檻合理嗎？）
- [ ] BBE 信心 gate 放寬到 ≥40（vs 原提議 ≥50）— 這會讓 Tovar 觸發短板 否決，是否可接受？
- [ ] 14d 近況旗標是否要加「連續 N 天」條件，避免單日波動？
- [ ] Sum 分數閾值「差 ≥ 2 分 = 明顯勝出」是否需要按 profile 調整？（同 profile 差 2 分 vs 不同 profile 差 2 分的意義可能不同）
- [ ] 是否要為 Pass 2 加入「Sum 差距量化」的明確文字規則，或讓 AI 自由判斷？

---

## 參考資料

- **CLAUDE.md 現行打者評估節**：約第 129-176 行
- **2025 MLB 百分位表**：CLAUDE.md 約第 230-245 行
- **Session 討論記錄**：2026-04-17 / 2026-04-19（本文件彙整）
- **驗證資料**：
  - 11 名打者 2026/2025 Savant 數據（fa_scan 每日 issue 存檔）
  - 14d Savant 數據（2026-04-04 to 2026-04-17 一次性抓取）
  - FA 候選（waiver-log.md 觀察中記錄）

---

## 相關 commits

- `7a17197` — Part A Daily Advisor 精簡
- `ebdf595` — Part B FA Scan prompt signal density

Part C 尚未提交。
