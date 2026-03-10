from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    DerivedArtifact,
    ExecPlan,
    ExecuteRequest,
    ExecuteResult,
    FoundryInputBindingsRef,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.executor import (
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
)
from polisyos.foundry.registry import MissingRuntimeMechanismSupportError


@dataclass(frozen=True)
class _ResolvedStateSource:
    state_snapshot_ref: StateSnapshotRef
    notes: tuple[str, ...]
    input_refs: tuple[InputRef, ...]


def execute(store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
    resolved_state = _resolve_state_snapshot(store, request)
    state_snapshot_ref = resolved_state.state_snapshot_ref
    registry_bundle_ref = request.registry_bundle_ref
    if registry_bundle_ref is None:
        raise ValueError("registry_bundle_ref is required for execute()")

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)
    base_state = load_state_snapshot(store, snapshot_ref=state_snapshot_ref)

    exec_plan = _load_model(store, request.exec_plan_ref, ExecPlan)
    try:
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
    except MissingRuntimeMechanismSupportError as exc:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[],
            notes=[
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
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
        metrics_ref=MetricsRef(artifact_id=exec_artifacts.metrics_ref.artifact_id),
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
    sim_inputs.extend(resolved_state.input_refs)
    sim_result_ref = store.put_json(
        sim_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
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
        notes=list(resolved_state.notes),
    )


def _resolve_state_snapshot(store: FileSystemCAS, request: ExecuteRequest) -> _ResolvedStateSource:
    bindings_ref = FoundryInputBindingsRef.model_validate(
        request.input_bindings_ref.model_dump()
    )
    bindings = load_input_bindings(store, bindings_ref)
    _ensure_readable(store, bindings.data_snapshot_ref)
    _ensure_readable(store, bindings.bound_state_snapshot_ref)
    return _ResolvedStateSource(
        state_snapshot_ref=bindings.bound_state_snapshot_ref,
        notes=("state_source:input_bindings_ref",),
        input_refs=(
            InputRef(
                artifact_id=bindings_ref.artifact_id,
                role="input.input_bindings_ref",
            ),
            InputRef(
                artifact_id=bindings.data_snapshot_ref.artifact_id,
                role="input.data_snapshot_ref",
            ),
            InputRef(
                artifact_id=bindings.bound_state_snapshot_ref.artifact_id,
                role="input.bound_state_snapshot_ref",
            ),
        ),
    )


def _ensure_readable(store: FileSystemCAS, ref: ArtifactRef) -> None:
    store.get_manifest(ref.artifact_id)


def _load_model(store: FileSystemCAS, ref: ArtifactRef, model_cls):
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)
