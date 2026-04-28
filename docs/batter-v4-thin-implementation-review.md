# Batter v4 Thin 實作 Review — 2026-04-28

> **Reviewer**: Claude (other session via this session) — code review against design doc
> **Scope**: 3 commits — `d0225f7` cant_cut update, `b5d1be1` fa_compute thin, `90a38c5` fa_scan thin pipeline
> **Reference**: `docs/batter-framework-upgrade-design.md`
> **指示**: 「若有發現狀況，先以文檔紀錄，不實際修改」— 此 doc 為 finding log, 不含 fix

---

## Summary

| 分級 | 數量 | 摘要 |
|---|---|---|
| 🔴 Critical | 1 | LLM 看到 design 明確排除的欄位（positions）|
| 🟡 Doc inconsistency | 2 | design 章節間自相矛盾，implementation 選一邊 |
| 🟠 Deferred | 2 | 預埋 multi-agent 用的函式 schema 不完整（多 agent 層上線前要補）|
| 🟢 Minor | 3 | 註記但不需 action |

整體實作與設計**高度對齊**。Critical 1 個是真實設計違背，Doc 不一致 2 個建議 design doc 補正而非 implementation 改。

---

## 🔴 Critical: LLM 看到 positions 欄位

### Finding C1 — anchor + FA display 包含 positions 字串

**檔案 / 位置**:
- `daily-advisor/fa_scan.py:2617` (`_fmt_anchor_block_batter_v4`)
- `daily-advisor/fa_scan.py:2703-2705` (`_fmt_fa_block_batter_v4`)

**Code**:
```python
# Anchor
positions = "/".join(entry.get("positions", []) or [])
lines = [f"- **{label} {name}** ({team}, {positions}) [PA ... / PA-TG ... / BBE ...]"]

# FA
pos = entry.get("position", "")
lines = [f"{prefix}**{name}** ({team}, {pos}) {pct_str}{shape_str} ..."]
```

**Design 違背**:
- `docs/batter-framework-upgrade-design.md` §1.2 拋棄的設計：
  > 守位 / selected_pos / status 進 anchor 評估 — 評價只看打擊數據；BN 與否、DTD 狀態跟當天比賽有關，不是球員品質判斷
- §3.4 FA schema 「明確不出現的欄位」：
  > ❌ `positions` — **完全無需考慮守位**，連 final decision 也不靠位置 fit 判斷

**實際影響**:
- Pass 2 string 範例：`- **P1 Albies** (ATL, 2B) [PA 320 / PA-TG 4.28 / BBE 92]`
- LLM 看到 `(ATL, 2B)` 可能用守位資訊 reason（「2B 稀缺，drop 風險高」）— 違反設計「完全無需考慮守位」原則
- 雖然在現役單 LLM 過渡期影響不致命（LLM 仍主要看數據），但跟 design 哲學牴觸

**建議**:
- `_fmt_anchor_block_batter_v4` line 2617：移除 positions 顯示
- `_fmt_fa_block_batter_v4` line 2703-2705：移除 pos 顯示
- 改成：`- **P1 Albies** (ATL) [PA 320 / PA-TG 4.28 / BBE 92]`

**驗證方式**: 上線後抓一份 Pass 2 string 確認沒 `(team, position)` pattern。

---

## 🟡 Doc Inconsistency: 設計章節間矛盾

### Finding D1 — FA schema 是否含 tags

**Doc 衝突**:
- `docs/batter-framework-upgrade-design.md` §3.4「FA candidate output schema」「明確不出現的欄位」:
  > ❌ `score` / `sum` / `breakdown` / `urgency` / **tags**
- §7.1「機械層精簡 改動清單」：
  > `compute_fa_tags` batter 分支：保留 `✅ 球隊主力 / ⚠️ 上場有限`（PA-based gate）但移除其他 14d / xwOBA / luck 相關 tag

**Implementation 選邊**: 跟隨 §7.1（保留 PA-based tags）— 看到 `tag_str = f" / {' '.join(minimal_tags)}"` line 2691。

