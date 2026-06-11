# PRD — fa_scan Batter 判斷品質 + 決策對帳回路（主 issue）

> 2026-06-10 定稿。來源：`docs/fa-scan-batter-judgment-quality.md`（品質研究 + C1 十題 grill-me 定案）+ `docs/fa-scan-batter-payload-optimization.md`（token 成本篇之 ②③④ 併入）。切法已經 agent 依 vertical-slice 原則審查修正並切分為 `issues/027`-`037`（8 AFK / 3 HITL）。
> **本檔為此計畫的主 issue** — 之後每個 session 開工先讀下方「進度看板」了解目標 / 當前進度 / handoff，完工後回寫狀態。

## 進度看板（session 開工先讀本段）

**工作協議**：挑 issue 前先看「開工順序」與 Blocked by → 開工時把狀態改 🔧 → 完工 merge 後改 ✅ 並附日期 + commit hash → 更新下方 Handoff 段（最後更新日期 + 一行現況）。

### 狀態

| Issue | Type | Blocked by | 狀態 |
|---|---|---|---|
| [`027-sp-backtest-repair-e2e`](027-sp-backtest-repair-e2e.md) | AFK | 無 | ✅ 2026-06-10（merge `4daefa7`） |
| [`028-waiver-log-grammar-extension`](028-waiver-log-grammar-extension.md) | HITL | 無（**最優先部署**） | ✅ 2026-06-10（merge `c549fe0`，已部署） |
| [`029-batter-backtest-skeleton`](029-batter-backtest-skeleton.md) | AFK | 027, 028 | ✅ 2026-06-10（merge `0e94cf7`） |
| [`030-judge-panel-verdicts`](030-judge-panel-verdicts.md) | HITL | 029 | ✅ 2026-06-10（merge `b9a8e4d`；殘留觀察：07-05 首個非空段再抽查一次） |
| [`031-execution-annotation`](031-execution-annotation.md) | AFK | 029（可與 030 平行） | ✅ 2026-06-10（雲端 session 完工，merge `ae8cb46`） |
| [`032-payload-history-truncation`](032-payload-history-truncation.md) | AFK | 無（軟排序在 028 後） | ✅ 2026-06-10（merge `d18207e`）；**隔日驗證 ✅ 2026-06-11**（issue #311：（中略 N 行）+ [機械計數] 行皆現） |
| [`033-payload-hygiene-pack`](033-payload-hygiene-pack.md) | AFK | 無 | ✅ 2026-06-10（merge `fc55fae`）；**隔日驗證 ✅ 2026-06-11**（payload 五項逐項可見 + cost 下降） |
| [`034-pa-tg-gap-warn-tag`](034-pa-tg-gap-warn-tag.md) | AFK | 無 | ✅ 2026-06-10（merge `57abeec`）；**隔日驗證 ✅ 2026-06-11**（FA/watch 多人帶 ⚠️ 上場量落差 tag） |
| [`035-woba-xwoba-luck-field`](035-woba-xwoba-luck-field.md) | AFK | 無 | ✅ 2026-06-10（merge `8a651ae`）；**隔日驗證 ✅ 2026-06-11**（season 顯著標記 + 14d 列值 + legend 行皆現，LLM 已引用入判斷） |
| [`036-fa-sort-key-debias`](036-fa-sort-key-debias.md) | AFK | 無 | ✅ 2026-06-10（雲端 session 完工，PR #308 merge `7e8bc91`）；**隔日驗證 ✅ 2026-06-11**（FA 順序 87→1% 嚴格降序） |
| [`037-trigger-schema-constraint`](037-trigger-schema-constraint.md) | HITL | 028（同 prompt 分批上線） | ⏳ 未開工 |

### 開工順序（曆法長竿驅動）

1. **028 最先做、最先部署** — batter 對帳只能讀新文法的帳，**部署日 + 21 天才有第一筆帳齡達標的帳**，它擋著全計畫關鍵路徑。部署日記錄到下方 Handoff。
2. **027 並行** — 無依賴；修好後既有週日 cron 自動開始產出真 SP 對帳資料。
3. **033-036 隨時可塞** — 四片獨立 AFK 小片。
4. **029 在 027+028 合併後開工**（fixture 先行開發，cron 上線後等資料熟，「0 筆可對帳」= 合格 demo）→ **030 / 031 接續**。
5. **032 在 028 上線後重測省幅**（結案自動化會先縮小歷史段）、**037 殿後**（與 028 分批，A/B 歸因隔離）。

### Handoff（最後更新：2026-06-11）

