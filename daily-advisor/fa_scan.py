"""FA Scan — unified FA market analysis with two-pass Claude architecture.

Modes:
    python fa_scan.py                   # Daily: Batter + SP scan (default)
    python fa_scan.py --rp              # Weekly: RP scan (Monday only)
    python fa_scan.py --snapshot-only   # Daily: %owned snapshot only
    python fa_scan.py --cleanup         # Manual: clean rostered watchlist players

Cron: 每天 TW 12:30 (UTC 04:30)。--rp 僅週一。--snapshot-only 每天 TW 15:15。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import (
    refresh_token, load_env, load_config, api_get,
    YAHOO_STAT_MAP, extract_player_info, parse_player_stats,
    send_telegram, _normalize, _search_players,
    pitcher_type, calc_position_depth, is_active,
)

TPE = ZoneInfo("Asia/Taipei")

from daily_advisor import pctile_tag, BATTER_PCTILES
from savant_rolling import fetch_savant_rolling
from roster_sync import (
    _download_savant_csv, _find_id_column, _extract_savant_row,
    search_mlb_id, fetch_mlb_season_stats, mlb_api_get, _parse_ip,
)
import fa_compute

SUMMARY_FILE = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")
FULL_SEASON_GAMES = 162

# Guards concurrent waiver-log git operations when batter + SP run in parallel.
_WAIVER_LOG_LOCK = threading.Lock()


# ── FA snapshot + %owned history (absorbed from fa_watch.py) ──


FA_HISTORY_FILE = os.path.join(SCRIPT_DIR, "fa_history.json")


def collect_fa_snapshot(access_token, config, queries=None):
    """Query FA players across positions. Returns {name: {team, position, pct, stats}}.

    Args:
        queries: list of (label, filter_str) tuples. Defaults to SCAN_QUERIES.
    """
    if queries is None:
        queries = SCAN_QUERIES
    league_key = config["league"]["league_key"]
    snapshot = {}

    for entry in queries:
        label, filters = entry[0], entry[1]
        stats_type = entry[2] if len(entry) > 2 else None
        if stats_type:
            path = f"/league/{league_key}/players;{filters};out=percent_owned,ownership/stats;type={stats_type}"
        else:
            path = f"/league/{league_key}/players;{filters};out=stats,percent_owned,ownership"
        try:
            data = api_get(path, access_token)
            league_data = data["fantasy_content"]["league"]
            if len(league_data) < 2 or "players" not in league_data[1]:
                continue
            players_data = league_data[1]["players"]
            for k, v in players_data.items():
                if k == "count":
                    continue
                p = extract_player_info(v["player"])
                stats = parse_player_stats(v["player"])
                name = p["name"]
                if name not in snapshot:
                    snapshot[name] = {
                        "team": p["team"],
                        "position": p["position"],
                        "pct": int(float(p["percent_owned"] or 0)),
                        "stats": stats,
                        "waiver_date": p.get("waiver_date", ""),
                    }
        except Exception as e:
            print(f"FA query error ({label}): {e}", file=sys.stderr)
        time.sleep(1)

    return snapshot


def load_fa_history():
    if os.path.exists(FA_HISTORY_FILE):
        with open(FA_HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_fa_history(history):
    with open(FA_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def calc_owned_changes(today_snapshot, history, today_str):
    """Calculate %owned changes for 24h and 3d windows.

    Returns (changes_list, ref_1d_date, ref_3d_date).
    """
    dates = sorted(history.keys())

    ref_1d = None
    ref_3d = None
    for d in reversed(dates):
        if d < today_str:
            if ref_1d is None:
                ref_1d = d
            days_diff = (
                datetime.strptime(today_str, "%Y-%m-%d")
                - datetime.strptime(d, "%Y-%m-%d")
            ).days
            if days_diff >= 3 and ref_3d is None:
                ref_3d = d
                break

    snap_1d = history.get(ref_1d, {}) if ref_1d else {}
    snap_3d = history.get(ref_3d, {}) if ref_3d else {}

    changes = []
    for name, info in today_snapshot.items():
        pct = info["pct"]
        d1 = pct - snap_1d.get(name, {}).get("pct", pct) if snap_1d else None
        d3 = pct - snap_3d.get(name, {}).get("pct", pct) if snap_3d else None
        changes.append({
            "name": name, "team": info["team"],
            "position": info["position"], "pct": pct,
            "d1": d1, "d3": d3,
            "stats": info.get("stats", {}),
            "waiver_date": info.get("waiver_date", ""),
        })

    return changes, ref_1d, ref_3d


def collect_owned_risers(history, today_str, position_filter=None, top_n=20, days=3):
    """Get top %owned risers from fa_history over N days.

    Args:
        position_filter: 'batter', 'sp', 'rp', or None (all)
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


def format_change_rankings(changes, ref_1d, ref_3d, top_n=5):
    """Format top %owned risers with reference date info."""
    lines = []

    if ref_1d:
        header = f"24h (vs {ref_1d})"
    else:
        return "（需累積至少 2 天數據才有變動排行）"
    if ref_3d:
        header += f" | 3d (vs {ref_3d})"
    else:
        header += " | 3d (需累積 3 天以上)"
    lines.append(header)

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

    return "\n".join(lines)


# ── Waiver-log parsing ──

_WAIVER_PLAYER_RE = re.compile(
    r"### (.+?) \((\w{2,3}),\s*(.+?)(?:\)\s*\[mlb_id:(\d+)\]|\))"
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
                row = name_idx[name_norm]
                id_col = _find_id_column(row)
                if id_col and row.get(id_col, "").strip():
                    w["mlb_id"] = int(row[id_col])
                break
        if not w.get("mlb_id"):
            # Fallback: MLB API search
            w["mlb_id"] = search_mlb_id(w["name"])
    return [w for w in watchlist if w.get("mlb_id")]


# Module-level cache for Savant CSVs to avoid duplicate downloads
_savant_csv_cache = {}


def enrich_watch_players(watchlist, savant_2026, config):
    """Enrich waiver-log watch players — skip Layer 1-2, direct to Layer 3.

    Returns list in same format as enrich_layer3 output.
    """
    if not watchlist:
        return []

    standings = _fetch_team_games()
    enriched = []

    savant_2025_csvs = download_savant_csvs(2025)  # cached by download_savant_csvs

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

        # 2025 prior (cached)
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

        # Top-level bbe for _format_fa_batter/_format_fa_pitcher
        p["bbe"] = s26.get("bbe", 0) if s26 else 0

        enriched.append(p)
        time.sleep(0.2)

    return enriched


# ── Waiver-log auto-cleanup ──


def _check_player_ownership(name, league_key, access_token, expected_team=None):
    """Check if a player is FA or rostered via Yahoo API.

    When expected_team is provided, cross-verify against Yahoo's
    editorial_team_abbr to disambiguate same-name players (e.g. Max Muncy
    LAD 571970 vs ATH 691777 — without team verification the name search
    picks the first match and can wrongly report ATH Muncy as rostered
    because LAD Muncy is rostered by someone). See CLAUDE.md TODO
    'waiver-log auto-close mlb_id 驗證'.

    Returns ownership_type: 'freeagents', 'waivers', 'team', or None on
    error / no matching player.
    """
    players_data = _search_players(name, league_key, access_token)
    if not players_data:
        return None
    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        # Cross-verify team to avoid same-name false matches
        if expected_team and p.get("team") and p["team"].upper() != expected_team.upper():
            continue
        player_key = p.get("player_key")
        if not player_key:
            continue
        od = api_get(
            f"/league/{league_key}/players;player_keys={player_key}"
            f";out=ownership",
            access_token,
        )
        p2 = extract_player_info(
            od["fantasy_content"]["league"][1]["players"]["0"]["player"])
        return p2.get("ownership_type", "")
    # No matching player (name + team) found — treat as unknown, not FA
    return None


def _sync_waiver_log_before_edit(repo_root, env=None):
    """Pull --rebase origin master before editing waiver-log.md.

    Called at the start of any function that edits waiver-log.md, so the
    working copy is already up-to-date before we read and write. This
    prevents the post-commit rebase conflicts that previously occurred
    when local edits (e.g. manual pushes) diverged from VPS cron state.
    Returns True on success; False if pull fails (caller should skip).
    """
    try:
        subprocess.run(["git", "pull", "--rebase", "origin", "master"],
                       cwd=repo_root, check=True, timeout=30)
        return True
    except subprocess.CalledProcessError:
        subprocess.run(["git", "rebase", "--abort"], cwd=repo_root,
                       capture_output=True, timeout=10)
        msg = ("[fa_scan] pre-edit pull --rebase failed — "
               "skipping waiver-log update. Needs manual fix.")
        print(f"  {msg}", file=sys.stderr)
        if env:
            send_telegram(msg, env)
        return False


def cleanup_rostered_watchlist(access_token, config, today_str, env=None):
    """Check watchlist players' FA status, auto-move rostered ones to 已結案.

    Runs during --snapshot-only (TW 15:15). Modifies waiver-log.md + git commit.
    Only checks active watchlist (not 條件 Pass — those track "被 drop 回 FA").
    """
    repo_root = os.path.join(SCRIPT_DIR, "..")
    if not _sync_waiver_log_before_edit(repo_root, env):
        return

    watchlist = parse_waiver_log_watchlist()
    if not watchlist:
        return

    league_key = config["league"]["league_key"]
    rostered = []
    for w in watchlist:
        try:
            ownership = _check_player_ownership(
                w["name"], league_key, access_token,
                expected_team=w.get("team"))
            if ownership == "team":
                rostered.append(w)
                print(f"  Rostered: {w['name']} ({w.get('team','?')})", file=sys.stderr)
            time.sleep(0.5)
        except Exception as e:
            print(f"  Ownership check failed for {w['name']}: {e}",
                  file=sys.stderr)

    if not rostered:
        print("  Watchlist cleanup: all still FA", file=sys.stderr)
        return

    # Modify waiver-log.md: move rostered players from 觀察中 → 已結案
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    with open(waiver_log_path, encoding="utf-8") as f:
        content = f.read()

    closed_entries = []
    for player in rostered:
        name = re.escape(player["name"])
        pattern = re.compile(
            rf"### {name} \([^)]+\)[^\n]*\n(?:(?!### |## ).*\n)*",
            re.MULTILINE,
        )
        match = pattern.search(content)
        if match:
            content = content[:match.start()] + content[match.end():]
            closed_entries.append(
                f"### {player['name']} ({player['team']}, {player['position']})"
                f" — 被搶（自動偵測）\n"
                f"- {today_str}：Yahoo ownership_type=team，從觀察中移除。\n"
            )

    if not closed_entries:
        return

    closed_marker = "## 已結案\n"
    if closed_marker in content:
        pos = content.index(closed_marker) + len(closed_marker)
        insert = "\n" + "\n".join(closed_entries)
        content = content[:pos] + insert + content[pos:]

    content = re.sub(r"\n{3,}", "\n\n", content)

    with open(waiver_log_path, "w", encoding="utf-8") as f:
        f.write(content)

    names = ", ".join(p["name"] for p in rostered)
    print(f"  Watchlist cleanup: moved {len(rostered)} to 已結案 ({names})",
          file=sys.stderr)

    try:
        subprocess.run(
            ["git", "add", "waiver-log.md"],
            cwd=repo_root, check=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"chore(waiver-log): auto-close rostered players ({names})"],
            cwd=repo_root, check=True, timeout=10,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Git commit failed: {e}", file=sys.stderr)
        return

    try:
        subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=repo_root, check=True, timeout=30,
        )
        print("  Git push OK", file=sys.stderr)
    except subprocess.CalledProcessError:
        alert = "[fa_scan] git push failed — resolve manually."
        print(f"  {alert}", file=sys.stderr)
        if env:
            send_telegram(alert, env)


