"""Exercise coverage, report completeness, and range at backtesting boundaries."""

from __future__ import annotations

import math
import sys

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    OutcomeComparison,
)
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

    score, grade = TrustScorer().compute(scenarios=[scenario], biases=[])

    assert scenario.compared_count == 0
    assert score == pytest.approx(0.0)
    assert grade != "A"


def test_incomplete_or_empty_report_is_not_trust_eligible(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0]}', encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="wrong-key-report",
        historical_data_path=str(history_path),
        ground_truth_outcomes={"metric": [1.0, 2.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"wrong_metric": [1.0, 2.0]},
    )

    report = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run([plan])

    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None


def test_zero_evidence_does_not_receive_trust_grade() -> None:
    score, grade = TrustScorer().compute(
        scenarios=[BacktestScenario(scenario_id="empty", scenario_label="empty")],
        biases=[],
    )

    assert score == pytest.approx(0.0)
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


def test_legacy_v1_payload_preserves_read_compatibility_and_ci_unknown_default() -> None:
    legacy_payload = {
        "schema_version": "1.0",
        "report_id": "legacy-v1",
        "scenarios": [
            {
                "scenario_id": "legacy-scenario",
                "scenario_label": "legacy scenario",
                "outcome_comparisons": [
                    {
                        "metric_name": "metric",
                        "y_pred": 1.0,
                        "y_true": 1.0,
                        "absolute_error": 0.0,
                    }
                ],
            }
        ],
    }

    report = BacktestReport.model_validate(legacy_payload)

    assert report.schema_version == "1.0"
    assert report.scenarios[0].outcome_comparisons[0].within_ci is None

    legacy_payload["scenarios"][0]["outcome_comparisons"] = [
        {
            "metric_name": "metric",
            "y_pred": 1.0,
            "y_true": 1.0,
            "absolute_error": 0.0,
            "within_ci": False,
        },
        {
            "metric_name": "metric",
            "y_pred": 2.0,
            "y_true": 2.0,
            "absolute_error": 0.0,
            "within_ci": True,
        },
    ]

    explicit_booleans = BacktestReport.model_validate(legacy_payload)

    assert [
        comparison.within_ci for comparison in explicit_booleans.scenarios[0].outcome_comparisons
    ] == [False, True]


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
    partitioned_report = BacktestOrchestrator(cas_root=str(tmp_path / "partitioned")).run(
        [
            plan("first", [0.0], [0.0]),
            plan("second", [10.0, 10.0], [0.0, 0.0]),
        ]
    )

    expected_micro_rmse = math.sqrt(200 / 3)
    assert whole_report.overall_rmse == pytest.approx(expected_micro_rmse)
    assert partitioned_report.overall_rmse == pytest.approx(expected_micro_rmse)
    assert partitioned_report.overall_macro_rmse == pytest.approx(5.0)
    assert partitioned_report.aggregation_policy == "micro_rmse_with_explicit_equal_scenario_macro"


@pytest.mark.parametrize("residual", [1e154, 1e308])
def test_range_limited_micro_metrics_survive_partition_and_fresh_cas(
    residual: float, tmp_path
) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.scientist.governance.backtest_matrix import verify_backtest_trust_projection

    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0]}', encoding="utf-8")

    def plan(plan_id: str, count: int) -> HistoricalValidationPlan:
        return HistoricalValidationPlan(
            plan_id=plan_id,
            historical_data_path=str(history_path),
            ground_truth_outcomes={"metric": [0.0] * count},
            target_metrics=["metric"],
            prediction_source=PredictionSource.PROVIDED,
            predicted_outcomes={"metric": [residual] * count},
        )

    for key, plans in (
        ("whole", [plan("whole", 2)]),
        ("partitioned", [plan("first", 1), plan("second", 1)]),
    ):
        root = tmp_path / key
        _, ref = BacktestOrchestrator(cas=FileSystemCAS(root)).run_with_ref(plans)
        result = load_backtest_report(
            _ensure_ir_artifact_store(FileSystemCAS.open_existing_read_only(root)), ref
        )
        assert result.n_metrics_evaluated == 2
        assert result.overall_rmse == pytest.approx(residual)
        assert result.overall_mae == pytest.approx(residual)
        assert result.overall_macro_rmse == pytest.approx(residual)
        assert "backtest_numerical_range" in result.degraded_reasons
        assert result.metric_diagnostics_are_source_bound()
        assert not result.trust_eligible and result.trust_grade is None
        projection = verify_backtest_trust_projection(result)
        assert not projection.eligible and projection.score is None and projection.grade is None
        expected_squares = residual == 1e154 and key == "partitioned"
        assert all(
            (scenario.squared_error_sum is not None) is expected_squares
            for scenario in result.scenarios
        )


