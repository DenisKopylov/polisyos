from __future__ import annotations

import json
from typing import Any

import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import SchemaInfo as CoreSchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.analytics.backtest import BacktestScenario
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
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


def test_fresh_backtest_report_readback_preserves_replica_cohort_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.ir.registry.refs import BacktestReportRef

    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps({"metric": [1.0, 1.1, 1.2]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="fresh-replica-report",
        historical_data_path=str(history_path),
        intervention_step=1,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [1.2]},
        prediction_source=PredictionSource.SCIENTIST,
    )
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    cohort_ref = _put_backtest_artifact(
        orchestrator,
        {"requested_count": 3, "completed_count": 2, "failed_count": 1},
        "scientist.backtest.replica_cohort",
    )

    def _prediction(_plan: HistoricalValidationPlan, _masked_data: dict[str, Any]):
        return {
            "predictions": {"metric": [1.1]},
            "prediction_mode_effective": PredictionSource.NAIVE.value,
            "degraded": True,
            "degraded_reasons": ["scientist_replica_cohort_incomplete"],
            "replica_cohort_ref": cohort_ref,
        }

    monkeypatch.setattr(orchestrator, "_predict", _prediction)
    report = orchestrator.run([plan])
    assert report.cas_artifact_id is not None
    assert report.scenarios[0].metadata["replica_cohort_ref"] == cohort_ref

    fresh_reader = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    loaded = load_backtest_report(
        fresh_reader,
        BacktestReportRef(artifact_id=report.cas_artifact_id),
    )

    assert loaded.scenarios[0].metadata["replica_cohort_ref"] == cohort_ref
    assert loaded.scenarios[0].metadata["degraded"] is True
    assert loaded.degraded is True
    assert "fresh-replica-report: scientist_replica_cohort_incomplete" in loaded.degraded_reasons
    manifest = store.get_manifest(report.cas_artifact_id)
    assert any(
        item.role == "replica_cohort:fresh-replica-report"
        and str(item.artifact_id) == cohort_ref["artifact_id"]
        for item in manifest.inputs
    )


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


def test_manifest_input_resolution_preserves_selected_profile_on_fresh_cas(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = b'{"stable":"payload"}'
    default_kind = "test.backtest.default_input"
    selected_kind = "test.backtest.selected_input"
    default_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=default_kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=default_kind, version="1.0"),
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=selected_kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=selected_kind, version="2.0"),
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    selectors = []
    get_manifest_by_profile = store.get_manifest_by_profile

    def record_manifest_by_profile(artifact_id, profile_sha256):
        selectors.append((artifact_id, profile_sha256))
        return get_manifest_by_profile(artifact_id, profile_sha256)

    monkeypatch.setattr(store, "get_manifest_by_profile", record_manifest_by_profile)
    input_ref = {
        "artifact_id": str(selected_ref.artifact_id),
        "role": "selected_source",
        "manifest_profile_sha256": selected_ref.manifest_profile_sha256,
    }
    normalized = orchestrator_module._resolve_manifest_inputs(store, [input_ref])

    assert normalized is not None
    assert normalized[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert selectors == [(selected_ref.artifact_id, selected_ref.manifest_profile_sha256)]
    selected_manifest = store.get_manifest(selected_ref)
    assert selected_manifest.kind == selected_kind
    assert selected_manifest.artifact_schema.version == "2.0"
    assert store.get_bytes(selected_ref) == payload


def test_manifest_input_resolution_fails_closed_for_unknown_selected_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b'{"stable":"payload"}',
        ArtifactWriteOptions(
            kind="test.backtest.unknown_selected_input",
            media_type="application/json",
            schema=CoreSchemaInfo(name="test.backtest.unknown_selected_input", version="1.0"),
            canon=CoreCanonInfo(),
        ),
    )

    with pytest.raises(ValueError, match="configured CAS"):
        orchestrator_module._resolve_manifest_inputs(
            store,
            [
                {
                    "artifact_id": str(ref.artifact_id),
                    "role": "selected_source",
                    "manifest_profile_sha256": "sha256:" + "f" * 64,
                }
            ],
        )


