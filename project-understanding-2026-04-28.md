# 專案理解紀錄（2026-04-28）

> 本文件是只讀檢視後的專案理解與接手筆記。目標讀者包含下一個 AI session。前段是快速對齊用，後段是詳細背景。

## 0. AI Handoff Summary

下一個 session 先讀這段，再決定要不要讀後面的詳細內容。

- 這是 Yahoo Fantasy MLB 7x7 H2H One Win 的 production 決策系統，不是單純筆記。
- **目前 SP live default 是 v4 + Phase 6 multi-agent**。`SP_FRAMEWORK_VERSION=v2` 只是短期 fallback。
- **不要再用 v2 的 xERA / xwOBA / HH% 三指標當 SP 主判斷**。那是舊 contact-quality-heavy 框架，容易漏掉 IP/K/QS/控球/球風。
- SP v4 的主體是 5-slot Sum：`IP/GS`、`Whiff%`、`BB/9`、`GB%`、`xwOBACON`。Sum 是材料，不是 action。
- SP final action 由 Phase 6 multi-agent 決策：3 agent 排我方 P1-P4、master 整合、必要時 review / re-eval、FA classify / rank、final master 輸出 `drop_X_add_Y` / `watch` / `pass`。
- Batter 目前是 v4 thin：Python 只做 hard filter，production 仍是 single LLM，不是 batter multi-agent。Batter 判斷要看 season skill + 14d trad + playing time + market pressure + prior baseline。
- **每日兩次戰報的最重要任務是 11 batter 全員有比賽時決定 BN 誰**。SP 基本選了就上；若信任度低到不想上，通常應進 FA/drop 評估，而不是 daily start/sit。
- `CLAUDE.md` 是策略大腦，但目前和 code 有 drift；特別是 SP 與部分手動 SOP 仍殘留舊框架文字。判斷 live behavior 時優先看 code dispatch、最新 git log、docs status。
- 高副作用腳本：`roster_sync.py` 會改 config + commit/push；`fa_scan.py` 可能寫 `fa_history.json`、`waiver-log.md`、Telegram、GitHub Issue；`daily_advisor.py` 可能送 Telegram / 建 Issue。
- 本機 `python3` 是 3.9.6，專案需要 Python 3.10+。目前本機 pytest collection 會因 `dict | None` 型別語法失敗。
- 下一步最重要不是加新指標，而是同步文件 / prompt / code、補 SP v4 production 回測、校正手動 `/player-eval` SOP。

## 1. Current Live Logic Map

| 類型 | 目前 live 邏輯 | 接手注意 |
|---|---|---|
| SP | v4 + Phase 6 multi-agent，default dispatch 在 `fa_scan.py` | v2 只作 fallback；SP action 不應只看 Sum |
| Batter | v4 thin，single LLM prompt `prompt_fa_scan_pass2_batter.txt` | Sum 只作 hard filter，不應暴露為主判斷 |
| RP | Punt SV+H 前提下週一獨立掃描 | 不主動增 RP，只在品質 / K / 附帶 SV+H 明顯時換 |
| Daily lineup | `daily_advisor.py` + Claude prompt | 核心是 11 batter 搶 10 active slots 時的 BN 決策；其他多為提醒 |
| Weekly review | `weekly_review.py --prepare` + `.claude/commands/weekly-review.md` | 強調 2 週合併、我方可控、策略驗證 |

## 2. SP Framework Opinion and Direction

我對目前 SP v4 的看法：方向正確，而且是本 repo 目前最成熟的球員評價線。

v2 / v3 的主要問題是 contact quality 訊號重複投票。`xERA`、`xwOBA allowed`、`HH% allowed` 都重要，但同家族高度相關，會讓「被打品質差」過度支配判斷，低估 fantasy SP 真正需要的 IP、K、QS、控球與角色穩定性。

v4 的改進是把 SP 拆成五個較獨立的 fantasy 軸：

| 指標 | 為什麼重要 |
|---|---|
| `IP/GS` | 直接對應 IP 與 QS，H2H 7x7 是實際得分類別 |
| `Whiff%` | K 能力前驅，比單純 K/9 更早反映 stuff |
| `BB/9` | WHIP 的 BB 端，也反映爆局風險 |
| `GB%` | 降低 HR / 長打風險，幫助 ERA / WHIP 與省球數 |
| `xwOBACON` | 只看 contact damage，避免 xwOBA 被 K/BB 稀釋 |

