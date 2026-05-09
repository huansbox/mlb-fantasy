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

### Step 1.0a：Age 與老化區檢查（必做）

`roster_config.json` 不存 age — 從 `yahoo_query.py player` 回傳或 WebSearch 補查：

```
WebSearch: "{球員名} age born {球員所屬球隊}"
```

**老化區門檻**（觸發後續深查步驟）：

| 球員類型 | 老化區門檻 | 老化區行為 |
|----------|----------|-----------|
| 打者 | age ≥33 | 觸發 Step 1.3 多年趨勢線 + Step 1.1b 老化軸新聞搜尋 |
| SP | age ≥32 | 觸發 Step 1.3 多年趨勢線 + Step 1.1b velocity / IP 限縮新聞 |
| RP | age ≥34 | 觸發 Step 1.1b 角色變動 / role demote 新聞 |

**不在老化區**：略過 Step 1.3 + 老化軸搜尋（避免 over-search）。

> 為什麼要查 age：fantasy 評估裡 age 是「結構性 vs slump」分流的核心變數 — 25 歲 14d OPS .437 = 等回歸（slump），35 歲 14d OPS .437 = 加速跳水（age-related decline）。同一 14d 數據兩種解讀，差別在 age。
> 教訓：曾因不查 age 把 35 歲 Altuve 14d 崩盤誤讀為短期 slump。

**隊上球員比較基準**：跑 `roster_stats.py --season {今年}` 取全隊當季 + 前一年 Savant 數據。
⚠️ **不可只靠 `roster_config.json` 的 prior_stats**（那只有去年數據，無法反映當季 breakout 或衰退）。

### 打者 — 資料蒐集

**Step 1.1：Savant Statcast（必做）**

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> 回傳 2025 + 2026 **兩行**，不需 Yahoo auth：
> - **第一行（v4 thin core）**：xwOBA / **BB%** / HH% / Barrel% / BBE，含百分位 tag — 一般評估用
> - **第二行（deep signals）**：LA（launch angle）/ EV（exit velocity）/ Whiff% / Chase% / xSLG / xBA，raw 值無百分位 — 老化區 / Savant 訊號異常 / Step 3.5 decisive signal 掃描時用，**跨年比較看結構性變化**（如 Altuve LA 17.7°→5.5° = swing 機制崩）
>
> BB% 從 MLB Stats API 抓（Savant CSV 無此欄位），fetch 失敗顯示 `—`。
> 名字支援模糊匹配（Jesús = Jesus）。

**Step 1.1a：14d Rolling 數據**（urgency 第 3 因子用）

- **隊上球員**：直接讀 `daily-advisor/savant_rolling.json`（每日 TW 12:00 cron 更新）
  ```bash
  python -c "import json; d=json.load(open('daily-advisor/savant_rolling.json'))['players']; print(d.get('{mlb_id}'))"
  ```
- **FA / 觀察中球員**：JSON 沒這人 → 動態抓
  ```bash
  cd daily-advisor && python3 -c "
  from savant_rolling import fetch_savant_rolling
  import json
  print(json.dumps(fetch_savant_rolling([{mlb_id}], '{今天 YYYY-MM-DD}')))
  "
  ```
- BBE <25 → 不輸出旗標，14d 因子算 0

**Step 1.1b：近期新聞（必做，非補充）**

**通用層**（必做）：
```
WebSearch: "{球員名} {今年} news injury role lineup"
```

> 必須確認：健康狀態、打序角色、上場時間前景（platoon？傷兵回歸後 PA 縮減？）

**條件觸發層**（依 Step 1.0a 老化區 + Step 1.1 Savant 訊號決定）：

| 觸發條件 | 搜尋詞模板 | 目的 |
|----------|----------|------|
| 老化區（age ≥33）| `{球員名} struggles velocity fastball decline {今年}` | 抓 age-related decline 訊號（對速球弱、bat speed 衰退）|
| Savant 訊號異常（launch angle / Whiff% 跨年跳動 / xSLG 與 Barrel% 矛盾）| `{球員名} swing mechanic adjustment launch angle {今年}` | 抓 swing 機制變化（受傷？角度調整失敗？）|
| PA-TG 變動 / 打序變動 | `{球員名} batting order demoted promoted {今年}` | 抓角色脈絡變化 |

