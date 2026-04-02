# roster_sync.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-sync Yahoo Fantasy roster to `roster_config.json` after daily waiver processing, including mlb_id lookup and prior_stats for new players.

**Architecture:** Standalone script with two modes: `--init` (full bootstrap) and daily cron (transactions gate + incremental diff). Reuses Yahoo OAuth from `yahoo_query.py`, defines own MLB API + Savant helpers. State tracked via `.last_sync` timestamp file.

**Tech Stack:** Python 3 stdlib (no external deps), Yahoo Fantasy API, MLB Stats API, Baseball Savant CSV

**Spec:** `docs/superpowers/specs/2026-04-03-roster-sync-design.md`

**Branch:** `feat/roster-sync`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `daily-advisor/roster_sync.py` | Create | Main script — all sync logic |
| `daily-advisor/roster_config.json` | Modified by script | Player data (yahoo_player_key, prior_stats added) |
| `daily-advisor/.last_sync` | Created by script | Timestamp of last successful sync (gitignored) |
| `.gitignore` | Modify | Add `.last_sync` |

---

## Task 0: Pre-implementation — Verify MLB API people search

Before writing code, manually verify the MLB API search endpoint works with edge cases.

**Files:** None (investigation only)

- [ ] **Step 1: Test MLB API people search on VPS**

```bash
ssh root@107.175.30.172 "python3 -c '
import urllib.request, json

def mlb_search(name):
    url = f\"https://statsapi.mlb.com/api/v1/people/search?names={name}&sportIds=1&active=true\"
    resp = urllib.request.urlopen(url, timeout=10)
    data = json.loads(resp.read())
    rows = data.get(\"people\", [])
    for r in rows[:3]:
        print(f\"  {r[\"fullName\"]} | id={r[\"id\"]} | team={r.get(\"currentTeam\", {}).get(\"abbreviation\", \"?\")} | active={r.get(\"active\")}\")

print(\"=== Jazz Chisholm Jr. ===\")
mlb_search(\"Jazz Chisholm Jr.\")
print(\"=== Jose Altuve (no accent) ===\")
mlb_search(\"Jose Altuve\")
print(\"=== Parker Messick (rookie) ===\")
mlb_search(\"Parker Messick\")
'"
```

Expected: Each returns at least one result with correct id. Record actual behavior for Jr. and accent handling.

- [ ] **Step 2: Document findings**

If search doesn't handle Jr./accents well, note the workaround (strip suffix, try without accent) for Task 5.

---

## Task 1: Scaffold + CLI + Yahoo helpers

**Files:**
- Create: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Create roster_sync.py with imports, constants, CLI**

```python
"""Roster sync — auto-update roster_config.json from Yahoo Fantasy API."""

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "roster_config.json")
LAST_SYNC_PATH = os.path.join(SCRIPT_DIR, ".last_sync")
MLB_API = "https://statsapi.mlb.com/api/v1"

sys.path.insert(0, SCRIPT_DIR)
from yahoo_query import load_env, refresh_token, api_get as yahoo_api_get, is_pitcher, pitcher_type  # noqa: E402


def load_config():
    """Load roster_config.json as dict."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Write config back to JSON with consistent formatting."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def mlb_api_get(path):
    """GET request to MLB Stats API (no auth needed)."""
    url = f"{MLB_API}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def read_last_sync():
    """Read last sync timestamp from state file. Returns 0 if not exists."""
    if os.path.exists(LAST_SYNC_PATH):
        with open(LAST_SYNC_PATH) as f:
            return int(f.read().strip())
    return 0


def write_last_sync(ts):
    """Write timestamp to state file."""
    with open(LAST_SYNC_PATH, "w") as f:
        f.write(str(ts))


def main():
    parser = argparse.ArgumentParser(description="Sync Yahoo roster to roster_config.json")
    parser.add_argument("--init", action="store_true", help="Full bootstrap: pull entire roster and build config")
    parser.add_argument("--dry-run", action="store_true", help="Print diff without writing config or pushing")
    args = parser.parse_args()

    env = load_env()
    token = refresh_token(env)
    config = load_config()
    league_key = config["league"]["league_key"]

    my_key = find_my_team_key(league_key, token)
    print(f"Team key: {my_key}", file=sys.stderr)

    if args.init:
        run_init(my_key, token, config, args.dry_run)
    else:
        run_daily(league_key, my_key, token, config, env, args.dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify scaffold runs**

```bash
cd daily-advisor && python3 roster_sync.py --help
```

Expected: Help text with `--init` and `--dry-run` flags.

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): scaffold with CLI, config I/O, MLB API helper"
```

