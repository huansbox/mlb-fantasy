---
name: rp-svh
description: "Fantasy Baseball 週級 RP-SV+H 掃描。production-first 找出 MLB 全聯盟近 14d SV+H 產出者中是聯賽 FA 的後援投手，三軸 rank-sum（BB/9 · whiff% · 30d SV+H）選 top-N，做角色安全 news check 後給 verdict（換 incumbent / hold / 選 1 / pass）。用戶說「掃 RP」「RP SV+H 掃描」「這週救援評估」「找個 SV+H RP」「rp scan」「rp-svh」時觸發，取代舊 fa_scan --rp 週掃。不用於評估特定已知球員（那是 /player-eval）或打者 / SP 的 FA 掃描（那是 /waiver-scan）。"
---

# RP-SV+H 掃描 SOP

主動掃 waiver wire 的 SV+H 產出者，每週與隊上 SV+H RP（incumbent）比較 → 明顯更優才換。

> **評估 SOP / 設計依據**：`docs/rp-svh-metrics.md`（production-first 邏輯、三軸 rank-sum、LLM 層輸入設計）。
> **球員追蹤**：`waiver-log-rp.md`（隊上 RP / FA 觀察中 / 已結案）。
> **本 skill 不做**：不評估打者 / SP（那是 /waiver-scan）/ 不評估特定指名球員（那是 /player-eval）/ 不算 FAAB 出價（FA add 走 $0）。

## 機會成本前提（LLM 必須知道）

- 聯賽現行策略 **Punt SV+H + 維持 2 RP**。本 SOP 是「放 1 個 RP 主攻 SV+H」的小幅調整，非全盤轉向。
- **已有 SV+H RP（incumbent）**：換人 = drop incumbent（同類別替換，一次 acquisition 成本）。
- **無 SV+H RP**：撿人 = 放棄一個 SP 串流格（跨類別取捨）。
- 賽制 7×7 H2H One Win，**只挑 1 個**。

## Step 1：跑機械層

機械層需 Yahoo token（只在 VPS）。SSH 跑 `rp_svh_scan.py`：

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && \
  python3 rp_svh_scan.py --pretty 2>/dev/null"
```

可選參數：`--floor N`（14d SV+H 入場門檻，預設 3）/ `--top N`（rank-sum top-N，預設 4，cutoff 並列一律納入）/ `--date YYYY-MM-DD`（預設 ET 今天）。stderr 走 fetcher progress（`2>/dev/null` 過濾），stdout 純 JSON。

## Step 2：讀 JSON

```json
{
  "scan_date": "2026-05-19",
  "floor": 3,
  "window_14d": {"start": "2026-05-05", "end": "2026-05-19"},
  "window_30d": {"start": "2026-04-19", "end": "2026-05-19"},
  "week_window": {"start": "2026-05-19", "end": "2026-05-25"},
  "candidate_pool_size": 23,
  "top_candidates": [
    {
      "name": "Adrian Morejon", "mlb_id": 101, "team": "SD", "team_id": 135,
      "percent_owned": "8%",
      "bb9": 2.35, "whiff_pct": 24.0, "whiff_pitches": 300,
      "whiff_low_sample": true, "svh_30d": 9,
      "axes": {
        "bb9":     {"value": 2.35, "rank": 2.0},
        "whiff_pct":{"value": 24.0, "rank": 2.0},
        "svh_30d": {"value": 9, "rank": 1.0}
      },
      "rank_sum": 5.0, "rank_sum_place": 1,
      "profile": {"svh_14d": 5, "sv_14d": 0, "h_14d": 5, "era": 2.10, "ip": 30.0},
      "role_signals": {
        "recent_10g": {"games": 10, "sv": 2, "h": 5, "svh": 7},
        "blown_saves": 1, "save_opportunities": 2,
        "week_schedule": {"games": 6, "opponents": ["LAD", "COL", ...]}
      }
    }
  ],
  "incumbent": {
    "name", "mlb_id", "in_pool": false,
    "bb9", "whiff_pct", "whiff_pitches", "whiff_low_sample", "svh_30d",
    "profile": {...同 candidate}, "role_signals": {...同 candidate}
  } 或 null,
  "all_candidates": [
    {"name", "team", "mlb_id", "svh_14d", "rank_sum", "rank_sum_place", "axes"}
  ]
}
```

機械層已內建：全聯盟 14d SV+H≥floor 篩選 → Yahoo FA 交叉（accent/apostrophe 正規化）→ 三軸 rank-sum（BB/9 升序 · whiff% 降序 · 30d SV+H 降序，等權，None 排最後）→ top-N（cutoff 並列納入）→ incumbent benchmark → top-N + incumbent 的角色訊號。

> **whiff% caveat**：RP 季中 arsenal ~300 球，低於 Savant 百分位基線 ≥500 球。`whiff_low_sample=true` 時 rank 仍可用（相對排序），但絕對值信心打折 — profile 顯示 whiff% 要帶此 caveat。

## Step 3：角色安全 news check（LLM 主戰場）

機械層已用 quant 選出 top-N。LLM 層 **thin** — 只做 C 類判斷（無結構化數據），**不重做 quant 排序、不做指標平均**。

對 `top_candidates`（+ `incumbent` 若存在）各 spawn 一個 `general-purpose` agent 並行查證。prompt 範本：

```
Search for recent news (last 2 weeks) about {name} ({team}) — a relief pitcher.

