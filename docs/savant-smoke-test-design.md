# Savant 端點 Smoke Test 設計

> **Status**：設計（2026-04-25）。non-blocking — 動工時機 v4 cutover 前後（v4 上線後對 Savant 依賴度進一步增加）。
> **動機**：上次 session「腦中還有什麼」#3 直接命中 — Savant 是 single point of failure，一旦改 API 全鏈斷掉。

---

## 1. Threat model

### 1.1 Savant 端點失誤模式

| 模式 | 影響 | 偵測難度 |
|------|------|---------|
| **A. URL 整個 404** | 端點下架；fa_scan / savant_rolling 整個 fail | 易（HTTP status） |
| **B. URL 重導向**（302 → 新位址）| 視 Python urllib 行為而定，可能 fetch 不到 | 中 |
| **C. CSV schema 改**（欄位改名 / 新增欄）| Python csv.DictReader 仍能 parse，但 `row.get("xwobacon")` 拿到 None — 後續 silent failure | **難**（不會 raise）|
| **D. CSV 改回 JSON / API token 化** | text decode 失敗或 JSON parse 失敗 | 易 |
| **E. Rate limiting** | 有時段 fail，重試可恢復 | 中（需 retry pattern）|
| **F. CSV value semantic 改**（如 gb_rate 從 0-1 改為 0-100）| 數值能 parse 但意義錯，下游分析全歪 | **極難**（需 sanity check） |
| **G. 球員 ID schema 改**（player_id 改名為 mlbam_id 或 batter_id）| `safe_int(row.get("player_id"))` 拿 0，整批資料合併不上 | 中 |

C / F / G 是最危險的 silent failure。

### 1.2 已遇過的 case（歷史教訓）

CLAUDE.md learnings 提及「Savant 端點穩定性 — xwOBACON 走非標準 URL」— 表示用戶已意識端點可能變動。

`roster_sync.py:_find_id_column()` 已處理 player_id vs mlbam_id 雙 schema（line 293-298）— 顯示 G 模式已實際發生過。

---

## 2. 端點清單（總共 6 個）

依 grep 結果整理：

| # | URL pattern | 用途 | 使用點 |
|---|-------------|------|--------|
| 1 | `leaderboard/custom?selections=...` | xera / xwoba / xwobacon | `calc_v4_percentiles.py` / `fa_scan_v4.py` / `backfill_prior_stats_v4.py` |
| 2 | `leaderboard/batted-ball` | gb_pct / bbe | `calc_v4_percentiles.py` / `fa_scan_v4.py` / `backfill_prior_stats_v4.py` |
| 3 | `leaderboard/pitch-arsenal-stats` | whiff_pct（按球種加權）| `calc_v4_percentiles.py` / `fa_scan_v4.py` / `backfill_prior_stats_v4.py` |
| 4 | `leaderboard/statcast` | xwoba / xera / barrel / hh_pct（通用）| `roster_sync.py` / `daily_advisor.py` / `yahoo_query.py` |
| 5 | `leaderboard/expected_statistics` | xwoba / xera（v2 路徑）| `daily_advisor.py` / `yahoo_query.py` |
| 6 | `statcast_search/csv` | pitch-level rolling | `savant_rolling.py` |

---

## 3. Smoke Test 架構

### 3.1 腳本：`daily-advisor/savant_smoke.py`

```python
"""savant_smoke — daily health check for all Savant endpoints used in pipeline.

Pings each endpoint with a known-good fixture (e.g. Skubal mlb_id 669373
for pitcher endpoints, Judge for batter), validates HTTP 200 + expected
CSV schema + sanity bounds on key values. On failure: Telegram ping
with details + exit non-zero (for cron alerting).

Usage:
  python3 savant_smoke.py             # all endpoints, alert on fail
  python3 savant_smoke.py --endpoint custom   # only one
  python3 savant_smoke.py --no-alert  # human dry-run, stdout only
"""
```

### 3.2 Per-endpoint check spec

對每個 endpoint 做 4 檢核：

