"""Program-graph orchestrator — execute_program_graph and direct helpers."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

import jax
import jax.numpy as jnp
import numpy as np
from pydantic import TypeAdapter, ValidationError

from polisyos.core.artifacts.environment import (
    EnvironmentManifest,
    EnvironmentManifestRef,
    capture_environment,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ConstraintReport,
    ConstraintReportRef,
    ExecPlan,
    LoweredIR,
    Metrics,
    PatchOp,
    ProgramGraph,
    StateDelta,
)
from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.agent_sim.agents import AdaptiveAgentMechanism
from polisyos.foundry.execute._internal.models import (
    ExecuteArtifacts,
    ExecutionStrictness,
    FailureCard,
    FailureKind,
    FailureSeverity,
    artifact_id,
    get_state_path,
    load_model,
    load_payload,
    put_tensor,
)
from polisyos.foundry.execute._internal.ops import (
    apply_ops_to_state,
    coerce_number,
    evaluate_selector,
)
from polisyos.foundry.execute._internal.patching import apply_patch_map
from polisyos.foundry.execute.patch_vm import merge_patch_records
from polisyos.foundry.methods.backends.circuit_breaker import BackendCircuitOpenError
from polisyos.foundry.methods.backends.dispatch import BackendNotAvailableError
from polisyos.foundry.methods.exceptions import (
    BackendAdaptationError,
    ContractViolationError,
    FoundryExecutionError,
    MethodExecutionAbortError,
    ObservationBindingError,
    ProgramNodeValidationError,
    SelectorEvaluationError,
    ShapeMismatchError,
    StatePathTraversalError,
)
from polisyos.foundry.welfare.bounds import (
    load_observed_range_bundle,
    persist_welfare_bound_report,
    safe_compute_mechanism_welfare_bound_report,
)
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)

__all__ = [
    "execute_program_graph",
]

_SELECTOR_ADAPTER = TypeAdapter(SelectorExpr)
_MAX_FAILURE_CARDS = 256
_CLASSIFIED_EXECUTOR_FAILURES = (
    BackendAdaptationError,
    BackendCircuitOpenError,
    BackendNotAvailableError,
    ContractViolationError,
    FloatingPointError,
    FoundryExecutionError,
    ImportError,
    ModuleNotFoundError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValidationError,
    ValueError,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_program_graph(
    store: FileSystemCAS,
    *,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    base_state: Any,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    selector_field_registry: SelectorFieldRegistry | None = None,
    constraint_registry: ConstraintRegistry | None = None,
    step: int = 0,
    seed: int = 0,
    base_ref: ArtifactRef | None = None,
    project_root: str | None = None,
    capture_env: bool = False,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
    parameter_override_bundle_ref: ArtifactRef | None = None,
    observed_range_bundle_ref: ArtifactRef | None = None,
    welfare_bound_mode: str = "ex_ante",
    persist_welfare_bound_reports: bool = True,
    strictness: ExecutionStrictness = ExecutionStrictness.FAIL_CLOSED,
) -> ExecuteArtifacts:
    """Execute program graph."""
    env_manifest_ref: EnvironmentManifestRef | None = None
    env_fingerprint: str | None = None
    if capture_env:
        env_manifest = capture_environment(
            project_root=project_root,
            include_git=True,
            include_dependencies=True,
            custom_metadata={
                "seed": seed,
                "seed_source": "jax_prng",
                "exec_plan_id": str(artifact_id(exec_plan_ref)),
            },
        )
        env_manifest_ref = _persist_environment_manifest(store, env_manifest, exec_plan_ref)
        env_fingerprint = env_manifest.fingerprint
        _log_environment_captured(env_manifest)

    start_time = time.perf_counter()
    program_graph = load_model(store, program_ref, ProgramGraph)
    exec_plan = load_model(store, exec_plan_ref, ExecPlan)
    if program_graph.lowered_ir_ref is None:
        raise ValueError("program_graph_missing_lowered_ir_ref")
    lowered_ir = load_model(store, program_graph.lowered_ir_ref, LoweredIR)
    observed_ranges = None
    if persist_welfare_bound_reports and welfare_bound_mode != "off":
        observed_ranges = (
            load_observed_range_bundle(store, observed_range_bundle_ref)
            if observed_range_bundle_ref is not None
            else None
        )

    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}
    incoming_dependencies = _incoming_dependencies(program_graph)
    mask_barrier_targets = _mask_barrier_targets(program_graph)

    n_agents = getattr(base_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(base_state.firms.capital.shape[0])

    key = jax.random.PRNGKey(seed)
    tax_rate_value = _resolve_income_tax_rate(
        program_graph,
        store,
        step,
        parameter_overrides=parameter_overrides,
    )
    visible_state = base_state
    patch_records: dict[str, list[dict[str, Any]]] = {}
    ops: list[PatchOp] = []
    applied_nodes = 0
    skipped_nodes = 0
    failure_cards: list[FailureCard] = []
    failure_cards_dropped = 0
    provenance: dict[str, list[str]] = {}
    derived_artifacts: list[tuple[str, ArtifactRef]] = []
    touched_slots: set[str] = set()
    executed_mutating_nodes: set[str] = set()
    op_nodes = 0
    checked_constraints = 0
    masks: dict[str, tuple[jnp.ndarray, SlotScope]] = {}
    constraint_report = ConstraintReport(
        ok=True,
        hard_fail=False,
        constraint_mode=lowered_ir.constraint_mode,
        total_constraints=0,
        violations=[],
        penalty_total=None,
        notes=[],
    )

    def _flush_pending_records() -> None:
        nonlocal patch_records, visible_state
        if not patch_records:
            return
        touched_slots.update(patch_records.keys())
        base_values = {
            slot_id: get_state_path(visible_state, slot_spec.state_path)
            for slot_id in patch_records
            for slot_spec in [slot_registry.slots.get(slot_id)]
            if slot_spec is not None and slot_spec.state_path
        }
        merged_ops = merge_patch_records(
            store,
            patch_records,
            base_values=base_values,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )
        visible_state = apply_ops_to_state(
            store,
            base_state=visible_state,
            ops=merged_ops,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )
        patch_records = {}

    def _persist_welfare_report(node: Any, report: Any) -> None:
        if report is None or not persist_welfare_bound_reports:
            return
        report_inputs = [
            InputRef(artifact_id=artifact_id(exec_plan_ref), role="exec_plan"),
        ]
        if base_ref is not None:
            report_inputs.append(
                InputRef(artifact_id=base_ref.artifact_id, role="base_state_snapshot")
            )
        if node.params_ref is not None:
            report_inputs.append(
                InputRef(artifact_id=node.params_ref.artifact_id, role="mechanism_params")
            )
        if parameter_override_bundle_ref is not None:
            report_inputs.append(
                InputRef(
                    artifact_id=parameter_override_bundle_ref.artifact_id,
                    role="parameter_override_bundle",
                )
            )
        if observed_range_bundle_ref is not None:
            report_inputs.append(
                InputRef(
                    artifact_id=observed_range_bundle_ref.artifact_id,
                    role="observed_range_bundle",
                )
            )
        report_ref = persist_welfare_bound_report(store, report, inputs=report_inputs)
        derived_artifacts.append((f"welfare_bound_report:{node.node_id}", report_ref))

    for node_id in order:
        node = node_map.get(node_id)
        if node is None:
            card = _build_failure_card(
                ProgramNodeValidationError(
                    f"ExecPlan referenced unknown node '{node_id}'",
                    node_id=node_id,
                    code="unknown_exec_plan_node",
                ),
                node_id=node_id,
                slot_context=(),
            )
            failure_cards_dropped += _append_failure_card(failure_cards, card)
            if _should_abort(card, strictness):
                raise MethodExecutionAbortError(card)
            skipped_nodes += 1
            continue
        barrier_target = mask_barrier_targets.get(node_id, node_id)
        if patch_records and _depends_on_executed_mutation(
            barrier_target,
            incoming_dependencies=incoming_dependencies,
            executed_mutating_nodes=executed_mutating_nodes,
        ):
            _flush_pending_records()
        try:
            if node.node_kind == "op":
                op_nodes += 1
                if node.op is None:
                    raise ProgramNodeValidationError(
                        f"Program op node '{node_id}' is missing op payload",
                        node_id=node_id,
                        op_kind=None,
                        code="missing_program_op",
                    )
                if node.op.op_kind == "make_mask":
                    selector_payload = node.op.params.get("selector") or {}
                    target = _parse_selector_payload(selector_payload, node=node)
                    mask, scope = evaluate_selector(
                        target, visible_state, selector_field_registry=selector_field_registry
                    )
                    masks[node.node_id] = (mask, scope)
                    continue
                if node.op.op_kind == "apply_mechanism":
                    key, patch_map, payload, welfare_report = _execute_mechanism_like_node(
                        store,
                        node=node,
                        visible_state=visible_state,
                        selector_field_registry=selector_field_registry,
                        masks=masks,
                        step=step,
                        key=key,
                        n_agents=n_agents,
                        n_firms=n_firms,
                        mechanism_registry=mechanism_registry,
                        parameter_overrides=parameter_overrides,
                        observed_ranges=observed_ranges,
                        slot_registry=slot_registry,
                        merge_registry=merge_registry,
                        tax_rate_value=tax_rate_value,
                        welfare_bound_mode=welfare_bound_mode,
                    )
                    if patch_map is None:
                        skipped_nodes += 1
                        continue
                    _append_patch_map_records(
                        patch_records,
                        node=node,
                        payload=payload,
                        patch_map=patch_map,
                    )
                    _persist_welfare_report(node, welfare_report)
                    applied_nodes += 1
                    executed_mutating_nodes.add(node_id)
                    continue
                if node.op.op_kind == "merge_state":
                    _flush_pending_records()
                    continue
                if node.op.op_kind == "check_constraints":
                    ids = node.op.params.get("constraint_ids") or []
                    if constraint_registry is not None:
                        from polisyos.foundry.validation.constraints_engine import (
                            check_constraints as evaluate_lowered_constraints,
                        )

                        constraint_ids = [item for item in ids if isinstance(item, str)]
                        lowered_constraints = [
                            item
                            for item in lowered_ir.constraints
                            if item.constraint_id in constraint_ids
                        ]
                        checked_constraints += len(lowered_constraints)
                        constraint_report = evaluate_lowered_constraints(
                            constraints=lowered_constraints,
                            slot_registry=slot_registry,
                            state=visible_state,
                        )
                    continue
                raise ProgramNodeValidationError(
                    f"Unsupported program op '{node.op.op_kind}'",
                    node_id=node_id,
                    op_kind=node.op.op_kind,
                    code="unsupported_program_op",
                )
            if node.node_kind == "mechanism":
                key, patch_map, payload, welfare_report = _execute_mechanism_like_node(
                    store,
                    node=node,
                    visible_state=visible_state,
                    selector_field_registry=selector_field_registry,
                    masks=masks,
                    step=step,
                    key=key,
                    n_agents=n_agents,
                    n_firms=n_firms,
                    mechanism_registry=mechanism_registry,
                    parameter_overrides=parameter_overrides,
                    observed_ranges=observed_ranges,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                    tax_rate_value=tax_rate_value,
                    welfare_bound_mode=welfare_bound_mode,
                )
                if patch_map is None:
                    skipped_nodes += 1
                    continue
                _append_patch_map_records(
                    patch_records,
                    node=node,
                    payload=payload,
                    patch_map=patch_map,
                )
                _persist_welfare_report(node, welfare_report)
                applied_nodes += 1
                executed_mutating_nodes.add(node_id)
                continue
            if node.node_kind == "method":
                method_fqn = node.method_fqn
                if not method_fqn:
                    raise ProgramNodeValidationError(
                        f"Method node '{node_id}' is missing method_fqn",
                        node_id=node_id,
                        code="missing_method_fqn",
                    )
                from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
                from polisyos.foundry.methods.registry import MethodRegistry

                registry = MethodRegistry.get_instance()
                method_class = registry.get(method_fqn, version=node.method_version)
                signature = method_class.signature
                dispatcher = MethodDispatcher.get_instance()
                key, step_key = jax.random.split(key)
                method_result = dispatcher.dispatch(
                    method_class=method_class,
                    signature=signature,
                    state=visible_state,
                    params=node.method_params,
                    seed=_seed_from_key(step_key),
                )
                _append_method_patch_records(
                    patch_records,
                    provenance,
                    node=node,
                    output_payload=method_result.output,
                )
                applied_nodes += 1
                executed_mutating_nodes.add(node_id)
                continue
            raise ProgramNodeValidationError(
                f"Unsupported node kind '{node.node_kind}'",
                node_id=node_id,
                code="unsupported_node_kind",
            )
        except _CLASSIFIED_EXECUTOR_FAILURES as exc:
            card = _build_failure_card(
                exc,
                node=node,
                slot_context=tuple(node.inputs) + tuple(node.outputs),
            )
            failure_cards_dropped += _append_failure_card(failure_cards, card)
            logger.warning(
                "Program node '%s' failed [%s/%s]: %s",
                node_id,
                card.severity.value,
                card.failure_kind.value,
                card.error_message,
            )
            if _should_abort(card, strictness):
                raise MethodExecutionAbortError(card) from exc
            skipped_nodes += 1

    if patch_records:
        _flush_pending_records()

    ops = _build_state_delta_ops(
        store,
        base_state=base_state,
        final_state=visible_state,
        touched_slots=touched_slots,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    inputs = [
        InputRef(artifact_id=artifact_id(program_ref), role="program_graph"),
        InputRef(artifact_id=artifact_id(exec_plan_ref), role="exec_plan"),
    ]
    if program_graph.lowered_ir_ref is not None:
        inputs.append(
            InputRef(artifact_id=program_graph.lowered_ir_ref.artifact_id, role="lowered_ir")
        )
    if parameter_override_bundle_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=parameter_override_bundle_ref.artifact_id,
                role="parameter_override_bundle",
            )
        )
    for op in ops:
        if op.value_ref is not None:
            inputs.append(InputRef(artifact_id=op.value_ref.artifact_id, role="patch_value"))

    state_delta = StateDelta(base_ref=base_ref, ops=ops)
    state_delta_ref = store.put_json(
        state_delta,
        PutOptions(
            kind="foundry.state_delta",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateDelta", version="0.1.0"),
            inputs=inputs,
        ),
    )

    metrics = Metrics(
        values={
            "applied_nodes": int(applied_nodes),
            "skipped_nodes": int(skipped_nodes),
            "op_nodes": int(op_nodes),
            "checked_constraints": int(checked_constraints),
            "patch_ops": len(ops),
            "step": int(step),
            "step_latency_ms": latency_ms,
            "constraint_hard_fail": int(constraint_report.hard_fail),
            "failure_cards_recorded": len(failure_cards),
            "failure_cards_dropped": int(failure_cards_dropped),
        }
    )
    metrics_ref = store.put_json(
        metrics,
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="0.1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    constraint_report_ref = None
    if constraint_registry is not None or lowered_ir.constraints:
        cref = store.put_json(
            constraint_report,
            PutOptions(
                kind="foundry.constraint_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ConstraintReport", version="1.0"),
                inputs=inputs,
            ),
        )
        constraint_report_ref = ConstraintReportRef.model_validate(cref.model_dump())

    frozen_provenance = {k: tuple(v) for k, v in provenance.items()}
    degradation_cards = tuple(
        card for card in failure_cards if card.severity != FailureSeverity.FATAL
    )
    return ExecuteArtifacts(
        state_delta_ref=state_delta_ref,
        metrics_ref=metrics_ref,
        derived_artifacts=tuple(derived_artifacts),
        constraint_report_ref=constraint_report_ref,
        constraint_hard_fail=constraint_report.hard_fail,
        environment_ref=env_manifest_ref,
        environment_fingerprint=env_fingerprint,
        failure_cards=tuple(failure_cards),
        degradation_cards=degradation_cards,
        is_degraded=len(failure_cards) > 0,
        provenance=frozen_provenance,
    )


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def _classify_failure(exc: Exception) -> FailureSeverity:
    """Classify an exception into a failure severity level."""
    if isinstance(
        exc,
        (
            TypeError,
            ValueError,
            ShapeMismatchError,
            ContractViolationError,
            FoundryExecutionError,
            StatePathTraversalError,
            SelectorEvaluationError,
            ObservationBindingError,
        ),
    ):
        return FailureSeverity.FATAL
    if isinstance(exc, (ModuleNotFoundError, ImportError, TimeoutError)):
        return FailureSeverity.RECOVERABLE
    if isinstance(exc, FloatingPointError):
        return FailureSeverity.DEGRADED
    return FailureSeverity.FATAL


def _classify_failure_kind(exc: Exception) -> FailureKind:
    if isinstance(exc, (ContractViolationError, ShapeMismatchError)):
        return FailureKind.CONTRACT
    if isinstance(exc, StatePathTraversalError):
        return FailureKind.PATH
    if isinstance(exc, SelectorEvaluationError):
        return FailureKind.SELECTOR
    if isinstance(exc, ObservationBindingError):
        return FailureKind.ROUTING
    if type(exc).__name__ == "LifecycleTransitionError":
        return FailureKind.LIFECYCLE
    if isinstance(exc, BackendAdaptationError):
        return FailureKind.BACKEND
    if isinstance(exc, (FloatingPointError, RuntimeWarning)):
        return FailureKind.NUMERICAL
    if isinstance(exc, (ModuleNotFoundError, ImportError, TimeoutError)):
        return FailureKind.DEPENDENCY
    if isinstance(exc, (ProgramNodeValidationError, TypeError, ValueError, FoundryExecutionError)):
        return FailureKind.VALIDATION
    return FailureKind.INTERNAL


def _node_target_fqn(node: Any | None, *, node_id: str | None = None) -> str:
    if node is None:
        return f"executor.graph.{node_id or 'unknown'}@runtime"
    if getattr(node, "method_fqn", None):
        return str(node.method_fqn)
    if getattr(node, "mechanism_type", None):
        return f"mechanism.{node.mechanism_type}@runtime"
    if getattr(node, "op", None) is not None:
        return f"executor.op.{node.op.op_kind}@runtime"
    return f"executor.node.{getattr(node, 'node_id', node_id or 'unknown')}@runtime"


def _build_failure_card(
    exc: Exception,
    *,
    node: Any | None = None,
    node_id: str | None = None,
    slot_context: tuple[str, ...] = (),
) -> FailureCard:
    details = dict(getattr(exc, "details", {}) or {})
    resolved_node_id = (
        getattr(exc, "node_id", None) or getattr(node, "node_id", None) or node_id or "unknown"
    )
    resolved_method_fqn = getattr(exc, "method_fqn", None) or _node_target_fqn(
        node, node_id=resolved_node_id
    )
    resolved_mechanism_type = getattr(exc, "mechanism_type", None) or getattr(
        node, "mechanism_type", None
    )
    resolved_op_kind = getattr(exc, "op_kind", None) or (
        getattr(node.op, "op_kind", None)
        if node is not None and getattr(node, "op", None)
        else None
    )
    resolved_slot_context = tuple(slot_context)
    slot_id = getattr(exc, "slot_id", None)
    if slot_id is not None and slot_id not in resolved_slot_context:
        resolved_slot_context = resolved_slot_context + (str(slot_id),)
    if resolved_slot_context:
        details.setdefault("slot_context", list(resolved_slot_context))
    return FailureCard(
        node_id=str(resolved_node_id),
        method_fqn=str(resolved_method_fqn),
        severity=_classify_failure(exc),
        failure_kind=_classify_failure_kind(exc),
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback_hash=_hash_traceback(exc),
        timestamp=time.time(),
        retry_eligible=_classify_failure(exc) == FailureSeverity.RECOVERABLE,
        suggested_fallback="retry"
        if _classify_failure(exc) == FailureSeverity.RECOVERABLE
        else None,
        mechanism_type=resolved_mechanism_type,
        op_kind=resolved_op_kind,
        slot_context=resolved_slot_context,
        details=details,
    )


def _should_abort(card: FailureCard, strictness: ExecutionStrictness) -> bool:
    if strictness == ExecutionStrictness.FAIL_CLOSED:
        return True
    if strictness == ExecutionStrictness.DEGRADED:
        return card.severity == FailureSeverity.FATAL
    return False


def _parse_selector_payload(selector_payload: Any, *, node: Any) -> SelectorExpr:
    try:
        return _SELECTOR_ADAPTER.validate_python(selector_payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise SelectorEvaluationError(
            None,
            f"invalid selector payload for node '{node.node_id}': {exc}",
            value=selector_payload,
        ) from exc


def _append_patch_map_records(
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    node: Any,
    payload: dict[str, Any],
    patch_map: Any,
) -> None:
    if not isinstance(patch_map, dict):
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            "patch map must be a dict[str, list[dict]]",
        )
    expected_slots = {str(slot_id) for slot_id in getattr(node, "outputs", [])}
    unexpected_slots = set(map(str, patch_map.keys())) - expected_slots if expected_slots else set()
    if unexpected_slots:
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            f"unexpected patch outputs: {sorted(unexpected_slots)}",
        )
    for slot_id, patches in patch_map.items():
        patch_list = patches if isinstance(patches, list) else [patches]
        for patch in patch_list:
            if not isinstance(patch, dict):
                raise ContractViolationError(
                    _node_target_fqn(node),
                    "postcondition",
                    f"patch for slot '{slot_id}' must be a dict",
                )
            record = {
                "node_id": node.node_id,
                "priority": payload.get("priority"),
            }
            record.update(patch)
            patch_records.setdefault(str(slot_id), []).append(record)


def _append_method_patch_records(
    patch_records: dict[str, list[dict[str, Any]]],
    provenance: dict[str, list[str]],
    *,
    node: Any,
    output_payload: Any,
) -> None:
    method_fqn = str(node.method_fqn)
    if not isinstance(output_payload, dict):
        raise ContractViolationError(method_fqn, "postcondition", "method output must be a dict")
    patch_payload = output_payload.get("patch_records")
    if patch_payload is None:
        if getattr(node, "outputs", None):
            raise ContractViolationError(
                method_fqn,
                "postcondition",
                "declared outputs require patch_records in method output",
            )
        return
    if not isinstance(patch_payload, dict):
        raise ContractViolationError(
            method_fqn,
            "postcondition",
            "patch_records must be a dict[str, list[dict]]",
        )
    expected_slots = {str(slot_id) for slot_id in getattr(node, "outputs", [])}
    unexpected_slots = (
        set(map(str, patch_payload.keys())) - expected_slots if expected_slots else set()
    )
    if unexpected_slots:
        raise ContractViolationError(
            method_fqn,
            "postcondition",
            f"unexpected patch outputs: {sorted(unexpected_slots)}",
        )
    for slot_id, patches in patch_payload.items():
        if not isinstance(patches, list):
            raise ContractViolationError(
                method_fqn,
                "postcondition",
                f"patch_records['{slot_id}'] must be a list of patch dicts",
            )
        for patch in patches:
            if not isinstance(patch, dict):
                raise ContractViolationError(
                    method_fqn,
                    "postcondition",
                    f"patch for slot '{slot_id}' must be a dict",
                )
            materialized_patch = dict(patch)
            materialized_patch.setdefault("node_id", node.node_id)
            patch_records.setdefault(str(slot_id), []).append(materialized_patch)
            provenance.setdefault(str(slot_id), []).append(method_fqn)


def _hash_traceback(exc: Exception) -> str:
    """Produce a short hash of the traceback for deduplication."""
    import hashlib
    import traceback as tb_mod

    tb_str = "".join(tb_mod.format_exception(type(exc), exc, exc.__traceback__))
    return hashlib.sha256(tb_str.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _incoming_dependencies(program_graph: ProgramGraph) -> dict[str, tuple[str, ...]]:
    incoming: dict[str, list[str]] = {}
    for edge in program_graph.edges:
        incoming.setdefault(edge.dst, []).append(edge.src)
    return {node_id: tuple(sorted(srcs)) for node_id, srcs in incoming.items()}


def _mask_barrier_targets(program_graph: ProgramGraph) -> dict[str, str]:
    targets: dict[str, str] = {}
    for node in program_graph.nodes:
        if node.op is None or node.op.op_kind not in {"apply_mechanism", "apply_method"}:
            continue
        mask_id = node.op.params.get("mask_id")
        if isinstance(mask_id, str):
            targets[mask_id] = node.node_id
    return targets


def _depends_on_executed_mutation(
    node_id: str,
    *,
    incoming_dependencies: dict[str, tuple[str, ...]],
    executed_mutating_nodes: set[str],
) -> bool:
    return any(
        dependency in executed_mutating_nodes
        for dependency in incoming_dependencies.get(node_id, ())
    )


def _append_failure_card(failure_cards: list[FailureCard], card: FailureCard) -> int:
    if len(failure_cards) < _MAX_FAILURE_CARDS:
        failure_cards.append(card)
        return 0
    return 1


def _seed_from_key(key: jax.Array) -> int:
    key_words = np.asarray(jax.random.key_data(key), dtype=np.uint32).reshape(-1)
    acc = 0
    for word in key_words:
        acc = (acc * 1664525 + int(word) + 1013904223) % (2**31 - 1)
    return int(acc or 1)


def _execute_mechanism_like_node(
    store: FileSystemCAS,
    *,
    node: Any,
    visible_state: Any,
    selector_field_registry: SelectorFieldRegistry | None,
    masks: dict[str, tuple[jnp.ndarray, SlotScope]],
    step: int,
    key: jax.Array,
    n_agents: int,
    n_firms: int,
    mechanism_registry: MechanismTypeRegistry,
    parameter_overrides: dict[str, dict[str, Any]] | None,
    observed_ranges: Any | None,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    tax_rate_value: jnp.ndarray | None,
    welfare_bound_mode: str,
) -> tuple[jax.Array, dict[str, Any] | None, dict[str, Any], Any | None]:
    if node.params_ref is None:
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' is missing params_ref",
            node_id=node.node_id,
            mechanism_type=node.mechanism_type,
            op_kind=getattr(node.op, "op_kind", None),
            code="missing_params_ref",
        )
    payload = _load_node_payload(
        store,
        node=node,
        parameter_overrides=parameter_overrides,
    )
    schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
    start, end = schedule_range(schedule)
    if step < start or step > end:
        return key, None, payload, None

    mechanism_type = node.mechanism_type or payload.get("mechanism_id")
    if not isinstance(mechanism_type, str) or not mechanism_type.strip():
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' is missing mechanism_type",
            node_id=node.node_id,
            code="missing_mechanism_type",
        )
    mechanism_spec = mechanism_registry.mechanisms.get(mechanism_type)

    mask_info: tuple[jnp.ndarray, SlotScope] | None = None
    if node.node_kind == "op" and node.op is not None and node.op.op_kind == "apply_mechanism":
        mask_id = node.op.params.get("mask_id")
        if isinstance(mask_id, str):
            mask_info = masks.get(mask_id)
            if mask_info is None:
                raise ProgramNodeValidationError(
                    f"Node '{node.node_id}' referenced unresolved mask '{mask_id}'",
                    node_id=node.node_id,
                    mechanism_type=mechanism_type,
                    op_kind=node.op.op_kind,
                    code="missing_mask_dependency",
                )
        if mask_info is None:
            selector_payload = payload.get("selector") or payload.get("target")
            if selector_payload is None:
                raise ProgramNodeValidationError(
                    f"Node '{node.node_id}' is missing selector payload",
                    node_id=node.node_id,
                    mechanism_type=mechanism_type,
                    op_kind=node.op.op_kind,
                    code="missing_selector_payload",
                )
            target = _parse_selector_payload(selector_payload, node=node)
            mask_info = evaluate_selector(
                target, visible_state, selector_field_registry=selector_field_registry
            )

    params = payload.get("params", {})
    mechanism = create_mechanism_from_spec(
        mechanism_type,
        params,
        n_agents=n_agents,
        n_firms=n_firms,
        mechanism_spec=mechanism_spec,
        selected_fidelity=payload.get("selected_fidelity"),
    )
    if (
        tax_rate_value is not None
        and isinstance(mechanism, AdaptiveAgentMechanism)
        and (
            "global.tax_rate" in mechanism.observation_space
            or "policy.tax_rate" in mechanism.observation_space
        )
    ):
        mechanism = mechanism.with_runtime_overrides(tax_rate_value=tax_rate_value)

    key, step_key = jax.random.split(key)
    target_mask = None
    if mask_info is not None:
        mask, mask_scope = mask_info
        if mask_scope in {SlotScope.PER_AGENT, SlotScope.PER_FIRM}:
            target_mask = mask
    patch_map, key = mechanism.emit_patches(visible_state, step_key, target_mask=target_mask)
    if patch_map is None:
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            f"mechanism '{mechanism_type}' did not emit patches",
        )
    welfare_report = None
    state_after_error: str | None = None
    if welfare_bound_mode != "off":
        state_after = None
        if welfare_bound_mode in {"ex_post", "both"}:
            try:
                state_after = apply_patch_map(
                    visible_state,
                    patch_map,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                    default_node_id=node.node_id,
                    priority=payload.get("priority"),
                )
            except Exception as exc:  # pragma: no cover - defensive envelope
                state_after_error = f"{type(exc).__name__}: {exc}"
        welfare_report = safe_compute_mechanism_welfare_bound_report(
            mechanism_type,
            mechanism,
            visible_state,
            observed_ranges,
            state_after=state_after,
            node_id=node.node_id,
            target_mask=target_mask,
            mode=welfare_bound_mode,
        )
    if welfare_report is not None and state_after_error is not None:
        welfare_report = welfare_report.model_copy(
            update={
                "status": "warning",
                "notes": [
                    *welfare_report.notes,
                    f"state_after_reconstruction_failed:{state_after_error}",
                ],
            }
        )
    return key, patch_map, payload, welfare_report


def _build_state_delta_ops(
    store: FileSystemCAS,
    *,
    base_state: Any,
    final_state: Any,
    touched_slots: set[str],
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    ops: list[PatchOp] = []
    for slot_id in sorted(touched_slots):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        base_value = get_state_path(base_state, slot_spec.state_path)
        final_value = get_state_path(final_state, slot_spec.state_path)
        if rule.kind == MergeRuleKind.SUM:
            payload = jnp.asarray(final_value) - jnp.asarray(base_value)
            op_kind = "add"
        else:
            payload = jnp.asarray(final_value)
            op_kind = "set"
        value_ref = put_tensor(store, payload)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op_kind,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}", "source:visible_state_diff"],
            )
        )
    return ops


def _persist_environment_manifest(
    store: FileSystemCAS,
    manifest: EnvironmentManifest,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
) -> EnvironmentManifestRef:
    artifact_ref = store.put_json(
        manifest,
        PutOptions(
            kind="foundry.environment_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.artifacts.environment.EnvironmentManifest",
                version="1.0",
            ),
            inputs=[InputRef(artifact_id=artifact_id(exec_plan_ref), role="exec_plan")],
        ),
    )
    return EnvironmentManifestRef(artifact_id=artifact_ref.artifact_id)


def _log_environment_captured(manifest: EnvironmentManifest) -> None:
    from polisyos.common.logger import get_logger

    log = get_logger(__name__)
    log.info(
        "Environment captured",
        fingerprint=manifest.fingerprint,
        cpu_arch=manifest.cpu.architecture,
        jax_version=manifest.jax.jax_version,
        cuda_version=manifest.gpu.cuda_version,
        python_version=manifest.python.version,
        git_commit=manifest.git.commit_short if manifest.git else None,
    )


def _resolve_income_tax_rate(
    program_graph: ProgramGraph,
    store: FileSystemCAS,
    step: int,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
) -> jnp.ndarray | None:
    for node in program_graph.nodes:
        if node.mechanism_type != "income_tax" or node.params_ref is None:
            continue
        payload = _load_node_payload(
            store,
            node=node,
            parameter_overrides=parameter_overrides,
        )
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        if step < start or step > end:
            continue
        params = payload.get("params", {})
        numeric = coerce_number(params.get("rate"))
        if numeric is None:
            continue
        return jnp.array(float(numeric), dtype=jnp.float32)
    return None


def _load_node_payload(
    store: FileSystemCAS,
    *,
    node: Any,
    parameter_overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    payload = load_payload(store, node.params_ref)
    if not isinstance(payload, dict):
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' params payload must be a dict",
            node_id=node.node_id,
            mechanism_type=getattr(node, "mechanism_type", None),
            op_kind=getattr(node.op, "op_kind", None) if getattr(node, "op", None) else None,
            code="invalid_node_payload",
        )
    if not parameter_overrides:
        return payload
    node_overrides = parameter_overrides.get(str(node.node_id))
    if not isinstance(node_overrides, dict) or not node_overrides:
        return payload
    merged_payload = dict(payload)
    params = payload.get("params")
    merged_payload["params"] = {**(params if isinstance(params, dict) else {}), **node_overrides}
    return merged_payload
