# Weekly Review — 週覆盤 + 週預測

每週一執行。Phase 1 覆盤上週，Phase 2 預測本週。

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

若 JSON 不存在，提示用戶：
- VPS 上跑：`ssh root@107.175.30.172 'cd /opt/mlb-fantasy && python3 daily-advisor/weekly_review.py --prepare'`
- 或本地即時拉取：`python daily-advisor/weekly_review.py --prepare --dry-run > daily-advisor/weekly-data/week-{N}.json`

## Step 2：取近 2 週聯賽合併排名

使用 `_merge_weeks.py` 取得 Week N-1 + N-2 的 14 類別合併數據和各隊排名（其中 N = 當前週）。

```bash
# 先把最新版本 scp 到 VPS（若本地有改動）
scp daily-advisor/_merge_weeks.py root@107.175.30.172:/opt/mlb-fantasy/daily-advisor/_merge_weeks.py

# 在 VPS 跑（本機無 Yahoo token）
ssh root@107.175.30.172 'export PATH=/root/.local/bin:$PATH && cd /opt/mlb-fantasy/daily-advisor && python3 _merge_weeks.py'
```

腳本預設抓 Week 2+3。若要抓其他週次，修改腳本最下方的 `fetch_week(league_key, token, 2/3)` 或改為參數化。

> **開季第 2 週例外**：只能用 Week 1 單週數據，註明信心低。所有歸因和預測都加 `(single-week, low confidence)` 標記。

輸出會包含：
- 每隊 14 類別合併值（counting 加總；AVG/OPS 按 AB 加權；ERA/WHIP 按 IP 加權）
- 我方和對手在每個類別的聯賽排名對比

**把這份排名表存起來，Phase 1 歸因和 Phase 2 預測都會引用**。

## Step 3（Phase 1）：覆盤上週

> 如果是開季第一週（無上週資料），跳過 Phase 1，直接進 Phase 4（Phase 2 預測）。

1. 從 JSON `review` 區塊讀取 14 類別 mine/opp/result
2. 從 `week-reviews.md` 讀取上週的 predicted_outcome（strong/toss_up/weak 分類）
3. 顯示對照表：

   | 類別 | 預測 | 實際 | ✓/✗ | mine | opp |
   |------|------|------|------|------|-----|

4. 計算準確率（correct / total）
5. 顯示 **雙視角** 排名：
   - **單週排名**（從 JSON `review.league_category_ranks`）— 參考
   - **2 週合併排名**（從 Step 2）— **歸因主依據**

6. 球員表現分析（從 `review.my_roster_performance`）：
   - 打者：列出當週 PA/R/HR/RBI/SB/BB/AVG/OPS + 開季 xwOBA/BB%/Barrel% 百分位
   - SP：列出當週 GS/IP/W/K/ERA/WHIP/QS + 開季 xERA/xwOBA allowed 百分位
   - 標記「撐場者」（週產出突出 vs 開季水準）和「拖累者」（週產出遠低於開季水準或空白）
   - **只看 counting stats + 品質指標**，禁止引用 selected_pos 做失誤判斷

7. **對表現異常者執行 news check**（拖累者優先，特別是週表現與開季品質嚴重背離者）：
   - 例：開季 xwOBA >P90 的打者週 OPS <.400；開季 xERA P70+ 的 SP 週 ERA >10.00
   - 查該球員當週先發/出賽對應的最終報：`gh issue view {issue_number} -R huansbox/mlb-fantasy`
   - 若最終報無相關提醒 → WebFetch 最新傷勢 / 狀況報導
   - 歸類標註：「傷勢（XX）」/「被打下場」/「對戰特殊」/「無消息純波動」

8. **歸因分類**（對每項預測偏差 W/L 都要分類，即使預測準了也要分析贏/輸原因）：

   針對每個類別，回答 4 個問題：
   - (a) 對手近 2 週該類別聯賽排名是多少？
   - (b) 我方近 2 週該類別聯賽排名是多少？
   - (c) 單週實際差距是小/中/大？
   - (d) 有無 news check 發現的單場意外？

   分類規則：
   - 對手 2 週 #1-3 + 我方 #6+ → **對手結構強**（下週換對手可解）
   - 我方 2 週 #10-12 + 對手 #6- → **我方結構弱**（要補強）
   - 雙方都 #1-3 或都 #10-12 → **對稱變異**（近戰險輸贏）
   - 有 news check 確認意外 → **單場意外**
   - 單週極端值但 2 週合併中段 → **單週波動**

   **⚠️ 重要**：不要單看上週數據就說「對手 ERA #1」或「我方 BB #10」。單週排名可能被極端值拉動。**必須用 2 週合併排名**。

9. 掃描日報品質（用 `gh issue view {number}` 讀取 daily_reports 中的 issues）：
   - 速報 → 最終報推翻次數及類型
   - 「Lineup 未公布」出現比例
   - 這步可以只做抽樣（選 2-3 份異常日的速報+最終報對照），不必全讀

10. **詢問用戶**：對歸因分類或偏差原因有無補充或修正（特別是我無法從資料看到的 context：球員傷勢細節、對戰特殊因素、策略調整）

11. 寫入 `week-reviews.md` 的覆盤區塊

