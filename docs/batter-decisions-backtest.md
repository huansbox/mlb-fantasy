# Batter 決策對帳 Living Log（issue 029）

> 每週日 cron（`cron_backtest.sh` → `backtest_batter.py --update-doc`）自動 append 週報段。
> 與 SP 對帳（`sp-decisions-backtest.md`）**分檔**：兩邊 hit 定義不同（SP = xwOBACON 品質比較；batter = 六類別實際產出 + 裁判合議），混一份表格式打架。
> 週一 `/weekly-review` 與 SP 週報一起看。

## 機制（PRD C1 定案，`issues/prd-fa-scan-batter-quality.md`）

- **對帳對象**：每日 batter fa-scan issue 的 ```waiver-log``` 區塊（issue 028 文法）——
  - `ACTION|球員|取代/立即取代|vs對象` → **replace 帳**（宣稱：球員產出將勝過 vs 對象）
  - 7 欄 `NEW|球員|隊伍||觸發|vs對象|摘要` 且無同區塊 ACTION → **watch 帳**（宣稱：球員還沒明顯好過 vs 對象）
  - UPDATE / CLOSE / 舊 6 欄 NEW（pre-028）不可對帳。**028 部署日 2026-06-10 = 曆法起點**；首筆新文法帳 2026-06-11 產生，最早 2026-07-02 帳齡達 21 天，**首個可能非空週日段 = 2026-07-05**。在那之前每週輸出「0 筆可對帳」屬正確行為。
- **Episode 去重**（與 SP 共用 `_backtest_lib.dedupe_episodes`）：同一組（kind, 球員, vs）相鄰掃描日連續出現 = 一筆帳，從首日起算觀察窗；取代/立即取代強度不拆帳。
- **帳齡窗口**：每週日只對帳齡 ∈ [21, 28) 天的 episode — 觀察窗走完才對、每筆恰對一次（週日 stride 7）。
- **實際產出**：建議日後 21 天，雙側六類別 **R / HR / RBI / BB / AVG / OPS**（**無 SB** — 軟 punt；**不含 PA** — 上場量已自然反映在累積項），MLB byDateRange 日期窗聚合。
- **機械類別比數** = 稽核底稿，**不參與 hit/miss 判定**（類別輸贏二元、感知不到幅度 — RBI 20 vs 5 ≠ HR 3 vs 4 等值）。
- **outcome 語意**（issue 030，已上線）：裁判合議升級為 hit / miss / 難分 —
  - **裁判運作**：整週可判帳打包成 1 個 payload → 2 位裁判**同一份指示**（`prompt_batter_judge.txt`）各 1 次 claude -p（自 neutral cwd，**每週固定 2 calls**，非逐筆；契約違反各有 1 次 retry）。裁判看到的是**匿名 A/B 六類別產出**（A = 建議球員 / B = vs 對象）— 無姓名（防 brand bias）、無帳種（防順著建議判）、無 PA/G（C1 #4）。
  - **裁判契約**：每帳強制二選一（A/B，不准棄權）+ 明顯/勉強標註 → 合議表：同人 + 至少一位明顯 → 採用；同人 + 雙勉強 → 難分；分歧 → 難分。
  - **replace 帳**：採用 A → hit（量「太衝動」病的反面）；採用 B → miss；難分 → 難分（不進命中率分母）
  - **watch 帳**（鏡像，C1 #8）：採用 A（FA 明顯較好）→ miss（**看走眼**，太保守）；採用 B 或難分 → hit（看對 — 難分即證實「還沒明顯好過」的宣稱，**計入分母**）
  - **降級語意**：scorecard 缺漏（任一側無窗口數據）→ `no-data`；裁判連續契約違反 → panel fail-open，outcomes 留 `pending-judge` + 週報 ⚠️ 警示 — 該批帳下週會老化出 [21, 28) 窗，需手動 `--age-min/--age-max` 重跑補判。
  - **稽核**：週報每帳並列「機械比數 + 兩位裁判判定 + 合議結果」；裁判系統性與機械比數唱反調 → 回頭修裁判 prompt（重測工具 `_tools/_judge_demo_runner.py`）。
- **執行標註**（issue 031，已上線）：每筆帳標「是否實際執行」— 由 `roster_config.json` git 歷史機械判定（**不靠人工**）：執行窗 = episode 首日 → 末日 + 3 天 grace（涵蓋 FA add 隔日生效與 waiver claim Daily-Tomorrow 延遲生效，如 06-02 Buehler 案）。比對 **mlb_id 優先**（id 已解析時同名不同 id 不算執行 — 防同名誤判）、id 未解析才退 name 比對。狀態：`executed`（窗內進名單）/ `not-executed`（窗內未進）/ `already-rostered`（窗前已在名單，罕見）/ `unknown`（git 歷史不足以確立窗前不在籍，寧可 unknown 不給錯的 False）。週報含 executed / not-executed 分組 hit-rate（030 裁判上線前分母為 0 顯示「—」）— 量「人工否決是在加值還是誤殺好建議」（PRD user story 9）。

