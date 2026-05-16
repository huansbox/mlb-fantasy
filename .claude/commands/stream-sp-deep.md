---
name: stream-sp-deep
description: "Fantasy Baseball 串流 SP 候選深評。用戶在 /stream-sp 跑完後指名特定候選想進一步分析時觸發 — 例如「深評 Burke」「Burke 對 CHC 值不值得串」「進一步看 May」「X 串流分析」「X stream eval」。拉 game log → 對手強弱 pattern 分類 → 對手 7d/14d/30d 趨勢 + vs RHP/LHP split → 估 IP/ER/K/QS%/W% → verdict。不用於主動找候選（那是 /stream-sp）或長期 add/cut/trade 決策（那是 /player-eval）。"
---

# 串流 SP 候選深評 SOP

在 `/stream-sp` 跑完後對 borderline 候選（⚠️ 條件推 / ❌ 但接近 / 用戶猶豫）做進一步深評，補上主表沒做的三件事：game log 對手強弱 pattern、對手多窗口趨勢、vs same-hand split。

> **接續上下文**：默認從 `daily-advisor/stream-sp-pending.md` 讀對應 ET 日找 SP；用戶顯式給 opponent + ET date 也可。
> **本 skill 不做**：不重新跑 stream-sp scan（用戶應先跑 `/stream-sp`）/ 不算 FAAB 預算 / 不建議 drop 對象 / 不算翻盤期望。

## Step 0：定位 context

從用戶輸入抽出 SP 名 + （可選）ET 日期。

### 0a：用戶顯式給日期 + 對手

例：「深評 Burke 5/15 vs CHC」「May STL @ KC 5/15」→ 直接用，跳到 Step 1。

### 0b：默認 — 從 pending file 找

1. Read `daily-advisor/stream-sp-pending.md`
2. 對檔內每個 `## ET YYYY-MM-DD` H2 section，掃 `### 已評估` 表格找 SP 名
3. 若找到：取該 row 的 opponent / %own / Sum26/25 / 5-slot 細節作為起手 context
4. 若找不到：
   - 該 SP 名可能在 `owned_by_others` / `owned_by_me` / `已過濾` — 提醒用戶該 SP 不在 FA 候選池
   - 或用戶名字拼錯 → AskUserQuestion 確認

### 0c：取 MLB Player ID

優先序：
1. **/stream-sp scan 上次 stdout JSON**（剛跑過 /stream-sp 時 `candidates[i].mlb_id` 已含）— 從對話 context 取，免 API call
2. **MLB Stats API search** fallback（跨 session 已遺失 scan cache 時）：

```bash
ssh root@107.175.30.172 "curl -s 'https://statsapi.mlb.com/api/v1/people/search?names=Sean%20Burke' | python3 -m json.tool | head -50"
```

> 注：FA 候選**不在** `daily-advisor/roster_config.json`（那只有我隊球員），不必往那找。

## Step 1：拉 game log + 對手強弱 pattern 分類

