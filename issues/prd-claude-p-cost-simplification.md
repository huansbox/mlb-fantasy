# PRD: claude -p 成本簡化（必要性砍除 pass）

> grill-me session 2026-06-05 對齊。背景觸發：Anthropic 6/15 programmatic credit pool 改動。
> 本 pass = **必要性砍除，不動 model**。model 降級為 Phase 2（見 Out of Scope）。

## 進度

- ✅ **2026-06-05 — `--rp` 退役完成**（Solution 1 + C1 死碼清除）：branch `refactor/retire-fa-scan-rp`。移除 VPS cron「FA Scan RP」stanza（止血，下週一起不跑）+ `fa_scan.py` RP 殘碼（`_run_rp_scan` / `RP_QUERIES` / `_build_rp_data` / `build_roster_for_pass1` / `--rp` flag）+ 連帶浮現的既有死碼島（`build_roster_summary` 等 roster-summary display helpers，grep 證實 0 live caller）+ 刪 `prompt_fa_scan_rp.txt` + 文檔同步（CLAUDE.md / README / architecture）。共用 `_classify_fa_type` / `_format_fa_pitcher` rp 分支保留（每日掃描仍用來排除 RP）。code review 通過。
- ✅ **2026-06-06 — 日報 2 合 1 程式碼完成（Solution 2）**：branch `refactor/claude-p-cost-cut`（commit `1e93880`）。`daily_advisor.py` 去 `--morning` 二分 + 刪 Section 7 / `fetch_evening_advice()` + issue tag 統一為 `[日報]`；`prompt_template.txt` 兩份合併為單一 **adaptive** prompt（有實際打序用打序 / 無則 probable matchup），砍到 2 區塊（Lineup 異動 + SP 確認），移除注意事項 / 投打衝突 / 速報修正 / SP 排程備查；刪 `prompt_template_morning.txt`；`weekly_review.py` 註解一致性（**無行為改變** — 它靠 `week-N` label + 日期 token 篩 issue，不 match tag 字串）。意外收穫：lineup adaptive 本就不由 `--morning` 驅動（`fetch_lineups()` 無條件呼叫），合併比 PRD 預想乾淨。**VPS worktree 隔離驗證兩情境通過**（未來日期=無 lineup 走 probable / 今日=有 lineup 走實際打序 + 引用打序訊號），production checkout 未污染。
  - ⚠️ **發現 — S2 與 S3 在 VPS 是「綁定 deploy」**：S2 一旦進 master，舊 cron 的 `--morning` 行（05:00 最終報）會因 argparse 不認 `--morning` 而失敗 → **S2 不可單獨 merge master，必須與 S3 cron 改動（刪舊 2 行 22:15/05:00 + 新增平日/假日行）在同一次 VPS deploy 一起上**。文檔時間表（README:32/54-55 / architecture.md:11-14 / CLAUDE.md 每日 SOP 表）也因此整批留 S3，等 cron 分鐘定案後一次寫對。
