from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    DerivedArtifact,
    ExecuteRequest,
    ExecuteResult,
    ExecPlan,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.executor import (
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
)


def execute(store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
    state_snapshot_ref = _resolve_state_snapshot(store, request)
    registry_bundle_ref = request.registry_bundle_ref
    if registry_bundle_ref is None:
        raise ValueError("registry_bundle_ref is required for execute()")

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)
    base_state = load_state_snapshot(store, snapshot_ref=state_snapshot_ref)

    exec_plan = _load_model(store, request.exec_plan_ref, ExecPlan)
    exec_artifacts = execute_program_graph(
        store,
        program_ref=exec_plan.program_ref,
        exec_plan_ref=request.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registry_content.mechanism_registry,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        selector_field_registry=registry_content.selector_field_registry,
        constraint_registry=registry_content.constraint_registry,
        step=int(getattr(base_state, "step", 0)),
        seed=request.exec_config.seed,
        base_ref=state_snapshot_ref,
        capture_env=request.exec_config.capture_env,
    )

    _, applied = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        step=int(getattr(base_state, "step", 0)),
        base_ref=state_snapshot_ref,
    )

    sim_result = SimulationResult(
        exec_plan_ref=request.exec_plan_ref,
        metrics_ref=exec_artifacts.metrics_ref,
        state_snapshot_ref=StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id),
        environment_ref=exec_artifacts.environment_ref,
        environment_fingerprint=exec_artifacts.environment_fingerprint,
    )
    sim_inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=exec_artifacts.metrics_ref.artifact_id, role="metrics"),
        InputRef(artifact_id=exec_artifacts.state_delta_ref.artifact_id, role="state_delta"),
        InputRef(artifact_id=applied.state_snapshot_ref.artifact_id, role="state_snapshot"),
    ]
    sim_result_ref = store.put_json(
        sim_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.0"),
            inputs=sim_inputs,
        ),
    )

    derived_refs = [
        DerivedArtifact(role="metrics", ref=exec_artifacts.metrics_ref),
        DerivedArtifact(role="state_delta", ref=exec_artifacts.state_delta_ref),
    ]
    if exec_artifacts.constraint_report_ref is not None:
        derived_refs.append(
            DerivedArtifact(role="constraint_report", ref=exec_artifacts.constraint_report_ref)
        )
    if exec_artifacts.environment_ref is not None:
        derived_refs.append(
            DerivedArtifact(role="environment_manifest", ref=exec_artifacts.environment_ref)
        )

    return ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=sim_result_ref.artifact_id),
        derived_refs=derived_refs,
        notes=[],
    )


def _resolve_state_snapshot(store: FileSystemCAS, request: ExecuteRequest) -> StateSnapshotRef:
    if request.state_snapshot_ref is not None and request.data_snapshot_ref is not None:
        raise ValueError("Only one of state_snapshot_ref or data_snapshot_ref may be set")
    if request.state_snapshot_ref is not None:
        return request.state_snapshot_ref
    if request.data_snapshot_ref is None:
        raise ValueError("Either state_snapshot_ref or data_snapshot_ref must be set")
    snapshot_payload = from_canonical_bytes(
        store.get_bytes(request.data_snapshot_ref.artifact_id)
    )
    snapshot = DataSnapshot.model_validate(snapshot_payload)
    if snapshot.data_ref.kind != "foundry.state_snapshot":
        raise ValueError(
            f"DataSnapshot.data_ref.kind must be foundry.state_snapshot, got {snapshot.data_ref.kind}"
        )
    return StateSnapshotRef(artifact_id=snapshot.data_ref.artifact_id)


def _load_model(store: FileSystemCAS, ref: ArtifactRef, model_cls):
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)
