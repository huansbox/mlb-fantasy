# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-06
- recorded_at: 2026-06-05T10:43:32+08:00
- last_recheck_at: 2026-06-06T10:32:16+08:00

### TBD 場次（待補查）
- BAL @ TOR (TOR home TBD)
- TB @ MIA (MIA home TBD)
- MIL @ COL (COL home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| 🆕 Jack Kochanowicz | LAA @ LAD | LAD (.856 🔴) | 4% | 25/16 | P25-40·P40-50·<P25·**>P90**·P50-60 | ❌ 不推 | GB% >P90（57.4% 唯一菁英軸）但對手 LAD 14d .856 🔴 聯盟頂級打線 + 客場 Dodger Stadium；BB/9 4.95 <P25 控球差 + K9 6.5 低 + vs RHP .793；ERA 5.23 xERA 5.19 無運氣修正，QS 機率低，串流 ROI 差 |

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
- 2026-06-06 10:32 補查（pending_diff 全空 → fallback 手動 cross-check）：**舊評 2 位全失效** — Burke 今日 CWS@PHI 先發換成 Brandon Eisert（Burke 不先發，已從表格移除）；Canning 今日被別隊認領（owned_by_others，已從表格移除）。**新評 1 位** — 🆕 Jack Kochanowicz（LAA@LAD，原 TBD 公布），❌ 不推（GB%>P90 但對手 LAD .856 🔴 + 控球差 + 低 K）。Eisert rotation_gate 🚫（GS=1/G=12）已過濾。**ET 6/6 無值得串流候選**。剩 3 場 TBD：BAL@TOR / TB@MIA / MIL@COL（LAA@LAD 已公布故移除，MIL@COL 新增）。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

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
