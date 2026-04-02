# Config Schema Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all scripts to work with the new roster_config.json schema (no `role`/`type`/`proj` fields, unified `positions` array) and make FA Watch position queries dynamic.

**Architecture:** The new config uses a unified `positions` array for batters and pitchers (e.g. `["SP"]`, `["2B","3B"]`). Scripts that previously read `role` or `type` must derive these from `positions` or from Yahoo API's `selected_position`. Position queries in fa_watch.py change from hardcoded to dynamically computed from config's position coverage.

**Tech Stack:** Python 3, Yahoo Fantasy API, MLB Stats API, Baseball Savant CSV

**Branch:** `refactor/config-schema`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `daily-advisor/fa_watch.py` | Modify | Remove role/type reads, dynamic DAILY_QUERIES, dynamic risk summary in build_fa_watch_data() |
| `daily-advisor/weekly_scan.py` | Modify | Remove role/type reads, dynamic WEEKLY_QUERIES, roster summary from positions |
| `daily-advisor/main.py` | Modify | Remove role/type from config reads (Yahoo API path already works, only config fallback needs fix) |
| `daily-advisor/roster_stats.py` | Modify | Remove role/type reads, derive pitcher type from positions |
| `daily-advisor/weekly_review.py` | Modify | fetch_sp_schedules reads type/role from config — change to positions-based |

### Helper: is_pitcher() and derive type

All scripts need the same logic to determine if a player is a pitcher and what type (SP/RP). Add a shared helper to `yahoo_query.py` (already the shared module):

```python
def is_pitcher(player):
    """Check if player is pitcher based on positions array."""
    return any(p in ("SP", "RP") for p in player.get("positions", []))

def pitcher_type(player):
    """Derive SP/RP from positions array."""
    positions = player.get("positions", [])
    if "SP" in positions:
        return "SP"
    if "RP" in positions:
        return "RP"
    return None
```

### Helper: position depth

fa_watch.py needs to compute which positions have zero backup. Add to `yahoo_query.py`:

```python
# All Yahoo fantasy positions for batters
ALL_BATTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]

def calc_position_depth(config):
    """Calculate position coverage from config.

    Returns dict: {position: count} for positions with ≤ 1 player.
    """
    coverage = {pos: 0 for pos in ALL_BATTER_POSITIONS}
    for b in config.get("batters", []):
        for pos in b.get("positions", []):
            if pos in coverage:
                coverage[pos] += 1
    return {pos: count for pos, count in coverage.items() if count <= 1}
```

---

### Task 1: Add shared helpers to yahoo_query.py

**Files:**
- Modify: `daily-advisor/yahoo_query.py` (add helpers at module level, after existing imports)

- [ ] **Step 1: Add is_pitcher, pitcher_type, calc_position_depth**

Add after the existing `send_telegram` function (around line 75):

```python
# ── Roster helpers ──

ALL_BATTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]

def is_pitcher(player):
    """Check if player is pitcher based on positions array."""
    return any(p in ("SP", "RP") for p in player.get("positions", []))

def pitcher_type(player):
    """Derive SP/RP from positions array. Returns 'SP', 'RP', or None."""
    positions = player.get("positions", [])
    if "SP" in positions:
        return "SP"
    if "RP" in positions:
        return "RP"
    return None

def calc_position_depth(config):
    """Calculate position coverage from config.

    Returns dict of positions with ≤ 1 player covering them.
    Example: {"C": 1, "SS": 1} means C and SS have only 1 player each.
    """
    coverage = {pos: 0 for pos in ALL_BATTER_POSITIONS}
    for b in config.get("batters", []):
        for pos in b.get("positions", []):
            if pos in coverage:
                coverage[pos] += 1
    return {pos: count for pos, count in coverage.items() if count <= 1}
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from yahoo_query import is_pitcher, pitcher_type, calc_position_depth; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```
git add daily-advisor/yahoo_query.py
git commit -m "feat: add is_pitcher, pitcher_type, calc_position_depth helpers"
```

---

### Task 2: Fix fa_watch.py — remove role/type, dynamic queries, dynamic risk

**Files:**
- Modify: `daily-advisor/fa_watch.py`

**Changes needed (3 areas):**

1. **Import new helpers** (line 16): add `is_pitcher, pitcher_type, calc_position_depth`
2. **Remove hardcoded DAILY_QUERIES position list** (lines 24-30): replace with a function that builds queries dynamically from config
3. **Fix build_fa_watch_data()** (lines 191-261): remove `role`/`type` reads, add position depth section

- [ ] **Step 1: Update imports**

```python
# line 16, add to existing import:
from yahoo_query import (
    refresh_token, load_env, load_config, api_get,
    YAHOO_STAT_MAP, extract_player_info, parse_player_stats,
    send_telegram,
    is_pitcher, pitcher_type, calc_position_depth,
)
```

- [ ] **Step 2: Replace hardcoded DAILY_QUERIES with dynamic builder**

Replace lines 23-41 with:

```python
# Base queries (always included)
BASE_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=20"),
    ("SP", "status=A;position=SP;sort=AR;count=10"),
]

