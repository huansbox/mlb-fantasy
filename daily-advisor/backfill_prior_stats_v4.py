#!/usr/bin/env python3
"""backfill_prior_stats_v4 — one-off tool to backfill v4 SP metrics into roster_config.

Adds whiff_pct / gb_pct / xwobacon to roster_config.json prior_stats for SPs
that have an mlb_id but are missing the v4 metrics (added in the v4 framework).
Existing prior_stats keys (xera, xwoba_allowed, hh_pct_allowed, etc.) are
preserved.

Usage (run from daily-advisor/):
    python3 backfill_prior_stats_v4.py --dry-run     # preview, no write
    python3 backfill_prior_stats_v4.py               # write changes
    python3 backfill_prior_stats_v4.py --year 2025   # explicit year (default 2025)

Idempotent: SPs that already have all three v4 keys are skipped automatically.
After v4 cutover this tool can be re-run when new SPs join the roster.

Reuses fetchers from fa_scan_v4.py to keep the Savant URL patterns in one place.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fa_scan_v4 import (
    fetch_savant_arsenal_whiff,
    fetch_savant_batted_ball,
    fetch_savant_custom,
)

V4_KEYS = ("whiff_pct", "gb_pct", "xwobacon")
DEFAULT_YEAR = 2025
CONFIG_PATH = "roster_config.json"


def has_all_v4_keys(prior_stats):
    """True iff prior_stats contains every v4 key (any value, including None)."""
    if not isinstance(prior_stats, dict):
        return False
    return all(k in prior_stats for k in V4_KEYS)


def collect_sp_ids(config):
    """Return [{name, mlb_id}] for SPs missing one or more v4 keys.

    SP detection: 'SP' in positions list. Pure RPs are skipped (v4 framework
    is SP-specific). Players without mlb_id can't be backfilled and are skipped
    silently.
    """
    out = []
    for p in config.get("pitchers", []):
        mlb_id = p.get("mlb_id")
        if not mlb_id:
            continue
        positions = p.get("positions") or []
        if "SP" not in positions:
            continue
        prior = p.get("prior_stats") or {}
        if has_all_v4_keys(prior):
            continue
        out.append({"name": p["name"], "mlb_id": int(mlb_id)})
    return out


def _format_value(key, value):
    if value is None:
        return f"{key}=NULL"
    if key == "xwobacon":
        return f"{key}={value:.3f}"
    return f"{key}={value:.1f}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR,
                        help=f"Year to fetch Savant data from (default {DEFAULT_YEAR})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--config", default=CONFIG_PATH,
                        help=f"Path to roster_config.json (default {CONFIG_PATH})")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    config = json.loads(config_path.read_text(encoding="utf-8"))

    todo = collect_sp_ids(config)
    if not todo:
        print("No SPs need backfill — all v4 keys already present.", file=sys.stderr)
        return 0

    print(f"Found {len(todo)} SP(s) missing v4 keys:", file=sys.stderr)
    for p in todo:
        print(f"  - {p['name']} (mlb_id={p['mlb_id']})", file=sys.stderr)

    print(f"\nFetching {args.year} Savant data (3 endpoints)...", file=sys.stderr)
    custom = fetch_savant_custom(args.year)
    bb = fetch_savant_batted_ball(args.year)
    arsenal = fetch_savant_arsenal_whiff(args.year)
    print(
        f"Got {len(custom)} custom / {len(bb)} batted-ball / {len(arsenal)} arsenal rows.",
        file=sys.stderr,
    )

    updates = {}
    incomplete = []
    for p in todo:
        pid = p["mlb_id"]
        rec = {
            "whiff_pct": arsenal.get(pid, {}).get("whiff_pct"),
            "gb_pct": bb.get(pid, {}).get("gb_pct"),
            "xwobacon": custom.get(pid, {}).get("xwobacon"),
        }
        missing = [k for k, v in rec.items() if v is None]
        if missing:
            incomplete.append((p["name"], pid, missing))
        updates[p["name"]] = rec

    print("\n=== Backfill Plan ===", file=sys.stderr)
    for name, rec in updates.items():
        rec_str = ", ".join(_format_value(k, v) for k, v in rec.items())
        print(f"  {name}: {rec_str}", file=sys.stderr)

    if incomplete:
        print("\nWarnings (incomplete data — partial backfill, may indicate "
              "low-IP rookie or wrong mlb_id):", file=sys.stderr)
        for name, pid, missing in incomplete:
            print(f"  ! {name} (mlb_id={pid}): missing from {missing}", file=sys.stderr)

    if args.dry_run:
        print("\n[DRY RUN] No changes written.", file=sys.stderr)
        return 0

    applied = 0
    for p in config.get("pitchers", []):
        rec = updates.get(p["name"])
        if rec is None:
            continue
        prior = p.setdefault("prior_stats", {})
        if rec["whiff_pct"] is not None:
            prior["whiff_pct"] = round(rec["whiff_pct"], 1)
        if rec["gb_pct"] is not None:
            prior["gb_pct"] = round(rec["gb_pct"], 1)
        if rec["xwobacon"] is not None:
            prior["xwobacon"] = round(rec["xwobacon"], 3)
        applied += 1

    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nApplied to {applied} pitcher(s). Wrote {config_path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