# ── Layer 1: Yahoo FA queries ──

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

# ── Layer 2: Quality thresholds ──

# Batter: Sum scoring (3 metrics × percentile → 1-10 each, total 3-30)
# Threshold ≥21 ≈ avg P55+, aligns with Pass 2 「Sum 差 ≥3」 win rule against
# weakest 4 (Albies 9 / Tovar 16 → FA need ≥12/19 to upgrade; ≥21 ensures both)
BATTER_SUM_THRESHOLD = 21

SP_THRESHOLDS = [
    ("xera", 4.64, False),        # P40
    ("xwoba", 0.332, False),      # P40 (xwOBA allowed)
    ("hh_pct", 42.2, False),      # P40
]
# RP: filtered by biweekly SV+H >= 2 + optional xERA < P50 (4.33) in filter_by_savant


# ── Savant CSV utilities ──


def download_savant_csvs(year):
    """Download 4 Savant CSVs for a year. Returns dict of (name_idx, id_idx). Cached."""
    if year in _savant_csv_cache:
        return _savant_csv_cache[year]
    csvs = {}
    for lb, p_type, key in [
        ("statcast", "batter", "batter_sc"),
        ("expected_statistics", "batter", "batter_ex"),
        ("statcast", "pitcher", "pitcher_sc"),
        ("expected_statistics", "pitcher", "pitcher_ex"),
    ]:
        try:
            rows = _download_savant_csv(lb, p_type, year)
            name_idx, id_idx = _build_savant_indexes(rows)
            csvs[key] = (name_idx, id_idx)
            print(f"  Savant {key} {year}: {len(rows)} rows", file=sys.stderr)
        except Exception as e:
            print(f"  Savant {key} {year} failed: {e}", file=sys.stderr)
            csvs[key] = ({}, {})
    _savant_csv_cache[year] = csvs
    return csvs


def _build_savant_indexes(csv_rows):
    """Build name→row and mlb_id→row dicts from Savant CSV rows."""
    name_idx, id_idx = {}, {}
    id_col = _find_id_column(csv_rows[0]) if csv_rows else None
    for row in csv_rows:
        raw = row.get("last_name, first_name") or row.get("\ufefflast_name, first_name", "")
        if raw:
            parts = [p.strip().strip('"') for p in raw.split(",")]
            if len(parts) >= 2:
                key = f"{_normalize(parts[1])} {_normalize(parts[0])}"
                name_idx[key] = row
        if id_col and row.get(id_col, "").strip():
            id_idx[int(row[id_col])] = row
    return name_idx, id_idx


def _match_by_name(name, name_index):
    """O(1) name lookup with Jr./Sr./suffix fallback."""
    norm = _normalize(name)
    if norm in name_index:
        return name_index[norm]
    stripped = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv)$", "", norm, flags=re.I).strip()
    if stripped != norm and stripped in name_index:
        return name_index[stripped]
    return None


def _extract_savant_for_player(name, fa_type, savant_csvs):
    """Extract combined Savant data + mlb_id by name matching across sc+ex CSVs."""
    if fa_type == "batter":
        sc_key, ex_key, p_type = "batter_sc", "batter_ex", "batter"
    else:
        sc_key, ex_key, p_type = "pitcher_sc", "pitcher_ex", "pitcher"

    data = {}
    mlb_id = None
    for csv_key in (sc_key, ex_key):
        row = _match_by_name(name, savant_csvs[csv_key][0])
        if row:
            data.update(_extract_savant_row(row, p_type))
            if mlb_id is None:
                id_col = _find_id_column(row)
                if id_col and row.get(id_col, "").strip():
                    mlb_id = int(row[id_col])
    return (data if data else None, mlb_id)


def _extract_savant_by_id(mlb_id, fa_type, savant_csvs):
    """Extract combined Savant data by mlb_id from id indexes."""
    if fa_type == "batter":
        sc_key, ex_key, p_type = "batter_sc", "batter_ex", "batter"
    else:
        sc_key, ex_key, p_type = "pitcher_sc", "pitcher_ex", "pitcher"

    data = {}
    sc_row = savant_csvs[sc_key][1].get(mlb_id)
    if sc_row:
        data.update(_extract_savant_row(sc_row, p_type))
    ex_row = savant_csvs[ex_key][1].get(mlb_id)
    if ex_row:
        data.update(_extract_savant_row(ex_row, p_type))
    return data if data else None


# ── Layer 2: Quality filter ──


def _classify_fa_type(position_str):
    """Classify Yahoo position string → 'batter'/'sp'/'rp'."""
    positions = position_str.split(",")
    if "SP" in positions:
        return "sp"
    if "RP" in positions:
        return "rp"
    return "batter"


def _check_thresholds(metrics, thresholds):
    """Count how many of 3 threshold conditions pass (used for SP/RP)."""
    passed = 0
    for metric, threshold, higher_better in thresholds:
        val = metrics.get(metric)
        if val is None:
            continue
        if (higher_better and val >= threshold) or (not higher_better and val <= threshold):
            passed += 1
    return passed


def _metric_to_score(value, metric):
    """Convert metric value to 1-10 score per CLAUDE.md Sum 打分表.

    >P90=10, P80-90=9, P70-80=8, P60-70=7, P50-60=6, P40-50=5, P25-40=3, <P25=1
    Returns 0 if value is None (unknown — Sum 不算分).
    """
    if value is None:
        return 0
    bp = BATTER_PCTILES.get(metric)
    if not bp:
        return 0
    higher_better = bp[-1][1] > bp[0][1]
    matched_pct = 0
    for pct, thresh in bp:
        if (higher_better and value >= thresh) or (not higher_better and value <= thresh):
            matched_pct = pct
    if matched_pct >= 90: return 10
    if matched_pct >= 80: return 9
    if matched_pct >= 70: return 8
    if matched_pct >= 60: return 7
    if matched_pct >= 50: return 6
    if matched_pct >= 40: return 5
    if matched_pct >= 25: return 3
    return 1


def _calc_batter_sum(metrics):
    """3-metric Sum (xwOBA + BB% + Barrel%) per CLAUDE.md Step 1 規則."""
    return (
        _metric_to_score(metrics.get("xwoba"), "xwoba")
        + _metric_to_score(metrics.get("bb_pct"), "bb_pct")
        + _metric_to_score(metrics.get("barrel_pct"), "barrel_pct")
    )


def filter_by_savant(snapshot, savant_2026):
    """Layer 2: Filter FA by 2026 Savant quality (P40/P50 threshold, 2/3 pass).

    Name match → get Savant + mlb_id. Failures fallback to search_mlb_id.
    No BBE-based deferral — all filtering uses 2026 data regardless of sample size.
    """
    results = []
    matched = 0
    fallback = 0
    total = len(snapshot)

    for name, info in snapshot.items():
        fa_type = _classify_fa_type(info["position"])
        savant, mlb_id = _extract_savant_for_player(name, fa_type, savant_2026)

        # Name match failed → search_mlb_id fallback
        if savant is None:
            mlb_id = search_mlb_id(name)
            if mlb_id:
                savant = _extract_savant_by_id(mlb_id, fa_type, savant_2026)
                if savant:
                    fallback += 1
            if savant is None:
                if fa_type != "rp":
                    continue  # Batters/SP need Savant; RP can pass without
        else:
            matched += 1

        # ── RP: SV+H-driven filter (independent path) ──
        if fa_type == "rp":
            svh = int(info.get("stats", {}).get("SV+H", 0) or 0)
            if svh < 2:
                continue  # biweekly SV+H < 2 → skip
            # Auxiliary: if 2026 Savant exists and xERA > P50, skip
            if savant and savant.get("xera") and savant["xera"] > 4.33:
                continue
            results.append({
                "name": name,
                "team": info["team"],
                "position": info["position"],
                "pct": info["pct"],
                "stats": info.get("stats", {}),
                "waiver_date": info.get("waiver_date", ""),
                "fa_type": fa_type,
                "savant_2026": savant,  # may be None
                "mlb_id": mlb_id,
                "bbe": savant.get("bbe", 0) if savant else 0,
            })
            continue

        # ── Batters / SP: Statcast quality filter (existing logic) ──
        metrics = {
            "xwoba": savant.get("xwoba") or None,
            "hh_pct": savant.get("hh_pct") or None,
            "barrel_pct": savant.get("barrel_pct") or None,
            "xera": savant.get("xera") or None,
        }
        if fa_type == "batter":
            yahoo_bb = info.get("stats", {}).get("BB")
            savant_pa = savant.get("pa")
            if yahoo_bb and savant_pa and int(savant_pa) > 0:
                metrics["bb_pct"] = int(yahoo_bb) / int(savant_pa) * 100

        # BBE minimum: filter pure noise (BBE < 15 = 1-3 game samples).
        # Watch list players bypass this via direct enrichment.
        if (savant.get("bbe") or 0) < 15:
            continue

        # Quality filter — batter uses Sum scoring, SP keeps 2-of-3 P40
        if fa_type == "batter":
            if _calc_batter_sum(metrics) < BATTER_SUM_THRESHOLD:
                continue
        else:  # sp
            if _check_thresholds(metrics, SP_THRESHOLDS) < 2:
                continue

        results.append({
            "name": name,
            "team": info["team"],
            "position": info["position"],
            "pct": info["pct"],
            "stats": info.get("stats", {}),
            "waiver_date": info.get("waiver_date", ""),
            "fa_type": fa_type,
            "savant_2026": savant,
            "mlb_id": mlb_id,
            "bbe": savant.get("bbe", 0),
        })

    batters = sum(1 for r in results if r["fa_type"] == "batter")
    sps = sum(1 for r in results if r["fa_type"] == "sp")
    rps = sum(1 for r in results if r["fa_type"] == "rp")
    print(f"  Layer 2: {total} FA → {matched} name-matched + {fallback} fallback "
          f"→ {len(results)} passed ({batters} bat Sum≥{BATTER_SUM_THRESHOLD} / "
          f"{sps} SP P40×2 / {rps} RP)", file=sys.stderr)
    return results


# ── Layer 3: Enrichment ──


def _fetch_team_games():
    """Fetch 2026 gamesPlayed for all 30 teams. Returns abbr→games.

    Requires `hydrate=team` because the default standings response no longer
    includes `team.abbreviation` (only id/name/link). Without hydrate every
    abbr collapses to "" and IP/TG / PA/TG factors silently zero out.
    """
    try:
        data = mlb_api_get("/standings?leagueId=103,104&season=2026&hydrate=team")
        result = {}
        for record in data.get("records", []):
            for entry in record.get("teamRecords", []):
                abbr = entry["team"].get("abbreviation", "")
                if abbr:
                    result[abbr] = entry.get("gamesPlayed", 0)
        return result
    except Exception as e:
        print(f"  Standings fetch failed: {e}", file=sys.stderr)
        return {}


def _compute_derived_batter(mlb_stats, team_games, team, year):
    """Compute BB% and PA/Team_G for a batter."""
    if not mlb_stats:
        return {}
    pa = int(mlb_stats.get("plateAppearances", 0))
    bb = int(mlb_stats.get("baseOnBalls", 0))
    d = {}
    d["bb_pct"] = round(bb / pa * 100, 1) if pa > 0 else None
    if year == 2026:
        tg = team_games.get(team, 0)
        d["pa_per_tg"] = round(pa / tg, 2) if tg > 0 else None
    else:
        d["pa_per_tg"] = round(pa / FULL_SEASON_GAMES, 2) if pa > 0 else None
    return d


