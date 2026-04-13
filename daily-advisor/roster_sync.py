"""Roster sync — auto-update roster_config.json from Yahoo Fantasy API."""

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "roster_config.json")
LAST_SYNC_PATH = os.path.join(SCRIPT_DIR, ".last_sync")
MLB_API = "https://statsapi.mlb.com/api/v1"

sys.path.insert(0, SCRIPT_DIR)
from yahoo_query import load_env, refresh_token, api_get as yahoo_api_get, is_pitcher, pitcher_type, send_telegram  # noqa: E402


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


def fetch_full_roster(team_key, token, date=None):
    """Fetch roster from Yahoo API, return list of player dicts.

    Yahoo's default /team/{key}/roster endpoint returns a stale snapshot
    (often the previous day's lineup), which causes us to miss new adds.
    Always pass an explicit date so we get the active roster for that day.
    Defaults to today in ET when not specified.

    Each dict: {name, yahoo_player_key, team, positions, selected_pos, status}
    """
    if date is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    data = yahoo_api_get(f"/team/{team_key}/roster;date={date}", token)
    players_data = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    players = []
    for k, v in players_data.items():
        if k == "count":
            continue
        player = v["player"]
        info = player[0]
        pos_data = player[1]

        name = team_val = display_pos = player_key = status = None
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
                if "status" in item:
                    status = item["status"]

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
            "status": status or "",
        })

    return players


# ── Task 3: Transactions gate ──


def fetch_transactions(league_key, my_key, token):
    """Fetch our team's transactions from Yahoo API.

    Returns list of {timestamp, type, players: [{name, action}]}, newest first.
    """
    data = yahoo_api_get(f"/league/{league_key}/transactions;team_key={my_key}", token)
    content = data["fantasy_content"]["league"][1]

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
    return any(tx["timestamp"] > last_sync_ts for tx in transactions)


# ── Task 4: Diff logic ──


def diff_roster(yahoo_roster, config, init=False):
    """Compare Yahoo roster vs config.

    init=True: name matching (config may not have yahoo_player_key yet).
    init=False: yahoo_player_key matching (normal daily mode).
    """
    if init:
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

    yahoo_keys = {p["yahoo_player_key"] for p in yahoo_roster}
    config_keys = set()
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            k = p.get("yahoo_player_key")
            if k:
                config_keys.add(k)

    added_keys = yahoo_keys - config_keys
    dropped_keys = config_keys - yahoo_keys
    added = [p for p in yahoo_roster if p["yahoo_player_key"] in added_keys]
    dropped = []
    for section in ("batters", "pitchers"):
        for p in config.get(section, []):
            if p.get("yahoo_player_key") in dropped_keys:
                dropped.append(p)

    return {"added": added, "dropped": dropped}


# ── Task 5: MLB API mlb_id search ──


def search_mlb_id(name):
    """Search MLB API for player's mlb_id by name.

    Handles Jr./Sr. suffixes and accent characters.
    Returns int mlb_id or None.
    """
    def normalize(s):
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

    result = try_search(name)
    if result:
        return result

    stripped = re.sub(r'\s+(Jr\.|Sr\.|II|III|IV)$', '', name).strip()
    if stripped != name:
        result = try_search(stripped)
        if result:
            return result

    normalized = normalize(name)
    if normalized != name:
        result = try_search(normalized)
        if result:
            return result

    print(f"  WARNING: Could not find mlb_id for '{name}'", file=sys.stderr)
    return None


# ── Task 6: Savant CSV + MLB Stats API ──

# 2025 full season = 162 games for all teams.
# Approximation: ignores mid-season trades. Accurate enough for baseline metrics.
FULL_SEASON_GAMES = 162


def _download_savant_csv(leaderboard, player_type, year):
    """Download a Savant CSV and return list of row dicts."""
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/{leaderboard}"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    text = resp.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _find_id_column(row):
    """Detect the player ID column name in a Savant CSV row."""
    for col in ("player_id", "mlbam_id"):
        if col in row:
            return col
    return None


def _extract_savant_row(row, player_type):
    """Extract relevant fields from a Savant CSV row."""
    result = {}
    if "est_woba" in row:
        result["xwoba"] = float(row.get("est_woba", 0) or 0)
        result["pa"] = int(row.get("pa", 0) or 0)
        if player_type == "pitcher":
            xera = row.get("xera")
            result["xera"] = float(xera) if xera else 0
    if "ev95percent" in row:
        result["hh_pct"] = float(row.get("ev95percent", 0) or 0)
        result["barrel_pct"] = float(row.get("brl_percent", 0) or 0)
        result["bbe"] = int(row.get("attempts", 0) or 0)
    return result