正確使用方式：

- Sum 是「當下能力快照」，不是 add/drop verdict。
- Rotation Gate 要先排除 fake SP / long relief。
- 2025 prior、slump hold、21d xwOBACON、xERA-ERA luck、樣本量與角色警示要一起看。
- FA 是否值得 add，要看 anchor vs FA 的一對一脈絡、%owned 壓力、acquisition 成本與下次先發窗口。
- Borderline case 應交給 Phase 6 review / re-eval，不要由 Python tiebreak 硬選。

目前風險：

- 百分位桶有鈍器問題；相鄰 bucket 的 raw 差距可能很小。prompt 已要求看 raw value，不只看 Sum。
- Multi-agent 同模型同 prompt，不是真正多模型 diversity；價值主要在穩定性與 borderline review。
- SP v4 剛切 live，需要持續把每次 action 寫入 backtest，2-8 週後驗證。
- 文件 drift 會讓手動評估誤用舊規則，這比公式本身更危險。

我的方向建議：

1. 先把 `CLAUDE.md` SP 章節改成 v4 live rules，v2 僅標為 rollback / historical。
2. 對齊 `.claude/commands/player-eval.md`，避免手動評估還走舊 SP 流程。
3. 補 SP v4 production observation / backtest，不急著再加第六個指標。
4. 等累積足夠 borderline case，再校準 Phase 6 的 review gate 與 watch / action 門檻。

## 3. Batter Framework Opinion and Direction

我對目前 batter v4 thin 的看法：方向正確，但成熟度低於 SP。SP 已進 v4 + Phase 6 multi-agent；batter 目前是 v4 thin + single LLM，決策層還沒完全升級。

舊 batter 流程的問題是過度相信 season Sum / urgency。打者在 H2H 一週週期裡，短期使用價值受 14d 產出、PA 分配、K% spike、platoon / role、%owned 窗口影響很大。只看 season Savant 容易出現兩種錯誤：

- drop 正在熱的隊上球員：例如 season quality 弱，但 14d OPS / counting stats 正在提供當週價值。
- add 正在冷的 FA：例如 season quality 好，但 14d OPS 崩、%owned dropping，實際是在接刀。

目前 v4 thin 的核心是「Python thin / LLM thick」：

- Python 只做 hard rule：`cant_cut` 排除、BBE < 40 排除、2026 Sum >= 25 排除。
- Sum 只在機械層內部當 filter，不應成為 prompt 的主要 anchor。
- LLM 看 raw + percentile + 14d trad + owned trend，自由 reasoning drop / add / watch。

我會把 batter 評估拆成五層：

| 層 | 主要數據 | 判斷目的 |
|---|---|---|
| Season skill | `xwOBA`、`BB%`、`Barrel%`、輔助 `HH%` | 球員長期打擊品質、discipline、power skill |
| 14d trad | OPS、AVG、HR、RBI、R、SB、BB、K%、K% spike | H2H 一週使用價值；不是長期預測，但會影響本週是否能 drop/add |
| Playing time | PA、PA/Team_G、BBE | 樣本量與每日上場可信度 |
| Market pressure | %owned current、3d / 7d delta、shape | 判斷 FA 窗口是否正在關閉，或市場是否正在放棄 |
| Prior baseline | 2025 xwOBA / BB% / Barrel% / OPS / PA | 區分 breakout、slump、結構性弱、BABIP 噪音 |

我認同的設計：

- **Sum 不暴露給 LLM**：避免 LLM 被 aggregated score 錨定，尤其是 FA vs anchor 的排序。
- **14d trad 是 first-order signal**：H2H 一週決策不能只看 season Savant；短期產出會直接影響本週類別。
- **BB% 要比一般 fantasy 更重要**：本聯盟 BB 是獨立類別，且能支撐 OPS 的 OBP 端；隊伍也曾記錄 BB 結構性偏低。
- **品質評估不看守位 / BN / DTD**：這些不是球員打擊品質；但 final execution 可以看 roster slot 成本與守位 fit。

目前風險：

