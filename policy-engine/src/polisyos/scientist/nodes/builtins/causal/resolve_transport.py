"""Public causal resolve transport module API."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import (
    profile_bound_ref,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.data_forge.read_api.catalog import (
    DatasetRegistry,
    PStarZResult,
    compose_confidence_harmonic,
    resolve_proxy,
    validate_proxy,
)
from polisyos.data_forge.read_api.legal import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.foundry.methods.catalog.causal.pag_member_family import (
    PAGMemberBudget,
    PAGMemberFamilyCoverage,
    PAGMemberFamilyStatus,
    PAGMemberWorkEstimateV1,
    PAGProposalDisposition,
    PAGWorkEstimateError,
    estimate_pag_member_work,
    evaluate_pag_member_family,
    pag_member_work_algorithm_identity,
    pag_member_work_estimate_sha256,
    pag_member_work_estimator_source_sha256,
)
from polisyos.foundry.methods.catalog.causal.transport_engine import (
    TransportCandidateMemberBindingError,
    evaluate_pag_member_candidate,
    solve_transportability,
)
from polisyos.foundry.methods.causal import (
    Y0_SURROGATE_DATA_PROFILE_ABSENT,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_capabilities import (
    CausalCapabilityContract,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
)
from polisyos.ir.analytics.transportability import (
    DataGap,
    SelectionDiagram,
    SNode,
    TransportabilityCandidateAttemptBindingV1,
    TransportabilityCandidateDiagnosticV1,
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidateModelPlanRelationV1,
    TransportabilityCandidatePhaseBudgetV1,
    TransportabilityCandidateProfileV1,
    TransportabilityCandidateProposalV1,
    TransportabilityCandidateReasonV1,
    TransportabilityCandidateRequestV1,
    TransportabilityCandidateResourceResolutionV1,
    TransportabilityCandidateSolverOutcomeV1,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
    load_transportability_result,
    persist_transportability_result,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.registry.refs import (
    CausalEffectReportRef,
    CausalGraphModelRef,
)
from polisyos.lex.api import evaluate_transport_constraints
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraint,
    LegalConstraintSet,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec
from polisyos.scientist.orchestration.workflows.causal_full import (
    CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
    causal_full_transport_resource_policy_snapshot,
)

from .transport_resolution_inputs import (
    InvalidTransportInput,
    _build_dataset_registry,
    _coerce_path,
    _LoopDatasetRegistry,
    _normalize_transport_solver_mode,
    _NullDatasetRegistry,
    _NullSKG,
    _parse_conditional_transport_request,
    _resolve_causal_graph_source,
    _resolve_context_profile,
    _resolve_context_year,
    _resolve_or_build_capability_contract,
    _resolve_query_outcome,
    _resolve_query_outcome_for_blocking,
    _resolve_query_treatment,
    _resolve_query_treatment_for_blocking,
    _resolve_transport_execution_inputs,
    _resolve_transport_privacy_context,
    _resolve_treatment_value,
    _transport_execution_profile,
)
from .transport_resolution_inputs import (
    build_skg_query as _build_skg_query_impl,
)
from .transport_resolution_results import (
    _build_adjacency,
    _build_blocking_transportability_result,
    _build_final_result,
    _build_infeasible_result,
    _build_proxy_quantity_or_gap,
    _finalize_transport_loop_result,
    _invalid_transport_input_outcome,
    _legal_constraints_to_s_nodes,
)

logger = get_logger(__name__)

_TRANSPORT_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_TRANSPORT_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_TRANSPORT_NUMERIC_PARSE_ERRORS = (TypeError, ValueError, OverflowError)

_CANDIDATE_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_CANDIDATE_OUTPUT_CANON = CanonSpec(forbid_floats=False)
_CANDIDATE_REQUEST_STATE_KEY = "conditional_transport_request"
_CANDIDATE_POLICY_SOURCE = "bounded_execution_policy"
_RESOLVED_GRAPH_PROFILE = ("transport.conditional.resolved_graph", "1")
_PAG_FAMILY_PROFILE = ("pag.no_selection.finite_member_sensitivity", "1")
_UNBOUND_NODE_TIMEOUT = object()


def _resolve_conditional_transport_resource_profile(
    request: TransportabilityCandidateRequestV1,
    *,
    actual_node_timeout_s: float | None | object = _UNBOUND_NODE_TIMEOUT,
    frozen_policy_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve candidate limits from the owner snapshot frozen in WorkflowSpec.

    A live candidate route supplies the exact static invocation parameter snapshot
    and deadline verified from the persisted attempt. Omitting the snapshot is
    reserved for metadata-only owner inspection and focused tests.
    """
    current_policy = causal_full_transport_resource_policy_snapshot()
    refusal: str | None = None
    if frozen_policy_snapshot is not None:
        if not isinstance(frozen_policy_snapshot, Mapping) or dict(frozen_policy_snapshot) != (
            current_policy
        ):
            refusal = "conditional_transport_resource_policy_snapshot_mismatch"
        else:
            current_policy = dict(frozen_policy_snapshot)

    profile_pairs = {
        (profile.get("profile_id"), profile.get("profile_revision"))
        for profile in current_policy.get("supported_profiles", [])
        if isinstance(profile, Mapping)
    }
    if refusal is None and (request.profile_id, request.profile_revision) not in profile_pairs:
        refusal = "conditional_transport_profile_unsupported"
    elif refusal is None and request.selection_identity != current_policy.get("selection_identity"):
        refusal = "conditional_transport_resource_selection_unsupported"

    raw_limits = current_policy.get("limits")
    raw_units = current_policy.get("limit_units")
    if not isinstance(raw_limits, Mapping) or not isinstance(raw_units, Mapping):
        refusal = refusal or "conditional_transport_resource_policy_invalid"
        limits: dict[str, int | float] = {}
        units: dict[str, str] = {}
    else:
        limits = dict(raw_limits)
        units = dict(raw_units)

    if refusal is None and actual_node_timeout_s is not _UNBOUND_NODE_TIMEOUT:
        if actual_node_timeout_s is None:
            refusal = "conditional_transport_node_timeout_not_configured"
        elif (
            isinstance(actual_node_timeout_s, bool)
            or not isinstance(actual_node_timeout_s, (int, float))
            or not math.isfinite(float(actual_node_timeout_s))
            or float(actual_node_timeout_s) <= 0.0
        ):
            refusal = "conditional_transport_node_timeout_invalid"
        elif float(actual_node_timeout_s) > float(limits["node_timeout_s"]):
            refusal = "conditional_transport_node_timeout_exceeds_owner_profile"
        elif float(actual_node_timeout_s) <= float(limits["max_elapsed_seconds"]):
            refusal = "conditional_transport_node_timeout_incompatible_with_phase_budget"
        else:
            limits["node_timeout_s"] = float(actual_node_timeout_s)

    snapshot: dict[str, Any] = {
        "schema_version": "1.1",
        "policy_id": current_policy.get("policy_id"),
        "policy_revision": current_policy.get("policy_revision"),
        "profile_id": request.profile_id,
        "profile_revision": request.profile_revision,
        "selection_identity": request.selection_identity,
        "status": "refused" if refusal else "selected",
        "reason_code": refusal,
        "effective_limits": None if refusal else limits,
        "effective_limit_units": None if refusal else units,
    }
    canonical = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    snapshot["sha256"] = hashlib.sha256(canonical).hexdigest()
    return snapshot


def _candidate_sha256(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANDIDATE_CANON)).hexdigest()


def _candidate_input_ref(ref: Any, role: str) -> InputRef:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("conditional_transport_input_ref_missing_selected_profile")
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _candidate_missing_input_outcome(
    state: ExperimentState,
    required_input: str,
) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code=node_errors.ERROR_MISSING_INPUT,
            message=f"Conditional transport candidate requires {required_input}.",
            details={
                "request_key": _CANDIDATE_REQUEST_STATE_KEY,
                "required_input": required_input,
            },
        ),
    )


@dataclass(frozen=True)
class _ConditionalCandidateAttempt:
    """Exact selected engine basis accepted for one explicitly requested candidate."""

    attempt_binding: TransportabilityCandidateAttemptBindingV1
    workflow_params: dict[str, Any]
    input_state: ExperimentState
    identity: Any
    hard_deadline_s: float | None
    effective_worker_timeout_s: float
    supervisor_deadline_monotonic: float


def _bind_conditional_candidate_attempt(
    *,
    ctx: ExecutionContext,
    current_state: ExperimentState,
    request: TransportabilityCandidateRequestV1,
    node: RunTransportabilityNode,
) -> _ConditionalCandidateAttempt:
    """Recompute the live engine-owned request, node identity and input-state binding."""
    binding = ctx._engine_invocation
    if not isinstance(binding, _EngineInvocationBinding):
        raise ValueError("conditional_transport_candidate_requires_engine_attempt")
    if (
        binding.run_id != ctx.run.run_manifest.run_id
        or current_state.run_id != binding.run_id
        or binding.basis_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("conditional_transport_candidate_engine_owner_mismatch")
    attempts = ctx.run.read_runtime_invocation_attempts()
    matches = [
        item
        for item in attempts
        if item.basis.attempt_id == binding.attempt_id and item.basis_ref == binding.basis_ref
    ]
    if len(matches) != 1:
        raise ValueError("conditional_transport_candidate_attempt_not_uniquely_owner_linked")
    attempt = matches[0]
    basis = attempt.basis
    if basis.run_id != binding.run_id:
        raise ValueError("conditional_transport_candidate_attempt_run_id_mismatch")
    if basis.node_alias != "run_transportability":
        raise ValueError("conditional_transport_candidate_attempt_alias_mismatch")
    if basis.component_id != str(_SPEC.metadata.component_id):
        raise ValueError("conditional_transport_candidate_attempt_component_mismatch")
    if attempt.outcome is not None:
        raise ValueError("conditional_transport_candidate_attempt_already_finished")
    if basis.implementation_identity is None:
        raise ValueError("conditional_transport_candidate_attempt_identity_missing")
    if not all(
        ref.manifest_profile_sha256 is not None and ctx.store.verify(ref).ok
        for ref in (binding.basis_ref, basis.workflow_spec_ref, basis.input_state_ref)
    ):
        raise ValueError("conditional_transport_candidate_attempt_refs_not_verified")
    from polisyos.scientist.orchestration.engine.component_identity import (
        matches_spawned_timeout_worker_component_identity,
    )

    workflow_manifest = ctx.store.get_manifest(basis.workflow_spec_ref)
    if (
        workflow_manifest.kind != "scientist.workflow_spec"
        or workflow_manifest.artifact_schema is None
        or workflow_manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.WorkflowSpec"
        or workflow_manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("conditional_transport_candidate_workflow_spec_contract_invalid")
    workflow = WorkflowSpec.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(basis.workflow_spec_ref))
    )
    selected_nodes = [item for item in workflow.nodes if item.alias == basis.node_alias]
    if len(selected_nodes) != 1 or str(selected_nodes[0].node_id) != basis.component_id:
        raise ValueError("conditional_transport_candidate_workflow_node_mismatch")
    selected_node = selected_nodes[0]
    params = dict(selected_node.params)
    if (
        "conditional_transport_request" in params
        or "transportability_candidate_request" in params
        or "transportability_candidate_resource_profile" in params
    ):
        raise ValueError("conditional_transport_candidate_workflow_static_binding_mismatch")
    if CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM not in params:
        raise ValueError("conditional_transport_resource_policy_snapshot_missing")
    if params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM] != (
        causal_full_transport_resource_policy_snapshot()
    ):
        raise ValueError("conditional_transport_resource_policy_snapshot_mismatch")
    basis_state = _load_engine_owned_invocation_input_state(ctx, current_state)
    if basis_state is None:
        raise ValueError("conditional_transport_candidate_input_state_not_owner_linked")
    if _CANDIDATE_REQUEST_STATE_KEY not in basis_state.params:
        raise ValueError("conditional_transport_candidate_frozen_request_missing")
    frozen_request = _parse_conditional_transport_request(
        basis_state.params[_CANDIDATE_REQUEST_STATE_KEY]
    )
    if (
        frozen_request != request
        or current_state.params.get(_CANDIDATE_REQUEST_STATE_KEY)
        != basis_state.params[_CANDIDATE_REQUEST_STATE_KEY]
    ):
        raise ValueError("conditional_transport_candidate_frozen_input_state_mismatch")
    identity = basis.implementation_identity
    if (
        identity.dispatch_params_sha256 != _candidate_sha256(params)
        or identity.bound_state_sha256 != _candidate_sha256(vars(node))
        or not matches_spawned_timeout_worker_component_identity(
            ctx,
            identity,
            basis.component_id,
            "run_transportability",
            params,
        )
    ):
        raise ValueError("conditional_transport_candidate_implementation_identity_mismatch")
    attempt_binding = TransportabilityCandidateAttemptBindingV1(
        run_id=basis.run_id,
        attempt_id=basis.attempt_id,
        attempt_number=basis.attempt_number,
        node_alias=basis.node_alias,
        component_id=basis.component_id,
        started_at=basis.started_at,
        dispatch_params_sha256=identity.dispatch_params_sha256,
        workflow_spec_ref=_candidate_input_ref(
            basis.workflow_spec_ref, "transportability_workflow_spec"
        ),
        input_state_ref=_candidate_input_ref(basis.input_state_ref, "transportability_input_state"),
        basis_ref=_candidate_input_ref(binding.basis_ref, "transportability_attempt_basis"),
    )
    return _ConditionalCandidateAttempt(
        attempt_binding=attempt_binding,
        workflow_params=params,
        input_state=basis_state,
        identity=identity,
        hard_deadline_s=selected_node.timeout_s,
        effective_worker_timeout_s=binding.effective_timeout_s,
        supervisor_deadline_monotonic=binding.supervisor_deadline_monotonic,
    )


def _candidate_measure(resource: str, value: int | float, unit: str) -> dict[str, Any]:
    return {"resource": resource, "value": float(value), "unit": unit}


def _candidate_owned_measure(
    resource: str,
    value: int | float,
    resource_resolution: TransportabilityCandidateResourceResolutionV1,
) -> dict[str, Any]:
    """Use the exact unit declared by the trusted resource-profile owner."""
    units = resource_resolution.effective_limit_units
    if units is None or resource not in units:
        raise ValueError("conditional_transport_candidate_resource_unit_not_owner_resolved")
    return _candidate_measure(resource, value, units[resource])


def _candidate_budget_phase(
    *,
    phase: str,
    selection_identity: str,
    admission: str,
    resource_resolution: TransportabilityCandidateResourceResolutionV1 | None = None,
    limits: tuple[dict[str, Any], ...] = (),
    consumed: tuple[dict[str, Any], ...] = (),
    termination: str,
    reason: TransportabilityCandidateReasonV1 | None = None,
    elapsed_seconds: float | None = None,
) -> TransportabilityCandidatePhaseBudgetV1:
    if admission == "not_required":
        return TransportabilityCandidatePhaseBudgetV1(
            phase=phase,
            selection_identity=selection_identity,
            admission="not_required",
            admission_source="not_required",
            termination="not_required",
        )
    if admission == "admitted":
        if resource_resolution is None or resource_resolution.status != "selected":
            raise ValueError("conditional_transport_candidate_budget_owner_not_selected")
        return TransportabilityCandidatePhaseBudgetV1(
            phase=phase,
            selection_identity=selection_identity,
            admission="admitted",
            admission_source=_CANDIDATE_POLICY_SOURCE,
            admission_policy_id=(
                f"{resource_resolution.policy_id}@{resource_resolution.policy_revision}"
            ),
            effective_limits=tuple(limits),
            consumed=tuple(consumed),
            termination=termination,
            reason=reason,
            elapsed_seconds=elapsed_seconds,
        )
    return TransportabilityCandidatePhaseBudgetV1(
        phase=phase,
        selection_identity=selection_identity,
        admission="refused",
        admission_source="owner_refusal",
        termination="not_started",
        reason=reason
        or TransportabilityCandidateReasonV1(
            code="candidate_budget_not_admitted",
            detail="The existing bounded resource owner did not admit this phase.",
        ),
    )