---

## Task 2: Yahoo API — find team key + fetch full roster

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add find_my_team_key()**

```python
def find_my_team_key(league_key, token):
    """Find our team_key from Yahoo league teams endpoint."""
    data = yahoo_api_get(f"/league/{league_key}/teams", token)
    teams = data["fantasy_content"]["league"][1]["teams"]
    for k, v in teams.items():
        if k == "count":
            continue
        for item in v["team"][0]:
            if isinstance(item, dict) and "is_owned_by_current_login" in item:
                for it in v["team"][0]:
                    if isinstance(it, dict) and "team_key" in it:
                        return it["team_key"]
    raise RuntimeError("Could not find my team key")
```

- [ ] **Step 2: Add fetch_full_roster()**

```python
def fetch_full_roster(team_key, token):
    """Fetch roster from Yahoo API, return list of player dicts.

    Each dict: {name, yahoo_player_key, team, positions, selected_pos}
    Positions is a list like ["2B", "3B"] or ["SP"].
    """
    data = yahoo_api_get(f"/team/{team_key}/roster", token)
    players_data = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    players = []
    for k, v in players_data.items():
        if k == "count":
            continue
        player = v["player"]
        info = player[0]
        pos_data = player[1]

        name = team_val = display_pos = player_key = None
        for item in info:
            if isinstance(item, dict):
                if "name" in item:
                    name = item["name"].get("full")
                if "editorial_team_abbr" in item:
                    team_val = item["editorial_team_abbr"].upper()
                if "display_position" in item:
                    display_pos = item["display_position"]
                if "player_key" in item:
                    player_key = item["player_key"]

        selected_pos = "BN"
        sel = pos_data.get("selected_position", [{}])
        for s in sel:
            if isinstance(s, dict) and "position" in s:
                selected_pos = s["position"]

        if not name or not display_pos:
            continue

        positions = [p.strip() for p in display_pos.split(",")]
        players.append({
            "name": name,
            "yahoo_player_key": player_key,
            "team": team_val or "?",
            "positions": positions,
            "selected_pos": selected_pos,
        })

    return players
```

- [ ] **Step 3: Verify on VPS with a test print**

Add temporary code at end of `main()` init branch:

```python
    if args.init:
        roster = fetch_full_roster(my_key, token)
        for p in roster:
            print(f"  {p['name']:25s} {p['yahoo_player_key']:15s} {p['team']:4s} {','.join(p['positions']):12s} [{p['selected_pos']}]")
        return
```

Run on VPS:
```bash
ssh root@107.175.30.172 "export $(cat /etc/calorie-bot/op-token.env) && export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin && cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py --init --dry-run"
```

Expected: All 23 roster players listed with correct names, player_keys, positions.

- [ ] **Step 4: Remove temporary test code, commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): fetch full roster from Yahoo API"
```

---

## Task 3: Transactions gate + .last_sync

**Files:**
- Modify: `daily-advisor/roster_sync.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add fetch_transactions()**

```python
def fetch_transactions(league_key, my_key, token):
    """Fetch our team's transactions from Yahoo API.

    Returns list of {timestamp: int, type: str, players: [{name, action}]}.
    """
    data = yahoo_api_get(f"/league/{league_key}/transactions;team_key={my_key}", token)
    content = data["fantasy_content"]["league"][1]

    # When no transactions exist, the key may be missing or empty
    if "transactions" not in content:
        return []

    txns_data = content["transactions"]
    result = []
    for k, v in txns_data.items():
        if k == "count":
            continue
        tx = v["transaction"]
        meta = tx[0]
        ts = int(meta.get("timestamp", 0))
        tx_type = meta.get("type", "")

        players = []
        players_data = tx[1].get("players", {})
        for pk, pv in players_data.items():
            if pk == "count":
                continue
            p = pv["player"]
            name = "?"
            for item in p[0]:
                if isinstance(item, dict) and "name" in item:
                    name = item["name"]["full"]
            for td in p[1].get("transaction_data", []):
                if isinstance(td, dict):
                    players.append({"name": name, "action": td.get("type", "?")})

        result.append({"timestamp": ts, "type": tx_type, "players": players})

    return sorted(result, key=lambda x: x["timestamp"], reverse=True)


def has_new_transactions(transactions, last_sync_ts):
    """Check if any transaction is newer than last sync."""
    for tx in transactions:
        if tx["timestamp"] > last_sync_ts:
            return True
    return False
```

