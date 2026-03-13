# MLB Fantasy Baseball 選秀分析專案

## 專案概述

針對 2026 Yahoo Fantasy Baseball 聯賽，進行格式專屬的選秀分析與策略制定。

## 聯賽設定

- **平台**：Yahoo Fantasy Baseball
- **賽制**：H2H **One Win 勝負制**（14 類別合計，贏 8+ = 1 週勝）
- **隊伍數**：12 隊，分兩個聯盟
- **選秀**：蛇形選秀（Snake Draft），22 輪，順位未定
- **名單配置**：
  - 打者：C / 1B / 2B / 3B / SS / OF×3 / UTIL×2（共 10 人）
  - 投手：SP×4 / RP×2 / P×3（共 9 人）
  - 板凳 / IL / NA
- **計分類別（7×7 確認版）**：
  - 打者：R, HR, RBI, SB, BB, AVG, OPS
  - 投手：IP, W, K, ERA, WHIP, QS, SV+H
- **限制**：
  - 每週最低 65 投球局數（Min IP = 65，未達 → ERA + WHIP 判負）
  - 每週最多 6 次異動（Max Acquisition = 6）

## 格式狀態（已確認）

- **確認版 7×7 勝負制**（2026-03-13 確認）
- 原 8×8 分析保留作參考（`分析1`、`分析2`、`分析3`）
- 所有策略文件已更新為 7×7 確認版

## 7×7 格式關鍵特性

### vs 原 8×8 的結構性改變（僅兩項打者改動）

1. **移除打者 K（負向）** → 高三振球員完全解鎖（Judge、Schwarber 大升）
2. **SLG → OPS** → 加入 OBP 維度，BB 雙重計算（BB 欄 + OPS 的 OBP）
3. **BB 保留、AVG 保留** → 與 8×8 相同
4. **IP 取代投手 BB** → 工作馬 SP 暴漲（Webb +7、Valdez +5），控球型溢價消失
5. **SV+H 合併** → RP 價值腰斬（覆蓋 1 類別而非 2）+ IP -2 再重創
6. **勝負制（14 類別合計贏 8+）** → 可策略性 punt 2 項

### 勝負制策略含義

- **Punt SB + Punt SV+H**：放棄 2/14 → 需贏 8/12 = 67% → 完全可行
- **力量 punt 路線**：專攻 R, HR, RBI, BB, AVG, OPS + SP 六項
- **解鎖球員**：Alvarez（零 SB）、Olson（高 K→無懲罰）、Schwarber（K 移除翻身）

## 核心分析框架

三層遞進分析：

```
Layer 1：格式類別貢獻評分（每位球員在 7 項中的 +2 到 -2 評分）
Layer 2：跨守位替代價值 VOR（相對於守位替代水平的超額貢獻）
Layer 3：ADP 套利標記（格式排名 vs 市場 ADP 的落差）
+ Layer 4：勝負制 punt 路線適配性
```

## 7×7 已確立的分析結論

### VOR Top 5
Skubal(+12) >> Judge(+10) > Soto(+9) > Crochet/Skenes(+8) > Vlad/Acuña/Henderson/Ramírez(+7)

### SP 價值排序（IP 類別加持）
Skubal(+12) >> Webb/Sánchez(+7) > Crochet/Skenes(+8) > Gilbert(+6) > Valdez/Woo(+5)

### K 移除影響
- **大升**：Judge(+10→+11)、Schwarber(+3→+4)、De La Cruz(+4→+5)、Olson(+4→+5)
- **大降**：Vlad(+10→+8)、Ramírez(+9→+7)、Betts(+6→+4)、Kwan(+4→+2)、Perdomo(+2→0)

### RP 大幅貶值
- 所有 RP 受 IP -2 結構性懲罰 + SV+H 合併
- RP 從「前 4 輪必搶」降為「最後幾輪隨緣」

### 守位稀缺性（維持）
2B（最稀缺）> SS > 1B ≈ 3B > C > OF

## 45 秒速查決策規則（7×7 確認版）

- **打者**：BB% > 10% → OPS > .830 → AVG > .260，兩項通過就選
- **SP**：IP > 180 → ERA < 3.50，兩項通過就選
- **RP**：最後幾輪才拿
- **不確定時**：選高 BB 打者、高 IP 工作馬 SP、有 2B/3B 資格的

## 文件結構

| 文件 | 用途 | 狀態 |
|------|------|------|
| **`7x7-備案分析.md`** | **7×7 確認版分析**（類別評分+VOR+策略） | ✅ 完成 |
| `作戰策略.md` | 7×7 選秀日決策樹（R1-R5 + 守位檢查） | ✅ 完成 |
| `draft-helper.html` | 選秀日互動助手（7×7 確認版分數） | ✅ 完成 |
| `分析1-格式類別貢獻評分.md` | 原 8×8 打者+投手八項評分 | ✅ 參考用 |
| `分析2-跨守位替代價值VOR.md` | 原 8×8 跨守位統一排名 | ✅ 參考用 |
| `分析3-實戰選秀排名與行動指南.md` | 原 8×8 ADP 套利+行動指南 | ✅ 參考用 |
| `yahoo-app-rank.txt` / `yahoo-app-rank - 56.txt` / `yahoo-app-rank - 152.txt` | Yahoo App 排名原始數據 | ✅ 資料 |
| `draft-sim.js` | 蒙地卡羅選秀模擬器（200 次 × 12 順位） | ✅ 完成 |

## 選秀日工具

- **Draft Helper**：https://huansbox.github.io/mlb-fantasy/draft-helper.html
- 單一 HTML，手機瀏覽器直接開
- 點擊劃掉 + 長按操作 + 📋複製給 AI + 已選面板（含撤銷）
- localStorage 持久化

## 數據來源與限制

- **排名以 Yahoo App Projected Rank 為準**（2026-03-12/13 擷取，前 202 名）
- **預測數據**：Steamer 2026 預測（前 30 打者 + 32 SP 有完整數據，其餘推估）
- **數據盲點**：缺乏春訓表現、小聯盟數據，系統性低估突破型新秀
- **OPS 數據**：基於 Steamer AVG/BB%/SLG 推算 OBP+SLG，非精確值
- **7×7 計算公式**：7×7 淨分 = 8×8 淨分 - K 欄分數 - SLG 分數 + OPS 分數
