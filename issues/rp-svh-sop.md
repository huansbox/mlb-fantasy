# Issue: RP-SV+H SOP 落地（取代 fa_scan.py --rp 週掃）

**狀態**：A 機械層（`rp_svh_scan.py`，TDD 44 tests）+ B skill（`/rp-svh`）已實作、code review 修復、merged master、VPS 部署 + e2e 驗證通過（2026-05-19）。8 個開放決策已定案（見「開放決策」段）。**剩**：① 與舊 `--rp` 並行 1-2 週驗證 → ② C1 退役 `fa_scan.py` RP 殘留 → ③ 後續迭代 I1/I2/I4/I5（見末段「後續迭代」）。
**規格依據**：[`docs/rp-svh-metrics.md`](../docs/rp-svh-metrics.md)（SOP 已手動走驗證一輪）。
**背景**：2026-05-19 手動走 RP-SV+H SOP，verdict → add Kevin Kelly。決定將此 SOP
落地為腳本 + skill，取代原本 `fa_scan.py --rp` 週掃。

## 目標

把 `docs/rp-svh-metrics.md` 的 SOP 從手動走變成可重複執行的工具：
- 機械層 → `rp_svh_scan.py`（腳本，比照 `stream_sp_scan.py`）
- LLM 層 → skill（news check + verdict，需 web search，不適合純 cron）
- 退役 `fa_scan.py --rp`

## 現況

`fa_scan.py --rp`：週一 cron，Yahoo RP 查詢 → biweekly SV+H≥2 filter → v2 指標
enrich → 單次 Claude call。FA-first，受 Yahoo AR 排序失準會漏掉真正的角色持有者。

## 工作盤點

### A. 機械層 `rp_svh_scan.py`

| # | 任務 |
|---|------|
| A1 | Step 1 — MLB byDateRange 全聯盟 14d SV+H≥3（floor）。**新寫**：現有 byDateRange code（`mlb_query._default_range_fetch` / `stream_sp_scan`）都是 `group=hitting` 的球隊查詢，本 step 要 `group=pitching` + `playerPool=All` 全聯盟球員排行榜（URL 不同）→ 只能 reuse 呼叫慣例、非函式。**byDateRange split 內含 player id → 留存供 A4/A6/A7 reuse，不另寫 name→id 解析。** |
| A2 | Step 2 — Yahoo FA 交叉（`query_fa --names`）。**`--names` 比對修復**：`_normalize`（`yahoo_query.py:496`）已存在但只用於 Savant CSV 比對；`query_fa` 的 `--names` 在第 277 行是純精確比對。修法 = 套用既有 `_normalize` 到 `query_fa` 比對**兩端**（Yahoo 回傳名 + 傳入名都 normalize），非新寫正規化 |
| A3 | **改共用 fetcher `sp_data_fetchers.fetch_mlb_season_stats` 增 parse `saves` / `holds` / `blownSaves` / `saveOpportunities`** — 目前只 parse g/gs/ip/bb/k/era/whip。規格 doc §B 點名此為「SV+H 評估缺最大、最高投報率」。A7 的 blownSaves+SVO 依賴此 |
| A4 | Step 3 — 三軸 fetch：BB/9（reuse `sp_data_fetchers.fetch_mlb_season_stats`）/ whiff%（reuse `sp_data_fetchers.fetch_savant_arsenal_whiff`）/ 球隊 14d 勝率（**新程式碼** — 現有 `_fetch_team_games` 只抓場次數沒 W-L，需 parse schedule final score 或打 standings endpoint）。mlb_id 取自 A1 |
| A5 | Step 4 — 三軸各自 rank → rank-sum → top-N |
| A6 | Step 5 — incumbent（隊上 SV+H RP，現為 Kelly）同款三軸 + 訊號 fetch，當 benchmark（供 LLM 層情況 A 比較，見規格 doc「要 LLM 輸出」）|
| A7 | Step 6 — 角色訊號 fetch（**僅對 A5 的 top-N 跑，非全候選池** — 避免對 ~23 人全跑 gameLog）：近 10 場 SV/H pattern（gameLog）/ blownSaves+SVO（season，依賴 A3）/ 本週賽程（schedule）|
| A8 | JSON 輸出 + CLI。預期簽名 `python3 rp_svh_scan.py [--floor N] [--top N]`（floor 預設 3、top 預設 4，可覆寫；比照 `stream_sp_scan.py` 慣例）|
| A9 | TDD tests（比照 stream_sp_scan 32 / emerging_batter_scan 40）|

### B. LLM 層 skill

| # | 任務 |
|---|------|
| B1 | skill md — Step 結構：跑腳本 → news check → verdict → 寫回 `waiver-log-rp.md`。**verdict 邏輯見規格 doc「要 LLM 輸出」**（情況 A：best-FA vs incumbent；情況 B：top-N 選 1 / pass）|
| B2 | news check / 決策脈絡 / 判斷規則 / 輸出格式 — 全部見規格 doc「LLM 層輸入設計」段 |

