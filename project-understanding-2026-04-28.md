# 專案理解紀錄（2026-04-28）— 設計反思與開放風險

> 從原 695 行接手筆記保留的設計反思 + 開放風險。已落地或與 `CLAUDE.md` 重複的章節（聯盟設定、評估框架、SOP、live logic map、handoff summary、recommended next actions）已移除，避免雙寫 drift。內容凍結於 2026-04-28，後續演進以 `CLAUDE.md` 為準。

## 1. SP Framework Opinion and Direction

我對目前 SP v4 的看法：方向正確，而且是本 repo 目前最成熟的球員評價線。

v2 / v3 的主要問題是 contact quality 訊號重複投票。`xERA`、`xwOBA allowed`、`HH% allowed` 都重要，但同家族高度相關，會讓「被打品質差」過度支配判斷，低估 fantasy SP 真正需要的 IP、K、QS、控球與角色穩定性。

v4 的改進是把 SP 拆成五個較獨立的 fantasy 軸：

| 指標 | 為什麼重要 |
|---|---|
| `IP/GS` | 直接對應 IP 與 QS,H2H 7x7 是實際得分類別 |
| `Whiff%` | K 能力前驅,比單純 K/9 更早反映 stuff |
| `BB/9` | WHIP 的 BB 端,也反映爆局風險 |
| `GB%` | 降低 HR / 長打風險,幫助 ERA / WHIP 與省球數 |
| `xwOBACON` | 只看 contact damage,避免 xwOBA 被 K/BB 稀釋 |

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

## 2. Batter Framework Opinion and Direction

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

## 3. Daily Reports Opinion and Direction

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
- **清晨最終報**:用 confirmed lineup 修正晚間建議；列出「active 但未先發」與「BN 但有先發」的交換建議。

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

## 4. 程式碼架構觀察

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

## 5. 測試狀態

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

## 6. 風險與注意事項

### 文件與 code drift

這是目前最大風險。repo 文件非常詳盡，但演進很快，因此會出現：

- design doc 已更新，prompt / code 有時先修，有時後修
- `CLAUDE.md` 與手動 SOP 文件偶有滯後

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

## 7. 高價值後續工作

先校正：

1. 建立 `docs/v4-cutover-parallel-log.md` 或更新 Stage F.1 觀察紀錄
2. 在本機安裝 / 指定 Python 3.10+，讓測試可跑

再升級：

1. Batter multi-agent：補齊 `_player_to_v4_schema` 的 14d trad / K% spike / owned trend
2. 把 `fa_scan.py` 的 I/O 模組拆小，降低 regression 成本
3. 強化 SP v4 production log parser，追蹤 v4 vs v2 / actual outcome
4. 把手動 `/player-eval` 和自動 `fa_scan` 的 schema 收斂，避免兩套判斷語言
