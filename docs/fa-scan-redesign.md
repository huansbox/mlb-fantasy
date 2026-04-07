# FA Scan 重新設計（討論中）

> 暫時性文檔，記錄 fa_scan 整合討論的方向和結論。完成後整理進 CLAUDE.md。

## 核心目的

**在別人搶走之前，找到比我陣容最弱球員更好的 FA。**

## 整合方向

- `fa_scan.py`（唯一 FA 分析入口，由 weekly_scan.py 改名）
- fa_watch.py 廢棄，功能併入 fa_scan.py
- `/waiver-scan` skill 維持手動按需（WebSearch 新聞面 + 深度搜尋）

### 執行模式

| 模式 | 頻率 | 內容 |
|------|------|------|
| （預設） | 每天 | Batter + SP 完整掃描（Step A/B/C） |
| `--rp` | 僅週一 | RP 獨立掃描，和 weekly review 一起處理 |
| `--snapshot-only` | 每天 TW 15:15 | 只存 %owned 快照到 fa_history.json |
| `--cleanup` | 可選 | 自動清理 waiver-log 已被搶球員 |

---

## 每日掃描流程（Batter + SP）

```
┌─ 並行 ──────────────────────────────────────┐
│                                              │
│  Step A: 撈 FA 候選                           │  Step B: Claude Pass 1
│                                              │  從我方陣容挑最弱
│  1. Layer 1: Yahoo API + %owned risers        │
│  2. Layer 2: Savant 品質篩                     │  打者 → 挑最弱 4 人
│  3. Layer 3: 充實（MLB Stats + Savant）        │  SP → 挑最弱 3 人
│  4. waiver-log watch 球員直接帶數據進 pool      │
│                                              │
└──────────────────┬───────────────────────────┘
                   ↓
           Step C: Claude Pass 2（打者/SP 分開）
           FA 候選 + watch 名單 vs 最弱球員
           輸出：取代 / 觀察 / pass
```

---

## Step A：撈 FA 候選

### Batter

**Layer 1：FA 池撈取**
- Yahoo AR sort top 50 打者（市場熱門度，Yahoo 黑箱綜合排名）
- Yahoo biweekly sort top 30 打者（近兩週表現排序）
- 3d %owned 上升最多 top 20 打者（fa_history.json）
- 去重（包含去重 waiver-log watch 球員）

**Layer 2：品質篩選**
- 2/3 2026 核心指標通過 P40：xwOBA ≥ 0.286 / BB% ≥ 7.0% / Barrel% ≥ 6.5%
- 必須有 2026 Savant 數據（無則跳過）

**Layer 3：充實**
- 2026 MLB Stats（G, PA, OPS, HR, BB%）+ Savant（xwOBA, HH%, Barrel%）
- 2025 Savant（prior context）
- 衍生：PA/Team_G、BB%

### SP

**Layer 1：FA 池撈取**
- Yahoo AR sort top 30 SP（市場熱門度）
- Yahoo biweekly sort top 30 SP（近兩週表現，涵蓋 ~2 場先發）
- 3d %owned 上升最多 top 20 SP（fa_history.json）
- 去重（包含去重 waiver-log watch 球員）

**Layer 2：品質篩選**
- 2/3 2026 核心指標通過 P40：xERA ≤ 4.64 / xwOBA allowed ≤ 0.332 / HH% allowed ≤ 42.2%
- 必須有 2026 Savant 數據（無則跳過）

**Layer 3：充實**
- 2026 MLB Stats（ERA, IP, GS, K, W）+ Savant（xERA, xwOBA, HH%, Barrel%）
- 2025 Savant（prior context）
- 衍生：IP/GS（game log 版，只算 gamesStarted=1）、xERA-ERA 運氣標記（正=運氣好小心，負=運氣差撿便宜）

### waiver-log watch 球員

- 跳過 Layer 1-2（已被判定值得追蹤）
- 直接用 mlb_id 跑 Layer 3 充實，帶最新數據進 Pass 2 pool

---

## Step B：Claude Pass 1 — 挑最弱球員

**輸入**：我方陣容，按單一指標排序，隱藏最強展示其餘
- 打者：按 xwOBA 排序，隱藏前 5 強
- SP：按 xERA 排序，隱藏前 3 強
- 附 2026 Savant 數據 + 百分位標籤

**Claude 輸出**（打者/SP 分開呼叫）：
- 打者最弱 4 人（理由只考慮：Savant 數據（優先）+ 對 SB 以外的打者 6 類別貢獻（次要））
- SP 最弱 3 人（理由只考慮：Savant 數據（優先）+ 對 W、SV+H 以外的投手 5 類別貢獻（次要））

共 4 次 Claude 呼叫：Pass 1 打者 + Pass 1 SP + Pass 2 打者 + Pass 2 SP

---

## Step C：Claude Pass 2 — 比較與決策

**輸入**：
- Pass 1 挑出的最弱球員（打者 4 + SP 3），附完整數據
- FA 候選（Step A Layer 3 後），附完整數據
- waiver-log watch 球員，附最新 Layer 3 數據
- %owned 升幅排行（只有升幅，無降幅）
- waiver-log 完整內容（觀察中 + 觸發條件）