### C. 整合 / 退役

| # | 任務 |
|---|------|
| C1 | **`fa_scan.py --rp` 退役 — 需完整 grep RP 殘留**（下列行號為參考值，以 grep 結果為準），逐一決定移除 vs 保留：`_run_rp_scan`、`RP_QUERIES`、`filter_by_savant` 的 `fa_type=="rp"` 分支（~806-813 行）、`build_roster_for_pass1` 的 rp 分支（~1073 行）、`_fmt_roster_pitcher_rp`（~1335 行）、`_build_rp_data`（~3130 行）、`prompt_fa_scan_rp.txt`、`fa_type=="rp"` 統計（~876/2000 行）、`--rp` CLI flag + dispatch。RP 邏輯散在共用函式內，非「移除一個函式」 |
| C2 | CLAUDE.md：檔案索引加 `rp_svh_scan.py` / `rp-svh-metrics.md` / `waiver-log-rp.md` / 本 issue；賽季運營週表 `--rp` 條目更新；「RP 評估」段改寫（目前寫 v2 指標）|
| C3 | cron / skill 觸發形態決定（見開放決策 5）|
| C4 | 與舊 `--rp` 並行 1-2 週比對再退役（比照 v4 cutover parallel）。需先定義驗收標準：「比對什麼算通過」（例：新 SOP 是否漏掉舊 scan 抓到的人 / verdict 是否合理）|

> 次 session 可決定是否把 A 拆成 TDD increments（A 是主體且可測，建議先做；B skill 後做）。

## 開放決策（2026-05-19 全數定案）

1. **SV+H floor** → **≥3**，CLI `--floor` 可覆寫。機器版可對全池跑 step 3。
2. **機會供給軸** → **30d SV+H 累積**（非團隊勝率、非本週場次數）。3 agent 開放發想後選定：team-level 的勝率/場次數都有重複投票（勝率含 bullpen 表現）或回溯/區辨力問題；30d SV+H 是 player-level、與 BB/9 / whiff% 正交、reuse Step 1 byDateRange call（多一個 30d 窗），且用比 14d floor 更寬的窗口避免與 floor 同源塌成 tie。「球隊製造領先能力」交 LLM 層賽程前瞻兜底。
3. **rank-sum** → **三軸等權**。落地觀察期若某軸預測力明顯較強再改加權。
4. **top-N** → **預設 4**，CLI `--top` 可覆寫；rank-sum 在第 N 名並列時一律納入（硬切點任意性交 LLM 吸收）。
5. **觸發形態** → **純 skill 觸發**，無 cron。LLM 層需 web search（news check）本就不適合 cron；skill 內即時跑 `rp_svh_scan.py`，避開 cron-JSON 時效落差。
6. **`fa_scan.py --rp`** → **完全退役**（不保留機械殼，單人維護不留 dead code）。先與舊 `--rp` 並行 1-2 週驗證，通過後 grep 清除。
7. **incumbent 比較規則** → 「明顯優於」**純交 LLM 自由 reasoning**，不卡 binary 門檻（規格 doc 已定）。
8. **趨勢訊號** → 本期 **out-of-scope**（需改 `fa_history.json` schema 存多期 SV+H），留後續迭代。

> 軸 3 定案後 A4 從「新寫球隊 W-L parse」簡化為「reuse Step 1 byDateRange、改 30d startDate」。

## 不在範圍

- 打者 / SP 的 `fa_scan` 不動
- 維持 2 RP 的數量策略不變；RP 是否擴增是策略題，非本 issue
- **趨勢類訊號（近 2-4 週 SV+H 速率趨勢）本期不做** — 規格 doc 雖列為 layer-1 主訊號，
  但需 `fa_history.json` schema 改動存多期 SV+H，留後續迭代（見開放決策 8）。本期
  Step 1 只取單一 14d 窗

## 建議（給次 session）

- **RP BB/9 百分位表非 prerequisite**：rank-sum 是 pool 內相對排名，不需絕對門檻 →
  原 CLAUDE.md「RP 框架 v4 升級」待辦裡「重跑 RP 百分位」那條對本 SOP 不成立。
- **reuse 區分清楚**：可直接呼叫的現成**函式** = `query_fa`、`sp_data_fetchers.fetch_mlb_season_stats`、
  `sp_data_fetchers.fetch_savant_arsenal_whiff`（注意 `fetch_mlb_season_stats` 在 `roster_sync.py`
  另有同名單人版，務必用 `sp_data_fetchers` 批次版）；**新寫**（只能 reuse API 呼叫慣例）= byDateRange
  `group=pitching` 全聯盟排行（A1）、schedule W-L parse（A4 球隊勝率）。
- **機械層只實作三軸**：規格 doc「排除的指標」段所列（GF / Barrel% / xwOBACON /
  xERA-ERA / 2025 prior）不進機械層，後續 session 勿「順手」把 `sp_data_fetchers`
  既有的 xwOBACON / Barrel% 加回。
