"""fa_scan_v4 — SP v4 framework analysis tool (parallel to production fa_scan).

Pulls live data from Savant + MLB Stats API, computes v4 Sum (5-slot balanced
scoring), applies rotation gate pre-filter, and produces a ranking + FA upgrade
recommendation report.

Usage:
    python fa_scan_v4.py                          # team SPs + hard-coded FA watch list
    python fa_scan_v4.py --fa 668964,607200,...   # custom FA IDs

Does NOT send to Telegram (stdout only) and does NOT modify waiver-log.
Coexists with production fa_scan.py (v2) which handles daily cron.

See docs/sp-framework-v4-balanced.md for framework rationale.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request

from fa_compute import (
    PITCHER_V4_PCTILES,
    compute_sum_score_v4_sp,
    rotation_gate_v4,
    luck_tag_v4,
    v4_add_tags_sp,
    v4_warn_tags_sp,
    v4_decision_sp,
)


MLB_API = "https://statsapi.mlb.com/api/v1"
YEAR_DEFAULT = 2026


def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8-sig")


def safe_float(v, default=None):
    if v in (None, "", "null", "None", "-", "--", "-.--"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def safe_int(v, default=0):
    if v in (None, "", "null", "None"):
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


# ── Data fetch ──

def fetch_savant_custom(year: int) -> dict:
    """Returns {pid: {xwoba_allowed, xwobacon, xera, era}}."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=pitcher&filter=&min=1"
        "&selections=pa,bip,xwoba,xwobacon,xera,era&csv=true"
    )
    text = fetch_url(url)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        out[pid] = {
            "xwoba_allowed": safe_float(row.get("xwoba")),
            "xwobacon": safe_float(row.get("xwobacon")),
            "xera": safe_float(row.get("xera")),
            "era": safe_float(row.get("era")),
        }
    return out


def fetch_savant_batted_ball(year: int) -> dict:
    """Returns {pid: {bbe, gb_pct}}."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/batted-ball"
        f"?year={year}&type=pitcher&min=1&csv=true"
    )
    text = fetch_url(url)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("id"), 0)
        if not pid:
            continue
        bbe = safe_int(row.get("bbe"), 0)
        gb_rate = safe_float(row.get("gb_rate"))
        out[pid] = {
            "bbe": bbe,
            "gb_pct": gb_rate * 100 if gb_rate is not None else None,
        }
    return out


def fetch_savant_arsenal_whiff(year: int) -> dict:
    """Returns {pid: {whiff_pct, arsenal_pitches}} weighted by pitch usage."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
        f"?type=pitcher&year={year}&min=1&csv=true"
    )
    text = fetch_url(url)
    agg = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        pitches = safe_int(row.get("pitches"), 0)
        whiff = safe_float(row.get("whiff_percent"))
        if not pitches or whiff is None:
            continue
        if pid not in agg:
            agg[pid] = {"pitches": 0, "wsum": 0.0}
        agg[pid]["pitches"] += pitches
        agg[pid]["wsum"] += whiff * pitches
    return {
        pid: {
            "whiff_pct": a["wsum"] / a["pitches"],
            "arsenal_pitches": a["pitches"],
        }
        for pid, a in agg.items()
        if a["pitches"] > 0
    }


def fetch_mlb_season_stats(pitcher_ids, year: int) -> dict:
    """Returns {pid: {g, gs, ip, ip_gs, bb9, era, whip, qs, k}}.

    Batches 50 per call via /people?personIds=...
    """
    out = {}
    ids = list(pitcher_ids)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        id_str = ",".join(str(x) for x in batch)
        url = (
            f"{MLB_API}/people?personIds={id_str}"
            f"&hydrate=stats(group=[pitching],type=[season],season={year})"
        )
        try:
            data = json.loads(fetch_url(url, timeout=30))
            for person in data.get("people", []):
                pid = person.get("id")
                for sg in person.get("stats", []):
                    splits = sg.get("splits", [])
                    if not splits:
                        continue
                    stat = splits[0].get("stat", {})
                    g = int(stat.get("gamesPlayed", 0))
                    gs = int(stat.get("gamesStarted", 0))
                    ip_str = stat.get("inningsPitched", "0.0")
                    ip_val = safe_float(ip_str, 0.0)
                    ip_real = int(ip_val) + (ip_val - int(ip_val)) * 10 / 3
                    bb = safe_int(stat.get("baseOnBalls"), 0)
                    k = safe_int(stat.get("strikeOuts"), 0)
                    out[pid] = {
                        "g": g, "gs": gs, "ip": ip_real, "bb": bb, "k": k,
                        "ip_gs": ip_real / gs if gs else 0,
                        "bb9": 9 * bb / ip_real if ip_real else 0,
                        "k9": 9 * k / ip_real if ip_real else 0,
                        "era": safe_float(stat.get("era")),
                        "whip": safe_float(stat.get("whip")),
                    }
                    break
        except Exception as e:
            print(f"[warn] MLB API batch {i} failed: {e}", file=sys.stderr)
    return out