def _ip_per_gs_from_gamelog(mlb_id, season):
    """Calculate IP/GS using only games where gamesStarted=1 (game log based).

    Returns float or None if no starts found or API error.
    """
    try:
        stats = mlb_api_get(
            f"/people/{mlb_id}/stats?stats=gameLog&season={season}&group=pitching"
        )
        splits = (stats.get("stats") or [{}])[0].get("splits", [])
        starts = [s for s in splits if int(s["stat"].get("gamesStarted", 0)) == 1]
        if not starts:
            return None
        total_ip = sum(_parse_ip(s["stat"].get("inningsPitched", "0")) for s in starts)
        return round(total_ip / len(starts), 1)
    except Exception:
        return None


def _compute_derived_pitcher(savant, mlb_stats, team_games, team, year, fa_type,
                             mlb_id=None):
    """Compute ERA, IP/GS, K/9, IP/TG, |xERA-ERA| for SP or RP."""
    if not mlb_stats:
        return {}
    ip = _parse_ip(mlb_stats.get("inningsPitched", "0"))
    era_str = mlb_stats.get("era", "0")
    era = float(era_str) if era_str not in ("—", "-", "", "-.--") else None
    d = {"era": era, "ip": round(ip, 1)}

    xera = savant.get("xera") if savant else None
    if xera is not None and xera > 0 and era is not None:
        d["era_diff"] = round(xera - era, 2)

    if fa_type == "sp":
        # IP/GS from game log only (GS=1 splits). None on API fail or no
        # starts — fail loud rather than fall back to naive total-IP/GS,
        # which inflates for swingmen with token starts.
        d["ip_per_gs"] = _ip_per_gs_from_gamelog(mlb_id, year) if mlb_id else None
        # IP/Team_G for Phase 3 urgency factor (active 輪值 vs stash)
        if year == 2026:
            tg = team_games.get(team, 0)
            d["ip_per_tg"] = round(ip / tg, 2) if tg > 0 else None
        else:
            d["ip_per_tg"] = round(ip / FULL_SEASON_GAMES, 2) if ip > 0 else None
    else:
        k = int(mlb_stats.get("strikeOuts", 0))
        d["k_per_9"] = round(k * 9 / ip, 2) if ip > 0 else None
        if year == 2026:
            tg = team_games.get(team, 0)
            d["ip_per_tg"] = round(ip / tg, 2) if tg > 0 else None
        else:
            d["ip_per_tg"] = round(ip / FULL_SEASON_GAMES, 2) if ip > 0 else None
    return d


def enrich_layer3(filtered, savant_2026, config, savant_prior=True):
    """Layer 3: Pure enrichment — prior Savant + MLB Stats + derived metrics.

    No quality filtering. mlb_id already obtained in Layer 2.
    savant_prior: True = fetch 2025 data (default). False = skip all 2025.
    """
    standings = _fetch_team_games()

    savant_2025 = None
    if savant_prior:
        print("  Downloading 2025 Savant CSVs...", file=sys.stderr)
        savant_2025 = download_savant_csvs(2025)

    enriched = []
    for p in filtered:
        mlb_id = p.get("mlb_id")
        fa_type = p["fa_type"]
        group = "hitting" if fa_type == "batter" else "pitching"
        team = p["team"]

        if not mlb_id:
            print(f"  SKIP {p['name']}: no mlb_id", file=sys.stderr)
            continue

        # 2026 MLB Stats (always)
        p["mlb_2026"] = fetch_mlb_season_stats(mlb_id, 2026, group)

        # 2025 data (optional — skip when 2026 sample is sufficient)
        if savant_prior:
            p["savant_2025"] = _extract_savant_by_id(mlb_id, fa_type, savant_2025)
            p["mlb_2025"] = fetch_mlb_season_stats(mlb_id, 2025, group)
        else:
            p["savant_2025"] = None
            p["mlb_2025"] = None

        # Derived metrics
        s26 = p.get("savant_2026")
        s25 = p.get("savant_2025")
        p["derived_2026"] = (
            _compute_derived_batter(p["mlb_2026"], standings, team, 2026)
            if fa_type == "batter" else
            _compute_derived_pitcher(s26, p["mlb_2026"], standings, team, 2026, fa_type,
                                     mlb_id=mlb_id)
        )
        if savant_prior:
            p["derived_2025"] = (
                _compute_derived_batter(p["mlb_2025"], standings, team, 2025)
                if fa_type == "batter" else
                _compute_derived_pitcher(s25, p["mlb_2025"], standings, team, 2025, fa_type,
                                         mlb_id=mlb_id)
            )
        else:
            p["derived_2025"] = {}

        enriched.append(p)
        time.sleep(0.2)  # MLB API rate limit

    print(f"  Layer 3: {len(filtered)} → {len(enriched)} enriched", file=sys.stderr)
    return enriched


# ── Roster data for Pass 1 ──


def build_roster_for_pass1(config, savant_2026, player_type="batter"):
    """Build roster data string for Pass 1 (Claude picks weakest players).

    Args:
        player_type: "batter", "sp", or "rp"

    Returns formatted string with bottom N players sorted by quality.
    """
    # Exclude IL/IL+/NA and can't-cut players — they can't be dropped
    cant_cut = {n.lower() for n in config.get("league", {}).get("cant_cut", [])}

    def _is_replaceable(p):
        if not is_active(p):
            return False
        if p.get("name", "").lower() in cant_cut:
            return False
        return True

    if player_type == "batter":
        players = [p for p in config.get("batters", []) if _is_replaceable(p)]
        hide_top = 5
        sort_key = "xwoba"
        higher_better = True
    elif player_type == "rp":
        players = [p for p in config.get("pitchers", [])
                   if pitcher_type(p) == "RP" and _is_replaceable(p)]
        hide_top = 0  # show all RP (only 2)
        sort_key = "xera"
        higher_better = False
    else:
        players = [p for p in config.get("pitchers", [])
                   if pitcher_type(p) == "SP" and _is_replaceable(p)]
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

    # Sort: batter by xwOBA asc (worst first), SP/RP by xERA desc (worst first)
    scored.sort(key=lambda x: x["sort_val"] or (0 if higher_better else 999),
                reverse=(not higher_better))

    # Hide top N (strongest)
    shown = scored[:-hide_top] if hide_top and len(scored) > hide_top else scored

    # Format output
    pt = "pitcher" if player_type != "batter" else "batter"
    lines = []
    for item in shown:
        p = item["player"]
        s = item["savant"] or {}
        name = p["name"]
        team = p["team"]
        pos = "/".join(p.get("positions", [])) if player_type == "batter" else player_type.upper()

        parts = [f"{name}({team}) {pos}"]

        if player_type == "batter":
            if s.get("xwoba"):
                parts.append(f"xwOBA {s['xwoba']:.3f} {pctile_tag(s['xwoba'], 'xwoba')}")
            if s.get("bb_pct") is not None:
                parts.append(f"BB% {s['bb_pct']:.1f}% {pctile_tag(s['bb_pct'], 'bb_pct')}")
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

    label = {"batter": "打者", "sp": "SP", "rp": "RP"}[player_type]
    header = f"[{label}] 以下為可能被替換的球員（由弱到強）："
    return header + "\n" + "\n".join(lines)


# ── Roster summary ──


def build_roster_summary(config, savant_2026=None):
    """Build roster summary: 2026 Statcast primary, 2025 prior_stats as auxiliary."""
    lines = [
        "--- 我的陣容（由弱到強，最強已隱藏）---",
        "  排序依據：打者 xwOBA / SP xERA（2026 優先，無 2026 用 2025）",
    ]

    def _get_sort_key_batter(b):
        s26 = _lookup_roster_savant(b, "batter", savant_2026)
        if s26 and s26.get("xwoba"):
            return s26["xwoba"]
        return b.get("prior_stats", {}).get("xwoba", 0)

    def _get_sort_key_sp(p):
        s26 = _lookup_roster_savant(p, "pitcher", savant_2026)
        if s26 and s26.get("xera"):
            return s26["xera"]
        return p.get("prior_stats", {}).get("xera", 99)

    # Batters: sort by xwOBA ascending, hide top 5
    batters = sorted(config["batters"], key=_get_sort_key_batter)
    show_b = max(len(batters) - 5, 0)
    if show_b:
        lines.append("[打者]")
        for b in batters[:show_b]:
            lines.append(_fmt_roster_batter(b, savant_2026))

    # SP: sort by xERA descending (worst first), hide top 3
    sps = [p for p in config["pitchers"] if "SP" in p.get("positions", [])]
    sps.sort(key=_get_sort_key_sp, reverse=True)
    show_sp = max(len(sps) - 3, 0)
    if show_sp:
        lines.append("[SP]")
        for p in sps[:show_sp]:
            lines.append(_fmt_roster_pitcher(p, "pitcher", savant_2026))

    # RP: show all
    rps = [p for p in config["pitchers"] if "RP" in p.get("positions", [])]
    if rps:
        lines.append("[RP]")
        for p in rps:
            lines.append(_fmt_roster_pitcher(p, "rp", savant_2026))

    return "\n".join(lines)


def _lookup_roster_savant(player, p_type, savant_2026):
    """Look up a roster player's 2026 Savant data by mlb_id."""
    if not savant_2026 or not player.get("mlb_id"):
        return None
    return _extract_savant_by_id(player["mlb_id"], p_type, savant_2026)


def _fmt_roster_batter(b, savant_2026=None):
    ps = b.get("prior_stats", {})
    s26 = _lookup_roster_savant(b, "batter", savant_2026)
    pos = "/".join(b.get("positions", []))

    # Primary: 2026 if available
    if s26 and (s26.get("xwoba") is not None or s26.get("barrel_pct") is not None):
        bbe = s26.get("bbe", 0)
        parts = [f"[2026 BBE {bbe}]"]
        if s26.get("xwoba") is not None:
            parts.append(f"xwOBA {s26['xwoba']:.3f} {pctile_tag(s26['xwoba'], 'xwoba', 'batter')}")
        if s26.get("barrel_pct") is not None:
            parts.append(f"Barrel% {s26['barrel_pct']:.1f}% {pctile_tag(s26['barrel_pct'], 'barrel_pct', 'batter')}")
        if s26.get("hh_pct") is not None:
            parts.append(f"HH% {s26['hh_pct']:.1f}%")
        line = f"  {b['name']}({b['team']}) {pos} — {' | '.join(parts)}"
        # Auxiliary: 2025 one-liner
        y25 = []
        if ps.get("xwoba") is not None:
            y25.append(f"xwOBA {ps['xwoba']:.3f}")
        if ps.get("bb_pct") is not None:
            y25.append(f"BB% {ps['bb_pct']:.1f}%")
        if ps.get("barrel_pct") is not None:
            y25.append(f"Barrel% {ps['barrel_pct']:.1f}%")
        if y25:
            line += f"\n    2025: {' | '.join(y25)}"
        return line

    # Fallback: 2025 only
    parts = []
    if ps.get("xwoba") is not None:
        parts.append(f"xwOBA {ps['xwoba']:.3f} {pctile_tag(ps['xwoba'], 'xwoba', 'batter')}")
    if ps.get("bb_pct") is not None:
        parts.append(f"BB% {ps['bb_pct']:.1f}% {pctile_tag(ps['bb_pct'], 'bb_pct', 'batter')}")
    if ps.get("barrel_pct") is not None:
        parts.append(f"Barrel% {ps['barrel_pct']:.1f}% {pctile_tag(ps['barrel_pct'], 'barrel_pct', 'batter')}")
    if ps.get("hh_pct") is not None:
        parts.append(f"HH% {ps['hh_pct']:.1f}%")
    if ps.get("ops"):
        parts.append(f"OPS {ps['ops']:.3f}")
    if ps.get("pa_per_team_g") is not None:
        parts.append(f"PA/TG {ps['pa_per_team_g']:.2f}")
    return f"  {b['name']}({b['team']}) {pos} — [2025] {' | '.join(parts)}"


