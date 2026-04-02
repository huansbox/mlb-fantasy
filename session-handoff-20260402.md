# Session Handoff — 2026-04-02

> 下個 session 先讀這份，再讀 `CLAUDE.md`。
> 完整架構地圖見 `file-dependencies.md`。

## 本次 Session 完成事項

### 核心：檔案依賴整理 + 系統整合

本次 session 的主要工作是全面盤點專案檔案間的依賴關係，消除資訊重複和同步斷裂。

**1. CLAUDE.md 全面改造**（376 → 252 行，`97a11d1`）
- 移除 11 個過時區段（選秀分析、Week 1 複盤、Watchlist、行動觸發規則等）
- 陣容改為核心 3 人（Skubal/Chisholm/Machado）+ 連結 `roster_config.json`
- 評估框架統一為打者/SP/RP 三段（唯一定義，skills 引用不複製）
- 文件結構 + 每週 SOP 合併為「賽季運營 SOP」

**2. 球員評估框架重新設計**
- 打者核心 3 指標：xwOBA / BB% / **Barrel%**（原 HH% 降為輔助）
- 打者產量指標：**PA / Team_G**（新增）
- SP 核心 3 指標：xERA / xwOBA allowed / **HH% allowed**（原 Barrel% 降為輔助）
- SP 產量指標：**IP/GS**（新增，用三級分類：<5.3 / 5.3-5.7 / >5.7）
- RP：同 SP 品質 + K/9 + IP/Team_G
- 打者排最弱 5 人 → FA 只跟這 5 人比；SP 排最弱 4 人；RP 直接比 2 人
- 移除所有固定門檻（原 xERA < P60 + IP > 180），改為百分位相對比較
- |xERA - ERA| 運氣標記改用百分位（原固定 0.50）

**3. 新百分位表計算**（`602873a`, `27f5fb1`）
- 從 2025 MLB 全季數據計算 5 個新指標：PA/Team_G、IP/GS、K/9(RP)、IP/Team_G(RP)、|xERA-ERA|(SP/RP)
- 已寫入 CLAUDE.md + main.py（RP_PCTILES 新 dict + pctile_tag RP 支援）

**4. roster_config.json 整合**（`97a11d1`）
- 更新名單：移除 Kwan/Littell，新增 Walker(STL)/Messick
- 移除 `role`、`type`、`proj` 欄位，投打統一用 `positions`
- 加 `faab_remaining` 到 league 區段

**5. Skills + prompt 檔更新**（`0d0331e`）
- player-eval / waiver-scan / roster-scan：評估標準改為引用 CLAUDE.md（不複製）
- waiver-scan：移除「同步 CLAUDE.md watchlist」指引
- prompt_fa_watch.txt：移除寫死的 Kwan 弱點，打者指標改為 xwOBA/BB%/Barrel%
- prompt_weekly_scan.txt：更新指標 + 百分位參考

**6. 腳本修復**（`c618f5e`，branch `refactor/config-schema`）
- yahoo_query.py：新增 `is_pitcher()` / `pitcher_type()` / `calc_position_depth()` helpers
- fa_watch.py：DAILY_QUERIES 改為動態計算零替補位置 + 動態風險摘要
- weekly_scan.py：同上
- main.py：config fallback 路徑 derive role/type from positions
- roster_stats.py / weekly_review.py：移除 role/type 直接讀取

**7. VPS 維護**
- git pull 同步
- gh CLI 認證修復（Fine-grained token）
- GitHub Issue labels 建立（fa-watch / waiver-scan / daily-report）

---

## 未完成 / 下次接手的待辦

### 功能開發

#### ~~1. roster_sync.py（新腳本）~~ ✅ 2026-04-03 完成
- `--init` bootstrap + daily cron（TW 15:10）已部署 VPS
- 23 人 yahoo_player_key + prior_stats（2025 Savant + MLB Stats）全部寫入
- transactions gate：只在有新 add/drop 時才更新，auto git push + Telegram 通知

#### ~~2. roster_config.json 補齊欄位~~ ✅ 2026-04-03 完成
- yahoo_player_key + prior_stats 已由 roster_sync.py --init 寫入

#### 3. weekly_scan.py 投手 Statcast
目前 weekly_scan 只餵傳統 stats（ERA/WHIP/K/IP）給 Claude，沒有 Savant 數據。
跟 fa_watch.py 的 Statcast 整合同理。

### 觀察中（賽季進行）

#### 4. Walker(STL) 開季驗證
- breakout 確認：xwOBA > P50 (.297) + HH% > P70 (44.7%)
- drop 評估：連 3 週 xwOBA < P25 (.261)

#### 5. Messick 開季驗證
Savant P80-90 是否持續。CLE 是否限制局數。

#### 6. Hancock 第二場（4/3-4/4 vs LAA）
觸發：xERA < P60 (4.04) + K/9 > 8 → drop Singer, add Hancock。
注意：Bryce Miller 回歸可能擠掉 Hancock rotation 位置。

#### 7. Canzone 後續
BN 有空位時撿當 RHP matchup 武器。13% owned 不急。

### VPS 待驗證

#### ~~8. 百分位標籤實測~~ ✅ 2026-04-03 完成
`--no-send` 測試通過，百分位標籤正常顯示。同時修復了 `--no-send` 仍建 GitHub Issue 的 bug。

---

## 系統架構快照

```
CLAUDE.md（策略大腦 + 評估框架唯一定義）
  ├─ 核心球員（3 人）+ 連結 roster_config.json
  ├─ 評估框架（打者/SP/RP）+ 百分位表
  ├─ 賽季運營 SOP
  └─ 讀取者：skills（/player-eval, /waiver-scan, /roster-scan）

roster_config.json（陣容唯一來源）
  ├─ 球員名 / mlb_id / positions / team
  ├─ 讀取者：全部 5 支腳本
  └─ 更新：add/drop 後手動改（未來由 roster_sync.py 自動化）

waiver-log.md（FA 追蹤唯一來源）
  ├─ 觀察中 / 條件 Pass / 已結案
  └─ 讀取者：fa_watch.py / weekly_scan.py / skills

file-dependencies.md（架構地圖）
  └─ 完整依賴關係 + 變更完成記錄 + 未完成清單
```

### 關鍵改動提醒（給下次 session 的 AI）

- **CLAUDE.md 不再有完整陣容表**——只有核心 3 人，完整名單在 roster_config.json
- **CLAUDE.md 不再有 Watchlist / 行動觸發規則**——在 waiver-log.md
- **評估框架在 CLAUDE.md 是唯一定義**——skills 引用不複製，改標準只改 CLAUDE.md
- **打者核心指標是 Barrel% 不是 HH%**，投手核心是 HH% allowed 不是 Barrel%（投打相反）
- **roster_config.json 沒有 role/type 欄位**——腳本用 `pitcher_type()` 從 positions 推導
- **fa_watch.py 的位置查詢是動態的**——從 config 算零替補位置，不是硬編碼
