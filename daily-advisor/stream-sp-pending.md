# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-20
- recorded_at: 2026-06-18T22:42:45+08:00
- last_recheck_at: 2026-06-20T14:33:45+08:00

### TBD 場次（待補查）
- CWS @ DET (CWS away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| 🆕 Trevor McDonald | SF @ MIA | MIA (.786 🔴 / vs RHP .708) | 8% | 30/46 | P25-40·P50-60·P40-50·**>P90**·P50-60 | ⚠️ 條件推 | GB% 57.7% >P90 極端滾地（HR/長打抑制 + 雙殺 + 省球）給 floor + 對 MIA 季線 vs RHP .708 偏弱有利；但對手 14d .786 🔴 熱 + IP/GS 5.33 偏短 QS 不穩 + Whiff P50-60 K 中等 + 2025 僅 15IP 小樣本(⚠️賣高)無可靠 prior。缺 ERA/WHIP/要低變異 GB 壓制可賭、要穩 QS/高 K 不適合。樣本 medium |

### 備註
- 2026-06-20 首次評估（recorded 22:42）：1 位過 Rotation gate + Sum ≥15 + true_starter（Joey Cantillo）。Opener 排除 1 位（Miles Mikolas WSH @ TB — 機械 opener_verdict=true_starter 誤判，WebSearch 確認連續 6 場 opener 後 bulk reliever：6/14 接 Poulin、6/8 接 Lovelady，g15/gs6 是 performance demotion 非傷癒 ramp，6/20 預期 ~4-5 IP + W 非 pitcher of record 拿不到 + K9 5.4 → 串流 ROI 差）。owned_by_others 12 位（含 Paul Skenes / Freddy Peralta / Yoshinobu Yamamoto / Cristopher Sánchez / Zac Gallen / Spencer Arrighetti）+ 本隊 2 位（Walker Buehler SD @ TEX、J.T. Ginn ATH vs LAA）。無 v4 缺數據 / Rotation gate 🚫 / Sum<15 hard floor 排除項。
- TBD 11 場（多到爆，6/20 是後天，probable 多未公布），建議 TW 6/19 晚上/6/20 早上 `/stream-sp 2026-06-20 --tbd-only` 補查；公布後可能有更好候選。
- 排序：**Cantillo（⚠️ 條件推）唯一候選**。純 SP + K stuff 有底但控球差 + 對手中等，偏弱。
- 用戶決策建議：① 缺 K + 能接受控球差/WHIP 風險 + 對手中等 → Cantillo（唯一可賭，K9 8.4 + 純先發穩定）② 要穩 QS（IP 短）/ 缺 ERA-WHIP（BB 多）→ 不適合，pass。整體本日無強推，待 11 場 TBD 公布後可能翻盤。
- 2026-06-20 14:33 補查（當天）：11→1 場 TBD（剩 CWS@DET）。**舊評 Joey Cantillo 已被別隊認領（進 owned_by_others），移出候選表。** 新公布 starter 多數被聯盟搶走（owned_by_others 20 位含 Skenes/Peralta/Sánchez/Yamamoto/Gallen/Cavalli）+ 本隊 3 位（Buehler SD@TEX、Sale ATL vs MIL、J.T. Ginn ATH vs LAA）。新評 1 位真先發 FA：🆕 Trevor McDonald（SF@MIA，⚠️ 條件推，GB >P90 對 MIA vs RHP 偏弱）。Sum<15 hard floor 排除 2 位（Patrick Corbin Sum11 / Colin Rea Sum12，皆對手 🔴）+ Rotation gate 🚫 排除 1 位（Ian Seymour g28/gs2 pure RP）。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-21
- recorded_at: 2026-06-20T14:33:45+08:00
- last_recheck_at: 2026-06-20T15:05:00+08:00

### TBD 場次（待補查）
- SD @ TEX (SD away TBD)
- MIN @ AZ (both TBD)
- LAA @ ATH (LAA away TBD)
- NYM @ PHI (NYM away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Keider Montero | DET vs CWS | CWS (.706 🟢 / vs RHP .723) | 8% | 27/11 | P50-60·<P25·**P80-90**·<P25·**>P90** | ✅ 推 | 對弱打 CWS + 控球精（BB/9 2.08 P80-90 / WHIP 1.02）+ contact 壓制菁英（xwOBACON .335 >P90）+ IP/GS 5.56 夠 → QS 高 + ratio 友善（ERA 3.67≈xERA 3.69 實打實）。唯一缺 K（Whiff <P25 / K9 6.1）。要 QS/ERA/WHIP 最佳、要 K 不適合。樣本 none（信心高）|
| Slade Cecconi | CLE @ HOU | HOU (.718 🟢 / vs RHP .734) | 7% | 26/28 | P25-40·P25-40·P50-60·P70-80·P50-60 | ✅ 推 (deep) | deep：近 6 場 ERA 3.24（vs 整季 4.60）+ floor 低（近 6 場 0 崩盤）+ 對強隊(PHI/BOS/NYY×2)維持壓制 → 對位 HOU 中性(14d .718)降一階。4/20 對 HOU 黑歷史(5IP 6ER)已過時。求穩 QS + floor 最穩首選，K 略多於 Montero。QS~50%/ER 2-3。樣本 none |
| Kai-Wei Teng | HOU vs CLE | CLE (.620 🟢 / vs RHP .680) | 8% | 22/25 | <P25·**P70-80**·<P25·P60-70·P40-50 | ❌ 不推 (deep) | deep：近 3 場全爆(6/04 PIT 4ER/6/09 LAA 5ER/6/15 DET 5ER 3HR) + 近 6 ERA 5.40 + HR 病惡化 + IP 逐場縮短(5→4→3.1) → 對 CLE 極弱也救不了即時崩盤。唯一利多 K stuff(K9 9.6) → 純缺 K 能吞 ER/IP/WHIP 風險者可視高變異賭。QS~20%。樣本 medium |
| Robert Gasser | MIL @ ATL | ATL (.617 🟢 / vs LHP .733) | 2% | 20/18 | <P25·P60-70·<P25·<P25·**>P90** | ❌ 不推 (deep) | deep：2 次崩盤皆伴 HR(5/23 LAD 4ER 1HR/6/09 ATH 6ER 4HR) + GB <P25 飛球型 HR 病對「強隊 slump 回歸」的 ATL(vs LHP .733 中性非弱) + 整季 0 QS(IP 全<6) + 僅 24IP。xwOBACON>P90/buy-low 是 5-slot 利多但 HR 病是真結構風險。高變異者可賭近 2 場好轉。QS~25%。樣本 medium |

### 備註
- 2026-06-21 首次評估（recorded 14:33）：4 位過 Rotation gate + Sum ≥15 + true_starter 進主表（Montero/Cecconi/Teng/Gasser）。Opener 排除 1 位（Andrew Alvarez WSH@TB — WebSearch 確認 piggyback/bulk，2026 從未滿 5 IP，6/15 僅 4IP/58PC 硬上限，QS 不可能、IP ≤4）。Sum<15 hard floor 排除 1 位（Ryan Gusto MIA vs SF Sum13，ERA 7.24）+ Rotation gate 🚫 排除 1 位（Jack Perkins ATH vs LAA g20/gs3 pure RP）。owned_by_others 17 位（含 Gerrit Cole / Logan Webb / Dylan Cease / Shota Imanaga / MacKenzie Gore / Zack Wheeler / Logan Gilbert / Chase Burns）+ 本隊 1 位（Stephen Kolek KC vs STL）。
- TBD 4 場（SD@TEX / MIN@AZ / LAA@ATH / NYM@PHI），建議 TW 6/21 早上 `/stream-sp 2026-06-21 --tbd-only` 補查；公布後可能有更好候選。
- 排序：**Montero ✅ > Cecconi ⚠️ > Teng ⚠️ > Gasser ⚠️**。Montero 唯一 Sum≥25 + 2 elite 軸 + 對弱打 + 控球精，QS/ratio 最佳（缺 K）。Cecconi 穩定無亮點。Teng K play 但控球/IP 風險。Gasser xwOBACON+buy-low 但樣本小變異大。
- 用戶決策建議：① 要 QS / ERA / WHIP → Montero（首選，控球精 + IP 夠 + 對弱打）② 純缺 K → Teng（K9 9.6 + 對手最弱，但 WHIP 風險）③ 求穩低變異 → Cecconi ④ 都不缺 → pass，待 4 場 TBD 公布。
- 2026-06-20 15:05 deep eval（4 位候選）：
  - **Keider Montero**：✅ 推 → **✅ 維持 (deep)**。深評確認 = 近 6 ERA 3.68 + 5/31 對同隊 CWS 6IP 0ER fingerprint + 控球精 WHIP 1.02。風險 floor hint 高(近 6 場 2 次 4ER LAA/SEA) + 6/16 HOU 1.1IP/30PC 異常短局(疑雨延，claim 前確認健康) + 缺 K(K9 6.1)。
  - **Slade Cecconi**：⚠️ 條件推 → **✅ 推 (deep)**。差異訊號 = 近 6 ERA 3.24(vs 整季 4.60) + floor 低(近 6 場 0 崩盤) + 對強隊(PHI/BOS/NYY×2)維持壓制 → 對位 HOU 中性降一階。pending「穩定無 elite」反映不到近況 inflection(5/18 後)。
  - **Kai-Wei Teng**：⚠️ 條件推 → **❌ 不推 (deep)**。差異訊號 = 近 3 場全爆(6/04 4ER/6/09 5ER/6/15 5ER 3HR) + 近 6 ERA 5.40 + HR 病 + IP 縮(5→3.1)。對 CLE 極弱救不了即時崩盤。純缺 K 高變異賭例外。
  - **Robert Gasser**：⚠️ 條件推 → **❌ 不推 (deep)**。差異訊號 = 2 次崩盤伴 HR(5/23 1HR/6/09 4HR) + GB<P25 飛球 HR 病對可能回歸的 ATL(vs LHP .733 中性) + 整季 0 QS + 僅 24IP。xwOBACON>P90/buy-low 利多被 HR 病結構風險抵消。
- deep 排序：**Cecconi ≈ Montero（並列 ✅ 首選）> Teng > Gasser**。SP 自身近況 + floor 權重 >> 對手冷度(CLE/ATL 冰冷但有回歸風險)。Cecconi floor 低 + 對強隊驗證；Montero 對 CWS 最弱 + 控球精 ratio。Teng/Gasser 是「賭對手救自己」高變異局。決策分流：缺 ERA/WHIP+最弱對手 → Montero；缺 QS+floor 穩 → Cecconi；純缺 K 吞變異 → Teng；pass → Gasser。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
