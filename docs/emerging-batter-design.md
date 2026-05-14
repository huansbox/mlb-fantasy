# /emerging-batter + /emerging-batter-deep Design — Batter 短期決策 skill

**狀態**：設計定稿（2026-05-14 session）
**前置依賴**：無（與 /stream-sp / /stream-sp-deep / /waiver-scan / /player-eval 並存，邊界明確）
**落地時機**：下次 session 從本 doc 寫 skill md + `emerging_batter_scan.py`（TDD）

---

## TL;DR

開兩個新 skill 對稱 SP 那側的串流路徑，補上 batter 短期決策空缺：

- **/emerging-batter** = batter 版 /stream-sp（找候選）
- **/emerging-batter-deep** = batter 版 /stream-sp-deep（指名深評）

**主軸不是 hot streak（預測力 R²~.05-.10 太弱），是 role change detection** — 抓「PA/TG 跳升 + lineup 角色變化」這類**結構訊號藏在短期數據裡**的候選；hot streak 進 scan 但分段呈現、權重低於 role change。

退場機制：14 天觀察期 + 災難 hard floor early drop + graduation 雙路徑（role change vs hot streak graduation 條件不同）。

---

## 為什麼

### 痛點

當前 4 個 skill 對 batter 的覆蓋有明確 gap：

| 路徑 | SP | Batter |
|---|---|---|
| 機械層每日自動報告 | fa_scan SP-v4 ✅ | fa_scan Batter-v4 ✅ |
| 長期深評（指名） | /player-eval ✅ | /player-eval ✅ |
| 主動掃 FA | /waiver-scan（共用） | /waiver-scan（共用） |
| **短期/即時決策** | **/stream-sp + /stream-sp-deep ✅** | **❌ 空缺** |

/player-eval 框架（雙年 prior + xwOBA/BB%/Barrel% v4 thin 三軸 + season 結構訊號）對「結構面中庸但短期有變化」的 batter 給不出明確 add 建議。H2H 一週為單位計分，當週 R/HR/RBI 才結算，但 player-eval 主要 lens 是「season-long 品質 + slump/breakout 識別」，跟「下週期望輸出」對不齊。

### 為什麼不是 hot streak skill

**Batter 短期 trend 預測力本身就弱**：7d OPS 1.000+ → 下週繼續火燙的條件機率比季線平均高不多。大半是 BABIP + 對戰運氣，不是能力變化。R² 大概 .05-.10（rolling 7d 對下週）。

**但短期數據裡有一類訊號預測力強很多** — 角色變化：
- 從替補變先發（PA/G 從 1.5 跳到 4.0）
- 從 platoon 變 everyday（vs 同手投手也排先發）
- 從 9 棒升 leadoff（lineup 位置變高）
- 受傷主力歸位後 lineup 重排

這些是**結構**不是運氣 — 對應訊號是 **PA/Team_G 跳升 + lineup 位置 + %owned 衝刺**，不是 OPS / Barrel 短期跳。

→ skill 主軸定位「emerging batter（角色變強中）」而非「hot streak 串流」。

### 為什麼 SP 路徑已獨立成 skill、batter 也該對稱

SP 短期決策已抽出 /stream-sp（找）+ /stream-sp-deep（深評），不擴 /waiver-scan。理由：/waiver-scan 是「主動掃全市場、週級節奏」；/stream-sp 是「針對特定日期、即時節奏」— 兩者觸發場景與 lens 不同，混在一個 skill 會讓決策路徑混亂。

Batter 同理：waiver-scan 維持全市場週級掃描，short-term lens 獨立成 skill。

---

## 設計核心

### 兩層分工

| 層 | 職責 | 輸出 |
|---|---|---|
| **機械層**（Python：`emerging_batter_scan.py`） | Yahoo FA pool 拉取 + role change 訊號 filter + hot streak 訊號 filter + 14d trad/Savant rolling enrich + cant_cut / 同類別飽和排除 | JSON：候選清單分兩段（role_change / hot_streak）+ 已過濾段 |
| **LLM 層** | 主表呈現 + 推/不推 verdict + pending file 寫入 + graduation 判斷 | Markdown 報告 + pending file update |

對齊 batter v4 thin 哲學：機械層**不算 score、不打 ✅/⚠️ tag、不做 verdict**，只做 hard filter 跟 enrich。

