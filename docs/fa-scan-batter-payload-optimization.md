# fa_scan Batter payload 優化 — 探索定稿

> 2026-06-10 探索 session 產出。延續 `issues/prd-claude-p-cost-simplification.md` Phase 1.5（lever 1a 已 deploy、lever 2 已放棄）後的 batter 端成本探索。
> 結論先行：**batter call 的成本問題不在 prompt、不在輸出格式，而在 payload 裡的 waiver-log 觀察歷史段 — 佔 72.4% 且只進不出、每日複利成長。**

## 成本解剖（現狀，lever 1a 後）

batter 每日 1 call（TW 12:30 cron），實測 $0.43–0.49/call ≈ **$14/月**：

| 項目 | 數值 | 備註 |
|---|---:|---|
| input 總計 | ~52K tok（$0.33）| cache_create rate $6.25/1M |
| — harness 固定開銷 | ~15.9K | 1a 已砍 CLAUDE.md 22.5K，不可再砍 |
| — prompt 模板 | ~1.5K | 可忽略 |
| — payload | ~35K | **唯一可操作的 input 槓桿** |
| output | 6.7–9K tok（$0.17–0.23）| lever 2 已證實不可用 prompt 規則收斂 |

## Payload 解剖（issue #303，2026-06-09，48.3K chars）

| 區塊 | 大小 | 佔比 |
|---|---:|---:|
| 我方候選 drop（7 人）| 2.6K | 5.4% |
| FA 候選（10 人）| 3.8K | 7.9% |
| 觀察中球員當日數據 stat blocks（18 人）| 6.5K | 13.5% |
| %owned 升幅 | 0.3K | 0.6% |
| **waiver-log 觀察歷史全文** | **35K** | **72.4%** |

歷史段的結構性問題：

1. **只進不出**：18 位觀察球員平均 20+ 行每日記錄（最多 31 行），git 歷史顯示每日淨增 15–20 行；唯一自動移除途徑是 auto-close rostered（被任一隊 roster）。LLM 連續 7+ 天對同樣 6 人輸出「建議結案」，但建議沒有接到任何執行機制。
2. **資料重複**：觀察球員出現兩次 — 當日數據 stat block（新算的）+ 歷史段最後一行（昨天的同樣數字）。
3. **「隊上觀察」段意外夾帶**：`_filter_waiver_log_by_group` 取「## 觀察中」到「## 已結案」之間全部內容，「## 隊上觀察」剛好坐在中間 → 自家球員觀察（含已離隊球員的 stale 條目）一併進 payload（batter 條目進 batter payload、SP 條目進 SP payload）。

## 品質檢視發現（過去產出抽查）

整體品質好（slump vs 結構弱區辨、IL gate 遵守、PASS 段簡潔），但有三類可機械修復的誤差：

| 問題 | 實例 | 根因 |
|---|---|---|
| **counter 誤數** | 06-08 把 Duran 14d OPS .782 寫成「破 .750 day 2/3」，06-09 才自我修正重置 | LLM 從 30 行歷史自行數「連 N 天」，既花 token 又不可靠 |
| **%owned 誤讀** | Basallo 57% 被推理成「幾乎不可能是直接 FA」 | %owned 是 Yahoo 全平台值非本聯盟，prompt 未說明 |
| **14d Savant 無 gate** | Teoscar BBE 3 / Δ+0.111 直接印出 | `_format_fa_batter` 有 BBE≥25 gate，但實際使用的 `_fmt_fa_block_batter_v4` 沒有 |

另發現死碼島（無 caller，順手清）：`build_weekly_data` / `_extract_eval_framework` / `_format_fa_batter` / `_format_fa_pitcher`。

## A/B 實測（2026-06-10，本機配對）

方法：#303 真實 payload；**截斷規則 = 每條觀察保留觸發條件 + `[eval]` 里程碑行 + 最近 5 天**，其餘以一行「中略 N 行」標記。同機、同 model（claude-opus-4-6）、同 prompt、neutral cwd 配對跑。

| | A 原始 | B 截斷 | Δ |
|---|---:|---:|---|
| payload | 48.3K chars | 26.2K chars | **−45.9%** |
| input tokens | 71,135 | 55,271 | −15.9K（−22%）|
| output tokens | 29,608 | 25,512 | −14% |
| cost | $1.185 | $0.983 | **−17%** |
| 時長 | 597s | 510s | −15% |

