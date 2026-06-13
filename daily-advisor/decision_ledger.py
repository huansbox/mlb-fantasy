"""Decision ledger — deep core (issue 038).

The single persistence layer for per-player decision history: each entry
records a daily verdict plus the context later slices reason over (the
original add reason, the discovery channel, the mechanical star rating).

Design (PRD `issues/prd-decision-execution.md`, 「decision_ledger 深核心」):
  - Frozen interface `record()` / `get_history()` — slices 039/040 depend on
    it and must not change the signature.
  - JSON persistence keyed by player; entries kept in (ts, insertion) order.
  - Same-day same-verdict dedup-merge: a repeated daily scan is idempotent,
    and a later same-day record only fills in fields it newly provides
    (so 039 can enrich a row with channel/stars without clobbering).
  - `derive_ledger_records` reads the SAME ```waiver-log``` block that
    `apply_waiver_log_block` (fa_scan) applies, so the ledger and the
    markdown share one source of truth — no second parse path. The 032
    `[機械計數]` counters keep deriving from the markdown independently;
    this module never writes waiver-log.md.

Channel / add_reason classification and payload injection are NOT here —
they are the thin consumers in issue 039, which call `record()` (or re-call
it same-day to enrich via the merge rule).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

# Verdict vocabulary derived from waiver-log line types.
VERDICT_WATCH = "watch"
VERDICT_REPLACE = "取代"
VERDICT_REPLACE_NOW = "立即取代"
VERDICT_CLOSED = "closed"

# Per-block precedence when a player appears on several lines: a terminal
# CLOSE wins, then an immediate replace, then replace, then plain watch.
_VERDICT_PRECEDENCE = {
    VERDICT_CLOSED: 3,
    VERDICT_REPLACE_NOW: 2,
    VERDICT_REPLACE: 1,
    VERDICT_WATCH: 0,
}
_ACTION_TYPES = (VERDICT_REPLACE_NOW, VERDICT_REPLACE)


@dataclass
class LedgerEntry:
    player: str
    verdict: str
    ts: str
    add_reason: str | None = None
    channel: str | None = None
    stars: int | None = None


_ENTRY_FIELDS = {f.name for f in fields(LedgerEntry)}


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
        return json.loads(text)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def record(self, player, verdict, ts=None, add_reason=None,
               channel=None, stars=None) -> LedgerEntry:
        """Append (or dedup-merge) one decision for ``player``.

        Same-day + same-verdict as the player's latest entry → merge any
        newly-provided (non-None) fields into it instead of appending.
        A different same-day verdict appends a new entry (a real transition).
        """
        if ts is None:
            ts = self._clock() if self._clock else None
            if ts is None:
                raise ValueError("record() needs ts or an injected clock")
        rows = self._data.setdefault(player, [])
        incoming = {"player": player, "verdict": verdict, "ts": ts,
                    "add_reason": add_reason, "channel": channel,
                    "stars": stars}
        if rows and rows[-1]["ts"] == ts and rows[-1]["verdict"] == verdict:
            merged = rows[-1]
            for key in ("add_reason", "channel", "stars"):
                if incoming[key] is not None:
                    merged[key] = incoming[key]
            self._save()
            return LedgerEntry(**merged)
        rows.append(incoming)
        rows.sort(key=lambda r: r["ts"])  # stable: keeps same-ts insertion order
        self._save()
        return LedgerEntry(**incoming)

    def get_history(self, player) -> list[LedgerEntry]:
        return [LedgerEntry(**{k: v for k, v in row.items() if k in _ENTRY_FIELDS})
                for row in self._data.get(player, [])]


def derive_ledger_records(block: str, ts: str) -> list[tuple[str, str]]:
    """Map one ```waiver-log``` block to ``[(player, verdict)]``.

    Shares the 028 line grammar + ACTION-annotation precedence used by
    ``fa_scan.apply_waiver_log_block`` so the ledger and the markdown derive
    from one source. One record per player; precedence resolves a player
    appearing on multiple lines (CLOSE > 立即取代 > 取代 > watch).

    ``ts`` is accepted for caller symmetry (the verdict, not the date, is
    derived here); the caller passes both to ``DecisionLedger.record``.
    """
    verdicts: dict[str, str] = {}

    def _offer(player: str, verdict: str) -> None:
        player = player.strip()
        if not player:
            return
        prev = verdicts.get(player)
        if prev is None or _VERDICT_PRECEDENCE[verdict] > _VERDICT_PRECEDENCE[prev]:
            verdicts[player] = verdict

    for raw in block.split("\n"):
        line = raw.strip()
        if not line:
            continue
        parts = line.split("|")
        kind = parts[0]
        if kind == "NEW" and len(parts) >= 6:
            _offer(parts[1], VERDICT_WATCH)
        elif kind == "UPDATE" and len(parts) >= 3:
            _offer(parts[1], VERDICT_WATCH)
        elif kind == "ACTION" and len(parts) >= 4 and parts[2].strip() in _ACTION_TYPES:
            _offer(parts[1], parts[2].strip())
        elif kind == "CLOSE" and len(parts) >= 3 and parts[1].strip():
            _offer(parts[1], VERDICT_CLOSED)

    return [(player, verdicts[player])
            for player in verdicts]