def _fmt_roster_pitcher(p, pt, savant_2026=None):
    """Format roster pitcher (SP or RP). pt = 'pitcher' or 'rp'."""
    ps = p.get("prior_stats", {})
    s26 = _lookup_roster_savant(p, "pitcher", savant_2026)

    # Primary: 2026 if available
    if s26 and (s26.get("xera") is not None or s26.get("xwoba") is not None):
        bbe = s26.get("bbe", 0)
        parts = [f"[2026 BBE {bbe}]"]
        if s26.get("xera") is not None:
            parts.append(f"xERA {s26['xera']:.2f} {pctile_tag(s26['xera'], 'xera', pt)}")
        if s26.get("xwoba") is not None:
            parts.append(f"xwOBA {s26['xwoba']:.3f} {pctile_tag(s26['xwoba'], 'xwoba', pt)}")
        if s26.get("hh_pct") is not None:
            parts.append(f"HH% {s26['hh_pct']:.1f}% {pctile_tag(s26['hh_pct'], 'hh_pct', pt)}")
        if pt == "rp" and ps.get("k_per_9") is not None:
            parts.append(f"K/9 {ps['k_per_9']:.2f} {pctile_tag(ps['k_per_9'], 'k_per_9', 'rp')}")
        line = f"  {p['name']}({p['team']}) — {' | '.join(parts)}"
        # Auxiliary: 2025 one-liner
        y25 = []
        if ps.get("xera") is not None:
            y25.append(f"xERA {ps['xera']:.2f}")
        if ps.get("xwoba_allowed") is not None:
            y25.append(f"xwOBA {ps['xwoba_allowed']:.3f}")
        if ps.get("hh_pct_allowed") is not None:
            y25.append(f"HH% {ps['hh_pct_allowed']:.1f}%")
        if y25:
            line += f"\n    2025: {' | '.join(y25)}"
        return line

    # Fallback: 2025 only
    parts = []
    if ps.get("xera") is not None:
        parts.append(f"xERA {ps['xera']:.2f} {pctile_tag(ps['xera'], 'xera', pt)}")
    if ps.get("xwoba_allowed") is not None:
        parts.append(f"xwOBA {ps['xwoba_allowed']:.3f} {pctile_tag(ps['xwoba_allowed'], 'xwoba', pt)}")
    if ps.get("hh_pct_allowed") is not None:
        parts.append(f"HH% {ps['hh_pct_allowed']:.1f}% {pctile_tag(ps['hh_pct_allowed'], 'hh_pct', pt)}")
    if ps.get("barrel_pct_allowed") is not None:
        parts.append(f"Barrel% {ps['barrel_pct_allowed']:.1f}%")
    if ps.get("era") is not None:
        parts.append(f"ERA {ps['era']:.2f}")
    if pt == "rp":
        if ps.get("k_per_9") is not None:
            parts.append(f"K/9 {ps['k_per_9']:.2f} {pctile_tag(ps['k_per_9'], 'k_per_9', 'rp')}")
        if ps.get("ip_per_team_g") is not None:
            parts.append(f"IP/TG {ps['ip_per_team_g']:.2f}")
    else:
        if ps.get("ip_per_gs") is not None:
            tier = " [深投]" if ps["ip_per_gs"] > 5.7 else (" [短局]" if ps["ip_per_gs"] < 5.3 else "")
            parts.append(f"IP/GS {ps['ip_per_gs']:.1f}{tier}")
    return f"  {p['name']}({p['team']}) — [2025] {' | '.join(parts)}"


# ── Output formatting ──


def _bbe_label(bbe):
    if bbe < 30:
        return f"BBE {bbe} (低信心)"
    elif bbe <= 50:
        return f"BBE {bbe} (中等信心)"
    return f"BBE {bbe} (高信心)"


def _fmt_owned_change(d1, d3):
    """Format %owned 24h/3d change string like '(+3/+8)'."""
    d1s = f"+{d1}" if d1 and d1 > 0 else (str(d1) if d1 else "—")
    d3s = f"+{d3}" if d3 and d3 > 0 else (str(d3) if d3 else "—")
    return f"({d1s}/{d3s})"


def _format_fa_batter(p, fa_rolling=None):
    s26 = p.get("savant_2026") or {}
    d26 = p.get("derived_2026") or {}
    s25 = p.get("savant_2025") or {}
    d25 = p.get("derived_2025") or {}
    yahoo = p.get("stats", {})

    header = (f"  {p['name']} ({p['team']}, {p['position']}) — "
              f"{p['pct']}% {_fmt_owned_change(p.get('d1'), p.get('d3'))}")
    lines = [header]

    # Quality
    q = []
    if s26.get("xwoba") is not None:
        q.append(f"xwOBA {s26['xwoba']:.3f} {pctile_tag(s26['xwoba'], 'xwoba', 'batter')}")
    if d26.get("bb_pct") is not None:
        q.append(f"BB% {d26['bb_pct']:.1f}% {pctile_tag(d26['bb_pct'], 'bb_pct', 'batter')}")
    if s26.get("barrel_pct") is not None:
        q.append(f"Barrel% {s26['barrel_pct']:.1f}% {pctile_tag(s26['barrel_pct'], 'barrel_pct', 'batter')}")
    if q:
        lines.append(f"    品質: {' | '.join(q)}")

    # Auxiliary
    aux = []
    if s26.get("hh_pct") is not None:
        aux.append(f"HH% {s26['hh_pct']:.1f}%")
    if yahoo.get("OPS"):
        aux.append(f"OPS {yahoo['OPS']}")
    if aux:
        lines.append(f"    輔助: {' | '.join(aux)}")

    # Volume
    if d26.get("pa_per_tg") is not None:
        lines.append(f"    產量: PA/TG {d26['pa_per_tg']:.2f} "
                      f"{pctile_tag(d26['pa_per_tg'], 'pa_per_tg', 'batter')}")

    # Yahoo stats
    yp = [f"{k} {yahoo[k]}" for k in ("AVG", "OPS", "HR", "BB") if yahoo.get(k)]
    if yp:
        lines.append(f"    Yahoo: {' | '.join(yp)}")

    lines.append(f"    {_bbe_label(p.get('bbe', 0))}")

    # 14d rolling (Pass 2 task B add evaluation, BBE >= 25 gate)
    mlb_id_str = str(p.get("mlb_id", ""))
    r14 = (fa_rolling or {}).get(mlb_id_str) if mlb_id_str else None
    if r14 and r14.get("bbe", 0) >= 25:
        s26_xwoba = s26.get("xwoba")
        r14_xwoba = r14.get("xwoba")
        delta_str = ""
        if s26_xwoba and r14_xwoba:
            delta = r14_xwoba - s26_xwoba
            delta_str = f" Δ{delta:+.3f}"
        lines.append(
            f"    14d: xwOBA {r14_xwoba:.3f}{delta_str} | "
            f"HH% {r14.get('hh_pct', 0):.1f}% | BBE {r14.get('bbe', 0)}"
        )

    # 2025
    if s25:
        y25 = []
        if s25.get("xwoba") is not None:
            y25.append(f"xwOBA {s25['xwoba']:.3f}")
        if d25.get("bb_pct") is not None:
            y25.append(f"BB% {d25['bb_pct']:.1f}%")
        if s25.get("barrel_pct") is not None:
            y25.append(f"Barrel% {s25['barrel_pct']:.1f}%")
        if s25.get("bbe"):
            y25.append(f"BBE {s25['bbe']}")
        if y25:
            lines.append(f"    2025: {' | '.join(y25)}")

    return "\n".join(lines)


def _format_fa_pitcher(p, fa_rolling=None):
    s26 = p.get("savant_2026") or {}
    d26 = p.get("derived_2026") or {}
    s25 = p.get("savant_2025") or {}
    d25 = p.get("derived_2025") or {}
    yahoo = p.get("stats", {})
    fa_type = p["fa_type"]
    pt = "rp" if fa_type == "rp" else "pitcher"

    header = (f"  {p['name']} ({p['team']}, {p['position']}) — "
              f"{p['pct']}% {_fmt_owned_change(p.get('d1'), p.get('d3'))}")
    lines = [header]

    # Quality
    q = []
    if s26.get("xera") is not None:
        q.append(f"xERA {s26['xera']:.2f} {pctile_tag(s26['xera'], 'xera', pt)}")
    if s26.get("xwoba") is not None:
        q.append(f"xwOBA {s26['xwoba']:.3f} {pctile_tag(s26['xwoba'], 'xwoba', pt)}")
    if s26.get("hh_pct") is not None:
        q.append(f"HH% {s26['hh_pct']:.1f}% {pctile_tag(s26['hh_pct'], 'hh_pct', pt)}")
    if q:
        lines.append(f"    品質: {' | '.join(q)}")

    # Auxiliary
    aux = []
    if s26.get("barrel_pct") is not None:
        aux.append(f"Barrel% {s26['barrel_pct']:.1f}%")
    if d26.get("era") is not None:
        aux.append(f"ERA {d26['era']:.2f}")
    if d26.get("era_diff") is not None:
        tag = pctile_tag(abs(d26["era_diff"]), "era_diff", pt)
        sign = "+" if d26["era_diff"] > 0 else ""
        aux.append(f"運氣 {sign}{d26['era_diff']:.2f} {tag}")
    if aux:
        lines.append(f"    輔助: {' | '.join(aux)}")

    # Volume
    if fa_type == "sp":
        vol = []
        ipgs = d26.get("ip_per_gs")
        if ipgs is not None:
            tier = " [深投]" if ipgs > 5.7 else (" [短局]" if ipgs < 5.3 else "")
            vol.append(f"IP/GS {ipgs:.1f}{tier}")
        iptg = d26.get("ip_per_tg")
        if iptg is not None:
            role = " [主力]" if iptg >= 1.0 else (" [stash]" if iptg < 0.5 else " [半 active]")
            vol.append(f"IP/TG {iptg:.2f}{role}")
        if vol:
            lines.append(f"    產量: {' | '.join(vol)}")
    else:
        vol = []
        if d26.get("k_per_9") is not None:
            vol.append(f"K/9 {d26['k_per_9']:.2f} {pctile_tag(d26['k_per_9'], 'k_per_9', 'rp')}")
        if d26.get("ip_per_tg") is not None:
            vol.append(f"IP/TG {d26['ip_per_tg']:.2f} {pctile_tag(d26['ip_per_tg'], 'ip_per_tg', 'rp')}")
        if vol:
            lines.append(f"    產量: {' | '.join(vol)}")
        svh = yahoo.get("SV+H")
        if svh and str(svh) != "0":
            lines.append(f"    加分: SV+H {svh}")

    # Yahoo stats
    y_keys = ("ERA", "WHIP", "K", "IP", "SV+H") if fa_type == "rp" else ("ERA", "WHIP", "K", "IP")
    yp = [f"{k} {yahoo[k]}" for k in y_keys if yahoo.get(k)]
    if yp:
        lines.append(f"    Yahoo: {' | '.join(yp)}")

    lines.append(f"    {_bbe_label(p.get('bbe', 0))}")

    # 2025
    if s25:
        y25 = []
        if s25.get("xera") is not None:
            y25.append(f"xERA {s25['xera']:.2f}")
        if s25.get("xwoba") is not None:
            y25.append(f"xwOBA {s25['xwoba']:.3f}")
        if s25.get("hh_pct") is not None:
            y25.append(f"HH% {s25['hh_pct']:.1f}%")
        if s25.get("bbe"):
            y25.append(f"BBE {s25['bbe']}")
        if y25:
            lines.append(f"    2025: {' | '.join(y25)}")

    # 21d rolling (SP only, Pass 2 task B add evaluation, BBE >= 20 gate)
    if fa_type == "sp" and fa_rolling:
        mlb_id_str = str(p.get("mlb_id", ""))
        r21 = fa_rolling.get(mlb_id_str) if mlb_id_str else None
        if r21 and r21.get("bbe", 0) >= 20:
            s26_xwoba = s26.get("xwoba")
            r21_xwoba = r21.get("xwoba")
            delta_str = ""
            if s26_xwoba and r21_xwoba:
                delta = r21_xwoba - s26_xwoba
                delta_str = f" Δ{delta:+.3f}"
            lines.append(
                f"    21d: xwOBA {r21_xwoba:.3f}{delta_str} | "
                f"HH% {r21.get('hh_pct', 0):.1f}% | BBE {r21.get('bbe', 0)}"
            )

    return "\n".join(lines)


