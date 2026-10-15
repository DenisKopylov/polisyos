from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_backtest_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract("ir", "backtest")


def _scenario(
    residuals: list[float],
    *,
    metric: str = "observed_value",
    scenario_id: str = "fixture",
    with_intervals: bool = False,
):
    from polisyos.ir.analytics.backtest import BacktestScenario, OutcomeComparison

    comparisons = []
    percentage_errors = []
    for index, residual in enumerate(residuals):
        y_true = 10.0 + index
        relative_error = abs(residual) / abs(y_true) if abs(y_true) > 1e-12 else None
        if relative_error is not None:
            percentage_errors.append(relative_error * 100.0)
        comparisons.append(
            OutcomeComparison(
                metric_name=metric,
                y_pred=y_true + residual,
                y_true=y_true,
                absolute_error=abs(residual),
                relative_error=relative_error,
                within_ci=True if with_intervals else None,
                ci_lower=y_true - 1.0 if with_intervals else None,
                ci_upper=y_true + 1.0 if with_intervals else None,
            )
        )
    absolute_sum = sum(abs(value) for value in residuals)
    squared_sum = sum(value * value for value in residuals)
    count = len(residuals)
    percentage_sum = sum(percentage_errors)
    return BacktestScenario(
        scenario_id=scenario_id,
        scenario_label=scenario_id,
        outcome_comparisons=comparisons,
        rmse=math.sqrt(squared_sum / count) if count else None,
        mae=absolute_sum / count if count else None,
        mape=percentage_sum / len(percentage_errors) if percentage_errors else None,
        coverage_probability=1.0 if with_intervals else None,
        requested_count=count,
        compared_count=count,
        interval_requested_count=count if with_intervals else 0,
        interval_available_count=count if with_intervals else 0,
        interval_evaluated_count=count if with_intervals else 0,
        interval_hit_count=count if with_intervals else 0,
        interval_availability=1.0 if with_intervals else None,
        interval_hit_rate=1.0 if with_intervals else None,
        nominal_confidence_level=0.95 if with_intervals else None,
        interval_type="fixture_interval" if with_intervals else None,
        absolute_error_sum=absolute_sum,
        squared_error_sum=squared_sum,
        percentage_error_sum=percentage_sum,
        percentage_error_count=len(percentage_errors),
        metadata={
            "holdout_windows": ["2025-01-01::2025-12-31"],
            "selected_training_role": "fixture_training",
            "selected_validation_role": "fixture_validation",
            "selected_holdout_role": "fixture_holdout",
        },
    )


def _diagnostic(
    residuals: list[float], *, metric: str = "observed_value", scenario_id: str = "fixture"
):
    from polisyos.ir.analytics.backtest import MetricBiasDiagnostic

    count = len(residuals)
    mean = sum(residuals) / count
    exact_zero = all(value == 0.0 for value in residuals)
    status = "exact_zero" if exact_zero else "available"
    sample_std = math.sqrt(sum((value - mean) ** 2 for value in residuals) / (count - 1))
    statistic = None if exact_zero else mean / (sample_std / math.sqrt(count))
    return MetricBiasDiagnostic(
        metric_name=metric,
        status=status,
        n=count,
        mean_residual=mean,
        magnitude=abs(mean),
        scope={
            "scenario_ids": [scenario_id],
            "holdout_windows": ["2025-01-01::2025-12-31"],
            "selected_training_roles": ["fixture_training"],
            "selected_validation_roles": ["fixture_validation"],
            "selected_holdout_roles": ["fixture_holdout"],
        },
        residual_sign="zero" if exact_zero or mean == 0 else "positive" if mean > 0 else "negative",
        direction_status="not_applicable" if exact_zero else "not_established",
        method_id=None if exact_zero else "scipy.stats.ttest_1samp",
        backend_id=None if exact_zero else "scipy",
        backend_version=None if exact_zero else "1.15.3",
        statistic=statistic,
        p_value=None if exact_zero else 0.121690,
        unresolved_assumptions=(
            ["residual_independence", "multiplicity_policy", "population_scope"]
            if exact_zero
            else [
                "residual_independence",
                "multiplicity_policy",
                "population_scope",
                "metric_direction",
            ]
        ),
    )


