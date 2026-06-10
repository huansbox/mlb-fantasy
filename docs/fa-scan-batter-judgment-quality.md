# fa_scan Batter 判斷品質優化 — 研究定稿

> 2026-06-10 探索 session 產出。姊妹篇 [`fa-scan-batter-payload-optimization.md`](fa-scan-batter-payload-optimization.md) 處理 token 成本；本篇處理**同模型下的判斷品質** — 兩篇有 3 個重疊項，對照表見文末。
> 結論先行：**最大品質槓桿不在 prompt 或推理流程，而是 ① payload 有假值與訊號缺口直接誤導判斷、② 「建議結案」根本不在 prompt 設計內（自發行為，必然接不到執行）、③ batter 決策沒有 backtest 回路 — 所有品質調整都在盲調。**

驗證素材：fa_scan.py / fa_compute.py / prompt_fa_scan_pass2_batter.txt / prompt_sp_b2_step_a+b.txt / savant_rolling.py 全鏈 + issue #306（2026-06-10 batter 實際產出）逐項對照。

## A. Payload 訊號缺口（資料層 → 判斷盲區）

### A1. watch 球員 %owned 是捏造的 0%（假值最傷）

- `parse_waiver_log_watchlist()`（fa_scan.py:254）不解析 pct；回填（fa_scan.py:3013-3025）只覆蓋「剛好在 SCAN_QUERIES top-50 snapshot 內」的人，其餘 `w.get("pct", 0)` → 假 0%。
- 實證：#306 Cam Smith 印「0%」（HOU 主力，非真值）；Goldschmidt/Crawford 有真值純屬碰巧在 top-50 內。
- **修法（零額外 API 成本）**：`_check_player_ownership`（fa_scan.py:402-406）本來就對每位 watch 球員打一次 Yahoo API，只取 ownership_type 丟掉 percent_owned — `out=ownership` 改 `out=percent_owned,ownership` 即得真值。
- 與 payload doc 建議 4 的「%owned 為全平台值」誤讀同族：聯盟動態軸建立在錯的數字上。

### A2. FA 的 Prior 2025 沒有 PA — breakout 判斷缺核心變數

- anchor block prior 有 OPS+PA（`_fmt_anchor_block_batter_v4`，fa_scan.py:2606-2616）；FA block 只印 3 個 percentile（`_fmt_fa_block_batter_v4`，fa_scan.py:2695-2703）。不對稱。
- 「單年 breakout vs 結構確認」判斷裡，prior 是 600 PA 的 P0 還是 150 PA 的 P0 意義完全不同。實證：#306 Curtis Mead 被判「prior P40/P0/P0 = breakout 風險極高」，LLM 看不到 2025 樣本量。
- 修法：prior_parts 補 PA（資料已在 `prior_stats` dict）。順手補 **age** 欄價值更高（23 歲二年生跳級 vs 31 歲 fluke 的先驗完全不同）。

### A3. 無 platoon / PA 量落差訊號 — Pederson 案例自證

- 實證：#306 Joc Pederson（典型 platoon 打者，基本只對 RHP 先發）被判「立即取代」Arraez。Pederson PA-TG 3.06 落在 tag 門檻中間（<2.5 警示 / ≥3.5 主力，fa_compute.py:310-352）→ 無 tag；Arraez PA-TG 4.27 → 換人 = **-28% 週 PA 量**，直接吃 R/RBI counting。payload 無 splits、prompt 無 PA 落差概念，LLM 整段 reasoning 沒碰這軸。
- 兩級修法：(輕) 機械層在 FA vs 比較 anchor 的 PA-TG 差 ≥1.0 時打 ⚠️ tag；(重) payload 補 vs L/R PA 占比一行 — 記憶 `project_batter_splits_todo` 已確認 API 可行。

### A4. batter 缺運氣量化訊號（SP 有 xERA-ERA，batter 無對稱件）

- LLM 只能從 AVG 高低腦補 BABIP 噪音。實證：#306 P2 Albies — LLM 寫「AVG .346 = BABIP 偏高、熱度不可持續」，但同行 14d Savant xwOBA Δ+0.021 在上升，兩訊號矛盾時全靠自由裁量。
- 修法：season + 14d 各補 **wOBA−xwOBA gap**（Savant CSV 本有 wOBA），量化「實際 vs 預期」，門檻設計仿 SP luck tag（顯著值 + BBE gate）。

