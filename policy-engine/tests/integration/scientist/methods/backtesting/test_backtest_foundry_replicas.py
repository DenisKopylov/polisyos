from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FoundryInputBindingRule,
    FoundryInputBindings,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.data_plane import build_input_bindings
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir import CanonSpec
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.artifacts import InputRef, put_json_artifact
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.methods.backtesting.masking import MaskingValidationError
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    MaskingStrategy,
    PredictionSource,
)


def _plan(
    tmp_path,
    *,
    replica_count: int = 3,
    intervention_step: int | None = 2,
    intervention_date: str = "",
    pre_intervention_periods: int | None = None,
):
    raw_data = {
        "metric": [1.0, 2.0, 900.0, 901.0],
        "time_index": ["t0", "t1", "t2", "t3"],
    }
    history_path = tmp_path / "masked-backtest-history.json"
    history_path.write_text(json.dumps(raw_data), encoding="utf-8")
    return raw_data, HistoricalValidationPlan(
        plan_id="masked_foundry_replicas",
        historical_data_path=str(history_path),
        intervention_step=intervention_step,
        intervention_date=intervention_date,
        pre_intervention_periods=pre_intervention_periods,
        target_metrics=["metric"],
        ground_truth_outcomes={"metric": [20.0, 21.0, 22.0]},
        prediction_source=PredictionSource.SCIENTIST,
        n_simulation_runs=replica_count,
        random_seed=31,
        scientist_state={
            "run_id": "backtest-original-run",
            "inputs": {
                "data_snapshot_ref": None,
            },
        },
    )


def _persist_trinity(
    store: FileSystemCAS,
    *,
    data_snapshot_ref: DataSnapshotRef,
    registry_bundle_ref: Any,
) -> Any:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="backtest_masked_view",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="backtest_masked_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="income_tax",
                    kind="income_tax",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": "0.1"},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="backtest_masked_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        ),
    )
    return persist_trinity_bundle_artifact(
        ensure_ir_artifact_store(store),
        bundle,
        inputs=[
            input_ref_from_artifact_ref(data_snapshot_ref, role="model_data_snapshot"),
            input_ref_from_artifact_ref(registry_bundle_ref, role="model_registry"),
        ],
    )


def _bind_real_default_route(
    *,
    plan: HistoricalValidationPlan,
    trinity_ref: Any,
    registry_bundle_ref: Any,
) -> None:
    assert plan.scientist_state is not None
    plan.scientist_state["inputs"] = {
        "trinity_bundle_ref": trinity_ref.model_dump(mode="json"),
        "registry_bundle_ref": registry_bundle_ref.model_dump(mode="json"),
    }
    plan.scientist_state["params"] = {
        "workflow_id": "scientist_default",
        "foundry_input_binding_rules": [
            {
                "binding_id": "historical_metric_to_income",
                "source_path": "metric",
                "target_slot_id": "agents.income",
                "required": True,
            }
        ],
    }