- **032-036 隔日 production 驗證全過（2026-06-11，對象 issue #311 + VPS transcript）**：① 032 — 觀察中段全部長歷史條目折疊為「（中略 N 行）」、Cam Smith 帶 `[機械計數] counter day 0/3（引自 06-10）`；② 033 — 視窗註記 + 運氣 legend 兩行、watch 球員真 %owned（Cam Smith 12% 等）、prior 行 PA+年齡、Heriberto 14d Savant「樣本不足 (BBE 13 <15)」；③ 034 — Teoscar/Basallo/Jeffers/Mead/Pederson/Meckler + watch 多人帶 ⚠️ 上場量落差 tag，且 LLM 確實用它擋了立即取代（Mead/Basallo 留觀察）；④ 035 — season「運氣 +0.040(顯著)」格式正確、14d 只列值，LLM 判斷大量引用（Arraez/Albies 泡沫、Steer buy-low）；⑤ 036 — FA 10 人 87/53/52/50/48/33/26/7/3/1% 嚴格降序。**Cost spot-check**：batter call cache 寫入 41.3K→21.4K（−48%）、output 13.1K→7.1K（−46%），無 thinking 誘發反噬。⑥ 028 CLOSE 鏈端到端首次在 production 走通：LLM 發 `CLOSE|Gavin Sheets` → 寫入端即時搬已結案（VPS log + waiver-log.md 皆證實）。**唯一未開工：037**。

