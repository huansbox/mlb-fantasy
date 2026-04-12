---
name: player-eval
description: "Fantasy Baseball 球員評估 SOP（7x7 H2H One Win 聯賽專用）。用戶已指名特定球員並詢問是否值得撿/換/交易/關注時觸發 - 例如「Kirk 值不值得撿」「Langeliers 和 Kirk 誰好」。不用於主動搜尋 FA 市場（那是 waiver-scan 的職責）。"
---

# 球員評估 SOP（7×7 H2H One Win）

> 評估標準見 `CLAUDE.md`「球員評估框架」（唯一定義）。本 SOP 定義資料蒐集流程和輸出格式。
> 完整陣容見 `daily-advisor/roster_config.json`。

## 鐵則：先查數據，再做判斷

**禁止基於印象、位置刻板印象、或「大概」推測球員數據。**

每位待評估球員必須先完成 Step 1 數據蒐集，取得精確數值後才能進入 Step 2 篩選。

> 教訓：曾假設捕手 AVG .230-.240 而推薦換人，實際該球員 .277/31HR — 差點主動降級菁英 C。

**數據缺失處理**：查不到精確數據時，不得用估算值補位。回報「[欄位] 無法取得」，若缺失的是決策關鍵欄位（AVG/OPS/IP），標記「判斷信心低，建議再查確認」。

## Step 1：數據蒐集（不可跳過）

> 年份：{今年} = currentDate 年份，{去年} = currentDate 年份 - 1。

### Step 1 前置：Drop history 檢查

評估任何球員前，先確認自家是否 drop 過他：

```bash
grep -i "{球員名}" waiver-log.md
```

> 若找到「dropped」或「Pass」紀錄 → 閱讀當時理由，確認情況是否已改變。
> 若當時是用 Savant 框架 drop 的（品質 cut），除非 Savant 數據有結構性改善，否則不重新推薦。
> 教訓：曾推薦 Brady Singer 換 Albies，忽略我們早已用 Savant 框架 drop 過 Singer。

### Step 1.0：Yahoo API 快速查詢（優先）

用 Bash 確認球員的聯賽狀態與守位：

```bash
python daily-advisor/yahoo_query.py player "{球員名}"
```

> 回傳：隊伍、Yahoo 守位資格、持有率、健康狀態（Yahoo + MLB API 雙來源）、本季數據（打者 AVG/OPS/HR/BB，投手 ERA/WHIP/K/IP）。
> 若球員名含 apostrophe（如 O'Hearn），工具會自動處理。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。
> Yahoo API 失敗時 fallback 到 WebSearch 查守位。

> ⚠️ **球員狀態驗證**：確認球員 roster status（Active / IL / Minors）。`yahoo_query.py player` 同時顯示 Yahoo 和 MLB API 狀態。若兩邊不一致，以 MLB API 為準。IL 球員標記「短期不可用」，影響 add 優先序。

> ⚠️ **平行執行注意**：多個 player-eval agent 同時跑時，各 agent 不要自行寫入 waiver-log.md（會衝突）。改為在結論中列出建議的 log 更新內容，由主 session 統一寫入。單獨執行時正常寫入。

**隊上球員比較基準**：跑 `roster_stats.py --season {今年}` 取全隊當季 + 前一年 Savant 數據。
⚠️ **不可只靠 `roster_config.json` 的 prior_stats**（那只有去年數據，無法反映當季 breakout 或衰退）。

### 打者 — 資料蒐集

**Step 1.1：Savant Statcast（必做）**

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> 回傳 2025 + 2026 的 xwOBA / HH% / Barrel% / BBE，不需 Yahoo auth。
> 名字支援模糊匹配（Jesús = Jesus）。

**Step 1.1b：近期新聞（必做，非補充）**

```
WebSearch: "{球員名} {今年} news injury role lineup"
```

