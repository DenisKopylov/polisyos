"""Behavioral consumers of the recomputed interval roster (synthetic only)."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from polisyos.calibration.interval_basis import _reconcile_interval_basis
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.backtest import load_backtest_report, persist_backtest_report
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.governance.backtest_matrix import _score_backtest_scenarios
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.backtesting.temporal import (
    TemporalEvaluationResult,
    TemporalThresholds,
    build_temporal_backtest_report,
    evaluate_temporal_trajectory,
)


@pytest.mark.parametrize(
    "admission", [None, {"status": "evaluated", "requested_count": 3, "evaluated_count": 3}]
)
def test_fake_or_missing_marker_cannot_admit_partial_actual_rows(admission):
    scenario = PredictionEvaluator().evaluate(
        scenario_id="partial",
        scenario_label="partial",
        y_pred={"m": [0.0, 0.0, 0.0]},
        y_true={"m": [0.0, 0.0, 0.0]},
        intervals={"m": [(-1.0, 1.0)]},
    )
    scenario.metadata = {} if admission is None else {"interval_admission": admission}
    basis = _reconcile_interval_basis(scenario)
    assert not basis.complete
    assert (basis.requested_count, basis.evaluated_count) == (3, 1)
    assert scenario.coverage_probability == 1.0
    assert scenario.rmse == 0.0
    assert _score_backtest_scenarios([scenario]) is None


def test_complete_legacy_and_point_only_have_no_new_marker_requirement():
    evaluator = PredictionEvaluator()
    complete = evaluator.evaluate(
        scenario_id="legacy",
        scenario_label="legacy",
        y_pred={"m": [0.0, 0.0, 0.0]},
        y_true={"m": [-1.0, 0.0, 1.0]},
        intervals={"m": [(-1.0, 1.0)] * 3},
    )
    complete.metadata = {}
    complete.coverage_probability = None  # legacy alias absent; measured hit rate remains
    assert _reconcile_interval_basis(complete).complete
    point = evaluator.evaluate(
        scenario_id="point", scenario_label="point", y_pred={"m": [0.0]}, y_true={"m": [0.0]}
    )
    assert not _reconcile_interval_basis(point).requested
    assert _score_backtest_scenarios([point]) == 1.0


def test_counts_and_hits_are_recomputed_instead_of_accepting_complete_label():
    scenario = PredictionEvaluator().evaluate(
        scenario_id="contradiction",
        scenario_label="contradiction",
        y_pred={"m": [0.0]},
        y_true={"m": [2.0]},
        intervals={"m": [(-1.0, 1.0)]},
    )
    scenario.interval_hit_count = 1
    scenario.interval_hit_rate = scenario.coverage_probability = 1.0
    scenario.outcome_comparisons[0].within_ci = True
    scenario.metadata = {"interval_admission": {"status": "evaluated"}}
    assert not _reconcile_interval_basis(scenario).complete


def test_retained_recomputed_issue_and_orphan_hit_rate_cannot_become_point_only():
    scenario = PredictionEvaluator().evaluate(
        scenario_id="retained",
        scenario_label="retained",
        y_pred={"m": [0.0]},
        y_true={"m": [0.0]},
        intervals={"m": [(-1.0, 1.0)]},
    )
    scenario.metadata["interval_admission"].update(
        status="evaluated", reconciled_issues=["interval_point_roster_incomplete"]
    )
    assert not _reconcile_interval_basis(scenario).complete
    point = PredictionEvaluator().evaluate(
        scenario_id="point", scenario_label="point", y_pred={"m": [0.0]}, y_true={"m": [0.0]}
    )
    point.interval_hit_rate = 1.0
    assert not _reconcile_interval_basis(point).complete


def test_empty_requested_axis_and_retained_extra_pair_are_not_point_only():
    scenario = PredictionEvaluator().evaluate(
        scenario_id="empty-axis",
        scenario_label="empty-axis",
        y_pred={"m": []},
        y_true={"m": []},
        intervals={"m": [(-1.0, 1.0)]},
    )
    assert scenario.metadata["interval_admission"]["status"] == "limited"
    assert not _reconcile_interval_basis(scenario).complete
    assert _score_backtest_scenarios([scenario]) is None


def test_real_orchestrator_scenario_cannot_escape_temporal_persisted_projection(tmp_path):
    cas_store = FileSystemCAS(tmp_path / "cas")
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"m": [0.0, 0.0, 0.0]}))
    report = BacktestOrchestrator(cas=cas_store).run(
        [
            HistoricalValidationPlan(
                plan_id="partial",
                historical_data_path=str(history),
                prediction_source=PredictionSource.PROVIDED,
                predicted_outcomes={"m": [0.0, 0.0, 0.0]},
                ground_truth_outcomes={"m": [0.0, 0.0, 0.0]},
                prediction_intervals={"m": [(-1.0, 1.0)]},
            )
        ]
    )
    fresh = load_backtest_report(cas_store, BacktestReportRef(artifact_id=report.cas_artifact_id))
    # This typed projection fixture is not a temporal trajectory producer/authority.
    carrier = TemporalEvaluationResult(
        scenario=fresh.scenarios[0],
        pointwise_metrics={},
        functional_metrics={},
        uncertainty_metrics={"band_coverage": 1.0},
        diagnostics_checks={"complete": True},
        gating_checks={},
        thresholds={},
        acceptance_checks={},
        expected_outcome="pass",
        actual_outcome="pass",
        matches_expected_outcome=True,
        passes=True,
    )
    result = build_temporal_backtest_report(report_id="projection", evaluations=[carrier])
    ref = persist_backtest_report(cas_store, result)
    reopened = load_backtest_report(cas_store, ref)
    assert reopened.degraded and not reopened.trust_eligible
    assert reopened.metadata["temporal_summary"]["passes_all"] is False
    assert reopened.scenarios[0].interval_requested_count == 3
    assert reopened.scenarios[0].coverage_probability == 1.0


def test_actual_temporal_solver_evaluator_preserves_reserved_basis_against_caller_metadata():
    # Maintained helper calls compile_temporal_estimand and solve_temporal_effect_path.
    trajectory = runpy.run_path(str(Path(__file__).with_name("test_temporal.py")))["_trajectory"](
        [0.0, 0.2, 0.4, 0.6]
    )
    payload = trajectory.model_dump()
    payload["confidence_band_lower"] = (1.0, 1.0, 1.0, 1.0)
    payload["confidence_band_upper"] = (-1.0, -1.0, -1.0, -1.0)
    malformed = type(trajectory).model_validate(payload)  # genuine supported DTO validation
    result = evaluate_temporal_trajectory(
        scenario_id="invalid-band",
        scenario_label="invalid-band",
        trajectory=malformed,
        expected_effect_path=[0.0, 0.2, 0.4, 0.6],
        thresholds=TemporalThresholds(min_band_coverage=0.0),
        extra_acceptance_checks={"interval_basis_complete": True},
        metadata={"interval_admission": {"status": "evaluated", "evaluated_count": 4}},
    )
    assert result.scenario.metadata["interval_admission"]["status"] == "limited"
    assert result.acceptance_checks["interval_basis_complete"] is False
    assert result.passes is False