```python
@dataclass
class EndpointCheck:
    name: str                       # "custom" / "batted-ball" / etc.
    url: str                        # full URL
    expected_columns: set[str]      # e.g. {"player_id", "xwoba", "xwobacon"}
    sanity_checks: list[Callable]   # e.g. [lambda d: d["xwoba"] is not None and 0.2 < d["xwoba"] < 0.5]
    fixture_player_id: int          # known-active player to validate

CHECKS = [
    EndpointCheck(
        name="custom",
        url="https://baseballsavant.mlb.com/leaderboard/custom?year={year}&type=pitcher&filter=&min=1&selections=pa,bip,xwoba,xwobacon,xera,era&csv=true",
        expected_columns={"player_id", "xwoba", "xwobacon", "xera"},
        sanity_checks=[
            lambda r: 0.20 <= r["xwoba"] <= 0.50,
            lambda r: 0.25 <= r["xwobacon"] <= 0.55,
            lambda r: 1.5 <= r["xera"] <= 8.0,
        ],
        fixture_player_id=669373,  # Skubal
    ),
    # ... 其他 5 個 endpoint
]
```

### 3.3 失敗類型細分

```python
class CheckFailure(Enum):
    HTTP_ERROR = "http"           # 4xx / 5xx / timeout
    EMPTY_RESPONSE = "empty"      # 200 但 body 空
    SCHEMA_MISSING = "schema"     # 預期欄位不在 CSV
    FIXTURE_NOT_FOUND = "fixture" # 預期 fixture player 在 CSV 找不到
    SANITY_FAIL = "sanity"        # value 在合理範圍外
```

### 3.4 通知格式

對 Telegram：

```
⚠️ Savant Smoke Test FAIL — 2026-05-15

Endpoint: leaderboard/custom (xwobacon)
Failure: SCHEMA_MISSING
Detail: column 'xwobacon' missing from CSV
URL: https://...

Affected pipelines:
- fa_scan_v4 (SP analysis)
- backfill_prior_stats_v4 (will fail)
- calc_v4_percentiles (next quarterly run will fail)

Action: investigate Savant endpoint change (URL or schema).
```

對 GitHub Issue（自動建立 + label `savant-endpoint-error`）：

```
[Savant Smoke] {endpoint name} {failure type} on {date}

Body: full diagnostic dump (raw response head, expected schema, observed schema, etc.)
```

---

## 4. Cron 排程

```cron
# /etc/cron.d/daily-advisor (VPS)
# Savant smoke test — runs early morning before fa_scan
00 11 * * * mlb cd /opt/mlb-fantasy/daily-advisor && python3 savant_smoke.py >> /var/log/savant_smoke.log 2>&1
```

排在 TW 11:00（fa_scan 12:30 之前），失敗時用戶 11:30 看到 Telegram 警示，仍有時間判斷是否手動干預（如停掉 fa_scan cron 等修復）。

---

## 5. Sanity check 細節

### 5.1 為什麼 sanity check 重要

C / F 模式（schema 改 / value semantic 改）只 sanity check 才能抓。例：
- gb_pct 從 0-1 改 0-100 → 99% 變 99.0（看起來正常但意義反了）
- xwoba 從 .350 變 35.0（小數點變化）

### 5.2 Sanity check 邊界（基於 2025 MLB 全季分布）

| 指標 | 合理範圍 | 來源 |
|------|---------|------|
| xwoba (batter) | 0.200-0.500 | CLAUDE.md 百分位表 P25-P90 = .261-.349 |
| xwoba (pitcher allowed) | 0.250-0.450 | CLAUDE.md SP P25-P90 = .361-.270 |
| xwobacon | 0.300-0.500 | 接觸品質範圍 |
| xera | 1.5-8.0 | 季全 SP P25-P90 = 5.62-2.98 |
| era | 1.0-12.0 | 寬鬆容納 short stint relievers |
| barrel_pct | 0-30% | P90 ~14% buffer 至 30% |
| hh_pct | 20-60% | P25-P90 ~34-50% |
| gb_rate (CSV decimal) | 0.20-0.65 | P25-P90 ~38-55% |
| whiff_percent | 0-50% | 球種加權後合理上限 |
| ip | 0-220 | 全季 SP 上限 ~220 |

