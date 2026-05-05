# Handoff: FA IL/NA Status Filter (2026-05-05)

## 背景 / 為什麼

**觸發案例**：2026-05-05 dry-run 推薦 `drop Ragans add Mize`，但 Mize 當下 Yahoo status = `IL15`。yesterday 的 Issue #149 也推薦同一人 — 兩天連續推薦 IL FA。**claim IL 球員無法立即上場**，等於浪費 add 名額（每週上限 6 次）+ 可能浪費 FAAB。

## 目前機制現狀

fa_scan.py **完全沒有自動排除 IL/NA FA 的機制**：

| 層次 | 處理 status |
|---|---|
| Yahoo 查詢（L532-535）| `status=A`（Available）— **IL 球員仍算 available** |
| Layer 2 品質過濾 | 只過 Sum 門檻，不看 status |
| Layer 3 / Layer 4 | 不過 status |
| LLM 看到 status? | ✅ `_status_tag`（fa_scan.py:1248）把 `[傷:IL15-15 天傷兵]` 加進 data block |
| Phase 6 prompt 強制看 status? | ❌ 沒明確指令「IL FA 扣分」 |

→ Mize case：LLM 看到 `[傷:IL15]` tag 但 Phase 6 prompt 沒強制 deprioritize，被 Sum +9 win gate + 21d xwOBACON .288 P90+ 等正向訊號蓋過。

## 方案 A：分 status 等級過濾（本 session 已對齊）

### Status 行動性矩陣

| Status | 涵義 | 處理 | 理由 |
|---|---|---|---|
| 空 / 無 | 健康 | **不過濾**，正常評估 | 隔日上場 |
| `DTD` | day-to-day | **不過濾** | 隨時可能上場，不該排除 |
| `IL10` / `IL15` | 短期 IL | **保留 + Layer 4 軟 tag** `⚠️ IL 短期-X 天` + Phase 6 prompt 加扣分指示 | 1-2 週可能回，elite 值得 stash 但需 deprioritize |
| `IL60` | 長期 IL | **Layer 2 hard filter**（除非 `--stash-mode`）| ≥2 個月不在，無 stash 價值（IL slot 只 2 格）|
| `NA` | minors / inactive | **Layer 2 hard filter**（除非 `--stash-mode`）| 真正即將 call up 訊號靠 owned% rising 抓得到（`collect_owned_risers`），不需 NA filter 預留特例 |

### 為什麼不用方案 B（全 IL/NA 排除 + `--stash` mode）？

IL10/IL15 是真正的灰色帶（elite + rest 1-2 週的場景），硬排除會誤殺。軟 tag + prompt 提醒讓 LLM 自然 deprioritize 但保留判斷彈性。

### 為什麼不用方案 C（軟 tag only）？

Mize case 證明只給 tag 不夠 — LLM 仍可被正向訊號蓋過。IL60/NA 雜訊太大，硬排除減少 LLM 注意力浪費。

## 實作骨架（拆 2 commits）

### Commit 1：Layer 2 hard filter（IL60 + NA）

**改動檔案**：`daily-advisor/fa_scan.py`

**位置**：`filter_by_savant` 之前，或在 `_run_daily_scan` Layer 2 流程加一步 status 過濾。具體看 `snapshot_no_watch` 怎麼流到 `filter_by_savant`（L3289-3292）— 在 filter_by_savant 內或外加都可以，建議在 snapshot 抽出時就過濾。

**邏輯**：
```python
# 預設排除長期不可用 FA
INACTIVE_STATUS = {"IL60", "NA"}

def _is_inactive_fa(player, include_inactive=False):
    if include_inactive:
        return False
    status = (player.get("status") or "").strip()
    return status in INACTIVE_STATUS
```

**CLI flag**：加 `--include-inactive`（IL stash / prospect 偵察用）。default false。

**Tests**：
- IL10 / IL15 / DTD / 空 → 不過濾
- IL60 / NA → 過濾
- `--include-inactive` → 全保留

### Commit 2：Layer 4 軟 tag + Phase 6 prompt 提醒

**A. 軟 tag**（fa_compute.py）

