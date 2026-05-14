# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-05-14
- recorded_at: 2026-05-13T13:40:00+08:00
- last_recheck_at: 2026-05-14T13:00:00+08:00

### TBD 場次（待補查）
- MIA @ MIN (MIN home TBD)

### 已評估
_（本次重跑無通過 Rotation gate + Sum ≥15 + opener 真先發的 FA 候選；DET away 已公布 Keider Montero 為本隊球員，其餘 starter 全 owned by 別隊。）_

### 備註
- 2026-05-13 21:30 補查：TBD 兩場 (DET away / MIN home) 仍未公布 starter，新評 0 位。
- 2026-05-13 21:30：Robby Snelling 已被別隊撿走（用戶確認），從評估表移除（不再是 FA 候選）。
- 2026-05-14 13:00 重跑：DET away 公布 Keider Montero（本隊）。MIN home 仍 TBD。FA candidates 仍 0 位。

## ET 2026-05-15
- recorded_at: 2026-05-13T21:30:00+08:00
- last_recheck_at: 2026-05-14T13:00:00+08:00

### TBD 場次（待補查）
- PHI @ PIT (both TBD)
- BAL @ WSH (WSH home TBD)
- TOR @ DET (DET home TBD)
- MIL @ MIN (both TBD)
- BOS @ ATL (both TBD)
- TEX @ HOU (both TBD)
- KC @ STL (KC away TBD)
- AZ @ COL (COL home TBD)
- LAD @ LAA (LAD away TBD)
- SF @ ATH (both TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Sean Burke | CWS | CHC (.661) | 25% | 24/15 | <P25·<P25·**P80-90**·P40-50·**P70-80** | ⚠️ 條件推 | BB 控球 + contact 抑制雙菁英，CHC 14d .661 弱打 🟢；但 Whiff/IP/GS 雙低 + 5/8 4.1 IP 6 ER 爆 → floor 風險仍未消；雙年雙弱 24/15 |
| Dustin May | STL | KC (.709) | 15% | 20/13 | P25-40·<P25·**P70-80**·P40-50·P25-40 | ❌ 不推 | 5-slot 僅 BB/9 P70-80 邊緣；近 6 場穩 (5 場 ≥6 IP / ER ≤3) 但結構無 elite + 雙年雙弱 20/13；KC .709 中等不夠 hedge |
| Jesse Scholtens | TB | MIA (.663) | 2% | 18/24* | <P25·<P25·P25-40·P40-50·**P70-80** | ❌ 不推 | xwOBACON P70-80 + MIA .663 最弱對手；但 GS=2/G=6 mixed-role (IP/GS <P25)→QS 機率近零；雙年 prior 都非真 SP 樣本 (2025 GS=0 全 RP) |

_*Scholtens 2025 sum 24 但 GS=0 全 RP，IP/GS 缺值；雙年 prior 不是真實 SP 樣本。_

### 備註
_（free-form 區，用戶可手寫「已 claim X $Y」「想下週再評估 Z」等註記。AI 讀進來但不主動覆寫。）_
