# Weekly Review Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance weekly_review.py to include roster player performance data and weekly_scan results, enabling /weekly-review to complete the full "review -> predict -> FA action" cycle in one session.

**Architecture:** Two independent features added to `weekly_review.py --prepare`: (1) `compute_roster_performance()` fetches per-player weekly game logs + season Savant stats, outputting to `review.my_roster_performance`; (2) `fetch_scan_summary()` reads the latest weekly_scan GitHub Issue, outputting to `review.scan_summary`. Both feed into the existing JSON pipeline. The /weekly-review skill gets a new Step 4 for FA action decisions.

**Tech Stack:** Python 3, MLB Stats API (game logs), Baseball Savant CSV (Statcast), GitHub CLI (`gh`), Yahoo Fantasy API (existing)

**Branch:** `feat/weekly-review-enhancement`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `daily-advisor/daily_advisor.py` | Modify (add 1 function) | `fetch_batter_gamelog()` — batter game log from MLB API |
| `daily-advisor/weekly_review.py` | Modify (add 2 functions + main integration) | `compute_roster_performance()`, `fetch_scan_summary()`, wire into `main()` |
| `.claude/commands/weekly-review.md` | Modify | Add roster performance references in Step 2, add Step 4 for FA action |
| `CLAUDE.md` | Modify | Update cron schedule, mark TODOs done |

---

### Task 1: Add `fetch_batter_gamelog()` to daily_advisor.py

**Files:**
- Modify: `daily-advisor/daily_advisor.py:281` (after `fetch_pitcher_gamelog`)

This mirrors the existing `fetch_pitcher_gamelog()` pattern (line 266-281) but for hitting.

- [ ] **Step 1: Add `fetch_batter_gamelog()` function**

Insert after `fetch_pitcher_gamelog()` (line 281), before `fetch_lineups()` (line 284):

```python
def fetch_batter_gamelog(player_id, season):
    """Fetch batting game log for the season."""
    data = api_get(
        f"/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    return [
        {
            "date": s["date"],
            "opponent": s.get("opponent", {}).get("name", "?"),
            "pa": int(s["stat"].get("plateAppearances", 0)),
            "ab": int(s["stat"].get("atBats", 0)),
            "r": int(s["stat"].get("runs", 0)),
            "h": int(s["stat"].get("hits", 0)),
            "hr": int(s["stat"].get("homeRuns", 0)),
            "rbi": int(s["stat"].get("rbi", 0)),
            "sb": int(s["stat"].get("stolenBases", 0)),
            "bb": int(s["stat"].get("baseOnBalls", 0)),
            "doubles": int(s["stat"].get("doubles", 0)),
            "triples": int(s["stat"].get("triples", 0)),
            "hbp": int(s["stat"].get("hitByPitch", 0)),
            "sf": int(s["stat"].get("sacrificeFlies", 0)),
        }
        for s in splits
    ]
```

- [ ] **Step 2: Verify function works**

```bash
python -c "
import sys; sys.path.insert(0,'daily-advisor')
from daily_advisor import fetch_batter_gamelog
log = fetch_batter_gamelog(592518, 2026)  # Manny Machado
for g in log[:3]:
    print(g)
print(f'Total games: {len(log)}')
"
```

Expected: List of game dicts with date, pa, r, hr, etc. Non-empty if season has started.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/daily_advisor.py
git commit -m "feat(daily_advisor): add fetch_batter_gamelog for weekly stats"
```

---

### Task 2: Add `compute_roster_performance()` to weekly_review.py

**Files:**
- Modify: `daily-advisor/weekly_review.py` (add imports + new function before `main()`)

This is the core function. It fetches game logs for the previous week, season totals, and Savant data for all roster players.

- [ ] **Step 1: Add imports**

At the top of `weekly_review.py`, **append** after the existing `from yahoo_query import (...)` block (line 24-28). Note: `pitcher_type` is already imported at line 27 via `from yahoo_query import ... pitcher_type` — do NOT duplicate it.

```python
from daily_advisor import (
    fetch_batter_gamelog, fetch_pitcher_gamelog,
    fetch_savant_statcast, fetch_savant_expected,
    fetch_savant_for_pitchers,
    pctile_tag, parse_ip,
)
from roster_stats import fetch_batter_full, fetch_pitcher_full
```

- [ ] **Step 2: Add helper `_aggregate_batter_weekly()`**

Insert before `main()` (line 448), after the `git_push()` function:

```python
# ── Roster Performance ──