### 與既有 skill 的邊界（觸發語映射）

| 用戶意圖 | 觸發 skill |
|---|---|
| 「最近 FA 有什麼新冒出來的 batter」「掃一下 emerging batter」 | /emerging-batter |
| 「{球員} 短期值不值得撿」「深評 {球員}」（角色變化 / 短期 lens）| /emerging-batter-deep |
| 「掃 waiver」「有什麼人值得撿」（全市場週級） | /waiver-scan |
| 「{球員} 值不值得 add/cut/trade」（全季結構 lens） | /player-eval |
| 「下週覆盤 + 預測」 | /weekly-review |

灰區判斷：用戶問特定 batter 且**沒指定短期/長期** → 預設走 /player-eval（保守，全季 lens 適用範圍廣）。明確說「短期」「最近」「熱手」「角色變化」「下週」才走 /emerging-batter-deep。

---

## /emerging-batter — 找候選

### Step 結構（仿 /stream-sp）

**Step 0：Pending file 處理**

Pending file：`daily-advisor/emerging-batter-pending.md`（git 追蹤、markdown、AI 讀寫）。

- 讀檔 + 過期清理：對每個候選看 `entry_date + 14 天` 到期日；過期 + 未撿/未 pass → 提醒用戶決定（不自動刪，因為 graduation 需要 LLM 判斷）
- 判斷模式：補查 pending 中候選的最新表現 / 重跑全市場 / 忽略 pending

**Step 1：解析範圍**

不解析日期（不像 SP 對應某場）。直接 enter Step 2。可選擇：
- (a) 掃全市場 FA pool（default）
- (b) 只更新 pending 中候選的延續度

**Step 2-6：機械層 scan（emerging_batter_scan.py）**

- Yahoo FA pool 拉取（`yahoo_query.py fa --sort AR --sort-type lastweek --count 50`）
- 套 role change 訊號 filter（具體門檻見下節）
- 套 hot streak 訊號 filter
- 14d trad + Savant rolling enrich（reuse `savant_rolling.json`）
- cant_cut / 同類別飽和 / %owned > 40% 排除
- 不做 lineup 位置判斷（WebSearch agent spawn 成本高，留給 deep）

stdout = JSON，schema：
```json
{
  "role_change_candidates": [
    {
      "name": "...", "mlb_id": ..., "team": "...", "positions": [...],
      "percent_owned": "...", "owned_delta_3d": ..., "owned_delta_7d": ...,
      "pa_tg_14d": ..., "pa_tg_7d": ..., "pa_tg_jump": ...,
      "season": {"xwoba_pct": "...", "bb_pct_pct": "...", "barrel_pct_pct": "...", "bbe": ...},
      "rolling_14d": {"wobacon": ..., "barrel_pct": ..., "bbe": ...},
      "trad_14d": {"ops": ..., "hr": ..., "rbi": ..., "r": ..., "sb": ..., "k_pct": ..., "bb_pct": ...}
    }
  ],
  "hot_streak_candidates": [...],
  "filtered": {
    "cant_cut_conflict": [...],
    "position_saturated": [...],
    "high_ownership": [...],
    "low_confidence_bbe": [...]
  }
}
```

**Step 7：整合報告（Markdown）**

```markdown
## Emerging Batter 候選評估（{日期}）

### 已過濾
- cant_cut / 同類別飽和 / %owned > 40% / BBE 信心過低（列數量，不列名）

### Role change 候選（主推薦）
| # | Batter | 隊 | Pos | %own (Δ3d/Δ7d) | PA/TG 14d→7d | 14d wOBA/Barrel/BB% | 季結構 (xwOBA/BB/Barrel pct) | 推/不推 |
|---|---|---|---|---|---|---|---|---|

### Hot streak 候選（⚠️ 信心低，補充）
| 同欄位 + ⚠️ 標籤 |

### 推薦理由（每位 ✅ 的）
- Role change 訊號（PA/TG 跳升細節 / 雖無 lineup 位置但 PA 是強 proxy）
- 14d 表現匹配度
- 季結構 anchor（不是排他但作背景）
- 風險：BBE 樣本 / 角色穩定性質疑

### 不推薦速覽（一行）
```

