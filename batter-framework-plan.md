# 打者評估框架改版計畫

**狀態**：規則定稿，待實施
**日期**：2026-04-19 初版 / 2026-04-20 Part C 規則定稿
**觸發 session**：2026-04-17 / 2026-04-19 / 2026-04-20

---

## 背景

Session 內討論累積的改動，分三部分：
- **Part A**（✅ 已完成）：Daily Advisor 精簡（砍 H2H 比分 + IP 進度）
- **Part B**（✅ 已完成）：FA Scan prompt 調整（Pass 1 錨點宣告 + Pass 2 觀察/Pass 區塊精簡 + 連續取代警示）
- **Part C**（✅ 規則定稿 2026-04-20，待實施）：打者評估框架全面改版（本計畫主體）

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

## Part C — 打者評估框架改版（規則定稿 2026-04-20）

**設計哲學**：
- 自動化處理主流，特殊案例留給 /player-eval、/weekly-review 手動判斷
- 兩步分工：Step 1 機械化排錨點 / Step 2 量化排 drop 順序
- 不分級門檻，只排序：最弱 4 人內部依 urgency 排出 P1-P4 drop 候選，用來和 FA 比較

---

### C.1 Step 1 — 挑最弱 4 人（fa_scan Pass 1）

**目的**：產出 FA 比較的「錨點」清單，不做任何決策判斷。

**流程**：
1. 對全隊 11 名打者用 2026 當季 3 核心指標打分
2. 按 Sum 升冪排序，取最弱 4 人
3. 輸出 Sum 分數，無 profile 標籤、無其他修飾

**核心 3 指標**（相加，分數範圍 3-30）：
- **xwOBA**（打擊品質總指標）
- **BB%**（7×7 雙重計算）
- **Barrel%**（HR 最佳預測）

**指標打分表**：

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

**警示**（附註用，不計入 Sum）：
- **短板**：任一指標 <P25
- **低信心**：BBE <40

**Pass 1 JSON 輸出範例**：
```json
{
  "weakest": [
    {"name": "Ozzie Albies", "score": 9,
     "breakdown": {"xwOBA": 5, "BB%": 3, "Barrel%": 1},
     "warnings": ["短板 Barrel% <P25"], "confidence": "高"},
    {"name": "Jazz Chisholm Jr.", "score": 10,
     "breakdown": {"xwOBA": 1, "BB%": 6, "Barrel%": 3},
     "warnings": ["短板 xwOBA <P25"], "confidence": "中"},
    {"name": "Ezequiel Tovar", "score": 16,
     "breakdown": {"xwOBA": 9, "BB%": 1, "Barrel%": 6},
     "warnings": ["短板 BB% <P25"], "confidence": "中"},
    {"name": "Byron Buxton", "score": 20,
     "breakdown": {"xwOBA": 7, "BB%": 3, "Barrel%": 10},
     "warnings": [], "confidence": "中"}
  ]
}
```

---

### C.2 Step 2 — 最弱 4 人內部 urgency 排序（fa_scan Pass 2）

**目的**：對最弱 4 人量化「誰最該 drop」，輸出排序（P1 最優先）供 FA 比較。

**Urgency 計算**（四因子加總）：

| 因子 | 條件 | 分數 |
|------|------|------|
| **2026 Sum** | <9 | +5 |
|  | 9-11 | +4 |
|  | 12-14 | +3 |
|  | 15-17 | +2 |
|  | 18-21 | +1 |
| **2025 Sum**（雙年檢核）| **≥24** | **Slump hold**（移出 drop 排序） |
|  | 22-23 | +0（灰色帶，給機會） |
|  | 18-21 | +1 |
|  | <18 | +2 |
| **14d 近況**（BBE ≥25 才啟用）| Δ ≥ +0.050（🔥 強回升） | **-2** |
|  | +0.035 ≤ Δ < +0.050（🔥 弱回升） | **-1** |
|  | -0.035 < Δ < +0.035（持平） | 0 |
|  | -0.050 < Δ ≤ -0.035（❄️ 弱下滑） | +1 |
|  | Δ ≤ -0.050（❄️ 強下滑） | +2 |
| **2026 PA/Team_G** | ≥3.5 | +2 |
|  | 3.0-3.5 | +1 |
|  | 2.5-3.0 | +0 |
|  | <2.5 | +0 |

**Δ = 14d xwOBA - season xwOBA**（絕對差值）

**輸出規則**：
- 4 人按 urgency **降冪**排序（P1 → P4），**不分級**
- P1 = 最該 drop；用於 FA 比較
- **Slump hold 特例**：2025 Sum ≥24 者獨立標註，附註「2025 菁英底，slump 候選」，不參與 urgency 排序

