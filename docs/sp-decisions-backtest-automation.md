# SP 決策回測自動化機制 design

> **Status**：設計文檔（2026-04-25）。non-blocking — 動工時機 v4 cutover 後 1-2 月（CLAUDE.md TODO 已標）。
> **目的**：把 `docs/sp-decisions-backtest.md` 手動 living log 升級為半自動 + 把「21d Δ xwOBACON 絕對門檻校準」的 archive-mining 工作落地。

---

## 1. 雙重 use case

### 1.1 Use case A：backtest 條目「後續走勢」半自動化

`docs/sp-decisions-backtest.md` 9 筆決策，每筆有「後續走勢（每 2 週更新）」欄位，**目前手動更新**。當 entries 累積到 20+ 筆，手動更新成本爆炸。

**目標**：寫腳本生成「後續走勢」段落 markdown，user review 後 commit。

### 1.2 Use case B：21d Δ xwOBACON 門檻校準

CLAUDE.md TODO（2026-04-25 鎖定）：

> v4 上線後 Python `_factor_rolling` 暫返回 0...原始 Δ + BBE 餵 Claude 用絕對量級提示判斷（|Δ| <0.030 / 0.030-0.050 / ≥0.050）。校準路徑：累積 1-2 個月後從 GitHub Issue archive 反推全期 SP 21d Δ xwOBACON **絕對門檻**

**目標**：寫 archive-miner 腳本累計**所有歷史 fa_scan SP 條目** 的 21d Δ xwOBACON + 後續 N 週實際變化 → 算「應驗率」分布 → 反推合理門檻。

兩個 use case 共用基礎設施（archive 解析 + stats fetch），但下游分析不同。

---

## 2. 既有素材盤點

### 2.1 GitHub Issue archive

每天 fa_scan 推送一份 GitHub Issue（CLAUDE.md「資料流」章節）：
```
[FA Scan Daily] 2026-04-25
[FA Scan Daily SP] 2026-04-25
[FA Scan Weekly RP] 2026-04-21
```

每份 Issue body 含：
- 我方最弱 SP P1-P4（含 Sum / urgency / tag）
- FA 候選（含 Sum / sum_diff / tag）
- 21d xwOBA Δ（從 savant_rolling.json 注入）
- 推薦 action

**未來 v4 cutover 後** Issue 也會含 21d Δ xwOBACON。

### 2.2 stats fetch infrastructure

已就緒：
- `daily-advisor/savant_rolling.py` — 任意日期 N 天窗口 fetch xwoba/xwobacon（v4 cutover 後）
- `daily-advisor/yahoo_query.py` — Yahoo API（轉隊 / 異動）
- MLB Stats API — game log

### 2.3 backtest doc 結構

`docs/sp-decisions-backtest.md` 是 markdown，每 entry 有固定 schema：
- `### N. {決策名}（{日期}）`
- `**決策**：` / `**執行方**：` / `**框架依據**：` / `**當時數據**：`
- `**回測問題**：` (list)
- `**後續走勢**：` 或 `**後續走勢（YYYY-MM-DD 更新）**：`
- `**回測判定**：`

可被正規 parse（regex + heading split）。

---

## 3. Use case A 自動化架構

### 3.1 腳本：`daily-advisor/backtest_track.py`

```python
"""backtest_track — generate auto-fills for sp-decisions-backtest.md.

Reads each entry, identifies the player by mlb_id (from CLAUDE.md or
roster_config.json or hand-tagged), fetches stats from decision date
to today, generates a "後續走勢" markdown block. User reviews + edits
before commit.

Usage:
  python3 backtest_track.py --dry-run             # generate to stdout
  python3 backtest_track.py --update-doc          # write back to doc
  python3 backtest_track.py --entry 4             # only entry #4
"""
```

### 3.2 資料模型

每 entry 抽出：

```python
@dataclass
class BacktestEntry:
    number: int                        # "### 4. Nola..."
    title: str                         # "Nola 結構性 cut → hold"
    decision_date: date                # 從 (YYYY-MM-DD) 抽
    last_update_date: date | None      # 從 後續走勢（YYYY-MM-DD 更新）抽
    player_names: list[str]            # 主角（regex 或 hand-tag）
    player_mlb_ids: list[int]          # 從 player_names + roster_config 解析
    backtest_questions: list[str]      # 回測問題 list
    raw_followup: str                  # 既有「後續走勢」原文
```

### 3.3 後續走勢生成邏輯

```python
def generate_followup(entry: BacktestEntry, today: date) -> str:
    """Build a markdown section for the entry's followup."""
    blocks = []
    for pid in entry.player_mlb_ids:
        # Pull stats from decision_date to today
        decision_to_now = fetch_savant_window(pid, entry.decision_date, today)
        # Compare to decision-day snapshot (parsed from "**當時數據**" or fa_scan archive)
        decision_snapshot = parse_decision_snapshot(entry, pid)
        diff = compute_diff(decision_snapshot, decision_to_now)
        blocks.append(format_player_block(name=..., diff=diff))
    return f"**後續走勢（{today} 更新）**：\n" + "\n".join(blocks)
```

