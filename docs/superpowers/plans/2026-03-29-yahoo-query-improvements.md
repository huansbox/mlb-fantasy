# Yahoo Query Tool Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance yahoo_query.py with stats data and percent_owned for player search, reducing WebSearch dependency in skills.

**Architecture:** Extend existing `fa` and `player` commands with Yahoo stat sub-resources. Use `YAHOO_STAT_MAP` from main.py for stat_id → display name mapping. Two-step lookup for `player` command (search → player_key → stats+percent_owned).

**Tech Stack:** Python 3.10+ / urllib (zero dependencies, same as existing)

---

## API Research Summary

- `fa` command: `/players;{filters}/stats` works — returns `player_stats.stats[]` with `stat_id` + `value`
- `fa` command: `/players;{filters}/percent_owned` works (already implemented)
- `player` command: search doesn't support `/percent_owned` or `/stats` directly
- `player` command workaround: search → extract `player_key` → query `/players;player_keys={key}/stats` and `/players;player_keys={key}/percent_owned` separately
- stat_id mapping already exists in `main.py` as `YAHOO_STAT_MAP` (14 categories)

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `daily-advisor/yahoo_query.py` | Modify | Add stats parsing, player two-step lookup, default status change |
| `.claude/commands/waiver-scan.md` | Modify | Note stats availability in output |
| `.claude/commands/player-eval.md` | Modify | Note stats availability, reduce WebSearch dependency |
| `.claude/commands/roster-scan.md` | Modify | Note stats availability for roster data |
| `daily-advisor/yahoo-api-reference.md` | Modify | Update "已使用" section |

---

### Task 1: Add stat_id mapping to yahoo_query.py

**Files:**
- Modify: `daily-advisor/yahoo_query.py` (top of file, after imports)

- [ ] **Step 1: Add YAHOO_STAT_MAP constant**

Copy the mapping from `main.py` (line 23-38). This maps stat_id strings to `(display_name, lower_is_better)` tuples.

```python
# Yahoo stat_id → display name (matches league's 14 scoring categories)
YAHOO_STAT_MAP = {
    "60": ("H/AB", None),   # display-only, not a scoring category
    "7": ("R", False),
    "12": ("HR", False),
    "13": ("RBI", False),
    "16": ("SB", False),
    "18": ("BB", False),
    "3": ("AVG", False),
    "55": ("OPS", False),
    "50": ("IP", False),
    "28": ("W", False),
    "42": ("K", False),
    "26": ("ERA", True),
    "27": ("WHIP", True),
    "83": ("QS", False),
    "89": ("SV+H", False),
}
```

Place after `YAHOO_TOKEN_FILE` constant (line 13).

- [ ] **Step 2: Add parse_player_stats helper**

```python
def parse_player_stats(player_data):
    """Extract stats from player data that includes /stats sub-resource."""
    stats = {}
    if len(player_data) < 2:
        return stats
    ps = player_data[1]
    if not isinstance(ps, dict) or "player_stats" not in ps:
        return stats
    for s in ps["player_stats"].get("stats", []):
        sid = s["stat"]["stat_id"]
        val = s["stat"]["value"]
        if sid in YAHOO_STAT_MAP:
            name, _ = YAHOO_STAT_MAP[sid]
            stats[name] = val
    return stats
```

Place after `extract_player_info` function.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/yahoo_query.py
git commit -m "feat: add stat_id mapping and stats parser to yahoo_query"
```

---

### Task 2: Add stats to `fa` command output

**Files:**
- Modify: `daily-advisor/yahoo_query.py` — `cmd_fa` function

- [ ] **Step 1: Change sub-resource from `/percent_owned` to `/percent_owned,stats`**

In `cmd_fa`, change the API path:

```python
# Before:
path = f"/league/{league_key}/players;{filter_str}/percent_owned"

# After:
path = f"/league/{league_key}/players;{filter_str}/percent_owned,stats"
```

- [ ] **Step 2: Extract stats in the player loop**

After `p = extract_player_info(v["player"])`, add stats extraction:

```python
stats = parse_player_stats(v["player"])
p["stats"] = stats
```

- [ ] **Step 3: Add stats columns to output**

Replace the output section. For batters show AVG/OPS/HR/BB, for pitchers show ERA/WHIP/K/IP. Detect by checking if "ERA" is in stats:

```python
# Output
pos_filter = args.position or "ALL"
print(f"=== FA 查詢 (position={pos_filter}, sort={args.sort}, count={args.count}) ===\n")

