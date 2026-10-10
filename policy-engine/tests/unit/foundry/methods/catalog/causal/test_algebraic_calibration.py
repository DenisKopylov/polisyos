from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.algebraic_calibration import (
    TetradBlockCalibrationMetrics,
    TetradCalibrationBenchmarkReport,
    TetradCalibrationRunResult,
    TetradCalibrationScenarioKind,
    decide_tetrad_severity,
    default_tetrad_calibration_benchmark_suite,
    generate_tetrad_calibration_dataset,
    iter_tetrad_calibration_cases,
    run_tetrad_calibration_case,
    run_tetrad_calibration_suite,
    summarize_tetrad_type_errors,
    tetrad_threshold_recommendations,
)


def test_default_tetrad_calibration_suite_materializes_research_grid() -> None:
    suite = default_tetrad_calibration_benchmark_suite()
    cases = iter_tetrad_calibration_cases(suite)

    assert {scenario.kind for scenario in suite.scenarios} == set(TetradCalibrationScenarioKind)
    assert len(cases) == (
        len(suite.scenarios)
        * len(suite.sample_sizes)
        * len(suite.indicator_counts)
        * len(suite.missing_rates)
        * len(suite.routes)
    )
    assert "algebraic_tetrad_min_q" in suite.metrics
    assert any(case.expected_violation for case in cases)
    assert any(not case.expected_violation for case in cases)


def test_tetrad_calibration_dataset_generator_supports_core_scenarios() -> None:
    exact, names, exact_meta = generate_tetrad_calibration_dataset(
        scenario_kind=TetradCalibrationScenarioKind.EXACT_NULL,
        n_samples=40,
        n_indicators=4,
        seed=1,
    )
    ordinal, _, ordinal_meta = generate_tetrad_calibration_dataset(
        scenario_kind=TetradCalibrationScenarioKind.ORDINAL_ROUTE,
        n_samples=40,
        n_indicators=4,
        missing_rate=0.10,
        seed=2,
    )

    assert exact.shape == (40, 4)
    assert names == ["X1", "X2", "X3", "X4"]
    assert exact_meta["scenario_kind"] == "exact_null"
    finite_ordinal = ordinal[np.isfinite(ordinal)]
    assert set(np.unique(finite_ordinal)).issubset({0.0, 1.0, 2.0, 3.0})
    assert np.isnan(ordinal).any()
    assert ordinal_meta["scenario_kind"] == "ordinal_route"


def test_tetrad_severity_requires_high_confidence_regime_for_blocker() -> None:
    strong = TetradBlockCalibrationMetrics(
        min_q=0.001,
        max_abs_z=5.2,
        median_delta=0.12,
        violation_support=0.96,
        effective_n=650,
        n_violations=3,
        bootstrap_draws=1200,
    )
    screening = strong.model_copy(update={"bootstrap_draws": 200})
    low_n = strong.model_copy(update={"effective_n": 60})
    ordinal_route = strong.model_copy(
        update={"continuous_only": False, "route": "polychoric_tetrad"}
    )

    assert decide_tetrad_severity(strong).severity == "blocker"
    screening_decision = decide_tetrad_severity(screening)
    assert screening_decision.severity == "warning"
    assert "bootstrap_draws_below_blocker_floor" in screening_decision.blocker_eligibility_failures
    assert decide_tetrad_severity(low_n).severity == "info"
    ordinal_decision = decide_tetrad_severity(ordinal_route)
    assert ordinal_decision.severity == "warning"
    assert "noncontinuous_or_ordinal_route" in ordinal_decision.blocker_eligibility_failures


def test_tetrad_type_error_summary_reports_false_alarm_and_power_rates() -> None:
    null_metrics = TetradBlockCalibrationMetrics(effective_n=500)
    alt_metrics = TetradBlockCalibrationMetrics(
        min_q=0.001,
        max_abs_z=5.0,
        median_delta=0.10,
        violation_support=0.95,
        effective_n=600,
        n_violations=2,
        bootstrap_draws=1000,
    )
    summary = summarize_tetrad_type_errors(
        [
            TetradCalibrationRunResult(
                case_id="null_ok",
                scenario_kind=TetradCalibrationScenarioKind.EXACT_NULL,
                expected_violation=False,
                severity="info",
                metrics=null_metrics,
            ),
            TetradCalibrationRunResult(
                case_id="null_warn",
                scenario_kind=TetradCalibrationScenarioKind.EXACT_NULL,
                expected_violation=False,
                severity="warning",
                metrics=null_metrics,
            ),
            TetradCalibrationRunResult(
                case_id="alt_hit",
                scenario_kind=TetradCalibrationScenarioKind.MODERATE_ALTERNATIVE,
                expected_violation=True,
                severity="blocker",
                metrics=alt_metrics,
            ),
        ]
    )

    assert summary["exact_null"]["false_alarm_rate"] == 0.5
    assert summary["exact_null"]["blocker_false_alarm_rate"] == 0.0
    assert summary["moderate_alternative"]["warning_or_blocker_power"] == 1.0


def test_tetrad_calibration_case_runner_is_executable_for_both_routes() -> None:
    suite = default_tetrad_calibration_benchmark_suite()
    cases = iter_tetrad_calibration_cases(suite)
    bootstrap_case = next(case for case in cases if case.route == "bootstrap_tetrad")
    modified_case = next(case for case in cases if case.route == "modified_bootstrap_tetrad")

    bootstrap_result = run_tetrad_calibration_case(
        bootstrap_case,
        seed=11,
        bootstrap_draws=120,
    )
    modified_result = run_tetrad_calibration_case(
        modified_case,
        seed=11,
        bootstrap_draws=120,
    )

    assert bootstrap_result.metrics.bootstrap_draws == 120
    assert bootstrap_result.metrics.route == "bootstrap_tetrad"
    assert modified_result.metrics.route == "modified_bootstrap_tetrad"
    assert modified_result.metrics.route_calibrated is True


def test_tetrad_calibration_suite_runner_returns_type_error_report() -> None:
    report = run_tetrad_calibration_suite(
        default_tetrad_calibration_benchmark_suite(),
        seed=5,
        bootstrap_draws=80,
        max_cases=4,
    )

    assert isinstance(report, TetradCalibrationBenchmarkReport)
    assert report.bootstrap_draws == 80
    assert len(report.results) == 4
    assert report.type_error_summary


def test_tetrad_threshold_recommendations_match_stage_8_2_metric_set() -> None:
    recommendations = tetrad_threshold_recommendations()

    assert len(recommendations) == 10
    assert {item.metric_name for item in recommendations} == {
        "algebraic_tetrad_min_q",
        "algebraic_tetrad_max_abs_z",
        "algebraic_tetrad_median_delta",
        "algebraic_tetrad_violation_support",
        "algebraic_tetrad_effective_n",
    }