### A5. 兩個「14d」是不同視窗

- trad = 最近 14 **場**（`enrich_14d_trad` 取 `splits[-14:]`，fa_scan.py:1422，約 15-17 日曆天）；Savant rolling = 日曆 14 **天**（savant_rolling.py:179-192 `timedelta(days=14)`）。
- 同球員行內「14d OPS」與「14d Savant Δ」樣本基底不同 → Δ 比較有系統性噪音。修法：統一視窗，或至少 payload 標註。

### A6. 14d Savant BBE gate（= payload doc 建議 4）

- 實證：#306 Torres 14d Savant BBE 14 印 Δ-0.090、Teoscar BBE 1 印 Δ-0.059 — 該日 LLM 有自行 discount，但「每次都記得」不可依賴。
- 修法：機械層 BBE <15 不印或改印「樣本不足」。

## B. 判斷步驟 / 流程結構

### B1. 「建議結案」是 prompt 之外的自發行為 — 接不到執行的根因

- `prompt_fa_scan_pass2_batter.txt` 輸出格式只定義 `NEW|` / `UPDATE|` 兩種行（line 69-85），**沒有任何結案指令**。LLM 每天在 PASS 段自發輸出結案建議（推測模仿 payload 歷史段過往文字）→「連 7+ 天建議結案無人執行」是必然。
- 修法（比 payload doc 建議 2「偵測連 3 天字樣」更乾淨）：prompt 正式定義結案條件 + `CLOSE|球員名|理由` 結構化行，`_update_waiver_log` 機械搬到已結案。行為從「巧合」變「契約」，不用 fuzzy 偵測自由文字。

### B2. 所有「數天數」的工作都該離開 LLM

- counter 誤數已實證（payload doc：Duran day 2/3 誤數）；prompt 的「⚠️ 已推薦 N 天未執行」警示（line 83-85）同樣要 LLM 自己從 30 行歷史數。
- 修法：機械層在每條觀察 entry 注入一行 derived 摘要（「counter day X/N」「已連續建議結案 N 天」「已推薦取代 N 天」），LLM 只引用不計算。= payload doc 建議 3 的 counter 摘要行，但品質動機獨立於 token 動機成立。

### B3. 機械 hint 全 vs P1，LLM 實際建議卻 vs P2/P3

- `compute_fa_tags` 只拿 `weakest_ranked[0]` 當 anchor（fa_scan.py:2856-2880）；FA 候選排序按 vs-P1 sum_diff（fa_scan.py:2748）。
- 實證：#306 Kody Clemens 建議對象是 P2 Albies，但排序提示是 vs Arraez（P1）算的。P1 特別弱時所有 FA hint 一起膨脹，影響 LLM 注意力順序。
- 修法：batter v4 thin 哲學本是「Sum 不暴露、hint 非 verdict」— 可考慮拿掉 sum_diff 排序（改 %owned 或 14d OPS 排序），讓呈現順序不帶機械偏置。

### B4. 觸發條件無 schema，跨日可判定性差

- 實證：#306 寫出「prior-adjusted xwOBA 維持 P90+（BBE ≥150 確認）」— 隔日 LLM 得自行解釋「prior-adjusted」。
- 修法：prompt 約束觸發條件**只能引用 payload 既有欄位 + 明確比較 + 明確視窗**（「14d OPS ≥.850 連 7 天」合格；「品質維持」不合格）。零成本紀律改善，為 B2 機械 counter 鋪路。中期 DSL（payload doc 中期選項）是完全體。

### B5. batter 單 call 無驗證步 — 結構上落後 SP（謹慎）

- SP Step B 被要求「re-read raw、不同意 Step A 要點名衝突」= 內建 self-check；batter 一個 call 直出 P1-P7 + ACTION + 觸發 + 結案，run-to-run 變異已被觀察（P2/P3 互換）。
- 若做：Step A rank+classify JSON → Step B verdict，順帶解 B1 的結案 schema 化。
- **Trade-off**：多一個 call 成本確定、品質收益不確定 + lever 2 教訓（prompt 結構變動誘發 thinking）→ 清單中唯一排最後、需 C1 基線後 A/B 的項目。呼應 CLAUDE.md 待辦「SP/Batter 框架對稱性檢視」。

