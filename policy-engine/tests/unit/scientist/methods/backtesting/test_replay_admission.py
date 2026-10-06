"""Discriminators for actual replay denominators and unavailable trust authority."""

from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.ir.analytics.backtest import BacktestReport
from polisyos.ir.artifacts import get_json_artifact, normalize_artifact_ref, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.scientist.methods.backtesting.bootstrap import (
    BootstrapCI,
    BootstrapValidationError,
    bootstrap_metric,
)
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer


def _plan(tmp_path, *, count: int = 1, source=PredictionSource.SCIENTIST):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"metric": [1.0, 2.0, 900.0, 901.0]}), encoding="utf-8")
    return HistoricalValidationPlan(
        plan_id="replays",
        historical_data_path=str(path),
        intervention_step=2,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [10.0, 11.0]},
        prediction_source=source,
        predicted_outcomes={"metric": [10.0, 11.0]},
        scientist_state={"params": {}, "inputs": {}},
        n_simulation_runs=count,
        random_seed=12,
        metadata={"source_plan_id": "fake-parent", "replica_count": 999},
    )


def _backend(monkeypatch, orchestrator, *, fail_at: int | None = None):
    calls = []

    def execute(state, **kwargs):
        assert kwargs["store"] is orchestrator._scientist_store
        calls.append(state)
        snapshot = get_json_artifact(
            orchestrator._store,
            normalize_artifact_ref(state["inputs"]["data_snapshot_ref"])["artifact_id"],
        )
        consumed = get_json_artifact(
            orchestrator._store, normalize_artifact_ref(snapshot["data_ref"])["artifact_id"]
        )
        assert consumed["metric"] == [1.0, 2.0]
        assert state["params"]["n_simulation_runs"] == 1
        if len(calls) - 1 == fail_at:
            raise RuntimeError("controlled numerical execution failure")
        predictions = [10.0 + len(calls), 11.0 + len(calls)]
        ref = put_json_artifact(
            orchestrator._store,
            {"values": {"metric": predictions}},
            kind="scientist.backtest.metrics",
            schema_name="test.replay.Metrics",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return {"artifacts_index": {"metrics_ref": ref}}

    monkeypatch.setattr(orchestrator_module, "run_experiment", execute)
    return calls


def _reopen(orchestrator, report):
    return BacktestReport.model_validate(
        get_json_artifact(orchestrator._store, report.cas_artifact_id)
    )


@pytest.mark.parametrize("count", [1, 7])
def test_requested_replays_are_actual_calls_and_keep_rows_after_cas_readback(
    monkeypatch, tmp_path, count
):
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    calls = _backend(monkeypatch, orchestrator)
    report = orchestrator.run([_plan(tmp_path, count=count)])
    assert len(calls) == count
    seeds = [call["params"]["random_seed"] for call in calls]
    assert len(set(seeds)) == count
    if count == 7:
        expected = [
            int(stream.generate_state(1)[0]) for stream in np.random.SeedSequence(12).spawn(7)
        ]
        assert seeds == expected
    for observed in (report, _reopen(orchestrator, report)):
        assert observed.n_scenarios == count
        assert observed.metadata["comparison_denominator"]["requested"] == 2 * count
        denominator = observed.metadata["replay_denominators"][0]
        assert denominator["requested"] == denominator["attempted"] == count
        assert denominator["completed"] == count
        assert denominator["failed"] == 0
        assert len(denominator["outcomes"]) == count
        assert [scenario.metadata["replica_index"] for scenario in observed.scenarios] == list(
            range(count)
        )
        assert [
            scenario.metadata["requested_replay_seed"] for scenario in observed.scenarios
        ] == seeds
        assert all(
            scenario.metadata["source_plan_id"] == "replays" for scenario in observed.scenarios
        )
        assert (
            len({scenario.outcome_comparisons[0].y_pred for scenario in observed.scenarios})
            == count
        )
        for scenario in observed.scenarios:
            snapshot = get_json_artifact(
                orchestrator._store,
                normalize_artifact_ref(scenario.metadata["historical_snapshot_ref"])["artifact_id"],
            )
            consumed = get_json_artifact(
                orchestrator._store, normalize_artifact_ref(snapshot["data_ref"])["artifact_id"]
            )
            assert consumed["metric"] == [1.0, 2.0]
        assert observed.trust_grade is None


def test_failed_replay_remains_a_terminal_failure_and_is_not_an_independent_success(
    monkeypatch, tmp_path
):
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    calls = _backend(monkeypatch, orchestrator, fail_at=1)
    report = orchestrator.run([_plan(tmp_path, count=3)])
    assert len(calls) == 3
    for observed in (report, _reopen(orchestrator, report)):
        counts = observed.metadata["replay_denominators"][0]
        assert counts["requested"] == counts["attempted"] == 3
        assert counts["completed"] == 2
        assert counts["failed"] == 1
        assert observed.scenarios[1].metadata["prediction_source_effective"] == "naive"
        assert observed.scenarios[1].metadata["degraded"] is True
        assert any(
            "scientist_execution_failed:RuntimeError" in item for item in observed.degraded_reasons
        )
        assert observed.trust_eligible is False


def test_provided_forecast_is_not_recomputed_for_a_replica_parameter(monkeypatch, tmp_path):
    def forbidden(_state):
        raise AssertionError("provided forecast must not invoke Scientist")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    report = orchestrator.run([_plan(tmp_path, count=7, source=PredictionSource.PROVIDED)])
    assert report.n_scenarios == 1
    assert report.metadata["replay_denominators"][0]["declared_n_simulation_runs"] == 7
    assert report.metadata["replay_denominators"][0]["requested"] == 1
    assert report.metadata["replay_denominators"][0]["attempted"] == 0


def test_truth_observation_is_distinct_from_prediction_eligibility():
    scenario = PredictionEvaluator().evaluate(
        scenario_id="denominator",
        scenario_label="denominator",
        y_pred={"metric": [1.0]},
        y_true={"metric": [1.0, 100.0, float("nan")]},
        metadata={"comparison_denominator": {"requested": 0}},
    )
    assert scenario.metadata["comparison_denominator"] == {
        "requested": 3,
        "eligible": 1,
        "observed": 2,
        "unit": "metric_time_cell",
        "basis": "recomputed",
    }
    empty = PredictionEvaluator().evaluate(
        scenario_id="empty", scenario_label="empty", y_pred={}, y_true={"metric": [1.0]}
    )
    assert empty.metadata["evaluation_status"] == "not_evaluated"
    assert empty.rmse is None


@pytest.mark.parametrize("errors", [[-0.01, 0.0, 0.01], [0.5, 1.5, 2.5]])
def test_real_student_t_oracle_does_not_prove_equivalence(errors, tmp_path):
    scipy_stats = pytest.importorskip("scipy.stats")
    oracle = scipy_stats.ttest_1samp(errors, 0.0)
    expected_t = 0.0 if errors[0] < 0 else 2.598076211353316
    expected_p = 1.0 if errors[0] < 0 else 0.1216899343463201
    assert oracle.statistic == pytest.approx(expected_t, abs=1e-12)
    assert oracle.df == 2
    assert oracle.pvalue == pytest.approx(expected_p, abs=1e-12)
    assert BacktestOrchestrator._two_sided_ttest_pvalue(np.asarray(errors)) == pytest.approx(
        expected_p
    )
    plan = _plan(tmp_path, source=PredictionSource.PROVIDED).model_copy(
        update={
            "ground_truth_outcomes": {"metric": [0.0] * 3},
            "predicted_outcomes": {"metric": errors},
        }
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    report = orchestrator.run(
        [plan], metadata={"trust_admission": {"profile_ref": "present-but-fake"}}
    )
    for observed in (report, _reopen(orchestrator, report)):
        assert observed.metadata["trust_admission"]["predicate_basis"] == "not_established"
        assert observed.metadata["trust_admission"]["profile_ref"] is None
        assert observed.trust_eligible is False
        assert observed.trust_grade is None
        assert TrustScorer().compute(
            scenarios=observed.scenarios, biases=observed.detected_biases
        ) == (None, None)


@pytest.mark.parametrize("values", [np.asarray([[1.0, 2.0]]), np.asarray(1.0)])
def test_invalid_bootstrap_shape_rejects_before_callable_or_rng(monkeypatch, values):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid bootstrap input reached numerical callback")

    monkeypatch.setattr(np.random, "default_rng", forbidden)
    with pytest.raises(BootstrapValidationError, match="one-dimensional"):
        bootstrap_metric(values, statistic=forbidden)


@pytest.mark.parametrize("count", [1.5, True, np.bool_(True)])
def test_invalid_bootstrap_count_rejects_before_callable(count):
    def forbidden(_values):
        raise AssertionError("invalid bootstrap count reached statistic")

    with pytest.raises(BootstrapValidationError, match="integer"):
        bootstrap_metric([1.0, 2.0], statistic=forbidden, n_bootstrap=count)


def test_bootstrap_builtin_definition_has_independent_resample_oracle():
    values = np.asarray([0.0, 0.0, 9.0])
    rng = np.random.default_rng(12)
    rows = [rng.choice(values, size=3, replace=True) for _ in range(31)]
    for name, fn in (("mean", np.mean), ("median", np.median)):
        ci = bootstrap_metric(values, statistic=name, n_bootstrap=31, seed=12)
        quantiles = np.quantile([fn(row) for row in rows], [0.025, 0.975])
        reopened = BootstrapCI(**json.loads(json.dumps(asdict(ci))))
        assert reopened.point_estimate == float(fn(values))
        assert [reopened.lower, reopened.upper] == pytest.approx(quantiles)
        assert reopened.statistic == name
        assert reopened.statistic_identity_basis == "recomputed"


def test_empty_comparison_cannot_recover_metrics_from_present_but_fake_summary(tmp_path):
    from polisyos.ir.analytics.backtest import BacktestScenario

    forged = BacktestScenario(
        scenario_id="summary-only",
        scenario_label="summary-only",
        rmse=0.0,
        mae=0.0,
        mape=0.0,
        coverage_probability=1.0,
    )
    report = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))._aggregate(
        report_id="summary-only",
        scenarios=[forged],
        metadata={},
        prediction_mode_requested="provided",
        prediction_mode_effective="provided",
        degraded_reasons=[],
    )
    assert report.metadata["evaluation_status"] == "not_evaluated"
    assert report.n_metrics_evaluated == 0
    assert report.overall_rmse is None
    assert report.overall_macro_rmse is None
    assert report.overall_mae is None
    assert report.overall_mape is None
    assert report.overall_coverage_probability is None
    assert report.trust_grade is None


