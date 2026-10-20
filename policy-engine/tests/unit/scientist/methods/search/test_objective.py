"""Regression tests for search objective metric normalization."""

from __future__ import annotations

import math
from typing import Any

import pytest

from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    ObjectiveScoreStatus,
)

# A declared fixture unit exercises generic binding only; it is not a production fiscal claim.
FISCAL_UNIT_FIXTURE = "usd"


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        (
            {
                "budget_deficit": 100.0,
                "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE},
            },
            100.0,
        ),
        (
            {
                "gov_balance": None,
                "budget_deficit": 100.0,
                "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE},
            },
            100.0,
        ),
        (
            {
                "gov_balance": 0.0,
                "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE},
            },
            0.0,
        ),
        (
            {
                "gov_balance": 0.0,
                "budget_deficit": 0.0,
                "metric_units": {
                    "gov_balance": FISCAL_UNIT_FIXTURE,
                    "budget_deficit": FISCAL_UNIT_FIXTURE,
                },
            },
            0.0,
        ),
        (
            {
                "gov_balance": -5.0,
                "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE},
            },
            5.0,
        ),
        (
            {
                "government_balance": -12.0,
                "metric_units": {"government_balance": FISCAL_UNIT_FIXTURE},
            },
            12.0,
        ),
    ],
)
def test_budget_deficit_normalizes_unit_bound_aliases_and_sign(
    results: dict[str, Any],
    expected: float,
) -> None:
    """Explicitly unit-bound measurements normalize without inventing a zero."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert evaluated.score_status is ObjectiveScoreStatus.AVAILABLE
    assert evaluated.raw_value == expected
    assert evaluated.is_satisfied is True


def test_budget_deficit_marks_missing_metric_unusable() -> None:
    """No fiscal metric remains unavailable with the default unselected unit."""
    evaluated = BudgetDeficitObjective().evaluate({})

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize("balance", [math.nan, math.inf, -math.inf])
def test_budget_deficit_keeps_non_finite_metric_unusable(balance: float) -> None:
    """Non-finite measurements fail after a valid fixture unit is supplied."""
    results = {
        "gov_balance": balance,
        "budget_deficit": 100.0,
        "metric_units": {
            "gov_balance": FISCAL_UNIT_FIXTURE,
            "budget_deficit": FISCAL_UNIT_FIXTURE,
        },
    }
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize("value", [True, False])
def test_budget_deficit_rejects_boolean_measurements(value: bool) -> None:
    """Boolean flags are invalid even when the fixture declares a matching unit."""
    results = {
        "budget_deficit": value,
        "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE},
    }
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.is_satisfied is False


def test_budget_deficit_rejects_conflicting_balance_and_deficit_families() -> None:
    """The original cross-family conflict fails with explicit units on both inputs."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {
            "gov_balance": 0.0,
            "budget_deficit": 100.0,
            "metric_units": {
                "gov_balance": FISCAL_UNIT_FIXTURE,
                "budget_deficit": FISCAL_UNIT_FIXTURE,
            },
        }
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.score_assessment is not None
    assert evaluated.score_assessment.limitation == (
        "objective_basis_conflicting_fiscal_measurements"
    )
    assert evaluated.is_satisfied is False


def test_budget_deficit_rejects_conflicting_balance_aliases() -> None:
    """Conflicting same-family aliases remain invalid with unit evidence present."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {
            "gov_balance": -100.0,
            "government_balance": 100.0,
            "metric_units": {
                "gov_balance": FISCAL_UNIT_FIXTURE,
                "government_balance": FISCAL_UNIT_FIXTURE,
            },
        }
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.is_satisfied is False
