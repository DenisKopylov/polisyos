"""Execute compiled Foundry plans from bound runtime state snapshots.

`execute()` is the public runtime entrypoint paired with
`polisyos.foundry.compile.api.compile`. It resolves
`FoundryInputBindingsRef -> StateSnapshotRef`, replays the persisted
`ExecPlan` deterministically with the requested seed, and writes
`foundry.simulation_result` plus runtime-derived artifacts back to CAS.
"""
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
    ParameterOverrideBundle,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry._execution_posture import resolve_execution_posture
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.executor import (
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
)
from polisyos.foundry.registry import MissingRuntimeMechanismSupportError


@dataclass(frozen=True)
class _ResolvedStateSource:
    """Internal bundle describing where the execution base state came from."""

    state_snapshot_ref: StateSnapshotRef
    notes: tuple[str, ...]
    input_refs: tuple[InputRef, ...]


def execute(store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
    """Execute a compiled Foundry plan from a bound state snapshot.

    `request.input_bindings_ref` is treated as the canonical boundary object
    between Fabric data ingestion and Foundry runtime state. Execution reads
    the bound `StateSnapshotRef`, applies the `ExecPlan`, persists metrics,
    state-delta, optional constraint/environment artifacts, and finally writes
    a `SimulationResult` whose `state_snapshot_ref` points to the updated
    post-step snapshot.

    Deterministic replay is expected when the same `exec_plan_ref`,
    `input_bindings_ref`, `registry_bundle_ref`, parameter overrides, and
    `exec_config.seed` are reused against identical CAS content. Runtime
    unsupported-mechanism errors are returned as `ExecuteResult(ok=False, ...)`
    envelopes; malformed requests and missing registry references raise.

    Args:
        store: CAS containing the `ExecPlan`, registry bundle, input bindings,
            and parameter override artifacts, and receiving runtime outputs.
        request: Execution contract referencing the compiled plan, bound
            input snapshot, registry bundle, and runtime configuration.

    Returns:
        `ExecuteResult` with `simulation_result_ref` and derived artifact refs
        on success, or `ok=False` plus notes such as
        `missing_runtime_mechanism_support:*` or
        `hard_constraint_violation` when execution is rejected.

    Raises:
        ValueError: If `registry_bundle_ref` is missing or the request points
            to unreadable or invalid artifacts.

    Example:
        ```python
        from polisyos.core.contracts.foundry import ExecuteRequest
        from polisyos.foundry import execute

        result = execute(
            store,
            ExecuteRequest(
                exec_plan_ref=compile_result.exec_plan_ref,
                input_bindings_ref=input_bindings_ref,
                registry_bundle_ref=registry_bundle_ref,
            ),
        )
        if result.ok:
            simulation_ref = result.simulation_result_ref
        ```
    """

    resolved_state = _resolve_state_snapshot(store, request)
    state_snapshot_ref = resolved_state.state_snapshot_ref
    registry_bundle_ref = request.registry_bundle_ref
    if registry_bundle_ref is None:
        raise ValueError("registry_bundle_ref is required for execute()")

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)
    base_state = load_state_snapshot(store, snapshot_ref=state_snapshot_ref)

    exec_plan = _load_model(store, request.exec_plan_ref, ExecPlan)
    posture = resolve_execution_posture(exec_plan, request.exec_config)
    current_step = int(getattr(base_state, "step", 0))
    execution_notes = [*resolved_state.notes, *posture.notes]
    if posture.max_steps is not None and current_step >= posture.max_steps:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[],
            notes=[*execution_notes, f"max_steps_reached:{current_step}>={posture.max_steps}"],
        )
    parameter_overrides: dict[str, dict[str, object]] | None = None
    parameter_override_inputs: list[InputRef] = []
    if request.parameter_override_bundle_ref is not None:
        bundle = _load_model(
            store,
            request.parameter_override_bundle_ref,
            ParameterOverrideBundle,
        )
        parameter_overrides = {
            str(node_id): dict(values)
            for node_id, values in bundle.overrides.items()
            if isinstance(values, dict)
        }
        parameter_override_inputs.append(
            InputRef(
                artifact_id=request.parameter_override_bundle_ref.artifact_id,
                role="parameter_override_bundle",
            )
        )
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
            step=current_step,
            seed=posture.seed,
            base_ref=state_snapshot_ref,
            capture_env=posture.capture_env,
            parameter_overrides=parameter_overrides,
            parameter_override_bundle_ref=request.parameter_override_bundle_ref,
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

    if exec_artifacts.constraint_hard_fail:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, "hard_constraint_violation"],
        )

    _, applied = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        step=current_step,
        base_ref=state_snapshot_ref,
    )

    sim_result = SimulationResult(
        exec_plan_ref=request.exec_plan_ref,
        metrics_ref=MetricsRef(artifact_id=exec_artifacts.metrics_ref.artifact_id),
        state_snapshot_ref=StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id),
        environment_ref=exec_artifacts.environment_ref,
        environment_fingerprint=(
            exec_artifacts.environment_fingerprint or posture.current_environment_fingerprint
        ),
        notes=list(execution_notes),
    )
    sim_inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=exec_artifacts.metrics_ref.artifact_id, role="metrics"),
        InputRef(artifact_id=exec_artifacts.state_delta_ref.artifact_id, role="state_delta"),
        InputRef(artifact_id=applied.state_snapshot_ref.artifact_id, role="state_snapshot"),
    ]
    sim_inputs.extend(resolved_state.input_refs)
    sim_inputs.extend(parameter_override_inputs)
    sim_result_ref = store.put_json(
        sim_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
            inputs=sim_inputs,
        ),
    )

    return ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=sim_result_ref.artifact_id),
        derived_refs=derived_refs,
        notes=execution_notes,
    )


def _resolve_state_snapshot(store: FileSystemCAS, request: ExecuteRequest) -> _ResolvedStateSource:
    """Load and validate the bound snapshot referenced by `request`."""
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
    """Raise if `ref` does not resolve to a readable CAS manifest."""
    store.get_manifest(ref.artifact_id)


def _load_model(store: FileSystemCAS, ref: ArtifactRef, model_cls):
    """Deserialize a CAS JSON artifact into the requested Pydantic model."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)
