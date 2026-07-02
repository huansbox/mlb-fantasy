# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-07-02
- recorded_at: 2026-07-02T10:18:14+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- MIA @ COL (MIA away TBD)
- STL @ ATL (ATL home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|

### 備註
- 2026-07-02 首次評估（recorded TW 10:18）：**0 位過 filter 進主表**。Rotation gate 🚫 排除 2 位（Alan Rangel PHI vs PIT g3/gs0 long-relief spot start，Sum22 但無 GS 紀錄；Ian Seymour TB @ KC g30/gs3 IP/GS 3.67 bulk 型，6/20・6/24・6/25 已連續排除同人）。無 Sum<15 / 無 v4 缺數據 / 無 opener WebSearch 觸發（兩位皆在 gate 就淘汰，省額度）。owned_by_others 13 位（含 Jared Jones / Chase Burns / Misiorowski / Cecconi / Dustin May / Valdez / Eovaldi / Bryce Miller / Sasaki）+ 本隊 1 位（Stephen Kolek KC vs TB）。
- 排序：**本日無值得串流候選**。TBD 僅 2 場（MIA 客場 / ATL 主場先發未公布），建議 TW 7/2 傍晚 `/stream-sp 2026-07-02 --tbd-only` 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_

## ET 2026-07-03
- recorded_at: 2026-07-02T10:18:14+08:00
- last_recheck_at: —

### TBD 場次（待補查）
- STL @ CHC (CHC home TBD)
- PIT @ WSH (PIT away TBD)
- NYM @ ATL (ATL home TBD)
- SF @ COL (both TBD)
- TB @ HOU (TB away TBD)
- BOS @ LAA (LAA home TBD)
- MIA @ ATH (MIA away TBD)
- MIL @ AZ (MIL away TBD)
- TOR @ SEA (SEA home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Jose Cabrera | AZ vs MIL | MIL (.737 🟡 / vs RHP .760) | 1% | 33/— | <P25·**P70-80**·**>P90**·P40-50·**P80-90** | ⚠️ 條件推 | Sum 33 三 elite 軸（BB/9 1.8 >P90 + xwOBACON P80-90 + Whiff P70-80）但僅 2 場 MLB 先發（10 IP / BBE 31）全 noise 級；AAA prior 佐證 command（61 IP、K/BB 64/16、3.69 ERA 全職先發）。WebSearch 確認 true starter 非 opener（首秀 62 球 5 IP，球數上限 ~85-90 → 期望 5-6 IP，QS 邊緣）。對手 MIL 🟡 中偏熱 + Chase Field 打者友善。賭新秀 command 可撿；要穩 pass。樣本 medium |
| Mike Paredes | MIN @ NYY | NYY (.542 🟢 / vs RHP .731) | 1% | 16/— | <P25·<P25·P25-40·P40-50·P50-60 | ❌ 不推 | 5-slot 無 elite 軸 + K9 4.62 幾無 K 價值 + ⚠️ 賣高運氣（ERA 4.26 < xERA 5.41）+ IP/GS 4.5 QS 難。唯一利多 = NYY 14d .542 🟢 聯盟級冰冷。純賭對手冷的 ratio 一場，無 K/QS upside，不值 1 次異動。樣本 medium |

### 備註
- 2026-07-03 首次評估（recorded TW 10:18，ET 7/3 為後天，9 場 TBD 多未公布）：2 位過 Rotation gate + Sum ≥15 + true_starter 進主表（Cabrera ⚠️ / Paredes ❌）。Sum<15 hard floor 排除 1 位（Christian Scott NYM @ ATL Sum11 — K9 10.6 名氣款但 BB/9 4.2 + xwOBACON <P25 + ⚠️ 賣高運氣 ERA 3.20 < xERA 4.61）。Rotation gate 🚫 排除 1 位（Jack Perkins ATH vs MIA g22/gs5 pure RP，6/21 亦排除過同人）。owned_by_others 11 位（含 Gerrit Cole / Dylan Cease / Ohtani / Michael King / Gavin Williams / Arrighetti）+ 本隊 1 位（Andre Pallante STL @ CHC）。
- Cabrera 注意：scan（statsapi probable）已列 AZ 7/3 先發 = Cabrera，但 WebSearch agent 看到部分站點仍標 D-backs TBD → **claim 前再確認官方公布**（新秀輪值填補位，Nelson/Soroka 傷癒回歸會擠掉他）。
- 排序：**Cabrera（⚠️ 條件推）唯一可賭**。Paredes 純賭 NYY 冰冷無結構支撐。9 場 TBD 公布後可能有更好候選，建議 TW 7/3 早上 `/stream-sp 2026-07-03 --tbd-only` 補查。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