### 1a：呼叫 `mlb_query.gamelog_with_qs`

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && python3 -c \"import json; from mlb_query import gamelog_with_qs; print(json.dumps(gamelog_with_qs({mlb_id}, 2026), indent=2))\""
```

替換 `{mlb_id}` 為 SP 的 MLB Player ID。Helper 回 JSON list，每場含：

| 欄位 | 說明 |
|---|---|
| `date` / `opp` / `h_a` | 比賽日期 / 對手 abbr / H 或 A |
| `ip` (string) / `ip_decimal` (float) | "5.2" 跟 5.667 兩個都給；報告用 `ip`，QS 邏輯內部用 `ip_decimal` |
| `qs` (bool) | Quality Start = IP ≥ 6 且 ER ≤ 3，已 mechanical 算好 |
| `h` / `r` / `er` / `bb` / `k` / `hr` / `pc` / `era` | 比賽其他 raw 欄位 |

> **不要再自己手算 QS**。helper 已用 `parse_ip("5.2") = 5.667` 邏輯保證 5⅔ IP 不會被誤判為 QS（單元測試覆蓋）。

### 1b：對手強弱 pattern 分類（手動，AI 看 table 整理）

對 game log 每場：
- **對手「強」**：對手季 OPS ≥ .770 (R/G ≥ 4.8) — 高 contact / power 線
- **對手「中」**：對手季 OPS .720-.770 — 中等
- **對手「弱」**：對手季 OPS ≤ .720 — 投手友善

> **參考門檻**：2026 MLB 全聯盟季 OPS 約 .720 (League avg)，±.050 切強/中/弱。
>
> **預設操作：AI 從記憶 take，不必每隊查**。約定俗成的分法（賽季中可能微幅變動，但量級穩）：
> - **強**：LAD / NYY / PHI / ATL / NYM / BOS（contact + power 雙佳）
> - **中-強**：TOR / TB / HOU / MIN / SD / SEA
> - **中**：CHC / STL / SF / DET / AZ / CIN / TEX / MIL
> - **弱**：COL / CWS / MIA / WSH / PIT / KC / LAA / OAK / BAL / CLE
>
> Edge case（一年內格局重洗 / 不確定的隊）才補拉一次 `byDateRange` 全季 OPS 確認。不要對每場都查。

整理後輸出兩個 split：
- 對「中-弱」打線 X/Y QS（含 ER ≤2）
- 對「中-強」打線 X/Y QS

### 1c：辨識 floor risk

近 6-8 場有幾次 ER≥4 的崩盤？是否集中在短局（IP<5）或多支 HR？

- **不要用「連續 vs 非連續」二分**判定 outlier — 非連續但重複的崩盤（例：8 場內 2 次 ER≥4）一樣是 floor risk，不能因為「不相鄰」就當成單一 outlier 抹掉。
- 看的是崩盤的**頻率 + 性質**：1 次孤立、前後皆穩 → floor 風險低；2 次以上，或都伴隨短局 / 多 HR → floor 風險高。

### 1d：近 N 場 ERA / QS rate

**Default N=6**。若 game log 有明顯分界 — 例「開季 2 場 ER ≥5 → 後續 ER ≤3 連續」這種 inflection point，改用「分界後」的 N，**但 N 必須 ≥ 4 才有統計意義**（< 4 樣本太小，仍用 N=6 全季尾段）。

輸出：
- 近 N 場 ERA
- 近 N 場 QS rate
- 近 N 場 IP/GS

> 為什麼明確 N：兩 session 用「自然分界」會切出不同 N，verdict 也跟著漂。先 anchor N=6，再才考慮 override。

## Step 2：對手多窗口趨勢 + vs 慣用手 split

### 2a：呼叫 `mlb_query.opponent_context`

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && python3 -c \"import json; from mlb_query import opponent_context; print(json.dumps(opponent_context({opp_team_id}, '{et_date}', {sp_id}), indent=2))\""
```

替換：
- `{opp_team_id}` — 對手 team ID（BAL=110 / CLE=114 / WSH=120 / CHC=112 / KC=118 ...，不確定先查 `/teams?sportId=1`）
- `{et_date}` — **深評對象比賽的 ET 日期 ISO 字串**（例 `"2026-05-16"`），**不是執行報告當下的日期**。Helper 用此 date 為 anchor 算 7d/14d/30d 窗口；填錯（如 5/15 執行時填 `"2026-05-15"` 評估隔天 5/16 的比賽）會讓窗口往前滑 1 天，造成跟下一輪深評 1 天遊戲結果差異被誤判為 regression。Pending file 的 H2 `## ET YYYY-MM-DD` 就是該值。
- `{sp_id}` — SP MLB Player ID（helper 內部用來查 pitchHand 自動接 vs RHP / vs LHP split，**caller 不用傳慣用手**）

Helper 回 JSON dict，含 4 key：

| Key | 內容 |
|---|---|
| `7d` / `14d` / `30d` | 各窗口 batting stats — `g` / `avg` / `obp` / `ops` / `rg` / `k_pct` / `bb_pct` |
| `vs_hand` | season vs SP 慣用手 split — `pa` / `avg` / `obp` / `ops` / `k_pct` / `bb_pct` / `hand`（"R" or "L"）|

### 2b：讀完看

- **趨勢方向**：7d vs 14d vs 30d OPS 是惡化 / 持平 / 回升？
  - ⚠️ **7d 是 ~6 場的噪音樣本**。讀 7d 必對照 14d/30d：7d 顯著偏離 14d 時，往「即將均值回歸」方向解讀，**不可把 7d 極端值本身當成對手實力**。窗口塌陷 / 熱化越陡（30d→14d→7d 落差越大）→ 越可能反彈 / 回落，不是越弱 / 越強。趨勢判斷以 14d 為主錨，7d 只用來定方向。
  - 量級語感（**非門檻，僅供對齊**）：窗口間 OPS 落差 ~.040 上下開始算「有方向」，越大越要往回歸解讀 — 結合該窗口場數自行判斷。
- **K%/BB% 變化**：7d 對比 30d 是否明顯波動？高 BB% 對控球弱的 SP 是警示
- **vs 慣用手 split**：對 SP 是利多 / 中性 / 利空？偏離季全 OPS 的量級自行判斷（~.030 上下開始有意義，非硬門檻）

## Step 3：交叉比對 pattern + opp

對照 Step 1b 的對手強弱 pattern 和 Step 2 的對手多窗口 OPS。