def test_invalid_prediction_is_counted_and_kept_out_of_valid_denominator() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="invalid-prediction",
        scenario_label="one invalid prediction",
        y_pred={"metric": [math.nan, 2.0]},
        y_true={"metric": [1.0, 2.0]},
    )

    assert scenario.requested_count == 2
    assert scenario.compared_count == 1
    assert scenario.invalid_count == 1
    assert scenario.missing_count == 0
    assert scenario.invalid_cells == [("metric", 0)]
    assert scenario.rmse == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("predicted", "observed", "rmse", "mae", "squared_sum", "unavailable_sums"),
    [
        (
            [1.0, 1e308],
            [1.0, 0.0],
            1e308 / math.sqrt(2),
            5e307,
            None,
            {"squared_error_sum": "overflow"},
        ),
        ([1e154, 1e154], [0.0, 0.0], 1e154, 1e154, None, {"squared_error_sum": "overflow"}),
        ([1e150, 1e150], [0.0, 0.0], 1e150, 1e150, 2e300, {}),
        (
            [1e308, 1e308],
            [100.0, 100.0],
            1e308,
            1e308,
            None,
            {
                "squared_error_sum": "overflow",
                "absolute_error_sum": "overflow",
                "percentage_error_sum": "overflow",
            },
        ),
        ([1e-308], [0.0], 1e-308, 1e-308, None, {"squared_error_sum": "underflow"}),
    ],
)
def test_unavailable_error_sum_keeps_finite_observation(
    predicted: list[float],
    observed: list[float],
    rmse: float,
    mae: float,
    squared_sum: float | None,
    unavailable_sums: dict[str, str],
) -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="finite-residual",
        scenario_label="finite residual",
        y_pred={"metric": predicted},
        y_true={"metric": observed},
    )

    assert scenario.requested_count == scenario.compared_count == len(observed)
    assert scenario.invalid_cells == []
    assert [row.absolute_error for row in scenario.outcome_comparisons] == [
        abs(p - y) for p, y in zip(predicted, observed, strict=True)
    ]
    assert scenario.rmse == pytest.approx(rmse, rel=1e-15, abs=0.0)
    assert scenario.mae == pytest.approx(mae, rel=1e-15, abs=0.0)
    if squared_sum is None:
        assert scenario.squared_error_sum is None
    else:
        assert scenario.squared_error_sum == pytest.approx(squared_sum)
    if unavailable_sums:
        assert scenario.numerical_range is not None
        assert scenario.numerical_range.unavailable_error_sums == unavailable_sums
        assert all(getattr(scenario, name) is None for name in unavailable_sums)
        assert TrustScorer().compute(scenarios=[scenario], biases=[]) == (None, None)
    else:
        assert scenario.numerical_range is None
        assert "numerical_range" not in scenario.model_dump(mode="json")
    if "percentage_error_sum" in unavailable_sums:
        assert scenario.percentage_error_count == 2 and scenario.mape == pytest.approx(1e308)
    assert BacktestScenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_unrepresentable_residual_is_an_addressed_invalid_cell() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="residual-overflow",
        scenario_label="residual overflow",
        y_pred={"metric": [1.0, sys.float_info.max, 6.0]},
        y_true={"metric": [1.0, -sys.float_info.max, 4.0, 1.0]},
    )

    assert (scenario.requested_count, scenario.compared_count) == (4, 2)
    assert scenario.missing_cells == [("metric", 3)]
    assert scenario.invalid_cells == [("metric", 1)]
    assert scenario.squared_error_sum == pytest.approx(4.0)
    assert scenario.rmse == pytest.approx(math.sqrt(2))
    assert scenario.numerical_range is not None
    assert scenario.numerical_range.unavailable_error_sums == {}
    (cell,) = scenario.numerical_range.residual_overflow_cells
    assert (cell.metric_name, cell.observation_index) == ("metric", 1)
    assert cell.y_pred == sys.float_info.max and cell.y_true == -sys.float_info.max


def test_complete_exact_prediction_remains_a_positive_grade_control() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="complete-exact",
        scenario_label="complete exact prediction",
        y_pred={"metric": [1.0, 100.0]},
        y_true={"metric": [1.0, 100.0]},
    )

    score, grade = TrustScorer().compute(scenarios=[scenario], biases=[])

    assert scenario.requested_count == 2
    assert scenario.compared_count == 2
    assert scenario.missing_count == 0
    assert scenario.invalid_count == 0
    assert score == pytest.approx(1.0)
    assert grade == "A"


