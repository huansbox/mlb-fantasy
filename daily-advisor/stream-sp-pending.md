# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-26
- recorded_at: 2026-05-25T13:01:00+08:00
- last_recheck_at: 2026-05-26T07:22:27+08:00

### TBD 場次（待補查）
- MIA @ TOR (TOR home TBD)
- CIN @ NYM (NYM home TBD)

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
- 2026-05-26 07:22 補查：原 5 場 TBD → 3 場已公布 starter + 2 場仍 TBD（MIA@TOR / CIN@NYM）。
  - 3 場新公布 starter 全被結構過濾：Jordan Wicks（CHC，Rotation gate 🚫 雙年 GS=0 = 純 RP）/ Bailey Falter（KC，Rotation gate 🚫 G=4/GS=1 = long-relief 改先發但結構分類仍排除）/ AZ@SF + NYY@KC 兩場 FA 端被結構過濾，SD@PHI 端 owned。
  - **Canning（SD home）已換成 Randy Vásquez 先發** → Canning 原評估失效。Sean Burke（CWS home vs MIN）被聯盟認領（已 owned by 別隊）→ 原評估失效。Alexander / Freeland 仍是 5/26 starter + FA，舊評帶回。
  - 剩餘有效候選只有 Alexander ❌ / Freeland ❌，皆不推。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-27
- recorded_at: 2026-05-26T07:22:27+08:00
- last_recheck_at: 2026-05-26T07:35:00+08:00

### TBD 場次（待補查）
- STL @ MIL (MIL home TBD)
- TB @ BAL (BAL home TBD)
- CIN @ NYM (NYM home TBD)
- COL @ LAD (COL away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Jeffrey Springs | ATH home | SEA (.648) | 27% | 25/22 | P50-60·P25-40·P50-60·<P25·**P80-90** | ✅ 強推 (deep) | SEA 季 vs LHP **.592** P10 極弱底盤 + 14d .648 + vs LHP K% 24.1% 強 K 加成；近 6 場 3.94 ERA + 11 場樣本足；主場 ATH 投手友善 → 三條件最齊 |
| Trevor McDonald | SF home | AZ (.842) | 13% | **40**/46 | P60-70·P70-80·**>P90**·**>P90**·P40-50 | ⚠️ 條件推 (deep) | 結構 Sum 40 頂級但 4 場 BBE=65 樣本小 + 5/22 vs CWS 弱打 3.2IP/7ER 新鮮 floor crash；AZ 14d→7d cool 但仍中強 (.840→.769) + 季 vs RHP .686 偏弱 → 可撿但信心不到 Springs |
| Miles Mikolas | WSH away | CLE (.729) | 1% | 18/20 | <P25·<P25·P60-70·P70-80·<P25 | ❌ 不推 | 5 軸 3 個 <P25 (IP/GS·Whiff·xwOBACON) + Rotation gate ⚠️ (G=11/GS=6 = 牛棚混用) + 雙年低 Sum + 對手 .729 🟡 |
| Noah Cameron | KC home | NYY (.673) | 18% | 16/29 | P25-40·P50-60·P40-50·<P25·<P25 | ⚠️ 條件推 (deep) | NYY 30d→7d -.130 巨幅 cool + Cameron 近 4 場 3.38 ERA 連 2 QS（5/22 vs SEA 6IP/0ER/8K shutout）= 短期 inflection；但季 vs LHP .788 強底盤 + 4/18 對 NYY 4IP/5ER/3HR fingerprint + xwOBACON <P25 對 NYY power 對盤 → 賭 7d cool 命中才推 |

### 備註
- 2026-05-26 07:22 首次評估：4 位通過 Rotation gate + Sum ≥15 + true_starter。已過濾：Walker Buehler（Sum 12 hard floor，5 軸幾乎全 <P25 + 雙年低）+ 別隊 21 位 + 本隊 0 位（5/27 本隊 0 SP 先發）。
- TBD 4 場（STL@MIL / TB@BAL / CIN@NYM / COL@LAD），建議 TW 5/27 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- **Trevor McDonald 強推候選但對手 🔴**：Sum 40 + BB/9 >P90 + GB% 61.5% >P90 是 fa pool 全季最罕見的結構（雙年都頂級），但對 AZ 14d .842 🔴 強打需驗證 stuff/control 能否壓制。建議：1) 跑 `/stream-sp-deep Trevor McDonald` 看 4 場 game log + 對 strong contact 隊伍歷史；2) Springs 是更穩的選擇（無對手風險）。
- 2026-05-26 07:35 deep eval（3 位候選）：
  - **Springs**：✅ 推 → ✅ 強推 (deep)。差異訊號 = SEA 季 vs LHP **.592** P10 極弱底盤（pending 14d .648 沒抓到 vs 慣用手 split）+ vs LHP K% 24.1% K 量加成 + 11 場樣本足
  - **McDonald**：⚠️ 偏推（觀察）→ ⚠️ 條件推 (deep)。差異訊號 = 5/22 對 CWS 弱打 3.2IP/7ER 是新鮮 floor crash + 14d→7d cool down (-.071) 但對手仍中強 + 4 場 BBE=65 樣本小，信心不到 Springs
  - **Cameron**：❌ 不推 → ⚠️ 條件推 (deep)。差異訊號 = NYY 30d→7d 巨幅 cool (-.130) + Cameron 近 4 場 3.38 ERA 連 2 QS（含 5/22 vs SEA 8K shutout）是 short-term inflection；但季 vs LHP .788 + 4/18 對 NYY fingerprint = 賭 cool 命中才推
