# FA Scan Batch 2: Core Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge weekly_scan.py + fa_watch.py into unified fa_scan.py with two-pass Claude architecture, %owned risers source, waiver-log watch integration, and --rp/--snapshot-only/--cleanup modes.

**Architecture:** fa_scan.py is the single FA analysis entry point. Default mode runs daily (Batter + SP) with parallel Step A (FA candidates) + Step B (Claude Pass 1: pick weakest roster players), then Step C (Claude Pass 2: compare). RP is a separate `--rp` weekly mode. Functions from fa_watch.py are absorbed; fa_watch.py is deprecated.

**Tech Stack:** Python 3, MLB Stats API, Baseball Savant CSV, Yahoo Fantasy API, Claude CLI (`claude -p`), GitHub CLI (`gh`)

**Branch:** `feat/fa-scan-refactor`

**Spec:** `docs/fa-scan-redesign.md` — the authoritative design document. Refer to it for all design decisions.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `daily-advisor/fa_scan.py` | **Create** (copy from weekly_scan.py, then refactor) | Unified FA scanning: Layer 1-2-3, two-pass Claude, all modes |
| `daily-advisor/weekly_scan.py` | **Delete** after fa_scan.py is verified | Replaced by fa_scan.py |
| `daily-advisor/fa_watch.py` | **Keep but deprecate** (add deprecation note) | Functions still imported during transition; Batch 3 will remove |
| `daily-advisor/prompt_fa_scan_pass1.txt` | **Create** | Pass 1 prompt: pick weakest batters/SP from roster |
| `daily-advisor/prompt_fa_scan_pass2_batter.txt` | **Create** | Pass 2 batter prompt: FA + watch vs weakest batters |
| `daily-advisor/prompt_fa_scan_pass2_sp.txt` | **Create** | Pass 2 SP prompt: FA + watch vs weakest SP |
| `daily-advisor/prompt_fa_scan_rp.txt` | **Create** | RP mode prompt: FA RP vs my 2 RP |
| `daily-advisor/weekly_review.py` | **Modify** | Update `fetch_scan_summary()` label from `waiver-scan` to `fa-scan` |

---

## Important: Read before implementing

1. Read `docs/fa-scan-redesign.md` thoroughly — it defines all Layer 1/2/3 specs, Pass 1/2 logic, RP mode, error handling
2. Read `CLAUDE.md` "球員評估框架" section — prompts must reference this framework
3. Read current `daily-advisor/weekly_scan.py` — most Layer 1/2/3 code is reused
4. Read current `daily-advisor/fa_watch.py` — functions to absorb: `collect_fa_snapshot`, `load/save_fa_history`, `calc_owned_changes`, `parse_waiver_log_watchlist`, `cleanup_rostered_watchlist`, `format_change_rankings`

---

### Task 1: Create fa_scan.py from weekly_scan.py

Copy weekly_scan.py → fa_scan.py, update module docstring and imports. This task only renames — no logic changes yet.

**Files:**
- Create: `daily-advisor/fa_scan.py` (copy from `daily-advisor/weekly_scan.py`)
- Modify: `daily-advisor/weekly_review.py:670` (label change)

- [ ] **Step 1: Copy file**

```bash
cp daily-advisor/weekly_scan.py daily-advisor/fa_scan.py
```

- [ ] **Step 2: Update module docstring in fa_scan.py**

Replace the first docstring:

```python
"""Weekly Deep Scan — FA market analysis with Statcast quality filter."""
```

With:

```python
"""FA Scan — unified FA market analysis with two-pass Claude architecture.

Modes:
    python fa_scan.py                   # Daily: Batter + SP scan (default)
    python fa_scan.py --rp              # Weekly: RP scan (Monday only)
    python fa_scan.py --snapshot-only   # Daily: %owned snapshot only
    python fa_scan.py --cleanup         # Manual: clean rostered watchlist players

Cron: 每天 TW 12:30 (UTC 04:30)。--rp 僅週一。--snapshot-only 每天 TW 15:15。
"""
```

- [ ] **Step 3: Absorb fa_watch imports into fa_scan.py**

Currently fa_scan.py (copied from weekly_scan.py) imports from fa_watch:

```python
from fa_watch import (
    collect_fa_snapshot, load_fa_history, save_fa_history,
    calc_owned_changes, TPE,
)
```

Copy these functions directly from fa_watch.py into fa_scan.py (above the Layer 1 section), then remove the fa_watch import. Functions to copy:
- `collect_fa_snapshot()` (fa_watch.py:52-101)
- `load_fa_history()` (fa_watch.py:103-108)
- `save_fa_history()` (fa_watch.py:110-113)
- `calc_owned_changes()` (fa_watch.py:115-152)
- `format_change_rankings()` (fa_watch.py:155-193) — already modified in Batch 1 to remove fallers
- `parse_waiver_log_watchlist()` (fa_watch.py:192-217) + the `_WAIVER_PLAYER_RE` constant
- `cleanup_rostered_watchlist()` (fa_watch.py:329-443) + helper `_check_player_ownership()`
- `TPE` constant

Also need these Yahoo imports that fa_watch uses but weekly_scan doesn't currently import:

```python
from yahoo_query import (
    refresh_token, load_env, load_config,
    send_telegram, _normalize,
    extract_player_info, parse_player_stats,  # needed by collect_fa_snapshot
    _search_players,  # needed by cleanup_rostered_watchlist
    api_get,  # needed by collect_fa_snapshot and cleanup
    YAHOO_STAT_MAP,
    pitcher_type, calc_position_depth,  # needed by build_position_queries if kept
)
```