### 3.4 Player ID resolution

`backtest_track.py` 需要 entry → mlb_id 對應。三種來源（fallback 順序）：

1. **明確 hand-tag**：在 entry 加 markdown comment `<!-- mlb_id: 605400, 666774 -->`（最穩）
2. **roster_config.json 名字反查**：當前隊上球員可查到
3. **MLB API search**：未在 roster 也能查（同名同姓風險）

### 3.5 輸出範例

對 Entry 4（Nola hold）：

```markdown
**後續走勢（2026-05-15 更新）**：
- Nola（605400）04-23 → 05-15 共 4 GS：
  - IP/GS 5.45（決策當時 5.33，+0.12）
  - xwOBA .332（當時 .342，-0.010）
  - xwOBACON .395（當時 .424，**-0.029**）✅ 接觸品質改善
  - K/9 8.55（當時 8.21，+0.34）
  - 21d Δ xwOBACON: -0.025（持平到弱回升範圍）
- 速度（avg FB velo）：91.2 → 91.8 mph（+0.6，速度回升）
- 是否被搶：仍隊上
- vs 候選 Pfaadt（684007）04-23 → 05-15 共 3 GS：
  - K/9 5.5 → 7.2 ⬆️
  - xwOBACON .345 → .328 ⬆️
  - **Pfaadt K 確實起來了**

**自動標記**：✅ 三視角預測 Nola 反彈方向**部分驗證**（速度 + xwOBACON 改善），Pfaadt K 起來印證 04-24 v4 升級候選判斷
```

下面 user 自行寫「**回測判定**：」段落，因為判定是綜合判斷不全自動。

### 3.6 實作要點

- **冪等**：腳本可重複跑，每次更新「最新一份」followup（不累加）
- **diff-based update**：把 entry 的 followup 段落整段替換（regex 識別 `**後續走勢` 到下個 `**回測判定`）
- **dry-run 預設**：避免誤改 doc

---

## 4. Use case B 21d Δ xwOBACON 門檻校準

### 4.1 腳本：`daily-advisor/calibrate_xwobacon_threshold.py`

```python
"""calibrate_xwobacon_threshold — backfill xwobacon delta thresholds from archive.

Goes through all GitHub Issue archive (last N months), extracts (player,
date, 21d_delta_xwobacon, BBE) tuples for SPs in that day's fa_scan,
then fetches the actual xwobacon trajectory in the next 21 days post-
decision. Computes "validation rate" by absolute Δ magnitude buckets.

Usage:
  python3 calibrate_xwobacon_threshold.py --since 2026-03-26
  python3 calibrate_xwobacon_threshold.py --plot   # matplotlib distribution
"""
```

### 4.2 資料抽取

對每份 Issue：

```python
def parse_fa_scan_issue(issue_body: str) -> list[SPDecisionRecord]:
    """Parse one daily fa_scan Issue, return list of SP records.

    Each record: {
        date: date,
        player_name: str,
        mlb_id: int,
        my_or_fa: "my" | "fa",
        sum_score: int,
        delta_xwobacon_21d: float | None,
        bbe_21d: int | None,
        action: str,  # "drop" / "hold" / "watch" / etc.
    }
    """
```

### 4.3 後續 trajectory fetch

對每筆 record，在 record.date + 21 天內：
- 重抓 21d xwobacon 窗口（end_date = record.date + 21 天）
- diff = post_window_xwobacon - record.xwobacon_at_decision
- 標記 trajectory：
  - `improved`：diff <= -0.020
  - `stable`：-0.020 < diff < +0.020
  - `worsened`：diff >= +0.020

### 4.4 應驗率計算

對每個 |Δ_at_decision| 桶（5 個桶：[0, 0.020) / [0.020, 0.030) / [0.030, 0.050) / [0.050, 0.080) / [0.080, ∞)）：

```python
def validation_rate(records, bucket_lo, bucket_hi):
    """For records with |Δ| ∈ [lo, hi), what % were predicted correctly?"""
    in_bucket = [r for r in records if bucket_lo <= abs(r.delta) < bucket_hi]
    correct = []
    for r in in_bucket:
        if r.delta < 0:  # 當下訊號 = improving
            correct.append(r.trajectory == "improved")
        else:  # 當下訊號 = worsening
            correct.append(r.trajectory == "worsened")
    return sum(correct) / len(correct) if correct else None
```

### 4.5 輸出：絕對門檻建議

```
=== 21d Δ xwOBACON Validation Report ===
Period: 2026-03-26 → 2026-05-25 (60 days)
Total SP records: 423

Bucket           | Sample N | Validation Rate | Verdict
-----------------|----------|-----------------|--------
|Δ| < 0.020      |    187   |    52% (noise) | Below threshold
0.020 ≤ |Δ| < 0.030 |  98   |    58% (weak)  | Below threshold
0.030 ≤ |Δ| < 0.050 |  78   |    71%         | Possible weak threshold
0.050 ≤ |Δ| < 0.080 |  44   |    81%         | Strong threshold candidate
|Δ| ≥ 0.080      |    16   |    88%         | Reliable threshold

Recommendation:
- Weak threshold: |Δ| ≥ 0.040 (interpolated, ~75% validation)
- Strong threshold: |Δ| ≥ 0.060 (interpolated, ~83% validation)

Compare to current rule (|Δ| ≥ 0.030 / 0.050 in v2 batter framework):
- Current weak threshold (0.030) too lax — only 58% validates
- Current strong threshold (0.050) about right (81%)
```

