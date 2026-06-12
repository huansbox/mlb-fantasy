# fa_scan 評斷框架升級腦力激盪 — 7x7 適配訊號（2026-06-12）

> **任務性質**：純研究探索，不動任何程式碼。產出方式 = multi-agent workflow（3 個 ground agent 盤點現況 / 6 個 lens brainstorm agent 各自上網查證 2024-2026 sabermetrics 進展 / 3 個 domain critic 去重 + 可行性審查），45 個提案合併為 36 項評估。
> **本文件是裁決素材**：所有 verdict（adopt_now / pilot / research_more / reject）為 AI 建議，未經用戶裁決前不進 PRD、不動 code。
> ⚠️ 文中「已實測」指本次 workflow agent 當下驗證（endpoint 回 200 / CSV 可下載等）。實作 session 仍須重新驗證（`feedback_no_hardcode_facts` 鐵律：不憑記憶 hardcode 事實）。

## 1. 問題定義

用戶需求原文：「夠好、夠差的球員其實容易判斷，關鍵是找出潛力股（比如今年的 Jordan Walker 就是 AI 挑到的好例子），以及在幾個不那麼好也不那麼壞當中找出更好的。」

拆成兩個子問題：

- **問題 A（breakout 偵測）**：在聯盟注意到之前找到被低估的球員。
- **問題 B（murky middle 鑑別）**：在幾個 P40-P60 之間的球員中，判斷誰對「這個 7x7 格式 + 這套陣容」相對更有價值。

### Jordan Walker 案例的張力（本次研究的起點）

- 03-30 進 watchlist（3% owned）、04-01 執行加入。
- 決勝訊號：23 歲 post-hype top prospect、休季 Driveline 揮棒重建（新聞訊號）、STL 承諾每日 RF 先發、84th percentile sprint speed、2025 HH% 50%（P90 原始擊球力 + 墊底產出 = 潛力未兌現型）。
- **他的 2025 數據（OPS .584 / xwOBA .278）在現行百分位框架會被打到接近墊底**；上述決勝訊號全部是現行框架的 NON-SIGNAL。
- 結論：這次成功 100% 來自 LLM/news 側的自由推理，機械層零貢獻。本次任務 = 把這個成功的可重複部分機械化。

## 2. 核心診斷：現行框架的四個結構性盲區

### 盲區 1 — 核心指標全是「結果落後型」（outcome-lagging）

打者 3 指標（xwOBA / BB% / Barrel%）與 SP 5-slot 都是「結果已經發生」的確認型指標，且 BBE<40（打者）/ BBE<30（SP）排除窗把樣本不足者整批消音。**breakout 的母群體（新升上 / 角色轉換 / 揮棒重建 / 新球種）恰好就是樣本不足者** — 等指標確認時 %owned 已經起飛。物理層訊號（bat speed、max EV、velocity、pitch mix）在 10-30 BBE 就有意義，但框架一個都沒有。

### 盲區 2 — Sum 量的是泛用品質，不是 7x7 類別邊際價值

- P55 contact 型與 P55 TTO 型 Sum 相同，但 BB/HR/AVG 類別產出完全不同 → murky middle 無從鑑別。
- 百分位表是 vs 全 MLB 2025，**沒有 replacement level 概念**（vs 本聯盟 FA 池當下還剩什麼）。
- 格式怪癖未被利用：BB 獨立類別 + OPS 的 OBP 端雙重計算、打者無 K 懲罰、IP 獨立類別 — 市場（多為 5x5 玩家）對這些 profile 的定價系統性偏低。

### 盲區 3 — 量（PA / start count）是所有 counting 類別的乘數，但框架幾乎只看 rate

Arraez→Pederson 06-03 案：系統推薦 P95/P95 的 Pederson 取代 P55/P0 的 Arraez，執行後實測 **-28% 週 PA**（platoon 強側 vs everyday）。7 個打者類別中 5 個是 counting；SP 端 IP/W/K/QS 全部隨先發場次線性放大，而 fa_scan 對「這位 SP 下週投 1 場還是 2 場」完全盲目（用戶自己在 memory 手動追 Skubal/Sale 單雙週 cadence — 證明需求存在）。