def _candidate_measure_diagnostic_output(
    diagnostic: TransportabilityCandidateDiagnosticV1,
    *,
    resource_resolution: TransportabilityCandidateResourceResolutionV1,
    recorded_size: int | None = None,
) -> tuple[TransportabilityCandidateDiagnosticV1, int]:
    """Record either the exact retained size or a measured over-budget attempt."""
    observed_size = 0 if recorded_size is None else recorded_size
    for _ in range(32):
        payload = diagnostic.model_dump(mode="json")
        budget_payload = payload["evaluation_budget"]
        consumed = [
            item
            for item in budget_payload["consumed"]
            if item["resource"] != "max_diagnostic_bytes"
        ]
        if budget_payload["admission"] == "admitted":
            consumed.append(
                _candidate_owned_measure(
                    "max_diagnostic_bytes",
                    observed_size,
                    resource_resolution,
                )
            )
        budget_payload["consumed"] = consumed
        payload["evaluation_budget"] = budget_payload
        current = TransportabilityCandidateDiagnosticV1.model_validate(payload)
        encoded_size = len(
            to_canonical_bytes(current.model_dump(mode="json"), _CANDIDATE_OUTPUT_CANON)
        )
        if recorded_size is not None:
            return current, encoded_size
        if encoded_size == observed_size:
            return current, encoded_size
        observed_size = encoded_size
    raise ValueError("conditional_transport_candidate_output_measure_did_not_converge")


def _candidate_persisted_result_bytes(result: TransportabilityResult) -> bytes:
    return to_canonical_bytes(
        result.model_dump(mode="json"),
        CanonSpec(forbid_floats=False),
    )


def _require_candidate_transport_result_within_output_budget(
    result: TransportabilityResult,
) -> None:
    """Refuse persistence when the complete typed result exceeds its owner byte cap."""
    diagnostic = result.candidate_diagnostics
    if diagnostic is None:
        return
    limits = diagnostic.resource_resolution.effective_limits
    limit = int(
        limits["max_diagnostic_bytes"]
        if limits is not None
        else causal_full_transport_resource_policy_snapshot()["limits"]["max_diagnostic_bytes"]
    )
    serialized_size = len(_candidate_persisted_result_bytes(result))
    if serialized_size > limit:
        raise InvalidTransportInput(
            "conditional_transport_candidate_complete_result_exceeds_output_budget:"
            f"{serialized_size}>{limit}"
        )


def _candidate_context_digest(context: ContextProfile) -> str:
    return _candidate_sha256(context.model_dump(mode="json"))


def _candidate_solver_revision() -> str:
    source = inspect.getsourcefile(solve_transportability)
    if source is None:
        raise ValueError("conditional_transport_candidate_solver_source_not_established")
    return "sha256:" + hashlib.sha256(Path(source).read_bytes()).hexdigest()


def _candidate_worker_deadline_evidence(
    attempt: _ConditionalCandidateAttempt,
    *,
    phase_limit: float,
) -> tuple[dict[str, float | str] | None, str | None]:
    """Record the actual worker window and decide if it contains the full phase."""
    timeout_s = attempt.effective_worker_timeout_s
    deadline = attempt.supervisor_deadline_monotonic
    now = time.monotonic()
    remaining = deadline - now
    if (
        type(timeout_s) is not float
        or type(deadline) is not float
        or not math.isfinite(timeout_s)
        or not math.isfinite(deadline)
        or not math.isfinite(remaining)
    ):
        return None, "conditional_transport_candidate_worker_deadline_insufficient"
    evidence: dict[str, float | str] = {
        "effective_worker_timeout_s": timeout_s,
        "effective_worker_timeout_s_hex": timeout_s.hex(),
        "supervisor_deadline_monotonic_hex": deadline.hex(),
        "supervisor_deadline_remaining_seconds": remaining,
        "supervisor_deadline_remaining_seconds_hex": remaining.hex(),
    }
    if timeout_s <= phase_limit or remaining <= phase_limit:
        return evidence, "conditional_transport_candidate_worker_deadline_insufficient"
    return evidence, None


def _build_candidate_worker_deadline_refusal_diagnostic(
    *,
    request: TransportabilityCandidateRequestV1,
    attempt: _ConditionalCandidateAttempt,
    inputs: TransportabilityCandidateInputBindingV1,
    graph: CausalGraphModel,
    resource_profile: Mapping[str, Any],
    resource_resolution: TransportabilityCandidateResourceResolutionV1,
    reason: TransportabilityCandidateReasonV1,
    worker_deadline_evidence: Mapping[str, float | str] | None,
) -> TransportabilityCandidateDiagnosticV1:
    """Refuse selected candidate work before either PAG generation or DAG/ADMG solving."""
    limits = resource_resolution.effective_limits
    if limits is None:
        raise ValueError("conditional_transport_candidate_deadline_refusal_requires_owner_limits")
    now = datetime.now(UTC)
    is_pag = graph.graph_type is GraphType.PAG
    assignment_space_size, unattempted_proposals = _candidate_unattempted_pag_partition(
        graph,
        max_diagnostic_bytes=int(limits["max_diagnostic_bytes"]),
    )
    return TransportabilityCandidateDiagnosticV1(
        candidate_request=request,
        effective_profile=TransportabilityCandidateProfileV1(
            profile_id=request.profile_id,
            profile_revision=request.profile_revision,
        ),
        resource_resolution=resource_resolution,
        disposition="unsupported",
        reason=reason,
        attempt=attempt.attempt_binding,
        inputs=inputs,
        graph_provenance="unknown",
        algorithm_id=(
            "polisyos.pag_member_family+transport_engine.solve_transportability"
            if is_pag
            else "polisyos.transport_engine.solve_transportability"
        ),
        algorithm_revision=request.profile_revision,
        implementation_revision=_candidate_solver_revision(),
        backend_id="not_established",
        backend_revision="not_established",
        parameters={
            "resource_profile_policy_id": resource_profile["policy_id"],
            "resource_profile_policy_revision": resource_profile["policy_revision"],
            "resource_profile_sha256": resource_profile["sha256"],
            "verified_node_hard_deadline_s": attempt.hard_deadline_s,
            "phase_budget_seconds": float(limits["max_elapsed_seconds"]),
            "worker_deadline_evidence": dict(worker_deadline_evidence or {}),
        },
        assumptions=(
            "The selected worker window must contain the full phase budget before candidate work starts.",
            "The unverified legal source relation and legal effects remain excluded from this candidate calculation.",
        ),
        unresolved_predicates=(
            "operative_legal_relation_verification",
            "candidate_worker_deadline_admission",
            "graph_real_world_truth_and_currentness",
        ),
        generation_budget=_candidate_budget_phase(
            phase="generation",
            selection_identity=request.selection_identity,
            admission="refused" if is_pag else "not_required",
            reason=reason,
            termination="not_started",
        ),
        evaluation_budget=_candidate_budget_phase(
            phase="evaluation",
            selection_identity=request.selection_identity,
            admission="refused",
            reason=reason,
            termination="not_started",
        ),
        assignment_space_size=assignment_space_size,
        unattempted_proposals=unattempted_proposals,
        generation_coverage="not_established",
        evaluated_at=now,
    )


def _candidate_exact_power_of_two_decimal(exponent: int, *, max_digits: int) -> str:
    """Format exact assignment cardinality without Python's global int-string limit."""
    if exponent < 0:
        raise ValueError("conditional_transport_candidate_assignment_exponent_invalid")
    upper_digits = math.floor(exponent * math.log10(2)) + 2
    if upper_digits > max_digits:
        raise ValueError(
            "conditional_transport_candidate_assignment_count_exceeds_diagnostic_budget"
        )
    number = 1 << exponent
    digits = math.floor(exponent * math.log10(2)) + 1
    while number >= 10**digits:
        digits += 1
    while digits > 1 and number < 10 ** (digits - 1):
        digits -= 1

    def encode(value: int, width: int) -> str:
        if width <= 9:
            return str(value).zfill(width)
        low_width = width // 2
        divisor = 10**low_width
        high, low = divmod(value, divisor)
        return encode(high, width - low_width) + encode(low, low_width)

    return encode(number, digits)


def _candidate_unattempted_pag_partition(
    graph: CausalGraphModel,
    *,
    max_diagnostic_bytes: int,
) -> tuple[str | None, str | None]:
    # Reconcile a refused PAG request as zero attempted assignments.
    if graph.graph_type is not GraphType.PAG:
        return None, None
    exponent = sum(
        int(edge.mark_src is EdgeMark.CIRCLE) + int(edge.mark_dst is EdgeMark.CIRCLE)
        for edge in graph.edges
    )
    total = _candidate_exact_power_of_two_decimal(
        exponent,
        max_digits=max(1, max_diagnostic_bytes - 2048),
    )
    return total, total


def _build_pag_preflight_refusal_diagnostic(
    *,
    request: TransportabilityCandidateRequestV1,
    attempt: _ConditionalCandidateAttempt,
    inputs: TransportabilityCandidateInputBindingV1,
    graph: CausalGraphModel,
    resource_profile: Mapping[str, Any],
    resource_resolution: TransportabilityCandidateResourceResolutionV1,
    reason: TransportabilityCandidateReasonV1,
    estimator_snapshot: Mapping[str, Any] | None,
    work_estimate: PAGMemberWorkEstimateV1 | None,
    worker_deadline_evidence: Mapping[str, float | str] | None,
) -> TransportabilityCandidateDiagnosticV1:
    """Persist a typed pre-generation refusal with exact finite-assignment accounting."""
    limits = resource_resolution.effective_limits
    if limits is None:
        raise ValueError("conditional_transport_candidate_preflight_requires_owner_limits")
    assignment_space_size, unattempted_proposals = _candidate_unattempted_pag_partition(
        graph,
        max_diagnostic_bytes=int(limits["max_diagnostic_bytes"]),
    )
    if work_estimate is not None and assignment_space_size != _candidate_exact_power_of_two_decimal(
        work_estimate.assignment_space.exponent,
        max_digits=max(1, int(limits["max_diagnostic_bytes"]) - 2048),
    ):
        raise ValueError("conditional_transport_candidate_assignment_estimate_mismatch")
    identity = (
        estimator_snapshot.get("algorithm_identity") if estimator_snapshot is not None else None
    )
    identity_map = identity if isinstance(identity, Mapping) else {}
    backend_id = str(identity_map.get("algorithm_id") or "not_established")
    backend_revision = (
        f"causal-learn:{identity_map.get('causal_learn_version', 'unknown')};"
        f"networkx:{identity_map.get('networkx_version', 'unknown')}"
    )[:120]
    estimator_source = (
        estimator_snapshot.get("estimator_source_sha256")
        if estimator_snapshot is not None
        else None
    )
    implementation_basis = f"{estimator_source or 'not_established'}:{_candidate_solver_revision()}"
    implementation_revision = (
        "sha256:" + hashlib.sha256(implementation_basis.encode("utf-8")).hexdigest()
    )
    parameters: dict[str, Any] = {
        "resource_profile_policy_id": resource_profile["policy_id"],
        "resource_profile_policy_revision": resource_profile["policy_revision"],
        "resource_profile_sha256": resource_profile["sha256"],
        "verified_node_hard_deadline_s": attempt.hard_deadline_s,
        "work_estimator_policy_snapshot": dict(estimator_snapshot or {}),
        "worker_deadline_evidence": dict(worker_deadline_evidence or {}),
        "preflight_refusal_code": reason.code,
    }
    if work_estimate is not None:
        parameters["work_estimate"] = work_estimate.model_dump(mode="json")
        parameters["work_estimate_sha256"] = pag_member_work_estimate_sha256(work_estimate)
    now = datetime.now(UTC)
    return TransportabilityCandidateDiagnosticV1(
        candidate_request=request,
        effective_profile=TransportabilityCandidateProfileV1(
            profile_id=request.profile_id,
            profile_revision=request.profile_revision,
        ),
        resource_resolution=resource_resolution,
        disposition="unsupported",
        reason=reason,
        attempt=attempt.attempt_binding,
        inputs=inputs,
        graph_provenance="unknown",
        algorithm_id="polisyos.pag_member_family+transport_engine.solve_transportability",
        algorithm_revision=request.profile_revision,
        implementation_revision=implementation_revision,
        backend_id=backend_id,
        backend_revision=backend_revision,
        parameters=parameters,
        assumptions=(
            "The preflight work estimate is a graph-derived upper bound, not a calibrated CPU-time prediction.",
            "The unverified legal source relation and legal effects remain excluded from this candidate calculation.",
        ),
        unresolved_predicates=(
            "operative_legal_relation_verification",
            "graph_real_world_truth_and_currentness",
            "candidate_resource_preflight_admission",
        ),
        generation_budget=_candidate_budget_phase(
            phase="generation",
            selection_identity=request.selection_identity,
            admission="refused",
            reason=reason,
            termination="not_started",
        ),
        evaluation_budget=_candidate_budget_phase(
            phase="evaluation",
            selection_identity=request.selection_identity,
            admission="refused",
            reason=reason,
            termination="not_started",
        ),
        assignment_space_size=assignment_space_size,
        unattempted_proposals=unattempted_proposals,
        generation_coverage="not_established",
        evaluated_at=now,
    )


