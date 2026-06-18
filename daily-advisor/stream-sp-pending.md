# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-18
- recorded_at: 2026-06-18T14:06:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- LAA @ ATH (LAA away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Sean Burke | CWS @ NYY | NYY (.834 🔴 / vs RHP .763) | 20% | 15/11 | <P25·P25-40·P25-40·<P25·P60-70 | ❌ 不推 | 對手 NYY 🔴 客場 + 無 elite 軸（最高 xwOBACON P60-70）+ Sum 15 偏弱；ERA 4.15/xERA 3.90 小幅 buy-low 但不顯著（luck null）。結構平庸 + 對位最差。樣本 medium |

### 備註
- 2026-06-18 首次評估（recorded 14:06）：1 位過 Rotation gate + Sum ≥15 + true_starter（Sean Burke）。Sum<15 hard floor 排除 1 位（Matthew Liberatore STL @ KC Sum 11 — vs LHP .683 對手偏弱但結構崩 xwOBACON .425 <P25）。owned_by_others 14 位（含 Sonny Gray / Joe Ryan / Bryan Woo / Aaron Nola / Sean Manaea / Trey Yesavage）+ 本隊 1 位（Parker Messick CLE @ MIL）。無 v4 缺數據 / Rotation gate 🚫 排除項。
- TBD 1 場（LAA @ ATH，LAA away SP 未公布；ATH = Gage Jump 別隊），建議 TW 6/18 晚上/6/19 早上 `/stream-sp 2026-06-18 --tbd-only` 補查。
- 用戶決策建議：本日無值得串流候選。Sean Burke 結構平庸（Sum 15 五軸無 elite）+ 客場到 Yankee Stadium 面對 14d .834 全聯盟最熱打線，串流 ROI 差。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-19
- recorded_at: 2026-06-18T14:06:00+08:00
- last_recheck_at: 2026-06-18T22:42:45+08:00

### TBD 場次（待補查）
- TOR @ CHC (both TBD)
- CIN @ NYY (NYY home TBD)
- SF @ MIA (both TBD)
- MIL @ ATL (ATL home TBD)
- SD @ TEX (TEX home TBD)
- LAA @ ATH (LAA away TBD)
- MIN @ AZ (MIN away TBD)
- BAL @ LAD (BAL away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Rhett Lowder | CIN @ NYY | NYY (.860 🔴 / vs RHP .763) | 7% | 16/7 | <P25·<P25·<P25·P60-70·P50-60 | ❌ 不推 | BB/9 4.79 <P25 控球崩 + 對手 NYY 🔴 全聯盟最熱（客場）+ 無 elite 軸；2025 無 prior（傷癒）。對位最差。樣本 medium |
| Erick Fedde | CWS @ DET | DET (.753 🟡 / vs RHP .709) | 2% | 15/12 | <P25·<P25·<P25·P25-40·**P80-90** | ❌ 不推 (deep) | 近 6 場 ERA 5.87 + 0/6 QS（IP 全 <6）+ swingman IP 崩（6/14 僅 2.2IP/58PC）+ floor 高（5/23 SF 8ER + 5/17 CHC 4ER 兩崩短局）。近 3 場 ER 壓制好轉(1ER/12.7IP)但 IP 短 QS 仍 0 + K9 6.0 零貢獻。對手 DET 中等救不了即時命中率。樣本 medium |
| Kyle Freeland | COL vs PIT | PIT (.753 🟡 / vs LHP .690) | 1% | 15/19 | <P25·P25-40·P60-70·P25-40·<P25 | ❌ 不推 (deep) | 近 6 場 ERA 10.05 災難 + 0/6 QS + 4 次崩盤（含對弱打 6/13 ATH 6ER + 6/01 LAA 5ER）+ 主場 Coors 放大飛球 HR。luck ✅撿便宜被 game log 完全推翻（即時命中率崩，xERA 6.02 回歸點仍爛）。對手 PIT vs LHP .690 偏弱也救不了。樣本 medium |

### 備註
- 2026-06-19 首次評估（recorded 14:06）：3 位過 Rotation gate + Sum ≥15 + true_starter（全 true_starter，免 WebSearch）。owned_by_others 14 位（含 Jacob Misiorowski / Roki Sasaki / Seth Lugo / Tanner Bibee / Bryce Miller / Ranger Suarez）+ 本隊 1 位（Tarik Skubal DET vs CWS — 核心）。無 v4 缺數據 / Rotation gate 🚫 / Sum<15 hard floor 排除項。Fedde rotation_gate ⚠️（g14/gs8 swingman 化，未被 🚫 排除但 IP 風險高）。
- TBD 8 場（多到爆），建議 TW 6/18 晚上/6/19 早上 `/stream-sp 2026-06-19 --tbd-only` 補查；TBD 內含 TOR/CHC/SF/MIA/MIL/ATL/SD/TEX/LAA/MIN/AZ/BAL/LAD 等隊，公布後可能有更好候選。
- 排序：**Fedde（⚠️ 條件推）> Lowder ❌ > Freeland ❌**。Fedde 唯一勉強：對偏弱 DET + xwOBACON 菁英 contact 抑制給 floor，但 K 零貢獻 + swingman IP 不保證。Lowder 控球崩 + NYY🔴 客場；Freeland Coors 主場 + 結構崩。
- 用戶決策建議：① 缺 QS/想要對偏弱打線低變異 contact 抑制、且不在意 K + 能接受 <5 IP swingman 風險 → Fedde（唯一可賭）② 缺 K / 要穩 QS / 缺 ERA-WHIP → 三位皆不適合，pass。整體本日無強推，待 8 場 TBD 公布後可能翻盤。
- 2026-06-18 14:14 deep eval（2 位候選）：
  - **Erick Fedde**：⚠️ 條件推 → **❌ 不推 (deep)**。差異訊號 = 近 6 場 ERA 5.87 + 0/6 QS（IP 全 <6，swingman 化 6/14 僅 2.2IP/58PC）+ floor 高（5/23 SF 8ER + 5/17 CHC 4ER 兩崩短局）。pending 條件推靠 xwOBACON P80-90 結構 + 對手偏弱，但 game log 即時命中率不支撐：IP 給不出 QS、K9 6.0 給不出 K、近 6 ERA 5.87 floor 高。近 3 場 ER 壓制好轉(1ER/12.7IP)是唯一利多但 IP 短 QS 仍 0。
  - **Kyle Freeland**：❌ 不推 → **❌ 維持 (deep)**。深評確認 = 近 6 場 ERA 10.05 + 0/6 QS + 4 次崩盤（含對弱打 6/13 ATH 6ER + 6/01 LAA 5ER）+ 主場 Coors 放大飛球。luck ✅撿便宜（ERA 7.98 vs xERA 6.02）被 game log 完全推翻，xERA 6.02 回歸點本身爛。災難級，pass。
- 深評排序：**Fedde > Freeland**（兩位皆 ❌）。Fedde 近 6 ERA 5.87 < Freeland 10.05 + 對手 DET 中等降溫 + 近 3 場 ER 壓制好轉，是「比較不爛」的；但 IP/K/QS 三類別全給不出。Freeland Coors 主場 + 4 崩盤含對弱打，災難。兩位串流 ROI 皆負，本日機會在 8 場 TBD 公布後再找。
- 2026-06-18 22:42 補查：8 場 TBD + 3 候選經 8.5h 零變化，無新公布 starter，僅更新 last_recheck_at。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-20
- recorded_at: 2026-06-18T22:42:45+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- CWS @ DET (CWS away TBD)
- CIN @ NYY (NYY home TBD)
- TOR @ CHC (both TBD)
- SD @ TEX (TEX home TBD)
- WSH @ TB (TB home TBD)
- SF @ MIA (SF away TBD)
- MIL @ ATL (ATL home TBD)
- LAA @ ATH (LAA away TBD)
- BAL @ LAD (BAL away TBD)
- BOS @ SEA (SEA home TBD)
- MIN @ AZ (MIN away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Joey Cantillo | CLE @ HOU | HOU (.734 🟡 / vs LHP .736) | 24% | 21/24 | <P25·P60-70·<P25·P50-60·P50-60 | ⚠️ 條件推 | 純 SP（gate 🟢）+ K 有底（K9 8.4 / Whiff P60-70 / 2025 K9 10.2）+ xERA 4.37 穩無崩；但 BB/9 4.5 <P25 控球差（WHIP 1.49 傷 ratio）+ IP/GS 4.8 偏短 QS 不穩 + Sum 21 無 elite 軸。缺 K 可賭、要 QS/WHIP 不適合。樣本 none（信心高）|

### 備註
- 2026-06-20 首次評估（recorded 22:42）：1 位過 Rotation gate + Sum ≥15 + true_starter（Joey Cantillo）。Opener 排除 1 位（Miles Mikolas WSH @ TB — 機械 opener_verdict=true_starter 誤判，WebSearch 確認連續 6 場 opener 後 bulk reliever：6/14 接 Poulin、6/8 接 Lovelady，g15/gs6 是 performance demotion 非傷癒 ramp，6/20 預期 ~4-5 IP + W 非 pitcher of record 拿不到 + K9 5.4 → 串流 ROI 差）。owned_by_others 12 位（含 Paul Skenes / Freddy Peralta / Yoshinobu Yamamoto / Cristopher Sánchez / Zac Gallen / Spencer Arrighetti）+ 本隊 2 位（Walker Buehler SD @ TEX、J.T. Ginn ATH vs LAA）。無 v4 缺數據 / Rotation gate 🚫 / Sum<15 hard floor 排除項。
- TBD 11 場（多到爆，6/20 是後天，probable 多未公布），建議 TW 6/19 晚上/6/20 早上 `/stream-sp 2026-06-20 --tbd-only` 補查；公布後可能有更好候選。
- 排序：**Cantillo（⚠️ 條件推）唯一候選**。純 SP + K stuff 有底但控球差 + 對手中等，偏弱。
- 用戶決策建議：① 缺 K + 能接受控球差/WHIP 風險 + 對手中等 → Cantillo（唯一可賭，K9 8.4 + 純先發穩定）② 要穩 QS（IP 短）/ 缺 ERA-WHIP（BB 多）→ 不適合，pass。整體本日無強推，待 11 場 TBD 公布後可能翻盤。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
