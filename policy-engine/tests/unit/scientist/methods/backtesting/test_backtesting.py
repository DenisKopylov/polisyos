from __future__ import annotations

import json
from typing import Any

import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.ir.analytics.backtest import BacktestScenario
from polisyos.ir.artifacts import (
    InputRef,
    StorePutOptions,
    get_json_artifact,
    normalize_artifact_ref,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.scientist.methods.backtesting.orchestrator import (
    BacktestOrchestrator,
    TrustScreeningMode,
)
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
    assert report.report_id.startswith("BT_")


def test_orchestrator_preserves_preallocated_report_id_and_manifest_inputs(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps({"metric": [1.0, 1.1, 1.2]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="frc02-owner-direct",
        historical_data_path=str(history_path),
        intervention_step=1,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [1.2]},
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.2]},
        model_spec_ref="sha256:" + "a" * 64,
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    source_ref = _put_backtest_artifact(
        orchestrator,
        {"source": "frc02"},
        "test.frc02.owner_source",
    )
    inputs = [InputRef(artifact_id=source_ref["artifact_id"], role="calibration_source")]

    report = orchestrator.run(
        [plan],
        report_id="frc02.owner.direct/report-1",
        inputs=inputs,
    )

    assert report.report_id == "frc02.owner.direct/report-1"
    assert report.cas_artifact_id is not None
    manifest = orchestrator._store.get_manifest(report.cas_artifact_id)
    assert [(str(item.artifact_id), item.role) for item in manifest.inputs] == [
        (source_ref["artifact_id"], "calibration_source")
    ]


def test_orchestrator_does_not_infer_plan_refs_into_manifest_inputs(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps({"metric": [1.0, 1.1, 1.2]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="frc02-owner-no-inferred-inputs",
        historical_data_path=str(history_path),
        intervention_step=1,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [1.2]},
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.2]},
        model_spec_ref="sha256:" + "b" * 64,
        policy_spec_ref="sha256:" + "c" * 64,
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    report = orchestrator.run([plan], report_id="frc02.owner.no-inferred-inputs")

    assert report.cas_artifact_id is not None
    manifest = orchestrator._store.get_manifest(report.cas_artifact_id)
    assert manifest.inputs == []


def test_orchestrator_rejects_unresolved_manifest_input_before_persistence(tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    missing_input = InputRef(
        artifact_id="sha256:" + "d" * 64,
        role="calibration_source",
    )
    foreign_orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "foreign"))
    foreign_ref = _put_backtest_artifact(
        foreign_orchestrator,
        {"source": "foreign"},
        "test.frc02.foreign_source",
    )
    foreign_input = InputRef(
        artifact_id=foreign_ref["artifact_id"],
        role="calibration_source",
    )

    for input_ref in (missing_input, foreign_input):
        with pytest.raises(ValueError, match="configured CAS"):
            orchestrator.run(
                [],
                report_id="frc02.owner.unresolved-input",
                inputs=[input_ref],
            )

    assert orchestrator._store.iter_artifact_ids() == []