Merge with existing imports, remove duplicates.

- [ ] **Step 4: Update weekly_review.py label**

In `daily-advisor/weekly_review.py`, change line 670:

```python
"--label", "waiver-scan",
```

To:

```python
"--label", "fa-scan",
```

- [ ] **Step 5: Verify fa_scan.py imports work**

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
import fa_scan
print('Import OK')
print(f'Functions available: collect_fa_snapshot={hasattr(fa_scan, \"collect_fa_snapshot\")}, '
      f'parse_waiver_log_watchlist={hasattr(fa_scan, \"parse_waiver_log_watchlist\")}, '
      f'cleanup_rostered_watchlist={hasattr(fa_scan, \"cleanup_rostered_watchlist\")}')
"
```

Expected: Import OK, all functions available.

- [ ] **Step 6: Commit**

```bash
git add daily-advisor/fa_scan.py daily-advisor/weekly_review.py
git commit -m "feat: create fa_scan.py from weekly_scan.py, absorb fa_watch functions"
```

---

### Task 2: Update Layer 1 queries — add %owned risers + biweekly sort

**Files:**
- Modify: `daily-advisor/fa_scan.py`

Replace `WEEKLY_FA_QUERIES` with new query structure per redesign spec.

- [ ] **Step 1: Replace query constants**

Replace:

```python
WEEKLY_FA_QUERIES = [
    ("B-AR",  "status=A;position=B;sort=AR;count=50"),
    ("SP-AR", "status=A;position=SP;sort=AR;count=30"),
    ("RP-AR", "status=A;position=RP;sort=AR;count=25", "biweekly"),
    ("B-LW",  "status=A;position=B;sort=AR;sort_type=lastweek;count=30"),
    ("SP-LW", "status=A;position=SP;sort=AR;sort_type=lastweek;count=20"),
    ("RP-BW", "status=A;position=RP;sort=AR;sort_type=biweekly;count=25", "biweekly"),
]
```

With:

```python
# Batter + SP queries (default daily mode)
SCAN_QUERIES = [
    ("B-AR",  "status=A;position=B;sort=AR;count=50"),
    ("B-BW",  "status=A;position=B;sort=AR;sort_type=biweekly;count=30"),
    ("SP-AR", "status=A;position=SP;sort=AR;count=30"),
    ("SP-BW", "status=A;position=SP;sort=AR;sort_type=biweekly;count=30"),
]

# RP queries (--rp weekly mode only)
RP_QUERIES = [
    ("RP-AR", "status=A;position=RP;sort=AR;count=10", "biweekly"),
    ("RP-BW", "status=A;position=RP;sort=AR;sort_type=biweekly;count=10", "biweekly"),
]
```

- [ ] **Step 2: Add %owned risers collection function**

Add after `calc_owned_changes()`:

```python
def collect_owned_risers(history, today_str, position_filter=None, top_n=20, days=3):
    """Get top %owned risers from fa_history over N days.

    Args:
        position_filter: 'batter', 'sp', or None (all)
        top_n: max results
        days: lookback window (default 3d)

    Returns list of {name, team, position, pct, d_rise} sorted by rise desc.
    """
    sorted_dates = sorted(history.keys())
    if today_str not in sorted_dates:
        return []

    # Find reference date (>= days ago)
    ref_date = None
    for d in reversed(sorted_dates):
        if d < today_str:
            day_diff = (datetime.strptime(today_str, "%Y-%m-%d")
                        - datetime.strptime(d, "%Y-%m-%d")).days
            if day_diff >= days:
                ref_date = d
                break
            if ref_date is None:
                ref_date = d  # fallback: most recent before today

    if not ref_date:
        return []

    today_data = history.get(today_str, {})
    ref_data = history.get(ref_date, {})

    risers = []
    for name, info in today_data.items():
        ref = ref_data.get(name)
        if not ref:
            continue
        rise = info["pct"] - ref["pct"]
        if rise <= 0:
            continue
        pos = info.get("position", "")
        if position_filter:
            fa_type = _classify_fa_type(pos)
            if fa_type != position_filter:
                continue
        risers.append({
            "name": name,
            "team": info.get("team", ""),
            "position": pos,
            "pct": info["pct"],
            "d_rise": rise,
        })

    risers.sort(key=lambda x: x["d_rise"], reverse=True)
    return risers[:top_n]
```

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/fa_scan.py
git commit -m "feat(fa_scan): update Layer 1 queries + add %owned risers collection"
```

---

### Task 3: Add waiver-log watch integration

**Files:**
- Modify: `daily-advisor/fa_scan.py`

Watch players skip Layer 1-2, go directly to Layer 3 enrichment. Need to resolve mlb_id from name.

- [ ] **Step 1: Update `parse_waiver_log_watchlist()` to support mlb_id**

The waiver-log format will include optional mlb_id: `### Name (Team, Pos) [mlb_id:123456]`

Update the function (already copied in Task 1) to parse mlb_id if present:

```python
_WAIVER_PLAYER_RE = re.compile(
    r"### (.+?) \((\w+),\s*(.+?)(?:\)\s*\[mlb_id:(\d+)\]|\))"
)

def parse_waiver_log_watchlist():
    """Parse waiver-log.md '觀察中' section for player names + team + position + mlb_id."""
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if not os.path.exists(waiver_log_path):
        return []
    with open(waiver_log_path, encoding="utf-8") as f:
        content = f.read()
    players = []
    in_section = False
    for line in content.split("\n"):
        if line.startswith("## 觀察中"):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            break
        if in_section and line.startswith("### "):
            if "已在陣容" in line or "條件 Pass" in line:
                continue
            m = _WAIVER_PLAYER_RE.match(line)
            if m:
                entry = {
                    "name": m.group(1).strip(),
                    "team": m.group(2),
                    "position": m.group(3).split(")")[0].strip(),
                }
                if m.group(4):
                    entry["mlb_id"] = int(m.group(4))
                players.append(entry)
    return players
```