- **033 / 034 / 035 / 036 同日完工（2026-06-10）— payload 誠實度 + 去偏四片全上**。共同剩餘驗證：**6/11 12:30 cron 後看 production batter issue** ① payload 逐項可見（視窗註記 + 運氣 legend 兩行、watch 真 %owned 或 `?%`、prior 行 PA+年齡、BBE<15 樣本不足、符合條件 FA 的 ⚠️ 上場量落差、Season/14d 運氣欄、FA 順序 = %owned 降序）② cost spot-check（input/output tokens 與前日同量級 — 新增行均為靜態資料字典類，非判斷規則，lever 2 風險低但仍要看）。035 注意：我方 roster 的 14d 運氣欄要等 VPS savant_rolling cron（TW 12:00）以新 code 跑過一輪；FA 端即時計算當天即有。剩餘未開工：**037**（觸發 schema 約束，HITL，需與 028 分批 A/B — 至此 11 片唯一未完）。
- **032 完工（2026-06-10，merge `d18207e`）— payload 觀察歷史讀取端截斷 + 機械 counter 摘要行**：`truncate_watch_history`（觸發 + [eval] + 最近 5 日行保留，連續省略 run 折疊為（中略 N 行））+ `compute_history_counters`（`counter day X/N（引自 MM-DD）` 僅引最近 5 日行內 token、過窗 stale 不引用；`已連續建議結案 N 個掃描日` 從完整歷史算）。注入順序 filter → inject_replace_streaks（028）→ truncate（counter 先推導後截斷）。僅 batter 路徑、零 prompt 變動。凍結 fixture 實測觀察中段 −59.7%（18,295 → 7,366 chars）。18 tests，全套 770 綠。**剩餘驗證：6/11 12:30 cron 後看 payload 觀察中段（中略 N 行）+ [機械計數] 行 + cost 較前日下降**（issue 存檔 raw 段可直接看）。注意：032 上線後 payload doc 建議 ②（建議結案自動化）的省幅前提已部分被 028 CLOSE + 032 截斷吃掉，若再評估以新基線量。
- **035 完工（2026-06-10，merge `8a651ae`）— 打者運氣欄位**：`fa_compute.compute_woba_gap` 純函式（gap = wOBA−xwOBA，BBE floor 參數化：season 40 / 14d 15）；顯著門檻 0.023 = 2025 |gap| P70（`calc_woba_gap_pctiles.py` 推導，bip ≥50 n=486，記錄於 CLAUDE.md 百分位表段）；season woba 從 expected CSV 順手抽、14d woba 從逐球 CSV `woba_value/woba_denom` 聚合；14d 只列值不標顯著（噪音基底不可比）。22 tests。
- **034 完工（2026-06-10，merge `57abeec`）— PA-TG 落差警示 tag**：`fa_compute.pa_tg_gap_warn` 純函式（anchor − FA ≥1.0 → `⚠️ 上場量落差 (PA-TG x vs anchor y)`，缺值/反向不打），wire 在 `compute_fa_tags` win gate 兩側（watch/pass 條目也可見）；一般 ⚠️ → 擋 立即取代。Pederson fixture（3.06 vs 4.27）+ 邊界 10 tests。**剩餘驗證：6/11 cron 後看符合條件 FA 是否帶 tag**。
- **033 完工（2026-06-10，merge `fc55fae`）— payload hygiene 包五項**：① watch %owned 真值（`_check_player_ownership` 改 `out=percent_owned,ownership`，回傳 `{ownership_type, pct, status}`；未知留 None 顯示 `?%`，不再假 0%）② FA prior 行補 PA（savant 2025 pa，mlb fallback）+ 年齡（`_fetch_ages_bulk` 一次 bulk `/people` call）③ 14d Savant BBE<15 印「樣本不足」不印 xwOBA/Δ（`_fmt_14d_savant_line` anchor+FA 共用，floor 常數 `_SAVANT_14D_BBE_FLOOR`）④ payload 開頭視窗註記行（場次窗 vs 日曆窗）⑤ prompt 補「%owned 為 Yahoo 全平台值」+「?% = 未知非 0%」靜態說明。20 tests（`tests/test_fa_scan_payload_hygiene.py`）。**剩餘驗證：6/11 12:30 cron 後看 production issue payload 逐項可見 + cost spot-check（input/output tokens 與前日同量級）**。
- **036 完工（2026-06-10，雲端 session，PR #308，merge `7e8bc91`）**：FA 打者候選呈現順序由 vs-P1 `sum_diff` 降序改 **%owned 降序**（外部市場訊號，與系統自身 verdict 正交）— 消除「P1 弱時整批機械分差膨脹、注意力順序被偏置」。抽純函式 `_sort_fa_by_owned`（name-asc tiebreak / 缺 pct 排末 / pct=0 視為真值），8 單測 `tests/test_fa_sort_key.py`。`pct` 來自 snapshot `percent_owned`，經 `_normalize_fa_for_compute` 帶上 fa_tagged。剩餘驗收：部署後隔日 issue payload 順序符合新鍵。
- **現況**：**029 完工 merge（`0e94cf7`，2026-06-10）— batter 對帳骨架端到端打穿**：`_backtest_lib` 新增 batter 純函式層（028 文法 verdict 解析：ACTION→replace / 7 欄 NEW 帶 vs→watch，UPDATE/CLOSE/舊 6 欄不可對帳；episode key 取代/立即取代不拆帳；byDateRange 解析含「重複相同 splits」API quirk 去重 + 跨隊交易比率重算；六類別比數 R/HR/RBI/BB/AVG/OPS 無 SB）+ `backtest_batter.py` CLI（outcome 一律 pending-judge，週報 append `docs/batter-decisions-backtest.md`）+ `cron_backtest.sh` 擴充週日一次跑 SP + batter（單邊失敗仍 commit 健康側）。41 tests；對真實 archive dry-run 過（42 天 ~80 份 issue body 零誤報、輸出「0 筆可對帳」段 = 合格骨架輸出）。**曆法預期：batter 首筆新文法帳 = 2026-06-11 cron 產生，帳齡 21 達標日 ~07-02，首個可能非空週日段 = 2026-07-05**；SP 端首個非空 regular 段仍 = 2026-06-21；06-14 兩邊 0 筆屬正確行為。VPS 無需手動部署（每日 cron pull 會在 06-14 前帶上新 wrapper）。**030（裁判合議，HITL）/ 031（執行標註，AFK，可與 030 平行）已解鎖**。029 解析端注意：真實 production 新文法 issue（06-11 起）出現後，應補一份真實 production fixture 進 `test_backtest_batter.py`（目前新文法用 028 配對 A/B 的真實 LLM 輸出 `ab_028_b_result.json` 代位）。027 詳情：三破洞全修（header 定位 + 平衡大括號解析 / Savant outcome 補實 + MLB API id fallback / 帳齡 [21,28) episode 對帳）、5 個真實 issue fixture（#254/259/276/280/305）。028 詳情見下方「028 部署日」段。~~既存無關失敗：`test_pending_parser` 的活檔 fixture 漂移~~（✅ 2026-06-10 已修：當時內容凍結為 `tests/fixtures/stream_sp_pending_2026-05-26.md`，測試不再讀活檔；全套 752 綠）。
- **030 完工（2026-06-10，merge `b9a8e4d`）— 對帳回路全鏈打通（027→028→029→031→030 五片皆 ✅）**：pending-judge 升級 2 位裁判合議 verdict。純函式層 `build_judge_payload`（匿名 A/B、claim-blind、無 PA/G）/ `parse_judge_response`（強制二選一契約）/ `judge_consensus`（16 組合窮舉單測）/ `map_judge_outcome`（watch 鏡像：採用 A → miss、餘含難分 → hit 計分母）；邊界層 `run_judge_panel`（整週 1 payload × 2 judges claude -p neutral cwd，每週固定 2 calls + 各 1 retry，fail-open 留 pending-judge + ⚠️ 週報行）。週報每帳並列機械比數 + J1/J2 + 合議（稽核底稿）+ 命中率行（replace 量太衝動 / watch 量太保守）。第一批真 claude 抽查通過（真實 05-15→06-04 產出兩帳，零 retry、無唱反調；重測工具 `_tools/_judge_demo_runner.py`）。VPS 零部署動作（cron pull 自帶；cron PATH 已驗證含 claude）。**殘留觀察：07-05 首個非空 production 段出來後再人工抽查一次**（勉強/難分路徑尚未被真裁判走過）。31 tests（`tests/test_judge_panel.py`）。
- **031 完工（2026-06-10，雲端 session，merge `ae8cb46`）**：executed 判定純函式（`_backtest_lib.judge_executed` + `parse_roster_snapshot`，mlb_id 優先防同名、歷史不足 → unknown 不給錯 False）+ git 邊界 `fetch_roster_timeline`（baseline = since 前最後 commit）+ row `executed`/`execution` 欄位 + 週報「Executed split」行（hit/miss 進分母即自動有值）。真實歷史 spot-check 三例正確（Rafaela executed / Pederson not-executed / Arraez already-rostered）。測試獨立檔 `tests/test_execution_annotation.py`（26 cases）。詳見 031 issue「實作備註」。
- **決策依據去哪讀**：完整發現 + C1 十題定案總表在 `docs/fa-scan-batter-judgment-quality.md`（動 027-030 前先讀）；payload 量測 + 截斷 A/B 證據在 `docs/fa-scan-batter-payload-optimization.md`（動 032-033 前先讀）。
- **已驗證事實（不用重查）**：SP backtest 三破洞 — ① verdict regex 對真實 issue body（#305）實測不匹配（JSON 被 code fence + `</details>` 包住）② outcome fetch 是 `return None` stub ③ `--days 7` 取帳在 21 天觀察窗未走完就對帳；issue 存檔 raw 段含完整 waiver-log 區塊（#306 可直接當 fixture）。
- **鐵律提醒**：解析測試 fixture 必須 `gh issue view --json body` 真實存檔，禁止手寫樣本（SP「測試全綠、production 全敗」教訓）；prompt 變更必配對 A/B 看 output_tokens（lever 2）；本機禁跑 Yahoo-touching 腳本（PreToolUse hook 會擋，VPS 指令走 `bin/vps-run.sh`）。
- **028 部署日**：**2026-06-10**（首筆新文法帳 06-11 cron 產生 → 帳齡 21 達標 ~07-02 → 029 **首個可能非空週日段 = 2026-07-05**）。文法定版（HITL 三題皆選推薦案）：ACTION 行只在取代/立即取代時出（觀察 vs 由 NEW 新欄帶）；CLOSE 整條連歷史搬移；vs 欄插在觸發條件後、摘要前（7 欄，6 欄舊格式向後相容）。配對 A/B 證據：output_tokens +52% 但可見輸出 +48% 等比成長（tokens/char 4.87→5.00 持平，非 lever 2 thinking 誘發）、核心決策一致（P1 Arraez + Pederson 立即取代兩邊同）、B 的 CLOSE 建議與 06-10 手動結案完全吻合；真實 B 輸出 round-trip 新寫入端 = 11 UPDATE 落地 + 7 條 stale CLOSE 優雅 SKIP。Runner 在 `daily-advisor/_tools/_ab_028_runner.py`（037 A/B 可重用）；raw A/B 輸出檔（`_tools/ab_028_A/B.json`）已 2026-06-10 清理 — B 全文以 `daily-advisor/tests/fixtures/ab_028_b_result.json` 入庫（029 解析 fixture），A 未入庫（證據結論已記於本段）。**部署後驗證**：6/11 12:30 cron 第一班看 production issue 區塊出現新行型 + waiver-log 寫入無解析錯誤（Telegram 報警覆蓋）。**既存小毛病（非 028 造成，待小修）**：球員條目已在「已結案」段時 NEW/UPDATE 會殭屍寫入到已結案條目下（如 Pederson 被搶條目下的 06-09/06-10 行）— 修法 = NEW/UPDATE 查找範圍限縮觀察中＋隊上觀察。

