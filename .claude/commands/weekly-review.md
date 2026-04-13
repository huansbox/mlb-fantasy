# Weekly Review — 週覆盤 + 週預測

每週一執行。Phase 1 覆盤上週，Phase 2 預測本週，重心**我方可控**而非對手不可控。

## 核心原則

以下原則貫穿整個流程，違反任何一項都會導致判斷失準（2026-04-13 Week 3 覆盤實戰教訓確立）：

1. **2 週合併為準**：所有強弱判斷（對手實力、我方實力、歸因）用近 2 週合併數據，**不看單週**
   - 單週易被極端事件扭曲（對手爆炸週、我方單人炸比率）
   - 3+ 週太久，人員調動後不反映當前陣容
   - 例外：開季第 2 週只能用 Week 1，註明信心低

2. **不看 BN 決策**：球員表現分析只看週 counting stats + 開季品質指標百分位
   - **禁止**用 `selected_pos='BN'` 判斷「該上沒上」或「該坐沒坐」
   - JSON 裡的 selected_pos 是 snapshot，不反映每日動態 lineup
   - 撐場/拖累歸類只看週產出 vs 開季水準

3. **意外先 news check**：表現遠離開季水準的球員（百分位差 >30 或爆炸/冰凍）先查新聞
   - 查最終報（`gh issue view {issue_number}`）有無傷勢/狀況標記
   - 必要時 WebFetch MLB Trade Rumors / RotoWire / ESPN injury
   - 歸類註明「傷勢」/「對戰特殊」/「無消息純波動」，**不要只寫「意外」**

4. **歸因分類**：預測偏差必須歸類，只有「我方結構弱」才驅動補強決策
   - **對手結構強**：對手近 2 週該類別排名 #1-3
   - **我方結構弱**：我方近 2 週該類別排名 #10-12（這才是要補強的）
   - **對稱變異**：雙方都強或都弱，近戰險輸險贏
   - **單場意外**：news check 確認的傷勢/對戰特殊
   - **單週波動**：2 週合併雙方都中段，單週極端值

5. **Skubal/Sale 雙週規律**（結構性時程）：
   - **奇數週**（Week 1, 3, 5...）：Skubal 2 GS + Sale 2 GS = **4 GS from 王牌**
   - **偶數週**（Week 2, 4, 6...）：Skubal 1 GS + Sale 1 GS = **2 GS from 王牌**
   - 偶數週預測：IP/K/W/QS 信心自動降級（高→中），補強要靠後段 SP 深度
   - 規律會隨 off-day/雨延/IL 變動，每週仍驗證實際 SP 排程

6. **重心：我方可控優先**（不同於早期版本）：
   - 對手分析只到「能預測」的程度（一張排名表），不深入陣容/SP 排程
   - 我方分析做到「能行動」的程度（球員狀態 + 趨勢 + 異常 news check）
   - 對手強弱多半混合運氣與真實力，不可控；我方陣容才是可調整的
   - 時間比重：對手 5% / 戰績歸因 10% / **我方球員 45%** / 策略驗證 20% / 行動清單 20%

7. **跨週連續性**：Phase 0 必讀 CLAUDE.md「進行中補強行動」section
   - 每週 review 開頭載入當前進行中項目（如 BB 補強、IP 補強、Whitlock 軟 cut）
   - Phase 1C 對每個項目逐一驗證指標 + 更新狀態
   - 已驗證/失敗 2 週後清理（避免 CLAUDE.md 膨脹）
   - 防止「忘記上週做了什麼」造成的決策斷層

8. **拖累者分類**：Phase 1B 識別拖累者後必須再分類（不能模糊「拖累者」一詞）
   - **slump 觀察**：單週/單場爆炸但 2025 baseline 強 → 不行動，等回歸
   - **結構性 cut 候選**：套 CLAUDE.md cut 評估流程，**雙年雙確認弱**才算
   - **單場意外**：news check 確認的傷勢/狀況 → 條件性 drop 候選（依後續發展）

## Step 1：讀取基本資料

1. 確認當前 fantasy week：
   ```bash
   python -c "
   import sys; sys.path.insert(0,'daily-advisor')
   from weekly_review import load_config, get_fantasy_week
   from datetime import datetime
   from zoneinfo import ZoneInfo
   config = load_config()
   today = datetime.now(ZoneInfo('America/New_York')).date()
   ws, we, wn = get_fantasy_week(today, config)
   print(f'Current week: {wn} ({ws} ~ {we})')
   "
   ```
