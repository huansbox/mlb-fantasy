"""Unit tests for payload_budget (issue 039 / 318b).

The budget is a pure accounting gate: slices each declare how many payload
lines they add for one candidate via ``register``, and the budget enforces a
single per-candidate ceiling. It owns the *mechanism* (count + assert), never
the *policy* (which lines to drop when over — that is the injection site's
job). Tests therefore exercise accounting + the assert boundary only, with no
knowledge of line content or any fa_scan wiring.
"""

import pytest

from payload_budget import PayloadBudget, PayloadBudgetExceeded


# ── construction ──

def test_negative_max_lines_rejected():
    with pytest.raises(ValueError):
        PayloadBudget(max_lines=-1)


def test_empty_budget_state():
    b = PayloadBudget(max_lines=3)
    assert b.total() == 0
    assert b.remaining() == 3
    assert b.within() is True
    assert b.breakdown() == {}


# ── register accumulation ──

def test_register_accumulates_across_slices():
    b = PayloadBudget(max_lines=5)
    b.register("ledger", 3)
    b.register("platoon", 1)
    assert b.total() == 4
    assert b.remaining() == 1
    assert b.breakdown() == {"ledger": 3, "platoon": 1}


def test_register_same_slice_overwrites_not_doubles():
    # A slice re-registering (re-run, re-render) must not double-count.
    b = PayloadBudget(max_lines=5)
    b.register("ledger", 3)
    b.register("ledger", 2)  # supersedes, not adds
    assert b.total() == 2
    assert b.breakdown() == {"ledger": 2}


def test_register_zero_lines_is_legal():
    # A slice that contributes nothing for this candidate registers 0.
    b = PayloadBudget(max_lines=3)
    b.register("platoon", 0)
    assert b.total() == 0
    assert b.breakdown() == {"platoon": 0}


def test_register_negative_lines_rejected():
    b = PayloadBudget(max_lines=3)
    with pytest.raises(ValueError):
        b.register("platoon", -1)


def test_register_returns_none():
    # register is a side-effecting declaration, not a query — slices use
    # remaining() to introspect.
    b = PayloadBudget(max_lines=3)
    assert b.register("ledger", 1) is None


# ── within / boundary ──

def test_within_true_below_and_at_limit():
    b = PayloadBudget(max_lines=3)
    b.register("a", 2)
    assert b.within() is True          # below
    b.register("b", 1)
    assert b.total() == 3
    assert b.within() is True          # exactly at the ceiling is OK (≤)
    assert b.remaining() == 0


def test_within_false_over_limit():
    b = PayloadBudget(max_lines=3)
    b.register("a", 4)
    assert b.within() is False
    assert b.remaining() == -1         # remaining may go negative


# ── assert_within ──

def test_assert_within_returns_total_when_ok():
    b = PayloadBudget(max_lines=3)
    b.register("a", 2)
    assert b.assert_within("Some Candidate") == 2


def test_assert_within_passes_exactly_at_limit():
    b = PayloadBudget(max_lines=3)
    b.register("a", 3)
    assert b.assert_within("Some Candidate") == 3  # no raise at the boundary


def test_assert_within_raises_when_exceeded():
    b = PayloadBudget(max_lines=3)
    b.register("ledger", 3)
    b.register("swap", 6)
    with pytest.raises(PayloadBudgetExceeded):
        b.assert_within("Vargas")


def test_exceeded_exception_carries_diagnostic_context():
    b = PayloadBudget(max_lines=3)
    b.register("ledger", 3)
    b.register("swap", 6)
    with pytest.raises(PayloadBudgetExceeded) as ei:
        b.assert_within("Vargas")
    exc = ei.value
    assert exc.candidate == "Vargas"
    assert exc.total == 9
    assert exc.limit == 3
    assert exc.breakdown == {"ledger": 3, "swap": 6}
    # the offending slices should be inspectable from the message too
    assert "Vargas" in str(exc)
    assert "swap" in str(exc)


# ── multi-pool isolation (the "tag pool vs diff pool" use case) ──

def test_multiple_instances_are_independent():
    # The injection site builds separate pools (e.g. a 3-line tag pool and a
    # wider diff-table pool) as separate instances; they must not share state.
    tag_pool = PayloadBudget(max_lines=3)
    diff_pool = PayloadBudget(max_lines=8)
    tag_pool.register("platoon", 1)
    diff_pool.register("swap", 7)
    assert tag_pool.total() == 1
    assert diff_pool.total() == 7
    assert tag_pool.breakdown() == {"platoon": 1}
    assert diff_pool.breakdown() == {"swap": 7}


def test_breakdown_is_a_copy_not_internal_ref():
    # Callers must not be able to mutate budget internals via breakdown().
    b = PayloadBudget(max_lines=3)
    b.register("a", 1)
    snap = b.breakdown()
    snap["a"] = 99
    assert b.breakdown() == {"a": 1}
