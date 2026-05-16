# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-16
- recorded_at: 2026-05-15T12:10:00+08:00
- last_recheck_at: 2026-05-16T10:35:00+08:00

### TBD 場次（待補查）
- NYY @ NYM (NYM home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Cade Cavalli | WSH home | BAL (.639) | 14% | 24/31 | <P25·**P70-80**·<P25·P50-60·**P70-80** | ✅ 推 (deep) | BAL **7d .595 極弱 + 30d→7d 強下滑 -.073**；BAL K% 26.7% 對 Whiff P70-80 直接利 K；Cavalli 近 5 場 ERA 3.64 + floor risk 低（4/13 PIT 1.1IP 4ER 是 outlier）|
| Chris Paddack | CIN | CLE (.665) | 1% | 20/15 | <P25·P40-50·P50-60·P25-40·P40-50 | ❌ 不推 (deep) | **近 4 場 ERA 9.29 災難**（7 場 4 場 ER ≥5，連對弱也爆）；CLE K% 16.9% contact 線抵銷 K 期望 + BB% 14.7% 極高吃 PC，luck (xERA 4.33) 連 4 場沒回歸 |
| Chris Bassitt | BAL | WSH (.803) | 13% | 21/28 | <P25·P25-40·<P25·P70-80·P70-80 | ❌ 不推 (deep) | **WSH 30d→7d 強上升 +.093**（.704→.769→.797 正熱化）；Bassitt 近 6 場 ERA 3.43 反而回升但對手熱抵銷；對「強/中-強」歷史 1/3 QS |

### 備註
- 2026-05-15 12:10 首次評估（3 位候選通過 Rotation gate + Sum ≥15 + opener 真先發）。
- 已過濾：Kai-Wei Teng（Rotation gate 🚫，2026 GS 2/15 mixed role）/ Kyle Leahy（Sum 14 hard floor）。
- 2026-05-15 13:00 deep eval（3 位候選）：
  - **Cavalli**：✅ 維持。深評確認訊號 = BAL 7d .595 + 趨勢強下滑 + K% 26.7% 高利 K + Cavalli 近 5 場 ERA 3.64 floor 低
  - **Paddack**：❌ 維持加強。差異訊號 = 近 4 場 ERA 9.29（floor 系統性破裂，xERA luck 連 4 場沒回歸）+ CLE K% 16.9% contact 不利 K + BB% 14.7% 極高
  - **Bassitt**：❌ 維持加強。差異訊號 = WSH 30d→14d→7d 強上升 +.093（scan 14d baseline 沒反映）+ Bassitt 對中-強歷史 1/3 QS
- 排序：**Cavalli >>> Paddack ≈ Bassitt**。Cavalli 對 ERA/K 翻盤最好；Paddack/Bassitt 都 floor risk 不適合 contested。FAAB $1-3 撿 Cavalli。
- 2026-05-15 14:00 deep refresh（3 位全部，與 13:00 verdict 對齊）：
  - **Cavalli**：✅ 維持。差異訊號 = BAL 7d .595→**.603**（微升 +.008，仍極弱）；趨勢 30d→7d -.067 持續強下滑；K% 26.9% 利 K 不變
  - **Paddack**：❌ 維持加強。差異訊號 = CLE 7d .655→**.598**（再下滑 -.057！對手變更弱）— 但 Paddack 自己 floor 系統性破裂（近 4 場 ERA 9.00，連對 CWS/STL 弱-中等都爆）+ CLE BB% 7d 16.1% 極高必拖 PC，對手變弱救不了
  - **Bassitt**：❌ 維持加強。差異訊號 = WSH 7d .797→**.824**（再上升 +.027 熱化加劇）+ 30d→7d +.108 強上升；Bassitt 對弱對手已出現 floor risk (PIT 6ER/KC 5ER/MIA 4ER)，對熱化線更危
- 排序：**Cavalli >>> Paddack ≈ Bassitt**（與 13:00 一致）。Cavalli 唯一 ✅；Paddack 是 SP 結構破裂，Bassitt 是對手熱化，兩者 floor 皆高。建議 FAAB $1-3 單撿 Cavalli。
- 2026-05-15 14:00 **issue 011 e2e parity 確認** ✅（new session 走 /stream-sp-deep 全流程，refactored skill md + mlb_query helper 端到端跑通；verdict + 排序與 13:00 一致；數值小差源自此 session 13:00 end_date 用錯 5/15 應為 5/16，新 session 自然修正，非 regression）。feat/mlb-query-helper branch 可 merge。
- 2026-05-16 10:35 補查：3 場 TBD 中 TOR@DET（Mize/Fluharty）/ SD@SEA（Buehler/Gilbert）已公布但 starter 全 owned by 別隊 → 無新 FA 候選，僅更新 last_recheck_at + TBD list。剩 NYY@NYM（NYM home）TBD。舊評 Cavalli 已被別隊 claim（非本隊）。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-17
- recorded_at: 2026-05-16T10:35:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- BOS @ ATL (BOS away TBD)
- TEX @ HOU (TEX away TBD)
- MIL @ MIN (MIL away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Andre Pallante | STL home | KC (.694) | 6% | 28/31 | P25-40·P40-50·<P25·**>P90**·**P80-90** | ✅ 推 | GB% >P90 + xwOBACON P80-90 雙菁英抑長打，雙年 Sum 28/31 穩；對手 KC 🟢；風險 BB/9 4.04 <P25 吃 WHIP |
| Jeffrey Springs | ATH home | SF (.656) | 33% | 26/22 | P40-50·P40-50·P50-60·<P25·**P80-90** | ✅ 推 | xwOBACON P80-90 菁英 + xERA 3.59 < ERA 4.22 買低訊號；IP/GS 5.44 有 QS 機會；對手 SF 🟢；%own 33% 別隊可能搶 |
| Grant Holmes | ATL home | BOS (.680) | 16% | 24/23 | <P25·P70-80·<P25·P60-70·P60-70 | ⚠️ 借觀察 | Whiff P70-80（25 P80-90）K stuff 真，但 BB/9 4.57 <P25 爆局風險 + IP/GS <P25 QS 難；Sum 24 差 1 分到推薦線 |
| Adrian Houser | SF | ATH (.762) | 1% | 20/34 | P25-40·<P25·P40-50·P70-80·P25-40 | ❌ 不推 | K9 4.93 極低無 K 貢獻 + 對手 ATH .762 🔴；2025 Sum 34 是 slump 對照但 2026 五軸無菁英 |
| Brady Singer | CIN | CLE (.628) | 15% | 18/21 | <P25·P25-40·P70-80·P40-50·<P25 | ❌ 不推 | xwOBACON .420 <P25 contact 結構崩 + xERA 6.06 無運氣成分（真被打）；對手弱也救不了 |
| Roki Sasaki | LAD | LAA (.640) | 27% | 17/15 | <P25·**P80-90**·<P25·P40-50·<P25 | ⚠️ 條件推 | Whiff P80-90 K 上限高，但 IP/GS <P25 + BB/9 <P25 + xwOBACON <P25 + ERA 5.88 — K 樂透，僅在需 K 且能吃 ERA/WHIP 損失時撿 |
| Miles Mikolas | WSH home | BAL (.808) | 1% | 17/21 | <P25·<P25·P25-40·**P80-90**·P25-40 | ❌ 不推 | WebSearch 確認真先發（非 opener），但近況 ~4-5 IP / 7.00 ERA / 9 場僅 2 場 5+ IP；對手 BAL .808 🔴 |

### 備註
- 2026-05-16 10:35 首次評估（7 位候選通過 Rotation gate + Sum ≥15 + opener 真先發）。
- 已過濾：Brandon Young（Sum 13 hard floor）/ Stephen Kolek（Sum 12 hard floor，rotation_gate ⚠️ small_sample 2 GS）。
- Miles Mikolas opener_suspect → WebSearch 確認：5/17 標準先發（非 opener；先前 3 次救援是 PJ Poulin opener 後 bulk arm，5/17 無 Poulin 配對），但近況短局 ~4-5 IP QS 機率低 → 進主表評為 ❌。
- 排序：Pallante ≈ Springs（兩 ✅）>> Holmes（⚠️ 借觀察）≈ Sasaki（⚠️ K 條件推）>> Singer ≈ Houser ≈ Mikolas（❌）。
- TBD 3 場（BOS@ATL / TEX@HOU / MIL@MIN）均客場 TBD，建議 TW 5/17 早上補查。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
