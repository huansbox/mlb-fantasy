---
name: player-eval
description: "Fantasy Baseball 球員評估 SOP（7x7 H2H One Win 聯賽專用）。用戶已指名特定球員並詢問是否值得撿/換/交易/關注時觸發 - 例如「Kirk 值不值得撿」「Langeliers 和 Kirk 誰好」。不用於主動搜尋 FA 市場（那是 waiver-scan 的職責）。"
---

# 球員評估 SOP（7×7 H2H One Win）

聯賽格式：14 類別合計贏 8+ = 1 週勝
- 打者：R, HR, RBI, SB, BB, AVG, OPS
- 投手：IP, W, K, ERA, WHIP, QS, SV+H
- 策略：Punt SV+H + 軟 Punt SB
- Min IP = 40/週（4 SP 基本穩過，不需刻意串流）

> 完整聯賽設定與陣容見專案 `CLAUDE.md`。開始評估前先讀取 CLAUDE.md 確認當前陣容。

## 鐵則：先查數據，再做判斷

**禁止基於印象、位置刻板印象、或「大概」推測球員數據。**

每位待評估球員必須先完成 Step 1 數據蒐集，取得精確數值後才能進入 Step 2 篩選。

> 教訓：曾假設捕手 AVG .230-.240 而推薦換人，實際該球員 .277/31HR — 差點主動降級菁英 C。

**數據缺失處理**：查不到精確數據時，不得用估算值補位。回報「[欄位] 無法取得」，若缺失的是決策關鍵欄位（AVG/OPS/IP），標記「判斷信心低，建議再查確認」。

## Step 1：數據蒐集（不可跳過）

> 年份：{今年} = currentDate 年份，{去年} = currentDate 年份 - 1。

### Step 1.0：Yahoo API 快速查詢（優先）

用 Bash 確認球員的聯賽狀態與守位：

```bash
python daily-advisor/yahoo_query.py player "{球員名}"
```

> 回傳：隊伍、Yahoo 守位資格、持有率、健康狀態、本季數據（打者 AVG/OPS/HR/BB，投手 ERA/WHIP/K/IP）。
> 若球員名含 apostrophe（如 O'Hearn），工具會自動處理。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。
> Yahoo API 失敗時 fallback 到 WebSearch 查守位。

> ⚠️ **平行執行注意**：多個 player-eval agent 同時跑時，各 agent 不要自行寫入 waiver-log.md（會衝突）。改為在結論中列出建議的 log 更新內容，由主 session 統一寫入。單獨執行時正常寫入。

### 打者 — 資料蒐集

**Step 1.1：Savant Statcast（優先，取代 WebSearch）**

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> 回傳 2025 + 2026 的 xwOBA / HH% / Barrel% / BBE，不需 Yahoo auth。
> 名字支援模糊匹配（Jesús = Jesus）。

**Step 1.2：WebSearch 補充**

1. `{球員名} {去年} stats batting` → 取得 OPS / HR / SB / BB%
2. `{球員名} {今年} projected stats fantasy` → Steamer/ATC 預測
3. `{球員名} {今年} news spring training` → 近況、傷病、WBC、角色
4. `{球員名} position eligibility yahoo fantasy` → Yahoo 守位資格

**必須取得（不可用「大概」代替）**：xwOBA、HH%、Barrel%、OPS、HR、BB%、上場場次、守位資格、PA/BBE（樣本量）

### 投手 — WebSearch 查詢清單

1. `{球員名} {去年} stats ERA WHIP strikeouts innings` → 完整投球數據
2. `{球員名} {今年} projected stats fantasy SP` → 預測 IP / ERA / K
3. `{球員名} {今年} news injury rotation` → 傷病、輪值順位、IP 限制

**必須取得**：ERA、WHIP、K/9、**預測全季 IP**、球隊名（判斷 W 支援）

### 高風險觸發點（查到以下情況需額外處理）

**轉隊**：確認球員目前球隊 = 搜尋到的數據球隊。如有出入，重新評估打線位置、球場效應、先發機會。

**小樣本**：
- 打者上季 < 80 場：需額外查 career stats 或多年趨勢，不可只看單季
- 投手上季 < 80 IP：用預期值區間而非單點估計
- 季初前 3 週實際數據：標記「小樣本，僅供傾向參考」

**數據衝突優先順序**：
- 預設：Steamer/ATC 預測 > 春訓表現（春訓小樣本，投手春訓 ERA 噪音極大）
- 例外：傷病相關（春訓沒上場 → 標記 IL 風險）、角色改變（升降先發）
- 開季後 30+ PA/IP → 實際表現開始有參考價值，但仍需結合預測

## Step 2：7×7 篩選框架

### 打者評估（相對比較法 — 無固定門檻）

**核心 3 指標**：xwOBA、BB%、Hard-Hit%
**輔助指標**：Barrel%（確認 HH% 品質）、OPS（計分類別直接影響）

