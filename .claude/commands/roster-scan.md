---
name: roster-scan
description: "Fantasy Baseball 陣容基準卡週更。更新 roster-baseline.md 的數據（預測→實際），標記表現偏離預測的球員，觸發替換評估。用戶說「更新基準卡」「roster scan」「陣容健檢」「weekly update」或每週例行檢查時觸發。"
---

# 陣容基準卡週更 SOP

定期更新 `roster-baseline.md`，追蹤現有球員實際表現 vs 預測，標記需要行動的異常。

> 本 skill 負責「更新自家陣容數據」。發現替換需求後：
> - 找 FA 候選人 → 觸發 `waiver-scan`
> - 評估特定球員 → 觸發 `player-eval`

## 適用時機

| 時期 | 建議頻率 | 數據內容 |
|------|---------|---------|
| 開季前 3 週 | 不需要跑（預測數據不變） | — |
| Week 3-6 | 每 2 週一次 | 實際數據開始有參考價值（30+ PA / 3-4 GS），但仍高噪音 |
| Week 7+ | 每週一次 | 實際數據穩定，可信度提升 |

## Step 1：讀取現況

1. 讀 `roster-baseline.md` — 上次更新日期 + 現有基準數據
2. 讀 `CLAUDE.md` — 確認當前陣容（是否有異動後未更新基準卡的球員）
3. 確認今天日期和賽季週數

**陣容異動檢查**：如果 CLAUDE.md 陣容與 `roster-baseline.md` 不一致（有新球員或 drop 球員），先同步名單再進入 Step 2。

## Step 2：蒐集實際數據

> 數據來源優先順序：FanGraphs > Baseball Reference > ESPN > Yahoo
> ROS（Rest of Season）預測：RotoChamp Steamer 或 FanGraphs Steamer ROS

### 2a：WebSearch 查詢（主要數據來源）

**打者** — 每位搜尋：
```
{球員名} {今年} stats {今天日期附近}
```
**必須取得**：G（場次）、PA、AVG、OPS、HR、RBI、R、SB、BB%

**投手** — 每位 SP 搜尋：
```
{球員名} {今年} stats pitching {今天日期附近}
```
**必須取得**：GS、IP、ERA、WHIP、K、W、QS（如可取得）

### 2b：Yahoo API 輔助查詢

球員狀態（守位資格、IL、健康）有疑問時，用 `yahoo_query.py` 快速確認：

```bash
python daily-advisor/yahoo_query.py player "{球員名}"
```

> `yahoo_query.py player` 現在回傳守位資格、持有率、本季 7×7 stats。可作為 WebSearch 的交叉驗證或替代來源。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。

### 效率技巧

- **並行搜尋**：用 4 個 Agent 分批搜尋（打者 A-F / 打者 G-L / SP 組 / 後段 SP + RP 組）
- **單一來源優先**：如果 FanGraphs 或 ESPN 的一個頁面能拉到多人數據，優先用
- **RP 簡化**：Punt SV+H 策略下，RP 只需更新 ERA / WHIP / IP，不追 SV+H

## Step 3：更新 roster-baseline.md

### 表格格式（in-season 版本）

開季後第一次更新時，將表格格式從「預測版」切換為「實際 + 預測對照版」：

**打者表格**：
```markdown
| 球員 | 位置 | G | PA | xwOBA | HH% | Barrel% | OPS | HR | BB% | BBE | 趨勢 |
```

**投手表格**：
```markdown
| 球員 | 隊伍 | GS | IP | ERA | WHIP | K | W | QS | 趨勢 |
```
> QS：有實際數據時填入，無數據時用粗估（ERA < 3.50 ≈ 18-22 QS；3.50-4.00 ≈ 14-17；4.00-4.50 ≈ 10-13）。

### 趨勢標記規則

對比預測值（開季版基準卡的 Steamer 數據），標記趨勢：

