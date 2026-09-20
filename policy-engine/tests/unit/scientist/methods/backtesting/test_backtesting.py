from __future__ import annotations

import json
from typing import Any

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.ir.analytics.backtest import BacktestScenario
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer


def test_backtesting_orchestrator_naive_mode(tmp_path) -> None:
    history = {
        "tax_revenue": [10.0, 11.0, 12.0, 12.5, 13.0],
    }
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    plan = HistoricalValidationPlan(
        plan_id="bt_1",
        plan_label="naive backtest",
        historical_data_path=str(history_path),
        intervention_step=3,
        target_metrics=["tax_revenue"],
        ground_truth_outcomes={"tax_revenue": [13.2, 13.4]},
        prediction_source=PredictionSource.NAIVE,
    )

    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    report = orchestrator.run([plan])
    assert report.n_scenarios == 1
    assert report.cas_artifact_id is not None
    assert report.scenarios[0].scenario_id == "bt_1"


def test_trust_scorer_coverage_gate_caps_grade() -> None:
    scorer = TrustScorer()
    scenarios = [
        BacktestScenario(
            scenario_id="s1",
            scenario_label="scenario",
            rmse=0.1,
            mae=0.1,
            mape=2.0,
            coverage_probability=0.4,
        )
    ]
    score, grade = scorer.compute(scenarios=scenarios, biases=[])
    assert score is not None
    assert grade in {"C", "D", "F"}


def test_backtesting_scientist_fallback_marks_report_degraded(tmp_path) -> None:
    history = {
        "policy_cost": [100.0, 101.0, 99.0, 98.0],
    }
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    plan = HistoricalValidationPlan(
        plan_id="bt_fallback",
        historical_data_path=str(history_path),
        intervention_step=2,
        target_metrics=["policy_cost"],
        ground_truth_outcomes={"policy_cost": [97.0, 96.0]},
        prediction_source=PredictionSource.SCIENTIST,
        scientist_state=None,
    )

    report = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run([plan])
    assert report.prediction_mode_requested == "scientist"
    assert report.prediction_mode_effective == "naive"
    assert report.degraded is True
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.degraded_reasons


def test_backtesting_orchestrator_accepts_injected_store_factory(monkeypatch, tmp_path) -> None:
    history = {"tax_revenue": [10.0, 11.0, 12.0, 12.5, 13.0]}
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="bt_injected_factory",
        plan_label="injected store factory",
        historical_data_path=str(history_path),
        intervention_step=3,
        target_metrics=["tax_revenue"],
        ground_truth_outcomes={"tax_revenue": [13.2, 13.4]},
        prediction_source=PredictionSource.NAIVE,
    )
    captured_roots = []

    def _unexpected_default(root):
        del root
        raise AssertionError("default backtest store factory should not run")

    def _store_factory(root):
        captured_roots.append(root)
        return orchestrator_module.build_ir_artifact_store(root)

    monkeypatch.setattr(
        orchestrator_module,
        "_default_backtest_store_factory",
        _unexpected_default,
    )

    report = BacktestOrchestrator(
        cas_root=str(tmp_path / ".polisyos"),
        store_factory=_store_factory,
    ).run([plan])

    assert captured_roots == [tmp_path / ".polisyos"]
    assert report.cas_artifact_id is not None


def _scientist_plan(tmp_path, **overrides: Any) -> HistoricalValidationPlan:
    history_path = tmp_path / "scientist-history.json"
    history_path.write_text("{}", encoding="utf-8")
    payload: dict[str, Any] = {
        "plan_id": "scientist_dispatch",
        "historical_data_path": str(history_path),
        "intervention_step": 2,
        "ground_truth_outcomes": {"metric": [10.0, 11.0, 12.0]},
        "target_metrics": ["metric"],
        "prediction_source": PredictionSource.SCIENTIST,
        "scientist_state": {"run_id": "BKT-01-test"},
    }
    payload.update(overrides)
    return HistoricalValidationPlan(**payload)


