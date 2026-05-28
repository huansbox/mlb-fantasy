"""backtest_track — Use Case A: B2 SP-v4 verdict → outcome backtest.

Reads GitHub Issues labelled `fa-scan` from the last N days, extracts B2 Step B
verdicts, joins with subsequent SP performance data (Savant rolling), classifies
each verdict as hit / miss / neutral, and appends a weekly summary section to
`docs/sp-decisions-backtest.md`.

This is the quality-monitoring replacement for retired B1 M1/M4' metrics
(see docs/sp-b2-cutover-design.md §"Quality Monitoring").

Use Case B (xwOBACON threshold calibration) is explicitly out of scope — deferred
4-6 weeks post-cutover. Pure-function primitives live in `_backtest_lib.py`.

Usage:
    python3 backtest_track.py --days 7                 # weekly summary to stdout
    python3 backtest_track.py --days 7 --update-doc    # append to backtest doc
    python3 backtest_track.py --dry-run                # explicit no-op preview
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from _backtest_lib import (
    B2Verdict,
    VerdictOutcome,
    aggregate_hit_rate,
    build_roster_name_index,
    parse_b2_verdict,
    parse_issue_date,
    resolve_player,
)


_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
_BACKTEST_DOC = _REPO_ROOT / "docs" / "sp-decisions-backtest.md"
_ROSTER_CONFIG = _MODULE_DIR / "roster_config.json"

# Post-verdict observation window. Short enough to surface fast feedback,
# long enough for SP signal noise to settle.
_OBSERVATION_DAYS = 21

# `watch` action outcome threshold — xwOBACON ≤ P50 (.370) means the target
# stayed strong enough to remain watchable. Static P50 used here pending
# Use Case B calibration from real data; absolute-delta logic deferred to
# the same calibration pass.
_WATCH_HIT_XWOBACON = 0.370

logger = logging.getLogger(__name__)


# ── GitHub Issue fetch ──

def fetch_recent_issues(days: int, repo: str = "huansbox/mlb-fantasy",
                       label: str = "fa-scan") -> list[dict]:
    """Pull recent fa-scan issues via gh CLI, filtered to last `days` days.

    System boundary — relies on `gh` CLI being authenticated. Not unit-tested.
    """
    limit = max(days * 4, 30)
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "-R", repo,
            "--label", label,
            "--limit", str(limit),
            "--state", "all",
            "--json", "body,createdAt,number,title",
        ],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(result.stdout)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        i for i in issues
        if datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")) >= cutoff
    ]


# ── Outcome classification ──

def fetch_post_verdict_xwobacon(mlb_id: int, start_date: date,
                                window_days: int = _OBSERVATION_DAYS) -> float | None:
    """Fetch SP's xwOBACON in [start_date, start_date + window_days).

    System boundary — wraps savant_rolling.fetch_savant_rolling under the hood
    if available. Returns None when data unavailable. Not unit-tested.

    Stub: full Savant integration is out of scope until B2 emits real verdicts
    post-cutover (issue 025). The function signature is locked in so the
    aggregate pipeline shape stabilizes.
    """
    # TODO: integrate savant_rolling.fetch_savant_rolling once B2 has real
    # production data; for now return None so outcomes classify as neutral.
    return None


def classify_outcome(verdict: B2Verdict, post_drop: float | None,
                     post_add: float | None) -> VerdictOutcome:
    """Decide hit / miss / neutral from observed post-verdict xwOBACON.

    Hit logic per action (xwOBACON LOWER = better SP):
      - drop_X_add_Y: hit iff post_add < post_drop (FA actually outproduced
                       the dropped SP). Marginal benefit = post_drop - post_add.
      - watch:        hit iff watch target's xwOBACON stayed below P50
                       threshold (`_WATCH_HIT_XWOBACON`) — i.e. remained
                       watchable. Marginal benefit not defined → None.
                       (`post_add` parameter carries the watch-target value
                       in this branch; see callers in run_weekly_summary.)
      - pass:         neutral (no observable comparison from pass action alone).

    Missing data on either side → neutral (we don't punish the verdict for
    data unavailability; flag in stderr instead).
    """
    if verdict.action == "pass":
        return VerdictOutcome(verdict=verdict, outcome_label="neutral", marginal_benefit=None)
    if verdict.action == "drop_X_add_Y":
        if post_drop is None or post_add is None:
            return VerdictOutcome(verdict=verdict, outcome_label="neutral", marginal_benefit=None)
        benefit = post_drop - post_add  # positive = FA was better
        label = "hit" if benefit > 0 else "miss"
        return VerdictOutcome(verdict=verdict, outcome_label=label, marginal_benefit=benefit)
    if verdict.action == "watch":
        if post_add is None:  # post_add here is the watch_target xwOBACON snapshot
            return VerdictOutcome(verdict=verdict, outcome_label="neutral", marginal_benefit=None)
        label = "hit" if post_add <= _WATCH_HIT_XWOBACON else "miss"
        return VerdictOutcome(verdict=verdict, outcome_label=label, marginal_benefit=None)
    return VerdictOutcome(verdict=verdict, outcome_label="neutral", marginal_benefit=None)


# ── Aggregate pipeline ──

def collect_verdicts(issues: list[dict]) -> list[B2Verdict]:
    """Parse a list of GitHub Issue dicts into B2Verdict objects.

    Issues without B2 Step B blocks are silently skipped (B1 issues, batter
    issues, RP issues — all expected non-matches).
    """
    verdicts: list[B2Verdict] = []
    for issue in issues:
        body = issue.get("body") or ""
        d = parse_issue_date(issue.get("createdAt") or "")
        v = parse_b2_verdict(body, d)
        if v is not None:
            verdicts.append(v)
    return verdicts


def run_weekly_summary(days: int, repo: str = "huansbox/mlb-fantasy",
                      label: str = "fa-scan") -> dict:
    """Full pipeline: fetch issues → parse verdicts → classify outcomes → aggregate."""
    issues = fetch_recent_issues(days, repo=repo, label=label)
    verdicts = collect_verdicts(issues)

    try:
        roster_config = json.loads(_ROSTER_CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        roster_config = {}
    roster_index = build_roster_name_index(roster_config)

    outcomes: list[VerdictOutcome] = []
    for v in verdicts:
        # Resolve drop / add targets when present
        drop_id = resolve_player(v.drop, roster_index).mlb_id if v.drop else None
        add_id = resolve_player(v.add or v.watch_target or "", roster_index).mlb_id

        post_drop = (
            fetch_post_verdict_xwobacon(drop_id, v.issue_date)
            if drop_id else None
        )
        post_add = (
            fetch_post_verdict_xwobacon(add_id, v.issue_date)
            if add_id else None
        )
        outcomes.append(classify_outcome(v, post_drop, post_add))

    stats = aggregate_hit_rate(outcomes)
    stats["window_days"] = days
    stats["observation_window_days"] = _OBSERVATION_DAYS
    stats["date_range"] = _date_range(verdicts)
    stats["verdicts"] = [
        {
            "issue_date": v.issue_date.isoformat(),
            "action": v.action,
            "drop": v.drop,
            "add": v.add,
            "watch_target": v.watch_target,
        }
        for v in verdicts
    ]
    return stats


def _date_range(verdicts: list[B2Verdict]) -> list[str] | None:
    if not verdicts:
        return None
    dates = sorted(v.issue_date for v in verdicts)
    return [dates[0].isoformat(), dates[-1].isoformat()]


# ── Markdown append ──

def format_weekly_section(stats: dict) -> str:
    """Render the weekly summary as appendable markdown.

    Inserted under a new section in docs/sp-decisions-backtest.md.
    """
    range_str = " ~ ".join(stats["date_range"]) if stats["date_range"] else "no verdicts"
    today_str = date.today().isoformat()
    lines = [
        f"## Weekly Backtest {today_str} ({range_str})",
        "",
        f"- Window: last {stats['window_days']} days; post-verdict observation: {stats['observation_window_days']} days",
        f"- Total verdicts parsed: {stats['n_total']} (actionable: {stats['n_actionable']})",
        f"- Hit rate: {_fmt_rate(stats['hit_rate'])}",
    ]
    avg_benefit = stats.get("avg_marginal_benefit")
    if avg_benefit is not None:
        lines.append(f"- Average marginal benefit (xwOBACON Δ favoring add): {avg_benefit:+.4f}")
    lines.append("")
    lines.append("By action:")
    for action, bucket in stats["by_action"].items():
        lines.append(
            f"- `{action}` n={bucket['n']} (actionable {bucket['n_actionable']}) "
            f"hit_rate={_fmt_rate(bucket['hit_rate'])}"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _fmt_rate(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}"


def append_to_backtest_doc(section_md: str) -> None:
    """Append section to backtest doc. Idempotent only on date — re-running
    same day appends a duplicate section; user reviews/edits before commit."""
    if not _BACKTEST_DOC.exists():
        raise FileNotFoundError(f"backtest doc not found: {_BACKTEST_DOC}")
    existing = _BACKTEST_DOC.read_text(encoding="utf-8")
    if not existing.endswith("\n"):
        existing += "\n"
    _BACKTEST_DOC.write_text(existing + "\n" + section_md, encoding="utf-8")


# ── CLI ──

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7,
                        help="Lookback window in days (default: 7)")
    parser.add_argument("--repo", default="huansbox/mlb-fantasy",
                        help="GitHub repo (default: huansbox/mlb-fantasy)")
    parser.add_argument("--label", default="fa-scan",
                        help="GitHub label filter (default: fa-scan)")
    parser.add_argument("--update-doc", action="store_true",
                        help="Append summary to docs/sp-decisions-backtest.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary to stdout (default behaviour)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    stats = run_weekly_summary(args.days, repo=args.repo, label=args.label)
    section_md = format_weekly_section(stats)

    if args.update_doc and not args.dry_run:
        append_to_backtest_doc(section_md)
        print(f"Appended section to {_BACKTEST_DOC}", file=sys.stderr)
    else:
        print(section_md)

    # Also dump stats JSON for downstream consumers
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
