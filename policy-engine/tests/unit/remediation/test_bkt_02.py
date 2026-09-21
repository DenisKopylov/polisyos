"""Behavioral witnesses for the BKT-02 backtesting contract.

These tests deliberately describe the missing B167/B168/B171 behavior at the
public backtesting seams.  They are test-first witnesses: this branch owns no
production remediation.
"""

from __future__ import annotations

import math

import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.core.artifacts import StorePutOptions
from polisyos.ir.analytics.backtest import BacktestScenario, OutcomeComparison
from polisyos.ir.model_layer.canon import CanonSpec
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
    persisted = load_backtest_report(orchestrator._store, persisted_ref)
    scenario = persisted.scenarios[0]

    assert persisted.overall_coverage_probability == pytest.approx(1.0)
    assert scenario.nominal_confidence_level == pytest.approx(0.80)
    assert scenario.interval_type == "predictive"


def test_persisted_envelope_metadata_overrides_plan_contract(monkeypatch, tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text("{}", encoding="utf-8")
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    def put_artifact(payload: dict, kind: str) -> dict[str, str]:
        ref = orchestrator._store.put_json(
            payload,
            StorePutOptions(
                kind=kind,
                media_type="application/json",
                schema={"name": kind, "version": "1.0"},
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return {"artifact_id": str(ref.artifact_id)}

    metrics_ref = put_artifact(
        {"values": {"metric": [20.0, 21.0, 22.0]}},
        "scientist.backtest.metrics",
    )
    envelope_ref = put_artifact(
        {
            "confidence_intervals": [[19.0, 21.0], [20.0, 22.0], [0.0, 1.0]],
            "confidence_level": 0.80,
            "interval_semantics": "credible_interval",
        },
        "scientist.backtest.envelope",
    )
    simulation_ref = put_artifact(
        {"uncertainty_envelopes": {"metric": envelope_ref}},
        "scientist.backtest.simulation",
    )
    monkeypatch.setattr(
        orchestrator_module,
        "run_experiment",
        lambda _state: {
            "artifacts_index": {
                "metrics_ref": metrics_ref,
                "simulation_result_ref": simulation_ref,
            }
        },
    )
    plan = HistoricalValidationPlan(
        plan_id="persisted-envelope-metadata",
        historical_data_path=str(history_path),
        intervention_step=1,
        ground_truth_outcomes={"metric": [20.0, 21.0, 22.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.SCIENTIST,
        scientist_state={"run_id": "BKT-02-envelope"},
        confidence_level=0.95,
        metadata={"interval_type": "plan_default"},
    )

    report = orchestrator.run([plan])

    scenario = report.scenarios[0]
    assert scenario.nominal_confidence_level == pytest.approx(0.80)
    assert scenario.interval_type == "credible_interval"
    assert scenario.metadata["interval_metadata_source"] == "persisted_envelope"
    assert scenario.coverage_probability == pytest.approx(2 / 3)
    assert report.trust_score == pytest.approx(0.9167)
    contract = report.metadata["interval_contracts"][0]
    assert contract["nominal_confidence_level"] == pytest.approx(0.80)
    assert contract["interval_type"] == "credible_interval"


@pytest.mark.parametrize(
    "envelope_payloads",
    [
        [
            {
                "confidence_intervals": [[0.0, 2.0]],
                "confidence_level": 0.80,
                "interval_semantics": "bogus_semantics",
            }
        ],
        [
            {
                "confidence_intervals": [[0.0, 2.0]],
                "interval_semantics": "credible_interval",
            }
        ],
        [
            {
                "confidence_intervals": [[0.0, 2.0]],
                "confidence_level": 0.80,
                "interval_semantics": "credible_interval",
            },
            {
                "confidence_intervals": [[0.0, 2.0]],
                "confidence_level": None,
                "interval_semantics": "deterministic_bounds",
            },
        ],
    ],
    ids=["bogus-semantics", "credible-missing-level", "statistical-nonstatistical-pair"],
)
def test_invalid_persisted_interval_metadata_is_degraded_and_unscored(
    monkeypatch,
    tmp_path,
    envelope_payloads,
) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text("{}", encoding="utf-8")
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    def put_artifact(payload: dict, kind: str) -> dict[str, str]:
        ref = orchestrator._store.put_json(
            payload,
            StorePutOptions(
                kind=kind,
                media_type="application/json",
                schema={"name": kind, "version": "1.0"},
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return {"artifact_id": str(ref.artifact_id)}

    metric_names = [f"metric_{index}" for index in range(len(envelope_payloads))]
    metrics_ref = put_artifact(
        {"values": {metric: [1.0] for metric in metric_names}},
        "scientist.backtest.metrics",
    )
    envelope_refs = {
        metric: put_artifact(payload, "scientist.backtest.envelope")
        for metric, payload in zip(metric_names, envelope_payloads)
    }
    simulation_ref = put_artifact(
        {"uncertainty_envelopes": envelope_refs},
        "scientist.backtest.simulation",
    )
    monkeypatch.setattr(
        orchestrator_module,
        "run_experiment",
        lambda _state: {
            "artifacts_index": {
                "metrics_ref": metrics_ref,
                "simulation_result_ref": simulation_ref,
            }
        },
    )
    plan = HistoricalValidationPlan(
        plan_id="invalid-persisted-envelope",
        historical_data_path=str(history_path),
        intervention_step=1,
        ground_truth_outcomes={metric: [1.0] for metric in metric_names},
        target_metrics=metric_names,
        prediction_source=PredictionSource.SCIENTIST,
        scientist_state={"run_id": "BKT-02-invalid-envelope"},
    )

    report = orchestrator.run([plan])

    scenario = report.scenarios[0]
    assert report.degraded is True
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert scenario.interval_evaluated_count == 0
    assert scenario.coverage_probability is None
    assert any("uncertainty_envelope_metadata" in reason for reason in report.degraded_reasons)
