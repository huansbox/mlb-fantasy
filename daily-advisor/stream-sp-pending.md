# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-15
- recorded_at: 2026-05-13T21:30:00+08:00
- last_recheck_at: 2026-05-15T12:10:00+08:00

### TBD 場次（待補查）
- MIL @ MIN (MIL away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| 🆕 Kyle Freeland | COL home | AZ (.583) | 2% | 20/21 | <P25·P50-60·P60-70·P40-50·<P25 | ⚠️ 借觀察 | AZ 14d .583 極弱對手，但 Freeland 5 軸無菁英 + 雙年 xwOBACON <P25 + Coors 主場放大風險，期望 IP 4-5 / QS 低 |

### 備註
- 2026-05-15 12:10 補查：舊評三位全部不再是 FA — **Burke 已 claim 成本隊 ✅**；**May / Scholtens 已被別隊撿走**。三 row 從表格移除。
- 唯一新評 Kyle Freeland（Sum 20 對手 .583 🟢🟢）— 借觀察等級不推，建議不串 5/15。
- 剩 1 場 TBD：MIL @ MIN（MIL away），TW 5/15 晚補查或讓它自然 13:00 過期。
- 2026-05-14 22:00 deep eval 紀錄（保留 audit）：
  - **Burke**：⚠️ → ✅ 強推（CHC 7d .522 極弱 + Burke 近 4 場 ERA 3.04 / QS 75%）→ 已 claim
  - **May**：❌ → ⚠️ 條件推（近 6 場 ERA 2.55 / QS 83%）→ 被別隊撿
  - **Scholtens**：❌ mixed-role 維持 → 被別隊撿

## ET 2026-05-16
- recorded_at: 2026-05-15T12:10:00+08:00
- last_recheck_at: 2026-05-15T13:00:00+08:00

### TBD 場次（待補查）
- TOR @ DET (both TBD)
- SD @ SEA (SD away TBD)
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
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
