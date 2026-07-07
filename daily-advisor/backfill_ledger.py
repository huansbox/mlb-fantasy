"""Legacy ledger backfill — one-shot pre-injection script (318b B7, issue 039 / #318).

Backfills decision-ledger.json for the CURRENT stock only (design doc
`docs/318b-injection-design.md` Q6): active roster + active watchlist. The
318b payload injection renders ledger memory ("上次 / 原撿因"); without this
backfill, every roster player predating the ledger confronts an empty
add_reason and the churn protection only covers future pickups.

Q6c — roster add reasons are NOT real pickup motives. Each one is a
day-of-run season snapshot explicitly tagged
「[backfill：上線日季線，非真實 add 理由]」 so a later drop decision is never
misled by fake history. The marker lives in the add_reason text, never in the
verdict (no sentinel verdict).

Watchlist channels are inferred from the entry's own earliest history bullet
(the text closest to discovery) — NOT from current-season signals, which
would whitewash a heat-led discovery that has since grown a season line.
Precedence mirrors ledger_enrich.classify_channel: structure > heat > market
> unknown; an unclassifiable entry stays unknown (neutral star weight).

Idempotent: a player already carrying the target field (roster: any
add_reason in history; watchlist: any channel) is skipped, so re-runs are
no-ops. main() ends with the machine-checkable acceptance from the PRD: no
roster player missing add_reason, no active watchlist entry missing channel;
exit 1 otherwise.

Usage (run once, before 318b-sp injection goes live):
    uv run python daily-advisor/backfill_ledger.py [--dry-run] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

from decision_ledger import VERDICT_WATCH, DecisionLedger
from ledger_enrich import (
    CHANNEL_HEAT,
    CHANNEL_MARKET,
    CHANNEL_STRUCTURE,
    CHANNEL_UNKNOWN,
)

# Roster backfill rows are "we currently hold him", not a waiver-log verdict.
# Non-actionable for decision_gate (only 取代/立即取代 escalate), renders
# naturally in the ledger note ("上次 hold（N 天前）").
VERDICT_HOLD = "hold"

BACKFILL_TAG = "[backfill：上線日季線，非真實 add 理由]"
NO_DATA_SNAPSHOT = "無 2026 季線數據"

# ── watchlist parsing ──

_WATCH_HEADER_RE = re.compile(
    r"^### (?P<name>[^(\n]+?)\s*\((?P<team>[^,)]+)[,，]?\s*(?P<pos>[^)]*)\)"
    r"(?:\s*\[mlb_id:(?P<mlb_id>\d+)\])?",
    re.M,
)
_FIRST_BULLET_RE = re.compile(r"^- \d{2}-\d{2}：(?P<text>.+)$", re.M)

# Channel evidence in discovery-era text. Strong percentile mentions
# (P60+..P95, or 「>P90」 style) ×2, an explicit 雙年 claim, or an SP 5-slot
# comparison (≥3 distinct v4 slot names — SP reasons cite raw slot values,
# not P-notation) → structure; a 14d/21d short-window stat → heat; ownership
# movement → market.
_STRONG_PCT_RE = re.compile(r"P(?:[6-9]\d)\b")
_SP_SLOT_RES = (
    re.compile(r"IP/GS", re.I),
    re.compile(r"Whiff", re.I),
    re.compile(r"BB/9", re.I),
    re.compile(r"\bGB\b", re.I),
    re.compile(r"xwOBACON", re.I),
)
_HEAT_RE = re.compile(r"14d|21d")
_MARKET_RE = re.compile(r"%owned|持有壓力|被搶風險")


def parse_active_watchlist(md_text: str) -> list[dict]:
    """Split the waiver-log 「## 觀察中」 section into per-player entries.

    Returns [{name, team, position, mlb_id, body}] where body is the entry's
    full text (header + trigger + history bullets). 隊上觀察 / 已結案 are NOT
    watchlist — roster players are covered by the roster half, closed entries
    are out of backfill scope (design Q6b: current stock only).
    """
    start = md_text.find("## 觀察中")
    if start == -1:
        return []
    end = md_text.find("\n## ", start + len("## 觀察中"))
    section = md_text[start:end] if end != -1 else md_text[start:]

    entries = []
    matches = list(_WATCH_HEADER_RE.finditer(section))
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        entries.append({
            "name": m.group("name").strip(),
            "team": m.group("team").strip(),
            "position": m.group("pos").strip(),
            "mlb_id": int(m.group("mlb_id")) if m.group("mlb_id") else None,
            "body": section[m.start():body_end],
        })
    return entries


def classify_channel_from_text(body: str) -> str:
    """Discovery channel from an entry's earliest history bullet.

    The trigger line states FUTURE conditions ("14d OPS ≥.850連5天") and would
    misread as heat for nearly every entry, so classification keys on the
    first dated bullet — the recorded observation closest to first contact.
    Only structure (+1 star) vs heat (+0) truly matters downstream; market /
    news / unknown all carry the same neutral weight.
    """
    m = _FIRST_BULLET_RE.search(body)
    text = m.group("text") if m else body
    slot_mentions = sum(1 for rx in _SP_SLOT_RES if rx.search(text))
    if ("雙年" in text or len(_STRONG_PCT_RE.findall(text)) >= 2
            or slot_mentions >= 3):
        return CHANNEL_STRUCTURE
    if _HEAT_RE.search(text):
        return CHANNEL_HEAT
    if _MARKET_RE.search(text):
        return CHANNEL_MARKET
    return CHANNEL_UNKNOWN


# ── season snapshots ──

def _fmt3(v) -> str:
    """xwOBA convention: 3 decimals, no leading zero (.349 not 0.349)."""
    s = f"{v:.3f}"
    return s[1:] if s.startswith("0.") else s


def format_batter_snapshot(row: dict | None) -> str | None:
    """「xwOBA .312 / BB% 8.4 / Barrel% 9.1 / PA 250」 from a bulk-CSV row;
    None when no core metric is present."""
    if not row:
        return None
    parts = []
    if row.get("xwoba") is not None:
        parts.append(f"xwOBA {_fmt3(row['xwoba'])}")
    if row.get("bb_pct") is not None:
        parts.append(f"BB% {row['bb_pct']:g}")
    if row.get("barrel_pct") is not None:
        parts.append(f"Barrel% {row['barrel_pct']:g}")
    if not parts:
        return None
    if row.get("pa") is not None:
        parts.append(f"PA {row['pa']:g}")
    return " / ".join(parts)


def format_pitcher_snapshot(v4: dict | None) -> str | None:
    """v4 5-slot snapshot 「IP/GS 5.4 / Whiff% 24.0 / BB/9 2.95 / GB% 43.2 /
    xwOBACON .370 / IP 80.2」; None when no slot is present."""
    if not v4:
        return None
    parts = []
    if v4.get("ip_gs") is not None:
        parts.append(f"IP/GS {v4['ip_gs']:.2f}")
    if v4.get("whiff_pct") is not None:
        parts.append(f"Whiff% {v4['whiff_pct']:.1f}")
    if v4.get("bb9") is not None:
        parts.append(f"BB/9 {v4['bb9']:.2f}")
    if v4.get("gb_pct") is not None:
        parts.append(f"GB% {v4['gb_pct']:.1f}")
    if v4.get("xwobacon") is not None:
        parts.append(f"xwOBACON {_fmt3(v4['xwobacon'])}")
    if not parts:
        return None
    if v4.get("ip"):
        parts.append(f"IP {v4['ip']:.1f}")
    return " / ".join(parts)


_BATTER_SEL = "pa,xwoba,bb_percent,barrel_batted_rate"


def fetch_batter_season_bulk(year: int) -> dict[int, dict]:
    """One league-bulk Savant custom CSV → {pid: {pa, xwoba, bb_pct,
    barrel_pct}} (same endpoint pattern as batter_discipline)."""
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=batter&filter=&min=1&selections={_BATTER_SEL}&csv=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    out: dict[int, dict] = {}
    for r in csv.DictReader(io.StringIO(raw)):
        try:
            pid = int(r["player_id"])
        except (ValueError, KeyError, TypeError):
            continue
        out[pid] = {
            "pa": _f(r.get("pa")),
            "xwoba": _f(r.get("xwoba")),
            "bb_pct": _f(r.get("bb_percent")),
            "barrel_pct": _f(r.get("barrel_batted_rate")),
        }
    return out


def _f(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── pure planning ──

def plan_backfill(roster, watchlist, histories, today,
                  batter_rows, pitcher_v4) -> list[dict]:
    """Decide the ledger.record calls, given everything already fetched.

    roster: [{name, mlb_id, role: "batter"|"pitcher"}]
    watchlist: parse_active_watchlist output
    histories: {name: [LedgerEntry]}
    batter_rows / pitcher_v4: {mlb_id: row} season snapshots

    Skips players already carrying the target field, so a re-run plans
    nothing (idempotent across days, not just via same-day dedup-merge).
    """
    actions = []
    for p in roster:
        hist = histories.get(p["name"], [])
        if any(getattr(e, "add_reason", None) for e in hist):
            continue
        if p["role"] == "pitcher":
            snap = format_pitcher_snapshot(pitcher_v4.get(p.get("mlb_id")))
        else:
            snap = format_batter_snapshot(batter_rows.get(p.get("mlb_id")))
        actions.append({
            "player": p["name"],
            "verdict": VERDICT_HOLD,
            "ts": today,
            "add_reason": f"{BACKFILL_TAG} {snap or NO_DATA_SNAPSHOT}",
            "channel": None,
        })
    for w in watchlist:
        hist = histories.get(w["name"], [])
        if any(getattr(e, "channel", None) for e in hist):
            continue
        verdict = getattr(hist[-1], "verdict", None) if hist else None
        actions.append({
            "player": w["name"],
            "verdict": verdict or VERDICT_WATCH,
            "ts": today,
            "add_reason": None,
            "channel": classify_channel_from_text(w["body"]),
        })
    return actions


def acceptance_failures(histories, roster, watchlist) -> list[str]:
    """PRD 039 machine-checkable acceptance: every roster player has an
    add_reason, every active watchlist entry has a channel."""
    failures = []
    for p in roster:
        if not any(getattr(e, "add_reason", None)
                   for e in histories.get(p["name"], [])):
            failures.append(f"roster 缺 add_reason: {p['name']}")
    for w in watchlist:
        if not any(getattr(e, "channel", None)
                   for e in histories.get(w["name"], [])):
            failures.append(f"watchlist 缺 channel: {w['name']}")
    return failures


# ── thin orchestrator ──

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="plan + print only, no ledger writes")
    ap.add_argument("--date", help="backfill ts (default: today ISO)")
    args = ap.parse_args(argv)
    today = args.date or date.today().isoformat()

    root = Path(__file__).resolve().parent.parent
    config = json.loads(
        (root / "daily-advisor" / "roster_config.json").read_text(encoding="utf-8"))
    season = int(config.get("league", {}).get("season") or date.today().year)
    roster = (
        [{"name": b["name"], "mlb_id": b.get("mlb_id"), "role": "batter"}
         for b in config.get("batters", [])]
        + [{"name": p["name"], "mlb_id": p.get("mlb_id"), "role": "pitcher"}
           for p in config.get("pitchers", [])]
    )
    watchlist = parse_active_watchlist(
        (root / "waiver-log.md").read_text(encoding="utf-8"))

    ledger = DecisionLedger(root / "decision-ledger.json")
    names = {p["name"] for p in roster} | {w["name"] for w in watchlist}
    histories = {n: ledger.get_history(n) for n in names}

    # Fetch only for players the plan will actually touch.
    def _needs_reason(p):
        return not any(getattr(e, "add_reason", None)
                       for e in histories.get(p["name"], []))

    need_batter = any(p["role"] == "batter" and _needs_reason(p) for p in roster)
    need_pids = [p["mlb_id"] for p in roster
                 if p["role"] == "pitcher" and _needs_reason(p) and p.get("mlb_id")]
    batter_rows = {}
    pitcher_v4 = {}
    if need_batter:
        print(f"Fetching Savant batter season bulk ({season})...", file=sys.stderr)
        batter_rows = fetch_batter_season_bulk(season)
    if need_pids:
        from sp_data_fetchers import assemble_data
        pitcher_v4 = assemble_data(need_pids, season)

    actions = plan_backfill(roster, watchlist, histories, today,
                            batter_rows, pitcher_v4)
    for a in actions:
        detail = a["add_reason"] or f"channel={a['channel']}"
        print(f"{'PLAN' if args.dry_run else 'RECORD'} {a['player']} "
              f"[{a['verdict']}] {detail}")
        if not args.dry_run:
            ledger.record(**a)

    if args.dry_run:
        print(f"dry-run: {len(actions)} 筆待回填")
        return 0

    fresh = {n: ledger.get_history(n) for n in names}
    failures = acceptance_failures(fresh, roster, watchlist)
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        return 1
    print(f"backfill 完成：{len(actions)} 筆寫入，驗收通過 "
          f"(roster {len(roster)} 全有 add_reason / watchlist {len(watchlist)} 全有 channel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