Determine:
1. Current bullpen role — confirmed closer? primary setup (8th inning)? or
   floating/committee? Any beat-writer / manager statement?
2. Role threats: committee bullpen, a rookie being tried, an injured
   closer/setup man about to return and squeeze him, recently demoted
   from high-leverage usage?
3. {team} this week vs {week_schedule.opponents} — opponent records /
   lineup strength, how many games are competitive (small-margin) vs blowout?

Context: 14d SV+H {svh_14d} ({sv_14d}SV/{h_14d}H), 30d SV+H {svh_30d},
blownSaves {blown_saves} / saveOpportunities {save_opportunities},
recent 10g SV+H {recent_10g.svh}.

Search beat reporters, MLB.com, Pitcher List, Fangraphs. Today is {currentDate}.
Report under 200 words.
```

針對性問題範例（依候選自行調整）：球隊是否已因連續 blown saves 移除某人 save 角色 / setup man 是否因 closer 傷癒回歸被擠 / 菜鳥是否正在試用期。

## Step 4：verdict

機械層 `incumbent` 欄位決定情況：

### 情況 A — 已有 SV+H RP（`incumbent != null`）

verdict = 最佳 FA **vs incumbent** → 「換」（指名 FA + drop incumbent）或「hold」（不動）。

- **預設 hold**。FA 需在 **SV+H 產出 + 角色穩定度** 上**明顯**優於 incumbent 才換 — 一次 acquisition 成本，不為邊際提升 churn。
- 「明顯優於」交 LLM 自由 reasoning，**不卡 binary 門檻**。對照 incumbent 的同款三軸 + role_signals 做 apples-to-apples。
- 換的判準脈絡：實際 SV+H 產出（14d / 30d / recent_10g）是 first-order，角色安全 news 是 first-order，rank-sum 名次是 second-order context。

### 情況 B — 無 SV+H RP（`incumbent == null`）

verdict = top-N 選 1 + 理由，或「都不值得佔一個 SP 串流格 → pass」。

### 判斷階層（兩種情況通用）

- **first-order**：角色安全（closer/setup 確定性、committee、傷兵擠壓、菜鳥試用）+ 實際 SV+H 產出。
- **second-order context**：rank-sum profile（BB/9 / whiff% / 30d SV+H 名次）。
- 不做指標平均 — quant 已由機械層 rank-sum 處理完。news check 推翻 rank-sum 名次是常態（如 rank-sum #1 因 save 上限封死 / 連續 blown saves 被降級）。

## Step 5：寫回 waiver-log-rp.md

依 verdict 更新 `waiver-log-rp.md`：

- **換**：incumbent 移到「已結案」（記 drop 理由），新 FA 寫入「隊上 RP」段（取得方式 / 加入時數據 / 選他理由 / 監看點 / incumbent benchmark 角色）。
- **hold**：incumbent 段更新本週數據對照（whiff% 監看點是否觸發等）；落敗的最佳 FA 若值得追蹤 → 寫「FA 觀察中」。
- **情況 B 選 1**：新 FA 寫「隊上 RP」段；其餘 top-N 值得追蹤的寫「FA 觀察中」。
- **pass**：不動 roster；top-N 中有潛力的寫「FA 觀察中」附觸發條件。

實際 add/drop 由用戶執行（FA add $0 即時生效）；roster_sync cron 會偵測並更新 config。

## 報告格式

```markdown
## RP-SV+H 掃描 {scan_date}

候選池：全聯盟 14d SV+H≥{floor} → {candidate_pool_size} 位 FA

### rank-sum top-{N}

| # | RP | 隊 | %own | 14d SV+H (SV/H) | 30d SV+H | BB/9 | whiff% | ERA+IP | rank-sum | recent10g | BS/SVO | 本週場次 |
|---|----|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ... |

### incumbent 對照（情況 A）

{incumbent 同款一行 + 三軸 + role_signals}

### 角色安全 news（每位 top-N）

**{Name}**：{closer/setup 確定性 · committee 與否 · 傷兵 / 菜鳥脈絡 · 本週對手}

### Verdict

{情況 A：換 {FA} drop {incumbent} / hold — 理由}
{情況 B：選 {FA} / pass — 理由}
```