def test_replica_foundry_port_reads_selected_binding_profile_without_mutating_request(
    tmp_path,
    monkeypatch,
) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        ExecuteRequest,
        ExecuteResult,
        FoundryExecConfig,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        StateSnapshotRef,
    )

    store = FileSystemCAS(tmp_path / "cas")
    snapshot_ref = DataSnapshotRef(
        artifact_id="sha256:" + "a" * 64,
        kind="fabric.data_snapshot",
        media_type="application/json",
    )
    bindings = FoundryInputBindings(
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=ArtifactRef(
            artifact_id="sha256:" + "b" * 64,
            kind="core.registry_bundle",
            media_type="application/json",
        ),
        bound_state_snapshot_ref=StateSnapshotRef(artifact_id="sha256:" + "c" * 64),
    )
    payload = json.dumps(
        bindings.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    default_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.backtest.default_bindings",
            media_type="application/json",
            schema=CoreSchemaInfo(name="test.backtest.default_bindings", version="1.0"),
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=CoreSchemaInfo(name="foundry.input_bindings", version="1.0"),
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    typed_binding_ref = FoundryInputBindingsRef.model_validate(selected_ref.model_dump(mode="json"))
    request = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "d" * 64),
        input_bindings_ref=typed_binding_ref,
        exec_config=FoundryExecConfig(seed=0),
    )
    reads = []
    original_get_bytes = store.get_bytes

    def record_read(artifact_ref):
        reads.append(artifact_ref)
        return original_get_bytes(artifact_ref)

    monkeypatch.setattr(store, "get_bytes", record_read)
    physical_requests = []

    class _Delegate:
        def compile(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("replica-bound execute must not compile")

        def execute(self, _store: Any, physical_request: ExecuteRequest) -> ExecuteResult:
            physical_requests.append(physical_request)
            return ExecuteResult(ok=True)

    port = orchestrator_module._BacktestReplicaFoundryPort(
        delegate=_Delegate(),
        expected_snapshot_ref=snapshot_ref,
        seed=23,
    )
    result = port.execute(store, request)

    assert result.ok is True
    assert len(reads) == 1
    assert reads[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert len(physical_requests) == 1
    assert physical_requests[0] is not request
    assert physical_requests[0].exec_config.seed == 23
    assert request.exec_config.seed == 0
    assert (
        request.input_bindings_ref.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    )


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
    [("",), (" ",), (" leading",), ("trailing ",), ("line\nbreak",), ("nul\x00byte",)],
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
    assert "trust_screening:predictive_only_bridge_pending" in screened_report.degraded_reasons
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
            producer=({"component": "test.bkt01", "version": "1.0"} if include_producer else None),
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
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        ExecuteRequest,
        ExecuteResult,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        MetricsRef,
        SimulationResult,
        SimulationResultRef,
        StateSnapshotRef,
        UncertaintyEnvelopeRef,
    )

    metrics_ref = _put_backtest_artifact(
        orchestrator,
        metrics_payload,
        "scientist.backtest.metrics",
        include_producer=include_producer,
    )
    artifacts: dict[str, Any] = {"metrics_ref": metrics_ref}
    envelope_ref: dict[str, str] | None = None
    if envelope_payload is not None:
        envelope_ref = _put_backtest_artifact(
            orchestrator,
            envelope_payload,
            "ir.uncertainty_envelope",
            include_producer=include_producer,
        )

    captured: dict[str, Any] = {"states": []}

    class _Foundry:
        def compile(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("unit backtest fixture does not compile Foundry")

        def execute(self, _store: Any, request: ExecuteRequest) -> ExecuteResult:
            simulation = SimulationResult(
                exec_plan_ref=request.exec_plan_ref,
                metrics_ref=MetricsRef.model_validate(metrics_ref),
                uncertainty_envelopes=(
                    {"metric": UncertaintyEnvelopeRef.model_validate(envelope_ref)}
                    if envelope_ref is not None
                    else None
                ),
                notes=["seed_source:exec_config.seed"],
            )
            simulation_ref = _put_backtest_artifact(
                orchestrator,
                simulation.model_dump(mode="json"),
                "foundry.simulation_result",
            )
            return ExecuteResult(
                ok=True,
                simulation_result_ref=SimulationResultRef.model_validate(simulation_ref),
                notes=["seed_source:exec_config.seed"],
            )

    def _run_experiment(
        state: dict[str, Any], *, store: Any = None, foundry: Any = None
    ) -> dict[str, Any]:
        captured["states"].append(state)
        data_snapshot_ref = DataSnapshotRef.model_validate(state["inputs"]["data_snapshot_ref"])
        bindings = FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="core.registry_bundle",
                media_type="application/json",
            ),
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(artifact_id="sha256:" + "b" * 64),
        )
        bindings_ref = _put_backtest_artifact(
            orchestrator,
            bindings.model_dump(mode="json"),
            "foundry.input_bindings",
        )
        request = ExecuteRequest(
            exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "c" * 64),
            input_bindings_ref=FoundryInputBindingsRef.model_validate(bindings_ref),
        )
        result = foundry.execute(store, request)
        workflow_report_ref = _put_backtest_artifact(
            orchestrator,
            {"run_id": state["run_id"], "status": "ok", "nodes": []},
            "scientist.workflow_report",
        )
        return {
            "reports_index": {"workflow_report": workflow_report_ref},
            "artifacts_index": {
                **artifacts,
                "simulation_result_ref": result.simulation_result_ref.model_dump(mode="json"),
            },
        }

    monkeypatch.setattr(orchestrator_module, "DefaultFoundryPort", _Foundry)
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

    snapshot_ref = captured["states"][0]["inputs"]["data_snapshot_ref"]
    snapshot = get_json_artifact(
        _ensure_ir_artifact_store(orchestrator._store), snapshot_ref["artifact_id"]
    )
    view_ref = snapshot["data_ref"]["artifact_id"]
    view = get_json_artifact(_ensure_ir_artifact_store(orchestrator._store), view_ref)
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

    assert len(captured["states"]) == 7
    assert [state["params"]["random_seed"] for state in captured["states"]] == list(range(12, 19))
    assert [state["params"]["n_simulation_runs"] for state in captured["states"]] == [1] * 7
    assert len({state["run_id"] for state in captured["states"]}) == 7


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


