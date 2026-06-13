# PRD: fa_scan 決策執行層 + 量修復改善計畫

> **主 issue = [huansbox/mlb-fantasy#316](https://github.com/huansbox/mlb-fantasy/issues/316)** — 進度看板與切片狀態以 GitHub issue 為準，本檔為規格凍結快照（spec 定稿後不常變）。
> 依據：[`docs/fa-scan-eval-brainstorm-7x7.md`](../docs/fa-scan-eval-brainstorm-7x7.md)（36 項提案評估）+ [`docs/fa-scan-decision-retrospective-2026h1.md`](../docs/fa-scan-decision-retrospective-2026h1.md)（全季回溯實證）+ 2026-06-13 grill-me 九題對齊 + agent 依 prd-to-issues 原則的模組審查。
> 下一步：`/prd-to-issues` 切片（草案見 Further Notes，最終以該輪為準）。

## Problem Statement

我每天靠 fa_scan 的自動建議做 add/drop，全季回溯（2026-03-25 ~ 06-12）證明：系統「找人」的眼睛已經及格（add 端 ~8/10 命中、structure-led 路徑整批有效），但「手」不及格，三型失誤反覆發生：

1. **Churn（最貴）**：撿對的人幾天後被換掉 — Hicks 持有 7 天（之後 30 天 .892/6HR/25RBI）、Clemens 9 天（之後系統天天推薦撿回）、Steer 被換隔天系統就後悔。系統對「自己 9 天前為什麼撿這個人」零記憶。
2. **執行洞（次貴）**：觸發達成、系統明確建議，但沒人執行 — Vargas（.945/8HR，全季最大漏接）、O'Hearn、Horwitz、Manzardo、Crawford 合計漏接 ~5 名 .85+ OPS 球員。建議淹沒在每日報告裡，沒有強度分級、沒有後續追蹤。
3. **量盲區**：系統只看打擊品質不看上場量 — Arraez→Pederson 換完才發現 -28% 週 PA（platoon 強側）；SP 端對「下週投 1 場還是 2 場」全盲（IP 是獨立類別、QS/K/W 隨場次線性放大）。

同時，每日通知若無強度分級會「狼來了」：回溯顯示真正該即刻行動的等級 2.5 個月只出現 ~6 次，其餘都是觀察級。

## Solution

給系統補上「手」：記憶、分級、追蹤、量感知 — 全部機械層實作，不增加 LLM 判斷負擔：

1. **決策記事本（decision ledger）**：每球員的歷次 verdict + 當初撿人理由 + 發現路徑（structure/heat/market/news，**首次接觸時持久化**，星等只讀不重判）。drop 建議必須面對「當初撿他的理由失效了嗎」。
2. **機械星等（1-5★，pre-LLM 決定論公式）**：發現路徑 / 雙年確認 / 上場量 / 觸發完成度四因子；day-0 新候選用三因子變體（上限 4★）。星等公式以回溯案例集校準：Vargas/Horwitz/O'Hearn 型必須 ≥4★，Sheets/Pederson 型必須 ≤3★。
3. **慢快軌 gate（post-LLM 純函式，零 prompt 變更）**：放人一律慢軌（連 2 天同建議 + 面對原 add 理由）；撿人預設慢軌，5★ 或 %owned 急升走快軌。
4. **通知政策**：只有 4★+ 發 Telegram；5★ 未執行逐日升級提醒（搭既有 12:30 scan，零新 cron）；「已執行」語意 = 當前 roster_config（roster_sync 15 分保鮮；waiver pending 造成 ≤1 天假升級為已知可接受）。weekly-review 自動列出未處理建議清單。
5. **量修復**：platoon 偵測（everyday/強側/弱側/bench tag）+ 下週 PA 投影（賽程 × 對手 SP 慣用手）+ SP 下週先發場次 {0,1,2} 投影 + 換人逐類別週差額表（只給 4★+ 候選；共用一個週投影算術模組）。
6. **五個近零成本欄位**：chase/zone-contact delta（打者）、post-hype 新秀標記（靜態年度 JSON，每年 3 月人工更新 30 分）、K-BB% 小樣本快篩（SP）、CSW% 21d 滾動（SP）、球速 delta（SP，突破+傷勢雙向）。
7. **一次性 legacy backfill**：存量 watchlist 從 git 歷史/觸發文字推回發現路徑（推不出標 unknown 取中性分）；既有 roster 球員以上線日季線快照充當 add 理由基準 — 上線第一天就保護全名單。
8. **成本三規**：每候選新增 ≤3 行（跨片累積預算，ledger 注入片 owns enforcement 點 + 既有行讓位規則）；差額表只給 4★+；每片上線前後量測 payload input + output tokens。

## User Stories

1. As a 聯盟經理, I want 系統記住每位球員的歷次判斷與當初撿人理由, so that drop 建議不會無視九天前自己的 add 理由（Hicks/Clemens/Steer 型反悔歸零）。
2. As a 聯盟經理, I want drop 類建議連續 2 天一致才升級為行動級, so that 單日噪音不會推動我換掉撿對的人。
3. As a 聯盟經理, I want 每個行動級建議帶機械星等（1-5★）與因子明細, so that 我一眼知道這是 Vargas 級還是觀察級。
4. As a 聯盟經理, I want 只有 4★ 以上才推 Telegram, so that 通知不會狼來了（預估每月 2-4 次）。
5. As a 聯盟經理, I want 5★ 建議未執行時逐日升級提醒（含「第 N 天未執行」）, so that Vargas 型漏接不再發生。
6. As a 聯盟經理, I want 撿人建議在 %owned 急升或 5★ 時走快軌即刻通知, so that 確認天數不會讓好貨被搶（O'Hearn/Horwitz 型）。
7. As a 聯盟經理, I want 我人工否決的建議被記錄為「已處理」, so that 系統不會對同一否決反覆糾纏（Arraez 框架偏見型），且否決紀錄可供日後對帳。
8. As a 聯盟經理, I want weekly-review 自動列出本週「已建議未處理」清單, so that 漏接在週級就被撈回，不必等季後檢討。
9. As a 聯盟經理, I want 候選的發現路徑（實力浮上來 vs 手感浮上來）在首次接觸時被永久標記, so that heat-led 候選（Sheets/Pederson 型）被強制提高證據門檻、且不會因養出季線而洗白。
10. As a 聯盟經理, I want 打者候選帶 platoon 標籤（everyday/強側/弱側/bench）, so that 我不會再換進一個 -28% 週 PA 的強側平台球員而不自知。
11. As a 聯盟經理, I want 候選與被換者的「下週預期 PA」投影（賽程 × 對手先發慣用手）, so that 量的差距在換人前就攤在桌上。
12. As a 聯盟經理, I want SP 候選帶「下週投 1 場還是 2 場」投影, so that 量是 SP 換人決策的第一排序鍵（IP/QS/K/W 全隨場次放大），且週四 Min-40-IP 檢查被機械化。
13. As a 聯盟經理, I want 4★+ 候選附「vs 指名被換者」的逐類別週差額表（含 PA 欄）, so that add/drop 是類別空間的具體交換，不是抽象的「整體誰較好」。
14. As a 聯盟經理, I want 打者的 chase/zone-contact 年度變化欄位, so that 選球進化/崩壞比 BB% 早幾週可見。
15. As a 聯盟經理, I want 前百大新秀出身 + 年輕 + 過往成績差的候選帶 post-hype 標記, so that 下一個 Walker 不會被雙年低分誤殺；我接受每年 3 月 30 分鐘人工更新名單。
16. As a 聯盟經理, I want BBE<30 的 SP 候選顯示 K-BB% 快篩 + 樣本可信度框架, so that 新升上的 SP 在 1-4 場先發窗就能被分級而不是整批棄權。
17. As a 聯盟經理, I want SP 的 21 天 CSW% 滾動值與球速 delta（YoY / 21d / 最近一場）, so that 三振能力變化與傷勢前兆比結果指標早幾週可見，自家 SP 的比率類別也受保護。
18. As a 聯盟經理, I want 存量 watchlist 與既有 roster 在機制上線日就有 backfill 的路徑/理由紀錄, so that 新保護對當下名單立即生效，不是只罩未來新人。
19. As a 系統維護者, I want 每片上線前後的 payload input/output token 量測紀錄, so that 成本回潮與 thinking 誘發（lever 2 教訓）當場可見。
20. As a 系統維護者, I want 每候選新增行數有跨片累積預算（≤3 行）與讓位規則的單一 enforcement 點, so that 八片各自合規加總卻爆線的事不會發生。
21. As a 系統維護者, I want 星等寫進 backtest 資料列、ledger 記錄執行時間戳, so that 週日 backtest cron 能對帳「4★/5★ 命中率是否顯著高於 3★」與「觸發→執行中位天數」兩個 KPI。
22. As a 系統維護者, I want 星等公式的回溯案例集（Vargas/Horwitz/O'Hearn ≥4★、Sheets/Pederson ≤3★）作為固定 fixture, so that 公式調整時有不可回退的校準錨點。

## Implementation Decisions

**模組切割**（經 agent 依 prd-to-issues tracer-bullet 原則審查修正）：

- **decision_ledger 拆三片**：
  - L-a（AFK）：ledger JSON 寫入路徑（與 waiver-log 同一寫入點 derive，單一真相源；032 的歷史計數行未來改讀 ledger 或明文分工）+ payload 注入（prev verdict 行 + 原 add 理由行）+ 發現路徑判定（pool assembly 時依候選來源持久化）+ 行數預算 enforcement + legacy backfill 一次性腳本。
  - L-b（AFK）：`gate(history, verdict, stars, owned_trend) → action_level` 純函式（慢快軌）+ 報告渲染 + 4★ Telegram / 5★ 逐日升級（notify_policy 併入此片）+ weekly-review 未處理清單消費端。
  - L-c（HITL）：prompt 契約（「翻供必須指認變因」「drop 須回應原 add 理由」）— lever 2 風險正主，配對 A/B + 人工審，與 037 分批上線隔離歸因。
- **star_rating（AFK）**：pre-LLM 決定論公式。四因子 = 發現路徑（structure +1 / market·news·unknown +0.5 / heat +0）、雙年確認（prior 核心 ≥2 項 P70+ 且樣本足 +1 / 部分 +0.5 / 無 +0）、上場量（PA/TG ≥3.5 +1 / 2.5-3.5 +0.5 / <2.5 +0；SP 以 IP/GS + Rotation Gate 對應）、觸發完成度（全達成 +1 / 部分 +0.5）；stars = 1 + round(Σ)。day-0 變體：三因子按比例放大、上限 4★（5★ 必須經觸發驗證）。確切門檻在實作片內以回溯案例集校準定案 — 公式本身凍結在本 PRD，避免變 HITL。
- **platoon 拆兩片**：P-a（AFK）classifier + tag（boxscore lineup × 對方先發慣用手；按「球隊×日」cache，fetch 次數上限寫進驗收）；P-b（AFK）下週 PA 投影（賽程 × 對手 SP 慣用手份額推估）。
- **sp_start_projector（AFK）**：下週先發場次 {0,1,2} + payload 行；per-start 產出向量移至 swap-SP 片；retro 場次預測準確率 ≥85% 為機器可判驗收 gate。
- **swap_vector 拆兩片 + 共用算術**：週投影算術（per-PA rate × 投影量）獨立成共用純模組，swap-batter（先行，吃 P-b）與 swap-SP（吃 projector）共用；只對 4★+ 候選 emit。
- **micro-fields 按管線拆兩片**：M-bat（chase delta + post-hype JSON join）、M-sp（CSW 21d + velo delta + K-BB ladder）。M-sp 是對前一輪 PRD「SP payload 不動」的**有意 scope 變更**，在此明示。
- **星等/gate 相對 LLM 的位置**：star pre-LLM（payload 預篩依據）、gate post-LLM（建議產出後的行動分級），兩者皆純 Python、零 prompt 變更（prompt 變更獨立在 L-c）。
- **「已執行」語意**：以當前 roster_config 為準（roster_sync 15 分 cron 保鮮）；waiver claim pending 期造成 ≤1 天假升級，接受並文件化，不當 bug 修。
- **KPI owner**：星等寫進 backtest 資料列、ledger 記執行時間戳，由既有週日 backtest cron 計算 KPI（star-bucket 命中率、執行延遲中位數）；regret rate 由 ledger 直接可算。此整合邊明寫，避免重蹈「SP backtest 空殼」。
- **排程**：既有 037 先收掉（結構化觸發文法是本計畫地基），本 PRD 接續；關鍵路徑 037 → L-a → star → L-b，P-a / projector / M-bat / M-sp 可在 037 觀察窗平行動工。
- 資料來源全部為既有 stack（MLB Stats API / Savant 已抓 rows / Yahoo 已抓欄位 / 自產 issue 存檔）；workflow agent 的端點實測在實作時依 no-hardcode-facts 鐵律重驗。

## Testing Decisions

- 好測試 = 只測外部行為不綁實作：純函式核心（gate / star / classifier / projector / swap 算術 / 各 micro field）全部單元測試，照 repo 既有 TDD 慣例（rp_svh_scan 43 cases / stream_sp_scan 72 cases 的 style）；fetcher 一律注入 mock。
- **真實 fixture 鐵律**：解析/注入測試的 fixture 必須取自真實 production 產物（gh issue body / 真 waiver-log 段），禁止手寫樣本 — SP backtest「測試全綠、production 全敗」的教訓。
- **回溯重放驗收**：可機器判定的歷史案例集作為驗收條件 — star 校準集（Vargas/Horwitz/O'Hearn ≥4★、Sheets/Pederson ≤3★）、platoon 重放 Pederson 案、swap-batter 對 2026 全部已執行 swap 回算（Arraez→Pederson 必須被標出）、projector 對季初至今逐週回測 ≥85%。
- prompt 變更（僅 L-c）必配對 A/B 量 output tokens；所有片上線前後量 payload delta。

## Out of Scope

- **Breakout pilot 家族**（ROS projections prior / bat-speed 揮棒重建 / process-change news-miner / AAA 碾壓標記 / pull-air / hidden-decline proxy / owned-velocity 曲率主體 / park factor / team context / matchup contested weighting / pass-audit-rescan）— 腦力激盪 §7 的五裁決點中涉及者一併推遲，待本輪驗收後另開 PRD。快軌例外只消費**既有** %owned delta/shape 欄位，不新建市場訊號。
- **research_more 8 項與 reject 1 項**（Stuff+ / 信心校準迴路 / 春訓種子 / xHR / SB 機會模型 / 格式套利 / 守位套利 / 出手角度 / 跨平台 ownership）。
- **Yahoo API 自動下單**（Q3 的 C 案）— 人工把關有實證價值（Pederson/Caglianone 否決）。
- SP 端 5-6 月 churn 的逐案量化對帳（C1 backtest 既有職責）。
- model 降級、claude -p 成本 Phase 2、百分位表 2026 更新 — 各自既有待辦。

## Further Notes

- **切片草案（12 片，最終以 /prd-to-issues 為準）**：037（既有，先行）→ L-a → star → L-b 為關鍵路徑；P-a、P-b、sp_start_projector、swap-batter、swap-SP、M-bat、M-sp、L-c。AFK 11 / HITL 1（L-c；037 另計）。
- **星等頻率預期**：依回溯，4★+ 事件 ~2-4 次/月 — 若上線後顯著高於此，先懷疑公式而非調通知門檻。
- **驗收 KPI**（上線一個月對帳）：①30 天內反悔事件（add→drop→系統再推薦回）= 0；②行動級建議「首次達標→執行或否決」中位 ≤2 天；③4★/5★ 事後命中率顯著 > 3★；④payload 餵入量增幅 ≤10%。
- 灰色地帶先例：post-hype 年度 JSON 是本系統第一個「需定期人工維護的資料資產」— 若 3 月忘記更新，標記自動降級為 stale 並在報告中註明，不靜默用舊資料。