決策一致性：P1 drop（Arraez）相同、頂部 ACTION（Pederson 立即取代）相同、6 筆結案建議兩邊都齊。P2/P3 互換屬 run-to-run 變異（production vs A 也互換）。

**邊際代價**：Cam Smith 兩邊都判「取代」，但 A 保留「Duran 計數器今日重置 day 0/3」的觸發紀律，B 直接建議 7 日內執行 — **截斷會輕微弱化依賴長歷史推導的觸發紀律**。緩解：機械層在截斷時補一行 derived 摘要（如「已連續建議結案 N 天」「counter 目前 day X/N」）。

Caveat：本機 harness 比 VPS 肥（user CLAUDE.md + MCP tool defs → input 71K vs VPS 52K；CLI thinking → output 25–30K vs VPS 6.7–9K），**絕對值不可比、配對 Δ 有效**。換算 VPS：input 省 15.9K ≈ −$0.10/call ≈ **−$3/月**。

## 建議優先序與落地狀態

| # | 行動 | 成本 | 效益 | 狀態 |
|---|---|---|---|---|
| 1 | **執行結案 backlog**（6 筆觀察中 + 隊上觀察 stale 條目）+ 把「建議結案 backlog 執行」納入 `/weekly-review` Phase 1C | 零 code | payload 歷史段立即 −~40%，停掉每日重複結案輸出 | ✅ 2026-06-10 |
| 2 | **建議結案自動化**：LLM 連 N 天（建議 3）輸出建議結案 → 機械移到已結案（仿 auto-close rostered 模式），或 Telegram 提醒 | 中 code | 治本「只進不出」 | ⏳ |
| 3 | **payload 讀取端歷史截斷**（waiver-log.md 檔案不動，只動 `_filter_waiver_log_by_group` 下游）：觸發 + [eval] + 最近 5 天 + 機械 counter 摘要行 | ~20–30 行 Python，零 prompt 變動 | −$3/月 + cap 複利成長 + 降低 counter 誤數；**純機械裁切，無 lever 2 的 thinking induction 風險** | ⏳ |
| 4 | hygiene 小修：14d Savant BBE <15 不顯示或標註；prompt 加一行「%owned 為 Yahoo 全平台值，非本聯盟」（靜態資料字典說明，不誘發 thinking） | 極小 | 消除兩類已觀察誤讀 | ⏳ |
| 5 | **model 降級 Sonnet**：batter 決策低風險可逆（FA add $0 即時、waiver-log 留痕），比 SP 更適合先試；配對 A/B 驗證一週 | 一行 `--model` + A/B | **最大單一槓桿 −40%（$14→$8.4/月）** | Phase 2（PRD Out of Scope，batter 先試）|

## 不做的事

- **頻率降低（隔日掃）**：觸發條件大量依賴「連 N 天」每日 cadence，省 ~$7/月但破壞 watch 機制設計。
- **輸出格式收斂**：lever 2 已實證 backfire（skip 規則誘發 ~12K thinking、cost +68%），不再碰。
- **我方 drop 池縮減（7→4）**：P5–P7 的 hold 判斷 load-bearing（Torres slump 區辨發生在 P5），省幅小。

## 中期選項（未排程）

**觸發條件結構化（DSL）**：counter 由 Python 數、LLM 只負責設定/變更觸發條件。同時解決誤數問題，並為「無事件日跳過 LLM call」鋪路。與 emerging-batter pending 機制（`docs/emerging-batter-design.md`）同族，若 batter 端做 Phase 6 升級時一併考慮。

## 尚待決定

- 建議 2 的 N（連續建議結案天數門檻）：3 天 vs 5 天 — 3 天較積極，誤關可重開（NEW 行成本低）。
- 建議 3 截斷參數：最近 5 天是 A/B 驗證值；[eval] 行無條件保留；機械 counter 摘要行的格式。
- 建議 3 與建議 2 的先後：先做 2（治本）再看 3 是否仍需要 — 若 watch list 穩態縮到 ~8 人，3 的省幅減半。