def assemble_data(pitcher_ids, year: int) -> dict:
    """Pull all data + merge into per-pitcher dict with v4 fields."""
    print(f"Fetching Savant custom (xwOBA/xwOBACON/xERA)...", file=sys.stderr)
    custom = fetch_savant_custom(year)
    print(f"Fetching Savant batted-ball (GB%)...", file=sys.stderr)
    bb_ball = fetch_savant_batted_ball(year)
    print(f"Fetching Savant pitch-arsenal (Whiff%)...", file=sys.stderr)
    arsenal = fetch_savant_arsenal_whiff(year)
    print(f"Fetching MLB Stats API season stats...", file=sys.stderr)
    mlb = fetch_mlb_season_stats(pitcher_ids, year)

    merged = {}
    for pid in pitcher_ids:
        c = custom.get(pid, {})
        b = bb_ball.get(pid, {})
        a = arsenal.get(pid, {})
        m = mlb.get(pid, {})
        merged[pid] = {
            # v4 Sum inputs
            "ip_gs": m.get("ip_gs"),
            "whiff_pct": a.get("whiff_pct"),
            "bb9": m.get("bb9"),
            "gb_pct": b.get("gb_pct"),
            "xwobacon": c.get("xwobacon"),
            # Gate + luck + context
            "g": m.get("g", 0),
            "gs": m.get("gs", 0),
            "ip": m.get("ip", 0),
            "bbe": b.get("bbe", 0),
            "xera": c.get("xera"),
            # ERA: MLB API is authoritative; Savant custom's era column is empty
            # when passed through `selections` params
            "era": m.get("era"),
            "xwoba_allowed": c.get("xwoba_allowed"),
            "k9": m.get("k9"),
            "whip": m.get("whip"),
            "arsenal_pitches": a.get("arsenal_pitches", 0),
        }
    return merged


# ── Report ──

def analyze_pitcher(name: str, pid: int, data: dict) -> dict:
    """Run v4 computations on single pitcher. Returns ranking row dict."""
    d = data.get(pid, {})
    sum_input = {
        "ip_gs": d.get("ip_gs"),
        "whiff_pct": d.get("whiff_pct"),
        "bb9": d.get("bb9"),
        "gb_pct": d.get("gb_pct"),
        "xwobacon": d.get("xwobacon"),
    }
    total, breakdown = compute_sum_score_v4_sp(sum_input)
    gate_icon, gate_desc = rotation_gate_v4(d.get("g", 0), d.get("gs", 0))
    luck = luck_tag_v4(d.get("xera"), d.get("era"))

    # Build FA-tag-ready view
    fa_view = {
        "savant_v4": {**sum_input,
                      "xera": d.get("xera"), "era": d.get("era"),
                      "bbe": d.get("bbe", 0), "ip": d.get("ip", 0)},
        "rotation_gate": gate_icon,
        # prior_stats + rolling_21d not populated (would require history fetch)
    }
    # For Skubal/main-team display we don't run FA tags; reserved for FA candidates.

    return {
        "name": name,
        "pid": pid,
        "sum": total,
        "breakdown": breakdown,
        "gate": gate_icon,
        "gate_desc": gate_desc,
        "luck": luck,
        "data": d,
        "fa_view": fa_view,
    }


def format_table(rows: list[dict], title: str):
    """Print a ranking table."""
    print(f"\n{'=' * 130}")
    print(f"=== {title} ===")
    print('=' * 130)
    hdr = ("{:<12} {:>4} {:>5} | {:>5}{:>3} {:>6}{:>3} {:>5}{:>3} "
           "{:>5}{:>3} {:>8}{:>3} | {:>4} {:>5} {:>5} | {:<16}")
    print(hdr.format("Name", "Gate", "Sum",
                     "IP/GS", "s", "Whiff%", "s", "BB/9", "s",
                     "GB%", "s", "xwOBAcon", "s",
                     "BBE", "ERA", "xERA", "Luck/Note"))
    print('-' * 160)
    fmt = ("{:<12} {:>4} {:>5} | {:>5.2f}{:>3} {:>6.1f}{:>3} {:>5.2f}{:>3} "
           "{:>5}{:>3} {:>8.3f}{:>3} | {:>4} {:>5} {:>5} | {:<16}")
    for r in rows:
        d = r["data"]
        b = r["breakdown"]
        gb_str = f"{d['gb_pct']:.1f}" if d.get("gb_pct") is not None else "--"
        luck_str = r["luck"] or ""
        try:
            print(fmt.format(
                r["name"], r["gate"], r["sum"],
                d.get("ip_gs") or 0.0, b.get("IP/GS", 0),
                d.get("whiff_pct") or 0.0, b.get("Whiff%", 0),
                d.get("bb9") or 0.0, b.get("BB/9", 0),
                gb_str, b.get("GB%", 0),
                d.get("xwobacon") or 0.0, b.get("xwOBACON", 0),
                d.get("bbe", 0), d.get("era") or 0.0, d.get("xera") or 0.0,
                luck_str,
            ))
        except (TypeError, ValueError) as e:
            print(f"  [err {r['name']}: {e}]")