def _validate_pag_member_family_owner_completion(family: Any) -> None:
    """Reconcile producer rows before owner code can claim finite completion.

    This check is intentionally independent of the producer DTO validator. The owner consumes
    the producer result as untrusted candidate data and must not promote incomplete or shifted
    ordinal accounting into a completed or zero-admitted diagnostic.
    """
    counts = family.counts
    proposals = tuple(family.proposals)
    members = tuple(family.members)
    attempted = counts.proposals_attempted
    error_code = "conditional_transport_candidate_pag_producer_completion_binding_mismatch"
    if type(attempted) is not int or attempted < 0 or len(proposals) != attempted:
        raise ValueError(error_code)
    if any(type(row.ordinal) is not int for row in proposals):
        raise ValueError(error_code)
    if tuple(row.ordinal for row in proposals) != tuple(range(attempted)):
        raise ValueError(error_code)

    disposition_counts = dict.fromkeys(PAGProposalDisposition, 0)
    admitted_links: dict[int, tuple[str, str]] = {}
    for row in proposals:
        if not isinstance(row.disposition, PAGProposalDisposition):
            raise ValueError(error_code)
        disposition_counts[row.disposition] += 1
        if row.disposition is PAGProposalDisposition.ADMITTED:
            if row.member_sha256 is None:
                raise ValueError(error_code)
            admitted_links[row.ordinal] = (row.assignment_sha256, row.member_sha256)
    for disposition, actual_count in disposition_counts.items():
        stored_count = getattr(counts, disposition.value, None)
        if type(stored_count) is not int or stored_count != actual_count:
            raise ValueError(error_code)

    if len(members) != counts.admitted:
        raise ValueError(error_code)
    member_links: dict[int, tuple[str, str]] = {}
    for member in members:
        if member.proposal_ordinal in member_links:
            raise ValueError(error_code)
        member_links[member.proposal_ordinal] = (
            member.assignment_sha256,
            member.member_sha256,
        )
    if member_links != admitted_links:
        raise ValueError(error_code)

    incomplete_count = disposition_counts[PAGProposalDisposition.VALIDATION_INCOMPLETE]
    if not isinstance(family.status, PAGMemberFamilyStatus):
        raise ValueError(error_code)
    if incomplete_count and family.status is not PAGMemberFamilyStatus.VALIDATION_INCOMPLETE:
        raise ValueError(error_code)
    if family.status is PAGMemberFamilyStatus.VALIDATION_INCOMPLETE and not incomplete_count:
        raise ValueError(error_code)

    if family.status not in {
        PAGMemberFamilyStatus.COMPLETED,
        PAGMemberFamilyStatus.NOT_ESTABLISHED,
    }:
        return
    exhausted = counts.unattempted_proposals == "0" and counts.assignment_space_size == str(
        attempted
    )
    if incomplete_count or counts.validation_incomplete != 0 or not exhausted:
        raise ValueError(error_code)
    if family.status is PAGMemberFamilyStatus.COMPLETED:
        if (
            family.coverage is not PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
            or counts.admitted == 0
            or not members
        ):
            raise ValueError(error_code)
        return
    if (
        family.coverage is not PAGMemberFamilyCoverage.NOT_ESTABLISHED
        or family.reason_code != "zero_admitted_members_not_established"
        or counts.admitted != 0
        or members
    ):
        raise ValueError(error_code)