## 更新紀錄

- **2026-06-10 創建**（issue 029 骨架）：解析 + episode + 六類別比數 + 週日 cron 端到端；outcome 全 pending-judge。
- **2026-06-10 執行標註上線**（issue 031）：每筆帳補 executed 欄位（roster git 歷史機械判定）+ 週報 executed / not-executed 分組 hit-rate 行。真實歷史 spot-check 三例皆正確（Rafaela 06-07 add → executed / Pederson 被搶 → not-executed / Arraez 長期在籍 → already-rostered）。
- **2026-06-10 裁判合議上線**（issue 030）：pending-judge → 2 位裁判合議 verdict（hit / miss / 難分）+ 週報命中率行（replace 量太衝動 / watch 鏡像量太保守）。第一批真 claude 抽查（真實 05-15→06-04 產出，Pederson vs Arraez + Clemens vs Arraez）：2 calls 零 retry 契約全合規、判定與機械比數方向一致無唱反調。**待辦：首個非空 production 週日段（預期 2026-07-05）出來後再做一次人工抽查**（demo 兩帳都偏明顯案例，勉強/難分路徑尚未被真裁判走過）。
- 後續：xwOBACON 門檻校準（Use Case B）等對帳資料累積 4-6 週後另案。

## Weekly Batter Backtest 2026-06-14 (no due episodes)

- Episode age window: [21, 28) days; post-verdict observation: 21 days; issue lookback: 42 days
- Episodes due this run: 0 (replace 0 / watch 0; episodes in lookback: 17) — 0 筆可對帳
- Judge panel（issue 030）: 0 筆可判（無完整 scorecard 的帳）— 0 calls
- Executed split（issue 031，roster git 歷史機械判定；執行窗 = episode 首日 → 末日 + 3d）: executed 0（hit-rate —）/ not-executed 0（hit-rate —）

Decision KPIs (issue 051):
- ⭐ star-bucket 命中率: 5★ 0/0 (—) / 4★ 0/0 (—) / ≤3★ 0/0 (—)
- ⏱ 觸發→執行延遲中位: —（n=0；目標 ≤2 天）
- 🔁 regret（撿入後 30 天內再推薦）: 0


## Weekly Batter Backtest 2026-06-21 (no due episodes)

- Episode age window: [21, 28) days; post-verdict observation: 21 days; issue lookback: 42 days
- Episodes due this run: 0 (replace 0 / watch 0; episodes in lookback: 25) — 0 筆可對帳
- Judge panel（issue 030）: 0 筆可判（無完整 scorecard 的帳）— 0 calls
- Executed split（issue 031，roster git 歷史機械判定；執行窗 = episode 首日 → 末日 + 3d）: executed 0（hit-rate —）/ not-executed 0（hit-rate —）

Decision KPIs (issue 051):
- ⭐ star-bucket 命中率: 5★ 0/0 (—) / 4★ 0/0 (—) / ≤3★ 0/0 (—)
- ⏱ 觸發→執行延遲中位: —（n=0；目標 ≤2 天）
- 🔁 regret（撿入後 30 天內再推薦）: 0


## Weekly Batter Backtest 2026-06-28 (no due episodes)

- Episode age window: [21, 28) days; post-verdict observation: 21 days; issue lookback: 42 days
- Episodes due this run: 0 (replace 0 / watch 0; episodes in lookback: 36) — 0 筆可對帳
- Judge panel（issue 030）: 0 筆可判（無完整 scorecard 的帳）— 0 calls
- Executed split（issue 031，roster git 歷史機械判定；執行窗 = episode 首日 → 末日 + 3d）: executed 0（hit-rate —）/ not-executed 0（hit-rate —）

Decision KPIs (issue 051):
- ⭐ star-bucket 命中率: 5★ 0/0 (—) / 4★ 0/0 (—) / ≤3★ 0/0 (—)
- ⏱ 觸發→執行延遲中位: —（n=0；目標 ≤2 天）
- 🔁 regret（撿入後 30 天內再推薦）: 0


## Weekly Batter Backtest 2026-07-05 (2026-06-11 ~ 2026-06-14)