**建議**:
- 兩條 design spec 不一致 — implementation 選了正確的那邊（功能上 PA-based tags 確實有訊號價值）
- Design doc §3.4 應該補上：「保留 ✅ 球隊主力 / ⚠️ 上場有限 兩個 PA-based gate tags（其他 data-based tags 全移除）」
- 不需動 code，**改 design doc**

### Finding D2 — anchor schema 中 14d 完整 trad 是否進結構

**Doc 衝突**:
- §3.2 anchor schema 範例 JSON 寫了完整 14d trad（ops / avg / hr / rbi / r / bb_pct / k_pct / k_spike_pp / delta_xwoba / pa / bbe）
- 但 §3.7「百分位 lookup 實作指引」描述 14d 只用 Savant rolling 的 xwoba/barrel/hh + pctile

**Implementation 選邊**:
- `_player_to_v4_schema` (multi-agent enrich) → rolling_block **只含 Savant rolling 4 項**（xwoba / barrel_pct / hh_pct / bbe / pa）
- `_fmt_anchor_block_batter_v4` (Pass 2 顯示) → 同時含 Savant rolling + MLB API 14d trad（透過 `_fetch_14d_trad_bulk`）

**結論**:
- 過渡期 single LLM 路徑 OK（顯示完整 trad）
- Multi-agent enrich schema 不完整（見 Finding F1）

---

## 🟠 Deferred: Multi-agent 層上線前需補

### Finding F1 — `enrich_for_multi_agent_batter` 沒整合 14d trad

**檔案**: `daily-advisor/fa_scan.py:1712` (`_player_to_v4_schema`)

**Code**:
```python
rolling_block = None
if rolling:
    rolling_block = {
        "ops": rolling.get("ops"),  # may be None — Savant rolling lacks OPS
        "xwoba": _val_pct(rolling.get("xwoba"), "xwoba", "batter"),
        "barrel_pct": _val_pct(rolling.get("barrel_pct"), "barrel_pct", "batter"),
        "hh_pct": _val_pct(rolling.get("hh_pct"), "hh_pct", "batter"),
        "bbe": int(rolling.get("bbe", 0) or 0),
        "pa": int(rolling.get("pa", 0) or 0),
    }
```

**Design 期望**（§3.2 anchor schema rolling_14d block）：

```json
"rolling_14d": {
  "ops": ..., "avg": ..., "obp": ..., "slg": ...,
  "hr": ..., "rbi": ..., "r": ...,
  "bb_pct": ..., "k_pct": ...,
  "k_spike_pp": ..., "delta_xwoba": ...,
  "pa": ..., "bbe": ...
}
```

**現況**:
- Schema 只含 Savant rolling 4 項（xwoba / barrel / hh / pa / bbe）
- 缺：MLB API 14d trad（hr / rbi / r / sb / bb / k / k_pct / avg / obp / slg / k_spike_pp / delta_xwoba）
- 所以 multi-agent 上線時看不到「14d OPS .947 / 14d HR 2 / K% spike +5.9pp」這類 trad 訊號

**為什麼 deferred 不是 critical**:
- Commit 訊息明示：「Wired up by future Phase 6 multi-agent path; ship now for review/test ahead of orchestrator work」
- 多 agent 編排尚未啟用，目前 fa_scan production 走的是 `_build_pass2_data_batter_v4`（單 LLM，已含完整 trad）
- 所以 multi-agent enrich 的不完整在當前不影響行為

**建議**:
- 多 agent 層上線前（即 §13.2 開工選項 B / C 啟動時），需擴充 `_player_to_v4_schema` 的 `rolling_block`：
  - 把 `enrich_14d_trad` 結果合併進 rolling_block
  - 加 `k_spike_pp = trad.k_pct - season.k_pct`
  - 加 `delta_xwoba = rolling_savant.xwoba - season.xwoba`
- 預估工作量：30-60 分鐘

### Finding F2 — `sum_diff` 仍用作 FA 排序 hint

**檔案**: `daily-advisor/fa_scan.py:2796` (`_build_pass2_data_batter_v4`)

**Code**:
```python
fa_sorted = sorted(fa_tagged, key=lambda x: -x.get("sum_diff", 0))
```

**Design 哲學**:
- §1.1：「Sum 只在機械層內部使用，不暴露給 agent」
- §3.5「不算 Sum 差 vs anchor」(讓 agent 自己看 raw 比)