| 標記 | 含義 | 打者觸發條件 | 投手觸發條件 |
|------|------|------------|------------|
| ▲ | 超越預測 | xwOBA 比前一年高 .025+ 或 HH% 高 5+ 百分點 | ERA 比預測低 0.50+ 或 K/9 超預測 1.0+ |
| — | 符合預測 | xwOBA/HH% 在前一年 ±10% 內 | 各項在預測值 ±10% 內 |
| ▼ | 低於預測 | xwOBA 比前一年低 .025+ 或 HH% 低 5+ 百分點 | ERA 比預測高 0.50+ 或 IP pace 低於預測 15%+ |
| ⚠️ | 需要關注 | 連 2 週 ▼ 或觸及 CLAUDE.md 行動觸發規則 | 連 2 週 ▼ 或 WHIP > 1.50 |

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

更新完數據後，檢查以下觸發條件：

### 自動觸發（直接建議行動）

1. **CLAUDE.md 行動觸發規則命中**：
   - 讀取 CLAUDE.md「行動觸發規則」表格，逐條比對當前數據
   - 任何條件命中 → 提示用戶並建議對應行動
   - ⚠️ 不硬編碼球員名稱，陣容會隨賽季變動，一律以 CLAUDE.md 即時版本為準

2. **過程指標警報**：
   - 任何正選打者 xwOBA < .262 (P25) + HH% < 36% (P25)（過程指標雙低 = 結構性問題，非小樣本噪音）
   - Barrel% 同時 < 5% (P25) 時加重標記
   - 任何 SP ERA > 5.50 且 WHIP > 1.60（拖比率）

### 需要觀察（標記但不立即行動）

3. **表現偏離預測**：
   - 打者 xwOBA 比前一年低 .030+ 且 BBE > 30（過程指標偏離比結果指標更早示警）
   - 打者 HH% 比前一年低 5+ 百分點且 BBE > 30
   - SP ERA 比預測高 1.00+ 且已過 20 IP

4. **正面驚喜**：
   - 任何球員大幅超越預測 → 標記「勿 drop」，避免被短期低潮誤判

### 分流規則（決定下一步）

| 情境 | 行動 |
|------|------|
| 觸發規則命中（CLAUDE.md 行動觸發） | → `waiver-scan`（找替換候選人） |
| ▼ 但仍在小樣本期（< 50 PA / < 20 IP） | → 不動，下週再看 |
| 比率拖累警報 + 已超過 50 PA / 20 IP | → `player-eval`（確認是否結構性問題） |
| 已知特定替換候選人（waiver-log 觀察中有人） | → `player-eval`（直接比較） |
| 所有球員符合預測或超越 | → 不動 |

> 建議行動時同時引用 `roster-baseline.md` 替換門檻，確認候選人達標。

## Step 5：輸出摘要

```
## 基準卡週更（{日期}，Week {N}）

### 數據更新
- 打者：{N} 人已更新
- 投手：{N} 人已更新
- 數據來源：{來源}

### 趨勢摘要
- ▲ 超越預測：{球員列表}
- ▼ 低於預測：{球員列表}
- ⚠️ 需要關注：{球員列表 + 原因}

### 行動建議
- {有/無觸發條件命中}
- {建議的下一步：waiver-scan / player-eval / 不動}

### roster-baseline.md 已更新
```

## 錯誤檢查（更新前必過）

- [ ] 所有數據來自搜尋結果，無「大概」估算？
- [ ] 陣容名單與 CLAUDE.md 一致？（無遺漏、無多餘）
- [ ] 趨勢標記有對照預測基準值？
- [ ] 小樣本期間（< Week 7）有加註 `(小樣本)`？
- [ ] 行動觸發規則有讀取 CLAUDE.md 最新版？

## 與其他 SOP 的整合

```
roster-scan（本 SOP）
  ├─ 發現替換需求 → waiver-scan（找 FA 候選人）
  ├─ 特定球員疑問 → player-eval（深入評估）
  └─ 陣容異動後 → 更新 CLAUDE.md + roster-baseline.md
```