def _report(
    residuals: list[float],
    *,
    metric: str = "observed_value",
    scenario_id: str = "fixture",
    with_intervals: bool = False,
):
    from polisyos.ir.analytics.backtest import BacktestReport, BiasDirection

    scenario = _scenario(
        residuals, metric=metric, scenario_id=scenario_id, with_intervals=with_intervals
    )
    exact_zero = all(value == 0.0 for value in residuals)
    absolute_sum = sum(abs(value) for value in residuals)
    squared_sum = sum(value * value for value in residuals)
    count = len(residuals)
    return BacktestReport(
        report_id="s1-reconciled",
        scenarios=[scenario],
        overall_rmse=math.sqrt(squared_sum / count) if count else None,
        overall_mae=absolute_sum / count if count else None,
        overall_mape=scenario.mape,
        overall_coverage_probability=scenario.coverage_probability,
        n_scenarios=1,
        n_metrics_evaluated=count,
        metric_diagnostics=[_diagnostic(residuals, metric=metric, scenario_id=scenario_id)],
        metadata=(
            {
                "interval_contracts": [
                    {
                        "scenario_id": scenario.scenario_id,
                        "nominal_confidence_level": scenario.nominal_confidence_level,
                        "interval_type": scenario.interval_type,
                        "interval_requested_count": scenario.interval_requested_count,
                        "interval_available_count": scenario.interval_available_count,
                        "interval_evaluated_count": scenario.interval_evaluated_count,
                        "interval_hit_count": scenario.interval_hit_count,
                    }
                ]
            }
            if with_intervals
            else {}
        ),
        overall_bias_direction=BiasDirection.NEUTRAL if exact_zero else BiasDirection.UNKNOWN,
        degraded=not exact_zero,
        degraded_reasons=[] if exact_zero else [f"metric_direction_not_established:{metric}"],
        trust_eligible=False,
        trust_score=None,
        trust_grade=None,
    )


def test_source_reconciliation_accepts_real_rows_and_keeps_legacy_candidate_untrusted() -> None:
    from polisyos.ir.analytics.backtest import BacktestReport

    variable = _report([0.5, 1.5, 2.5])
    assert variable.metric_diagnostics_are_source_bound() is True
    assert variable.has_source_bound_exact_zero_metrics() is False

    exact_zero = _report([0.0, 0.0, 0.0])
    assert exact_zero.metric_diagnostics_are_source_bound() is True
    assert exact_zero.has_source_bound_exact_zero_metrics() is True
    assert exact_zero.trust_eligible is False

    legacy = BacktestReport.model_validate(
        {
            "report_id": "legacy-with-trust-marker",
            "trust_eligible": True,
            "trust_score": 0.9,
            "trust_grade": "A",
        }
    )
    assert legacy.metric_diagnostics_are_source_bound() is False
    assert legacy.has_source_bound_exact_zero_metrics() is False
    assert legacy.trust_eligible is False
    assert legacy.trust_score is None and legacy.trust_grade is None
    assert "metric_diagnostics_not_source_bound" in legacy.degraded_reasons


