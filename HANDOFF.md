# HANDOFF

- Status: idle
- Task/issue: 無 tracker issue — master 直接交付的故障處理與降級運作。跨 session 待辦見 `CLAUDE.md`「待辦」段首條（Yahoo API 申請決策點，2026-08-19 後回查）
- Branch: master
- Updated: 2026-08-05

## Progress

診斷並處理兩個獨立故障，系統轉入降級運作。

- **故障 A（Claude token）**：`~/.claude/.credentials.json` 的 `refreshToken` 為空字串，access token 於 2026-07-22 過期後無法續期，日報停發、fa_scan 連續 14 天發 error issue。使用者重新登入後已恢復（新憑證 refreshToken 正常）
- **故障 B（Yahoo API）**：2026-07-28 起 app-level 403，全端點含公開的 `/game/mlb`。確認非 token 問題（全新 mint 的 token 同樣 403）、非本專案個案（uberfastman/yfpy#84 等三個 issue 佐證全業界分波斷網）。write scope 更早於 2025-10 被官方移除
- **降級運作**：9 個 cron 縮到 4 個（日報平日/假日、savant_rolling、健康檢查），完整版保留於 VPS `/etc/cron.d/daily-advisor.disabled-20260805` 可一行還原
- **日報改行動清單格式**（`dd45256`）— 兩份清單取代描述式報告，不做 A→B 配對（roster_config 凍結於 07-22，硬配對會出錯）
- **新增日報健康檢查**（`7c38421`、`2f080de`）— `heartbeat_check.py` 獨立 cron，48h 門檻推 Telegram 警告；與 `daily_advisor` 雙向不 import
- **文件同步**：CLAUDE.md 頂端狀態區塊 + 待辦決策點 + 檔案索引（`4d55d1c`、`66e6c64`、`ac531a6`）；wiki 五頁 refresh 並經 CI 發佈驗證（`875d427`）

## Next step

None

## Validation

- `pytest tests/` 全套 **1250 passed**（需 `--with tzdata`，Windows 環境缺 IANA 時區資料，非程式碼問題）
- `heartbeat_check` 單元測試 22 cases 涵蓋門檻邊界、時鐘回撥、heartbeat 檔遺失／損毀
- VPS 端到端：日報手動觸發成功（Telegram 送達 + issue #481）；健康檢查五條路徑實測（正常不觸發 / 50h 觸發 / 檔案遺失 fail loud / Telegram 實際送達 / 真 heartbeat 未受污染）；`record_heartbeat()` 確認實際寫入
- wiki 發佈鏈：CI run success，wiki.git 七檔與 repo `wiki/` 內容一致
- **未執行**：cron 首班自動執行尚未發生（日報 2026-08-06 TW 05:30、健康檢查同日 TW 07:00），需下次 session 確認

## Blockers

None（本 session 工作已完成）。

外部約束：Yahoo API 撤銷阻擋所有 Yahoo 相依開發線（fa_scan、weekly_review、roster_sync、stream-sp / rp-svh / waiver-scan 等 skill）。非本 session 未解事項，決策點與判準記於 `CLAUDE.md` 待辦段首條。
