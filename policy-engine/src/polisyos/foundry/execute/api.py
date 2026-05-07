"""Execute compiled Foundry plans from bound runtime state snapshots.

`execute()` is the public runtime entrypoint paired with
`polisyos.foundry.compile.api.compile`. It resolves
`FoundryInputBindingsRef -> StateSnapshotRef`, replays the persisted
`ExecPlan` deterministically with the requested seed, and writes
`foundry.simulation_result` plus runtime-derived artifacts back to CAS.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    DerivedArtifact,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    ExecPlan,
    ExecuteRequest,
    ExecuteResult,
    FeedbackConfig,
    FeedbackConvergenceCertificate,
    FeedbackConvergenceCertificateRef,
    FeedbackFixedPointCandidate,
    FeedbackIterationRecord,
    FeedbackJacobianDiagnostics,
    FeedbackJacobianDiagnosticsRef,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    FeedbackTrace,
    FeedbackTraceRef,
    FoundryInputBindingsRef,
    Metrics,
    MetricsRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
    WelfareBoundReportRef,
)
from polisyos.core.registry import RegistryBundleContent, load_registry_bundle_content
from polisyos.foundry._registry import MissingRuntimeMechanismSupportError
from polisyos.foundry.data_plane import (
    extract_feedback_diagnostics,
    extract_feedback_state,
    inject_feedback_state,
    load_input_bindings,
)
from polisyos.foundry.execute._internal.posture import (
    ResolvedExecutionPosture,
    resolve_execution_posture,
)
from polisyos.foundry.execute.executor import (
    ExecuteArtifacts,
    apply_state_delta,
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.foundry.feedback import (
    AlternativeSolution,
    MapEvaluation,
    PreparedFeedbackConfig,
    SolveOutcome,
    discover_equilibria,
    prepare_feedback_config,
    snapshot_from_vector,
    solve_fixed_point,
)


@dataclass(frozen=True)
class _ResolvedStateSource:
    """Internal bundle describing where the execution base state came from."""

    state_snapshot_ref: StateSnapshotRef
    notes: tuple[str, ...]
    input_refs: tuple[InputRef, ...]


@dataclass(frozen=True)
class _FeedbackExecutionEvaluation:
    """Internal one-shot execution result used by the outer feedback solver."""

    map_evaluation: MapEvaluation
    final_state: object


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
    if request.feedback_config_ref is not None:
        feedback_config = _load_model(store, request.feedback_config_ref, FeedbackConfig)
        if feedback_config.mode == "fixed_point":
            return _execute_with_feedback(
                store,
                request=request,
                resolved_state=resolved_state,
                registry_content=registry_content,
                base_state=base_state,
                exec_plan=exec_plan,
                posture=posture,
                current_step=current_step,
                execution_notes=execution_notes,
                parameter_overrides=parameter_overrides,
                parameter_override_inputs=parameter_override_inputs,
                feedback_config=feedback_config,
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
            observed_range_bundle_ref=request.observed_range_bundle_ref,
            welfare_bound_mode=request.welfare_bound_mode,
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

    derived_refs = _build_standard_derived_refs(exec_artifacts)
    welfare_bound_failure_notes = _evaluate_welfare_bound_requirement(
        store,
        request=request,
        derived_refs=derived_refs,
    )

    if exec_artifacts.constraint_hard_fail:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, "hard_constraint_violation"],
        )
    if welfare_bound_failure_notes:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, *welfare_bound_failure_notes],
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
        welfare_bound_refs=_extract_welfare_bound_refs(derived_refs),
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
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
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
    bindings_ref = FoundryInputBindingsRef.model_validate(request.input_bindings_ref.model_dump())
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


def _load_model[ModelT: BaseModel](
    store: FileSystemCAS,
    ref: ArtifactRef,
    model_cls: type[ModelT],
) -> ModelT:
    """Deserialize a CAS JSON artifact into the requested Pydantic model."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)