def fetch_savant_batch(mlb_ids, year, player_type="batter"):
    """Fetch Savant data for multiple players. Downloads each CSV once.

    Returns dict: mlb_id -> {xwoba, hh_pct, barrel_pct, bbe, pa, [xera]}
    """
    id_set = {str(mid) for mid in mlb_ids if mid}
    result = {mid: {} for mid in mlb_ids if mid}

    for leaderboard in ("statcast", "expected_statistics"):
        try:
            rows = _download_savant_csv(leaderboard, player_type, year)
            if not rows:
                continue
            id_col = _find_id_column(rows[0])
            if not id_col:
                print(f"  WARNING: No ID column in {leaderboard} CSV", file=sys.stderr)
                continue
            for row in rows:
                pid = row.get(id_col, "").strip()
                if pid in id_set:
                    extracted = _extract_savant_row(row, player_type)
                    result[int(pid)].update(extracted)
        except Exception as e:
            print(f"  Savant {leaderboard} batch failed ({year}): {e}", file=sys.stderr)

    return result


def fetch_savant_player(mlb_id, year, player_type="batter"):
    """Fetch Savant data for a single player (daily mode)."""
    data = fetch_savant_batch([mlb_id], year, player_type)
    return data.get(mlb_id) or None


def fetch_mlb_season_stats(mlb_id, season, group="hitting"):
    """Fetch season stats from MLB Stats API. Returns raw stat dict or None."""
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
        print(f"  MLB stats failed ({mlb_id}, {season}): {e}", file=sys.stderr)
        return None


def _parse_ip(ip_str):
    """Convert baseball IP notation (6.1 = 6 1/3) to float."""
    s = str(ip_str)
    if "." in s:
        whole, frac = s.split(".", 1)
        return int(whole) + int(frac) / 3
    return float(s) if s else 0


def build_prior_stats_batter(mlb_id, savant=None):
    """Build prior_stats dict for a batter using 2025 data."""
    if savant is None:
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


def _ip_per_gs_from_gamelog(mlb_id, season):
    """Calculate IP/GS using only games where gamesStarted=1 (game log based).

    Returns float or None if no starts found or API error.
    """
    try:
        stats = mlb_api_get(
            f"/people/{mlb_id}/stats?stats=gameLog&season={season}&group=pitching"
        )
        splits = stats.get("stats", [{}])[0].get("splits", [])
        starts = [s for s in splits if int(s["stat"].get("gamesStarted", 0)) == 1]
        if not starts:
            return None
        total_ip = sum(_parse_ip(s["stat"].get("inningsPitched", "0")) for s in starts)
        return round(total_ip / len(starts), 1)
    except Exception:
        return None


def build_prior_stats_sp(mlb_id, savant=None):
    """Build prior_stats dict for an SP using 2025 data."""
    if savant is None:
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
        ip = _parse_ip(mlb_stats.get("inningsPitched", "0"))
        result["era"] = float(era) if era != "—" else 0
        result["ip"] = round(ip, 1)
        # IP/GS from game log: only count IP in games where gamesStarted=1
        ip_per_gs = _ip_per_gs_from_gamelog(mlb_id, 2025)
        if ip_per_gs is not None:
            result["ip_per_gs"] = ip_per_gs
        else:
            gs = int(mlb_stats.get("gamesStarted", 0))
            result["ip_per_gs"] = round(ip / gs, 1) if gs > 0 else 0
    return result


def build_prior_stats_rp(mlb_id, savant=None):
    """Build prior_stats dict for an RP using 2025 data."""
    if savant is None:
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
        ip = _parse_ip(mlb_stats.get("inningsPitched", "0"))
        k = int(mlb_stats.get("strikeOuts", 0))
        result["era"] = float(era) if era != "—" else 0
        result["k_per_9"] = round(k * 9 / ip, 2) if ip > 0 else 0
        result["ip_per_team_g"] = round(ip / FULL_SEASON_GAMES, 2)
        result["ip"] = round(ip, 1)
    return result


# ── Task 7: Config update ──


