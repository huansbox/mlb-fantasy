"""Read Phase 6 dissent metrics from GitHub issue bodies.

Parses ``<!-- phase6_metrics: {...} -->`` blocks emitted by ``metrics_emitter``
and aggregates them into rate stats (P1 match rate, review trigger rate),
broken down by SP vs FA path. Used for weekly dissent monitoring.

CLI:
    python metrics_reader.py --days 7
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

_METRIC_BLOCK_RE = re.compile(
    r"<!-- phase6_metrics:\s*(\{.*?\})\s*-->",
    re.DOTALL,
)

logger = logging.getLogger(__name__)


def parse_metric_block(body: str | None) -> dict | None:
    """Extract one metric block from an issue body.

    Returns None when the block is missing or the JSON is malformed (the
    latter is logged at WARNING).
    """
    if not body:
        return None
    match = _METRIC_BLOCK_RE.search(body)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.warning("Malformed metric block JSON: %s", e)
        return None


def aggregate_metrics(issue_bodies: list[str]) -> dict:
    """Pure aggregation across N issue bodies."""
    blocks = [b for b in (parse_metric_block(body) for body in issue_bodies) if b]
    n = len(blocks)
    empty_breakdown = {
        "p1_match_rate": None,
        "review_trigger_rate": None,
        "p1_pair_borderline_rate": None,
        "p1_pair_borderline_n": 0,
    }
    if n == 0:
        return {
            "n_samples": 0,
            "date_range": None,
            "sp_breakdown": dict(empty_breakdown),
            "fa_breakdown": dict(empty_breakdown),
            "p1_match_rate": None,
            "review_trigger_rate": None,
        }

    dates = sorted(b["date"] for b in blocks if b.get("date"))
    sp_p1 = sum(1 for b in blocks if b.get("sp_p1_match")) / n
    sp_rev = sum(1 for b in blocks if b.get("sp_review_triggered")) / n
    fa_p1 = sum(1 for b in blocks if b.get("fa_p1_match")) / n
    fa_rev = sum(1 for b in blocks if b.get("fa_review_triggered")) / n

    # M4' (top-position pair borderline): the actionable refinement of M4.
    # Aggregated only over blocks that have the new field — issue bodies emitted
    # before 2026-05-26 lack it and would otherwise count as False, biasing rate
    # downward during rollout window.
    sp_pair_blocks = [b for b in blocks if "sp_p1_pair_borderline" in b]
    fa_pair_blocks = [b for b in blocks if "fa_top1_pair_borderline" in b]
    sp_pair_rate = (
        sum(1 for b in sp_pair_blocks if b.get("sp_p1_pair_borderline")) / len(sp_pair_blocks)
        if sp_pair_blocks else None
    )
    fa_pair_rate = (
        sum(1 for b in fa_pair_blocks if b.get("fa_top1_pair_borderline")) / len(fa_pair_blocks)
        if fa_pair_blocks else None
    )

    return {
        "n_samples": n,
        "date_range": [dates[0], dates[-1]] if dates else None,
        "sp_breakdown": {
            "p1_match_rate": sp_p1,
            "review_trigger_rate": sp_rev,
            "p1_pair_borderline_rate": sp_pair_rate,
            "p1_pair_borderline_n": len(sp_pair_blocks),
        },
        "fa_breakdown": {
            "p1_match_rate": fa_p1,
            "review_trigger_rate": fa_rev,
            "p1_pair_borderline_rate": fa_pair_rate,
            "p1_pair_borderline_n": len(fa_pair_blocks),
        },
        "p1_match_rate": (sp_p1 + fa_p1) / 2,
        "review_trigger_rate": (sp_rev + fa_rev) / 2,
    }


def _fetch_issue_bodies(days: int, repo: str, label: str) -> list[str]:
    """Pull recent issue bodies via gh CLI, filtered to last ``days`` days."""
    limit = max(days * 3, 30)
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "-R", repo,
            "--label", label,
            "--limit", str(limit),
            "--state", "all",
            "--json", "body,createdAt",
        ],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(result.stdout)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        i["body"]
        for i in issues
        if datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")) >= cutoff
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7,
                        help="Lookback window in days (default: 7)")
    parser.add_argument("--repo", default="huansbox/mlb-fantasy",
                        help="GitHub repo (default: huansbox/mlb-fantasy)")
    parser.add_argument("--label", default="fa-scan",
                        help="GitHub label filter (default: fa-scan)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    bodies = _fetch_issue_bodies(args.days, args.repo, args.label)
    stats = aggregate_metrics(bodies)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