- [ ] **Step 2: Add .last_sync to .gitignore**

Append to `.gitignore`:
```
daily-advisor/.last_sync
```

- [ ] **Step 3: Commit**

```bash
git add daily-advisor/roster_sync.py .gitignore
git commit -m "feat(roster-sync): transactions gate + .last_sync state file"
```

---

## Task 4: Diff logic

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add diff_roster()**

```python
def diff_roster(yahoo_roster, config):
    """Compare Yahoo roster vs config by yahoo_player_key.

    Returns {added: [yahoo_player_dicts], dropped: [config_player_dicts]}.
    For --init (config has no yahoo_player_key), falls back to name matching.
    """
    # Build config player key sets
    config_players = {}
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            key = p.get("yahoo_player_key")
            if key:
                config_players[key] = p
            else:
                # Fallback: name-based for --init bootstrap
                config_players[f"name:{p['name']}"] = p

    # Build Yahoo player key set
    yahoo_players = {}
    for p in yahoo_roster:
        key = p["yahoo_player_key"]
        yahoo_players[key] = p
        # Also add name-based key for --init matching
        yahoo_players[f"name:{p['name']}"] = p

    yahoo_keys = {p["yahoo_player_key"] for p in yahoo_roster}
    config_keys = set()
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            k = p.get("yahoo_player_key")
            if k:
                config_keys.add(k)

    # If config has no yahoo_player_keys yet (--init), use name matching
    if not config_keys:
        config_names = set()
        for section in ("batters", "pitchers"):
            for p in config.get(section, []):
                config_names.add(p["name"])
        yahoo_names = {p["name"] for p in yahoo_roster}
        added_names = yahoo_names - config_names
        dropped_names = config_names - yahoo_names
        added = [p for p in yahoo_roster if p["name"] in added_names]
        dropped = []
        for section in ("batters", "pitchers"):
            for p in config.get(section, []):
                if p["name"] in dropped_names:
                    dropped.append(p)
        return {"added": added, "dropped": dropped}

    added_keys = yahoo_keys - config_keys
    dropped_keys = config_keys - yahoo_keys
    added = [p for p in yahoo_roster if p["yahoo_player_key"] in added_keys]
    dropped = []
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            if p.get("yahoo_player_key") in dropped_keys:
                dropped.append(p)

    return {"added": added, "dropped": dropped}
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): diff roster by yahoo_player_key"
```

---

## Task 5: MLB API — mlb_id search

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add search_mlb_id()**

```python
def search_mlb_id(name):
    """Search MLB API for player's mlb_id by name.

    Handles Jr./Sr. suffixes and accent characters.
    Returns int mlb_id or None if not found.
    """
    import unicodedata

    def normalize(s):
        # Remove accents
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def try_search(query):
        encoded = urllib.parse.quote(query)
        try:
            data = mlb_api_get(f"/people/search?names={encoded}&sportIds=1&active=true")
            people = data.get("people", [])
            if people:
                return people[0]["id"]
        except Exception as e:
            print(f"  MLB search failed for '{query}': {e}", file=sys.stderr)
        return None

    # Try exact name first
    result = try_search(name)
    if result:
        return result

    # Try without suffix (Jr., Sr., II, III, IV)
    import re
    stripped = re.sub(r'\s+(Jr\.|Sr\.|II|III|IV)$', '', name).strip()
    if stripped != name:
        result = try_search(stripped)
        if result:
            return result

    # Try with accents removed
    normalized = normalize(name)
    if normalized != name:
        result = try_search(normalized)
        if result:
            return result

    # Try normalized + stripped
    normalized_stripped = normalize(stripped)
    if normalized_stripped != name and normalized_stripped != stripped:
        result = try_search(normalized_stripped)
        if result:
            return result

    print(f"  WARNING: Could not find mlb_id for '{name}'", file=sys.stderr)
    return None
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): MLB API mlb_id search with Jr./accent fallbacks"
```

