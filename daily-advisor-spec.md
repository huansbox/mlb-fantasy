# Daily Advisor — 需求規格

> **目標**：每日自動產出隔日陣容調整建議，透過 Telegram Bot 推送
> **執行環境**：VPS + cron + `claude -p`
> **狀態**：Phase 1 規劃中

## 開發階段

### Phase 1：陣容微調（僅 MLB Stats API）

單一 Python 腳本，每日抓 MLB 賽程數據 → 比對本地陣容檔 → `claude -p` 產出建議 → Telegram 推送。

**包含：**
- 模組 ① 明日陣容概覽（休兵、SP 先發、投打衝突、對手打線強弱）
- 模組 ② 部分：本週 IP 追蹤（從 game log 加總）
- Watchlist 球員近期表現

**不含（Phase 2）：**
- 異動規劃（需要 Yahoo API 的 FA 市場清單）
- 週對戰態勢（需要 Yahoo API 的 H2H 比分板）
- 傷兵處理（手動問 Claude 即可）

### Phase 2：異動規劃 + 週對戰態勢（加接 Yahoo API）

Phase 1 驗證價值後擴充。

## 系統架構

```
[VPS cron 每日定時]
  → 腳本抓 MLB Stats API（明日賽程、SP 先發、球隊數據）
  → 比對陣容（Yahoo API 或 roster-baseline.md fallback）
  → claude -p 產出每日建議
  → Telegram Bot 發送
```

## 報告內容（三區塊）

### 區塊一：明日陣容概覽（每日決策核心）

| 資訊 | 數據來源 | 說明 |
|------|---------|------|
| 誰有比賽 / 誰休兵 | MLB Stats API schedule | 休兵日打者要坐，板凳替補要上 |
| 明日 SP 先發 | MLB Stats API probable pitchers | 自家哪些 SP 明天登板 |
| SP 對手打線強弱 | MLB Stats API team stats | wRC+/OPS 排名，判斷 SP 風險 |
| 自家投打衝突 | 交叉比對 roster × schedule | 例：Ragans 先發 vs ATL → Albies 對上 |

### 區塊二：週進度追蹤（影響當日策略方向）

| 資訊 | 數據來源 | 說明 |
|------|---------|------|
| 本週已累積 IP | MLB Stats API game logs 加總 | 離 40 IP 門檻還差多少 |
| 本週剩餘 SP 先發數 | MLB Stats API probable pitchers | 判斷是否需要多排 SP |
| 週末 ratio 保護提醒 | 規則引擎（週五起觸發） | ERA/WHIP 領先就準備鎖 |

### 區塊三：情境提醒（錦上添花）

| 資訊 | 數據來源 | 說明 |
|------|---------|------|
| 傷兵更新 | MLB Stats API roster/injuries | Buxton 進 IL → 提醒 Frelick 頂上 |
| Two-start SP 本週 | MLB Stats API schedule 推算 | 哪些 SP 本週投兩場 |
| Watchlist 球員動態 | MLB Stats API player stats | O'Hearn / Painter 近期表現追蹤 |

## 數據來源可行性（2026-03-28 驗證）

### MLB Stats API ✅ 已實測通過

| 項目 | 結果 |
|------|------|
| **認證** | 無需任何認證，直接 HTTP GET |
| **費用** | 完全免費 |
| **Rate limit** | 無明確限制，每日 10-15 call 安全 |
| **使用條款** | 個人非商業用途允許 |

**已驗證端點：**

| 端點 | 用途 | 測試結果 |
|------|------|---------|
| `/schedule?hydrate=probablePitcher` | 每日賽程 + SP 先發 | ✅ 回傳完整賽程、先發投手姓名與 ID |
| `/people/{id}/stats?stats=gameLog` | 球員逐場數據（IP 追蹤） | ✅ Skubal: 2026-03-26 vs SD, 6.0 IP, 6K, 0ER |
| `/teams/{id}/stats?stats=season` | 球隊打擊數據 | ✅ NYY: AVG .257, OPS .711 |
| `/teams/{id}/stats?stats=sabermetrics` | 進階數據（wRC+） | ✅ NYY 2025: wRC+ 103.4 |

**投打衝突偵測 POC（3/29 測試）：**
- 成功偵測明日 SP 先發（無）
- 成功偵測休兵打者：Chisholm(NYY)、Machado(SD)、Stanton(NYY)
- 衝突比對邏輯正常運作

**推薦 library：**
- Python: `MLB-StatsAPI`（pip install MLB-StatsAPI）
- Node.js: `mlb-stats-api`（npm install mlb-stats-api）

### Yahoo Fantasy API ✅ 研究確認可行

| 項目 | 結果 |
|------|------|
| **認證** | OAuth 2.0，首次需瀏覽器手動授權（~15 分鐘），之後 refresh token 永不過期 |
| **費用** | 完全免費 |
| **Rate limit** | 不公開，每日 5-10 call 安全；超限返回 HTTP 999，10-15 分鐘自動解除 |
| **使用條款** | 禁止商業用途，個人自用允許 |

**可用端點：**

| 端點 | 用途 |
|------|------|
| `/team/{key}/roster` | 我的陣容（含日期過濾） |
| `/league/{key}/scoreboard;week=N` | 本週 H2H 對戰比分板（14 類別即時勝負） |
| `/team/{key}/matchups` | 我的對戰詳情 |
| `/league/{key}/players;status=FA` | FA 市場 |
| `/league/{key}/standings` | 聯賽排名 |

**推薦 library：**
- Python: `yfpy`（pip install yfpy）— 最活躍維護，內建 token refresh
- Node.js: `yahoo-fantasy`（功能完整但 12+ 月未更新）

### 結論：兩個都接，Python 開發

兩者互補不重疊：
- **MLB Stats API** → MLB 真實世界數據（賽程、投手、球隊強弱、game log）
- **Yahoo Fantasy API** → 聯賽數據（陣容、對戰比分、FA 市場）

語言選 **Python**（兩邊 wrapper 都最成熟）。

## 聯賽背景參數（供 claude -p prompt 使用）

- 賽制：H2H One Win，14 類別（7×7），贏 8+ = 週勝
- Lineup 鎖定：Daily - Tomorrow
- Min IP：40/週
- Max Acquisition：6/週
- 策略：Punt SV+H + 軟 Punt SB
- 目標類別：R/HR/RBI/BB/AVG/OPS + IP/W/K/QS/ERA/WHIP（12 項中贏 8+）

## 通知管道

- **Telegram Bot**（BotFather 建立，HTTP POST 發訊息）
- 每日一則，Markdown 格式

## 待確認

- [x] MLB Stats API 可行性 — ✅ 已實測通過
- [x] Yahoo Fantasy API 可行性 — ✅ 研究確認可行
- [x] Max Games Played 限制 — H2H 無此限制（Roto 專屬），matchup 頁 GP 僅資訊顯示
- [ ] Yahoo Fantasy API 實測（Phase 2，註冊 App + OAuth 首次授權）
- [ ] VPS 環境（OS、已安裝語言/工具）
- [ ] Telegram Bot 建立
- [ ] 每日推送時間（建議：台灣時間早上，MLB 比賽前數小時）
- [ ] claude -p 的 token 用量與成本估算
