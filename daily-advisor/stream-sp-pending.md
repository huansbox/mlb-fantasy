# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-29
- recorded_at: 2026-05-28T12:52:00+08:00
- last_recheck_at: 2026-05-29T07:05:00+08:00

### TBD 場次（待補查）
- TOR @ BAL (TOR away TBD)
- BOS @ CLE (BOS away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Coleman Crow | MIL away | HOU (.674) | 1% | 22/— | <P25·<P25·**>P90**·—·**>P90** | ✅ 已 claim（本隊）| 2026-05-29 補查：已進本隊（scan owned_by_me）。原 ⚠️ 條件推 candidate 已撿下，今晚 vs HOU 先發。 |
| Chris Paddack | CIN home | ATL (.65) | 1% | 20/17 | <P25·P25-40·P40-50·P40-50·P50-60 | ❌ 不推 (deep) | 維持 pending verdict（差異訊號更明確）。近 6 場 ERA **7.27** + QS **0/6** deep crisis + 2 次 collapse（STL 5ER + PHI 7ER）→ floor risk hard rule trigger。ATL 7d .515 是 cold noise（hard rule 強制 14d 為錨）→ 回歸後 30d .700 / vs RHP .765 屬「中-強」級；4/15 對 ATL 客場已是 4.2IP/2ER 短局。luck_tag ✅ 撿便宜（xERA 4.33）已破功 — 結構面跟不上實際表現。 |
| Slade Cecconi | CLE home | BOS (.777) | 5% | 19/27 | P25-40·<P25·P40-50·**P60-70**·P25-40 | ❌ 不推（已被別隊認領）| 2026-05-29 補查：scan owned_by_others 出現，已被聯盟撿走。原 ❌ 不推結論不變，現已非 FA。 |
| Kyle Leahy | STL home | CHC (.656) | 7% | 15/20 | <P25·P40-50·<P25·**P60-70**·<P25 | ❌ 不推 | luck_tag **⚠️ 賣高運氣** (ERA 4.44 / xERA 6.34 差 -1.90) — 真實結構 xERA 6.34 deep crisis；2026 5 軸 3 個 <P25 + 2025 IP/GS 3.0 顯示 reliever 出身；雖對手 .656 🟢 但結構崩潰風險過高。 |

### 備註
- 2026-05-28 12:52 首次評估：4 位通過 Rotation gate + Sum ≥15 + true_starter（Coleman Crow WebSearch 確認真先發補 Henderson IL 缺）。已過濾：Andrew Alvarez（Rotation gate 🚫 G=4/GS=0 pure reliever）+ Lucas Giolito（Sum 13 hard floor，GS=2 樣本小 + 雙年 11）+ Erick Fedde（Sum 12 hard floor，5 軸 4 個 <P25 + 雙年低）+ 別隊 12 位（含 Carlos Rodón / Zac Gallen / George Kirby / Logan Webb / Zack Wheeler）+ 本隊 2 位（Kolek @ TEX / Severino home vs NYY）。
- TBD 9 場（多為 away SP TBD），建議 TW 5/29 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- **Coleman Crow 唯一條件推但樣本零**：MLB.com 報補 Logan Henderson IL 缺，預期 ~5 IP。雙 elite 軸（BB/9 + xwOBACON）但 BBE=0 + 2025 無 MLB 數據 → 結構訊號信心低。建議：1) 是否 ERA/WHIP 已輸定 → 撿；有翻盤空間 → pass，2) `/stream-sp-deep Coleman Crow` 看 MIL 兩場 game log + HOU 對 RHP rookie 歷史。
- 2026-05-28 13:05 deep eval（3 位候選：Bassitt 跨日 5/28 + Crow 5/29 + Paddack 5/29）：
  - **Bassitt (ET 5/28，不在本 pending 範圍)**：⚠️ 偏推 → ❌ 不推 (deep)。差異訊號 = 近 6 場 ERA 5.17 + **對弱打 4 次崩盤**（PIT 6ER / KC 5ER / MIA 4ER / WSH 4ER）+ floor risk hard rule trigger。Pending 5-slot Sum 25 28 prior 撐底反映不到近場結構崩
  - **Crow**：⚠️ 條件推 → ⚠️ 條件推 (deep)。差異訊號 = 近 2 場 ERA 2.61 無 collapse + HOU 14d/30d 持平 .674（hard rule lock 14d 為錨，7d .803 是 spike noise）；但樣本警告 + 雙年無 prior 維持條件推（不升 ✅）
  - **Paddack**：❌ 不推 → ❌ 不推 (deep)。差異訊號 = 近 6 場 ERA **7.27** + QS 0/6 deep crisis + 2 次 collapse + ATL 7d .515 是 cold noise（hard rule lock 14d 為錨）→ 回歸後對手仍中-強級；維持不推結論成立
