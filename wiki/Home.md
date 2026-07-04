# MLB Fantasy Baseball 2026 — 專案 Wiki

2026 Yahoo Fantasy Baseball 聯賽（12 隊、H2H One Win、7×7 類別）的**賽季管理自動化 + 決策支援系統**。選秀已完成，目前為 in-season 管理階段。

## 這個專案在做什麼

一句話：**VPS cron 跑 Python 機械層組資料 → `claude -p` 做 LLM 定性判斷 → Telegram 推送 + GitHub Issue 存檔；本機 Claude Code skills 負責手動決策場景。**

- **聯賽格式**：H2H One Win（majority rule — 贏的類別 > 輸的類別 = 1 W；6-6-2 = T）、每週 Min IP 40、每週最多 6 次異動、FAAB $100 全季
- **計分類別（7×7）**：打者 R / HR / RBI / SB / BB / AVG / OPS；投手 IP / W / K / ERA / WHIP / QS / SV+H
- **執行策略**：Punt SV+H、軟 Punt SB、預設不串流 SP、每週目標「贏的類別 > 輸的類別」拿 1 W

## 系統組成

| 層 | 內容 |
|---|---|
| 機械層（Python） | `fa_scan.py` / `fa_compute.py` / `stream_sp_scan.py` / `rp_svh_scan.py` / `roster_sync.py` 等 — 資料抓取、hard rule 過濾、排序，**不做定性判斷** |
| LLM 層（claude -p / skills） | 自由 reasoning 排 drop 優先序、FA classify、verdict — 機械層只餵 raw + percentile |
| 存放層 | `roster_config.json`（陣容唯一來源）、`waiver-log.md`（球員追蹤）、GitHub Issues（報告存檔） |
| 排程層 | VPS cron（每日 FA scan / 日報 / roster sync 每 15 分 / 週日 backtest） |

評估框架的唯一定義在 repo 的 [`CLAUDE.md`](https://github.com/huansbox/mlb-fantasy/blob/master/CLAUDE.md)；資料流圖在 [`docs/architecture.md`](https://github.com/huansbox/mlb-fantasy/blob/master/docs/architecture.md)。

## 專案階段

- **Phase 1 — 選秀準備（已完成）**：7×7 格式分析 → VOR 排名 → Monte Carlo 模擬 → Draft Helper 工具
- **Phase 2 — 賽季管理（進行中）**：每日戰報、FA 市場掃描、waiver 操作、每週覆盤、串流 SP / RP-SV+H 專用流程

## Wiki 頁面導覽

| 頁面 | 內容 |
|---|---|
| [Maintenance](Maintenance) | 維運手冊 — 執行環境、cron 排程、同步 pipeline、部署與故障排查 |
| [Roadmap](Roadmap) | 路線圖 — 已完成里程碑時間線 + 未來方向 |
| [Plan](Plan) | 執行中計畫 — 當前開發主軸與待辦快照 |
| [Tech Debt](Tech-Debt) | 技術債清單 — 已知欠帳與風險 |

> **文件分工**：wiki 是導覽與快照；策略 / 評估框架 / 待辦的 source of truth 永遠在 repo 內（`CLAUDE.md`、`issues/`、GitHub Issues）。兩者衝突時以 repo 為準。
