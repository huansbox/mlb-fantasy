# 318b payload 注入設計定稿

> 2026-06-15 grill-me 六題對齊定稿。父 PRD `issues/prd-decision-execution.md`（GitHub #316），子 issue #318（039 ledger 消費端 + payload_budget）。
>
> 背景：PRD #316 的量修復鏈與 micro-fields 模組（044-050）已全部建好、測過、merge 進 master，但**輸出尚未接進實際送 LLM 的 payload** — 全擱在架上。318b 是唯一匯流點：把這些模組 + ledger 記憶注入 batter/SP payload，受 `payload_budget`（≤3 行/候選，gate 已 merge `8be035b`）守門。本文釘死注入的存在性、預算語意、切批順序、A/B 隔離與 backfill 範圍。

## 為什麼需要這份對齊

318b 不能一句話描述完整 diff，兩個真實缺口逼出設計討論：

1. **行數裝不下、讓位規則 PRD 未定**：光 ledger 的 prev-verdict + add-reason + star 就三行吃滿 ≤3，platoon/PA/swap/micro-field 往哪擠，PRD 只說「新行讓既有行讓位」沒寫優先序。
2. **成本回潮是 lever-2 地雷正中央**：注入多行 + 042 prompt 改動極可能誘發 billed thinking（記憶 `feedback_claude_p_thinking_induction`：output 6.7K→18-19K、cost +68%）。歸因方案不先定，爆了只能整批 revert。

## 六個決策（含 rationale）

### Q1 — star 不注入 batter payload

issue #318 comment 原寫「注入 prev-verdict / add-reason / **star** 三行」。**star 拿掉**。

- batter v4 thin 鐵律：機械層「不算 urgency / 不打 tag / 不預判 decision，Sum 不暴露給 LLM」，理由就是避免機械總分錨定 LLM。star（1-5★）正是機械總分。
- 040/041 的設計位置是 **star 在 pre-LLM 算（payload 預篩依據）、041 gate 在 post-LLM 用（行動分級）** — star 從不是 LLM 的 reasoning 輸入。注入它 = 走回 v2「Sum 暴露給 LLM」那條 2026-04-28 被廢掉的老路。
- ledger 只注入 **prev-verdict + add-reason 兩行**：這是「系統對球員的記憶」（上次判什麼、當初為何撿），是事實脈絡不是判斷框架。star 留 pre-LLM 預篩 + 041 gate + 051 KPI。

### Q2 — 「≤3 新行」只數真正多出來的整行；tag 擠既有行算 0

- 算新行（`register(slice, n)`）：ledger prev-verdict（1）+ ledger add-reason（1）+ PA 投影（1）= 填滿基礎 ≤3。
- 不算新行（`register(slice, 0)`，併既有行）：platoon tag → 併「產量」行；chase/zone delta → 併「品質」或「2025」行；post-hype tag → 併 header。
- **token ≠ 行**：tag 擠行雖「行數 0」仍加 token、仍可能誘發 thinking。`payload_budget` 守的是「視覺行數別爆版」；**真正的成本閘門是 A/B 量到的 token delta**。兩個關卡分開 — 行數沒爆 ≠ 成本沒漲。

### Q3 — swap 差額表（4★+ only）走獨立 pool + 單行緊湊式

- **預算歸屬**：swap 表走**獨立 `PayloadBudget` 實例**（multi-instance 記帳，當初設計 multi-pool 就是為此）。4★+ 是真正該行動的候選，回溯 2.5 個月只 ~6 次，極稀有 — 對這批放寬預算、攤開類別交換是資訊密度該花的地方，不跟日常觀察級候選搶基礎 ≤3。
- **格式**：單行緊湊式（7 類別 + PA delta 壓一行），非 markdown 多行表格 — lever-2 風險是 token 驅動，單行省排版 token 不犧牲資訊完整性。
- **模組層已實作**：`swap_batter.format_swap_line(drop, add, vec)` 已回 `swap {drop}→{add}/week: R +2, HR +1, ..., PA -7`；`should_emit_swap(stars)` gate 在 `MIN_STARS_TO_EMIT=4`。318b 只需呼叫，不需重寫格式。