def _aggregate_batter_weekly(gamelog, week_start, week_end):
    """Aggregate batter game log entries within a date range.

    Returns dict with PA, R, HR, RBI, SB, BB, AVG, OPS or None if no games.
    """
    start_str = week_start.isoformat()
    end_str = week_end.isoformat()
    games = [g for g in gamelog if start_str <= g["date"] <= end_str]
    if not games:
        return None

    pa = sum(g["pa"] for g in games)
    ab = sum(g["ab"] for g in games)
    h = sum(g["h"] for g in games)
    r = sum(g["r"] for g in games)
    hr = sum(g["hr"] for g in games)
    rbi = sum(g["rbi"] for g in games)
    sb = sum(g["sb"] for g in games)
    bb = sum(g["bb"] for g in games)
    doubles = sum(g["doubles"] for g in games)
    triples = sum(g["triples"] for g in games)
    hbp = sum(g["hbp"] for g in games)
    sf = sum(g["sf"] for g in games)

    avg = round(h / ab, 3) if ab > 0 else 0
    # OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    obp_denom = ab + bb + hbp + sf
    obp = (h + bb + hbp) / obp_denom if obp_denom > 0 else 0
    # SLG = TB / AB, TB = H + 2B + 2*3B + 3*HR
    tb = h + doubles + 2 * triples + 3 * hr
    slg = tb / ab if ab > 0 else 0
    ops = round(obp + slg, 3)

    return {
        "games": len(games),
        "pa": pa, "r": r, "hr": hr, "rbi": rbi,
        "sb": sb, "bb": bb, "avg": avg, "ops": ops,
    }
