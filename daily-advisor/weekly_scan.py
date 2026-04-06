"""Weekly Deep Scan — FA market analysis with Statcast quality filter."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from yahoo_query import (
    refresh_token, load_env, load_config,
    send_telegram, _normalize,
)
from fa_watch import (
    collect_fa_snapshot, load_fa_history, save_fa_history,
    calc_owned_changes, TPE,
)
from main import pctile_tag
from roster_sync import (
    _download_savant_csv, _find_id_column, _extract_savant_row,
    search_mlb_id, fetch_mlb_season_stats, mlb_api_get, _parse_ip,
)

SUMMARY_FILE = os.path.join(SCRIPT_DIR, "weekly_scan_summary.txt")
FULL_SEASON_GAMES = 162

# ── Layer 1: Yahoo FA queries (6 calls) ──

WEEKLY_FA_QUERIES = [
    ("B-AR",  "status=A;position=B;sort=AR;count=50"),
    ("SP-AR", "status=A;position=SP;sort=AR;count=30"),
    ("RP-AR", "status=A;position=RP;sort=AR;count=20"),
    ("B-LW",  "status=A;position=B;sort=AR;sort_type=lastweek;count=30"),
    ("SP-LW", "status=A;position=SP;sort=AR;sort_type=lastweek;count=20"),
    ("RP-LW", "status=A;position=RP;sort=AR;sort_type=lastweek;count=10"),
]

# ── Layer 2: Quality thresholds ──

BATTER_THRESHOLDS = [
    ("xwoba", 0.286, True),       # P40
    ("bb_pct", 7.0, True),        # P40
    ("barrel_pct", 6.5, True),    # P40
]
SP_THRESHOLDS = [
    ("xera", 4.64, False),        # P40
    ("xwoba", 0.332, False),      # P40 (xwOBA allowed)
    ("hh_pct", 42.2, False),      # P40
]
RP_THRESHOLDS = [
    ("xera", 4.33, False),        # P50
    ("xwoba", 0.322, False),      # P50
    ("hh_pct", 40.8, False),      # P50
]


# ── Savant CSV utilities ──


def download_savant_csvs(year):
    """Download 4 Savant CSVs for a year. Returns dict of (name_idx, id_idx)."""
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
    """Count how many of 3 threshold conditions pass."""
    passed = 0
    for metric, threshold, higher_better in thresholds:
        val = metrics.get(metric)
        if val is None:
            continue
        if (higher_better and val >= threshold) or (not higher_better and val <= threshold):
            passed += 1
    return passed


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
                continue  # No Savant data at all → skip
        else:
            matched += 1

        # Build metrics (0 → None: _extract_savant_row defaults missing to 0)
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

        thresholds = (
            BATTER_THRESHOLDS if fa_type == "batter"
            else SP_THRESHOLDS if fa_type == "sp"
            else RP_THRESHOLDS
        )

        if _check_thresholds(metrics, thresholds) < 2:
            continue  # Doesn't meet 2026 quality threshold

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

    print(f"  Layer 2: {total} FA → {matched} name-matched + {fallback} fallback "
          f"→ {len(results)} passed", file=sys.stderr)
    return results


# ── Layer 3: Enrichment ──


def _fetch_team_games():
    """Fetch 2026 gamesPlayed for all 30 teams. Returns abbr→games."""
    try:
        data = mlb_api_get("/standings?leagueId=103,104&season=2026")
        result = {}
        for record in data.get("records", []):
            for entry in record.get("teamRecords", []):
                abbr = entry["team"].get("abbreviation", "")
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


def _compute_derived_pitcher(savant, mlb_stats, team_games, team, year, fa_type):
    """Compute ERA, IP/GS, K/9, IP/TG, |xERA-ERA| for SP or RP."""
    if not mlb_stats:
        return {}
    ip = _parse_ip(mlb_stats.get("inningsPitched", "0"))
    era_str = mlb_stats.get("era", "0")
    era = float(era_str) if era_str not in ("—", "-", "", "-.--") else None
    d = {"era": era, "ip": round(ip, 1)}

    xera = savant.get("xera") if savant else None
    if xera is not None and xera > 0 and era is not None:
        diff = abs(xera - era)
        d["era_diff"] = round(diff, 2)
        if era < xera:
            d["era_diff_dir"] = "運氣好↑"
        elif era > xera:
            d["era_diff_dir"] = "運氣差↓"

    if fa_type == "sp":
        gs = int(mlb_stats.get("gamesStarted", 0))
        d["ip_per_gs"] = round(ip / gs, 1) if gs > 0 else None
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
            _compute_derived_pitcher(s26, p["mlb_2026"], standings, team, 2026, fa_type)
        )
        if savant_prior:
            p["derived_2025"] = (
                _compute_derived_batter(p["mlb_2025"], standings, team, 2025)
                if fa_type == "batter" else
                _compute_derived_pitcher(s25, p["mlb_2025"], standings, team, 2025, fa_type)
            )
        else:
            p["derived_2025"] = {}

        enriched.append(p)
        time.sleep(0.2)  # MLB API rate limit

    print(f"  Layer 3: {len(filtered)} → {len(enriched)} enriched", file=sys.stderr)
    return enriched


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


def _format_fa_batter(p):
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


def _format_fa_pitcher(p):
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
        tag = pctile_tag(d26["era_diff"], "era_diff", pt)
        aux.append(f"{d26.get('era_diff_dir', '')} {d26['era_diff']:.2f} {tag}".strip())
    if aux:
        lines.append(f"    輔助: {' | '.join(aux)}")

    # Volume
    if fa_type == "sp":
        ipgs = d26.get("ip_per_gs")
        if ipgs is not None:
            tier = " [深投]" if ipgs > 5.7 else (" [短局]" if ipgs < 5.3 else "")
            lines.append(f"    產量: IP/GS {ipgs:.1f}{tier}")
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


def save_github_issue(today_str, data_summary, advice):
    repo = "huansbox/mlb-fantasy"
    title = f"[Weekly Scan] {today_str}"
    body = f"""## Analysis

