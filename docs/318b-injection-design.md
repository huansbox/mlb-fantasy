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

## 段① 實測結果（2026-06-18，VPS 配對 A/B）

PR #351（318b-batter）merge（`9449fa2`）+ VPS deploy 後，VPS production code 跑出注入後 batter payload，反注入得**同 13 候選**的 clean 版（零候選池 noise，優於跨天 production issue 配對），VPS neutral cwd 各跑 `claude -p --output-format json` ×2（A=clean 無注入 / B=injected 有注入，同一個未動的 batter prompt）：

| | input（cache_read+creation）| output_tokens | duration | cost（rep0 可比）|
|---|---|---|---|---|
| A_clean（無注入）| ~33.6–34.1K | 8,131 / 9,189（avg **8,660**）| ~184s | $0.351 |
| B_injected（注入）| 34.8K | 7,231 / 7,105（avg **7,168**）| ~155s | $0.336 |

**注入內容**（這批 13 FA + 我方 P1–P7）：ledger 22 行（791 chars）+ chase/zone tag 10 個（272 chars）= **1,063 chars（+5.2% payload）**。platoon / PA 投影 / swap 因無 actionable（取代）候選**未觸發**（設計意圖，稀有條件性注入，swap 走獨立 pool）；post-hype 無命中。

**通過判定 — 段① 乾淨通過**：
- ✅ **input 漲在預期內**：B−A ≈ **+1,029 tokens（+3.0%）**，精確對應注入 1,063 chars。
- ✅✅ **output 無 thinking 誘發**：B（注入）7,168 vs A（無注入）8,660，**反低 17%**。對比 lever-2 backfire（output ~3× 暴增）完全相反；cost rep0 B $0.336 < A $0.351，注入裸上零成本甚至略省。

**對照組效果（決定 042）**：
- **chase/zone 事實型 tag：LLM 自發使用** — B output 直接引用「Joc Pederson zone-contact -4.4 接觸降」，waiver-log UPDATE 也寫入 chase/zone tag（Manzardo/Heriberto chase崩壞）。給資訊即用，**不需 042 強制**。
- **ledger prev-verdict / add-reason：本批無有效驗證場景** — 有 ledger 的候選（Curtis Mead / Joc Pederson）judgment 未回溯「上次/原撿因」，但此批是弱樣本：① prev-verdict 全「0 天前 watch」無變化可指認；② add_reason 是季線快照（backfill B7 未跑 = 假理由，忽略反而合理）；③ 無翻供案例。042 兩規則本批皆無觸發場景。

**fetcher VPS endpoint 確認**（B6 SP 注入參照）：
- ✅ discipline bulk CSV + ledger fetcher：成功（payload_b 有對應注入，整次跑**無一條 best-effort skip 警告**）。注入鏈在 VPS production 環境跑通、never abort scan，B6 SP dict 注入可比照此 best-effort 模式。
- ⏳ platoon games / future-games（PA 投影）fetcher：此批無 actionable 候選未觸發，endpoint shape 未驗 → 待後續有 actionable 候選的掃描日，或 B6 前單獨 smoke test 補驗。

**042 決策 → 暫緩**（從「條件性」降為「backfill B7 + 真實翻供/drop 案例成熟後再評估」）：
- 段① 證實「給資訊」對事實型 tag（chase/zone）已生效（Q5「步驟 1 是 042 對照組」假設在 tag 層面成立）；ledger 規則的增益未被本批證實，而 042 是 lever-2 風險正主（加判斷規則誘發 thinking）。價值未證實 + 風險已知 → 不值得現在做。
- 042 的「drop 面對原 add 理由」邏輯上 **blocked by backfill B7**（現 add_reason 是季線快照假理由，強制面對會誤導）。
- 結論：**注入裸上保留（已 production），042 不上**。重評觸發 = backfill B7 跑完 + 出現真實翻供（verdict 改變）或 drop 回溯案例。

## 段③ 實測結果（2026-07-08，VPS 配對 A/B）

B6 merge（`7ecdfd1`）+ VPS deploy 後，取首批注入的 production capture fixture（`_tools/fixtures/b1_baseline/2026-07-08_sp_b2_{step_a,step_b}.json`）作 B（injected）；反注入剝掉 B6 欄位（`_inject_318b` + `_rolling_payload` 權威清單：ledger_note / next_week_starts / velo / kbb_small_sample / swap_vs_incumbent + rolling_21d.csw_pct/pitches + velo-prefix tags）得**同批候選**的 A（clean），零候選池 noise。VPS neutral cwd 各跑 unchanged Step A/B prompt × `claude -p --output-format json` × 2 reps（runner `_tools/_ab_318b_sp_runner.py`）。主 model = **claude-opus-4-8[1m]**（modelUsage 另有 ~$0.008 Haiku 輔助 call = claude -p harness 開銷，非主推理）。