2. 讀 `daily-advisor/weekly-data/week-{N}.json`（N = 當前週數，由 cron 自動準備）
3. 讀 `week-reviews.md`（上週的 predicted_outcome，用於覆盤對照）
4. **讀 CLAUDE.md `### 進行中補強行動` section**（自動已在 context，不需手動讀檔）

若 JSON 不存在，提示用戶：
- VPS 上跑：`ssh root@107.175.30.172 'cd /opt/mlb-fantasy && python3 daily-advisor/weekly_review.py --prepare'`
- 或本地即時拉取：`python daily-advisor/weekly_review.py --prepare --dry-run > daily-advisor/weekly-data/week-{N}.json`

## Step 2：讀 2 週合併排名（自 JSON）

`review.two_week_ranks` 由 prepare 時 `fetch_two_week_merge` 自動產生，包含：

- `weeks`: `[N-2, N-1]` 兩週週次
- `merged`: `{team_name: {14 cat: val}}` 12 隊合併數據
- `my_ranks`: `{cat: my_rank}` 我方 14 類別排名

> **開季第 2 週例外**：week < 3 時 `two_week_ranks` 欄位不存在（prepare 自動跳過），只能用 Week 1 單週數據，註明信心低。

這份排名表驅動 **Phase 1A 歸因 / Phase 2A 對手摘要 / Phase 2B 預測**。

## Phase 0：策略現況載入（5 min）

從 CLAUDE.md `### 進行中補強行動` section 列出當前所有項目，標記每個項目的：
- **觸發**：當初為什麼啟動
- **行動**：執行了什麼
- **驗證指標**：要看哪個類別 / 球員 / 排名
- **驗證日期**：本週是否該驗證

**輸出**：「本週要驗證的策略項目清單」（Phase 1C 會逐一檢核）。

如果上一個 review 後沒新增 review，這份清單就是「上週啟動 + 本週啟動」的並集。

## Phase 1A：戰績結果 + 簡短歸因（10%，5 min）

1. 從 JSON `review` 讀 14 類別 mine/opp/result
2. 從 `week-reviews.md` 讀上週 predicted_outcome
3. 顯示對照表：

   | 類別 | 預測 | 實際 | ✓/✗ | mine | opp | 歸因 |
   |------|------|------|------|------|-----|------|
   | R | W | L | ✗ | 33 | 36 | 對稱（雙方都強）|

4. 計算準確率
5. **歸因分類**（套用核心原則 #4）：
   - 對每項偏差（W/L/D 都算）標記 5 類：對手結構強 / 我方結構弱 / 對稱變異 / 單場意外 / 單週波動
   - **只展開**「我方結構弱」+「單場意外」兩類細節
   - 其他 3 類一行帶過（不可控）

6. **聯盟排名**（雙視角，1 段話帶過）：
   - 單週排名（從 JSON）— 參考
   - 2 週合併排名（從 Step 2）— **歸因主依據**
   - 真實結構性弱項（2 週 #10-12）：列出

## Phase 1B：我方球員狀態更新（45%，主軸，15-20 min）

> **這是整個 review 的核心**。對手分析只能影響預測，球員狀態才能驅動行動。

1. 從 `review.my_roster_performance` 讀 11 batter + 12 pitcher 的：
   - 週 counting stats（PA/R/HR/RBI/SB/BB/AVG/OPS 或 GS/IP/W/K/ERA/WHIP/QS）
   - 開季 xwOBA / BB% / Barrel% 百分位（投手對應 xERA / xwOBA allowed / HH%）

2. **撐場者**：週產出 ≥ 開季水準上一級的球員（簡短列表）

3. **拖累者識別 + 分類**：週產出 << 開季水準的球員，必須**再分類**：
   - **slump 觀察**：2025 baseline 強（>P70）+ 2026 開季也強 → 純單週 slump，不行動
   - **結構性 cut 候選**：2025 baseline 弱（<P50） + 2026 也弱 → **雙年雙確認**，套 CLAUDE.md cut 評估流程
   - **單場意外**：表現與品質背離極端（百分位差 >30）→ 必須 news check（核心原則 #3）
   - **不知道**：先 news check 再分類

