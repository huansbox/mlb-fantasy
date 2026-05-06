# PRD: SP B1 Cutover — Phase 6 對齊 Batter v4 Thin

> 對應設計稿：`docs/sp-b1-cutover-design.md`（grill-me session 2026-05-06 對齊）

## Problem Statement

身為 12 隊 H2H Fantasy Baseball 聯賽的單人管理者，我每日依賴 fa_scan Phase 6 multi-agent SP pipeline 產出「該 drop 誰 + 撿誰」的決策建議。但 2026-05-04 觀察到三 agent 在 step1 prompt 中 lazy 引用機械層算出的 `sum: 14` / `sum: 19` 數字，三 agent 都 anchor 到同一機械排序，spike 顯示的「P1 共識率 100%」可能不是真共識，而是 anchor 鎖共識。

這代表：
1. multi-agent 的 dissent surface 機制（設計初衷）空轉 — 三 agent 沒有真正獨立 reasoning
2. Sum 1-10 分桶失真（P89 vs P91 跳 1 分；P79.5 vs P75 同分），加總喪失維度資訊，LLM 拿到的訊號比 raw percentile 更差
3. SP 框架（厚機械層）與 Batter v4 thin 框架（薄機械層）哲學不對稱，未來維護面雙倍

我需要在不引入新基礎設施、不增加 cron 排程、不破壞 v4 已穩跑的 production state 的前提下，把 SP Phase 6 收薄對齊 Batter v4 thin，並建立 dissent rate 監控與撤退機制，讓「multi-agent 是否真有用」這個問題能用實測數據回答而非靠記性觀察。

## Solution

把 SP Phase 6 改成「機械層只做 boolean filter（cant_cut / Rotation Gate / BBE<30 / Slump hold / Sum≥40 排除），排序與標籤都交 LLM」。具體：

- **拿掉 LLM payload 的 anchor 訊號**：Sum 加總分數、urgency 4-factor 排序、evaluation tags（雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣）
- **保留 LLM payload 的 raw 訊號**：5-slot 各自 percentile、雙年 prior（raw + percentile）、21d xwOBACON Δ、14d trad、%owned trend、PA-based / 樣本訊號 tags（短局 / 樣本小 / IL / 上場有限 / Swingman）
- **master borderline 判定改交 LLM**：從 mechanical 「sum diff <5」rule 改成 LLM 從 raw 訊號矛盾自判（例：「P1 候選 xwOBACON P30 但 IP/GS P85 = 內部矛盾」）
- **保留 multi-agent + 加 dissent 監控**：每日 fa-scan GitHub Issue body 加 HTML 註解 metric block，記錄三 agent step1 P1 是否一致（M1）+ master 是否觸發 step3 review（M4）。每週手動跑 `gh api` 抓 7-14 天 issue 算共識率
- **撤退門檻 + fallback**：spike fixture 跑 baseline → 設「P1 match rate 連 2 週 < baseline-1σ」或「review trigger rate 連 2 週 >75%」為撤退門檻；觸發時降回 single LLM call（對齊 Batter v4 thin 形態）。Fallback prompt 觸發後再寫，先不浪費

整套改動以漸進方式上線，rollback 走 git revert（v4 已穩跑 8+ 天，引入 feature flag 不划算）。

## User Stories

