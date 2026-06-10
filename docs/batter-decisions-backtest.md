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
- **outcome 語意**：骨架階段一律 `pending-judge`。裁判合議（issue 030：2 位裁判同指示獨立、強制二選一 + 明顯/勉強標註、合議表）上線後升級為 hit / miss / 難分：
  - **replace 帳**：FA 明顯較好 → hit（量「太衝動」病的反面）
  - **watch 帳**（鏡像）：FA 明顯較好 → **看走眼**（太保守）；難分或 vs 較好 → 看對
- **執行標註**（issue 031，已上線）：每筆帳標「是否實際執行」— 由 `roster_config.json` git 歷史機械判定（**不靠人工**）：執行窗 = episode 首日 → 末日 + 3 天 grace（涵蓋 FA add 隔日生效與 waiver claim Daily-Tomorrow 延遲生效，如 06-02 Buehler 案）。比對 **mlb_id 優先**（id 已解析時同名不同 id 不算執行 — 防同名誤判）、id 未解析才退 name 比對。狀態：`executed`（窗內進名單）/ `not-executed`（窗內未進）/ `already-rostered`（窗前已在名單，罕見）/ `unknown`（git 歷史不足以確立窗前不在籍，寧可 unknown 不給錯的 False）。週報含 executed / not-executed 分組 hit-rate（030 裁判上線前分母為 0 顯示「—」）— 量「人工否決是在加值還是誤殺好建議」（PRD user story 9）。

## 更新紀錄

- **2026-06-10 創建**（issue 029 骨架）：解析 + episode + 六類別比數 + 週日 cron 端到端；outcome 全 pending-judge。
- **2026-06-10 執行標註上線**（issue 031）：每筆帳補 executed 欄位（roster git 歷史機械判定）+ 週報 executed / not-executed 分組 hit-rate 行。真實歷史 spot-check 三例皆正確（Rafaela 06-07 add → executed / Pederson 被搶 → not-executed / Arraez 長期在籍 → already-rostered）。
- 後續：issue 030 裁判合議升級（pending-judge → hit/miss/難分，分組 hit-rate 隨之自動出現數值）。
