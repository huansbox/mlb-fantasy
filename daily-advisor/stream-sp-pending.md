# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-05
- recorded_at: 2026-06-05T10:43:32+08:00
- last_recheck_at: 2026-06-05T11:00:00+08:00

### TBD 場次（待補查）
- LAA @ LAD (LAA away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Jack Perkins | ATH @ HOU | HOU (.747 🟡) | 5% | 33/27 | —·**>P90**·P70-80·P40-50·**>P90** | ⚠️ 條件推 (deep) | 深評維持。17 場全 relief，唯一 start 5/25 vs SEA 4.2IP/2ER/7K（K carry）；近 6 場 ERA 7.71 + floor「低」hint 皆 relief 短局假象（starter 樣本僅 1 場）；對手 HOU 14d .747 升溫中強；ramp-up IP~5 QS 25-35%。whiff>P90/K9 12/xERA 3.15 撐 ceiling 但 variance 大 |
| Ryan Feltner | COL vs MIL | MIL (.728 🟡) | 1% | 20/25 | <P25·P50-60·P50-60·P50-60·<P25 | ❌ 不推 (deep) | 深評維持。IL gap 4/23→5/30 健康先發僅 1 場；floor 高（4/11 SD 6ER 2HR + 主場 Coors + xwOBACON <P25）+ 對手 MIL 30d.720→7d.769 升溫 + 7d BB% 14.2 選球佳 + ⚠️ 賣高運氣 ERA 回升 |

### 備註
- 2026-06-05 首次評估（recorded 10:43）：Feltner 通過 Rotation gate + Sum ≥15 + true_starter；Jack Perkins rotation_gate 機械 🚫（GS=0）但 WebSearch 確認真先發拉回主表。已過濾：Ryan Gusto (MIA vs TB, 🚫 GS=0 + BBE=0 不可信) + Kyle Leahy (STL vs CIN, Sum 13 hard floor) + Brandon Sproat (MIL @ COL, Sum 14 hard floor + Coors) + 別隊 22 位（含 Roki Sasaki / Framber Valdez / Jesús Luzardo / Michael King）+ 本隊 1 位（Parker Messick @ TEX）。
- TBD 1 場（LAA @ LAD，LAA away SP 未公布；LAD = Roki Sasaki 別隊），此場價值低。
- 排序：**Perkins > Feltner**。Perkins 唯一 ⚠️ 條件推（結構菁英但 ramp-up IP 風險）；Feltner 結構弱 + Coors + 賣高運氣。
- 用戶決策建議：① 缺 K → Perkins（whiff/K9 雙菁英 + buy-low，賭 ramp-up）② 缺 QS/IP 不想賭 rookie ramp-up → 本日 pass 等補查或看 fa_scan worst SP。
- 2026-06-05 11:00 deep eval（2 位候選 Perkins + Feltner）：
  - **Jack Perkins**：⚠️ 條件推 → ⚠️ 維持 (deep)。差異訊號 = game log 確認 17 場全 relief，唯一 start 5/25 vs SEA 4.2IP/2ER/7K（K carry）；近 6 場 ERA 7.71 + floor「低」hint 皆 relief 短局 cluster luck 假象（starter floor 樣本僅 1 場）；對手 HOU 30d.664→14d.747 升溫中強。維持 ⚠（whiff>P90/K9 12/xERA 3.15 buy-low 撐 ceiling，但 ramp-up IP~5 → QS 25-35%）
  - **Ryan Feltner**：❌ 不推 → ❌ 維持 (deep)。差異訊號 = IL gap 4/23→5/30 健康先發僅 1 場（5/30 SF 6/0ER QS）；floor 高（4/11 SD 6ER 2HR + 主場 Coors 放大 + xwOBACON <P25）+ 對手 MIL 30d.720→7d.769 階梯升溫 + 7d BB% 14.2 選球佳 + ⚠️ 賣高運氣 ERA 將回升
- 排序：**Perkins >> Feltner**（不變）。Perkins K/buy-low ceiling 高但 variance 大（ramp-up + 對手中強）；Feltner Coors + 結構弱 + 對手升溫，❌。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-06
- recorded_at: 2026-06-05T10:43:32+08:00
- last_recheck_at: 2026-06-05T11:00:00+08:00

### TBD 場次（待補查）
- BAL @ TOR (TOR home TBD)
- TB @ MIA (MIA home TBD)
- LAA @ LAD (LAA away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Sean Burke | CWS @ PHI | PHI (.635 🟢) | 29% | 19/11 | <P25·<P25·P60-70·<P25·**P80-90** | ⚠️ 條件推 (deep) | 深評維持，兩日整體最穩。近 6 場 2 崩集中 5/8-5/15、最近 3 場 5/20→5/26→5/31 回穩（2/2/1 ER + 8K/6K，K 比 Whiff<P25 暗示多 K9 8.27）；對手 PHI 14d .635 冷 + 7d .701 微反彈回歸後弱-中 + vs RHP .687；QS 45-55% |
| Griffin Canning | SD vs NYM | NYM (.66 🟢) | 3% | 17/19 | <P25·P50-60·<P25·P70-80·<P25 | ❌ 不推 (deep) | 深評維持。floor 極高（近 6 場 2 大崩含 5/14 MIL 1.2IP/6ER/4BB 控球崩 + 7 HR/6 場 + BB/9 4.88 失控）；對手 NYM 7d .746 觸發 hard rule 強制 14d .660 錨（對位弱救不了自身）；luck buy-low 需控球先穩賭注大 |

### 備註
- 2026-06-05 首次評估（recorded 10:43）：Burke + Canning 通過 Rotation gate + Sum ≥15 + true_starter。已過濾：Tanner Gordon (COL vs MIL, 🚫 GS=2 game-log IP/GS<3 + Coors) + Matthew Liberatore (STL vs CIN, Sum 11 hard floor) + 別隊 22 位（含 Spencer Strider / Yamamoto / Joe Ryan / Tanner Bibee / Ranger Suarez / Misiorowski / Nolan McLean）+ 本隊 1 位（Keider Montero vs SEA）。
- TBD 3 場（BAL@TOR / TB@MIA / LAA@LAD），建議 TW 6/6 早上呼叫 `/stream-sp 補查` 補查。
- 排序：**Burke > Canning**。Burke 唯一 ⚠️ 條件推（對位 + 控球 + contact 壓制，K 少）；Canning 對位好但 BB/9 失控 + ERA 7.16 風險高。
- 用戶決策建議：① 缺 QS/ERA/WHIP 且要穩 → Burke（WHIP 1.13 + IP/GS 5.2 + 對手最冷）② 缺 K → 兩位都不適合（Burke whiff <P25 / Canning P50-60）③ 不想賭 → 等 3 場 TBD 補查。
- 2026-06-05 11:00 deep eval（2 位候選 Burke + Canning）：
  - **Sean Burke**：⚠️ 條件推 → ⚠️ 維持 (deep)，當日 + 兩日整體最穩。差異訊號 = 近 6 場 2 崩集中 5/8-5/15、最近 3 場 5/20→5/26→5/31 回穩（2/2/1 ER + 8K/6K，K 比 Whiff<P25 暗示多 K9 8.27）；對手 PHI 30d.667→14d.635 急冷→7d.701 微反彈回歸後弱-中 + vs RHP .687；QS 45-55%
  - **Griffin Canning**：❌ 不推 → ❌ 維持 (deep)。差異訊號 = floor 極高（近 6 場 2 大崩含 5/14 MIL 1.2IP/6ER/4BB 控球崩 + 7 HR/6 場 + BB/9 4.88 失控）；對手 NYM 7d .746 vs 14d .660 落差 .086 觸發 hard rule 強制 14d 錨（對位弱是利多但救不了自身控球/HR）；luck buy-low 需控球先穩賭注太大
- 排序：**Burke >> Canning**（不變）。Burke 命中率最高（floor 修復 + 對位 + QS 45-55%）；Canning 控球崩 + HR 海 ❌。
- 跨兩日整體排序（4 位深評）：**Burke > Perkins >> Feltner ≈ Canning**。Burke 命中率最高、Perkins ceiling 最高 variance 最大、Feltner/Canning 皆 ❌。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
