"""Calculate 2026 Savant percentile distribution and compare with 2025.

Downloads 4 Savant CSVs (batter/pitcher x statcast/expected_statistics),
classifies SP vs RP via MLB Stats API (G/GS),
computes percentile breakpoints, and compares to 2025.
"""

import csv
import io
import json
import sys
import urllib.request
import numpy as np


# ── 2025 baselines from daily_advisor.py ──
BATTER_PCTILES_2025 = {
    "xwoba":      {25:.261, 40:.286, 45:.293, 50:.297, 55:.302, 60:.307, 70:.321, 80:.331, 90:.349},
    "barrel_pct": {25:4.7, 40:6.5, 45:7.1, 50:7.8, 55:8.5, 60:9.1, 70:10.3, 80:12.0, 90:14.0},
    "hh_pct":     {25:34.6, 40:38.3, 45:39.0, 50:40.4, 55:41.5, 60:42.6, 70:44.7, 80:46.7, 90:49.7},
}
SP_PCTILES_2025 = {
    "xera":       {25:5.62, 40:4.64, 45:4.48, 50:4.33, 55:4.16, 60:4.04, 70:3.74, 80:3.43, 90:2.98},
    "xwoba":      {25:.361, 40:.332, 45:.327, 50:.322, 55:.316, 60:.312, 70:.301, 80:.289, 90:.270},
    "hh_pct":     {25:44.2, 40:42.2, 45:41.6, 50:40.8, 55:40.2, 60:39.4, 70:38.0, 80:36.4, 90:34.1},
    "barrel_pct": {25:10.1, 40:9.1, 45:8.9, 50:8.5, 55:8.1, 60:7.9, 70:7.1, 80:6.3, 90:4.9},
    "era_diff":   {25:0.28, 40:0.43, 45:0.49, 50:0.53, 55:0.59, 60:0.66, 70:0.81, 80:1.03, 90:1.31},
}
RP_PCTILES_2025 = {
    "xera":       SP_PCTILES_2025["xera"],
    "xwoba":      SP_PCTILES_2025["xwoba"],
    "hh_pct":     SP_PCTILES_2025["hh_pct"],
    "barrel_pct": SP_PCTILES_2025["barrel_pct"],
    "era_diff":   {25:0.28, 40:0.43, 45:0.52, 50:0.57, 55:0.63, 60:0.72, 70:0.88, 80:1.06, 90:1.24},
}

PCTILE_LEVELS = [25, 40, 45, 50, 55, 60, 70, 80, 90]

MLB_API = "https://statsapi.mlb.com/api/v1"


def fetch_pitcher_gs_bulk(pitcher_ids, year):
    """Fetch G and GS for pitchers via MLB Stats API in batches.

    Uses /people?personIds=... with hydrate=stats(group=[pitching],type=[season])
    Returns dict: mlb_id -> {"g": int, "gs": int}
    """
    result = {}
    ids = list(pitcher_ids)
    batch_size = 50  # MLB API handles ~50 per request safely
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        id_str = ",".join(str(x) for x in batch)
        url = (
            f"{MLB_API}/people?personIds={id_str}"
            f"&hydrate=stats(group=[pitching],type=[season],season={year})"
        )
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read().decode("utf-8"))
            for person in data.get("people", []):
                pid = person.get("id")
                stats_list = person.get("stats", [])
                for sg in stats_list:
                    splits = sg.get("splits", [])
                    if splits:
                        stat = splits[0].get("stat", {})
                        g = int(stat.get("gamesPlayed", 0))
                        gs = int(stat.get("gamesStarted", 0))
                        result[pid] = {"g": g, "gs": gs}
                        break
        except Exception as e:
            print(f"  MLB API batch {i}-{i+len(batch)} failed: {e}", file=sys.stderr)
        print(f"  MLB API batch {i}-{i+len(batch)}: {len(batch)} queried", file=sys.stderr)
    print(f"  MLB API pitcher G/GS total: {len(result)} pitchers", file=sys.stderr)
    return result