def test_explicit_constant_profile_refuses_unadmitted_simulation_interval(
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
    assert result["intervals"] == {}
    assert result["degraded"] is True
    assert any(
        reason.startswith("simulation_uncertainty_admission_limited:metric:")
        for reason in result["degraded_reasons"]
    )

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


def test_scientist_backtest_accepts_preperiod_only_cutoff_and_masks_future_sentinel(
    tmp_path,
) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(
        tmp_path,
        intervention_step=None,
        intervention_date="",
        pre_intervention_periods=2,
    )
    raw_data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
    }

    masked = orchestrator._masker.mask(raw_data, plan)

    assert masked["metric"] == [1.0, 2.0]
    assert masked["time_index"] == ["t0", "t1"]
    assert masked["_backtest_metadata"]["intervention_step"] == 2
    assert raw_data["metric"] == [1.0, 2.0, 900.0, 901.0]


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


def test_backtest_refuses_actual_simulation_result_without_draw_admission(tmp_path) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    plan = _scientist_plan(tmp_path)
    envelope = UncertaintyEnvelope(
        point_estimate=7.0,
        confidence_interval=(6.0, 8.0),
        confidence_level=0.95,
        distribution_family="normal",
        source="ensemble",
        propagation_method="delta_method",
        interval_semantics="confidence_interval",
        gate_eligible=True,
    )
    envelope_ref = orchestrator._store.put_json(
        envelope.model_dump(mode="python", round_trip=True),
        StorePutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema={"name": "ir.uncertainty_envelope", "version": "1.1"},
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_ref = orchestrator._store.put_json(
        {
            "schema_version": "1.3",
            "uncertainty_envelopes": {
                "metric": normalize_artifact_ref(envelope_ref),
            },
        },
        StorePutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema={"name": "polisyos.core.SimulationResult", "version": "1.3"},
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    intervals, metadata, errors = orchestrator._extract_intervals_from_simulation_result(
        {"simulation_result_ref": normalize_artifact_ref(sim_ref)},
        plan,
    )

    assert intervals == {}
    assert metadata == {}
    assert any(
        error.startswith("simulation_uncertainty_admission_limited:metric:")
        and "propagation_report_ref_missing" in error
        for error in errors
    )


def test_simulation_result_interval_reader_preserves_selected_manifest_profile(
    tmp_path,
    monkeypatch,
) -> None:
    from polisyos.core.artifacts.manifest import InputRef as CoreInputRef
    from polisyos.core.contracts.foundry import SimulationResultRef

    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    plan = _scientist_plan(tmp_path)
    envelope = UncertaintyEnvelope(
        point_estimate=7.0,
        confidence_interval=(6.0, 8.0),
        confidence_level=0.95,
        distribution_family="normal",
        source="ensemble",
        propagation_method="delta_method",
        interval_semantics="confidence_interval",
    )
    envelope_ref = _put_backtest_artifact(
        orchestrator,
        envelope.model_dump(mode="json"),
        "ir.uncertainty_envelope",
    )
    report_ref = _put_backtest_artifact(
        orchestrator,
        {"schema_version": "1.1"},
        "foundry.propagation_report",
    )
    simulation_payload = {
        "schema_version": "1.3",
        "uncertainty_envelopes": {"metric": envelope_ref},
        "propagation_report_ref": report_ref,
    }
    simulation_bytes = json.dumps(
        simulation_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    def _lineage_input(ref: dict[str, str], role: str) -> CoreInputRef:
        return CoreInputRef(
            artifact_id=ref["artifact_id"],
            role=role,
            manifest_profile_sha256=ref.get("manifest_profile_sha256"),
        )

    default_ref = store.put_bytes(
        simulation_bytes,
        ArtifactWriteOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=CoreSchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            canon=CoreCanonInfo(forbid_floats=False),
        ),
    )
    selected_ref = store.put_bytes(
        simulation_bytes,
        ArtifactWriteOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=CoreSchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            inputs=[
                _lineage_input(envelope_ref, "metric_envelope.metric"),
                _lineage_input(report_ref, "propagation_report"),
                CoreInputRef(
                    artifact_id="sha256:" + "b" * 64,
                    role="base_simulation_result",
                ),
                CoreInputRef(
                    artifact_id="sha256:" + "c" * 64,
                    role="propagation_config",
                ),
            ],
            canon=CoreCanonInfo(forbid_floats=False),
        ),
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    selector = SimulationResultRef.model_validate(selected_ref.model_dump(mode="json"))
    observed_reads: list[object] = []
    original_get_bytes = store.get_bytes

    def _record_read(ref: object) -> bytes:
        if getattr(ref, "artifact_id", None) == selector.artifact_id:
            observed_reads.append(ref)
        return original_get_bytes(ref)

    monkeypatch.setattr(store, "get_bytes", _record_read)
    observed_admission_refs: list[object] = []
    original_admission = orchestrator_module.load_simulation_result_uncertainty_admission

    def _record_admission(store_arg: Any, ref: object, metric_id: str):
        observed_admission_refs.append(ref)
        return original_admission(store_arg, ref, metric_id)

    monkeypatch.setattr(
        orchestrator_module,
        "load_simulation_result_uncertainty_admission",
        _record_admission,
    )

    intervals, _metadata, errors = orchestrator._extract_intervals_from_simulation_result(
        {"simulation_result_ref": normalize_artifact_ref(selector)},
        plan,
    )

    selected_reads = [
        ref
        for ref in observed_reads
        if getattr(ref, "manifest_profile_sha256", None) == selector.manifest_profile_sha256
    ]
    assert selected_reads
    assert observed_admission_refs == [selector]
    assert intervals == {}
    assert any("simulation_uncertainty_admission_limited:metric:" in error for error in errors)
    selected_admission = original_admission(
        _ensure_ir_artifact_store(orchestrator._store),
        selector,
        "metric",
    )
    default_admission = original_admission(
        _ensure_ir_artifact_store(orchestrator._store),
        default_ref,
        "metric",
    )
    assert not any(
        item.startswith("simulation_result_lineage_mismatch:")
        for item in selected_admission.limitation_codes
    )
    assert any(
        item.startswith("simulation_result_lineage_mismatch:")
        for item in default_admission.limitation_codes
    )


def test_scientist_backtest_runs_and_reads_back_each_requested_replica(
    monkeypatch, tmp_path
) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        ExecuteRequest,
        ExecuteResult,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        MetricsRef,
        SimulationResult,
        SimulationResultRef,
        StateSnapshotRef,
    )

    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    plan = _scientist_plan(tmp_path, n_simulation_runs=3, random_seed=12)
    masked_data = {"metric": [1.0, 2.0], "time_index": ["t0", "t1"]}
    run_states: list[dict[str, Any]] = []
    caller_requests: list[ExecuteRequest] = []
    executed_requests: list[ExecuteRequest] = []

    class _Foundry:
        def compile(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("the caller fixture does not compile Foundry")

        def execute(self, _store: Any, request: ExecuteRequest) -> ExecuteResult:
            executed_requests.append(request)
            index = len(executed_requests)
            metrics_ref = _put_backtest_artifact(
                orchestrator,
                {"values": {"metric": [10.0 + index, 11.0 + index, 12.0 + index]}},
                "foundry.metrics",
            )
            typed_metrics_ref = MetricsRef.model_validate(metrics_ref)
            simulation_payload = SimulationResult(
                exec_plan_ref=request.exec_plan_ref,
                metrics_ref=typed_metrics_ref,
                notes=["seed_source:exec_config.seed"],
            )
            simulation_ref = _put_backtest_artifact(
                orchestrator,
                simulation_payload.model_dump(mode="json"),
                "foundry.simulation_result",
            )
            return ExecuteResult(
                ok=True,
                simulation_result_ref=SimulationResultRef.model_validate(simulation_ref),
                notes=["seed_source:exec_config.seed"],
            )

    def _run_experiment(
        state: dict[str, Any], *, store: Any = None, foundry: Any = None
    ) -> dict[str, Any]:
        assert store is orchestrator._scientist_execution_store()
        run_states.append(state)
        data_snapshot_ref = DataSnapshotRef.model_validate(state["inputs"]["data_snapshot_ref"])
        bindings = FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="core.registry_bundle",
                media_type="application/json",
            ),
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(artifact_id="sha256:" + "b" * 64),
        )
        bindings_ref = _put_backtest_artifact(
            orchestrator,
            bindings.model_dump(mode="json"),
            "foundry.input_bindings",
        )
        caller_request = ExecuteRequest(
            exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "c" * 64),
            input_bindings_ref=FoundryInputBindingsRef.model_validate(bindings_ref),
        )
        caller_requests.append(caller_request)
        execution_result = foundry.execute(store, caller_request)
        simulation_payload = get_json_artifact(
            orchestrator._store,
            execution_result.simulation_result_ref.artifact_id,
        )
        workflow_report_ref = _put_backtest_artifact(
            orchestrator,
            {"run_id": state["run_id"], "status": "ok", "nodes": []},
            "scientist.workflow_report",
        )
        return {
            "reports_index": {"workflow_report": workflow_report_ref},
            "artifacts_index": {
                "metrics_ref": simulation_payload["metrics_ref"],
                "simulation_result_ref": execution_result.simulation_result_ref.model_dump(
                    mode="json"
                ),
            },
        }

    monkeypatch.setattr(orchestrator_module, "DefaultFoundryPort", _Foundry)
    monkeypatch.setattr(orchestrator_module, "run_experiment", _run_experiment)

    result = orchestrator._predict_with_scientist(plan, masked_data)

    assert len(run_states) == 3
    assert len(executed_requests) == 3
    assert len({state["run_id"] for state in run_states}) == 3
    assert [state["params"]["random_seed"] for state in run_states] == [12, 13, 14]
    assert [state["params"]["n_simulation_runs"] for state in run_states] == [1, 1, 1]
    assert [request.exec_config.seed for request in executed_requests] == [12, 13, 14]
    assert [request.exec_config.seed for request in caller_requests] == [0, 0, 0]
    assert len({str(request.exec_plan_ref.artifact_id) for request in executed_requests}) == 1
    assert len({str(request.input_bindings_ref.artifact_id) for request in executed_requests}) == 1

    cohort_ref = result["replica_cohort_ref"]
    cohort = get_json_artifact(orchestrator._store, cohort_ref["artifact_id"])
    assert cohort["requested_count"] == 3
    assert cohort["started_count"] == 3
    assert cohort["completed_count"] == 3
    assert cohort["failed_count"] == 0
    assert [replica["seed"] for replica in cohort["replicas"]] == [12, 13, 14]
    assert len({replica["run_id"] for replica in cohort["replicas"]}) == 3
    for replica in cohort["replicas"]:
        simulation = get_json_artifact(
            orchestrator._store,
            replica["simulation_result_ref"]["artifact_id"],
        )
        metrics = get_json_artifact(orchestrator._store, replica["metrics_ref"]["artifact_id"])
        assert "seed_source:exec_config.seed" in simulation["notes"]
        assert isinstance(metrics["values"]["metric"], list)

    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert result["degraded"] is True
    assert "scientist_replica_projection_unsupported" in result["degraded_reasons"]


