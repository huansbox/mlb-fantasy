# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-07-05
- recorded_at: 2026-07-03T09:55:00+08:00
- last_recheck_at: 2026-07-05T12:12:00+08:00

### TBD 場次（待補查）
- TB @ HOU (TB away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Javier Assad | CHC home | STL (.738 🟡 / vs RHP .726) | 11% | 25/21 | P40-50·<P25·P70-80·P50-60·P40-50 | ⚠️ 條件推 (deep) | deep 確認 lens verdict：6 月轉先發 5 場 ERA 3.16 / **WHIP 0.97**（含 6/30 SD 崩局仍 0.97 — HR 型不淹跑者）+ 近 6 場 ERA 3.25 + floor 中（僅 1 崩，hard rule 未觸發）；STL 7d .779 vs 14d .735 落差 <.080 → 14d 中強下緣為錨。IP ~5 + W 40-45%（對投 Liberatore ERA 5.33）+ WHIP 正貢獻；K ~3 無助。QS ~30% 零邊際 |
| Luinder Avila | KC home | PHI (.799 🔴 / vs RHP .728) | 2% | 22/— | <P25·P50-60·<P25·P50-60·P70-80 | ❌ 不推 (deep) | deep：floor 高 hard rule 觸發（近 6 場 2 崩 — 6/12 HOU 0.2IP 8ER + 6/28 對弱打 CWS 4ER；近 6 ERA 5.68）+ 6 月 BB9 6.4 / WHIP 1.54 — WHIP 拉鋸下主動扣分；PHI 三窗 .780→.799→.826 越打越燙。唯一誘因 PHI K% 26 → K ~4-5，不抵 |
| Ryan Johnson | LAA home | BOS (.694 🟢 / vs RHP .676) | 2% | 19/— | <P25·P40-50·P25-40·<P25·P80-90 | ❌ 不推 (deep) | deep：floor-risk hard rule 觸發（近 6 場 ERA 6.00 含 5 月 relief 段 + 6/18 對弱打 ATH 5ER/2HR 崩盤）→ 機械降級。bull case 真實但樣本撐不起：recall 後僅 3 場先發（5ER → 0ER/8K → 1ER，ERA 3.38，N<4）+ BOS 三窗全冷（.684/.701/.600、R/G ≤3.8）+ vs RHP .676 + xwOBACON P80-90 + ✅ 撿便宜運氣。GB <P25 HR 病（recall 後 16IP 3HR）+ leash ~90 球。席位已官方確認（G-Rod 7/10 回歸）。ERA/WHIP 已定純賭 K/ratio 可小賭 5-6IP+4-6K；正常情境 pass。QS ~35%。0704 晚補查：已由我方 claim（轉入本隊，非 FA）|
| Tanner Gordon | COL home | SF (.702 🟢 / vs RHP .737) | — | 19/13 | <P25·P50-60·>P90·<P25·<P25 | ❌ 不推 (deep) | deep：floor 高（近 6 場 3 崩 — TEX 7ER / SF 4ER / MIA 5ER 含弱打，近 6 ERA 6.84）+ 6 月缺陣整月後回歸首戰 MIA 5IP 5ER 9H（WHIP 1.80）；Coors + WHIP 拉鋸下負資產。SF 14d .702 偏冷是唯一利多 |
| Aaron Nola | PHI away | KC (.634 🟢 / vs RHP .708) | 47% | 16/25 | <P25·P50-60·P40-50·P25-40·<P25 | ❌ 不推 | 名氣款：雙年 ERA 6+ + xwOBACON <P25 結構性被打爆；KC 🟢 + K9 9.2 唯一誘因，✅ 撿便宜運氣不足以翻。0704 晚補查：已被別隊認領 |
| Brandon Sproat | MIL away | AZ (.684 🟢 / vs RHP .665) | 21% | 15/21 | <P25·P60-70·<P25·P40-50·<P25 | ❌ 不推 | Sum 15 貼 hard floor + BB/9 4.08 + xwOBACON <P25；K9 9.6 有 K 但 WHIP / 爆局風險高。0704 補查：已被別隊認領 |

### 備註
- 2026-07-03 首次評估：7 位過 filter 進主表（Assad ⚠️ / Johnson ⚠️ / 其餘 ❌）。Sum<15 hard floor 排除 3 位（Erick Fedde 13 / Matthew Liberatore 9 / JP Sears 9 — Sears 為 small_sample 但先被 hard floor 淘汰，省 WebSearch）。Rotation gate 🚫 排除 1 位（Cal Quantrill TEX vs DET g17/gs2 IP/GS 3.0）。
- **排序：Johnson（席位確認前提下最佳）> Assad（安全但零 K 上限）**。Johnson 的先發需在 TW 7/4-7/5 確認 LAA 官方 probable（G-Rod activation 新聞）；若被擠掉則 Assad 是唯一可用。TB @ HOU 的 TB 端 + SF 端仍 TBD，建議 TW 7/4 `/stream-sp 2026-07-05 --tbd-only` 補查。
- 2026-07-04 09:55 補查：無新公布 starter（TB @ HOU 的 TB 端、SF @ COL 的 SF 端仍 TBD）。變化三件：① **Johnson 席位疑慮解除** — WebSearch 確認官方 probable 7/5 vs BOS（Suárez 對投），G-Rod（Grayson Rodriguez，6/15 IL 低背緊繃）預期 7/10 才回歸，opener_suspect flag 為早季 relief artifact，6/18 recall 後 3 場常規先發 → **升為本日首選**；② Assad 對手 STL 14d OPS .664 🟢 → .733 🟡 轉熱，「STL 冷」理由弱化，上限再降；③ Sproat 已被別隊認領（lost_to_others）。排序更新：**Johnson > Assad**，差距拉大。
- 2026-07-04 10:02 deep eval（2 位候選）：
  - **Ryan Johnson**：⚠️ 條件推 → **❌ 不推 (deep) 降級**。差異訊號 = ① floor-risk hard rule 觸發：近 6 場 ERA 6.00（含 5 月 relief 段）+ 6/18 對弱打 ATH 5ER/2HR 崩盤（1 崩 + ERA ≥4.50 = 條件 (b)）；② recall 後先發樣本僅 3 場（N<4 不足 override N=6 窗口），2 好 1 壞無法獨立支撐 sample=medium 的結構利多；③ BOS 冷是真訊號（三窗 .600-.701 + R/G ≤3.8 + vs RHP .676 全表最弱）但 7d .600 vs 14d 落差 .101 → 強制 14d .701 為錨，非極端弱。限定情境：ERA/WHIP 已定純賭 K/ratio 可小賭。
  - **Javier Assad**：⚠️ 條件推 → **❌ 不推 (deep) 降級**。差異訊號 = ① 對手重評：STL 30d .774 / 14d .733 / 7d .783 + 7d R/G 7.2，「STL 冷」前提（scan 14d .664）完全翻掉，回歸判斷中強偏熱；② 近 3 場 6HR（13.1IP 9ER ≈ 6.08 ERA）HR wave 進行中；③ pattern：對強/中強打線 6 次 4 崩 0 QS，兩場 QS gem 全來自 SF 弱打。
- deep 排序：**本日（7/5）無可推候選**（Johnson ❌ / Assad ❌）。若必須串：Johnson 限定情境 > Assad（BOS 遠冷於 STL + Johnson 有 K upside；Assad 只剩 CHC 打線帶來的 W ~40-45%）。TB 端 / SF 端 TBD 公布後補查再議。
- 2026-07-04 20:55 補查：無新公布 starter（TB 端 / SF 端仍 TBD）。新入池 Fedde(Sum 13)/Liberatore(Sum 9)/Sears(Sum 9) 全 Sum<15 hard floor 排除。Nola 已被別隊認領（lost_to_others）；Ryan Johnson 已由我方 claim（owned_by_me，限定情境賭 K 落地）。
- 2026-07-05 12:04 補查（用戶 lens：IP/W/K/WHIP 拉鋸；ERA 穩贏 / QS 穩輸 → 零邊際成本）：SF 端公布 = 🆕 Tyler Mahle（Sum 14 hard floor 排除 — @Coors + COL 14d .871 🔴 + WHIP 1.47，✅ 撿便宜運氣不救）；TB 端仍 TBD（HOU 端 = Peter Lambert 別隊持有）。WSH 換 starter：Mikolas → Cade Cavalli（別隊持有），Mikolas 舊評移除。Liberatore(9)/Sears(9) 再次 hard floor。**Lens 重排：Assad ❌(deep) → ⚠️ 條件推** — deep 降級主因全落在零邊際類別；Avila/Gordon 維持 ❌（WHIP 1.67/1.59 在 WHIP 拉鋸下主動扣分）。隊上 Johnson 今晚 vs BOS 已供 K/IP。
- 2026-07-05 12:12 deep eval（4 位，用戶 lens IP/W/K/WHIP）：
  - **Assad**：⚠️ (lens) → **⚠️ 條件推 (deep) 維持**。補強訊號 = 6 月轉先發段 5 場 25.2IP ERA 3.16 / WHIP 0.97 / QS 2-5；floor 中（近 6 場僅 1 崩 = 6/30 SD，HR 型短局非跑者洪水，hard rule (a)(b) 皆未觸發）；STL 7d .779 vs 14d .735 落差 .044 <.080 → 14d 中強下緣為錨。
  - **Avila**：❌ → **❌ (deep) 維持**。floor 高 hard rule（近 6 場 2 崩含弱打 CWS）+ 6 月 BB9 6.4 / WHIP 1.54；PHI 三窗遞增 .780→.799→.826。
  - **Gordon**：❌ → **❌ (deep) 維持**。floor 高（近 6 場 3 崩含弱打 MIA）+ 缺陣整月後回歸首戰又崩。
  - **Mahle**（hard floor 排除者，用戶指名深評，不入表）：**❌ 確認**。近 6 ERA 6.46 + floor 高（gem/崩極端交替：PHI/LAD/TB/ATH 0ER vs CIN 8ER / AZ 6ER 等 7 次 4+ER）+ COL 三窗 .861/.871/.892 全聯盟最燙級 + Coors；2025 Sum 28 prior 是唯一支撐，擋不住對手/場地。
  - deep 排序：**Assad >> Avila > Mahle ≈ Gordon**。lens 下只有 Assad 三類別（IP/W/WHIP）正期望；要 K 靠隊上 Johnson 今晚 vs BOS，Avila 的 K ~4-5 帶 WHIP 1.5+ 代價不划算。
- 2026-07-05 ~13:00 執行：**已 drop Leahy → add Assad（FA $0）**。決策依據：五選一 drop 分析（Leahy 本週剩餘 0 + 結構最弱 xERA 5.74/xwOBACON pct0 + 最易撿回）；RP 不動（Gaddis 今晚 ~25% hold 是 SV+H 主票、Ashby 是 W/K 禿鷹票）；B 案（改撿 Petersen 拉 SV+H）經 scoreboard 比較後棄 — IP −2.1 / K −2 / W 6-6 三個 loss/tie flip 的期望 ~0.8 格 > SV+H 單類 +23pp ~0.23 格。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-07-06
- recorded_at: 2026-07-04T20:55:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- NYY @ TB (both TBD)
- HOU @ WSH (both TBD)
- MIL @ STL (MIL away TBD)
- AZ @ SD (both TBD)
- TOR @ SF (both TBD)
- COL @ LAD (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Noah Cameron | KC home | PHI (.777 🔴 / vs LHP .669) | 22% | 17/29 | P25-40·P40-50·P60-70·<P25·<P25 | ❌ 不推 | Sum 17 五軸無菁英 + GB/xwOBACON 雙 <P25 + PHI 14d .777 🔴；支撐點只有 2025 Sum 29 prior + K9 8.1 + PHI vs LHP .669 |

### 備註
- 2026-07-04 20:55 首次評估：僅 1 位過 filter（Cameron ❌）。Sum<15 hard floor 排除 1 位（Reynaldo López Sum 9 — g20/gs7 swingman，ERA 3.31 但 xERA 4.60 ⚠️ 賣高運氣，BB/9 3.83 + 三軸 <P25）。Owned by 別隊 3 位（C. Sánchez / Peralta / McGreevy）。**6 場 TBD**（NYY@TB / HOU@WSH / AZ@SD / TOR@SF / COL@LAD 雙邊 + MIL 端），建議 TW 7/5 早上 `/stream-sp 7/6 --tbd-only` 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