def download_csv(leaderboard, player_type, year):
    """Download a Savant CSV and return list of row dicts."""
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/{leaderboard}"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    text = resp.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"  Downloaded {leaderboard}/{player_type}/{year}: {len(rows)} rows", file=sys.stderr)
    return rows


def find_id_col(row):
    for col in ("player_id", "mlbam_id"):
        if col in row:
            return col
    return None


def safe_float(val, default=None):
    if val is None or val in ("", "null", "None", "-", "—", "-.--"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    if val is None or val in ("", "null", "None"):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def compute_percentiles(values, levels=PCTILE_LEVELS):
    """Compute percentiles from a list of values."""
    arr = np.array(values, dtype=float)
    result = {}
    for p in levels:
        result[p] = round(float(np.percentile(arr, p)), 3)
    return result


def main():
    year = 2026
    min_bbe_primary = 50
    min_bbe_fallback = 30

    # ── Download 4 CSVs ──
    print("Downloading Savant CSVs...", file=sys.stderr)
    batter_sc = download_csv("statcast", "batter", year)
    batter_ex = download_csv("expected_statistics", "batter", year)
    pitcher_sc = download_csv("statcast", "pitcher", year)
    pitcher_ex = download_csv("expected_statistics", "pitcher", year)

    # ── Show column names for debugging ──
    if batter_sc:
        print(f"  batter_sc columns: {list(batter_sc[0].keys())[:15]}...", file=sys.stderr)
    if batter_ex:
        print(f"  batter_ex columns: {list(batter_ex[0].keys())[:15]}...", file=sys.stderr)
    if pitcher_sc:
        print(f"  pitcher_sc columns: {list(pitcher_sc[0].keys())[:15]}...", file=sys.stderr)
    if pitcher_ex:
        print(f"  pitcher_ex columns: {list(pitcher_ex[0].keys())[:15]}...", file=sys.stderr)

    # ── Build ID-indexed dicts ──
    def build_id_index(rows):
        idx = {}
        if not rows:
            return idx
        id_col = find_id_col(rows[0])
        if not id_col:
            return idx
        for row in rows:
            pid = row.get(id_col, "").strip()
            if pid:
                idx[int(pid)] = row
        return idx

    bat_sc_idx = build_id_index(batter_sc)
    bat_ex_idx = build_id_index(batter_ex)
    pit_sc_idx = build_id_index(pitcher_sc)
    pit_ex_idx = build_id_index(pitcher_ex)

    # ── Merge batter data ──
    all_bat_ids = set(bat_sc_idx.keys()) | set(bat_ex_idx.keys())
    batters = []
    for pid in all_bat_ids:
        sc = bat_sc_idx.get(pid, {})
        ex = bat_ex_idx.get(pid, {})
        bbe = safe_int(sc.get("attempts"), 0)
        xwoba = safe_float(ex.get("est_woba"))
        hh_pct = safe_float(sc.get("ev95percent"))
        barrel_pct = safe_float(sc.get("brl_percent"))
        batters.append({
            "id": pid,
            "bbe": bbe,
            "xwoba": xwoba,
            "hh_pct": hh_pct,
            "barrel_pct": barrel_pct,
        })

    # ── Fetch pitcher G/GS from MLB API for SP/RP classification ──
    all_pit_ids = set(pit_sc_idx.keys()) | set(pit_ex_idx.keys())
    print(f"\nFetching pitcher G/GS from MLB API for {len(all_pit_ids)} pitchers...", file=sys.stderr)
    pitcher_gs = fetch_pitcher_gs_bulk(all_pit_ids, year)

    # ── Merge pitcher data, classify SP vs RP ──
    sp_list = []
    rp_list = []
    unclassified = 0
    for pid in all_pit_ids:
        sc = pit_sc_idx.get(pid, {})
        ex = pit_ex_idx.get(pid, {})
        bbe = safe_int(sc.get("attempts"), 0)
        xwoba = safe_float(ex.get("est_woba"))
        xera = safe_float(ex.get("xera"))
        hh_pct = safe_float(sc.get("ev95percent"))
        barrel_pct = safe_float(sc.get("brl_percent"))
        era = safe_float(ex.get("era"))
        era_diff = abs(xera - era) if (xera is not None and era is not None) else None

        # Classify SP vs RP using MLB API G/GS
        gs_data = pitcher_gs.get(pid, {})
        g = gs_data.get("g", 0)
        gs = gs_data.get("gs", 0)

        entry = {
            "id": pid,
            "bbe": bbe,
            "xwoba": xwoba,
            "xera": xera,
            "hh_pct": hh_pct,
            "barrel_pct": barrel_pct,
            "era": era,
            "era_diff": era_diff,
            "g": g,
            "gs": gs,
        }

        if g == 0:
            # No MLB API data — skip (can't classify)
            unclassified += 1
            continue
        elif gs / g > 0.5:
            sp_list.append(entry)
        else:
            rp_list.append(entry)

    print(f"  SP: {len(sp_list)}, RP: {len(rp_list)}, unclassified: {unclassified}", file=sys.stderr)

    # ── Filter by min BBE and compute ──
    def compute_all(data_list, metrics, min_bbe, label):
        filtered = [d for d in data_list if d["bbe"] >= min_bbe]
        n = len(filtered)
        print(f"\n{label}: n={n} (min BBE >= {min_bbe})", file=sys.stderr)
        result = {}
        for metric in metrics:
            values = [d[metric] for d in filtered if d[metric] is not None]
            if len(values) < 10:
                print(f"  WARNING: {metric} only has {len(values)} values, skipping", file=sys.stderr)
                continue
            result[metric] = compute_percentiles(values)
            print(f"  {metric}: {len(values)} values", file=sys.stderr)
        return result, n

    bat_metrics = ["xwoba", "barrel_pct", "hh_pct"]
    sp_metrics = ["xera", "xwoba", "hh_pct", "barrel_pct", "era_diff"]
    rp_metrics = ["xera", "xwoba", "hh_pct", "barrel_pct", "era_diff"]

    # Show BBE distribution for debugging
    for label, dlist in [("Batters", batters), ("SP", sp_list), ("RP", rp_list)]:
        bbes = sorted([d["bbe"] for d in dlist], reverse=True)
        if bbes:
            print(f"\n  {label} BBE distribution (top 10): {bbes[:10]}", file=sys.stderr)
            for thresh in [50, 40, 30, 20, 15, 10]:
                cnt = sum(1 for b in bbes if b >= thresh)
                print(f"    BBE >= {thresh}: {cnt}", file=sys.stderr)

    # Adaptive threshold: try 50, then 30, then 20, then 15
    thresholds = [50, 30, 20, 15]

    def compute_with_adaptive_threshold(dlist, metrics, label, min_n=30):
        for thresh in thresholds:
            pct, n = compute_all(dlist, metrics, thresh, f"{label} (BBE>={thresh})")
            if n >= min_n:
                return pct, n, thresh
        # Last resort: use whatever we have with lowest threshold
        return pct, n, thresholds[-1]

    bat_pct, bat_n, bat_thresh = compute_with_adaptive_threshold(batters, bat_metrics, "Batters", 50)
    sp_pct, sp_n, sp_thresh = compute_with_adaptive_threshold(sp_list, sp_metrics, "SP", 30)
    rp_pct, rp_n, rp_thresh = compute_with_adaptive_threshold(rp_list, rp_metrics, "RP", 30)

    # ── Output comparison tables ──
    print()
    print("=" * 80)
    print(f"=== 2026 vs 2025 Savant Percentile Comparison (2026 data as of {year} early season) ===")
    print("=" * 80)

    def pct_diff(v2026, v2025):
        """Calculate percentage difference. Returns string with marker if > 5%."""
        if v2025 == 0:
            return ""
        diff = (v2026 - v2025) / abs(v2025) * 100
        marker = " ***" if abs(diff) > 5 else ""
        return f"{diff:+.1f}%{marker}"

    def print_comparison(label, pct_2026, pct_2025_dict, n, metrics_config):
        """Print comparison table.
        metrics_config: list of (metric_name, display_name, fmt, direction_note)
        """
        print(f"\n{'=' * 70}")
        print(f"  {label} (2026 n={n})")
        print(f"{'=' * 70}")

        for metric, display, fmt, note in metrics_config:
            if metric not in pct_2026:
                print(f"\n  {display}: insufficient data, skipped")
                continue
            p25 = pct_2025_dict.get(metric, {})
            p26 = pct_2026[metric]

            print(f"\n  {display} {note}")
            print(f"  {'Pctile':>6} | {'2025':>10} | {'2026':>10} | {'Diff':>10}")
            print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")
            for lvl in PCTILE_LEVELS:
                v25 = p25.get(lvl)
                v26 = p26.get(lvl)
                if v25 is None or v26 is None:
                    continue
                v25_s = fmt.format(v25)
                v26_s = fmt.format(v26)
                diff_s = pct_diff(v26, v25)
                print(f"  {'P'+str(lvl):>6} | {v25_s:>10} | {v26_s:>10} | {diff_s:>10}")

    # Batters
    print_comparison(
        "Batters (higher = better)",
        bat_pct, BATTER_PCTILES_2025, bat_n,
        [
            ("xwoba", "xwOBA", "{:.3f}", "(higher = better)"),
            ("barrel_pct", "Barrel%", "{:.1f}%", "(higher = better)"),
            ("hh_pct", "HH%", "{:.1f}%", "(higher = better)"),
        ]
    )

    # SP
    print_comparison(
        "SP (lower quality value = better, except |xERA-ERA| higher = more luck variance)",
        sp_pct, SP_PCTILES_2025, sp_n,
        [
            ("xera", "xERA", "{:.2f}", "(lower = better)"),
            ("xwoba", "xwOBA allowed", "{:.3f}", "(lower = better)"),
            ("hh_pct", "HH% allowed", "{:.1f}%", "(lower = better)"),
            ("barrel_pct", "Barrel% allowed", "{:.1f}%", "(lower = better)"),
            ("era_diff", "|xERA-ERA|", "{:.2f}", "(higher = more luck variance)"),
        ]
    )

    # RP
    print_comparison(
        "RP (same quality direction as SP)",
        rp_pct, RP_PCTILES_2025, rp_n,
        [
            ("xera", "xERA", "{:.2f}", "(lower = better)"),
            ("xwoba", "xwOBA allowed", "{:.3f}", "(lower = better)"),
            ("hh_pct", "HH% allowed", "{:.1f}%", "(lower = better)"),
            ("barrel_pct", "Barrel% allowed", "{:.1f}%", "(lower = better)"),
            ("era_diff", "|xERA-ERA|", "{:.2f}", "(higher = more luck variance)"),
        ]
    )

    # ── Summary: total data points ──
    print(f"\n{'=' * 70}")
    print(f"  Sample size summary")
    print(f"{'=' * 70}")
    print(f"  Batters: n={bat_n} (min BBE >= {bat_thresh})")
    print(f"  SP: n={sp_n} (GS > 50% of G, min BBE >= {sp_thresh})")
    print(f"  RP: n={rp_n} (GS <= 50% of G, min BBE >= {rp_thresh})")
    print(f"\n  Note: 2026 season Week 3, sample sizes are much smaller than 2025 full season")
    print(f"  2025 reference: Batters n=537, SP n=216, RP n=284")
    print()


if __name__ == "__main__":
    main()