4. **News check**（對單場意外 / 重大背離者）：
   - 查當週最終報（`gh issue view {issue_number}` 從 `daily_reports` 找）
   - 必要時 WebFetch 傷勢消息
   - 標註結果：「傷勢（XX）」/「無消息純波動」/「對戰特殊」/「球隊角色變化」

5. **趨勢標記**（可選，每週看 2 個變化）：
   - 上升中：哪個球員品質指標連 2 週往好的方向走
   - 下降中：哪個球員品質指標連 2 週往壞的方向走
   - 觸發行動：下降中的可能要進「條件性 drop 候選」

6. **每 4 週做一次深度雙年回顧**（Week 4, 8, 12, 16... 觸發）：
   - 11 batter + 12 pitcher 全員 2026 + 2025 雙年對照表
   - 套 cut 評估流程（雙年檢核 + 角色脈絡）
   - 一次性產出「結構性 cut 候選 / breakout 確認 / 持平」三類
   - 平週只做趨勢更新，不重做深度

## Phase 1C：策略行動驗證（20%，5 min）

對 Phase 0 載入的每個進行中補強項目逐一驗證：

1. 找對應驗證指標（類別排名 / 球員 stats）
2. 比對 1 週前狀態
3. 判定狀態：
   - **執行中**：尚未到驗證日期
   - **驗證中**：到驗證日期但結果不明顯（再等 1 週）
   - **已驗證（成功）**：指標明確改善
   - **已驗證（失敗）**：指標沒改善或惡化
4. 更新 CLAUDE.md `### 進行中補強行動` section：
   - 已驗證/失敗超過 2 週的項目移除（git log 留痕）
   - 新項目從 Phase 2C 行動清單啟動時加入
5. 記錄學習：失敗的補強項目要寫進「學到什麼」

## Phase 2A：對手摘要（5%，3 min）

> **對手分析只到能預測的程度**。我們改不了對手，深入分析陣容/SP 排程沒意義。

從 Step 2 的 2 週合併排名，**用一張表帶過**：

| 對手 RALLY MONKEY | 14 類別 2 週合併排名 |
|------|------|
| 強項 #1-5 | BB #1, K #5, R #5 |
| 中段 #6-8 | IP, W, RBI, AVG |
| 弱項 #9-12 | OPS, QS, SV+H, **WHIP, ERA, HR, SB** |

**不需要**：對手陣容深度、SP 排程細節、IL 名單

**唯一例外**：對手陣容有極端 ace SP 排在本週 → 標記「對手 Skubal 本週 1 GS 影響預測」

## Phase 2B：14 類別預測（10 min）

產出預測表（基於 Phase 2A 的對手 2 週排名 + 我方 2 週排名）：

| 類別 | 預測 | 信心 | 我方 | 對手 | 理由 |
|------|------|------|------|------|------|
| HR | W | 高 | #5 | #12 | 結構性優勢 |

規則：
- 我方 #1-5 + 對手 #8-12 → **W 高**
- 我方 #1-5 + 對手 #4-7 → **W 中**
- 雙方都 #1-5 或都 #8-12 → **toss-up**（註明偏哪方）
- 我方 #8-12 + 對手 #1-5 → **L 高**
- **偶數週 IP/K/W/QS → 信心再降一級**（核心原則 #5）

整體預測：
- 中位估計（例：9W-5L）
- range（最差 7-7，最好 10-4）

## Phase 2C：下週準備行動清單（10 min）

整合 Phase 1B（球員狀態）+ Phase 1C（策略驗證）+ Phase 2B（預測）的結果，產出明確 4 類行動：

### (a) Lineup 調整
- 哪些打者本週要 active / 哪些 BN
- 哪些 SP 排哪天先發
- 守位死格警告（哪天 C/1B/SS 沒人）

### (b) FA 候選清單
- 從 `scan_summary` 拉本週候選
- 對 Phase 1B「結構性 cut 候選」標記替換目標
- 出價建議（FAAB $）+ 時機

### (c) 觀察項目
- 哪些球員下週要重點看（slump 中 / 趨勢下降 / news check 待結果）
- 哪些補強項目要驗證

### (d) 條件性 drop 候選
- 哪些球員「如果本週爆炸就 drop」（單場意外延續 / 趨勢下降）
- 列出明確觸發條件