def _execute_with_feedback(
    store: FileSystemCAS,
    *,
    request: ExecuteRequest,
    resolved_state: _ResolvedStateSource,
    registry_content: RegistryBundleContent,
    base_state: object,
    exec_plan: ExecPlan,
    posture: ResolvedExecutionPosture,
    current_step: int,
    execution_notes: list[str],
    parameter_overrides: dict[str, dict[str, object]] | None,
    parameter_override_inputs: list[InputRef],
    feedback_config: FeedbackConfig,
) -> ExecuteResult:
    initial_feedback_state = _build_initial_feedback_state(base_state, feedback_config)
    prepared = prepare_feedback_config(
        feedback_config,
        initial_state=initial_feedback_state,
    )

    def evaluate_feedback_map(values: np.ndarray) -> MapEvaluation:
        snapshot = snapshot_from_vector(prepared, np.asarray(values, dtype=float))
        injected_state, feedback_overrides = inject_feedback_state(
            base_state,
            config=feedback_config,
            snapshot=snapshot,
        )
        merged_overrides = _merge_parameter_overrides(parameter_overrides, feedback_overrides)
        evaluation = _run_feedback_iteration(
            store,
            exec_plan=exec_plan,
            request=request,
            registry_content=registry_content,
            posture=posture,
            current_step=current_step,
            base_state=injected_state,
            parameter_overrides=merged_overrides,
            feedback_config=feedback_config,
        )
        return evaluation.map_evaluation

    try:
        outcome = solve_fixed_point(
            prepared=prepared,
            evaluate_map=evaluate_feedback_map,
        )
    except MissingRuntimeMechanismSupportError as exc:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[],
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
        )
    except RuntimeError as exc:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[],
            notes=[*execution_notes, "feedback_mode:fixed_point", f"feedback_solve_failed:{exc}"],
        )
    solved_feedback_state = snapshot_from_vector(
        prepared,
        np.asarray(outcome.solution, dtype=float),
        notes=[
            "fixed_point_solution" if outcome.converged else "fixed_point_candidate",
            outcome.status,
        ],
    )
    feedback_trace_ref = _persist_feedback_trace(
        store,
        outcome=outcome,
        request=request,
    )
    feedback_jacobian_ref = _persist_feedback_jacobian(
        store,
        outcome=outcome,
        request=request,
        trace_ref=feedback_trace_ref,
    )
    feedback_certificate_ref = _persist_feedback_convergence_certificate(
        store,
        outcome=outcome,
        request=request,
        prepared=prepared,
        trace_ref=feedback_trace_ref,
        jacobian_ref=feedback_jacobian_ref,
    )
    feedback_artifacts = [
        DerivedArtifact(role="feedback_trace", ref=feedback_trace_ref),
        DerivedArtifact(role="feedback_convergence_certificate", ref=feedback_certificate_ref),
    ]
    if feedback_jacobian_ref is not None:
        feedback_artifacts.append(
            DerivedArtifact(role="feedback_jacobian_diagnostics", ref=feedback_jacobian_ref)
        )
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None = None
    multiplicity_notes: list[str] = []
    if (
        feedback_config.solver.detect_multiplicity
        or feedback_config.solver.multiplicity_mode != "off"
    ):
        try:
            report = discover_equilibria(
                prepared=prepared,
                evaluate_map=evaluate_feedback_map,
                base_outcome=outcome,
                runtime_refs=[
                    str(feedback_trace_ref.artifact_id),
                    str(feedback_certificate_ref.artifact_id),
                    *(
                        [str(feedback_jacobian_ref.artifact_id)]
                        if feedback_jacobian_ref is not None
                        else []
                    ),
                ],
            )
            multiplicity_report_ref = _persist_equilibrium_multiplicity_report(
                store,
                request=request,
                report=report,
                trace_ref=feedback_trace_ref,
                jacobian_ref=feedback_jacobian_ref,
                convergence_certificate_ref=feedback_certificate_ref,
            )
            feedback_artifacts.append(
                DerivedArtifact(
                    role="equilibrium_multiplicity_report",
                    ref=multiplicity_report_ref,
                )
            )
            multiplicity_notes.append("feedback_multiplicity_report:created")
        except RuntimeError as exc:
            multiplicity_notes.append(f"feedback_multiplicity_report_failed:{exc}")

    if not outcome.converged:
        feedback_result_ref = _persist_feedback_result(
            store,
            request=request,
            prepared=prepared,
            exec_artifacts=None,
            initial_feedback_state=initial_feedback_state,
            final_feedback_state=solved_feedback_state,
            final_feedback_diagnostics=outcome.final_diagnostics,
            final_override_bundle_ref=None,
            trace_ref=feedback_trace_ref,
            jacobian_ref=feedback_jacobian_ref,
            convergence_certificate_ref=feedback_certificate_ref,
            multiplicity_report_ref=multiplicity_report_ref,
            status=outcome.status,
            converged=False,
            failure_reason=outcome.failure_reason,
            alternative_solutions=outcome.alternative_solutions,
            notes=[
                "feedback_mode:fixed_point",
                f"feedback_status:{outcome.status}",
                *multiplicity_notes,
            ],
        )
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[
                *feedback_artifacts,
                DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
            ],
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                f"feedback_status:{outcome.status}",
                *multiplicity_notes,
                *([f"feedback_failure:{outcome.failure_reason}"] if outcome.failure_reason else []),
            ],
        )

    final_injected_state, final_feedback_overrides = inject_feedback_state(
        base_state,
        config=feedback_config,
        snapshot=solved_feedback_state,
    )
    merged_final_overrides = _merge_parameter_overrides(
        parameter_overrides,
        final_feedback_overrides,
    )
    final_override_bundle_ref = _persist_parameter_override_bundle(
        store,
        request=request,
        merged_overrides=merged_final_overrides,
        feedback_notes=feedback_config.notes,
    )

    feedback_base_inputs = [
        InputRef(
            artifact_id=resolved_state.state_snapshot_ref.artifact_id,
            role="input.bound_state_snapshot_ref",
        )
    ]
    if request.feedback_config_ref is not None:
        feedback_base_inputs.append(
            InputRef(
                artifact_id=request.feedback_config_ref.artifact_id,
                role="input.feedback_config_ref",
            )
        )
    if final_override_bundle_ref is not None:
        feedback_base_inputs.append(
            InputRef(
                artifact_id=final_override_bundle_ref.artifact_id,
                role="feedback.parameter_override_bundle",
            )
        )
    feedback_base_state_ref = put_state_snapshot(
        store,
        state=final_injected_state,
        step=current_step,
        inputs=feedback_base_inputs,
    )
    feedback_base_state_snapshot_ref = StateSnapshotRef(
        artifact_id=feedback_base_state_ref.artifact_id
    )

    try:
        exec_artifacts = execute_program_graph(
            store,
            program_ref=exec_plan.program_ref,
            exec_plan_ref=request.exec_plan_ref,
            base_state=final_injected_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            step=current_step,
            seed=posture.seed,
            base_ref=feedback_base_state_snapshot_ref,
            capture_env=posture.capture_env,
            parameter_overrides=merged_final_overrides,
            parameter_override_bundle_ref=final_override_bundle_ref
            if final_override_bundle_ref is not None
            else request.parameter_override_bundle_ref,
            observed_range_bundle_ref=request.observed_range_bundle_ref,
            welfare_bound_mode=request.welfare_bound_mode,
        )
    except MissingRuntimeMechanismSupportError as exc:
        feedback_result_ref = _persist_feedback_result(
            store,
            request=request,
            prepared=prepared,
            exec_artifacts=None,
            initial_feedback_state=initial_feedback_state,
            final_feedback_state=solved_feedback_state,
            final_feedback_diagnostics={
                **outcome.final_diagnostics,
                "final_execution_failed": 1,
            },
            final_override_bundle_ref=final_override_bundle_ref,
            trace_ref=feedback_trace_ref,
            jacobian_ref=feedback_jacobian_ref,
            convergence_certificate_ref=feedback_certificate_ref,
            multiplicity_report_ref=multiplicity_report_ref,
            status="failed",
            converged=False,
            failure_reason=str(exc),
            alternative_solutions=outcome.alternative_solutions,
            notes=[
                "feedback_mode:fixed_point",
                "feedback_status:failed",
                *multiplicity_notes,
                f"missing_runtime_mechanism_support:{exc.mech_type}",
            ],
        )
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[
                *feedback_artifacts,
                DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
            ],
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                "feedback_status:failed",
                *multiplicity_notes,
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
        )

    derived_refs = _build_standard_derived_refs(exec_artifacts)
    welfare_bound_failure_notes = _evaluate_welfare_bound_requirement(
        store,
        request=request,
        derived_refs=derived_refs,
    )
    final_state, applied = apply_state_delta_and_snapshot(
        store,
        base_state=final_injected_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        step=current_step,
        base_ref=feedback_base_state_snapshot_ref,
    )
    final_metrics = _load_model(store, exec_artifacts.metrics_ref, Metrics)
    final_feedback_observed = extract_feedback_state(
        final_state,
        config=feedback_config,
        metrics=final_metrics.values,
    )
    final_feedback_diagnostics = extract_feedback_diagnostics(
        final_state,
        config=feedback_config,
        metrics=final_metrics.values,
    )
    if exec_artifacts.constraint_hard_fail:
        final_feedback_diagnostics["constraint_hard_fail"] = 1.0

    feedback_result_ref = _persist_feedback_result(
        store,
        request=request,
        prepared=prepared,
        exec_artifacts=exec_artifacts,
        initial_feedback_state=initial_feedback_state,
        final_feedback_state=final_feedback_observed,
        final_feedback_diagnostics=final_feedback_diagnostics,
        final_override_bundle_ref=final_override_bundle_ref,
        trace_ref=feedback_trace_ref,
        jacobian_ref=feedback_jacobian_ref,
        convergence_certificate_ref=feedback_certificate_ref,
        multiplicity_report_ref=multiplicity_report_ref,
        status=outcome.status,
        converged=outcome.converged,
        failure_reason=outcome.failure_reason,
        alternative_solutions=outcome.alternative_solutions,
        notes=[
            "feedback_mode:fixed_point",
            f"feedback_converged:{int(outcome.converged)}",
            f"feedback_status:{outcome.status}",
            *multiplicity_notes,
        ],
    )
    derived_refs.extend(
        [
            *feedback_artifacts,
            DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
        ]
    )

    if welfare_bound_failure_notes:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, "feedback_mode:fixed_point", *welfare_bound_failure_notes],
        )

    feedback_notes = [
        *execution_notes,
        "feedback_mode:fixed_point",
        f"feedback_iterations:{len(outcome.trace)}",
        f"feedback_status:{outcome.status}",
        *multiplicity_notes,
    ]
    sim_result = SimulationResult(
        exec_plan_ref=request.exec_plan_ref,
        metrics_ref=MetricsRef(artifact_id=exec_artifacts.metrics_ref.artifact_id),
        state_snapshot_ref=StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id),
        environment_ref=exec_artifacts.environment_ref,
        environment_fingerprint=(
            exec_artifacts.environment_fingerprint or posture.current_environment_fingerprint
        ),
        feedback_result_ref=feedback_result_ref,
        welfare_bound_refs=_extract_welfare_bound_refs(derived_refs),
        notes=feedback_notes,
    )
    sim_inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=exec_artifacts.metrics_ref.artifact_id, role="metrics"),
        InputRef(artifact_id=exec_artifacts.state_delta_ref.artifact_id, role="state_delta"),
        InputRef(artifact_id=applied.state_snapshot_ref.artifact_id, role="state_snapshot"),
        InputRef(
            artifact_id=feedback_base_state_snapshot_ref.artifact_id,
            role="input.feedback_base_state_snapshot_ref",
        ),
        InputRef(artifact_id=feedback_result_ref.artifact_id, role="artifact.feedback_result_ref"),
        InputRef(
            artifact_id=feedback_certificate_ref.artifact_id,
            role="artifact.feedback_convergence_certificate_ref",
        ),
    ]
    sim_inputs.extend(resolved_state.input_refs)
    sim_inputs.extend(parameter_override_inputs)
    if request.feedback_config_ref is not None:
        sim_inputs.append(
            InputRef(
                artifact_id=request.feedback_config_ref.artifact_id,
                role="input.feedback_config_ref",
            )
        )
    if final_override_bundle_ref is not None:
        sim_inputs.append(
            InputRef(
                artifact_id=final_override_bundle_ref.artifact_id,
                role="feedback.parameter_override_bundle",
            )
        )
    sim_result_ref = store.put_json(
        sim_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            inputs=sim_inputs,
        ),
    )

    if exec_artifacts.constraint_hard_fail:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*feedback_notes, "hard_constraint_violation"],
        )

    return ExecuteResult(
        ok=True,
        simulation_result_ref=SimulationResultRef(artifact_id=sim_result_ref.artifact_id),
        derived_refs=derived_refs,
        notes=feedback_notes,
    )