1. As a league manager, I want SP Phase 6 三 agent 真正獨立從 raw stats reasoning 出 P1 候選, so that 我看到的「共識」反映真實判斷收斂而非機械 anchor 鎖
2. As a league manager, I want LLM 不再看到 Sum 加總數字, so that prompt 不會引導 LLM lazy 引用 1-10 分桶失真的數字
3. As a league manager, I want LLM 不再看到 mechanical urgency 排序, so that 三 agent 不會被排序順位 anchor 到同一答案
4. As a league manager, I want LLM 不再看到 evaluation tags（雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣）, so that LLM 自行從 raw + percentile 得出評估而非 lazy 引用 tag verdict
5. As a league manager, I want LLM 仍看到 PA-based / 樣本訊號 tags（短局 / 樣本小 / IL 短期 / 上場有限 / Swingman）, so that sample-quality warning 不被當成 evaluation verdict 卻仍能 surface 樣本可信度
6. As a league manager, I want SP 機械層加上 Sum ≥40 hard 排除, so that 全 5-slot P70+ 的 SP 不會被列 drop 候選浪費 LLM 算力（對齊 Batter Sum≥25 排除）
7. As a league manager, I want master step2 從 raw 訊號矛盾自判 borderline, so that step3 review 觸發是真實 dissent surface 而非 mechanical sum diff rule
8. As a league manager, I want 每日 fa-scan GitHub Issue body 結尾加 HTML 註解 metric block, so that 不需新增 infra 就能記錄 dissent metric
9. As a league manager, I want metric block 包含三 agent step1 P1 match boolean、master borderline trigger boolean、anchor 名 / FA top 名 / date, so that 一週後可回查 P1 不一致那幾天分歧在哪
10. As a league manager, I want 每週日跑單一 `gh api` 指令抓 7-14 天 issue body, so that 算 P1 match rate / review trigger rate 不需開新 cron
11. As a league manager, I want spike fixture 在 B1 上線前重跑取得 baseline 共識率, so that 撤退門檻不是憑空設數字
12. As a league manager, I want spike fixture 樣本至少含 fa-scan #149（已知 anchor 失效案例）, so that baseline 反映真實 dissent surface 期望範圍
13. As a league manager, I want 撤退門檻定義為「P1 match rate 連 2 週 < baseline-1σ」OR「review trigger rate 連 2 週 >75%」, so that 觀察期不靠記性，達標立即撤退
14. As a league manager, I want 撤退觸發時降到 single LLM call（不是 step1 single + master 半套）, so that 撤退是徹底的可預期收斂，不留半套 multi-agent
15. As a league manager, I want fallback prompt 觸發後再寫, so that 觀察期 1-3 週若不觸發不浪費 prompt 撰寫時間
16. As a league manager, I want B1 改動分 6 個 commit（機械層 / payload schema / prompt / metric / spike fixture / merge）, so that 任何階段出問題可 selective git revert
17. As a league manager, I want B1 cutover 不引入 feature flag, so that 維護面不增加（v4 已穩跑 8+ 天，git revert 即可）
18. As a league manager, I want fa_scan_v4.py CLI 工具趁 B1 同步退役, so that 解決 CLAUDE.md 既有 TODO 不延長
19. As an observer reading 每週 dissent rate 報表, I want 看到 M1 + M4 兩個獨立指標, so that 區分「step1 input dissent」與「master 認知 dissent」（兩者 decoupled，組合意義不同）
20. As an observer, I want M1 高 + M4 低時 understood 為「三 agent 共識且 master 認可」, so that 不誤判為 multi-agent 失敗
21. As an observer, I want M1 低 + M4 高時 understood 為「ranking 分歧且 master 也覺得有問題」, so that 識別為強撤退訊號
22. As an observer, I want M1 高 + M4 高時 understood 為「ranking 一致但 master 覺得 raw 矛盾」, so that 識別為弱訊號（可能 master 過度敏感）
23. As a developer, I want payload schema 變更被自動測試覆蓋, so that 未來改 fa_compute 不會意外把 sum / urgency / evaluation tags 漏進 LLM payload
24. As a developer, I want metric block 結構被自動測試覆蓋, so that issue body footer 解析不會因欄位漂移失敗
25. As a developer, I want metric reader 對 fixture issue body 跑 parse 測試, so that 週彙整邏輯穩定
26. As a developer, I want SP Sum≥40 排除規則的 boundary case（39 / 40 / 41）被測試覆蓋, so that 門檻邏輯一致
27. As a developer, I want B1 上線後 batter Phase 6 multi-agent 升級時間點 trigger SP 對齊重評, so that 「框架對稱性檢視」TODO 在正確時機觸發（本 cutover 已先動 SP，原計畫倒序執行）

