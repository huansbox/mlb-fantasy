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

- `waiver-log.md` — 球員觀察追蹤記錄
- `roster-baseline.md` — 陣容基準卡（全員預測/實際數據）
- `player-eval` skill — 球員評估 SOP（Claude Code skill）
- `waiver-scan` skill — Waiver wire 掃描 SOP（Claude Code skill）
- `roster-scan` skill — 陣容基準卡週更 SOP（Claude Code skill）

## 核心策略

- **Punt SV+H**：RP 純比率用，不追救援
- **軟 Punt SB**：不刻意追速度，偶爾能贏
- **SP 重裝**：9 SP 深度，Min IP 40 輕鬆過

## 環境

- 需要 [Claude Code](https://claude.com/claude-code) 來使用 `player-eval` / `waiver-scan` / `roster-scan` skill
- `draft-helper.html` 為獨立 HTML，手機瀏覽器直接開
- `draft-sim.js` 需要 Node.js 執行