- Batter 尚未 multi-agent，single LLM 仍可能被窗口壓力或單一亮眼訊號帶走。
- Python thin 之後更依賴 prompt 品質；prompt 必須清楚區分「14d trad 是 H2H 使用訊號」與「hot/cold streak 不是長期預測」。
- FA pool 若仍以 `sum_diff` 或 Sum 派生順序排序，即使不顯示數字，也會有隱性 anchor。未來 batter multi-agent 時應移除這類 ordering hint。
- K% spike、platoon、傷勢、打序變化需要新聞與 lineup 脈絡，目前不是完整自動化。

我的方向建議：

1. 不要恢復 batter urgency 4-factor；v4 thin 的方向比舊機械決策更合理。
2. 下一步應補 batter multi-agent，而不是再加機械 tag。
3. Multi-agent 上線前，先補齊 `_player_to_v4_schema` 的 14d trad、K% spike、owned trend。
4. 手動 `/player-eval` 要改成同樣五層判斷，避免和 `fa_scan.py` production 判斷分裂。

## 4. Daily Reports Opinion and Direction

我修正後對每日兩次戰報的定位：**這不是 SP start/sit 系統，核心是 batter BN 決策系統**。

投手原則：

- SP 基本上選了就會上。
- 如果一位 SP 讓人不想在正常 matchup 裡啟用，問題通常不是「今天坐不坐」，而是「他是否值得 roster spot」。
- 因此 SP 的主要決策應回到 `fa_scan.py` / `player-eval` / SP v4，而不是 daily report 每天反覆 start/sit。
- Daily report 對 SP 只需提醒：明日誰先發、是否有明顯異常、是否撞上極端球場 / 打線、是否影響 Min IP。

打者才是晚間速報最重要，甚至幾乎唯一重要的任務。你的 roster 是 11 batter，但 active slot 是 10 個；當 11 人全員有比賽時，系統必須回答：

> 今天 / 明天應該 BN 哪一個 batter？

這個 BN 決策要用「短期 lineup execution」邏輯，不是長期 drop/add 邏輯。建議排序訊號：

| 優先順序 | 訊號 | 用法 |
|---|---|---|
| 1 | MLB confirmed lineup | 沒先發者優先 BN；bench 卻先發者要提醒可換上 |
| 2 | 是否休兵 / 死格 | 休兵自然 BN；避免 active slot 空轉 |
| 3 | 打序與 PA 機率 | 前段棒次 / 每日先發者優先 active；platoon / 下位棒次降級 |
| 4 | 14d trad | OPS、AVG、HR/RBI/R/BB 近況決定 H2H 當週使用價值 |
| 5 | 對手 SP 品質與 handedness | 面對極強 SP 或不利 split 時可作 tiebreak，不應凌駕 lineup / PA |
| 6 | 本週 category need | 需要 BB / HR / AVG / OPS 時，active 選擇可往該類傾斜 |
| 7 | Season skill / prior | 當日訊號接近時，用長期品質作最後 tiebreak |

我會把兩份報告分工定義成：

- **晚間速報**：預先判斷明天 11 batter 是否全員有賽；若超過 10 active bats，明確列出建議 BN 1 人與理由。
- **清晨最終報**：用 confirmed lineup 修正晚間建議；列出「active 但未先發」與「BN 但有先發」的交換建議。

輸出格式應該更像 action list，而不是一般分析文：

```text
打者 BN 決策：
- 建議 BN：Player X
- 主要理由：未先發 / 對手 SP 極強 / 14d 下滑 / category fit 較差
- 替代方案：若 Player Y 未先發，改 BN Player Y，上 Player X

提醒：
- SP 明日先發：...
- 投打衝突：...
- 死格 / 休兵：...
```

不應讓 daily report 承擔的事：

- 不應每天重新判斷誰該 drop。
- 不應把 SP start/sit 當主軸。
- 不應用單日 matchup 推翻 batter 長期評價。
- 不應把提醒資訊蓋過「今天 BN 誰」這個核心輸出。

我的方向建議：

1. 修改 daily prompt，要求輸出第一段固定為 `打者 BN 決策`。
2. 當 11 batter 全員有比賽時，必須給唯一 BN 建議；不可只列資料讓使用者自己判。
3. Morning mode 應把 confirmed lineup 差異放最前面：active not starting / BN starting。
4. SP 區塊降級為 reminder，除非出現極端異常或 Min IP 風險。

