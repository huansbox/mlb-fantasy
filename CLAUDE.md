# MLB Fantasy Baseball 2026 賽季管理

## 專案概述

2026 Yahoo Fantasy Baseball 聯賽 — 選秀已完成，目前為 in-season 管理階段。

## 聯賽設定（開季確認版 2026-03-26）

- **平台**：Yahoo Fantasy Baseball
- **賽制**：H2H **One Win 勝負制**（14 類別合計，贏 8+ = 1 週勝）
- **隊伍數**：12 隊，無分區
- **名單配置**：
  - 打者：C / 1B / 2B / 3B / SS / **LF / CF / RF** / UTIL×2（共 10 人）
  - 投手：SP×4 / RP×2 / P×3（共 9 人）
  - BN×3 / IL×2 / NA×1
- **計分類別（7×7）**：
  - 打者：R, HR, RBI, SB, BB, AVG, OPS
  - 投手：IP, W, K, ERA, WHIP, QS, SV+H
- **限制與規則**：
  - 每週最低 **40** 投球局數（Min IP = 40，未達 → ERA + WHIP 判負）
  - 每週最多 6 次異動（Max Acquisition = 6）
  - Waiver：**FAB**（Free Agent Budget）+ Continual rolling list tiebreak
  - Lineup 鎖定：**Daily - Tomorrow**（每天要設隔日先發）
  - Trade Review：Commissioner，Reject Time 2 天
- **季後賽**：4 隊，Week 24-25（至 9/20）

### vs 選秀前設定的變更

| 項目 | 選秀前 | 開季版 | 影響 |
|------|--------|--------|------|
| 外野位 | OF×3 | **LF/CF/RF** | 需個別對位，CF 最稀缺 |
| Min IP | 65 | **40** | 壓力大降，4 SP 基本穩過 |
| Divisions | 兩個聯盟 | **無** | 排名單一化 |
| Bench | 未指定 | **3 格** | 替補空間緊 |

## 現役陣容（2026-03-26）

### 打者

| 位置 | 球員 | 隊伍 | 資格 | 7×7 VOR | 備註 |
|------|------|------|------|---------|------|
| C | Shea Langeliers | ATH | C | — | |
| 1B | Christian Walker | HOU | 1B | — | |
| 2B | Jazz Chisholm Jr. | NYY | 2B/3B | +5 | K 受益，2B 稀缺 |
| 3B | Manny Machado | SD | 3B | +5 | 穩定 |
| SS | Ezequiel Tovar | COL | SS | — | |
| LF | Jose Altuve | HOU | 2B/LF | +4 | K 輸家但堪用 |
| CF | Byron Buxton | MIN | CF | +5 | K 受益，**玻璃體質** |
| RF | Lawrence Butler | ATH | CF/RF | +5 | K 受益 |
| Util | Ozzie Albies | ATL | 2B | +5 | |
| Util | Steven Kwan | CLE | LF | +2 | ⚠️ 全隊最弱，替換候選 |

### 板凳打者

| 球員 | 隊伍 | 資格 | 備註 |
|------|------|------|------|
| Sal Frelick | MIL | LF/CF/RF | Buxton 保險，CF backup |
| Giancarlo Stanton | NYY | LF/RF | 純砲 |

### 投手

| 位置 | 球員 | 隊伍 | 7×7 VOR | 備註 |
|------|------|------|---------|------|
| SP | Tarik Skubal | DET | **+12** | 全聯盟 #1 |
| SP | Chris Sale | ATL | +4 | 局數風險 |
| SP | Cole Ragans | KC | +4 | |
| SP | Aaron Nola | PHI | +5 | 工作馬 |
| RP | Robert Garcia | TEX | — | 比率用 |
| RP | Garrett Whitlock | BOS | — | 比率用 |
| P | Brayan Bello | BOS | — | |
| P | Zack Littell | WSH | — | |
| P | Brady Singer | CIN | — | |

### 板凳投手

| 球員 | 隊伍 | 備註 |
|------|------|------|
| Chris Bassitt | BAL | SP 深度 |

### 傷兵

| 球員 | 隊伍 | 狀態 |
|------|------|------|
| Merrill Kelly | AZ | IL15，佔 IL 格 |

## 執行中策略

- **Punt SV+H**：RP（Garcia/Whitlock）純比率用，不追救援
- **軟 Punt SB**：不刻意追速度，但 Chisholm/Albies/Buxton 偶爾能贏
- **SP 重裝**：9 SP 深度，40 IP 門檻輕鬆過
- **目標**：每週穩拿 R/HR/RBI/BB/AVG/OPS + IP/W/K/QS/ERA/WHIP 共 12 項中的 8+

### 陣容風險

| 風險 | 說明 |
|------|------|
| **CF 深度** | 只有 Buxton + Butler + Frelick 有 CF 資格，Buxton 傷退 → 連鎖反應 |
| **Kwan（VOR +2）** | 全隊最弱環節，K 移除輸家，第一替換候選 |
| **BN 僅 3 格** | 替補空間緊，串流 SP 彈性有限 |

### Watchlist（2026-03-27）

**打者**

| 球員 | 隊伍 | 位置 | 觸發條件 | 取代目標 |
|------|------|------|---------|---------|
| **Ryan O'Hearn** | PIT | 1B/LF/RF | Walker 連 2 週 AVG < .200 或 Kwan 連 2 週 OPS < .700 | Walker 或 Kwan |