## Implementation Decisions

### 機械層（`fa_compute` 模組）

- 新增 SP Sum ≥40 hard 排除規則進入 `pick_weakest_v4_sp` 既有 filter chain（cant_cut / Rotation Gate / BBE<30 / Slump hold 之後）
- 數值 40 為設計初稿，需用 2025 SP 池實證 Sum 分布（P75-P80 區間）校準。校準後若實際 P75 落 35-38 → 改 36；若落 42-45 → 改 42
- urgency 4-factor 計算邏輯保留（內部仍可用作 backup / debugging），但 Phase 6 payload 不再傳遞此欄位
- evaluation tags（v4_add_tags_sp / v4_warn_tags_sp 中的雙年菁英 / GB 重型 / K 壓制 / 撿便宜運氣 / 賣高運氣 / 深投型 / 賣高運氣）從 fa_compute 邏輯中移除或標記為 deprecated（不再被 Phase 6 payload 引用）
- PA-based / 樣本訊號 tags（短局 / 樣本小 / IL 短期 / 上場有限 / Swingman 角色）保留並仍傳遞給 LLM payload

### Payload Slimmer（深模組，從 `_phase6_sp` 既有函式重構）

- 提取 `_slim_my_team_entry` / `_slim_fa_entry` 為單一深模組「payload_slimmer」，責任：給定完整 entry，輸出 LLM-safe payload
- B1 schema 強制不出現的欄位：`score`（v4 Sum）、`breakdown.sum`（加總分）、`urgency`、`factors`（urgency 內部因子）、evaluation tags
- B1 schema 必出現的欄位：`name` / `team` / `position` / 5-slot raw + percentile（IP/GS, Whiff%, BB/9, GB%, xwOBACON 各自分數）/ 雙年 prior raw + percentile / 21d xwOBACON Δ + BBE / 14d trad（如有）/ %owned trend（FA 路徑）/ PA-based tags / sample tags / `low_confidence` / `selected_pos` / `status`
- 模組接口：`slim_entry(full_entry: dict, role: 'my_team' | 'fa') -> dict`。簡單可測，責任單一

### Prompt Layer（5 個 prompt 改寫，外加 1 個新建 fallback）

- `prompt_phase6_sp_step1_rank.txt`：拿掉 sum / urgency / evaluation tags 引用；強調從 raw + percentile + 雙年 prior + 21d 趨勢自由 reasoning
- `prompt_phase6_sp_step2_master.txt`：移除「sum diff <5 → borderline」rule；新增 LLM 自判 borderline 的指引（raw 訊號矛盾 / 候選間實質差距小）
- `prompt_phase6_sp_step3_review.txt`：清掉 sum 引用文字；review 仍是 sanity check master
- `prompt_phase6_fa_step1_classify.txt` / `fa_step2_rank.txt` / `fa_step3_review.txt`：FA 路徑同 SP 邏輯，拿掉 sum_diff / breakdown_diff / win_gate_passed 引用
- `prompt_phase6_final_decision.txt`：清掉 sum 引用
- `prompt_phase6_sp_single.txt`（新建，G-pre2 觸發後再寫）：1 個 prompt 看 my-team SP + FA + raw + percentile + tags + 14d trad + %owned，輸出 final action

### Metrics Emitter（深模組，新建）

- 模組責任：給定 SP / FA pipeline 結果（step1 results、master decision、anchor / fa_top entries），輸出 HTML 註解 metric block 字串
- 接口：`emit_metric_block(date, sp_step1_results, sp_master, fa_classify_results, fa_master, anchor, fa_top) -> str`
- 寫入點：在 fa-scan 每日 issue body 組裝邏輯尾端 append metric block
- 欄位：`date` / `sp_p1_match` / `sp_review_triggered` / `sp_anchor_name` / `fa_p1_match` / `fa_review_triggered` / `fa_top_name`
- 純函式，無 side effect，純字串組裝