def _run_feedback_iteration(
    store: FileSystemCAS,
    *,
    exec_plan: ExecPlan,
    request: ExecuteRequest,
    registry_content: RegistryBundleContent,
    posture: ResolvedExecutionPosture,
    current_step: int,
    base_state: object,
    parameter_overrides: dict[str, dict[str, object]] | None,
    feedback_config: FeedbackConfig,
) -> _FeedbackExecutionEvaluation:
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
        base_ref=None,
        capture_env=False,
        parameter_overrides=parameter_overrides,
        parameter_override_bundle_ref=request.parameter_override_bundle_ref,
        observed_range_bundle_ref=request.observed_range_bundle_ref,
        welfare_bound_mode="off",
    )
    final_state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
    )
    metrics = _load_model(store, exec_artifacts.metrics_ref, Metrics)
    diagnostics = extract_feedback_diagnostics(
        final_state,
        config=feedback_config,
        metrics=metrics.values,
    )
    feedback_state = extract_feedback_state(
        final_state,
        config=feedback_config,
        metrics=metrics.values,
    )
    if exec_artifacts.constraint_hard_fail:
        diagnostics["constraint_hard_fail"] = 1.0
    budget_gap = None
    if feedback_config.solver.budget_diagnostic_id is not None:
        raw_budget_gap = diagnostics.get(feedback_config.solver.budget_diagnostic_id)
        if raw_budget_gap is not None:
            budget_gap = float(raw_budget_gap)
    noise_sd = None
    if diagnostics.get("noise_sd") is not None:
        noise_sd = float(diagnostics["noise_sd"])
    return _FeedbackExecutionEvaluation(
        map_evaluation=MapEvaluation(
            map_value=np.asarray(feedback_state.values, dtype=float),
            diagnostics=diagnostics,
            budget_gap=budget_gap,
            noise_sd=noise_sd,
        ),
        final_state=final_state,
    )