## 5. Docs / Code Drift Warnings

目前不能把任何單一文件當絕對真相。建議下一個 session 判斷 live 行為時依序確認：

1. `fa_scan.py` 實際 dispatch：SP 預設 `SP_FRAMEWORK_VERSION=v4`
2. `_phase6_sp.py`：SP Phase 6 實際 orchestration
3. `fa_compute.py`：v4 Sum / gate / tag / urgency 實作
4. `docs/v4-cutover-plan.md` 與最新 git log：確認 cutover stage
5. `CLAUDE.md`：讀策略與營運 SOP，但遇到 SP 評估規則要交叉確認是否已過期

已知 drift：

- `CLAUDE.md` 仍有部分 v2 SP 規則文字。
- `.claude/commands/player-eval.md` 的 batter / SP 手動流程有舊邏輯。
- Batter multi-agent 設計已寫，但 production 尚未啟用；目前仍是 v4 thin + single LLM。
- Daily report 的核心需求應是 batter BN 決策；若 prompt 仍把 SP matchup / 長篇分析放太前面，應調整。
- `docs/` 中有些 design doc 是演進紀錄，不代表 live。

## 6. Recommended Next Actions

P0：

1. 更新 `CLAUDE.md` 的 SP 評估章節為 v4 live default。
2. 更新 `.claude/commands/player-eval.md`，明確區分 SP v4 live、Batter v4 thin 五層判斷、舊規則只作歷史。
3. 修改 daily report prompt，讓「11 batter 全員有比賽時 BN 誰」成為速報 / 最終報的第一輸出。
4. 指定 Python 3.10+ 測試環境，讓本機能跑 pytest。

P1：

1. 補 `docs/v4-cutover-parallel-log.md` 或 Stage F.1 production 觀察紀錄。
2. 持續更新 `docs/sp-decisions-backtest.md`，把 v4 action 後續走勢補齊。
3. 檢查 `fa_scan.py --sp-only --no-send --no-issue --no-waiver-log` 在 VPS 的健康狀態與 parse 穩定性。
4. 調整 `daily_advisor.py` / prompt 的資料排序：confirmed lineup 與 batter availability 高於 SP matchup 敘述。

P2：

1. 等 SP v4 穩定後，再做 batter multi-agent。
2. 拆小 `fa_scan.py` 的 I/O orchestration。
3. 強化 v4 vs actual outcome 的自動化 diff / parser。

## 7. 專案定位

這份 repo 不是單純的 fantasy baseball 筆記，而是一套「Yahoo Fantasy MLB 7x7 H2H One Win」的賽季管理決策系統。核心任務是每天幫你判斷：

- 明天 lineup 要怎麼排
- 哪些隊上球員正在拖累 14 類別勝率
- FA 市場有哪些 batter / SP / RP 值得觀察或替換
- 每週對戰要怎麼歸因、驗證策略、更新下一週行動

系統的設計方向很明確：Python 負責撈資料、整理資料、做可測的機械訊號；Claude prompt / multi-agent 負責把棒球脈絡、H2H 一週決策、FAAB 時效、短期風險整合成動作建議。

## 8. 聯盟與策略基準

聯盟格式：

- 12 隊
- H2H One Win
- 打者 7 類：R, HR, RBI, SB, BB, AVG, OPS
- 投手 7 類：IP, W, K, ERA, WHIP, QS, SV+H
- 每週 Min IP 40
- 每週最多 6 次 add
- Yahoo lineup 是 Daily - Tomorrow
- 所有撿人走 FAAB，台灣時間 15:00 左右處理

策略核心：

- Punt SV+H：不主動為 SV+H 增加 RP，但現有 RP 若有 SV+H 算附加價值
- 軟 Punt SB：不為速度型球員犧牲主力打擊品質
- SP 重裝：重視 IP / W / K / QS，同時管理 ERA / WHIP
- 打者偏好高 BB% + OPS，因 BB 在 7x7 中是獨立類別，也會支撐 OPS 的 OBP 端
- 「不動也是策略」：FA 沒明顯高於現有球員時，不為了有動作而動作

目前核心 cant_cut 在 `daily-advisor/roster_config.json`：

- Tarik Skubal
- Jazz Chisholm Jr.
- Manny Machado