### Metrics Reader（深模組，新建）

- 模組責任：給定一組 issue body 字串，parse 出 metric blocks，aggregate 成 rate stats
- 接口：`aggregate_metrics(issue_bodies: list[str]) -> dict` → 回傳 `{p1_match_rate, review_trigger_rate, n_samples, date_range}`
- 可獨立 CLI 跑：`python metrics_reader.py --days 7` → 內部 `gh api` 抓 issue → 算 rate → 輸出
- 純解析 + 計數，無外部依賴除了 gh api / regex

### Pipeline Dispatcher（既有 `_phase6_sp.process_sp_v4`）

- 增加 `fallback_mode` flag（預設 false）。觸發 G1 撤退時改 true，dispatcher 改走 `prompt_phase6_sp_single.txt` 路徑（1 call），跳過 8-step pipeline
- B1 上線時 flag 預設 false，等實際撤退觸發再切換

### 不引入的東西

- 不引入 feature flag 或 config toggle 切換 v4-thick / B1-thin（rollback 用 git revert）
- 不新增 cron 排程（週監控用手動 `gh api` 或現有 daily fa-scan 一起跑）
- 不新增 Telegram 推送 dissent rate（觀察期低頻監控，每週手動看即可；未來想升級可後加）
- 不新增獨立資料庫 / JSON rolling log（issue body metadata 已足夠）
- 不引入 fa_scan.py 大重構（3611 行 god file 留待 B1 穩定 1-2 月後評估）

### 退役

- `fa_scan_v4.py` CLI 工具趁本 cutover 同步退役（mv 進 archive/ 或 git rm）— v4 已 production，CLI frontend 命運不需保留

## Testing Decisions

**測試哲學**：只測試外部行為（接口的輸入輸出），不測試實作細節（內部變數、私有函式分支）。模組接口應保持穩定，內部實作可演化。

**Prior art**（既有相似測試）：
- `tests/test_fa_compute_v4.py` — fa_compute v4 boundary case 測試（百分位分桶、4-factor urgency、tags）
- `tests/test_phase6_sp.py` — Phase 6 dispatcher 行為測試
- `tests/test_multi_agent.py` — multi-agent skeleton（consensus_check_key / aggregate_classifications）測試
- `tests/conftest.py` + `tests/fixtures/` — fixture 模式

**B1 必含測試模組**：

1. **Payload Slimmer schema 測試**：
   - 給 full entry（含 sum / urgency / evaluation tags 欄位），slim 後輸出 dict 不應含 `score` / `breakdown.sum` / `urgency` / `factors` / 任一 evaluation tag
   - 給 full entry，slim 後輸出 dict 應含 5-slot percentile / PA-based tags / sample tags / low_confidence
   - my_team role vs fa role 兩個分支都覆蓋

2. **`pick_weakest_v4_sp` Sum≥40 排除測試**：
   - Boundary cases：Sum=39 應入 weakest 池；Sum=40 應排除；Sum=41 應排除
   - 與既有 filter（cant_cut / Rotation Gate / BBE / Slump hold）的組合：cant_cut 球員即使 Sum=20 仍排除；Sum=45 但 BBE<30 仍標 low_confidence（不該被 Sum filter 排除）

3. **Metrics Emitter 結構測試**：
   - 給 fixture pipeline 結果，輸出字串應符合 `<!-- phase6_metrics: { ... } -->` 格式
   - 必含 7 欄位：date / sp_p1_match / sp_review_triggered / sp_anchor_name / fa_p1_match / fa_review_triggered / fa_top_name
   - JSON 應 parse-able（用 json.loads 反向驗證）

4. **Metrics Reader parse 測試**：
   - Fixture issue body（含 / 不含 / 損壞 metric block 三種情境）
   - 含 → parse 成 metric dict
   - 不含 → skip 該筆
   - 損壞（JSON 格式錯）→ 不 crash，記錯誤但繼續
   - Aggregate：給 7 筆 fixture（5 P1 match + 2 不 match）→ p1_match_rate = 5/7

