"""_backtest_lib — shared pure-function primitives for decision backtests.

Two consumers share this library (PRD: episode dedup / age selection /
resolution written once, not twice):

- SP   (issue 024/027): backtest_track.py — B2 fa-scan SP-v4 issues →
  Step B verdicts → episodes → post-verdict Savant xwOBACON → hit-rate.
- Batter (issue 029): backtest_batter.py — batter fa-scan issues →
  waiver-log block verdicts (issue-028 grammar) → episodes → 21-day
  six-category actual production (R/HR/RBI/BB/AVG/OPS, no SB) →
  mechanical scorecard, outcome pending-judge until the judge panel
  (issue 030) upgrades it.

Use Case B (xwOBACON threshold calibration, future): explicitly deferred to
4-6 weeks post-cutover. Same primitives will be reused.

This module is pure parsing + ID resolution. Production data fetch
(Savant / Yahoo / MLB Stats API) is performed by callers; this layer is
unit-testable without network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from name_match import normalize_name as _normalize


# ── Data classes ──

@dataclass(frozen=True)
class B2Verdict:
    """One SP-v4 decision extracted from a B2 fa-scan GitHub Issue body.

    Mirrors the Step B output schema from prompt_sp_b2_step_b.txt:
    action ∈ {drop_X_add_Y, watch, pass}; drop / add / watch_target may be None.
    """
    issue_date: date
    action: str
    drop: str | None
    add: str | None
    watch_target: str | None
    reason: str


@dataclass(frozen=True)
class ResolvedPlayer:
    """Result of name → mlb_id resolution."""
    name: str
    mlb_id: int | None
    source: str  # "roster_config" / "hand_tag" / "mlb_api" / "unresolved"


# ── B2 issue body parsing ──

# Locates the "=== SP-v4 B2 Step B (final verdict) ===" header inside Issue
# bodies. Production issues wrap the whole raw dump in a ``` code fence inside
# a <details> fold, so the JSON object is followed by "```\n\n</details>" —
# NOT by another "===" header or end-of-string. The old anchor-suffix regex
# (`(\{.*?\})\s*(?:\n\s*===|$)`) therefore matched zero production bodies
# while passing hand-written test samples ("tests green, production dead",
# 2026-06-10 finding). The fix: anchor only on the header, then extract the
# first *balanced* JSON object after it (string-aware brace scan) — wrapper
# chrome after the closing brace is irrelevant. Bodies fetched via
# `gh --json body` may carry \r\n line endings; both the header regex and the
# brace scan are line-ending agnostic.
_STEP_B_HEADER_RE = re.compile(
    r"===\s*SP-v4\s+B2\s+Step\s+B\s+\(final\s+verdict\)\s*===",
)


def _extract_json_object(text: str, start: int) -> str | None:
    """Return the first balanced top-level JSON object in text[start:].

    String-aware: braces inside JSON string values (and escaped quotes) do
    not affect the depth count. Returns None when no opening brace is found
    or the object never closes (truncated body).
    """
    i = text.find("{", start)
    if i == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
    return None


def parse_b2_verdict(issue_body: str, issue_date: date) -> B2Verdict | None:
    """Extract one B2 SP-v4 verdict from an issue body.

    Handles both the production format (Step B block inside a ``` fence +
    <details> fold) and the bare raw-dump format (header + JSON, no wrapper).
    Returns None when the body lacks a B2 Step B block (pre-cutover issues,
    other label issues, malformed payload).
    """
    if not issue_body:
        return None
    header = _STEP_B_HEADER_RE.search(issue_body)
    if not header:
        return None
    raw_json = _extract_json_object(issue_body, header.end())
    if raw_json is None:
        return None
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    action = parsed.get("action")
    if action not in {"drop_X_add_Y", "watch", "pass"}:
        return None
    return B2Verdict(
        issue_date=issue_date,
        action=action,
        drop=parsed.get("drop"),
        add=parsed.get("add"),
        watch_target=parsed.get("watch_target"),
        reason=parsed.get("reason") or "",
    )


def parse_issue_date(created_at: str) -> date:
    """Parse GitHub Issue createdAt ISO string to local date.

    Falls through to today on parse error — caller decides what to do."""
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return date.today()


# ── Player ID resolution ──

def build_roster_name_index(roster_config: dict) -> dict[str, int]:
    """Build normalized-name → mlb_id index from roster_config.json.

    Combines `batters` + `pitchers` lists. Used as the primary lookup source
    in the fallback chain (per design doc §3.4).
    """
    index: dict[str, int] = {}
    for section in ("batters", "pitchers"):
        for player in roster_config.get(section, []) or []:
            name = player.get("name")
            mlb_id = player.get("mlb_id")
            if name and mlb_id:
                index[_normalize(name)] = int(mlb_id)
    return index


def resolve_player(name: str, roster_index: dict[str, int],
                   hand_tags: dict[str, int] | None = None) -> ResolvedPlayer:
    """Resolve a verdict name to mlb_id using fallback chain.

    Order per design doc §3.4:
      1. hand_tags (most authoritative — disambiguates homonyms)
      2. roster_config (current team players)
      3. unresolved (caller may dispatch MLB API search if needed)

    Args:
        name: player name from a B2 verdict (drop / add / watch_target).
        roster_index: pre-built name→id index (see build_roster_name_index).
        hand_tags: optional explicit normalized-name → mlb_id overrides.
    """
    if not name:
        return ResolvedPlayer(name="", mlb_id=None, source="unresolved")
    norm = _normalize(name)
    if hand_tags and norm in hand_tags:
        return ResolvedPlayer(name=name, mlb_id=hand_tags[norm], source="hand_tag")
    if norm in roster_index:
        return ResolvedPlayer(name=name, mlb_id=roster_index[norm], source="roster_config")
    return ResolvedPlayer(name=name, mlb_id=None, source="unresolved")


def resolve_id_with_fallback(name: str | None, roster_index: dict[str, int],
                             search_fn) -> int | None:
    """roster_config lookup first, injected MLB Stats API search fallback.

    Dropped players and FA add/watch targets are usually NOT in the current
    roster_config — without the API fallback they would all classify
    neutral (the pre-027 SP failure mode). Shared by both backtest CLIs.
    """
    if not name:
        return None
    resolved = resolve_player(name, roster_index)
    if resolved.mlb_id is not None:
        return resolved.mlb_id
    return search_fn(name)


# ── Episode dedup + reconciliation-age selection ──
#
# Shared by the SP backtest (backtest_track.py) and the batter backtest
# (issue 029) — both reconcile "one recommendation episode" rather than one
# raw daily occurrence. Keep these pure and generic (key_fn / date_fn
# injection) so the batter side can import them unchanged.

@dataclass(frozen=True)
class Episode:
    """One deduplicated recommendation episode.

    The same (action, drop, add, watch_target) combination repeated on
    adjacent scan days is ONE decision, not N. `start_date` (first
    occurrence) anchors the post-verdict observation window.
    """
    key: tuple
    start_date: date
    end_date: date
    occurrences: tuple  # original items in date order

    @property
    def first(self):
        """Representative item — the first occurrence."""
        return self.occurrences[0]


def verdict_episode_key(verdict: B2Verdict) -> tuple:
    """Episode identity for SP B2 verdicts: same action + same targets."""
    return (verdict.action, verdict.drop, verdict.add, verdict.watch_target)


def dedupe_episodes(items, *, key_fn, date_fn, max_gap_days: int = 2) -> list[Episode]:
    """Collapse same-key items on adjacent dates into episodes.

    A chain continues while the date gap to the previous occurrence is
    <= max_gap_days (default 2 — daily scans occasionally skip a day);
    a larger gap starts a new episode for the same key. Different keys
    never merge.

    Args:
        items: iterable of arbitrary objects (B2Verdict for SP).
        key_fn: item -> hashable episode identity.
        date_fn: item -> datetime.date of the occurrence.
        max_gap_days: max tolerated gap (in days) within one episode.

    Returns:
        Episodes sorted by (start_date, key) for deterministic output.
    """
    by_key: dict[tuple, list] = {}
    for item in items:
        by_key.setdefault(key_fn(item), []).append(item)

    episodes: list[Episode] = []
    for key, group in by_key.items():
        group = sorted(group, key=date_fn)
        chain = [group[0]]
        for item in group[1:]:
            if (date_fn(item) - date_fn(chain[-1])).days <= max_gap_days:
                chain.append(item)
            else:
                episodes.append(Episode(
                    key=key, start_date=date_fn(chain[0]),
                    end_date=date_fn(chain[-1]), occurrences=tuple(chain),
                ))
                chain = [item]
        episodes.append(Episode(
            key=key, start_date=date_fn(chain[0]),
            end_date=date_fn(chain[-1]), occurrences=tuple(chain),
        ))
    episodes.sort(key=lambda e: (e.start_date, repr(e.key)))
    return episodes


def select_due_episodes(episodes: list[Episode], *, on_date: date,
                        age_min: int = 21, age_max: int = 28) -> list[Episode]:
    """Pick episodes whose start-date age (in days) is in [age_min, age_max).

    With the weekly Sunday cron (stride exactly 7 days) and the default
    [21, 28) window, every episode start date falls into exactly one weekly
    run — each episode is reconciled exactly once, and only after its 21-day
    observation window has fully elapsed.
    """
    return [
        e for e in episodes
        if age_min <= (on_date - e.start_date).days < age_max
    ]


# ── Batter waiver-log verdict parsing (issue 029) ──
#
# Verdict source = the ```waiver-log``` fenced block at the tail of batter
# fa-scan issues (issue-028 grammar). Reconciled accounts per PRD C1 #2:
# 取代/立即取代 (ACTION lines) + 觀察 (7-field NEW lines with a vs target).
# UPDATE / CLOSE / pre-028 6-field NEW rows are not reconcilable — the first
# reconcilable account exists only after the 028 deploy (2026-06-10).
# Field-split rules mirror the writer (fa_scan.apply_waiver_log_block).

# Mirrors fa_scan._ACTION_TYPES — kept local so this module stays free of
# the fa_scan import graph (Yahoo/Savant production deps).
_BATTER_ACTION_TYPES = ("立即取代", "取代")

_WAIVER_BLOCK_RE = re.compile(r"```waiver-log[ \t]*\r?\n(.*?)```", re.DOTALL)

#: Six reconciled categories (league 7×7 batter cats minus SB — soft punt).
BATTER_CATEGORIES = ("R", "HR", "RBI", "BB", "AVG", "OPS")


@dataclass(frozen=True)
class BatterVerdict:
    """One reconcilable batter recommendation from a waiver-log block.

    kind: "replace" (取代/立即取代 — claim: player outproduces vs) or
    "watch" (觀察 — claim: player has NOT clearly outproduced vs yet;
    mirror-judged per PRD C1 #8). `vs` is the my-team comparison target.
    """
    issue_date: date
    kind: str
    player: str
    vs: str
    replace_type: str | None  # 取代 / 立即取代 — replace kind only


def extract_waiver_log_block(issue_body: str) -> str | None:
    """Return the first ```waiver-log``` fenced block body, stripped.

    Batter issues carry exactly one block (verified on production archive);
    SP issues carry none. Line-ending agnostic (gh --json body may carry
    \\r\\n). Returns None when no block exists, "" for an empty block
    (prompt spec: 無任何行動 → 空區塊).
    """
    if not issue_body:
        return None
    m = _WAIVER_BLOCK_RE.search(issue_body)
    if m is None:
        return None
    return m.group(1).strip()


def parse_batter_verdicts(issue_body: str, issue_date: date) -> list[BatterVerdict]:
    """Extract reconcilable batter verdicts from one issue body.

    Two passes mirroring the writer: ACTION lines are collected first so a
    same-block NEW for the same player emits ONE replace verdict, never an
    additional watch. Document order preserved; duplicates (same episode
    key) within a block collapse to the first occurrence.
    """
    block = extract_waiver_log_block(issue_body)
    if not block:
        return []
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]

    actions: dict[str, tuple[str, str]] = {}
    for line in lines:
        parts = line.split("|")
        if parts[0] != "ACTION" or len(parts) < 4:
            continue
        name, rtype, vs = parts[1].strip(), parts[2].strip(), parts[3].strip()
        if rtype not in _BATTER_ACTION_TYPES or not name or not vs:
            continue
        actions.setdefault(name, (rtype, vs))

    verdicts: list[BatterVerdict] = []
    seen: set[tuple] = set()

    def _emit(v: BatterVerdict) -> None:
        key = batter_episode_key(v)
        if key not in seen:
            seen.add(key)
            verdicts.append(v)

    for line in lines:
        parts = line.split("|")
        if parts[0] == "ACTION" and len(parts) >= 4:
            name = parts[1].strip()
            if name in actions:
                rtype, vs = actions[name]
                _emit(BatterVerdict(issue_date=issue_date, kind="replace",
                                    player=name, vs=vs, replace_type=rtype))
        elif parts[0] == "NEW" and len(parts) >= 7:
            # 7-field row (issue 028) — parts[5] is the vs column. Pre-028
            # 6-field rows (len 6) carry no vs and are not reconcilable.
            name, vs = parts[1].strip(), parts[5].strip()
            if name and vs and name not in actions:
                _emit(BatterVerdict(issue_date=issue_date, kind="watch",
                                    player=name, vs=vs, replace_type=None))
    return verdicts


def batter_episode_key(verdict: BatterVerdict) -> tuple:
    """Episode identity for batter verdicts: kind + normalized name pair.

    replace_type intensity (取代 vs 立即取代) does NOT split episodes —
    same comparison claim, different urgency. watch and replace on the same
    pair ARE distinct accounts (different claims, mirrored hit directions).
    Names normalized so day-to-day accent drift doesn't split a chain.
    """
    return (verdict.kind, _normalize(verdict.player), _normalize(verdict.vs))


# ── Batter six-category window stats (issue 029) ──


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stat_int(stat: dict, key: str) -> int:
    try:
        return int(stat.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def parse_bydaterange_hitting(data: dict) -> dict | None:
    """Parse a person byDateRange hitting response into six-category stats.

    Returns {"R","HR","RBI","BB","AVG","OPS","G"} or None when the window
    contains no games (empty splits — IL / not yet called up / future).

    MLB API quirk (pinned by real fixture): a single-team player may get
    DUPLICATE identical splits — dedupe by content before aggregating, or
    counting categories double. A mid-window trade yields one split per
    team: counting categories are summed and AVG/OPS recomputed from summed
    components (ratios must not be averaged).
    """
    splits = (data.get("stats") or [{}])[0].get("splits") or []
    unique, seen = [], set()
    for s in splits:
        fingerprint = json.dumps(
            {"team": (s.get("team") or {}).get("id"), "stat": s.get("stat")},
            sort_keys=True, default=str)
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(s)
    if not unique:
        return None
    if len(unique) == 1:
        st = unique[0].get("stat", {})
        return {
            "R": _stat_int(st, "runs"),
            "HR": _stat_int(st, "homeRuns"),
            "RBI": _stat_int(st, "rbi"),
            "BB": _stat_int(st, "baseOnBalls"),
            "AVG": _safe_float(st.get("avg")),
            "OPS": _safe_float(st.get("ops")),
            "G": _stat_int(st, "gamesPlayed"),
        }

    def total(key: str) -> int:
        return sum(_stat_int(s.get("stat", {}), key) for s in unique)

    hits, ab = total("hits"), total("atBats")
    bb, hbp, sf, tb = (total("baseOnBalls"), total("hitByPitch"),
                       total("sacFlies"), total("totalBases"))
    avg = round(hits / ab, 4) if ab else None
    obp_den = ab + bb + hbp + sf
    obp = (hits + bb + hbp) / obp_den if obp_den else None
    slg = tb / ab if ab else None
    ops = round(obp + slg, 4) if obp is not None and slg is not None else None
    return {
        "R": total("runs"), "HR": total("homeRuns"), "RBI": total("rbi"),
        "BB": bb, "AVG": avg, "OPS": ops, "G": total("gamesPlayed"),
    }


def compare_batter_categories(player_stats: dict | None,
                              vs_stats: dict | None) -> dict | None:
    """Six-category mechanical scorecard, from the FA/watch player's side.

    This is the audit baseline for the judge panel (issue 030) — recorded
    but NOT used to auto-classify hit/miss (PRD C1 #5: category wins are
    binary and magnitude-blind; RBI 20-vs-5 must not equal HR 3-vs-4).
    Returns None when either side has no window data; categories with an
    unparseable value on either side are marked "no-data" and excluded
    from the W/L/T counts.
    """
    if player_stats is None or vs_stats is None:
        return None
    categories: dict[str, dict] = {}
    wins = losses = ties = 0
    for cat in BATTER_CATEGORIES:
        a, b = player_stats.get(cat), vs_stats.get(cat)
        if a is None or b is None:
            categories[cat] = {"player": a, "vs": b, "result": "no-data"}
            continue
        if a > b:
            result = "win"
            wins += 1
        elif a < b:
            result = "loss"
            losses += 1
        else:
            result = "tie"
            ties += 1
        categories[cat] = {"player": a, "vs": b, "result": result}
    return {"wins": wins, "losses": losses, "ties": ties,
            "categories": categories}


# ── Execution annotation (issue 031) ──
#
# Each reconciled episode is annotated "was this recommendation actually
# executed?" — judged mechanically from roster_config.json git history
# (did the add/watch target enter our roster within the episode window +
# grace?), never by hand. Pure functions here; the git boundary
# (fetch_roster_timeline) lives in backtest_batter.py.

#: Days after the episode's LAST occurrence still counted as execution.
#: Covers FA add latency (same/next day) and waiver claims with
#: Daily-Tomorrow delayed roster effect (claim day X, roster commit X+1,
#: cf. the 2026-06-02 Buehler case) — a recommendation keeps repeating
#: while unexecuted, so a real execution lands near the episode end.
EXECUTION_GRACE_DAYS = 3


@dataclass(frozen=True)
class RosterSnapshot:
    """Roster membership at one roster_config.json commit.

    snap_date is the committer date (UTC date portion) — roster_sync
    commits from the VPS within 15 minutes of the Yahoo transaction, so
    commit date ≈ roster-effect date (grace window absorbs the rest).
    """
    snap_date: date
    mlb_ids: frozenset
    names: frozenset  # normalized via name_match.normalize_name


def parse_roster_snapshot(config: dict, snap_date: date) -> RosterSnapshot:
    """Build a membership snapshot from one roster_config.json payload."""
    ids: set[int] = set()
    names: set[str] = set()
    for section in ("batters", "pitchers"):
        for player in config.get(section) or []:
            if player.get("mlb_id"):
                ids.add(int(player["mlb_id"]))
            if player.get("name"):
                names.add(_normalize(player["name"]))
    return RosterSnapshot(snap_date=snap_date, mlb_ids=frozenset(ids),
                          names=frozenset(names))


def judge_executed(timeline: list[RosterSnapshot], *, player_name: str,
                   player_id: int | None, window_start: date,
                   window_end: date) -> dict:
    """Did the recommended player enter our roster within the window?

    Match policy: when player_id is known, ONLY mlb_id counts — a same-name
    different-id roster entry is a homonym, not an execution (the documented
    search_mlb_id first-hit failure mode). Name matching is the fallback for
    unresolved ids only. Both window endpoints are inclusive.

    Status semantics:
      - executed:        absent at baseline, present in an in-window snapshot
      - not-executed:    absent at baseline and throughout the window
                         (no commits in window = no roster change — valid)
      - already-rostered: present in the last snapshot BEFORE the window
                         (executed=True; should be rare — stale verdict)
      - unknown:         executed=None — empty timeline, or no snapshot
                         before window_start (shallow history: prior
                         absence cannot be established)
    """
    norm = _normalize(player_name) if player_name else ""

    def member(snap: RosterSnapshot) -> str | None:
        if player_id is not None:
            return "mlb_id" if player_id in snap.mlb_ids else None
        return "name" if norm and norm in snap.names else None

    snaps = sorted(timeline, key=lambda s: s.snap_date)
    if not snaps:
        return {"executed": None, "status": "unknown", "matched_date": None,
                "match_by": None, "note": "no roster history available"}
    before = [s for s in snaps if s.snap_date < window_start]
    if not before:
        return {"executed": None, "status": "unknown", "matched_date": None,
                "match_by": None,
                "note": "no snapshot before window — prior absence unknown"}
    baseline = before[-1]
    matched = member(baseline)
    if matched:
        return {"executed": True, "status": "already-rostered",
                "matched_date": baseline.snap_date.isoformat(),
                "match_by": matched,
                "note": "already in roster before the recommendation window"}
    for snap in snaps:
        if window_start <= snap.snap_date <= window_end:
            matched = member(snap)
            if matched:
                return {"executed": True, "status": "executed",
                        "matched_date": snap.snap_date.isoformat(),
                        "match_by": matched, "note": None}
    return {"executed": False, "status": "not-executed", "matched_date": None,
            "match_by": None, "note": None}


# ── Hit-rate / marginal benefit aggregation ──

@dataclass(frozen=True)
class VerdictOutcome:
    """Pairs a verdict with the observable post-verdict performance result.

    `outcome_label` ∈ {"hit", "miss", "neutral"}:
      - hit: verdict aligned with subsequent player performance
      - miss: verdict contradicted by subsequent performance
      - neutral: pass verdicts that yielded no observable comparison; or
        cases where post-verdict sample is too small to judge

    Concrete hit/miss logic for B2 is defined in backtest_track.py, not here.
    """
    verdict: B2Verdict
    outcome_label: str
    marginal_benefit: float | None  # e.g., FA's xwOBACON delta minus dropped SP's


def aggregate_hit_rate(outcomes: list[VerdictOutcome]) -> dict:
    """Compute weekly hit-rate stats over a list of outcomes.

    Excludes neutral outcomes from rate denominator. Returns:
        {
            "n_total": int,
            "n_actionable": int,   # excludes neutrals
            "n_hits": int,
            "hit_rate": float | None,
            "avg_marginal_benefit": float | None,
            "by_action": {"drop_X_add_Y": ..., "watch": ..., "pass": ...},
        }
    """
    actionable = [o for o in outcomes if o.outcome_label != "neutral"]
    hits = [o for o in actionable if o.outcome_label == "hit"]
    benefits = [o.marginal_benefit for o in outcomes if o.marginal_benefit is not None]

    by_action: dict[str, dict] = {}
    for action in ("drop_X_add_Y", "watch", "pass"):
        bucket = [o for o in outcomes if o.verdict.action == action]
        bucket_actionable = [o for o in bucket if o.outcome_label != "neutral"]
        bucket_hits = [o for o in bucket_actionable if o.outcome_label == "hit"]
        by_action[action] = {
            "n": len(bucket),
            "n_actionable": len(bucket_actionable),
            "hit_rate": (len(bucket_hits) / len(bucket_actionable)) if bucket_actionable else None,
        }

    return {
        "n_total": len(outcomes),
        "n_actionable": len(actionable),
        "n_hits": len(hits),
        "hit_rate": (len(hits) / len(actionable)) if actionable else None,
        "avg_marginal_benefit": (sum(benefits) / len(benefits)) if benefits else None,
        "by_action": by_action,
    }
