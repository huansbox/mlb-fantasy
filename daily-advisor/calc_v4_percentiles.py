"""Calculate 2025 SP percentiles for v4 framework (IP/GS, Whiff%, BB/9, GB%, xwOBACON).

Downloads from:
  - Baseball Savant custom leaderboard  (xwOBACON)
  - Baseball Savant batted-ball         (GB%)
  - Baseball Savant pitch-arsenal-stats (Whiff%, weighted by pitch usage)
  - MLB Stats API                       (G, GS, IP, BB -> IP/GS, BB/9)

Classifies SP as GS/G > 0.5, min GS >= 10 (2025 full season threshold).
Outputs v4 percentile table and CLAUDE.md snippet.
"""

import csv
import io
import json
import sys
import urllib.request
import numpy as np


MLB_API = "https://statsapi.mlb.com/api/v1"
YEAR = 2025
PCTILE_LEVELS = [25, 40, 45, 50, 55, 60, 70, 80, 90]


def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")


def download_csv(url):
    text = fetch_url(url)
    return list(csv.DictReader(io.StringIO(text)))


def safe_float(val, default=None):
    if val in (None, "", "null", "None", "-", "--", "-.--"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    if val in (None, "", "null", "None"):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def fetch_pitcher_season_bulk(pitcher_ids, year):
    """Fetch G, GS, IP, BB for pitchers via MLB Stats API (batch 50)."""
    result = {}
    ids = list(pitcher_ids)
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        id_str = ",".join(str(x) for x in batch)
        url = (
            f"{MLB_API}/people?personIds={id_str}"
            f"&hydrate=stats(group=[pitching],type=[season],season={year})"
        )
        try:
            data = json.loads(fetch_url(url))
            for person in data.get("people", []):
                pid = person.get("id")
                for sg in person.get("stats", []):
                    splits = sg.get("splits", [])
                    if splits:
                        stat = splits[0].get("stat", {})
                        g = int(stat.get("gamesPlayed", 0))
                        gs = int(stat.get("gamesStarted", 0))
                        ip_str = stat.get("inningsPitched", "0.0")
                        ip_val = safe_float(ip_str, 0.0)
                        # Convert 26.2 (26 outs + 2/3 inn) → real float
                        ip_real = int(ip_val) + (ip_val - int(ip_val)) * 10 / 3
                        bb = safe_int(stat.get("baseOnBalls"), 0)
                        result[pid] = {
                            "g": g, "gs": gs, "ip": ip_real, "bb": bb,
                        }
                        break
        except Exception as e:
            print(f"  MLB API batch {i} failed: {e}", file=sys.stderr)
        print(f"  MLB API batch {i}-{i + len(batch)}: queried", file=sys.stderr)
    return result


def build_savant_data(year):
    """Build {pid: {...}} dict merging 3 Savant endpoints."""
    print(f"\nDownloading 2025 Savant data...", file=sys.stderr)

    # 1. custom leaderboard — xwOBACON
    print("  custom (xwOBACON)...", file=sys.stderr)
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=pitcher&filter=&min=1"
        f"&selections=pa,bip,xwoba,xwobacon&csv=true"
    )
    custom = download_csv(url)

    # 2. batted-ball — GB%
    print("  batted-ball (GB%)...", file=sys.stderr)
    url = (
        "https://baseballsavant.mlb.com/leaderboard/batted-ball"
        f"?year={year}&type=pitcher&min=1&csv=true"
    )
    bb_data = download_csv(url)

    # 3. pitch-arsenal-stats — Whiff% by pitch type
    print("  pitch-arsenal (Whiff%)...", file=sys.stderr)
    url = (
        "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
        f"?type=pitcher&year={year}&min=1&csv=true"
    )
    arsenal = download_csv(url)

    # Merge
    pitchers = {}

    # custom keys: player_id, pa, bip, xwoba, xwobacon
    # NOTE: 2025 custom endpoint's `bip` column is empty; use batted-ball's bbe instead.
    for row in custom:
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        pitchers.setdefault(pid, {})
        pitchers[pid]["xwoba_allowed"] = safe_float(row.get("xwoba"))
        pitchers[pid]["xwobacon"] = safe_float(row.get("xwobacon"))

    # batted-ball keys: id, name, bbe, gb_rate, ld_rate, fb_rate, ...
    # This endpoint has the authoritative bbe for sample filtering.
    for row in bb_data:
        pid = safe_int(row.get("id"), 0)
        if not pid:
            continue
        pitchers.setdefault(pid, {})
        pitchers[pid]["bbe"] = safe_int(row.get("bbe"), 0)
        gb = safe_float(row.get("gb_rate"))
        if gb is not None:
            pitchers[pid]["gb_pct"] = gb * 100  # rate → %

    # pitch-arsenal-stats: weighted Whiff% per pitch type
    # Aggregate: weighted avg of whiff_percent by pitches
    agg = {}
    for row in arsenal:
        pid = safe_int(row.get("player_id"), 0)
        if not pid:
            continue
        pitches = safe_int(row.get("pitches"), 0)
        whiff = safe_float(row.get("whiff_percent"))
        if pitches and whiff is not None:
            if pid not in agg:
                agg[pid] = {"pitches": 0, "whiff_wsum": 0.0}
            agg[pid]["pitches"] += pitches
            agg[pid]["whiff_wsum"] += whiff * pitches
    for pid, a in agg.items():
        if a["pitches"] > 0:
            pitchers.setdefault(pid, {})
            pitchers[pid]["whiff_pct"] = a["whiff_wsum"] / a["pitches"]
            pitchers[pid]["arsenal_pitches"] = a["pitches"]

    return pitchers


