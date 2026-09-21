"""Behavioral witnesses for the BKT-02 backtesting contract.

These tests deliberately describe the missing B167/B168/B171 behavior at the
public backtesting seams.  They are test-first witnesses: this branch owns no
production remediation.
"""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer


def test_wrong_key_comparison_does_not_qualify_for_grade_a() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="wrong-key",
        scenario_label="wrong-key comparison",
        y_pred={"wrong_metric": [1.0, 2.0]},
        y_true={"metric": [1.0, 2.0]},
    )

    _score, grade = TrustScorer().compute(scenarios=[scenario], biases=[])

    assert scenario.compared_count == 0
    assert grade != "A"


def test_missing_prediction_remains_in_requested_completeness() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="missing-prediction",
        scenario_label="one missing prediction",
        y_pred={"metric": [1.0]},
        y_true={"metric": [1.0, 100.0]},
    )

    assert scenario.requested_count == 2
    assert scenario.compared_count == 1
    assert scenario.missing_count == 1
    assert scenario.invalid_count == 0
    assert scenario.missing_cells == [("metric", 1)]


def test_missing_ci_is_unknown_and_preserves_nominal_level() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="partial-ci",
        scenario_label="one available interval",
        y_pred={"metric": [1.0, 2.0]},
        y_true={"metric": [1.0, 2.0]},
        intervals={"metric": [(0.0, 2.0)]},
        confidence_level=0.80,
    )

    assert scenario.outcome_comparisons[0].within_ci is True
    assert scenario.outcome_comparisons[1].within_ci is None
    assert scenario.interval_requested_count == 2
    assert scenario.interval_available_count == 1
    assert scenario.interval_evaluated_count == 1
    assert scenario.interval_hit_count == 1
    assert scenario.coverage_probability == pytest.approx(1.0)
    assert scenario.nominal_confidence_level == pytest.approx(0.80)


def test_partial_ci_exposes_availability_and_hit_denominators() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="partial-ci-denominators",
        scenario_label="partial interval coverage",
        y_pred={"metric": [1.0, 2.0]},
        y_true={"metric": [1.0, 2.0]},
        intervals={"metric": [(0.5, 1.5)]},
        confidence_level=0.95,
    )

    assert scenario.interval_availability == pytest.approx(1 / 2)
    assert scenario.interval_hit_rate == pytest.approx(1 / 1)
    assert scenario.interval_available_count == 1
    assert scenario.interval_requested_count == 2
    assert scenario.interval_hit_count == 1
    assert scenario.interval_evaluated_count == 1


def test_micro_rmse_is_partition_invariant_and_macro_is_explicit(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0, 0.0]}', encoding="utf-8")

    def plan(
        plan_id: str,
        outcomes: list[float],
        predictions: list[float],
    ) -> HistoricalValidationPlan:
        return HistoricalValidationPlan(
            plan_id=plan_id,
            historical_data_path=str(history_path),
            ground_truth_outcomes={"metric": outcomes},
            target_metrics=["metric"],
            prediction_source=PredictionSource.PROVIDED,
            predicted_outcomes={"metric": predictions},
        )

    whole_report = BacktestOrchestrator(cas_root=str(tmp_path / "whole")).run(
        [plan("whole", [0.0, 10.0, 10.0], [0.0, 0.0, 0.0])]
    )
    partitioned_report = BacktestOrchestrator(
        cas_root=str(tmp_path / "partitioned")
    ).run(
        [
            plan("first", [0.0], [0.0]),
            plan("second", [10.0, 10.0], [0.0, 0.0]),
        ]
    )

    expected_micro_rmse = math.sqrt(200 / 3)
    assert whole_report.overall_rmse == pytest.approx(expected_micro_rmse)
    assert partitioned_report.overall_rmse == pytest.approx(expected_micro_rmse)
    assert partitioned_report.overall_macro_rmse == pytest.approx(5.0)
    assert (
        partitioned_report.aggregation_policy
        == "micro_rmse_with_explicit_equal_scenario_macro"
    )