- [ ] **Step 2: Add function to resolve mlb_id for watch players**

```python
def _resolve_watch_mlb_ids(watchlist, savant_csvs):
    """Resolve mlb_id for watchlist players that don't have one.

    Uses Savant CSV name matching first, then MLB API search as fallback.
    """
    for w in watchlist:
        if w.get("mlb_id"):
            continue
        # Try Savant CSV name match
        name_norm = _normalize(w["name"])
        for csv_key in ("batter_sc", "batter_ex", "pitcher_sc", "pitcher_ex"):
            name_idx, id_idx = savant_csvs.get(csv_key, ({}, {}))
            if name_norm in name_idx:
                w["mlb_id"] = name_idx[name_norm]
                break
        if not w.get("mlb_id"):
            # Fallback: MLB API search
            w["mlb_id"] = search_mlb_id(w["name"])
    return [w for w in watchlist if w.get("mlb_id")]
```

- [ ] **Step 3: Add function to enrich watch players (Layer 3 only)**

```python
def enrich_watch_players(watchlist, savant_2026, config):
    """Enrich waiver-log watch players — skip Layer 1-2, direct to Layer 3.

    Returns list in same format as enrich_layer3 output.
    """
    if not watchlist:
        return []

    standings = _fetch_team_games()
    enriched = []

    for w in watchlist:
        mlb_id = w["mlb_id"]
        fa_type = _classify_fa_type(w["position"])
        group = "hitting" if fa_type == "batter" else "pitching"

        p = {
            "name": w["name"],
            "team": w["team"],
            "position": w["position"],
            "mlb_id": mlb_id,
            "fa_type": fa_type,
            "pct": w.get("pct", 0),
            "source": "watch",
        }

        # Layer 3 enrichment (same logic as enrich_layer3)
        p["savant_2026"] = _extract_savant_by_id(mlb_id, fa_type, savant_2026)
        p["mlb_2026"] = fetch_mlb_season_stats(mlb_id, 2026, group)

        # 2025 prior
        savant_2025_csvs = download_savant_csvs(2025)  # TODO: cache if already downloaded
        p["savant_2025"] = _extract_savant_by_id(mlb_id, fa_type, savant_2025_csvs)
        p["mlb_2025"] = fetch_mlb_season_stats(mlb_id, 2025, group)

        # Derived metrics
        s26 = p.get("savant_2026")
        p["derived_2026"] = (
            _compute_derived_batter(p["mlb_2026"], standings, w["team"], 2026)
            if fa_type == "batter" else
            _compute_derived_pitcher(s26, p["mlb_2026"], standings, w["team"], 2026, fa_type,
                                     mlb_id=mlb_id)
        )

        enriched.append(p)
        time.sleep(0.2)

    return enriched
```

Note: The `download_savant_csvs(2025)` call should be cached. In the main flow, 2025 CSVs are already downloaded by `enrich_layer3()`. Consider passing them in or caching at module level. Implementation detail — Builder can decide the simplest approach (e.g., module-level cache dict).

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/fa_scan.py
git commit -m "feat(fa_scan): add waiver-log watch integration with mlb_id resolution"
```

---

### Task 4: Build roster data for Pass 1

**Files:**
- Modify: `daily-advisor/fa_scan.py`

Restructure `build_roster_summary()` to output structured data (not just display text) that Pass 1 Claude can consume.

- [ ] **Step 1: Add `build_roster_for_pass1()` function**

This replaces `build_roster_summary()` for the two-pass flow. It produces a structured string showing bottom batters and bottom SP with Savant data + percentile tags, suitable for Claude to pick weakest.

```python
def build_roster_for_pass1(config, savant_2026, player_type="batter"):
    """Build roster data string for Pass 1 (Claude picks weakest players).

    Args:
        player_type: "batter" or "sp"

    Returns formatted string with bottom N players sorted by quality.
    """
    if player_type == "batter":
        players = config.get("batters", [])
        hide_top = 5
        sort_key = "xwoba"
        higher_better = True
    else:
        players = [p for p in config.get("pitchers", [])
                   if pitcher_type(p) == "SP"]
        hide_top = 3
        sort_key = "xera"
        higher_better = False

    # Get Savant data for sorting
    scored = []
    for p in players:
        mlb_id = p.get("mlb_id")
        if not mlb_id:
            continue
        savant = _extract_savant_by_id(mlb_id, player_type if player_type == "batter" else "sp", savant_2026)
        val = savant.get(sort_key) if savant else None
        # Fallback to prior year
        if val is None or val == 0:
            prior = p.get("prior_stats", {})
            val = prior.get(sort_key, prior.get("xwoba", prior.get("xera")))
        scored.append({"player": p, "savant": savant, "sort_val": val})

    # Sort: batter by xwOBA asc (worst first), SP by xERA desc (worst first)
    scored.sort(key=lambda x: x["sort_val"] or (0 if higher_better else 999),
                reverse=(not higher_better))

    # Hide top N (strongest)
    shown = scored[:-hide_top] if len(scored) > hide_top else scored

    # Format output
    lines = []
    for item in shown:
        p = item["player"]
        s = item["savant"] or {}
        name = p["name"]
        team = p["team"]
        pos = "/".join(p.get("positions", [])) if player_type == "batter" else "SP"

        parts = [f"{name}({team}) {pos}"]

        if player_type == "batter":
            if s.get("xwoba"):
                parts.append(f"xwOBA {s['xwoba']:.3f} {pctile_tag(s['xwoba'], 'xwoba')}")
            if s.get("barrel_pct"):
                parts.append(f"Barrel% {s['barrel_pct']:.1f}% {pctile_tag(s['barrel_pct'], 'barrel_pct')}")
            if s.get("hh_pct"):
                parts.append(f"HH% {s['hh_pct']:.1f}% {pctile_tag(s['hh_pct'], 'hh_pct')}")
            parts.append(f"BBE {s.get('bbe', 0)}")
        else:
            if s.get("xera"):
                parts.append(f"xERA {s['xera']:.2f} {pctile_tag(s['xera'], 'xera', 'pitcher')}")
            if s.get("xwoba"):
                parts.append(f"xwOBA {s['xwoba']:.3f} {pctile_tag(s['xwoba'], 'xwoba', 'pitcher')}")
            if s.get("hh_pct"):
                parts.append(f"HH% {s['hh_pct']:.1f}% {pctile_tag(s['hh_pct'], 'hh_pct', 'pitcher')}")
            parts.append(f"BBE {s.get('bbe', 0)}")

        lines.append("  " + " | ".join(parts))

    header = f"[{'打者' if player_type == 'batter' else 'SP'}] 以下為可能被替換的球員（由弱到強）："
    return header + "\n" + "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/fa_scan.py
