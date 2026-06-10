"""_backtest_lib — shared pure-function primitives for SP decision backtest.

Use Case A (issue 024): backtest_track.py — read B2 fa-scan SP-v4 issues,
extract verdicts, join with subsequent SP performance, output hit-rate +
marginal benefit. Per docs/sp-decisions-backtest-automation.md §7.

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
