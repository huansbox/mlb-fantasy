# stream-sp pending

> 由 `/stream-sp` skill 自動讀寫。每個 ET 日期一個 H2 section。
> 過期清理：ET 該日 13:00 後整段刪除（含備註，因決策週期結束）。
> Schema / 寫入規則見 `.claude/commands/stream-sp.md` Step 8。

## ET 2026-06-26
- recorded_at: 2026-06-25T12:35:00+08:00
- last_recheck_at: 2026-06-25T12:42:00+08:00

### TBD 場次（待補查）
- CIN @ PIT (PIT home TBD)
- WSH @ BAL (WSH away TBD)
- SEA @ CLE (SEA away TBD)
- AZ @ TB (both TBD)
- PHI @ NYM (both TBD)
- KC @ CWS (both TBD)
- CHC @ MIL (CHC away TBD)
- ATH @ LAA (ATH away TBD)
- ATL @ SF (SF home TBD)

### 已評估
| SP | 隊 | 對手 (14d OPS) | %own | Sum26/25 | 5-slot (IP/GS·Whiff·BB/9·GB·xwOBACON) | Verdict | 一行理由 |
|---|---|---|---|---|---|---|---|
| Joey Cantillo | CLE vs SEA | SEA (.572 🟢 / vs LHP .618) | 28% | 21/23 | <P25·**P60-70**·<P25·P40-50·**P60-70** | ⚠️ 條件推 (deep) | deep：對位 first-order 確認（SEA vs LHP .618 878PA 大樣本 + 14d .572）+ 近 2 場 command 回歸（06-13 DET 1ER/0BB → 06-20 HOU 8IP/1ER/9K/1BB 季最佳）。但近 6 場 ERA 5.16（三連爆 WSH 2IP/4ER · NYY 4ER · TEX 7ER/3HR）floor risk 高 + 短局 IP/GS<P25。缺 K + 吞 floor/WHIP → 賭；要穩不適合。inflection 僅 2 場未足驗。樣本 none |
| Walker Buehler | SD vs LAD | LAD (.744 🟡 / vs RHP .807) | 23% | 19/14 | <P25·<P25·P50-60·**P70-80**·P25-40 | ⚠️ 條件推 (deep) | deep：近 6 場 ERA 2.59 + 0 崩盤（floor 低）自身火燙，pending「Sum 偏弱」嚴重低估近況。唯一逆風 = 對老東家 LAD vs RHP .807（2278PA 大樣本，30d/14d/7d .74-.78 穩定熱非噪音）。對位 vs 自身狀態對撞，自身贏對位輸。賭手感者可撿，怕硬對位 pass。樣本 none |

### 備註
- 2026-06-26 首次評估（recorded TW 12:35，ET 6/26 為明天，9 場 TBD 多未公布）：2 位過 Rotation gate + Sum ≥15 + true_starter 進主表（Cantillo / Buehler）。Sum<15 hard floor 排除 1 位（Patrick Corbin TOR vs TEX Sum9，⚠️ 賣高運氣 ERA 4.73<xERA 5.63）+ Rotation gate 🚫 排除 1 位（Reynaldo López ATL@SF g18/gs5 pure RP，opener_suspect）。owned_by_others 14 位（含 Spencer Arrighetti / Keider Montero / Andrew Abbott / Jacob Misiorowski / Roki Sasaki / Dustin May）+ 本隊 0 位。
- 排序：**Cantillo（⚠️ 條件推）> Buehler（❌ 不推）**。Cantillo 對位雙冷 + K play 為唯一可賭；Buehler 對 LAD vs RHP .807 對位不利。整體本日無 Sum≥25 強推候選。
- TBD 9 場（多到爆，6/26 是後天 probable 多未公布），建議 TW 6/26 早上 `/stream-sp 2026-06-26 --tbd-only` 補查；公布後可能有更好候選。
- 2026-06-25 12:42 deep eval（2 位候選）：
  - **Joey Cantillo**：⚠️ 條件推 → **⚠️ 條件推 (deep) 維持**。差異訊號 = 對位 first-order 確認（SEA vs LHP .618 大樣本）+ 近 2 場 command 回歸（06-20 HOU 8IP/1ER/9K 季最佳），但近 6 場 ERA 5.16 + floor risk 高（三連爆含對弱打 WSH 2IP/4ER）+ 短局結構天花板，未達 ✅。
  - **Walker Buehler**：❌ 不推 → **⚠️ 條件推 (deep) 升級**。差異訊號 = 近 6 場 ERA 2.59 + 0 崩盤 floor 低，自身近況火燙（pending「Sum 偏弱」反映不到）；唯一逆風 = LAD vs RHP .807 大樣本硬對位 + 老東家。經典強投 vs 強打對撞。
- deep 排序：**Cantillo ≳ Buehler**（兩者皆 ⚠️ 邊緣）。streaming 一場定生死，對位權重最高 → Cantillo 對位壓倒性（SEA vs LHP .618）+ 近 2 場回歸緩解 floor；Buehler 自身火燙但撞 LAD vs RHP .807 硬牆變異大。決策分流：缺 K + 賭對位 → Cantillo；要自身穩 + 不怕對手熱 → Buehler；兩者互補可雙撿（Cantillo 賭 K / Buehler 賭 IP）。
- _（free-form 區，用戶可手寫註記。AI 讀進來但不主動覆寫。）_