**Step 8：寫 pending file**

對新加入觀察的候選：寫 entry_date、14 天到期日、role change 訊號摘要、14d 表現 snapshot。
對已在觀察中且本次重評的候選：append 新觀察行（不覆寫，保留時序）。

### 報告原則（仿 /stream-sp）

- 不算翻盤期望、不建議 drop 對象、不算 FAAB 預算
- 推薦門檻：role change 訊號通過 + 14d 表現匹配（不崩）+ 季結構不是雙年雙弱
- 全部不推 → 明確說「無 emerging batter 候選」

---

## /emerging-batter-deep — 指名深評

### Step 結構（仿 /stream-sp-deep）

**Step 0：定位 context**

從用戶輸入抽 batter 名 + （可選）「角色變化」「下週」等 lens hint。
- 0a：顯式給名 + lens → 直接跳 Step 1
- 0b：默認從 pending file 找該名 → 取觀察中 row 作起手 context
- 0c：取 MLB Player ID（Yahoo API search / MLB Stats API search）

**Step 1：拉 batter 14d game log + role 穩定度**

```
ssh root@107.175.30.172 "python3 batter_log.py {mlb_id} --days 14"
```

每場輸出：date / opp / H/A / lineup_spot / PA / AB / R / HR / RBI / SB / BB / K / wOBA。

整理出：
- **Role 穩定度**：14d PA/G 中位數 / lineup spot 1-9 分布 / 被替換頻率（PA <3 的場次比例）
- **近 14d wOBA / Barrel% / K% trend**（與 28d 對比）
- **vs RHP / LHP 14d split**

**Step 2：下週對戰 staff 評估**

抓 batter 球隊下週 6-7 場 schedule + 對手 probable SP 列表。

每位對手 SP：
- ERA / xERA
- vs same-hand split（batter 慣用手 → SP vs L/R OPS allowed）
- IP/GS（會被換 → 後段牛棚 OPS allowed）

加總「下週 staff 對 batter 慣用手整體 利好 / 中性 / 利空」。

**Step 3：交叉判斷（matrix）**

| Role 穩定 | 下週 staff | Verdict baseline |
|---|---|---|
| ✅ 維持 / 升級 | ✅ 利好 | ✅ 強推 |
| ✅ 維持 / 升級 | ⚠️ 中性 | ⚠️ 條件推 |
| ✅ 維持 / 升級 | ❌ 利空 | ⚠️ 條件推（撿來等下下週） |
| ⚠️ 不穩 | ✅ 利好 | ⚠️ 條件推（短打） |
| ❌ 退化 | 任何 | ❌ 不推 |
| 無 role change（純 hot streak） | ✅ 利好 | ⚠️ 條件推（標 hot streak 警示） |
| 無 role change（純 hot streak） | ❌ 利空 | ❌ 不推 |

### Step 4：verdict + 期望

期望輸出（下週 6-7 場累積）：
- PA（基於 role 穩定度推估）
- R / HR / RBI / SB（基於 14d rate × 預期 PA）
- 下週 OPS 區間
- 對 contested 類別影響（不算翻盤期望勝率，用戶自判）

### Step 5：寫回 pending file

- Verdict divergence callout（若 deep verdict ≠ pending 上次）
- 更新 `last_recheck_at`
- 比較段（同 ET 期間 pending 中其他候選 → 自動產出排序表）

### 不做

- 不重新跑 emerging_batter_scan.py（已有 pending 帶基本資訊）
- 不算 FAAB 出價
- 不建議 drop 對象
- 不算 lineup lock 時序

---

## 訊號門檻定義（3 個決策）

### 決策 1：Role change 訊號

| 訊號 | 門檻 | Rationale |
|---|---|---|
| **PA/TG 跳升** | 7d PA/TG ≥ 3.5 **且** (7d − 14d) ≥ +1.0 | 3.5 = P80（CLAUDE.md 百分位表）= 主力門檻；跳 +1.0 排除單場 lineup 漂移 |
| **%owned delta** | 3d ≥ +5pp 或 7d ≥ +10pp | 對齊 fa_scan 既有 shape（explosive/rising）；聯盟層級發現訊號 |
| **Lineup 位置** | scan **不抓**，deep 階段補 | WebSearch agent ~50K tokens × 多候選成本高；PA/TG 已是強 proxy；deep 量級才合理 |

