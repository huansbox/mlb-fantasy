---
name: stream-sp
description: "Fantasy Baseball 串流 SP 候選評估。給定未來 1-3 天的 ET 日期範圍（默認明後天），找出 MLB probable starter 中是聯賽 FA 且非 opener 的真先發，套 v4 5-slot 框架評估值不值得撿來投一場。用戶說「明後天有沒有可串的 SP」「這兩天 FA SP 評估」「ET X/X stream SP」「值得撿哪場」「明天找個 SP 」時觸發。已假設用戶已決定要串流（不做要不要串流的預檢、不算翻盤路徑、不建議 drop 對象、不算 FAAB 預算），只負責找誰可串。不用於主動週級 FA 掃描（那是 /waiver-scan）或評估特定已知球員（那是 /player-eval）。"
---

# 串流 SP 候選評估 SOP

主動找出指定日期範圍內 MLB probable starter ∩ 聯賽 FA ∩ 真先發的候選，並用 v4 5-slot 框架排序值不值得串。

> **評估標準**：見 `CLAUDE.md`「SP 評估（v4）」段（唯一定義，本 SOP 不複製百分位表 / Sum 算式）。
> **串流 mental model / 操作時序**：見 `docs/streaming-sp-playbook.md`。
> **本 skill 不做**：不評估「該不該串流」（用戶呼叫時已決定要串）/ 不建議 drop 對象 / 不算 FAAB 餘額 / 不算翻盤期望。

## Step 0：Pending TBD 處理

Pending file：`daily-advisor/stream-sp-pending.md`（git 追蹤，跨機同步；markdown 格式，AI 讀寫，schema 見 Step 8）。

### 0a：讀檔 + 過期清理

1. **讀檔**：Read `daily-advisor/stream-sp-pending.md`（不存在 → 視為空，跳過清理）
2. **取當前 ET 時間**：TW now → ET（UTC-4，MLB 4-10 月 DST）
3. **對檔內每個 `## ET YYYY-MM-DD` H2 section**：
   - 解析 ET 日期
   - 過期門檻 = ET 該日 13:00（第一場開打，串流不可能再來得及）
   - 若 `now_et ≥ 門檻` → 用 Edit 刪整個 H2 section（從該 H2 到下一個 `## ` 標題前；包含其下所有 `### TBD 場次` / `### 已評估` / `### 備註` 子段）
4. **若有清理**：主動告知用戶「清掉 ET {日期} pending（已過 13:00）」

過期條目直接刪，不留 history。備註段（free-form 用戶手寫）也一併清掉。

### 0b：判斷模式（補查 / 重跑 / 忽略 pending）

| 用戶輸入訊號 | 動作 |
|---|---|
| `/stream-sp 5/8 --tbd-only` 或「補查 5/8 TBD」「補查 pending」| 直接走補查模式（只跑 pending 對應 ET 日的 TBD 場次）|
| `/stream-sp 5/8`（顯式日期）+ pending 有該日 | AskUserQuestion：「ET 5/8 上次留 N 場 TBD，要 補查（只跑 TBD）/ 重跑全部 / 忽略 pending」|
| `/stream-sp` + pending 非空 | AskUserQuestion 同上，但選項加「先看 Step 1b 列出 3 天再決定」|
| `/stream-sp` + pending 為空 | 直接走 Step 1 |

**批次補查多日**：補查模式支持同次 run 處理多個 ET 日（用戶在 Step 1b 的 AskUserQuestion multiSelect 選多天，且每天 pending 都有條目）。每日獨立走 Step 2-7-8 流程，pending 表格寫入互不干擾。Step 7 報告對每個 ET 日各產一段。

如有過期清理，主動告知用戶：「清掉 ET {日期} pending（已過 13:00）」。

## Step 1：解析日期範圍

> 補查模式跳過此步（ET 日期已由 Step 0 從 pending file 取得）。

