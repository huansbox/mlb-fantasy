# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-15
- recorded_at: 2026-06-15T12:26:12+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- SD @ STL (SD away TBD)
- MIN @ TEX (MIN away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Ryan Gusto | MIA @ PHI | PHI (.726 🟡 / vs RHP .685) | — | 21/21 | <P25·<P25·**P80-90**·**P80-90**·<P25 | ⚠️ 條件推 | floor 型：BB/9 2.0 + GB% 51.7 雙菁英控球壓 HR + 對手 PHI vs RHP .685 偏弱；但 Whiff <P25 K 少 + xwOBACON .397 <P25 on-contact 被打慘 + WebSearch 確認 true_starter 但仍 ramp-up（6/11 季高 66 球/4IP）預期 IP ~5 邊緣，QS 難、缺 K 無用。樣本 low (BBE 29/GS 2) |

### 備註
- 2026-06-15 首次評估（recorded 12:26）：Gusto 唯一過 Rotation gate + Sum ≥15 + true_starter（WebSearch 確認）。Rotation gate 🚫 排除 3 位（Mitch Spence KC g1/gs0、Andrew Alvarez WSH g7/gs2、Tobias Myers NYM g20/gs2 — 全 pure-RP/long-relief）。owned_by_others 13 位（含 Zack Wheeler / Dustin May / Shota Imanaga / MacKenzie Gore）+ 本隊 1 位（J.T. Ginn ATH vs PIT）。無 Sum<15 hard floor 排除項。
- Gusto opener_suspect flag = stale：歷史 IP/GS 3.0 來自 ramp-up（3A 拉上來）+ 一場 2 天短休的 opener 式出賽，Marlins 本輪明確「分離」配對投手把他當正規 SP。預期 IP ~5（low-end true starter，仍 building）。
- TBD 2 場（SD @ STL、MIN @ TEX，皆客場 SP 未公布），建議 TW 6/15 晚上/6/16 早上呼叫 `/stream-sp 2026-06-15 --tbd-only` 補查。
- 用戶決策建議：Gusto 是 floor/控球型賭注，**缺 K 或要 QS 都不適合**；只有「想要一個不爆 BB、GB 壓 HR、對手對 RHP 偏弱的低變異 5 IP」才考慮，且要接受 ramp-up 可能 <5 IP。整體本日無強推候選。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-06-16
- recorded_at: 2026-06-15T12:26:12+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- TOR @ BOS (TOR away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Zebby Matthews | MIN @ TEX | TEX (.730 🟡 / vs RHP .699) | 16% | 30/18 | **P80-90**·P25-40·P70-80·<P25·**P80-90** | ✅ 推 | Sum 30 最高 + IP/GS 6.06 P80-90 深投 + BB/9 2.23 P70-80 控球 + xwOBACON .348 P80-90 被打輕 + ✅ 撿便宜運氣（ERA 5.20 vs xERA 3.76）；對手 TEX 🟡 中等。風險：GB% <P25 飛球型 + Whiff P25-40 K 不多 + 6 GS 樣本 |
| Robert Gasser | MIL vs CLE | CLE (.671 🟢 / vs LHP .710) | 1% | 21/18 | <P25·**P70-80**·<P25·<P25·**>P90** | ⚠️ 條件推 | buy-low：ERA 6.38 vs xERA 3.69（✅ 撿便宜運氣，差 +2.69）+ Whiff 26.5 P70-80 + xwOBACON .317 >P90 被打極輕 + K9 9.33 + 對手 CLE 🟢 冷；風險 BB/9 4.42 <P25 控球差 + GB% 21.4 <P25 飛球 + IP/GS 4.58 短 + 4 GS 樣本。缺 K 願賭可，要 QS 不適合 |
| Slade Cecconi | CLE @ MIL | MIL (.886 🔴 / vs RHP .755) | 5% | 20/27 | <P25·P25-40·P50-60·P60-70·P25-40 | ❌ 不推 | 結構平庸（無 elite 軸）+ 對手 MIL 14d .886 🔴 全聯盟最熱長打線 + vs RHP .755 也硬；ERA 4.83 xERA 4.48 無 buy-low。對位最差 |
| Kumar Rocker | TEX vs MIN | MIN (.794 🔴 / vs RHP .727) | 10% | 19/19 | <P25·P25-40·<P25·P70-80·P50-60 | ❌ 不推 | ⚠️ 賣高運氣（ERA 3.56 vs xERA 4.69，ERA 預期回升）+ 對手 MIN .794 🔴；GB% P70-80 是唯一亮點但 Sum 19 偏弱。雙扣分 |
| Ryan Feltner | COL @ CHC | CHC (.720 🟡 / vs RHP .721) | 1% | 16/24 | <P25·P50-60·P25-40·P40-50·<P25 | ❌ 不推 | xwOBACON .413 <P25 on-contact 被打慘 + ERA 5.20 xERA 5.75（無 buy-low）+ Sum 16 偏弱；對手 CHC 🟡 中等但客場 Wrigley 不利飛球。結構弱 |
| Brady Singer | CIN vs NYM | NYM (.751 🟡 / vs RHP .670) | 11% | 15/21 | <P25·P25-40·P40-50·P40-50·<P25 | ❌ 不推 | xwOBACON <P25 + WHIP 1.64 + xERA 5.79（運氣未來更糟）+ Sum 15 剛過 floor；對手 NYM vs RHP .670 偏弱是唯一利多但救不了自身結構崩 |

### 備註
- 2026-06-16 首次評估（recorded 12:26）：6 位過 Rotation gate + Sum ≥15 + true_starter（全 true_starter，免 WebSearch）。Rotation gate 🚫 排除 2 位（Tyler Phillips MIA g19/gs3 Sum 29、Jack Perkins ATH g19/gs2 Sum 23 Whiff P80-90 — 結構不差但 pure-RP/long-relief 排除）。Sum<15 hard floor 排除 2 位（Christian Scott NYM Sum 7、Adrian Houser SF Sum 12）。owned_by_others 17 位（含 Jesús Luzardo / Gerrit Cole / Framber Valdez / Hunter Brown / Logan Gilbert / Michael King）+ 本隊 2 位（Andre Pallante STL vs SD、Reid Detmers LAA @ AZ）。
- TBD 1 場（TOR @ BOS，TOR away SP 未公布；BOS = Payton Tolle 別隊），建議補查。
- 排序：**Matthews >> Gasser > 其餘 4 位 ❌**。Matthews 唯一 ✅ 推（Sum 30 三條件全滿：深投 + 控球 + xwOBACON 菁英 + buy-low + 對手中等），命中率最高；Gasser buy-low 賭注（xERA 差 +2.69 + K + 對手最冷，但控球/飛球/短局風險）；Cecconi/Rocker 對手 🔴 + Feltner/Singer 結構弱全 ❌。
- 用戶決策建議：① 缺 QS/IP/ERA 想穩 → **Matthews**（IP/GS P80-90 深投 + 控球 + xwOBACON 菁英 + ERA 回歸，本兩日最佳）② 缺 K + 願賭 buy-low → Gasser（K9 9.33 + xERA 大幅低於 ERA + 對手冷，但控球差短局）③ 不缺或對手嫌硬 → pass。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