git commit -m "feat(fa_scan): add build_roster_for_pass1 for two-pass Claude architecture"
```

---

### Task 5: Create Pass 1 prompt

**Files:**
- Create: `daily-advisor/prompt_fa_scan_pass1.txt`

Pass 1 is the same prompt for both batter and SP (called twice with different data). Claude picks the weakest N players.

- [ ] **Step 1: Write prompt file**

```
你是 Fantasy Baseball 陣容分析顧問。以下是我方陣容中可能被替換的球員（由弱到強排序）。

請從中挑出最應該被取代的球員：
- 打者：挑 4 人
- SP：挑 3 人

挑選標準（嚴格依序）：
1. Savant 品質數據（xwOBA / BB% / Barrel% 或 xERA / xwOBA allowed / HH% allowed）— 優先
2. 對計分類別的貢獻（打者：R/HR/RBI/BB/AVG/OPS，不含 SB。SP：IP/K/ERA/WHIP/QS，不含 W 和 SV+H）— 次要

輸出格式（JSON，不要多餘文字）：
```json
{
  "weakest": [
    {"name": "球員名", "reason": "一句話理由"}
  ]
}
```

---

{roster_data}
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/prompt_fa_scan_pass1.txt
git commit -m "feat(fa_scan): add Pass 1 prompt for weakest player selection"
```

---

### Task 6: Create Pass 2 prompts (batter + SP)

**Files:**
- Create: `daily-advisor/prompt_fa_scan_pass2_batter.txt`
- Create: `daily-advisor/prompt_fa_scan_pass2_sp.txt`

- [ ] **Step 1: Write batter Pass 2 prompt**

```
你是 Fantasy Baseball FA 市場分析顧問。12 隊 H2H One Win 7×7 聯賽。

以下資料包含：
1. 我方最弱 4 名打者（Pass 1 篩出）
2. FA 打者候選（通過 Savant 品質篩選）
3. waiver-log 觀察中打者（持續追蹤對象）
4. %owned 升幅排行（市場訊號）
5. waiver-log 完整內容（觸發條件記錄）

評估規則依數據中嵌入的「評估框架」，不偏離。

任務：
1. FA 候選 + 觀察中打者 vs 我方最弱 4 人，逐人比較核心 3 指標（xwOBA / BB% / Barrel%），2 項勝出 = 值得行動
2. 考慮守位需求（填什麼位？零替補風險？）和 PA/Team_G 產量
3. 觀察中打者：檢查 waiver-log 觸發條件是否接近達成
4. %owned 急升者：是否有品質支撐？快被搶？

逐人輸出（只列有意義的，無候選時回報「無明確升級」）：
- **取代** — 明確優於最弱球員 → 建議 add 誰 / drop 誰 / FAAB 出價
- **觀察** — 有潛力但需確認 → 建議觸發條件（例：BBE 達 50 後 xwOBA 仍 > P70 → 行動）
- **pass** — 不動

控制在 2000 字元以內。Telegram Markdown 格式。

---

{data}
```

- [ ] **Step 2: Write SP Pass 2 prompt**

```
你是 Fantasy Baseball FA 市場分析顧問。12 隊 H2H One Win 7×7 聯賽。

以下資料包含：
1. 我方最弱 3 名 SP（Pass 1 篩出）
2. FA SP 候選（通過 Savant 品質篩選）
3. waiver-log 觀察中 SP（持續追蹤對象）
4. %owned 升幅排行（市場訊號）
5. waiver-log 完整內容（觸發條件記錄）

評估規則依數據中嵌入的「評估框架」，不偏離。

任務：
1. FA 候選 + 觀察中 SP vs 我方最弱 3 人，逐人比較核心 3 指標（xERA / xwOBA allowed / HH% allowed），2 項勝出 = 值得行動
2. 考慮 IP/GS 產量（深投型 > 短局型）和 xERA-ERA 運氣標記（負值 = 撿便宜）
3. 觀察中 SP：檢查 waiver-log 觸發條件是否接近達成
4. %owned 急升者：是否有品質支撐？快被搶？