## C. 品質測量回路（最高槓桿）

### C1. batter 決策沒有 backtest — 所有優化都在盲調

- SP 有 `cron_backtest.sh` 週級 hit-rate + marginal benefit（`docs/sp-decisions-backtest.md`）；batter 的「立即取代/取代/觀察」**沒有任何事後驗證**。
- 沒有 hit-rate 就無法回答「A2 補 PA 後 breakout 誤判率有沒有降」「B3 改排序有沒有差」「model 降級 Sonnet 品質掉多少」（Phase 2 的量尺也是它）。
- 資料都在：fa-scan issue archive 每天存建議 + 完整 raw payload；`backtest_track.py` 模式可複用。
- **建議排在所有訊號優化之前 — 先有尺，再調刀。**

## D. 入口 recall（已有規劃覆蓋，不急）

- SCAN_QUERIES 只取 Yahoo sort=AR top-50（season）+ top-30（biweekly）（fa_scan.py:542-547），AR 偏累積 counting → 剛升上 / 角色剛變的低 rank 球員會漏。
- 已由 %owned risers 注入（fa_scan.py:3047-3059）+ 落地中的 /emerging-batter（主軸正是 role change）覆蓋。fa_scan 本身不動。

## 優先序

| 優先 | 項目 | 為什麼 |
|---|---|---|
| 1 | C1 batter backtest | 先建測量回路，否則其餘項目效果無法驗證 |
| 2 | hygiene 包：A1 watch %owned 真值 + A2 prior PA/age + A6 BBE gate + A5 視窗標註 | 純機械、零 prompt 變動、消除假值/缺值誤導，無 thinking induction 風險 |
| 3 | B1 CLOSE 正規化 + B2 機械 counter 行 | 與 payload doc 建議 2/3 同波做，品質與 token 雙收 |
| 4 | A3 platoon/PA 落差 + A4 wOBA−xwOBA luck | 新訊號軸，做完用 C1 驗證效果 |
| 5 | B3 排序去偏 + B4 觸發 schema 約束 | 小改，搭車 |
| 6 | B5 batter 2-step | 收益不確定、成本確定，等 C1 有基線後再 A/B |

貫穿觀察：batter 端設計哲學是「raw 給足、LLM 自由 reasoning」，但目前 raw **給得不足且偶爾給錯**（假 0%、缺 prior PA、缺 platoon、運氣靠腦補）— 自由 reasoning 的品質上限就是 payload 的誠實度。先把資料層修誠實，再談推理層升級。

## 與 payload-optimization doc 的重疊對照

| 本篇 | payload doc | 關係 |
|---|---|---|
| B1 CLOSE 正規化 | 建議 2（結案自動化）| 同一件事；本篇給出更乾淨形態（schema 化 vs fuzzy 偵測）|
| B2 機械 counter 行 | 建議 3 的 counter 摘要行 | 同一機制；品質動機獨立成立 |
| A6 BBE gate | 建議 4 hygiene | 完全相同 |
| C1 backtest | 建議 5 model 降級的驗證手段 | C1 是建議 5 的前置量尺 |

→ 兩篇若各自落地會互相孤兒化，PRD 階段應合併為單一改善計畫。

## 尚待決定（grill-me / PRD 前的開放決策）

1. **PRD 範圍**：與 payload doc 的 ②③④⑤ 合併成單一「fa_scan batter 改善計畫」，或品質項獨立成篇？（推薦：合併）
2. **C1 hit 定義**：batter verdict 的對錯怎麼判 — 取代建議 → N 天後新人 vs 被 drop 者實際產出差？觀察 → 觸發達成率？時間窗多長？這是 PRD 中唯一需要真正設計的新東西。
3. **A3 輕重版**：先 PA-TG 落差 tag（一行 code）還是直上 vs L/R splits（新資料源）？（推薦：先輕後重）
4. **B5 是否直接 out of scope**：（推薦：out of scope，留待 C1 基線後另案）
