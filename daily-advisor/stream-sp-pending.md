# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-01
- recorded_at: 2026-06-01T12:38:21+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- CWS @ MIN (CWS away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|

_（本次無通過過濾的 FA 候選）_

### 備註
- 2026-06-01 12:38 首次評估：唯一 FA 候選 Kyle Freeland (COL @ LAA) Sum26 **11** < 15 hard floor 排除（5 軸 IP/GS <P25 + GB <P25 + xwOBACON <P25，ERA 8.08 / xERA 6.67 雙崩，luck_tag ✅ 撿便宜失效因 xERA 本身 deep crisis）。TBD 1 場（CWS away SP 未公布；MIN 已公布 Joe Ryan 別隊持有）。owned_by_others 16 位（含 Sandy Alcantara / Jacob deGrom / Joe Ryan）。建議 TW 6/1 晚上補查 CWS SP（時效至 ET 6/1 13:00 = TW 6/2 01:00）。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-02
- recorded_at: 2026-06-01T12:38:21+08:00
- last_recheck_at: 2026-06-01T12:46:13+08:00

### TBD 場次（待補查）
- MIA @ WSH (MIA away TBD)
- TOR @ ATL (ATL home TBD)
- NYM @ SEA (NYM away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Trevor McDonald | SF away | MIL (.628) | 11% | 43/46 | P70-80·P60-70·**>P90**·**>P90**·P70-80 | ⚠️ 條件推 (deep) | 深評降評。近 5 場 ERA 4.34（非強推 ≤3.50）+ 5/22 對 CWS 弱打 3.2IP/7ER 崩盤（0BB/0HR cluster luck 孤立，前後 ATH/AZ 皆 QS）+ GS=5 小樣本（medium）讓 Sum 43 信心降一檔；MIL 14d .628 冷但 vs RHP .713 季線中等（回歸往上）。仍當日最佳串流（QS ~50-55% + BB/9/GB% 雙 >P90）|
| Miles Mikolas | WSH home | MIA (.641) | 1% | 18/20 | <P25·<P25·P60-70·P70-80·<P25 | ❌ 不推 (deep) | 深評維持。近 6 場 ERA 3.33 近況回穩（比 season 5.72 好）但 **0/12 QS** + IP/GS 4.17 從未投滿 6 局 + K9 5.72 低三振 = fragile 天花板鎖死；MIA 弱（vs RHP .695）但只 hedge ERA/WHIP，QS/K/W 全拿不到 |
| Noah Cameron | KC away | CIN (.753) | 18% | 17/29 | P25-40·P50-60·P50-60·<P25·<P25 | ❌ 不推 | 無 elite 軸 + 對手 CIN 🟡 + vs LHP .761 偏強；2025 Sum 29 較佳但今年回落 + luck ⚠️ 賣高 |
| Bubba Chandler | PIT away | HOU (.681) | 62% | 15/27 | <P25·P50-60·**<P25**·<P25·P50-60 | ❌ 不推 | BB/9 6.23 控球失控（<P25）+ WHIP 1.52 + Sum 剛過 floor；高 %own 但結構撐不起 |

### 備註
- 2026-06-02 首次評估（recorded 2026-06-01 12:38）：4 位通過 Rotation gate + Sum ≥15 + true_starter。已過濾：Steven Matz (TB home vs DET, Sum26 **12** hard floor — 2026 5 軸 3 個 <P25；2025 是 reliever GS 2/G 53 rotation_gate 🚫，2026 才轉先發但結構未跟上) + 別隊 21 位（含 Jack Flaherty / Aaron Nola / Logan Gilbert / Nathan Eovaldi / Dustin May）+ 本隊 1 位（Joey Cantillo @ NYY）。
- TBD 3 場（MIA / ATL / NYM SP 未公布），建議 TW 6/2 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- 排序：**McDonald >> Mikolas ≈ Cameron ≈ Chandler**。McDonald 唯一推薦（Sum 43 + 雙 >P90 + 對手最弱）；其餘三位 Sum <19 結構偏弱，僅滿足「對手不硬」單條件。
- 用戶決策建議：① 缺 ERA/WHIP/QS/W → McDonald（對位 + 結構雙優，賭樣本小不崩）② 不想賭 rookie 小樣本（GS=5）→ 本日 pass，等 TBD 補查或看 fa_scan worst SP ③ McDonald 對 GB/控球維度最穩（BB/9 + GB% 雙 >P90），floor 相對高
- 2026-06-01 12:46 deep eval（2 位候選 McDonald + Mikolas）：
  - **Trevor McDonald**：✅ 推 → **⚠️ 條件推 (deep)**。差異訊號 = 近 5 場 ERA 4.34（非強推 ≤3.50）+ 5/22 對 CWS 弱打 3.2IP/7ER 崩盤（0BB/0HR cluster luck 孤立，前後 5/16 ATH + 5/27 AZ 皆 QS）+ GS=5 樣本小（medium）讓 Sum 43 信心降一檔；MIL 14d .628 冷但 vs RHP .713 季線中等（回歸往上）。仍當日最佳串流（QS ~50-55% + BB/9/GB% 雙 >P90 技術底盤）
  - **Miles Mikolas**：❌ 不推 → ❌ 維持 (deep)。差異訊號 = 近 6 場 ERA 3.33 近況回穩（比 season 5.72 好）但 **0/12 QS** + IP/GS 4.17 從未投滿 6 局 + K9 5.72 低三振 = fragile 天花板鎖死；MIA 弱（vs RHP .695）但只 hedge ERA/WHIP，QS/K/W 全拿不到
- 排序：**McDonald >> Mikolas**。McDonald QS ~50-55% + Sum 43 結構菁英 + IP/GS 5.8 全面優於 Mikolas（QS ~5-10% 短局型）；雖 Mikolas 近 6 場 ERA 3.33 < McDonald 4.34 且對手略弱（.695 < .713），但串流要的 IP/QS/K/W 四項 Mikolas 全弱，只 hedge ERA/WHIP
- 用戶決策建議（deep 後）：① 缺 QS/W/IP/K → McDonald（唯一合理目標，賭 GS=5 小樣本不崩）② 只 hedge ERA/WHIP 不在意 counting → McDonald 仍較優（4.34 ERA 多受 CWS 單場 cluster 拉抬，去掉後 4 場 ER 僅 7）③ 不想賭 rookie 樣本 → 本日 pass 等 TBD 補查
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