def _conditional_transport_pag_member_diagnostic(
    *,
    ctx: ExecutionContext,
    request: TransportabilityCandidateRequestV1,
    attempt: _ConditionalCandidateAttempt,
    graph_ref: Any,
    graph: CausalGraphModel,
    source_context: ContextProfile,
    target_context: ContextProfile,
    inputs: TransportabilityCandidateInputBindingV1,
    query_treatment: str,
    query_outcome: str,
    query_sha256: str,
    solver_mode: str,
    allow_degraded_transport: bool,
    capability_contract: CausalCapabilityContract,
    privacy_context: TransportPrivacyContext | None,
    resource_profile: Mapping[str, Any],
    resource_resolution: TransportabilityCandidateResourceResolutionV1,
) -> TransportabilityCandidateDiagnosticV1:
    """Evaluate PAG members in order while retaining a canonical source prefix."""
    limits_raw = resource_profile.get("effective_limits")
    if not isinstance(limits_raw, Mapping):
        raise ValueError("conditional_transport_candidate_limits_not_owner_resolved")
    owner_limits = resource_resolution.effective_limits
    if (
        resource_resolution.status != "selected"
        or owner_limits is None
        or dict(limits_raw) != dict(owner_limits)
    ):
        raise ValueError("conditional_transport_candidate_limits_changed")
    diagnostic_limit = int(limits_raw["max_diagnostic_bytes"])
    phase_limit = float(limits_raw["max_elapsed_seconds"])
    family_budget = PAGMemberBudget(
        max_proposals=int(limits_raw["max_proposals"]),
        max_members=int(limits_raw["max_members"]),
        max_oracle_operations=int(limits_raw["max_oracle_operations"]),
        max_elapsed_seconds=phase_limit,
        max_output_bytes=int(limits_raw["max_output_bytes"]),
    )
    frozen_policy = attempt.workflow_params.get(CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM)
    estimator_snapshot_raw = (
        frozen_policy.get("work_estimator") if isinstance(frozen_policy, Mapping) else None
    )
    estimator_snapshot = (
        estimator_snapshot_raw if isinstance(estimator_snapshot_raw, Mapping) else None
    )
    worker_deadline_evidence, deadline_refusal = _candidate_worker_deadline_evidence(
        attempt,
        phase_limit=phase_limit,
    )
    preflight_reason: TransportabilityCandidateReasonV1 | None = None
    work_estimate: PAGMemberWorkEstimateV1 | None = None
    if deadline_refusal is not None:
        preflight_reason = TransportabilityCandidateReasonV1(
            code=deadline_refusal,
            detail="The verified worker deadline no longer contains the full bounded generation phase.",
        )
    elif estimator_snapshot is None or estimator_snapshot.get("status") != "available":
        preflight_reason = TransportabilityCandidateReasonV1(
            code=(
                str(estimator_snapshot.get("reason_code"))
                if estimator_snapshot is not None
                else "conditional_transport_candidate_work_estimator_snapshot_missing"
            ),
            detail="The pre-dispatch owner snapshot does not establish a pinned PAG work estimator.",
        )
    else:
        try:
            current_identity = pag_member_work_algorithm_identity()
            current_estimator_sha256 = pag_member_work_estimator_source_sha256()
        except PAGWorkEstimateError as exc:
            preflight_reason = TransportabilityCandidateReasonV1(
                code=exc.code,
                detail="The pinned FCI, CIT, FAS, NetworkX, or adapter identity is unavailable.",
            )
        else:
            frozen_identity = estimator_snapshot.get("algorithm_identity")
            frozen_estimator_sha256 = estimator_snapshot.get("estimator_source_sha256")
            if (
                not isinstance(frozen_identity, Mapping)
                or current_identity.model_dump(mode="json") != dict(frozen_identity)
                or current_estimator_sha256 != frozen_estimator_sha256
            ):
                preflight_reason = TransportabilityCandidateReasonV1(
                    code="conditional_transport_candidate_work_estimator_snapshot_mismatch",
                    detail="Current method/backend identity differs from the pre-dispatch frozen owner snapshot.",
                )
            else:
                try:
                    work_estimate = estimate_pag_member_work(
                        graph,
                        budget=family_budget,
                        max_estimated_dsep_queries=int(limits_raw["max_estimated_dsep_queries"]),
                        max_estimated_expanded_graph_element_query_units=int(
                            limits_raw["max_expanded_graph_element_query_units"]
                        ),
                        profile_id=request.profile_id,
                        profile_revision=request.profile_revision,
                    )
                except PAGWorkEstimateError as exc:
                    preflight_reason = TransportabilityCandidateReasonV1(
                        code=exc.code,
                        detail="The method-owned PAG work estimate could not establish the pinned bounded work basis.",
                    )
    if preflight_reason is None and work_estimate is not None:
        estimate_identity = work_estimate.algorithm_identity.model_dump(mode="json")
        if (
            work_estimate.graph_sha256 != inputs.graph_sha256
            or estimate_identity != dict(estimator_snapshot["algorithm_identity"])
            or work_estimate.estimator_source_sha256
            != estimator_snapshot["estimator_source_sha256"]
            or work_estimate.profile_id != request.profile_id
            or work_estimate.profile_revision != request.profile_revision
            or work_estimate.max_estimated_dsep_queries
            != int(limits_raw["max_estimated_dsep_queries"])
            or work_estimate.max_estimated_expanded_graph_element_query_units
            != int(limits_raw["max_expanded_graph_element_query_units"])
        ):
            preflight_reason = TransportabilityCandidateReasonV1(
                code="conditional_transport_candidate_work_estimate_binding_mismatch",
                detail="The estimate does not match the selected graph, profile, policy limits, or frozen implementation identity.",
            )
        elif (
            work_estimate.d_separation_query_bound.exceeded_ceiling
            or work_estimate.expanded_graph_element_query_bound.exceeded_ceiling
        ):
            preflight_reason = TransportabilityCandidateReasonV1(
                code="conditional_transport_candidate_work_estimate_exceeds_owner_limits",
                detail="A graph-derived work upper bound exceeds its separately versioned owner limit.",
            )
    if preflight_reason is None:
        worker_deadline_evidence, deadline_refusal = _candidate_worker_deadline_evidence(
            attempt,
            phase_limit=phase_limit,
        )
        if deadline_refusal is not None:
            preflight_reason = TransportabilityCandidateReasonV1(
                code=deadline_refusal,
                detail="The verified worker deadline no longer contains the full bounded generation phase.",
            )
    if preflight_reason is not None:
        return _build_pag_preflight_refusal_diagnostic(
            request=request,
            attempt=attempt,
            inputs=inputs,
            graph=graph,
            resource_profile=resource_profile,
            resource_resolution=resource_resolution,
            reason=preflight_reason,
            estimator_snapshot=estimator_snapshot,
            work_estimate=work_estimate,
            worker_deadline_evidence=worker_deadline_evidence,
        )
    if work_estimate is None or worker_deadline_evidence is None:
        raise ValueError("conditional_transport_candidate_work_preflight_not_established")
    work_estimate_sha256 = pag_member_work_estimate_sha256(work_estimate)
    work_estimate_raw = work_estimate.model_dump(mode="json")
    family = evaluate_pag_member_family(
        graph,
        profile_id=request.profile_id,
        profile_revision=request.profile_revision,
        budget=family_budget,
    )

    _validate_pag_member_family_owner_completion(family)
    if (
        family.profile_id != request.profile_id
        or family.profile_revision != request.profile_revision
        or family.source_graph_sha256 != inputs.graph_sha256
        or family.budget != family_budget
        or family.counts.proposals_attempted != len(family.proposals)
        or family.counts.admitted != len(family.members)
    ):
        raise ValueError("conditional_transport_candidate_pag_producer_binding_mismatch")
    for row in family.members:
        if (
            row.graph.graph_type not in {GraphType.DAG, GraphType.ADMG}
            or graph_content_sha256(row.graph) != row.member_sha256
        ):
            raise ValueError("conditional_transport_candidate_pag_member_content_mismatch")

    proposal_rows = tuple(
        TransportabilityCandidateProposalV1(
            ordinal=row.ordinal,
            assignment_sha256=row.assignment_sha256,
            disposition=row.disposition.value,
            member_sha256=row.member_sha256,
            duplicate_of=row.duplicate_of,
            reason=(
                TransportabilityCandidateReasonV1(
                    code=row.reason_code or "pag_member_rejected",
                    detail=f"Finite PAG member producer disposition: {row.reason_code}.",
                )
                if row.disposition
                in {
                    PAGProposalDisposition.INVALID,
                    PAGProposalDisposition.UNSUPPORTED,
                    PAGProposalDisposition.VALIDATION_INCOMPLETE,
                }
                else None
            ),
        )
        for row in family.proposals
    )
    generation_resources = (
        "max_proposals",
        "max_members",
        "max_oracle_operations",
        "max_elapsed_seconds",
        "max_output_bytes",
        "max_estimated_dsep_queries",
        "max_expanded_graph_element_query_units",
    )
    generation_limits = tuple(
        _candidate_owned_measure(resource, float(limits_raw[resource]), resource_resolution)
        for resource in generation_resources
    )
    generation_consumed = tuple(
        _candidate_owned_measure(resource, float(value), resource_resolution)
        for resource, value in (
            ("max_proposals", family.counts.proposals_attempted),
            ("max_members", family.counts.admitted),
            ("max_oracle_operations", family.counts.oracle_operations),
            ("max_elapsed_seconds", family.elapsed_seconds),
            ("max_output_bytes", family.trace_bytes),
            (
                "max_estimated_dsep_queries",
                work_estimate.d_separation_query_bound.value,
            ),
            (
                "max_expanded_graph_element_query_units",
                work_estimate.expanded_graph_element_query_bound.value,
            ),
        )
    )
    generation_termination = {
        PAGMemberFamilyStatus.COMPLETED: "completed",
        PAGMemberFamilyStatus.NOT_ESTABLISHED: "completed",
        PAGMemberFamilyStatus.UNSUPPORTED: "unsupported",
        PAGMemberFamilyStatus.BUDGET_EXHAUSTED: "budget_exhausted",
        PAGMemberFamilyStatus.VALIDATION_INCOMPLETE: "error",
    }[family.status]
    if (
        family.elapsed_seconds > phase_limit
        or family.trace_bytes > int(limits_raw["max_output_bytes"])
        or family.counts.proposals_attempted > int(limits_raw["max_proposals"])
        or family.counts.admitted > int(limits_raw["max_members"])
        or family.counts.oracle_operations > int(limits_raw["max_oracle_operations"])
    ):
        generation_termination = "budget_exhausted"
    generation_reason = (
        None
        if generation_termination == "completed"
        else TransportabilityCandidateReasonV1(
            code=family.reason_code or f"pag_member_generation_{generation_termination}",
            detail=(
                "The bounded producer did not establish complete finite endpoint-assignment coverage; "
                "recorded rows and measured resource use remain available."
            ),
        )
    )
    generation_budget = _candidate_budget_phase(
        phase="generation",
        selection_identity=request.selection_identity,
        admission="admitted",
        resource_resolution=resource_resolution,
        limits=generation_limits,
        consumed=generation_consumed,
        termination=generation_termination,
        reason=generation_reason,
        elapsed_seconds=family.elapsed_seconds,
    )

    evaluation_started = time.monotonic()
    ir_store = _ensure_ir_artifact_store(ctx.store)
    member_graph_refs: dict[str, CausalGraphModelRef] = {}
    persisted_member_graphs: dict[str, CausalGraphModel] = {}
    for member in family.members:
        member_ref = persist_causal_graph_model(
            ir_store,
            member.graph,
            inputs=[_candidate_input_ref(graph_ref, "pag_member_of")],
            return_selected_profile=True,
        )
        if member_ref.manifest_profile_sha256 is None:
            raise ValueError("conditional_transport_candidate_member_graph_profile_missing")
        if not ctx.store.verify(member_ref).ok:
            raise ValueError("conditional_transport_candidate_member_graph_not_verified")
        persisted_member = load_causal_graph_model(ir_store, member_ref)
        if graph_content_sha256(persisted_member) != member.member_sha256:
            raise ValueError(
                "conditional_transport_candidate_member_graph_content_binding_mismatch"
            )
        member_graph_refs[member.member_sha256] = member_ref
        persisted_member_graphs[member.member_sha256] = persisted_member

    evaluation_resources = (
        "max_evaluations",
        "max_elapsed_seconds",
        "max_diagnostic_bytes",
    )
    evaluation_limits = tuple(
        _candidate_owned_measure(resource, float(limits_raw[resource]), resource_resolution)
        for resource in evaluation_resources
    )
    evaluation_admitted = bool(family.members)
    producer_backend = family.backend_identity
    if producer_backend is not None:
        backend_id = producer_backend.backend_id
        backend_revision = producer_backend.backend_version
        producer_backend_identity = producer_backend.model_dump(mode="json")
    else:
        backend_id = "not_established"
        backend_revision = "not_established"
        producer_backend_identity = None
    producer_source = inspect.getsourcefile(evaluate_pag_member_family)
    if producer_source is None:
        raise ValueError("conditional_transport_candidate_pag_implementation_not_established")
    producer_sha = hashlib.sha256(Path(producer_source).read_bytes()).hexdigest()
    solver_revision = _candidate_solver_revision()
    implementation_sha = hashlib.sha256(f"{producer_sha}:{solver_revision}".encode()).hexdigest()
    params_base = {
        "resource_profile_policy_id": resource_profile["policy_id"],
        "resource_profile_policy_revision": resource_profile["policy_revision"],
        "resource_profile_sha256": resource_profile["sha256"],
        "verified_node_hard_deadline_s": attempt.hard_deadline_s,
        "worker_deadline_evidence": dict(worker_deadline_evidence),
        "work_estimator_policy_snapshot": dict(estimator_snapshot),
        "work_estimate": work_estimate_raw,
        "work_estimate_sha256": work_estimate_sha256,
        "work_estimate_kind": "graph_derived_upper_bound_not_cpu_time_calibration",
        "effective_resource_limits": dict(limits_raw),
        "producer_status": family.status.value,
        "producer_coverage": family.coverage.value,
        "producer_deadline_scope": family.deadline_scope,
        "producer_elapsed_seconds": family.elapsed_seconds,
        "producer_trace_bytes": family.trace_bytes,
        "producer_trace_sha256": family.trace_sha256,
        "producer_counts": family.counts.model_dump(mode="json"),
        "producer_backend_identity": producer_backend_identity,
        "solver_mode": solver_mode,
        "allow_degraded_transport": allow_degraded_transport,
        "capability_contract_fingerprint": capability_contract.dependency_fingerprint,
        "evaluation_accounting_scope": "retained_completed_source_bound_outcomes_only",
        "evaluation_source_member_count": len(family.members),
    }

    now = datetime.now(UTC)
    evaluation_admitted = bool(family.members)
    not_started_reason = TransportabilityCandidateReasonV1(
        code="candidate_member_evaluation_not_started",
        detail="This admitted member follows the last started member in canonical producer order.",
    )

    def not_started_row(member: Any, reason: TransportabilityCandidateReasonV1):
        return TransportabilityCandidateMemberEvaluationV1(
            member_sha256=member.member_sha256,
            member_graph_ref=member_graph_refs[member.member_sha256],
            disposition="not_started",
            reason=reason,
        )

    def build_diagnostic(
        rows: list[TransportabilityCandidateMemberEvaluationV1],
        *,
        attempted_count: int,
        termination: str,
        phase_reason: TransportabilityCandidateReasonV1 | None,
        elapsed: float,
    ) -> TransportabilityCandidateDiagnosticV1:
        retained_count = sum(row.disposition == "completed" for row in rows)
        not_started_count = sum(row.disposition == "not_started" for row in rows)
        params = {
            **params_base,
            "evaluation_attempted_member_count": attempted_count,
            "evaluation_completed_retained_member_count": retained_count,
            "evaluation_not_started_member_count": not_started_count,
            "identified_member_fraction_denominator": retained_count,
        }
        if evaluation_admitted:
            evaluation_budget = _candidate_budget_phase(
                phase="evaluation",
                selection_identity=request.selection_identity,
                admission="admitted",
                resource_resolution=resource_resolution,
                limits=evaluation_limits,
                consumed=(
                    _candidate_owned_measure(
                        "max_evaluations", attempted_count, resource_resolution
                    ),
                    _candidate_owned_measure("max_elapsed_seconds", elapsed, resource_resolution),
                    _candidate_owned_measure("max_diagnostic_bytes", 0, resource_resolution),
                ),
                termination=termination,
                reason=phase_reason,
                elapsed_seconds=elapsed,
            )
        else:
            evaluation_budget = _candidate_budget_phase(
                phase="evaluation",
                selection_identity=request.selection_identity,
                admission="not_required",
                termination="not_required",
            )
        proposal_ordinals_exact = tuple(row.ordinal for row in family.proposals) == tuple(
            range(family.counts.proposals_attempted)
        )
        no_validation_incomplete_proposals = family.counts.validation_incomplete == 0 and all(
            row.disposition is not PAGProposalDisposition.VALIDATION_INCOMPLETE
            for row in family.proposals
        )
        exact_exhausted_proposal_partition = (
            proposal_ordinals_exact
            and family.counts.unattempted_proposals == "0"
            and family.counts.assignment_space_size == str(family.counts.proposals_attempted)
        )
        exact_generation_coverage = (
            family.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
            and family.status is PAGMemberFamilyStatus.COMPLETED
            and generation_termination == "completed"
            and no_validation_incomplete_proposals
            and exact_exhausted_proposal_partition
        )
        all_completed = (
            len(rows) == len(family.members)
            and bool(family.members)
            and all(row.disposition == "completed" for row in rows)
        )
        complete = all_completed and termination == "completed" and exact_generation_coverage
        zero_admitted_not_established = (
            family.status is PAGMemberFamilyStatus.NOT_ESTABLISHED
            and family.coverage is PAGMemberFamilyCoverage.NOT_ESTABLISHED
            and family.reason_code == "zero_admitted_members_not_established"
            and family.counts.proposals_attempted == len(family.proposals)
            and no_validation_incomplete_proposals
            and exact_exhausted_proposal_partition
            and family.counts.admitted == 0
            and not family.members
            and not rows
        )
        diagnostic_reason = (
            None
            if complete
            else TransportabilityCandidateReasonV1(
                code="zero_admitted_members_not_established",
                detail=(
                    "The producer exhausted the selected assignment family but admitted no members; "
                    "there is no solver denominator or identified fraction."
                ),
            )
            if zero_admitted_not_established
            else phase_reason
            or generation_reason
            or TransportabilityCandidateReasonV1(
                code=(family.reason_code or "pag_member_evaluation_incomplete"),
                detail=(
                    "The recorded rows cover only retained completed source-bound outcomes; "
                    "they do not establish a probability or result for the whole PAG class."
                ),
            )
        )
        if zero_admitted_not_established:
            disposition = "partial"
        elif (
            not family.proposals and not rows and family.status is PAGMemberFamilyStatus.UNSUPPORTED
        ):
            disposition = "unsupported"
        elif not family.proposals and not rows:
            disposition = "error"
            diagnostic_reason = diagnostic_reason or TransportabilityCandidateReasonV1(
                code="pag_member_generation_produced_no_attempt_evidence",
                detail="The producer returned no proposal or member rows to support a candidate result.",
            )
        else:
            disposition = "completed" if complete else "partial"
        return TransportabilityCandidateDiagnosticV1(
            candidate_request=request,
            effective_profile=TransportabilityCandidateProfileV1(
                profile_id=request.profile_id,
                profile_revision=request.profile_revision,
            ),
            resource_resolution=resource_resolution,
            disposition=disposition,
            reason=diagnostic_reason,
            attempt=attempt.attempt_binding,
            inputs=inputs,
            graph_provenance="unknown",
            algorithm_id="polisyos.pag_member_family+transport_engine.solve_transportability",
            algorithm_revision=request.profile_revision,
            implementation_revision=f"sha256:{implementation_sha}",
            backend_id=backend_id,
            backend_revision=backend_revision,
            parameters=params,
            assumptions=(
                *family.assumptions,
                "Every member calculation conditions on one independently validated no-selection PAG completion.",
                "The unverified legal source relation and legal effects are excluded from every member selection diagram.",
                "Member outcomes are candidate-only and do not calibrate or represent a probability over the PAG class.",
            ),
            unresolved_predicates=(
                "operative_legal_relation_verification",
                "graph_real_world_truth_and_currentness",
                "pag_class_probability_or_calibration",
                "population_or_class_level_transportability",
            ),
            generation_budget=generation_budget,
            evaluation_budget=evaluation_budget,
            proposals=proposal_rows,
            evaluations=tuple(rows),
            assignment_space_size=family.counts.assignment_space_size,
            unattempted_proposals=family.counts.unattempted_proposals,
            generation_coverage=(
                "finite_endpoint_assignment_space_complete"
                if exact_generation_coverage
                else "not_established"
            ),
            evaluated_at=now,
        )

    not_started_rows = [not_started_row(member, not_started_reason) for member in family.members]
    elapsed_before_solver = time.monotonic() - evaluation_started
    if not_started_rows:
        baseline = build_diagnostic(
            not_started_rows,
            attempted_count=0,
            termination="budget_exhausted",
            phase_reason=not_started_reason,
            elapsed=elapsed_before_solver,
        )
        baseline, baseline_size = _candidate_measure_diagnostic_output(
            baseline,
            resource_resolution=resource_resolution,
        )
        if baseline_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )

    retained_rows: list[TransportabilityCandidateMemberEvaluationV1] = []
    attempted_count = 0
    stop_reason: TransportabilityCandidateReasonV1 | None = None
    phase_termination = "completed"
    for index, member in enumerate(family.members):
        elapsed_before_solver = time.monotonic() - evaluation_started
        later_rows = [
            not_started_row(remaining, not_started_reason)
            for remaining in family.members[index + 1 :]
        ]
        output_reason = TransportabilityCandidateReasonV1(
            code="result_not_retained_due_output_budget",
            detail=(
                "The solver call returned, but retaining its complete result would exceed "
                "the selected serialized diagnostic byte limit."
            ),
        )
        preflight_error_row = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=member.member_sha256,
            member_graph_ref=member_graph_refs[member.member_sha256],
            disposition="error",
            reason=output_reason,
        )
        preflight = build_diagnostic(
            [*retained_rows, preflight_error_row, *later_rows],
            attempted_count=attempted_count + 1,
            termination="budget_exhausted",
            phase_reason=output_reason,
            elapsed=elapsed_before_solver,
        )
        preflight, preflight_size = _candidate_measure_diagnostic_output(
            preflight,
            resource_resolution=resource_resolution,
        )
        if preflight_size > diagnostic_limit:
            stop_reason = TransportabilityCandidateReasonV1(
                code="candidate_diagnostic_output_budget_exhausted_before_solver",
                detail=(
                    "The remaining byte budget cannot retain even a typed result-not-retained "
                    "row, so no additional solver call was started."
                ),
            )
            phase_termination = "budget_exhausted"
            rows = [
                *retained_rows,
                *[not_started_row(remaining, stop_reason) for remaining in family.members[index:]],
            ]
            stopped = build_diagnostic(
                rows,
                attempted_count=attempted_count,
                termination=phase_termination,
                phase_reason=stop_reason,
                elapsed=elapsed_before_solver,
            )
            stopped, stopped_size = _candidate_measure_diagnostic_output(
                stopped,
                resource_resolution=resource_resolution,
            )
            if stopped_size > diagnostic_limit:
                raise ValueError(
                    "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
                )
            return stopped
        if elapsed_before_solver >= phase_limit:
            stop_reason = TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The bounded phase stopped before starting this member evaluation.",
            )
            phase_termination = "budget_exhausted"
            rows = [
                *retained_rows,
                *[not_started_row(remaining, stop_reason) for remaining in family.members[index:]],
            ]
            stopped = build_diagnostic(
                rows,
                attempted_count=attempted_count,
                termination=phase_termination,
                phase_reason=stop_reason,
                elapsed=elapsed_before_solver,
            )
            stopped, stopped_size = _candidate_measure_diagnostic_output(
                stopped,
                resource_resolution=resource_resolution,
            )
            if stopped_size > diagnostic_limit:
                raise ValueError(
                    "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
                )
            return stopped

        persisted_member = persisted_member_graphs[member.member_sha256]
        diagram = build_selection_diagram(source_context, target_context, persisted_member)
        try:
            evaluation_row = evaluate_pag_member_candidate(
                family=family,
                member=member,
                source_graph=graph,
                source_context=source_context,
                target_context=target_context,
                selection_diagram=diagram,
                member_graph_ref=member_graph_refs[member.member_sha256],
                persisted_member_graph=persisted_member,
                inputs=inputs,
                solver_mode=solver_mode,
                allow_degraded_transport=allow_degraded_transport,
                capability_contract=capability_contract,
                privacy_context=privacy_context,
            )
        except TransportCandidateMemberBindingError as exc:
            evaluation_row = TransportabilityCandidateMemberEvaluationV1(
                member_sha256=member.member_sha256,
                member_graph_ref=member_graph_refs[member.member_sha256],
                disposition="error",
                reason=TransportabilityCandidateReasonV1(
                    code=exc.reason_code,
                    detail=(
                        "The admitted member failed exact input binding before the native solver was invoked."
                    ),
                ),
            )

        attempted_count += 1
        solver_elapsed = time.monotonic() - evaluation_started
        if evaluation_row.disposition == "error":
            retained_rows.append(evaluation_row)
            if solver_elapsed > phase_limit:
                stop_reason = TransportabilityCandidateReasonV1(
                    code="candidate_evaluation_elapsed_budget_exhausted",
                    detail="The synchronous solver returned after the admitted phase elapsed budget.",
                )
                phase_termination = "budget_exhausted"
                retained_rows.extend(
                    not_started_row(remaining, stop_reason)
                    for remaining in family.members[index + 1 :]
                )
                break
            continue
        if evaluation_row.disposition != "completed" or evaluation_row.outcome is None:
            raise ValueError("conditional_transport_candidate_solver_row_invalid")
        completed_row = evaluation_row
        remaining_rows = [
            not_started_row(remaining, not_started_reason)
            for remaining in family.members[index + 1 :]
        ]
        probe_reason = TransportabilityCandidateReasonV1(
            code="candidate_evaluation_output_size_probe",
            detail="Internal sizing probe only; it is not retained as an evaluation outcome.",
        )
        probe = build_diagnostic(
            [*retained_rows, completed_row, *remaining_rows],
            attempted_count=attempted_count,
            termination="error",
            phase_reason=probe_reason,
            elapsed=solver_elapsed,
        )
        probe, probe_size = _candidate_measure_diagnostic_output(
            probe,
            resource_resolution=resource_resolution,
        )
        if probe_size > diagnostic_limit:
            stop_reason = output_reason
            phase_termination = "budget_exhausted"
            overflow_row = TransportabilityCandidateMemberEvaluationV1(
                member_sha256=member.member_sha256,
                member_graph_ref=member_graph_refs[member.member_sha256],
                disposition="error",
                reason=output_reason,
            )
            final_rows = [
                *retained_rows,
                overflow_row,
                *[
                    not_started_row(remaining, output_reason)
                    for remaining in family.members[index + 1 :]
                ],
            ]
            final = build_diagnostic(
                final_rows,
                attempted_count=attempted_count,
                termination=phase_termination,
                phase_reason=stop_reason,
                elapsed=solver_elapsed,
            )
            final, final_size = _candidate_measure_diagnostic_output(
                final,
                resource_resolution=resource_resolution,
                recorded_size=probe_size,
            )
            if final_size > diagnostic_limit:
                raise ValueError(
                    "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
                )
            return final

        retained_rows.append(completed_row)
        if solver_elapsed > phase_limit:
            stop_reason = TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The synchronous solver returned after the admitted phase elapsed budget.",
            )
            phase_termination = "budget_exhausted"
            retained_rows.extend(
                not_started_row(remaining, stop_reason) for remaining in family.members[index + 1 :]
            )
            break

    evaluation_elapsed = time.monotonic() - evaluation_started
    if len(retained_rows) == len(family.members):
        if any(row.disposition == "error" for row in retained_rows):
            phase_termination = "error"
            stop_reason = stop_reason or TransportabilityCandidateReasonV1(
                code="candidate_member_evaluation_error",
                detail="At least one admitted member solver call returned an error.",
            )
        elif evaluation_elapsed > phase_limit:
            phase_termination = "budget_exhausted"
            stop_reason = TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The complete synchronous member sequence exceeded the admitted elapsed budget.",
            )
        else:
            phase_termination = "completed"
            stop_reason = None
    final = build_diagnostic(
        retained_rows,
        attempted_count=attempted_count,
        termination=phase_termination,
        phase_reason=stop_reason,
        elapsed=evaluation_elapsed,
    )
    final, final_size = _candidate_measure_diagnostic_output(
        final,
        resource_resolution=resource_resolution,
    )
    if final_size > diagnostic_limit:
        raise ValueError("conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget")
    return final