- Episode age window: [21, 28) days; post-verdict observation: 21 days; issue lookback: 42 days
- Episodes due this run: 17 (replace 7 / watch 10; episodes in lookback: 52)
- Judge panel（issue 030）: 2 位裁判同指示合議，2 calls（強制二選一＋明顯/勉強；同人+至少一明顯=採用，餘=難分）；機械類別比數僅為稽核底稿，不參與判定
- 命中率 — replace（量太衝動）: 71%（5/7），難分 0 / watch（鏡像，量太保守；難分=看對計 hit）: 57%（4/7）
- Executed split（issue 031，roster git 歷史機械判定；執行窗 = episode 首日 → 末日 + 3d）: executed 3（hit-rate 50%（1/2））/ not-executed 14（hit-rate 67%（8/12））

Decision KPIs (issue 051):
- ⭐ star-bucket 命中率: 5★ 0/0 (—) / 4★ 4/4 (100%) / ≤3★ 3/6 (50%)
- ⏱ 觸發→執行延遲中位: 1.5 天（n=2；目標 ≤2 天）
- 🔁 regret（撿入後 30 天內再推薦）: 1 — Kody Clemens

Episodes:
- 2026-06-11 (2d) `replace/取代` add Isaac Paredes ⇄ drop Albies → 機械比數 FA 3W-2L-1T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **hit** 〔not executed〕
- 2026-06-11 (1d) `replace/立即取代` add Jac Caglianone ⇄ drop Arraez → 機械比數 FA 4W-2L-0T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **hit** 〔not executed〕
- 2026-06-11 (1d) `replace/立即取代` add Spencer Steer ⇄ drop Rafaela → 機械比數 FA 2W-3L-1T → 裁判 J1 B·明顯 / J2 B·明顯 ⇒ adopted B → **miss** 〔already rostered 2026-06-10〕
- 2026-06-11 (1d) `watch` watch Curtis Mead vs Duran → 機械比數 FA 6W-0L-0T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **miss** 〔not executed〕
- 2026-06-11 (1d) `watch` watch Joc Pederson vs Arraez → 機械比數 FA 3W-2L-1T → 裁判 J1 A·明顯 / J2 A·勉強 ⇒ adopted A → **miss** 〔not executed〕
- 2026-06-11 (1d) `watch` watch Kyle Karros vs 待定 → 機械比數 no data → **no-data** 〔not executed〕（unresolved id: 待定）
- 2026-06-11 (1d) `watch` watch Samuel Basallo vs 待定 → 機械比數 no data → **no-data** 〔not executed〕（unresolved id: 待定）
- 2026-06-12 (1d) `replace/立即取代` add Spencer Steer ⇄ drop Dubón → 機械比數 FA 2W-3L-1T → 裁判 J1 B·明顯 / J2 B·明顯 ⇒ adopted B → **miss** 〔not executed〕
- 2026-06-12 (1d) `watch` watch Curtis Mead vs Albies → 機械比數 FA 2W-4L-0T → 裁判 J1 B·明顯 / J2 B·明顯 ⇒ adopted B → **hit** 〔not executed〕
- 2026-06-12 (1d) `watch` watch Joc Pederson vs Dubón → 機械比數 FA 2W-1L-3T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **miss** 〔not executed〕
- 2026-06-12 (1d) `watch` watch Samuel Basallo vs Albies → 機械比數 FA 3W-2L-1T → 裁判 J1 B·明顯 / J2 B·明顯 ⇒ adopted B → **hit** 〔not executed〕
- 2026-06-13 (1d) `replace/取代` add Cam Smith ⇄ drop Ezequiel Duran → 機械比數 FA 3W-3L-0T → 裁判 J1 A·明顯 / J2 A·勉強 ⇒ adopted A → **hit** 〔not executed〕
- 2026-06-13 (4d) `replace/取代` add Isaac Paredes ⇄ drop Ozzie Albies → 機械比數 FA 3W-2L-1T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **hit** 〔not executed〕
- 2026-06-13 (1d) `watch` watch Joc Pederson vs Albies → 機械比數 FA 4W-2L-0T → 裁判 J1 A·勉強 / J2 A·勉強 ⇒ 難分 → **hit** 〔not executed〕
- 2026-06-13 (1d) `watch` watch Kody Clemens vs Duran/Albies → 機械比數 no data → **no-data** 〔executed 2026-06-15〕（unresolved id: Duran/Albies）
- 2026-06-14 (1d) `replace/取代` add Kody Clemens ⇄ drop Ezequiel Duran → 機械比數 FA 5W-0L-1T → 裁判 J1 A·明顯 / J2 A·明顯 ⇒ adopted A → **hit** 〔executed 2026-06-15〕
- 2026-06-14 (1d) `watch` watch Spencer Torkelson vs Mauricio Dubón → 機械比數 FA 1W-3L-2T → 裁判 J1 B·明顯 / J2 B·明顯 ⇒ adopted B → **hit** 〔not executed〕

