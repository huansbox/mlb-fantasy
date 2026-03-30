# Weekly Review System Design

## 概述

週覆盤 + 週預測系統，由兩個元件組成：
1. **`weekly_review.py --prepare`**：VPS cron 自動準備資料，存 JSON 到 repo
2. **`/weekly-review` skill**：互動 session 中消費 JSON，執行覆盤 + 預測

## 目標

- 每週記錄 14 類別預測，下週覆盤對照 → 累積 prediction accuracy feedback loop
- 分析下週對手 → 產出策略建議
- 檢查守位覆蓋（C/1B/SS 死格風險）
- 掃描本週日報品質 → 必要時調整 prompt template

## 元件 1：資料準備腳本

### 檔案

`daily-advisor/weekly_review.py`

### 觸發

VPS cron，每週一 TW 18:00（UTC 10:00）。

### 輸出

`daily-advisor/weekly-data/week-{N}.json`

### JSON 結構

```json
{
  "week": 2,
  "dates": ["2026-03-30", "2026-04-05"],
  "generated": "2026-04-06T10:00:00Z",

  "review": {
    "categories": [
      {"name": "R", "mine": 18, "opp": 19, "result": "L"},
      {"name": "HR", "mine": 7, "opp": 5, "result": "W"},
      ...
    ],
    "final_record": {"wins": 10, "losses": 4, "draws": 0},
    "opponent_name": "鍋's Neat Team",
    "league_standings": [
      {"team": "99 940", "wins": 2, "losses": 0, "rank": 1},
      ...
    ],
    "league_category_ranks": {
      "R": 3, "HR": 1, "OPS": 2, ...
    },
    "daily_reports": [
      {"date": "2026-03-30", "issue_number": 4, "title": "[速報] Daily Report 2026-03-30"},
      ...
    ]
  },

  "preview": {
    "opponent_name": "BUMMER",
    "opponent_key": "469.l.105457.t.8",
    "opponent_roster": {
      "batters": [
        {"name": "Player A", "team": "NYY", "positions": ["LF","CF"], "role": "starter"},
        ...
      ],
      "pitchers": [
        {"name": "Pitcher A", "team": "NYY", "type": "SP"},
        ...
      ]
    },
    "my_sp_schedule": [
      {"date": "2026-04-06", "pitcher": "Tarik Skubal", "team": "DET", "vs": "St. Louis Cardinals", "confirmed": true},
      ...
    ],
    "opp_sp_schedule": [
      {"date": "2026-04-06", "pitcher": "Pitcher X", "team": "NYY", "vs": "Team Y", "confirmed": false},
      ...
    ],
    "probable_as_of": "2026-04-06T10:00:00Z",
    "positional_coverage": {
      "2026-04-06": {
        "players_with_games": ["Skubal", "Buxton", "Machado"],
        "players_no_game": ["Tovar", "Walker"],
        "dead_slots": ["SS", "1B"]
      },
      ...
    },
    "predicted_outcome": null
  }
}
```

`predicted_outcome` 在 prepare 階段為 null，由互動 skill 填入後 commit 回 repo。

### 資料來源與計算邏輯

| 欄位 | 來源 | 備註 |
|------|------|------|
| `review.categories` | Yahoo `/league/{key}/scoreboard;week={N-1}` | 回傳 12 隊 scoreboard，取自己的 matchup。保留每項的 mine/opp/result |
| `review.league_standings` | Yahoo `/league/{key}/standings` | 解析勝負場數和排名 |
| `review.league_category_ranks` | Yahoo `/league/{key}/scoreboard;week={N-1}`，取全 12 隊數據 | **需手動計算**：逐類別對 12 隊排序（counting stats 降序，ratio stats ERA/WHIP 升序） |
| `review.daily_reports` | `gh issue list --label week-{N-1} --json number,title,createdAt` | 只存 metadata，日報內容由 skill 按需讀取 |
| `preview.opponent_roster` | Yahoo `/team/{opp_key}/roster` | 沿用 main.py 的 roster 解析邏輯 |
| `preview.my_sp_schedule` | MLB Stats API `/schedule?hydrate=probablePitcher` + 上次先發日推算 | confirmed=true 只有 probable pitcher 已公布的。後半週多為 false |
| `preview.opp_sp_schedule` | 同上，針對對手 SP 所屬球隊 | |
| `preview.positional_coverage` | MLB Stats API `/schedule` × `roster_config.json` | 逐日判斷每位打者所屬球隊是否有比賽 → 有比賽的球員集合 → 對照 Yahoo 位置資格 → 找出無法填補的空槽（dead_slots） |

### dead_slots 計算邏輯

對每一天：
1. 列出當天有比賽的打者（球隊有比賽）
2. 對 C/1B/2B/3B/SS/LF/CF/RF 各槽位，檢查是否有至少一名有比賽的球員擁有該位置資格
3. 考慮 UTIL 槽（任何打者都能坐）和板凳（Frelick/Stanton）的遞補
4. 無法填補的槽位 = dead_slot

簡化版：只標記 C/1B/SS（已知單點風險位置），不做完整 lineup optimization。