### 1a：若用戶顯式指定 ET 日期

- 用戶說「ET 5/8」「ET 5/7 5/8」「2026-05-08」 → 直接使用，跳到 Step 2
- 用戶說相對詞「明後天」「明天」「這兩天」**不要直接套 currentDate ± N**（時區語義不穩，TW 用戶的「明天」常等於 ET currentDate 而非 +1）→ 走 1b 讓用戶挑

### 1b：默認 — 列出未來 3 天 ET 比賽日讓用戶挑

從 `currentDate` 起算，查 MLB API schedule 取連續 3 天，每天的場次數 + TBD 數，呈現給用戶選：

```bash
for offset in 0 1 2; do
  date=$(date -j -v+${offset}d -f '%Y-%m-%d' '2026-05-07' '+%Y-%m-%d')  # macOS
  curl -s "https://statsapi.mlb.com/api/v1/schedule?date=$date&sportId=1&hydrate=probablePitcher" \
    | python3 -c "<count games + TBD>"
done
```

呈現給用戶（用 AskUserQuestion）：

```
ET 2026-05-07：10 場 / 0 TBD
ET 2026-05-08：15 場 / 8 TBD
ET 2026-05-09：14 場 / 12 TBD
```

讓用戶 multiSelect 想評估的日期。**Lineup lock 時序由用戶自行判斷**（本 skill 不算）。

> 為什麼不默認 currentDate + 1：TW 用戶在 TW 早上/中午時，currentDate = TW 今天 ≈ ET 今天，但「今晚要看的 MLB 比賽」是 ET currentDate（= 用戶口中的「明天」）。直接套 +1 會少一天。讓用戶挑可避免時區語義踩雷。

## Step 2-6：機械層（單一 CLI 呼叫）

> 原本 5 個 step ~180 行 inline bash + python3 已壓縮成 `daily-advisor/stream_sp_scan.py`（TDD 27 tests，commit `96830ba`）。

對 Step 0/1 確定的 ET 日期清單，一次呼叫：

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && \
  python3 stream_sp_scan.py --et-dates 2026-05-14,2026-05-15 2>/dev/null"
```

`stdout = JSON`，schema：

```json
{
  "2026-05-15": {
    "tbd_games": [
      {"away": "PHI", "home": "PIT", "side": "both|away|home"}
    ],
    "candidates": [
      {
        "name": "Sean Burke", "mlb_id": 680732,
        "team": "CWS", "opponent": "CHC", "is_home": false,
        "opener_verdict": "true_starter|opener_suspect|small_sample",
        "opponent_14d": {"ops": 0.702, "tier": "🟢|🟡|🔴"},
        "v4_2026": {
          "ip_gs": 5.11, "whiff_pct": 19.5, "bb9": 2.04,
          "gb_pct": 41.5, "xwobacon": 0.354,
          "g": 8, "gs": 6, "ip": 44.0, "bbe": 130,
          "era": 3.68, "xera": 3.79,
          "sum_score": 24,
          "breakdown_pct": {"IP/GS": "<P25", "Whiff%": "<P25",
                            "BB/9": "P80-90", "GB%": "P40-50",
                            "xwOBACON": "P70-80"},
          "rotation_gate": "🟢|🟡|🚫",
          "luck_tag": "+1.52 | -1.50 | null"
        },
        "v4_2025": {"...同 v4_2026 schema..."}
      }
    ],
    "owned_by_me": [{"name", "mlb_id", "team", "opponent", "is_home"}],
    "owned_by_others": [{"name", "mlb_id", "team", "opponent", "is_home"}]
  }
}
```

scan 已內建：schedule parse（TBD 三態 both/away/home）/ Yahoo FA cross-check / v4 5-slot Sum + breakdown_pct labels / rotation gate / luck tag（xERA-ERA 差 ≥ P70 0.81 才標）/ opener 規則化 / 對手 14d OPS → tier。stderr 走 sp_data_fetchers 的 progress prints（用 `2>/dev/null` 過濾掉），stdout 純 JSON。

### 過濾規則（LLM 拿 JSON 後執行）

對每個 `candidates[i]`：

| 條件 | 動作 |
|---|---|
| `v4_2026.rotation_gate == "🚫"` | 移到「已過濾 / Rotation gate 排除」段，**不**進主表 |
| `v4_2026.sum_score < 15` | 移到「已過濾 / Sum hard floor 排除」段 |
| `opener_verdict in {"opener_suspect", "small_sample"}` | **必須 WebSearch 確認**（見下段）。確認為 opener → 移到「已過濾 / Opener 排除」段 |
| 通過以上全部 | 進「FA 真先發候選」主表 |

> 設計理由：rotation_gate / sum_score 是純規則，已由 scan 算好；不浪費 WebSearch 額度（~50K tokens / 70+ 秒每次）。opener_verdict 是規則粗篩，邊界場景仍需 LLM 看新聞脈絡判斷實際角色。

**Sum 區間參考**（推薦標準在 Step 7）：
- Sum 5-15：結構性確認弱（hard floor，淘汰）
- Sum 15-25：偏弱但保留（mixed-role / breakout 候選可能在此）
- Sum 25-30：邊緣，看單軸 elite
- Sum ≥ 30：整體菁英軸

### 自動 WebSearch（opener_verdict ≠ true_starter 才觸發）

Spawn `general-purpose` agent，prompt 範本：

```
Search for news about {name} ({team}) starting on {ET_date} vs {opponent}.