def compute_percentiles(values, reverse=False):
    """Compute percentiles with elite-direction convention.

    When reverse=True (e.g., BB/9, xwOBACON where lower is better), swap
    so output P90 = best 10% = raw 10th percentile value.
    """
    arr = np.array(values, dtype=float)
    result = {}
    for p in PCTILE_LEVELS:
        raw_p = (100 - p) if reverse else p
        result[p] = round(float(np.percentile(arr, raw_p)), 3)
    return result


def main():
    savant = build_savant_data(YEAR)
    pitcher_ids = set(savant.keys())
    print(f"\nTotal 2025 pitchers in Savant: {len(pitcher_ids)}", file=sys.stderr)

    # Fetch G/GS/IP/BB from MLB API
    print(f"\nFetching MLB Stats API for {len(pitcher_ids)} pitchers...", file=sys.stderr)
    mlb_data = fetch_pitcher_season_bulk(pitcher_ids, YEAR)
    print(f"  Got data for {len(mlb_data)} pitchers", file=sys.stderr)

    # Merge & classify
    sps = []
    for pid, s in savant.items():
        m = mlb_data.get(pid, {})
        g, gs, ip, bb = m.get("g", 0), m.get("gs", 0), m.get("ip", 0), m.get("bb", 0)
        if g == 0 or gs == 0:
            continue
        # SP classification: GS/G > 0.5 AND GS >= 10 (min full season threshold)
        if gs / g > 0.5 and gs >= 10:
            ip_gs = ip / gs if gs else 0
            bb9 = 9 * bb / ip if ip else 0
            entry = {
                "id": pid,
                "bbe": s.get("bbe", 0),
                "xwoba_allowed": s.get("xwoba_allowed"),
                "xwobacon": s.get("xwobacon"),
                "gb_pct": s.get("gb_pct"),
                "whiff_pct": s.get("whiff_pct"),
                "arsenal_pitches": s.get("arsenal_pitches", 0),
                "ip_gs": ip_gs,
                "bb9": bb9,
                "ip": ip, "gs": gs, "g": g, "bb": bb,
            }
            sps.append(entry)

    print(f"\nClassified SP (GS/G > 0.5, GS >= 10): n={len(sps)}", file=sys.stderr)

    # Filter by min sample sizes
    def filter_metric(sps, key, min_sample_key=None, min_sample_value=0):
        out = []
        for s in sps:
            v = s.get(key)
            if v is None:
                continue
            if min_sample_key and s.get(min_sample_key, 0) < min_sample_value:
                continue
            out.append(v)
        return out

    # Compute percentiles with sample filtering
    # reverse=True for indicators where LOWER value = BETTER (elite P90 = lowest)
    metrics_config = [
        ("ip_gs", "IP/GS", "{:.2f}", None, 0, False),
        ("whiff_pct", "Whiff% (weighted)", "{:.1f}", "arsenal_pitches", 500, False),
        ("bb9", "BB/9", "{:.2f}", None, 0, True),   # lower = better
        ("gb_pct", "GB%", "{:.1f}", "bbe", 50, False),
        ("xwobacon", "xwOBACON", "{:.3f}", "bbe", 50, True),   # lower = better
        # Legacy comparables
        ("xwoba_allowed", "xwOBA allowed (legacy)", "{:.3f}", "bbe", 50, True),
    ]

    results = {}
    sample_sizes = {}
    for key, label, fmt, sample_key, sample_min, reverse in metrics_config:
        values = filter_metric(sps, key, sample_key, sample_min)
        results[key] = compute_percentiles(values, reverse=reverse) if len(values) >= 30 else None
        sample_sizes[key] = len(values)

    # ── Output ──
    print()
    print("=" * 80)
    print(f"=== 2025 MLB SP Percentiles for v4 Framework ===")
    print(f"=== SP: GS/G > 0.5, GS >= 10 (n={len(sps)}) ===")
    print("=" * 80)

    for key, label, fmt, _, sample_min, reverse in metrics_config:
        pct = results.get(key)
        n = sample_sizes.get(key, 0)
        dir_note = " [lower = better, P90 = elite low value]" if reverse else ""
        print(f"\n{label} (n={n}, sample filter: {sample_min or 'none'}){dir_note}")
        if not pct:
            print("  [insufficient data]")
            continue
        print(f"  {'Pctile':>6} | {'Value':>10}")
        print(f"  {'-'*6}-+-{'-'*10}")
        for lvl in PCTILE_LEVELS:
            v = pct[lvl]
            print(f"  {'P'+str(lvl):>6} | {fmt.format(v):>10}")

    # ── Markdown snippet for CLAUDE.md ──
    print()
    print("=" * 80)
    print("=== CLAUDE.md SP v4 percentile table snippet ===")
    print("=" * 80)
    print()
    print("SP v4（2025 MLB SP, GS/G>0.5, GS>=10, n={}）:".format(len(sps)))
    print()
    print("| 百分位 | IP/GS | Whiff% | BB/9 | GB% | xwOBACON |")
    print("|--------|:---:|:---:|:---:|:---:|:---:|")

    lvl_label = {25: "P25", 40: "P40", 45: "P45", 50: "**P50**",
                 55: "P55", 60: "P60", 70: "P70", 80: "P80", 90: "P90"}

    def fmt_val(key, lvl):
        pct = results.get(key)
        if not pct:
            return "—"
        v = pct[lvl]
        if key == "ip_gs":
            return f"{v:.2f}"
        elif key == "bb9":
            return f"{v:.2f}"
        elif key == "xwobacon":
            return f".{str(round(v*1000)).zfill(3)}"
        elif key in ("whiff_pct", "gb_pct"):
            return f"{v:.1f}%"
        return str(v)

    for lvl in PCTILE_LEVELS:
        row = f"| {lvl_label[lvl]} "
        for key in ("ip_gs", "whiff_pct", "bb9", "gb_pct", "xwobacon"):
            row += f"| {fmt_val(key, lvl)} "
        row += "|"
        if lvl == 50:
            print(f"| **{lvl_label[lvl].replace('**', '')}** "
                  f"| **{fmt_val('ip_gs', lvl)}** "
                  f"| **{fmt_val('whiff_pct', lvl)}** "
                  f"| **{fmt_val('bb9', lvl)}** "
                  f"| **{fmt_val('gb_pct', lvl)}** "
                  f"| **{fmt_val('xwobacon', lvl)}** |")
        else:
            print(row)

    print()


if __name__ == "__main__":
    main()