- ✅ **2026-06-06 — S3 排程平日/假日分流 + 文檔時間表（程式碼/文檔完成）**：cron 行定稿 — 平日晚報 `30 21 * * 1-5`（TW 05:30 / ET Mon–Fri 夜場，趕 TW 06:34 最早鎖前）+ 假日早報 `30 14 * * 6,0`（TW 22:30 / ET Sat–Sun 日場，趕 TW 00:15 最早鎖前）。兩條 cron 的 UTC day-of-week 剛好 = ET 比賽日（平日報落 ET 同日傍晚 / 假日報落 ET 同日上午，皆未跨 UTC 午夜，無跨日界線陷阱）。日報 log 統一 `daily-advisor.log`。文檔時間表整批更新（README:32/54-55 / architecture.md:11-14 / CLAUDE.md 每日 SOP 表 + 檔案索引）。caveat（US 10）：平日 getaway day（~17%，TW 01:00 鎖）會被晚報漏掉，接受不補偵測。VPS deploy 見下條。
- ✅ **2026-06-06 — S2+S3 merge master + VPS deploy 完成**：merge commit `51bab0c` push origin master。VPS deploy 順序（避開 `--morning` argparse error 窗口）= 先 patch cron（失敗安全逐行 python，base64 經 vps-run 傳，備份 `/etc/cron.d/daily-advisor.bak`）→ 再 git pull ff 到 `51bab0c`；patch 先做使中間態為「新 cron 跑舊 code 無 flag」（無 error）。cron 落地確認：平日 `30 21 * * 1-5` + 假日 `30 14 * * 6,0`，舊 22:15/05:00 兩行已移除、其餘 6 段完整保留。dry-run 驗證新 code 無 `--morning` argparse 錯 + adaptive lineup「未公布」分支正常 fetch。**首班假日早報 14:30 UTC（TW 22:30）= deploy 後第一次真實 cron 觸發，待觀察**（Telegram 推送 + GitHub issue tag `[日報]`）。
- ⏳ **待處理**：US 13 記憶更正 — store 已定位在 **mac file-memory**（`project_claude_p_subscription`；Windows file-memory + cccmemory MCP 皆查無）。本機 Windows 已新建正確記憶 `project_claude_p_credit_pool`（6/15 改制事實），**剩 mac session 刪除/更正舊錯誤記憶**。Phase 2 model 降級（Out of Scope）。
- ⏳ **Phase 1.5（2026-06-08）— fa_scan prompt 簡化：槓桿 1a（CLAUDE.md cwd cut）已部署、首班觀察中**：VPS 實測證實每 `claude -p` call 的 project CLAUDE.md auto-load 佔 **22.5K token**（換 cwd 可砍、決策+格式不變、不動 auth）。**1a 已 merge master + VPS pull（commit `9c5c517`），明天 TW 12:30 cron 首班生效** — 被動觀察點：首班 batter/SP `[FA Scan]` issue 正常產出 + 無 `fa-scan-error` alert（production claude call 非 json mode、不記 usage，「省」靠 A/B 邏輯保證，不再 production 量）。VPS cron 環境 `tempfile.gettempdir()=/tmp`、往上 + `~/.claude` 無 CLAUDE.md，已驗證 neutral cwd 乾淨。`--tools ""` 否決（破壞 cache）。**槓桿 2（batter output 收斂，9–11K tokens 是單一最大成本項）有 OPEN（砍哪些）待對齊**。branch `refactor/fa-scan-prompt-slim`（保留待槓桿 2）。完整量測 + 槓桿決策見文末「Phase 1.5」段。

## Problem Statement

2026-06-15 起，Anthropic 把 `claude -p`（headless Claude Code）與 Agent SDK 的用量從訂閱方案的一般額度，改為扣**獨立月度 credit pool**：Max 5x = $100/月、按 full API rate 計價、**不滾存、用完即停**

本專案所有 cron 自動跑的 LLM 都是 headless `claude -p`，6/15 後全部改吃這筆 $100 credit。實測現況：

- VPS 預設 model = **`claude-opus-4-6`**（最貴：$5 / $25 per 1M），cron 無任何 `--model` 覆蓋，全跑 Opus。
- 每個 `claude -p` 背 **~38K input token / ~$0.17 的固定 Claude Code harness 開銷**（系統提示 + tool 定義 + 專案 CLAUDE.md；VPS 無 MCP server，開銷非 MCP）—— 對「單發資料分析」任務全是 waste，但走 `claude -p` 無法避免。

- 每日 headless 約 5 次（2 日報 + 3 fa_scan：1 batter + 2 SP）
同時，記憶 `project_claude_p_subscription`（「claude -p 走訂閱不計 API 費用」）6/15 起**失效**，需更正以免誤導未來 session。

## Solution

在不犧牲決策品質的前提下，砍掉「真正不必要」的 headless `claude -p` 呼叫，把月度 credit 消耗壓低、拉開與 $100 上限的餘裕。本 pass 只做**必要性砍除**（移除 waste、不拿品質換成本）：

