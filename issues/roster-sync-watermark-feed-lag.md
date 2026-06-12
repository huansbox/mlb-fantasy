# roster_sync watermark 推進漏交易（Yahoo transaction feed 晚浮出面）

**狀態**：🟡 fix deployed（2026-06-12 merge `53332fb` + VPS cron 已加），待首班 reconcile cron 驗證
- 已實作：修法 1（`compute_watermark` = max(seen tx ts)，monotonic，不再寫牆鐘）+ 修法 3 後半（`--reconcile` 每日全量 roster 對帳模式，cron `50 3 * * *` UTC = TW 11:50，fa_scan 前；發現 diff → 自動修復 + commit 標 `(reconcile recovery)` + Telegram 大聲警報）。8 新測試，全套 778 綠。
- 已知接受的邊角：reconcile 若搶在 gate 前套用了新交易，gate 之後會走 classify_empty_diff retry → ~30h 後一次 spurious advance_alert（罕見、有界、config 已正確）。
- 未實作：修法 2（overlap window）— reconcile 網已覆蓋同類風險，不疊加複雜度；修法 3 前半（fa_scan FA 池 ∩ roster alert）— reconcile 讓 config 滯後 ≤24h，FA 池污染窗口大幅縮小，暫不另做。
- **驗證完成（2026-06-12）**：首班 reconcile cron（TW 11:50）log 確認「Reconcile: config matches Yahoo roster. Done.」— Yahoo API 已恢復，reconcile 端到端走通（fetch 全量 roster + diff + 無差異提早結束）。原 ①② 兩項驗證一併結案。本 issue 關閉。
- 原始狀態（2026-06-11 發現，config 已手動 `--init` 修復 `73e7528`）：

## 事件

- 2026-06-10 13:08 UTC（TW 21:08）：用戶在 Yahoo 做兩筆異動 — ① drop Joey Cantillo ② add Mauricio Dubón / drop Spencer Steer。
- 13:22 UTC cron：`fetch_transactions` **只回傳了 ①**（② 因 Yahoo transaction feed read-after-write lag 尚未浮出），處理 ① 後走正常路徑 `write_last_sync(int(time.time()))` → watermark = 13:22:03。
- 之後每班 poll：② 浮出時 timestamp ≈13:08 < watermark 13:22 → `has_new_transactions` 永遠 False →「No new transactions」→ **② 永久跳過**。
- 後果：roster_config 滯後 26+ 小時，6/11 12:30 fa_scan 把 Steer（實際已被我們 drop、掛 waiver）當 FA 推薦「add Steer drop Rafaela」— 叫用戶 FAAB claim 回自己前一天 drop 的人。

## Root cause

`run_daily` 成功路徑（roster_sync.py:877，以及 :855/:860 兩分支同病）watermark 寫 **poll 牆鐘時間**，不是**已處理交易的 max(timestamp)**。任何「timestamp 早於 poll 時刻、但 feed 晚浮出」的交易都落入死角。

與 6/2 修復（`1a56c6f` classify_empty_diff / 30h 窗）的差異：那次防的是「**交易可見**但 roster snapshot 未反映」；本案是「**交易不可見**」— 當班另有可見交易 + 非空 diff 時走正常路徑，empty-diff 防線完全不觸發。同類前例：5/8 May→Lambert、5/16-5/19 sync break（`fd8199d` 手動恢復）。**這是第三次漏交易**。

## 修法方向（擇一或併用）

1. **watermark = max(processed tx timestamps)**（最小修）：不再用 `time.time()`。仍有殘洞 — 同秒多筆 + 部分浮出時仍可能跳過，但窗口從「分鐘級 lag」縮到「同 timestamp 並發」。
2. **查詢窗口 overlap + 冪等吸收**（較根治）：`has_new_transactions` 改看 `timestamp > last_sync − OVERLAP`（如 30-60 min），重看舊交易靠 `diff_roster`（本身冪等：config vs Yahoo roster 的 diff，無變化即空）吸收。注意：重看舊交易 + 空 diff 會進 `classify_empty_diff` → 需確認不會被誤判 retry 造成無限重試（30h 窗應已涵蓋，需加測試）。
3. **防呆網（獨立價值）**：fa_scan 建 FA 池後與 `roster_config` 名單取交集，非空 → Telegram alert + 把該 FA 從池中剔除。本案若有此網，12:30 cron 當場就會吵醒用戶，而不是產出反向建議。另一張網：roster_sync 每日固定一班（如 watermark 之外）跑 `fetch_full_roster` 全量 diff 對帳（等同自動 `--init --dry-run`），有 diff 即 alert — 直接終結「漏交易潛伏 N 天」這個 class。

## 驗證素材

- `roster_sync.py --init --dry-run` 2026-06-11 實測輸出：`+Mauricio Dubón / -Spencer Steer`（修復前）。
- `.last_sync` 當時值：1781097723（2026-06-10 13:22）。
- 修復 commit：`73e7528`（manual --init recovery）。
