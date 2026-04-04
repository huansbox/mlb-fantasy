# MLB Fantasy Baseball 2026

2026 Yahoo Fantasy Baseball 聯賽的選秀分析與賽季管理工具。

## 聯賽格式

- H2H One Win（14 類別合計，贏 8+ = 1 週勝）
- 打者 7 項：R, HR, RBI, SB, BB, AVG, OPS
- 投手 7 項：IP, W, K, ERA, WHIP, QS, SV+H
- 12 隊，Snake Draft

## 專案階段

### Phase 1：選秀準備（已完成）

格式分析 → VOR 排名 → 選秀策略 → Monte Carlo 模擬 → Draft Helper 工具

- `7x7-選秀分析.md` — 7×7 格式類別評分 + VOR
- `作戰策略.md` — 選秀日決策樹（R1-R22）
- `draft-helper.html` — 手機版選秀日互動助手（[線上版](https://huansbox.github.io/mlb-fantasy/draft-helper.html)）
- `draft-sim.js` — 蒙地卡羅選秀模擬器（200 次 × 12 順位）

### Phase 2：賽季管理（進行中）

開季後的陣容管理、waiver wire 操作、每週對戰分析。

- `賽季管理入門.md` — H2H One Win 賽季管理入門要點
- `waiver-log.md` — 球員觀察追蹤記錄
- `.claude/commands/player-eval.md` — 球員評估 SOP（`/player-eval`）
- `.claude/commands/waiver-scan.md` — Waiver wire 掃描 SOP（`/waiver-scan`，含 Yahoo FA 查詢）
- `daily-advisor/yahoo_query.py` — Yahoo FA 查詢 CLI（skill 內部使用）
- `daily-advisor/` — 每日陣容建議產生器（MLB Stats API + claude -p → Telegram 推送）

## 核心策略

- **Punt SV+H**：RP 純比率用，不追救援
- **軟 Punt SB**：不刻意追速度，偶爾能贏
- **SP 重裝**：9 SP 深度，Min IP 40 輕鬆過

## 環境

- 需要 [Claude Code](https://claude.com/claude-code) 來使用 `player-eval` / `waiver-scan` skill
- `daily-advisor/` 需要 Python 3.10+（零外部依賴）+ Claude Code CLI + Telegram Bot token + Yahoo OAuth token
  - VPS: RackNerd Ubuntu 24.04, Python 3.12 + Claude Code 原生版
  - Cron 排程：
    - **Weekly Review** UTC 10:00 每週一（台灣 18:00）：覆盤資料準備
    - **Weekly Scan** UTC 11:30 每週一（台灣 19:30）：FA 市場深度掃描
    - **速報** UTC 14:15（台灣 22:15）：SP 排程 + 對戰分析 + Lineup 確認
    - **最終報** UTC 21:00（台灣 05:00）：lineup 確認 + 調整建議
    - **FA Watch** UTC 23:00（台灣 07:00）：%owned 追蹤 + FA 快報
  - 報告自動存檔為 GitHub Issue（戰報 label: `week-N`，FA 掃描 label: `waiver-scan`）
  - 更新部署：`ssh root@107.175.30.172 'cd /opt/mlb-fantasy && git pull'`
- `draft-helper.html` 為獨立 HTML，手機瀏覽器直接開
- `draft-sim.js` 需要 Node.js 執行