{advice}

---

<details>
<summary>Raw Data</summary>

```
{data_summary}
```

</details>
"""
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", repo,
             "--title", title, "--body", body,
             "--label", "waiver-scan"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode == 0:
            print(f"Issue created: {result.stdout.strip()}", file=sys.stderr)
        else:
            print(f"GitHub Issue error: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"GitHub Issue failed: {e}", file=sys.stderr)


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Weekly Deep Scan with Statcast")
    parser.add_argument("--dry-run", action="store_true",
                        help="Layer 1+2 only, print filtered results")
    parser.add_argument("--no-send", action="store_true",
                        help="Full pipeline but skip Telegram + GitHub Issue")
    parser.add_argument("--date", help="Override date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()

    try:
        access_token = refresh_token(env)
        config = load_config()
        today_str = args.date or datetime.now(TPE).strftime("%Y-%m-%d")

        print(f"[Weekly Scan] {today_str}...", file=sys.stderr)

        # ── Layer 1: Yahoo FA snapshot ──
        print("  Layer 1: Yahoo FA queries...", file=sys.stderr)
        snapshot = collect_fa_snapshot(access_token, config, queries=WEEKLY_FA_QUERIES)

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

        # ── Layer 2: Savant 2026 quality filter ──
        print("  Layer 2: Savant quality filter...", file=sys.stderr)
        savant_2026 = download_savant_csvs(2026)
        filtered = filter_by_savant(snapshot, savant_2026)

        if args.dry_run:
            print(f"\n=== Layer 2 Results ({len(filtered)} passed) ===\n")
            for p in filtered:
                s = p.get("savant_2026") or {}
                xw = f"{s['xwoba']:.3f}" if s.get("xwoba") is not None else "—"
                xe = f"{s['xera']:.2f}" if s.get("xera") is not None else "—"
                print(f"  {p['name']:22} {p['team']:5} {p['fa_type']:6} "
                      f"BBE={p['bbe']:>3}  xwOBA={xw:>6}  xERA={xe:>5}")
            print(f"\n{build_roster_summary(config, savant_2026)}")
            return

        # ── Layer 3: Precise enrichment ──
        print("  Layer 3: Precise data enrichment...", file=sys.stderr)
        enriched = enrich_layer3(filtered, savant_2026, config)

        # Attach %owned changes
        changes_by_name = {c["name"]: c for c in changes}
        for p in enriched:
            c = changes_by_name.get(p["name"], {})
            p["d1"] = c.get("d1")
            p["d3"] = c.get("d3")

        # Build data for Claude
        roster_summary = build_roster_summary(config, savant_2026)
        data_summary = build_weekly_data(
            today_str, enriched, changes, ref_1d, ref_3d, roster_summary, config
        )

        # Call Claude
        prompt_path = os.path.join(SCRIPT_DIR, "prompt_weekly_scan.txt")
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
        full_prompt = f"{prompt}\n\n---\n\n{data_summary}"
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        if result.returncode != 0:
            print(f"claude -p error: {result.stderr}", file=sys.stderr)
            print("\n--- Raw data ---")
            print(data_summary)
            return
        advice = result.stdout.strip()
        print(advice)

        save_summary(advice)

        # Weekly review reminder
        try:
            from weekly_review import load_config as wr_load_config, get_fantasy_week
            wr_config = wr_load_config()
            today_et = datetime.now(ZoneInfo("America/New_York")).date()
            _, _, wn = get_fantasy_week(today_et, wr_config)
            advice += f"\n\n---\n Week {wn} 覆盤資料已備好，開 session 跑 /weekly-review"
        except Exception as e:
            print(f"Weekly review reminder failed (skipping): {e}", file=sys.stderr)

        if args.no_send:
            return

        save_github_issue(today_str, data_summary, advice)

        print("Sending to Telegram...", file=sys.stderr)
        ok = send_telegram(advice, env)
        print("Sent." if ok else "Failed.", file=sys.stderr)

    except Exception as e:
        print(f"Weekly Scan error: {e}", file=sys.stderr)
        try:
            send_telegram(f"Weekly Scan failed: {e}", env)
        except Exception:
            pass


if __name__ == "__main__":
    main()