| variant | input（tot）| output_tokens（2 reps）| cost rep0 |
|---|---|---|---|
| step_a clean | 28,050 | [7574, 7322] avg **7448** | $0.317 |
| step_a inj | 30,295（+8.0%）| [4547, 5066] avg **4806（−35.5%）** | $0.249 |
| step_b clean | 28,211 | [1366, 2479] avg **1922** | $0.147 |
| step_b inj | 30,456（+8.0%）| [3170, 5655] avg **4412（+129.5%）** | $0.216 |

**通過判定 — 段③ 通過（成本淨中性）**：
- ✅ **input 漲小**：+2,245 tok/step（+8.0%），A+B 共 **+4,490 tok**。注入 payload char +4,771/step（+25% payload body）看似大，但 token 只 +8%（JSON ~2 chars/tok + 28K base 含固定 Opus system prompt）；**char 量嚇人、token 量溫和**。最大宗 = 046 next_week_starts cadence dict（11 候選全帶，含 dates array）。
- ✅ **output 淨持平、無 lever-2 誘發**：net A+B output avg **−152 tok**（噪音內）。注入把 output 在兩步間**重分配** — Step A **−35.5%**（richer data → 排序更果斷、Opus thinking 少）、Step B **+129.5%**（final verdict 多料可衡量 → thinking 多）；兩步方向各自 robust（2 reps 不重疊）、淨相抵。與 lever-2「prompt 改動致 output 單調 3× 暴增 + 可見文字持平」本質不同：B6 **未動 prompt**、淨 output 平、可見 verdict 文字穩定（~500-1500 chars）。
- ✅ **成本中性**：每 scan（A+B）clean $0.463 → inj $0.466（**+0.5%、~$0.002**）。

**特徵記錄（非 fail，供未來注入片參照）**：
- SP 路徑 output_tokens 由 **Opus thinking 主導**（可見 result ~400-500 tok vs output_tokens 1366-7574）— 既有 production 特性、非注入造成；注入只在此基礎上重分配 thinking。
- Opus thinking 單 call 變異大（Step B clean 1366-2479 / inj 3170-5655）；2 reps 足判每步方向與淨中性，絕對量勿過度解讀。
- 若未來要壓 SP payload token，先精簡 next_week_starts 的 dates array（char/token 大宗）。

## 拆 slice 清單與順序

1. **318b-batter 注入**（✅ merge PR #351 `9449fa2` + VPS deploy + 段① A/B 通過，2026-06-18）：batter pass2 注入 → 基礎 + swap 兩 pool register → 段① A/B。backfill（B7）改拆第二批，故段① 跑時 ledger add_reason 多為空/季線快照（見「段① 實測結果」）。
2. **042 prompt 契約**（#321，HITL，**暫緩**）：段① 數據已出 — 注入裸上零誘發、事實型 tag LLM 自發使用，但 ledger 規則增益未證實 + drop 規則 blocked by backfill B7 → **042 不上**。重評觸發：B7 已跑完（2026-07-07 ✓），仍待真實翻供（verdict 改變）或 drop 回溯案例出現。
3. **318b-sp 注入**（B6，✅ merge `7ecdfd1`，2026-07-07）：`slim_entry` dict 注入 — 046 `next_week_starts`（probable 錨定 cadence 投影，retro gate 85.3% production config / 85.0% 日曆協議，2354 cells；窗口 = 明天 ET 起算的當週剩餘，staleness 用球隊比賽日免疫 All-Star break，horizon-absence per-team）+ 050 micro（CSW 21d 騎 rolling dict 0 行 — season CSW 經驗證不可得；velo 21d/YoY delta + prefix 白名單 tag；K-BB ladder BBE<30 only）+ ledger 記憶 2 行 + 048 swap line（4★+ 獨立 pool）。SP 端 channel/stars wiring（318a SP mirror）同批 — SP 條目今後自動有 channel。prompt 未動。**段③ A/B ✅ 通過（2026-07-08）**：input +8.0%/step（+4,490 tok/scan）、output 淨 −152 tok（Step A −35.5% / Step B +129.5% 重分配相抵）、成本 +0.5%（~$0.002/scan）、無 lever-2 誘發。詳見上方「段③ 實測結果」。
4. **legacy backfill**（B7，✅ 已執行，2026-07-07）：`daily-advisor/backfill_ledger.py`（26 tests）實跑 22 筆 — roster 20 人 tagged 季線快照 add_reason（batter 3 核心 / SP 5-slot）+ SP watchlist 2 人 channel（Gasser heat / Holmes structure，文字回推 classifier：structure > heat > market > unknown，含 SP slot-name 規則）。驗收通過：roster 23/23 有 add_reason、watchlist 11/11 有 channel；再跑 plan 0 筆（冪等）。

## 尚待決定的實作細節（design doc 不卡、實作時定）

- PA 投影行給誰：FA 候選 + 我方最弱錨點都給，還是只 FA？（傾向都給，量感知是普遍價值）
- swap pool ceiling 參數值（單行 = 1，未來若多行再調）。
- prev-verdict 行的「N 天前」用 `get_history` entry.ts 與 today 差；同組 verdict 相鄰日是否去重顯示。
- backfill 的 watchlist channel parse 失敗率 — unknown 比例若過高需回頭補 git log 觸發文字解析。