> 必須確認：健康狀態、打序角色、上場時間前景（platoon？傷兵回歸後 PA 縮減？）
> 教訓：Hicks 的 platoon 限制 + Morel/Stowers 回歸後 PA 預計縮減、Woodruff 的局數受限 — 都是新聞才能發現的資訊，直接影響結論。

**Step 1.2：WebSearch 補充**

1. `{球員名} {去年} stats batting` → 取得 OPS / HR / SB / BB%
2. `{球員名} position eligibility yahoo fantasy` → Yahoo 守位資格（Step 1.0 未取得時）

**必須取得（不可用「大概」代替）**：xwOBA、Barrel%、BB%、HH%、OPS、HR、上場場次、守位資格、PA/BBE（樣本量）

### 投手 — 資料蒐集

**Step 1.1：Savant Statcast（優先，取代 WebSearch）**

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> 自動偵測投手，回傳 2025 + 2026 的 xERA / xwOBA allowed / HH% allowed / Barrel% allowed / BBE。

**Step 1.1b：近期新聞（必做，非補充）**

```
WebSearch: "{球員名} {今年} news injury rotation role"
```

> 必須確認：健康狀態、輪值順位、IP 限制、角色穩定性
> 教訓：Woodruff「多數先發間隔 5 天以上 + 主要目標是季末健康」= IP 天花板受限，直接影響 IP 產量評估；Detmers「GM 背書回歸先發」= SP 定位確認。

**Step 1.2：WebSearch 補充**

1. `{球員名} {去年} stats ERA WHIP strikeouts innings` → 完整投球數據

**必須取得**：xERA、xwOBA allowed、HH% allowed、ERA、WHIP、K/9、IP（全季 + IP/GS）、球隊名（判斷 W 支援）、BBE（樣本量）

### WebSearch 年份驗證（打者 / 投手通用）

> ⚠️ WebSearch 傷病新聞必須確認日期年份。搜尋引擎常混入歷史舊聞（例：2023 年 IL 紀錄被當成 2026 年）。
> 無法確認年份的資訊標記「待驗證」，不可直接引用作為決策依據。
> 交叉驗證：`yahoo_query.py player` 的狀態欄位 + ESPN player page。

### 高風險觸發點（查到以下情況需額外處理）

**轉隊**：確認球員目前球隊 = 搜尋到的數據球隊。如有出入，重新評估打線位置、球場效應、先發機會。

**小樣本**：
- 打者上季 < 80 場：需額外查 career stats 或多年趨勢，不可只看單季
- 投手上季 < 80 IP：用預期值區間而非單點估計
- 季初前 3 週實際數據：標記「小樣本，僅供傾向參考」

## Step 2：評估框架

> **直接引用 CLAUDE.md「球員評估框架」區段**，不在此複製。

讀取 CLAUDE.md 確認：
- 打者核心 3 指標 + 產量指標 + 輔助指標
- SP 核心 3 指標 + 產量指標 + 輔助指標
- RP 評估方式
- 百分位表（打者/SP/RP 分開）
- 樣本量加權規則
- 7×7 格式規則
- 陣容脈絡檢查項目

**評估流程**：
- 打者：讀 roster_config.json 全隊打者 → 排出最弱 5 人 → FA 只跟這 5 人比
- SP：排出最弱 4 位 SP → FA 只跟最弱的比
- RP：只有 2 人，FA 直接跟目前 RP 比

## Step 2.5：Savant 回歸驗證（條件觸發）

**觸發條件**：Savant 品質與傳統數據出現矛盾（xwOBA 與 AVG/OPS 的百分位差距 > 20 pctile）。

**做法**：拉 MLB API game log 最近 7-10 場，觀察趨勢方向。

```bash
# MLB API game log（本地可跑，不需 Yahoo auth）
python -c "..." # 用 /api/v1/people/{id}/stats?stats=gameLog&season=2026&group=hitting
```

**用途**：驗證回歸是否已啟動 — **不是預測工具，是確認工具**。

