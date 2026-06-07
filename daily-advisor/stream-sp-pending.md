# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-07
- recorded_at: 2026-06-06T10:32:16+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- NYM @ SD (NYM away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Trevor McDonald | SF @ CHC | CHC (.723 🟡) | 11% | 40/46 | P60-70·P60-70·P60-70·**>P90**·**P80-90** | ✅ 推 | 全 5 軸 P60+ 雙菁英（GB% 61.6 >P90 + xwOBACON .349 P80-90）+ IP/GS 5.67 深投；對手 CHC 14d .723 🟡 中等 + vs RHP .728；ERA 4.50 xERA 3.83 小幅 buy-low；風險僅樣本 6 GS + 客場 Wrigley。6/2 自家 drop（換 Buehler）後結構回升 |
| Connor Prielipp | MIN vs KC | KC (.698 🟢) | 8% | 19/— | <P25·P40-50·<P25·P40-50·P60-70 | ⚠️ 條件推 | buy-low：ERA 5.26 vs xERA 3.80（✅ 撿便宜運氣）+ 對手 KC 14d .698 🟢 冷 + K9 9.6 + vs LHB .677；風險 Sum 19 偏低 + BB/9 3.89 <P25 控球偏差 + 2025 無 prior（rookie 待驗）|
| Bubba Chandler | PIT @ ATL | ATL (.747 🟡) | 61% | 16/27 | <P25·P50-60·<P25·<P25·P60-70 | ❌ 不推 | BB/9 6.0 <P25 嚴重失控 + GB% <P25 + Sum 16 偏弱；對手 ATL .747 🟡 中強；ERA 5.05 xERA 4.45。61% owned 高但結構不支持串流 |

### 備註
- 2026-06-06 首次評估（recorded 10:32）：McDonald + Prielipp + Chandler 通過 Rotation gate + Sum ≥15 + true_starter。已過濾 Sum<15 hard floor 3 位：David Sandlin (CWS@PHI, Sum 13, opener_verdict small_sample 但 Sum 先排除跳過 WebSearch) + Rhett Lowder (CIN@STL, Sum 12) + Kyle Freeland (COL vs MIL, Sum 12 + Coors + ERA 8.06)。別隊 22 位（含 deGrom / Aaron Nola / Sandy Alcantara / Spencer Strider 等）+ 本隊 1 位（Joey Cantillo @ TEX）。
- TBD 1 場（NYM @ SD，NYM away SP 未公布；SD = Randy Vásquez 別隊），建議 TW 6/7 早上補查。
- 排序：**McDonald >> Prielipp > Chandler**。McDonald 唯一 ✅ 推（Sum 40 雙菁英 + 對手中等），命中率最高；Prielipp buy-low 賭注（Sum 低但運氣 + K + 對手冷）；Chandler 控球崩 ❌。
- 用戶決策建議：① 缺 QS/IP/ERA 想穩 → McDonald（深投 + GB 壓 HR + 對手中等）② 缺 K + 願賭 buy-low → Prielipp（K9 9.6 + ERA 回歸 + 對手冷，但控球風險）③ 不缺或對手嫌硬 → pass / 等 TBD 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-08
- recorded_at: 2026-06-07T21:02:00+08:00
- last_recheck_at: 2026-06-07T21:20:00+08:00

### TBD 場次（待補查）
- SEA @ BAL (both TBD)
- BOS @ TB (both TBD)
- PHI @ TOR (both TBD)
- HOU @ LAA (both TBD)
- WSH @ SF (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Jeffrey Springs | ATH vs MIL | MIL (.782 🔴 / vs LHP .648) | 22% | 23/22 | P40-50·P25-40·P60-70·<P25·P60-70 | ❌ 不推 (deep) | 近 6 場 ERA 4.88 + QS 1/6 + floor 高（近 6 場 3 崩）；flyball（GB <P25）近 8 場 11 HR 對 MIL 7d .911 熱化長打線 = HR mismatch；vs LHP .648 是全季均值，熱化期回歸只到 14d .782 救不了。對位利多蓋不過自身近況崩 + HR 暴露 |

### 備註
- 2026-06-07 首次評估（recorded 21:02）：Springs 唯一過 Rotation gate + Sum ≥15 + true_starter。owned_by_others 別隊 4 位（Will Warren NYY@CLE / Gavin Williams CLE vs NYY / Andrew Abbott CIN@SD / Kyle Harrison MIL@ATH）+ 本隊 1 位（Walker Buehler SD vs CIN）。無 Sum<15 / rotation gate / opener 過濾項。
- TBD 5 場（SEA@BAL / BOS@TB / PHI@TOR / HOU@LAA / WSH@SF，全 both TBD），建議 TW 6/8 早上呼叫 `/stream-sp 補查` 補查。
- 排序：**Springs 單獨**（⚠️ 條件推）。關鍵 = 機械 tier 🔴 是 MIL 整體 14d，但對左投 .648 弱（Springs 左投對位實際偏 🟢）；穩定深投 + 控球給 QS floor，但缺 K。
- 2026-06-07 21:20 deep eval（與 6/9 Gasser/Giolito 同輪 3 位）：
  - **Jeffrey Springs**：⚠️ 條件推 → **❌ 不推**。差異訊號 = 近 6 場 ERA 4.88 + QS 1/6 + floor 高（5/12 STL · 5/22 SD 3HR · 6/3 CHC 2HR 三崩）；flyball 近 8 場 11 HR 對 MIL 7d .911 熱化長打線 HR mismatch。vs LHP .648 對位利多真實但救不了近況崩 + HR 結構（7d .911 vs 14d .782 落差 .129 觸發 hard rule 強制 14d 錨，熱化期對左投也可能高於季均 .648）。game log 顯示 Springs QS 不隨對手強弱、隨自身 HR 運氣（早季對 HOU/NYY 反 QS、對 CWS 弱打 7ER 崩）。
- 跨兩日整體排序見 ET 6/9 備註。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-09
- recorded_at: 2026-06-07T21:02:00+08:00
- last_recheck_at: 2026-06-07T21:20:00+08:00

### TBD 場次（待補查）
- SEA @ BAL (both TBD)
- LAD @ PIT (both TBD)
- BOS @ TB (both TBD)
- MIN @ DET (both TBD)
- AZ @ MIA (AZ away TBD)
- NYY @ CLE (both TBD)
- PHI @ TOR (both TBD)
- STL @ NYM (both TBD)
- TEX @ KC (both TBD)
- ATL @ CWS (both TBD)
- CHC @ COL (both TBD)
- HOU @ LAA (both TBD)
- WSH @ SF (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Robert Gasser | MIL @ ATH | ATH (.683 🟢) | 1% | 19/17 | <P25·P60-70·<P25·—·>P90 | ⚠️ 條件推 (deep) | 對手 ATH 三窗口一致冷（30d .692→14d .683→7d .630）+ vs LHP .701 中性 + K% 高利收割；近 3 場 4.73 ERA 全被 5/23 LAD 4ER 單崩汙染（去 LAD = 2.89），最近 6/3 vSF 5IP/1ER/5K 回穩。風險 = IP/GS 4.44 短局 + BB/9 4.73 + 3 場樣本。缺 K 願賭可，要 QS 不適合 |
| Lucas Giolito | SD vs CIN | CIN (.719 🟢) | 8% | 19/11 | <P25·P60-70·<P25·—·>P90 | ❌ 不推 (deep) | BB/9 7.02 + WHIP 1.74 控球災難（4 場 13BB）+ 0/4 QS + IP/GS 4.17 短局；5/29 對 WSH 弱打崩盤 2.2IP/4ER/4BB/2HR → floor 高；對手 CIN 冷（vs RHP .694）救不了自身控球崩，全面風險無加分側 |

### 備註
- 2026-06-07 首次評估（recorded 21:02）：Gasser + Giolito 過 Rotation gate + Sum ≥15 + true_starter。owned_by_others 別隊 2 位（Max Meyer MIA vs AZ / Chase Burns CIN@SD）+ 本隊 1 位（J.T. Ginn ATH vs MIL）。無 Sum<15 / opener 過濾項。
- TBD 13 場（其中 AZ@MIA 僅 away TBD，其餘 both TBD），建議 TW 6/9 早上補查（13 場大宗未公布，補查價值高）。
- 排序：**Gasser > Giolito**。兩位皆 Sum 19 短局型，Gasser 控球較不崩（BB/9 4.73 vs Giolito 7.02）+ xERA<ERA buy-low 味道 + 對手最冷；Giolito BB/9 7.02 + WHIP 1.74 控球災難 ❌。兩位 IP/GS 皆 <P25，QS floor 都低。
- 2026-06-07 21:20 deep eval（與 6/8 Springs 同輪 3 位）：
  - **Robert Gasser**：⚠️ 條件推 → ⚠️ 維持 (deep)。差異訊號 = ATH 三窗口一致冷（.692→.683→.630，無 hard rule 觸發）+ K% 24-25% 高利 K 收割；近 3 場 4.73 ERA 全被 5/23 LAD 單崩汙染（去 LAD = 2.89），6/3 vSF 5IP/1ER/5K 回穩。3 場樣本 buy-low 賭注，短局 + BB/9 4.73 限 QS。
  - **Lucas Giolito**：❌ 不推 → ❌ 維持 (deep)。差異訊號 = 4 場 13BB（BB/9 7.02）+ WHIP 1.74 控球災難 + 0/4 QS + 5/29 對 WSH 弱打崩盤（floor 高）；對手 CIN 冷救不了自身控球。
- 跨兩日整體排序（3 位深評）：**Gasser > Springs >> Giolito**。Gasser 唯一 ⚠️（對手最冷 + K + 回穩，短局/控球賭注）；Springs season 最穩但 deep 降 ❌（flyball vs MIL 熱化 HR mismatch + 近 6 場 4.88）；Giolito 控球災難最差。缺 K 願賭 → Gasser；缺 QS/IP 想穩 → 三位皆不適合，等 6/9 13 場 TBD 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