### 盲區 4 — 系統失憶（statelessness）

每天的 LLM call 不知道自己昨天說過什麼：Sheets A-plan→B-plan→drop 連鎖每天從零推理、Arraez 連續數週每天產生 drop 噪音、Clemens「立即行動」urgency 是 LLM 自創（不在 prompt 設計內）。這些不是推理失敗，是無狀態失敗 — 換更強的 model 也不會好。

### 案例庫摘要（ground agent 重建）

| 案例 | 結果 | 教訓 |
|------|------|------|
| Jordan Walker add 04-01 | 成功 | 決勝訊號全在框架外（pedigree / news / role / sprint speed）|
| Spencer Horwitz add 05-28 | 成功 | 雙年 BB% P95 + 極低 K% 的 contact 突破型 — 框架有抓到，但靠 outcome 確認，偏晚（9% rising 才動）|
| Cam Smith recovery 05-30 | 成功 | 14d K% 回落 + OPS 反彈雙條件 gate 有效 |
| Arraez→Pederson 06-03 | 失敗 | -28% 週 PA；platoon / 量訊號完全缺席（issue 034 只補了粗略 PA-TG gap tag）|
| Gavin Sheets 降級連鎖 06-04 | 誤判 | 品質衰退（Savant Δ-0.082/7d）被 LLM 敘事成「BABIP 有利」— 當時無 wOBA−xwOBA 運氣量化（issue 035 已補）|
| Kody Clemens 05-12~19 | 延遲 | 機械觸發了但「立即行動」不在輸出 schema，7 天才執行（幸虧聯盟慢，5% owned 沒被搶）|
| Tovar 換 Correa 04-27 | 無對帳 | 交易 out/in 配對從無 backtest — 換得值不值永遠不知道 |

> 橫向確認：**backtest 迴路是一切的前置**（C1，已在 `issues/prd-fa-scan-batter-quality.md` 027-037 進行中）。沒有 hit-rate 量尺，以下任何新訊號上線都是 dark experiment。

## 3. 提案總覽（45 → 合併為 36 項評估）

### 3.1 adopt_now（9 項）— critic 認定資料已驗證、成本小、直接命中已記錄的失敗模式

| 提案 | 範圍/問題 | 一句話機制 | Effort |
|------|------|------|------|
| `chase-zone-discipline-delta` | batter/雙 | chase% + zone-contact% 加進**現有** leaderboard fetch 欄位（agent 實測 `fetch_savant_custom` selections 可直加），BB% 的上游先行指標（~50-60 PA 就穩定，BB% 本身要 170+ PA）| 半天 |
| `post-hype-pedigree-flag` | batter/A | top-100 prospect 名單靜態 JSON（每年一次）+ mlb_id dict join + 年齡 → 一行 tag，給 LLM「折價爛 prior」的授權 — 直接反制「2025 低+2026 低=結構性 cut」對 post-hype 的誤殺（反 Walker 失敗模式）| 數小時 |
| `platoon-share-classifier` | batter/雙 | boxscore battingOrder × 對方先發 pitchHand → everyday / 強側 platoon / 弱側 / bench 分類 + 下週先發數投影 — Arraez→Pederson 失敗的直接機械化修復 | 2-3 天 |
| `sp-two-start-volume-projector` | sp/B | 從輪值 cadence + 球隊賽程 + probables 推算下週先發場次 {0,1,2} × per-start 向量（IP/K/QS/W 期望）— SP 端最大的類別邊際鑑別器，同時機械化週四 Min-40-IP 檢查 | 1-2 週末 |
| `csw-rolling` | sp/雙 | 21d CSW%（called + swinging strikes / pitches）from **已在硬碟上**的 pitch-level rows — 現行 Whiff% 是 season 快照且漏 called strike，無任何 rolling K 先行指標 | 幾個晚上 |
| `velo-delta-watch` | sp/A | 球速三窗 delta（YoY / 21d / 最近一場）— +1.0 mph YoY = 突破前兆；最近一場 -1.5 mph = 傷勢先行（保護自家 SP 的 ratio，目前 SP 端零傷勢 proxy）。Mike Fast：YoY 每 1 mph ≈ 0.28 ERA runs | 幾個晚上 |
| `kbb-small-sample-ladder` | sp/A | BBE<30 死區從「純棄權」改為 K-BB%（per BF）階梯 + 明示 stabilization 框架（K% ~70 BF / BB% ~170 BF 可信）— breakout SP 正是在 1-4 場先發窗被別隊撿走 | 1-2 晚 |
| `marginal-swap-vector` | both/B | 候選 vs **指名 incumbent** 的逐類別週 delta 向量（`swap X→Y/week: BB +2.1, HR +0.4, AVG -0.006, PA -7`）— murky middle 的字面解答；PA 欄讓量損失無法被忽略 | 1-2 天 |
| `verdict-ledger-per-player-memory`（併 stability-gate）| both/B | 每球員結構化 verdict 帳本注入 payload（`prev: watch, 3d ago, 理由 X`）+ 翻供必須指認變因 + 連 2 天同 verdict 才升級 ACT NOW — 修盲區 4，gate 可被 backtest 證偽 | 2-3 天 |

