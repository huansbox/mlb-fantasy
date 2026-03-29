# Yahoo Fantasy API Reference

## 基本資訊

- Base URL: `https://fantasysports.yahooapis.com/fantasy/v2`
- Auth: OAuth 2.0（refresh token 不過期，set-and-forget）
- 讀取回應：`?format=json` 拿 JSON
- 寫入 payload：必須 XML
- Rate limit：不公開，約每小時幾千次，超限回 HTTP 999（10-15 分鐘自動恢復）

## OAuth Scope

| Scope | 值 | 用途 |
|-------|-----|------|
| Read-only | `fspt-r` | 讀取聯賽、球員、陣容、成績 |
| Read/Write | `fspt-w` | 上述 + 設陣容、add/drop、交易 |

目前專案授權時未帶 scope 參數，推測為 read-only。啟用寫入需重跑 `yahoo_auth.py` 帶 `scope=fspt-w`。

## 已使用的端點

| 端點 | 用途 | 函式 |
|------|------|------|
| `GET /league/{league_key}/scoreboard` | H2H 週對戰比分 | `fetch_yahoo_scoreboard()` |
| `GET /team/{team_key}/roster` | 我方/對手陣容 | `fetch_yahoo_roster()` |
| `GET /league/{league_key}/teams` | 聯賽隊伍列表，找自己的 team_key | `analyze()` 內 |
| `GET /league/{key}/players;{filters};out=stats,percent_owned` | FA 查詢 + 7×7 stats + 持有率 | `cmd_fa()` |
| `GET /league/{key}/players;search={name}` | 球員姓名搜尋 | `cmd_player()` |
| `GET /league/{key}/players;player_keys={key}/stats` | 指定球員本季數據 | `cmd_player()` 二段查詢 |
| `GET /league/{key}/players;player_keys={key}/percent_owned` | 指定球員持有率 | `cmd_player()` 二段查詢 |

## 可用但尚未使用的端點

### 讀取類（現有權限即可）

**FA / 球員查詢**
```
GET /league/{league_key}/players;status=FA;position={pos};sort=AR;count=25;start=0
```
- `status`: `FA`（自由球員）/ `W`（waiver）/ `A`（所有可用）/ `T`（已被選）
- `position`: `C`, `1B`, `2B`, `SS`, `LF`, `CF`, `RF`, `SP`, `RP`, `B`（全打者）, `P`（全投手）
- `sort`: `AR`（actual rank）/ `OR`（overall rank）/ stat_id
- `sort_type`: `season` / `lastweek` / `lastmonth` / `date`
- 可附加 sub-resource: `stats`, `percent_owned`, `ownership`

**其他可查的資源**
- `/league/{league_key}/standings` — 聯賽排名
- `/league/{league_key}/transactions` — 近期交易/異動記錄
- `/player/{player_key}/stats` — 單一球員數據

### 寫入類（需 `fspt-w` scope）

| 操作 | 方法 | 端點 |
|------|------|------|
| 設定先發/板凳位置 | PUT | `/team/{team_key}/roster` |
| Add player | POST | `/league/{league_key}/transactions` |
| Drop player | POST | `/league/{league_key}/transactions` |
| Add/Drop + FAAB 出價 | POST | `/league/{league_key}/transactions` |
| 提出交易 | POST | `/league/{league_key}/transactions` |
| 接受/拒絕交易 | PUT | `/transaction/{transaction_key}` |

寫入端點的 XML payload 格式待實際使用時再補。

## 擴展方向

### 讀取類（現有權限可用）

- [x] H2H 週對戰比分（已實作）
- [x] 我方 / 對手陣容（已實作）
- [ ] **FA 球員查詢** — waiver-scan / player-eval 可直接拉 FA 清單 + 數據，取代手動搜尋
- [ ] 近期交易記錄 — 知道別隊撿了誰放了誰
- [ ] 聯賽排名 — standings

### 寫入類（需 `fspt-w` scope，重新授權）

- [ ] 自動設 lineup — 最終報建議後直接執行，省手動操作（需確認防護機制）
- [ ] 自動 add/drop — waiver-scan 發現目標後直接操作（FAB 花錯不可逆，風險高）
- [ ] 自動交易 — 風險太高，不建議自動化

## 相關檔案

| 檔案 | 用途 |
|------|------|
| `yahoo_auth.py` | 首次 OAuth 授權（手動跑一次） |
| `yahoo_token.json` | 存放 access_token / refresh_token（不入 git） |
| `.env` | `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET` |