## Problem Statement

我每天依 fa_scan 自動產出的打者 FA 建議做 add/drop 決策，但有三個結構性問題讓我無法信任、也無法改善這套系統：

1. **我不知道建議的歷史命中率，所有調整都在盲調。** SP 端的對帳（backtest）系統已部署兩週，但實際一筆帳都沒對過 — verdict 解析規則與 production 報告格式不匹配（兩班週日 cron 全輸出「no verdicts」）、後續表現查詢是永遠回空值的 stub、取帳邏輯會在 21 天觀察窗還沒走完時就對帳。打者端連對帳系統都不存在。沒有命中率，我無法回答「這個 prompt 改動是進步還是退步」「模型降級品質掉多少」。

2. **建議的判斷品質有已實證的盲區，根因是餵給 LLM 的資料不誠實。** watch 球員顯示捏造的 0% 持有率；FA 的前一年數據缺樣本量與年齡（breakout 真假無從判斷）；沒有上場量落差警示（已實證建議用平台型打者換掉每日先發，週打席量 -28% 無人攔截）；打者沒有運氣量化訊號（BABIP 噪音 vs 真品質變化全靠 LLM 腦補）；14 天 Savant 小樣本噪音直接印出；兩種「14d」視窗（最近 14 場 vs 日曆 14 天）基底不一致且無標註。