### 3.2 pilot（18 項）— 高價值但門檻/假設未經自家驗證，先小規模驗證

| 提案 | 範圍/問題 | 一句話機制 | 備註 |
|------|------|------|------|
| `ros-projection-prior` | both/A | FanGraphs ROS projections（ZiPS/Steamer）JSON nightly fetch，重點欄位 = **projection−production gap**（投影 wOBA − 當季 xwOBA，大正值 = 系統性 prior 看好但當季未兌現 = Walker 型 buy-low）| **問題 A 最大單一解**。Agent 實測 `fangraphs.com/api/projections?type=rzips` 回 200 免 auth。但離開「純觀察制」哲學 + 非官方 endpoint 會斷，需 staleness alarm + A/B 窗 → 見 §7 裁決點 1 |
| `bat-speed-swing-rebuild-delta`（併 max-ev-jump）| batter/A | Savant bat-tracking CSV 週抓：YoY bat speed / swing length delta + maxEV/EV90 跳升 — 揮棒重建的物理偵測（Walker Driveline 機制機械化），10-30 BBE 即有意義 | 門檻（+1.5mph 等）借自文章未經自家回測 → 先 2025 retro 驗證 |
| `expected-weekly-pa-projection`（併 forward-pa-volume）| batter/B | 週 PA 投影 = 球隊下週場次 × 手性 start share × PA/G → 換算逐類別週期望 | 依賴 platoon classifier，先建那個 |
| `fa-pool-replacement-baseline` + `category-z-fit-score` | system/B | 每日從 FA 池算 per-category replacement level + SD → punt-weighted z-sum 取代 Sum 作排序鍵（Sum 留作 eligibility filter）| 兩者合建（baseline 是分母）。週投影算式是未驗證假設堆疊 → 先 re-rank 歷史 archive 比對 |
| `matchup-contested-weighting` | system/B | 把 CLAUDE.md contested 類別框架機械化：scoreboard 分類 14 類 → 權重向量 → WeekFitScore 與 season score 並列 | 依賴 z-fit；「週戰術混進日掃描」介面問題見 §7 裁決點 4 |
| `process-change-news-miner` | both/A | 機械預篩「有工具沒結果」名單（HH%/Barrel% ≥P70 + xwOBA ≤P40 + 年齡 ≤26 + owned <15%，≤8 人）→ 每週 1 次 batched news call 抽結構化 tag（swing_rebuild / new_pitch / role_change，需附 source URL）| 系統化 Walker 的 news 機制、成本有界。但吃 6/15 後 claude -p credit pool → 見 §7 裁決點 3。Retro 驗證：預篩名單必須包含 3 月底的 Walker |
| `pass-audit-rescan` | system/A | 週 cron 回掃 60 天內 pass/結案球員的後續 21d 實際產出，跨門檻且仍 ≤15% owned → 帶「曾 pass 現在打臉中」tag 重注入候選池 | 自我驗證（回掃本身就是 backtest）；重注入觸發需搭結構性 co-signal 防 hot-streak 噪音 |
| `new-pitch-mix-delta` | sp/A | 三窗 pitch_type usage 比對 → NEW_PITCH / MIX_SHIFT tag（新球種 = 現代 SP breakout 經典機制）| Savant pitch_type 跨季 relabel（slider/sweeper）會產生假 NEW_PITCH → 先量 2024→2025 誤報率 |
| `rp-to-sp-stretchout-detector` | sp/A | game log 逐場 pitch count / IP ramp 偵測（30→50→70+）→ 在 Rotation Gate 放行**之前**以 watch 行先曝光 — Gate 是正確性過濾器但同時是 breakout 盲區 | 誤報源：bulk reliever、復健 ramp → 需一季觀察期 |
| `lineup-slot-tracker` | batter/雙 | boxscore battingOrder → 先發率 + 打序趨勢（上移 = 教練信心先行訊號，Walker「每日 RF」的機械版）| 與 platoon classifier 共用 fetcher，作第二消費者，不單獨建 |
| `schedule-window-strength` | batter/B | 下週場次數（5-7 場 = ±15% 量）+ 主客場 | 場次數一半近乎 adopt 級；對手強度那半訊號弱、先緩 |
| `aaa-dominance-callup-flag` | batter/A | BBE<40 的 FA 撈 2026 AAA 線（sportId=11）+ 升上後先發率 → 把盲窗從「無訊號」變「用最好的可得 prior 定價」| AAA→MLB 翻譯噪音需校準；stash 雷達半部已剔除（3 BN 格太貴）|
| `pull-air-fb-rate` | batter/雙 | 拉打飛球%（HR 的方向軸，Barrel% 看不見：66% 的 HR 來自 pulled air）| season 版用 leaderboard 便宜先做；14d 版需新 per-player fetch，緩議 |
| `hidden-decline-proxy` | batter/B | 14d EV90 / bat speed 下滑警示（隱性傷勢的物理通道，補 K% spike 之外）| 數據已在硬碟（roster 球員）；maxEV 是極值統計易誤報 → 以 EV90 為主 |
| `owned-velocity-curvature` | batter/A | 品質-市場背離 flag（14d xwOBA 上升而 %owned 持平 = 聯盟還沒注意 = Walker-at-3% 條件）| 零新 fetch（純既有 snapshot 計算）；加速度（二階差分）噪音大列實驗性 |
| `park-factor-overlay` | both/雙 | Savant park factors 月抓（頁內 `var data=` JSON，agent 實測可 parse）→ 主場 HR/runs index tag + 「換環境」breakout flag | 順帶修正一個現行錯誤假設：**Savant xwOBA 只用 EV/LA、不做 park 調整**（現行 NON-SIGNAL 注記寫反了）|
| `w-team-context`（併 2 案）| sp/B | 球隊 R/G + bullpen 品質 → W 環境 3-bucket tag — 把規則文件自己寫的「強隊 SP 有 W 加成」first 次量化 | W 單場變異極大，tiebreaker 級，低優先 |
| `team-context-multiplier` | both/B | R/RBI 環境（隊 R/G）+ W 環境（隊勝率）index | 同上家族最低優先；與既有 counting 實績有雙重計算風險 |

