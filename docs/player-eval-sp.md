# SP 評估子流程（v4 5-slot + 多訊號交叉）

> 入口：`/player-eval` SOP（SKILL.md）。本檔是投手 **SP 路徑**的完整實作。
> RP 評估留在 SKILL.md（只有 2 人不排序 + 規則簡單，未拆分）。
> 評估標準見 `CLAUDE.md`「SP 評估」（v4 5-slot Sum + Phase 6 multi-agent）。

## 與 SKILL.md 的分工

| Step | 走 SKILL.md（共用）| 走 sp-eval.md（SP 專屬）|
|------|-------------------|------------------------|
| Step 0 drop history | ✅ | — |
| Step 1.0 Yahoo API | ✅ | — |
| Step 1.0a Age 老化區 | ✅（門檻 SP age ≥32）| — |
| Step 1.1 Savant | — | ✅ 5-slot |
| **Step 1.1a 21d Savant rolling** | — | ✅ 必做 |
| **Step 1.1c IP/Team_G** | — | ✅ 必做 |
| Step 1.1b 新聞通用層 | ✅ | — |
| Step 1.1b 條件觸發層（SP 軸）| — | ✅ |
| Step 1.2 WebSearch 補充 | — | ✅ |
| Step 1.3 多年趨勢（老化區）| — | ✅ velocity + arsenal |
| **Step 1.4 Pitch Arsenal 3 年趨勢** | — | ✅ 必做（新升級）|
| **Step 1.5 Platoon vs L/R** | — | ✅ 必做（新升級）|
| Step 2 SP 流程 | — | ✅ |
| Step 2.5 回歸驗證 | ✅（通用骨架）| ✅（SP 例子）|
| Step 3 SP 比較表 | — | ✅ 9 欄完整版 |
| Step 3 末行 + Brand bias | ✅ 通用 | ✅ SP 觸發條件 |
| Step 3.5 Decisive signals | ✅ 表格骨架 | ✅ SP 5 條（雙條件確認）|
| Step 4 陣容脈絡 | ✅ 共用前 5 項 | ✅ 第 6 項 SP 視角 |
| Step 5 waiver-log | ✅ | — |
| Error checklist | ✅ 共用 | ✅ SP 補充 |

## SP 路徑核心原則

1. **5-slot 為骨架，輔助訊號交叉驗證**：IP/GS / Whiff% / BB/9 / GB% / xwOBACON 主軸；xERA-ERA Δ + 21d xwOBACON Δ + arsenal + platoon 補完。
2. **角色變化 caveat**：2025 RP / 2026 SP 等角色轉型場景，prior 不適用「雙年雙低 = 結構崩」邏輯。
3. **雙條件確認**：decisive signals 都需 2 條獨立訊號同向才觸發（避免 batter SOP 單條件機械套用 RP→SP 場景誤判）。

---

## SP Step 1：資料蒐集

### Step 1.1 — Savant Statcast（必做）

```bash
python daily-advisor/yahoo_query.py savant "{球員名}"
```

> 投手自動分流：
> - **GS ≥ 3 → SP v4 5-slot**：IP/GS / Whiff% / BB/9 / GB% / xwOBACON + xERA-ERA Δ + GS/IP/BBE context
> - **GS < 3 → RP v2**：見 SKILL.md「RP 流程」段
> 2025 prior：custom + arsenal + MLB API 對歷史年份有效，但 **Savant batted-ball endpoint 對歷史年份失效** → 過去年份的 GB% / BBE 顯示 `—`（誠實標註，非 fetch 失敗）。

### Step 1.1a — 21d Savant Rolling（必做，新升級）