**現況評估**:
- `sum_diff` 是排序 key，**不是顯示給 agent 的欄位**
- LLM 看到的是「排序好的 FA list」，看不到 sum_diff 數字本身
- 嚴格說違反「不算 Sum 差」的精神，但只是 ordering hint

**多 agent 層上線時應該怎麼處理**:
- Multi-agent step 3 classify 是 per-FA 獨立評估（沒 ordering 概念），所以 sum_diff 不需要
- Multi-agent step 4 rank 是 3 agent 看完整 raw 自由排序，也不需要 sum_diff
- **多 agent 上線時這個 sort 應該移除**（FA 順序按其他指標如 %owned 或乾脆不排序）

**建議**: 多 agent 層上線時把這條 sort 拿掉。當前過渡期保留無妨（單 LLM 看了 raw 仍會自行 reason，sum_diff 排序只是視覺 hint）。

---

## 🟢 Minor / 無需 Action

### Finding M1 — BBE 估算為 AB - K

**檔案**: `daily-advisor/fa_scan.py:1591`

```python
bbe = max(ab - k, 0)
```

**Design**: §3.2 schema 標 `bbe`（無精確算法說明）。

**現況**: docstring 已記載「approximated as AB - K (ignores SF, HBP — within ±1-2 BBE)」。誤差 ±1-2 BBE 在 BBE 大小決策（門檻 40）旁邊微不足道。

**結論**: OK，已 documented。

### Finding M2 — PA-TG 顯示給 LLM

**檔案**: `daily-advisor/fa_scan.py:2617`

```python
lines = [f"... [PA {pa_2026} / PA-TG {pa_tg_str} / BBE {bbe}]"]
```

**Design**: §3.2 schema 含 `pa_per_tg`，§3.5 說「PA/TG 進 urgency 計分」拋棄 — 但 schema 仍含 PA-TG 作為 context。

**結論**: 顯示作 context，**不算分**，符合 §3.6「不暴露給 agent 的是分數，raw 數據可以」原則。OK。

### Finding M3 — Slump hold 移除自動偵測，但 `prior_sum` 仍計算

**檔案**: `daily-advisor/fa_compute.py:399-414`

```python
if player_type == "batter":
    passthrough = []
    for w in weakest_n:
        prior = w.get("prior_stats") or {}
        sum_2025, prior_breakdown = compute_2025_sum(prior, "batter")
        passthrough.append({
            **w,
            "urgency": None,
            "factors": {},
            "prior_sum": sum_2025,    # ← still computed
            ...
        })
```

**Design**: §1.2「Slump hold 自動偵測（2025 Sum ≥24）」拋棄 → 改 cant_cut。

**現況**:
- 沒有自動 slump_hold 排除 ✓
- `prior_sum` 仍算出來 — 但只是 backward-compat 給 callers iterate
- 不會用 prior_sum 做 hold 判斷 ✓

**結論**: OK，schema 穩定不破壞 callers。Sum 在內部運算路徑上停留（filter 用），不暴露給 agent。

---

## 結構性 Compliance Audit（design vs code）

對 design doc 主要章節逐項打勾：