### 3.3 research_more（8 項）— 先用歷史資料做回溯研究，通過才寫 production code

| 提案 | 一句話 | 先做的回溯研究 |
|------|------|------|
| `stuff-plus-botstuff-fetch` | FanGraphs Stuff+/PitchingBot — BBE<30 死區理論最佳解（~80 球就穩定）| **可行性實測失敗**：agent 當場 curl 被 Cloudflare 擋。除非找到穩定合法取得路徑（會員 API / 手動週匯出），否則擱置 |
| `confidence-calibration-loop` | verdict 加 confidence + driver 欄位 → C1 分桶 hit-rate 回饋進 prompt | 欄位先加（近零成本、未來免疫）；回饋迴路等每桶 n≥20 才開（目前 verdict 量會做出 n=9 的假校準表）|
| `spring-extreme-watchlist-seed` | 春訓極端表現（ISO ≥.300 等）3 月播種 watchlist — 用戶 memory 已認可此訊號 | 現在就能回測：拉 2026 春訓資料，看名單對 4-6 月實際的命中率；通過則 2027 年 2 月建 |
| `xhr-park-gap` | HR−xHR 缺口（球場圍牆幾何的類別級 buy-low）| 對 Barrel% + wOBA−xwOBA 的增量資訊未證明 → 先回歸驗證殘差顯著才動 |
| `sb-opportunity-model` | sprint speed × 綠燈率 × 上壘頻率 → 週 SB 期望 tag | 先數 2026 至今有幾週 SB 真的 contested（gap≤5）；≥30% 才值得建 |
| `format-arbitrage-gap` | V_7x7 − V_5x5 雙重估值差 → 市場結構性錯價名單 | 疑似冗餘（BB% + %owned 已在 payload）→ 先驗證它能抓到現有篩選漏掉的人 |
| `position-eligibility-arbitrage` | 守位覆蓋矩陣 × 邊際可先發場次 | 「守位不進評估」是現行明示設計選擇非疏忽；先 audit 過去 10 次 add 有幾次真被 slot 卡到 |
| `arm-angle-delta` | 出手角度 YoY ≥5° = 重造訊號 | 證據是個案不是量化研究；若 new-pitch-mix pilot 通過，併入它的 process-change tag，不單獨建 |