def test_orchestrator_honors_metadata_only_report_id(tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    report = orchestrator.run(
        [],
        metadata={"report_id": "frc02.owner.metadata-only"},
    )

    assert report.report_id == "frc02.owner.metadata-only"


def test_orchestrator_rejects_malformed_metadata_report_id(tmp_path) -> None:
    with pytest.raises(ValueError, match="metadata.report_id"):
        BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run(
            [],
            metadata={"report_id": " "},
        )


@pytest.mark.parametrize(
    "invalid_report_id",
    ("", " ", " leading", "trailing ", "line\nbreak", "nul\x00byte"),
)
def test_orchestrator_rejects_malformed_preallocated_report_id(
    invalid_report_id: str,
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="report_id"):
        BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run(
            [],
            report_id=invalid_report_id,
        )


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


def test_predictive_trust_screening_only_denies_trust(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps({"metric": [1.0, 2.0, 3.0, 4.0]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="predictive-screening",
        historical_data_path=str(history_path),
        intervention_step=2,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [3.0, 4.0]},
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [3.0, 4.0]},
    )
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))

    default_report = orchestrator.run([plan], report_id="predictive-screening-default")
    screened_report = orchestrator.run(
        [plan],
        report_id="predictive-screening-limited",
        trust_screening=TrustScreeningMode.PREDICTIVE_ONLY_BRIDGE_PENDING,
    )

    assert default_report.trust_eligible is True
    assert default_report.trust_score is not None
    assert screened_report.trust_eligible is False
    assert screened_report.trust_score is None
    assert (
        "trust_screening:predictive_only_bridge_pending"
        in screened_report.degraded_reasons
    )
    assert screened_report.metadata["trust_screening"] == "predictive_only_bridge_pending"


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
    *,
    include_producer: bool = True,
) -> dict[str, str]:
    ref = orchestrator._store.put_json(
        payload,
        StorePutOptions(
            kind=kind,
            media_type="application/json",
            schema={"name": kind, "version": "1.0"},
            producer=(
                {"component": "test.bkt01", "version": "1.0"}
                if include_producer
                else None
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return normalize_artifact_ref(ref)


def _scientist_result_with_artifacts(
    monkeypatch,
    orchestrator: BacktestOrchestrator,
    *,
    metrics_payload: dict[str, Any],
    envelope_payload: dict[str, Any] | None = None,
    include_producer: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics_ref = _put_backtest_artifact(
        orchestrator,
        metrics_payload,
        "scientist.backtest.metrics",
        include_producer=include_producer,
    )
    artifacts: dict[str, Any] = {"metrics_ref": metrics_ref}
    if envelope_payload is not None:
        envelope_ref = _put_backtest_artifact(
            orchestrator,
            envelope_payload,
            "scientist.backtest.envelope",
            include_producer=include_producer,
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
            "forecast_contract": {
                "profile": "constant_forecast",
                "producer": {"component": "test.bkt01", "version": "1.0"},
                "estimand": "outcome_trajectory",
                "horizon": 3,
                "time_index": ["t0", "t1", "t2"],
            },
        },
        envelope_payload={
            "confidence_interval": [6.0, 8.0],
            "forecast_profile": "constant_forecast",
            "forecast_contract": {
                "profile": "constant_forecast",
                "producer": {"component": "test.bkt01", "version": "1.0"},
                "estimand": "outcome_trajectory",
                "horizon": 3,
                "time_index": ["t0", "t1", "t2"],
            },
        },
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.SCIENTIST.value
    assert result["predictions"]["metric"] == [7.0, 7.0, 7.0]
    assert result["intervals"]["metric"] == [(6.0, 8.0)] * 3

    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={"values": {"metric": 7.0}},
        envelope_payload={"confidence_interval": [6.0, 8.0]},
    )
    without_profile = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})
    assert without_profile["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert "scientist_predictions_missing" in without_profile["degraded_reasons"]


def test_forged_constant_profile_without_producer_is_degraded(monkeypatch, tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    profile = {
        "profile": "constant_forecast",
        "producer": {"component": "test.bkt01", "version": "1.0"},
        "estimand": "outcome_trajectory",
        "horizon": 3,
        "time_index": ["t0", "t1", "t2"],
    }
    _artifacts, _captured = _scientist_result_with_artifacts(
        monkeypatch,
        orchestrator,
        metrics_payload={
            "values": {"metric": 7.0},
            "forecast_profile": "constant_forecast",
            "forecast_contract": profile,
        },
        envelope_payload={
            "confidence_interval": [6.0, 8.0],
            "forecast_profile": "constant_forecast",
            "forecast_contract": profile,
        },
        include_producer=False,
    )

    result = orchestrator._predict_with_scientist(plan, {"metric": [1.0, 2.0]})

    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert result["degraded"] is True
    assert "scientist_predictions_missing" in result["degraded_reasons"]


def test_scientist_without_temporal_boundary_is_degraded(monkeypatch, tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path, intervention_step=None, pre_intervention_periods=None)

    def _unexpected_run(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("unbounded Scientist replay must not dispatch")

    monkeypatch.setattr(orchestrator_module, "run_experiment", _unexpected_run)

    result = orchestrator._predict_with_scientist(
        plan,
        {"metric": [1.0, 2.0, 900.0, 901.0]},
    )

    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert result["degraded"] is True
    assert "scientist_historical_cutoff_missing" in result["degraded_reasons"]


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