1. **退役 `--rp` 週掃** —— 已被互動式 `/rp-svh` skill（不計 credit）取代，直接停。✅ 2026-06-05 完成（見「進度」段）。
2. **日報 2 份合併成 1 份/日** —— 速報（TW 22:15）+ 最終報（TW 05:00）原本各自覆蓋「日場 / 夜場」兩種賽程 regime；合併成單一報，靠**排程隨星期幾追當天主賽程**，避免兩份重複的固定開銷。保留 LLM（內容做簡化）。
3. **排程改平日/假日分流** —— 賽程實測證實平日 83% 夜場、假日 80% 日場，最早鎖點差異大；單一固定時間無法同時服務，故分流。

載體續用 `claude -p` 吞訂閱 credit

## User Stories

1. 作為聯賽單人維護者，我要在 6/15 credit 改制前砍掉不必要的 headless `claude -p`，以免自動化 cron 在月中耗盡 $100 credit 後靜默停擺。
2. 作為維護者，我要保留 batter FA 評估的 LLM 層，因為它是 v4 thin 的決策核心（drop 排序 + FA 取代建議 + waiver-log 自動更新），砍了會失去整個打者 FA 決策。
3. 作為維護者，我要維持 SP B2 的 2-step（Step A + Step B）原狀不併段，因為 Step B 是兩週前 cutover 刻意設計的品質 hedge，併段只省 $6–8/月卻撤掉設計、打斷 backtest 基線。
4. 作為維護者，我要直接退役 `fa_scan.py --rp` 週掃，因為它已被互動式 `/rp-svh` skill 取代，留著只是每週多燒一次 credit。
5. 作為維護者，我要把速報與最終報合併成一天一份報，以省下其中一份的 ~$0.17 固定開銷 + 輸出 token。
6. 作為維護者，我要合併後的單一日報保留 LLM 推理（sit/start matchup 比較），而非退化成 Python 模板，以維持決策品質。
7. 作為維護者，我要日報內容做簡化（精簡區塊與冗詞），降低輸出 token 並讓報更好讀（細節於實作時對齊）。
8. 作為維護者，我要日報排程按平日/假日分流：平日約 TW 05:30 報夜場（真實 lineup 已貼、趕在最早鎖 TW 06:34 前），假日約 TW 22:30 報日場（lineup 剛貼、趕在最早鎖 TW 00:15 前）。
9. 作為維護者，我要排程確切分鐘數在實作時用「Yahoo 日期翻轉 + lineup 貼出 lead time」實測微調，而非寫死猜測值。
10. 作為維護者，我接受平日 getaway day（Wed/Thu 少量午場、~TW 01:00 鎖）會被平日晚報漏掉的 caveat（佔平日 ~17%），不為此加額外偵測邏輯。
11. 作為維護者，我要合併後的單一日報能 graceful 處理「lineup 已貼（平日晚）」與「lineup 未貼、只有 probable（假日早）」兩種輸入狀態，沿用既有 `analyze(morning=...)` 的 lineup-availability 處理。
12. 作為維護者，我要繼續用 `claude -p` 吞訂閱 credit、不改直連 Anthropic API，因為 $100 免費額度用不完，直連是花真錢省免費資源 + 要管 API key + 重寫 subprocess。
13. 作為維護者，我要把失效的記憶 `project_claude_p_subscription` 更正為「6/15 起 claude -p 改吃獨立 credit pool」，以免未來 session 沿用錯誤假設。
14. 作為維護者，我要 model 降級明確留待 Phase 2（必要性砍除上線並觀察後再評 Opus→Sonnet/Haiku），不混進本 pass。
15. 作為維護者，我要本 pass 的 cron 改動在 VPS 上以正確的 TW↔UTC 日期/星期換算落地，避免 cron 在跨日界線誤觸發。
16. 作為維護者，我要 `--rp` 退役後，CLAUDE.md 與 SOP 表中相關段落（每週流程、檔案索引、待辦）同步更新，避免孤兒文檔。

