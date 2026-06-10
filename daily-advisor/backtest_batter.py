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
mechanical category scorecard, annotates each episode with whether it was
actually executed (issue 031 — judged from roster_config.json git history,
window = episode first day → last day + grace), and appends a weekly
section (with executed / not-executed split hit-rates) to
`docs/batter-decisions-backtest.md`.

JUDGE PANEL (issue 030): due accounts are packed into ONE payload and sent
to two LLM judges (same instruction, independent claude -p calls from a
neutral cwd — 2 calls/week, never per-account). Each judge makes a forced
A/B choice + 明顯/勉強 margin per account; the consensus table (same pick +
≥1 明顯 → adopted, otherwise 難分) plus the mechanical mirror mapping
(watch accounts: adopted A → miss / else hit) upgrades outcomes to
hit / miss / 難分. The mechanical scorecard stays recorded as the judges'
audit baseline, NOT a verdict (PRD C1 #5: category wins are binary and
magnitude-blind). Accounts whose scorecard is missing become `no-data`;
panel failure (contract violation after retry) fails open — outcomes stay
`pending-judge` and the weekly section carries a warning. Early runs
legitimately output "0 筆可對帳" — the first age-eligible account is
expected 2026-07-01 (028 deployed 2026-06-10 + 21d).

Pure-function primitives live in `_backtest_lib.py` (shared with the SP
backtest). Hit definitions intentionally differ from SP's — hence the
separate output doc.

Usage:
    python3 backtest_batter.py                          # weekly summary to stdout
    python3 backtest_batter.py --update-doc             # append to batter doc
    python3 backtest_batter.py --no-judge               # skip the 2 claude calls
    python3 backtest_batter.py --age-min 0 --update-doc # demo/backfill override
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from _backtest_lib import (
    EXECUTION_GRACE_DAYS,
    BatterVerdict,
    Episode,
    RosterSnapshot,
    batter_episode_key,
    build_judge_payload,
    build_roster_name_index,
    compare_batter_categories,
    dedupe_episodes,
    judge_consensus,
    judge_executed,
    map_judge_outcome,
    parse_batter_verdicts,
    parse_bydaterange_hitting,
    parse_issue_date,
    parse_judge_response,
    parse_roster_snapshot,
    resolve_id_with_fallback,
    select_due_episodes,
)
from _multi_agent import run_single_agent
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

# Judge panel (issue 030). Both judges share ONE instruction file — the
# "split picks = real 難分" inference only holds when the judges differ in
# nothing but sampling. 1 retry per judge mirrors the SP Step A precedent.
_JUDGE_PROMPT_PATH = _MODULE_DIR / "prompt_batter_judge.txt"
_JUDGE_RETRIES = 1

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


# ── Roster git-history timeline (issue 031 boundary) ──

_ROSTER_REL_PATH = "daily-advisor/roster_config.json"


def fetch_roster_timeline(since: date, repo_root: Path | None = None,
                          rel_path: str = _ROSTER_REL_PATH,
                          ) -> list[RosterSnapshot]:
    """Roster membership snapshots from roster_config.json git history.

    One snapshot per commit touching the config since `since`, plus the
    last commit BEFORE `since` (the baseline judge_executed needs to
    establish prior absence). System boundary (subprocess git) — degrades
    to [] on any failure (shallow clone without history, non-repo cwd),
    which judge_executed reports as executed=unknown rather than a wrong
    False.
    """
    repo_root = repo_root or _REPO_ROOT
    since_arg = f"{since.isoformat()}T00:00:00"

    def git_lines(*args: str) -> list[str]:
        proc = subprocess.run(["git", "-C", str(repo_root), *args],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "git failed")
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]

    try:
        entries = git_lines("log", "--format=%H|%cI", f"--since={since_arg}",
                            "--", rel_path)
        entries += git_lines("log", "-1", "--format=%H|%cI",
                             f"--before={since_arg}", "--", rel_path)
        commits = []
        for line in entries:
            sha, _, ciso = line.partition("|")
            commits.append((sha.strip(), ciso.strip()))
        commits.sort(key=lambda c: c[1])  # full ISO timestamp order
        snapshots = []
        for sha, ciso in commits:
            raw = git_lines("show", f"{sha}:{rel_path}")
            config = json.loads("\n".join(raw))
            snapshots.append(
                parse_roster_snapshot(config, date.fromisoformat(ciso[:10])))
        return snapshots
    except Exception as e:  # noqa: BLE001 — boundary: degrade to unknown
        logger.warning("roster timeline fetch failed (%s) — "
                       "executed annotation degrades to unknown", e)
        return []


