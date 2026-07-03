# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-07-03
- recorded_at: 2026-07-02T10:18:14+08:00
- last_recheck_at: 2026-07-03T10:10:00+08:00

### TBD 場次（待補查）
- SF @ COL (SF away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Jose Cabrera | AZ home | MIL (.737 🟡 / vs RHP .760) | 1% | 33/— | <P25·**P70-80**·**>P90**·P40-50·**P80-90** | ❌ 不推 (deep) | deep：MIL 回歸後中強偏熱（30d .802/26 場大樣本 + 7d .841 + R/G 5.4，scan 的 14d .739 🟡 反而是唯一低窗）+ QS 天花板被新秀球數上限鎖死（兩場先發都正好 5.0 IP，PC 62→80，需 ~90 球內投完 6 局）+ 唯一客場先發即爆（6/27 @TB 4ER/2HR）。Sum 33 結構利多僅 10 IP 樣本，game log 1 gem 1 爆無獨立支撐。純缺 K 且 ERA/WHIP 已輸定者可零成本小賭 5IP+4K；正常情境 pass。樣本 medium |
| Mike Paredes | MIN away | NYY (.542 🟢 / vs RHP .731) | 1% | 16/— | <P25·<P25·P25-40·P40-50·P50-60 | ❌ 不推 | 5-slot 無 elite 軸 + K9 4.62 幾無 K 價值 + ⚠️ 賣高運氣（ERA 4.26 < xERA 5.41）+ IP/GS 4.5 QS 難。唯一利多 = NYY 14d .542 🟢 聯盟級冰冷。純賭對手冷的 ratio 一場，無 K/QS upside，不值 1 次異動。樣本 medium。0703 補查：已被別隊認領 |
| Brady Singer | CIN home | BAL (.688 🟢 / vs RHP .734) | 19% | 19/21 | <P25·P50-60·P50-60·P40-50·<P25 | ⚠️ 條件推 (deep) | deep：近 6 場 ERA 3.45 + BAL 三窗連降（.713→.688→.623、K% 27%）+ 近 5 場場均 ~5.8K → K+QS 賭注成立。風險 = 全季 5 崩盤 4 次對弱隊（含 6/28 @PIT 4.1IP/5ER）+ HR 病（xwOBACON <P25）+ GABP。QS ~45-50% |
| Ryan Feltner | COL home | SF (.691 🟢 / vs RHP .741) | 2% | 18/25 | <P25·P40-50·P25-40·P50-60·P25-40 | ⚠️ 條件推 (deep) | deep：IL 復歸後 6 場 4QS + ERA 3.27（Coors 3QS）+ SF 14d .691 冷（R/G 3.25）→ QS/IP/ratio 賭注成立。風險 = 零 K（近 6 場 33IP 僅 18K）+ Coors variance（6/11 CHC 6ER）+ SF 30d .777 回升 risk。QS ~50% |
| Christian Scott | NYM away | ATL (.547 🟢 / vs RHP .721) | 14% | 11/— | <P25·P60-70·<P25·<P25·<P25 | ⚠️ 條件推 (deep) | deep（scan Sum11 hard floor 排除，用戶點名翻案）：ATL 三窗塌陷 .599→.544→.503（R/G 3.0，24 場大樣本）+ 近 6 場 ERA 3.07 + K9 10.1 → ER/K/ratio 賭注成立。天花板 = **10 場先發 0 QS、最高 5.2 IP**（leash ~90 球，QS ~10-15%）+ HR 病（GB/xwOBACON <P25，6/11 STL 3HR）+ ⚠️ 賣高運氣。純 K+ratio 用 |

### 備註
- 2026-07-03 首次評估（recorded TW 10:18，ET 7/3 為後天，9 場 TBD 多未公布）：2 位過 Rotation gate + Sum ≥15 + true_starter 進主表（Cabrera ⚠️ / Paredes ❌）。Sum<15 hard floor 排除 1 位（Christian Scott NYM @ ATL Sum11 — K9 10.6 名氣款但 BB/9 4.2 + xwOBACON <P25 + ⚠️ 賣高運氣 ERA 3.20 < xERA 4.61）。Rotation gate 🚫 排除 1 位（Jack Perkins ATH vs MIA g22/gs5 pure RP，6/21 亦排除過同人）。owned_by_others 11 位（含 Gerrit Cole / Dylan Cease / Ohtani / Michael King / Gavin Williams / Arrighetti）+ 本隊 1 位（Andre Pallante STL @ CHC）。
- Cabrera 注意：scan（statsapi probable）已列 AZ 7/3 先發 = Cabrera，但 WebSearch agent 看到部分站點仍標 D-backs TBD → **claim 前再確認官方公布**（新秀輪值填補位，Nelson/Soroka 傷癒回歸會擠掉他）。
- 排序：**Cabrera（⚠️ 條件推）唯一可賭**。Paredes 純賭 NYY 冰冷無結構支撐。9 場 TBD 公布後可能有更好候選，建議 TW 7/3 早上 `/stream-sp 2026-07-03 --tbd-only` 補查。
- 2026-07-02 10:21 deep eval（1 位候選）：
  - **Jose Cabrera**：⚠️ 條件推 → **❌ 不推 (deep) 降級**。差異訊號 = ① 對手重評：MIL 30d .802（26 場大樣本）+ 7d .841 + R/G 5.4，scan 錨定的 14d .739 是三窗中唯一低點 → 回歸判斷中強偏熱（.760-.790），非 🟡 中性；② QS 結構天花板：兩場 MLB 先發都被新秀 leash 鎖在正好 5.0 IP（PC 62→80），QS 需 ~90 球內吃完 6 局 → QS% 僅 ~15-20%，pending「QS 邊緣」高估；③ floor：唯一客場先發 6/27 @TB 即 4ER/2HR。sample medium 下結構訊號需 game log 獨立支撐，但 1 gem 1 爆撐不起 ⚠️。
- deep 排序：**本日（7/3）無可推候選**（Cabrera ❌ deep / Paredes ❌ scan）。等 9 場 TBD 公布後補查再議。
- 2026-07-03 09:52 補查：9 場 TBD 公布 8 場，剩 SF @ COL 的 SF 端。新評 2 位進主表（🆕 Singer ❌ / 🆕 Feltner ❌），Christian Scott 再次 Sum11 hard floor 排除。Paredes 已被別隊認領（lost_to_others）。Cabrera 官方 statsapi 已確認 7/3 先發（前次「部分站點標 TBD」疑慮解除），deep ❌ 維持。註：前次表格「隊」欄寫 `AZ vs MIL` 格式不符 pending_parser（要求 `AZ home`），pending_diff 曾全空，本次已修正格式。
- 2026-07-03 10:00 deep eval（2 位候選）：
  - **Brady Singer**：❌ 不推 → **⚠️ 條件推 升級**。差異訊號 = ① 近 6 場 ERA 3.45 / QS 2/6 / IP/GS 5.22（scan 的 IP/GS 4.83 + xwOBACON <P25 是全季值，近況已回穩，6/22 MIL 7IP/0ER/7K）；② BAL 三窗連降 30d .713 → 14d .688 → 7d .623 + K% 27%（Singer 近 5 場 29K/26.3IP，K 上行）；③ 對強隊反而穩（ATL 3ER / NYM 1ER / SD 2ER）。抵消訊號 = 全季 5 次崩盤 4 次對弱隊（MIA/PIT/CLE/PIT，最近 6/28 @PIT 4.1IP/5ER 2HR）— 對弱隊 BAL 是雙面刃 + GABP HR park。
  - **Ryan Feltner**：❌ 不推 → **⚠️ 條件推 升級**。差異訊號 = ① 5/30 IL 復歸為明確 inflection point，復歸後 6 場 4QS / ERA 3.27 / IP/GS 5.5，其中 3 QS 在 Coors（scan 的 Coors 排除被 game log 反證）；② 對中-強隊 2/2 QS（BOS 2ER / MIN 1ER）；③ SF 14d .691 + R/G 3.25 冷。抵消訊號 = 零 K 價值（近 6 場 K9 4.9，6/28 6IP 0K）+ SF 30d .777 回升 risk + 6/11 CHC 6ER。
- deep 排序：**Singer > Feltner**。Singer 給 K+QS 雙賭（BAL 更冷 + 高 K%、非 Coors）；Feltner QS 率較高但零 K，只適合 ERA/WHIP 已輸定或純缺 QS/IP 情境。兩位皆 ⚠️ — 7/3 從「無可推」改為「有條件可賭」。
- 2026-07-03 10:10 deep eval（1 位，用戶點名 hard-floor 翻案檢驗）：
  - **Christian Scott**：scan Sum11 hard floor 排除 → **⚠️ 條件推 升級（限定用途）**。差異訊號 = ① ATL 崩盤級冰冷（30d .599 → 14d .544 → 7d .503、R/G 3.0，24 場大樣本非噪音）— 全表最弱對手，遠低於季 vs RHP .721；② 近 6 場 ERA 3.07 + K9 10.1（兩場 8K），結構弱訊號近 6 場僅 6/11 STL 3HR 一次兌現；③ 6/11→6/27 有 16 天 gap（跳過輪值），6/27 復出 4.1IP/2ER/6K 正常。天花板 = 10 場先發 0 QS、單場最高 5.2 IP（NYM leash ~90 球）→ QS ~10-15%、IP 貢獻低。Scan 的 Sum11 hard floor 判「不值得串」對 QS/IP 視角正確，但 K/ratio 視角漏掉對手極端情境。
- deep 排序更新（7/3 三位 ⚠️）：**Singer ≈ Scott > Feltner**，按類別需求選 — Singer 最均衡（K + QS 機會 + W）；Scott ER/K/ratio 上限最高但 QS≈0、IP 低；Feltner 純 QS/IP。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-07-04
- recorded_at: 2026-07-03T09:55:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- SF @ COL (SF away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Griffin Canning | SD away | LAD (.800 🔴 / vs RHP .807) | 1% | 18/18 | <P25·P50-60·<P25·P60-70·P25-40 | ❌ 不推 | @ LAD 🔴 全表最硬對手 + BB/9 5.36 <P25 爆局風險；✅ 撿便宜運氣（ERA 7.09 / xERA 5.04）不足以抵 |

### 備註
- 2026-07-03 首次評估：僅 1 位過 filter（Canning ❌）。Sum<15 hard floor 排除 3 位（Sam Aldegheri 11 / Aaron Civale 11 / Merrill Kelly 14 — Kelly 36% owned 名氣款但 2026 xERA 7.55 崩盤 + ⚠️ 賣高運氣）。Rotation gate 🚫 排除 1 位（Sean Manaea NYM @ ATL g18/gs4 — gate 判 long-relief；ATL 14d .543 聯盟最冷，若官方 confirm 他拉長局數可手動重看）。**本日無值得串流候選**。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-07-05
- recorded_at: 2026-07-03T09:55:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- TB @ HOU (TB away TBD)
- SF @ COL (SF away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Javier Assad | CHC home | STL (.664 🟢 / vs RHP .716) | 11% | 25/21 | P40-50·<P25·P70-80·P50-60·P40-50 | ⚠️ 條件推 | WHIP 1.12 + BB/9 P70-80 控球型 + STL 冷 + 主場；缺 K（Whiff 13.9% <P25 / K9 5.4）→ 只補 IP/QS/ratio；g13/gs6 swing 角色留意官方 confirm。樣本 medium |
| Miles Mikolas | WSH home | PIT (.874 🔴 / vs RHP .785) | 1% | 25/19 | <P25·<P25·>P90·P60-70·P50-60 | ❌ 不推 | Sum 25 靠 BB/9 >P90 單軸；PIT 14d .874 全表最燙 + K9 5.0 無 K + g18/gs7 IP/GS 4.57 QS 難 |
| Luinder Avila | KC home | PHI (.784 🔴 / vs RHP .724) | 3% | 22/— | <P25·P50-60·<P25·P50-60·P70-80 | ❌ 不推 | BB/9 5.79 <P25 爆局風險 + PHI 🔴 + IP/GS 4.05 QS 幾無可能 |
| Ryan Johnson | LAA home | BOS (.694 🟢 / vs RHP .676) | 2% | 19/— | <P25·P40-50·P25-40·<P25·P80-90 | ⚠️ 條件推 | WebSearch 確認真先發（G-Rod IL 缺輪值位，近 3 場常規先發，6/23 vs BAL 6IP 8K 0R、6/29 5IP 1ER）+ xwOBACON P80-90 + ✅ 撿便宜運氣（ERA 7.40 / xERA 4.29）+ BOS 🟢；⚠️ G-Rod 傷癒啟用在即，7/5 先發僅 tentatively projected — claim 前必確認官方 probable |
| Tanner Gordon | COL home | SF (.675 🟢 / vs RHP .741) | — | 19/13 | <P25·P50-60·>P90·<P25·<P25 | ❌ 不推 | Coors 主場 + xwOBACON <P25 被打爆 + ERA 6.69；BB/9 >P90 唯一亮點 |
| Aaron Nola | PHI away | KC (.634 🟢 / vs RHP .708) | 47% | 16/25 | <P25·P50-60·P40-50·P25-40·<P25 | ❌ 不推 | 名氣款：雙年 ERA 6+ + xwOBACON <P25 結構性被打爆；KC 🟢 + K9 9.2 唯一誘因，✅ 撿便宜運氣不足以翻 |
| Brandon Sproat | MIL away | AZ (.684 🟢 / vs RHP .665) | 21% | 15/21 | <P25·P60-70·<P25·P40-50·<P25 | ❌ 不推 | Sum 15 貼 hard floor + BB/9 4.08 + xwOBACON <P25；K9 9.6 有 K 但 WHIP / 爆局風險高 |

### 備註
- 2026-07-03 首次評估：7 位過 filter 進主表（Assad ⚠️ / Johnson ⚠️ / 其餘 ❌）。Sum<15 hard floor 排除 3 位（Erick Fedde 13 / Matthew Liberatore 9 / JP Sears 9 — Sears 為 small_sample 但先被 hard floor 淘汰，省 WebSearch）。Rotation gate 🚫 排除 1 位（Cal Quantrill TEX vs DET g17/gs2 IP/GS 3.0）。
- **排序：Johnson（席位確認前提下最佳）> Assad（安全但零 K 上限）**。Johnson 的先發需在 TW 7/4-7/5 確認 LAA 官方 probable（G-Rod activation 新聞）；若被擠掉則 Assad 是唯一可用。TB @ HOU 的 TB 端 + SF 端仍 TBD，建議 TW 7/4 `/stream-sp 2026-07-05 --tbd-only` 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