逐人輸出（只列有意義的，無候選時回報「無明確升級」）：
- **取代** — 明確優於最弱 SP → 建議 add 誰 / drop 誰 / FAAB 出價
- **觀察** — 有潛力但需確認 → 建議觸發條件
- **pass** — 不動

控制在 2000 字元以內。Telegram Markdown 格式。

---

{data}
```

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/prompt_fa_scan_pass2_batter.txt daily-advisor/prompt_fa_scan_pass2_sp.txt
git commit -m "feat(fa_scan): add Pass 2 prompts for batter and SP comparison"
```

---

### Task 7: Create RP prompt

**Files:**
- Create: `daily-advisor/prompt_fa_scan_rp.txt`

- [ ] **Step 1: Write RP prompt**

```
你是 Fantasy Baseball FA 市場分析顧問。12 隊 H2H One Win 7×7 聯賽。

RP 策略：維持 2 位，不為 SV+H 多拿 RP，但有更好替換應行動。
品質小輸也值得換（SV+H 獨立類別，多贏 1 類的價值 > 比率微降損失）。

以下資料包含：
1. 我方 2 名 RP（完整數據）
2. FA RP 候選（biweekly SV+H ≥ 2 + 品質篩選通過）

評估規則依數據中嵌入的「評估框架」，不偏離。

任務：
1. FA RP vs 我方 2 RP 逐人比較：
   - SV+H 產量（主要）
   - 品質指標（xERA / xwOBA allowed / HH% allowed），2026 為主、2025 為輔
2. 品質小輸但 SV+H 明顯多 → 值得換

逐人輸出：
- **取代** — 建議換誰 / FAAB 出價
- **觀察** — 附觸發條件
- **pass** — 不動

控制在 1000 字元以內。Telegram Markdown 格式。

---

{data}
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/prompt_fa_scan_rp.txt
git commit -m "feat(fa_scan): add RP mode prompt"
```

---

### Task 8: Rewrite main() — two-pass architecture + modes

**Files:**
- Modify: `daily-advisor/fa_scan.py` (main function — this is the core task)

This is the **highest-risk task**. The new main() orchestrates:
- Argument parsing (default / --rp / --snapshot-only / --cleanup)
- Step A: Layer 1-2-3 + watch players (parallel-ready)
- Step B: Pass 1 Claude (batter + SP separate)
- Step C: Pass 2 Claude (batter + SP separate)
- Error handling with Telegram notification
- Output to Telegram + GitHub Issue

- [ ] **Step 1: Update argument parser**

Replace existing parser with:

```python
def main():
    parser = argparse.ArgumentParser(description="FA Scan — unified FA market analysis")
    parser.add_argument("--rp", action="store_true", help="RP scan mode (weekly, Monday)")
    parser.add_argument("--snapshot-only", action="store_true", help="Only save %owned snapshot")
    parser.add_argument("--cleanup", action="store_true", help="Clean rostered watchlist players")
    parser.add_argument("--dry-run", action="store_true", help="Layer 1+2 only, skip Claude")
    parser.add_argument("--no-send", action="store_true", help="Skip Telegram + GitHub Issue")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()
```

- [ ] **Step 2: Implement mode dispatch**

After argument parsing:

```python
    env = load_env()
    access_token = refresh_token(env)
    config = load_config()
    today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")

    if args.snapshot_only:
        _run_snapshot_only(access_token, config, today_str, env)
        return

    if args.cleanup:
        cleanup_rostered_watchlist(access_token, config, today_str, env)
        return

    if args.rp:
        _run_rp_scan(access_token, config, today_str, env, args)
        return

    _run_daily_scan(access_token, config, today_str, env, args)
```

- [ ] **Step 3: Implement `_run_snapshot_only()`**

Migrate from fa_watch.py's snapshot-only mode:

```python
def _run_snapshot_only(access_token, config, today_str, env):
    """Save %owned snapshot + cleanup rostered watchlist."""
    print(f"[FA Scan] Snapshot-only {today_str}...", file=sys.stderr)
    queries = SCAN_QUERIES  # use same queries as daily scan for consistent pool
    snapshot = collect_fa_snapshot(access_token, config, queries=queries)
    history = load_fa_history()
    history[today_str] = {
        name: {"pct": info["pct"], "team": info["team"], "position": info["position"]}
        for name, info in snapshot.items()
    }
    sorted_dates = sorted(history.keys())
    if len(sorted_dates) > 14:
        for old_date in sorted_dates[:-14]:
            del history[old_date]
    save_fa_history(history)
    print(f"  Snapshot saved ({len(snapshot)} players)", file=sys.stderr)

    # Auto-cleanup rostered watchlist
    cleanup_rostered_watchlist(access_token, config, today_str, env)
    print("[FA Scan] Snapshot-only done.", file=sys.stderr)
```

- [ ] **Step 4: Implement `_run_rp_scan()`**