> **下表 OPS 量級指「回歸判斷後」的對手實力** — 以 14d 為主錨、7d 只校正方向，**不可直接把 7d 極端值套進表**（見 Step 2b）。

| 對手回歸判斷後 OPS | SP 對該等級 pattern | 期望 |
|---|---|---|
| ≤ .650（極弱）| 對弱打 QS rate 高 | ER 0-2，QS 60-70% |
| .650-.700（弱）| 對弱打 QS rate 高 | ER 1-2，QS 55-65% |
| .700-.760（中）| 對中等 QS rate | ER 2-3，QS 50-55% |
| .760-.820（中強）| 對中強 mixed | ER 2-4，QS 40-50% |
| ≥ .820（強）| 通常爆 | ER 4+，QS 25-35% |

> 這只是 baseline；單一指標（vs RHP split / 對手趨勢方向 / SP 結構 Sum）可調整 ±5-10%。

## Step 4：綜合判斷 + verdict

### 推/不推門檻（baseline）

> 對手等級一律指「回歸判斷後」（14d 主錨，7d 校正方向）— 不是 raw 7d。ERA 量級用「約」，是近 N 場產出的粗略 band，非硬切點。

| Verdict | 條件 |
|---|---|
| ✅ **強推** | 對手回歸後屬「弱」級 + SP 近 N 場 ERA 約 ≤ 3.50 + floor 風險低 + 非短局/低三振 fragile 型 |
| ⚠️ **條件推** | 對手「中-弱」級但有 1-2 個風險（5-slot 結構弱 / 近期單場爆掉 / vs 慣用手 split 不利 / 短局型）|
| ❌ **不推** | 對手回歸後屬「強」級 OR 近 N 場 ERA 約 ≥ 4.50 OR floor 風險高 |

> **短局/低三振型的天花板檢查**：5-slot 顯示 <P25 IP/GS（短局）或 <P25 Whiff%（低三振）的 SP，好結果高度依賴 ER 壓制（BB/9 + xwOBACON）→ QS 結構受限、variance 高。評 ✅ 強推前必須檢查：近況樂觀是否蓋過了結構天花板？這類 fragile 型即使近況好，QS 機率也要打折。

> 結構性 Sum 是輔助訊號，不是 first-order。短期 game log 對手 pattern 比 5-slot 重要（5-slot 是「整季品質基線」，game log 是「即時命中率」）。

### 期望輸出

- **IP**: 數值範圍（例 5.2 - 6.1）
- **ER**: 數值範圍（floor 用「最差 X ER」）
- **K**: 數值範圍
- **BB**: 數值範圍
- **QS 機率**: 百分比
- **W 機率**: 百分比（看 SP 球隊近期戰績、對手投手）

## Step 5：輸出報告格式

```markdown
## {SP Name} ({SP team}) vs {Opp} — ET {date} {主/客}場串流深評

> **Verdict divergence**（**只有 deep verdict ≠ pending verdict 才寫此段；相同則整段省略**）：
> - Pending: {verdict}（{若含 `(deep)` 戳記註明「上一輪 deep」；否則就是 scan baseline}；理由摘要：{pending 表格「一行理由」欄}）
> - **Deep eval: {✅ 強推 / ⚠️ 條件推 / ❌ 不推}**
> - **差異訊號**：{近 N 場 ERA 反轉 / floor risk 重評 / 對手 7d 趨勢 / vs 慣用手 split / 其他 — 一行說明 pending 反映不到的訊號}
>
> 範例（ground truth）：May pending ❌ 不推（scan 理由：5-slot Sum 20 雙年雙弱）→ deep ⚠️ 條件推（差異訊號：近 6 場 ERA 1.67 + floor risk 低，是 5-slot Sum 反映不到的短期訊號）。

### 1. {SP Name} 2026 game log

| Date | Opp | H/A | IP | ER | K | BB | HR | PC | QS |
|---|---|---|---|---|---|---|---|---|---|
| (8-10 場) |

**對手強弱 pattern**:
- 對「中-弱」打線：X/Y QS
- 對「中-強」打線：X/Y QS

**近 N 場 ERA / QS / IP**：summary 一行

**Floor risk**：高 / 低（理由一句）

### 2. {Opp} 對手深評（{SP Name} 視角）

| 期間 | G | AVG | OBP | OPS | R/G | K% | BB% |
|---|---|---|---|---|---|---|---|
| 30d / 14d / 7d / 季 vs {R/L}HP |

**關鍵訊號**：3-5 個 bullet (✅/⚠️/中性)

### 3. 串流結論：✅/⚠️/❌

#### 推的理由（N 項）
1. ...

#### 不推/風險理由（N 項）
1. ...

#### 期望
- IP / ER / K / BB / QS% / W%

#### 對 7×7 影響
- 加分類別: ...
- 中性: ...
- 風險: ... (對已輸定類別 = 邊際成本 0，hedge 不要過度放大)

### 4. 與其他 pending 候選比較（**自動產出，不必用戶顯式 ask**）

**觸發條件**：pending file 同 ET 日 `### 已評估` 表格內含**任何**其他 ✅/⚠️ 候選 → 必出比較表。只有當該 ET 日只有當前一位被深評候選時才省略。

