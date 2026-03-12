# MLB Fantasy Baseball 選秀分析專案

## 專案概述

針對 2026 Yahoo Fantasy Baseball 8×8 H2H Categories 聯賽，進行格式專屬的選秀分析與策略制定。

## 聯賽設定

- **平台**：Yahoo Fantasy Baseball
- **賽制**：H2H Categories（每週對戰）
- **隊伍數**：12 隊，分兩個聯盟
- **選秀**：蛇形選秀（Snake Draft），22 輪，順位未定
- **名單配置**：
  - 打者：C / 1B / 2B / 3B / SS / OF×3 / UTIL×2（共 10 人）
  - 投手：SP×4 / RP×2 / P×3（共 9 人）
  - 板凳 / IL / NA
- **計分類別（8×8）**：
  - 打者：R, HR, RBI, SB, BB, K(負向), AVG, SLG
  - 投手：W, SV, BB(負向), K, HLD, ERA, WHIP, QS
- **限制**：
  - 每週最低 65 投球局數（Min IP = 65）
  - 每週最多 6 次異動（Max Acquisition = 6）

## 格式關鍵特性

與標準 5×5 聯賽的六大差異，決定了所有分析的基礎邏輯：

1. **打者 K 扣分** → 低 K% 球員價值上升，高 K 強打者被懲罰
2. **BB 計數** → 高保送的每日先發球員雙重受益
3. **SLG 取代 OPS** → 力量雙重計算（HR+SLG），OBP 專精型無用
4. **HLD 獨立計分** → 菁英中繼（SU）與終結者（CL）等值，但 ADP 成本低 3-5 倍
5. **QS 計分** → 工作馬型投手（能投 6+ 局）價值提升
6. **投手 BB 扣分** → 控球差的投手在 BB+WHIP 雙重失血

## 核心分析框架

三層遞進分析（見 `plan-8x8-draft-analysis.md`）：

```
Layer 1：格式類別貢獻評分（每位球員在 8 項中的 +2 到 -2 評分）
Layer 2：跨守位替代價值 VOR（相對於守位替代水平的超額貢獻）
Layer 3：ADP 套利標記（格式排名 vs 市場 ADP 的落差）
```

## 已確立的分析結論

### 守位稀缺性排序
2B（最稀缺）> SS（有斷層但深度緩衝）> 1B ≈ 3B（中等）> C（兩極化）> OF（最深）

### 格式評分核心指標
- **打者**：K% 是最強單一預測指標（每高一級 K%，淨分平均掉 1.2 分）
- **投手**：BB% 是最強單一預測指標（雙重懲罰：BB 欄 + WHIP 欄）

### 最大套利機會（以 App 排名計）
- 打者：Freeman（App 41, VOR+6）、Chisholm（App 53, VOR+5）、Machado（App 51, VOR+5）
- 2B：Altuve（App 55+, VOR+5）、Albies（App 55+, VOR+5）
- RP：Cade Smith（App 43, VOR+9）、Whitlock（免費 VOR+7）、Gaddis/Jax/Garcia
- ⚠️ SP 套利因 App 推高而縮小：Webb(25)、Wheeler(26)、Kirby(38) 已是公平價

### 最大格式陷阱
- 打者：Schwarber（App 19, VOR+1）、De La Cruz（App 27, VOR+2）、Raleigh（App 42, VOR+3）
- SP：Snell（VOR -1）、Glasnow（VOR 0）、Cease（App 54, VOR+1）

## 45 秒速查決策規則

- **打者**：K% < 20% → BB% > 10% → SLG > .450，三項至少兩項通過就選
- **投手**：BB% < 7% 選，> 9% 不選
- **不確定時**：選低 K 的打者、低 BB 的投手、有 2B/3B 資格的人

## 文件結構

| 文件 | 用途 | 狀態 |
|------|------|------|
| `plan-8x8-draft-analysis.md` | 分析計畫（4 Task / 16 Step） | ✅ 完成 |
| `分析1-格式類別貢獻評分.md` | 打者+投手的八項評分 | ✅ Task 1+2 完成 |
| `分析2-跨守位替代價值VOR.md` | 跨守位統一排名 | ✅ Task 3 完成 |
| `分析3-實戰選秀排名與行動指南.md` | ADP 套利+價格帶行動指南+R1-R2 優先名單+Plan B+45 秒速查 | ✅ Task 4 完成 |
| `draft-helper.html` | 選秀日互動助手（手機可用） | ✅ 完成 |
| `2026 FanGraphs Fantasy Baseball ADP 資料.md` | 原始 ADP 數據 | ✅ 資料收集完成 |
| `2026 守位稀缺性分析 - 內野與捕手篇.md` | 守位分析（交叉比對） | ✅ 完成 |
| `*-claude.md` / `*-gemini.md` | 兩份 AI 策略報告（原始輸入） | ✅ 參考資料 |
| `2026 Yahoo Fantasy Baseball 8×8 H2H 聯賽選秀策略.md` | Claude 報告中文翻譯 | ✅ 完成 |

## 選秀日工具

- **Draft Helper**：https://huansbox.github.io/mlb-fantasy/draft-helper.html
- 單一 HTML，手機瀏覽器直接開
- 色標（綠=搶、黃=可選、紫=可等、紅=避開）+ 點擊劃掉 + VOR/淨分排序
- localStorage 持久化，關掉再開狀態還在

## 數據來源與限制

- **三套排名系統**：
  1. FanGraphs 跨平台共識 ADP
  2. Yahoo 網頁版 Pre-Season 排名（編輯手動排列）
  3. **Yahoo App Projected Rank**（預測系統自動生成）← 對手實際看到的排名
- **最終策略以 App 排名為準**（2026-03-12 擷取，前 55 名完整校正）
- **App vs 網頁版關鍵差異**：App SP 極端偏高（前 20 名中 8 個 SP），打者被壓低
- **預測數據**：Steamer 2026 預測（前 30 打者 + 32 SP 有完整數據，其餘推估）
- **Yahoo 守位資格**：2026 年 Mookie Betts 僅有 SS（無 2B），已反映在分析中
- **原始 App 排名數據**：`yahoo-app-rank.txt`
