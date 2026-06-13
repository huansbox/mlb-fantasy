# Post-hype prospect pedigree（issue 049 / GitHub #328）

打者 post-hype 標記的資料資產 + 引擎。一個年輕、前百大新秀出身、但 MLB 成績到目前
還差的候選 → 給 LLM「折價爛 prior」的授權，避免被雙年低分當結構性弱誤殺（反例：
Jordan Walker，BR 2023 #4 / MLB Pipeline #2，當時 21 歲被當 cut 候選）。

## 檔案

| 檔 | 角色 |
|----|------|
| `daily-advisor/prospect_pedigree.json` | **資料資產**。`mlb_id → {best_rank, best_rank_year, name}`。手動維護，每年 3 月刷新。join key = mlb_id（API 驗證過），`name` 只供人看、不做比對 |
| `daily-advisor/prospect_pedigree.py` | **執行期引擎**（stdlib only，純函式）。load / stale 偵測 / pedigree join / post-hype predicate + tag。不 import 專案其他模組、不碰網路 |
| `daily-advisor/build_prospect_json.py` | **builder**。吃排名來源 TSV → MLB Stats API 程式化解析 mlb_id → 寫 JSON。每個 id 都是 API 查出來的，**不 hardcode**（CLAUDE.md no-hardcode rule）|
| `daily-advisor/prospect_rankings_raw.tsv` | builder 的輸入。`year<TAB>rank<TAB>name`，# 開頭為註解。本資產的人工維護面就是這個檔 |

## 每年 3 月刷新（~30 分）

1. 把新一季的 Top 100（名次 + 名字）貼進 `prospect_rankings_raw.tsv`，格式 `year<TAB>rank<TAB>name`。
   舊年份保留 —— builder 會跨年取 best（最低）rank。
2. `cd daily-advisor && python build_prospect_json.py`
3. 看 builder 輸出：
   - `resolved N` → 寫進 JSON 的（已登板、id 唯一）。
   - `dropped …（age > 28）` → 同名老將碰撞，自動剔除（lossless：執行期 age gate ≤25，>28 本就永不觸發）。
   - `needs_review …` → 沒對到 MLB id（多半是還沒登板的純新秀）或同名碰撞，**一律排除、不猜 id**。等他登板後下次刷新自動納入。
4. `git diff prospect_pedigree.json` 眼睛掃一遍 → commit。

未更新會怎樣：引擎的 `is_stale()` 在「比 updated 晚一年且過了 3 月」時自動判 stale，
報告端 tag 降級為 `⚠️ post-hype 名單過期 (#R YEAR)`，**不靜默用舊資料**（PRD 灰色地帶先例）。

## 資料來源現況

MLB Pipeline 官方完整 Top 100 被前端 JS widget 鎖住（文章頁只露前 10、無乾淨 API、
SPA bundle 當下還 404）。**現行 seed 用 Bleacher Report 年度 Top 100**（2023/2024/2025，
完整 1-100）當 pedigree proxy —— 「曾是公認百大新秀」這個訊號 BR 一樣成立。`meta.source`
誠實標注來源。3 月刷新時想換回 MLB Pipeline 就改貼 TSV 即可，引擎/builder 不在意來源。

seed 只含**已登板**球員（FA 掃描才會碰到的人）。未登板新秀進 needs_review、暫不收 ——
代價只有 false negative（漏標），**沒有 false positive**；post-hype tag 只加折價訊號、
不移除任何訊號，所以漏標 = 維持現狀，安全。

## 執行期 API（`prospect_pedigree.py`）

```python
ped = load_pedigree()                       # 讀 prospect_pedigree.json
is_stale(ped, date.today())                 # 全域 stale banner 用
lookup(ped, mlb_id)                          # → {best_rank, best_rank_year, name} | None
post_hype_tag(ped, mlb_id, age, weak_signal, today)   # → "✅ post-hype 新秀 (#R YEAR)" | None
evaluate_post_hype(...)                      # → PostHypeResult（結構化，含 reason / stale）
```

三道 gate：**pedigree**（best_rank ≤ `DEFAULT_RANK_THRESHOLD`=100）× **young**
（age ≤ `DEFAULT_AGE_THRESHOLD`=25）× **weak**（`weak_signal`，由呼叫端給）。
`weak_signal` 是「過往成績差」的代理 —— 引擎刻意不自己算，避免新增 fetch；用
`default_weak_signal(batter_sum)`（season Sum < 20）當預設，門檻可調。

## 尚未接線（follow-up，需 live pipeline session）

post-hype tag 已能產出，但**還沒注入 batter payload**。剩下：

1. **接 fa_compute / fa_scan batter tag 路徑** —— batter payload 目前在 `fa_scan.py`
   直接 dict 組裝、未抽成 slim 函式；需在組裝點呼叫 `post_hype_tag` 並把 mlb_id / age
   （`_fetch_ages_bulk` 已有）/ batter Sum 餵進去。
2. **039 payload_budget 守門** —— `payload_slimmer._ALLOWED_TAGS` 目前只有 SP；
   batter 端要建對應 whitelist 把 post-hype tag 納入。
3. **`weak_signal`「生涯成績門檻」定案** —— 預設用 season Sum<20 proxy，最終門檻
   （是否改看 2026 xwOBA percentile / 是否納入生涯 MLB 成績）建議跟用戶對齊後定。

> 這三項需要跑 live fa_scan 驗證 + 一個設計決策，故與「post-hype 引擎 + 資料資產」分開。
> issue 049 的另一半 **chase / zone-contact delta** 亦未做（需擴充 Savant leaderboard fetch）。