| Savant vs Trad | Game log 趨勢 | 判讀 |
|----------------|-------------|------|
| Savant 好 + trad 差（如 Grisham .379 xwOBA / .146 AVG） | 近場升溫中 | 回歸進行中，buy-low 窗口在關 |
| Savant 好 + trad 差 | 持續低迷 | 回歸尚未啟動，有時間觀察 |
| Savant 差 + trad 好（如 Kochanowicz 5.96 xERA / 3.24 ERA） | 近場開始崩 | 回歸進行中，sell-high/不碰 |
| Savant 好 + trad 好**但走低**（如 Hicks 前 5 場 .467 → 後 9 場 .185） | 明顯下滑 | **BABIP 噪音正在退散**，降低 drop 成本 |

> ⚠️ Hot/cold streaks 作為**預測工具**零預測力（CLAUDE.md 規則不變）。此步驟用途是**驗證 Savant 訊號是否已在實際數據中體現**，不是用趨勢預測未來。

## Step 3：比較與輸出

用表格逐項列出實際數值對比：
- 打者欄位：xwOBA / Barrel% / BB% / HH% / OPS / PA/Team_G / HR / RBI / SB（權重低）/ 守位
  - 附 MLB 百分位定位（如 xwOBA .320 = ~P70）
  - 附樣本量（PA / BBE）
- SP 欄位：xERA / xwOBA allowed / HH% allowed / Barrel% allowed / IP/GS / ERA / WHIP / K/9 / |xERA-ERA| / QS 潛力 / W 支援
  - 附 MLB 百分位定位
  - 附樣本量（BBE）
  - |xERA-ERA| 超過百分位 P70+ 時標記運氣方向
- RP 欄位：同 SP + K/9 / IP/Team_G / SV+H（留意但不追）

末行給明確決策結論。**「不動也是策略」** — 如果 FA 球員未明顯優於現有球員，結論應為「不換」。

**Owned% 判讀**（輔助，非決策依據）：
- 高 owned（>80%）+ Savant 差 → 市場溢價中，sell-high / trade 窗口存在
- 高 owned（>80%）+ Savant 好 → 市場認知正確，不太可能 FA 撿到
- 低 owned（<30%）+ Savant 好 → 市場低估，buy-low 機會（Detmers 27% 模式）
- Owned% 反映「其他 GM 怎麼看（傳統數據視角）」，不是品質指標

## Step 4：陣容脈絡檢查

> 引用 CLAUDE.md「陣容脈絡」區段。

1. **守位需求**：填什麼位？升級、backup、還是重複？（注意：UTIL 讓守位限制降低，棒子夠大就能上場）
2. **單點故障**：是否解決零替補位置風險？（從 roster_config.json 的 positions 計算）
3. **邊際遞減**：陣容已有的強項，再加同類型球員效益遞減
4. **BN 限制**：只有 3 格，每格珍貴
5. **FA 優先**：FA 免費 > 交易要送資產。除非目標明顯更強，否則走 FA
6. **週 H2H 貢獻估算**（drop 場景必做）：用 per-game rate × 預期週出賽場數（active ~6G / BN ~1-2G），算出該球員每週對 R/HR/RBI/SB/BB 的邊際貢獻。避免低估 BN 球員（「BN 0 貢獻」是錯的 — Albies 全週先發可貢獻 2R/1HR/3RBI/1.5BB）

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

## 錯誤檢查清單（評估結束前必過）

- [ ] 所有數值都來自搜尋結果，沒有用「大概」替代？查不到的有標記？
- [ ] 有沒有查近況（傷病/角色變化）？球員有沒有轉隊？
- [ ] 指標差距有沒有 ≥ 10 百分位點？不到就不算顯著
- [ ] 投手有沒有查 xERA + IP/GS？|xERA-ERA| 超 P70 要標記運氣
- [ ] 小樣本數據有沒有標記？（< 80 場/IP、季初 < 30 PA）
- [ ] 有沒有回到陣容脈絡判斷邊際效益？不動是否才是最佳策略？
