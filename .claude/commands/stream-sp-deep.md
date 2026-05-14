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

### 1a：MLB Stats API gameLog

```bash
ssh root@107.175.30.172 "cat > /tmp/sp_log.py << 'PYEOF'
import json, urllib.request
MLB_ID = {mlb_id}  # 替換
url = f'https://statsapi.mlb.com/api/v1/people/{MLB_ID}/stats?stats=gameLog&season=2026&group=pitching'
d = json.loads(urllib.request.urlopen(url).read())
splits = d['stats'][0]['splits']

teams = json.loads(urllib.request.urlopen('https://statsapi.mlb.com/api/v1/teams?sportId=1').read())['teams']
abbr = {t['id']: t.get('abbreviation', t['name'][:3]) for t in teams}

print(f'2026 共 {len(splits)} 場')
print()
print(f\"{'Date':<12}{'Opp':<6}{'H/A':<5}{'IP':<6}{'H':<4}{'R':<4}{'ER':<4}{'BB':<4}{'K':<4}{'HR':<4}{'PC':<6}{'ERA':<7}\")
print('-'*65)
for s in splits:
    st = s['stat']
    opp = abbr.get(s['opponent']['id'], s['opponent']['name'][:3])
    ha = 'H' if s.get('isHome') else 'A'
    print(f\"{s['date']:<12}{opp:<6}{ha:<5}{str(st['inningsPitched']):<6}{str(st['hits']):<4}{str(st['runs']):<4}{str(st['earnedRuns']):<4}{str(st['baseOnBalls']):<4}{str(st['strikeOuts']):<4}{str(st['homeRuns']):<4}{str(st.get('numberOfPitches','-')):<6}{str(st.get('era','-')):<7}\")
PYEOF
python3 /tmp/sp_log.py"
```

> **Quoting hint**：MLB Stats API 從 VPS heredoc 寫 Python 比本機 Windows PowerShell 直接 inline 穩。AI 直接 ssh 跑 VPS script。

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

近 3-5 場是否有 ER ≥5 的爆掉？爆掉的是 outlier (前後皆穩) 還是趨勢 (連續 2+ 場)？這影響 floor 風險判斷。

### 1d：近 N 場 ERA / QS rate

**Default N=6**。若 game log 有明顯分界 — 例「開季 2 場 ER ≥5 → 後續 ER ≤3 連續」這種 inflection point，改用「分界後」的 N，**但 N 必須 ≥ 4 才有統計意義**（< 4 樣本太小，仍用 N=6 全季尾段）。

輸出：
- 近 N 場 ERA
- 近 N 場 QS rate
- 近 N 場 IP/GS

> 為什麼明確 N：兩 session 用「自然分界」會切出不同 N，verdict 也跟著漂。先 anchor N=6，再才考慮 override。

## Step 2：對手多窗口趨勢

```bash
ssh root@107.175.30.172 "cat > /tmp/opp_trend.py << 'PYEOF'
import json, urllib.request
from datetime import date, timedelta

OPP_TEAM_ID = {opp_id}  # 替換（CHC=112 / KC=118 / 用 abbr lookup）
END_DATE = '{et_date}'  # 該 ET 日期

def fetch_range(start, end):
    url = f'https://statsapi.mlb.com/api/v1/teams/{OPP_TEAM_ID}/stats?stats=byDateRange&group=hitting&season=2026&startDate={start}&endDate={end}&sportId=1'
    return json.loads(urllib.request.urlopen(url).read())

end = date.fromisoformat(END_DATE)
for days, label in [(7, '7d'), (14, '14d'), (30, '30d')]:
    start = end - timedelta(days=days)
    d = fetch_range(start.isoformat(), end.isoformat())
    s = d['stats'][0]['splits'][0]['stat']
    pa = s['plateAppearances']
    print(f\"{label} ({start} → {end}): G={s['gamesPlayed']:>2} AVG={s['avg']} OBP={s['obp']} OPS={s['ops']} R/G={s['runs']/max(s['gamesPlayed'],1):.2f} K%={s['strikeOuts']/pa*100:.1f}% BB%={s['baseOnBalls']/pa*100:.1f}%\")

# vs same-hand season split. SP 慣用手 → sitCodes: 'vr' (vs RHP) or 'vl' (vs LHP)
SP_THROWS = '{sp_throws}'  # 'R' or 'L'
sit = 'vr' if SP_THROWS == 'R' else 'vl'
url = f'https://statsapi.mlb.com/api/v1/teams/{OPP_TEAM_ID}/stats?stats=statSplits&sitCodes={sit}&group=hitting&season=2026&sportId=1'
d = json.loads(urllib.request.urlopen(url).read())
splits = d['stats'][0]['splits']
if splits:
    s = splits[0]['stat']
    pa = s['plateAppearances']
    print(f\"season vs {SP_THROWS}HP: G={s['gamesPlayed']} PA={pa} AVG={s['avg']} OBP={s['obp']} OPS={s['ops']} K%={s['strikeOuts']/max(pa,1)*100:.1f}% BB%={s['baseOnBalls']/max(pa,1)*100:.1f}%\")
PYEOF
python3 /tmp/opp_trend.py"
```

