"""Historical verification of selected acquisition evaluation retention.

This reader reopens persisted owner artifacts and the transaction-bound action
frontier. It records what was selected at that historical action, not present
permission, present source eligibility, or a new N5 occurrence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    load_core_json_artifact,
)
from polisyos.core.contracts import epoch
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    ResolvedAcquisitionEvaluation,
    basis_exact_values_equal,
    read_acquisition_evaluation_artifact,
    resolve_selected_acquisition_evaluation_parts,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRouteLoopReceiptV2,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.generation_cycle import GenerationCycleRecord, GenerationCycleRun
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.core.contracts import RunCandidateSimulationCheapConsequences
    from polisyos.runtime.http.resilience import GuardedDependencyProxy
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        VerifiedAcquisitionActionOutcome,
        VerifiedAcquisitionActionPhase,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
        AcquisitionEvaluationFrontierRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateEvaluationTerminalHistory,
        CandidateExperimentTerminalHistory,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        AcquisitionRetainedCurrentProjection,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


class AcquisitionRetentionHistoryVerification(BaseModel):
    """Exactly one verified history rendering for one selected action terminal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    history_entry: Mapping[str, object] | None = None
    legacy_receipt: AcquisitionRouteLoopReceipt | None = None
    terminal: AcquisitionRouteLoopReceiptV2 | None = None
    source_generation_run: GenerationCycleRun | None = None
    source_cycle: GenerationCycleRecord | None = None
    source_evaluation_job_id: str | None = None

    @model_validator(mode="after")
    def _one_result(self) -> Self:
        if (self.history_entry is None) == (self.legacy_receipt is None):
            raise ValueError("acquisition_history_verified_result_not_unique")
        if (self.source_generation_run is None) != (self.source_cycle is None):
            raise ValueError("acquisition_history_source_accumulator_incomplete")
        if self.history_entry is not None and (
            self.source_generation_run is not None
            or self.source_cycle is not None
            or self.source_evaluation_job_id is not None
            or self.terminal is not None
        ):
            raise ValueError("acquisition_history_retained_context_not_legacy")
        if self.terminal is not None and (
            self.legacy_receipt is None
            or self.terminal.terminal_outcome != "reentry_completed"
            or self.terminal.model_dump(
                mode="python",
                include=set(AcquisitionRouteLoopReceipt.model_fields) - {"schema_version"},
            )
            != self.legacy_receipt.model_dump(mode="python", exclude={"schema_version"})
        ):
            raise ValueError("acquisition_history_terminal_projection_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _VerifiedRetainedRoute:
    decision: AcquisitionEvaluationDecision
    prior_basis: AcquisitionEvaluationBasis
    current_basis: AcquisitionEvaluationBasis
    evaluation: ResolvedAcquisitionEvaluation
    growth: AcquisitionWorldGrowthReceipt
    continuation: AcquisitionRetainedContinuation


def _same_ref(left: ArtifactRef, right: ArtifactRef) -> bool:
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def project_retained_cheap_consequences(
    projection: AcquisitionRetainedCurrentProjection,
) -> RunCandidateSimulationCheapConsequences:
    """Map an already verified recorded projection without granting authority."""
    from polisyos.core.contracts import RunCandidateSimulationCheapConsequences
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedCurrentProjection,
    )

    if type(projection) is not AcquisitionRetainedCurrentProjection:
        raise TypeError("acquisition_retained_cheap_projection_untyped")
    return RunCandidateSimulationCheapConsequences.model_validate(
        {
            "source_cycle_index": projection.source_cycle_index,
            "candidate_id": projection.selected_candidate_id,
            "candidate_content_hash": projection.selected_candidate_content_hash,
            "grounding_status": projection.grounding.status,
            "grounding_current_valid": projection.grounding.current_valid,
            "value_status": projection.value_port.status,
            "value_decision_grade": projection.value_port.decision_grade,
            "value_authority_blockers": projection.value_port.authority_blockers,
            "value_ref": projection.value_port.value_ref,
            "voi_next_action": projection.voi_decision.next_action,
            "voi_reason": projection.voi_decision.reason,
            "terminal_kind": projection.terminal_kind,
            "refinement_decision": projection.refinement_decision.decision,
            "search_iteration_status": projection.search_iteration.status,
            "current_planner_report_ref": projection.current_planner_report_ref,
        }
    )