- 排序：**Crow > Bassitt >> Paddack**。Crow 對 ERA/WHIP 翻盤無風險（賭 BB/9 elite 複製）；Bassitt 雖 Sum 25 28 撐但近 6 場崩盤太頻繁，QS/W 期望都低於 30%；Paddack 結構 + 近況 + 對手 + 運氣四方向全壞
- 用戶決策建議：① ERA/WHIP 有翻盤空間 → 只 Crow ② ERA/WHIP 已輸定 + 堆 IP/W/K → 也只 Crow（Bassitt QS 30% 不值得） ③ FAAB 預算緊 → Crow $0 FA 撿即可
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-30
- recorded_at: 2026-05-28T13:22:08+08:00
- last_recheck_at: 2026-05-29T07:20:00+08:00

### TBD 場次（待補查）
- SD @ WSH (WSH home TBD)
- SF @ COL (COL home TBD)
- PHI @ LAD (PHI away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Roki Sasaki | LAD home | PHI (.635) | 39% | 17/15 | <P25·**P80-90**·<P25·P40-50·<P25 | ⚠️ 條件推 (deep) | 維持 pending verdict。深評確認：近 4 場 3.52 ERA（5/02 inflection 後）+ 2 QS + 5/17 對 LAA 7IP/1ER/8K dominant fingerprint；PHI vs RHP .685 弱-中 + 14d/7d 一致 .635/.628 冷期（30d→7d Δ -.075 非 spike）；floor risk 低（無對弱打崩盤）。短局型 IP/GS <P25 限 QS 機率 ~35-40%，故不升 ✅。 |
| 🆕 Kumar Rocker | TEX home | KC (.595) | 10% | 21/20 | <P25·P40-50·<P25·**P80-90**·P40-50 | ⚠️ 條件推 (deep) | 維持 pending verdict。深評確認：對位最甜 — KC 14d .595 / 7d .616 一致冷期 + vs RHP .691 弱-中 ∩ Rocker「吃弱打」pattern（對弱線 PIT/ATH/COL **3/4 QS**，對中線 0/4）；GB% P80-90 ∩ KC 低 power 抑 ER；無 luck 扭曲。風險：IP/GS 4.7 短局限 QS ~50-55% + 近 6 場 2 次崩盤（DET 2IP/5ER、HOU 4ER，但都非對弱打 → hard rule 未觸發，floor 中-高下修）+ BB/9 <P25。 |
| Brandon Sproat | MIL away | HOU (.684) | 6% | 16/22 | <P25·P60-70·<P25·P50-60·<P25 | ❌ 不推 (deep) | 反轉 pending verdict ⚠️ → ❌。差異訊號 = 近 6 場 **0/6 QS** + 5.20 ERA + 4 連場 IP<5 fragile；BB/9 5.44 失控（近 4 場 16BB/18IP）+ HOU 7d .834/R/G 6.2 hot lineup（hard rule lock 14d 為錨 .684 中，但 vs RHP .722 季線回歸方向不利）；客場 + LAD 後手感差（5/24 4IP/3ER/4BB）。luck_tag ✅ 撿便宜唯一加分但結構 P<25 撐不起。 |
| Brady Singer | CIN home | ATL (.653) | 13% | 16/19 | <P25·P25-40·**P70-80**·P25-40·<P25 | ❌ 不推 (deep) | 維持 pending verdict。深評強化：floor risk **hard rule trigger 高**（近 6 場對弱打 PIT/WSH/CLE 3 次崩盤/準崩 + 近 6 場 ERA **6.67** ≥4.50 OR 雙條件全 trigger）；ATL 14d .653 cool 看似友善但 vs RHP .765 季線 1342 PA 強底盤 + 7d .489 是 cold noise（hard rule lock 14d）→ 回歸窗口往上；5/17 對 CLE 弱打 4IP/5ER/3HR fingerprint。 |

### 備註
- 2026-05-28 13:22 首次評估：3 位通過 Rotation gate + Sum ≥15 + true_starter（無 opener 待確認）。已過濾：Brandon Young (BAL home vs TOR, Sum 13 hard floor — 5 軸 4 個 <P25 雙年低 + 雖 xwOBACON P80-90 elite 但 luck_tag ⚠️ 賣高運氣 ERA 3.47/xERA 4.28 真實結構接近 4.28) + 別隊 11 位（含 Michael King / Bryan Woo / Seth Lugo / Trey Yesavage / Drew Rasmussen / Ryan Weathers）+ 本隊 3 位（Messick home vs BOS / Pallante home vs CHC / Ginn home vs NYY）。
- TBD 11 場（多為 5/30 才公布的 starter），建議 TW 5/29 晚上或 5/30 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- 2026-05-28 13:28 deep eval（3 位候選 Sasaki + Sproat + Singer）：
  - **Sasaki**：⚠️ 條件推 → ⚠️ 維持 (deep)。差異訊號 = 近 4 場 3.52 ERA inflection（5/02 後）+ 5/17 LAA 7IP/1ER/8K fingerprint + PHI vs RHP .685 主錨弱-中 + floor risk 低；短局型 IP/GS <P25 限 QS ~35-40% 不升 ✅
  - **Sproat**：⚠️ 條件推 → **❌ 不推 (deep)**。差異訊號 = 近 6 場 **0/6 QS** + 5.20 ERA + 4 連場 IP<5 fragile + BB/9 5.44 失控 + HOU 7d .834/R/G 6.2 hot lineup（hard rule lock 14d .684 但 vs RHP .722 季線回歸方向不利）；luck_tag 撿便宜結構 P<25 撐不起
  - **Singer**：❌ 不推 → ❌ 維持 (deep)。差異訊號強化 = floor risk **hard rule trigger 高**（近 6 場對弱打 3 次崩盤/準崩 + ERA 6.67 OR 雙條件全 trigger）+ ATL vs RHP .765 季線強底盤 + 5/17 對 CLE 弱打 4IP/5ER/3HR fingerprint
- 排序：**Sasaki > Sproat >> Singer**。Sasaki 對 ERA/WHIP 翻盤較好（floor 低 + 主場 + K elite）；Sproat 短局 + 0 QS 串流 ROI 差；Singer 結構+表現+對手+floor 四方向全壞
- 用戶決策建議：① ERA/WHIP 有翻盤空間 → 只 Sasaki ② ERA/WHIP 已輸定 + 堆 IP/W/K → 也只 Sasaki（Sproat 0/6 QS + 4.61 IP/GS 期望差於 Sasaki）③ FAAB 預算緊 → Sasaki $0 FA 撿即可 ④ Crow（5/29）已 claim 則 5/30 Sasaki 順位串疊
- 2026-05-29 07:20 deep eval（1 位候選 Rocker，補查新評帶出）：
  - **Rocker**：⚠️ 條件推 → ⚠️ 維持 (deep)。深評確認訊號 = 對位最甜（KC 14d .595/7d .616 一致冷期 ∩ Rocker「吃弱打」pattern 對弱線 3/4 QS）+ GB% P80-90 抑 ER；floor 中-高（近 6 場 2 崩盤但非對弱打，hard rule 未觸發）+ 短局 IP/GS 4.7 限 QS ~50-55% → 不升 ✅
  - 排序（5/30 全候選）：**Rocker ≈ Sasaki >> Sproat >> Singer**。Rocker 對手更弱（KC .595 < PHI .635）+ QS 期望高 + 雙年 Sum 穩 → ERA/WHIP/W/IP floor 較佳；Sasaki K elite（Whiff P80-90）→ 追 K 選他。兩者互補 $0 FA 主場
- 用戶決策建議（含 Rocker）：① 缺 ERA/WHIP/W/IP → Rocker（對位最甜）② 缺 K（contested）→ Sasaki ③ 要單撿綜合期望略穩 → Rocker
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