### 4.6 落地：CLAUDE.md prompt 更新

校準後改 `prompt_fa_scan_pass2_sp.txt`（按 v4 cutover plan §5.3）：

```
舊：|Δ| < 0.030 = 小變動 / 0.030-0.050 = 中等 / ≥0.050 = 明顯
新：|Δ| < 0.040 = 噪音 / 0.040-0.060 = 中等可考慮 / ≥0.060 = 可靠訊號
```

**只改 prompt，不改 code** — 校準後的門檻寫進 prompt 給 Claude 用，Python `_factor_rolling` 仍返 0（CLAUDE.md TODO 已鎖定）。

---

## 5. 共用基礎模組

```python
# daily-advisor/_backtest_lib.py（新模組）

def fetch_github_issue_archive(since: date, until: date = None) -> list[Issue]:
    """gh issue list --search 'label:fa-scan-daily' --json ..."""

def parse_fa_scan_issue_body(body: str) -> list[SPDecisionRecord]:
    """Regex extract SP records from Issue markdown."""

def fetch_player_window(mlb_id: int, start: date, end: date) -> dict:
    """Wrap savant_rolling.fetch_savant_rolling for arbitrary windows."""

def parse_backtest_entries(doc_path: Path) -> list[BacktestEntry]:
    """Parse docs/sp-decisions-backtest.md."""
```

兩個 use case 都依此模組。Use case A 用 `parse_backtest_entries` + `fetch_player_window`；Use case B 用 `fetch_github_issue_archive` + `parse_fa_scan_issue_body` + `fetch_player_window`。

---

## 6. 1Password / gh auth 風險

**警告**：Use case B 大量呼叫 `gh issue` 取得歷史 archive。

- VPS 有 gh PAT 配置，token 不過期前 fine
- 本機跑可能踩 1Password 授權（CLAUDE.md learnings：「gh auth token 統一」）
- 建議：腳本跑在 VPS（cron 或手動 ssh），不在本機跑

或：把 `gh issue list` 結果先 dump 為 JSON 檔（用戶在 VPS 跑一次 export），本機讀 dump 分析（離線可重複）。

---

## 7. 實作優先序

| 模組 | 優先序 | 觸發條件 |
|------|-------|---------|
| `_backtest_lib.py`（共用模組）| **1** | 任 use case 動工前必先 |
| `backtest_track.py`（Use case A）| **2** | backtest doc 累積 > 15 entries 或手動更新 ≥3 次 |
| `calibrate_xwobacon_threshold.py`（Use case B）| **3** | v4 cutover 後 1-2 月（CLAUDE.md TODO 觸發點）|

**估計工時**：
- 共用模組：3-5 hr
- Use case A：3-4 hr
- Use case B：5-7 hr

---

## 8. 不在範圍內的事

- **判定自動化**：「✅ 正確 / ⚠️ 部分對 / ❌ 判錯」這個結論 user 自己寫，腳本只給 raw data
- **跨框架版本比對**：v2/v3/v4 對同一 SP 的判斷差異分析屬於另一份 doc
- **打者 backtest**：本設計只 SP（symmetrical 但範圍另算）
- **Live dashboard**：不做 web UI，只 markdown / stdout

---

## 9. 與現有文件的關聯

| 本 doc | 關聯 |
|--------|------|
| 自動化目標 | `docs/sp-decisions-backtest.md`（手動 living log，本 doc 是其升級版）|
| Use case B 動機 | CLAUDE.md TODO「SP 21d Δ xwOBACON 絕對門檻校準」|
| Stats fetch 共用 | `daily-advisor/savant_rolling.py` |
| Issue archive 共用 | fa_scan.py 推送邏輯 |
| Phase 6 / v4 後置 | `docs/v4-cutover-plan.md` Stage F 之後 1-2 月 |

---

## 10. Action items（觸發時動工）

- [ ] 寫 `daily-advisor/_backtest_lib.py`（共用模組）
- [ ] 寫 `daily-advisor/backtest_track.py`（Use case A）
- [ ] 跑 use case A 一次更新 `docs/sp-decisions-backtest.md`，確認半自動工作流順暢
- [ ] 寫 `daily-advisor/calibrate_xwobacon_threshold.py`（Use case B）
- [ ] 跑 use case B 一次累計 60 天 archive，產出絕對門檻建議
- [ ] 依建議改 `prompt_fa_scan_pass2_sp.txt`（不改 code）
- [ ] 移除 CLAUDE.md「SP 21d Δ xwOBACON 絕對門檻校準」TODO（標 ✅ 完成）