### Q4 — batter 注入先、SP 注入後，分兩批

兩端注入機制根本不同：
- **batter payload = 縮排文字行**（`_format_fa_batter` 一路 `lines.append`）→ 注入 = 加/改 append 的行。
- **SP payload = 結構化 JSON dict**（`payload_slimmer.slim_entry` 回 dict）→ 注入 = 改 dict 欄位，獨立工程。

batter 先的四個理由：成本大頭在 batter（call ~$0.49 / payload 35K，lever-2 也在 batter 量到）→ 風險最大處先試先驗 A/B 方法論；batter 引擎全 ready（049 #333/#334 + 044/045/047 全 merge）；SP 是 JSON 注入混同批會讓 token 歸因糾纏；一次只動一端 token delta 才歸因得乾淨。

→ 原 318b 一批拆成 **318b-batter** + **318b-sp**。

### Q5 — 三段分離：注入裸上 → 量 → 視數據才上 042

board 原寫「318b 與 042 同批」。改三段：

1. **batter 注入裸上**（payload 多 ledger 2 行 + PA 1 行 + tag 擠行，**prompt 完全不動**）→ A/B 量 input/output token。預期只增 input、不太誘發 thinking。
2. 步驟 1 成本可接受 → **再上 042 prompt** → 再量。若 output token 這時才暴增，明確歸因 prompt，可單獨 revert prompt 保留注入。
3. 確認後 → **318b-sp 注入**另批。

042 是 lever-2 風險正主（「翻供須指認變因 / drop 須回應原 add 理由」= 要 LLM 逐項比對+決策的指令型）。**bonus：步驟 1 本身是 042 的對照組** — LLM 光看到「當初撿他因為 14d OPS 火燙」這行，很可能 reasoning 時就自己面對了，不需 prompt 強制。先用數據驗「給資訊」夠不夠，再決定要不要花「強制比對」的 thinking 成本。

→ **042（#321）從「必做」降為「條件性」**：步驟 1 數據決定它做不做。

### Q6 — legacy backfill：前置獨立跑 / 只當下存量 / roster 快照加標註

- **(a) 時機**：backfill 是**獨立前置腳本，注入上線前跑完**（否則 ledger 空、注入行全空白）。一次性、idempotent、跑完驗收再上注入。
- **(b) 範圍**：只回填**當下存量**（active roster + active watchlist）。已結案歷史球員不回填 — 沒有未來決策會讀它們的 ledger。
- **(c) roster add-reason 真實性**（PRD 未寫、本次新增）：PRD 說 roster 球員用「上線日季線快照」充 add 理由，但這不是真實撿人動機 — 對今天 slump 的球員會寫成「當初撿他因為 xwOBA .280（爛）」的**假歷史**，之後 drop 決策面對假理由會被誤導。快照行明確標 `[backfill：上線日季線，非真實 add 理由]`。PRD 驗收只要「不缺 add 理由」沒要求真實，標註零成本防假歷史。

## 注入點實作骨架

### batter 注入（`_format_fa_batter`，fa_scan.py L1117-1190）

每候選現約 6-8 行：header / 品質 / 輔助 / 產量 / Yahoo / bbe / 14d / 2025。注入改動：

