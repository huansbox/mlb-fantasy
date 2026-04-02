---
name: roster-scan
description: "Fantasy Baseball 陣容基準卡週更。更新 roster-baseline.md 的數據（預測→實際），標記表現偏離預測的球員，觸發替換評估。用戶說「更新基準卡」「roster scan」「陣容健檢」「weekly update」或每週例行檢查時觸發。"
---

# 陣容基準卡週更 SOP

定期更新 `roster-baseline.md`，追蹤現有球員實際表現 vs 前一年數據，標記需要行動的異常。

> 本 skill 負責「更新自家陣容數據」。發現替換需求後：
> - 找 FA 候選人 → 觸發 `waiver-scan`
> - 評估特定球員 → 觸發 `player-eval`

> **評估標準**：見 `CLAUDE.md`「球員評估框架」（唯一定義）。本 SOP 不複製評估標準。
> **陣容來源**：`daily-advisor/roster_config.json`（唯一名單來源）。

## 適用時機

| 時期 | 建議頻率 | 數據內容 |
|------|---------|---------|
| 開季前 3 週 | 不需要跑（預測數據不變） | — |
| Week 3-6 | 每 2 週一次 | 實際數據開始有參考價值（30+ PA / 3-4 GS），但仍高噪音 |
| Week 7+ | 每週一次 | 實際數據穩定，可信度提升 |

## Step 1：讀取現況

1. 讀 `roster-baseline.md` — 上次更新日期 + 現有基準數據
2. 讀 `daily-advisor/roster_config.json` — 確認當前陣容（唯一名單來源）
3. 讀 `CLAUDE.md` — 確認評估框架（百分位表、指標定義）
4. 確認今天日期和賽季週數

**陣容異動檢查**：如果 roster_config.json 陣容與 `roster-baseline.md` 不一致（有新球員或 drop 球員），先同步名單再進入 Step 2。

## Step 2：蒐集實際數據

### 2a：自動化腳本（主要資料來源）

一次抓取全陣容的 MLB Stats API + Savant Statcast 數據：

```bash
python daily-advisor/roster_stats.py
```

> 輸出 markdown 表格：打者（G/PA/xwOBA/HH%/Barrel%/OPS/HR/BB%/BBE + 去年基準）+ 投手（GS/IP/ERA/WHIP/K/W/QS + xERA/xwOBA/HH%/Barrel%/BBE + 去年基準）。
> 直接複製到 roster-baseline.md，不需手動搜尋。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。

### 2b：Yahoo API 輔助查詢

球員狀態（守位資格、IL、健康）有疑問時，用 `yahoo_query.py` 快速確認：

```bash
python daily-advisor/yahoo_query.py player "{球員名}"
```

### 2c：WebSearch 補充（fallback）

roster_stats.py 無法取得的資訊才用 WebSearch：
- 傷病 / IL 更新
- 角色變動（先發 → 替補、輪值調整）

### 效率技巧

- **不再需要並行 Agent 搜尋** — roster_stats.py 一次跑完全陣容（~30 秒）
- **RP 簡化**：Punt SV+H 策略下，RP 重點看 ERA/WHIP/K/9，不追 SV+H

## Step 3：更新 roster-baseline.md

### 表格格式（in-season 版本）

**打者表格**：
```markdown
| 球員 | 位置 | G | PA | xwOBA | Barrel% | BB% | HH% | OPS | PA/TG | HR | BBE | 趨勢 |
```

**投手表格**：
```markdown
| 球員 | 隊伍 | GS | IP | xERA | xwOBA | HH% | Barrel% | ERA | IP/GS | WHIP | K | W | QS | BBE | 趨勢 |
```

### 趨勢標記規則

對比前一年數據（roster_config.json 的 prior_stats），標記趨勢：

| 標記 | 含義 | 打者觸發條件 | 投手觸發條件 |
|------|------|------------|------------|
| ▲ | 超越前一年 | xwOBA 高 .025+ 或 Barrel% 高 3+ 百分點 | xERA 低 0.30+ 或 HH% allowed 低 3+ 百分點 |
| — | 持平 | 核心指標在前一年 ±10% 內 | 同上 |
| ▼ | 低於前一年 | xwOBA 低 .025+ 或 Barrel% 低 3+ 百分點 | xERA 高 0.30+ 或 HH% allowed 高 3+ 百分點 |
| ⚠️ | 需要關注 | 連 2 週 ▼ | 連 2 週 ▼ |

> **小樣本警告**：Week 3-6 期間，所有趨勢標記後加註 `(小樣本)` 提醒。

### 更新 header

每次更新時修改文件頂部：
```markdown
> **數據來源**：{來源}
> **更新日期**：{日期}（Week {N}，實際數據）
> **下次更新**：{日期}
> **前次趨勢**：{上次 ⚠️/▼ 球員摘要，首次更新時寫「無（開季版）」}
```

## Step 4：異常標記與行動建議

更新完數據後，依 CLAUDE.md 評估框架檢查：

### 自動觸發（直接建議行動）

1. **過程指標警報**（引用 CLAUDE.md 百分位表判斷）：
   - 打者：核心 3 指標中 2 項 < P25 → 結構性問題
   - SP：核心 3 指標中 2 項 < P25 → 結構性問題
   - 輔助確認：傳統 stats 也差時更確定

2. **排名觸發**：
   - 打者排在全隊最弱 5 人 + 核心指標持續 ▼ → 建議 waiver-scan 找替換
   - SP 排在最弱 4 人 + 核心指標持續 ▼ → 同上

### 需要觀察（標記但不立即行動）

3. **表現偏離前一年**：
   - 打者核心指標比前一年顯著下降（≥ 10 百分位點）且 BBE > 30
   - SP 核心指標比前一年顯著下降（≥ 10 百分位點）且 BBE > 30

4. **正面驚喜**：
   - 任何球員大幅超越前一年 → 標記「勿 drop」，避免被短期低潮誤判

### 分流規則（決定下一步）

| 情境 | 行動 |
|------|------|
| 核心指標雙低 + BBE > 30 | → `waiver-scan`（找替換候選人） |
| ▼ 但仍在小樣本期（< 50 PA / < 20 IP） | → 不動，下週再看 |
| 已知特定替換候選人（waiver-log 觀察中有人） | → `player-eval`（直接比較） |
| 所有球員持平或超越 | → 不動 |

## Step 5：輸出摘要

```
## 基準卡週更（{日期}，Week {N}）

### 數據更新
- 打者：{N} 人已更新
- 投手：{N} 人已更新
- 數據來源：{來源}

### 趨勢摘要
- ▲ 超越前一年：{球員列表}
- ▼ 低於前一年：{球員列表}
- ⚠️ 需要關注：{球員列表 + 原因}

### 行動建議
- {有/無觸發條件命中}
- {建議的下一步：waiver-scan / player-eval / 不動}

### roster-baseline.md 已更新
```

## 錯誤檢查（更新前必過）

- [ ] 所有數據來自搜尋結果，無「大概」估算？
- [ ] 陣容名單與 roster_config.json 一致？（無遺漏、無多餘）
- [ ] 趨勢標記有對照 prior_stats 基準值？
- [ ] 小樣本期間（< Week 7）有加註 `(小樣本)`？

## 與其他 SOP 的整合

```
roster-scan（本 SOP）
  ├─ 發現替換需求 → waiver-scan（找 FA 候選人）
  ├─ 特定球員疑問 → player-eval（深入評估）
  └─ 陣容異動後 → 更新 roster_config.json + roster-baseline.md
```
