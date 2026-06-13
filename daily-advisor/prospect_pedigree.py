"""Post-hype 新秀標記 engine (issue 049 / GitHub #328).

Durable runtime layer for the post-hype prospect tag: a young, former top-100
prospect whose MLB results have so far disappointed gets a tag that authorizes
the LLM to *discount the bad prior* instead of auto-cutting on a double-year-low
Sum. Counter-example it exists to fix: Jordan Walker (MLB Pipeline #2, 2023,
young) flagged structurally-weak and nearly mis-cut (docs/fa-scan-eval-
brainstorm-7x7.md).

Three layers, kept separate on purpose:

  - **data asset** `prospect_pedigree.json` — static, human-maintained, refreshed
    each March (the system's first hand-curated data asset). Built by
    build_prospect_json.py so every mlb_id is API-verified, never hand-typed
    (CLAUDE.md no-hardcode rule).
  - **this module** — pure load / stale-detection / join / predicate. stdlib only,
    no project imports, no network — trivially testable.
  - **payload wiring** (fa_compute / fa_scan batter tags + 039 whitelist) — a
    separate step; this module just produces the tag string + a structured result.

The join key is mlb_id (verified). The `name` field in the JSON is descriptive
only — never matched on.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "prospect_pedigree.json")

# Top-100 pedigree gate — best (lowest) career prospect rank must be ≤ this.
DEFAULT_RANK_THRESHOLD = 100
# Young gate — currentAge ≤ this (inclusive). Post-hype is about youth still on
# the table; an old former prospect is just a bust, not a discount candidate.
DEFAULT_AGE_THRESHOLD = 25
# Refresh-window month — the list is expected to be rebuilt each year by the end
# of this month (March). Past it with a stale year → flagged, never silently used.
DEFAULT_STALE_AFTER_MONTH = 3
# "過往成績差" proxy: batter season Sum (3-30 scale from fa_compute) below this
# reads as poor-results-so-far. Tunable; the exact cutoff is calibration, not law.
DEFAULT_WEAK_SUM_THRESHOLD = 20


@dataclass(frozen=True)
class Pedigree:
    """Parsed pedigree data asset. `prospects` is keyed by int mlb_id."""

    updated_year: int
    updated_date: str
    source: str
    stale_after_month: int
    prospects: dict


@dataclass(frozen=True)
class PostHypeResult:
    is_post_hype: bool
    best_rank: int | None
    best_rank_year: int | None
    age: float | None
    weak: bool
    stale: bool
    reason: str


def parse_pedigree(raw: dict) -> Pedigree:
    """Pure parse of a raw pedigree dict (no I/O). Coerces mlb_id keys to int.

    Raises ValueError on a malformed asset (missing meta / updated) rather than
    silently degrading — a broken data asset should be loud.
    """
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("prospect_pedigree: missing or invalid 'meta' block")
    updated = meta.get("updated")
    if not updated:
        raise ValueError("prospect_pedigree: meta.updated is required")
    try:
        updated_year = int(str(updated)[:4])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"prospect_pedigree: bad meta.updated {updated!r}") from exc

    raw_prospects = raw.get("prospects") or {}
    prospects: dict = {}
    for k, v in raw_prospects.items():
        try:
            mlb_id = int(k)
        except (ValueError, TypeError):
            # skip unparseable keys rather than crash the whole load
            continue
        prospects[mlb_id] = v

    return Pedigree(
        updated_year=updated_year,
        updated_date=str(updated),
        source=str(meta.get("source", "")),
        stale_after_month=int(meta.get("stale_after_month", DEFAULT_STALE_AFTER_MONTH)),
        prospects=prospects,
    )


def load_pedigree(path: str = DEFAULT_PATH) -> Pedigree:
    """Load + parse the on-disk data asset. Raises FileNotFoundError if absent."""
    with open(path, encoding="utf-8") as f:
        return parse_pedigree(json.load(f))


def is_stale(ped: Pedigree, today: _dt.date, stale_after_month: int | None = None) -> bool:
    """True when the list is older than its yearly March refresh window allows.

    Rule (window month m = stale_after_month, default from the asset):
      - updated this year or in the future → fresh
      - 1 year behind → stale only once we are past month m (the March window
        for the current year has closed without a refresh)
      - ≥2 years behind → stale regardless of month
    """
    m = ped.stale_after_month if stale_after_month is None else stale_after_month
    years_behind = today.year - ped.updated_year
    if years_behind <= 0:
        return False
    if years_behind >= 2:
        return True
    return today.month > m


def lookup(ped: Pedigree, mlb_id) -> dict | None:
    """Pedigree join. Returns the record dict or None on miss / unparseable id."""
    if mlb_id is None:
        return None
    try:
        key = int(mlb_id)
    except (ValueError, TypeError):
        return None
    return ped.prospects.get(key)


def default_weak_signal(batter_sum, threshold: int = DEFAULT_WEAK_SUM_THRESHOLD) -> bool:
    """Default "過往成績差" proxy from the batter season Sum (3-30).

    None → False (no fabricated signal on missing data). Tunable threshold.
    """
    if batter_sum is None:
        return False
    return batter_sum < threshold


def evaluate_post_hype(
    ped: Pedigree,
    mlb_id,
    age,
    weak_signal: bool,
    today: _dt.date,
    *,
    rank_threshold: int = DEFAULT_RANK_THRESHOLD,
    age_threshold: int = DEFAULT_AGE_THRESHOLD,
) -> PostHypeResult:
    """Combine the three gates — pedigree (top-N) + young + poor-results.

    `weak_signal` is supplied by the caller (use default_weak_signal for the
    season-Sum proxy) so this module stays agnostic to how "poor" is measured
    and needs no extra fetch.
    """
    rec = lookup(ped, mlb_id)
    best_rank = rec["best_rank"] if rec else None
    best_rank_year = rec["best_rank_year"] if rec else None

    pedigree_ok = rec is not None and best_rank is not None and best_rank <= rank_threshold
    young_ok = age is not None and age <= age_threshold
    weak = bool(weak_signal)
    stale = is_stale(ped, today)

    fires = pedigree_ok and young_ok and weak

    if not pedigree_ok:
        reason = "no top-100 pedigree on file"
    elif not young_ok:
        reason = f"not young (age {age} > {age_threshold})"
    elif not weak:
        reason = "season results not weak — no discount needed"
    else:
        reason = f"post-hype: #{best_rank} ({best_rank_year}), age {age}, weak season"

    return PostHypeResult(
        is_post_hype=fires,
        best_rank=best_rank,
        best_rank_year=best_rank_year,
        age=age,
        weak=weak,
        stale=stale,
        reason=reason,
    )


def post_hype_tag(ped: Pedigree, mlb_id, age, weak_signal: bool, today: _dt.date, **kw) -> str | None:
    """Tag string for the batter payload, or None when it does not fire.

    Fresh list → "✅ post-hype 新秀 (#R YEAR)".
    Stale list → "⚠️ post-hype 名單過期 (#R YEAR)" — the ⚠️/過期 wording makes the
    stale data explicit so it is never silently trusted (PRD gray-area rule).
    """
    r = evaluate_post_hype(ped, mlb_id, age, weak_signal, today, **kw)
    if not r.is_post_hype:
        return None
    if r.stale:
        return f"⚠️ post-hype 名單過期 (#{r.best_rank} {r.best_rank_year})"
    return f"✅ post-hype 新秀 (#{r.best_rank} {r.best_rank_year})"