for i, p in enumerate(players, 1):
    po = f"{p['percent_owned']}%" if p["percent_owned"] else "—"
    st = p["status"] if p["status"] else ""
    stats = p.get("stats", {})

    # Format stats line based on player type
    if "ERA" in stats:
        stat_str = f"ERA {stats.get('ERA', '—')} | WHIP {stats.get('WHIP', '—')} | K {stats.get('K', '—')} | IP {stats.get('IP', '—')}"
    elif "AVG" in stats:
        stat_str = f"AVG {stats.get('AVG', '—')} | OPS {stats.get('OPS', '—')} | HR {stats.get('HR', '—')} | BB {stats.get('BB', '—')}"
    else:
        stat_str = ""

    print(f"{i:3}  {p['name']:20}  {p['team']:5}  {p['position']:12}  {po:>7}  {stat_str}  {st}")
```

- [ ] **Step 4: Test**

```bash
python daily-advisor/yahoo_query.py fa --position CF --count 3
python daily-advisor/yahoo_query.py fa --position SP --count 3
```

Expected: stats columns appear after %owned.

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/yahoo_query.py
git commit -m "feat: add stats to fa command output"
```

---

### Task 3: Change `fa` default status from `A` to `FA`

**Files:**
- Modify: `daily-advisor/yahoo_query.py` — argparse section

- [ ] **Step 1: Change default**

```python
# Before:
fa_parser.add_argument("--status", default="A", help="Player status: FA, A (all available), W (waivers) (default: A)")

# After:
fa_parser.add_argument("--status", default="FA", help="Player status: FA (free agents), A (all available), W (waivers) (default: FA)")
```

- [ ] **Step 2: Test**

```bash
python daily-advisor/yahoo_query.py fa --count 5
python daily-advisor/yahoo_query.py fa --status A --count 5
```

Expected: default shows only pure FA, `--status A` includes waiver players too.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/yahoo_query.py
git commit -m "fix: change fa default status from A to FA"
```

---

### Task 4: Add two-step lookup to `player` command (stats + percent_owned)

**Files:**
- Modify: `daily-advisor/yahoo_query.py` — `cmd_player` function

- [ ] **Step 1: Extract player_key from search results**

After finding players_data via `_search_players`, extract the player_key:

```python
for k, v in players_data.items():
    if k == "count":
        continue
    p = extract_player_info(v["player"])
    player_key = p.get("player_key")
```

- [ ] **Step 2: Do second API call for stats + percent_owned**

After getting player_key, make two additional calls:

```python
    # Second call: stats + percent_owned via player_key
    stats = {}
    percent_owned = None
    if player_key:
        try:
            stats_data = api_get(
                f"/league/{league_key}/players;player_keys={player_key}/stats",
                access_token,
            )
            sp = stats_data["fantasy_content"]["league"][1]["players"]["0"]["player"]
            stats = parse_player_stats(sp)
        except Exception:
            pass
        try:
            po_data = api_get(
                f"/league/{league_key}/players;player_keys={player_key}/percent_owned",
                access_token,
            )
            pp = po_data["fantasy_content"]["league"][1]["players"]["0"]["player"]
            for item in pp[1].get("percent_owned", []):
                if isinstance(item, dict) and "value" in item:
                    percent_owned = item["value"]
        except Exception:
            pass
```

- [ ] **Step 3: Update output to show stats and percent_owned**

```python
    po_str = f"{percent_owned}%" if percent_owned is not None else "—"
    print(f"=== {p['name']} ===")
    print(f"隊伍: {p['team']}")
    print(f"位置: {p['position']}")
    print(f"持有率: {po_str}")
    print(f"狀態: {p['status'] or '健康'}")
    if stats:
        print(f"--- 本季數據 ---")
        for name, val in stats.items():
            print(f"  {name}: {val}")
    print()