**Claude prompt 比較邏輯**：

打者（FA vs 我方最弱 4 人）：
- 核心 3 指標（xwOBA / BB% / Barrel%），2 項勝出 = 值得行動
- 守位需求（填什麼位？零替補位置風險？）
- PA/Team_G 產量（上場率）
- 引用 CLAUDE.md 評估框架

SP（FA vs 我方最弱 3 人）：
- 核心 3 指標（xERA / xwOBA allowed / HH% allowed），2 項勝出 = 值得行動
- IP/GS 產量（深投型 > 短局型）
- xERA-ERA 運氣標記（負值 = 撿便宜訊號）
- 引用 CLAUDE.md 評估框架

**Claude 輸出**（逐人）：
- **取代** — 明確優於最弱球員 → add/drop 建議 + FAAB 出價
- **觀察** — 有潛力但需確認 → 寫入 waiver-log + 觸發條件
- **pass** — 不優於現有球員 → 不動

**額外輸出**：
- waiver-log watch 球員觸發條件判斷（接近？達成？）
- %owned 急升警報（快被搶的球員）

---

## 週一 RP 掃描（`--rp`）

獨立於每日掃描，和 weekly review 一起處理。

**Layer 1：FA 池撈取**
- biweekly sort top 10 RP（Yahoo API）
- yahoo rank top 10 RP（Yahoo API）
- 7d %owned 上升最多 top 10 RP（fa_history.json）
- 去重 + 只留 biweekly SV+H ≥ 2

**Layer 2：品質篩選**
- 有 2026 Savant → xERA > P50（< 4.33）
- 無 2026 Savant → 自動通過（靠 Layer 1 的 SV+H 把關）

**比較邏輯（FA vs 我方 2 RP，單次 Claude）**：
- SV+H 產量 > 我方 RP
- Savant 品質不比我方 RP 差太多（2026 為主，2025 為輔）
- 品質小輸也值得換（SV+H 獨立類別價值 > 比率微降損失）

biweekly SV+H ≥ 2 為滾動兩週窗口，全球季適用，不需動態調整門檻。

---

## 輸出

- Telegram 推送（精簡版）
- GitHub Issue 存檔（完整 raw data + Claude 分析）
- label：`fa-scan`（統一取代原本的 `waiver-scan` + `fa-watch`）

---

## 全域修正項目

- [ ] **|xERA-ERA| → xERA-ERA**：所有程式碼中的運氣標記改為帶正負號單一值（正=運氣好小心，負=運氣差撿便宜）。涉及：weekly_scan.py、daily_advisor.py、roster_stats.py、CLAUDE.md 百分位表
- [ ] **%owned 降幅移除**：format_change_rankings() 和 _format_owned_risers() 中的降幅段落刪除，只保留升幅
- [ ] **CLAUDE.md 待辦取消**：「RP SV+H ≥ 2 門檻動態化」不再需要（biweekly 滾動窗口全季適用）

---

## 排程

| 時間 (TW) | UTC | 頻率 | 腳本 |
|-----------|-----|------|------|
| 12:30 | 04:30 | 每天 | `fa_scan.py`（預設模式，Batter + SP） |
| 13:00 | 05:00 | 週一 | `weekly_review.py --prepare`（讀 fa_scan 結果） |
| 13:00 | 05:00 | 週一 | `fa_scan.py --rp`（RP 掃描） |
| 15:15 | 07:15 | 每天 | `fa_scan.py --snapshot-only`（%owned 快照） |

廢棄：fa_watch.py TW 07:00 cron

## 錯誤處理

**原則**：打者和 SP 是獨立流程，一邊失敗不影響另一邊。共用資源（Savant CSV、Yahoo API）失敗則全部中斷。

| 失敗點 | 處理 |
|--------|------|
| Layer 1/2/3（Savant 下載、Yahoo API） | 全部中斷，Telegram + Issue 回報 |
| Pass 1 打者失敗 | 跳過 Pass 2 打者，SP 繼續。fallback：用程式碼排序 bottom 4 |
| Pass 1 SP 失敗 | 跳過 Pass 2 SP，打者繼續。fallback：用程式碼排序 bottom 3 |
| Pass 2 打者/SP 失敗 | 回報該組失敗，另一組結果正常輸出 |

**通知**：
- Telegram：`[fa_scan] {步驟名} 失敗：{錯誤摘要}`
- GitHub Issue：label `fa-scan-error`，body 含完整 traceback + 已完成步驟的 partial data

## 其他設計決策

- **waiver-log 存 mlb_id**：寫入時格式 `### 球員名 (隊伍, 位置) [mlb_id:123456]`
- **Layer 2 為空時**：若有 watch list → 只跑 watch 比較；無 watch list → 回報「無候選」，不跑 Claude
- **--cleanup**：嵌入每日掃描（Step A 前自動清理），`--cleanup` flag 保留作手動 override
- **百分位表**：維持 2025，Week 6-8 更新為 2026（腳本 `calc_percentiles_2026.py` 已備好）

## 待討論

- [ ] Pass 1 / Pass 2 的 prompt 具體內容（實作時再定）
- [ ] Telegram 推送格式（試跑後再定）