- 排序：**Springs >> McDonald > Cameron**。Springs 對 ERA/WHIP/K/QS/W 全加分無大風險；McDonald 賭結構面 + 對手 cool；Cameron 賭 NYY 7d .614 cool 命中 + HR variance 押反方向（最高風險）
- 用戶決策：① ERA/WHIP 有翻盤空間 → 只撿 Springs ② ERA/WHIP 已輸定 + 堆 IP/W/K → Springs + McDonald 雙撿 ③ Cameron 除非賭命中不建議
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-28
- recorded_at: 2026-05-26T07:22:27+08:00
- last_recheck_at: 2026-05-26T07:35:00+08:00

### TBD 場次（待補查）
- ATL @ BOS (BOS home TBD)
- TOR @ BAL (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Colin Rea | CHC away | PIT (.689) | 13% | 21/24 | P25-40·P25-40·P50-60·P70-80·<P25 | ❌ 不推 (deep) | 近 6 場 ERA **6.10** + QS 17% deep crisis + 5/17 對弱打 CWS 4.2IP/4ER 顯示 floor 在崩；PIT 季 vs RHP .740 是 baseline（14d .689 / 7d .647 是低點噪音，回歸到 .700-.720「中」級）；xwOBACON <P25 雙年 + HR variance 高（11 場 8 HR）→ 串流 ROI 不足 |

### 備註
- 2026-05-26 07:22 首次評估：1 位通過 filter。已過濾：Grayson Rodriguez（Sum 4 hard floor，2 場 BBE=0 樣本不可信 + 2025 無數據 / Rotation gate 🚫）+ Erick Fedde（Sum 12 hard floor，5 軸 4 個 <P25 + 雙年低）+ 別隊 5 位 + 本隊 1 位（Chris Sale @ BOS）。
- TBD 2 場（ATL@BOS / TOR@BAL 兩邊都 TBD），建議 TW 5/28 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- 5/28 本隊已有 Sale 先發，串流空間視陣容狀況。
- 2026-05-26 07:35 deep eval（1 位候選 Rea）：
  - **Rea**：❌ 維持不推 (deep)。差異訊號 = 近 6 場 ERA 6.10 + QS 17% 是 deep crisis（pending 沒反映）+ 5/17 對弱打 CWS 4.2IP/4ER floor 崩；唯一支撐是 5/23 對 HOU 7IP/3ER QS 1 場近況，但對 PIT 季 vs RHP .740 baseline 不弱 → 維持不推結論成立
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