def verify_candidate_terminal_history(
    *,
    control_service: ControlPlaneService,
    head: AcquisitionActionHeadRecord,
    terminal_ref: ArtifactRef,
) -> CandidateEvaluationTerminalHistory:
    """Replay one selected candidate terminal and its transaction-bound frontier.

    This is a historical read, not a live lease or a current-source permit. The
    exact terminal profile comes from the action-head transaction; the bounded
    prior fold, action, budget window, basis, N5 and continuation are reopened
    through their existing owners. A missing link refuses the historical claim.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        ControlPlaneService,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateEvaluationTerminalHistory,
        _candidate_model_values_same,
        _candidate_ref_same,
        replay_candidate_acquisition_basis_for_history,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        read_candidate_acquisition_retained_continuation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
        AcquisitionRoutePhaseReceipt,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        CandidateAcquisitionWorldIntent,
        resolve_first_candidate_n4_prior,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_closure,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        _INTENT_KIND,
        _owner_record,
        _read_historical_action,
        _scope_from_action,
        verify_candidate_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_cycle import validate_candidate_source_continuation
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    if (
        type(control_service) is not ControlPlaneService
        or type(head) is not AcquisitionActionHeadRecord
        or not isinstance(terminal_ref, ArtifactRef)
        or not _candidate_ref_same(terminal_ref, terminal_ref)
        or terminal_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_terminal_history_owner_not_established")
    store = control_service._artifact_store
    events = control_service._diagnostic_event_log
    control = control_service._control_store
    sink = control_service.acquisition_route_sink
    if (
        type(sink) is not AcquisitionRouteLoopAuthoritySink
        or sink._artifact_store is not store
        or sink._event_log is not events
        or sink._control_store is not control
        or getattr(sink._core_source_resolver, "__self__", None) is not control_service
    ):
        raise ValueError("candidate_terminal_history_sink_not_established")
    chain = sink._candidate_selected_terminal_chain(head, terminal_ref)
    terminal = chain[-1].receipt
    if type(terminal) is not AcquisitionCandidateRouteLoopReceipt:
        raise ValueError("candidate_terminal_history_terminal_untyped")
    prior_closure = sink._candidate_prior_closure(terminal)
    action, executing = _read_historical_action(
        store=store, event_log=events, action_ref=terminal.candidate_action_ref
    )
    control_service.verify_candidate_source_budget_window_historical(
        closure=prior_closure, action=action
    )
    executing_rows = tuple(
        item
        for item in chain
        if type(item.receipt) is AcquisitionRoutePhaseReceipt
        and item.receipt.receipt_phase == "executing"
    )
    if (
        len(executing_rows) != 1
        or executing_rows[0].receipt_ref != action.action_phase_ref
        or not _candidate_model_values_same(executing_rows[0].receipt, executing)
        or action.action_job_id != terminal.job_id
        or action.action_generation != terminal.action_generation
        or action.route_id != terminal.route_id
    ):
        raise ValueError("candidate_terminal_history_action_mismatch")

    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=terminal.evaluation_decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    if type(decision) is not CandidateAcquisitionEvaluationDecision:
        raise ValueError("candidate_terminal_history_decision_untyped")
    current = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=decision.current_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    selected = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=terminal.selected_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        type(current) is not CandidateAcquisitionEvaluationBasis
        or type(selected) is not CandidateAcquisitionEvaluationBasis
        or current.basis_role != "prospective"
        or not _candidate_ref_same(decision.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(current.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(current.candidate_source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(
            current.candidate_world_intent_ref, decision.candidate_world_intent_ref
        )
        or not set(action.limitations).issubset(current.limitations)
    ):
        raise ValueError("candidate_terminal_history_current_basis_mismatch")
    for record in (decision, current):
        if (
            (record.tenant_id, record.cell_id, record.run_id, record.source_job_id)
            != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            or record.action_job_id != terminal.job_id
            or record.action_generation != terminal.action_generation
            or record.route_id != terminal.route_id
            or record.design_problem_ref != prior_closure.design_problem_ref
            or record.design_problem_basis_ref != prior_closure.design_problem_basis_ref
            or record.candidate_id != prior_closure.source_cycle.selected_candidate_ref
            or record.source_candidate_content_hash
            != prior_closure.source_cycle.selected_candidate_content_hash
        ):
            raise ValueError("candidate_terminal_history_record_scope_mismatch")
    if decision.compiled_ref != terminal.compiled_ref:
        raise ValueError("candidate_terminal_history_compiled_mismatch")

    identity = hashlib.sha256(
        canon.to_canonical_bytes(terminal.candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    intent = _owner_record(
        store=store,
        events=events,
        ref=decision.candidate_world_intent_ref,
        record_type=CandidateAcquisitionWorldIntent,
        kind=_INTENT_KIND,
        schema="polisyos.runtime.CandidateAcquisitionWorldIntent",
        version="1.2",
        phase="candidate_world_materialization_started",
        event_id="evt_candidate_world_intent_" + identity,
        inputs=(
            artifacts.input_ref_from_artifact_ref(
                terminal.candidate_action_ref, role="candidate_acquisition_action"
            ),
        ),
        compiled_ref=executing.compiled_ref,
        scope=_scope_from_action(action),
    )
    predecessors = _candidate_source_predecessors_for_verified_closure(
        store=store, closure=prior_closure
    )
    inputs = current.preparation_inputs
    binding = inputs.slot_binding
    expected_base = predecessors[-1].world_model_ref if predecessors else None
    if (
        not _candidate_ref_same(intent.candidate_action_ref, terminal.candidate_action_ref)
        or intent.action_phase_ref != action.action_phase_ref
        or (intent.tenant_id, intent.cell_id, intent.run_id, intent.action_job_id, intent.route_id)
        != (head.tenant_id, head.cell_id, head.run_id, head.job_id, head.route_id)
        or not _candidate_model_values_same(inputs.configured_profile, intent.configured_profile)
        or not _candidate_model_values_same(
            inputs.original_model_declaration, intent.original_model_declaration
        )
        or inputs.transaction_time != intent.transaction_time
        or not _candidate_ref_same(inputs.candidate_source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(inputs.base_world_model_ref, expected_base)
        or not _candidate_ref_same(
            inputs.base_data_snapshot_ref,
            world_model_artifact_views(
                intent.configured_profile.context_inputs.world_model_record
            ).data_snapshot_ref,
        )
        or binding.profile_selection_ref != action.profile_selection_ref
        or binding.candidate_digest != action.candidate_digest
        or binding.canonical_variable_id != action.canonical_variable_id
        or binding.target_slot_id != action.target_slot_id
    ):
        raise ValueError("candidate_terminal_history_intent_mismatch")

    prior = (
        resolve_selected_acquisition_evaluation_parts(
            artifact_store=store,
            control_store=control,
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            generation_run=prior_closure.generation_run,
            source_cycle=prior_closure.source_cycle,
            design_problem_ref=prior_closure.design_problem_ref,
        )
        if prior_closure.source_cycle.simulation.status == "joint_simulated"
        else None
    )
    if prior is None:
        if (
            prior_closure.candidate_basis_transitions
            or not prior_closure.generation_run.cycles
            or prior_closure.generation_run.cycles[-1] != prior_closure.source_cycle
        ):
            raise ValueError("candidate_terminal_history_prior_source_not_established")
        source = resolve_first_candidate_n4_prior(
            artifact_store=store,
            source_cycle=prior_closure.source_cycle,
            problem=prior_closure.design_problem_basis,
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            design_problem_ref=prior_closure.design_problem_ref,
        )
        prior_profile, prior_declaration = source.profile, source.model_declaration
    else:
        prior_profile, prior_declaration = (
            prior.input_record.profile,
            prior.handoff.model_declaration,
        )
    if not _candidate_model_values_same(
        inputs.configured_profile, prior_profile
    ) or not _candidate_model_values_same(inputs.original_model_declaration, prior_declaration):
        raise ValueError("candidate_terminal_history_prior_configuration_mismatch")
    global_limit = control_service.acquisition_source_global_budget_usd(closure=prior_closure)
    fresh_limit = action.selection.reentry_budget_usd
    replay_candidate_acquisition_basis_for_history(
        artifact_store=store,
        problem=prior_closure.design_problem_basis,
        basis=current,
        predecessors=predecessors,
        selected_evaluation=prior,
        fresh_limit_usd=fresh_limit,
        global_limit_usd=global_limit,
    )

    previous = None
    histories = prior_closure.candidate_terminal_history
    if decision.prior_basis_ref is not None:
        if prior is None or not predecessors or not histories:
            raise ValueError("candidate_terminal_history_prior_not_established")
        previous = read_acquisition_evaluation_artifact(
            store=store,
            event_log=events,
            ref=decision.prior_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        latest = histories[-1]
        previous_receipt = prior_closure.candidate_basis_transitions[-1]
        if (
            type(previous) is not CandidateAcquisitionEvaluationBasis
            or previous.basis_role != "evaluated"
            or not _candidate_ref_same(
                previous.candidate_action_ref, previous_receipt.candidate_action_ref
            )
            or not _candidate_ref_same(
                previous.candidate_world_intent_ref, previous_receipt.candidate_world_intent_ref
            )
            or not _candidate_ref_same(
                previous.candidate_source_ref, previous_receipt.candidate_source_ref
            )
            or not _candidate_ref_same(
                previous.selected_data_snapshot_ref, previous_receipt.data_snapshot_ref
            )
            or not _candidate_ref_same(
                previous.selected_world_model_ref, previous_receipt.world_model_ref
            )
            or not _candidate_model_values_same(
                previous.preparation_inputs, predecessors[-1].inputs
            )
            or not _candidate_model_values_same(previous.evaluation, prior.selected)
            or not _candidate_ref_same(latest.terminal.selected_basis_ref, decision.prior_basis_ref)
            or not _candidate_model_values_same(latest.selected_basis, previous)
            or not _candidate_model_values_same(latest.evaluation, prior)
            or not _candidate_model_values_same(
                latest.terminal.selected_evaluation, decision.prior_evaluation
            )
            or latest.frontier.frontier_ref != decision.expected_frontier_ref
            or latest.frontier.revision != decision.expected_frontier_revision
        ):
            raise ValueError("candidate_terminal_history_prior_binding_mismatch")
        if (
            (previous.tenant_id, previous.cell_id, previous.run_id, previous.source_job_id)
            != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            or previous.route_id != head.route_id
            or previous.design_problem_ref != prior_closure.design_problem_ref
            or previous.design_problem_basis_ref != prior_closure.design_problem_basis_ref
            or previous.candidate_id != decision.candidate_id
            or previous.source_candidate_content_hash
            != previous_receipt.basis_transition.source_candidate_content_hash
            or previous.action_generation != previous_receipt.action_generation
            or previous.action_job_id != previous_receipt.action_job_id
        ):
            raise ValueError("candidate_terminal_history_prior_scope_mismatch")
        previous_action, _ = _read_historical_action(
            store=store, event_log=events, action_ref=previous.candidate_action_ref
        )
        control_service.verify_candidate_source_budget_window_historical(
            closure=prior_closure, action=previous_action
        )
        replay_candidate_acquisition_basis_for_history(
            artifact_store=store,
            problem=prior_closure.design_problem_basis,
            basis=previous,
            predecessors=predecessors[:-1],
            selected_evaluation=prior,
            fresh_limit_usd=previous_action.selection.reentry_budget_usd,
            global_limit_usd=global_limit,
        )
        inherited = set(previous.limitations)
        retained = tuple(
            history
            for history in histories
            if history.head.action_generation > previous_receipt.action_generation
        )
        if tuple(history.head.action_generation for history in retained) != tuple(
            range(previous_receipt.action_generation + 1, terminal.action_generation)
        ):
            raise ValueError("candidate_terminal_history_limitations_not_established")
        for history in retained:
            if (
                history.terminal.terminal_outcome != "candidate_evaluation_retained"
                or history.continuation is None
                or not _candidate_ref_same(
                    history.terminal.selected_basis_ref, decision.prior_basis_ref
                )
                or not _candidate_model_values_same(history.selected_basis, previous)
                or not _candidate_model_values_same(history.evaluation, prior)
                or not (inherited | set(history.current_basis.limitations)).issubset(
                    history.continuation.limitations
                )
            ):
                raise ValueError("candidate_terminal_history_limitations_not_established")
            inherited.update(history.continuation.limitations)
        if not inherited.issubset(current.limitations):
            raise ValueError("candidate_terminal_history_limitations_not_established")
        equal = basis_exact_values_equal(previous, current)
        if decision.comparison_result == "equivalent" and not equal:
            raise ValueError("candidate_terminal_history_equivalence_mismatch")
        if decision.comparison_result == "different" and (
            equal
            or previous.predicate_provenance != "recomputed"
            or current.predicate_provenance != "recomputed"
        ):
            raise ValueError("candidate_terminal_history_difference_mismatch")
    elif decision.comparison_result != "not_established":
        raise ValueError("candidate_terminal_history_prior_not_established")

    frontier_ref = head.evaluation_frontier_ref
    if (
        frontier_ref is None
        or head.evaluation_frontier_before_ref != decision.expected_frontier_ref
    ):
        raise ValueError("candidate_terminal_history_frontier_transaction_mismatch")
    frontier = control.get_acquisition_evaluation_frontier_by_ref(frontier_ref)
    if (
        frontier is None
        or frontier.key
        != AcquisitionEvaluationFrontierKey(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            source_job_id=head.source_job_id,
            design_problem_ref=prior_closure.design_problem_ref,
            candidate_id=decision.candidate_id,
        )
        or frontier.basis_ref != str(terminal.selected_basis_ref.artifact_id)
        or frontier.basis_content_hash != selected.content_hash
        or frontier.selected_evaluation_witness_ref
        != str(terminal.selected_evaluation_witness_ref.artifact_id)
    ):
        raise ValueError("candidate_terminal_history_frontier_mismatch")

    reentry = None
    continuation = None
    evaluation = None
    if terminal.terminal_outcome == "candidate_evaluation_retained":
        if (
            previous is None
            or prior is None
            or decision.comparison_result != "equivalent"
            or not _candidate_ref_same(terminal.selected_basis_ref, decision.prior_basis_ref)
            or head.evaluation_frontier_ref != decision.expected_frontier_ref
            or frontier.revision != decision.expected_frontier_revision
            or frontier.selected_evaluation_content_hash != prior.execution.content_hash
            or terminal.current_continuation_ref is None
        ):
            raise ValueError("candidate_terminal_history_retention_not_established")
        continuation, evaluation = read_candidate_acquisition_retained_continuation(
            store=store,
            event_log=events,
            control_store=control,
            ref=terminal.current_continuation_ref,
            decision=decision,
            terminal=terminal,
            prior_closure=prior_closure,
        )
        if not (set(current.limitations) | set(previous.limitations)).issubset(
            continuation.limitations
        ):
            raise ValueError("candidate_terminal_history_limitations_not_established")
    else:
        if terminal.candidate_reentry_ref is None or decision.comparison_result == "equivalent":
            raise ValueError("candidate_terminal_history_reentry_not_established")
        reentry = verify_candidate_source_reentry_history(
            artifact_store=store,
            event_log=events,
            control_store=control,
            receipt_ref=terminal.candidate_reentry_ref,
            expected_tenant_id=head.tenant_id,
            expected_cell_id=head.cell_id,
            expected_run_id=head.run_id,
            expected_source_job_id=head.source_job_id,
            expected_action_job_id=head.job_id,
            expected_route_id=head.route_id,
            expected_action_generation=head.action_generation,
            expected_selected_action_ref=terminal.candidate_action_ref,
        )
        validate_candidate_source_continuation(prior_closure.generation_run, reentry)
        if reentry.new_cycle.simulation.status == "joint_simulated":
            evaluation = resolve_selected_acquisition_evaluation_parts(
                artifact_store=store,
                control_store=control,
                tenant_id=head.tenant_id,
                cell_id=head.cell_id,
                run_id=head.run_id,
                generation_run=reentry.continued_generation_run,
                source_cycle=reentry.new_cycle,
                design_problem_ref=prior_closure.design_problem_ref,
            )
        expected_witness = evaluation.execution.content_hash if evaluation else reentry.content_hash
        if (
            selected.basis_role != ("evaluated" if evaluation else "blocked")
            or (selected.tenant_id, selected.cell_id, selected.run_id, selected.source_job_id)
            != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            or selected.action_job_id != head.job_id
            or selected.action_generation != head.action_generation
            or selected.route_id != head.route_id
            or selected.design_problem_ref != prior_closure.design_problem_ref
            or selected.design_problem_basis_ref != prior_closure.design_problem_basis_ref
            or selected.candidate_id != decision.candidate_id
            or selected.source_candidate_content_hash != decision.source_candidate_content_hash
            or not _candidate_ref_same(selected.candidate_action_ref, terminal.candidate_action_ref)
            or not _candidate_ref_same(selected.candidate_source_ref, reentry.candidate_source_ref)
            or not _candidate_ref_same(
                selected.candidate_world_intent_ref, reentry.candidate_world_intent_ref
            )
            or not _candidate_ref_same(
                selected.selected_data_snapshot_ref, reentry.data_snapshot_ref
            )
            or not _candidate_ref_same(selected.selected_world_model_ref, reentry.world_model_ref)
            or not _candidate_model_values_same(
                selected.preparation_inputs, current.preparation_inputs
            )
            or selected.prepared_n5_configuration != current.prepared_n5_configuration
            or not (set(current.limitations) | set(reentry.limitations)).issubset(
                selected.limitations
            )
            or frontier.revision != decision.expected_frontier_revision + 1
            or frontier.decision_ref != str(terminal.evaluation_decision_ref.artifact_id)
            or frontier.selected_evaluation_content_hash != expected_witness
            or (evaluation is None) != (terminal.selected_evaluation is None)
            or (
                evaluation is not None
                and not _candidate_model_values_same(
                    terminal.selected_evaluation,
                    evaluation.selected.model_copy(
                        update={"basis_ref": terminal.selected_basis_ref}
                    ),
                )
            )
        ):
            raise ValueError("candidate_terminal_history_reentry_binding_mismatch")
        replay_candidate_acquisition_basis_for_history(
            artifact_store=store,
            problem=prior_closure.design_problem_basis,
            basis=selected,
            predecessors=predecessors,
            selected_evaluation=evaluation,
            fresh_limit_usd=fresh_limit,
            global_limit_usd=global_limit,
        )
    if (
        control.get_acquisition_action_head(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            route_id=head.route_id,
            action_generation=head.action_generation,
        )
        != head
    ):
        raise ValueError("candidate_terminal_history_head_changed")
    return CandidateEvaluationTerminalHistory(
        head=head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        action=action,
        decision=decision,
        current_basis=current,
        selected_basis=selected,
        evaluation=evaluation,
        reentry=reentry,
        continuation=continuation,
        frontier=frontier,
    )


def _candidate_experiment_frontier_transition_for_history(
    *,
    control_store: ControlPlaneStore | GuardedDependencyProxy,
    key: AcquisitionEvaluationFrontierKey,
    head: AcquisitionActionHeadRecord,
    expected_frontier_ref: str | None,
    expected_frontier_revision: int,
    selected_basis_ref: str,
    selected_basis_content_hash: str,
    decision_ref: str,
    selected_evaluation_witness_ref: str,
    selected_evaluation_content_hash: str | None,
) -> tuple[
    AcquisitionEvaluationFrontierRecord | None,
    AcquisitionEvaluationFrontierRecord | None,
]:
    """Reconstruct one committed terminal's immutable before/after frontier."""
    from polisyos.runtime.http.resilience import GuardedDependencyProxy
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
        ControlPlaneStore,
    )

    store_owner = (
        control_store._target if type(control_store) is GuardedDependencyProxy else control_store
    )
    if (
        type(store_owner) is not ControlPlaneStore
        or type(key) is not AcquisitionEvaluationFrontierKey
        or type(head) is not AcquisitionActionHeadRecord
    ):
        raise ValueError("candidate_experiment_terminal_frontier_owner_not_established")
    if head.evaluation_frontier_before_ref != expected_frontier_ref:
        raise ValueError("candidate_experiment_terminal_frontier_transaction_mismatch")

    frontier_before = (
        None
        if expected_frontier_ref is None
        else control_store.get_acquisition_evaluation_frontier_by_ref(expected_frontier_ref)
    )
    if (
        (frontier_before.revision if frontier_before is not None else 0)
        != expected_frontier_revision
        or (frontier_before.frontier_ref if frontier_before is not None else None)
        != expected_frontier_ref
        or (frontier_before is not None and frontier_before.key != key)
    ):
        raise ValueError("candidate_experiment_terminal_frontier_before_mismatch")

    if selected_evaluation_content_hash is None:
        if head.evaluation_frontier_ref not in {None, expected_frontier_ref}:
            raise ValueError("candidate_experiment_terminal_blocked_frontier_mismatch")
        return frontier_before, frontier_before

    frontier_after_ref = head.evaluation_frontier_ref
    if frontier_after_ref is None:
        raise ValueError("candidate_experiment_terminal_frontier_missing")
    frontier_after = control_store.get_acquisition_evaluation_frontier_by_ref(frontier_after_ref)
    if (
        frontier_after is None
        or frontier_after.frontier_ref != frontier_after_ref
        or frontier_after.key != key
        or frontier_after.revision != expected_frontier_revision + 1
        or frontier_after.basis_ref != selected_basis_ref
        or frontier_after.basis_content_hash != selected_basis_content_hash
        or frontier_after.decision_ref != decision_ref
        or frontier_after.selected_evaluation_witness_ref != selected_evaluation_witness_ref
        or frontier_after.selected_evaluation_content_hash != selected_evaluation_content_hash
    ):
        raise ValueError("candidate_experiment_terminal_frontier_after_mismatch")
    return frontier_before, frontier_after


