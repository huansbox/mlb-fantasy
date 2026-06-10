"""Calculate 2025 batter wOBA−xwOBA gap distribution (issue 035).

Derives the significance threshold for the batter luck field — the batter
counterpart of the SP xERA−ERA luck tag (significant at |diff| ≥ P70 of the
2025 distribution, per CLAUDE.md SP 運氣標記 precedent).

Source: Baseball Savant expected_statistics leaderboard CSV (batter, 2025),
which carries both woba and est_woba. Sample gate: bip ≥ 50 (balls in play
≈ BBE, aligned with the existing batter percentile table "min 50 BBE").

Run: uv run --with numpy python calc_woba_gap_pctiles.py
Output: percentile table + recommended threshold + CLAUDE.md snippet.
"""

import csv
import io
import sys
import urllib.request

import numpy as np

YEAR = 2025
MIN_BIP = 50
PCTILE_LEVELS = [10, 25, 40, 50, 60, 70, 80, 90]


def download_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def safe_float(val):
    if val in (None, "", "null", "None", "-", "--"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def main():
    url = (
        "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type=batter&year={YEAR}&position=&team=&min=1&csv=true"
    )
    rows = download_csv(url)
    print(f"Downloaded {len(rows)} batter rows ({YEAR})", file=sys.stderr)

    gaps = []
    for row in rows:
        bip = safe_float(row.get("bip"))
        woba = safe_float(row.get("woba"))
        est_woba = safe_float(row.get("est_woba"))
        if bip is None or bip < MIN_BIP:
            continue
        if woba is None or est_woba is None:
            continue
        gaps.append(woba - est_woba)

    arr = np.array(gaps, dtype=float)
    abs_arr = np.abs(arr)
    n = len(arr)
    print(f"Qualified batters (bip >= {MIN_BIP}): n={n}", file=sys.stderr)

    print()
    print("=" * 70)
    print(f"=== {YEAR} MLB batter wOBA−xwOBA gap distribution "
          f"(bip ≥ {MIN_BIP}, n={n}) ===")
    print("=" * 70)
    print(f"\nmean {arr.mean():+.3f} / std {arr.std():.3f}")

    print("\nSigned gap (正 = 實際優於預期 = 運氣偏多):")
    for p in PCTILE_LEVELS:
        print(f"  P{p:>2}: {np.percentile(arr, p):+.3f}")

    print("\n|gap| (顯著門檻推導用，對齊 SP xERA−ERA P70 前例):")
    for p in (50, 60, 70, 80, 90):
        print(f"  P{p:>2}: {np.percentile(abs_arr, p):.3f}")

    thr = float(np.percentile(abs_arr, 70))
    print(f"\n建議顯著門檻 (|gap| P70): {thr:.3f}")

    print()
    print("=" * 70)
    print("=== CLAUDE.md snippet ===")
    print("=" * 70)
    print(f"打者 wOBA−xwOBA gap（{YEAR} 全季, bip ≥ {MIN_BIP}, n={n}）："
          f"|gap| P50 {np.percentile(abs_arr, 50):.3f} / "
          f"P70 {np.percentile(abs_arr, 70):.3f} / "
          f"P90 {np.percentile(abs_arr, 90):.3f} → "
          f"顯著門檻 |gap| ≥ {thr:.3f}（P70+）")


if __name__ == "__main__":
    main()