**評估方法**：
1. 將 FA 的 3 項核心指標逐項比較被取代球員
2. FA 在 3 項中至少 2 項優於被取代者 → 值得行動
3. 差距顯著性：差距在同一百分位區間內（如 P50-P75）視為不顯著；跨一個區間以上才視為有意義優勢
4. 樣本量加權：當季 PA < 50 / BBE < 30 → 以前一年為主要基準，當季僅作傾向參考

**2025 MLB 百分位分布**：

| 百分位 | xwOBA | BB% | Hard-Hit% | Barrel% |
|--------|-------|-----|-----------|---------|
| P25 | .262 | 6.2% | 36% | 5.0% |
| P50 | .298 | 8.2% | 41% | 8.2% |
| P75 | .327 | 10.5% | 46% | 11.4% |
| P90 | .350 | 12.7% | 50% | 14.2% |
（2025 全季數據；2026 分布約 Week 6-8 更新）

**格式特殊規則**：
- BB% 是最高效指標（BB 欄 + OPS 的 OBP 端，雙重計算）
- 無打者 K 類別 → K% 不直接扣分
- Punt SB → 速度價值打折，但非零
- AVG 仍是計分類別 → xwOBA 低的打者通常也拖 AVG，但不單獨用 AVG 作篩選門檻
- 外野分拆 LF/CF/RF → CF 資格在當前陣容溢價最高（Buxton 傷病風險），評估 OF 必須區分具體位置
- 不使用連續場次 hot/cold streaks 作為評估依據（零預測力）
- 不使用 BvP 歷史對戰（樣本太小）

### 投手門檻

**SP**（兩項通過）：預測 IP > 180、ERA < 3.50

**格式特殊規則**：
- **IP 是獨立類別** → 局數怪物（190 IP / ERA 3.80）格式價值 > 精品短局型（100 IP / ERA 3.00）
- QS 需要 6+ IP → IP 受限（傷癒、新秀保護）的投手 QS 打折
- W 受球隊影響 → 強隊 SP 有 W 加成
- Punt SV+H → RP 只看 ERA/WHIP 比率，不追救援

## Step 3：比較與輸出

用表格逐項列出 7×7 類別的實際數值對比：
- 打者欄位：xwOBA / HH% / Barrel% / OPS / BB% / HR / RBI / SB（權重低）/ 守位（LF/CF/RF 分開）
  - 附 MLB 百分位定位（如 xwOBA .320 = ~P70）
  - 附樣本量（PA / BBE）
- 投手欄位：IP（權重高）/ ERA / WHIP / K/9 / QS 潛力 / W 支援 / SV+H（Punt，不追）/ 近況

末行給明確決策結論。**「不動也是策略」** — 如果 FA 球員未明顯優於現有球員，結論應為「不換」。

## Step 4：陣容脈絡檢查

1. **守位需求**：填什麼位？升級、backup、還是重複？（OF 必須區分 LF/CF/RF）
2. **單點故障**：是否解決只有 1 人覆蓋的位置風險？
3. **邊際遞減**：陣容已有的強項（如 power 過剩），再加同類型球員效益遞減
4. **BN 限制**：只有 3 格，每格珍貴
5. **FA 優先**：FA 免費 > 交易要送資產。除非目標明顯更強，否則走 FA

## Step 5：記錄評估結果（FA 相關必做）

評估涉及 FA 球員時，**必須**更新 `waiver-log.md`（專案根目錄），這是流程的一部分，不是可選的。

**評估對象已在 log 中（觀察中或條件 Pass）**：加一行日期紀錄，標記 `[eval]`。
```
- {日期}：[eval] vs {現有球員}，結論：{撿/不換/繼續觀察}，理由：{一句話}
```

**評估對象不在 log（新的 FA 評估）**：依結論新增條目：
- 值得觀察 → 加入「觀察中」，寫觸發條件
- 不值得 → 加入「已結案」，標記 Pass + 一行理由

**陣容內部比較（雙方都非 FA）**：不記錄。

如有變動，同步 CLAUDE.md watchlist（新增/移除觀察對象時）。

## 錯誤檢查清單（評估結束前必過）

- [ ] 所有數值都來自搜尋結果，沒有用「大概」替代？查不到的有標記？
- [ ] 有沒有查近況（春訓/WBC/傷病/角色變化）？球員有沒有轉隊？
- [ ] xwOBA/HH% 差距有沒有跨百分位區間？同區間內的差距不算顯著
- [ ] 投手有沒有確認預測 IP？（IP 受限 → IP + QS 都打折）
- [ ] 小樣本數據有沒有標記？（< 80 場/IP、季初 < 30 PA）
- [ ] 有沒有回到陣容脈絡判斷邊際效益？不動是否才是最佳策略？