**投手**

| 球員 | 隊伍 | 類型 | 觸發條件 | 取代目標 |
|------|------|------|---------|---------|
| **Andrew Painter** | PHI | SP | 前 2-3 場先發穩定投 6+ IP | Singer |

**已被聯賽搶走**：McGonigle、Basallo、Wetherholt、McLean、Misiorowski、Pepiot、Benge

**已評估 Pass**：Correa（3B/SS，.734 OPS 不過門檻）、Liberatore（SP，預測 4.44 ERA/152 IP，不勝現有後段 SP）

### 行動觸發規則

| 條件 | 動作 |
|------|------|
| Walker 連 2 週 AVG < .200 | 撿 O'Hearn，drop Walker（O'Hearn 有 1B 資格） |
| Kwan 連 2 週 OPS < .700 且無 power 改善 | 撿 O'Hearn，drop Kwan |
| Kwan 維持 OPS > .750 + HR pace > 15 | 不動，春訓 bat speed 改善兌現中 |
| Singer 開季 ERA > 5.00 + 水泡復發 | 撿 O'Hearn，drop Singer（騰打者位） |
| Painter 前 2-3 場穩定投 6+ IP | 撿 Painter，drop Singer |
| Painter 被限 5 IP 或跳先發 | 不動，Singer 穩定局數更有用 |
| Buxton 進 IL | Frelick 頂 CF，BN 空位補 OF |

## 格式狀態

- **選秀準備階段**：已完成（2026-03-13 確認 7×7）
- **開季管理階段**：進行中（2026-03-26 起）
- 原 8×8 分析保留作參考（`分析1`、`分析2`、`分析3`）

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

### In-Season 管理

| 文件 | 用途 | 狀態 |
|------|------|------|
| `賽季管理入門.md` | H2H One Win 賽季管理入門要點（週例行、決策樹、punt 紀律） | ✅ 開季參考 |
| `waiver-log.md` | 球員觀察追蹤 log（觀察中 / 條件 Pass / 已結案） | 🔄 進行中 |
| `roster-baseline.md` | 陣容基準卡（全員預測/實際數據，eval 比較用） | 🔄 進行中 |
| `.claude/commands/player-eval.md` | 球員評估 SOP（`/player-eval`） | ✅ 完成 |
| `.claude/commands/waiver-scan.md` | Waiver wire 掃描 SOP（`/waiver-scan`，含 Yahoo FA 查詢） | ✅ 完成 |
| `.claude/commands/roster-scan.md` | 陣容基準卡週更 SOP（`/roster-scan`） | ✅ 完成 |
| `daily-advisor/yahoo_query.py` | Yahoo FA 查詢 CLI（skill 透過 Bash 呼叫） | ✅ 完成 |
| `daily-advisor/` | 每日陣容建議產生器，兩階段：速報（台灣 21:45）+ 最終報（台灣 05:00，含 Lineup 確認） | ✅ Phase 2 已部署 |
| `daily-advisor-spec.md` | Daily Advisor 需求規格與 API 研究筆記 | ✅ 參考 |
| `daily-advisor/yahoo-api-reference.md` | Yahoo Fantasy API 端點參考（已用 + 可用） | ✅ 參考 |

### 選秀準備（已完成，留作參考）

| 文件 | 用途 |
|------|------|
| `7x7-選秀分析.md` | 7×7 確認版分析（類別評分+VOR+策略） |
| `作戰策略.md` | 7×7 選秀日決策樹（R1-R5 + 守位檢查） |
| `draft-helper.html` | 選秀日互動助手（7×7 確認版分數） |
| `draft-sim.js` | 蒙地卡羅選秀模擬器（200 次 × 12 順位） |
| `分析1-格式類別貢獻評分.md` | 原 8×8 打者+投手八項評分 |
| `分析2-跨守位替代價值VOR.md` | 原 8×8 跨守位統一排名 |
| `分析3-實戰選秀排名與行動指南.md` | 原 8×8 ADP 套利+行動指南 |

## In-Season 管理決策規則

### Waiver Wire 篩選框架

**正選級（先發）**：BB% > 10% → OPS > .830 → AVG > .260，兩項通過
**替補級（backup）**：BB% > 8% → OPS > .720 → AVG > .240，不傷比率優先

### SP 串流標準
- IP > 180 → ERA < 3.50，兩項通過
- 40 IP 門檻低，通常不需刻意串流

### 每週檢查清單
1. 設定隔日先發陣容（Daily deadline）
2. 確認 SP 週排程，確保 40 IP
3. 檢查傷兵，必要時用 IL 格 + 撿替補
4. FAB 競標（週中評估 waiver 目標）

## 選秀日工具（已完成，留作參考）

- **Draft Helper**：https://huansbox.github.io/mlb-fantasy/draft-helper.html

## 數據來源與限制

- **排名以 Yahoo App Projected Rank 為準**（2026-03-12/13 擷取，前 202 名）
- **預測數據**：Steamer 2026 預測（前 30 打者 + 32 SP 有完整數據，其餘推估）
- **數據盲點**：缺乏春訓表現、小聯盟數據，系統性低估突破型新秀
- **OPS 數據**：基於 Steamer AVG/BB%/SLG 推算 OBP+SLG，非精確值
- **7×7 計算公式**：7×7 淨分 = 8×8 淨分 - K 欄分數 - SLG 分數 + OPS 分數