def enrich_new_player(player, savant_data=None):
    """Look up mlb_id and prior_stats for a new player."""
    name = player["name"]
    print(f"  Enriching {name}...", file=sys.stderr)

    mlb_id = search_mlb_id(name)
    entry = {
        "name": name,
        "mlb_id": mlb_id,
        "yahoo_player_key": player["yahoo_player_key"],
        "team": player["team"],
        "positions": player["positions"],
        "selected_pos": player.get("selected_pos", ""),
        "status": player.get("status", ""),
    }

    if mlb_id:
        savant = savant_data.get(mlb_id) if savant_data else None
        p_type = pitcher_type(entry)
        if p_type == "SP":
            entry["prior_stats"] = build_prior_stats_sp(mlb_id, savant)
        elif p_type == "RP":
            entry["prior_stats"] = build_prior_stats_rp(mlb_id, savant)
        else:
            entry["prior_stats"] = build_prior_stats_batter(mlb_id, savant)
    else:
        entry["prior_stats"] = None

    return entry


def update_config(config, yahoo_roster, diff, savant_data=None):
    """Apply diff to config: remove dropped, add new players.

    Also backfills yahoo_player_key, team, positions for existing players.
    """
    added = diff["added"]
    dropped = diff["dropped"]

    dropped_keys = {p.get("yahoo_player_key") or p["name"] for p in dropped}
    for section in ("batters", "pitchers"):
        config[section] = [
            p for p in config[section]
            if (p.get("yahoo_player_key") or p["name"]) not in dropped_keys
        ]

    for player in added:
        entry = enrich_new_player(player, savant_data=savant_data)
        if is_pitcher(entry):
            config["pitchers"].append(entry)
        else:
            config["batters"].append(entry)

    # Backfill yahoo_player_key, team, positions, prior_stats for existing players
    yahoo_by_name = {p["name"]: p for p in yahoo_roster}
    for section in ("batters", "pitchers"):
        for p in config[section]:
            yp = yahoo_by_name.get(p["name"])
            if yp:
                if not p.get("yahoo_player_key"):
                    p["yahoo_player_key"] = yp["yahoo_player_key"]
                p["team"] = yp["team"]
                p["positions"] = yp["positions"]
                p["selected_pos"] = yp.get("selected_pos", "")
                p["status"] = yp.get("status", "")
            # Backfill prior_stats if missing and mlb_id available
            if not p.get("prior_stats") and p.get("mlb_id"):
                savant = savant_data.get(p["mlb_id"]) if savant_data else None
                p_type = pitcher_type(p)
                if p_type == "SP":
                    p["prior_stats"] = build_prior_stats_sp(p["mlb_id"], savant)
                elif p_type == "RP":
                    p["prior_stats"] = build_prior_stats_rp(p["mlb_id"], savant)
                else:
                    p["prior_stats"] = build_prior_stats_batter(p["mlb_id"], savant)

    return config


# ── Task 8: Git + Telegram ──


def sync_repo_before_edit(env=None):
    """Pull --rebase origin master before editing roster_config.json.

    Mirrors fa_scan._sync_waiver_log_before_edit. Called at the start of
    main() so we read a fresh roster_config.json and the subsequent
    commit is a clean fast-forward — no post-commit rebase race.
    Returns True on success; False if pull fails (caller should abort).
    """
    try:
        subprocess.run(["git", "pull", "--rebase", "origin", "master"],
                       cwd=REPO_ROOT, check=True, timeout=30)
        return True
    except subprocess.CalledProcessError:
        subprocess.run(["git", "rebase", "--abort"], cwd=REPO_ROOT,
                       capture_output=True, timeout=10)
        msg = ("[roster_sync] pre-edit pull --rebase failed — "
               "skipping sync. Needs manual fix.")
        print(msg, file=sys.stderr)
        if env:
            send_telegram(msg, env)
        return False


def git_commit_and_push(added_names, dropped_names, env=None):
    """Git add, commit, and push roster_config.json.

    No rebase here — sync_repo_before_edit() runs at main() start so
    the working copy is already on top of origin/master.
    """
    parts = [f"+{n}" for n in added_names] + [f"-{n}" for n in dropped_names]
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
            ["git", "push", "origin", "master"],
            cwd=REPO_ROOT, check=True, timeout=30,
        )
        print("Git push succeeded", file=sys.stderr)
        return True
    except subprocess.CalledProcessError:
        alert = "[roster_sync] git push failed — resolve manually."
        print(alert, file=sys.stderr)
        if env:
            send_telegram(alert, env)
        return False


def send_notification(added_names, dropped_names, env, dry_run=False):
    """Send Telegram notification about roster changes."""
    lines = ["\\[Roster Sync]"]
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