## 9. 單一事實來源

我看到幾個很清楚的 source of truth：

| 檔案 | 角色 |
|---|---|
| `CLAUDE.md` | 策略大腦、評估框架、SOP、cron、待辦與架構說明 |
| `daily-advisor/roster_config.json` | 當前 roster 唯一來源，含 Yahoo key、MLB id、守位、selected_pos、status、prior_stats |
| `waiver-log.md` | FA 觀察中、隊上觀察、已結案的追蹤檔 |
| `week-reviews.md` | 週預測與覆盤紀錄 |
| `league-scouting.md` | 其他 GM 策略、waiver 競爭與交易情報 |
| `docs/` | 框架演進、cutover、backtest、review finding |
| GitHub Issues | daily report / FA scan 的長期 archive |
| Telegram | 每日實際通知出口 |

`CLAUDE.md` 的地位最高，但它也有目前遷移期留下的文件落差：程式碼已把 SP 預設切到 v4 multi-agent，`CLAUDE.md` 內仍保留部分 v2 SP 評估章節，文件自己也註記 Stage F cutover 完成時要改寫。

## 10. 主要資料來源

系統吃四類外部資料：

- Yahoo Fantasy API：league roster、FA list、percent owned、scoreboard、transactions
- MLB Stats API：賽程、probable pitcher、game log、season stats、lineup
- Baseball Savant CSV / Statcast endpoints：xwOBA、xERA、Barrel%、HH%、Whiff%、GB%、xwOBACON 等
- Claude CLI：`claude -p` 產出自然語言與 structured JSON 決策

輸出端：

- Telegram Bot
- GitHub Issue archive
- `waiver-log.md`
- `daily-advisor/fa_history.json`
- `daily-advisor/weekly-data/week-N.json`
- `daily-advisor/savant_rolling.json`

## 11. 日常工作流

### 每日戰報：`daily_advisor.py`

入口：

```bash
python3 daily_advisor.py
python3 daily_advisor.py --morning
```

它做的事：

1. 讀 `roster_config.json`
2. 若 Yahoo token 可用，抓 live Yahoo roster，失敗則 fallback 到 config
3. 抓當天 MLB schedule / probable pitchers
4. 找我方 batter 面對的 opposing SP
5. 找我方 SP 明日先發
6. 抓我方與對手投手的 season stats / Savant
7. 抓 lineup 確認
8. 組成 raw summary
9. 呼叫 `claude -p` 套 `prompt_template.txt` 或 `prompt_template_morning.txt`
10. 印出結果、送 Telegram、建立 GitHub Issue

它不是單純「誰今天有比賽」工具，而是 daily lineup advisor：會考慮 batter 是否休兵、對手 SP、我方 SP matchup、投打衝突、本週剩餘 SP 排程、對手 SP 排程、lineup 是否公布。

重要風險：

- `--no-send` 只是不送 Telegram，但仍會跑 Claude；正常模式會建立 GitHub Issue。
- 本機沒有 Yahoo token 時會 fallback 到 config，資料不一定是 live roster。
- `python3` 需 3.10+；本機目前 `python3 --version` 是 3.9.6。

### FA 市場掃描：`fa_scan.py`

入口：

```bash
python3 fa_scan.py
python3 fa_scan.py --rp
python3 fa_scan.py --snapshot-only
python3 fa_scan.py --cleanup
python3 fa_scan.py --sp-only --no-send --no-issue --no-waiver-log
```

它是目前最核心的球員挑選系統。每日流程：

1. Yahoo FA queries 抓 batter / SP 候選與 percent owned
2. 讀寫 `fa_history.json`，計算 1d / 3d owned trend
3. 下載 2026 Savant CSV
4. 解析 `waiver-log.md` watchlist
5. 確認 watchlist 球員是否已被 rostered
6. Layer 2 用 Savant 品質初篩 FA
7. 把 owned risers 補進候選池
8. Layer 3 補 MLB stats、prior stats、derived stats
9. batter 與 SP 以 threading 並行處理
10. 呼叫 Claude / multi-agent
11. 推送 Telegram / GitHub Issue
12. 視參數更新 `waiver-log.md`

安全旗標很重要：

