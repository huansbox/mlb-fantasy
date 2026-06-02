# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-02
- recorded_at: 2026-06-01T12:38:21+08:00
- last_recheck_at: 2026-06-02T14:46:41+08:00

### TBD 場次（待補查）
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
- 2026-06-02 14:46 補查（TBD 3→1）：MIA→Lake Bachar（別隊）、ATL→Bryce Elder（別隊）公布，無新 FA 候選進池（新評 0）。狀態變化：**Trevor McDonald 已被本隊認領**（owned_by_me，6/1 deep eval 後 claim）→ 移出 FA 候選；Noah Cameron + Bubba Chandler 已被別隊認領（lost_to_others）；Miles Mikolas 仍 FA（❌ 不推維持）。剩 NYM @ SEA（NYM away）TBD，時效至 ET 6/2 13:00 = TW 6/3 01:00。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-03
- recorded_at: 2026-06-02T14:46:41+08:00
- last_recheck_at: 2026-06-02T15:10:58+08:00

### TBD 場次（待補查）
- SF @ MIL (MIL home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Chris Bassitt | BAL @ BOS | BOS (.790 🔴) | 12% | 24/28 | <P25·P25-40·P25-40·P70-80·**P80-90** | ❌ 不推 (deep) | floor risk 高（近 6 場對 MIA+WSH 弱打各崩 4ER）+ 對手 BOS 真熱非噪音（30d.735→14d.790→7d.793 階梯升溫不可賭回歸）+ 客場 Fenway；近 6 場 ERA 3.94 + Sum 24/28 撐不過 variance |
| Colin Rea | CHC vs ATH | ATH (.686 🟢) | 13% | 20/24 | P25-40·P25-40·P40-50·P70-80·<P25 | ❌ 不推 (deep) | 雙 ❌ 硬條件：近 6 場 ERA 4.78 + floor risk 高（5/17 對 CWS 弱打 4.2/4ER + 5/12 ATL 5ER）；對手 ATH vs RHP .736 中強（14d .686 強制錨但 7d .801 反彈）|
| Walker Buehler | SD @ PHI | PHI (.569 🟢) | 6% | 17/13 | <P25·<P25·P40-50·P60-70·P25-40 | ⚠️ 條件推 (deep) | 對手 PHI 急冷（30d.675→7d.498）回歸後仍弱-中(.679) + K9 7.49 最高 + floor 中(近6場1崩) + 剛對 PHI 5.1/2ER；風險在 Sum 17 雙年弱 + 短局 QS 17% |
| Chris Paddack | CIN vs KC | KC (.659 🟢) | 1% | 15/15 | <P25·P25-40·P25-40·P25-40·P40-50 | ❌ 不推 | 5 軸全 P40 以下 + ERA 6.90（xERA 4.76 buy-low 但需單場好投撐）|
| Patrick Corbin | TOR @ ATL | ATL (.735 🟡) | 7% | 15/20 | <P25·<P25·P60-70·P40-50·<P25 | ❌ 不推 | ERA 3.65 = ⚠️ 賣高運氣假象（xERA 5.25 回升）+ xwOBACON <P25 + 對手 ATL 不弱 |

### 備註
- 2026-06-02 14:46 首次評估（ET 6/3）：5 位通過 Rotation gate + Sum ≥15 + true_starter。已過濾：Erick Fedde (CWS @ MIN) Sum26 **13** < 15 hard floor（5 軸 4 個 <P25，只 xwOBACON P80-90 撐不起 + luck ✅ 撿便宜 ERA 5.40/xERA 4.57）+ 別隊 21 位（含 Paul Skenes / Gerrit Cole / Zac Gallen / Freddy Peralta / George Kirby / Logan Webb / MacKenzie Gore / Cristopher Sánchez / Shohei Ohtani）+ 本隊 2 位（Stephen Kolek @ MIN / Andre Pallante vs TEX）。
- TBD 1 場（SF @ MIL，MIL home SP 未公布），建議 TW 6/3 早上補查。
- 排序：**Bassitt > Rea > Buehler > Paddack ≈ Corbin**。Bassitt 唯一條件推（雙年結構穩 + xwOBACON P80-90），但對手 BOS 14d .79 🔴 是當日最硬，賭 BOS vs RHP 季線 .677 弱回歸。其餘 4 位 Sum ≤20 結構偏弱。
- 用戶決策建議：① 缺 QS/W/IP/K 且願賭對手回歸 → Bassitt（結構底盤最穩）② 想賭純對位（對手冷 + K 產出）→ Buehler（PHI .569 最冷 + K9 7.49）但結構弱風險高 ③ 不想賭 → 本日 pass 等 SF@MIL TBD 補查或看 fa_scan worst SP。
- 2026-06-02 15:10 deep eval（3 位候選 Bassitt + Buehler + Rea）：
  - **Chris Bassitt**：⚠️ 條件推 → **❌ 不推 (deep)**。差異訊號 = floor risk 高（近 6 場對 MIA+WSH 兩支弱打各崩 4ER，scan 5-slot 看不到）+ 對手 BOS 真熱非噪音（30d.735→14d.790→7d.793 階梯升溫，14d/7d 一致不可賭回歸）+ 客場 Fenway。近 6 場 ERA 3.94 + Sum 24/28 結構底盤撐不過 variance
  - **Walker Buehler**：❌ 不推 → **⚠️ 條件推 (deep)**。差異訊號 = 對手 PHI 急速冷卻（30d.675→14d.569→7d.498 Δ-.177）回歸後仍弱-中(vs RHP .679) + K9 7.49 當日最高 + floor 中（近6場僅1崩）+ 剛對 PHI 5.1/2ER/0BB；風險全在結構（Sum 17 雙年弱 + IP/GS 短局 QS 17%）
  - **Colin Rea**：❌ 不推 → ❌ 維持 (deep)。差異訊號 = 觸發雙 ❌ 硬條件（近 6 場 ERA 4.78 ≥4.50 + floor risk 高：5/17 對 CWS 弱打 4.2/4ER + 5/12 ATL 5ER 2HR）+ 對手 ATH vs RHP .736 中強（14d .686 強制錨，7d .801 反彈）+ xwOBACON <P25
- 排序（deep 後反轉）：**Buehler > Bassitt > Rea**。串流核心對手對位 > 5-slot：Bassitt 結構/產量維度幾乎全勝（Sum 24/28 + QS 50% + vs RHP .677）但對手真熱 + floor 高壓過；Buehler 結構弱(Sum 17)但對手 PHI 回歸後最弱 + K 高 + floor 穩，當日唯一 ⚠️
- 用戶決策建議（deep 後）：① 要 K + ERA/WHIP hedge + 對位安全（不指望 QS/W）→ Buehler ② 執意要 QS/IP/W 產量 + 願賭 BOS 季線 .677 回歸 → Bassitt（但機械門檻已 ❌，floor variance 大）③ 三人都不夠乾淨 → 本日 pass 等 SF@MIL TBD 補查或看 fa_scan worst SP
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