### 3.4 reject（1 項）

- `cross-platform-ownership-divergence`（ESPN/CBS 跨平台 ownership 背離）：非官方 cookie-auth API + 無正式證據的社群傳說 + 單人維護者最該拒絕的脆弱度 profile。若未來自家 Yahoo snapshot archive 證明 1-3 天 timing alpha 存在且被錯過，再議。

## 4. 三個 critic 各自的 top 3（九大重點）

### Batter critic top 3

1. **`platoon-share-classifier`** — murky middle 最強項：直接機械化已量化的 Arraez→Pederson -28% PA 失敗（issue 034 只是粗補丁）。boxscore battingOrder + pitchHand endpoint 皆 agent 實測免費可用。platoon 角色季中黏性高 → 分類有預測性、不是追 streak。驗證：重放 Pederson 案 + 2025 boxscores，分類標籤 vs 實際後續 21d PA。
2. **`chase-zone-discipline-delta`** — 性價比最高：同一張已在抓的 CSV 加欄位。chase ~50-60 PA 穩定，是 BB%（本格式雙重計算的最高槓桿類別）的上游。驗證：2025 歷史資料 — 早季 chase delta 預測全季 BB% 是否優於早季 BB% 自身。
3. **`bat-speed-swing-rebuild-delta`** — 正面攻擊 Walker 盲區：現行三核心指標全是落後型且 BBE<40 全消音；bat speed/maxEV 在 10-30 BBE 就有意義。pilot 而非 adopt 的唯一原因：門檻數字未經自家驗證。

### SP critic top 3