Determine:
1. True starter or "opener" (1-2 IP + bulk reliever behind)?
2. If opener, who is the planned bulk pitcher?
3. Expected workload / pitch count if known?

Context: opener_verdict={opener_verdict}, recent_game_log_summary={一行}

Search beat reporters, MLB.com, Pitcher List, Fangraphs. Today is {currentDate}.
Report under 200 words.
```

WebSearch 結論：
- **真先發 + 預期 IP ≥ 5** → 過關進主表
- **Opener / piggyback / 沒拉長 → 預期 IP ≤ 4** → 移到「已過濾 / Opener 排除」段（QS 機率太低，串流 ROI 差）

### 補查模式：對照 pending TBD list

scan 對 `--et-dates` 給的所有日期都跑完整流程（**不**做 TBD-only filter — scan 不讀 pending file）。**補查模式下 LLM 拿到 JSON 後**：
- 對照 `daily-advisor/stream-sp-pending.md` 該 ET 日的 TBD list
- candidates 中對應 pending TBD 的 starter 視為「新評」（Step 7 報告 SP 名前加 🆕 標記）
- TBD list 中已不在 `tbd_games` 的場次 = starter 已公布 → 該 starter 應出現在 candidates / owned_by_me / owned_by_others 三者之一

scan 不知道 pending file 存在，pending diff 是 LLM 的職責。

## Step 7：整合報告

### 補查模式：合併呈現舊 evaluations + 新評

**僅補查模式（Step 0b 走補查模式 + 該 ET 日有舊 pending）才執行此段**：

1. 從 pending file 讀回該 ET 日 `### 已評估` 表格的 row（舊評）。**「舊評」嚴格僅指此表格內容，不含上次或當次報告的「已過濾」段（Sum<15 hard floor / Rotation gate / Owned 別隊 / Owned 自家）**。已過濾的候選不持久化、不帶回 — 它們是結構性結論，補查時新評同樣的 filter 邏輯會再排除一次。
2. 新評的 row 在 SP 名前面加 `🆕` 標記
3. 合併新舊兩份清單，按 v4 Sum26 由高到低排序
4. 在主表「FA 真先發候選」中合併呈現（**不分舊/新兩段**，只用 🆕 標記區分）
5. 報告開頭加一行：「補查 ET {日期}：新評 {N} 位（🆕 標記），舊評 {M} 位帶回」