---

## Task 6: Savant CSV + MLB Stats API — prior_stats

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add Savant CSV single-player lookup**

```python
def fetch_savant_player(mlb_id, year, player_type="batter"):
    """Fetch Savant data for a single player from full CSV.

    Returns {xwoba, hh_pct, barrel_pct, bbe, pa} for batter,
    or {xwoba, xera, hh_pct, barrel_pct, bbe} for pitcher.
    Returns None if player not found.
    """
    pid_str = str(mlb_id)

    # Statcast CSV (Hard-Hit%, Barrel%)
    sc_url = (
        f"https://baseballsavant.mlb.com/leaderboard/statcast"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    # Expected stats CSV (xwOBA, xERA)
    ex_url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )

    sc_data = ex_data = None
    for url, label in [(sc_url, "statcast"), (ex_url, "expected")]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            text = resp.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                if row.get("player_id", "").strip() == pid_str:
                    if label == "statcast":
                        sc_data = row
                    else:
                        ex_data = row
                    break
        except Exception as e:
            print(f"  Savant {label} fetch failed ({year}): {e}", file=sys.stderr)

    if not sc_data and not ex_data:
        return None

    result = {}
    if ex_data:
        result["xwoba"] = float(ex_data.get("est_woba", 0) or 0)
        result["pa"] = int(ex_data.get("pa", 0) or 0)
        if player_type == "pitcher":
            xera = ex_data.get("xera")
            result["xera"] = float(xera) if xera else 0
    if sc_data:
        result["hh_pct"] = float(sc_data.get("ev95percent", 0) or 0)
        result["barrel_pct"] = float(sc_data.get("brl_percent", 0) or 0)
        result["bbe"] = int(sc_data.get("attempts", 0) or 0)

    return result
```

- [ ] **Step 2: Add MLB Stats API prior season stats fetch**

```python
def fetch_mlb_season_stats(mlb_id, season, group="hitting"):
    """Fetch season stats from MLB Stats API.

    group: 'hitting' or 'pitching'
    Returns raw splits[0]['stat'] dict, or None.
    """
    try:
        data = mlb_api_get(
            f"/people/{mlb_id}/stats?stats=season&season={season}&group={group}"
        )
        stat_groups = data.get("stats", [])
        splits = stat_groups[0].get("splits", []) if stat_groups else []
        if not splits:
            return None
        return splits[0]["stat"]
    except Exception as e:
        print(f"  MLB stats fetch failed ({mlb_id}, {season}): {e}", file=sys.stderr)
        return None
```

- [ ] **Step 3: Add prior_stats builders for batter/SP/RP**