## Implementation Decisions

**範圍模組（改動點，非新建深模組）：**

- **`daily_advisor.py`** —— 收斂現有雙模式（`--morning`=最終報 / 無 flag=速報）為**單一報模式**：
  - 移除 `--morning` 的「速報/最終報」語意二分；報內容統一為「有 lineup 用真實、無則用 probable」的 adaptive 判斷（沿用既有 `analyze(..., morning=...)` 的 lineup-data 注入路徑，但不再讀前一份速報）。
  - 移除 Section 7「讀速報建議」邏輯（合併後沒有前一份報可讀）。
  - `save_github_issue` 的 tag / title 命名統一（移除「速報 / 最終報」二分）。
- **Prompt 模板** —— `prompt_template.txt` + `prompt_template_morning.txt` 併為單一模板。同步做**內容簡化**（OPEN：保留哪些區塊、砍哪些冗詞，於實作時對齊）。預設方向：保留「Lineup 異動（sit/start + 1 句數據理由）」與「SP 確認」，砍「SP 排程備查」「注意事項」等低訊號區塊。
- **Cron（VPS `/etc/cron.d/daily-advisor`）**：
  - 刪除現有兩條 daily_advisor 行（22:15 速報 + 05:00 最終報）與一條 `--rp` 週掃行。
  - 新增**平日行**（Mon–Fri，~TW 05:30）與**假日行**（Sat–Sun，~TW 22:30），同一支 `daily_advisor.py`、無 `--morning` 二分。day-of-week 與時間以 UTC 表示，需正確換算 TW↔UTC 並注意跨日界線（既有 cron 註解已有手算 TW→UTC 前例，沿用同風格但加註）。
- **`--rp` 退役**：本 pass 最小範圍 = 移除 cron 行使其停跑。`_run_rp_scan` / `RP_QUERIES` / `prompt_fa_scan_rp.txt` 等死碼的完整 grep 清除屬 C1 cleanup（見既有待辦 rp-svh-sop），可同批做亦可分開。
- **記憶 / 文檔更正**：更新 `memory/project_claude_p_subscription.md`（6/15 改制事實）；CLAUDE.md 每週 SOP 表移除 `--rp` 列、檔案索引與待辦同步。

**排程決策依據（未來 14 天賽程實測）：**

- 平日 124 場：日場 17% / 夜場 83%；純夜場日最早 first pitch 18:34 ET = TW 06:34。
- 假日 60 場：日場 80% / 夜場 20%；最早 first pitch 12:15 ET = TW 00:15。
- → 平日晚報（TW ~05:30 / ET ~17:30）吃夜場真實 lineup；假日早報（TW ~22:30 / ET ~10:30）吃日場 lineup。

**載體決策**：續用 `claude -p`（吞訂閱 credit），不改直連 API。

**保留不動**：batter LLM（v4 thin load-bearing）；SP B2 2-step（Step A + Step B 原狀）。

## Testing Decisions

好測試只驗外部行為、不綁實作細節。本 pass 的測試面**很薄** —— 主要改動是 cron config（無 Python 邏輯可單測）+ prompt/flag 重構（LLM 輸出形狀，不適合 assert 字串）。決策：

- **不為 cron 排程新增單元測試**（純 config；day-of-week / TW↔UTC 換算以人工核對 + VPS dry-run 驗證，非 pytest）。若實作時選擇把「當下該跑哪個 regime」抽成 Python 純函式（而非純 cron），則該函式比照專案既有 pure-function TDD 風格（如 `test_stream_sp_scan.py` 的 `classify_opener` / `compute_sample_warning` 邊界測試）補測。預設傾向純 cron、不抽函式（單人維護優先簡單）。
- **daily_advisor 合併**：以一次 VPS 端 dry-run / 實跑驗證合併後報能在「有 lineup」與「無 lineup（probable）」兩情境正常產出，非自動化測試。
- **`--rp` 退役**：驗證 = cron 不再觸發（log 無 RP 行）+ `/rp-svh` 仍可手動跑；無新測試。
- 既有測試（`test_fa_compute.py` 等）不受本 pass 影響，應維持綠燈。