def _put_backtest_artifact(
    orchestrator: BacktestOrchestrator,
    payload: Any,
    kind: str,
) -> dict[str, str]:
    return put_json_artifact(
        orchestrator._store,
        payload,
        kind=kind,
        schema_name=kind,
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _scientist_result_with_artifacts(
    monkeypatch,
    orchestrator: BacktestOrchestrator,
    *,
    metrics_payload: dict[str, Any],
    envelope_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics_ref = _put_backtest_artifact(
        orchestrator,
        metrics_payload,
        "scientist.backtest.metrics",
    )
    artifacts: dict[str, Any] = {"metrics_ref": metrics_ref}
    if envelope_payload is not None:
        envelope_ref = _put_backtest_artifact(
            orchestrator,
            envelope_payload,
            "scientist.backtest.envelope",
        )
        simulation_ref = _put_backtest_artifact(
            orchestrator,
            {"uncertainty_envelopes": {"metric": envelope_ref}},
            "scientist.backtest.simulation",
        )
        artifacts["simulation_result_ref"] = simulation_ref

    captured: dict[str, Any] = {}

    def _run_experiment(state: dict[str, Any]) -> dict[str, Any]:
        captured["state"] = state
        return {"artifacts_index": artifacts}

    monkeypatch.setattr(orchestrator_module, "run_experiment", _run_experiment)
    return artifacts, captured


def test_scientist_dispatch_binds_masked_view_to_backend_input(monkeypatch, tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    raw_data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
    }
    masked_data = orchestrator._masker.mask(raw_data, plan)
    _artifacts, captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={},
    )

    orchestrator._predict_with_scientist(plan, masked_data)

    snapshot_ref = captured["state"]["inputs"]["data_snapshot_ref"]
    snapshot = get_json_artifact(orchestrator._store, snapshot_ref["artifact_id"])
    view_ref = snapshot["data_ref"]["artifact_id"]
    view = get_json_artifact(orchestrator._store, view_ref)
    assert view["metric"] == [1.0, 2.0]
    assert view["time_index"] == ["t0", "t1"]
    assert 900.0 not in view["metric"]
    assert 901.0 not in view["metric"]


def test_scientist_dispatch_passes_requested_replica_count(monkeypatch, tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path, n_simulation_runs=7, random_seed=12)
    _artifacts, captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={},
    )

    orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert captured["state"]["params"]["random_seed"] == 12
    assert captured["state"]["params"]["n_simulation_runs"] == 7


def test_scientist_scalar_without_constant_profile_is_not_a_trajectory(
    monkeypatch,
    tmp_path,
) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={"values": {"metric": 7.0}},
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert "scientist_predictions_missing" in result["degraded_reasons"]


def test_scientist_trajectory_length_mismatch_is_not_silently_truncated(
    monkeypatch,
    tmp_path,
) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={"values": {"metric": [20.0, 21.0, 22.0, 23.0]}},
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert "scientist_predictions_missing" in result["degraded_reasons"]


def test_singleton_interval_without_constant_profile_is_not_repeated(monkeypatch, tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={"values": {"metric": [20.0, 21.0, 22.0]}},
        envelope_payload={"confidence_interval": [19.0, 21.0]},
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.SCIENTIST.value
    assert result["predictions"]["metric"] == [20.0, 21.0, 22.0]
    assert result["intervals"] == {}


def test_explicit_constant_profile_preserves_constant_forecast_and_interval(
    monkeypatch,
    tmp_path,
) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={
            "values": {"metric": 7.0},
            "forecast_profile": "constant_forecast",
        },
        envelope_payload={
            "confidence_interval": [6.0, 8.0],
            "forecast_profile": "constant_forecast",
        },
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.SCIENTIST.value
    assert result["predictions"]["metric"] == [7.0, 7.0, 7.0]
    assert result["intervals"]["metric"] == [(6.0, 8.0)] * 3


def test_provided_predictions_do_not_dispatch_scientist(monkeypatch, tmp_path) -> None:
    history_path = tmp_path / "provided-history.json"
    history_path.write_text("{}", encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="provided",
        historical_data_path=str(history_path),
        intervention_step=2,
        ground_truth_outcomes={"metric": [10.0, 11.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [10.5, 11.5]},
        prediction_intervals={"metric": [(10.0, 11.0), (11.0, 12.0)]},
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    def _unexpected_run(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("PROVIDED predictions must not dispatch Scientist")

    monkeypatch.setattr(orchestrator_module, "run_experiment", _unexpected_run)

    result = orchestrator._predict(plan, {"metric": [1.0, 2.0]})

    assert result["predictions"] == {"metric": [10.5, 11.5]}
    assert result["intervals"] == {"metric": [(10.0, 11.0), (11.0, 12.0)]}
