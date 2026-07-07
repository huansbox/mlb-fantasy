# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-07-06
- recorded_at: 2026-07-04T20:55:00+08:00
- last_recheck_at: 2026-07-06T09:12:56+08:00

### TBD 場次（待補查）
_（6 場 TBD 已於 07-06 補查全部公布，無剩餘）_

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Miles Mikolas | WSH home | HOU (.695 🟢 / vs RHP .728) | 1% | 25/19 | <P25·<P25·**>P90**·P60-70·P50-60 | ❌ 不推 (deep) | deep 降級：近 6 場 3 次 HR 崩局（MIA 6ER/3HR·TB 5ER/2HR·BOS 6ER/2HR，近 6 ERA 4.50，floor hard rule 觸發）— Sum 25 靠 elite BB/9 撐但 HR boom/bust 打穿 WHIP-only；K9 5.0 零 K + swingman 無 QS。僅「本週唯一缺 WHIP + 能吃 HR variance」窄情境 |
| Noah Cameron | KC home | PHI (.774 🔴 / vs LHP .667) | 21% | 17/29 | P25-40·P40-50·P60-70·<P25·<P25 | ❌ 不推 (deep) | deep 維持：近 4 場 ERA 9.00 tailspin（TB 兩連爆，sample=none 高信心非噪音）+ GB/xwOBACON <P25。唯一利多 PHI vs LHP .667 弱 + K9 8.1 → 三位裡最有 K 賭注（限 K contested + ERA/WHIP 零邊際情境小賭 5-7K）|
| Kyle Freeland | COL away | LAD (.847 🔴 / vs LHP .762) | 1% | 17/19 | <P25·P25-40·P80-90·P25-40·<P25 | ❌ 不推 (deep) | deep 維持：最糟串流點 — LAD 全面火燙（30d .801→14d .845）+ @Dodger + 季 ERA 7.25；近 6 場 3 崩含 2 次對弱打 LAA/ATH（floor hard rule (a)）。硬避開 |

### 備註
- 2026-07-06 09:12 補查（6 場 TBD 全公布）+ deep eval（3 位候選）：
  - **Miles Mikolas**：⚠️ 條件推（scan） → **❌ 不推 (deep) 降級**。差異訊號 = 近 6 場 3 次 HR 驅動崩局（含對弱打 MIA），floor risk 高；scan Sum 25 靠 elite BB/9，反映不到 HR boom/bust；K9 5.0 零 K + IP/GS <P25 無 QS。
  - **Noah Cameron**：❌（scan） → **❌ 不推 (deep) 維持**。差異訊號 = 近 4 場 ERA 9.00 tailspin（TB 兩連爆）蓋過唯一利多 PHI vs LHP .667；但 K9 8.1 + PHI 高 K% 保留 K 天花板（6/2 CIN 8K / 6/7 MIN 7K）。
  - **Kyle Freeland**：❌（scan） → **❌ 不推 (deep) 維持**。差異訊號 = LAD 三窗遞增 .801→.845 全聯盟頂燙 + @Dodger + 對弱打 LAA/ATH 都崩，無翻案。
- deep 排序：**Cameron ≈ Mikolas >> Freeland**。要 K（K contested + ERA/WHIP 零邊際）→ Cameron；要 WHIP/吃 IP → Mikolas；Freeland 硬避開。**本日無安全串流點**，三位皆 ❌，僅在必動 acquisition 補特定 contested 類別時二選一（Cameron 賭 K / Mikolas 賭 WHIP）。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-07-07
- recorded_at: 2026-07-06T09:19:00+08:00
- last_recheck_at: 2026-07-06T09:22:00+08:00

### TBD 場次（待補查）
- MIL @ STL (STL home TBD)
- MIL @ STL (both TBD)（雙重賽 G2）
- ATL @ PIT (ATL away TBD)
- SEA @ MIA (SEA away TBD)
- NYY @ TB (TB home TBD)
- KC @ NYM (both TBD)
- PHI @ CIN (PHI away TBD)
- AZ @ SD (SD home TBD)
- TOR @ SF (TOR away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 | mlb_id |
|---|---|---|---|---|---|---|---|---|
| Trevor McDonald | SF home | TOR (.570 🟢 / vs RHP .701) | 5% | 29/46 | <P25·P25-40·P40-50·**>P90**·**>P90** | ⚠️ 條件推 (deep) | deep 降級：近 6 場 ERA 4.50（觸 ❌ 邊界）+ 弱-中打崩盤 fingerprint（5/22 CWS 7ER·6/13 CHC 4ER）+ 近 6 IP/GS 4.67 → QS 轉換率低於 Sum 29 結構暗示；但 TOR 14d .570 全日最冷（7d .487 噪音、14d 錨仍極弱）+ 末 2 場回穩（ATL 3ER·AZ 6IP 0ER）→ 當日最佳但非安全串流點 | 686790 |
| Andrew Alvarez | WSH home | HOU (.710 🟢 / vs LHP .714) | 4% | 22/25 | <P25·**P80-90**·<P25·**>P90**·<P25 | ⚠️ 條件推 (deep) | deep 維持（範圍收窄）：全季 11 出賽 0 QS、單場上限 4.2 IP / PC≤90 硬 workload cap → QS 0%·W≈0%（先發 W 需 5 完整局，本季從未達過）；近 6 ERA 2.45 + K9 10.9 floor 低 — 純「4 局賭 5-6 K + 小補 IP」窄情境 | 674841 |
| Zac Gallen | AZ away | SD (.770 🔴 / vs RHP .675) | 35% | 16/28 | <P25·<P25·P50-60·P60-70·<P25 | ❌ 不推 (deep) | deep 維持（強化）：近 6 場 ERA 8.54、5/6 場 ER≥4、7 HR、K9 3.9 全面崩壞；SD 30d→7d .735→.785 遞增火燙蓋過季 vs RHP .675 — 硬避開 | 668678 |

### 備註
- 2026-07-06 09:22 deep eval（3 位候選）：
  - **Trevor McDonald**：✅ 推（scan）→ **⚠️ 條件推 (deep) 降級**。差異訊號 = 近 6 場 ERA 4.50（觸 ❌ 邊界）+ 弱-中打崩盤 fingerprint（CWS 7ER / CHC 4ER）是 Sum 29 反映不到的 QS 轉換率問題；TOR 14d .570 極弱（7d .487-14d 落差 .083 → 強制 14d 錨）+ 末 2 場回穩（ATL 3ER·AZ 6IP 0ER 1H）留住條件推。
  - **Andrew Alvarez**：⚠️（scan）→ **⚠️ 維持（範圍收窄）**。差異訊號 = 全季 0 QS / 單場 max 4.2 IP 硬 workload cap → 先發 W 需 5 完整局，本季未達過 → W≈0%；比 scan「賭 K」更窄：只值 4 局 5-6 K + 比率小補（近 6 WHIP 1.44 其實不算保護）。
  - **Zac Gallen**：❌（scan）→ **❌ 維持（強化）**。差異訊號 = 近 6 ERA 8.54 + 5/6 場崩 + 7 HR + K9 3.9；SD 三窗遞增 .735→.770→.785 真火燙非噪音。
- deep 排序：**McDonald > Alvarez >> Gallen**。要 QS/W → 唯一 McDonald（QS ~45-50%）；K contested + ERA 保護 → Alvarez 4 局 5-6 K（零 QS/W 貢獻）；Gallen 硬避開。本日 McDonald 是「最佳但非安全」串流點。
- _（free-form 區，用戶可手寫「已 claim X 」「想下週再評估 Y」等註記。AI 讀進來但不主動覆寫。）_