BASE_WEEKLY_QUERIES = [
    ("ALL", "status=A;sort=AR;count=50"),
    ("ALL-lastweek", "status=A;sort=AR;sort_type=lastweek;count=30"),
    ("SP", "status=A;position=SP;sort=AR;count=20"),
]

def build_position_queries(config, weekly=False):
    """Build FA queries dynamically: base + thin positions from config."""
    base = list(BASE_WEEKLY_QUERIES if weekly else BASE_QUERIES)
    thin = calc_position_depth(config)
    count = 15 if weekly else 10
    for pos in thin:
        base.append((pos, f"status=A;position={pos};sort=AR;count={count}"))
    return base
```

- [ ] **Step 3: Fix build_fa_watch_data() — roster summary without role/type**

Replace the roster summary block (lines 199-206) with:

```python
    # Roster summary
    lines.append("\n--- 我的陣容 ---")
    for b in config.get("batters", []):
        lines.append(f"  {b['name']} ({b['team']}, {'/'.join(b['positions'])})")
    for p in config.get("pitchers", []):
        p_type = pitcher_type(p) or "P"
        lines.append(f"  {p['name']} ({p['team']}, {p_type})")
```

- [ ] **Step 4: Fix build_fa_watch_data() — dynamic position depth instead of hardcoded "CF/SP/1B"**

Replace the "弱點位置 FA" block (lines 208-219) with:

```python
    # Dynamic weak position FA (positions with ≤ 1 player)
    thin = calc_position_depth(config)
    if thin:
        lines.append(f"\n--- 零/薄替補位置 FA（{', '.join(thin.keys())}）---")
        for pos in thin:
            pos_players = [
                (n, i) for n, i in snapshot.items()
                if pos in i["position"].split(",")
            ]
            pos_players.sort(key=lambda x: x[1]["pct"], reverse=True)
            top = pos_players[:3]
            if top:
                names = ", ".join(f"{n}({i['pct']}%)" for n, i in top)
                lines.append(f"  {pos}（覆蓋 {thin[pos]} 人）: {names}")
```

- [ ] **Step 5: Update collect_fa_snapshot call in main() to use dynamic queries**

In `main()` (line 335), change:
```python
        snapshot = collect_fa_snapshot(access_token, config)
```
to:
```python
        queries = build_position_queries(config)
        snapshot = collect_fa_snapshot(access_token, config, queries)
```

- [ ] **Step 6: Verify fa_watch.py loads without error**

Run: `python -c "import fa_watch; print('OK')"` (from daily-advisor dir)
Expected: `OK` (no import errors)

- [ ] **Step 7: Commit**

```
git add daily-advisor/fa_watch.py
git commit -m "refactor: fa_watch dynamic position queries, remove role/type"
```

---

### Task 3: Fix weekly_scan.py — remove role/type, dynamic queries

**Files:**
- Modify: `daily-advisor/weekly_scan.py`

- [ ] **Step 1: Update imports**

Add `is_pitcher, pitcher_type, calc_position_depth` to the yahoo_query import (line 15).

Add `build_position_queries` to the fa_watch import (line 19):
```python
from fa_watch import (
    collect_fa_snapshot, load_fa_history, save_fa_history,
    calc_owned_changes, format_change_rankings,
    build_position_queries, TPE,
)
```

- [ ] **Step 2: Fix build_weekly_data() roster summary (lines 33-39)**

Replace:
```python
    for b in config.get("batters", []):
        role = "BN" if b["role"] == "bench" else b["role"]
        lines.append(f"  [{role}] {b['name']} ({b['team']}, {'/'.join(b['positions'])})")
    for p in config.get("pitchers", []):
        role = "BN" if p["role"] == "bench" else ("IL" if p["role"] == "IL" else p["type"])
        lines.append(f"  [{role}] {p['name']} ({p['team']}, {p['type']})")