> 對應 fa_compute urgency factor #3（季線 vs 21d Δ 趨勢）。

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && python3 -c '
from savant_rolling import fetch_savant_rolling
import json
print(json.dumps(fetch_savant_rolling([{mlb_id}], \"{今天 YYYY-MM-DD}\", window_days=21, player_type=\"pitcher\"), indent=2))
'"
```

⚠️ **必加 `window_days=21, player_type=\"pitcher\"`** — 預設值是 14d batter，會對 SP 回空 dict（這次評估踩過坑）。

**讀法**：
- 21d xwOBACON 對比季線 xwOBACON
- |Δ| < 0.030 → 中性，urgency factor #3 = 0
- |Δ| ≥ 0.030 → 顯著（fa_compute 門檻），± 1
- |Δ| ≥ 0.080 + BBE ≥ 30 連 7+ 天 → decisive signal（drop 觸發，見 Step 3.5）
- BBE 通常 50-80（21d 4 場左右）= 高信心

### Step 1.1c — IP/Team_G（必做，新升級）

> 對應 fa_compute urgency factor #4（active 輪值放大）。

最簡：球員 GS / 球隊 G played。球隊 G played 從 MLB Stats API 取：

```bash
# Team ID 對照表常用：LAA=108 NYY=147 LAD=119 BOS=111 SF=137 SEA=136
# 完整查 https://statsapi.mlb.com/api/v1/teams?sportId=1
ssh root@107.175.30.172 "python3 -c '
import requests
r = requests.get(\"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=season&season=2026&group=pitching\").json()
print(r[\"stats\"][0][\"splits\"][0][\"stat\"][\"gamesPlayed\"])
'"
```

**讀法**（雙視角，方向相反）：
- IP/Team_G ≥ 1.0 → **drop 視角**：urgency +2（active 輪值，每場拖比率）；**anchor/add 視角**：信心高（球隊輪值固定）
- 0.5-1.0 → 半輪值（drop +1 / anchor 中等）
- < 0.5 → 邊緣（drop 0 / anchor 低）

### Step 1.1b — 近期新聞（必做，SP 條件觸發層）

通用層（必做）見 SKILL.md。SP 條件觸發層：

| 觸發條件 | 搜尋詞 | 目的 |
|---------|-------|------|
| 老化區（age ≥32）| `{球員名} fastball velocity decline arm strength {今年}` | 速球下滑（K% 前驅）|
| Savant 訊號異常（Whiff% 跨年降 / xwOBACON 跨年升 / GB% 跨年掉）| `{球員名} pitch mix change mechanics adjustment {今年}` | 配球或機制調整 |
| IP/Team_G 偏低 | `{球員名} innings limit workload management {今年}` | IP 天花板 |
| 5-slot 與 ERA 矛盾（xERA-ERA \|Δ\| ≥0.81）| `{球員名} ERA luck BABIP {今年}` | 運氣訊號驗證 |

> 教訓：Woodruff「先發間隔 ≥5 天 + 主要目標季末健康」= IP 限縮；Detmers「GM 背書回歸先發」= SP 定位確認。

### Step 1.2 — WebSearch 補充

`{球員名} {去年} stats ERA WHIP strikeouts innings`

### Step 1.3 — 多年趨勢線（老化區 age ≥32 才做）

```
WebSearch: "{球員名} ERA FIP K% fastball velocity year by year"
```

> 拉 3-4 年 ERA / FIP / K% / fastball velocity（mph）。
> SP 殺手訊號：fastball velocity 連年下降 → K% / Whiff% 跟著掉。
> 區分：**真 decay**（角色不變，velocity 連 3+ 年降 + K% 同降）/ **角色轉型**（RP→SP 速球減速 1-2 mph 但用率不變或增加 = 配球策略，不是 decay）。

### Step 1.4 — Pitch Arsenal 3 年趨勢（必做，新升級）

> Detmers 案例驗證：這條是 SP 評估**最有資訊量**的訊號。能區分「角色轉型 vs velocity decay」。

```bash
ssh root@107.175.30.172 'python3 << EOF
import urllib.request, urllib.parse, csv, io
def fetch(year, mlb_id):
    params = {
        "hfSea": f"{year}|", "player_type": "pitcher",
        "pitchers_lookup[]": str(mlb_id),
        "min_pitches": "0", "min_results": "0", "min_pas": "0",
        "type": "details",
    }
    url = "https://baseballsavant.mlb.com/statcast_search/csv?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))

MLB_ID = {mlb_id}  # ← 替換
for yr in [2024, 2025, 2026]:
    rows = fetch(yr, MLB_ID)
    if not rows:
        print(f"{yr}: no data"); continue
    by_type = {}
    for r in rows:
        pt, rs = r.get("pitch_type", ""), r.get("release_speed", "")
        if pt and rs:
            try: by_type.setdefault(pt, []).append(float(rs))
            except: pass
    print(f"=== {yr} (n={len(rows)}) ===")
    for pt, speeds in sorted(by_type.items(), key=lambda x: -len(x[1])):
        usage = len(speeds) / len(rows) * 100
        avg = sum(speeds) / len(speeds)
        print(f"  {pt}: usage {usage:.1f}% avg {avg:.1f} mph (n={len(speeds)})")
EOF'
```

**讀法**：
- 跨年看 (a) 主球種使用率變動 (b) 速球 velocity 變動 (c) 新增/退役球種
- **角色轉型訊號**（不是 decay）：RP→SP 速球 velocity 下降 1-2 mph **+ 用率/球種數增加** = 配球深度化
- **真正 decay 訊號**：角色不變 **+ velocity 連 3 年降 ≥2 mph + 主球種使用率不變 + xwOBACON 跨年升**（雙條件確認）

### Step 1.5 — Platoon Splits vs L/R（必做，新升級）

```bash
ssh root@107.175.30.172 'python3 << EOF
import requests
MLB_ID = {mlb_id}  # ← 替換
for yr in [2025, 2026]:
    url = f"https://statsapi.mlb.com/api/v1/people/{MLB_ID}/stats?stats=statSplits&season={yr}&group=pitching&sitCodes=vl,vr"
    splits = requests.get(url).json().get("stats", [{}])[0].get("splits", [])
    print(f"=== {yr} ===")
    for s in splits:
        sit = s.get("split", {}).get("description", "?")
        st = s.get("stat", {})
        print(f"  {sit}: AVG {st.get('avg')} OPS {st.get('ops')} K {st.get('strikeOuts')} BB {st.get('baseOnBalls')} TBF {st.get('battersFaced')}")
EOF'
```

**讀法**：
- LHP 該對左打更好（同邊壓制），RHP 對右打更好
- 跨年同邊改善 = 配球策略奏效（**搭配 Step 1.4 arsenal 變化驗證**）
- 跨年雙邊同步惡化 (vs L 與 vs R OPS 都升 ≥+0.080) = 配球失效，drop 訊號（見 Step 3.5）
- vs L/R 差距 >.150 OPS 是 platoon 武器，串流時挑對戰打線

### SP 必須取得（不可用「大概」代替）

5-slot（IP/GS / Whiff% / BB/9 / GB% / xwOBACON）+ xERA / ERA / WHIP / K/9 / 球隊（W 支援判斷）/ BBE / **21d xwOBACON Δ + IP/Team_G + 3 年 arsenal + vs L/R splits**。老化區另需 age + 多年 ERA/FIP/K%/velocity。

---

## SP Step 2：評估流程

### 機械層篩選（與 fa_scan v4 對齊）

1. Rotation Gate 排除 pure RP（GS=0 或 IP/GS<3）+ cant_cut + IL/NA
2. 5-slot Sum：IP/GS / Whiff% / BB/9 / GB% / xwOBACON 各取百分位 → 1-10 分加總（Sum 5-50）
3. BBE <30 → low_confidence_excluded
4. Slump hold（2025 Sum ≥24 且 IP ≥50）獨立標註

### Drop urgency 4-factor

- **F1**：2026 Sum 越低分越高
- **F2**：2025 Sum 雙年檢核（<18 +2 / ≥24 移出）— ⚠️ **若 2025 為 RP 角色（GS=0），雙年檢核不適用**，標註「角色變化，prior 不對齊」
- **F3**：21d xwOBACON Δ（強劣化 +2 / 強回升 -2）
- **F4**：2026 IP/Team_G（≥1.0 +2 / 0.5-1.0 +1）

### 評估目標球員

- **FA SP** → 跟最弱 SP 比 5-slot Sum + ✅⚠️ tags（Sum 差 ≥3 + 2 項正向 = 機械 win_gate）
- **隊上 SP** → 看 urgency + 雙年檢核（角色變化時跳過 F2）+ 21d trend + slump 判斷
- **邊界 case** → 走 LLM 自由 reasoning

### 優先讀 fa_scan 最新 SP 報告

```bash
gh issue list -R huansbox/mlb-fantasy --label fa-scan --limit 5
gh issue view <N> -R huansbox/mlb-fantasy  # 找 [FA Scan SP-v4] 標題
```

> fa_scan SP 報告已對隊上 SP + FA 池跑完 v4 + Phase 6 multi-agent reasoning。**player-eval 在其上補的層**：新聞、多年 trend、age 老化、arsenal 跨年、platoon、decisive signal 雙條件確認。

---

## SP Step 3：比較與輸出

### 3.1 — 完整 9 欄比較表（v4 SP 升級版）

| 軸 | 2026 | 百分位 | 2025 prior | 21d | Δ trend |
|----|------|--------|-----------|-----|---------|
| IP/GS | x.xx | Pxx | x.xx | — | — |
| Whiff% | xx.x% | Pxx | xx.x% | — | — |
| BB/9 | x.xx | Pxx | x.xx | — | 雙年改善/惡化 |
| GB% | xx.x% | Pxx | x.xx | — | — |
| **xwOBACON** | **.xxx** | **Pxx** | **.xxx** | **.xxx** | **Δ ±0.0xx** |
| ERA | x.xx | — | x.xx | — | — |
| xERA | x.xx | — | x.xx | — | — |
| **\|xERA-ERA\|** | x.xx | (≥0.81 顯著) | x.xx | — | **buy-low / 賣高** |
| **IP/Team_G** | **x.xx** | **active 等級** | — | — | — |

附隊內 SP urgency 排序作背景（從 fa-scan 最新報告 Phase 6 worst 4 + 自算 Sum 推估）。

### 3.2 — Arsenal + Platoon 補述（必做，新升級）

簡表呈現 3 年 pitch arsenal 跨年 + vs L/R OPS 跨年。重點挑出：
- 主球種使用率變化（≥±5pp 標註）
- 速球 velocity 跨年差（標註 mph）
- 新增 / 退役球種
- 跨年同邊 platoon 改善 / 雙邊惡化
- 角色變化標註（RP→SP / SP→RP）

### 3.3 — 末行決策

「不動也是策略」+ Brand bias SP 觸發（見下）+ Step 3.5 decisive signal 收斂後寫單一行動。

---

## SP Brand Bias 警示（SP-specific 觸發條件）

評估隊上 SP 命中以下任一項時，**警示 brand bias，不得讓 owned% 拖延 drop**：

- 高 owned% (>80%) + 5-slot 4/5 P30 以下（**雙年確認且角色未變**）
- 高 owned% (>80%) + fastball velocity 連 3 年 ≥-2 mph **+ K/9 同步降**
- 高 owned% (>80%) + 21d xwOBACON Δ ≥+0.080 + BBE ≥30 連 7+ 天

**反向（buy-low / hold 強化）SP 特有訊號**：

- **xERA-ERA Δ ≤-0.81（P70+）+ owned% 跌**：市場看 ERA panic，xERA 暗示回歸 → **Detmers 模式**（buy-low）
- **角色轉型 + xwOBACON 維持 ≥P75**：RP→SP / SP→RP 第一年 prior 不適用結構崩判斷
- **5-slot Sum P50+ + ERA > xERA + 1.0**：機械層運氣標籤直接觸發 hold

> 教訓：Detmers 2026 SP 第一年，2025 RP xwOBACON .387 (<P25)。若機械套「雙年雙低 = 結構崩」會誤判 — 實際 2025 是 RP 角色，2026 SP 是新賽道，prior 不對齊。

---

## SP Step 3.5 — Decisive Signals（5 條，雙條件確認）

| Signal | 雙條件（必須 2 條同向）| 應觸發的結論 |
|--------|----------------------|--------------|
| **Velocity decay** | fastball velocity 連 3 年 ≥-2 mph **且** K/9 同步降 | drop 路徑優先序 +；趨勢支持 |
| **主球種失效** | 主球種使用率劇變（≥±15pp）**且** xwOBACON 跨年崩 | 配球結構崩，不可期待短期回歸 |
| **Platoon 雙邊惡化** | vs L 與 vs R OPS **同步**跨年 ≥+0.080 | 整體配球失效，drop 訊號 |
| **Owned + Savant 矛盾** | Owned% >80 **且** 21d xwOBACON Δ ≥+0.080 連 7+ 天 + BBE ≥30 | market lag 確認，drop 不等市場修正 |
| **新聞 explicit** | 球隊公開降輪值 **或** IP cap 公開 **或** 醫療長期 ≥4 週 | 結構性訊號，不是 noise |

### 反向訊號（buy-low / hold 強化）

| 訊號 | 雙條件 | 結論 |
|------|--------|------|
| **xERA-ERA buy-low** | xERA-ERA Δ ≤-0.81 **且** 21d xwOBACON Δ 中性或 ≤0 | hold 強化 / buy-low 窗口 |
| **角色轉型成功** | 主球種使用變化 ≥+5pp **且** 對應 platoon 改善 ≥-0.080 OPS **且** xwOBACON 維持 P75+ | 配球策略奏效，不是退化 |

### 輸出格式

- 命中 0 項 → 維持 Step 3 初判
- 命中 1+ 項 → 「**初判修正**：原 X 路徑 [撤回/升級]，理由：[命中 signal]」
- 反向訊號命中 → 「初判強化：hold/buy-low 證據鏈完整」
- 必須收斂單一推薦行動，不留多選並列

> ⚠️ **雙條件設計理由**：batter 路徑 5 條 decisive signals 都是單條件（如 launch angle Δ ≥10°）— 對 batter 適用是因為打擊機制改變難偽裝。SP 路徑 RP↔SP 角色轉型常觸發單一指標誤報（velocity 下降但實為策略），所以全部要雙條件交叉確認。

---

## SP Step 4：陣容脈絡（投手視角第 6 項）

承 SKILL.md 共用 1-5 項，SP 加：

6. **輪值排序**：Sum 排序 + 隊內 anchor 識別（Sale 模式 / Detmers buy-low 模式 / Severino slump 模式）。每週前 3 名 anchor + 候補 / 可串流 SP 區別處理。
7. **IP 累積能力**：每週 IP 預算（min 40 IP）— SP 主導，IP/Team_G + GS 連續性決定。drop 高 IP/TG SP 風險高。
8. **QS 能力**：IP/GS ≥6 + ERA 友善 + GB% 高 = QS 候選。drop 唯一 QS-friendly SP 風險高。
9. **2 SP 同隊風險**：避免同隊多名 SP 同步走 RP→SP（風險過度集中於同一個球團配球策略）。

---

## SP Error Checklist 補充（除了 SKILL.md 共用項）

- [ ] **21d xwOBACON Δ** 有沒有查（**`window_days=21, player_type="pitcher"`** 兩個參數都加了？）
- [ ] **IP/Team_G** 算了沒？方向（drop / anchor）對嗎？
- [ ] **角色變化（RP↔SP）** 有沒有標註？prior 雙年檢核是否該停用（F2 跳過）？
- [ ] **Pitch arsenal 3 年趨勢** 看了嗎？velocity 下降是 decay 還是角色轉型？
- [ ] **Platoon vs L/R** 看了嗎？跨年雙邊惡化還是同邊改善？
- [ ] **xERA-ERA \|Δ\|** 顯著（≥0.81）有沒有標 buy-low / 賣高？
- [ ] **隊內 SP urgency 排序** 做了嗎？目標 SP 在排序中位置？
- [ ] Decisive signals 是否走**雙條件確認**（不是單條件機械套用）？