def test_backtest_replays_only_masked_bindings_with_distinct_real_foundry_replicas(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    raw_data, plan = _plan(tmp_path, intervention_step=None, intervention_date="2024-01-03")
    plan = HistoricalValidationPlan.model_validate(
        {
            **plan.model_dump(mode="python"),
            "ground_truth_outcomes": {"metric": [20.0, 21.0]},
            "post_intervention_periods": 2,
            "known_ahead_calendar": {
                "profile": "iso_weekday.daily.v1",
                "output_field": "weekday",
            },
        }
    )
    raw_data.update(
        {
            "time_index": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "derived_income": [451.0, 451.0],
            "weekday": [451.0, 451.0],
        }
    )
    assert plan.historical_data_path is not None
    history = Path(plan.historical_data_path)
    history.write_text(json.dumps(raw_data), encoding="utf-8")
    original_source = history.read_bytes()
    masked_data = orchestrator._masker.mask(raw_data, plan)
    masked_snapshot_ref = DataSnapshotRef.model_validate(
        orchestrator._persist_masked_view(plan, masked_data)
    )
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    trinity_ref = _persist_trinity(
        store,
        data_snapshot_ref=masked_snapshot_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )
    _bind_real_default_route(
        plan=plan,
        trinity_ref=trinity_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )
    assert plan.scientist_state is not None
    plan.scientist_state["params"]["foundry_input_binding_rules"].append(
        {
            "binding_id": "calendar_projection_control",
            "source_path": "weekday",
            "target_slot_id": "agents.reported_income",
        }
    )

    captured: list[tuple[ExecuteRequest, FoundryInputBindings, list[float], list[float]]] = []
    original_execute = DefaultFoundryPort.execute

    def _capture_and_execute(self, cas, request: ExecuteRequest):
        bindings = FoundryInputBindings.model_validate(
            load_core_json_artifact(cas, request.input_bindings_ref)
        )
        bound_state = load_state_snapshot(
            cas,
            snapshot_ref=bindings.bound_state_snapshot_ref,
        )
        captured.append(
            (
                request,
                bindings,
                np.asarray(bound_state.agents.income, dtype=float).tolist(),
                np.asarray(bound_state.agents.reported_income, dtype=float).tolist(),
            )
        )
        return original_execute(self, cas, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", _capture_and_execute)
    original_plan = plan.model_dump(mode="python")
    report = orchestrator.run([plan])
    assert history.read_bytes() == original_source
    assert plan.model_dump(mode="python") == original_plan
    assert report.cas_artifact_id is not None
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    fresh_report = load_backtest_report(
        fresh_reader,
        BacktestReportRef(artifact_id=report.cas_artifact_id),
    )
    assert fresh_report.report_id == report.report_id
    assert fresh_report.degraded is report.degraded
    assert fresh_report.degraded_reasons == report.degraded_reasons

    assert len(captured) == 3
    assert [request.exec_config.seed for request, *_values in captured] == [31, 32, 33]
    assert len({id(request) for request, *_values in captured}) == 3

    for _request, bindings, bound_income, bound_weekday in captured:
        assert artifact_ref_identity_key(bindings.data_snapshot_ref) == artifact_ref_identity_key(
            masked_snapshot_ref
        )
        assert bound_income == [1.0, 2.0]
        assert bound_weekday == [3.0, 4.0]
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(fresh_reader, bindings.data_snapshot_ref)
        )
        assert bindings.data_snapshot_ref.manifest_profile_sha256 is not None
        (masked_data_edge,) = [
            item
            for item in fresh_reader.get_manifest(bindings.data_snapshot_ref).inputs
            if item.role == "masked_data"
        ]
        assert masked_data_edge.artifact_id == snapshot.data_ref.artifact_id
        assert masked_data_edge.manifest_profile_sha256 is not None
        selected_data = snapshot.data_ref.model_copy(
            update={"manifest_profile_sha256": masked_data_edge.manifest_profile_sha256}
        )
        masked_payload = load_core_json_artifact(fresh_reader, selected_data)
        assert masked_payload["metric"] == [1.0, 2.0]
        assert masked_payload["weekday"] == [3, 4]
        assert "derived_income" not in masked_payload
        assert 900.0 not in masked_payload["metric"]
        assert 901.0 not in masked_payload["metric"]

    cohort_ref = report.scenarios[0].metadata["replica_cohort_ref"]
    cohort = from_canonical_bytes(store.get_bytes(cohort_ref["artifact_id"]))
    assert cohort["requested_count"] == 3
    assert cohort["started_count"] == 3
    assert cohort["foundry_execute_count"] == 3
    assert cohort["completed_count"] == 3
    assert cohort["failed_count"] == 0
    assert [row["seed"] for row in cohort["replicas"]] == [31, 32, 33]
    assert len({row["run_id"] for row in cohort["replicas"]}) == 3
    for row in cohort["replicas"]:
        assert row["status"] == "completed"
        assert row["workflow_status"] == "ok"
        workflow_report = from_canonical_bytes(
            store.get_bytes(row["workflow_report_ref"]["artifact_id"])
        )
        assert workflow_report["run_id"] == row["run_id"]
        assert row["seed_source"] == "exec_config.seed"
        physical_request = row["physical_request"]
        assert physical_request["exec_config"]["seed"] == row["seed"]
        simulation = from_canonical_bytes(
            store.get_bytes(row["simulation_result_ref"]["artifact_id"])
        )
        metrics = from_canonical_bytes(store.get_bytes(row["metrics_ref"]["artifact_id"]))
        assert "seed_source:exec_config.seed" in simulation["notes"]
        assert isinstance(metrics, dict)

    report_manifest = store.get_manifest(report.cas_artifact_id)
    assert any(
        item.role == "replica_cohort:masked_foundry_replicas" for item in report_manifest.inputs
    )
    assert report.degraded is True
    assert (
        "masked_foundry_replicas: scientist_replica_projection_unsupported"
        in fresh_report.degraded_reasons
    )
    fresh_scenario = fresh_report.scenarios[0]
    assert fresh_scenario.metadata["replica_cohort_ref"] == cohort_ref
    fresh_cohort = from_canonical_bytes(fresh_reader.get_bytes(cohort_ref["artifact_id"]))
    assert fresh_cohort["requested_count"] == 3
    assert fresh_cohort["completed_count"] == 3
    assert fresh_cohort["failed_count"] == 0


def test_backtest_selects_exact_view_for_a_safe_legacy_snapshot_body(tmp_path) -> None:
    cas_path = tmp_path / "cas"
    store = FileSystemCAS(cas_path)
    ir_store = ensure_ir_artifact_store(store)
    raw_data, plan = _plan(tmp_path, replica_count=1)
    orchestrator = BacktestOrchestrator(cas=store)
    projection = orchestrator._masker.mask(raw_data, plan)
    canon = CanonSpec(forbid_floats=False, forbid_nan_inf=False)
    old_data = ArtifactRef.model_validate(
        put_json_artifact(
            ir_store,
            projection,
            kind="scientist.backtest.masked_historical_view",
            schema_name="polisyos.scientist.backtesting.MaskedHistoricalView",
            schema_version="1.0",
            canon_spec=canon,
        )
    )
    old_body = DataSnapshot(
        data_ref=old_data,
        stats={"masking_strategy": "drop_post", "intervention_step": 2},
        notes=["scientist.backtest.masked_historical_view", f"plan_id:{plan.plan_id}"],
    ).model_dump(mode="json")
    old_snapshot = DataSnapshotRef.model_validate(
        put_json_artifact(
            ir_store,
            old_body,
            kind="fabric.data_snapshot",
            schema_name="polisyos.core.DataSnapshot",
            schema_version="0.2.0",
            inputs=[InputRef(artifact_id=str(old_data.artifact_id), role="masked_data")],
            canon_spec=canon,
        )
    )

    selected = DataSnapshotRef.model_validate(orchestrator._persist_masked_view(plan, projection))
    assert selected.artifact_id == old_snapshot.artifact_id
    assert old_snapshot.manifest_profile_sha256 is None
    assert selected.manifest_profile_sha256 is not None
    reader = FileSystemCAS(cas_path)
    assert load_core_json_artifact(reader, selected) == old_body
    (edge,) = reader.get_manifest(selected).inputs
    assert edge.role == "masked_data" and edge.artifact_id == old_data.artifact_id
    assert edge.manifest_profile_sha256 is not None
    assert reader.get_manifest(old_snapshot).inputs[0].manifest_profile_sha256 is None

    registry = build_default_registry_bundle(store, return_selected_profile=True)
    rule = FoundryInputBindingRule(
        binding_id="history_to_income",
        source_path="metric",
        target_slot_id="agents.income",
    )
    actual = build_input_bindings(
        reader,
        data_snapshot_ref=selected,
        registry_bundle_ref=registry.bundle_ref,
        rules=[rule],
        return_selected_profile=True,
    )
    persisted_bindings = FoundryInputBindings.model_validate(
        load_core_json_artifact(reader, actual.input_bindings_ref)
    )
    assert artifact_ref_identity_key(persisted_bindings.data_snapshot_ref) == (
        artifact_ref_identity_key(selected)
    )
    bound_state = load_state_snapshot(reader, snapshot_ref=actual.bound_state_snapshot_ref)
    assert np.asarray(bound_state.agents.income, dtype=float).tolist() == [1.0, 2.0]

    foreign_child = ArtifactRef.model_validate(
        put_json_artifact(
            ir_store,
            projection,
            kind="fixture.foreign_history",
            schema_name="fixture.ForeignHistory",
            schema_version="1.0",
            canon_spec=canon,
            return_selected_profile=True,
        )
    )
    assert foreign_child.artifact_id == old_data.artifact_id
    assert foreign_child.manifest_profile_sha256 != edge.manifest_profile_sha256
    foreign_parent = DataSnapshotRef.model_validate(
        put_json_artifact(
            ir_store,
            old_body,
            kind="fabric.data_snapshot",
            schema_name="polisyos.core.DataSnapshot",
            schema_version="0.2.0",
            inputs=[input_ref_from_artifact_ref(foreign_child, role="masked_data")],
            canon_spec=canon,
            return_selected_profile=True,
        )
    )
    assert foreign_parent.artifact_id == selected.artifact_id
    assert foreign_parent.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="nested reference differs from its manifest: data_ref"):
        build_input_bindings(
            reader,
            data_snapshot_ref=foreign_parent,
            registry_bundle_ref=registry.bundle_ref,
            rules=[rule],
            return_selected_profile=True,
        )


