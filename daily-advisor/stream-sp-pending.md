# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-21
- recorded_at: 2026-05-21T15:30:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- NYM @ WSH (NYM away TBD)
- TOR @ NYY (TOR away TBD)
- COL @ AZ (COL away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| _(無候選通過 Sum ≥15 + Rotation gate)_ |  |  |  |  |  |  |  |

### 備註
- 2026-05-21 15:30 首次評估：0 位 FA 候選；別隊 9 位（Mize/Ashcraft/May/Cavalli/Strider/Alcantara/Rodón/Soriano/E.Rodriguez）/ 本隊 2 位（Cantillo/Severino）。
- TBD 3 場均 away 隊 TBD，補查 ROI 低（公布後多半 owned by 別隊）。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-22
- recorded_at: 2026-05-21T15:30:00+08:00
- last_recheck_at: 2026-05-21T16:00:00+08:00

### TBD 場次（待補查）
- HOU @ CHC (both TBD)
- PIT @ TOR (both TBD)
- DET @ BAL (DET away TBD)
- WSH @ ATL (both TBD)
- TEX @ LAA (both TBD)
- ATH @ SD (ATH away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Chris Paddack | CIN home | STL (.692) | 1% | 22/17 | <P25·P25-40·P50-60·P40-50·**P60-70** | ❌ 不推 | Sum<25；5/17 deep eval 已認近 4 場 ERA 9.29 + xERA luck 沒回歸，5/22 對 STL 中等不夠抵銷 |
| Chris Bassitt | BAL home | DET (.612) | 12% | 20/27 | <P25·P25-40·<P25·P60-70·**P70-80** | ❌ 不推 (deep) | DET 30d→7d -.149 強下滑利好被 Bassitt 自身對弱對手 1/6 QS pattern 抵銷；5/9 ER≥4 = 56% floor 結構性高；xERA 4.98 真被打無 luck 空間 |

### 備註
- 2026-05-21 15:30 首次評估：2 位候選；過濾 Kyle Leahy（Sum 14 hard floor）+ 別隊 17 位 + 本隊 0 位。
- TBD 6 場（含 4 場 both TBD），建議 TW 5/22 早上 9-10 點補查。
- Paddack/Bassitt 與 5/16-5/17 deep eval 結論一致（❌ ❌），5 天內結構無實質改善。
- 2026-05-21 16:00 deep eval（1 位候選 Bassitt）：
  - **Bassitt**：❌ 維持加強。差異訊號 = DET 7d .534 / 30d→7d -.149 強下滑「對手利好」訊號被 Bassitt 自身結構問題抵銷（對弱對手 PIT 6ER/KC 5ER/MIA 4ER/WSH 4ER 1/6 QS = 16.7%）；近 6 場 ERA 4.50 + 3/6 ER≥4 = 50% floor structural
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-23
- recorded_at: 2026-05-21T15:30:00+08:00
- last_recheck_at: 2026-05-21T16:00:00+08:00

### TBD 場次（待補查）
- TB @ NYY (NYY home TBD)
- HOU @ CHC (both TBD)
- PIT @ TOR (both TBD)
- DET @ BAL (DET away TBD)
- MIN @ BOS (both TBD)
- WSH @ ATL (both TBD)
- ATH @ SD (ATH away TBD)
- TEX @ LAA (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Stephen Kolek | KC home | SEA (.653) | 5% | **33/33** | P60-70·<P25·**P80-90**·P70-80·P70-80 | ⚠️ 條件推 (deep) | SEA 7d .590 + 30d→7d -.115 強下滑（回歸實質 .640-.680 弱級）；2025 同 Sum 33 + 113 IP 3.51 ERA baseline 真實力非 outlier；5/17 對 STL 復活 6.1 IP 0 ER；3 場樣本仍是主要風險 |
| Roki Sasaki | LAD away | MIL (.722) | **35%** | 17/15 | <P25·**P80-90**·<P25·P40-50·<P25 | ❌ 不推 (deep) | MIL 30d→7d +.090 強上升熱化；MIL 7d K% 15.3% 偏低使 Whiff P80-90 K 工具受抑；對中等對手歷史 1/4 QS pattern 致命；HR 機器 8 HR/8 GS 對熱化對手極危 |
| Brady Singer | CIN home | STL (.693) | 14% | 16/19 | <P25·P25-40·P70-80·P25-40·**<P25** | ❌ 不推 | 2026 xwOBACON .429 <P25 contact 結構崩 + xERA 6.09 真被打 |

### 備註
- 2026-05-21 15:30 首次評估：3 位候選；過濾 6 位 Sum<15（Brandon Young 13/Fedde 13/Houser 14/Christian Scott 13/Robert Gasser 13/Lucas Giolito 13）+ 別隊 7 位 + 本隊 1 位（Pallante）。
- TBD 8 場（53% TBD 比例偏高），建議 TW 5/23 早上補查。
- Kolek 唯一 Sum ≥25 候選但 GS=3 樣本仍小，5/17 時 Sum=12 hard floor 排除；近 3 場跳升須觀察是否 outlier。撿建議 FAAB $0-1。
- Sasaki 純 K 工具，5/17 deep eval 結論一致；%own 35% 市場已半握。
- 2026-05-21 16:00 deep eval（2 位候選 Kolek + Sasaki）：
  - **Kolek**：⚠️ 維持 (deep)。差異訊號 = SEA 7d .590 / 30d→7d -.115 強下滑（回歸實質「弱」.640-.680）+ 2025 baseline 真實力（113 IP 3.51 ERA）+ 5/17 對 STL 復活；3 場樣本（5/12 對 CWS 弱卻爆 5 ER）+ Whiff <P25 K 工具弱仍是兩大風險
  - **Sasaki**：⚠️ → ❌ 降級 (deep)。差異訊號 = MIL 30d→7d +.090 強上升（scan 14d .722 baseline 沒反映熱化加劇）+ MIL 7d K% **15.3% 偏低**使 Sasaki 唯一強項 Whiff P80-90 K 工具失去發揮空間 + 對中等對手歷史 1/4 QS（4/12 TEX / 4/25 CHC / 5/11 SF 全爆）
- 排序：**Kolek >>> Sasaki >>> Singer**。Kolek 全 7 維度勝（對手 7d / 趨勢 / Floor / Sum26 / 雙年 / QS%）；Sasaki 僅在「K contested + ERA/WHIP 已輸定」狹窄情境適用；Singer 結構性崩。建議 FAAB $0-1 單撿 Kolek。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
