# 路線圖

> 快照日期：2026-07-07。長期方向在此；逐項執行狀態見 [Plan](Plan)。

## 已完成里程碑

| 時間 | 里程碑 |
|---|---|
| 2026-03 | Phase 1 選秀完成（VOR 排名 + Monte Carlo 模擬 + Draft Helper） |
| 2026-04-28 | **SP 評估 v4 cutover** — 退役 v2（xERA / xwOBA / HH%），改 5-slot balanced Sum（IP/GS / Whiff% / BB/9 / GB% / xwOBACON）；batter 同波改 v4 thin |
| 2026-05-19 | **RP-SV+H SOP 落地** — production-first 三軸 rank-sum（`rp_svh_scan.py` + `/rp-svh`），取代舊 `--rp` 週掃 |
| 2026-05-26 | SP B1 cutover（multi-agent Phase 6） |
| 2026-05-28 | **SP B2 cutover（現行）** — thin mechanical + 2-step single-LLM + anchor 機制（cant_cut / weekly_anchor_sp） |
| 2026-06-05 | 退役 `fa_scan.py --rp` 全部殘留 |
| 2026-06-06 | **claude -p 成本簡化 S1-S3 + lever 1a** — 日報 2 合 1、平日/假日 cron 分流、neutral cwd 省 22.5K input/call |
| 2026-06-10 | fa_scan batter payload 瘦身（觀察中段 −59.7%）+ 判斷品質 PRD 定稿（11 切片） |
| 2026-06-12 | roster_sync watermark 第三次根修（monotonic watermark + 每日 reconcile 防呆網）驗證完成 |
| 2026-06-13 | **fa_scan 決策執行層 + 量修復 PRD 定稿** — 主 issue #316，14 子切片（#317-#330） |
| 2026-06-18 | 318b batter payload 注入 merge + VPS 段① A/B 通過 |
| 2026-07-07 | **stream-sp / stream-sp-deep 優化批（#404-#409）全數落地** — scan `recent_form` 近況軸 + floor cap / `bulk_suspect` 分類 + 角色 registry（TTL 21 天免重付 WebSearch）/ deep CLI pending 自讀（7 手抄參數 → 2）/ `opp_tier` 對手分級機械化去記憶 take；`issues/011` 以 OBE 結案 |

## 進行中主軸

**fa_scan 決策執行層 + 量修復（GitHub [#316](https://github.com/huansbox/mlb-fantasy/issues/316)）** — 本季下半場最大的工程投資：

- 執行層：decision ledger / 機械星等 4★+ 通知 / 慢快軌 gate
- 量修復：platoon 訊號 / SP 場次投影 / swap vector
- 關鍵路徑：#317 ledger → #319 star → #320 gate →（#330 KPI）

## 未來方向（尚未排程）

- **Backtest Use Case B（xwOBACON 校準）**：數據累積 4-6 週後，從 Issue archive 反推 21d Δ 絕對門檻，改 prompt 不改 code
- **Phase 2 model 降級**：`claude -p` Opus → Sonnet/Haiku（batter 先試），等對帳基線（C1）建立後另案
- **SP / Batter 框架對稱性重評**:batter 仍 v4 thin — 決定升 multi-agent 或維持 thin（已對稱 B2 即不動）
- **百分位表 2026 化**：CLAUDE.md + prompt 檔的 2025 基線換成 2026 當季分布（`calc_percentiles_2026.py` 已備好）
- **交易掃描工具擴充**：SP 端排名掃描 + 「我方打者對方排 ≤8 × 對方 SP 品質」自動交叉比對
- **preview 加聯盟 scoreboard**：預測時有數據基礎

## 非目標（Non-goals）

刻意不做的事，防止未來的自己或 AI「好心」加回來：

- **不做「預測未來 roster」機制** — waiver 結果 TW 15:00 後拉即知；pending claim 本就可能失敗，不該預測
- **不用 hot/cold streaks 與 BvP 對戰史進評估框架** — 前者零預測力、後者樣本太小（7×7 格式規則明文）
- **不為 SV+H 加碼 RP** — Punt SV+H 策略，RP 上限 2 位；SB 軟 punt，不刻意追速度
- **串流 SP 不是常態** — 預設不串流，contested 類別 + controllable 變數推算成立才走 `/stream-sp`
- **breakout 家族與 research_more 不進 #316** — PRD 明列 out of scope，不夾帶進執行層切片
- **不本機 call Yahoo、token 不落地本機** — 架構層約束，由 PreToolUse hook 機械化執行

## 賽季時間軸

- 每週節奏：週一覆盤 / 週四 IP 檢查 / 每日 lineup 微調
- **季後賽：4 隊，Week 24-25（至 2026-09-20）** — 全部工程投資的收斂點：在季後賽窗口前讓決策執行層跑順、讓 backtest 有足夠帳齡數據校準判斷品質