# ── Task 9-10: run_init + run_daily ──


def run_init(my_key, token, config, dry_run):
    """Full bootstrap: pull roster, diff, enrich new players, update config."""
    print("Running --init: full roster sync...", file=sys.stderr)

    roster = fetch_full_roster(my_key, token)
    print(f"Yahoo roster: {len(roster)} players", file=sys.stderr)

    diff = diff_roster(roster, config, init=True)
    added = diff["added"]
    dropped = diff["dropped"]

    needs_key = sum(
        1 for section in ("batters", "pitchers")
        for p in config.get(section, [])
        if not p.get("yahoo_player_key")
    )
    needs_stats = sum(
        1 for section in ("batters", "pitchers")
        for p in config.get(section, [])
        if not p.get("prior_stats") and p.get("mlb_id")
    )

    print(f"Diff: +{len(added)} added, -{len(dropped)} dropped, {needs_key} need key, {needs_stats} need prior_stats", file=sys.stderr)

    if not added and not dropped and needs_key == 0 and needs_stats == 0:
        print("No changes needed.", file=sys.stderr)
        return

    if dry_run:
        for p in added:
            print(f"  + {p['name']} ({p['team']}, {','.join(p['positions'])})", file=sys.stderr)
        for p in dropped:
            print(f"  - {p['name']}", file=sys.stderr)
        if needs_key:
            print(f"  {needs_key} players will get yahoo_player_key backfilled", file=sys.stderr)
        if needs_stats:
            print(f"  {needs_stats} players will get prior_stats backfilled", file=sys.stderr)
        print("[DRY RUN] No changes written.", file=sys.stderr)
        return

    # Batch-fetch 2025 Savant data (4 CSV downloads total)
    all_ids = [p.get("mlb_id") for section in ("batters", "pitchers")
               for p in config.get(section, []) if p.get("mlb_id")]
    for p in added:
        mid = search_mlb_id(p["name"])
        if mid:
            all_ids.append(mid)

    print("Batch-fetching 2025 Savant data...", file=sys.stderr)
    savant_data = {}
    for ptype in ("batter", "pitcher"):
        batch = fetch_savant_batch(all_ids, 2025, ptype)
        for mid, data in batch.items():
            if data:  # Only merge non-empty results
                savant_data.setdefault(mid, {}).update(data)

    config = update_config(config, roster, diff, savant_data=savant_data)
    save_config(config)
    write_last_sync(int(time.time()))
    print("Config updated and saved.", file=sys.stderr)


def run_daily(league_key, my_key, token, config, env, dry_run):
    """Daily mode: check transactions, sync if changes detected."""
    last_sync = read_last_sync()
    ts_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(last_sync)) if last_sync else 'never'
    print(f"Last sync: {last_sync} ({ts_str})", file=sys.stderr)

    transactions = fetch_transactions(league_key, my_key, token)
    if not has_new_transactions(transactions, last_sync):
        print("No new transactions. Done.", file=sys.stderr)
        return

    new_txns = [t for t in transactions if t["timestamp"] > last_sync]
    print(f"Found {len(new_txns)} new transaction(s):", file=sys.stderr)
    for tx in new_txns:
        names = ", ".join(f"{p['action']}:{p['name']}" for p in tx["players"])
        print(f"  {tx['type']}: {names}", file=sys.stderr)

    roster = fetch_full_roster(my_key, token)
    diff = diff_roster(roster, config)
    added = diff["added"]
    dropped = diff["dropped"]

    if not added and not dropped:
        # Transactions detected but roster unchanged (e.g. pending waiver).
        # Update last_sync so we don't re-check these transactions.
        print("Transactions detected but roster unchanged. Done.", file=sys.stderr)
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

    git_commit_and_push(added_names, dropped_names, env=env)
    send_notification(added_names, dropped_names, env)


def main():
    parser = argparse.ArgumentParser(description="Sync Yahoo roster to roster_config.json")
    parser.add_argument("--init", action="store_true", help="Full bootstrap: pull entire roster and build config")
    parser.add_argument("--dry-run", action="store_true", help="Print diff without writing config or pushing")
    args = parser.parse_args()

    env = load_env()

    # Pre-edit sync: pull latest from origin so we read fresh state
    # and the post-edit commit is a clean fast-forward.
    if not args.dry_run and not sync_repo_before_edit(env):
        sys.exit(1)

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