def _verify_candidate_experiment_reuse_terminal_history(
    *,
    control_service: ControlPlaneService,
    head: AcquisitionActionHeadRecord,
    terminal_ref: ArtifactRef,
    terminal_verified: VerifiedAcquisitionActionPhase,
    committed: bool,
) -> CandidateExperimentTerminalHistory:
    """Replay a no-fetch occurrence against its signed action and prior N5.

    The selected action and budget window belong to the earlier physical
    acquisition. This terminal owns neither a new source attempt nor a new
    budget window; replaying those earlier limits establishes only the old
    evaluation's comparison inputs, not present permission or cost.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateExperimentTerminalHistory,
        _candidate_model_values_same,
        _candidate_ref_same,
        recompute_candidate_acquisition_basis_values,
        replay_candidate_acquisition_basis_for_history,
    )
    from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
        _candidate_experiment_inherited_limitations,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        read_candidate_acquisition_retained_continuation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        AcquisitionRouteLoop,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.candidate_experiment_reuse import (
        CandidateExperimentReuseActionSelection,
        _selected_predecessor_evaluation,
    )
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CandidateExperimentReuseOccurrence,
        read_candidate_experiment_reuse_occurrence,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_experiment_origin,
    )
    from polisyos.scientist.orchestration.engine import BudgetLedgerReentryBudgetWindow

    terminal = terminal_verified.receipt
    store = control_service._artifact_store
    events = control_service._diagnostic_event_log
    control = control_service._control_store
    sink = control_service.acquisition_route_sink
    if (
        type(terminal) is not AcquisitionCandidateExperimentTerminalReceiptV2
        or type(sink) is not AcquisitionRouteLoopAuthoritySink
    ):
        raise ValueError("candidate_experiment_reuse_terminal_owner_not_established")
    scope = {
        "tenant_id": head.tenant_id,
        "cell_id": head.cell_id,
        "run_id": head.run_id,
        "source_job_id": head.source_job_id,
        "route_id": head.route_id,
        "action_generation": head.action_generation,
    }
    phase_head = (
        control.get_acquisition_action_head_by_receipt(
            **scope, receipt_ref=terminal.predecessor_receipt_ref
        )
        if committed
        else head
    )
    if (
        type(phase_head) is not AcquisitionActionHeadRecord
        or phase_head.receipt_phase != "executing"
        or phase_head.head_generation
        != (head.head_generation - 1 if committed else head.head_generation)
        or phase_head.receipt_ref != terminal.predecessor_receipt_ref
        or phase_head.job_id != terminal.job_id
        or phase_head.action_generation != terminal.action_generation
        or phase_head.receipt_manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_experiment_reuse_terminal_predecessor_mismatch")
    executing_ref = ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(phase_head.receipt_ref),
        kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        media_type="application/json",
        manifest_profile_sha256=phase_head.receipt_manifest_profile_sha256,
    )
    executing_verified = sink._read_verified_action_phase(
        phase_head.receipt_ref, selected_ref=executing_ref
    )
    executing = executing_verified.receipt
    if type(executing) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_reuse_terminal_executing_untyped")

    # This first parse is untrusted: it supplies selectors only. The selected
    # occurrence owner, immutable Control job, signed PA2 and independently
    # replayed predecessor each reconcile the selectors before any use.
    candidate_occurrence = CandidateExperimentReuseOccurrence.model_validate(
        load_core_json_artifact(store, terminal.reuse_occurrence_ref)
    )
    candidate_selection = candidate_occurrence.selection
    if type(candidate_selection) is not CandidateExperimentReuseActionSelection:
        raise ValueError("candidate_experiment_reuse_selection_untyped")
    loop = AcquisitionRouteLoop(
        control_store=control,
        artifact_store=store,
        event_log=events,
        core_source_resolver=sink._core_source_resolver,
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        action_outcome_reader=sink,
    )
    origin = loop.resolve_candidate_experiment_predecessor_origin(
        run_id=head.run_id,
        predecessor_terminal_ref=candidate_selection.predecessor_terminal_ref,
        expected_action_generation=head.action_generation,
    )
    chain_before = origin.candidate_terminal_history_chain
    if (
        type(origin) is not VerifiedCandidateExperimentOrigin
        or len(chain_before) + 1 != head.action_generation
        or not chain_before
        or origin.current_terminal_history is not chain_before[-1]
    ):
        raise ValueError("candidate_experiment_reuse_prior_generation_missing")
    previous = chain_before[-1]
    context = getattr(sink, "_candidate_experiment_reuse_phase_action_context", None)
    if not callable(context):
        raise ValueError("candidate_experiment_reuse_authority_owner_not_composed")
    # The chain owner authenticates the selected immutable Control payload and
    # PA2/DS9 exactly once using this historical predecessor, never live grants.
    selection = candidate_selection
    phase_chain = sink._verified_candidate_experiment_phase_chain(
        phase_head,
        verified_origin=origin,
        reuse_verified_origin=True,
        candidate_reuse_selection=selection,
        expected_control_payload_ref=candidate_occurrence.control_payload_ref,
    )
    occurrence = read_candidate_experiment_reuse_occurrence(
        store,
        occurrence_ref=terminal.reuse_occurrence_ref,
        expected_selection=selection,
        expected_executing_phase_ref=executing_ref,
        expected_control_payload_ref=candidate_occurrence.control_payload_ref,
        expected_pa2_decision_ref=executing.authority_decision_ref,
    )
    selected_occurrence_ref = artifact_ref_for_manifest(
        store.get_manifest(terminal.reuse_occurrence_ref)
    )
    if not _candidate_ref_same(selected_occurrence_ref, terminal.reuse_occurrence_ref):
        raise ValueError("candidate_experiment_reuse_occurrence_profile_mismatch")
    chain = (*phase_chain, terminal_verified)
    if (
        len(chain) != 3
        or tuple(item.receipt.receipt_phase for item in chain)
        != ("requested", "executing", "terminal")
        or chain[0].receipt.predecessor_receipt_ref is not None
        or chain[0].event.state_before is not None
        or chain[1].receipt_ref != phase_head.receipt_ref
        or chain[1].durable_event_id != phase_head.durable_event_id
        or not all(sink._same_action_identity(chain[0].receipt, item.receipt) for item in chain[1:])
        or any(
            item.receipt.predecessor_receipt_ref != prior.receipt_ref
            or item.event.state_before != prior.receipt.receipt_phase
            or item.receipt.generated_at < prior.receipt.generated_at
            or prior.receipt.receipt_phase
            not in (sink._allowed_predecessor_phases(item.receipt) or ())
            for prior, item in pairwise(chain)
        )
        or any(item.event.state_after != item.receipt.receipt_phase for item in chain)
    ):
        raise ValueError("candidate_experiment_reuse_terminal_phase_history_invalid")
    if committed and (
        terminal_verified.durable_event_id != head.durable_event_id
        or any(
            getattr(terminal, field) != getattr(head, field)
            for field in (
                "tenant_id",
                "cell_id",
                "run_id",
                "source_job_id",
                "route_id",
                "action_generation",
                "job_id",
                "coarse_phase",
                "receipt_phase",
                "recovery_state",
                "predecessor_receipt_ref",
            )
        )
    ):
        raise ValueError("candidate_experiment_reuse_terminal_head_mismatch")

    prior_evaluation = _selected_predecessor_evaluation(previous)
    action = previous.action
    source = previous.source
    replay_window = previous.budget_window or previous.provenance_budget_window
    if (
        type(source) is not CandidateAcquisitionSource
        or type(replay_window) is not BudgetLedgerReentryBudgetWindow
        or previous.frontier_after is None
        or previous.selected_basis is None
        or previous.selected_basis.predicate_provenance != "recomputed"
        or not _candidate_ref_same(selection.predecessor_terminal_ref, previous.terminal_ref)
        or not _candidate_ref_same(
            selection.predecessor_action_ref, previous.terminal.candidate_action_ref
        )
        or not _candidate_ref_same(selection.predecessor_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(selection.source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(selection.n5_input_ref, prior_evaluation.selected.n5_input_ref)
        or not _candidate_ref_same(
            selection.n5_execution_ref, prior_evaluation.selected.n5_execution_ref
        )
        or not _candidate_ref_same(selection.n5_result_ref, prior_evaluation.selected.n5_result_ref)
        or selection.predecessor_action_generation != previous.head.action_generation
        or selection.action_generation != head.action_generation
        or selection.action_job_id != head.job_id
        or (selection.tenant_id, selection.cell_id, selection.run_id, selection.source_job_id)
        != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        or selection.route_id != origin.route_id
        or selection.source_payload_ref != origin.source_payload_ref
        or selection.request_content_hash != origin.request_content_hash
        or not _candidate_model_values_same(selection.policy_scope, origin.policy_scope)
        or not _candidate_ref_same(selection.policy_ref, origin.policy_ref)
        or terminal.capability_manifest_ref != origin.capability_manifest_ref
        or not _candidate_model_values_same(terminal.voi_decision, origin.source_cycle.voi_decision)
    ):
        raise ValueError("candidate_experiment_reuse_prior_selection_mismatch")

    blocked = terminal.terminal_outcome == "candidate_blocked"
    decision_ref_artifact = terminal.blocker_ref if blocked else terminal.evaluation_decision_ref
    if decision_ref_artifact is None:
        raise ValueError("candidate_experiment_reuse_decision_missing")
    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=decision_ref_artifact,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    current_basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=decision.current_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    expected_prior = prior_evaluation.selected.model_copy(
        update={"basis_ref": previous.terminal.selected_basis_ref}
    )
    previous_frontier = previous.frontier_after
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or type(current_basis) is not CandidateAcquisitionEvaluationBasis
        or current_basis.basis_role != "prospective"
        or (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
        or (decision.action_job_id, decision.action_generation, decision.route_id)
        != (head.job_id, head.action_generation, head.route_id)
        or (
            current_basis.tenant_id,
            current_basis.cell_id,
            current_basis.run_id,
            current_basis.source_job_id,
        )
        != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
        or (current_basis.action_job_id, current_basis.action_generation, current_basis.route_id)
        != (head.job_id, head.action_generation, head.route_id)
        or decision.design_problem_ref != origin.policy_scope.design_problem_ref
        or decision.design_problem_basis_ref != origin.policy_scope.design_problem_basis_ref
        or decision.candidate_id != origin.policy_scope.candidate_id
        or decision.compiled_ref != str(origin.policy_scope.compiled_ref.artifact_id)
        or decision.source_candidate_content_hash
        != origin.effective_source_cycle.selected_candidate_content_hash
        or current_basis.design_problem_ref != decision.design_problem_ref
        or current_basis.design_problem_basis_ref != decision.design_problem_basis_ref
        or current_basis.candidate_id != decision.candidate_id
        or current_basis.source_candidate_content_hash != decision.source_candidate_content_hash
        or not _candidate_ref_same(decision.candidate_action_ref, selection.predecessor_action_ref)
        or not _candidate_ref_same(
            current_basis.candidate_action_ref, selection.predecessor_action_ref
        )
        or not _candidate_ref_same(decision.candidate_source_ref, selection.source_ref)
        or not _candidate_ref_same(current_basis.candidate_source_ref, selection.source_ref)
        or not _candidate_ref_same(
            decision.candidate_world_intent_ref, current_basis.candidate_world_intent_ref
        )
        or not _candidate_ref_same(decision.reuse_occurrence_ref, terminal.reuse_occurrence_ref)
        or not _candidate_ref_same(
            current_basis.reuse_occurrence_ref, terminal.reuse_occurrence_ref
        )
        or not _candidate_ref_same(decision.prior_basis_ref, previous.terminal.selected_basis_ref)
        or not _candidate_model_values_same(decision.prior_evaluation, expected_prior)
        or decision.expected_frontier_ref != previous_frontier.frontier_ref
        or decision.expected_frontier_revision != previous_frontier.revision
        or decision.reason_codes
        != (current_basis.reason_codes if decision.comparison_result == "not_established" else ())
        or not set(_candidate_experiment_inherited_limitations(origin)).issubset(
            current_basis.limitations
        )
        or not set(action.limitations).issubset(current_basis.limitations)
    ):
        raise ValueError("candidate_experiment_reuse_evaluation_owner_mismatch")
    predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
        store=store,
        origin=origin,
        before_action_generation=previous.selected_basis.action_generation,
    )
    recorded_live_refusal = False
    try:
        replay_candidate_acquisition_basis_for_history(
            artifact_store=store,
            problem=origin.design_problem_basis,
            basis=current_basis,
            predecessors=predecessors,
            selected_evaluation=prior_evaluation,
            fresh_limit_usd=replay_window.fresh_limit_usd,
            global_limit_usd=replay_window.global_limit_usd,
        )
    except ValueError as exc:
        # The live implementation cannot be reconstructed retrospectively.
        # A prior producer's bounded refusal can still be carried as such,
        # never as a recomputed predicate or a successful reuse. Require the
        # historical inputs/witness to replay and the live-only early failure
        # to have produced no comparison values; arbitrary reasons fail closed.
        live_refusal_reasons = {
            "n5_prior_live_implementation_not_established",
            "n5_execution_witness_not_producer_observed",
            "n5_receiver_construction_not_established",
            "n5_live_implementation_changed",
        }
        if (
            str(exc) != "candidate_evaluation_history_basis_owner_replay_mismatch"
            or not blocked
            or decision.comparison_result != "not_established"
            or current_basis.predicate_provenance != "not_established"
            or len(current_basis.reason_codes) != 1
            or current_basis.reason_codes[0] not in live_refusal_reasons
            or bytes.fromhex(current_basis.effective_native_values_hex)
            != exact_n5_content_bytes({})
        ):
            raise
        _historical_values, historical_reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=store,
            problem=origin.design_problem_basis,
            preparation_inputs=current_basis.preparation_inputs,
            predecessors=predecessors,
            prior=prior_evaluation,
            prepared_n5_configuration=current_basis.prepared_n5_configuration,
            fresh_limit_usd=replay_window.fresh_limit_usd,
            global_limit_usd=replay_window.global_limit_usd,
            historical_read_only=True,
        )
        if historical_reasons:
            raise ValueError(
                "candidate_experiment_reuse_historical_inputs_not_established"
            ) from exc
        recorded_live_refusal = True
    equivalent = basis_exact_values_equal(current_basis, previous.selected_basis)
    if blocked:
        if (
            decision.comparison_result not in {"different", "not_established"}
            or (
                decision.comparison_result == "different"
                and (current_basis.predicate_provenance != "recomputed" or equivalent)
            )
            or (
                decision.comparison_result == "not_established"
                and current_basis.predicate_provenance != "not_established"
            )
            or terminal.blocker_reason
            not in {
                "candidate_experiment_reuse_numerical_basis_not_established",
                "candidate_experiment_reuse_numerical_basis_different",
            }
            or terminal.blocker_reason
            != "candidate_experiment_reuse_numerical_basis_" + decision.comparison_result
        ):
            raise ValueError("candidate_experiment_reuse_blocker_not_established")
        continuation = None
        evaluation = None
        selected_basis = None
    else:
        if (
            terminal.terminal_outcome != "candidate_evaluation_retained"
            or decision.comparison_result != "equivalent"
            or decision.predicate_provenance != "recomputed"
            or not equivalent
            or not _candidate_ref_same(
                terminal.selected_basis_ref, previous.terminal.selected_basis_ref
            )
            or not _candidate_ref_same(
                terminal.selected_evaluation_witness_ref, selection.n5_execution_ref
            )
            or not _candidate_model_values_same(terminal.selected_evaluation, expected_prior)
            or terminal.current_continuation_ref is None
        ):
            raise ValueError("candidate_experiment_reuse_retained_prior_mismatch")
        continuation, evaluation = read_candidate_acquisition_retained_continuation(
            store=store,
            event_log=events,
            control_store=control,
            ref=terminal.current_continuation_ref,
            decision=decision,
            terminal=terminal,
            prior_experiment_origin=origin,
        )
        if not _candidate_model_values_same(evaluation.selected, prior_evaluation.selected) or not (
            set(current_basis.limitations) | set(previous.selected_basis.limitations)
        ).issubset(continuation.limitations):
            raise ValueError("candidate_experiment_reuse_retained_history_mismatch")
        selected_basis = previous.selected_basis

    key = AcquisitionEvaluationFrontierKey(
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        source_job_id=head.source_job_id,
        design_problem_ref=origin.policy_scope.design_problem_ref,
        candidate_id=origin.policy_scope.candidate_id,
    )
    current_frontier = control.read_acquisition_evaluation_frontier(key)
    route_scope = {
        name: scope[name]
        for name in ("tenant_id", "cell_id", "run_id", "source_job_id", "route_id")
    }
    action_heads = control.list_acquisition_action_heads(**route_scope) if committed else ()
    latest_terminal = next(
        (row for row in reversed(action_heads) if row.receipt_phase == "terminal"), None
    )
    if committed:
        if head not in action_heads:
            raise ValueError("candidate_experiment_reuse_terminal_head_changed")
        if blocked:
            if (
                head.evaluation_frontier_before_ref != previous_frontier.frontier_ref
                or head.evaluation_frontier_ref not in {None, previous_frontier.frontier_ref}
                or control.get_acquisition_evaluation_frontier_by_ref(
                    previous_frontier.frontier_ref
                )
                != previous_frontier
            ):
                raise ValueError("candidate_experiment_reuse_blocked_frontier_changed")
            frontier_before = frontier_after = previous_frontier
        else:
            frontier_before, frontier_after = _candidate_experiment_frontier_transition_for_history(
                control_store=control,
                key=key,
                head=head,
                expected_frontier_ref=decision.expected_frontier_ref,
                expected_frontier_revision=decision.expected_frontier_revision,
                selected_basis_ref=str(terminal.selected_basis_ref.artifact_id),
                selected_basis_content_hash=selected_basis.content_hash,
                decision_ref=str(decision_ref_artifact.artifact_id),
                selected_evaluation_witness_ref=str(
                    terminal.selected_evaluation_witness_ref.artifact_id
                ),
                selected_evaluation_content_hash=evaluation.execution.content_hash,
            )
        if frontier_before != previous_frontier or (
            latest_terminal == head and current_frontier != frontier_after
        ):
            raise ValueError("candidate_experiment_reuse_frontier_changed")
    else:
        if current_frontier != previous_frontier:
            raise ValueError("candidate_experiment_reuse_frontier_before_mismatch")
        frontier_before = current_frontier
        frontier_after = current_frontier if blocked else None
    if (
        control.get_acquisition_action_head(**scope) != head
        or control.read_acquisition_evaluation_frontier(key) != current_frontier
        or (committed and control.list_acquisition_action_heads(**route_scope) != action_heads)
    ):
        raise ValueError("candidate_experiment_reuse_terminal_head_changed")
    return CandidateExperimentTerminalHistory(
        head=head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        origin=origin,
        phase_chain=chain,
        action=action,
        source=source,
        budget_window=None,
        decision=decision,
        current_basis=current_basis,
        selected_basis=selected_basis,
        evaluation=evaluation,
        reentry=None,
        continuation=continuation,
        frontier_before=frontier_before,
        frontier_after=frontier_after,
        reuse_occurrence=occurrence,
        reuse_occurrence_ref=selected_occurrence_ref,
        provenance_budget_window=replay_window,
        recorded_live_refusal=recorded_live_refusal,
    )


def verify_candidate_experiment_terminal_history(
    *,
    control_service: ControlPlaneService,
    head: AcquisitionActionHeadRecord,
    terminal_ref: ArtifactRef,
) -> CandidateExperimentTerminalHistory:
    """Replay one candidate-experiment terminal from its original signed history.

    ``head`` may be the exact pending predecessor while a selected terminal is
    prepared for the atomic SQL head/frontier transaction, or the committed
    terminal head during a fresh read. This reader authenticates historical
    PA2 bytes without treating the old decision as current permission or lease.
    """
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        ControlPlaneService,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateExperimentTerminalHistory,
        _candidate_model_values_same,
        _candidate_ref_same,
        replay_candidate_acquisition_basis_for_history,
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        read_candidate_experiment_acquisition_action_historical,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_experiment_origin,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_experiment_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_cycle import (
        generation_cycle_run_content_hash,
        validate_candidate_source_continuation,
    )

    if (
        type(control_service) is not ControlPlaneService
        or type(head) is not AcquisitionActionHeadRecord
        or type(terminal_ref) is not ArtifactRef
        or terminal_ref.kind != "runtime_quality.acquisition_route_loop_receipt"
        or terminal_ref.media_type != "application/json"
        or terminal_ref.manifest_profile_sha256 is None
        or set(type(terminal_ref).model_fields) != set(ArtifactRef.model_fields)
    ):
        raise ValueError("candidate_experiment_terminal_history_owner_not_established")
    store = control_service._artifact_store
    events = control_service._diagnostic_event_log
    control = control_service._control_store
    sink = control_service.acquisition_route_sink
    if (
        type(sink) is not AcquisitionRouteLoopAuthoritySink
        or sink._artifact_store is not store
        or sink._event_log is not events
        or sink._control_store is not control
        or getattr(sink._core_source_resolver, "__self__", None) is not control_service
    ):
        raise ValueError("candidate_experiment_terminal_history_sink_not_established")

    committed = str(
        terminal_ref.artifact_id
    ) == head.receipt_ref and terminal_ref.manifest_profile_sha256 == getattr(
        head, "receipt_manifest_profile_sha256", None
    )
    if str(terminal_ref.artifact_id) == head.receipt_ref and not committed:
        raise ValueError("candidate_experiment_terminal_profile_not_selected")
    if not committed and head.receipt_phase not in {
        "candidate_input_reentry_pending",
        "executing",
    }:
        raise ValueError("candidate_experiment_terminal_predecessor_not_current")
    scope = {
        "tenant_id": head.tenant_id,
        "cell_id": head.cell_id,
        "run_id": head.run_id,
        "source_job_id": head.source_job_id,
        "route_id": head.route_id,
        "action_generation": head.action_generation,
    }
    if control.get_acquisition_action_head(**scope) != head:
        raise ValueError("candidate_experiment_terminal_predecessor_changed")

    # Reuse the phase-head owner for all persisted ancestors. Do not call the
    # full action fold here: verify_action_head delegates to this function for
    # terminal generations, so a full fold would recurse.
    terminal_verified = sink._read_verified_action_phase(
        str(terminal_ref.artifact_id), selected_ref=terminal_ref
    )
    terminal = terminal_verified.receipt
    if type(terminal) is AcquisitionCandidateExperimentTerminalReceiptV2:
        return _verify_candidate_experiment_reuse_terminal_history(
            control_service=control_service,
            head=head,
            terminal_ref=terminal_ref,
            terminal_verified=terminal_verified,
            committed=committed,
        )
    if type(terminal) is not AcquisitionCandidateExperimentTerminalReceipt:
        raise ValueError("candidate_experiment_terminal_chain_untyped")
    if committed:
        phase_head = control.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=terminal.predecessor_receipt_ref,
        )
        expected_phase_generation = head.head_generation - 1
    else:
        phase_head = head
        expected_phase_generation = head.head_generation
    if (
        type(phase_head) is not AcquisitionActionHeadRecord
        or phase_head.head_generation != expected_phase_generation
        or phase_head.receipt_ref != terminal.predecessor_receipt_ref
        or phase_head.receipt_phase != "candidate_input_reentry_pending"
        or phase_head.job_id != terminal.job_id
        or phase_head.action_generation != terminal.action_generation
    ):
        raise ValueError("candidate_experiment_terminal_predecessor_binding_mismatch")
    pending_ref = ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(phase_head.receipt_ref),
        kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        media_type="application/json",
        manifest_profile_sha256=phase_head.receipt_manifest_profile_sha256,
    )
    pending_phase = sink._read_verified_action_phase(
        phase_head.receipt_ref, selected_ref=pending_ref
    ).receipt
    if type(pending_phase) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_terminal_pending_phase_untyped")
    # The phase owner reopens the signed request's earlier prefix. A full
    # current fold here would recursively verify this terminal again.
    _, _, _, origin = sink._candidate_experiment_phase_action_context(pending_phase)
    predecessor_history_chain = origin.candidate_terminal_history_chain
    if len(predecessor_history_chain) + 1 != head.action_generation:
        raise ValueError("candidate_experiment_terminal_prior_generation_missing")
    phase_chain = sink._verified_candidate_experiment_phase_chain(
        phase_head, verified_origin=origin, reuse_verified_origin=True
    )
    chain = (*phase_chain, terminal_verified)
    if (
        len(chain) != 5
        or type(chain[-1].receipt) is not AcquisitionCandidateExperimentTerminalReceipt
    ):
        raise ValueError("candidate_experiment_terminal_chain_generation_mismatch")
    terminal = chain[-1].receipt
    expected_phases = (
        "requested",
        "executing",
        "outcome_selected",
        "candidate_input_reentry_pending",
    )
    phases = chain[:-1]
    if tuple(item.receipt.receipt_phase for item in phases) != expected_phases:
        raise ValueError("candidate_experiment_terminal_phase_history_incomplete")
    if (
        phases[0].receipt.predecessor_receipt_ref is not None
        or phases[0].event.state_before is not None
    ):
        raise ValueError("candidate_experiment_terminal_phase_root_invalid")
    if (
        str(terminal_ref.artifact_id) != head.receipt_ref
        and terminal.predecessor_receipt_ref != head.receipt_ref
    ):
        raise ValueError("candidate_experiment_terminal_predecessor_binding_mismatch")
    if committed:
        if (
            str(terminal_ref.artifact_id) != head.receipt_ref
            or chain[-1].durable_event_id != head.durable_event_id
            or any(
                getattr(terminal, field) != getattr(head, field)
                for field in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "route_id",
                    "action_generation",
                    "job_id",
                    "coarse_phase",
                    "receipt_phase",
                    "recovery_state",
                    "predecessor_receipt_ref",
                )
            )
        ):
            raise ValueError("candidate_experiment_terminal_head_binding_mismatch")
    elif (
        terminal.predecessor_receipt_ref != head.receipt_ref
        or phases[-1].receipt_ref != head.receipt_ref
        or phases[-1].durable_event_id != head.durable_event_id
    ):
        raise ValueError("candidate_experiment_terminal_predecessor_binding_mismatch")

    first_phase = phases[0].receipt
    if any(not sink._same_action_identity(first_phase, item.receipt) for item in chain[1:]):
        raise ValueError("candidate_experiment_terminal_identity_mismatch")
    if any(
        item.receipt.predecessor_receipt_ref != previous.receipt_ref
        or item.event.state_before != previous.receipt.receipt_phase
        or item.receipt.generated_at < previous.receipt.generated_at
        or (allowed := sink._allowed_predecessor_phases(item.receipt)) is None
        or previous.receipt.receipt_phase not in allowed
        for previous, item in pairwise(chain)
    ) or any(item.event.state_after != item.receipt.receipt_phase for item in chain):
        raise ValueError("candidate_experiment_terminal_transition_invalid")
    if (
        phases[-1].receipt.candidate_receipt_ref is None
        or not _candidate_ref_same(
            phases[-1].receipt.candidate_receipt_ref, terminal.candidate_action_ref
        )
        or str(terminal.candidate_action_ref.artifact_id) not in terminal.owner_receipt_refs
        or chain[-1].event.state_before != "candidate_input_reentry_pending"
        or chain[-1].event.state_after != "terminal"
    ):
        raise ValueError("candidate_experiment_terminal_selection_mismatch")
    # The phase-chain verifier already authenticated the selected pending
    # phase's historical PA2 decision against this origin. Its full action
    # identity join binds every earlier phase to the same request and selected
    # decision profile, so reopening the same signed history for each phase is
    # redundant. This remains historical evidence, never a live permit.

    effective_generation_run = origin.effective_generation_run
    effective_source_cycle = origin.effective_source_cycle
    if (
        type(origin) is not VerifiedCandidateExperimentOrigin
        or origin.source_job_id != head.source_job_id
        or origin.route_id != head.route_id
        or origin.source_payload_ref != terminal.source_payload_ref
        or origin.capability_manifest_ref != terminal.capability_manifest_ref
        or origin.request_content_hash != terminal.request_content_hash
        or not _candidate_model_values_same(origin.policy_scope, terminal.policy_scope)
        or not _candidate_ref_same(origin.policy_ref, terminal.policy_ref)
        or not _candidate_model_values_same(origin.source_cycle.voi_decision, terminal.voi_decision)
    ):
        raise ValueError("candidate_experiment_terminal_source_mismatch")

    action_service = getattr(
        getattr(control_service, "_acquisition_job_handler", None), "__self__", None
    )
    port = getattr(action_service, "_production_execution_port", None)
    bridge = getattr(port, "_world_growth_bridge", None)
    if (
        type(action_service) is not AcquisitionActionService
        or action_service.control_service is not control_service
        or type(port) is not WorldBankWDIAcquisitionExecutionPort
        or bridge is None
        or bridge._source_control_service is not control_service
        or bridge.artifact_store is not store
        or bridge.event_log is not events
        or bridge.control_store is not control
    ):
        raise ValueError("candidate_experiment_terminal_action_owner_not_composed")
    executing = phases[1].receipt
    if type(executing) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_terminal_executing_phase_untyped")
    action, source, budget_window = read_candidate_experiment_acquisition_action_historical(
        bridge=bridge,
        origin=origin,
        receipt_ref=terminal.candidate_action_ref,
        executing_phase=executing,
        executing_phase_ref=phases[1].receipt_ref,
    )
    if (
        type(source) is not CandidateAcquisitionSource
        or str(terminal.authority_decision_ref.artifact_id) != str(action.decision_ref)
        or action.action_job_id != terminal.job_id
        or action.action_generation != terminal.action_generation
        or action.route_id != terminal.route_id
        or (source.tenant_id, source.cell_id, source.run_id, source.job_id, source.route_id)
        != (head.tenant_id, head.cell_id, head.run_id, action.action_job_id, head.route_id)
        or source.candidate_digest != action.candidate_digest
        or source.target_slot_id != action.target_slot_id
    ):
        raise ValueError("candidate_experiment_terminal_action_mismatch")

    decision = None
    current_basis = None
    selected_basis = None
    evaluation = None
    reentry_evaluation = None
    reentry = None
    continuation = None
    frontier_before = None
    frontier_after = None
    retained = terminal.terminal_outcome == "candidate_evaluation_retained"
    if terminal.terminal_outcome == "candidate_blocked":
        from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
            _candidate_experiment_inherited_limitations,
            _candidate_experiment_unselected_input_changed,
            _candidate_experiment_unselected_prior,
        )
        from polisyos.runtime.quality.candidate_source_basis import (
            prepare_candidate_source_basis_values,
        )

        if terminal.blocker_reason != "candidate_experiment_input_change_not_established":
            raise ValueError("candidate_experiment_blocker_owner_not_established")
        decision = read_acquisition_evaluation_artifact(
            store=store,
            event_log=events,
            ref=terminal.blocker_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if type(decision) is not CandidateAcquisitionEvaluationDecision:
            raise ValueError("candidate_experiment_blocker_decision_untyped")
        current_basis = read_acquisition_evaluation_artifact(
            store=store,
            event_log=events,
            ref=decision.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        prior_history = _candidate_experiment_unselected_prior(origin)
        prior = None if prior_history is None else prior_history.reentry_evaluation
        if (
            type(current_basis) is not CandidateAcquisitionEvaluationBasis
            or current_basis.basis_role != "prospective"
            or prior is None
            or decision.comparison_result != "not_established"
            or decision.predicate_provenance != "not_established"
            or decision.reason_codes
            != tuple(
                dict.fromkeys(
                    (
                        "candidate_evaluation_prior_basis_not_established",
                        "candidate_experiment_input_change_not_established",
                        *current_basis.reason_codes,
                    )
                )
            )
            or decision.prior_basis_ref is not None
            or decision.prior_evaluation is not None
            or decision.expected_frontier_ref is not None
            or decision.expected_frontier_revision != 0
            or (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
            != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            or decision.action_job_id != head.job_id
            or decision.action_generation != head.action_generation
            or decision.route_id != head.route_id
            or decision.design_problem_ref != origin.policy_scope.design_problem_ref
            or decision.design_problem_basis_ref != origin.policy_scope.design_problem_basis_ref
            or decision.candidate_id != origin.policy_scope.candidate_id
            or decision.compiled_ref != str(origin.policy_scope.compiled_ref.artifact_id)
            or decision.source_candidate_content_hash
            != effective_source_cycle.selected_candidate_content_hash
            or (current_basis.tenant_id, current_basis.cell_id, current_basis.run_id)
            != (head.tenant_id, head.cell_id, head.run_id)
            or current_basis.source_job_id != head.source_job_id
            or current_basis.action_job_id != head.job_id
            or current_basis.action_generation != head.action_generation
            or current_basis.route_id != head.route_id
            or current_basis.design_problem_ref != decision.design_problem_ref
            or current_basis.design_problem_basis_ref != decision.design_problem_basis_ref
            or current_basis.candidate_id != decision.candidate_id
            or current_basis.source_candidate_content_hash != decision.source_candidate_content_hash
            or not set(_candidate_experiment_inherited_limitations(origin)).issubset(
                current_basis.limitations
            )
            or not set(action.limitations).issubset(current_basis.limitations)
            or not _candidate_ref_same(decision.candidate_action_ref, terminal.candidate_action_ref)
            or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
            or not _candidate_ref_same(
                current_basis.candidate_action_ref, terminal.candidate_action_ref
            )
            or not _candidate_ref_same(
                current_basis.candidate_source_ref, action.candidate_source_ref
            )
            or not _candidate_ref_same(
                current_basis.candidate_world_intent_ref, decision.candidate_world_intent_ref
            )
        ):
            raise ValueError("candidate_experiment_blocker_owner_not_established")
        predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
            store=store, origin=origin
        )
        prepared = prepare_candidate_source_basis_values(
            store=store,
            problem=origin.design_problem_basis,
            inputs=current_basis.preparation_inputs,
            predecessors=predecessors,
        )
        if _candidate_experiment_unselected_input_changed(
            bridge=bridge, origin=origin, prior=prior, prepared=prepared
        ):
            raise ValueError("candidate_experiment_blocker_input_changed")
        replay_candidate_acquisition_basis_for_history(
            artifact_store=store,
            problem=origin.design_problem_basis,
            basis=current_basis,
            predecessors=predecessors,
            selected_evaluation=prior,
            fresh_limit_usd=budget_window.fresh_limit_usd,
            global_limit_usd=budget_window.global_limit_usd,
        )
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            source_job_id=head.source_job_id,
            design_problem_ref=origin.policy_scope.design_problem_ref,
            candidate_id=origin.policy_scope.candidate_id,
        )
        route_heads = (
            control.list_acquisition_action_heads(
                tenant_id=head.tenant_id,
                cell_id=head.cell_id,
                run_id=head.run_id,
                source_job_id=head.source_job_id,
                route_id=head.route_id,
            )
            if committed
            else ()
        )
        latest_terminal = next(
            (item for item in reversed(route_heads) if item.receipt_phase == "terminal"), None
        )
        if (
            head.evaluation_frontier_before_ref is not None
            or head.evaluation_frontier_ref is not None
            or (
                (not committed or latest_terminal == head)
                and control.read_acquisition_evaluation_frontier(key) is not None
            )
            or control.get_acquisition_action_head(**scope) != head
            or (
                committed
                and control.list_acquisition_action_heads(
                    tenant_id=head.tenant_id,
                    cell_id=head.cell_id,
                    run_id=head.run_id,
                    source_job_id=head.source_job_id,
                    route_id=head.route_id,
                )
                != route_heads
            )
        ):
            raise ValueError("candidate_experiment_blocker_frontier_changed")
        return CandidateExperimentTerminalHistory(
            head=head,
            terminal_ref=terminal_ref,
            terminal=terminal,
            origin=origin,
            phase_chain=chain,
            action=action,
            source=source,
            budget_window=budget_window,
            decision=decision,
            current_basis=current_basis,
            selected_basis=current_basis,
            evaluation=None,
            reentry=None,
            continuation=None,
            frontier_before=None,
            frontier_after=None,
        )
    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=terminal.evaluation_decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    current_basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=decision.current_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    selected_basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=events,
        ref=terminal.selected_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or type(current_basis) is not CandidateAcquisitionEvaluationBasis
        or type(selected_basis) is not CandidateAcquisitionEvaluationBasis
        or (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
        or decision.action_job_id != head.job_id
        or decision.action_generation != head.action_generation
        or decision.route_id != head.route_id
        or decision.design_problem_ref != origin.policy_scope.design_problem_ref
        or decision.design_problem_basis_ref != origin.policy_scope.design_problem_basis_ref
        or decision.candidate_id != origin.policy_scope.candidate_id
        or decision.source_candidate_content_hash
        != effective_source_cycle.selected_candidate_content_hash
        or effective_source_cycle.selected_candidate_ref != origin.policy_scope.candidate_id
        or effective_source_cycle.design_problem_ref != origin.policy_scope.design_problem_ref
        or effective_source_cycle.design_problem_basis_ref
        != origin.policy_scope.design_problem_basis_ref
        or decision.compiled_ref != str(origin.policy_scope.compiled_ref.artifact_id)
        or origin.policy_scope.source_cycle_index != origin.source_cycle.cycle_index
        or origin.source_cycle.cycle_index >= len(origin.generation_run.cycles)
        or origin.generation_run.cycles[origin.source_cycle.cycle_index] != origin.source_cycle
        or current_basis.design_problem_ref != decision.design_problem_ref
        or current_basis.design_problem_basis_ref != decision.design_problem_basis_ref
        or current_basis.candidate_id != decision.candidate_id
        or current_basis.source_candidate_content_hash != decision.source_candidate_content_hash
        or current_basis.action_job_id != head.job_id
        or current_basis.action_generation != head.action_generation
        or current_basis.route_id != head.route_id
        or selected_basis.design_problem_ref != decision.design_problem_ref
        or selected_basis.design_problem_basis_ref != decision.design_problem_basis_ref
        or selected_basis.candidate_id != decision.candidate_id
        or (
            not retained
            and selected_basis.source_candidate_content_hash
            != decision.source_candidate_content_hash
        )
        or (not retained and selected_basis.action_job_id != head.job_id)
        or (not retained and selected_basis.action_generation != head.action_generation)
        or (not retained and selected_basis.route_id != head.route_id)
        or not _candidate_ref_same(decision.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(
            current_basis.candidate_action_ref, terminal.candidate_action_ref
        )
        or (
            not retained
            and not _candidate_ref_same(
                selected_basis.candidate_action_ref, terminal.candidate_action_ref
            )
        )
        or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(current_basis.candidate_source_ref, action.candidate_source_ref)
        or (
            not retained
            and not _candidate_ref_same(
                selected_basis.candidate_source_ref, action.candidate_source_ref
            )
        )
        or not _candidate_ref_same(
            decision.candidate_world_intent_ref, current_basis.candidate_world_intent_ref
        )
        or (
            not retained
            and not _candidate_ref_same(
                current_basis.candidate_world_intent_ref, selected_basis.candidate_world_intent_ref
            )
        )
        or current_basis.basis_role != "prospective"
    ):
        raise ValueError("candidate_experiment_terminal_evaluation_owner_mismatch")
    if predecessor_history_chain:
        previous = predecessor_history_chain[-1]
        previous_frontier = previous.frontier_after
        expected_prior_evaluation = (
            previous.evaluation.selected.model_copy(
                update={"basis_ref": previous.terminal.selected_basis_ref}
            )
            if previous.evaluation is not None
            else None
        )
        if previous_frontier is None:
            if (
                previous.evaluation is not None
                or decision.comparison_result != "not_established"
                or decision.predicate_provenance != "not_established"
                or decision.prior_basis_ref is not None
                or decision.prior_evaluation is not None
                or decision.expected_frontier_ref is not None
                or decision.expected_frontier_revision != 0
            ):
                raise ValueError("candidate_experiment_terminal_prior_generation_mismatch")
        elif (
            previous.selected_basis is None
            or expected_prior_evaluation is None
            or not _candidate_ref_same(
                decision.prior_basis_ref, previous.terminal.selected_basis_ref
            )
            or not _candidate_model_values_same(
                decision.prior_evaluation, expected_prior_evaluation
            )
            or decision.expected_frontier_ref != previous_frontier.frontier_ref
            or decision.expected_frontier_revision != previous_frontier.revision
        ):
            raise ValueError("candidate_experiment_terminal_prior_generation_mismatch")
    elif (
        decision.prior_basis_ref is not None
        or decision.prior_evaluation is not None
        or decision.expected_frontier_ref is not None
        or decision.expected_frontier_revision != 0
    ):
        raise ValueError("candidate_experiment_terminal_unexpected_prior_frontier")

    if predecessor_history_chain and predecessor_history_chain[-1].frontier_after is None:
        from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
            _candidate_experiment_unselected_input_changed,
            _candidate_experiment_unselected_prior,
        )
        from polisyos.runtime.quality.candidate_source_basis import (
            prepare_candidate_source_basis_values,
        )

        prior_history = _candidate_experiment_unselected_prior(origin)
        prepared = prepare_candidate_source_basis_values(
            store=store,
            problem=origin.design_problem_basis,
            inputs=current_basis.preparation_inputs,
            predecessors=_candidate_source_predecessors_for_verified_experiment_origin(
                store=store, origin=origin
            ),
        )
        if (
            prior_history is None
            or "candidate_experiment_changed_input" not in decision.reason_codes
            or not _candidate_experiment_unselected_input_changed(
                bridge=bridge,
                origin=origin,
                prior=prior_history.reentry_evaluation,
                prepared=prepared,
            )
        ):
            raise ValueError("candidate_experiment_terminal_changed_input_not_established")

    reentry_evaluation: ResolvedAcquisitionEvaluation | None = None
    if retained:
        if not predecessor_history_chain:
            raise ValueError("candidate_experiment_retained_prior_history_missing")
        previous = predecessor_history_chain[-1]
        if (
            decision.comparison_result != "equivalent"
            or decision.predicate_provenance != "recomputed"
            or current_basis.predicate_provenance != "recomputed"
            or selected_basis.predicate_provenance != "recomputed"
            or not basis_exact_values_equal(current_basis, selected_basis)
            or previous.selected_basis is None
            or previous.evaluation is None
            or not _candidate_ref_same(
                terminal.selected_basis_ref, previous.terminal.selected_basis_ref
            )
            or not _candidate_model_values_same(selected_basis, previous.selected_basis)
            or not _candidate_model_values_same(
                decision.prior_evaluation,
                previous.evaluation.selected.model_copy(
                    update={"basis_ref": previous.terminal.selected_basis_ref}
                ),
            )
            or selected_basis.basis_role != "evaluated"
        ):
            raise ValueError("candidate_experiment_retained_prior_mismatch")

    if retained:
        from polisyos.runtime.quality.acquisition_retained_continuation import (
            read_candidate_acquisition_retained_continuation,
        )

        if terminal.current_continuation_ref is None:
            raise ValueError("candidate_experiment_retained_continuation_missing")
        continuation, evaluation = read_candidate_acquisition_retained_continuation(
            store=store,
            event_log=events,
            control_store=control,
            ref=terminal.current_continuation_ref,
            decision=decision,
            terminal=terminal,
            prior_experiment_origin=origin,
        )
        if (
            terminal.candidate_reentry_ref is not None
            or terminal.selected_evaluation is None
            or evaluation is None
            or not _candidate_model_values_same(selected_basis.evaluation, evaluation.selected)
            or not _candidate_ref_same(
                terminal.selected_evaluation_witness_ref,
                evaluation.selected.n5_execution_ref,
            )
            or not _candidate_model_values_same(
                terminal.selected_evaluation,
                evaluation.selected.model_copy(update={"basis_ref": terminal.selected_basis_ref}),
            )
            or not (
                set(current_basis.limitations)
                | set(predecessor_history_chain[-1].selected_basis.limitations)
            ).issubset(continuation.limitations)
        ):
            raise ValueError("candidate_experiment_retained_history_mismatch")
    else:
        if terminal.candidate_reentry_ref is None:
            raise ValueError("candidate_experiment_terminal_reentry_missing")
        reentry = verify_candidate_experiment_source_reentry_history(
            bridge=bridge,
            origin=origin,
            receipt_ref=terminal.candidate_reentry_ref,
            expected_selected_action_ref=terminal.candidate_action_ref,
        )
        if (
            reentry.source_cycle_index != effective_source_cycle.cycle_index
            or reentry.source_generation_run_content_hash
            != generation_cycle_run_content_hash(effective_generation_run)
        ):
            raise ValueError("candidate_experiment_terminal_effective_source_binding_mismatch")
        validate_candidate_source_continuation(effective_generation_run, reentry)
        if (
            not _candidate_ref_same(
                current_basis.candidate_world_intent_ref, reentry.candidate_world_intent_ref
            )
            or not _candidate_ref_same(
                selected_basis.candidate_world_intent_ref, reentry.candidate_world_intent_ref
            )
            or not _candidate_ref_same(
                current_basis.candidate_source_ref, reentry.candidate_source_ref
            )
            or not _candidate_ref_same(
                selected_basis.candidate_source_ref, reentry.candidate_source_ref
            )
            or not _candidate_ref_same(
                selected_basis.selected_data_snapshot_ref, reentry.data_snapshot_ref
            )
            or not _candidate_ref_same(
                selected_basis.selected_world_model_ref, reentry.world_model_ref
            )
        ):
            raise ValueError("candidate_experiment_terminal_reentry_basis_mismatch")
        if reentry.new_cycle.simulation.status == "joint_simulated":
            reentry_evaluation = resolve_selected_acquisition_evaluation_parts(
                artifact_store=store,
                control_store=control,
                tenant_id=head.tenant_id,
                cell_id=head.cell_id,
                run_id=head.run_id,
                generation_run=reentry.continued_generation_run,
                source_cycle=reentry.new_cycle,
                design_problem_ref=origin.policy_scope.design_problem_ref,
            )
        if predecessor_history_chain and predecessor_history_chain[-1].frontier_after is None:
            from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

            slot = prepared.inputs.slot_binding.target_slot_id
            if (
                reentry_evaluation is None
                or prepared.prospective_model is None
                or slot not in reentry_evaluation.input_record.n5.baseline_state
                or slot not in prepared.prospective_model.n5_config.baseline_state
                or exact_n5_content_bytes(reentry_evaluation.input_record.n5.baseline_state[slot])
                != exact_n5_content_bytes(prepared.prospective_model.n5_config.baseline_state[slot])
                or exact_n5_content_bytes(reentry_evaluation.input_record.n5)
                != exact_n5_content_bytes(prepared.prospective_model.n5_config)
            ):
                raise ValueError("candidate_experiment_terminal_changed_input_not_consumed")
        evaluation = reentry_evaluation if selected_basis.basis_role == "evaluated" else None
        if (
            terminal.terminal_outcome != "candidate_reentry_completed"
            or terminal.current_continuation_ref is not None
            or selected_basis.basis_role != ("evaluated" if evaluation is not None else "blocked")
            or (terminal.selected_evaluation is None) != (evaluation is None)
            or (
                evaluation is not None
                and (
                    evaluation.selected.candidate_id != reentry.new_cycle.selected_candidate_ref
                    or evaluation.selected.candidate_content_hash
                    != reentry.new_cycle.selected_candidate_content_hash
                    or not _candidate_ref_same(
                        terminal.selected_evaluation_witness_ref,
                        evaluation.selected.n5_execution_ref,
                    )
                    or not _candidate_model_values_same(
                        terminal.selected_evaluation,
                        evaluation.selected.model_copy(
                            update={"basis_ref": terminal.selected_basis_ref}
                        ),
                    )
                )
            )
            or (
                evaluation is None
                and not _candidate_ref_same(
                    terminal.selected_evaluation_witness_ref, terminal.candidate_reentry_ref
                )
            )
        ):
            raise ValueError("candidate_experiment_terminal_evaluation_mismatch")

    # The initial candidate basis is calculated against the source cycle's
    # existing N4 evaluation, when that cycle has one. The selected basis is
    # calculated against the newly reopened reentry evaluation. The experiment
    # template and persisted window supply ceilings, never source prices.
    current_evaluation = (
        resolve_selected_acquisition_evaluation_parts(
            artifact_store=store,
            control_store=control,
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            generation_run=effective_generation_run,
            source_cycle=effective_source_cycle,
            design_problem_ref=origin.policy_scope.design_problem_ref,
        )
        if effective_source_cycle.simulation.status == "joint_simulated"
        else None
    )
    predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
        store=store, origin=origin
    )
    replay_candidate_acquisition_basis_for_history(
        artifact_store=store,
        problem=origin.design_problem_basis,
        basis=current_basis,
        predecessors=predecessors,
        selected_evaluation=current_evaluation,
        fresh_limit_usd=budget_window.fresh_limit_usd,
        global_limit_usd=budget_window.global_limit_usd,
    )
    if not retained:
        replay_candidate_acquisition_basis_for_history(
            artifact_store=store,
            problem=origin.design_problem_basis,
            basis=selected_basis,
            predecessors=predecessors,
            selected_evaluation=reentry_evaluation,
            fresh_limit_usd=budget_window.fresh_limit_usd,
            global_limit_usd=budget_window.global_limit_usd,
        )

    frontier_key = AcquisitionEvaluationFrontierKey(
        tenant_id=decision.tenant_id,
        cell_id=decision.cell_id,
        source_job_id=decision.source_job_id,
        design_problem_ref=decision.design_problem_ref,
        candidate_id=decision.candidate_id,
    )
    current_frontier = control.read_acquisition_evaluation_frontier(frontier_key)
    route_scope = {
        "tenant_id": head.tenant_id,
        "cell_id": head.cell_id,
        "run_id": head.run_id,
        "source_job_id": head.source_job_id,
        "route_id": head.route_id,
    }
    action_heads = control.list_acquisition_action_heads(**route_scope) if committed else ()
    if committed and head not in action_heads:
        raise ValueError("candidate_experiment_terminal_head_changed")
    latest_terminal_head = next(
        (item for item in reversed(action_heads) if item.receipt_phase == "terminal"),
        None,
    )
    if committed:
        frontier_before, frontier_after = _candidate_experiment_frontier_transition_for_history(
            control_store=control,
            key=frontier_key,
            head=head,
            expected_frontier_ref=decision.expected_frontier_ref,
            expected_frontier_revision=decision.expected_frontier_revision,
            selected_basis_ref=str(terminal.selected_basis_ref.artifact_id),
            selected_basis_content_hash=selected_basis.content_hash,
            decision_ref=str(terminal.evaluation_decision_ref.artifact_id),
            selected_evaluation_witness_ref=str(
                terminal.selected_evaluation_witness_ref.artifact_id
            ),
            selected_evaluation_content_hash=(
                evaluation.execution.content_hash if evaluation is not None else None
            ),
        )
        if latest_terminal_head == head and current_frontier != frontier_after:
            if evaluation is None:
                raise ValueError("candidate_experiment_terminal_blocked_frontier_changed")
            raise ValueError("candidate_experiment_terminal_frontier_after_mismatch")
    else:
        frontier_before = current_frontier
        if (
            frontier_before.revision if frontier_before else 0
        ) != decision.expected_frontier_revision or (
            frontier_before.frontier_ref if frontier_before else None
        ) != decision.expected_frontier_ref:
            raise ValueError("candidate_experiment_terminal_frontier_before_mismatch")

    if (
        control.get_acquisition_action_head(**scope) != head
        or control.read_acquisition_evaluation_frontier(frontier_key) != current_frontier
        or (committed and control.list_acquisition_action_heads(**route_scope) != action_heads)
    ):
        raise ValueError("candidate_experiment_terminal_head_changed")
    return CandidateExperimentTerminalHistory(
        head=head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        origin=origin,
        phase_chain=chain,
        action=action,
        source=source,
        budget_window=budget_window,
        decision=decision,
        current_basis=current_basis,
        selected_basis=selected_basis,
        evaluation=evaluation,
        reentry=reentry,
        continuation=continuation,
        frontier_before=frontier_before,
        frontier_after=frontier_after,
        reentry_evaluation=reentry_evaluation,
    )


def _selected_ref(store: CoreJSONArtifactStore, locator: str | ArtifactRef) -> ArtifactRef:
    """Resolve the actual selected manifest, with no synthesized selector."""
    if isinstance(locator, ArtifactRef) and locator.manifest_profile_sha256 is None:
        raise ValueError("acquisition_history_selected_profile_missing")
    manifest = store.get_manifest(locator)
    selected = artifact_ref_for_manifest(manifest)
    if isinstance(locator, ArtifactRef) and not _same_ref(locator, selected):
        raise ValueError("acquisition_history_selected_profile_mismatch")
    if selected.manifest_profile_sha256 is None or not store.verify(selected).ok:
        raise ValueError("acquisition_history_selected_artifact_unverified")
    raw = store.get_bytes(selected)
    if str(selected.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("acquisition_history_selected_bytes_mismatch")
    if store.get_manifest(selected) != manifest:
        raise ValueError("acquisition_history_selected_manifest_changed")
    return selected


def _verified_terminal(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    head: AcquisitionActionHeadRecord,
    selected_ref: ArtifactRef,
) -> AcquisitionRouteLoopReceiptV2:
    """Independently reopen the exact selected @2 terminal and owner event."""
    manifest = artifact_store.get_manifest(selected_ref)
    if (
        head.receipt_ref != head.receipt_sha256
        or str(selected_ref.artifact_id) != head.receipt_ref
        or manifest.kind != "runtime_quality.acquisition_route_loop_receipt"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != "polisyos.runtime.AcquisitionRouteLoopReceipt"
        or manifest.artifact_schema.version != "2.0"
        or manifest.producer is None
        or manifest.producer.component != "polisyos.runtime.acquisition_route_loop"
        or manifest.producer.version != "2026.08.28+ds15-c02"
    ):
        raise ValueError("acquisition_retained_terminal_manifest_mismatch")
    terminal = AcquisitionRouteLoopReceiptV2.model_validate(
        load_core_json_artifact(artifact_store, selected_ref)
    )
    event = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(selected_ref.artifact_id),
        expected_tenant_id=head.tenant_id,
        expected_cell_id=head.cell_id,
        expected_run_id=head.run_id,
        expected_job_id=head.job_id,
    )
    if event.durable_event_id != head.durable_event_id:
        raise ValueError("acquisition_retained_terminal_event_mismatch")
    return terminal


def read_historical_acquisition_growth(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
) -> AcquisitionWorldGrowthReceipt:
    """Reopen the immutable growth owner fact, without claiming it is current."""
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt

    growth_ref = _selected_ref(artifact_store, ref)
    manifest = epoch._preflight_core_manifest_profile(
        store=artifact_store,
        selector=growth_ref,
        expected_kind="runtime_quality.acquisition_world_growth_receipt",
        expected_media_type="application/json",
        expected_canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
        expected_schema=artifacts.SchemaInfo(
            name=AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME, version="1.1"
        ),
        require_selected_profile=True,
        expected_inputs=epoch._ExactManifestInputClosure(()),
    )
    if (
        manifest.authority is None
        or manifest.producer is None
        or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
        or manifest.producer.version != "1.0"
    ):
        raise ValueError("acquisition_retained_growth_producer_mismatch")
    growth = AcquisitionWorldGrowthReceipt.model_validate(
        load_core_json_artifact(artifact_store, growth_ref)
    )
    if (
        growth.schema_version != "AcquisitionWorldGrowthReceipt@1.1"
        or (growth.selection.tenant_id, growth.selection.cell_id, growth.selection.run_id)
        != (tenant_id, cell_id, run_id)
        or growth.admitted_observation_delta <= 0
    ):
        raise ValueError("acquisition_retained_growth_scope_mismatch")
    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(growth_ref.artifact_id),
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
        expected_run_id=run_id,
        expected_job_id=source_job_id,
    )
    if report.durable_event_id is None:
        raise ValueError("acquisition_retained_growth_event_missing")
    return growth


def _verified_growth(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    snapshot: VerifiedAcquisitionActionOutcome,
    terminal: AcquisitionRouteLoopReceiptV2,
    decision: AcquisitionEvaluationDecision,
    current_basis: AcquisitionEvaluationBasis,
    design_problem_ref: str,
) -> AcquisitionWorldGrowthReceipt:
    """Reopen the selected historical growth and its passport/source relation."""
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    if (
        snapshot.executing_phase_ref is None
        or snapshot.executing_phase is None
        or snapshot.selection_phase_ref is None
        or snapshot.selection_phase is None
        or snapshot.selection_phase.predecessor_receipt_ref != snapshot.executing_phase_ref
        or snapshot.selection_phase.owner_receipt_refs
        != (str(decision.growth_receipt_ref.artifact_id),)
        or str(decision.growth_receipt_ref.artifact_id) not in terminal.owner_receipt_refs
    ):
        raise ValueError("acquisition_retained_action_selection_unverified")
    action_ref = _selected_ref(artifact_store, snapshot.selection_phase_ref)
    if not _same_ref(action_ref, decision.selected_action_receipt_ref):
        raise ValueError("acquisition_retained_action_selection_mismatch")

    growth = read_historical_acquisition_growth(
        artifact_store=artifact_store,
        event_log=event_log,
        ref=decision.growth_receipt_ref,
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        source_job_id=terminal.source_job_id,
    )
    if (
        growth.action_phase_ref != snapshot.executing_phase_ref
        or growth.selection.key
        != (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.route_id)
        or growth.selection.design_problem_ref != design_problem_ref
        or growth.admitted_observation_delta <= 0
    ):
        raise ValueError("acquisition_retained_growth_scope_mismatch")
    passport = AdmissionPassport.model_validate(
        epoch.load_verified_epoch_statement(
            store=artifact_store,
            ref=growth.activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    candidate = epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        epoch.load_verified_epoch_statement(
            store=artifact_store,
            ref=passport.semantic_boundary_candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    source_ref = _selected_ref(artifact_store, decision.admitted_source_ref)
    if (
        passport.passport_id != growth.passport_id
        or passport.epoch_id != growth.selection.epoch_id
        or passport.status not in {"admitted", "admitted_degraded"}
        or passport.semantic_epoch_stamp != growth.activation.semantic_epoch_stamp
        or epoch.acquisition_semantic_candidate_content_hash(candidate)
        != passport.semantic_boundary_candidate_content_hash
        or not _same_ref(candidate.source_record_ref, source_ref)
        or candidate.source_record_content_hash != str(source_ref.artifact_id)
        or not _same_ref(
            current_basis.preparation_inputs.boundary_candidate_ref,
            passport.semantic_boundary_candidate_ref,
        )
    ):
        raise ValueError("acquisition_retained_admitted_source_mismatch")
    return growth


def _prior_evaluation_job_id(
    *,
    artifact_store: CoreJSONArtifactStore,
    source_cycle: GenerationCycleRecord,
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> str | None:
    """Resolve the old evaluation's own job; never substitute the source job."""
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    source_ref = source_cycle.simulation.candidate_simulation_n4_source_ref
    input_ref = source_cycle.simulation.candidate_simulation_n5_input_ref
    if source_ref is None and input_ref is None:
        return None
    if source_ref is None or input_ref is None:
        raise ValueError("acquisition_history_prior_input_source_incomplete")
    repository = GenerationSourceRepository(artifact_store)
    source = repository.load_candidate_scenario_source_in_owner_scope(
        source_ref,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    if type(source) is not N4CandidateScenarioSourceRecordV3:
        raise ValueError("acquisition_history_prior_source_version_not_established")
    prior_input = repository.resolve_candidate_simulation_v5(
        ref=input_ref,
        expected_run_id=run_id,
        expected_job_id=source.job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    if (
        type(prior_input) is not CandidateSimulationN5InputV5
        or not _same_ref(prior_input.n4_source_ref, source_ref)
        or source.candidate.candidate_id != source_cycle.selected_candidate_ref
        or source.candidate.atom.content_hash != source_cycle.selected_candidate_content_hash
        or prior_input.original_candidate_id != source_cycle.selected_candidate_ref
        or prior_input.original_candidate_hash != source_cycle.selected_candidate_content_hash
    ):
        raise ValueError("acquisition_history_prior_input_source_mismatch")
    return source.job_id


def verify_retained_route_accumulator(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    snapshot: VerifiedAcquisitionActionOutcome,
    terminal: AcquisitionRouteLoopReceiptV2,
    generation_run: GenerationCycleRun,
    source_cycle: GenerationCycleRecord,
    design_problem_ref: str,
) -> _VerifiedRetainedRoute:
    """Verify one retained terminal against the currently folded evaluation.

    The calling route owner supplies its already verified action snapshot. This
    function rereads the selected terminal and head but never recursively calls
    the same action fold. Later frontier movement does not erase this historical
    transaction, whose before/after witnesses must both equal the decision.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
    from polisyos.runtime.quality.acquisition_evaluation import (
        read_acquisition_retained_continuation,
        replay_acquisition_basis_for_history,
    )
    from polisyos.runtime.quality.generation_cycle import _cycle_basis_ref

    if (
        type(snapshot) is not VerifiedAcquisitionActionOutcome
        or type(snapshot.head) is not AcquisitionActionHeadRecord
        or type(terminal) is not AcquisitionRouteLoopReceiptV2
        or terminal.terminal_outcome != "source_admitted_evaluation_retained"
        or terminal.selected_evaluation is None
        or terminal.current_continuation_ref is None
        or terminal.reentry_receipt_ref is not None
    ):
        raise ValueError("acquisition_retained_terminal_untyped")
    head = snapshot.head
    if snapshot.latest_receipt != terminal:
        raise ValueError("acquisition_retained_snapshot_terminal_mismatch")
    # The sink verifies only the basic selected V2 head/phase chain; it does
    # not call this accumulator or the source fold. Reusing it prevents an
    # invented VerifiedAcquisitionActionOutcome object from acting as proof.
    observed = AcquisitionRouteLoopAuthoritySink(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=control_store,
    ).verify_action_head(head)
    if (
        observed.head != snapshot.head
        or observed.executing_phase_ref != snapshot.executing_phase_ref
        or observed.selection_phase_ref != snapshot.selection_phase_ref
        or exact_n5_content_bytes(observed.latest_receipt)
        != exact_n5_content_bytes(snapshot.latest_receipt)
        or exact_n5_content_bytes(observed.selection_phase)
        != exact_n5_content_bytes(snapshot.selection_phase)
        or exact_n5_content_bytes(observed.executing_phase)
        != exact_n5_content_bytes(snapshot.executing_phase)
    ):
        raise ValueError("acquisition_retained_verified_snapshot_mismatch")
    fresh_head = control_store.get_acquisition_action_head(
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
        action_generation=head.action_generation,
    )
    if fresh_head != head or head.receipt_phase != "terminal":
        raise ValueError("acquisition_retained_action_head_changed")
    if any(
        getattr(head, name) != getattr(terminal, name)
        for name in (
            "tenant_id",
            "cell_id",
            "run_id",
            "source_job_id",
            "route_id",
            "action_generation",
            "job_id",
            "coarse_phase",
            "receipt_phase",
            "recovery_state",
            "predecessor_receipt_ref",
        )
    ):
        raise ValueError("acquisition_retained_action_head_scope_mismatch")
    terminal_ref = _selected_ref(artifact_store, head.receipt_ref)
    persisted_terminal = _verified_terminal(
        artifact_store=artifact_store,
        event_log=event_log,
        head=head,
        selected_ref=terminal_ref,
    )
    if exact_n5_content_bytes(persisted_terminal) != exact_n5_content_bytes(terminal):
        raise ValueError("acquisition_retained_terminal_payload_mismatch")

    decision = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=terminal.evaluation_decision_ref,
        record_type=AcquisitionEvaluationDecision,
    )
    if type(decision) is not AcquisitionEvaluationDecision:
        raise ValueError("acquisition_retained_decision_untyped")
    if (
        decision.comparison_result != "equivalent"
        or decision.predicate_provenance != "recomputed"
        or decision.reason_codes
        or decision.prior_evaluation is None
        or decision.prior_basis_ref is None
        or decision.expected_frontier_ref is None
        or (
            decision.tenant_id,
            decision.cell_id,
            decision.run_id,
            decision.source_job_id,
            decision.action_job_id,
            decision.action_generation,
            decision.route_id,
            decision.compiled_ref,
            decision.design_problem_ref,
        )
        != (
            terminal.tenant_id,
            terminal.cell_id,
            terminal.run_id,
            terminal.source_job_id,
            terminal.job_id,
            terminal.action_generation,
            terminal.route_id,
            terminal.compiled_ref,
            design_problem_ref,
        )
        or decision.design_problem_basis_ref != _cycle_basis_ref(source_cycle)
        or decision.candidate_id != source_cycle.selected_candidate_ref
        or not _same_ref(decision.prior_basis_ref, terminal.selected_basis_ref)
        or exact_n5_content_bytes(decision.prior_evaluation)
        != exact_n5_content_bytes(terminal.selected_evaluation)
    ):
        raise ValueError("acquisition_retained_decision_scope_mismatch")

    if not generation_run.cycles or (
        exact_n5_content_bytes(generation_run.cycles[-1]) != exact_n5_content_bytes(source_cycle)
    ):
        raise ValueError("acquisition_retained_source_not_current_accumulator")
    actual = resolve_selected_acquisition_evaluation_parts(
        artifact_store=artifact_store,
        control_store=control_store,
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        generation_run=generation_run,
        source_cycle=source_cycle,
        design_problem_ref=design_problem_ref,
    )
    selected = actual.selected.model_copy(update={"basis_ref": terminal.selected_basis_ref})
    if exact_n5_content_bytes(selected) != exact_n5_content_bytes(
        terminal.selected_evaluation
    ) or not _same_ref(terminal.selected_evaluation_witness_ref, selected.n5_execution_ref):
        raise ValueError("acquisition_retained_selected_evaluation_mismatch")

    prior_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.prior_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    current_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.current_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    if type(prior_basis) is not AcquisitionEvaluationBasis or type(current_basis) is not (
        AcquisitionEvaluationBasis
    ):
        raise ValueError("acquisition_retained_basis_untyped")
    for basis in (prior_basis, current_basis):
        if (
            (basis.tenant_id, basis.cell_id, basis.run_id, basis.source_job_id)
            != (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
            or basis.design_problem_ref != decision.design_problem_basis_ref
            or basis.candidate_id != selected.candidate_id
            or basis.predicate_provenance != "recomputed"
            or basis.reason_codes
            or not _same_ref(basis.preparation_inputs.source_ref, basis.admitted_source_ref)
        ):
            raise ValueError("acquisition_retained_basis_scope_mismatch")
    if (
        prior_basis.evaluation is None
        or exact_n5_content_bytes(prior_basis.evaluation) != exact_n5_content_bytes(actual.selected)
        or current_basis.evaluation is not None
        or not _same_ref(current_basis.growth_receipt_ref, decision.growth_receipt_ref)
        or not _same_ref(current_basis.admitted_source_ref, decision.admitted_source_ref)
    ):
        raise ValueError("acquisition_retained_basis_lineage_mismatch")
    growth = _verified_growth(
        artifact_store=artifact_store,
        event_log=event_log,
        snapshot=snapshot,
        terminal=terminal,
        decision=decision,
        current_basis=current_basis,
        design_problem_ref=design_problem_ref,
    )
    if not _same_ref(
        current_basis.preparation_inputs.receipt_ref,
        growth.activation.overlay_admission_receipt_ref,
    ) or not _same_ref(
        current_basis.preparation_inputs.passport_ref, growth.activation.passport_ref
    ):
        raise ValueError("acquisition_retained_basis_admission_mismatch")

    replayed_prior = replay_acquisition_basis_for_history(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=control_store,
        basis=prior_basis,
        prior_evaluation=actual,
        control_service=None,
    )
    replayed_current = replay_acquisition_basis_for_history(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=control_store,
        basis=current_basis,
        prior_evaluation=actual,
        control_service=None,
    )
    if (
        type(replayed_prior) is not AcquisitionEvaluationBasis
        or type(replayed_current) is not AcquisitionEvaluationBasis
        or exact_n5_content_bytes(replayed_prior) != exact_n5_content_bytes(prior_basis)
        or exact_n5_content_bytes(replayed_current) != exact_n5_content_bytes(current_basis)
        or not basis_exact_values_equal(replayed_prior, replayed_current)
    ):
        raise ValueError("acquisition_retained_basis_replay_mismatch")

    if (
        head.evaluation_frontier_before_ref != decision.expected_frontier_ref
        or head.evaluation_frontier_ref != decision.expected_frontier_ref
    ):
        raise ValueError("acquisition_retained_frontier_transaction_mismatch")
    frontier = control_store.get_acquisition_evaluation_frontier_by_ref(
        decision.expected_frontier_ref
    )
    if (
        frontier is None
        or frontier.frontier_ref != decision.expected_frontier_ref
        or frontier.revision != decision.expected_frontier_revision
        or (
            frontier.key.tenant_id,
            frontier.key.cell_id,
            frontier.key.source_job_id,
            frontier.key.design_problem_ref,
            frontier.key.candidate_id,
        )
        != (
            head.tenant_id,
            head.cell_id,
            head.source_job_id,
            design_problem_ref,
            selected.candidate_id,
        )
        or frontier.selected_evaluation_witness_ref != str(selected.n5_execution_ref.artifact_id)
        or frontier.selected_evaluation_content_hash != actual.execution.content_hash
        or frontier.basis_ref != str(decision.prior_basis_ref.artifact_id)
        or frontier.basis_content_hash != prior_basis.content_hash
    ):
        raise ValueError("acquisition_retained_frontier_evaluation_mismatch")
    continuation = read_acquisition_retained_continuation(
        store=artifact_store,
        event_log=event_log,
        ref=terminal.current_continuation_ref,
        decision=decision,
        terminal=terminal,
    )
    return _VerifiedRetainedRoute(
        decision=decision,
        prior_basis=prior_basis,
        current_basis=current_basis,
        evaluation=actual,
        growth=growth,
        continuation=continuation,
    )


def verify_acquisition_retention_history(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    control_service: ControlPlaneService,
    head: AcquisitionActionHeadRecord,
    route_receipt_ref: ArtifactRef,
    compiled_ref: ArtifactRef,
    source_run_id: str,
    source_job_id: str,
    tenant_id: str,
    cell_id: str,
) -> AcquisitionRetentionHistoryVerification:
    """Reopen the selected action, its earlier source fold, and its full retained join."""
    from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntryV3
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        ControlPlaneService,
    )
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord

    if (
        type(control_service) is not ControlPlaneService
        or control_service._artifact_store is not artifact_store
        or control_service._control_store is not control_store
        or control_service._diagnostic_event_log is not event_log
        or type(head) is not AcquisitionActionHeadRecord
        or (head.tenant_id, head.cell_id, head.run_id, head.source_job_id)
        != (tenant_id, cell_id, source_run_id, source_job_id)
    ):
        raise ValueError("acquisition_history_owner_scope_not_established")
    sink = control_service.acquisition_route_sink
    if (
        type(sink) is not AcquisitionRouteLoopAuthoritySink
        or sink._artifact_store is not artifact_store
        or sink._control_store is not control_store
        or sink._event_log is not event_log
    ):
        raise ValueError("acquisition_history_action_owner_not_established")
    snapshot = sink.verify_action_head(head)
    selected_terminal_ref = _selected_ref(artifact_store, head.receipt_ref)
    if not _same_ref(selected_terminal_ref, route_receipt_ref):
        raise ValueError("acquisition_history_terminal_selected_view_mismatch")
    terminal = snapshot.latest_receipt
    if (
        type(terminal) is not AcquisitionRouteLoopReceiptV2
        or terminal.compiled_ref != str(compiled_ref.artifact_id)
        or terminal.terminal_outcome
        not in {
            "quarantined_no_growth",
            "reentry_completed",
            "source_admitted_evaluation_retained",
        }
    ):
        raise ValueError("acquisition_history_terminal_not_established")
    reopened = _verified_terminal(
        artifact_store=artifact_store,
        event_log=event_log,
        head=head,
        selected_ref=selected_terminal_ref,
    )
    if exact_n5_content_bytes(reopened) != exact_n5_content_bytes(terminal):
        raise ValueError("acquisition_history_terminal_payload_mismatch")

    # The actual resolver verifies Core source, selected compiled output and
    # every earlier action. The exclusive cutoff prevents self-recursion.
    loop = AcquisitionRouteLoop(
        control_store=control_store,
        artifact_store=artifact_store,
        event_log=event_log,
        core_source_resolver=control_service.resolve_completed_control_job_core_run_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        action_outcome_reader=sink,
    )
    closure = loop.resolve_current_route(
        run_id=source_run_id,
        before_action_generation=head.action_generation,
    )
    source_job = control_store.get_unique_completed_job_by_run_and_kind(
        run_id=source_run_id, kind="natural_language_run"
    )
    if source_job is None or source_job.job_id != source_job_id:
        raise ValueError("acquisition_history_source_job_mismatch")
    selected_compiled = ArtifactRef.model_validate(
        source_job.progress.get("compiled_recursive_generation_cycle_artifact_ref")
    )
    if (
        not _same_ref(_selected_ref(artifact_store, selected_compiled), compiled_ref)
        or closure.compiled_ref != str(compiled_ref.artifact_id)
        or closure.route_id != terminal.route_id
        or closure.source_job_id != source_job_id
    ):
        raise ValueError("acquisition_history_source_compiled_mismatch")

    if terminal.terminal_outcome != "source_admitted_evaluation_retained":
        # Include this selected action in the owner fold. A reentry is accepted
        # only after the existing real continuation owner verifies it; a
        # no-growth action remains its old meaning, with no retention claim.
        loop.resolve_current_route(
            run_id=source_run_id,
            before_action_generation=head.action_generation + 1,
        )
        legacy = AcquisitionRouteLoopReceipt.model_validate(
            terminal.model_dump(
                mode="python",
                include=set(AcquisitionRouteLoopReceipt.model_fields) - {"schema_version"},
            )
        )
        prior_job_id = (
            _prior_evaluation_job_id(
                artifact_store=artifact_store,
                source_cycle=closure.source_cycle,
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=source_run_id,
            )
            if terminal.terminal_outcome == "reentry_completed"
            else None
        )
        if (
            control_store.get_acquisition_action_head(
                tenant_id=head.tenant_id,
                cell_id=head.cell_id,
                run_id=head.run_id,
                source_job_id=head.source_job_id,
                route_id=head.route_id,
                action_generation=head.action_generation,
            )
            != head
        ):
            raise ValueError("acquisition_history_head_changed_during_read")
        return AcquisitionRetentionHistoryVerification(
            legacy_receipt=legacy,
            terminal=terminal if terminal.terminal_outcome == "reentry_completed" else None,
            source_generation_run=closure.generation_run,
            source_cycle=closure.source_cycle,
            source_evaluation_job_id=prior_job_id,
        )

    verified = verify_retained_route_accumulator(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=control_store,
        snapshot=snapshot,
        terminal=terminal,
        generation_run=closure.generation_run,
        source_cycle=closure.source_cycle,
        design_problem_ref=closure.design_problem_ref,
    )
    current = verified.continuation.current_projection
    entry = RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(
        {
            "schema_version": "policyos.runtime.run_candidate_simulation_acquisition_history.v3",
            "route_receipt_ref": route_receipt_ref,
            "route_id": terminal.route_id,
            "action_generation": terminal.action_generation,
            "terminal_outcome": terminal.terminal_outcome,
            "admitted_source_ref": verified.decision.admitted_source_ref,
            "growth_receipt_ref": verified.decision.growth_receipt_ref,
            "evaluation_decision_ref": terminal.evaluation_decision_ref,
            "current_continuation_ref": terminal.current_continuation_ref,
            "retained_evaluation": terminal.selected_evaluation.model_dump(mode="python"),
            "current_cheap_consequences": project_retained_cheap_consequences(current),
        }
    )
    # Freeze/read the same action head again after all selected artifact reads.
    if (
        control_store.get_acquisition_action_head(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            route_id=head.route_id,
            action_generation=head.action_generation,
        )
        != head
    ):
        raise ValueError("acquisition_history_head_changed_during_read")
    return AcquisitionRetentionHistoryVerification(history_entry=entry.model_dump(mode="python"))
