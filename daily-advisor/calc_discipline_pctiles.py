"""2025 plate-discipline distribution for the chase / zone-contact delta field
(issue 049 M-bat). Two outputs:

  1. Cross-sectional 2025 percentile table for chase% (oz_swing_percent) and
     zone-contact% (iz_contact_percent) — qualified-ish batters (PA >= floor).
     Direction: chase LOWER = better (selective); zone-contact HIGHER = better.
  2. The 2024->2025 YoY |delta| distribution (players with PA >= floor in BOTH
     years) — the test-retest baseline that sets the "significant move"
     threshold, the same way calc_woba_gap_pctiles set the luck threshold.

Source: Baseball Savant /leaderboard/custom (batter). Savant only, no Yahoo —
safe to run locally. Re-run when refreshing the 2026 baselines (Week 6-8 task).

    python calc_discipline_pctiles.py [--pa-floor 250]
"""

from __future__ import annotations

import argparse
import csv
import io
import urllib.request

_SEL = "pa,oz_swing_percent,iz_contact_percent"


def fetch(year: int) -> dict[int, dict]:
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=batter&filter=&min=1&selections={_SEL}&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    out = {}
    for r in csv.DictReader(io.StringIO(raw)):
        try:
            pid = int(r["player_id"])
            out[pid] = {
                "pa": float(r["pa"]),
                "chase": float(r["oz_swing_percent"]),
                "zone_contact": float(r["iz_contact_percent"]),
            }
        except (ValueError, KeyError, TypeError):
            continue
    return out


def pctiles(vals: list[float], ps=(10, 25, 40, 50, 55, 60, 70, 80, 90)) -> dict:
    s = sorted(vals)
    n = len(s)
    out = {}
    for p in ps:
        k = (n - 1) * p / 100
        lo = int(k)
        hi = min(lo + 1, n - 1)
        out[p] = round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pa-floor", type=int, default=250)
    args = ap.parse_args()
    floor = args.pa_floor

    y25 = fetch(2025)
    y24 = fetch(2024)
    q25 = {pid: v for pid, v in y25.items() if v["pa"] >= floor}
    print(f"2025 batters PA>={floor}: n={len(q25)}")

    chase = [v["chase"] for v in q25.values()]
    zcon = [v["zone_contact"] for v in q25.values()]
    print("\n# 2025 level percentiles (PA>=%d)" % floor)
    print("chase% (oz_swing, LOWER=better):", pctiles(chase))
    print("zone_contact% (iz_contact, HIGHER=better):", pctiles(zcon))

    # YoY 2024->2025 delta among players qualified both years
    both = [
        pid for pid in q25
        if pid in y24 and y24[pid]["pa"] >= floor
    ]
    dch = [abs(y25[pid]["chase"] - y24[pid]["chase"]) for pid in both]
    dzc = [abs(y25[pid]["zone_contact"] - y24[pid]["zone_contact"]) for pid in both]
    print(f"\n# 2024->2025 |YoY delta| (both years PA>={floor}): n={len(both)}")
    print("|chase delta|:", pctiles(dch, ps=(50, 70, 80, 90)))
    print("|zone_contact delta|:", pctiles(dzc, ps=(50, 70, 80, 90)))


if __name__ == "__main__":
    main()