```python
FULL_SEASON_GAMES = 162  # 2025 full season


def build_prior_stats_batter(mlb_id):
    """Build prior_stats dict for a batter using 2025 data."""
    savant = fetch_savant_player(mlb_id, 2025, "batter")
    mlb_stats = fetch_mlb_season_stats(mlb_id, 2025, "hitting")

    if not savant and not mlb_stats:
        return None

    result = {"season": 2025}

    if savant:
        result["xwoba"] = round(savant.get("xwoba", 0), 3)
        result["barrel_pct"] = round(savant.get("barrel_pct", 0), 1)
        result["hh_pct"] = round(savant.get("hh_pct", 0), 1)

    if mlb_stats:
        pa = int(mlb_stats.get("plateAppearances", 0))
        bb = int(mlb_stats.get("baseOnBalls", 0))
        g = int(mlb_stats.get("gamesPlayed", 0))
        ops = mlb_stats.get("ops", "0")
        result["bb_pct"] = round(bb / pa * 100, 1) if pa > 0 else 0
        result["ops"] = float(ops) if ops != "—" else 0
        result["pa_per_team_g"] = round(pa / FULL_SEASON_GAMES, 2)
        result["pa"] = pa
        result["g"] = g

    return result


def build_prior_stats_sp(mlb_id):
    """Build prior_stats dict for an SP using 2025 data."""
    savant = fetch_savant_player(mlb_id, 2025, "pitcher")
    mlb_stats = fetch_mlb_season_stats(mlb_id, 2025, "pitching")

    if not savant and not mlb_stats:
        return None

    result = {"season": 2025}

    if savant:
        result["xera"] = round(savant.get("xera", 0), 2)
        result["xwoba_allowed"] = round(savant.get("xwoba", 0), 3)
        result["hh_pct_allowed"] = round(savant.get("hh_pct", 0), 1)
        result["barrel_pct_allowed"] = round(savant.get("barrel_pct", 0), 1)
        result["bbe"] = savant.get("bbe", 0)

    if mlb_stats:
        era = mlb_stats.get("era", "0")
        ip_str = mlb_stats.get("inningsPitched", "0")
        gs = int(mlb_stats.get("gamesStarted", 0))
        # Parse IP (6.1 = 6.333)
        ip = 0
        if "." in str(ip_str):
            whole, frac = str(ip_str).split(".", 1)
            ip = int(whole) + int(frac) / 3
        else:
            ip = float(ip_str)
        result["era"] = float(era) if era != "—" else 0
        result["ip_per_gs"] = round(ip / gs, 1) if gs > 0 else 0
        result["ip"] = ip_str

    return result


def build_prior_stats_rp(mlb_id):
    """Build prior_stats dict for an RP using 2025 data."""
    savant = fetch_savant_player(mlb_id, 2025, "pitcher")
    mlb_stats = fetch_mlb_season_stats(mlb_id, 2025, "pitching")

    if not savant and not mlb_stats:
        return None

    result = {"season": 2025}

    if savant:
        result["xera"] = round(savant.get("xera", 0), 2)
        result["xwoba_allowed"] = round(savant.get("xwoba", 0), 3)
        result["hh_pct_allowed"] = round(savant.get("hh_pct", 0), 1)
        result["barrel_pct_allowed"] = round(savant.get("barrel_pct", 0), 1)
        result["bbe"] = savant.get("bbe", 0)

    if mlb_stats:
        era = mlb_stats.get("era", "0")
        ip_str = mlb_stats.get("inningsPitched", "0")
        k = int(mlb_stats.get("strikeOuts", 0))
        # Parse IP
        ip = 0
        if "." in str(ip_str):
            whole, frac = str(ip_str).split(".", 1)
            ip = int(whole) + int(frac) / 3
        else:
            ip = float(ip_str)
        result["era"] = float(era) if era != "—" else 0
        result["k_per_9"] = round(k * 9 / ip, 2) if ip > 0 else 0
        result["ip_per_team_g"] = round(ip / FULL_SEASON_GAMES, 2)
        result["ip"] = ip_str

    return result
```

- [ ] **Step 4: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): prior_stats from Savant CSV + MLB Stats API"
```

---

## Task 7: Config update + save

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add update_config()**

```python
def enrich_new_player(player):
    """For a new player from Yahoo roster, look up mlb_id and prior_stats."""
    name = player["name"]
    positions = player["positions"]

    print(f"  Enriching {name}...", file=sys.stderr)

    mlb_id = search_mlb_id(name)
    entry = {
        "name": name,
        "mlb_id": mlb_id,
        "yahoo_player_key": player["yahoo_player_key"],
        "team": player["team"],
        "positions": positions,
    }

    if mlb_id:
        p_type = pitcher_type(entry)
        if p_type == "SP":
            entry["prior_stats"] = build_prior_stats_sp(mlb_id)
        elif p_type == "RP":
            entry["prior_stats"] = build_prior_stats_rp(mlb_id)
        else:
            entry["prior_stats"] = build_prior_stats_batter(mlb_id)
    else:
        entry["prior_stats"] = None

    return entry