3. **觀察清單只進不出，機械工作被錯誤地交給 LLM。** LLM 每天自發輸出結案建議，但「結案」根本不在 prompt 的輸出設計內，所以永遠接不到執行機制 — 同樣 6 人的結案建議連續輸出 7+ 天；「連 N 天」計數由 LLM 自己從 30 行歷史數，已實證誤數；觀察歷史段佔 payload 72%、每日複利成長。

## Solution

建立一條可信的決策對帳回路，並把 payload 修誠實、把機械工作移回程式：

- **對帳回路（最高槓桿，先建尺再調刀）**：修復 SP 對帳的三個破洞、為打者新建對帳，共用同一套引擎。打者建議的對錯由「建議日後 21 天的實際產出」判定 — 六個聯賽類別（R/HR/RBI/BB/AVG/OPS，不含 SB），交兩位 LLM 裁判強制二選一 + 幅度標註合議，難分的帳保留模糊空間。「觀察」建議鏡像對帳（該撿沒撿 = 看走眼），沒執行的建議也照樣對帳並標註執行狀態。每週日自動產出對帳週報。
- **報告輸出結構化**：建議紀錄區塊的文法擴充（vs 對象欄位、每日判斷顯式行、結案指令行），讓對帳有可靠的讀取來源、讓結案建議直接接上自動執行。
- **payload 誠實度修復**：假值修真（watch %owned）、缺值補齊（prior 樣本量 + 年齡）、新訊號（上場量落差警示、wOBA−xwOBA 運氣欄位）、噪音治理（小樣本 gate、視窗標註、%owned 語意說明）。
- **機械工作回收**：「連 N 天」計數由程式算好注入、觀察歷史機械截斷（觸發 + 里程碑 + 最近 5 天 + 機械摘要行）、FA 呈現順序去除 vs-P1 機械偏置、觸發條件約束為機械可判定的文法。

## User Stories