任一訊號達標 + 14d trad 表現匹配（OPS ≥ .650 OR R+HR+RBI ≥ 8）→ 進 role_change_candidates 段。

### 決策 2：Hot streak 訊號（分段呈現）

進 `hot_streak_candidates` 段（標 ⚠️ 信心低）條件：

- 14d wOBA ≥ P75 **或** 14d Barrel% ≥ P75（rate stat 看 wOBA 比 OPS 純）
- 14d BBE ≥ 25（樣本門檻，比 fa_scan v4 batter 的 40 寬，因為這層本來信心就低）
- season Sum 中等（在 v4 thin Sum<25 池）
- **沒有** role change 訊號（不然應該歸 role_change_candidates 段）

Why 分段：第 1 段是結構訊號（預測力強），第 2 段是短期表現（預測力弱但偶有真 breakout）。讓用戶看見差別 → 對應不同 FAAB 出價 + 期望值。

### 決策 3：14 天 graduation 判斷（雙路徑）

**Path 1：Role change 候選 graduation**

| 條件 | 動作 |
|---|---|
| Role 維持（7d PA/TG ≥ 3.0 + 沒被降到 8-9 棒/板凳）+ 表現匹配（14d OPS ≥ .700 OR season Sum +3）| ✅ hold（從 pending 移「已轉正」段，後續走 /player-eval） |
| Role 維持 + 表現崩（14d OPS <.600） | ⚠️ extend 1 週（給樣本機會） |
| Role 退化（PA/TG <3.0 或 lineup 降到 8-9 棒）| ❌ drop（不管表現） |

**Path 2：Hot streak 候選 graduation**

| 條件 | 動作 |
|---|---|
| 表現延續（14d OPS ≥ .750，比 Path 1 嚴）| ✅ hold |
| 出現 role change 訊號 | ✅ 升級到 Path 1（從此走 Path 1 條件） |
| 表現回落（14d OPS <.650） | ❌ drop |
| 中間（.650-.750）| ⚠️ extend 1 週 |

Why Path 2 比 Path 1 嚴：當初是用「熱」撿的（無結構錨）→ 要求表現延續門檻更高，否則確認是 BABIP noise。

**災難 hard floor early drop（不到 14 天就 drop）**

| 條件 | 動作 |
|---|---|
| 連 3 天 0 PA（板凳 or IL）| 立即 drop — role 崩 |
| 7d ≥15 PA 但 OPS <.450 | 立即 drop — 災難表現 |

---

## Pending file Schema

`daily-advisor/emerging-batter-pending.md`：

```markdown
# Emerging Batter Pending Log

## 觀察中 — Role change 候選

### {Batter Name} ({Team}, {Positions})
- entry_date: 2026-05-14
- expiry: 2026-05-28（14 天觀察期）
- last_recheck_at: 2026-05-14
- 撿入時訊號:
  - PA/TG 14d→7d: 1.8 → 4.0（+2.2）
  - %owned: 8% (Δ3d +6pp, Δ7d +12pp)
  - 14d wOBA / Barrel% / BB%: .380 / 12.5% / 10.2%
  - 季結構 (xwOBA/BB/Barrel pct): P45 / P55 / P50
  - 14d trad: OPS .812, R 8, HR 3, RBI 9, SB 1
- 觀察紀錄:
  - 2026-05-14: 撿入。role 訊號 PA/TG 跳 +2.2 + %owned 7d +12pp = explosive。
- Verdict（上一輪 scan / deep）: ⚠️ 條件推

## 觀察中 — Hot streak 候選

### {Batter Name} ({Team}, {Positions}) — ⚠️ 信心低
- 同上 schema，標 hot_streak_track
- Path 2 graduation 條件適用

## 已轉正（hold，後續走 /player-eval）

### {Batter Name} — graduated 2026-05-28
- 一行：role 維持 + 14d OPS .780 → 持續 hold

## 已結案

### {Batter Name} — drop 2026-05-22
- 一行：連 3 天板凳，role 崩 → early drop

### {Batter Name} — pass 2026-05-14
- 一行：role 訊號達標但 14d OPS .580 表現不匹配 → 不撿
```

---

## 機械層實作骨架