```

- [ ] **Step 4: Test**

```bash
python daily-advisor/yahoo_query.py player "Stanton"
python daily-advisor/yahoo_query.py player "Hearn"
python daily-advisor/yahoo_query.py player "Skubal"
```

Expected: each shows team, position, %owned, and season stats.

- [ ] **Step 5: Commit**

```bash
git add daily-advisor/yahoo_query.py
git commit -m "feat: add stats and percent_owned to player command"
```

---

### Task 5: Add parallel agent file-write guard to player-eval skill

**Files:**
- Modify: `.claude/commands/player-eval.md` — Step 5 section

- [ ] **Step 1: Add parallel execution warning**

After the existing Step 5 header ("記錄評估結果"), add:

```markdown
> ⚠️ **平行執行注意**：多個 player-eval agent 同時跑時，各 agent 不要自行寫入 waiver-log.md（會衝突）。改為在結論中列出建議的 log 更新內容，由主 session 統一寫入。單獨執行時正常寫入。
```

- [ ] **Step 2: Update Step 1.0 Yahoo API description to mention stats**

Update the description after the bash command:

```markdown
> 回傳：隊伍、Yahoo 守位資格、健康狀態、持有率、本季數據（AVG/OPS/HR/BB 或 ERA/WHIP/K/IP）。
```

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/player-eval.md
git commit -m "docs: add parallel write guard + stats note to player-eval"
```

---

### Task 6: Update waiver-scan and roster-scan skills

**Files:**
- Modify: `.claude/commands/waiver-scan.md` — Step 2a note
- Modify: `.claude/commands/roster-scan.md` — Step 2b note

- [ ] **Step 1: Update waiver-scan Step 2a**

After the bash commands block, update the note:

```markdown
> `yahoo_query.py fa` 現在回傳 7×7 scoring stats（打者 AVG/OPS/HR/BB，投手 ERA/WHIP/K/IP）+ %owned，可直接用於初篩，減少 WebSearch 依賴。
> `--position` 參數根據 CLAUDE.md 陣容風險動態決定，不硬編碼。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。
> 若 Yahoo API 失敗（HTTP 999 rate limit 等），fallback 到 Step 2b。
```

- [ ] **Step 2: Update roster-scan Step 2b**

Update the description:

```markdown
> `yahoo_query.py player` 現在回傳守位資格、持有率、本季 7×7 stats。可作為 WebSearch 的交叉驗證或替代來源。
> VPS 上需加 `export $(cat /etc/calorie-bot/op-token.env) &&` 前綴。
```

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/waiver-scan.md .claude/commands/roster-scan.md
git commit -m "docs: update skills to note stats availability from Yahoo API"
```

---

### Task 7: Update yahoo-api-reference.md

**Files:**
- Modify: `daily-advisor/yahoo-api-reference.md`

- [ ] **Step 1: Move stats and percent_owned to "已使用" section**

In the "已使用的端點" table, add:

```markdown
| `GET /league/{key}/players;{filters}/stats` | 球員本季數據（7×7 scoring） | `cmd_fa()`, `cmd_player()` |
| `GET /league/{key}/players;{filters}/percent_owned` | 持有率 | `cmd_fa()`, `cmd_player()` |
| `GET /league/{key}/players;player_keys={key}/stats` | 指定球員本季數據 | `cmd_player()` 二段查詢 |
| `GET /league/{key}/players;player_keys={key}/percent_owned` | 指定球員持有率 | `cmd_player()` 二段查詢 |
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/yahoo-api-reference.md
git commit -m "docs: update API reference with stats endpoints"
```

---

### Task 8: Integration test

- [ ] **Step 1: Run full test suite**

```bash
# FA with stats
python daily-advisor/yahoo_query.py fa --position CF --count 5
python daily-advisor/yahoo_query.py fa --position SP --count 5
python daily-advisor/yahoo_query.py fa --sort AR --sort-type lastweek --count 10

# Player with stats + %owned
python daily-advisor/yahoo_query.py player "Stanton"
python daily-advisor/yahoo_query.py player "O'Hearn"
python daily-advisor/yahoo_query.py player "Skubal"

# Edge cases
python daily-advisor/yahoo_query.py player "nonexistent_player_xyz"
python daily-advisor/yahoo_query.py fa --status A --count 3
```

- [ ] **Step 2: Verify daily-advisor main.py still works**

```bash
python daily-advisor/main.py --dry-run --date 2026-03-28
python daily-advisor/main.py --dry-run --morning --date 2026-03-28
```

Expected: no regression, yahoo_query.py changes don't affect main.py.

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration test fixes"
```
