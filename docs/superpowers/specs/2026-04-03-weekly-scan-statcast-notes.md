# Weekly Scan Statcast 升級 — 討論筆記

> 討論進行中，確定方案後轉為正式 spec。

## 核心目標

修復 prompt-data 脫節：prompt 要求 Claude 用 Statcast 指標評估 FA，但 data 只有 Yahoo 傳統 stats。

## 三層漏斗設計

### 第 1 層：Yahoo API 多角度撈 FA（去重）

```
AR rank（本季累計表現）
  打者 50 / SP 30 / RP 20

Lastweek（上週單週爆發）
  打者 30 / SP 20 / RP 10

%owned 升幅（市場訊號，3d 排序）
  打者 top 20 / SP top 20 / RP top 5

→ 去重 → 預估 ~100-130 人
```

三個角度互補：
- AR：Yahoo 認為整體最好的
- Lastweek：近期爆發但 AR 還沒反映的
- %owned 升幅：其他 GM 在搶但排名不一定高的

移除零替補位置專查（AR 打者 50 已涵蓋）。

### 第 2 層：Savant CSV 品質篩選

批次下載 4 個 Savant CSV（batter/pitcher × statcast/expected），用 name matching 比對第 1 層名單。

**RP 篩選**（已確認）：
- 核心 3 項（xERA / xwOBA allowed / HH% allowed）至少 2 項 >= P50
- 樣本量：賽季初 BBE < 30 以 2025 為主篩，2026 僅傾向參考
- SV+H 不參與篩選（第 1 層 %owned 已捕捉角色變動訊號）
- 預估通過：~5-10 人

**SP 篩選**（已確認）：
- 核心 3 項（xERA / xwOBA allowed / HH% allowed）至少 2 項 >= P40
- P40 門檻：xERA <= 4.64 / xwOBA allowed <= .332 / HH% allowed <= 42.2%
- 比 RP（P50）寬鬆，因為 SP 格數多（7-8 格）、最弱 SP 約在 P40-P50、FA 池品質差
- 樣本量：同 RP（BBE < 30 以 2025 為主）

**打者篩選**（已確認）：
- 核心 3 項（xwOBA / BB% / Barrel%）至少 2 項 >= P40
- P40 門檻：xwOBA >= .286 / BB% >= 7.0% / Barrel% >= 6.5%
- BB% 來源：Yahoo stats BB ÷ Savant CSV PA（零額外 API call）
- 門檻同 SP（P40），打者 10 格，FA 池品質有限
- 樣本量：同通用規則（BBE < 30 只看去年 / 30-50 兩年並看 / > 50 當季為主）

### 第 3 層：Claude 評估

通過第 2 層的球員附完整資料送 Claude：
- Statcast 品質指標 + 百分位 tag（2025 + 2026）
- 輔助指標
- 產量指標
- Yahoo 傳統 stats（計分類別參考）
- %owned + 3d/24h 變動
- BBE 樣本量

Claude 用 CLAUDE.md 評估框架做最終判斷。

## 已確認的改動

### FA RP 顯示欄位（第 3 層給 Claude）

對齊 CLAUDE.md RP 評估框架：
- 品質（核心）：xERA / xwOBA allowed / HH% allowed + 百分位 tag
- 輔助：Barrel% allowed / ERA / |xERA-ERA| 方向+幅度
- 產量：K/9 / IP/Team_G
- 加分項：SV+H（品質小輸也值得換，RP 只佔 2 格比率影響有限）
- 樣本量：BBE + 標記賽季初小樣本

### |xERA-ERA| 方向標記（已更新 CLAUDE.md）

- ERA < xERA = 運氣好，ERA 預期回升（負面）
- ERA > xERA = 運氣差，ERA 預期回降（撿便宜訊號）
- 幅度用百分位判斷（P70+ = 顯著）

### %owned 相關

- **快照時間**：07:00 → TW 15:10（waiver ET 3AM 處理後 10 分鐘）
  - 15:10 存快照為當天定值，07:00 / 19:30 讀快照做分析
  - 比較窗口精確：15:10 vs 15:10 = 精確 24h / 72h
  - 實作：fa_watch.py 加 `--snapshot-only` flag → cron 15:10
- **排序基準**：weekly_scan 用 3d，fa_watch 維持 24h
- **只保留升幅**：移除降幅排行（12 隊 drop 的通常真的不好）
- **按位置分開**：打者 / SP / RP 分開排行

### 我方陣容加 prior_stats 摘要

從 roster_config.json 的 prior_stats 讀取，讓 Claude 有比較基準。不打 API。

### RP 評估邏輯更新（已更新 CLAUDE.md）

- SV+H 從產量拆為獨立加分項
- 品質小輸 + SV+H 也值得換（RP 只佔 2 格，比率影響有限；SV+H 獨立類別門檻低）
- 維持 2 位 RP 上限

## 尚未討論

- [x] SP 第 2 層：核心 3 項至少 2 項 >= P40（比 RP 寬鬆）
- [x] SP 第 3 層：品質（xERA / xwOBA / HH% + tag）+ 輔助（Barrel% / ERA / |xERA-ERA| 方向）+ 產量（IP/GS）+ BBE
- [x] 打者第 2 層：xwOBA / BB% / Barrel% 至少 2/3 >= P40（BB% = Yahoo BB ÷ Savant PA）
- [x] 打者第 3 層：xwOBA / BB% / Barrel% / HH% / OPS / PA/Team_G + 百分位 tag + BBE
- [x] 產量指標來源：通過第 2 層的 ~20-30 人，用 Savant 匹配的 mlb_id 查 MLB Stats API（2025 + 2026 兩年）。打者算 PA/Team_G，SP 算 IP/GS，RP 算 K/9 + IP/Team_G。2025 分母用 162，2026 分母用球隊實際已打場次。
- [x] 2026 PA/Team_G 分母：`/api/v1/standings?leagueId=103,104&season=2026` → 每隊 `gamesPlayed`，1 次 API call 拿全部 30 隊
- [x] 我方陣容 prior_stats 摘要格式：
  - 從 roster_config.json 讀取，零 API call
  - 投打分開，由弱到強排序
  - 打者排序用 xwOBA，隱藏前 5（Claude 只看可能被替換的 7 人）
  - SP 排序用 xERA，隱藏前 3（Claude 只看可能被替換的 6 人）
  - RP 全列（只有 2 人）
  - 打者欄位：xwOBA / BB% / Barrel% / HH% / OPS / PA/Team_G
  - SP 欄位：xERA / xwOBA / HH% / Barrel% / ERA / IP/GS
  - RP 欄位：xERA / xwOBA / HH% / Barrel% / ERA / K/9 / IP/Team_G / SV+H
- [x] 兩階段匹配策略：
  - 第 2 層篩選：name matching（快，0 API call，覆蓋 ~95%）
  - 通過篩選的 ~20-30 人：search_mlb_id 拿精確 mlb_id → 用 mlb_id 從 Savant CSV 重取精確數據 + 查 MLB Stats API 產量指標
  - name matching 失敗但在 %owned 升幅 top 的：也查 mlb_id 補救
  - 仍查不到：標記「無 Statcast」，只顯示 Yahoo stats
- [x] prompt_weekly_scan.txt 已更新：加入 RP 規則、資料結構說明、BBE 加權、比較指引、運氣方向、移除降幅
- [ ] fa_watch.py 同樣缺口（先做 weekly_scan，之後複用）