```
基礎 pool（PayloadBudget(max_lines=3)，每候選 new 一個）：
  ledger = DecisionLedger(path).get_history(name)
  if ledger 有歷史:
      prev = ledger[-1]                      # 最近一筆 LedgerEntry
      lines.append(f"    上次: {prev.verdict}（{days_ago(prev.ts)} 天前）")   # register("ledger_prev", 1)
      first_add = 最早帶 add_reason 的 entry
      if first_add: lines.append(f"    當初撿: {first_add.add_reason}")        # register("ledger_add", 1)
  pa_proj = weekly_projection.project(rates, projected_volume)
  lines.append(f"    投影: 下週 PA ~{pa}")                                      # register("pa_proj", 1)

  tag 擠既有行（register 0）：
    platoon → classify_platoon(games)["label"] 接到「產量」行尾
    chase/zone → batter_discipline.discipline_tag(result) 接「品質」或「2025」行尾
    post-hype → prospect_pedigree.post_hype_tag(...) 接 header 行尾

  base_budget.assert_within(name)   # 超 3 行 raise，try/except 包覆（best-effort，never abort）

swap pool（獨立 PayloadBudget 實例）：
  if swap_batter.should_emit_swap(stars):    # stars 來自 pre-LLM 機械算（不注入，只 gate）
      vec = swap_vector_batter(cand_cats, cand_pa, inc_cats, inc_pa)
      lines.append("    " + format_swap_line(drop_name, name, vec))   # 獨立 pool register
```

首次接觸候選無 ledger 歷史 → 0 注入行，預算更鬆。

### payload_budget 兩 pool

`payload_budget.PayloadBudget` 已 merge（`8be035b`）。每候選組裝時 new 兩個實例：基礎 pool `max_lines=3`、swap pool 獨立 ceiling（單行 = 1，留參數化）。生產路徑（fa_scan cron）以 try/except 包 `assert_within`，比照既有 ledger best-effort 慣例（守門失敗 never abort waiver-log write）。

### backfill 腳本流程（前置一次性）

```
for 球員 in (active roster + active watchlist):
    if 在 watchlist:
        channel = parse waiver-log.md 歷史段 + git log 觸發文字 → classify_channel / unknown
        ledger.record(球員, verdict=當前, channel=channel, ...)
    if 在 roster:
        snapshot = 上線日季線（xwOBA/BB%/Barrel% percentile 摘要）
        ledger.record(球員, add_reason=f"[backfill：上線日季線，非真實 add 理由] {snapshot}", ...)
驗收（機器可判）：無「缺 add 理由」的 roster 球員、無「缺 channel」的 watchlist 條目。
```

## 三段 A/B 量測契約

沿用 lever-2 / 037 的**真實 payload 配對 A/B**（取真實一天 batter payload，跑改前 vs 改後兩版比 token）：

| 段 | 改動 | 量什麼 | 通過條件 |
|---|---|---|---|
| ① 注入裸上 | payload 加注入行 + tag，prompt 不動 | input + output token delta | input 漲在預期內、output 不暴增（無 thinking 誘發） |
| ② 042 prompt | 加「翻供指認變因 / drop 回應 add 理由」 | output token delta vs ① | 若暴增 → 歸因 prompt、可單獨 revert；① 已有效則 042 可不做 |
| ③ 318b-sp 注入 | SP dict 加欄位 | SP call token delta | 獨立量、不與 batter 混 |

每段上線前後都記錄 payload input/output token（user story 19）。

## 拆 slice 清單與順序

1. **318b-batter 注入 + backfill 前置**（先做，AFK）：backfill 腳本 → batter `_format_fa_batter` 注入 → 基礎 + swap 兩 pool register → 段① A/B。
2. **042 prompt 契約**（#321，HITL，**條件性**）：段① 數據決定做不做；做則配對 A/B + 人工審。
3. **318b-sp 注入**（延後，AFK）：`payload_slimmer.slim_entry` dict 注入 046/048/050 → 段③ A/B。

## 尚待決定的實作細節（design doc 不卡、實作時定）

- PA 投影行給誰：FA 候選 + 我方最弱錨點都給，還是只 FA？（傾向都給，量感知是普遍價值）
- swap pool ceiling 參數值（單行 = 1，未來若多行再調）。
- prev-verdict 行的「N 天前」用 `get_history` entry.ts 與 today 差；同組 verdict 相鄰日是否去重顯示。
- backfill 的 watchlist channel parse 失敗率 — unknown 比例若過高需回頭補 git log 觸發文字解析。