def test_source_reconciliation_rejects_marker_retaining_scenario_flip_and_metric_set_gaps() -> None:
    from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator

    valid_zero = _report([0.0, 0.0, 0.0])
    source_flipped = _report([1.0, 0.0, 0.0])
    producer = BacktestOrchestrator.__new__(BacktestOrchestrator)
    _, produced_diagnostics, _ = producer._detect_systematic_biases(source_flipped.scenarios)
    assert len(produced_diagnostics) == 1

    # Keep the actual producer's source-bound count, mean, magnitude, scope, direction,
    # and statistical result. Retaining only its old exact-zero status violates the
    # diagnostic's own execution-identity contract before report-level reconciliation.
    payload = source_flipped.model_dump(mode="python")
    payload["metric_diagnostics"] = [
        produced_diagnostics[0].model_copy(
            update={"status": valid_zero.metric_diagnostics[0].status}
        )
    ]
    with pytest.raises(
        ValidationError,
        match="non-available diagnostic cannot claim an executed statistical method",
    ):
        type(valid_zero).model_validate(payload)

    first = _scenario([0.5, 1.5, 2.5], metric="metric_a", scenario_id="a")
    second = _scenario([0.0, 0.0, 0.0], metric="metric_b", scenario_id="b")
    omitted = {
        "report_id": "omitted-sibling-metric",
        "scenarios": [first, second],
        "overall_mae": 0.75,
        "overall_rmse": math.sqrt(8.75 / 6.0),
        "overall_mape": math.fsum(
            scenario.percentage_error_sum or 0.0 for scenario in (first, second)
        )
        / sum(scenario.percentage_error_count for scenario in (first, second)),
        "n_scenarios": 2,
        "n_metrics_evaluated": 6,
        "metric_diagnostics": [_diagnostic([0.5, 1.5, 2.5], metric="metric_a", scenario_id="a")],
        "overall_bias_direction": "unknown",
        "degraded": True,
        "degraded_reasons": ["metric_direction_not_established:metric_a"],
        "trust_eligible": False,
    }
    with pytest.raises(ValidationError, match="complete actual metric set"):
        type(valid_zero).model_validate(omitted)


def test_source_reconciliation_recomputes_mape_and_interval_summaries() -> None:
    source = _report([0.0, 0.0, 0.0], with_intervals=True)
    assert source.metric_diagnostics_are_source_bound() is True
    forged = source.model_dump(mode="python")
    forged["scenarios"][0]["mape"] = 4.0
    with pytest.raises(ValidationError, match="scenario MAPE"):
        type(source).model_validate(forged)
    forged = source.model_dump(mode="python")
    forged["scenarios"][0]["outcome_comparisons"][0]["relative_error"] = 0.5
    with pytest.raises(ValidationError, match="relative_error"):
        type(source).model_validate(forged)
    forged = source.model_dump(mode="python")
    forged["scenarios"][0]["coverage_probability"] = 0.0
    with pytest.raises(ValidationError, match="scenario coverage"):
        type(source).model_validate(forged)
    forged = source.model_dump(mode="python")
    forged["overall_mape"] = 1.0
    with pytest.raises(ValidationError, match="overall MAPE"):
        type(source).model_validate(forged)


def test_source_reconciliation_rejects_forged_availability_and_t_statistic() -> None:
    valid = _report([0.5, 1.5, 2.5])
    payload = valid.model_dump(mode="python")
    diagnostic = payload["metric_diagnostics"][0]
    diagnostic.update(
        {
            "status": "not_computable",
            "method_id": None,
            "backend_id": None,
            "backend_version": None,
            "statistic": None,
            "p_value": None,
            "reason": "zero_variance",
        }
    )
    with pytest.raises(
        ValidationError, match="variable source residuals cannot be marked not_computable"
    ):
        type(valid).model_validate(payload)

    payload = valid.model_dump(mode="python")
    payload["metric_diagnostics"][0]["statistic"] += 5.0
    with pytest.raises(ValidationError, match="executed diagnostic does not reconcile"):
        type(valid).model_validate(payload)


def test_metric_bias_diagnostic_is_exposed_by_stable_ir_facades() -> None:
    from polisyos import ir
    from polisyos.ir.analytics import MetricBiasDiagnostic as AnalyticsMetricBiasDiagnostic
    from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

    assert "MetricBiasDiagnostic" in ir.__all__
    assert ANALYTICS_FACADE_EXPORTS["MetricBiasDiagnostic"] == (
        "polisyos.ir.analytics.backtest",
        "MetricBiasDiagnostic",
    )
    assert ir.MetricBiasDiagnostic is AnalyticsMetricBiasDiagnostic
