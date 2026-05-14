# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-14
- recorded_at: 2026-05-13T13:40:00+08:00
- last_recheck_at: 2026-05-14T13:00:00+08:00

### TBD 場次（待補查）
- MIA @ MIN (MIN home TBD)

### 已評估
_（本次重跑無通過 Rotation gate + Sum ≥15 + opener 真先發的 FA 候選；DET away 已公布 Keider Montero 為本隊球員，其餘 starter 全 owned by 別隊。）_

### 備註
- 2026-05-13 21:30 補查：TBD 兩場 (DET away / MIN home) 仍未公布 starter，新評 0 位。
- 2026-05-13 21:30：Robby Snelling 已被別隊撿走（用戶確認），從評估表移除（不再是 FA 候選）。
- 2026-05-14 13:00 重跑：DET away 公布 Keider Montero（本隊）。MIN home 仍 TBD。FA candidates 仍 0 位。

## ET 2026-05-15
- recorded_at: 2026-05-13T21:30:00+08:00
- last_recheck_at: 2026-05-14T22:00:00+08:00

### TBD 場次（待補查）
- PHI @ PIT (both TBD)
- BAL @ WSH (WSH home TBD)
- TOR @ DET (DET home TBD)
- MIL @ MIN (both TBD)
- BOS @ ATL (both TBD)
- TEX @ HOU (both TBD)
- KC @ STL (KC away TBD)
- AZ @ COL (COL home TBD)
- LAD @ LAA (LAD away TBD)
- SF @ ATH (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Sean Burke | CWS | CHC (.661) | 25% | 24/15 | <P25·<P25·**P80-90**·P40-50·**P70-80** | ✅ 強推 (deep) | CHC **7d OPS .522** 極弱 + 趨勢強下滑 (.785→.661→.522)；Burke **近 4 場 ERA 3.04 / QS 75%**（5/8 SEA 爆是 outlier）；BB/9 + xwOBACON 雙菁英剛好對應 CHC 弱點 |
| Dustin May | STL | KC (.709) | 15% | 20/13 | P25-40·<P25·**P70-80**·P40-50·P25-40 | ⚠️ 條件推 (deep) | **近 6 場 ERA 2.55 / QS 83% / IP/GS 5.89**（開季 2 場污染整季 Sum 20）；KC 7d .761 中等持平不到強推門檻，但 floor risk 已消 + 結構回歸風險仍在 |
| Jesse Scholtens | TB | MIA (.663) | 2% | 18/24* | <P25·<P25·P25-40·P40-50·**P70-80** | ❌ 不推 (deep) | **6 場僅 2 場 GS=1**（4 場 bulk relief）+ 真先發 IP avg **4.92** → QS<15%；MIA 7d .655 弱對手但 role 是 disqualifier，對手再弱也救不了 |

_*Scholtens 2025 sum 24 但 GS=0 全 RP，IP/GS 缺值；雙年 prior 不是真實 SP 樣本。_

### 備註
- 2026-05-14 22:00 deep eval（3 位候選）：
  - **Burke**：⚠️ → ✅ 強推。差異訊號 = CHC 7d .522 極弱 + 趨勢下滑 + 近 4 場 ERA 3.04 / QS 75%（5/8 SEA 爆 outlier）
  - **May**：❌ → ⚠️ 條件推。差異訊號 = 近 6 場 ERA 2.55 / QS 83%（開季 TB/DET 兩場污染 Sum 20）；KC 7d .761 中等沒到強推
  - **Scholtens**：❌ 維持。深評確認 mixed-role（6 場僅 2 GS / 真先發 IP avg 4.92），對手 .655 弱救不了 role
- 排序：**Burke ≈ May >> Scholtens**。Burke 對 ERA/WHIP 翻盤較好；May 對 QS/IP 累積較穩。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