def _candidate_input_binding(
    *,
    graph_ref: Any,
    graph: CausalGraphModel,
    source_context: ContextProfile,
    target_context: ContextProfile,
    query_treatment: str,
    query_outcome: str,
    query_sha256: str,
    lineage_refs: tuple[InputRef, ...],
    requested_profile_id: str,
    requested_profile_revision: str,
) -> TransportabilityCandidateInputBindingV1:
    diagram_sha256: str | None = None
    if graph.graph_type is not GraphType.PAG:
        diagram = build_selection_diagram(source_context, target_context, graph)
        diagram_sha256 = _candidate_sha256(diagram.model_dump(mode="json"))
    base = {
        "graph_ref": graph_ref.model_dump(mode="json"),
        "graph_type": graph.graph_type.value,
        "graph_sha256": graph_content_sha256(graph),
        "query_treatment": query_treatment,
        "query_outcome": query_outcome,
        "query_sha256": query_sha256,
        "source_context_id": source_context.context_id,
        "source_context_sha256": _candidate_context_digest(source_context),
        "target_context_id": target_context.context_id,
        "target_context_sha256": _candidate_context_digest(target_context),
        "profile_id": requested_profile_id,
        "profile_revision": requested_profile_revision,
    }
    if graph.graph_type is GraphType.PAG:
        relation_payload = {
            "relation_id": "transportability.pag.no_selection.member_selection_diagrams",
            "revision": "1",
            **base,
        }
    if graph.graph_type is GraphType.PAG:
        return TransportabilityCandidateInputBindingV1(
            graph_ref=graph_ref,
            graph_type=graph.graph_type,
            graph_sha256=base["graph_sha256"],
            model_plan_relation=TransportabilityCandidateModelPlanRelationV1(
                relation_id=relation_payload["relation_id"],
                revision=relation_payload["revision"],
                content_sha256=_candidate_sha256(relation_payload),
            ),
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            query_sha256=query_sha256,
            source_context_id=source_context.context_id,
            source_context_sha256=base["source_context_sha256"],
            target_context_id=target_context.context_id,
            target_context_sha256=base["target_context_sha256"],
            lineage_refs=lineage_refs,
        )
    return TransportabilityCandidateInputBindingV1(
        graph_ref=graph_ref,
        graph_type=graph.graph_type,
        graph_sha256=base["graph_sha256"],
        selection_diagram_sha256=diagram_sha256,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        query_sha256=query_sha256,
        source_context_id=source_context.context_id,
        source_context_sha256=base["source_context_sha256"],
        target_context_id=target_context.context_id,
        target_context_sha256=base["target_context_sha256"],
        lineage_refs=lineage_refs,
    )


def _conditional_transport_candidate_diagnostic(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    request: TransportabilityCandidateRequestV1,
    attempt: _ConditionalCandidateAttempt,
    graph_ref: Any,
    graph: CausalGraphModel,
    source_context: ContextProfile,
    target_context: ContextProfile,
    causal_report_ref: CausalEffectReportRef,
    capability_contract: CausalCapabilityContract,
    query_treatment: str,
    query_outcome: str,
    solver_mode: str,
    allow_degraded_transport: bool,
    privacy_context: TransportPrivacyContext | None,
) -> TransportabilityCandidateDiagnosticV1:
    resource_profile = _resolve_conditional_transport_resource_profile(
        request,
        actual_node_timeout_s=attempt.hard_deadline_s,
        frozen_policy_snapshot=attempt.workflow_params.get(
            CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM
        ),
    )
    resource_resolution = TransportabilityCandidateResourceResolutionV1.model_validate(
        resource_profile
    )
    graph_sha256 = graph_content_sha256(graph)
    query_sha256 = transportability_candidate_query_sha256(query_treatment, query_outcome)
    basis_ref = attempt.attempt_binding.basis_ref
    workflow_ref = attempt.attempt_binding.workflow_spec_ref
    state_ref = attempt.attempt_binding.input_state_ref
    graph_lineage_ref = _candidate_input_ref(graph_ref, "selected_causal_graph")
    report_lineage_ref = _candidate_input_ref(causal_report_ref, "causal_effect_report")
    lineage_refs = (
        basis_ref,
        workflow_ref,
        state_ref,
        graph_lineage_ref,
        report_lineage_ref,
    )
    inputs = _candidate_input_binding(
        graph_ref=graph_ref,
        graph=graph,
        source_context=source_context,
        target_context=target_context,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        query_sha256=query_sha256,
        lineage_refs=lineage_refs,
        requested_profile_id=request.profile_id,
        requested_profile_revision=request.profile_revision,
    )
    selected = resource_profile.get("status") == "selected"
    effective_profile = (
        TransportabilityCandidateProfileV1(
            profile_id=request.profile_id,
            profile_revision=request.profile_revision,
        )
        if selected
        else None
    )
    now = datetime.now(UTC)
    current_policy = causal_full_transport_resource_policy_snapshot()
    current_limits = current_policy.get("limits")
    if not isinstance(current_limits, Mapping):
        raise ValueError("conditional_transport_candidate_current_owner_limits_not_established")
    assignment_space_size, unattempted_proposals = _candidate_unattempted_pag_partition(
        graph,
        max_diagnostic_bytes=int(current_limits["max_diagnostic_bytes"]),
    )
    refusal_deadline_evidence, _ = _candidate_worker_deadline_evidence(
        attempt,
        phase_limit=float(current_limits["max_elapsed_seconds"]),
    )
    reason: TransportabilityCandidateReasonV1 | None = None
    if not selected:
        refusal = str(resource_profile.get("reason_code") or "candidate_profile_not_admitted")
        reason = TransportabilityCandidateReasonV1(
            code=refusal,
            detail="The trusted resource-profile owner refused this request before candidate work.",
        )
        generation = _candidate_budget_phase(
            phase="generation",
            selection_identity=request.selection_identity,
            admission="refused" if graph.graph_type is GraphType.PAG else "not_required",
            reason=reason,
            termination="not_started",
        )
        evaluation = _candidate_budget_phase(
            phase="evaluation",
            selection_identity=request.selection_identity,
            admission="refused",
            reason=reason,
            termination="not_started",
        )
        return TransportabilityCandidateDiagnosticV1(
            candidate_request=request,
            effective_profile=None,
            resource_resolution=resource_resolution,
            disposition="unsupported",
            reason=reason,
            attempt=attempt.attempt_binding,
            inputs=inputs,
            graph_provenance="unknown",
            algorithm_id=request.profile_id,
            algorithm_revision=request.profile_revision,
            implementation_revision=_candidate_solver_revision(),
            backend_id="not_established",
            backend_revision="not_established",
            parameters={
                "resource_profile_sha256": resource_profile["sha256"],
                "verified_node_hard_deadline_s": attempt.hard_deadline_s,
                "worker_deadline_evidence": dict(refusal_deadline_evidence or {}),
            },
            assumptions=(
                "The outer legal relation remains unverified and is not inferred from this request.",
            ),
            unresolved_predicates=(
                "operative_legal_relation_verification",
                "candidate_computation_access_admission",
                "graph_real_world_truth_and_currentness",
            ),
            generation_budget=generation,
            evaluation_budget=evaluation,
            assignment_space_size=assignment_space_size,
            unattempted_proposals=unattempted_proposals,
            generation_coverage="not_established",
            evaluated_at=now,
        )

    profile_key = (request.profile_id, request.profile_revision)
    profile_supported = profile_key in {_RESOLVED_GRAPH_PROFILE, _PAG_FAMILY_PROFILE}
    graph_supported = (
        profile_key == _RESOLVED_GRAPH_PROFILE
        and graph.graph_type in {GraphType.DAG, GraphType.ADMG}
    ) or (profile_key == _PAG_FAMILY_PROFILE and graph.graph_type is GraphType.PAG)
    if not profile_supported or not graph_supported:
        reason = TransportabilityCandidateReasonV1(
            code="candidate_profile_input_not_supported",
            detail=(
                f"Profile {request.profile_id}@{request.profile_revision} does not admit "
                f"selected graph type {graph.graph_type.value}."
            ),
        )
        generation = _candidate_budget_phase(
            phase="generation",
            selection_identity=request.selection_identity,
            admission=("refused" if graph.graph_type is GraphType.PAG else "not_required"),
            reason=reason,
            termination="not_started",
        )
        evaluation = _candidate_budget_phase(
            phase="evaluation",
            selection_identity=request.selection_identity,
            admission="refused",
            reason=reason,
            termination="not_started",
        )
        return TransportabilityCandidateDiagnosticV1(
            candidate_request=request,
            effective_profile=effective_profile,
            resource_resolution=resource_resolution,
            disposition="unsupported",
            reason=reason,
            attempt=attempt.attempt_binding,
            inputs=inputs,
            graph_provenance="unknown",
            algorithm_id=request.profile_id,
            algorithm_revision=request.profile_revision,
            implementation_revision=_candidate_solver_revision(),
            backend_id="not_established",
            backend_revision="not_established",
            parameters={
                "resource_profile_sha256": resource_profile["sha256"],
                "verified_node_hard_deadline_s": attempt.hard_deadline_s,
                "worker_deadline_evidence": dict(refusal_deadline_evidence or {}),
            },
            assumptions=(
                "The legal source relation remains unverified and is excluded from the candidate graph calculation.",
            ),
            unresolved_predicates=(
                "operative_legal_relation_verification",
                "selected_graph_profile_compatibility",
                "graph_real_world_truth_and_currentness",
            ),
            generation_budget=generation,
            evaluation_budget=evaluation,
            assignment_space_size=assignment_space_size,
            unattempted_proposals=unattempted_proposals,
            generation_coverage="not_established",
            evaluated_at=now,
        )

    phase_limit = float(resource_resolution.effective_limits["max_elapsed_seconds"])
    worker_deadline_evidence, deadline_refusal = _candidate_worker_deadline_evidence(
        attempt,
        phase_limit=phase_limit,
    )
    if deadline_refusal is not None:
        deadline_reason = TransportabilityCandidateReasonV1(
            code=deadline_refusal,
            detail="The verified worker deadline no longer contains the full bounded candidate phase.",
        )
        return _build_candidate_worker_deadline_refusal_diagnostic(
            request=request,
            attempt=attempt,
            inputs=inputs,
            graph=graph,
            resource_profile=resource_profile,
            resource_resolution=resource_resolution,
            reason=deadline_reason,
            worker_deadline_evidence=worker_deadline_evidence,
        )

    if graph.graph_type is GraphType.PAG:
        return _conditional_transport_pag_member_diagnostic(
            ctx=ctx,
            request=request,
            attempt=attempt,
            graph_ref=graph_ref,
            graph=graph,
            source_context=source_context,
            target_context=target_context,
            inputs=inputs,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            query_sha256=query_sha256,
            solver_mode=solver_mode,
            allow_degraded_transport=allow_degraded_transport,
            capability_contract=capability_contract,
            privacy_context=privacy_context,
            resource_profile=resource_profile,
            resource_resolution=resource_resolution,
        )

    diagram = build_selection_diagram(source_context, target_context, graph)
    evaluation_started = time.monotonic()
    max_elapsed = float(resource_resolution.effective_limits["max_elapsed_seconds"])
    diagnostic_limit = int(resource_resolution.effective_limits["max_diagnostic_bytes"])
    evaluation_limits = tuple(
        _candidate_owned_measure(
            resource,
            resource_resolution.effective_limits[resource],
            resource_resolution,
        )
        for resource in (
            "max_evaluations",
            "max_elapsed_seconds",
            "max_diagnostic_bytes",
        )
    )
    generation_budget = _candidate_budget_phase(
        phase="generation",
        selection_identity=request.selection_identity,
        admission="not_required",
        termination="not_required",
    )
    assumptions = (
        "The selected graph is analyzed as a conditional mathematical input, not verified as a truthful real-world graph.",
        "The unverified operative legal relation and legal effects are excluded from this candidate selection diagram.",
        "The existing scalar solver output is candidate-only and does not establish whole-class PAG probability or legal applicability.",
    )
    output_reason = TransportabilityCandidateReasonV1(
        code="result_not_retained_due_output_budget",
        detail=(
            "The solver call returned, but retaining its complete result would exceed "
            "the selected serialized diagnostic byte limit."
        ),
    )
    not_started_reason = TransportabilityCandidateReasonV1(
        code="candidate_evaluation_output_budget_exhausted_before_solver",
        detail="The selected byte budget cannot retain a typed refusal if the solver result is too large.",
    )

    def build_resolved_diagnostic(
        row: TransportabilityCandidateMemberEvaluationV1,
        *,
        attempted_count: int,
        termination: str,
        phase_reason: TransportabilityCandidateReasonV1 | None,
        elapsed: float,
        diagnostic_reason: TransportabilityCandidateReasonV1 | None = None,
        evaluation_admission: str = "admitted",
        worker_deadline_evidence: Mapping[str, float | str] | None = None,
    ) -> TransportabilityCandidateDiagnosticV1:
        retained_count = int(row.disposition == "completed")
        params = {
            "solver_mode": solver_mode,
            "allow_degraded_transport": allow_degraded_transport,
            "capability_contract_fingerprint": capability_contract.dependency_fingerprint,
            "resource_profile_policy_id": resource_profile["policy_id"],
            "resource_profile_policy_revision": resource_profile["policy_revision"],
            "resource_profile_sha256": resource_profile["sha256"],
            "verified_node_hard_deadline_s": attempt.hard_deadline_s,
            "evaluation_accounting_scope": "retained_completed_source_bound_outcomes_only",
            "evaluation_source_member_count": 1,
            "evaluation_attempted_member_count": attempted_count,
            "evaluation_completed_retained_member_count": retained_count,
            "evaluation_not_started_member_count": int(row.disposition == "not_started"),
            "identified_member_fraction_denominator": retained_count,
        }
        if worker_deadline_evidence is not None:
            params["worker_deadline_evidence"] = dict(worker_deadline_evidence)
        evaluation_budget = _candidate_budget_phase(
            phase="evaluation",
            selection_identity=request.selection_identity,
            admission=evaluation_admission,
            resource_resolution=resource_resolution,
            limits=evaluation_limits,
            consumed=(
                _candidate_owned_measure("max_evaluations", attempted_count, resource_resolution),
                _candidate_owned_measure("max_elapsed_seconds", elapsed, resource_resolution),
                _candidate_owned_measure("max_diagnostic_bytes", 0, resource_resolution),
            ),
            termination=termination,
            reason=phase_reason,
            elapsed_seconds=elapsed,
        )
        complete = row.disposition == "completed" and termination == "completed"
        reason = None if complete else diagnostic_reason or phase_reason or row.reason
        return TransportabilityCandidateDiagnosticV1(
            candidate_request=request,
            effective_profile=effective_profile,
            resource_resolution=resource_resolution,
            disposition="completed" if complete else "partial",
            reason=reason,
            attempt=attempt.attempt_binding,
            inputs=inputs,
            graph_provenance="unknown",
            algorithm_id="polisyos.transport_engine.solve_transportability",
            algorithm_revision=(
                row.outcome.algorithm_version if row.outcome is not None else "not_completed"
            ),
            implementation_revision=_candidate_solver_revision(),
            backend_id=(
                row.outcome.identification_engine if row.outcome is not None else "not_established"
            ),
            backend_revision=(
                row.outcome.algorithm_version if row.outcome is not None else "not_established"
            ),
            parameters=params,
            assumptions=assumptions,
            unresolved_predicates=(
                "operative_legal_relation_verification",
                "graph_real_world_truth_and_currentness",
                "population_or_class_level_transportability",
            ),
            generation_budget=generation_budget,
            evaluation_budget=evaluation_budget,
            evaluations=(row,),
            generation_coverage="not_established",
            evaluated_at=now,
        )

    preflight_row = TransportabilityCandidateMemberEvaluationV1(
        member_sha256=graph_sha256,
        member_graph_ref=graph_ref,
        disposition="error",
        reason=output_reason,
    )
    preflight = build_resolved_diagnostic(
        preflight_row,
        attempted_count=1,
        termination="budget_exhausted",
        phase_reason=output_reason,
        elapsed=0.0,
    )
    preflight, preflight_size = _candidate_measure_diagnostic_output(
        preflight,
        resource_resolution=resource_resolution,
    )
    if preflight_size > diagnostic_limit:
        not_started = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="not_started",
            reason=not_started_reason,
        )
        refused = build_resolved_diagnostic(
            not_started,
            attempted_count=0,
            termination="budget_exhausted",
            phase_reason=not_started_reason,
            elapsed=0.0,
            diagnostic_reason=not_started_reason,
        )
        refused, refused_size = _candidate_measure_diagnostic_output(
            refused,
            resource_resolution=resource_resolution,
        )
        if refused_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return refused

    live_deadline_evidence, live_deadline_refusal = _candidate_worker_deadline_evidence(
        attempt,
        phase_limit=max_elapsed,
    )
    if live_deadline_refusal is not None:
        deadline_reason = TransportabilityCandidateReasonV1(
            code=live_deadline_refusal,
            detail="The verified worker deadline no longer contains the full bounded evaluation phase.",
        )
        not_started = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="not_started",
            reason=deadline_reason,
        )
        refused = build_resolved_diagnostic(
            not_started,
            attempted_count=0,
            termination="budget_exhausted",
            phase_reason=deadline_reason,
            elapsed=0.0,
            diagnostic_reason=deadline_reason,
            evaluation_admission="refused",
            worker_deadline_evidence=live_deadline_evidence,
        )
        refused, refused_size = _candidate_measure_diagnostic_output(
            refused,
            resource_resolution=resource_resolution,
        )
        if refused_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return refused

    solver_error: Exception | None = None
    solver_result: TransportabilityResult | None = None
    try:
        solver_result = solve_transportability(
            selection_diagram=diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            solver_mode=solver_mode,
            allow_degraded_transport=allow_degraded_transport,
            capability_contract=capability_contract,
            pag_identification_policy=None,
            pag_max_dag_samples=1,
            pag_threshold=0.5,
            pag_seed=0,
            surrogate_data_profile=Y0_SURROGATE_DATA_PROFILE_ABSENT,
            privacy_context=privacy_context,
        )
        if solver_result.query != f"P*({query_outcome}|do({query_treatment}))":
            raise ValueError("candidate_solver_returned_different_query")
    except Exception as exc:
        solver_error = exc

    eval_elapsed = time.monotonic() - evaluation_started
    if solver_error is not None or solver_result is None:
        error_reason = TransportabilityCandidateReasonV1(
            code="candidate_member_solver_error",
            detail=f"Existing solver failed for the selected graph ({type(solver_error).__name__}).",
        )
        evaluation_row = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="error",
            reason=error_reason,
        )
        eval_termination = "budget_exhausted" if eval_elapsed > max_elapsed else "error"
        eval_reason = (
            TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The synchronous solver returned after the admitted phase elapsed budget.",
            )
            if eval_termination == "budget_exhausted"
            else error_reason
        )
        diagnostic = build_resolved_diagnostic(
            evaluation_row,
            attempted_count=1,
            termination=eval_termination,
            phase_reason=eval_reason,
            elapsed=eval_elapsed,
        )
        diagnostic, final_size = _candidate_measure_diagnostic_output(
            diagnostic,
            resource_resolution=resource_resolution,
        )
        if final_size > diagnostic_limit:
            diagnostic, final_size = _candidate_measure_diagnostic_output(
                diagnostic,
                resource_resolution=resource_resolution,
                recorded_size=preflight_size,
            )
        if final_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return diagnostic

    try:
        outcome = TransportabilityCandidateSolverOutcomeV1.from_result(
            solver_result,
            query_sha256=query_sha256,
        )
        evaluation_row = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="completed",
            outcome=outcome,
        )
    except (TypeError, ValueError) as exc:
        error_reason = TransportabilityCandidateReasonV1(
            code="candidate_solver_result_binding_error",
            detail=f"The completed solver result could not be bound to its source ({type(exc).__name__}).",
        )
        evaluation_row = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="error",
            reason=error_reason,
        )
        eval_termination = "budget_exhausted" if eval_elapsed > max_elapsed else "error"
        eval_reason = (
            TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The synchronous solver returned after the admitted phase elapsed budget.",
            )
            if eval_termination == "budget_exhausted"
            else error_reason
        )
        diagnostic = build_resolved_diagnostic(
            evaluation_row,
            attempted_count=1,
            termination=eval_termination,
            phase_reason=eval_reason,
            elapsed=eval_elapsed,
        )
        diagnostic, final_size = _candidate_measure_diagnostic_output(
            diagnostic,
            resource_resolution=resource_resolution,
        )
        if final_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return diagnostic

    probe_reason = TransportabilityCandidateReasonV1(
        code="candidate_evaluation_output_size_probe",
        detail="Internal sizing probe only; it is not retained as a diagnostic status.",
    )
    probe_termination = "budget_exhausted" if eval_elapsed > max_elapsed else "error"
    probe = build_resolved_diagnostic(
        evaluation_row,
        attempted_count=1,
        termination=probe_termination,
        phase_reason=(
            TransportabilityCandidateReasonV1(
                code="candidate_evaluation_elapsed_budget_exhausted",
                detail="The synchronous solver returned after the admitted phase elapsed budget.",
            )
            if eval_elapsed > max_elapsed
            else probe_reason
        ),
        elapsed=eval_elapsed,
        diagnostic_reason=probe_reason,
    )
    probe, probe_size = _candidate_measure_diagnostic_output(
        probe,
        resource_resolution=resource_resolution,
    )
    if probe_size > diagnostic_limit:
        overflow_row = TransportabilityCandidateMemberEvaluationV1(
            member_sha256=graph_sha256,
            member_graph_ref=graph_ref,
            disposition="error",
            reason=output_reason,
        )
        overflow = build_resolved_diagnostic(
            overflow_row,
            attempted_count=1,
            termination="budget_exhausted",
            phase_reason=output_reason,
            elapsed=eval_elapsed,
        )
        overflow, final_size = _candidate_measure_diagnostic_output(
            overflow,
            resource_resolution=resource_resolution,
            recorded_size=probe_size,
        )
        if final_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return overflow

    final_termination = "budget_exhausted" if eval_elapsed > max_elapsed else "completed"
    final_reason = (
        TransportabilityCandidateReasonV1(
            code="candidate_evaluation_elapsed_budget_exhausted",
            detail="The actual solver returned after the admitted phase elapsed budget.",
        )
        if final_termination == "budget_exhausted"
        else None
    )
    diagnostic = build_resolved_diagnostic(
        evaluation_row,
        attempted_count=1,
        termination=final_termination,
        phase_reason=final_reason,
        elapsed=eval_elapsed,
    )
    diagnostic, final_size = _candidate_measure_diagnostic_output(
        diagnostic,
        resource_resolution=resource_resolution,
    )
    if final_size > diagnostic_limit:
        overflow = build_resolved_diagnostic(
            TransportabilityCandidateMemberEvaluationV1(
                member_sha256=graph_sha256,
                member_graph_ref=graph_ref,
                disposition="error",
                reason=output_reason,
            ),
            attempted_count=1,
            termination="budget_exhausted",
            phase_reason=output_reason,
            elapsed=eval_elapsed,
        )
        overflow, final_size = _candidate_measure_diagnostic_output(
            overflow,
            resource_resolution=resource_resolution,
            recorded_size=probe_size,
        )
        if final_size > diagnostic_limit:
            raise ValueError(
                "conditional_transport_candidate_minimum_diagnostic_exceeds_output_budget"
            )
        return overflow
    return diagnostic