## Out of Scope

- **SP Step A+B 併段**：擱置，B2 維持 2-step 原狀（理由見 User Story 3）。
- **Model 降級（Opus→Sonnet/Haiku）**：Phase 2，獨立決策 / 獨立 PR。待必要性砍除上線並觀察一段時間後再評各 call site 的品質容忍度（fa_scan SP/batter 有 `cron_backtest` 週級監控可抓回歸）。
- **改直連 Anthropic API**：否決（$100 免費 credit 用不完，直連是花真錢省免費資源）。
- **fa_scan batter / SP 的 LLM 層改動**：不動。
- **`--rp` 相關死碼的完整 grep 清除（C1）**：可併入本 pass 亦可走既有 rp-svh-sop 待辦，非必須同批。✅ 2026-06-05 已併入本 pass 完成。

## Further Notes

- 本 pass 屬「功能重構 + 改 behavior（cron / 報結構）」→ 依專案版控規範**先開 branch**（如 `refactor/claude-p-cost-cut`），小步提交（退役 --rp / 合併日報 / 排程分流 / 文檔更正 各一 commit）。
- 所有 cron 與腳本改動落在 VPS（`/opt/mlb-fantasy`）；本機只開發 + git push，VPS git pull 生效。Yahoo-touching 腳本（daily_advisor / fa_scan）不可本機跑（hook 強制）。
- 合併後日報的**內容簡化細節**為本 pass 內 OPEN 子項，於實作 prompt 併檔時對齊（保留/砍哪些區塊、冗詞精簡）。
- 成本數字為估算；若需精準，可在實作前後各抓幾筆 `claude -p ... --output-format json`（回傳 `usage` + `total_cost_usd`）對照。
- Phase 2 model 降級的品質監控已有基礎設施：fa_scan SP 走 `cron_backtest.sh`（週日 backtest）+ `/weekly-review` 人工 spot check。

---

## Phase 1.5 — fa_scan prompt 簡化（2026-06-08）

> 觸發：S1+S2+S3（日報/排程）落地後，回頭處理 fa_scan 的 headless 成本。`/goal`-driven 量測 session。branch `refactor/fa-scan-prompt-slim`。
> 本段 = 必要性砍除延伸（砍 waste、不換品質），仍屬本 PRD「不動 model」範圍；model 降級續留 Phase 2。

### 背景重構

「prompt 簡化」初始直覺是刪 prompt 文字，但 VPS 實測證明 fa_scan 每個 `claude -p` call 的成本大頭**不在自帶 prompt+data，而在固定 harness 開銷裡的 project CLAUDE.md auto-load**。fa_scan 一天 3 call（batter 1 + SP Step A/B 2），每 call 都整份載入 CLAUDE.md，但 batter/SP prompt 本身已自帶完整評估框架 → CLAUDE.md 對此窄任務是純 redundant overhead。

### 量測（槓桿 0，VPS opus-4-6，`--output-format json` 的 `usage`）

短 prompt baseline（harness only，總 input context = input + cache_creation + cache_read）：

| 變體 | 總 input context | cost | 對現狀 |
|------|---:|---:|---|
| 現狀（proj cwd, 全 tool）| 38,399 | $0.176 | 對應 PRD「~38K/$0.17」✅ |
| 換空 cwd（砍 project CLAUDE.md）| 15,925 | $0.036 | −22.5K |
| `--tools ""` | 45,706 | $0.286 | +7K（更糟）|

真實 batter payload（issue #300 mechanical report 68KB，proj vs 空 cwd 各跑一次）：

| | proj（含 CLAUDE.md）| 空 cwd（無）|
|--|---:|---:|
| 總 input context | 74,463 | 51,989 |
| output tokens | 10,871 | 9,070 |
| cost | $0.673 | $0.488 |
| Δ input | — | **−22,474（與短 prompt 量測一致）**|

