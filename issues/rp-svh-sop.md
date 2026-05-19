# Issue: RP-SV+H SOP 落地（取代 fa_scan.py --rp 週掃）

**狀態**：規劃中（2026-05-19 建立，同日經 agent 審查修訂）。實作留待後續 session。
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

## 開放決策（實作前需定）

1. **SV+H floor**：≥3 vs ≥4（≥3 不漏剛沉寂 closer 但留太多人；≥4 較準有 lumpiness 風險）
2. **機會供給軸**：團隊 14d 勝率（手動走用，最吵）vs 前瞻本週場次數（Agent 3 原選，前瞻、可精確讀）vs 並用 —— **會改 A4 結構，建議最先定**
3. **rank-sum**：三軸等權 vs 加權
4. **top-N 的 N**（手動走用 4）
5. **觸發形態**：cron 跑機械層 + 手動 skill 跑 LLM 層 vs 全 skill 觸發。**附考量**：若 cron 產 JSON、skill 後讀，JSON 有**時效問題**（cron 凌晨跑、使用者下午開 skill，中間有新賽果）— `stream_sp_scan` 採純 skill 觸發正因如此
6. **`fa_scan.py --rp`**：完全退役 vs 保留機械殼
7. **incumbent 比較規則**（agent 審查新增）：規格 doc 已補 verdict 框架（情況 A best-FA vs incumbent、預設 hold），但「明顯優於」的判準細則 — 純交 LLM reasoning vs 給量化提示 — 待定
8. **趨勢訊號做不做**（agent 審查新增）：規格 doc 把「近 2-4 週 SV+H 速率趨勢」列為 layer-1 主訊號，需改 `fa_history.json` schema 存多期 SV+H。本期暫 out-of-scope（見不在範圍），是否納入後續迭代待定

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
