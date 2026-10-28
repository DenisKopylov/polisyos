"""Compile Trinity policy bundles into CAS-backed Foundry execution plans.

This module owns the public `compile()` entrypoint used by Scientist runtime
nodes and tutorials. It accepts only `CompileRequest` payloads whose
`policy_ref.kind` points to an `ir.trinity_bundle`, resolves the Trinity
compiler backend deterministically, and persists a `CompileReport` failure
envelope when compilation cannot produce an executable plan.
"""

from __future__ import annotations

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.compiler.report import CompileReport, put_compile_report
from polisyos.core.contracts.execution_plan import ExecutionPlan
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
)
from polisyos.foundry._artifact_capabilities import resolve_core_json_profile_store
from polisyos.ir.kernel import ConstraintRegistry
from polisyos.ir.trinity import TrinityBundle


def compile(store: ArtifactStore, request: CompileRequest) -> CompileResult:
    """Compile a Trinity bundle into a Foundry execution plan.

    The current public surface accepts only Trinity-backed compile requests and
    returns a structured `CompileResult`. Successful compilation writes
    `foundry.program_graph`, `foundry.exec_plan`, `foundry.slot_layout`,
    `foundry.treasury_plan`, and a `CompileReport` artifact into CAS. Failures
    are converted into `CompileResult(ok=False, exec_plan_ref=None, ...)`
    envelopes with a persisted `compile_report_ref`.

    Compilation is expected to be deterministic for identical CAS inputs and
    compile flags. Requests with unsupported `policy_ref.kind` or
    `input_kind` do not raise to callers; they return a failure result whose
    report notes include the validation error.

    Args:
        store: Content-addressed artifact store that contains the Trinity
            bundle and optional registry bundle, and receives derived compile
            artifacts.
        request: Compile contract referencing the policy bundle, registry
            bundle, validation flags, and compile-time determinism settings.

    Returns:
        `CompileResult` with `ok=True` and `exec_plan_ref` on success, or
        `ok=False` plus `compile_report_ref` and explanatory `notes` on any
        compile failure.

    Example:
        ```python
        from polisyos.core.contracts.foundry import CompileRequest
        from polisyos.foundry import compile

        result = compile(store, CompileRequest(policy_ref=trinity_bundle_ref))
        if not result.ok:
            report = store.get_bytes(result.compile_report_ref.artifact_id)
        else:
            exec_plan_ref = result.exec_plan_ref
        ```
    """

    try:
        _resolve_compiler(request)
        core_json_store = resolve_core_json_profile_store(store)
        if core_json_store is None:
            raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
        from .trinity_compiler import compile_trinity

        return compile_trinity(core_json_store, request)
    except Exception as exc:
        return _compile_exception(store, request, exc)


def _resolve_compiler(request: CompileRequest) -> str:
    """Resolve the compiler backend for the Trinity-only Foundry pipeline.

    Raises:
        ValueError: If `request.policy_ref.kind` is not `ir.trinity_bundle` or
            `request.input_kind` is neither `trinity` nor `auto`.
    """
    kind = request.policy_ref.kind
    if kind != "ir.trinity_bundle":
        raise ValueError(
            f"Unsupported policy_ref.kind: {kind}. Only 'ir.trinity_bundle' is accepted."
        )
    if request.input_kind == "trinity":
        return "trinity"
    if request.input_kind == "auto":
        return "trinity"
    raise ValueError(f"Unsupported input_kind: {request.input_kind}")


def _compile_exception(
    store: ArtifactStore, request: CompileRequest, exc: Exception
) -> CompileResult:
    """Persist a compile failure report and return the corresponding envelope."""
    notes = [f"compile_exception:{type(exc).__name__}:{exc}"]
    compile_report = CompileReport(
        schema_version="1.0",
        ok=False,
        policy_ref=request.policy_ref,
        registry_bundle_ref=request.registry_bundle_ref,
        notes=notes,
    )
    inputs = [InputRef(artifact_id=request.policy_ref.artifact_id, role="ir")]
    if request.registry_bundle_ref is not None:
        inputs.append(
            InputRef(artifact_id=request.registry_bundle_ref.artifact_id, role="registry_bundle")
        )
    compile_report_ref = put_compile_report(store, compile_report, inputs=inputs)
    return CompileResult(
        schema_version="1.0",
        ok=False,
        exec_plan_ref=None,
        compile_report_ref=compile_report_ref,
        derived_refs=[],
        notes=notes,
    )


def replay_method_program_graph(
    *,
    policy: TrinityBundle,
    policy_ref: ArtifactRef,
    lowered_ir: LoweredIR,
    lowered_ir_ref: LoweredIRRef,
    method_plan: ExecutionPlan,
    constraint_registry: ConstraintRegistry,
) -> tuple[ProgramGraph, list[str]]:
    """Recompute the compiler's complete zero-mechanism method graph without CAS I/O.

    Callers own bounded content reads and exact selected-profile reconciliation.
    This facade validates the selected lowering against Trinity, then delegates
    graph construction and ordering to the same owners used by ``compile``.
    It grants no completed-source or metric authority.

    Args:
        policy: Content-read selected Trinity bundle.
        policy_ref: Exact selected reference for that bundle.
        lowered_ir: Content-read lowering from the selected compiler lineage.
        lowered_ir_ref: Exact selected reference for that lowering.
        method_plan: Content-read selected Scientist method plan.
        constraint_registry: Content-read selected registry constraint member.

    Returns:
        The complete canonical graph and its deterministic execution order.

    Raises:
        ValueError: If enabled mechanisms are outside this replay profile or
            the selected lowering disagrees with its Trinity source.
    """
    from ._graph import build_exec_order, build_program_graph
    from ._lowering import _lower_constraints, audit_trinity_field_coverage

    if any(item.enabled for item in policy.policy_spec.interventions) or lowered_ir.mechanisms:
        raise ValueError("method_graph_replay_mechanisms_unsupported")
    constraints, notes = _lower_constraints(policy.problem_frame, constraint_registry)
    expected_lowering = LoweredIR(
        schema_version="0.2",
        ir_ref=policy_ref,
        mechanisms=[],
        constraints=constraints,
        parameter_specs=[item.model_dump(mode="json") for item in policy.policy_spec.parameters],
        time_semantics=(
            policy.model_spec.time_semantics.model_dump(mode="json")
            if policy.model_spec.time_semantics is not None
            else None
        ),
        environment_config=(
            policy.model_spec.environment_config.model_dump(mode="json")
            if policy.model_spec.environment_config is not None
            else None
        ),
        policy_fidelity_level=policy.model_spec.fidelity_level.value,
        constraint_mode="hard_soft_v1",
        notes=sorted(set(audit_trinity_field_coverage(strict=True) + notes)),
    )
    if lowered_ir != expected_lowering:
        raise ValueError("method_graph_replay_lowering_mismatch")
    # Both mechanism inventories are established empty above: the shared builder
    # never enters its store-reading mechanism/slot-transfer branch in this profile.
    graph, _ = build_program_graph(
        None,
        ir_ref=policy_ref,
        lowered_ir_ref=lowered_ir_ref,
        mechanisms=lowered_ir.mechanisms,
        constraint_ids=[item.constraint_id for item in lowered_ir.constraints],
        method_plan=method_plan,
    )
    return graph, build_exec_order(graph)