1. **`sp-two-start-volume-projector`** — 清單上最大的類別專屬鑑別器：IP 是獨立類別、QS/K/W 隨場次線性放大、40 IP 週下限目前靠週四手查。所有 fetcher 已存在（stream_sp_scan / mlb_query）。驗證：純機械回測 — 用過去每週一可得的資料投影場次 vs 實際 game log，準確率 ≥85% 才上線。
2. **`csw-rolling`** — 零新 fetch（description 欄已在每日下載的 rows 裡）；CSW 預測未來 K% 優於 SwStr% 是已重複驗證的公開研究，過得了本專案 no-hot-streak 證據門檻。注意 21d ≈ 4 場先發低於 ~10 場穩定點 → 永遠只作 context 行、不進 Sum。
3. **`velo-delta-watch`** — 公開 sabermetrics 中重複驗證最好的物理訊號（Fast: YoY 每 mph ≈ 0.28 ERA runs）；同時補上 SP 端目前完全沒有的傷勢先行指標，保護的是自家 roster 的 ERA/WHIP，價值超出 FA 掃描。

### System critic top 3

1. **`marginal-swap-vector`** — 全場最強提案：H2H 類別賽的 add/drop 本質是「候選 − 指名 incumbent」的逐類別差，不是「整體誰較好」。純本地計算、~10 行 payload、零新 endpoint。即使 per-PA rate 粗糙，光 PA 欄就修掉量盲區。驗證：對 2026 全部已執行 swap 回算向量，確認 Arraez/Pederson 案會被標出。
2. **`ros-projection-prior`** — 問題 A 的最佳單一解：Walker 的 2025 實績在百分位框架近墊底，但帶 pedigree/aging prior 的 ZiPS 投影是聯盟平均以上 — 這正是缺的那塊 prior。風險：非官方 endpoint + 哲學變更，需 staleness alarm + A/B 窗 + payload 控制在 2-3 欄。
3. **`verdict-ledger-per-player-memory`** — 修的是模型升級也救不了的無狀態失敗（Sheets / Arraez / Clemens 全是）。自產資料、複用 issue 028 的 CLOSE parse、gate 可證偽（2 天穩定 verdict 的 hit-rate vs day-1 — 無分離就拆掉）。注意「翻供必須指認變因」prompt 規則要寫得極簡，避免誘發 thinking tokens（lever 2 教訓）。

## 5. 橫向洞見（主題層）

1. **Leading vs lagging 是本次最大主軸**。現行框架是一台「確認機」：等結果發生、樣本夠了才說話 — 對問題 A 結構性遲到。六個 lens 不約而同把答案指向三類先行訊號：物理層（bat speed / velo / pitch mix，BBE 10-30 即有效）、過程層（chase% / CSW%，比結果型指標快 2-3 倍穩定）、prior 層（pedigree / 投影，樣本為零時就有值）。
2. **量是被系統性忽略的乘數**。13/14 個類別與 PA 或先發場次成正比，而現行框架 95% 的注意力在 rate 品質。`platoon-share` + `expected-weekly-pa` + `two-start-projector` 三件組是「同一個修復的打者版與 SP 版」。
3. **失憶是獨立於聰明度的缺陷**。verdict ledger 家族不增加任何「判斷力」，只是讓系統記得自己 — 但案例庫顯示它修掉的失敗數量不亞於任何指標升級。
4. **資料源新事實**（本次 agent 實測，實作時需複驗）：
   - ✅ FanGraphs ROS projections API（`/api/projections?type=rzips`）免費免 auth、回 200。
   - ❌ FanGraphs Stuff+ leaders API 被 Cloudflare challenge 擋下（headless VPS 大概率不可用）。
   - ✅ Savant bat-tracking / arm-angle / basestealing / park-factors 皆可免費取得（CSV 或頁內 JSON）。
   - ✅ MLB Stats API boxscore `battingOrder`（slot+先發/替補）、`/people` pitchHand、sportId=11（AAA）皆 live 驗證。
   - ⚠️ 更正一個現行框架的錯誤假設：**Savant xwOBA 不做 park adjustment**（只用 EV/LA），「已 context-neutral」的 NON-SIGNAL 注記不成立 — Barrel%→HR 轉換在 index_hr 70-130 的球場間有實質扭曲。