```

With:
```python
    for b in config.get("batters", []):
        lines.append(f"  {b['name']} ({b['team']}, {'/'.join(b['positions'])})")
    for p in config.get("pitchers", []):
        p_type = pitcher_type(p) or "P"
        lines.append(f"  {p['name']} ({p['team']}, {p_type})")
```

- [ ] **Step 3: Fix FA rankings by position (lines 42-60) — use dynamic positions**

Replace hardcoded `for pos in ["CF", "SP", "LF", "1B", "2B"]:` with:
```python
    thin = calc_position_depth(config)
    scan_positions = list(thin.keys()) + ["SP"]  # always scan SP
    scan_positions = list(dict.fromkeys(scan_positions))  # dedupe, preserve order
    for pos in scan_positions:
```

- [ ] **Step 4: Update main() to use dynamic queries (line 147)**

Change:
```python
        snapshot = collect_fa_snapshot(access_token, config, queries=WEEKLY_QUERIES)
```
to:
```python
        queries = build_position_queries(config, weekly=True)
        snapshot = collect_fa_snapshot(access_token, config, queries=queries)
```

Remove the now-unused `WEEKLY_QUERIES` import from fa_watch (if it was imported).

- [ ] **Step 5: Verify weekly_scan.py loads**

Run: `python -c "import weekly_scan; print('OK')"` (from daily-advisor dir)

- [ ] **Step 6: Commit**

```
git add daily-advisor/weekly_scan.py
git commit -m "refactor: weekly_scan dynamic position queries, remove role/type"
```

---

### Task 4: Fix main.py — config fallback path

**Files:**
- Modify: `daily-advisor/main.py`

**Context:** main.py's Yahoo API path (`fetch_yahoo_roster`) already builds `role` and `type` from API data at runtime (lines 775-795). The issue is only the **config fallback path** (lines 897-898) where it reads config directly — those config entries no longer have `role`/`type`.

- [ ] **Step 1: Add import**

Add to existing imports from yahoo_query (or use inline):
```python
from yahoo_query import (
    ...,
    is_pitcher, pitcher_type,
)
```

- [ ] **Step 2: Fix config fallback — add role/type at read time**

After line 898 (`pitchers = config["pitchers"]`), add a fixup loop that derives role/type from positions so downstream code works unchanged:

```python
    # Derive role/type for config fallback (Yahoo API path generates these at runtime)
    for b in batters:
        if "role" not in b:
            b["role"] = "starter"  # config doesn't track BN/IL; Yahoo API does
        if "positions" not in b:
            b["positions"] = []
    for p in pitchers:
        if "role" not in p:
            p["role"] = "starter"
        if "type" not in p:
            p["type"] = pitcher_type(p) or "SP"
```

This way the rest of main.py (which uses `role`/`type` extensively in ~15 places) continues working without touching every reference. The Yahoo API path already generates these fields, so this only affects the config fallback.

- [ ] **Step 3: Fix calc_weekly_ip — filter IL by selected_pos instead of role**

Line 887: `active_pitchers = [p for p in src if p["role"] != "IL"]`

This works for Yahoo API path (which sets role) but config path now sets all to "starter". Since config doesn't track IL status, keep as-is — when Yahoo API is available (normal case), it's correct. Config fallback is a degraded mode where IL filtering doesn't work anyway.

No change needed, but add a comment:

```python
    # Note: config fallback doesn't know IL status; only Yahoo API path has accurate role
    active_pitchers = [p for p in src if p.get("role") != "IL"]
```

- [ ] **Step 4: Fix my_sp_names filter (line 986)**

`my_sp_names = {p["name"]: p for p in pitchers if p["type"] == "SP"}`

This already works with the fixup from Step 2 (which sets `type`). No change needed.

- [ ] **Step 5: Verify main.py loads**

Run: `python -c "import main; print('OK')"` (from daily-advisor dir)

- [ ] **Step 6: Commit**

```
git add daily-advisor/main.py
git commit -m "fix: main.py config fallback derives role/type from positions"
```

---

### Task 5: Fix roster_stats.py — remove role/type reads

**Files:**
- Modify: `daily-advisor/roster_stats.py`

- [ ] **Step 1: Add pitcher_type import**

```python
from yahoo_query import (
    load_config,
    pitcher_type,
)
```

(Update existing import to include `pitcher_type`.)

- [ ] **Step 2: Fix pitcher table output (lines 202-206)**

Replace:
```python
        if not d:
            role = "IL" if p.get("role") == "IL" else p["type"]
            print(f"| {p['name']} | {p['team']} | {role} | — | ...")
            continue
        print(f"| {p['name']} | {p['team']} | {p['type']} | {d['gs']} | ...")