def test_scientist_backtest_rejects_workflow_report_from_another_run(
    monkeypatch,
    tmp_path,
) -> None:
    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    plan = _scientist_plan(tmp_path, n_simulation_runs=1, random_seed=23)
    foreign_report_ref = _put_backtest_artifact(
        orchestrator,
        {"run_id": "foreign-run", "status": "ok", "nodes": []},
        "scientist.workflow_report",
    )

    def _foreign_report(_state: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return {"reports_index": {"workflow_report": foreign_report_ref}}

    monkeypatch.setattr(orchestrator_module, "run_experiment", _foreign_report)
    result = orchestrator._predict_with_scientist(
        plan,
        {"metric": [1.0, 2.0], "time_index": ["t0", "t1"]},
    )

    cohort = get_json_artifact(
        orchestrator._store,
        result["replica_cohort_ref"]["artifact_id"],
    )
    replica = cohort["replicas"][0]
    assert cohort["requested_count"] == 1
    assert cohort["started_count"] == 1
    assert cohort["foundry_execute_count"] == 0
    assert cohort["completed_count"] == 0
    assert cohort["failed_count"] == 1
    assert replica["status"] == "failed"
    assert replica["workflow_report_ref"]["artifact_id"] == foreign_report_ref["artifact_id"]
    assert "scientist_workflow_report_run_id_mismatch" in replica["failure"]


def test_scientist_backtest_retains_failed_replica_in_requested_denominator(
    monkeypatch, tmp_path
) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        ExecuteRequest,
        ExecuteResult,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        MetricsRef,
        SimulationResult,
        SimulationResultRef,
        StateSnapshotRef,
    )

    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / "cas"))
    plan = _scientist_plan(tmp_path, n_simulation_runs=3, random_seed=40)
    run_states: list[dict[str, Any]] = []
    executed_requests: list[ExecuteRequest] = []

    class _Foundry:
        def compile(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("the caller fixture does not compile Foundry")

        def execute(self, _store: Any, request: ExecuteRequest) -> ExecuteResult:
            executed_requests.append(request)
            index = len(executed_requests)
            if index == 2:
                raise RuntimeError("replica-two-native-failure")
            metrics_ref = _put_backtest_artifact(
                orchestrator,
                {"values": {"metric": [10.0 + index, 11.0 + index, 12.0 + index]}},
                "foundry.metrics",
            )
            simulation_payload = SimulationResult(
                exec_plan_ref=request.exec_plan_ref,
                metrics_ref=MetricsRef.model_validate(metrics_ref),
                notes=["seed_source:exec_config.seed"],
            )
            simulation_ref = _put_backtest_artifact(
                orchestrator,
                simulation_payload.model_dump(mode="json"),
                "foundry.simulation_result",
            )
            return ExecuteResult(
                ok=True,
                simulation_result_ref=SimulationResultRef.model_validate(simulation_ref),
                notes=["seed_source:exec_config.seed"],
            )

    def _run_experiment(
        state: dict[str, Any], *, store: Any = None, foundry: Any = None
    ) -> dict[str, Any]:
        assert store is orchestrator._scientist_execution_store()
        run_states.append(state)
        snapshot_ref = DataSnapshotRef.model_validate(state["inputs"]["data_snapshot_ref"])
        bindings = FoundryInputBindings(
            data_snapshot_ref=snapshot_ref,
            registry_bundle_ref=ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="core.registry_bundle",
                media_type="application/json",
            ),
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(artifact_id="sha256:" + "b" * 64),
        )
        bindings_ref = _put_backtest_artifact(
            orchestrator,
            bindings.model_dump(mode="json"),
            "foundry.input_bindings",
        )
        request = ExecuteRequest(
            exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "c" * 64),
            input_bindings_ref=FoundryInputBindingsRef.model_validate(bindings_ref),
        )
        execution_result = foundry.execute(store, request)
        simulation_payload = get_json_artifact(
            orchestrator._store,
            execution_result.simulation_result_ref.artifact_id,
        )
        workflow_report_ref = _put_backtest_artifact(
            orchestrator,
            {"run_id": state["run_id"], "status": "ok", "nodes": []},
            "scientist.workflow_report",
        )
        return {
            "reports_index": {"workflow_report": workflow_report_ref},
            "artifacts_index": {
                "metrics_ref": simulation_payload["metrics_ref"],
                "simulation_result_ref": execution_result.simulation_result_ref.model_dump(
                    mode="json"
                ),
            },
        }

    monkeypatch.setattr(orchestrator_module, "DefaultFoundryPort", _Foundry)
    monkeypatch.setattr(orchestrator_module, "run_experiment", _run_experiment)

    result = orchestrator._predict_with_scientist(
        plan,
        {"metric": [1.0, 2.0], "time_index": ["t0", "t1"]},
    )

    assert len(run_states) == 3
    assert len(executed_requests) == 3
    cohort = get_json_artifact(
        orchestrator._store,
        result["replica_cohort_ref"]["artifact_id"],
    )
    assert cohort["requested_count"] == 3
    assert cohort["started_count"] == 3
    assert cohort["completed_count"] == 2
    assert cohort["failed_count"] == 1
    assert [replica["status"] for replica in cohort["replicas"]] == [
        "completed",
        "failed",
        "completed",
    ]
    assert "replica-two-native-failure" in cohort["replicas"][1]["failure"]
    assert len({replica["run_id"] for replica in cohort["replicas"]}) == 3
    assert [replica["seed"] for replica in cohort["replicas"]] == [40, 41, 42]
    assert result["prediction_mode_effective"] == PredictionSource.NAIVE.value
    assert result["degraded"] is True
    assert "scientist_replica_cohort_incomplete" in result["degraded_reasons"]