```python
def _run_rp_scan(access_token, config, today_str, env, args):
    """RP scan — weekly mode, single Claude call."""
    print(f"[FA Scan] RP scan {today_str}...", file=sys.stderr)

    try:
        # Layer 1: Yahoo RP queries
        snapshot = collect_fa_snapshot(access_token, config, queries=RP_QUERIES)

        # Add %owned risers (7d for RP)
        history = load_fa_history()
        rp_risers = collect_owned_risers(history, today_str, position_filter="rp", top_n=10, days=7)
        for r in rp_risers:
            if r["name"] not in snapshot:
                snapshot[r["name"]] = {"pct": r["pct"], "team": r["team"],
                                       "position": r["position"], "stats": {}}

        # Layer 2: Savant quality filter
        savant_2026 = download_savant_csvs(2026)
        filtered = filter_by_savant(snapshot, savant_2026)
        rp_candidates = [p for p in filtered if p["fa_type"] == "rp"]

        if not rp_candidates and not args.dry_run:
            _notify(env, args, "[FA Scan RP] 無 RP 候選通過品質門檻")
            return

        if args.dry_run:
            print(f"RP candidates: {len(rp_candidates)}")
            for p in rp_candidates:
                print(f"  {p['name']} {p['team']}")
            return

        # Layer 3: Enrich
        enriched = enrich_layer3(rp_candidates, savant_2026, config)

        # Build data + call Claude (single pass for RP)
        my_rps = build_roster_for_pass1(config, savant_2026, player_type="rp")
        data = _build_rp_data(enriched, my_rps, config)

        prompt_path = os.path.join(SCRIPT_DIR, "prompt_fa_scan_rp.txt")
        advice = _call_claude(prompt_path, data)

        _publish(today_str, "RP", advice, data, env, args)

    except Exception as e:
        _handle_error("RP scan", e, env, args)
```

Note: `build_roster_for_pass1` with `player_type="rp"` needs to handle RP (show all 2, no hide). Add this case to the function in Task 4. `_build_rp_data`, `_call_claude`, `_publish`, `_handle_error`, `_notify` are helper functions — implement in Step 5.

- [ ] **Step 5: Implement shared helpers**

```python
def _call_claude(prompt_path, data, timeout=180):
    """Call claude -p with prompt + data. Returns advice string or raises."""
    with open(prompt_path, encoding="utf-8") as f:
        prompt = f.read()
    full_prompt = f"{prompt}\n\n---\n\n{data}"
    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr[:500]}")
    return result.stdout.strip()


def _notify(env, args, message):
    """Send Telegram notification (unless --no-send)."""
    print(message, file=sys.stderr)
    if not args.no_send:
        send_telegram(message, env)


def _handle_error(step_name, error, env, args):
    """Handle pipeline error: print, Telegram notify, optionally create error Issue."""
    msg = f"[FA Scan] {step_name} failed: {error}"
    print(msg, file=sys.stderr)
    if not args.no_send:
        send_telegram(msg, env)
        # Create error Issue
        try:
            subprocess.run(
                ["gh", "issue", "create", "--repo", "huansbox/mlb-fantasy",
                 "--title", f"[FA Scan Error] {step_name}",
                 "--body", f"```\n{msg}\n```",
                 "--label", "fa-scan-error"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
        except Exception:
            pass


def _publish(today_str, scan_type, advice, raw_data, env, args):
    """Publish results: Telegram + GitHub Issue."""
    if args.no_send:
        print(advice)
        return

    # Telegram
    send_telegram(advice, env)

    # GitHub Issue
    title = f"[FA Scan {scan_type}] {today_str}"
    body = f"""## Analysis

{advice}

---

<details>
<summary>Raw Data</summary>

```
{raw_data}
```

</details>
"""
    try:
        subprocess.run(
            ["gh", "issue", "create", "--repo", "huansbox/mlb-fantasy",
             "--title", title, "--body", body,
             "--label", "fa-scan"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except Exception as e:
        print(f"GitHub Issue error: {e}", file=sys.stderr)
```

- [ ] **Step 6: Implement `_run_daily_scan()` — the core flow**

This is the main daily pipeline. Batter and SP are processed sequentially (not parallel — simpler to implement, parallel can be added later).