### (e) 啟動新補強項目（如有）
- 寫進 CLAUDE.md `### 進行中補強行動` section
- 觸發 / 行動 / 預期 / 驗證日期 / 狀態

## Step 3：寫入 + Commit

### 寫入分工

| 檔案 | 內容 | 性質 |
|------|------|------|
| `daily-advisor/weekly-data/week-{N}.json` | `preview.predicted_outcome`（machine-readable）| 結構化 |
| `week-reviews.md` | 完整覆盤 + 預測 + 行動清單（human-readable）| 摘要 |
| `CLAUDE.md` | `### 進行中補強行動` section 更新 | 滾動狀態 |

### `predicted_outcome` JSON 格式
```json
{
  "strong": ["HR", "R", "RBI", ...],
  "toss_up": ["ERA", "WHIP", "W", "SV+H"],
  "weak": ["BB", "IP", "K"],
  "projected_record": "9W-5L (median), 7-7~10-4 range",
  "strategy": "保護 ERA/WHIP, Ragans 先 news check",
  "basis": "Week 2+3 rolling merge"
}
```

### Commit
1 個 commit 包含：JSON + week-reviews.md + CLAUDE.md（如更新）

## `week-reviews.md` 寫入格式

每週追加一段，格式如下：

~~~markdown
## Week {N} vs {對手名}

### 預測（{日期} 產出，2 週合併基礎）

**對手 2 週合併**：強 {類別}, 弱 {類別}
**我方 2 週合併**：強 {類別}, 弱 {類別}

| 類別 | 預測 | 信心 | 我方 | 對手 | 理由 |
|------|------|------|------|------|------|

整體：{projected_record}，{strategy}

#### 下週行動清單
**(a) Lineup 調整**：{...}
**(b) FA 候選**：{...}
**(c) 觀察項目**：{...}
**(d) 條件性 drop 候選**：{...}

### 覆盤（{日期} 回顧）

**戰績：{W-L-D}，{一句話概述}**

#### 預測對照
| 類別 | 預測 | 實際 | ✓/✗ | mine | opp | 歸因 |
|------|------|------|------|------|-----|------|

準確率：{correct}/{total}

#### 我方球員狀態（核心）
**撐場者**：{球員 + 週 stats vs 開季}
**拖累者分類**：
- slump 觀察：{球員 + 為何不行動}
- 結構性 cut 候選：{球員 + 雙年數據}
- 單場意外（news check）：{球員 + 傷勢/狀況}

#### 策略行動驗證
- {進行中項目 1}：{驗證結果 / 狀態更新}
- {進行中項目 2}：{...}

#### 對手強弱（簡短）
{1-2 行帶過，2 週合併排名}

#### 歸因分類（簡短）
- 我方結構弱：{類別}（驅動補強）
- 單場意外：{球員/類別}
- 對手強 / 對稱 / 波動：{類別列表}（不可控，不細究）

### 學到什麼
- {insight — 結構性發現 / 補強驗證 / 單週陷阱 / 雙週規律}
~~~

## 開季前 3 週的特殊規則

| 週次 | 規則 |
|------|------|
| **Week 1**（無歷史）| 跳過 Phase 1。Phase 2A 對手用「對手前一年（去年）數據」當參考，註明低信心 |
| **Week 2** | Phase 1 用 Week 1 單週，註明 single-week low confidence。所有歸因「波動」類別比例會偏高，正常 |
| **Week 3+** | 完整流程，2 週合併標準 |

## 流程時間預算（目標收斂在 60 分鐘）

| Phase | 時間 | 內容 |
|-------|------|------|
| Step 1+2 資料準備 | 3 min | 讀 JSON（含 `review.two_week_ranks`） |
| Phase 0 策略載入 | 5 min | CLAUDE.md 現況 |
| Phase 1A 戰績歸因 | 5 min | 14 類別 + 簡短分類 |
| Phase 1B 球員狀態 | 15-20 min | **核心**，含 news check |
| Phase 1C 策略驗證 | 5 min | 對 Phase 0 項目逐一檢核 |
| Phase 2A 對手摘要 | 3 min | 一張表 |
| Phase 2B 14 類別預測 | 5 min | |
| Phase 2C 行動清單 | 10 min | (a)~(e) |
| Step 3 寫入 commit | 5 min | |
| **合計** | **~60 min** | |

每 4 週的深度球員回顧 +20-30 min。