# ── Judge panel (issue 030 boundary) ──

def _claude_judge_runner(prompt: str, agent_id: str) -> dict | None:
    """One judge call: `claude -p` from a neutral cwd (lever 1a pattern,
    via _multi_agent.run_single_agent) → parsed JSON or None."""
    result = run_single_agent(prompt, agent_id)
    if result.error:
        logger.warning("judge call %s error: %s", agent_id, result.error)
    return result.parsed


def run_judge_panel(rows: list[dict], *, _run_judge=None,
                    window_days: int = _OBSERVATION_DAYS) -> dict:
    """Upgrade pending-judge rows to consensus verdicts, in place.

    The whole week's judgeable accounts go into ONE payload; each of the
    two judges gets it in one call (2 calls/week regardless of account
    count, +1 retry each on contract violation). Rows without a scorecard
    are marked `no-data` (never judgeable). On persistent judge failure
    the panel fails open: rows keep `pending-judge`, the section renders a
    warning, and — because the [21, 28) age window moves on — those
    accounts need a manual --age-min/--age-max re-run to get judged.
    """
    run_judge = _run_judge or _claude_judge_runner
    payload, indices = build_judge_payload(rows, window_days=window_days)
    judgeable = set(indices)
    for i, row in enumerate(rows):
        if i not in judgeable and row.get("outcome") == "pending-judge":
            row["outcome"] = "no-data"
    if not indices:
        return {"status": "no-accounts", "n_calls": 0, "n_accounts": 0}

    prompt = (_JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
              + "\n\n---\n\n" + payload)
    expected = list(range(1, len(indices) + 1))
    judge_maps: list[dict] = []
    n_calls = 0
    for judge_id in ("judge_1", "judge_2"):
        judge_map = None
        for attempt in range(1 + _JUDGE_RETRIES):
            n_calls += 1
            parsed = run_judge(prompt, f"{judge_id}_try{attempt + 1}")
            judge_map = parse_judge_response(parsed, expected_ids=expected)
            if judge_map is not None:
                break
            logger.warning("judge panel: %s attempt %d violated the output "
                           "contract", judge_id, attempt + 1)
        if judge_map is None:
            logger.warning("judge panel: %s failed after retry — outcomes "
                           "stay pending-judge", judge_id)
            return {"status": "failed", "failed_judge": judge_id,
                    "n_calls": n_calls}
        judge_maps.append(judge_map)

    j1, j2 = judge_maps
    for account_id, row_i in zip(expected, indices):
        row = rows[row_i]
        consensus = judge_consensus(j1[account_id], j2[account_id])
        row["judge"] = {"j1": j1[account_id], "j2": j2[account_id],
                        **consensus}
        row["outcome"] = map_judge_outcome(row["kind"], consensus)
    return {"status": "ok", "n_calls": n_calls, "n_accounts": len(indices)}


