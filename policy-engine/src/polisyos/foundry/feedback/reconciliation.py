"""Reconcile persisted fixed-point execution evidence without promoting authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts import (
    FeedbackConfig,
    FeedbackConfigRef,
    FeedbackMapEvaluationRecord,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    FeedbackTrace,
    FeedbackTraceRef,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    MethodExecutionBundle,
    MethodExecutionBundleRef,
    SimulationResult,
    StateDelta,
    StateDeltaRef,
)
from polisyos.foundry.feedback.config import PreparedFeedbackConfig, prepare_feedback_config
from polisyos.foundry.feedback.diagnostics import converged

ReconciliationStatus = Literal["recomputed", "not_established"]


@dataclass(frozen=True)
class FeedbackExecutionReconciliation:
    """Per-property reconciliation outcomes for one selected feedback result."""

    source_binding_status: ReconciliationStatus
    final_materialization_status: ReconciliationStatus
    graph_invocation_status: ReconciliationStatus
    final_delta_base_status: ReconciliationStatus
    fixed_point_tolerance_status: ReconciliationStatus
    fixed_point_tolerance_satisfied: bool | None
    solver_convergence_claim_matches: bool | None
    limitations: tuple[str, ...] = ()


def reconcile_feedback_execution(
    *,
    simulation_result: SimulationResult,
    execution_input_basis: FoundryExecutionInputBasis,
    execution_input_basis_ref: FoundryExecutionInputBasisRef,
    feedback_config: FeedbackConfig,
    feedback_config_ref: FeedbackConfigRef,
    feedback_result: FeedbackSolveResult,
    feedback_result_ref: FeedbackResultRef,
    feedback_trace: FeedbackTrace,
    feedback_trace_ref: FeedbackTraceRef,
    state_delta: StateDelta,
    state_delta_ref: StateDeltaRef,
    method_execution_bundle: MethodExecutionBundle | None = None,
    method_execution_bundle_ref: MethodExecutionBundleRef | None = None,
) -> FeedbackExecutionReconciliation:
    """Join selected feedback artifacts and recompute the final map tolerance.

    All artifact bytes must already have been opened through the caller's exact
    selected-reference and schema-aware reader. This function performs no CAS reads.
    A successful result establishes only the listed identities and fixed-point
    tolerance predicate; it does not establish causal validity or authority.
    """
    context = execution_input_basis.feedback_execution_context
    if (
        simulation_result.schema_version != "1.5"
        or simulation_result.execution_source_status != "feedback_basis"
        or simulation_result.execution_input_basis_ref is None
        or simulation_result.feedback_result_ref is None
        or execution_input_basis.schema_version != "1.3"
        or execution_input_basis.execution_mode != "feedback"
        or context is None
    ):
        raise ValueError("feedback_execution_selected_basis_required")
    for ref, label in (
        (simulation_result.execution_input_basis_ref, "simulation_basis"),
        (execution_input_basis_ref, "execution_basis"),
        (simulation_result.feedback_result_ref, "simulation_feedback_result"),
        (feedback_result_ref, "feedback_result"),
        (feedback_config_ref, "feedback_config"),
        (feedback_trace_ref, "feedback_trace"),
        (state_delta_ref, "state_delta"),
        (context.final_injected_state_snapshot_ref, "final_injected_state"),
    ):
        _require_selected_ref(ref, label)
    if not _same_ref(simulation_result.execution_input_basis_ref, execution_input_basis_ref):
        raise ValueError("feedback_execution_basis_reference_mismatch")
    if not _same_ref(simulation_result.feedback_result_ref, feedback_result_ref):
        raise ValueError("feedback_execution_result_reference_mismatch")
    if not _same_ref(context.feedback_result_ref, feedback_result_ref):
        raise ValueError("feedback_execution_context_result_reference_mismatch")
    if not _same_ref(context.feedback_trace_ref, feedback_trace_ref):
        raise ValueError("feedback_execution_context_trace_reference_mismatch")
    if not _same_ref(execution_input_basis.request.feedback_config_ref, feedback_config_ref):
        raise ValueError("feedback_execution_config_reference_mismatch")
    if not _same_ref(feedback_result.trace_ref, feedback_trace_ref):
        raise ValueError("feedback_execution_result_trace_reference_mismatch")
    if not _same_optional_ref(
        context.final_parameter_override_bundle_ref,
        feedback_result.final_parameter_override_bundle_ref,
    ):
        raise ValueError("feedback_execution_final_override_reference_mismatch")
    if context.final_parameter_override_bundle_ref is not None:
        _require_selected_ref(
            context.final_parameter_override_bundle_ref,
            "final_parameter_override",
        )

    if (method_execution_bundle is None) != (method_execution_bundle_ref is None):
        raise ValueError("feedback_execution_method_bundle_pair_mismatch")
    if method_execution_bundle_ref is not None:
        _require_selected_ref(method_execution_bundle_ref, "method_execution_bundle")
    if (context.final_method_execution_bundle_ref is None) != (method_execution_bundle_ref is None):
        raise ValueError("feedback_execution_context_method_bundle_mismatch")
    if context.final_method_execution_bundle_ref is not None and not _same_ref(
        context.final_method_execution_bundle_ref,
        method_execution_bundle_ref,
    ):
        raise ValueError("feedback_execution_context_method_bundle_mismatch")
    if method_execution_bundle is not None and not _bundle_matches_basis(
        method_execution_bundle,
        execution_input_basis,
    ):
        raise ValueError("feedback_execution_method_bundle_source_mismatch")

    final_record = _final_materialization_record(feedback_trace, context.final_map_evaluation_id)
    if state_delta.base_ref is None or not _same_ref(
        state_delta.base_ref, context.final_injected_state_snapshot_ref
    ):
        raise ValueError("feedback_execution_final_delta_base_mismatch")

    graph_status: ReconciliationStatus = "not_established"
    if context.execution_link_status == "captured":
        if (
            context.final_graph_invocation_id != final_record.graph_invocation_id
            or final_record.execution_link_status != "captured"
            or method_execution_bundle is None
            or method_execution_bundle_ref is None
            or not _bundle_contains_invocation(
                method_execution_bundle,
                context.final_graph_invocation_id,
                execution_input_basis,
            )
        ):
            raise ValueError("feedback_execution_final_graph_invocation_mismatch")
        graph_status = "recomputed"
    elif (
        context.final_graph_invocation_id is not None
        or final_record.graph_invocation_id is not None
        or final_record.execution_link_status != "not_established"
    ):
        raise ValueError("feedback_execution_unestablished_graph_link_mismatch")

    if (
        feedback_result.final_state.variable_ids != feedback_result.initial_state.variable_ids
        or tuple(feedback_result.final_state.variable_ids)
        != tuple(item.variable_id for item in feedback_config.variables)
    ):
        raise ValueError("feedback_execution_final_vector_identity_mismatch")
    if tuple(feedback_result.final_state.values) != tuple(final_record.mapped_values or ()):
        raise ValueError("feedback_execution_final_state_map_mismatch")

    prepared = prepare_feedback_config(
        feedback_config,
        initial_state=feedback_result.initial_state,
    )
    if not _state_profile_matches(feedback_result.initial_state, prepared) or not (
        _state_profile_matches(feedback_result.final_state, prepared)
    ):
        raise ValueError("feedback_execution_state_profile_mismatch")
    candidate = np.asarray(final_record.candidate_values, dtype=float)
    mapped = np.asarray(final_record.mapped_values, dtype=float)
    if (
        candidate.shape != mapped.shape
        or candidate.shape != prepared.initial_values.shape
        or not bool(np.all(np.isfinite(candidate)))
        or not bool(np.all(np.isfinite(mapped)))
    ):
        raise ValueError("feedback_execution_final_vectors_invalid")

    if (
        feedback_config.solver.budget_diagnostic_id is not None
        and feedback_config.solver.budget_tolerance is not None
    ):
        tolerance_status: ReconciliationStatus = "not_established"
        tolerance_satisfied: bool | None = None
        solver_claim_matches: bool | None = None
        limitations = ("final_budget_gap_not_recorded",)
    else:
        tolerance_satisfied = converged(
            candidate,
            mapped,
            mapped - candidate,
            prepared=prepared,
            budget_gap=None,
        )
        tolerance_status = "recomputed"
        solver_claim_matches = feedback_result.converged == tolerance_satisfied
        limitations = ()

    return FeedbackExecutionReconciliation(
        source_binding_status="recomputed",
        final_materialization_status="recomputed",
        graph_invocation_status=graph_status,
        final_delta_base_status="recomputed",
        fixed_point_tolerance_status=tolerance_status,
        fixed_point_tolerance_satisfied=tolerance_satisfied,
        solver_convergence_claim_matches=solver_claim_matches,
        limitations=limitations,
    )


def _final_materialization_record(
    trace: FeedbackTrace,
    expected_evaluation_id: str,
) -> FeedbackMapEvaluationRecord:
    """Return the unique completed final evaluation from a complete trace."""
    if trace.schema_version != "1.1" or trace.evaluation_scope != "complete":
        raise ValueError("feedback_execution_complete_trace_required")
    rows = tuple(
        item for item in trace.map_evaluations or () if item.phase == "final_materialization"
    )
    if len(rows) != 1 or rows[0].evaluation_id != expected_evaluation_id:
        raise ValueError("feedback_execution_final_evaluation_identity_mismatch")
    record = rows[0]
    if record.outcome != "completed" or record.mapped_values is None:
        raise ValueError("feedback_execution_final_evaluation_not_completed")
    return record


def _bundle_contains_invocation(
    bundle: MethodExecutionBundle,
    invocation_id: str | None,
    basis: FoundryExecutionInputBasis,
) -> bool:
    """Check a captured final graph ID against its actual selected bundle."""
    if invocation_id is None:
        return False
    if not _bundle_matches_basis(bundle, basis):
        return False
    rows = tuple(item for item in bundle.occurrences if item.invocation_id == invocation_id)
    return bool(rows) and all(item.status == "succeeded" for item in rows)


def _bundle_matches_basis(
    bundle: MethodExecutionBundle,
    basis: FoundryExecutionInputBasis,
) -> bool:
    """Check the selected capture belongs to this exact graph and plan."""
    return _same_ref(bundle.program_graph_ref, basis.program_graph_ref) and _same_ref(
        bundle.exec_plan_ref,
        basis.exec_plan_ref,
    )


def _state_profile_matches(
    state: FeedbackStateSnapshot,
    prepared: PreparedFeedbackConfig,
) -> bool:
    """Confirm a state vector uses the selected config's exact variable profile."""
    expected_lower = tuple(
        None if np.isneginf(value) else float(value) for value in prepared.lower_bounds
    )
    expected_upper = tuple(
        None if np.isposinf(value) else float(value) for value in prepared.upper_bounds
    )
    return (
        tuple(state.variable_ids) == tuple(prepared.variable_ids)
        and tuple(state.scales) == tuple(float(value) for value in prepared.scales)
        and tuple(state.weights) == tuple(float(value) for value in prepared.weights)
        and tuple(state.lower_bounds) == expected_lower
        and tuple(state.upper_bounds) == expected_upper
    )


def _require_selected_ref(ref: ArtifactRef | None, label: str) -> None:
    """Require a selected CAS identity before comparing evidence references."""
    if ref is None or ref.manifest_profile_sha256 is None:
        raise ValueError(f"feedback_execution_unselected_reference:{label}")


def _same_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    """Compare complete selected artifact identities, including profile digests."""
    return (
        left is not None
        and right is not None
        and artifact_ref_identity_key(left) == artifact_ref_identity_key(right)
    )


def _same_optional_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    """Compare nullable refs while preserving the meaning of two absent refs."""
    return (left is None and right is None) or _same_ref(left, right)