- `--dry-run`：只跑 Layer 1+2，不呼叫 Claude
- `--no-send`：不送 Telegram / Issue，但仍可能做其他動作
- `--no-issue`：不建 Issue
- `--no-waiver-log`：不寫 waiver-log
- `--sp-only` / `--batter-only`：只跑一條線

`waiver-log.md` 更新有 thread lock，避免 batter 與 SP 並行時同時 git 操作。

### Roster sync：`roster_sync.py`

入口：

```bash
python3 roster_sync.py
python3 roster_sync.py --init
python3 roster_sync.py --dry-run
```

它是 Yahoo roster 到 `roster_config.json` 的同步器。

日常模式：

1. 先 `git pull`，避免 VPS cron 寫到舊版 repo
2. refresh Yahoo token
3. 找自己的 team key
4. 查 league transactions
5. 若沒有新 transaction 就結束
6. 若有新 transaction，抓 full roster
7. diff Yahoo roster vs config
8. enrich 新球員的 MLB id、Savant prior、MLB season stats
9. 寫 `roster_config.json`
10. git commit / push
11. Telegram 通知

這支腳本會修改 config、commit、push，所以不是只讀工具。

### Weekly review：`weekly_review.py`

入口：

```bash
python3 weekly_review.py --prepare
python3 weekly_review.py --prepare --dry-run
```

它準備每週覆盤資料：

- Yahoo scoreboard
- 14 類別排名
- 近兩週合併排名
- 下週 opponent
- 我方 / 對手 roster
- SP schedule
- positional coverage
- 我方 roster weekly performance
- FA scan summary

`.claude/commands/weekly-review.md` 定義了使用方式：重點不是追對手細節，而是用兩週合併資料判斷「我方可控」的補強與 lineup 決策。

## 12. 評分框架理解

### Batter：v4 thin

現在 batter 的方向是「機械層變薄、LLM 看 raw 自由判斷」。

機械層只做：

- cant_cut 排除
- BBE < 40 排除
- 2026 Sum >= 25 排除
- Sum 只作內部 hard filter，不應暴露給 LLM

核心品質訊號：

- xwOBA
- BB%
- Barrel%

LLM 額外看的訊號：

- 14d OPS / AVG / HR / RBI / R / SB / BB / K / K% spike
- 3d / 7d percent owned trend
- 2025 prior
- PA / BBE / PA per team game

目前 production 是單 LLM prompt `prompt_fa_scan_pass2_batter.txt`，不是完整 batter multi-agent。docs 記載未來要等 SP F.1 觀察期穩定後再接 batter multi-agent。

我注意到 `docs/batter-v4-thin-implementation-review.md` 已記錄過 positions 欄位暴露、schema 不完整等 finding，後續 commit 看起來已修過主要問題。這份 repo 有明確的 code review / follow-up 習慣。

### SP：v4 + Phase 6 multi-agent

程式碼目前 SP 預設走 v4：

```python
sp_framework = os.environ.get("SP_FRAMEWORK_VERSION", "v4")
```

可用 `SP_FRAMEWORK_VERSION=v2` 回滾。

SP v4 不再只看 contact quality，而是 5-slot balanced Sum：

| 指標 | 意義 |
|---|---|
| IP/GS | IP + QS 產量 |
| Whiff% | K 前驅訊號 |
| BB/9 | WHIP 的 BB 端與控球 |
| GB% | HR 抑制、省球、雙殺 |
| xwOBACON | on-contact quality |

v4 重點是把「當下產量快照」與「時序 / 角色 / 運氣訊號」分開：

- Sum：5 個獨立軸的目前能力
- Rotation gate：先排除 pure RP / long relief
- Tags / flags：雙年菁英、深投型、K 壓制、GB 重型、樣本小、短局、xwOBACON 極端、運氣回歸
- Urgency：低 Sum、2025 prior、21d xwOBACON raw、xERA-ERA luck regression

Phase 6 multi-agent 流程在 `_phase6_sp.py`：

1. 3 agents 排我方最弱 SP P1-P4
2. master 整合 P1-P4
3. 若 borderline，3 reviewers review，必要時 re-eval 一輪
4. 3 agents classify FA 候選為 worth / borderline / not_worth
5. FA master rank 候選
6. 若 borderline，FA reviewers review，必要時 re-eval 一輪
7. final master 做 drop / watch / pass
8. 輸出 Telegram summary 與 waiver-log updates