def aggregate_outcome_by_kind(rows: list[dict]) -> dict:
    """Hit-rate per account kind — the PRD's paired diagnosis (C1 #8):
    replace rate measures 太衝動, watch rate (mirror) measures 太保守.

    Denominator = hit + miss. For watch accounts 難分 maps to hit upstream
    (the verdict confirms the claim), so n_nanfen > 0 only on replace.
    """
    out: dict[str, dict] = {}
    for kind in ("replace", "watch"):
        bucket = [r for r in rows if r.get("kind") == kind]
        judged = [r for r in bucket if r.get("outcome") in ("hit", "miss")]
        hits = [r for r in judged if r["outcome"] == "hit"]
        out[kind] = {
            "n": len(bucket),
            "n_judged": len(judged),
            "n_hits": len(hits),
            "n_nanfen": sum(1 for r in bucket if r.get("outcome") == "難分"),
            "hit_rate": (len(hits) / len(judged)) if judged else None,
        }
    return out


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
                       roster_timeline: list[RosterSnapshot],
                       *, fetch_stats, search_fn) -> list[dict]:
    """Reconcile each due episode into a pending-judge scorecard row.

    The observation window is anchored on the episode start date (first
    occurrence). The execution window runs first occurrence → last
    occurrence + grace (a recommendation keeps repeating while unexecuted,
    so a real execution lands near the episode end). Boundary functions
    are injected so this stays unit-testable without network.
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
        execution = judge_executed(
            roster_timeline, player_name=v.player, player_id=player_id,
            window_start=ep.start_date,
            window_end=ep.end_date + timedelta(days=EXECUTION_GRACE_DAYS))
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
            "executed": execution["executed"],
            "execution": execution,
            "missing": missing,
        })
    return rows


def aggregate_executed_split(rows: list[dict]) -> dict:
    """Hit-rate split by execution status (PRD user story 9).

    Measures whether the user's manual veto adds value (not-executed
    recommendations that would have hit = 誤殺) or filters noise. Judged
    denominator = outcomes in {hit, miss} — pending-judge (pre-030) and
    難分 stay out, so rates appear automatically once the judge panel
    upgrades outcomes. already-rostered counts under executed.
    """
    split: dict[str, dict] = {}
    for group, value in (("executed", True), ("not_executed", False),
                         ("unknown", None)):
        bucket = [r for r in rows if r.get("executed") is value]
        judged = [r for r in bucket if r.get("outcome") in ("hit", "miss")]
        hits = [r for r in judged if r["outcome"] == "hit"]
        split[group] = {
            "n": len(bucket),
            "n_judged": len(judged),
            "n_hits": len(hits),
            "hit_rate": (len(hits) / len(judged)) if judged else None,
        }
    return split


def run_weekly_summary(age_min: int = _DEFAULT_AGE_MIN,
                       age_max: int = _DEFAULT_AGE_MAX,
                       days: int | None = None,
                       repo: str = "huansbox/mlb-fantasy",
                       label: str = "fa-scan",
                       today: date | None = None,
                       _fetch_issues=None,
                       _fetch_stats=None,
                       _search_mlb_id=None,
                       _roster_index=None,
                       _roster_timeline=None,
                       _judge_runner=None) -> dict:
    """Full pipeline: fetch issues → parse batter verdicts → dedupe episodes
    → select due episodes (age in [age_min, age_max)) → six-category
    scorecards → judge panel → stats dict.

    `days` overrides the issue-fetch lookback only (default age_max + slack);
    it does NOT select which episodes get reconciled. Underscore-prefixed
    params are injectable system boundaries for tests (_roster_index included
    — the real roster_config contains the very players test verdicts name).
    `_judge_runner=None` skips the panel entirely (outcomes stay
    pending-judge) — the CLI opts in with the real claude -p runner, so
    library callers and tests never subprocess claude by default.
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

    if _roster_timeline is not None:
        roster_timeline = _roster_timeline
    elif due:
        roster_timeline = fetch_roster_timeline(
            min(e.start_date for e in due))
    else:
        roster_timeline = []  # nothing to judge — skip the git boundary

    rows = build_episode_rows(
        due, roster_index, roster_timeline,
        fetch_stats=fetch_stats, search_fn=search_fn)

    if _judge_runner is not None:
        judge_panel = run_judge_panel(rows, _run_judge=_judge_runner,
                                      window_days=_OBSERVATION_DAYS)
    else:
        judge_panel = {"status": "skipped", "n_calls": 0}

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
        "execution_grace_days": EXECUTION_GRACE_DAYS,
        "executed_split": aggregate_executed_split(rows),
        "judge_panel": judge_panel,
        "outcome_by_kind": aggregate_outcome_by_kind(rows),
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

    Mirrors the SP weekly section style. Outcomes are consensus verdicts
    (issue 030); pending-judge appears only when the panel was skipped
    (--no-judge) or failed its output contract.
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
        *_fmt_judge_lines(stats),
        _fmt_executed_split_line(stats),
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
                f"→ 機械比數 {card_str} → {_fmt_judge_marker(ep.get('judge'))}"
                f"**{ep['outcome']}** "
                f"{_fmt_execution_marker(ep.get('execution'))}{missing}"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def _fmt_judge_lines(stats: dict) -> list[str]:
    panel = stats.get("judge_panel") or {"status": "skipped", "n_calls": 0}
    status = panel.get("status")
    if status == "ok":
        agg = stats.get("outcome_by_kind") or aggregate_outcome_by_kind(
            stats.get("episodes") or [])

        def rate(group: dict) -> str:
            if group["hit_rate"] is None:
                return "—"
            return (f"{group['hit_rate']:.0%}"
                    f"（{group['n_hits']}/{group['n_judged']}）")

        r, w = agg["replace"], agg["watch"]
        return [
            f"- Judge panel（issue 030）: 2 位裁判同指示合議，"
            f"{panel['n_calls']} calls（強制二選一＋明顯/勉強；"
            f"同人+至少一明顯=採用，餘=難分）；機械類別比數僅為稽核底稿，不參與判定",
            f"- 命中率 — replace（量太衝動）: {rate(r)}，難分 {r['n_nanfen']} "
            f"/ watch（鏡像，量太保守；難分=看對計 hit）: {rate(w)}",
        ]
    if status == "failed":
        return [
            f"- ⚠️ Judge panel FAILED（{panel['n_calls']} calls，"
            f"輸出契約連續違反，failed_judge={panel.get('failed_judge')}）— "
            f"outcomes 留 **pending-judge**；本批帳下週會老化出 [21, 28) 窗，"
            f"需手動 `--age-min/--age-max` 重跑補判",
        ]
    if status == "no-accounts":
        return [
            "- Judge panel（issue 030）: 0 筆可判（無完整 scorecard 的帳）— 0 calls",
        ]
    return [
        "- Outcome: all **pending-judge** — judge panel skipped"
        "（--no-judge / library 呼叫未注入 runner）；機械類別比數僅為稽核底稿",
    ]