### 執行後動作

```bash
git add daily-advisor/weekly-data/week-{N}.json
git commit -m "data: weekly review data for week {N}"
git pull --rebase origin master || echo "REBASE_FAILED" >> /var/log/weekly-review.log
git push origin master || echo "PUSH_FAILED" >> /var/log/weekly-review.log
```

push 失敗只 log，不中斷。下次 session git pull 時手動解決。

## 元件 2：互動 Skill

### 檔案

`.claude/commands/weekly-review.md`（skill 定義）

### 觸發

用戶在 Claude Code session 中執行 `/weekly-review`。

### Phase 1：覆盤（上週）

1. 讀 `daily-advisor/weekly-data/week-{N}.json` 的 `review` 區塊
2. 讀 `week-reviews.md` 中上週存的 `predicted_outcome`
3. 顯示：預測 vs 實際對照表（14 類別，標記 ✓/✗）
4. 掃描本週日報（`gh issue view` 按需讀取）找 prompt pattern：
   - 速報 → 最終報推翻次數及類型
   - 「Lineup 未公布」出現比例
5. 用戶標記偏差原因（互動輸入）
6. 寫入 `week-reviews.md` 的覆盤區塊

### Phase 2：預測（本週）

1. 讀同一 JSON 的 `preview` 區塊
2. 顯示：對手陣容 + SP 排程對比 + 守位死格
3. 產出 14 類別預測（strong / toss-up / weak）+ 整體策略建議
4. 用戶確認或修正策略
5. 將 `predicted_outcome` 寫回 JSON 的 `preview.predicted_outcome`：
   ```json
   {
     "strong": ["HR", "IP", "K", "ERA", "WHIP", "AVG", "OPS"],
     "toss_up": ["R", "W", "RBI", "QS", "BB"],
     "weak": ["SB", "SV+H"],
     "projected_record": "10-4",
     "strategy": "正常打，保護比率"
   }
   ```
6. 寫入 `week-reviews.md` 的預測區塊
7. Commit 兩個檔案（JSON + week-reviews.md）

### `week-reviews.md` 結構

```markdown
# 週對戰覆盤

## Week 2 vs 鍋's Neat Team

### 預測（2026-03-30 產出）
| 類別 | 預測 | 信心 | 理由 |
|------|------|------|------|
| AVG | W | 高 | .286 vs .182，結構性優勢 |
| WHIP | W | 中 | 1.29 vs 1.68，但 Nola@Coors 風險 |
| SB | L | 高 | 對手 Duran 有速度，punt |
| SV+H | L | 高 | 對手 5 RP，punt |
| ...

整體：10-4，正常打，保護比率

### 覆盤（2026-04-06 回顧）
| 類別 | 預測 | 實際 | ✓/✗ | 偏差原因 |
|------|------|------|------|---------|
| WHIP | W | L | ✗ | Nola@Coors 6.2IP/1.71WHIP |
| ...

準確率：12/14（85.7%）

### 日報品質
- 速報→最終報推翻：2 次（lineup 未公布相關）
- Lineup 未公布比例：速報 60%、最終報 10%
- Prompt 調整建議：無

### 學到什麼
- Coors 場 WHIP 風險需量化：WHIP 領先 < 0.15 時不上
```

## 元件 3：Weekly Scan 提醒

### 修改檔案

`daily-advisor/weekly_scan.py`

### 修改內容

在 Telegram 輸出尾巴追加一行：

```
---
📋 Week {N} 覆盤資料已備好，開 session 跑 /weekly-review
```

週數 N 從 `roster_config.json` 的 fantasy week 計算取得。

## Cron 排程

| Job | 時間 (TW) | UTC | Cron 表達式 |
|-----|----------|-----|------------|
| **weekly_review.py --prepare** | 週一 18:00 | 10:00 | `0 10 * * 1` |
| weekly_scan.py（已有） | 週一 19:30 | 11:30 | `30 11 * * 1` |

## 檔案清單

| 檔案 | 動作 | 說明 |
|------|------|------|
| `daily-advisor/weekly_review.py` | 新增 | 資料準備腳本 |
| `.claude/commands/weekly-review.md` | 新增 | 互動 skill 定義 |
| `daily-advisor/weekly-data/` | 新增目錄 | 存放 week-N.json |
| `week-reviews.md` | 新增 | 累積式覆盤記錄 |
| `daily-advisor/weekly_scan.py` | 修改 | 尾巴加提醒 |
| `/etc/cron.d/daily-advisor`（VPS） | 修改 | 加一行 cron |
| `CLAUDE.md` | 修改 | 文件表格加新檔案 |
| `README.md` | 修改 | 排程表加 weekly_review |

## 不做的事

- 不做完整 lineup optimization（dead_slots 只標記 C/1B/SS 單點風險）
- 不自動推 Telegram 週報（預測需要人的 input）
- 不做聯盟排名趨勢圖（月更時手動看即可）
- 不串接 waiver-scan（兩個系統獨立，覆盤中發現的問題手動觸發 waiver-scan）
