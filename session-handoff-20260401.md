# Session Handoff — 2026-04-01

> 本份 handoff 的待辦已於 2026-04-02 session 大部分完成。
> 當前系統狀態見 `CLAUDE.md`（唯一策略來源）+ `file-dependencies.md`（架構地圖）。

## 已完成（2026-04-02 session 處理）

### 高優先

- [x] **#1 roster_config.json 同步** — 移除 Kwan/Littell，新增 Walker(STL)/Messick，移除 role/type/proj 欄位，投打統一 positions（`97a11d1`）
- [x] **#2 fa_watch.py 弱點位置硬編碼** — 改為 `build_position_queries()` + `calc_position_depth()` 動態計算（`c618f5e`）
- [x] **#3 prompt_fa_watch.txt 位置深度** — `build_fa_watch_data()` 新增「零/薄替補位置 FA」段落，移除寫死的 Kwan 弱點（`0d0331e`）

### 中優先

- [x] **#7 百分位標籤驗證** — pctile_tag() 已擴充（新增 RP_PCTILES、bb_pct、pa_per_tg 等），VPS 已 pull 但尚未跑 `--no-send` 實測

### 額外完成（04-02 session 自行發起）

- [x] CLAUDE.md 全面改造（376→252 行）：移除 11 個過時區段，統一評估框架（打者/SP/RP），合併 SOP
- [x] 新百分位表計算：PA/Team_G、IP/GS（三級）、K/9、IP/Team_G(RP)、|xERA-ERA|
- [x] 3 個 Skills + 2 個 prompt 檔改為引用 CLAUDE.md（不複製）
- [x] 5 支腳本修復 role/type 依賴 + 動態位置查詢
- [x] VPS git pull + gh CLI 認證修復 + GitHub Issue labels 建立
- [x] `file-dependencies.md` 完整架構地圖

## 未完成

### 觀察中（賽季進行，非 code 任務）

- [ ] **#4 Walker(STL) 開季驗證** — breakout 確認（xwOBA > P50 + HH% > P70）或 drop 評估（連 3 週 xwOBA < P25）。已記到 CLAUDE.md 待辦
- [ ] **#5 Messick 開季驗證** — Savant P80-90 是否持續，CLE 是否限制局數
- [ ] **#6 Hancock 第二場**（4/3-4/4 vs LAA）— 觸發：xERA < P60 + K/9 > 8 → drop Singer。注意 Bryce Miller 回歸可能擠掉 rotation
- [ ] **#9 Canzone 後續** — BN 有空位時撿當 RHP matchup 武器，13% owned 不急

### 功能開發（下次 session）

- [ ] **#8 weekly_scan.py 投手 Statcast** — 目前只餵傳統 stats 給 Claude，沒有 Savant 數據
- [ ] **roster_sync.py 新腳本** — Yahoo API 自動同步陣容 + mlb_id 查詢 + prior_stats 寫入
- [ ] **roster_config.json 補齊** — yahoo_player_key + prior_stats 欄位（依賴 roster_sync.py）

## 04-01 Session 完成事項（原始記錄）

### 程式碼

1. 投手 Statcast 整合（`feat/pitcher-statcast` → merged）
2. 投手評估框架統一（`feat/pitcher-eval-framework` → merged）
3. 百分位表升級（4 格 → 9 格）
4. 百分位自動標籤（`feat/pctile-tags` → merged）

### 陣容異動

| Out | In | 理由 |
|-----|-----|------|
| Zack Littell (WSH, SP) | Parker Messick (CLE, SP) | WSH 弱隊 + 低 K + xERA P50 vs Savant P80-90 |
| Steven Kwan (CLE, LF) | Jordan Walker (STL, LF/RF) | HH% <P25 / Barrel% <P25 vs HH% >P90 breakout 候選 |

### 發現 / 洞見

- Canzone 舊框架 Pass 在新 Statcast 框架下翻轉（三項 >P90），但確認硬 platoon
- Kwan 87% rostered 是市場慣性，Statcast 底層
- 3 agent 評審模式有效