- project CLAUDE.md = **固定 22.5K token/call**，不隨 payload 變動。砍它省 ~$0.14/call（input 側，cache_create rate）。
- 真實 batter call cost **$0.49–0.67**（遠高於 harness-only $0.17）；其中 **output 9–11K tokens × $25/1M = $0.23–0.27 是單一最大成本項**（opus output 5× input 價）。
- 決策/格式驗證：proj vs 空 cwd 兩份輸出 — drop 叢集相同（Arraez/Duran，僅 P1/P2 互換 = run-to-run 變異）、hold 相同（Buxton/Torres/Walker）、FA 建議相同（Clemens/Smith）、輸出格式（P1-P7 三行式 + ACTION + PASS + waiver-log 區塊）完全一致。**砍 CLAUDE.md 零品質損失**（batter prompt 自帶框架，對 CLAUDE.md 零依賴）。

### 槓桿決策

| 槓桿 | 手段 | 決策 | 證據 |
|------|------|------|------|
| 1a CLAUDE.md | claude -p 從無 CLAUDE.md 的 cwd 跑（`subprocess.run(cwd=...)`）| **採用** | 省 22.5K/call、格式+決策不變、用現有 OAuth |
| 1b tool | `--tools ""` | **否決** | 只砍 built-in、破壞 cache 前綴 → 不省反增 7K |
| 2 output | 收斂 batter 輸出格式 | **採用（上修為主要）** | batter output $0.23–0.27/call = 最大成本項；字面即「prompt 簡化」；SP 走 JSON 不受影響 |

`--bare` 否決：明列 skip CLAUDE.md auto-discovery，但強制 `ANTHROPIC_API_KEY`、不讀 OAuth → 跳出 $100 credit pool 改吃真錢 API，與本 PRD「續吞訂閱 credit」矛盾。換 cwd 達同效果且不動 auth（VPS root 無 user-level `~/.claude/CLAUDE.md`、`/tmp` 往上無 CLAUDE.md，故空 cwd = 零 CLAUDE.md）。

### 實作計畫（branch `refactor/fa-scan-prompt-slim`）

1. **槓桿 1a（cwd cut）**— 一句話 diff：
   - `fa_scan._call_claude`（fa_scan.py:1718）+ `_multi_agent.run_single_agent`（_multi_agent.py:59）的 `subprocess.run([...])` 加 `cwd=<neutral dir>`。
   - neutral dir = `os.path.join(tempfile.gettempdir(), "fa_scan_claude_cwd")` + `makedirs(exist_ok=True)`（空目錄，保證無 CLAUDE.md auto-discovery）。
   - 影響全部 3 call（batter + SP Step A/B），每 call 省 22.5K。
2. **槓桿 2（batter output 收斂）**— 改 `prompt_fa_scan_pass2_batter.txt` 輸出格式段，獨立可逆 commit。

### 預期省幅

- 槓桿 1a：3 call/day × ~$0.14 ≈ $0.42/day ≈ **$12.6/月**（扣同 run 內 1h cache 共用略低），零品質損失。
- 槓桿 2：batter output 若砍 ~30%，再省 ~$0.07–0.08/call/day。

### Testing

- 槓桿 1a：VPS 端真實 payload proj vs 空 cwd 對照（本 session 已做，決策+格式一致）；實作後再跑一次 production dry-run 確認 fa_scan 端到端輸出不變。
- 槓桿 2：prompt 輸出形狀（不 assert 字串）；VPS dry-run 看 batter 報仍含必要區塊（drop 排序 / ACTION / waiver-log 區塊）。

### OPEN

- 槓桿 2 砍哪些區塊 / 冗詞（候選：drop 排序三行→兩行 / PASS 段只在觸發時出 / UPDATE 行精簡）— 實作時對齊。
- 同一次 fa_scan run 內 3 call 的 1h cache 實際共用率（影響真實月省，被動觀察 production usage）。