def test_coverage_score_uses_persisted_nominal_confidence_level() -> None:
    scenario = BacktestScenario(
        scenario_id="nominal-coverage",
        scenario_label="nominal coverage",
        outcome_comparisons=[
            OutcomeComparison(
                metric_name="metric",
                y_pred=1.0,
                y_true=1.0,
                absolute_error=0.0,
            )
        ],
        coverage_probability=0.80,
        nominal_confidence_level=0.80,
        requested_count=1,
        compared_count=1,
    )

    score, grade = TrustScorer().compute(scenarios=[scenario], biases=[])

    assert score == pytest.approx(1.0)
    assert grade == "A"


def test_omitting_difficult_prediction_cannot_improve_completeness_or_grade() -> None:
    evaluator = PredictionEvaluator()
    complete = evaluator.evaluate(
        scenario_id="complete-comparison",
        scenario_label="complete comparison",
        y_pred={"metric": [1.0, 100.0]},
        y_true={"metric": [1.0, 100.0]},
    )
    partial = evaluator.evaluate(
        scenario_id="partial-comparison",
        scenario_label="difficult prediction omitted",
        y_pred={"metric": [1.0]},
        y_true={"metric": [1.0, 100.0]},
    )
    scorer = TrustScorer()
    _complete_score, complete_grade = scorer.compute(scenarios=[complete], biases=[])
    _partial_score, partial_grade = scorer.compute(scenarios=[partial], biases=[])

    assert complete.requested_count == partial.requested_count == 2
    assert complete.compared_count == 2
    assert partial.compared_count == 1
    assert complete_grade == "A"
    assert partial_grade != "A"


def test_non_default_nominal_confidence_survives_orchestrator_and_persisted_report(
    tmp_path,
) -> None:
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.ir.registry.refs import BacktestReportRef

    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0]}', encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="nominal-confidence",
        historical_data_path=str(history_path),
        ground_truth_outcomes={"metric": [1.0, 2.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.0, 2.0]},
        prediction_intervals={"metric": [(0.0, 2.0), (1.0, 3.0)]},
        confidence_level=0.80,
        metadata={"interval_type": "predictive"},
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    report = orchestrator.run([plan])
    assert report.cas_artifact_id is not None
    assert report.scenarios[0].nominal_confidence_level == pytest.approx(0.80)
    assert report.scenarios[0].interval_type == "predictive"
    assert report.overall_coverage_probability == pytest.approx(1.0)
    persisted_ref = BacktestReportRef.model_validate({"artifact_id": report.cas_artifact_id})
    persisted = load_backtest_report(_ensure_ir_artifact_store(orchestrator._store), persisted_ref)
    scenario = persisted.scenarios[0]

    assert persisted.overall_coverage_probability == pytest.approx(1.0)
    assert scenario.nominal_confidence_level == pytest.approx(0.80)
    assert scenario.interval_type == "predictive"


def test_owned_envelope_preserves_nominal_level_and_typed_semantics() -> None:
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

    envelope = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.0, 2.0),
        confidence_level=0.80,
        interval_semantics="credible_interval",
        source="calibration",
    )

    declared, confidence, interval_type, decoded = (
        BacktestOrchestrator._resolve_persisted_interval_metadata(envelope.model_dump(mode="json"))
    )

    assert declared
    assert confidence == 0.80
    assert interval_type == "credible_interval"
    assert decoded == envelope


@pytest.mark.parametrize(
    ("semantics", "level"),
    [
        ("bogus_semantics", 0.80),
        ("credible_interval", None),
        ("deterministic_bounds", 0.80),
    ],
    ids=["bogus-semantics", "credible-missing-level", "deterministic-statistical-level"],
)
def test_malformed_interval_metadata_refuses_at_its_canonical_validator(
    semantics: str, level: float | None
) -> None:
    with pytest.raises(ValueError):
        BacktestOrchestrator._resolve_persisted_interval_metadata(
            {
                "point_estimate": 1.0,
                "confidence_interval": (0.0, 2.0),
                "confidence_level": level,
                "source": "calibration",
                "interval_semantics": semantics,
            }
        )


def test_mixed_statistical_and_deterministic_intervals_cannot_be_combined() -> None:
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, combine_envelopes

    credible = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.0, 2.0),
        confidence_level=0.80,
        interval_semantics="credible_interval",
        source="calibration",
    )
    bounded = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.0, 2.0),
        confidence_level=None,
        interval_semantics="deterministic_bounds",
        source="calibration",
    )

    with pytest.raises(ValueError, match="different interval semantics"):
        combine_envelopes([credible, bounded])
