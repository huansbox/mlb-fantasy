# Weekly Review — 週覆盤 + 週預測

每週一執行。Phase 1 覆盤上週，Phase 2 預測本週。

## Step 1：讀取資料

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

## Step 2（Phase 1）：覆盤上週

> 如果是開季第一週（無上週資料），跳過 Phase 1，直接進 Phase 2。

1. 從 JSON `review` 區塊讀取 14 類別 mine/opp/result
2. 從 `week-reviews.md` 讀取上週的 predicted_outcome（strong/toss_up/weak 分類）
3. 顯示對照表：

   | 類別 | 預測 | 實際 | ✓/✗ | mine | opp |
   |------|------|------|------|------|-----|

4. 計算準確率（correct / total）
5. 顯示聯盟類別排名（league_category_ranks）
6. **球員表現分析**（從 `review.my_roster_performance`）：
   - 打者：列出當週 PA/R/HR/RBI/SB/BB/AVG/OPS + 開季 xwOBA/BB%/Barrel% 百分位
   - SP：列出當週 GS/IP/W/K/ERA/WHIP/QS + 開季 xERA/xwOBA allowed 百分位
   - 標記「撐場者」（當週貢獻突出）和「拖累者」（當週表現遠低於開季水準或空白）
   - 結合類別勝負：哪些球員直接影響了哪些類別的 W/L
7. 掃描日報品質（用 `gh issue view {number}` 讀取 daily_reports 中的 issues）：
   - 速報 → 最終報推翻次數及類型
   - 「Lineup 未公布」出現比例
8. **詢問用戶**：預測偏差的原因（逐項標記或整體說明）
9. 寫入 `week-reviews.md` 的覆盤區塊

## Step 3（Phase 2）：預測本週

1. 從 JSON `preview` 區塊讀取：
   - 對手陣容（batters + pitchers，標注 IL）
   - 雙方 SP 排程（confirmed / 推估）
   - 守位覆蓋 + dead_slots
2. 顯示分析：
   - 對手打者/投手陣容摘要
   - SP 排程對比表（我方 vs 對手）
   - **守位死格警告**（哪天 C/1B/SS 沒人）
3. 產出 14 類別預測：
   - 結合覆盤 insight（若有）
   - 分 strong / toss_up / weak + 信心度 + 一句話理由
   - 整體預測比分 + 策略建議（攻擊/保守/正常）
4. **詢問用戶**：確認或修正策略
5. 將 predicted_outcome 寫回 JSON 的 `preview.predicted_outcome`：
   ```json
   {
     "strong": ["HR", "IP", "K", ...],
     "toss_up": ["R", "W", ...],
     "weak": ["SB", "SV+H"],
     "projected_record": "10-4",
     "strategy": "正常打，保護比率"
   }
   ```
6. 寫入 `week-reviews.md` 的預測區塊
7. Commit JSON + week-reviews.md

## Step 4（FA 行動決策）：整合 Scan 建議

> 若 JSON 中無 `review.scan_summary`（scan 未跑或非本週），跳過此步驟。

1. 讀 `review.scan_summary.analysis`（weekly_scan 的 Claude 分析摘要）
2. 交叉比對：
   - Phase 1 發現的拖累者 → 哪個位置需要補強？
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

### 預測（{日期} 產出）
| 類別 | 預測 | 信心 | 理由 |
|------|------|------|------|
| R | W | 中 | 我方打線較深 |
| ...

整體：{projected_record}，{strategy}

### 覆盤（{日期} 回顧）
| 類別 | 預測 | 實際 | ✓/✗ | 偏差原因 |
|------|------|------|------|---------|
| WHIP | W | L | ✗ | Nola@Coors |
| ...

準確率：{correct}/{total}（{pct}%）

#### 球員表現
- 撐場者：{球員} — {原因}
- 拖累者：{球員} — {原因}

### 日報品質
- 速報→最終報推翻：{N} 次（{類型}）
- Lineup 未公布比例：速報 {N}%
- Prompt 調整建議：{建議或「無」}

### FA 行動
- {決策：立即行動/深入評估/繼續觀察}
- {具體建議或「本週無明確升級」}

### 學到什麼
- {insight}
~~~
