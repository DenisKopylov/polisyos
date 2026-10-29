"""Historical verification of selected acquisition evaluation retention.

This reader reopens persisted owner artifacts and the transaction-bound action
frontier. It records what was selected at that historical action, not present
permission, present source eligibility, or a new N5 occurrence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
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
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


class AcquisitionRetentionHistoryVerification(BaseModel):
    """Exactly one verified history rendering for one selected action terminal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    history_entry: Mapping[str, object] | None = None
    legacy_receipt: AcquisitionRouteLoopReceipt | None = None
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
        ):
            raise ValueError("acquisition_history_retained_context_not_legacy")
        return self


@dataclass(frozen=True, slots=True)
class _VerifiedRetainedRoute:
    decision: AcquisitionEvaluationDecision
    prior_basis: AcquisitionEvaluationBasis
    current_basis: AcquisitionEvaluationBasis
    evaluation: ResolvedAcquisitionEvaluation
    growth: AcquisitionWorldGrowthReceipt


def _same_ref(left: ArtifactRef, right: ArtifactRef) -> bool:
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


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
    read_acquisition_retained_continuation(
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
