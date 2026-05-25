# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-25
- recorded_at: 2026-05-25T13:01:00+08:00
- last_recheck_at: —

### TBD 場次（待補查）
_（無 TBD）_

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Tatsuya Imai | HOU away | TEX (.712) | 35% | 21/— | <P25·**>P90**·<P25·P70-80·<P25 | ❌ 不推 | Whiff P90+ K 樂透但 IP/GS 3.47 封 K 量上限 + BB/9 7.27 狂吃 WHIP + xwOBACON <P25 容易長打掉 ER；ERA 8.31/xERA 6.09 luck✅但結構雙刀 |

### 備註
- 2026-05-25 13:01 首次評估：1 位候選通過 Rotation gate + Sum ≥15 + true_starter。
- 已過濾：Tanner Gordon（Rotation gate 🚫，pure-RP/long-relief）+ 別隊 24 位 + 本隊 0 位。
- 無 TBD，無需補查。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-26
- recorded_at: 2026-05-25T13:01:00+08:00
- last_recheck_at: 2026-05-25T13:28:55+08:00

### TBD 場次（待補查）
- CHC @ PIT (CHC away TBD)
- MIA @ TOR (TOR home TBD)
- CIN @ NYM (NYM home TBD)
- NYY @ KC (KC home TBD)
- AZ @ SF (SF home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Griffin Canning | SD home | PHI (.621) | 1% | 27/20 | <P25·**>P90**·<P25·**P80-90**·P50-60 | ❌ 不推 (deep) | 4 場樣本 0 QS + 3/4 場 ER ≥3 (75% 崩盤率) + IP/GS 4.0 結構封 QS；對 STL 主場 4.1IP/6ER + MIL 客場 1.2IP/6ER 雙崩；PHI 7d 雖 .514 但會均值回歸 ~.640，環境利好不足以蓋過 SP 自身 floor 破裂；buy-low (xERA 4.02) 適用季線不適用 1 場串流 |
| Jason Alexander | HOU away | TEX (.740) | — | 21/12 | P80-90·<P25·<P25·—·>P90 | ❌ 不推 | Rotation gate ⚠️ small_sample（GS=1 / BBE=0 不可信）+ 2025 Sum 12 雙年低 + 對手 .740 🟡 |
| Sean Burke | CWS home | MIN (.736) | 11% | 17/11 | <P25·<P25·**P70-80**·<P25·P50-60 | ❌ 不推 | 僅 BB/9 一軸亮點 + 2025 Sum 11 雙年低 + 對手 .736 🟡，5 軸 3 個 <P25 |
| Kyle Freeland | COL away | LAD (.754) | 1% | 15/21 | <P25·P40-50·P25-40·P40-50·<P25 | ❌ 不推 | COL 客場去 LAD（Dodger Stadium + 強打），對手 .754 🟡 致命；雖 luck✅ -1.32 但 LAD 會把運氣往爛吃 |

### 備註
- 2026-05-25 13:01 首次評估：4 位候選通過 Rotation gate + Sum ≥15 + true_starter（Lauer Sum 5 hard floor 排除）。
- 已過濾：Eric Lauer（Sum 5 hard floor，5 軸全 <P25）+ 別隊 17 位 + 本隊 3 位（Cantillo/Montero/Severino）。
- 本隊 5/26 已有 3 位 SP 先發（Cantillo @ WSH / Montero @ LAA / Severino @ SEA），考慮 Canning 前先看陣容是否有 SP 空缺。
- TBD 5 場（含 CHC@PIT / MIA@TOR / CIN@NYM / NYY@KC / AZ@SF），建議 TW 5/26 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- 2026-05-25 13:28 deep eval（1 位候選 Canning）：
  - **Canning**：✅ → ❌ 降級 (deep)。差異訊號 = 全季僅 4 場樣本但 QS 0/4 + 3/4 場 ER ≥3（75% 崩盤率，含 STL 主場 4.1IP/6ER + MIL 客場 1.2IP/6ER 雙崩）+ IP/GS 4.0 結構封 QS；對手 PHI 30d→7d 強下滑 -.185 但 7d .514 是 5 場噪音（回歸 ~.640-.670 仍弱但非極弱）；對 LAD 強敵 5IP/3ER 存活但對 STL/MIL 中等爆 = pattern 反直覺 stuff variance 大；雙菁英 Whiff P90+/GB P80-90 是樂透工具但 BB/9 <P25 + 4 場 N 過小信心低；buy-low (xERA 4.02) 是季線回歸邏輯不適用 1 場串流
- 排序：**Canning > Burke > Alexander > Freeland**（皆 ❌ 但 Canning 對手最弱 + K 工具最佳；Freeland 客場去 LAD 最致命）。**5/26 無真正值得撿的 FA 候選**；K contested + ERA/WHIP 已輸定才賭 Canning（Whiff P90 + PHI 14d K% 27% 上限 6-8 K）。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