def test_requested_denominator_survives_missing_terminal_scenario(tmp_path):
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    plans = orchestrator._expand_replay_plans(_plan(tmp_path, count=3))
    report = orchestrator._aggregate(
        report_id="lost-outcome",
        scenarios=[],
        plans=plans,
        metadata={},
        prediction_mode_requested="scientist",
        prediction_mode_effective=None,
        degraded_reasons=[],
    )
    assert report.metadata["comparison_denominator"]["requested"] == 6
    assert report.metadata["comparison_denominator"]["eligible"] == 0
    denominator = report.metadata["replay_denominators"][0]
    assert denominator["requested"] == 3
    assert denominator["unobserved"] == 3
    assert denominator["attempted"] == 0
    assert report.metadata["evaluation_status"] == "not_evaluated"
    assert report.trust_eligible is False


def test_native_scientist_missing_trinity_is_not_counted_as_prediction_success(
    monkeypatch, tmp_path
):
    """Exercise the real facade/workflow, preserving its missing-input failure."""
    native = orchestrator_module.run_experiment
    calls = []
    errors = []
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))

    def observed_native(state, **kwargs):
        assert kwargs["store"] is orchestrator._scientist_store
        calls.append(state)
        try:
            return native(state, **kwargs)
        except Exception as exc:
            errors.append({"type": type(exc).__name__, "message": str(exc)})
            raise

    monkeypatch.setattr(orchestrator_module, "run_experiment", observed_native)
    plan = _plan(tmp_path, count=2).model_copy(
        update={
            "scientist_state": {
                "run_id": "e02-native-missing-trinity",
                "params": {"workflow_id": "scientist_default"},
                "inputs": {},
            }
        }
    )
    report = orchestrator.run([plan])
    assert len(calls) == 2
    assert len({state["run_id"] for state in calls}) == 2
    assert all(state["params"]["n_simulation_runs"] == 1 for state in calls)
    for state in calls:
        snapshot = get_json_artifact(
            orchestrator._store, state["inputs"]["data_snapshot_ref"]["artifact_id"]
        )
        consumed = get_json_artifact(orchestrator._store, snapshot["data_ref"]["artifact_id"])
        assert consumed["metric"] == [1.0, 2.0]
    for observed in (report, _reopen(orchestrator, report)):
        counts = observed.metadata["replay_denominators"][0]
        assert counts["requested"] == counts["attempted"] == counts["failed"] == 2
        assert counts["completed"] == 0
        assert len({row.metadata["backend_run_id"] for row in observed.scenarios}) == 2
        assert observed.trust_eligible is False
    # This proves native refusal, never successful forecast backend execution.
    assert errors
    assert any("trinity" in error["message"].lower() for error in errors)
    print(json.dumps({"actual_native_errors": errors, "submitted_states": calls}, sort_keys=True))