> 通用層每次都做。條件觸發層只在對應 trigger 滿足時做（避免 over-search）。
> 教訓：Hicks 的 platoon 限制 + Morel/Stowers 回歸後 PA 預計縮減 — 通用層搜尋抓得到。
> 教訓：Altuve 通用搜尋只抓到 lineup change，但「對速球 .242 / SLG .323」這條 aging signal 要靠老化軸 `struggles velocity fastball` 才挖到 — 沒老化軸搜尋會漏掉決定性訊號。

**Step 1.2：WebSearch 補充**

1. `{球員名} {去年} stats batting` → 取得 OPS / HR / SB / BB%
2. `{球員名} position eligibility yahoo fantasy` → Yahoo 守位資格（Step 1.0 未取得時）

**Step 1.3：多年趨勢線（Step 1.0a 老化區觸發才做）**

```
WebSearch: "{球員名} wRC+ OPS+ career year by year"
```

> 拉 3-4 年 wRC+ 或 OPS+，確認是否 monotone decay。
> 區分 slump（短期 noise）vs age-related decline（結構性下行）：
> - 連 3+ 年 wRC+ 單調下降 → decline curve confirmed，drop 證據強化
> - 起伏但無趨勢 → 仍是 slump 候選
> 教訓：Altuve wRC+ 164→154→127→113→2026 崩 = 4 年 decay curve，與「14d slump 等回歸」結論完全相反。

**必須取得（不可用「大概」代替）**：xwOBA、Barrel%、BB%、HH%、OPS、HR、上場場次、守位資格、PA/BBE（樣本量）；老化區另需 age + 多年 wRC+/OPS+

### 投手 — 資料蒐集

#### SP 路徑 → 讀 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md)

> SP 評估完整流程已抽出至獨立 playbook。**評估 SP 時讀 `docs/player-eval-sp.md` 跑 Step 1.1 / 1.1a / 1.1c / 1.2 / 1.3 / 1.4 / 1.5**，回 SKILL.md 跑 Step 2 共用引言、Step 4、Step 5。
> 必查清單：5-slot Savant + **21d xwOBACON Δ**（`window_days=21, player_type='pitcher'`）+ **IP/Team_G** + **3 年 pitch arsenal** + **vs L/R splits** + 通用層新聞。

#### RP 路徑

**Step 1.1：Savant Statcast**

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> RP（GS < 3）走 v2：xERA / xwOBA allowed / HH% allowed / Barrel% allowed / BBE。RP 框架 v4 升級時對齊。

**Step 1.1b：近期新聞**

通用層：`WebSearch: "{球員名} {今年} news injury closer role"` — 確認健康、closer 順位、SV+H 機會。
條件觸發：老化區（age ≥34）查 `role demote bullpen demoted`。

**Step 1.2：WebSearch 補充**

1. `{球員名} {去年} stats ERA WHIP saves holds` → 完整數據

**RP 必須取得**：xERA / xwOBA allowed / HH% allowed / Barrel% allowed / K/9 / IP/Team_G / SV+H / BBE

### WebSearch 年份驗證（打者 / 投手通用）

> ⚠️ WebSearch 傷病新聞必須確認日期年份。搜尋引擎常混入歷史舊聞（例：2023 年 IL 紀錄被當成 2026 年）。
> 無法確認年份的資訊標記「待驗證」，不可直接引用作為決策依據。
> 交叉驗證：`yahoo_query.py player` 的狀態欄位 + ESPN player page。

### 高風險觸發點（查到以下情況需額外處理）

**轉隊**：確認球員目前球隊 = 搜尋到的數據球隊。如有出入，重新評估打線位置、球場效應、先發機會。

**小樣本**：
- 投手上季 < 80 IP：用預期值區間而非單點估計
- 季初前 3 週實際數據：標記「小樣本，僅供傾向參考」
- 打者：用 BBE 信心 gate（<30 低信心 / 30-50 中 / >50 高，CLAUDE.md 規則）；不再查 career stats（資料流無支援）

