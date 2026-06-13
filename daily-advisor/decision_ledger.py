"""Decision ledger — deep core (issue 038).

The single persistence layer for per-player decision history: each entry
records a daily verdict plus the context later slices reason over (the
original add reason, the discovery channel, the mechanical star rating, and
— for 051 — the execution timestamp).

Design (PRD `issues/prd-decision-execution.md`, 「decision_ledger 深核心」):
  - Frozen interface `record()` / `get_history()` / `first_channel()`. Slices
    039/040/051 depend on it; new fields are added as trailing optional
    dataclass fields (backward-compatible), never by reordering/removing.
  - JSON persistence keyed by player; entries kept in (ts, insertion) order.
  - Same-day same-verdict dedup-merge: a repeated daily scan is idempotent,
    and a later same-day record only fills fields it newly provides (so 039
    can enrich a row with channel/stars without clobbering). The match scans
    for the latest entry with the same (ts, verdict) — not merely the last
    row — so a same-day distinct-verdict transition in between doesn't defeat
    the merge.
  - The ledger is fed from `apply_waiver_log_block`'s state-aware
    `ledger_sink` (it emits a verdict only when it actually mutates the
    markdown), so the ledger and the markdown share one source of truth and
    never disagree about which players changed state. The 032 `[機械計數]`
    counters keep deriving from the markdown independently; this module never
    writes waiver-log.md.

Channel / add_reason classification and payload injection are NOT here — they
are the thin consumers in issue 039, which call `record()` (or re-call it
same-day to enrich via the merge rule) and use `first_channel()` to honor the
"discovery channel set at first contact, never re-judged" invariant.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

# Verdict vocabulary derived from waiver-log line types. Exported so the
# emitter (fa_scan.apply_waiver_log_block) and consumers share one spelling.
VERDICT_WATCH = "watch"
VERDICT_REPLACE = "取代"
VERDICT_REPLACE_NOW = "立即取代"
VERDICT_CLOSED = "closed"

# Per-block precedence when a player is touched by several lines: a terminal
# CLOSE wins, then an immediate replace, then replace, then plain watch.
VERDICT_PRECEDENCE = {
    VERDICT_CLOSED: 3,
    VERDICT_REPLACE_NOW: 2,
    VERDICT_REPLACE: 1,
    VERDICT_WATCH: 0,
}


@dataclass
class LedgerEntry:
    player: str
    verdict: str
    ts: str
    add_reason: str | None = None
    channel: str | None = None
    stars: int | None = None
    executed_ts: str | None = None  # set by 051 when the verdict is acted on


_ENTRY_FIELDS = {f.name for f in fields(LedgerEntry)}
_MERGEABLE = ("add_reason", "channel", "stars", "executed_ts")


class DecisionLedger:
    """JSON-backed per-player decision history.

    Inject ``path`` (any pathlib path) for fs isolation and ``clock`` (a
    no-arg callable returning an ISO date string) so ``record`` without an
    explicit ``ts`` is deterministic in tests.
    """

    def __init__(self, path, clock=None):
        self._path = Path(path)
        self._clock = clock
        self._data: dict[str, list[dict]] = self._load()

    def _load(self) -> dict[str, list[dict]]:
        if not self._path.exists():
            return {}
        text = self._path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        # A corrupt/truncated file is fatal-by-raise; the best-effort caller
        # (fa_scan) catches it, alerts, and skips this run rather than
        # silently overwriting a recoverable file with partial data.
        return json.loads(text)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def record(self, player, verdict, ts=None, add_reason=None,
               channel=None, stars=None, executed_ts=None) -> LedgerEntry:
        """Append (or dedup-merge) one decision for ``player``.

        Same-day + same-verdict as the player's latest matching entry → merge
        any newly-provided (non-None) fields into it instead of appending.
        A different same-day verdict appends a new entry (a real transition).
        """
        if ts is None:
            ts = self._clock() if self._clock else None
            if ts is None:
                raise ValueError("record() needs ts or an injected clock")
        rows = self._data.setdefault(player, [])
        incoming = {"player": player, "verdict": verdict, "ts": ts,
                    "add_reason": add_reason, "channel": channel,
                    "stars": stars, "executed_ts": executed_ts}
        # Scan from the end for the latest entry with the same (ts, verdict);
        # stop once we pass below this ts (rows are ts-sorted).
        for merged in reversed(rows):
            if merged["ts"] == ts and merged["verdict"] == verdict:
                for key in _MERGEABLE:
                    if incoming[key] is not None:
                        merged[key] = incoming[key]
                self._save()
                return LedgerEntry(**merged)
            if merged["ts"] < ts:
                break
        rows.append(incoming)
        rows.sort(key=lambda r: r["ts"])  # stable: keeps same-ts insertion order
        self._save()
        return LedgerEntry(**incoming)

    def get_history(self, player) -> list[LedgerEntry]:
        return [LedgerEntry(**{k: v for k, v in row.items() if k in _ENTRY_FIELDS})
                for row in self._data.get(player, [])]

    def all_histories(self) -> dict:
        """{player: [LedgerEntry]} for every player — used by the weekly-review
        unexecuted-recommendations consumer (issue 041)."""
        return {player: self.get_history(player) for player in self._data}

    def first_channel(self, player) -> str | None:
        """The discovery channel from the player's earliest entry that has one
        — the "set at first contact, never re-judged" value 039 must honor."""
        for row in self._data.get(player, []):
            if row.get("channel") is not None:
                return row["channel"]
        return None