讀完看：
- **趨勢方向**：7d vs 14d vs 30d 是惡化 / 持平 / 回升？（門檻：±.040 OPS 算明顯方向）
- **K%/BB% 變化**：7d 對比 30d 是否明顯波動？高 BB% 對控球弱的 SP 是警示
- **vs 慣用手 split**：對 SP 是利多 / 中性 / 利空？（比季全 OPS ±.030 算顯著）

## Step 3：交叉比對 pattern + opp

對照 Step 1b 的對手強弱 pattern 和 Step 2 的對手 OPS：

| 對手目前等級 | SP 對該等級 pattern | 期望 |
|---|---|---|
| 7d ≤ .650（極弱）| 對弱打 QS rate 高 | ER 0-2，QS 60-70% |
| 7d .650-.700（弱）| 對弱打 QS rate 高 | ER 1-2，QS 55-65% |
| 7d .700-.760（中）| 對中等 QS rate | ER 2-3，QS 50-55% |
| 7d .760-.820（中強）| 對中強 mixed | ER 2-4，QS 40-50% |
| 7d ≥ .820（強）| 通常爆 | ER 4+，QS 25-35% |

> 這只是 baseline；單一指標（vs RHP split / 對手趨勢方向 / SP 結構 Sum）可調整 ±5-10%。

## Step 4：綜合判斷 + verdict

### 推/不推門檻（baseline）

| Verdict | 條件 |
|---|---|
| ✅ **強推** | 對手 7d ≤ .700 + SP 近 N 場 ERA ≤ 3.50 + 無 floor risk |
| ⚠️ **條件推** | 對手 7d ≤ .740 但有 1-2 個風險（5-slot 結構弱 / 5/8 爆 / vs 慣用手 split 不利）|
| ❌ **不推** | 對手 7d ≥ .770 OR 近 N 場 ERA ≥ 4.50 OR floor 風險高 |

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
> - Pending: {❌ 不推 / ⚠️ 條件推 / ✅ 推}（理由摘要：{pending 表格「一行理由」欄}）
> - **Deep eval: {✅ 強推 / ⚠️ 條件推 / ❌ 不推}**
> - **差異訊號**：{近 N 場 ERA 反轉 / floor risk 重評 / 對手 7d 趨勢 / vs 慣用手 split / 其他 — 一行說明 5-slot Sum 看不到的訊號}
>
> 範例（ground truth）：May pending ❌ 不推（理由：5-slot Sum 20 雙年雙弱）→ deep ⚠️ 條件推（差異訊號：近 6 場 ERA 1.67 + floor risk 低，是 5-slot Sum 反映不到的短期訊號）。

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
- **不寫回 pending file** — 深評是 ad-hoc，不持久化（避免 pending 變第二份 cache）。**但若深評 verdict 與 pending 不同，必須在報告開頭主動標出「Verdict divergence」段**，見 Step 5 報告模板。否則用戶看到 deep 報告但 pending 已 stale 而沒察覺，深評最大價值（短期訊號修正結構面 verdict）等於白做
- **不算具體 FAAB 出價** — 預算策略 ≠ 串流評估
- **不建議 drop 對象** — 由用戶配合當天 fa_scan SP-v4 issue 看 worst SP
- **不算 lineup lock 時序** — 由用戶換算 ET/TW