## Step 4（Phase 2）：預測本週

1. 從 JSON `preview` 區塊讀取：
   - 對手陣容（batters + pitchers，標注 IL）
   - 雙方 SP 排程（confirmed / 推估）
   - 守位覆蓋 + dead_slots

2. **雙週規律檢查**：
   - 當前是奇數週還是偶數週？
   - 查我方 SP 排程確認 Skubal/Sale 各幾場
   - 偶數週 → Phase 2 預測中 IP/K/W/QS 的信心自動降級

3. 對手分析（**基於 Step 2 的 2 週合併排名**）：
   - 對手陣容摘要
   - 對手近 2 週 14 類別強項（#1-5）和弱項（#9-12）
   - SP 排程對比表（我方 vs 對手）
   - 守位死格警告（哪天 C/1B/SS 沒人）

4. 產出 14 類別預測表：

   | 類別 | 預測 | 信心 | 我方 2 週排名 | 對手 2 週排名 | 理由 |
   |------|------|------|--------------|--------------|------|
   | HR | W | 高 | #5 | #12 | 結構性優勢 |
   | ... |

   規則：
   - 我方 2 週排名 #1-5 + 對手 #8-12 → **W 高信心**
   - 我方 #1-5 + 對手 #4-7 → W 中信心
   - 雙方都 #1-5 或都 #8-12 → **toss-up**（註明偏哪方）
   - 我方 #8-12 + 對手 #1-5 → **L 高信心**
   - 偶數週 IP/K/W/QS → 再降一級信心

5. **整體預測比分**：
   - 中位估計（例：9W-5L）
   - range（最差 7-7，最好 10-4）
   - 策略建議（攻擊/保守/正常 + 關鍵行動點）

6. **詢問用戶**：確認或修正策略

7. 將 predicted_outcome 寫回 JSON 的 `preview.predicted_outcome`：
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

8. 寫入 `week-reviews.md` 的預測區塊

9. Commit JSON + week-reviews.md

## Step 5（FA 行動決策）：整合 Scan 建議

> 若 JSON 中無 `review.scan_summary`（scan 未跑或非本週），跳過此步驟。

1. 讀 `review.scan_summary.analysis`（weekly_scan 的 Claude 分析摘要）
2. 交叉比對：
   - Phase 1 「我方結構弱」的類別 → 哪個位置需要補強？（只有「結構弱」驅動補強，「對手強」或「單場意外」不驅動）
   - Phase 2 預測的弱項類別 → FA 候選能改善哪些？
   - scan 推薦的候選 → 是否比現有最弱球員更好？
3. 決策輸出（三選一）：
   - **立即行動**：候選明確優於拖累者 → 列出 add/drop 建議 + FAAB 出價
   - **深入評估**：候選有潛力但需確認 → 建議跑 `/player-eval {球員名}`
   - **繼續觀察**：本週無明確升級 → 不動
4. 將決策寫入 `week-reviews.md` 的 FA 行動區塊

## `week-reviews.md` 格式

每週追加一段，格式如下：

~~~markdown
## Week {N} vs {對手名}

### 預測（{日期} 產出，2 週合併基礎）

**近 2 週合併排名對比**：
- 我方強項：{類別 + 排名}
- 我方弱項：{類別 + 排名}
- 對手強項：{類別 + 排名}
- 對手弱項：{類別 + 排名}

| 類別 | 預測 | 信心 | 我方 | 對手 | 理由 |
|------|------|------|------|------|------|
| R | W | 中 | #2 | #5 | 我方打線較深 |
| ...

整體：{projected_record}，{strategy}

### 覆盤（{日期} 回顧）

**戰績：{W-L-D}，{一句話概述}**

#### 預測對照 + 歸因
| 類別 | 預測 | 實際 | ✓/✗ | mine | opp | 歸因（對手強/我方弱/對稱/意外/波動）|
|------|------|------|------|------|-----|--------|
| WHIP | Toss | L | ✗ | 1.42 | 1.13 | 單週波動（2 週合併對手 #11）|
| ...

準確率：{correct}/{total}（{pct}%）

#### 聯盟排名（雙視角）
- **單週**：{我方本週排名}
- **2 週合併**：{我方近 2 週排名}
- **真實結構性弱項**（2 週 #10-12）：{列出}

#### 球員表現
- 撐場者：{球員 + 週 stats vs 開季}
- 拖累者：{球員 + 週 stats vs 開季}
- News check 結果：{有傷勢/無消息等}

#### 歸因分類
- **對手結構強**（近 2 週 #1-3）：{類別列表}
- **我方結構弱**（近 2 週 #10-12）：{類別列表，這才要補強}
- **對稱變異**：{類別}
- **單場意外**：{球員 + 傷勢/狀況}
- **單週波動**：{類別}

### 日報品質
- 速報→最終報推翻：{N} 次（{類型}）
- Lineup 未公布比例：速報 {N}%
- Prompt 調整建議：{建議或「無」}

### FA 行動
- {決策：立即行動/深入評估/繼續觀察}
- {具體建議或「本週無明確升級」}

### 學到什麼
- {insight — 強調結構性發現 vs 運氣 / 雙週規律驗證 / 單週陷阱}
~~~