這是這個 repo 最有工程感的部分：LLM 不是直接自由輸出，而是被 prompt schema、JSON parser、投票與 degrade path 約束。

### RP

RP 因 Punt SV+H，不是主要掃描對象。週一 `--rp` 獨立掃描，主要看比率與 K，SV+H 是附加價值。策略上維持 2 RP，不會為 SV+H 擴到 3-4 RP。

## 13. 程式碼架構觀察

### 可測機械層

`fa_compute.py` 是 deterministic layer：

- 百分位轉分數
- 2026 / 2025 Sum
- weakest pool
- urgency
- FA tags
- v4 SP Sum / rotation gate / luck tag
- v4 SP weakest / urgency

這個切法是正確的：prompt 容易漂移，但 Sum / gate / tag 這些規則應該放 Python 並用 tests 鎖住。

### I/O orchestration 層

`fa_scan.py` 很大，負責：

- Yahoo snapshot
- fa_history
- waiver-log parsing / writing
- Savant CSV 下載與 index
- FA enrichment
- report formatting
- Claude invocation
- publish / notify
- v2 / v4 dispatch

它目前是 production orchestration 巨石。未來若要改善，應該優先抽：

- Yahoo snapshot + history
- Savant enrichment
- waiver-log mutation
- publish / GitHub Issue

但在目前個人專案規模下，功能仍可追蹤，而且已有 `_phase6_sp.py` 把最複雜的 SP multi-agent 拆出去。

### Prompt contract

SP Phase 6 prompt 都要求 strict JSON fenced block。`_multi_agent.extract_json()` 支援 fenced JSON 與裸 JSON，並有 unit tests。這讓 LLM output 變成可驗證接口，而不是純文字依賴。

Batter prompt 目前仍偏報告文字 + `waiver-log` block，較難自動化驗證。

## 14. 測試狀態

測試檔集中在 `daily-advisor/tests/`，覆蓋：

- `fa_compute`
- `fa_compute_v4`
- `_multi_agent`
- `_phase6_sp`
- `roster_sync`
- `savant_rolling`
- `backfill_prior_stats_v4`
- waiver-log position lookup

我嘗試用避免寫入 cache 的方式執行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

結果在 test collection 失敗：

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

原因是本機 `python3 --version` 為 `Python 3.9.6`，專案使用 `dict | None` 等 Python 3.10+ 語法。這與 README 的 Python 3.10+ 要求一致，不代表測試本身失敗。

## 15. 目前專案狀態判斷

從 git log 與文件看，現在正處於兩條遷移剛完成 / 觀察中的狀態：

1. SP v4 Stage F.1 已切成 default
   - commit 顯示 `feat(fa_scan): default SP framework v4`
   - `SP_FRAMEWORK_VERSION=v2` 仍是短期 fallback
   - 下一步應該是觀察 5-7 天 production 健康，再決定清 v2 或補文件

2. Batter v4 thin 已實作
   - commit / docs 顯示 PR #125 已完成
   - 目前 production 仍是單 LLM，不是 batter multi-agent
   - 下一步是等 SP 穩定後，再把 batter multi-agent 補上

3. `CLAUDE.md` / `.claude/commands/player-eval.md` 有部分舊框架文字
   - `player-eval` 還描述打者 v2 urgency / 最弱 4 人
   - 但目前 batter v4 thin 已不走該機械 urgency
   - 如果後續手動使用 `/player-eval`，應先校正這些 SOP，避免手動流程和 production 流程分裂

## 16. 風險與注意事項

### 文件與 code drift

這是目前最大風險。repo 文件非常詳盡，但演進很快，因此會出現：

- `CLAUDE.md` 仍有 v2 SP live rules 文字
- `.claude/commands/player-eval.md` 仍有舊 batter 流程
- design doc 已更新，prompt / code 有時先修，有時後修

接手時不能只讀一份文件，要用「程式碼實際 dispatch + 最新 git log + docs status」交叉確認。

### 本機與 VPS 環境不同

README 明確說：

- 所有 production 腳本跑在 VPS `/opt/mlb-fantasy`
- Yahoo token 只存在 VPS
- 本機主要做開發與 git push
- 不要 scp Yahoo token 回本機，避免 refresh token 雙邊不同步弄壞 cron