5. **成本紀律貫穿所有 verdict**：幾乎所有 adopt/pilot 提案的 payload 形式都是「每人一行 tag」；news-miner 用機械預篩把貴的 news call 限制在每週 ≤8 人一次。被 reject/降級的提案多數正是因為脆弱資料源或 payload 膨脹。

## 6. 建議 roadmap（波次）

- **Wave 0（前置，已在進行）**：完成 C1 backtest（PRD 027-037，只剩 037）。所有新訊號的驗證路徑都掛在這把尺上 —「先建尺再調刀」維持不變。
- **Wave 1（速贏包 = adopt_now 9 項，可再分批）**：
  - 近零成本組（合計 ~2 天）：`chase-zone-discipline-delta`、`post-hype-pedigree-flag`、`kbb-small-sample-ladder`。
  - SP rolling 組（共用已下載 pitch rows，~1 週晚上）：`csw-rolling`、`velo-delta-watch`。
  - 量修復組（共用 boxscore/schedule fetcher）：`platoon-share-classifier` → `sp-two-start-volume-projector`。
  - 系統組：`marginal-swap-vector`（搭最簡 projection 算術）、`verdict-ledger`。
- **Wave 2（pilot，各帶自己的驗證 gate）**：`ros-projection-prior`（先過 §7 裁決點 1）、`bat-speed-swing-rebuild-delta`（先 2025 retro 校門檻）、`expected-weekly-pa-projection`（platoon classifier 上線後）、replacement-baseline + z-fit（先 re-rank 歷史 archive）、`process-change-news-miner`（先過裁決點 3 + retro 確認預篩抓得到 Walker）、`pass-audit-rescan`。
- **Wave 3（回溯研究批）**：research_more 8 項全部「先用手上歷史資料做一次性研究、出數字再決定」— 其中 `spring-extreme` 與 `sb-opportunity` 的回溯研究本身只要數小時。
- **共用模組提醒**：boxscore lineup fetcher（platoon + slot tracker 共用）、週投影算術（z-fit + swap-vector + PA projection 共用）、verdict parse（ledger + pass-audit + C1 共用）— 實作排序時先建共用件。

## 7. 尚待決定（用戶裁決點）

1. **哲學變更**：引入 ROS projections = 離開「純觀察制」設計（NON-SIGNAL 裡的明示選擇）。要不要開這個門？critic 建議：開，但以「projection−production gap」單一欄位 + A/B 窗進入，不是整包投影。
2. **payload 預算上限**：每提案 +1 行 × N 提案，與 payload 瘦身計畫（issue 032/033 剛砍完）方向相反。建議定一個 tag 總行數上限（如每候選 ≤3 行新 tag），超過就要有東西讓位。
3. **news-miner 的 credit pool**：6/15 起 claude -p 吃獨立 $100/月 pool，news-miner 每週一次 call 約 $1-2/月 — 量小但要列入 pool 預算盤點。
4. **週戰術 vs 季構建的介面**：matchup-contested-weighting 把 scoreboard 即時權重帶進每日掃描，雙分數（season/week）設計會倍增解讀面。另一條路：留在 /weekly-review 與週四手動檢查，fa_scan 維持季視角。
5. **與現行 PRD 的排序**：本文件全部提案都排在 037 之後？還是 Wave 1 近零成本組（半天級）可以插隊？

## 附錄：方法論紀錄

- Workflow run id `wf_b32b5dc9-6e9`（2026-06-12）：12 agents / ~997K subagent tokens / 9 分鐘。
- Ground 層輸出（現況訊號全量盤點 36 項 + NON-SIGNAL 17 項 / 案例庫 11 案 / 資料源地圖）已濃縮進 §2、§5；完整 JSON 不另存檔（複現成本低於維護成本）。
- Critic 評準：是否真的動 14 類別之一或兩大問題之一 / 資料是否真免費可達（關鍵聲稱當場 curl 驗證）/ 是否通過專案既有教訓（no hot-streak 無證據、no BvP、樣本紀律、payload 成本、事實必驗證）。