**測試不覆蓋**：
- Prompt 文字內容（無 deterministic 測試方式，靠 spike fixture 人工檢視）
- LLM 實際 reasoning 品質（這是 spike fixture baseline + 觀察期實測的 scope，不是 unit test）
- Phase 6 pipeline 端對端整合（已有 `test_phase6_sp.py` 涵蓋 dispatcher 行為）

**用戶確認測試模組**（待 verify）：建議全部上述 4 個模組都加測試；若時間有限優先 1（schema 防 regression）+ 3（emitter 結構）。

## Out of Scope

- **Batter Phase 6 multi-agent 升級**：CLAUDE.md 既有 TODO，本 cutover 倒序執行先動 SP；Batter 升級時要重評是否還按原計畫升 batter（可能 batter 留 thin 已對稱無需動）
- **RP 框架 v4 升級**：仍走 v2 指標，與 SP B1 改動正交
- **SP 21d Δ xwOBACON 絕對門檻校準**：prompt 文字校準題，待累積 1-2 個月 issue archive 反推
- **fa_scan.py 3611 行 god file 重構**：留待 B1 穩定 1-2 月後評估，不混疊
- **Phase 5 minor refactor finding D**（fa_compute vs fa_scan 雙重 batter Sum 實作）
- **CLAUDE.md cleanup Task 2**（playbook 段抽出）
- **百分位表更新為 2026 賽季數據**（Week 6-8 才動）
- **Telegram 推送週 dissent rate 報表**（觀察期手動看即可，未來想升級可後加）
- **新增 cron 排程或排程性監控**（觀察期靠每週手動 `gh api` + 現有 daily fa-scan 一起跑）
- **Feature flag 切換 v4-thick / B1-thin**（rollback 走 git revert）
- **歷史決策語料 backtest**（無 corpus，靠 spike fixture + 觀察期實測）
- **策略耦合度（Punt SV+H 等與評分機制解耦）**：不影響 B1 主目標

## Further Notes

- **設計依據**：完整理由 / 反論 / 備案見 `docs/sp-b1-cutover-design.md`
- **grill-me 對齊軌跡**：Q1 SP 對齊 Batter / Q2 B1 拿掉 anchor / Q3 C2 保留 multi-agent + 監控 / Q4 D3 spike fixture baseline + M1 主 M4 副 / Q5 E1 全改 + Sum≥40 / Q6 F1 issue body metadata / Q7 G1 + G-pre2 / Q8 H3 master 從 raw 自判 borderline
- **預期 dissent 行為變化**：B1 上線後 spike fixture 共識率預估從現況 100% 降至 60-80%（真共識）；極端情況降至 <30%（疑似 raw 訊號本身 ambiguous，需 revert 部分 commit 評估）
- **觀察期長度**：建議 4 週。Week 1-2 baseline 校準 + 不撤退；Week 3-4 套門檻 + 觸發判定；Week 4 結束 review baseline 是否重設、multi-agent 是否保留
- **Rollback 粒度**：6 commit 拆分允許選擇性 revert
  - Commit 1（機械層 Sum≥40）獨立有價值，即使其他 revert 也應保留
  - Commits 2-3（payload schema + prompt）綁定 — 任一 revert 應同時 revert 另一
  - Commit 4（metric emitter）獨立 — issue body 多一段 HTML 註解不影響其他邏輯
  - Commit 5（spike fixture baseline）僅 docs，無 code
  - Commit 6（merge）— 形式上的 cutover 完成
- **與既有 CLAUDE.md TODO 的撞期**：本 cutover 同步處理「框架對稱性檢視」+「SP Phase 6 prompt 拿掉 Sum 暴露」+「fa_scan_v4.py 命運（退役）」三個 TODO，cutover 完成後可從 CLAUDE.md 待辦移除
