"""Regression tests for search objective metric normalization."""

from __future__ import annotations

import math
from typing import Any

import pytest

from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    ObjectiveScoreStatus,
    _assess_default_search_objective,
    _evaluate_configured_objective_source,
)

# A declared fixture unit exercises generic binding only; it is not a production fiscal claim.
FISCAL_UNIT_FIXTURE = "usd"


@pytest.mark.parametrize(
    "results",
    [
        {"gov_balance": 0.0, "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE}},
        {"gov_balance": -5.0, "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE}},
        {
            "government_balance": -12.0,
            "metric_units": {"government_balance": FISCAL_UNIT_FIXTURE},
        },
        {
            "gov_balance": -35.0,
            "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE},
            "quantity_role": "period_flow",
        },
    ],
)
def test_balance_stock_alias_does_not_establish_budget_deficit(
    results: dict[str, Any],
) -> None:
    """A scalar unit or source role label cannot turn balance stock into a deficit."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert evaluated.score_assessment is not None
    assert evaluated.score_assessment.limitation == (
        "budget_deficit_period_flow_source_not_established"
    )
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize(
    "unit_view",
    [
        pytest.param(None, id="metric-units-absent"),
        pytest.param({}, id="empty-unit-map"),
        pytest.param(
            {"deficit": FISCAL_UNIT_FIXTURE},
            id="unit-on-other-alias-not-selected-alias",
        ),
    ],
)
def test_budget_deficit_requires_unit_evidence_for_selected_alias(
    unit_view: dict[str, str] | None,
) -> None:
    """Configured direct deficit inputs need units bound to the actual selected alias."""
    results: dict[str, Any] = {"budget_deficit": 100.0}
    if unit_view is not None:
        results["metric_units"] = unit_view
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert evaluated.score_assessment is not None
    assert evaluated.score_assessment.limitation == "objective_source_unit_not_established"
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize(
    ("results", "expected_value"),
    [
        (
            {"budget_deficit": 100.0, "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE}},
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
        ({"deficit": -100.0, "metric_units": {"deficit": FISCAL_UNIT_FIXTURE}}, 100.0),
        (
            {
                "gov_balance": -100.0,
                "budget_deficit": 100.0,
                "metric_units": {
                    "gov_balance": FISCAL_UNIT_FIXTURE,
                    "budget_deficit": FISCAL_UNIT_FIXTURE,
                },
            },
            100.0,
        ),
        ({"budget_deficit": 0.0, "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE}}, 0.0),
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
    ],
)
def test_budget_deficit_scores_selected_unit_compatible_deficit_aliases(
    results: dict[str, Any], expected_value: float
) -> None:
    """A configured direct deficit operand is scored, including null alternative and zero."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(results)

    assert evaluated.raw_value == expected_value
    assert evaluated.score_status is ObjectiveScoreStatus.AVAILABLE
    assert evaluated.is_satisfied is True


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_budget_deficit_rejects_non_finite_deficit_aliases(value: float) -> None:
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {"budget_deficit": value, "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE}}
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID


def test_budget_deficit_rejects_conflicting_deficit_aliases() -> None:
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {
            "budget_deficit": 100.0,
            "deficit": 101.0,
            "metric_units": {
                "budget_deficit": FISCAL_UNIT_FIXTURE,
                "deficit": FISCAL_UNIT_FIXTURE,
            },
        }
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID


def test_budget_deficit_rejects_incompatible_deficit_alias_unit() -> None:
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {"budget_deficit": 100.0, "metric_units": {"budget_deficit": "eur"}}
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID


def test_budget_deficit_marks_missing_metric_unusable() -> None:
    """No fiscal metric remains unavailable with the default unselected unit."""
    evaluated = BudgetDeficitObjective().evaluate({})

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize("balance", [math.nan, math.inf, -math.inf])
def test_budget_deficit_invalid_stock_does_not_supply_a_period_measurement(balance: float) -> None:
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {"gov_balance": balance, "metric_units": {"gov_balance": FISCAL_UNIT_FIXTURE}}
    )

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


@pytest.mark.parametrize("balance", [0.0, -77.0, math.inf])
def test_period_deficit_keeps_a_separate_stock_outside_its_measurement_basis(
    balance: float,
) -> None:
    objective = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE)
    source = {"budget_deficit": 7.0, "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE}}
    combined = {
        **source,
        "gov_balance": balance,
        "metric_units": {**source["metric_units"], "gov_balance": "eur"},
    }

    direct = objective.evaluate(source)
    observed = objective.evaluate(combined)
    assert observed.score_status is ObjectiveScoreStatus.AVAILABLE
    assert observed.raw_value == 7.0
    assert observed.score_assessment == direct.score_assessment
    assert observed.score_assessment is not None
    assert observed.score_assessment.source_values == (("budget_deficit", 7.0),)
    assert observed.score_assessment.source_unit_bindings == (("budget_deficit", "usd"),)


def test_default_scalar_rechecks_period_deficit_without_binding_the_stock() -> None:
    source = {
        "gdp_change": 2.0,
        "budget_deficit": 7.0,
        "budget_deficit_objective_usable": True,
        "budget_deficit_objective_value": 7.0,
        "metric_units": {"budget_deficit": "usd", "gdp_change": "usd"},
    }
    direct = _assess_default_search_objective(source, expected_unit=FISCAL_UNIT_FIXTURE)
    observed = _assess_default_search_objective(
        {**source, "gov_balance": -2.0}, expected_unit=FISCAL_UNIT_FIXTURE
    )

    assert observed == direct
    assert observed.objective_value == 1.5
    assert observed.score_status is ObjectiveScoreStatus.AVAILABLE
    assert (
        _assess_default_search_objective(
            {**source, "budget_deficit_objective_value": 2.0},
            expected_unit=FISCAL_UNIT_FIXTURE,
        ).score_status
        is ObjectiveScoreStatus.INVALID
    )


def test_legacy_fiscal_rule_replays_its_original_conflict() -> None:
    assessment = _evaluate_configured_objective_source(
        {
            "kind": "budget_deficit",
            "weight": 1.0,
            "threshold": None,
            "expected_unit": FISCAL_UNIT_FIXTURE,
        },
        {
            "gov_balance": 0.0,
            "budget_deficit": 100.0,
            "metric_units": {
                "gov_balance": FISCAL_UNIT_FIXTURE,
                "budget_deficit": FISCAL_UNIT_FIXTURE,
            },
        },
    )

    assert assessment.status is ObjectiveScoreStatus.INVALID
    assert assessment.limitation == "objective_basis_conflicting_fiscal_measurements"


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


def test_period_deficit_rejects_conflicting_unit_views_of_the_selected_measurement() -> None:
    """The selected flow rejects contradictory source-unit metadata."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {
            "budget_deficit": 35.0,
            "metric_units": {"budget_deficit": FISCAL_UNIT_FIXTURE},
            "metrics": {
                "budget_deficit": 35.0,
                "metric_units": {"budget_deficit": "eur"},
            },
        }
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.is_satisfied is False


@pytest.mark.parametrize(
    ("alias", "value"),
    [("budget_deficit", 35.0), ("deficit", -35.0)],
)
@pytest.mark.parametrize("unit", ["usd ", "", None, True])
def test_budget_deficit_rejects_malformed_units_on_present_alias(
    alias: str, value: float, unit: Any
) -> None:
    """Malformed unit evidence remains invalid instead of being hidden by limitation."""
    evaluated = BudgetDeficitObjective(expected_unit=FISCAL_UNIT_FIXTURE).evaluate(
        {alias: value, "metric_units": {alias: unit}}
    )

    assert math.isnan(evaluated.raw_value)
    assert evaluated.score_status is ObjectiveScoreStatus.INVALID
    assert evaluated.is_satisfied is False