def _build_initial_feedback_state(
    base_state: object,
    feedback_config: FeedbackConfig,
) -> FeedbackStateSnapshot:
    values: list[float] = []
    for variable in feedback_config.variables:
        if variable.initial_value is not None:
            values.append(float(variable.initial_value))
            continue
        if variable.source_kind != "state_path":
            raise ValueError(
                f"Feedback variable '{variable.variable_id}' requires initial_value when "
                "source_kind is not 'state_path'"
            )
        single_config = FeedbackConfig(
            mode="fixed_point",
            variables=[variable],
            solver=feedback_config.solver,
            notes=feedback_config.notes,
        )
        extracted = extract_feedback_state(base_state, config=single_config, metrics={})
        values.append(float(extracted.values[0]))
    return FeedbackStateSnapshot(
        variable_ids=[variable.variable_id for variable in feedback_config.variables],
        values=values,
        scales=[
            float(variable.scale) if variable.scale is not None else 1.0
            for variable in feedback_config.variables
        ],
        lower_bounds=[variable.lower_bound for variable in feedback_config.variables],
        upper_bounds=[variable.upper_bound for variable in feedback_config.variables],
        weights=[float(variable.weight) for variable in feedback_config.variables],
        notes=["initial_feedback_state"],
    )


def _merge_parameter_overrides(
    base: dict[str, dict[str, object]] | None,
    extra: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, object]] | None:
    if not base and not extra:
        return None
    merged: dict[str, dict[str, object]] = {
        str(node_id): dict(values) for node_id, values in (base or {}).items()
    }
    for node_id, values in (extra or {}).items():
        merged.setdefault(str(node_id), {}).update(dict(values))
    return merged