**FA 勝出門檻**（add/drop 決策）：
- Sum 差 ≥ 3 分（整體明顯勝）
- **且**至少 2 項指標正向（每項 ≥ 0），避免 `+5 +1 -3 = +3` 單項爆表誤判
- `+1 +1 +1 = +3`：三項都贏算勝出
- `+2 +2 -1 = +3`：兩項明顯勝，一項小輸算勝出
- `+3 +2 -2 = +3`：兩項大勝，一項大輸算勝出

**PA/Team_G 方向說明**：
- **Drop 觀點**：PA/TG 越高 = 每天拖累 stats 越多 = drop urgency 越高（主力弱是流血傷口）
- **Add 觀點**（後續 Pass 2 FA 比較規則，本文件暫不定）：PA/TG 高 = 球隊重視 = 有實質輸出 = 應偏好
- 兩個方向相反，勿混用

**陣容脈絡分離**（fa_scan 不做）：
- 守位判斷（SS/C 稀缺位保護）
- Active/BN 角色脈絡
- 單點故障、邊際遞減、陣容需求
- → 這些特殊情況手動在 /player-eval 或 /weekly-review 處理

---

### C.3 14d 近況整合說明

**與原 sit/start 新增層差異**：
- 原計畫：14d 旗標僅用於 daily_advisor sit/start，**不用於 add/drop**
- **新規則**：14d 直接整合進 Step 2 urgency 計算，add/drop 也用
- 理由：若 2025 強 + 2026 弱 + 14d 🔥 → 強 slump 回升訊號（買點），add/drop 也該看
- 避免追噪音：14d BBE <25 停用旗標；🔥 最多 -2，❄️ 最多 +2，相對其他因子影響有限

**sit/start 的 K% / HH% 警訊（⚠️）保留用於 daily_advisor**，Step 2 urgency 不納入。

---

### C.4 刪除的舊規則

| 規則 | 刪除理由 |
|------|---------|
| 「上季 <80 場查 career stats」 | 資料流無 career stats，實作缺失 |
| 「陣容脈絡」寫在打者評估節 | 移至 /player-eval、/weekly-review，fa_scan 不做 |
| 「最弱 5 人」 → 改 4 人 | 統一 fa_scan 現行 Pass 1 設定 |
| 「2 項勝出」無量化 | 改為 Sum 差 ≥ 3 + 至少 2 項正向 |
| Profile 標籤（全能/純 power 等） | 13 人小隊用不到，增加 AI 執行成本 |
| Tier 制（T1-T5） | Sum 連續可比，取代分層 |
| urgency 分級門檻（P1/P2/P3） | 改為純排序，決策權留用戶 |

---

## Part D — 數據驗證

### D.1 我隊 11 名打者 Sum 排序（2026 當季）

| # | 球員 | xwOBA | BB% | Barrel% | Sum | BBE |
|---|------|-------|-----|---------|-----|-----|
| 1 | **Albies** | 5 | 3 | 1 | **9** | 61 高 |
| 2 | **Chisholm** | 1 | 6 | 3 | **10** | 43 中 |
| 3 | **Tovar** | 9 | 1 | 6 | **16** | 48 中 |
| 4 | **Buxton** | 7 | 3 | 10 | **20** | 49 中 |
| 5 | **Stanton** | 8 | 6 | 10 | **24** | 41 中 |
| 6 | **Machado** | 10 | 10 | 5 | **25** | 43 中 |
| 6 | **Altuve** | 10 | 10 | 5 | **25** | 52 高 |
| 8 | **J.Walker** | 10 | 6 | 10 | **26** | 48 中 |
| 9 | **Langeliers** | 10 | 8 | 9 | **27** | 46 中 |
| 10 | **Grisham** | 10 | 10 | 8 | **28** | 42 中 |
| 11 | **Walker** | 10 | 10 | 10 | **30** | 56 高 |

**Step 1 最弱 4 人錨點**：Albies(9) / Chisholm(10) / Tovar(16) / Buxton(20)

**雙年檢核結果**（參考）：
- 🔴 結構弱（雙年雙確認）：**Albies** — drop P1 候選
- 🟡 Slump hold（2025 Sum ≥24 救援）：**Chisholm / Buxton** — 不 drop
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

### D.3 Step 2 urgency 排序（套用新規則）

假設 2025 Sum 資料（需查證確認）：
- Albies 2025 Sum ~14（偏弱）
- Chisholm 2025 Sum ~25（P80+ 菁英）
- Tovar 2025 Sum ~18-21（中等）
- Buxton 2025 Sum ~27（P90+ 菁英）

**urgency 計算**：

| 球員 | 2026 Sum | 2025 Sum | 14d Δ | PA/TG | 加分 | urgency | 狀態 |
|------|---------|---------|-------|-------|------|---------|------|
| **Albies** | 9 (+4) | ~14 (+2) | -0.033（持平 0） | 4.12 (+2) | 4+2+0+2 | **+8** | **P1** drop |
| **Tovar** | 16 (+2) | ~18-21 (+1) | -0.015（持平 0） | 2.41 (+0) | 2+1+0+0 | **+3** | **P2** drop |
| **Chisholm** | 10 | **≥24** | +0.007（持平） | 3.28 | — | **Slump hold** | hold |
| **Buxton** | 20 | **≥24** | +0.069（🔥強回升） | 3.35 | — | **Slump hold** | hold（附註回升） |

