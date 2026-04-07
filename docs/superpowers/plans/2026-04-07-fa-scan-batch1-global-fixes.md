# FA Scan Batch 1: Global Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two global fixes before the fa_scan refactor: (1) change |xERA-ERA| luck marker from absolute value + direction text to signed xERA-ERA, (2) remove %owned fallers from display.

**Architecture:** Modify calculation logic in weekly_scan.py, display logic in weekly_scan.py + fa_watch.py, percentile tables in daily_advisor.py, and documentation in CLAUDE.md. No new files, no new functions — just editing existing code.

**Tech Stack:** Python 3, existing codebase

**Branch:** `fix/era-diff-sign-and-owned-fallers`

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `daily-advisor/weekly_scan.py` | Modify | era_diff calculation + display format |
| `daily-advisor/fa_watch.py` | Modify | Remove fallers from format_change_rankings() |
| `daily-advisor/daily_advisor.py` | Modify | Remove era_diff from percentile tables (no longer used as absolute value) |
| `CLAUDE.md` | Modify | Update luck marker description + percentile table |

---

### Task 1: Change era_diff calculation from absolute to signed value

**Files:**
- Modify: `daily-advisor/weekly_scan.py:326-333`

The current code computes `abs(xera - era)` and stores direction as a separate string field. Change to store `xera - era` directly (positive = lucky/ERA will rise, negative = unlucky/buy-low).

- [ ] **Step 1: Modify `_compute_derived_pitcher()` in weekly_scan.py**

Replace lines 327-333:

```python
    if xera is not None and xera > 0 and era is not None:
        diff = abs(xera - era)
        d["era_diff"] = round(diff, 2)
        if era < xera:
            d["era_diff_dir"] = "運氣好↑"
        elif era > xera:
            d["era_diff_dir"] = "運氣差↓"
```

With:

```python
    if xera is not None and xera > 0 and era is not None:
        d["era_diff"] = round(xera - era, 2)
```

This removes `era_diff_dir` entirely. Positive = xERA > ERA = lucky (ERA will regress up). Negative = xERA < ERA = unlucky (buy-low signal).

- [ ] **Step 2: Verify calculation**

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
from weekly_scan import _compute_derived_pitcher

# Case 1: lucky pitcher (ERA 2.00, xERA 3.50 -> +1.50)
result = _compute_derived_pitcher(
    {'xera': 3.50}, {'inningsPitched': '50.0', 'era': '2.00', 'gamesStarted': '8'},
    {}, 'NYY', 2026, 'sp')
print(f'Lucky: era_diff={result[\"era_diff\"]} (expect +1.50)')
assert result['era_diff'] == 1.50
assert 'era_diff_dir' not in result

# Case 2: unlucky pitcher (ERA 5.00, xERA 3.50 -> -1.50)
result2 = _compute_derived_pitcher(
    {'xera': 3.50}, {'inningsPitched': '50.0', 'era': '5.00', 'gamesStarted': '8'},
    {}, 'NYY', 2026, 'sp')
print(f'Unlucky: era_diff={result2[\"era_diff\"]} (expect -1.50)')
assert result2['era_diff'] == -1.50
print('OK')
"
```

Expected: Both assertions pass.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/weekly_scan.py
git commit -m "fix: era_diff now stores signed xERA-ERA instead of absolute value"
```

---

### Task 2: Update era_diff display format in weekly_scan.py

**Files:**
- Modify: `daily-advisor/weekly_scan.py:678-680`

The display currently shows `"運氣好↑ 1.52 (P80-90)"`. Change to show signed value with +/- prefix: `"+1.52 (P80-90)"` or `"-1.52 (P80-90)"`.

- [ ] **Step 1: Update `_format_fa_pitcher()` display**

Replace lines 678-680:

```python
    if d26.get("era_diff") is not None:
        tag = pctile_tag(d26["era_diff"], "era_diff", pt)
        aux.append(f"{d26.get('era_diff_dir', '')} {d26['era_diff']:.2f} {tag}".strip())
```

With:

```python
    if d26.get("era_diff") is not None:
        tag = pctile_tag(abs(d26["era_diff"]), "era_diff", pt)
        sign = "+" if d26["era_diff"] > 0 else ""
        aux.append(f"運氣 {sign}{d26['era_diff']:.2f} {tag}")
```