```

- [ ] **Step 3: Expand `fetch_pitcher_gamelog()` in daily_advisor.py**

Modify `daily-advisor/daily_advisor.py` lines 266-281 to include additional fields needed for WHIP and W:

```python
def fetch_pitcher_gamelog(player_id, season):
    """Fetch pitching game log for the season."""
    data = api_get(
        f"/people/{player_id}/stats?stats=gameLog&season={season}&group=pitching"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    return [
        {
            "date": s["date"],
            "opponent": s.get("opponent", {}).get("name", "?"),
            "ip": parse_ip(s["stat"].get("inningsPitched", 0)),
            "er": int(s["stat"].get("earnedRuns", 0)),
            "k": int(s["stat"].get("strikeOuts", 0)),
            "w": int(s["stat"].get("wins", 0)),
            "h": int(s["stat"].get("hits", 0)),
            "bb": int(s["stat"].get("baseOnBalls", 0)),
        }
        for s in splits
    ]
```

New fields: `w`, `h`, `bb`. Existing consumers (`roster_stats.py:fetch_pitcher_full`) only use `ip`, `er`, `k` — the new fields are additive and backward-compatible.

- [ ] **Step 4: Add helper `_aggregate_pitcher_weekly()`**

Insert immediately after `_aggregate_batter_weekly()`. This is the complete version with W and WHIP (requires the expanded `fetch_pitcher_gamelog` from Step 3):

```python
def _aggregate_pitcher_weekly(gamelog, week_start, week_end):
    """Aggregate pitcher game log entries within a date range.

    Returns dict with starts, IP, W, K, ERA, WHIP, QS or None if no games.
    """
    start_str = week_start.isoformat()
    end_str = week_end.isoformat()
    games = [g for g in gamelog if start_str <= g["date"] <= end_str]
    if not games:
        return None

    ip = sum(g["ip"] for g in games)
    er = sum(g["er"] for g in games)
    k = sum(g["k"] for g in games)
    w = sum(g["w"] for g in games)
    h = sum(g["h"] for g in games)
    bb = sum(g["bb"] for g in games)
    qs = sum(1 for g in games if g["ip"] >= 6.0 and g["er"] <= 3)

    era = round(er * 9 / ip, 2) if ip > 0 else 0
    whip = round((h + bb) / ip, 2) if ip > 0 else 0
    return {
        "starts": len(games),
        "ip": round(ip, 1), "w": w, "k": k, "qs": qs,
        "era": era, "whip": whip,
    }
```

- [ ] **Step 5: Add main `compute_roster_performance()`**

Insert after `_aggregate_pitcher_weekly()`:

```python
def compute_roster_performance(config, prev_week_start, prev_week_end, season):
    """Compute per-player performance for the previous week + season-to-date.

    Returns dict: {"batters": [...], "pitchers": [...]}
    """
    batters_cfg = config.get("batters", [])
    pitchers_cfg = config.get("pitchers", [])

    # Collect all mlb_ids for batch Savant download
    batter_ids = [b["mlb_id"] for b in batters_cfg if b.get("mlb_id")]
    pitcher_ids = [p["mlb_id"] for p in pitchers_cfg
                   if p.get("mlb_id") and pitcher_type(p) == "SP"]

    # Savant batch download (4 CSVs total — 2 batter, 2 pitcher)
    print("  Fetching Savant CSV for roster...", file=sys.stderr)
    bat_sc = fetch_savant_statcast(season, batter_ids, player_type="batter")
    bat_ex = fetch_savant_expected(season, batter_ids, player_type="batter")
    pit_savant = fetch_savant_for_pitchers(pitcher_ids, season)

    # ── Batters ──
    batter_results = []
    for b in batters_cfg:
        mid = b.get("mlb_id")
        if not mid:
            continue

        print(f"    Batter: {b['name']}...", file=sys.stderr)
        # Weekly game log
        try:
            gamelog = fetch_batter_gamelog(mid, season)
        except Exception as e:
            print(f"      gamelog error: {e}", file=sys.stderr)
            gamelog = []
        weekly = _aggregate_batter_weekly(gamelog, prev_week_start, prev_week_end)

        # Season totals (MLB API)
        season_mlb = fetch_batter_full(mid, season)

        # Savant data
        sc = bat_sc.get(mid, {})
        ex = bat_ex.get(mid, {})
        xwoba = ex.get("xwoba")
        hh_pct = sc.get("hh_pct")
        barrel_pct = sc.get("barrel_pct")
        bbe = sc.get("bbe", 0)
        bb_pct = season_mlb.get("bb_pct") if season_mlb else None

        pctiles = {}
        if xwoba:
            pctiles["xwoba"] = pctile_tag(xwoba, "xwoba")
        if bb_pct is not None:
            pctiles["bb_pct"] = pctile_tag(bb_pct, "bb_pct")
        if barrel_pct:
            pctiles["barrel_pct"] = pctile_tag(barrel_pct, "barrel_pct")
        if hh_pct:
            pctiles["hh_pct"] = pctile_tag(hh_pct, "hh_pct")

        entry = {
            "name": b["name"],
            "team": b["team"],
            "positions": b.get("positions", []),
            "selected_pos": b.get("selected_pos", ""),
            "weekly": weekly,
            "season": {
                **(season_mlb or {}),
                "xwoba": xwoba,
                "hh_pct": hh_pct,
                "barrel_pct": barrel_pct,
                "bbe": bbe,
            },
            "pctiles": pctiles,
        }
        batter_results.append(entry)
        time.sleep(0.2)

    # ── SP only (CLAUDE.md: RP 只有 2 人不評估) ──
    pitcher_results = []
    for p in pitchers_cfg:
        mid = p.get("mlb_id")
        if not mid or pitcher_type(p) != "SP":
            continue

        print(f"    SP: {p['name']}...", file=sys.stderr)
        # Weekly game log
        try:
            gamelog = fetch_pitcher_gamelog(mid, season)
        except Exception as e:
            print(f"      gamelog error: {e}", file=sys.stderr)
            gamelog = []
        weekly = _aggregate_pitcher_weekly(gamelog, prev_week_start, prev_week_end)

        # Season totals (MLB API)
        season_mlb = fetch_pitcher_full(mid, season)

        # Savant data — fetch_savant_for_pitchers returns 0 (not None) as default,
        # so use `or None` to normalize falsy-zero to None for pctile guard
        sv = (pit_savant.get(mid) or {}).get("current") or {}
        xera = sv.get("xera") or None
        xwoba_a = sv.get("xwoba") or None
        hh_pct_a = sv.get("hh_pct") or None
        barrel_pct_a = sv.get("barrel_pct") or None
        bbe = sv.get("bbe", 0)

        pctiles = {}
        if xera is not None:
            pctiles["xera"] = pctile_tag(xera, "xera", "pitcher")
        if xwoba_a is not None:
            pctiles["xwoba_allowed"] = pctile_tag(xwoba_a, "xwoba", "pitcher")
        if hh_pct_a is not None:
            pctiles["hh_pct_allowed"] = pctile_tag(hh_pct_a, "hh_pct", "pitcher")

        entry = {
            "name": p["name"],
            "team": p["team"],
            "selected_pos": p.get("selected_pos", ""),
            "weekly": weekly,
            "season": {
                **(season_mlb or {}),
                "xera": xera,
                "xwoba_allowed": xwoba_a,
                "hh_pct_allowed": hh_pct_a,
                "barrel_pct_allowed": barrel_pct_a,
                "bbe": bbe,
            },
            "pctiles": pctiles,
        }
        pitcher_results.append(entry)
        time.sleep(0.2)

    return {"batters": batter_results, "pitchers": pitcher_results}
```

- [ ] **Step 6: Verify `compute_roster_performance()` works**

```bash
python -c "
import sys; sys.path.insert(0,'daily-advisor')
from weekly_review import load_config, get_fantasy_week, compute_roster_performance
from yahoo_query import pitcher_type
from datetime import date
import json

config = load_config()
season = config['league']['season']
# Use week 2 as example
ws, we, wn = get_fantasy_week(date(2026, 4, 6), config)
prev_ws = ws - __import__('datetime').timedelta(days=7)
prev_we = ws - __import__('datetime').timedelta(days=1)
print(f'Previous week: {prev_ws} ~ {prev_we}')

perf = compute_roster_performance(config, prev_ws, prev_we, season)
print(json.dumps(perf, indent=2, ensure_ascii=False, default=str)[:2000])
"
```

Expected: JSON with `batters` and `pitchers` arrays, each entry having `name`, `weekly` (stats or null), `season`, `pctiles`.

- [ ] **Step 7: Commit**

```bash
git add daily-advisor/daily_advisor.py daily-advisor/weekly_review.py
git commit -m "feat(weekly_review): add compute_roster_performance with game logs + Savant"
```

---

### Task 3: Integrate roster performance into `main()`

**Files:**
- Modify: `daily-advisor/weekly_review.py` (main function, lines 451-561)

- [ ] **Step 1: Wire `compute_roster_performance()` into the review section**

In `main()`, first add `season` extraction (currently missing). At line 472, change:

```python
    league_key = config["league"]["league_key"]
    team_name = config["league"]["team_name"]
```

to:

```python
    league_key = config["league"]["league_key"]
    team_name = config["league"]["team_name"]
    season = config["league"]["season"]
```

Then replace the review block (lines 478-499) with:

```python
    # ── Review: last week's data ──
    prev_week = week_number - 1
    review_data = {}
    if prev_week >= 1:
        print(f"  Fetching week {prev_week} scoreboard (all teams)...", file=sys.stderr)
        my_matchup, all_teams = fetch_league_scoreboard(
            league_key, access_token, prev_week, team_name)

        print(f"  Computing category ranks...", file=sys.stderr)
        category_ranks = compute_category_ranks(all_teams, team_name)

        print(f"  Fetching daily report metadata...", file=sys.stderr)
        daily_reports = fetch_daily_reports_metadata(prev_week)

        # Previous week date range for game log filtering
        prev_ws, prev_we, _ = get_fantasy_week(week_start - timedelta(days=1), config)
        print(f"  Computing roster performance ({prev_ws} ~ {prev_we})...", file=sys.stderr)
        roster_perf = compute_roster_performance(config, prev_ws, prev_we, season)

        review_data = {
            **(my_matchup or {}),
            "league_category_ranks": category_ranks,
            "daily_reports": daily_reports,
            "my_roster_performance": roster_perf,
        }
    else:
        print("  Week 1 — no previous week to review", file=sys.stderr)
```

- [ ] **Step 2: Test with `--dry-run`**

```bash
cd daily-advisor && python weekly_review.py --prepare --dry-run 2>weekly_review_debug.log | python -c "
import sys, json
data = json.load(sys.stdin)
perf = data.get('review', {}).get('my_roster_performance', {})
print(f'Batters: {len(perf.get(\"batters\", []))}')
print(f'Pitchers: {len(perf.get(\"pitchers\", []))}')
if perf.get('batters'):
    b = perf['batters'][0]
    print(f'First batter: {b[\"name\"]}')
    print(f'  Weekly: {b.get(\"weekly\")}')
    print(f'  Season xwOBA: {b[\"season\"].get(\"xwoba\")}')
    print(f'  Pctiles: {b.get(\"pctiles\")}')
"
```

Expected: Batter count ~13-15, Pitcher count ~7-9, with populated weekly/season/pctiles data.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly_review): integrate roster performance into review JSON output"
```

---

### Task 4: Add `fetch_scan_summary()` to weekly_review.py

**Files:**
- Modify: `daily-advisor/weekly_review.py` (add function before `main()`)

- [ ] **Step 1: Add `fetch_scan_summary()` function**

Insert after `compute_roster_performance()`, before `main()`:

```python
def fetch_scan_summary(week_start):
    """Fetch the latest weekly_scan GitHub Issue if it's from this week.

    Returns dict with issue_number, issue_url, analysis text, or None.
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", "huansbox/mlb-fantasy",
             "--label", "waiver-scan",
             "--state", "all",
             "--json", "number,title,body,url,createdAt",
             "--limit", "1"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode != 0:
            print(f"  gh issue list (waiver-scan) failed: {result.stderr}", file=sys.stderr)
            return None

        issues = json.loads(result.stdout)
        if not issues:
            return None

        issue = issues[0]
        # Check if issue was created within this week (on or after week_start)
        created = issue["createdAt"][:10]  # "2026-04-07T..." -> "2026-04-07"
        if created < week_start.isoformat():
            print(f"  Latest scan issue ({created}) is before this week ({week_start}), skipping",
                  file=sys.stderr)
            return None

        # Extract analysis section from issue body
        body = issue.get("body", "")
        analysis = ""
        if "## Analysis" in body:
            parts = body.split("## Analysis", 1)
            if len(parts) > 1:
                # Take text between "## Analysis" and the next "---"
                remainder = parts[1]
                if "\n---\n" in remainder:
                    analysis = remainder.split("\n---\n", 1)[0].strip()
                else:
                    analysis = remainder.strip()

        return {
            "issue_number": issue["number"],
            "issue_url": issue.get("url", ""),
            "issue_date": created,
            "analysis": analysis,
        }
    except Exception as e:
        print(f"  fetch_scan_summary error: {e}", file=sys.stderr)
        return None
```

- [ ] **Step 2: Verify function works**

```bash
python -c "
import sys; sys.path.insert(0,'daily-advisor')
from weekly_review import fetch_scan_summary
from datetime import date
result = fetch_scan_summary(date(2026, 4, 6))
if result:
    print(f'Issue #{result[\"issue_number\"]} ({result[\"issue_date\"]})')
    print(f'URL: {result[\"issue_url\"]}')
    print(f'Analysis length: {len(result[\"analysis\"])} chars')
    print(f'First 200 chars: {result[\"analysis\"][:200]}')
else:
    print('No scan summary found for this week')
"
```

Expected: Either a valid scan summary from this week, or "No scan summary found" if scan hasn't run yet.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly_review): add fetch_scan_summary to read latest weekly_scan issue"
```

---

### Task 5: Integrate scan summary into `main()`

**Files:**
- Modify: `daily-advisor/weekly_review.py` (main function)

- [ ] **Step 1: Add scan summary fetch to review section**

In `main()`, after the `roster_perf` block and before the preview section, add:

```python
        # ── Scan summary (if weekly_scan ran this week) ──
        print(f"  Checking for weekly scan summary...", file=sys.stderr)
        scan_summary = fetch_scan_summary(week_start)
        if scan_summary:
            print(f"  Found scan issue #{scan_summary['issue_number']} ({scan_summary['issue_date']})",
                  file=sys.stderr)
            review_data["scan_summary"] = scan_summary
        else:
            print(f"  No scan summary for this week", file=sys.stderr)
```

This goes inside the `if prev_week >= 1:` block, after `review_data = {...}` is assembled, so it appends to the existing dict.

- [ ] **Step 2: Test full pipeline with `--dry-run`**

```bash
cd daily-advisor && python weekly_review.py --prepare --dry-run 2>weekly_review_debug.log | python -c "
import sys, json
data = json.load(sys.stdin)
review = data.get('review', {})
scan = review.get('scan_summary')
if scan:
    print(f'Scan: Issue #{scan[\"issue_number\"]} ({scan[\"issue_date\"]})')
    print(f'Analysis: {scan[\"analysis\"][:100]}...')
else:
    print('No scan summary in output (expected if scan has not run this week)')
perf = review.get('my_roster_performance', {})
print(f'Roster perf: {len(perf.get(\"batters\",[]))} batters, {len(perf.get(\"pitchers\",[]))} SPs')
"
```

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/weekly_review.py
git commit -m "feat(weekly_review): integrate scan summary into review JSON"
```

---

### Task 6: Update /weekly-review skill

**Files:**
- Modify: `.claude/commands/weekly-review.md`

- [ ] **Step 1: Update Step 2 (Phase 1) to reference roster performance**

Replace Step 2 point 1 (line 31: `1. 從 JSON review 區塊讀取 14 類別...`) with expanded instructions. The full replacement for Step 2:

```markdown
## Step 2（Phase 1）：覆盤上週

> 如果是開季第一週（無上週資料），跳過 Phase 1，直接進 Phase 2。

1. 從 JSON `review` 區塊讀取 14 類別 mine/opp/result
2. 從 `week-reviews.md` 讀取上週的 predicted_outcome（strong/toss_up/weak 分類）
3. 顯示對照表：

   | 類別 | 預測 | 實際 | ✓/✗ | mine | opp |
   |------|------|------|------|------|-----|

4. 計算準確率（correct / total）
5. 顯示聯盟類別排名（league_category_ranks）
6. **球員表現分析**（從 `review.my_roster_performance`）：
   - 打者：列出當週 PA/R/HR/RBI/SB/BB/AVG/OPS + 開季 xwOBA/BB%/Barrel% 百分位
   - SP：列出當週 GS/IP/W/K/ERA/WHIP/QS + 開季 xERA/xwOBA allowed 百分位
   - 標記「撐場者」（當週貢獻突出）和「拖累者」（當週表現遠低於開季水準或空白）
   - 結合類別勝負：哪些球員直接影響了哪些類別的 W/L
7. 掃描日報品質（用 `gh issue view {number}` 讀取 daily_reports 中的 issues）：
   - 速報 → 最終報推翻次數及類型
   - 「Lineup 未公布」出現比例
8. **詢問用戶**：預測偏差的原因（逐項標記或整體說明）
9. 寫入 `week-reviews.md` 的覆盤區塊
```

- [ ] **Step 2: Add Step 4 for FA action decisions**

After Step 3 (Phase 2), add new Step 4. Append before the `## week-reviews.md 格式` section:

```markdown
## Step 4（FA 行動決策）：整合 Scan 建議

> 若 JSON 中無 `review.scan_summary`（scan 未跑或非本週），跳過此步驟。

1. 讀 `review.scan_summary.analysis`（weekly_scan 的 Claude 分析摘要）
2. 交叉比對：
   - Phase 1 發現的拖累者 → 哪個位置需要補強？
   - Phase 2 預測的弱項類別 → FA 候選能改善哪些？
   - scan 推薦的候選 → 是否比現有最弱球員更好？
3. 決策輸出（三選一）：
   - **立即行動**：候選明確優於拖累者 → 列出 add/drop 建議 + FAAB 出價
   - **深入評估**：候選有潛力但需確認 → 建議跑 `/player-eval {球員名}`
   - **繼續觀察**：本週無明確升級 → 不動
4. 將決策寫入 `week-reviews.md` 的 FA 行動區塊
```

- [ ] **Step 3: Update `week-reviews.md` 格式 section**

In the format template at the bottom of the skill, add the new sections. Replace the existing format block with:

```markdown
## `week-reviews.md` 格式

每週追加一段，格式如下：

~~~markdown
## Week {N} vs {對手名}

### 預測（{日期} 產出）
| 類別 | 預測 | 信心 | 理由 |
|------|------|------|------|
| R | W | 中 | 我方打線較深 |
| ...

整體：{projected_record}，{strategy}

### 覆盤（{日期} 回顧）
| 類別 | 預測 | 實際 | ✓/✗ | 偏差原因 |
|------|------|------|------|---------|
| WHIP | W | L | ✗ | Nola@Coors |
| ...

準確率：{correct}/{total}（{pct}%）

#### 球員表現
- 撐場者：{球員} — {原因}
- 拖累者：{球員} — {原因}

### 日報品質
- 速報→最終報推翻：{N} 次（{類型}）
- Lineup 未公布比例：速報 {N}%
- Prompt 調整建議：{建議或「無」}

### FA 行動
- {決策：立即行動/深入評估/繼續觀察}
- {具體建議或「本週無明確升級」}

### 學到什麼
- {insight}
~~~
```

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/weekly-review.md
git commit -m "feat(weekly-review skill): add roster performance analysis + FA action step"
```

---

### Task 7: Update CLAUDE.md and cron schedule

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update cron schedule description**

In CLAUDE.md, update the cron comment in `weekly_review.py` docstring. In `daily-advisor/weekly_review.py` line 7, change:

```
Cron: 每週一 TW 18:00 (UTC 10:00)，在 Weekly Scan 之前執行。
```

to:

```
Cron: 每週一 TW 13:00 (UTC 05:00)，在 Weekly Scan 之後執行。
```

- [ ] **Step 2: Mark TODOs as done in CLAUDE.md**

In CLAUDE.md, mark the two TODO sections as done:

Replace the `### weekly_review 加入隊上球員表現評估` section header and content with a completed version:

```markdown
### ~~weekly_review 加入隊上球員表現評估~~ ✅ 完成（2026-04-07）

> `review.my_roster_performance`：打者當週 game log + 開季 Savant，SP 同理。RP 不評估。
```

Replace the `### weekly_review 整合 weekly_scan 結果` section header and content with:

```markdown
### ~~weekly_review 整合 weekly_scan 結果~~ ✅ 完成（2026-04-07）

> cron 順序：weekly_scan TW 12:30 → weekly_review TW 13:00。`review.scan_summary` 讀最新 waiver-scan Issue。/weekly-review skill 加 Step 4 FA 行動決策。
```

- [ ] **Step 3: Update cron on VPS**

SSH to VPS and update cron schedule:

```bash
ssh root@107.175.30.172 'crontab -l'
# Verify current schedule, then update:
# weekly_scan: TW 12:30 (UTC 04:30) — runs FIRST
# weekly_review: TW 13:00 (UTC 05:00) — runs SECOND (reads scan output)
```

Exact cron change depends on current VPS crontab content. The key change:
- weekly_scan stays at or moves to `30 4 * * 1` (UTC)
- weekly_review moves to `0 5 * * 1` (UTC)

- [ ] **Step 4: Commit all doc changes**

```bash
git add CLAUDE.md daily-advisor/weekly_review.py
git commit -m "docs: mark weekly_review enhancements as done, update cron schedule"
```

---

## Verification Checklist

After all tasks complete, run the full pipeline:

```bash
cd daily-advisor && python weekly_review.py --prepare --dry-run 2>debug.log
```

Verify the JSON output contains:
- [ ] `review.my_roster_performance.batters` — array with weekly + season + pctiles per batter
- [ ] `review.my_roster_performance.pitchers` — array with weekly + season + pctiles per SP
- [ ] `review.scan_summary` — present if weekly_scan Issue exists for this week, null otherwise
- [ ] All existing fields (`review.categories`, `preview.opponent_roster`, etc.) still present
- [ ] No Python errors in `debug.log`