def fa_upgrade_analysis(fa_rows, weakest_anchors):
    """For each Active FA, compare with each weakest anchor on team.

    Prints one-line recommendation per FA.
    """
    print()
    print('=' * 130)
    print('=== FA 升級分析（對 Active FA）===')
    print('=' * 130)
    for fa in fa_rows:
        if fa["gate"] != "🟢":
            continue
        # Compute add/warn tags
        add_tags = v4_add_tags_sp(fa["fa_view"])
        warn_tags = v4_warn_tags_sp(fa["fa_view"])

        print(f"\n【{fa['name']}】Sum {fa['sum']} / Gate {fa['gate']}")
        if fa["luck"]:
            print(f"  運氣: {fa['luck']}")
        if add_tags:
            print(f"  ✅ {' / '.join(add_tags)}")
        if warn_tags:
            print(f"  ⚠️ {' / '.join(warn_tags)}")

        # Compare against each weakest anchor
        for anchor in weakest_anchors[:3]:  # top 3 worst on team
            sum_diff = fa["sum"] - anchor["sum"]
            breakdown_diff = {
                k: fa["breakdown"].get(k, 0) - anchor["breakdown"].get(k, 0)
                for k in fa["breakdown"]
            }
            decision = v4_decision_sp(sum_diff, breakdown_diff, add_tags, warn_tags)
            positive = sum(1 for d in breakdown_diff.values() if d >= 0)
            print(f"  vs {anchor['name']:<10} Sum={anchor['sum']} | "
                  f"diff +{sum_diff:>2} ({positive}/5 正向) → {decision}")


# ── Main ──

DEFAULT_FA_IDS = {
    # From waiver-log 觀察中 SPs (2026-04-24 snapshot)
    694297: "Pfaadt",
    700712: "Urena",
    690990: "Horton",
    669372: "Ginn",
    676962: "Brown",
    668964: "Myers",
    656492: "Griffin",
    607200: "Fedde",
}


def load_team_sps(config_path="roster_config.json"):
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    sps = []
    for p in config.get("pitchers", []):
        if "SP" in p.get("positions", []):
            sps.append((p["mlb_id"], p["name"]))
    return sps


def main():
    parser = argparse.ArgumentParser(description="SP v4 framework analysis tool")
    parser.add_argument("--year", type=int, default=YEAR_DEFAULT)
    parser.add_argument("--fa", type=str, default="",
                        help="Comma-separated FA mlb_ids (overrides default watch list)")
    parser.add_argument("--config", type=str, default="roster_config.json")
    args = parser.parse_args()

    # Build pitcher ID → name map
    team = load_team_sps(args.config)
    fa_ids_map = DEFAULT_FA_IDS.copy()
    if args.fa:
        # User-supplied overrides default (name unknown → use "FA-{id}")
        fa_ids_map = {int(x): f"FA-{x}" for x in args.fa.split(",") if x.strip()}

    all_ids_to_name = {pid: name for pid, name in team}
    all_ids_to_name.update(fa_ids_map)

    # Fetch all data
    data = assemble_data(set(all_ids_to_name.keys()), args.year)

    # Analyze each pitcher
    team_rows = [analyze_pitcher(name, pid, data) for pid, name in team]
    fa_rows = [analyze_pitcher(name, pid, data) for pid, name in fa_ids_map.items()]

    # Sort by gate then Sum desc
    gate_order = {"🟢": 0, "⚠️": 1, "🚫": 2}
    team_rows.sort(key=lambda r: (gate_order.get(r["gate"], 99), -r["sum"]))
    fa_rows.sort(key=lambda r: (gate_order.get(r["gate"], 99), -r["sum"]))

    # Print reports
    format_table(team_rows, f"隊上 SP ({len(team_rows)}) — {args.year} v4 Sum")
    format_table(fa_rows, f"FA 候選 SP ({len(fa_rows)}) — {args.year} v4 Sum")

    # Identify weakest Active team SPs for FA upgrade analysis
    active_weakest = [r for r in team_rows if r["gate"] == "🟢"][-3:]  # bottom 3 active
    active_weakest.reverse()  # worst first
    fa_upgrade_analysis(fa_rows, active_weakest)

    print()
    print('=' * 130)
    print("=== 資料說明 ===")
    print('=' * 130)
    print("  Sum = 5 indicators × 0-10 (IP/GS + Whiff% + BB/9 + GB% + xwOBACON, 2025 pctile bands)")
    print("  Rotation gate 🟢 = GS/G≥0.6 & GS≥3 ｜ ⚠️ = swingman/新晉 ｜ 🚫 = pure RP/long relief")
    print("  Luck tag: xERA−ERA ≤ -0.81 = ✅ 撿便宜運氣 ｜ ≥ +0.81 = ⚠️ 賣高運氣")
    print("  See docs/sp-framework-v4-balanced.md for full rules")


if __name__ == "__main__":
    main()
