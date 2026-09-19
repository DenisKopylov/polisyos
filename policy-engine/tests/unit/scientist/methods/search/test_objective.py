"""Regression tests for search objective metric normalization."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.objective import BudgetDeficitObjective


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ({"budget_deficit": 100.0}, 100.0),
        ({"gov_balance": None, "budget_deficit": 100.0}, 100.0),
        ({"gov_balance": 0.0, "budget_deficit": 100.0}, 0.0),
        ({"gov_balance": -5.0}, 5.0),
        ({"government_balance": -12.0}, 12.0),
    ],
)
def test_budget_deficit_normalizes_missing_null_alias_and_sign(
    results: dict[str, float | None],
    expected: float,
) -> None:
    """A present balance wins, while a missing/null balance uses the deficit alias."""
    # Catches the production mutation that defaults absent gov_balance to 0.0
    # instead of distinguishing absent, null, and an explicit numeric zero.
    value = BudgetDeficitObjective().evaluate(results).raw_value

    assert value == expected


def test_budget_deficit_marks_missing_metric_unusable() -> None:
    """No fiscal metric must not receive an invented optimal zero."""
    # Catches the production mutation that maps an entirely missing metric to
    # a valid zero and leaves it eligible for numeric comparison.
    evaluated = BudgetDeficitObjective().evaluate({})

    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize("balance", [math.nan, math.inf, -math.inf])
def test_budget_deficit_keeps_non_finite_metric_unusable(balance: float) -> None:
    """Non-finite primary values must not silently fall back or become scores."""
    # Catches the production mutation that treats NaN/inf as an ordinary
    # balance and lets a non-finite result pass the objective gate.
    evaluated = BudgetDeficitObjective().evaluate(
        {"gov_balance": balance, "budget_deficit": 100.0}
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False


def test_budget_deficit_rejects_conflicting_balance_aliases() -> None:
    """Conflicting aliases must not silently choose one authority."""
    # Catches the production mutation that takes the first alias and hides a
    # disagreement between independently supplied balance measurements.
    evaluated = BudgetDeficitObjective().evaluate(
        {"gov_balance": -100.0, "government_balance": 100.0}
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.is_satisfied is False
