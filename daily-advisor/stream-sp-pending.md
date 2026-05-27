# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-27
- recorded_at: 2026-05-26T07:22:27+08:00
- last_recheck_at: 2026-05-27T10:34:34+08:00

### TBD 場次（待補查）
- STL @ MIL (MIL home TBD)
- TB @ BAL (BAL home TBD)
- CIN @ NYM (NYM home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Miles Mikolas | WSH away | CLE (.706) | 1% | 18/20 | <P25·<P25·P60-70·**P70-80**·<P25 | ❌ 不推 | 5 軸 3 個 <P25 (IP/GS·Whiff·xwOBACON) + Rotation gate ⚠️ (G=11/GS=6 = 牛棚混用) + 雙年低 + 對手 .706 🟢 (vs RHP .674) |

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
- 2026-05-27 10:34 補查：原 4 場 TBD → 1 場已公布 starter + 3 場仍 TBD（STL@MIL / TB@BAL / CIN@NYM）。COL@LAD 公布 Ohtani（已 owned by 別隊）。
  - **3 位舊評 ✅ 候選全被聯盟認領失效**：Springs (ATH) / McDonald (SF) / Cameron (KC) 都成為 owned_by_others → 從表中移除。
  - 1 位新公布 starter Walker Buehler（SD home vs PHI）Sum 12 hard floor 排除（5 軸 3 個 <P25 + IP/GS 短）。
  - **剩餘有效候選只有舊評 Mikolas ❌ 不推。5/27 已無值得撿的 FA。**
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_

## ET 2026-05-28
- recorded_at: 2026-05-26T07:22:27+08:00
- last_recheck_at: 2026-05-27T10:34:34+08:00

### TBD 場次（待補查）
- ATL @ BOS (BOS home TBD)
- TOR @ BAL (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Colin Rea | CHC away | PIT (.721) | 12% | 21/24 | P25-40·P25-40·P50-60·**P70-80**·<P25 | ❌ 不推 (deep) | 近 6 場 ERA **6.10** + QS 17% deep crisis + 5/17 對弱打 CWS 4.2IP/4ER 顯示 floor 在崩；PIT 季 vs RHP .740（本次 vs hand .741 一致）是 baseline，14d 由 .689 升到 .721；xwOBACON <P25 雙年 + HR variance 高（11 場 8 HR）→ 串流 ROI 不足 |

### 備註
- 2026-05-26 07:22 首次評估：1 位通過 filter。已過濾：Grayson Rodriguez（Sum 4 hard floor，2 場 BBE=0 樣本不可信 + 2025 無數據 / Rotation gate 🚫）+ Erick Fedde（Sum 12 hard floor，5 軸 4 個 <P25 + 雙年低）+ 別隊 5 位 + 本隊 1 位（Chris Sale @ BOS）。
- TBD 2 場（ATL@BOS / TOR@BAL 兩邊都 TBD），建議 TW 5/28 早上 9-10 點呼叫 `/stream-sp 補查` 補查。
- 5/28 本隊已有 Sale 先發，串流空間視陣容狀況。
- 2026-05-26 07:35 deep eval（1 位候選 Rea）：
  - **Rea**：❌ 維持不推 (deep)。差異訊號 = 近 6 場 ERA 6.10 + QS 17% 是 deep crisis（pending 沒反映）+ 5/17 對弱打 CWS 4.2IP/4ER floor 崩；唯一支撐是 5/23 對 HOU 7IP/3ER QS 1 場近況，但對 PIT 季 vs RHP .740 baseline 不弱 → 維持不推結論成立
- 2026-05-27 10:34 補查：TBD 仍 2 場未公布（ATL@BOS home / TOR@BAL both）。
  - 2 位新公布 starter 都被 Sum hard floor 過濾：Grayson Rodriguez（LAA away vs DET，Sum 4 — opener_suspect + 2 場 BBE=0）/ Erick Fedde（CWS home vs MIN，Sum 12 — 5 軸 4 個 <P25 + 雙年低）。
  - Colin Rea 仍 still_starting，舊評帶回維持不推。**5/28 已無新可撿 FA**，建議今晚或明早再補一次抓 TBD 公布的 starter。
- _（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
