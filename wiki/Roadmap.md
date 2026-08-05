# 路線圖

> 快照日期：2026-08-05。長期方向在此；逐項執行狀態見 [Plan](Plan)。

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
| 2026-07-07 | **stream-sp / stream-sp-deep 優化批（#404-#409）全數落地** — scan `recent_form` 近況軸 + floor cap / `bulk_suspect` 分類 + 角色 registry / deep CLI pending 自讀 / `opp_tier` 對手分級機械化 |
| 2026-07-08 | **fa_scan 決策執行層 14 片實質收官** — 318b 三段 A/B 全通過；batter + SP 兩份對帳都產出真帳，C1 回路 production 驗證完成 |
| **2026-07-28** | **⚠️ Yahoo Fantasy API 對本 app 全面撤銷** — 系統多數自動化停擺（非本專案缺陷，見下方「平台中斷」） |
| 2026-08-05 | **降級運作定案** — 停用 5 個 Yahoo 相依排程、日報改行動清單格式、新增日報健康檢查 |

## 平台中斷（2026-07-28 起）

這不是技術債也不是待辦，是**外部約束**，決定了下面所有方向的可行性：

- 2025-10 — Yahoo 靜默移除 create-app 的 Fantasy Sports **Write** 權限（只剩 Read）
- 2026-05 — 改為人工審核制（`sports.yahoo.com/developer/access`），舊自助文件站 308 重導向
- 2026-07-22 起 — legacy app 分波斷網，本專案落在 07-28 那波
- 現況 — 新建 app 的權限清單已無 Fantasy Sports 選項；新 portal 無 support channel；全網 0 個恢復成功案例

**影響**：「AI 全自動代打理隊伍」這個長期方向，在 Yahoo 平台上已不可行 — 卡點是對方的產品決策，不是技術。詳見 [Tech-Debt](Tech-Debt) 的平台依賴條目。

## 進行中主軸

無。工程投資暫停，等 [Plan](Plan) 的 Yahoo 申請決策點（2026-08-19 後回查）。

維持中的只有日報單線（不依賴 Yahoo）與其健康檢查。

## 未來方向（全部以 Yahoo 恢復為前提）

若 read access 恢復：

- **凍結線解凍**：`/emerging-batter` Step 2-7、Backtest Use Case B（xwOBACON 校準）、百分位表 2026 化
- **Phase 2 model 降級**：`claude -p` Opus → Sonnet/Haiku（batter 先試），對帳基線已建立可支撐 A/B
- **SP / Batter 框架對稱性重評**：batter 仍 v4 thin — 決定升 multi-agent 或明文維持 thin
- **交易掃描工具擴充**：SP 端排名掃描 + 「我方打者對方排 ≤8 × 對方 SP 品質」自動交叉比對

若 read access 不恢復：

- 系統定位收斂為「**不依賴 Yahoo 的決策輔助**」— 日報、球員評估（Savant + MLB Stats API）可續用，FA 掃描與週中戰術則需要人工提供輸入
- 換平台不在選項內（聯盟夥伴都在 Yahoo）

## 非目標（Non-goals）

刻意不做的事，防止未來的自己或 AI「好心」加回來：

- **不做「預測未來 roster」機制** — waiver 結果 TW 15:00 後拉即知；pending claim 本就可能失敗，不該預測
- **不用 hot/cold streaks 與 BvP 對戰史進評估框架** — 前者零預測力、後者樣本太小（7×7 格式規則明文）
- **不為 SV+H 加碼 RP** — Punt SV+H 策略，RP 上限 2 位；SB 軟 punt，不刻意追速度
- **串流 SP 不是常態** — 預設不串流，contested 類別 + controllable 變數推算成立才走 `/stream-sp`
- **不本機 call Yahoo、token 不落地本機** — 架構層約束，由 PreToolUse hook 機械化執行
- **不用瀏覽器自動化繞過 Yahoo API** — 違反服務條款，且帳號是跨季資產，不值得為單季功能冒險

## 賽季時間軸

- **季後賽：4 隊，Week 24-25（至 2026-09-20）** — 本季賽績已無望，不再作為工程收斂點
- 降級期節奏：每日看日報調 lineup（約 2 分鐘），其餘暫停