`emerging_batter_scan.py`（仿 `stream_sp_scan.py` 模式 + TDD）：

```python
def scan(
    fa_fetcher: Callable,  # Yahoo FA query
    rolling_loader: Callable,  # savant_rolling.json
    config_loader: Callable,  # roster_config.json (for cant_cut / 隊上同位置)
) -> dict:
    """Return {'role_change_candidates': [...], 'hot_streak_candidates': [...], 'filtered': {...}}"""
    fa_pool = fa_fetcher(sort='AR', sort_type='lastweek', count=50)
    rolling = rolling_loader()
    config = config_loader()

    candidates = []
    for batter in fa_pool:
        if batter['mlb_id'] in cant_cut(config):
            continue
        if batter['percent_owned'] > 40:
            continue
        # ... 套門檻
        candidates.append(enrich(batter, rolling))

    return classify(candidates)  # 分 role_change / hot_streak / filtered
```

測試：
- `test_classify_role_change_triggers_on_pa_tg_jump`
- `test_classify_hot_streak_requires_no_role_signal`
- `test_filter_cant_cut`
- `test_filter_high_ownership`
- `test_graduation_path1_role_maintained_performance_ok`
- `test_early_drop_3_day_bench`
- ... 約 20-25 個 test case

CLI：`python3 emerging_batter_scan.py 2>/dev/null` 純 JSON stdout。

---

## 不做（避免 scope creep）

- 不抓 lineup card 位置（WebSearch 成本高，PA/TG 是強 proxy；deep 階段可補）
- 不算 FAAB 出價建議（emerging batter typical $0-2，預算策略 ≠ 找候選）
- 不建議 drop 對象（用戶看 fa_scan Batter-v4 issue 找最弱）
- 不算 lineup lock 時序（同 /stream-sp）
- 不重新評估「該不該撿」（用戶呼叫時已決定要看 emerging batter）
- 不主動掃全市場（那是 /waiver-scan）
- 不做全季結構深評（那是 /player-eval）

---

## 尚待決定（落地時 anchor）

1. **`emerging-batter-pending.md` 已轉正段是否寫 audit**？或乾脆刪除？傾向：保留 1-2 週後刪（git log 可回溯）
2. **同類別飽和門檻**：「隊上同位置已有 P75+ anchor」如何定義？傾向：簡單 cap — 同位置 active batter ≥2 位且都 ≥ season Sum 25 → 飽和
3. **/emerging-batter 是否該日呼叫 1 次 limit**？SP 是每天可呼叫（probable starter 變化快），batter 變化慢 → 建議每 2-3 天呼叫 1 次（成本 / 信號比較）
4. **Hot streak 段是否該完全砍掉**？落地後觀察 1-2 個月 — 若 hot streak 段歷次推薦命中率明顯低於 role change → 砍。先留著做數據
5. **Lineup 位置在 deep 階段怎麼取**？WebSearch agent vs MLB Stats API gameLog 的 `battingOrder` 欄位？傾向後者（API 比 search 穩 + 免費）
6. **vs RHP/LHP split 樣本門檻**：14d 內 PA <10 對單手投手 → 不算 split 訊號（樣本太小）。具體門檻待落地驗證

---

## 落地清單（下次 session）

| 順序 | 項目 | 預估 |
|---|---|---|
| 1 | TDD 寫 `daily-advisor/emerging_batter_scan.py` + 20-25 個 test case | 2-3 小時 |
| 2 | 寫 `.claude/commands/emerging-batter.md`（仿 stream-sp.md 結構） | 1 小時 |
| 3 | 寫 `.claude/commands/emerging-batter-deep.md`（仿 stream-sp-deep.md） | 1 小時 |
| 4 | 建立 `daily-advisor/emerging-batter-pending.md` 空檔 + schema 範本 | 15 分鐘 |
| 5 | CLAUDE.md 更新「檔案索引」+ Skills 觸發詞表（如有） | 30 分鐘 |
| 6 | 跑 1-2 次 e2e 驗證（real Yahoo API + real rolling data） | 30 分鐘 |
| 7 | 觀察期 1-2 週後 review：role change vs hot streak 命中率對比 | — |

依賴：無新外部資源；reuse `yahoo_query.py fa` + `savant_rolling.json` + `roster_config.json`。