@pytest.mark.parametrize(
    ("source_path", "required", "default_value", "masking_strategy"),
    [
        ("derived_income", True, [451.0, 451.0], MaskingStrategy.DROP_POST),
        ("metric.2", True, [451.0, 451.0], MaskingStrategy.DROP_POST),
        ("", False, None, MaskingStrategy.DROP_POST),
        ("_backtest_metadata.intervention_step", False, None, MaskingStrategy.DROP_POST),
        ("metric.2", False, None, MaskingStrategy.REPLACE_NAN),
    ],
    ids=(
        "future-derived",
        "future-position",
        "whole-view",
        "internal-metadata",
        "mask-placeholder",
    ),
)
def test_backtest_refuses_unavailable_binding_before_foundry(
    monkeypatch, tmp_path, source_path, required, default_value, masking_strategy
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    raw_data, plan = _plan(tmp_path, replica_count=1)
    plan.masking_strategy = masking_strategy
    raw_data["derived_income"] = [451.0, 451.0]
    assert plan.historical_data_path is not None
    history = Path(plan.historical_data_path)
    history.write_text(json.dumps(raw_data), encoding="utf-8")
    original_source = history.read_bytes()

    projected = orchestrator._masker.mask(raw_data, plan)
    snapshot = DataSnapshotRef.model_validate(orchestrator._persist_masked_view(plan, projected))
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    trinity = _persist_trinity(
        store,
        data_snapshot_ref=snapshot,
        registry_bundle_ref=registry.bundle_ref,
    )
    _bind_real_default_route(
        plan=plan, trinity_ref=trinity, registry_bundle_ref=registry.bundle_ref
    )
    assert plan.scientist_state is not None
    plan.scientist_state["params"]["foundry_input_binding_rules"][0].update(
        {"source_path": source_path, "required": required, "default_value": default_value}
    )
    original_plan = plan.model_dump(mode="python")
    foundry_calls: list[ExecuteRequest] = []
    execute = DefaultFoundryPort.execute

    def observe(port, actual_store, request: ExecuteRequest):
        foundry_calls.append(request)
        return execute(port, actual_store, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    report = orchestrator.run([plan])

    assert not foundry_calls
    assert history.read_bytes() == original_source
    assert plan.model_dump(mode="python") == original_plan
    assert report.degraded and report.prediction_mode_effective == PredictionSource.NAIVE.value
    assert any(
        "scientist_historical_feature_not_admitted" in reason for reason in report.degraded_reasons
    )
    assert any(repr(source_path) in warning for warning in report.metadata["warnings"])
    assert "replica_cohort_ref" not in report.scenarios[0].metadata


def test_backtest_retains_failed_real_foundry_replica_and_fresh_report_readback(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    raw_data, plan = _plan(tmp_path, intervention_step=None, intervention_date="t2")
    masked_data = orchestrator._masker.mask(raw_data, plan)
    masked_snapshot_ref = DataSnapshotRef.model_validate(
        orchestrator._persist_masked_view(plan, masked_data)
    )
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    trinity_ref = _persist_trinity(
        store,
        data_snapshot_ref=masked_snapshot_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )
    _bind_real_default_route(
        plan=plan,
        trinity_ref=trinity_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )

    attempted_requests: list[ExecuteRequest] = []
    original_execute = DefaultFoundryPort.execute

    def _fail_middle_replica_and_delegate_others(
        self,
        cas,
        request: ExecuteRequest,
    ):
        attempted_requests.append(request)
        if len(attempted_requests) == 2:
            raise RuntimeError("controlled_foundry_replica_failure")
        return original_execute(self, cas, request)

    monkeypatch.setattr(
        DefaultFoundryPort,
        "execute",
        _fail_middle_replica_and_delegate_others,
    )
    report = orchestrator.run([plan])
    assert report.cas_artifact_id is not None

    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    fresh_report = load_backtest_report(
        fresh_reader,
        BacktestReportRef(artifact_id=report.cas_artifact_id),
    )
    scenario = fresh_report.scenarios[0]
    cohort_ref = scenario.metadata["replica_cohort_ref"]
    cohort = from_canonical_bytes(fresh_reader.get_bytes(cohort_ref["artifact_id"]))

    assert len(attempted_requests) == 3
    assert [request.exec_config.seed for request in attempted_requests] == [31, 32, 33]
    assert fresh_report.degraded is True
    assert fresh_report.prediction_mode_effective == PredictionSource.NAIVE.value
    assert any(
        item.endswith("scientist_replica_cohort_incomplete")
        for item in fresh_report.degraded_reasons
    )
    assert scenario.metadata["replica_cohort_ref"] == cohort_ref
    assert scenario.metadata["prediction_source_effective"] == PredictionSource.NAIVE.value
    assert cohort["requested_count"] == 3
    assert cohort["started_count"] == 3
    assert cohort["foundry_execute_count"] == 3
    assert cohort["completed_count"] == 2
    assert cohort["failed_count"] == 1
    replicas = cohort["replicas"]
    assert [item["status"] for item in replicas] == ["completed", "failed", "completed"]
    assert len({item["run_id"] for item in replicas}) == 3
    assert [item["seed"] for item in replicas] == [31, 32, 33]
    assert all(item["workflow_report_ref"] for item in replicas)
    assert "RuntimeError: controlled_foundry_replica_failure" in replicas[1]["failure"]
    assert replicas[1]["workflow_status"] == "fail"
    assert any(
        "controlled_foundry_replica_failure" in warning
        for warning in fresh_report.metadata["warnings"]
    )
    for replica in (replicas[0], replicas[2]):
        assert replica["simulation_result_ref"] is not None
        assert replica["metrics_ref"] is not None
        simulation = from_canonical_bytes(
            fresh_reader.get_bytes(replica["simulation_result_ref"]["artifact_id"])
        )
        metrics = from_canonical_bytes(
            fresh_reader.get_bytes(replica["metrics_ref"]["artifact_id"])
        )
        assert "seed_source:exec_config.seed" in simulation["notes"]
        assert isinstance(metrics, dict)
    report_manifest = store.get_manifest(report.cas_artifact_id)
    assert any(
        item.role == "replica_cohort:masked_foundry_replicas" for item in report_manifest.inputs
    )


def test_full_data_model_spec_fails_before_any_foundry_replica_executes(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    raw_data, plan = _plan(tmp_path, replica_count=1)
    full_snapshot_ref = DataSnapshotRef.model_validate(
        orchestrator._persist_masked_view(plan, raw_data)
    )
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    trinity_ref = _persist_trinity(
        store,
        data_snapshot_ref=full_snapshot_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )
    _bind_real_default_route(
        plan=plan,
        trinity_ref=trinity_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
    )

    executed: list[ExecuteRequest] = []
    original_execute = DefaultFoundryPort.execute

    def _capture_and_execute(self, cas, request: ExecuteRequest):
        executed.append(request)
        return original_execute(self, cas, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", _capture_and_execute)
    report = orchestrator.run([plan])

    assert executed == []
    cohort_ref = report.scenarios[0].metadata["replica_cohort_ref"]
    cohort = from_canonical_bytes(store.get_bytes(cohort_ref["artifact_id"]))
    assert cohort["requested_count"] == 1
    assert cohort["started_count"] == 1
    assert cohort["foundry_execute_count"] == 0
    assert cohort["completed_count"] == 0
    assert cohort["failed_count"] == 1
    assert cohort["replicas"][0]["status"] == "failed"
    assert cohort["replicas"][0]["workflow_status"] == "fail"
    failure_report = from_canonical_bytes(
        store.get_bytes(cohort["replicas"][0]["workflow_report_ref"]["artifact_id"])
    )
    assert failure_report["run_id"] == cohort["replicas"][0]["run_id"]
    assert cohort["replicas"][0]["physical_request"] is None
    assert any(
        node["alias"] == "bind_foundry_inputs"
        and "ModelSpec data_snapshot_ref mismatch" in node["error"]["message"]
        for node in cohort["replicas"][0]["workflow_failures"]
    )
    assert "ModelSpec data_snapshot_ref mismatch" in cohort["replicas"][0]["failure"]
    assert any(
        "ModelSpec data_snapshot_ref mismatch" in warning for warning in report.metadata["warnings"]
    )
    assert report.degraded is True
    assert any(
        item.endswith("scientist_replica_cohort_incomplete") for item in report.degraded_reasons
    )


def test_backtest_without_temporal_cutoff_refuses_before_snapshot_or_foundry_execution(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    raw_data, plan = _plan(tmp_path, replica_count=1, intervention_step=None)
    assert raw_data["metric"] == [1.0, 2.0, 900.0, 901.0]

    executed: list[ExecuteRequest] = []
    original_execute = DefaultFoundryPort.execute

    def _capture_execute(self, cas, request: ExecuteRequest):
        executed.append(request)
        return original_execute(self, cas, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", _capture_execute)
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    report = orchestrator.run([plan])
    after_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    new_manifests = [
        store.get_manifest(artifact_id) for artifact_id in sorted(after_ids - before_ids)
    ]

    assert executed == []
    assert all(
        manifest.kind
        not in {
            "scientist.backtest.masked_historical_view",
            "fabric.data_snapshot",
            "scientist.backtest.replica_cohort",
        }
        for manifest in new_manifests
    )
    scenario = report.scenarios[0]
    assert scenario.metadata.get("replica_cohort_ref") is None
    assert scenario.metadata["degraded"] is True
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert report.degraded is True
    assert any(
        item.endswith("scientist_historical_cutoff_missing") for item in report.degraded_reasons
    )


def test_unresolved_present_cutoff_fails_before_snapshot_or_foundry_execution(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    orchestrator = BacktestOrchestrator(cas=store)
    _raw_data, plan = _plan(
        tmp_path,
        replica_count=1,
        intervention_step=None,
        intervention_date=" ",
    )

    executed: list[ExecuteRequest] = []

    def _capture_execute(self, cas, request: ExecuteRequest):
        executed.append(request)
        raise AssertionError("unresolved cutoff must not reach Foundry")

    monkeypatch.setattr(DefaultFoundryPort, "execute", _capture_execute)
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    with pytest.raises(
        MaskingValidationError,
        match="intervention_date requires one matching time_index",
    ):
        orchestrator.run([plan])

    after_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    new_manifests = [
        store.get_manifest(artifact_id) for artifact_id in sorted(after_ids - before_ids)
    ]
    assert executed == []
    assert all(
        manifest.kind
        not in {
            "scientist.backtest.masked_historical_view",
            "fabric.data_snapshot",
            "scientist.backtest.replica_cohort",
        }
        for manifest in new_manifests
    )