## Step 2：評估框架

> **直接引用 CLAUDE.md「球員評估框架」區段**，不在此複製。

讀取 CLAUDE.md 確認：
- 打者：Sum 打分表（3 指標 P25-P90 對應分數）+ Step 1/2 兩步分工 + urgency 四因子 + ✅/⚠️ add tags
- SP / RP：核心 3 指標 + 產量 + 輔助
- 百分位表（打者/SP/RP 分開）
- 樣本量加權規則 + 7×7 格式規則

### 與 fa_scan 的分工

| 流程 | 職責 | 對打者的處理 |
|------|------|------------|
| fa_scan（自動）| 批量篩選 + drop 排序 | v4 thin：Sum≥25 排除 → 全候選池（不限 4 人 cap）→ LLM 自由 reasoning + ✅/⚠️ PA-based tags |
| /player-eval（手動）| 單點深入 + 陣容脈絡 | 同上 + 新聞層 / 多年 trend / age 老化區 / decisive signal 掃描 / 守位 / 單點故障 / 邊際遞減 |

→ `/player-eval` **完整套用 fa_scan 的評估規則**（保證一致），再加 fa_scan **不做**的陣容脈絡判斷。

### 打者評估流程（對齊 fa_scan v4 thin）

> 完整規則見 CLAUDE.md「打者評估」（v4 thin — raw + agent 自由 reasoning）。

**Step 2.1 — 機械層 hard filter**：
1. 讀 `roster_config.json` 全隊 batter
2. 排除 cant_cut 名單 + BBE <40 + 2026 Sum ≥25（內部 filter，不暴露給 LLM）
3. 餘者全進候選池（不限 4 人 cap）

**Step 2.2 — LLM 層自由 reasoning**（不機械化排序）：
從 raw + percentile + 14d trad + %owned + prior 自行判斷：
- 結構性弱（雙年雙低）→ drop 候選
- 14d 火燙（OPS ≥.850）但 season Sum 低 → 賣低風險，hold
- K% 短期跳 +5pp 以上 → 傷勢警訊
- BBE 邊緣（剛過 40）→ 信心仍低，hedge
- Savant 好 + Trad 差（BABIP 噪音）→ buy-low
- Trad 好 + Savant 差 → 賣高窗口

**Step 2.3 — 評估目標球員**：
- 若是 FA → 跟池內弱者比 raw signals + Sum 差（≥3 是排序提示，不是 verdict）+ 14d 趨勢
- 若是隊上球員 → 看 raw signals + 雙年檢核 + 14d trend + %owned
- 若是交易標的 → 對方陣容同樣用 5 層判斷（season skill / 14d trad / playing time / market pressure / prior）

### SP 流程 → 讀 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md)

完整 SP 評估流程（機械層篩選 + 4-factor urgency + 角色變化 caveat + 評估路徑分流）已抽出至 SP playbook。

### RP 流程

只有 2 人不排最弱清單，FA 直接跟目前 RP 比品質（xERA / xwOBA / HH% / Barrel%）+ K/9 + SV+H（附加項）。維持 2 RP 的 punt SV+H 前提下，品質小輸但有 SV+H 也值得換。

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

### 打者（對齊 fa_scan v4 thin）

**3.1 — Raw 比較表**（核心 3 指標 + 14d + %owned + prior）

| 球員 | xwOBA | BB% | Barrel% | 2025 prior | 14d trad | %owned | PA/TG | BBE |
|------|-------|-----|---------|-----------|----------|--------|-------|-----|
| FA   | .320 (P75) | 9.0% (P55) | 10.5% (P75) | xwOBA .310 P70 | OPS .920 (HR 3 / BB 6 / K 14%) | 28% (+5/3d) | 3.4 | 38 |
| 我隊 P1 | .250 (P25) | 6.0% (P30) | 4.0% (P15) | xwOBA .240 P15 | OPS .560 (HR 0 / K 28%) | 65% | 4.1 | 61 |