→ drop 排序：**P1 Albies** → P2 Tovar → Chisholm/Buxton hold

**vs FA 候選（Sum 差 ≥3 + 至少 2 項正向）**：
- **vs Albies (9)**：Alvarez 29 / Kelly 29 / Julien 26 等全部碾壓 → P1 立即升級
- **vs Tovar (16)**：多數 FA 勝，但 Sum 差已進觀察範圍（Vargas 23 差 7 分但守位重疊）
- **Chisholm / Buxton**：Slump hold 不動，等 2026 樣本累積或 14d 轉 🔥

**當前執行優先**：
1. 🔴 立即：add Alvarez / drop Albies（urgency +8 最高）
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
| 1 | CLAUDE.md 打者評估節重寫（Sum 打分表 + Step 1/2 規則）| `CLAUDE.md` | 低（純文件）|
| 2 | Pass 1 prompt 更新（Sum 算法 + 警示，移除 Profile）| `prompt_fa_scan_pass1_batter.txt` | 低 |
| 3 | Pass 2 prompt 更新（urgency 四因子 + drop 排序 + 陣容脈絡分離）| `prompt_fa_scan_pass2_batter.txt` | 低 |
| 4 | 驗證 1-2 週 fa_scan 輸出 | —（觀察）| — |
| 5 | 14d Savant 抓取實作（Step 2 與 daily_advisor 共用）| 新增 `rolling_stats.py` 或擴充 `roster_stats.py` | 中 |
| 6 | fa_scan Step 2 整合 14d 旗標 | `fa_scan.py` + Pass 2 prompt | 中 |
| 7 | daily_advisor Section 1 加 sit/start 近況旗標（🔥/❄️/⚠️ K%/⚠️ HH%）| `daily_advisor.py` + prompt | 中 |
| 8 | 整體回顧 | —（觀察）| — |

### 建議執行順序

- **第 1 批（文件層）**：Step 1+2+3 → 即時生效，驗證成本低。14d 因子先在 prompt 寫規則，資料欄位缺值時 AI 跳過（Fallback）
- **第 2 批（程式層）**：Step 5+6+7 → 視 Step 4 結果決定
- **Step 4/8** 為觀察期，不需動手

### 14d 資料相依注意

Step 2 urgency 的 14d 因子依賴每日 rolling 數據，資料來源：
- 目前：2026-04-04 to 04-17 一次性抓取（驗證用）
- 正式：需實作 Step 5 持續抓取
- 過渡期：fa_scan prompt 允許 14d 欄位缺值 → 該因子算 0，不影響其他因子

---

## 風險與回退

| 風險 | 機率 | 緩解 |
|------|------|------|
| Sum 分數丟失打者 profile 差異 | 低 | 實作先跑驗證期，看排序合理性 |
| Step 2 四因子加總權重失衡 | 中 | 驗證期比對人工排序，微調分段門檻 |
| 14d Savant 抓取變動 | 低 | Fallback：抓不到時 14d 因子算 0 |
| 14d 樣本量太小判斷噪音 | 中 | BBE <25 時停用旗標 |
| Step 1-3 prompt 改動後 AI 輸出退化 | 中 | 改動純文字，可 revert commit |
| 2025 Sum 缺值（新人無上季數據）| 中 | 預設當 +0（灰色帶），並標記低信心 |

**回退成本**：低 — Prompt / CLAUDE.md 改動可隨時 revert；程式改動獨立模組，關閉旗標即回歸舊行為。

---

## 待決問題 / Open Questions（輕量微調，可先用再調）

- [ ] **BBE 信心 gate**：Step 1 警示用 BBE <40 vs <50？預設 40，Tovar 觸發短板可接受
- [ ] **2025 Sum 缺值處理**：新人無 2025 數據 → 預設 +0（灰色帶）；或強制低信心 +1？預設 +0
- [ ] **urgency 階梯線性 vs 非線性**：目前等距，實戰若發現 Sum 9 vs 15 排序太接近再調
- [ ] **14d 連續 N 天條件**：是否加「連續 N 天 ❄️」避免單日波動？暫不加，BBE ≥25 gate 已防護
- [ ] **BB% 的 PA/TG 方向**：BB 是 counting stat，主力累積量反而多，PA/TG 高對 BB 是正面 — Step 2 暫不處理，未來若 BB 結構性補強成效不彰再討論
- [ ] **Add 觀點 PA/TG 方向**：add 候選需 PA/TG 高證明球隊重視（與 drop 觀點相反）— Pass 2 FA 比較規則，本文件未定，之後再討論

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