**特殊情況：補查無新 starter 公布（新評 = 0）**

若該 ET 日本次補查跑完發現 TBD 對應的 starter 仍全部未公布（或公布但全被過濾掉，新評 0 位）：

- 步驟 1-4 跳過，**不重新呈現舊 evaluations 主表**（避免報告冗長 + 用戶誤以為要再決策一次）
- 報告該 ET 日只寫一行：「**ET {日期}：本次補查無新公布 starter，僅更新 `last_recheck_at`（{舊值} → {新值}）**」
- pending file 寫入：仍按 Step 8b 補查模式更新 `last_recheck_at`（audit trail），TBD list / evaluations / 備註不變

這個分支是為了避免另一個踩坑情境：用戶看不到報告變化但 master 出現 dirty pending file，會疑惑「跑了什麼」。明確標註「nothing changed, only timestamp」讓用戶有 audit 線索。

非補查模式（首次評估該 ET 日 / 重跑模式）跳過此段。重跑模式 Step 7 純走首次評估邏輯。

### 輸出格式

```markdown
## ET {日期} probable FA starter 評估

### 已過濾
- TBD probable: {N} 場（建議 ET-1 day 早上補查）
  - 列出 TBD 場次：{Team A @ Team B}
- Owned by 別隊: {N} 位（不列）
- 本隊已有: {N} 位（不列）
- Rotation gate 🚫 排除: {N} 位（{name} G/GS={g}/{gs} - pure-RP / long-relief）
- v4 Sum < 15 hard floor 排除: {N} 位（{name} Sum {n} - 五軸全 P25 以下，跳過 opener filter 直接淘汰）
- Opener 排除: {N} 位（{name} - {WebSearch 結論摘要}）

### FA 真先發候選（按 v4 Sum 排序）

| # | SP | 隊 | 對手 | %own | v4 Sum26/25 | 5-slot 細節 | 對手 14d OPS / tier | 推/不推 |
|---|----|---|---|---|---|---|---|---|
| 1 | Keider Montero | DET | KC 🟢 | 9% | 29/22 | IP/GS P60-70 \| Whiff <P25 \| BB/9 >P90 \| GB <P25 \| xwOBACON >P90 | .698 🟢 | ✅ 推 |
| ... |

### 推薦理由（每位推薦的）

**{Name}**：
- v4 結構：{2-3 個 elite 軸點出}
- 對手：{tier + OPS}
- 風險：{IP/GS 短 / Whiff 低 / 雙年低 等}
- 期望：{IP / K / QS 機率粗估，一句話不量化}

### 不推薦速覽（一句話帶過）

- **{Name}**：{結構性弱 / 對手太硬 / 限局型 — 一行}
- ...

### TBD 提醒

ET {日期} 剩 {N} 場 TBD probable，已記錄至 `daily-advisor/stream-sp-pending.md`。建議 TW {日期} 早上 9-10 點呼叫 `/stream-sp 補查` 或 `/stream-sp {ET 日期} --tbd-only` 只跑這 N 場，不重評其他。
```

### 報告原則

- 推薦標準：v4 Sum ≥ 25 + 至少 1 個 elite 軸（>P90 或 P80-90）+ 對手不是 🔴 強打 — 三條件至少滿足兩條
- **不算翻盤期望勝率**（用戶自己判斷對本週類別狀況的影響）
- **不建議 drop 對象**（用戶自己看當天 fa_scan SP-v4 issue 找 worst SP）
- **不算 lineup lock 時序**（用戶自己換算）
- 若全部候選都不推（Sum < 25 或對手全 🔴）→ 明確說「無值得串流的候選」

## Step 8：寫/更新 pending file

對本次跑的每個 ET 日期，更新 `daily-advisor/stream-sp-pending.md`。AI 直接用 Read/Write/Edit 操作 markdown，不走 Python json。