def update_config(config, yahoo_roster, diff):
    """Apply diff to config: remove dropped, add new players.

    Also updates yahoo_player_key, team, and positions for existing players.
    """
    added = diff["added"]
    dropped = diff["dropped"]

    # Remove dropped players
    dropped_keys = {p.get("yahoo_player_key") or p["name"] for p in dropped}
    for section in ("batters", "pitchers"):
        config[section] = [
            p for p in config[section]
            if (p.get("yahoo_player_key") or p["name"]) not in dropped_keys
        ]

    # Add new players
    for player in added:
        entry = enrich_new_player(player)
        if is_pitcher(entry):
            config["pitchers"].append(entry)
        else:
            config["batters"].append(entry)

    # Update yahoo_player_key, team, positions for existing players (--init bootstrap)
    yahoo_by_name = {p["name"]: p for p in yahoo_roster}
    for section in ("batters", "pitchers"):
        for p in config[section]:
            yp = yahoo_by_name.get(p["name"])
            if yp:
                if not p.get("yahoo_player_key"):
                    p["yahoo_player_key"] = yp["yahoo_player_key"]
                p["team"] = yp["team"]
                p["positions"] = yp["positions"]

    return config
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): config update logic with player enrichment"
```

---

## Task 8: Git push + Telegram notification

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add git_commit_and_push() and send_telegram()**

```python
def git_commit_and_push(added_names, dropped_names):
    """Git add roster_config.json, commit, pull --rebase, push."""
    parts = []
    for name in added_names:
        parts.append(f"+{name}")
    for name in dropped_names:
        parts.append(f"-{name}")
    msg = f"roster: {', '.join(parts)}"

    try:
        subprocess.run(
            ["git", "add", "daily-advisor/roster_config.json"],
            cwd=REPO_ROOT, check=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=REPO_ROOT, check=True, timeout=10,
        )
    except subprocess.CalledProcessError as e:
        print(f"Git commit failed: {e}", file=sys.stderr)
        return False

    try:
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "master"],
            cwd=REPO_ROOT, check=True, timeout=30,
        )
    except subprocess.CalledProcessError as e:
        print(f"Git pull --rebase failed (skip push): {e}", file=sys.stderr)
        return False

    try:
        subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=REPO_ROOT, check=True, timeout=30,
        )
        print("Git push succeeded", file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git push failed (resolve manually): {e}", file=sys.stderr)
        return False


def send_notification(added_names, dropped_names, env, dry_run=False):
    """Send Telegram notification about roster changes."""
    lines = ["[Roster Sync]"]
    for name in added_names:
        lines.append(f"  + {name}")
    for name in dropped_names:
        lines.append(f"  - {name}")
    message = "\n".join(lines)

    if dry_run:
        print(f"\n[DRY RUN] Would send:\n{message}", file=sys.stderr)
        return

    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing", file=sys.stderr)
        return

    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("Telegram notification sent", file=sys.stderr)
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): git commit/push + Telegram notification"
```

---

## Task 9: Wire --init mode

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add run_init()**

```python
def run_init(my_key, token, config, dry_run):
    """Full bootstrap: pull roster, diff, enrich new players, update config."""
    print("Running --init: full roster sync...", file=sys.stderr)

    roster = fetch_full_roster(my_key, token)
    print(f"Yahoo roster: {len(roster)} players", file=sys.stderr)

    diff = diff_roster(roster, config)
    added = diff["added"]
    dropped = diff["dropped"]

    # For --init, also count players that exist but need yahoo_player_key
    needs_key = 0
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            if not p.get("yahoo_player_key"):
                needs_key += 1

    print(f"Diff: +{len(added)} added, -{len(dropped)} dropped, {needs_key} need yahoo_player_key", file=sys.stderr)

    if not added and not dropped and needs_key == 0:
        print("No changes needed.", file=sys.stderr)
        return

    if dry_run:
        for p in added:
            print(f"  + {p['name']} ({p['team']}, {','.join(p['positions'])})", file=sys.stderr)
        for p in dropped:
            print(f"  - {p['name']}", file=sys.stderr)
        if needs_key:
            print(f"  {needs_key} players will get yahoo_player_key backfilled", file=sys.stderr)
        print("[DRY RUN] No changes written.", file=sys.stderr)
        return

    config = update_config(config, roster, diff)
    save_config(config)
    write_last_sync(int(time.time()))
    print("Config updated and saved.", file=sys.stderr)