def _fmt_judge_marker(judge: dict | None) -> str:
    if not judge:
        return ""
    j1, j2 = judge["j1"], judge["j2"]
    consensus = (f"adopted {judge['winner']}"
                 if judge["consensus"] == "adopted" else "難分")
    return (f"裁判 J1 {j1['better']}·{j1['margin']} / "
            f"J2 {j2['better']}·{j2['margin']} ⇒ {consensus} → ")


def _fmt_executed_split_line(stats: dict) -> str:
    split = stats.get("executed_split") or aggregate_executed_split(
        stats.get("episodes") or [])

    def rate(group: dict) -> str:
        if group["hit_rate"] is None:
            return "—"
        return f"{group['hit_rate']:.0%}（{group['n_hits']}/{group['n_judged']}）"

    e, n, u = split["executed"], split["not_executed"], split["unknown"]
    unknown_str = f" / unknown {u['n']}" if u["n"] else ""
    return (
        f"- Executed split（issue 031，roster git 歷史機械判定；"
        f"執行窗 = episode 首日 → 末日 + {stats.get('execution_grace_days', EXECUTION_GRACE_DAYS)}d）: "
        f"executed {e['n']}（hit-rate {rate(e)}）/ "
        f"not-executed {n['n']}（hit-rate {rate(n)}）{unknown_str}"
    )


def _fmt_execution_marker(execution: dict | None) -> str:
    if not execution:
        return "〔execution unknown〕"
    status = execution.get("status")
    if status == "executed":
        return f"〔executed {execution['matched_date']}〕"
    if status == "already-rostered":
        return f"〔already rostered {execution['matched_date']}〕"
    if status == "not-executed":
        return "〔not executed〕"
    return "〔execution unknown〕"


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
    parser.add_argument("--no-judge", action="store_true",
                        help="Skip the judge panel (no claude -p calls); "
                             "outcomes stay pending-judge")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    stats = run_weekly_summary(age_min=args.age_min, age_max=args.age_max,
                               days=args.days, repo=args.repo, label=args.label,
                               _judge_runner=(None if args.no_judge
                                              else _claude_judge_runner))
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