1. 作為聯賽管理者，我想知道 fa_scan 撿人建議的歷史命中率，以便判斷該多信任每天的建議。
2. 作為聯賽管理者，我想讓 SP 對帳系統真的對出帳來（而非每週「no verdicts」），以便已部署的監控機制開始產生價值。
3. 作為聯賽管理者，我想讓對帳只發生在觀察窗走完的建議上（帳齡 21-28 天），以便命中率不被「窗未走完就對帳」的假數據污染。
4. 作為聯賽管理者，我想讓連續多天重複的同一筆建議只對一次帳（episode 去重），以便命中率不被重複計數灌水。
5. 作為聯賽管理者，我想用實際產出（R/HR/RBI/BB/AVG/OPS，無 SB）判定撿人建議的對錯，以便量尺對齊聯賽真實計分方式與我的 punt SB 策略。
6. 作為聯賽管理者，我想讓兩位 LLM 裁判（強制二選一 + 明顯/勉強標註）合議產出判定，以便幅度差異（RBI 20 vs 5 ≠ HR 3 vs 4）不被二元類別比數抹平、又保留「難分」的模糊空間。
7. 作為聯賽管理者，我想看到機械類別比數與裁判判定並列記錄，以便日後稽核裁判是否系統性失準。
8. 作為聯賽管理者，我想讓「觀察」建議也被鏡像對帳（21 天後明顯該撿 = 看走眼），以便同時量到系統「太衝動」與「太保守」兩種病。
9. 作為聯賽管理者，我想讓沒執行的建議也照樣對帳並標註是否實際執行，以便量系統判斷力之餘、也能量我人工否決的加值或誤殺。
10. 作為聯賽管理者，我想每週日自動收到打者對帳週報（獨立紀錄檔），以便週一 weekly-review 與 SP 週報一起檢視。
11. 作為聯賽管理者，我想讓報告對「取代/觀察」建議記下明確的 vs 對象，以便對帳系統知道該拿誰跟誰比。
12. 作為聯賽管理者，我想讓「已在追蹤中、當天升級成取代」的建議也被結構化記錄，以便升級事件不再隱形漏帳。
13. 作為聯賽管理者，我想讓 LLM 的結案建議變成正式指令並自動執行搬移，以便觀察清單不再只進不出。
14. 作為聯賽管理者，我想讓「連 N 天」類計數由程式計算並注入 payload，以便不再出現 LLM 數歷史數錯的情況。
15. 作為聯賽管理者，我想讓 payload 的觀察歷史被機械截斷（觸發 + 里程碑 + 最近 5 天 + 機械摘要行），以便停止每日複利成長、同時保留觸發紀律所需資訊。
16. 作為聯賽管理者，我想讓 watch 球員顯示真實 %owned 而非假 0%，以便聯盟動態判讀不再建立在捏造數字上。
17. 作為聯賽管理者，我想讓 FA 的前一年數據附樣本量（PA）與年齡，以便 breakout 真假判斷有先驗可依。
18. 作為聯賽管理者，我想讓 14d Savant 樣本不足（BBE 過低）時不顯示或標註，以便不依賴 LLM「每次都記得」去 discount 噪音。
19. 作為聯賽管理者，我想讓兩種「14d」視窗（最近 14 場 vs 日曆 14 天）被標註區分，以便 Δ 比較不再有隱形的基底錯位。
20. 作為聯賽管理者，我想讓 prompt 說明 %owned 是 Yahoo 全平台值非本聯盟，以便不再出現「57% 不可能是 FA」的誤讀。
21. 作為聯賽管理者，我想在 FA 與其比較對象的上場量（PA/Team_G）落差過大時收到機械警示 tag，以便「品質好但上場少」的換人建議（platoon 陷阱）被攔截。
22. 作為聯賽管理者，我想看到打者的 wOBA−xwOBA 運氣訊號（season + 14d），以便 BABIP 噪音 vs 真品質變化有量化依據。
23. 作為聯賽管理者，我想讓 FA 候選的呈現順序改用與系統自身判斷無關的排序鍵，以便 P1 特別弱時不會整批候選的注意力順序被機械分差膨脹。
24. 作為聯賽管理者，我想讓觀察觸發條件被約束為「既有欄位 + 明確比較 + 明確視窗」，以便隔天的 LLM 與未來的機械 counter 能無歧義判定觸發是否達成。
25. 作為系統維護者，我想讓所有解析類測試使用真實 issue 存檔當 fixture，以便不再發生「測試全綠、production 全敗」。
26. 作為系統維護者，我想讓每個涉及 prompt 的變更都附配對 A/B 驗證，以便 thinking 誘發型成本暴增（lever 2 前車之鑑）在部署前被攔截。
27. 作為系統維護者，我想讓對帳引擎的核心邏輯是純函式 + 注入式資料源，以便在本機不碰 Yahoo/LLM 的情況下完整測試。

## Implementation Decisions

### 對帳引擎（修 SP + 建 batter，共用零件）