| 維度 | {SP A} vs {Opp A} | {SP B} vs {Opp B} | 勝者 |
|---|---|---|---|
| 對手 7d OPS | | | |
| 對手趨勢 (30d→7d) | | | |
| SP 近況 ERA (近 N 場) | | | |
| Floor risk | | | |
| 結構面 Sum26 (v4) | | | |
| 雙年 prior (Sum26/25) | | | |
| QS 機率 | | | |

排序：A > B（理由一句）

> 為什麼半強制：用戶心智模型一定會跨候選比較（ground truth：第一次深評 Burke 沒做比較，第二次深評 May 才補做 → 多一輪 round-trip）。pending 同日有多位候選 = 比較需求隱含存在。

**用戶決策建議**：
- 若 ERA/WHIP 有翻盤空間 → 選 ?
- 若 ERA 已輸定 + 堆 IP/W/K → 雙撿或單撿較弱對手
- FAAB 預算緊 → 只撿 ?
```

## Step 6：不做什麼

- **不重新跑 stream_sp_scan.py** — 已有 pending file 帶 5-slot / Sum / breakdown_pct，本 skill 是補充不是重做
- **寫回 pending file（限定欄位）** — 見 Step 7。深評 verdict 與 pending 不同必須回寫；相同則只寫備註戳記。不改 Sum / 5-slot / 對手 OPS（scan baseline 不動，保留 audit trail）
- **不算具體 FAAB 出價** — 預算策略 ≠ 串流評估
- **不建議 drop 對象** — 由用戶配合當天 fa_scan SP-v4 issue 看 worst SP
- **不算 lineup lock 時序** — 由用戶換算 ET/TW

## Step 7：寫回 pending file

報告產出後執行寫回。deep verdict ≠ pending verdict → 必須回寫；相同則只 append 備註戳記。

### 7a：改 evaluations 表（限定 2 欄）

只 Edit `### 已評估` 表格的兩欄：

- **Verdict** cell: 改為 `{new verdict} (deep)`，例 `✅ 強推 (deep)` / `⚠️ 條件推 (deep)` / `❌ 不推 (deep)`
- **一行理由** cell: 改寫為 deep 訊號為主 — 對手 7d / 近 N 場 ERA / floor risk / pattern 訊號（比 scan 一行多顯示什麼）

**不改**（保留 scan baseline 作 audit）：
- Sum26/25 — 5-slot 結構訊號
- 5-slot 細節 cell — 同上
- 對手 OPS（14d）— scan 當天取值
- SP / 隊 / 對手 / %own — 識別欄位

### 7b：append 備註段

同一輪深評多位候選時統一寫一個區塊：

```
- {YYYY-MM-DD HH:MM} deep eval（{N} 位候選）：
  - **{SP1}**：{舊 verdict} → {新 verdict}。差異訊號 = {對手 7d / 近 N 場 ERA / floor / 其他訊號摘要}
  - **{SP2}**：...
- 排序：**{SP1} {≈|>|>>} {SP2} {≈|>|>>} {SP3}**。{各自適用情境一句，例「A 對 ERA/WHIP 翻盤較好；B 對 QS/IP 累積較穩」}
```

verdict 未變動的候選也列入（標 `❌ 維持` / `⚠️ 維持` / `✅ 維持` + 深評確認的訊號），用戶下次補查能看到「上次深評過 X 也已驗證」。

### 7c：更新 last_recheck_at

該 ET 日 H2 的 `- last_recheck_at: ` 改為當下 TW ISO 時間。深評也算一次 recheck。

### 7d：下次深評同位候選時的 baseline

Pending Verdict 若已含 `(deep)` 戳記 → divergence callout 比對 baseline 是「上一輪 deep verdict」，不是原始 scan verdict。戳記不疊加（仍是 `(deep)`），但 一行理由 + 備註 反映最新訊號。

### 7e：原始 scan verdict 哪裡留 audit？

不留。Verdict 欄被 deep 覆寫後 scan 原 verdict 失去，但 Sum26/25 + 5-slot 細節 cell 保留 — 那是 scan 的結構性 ground truth。若需要回看 scan verdict，從 git log 翻 pending file 歷史版本。