附 Sum 內部差作排序提示（≥3 = 機械 win_gate hint），不是 verdict。

**3.2 — 自由 reasoning 判斷**（不卡 binary matrix）

**優先讀 fa_scan 最新報告**該球員段落：

```bash
gh issue list -R huansbox/mlb-fantasy --label fa-scan --limit 5
gh issue view <N> -R huansbox/mlb-fantasy  # 最新打者報告
```

fa_scan 已對隊上球員 + FA 池跑完 v4 thin reasoning（結構性弱 / slump hold / BABIP 噪音 / 賣高窗口 / 14d 火燙 / K% 跳動 全部覆蓋）— 不重複該層。

**player-eval 在 fa_scan 之上補的層**（這才是 player-eval 獨有價值）：
- **新聞層**（Step 1.1b 通用 + 條件觸發軸）— fa_scan LLM 無 web tool
- **多年 trend line**（Step 1.3，老化區觸發）— fa_scan 只看當季 + 前一年
- **Age + 老化區檢查**（Step 1.0a）— fa_scan 不查 age
- **Decisive signal 掃描**（Step 3.5）— fa_scan 是 single-pass 不迭代

**fa_scan 池外的球員**（trade target 不在 FA、剛升上來不在報告）才需 player-eval 自己跑 reasoning — 規則參考 CLAUDE.md「球員評估框架」。

**3.3 — PA-based gate**（v4 thin 唯一保留 binary tag）

| 標籤 | 條件 | 用途 |
|------|------|------|
| ✅ 球隊主力 | 2026 PA/TG ≥3.5 | 信心提升（樣本能累積）|
| ⚠️ 上場有限（強警示）| 2026 PA/TG <2.5 | 強警示，否決多數升級 |

其他 ✅⚠️ tags（雙年菁英 / 近況確認 / Breakout 待驗 / 近況下滑）已從 v4 thin 移除，交 LLM 從 raw 判斷。

**3.4 — 升級判斷**

不給 binary matrix。LLM 從 reasoning 自由判斷：立即取代 / 取代 / 觀察 / 不換。判斷時需考量：
- 結構性 vs slump 區分
- 14d 是 H2H 短期使用價值（一週決策），不是長期預測
- %owned 窗口（dropping = 市場放棄 / explosive = 窗口正在關）
- 陣容脈絡（守位、單點故障、邊際遞減 — Step 4 處理）

### SP → 讀 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md)

SP 完整 9 欄比較表（含 21d xwOBACON Δ + IP/Team_G + Arsenal + Platoon）+ SP-specific Brand bias 觸發 + SP 5 條 decisive signals（雙條件確認）見 SP playbook。

### RP

- RP 欄位：xERA / xwOBA allowed / HH% allowed / Barrel% allowed / K/9 / IP/Team_G / SV+H（附加項）
- 只有 2 人，FA 直接跟現有 RP 比
- Punt SV+H 前提下品質小輸但有 SV+H 也值得換

### 末行明確決策結論

**「不動也是策略」** — 如果 FA 球員未明顯優於現有球員（無 ✅ 或多個 ⚠️），結論應為「不換」。

**Owned% 判讀**（輔助，非決策依據）：
- 高 owned（>80%）+ Savant 差 → 市場溢價中，sell-high / trade 窗口存在
- 高 owned（>80%）+ Savant 好 → 市場認知正確，不太可能 FA 撿到
- 低 owned（<30%）+ Savant 好 → 市場低估，buy-low 機會（Detmers 27% 模式）
- Owned% 反映「其他 GM 怎麼看（傳統數據視角）」，不是品質指標

**⚠️ Brand bias 警示**（高 owned + 結構崩 = market lag）

> SP 場景觸發條件 + 反向（buy-low）見 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md) 「SP Brand Bias 警示」段。以下為 batter 路徑。

評估隊上球員命中以下任一項時，**必須在結論中明確警示 brand bias，不得讓 owned% 拖延 drop 決定**：