### 8a：Schema 範本（每個 ET 日期一個 H2 section）

```markdown
## ET 2026-05-10
- recorded_at: 2026-05-08T18:00:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- TB @ BOS (BOS home TBD)
- COL @ PHI (PHI home TBD)
- DET @ KC (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Cade Cavalli | WSH | MIA (.618) | 20% | 25/31 | <P25·P70-80·<P25·P50-60·**P80-90** | ✅ 強推 | Whiff/xwOBACON 雙菁英 + 對手最弱 |
| Chris Bassitt | BAL | ATH (.780) | 13% | 18/28 | <P25·<P25·<P25·P70-80·P60-70 | ❌ 不推 | 5 軸 3 <P25 + 對手最硬 |

### 備註
_（free-form 區，用戶可手寫「已 claim X $3」「想下週再評估 Y」等註記。AI 讀進來但不主動覆寫。）_
```

### 8b：寫入規則

對應 Step 0b 三種輸入模式（補查 / 重跑全部 / 忽略 pending）+ pending file 是否已有該 ET 日 H2 section：

- **首次評估該 ET 日**（pending file 沒有此 H2 section）：
  - 用 Edit / Write 在檔尾 append 整個 H2 section
  - `recorded_at` = 當下 TW ISO 時間（精確到秒），`last_recheck_at` = `—`
  - TBD 場次 + 已評估表格寫入，備註留空提示文字

- **補查模式**（已存在該 ET 日 H2 section + Step 0b 走補查）：
  - 用 Edit 更新 `last_recheck_at` 為當下 TW ISO 時間，`recorded_at` 保留原值
  - 用 Edit 替換 TBD 場次列表（剩下還沒公布的）
  - 用 Edit 在已評估表格 append 新評 row。**Dedup 規則**：append 前先掃表格是否已有同 SP 名 row（用 SP 名作 key），**有則 Edit 覆寫該行**（保留位置不重排，更新成本次新評的數值），**無才 append 在表尾**。避免同投手在不同 run 出現重複行。
  - 備註段保留原樣不動

- **重跑模式**（已存在該 ET 日 H2 section + Step 0b 走「重跑全部」或「忽略 pending」）：
  - 用 Edit 整段替換 H2 section 內容：
    - `recorded_at` 保留原值（語義 = 該 ET 日初次寫入時間，不重置）
    - `last_recheck_at` 更新為當下 TW ISO 時間
    - TBD 場次列表 + 已評估表格 **完全用本次新評取代**（不 append 舊 row、不 dedup，整個 reset）
  - 備註段保留原樣不動

- **TBD 完全公布**（list 變空 + 走補查/重跑且本次跑完無 TBD 剩）：刪除整個 H2 section（包含 evaluations + 備註，因為決策週期結束）

### 8c：哪些評估會寫入

只寫入 **過 Rotation gate + Sum ≥ 15 + opener 確認真先發**（即 Step 2-6 過濾規則全通過）的候選（推薦 ✅ + 不推薦 ❌ 都寫，確保補查時能對照優劣）。

**不寫入**：
- Rotation gate 🚫 排除（pure-RP / long-relief）
- Sum < 15 hard floor 排除
- Opener 排除
- 上述三類是結構性結論，補查時新評同樣會走這三個 filter，無需保留歷史

### 8d：TBD 場次格式

每行一場 TBD：
- `AWAY @ HOME (AWAY away TBD)` — 客場 SP TBD
- `AWAY @ HOME (HOME home TBD)` — 主場 SP TBD
- `AWAY @ HOME (both TBD)` — 兩邊都 TBD

補查模式對照新 schedule 的 diff 邏輯：對檔內每行 TBD 找對應今日 schedule 的場次，原 TBD 邊現在公布 starter 即視為「該 starter 進候選池」走 Step 3-7，並從 TBD list 移除。
