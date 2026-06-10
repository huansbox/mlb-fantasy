"""backtest_batter — batter decision backtest skeleton (issue 029).

Reads GitHub Issues labelled `fa-scan`, extracts batter verdicts from the
```waiver-log``` block (issue-028 grammar: ACTION lines → replace accounts,
7-field NEW lines with a vs target → watch accounts), deduplicates them into
episodes (shared issue-027 primitives — same claim on adjacent days = one
decision), selects episodes whose age is in [--age-min, --age-max) (default
[21, 28) — reconcile only AFTER the 21-day observation window has fully
elapsed; weekly Sunday cron stride 7 means each episode reconciles exactly
once), fetches both sides' six-category actual production (R/HR/RBI/BB/AVG/
OPS, no SB — soft punt) over the window via MLB byDateRange, records the
mechanical category scorecard, and appends a weekly section to
`docs/batter-decisions-backtest.md`.

SKELETON SEMANTICS (tracer bullet): every episode outcome is labelled
`pending-judge` — hit/miss classification is the judge panel's job
(issue 030: 2 judges, forced A/B choice + 明顯/勉強 annotation, consensus
table). The mechanical scorecard recorded here is the judges' audit
baseline, NOT a verdict (PRD C1 #5: category wins are binary and
magnitude-blind). Early runs legitimately output "0 筆可對帳" — the first
age-eligible account is expected 2026-07-01 (028 deployed 2026-06-10 + 21d).

Pure-function primitives live in `_backtest_lib.py` (shared with the SP
backtest). Hit definitions intentionally differ from SP's — hence the
separate output doc.

Usage:
    python3 backtest_batter.py                          # weekly summary to stdout
    python3 backtest_batter.py --update-doc             # append to batter doc
    python3 backtest_batter.py --age-min 0 --update-doc # demo/backfill override
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from _backtest_lib import (
    BatterVerdict,
    Episode,
    batter_episode_key,
    build_roster_name_index,
    compare_batter_categories,
    dedupe_episodes,
    parse_batter_verdicts,
    parse_bydaterange_hitting,
    parse_issue_date,
    resolve_id_with_fallback,
    select_due_episodes,
)
from backtest_track import fetch_recent_issues, search_mlb_id

_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
_BATTER_DOC = _REPO_ROOT / "docs" / "batter-decisions-backtest.md"
_ROSTER_CONFIG = _MODULE_DIR / "roster_config.json"

# Post-verdict observation window (days). Same length as the SP side —
# both feed the Sunday cron's [21, 28) reconciliation-age window.
_OBSERVATION_DAYS = 21
_DEFAULT_AGE_MIN = _OBSERVATION_DAYS
_DEFAULT_AGE_MAX = _OBSERVATION_DAYS + 7
_FETCH_LOOKBACK_SLACK = 14

logger = logging.getLogger(__name__)


# ── Outcome data fetch ──

def fetch_batter_window_stats(mlb_id: int, start_date: date,
                              window_days: int = _OBSERVATION_DAYS) -> dict | None:
    """Six-category actual production over [start_date, start_date + window).

    Person-level byDateRange — MLB aggregates the game log server-side over
    the date window (endpoints inclusive; a half-open window of N days ends
    at start + N - 1). System boundary (network) — tests inject a fake via
    run_weekly_summary; the response parse is the unit-tested
    parse_bydaterange_hitting. Returns None on no games or fetch error.
    """
    end = start_date + timedelta(days=window_days - 1)
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        f"?stats=byDateRange&group=hitting"
        f"&startDate={start_date.isoformat()}&endDate={end.isoformat()}"
        f"&season={start_date.year}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — boundary: degrade to no-data
        logger.warning("byDateRange fetch failed for %s: %s", mlb_id, e)
        return None
    return parse_bydaterange_hitting(data)


# ── Aggregate pipeline ──

def collect_batter_verdicts(issues: list[dict]) -> list[BatterVerdict]:
    """Parse a list of GitHub Issue dicts into BatterVerdict objects.

    Issues without a waiver-log block (SP issues) or with only
    non-reconcilable lines (pre-028 grammar, UPDATE/CLOSE) contribute
    nothing — all expected non-matches, silently skipped.
    """
    verdicts: list[BatterVerdict] = []
    for issue in issues:
        body = issue.get("body") or ""
        d = parse_issue_date(issue.get("createdAt") or "")
        verdicts.extend(parse_batter_verdicts(body, d))
    return verdicts


def build_episode_rows(episodes: list[Episode], roster_index: dict[str, int],
                       *, fetch_stats, search_fn) -> list[dict]:
    """Reconcile each due episode into a pending-judge scorecard row.

    The observation window is anchored on the episode start date (first
    occurrence). Boundary functions are injected so this stays
    unit-testable without network.
    """
    rows: list[dict] = []
    for ep in episodes:
        v: BatterVerdict = ep.first
        missing: list[str] = []
        player_id = resolve_id_with_fallback(v.player, roster_index, search_fn)
        vs_id = resolve_id_with_fallback(v.vs, roster_index, search_fn)
        if player_id is None:
            missing.append(f"unresolved id: {v.player}")
        if vs_id is None:
            missing.append(f"unresolved id: {v.vs}")
        player_stats = fetch_stats(player_id, ep.start_date) if player_id else None
        vs_stats = fetch_stats(vs_id, ep.start_date) if vs_id else None
        if player_id is not None and player_stats is None:
            missing.append(f"no window data: {v.player}")
        if vs_id is not None and vs_stats is None:
            missing.append(f"no window data: {v.vs}")
        rows.append({
            "start_date": ep.start_date.isoformat(),
            "end_date": ep.end_date.isoformat(),
            "n_occurrences": len(ep.occurrences),
            "kind": v.kind,
            "replace_type": v.replace_type,
            "player": v.player,
            "vs": v.vs,
            "outcome": "pending-judge",
            "scorecard": compare_batter_categories(player_stats, vs_stats),
            "missing": missing,
        })
    return rows


def run_weekly_summary(age_min: int = _DEFAULT_AGE_MIN,
                       age_max: int = _DEFAULT_AGE_MAX,
                       days: int | None = None,
                       repo: str = "huansbox/mlb-fantasy",
                       label: str = "fa-scan",
                       today: date | None = None,
                       _fetch_issues=None,
                       _fetch_stats=None,
                       _search_mlb_id=None,
                       _roster_index=None) -> dict:
    """Full pipeline: fetch issues → parse batter verdicts → dedupe episodes
    → select due episodes (age in [age_min, age_max)) → six-category
    scorecards → stats dict.

    `days` overrides the issue-fetch lookback only (default age_max + slack);
    it does NOT select which episodes get reconciled. Underscore-prefixed
    params are injectable system boundaries for tests (_roster_index included
    — the real roster_config contains the very players test verdicts name).
    """
    today = today or date.today()
    fetch_issues = _fetch_issues or fetch_recent_issues
    fetch_stats = _fetch_stats or fetch_batter_window_stats
    search_fn = _search_mlb_id or search_mlb_id

    lookback = days if days is not None else age_max + _FETCH_LOOKBACK_SLACK
    issues = fetch_issues(lookback, repo=repo, label=label)
    verdicts = collect_batter_verdicts(issues)
    episodes = dedupe_episodes(
        verdicts, key_fn=batter_episode_key, date_fn=lambda v: v.issue_date)
    due = select_due_episodes(
        episodes, on_date=today, age_min=age_min, age_max=age_max)

    if _roster_index is not None:
        roster_index = _roster_index
    else:
        try:
            roster_config = json.loads(_ROSTER_CONFIG.read_text(encoding="utf-8"))
        except FileNotFoundError:
            roster_config = {}
        roster_index = build_roster_name_index(roster_config)

    rows = build_episode_rows(
        due, roster_index, fetch_stats=fetch_stats, search_fn=search_fn)

    return {
        "run_date": today.isoformat(),
        "age_window": [age_min, age_max],
        "age_window_is_override": (
            (age_min, age_max) != (_DEFAULT_AGE_MIN, _DEFAULT_AGE_MAX)),
        "observation_window_days": _OBSERVATION_DAYS,
        "fetch_lookback_days": lookback,
        "n_total": len(rows),
        "n_replace": sum(1 for r in rows if r["kind"] == "replace"),
        "n_watch": sum(1 for r in rows if r["kind"] == "watch"),
        "n_episodes_in_lookback": len(episodes),
        "date_range": _date_range(due),
        "episodes": rows,
    }


def _date_range(episodes: list[Episode]) -> list[str] | None:
    if not episodes:
        return None
    dates = sorted(e.start_date for e in episodes)
    return [dates[0].isoformat(), dates[-1].isoformat()]


# ── Markdown append ──

def format_batter_weekly_section(stats: dict) -> str:
    """Render the weekly batter summary as appendable markdown.

    Mirrors the SP weekly section style; outcomes stay pending-judge until
    issue 030 wires the judge panel.
    """
    range_str = (" ~ ".join(stats["date_range"]) if stats["date_range"]
                 else "no due episodes")
    age_min, age_max = stats["age_window"]
    lines = [
        f"## Weekly Batter Backtest {stats['run_date']} ({range_str})",
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
    zero_marker = " — 0 筆可對帳" if stats["n_total"] == 0 else ""
    lines += [
        f"- Episodes due this run: {stats['n_total']} "
        f"(replace {stats['n_replace']} / watch {stats['n_watch']}; "
        f"episodes in lookback: {stats['n_episodes_in_lookback']}){zero_marker}",
        "- Outcome: all **pending-judge** — 裁判合議（issue 030）上線後升級為 "
        "hit/miss；機械類別比數僅為稽核底稿，不參與判定",
    ]
    rows = stats.get("episodes") or []
    if rows:
        lines.append("")
        lines.append("Episodes:")
        for ep in rows:
            if ep["kind"] == "replace":
                target = (f"`replace/{ep['replace_type']}` "
                          f"add {ep['player']} ⇄ drop {ep['vs']}")
            else:
                target = f"`watch` watch {ep['player']} vs {ep['vs']}"
            card = ep["scorecard"]
            card_str = (
                f"FA {card['wins']}W-{card['losses']}L-{card['ties']}T"
                if card else "no data")
            missing = f"（{'; '.join(ep['missing'])}）" if ep["missing"] else ""
            lines.append(
                f"- {ep['start_date']} ({ep['n_occurrences']}d) {target} "
                f"→ 機械比數 {card_str} → **{ep['outcome']}**{missing}"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def append_to_batter_doc(section_md: str, doc_path: Path | None = None) -> None:
    """Append section to the batter backtest doc. Idempotent only on date —
    re-running same day appends a duplicate section; user reviews before
    commit (cron commits blindly, mirroring the SP wrapper)."""
    doc = Path(doc_path) if doc_path is not None else _BATTER_DOC
    if not doc.exists():
        raise FileNotFoundError(f"batter backtest doc not found: {doc}")
    existing = doc.read_text(encoding="utf-8")
    if not existing.endswith("\n"):
        existing += "\n"
    doc.write_text(existing + "\n" + section_md, encoding="utf-8")


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
                        help="Append summary to docs/batter-decisions-backtest.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary to stdout (default behaviour)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    stats = run_weekly_summary(age_min=args.age_min, age_max=args.age_max,
                               days=args.days, repo=args.repo, label=args.label)
    section_md = format_batter_weekly_section(stats)

    if args.update_doc and not args.dry_run:
        append_to_batter_doc(section_md)
        print(f"Appended section to {_BATTER_DOC}", file=sys.stderr)
    else:
        print(section_md)

    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