- **SP 修復三件**：① verdict 解析改為能穿過 code fence 與摺疊標籤的真實格式解析；② 後續表現查詢補完（接上既有 Savant rolling 抓取，xwOBACON 21 天窗）；③ 取帳邏輯改為「帳齡 21-28 天」窗口 — 每筆建議恰好對帳一次、且必在觀察窗走完後。
- **Episode 去重為共用純函式**：同一組「撿 Y 丟 X」連續多天出現 = 一個 episode，從首日起算觀察窗。SP 與打者共用，落在共用對帳函式庫，不寫兩遍。
- **打者 verdict 來源 = 建議紀錄區塊**（報告尾端既有的機器可讀區塊，已完整存於每日 issue 檔案庫），不寫自由文字解析器。
- **打者 hit 判定**：建議日後 21 天，兩位球員的六類別實際產出（R/HR/RBI/BB/AVG/OPS，無 SB）；**不給裁判 PA** — 上場量已自然反映在累積項，附 PA 反而誘導折算腦補。
- **裁判合議契約**：兩位裁判同一份指示、各自獨立、強制二選一（A/B 誰較好）+「明顯/勉強」標註。合議表：同人 + 至少一位明顯 → 採用；同人 + 雙勉強 → 難分；分歧 → 難分。整週帳打包成每位裁判 1 次呼叫（每週固定 2 次）。機械類別比數照記但不參與判定，作裁判稽核底稿。
- **觀察類鏡像判定**：觀察 = 宣稱「Y 還沒明顯好過 X」。21 天後合議 Y 明顯較好 → 看走眼（太保守）；難分或 X 較好 → 看對。與撿人命中率（太衝動）成對解讀。
- **執行標註**：每筆帳標「是否實際執行」，由名單設定檔的 git 歷史機械判定（建議日後短窗內 Y 是否進入我方名單），不靠人工。
- **排程與輸出**：共用既有週日對帳 cron 班次，一次跑 SP + 打者；打者寫獨立對帳紀錄檔（兩邊 hit 定義不同，不混一份）；週報段落格式仿 SP 既有版式，另含 executed / not-executed 分組命中率。
- **裁判呼叫經 claude -p，自 neutral cwd 跑**（沿用 lever 1a 部署模式，避免 harness 載入專案脈絡的固定開銷）。

### 建議紀錄區塊文法擴充（同一波 prompt + 解析端變更）

- **NEW 行補「vs 對象」欄位**：取代與觀察類建議記下比較對象。
- **新增 ACTION 行**（`ACTION|球員|取代類型|vs對象`）：每日 actionable 判斷顯式化 — 解決「球員已在追蹤中、當天才升級成取代」時只有 UPDATE 行、升級事件隱形的盲點。
- **新增 CLOSE 行**（`CLOSE|球員|理由`）：結案從 LLM 自發行為變成正式輸出契約，寫入端自動把對應條目搬到已結案段。取代 payload 成本篇原規劃的「偵測連 3 天結案字樣」方案。
- **連續推薦警示改機械**：prompt 中「已推薦 N 天未執行」的計數改由程式從區塊歷史算好注入，LLM 只引用。
- 文法細節（欄位順序、分隔符相容性）在實作 issue 內定版；解析端對新舊兩種格式向後相容（舊 issue 無新欄位仍可解析其餘行型）。

### 機械工作回收

- **機械 counter 摘要行**：每條觀察條目由程式注入一行 derived 摘要（counter day X/N、已連續建議結案 N 天、已推薦取代 N 天），LLM 不再自己數。
- **payload 讀取端歷史截斷**：waiver-log 檔案不動，只在組裝 payload 時對每條觀察保留觸發條件 + 里程碑（[eval]）行 + 最近 5 天，其餘以一行「中略 N 行」標記（A/B 已實證：payload −46%、核心決策不變）。截斷與 counter 摘要行同一片交付（摘要行正是截斷的品質緩解）。

### Payload 誠實度

- **watch %owned 真值**：watch 球員的持有率改從既有的逐人 ownership 查詢一併取得（該查詢本來就每天打、只是把持有率欄位丟掉了），消除假 0%。
- **FA prior 補 PA + 年齡**：與我方候選區塊的呈現對稱。
- **14d Savant BBE gate**：樣本低於門檻不顯示或標「樣本不足」。
- **視窗標註**：兩種 14d（場次窗 vs 日曆窗）在 payload 標示區分。
- **%owned 語意說明**：prompt 加一行靜態資料字典說明（全平台值非本聯盟）— 屬不誘發 thinking 的說明行，仍附 cost spot-check。
- **PA-TG 落差警示 tag**：FA 與其比較 anchor 的 PA/Team_G 差距達門檻（初版 ≥1.0）時打機械警示 tag。
- **wOBA−xwOBA 運氣欄位**：season 與 14d 各補實際 vs 預期的 gap 數字；顯著門檻由 2025 分布推導（沿用既有百分位計算腳本模式），低 BBE 抑制。

### 判斷流程去偏

- **FA 排序鍵去 sum_diff**：呈現順序改 **%owned 降序**（與系統自身判斷無關的外部市場訊號），消除 vs-P1 機械分差的注意力偏置。
- **觸發條件 schema 約束**：prompt 約束觀察觸發條件只能引用 payload 既有欄位 + 明確比較運算 + 明確視窗。屬「往 prompt 加判斷規則」類變更，需配對 A/B，且與文法擴充分開上線（A/B 歸因乾淨）。

### 上線順序的硬約束（曆法長竿）