def _persist_parameter_override_bundle(
    store: FileSystemCAS,
    *,
    request: ExecuteRequest,
    merged_overrides: dict[str, dict[str, object]] | None,
    feedback_notes: list[str],
) -> ParameterOverrideBundleRef | None:
    if not merged_overrides:
        return request.parameter_override_bundle_ref
    payload = ParameterOverrideBundle(
        overrides=merged_overrides,
        sources={str(node_id): ["feedback_solver"] for node_id in merged_overrides},
        notes=["merged_for_feedback_mode", *feedback_notes],
    )
    ref = store.put_json(
        payload,
        PutOptions(
            kind="foundry.parameter_override_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ParameterOverrideBundle", version="1.0"),
            inputs=(
                [
                    InputRef(
                        artifact_id=request.parameter_override_bundle_ref.artifact_id,
                        role="input.original_parameter_override_bundle_ref",
                    )
                ]
                if request.parameter_override_bundle_ref is not None
                else []
            )
            + (
                [
                    InputRef(
                        artifact_id=request.feedback_config_ref.artifact_id,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ParameterOverrideBundleRef(artifact_id=ref.artifact_id)


def _build_standard_derived_refs(exec_artifacts: ExecuteArtifacts) -> list[DerivedArtifact]:
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
    derived_refs.extend(
        DerivedArtifact(role=role, ref=ref) for role, ref in exec_artifacts.derived_artifacts
    )
    return derived_refs


def _extract_welfare_bound_refs(
    derived_refs: list[DerivedArtifact],
) -> dict[str, WelfareBoundReportRef] | None:
    refs: dict[str, WelfareBoundReportRef] = {}
    prefix = "welfare_bound_report:"
    for item in derived_refs:
        if not item.role.startswith(prefix):
            continue
        node_id = item.role[len(prefix) :].strip()
        if not node_id:
            continue
        refs[node_id] = WelfareBoundReportRef.model_validate(item.ref.model_dump())
    return refs or None


def _evaluate_welfare_bound_requirement(
    store: FileSystemCAS,
    *,
    request: ExecuteRequest,
    derived_refs: list[DerivedArtifact],
) -> list[str]:
    if not request.welfare_bound_required:
        return []
    if request.welfare_bound_mode not in {"ex_ante", "ex_post", "both"}:
        return [f"invalid_welfare_bound_mode:{request.welfare_bound_mode}"]
    report_refs = [
        item.ref for item in derived_refs if item.role.startswith("welfare_bound_report:")
    ]
    if not report_refs:
        return ["missing_required_welfare_bound_reports"]

    failures: list[str] = []
    for ref in report_refs:
        payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
        status = str(payload.get("status", "")).strip().lower()
        if status == "ok":
            continue
        node_id = str(payload.get("node_id") or "unknown")
        mechanism_type = str(payload.get("mechanism_type") or "unknown")
        failures.append(f"required_welfare_bound_failed:{mechanism_type}:{node_id}:{status}")
    return failures


def _persist_feedback_trace(
    store: FileSystemCAS,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
) -> FeedbackTraceRef:
    trace = FeedbackTrace(
        records=[
            FeedbackIterationRecord(
                stage_alpha=float(record.stage_alpha),
                iteration=int(record.iteration),
                residual_norm=float(record.residual_norm),
                step_norm=float(record.step_norm),
                damping=float(record.damping),
                method=record.method,
                accepted=bool(record.accepted),
                iterate=np.asarray(record.iterate, dtype=float).tolist(),
                residual=np.asarray(record.residual, dtype=float).tolist(),
                diagnostics=_sanitize_diagnostics(record.diagnostics),
                notes=list(record.notes),
            )
            for record in outcome.trace
        ],
        notes=["feedback_mode:fixed_point"],
    )
    ref = store.put_json(
        trace,
        PutOptions(
            kind="foundry.feedback_trace",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackTrace", version="1.0"),
            inputs=[
                InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
            ]
            + (
                [
                    InputRef(
                        artifact_id=request.feedback_config_ref.artifact_id,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackTraceRef(artifact_id=ref.artifact_id)


def _persist_feedback_jacobian(
    store: FileSystemCAS,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
    trace_ref: FeedbackTraceRef,
) -> FeedbackJacobianDiagnosticsRef | None:
    if outcome.jacobian is None:
        return None
    diagnostics = FeedbackJacobianDiagnostics(
        dimension=int(outcome.jacobian.matrix.shape[0]),
        jacobian=np.asarray(outcome.jacobian.matrix, dtype=float).tolist(),
        spectral_radius=outcome.jacobian.spectral_radius,
        operator_norm_inf=outcome.jacobian.operator_norm_inf,
        condition_number=outcome.jacobian.condition_number,
        smallest_singular_value_i_minus_j=(outcome.jacobian.smallest_singular_value_i_minus_j),
        near_fold=outcome.jacobian.near_fold,
        near_flip=outcome.jacobian.near_flip,
        near_loss_of_stability=outcome.jacobian.near_loss_of_stability,
        near_bifurcation=outcome.jacobian.near_bifurcation,
        notes=list(outcome.jacobian.notes),
    )
    ref = store.put_json(
        diagnostics,
        PutOptions(
            kind="foundry.feedback_jacobian_diagnostics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackJacobianDiagnostics", version="1.0"),
            inputs=[
                InputRef(artifact_id=trace_ref.artifact_id, role="artifact.feedback_trace_ref"),
            ]
            + (
                [
                    InputRef(
                        artifact_id=request.feedback_config_ref.artifact_id,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackJacobianDiagnosticsRef(artifact_id=ref.artifact_id)


def _persist_feedback_convergence_certificate(
    store: FileSystemCAS,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
    prepared: PreparedFeedbackConfig,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
) -> FeedbackConvergenceCertificateRef:
    final_record = outcome.trace[-1] if outcome.trace else None
    diagnostics = _sanitize_diagnostics(outcome.final_diagnostics)
    allowed_statuses = {
        "converged",
        "max_iter_exceeded",
        "restarts_exhausted",
        "diverged",
        "oscillating",
        "stagnated",
        "failed",
    }
    status = outcome.status if outcome.status in allowed_statuses else "failed"
    certificate = FeedbackConvergenceCertificate(
        status=status,
        converged=bool(outcome.converged),
        final_stage_alpha=float(final_record.stage_alpha) if final_record is not None else None,
        final_iteration=int(final_record.iteration) if final_record is not None else None,
        final_residual_norm=(
            None if outcome.final_residual_norm is None else float(outcome.final_residual_norm)
        ),
        final_step_norm=None if outcome.final_step_norm is None else float(outcome.final_step_norm),
        budget_gap=None if outcome.final_budget_gap is None else float(outcome.final_budget_gap),
        budget_tolerance=prepared.config.solver.budget_tolerance,
        multiple_fixed_points=bool(outcome.alternative_solutions)
        or bool(diagnostics.get("multiple_fixed_points", False)),
        oscillation_detected=bool(diagnostics.get("oscillation_detected", False)),
        divergence_detected=bool(diagnostics.get("divergence_detected", False)),
        stagnation_detected=bool(diagnostics.get("stagnation_detected", False)),
        near_bifurcation=bool(diagnostics.get("near_bifurcation", False)),
        notes=(
            ["feedback_mode:fixed_point"]
            + ([f"failure_reason:{outcome.failure_reason}"] if outcome.failure_reason else [])
        ),
    )
    inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=trace_ref.artifact_id, role="artifact.feedback_trace_ref"),
    ]
    if request.feedback_config_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=request.feedback_config_ref.artifact_id,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=jacobian_ref.artifact_id,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    ref = store.put_json(
        certificate,
        PutOptions(
            kind="foundry.feedback_convergence_certificate",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.FeedbackConvergenceCertificate",
                version="1.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackConvergenceCertificateRef(artifact_id=ref.artifact_id)


def _persist_equilibrium_multiplicity_report(
    store: FileSystemCAS,
    *,
    request: ExecuteRequest,
    report: EquilibriumMultiplicityReport,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
    convergence_certificate_ref: FeedbackConvergenceCertificateRef,
) -> EquilibriumMultiplicityReportRef:
    inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=trace_ref.artifact_id, role="artifact.feedback_trace_ref"),
        InputRef(
            artifact_id=convergence_certificate_ref.artifact_id,
            role="artifact.feedback_convergence_certificate_ref",
        ),
    ]
    if request.feedback_config_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=request.feedback_config_ref.artifact_id,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=jacobian_ref.artifact_id,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    ref = store.put_json(
        report,
        PutOptions(
            kind="foundry.equilibrium_multiplicity_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.EquilibriumMultiplicityReport",
                version="1.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EquilibriumMultiplicityReportRef(artifact_id=ref.artifact_id)


def _persist_feedback_result(
    store: FileSystemCAS,
    *,
    request: ExecuteRequest,
    prepared: PreparedFeedbackConfig,
    exec_artifacts: ExecuteArtifacts | None,
    initial_feedback_state: FeedbackStateSnapshot,
    final_feedback_state: FeedbackStateSnapshot,
    final_feedback_diagnostics: dict[str, object],
    final_override_bundle_ref: ParameterOverrideBundleRef | None,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
    convergence_certificate_ref: FeedbackConvergenceCertificateRef | None,
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None,
    status: str,
    converged: bool,
    failure_reason: str | None,
    alternative_solutions: tuple[AlternativeSolution, ...],
    notes: list[str],
) -> FeedbackResultRef:
    result = FeedbackSolveResult(
        status=status,
        converged=converged,
        initial_state=initial_feedback_state,
        final_state=final_feedback_state,
        trace_ref=trace_ref,
        jacobian_diagnostics_ref=jacobian_ref,
        convergence_certificate_ref=convergence_certificate_ref,
        final_parameter_override_bundle_ref=final_override_bundle_ref,
        multiplicity_report_ref=multiplicity_report_ref,
        alternative_fixed_points=[
            FeedbackFixedPointCandidate(
                state=snapshot_from_vector(
                    prepared,
                    np.asarray(candidate.solution, dtype=float),
                    notes=list(candidate.notes),
                ),
                residual_norm=(
                    None if candidate.residual_norm is None else float(candidate.residual_norm)
                ),
                diagnostics=_sanitize_diagnostics(candidate.diagnostics),
                notes=list(candidate.notes),
            )
            for candidate in alternative_solutions
        ],
        failure_reason=failure_reason,
        final_diagnostics=_sanitize_diagnostics(final_feedback_diagnostics),
        notes=notes,
    )
    inputs = [
        InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
        InputRef(artifact_id=trace_ref.artifact_id, role="artifact.feedback_trace_ref"),
    ]
    if exec_artifacts is not None:
        inputs.append(InputRef(artifact_id=exec_artifacts.metrics_ref.artifact_id, role="metrics"))
    if request.feedback_config_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=request.feedback_config_ref.artifact_id,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=jacobian_ref.artifact_id,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    if convergence_certificate_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=convergence_certificate_ref.artifact_id,
                role="artifact.feedback_convergence_certificate_ref",
            )
        )
    if final_override_bundle_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=final_override_bundle_ref.artifact_id,
                role="feedback.parameter_override_bundle",
            )
        )
    if multiplicity_report_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=multiplicity_report_ref.artifact_id,
                role="artifact.equilibrium_multiplicity_report_ref",
            )
        )
    ref = store.put_json(
        result,
        PutOptions(
            kind="foundry.feedback_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackSolveResult", version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackResultRef(artifact_id=ref.artifact_id)


def _sanitize_diagnostics(values: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in values.items():
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_sanitize_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    return str(value)
