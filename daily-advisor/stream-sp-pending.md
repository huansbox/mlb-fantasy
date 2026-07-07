# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-07-07
- recorded_at: 2026-07-06T09:19:00+08:00
- last_recheck_at: 2026-07-07T11:52:00+08:00

### TBD 場次（待補查）
- MIL @ STL (STL home TBD)
- MIL @ STL (both TBD)（雙重賽 G2）
- SEA @ MIA (SEA away TBD)
- KC @ NYM (NYM home TBD)
- PHI @ CIN (PHI away TBD)
- AZ @ SD (SD home TBD)
- TOR @ SF (TOR away TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 | mlb_id |
|---|---|---|---|---|---|---|---|---|
| Trevor McDonald | SF home | TOR (.570 🟢 / vs RHP .701) | 5% | 29/46 | <P25·P25-40·P40-50·**>P90**·**>P90** | ⚠️ 條件推 (deep) | deep 降級：近 6 場 ERA 4.50（觸 ❌ 邊界）+ 弱-中打崩盤 fingerprint（5/22 CWS 7ER·6/13 CHC 4ER）+ 近 6 IP/GS 4.67 → QS 轉換率低於 Sum 29 結構暗示；但 TOR 14d .570 全日最冷（7d .487 噪音、14d 錨仍極弱）+ 末 2 場回穩（ATL 3ER·AZ 6IP 0ER）→ 當日最佳但非安全串流點 | 686790 |
| Andrew Alvarez | WSH home | HOU (.710 🟢 / vs LHP .714) | 4% | 22/25 | <P25·**P80-90**·<P25·**>P90**·<P25 | ⚠️ 條件推 (deep) | deep 維持（範圍收窄）：全季 11 出賽 0 QS、單場上限 4.2 IP / PC≤90 硬 workload cap → QS 0%·W≈0%（先發 W 需 5 完整局，本季從未達過）；近 6 ERA 2.45 + K9 10.9 floor 低 — 純「4 局賭 5-6 K + 小補 IP」窄情境 | 674841 |
| Zac Gallen | AZ away | SD (.770 🔴 / vs RHP .675) | 35% | 16/28 | <P25·<P25·P50-60·P60-70·<P25 | ❌ 不推 (deep) | deep 維持（強化）：近 6 場 ERA 8.54、5/6 場 ER≥4、7 HR、K9 3.9 全面崩壞；SD 30d→7d .735→.785 遞增火燙蓋過季 vs RHP .675 — 硬避開 | 668678 |

### 備註
- 2026-07-06 09:22 deep eval（3 位候選）：
  - **Trevor McDonald**：✅ 推（scan）→ **⚠️ 條件推 (deep) 降級**。差異訊號 = 近 6 場 ERA 4.50（觸 ❌ 邊界）+ 弱-中打崩盤 fingerprint（CWS 7ER / CHC 4ER）是 Sum 29 反映不到的 QS 轉換率問題；TOR 14d .570 極弱（7d .487-14d 落差 .083 → 強制 14d 錨）+ 末 2 場回穩（ATL 3ER·AZ 6IP 0ER 1H）留住條件推。
  - **Andrew Alvarez**：⚠️（scan）→ **⚠️ 維持（範圍收窄）**。差異訊號 = 全季 0 QS / 單場 max 4.2 IP 硬 workload cap → 先發 W 需 5 完整局，本季未達過 → W≈0%；比 scan「賭 K」更窄：只值 4 局 5-6 K + 比率小補（近 6 WHIP 1.44 其實不算保護）。
  - **Zac Gallen**：❌（scan）→ **❌ 維持（強化）**。差異訊號 = 近 6 ERA 8.54 + 5/6 場崩 + 7 HR + K9 3.9；SD 三窗遞增 .735→.770→.785 真火燙非噪音。
- deep 排序：**McDonald > Alvarez >> Gallen**。要 QS/W → 唯一 McDonald（QS ~45-50%）；K contested + ERA 保護 → Alvarez 4 局 5-6 K（零 QS/W 貢獻）；Gallen 硬避開。本日 McDonald 是「最佳但非安全」串流點。
- _（free-form 區，用戶可手寫「已 claim X 」「想下週再評估 Y」等註記。AI 讀進來但不主動覆寫。）_
