"""Builder for the post-hype prospect data asset (issue 049 / GitHub #328).

Turns a human-maintained ranking source (editorial Top-100 facts) into the
runtime data asset `prospect_pedigree.json`, resolving every player to an
API-verified mlb_id — never a hand-typed id (CLAUDE.md no-hardcode rule).

The yearly ~30-min March refresh is: paste the new season's MLB Pipeline Top 100
into `prospect_rankings_raw.tsv` as `year<TAB>rank<TAB>name` rows, then run

    python build_prospect_json.py

Resolution is deliberately conservative: a name is only written when it maps to
exactly ONE MLB player id across the queried seasons. Zero matches (still a
minor-leaguer who hasn't debuted) or multiple matches (same-name collision) go
to a needs_review report and are excluded — the builder never guesses an id.
Excluding undebuted prospects is fine: the post-hype tag only ever fires on
players who can appear in a fantasy FA scan, i.e. ones who have reached MLB.

Network surface: statsapi.mlb.com only (public, no auth, not Yahoo) — safe to
run locally; the project's local-Yahoo hook does not block this script.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_SOURCE = os.path.join(HERE, "prospect_rankings_raw.tsv")
OUT_JSON = os.path.join(HERE, "prospect_pedigree.json")

# MLB seasons to pull rosters for, to resolve names → ids. Covers the debuted
# cohort of any prospect ranked in the last few preseasons.
DEFAULT_SEASONS = (2023, 2024, 2025, 2026)

# Build-time age cut. A player ranked a *prospect* in 2023-2025 who is now older
# than this is a same-name veteran collision (e.g. the b.1991 Wilmer Flores
# matching the b.2001 prospect), not the prospect. Dropping them is lossless: the
# runtime post-hype gate is ≤25, so anyone over this could never fire it anyway —
# the cut just keeps veteran ids out of the asset. Must exceed the runtime gate.
MAX_PROSPECT_AGE = 28

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv)\b\.?")
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


# ── pure helpers (unit-tested) ──
def normalize_name(name: str) -> str:
    """Accent-fold + lowercase + drop punctuation/suffixes for matching."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _SUFFIX_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def parse_raw_source(text: str) -> list[tuple[int, int, str]]:
    """Parse `year<TAB>rank<TAB>name` rows. Skips blanks and # comments.

    Tolerant of malformed rows (missing cols / non-int year|rank) — they are
    skipped rather than raising, so one bad paste line never breaks a refresh.
    """
    rows: list[tuple[int, int, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 3:
            parts = [p.strip() for p in re.split(r"\s{2,}|,", line)]
        if len(parts) < 3:
            continue
        year_s, rank_s, name = parts[0], parts[1], parts[2]
        try:
            year, rank = int(year_s), int(rank_s)
        except ValueError:
            continue
        if not name:
            continue
        rows.append((year, rank, name))
    return rows


def build_name_index(players: list[dict]) -> dict[str, set[int]]:
    """norm fullName → set of mlb ids (a set so same-name collisions surface)."""
    index: dict[str, set[int]] = {}
    for p in players:
        pid = p.get("id")
        full = p.get("fullName")
        if pid is None or not full:
            continue
        index.setdefault(normalize_name(full), set()).add(int(pid))
    return index


def resolve(
    rankings: list[tuple[int, int, str]], name_index: dict[str, set[int]]
) -> tuple[list[dict], list[dict]]:
    """Split rankings into resolved (exactly-one id) and needs_review rows."""
    resolved: list[dict] = []
    needs_review: list[dict] = []
    for year, rank, name in rankings:
        ids = name_index.get(normalize_name(name), set())
        if len(ids) == 1:
            resolved.append(
                {"mlb_id": next(iter(ids)), "best_rank": rank, "year": year, "name": name}
            )
        else:
            needs_review.append(
                {"name": name, "year": year, "rank": rank, "match_count": len(ids),
                 "reason": "no MLB debut / unmatched" if not ids else "same-name collision"}
            )
    return resolved, needs_review


def build_age_index(players: list[dict]) -> dict[int, int]:
    """mlb id → currentAge, for the build-time veteran-collision cut."""
    ages: dict[int, int] = {}
    for p in players:
        pid, age = p.get("id"), p.get("currentAge")
        if pid is None or age is None:
            continue
        ages[int(pid)] = int(age)
    return ages


def drop_aged_out(
    prospects: dict[int, dict], age_index: dict[int, int], max_age: int = MAX_PROSPECT_AGE
) -> tuple[dict[int, dict], list[dict]]:
    """Strip resolved ids older than max_age (same-name veteran false positives).

    Unknown age → kept (no fabricated reason to drop). Returns (kept, dropped),
    dropped rows carrying name/age/best_rank for the report.
    """
    kept: dict[int, dict] = {}
    dropped: list[dict] = []
    for pid, rec in prospects.items():
        age = age_index.get(pid)
        if age is not None and age > max_age:
            dropped.append({"mlb_id": pid, "age": age, **rec})
        else:
            kept[pid] = rec
    return kept, dropped


def merge_best_rank(resolved: list[dict]) -> dict[int, dict]:
    """Dedup to the best (lowest) rank per id, recording that rank's year."""
    out: dict[int, dict] = {}
    for row in resolved:
        pid = row["mlb_id"]
        cur = out.get(pid)
        if cur is None or row["best_rank"] < cur["best_rank"]:
            out[pid] = {
                "best_rank": row["best_rank"],
                "best_rank_year": row["year"],
                "name": row["name"],
            }
    return out


# ── network ──
def fetch_mlb_players(season: int) -> list[dict]:
    """GET MLB (sport 1) players for a season → [{id, fullName}, ...]."""
    url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
    req = urllib.request.Request(url, headers={"User-Agent": "mlb-fantasy-prospect-builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data.get("people", [])


def build(seasons=DEFAULT_SEASONS, raw_path=RAW_SOURCE, out_path=OUT_JSON,
          today: _dt.date | None = None) -> dict:
    today = today or _dt.date.today()
    with open(raw_path, encoding="utf-8") as f:
        rankings = parse_raw_source(f.read())
    if not rankings:
        raise SystemExit(f"no rankings parsed from {raw_path}")

    all_players: list[dict] = []
    for season in seasons:
        all_players.extend(fetch_mlb_players(season))
    name_index = build_name_index(all_players)
    age_index = build_age_index(all_players)

    resolved, needs_review = resolve(rankings, name_index)
    prospects, aged_out = drop_aged_out(merge_best_rank(resolved), age_index)
    source_years = sorted({y for y, _, _ in rankings})

    asset = {
        "meta": {
            "updated": today.isoformat(),
            "source": "Bleacher Report annual Top 100 MLB Prospects (seed)",
            "source_years": source_years,
            "stale_after_month": 3,
            "resolved": len(prospects),
            "needs_review": len(needs_review),
            "aged_out": len(aged_out),
            "note": (
                "Join key is mlb_id (API-verified). name is descriptive only. "
                "Only MLB-debuted prospects are kept — undebuted ones go to "
                "needs_review and are excluded until they reach MLB. Refresh each "
                "March: paste the new Top 100 into prospect_rankings_raw.tsv, rerun."
            ),
        },
        "prospects": {str(pid): rec for pid, rec in sorted(prospects.items())},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asset, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")

    print(f"resolved {len(prospects)} prospects → {out_path}")
    if aged_out:
        print(f"\ndropped {len(aged_out)} same-name veteran collisions (age > {MAX_PROSPECT_AGE}):")
        for r in sorted(aged_out, key=lambda x: x["best_rank_year"]):
            print(f"  {r['best_rank_year']} #{r['best_rank']:>3}  {r['name']}  (age {r['age']})")
    if needs_review:
        print(f"\n{len(needs_review)} rows need manual review (excluded — no guessed ids):")
        for r in sorted(needs_review, key=lambda x: (x["year"], x["rank"])):
            print(f"  {r['year']} #{r['rank']:>3}  {r['name']}  ({r['reason']})")
    return asset


if __name__ == "__main__":
    build()
    sys.exit(0)