```python
def _run_daily_scan(access_token, config, today_str, env, args):
    """Daily scan: Batter + SP with two-pass Claude architecture."""
    print(f"[FA Scan] Daily scan {today_str}...", file=sys.stderr)

    # ── Shared: Layer 1 Yahoo snapshot + history ──
    print("  Layer 1: Yahoo FA queries...", file=sys.stderr)
    snapshot = collect_fa_snapshot(access_token, config, queries=SCAN_QUERIES)

    history = load_fa_history()
    changes, ref_1d, ref_3d = calc_owned_changes(snapshot, history, today_str)
    history[today_str] = {
        name: {"pct": info["pct"], "team": info["team"], "position": info["position"]}
        for name, info in snapshot.items()
    }
    sorted_dates = sorted(history.keys())
    if len(sorted_dates) > 14:
        for old_date in sorted_dates[:-14]:
            del history[old_date]
    save_fa_history(history)

    # ── Shared: Savant CSVs ──
    print("  Layer 2: Savant quality filter...", file=sys.stderr)
    savant_2026 = download_savant_csvs(2026)

    # ── Shared: waiver-log watch players ──
    watchlist = parse_waiver_log_watchlist()
    watchlist = _resolve_watch_mlb_ids(watchlist, savant_2026)

    # Remove watch players from snapshot to avoid duplication
    watch_names = {w["name"] for w in watchlist}
    snapshot_no_watch = {k: v for k, v in snapshot.items() if k not in watch_names}

    # ── Layer 2: filter ──
    filtered = filter_by_savant(snapshot_no_watch, savant_2026)

    # Add %owned risers (3d) that aren't already in filtered or watch
    existing_names = {p["name"] for p in filtered} | watch_names
    for pt, top_n in [("batter", 20), ("sp", 20)]:
        risers = collect_owned_risers(history, today_str, position_filter=pt, top_n=top_n, days=3)
        for r in risers:
            if r["name"] not in existing_names:
                # Need to check if this riser passes Layer 2
                # Add to snapshot and re-filter just this player
                snapshot_no_watch[r["name"]] = {
                    "pct": r["pct"], "team": r["team"],
                    "position": r["position"], "stats": {},
                }
                extra = filter_by_savant({r["name"]: snapshot_no_watch[r["name"]]}, savant_2026)
                filtered.extend(extra)
                existing_names.add(r["name"])

    if args.dry_run:
        print(f"\n=== Layer 2 Results ({len(filtered)} passed) ===")
        for p in filtered:
            s = p.get("savant_2026") or {}
            print(f"  {p['name']:22} {p['team']:5} {p['fa_type']:6}")
        print(f"\nWatch list: {len(watchlist)} players")
        return

    # ── Layer 3: Enrich FA candidates ──
    print("  Layer 3: Enriching FA candidates...", file=sys.stderr)
    enriched = enrich_layer3(filtered, savant_2026, config)

    # Enrich watch players (Layer 3 only)
    print("  Layer 3: Enriching watch players...", file=sys.stderr)
    watch_enriched = enrich_watch_players(watchlist, savant_2026, config)

    # Attach %owned changes
    changes_by_name = {c["name"]: c for c in changes}
    for p in enriched + watch_enriched:
        c = changes_by_name.get(p["name"], {})
        p["d1"] = c.get("d1")
        p["d3"] = c.get("d3")

    # ── Process Batter ──
    _process_group(
        "batter", config, savant_2026, enriched, watch_enriched,
        changes, ref_1d, ref_3d, today_str, env, args,
    )

    # ── Process SP ──
    _process_group(
        "sp", config, savant_2026, enriched, watch_enriched,
        changes, ref_1d, ref_3d, today_str, env, args,
    )


def _process_group(group_type, config, savant_2026, enriched, watch_enriched,
                   changes, ref_1d, ref_3d, today_str, env, args):
    """Process one group (batter or SP): Pass 1 + Pass 2."""
    label = "打者" if group_type == "batter" else "SP"
    try:
        # Filter to this group
        fa_candidates = [p for p in enriched if p["fa_type"] == group_type]
        watch_candidates = [p for p in watch_enriched if p["fa_type"] == group_type]

        # Pass 1: pick weakest from roster
        print(f"  Pass 1 ({label}): picking weakest...", file=sys.stderr)
        roster_data = build_roster_for_pass1(config, savant_2026, player_type=group_type)
        prompt_path = os.path.join(SCRIPT_DIR, "prompt_fa_scan_pass1.txt")
        pass1_result = _call_claude(prompt_path, roster_data)

        # Parse Pass 1 output (JSON)
        try:
            pass1_json = json.loads(pass1_result)
            weakest_names = [w["name"] for w in pass1_json.get("weakest", [])]
        except (json.JSONDecodeError, KeyError):
            # Fallback: use code-sorted bottom N
            print(f"  Pass 1 ({label}): JSON parse failed, using code fallback", file=sys.stderr)
            weakest_names = _fallback_weakest(config, savant_2026, group_type)

        if not fa_candidates and not watch_candidates:
            _notify(env, args, f"[FA Scan {label}] 無候選通過品質門檻，waiver-log 無 watch")
            return

        # Pass 2: compare
        print(f"  Pass 2 ({label}): comparing...", file=sys.stderr)
        prompt_file = f"prompt_fa_scan_pass2_{'batter' if group_type == 'batter' else 'sp'}.txt"
        prompt_path = os.path.join(SCRIPT_DIR, prompt_file)

        # Build Pass 2 data
        data = _build_pass2_data(
            group_type, weakest_names, fa_candidates, watch_candidates,
            changes, ref_1d, ref_3d, config,
        )
        advice = _call_claude(prompt_path, data)

        _publish(today_str, label, advice, data, env, args)

    except Exception as e:
        _handle_error(f"{label} scan", e, env, args)


def _fallback_weakest(config, savant_2026, group_type):
    """Fallback when Pass 1 Claude fails: return bottom N by code sorting."""
    if group_type == "batter":
        players = config.get("batters", [])
        n = 4
    else:
        players = [p for p in config.get("pitchers", []) if pitcher_type(p) == "SP"]
        n = 3

    # Simple sort by prior_stats (since Savant extraction here would duplicate code)
    scored = []
    for p in players:
        prior = p.get("prior_stats", {})
        if group_type == "batter":
            val = prior.get("xwoba", 0)
        else:
            val = prior.get("xera", 99)
        scored.append((p["name"], val))

    if group_type == "batter":
        scored.sort(key=lambda x: x[1])  # lowest xwOBA first
    else:
        scored.sort(key=lambda x: x[1], reverse=True)  # highest xERA first

    return [name for name, _ in scored[:n]]
```

- [ ] **Step 7: Implement `_build_pass2_data()`**

This function assembles the data string for Pass 2. It combines:
- Weakest roster players (from Pass 1)
- FA candidates (formatted)
- Watch candidates (formatted)
- %owned changes (risers only)
- waiver-log content
- Evaluation framework from CLAUDE.md