- 高 owned% (>80%) + Savant 結構崩（雙年雙低 / launch angle 暴跌 / 對速球結構弱）
- 高 owned% (>80%) + 多年 wRC+ / OPS+ 連 3+ 年單調下降
- 高 owned% (>80%) + 14d Savant Δ ≤-0.080 連 5+ 天

**判讀**：
- Owned% 是「其他 GM 對 brand 的延遲認知」，不是「球員當前價值」— 市場資訊延遲 1-2 週
- 90+ % owned **不是 hold 理由** — 市場修正後下週 ownership 會跳到 60%，且 FA 池當週的替代品也被搶走
- 經典偏誤語言：「他應該回得來」「下週可能反彈」「換掉他怕後悔」「他畢竟是 X 屆 MVP / 全壘打王」— 都是 brand inertia 不是分析

**反向**：低 owned (<30%) + 結構強 = market 還沒注意到，buy-low 窗口在開（搶在熱點起來前）

> 教訓：曾因 9x% owned Altuve 14d OPS .437 + launch angle 17.7°→5.5° + 4 年 wRC+ 連跌（164→154→127→113）仍猶豫 drop — owned% 是雜訊不是信號，brand bias 是最常見偏誤。

## Step 3.5：決定性訊號掃描（避免初判固化）

> SP 場景走雙條件確認版（5 條），完整見 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md) 「SP Step 3.5 — Decisive Signals」。以下為 batter 路徑（單條件即可觸發）。

Step 3 出初判後，掃描以下 **decisive signals** — 命中任一項要明確升級/降級結論，不得停留在「多選項並列」：

| Decisive signal | 條件 | 應觸發的結論修正 |
|----------------|------|----------------|
| 多年 decay curve | 連 3+ 年 wRC+ 單調下降 | drop 路徑優先序提升；trade 路徑撤回（市場資訊延遲，下週折價）|
| Launch angle 暴跌 | Δ ≥10° 跨年 | swing mechanic 結構性變化，drop 證據壓倒性 |
| 對特定球種結構崩 | 對 fastball SLG <.350 / 對 breaking ball Whiff% >40% | aging 或 mechanic 訊號，不可期待短期回歸 |
| Owned% + Savant 矛盾 | Owned% >80 但 14d Savant Δ ≤-0.080 連 5+ 天 | market lag 確認，drop 不要等市場修正 |
| 新聞 explicit signal | 教練公開談角色降級 / 球員自承 swing 改造失敗 / 醫療長期受限 | 結構性訊號，不是 noise |

**輸出格式**：
- 命中 0 項 → 維持 Step 3 初判
- 命中 1+ 項 → explicit 寫「**初判修正**：原 X 路徑 [撤回/升級]，理由：[命中 signal]」
- 必須收斂到單一推薦行動，避免「初判給多選項但沒收斂」

> 教訓：曾給 A/B/C 三選一含 trade 路徑，深查 launch angle 17.7°→5.5° 後才撤回 trade（B 路徑前提是市場仍認可 brand，但 launch angle 暴跌一旦其他 GM 知道就崩盤）。Step 3.5 確保查到後就立即收斂。

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

> 投手 SP 額外清單見 [`docs/player-eval-sp.md`](../../docs/player-eval-sp.md) 「SP Error Checklist 補充」段（21d Δ / IP/Team_G / 角色變化 / arsenal / platoon / xERA-ERA / 隊內排序 / 雙條件確認）。

- [ ] 所有數值都來自搜尋結果，沒有用「大概」替代？查不到的有標記？
- [ ] 有沒有查近況（傷病/角色變化）？球員有沒有轉隊？
- [ ] 指標差距有沒有 ≥ 10 百分位點？不到就不算顯著
- [ ] 投手有沒有查 5-slot（IP/GS / Whiff% / BB/9 / GB% / xwOBACON）+ xERA？|xERA-ERA| 超 P70（≥0.81）要標記運氣
- [ ] 小樣本數據有沒有標記？（< 80 場/IP、季初 < 30 PA）
- [ ] 有沒有回到陣容脈絡判斷邊際效益？不動是否才是最佳策略？