def _format_owned_risers(changes):
    """Format %owned risers by position, 3d sort, risers only."""
    lines = []
    batters = [c for c in changes if _classify_fa_type(c["position"]) == "batter"]
    sps = [c for c in changes if _classify_fa_type(c["position"]) == "sp"]
    rps = [c for c in changes if _classify_fa_type(c["position"]) == "rp"]

    for label, group, top_n in [("打者", batters, 20), ("SP", sps, 20), ("RP", rps, 5)]:
        rising = sorted(
            [c for c in group if c.get("d3") is not None and c["d3"] > 0],
            key=lambda x: x["d3"], reverse=True,
        )[:top_n]
        if rising:
            lines.append(f"  [{label}]")
            for c in rising:
                d1 = f"+{c['d1']}" if c.get("d1") and c["d1"] > 0 else str(c.get("d1", "—"))
                lines.append(
                    f"    {c['name']:20} 3d:+{c['d3']:>3} 24h:{d1:>4}  "
                    f"{c['pct']:>3}%  {c['position']}"
                )

    return "\n".join(lines) if lines else "  (升幅數據不足)"


# ── Build data for Claude ──


_FRAMEWORK_SKIP_PATTERNS = [
    "唯一定義。Skills",           # meta comment
    "**評估流程**",               # code already handles sorting
    "上季 < 80 場",              # Claude can't query career stats
    "上季 < 80 IP",              # Claude can't compute intervals
    "串流 SP：",                  # not weekly scan's job
    "不使用 BvP",                # data not provided
]


def _extract_eval_framework():
    """Extract evaluation framework from CLAUDE.md, trimmed for weekly scan."""
    claude_md = os.path.join(SCRIPT_DIR, "..", "CLAUDE.md")
    try:
        with open(claude_md, encoding="utf-8") as f:
            content = f.read()
        start = content.find("## 球員評估框架")
        end = content.find("### 2025 MLB 百分位分布")
        if start == -1 or end == -1:
            return ""
        raw = content[start:end].strip()
        # Post-process: remove lines irrelevant to weekly scan
        lines = raw.split("\n")
        filtered = []
        skip_indent = False
        for line in lines:
            # Skip numbered sub-steps under "評估流程"
            if skip_indent:
                if line.startswith("1. ") or line.startswith("2. "):
                    continue
                skip_indent = False
            if any(p in line for p in _FRAMEWORK_SKIP_PATTERNS):
                if "評估流程" in line:
                    skip_indent = True
                continue
            filtered.append(line)
        return "\n".join(filtered).strip()
    except Exception as e:
        print(f"  CLAUDE.md read failed: {e}", file=sys.stderr)
        return ""


def _load_savant_rolling(player_type="batter"):
    """Load savant_rolling.json, returning batter 14d or pitcher 21d section.

    Args:
        player_type: "batter" → players section; "sp"/"pitcher" → pitchers section

    Returns:
        dict[str, dict] — {player_id_str: {name, xwoba, hh_pct, barrel_pct, bbe, pa}}
    """
    path = os.path.join(SCRIPT_DIR, "savant_rolling.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        key = "players" if player_type == "batter" else "pitchers"
        return data.get(key, {})
    except Exception as e:
        print(f"Failed to load savant_rolling.json: {e}", file=sys.stderr)
        return {}


def _fetch_fa_rolling(fa_candidates, watch_candidates, today_str, player_type="batter"):
    """Fetch rolling Savant for FA + watchlist (Pass 2 add evaluation).

    Args:
        player_type: "batter" (14d) or "pitcher" (21d)

    Returns:
        dict[str, dict] — {mlb_id_str: {xwoba, barrel_pct, hh_pct, bbe, pa}}
    """
    mlb_ids = []
    for p in list(fa_candidates) + list(watch_candidates):
        mid = p.get("mlb_id")
        if mid:
            mlb_ids.append(int(mid))
    mlb_ids = list(set(mlb_ids))  # dedupe (overlap between fa and watch possible)

    if not mlb_ids:
        return {}

    window = 14 if player_type == "batter" else 21
    label = player_type
    print(f"  Pass 2 ({label}): fetching {window}d for {len(mlb_ids)} FA/watch...",
          file=sys.stderr)
    data = fetch_savant_rolling(mlb_ids, today_str, window_days=window,
                                player_type=player_type)
    return {str(pid): metrics for pid, metrics in data.items()}


def build_weekly_data(today_str, enriched, changes, ref_1d, ref_3d,
                      roster_summary, config):
    """Build comprehensive data summary for claude -p."""
    lines = [f"=== Weekly Deep Scan ({today_str}) ===\n"]

    # Embed evaluation framework from CLAUDE.md
    framework = _extract_eval_framework()
    if framework:
        lines.append(f"--- 評估框架（from CLAUDE.md）---\n{framework}\n")

    lines.append(roster_summary)

    # FA candidates by type
    fa_batters = [p for p in enriched if p["fa_type"] == "batter"]
    fa_sps = [p for p in enriched if p["fa_type"] == "sp"]
    fa_rps = [p for p in enriched if p["fa_type"] == "rp"]

    if fa_batters:
        lines.append(f"\n--- FA 打者候選 ({len(fa_batters)} 人) ---")
        for p in fa_batters:
            lines.append(_format_fa_batter(p))

    if fa_sps:
        lines.append(f"\n--- FA SP 候選 ({len(fa_sps)} 人) ---")
        for p in fa_sps:
            lines.append(_format_fa_pitcher(p))

    if fa_rps:
        lines.append(f"\n--- FA RP 候選 ({len(fa_rps)} 人) ---")
        for p in fa_rps:
            lines.append(_format_fa_pitcher(p))

    # %owned risers
    ref_parts = []
    if ref_1d:
        ref_parts.append(f"24h vs {ref_1d}")
    if ref_3d:
        ref_parts.append(f"3d vs {ref_3d}")
    lines.append(f"\n--- %owned 升幅 ({' | '.join(ref_parts) or 'N/A'}) ---")
    lines.append(_format_owned_risers(changes))

    # waiver-log
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            lines.append(f"\n--- waiver-log.md ---\n{f.read()}")


    return "\n".join(lines)


# ── Persistence ──


def save_summary(advice):
    summary = advice[:800] if len(advice) > 800 else advice
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Summary saved to {SUMMARY_FILE}", file=sys.stderr)


# ── Two-pass Claude helpers ──


def _call_claude(prompt_path, data, timeout=600, retries=1):
    """Call claude -p with prompt + data. Returns advice string or raises."""
    with open(prompt_path, encoding="utf-8") as f:
        prompt = f.read()
    if "{data}" in prompt:
        full_prompt = prompt.replace("{data}", data)
    elif "{roster_data}" in prompt:
        full_prompt = prompt.replace("{roster_data}", data)
    else:
        full_prompt = f"{prompt}\n\n---\n\n{data}"
    last_err = None
    for attempt in range(1 + retries):
        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True, text=True, encoding="utf-8", timeout=timeout,
            )
            if result.returncode != 0:
                raise RuntimeError(f"claude -p failed: {result.stderr[:500]}")
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, RuntimeError) as e:
            last_err = e
            if attempt < retries:
                print(f"  claude -p attempt {attempt+1} failed ({type(e).__name__}), retrying...",
                      file=sys.stderr)
    raise last_err


def _notify(env, args, message):
    """Send Telegram notification (unless --no-send)."""
    print(message, file=sys.stderr)
    if not args.no_send:
        send_telegram(message, env)