Note: `pctile_tag` still receives the absolute value because the percentile table measures magnitude of luck (higher = more luck variance regardless of direction). The sign is shown separately for human interpretation.

- [ ] **Step 2: Check for era_diff_dir references elsewhere in weekly_scan.py**

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
# grep for era_diff_dir in weekly_scan source
with open('daily-advisor/weekly_scan.py', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'era_diff_dir' in line:
            print(f'  Line {i}: {line.rstrip()}')
"
```

Expected: No output (all references removed in Task 1 and this task).

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/weekly_scan.py
git commit -m "fix: era_diff display uses signed +/- format instead of direction text"
```

---

### Task 3: Remove era_diff percentile tables from daily_advisor.py

**Files:**
- Modify: `daily-advisor/daily_advisor.py:38,43`

The `era_diff` entry in `PITCHER_PCTILES` and `RP_PCTILES` measures the magnitude of luck (absolute value). Since we now store signed values, `pctile_tag()` in Task 2 passes `abs(value)` — so the table still works. **However**, the table is only used for display tagging, and we should keep it for now.

Actually, on review: the table is still needed because Task 2 calls `pctile_tag(abs(d26["era_diff"]), "era_diff", pt)`. The table stays. **Skip this task.**

- [ ] **Step 1: No changes needed — era_diff percentile table still used with abs() in display**

This task is a no-op. The percentile table measures luck magnitude and is still valid.

- [ ] **Step 2: Commit (skip — nothing to commit)**

---

### Task 4: Remove %owned fallers from fa_watch.py

**Files:**
- Modify: `daily-advisor/fa_watch.py:156-193`

Remove the fallers section from `format_change_rankings()`. Keep risers only.

- [ ] **Step 1: Update `format_change_rankings()` in fa_watch.py**

Replace lines 170-193 (the `with_d1` filtering through end of fallers block):

```python
    with_d1 = [c for c in changes if c["d1"] is not None and c["d1"] != 0]

    risers = sorted(with_d1, key=lambda x: x["d1"], reverse=True)[:top_n]
    fallers = sorted(with_d1, key=lambda x: x["d1"])[:top_n]

    if risers:
        lines.append("\n升幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in risers:
            d1 = f"+{c['d1']}" if c["d1"] > 0 else str(c["d1"])
            d3 = f"+{c['d3']}" if c["d3"] and c["d3"] > 0 else (str(c["d3"]) if c["d3"] is not None else "—")
            wtag = f" [W {c['waiver_date']}]" if c.get("waiver_date") else ""
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}{wtag}")

    if fallers and fallers[0]["d1"] < 0:
        lines.append("\n降幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in fallers:
            if c["d1"] >= 0:
                break
            d1 = str(c["d1"])
            d3 = str(c["d3"]) if c["d3"] is not None else "—"
            wtag = f" [W {c['waiver_date']}]" if c.get("waiver_date") else ""
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}{wtag}")
```

With (risers only, remove fallers):

```python
    with_d1 = [c for c in changes if c["d1"] is not None and c["d1"] > 0]

    risers = sorted(with_d1, key=lambda x: x["d1"], reverse=True)[:top_n]

    if risers:
        lines.append("\n升幅前 5:")
        lines.append(f"  {'':20} {'24h':>5} {'3d':>5} {'%own':>5}  位置")
        for c in risers:
            d1 = f"+{c['d1']}"
            d3 = f"+{c['d3']}" if c["d3"] and c["d3"] > 0 else (str(c["d3"]) if c["d3"] is not None else "—")
            wtag = f" [W {c['waiver_date']}]" if c.get("waiver_date") else ""
            lines.append(f"  {c['name']:20} {d1:>5} {d3:>5} {c['pct']:>4}%  {c['position']}{wtag}")
```

Changes:
- `with_d1` filter: `!= 0` → `> 0` (only positive changes)
- Remove `fallers` variable and entire fallers block
- Simplify `d1` format (always positive now, always `+` prefix)

- [ ] **Step 2: Update function docstring**

Change line 156:

```python
    """Format top risers and fallers with reference date info."""
```

To:

```python
    """Format top %owned risers with reference date info."""
```

- [ ] **Step 3: Verify**

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
from fa_watch import format_change_rankings
changes = [
    {'name': 'Player A', 'd1': 5, 'd3': 8, 'pct': 20, 'position': 'SP'},
    {'name': 'Player B', 'd1': -3, 'd3': -5, 'pct': 15, 'position': 'CF'},
    {'name': 'Player C', 'd1': 2, 'd3': 3, 'pct': 10, 'position': '1B'},
    {'name': 'Player D', 'd1': 0, 'd3': 1, 'pct': 5, 'position': 'RP'},
]
result = format_change_rankings(changes, '2026-04-06', '2026-04-04')
print(result)
assert '降幅' not in result
assert 'Player B' not in result  # negative d1, should be excluded
assert 'Player D' not in result  # zero d1, should be excluded
assert 'Player A' in result
print('OK — no fallers, no zero changes')
"
```

Expected: Only Player A and C shown. No fallers section.

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/fa_watch.py
git commit -m "fix: remove %owned fallers from display, keep risers only"
```

---

### Task 5: Update CLAUDE.md luck marker description and percentile table

**Files:**
- Modify: `CLAUDE.md:161-163, 180, 204, 226`

- [ ] **Step 1: Update SP evaluation section (lines 161-163)**

Replace:

```markdown
- |xERA - ERA| 運氣標記（百分位判斷幅度，P70+ = 顯著）：
  - ERA < xERA（運氣好）→ ERA 預期回升，表現會變差（例：ERA 1.84 / xERA 3.36）
  - ERA > xERA（運氣差）→ ERA 預期回降，撿便宜訊號（例：ERA 5.00 / xERA 3.50）
```

With:

```markdown
- xERA-ERA 運氣標記（正=運氣好小心，負=運氣差撿便宜，百分位判斷絕對值幅度，P70+ = 顯著）：
  - +1.52：xERA 3.52 / ERA 2.00 → 運氣好，ERA 預期回升
  - -1.50：xERA 3.50 / ERA 5.00 → 運氣差，撿便宜訊號
```

- [ ] **Step 2: Update RP evaluation section (line 180)**

Replace:

```markdown
**輔助**：Barrel% allowed、ERA、|xERA - ERA| 運氣標記（同 SP：ERA < xERA = 運氣好會回升，ERA > xERA = 運氣差可撿便宜）
```

With:

```markdown
**輔助**：Barrel% allowed、ERA、xERA-ERA 運氣標記（同 SP：正=運氣好會回升，負=運氣差可撿便宜）
```

- [ ] **Step 3: Update SP percentile table header (line 204)**

Replace:

```markdown
| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | \|xERA-ERA\| |
```

With:

```markdown
| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | xERA-ERA |
```

Note: The percentile values themselves don't change — they still measure magnitude (absolute value). The column header just drops the `| |` notation since the signed format makes direction self-evident.

- [ ] **Step 4: Update RP percentile table header (line 226)**

Replace:

```markdown
| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | K/9 | IP/Team_G | \|xERA-ERA\| |
```

With:

```markdown
| 百分位 | xERA | xwOBA allowed | HH% allowed | Barrel% allowed | K/9 | IP/Team_G | xERA-ERA |
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update luck marker from |xERA-ERA| to signed xERA-ERA format"
```

---

## Verification Checklist

After all tasks:

```bash
cd D:/mywork/_mynote/mlb-fantasy && python -c "
import sys; sys.path.insert(0,'daily-advisor')
# 1. Verify era_diff is signed
from weekly_scan import _compute_derived_pitcher
r = _compute_derived_pitcher(
    {'xera': 3.50}, {'inningsPitched': '50.0', 'era': '5.00', 'gamesStarted': '8'},
    {}, 'NYY', 2026, 'sp')
assert r['era_diff'] == -1.50, f'Expected -1.50, got {r[\"era_diff\"]}'
assert 'era_diff_dir' not in r

# 2. Verify no fallers in format_change_rankings
from fa_watch import format_change_rankings
result = format_change_rankings(
    [{'name':'X','d1':-3,'d3':-5,'pct':10,'position':'SP'}],
    '2026-04-06', '2026-04-04')
assert '降幅' not in result
assert 'X' not in result

# 3. Verify pctile_tag still works with era_diff
from daily_advisor import pctile_tag
tag = pctile_tag(1.50, 'era_diff', 'pitcher')
assert tag != '', f'Empty tag for era_diff=1.50'

print('All checks passed')
"
```
