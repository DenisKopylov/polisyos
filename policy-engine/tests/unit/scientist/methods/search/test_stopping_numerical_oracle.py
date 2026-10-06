"""B108/B122 analytic oracles, without selecting a scientific near-zero scale."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.search.objective import BudgetDeficitObjective
from polisyos.scientist.methods.search.stopping import ImprovementPlateau


@pytest.mark.parametrize(
    "metrics, expected",
    [
        ({"budget_deficit": 100.0}, 100.0),
        ({"gov_balance": None, "budget_deficit": 100.0}, 100.0),
        ({"gov_balance": -100.0}, 100.0),
        ({"gov_balance": 0.0, "budget_deficit": 100.0}, 0.0),
        ({"gov_balance": 100.0}, 0.0),
    ],
)
def test_measured_budget_alias_and_genuine_zero_preserve_minimization(
    metrics: dict[str, float | None],
    expected: float,
) -> None:
    value = BudgetDeficitObjective().evaluate(metrics)
    assert value.raw_value == expected
    assert value.normalized_value == expected and value.is_satisfied


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"gov_balance": None},
        {"budget_deficit": math.nan},
        {"budget_deficit": math.inf},
        {"budget_deficit": -math.inf},
        {"budget_deficit": 1.0, "deficit": 2.0},
    ],
)
def test_unusable_budget_does_not_become_optimal_zero(metrics: dict[str, float | None]) -> None:
    value = BudgetDeficitObjective().evaluate(metrics)
    assert not value.is_satisfied
    assert not math.isfinite(value.raw_value)


@pytest.mark.parametrize(
    "values, threshold, should_stop",
    [
        ([0.0, 1.0, 1.0], 0.01, True),
        ([0.0, -1.0, -1.0], 0.01, False),
        ([0.0, 0.0, 0.0], 0.01, True),
        ([-1e-11, 1e-11, 1e-11], 1e-12, True),
        ([1e-11, -1e-11, -1e-11], 1e-12, False),
        ([-1.0, -2.0, -2.0], 0.01, False),
        ([-1.0, -0.5, -0.5], 0.01, True),
    ],
)
def test_signed_plateau_cases_with_explicit_caller_threshold(
    values: list[float],
    threshold: float,
    should_stop: bool,
) -> None:
    result = ImprovementPlateau(patience=2, min_improvement=threshold).check(
        [{"objective_value": value} for value in values],
        {},
    )
    assert result.should_stop is should_stop
    if should_stop:
        assert math.isfinite(result.details["improvement"])


@pytest.mark.parametrize(
    "values",
    [
        [math.nan, 1.0, 1.0],
        [1.0, math.nan, math.nan],
        [math.inf, math.inf, math.inf],
        [-math.inf, -math.inf, -math.inf],
    ],
)
def test_undefined_plateau_comparison_is_rejected_or_explicitly_limited(
    values: list[float],
) -> None:
    """Either policy is admissible here; silently returning no reason is not."""
    try:
        result = ImprovementPlateau(patience=2).check(
            [{"objective_value": value} for value in values],
            {},
        )
    except ValueError:
        return
    assert result.reason or result.details, (
        "non-finite history silently entered numerical comparison"
    )
