---
name: waiver-scan
description: "Fantasy Baseball waiver wire 主動掃描，搜尋近期值得關注的 FA 球員並更新 waiver-log.md。用戶說「掃描 waiver」「有什麼人值得撿」「最近有誰表現好」「waiver scan」或要求主動搜尋 FA 市場時觸發。不用於評估特定已知球員（那是 player-eval 的職責）。"
---

# Waiver Wire 掃描 SOP

主動搜尋 FA 市場中值得關注的球員，套用 7×7 篩選，更新 `waiver-log.md`。

> 本 skill 負責「找名字」。找到候選人後，用 `player-eval` skill 做深入評估。
> 觸發 player-eval 的條件：初篩後仍無法確定守位資格、全季預測 IP、或當前角色時，必須交給 player-eval，不在 waiver-scan 層做最終判斷。

## 手動通報處理

用戶直接告知「{球員} 被搶了」或「我撿了 {球員}」時：
1. 將該球員從 waiver-log.md「觀察中」移至「已結案」，標記對應結果
2. 同步更新 CLAUDE.md watchlist
3. 不需要跑完整掃描流程

## Step 1：讀取現況

> {今年} = currentDate 年份（由 system context 提供）。

1. 讀 `CLAUDE.md` — 確認當前陣容、**陣容風險區塊**、watchlist
2. 讀 `waiver-log.md` — 確認觀察中球員近況 + 條件 Pass 球員是否達成重評條件
3. 讀 `roster-baseline.md` — 確認可被替換球員的當前數據（初篩快速比對用）
4. 確認今天日期（用於搜尋和 log 記錄）

## Step 2：搜尋 FA 市場

### 2a：Yahoo API 查詢（優先）

用 Bash 執行 `yahoo_query.py` 拉取聯賽實際 FA 資料：

```bash
# 依 CLAUDE.md 陣容風險標記的弱點位置查詢（範例）
python daily-advisor/yahoo_query.py fa --position CF --count 15
python daily-advisor/yahoo_query.py fa --position SP --count 15

# 近一週表現最佳的可用球員
python daily-advisor/yahoo_query.py fa --sort AR --sort-type lastweek --count 15

# 整體排名最高的可用球員
python daily-advisor/yahoo_query.py fa --sort AR --count 20
```

> `yahoo_query.py fa` 回傳 7×7 scoring stats（打者 AVG/OPS/HR/BB，投手 ERA/WHIP/K/IP）+ %owned，可直接用於初篩，減少 WebSearch 依賴。
> `--position` 參數根據 CLAUDE.md 陣容風險動態決定，不硬編碼。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。
> 若 Yahoo API 失敗（HTTP 999 rate limit 等），fallback 到 Step 2b。

### 2b：WebSearch 補充

Yahoo API 只能看到「誰是 FA」和排名，無法看到新聞脈絡。用 WebSearch 補充：

```
{今年} fantasy baseball waiver wire pickups week {週數}
{今年} MLB roster moves callups DFA
{今年} MLB IL injury update recent roster moves
{今年} fantasy baseball players dropped recently waiver claims
```

**搜尋重點**：
- 角色變動（升上大聯盟、接手先發、closer 轉換）
- **傷兵連鎖機會**（某隊主力進 IL → 替補獲得每日先發，視窗通常 24-48 小時）
- 被 drop 的前中段選秀球員（可能被其他 manager 因短期低潮誤判）

## Step 3：初篩

從搜尋結果中，**讀取 CLAUDE.md 的陣容風險和 watchlist 區塊**動態決定搜尋優先順序（不硬編碼球員名，陣容會隨賽季變動）：

**優先找**：CLAUDE.md 陣容風險標記的弱點位置和替換候選

**次要找**：
- 任何通過替補級門檻的打者 FA（BB% > 8%、OPS > .720、AVG > .240 兩項通過）
- SP 分兩層篩選：
  - 全季型：預測 IP > 150 + ERA < 4.00（in-season FA 整體質量低於選秀，門檻放寬）
  - 串流型：下週有 2 先發 + 對戰後段打線，不看全季預測

> 12 隊聯賽中通過正選級門檻（OPS > .830）的 FA 基本不存在。若出現，代表是其他 manager 的 drop 失誤，需特別注意。

**直接跳過**：
- 純速度型（punt SB 下價值低）
- RP/CL（punt SV+H）
- 明顯已被 12 隊聯賽 rostered 的球星

> 初篩只需快速判斷，不需完整 player-eval。但無法確定守位資格、IP 預測、或角色時，告知用戶建議觸發 player-eval 深入評估。

## Step 4：更新 waiver-log.md

掃描結束後更新 `waiver-log.md`（專案根目錄）。

### Log 檔結構

```markdown
# Waiver Log 2026

## 觀察中

### {球員名} ({隊伍}, {位置})
觸發：{什麼條件達成就行動，取代誰}
- {日期}：{觀察內容}

### {球員名} ({隊伍}, {位置}) — 條件 Pass
重評條件：{什麼條件達成就重新觀察}
- {日期}：{為什麼暫時 pass + 重評條件}

## 已結案

### {球員名} ({隊伍}, {位置}) — {撿了/Pass/被搶}
- {日期}：{結論一行}
```

### 更新規則

- **新球員**：加入「觀察中」，寫首次觀察紀錄 + 觸發條件
- **已在觀察中的球員**：加入新日期行，更新近況
- **達成觸發條件**：告知用戶建議行動，用戶確認後移至「已結案」
- **確認不再觀察**：移至「已結案」，寫一行結論
- **觀察中球員被其他隊 rostered**：移至「已結案」，標記「— 被搶」
- **條件性暫不觀察**：留在「觀察中」標記「— 條件 Pass」+ 重評條件，每次掃描 Step 1 檢查是否達成
- **Log 不存在**：建立新檔，從模板開始

### 同步 CLAUDE.md

掃描結果改變 watchlist 時，同步更新 CLAUDE.md 以下三處：
1. **Watchlist 打者/投手表格**（新增/移除行）
2. **行動觸發規則表格**（新增/移除對應條目）
3. **已被聯賽搶走清單**（如適用）

CLAUDE.md 只放結論（誰 + 觸發條件 + 取代目標），waiver-log.md 放完整過程。

## Step 5：輸出摘要

```
本次掃描（{日期}）：
- 搜尋來源：{列出}
- 新發現：{N} 人
- 加入觀察：{球員名列表}
- 觀察中更新：{球員名列表}
- 條件 Pass 檢查：{有無達成重評條件}
- 建議行動：{有/無，說明}
- waiver-log.md 已更新
```