MAX_ROUNDS = 3
PROXY_FALLBACK_THRESHOLD = 0.3
_SERIOUS_TRANSPORT_PROFILES: frozenset[str] = frozenset({"research", "governed", "production"})


_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_transportability@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Transportability",
    description=(
        "Resolve transportability through three-graph closure "
        "(context/SKG + datasets + legal constraints)."
    ),
    tags=["builtin", "causal", "transportability"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.source_context",
        "params.target_context",
        "params.query_treatment",
        "params.query_outcome",
        "params.policy_spec",
        "params.pag_identification_policy",
        "params.pag_max_dag_samples",
        "params.pag_threshold",
        "params.pag_seed",
        "params.transport_solver_mode",
        "params.surrogate_data_profile",
        "params.allow_degraded_transport",
        "params.privacy_context",
        "params.dp_utility_manifest",
        "params.privacy_transport_certificate",
        "params.conditional_transport_request",
        "params.workflow_id",
        "params.dataset_registry_db_path",
        "params.legal_kg_db_path",
        "params.skg_db_path",
        "params.skg_index_dir",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENSEMBLE_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
    ],
    state_writes=[
        "causal_capability_contract_ref",
        "params.transportability_status",
        "params.transportability_transport_mode",
        "params.transportability_identification_engine",
        "params.transportability_id_confidence_under_pag",
        "params.transportability_capability_hash",
        "params.transportability_degradation_policy",
        "params.transportability_warning",
        "params.transport_required",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_TRANSPORTABILITY_RESULT_REF}",
    ],
    produces=[
        ARTIFACT_TRANSPORTABILITY_RESULT_REF,
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ],
)