- **文法擴充必須最早上線**：打者對帳只能讀新文法的帳，部署後要等 21 天才有第一筆帳齡達標的帳。曆法時間 > 工程時間。
- **對帳骨架先行、裁判後接**：骨架先以機械類別比數輸出 pending-judge 狀態走通全程（cron → 週報），裁判片再把 pending-judge 升級為合議判定。骨架上線初期輸出「0 筆可對帳」屬合格交付。
- **prompt 變更分批上線**：文法擴充與觸發 schema 約束不同批，各自配對 A/B。

## Testing Decisions

- **好測試的定義**：只測外部行為（輸入 → 輸出契約），不測實作細節；純函式直測、外部資料源（Yahoo / Savant / MLB API / claude -p / gh）一律注入式邊界。
- **真實 fixture 鐵律**：所有解析類測試（issue 存檔 → verdict、區塊行 → 寫入動作）的 fixture 必須取自真實 production issue 存檔，禁止手寫模板樣本。這是 SP 對帳「測試全綠、production 全敗」的直接教訓，寫入相關 issue 的驗收條件。
- **受測模組**：對帳引擎全部純函式層（verdict 解析、episode 去重、帳齡選擇、六類別窗口聚合、合議函式含組合窮舉、鏡像方向、執行標註判定）；區塊文法解析端（含新舊格式相容）；歷史截斷函式；counter 摘要行；PA-TG tag 與 luck 欄位計算；新排序鍵。
- **不強制單測**：cron wrapper、報表 markdown 渲染、LLM 呼叫邊界（以 dry-run / 人工抽查覆蓋）。
- **Prior art**：repo 既有 TDD 慣例 — 注入 Fetchers 端到端（stream-sp / rp-svh 掃描測試）、fixture 回歸（fa_compute 測試）、真實 git repo 整合測試（git 同步測試）。
- **Prompt 變更驗證**：配對 A/B（同 payload、同模型、neutral cwd），看 output_tokens 與決策一致性，不能只看可見文字 — lever 2 教訓的標準作業。

## Out of Scope

- **打者兩段式 LLM（Step A/B 對稱 SP）**：收益不確定、成本確定，待對帳基線建立後另案 A/B。
- **vs L/R splits 重版**（platoon 訊號完整版）：先以 PA-TG 落差 tag 輕版攔截，重版待輕版觀察後另案。
- **Model 降級（Opus→Sonnet/Haiku）**：歸 Phase 2 另案；本 PRD 的對帳回路正是其前置量尺。
- **掃描頻率降低 / 輸出格式收斂 / 我方 drop 池縮減**：成本篇已判定不做（破壞 watch 機制 / lever 2 backfire / hold 判斷 load-bearing）。
- **SP 端 payload 與判斷邏輯改動**：本 PRD 對 SP 只修對帳，不動其評估框架。
- **觸發條件 DSL 完全體**（counter 全機械化 + 無事件日跳過 LLM）：中期選項，schema 約束是其鋪路。
- **emerging-batter skill**：另案進行中。
- **xwOBACON 門檻校準（Use Case B）**：既有待辦，依賴對帳資料累積。

## Further Notes

- **參考文件**：完整發現與證據在 `docs/fa-scan-batter-judgment-quality.md`（含 C1 十題定案總表、SP 空殼三破洞驗證）與 `docs/fa-scan-batter-payload-optimization.md`（payload 解剖 + 截斷 A/B 實測）。
- **切分建議（供 /prd-to-issues 參考，已經 vertical-slice 審查）**：11 片 — ① SP 對帳修復端到端（AFK）② 區塊文法擴充端到端（HITL，**最先上線**）③ 打者對帳骨架端到端（AFK，blocked by ①②）④ 裁判合議端到端（HITL，blocked by ③）⑤ 執行標註（AFK，blocked by ③）⑥ 歷史截斷 + counter 摘要行（AFK）⑦ payload hygiene 包（AFK）⑧ PA-TG 落差 tag（AFK）⑨ wOBA−xwOBA 欄位（AFK）⑩ 排序鍵去偏（AFK）⑪ 觸發 schema 約束（HITL，blocked by ②）。
- **成功判準**：部署完成後 4-6 週，每週日自動產出 SP + 打者兩份非空對帳週報，撿人 / 觀察兩類命中率有可解讀的基線 — 屆時才開始動「訊號擴充是否有效」「模型降級是否可行」這類需要量尺的問題。
- **風險備忘**：裁判合議是新的 LLM 用法，第一批輸出必須人工對照機械比數底稿（系統性唱反調 → 回頭查裁判 prompt）；文法擴充上線後第一週注意 waiver-log 寫入端有無解析錯誤（Telegram 報警既有機制覆蓋）。