- **whiff% caveat**：RP 季中 ~300 球低於 Savant arsenal 基線 ≥500 球。rank-sum 相對
  排序已規避絕對門檻問題，但 LLM 層 profile 顯示 whiff% 時要帶 caveat（規格 doc
  verdict 段已示範 Kelly whiff% caveat）。
- A2 的 `--names` 修復是低風險獨立小修，可先單獨做。
- 開放決策建議在次 session 規劃階段一次定完再開工（尤其決策 2 改 A4 結構）。

## 後續迭代（2026-05-19 `/rp-svh` 首次實測回饋）

A 機械層 + B skill 落地後另一 session 實跑 `/rp-svh` 一輪，提出 5 點優化。
評估後採納 4 項、駁回 1 項。**未實作，留給後續 session**。

### I1 — 對手 W-L 進 JSON（高優先，code + skill）

**問題**：`week_schedule.opponents` 目前只有隊名縮寫。news-check 階段對 top-N + incumbent
各 spawn 一個 agent，prompt 第 3 點要 agent 自己查對手戰績 → 5 個 agent 各跑一次
standings WebSearch 抓同一份 deterministic 資料，浪費且結果可能不一致。

**改法**：機械層加一次 MLB `/standings` call（一次回 30 隊 W-L），把每場對手的
W-L（+ 勝率）附進 `week_schedule.opponents`（縮寫 → `{team, w, l}`）。skill md 的
news-check prompt 第 3 點同步改為「對手戰績已在 JSON，專注判斷打線強弱 / 競爭性」。

**範圍收斂**：只抓 W-L（+ 勝率）。**不做** runs/game（要 per-team byDateRange、多 N 個
call）、wRC+（MLB API 無此欄位）。

> **Guardrail**：對手 W-L 是給 LLM 層賽程前瞻用的 **context，不是新的 rank-sum 軸**。
> 開放決策 2 已明確把球隊強弱排除在 quant 之外、交 LLM 兜底。此改動只是讓「已交給
> LLM 的工作」資料更好，**不可順手做成第 4 軸**。

### I2 — incumbent phantom rank（中優先，code）

**問題**：情況 A 的「明顯優於 incumbent」判斷，incumbent 目前只有 bb9 / whiff_pct /
svh_30d 原始值，無 rank / rank_sum（`in_pool: false`、無 `axes`）。原始值已能
apples-to-apples（bb9 比 bb9），但缺一個 pool-relative 的「incumbent 排第幾」訊號。

**改法**：另算一份 `candidates + incumbent` 的 phantom ranking，只讀 incumbent 的
rank_sum + 各軸 rank + 名次，填進 `incumbent` 輸出。verdict 的「明顯優於」就有
「incumbent 併入池排第 X / N+1」直接對照（排第 1 → 沒人明顯優於 → hold；排第 6 →
top FA 明顯贏）。

**實作 caveat**：phantom ranking 是**另算一份**、只取 incumbent 的名次，**絕不能動到
真正 `top_candidates` 的 rank**（多一個競爭者會讓真候選名次位移）。rank 會壓縮量級 →
incumbent 原始三軸值仍要保留並列。

### I4 — whiff_low_sample 對 RP 結構性恆真（中優先，純文檔）

**問題**：`WHIFF_LOW_SAMPLE_PITCHES=500` 是從 SP 百分位表借來的門檻。RP 季中 arsenal
~300 球幾乎不可能達標 → 首次實測 top-4 + incumbent 5 位全部 `whiff_low_sample: true`。
旗標恆真、對候選間零區辨力，不該被誤讀為個別候選警訊。

**改法**：`docs/rp-svh-metrics.md` 明寫「RP 季中此旗標結構性恆真，whiff% 只作 pool 內
相對排序、絕對值一律打折」。旗標本身不算錯（「絕對值信心低」屬實），不動 code。

### I5 — 機械層耗時提示（低優先，純文檔）

**問題**：SSH 跑 `rp_svh_scan.py` 約 1-2 分鐘（全聯盟 byDateRange ×2 + Yahoo FA 交叉）。
skill md Step 1 未提示時長。

**改法**：skill md Step 1 註明「約 1-2 分鐘，建議 `run_in_background` 起手」。與
`issues/vps-ssh-handshake-hang.md` 獨立 — 無論 SSH 問題修不修都該加。

### I3 — incumbent percent_owned（駁回）

**提議**：candidate 都有 `percent_owned`，incumbent 沒有，補上湊齊對照表。

**駁回理由**：incumbent 是我方已 rostered 球員，FA pool query 涵蓋不到它 → 要另開
一次 Yahoo `player_keys` call 才拿得到。而「一個已被我撿走的球員」的全聯盟持有率對
swap/hold 決策幾乎零資訊量。為一個裝飾性表格欄位多打一次 API，不值得。

### 實作順序建議

- **先做 I4 + I5**（純文檔、零風險、可獨立）。
- **I1 + I2 動 `rp_svh_scan.py`**，需配 TDD test（比照現有 44 cases 慣例）。I1 高優先。