class ResolutionState(BaseModel):
    """Immutable snapshot of one transportability-resolution loop iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    round: int
    s_nodes: list[SNode] = Field(default_factory=list)
    legal_s_nodes: list[SNode] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    hard_constraints: list[LegalConstraint] = Field(default_factory=list)
    p_star_values: dict[str, PStarZResult] = Field(default_factory=dict)
    proxy_penalties: dict[str, float] = Field(default_factory=dict)
    proxy_validity: dict[str, dict[str, Any]] = Field(default_factory=dict)
    requires_expert_review: bool = False
    expert_review_reasons: list[str] = Field(default_factory=list)
    converged: bool = False
    feasible: bool = True


class TransportabilityResolutionLoop:
    """Resolve transportability across datasets, SKG evidence, and legal rules.

    The loop caches expensive lookups across rounds, accumulates S-nodes and
    data gaps, and determines whether the workflow can proceed with direct
    transport, degraded transport, or expert-review escalation.
    """

    MAX_ROUNDS: int = MAX_ROUNDS

    def __init__(
        self,
        *,
        dataset_registry: DatasetRegistry | _NullDatasetRegistry,
        legal_kg_db_path: Path | None,
        skg_query: SKGQuery | _NullSKG,
        max_rounds: int = MAX_ROUNDS,
        proxy_threshold: float = PROXY_FALLBACK_THRESHOLD,
    ) -> None:
        self._datasets = dataset_registry
        self._legal_kg_db_path = legal_kg_db_path
        self._skg = skg_query
        self._max_rounds = min(MAX_ROUNDS, max(1, int(max_rounds)))
        self._proxy_threshold = max(0.0, min(1.0, float(proxy_threshold)))
        self._distance_cache: dict[tuple[str, str], float] = {}
        self._find_datasets_cache: dict[
            tuple[str, str, tuple[int, int] | None], tuple[Any, ...]
        ] = {}
        self._p_star_cache: dict[
            tuple[str, str, int, tuple[tuple[str, float], ...]], PStarZResult
        ] = {}

    def _cache_clear(self) -> None:
        self._distance_cache.clear()
        self._find_datasets_cache.clear()
        self._p_star_cache.clear()

    @staticmethod
    def _normalize_condition_key(
        condition_on: dict[str, float] | None,
    ) -> tuple[tuple[str, float], ...]:
        if not condition_on:
            return ()
        normalized: list[tuple[str, float]] = []
        for key, value in sorted(condition_on.items(), key=lambda item: str(item[0])):
            normalized.append((str(key), float(value)))
        return tuple(normalized)

    def _cached_context_distance(
        self,
        *,
        source_context: ContextProfile,
        target_context: ContextProfile,
    ) -> float:
        key = (source_context.context_id, target_context.context_id)
        cached = self._distance_cache.get(key)
        if cached is not None:
            return cached
        distance = float(source_context.distance_to(target_context))
        self._distance_cache[key] = distance
        return distance

    def _cached_find_datasets(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None,
    ) -> list[Any]:
        key = (canonical_var, country_code, year_range)
        cached = self._find_datasets_cache.get(key)
        if cached is not None:
            return list(cached)
        matches = self._datasets.find_datasets_for_variable(
            canonical_var=canonical_var,
            country_code=country_code,
            year_range=year_range,
        )
        frozen = tuple(matches)
        self._find_datasets_cache[key] = frozen
        return list(frozen)

    def _cached_compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        condition_on: dict[str, float] | None,
    ) -> PStarZResult:
        condition_key = self._normalize_condition_key(condition_on)
        key = (canonical_var, country_code, int(year), condition_key)
        cached = self._p_star_cache.get(key)
        if cached is not None:
            return cached

        # Prime dataset lookup cache for the same year-slice used by compute_p_star_z.
        self._cached_find_datasets(canonical_var, country_code, (int(year), int(year)))

        result = self._datasets.compute_p_star_z(
            canonical_var=canonical_var,
            country_code=country_code,
            year=int(year),
            condition_on=condition_on,
        )
        self._p_star_cache[key] = result
        return result

    def _cached_dataset_registry(self) -> _LoopDatasetRegistry:
        return _LoopDatasetRegistry(
            find_cached=self._cached_find_datasets,
            p_star_cached=self._cached_compute_p_star_z,
        )

    @staticmethod
    def _record_proxy_fallback(
        *,
        variable: str,
        fallback: tuple[
            PStarZResult | None,
            DataGap | None,
            dict[str, Any] | None,
            float | None,
            bool,
            list[str],
        ],
        p_star_values: dict[str, PStarZResult],
        data_gaps: list[DataGap],
        proxy_penalties: dict[str, float],
        proxy_validity: dict[str, dict[str, Any]],
        requires_expert_review: bool,
        expert_review_reasons: list[str],
    ) -> bool:
        (
            proxy_value,
            data_gap,
            proxy_validity_value,
            proxy_penalty,
            proxy_requires_expert_review,
            proxy_expert_review_reasons,
        ) = fallback
        if proxy_validity_value is not None:
            proxy_validity[variable] = proxy_validity_value
        if proxy_requires_expert_review:
            requires_expert_review = True
            for reason in proxy_expert_review_reasons:
                if reason not in expert_review_reasons:
                    expert_review_reasons.append(reason)
        if proxy_value is not None:
            p_star_values[variable] = proxy_value
        if proxy_penalty is not None:
            proxy_penalties[variable] = proxy_penalty
        if data_gap is not None:
            data_gaps.append(data_gap)
        return requires_expert_review

    def resolve(
        self,
        *,
        source_context: ContextProfile,
        target_context: ContextProfile,
        causal_graph: CausalGraphModel,
        query_treatment: str,
        query_outcome: str,
        policy_spec: Mapping[str, Any] | None = None,
        pag_identification_policy: str | None = None,
        pag_max_dag_samples: int = 100,
        pag_threshold: float = 0.5,
        pag_seed: int | None = None,
        solver_mode: str = "auto",
        surrogate_data_profile: object = Y0_SURROGATE_DATA_PROFILE_ABSENT,
        allow_degraded_transport: bool = False,
        capability_contract: CausalCapabilityContract | None = None,
        privacy_context: TransportPrivacyContext | None = None,
        candidate_refusal_handler: Callable[[TransportabilityResult], TransportabilityResult]
        | None = None,
    ) -> TransportabilityResult:
        self._cache_clear()
        normalized_solver_mode = _normalize_transport_solver_mode(solver_mode)
        _resolve_treatment_value(policy_spec)
        try:
            cached_registry = self._cached_dataset_registry()
            prev_s_node_set: set[tuple[str, str, str]] = set()
            legal_mapping_review_reasons: list[str] = []
            state: ResolutionState | None = None
            tr_result: TransportabilityResult | None = None
            diagram: SelectionDiagram | None = None

            for round_num in range(1, self._max_rounds + 1):
                context_diagram = build_selection_diagram(
                    source_context,
                    target_context,
                    causal_graph,
                )
                context_s_nodes = list(context_diagram.s_nodes)
                try:
                    legal_constraint_set = _evaluate_legal_constraints(
                        target_context=target_context,
                        policy_spec=policy_spec,
                        causal_graph=causal_graph,
                        legal_kg_db_path=self._legal_kg_db_path,
                    )
                except LegalSourceRelationVerificationMissingError as exc:
                    refusal = exc.refusal
                    legal_refusal = _finalize_transport_loop_result(
                        TransportabilityResult(
                            query=f"P*({query_outcome}|do({query_treatment}))",
                            status=TransportabilityStatus.UNSUPPORTED,
                            transport_mode=TransportMode.NONE,
                            base_confidence=0.0,
                            final_confidence=0.0,
                            feasible=False,
                            identification_engine="legal_source_relation_gate",
                            identification_trace=[f"legal_source_relation:{refusal.status}"],
                            unsupported_reason=refusal.code,
                            unsupported_cases=[refusal.code],
                            requires_expert_review=True,
                            expert_review_reasons=[refusal.code],
                            source_context_id=source_context.context_id,
                            target_context_id=target_context.context_id,
                            warnings=[
                                "Legal transport authority is unavailable until the complete "
                                "claim-to-source relation is independently verified."
                            ],
                            metadata={"legal_source_relation_refusal": refusal.to_payload()},
                            notes=["Legal relation verification is not established."],
                        ),
                        privacy_context=privacy_context,
                    )
                    if candidate_refusal_handler is not None:
                        return candidate_refusal_handler(legal_refusal)
                    return legal_refusal
                hard_constraints = list(legal_constraint_set.hard_constraints)
                legal_s_nodes = _legal_constraints_to_s_nodes(
                    mappings=legal_constraint_set.legal_dag_mappings,
                    causal_graph=causal_graph,
                    expert_review_reasons=legal_mapping_review_reasons,
                )
                if hard_constraints:
                    return _finalize_transport_loop_result(
                        _build_infeasible_result(
                            source_context=source_context,
                            target_context=target_context,
                            hard_constraints=hard_constraints,
                            query_treatment=query_treatment,
                            query_outcome=query_outcome,
                        ),
                        privacy_context=privacy_context,
                    )

                all_s_nodes = context_s_nodes + legal_s_nodes
                diagram = SelectionDiagram(
                    base_graph=causal_graph,
                    s_nodes=all_s_nodes,
                    source_context=source_context,
                    target_context=target_context,
                    context_distance=self._cached_context_distance(
                        source_context=source_context,
                        target_context=target_context,
                    ),
                )
                tr_payload = _run_transport_solver(
                    diagram=diagram,
                    query_treatment=query_treatment,
                    query_outcome=query_outcome,
                    solver_mode=normalized_solver_mode,
                    allow_degraded_transport=allow_degraded_transport,
                    capability_contract=capability_contract,
                    pag_identification_policy=pag_identification_policy,
                    pag_max_dag_samples=pag_max_dag_samples,
                    pag_threshold=pag_threshold,
                    pag_seed=pag_seed if pag_seed is not None else 0,
                    surrogate_data_profile=surrogate_data_profile,
                    privacy_context=None,
                )
                tr_result = TransportabilityResult.model_validate(tr_payload["transport_result"])

                p_star_values: dict[str, PStarZResult] = {}
                data_gaps: list[DataGap] = []
                proxy_penalties: dict[str, float] = {}
                proxy_validity: dict[str, dict[str, Any]] = {}
                requires_expert_review = bool(legal_mapping_review_reasons) or bool(
                    tr_result.requires_expert_review
                )
                expert_review_reasons = list(legal_mapping_review_reasons)
                for reason in tr_result.expert_review_reasons:
                    if reason not in expert_review_reasons:
                        expert_review_reasons.append(reason)
                adjacency = _build_adjacency(causal_graph)

                formula = tr_result.transport_formula
                if formula is not None:
                    details_lookup = {item.name: item for item in formula.stratification_details}
                    for z_var in formula.stratification_variables:
                        detail = details_lookup.get(z_var)
                        condition_on: dict[str, float] | None = None
                        if detail is not None and detail.requires_conditional:
                            condition_on = {
                                (
                                    detail.condition_on_treatment or query_treatment
                                ): _resolve_treatment_value(policy_spec)
                            }

                        p_star = self._cached_compute_p_star_z(
                            canonical_var=z_var,
                            country_code=target_context.context_id,
                            year=_resolve_context_year(target_context),
                            condition_on=condition_on,
                        )
                        if p_star.value is not None:
                            p_star_values[z_var] = p_star
                            if p_star.is_proxy:
                                proxy_penalties[z_var] = max(
                                    0.0,
                                    min(1.0, 1.0 - p_star.confidence),
                                )
                            continue

                        proxy_chain = resolve_proxy(
                            target_var=z_var,
                            target_context=target_context.context_id,
                            dataset_registry=cached_registry,
                            skg_query=self._skg,
                        )
                        fallback = _build_proxy_quantity_or_gap(
                            variable=z_var,
                            target_context=target_context,
                            outcome=query_outcome,
                            adjacency=adjacency,
                            proxy_chain=proxy_chain,
                            condition_on=condition_on,
                            proxy_threshold=self._proxy_threshold,
                            validate_proxy_fn=validate_proxy,
                            compose_confidence_harmonic_fn=compose_confidence_harmonic,
                        )
                        requires_expert_review = self._record_proxy_fallback(
                            variable=z_var,
                            fallback=fallback,
                            p_star_values=p_star_values,
                            data_gaps=data_gaps,
                            proxy_penalties=proxy_penalties,
                            proxy_validity=proxy_validity,
                            requires_expert_review=requires_expert_review,
                            expert_review_reasons=expert_review_reasons,
                        )

                proxy_introduced_vars = {
                    var for var, value in p_star_values.items() if value.is_proxy
                }
                filtered_context_nodes = [
                    node
                    for node in context_s_nodes
                    if node.target_variable not in proxy_introduced_vars
                ]
                merged_nodes = filtered_context_nodes + legal_s_nodes
                current_s_set = {
                    (node.target_variable, node.context_dimension, node.origin.value)
                    for node in merged_nodes
                }
                converged = (current_s_set == prev_s_node_set) or (round_num >= self._max_rounds)
                prev_s_node_set = current_s_set

                state = ResolutionState(
                    round=round_num,
                    s_nodes=filtered_context_nodes,
                    legal_s_nodes=legal_s_nodes,
                    data_gaps=data_gaps,
                    hard_constraints=hard_constraints,
                    p_star_values=p_star_values,
                    proxy_penalties=proxy_penalties,
                    proxy_validity=proxy_validity,
                    requires_expert_review=requires_expert_review,
                    expert_review_reasons=expert_review_reasons,
                    converged=converged,
                    feasible=True,
                )
                if converged:
                    break

            if tr_result is None or state is None or diagram is None:
                return _finalize_transport_loop_result(
                    TransportabilityResult(
                        query=f"P*({query_outcome}|do({query_treatment}))",
                        status=TransportabilityStatus.UNSUPPORTED,
                        transport_mode=TransportMode.NONE,
                        base_confidence=0.0,
                        final_confidence=0.0,
                        feasible=False,
                        warnings=["Transportability resolution failed unexpectedly."],
                        source_context_id=source_context.context_id,
                        target_context_id=target_context.context_id,
                        identification_engine="simplified_legacy",
                        identification_trace=["resolution_loop:unexpected_failure"],
                        unsupported_reason="resolution_loop_unexpected_failure",
                    ),
                    privacy_context=privacy_context,
                )
            return _finalize_transport_loop_result(
                _build_final_result(tr_result=tr_result, state=state, diagram=diagram),
                privacy_context=privacy_context,
            )
        finally:
            # Per-run cache isolation.
            self._cache_clear()


def _run_transport_solver(
    *,
    diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
    solver_mode: str,
    allow_degraded_transport: bool,
    capability_contract: CausalCapabilityContract | None,
    pag_identification_policy: str | None,
    pag_max_dag_samples: int,
    pag_threshold: float,
    pag_seed: int,
    surrogate_data_profile: object,
    privacy_context: TransportPrivacyContext | None,
) -> dict[str, Any]:
    result = solve_transportability(
        selection_diagram=diagram,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        solver_mode=solver_mode,
        allow_degraded_transport=allow_degraded_transport,
        capability_contract=capability_contract,
        pag_identification_policy=pag_identification_policy,
        pag_max_dag_samples=pag_max_dag_samples,
        pag_threshold=pag_threshold,
        pag_seed=pag_seed,
        surrogate_data_profile=surrogate_data_profile,
        privacy_context=privacy_context,
    )
    return {"transport_result": result.model_dump(mode="json")}


@dataclass(frozen=True)
class RunTransportabilityNode:
    """Execute the transportability resolution loop for the active workflow.

    Consumes causal reports, contexts, legal constraints, and capability
    metadata, then persists a ``TransportabilityResult`` together with any
    updated causal report or capability contract artifacts.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def prepare_cache_input(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> PreparedSKGRead | None:
        """Bind cache lookup to the selected academic source database."""
        del ctx
        db_path_raw = state.params.get("skg_db_path")
        if not isinstance(db_path_raw, str) or not db_path_raw.strip():
            return None
        db_path = Path(db_path_raw)
        index_dir_raw = state.params.get("skg_index_dir")
        index_dir = Path(str(index_dir_raw)) if index_dir_raw else db_path.parent
        return SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)

    @staticmethod
    def _missing_report_outcome(
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        try:
            _resolve_query_treatment_for_blocking(state, None)
            _resolve_query_outcome_for_blocking(state, None)
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        if _is_serious_transport_profile(state):
            return _persist_blocking_transportability_result(
                ctx=ctx,
                state=state,
                reason="missing_causal_report",
                message=(
                    "No causal report artifact found; persisted unsupported "
                    "transportability result for serious workflow traceability."
                ),
            )
        return NodeOutcome(
            status="skip",
            state=state,
            events=[
                NodeEvent(
                    level="info",
                    message="No causal report artifact found; skip transportability.",
                )
            ],
        )

    @staticmethod
    def _bind_privacy_context(
        ctx: ExecutionContext,
        privacy_context: TransportPrivacyContext | None,
        input_refs: list[InputRef],
    ) -> TransportPrivacyContext | None:
        if privacy_context is None:
            return None
        return privacy_context.model_copy(
            update={
                "store": ctx.store,
                "inputs": tuple([*privacy_context.inputs, *input_refs]),
            }
        )

    @staticmethod
    def _select_skg_query(
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> tuple[SKGQuery | _NullSKG, bool] | None:
        prepared_read = ctx.prepared_skg_read
        configured_skg_path = state.params.get("skg_db_path")
        if prepared_read is not None and isinstance(configured_skg_path, str):
            if not prepared_read.matches_path(configured_skg_path):
                return None
            return prepared_read.query, False
        skg_query = _build_skg_query(
            db_path=configured_skg_path,
            index_dir=state.params.get("skg_index_dir"),
        )
        return skg_query, isinstance(skg_query, SKGQuery)

    @staticmethod
    def _missing_context_outcome(
        *,
        ctx: ExecutionContext,
        state: ExperimentState,
        causal_report: CausalEffectReport,
        report_ref: CausalEffectReportRef,
        source_context: ContextProfile | None,
        target_context: ContextProfile | None,
    ) -> NodeOutcome:
        if _is_serious_transport_profile(state):
            return _persist_blocking_transportability_result(
                ctx=ctx,
                state=state,
                reason="missing_source_or_target_context",
                message=(
                    "Missing source/target context profile; persisted unsupported "
                    "transportability result for serious workflow traceability."
                ),
                causal_report=causal_report,
                report_ref=report_ref,
                source_context=source_context,
                target_context=target_context,
            )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["transportability_warning"] = (
            "missing_source_or_target_context: transportability skipped"
        )
        return NodeOutcome(
            status="skip",
            state=new_state,
            events=[
                NodeEvent(
                    level="warn",
                    message=(
                        "Missing source/target context profile; transportability check skipped."
                    ),
                )
            ],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        candidate_request: TransportabilityCandidateRequestV1 | None = None
        if _CANDIDATE_REQUEST_STATE_KEY in state.params:
            try:
                candidate_request = _parse_conditional_transport_request(
                    state.params[_CANDIDATE_REQUEST_STATE_KEY]
                )
            except InvalidTransportInput as exc:
                return _invalid_transport_input_outcome(state, exc)

        report_ref_raw = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if report_ref_raw is None:
            if candidate_request is not None:
                return _candidate_missing_input_outcome(state, "causal_report")
            return self._missing_report_outcome(ctx, state)

        try:
            report_ref = CausalEffectReportRef.model_validate(
                report_ref_raw.model_dump(mode="json")
            )
            if candidate_request is not None:
                report_ref = profile_bound_ref(ctx.store, report_ref)
            causal_report = load_causal_effect_report(
                _ensure_ir_artifact_store(ctx.store), report_ref
            )
        except _TRANSPORT_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load CausalEffectReport: {exc}",
                ),
            )

        try:
            treatment = _resolve_query_treatment(state, causal_report)
            outcome = _resolve_query_outcome(state, causal_report)
            source_context = _resolve_context_profile(state.params.get("source_context"))
            target_context = _resolve_context_profile(state.params.get("target_context"))
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        if source_context is None or target_context is None:
            if candidate_request is not None:
                return _candidate_missing_input_outcome(
                    state,
                    "source_context_and_target_context",
                )
            return self._missing_context_outcome(
                ctx=ctx,
                state=state,
                causal_report=causal_report,
                report_ref=report_ref,
                source_context=source_context,
                target_context=target_context,
            )

        try:
            graph_source = _resolve_causal_graph_source(ctx, state)
            graph = graph_source[1] if graph_source is not None else None
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        if graph is None:
            if candidate_request is not None:
                return _candidate_missing_input_outcome(state, "selected_causal_graph")
            if _is_serious_transport_profile(state):
                return _persist_blocking_transportability_result(
                    ctx=ctx,
                    state=state,
                    reason="missing_causal_graph",
                    message=(
                        "No causal graph available; persisted unsupported "
                        "transportability result for serious workflow traceability."
                    ),
                    causal_report=causal_report,
                    report_ref=report_ref,
                    source_context=source_context,
                    target_context=target_context,
                )
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            new_state.params["transportability_warning"] = (
                "missing_causal_graph: transportability skipped"
            )
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="No causal graph available; transportability check skipped.",
                    )
                ],
            )

        try:
            resolved_inputs = _resolve_transport_execution_inputs(
                state,
                causal_report,
                graph,
                privacy_context_resolver=_resolve_transport_privacy_context,
            )
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        treatment = resolved_inputs.query_treatment
        outcome = resolved_inputs.query_outcome
        policy_spec = resolved_inputs.policy_spec
        pag_identification_policy = resolved_inputs.pag_identification_policy
        pag_max_dag_samples = resolved_inputs.pag_max_dag_samples
        pag_threshold = resolved_inputs.pag_threshold
        pag_seed = resolved_inputs.pag_seed
        transport_solver_mode = resolved_inputs.solver_mode
        surrogate_data_profile = resolved_inputs.surrogate_data_profile
        allow_degraded_transport = resolved_inputs.allow_degraded_transport
        normalization_warnings = resolved_inputs.normalization_warnings
        capability_contract, capability_ref = _resolve_or_build_capability_contract(ctx, state)
        input_refs = [
            InputRef(
                artifact_id=report_ref.artifact_id,
                role="causal_report",
                manifest_profile_sha256=report_ref.manifest_profile_sha256,
            )
        ]
        privacy_context = self._bind_privacy_context(
            ctx,
            resolved_inputs.privacy_context,
            input_refs,
        )

        dataset_registry = _build_dataset_registry(state.params.get("dataset_registry_db_path"))
        skg_selection = self._select_skg_query(ctx, state)
        if skg_selection is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Prepared SKG source path does not match transport selector input.",
                ),
            )
        skg_query, owns_skg_query = skg_selection
        legal_kg_db_path = _coerce_path(state.params.get("legal_kg_db_path"))

        loop = TransportabilityResolutionLoop(
            dataset_registry=dataset_registry,
            legal_kg_db_path=legal_kg_db_path,
            skg_query=skg_query,
            max_rounds=MAX_ROUNDS,
            proxy_threshold=PROXY_FALLBACK_THRESHOLD,
        )

        candidate_attempt: _ConditionalCandidateAttempt | None = None
        candidate_handler: Callable[[TransportabilityResult], TransportabilityResult] | None = None
        if candidate_request is not None:
            try:
                candidate_attempt = _bind_conditional_candidate_attempt(
                    ctx=ctx,
                    current_state=state,
                    request=candidate_request,
                    node=self,
                )
            except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as exc:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=f"Conditional transport candidate attempt is not admitted: {exc}",
                    ),
                )
            if graph_source is None:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_MISSING_INPUT,
                        message="Conditional transport candidate requires an exact selected graph ref.",
                    ),
                )

            def _attach_candidate(
                refusal: TransportabilityResult,
            ) -> TransportabilityResult:
                if (
                    refusal.status is not TransportabilityStatus.UNSUPPORTED
                    or refusal.transport_mode is not TransportMode.NONE
                    or refusal.feasible
                    or not refusal.unsupported_reason
                    or not refusal.requires_expert_review
                    or refusal.unsupported_reason not in refusal.expert_review_reasons
                    or "legal_source_relation_refusal" not in refusal.metadata
                    or refusal.base_confidence != 0.0
                    or refusal.final_confidence != 0.0
                    or refusal.transport_formula is not None
                ):
                    raise ValueError("conditional_transport_candidate_requires_exact_legal_refusal")
                diagnostic = _conditional_transport_candidate_diagnostic(
                    ctx=ctx,
                    state=state,
                    request=candidate_request,
                    attempt=candidate_attempt,
                    graph_ref=graph_source[0],
                    graph=graph_source[1],
                    source_context=source_context,
                    target_context=target_context,
                    causal_report_ref=report_ref,
                    capability_contract=capability_contract,
                    query_treatment=treatment,
                    query_outcome=outcome,
                    solver_mode=transport_solver_mode,
                    allow_degraded_transport=allow_degraded_transport,
                    privacy_context=privacy_context,
                )
                payload = refusal.model_dump(mode="json")
                payload.update(
                    {
                        "schema_version": "2.2",
                        "candidate_diagnostics": diagnostic.model_dump(mode="json"),
                        "query": f"P*({outcome}|do({treatment}))",
                        "source_graph_type": graph_source[1].graph_type.value,
                        "source_graph_sha256": graph_content_sha256(graph_source[1]),
                        "source_context_id": source_context.context_id,
                        "target_context_id": target_context.context_id,
                    }
                )
                candidate_result = TransportabilityResult.model_validate(payload)
                _require_candidate_transport_result_within_output_budget(candidate_result)
                return candidate_result

            candidate_handler = _attach_candidate

        try:
            transport_result = loop.resolve(
                source_context=source_context,
                target_context=target_context,
                causal_graph=graph,
                query_treatment=treatment,
                query_outcome=outcome,
                policy_spec=policy_spec,
                pag_identification_policy=pag_identification_policy,
                pag_max_dag_samples=pag_max_dag_samples,
                pag_threshold=pag_threshold,
                pag_seed=pag_seed,
                solver_mode=transport_solver_mode,
                surrogate_data_profile=surrogate_data_profile,
                allow_degraded_transport=allow_degraded_transport,
                capability_contract=capability_contract,
                privacy_context=privacy_context,
                candidate_refusal_handler=candidate_handler,
            )
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        finally:
            if owns_skg_query and isinstance(skg_query, SKGQuery):
                skg_query.close()

        transport_result = transport_result.model_copy(
            update={
                "schema_version": "2.2",
                "warnings": [*transport_result.warnings, *normalization_warnings],
            }
        )
        try:
            _require_candidate_transport_result_within_output_budget(transport_result)
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)

        candidate_diagnostic = transport_result.candidate_diagnostics
        result_inputs = input_refs
        if candidate_diagnostic is not None:
            result_inputs = list(candidate_diagnostic.inputs.lineage_refs)
            selected_graph_artifact = candidate_diagnostic.inputs.graph_ref.artifact_id
            seen_member_refs: set[tuple[str, str | None]] = set()
            for evaluation in candidate_diagnostic.evaluations:
                member_ref = evaluation.member_graph_ref
                ref_key = (str(member_ref.artifact_id), member_ref.manifest_profile_sha256)
                if (
                    str(member_ref.artifact_id) != str(selected_graph_artifact)
                    and ref_key not in seen_member_refs
                ):
                    result_inputs.append(
                        _candidate_input_ref(
                            member_ref,
                            f"transportability_candidate_member_graph:{evaluation.member_sha256}",
                        )
                    )
                    seen_member_refs.add(ref_key)
            if privacy_context is not None:
                result_inputs.extend(privacy_context.inputs)
        transport_ref = persist_transportability_result(
            _ensure_ir_artifact_store(ctx.store),
            transport_result,
            inputs=result_inputs,
            schema_version=transport_result.schema_version,
            return_selected_profile=True,
        )
        if transport_ref.manifest_profile_sha256 is None:
            raise ValueError("transportability_result_selected_profile_missing")
        report_update = {"transport_result": transport_result, "schema_version": "1.1"}
        report_schema_version = "1.1"
        updated_report = causal_report.model_copy(update=report_update)
        updated_report_ref = persist_causal_effect_report(
            _ensure_ir_artifact_store(ctx.store),
            updated_report,
            schema_version=report_schema_version,
            return_selected_profile=True,
            inputs=[
                InputRef(
                    artifact_id=report_ref.artifact_id,
                    role="causal_report_prev",
                    manifest_profile_sha256=report_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=transport_ref.artifact_id,
                    role="transportability_result",
                    manifest_profile_sha256=transport_ref.manifest_profile_sha256,
                ),
            ],
        )

        if candidate_request is not None:
            if updated_report_ref.manifest_profile_sha256 is None:
                raise ValueError("conditional_transport_report_selected_profile_missing")
            persisted_result = load_transportability_result(
                _ensure_ir_artifact_store(ctx.store),
                transport_ref,
            )
            persisted_report = load_causal_effect_report(
                _ensure_ir_artifact_store(ctx.store),
                updated_report_ref,
            )
            if persisted_result.model_dump(mode="json") != transport_result.model_dump(
                mode="json"
            ) or persisted_report.model_dump(mode="json") != updated_report.model_dump(mode="json"):
                raise ValueError("conditional_transport_selected_output_content_mismatch")
            report_manifest = ctx.store.get_manifest(updated_report_ref.artifact_id)
            result_edges = [
                edge for edge in report_manifest.inputs if edge.role == "transportability_result"
            ]
            if len(result_edges) != 1:
                raise ValueError("conditional_transport_report_result_edge_count_mismatch")
            result_edge = result_edges[0]
            if str(result_edge.artifact_id) != str(transport_ref.artifact_id):
                raise ValueError("conditional_transport_report_result_edge_artifact_mismatch")
            if result_edge.manifest_profile_sha256 != transport_ref.manifest_profile_sha256:
                raise ValueError("conditional_transport_report_result_edge_profile_mismatch")
            ctx.run.add_output(transport_ref)
            ctx.run.add_output(updated_report_ref)

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["transportability_status"] = transport_result.status.value
        new_state.params["transportability_transport_mode"] = transport_result.transport_mode.value
        new_state.params["transportability_identification_engine"] = (
            transport_result.identification_engine
        )
        new_state.params["transportability_capability_hash"] = (
            capability_contract.dependency_fingerprint
        )
        new_state.params["transportability_degradation_policy"] = (
            capability_contract.degradation_policy
        )
        if transport_result.id_confidence_under_pag is not None:
            new_state.params["transportability_id_confidence_under_pag"] = (
                transport_result.id_confidence_under_pag
            )
        else:
            new_state.params.pop("transportability_id_confidence_under_pag", None)
        new_state.params.pop("transportability_warning", None)
        new_state.artifacts_index[ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF] = capability_ref
        new_state.causal_capability_contract_ref = capability_ref
        new_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = transport_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = updated_report_ref

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[capability_ref, transport_ref, updated_report_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Transportability resolved: "
                        f"status={transport_result.status.value}, "
                        f"mode={transport_result.transport_mode.value}, "
                        f"engine={transport_result.identification_engine}, "
                        f"rounds={transport_result.resolution_rounds}, "
                        f"feasible={transport_result.feasible}"
                    ),
                )
            ],
        )