def _handle_error(step_name, error, env, args):
    """Handle pipeline error: print, Telegram notify, optionally create error Issue."""
    full_msg = f"[FA Scan] {step_name} failed: {error}"
    print(full_msg, file=sys.stderr)
    if not args.no_send:
        # Telegram: concise message (TimeoutExpired str() contains the full prompt)
        err_type = type(error).__name__
        if isinstance(error, subprocess.TimeoutExpired):
            tg_msg = f"[FA Scan] {step_name} failed: claude -p timed out after {error.timeout}s (with retry)"
        else:
            tg_msg = f"[FA Scan] {step_name} failed: {err_type}: {str(error)[:200]}"
        send_telegram(tg_msg, env)
        try:
            subprocess.run(
                ["gh", "issue", "create", "--repo", "huansbox/mlb-fantasy",
                 "--title", f"[FA Scan Error] {step_name}",
                 "--body", f"```\n{full_msg[:3000]}\n```",
                 "--label", "fa-scan-error"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
        except Exception:
            pass


def _publish(today_str, scan_type, advice_telegram, advice_issue, raw_data, env, args):
    """Publish results: Telegram (compact) + GitHub Issue (full analysis).

    Skip flags:
    - --no-send: skip Telegram + Issue (print to stdout for dev/CI)
    - --no-issue: skip Issue only (Telegram still goes; Stage E parallel uses this)
    """
    if args.no_send:
        print(advice_telegram, flush=True)
        return

    send_telegram(advice_telegram, env)

    if getattr(args, "no_issue", False):
        return

    title = f"[FA Scan {scan_type}] {today_str}"
    body = f"""## Analysis

{advice_issue}

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


def _update_waiver_log(advice, today_str, env=None):
    """Parse waiver-log update block from Claude output, write to waiver-log.md.

    Expects ```waiver-log ... ``` block in advice with lines:
      NEW|name|team|position|mlb_id|trigger|summary
      UPDATE|name|summary

    Thread-safe: _WAIVER_LOG_LOCK serializes git pull/commit/push so that
    parallel batter + SP scans don't race on the working tree.
    """
    if "```waiver-log" not in advice:
        return
    with _WAIVER_LOG_LOCK:
        _update_waiver_log_locked(advice, today_str, env)


def _update_waiver_log_locked(advice, today_str, env=None):
    """Actual waiver-log update logic (called inside _WAIVER_LOG_LOCK)."""
    if "```waiver-log" not in advice:
        return
    try:
        block = advice.split("```waiver-log")[1].split("```")[0].strip()
    except IndexError:
        return
    if not block:
        print("  waiver-log: empty block (no actions)", file=sys.stderr)
        return

    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if not os.path.exists(waiver_log_path):
        return

    repo_root = os.path.join(SCRIPT_DIR, "..")
    if not _sync_waiver_log_before_edit(repo_root, env):
        return

    with open(waiver_log_path, encoding="utf-8") as f:
        content = f.read()

    # Short date format (MM-DD) for consistency with existing entries
    short_date = today_str[5:]  # "2026-04-07" → "04-07"

    modified = False
    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")

        if parts[0] == "NEW" and len(parts) >= 6:
            _, name, team, position, trigger, summary = parts[0], parts[1], parts[2], parts[3], parts[4], "|".join(parts[5:])
            # Check if player already exists in 觀察中
            if name in content:
                # Treat as UPDATE instead — but skip 條件 Pass players
                if _is_condition_pass(content, name):
                    print(f"  waiver-log: SKIP UPDATE {name} (條件 Pass)", file=sys.stderr)
                    continue
                content = _insert_update_line(content, name, short_date, summary)
                modified = True
                continue
            # Resolve mlb_id via API (don't trust Claude's ID)
            mlb_id = search_mlb_id(name)
            mlb_id_tag = f" [mlb_id:{mlb_id}]" if mlb_id else ""
            # Append new player block to end of 觀察中 section
            new_entry = (
                f"\n### {name} ({team}, {position}){mlb_id_tag} — 觀察中\n"
                f"觸發：{trigger}\n"
                f"- {short_date}：{summary}（fa_scan）\n"
            )
            # Insert new FA at the END of 觀察中 section, which means BEFORE
            # the next section header. Try ## 隊上觀察 first (FA goes in 觀察中,
            # not in 隊上觀察); fall back to ## 已結案; finally append.
            if "## 隊上觀察" in content:
                pos = content.index("## 隊上觀察")
                content = content[:pos] + new_entry + "\n" + content[pos:]
            elif "## 已結案" in content:
                pos = content.index("## 已結案")
                content = content[:pos] + new_entry + "\n" + content[pos:]
            else:
                content += new_entry
            modified = True
            print(f"  waiver-log: NEW {name}", file=sys.stderr)

        elif parts[0] == "UPDATE" and len(parts) >= 3:
            _, name, summary = parts[0], parts[1], "|".join(parts[2:])
            # Skip 條件 Pass players
            if _is_condition_pass(content, name):
                print(f"  waiver-log: SKIP UPDATE {name} (條件 Pass)", file=sys.stderr)
                continue
            content = _insert_update_line(content, name, short_date, summary)
            modified = True
            print(f"  waiver-log: UPDATE {name}", file=sys.stderr)

    if not modified:
        return

    # Clean up excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    with open(waiver_log_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Git commit + push (pre-edit sync already done above)
    try:
        subprocess.run(["git", "add", "waiver-log.md"],
                       cwd=repo_root, check=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore(waiver-log): fa_scan auto-update {today_str}"],
            cwd=repo_root, check=True, timeout=10)
    except subprocess.CalledProcessError as e:
        print(f"  waiver-log git commit failed: {e}", file=sys.stderr)
        return

    # Push to the current branch (not hard-coded master) — VPS may run on a
    # feature branch during development; pushing to master would fail with
    # non-fast-forward and drop waiver-log updates.
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True, timeout=5,
        )
        current_branch = branch_result.stdout.strip() or "master"
    except subprocess.CalledProcessError:
        current_branch = "master"

    try:
        subprocess.run(["git", "push", "origin", current_branch],
                       cwd=repo_root, check=True, timeout=30)
        print(f"  waiver-log: git push OK ({current_branch})", file=sys.stderr)
    except subprocess.CalledProcessError:
        msg = f"[fa_scan] waiver-log git push failed ({current_branch})."
        print(f"  {msg}", file=sys.stderr)
        if env:
            send_telegram(msg, env)


def _is_condition_pass(content, player_name):
    """Check if a player's section in waiver-log is marked as 條件 Pass."""
    pattern = re.compile(
        rf"### {re.escape(player_name)} \([^)]+\)[^\n]*",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return False
    return "條件 Pass" in match.group(0)


def _insert_update_line(content, player_name, short_date, summary):
    """Insert or replace a date line under an existing player's section.

    Dedup strategy: when a same-date (fa_scan) line already exists within
    the player's section, replace the last one with the new summary rather
    than appending. Prevents the 5-6 near-duplicate lines per player that
    accumulated when fa_scan ran multiple times in one day (12:30 cron +
    ad-hoc reruns both appended). The most recent run's phrasing wins.
    """
    # Find the player's ### header
    pattern = re.compile(
        rf"### {re.escape(player_name)} \([^)]+\)[^\n]*\n",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return content

    # Find the next ### or ## after this player
    rest = content[match.end():]
    next_header = re.search(r"^###? ", rest, re.MULTILINE)
    if next_header:
        section_end = match.end() + next_header.start()
    else:
        section_end = len(content)

    # Strip trailing （fa_scan） if Claude already included it in summary
    summary = summary.rstrip()
    while summary.endswith("（fa_scan）"):
        summary = summary[:-len("（fa_scan）")].rstrip()
    new_line = f"- {short_date}：{summary}（fa_scan）\n"

    # Dedup: replace last same-date fa_scan line in this player's section
    section_start = match.end()
    section = content[section_start:section_end]
    same_date_re = re.compile(
        rf"^- {re.escape(short_date)}：[^\n]*（fa_scan）\n",
        re.MULTILINE,
    )
    matches = list(same_date_re.finditer(section))
    if matches:
        last = matches[-1]
        new_section = section[:last.start()] + new_line + section[last.end():]
        content = content[:section_start] + new_section + content[section_end:]
    else:
        # No same-date line yet → append at section end
        before = content[:section_end].rstrip("\n") + "\n"
        after = content[section_end:]
        content = before + new_line + "\n" + after
    return content


# ── Phase 5: Python compute layer (Layer 4) integration ──


def _prep_my_roster_for_compute(group_type, config, savant_2026, standings, rolling):
    """Build active-roster entries ready for fa_compute.pick_weakest/compute_urgency.

    Each entry carries 2026 Savant (+ bb_pct for batter), prior_stats from config,
    derived (ip_per_gs/ip_per_tg/era_diff for SP; bb_pct/pa_per_tg for batter),
    and rolling data keyed for its group (rolling_21d for SP, rolling_14d for
    batter).
    """
    if group_type == "batter":
        players = [p for p in config.get("batters", []) if is_active(p)]
        fa_type_key = "batter"
        stat_group = "hitting"
    else:
        players = [
            p for p in config.get("pitchers", [])
            if pitcher_type(p) == "SP" and is_active(p)
        ]
        fa_type_key = "sp"
        stat_group = "pitching"

    entries = []
    for p in players:
        mlb_id = p.get("mlb_id")
        if not mlb_id:
            continue
        savant = _extract_savant_by_id(mlb_id, fa_type_key, savant_2026)
        if not savant:
            # No 2026 Savant → cannot score; skip (matches build_roster_for_pass1).
            continue

        mlb_2026 = fetch_mlb_season_stats(mlb_id, 2026, stat_group)

        if group_type == "batter":
            derived = _compute_derived_batter(mlb_2026, standings, p["team"], 2026) or {}
            bb_pct = derived.get("bb_pct")
            if bb_pct is not None:
                savant = {**savant, "bb_pct": bb_pct}
        else:
            derived = _compute_derived_pitcher(
                savant, mlb_2026, standings, p["team"], 2026, "sp", mlb_id=mlb_id,
            ) or {}

        mid_str = str(mlb_id)
        rolling_data = rolling.get(mid_str) if rolling else None

        entry = {
            "name": p["name"],
            "mlb_id": mlb_id,
            "team": p["team"],
            "positions": p.get("positions", []),
            "selected_pos": p.get("selected_pos", ""),
            "status": p.get("status", ""),
            "savant_2026": savant,
            "prior_stats": p.get("prior_stats", {}) or {},
            "derived": derived,
            "mlb_2026": mlb_2026,
        }
        if group_type == "sp":
            entry["rolling_21d"] = rolling_data
        else:
            entry["rolling_14d"] = rolling_data
        entries.append(entry)
        time.sleep(0.2)  # MLB API rate limit

    return entries


def _normalize_fa_for_compute(p, group_type, fa_rolling):
    """Convert Layer 3 enriched FA dict → compute_fa_tags-ready entry."""
    savant = dict(p.get("savant_2026") or {})
    mlb_26 = p.get("mlb_2026") or {}

    if group_type == "batter":
        pa = int(mlb_26.get("plateAppearances", 0) or 0)
        bb = int(mlb_26.get("baseOnBalls", 0) or 0)
        if pa > 0 and savant.get("bb_pct") is None:
            savant["bb_pct"] = round(bb / pa * 100, 2)

    # Prior from savant_2025 + mlb_2025 (Layer 3 enrichment already fetched both)
    savant_25 = p.get("savant_2025") or {}
    mlb_25 = p.get("mlb_2025") or {}
    prior_stats = {}
    if group_type == "sp":
        if savant_25:
            prior_ip = 0.0
            if mlb_25:
                prior_ip = _parse_ip(mlb_25.get("inningsPitched", "0"))
            prior_stats = {
                "xera": savant_25.get("xera"),
                "xwoba_allowed": savant_25.get("xwoba"),
                "hh_pct_allowed": savant_25.get("hh_pct"),
                "ip": prior_ip,
            }
    else:
        if savant_25:
            prior_bb_pct = None
            if mlb_25:
                pa25 = int(mlb_25.get("plateAppearances", 0) or 0)
                bb25 = int(mlb_25.get("baseOnBalls", 0) or 0)
                if pa25 > 0:
                    prior_bb_pct = round(bb25 / pa25 * 100, 2)
            prior_stats = {
                "xwoba": savant_25.get("xwoba"),
                "bb_pct": prior_bb_pct,
                "barrel_pct": savant_25.get("barrel_pct"),
            }

    mid_str = str(p.get("mlb_id", ""))
    rolling_data = (fa_rolling or {}).get(mid_str)

    entry = {
        "name": p["name"],
        "mlb_id": p.get("mlb_id"),
        "team": p.get("team", ""),
        "position": p.get("position", ""),
        "pct": p.get("pct"),
        "waiver_date": p.get("waiver_date", ""),
        "savant_2026": savant,
        "prior_stats": prior_stats,
        "derived": p.get("derived_2026") or {},
    }
    if group_type == "sp":
        entry["rolling_21d"] = rolling_data
    else:
        entry["rolling_14d"] = rolling_data

    score, breakdown = fa_compute.compute_sum_score(savant, group_type)
    entry["score"] = score
    entry["breakdown"] = breakdown
    return entry


def _rolling_tag(rolling, season_savant, group_type):
    """Return e.g. '持平' / '🔥弱回升' / '❄️強劣化' for display in machine report."""
    if not rolling or not season_savant or season_savant.get("xwoba") is None:
        return "—"
    r_x = rolling.get("xwoba")
    if r_x is None:
        return "—"
    bbe_gate = 25 if group_type == "batter" else 20
    if (rolling.get("bbe") or 0) < bbe_gate:
        return "樣本不足"
    delta = r_x - season_savant["xwoba"]
    if group_type == "sp":
        if delta <= -0.050:
            return "🔥強回升"
        if delta <= -0.035:
            return "🔥弱回升"
        if delta >= 0.050:
            return "❄️強劣化"
        if delta >= 0.035:
            return "❄️弱劣化"
    else:
        if delta >= 0.050:
            return "🔥強回升"
        if delta >= 0.035:
            return "🔥弱回升"
        if delta <= -0.050:
            return "❄️強下滑"
        if delta <= -0.035:
            return "❄️弱下滑"
    return "持平"


def _format_fa_for_layer5(entry, group_type, idx):
    """Format one FA / watch entry as multi-line text for Claude Layer 5 input."""
    name = entry.get("name", "?")
    team = entry.get("team", "")
    pos = entry.get("position", "")
    pct = entry.get("pct")
    pct_str = f"{pct}%" if pct is not None else "?"
    decision = entry.get("decision", "?")
    sum_diff = entry.get("sum_diff", 0)
    bd_diff = entry.get("breakdown_diff", {})
    add_tags = entry.get("add_tags", [])
    warn_tags = entry.get("warn_tags", [])
    anchor = entry.get("anchor_name", "?")

    prefix = f"{idx}. " if idx is not None else "- "
    lines = [f"{prefix}**{name}**（{team}, {pos}）{pct_str} — {decision}"]

    if entry.get("win_gate_passed"):
        fa_sum = entry.get("score", 0)
        my_sum = fa_sum - sum_diff
        bd_str = " / ".join(
            f"{'+' if v >= 0 else ''}{v}" for v in bd_diff.values()
        )
        lines.append(
            f"   vs {anchor}：Sum {fa_sum} vs {my_sum} = 差 +{sum_diff}, breakdown {bd_str}"
        )
    else:
        lines.append(
            f"   win gate 未過 (Sum 差 {sum_diff}, 2 项正向不足) — 建議 pass"
        )

    tag_parts = list(add_tags) + list(warn_tags)
    if tag_parts:
        lines.append(f"   標籤：{' + '.join(tag_parts)}")

    sv = entry.get("savant_2026") or {}
    if group_type == "sp":
        d = entry.get("derived") or {}
        lines.append(
            f"   2026: xERA {sv.get('xera','?')} / xwOBA {sv.get('xwoba','?')} / "
            f"HH% {sv.get('hh_pct','?')} / BBE {sv.get('bbe',0)} / "
            f"IP/GS {d.get('ip_per_gs','?')} / IP/TG {d.get('ip_per_tg','?')} / "
            f"運氣 {d.get('era_diff','?')}"
        )
    else:
        bb = sv.get("bb_pct")
        lines.append(
            f"   2026: xwOBA {sv.get('xwoba','?')} / BB% {bb if bb is not None else '?'} / "
            f"Barrel% {sv.get('barrel_pct','?')} / HH% {sv.get('hh_pct','?')} / "
            f"BBE {sv.get('bbe',0)}"
        )

    prior = entry.get("prior_stats") or {}
    if prior:
        lines.append(f"   2025 prior: {json.dumps(prior, ensure_ascii=False)}")

    rolling = entry.get("rolling_21d") or entry.get("rolling_14d")
    if rolling:
        window = "21d" if group_type == "sp" else "14d"
        r_x = rolling.get("xwoba")
        delta = None
        if r_x is not None and sv.get("xwoba") is not None:
            delta = r_x - sv["xwoba"]
        delta_str = f" Δ{delta:+.3f}" if delta is not None else ""
        lines.append(
            f"   {window}: xwOBA {r_x}{delta_str} / HH% {rolling.get('hh_pct','?')} / "
            f"BBE {rolling.get('bbe',0)}"
        )

    return lines


def _filter_waiver_log_by_group(section_content, group_type, rostered_names=None):
    """Split waiver-log 觀察中 section into per-player entries and keep only
    those matching group_type ('batter' or 'sp') AND not already rostered.

    Entry format: `### 球員名 (TEAM, POSITIONS) [mlb_id:XXX] — 觀察中`
    POSITIONS examples: "SP", "RP", "SP,RP" (pitcher) vs "C", "1B,3B" (batter).

    rostered_names: set of player names already rostered by some team. These
    entries are dropped from Claude's view even though they still live in
    waiver-log.md (snapshot-only cron at TW 15:15 will auto-close them).
    Without this filter, Claude sees them and writes stale 結案 suggestions.
    """
    rostered = rostered_names or set()
    entries = re.split(r"(?=^### )", section_content, flags=re.MULTILINE)
    kept = []
    for entry in entries:
        if not entry.startswith("### "):
            kept.append(entry)  # Preamble before first ### header
            continue
        m = re.match(r"### ([^(]+)\(([A-Z]+),\s*([^)]+)\)", entry)
        if not m:
            continue  # Malformed header, skip defensively
        name = m.group(1).strip()
        positions = m.group(3).strip()
        if name in rostered:
            continue  # Already rostered — snapshot cron will auto-close
        is_pitcher = "SP" in positions or "RP" in positions
        if group_type == "sp" and is_pitcher:
            kept.append(entry)
        elif group_type == "batter" and not is_pitcher:
            kept.append(entry)
    return "".join(kept)


def _build_pass2_data_v2(group_type, urgency_result, low_conf, fa_tagged,
                         watch_tagged, changes, ref_1d, ref_3d, config,
                         rostered_names=None):
    """Build Claude Layer 5 input string: mechanical report + context.

    Claude task is to text-ify the pre-computed Sum/urgency/tags/decision and
    flag edge cases — NOT to re-compute rules.
    """
    lines = []
    label = "打者" if group_type == "batter" else "SP"
    window = "14d" if group_type == "batter" else "21d"
    factor_tg_label = "PA/TG" if group_type == "batter" else "IP/TG"
    factor_tg_key = "pa_per_tg" if group_type == "batter" else "ip_per_tg"

    # ── 機械報告：我方最弱 ──
    lines.append(f"--- 我方最弱{label}（機械報告，Sum/urgency/決策已算）---")
    ranked = urgency_result.get("weakest_ranked", [])
    for i, r in enumerate(ranked, start=1):
        factors = r.get("factors", {})
        f26 = factors.get("sum_2026", 0)
        f25 = factors.get("sum_2025", 0)
        f_roll = factors.get("rolling", 0)
        f_tg = factors.get(factor_tg_key, 0)
        prior_sum = r.get("prior_sum", 0)
        prior_ip = r.get("prior_ip")
        prior_ip_str = f", {prior_ip:.1f}IP" if prior_ip is not None else ""

        season_savant = r.get("savant_2026") or {}
        rolling = r.get("rolling_21d") or r.get("rolling_14d")
        roll_tag = _rolling_tag(rolling, season_savant, group_type)

        tg_val = (r.get("derived") or {}).get(factor_tg_key)
        tg_str = f"{tg_val:.2f}" if isinstance(tg_val, (int, float)) else "?"

        sign_roll = "+" if f_roll >= 0 else ""
        sign_tg = "+" if f_tg >= 0 else ""
        lines.append(
            f"- **P{i} {r['name']}** urgency {r['urgency']}："
            f"2026 Sum {r.get('score', 0)}(+{f26}) / "
            f"2025 Sum {prior_sum}(+{f25}{prior_ip_str}) / "
            f"{window} {roll_tag}({sign_roll}{f_roll}) / "
            f"{factor_tg_label} {tg_str}({sign_tg}{f_tg})"
        )

        # Supplementary data for Claude's 定性 writing
        sv = season_savant
        if group_type == "sp":
            lines.append(
                f"    2026 Savant: xERA {sv.get('xera','?')} / xwOBA {sv.get('xwoba','?')} / "
                f"HH% {sv.get('hh_pct','?')} / BBE {sv.get('bbe',0)}"
            )
            d = r.get("derived") or {}
            lines.append(
                f"    產量: IP/GS {d.get('ip_per_gs','?')} / IP/TG {d.get('ip_per_tg','?')} "
                f"/ 運氣 {d.get('era_diff','?')}"
            )
        else:
            lines.append(
                f"    2026 Savant: xwOBA {sv.get('xwoba','?')} / BB% {sv.get('bb_pct','?')} / "
                f"Barrel% {sv.get('barrel_pct','?')} / HH% {sv.get('hh_pct','?')} / "
                f"BBE {sv.get('bbe',0)}"
            )
        prior = r.get("prior_stats") or {}
        if prior:
            lines.append(f"    2025 prior: {json.dumps(prior, ensure_ascii=False)}")
        for n in r.get("notes") or []:
            lines.append(f"    ⚠️ {n}")

    # Slump hold — SP shows IP gate (≥_PRIOR_IP_SLUMP_HOLD_MIN), batter has no IP gate
    for s in urgency_result.get("slump_hold", []):
        if group_type == "sp":
            ip_str = f"{s['prior_ip']:.1f}IP" if s.get("prior_ip") is not None else "?"
            gate_str = f"（{ip_str} ≥{fa_compute._PRIOR_IP_SLUMP_HOLD_MIN}）"
        else:
            gate_str = ""  # Batter: no IP gate per CLAUDE.md Step 2 rules
        lines.append(
            f"- **Slump hold {s['name']}**：2025 Sum {s['prior_sum']} ≥24 菁英底{gate_str} — 2026 表現低，等回歸"
        )
        prior = s.get("prior_stats")
        if prior:
            lines.append(f"    2025 prior: {json.dumps(prior, ensure_ascii=False)}")

    # Low-confidence excluded (SP only)
    for lc in low_conf:
        lines.append(
            f"- **低信心排除 {lc['name']}**：BBE {lc['bbe']} 驗證期，暫不排序"
        )

    # ── 機械報告：FA 候選 ──
    if fa_tagged:
        lines.append(f"\n--- FA {label}候選（機械報告，已算好決策）---")
        decision_order = {"立即取代": 0, "取代": 1, "觀察": 2, "pass": 3}
        fa_sorted = sorted(
            fa_tagged,
            key=lambda x: (decision_order.get(x.get("decision", "pass"), 9),
                           -x.get("sum_diff", 0)),
        )
        for idx, f in enumerate(fa_sorted, start=1):
            lines.extend(_format_fa_for_layer5(f, group_type, idx))
    else:
        lines.append(f"\n--- FA {label}候選: 無 ---")

    # ── 觀察中 watch ──
    if watch_tagged:
        lines.append(f"\n--- waiver-log 觀察中{label}（含機械決策 + 當前數據）---")
        for w in watch_tagged:
            lines.extend(_format_fa_for_layer5(w, group_type, None))

    # ── %owned 升幅 ──
    group_changes = [
        c for c in changes
        if _classify_fa_type(c.get("position", "")) == group_type
        and c.get("d3") is not None and c["d3"] > 0
    ]
    group_changes.sort(key=lambda x: x["d3"], reverse=True)
    if group_changes:
        lines.append(f"\n--- %owned 升幅 ({label}, 3 日) ---")
        for c in group_changes[:10]:
            lines.append(f"  {c['name']:20} 3d:+{c['d3']:>3} {c['pct']:>3}%  {c['position']}")

    # ── waiver-log 觀察中（觸發條件，按 group_type 過濾） ──
    # Filter by position in the entry header: pitcher (SP/RP) vs batter (C/1B/…).
    # Without filtering, Claude sees ALL watch entries and flags batter-type
    # players in SP 觀察中更新 section (and vice versa).
    waiver_log_path = os.path.join(SCRIPT_DIR, "..", "waiver-log.md")
    if os.path.exists(waiver_log_path):
        with open(waiver_log_path, encoding="utf-8") as f:
            wl_content = f.read()
        if "## 觀察中" in wl_content:
            section = wl_content.split("## 觀察中")[1]
            if "## 已結案" in section:
                section = section.split("## 已結案")[0]
            filtered = _filter_waiver_log_by_group(section, group_type, rostered_names)
            if filtered.strip():
                lines.append(f"\n--- waiver-log 觀察中（含觸發條件，僅 {label}）---\n## 觀察中{filtered}")

    return "\n".join(lines)


def _build_rp_data(enriched_rps, my_rps_str, config):
    """Build data string for RP mode Claude prompt."""
    lines = []

    framework = _extract_eval_framework()
    if framework:
        lines.append(f"--- 評估框架（from CLAUDE.md）---\n{framework}\n")

    lines.append(f"--- 我方 RP ---\n{my_rps_str}\n")

    if enriched_rps:
        lines.append(f"--- FA RP 候選 ({len(enriched_rps)} 人) ---")
        for p in enriched_rps:
            lines.append(_format_fa_pitcher(p))
    else:
        lines.append("--- FA RP 候選: 無 ---")

    return "\n".join(lines)


# ── Mode implementations ──


def _run_snapshot_only(access_token, config, today_str, env):
    """Save %owned snapshot + cleanup rostered watchlist."""
    print(f"[FA Scan] Snapshot-only {today_str}...", file=sys.stderr)
    snapshot = collect_fa_snapshot(access_token, config, queries=SCAN_QUERIES)
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

        _publish(today_str, "RP", advice, advice, data, env, args)

    except Exception as e:
        _handle_error("RP scan", e, env, args)


def _process_group(group_type, config, savant_2026, enriched, watch_enriched,
                   changes, ref_1d, ref_3d, today_str, env, args,
                   rostered_names=None):
    """Process one group (batter or SP) via Python compute layer + Claude text layer.

    Pipeline (Phase 5):
        Layer 1.5: filter pure RP from FA/watch (SP only)
        Layer 4:   fa_compute.pick_weakest + compute_urgency + compute_fa_tags
        Layer 5:   Claude writes 定性 reason + watch change detection
    """
    label = "打者" if group_type == "batter" else "SP"
    try:
        fa_candidates = [p for p in enriched if p["fa_type"] == group_type]
        watch_candidates = [p for p in watch_enriched if p["fa_type"] == group_type]

        # Layer 1.5: pure RP filter — drop SP,RP dual-eligible players whose
        # 2026 starts average <3.0 IP (opener / swingman-heavy role).
        # Uses game-log (GS=1 only) IP/GS, not naive total-IP/GS which
        # inflates for RPs with 1-2 token starts (e.g. Bernardino 10.3 IP
        # total / 1 GS = naive 10.3 IP/GS, but actual start was 0.7 IP).
        if group_type == "sp":
            def _is_real_sp(p):
                mlb = p.get("mlb_2026") or {}
                gs = int(mlb.get("gamesStarted", 0) or 0)
                if gs == 0:
                    return False
                mlb_id = p.get("mlb_id")
                if not mlb_id:
                    return False  # no ID — can't verify, exclude safely
                ip_per_gs = _ip_per_gs_from_gamelog(mlb_id, 2026)
                if ip_per_gs is None:
                    return False  # API fail / no GS=1 splits — exclude
                return ip_per_gs >= 3.0
            before = len(fa_candidates) + len(watch_candidates)
            fa_candidates = [p for p in fa_candidates if _is_real_sp(p)]
            watch_candidates = [p for p in watch_candidates if _is_real_sp(p)]
            removed = before - len(fa_candidates) - len(watch_candidates)
            if removed:
                print(f"  Layer 1.5 ({label}): {removed} pure RP removed (GS=0 or game-log IP/GS<3.0)",
                      file=sys.stderr)

        # ── Layer 4: Python compute (Sum / urgency / FA tags) ──
        print(f"  Layer 4 ({label}): computing weakest + urgency...", file=sys.stderr)
        standings = _fetch_team_games()
        rolling = _load_savant_rolling(player_type=group_type)
        my_roster = _prep_my_roster_for_compute(
            group_type, config, savant_2026, standings, rolling,
        )
        cant_cut = set(config.get("league", {}).get("cant_cut", []))
        weakest, low_conf = fa_compute.pick_weakest(
            my_roster, group_type, n=4, cant_cut=cant_cut,
        )
        urgency_result = fa_compute.compute_urgency(weakest, group_type)

        if not fa_candidates and not watch_candidates:
            _notify(env, args, f"[FA Scan {label}] 無候選通過品質門檻，waiver-log 無 watch")
            return

        # FA rolling for compute_fa_tags recency evaluation
        fa_rolling_type = "batter" if group_type == "batter" else "pitcher"
        fa_rolling = _fetch_fa_rolling(
            fa_candidates, watch_candidates, today_str, player_type=fa_rolling_type,
        )

        # Anchor for FA tag comparison — P1 in urgency rank (fallback: first slump hold)
        anchor = None
        if urgency_result["weakest_ranked"]:
            anchor = urgency_result["weakest_ranked"][0]
        elif urgency_result.get("slump_hold"):
            sh = urgency_result["slump_hold"][0]
            anchor = {
                "name": sh["name"],
                "score": sh.get("sum_2026", 0),
                "breakdown": sh.get("prior_breakdown", {}),
                "savant_2026": sh.get("savant_2026") or {},
            }

        fa_tagged = []
        for p in fa_candidates:
            entry = _normalize_fa_for_compute(p, group_type, fa_rolling)
            if anchor is None:
                entry.update({
                    "sum_diff": 0, "breakdown_diff": {},
                    "win_gate_passed": False, "add_tags": [], "warn_tags": [],
                    "decision": "pass", "anchor_name": "—",
                })
            else:
                entry.update(fa_compute.compute_fa_tags(entry, anchor, group_type))
            fa_tagged.append(entry)

        watch_tagged = []
        for p in watch_candidates:
            entry = _normalize_fa_for_compute(p, group_type, fa_rolling)
            if anchor is None:
                entry.update({
                    "sum_diff": 0, "breakdown_diff": {},
                    "win_gate_passed": False, "add_tags": [], "warn_tags": [],
                    "decision": "pass", "anchor_name": "—",
                })
            else:
                entry.update(fa_compute.compute_fa_tags(entry, anchor, group_type))
            watch_tagged.append(entry)

        # ── Layer 5: Claude text layer ──
        print(f"  Layer 5 ({label}): Claude 文字化...", file=sys.stderr)
        prompt_file = f"prompt_fa_scan_pass2_{'batter' if group_type == 'batter' else 'sp'}.txt"
        prompt_path = os.path.join(SCRIPT_DIR, prompt_file)

        data = _build_pass2_data_v2(
            group_type, urgency_result, low_conf, fa_tagged, watch_tagged,
            changes, ref_1d, ref_3d, config,
            rostered_names=rostered_names,
        )
        advice = _call_claude(prompt_path, data, timeout=900)

        # Telegram: strip waiver-log + pass section + delimiter markers
        advice_display = re.sub(r"```waiver-log.*?```", "", advice, flags=re.DOTALL)
        advice_display = re.sub(r"--- PASS ---.*?--- END_PASS ---", "", advice_display, flags=re.DOTALL)
        advice_display = re.sub(r"--- (?:ACTION|END_ACTION) ---", "", advice_display)
        advice_display = advice_display.strip()

        # Issue: strip waiver-log + delimiter markers, keep pass section
        advice_issue = re.sub(r"```waiver-log.*?```", "", advice, flags=re.DOTALL)
        advice_issue = re.sub(r"--- (?:ACTION|END_ACTION|PASS|END_PASS) ---", "", advice_issue)
        advice_issue = advice_issue.strip()

        # Full raw dump for Issue archive (machine report + Claude output)
        full_raw = (
            f"=== Layer 4 Mechanical Report ({label}) ===\n{data}\n\n"
            f"=== Layer 5 Claude Output ({label}) ===\n{advice}"
        )
        _publish(today_str, label, advice_display, advice_issue, full_raw, env, args)

        _update_waiver_log(advice, today_str, env)

    except Exception as e:
        _handle_error(f"{label} scan", e, env, args)


def _process_group_sp_v4(config, savant_2026, enriched, watch_enriched,
                         changes, ref_1d, ref_3d, today_str, env, args,
                         rostered_names=None):
    """Phase 6 multi-agent v4 SP path. Thin dispatcher to _phase6_sp.process_sp_v4.

    Activated via env flag SP_FRAMEWORK_VERSION=v4. Default v2 path
    (_process_group("sp", ...)) is unchanged. See docs/v4-cutover-plan.md
    Stage D and docs/fa_scan-claude-decision-layer-design.md §4.
    """
    from _phase6_sp import process_sp_v4

    helpers = {
        "notify": _notify,
        "handle_error": _handle_error,
        "publish": _publish,
        "update_waiver_log": _update_waiver_log,
        "prep_my_roster": _prep_my_roster_for_compute,
        "normalize_fa_for_compute": _normalize_fa_for_compute,
        "fetch_team_games": _fetch_team_games,
        "load_savant_rolling": _load_savant_rolling,
        "fetch_fa_rolling": _fetch_fa_rolling,
        "ip_per_gs_from_gamelog": _ip_per_gs_from_gamelog,
    }
    process_sp_v4(
        config, savant_2026, enriched, watch_enriched,
        changes, ref_1d, ref_3d, today_str, env, args,
        rostered_names=rostered_names,
        fa_scan_helpers=helpers,
    )


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

    # Filter out watchlist players already rostered (no longer FA)
    league_key = config["league"]["league_key"]
    still_fa = []
    rostered_names = set()
    print(f"  Ownership check: {len(watchlist)} watch players...", file=sys.stderr)
    for w in watchlist:
        try:
            ownership = _check_player_ownership(
                w["name"], league_key, access_token,
                expected_team=w.get("team"))
            if ownership == "team":
                print(f"  Watch skip (rostered): {w['name']} ({w.get('team','?')})", file=sys.stderr)
                rostered_names.add(w["name"])
            else:
                still_fa.append(w)
        except Exception as e:
            print(f"  Ownership check failed for {w['name']}: {e}", file=sys.stderr)
            still_fa.append(w)  # keep on error to avoid false removal
        time.sleep(0.5)
    watchlist = still_fa

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

    # ── Process Batter + SP in parallel ──
    # Both groups share read-only snapshot data (savant_2026, enriched,
    # watch_enriched); _process_group filters by fa_type so there is no write
    # contention on those structures. Claude subprocess + MLB API are IO-bound
    # so threading (no GIL blocking) halves wall-clock time.
    #
    # Waiver-log git operations are serialized inside _update_waiver_log via
    # _WAIVER_LOG_LOCK to avoid working-tree race conditions.
    threads = []
    errors = []
    error_lock = threading.Lock()

    sp_framework = os.environ.get("SP_FRAMEWORK_VERSION", "v2")

    def _run_group_thread(group_type):
        try:
            if group_type == "sp" and sp_framework == "v4":
                _process_group_sp_v4(
                    config, savant_2026, enriched, watch_enriched,
                    changes, ref_1d, ref_3d, today_str, env, args,
                    rostered_names=rostered_names,
                )
            else:
                _process_group(
                    group_type, config, savant_2026, enriched, watch_enriched,
                    changes, ref_1d, ref_3d, today_str, env, args,
                    rostered_names=rostered_names,
                )
        except Exception as e:
            with error_lock:
                errors.append((group_type, e))

    if not args.sp_only:
        threads.append(threading.Thread(
            target=_run_group_thread, args=("batter",), name="fa_scan-batter",
        ))
    if not args.batter_only:
        sp_label = "sp-v4" if sp_framework == "v4" else "sp"
        threads.append(threading.Thread(
            target=_run_group_thread, args=("sp",), name=f"fa_scan-{sp_label}",
        ))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for group_type, err in errors:
        _handle_error(f"{group_type} scan", err, env, args)


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="FA Scan — unified FA market analysis")
    parser.add_argument("--rp", action="store_true", help="RP scan mode (weekly, Monday)")
    parser.add_argument("--snapshot-only", action="store_true", help="Only save %owned snapshot")
    parser.add_argument("--cleanup", action="store_true", help="Clean rostered watchlist players")
    parser.add_argument("--dry-run", action="store_true", help="Layer 1+2 only, skip Claude")
    parser.add_argument("--no-send", action="store_true", help="Skip Telegram + GitHub Issue")
    parser.add_argument("--no-issue", action="store_true",
                        help="Skip GitHub Issue creation only (Telegram still sends; for Stage E parallel)")
    parser.add_argument("--no-waiver-log", action="store_true",
                        help="Skip waiver-log.md updates (for Stage E parallel)")
    parser.add_argument("--sp-only", action="store_true", help="Skip batter group (SP smoke test)")
    parser.add_argument("--batter-only", action="store_true", help="Skip SP group")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