| Design § | 規定 | Implementation | 狀態 |
|---|---|---|---|
| §1.1 機械層輸出 | 無 Sum / 無 score | enrich_for_multi_agent_batter schema 無 sum/score | ✓ |
| §1.2 拋棄 urgency 4-factor | 完全移除 | compute_urgency batter 改 passthrough | ✓ |
| §1.2 拋棄 ✅⚠️ tag 層 | 移除 | _compute_batter_add/warn_tags 只剩 PA-based | △ (D1 doc 不一致) |
| §1.2 拋棄 PA/TG 進 urgency | 移除計分 | passthrough 不算 PA/TG | ✓ |
| §1.2 拋棄 Sum 出現在 anchor output | 不暴露 | enrich schema 無 score | ✓ |
| §1.2 拋棄 守位/status 進評估 | 不過濾不 surface | enrich schema 無 positions/status | ✓ |
| **§1.2 拋棄 守位顯示** | 不該 surface | **`_fmt_*_block_v4` 顯示 positions** | **✗ C1** |
| §1.2 拋棄 Slump hold 自動偵測 | 改 cant_cut | 自動偵測移除，靠 cant_cut | ✓ |
| §1.3 保留 Sum 計算（內部）| filter 用 | pick_weakest 仍算 Sum 給 ≥25 filter | ✓ |
| §1.3 保留 cant_cut 排除 | hardcode list | roster_config 加 Machado | ✓ |
| §1.3 保留 BBE <40 排除 | hard rule | _BATTER_BBE_MIN = 40 | ✓ |
| §1.3 保留 2026 Sum ≥25 排除 | hard rule | _BATTER_SUM_HARD_FLOOR = 25 | ✓ |
| §3.1 pick_weakest 不限人數 | 全部 Sum<25 進池 | 移除 n cap，回傳全部 surviving | ✓ |
| §3.1 特殊：pool 0 / 1-3 / >3 | 跳過 / 排所有 / top 3 | pool 0 印「池為空」訊息 | ✓ |
| §3.2 anchor schema 完整 | raw + percentile + 14d + prior | enrich_for_multi_agent rolling_14d 缺 trad | △ F1 |
| §3.4 FA schema 含 owned | shape 4 種 | enrich_owned_trend 有實作 | ✓ |
| §3.6 master 雙 output | downstream + report_metadata | **未實作**（多 agent 層尚未上線）| (deferred) |
| §3.7 value_to_pctile | reverse-direction 自動偵測 | implementation 邏輯 OK | ✓ |
| §4 multi-agent 8-step | 整套流程 | **未實作**（單 LLM 過渡期）| (deferred) |

---

## Action Items 排序建議

### 立即（在當前 thin 路徑 production 跑時）

1. **🔴 修 Finding C1 — 移除 positions 顯示**
   - `_fmt_anchor_block_batter_v4` + `_fmt_fa_block_batter_v4` 兩處
   - 約 10 行改動，1 commit
   - 風險：低（純顯示移除）
   - 影響：當前 thin 路徑 LLM reasoning 更貼近設計原則

### 在 design doc commit 補正

2. **🟡 修 Finding D1 — Design §3.4 補充「保留 PA-based tags」**
   - 編輯 `docs/batter-framework-upgrade-design.md` §3.4 「明確不出現的欄位」
   - 改：「❌ tags」→「❌ data-based tags（14d/xwOBA/luck 相關），✅ 保留 PA-based gate tags（球隊主力 / 上場有限）」

### Multi-agent 層上線前（design doc §13.2 選項 B/C 啟動時）

3. **🟠 修 Finding F1 — enrich_for_multi_agent_batter 補完 14d trad**
   - 把 `enrich_14d_trad` 結果合併進 rolling_block
   - 加 k_spike_pp + delta_xwoba 計算
   - 約 20-30 行新 code

4. **🟠 修 Finding F2 — 移除 sum_diff sort（multi-agent 不需要）**
   - 多 agent path 啟動時拿掉
   - 1 行改動

### 不需 action

5. M1 / M2 / M3 — 已 documented 或 by design

---

## 推薦給用戶的下一步

**選 A — 立即修 C1（推薦）**：
- 影響小但符合設計原則
- 1 個 small commit (`fix(fa_scan): remove positions from batter v4 thin display`)
- 跟現役 production 並行不影響

**選 B — 連同 D1 一起補正 design + code**：
- C1 implementation fix
- D1 design doc clarify
- 2 個 commits（一個 fix 一個 docs）

**選 C — 先觀察 production 跑 1-2 天看 LLM 行為再決定**：
- 看 LLM 在 Pass 2 reasoning 中是否真的用了守位資訊
- 用了 → 確認需要修
- 沒用 → C1 可降級為「nice to have」延後處理

我建議 **B**：C1 是真實設計違背，趁同 session 連 D1 一起修，2 個 commits 收尾乾淨。

---

## Sign-off

- 整體實作品質：高
- Design 對齊度：~90%（1 critical + 2 doc inconsistency）
- 過渡期可正常運行
- Multi-agent 層上線前需補 F1 / F2

Reviewer 結論：**可繼續觀察 production 行為**，C1 修正建議在下次 batter 相關 commit 順手帶。
