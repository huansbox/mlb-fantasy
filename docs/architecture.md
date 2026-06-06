# 系統架構

MLB Fantasy 2026 賽季管理的腳本資料流。CLAUDE.md 是策略大腦，所有自動化腳本依賴 `roster_config.json` 為陣容唯一來源、`waiver-log.md` 為球員追蹤唯一來源。

```
CLAUDE.md（策略大腦 + 評估框架唯一定義）
  ├─ 評估框架（打者/SP/RP）+ 百分位表 + 賽季運營 SOP
  ├─ 被讀取：所有 skill（/player-eval, /waiver-scan, /weekly-review）
  └─ 被更新：策略調整時手動改（唯一來源，skills 引用不複製）

daily_advisor.py（每日戰報，單一 adaptive 報）
  ├─ 平日（TW 05:30 / ET Mon-Fri 夜場）：有實際打序用打序，否則 probable matchup
  ├─ 假日（TW 22:30 / ET Sat-Sun 日場）：同上 adaptive
  ├─ 內容：Lineup 異動（sit/start）+ SP 確認（H2H 態勢 / SP matchup）
  └─ 輸出：Telegram 推送 + GitHub Issue 存檔（tag [日報]）

fa_scan.py（FA 市場分析唯一入口）
  ├─ 每日：Batter + SP 並行 threading（Python compute + Claude 文字化）
  │   └─ fa_compute.py: pick_weakest / compute_urgency / compute_fa_tags (Layer 4)
  │   └─ Claude 只做 定性 reason + 邊界 case flag + 觀察中變化 (Layer 5)
  ├─ 每日 TW 15:15：--snapshot-only（%owned 快照 + watchlist 清理）
  ├─ 被讀取：weekly_review.py（scan_summary）
  └─ 被更新：waiver-log.md（觀察中球員追蹤）

stream_sp_scan.py（/stream-sp skill 機械層；非 cron，skill 觸發）
  ├─ 輸入：--et-dates YYYY-MM-DD[,...]
  ├─ 流程：parse_schedule → cross_check_fa → 並行 batch v4_2026/2025 + game_log + 14d OPS → enrich
  │   └─ 重用：sp_data_fetchers (Savant) + fa_compute (Sum/breakdown_pct/rotation_gate/luck_tag)
  │   └─ 短路：fa_pool 拉到當天所有 starter hits 後早停分頁
  ├─ 輸出：純 JSON to stdout（LLM 拿來寫報告 + 更新 pending file）
  ├─ 被讀取：/stream-sp skill（Step 2-6 整合）
  └─ 不更新任何 state（pending file 由 LLM 在 Step 8 寫）

rp_svh_scan.py（/rp-svh skill 機械層；非 cron，skill 觸發）
  ├─ 流程：MLB 全聯盟 14d SV+H 排行 → Yahoo FA 交叉 → 三軸 rank-sum（BB/9 · whiff% · 30d SV+H）top-N
  ├─ 輸出：純 JSON to stdout（LLM 做角色安全 news check + verdict）
  ├─ 被讀取：/rp-svh skill
  └─ 取代舊 fa_scan.py --rp 週掃（2026-06-05 退役）；球員追蹤：waiver-log-rp.md

roster_config.json（陣容唯一來源）
  ├─ 球員名 / mlb_id / yahoo_player_key / positions / team / prior_stats
  ├─ selected_pos（Yahoo 格位：IL/IL+/BN/NA/位置）/ status（MLB 狀態：IL10/IL60/DTD/NA/空=健康）
  ├─ 被讀取：daily_advisor.py / fa_scan.py / roster_stats.py / weekly_review.py
  └─ 被更新：roster_sync.py（cron TW 15:10，偵測 add/drop + 更新狀態 → auto sync + git push）

waiver-log.md（球員追蹤唯一來源）
  ├─ 觀察中（FA）/ 隊上觀察（自家球員非數據脈絡）/ 已結案
  ├─ 被讀取：fa_scan.py / skills
  └─ 被更新：/player-eval / /waiver-scan skill / 傷病事件時手動

資料流：MLB Stats API + Yahoo Fantasy API + Baseball Savant CSV
  → Python 腳本組裝 → claude -p 分析 → Telegram 推送 + GitHub Issue 存檔
```