```

- [ ] **Step 2: Verify --init --dry-run on VPS**

Push to remote, pull on VPS, run:

```bash
ssh root@107.175.30.172 "export $(cat /etc/calorie-bot/op-token.env) && export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin && cd /opt/mlb-fantasy && git pull && python3 daily-advisor/roster_sync.py --init --dry-run"
```

Expected: Shows current roster, reports how many need yahoo_player_key backfill, no files changed.

- [ ] **Step 3: Run --init for real (on VPS)**

```bash
ssh root@107.175.30.172 "export $(cat /etc/calorie-bot/op-token.env) && export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin && cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py --init"
```

Expected: Config updated with yahoo_player_key + prior_stats for all players. Verify output JSON is valid.

- [ ] **Step 4: Pull updated config to dev machine, review, commit**

```bash
git pull  # get the config changes from VPS --init run
# Review roster_config.json diff — should see yahoo_player_key + prior_stats added
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): wire --init mode"
```

---

## Task 10: Wire daily mode

**Files:**
- Modify: `daily-advisor/roster_sync.py`

- [ ] **Step 1: Add run_daily()**

```python
def run_daily(league_key, my_key, token, config, env, dry_run):
    """Daily mode: check transactions, sync if changes detected."""
    last_sync = read_last_sync()
    print(f"Last sync: {last_sync} ({time.strftime('%Y-%m-%d %H:%M', time.localtime(last_sync)) if last_sync else 'never'})", file=sys.stderr)

    transactions = fetch_transactions(league_key, my_key, token)
    if not has_new_transactions(transactions, last_sync):
        print("No new transactions. Done.", file=sys.stderr)
        return

    new_txns = [t for t in transactions if t["timestamp"] > last_sync]
    print(f"Found {len(new_txns)} new transaction(s):", file=sys.stderr)
    for tx in new_txns:
        names = ", ".join(f"{p['action']}:{p['name']}" for p in tx["players"])
        print(f"  {tx['type']}: {names}", file=sys.stderr)

    # Fetch full roster and diff
    roster = fetch_full_roster(my_key, token)
    diff = diff_roster(roster, config)
    added = diff["added"]
    dropped = diff["dropped"]

    if not added and not dropped:
        print("Transactions detected but roster unchanged (e.g. pending waiver). Done.", file=sys.stderr)
        write_last_sync(int(time.time()))
        return

    added_names = [p["name"] for p in added]
    dropped_names = [p["name"] for p in dropped]
    print(f"Roster changes: +{added_names} -{dropped_names}", file=sys.stderr)

    if dry_run:
        for p in added:
            print(f"  + {p['name']} ({p['team']}, {','.join(p['positions'])})", file=sys.stderr)
        for p in dropped:
            print(f"  - {p['name']}", file=sys.stderr)
        print("[DRY RUN] No changes written.", file=sys.stderr)
        return

    config = update_config(config, roster, diff)
    save_config(config)
    write_last_sync(int(time.time()))
    print("Config updated.", file=sys.stderr)

    git_commit_and_push(added_names, dropped_names)
    send_notification(added_names, dropped_names, env)
```

- [ ] **Step 2: Commit**

```bash
git add daily-advisor/roster_sync.py
git commit -m "feat(roster-sync): wire daily mode with transactions gate"
```

- [ ] **Step 3: Test daily mode (dry-run) on VPS**

```bash
ssh root@107.175.30.172 "export $(cat /etc/calorie-bot/op-token.env) && export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin && cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py --dry-run"
```

Expected: If no new transactions since --init, shows "No new transactions. Done." If there are, shows the diff without writing.

---

## Task 11: Deploy — cron + VPS sync

**Files:**
- Modify: `/etc/cron.d/daily-advisor` (on VPS)

- [ ] **Step 1: Push all code to remote**

```bash
git push origin feat/roster-sync
# or if working on master:
git push origin master
```

- [ ] **Step 2: Pull on VPS and add cron entry**

```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy && git pull"
```

Add to `/etc/cron.d/daily-advisor`:
```
# Roster Sync — TW 15:10 = UTC 07:10
10 7 * * * root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py >> /var/log/roster-sync.log 2>&1"
```

- [ ] **Step 3: Verify cron syntax and log path**

```bash
ssh root@107.175.30.172 "touch /var/log/roster-sync.log && cat /etc/cron.d/daily-advisor"
```

- [ ] **Step 4: Final commit with updated memory/docs**

Update `daily-advisor/yahoo-api-reference.md` to mark `/transactions` as "used":
```
| `GET /league/{key}/transactions;team_key={my_key}` | Check for roster changes | `roster_sync.py` |
```

Commit:
```bash
git add daily-advisor/yahoo-api-reference.md
git commit -m "docs: mark transactions endpoint as used in API reference"
```
