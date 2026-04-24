"""Property-based tests for BudgetState arithmetic."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from polisyos.scientist.engine.budget import BudgetLimit, BudgetState

pytestmark = pytest.mark.property

_pos_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("10000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

_small_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


def _budget_with_limit(max_usd: Decimal, key: str = "run") -> BudgetState:
    return BudgetState(limits={key: BudgetLimit(key=key, max_usd=max_usd)})


@given(max_usd=_pos_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_remaining_starts_at_max(max_usd: Decimal):
    """Fresh budget has remaining == max_usd."""
    bs = _budget_with_limit(max_usd)
    assert bs.remaining("run") == max_usd


@given(max_usd=_pos_decimal, spend=_small_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_remaining_non_negative_after_capped_spend(max_usd: Decimal, spend: Decimal):
    """remaining >= 0 when spend <= limit."""
    assume(spend <= max_usd)
    bs = _budget_with_limit(max_usd)
    bs.record_spend("run", spend)
    rem = bs.remaining("run")
    assert rem is not None
    assert rem >= 0


@given(max_usd=_pos_decimal, x=_small_decimal, y=_small_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_would_exceed_monotone(max_usd: Decimal, x: Decimal, y: Decimal):
    """If would_exceed at x, then also at y > x."""
    assume(y > x)
    bs = _budget_with_limit(max_usd)
    if bs.would_exceed("run", x):
        assert bs.would_exceed("run", y)


@given(a=_small_decimal, b=_small_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_record_spend_additive(a: Decimal, b: Decimal):
    """record_spend(a) + record_spend(b) yields spent == a + b."""
    bs = BudgetState()
    bs.record_spend("k", a)
    bs.record_spend("k", b)
    assert bs.spent["k"] == a + b


@given(max_usd=_pos_decimal, amount=_small_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_reserve_commit_equals_spend(max_usd: Decimal, amount: Decimal):
    """reserve + commit_reservation ≡ record_spend."""
    assume(amount <= max_usd)
    bs1 = _budget_with_limit(max_usd)
    bs1.reserve("run", amount)
    bs1.commit_reservation("run", amount)

    bs2 = _budget_with_limit(max_usd)
    bs2.record_spend("run", amount)

    assert bs1.spent["run"] == bs2.spent["run"]
    assert bs1.remaining("run") == bs2.remaining("run")


@given(max_usd=_pos_decimal, amount=_small_decimal)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_reserve_release_is_noop(max_usd: Decimal, amount: Decimal):
    """reserve + release returns reserved to 0."""
    assume(amount <= max_usd)
    bs = _budget_with_limit(max_usd)
    bs.reserve("run", amount)
    assert bs.reserved.get("run", Decimal(0)) == amount
    bs.release("run", amount)
    assert bs.reserved.get("run", Decimal(0)) == Decimal(0)


def test_no_limit_remaining_is_none():
    """remaining returns None when no limit is set."""
    bs = BudgetState()
    assert bs.remaining("nonexistent") is None


def test_no_limit_would_exceed_is_false():
    """would_exceed returns False when no limit is set."""
    bs = BudgetState()
    assert bs.would_exceed("nonexistent", Decimal("999999")) is False
