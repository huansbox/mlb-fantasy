# stream-sp 角色確認 registry

> 由 `/stream-sp` 與 `/stream-sp-deep` skill 讀寫（issue #405）。記錄 WebSearch / deep 確認過的 SP 角色結論，TTL 內同一 SP 再進 scan 直接沿用結論，免重付 WebSearch（~50K tokens / 70+ 秒每次）。
>
> - **TTL 21 天**：`confirmed_at` 距今 > 21 天 → 過期，重新 WebSearch 確認並更新該行（不刪行，覆寫）。
> - **提前重驗**：TTL 內但該 SP 近 game log 出現 GS=1 且 IP≥5（角色可能已變回先發）→ 重新 WebSearch 並更新。
> - 本檔**不受** `stream-sp-pending.md` 的過期清理影響 — 角色是跨週事實，不是 per-ET-day 決策。
> - 結論寫法：`true_starter` / `opener`（先發 1-2 局）/ `bulk`（piggyback 後段 3-5 局）+ 自由補充 workload cap / QS 可能性等脈絡。

## 角色確認

| SP | 隊 | 結論 | confirmed_at | 來源 |
|---|---|---|---|---|
| Miles Mikolas | WSH | bulk（piggyback 後段，swingman 無 QS）| 2026-07-06 | deep eval（初確認 2026-06-18 WebSearch）|
| Andrew Alvarez | WSH | opener/piggyback，單場 cap ~4.2 IP / PC≤90，全季 0 QS | 2026-07-06 | deep eval（初確認 2026-06-20 WebSearch）|