所以本機測試 Yahoo API 相關腳本時，沒有 token 是正常狀況。

### 有些腳本不是只讀

高風險會寫入 / 推送的腳本：

- `roster_sync.py`：可修改 `roster_config.json`、commit、push
- `fa_scan.py`：會更新 `fa_history.json`、`waiver-log.md`、Telegram、GitHub Issue
- `daily_advisor.py`：會建立 GitHub Issue、Telegram
- `weekly_review.py --prepare`：會寫 weekly-data 並可能 git push

安全使用要加 `--dry-run`、`--no-send`、`--no-issue`、`--no-waiver-log`。

### External API fragility

依賴點多：

- Yahoo OAuth token refresh
- Yahoo API rate limit / HTTP 999
- Baseball Savant CSV 欄位變動
- MLB API probable pitcher 公布時間
- Claude CLI latency / JSON parse
- GitHub CLI issue create
- Telegram 4096 字限制

目前已有部分 fallback / degrade，但 production cron 需要看 log。

### Multi-agent diversity 有限制

Phase 6 spike 結論寫得很誠實：3 個 agent 用同一模型 + 同一 prompt，更多是穩定性與自我審查，不是真正不同模型 / 不同 prior 的 diversity。真正價值在 borderline case 的 review / dissent，而不是非邊界 case 的三次同答案。

## 17. 我會怎麼接手操作

### 想看今天狀態

優先順序：

1. 讀 `CLAUDE.md` 進行中補強行動
2. 讀 `roster_config.json`
3. 讀 `waiver-log.md`
4. 看最近 GitHub Issue 的 FA scan / daily report
5. 看 VPS cron log，而不是直接在本機跑 production 指令

### 想安全跑 FA scan

本機無 Yahoo token不適合跑完整 production。若在 VPS 應優先：

```bash
python3 fa_scan.py --sp-only --no-send --no-issue --no-waiver-log
```

或只看早期篩選：

```bash
python3 fa_scan.py --dry-run
```

### 想評估一位球員

應先確認目前 production 框架版本：

- batter：v4 thin，不要照舊 `player-eval` 的 v2 urgency 直接判
- SP：v4 5-slot + Phase 6
- RP：punt SV+H 前提下看比率 / K / 少量 SV+H 附加價值

然後補：

- Yahoo 狀態 / 守位 / percent owned
- Savant 2026 + 2025
- MLB season stats / game log
- 14d trad / rolling
- 新聞：健康、角色、rotation、lineup

## 18. 高價值後續工作

我會把後續工作分成「先校正」與「再升級」。

先校正：

1. 更新 `CLAUDE.md` 的 SP 評估章節為 v4，移除或標記 v2 只作 fallback
2. 更新 `.claude/commands/player-eval.md` 的 batter 流程，對齊 v4 thin
3. 建立 `docs/v4-cutover-parallel-log.md` 或更新 Stage F.1 觀察紀錄
4. 在本機安裝 / 指定 Python 3.10+，讓測試可跑

再升級：

1. Batter multi-agent：補齊 `_player_to_v4_schema` 的 14d trad / K% spike / owned trend
2. 把 `fa_scan.py` 的 I/O 模組拆小，降低 regression 成本
3. 強化 SP v4 production log parser，追蹤 v4 vs v2 / actual outcome
4. 把手動 `/player-eval` 和自動 `fa_scan` 的 schema 收斂，避免兩套判斷語言

## 19. 總結

這份專案的核心不是「查棒球資料」，而是把 fantasy baseball 決策流程工程化：

- 用 Yahoo API 確認誰真的可用
- 用 Savant / MLB API 把表面成績拆成品質、產量、樣本、近況
- 用 Python 固定機械規則，避免 LLM 隨口編分數
- 用 prompt / multi-agent 把人類脈絡納入：H2H 週期、FAAB 時效、窗口壓力、陣容策略
- 用 waiver-log / week-reviews / backtest docs 建立決策後驗證

我對這份 repo 的接手判斷：已經是一個進入 production 的個人決策系統，而不是實驗筆記。下一個品質瓶頸不是「多加幾個指標」，而是維持 code / docs / prompt / cron 四者同步，並且把 v4 切換後的真實決策回測補齊。