新 helper：
```python
def _status_warn_tag(status: str | None) -> str | None:
    """Yahoo IL10/IL15 → ⚠️ tag 強警示等級（同 ⚠️ 上場有限 / ⚠️ 短局 行為）。"""
    if not status:
        return None
    s = status.strip().upper()
    if s in ("IL10", "IL15"):
        return f"⚠️ IL 短期({s})"
    return None
```

把 `⚠️ IL 短期(...)` 加進 `_STRONG_WARN_TAGS`（fa_compute.py L388）— 觸發 `decision = "觀察"`，自動 deprioritize。

**B. 對應 status 進機械層輸出**

`compute_fa_tags_v4_sp`（fa_compute.py L724）需把 status 從 fa_player 拉出 → `v4_warn_tags_sp` 加進 IL 短期 tag。

**C. Phase 6 prompt 編輯**（5 SP + 1 batter）

`daily-advisor/prompt_phase6_sp_*.txt`（5 個）+ `prompt_fa_scan_pass2_batter.txt`（batter v4 thin 仍用）：

加一段明確指示，例如：
```
**IL/NA 處理規則**：
- FA 候選若 status 含 `IL10`/`IL15` → 不能立即上場（claim 後必須佔 IL slot），除非滿足 IL stash 條件（雙年菁英 + 預期 ≤2 週回歸 + 我方有 IL slot 空檔）否則 deprioritize 至 `觀察` 或 `pass`
- 寧可 pass 也不要推薦無法立即上場的 FA — claim 浪費 add 名額（每週上限 6）
```

### Tests 計畫

每 commit 後跑 `pytest daily-advisor/tests/`。新增測試：
- `test_inactive_status_filter`：IL10/IL15/DTD/空/IL60/NA 各 1 case
- `test_il_short_warn_tag`：IL10 / IL15 → 觸發 `⚠️ IL 短期`，IL60 / DTD / 空 → 不觸發
- `test_il_short_strong_warn_decision`：tag 出現 → decision=觀察

### 預估工時

~1.5-2 hour（含 prompt 編輯 + test）。

## 待決問題（下個 session 確認）

1. **DTD 處理確認**：DTD 通常隨時可能上場，不過濾合理。但 DTD 裡也有「明天才確定」的灰色帶 — 是否值得加 weak warn tag？建議先不加，觀察一段時間。

2. **`--include-inactive` flag 命名**：或拆成 `--include-il60` + `--include-na`？建議單一 flag 簡單，stash mode 場景少。

3. **IL 短期 tag 是否該寫上「預期 X 天回歸」**：Yahoo API 有沒有 expected return date？若有，tag 可顯示「⚠️ IL 短期(預期 5/12 回)」更有資訊量。需先確認 yahoo_query.py 能否取得。

4. **Phase 6 prompt 的「IL stash 條件」要寫多嚴**：太鬆 → LLM 還是會推薦 IL10/IL15；太嚴 → 永遠不會推薦真正值得的 stash 機會。建議用「雙年 Sum P85+ AND 已有 IL slot 空檔（透過 roster_config 檢查）」雙條件。

5. **本機 dry-run 驗證**：實作完跑 `python3 fa_scan.py --no-send --no-issue --no-waiver-log` 確認 Mize 從 SP-v4 candidates 中正確被排除（IL15 軟 tag 觸發觀察）。

## 風險

- **誤殺 IL15 即將回的 ace**：軟 tag 不是硬排除，LLM 仍可推薦但會 deprioritize。風險可控。
- **NA prospect call-up 訊號錯失**：依賴 owned% rising 偵測。建議實作後 watch 1-2 週確認 rising 機制能補位。

## 相關檔案 / 參考

- `daily-advisor/fa_scan.py` — Layer 2 / `_status_tag` (L1248) / SCAN_QUERIES (L532)
- `daily-advisor/fa_compute.py` — `_STRONG_WARN_TAGS` (L388) / `compute_fa_tags_v4_sp` (L724)
- `daily-advisor/prompt_phase6_sp_*.txt` — 5 SP prompts
- `daily-advisor/prompt_fa_scan_pass2_batter.txt` — batter v4 thin prompt
- 觸發案例 GitHub Issue：#149 (yesterday) + 今日 dry-run（VPS `/tmp/fa_scan_dryrun.log`，僅本地）
- 設計討論：本 session（2026-05-05）user + AI 對齊定稿
