"""backtest_track — Use Case A: B2 SP-v4 verdict → outcome backtest.

Reads GitHub Issues labelled `fa-scan`, extracts B2 Step B verdicts,
deduplicates them into episodes (same action+targets on adjacent days = one
decision), selects episodes whose age is in the [--age-min, --age-max) window
(default [21, 28) — reconcile only AFTER the 21-day observation window has
fully elapsed; weekly Sunday cron stride 7 means each episode reconciles
exactly once), joins with post-verdict Savant xwOBACON, classifies each
episode as hit / miss / neutral, and appends a weekly summary section to
`docs/sp-decisions-backtest.md`.

This is the quality-monitoring replacement for retired B1 M1/M4' metrics
(see docs/sp-b2-cutover-design.md §"Quality Monitoring").

Use Case B (xwOBACON threshold calibration) is explicitly out of scope — deferred
4-6 weeks post-cutover. Pure-function primitives live in `_backtest_lib.py`.

CLI semantics:
    --age-min / --age-max  episode start-date age window in days, half-open
                           [age_min, age_max). Default 21 / 28. Override
                           (e.g. --age-min 0) is for demo / backfill runs
                           only — the output section is marked as such.
    --days                 issue-fetch lookback upper bound in days. Default:
                           auto (= age_max + 14, enough slack to see the true
                           start of any episode still inside the age window).
                           This flag NO LONGER selects which verdicts get
                           reconciled — that is the age window's job.

Usage:
    python3 backtest_track.py                          # weekly summary to stdout
    python3 backtest_track.py --update-doc             # append to backtest doc
    python3 backtest_track.py --age-min 0 --update-doc # demo/backfill override
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from _backtest_lib import (
    B2Verdict,
    Episode,
    VerdictOutcome,
    aggregate_hit_rate,
    build_roster_name_index,
    dedupe_episodes,
    parse_b2_verdict,
    parse_issue_date,
    resolve_id_with_fallback,
    select_due_episodes,
    verdict_episode_key,
)


_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
_BACKTEST_DOC = _REPO_ROOT / "docs" / "sp-decisions-backtest.md"
_ROSTER_CONFIG = _MODULE_DIR / "roster_config.json"

# Post-verdict observation window. Short enough to surface fast feedback,
# long enough for SP signal noise to settle.
_OBSERVATION_DAYS = 21

# Default reconciliation-age window [min, max) in days. age_min equals the
# observation window so no episode is reconciled before its window elapsed;
# age_max = age_min + 7 pairs with the weekly cron stride so each episode
# is reconciled exactly once.
_DEFAULT_AGE_MIN = _OBSERVATION_DAYS
_DEFAULT_AGE_MAX = _OBSERVATION_DAYS + 7

# Slack added to age_max for the auto issue-fetch lookback: an episode whose
# start is inside the age window may have begun a couple of scan days before
# the oldest fetched issue would otherwise reveal; 14 extra days comfortably
# covers realistic episode chain lengths.
_FETCH_LOOKBACK_SLACK = 14

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
        encoding="utf-8",  # issue titles contain CJK; never trust locale codec
    )
    issues = json.loads(result.stdout)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        i for i in issues
        if datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")) >= cutoff
    ]


# ── Outcome data fetch ──

def fetch_post_verdict_xwobacon(mlb_id: int, start_date: date,
                                window_days: int = _OBSERVATION_DAYS,
                                fetch_pitches=None) -> float | None:
    """Fetch SP's xwOBACON over [start_date, start_date + window_days).

    Reuses savant_rolling's pitch-level fetch + local aggregation (same
    Savant statcast_search/csv endpoint pattern, arbitrary date window
    instead of a today-anchored lookback). Returns None when the player had
    no BBE in the window (no starts / IL / future dates) — callers classify
    that as neutral.

    Args:
        fetch_pitches: injectable fetcher with savant_rolling's
            `_fetch_player_pitches(mlb_id, start, end, player_type)`
            signature; tests pass a fake so no network is touched.
    """
    if fetch_pitches is None:
        from savant_rolling import _fetch_player_pitches as fetch_pitches
    from savant_rolling import _aggregate_pitches

    start_str = start_date.isoformat()
    # Savant's game_date_gt/lt are inclusive; half-open window of N days ends
    # at start + N - 1.
    end_str = (start_date + timedelta(days=window_days - 1)).isoformat()
    rows = fetch_pitches(mlb_id, start_str, end_str, "pitcher")
    metrics = _aggregate_pitches(rows, "pitcher")
    return metrics.get("xwobacon")


def search_mlb_id(name: str) -> int | None:
    """Resolve a player name to mlb_id via MLB Stats API people/search.

    System boundary (network) — used as the fallback when a verdict target
    is no longer (or never was) in roster_config: dropped SPs and FA
    watch/add targets. Not unit-tested; tests inject a fake.
    """
    if not name:
        return None
    qs = urllib.parse.urlencode(
        {"names": name, "sportIds": 1, "active": "true"})
    url = f"https://statsapi.mlb.com/api/v1/people/search?{qs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        people = data.get("people") or []
        return int(people[0]["id"]) if people else None
    except Exception as e:  # noqa: BLE001 — boundary: degrade to unresolved
        logger.warning("MLB id search failed for %r: %s", name, e)
        return None


# ── Outcome classification ──


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
                       in this branch; see build_episode_outcomes.)
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


def build_episode_outcomes(episodes: list[Episode], roster_index: dict[str, int],
                           *, fetch_xwobacon, search_fn) -> list[VerdictOutcome]:
    """Classify each due episode using its representative (first) verdict.

    The observation window is anchored on the episode start date. Boundary
    functions are injected so this stays unit-testable without network.
    """
    outcomes: list[VerdictOutcome] = []
    for ep in episodes:
        v: B2Verdict = ep.first
        drop_id = resolve_id_with_fallback(v.drop, roster_index, search_fn)
        add_id = resolve_id_with_fallback(v.add or v.watch_target, roster_index, search_fn)

        post_drop = (
            fetch_xwobacon(drop_id, ep.start_date) if drop_id else None
        )
        post_add = (
            fetch_xwobacon(add_id, ep.start_date) if add_id else None
        )
        outcomes.append(classify_outcome(v, post_drop, post_add))
    return outcomes


def run_weekly_summary(age_min: int = _DEFAULT_AGE_MIN,
                       age_max: int = _DEFAULT_AGE_MAX,
                       days: int | None = None,
                       repo: str = "huansbox/mlb-fantasy",
                       label: str = "fa-scan",
                       today: date | None = None,
                       _fetch_issues=None,
                       _fetch_xwobacon=None,
                       _search_mlb_id=None) -> dict:
    """Full pipeline: fetch issues → parse verdicts → dedupe episodes →
    select due episodes (age in [age_min, age_max)) → classify → aggregate.

    `days` overrides the issue-fetch lookback only (default age_max + slack);
    it does NOT select which episodes get reconciled. Underscore-prefixed
    params are injectable system boundaries for tests.
    """
    today = today or date.today()
    fetch_issues = _fetch_issues or fetch_recent_issues
    fetch_xwobacon = _fetch_xwobacon or fetch_post_verdict_xwobacon
    search_fn = _search_mlb_id or search_mlb_id

    lookback = days if days is not None else age_max + _FETCH_LOOKBACK_SLACK
    issues = fetch_issues(lookback, repo=repo, label=label)
    verdicts = collect_verdicts(issues)
    episodes = dedupe_episodes(
        verdicts, key_fn=verdict_episode_key, date_fn=lambda v: v.issue_date)
    due = select_due_episodes(
        episodes, on_date=today, age_min=age_min, age_max=age_max)

    try:
        roster_config = json.loads(_ROSTER_CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        roster_config = {}
    roster_index = build_roster_name_index(roster_config)

    outcomes = build_episode_outcomes(
        due, roster_index, fetch_xwobacon=fetch_xwobacon, search_fn=search_fn)

    stats = aggregate_hit_rate(outcomes)
    stats["age_window"] = [age_min, age_max]
    stats["age_window_is_override"] = (
        (age_min, age_max) != (_DEFAULT_AGE_MIN, _DEFAULT_AGE_MAX))
    stats["fetch_lookback_days"] = lookback
    stats["observation_window_days"] = _OBSERVATION_DAYS
    stats["run_date"] = today.isoformat()
    stats["n_episodes_in_lookback"] = len(episodes)
    stats["date_range"] = _date_range(due)
    stats["episodes"] = [
        {
            "start_date": ep.start_date.isoformat(),
            "end_date": ep.end_date.isoformat(),
            "n_occurrences": len(ep.occurrences),
            "action": ep.first.action,
            "drop": ep.first.drop,
            "add": ep.first.add,
            "watch_target": ep.first.watch_target,
            "outcome": outcome.outcome_label,
            "marginal_benefit": outcome.marginal_benefit,
        }
        for ep, outcome in zip(due, outcomes)
    ]
    return stats


def _date_range(episodes: list[Episode]) -> list[str] | None:
    if not episodes:
        return None
    dates = sorted(e.start_date for e in episodes)
    return [dates[0].isoformat(), dates[-1].isoformat()]


# ── Markdown append ──

def format_weekly_section(stats: dict) -> str:
    """Render the weekly summary as appendable markdown.

    Inserted under a new section in docs/sp-decisions-backtest.md.
    """
    range_str = (" ~ ".join(stats["date_range"]) if stats["date_range"]
                 else "no due episodes")
    today_str = stats.get("run_date") or date.today().isoformat()
    age_min, age_max = stats["age_window"]
    lines = [
        f"## Weekly Backtest {today_str} ({range_str})",
        "",
        f"- Episode age window: [{age_min}, {age_max}) days; "
        f"post-verdict observation: {stats['observation_window_days']} days; "
        f"issue lookback: {stats['fetch_lookback_days']} days",
    ]
    if stats.get("age_window_is_override"):
        lines.append(
            f"- ⚠️ **OVERRIDE DEMO RUN** — non-default age window "
            f"(--age-min {age_min} --age-max {age_max}); episodes younger than "
            f"{stats['observation_window_days']} days have NOT completed their "
            f"observation window. Not comparable with regular weekly sections."
        )
    lines += [
        f"- Episodes due this run: {stats['n_total']} "
        f"(actionable: {stats['n_actionable']}; "
        f"episodes in lookback: {stats.get('n_episodes_in_lookback', '?')})",
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
    episodes = stats.get("episodes") or []
    if episodes:
        lines.append("")
        lines.append("Episodes:")
        for ep in episodes:
            target = (
                f"drop {ep['drop']} → add {ep['add']}"
                if ep["action"] == "drop_X_add_Y"
                else (f"watch {ep['watch_target']}" if ep["action"] == "watch"
                      else "pass")
            )
            benefit = (f", Δ {ep['marginal_benefit']:+.3f}"
                       if ep.get("marginal_benefit") is not None else "")
            lines.append(
                f"- {ep['start_date']} ({ep['n_occurrences']}d) `{ep['action']}` "
                f"{target} → **{ep['outcome']}**{benefit}"
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
    parser.add_argument("--age-min", type=int, default=_DEFAULT_AGE_MIN,
                        help=f"Min episode age in days, inclusive "
                             f"(default: {_DEFAULT_AGE_MIN}). Override to 0 "
                             f"for demo/backfill runs (section gets marked).")
    parser.add_argument("--age-max", type=int, default=_DEFAULT_AGE_MAX,
                        help=f"Max episode age in days, exclusive "
                             f"(default: {_DEFAULT_AGE_MAX})")
    parser.add_argument("--days", type=int, default=None,
                        help="Issue-fetch lookback in days (default: auto = "
                             "age-max + 14). Does NOT select which episodes "
                             "are reconciled — the age window does.")
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

    stats = run_weekly_summary(age_min=args.age_min, age_max=args.age_max,
                               days=args.days, repo=args.repo, label=args.label)
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