def _persist_blocking_transportability_result(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    reason: str,
    message: str,
    causal_report: CausalEffectReport | None = None,
    report_ref: CausalEffectReportRef | None = None,
    source_context: ContextProfile | None = None,
    target_context: ContextProfile | None = None,
) -> NodeOutcome:
    capability_contract, capability_ref = _resolve_or_build_capability_contract(ctx, state)
    input_refs: list[InputRef] = []
    if report_ref is not None:
        input_refs.append(
            InputRef(
                artifact_id=report_ref.artifact_id,
                role="causal_report",
                manifest_profile_sha256=report_ref.manifest_profile_sha256,
            )
        )

    transport_result = _build_blocking_transportability_result(
        state=state,
        reason=reason,
        message=message,
        causal_report=causal_report,
        source_context=source_context,
        target_context=target_context,
    ).model_copy(update={"schema_version": "2.2"})
    transport_ref = persist_transportability_result(
        _ensure_ir_artifact_store(ctx.store),
        transport_result,
        inputs=input_refs,
        schema_version=transport_result.schema_version,
        return_selected_profile=True,
    )
    if transport_ref.manifest_profile_sha256 is None:
        raise ValueError("transportability_result_selected_profile_missing")

    artifacts = [capability_ref, transport_ref]
    new_state = branch_state(state, write_paths=_SPEC.state_writes).state
    new_state.params["transportability_status"] = transport_result.status.value
    new_state.params["transportability_transport_mode"] = transport_result.transport_mode.value
    new_state.params["transportability_identification_engine"] = (
        transport_result.identification_engine
    )
    new_state.params["transportability_capability_hash"] = (
        capability_contract.dependency_fingerprint
    )
    new_state.params["transportability_degradation_policy"] = capability_contract.degradation_policy
    new_state.params.pop("transportability_id_confidence_under_pag", None)
    new_state.params["transportability_warning"] = f"{reason}: {message}"
    new_state.params["transport_required"] = True
    new_state.artifacts_index[ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF] = capability_ref
    new_state.causal_capability_contract_ref = capability_ref
    new_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = transport_ref

    if causal_report is not None and report_ref is not None:
        updated_report = causal_report.model_copy(
            update={"schema_version": "1.1", "transport_result": transport_result}
        )
        updated_report_ref = persist_causal_effect_report(
            _ensure_ir_artifact_store(ctx.store),
            updated_report,
            schema_version="1.1",
            return_selected_profile=True,
            inputs=[
                InputRef(
                    artifact_id=report_ref.artifact_id,
                    role="causal_report_prev",
                    manifest_profile_sha256=report_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=transport_ref.artifact_id,
                    role="transportability_result",
                    manifest_profile_sha256=transport_ref.manifest_profile_sha256,
                ),
            ],
        )
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = updated_report_ref
        artifacts.append(updated_report_ref)

    profile = _transport_execution_profile(state)
    return NodeOutcome(
        status="ok",
        state=new_state,
        artifacts=artifacts,
        events=[
            NodeEvent(
                level="warn",
                code="transportability.blocked_prerequisite",
                message=message,
                attrs={"reason": reason, "execution_profile": profile or "unknown"},
            )
        ],
    )


def _is_serious_transport_profile(state: ExperimentState) -> bool:
    return _transport_execution_profile(state) in _SERIOUS_TRANSPORT_PROFILES


def _evaluate_legal_constraints(
    *,
    target_context: ContextProfile,
    policy_spec: Mapping[str, Any] | None,
    causal_graph: CausalGraphModel,
    legal_kg_db_path: Path | None,
) -> LegalConstraintSet:
    policy_payload = dict(policy_spec) if policy_spec else {}
    domain = str(policy_payload.get("domain", ""))
    return evaluate_transport_constraints(
        jurisdiction=target_context.context_id,
        policy_domain=domain,
        policy_spec=policy_payload,
        causal_graph=causal_graph.model_dump(mode="json"),
        legal_kg_db_path=legal_kg_db_path,
    )


def _build_skg_query(db_path: Any, index_dir: Any) -> SKGQuery | _NullSKG:
    return _build_skg_query_impl(db_path, index_dir, query_type=SKGQuery)


__all__ = [
    "ResolutionState",
    "RunTransportabilityNode",
    "TransportabilityResolutionLoop",
]
