"""Payload line budget — the per-candidate cross-slice accounting gate (039/318b).

Each injection slice declares how many payload lines it adds for one candidate
via ``register``; the budget enforces a single per-candidate ceiling. It owns
the *mechanism* (count + assert), never the *policy* (which lines to drop when
over — that belongs to the injection site, per the PRD: 「ledger 注入片 owns
既有行讓位規則」). 跨片協作的唯一交會點：各注入片彼此不需認識，只透過同一個
budget 實例間接協調行數 — 這就是 User story 20 的「單一 enforcement 點」（指
唯一做超限判定的地方，不是全系統唯一物件）。

Mechanism not policy（設計骨幹）：
  - budget 只碰「數字」(行數)，永遠不碰行的「內容 / 格式」。
  - 上限可配置 (``max_lines``)，模組不 hardcode「3 是什麼 / swap 差額表算不算」
    — 那是注入端 policy。要分池 (tag 池 vs diff 池) 就建多個實例。
  - per-candidate 實例：每個候選組裝時 new 一個，純記憶體累積，無持久化
    （仿 DecisionLedger 的 class 形態，但更輕）。

Fail 行為：``assert_within`` 超限 raise ``PayloadBudgetExceeded``（與 AC「超限
assert」一致）；``within`` / ``remaining`` 為非 raise 查詢，供注入端優雅讓位。
生產路徑 (fa_scan cron) 應以 try/except 包覆 assert，比照既有 ledger 的
best-effort 慣例（ledger failure 必須 never abort waiver-log write）。
"""

from __future__ import annotations


class PayloadBudgetExceeded(Exception):
    """Raised by ``assert_within`` when a candidate's registered lines exceed
    the ceiling. Carries the per-slice counts (``slice_counts``) so the
    offending slice is diagnosable from logs / alerts. Named ``slice_counts``
    rather than ``breakdown`` on purpose: it is a plain dict attribute, not the
    ``PayloadBudget.breakdown()`` method — so ``except`` handlers don't reflex
    into ``e.breakdown()`` and hit a ``'dict' object is not callable``."""

    def __init__(self, candidate, total, limit, slice_counts):
        self.candidate = candidate
        self.total = total
        self.limit = limit
        self.slice_counts = dict(slice_counts)
        super().__init__(
            f"payload budget exceeded for {candidate!r}: "
            f"{total} > {limit} lines (breakdown: {self.slice_counts})"
        )


class PayloadBudget:
    """A per-candidate, per-pool payload line-count gate.

    Inject ``max_lines`` (this pool's ceiling). Each slice calls
    ``register(slice_id, lines)`` to declare its line contribution for the
    current candidate; a slice re-registering supersedes its prior value
    (idempotent — a re-run / re-render never double-counts). Introspect with
    ``total`` / ``remaining`` / ``within`` (non-raising) or guard the assembled
    candidate with ``assert_within`` (raises ``PayloadBudgetExceeded``).
    """

    def __init__(self, max_lines):
        if max_lines < 0:
            raise ValueError(f"max_lines must be >= 0, got {max_lines}")
        self._max = max_lines
        self._registered: dict[str, int] = {}

    def register(self, slice_id, lines) -> None:
        """Declare ``slice_id``'s line contribution for the current candidate.
        Overwrites any prior value for the same slice (idempotent)."""
        if lines < 0:
            raise ValueError(
                f"lines must be >= 0, got {lines} for slice {slice_id!r}")
        self._registered[slice_id] = lines

    def total(self) -> int:
        """Sum of all registered slice contributions."""
        return sum(self._registered.values())

    def remaining(self) -> int:
        """Lines left before the ceiling; negative when already over (lets the
        injection site see by how much it must trim)."""
        return self._max - self.total()

    def within(self) -> bool:
        """True while total ≤ ceiling (the ceiling itself is allowed)."""
        return self.total() <= self._max

    def assert_within(self, candidate) -> int:
        """Guard: raise ``PayloadBudgetExceeded`` if over the ceiling, else
        return the current total. ``candidate`` is for the diagnostic only."""
        t = self.total()
        if t > self._max:
            raise PayloadBudgetExceeded(candidate, t, self._max, self._registered)
        return t

    def breakdown(self) -> dict:
        """A copy of {slice_id: lines} — callers cannot mutate internals."""
        return dict(self._registered)