```python
def _build_pass2_data(group_type, weakest_names, fa_candidates, watch_candidates,
                      changes, ref_1d, ref_3d, config):
    """Build data string for Pass 2 Claude prompt."""
    lines = []

    # Embed evaluation framework
    framework = _extract_eval_framework()
    if framework:
        lines.append(f"--- 評估框架（from CLAUDE.md）---\n{framework}\n")

    # My weakest players
    label = "打者" if group_type == "batter" else "SP"
    lines.append(f"--- 我方最弱{label}（Pass 1 篩出）---")
    # Find these players in config and format their data
    all_players = config.get("batters" if group_type == "batter" else "pitchers", [])
    for name in weakest_names:
        p = next((x for x in all_players if x["name"] == name), None)
        if p:
            prior = p.get("prior_stats", {})
            lines.append(f"  {name}({p['team']}) — prior: {json.dumps(prior, ensure_ascii=False)}")

    # FA candidates
    fa_label = f"FA {label}候選"
    if fa_candidates:
        lines.append(f"\n--- {fa_label} ({len(fa_candidates)} 人) ---")
        for p in fa_candidates:
            if group_type == "batter":
                lines.append(_format_fa_batter(p))
            else:
                lines.append(_format_fa_pitcher(p))
    else:
        lines.append(f"\n--- {fa_label}: 無 ---")

    # Watch candidates
    if watch_candidates:
        lines.append(f"\n--- waiver-log 觀察中{label} ({len(watch_candidates)} 人) ---")
        for p in watch_candidates:
            if group_type == "batter":
                lines.append(_format_fa_batter(p))
            else:
                lines.append(_format_fa_pitcher(p))

    # %owned risers (filtered to this group)
    group_changes = [c for c in changes
                     if _classify_fa_type(c.get("position", "")) == group_type
                     and c.get("d3") is not None and c["d3"] > 0]
    group_changes.sort(key=lambda x: x["d3"], reverse=True)
    if group_changes:
        lines.append(f"\n--- %owned 升幅 ({label}) ---")
        for c in group_changes[:10]:
            lines.append(f"  {c['name']:20} 3d:+{c['d3']:>3} {c['pct']:>3}%  {c['position']}")

    # waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            lines.append(f"\n--- waiver-log.md ---\n{f.read()}")

    return "\n".join(lines)
```

- [ ] **Step 8: Verify with --dry-run**

```bash
cd D:/mywork/_mynote/mlb-fantasy/daily-advisor && python fa_scan.py --dry-run 2>&1 | head -30
```

Expected: Layer 2 results printed (batter + SP candidates), watch list count, no Claude calls.

- [ ] **Step 9: Commit**

```bash
git add daily-advisor/fa_scan.py
git commit -m "feat(fa_scan): implement two-pass Claude architecture with all modes"
```

---

### Task 9: Delete weekly_scan.py + deprecate fa_watch.py

**Files:**
- Delete: `daily-advisor/weekly_scan.py`
- Modify: `daily-advisor/fa_watch.py` (add deprecation notice)

- [ ] **Step 1: Verify fa_scan.py works independently of weekly_scan.py**

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
# Verify fa_scan imports don't depend on weekly_scan
import fa_scan
print('fa_scan imports OK without weekly_scan dependency')
"
```

- [ ] **Step 2: Delete weekly_scan.py**

```bash
git rm daily-advisor/weekly_scan.py
```

- [ ] **Step 3: Add deprecation notice to fa_watch.py**

Add at the top of fa_watch.py, after the module docstring:

```python
import warnings
warnings.warn(
    "fa_watch.py is deprecated. Use fa_scan.py instead. "
    "This file will be removed in Batch 3.",
    DeprecationWarning, stacklevel=1,
)
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete weekly_scan.py, deprecate fa_watch.py (replaced by fa_scan.py)"
```

---

### Task 10: End-to-end test with --no-send

**Files:** None (testing only)

- [ ] **Step 1: Run full daily scan with --no-send**

```bash
cd D:/mywork/_mynote/mlb-fantasy/daily-advisor && python fa_scan.py --no-send 2>fa_scan_debug.log
```

Check:
- Layer 1-2-3 completes without error
- Pass 1 batter + SP produce valid JSON (or fallback kicks in)
- Pass 2 batter + SP produce analysis text
- No Telegram or GitHub Issue sent (--no-send)

- [ ] **Step 2: Run RP scan with --no-send**

```bash
cd D:/mywork/_mynote/mlb-fantasy/daily-advisor && python fa_scan.py --rp --no-send 2>fa_scan_rp_debug.log
```

- [ ] **Step 3: Run snapshot-only**

```bash
cd D:/mywork/_mynote/mlb-fantasy/daily-advisor && python fa_scan.py --snapshot-only 2>fa_scan_snapshot_debug.log
```

- [ ] **Step 4: Check debug logs for errors**

```bash
grep -i "error\|fail\|traceback" fa_scan_debug.log fa_scan_rp_debug.log fa_scan_snapshot_debug.log
```

- [ ] **Step 5: Commit any fixes, then final commit**

```bash
git add -A
git commit -m "test: verify fa_scan.py end-to-end with all modes"
```

---

## Verification Checklist

After all tasks:

- [ ] `python fa_scan.py --dry-run` works (Layer 1+2, no Claude)
- [ ] `python fa_scan.py --no-send` works (full pipeline, no external output)
- [ ] `python fa_scan.py --rp --no-send` works (RP mode)
- [ ] `python fa_scan.py --snapshot-only` works (snapshot + cleanup)
- [ ] `weekly_scan.py` is deleted
- [ ] `fa_watch.py` has deprecation warning
- [ ] `weekly_review.py` reads `fa-scan` label Issues
- [ ] No `from weekly_scan import` or `from fa_watch import` in fa_scan.py