```

With:
```python
        p_type = pitcher_type(p) or "P"
        if not d:
            print(f"| {p['name']} | {p['team']} | {p_type} | — | — | — | — | — | — | — | {xera} | {xwoba} | {hh} | {barrel} | {bbe} | {xera_pri} | {hh_pri} |")
            continue
        print(f"| {p['name']} | {p['team']} | {p_type} | {d['gs']} | {d['ip']} | {d['era']} | {d['whip']} | {d['k']} | {d['w']} | {d['qs']} | {xera} | {xwoba} | {hh} | {barrel} | {bbe} | {xera_pri} | {hh_pri} |")
```

- [ ] **Step 3: Verify roster_stats.py loads**

Run: `python -c "import roster_stats; print('OK')"` (from daily-advisor dir)

- [ ] **Step 4: Commit**

```
git add daily-advisor/roster_stats.py
git commit -m "fix: roster_stats derives pitcher type from positions"
```

---

### Task 6: Fix weekly_review.py — remove type/role from config reads

**Files:**
- Modify: `daily-advisor/weekly_review.py`

**Context:** weekly_review.py has TWO paths that read type/role:
1. `fetch_my_roster()` (line 316) — reads from Yahoo API, generates type/role at runtime ✓ (already works)
2. `fetch_sp_schedules()` (lines 328-331) — reads `type`/`role` from **config** dict ✗ (broken)

- [ ] **Step 1: Add pitcher_type import**

```python
from yahoo_query import (
    refresh_token, load_env, load_config, api_get as yahoo_api_get,
    ...,
    is_pitcher, pitcher_type,
)
```

- [ ] **Step 2: Fix fetch_sp_schedules (lines 328-331)**

Replace:
```python
    my_sps = {p["name"]: p["team"] for p in config.get("pitchers", [])
              if p.get("type") == "SP" and p.get("role") != "IL"}
    opp_sps = {p["name"]: p["team"] for p in opp_roster.get("pitchers", [])
               if p.get("type") == "SP" and p.get("role") != "IL"}
```

With:
```python
    my_sps = {p["name"]: p["team"] for p in config.get("pitchers", [])
              if pitcher_type(p) == "SP"}
    opp_sps = {p["name"]: p["team"] for p in opp_roster.get("pitchers", [])
               if p.get("type") == "SP" and p.get("role") != "IL"}
```

Note: `opp_roster` comes from Yahoo API `fetch_opponent_roster()` which generates `type`/`role` at runtime — so it keeps the old syntax. Only `config` (my roster from file) needs the fix.

- [ ] **Step 3: Verify weekly_review.py loads**

Run: `python -c "import weekly_review; print('OK')"` (from daily-advisor dir)

- [ ] **Step 4: Commit**

```
git add daily-advisor/weekly_review.py
git commit -m "fix: weekly_review derives pitcher type from positions for config path"
```

---

### Task 7: Integration test — dry run all scripts

- [ ] **Step 1: Test fa_watch.py dry run**

Run: `python daily-advisor/fa_watch.py --dry-run --no-send`

Expected: prints FA data summary with dynamic position queries, no crash. Verify output shows "零/薄替補位置 FA" section with dynamically detected positions (should include C, SS, 1B based on current config).

- [ ] **Step 2: Test roster_stats.py**

Run: `python daily-advisor/roster_stats.py`

Expected: prints batter + pitcher tables, no KeyError for role/type.

- [ ] **Step 3: Test main.py config-only mode**

Run: `python daily-advisor/main.py --no-send`

Expected: runs without crash (may fail on Yahoo auth if not available, but should not crash on config reads).

- [ ] **Step 4: Final commit + merge consideration**

If all pass:
```
git add -A
git commit -m "test: verify all scripts work with new config schema"
```

Decide: merge to master or PR.