任一 fixture player 的數值落在範圍外 → SANITY_FAIL。

### 5.3 Cross-endpoint consistency check

進階：兩個 endpoint 都返回同一 player 的同一指標時，比對是否一致：
- `leaderboard/custom` xwoba vs `leaderboard/expected_statistics` xwoba（同 player 同年）→ 應 ≤ 0.005 差距

差距過大 → 表示其中一個 endpoint 有問題或 semantic 改了。

---

## 6. 整合到 fa_scan / savant_rolling 的策略

### 6.1 Pre-flight check（不採用）

可考慮 fa_scan 啟動時先 ping 所有 endpoint smoke check 過才繼續。

**問題**：每天 fa_scan 多 2-3 分鐘 + 噴大量請求 + 早晨 Savant 載入慢可能造成 cron 整體延後。

**結論**：不採用。smoke 獨立 cron 跑。

### 6.2 失敗時的 fallback（不採用）

考慮 endpoint 失敗時 fa_scan 跳過該指標仍跑 partial。

**問題**：partial run 結果可能誤導決策（用戶不知道少了什麼）。

**結論**：不採用。失敗就 alert + 人工處理，比 silent partial 好。

### 6.3 採用方案：smoke 獨立 cron + 失敗時 alert + 人工決定 fa_scan 是否仍跑

簡單、低風險、保留 visibility。

---

## 7. 端點變化追蹤

如果某 endpoint 確認改了（不是暫時 outage），需要：

1. **更新 fa_compute / fa_scan / 各 fetcher 的 URL pattern**
2. **更新 prior_stats schema** 若 value semantic 改
3. **重跑 backfill_prior_stats_v4**（若 schema 改影響歷史 backfill）
4. **更新本 smoke test 的 sanity ranges** 若分布改

腳本不該自動修；alert 後由用戶人工處理。

---

## 8. 實作工時估計

| 工作 | 工時 |
|------|------|
| `savant_smoke.py` 主腳本 | 3-4 hr |
| `EndpointCheck` 6 個端點 spec 撰寫 | 2 hr |
| Telegram 通知 + GitHub Issue 整合 | 1 hr（reuse fa_scan _publish 邏輯）|
| `tests/test_savant_smoke.py`（mock fixtures）| 2 hr |
| Cron 部署 + 1 週驗證 | 1 hr setup + 觀察 |

**total**：~9-10 hr

---

## 9. 不在範圍內

- **自動修復端點變化**：太危險，人工處理
- **Endpoint 替代源**：如果 Savant 全死，沒備援。可以 long-term 考慮 Statcast Public Search API 但複雜度過高
- **歷史 archive 補抓**：smoke test 不負責補抓過去資料

---

## 10. 與其他文件的關聯

| 本 doc | 關聯 |
|--------|------|
| 動機 | `docs/v4-cutover-plan.md` §9 風險「Savant endpoint 失誤」標 「記入此 doc」 |
| 端點清單 | `daily-advisor/calc_v4_percentiles.py` / `fa_scan_v4.py` / `savant_rolling.py` 的 fetcher |
| 整合策略 | 不破壞 fa_scan production cron |
| 觸發實作 | v4 cutover 前後 |

---

## 11. Action items

- [ ] `daily-advisor/savant_smoke.py`（核心腳本）
- [ ] `daily-advisor/_savant_endpoints.py`（CHECKS 定義抽出）
- [ ] `tests/test_savant_smoke.py`（mock 6 個 endpoint 的成功 / 失敗 case）
- [ ] VPS cron entry（TW 11:00 daily）
- [ ] 1 週 dry-run 觀察（`--no-alert` mode）
- [ ] Telegram bot 訊息格式 review
- [ ] 寫好後在 CLAUDE.md「資料流」章節加 reference
