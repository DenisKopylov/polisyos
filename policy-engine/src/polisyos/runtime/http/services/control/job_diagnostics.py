"""ControlJobDiagnosticsMixin implementation for durable control-job lifecycle facets."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import MethodType
from typing import TYPE_CHECKING, Any, Literal, cast

from opentelemetry.context import attach, detach
from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.common import logger as common_logger
from polisyos.core.security import AccessScope
from polisyos.runtime.http.execution_policy import (
    ResolvedExecutionPolicy,
    build_capability_manifest_payload,
)
from polisyos.runtime.http.resilience import run_guarded_dependency_operation
from polisyos.runtime.http.services.control.admission import (
    _record_control_plane_job_admission_metric,
    _record_control_plane_job_execution_metric,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    SERIOUS_EXECUTION_PROFILES,
    DiagnosticEvent,
)
from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    _PreparedDiagnosticEvent,
)

from .._control_contracts import (
    _coerce_control_job_kind,
    _ControlJobAdmissionDiagnosticBinding,
)
from ..control_plane_store import (
    ControlDiagnosticEventRecord,
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
    ControlJobRecord,
    GenericModelInputEvaluationFrontierCAS,
    _ControlJobExecutionLifecycleProof,
    _PreparedAcquisitionActionHeadPublication,
)
from .job_attempt_publication import (
    _EXECUTION_INTENT_BINDING_KEY,
    _build_control_execution_intent_binding,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.core.contracts.runtime import RunModelInputUseN5SuccessorProjection
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
        GenericN5ResolvedResult,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerReentryBudgetWindow,
        BudgetMiddleware,
    )
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerInvocationReservation,
    )

    from ..acquisition_action_service import AcquisitionActionService
    from ..control_plane_store import ControlPlaneStore, _ControlJobLifecycleSourceEventRecord
    from ..human_decisions import _ReservationRecord
    from ..model_input_successor_action import (
        ModelInputSuccessorIdentity,
        ModelInputUseActionCheckpoint,
        SelectedModelInputSuccessorAction,
    )
    from .run_lifecycle import ControlPlaneService

logger = common_logger.get_logger("polisyos.runtime.http.services.control.run_lifecycle")

_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})
_CONTROL_JOB_EXECUTION_BINDING_KEY = "control_job_execution_binding"
_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY = "observational_method_execution"


def _closed_native_model_input_use_checkpoint(
    job_store: ControlPlaneStore, job: ControlJobRecord
) -> tuple[ModelInputUseActionCheckpoint, _ControlJobLifecycleSourceEventRecord, datetime]:
    """Read the exact checkpoint selected by an immutable completion outbox."""
    from ..control_plane_store import _json_values_equal_strict
    from ..model_input_successor_action import (
        ModelInputSuccessorActionError,
        ModelInputUseActionCheckpoint,
        model_input_use_terminal_progress,
    )

    terminal = job_store.get_job_terminal_source_event_record(job.job_id)
    running = job_store._latest_control_job_lifecycle_event_record(
        job_id=job.job_id, event_type="job_running"
    )
    outbox = job_store.get_job_completed_outbox_event(job.job_id)
    lease_owner = terminal.payload.get("lease_owner")
    if (
        job.kind != "acquisition"
        or job.state != "completed"
        or job.finished_at is None
        or job.lease_owner is not None
        or job.lease_expires_at is not None
        or terminal.event_type != "job_completed"
        or terminal.job_id != job.job_id
        or terminal.payload.get("state") != "completed"
        or not isinstance(lease_owner, str)
        or not lease_owner
        or running.job_id != job.job_id
        or running.payload.get("state") != "running"
        or running.payload.get("lease_owner") != lease_owner
        or any(
            type(event.payload.get("attempt")) is not int or event.payload["attempt"] != job.attempt
            for event in (running, terminal)
        )
        or running.event_id >= terminal.event_id
        or running.created_at > terminal.created_at
        or outbox is None
        or outbox.topic != "control.job.completed"
        or outbox.event_key != f"{job.job_id}:job_completed"
        or (outbox.job_id, outbox.run_id) != (job.job_id, job.run_id)
        or any(
            not _json_values_equal_strict(outbox.payload.get(key), value)
            for key, value in terminal.payload.items()
        )
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_completion_not_established")
    progress = outbox.payload.get("progress")
    if type(progress) is not dict:
        raise ModelInputSuccessorActionError("native_model_input_use_terminal_checkpoint_missing")
    checkpoint = ModelInputUseActionCheckpoint.model_validate(progress.get("model_input_use"))
    if (
        checkpoint.schema_version is not None
        or checkpoint.execution_ref is None
        or checkpoint.result_ref is None
        or any(
            not _json_values_equal_strict(progress.get(key), value)
            or not _json_values_equal_strict(job.progress.get(key), value)
            for key, value in model_input_use_terminal_progress(checkpoint).items()
        )
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_terminal_checkpoint_mismatch")
    return checkpoint, terminal, running.created_at


def _verify_native_model_input_use_completed_work(
    control: ControlPlaneService,
    *,
    resolved: GenericN5ResolvedResult,
    input_record: GenericCycleSimulationN5InputV1,
    window: BudgetLedgerReentryBudgetWindow,
    started_at: datetime,
    finished_at: datetime,
    require_failed_attempt_cut: bool = False,
    original_work_cut_revision: int | None = None,
) -> int:
    """Reopen one completed standard unit from the original run's ledger."""
    from polisyos.scientist.orchestration.engine import (
        BudgetMiddleware,
        ProducerBudgetObservation,
        verify_completed_standard_invocations_historical,
    )

    from ..model_input_successor_action import ModelInputSuccessorActionError

    result = resolved.result
    ledger = control._llm_producer_settlement_store
    work = result.physical_work_observations
    bases = result.diagnostics.get("producer_budget_observations")
    if (
        len(work) != 1
        or len(result.trajectories) == 0
        or result.receipt.engine_kind != "program_graph"
        or resolved.request.replications != 1
        or resolved.request.program_graph_comparator_profile is not None
        or result.diagnostics.get("physical_work_capture_status") != "observed"
        or "physical_work_interruption" in result.diagnostics
        or type(ledger) is not BudgetMiddleware
        or type(bases) is not dict
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_physical_completion_missing")
    (unit,) = work
    basis = ProducerBudgetObservation.model_validate(bases.get(unit.budget_source_basis_digest))
    operation_id = unit.invocation_quota_operation_id
    request_digest = unit.invocation_quota_request_digest
    profile_digest = unit.invocation_quota_profile_digest
    if (
        operation_id is None
        or request_digest is None
        or profile_digest is None
        or unit.status != "completed"
        or unit.budget_status != "current_owner_checked"
        or unit.invocation_quota_purpose != "standard"
        or unit.invocation_quota_status != "completed"
        or not started_at <= unit.started_at <= unit.completed_at <= finished_at
        or basis.source_basis_digest != unit.budget_source_basis_digest
        or basis.run_binding != window.scope.run_binding
        or basis.configured_limit_usd != window.effective_limit_usd
        or basis.ledger_revision < window.revision
        or basis.remaining_usd <= 0
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_physical_completion_mismatch")
    (reservation,) = verify_completed_standard_invocations_historical(
        settlement_store=ledger,
        expected_run_binding=window.scope.run_binding,
        expected_policy=input_record.n5.invocation_quota_policy,
        expected_settlement_owner=basis.settlement_owner,
        expected_invocations=((operation_id, request_digest, profile_digest),),
    )
    if reservation.revision <= window.revision:
        raise ModelInputSuccessorActionError("native_model_input_use_physical_work_before_window")
    if require_failed_attempt_cut:
        return _verify_native_model_input_use_failed_work_cut(
            ledger,
            window=window,
            reservation=reservation,
            settlement_owner=basis.settlement_owner,
            original_work_cut_revision=original_work_cut_revision,
        )
    return reservation.revision


def _verify_native_model_input_use_failed_work_cut(
    ledger: BudgetMiddleware,
    *,
    window: BudgetLedgerReentryBudgetWindow,
    reservation: BudgetLedgerInvocationReservation,
    settlement_owner: tuple[str, str, str],
    original_work_cut_revision: int | None,
) -> int:
    """Require one physical unit in the retained cut without guessing legacy action identity."""
    from polisyos.scientist.orchestration.engine.producer_budget import _capacity_store_snapshot

    from ..model_input_successor_action import ModelInputSuccessorActionError

    owner, resource, anchor, snapshot = _capacity_store_snapshot(ledger, require_existing_lock=True)
    if (
        owner != settlement_owner
        or resource != window.resource_identity
        or snapshot.revision != anchor[0]
        or snapshot.ledger_id != window.ledger_id
        or snapshot.reentry_budget_windows.get(window.window_id) != window
        or snapshot.invocation_reservations.get(reservation.operation_id) != reservation
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_window_changed")
    cut_revision = (
        snapshot.revision if original_work_cut_revision is None else original_work_cut_revision
    )
    if (
        type(cut_revision) is not int
        or not reservation.revision <= cut_revision <= snapshot.revision
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_cut_not_established")
    # The v1 row has no action selector. An earlier revision excludes this
    # action because its budget window precedes physical admission. Later
    # same-run records are ambiguous even after failure: mutation times do
    # not establish the worker stopped. The protected settlement seals the
    # verified denominator, excluding new work only on subsequent reads.
    if any(
        row.run_id == reservation.run_id
        and row.operation_id != reservation.operation_id
        and window.revision < row.revision <= cut_revision
        for row in snapshot.invocation_reservations.values()
    ):
        raise ModelInputSuccessorActionError(
            "native_model_input_use_custody_physical_denominator_not_established"
        )
    return cut_revision


@dataclass(frozen=True, slots=True)
class PreparedNativeModelInputUseTerminalCustody:
    """Selected failed-attempt evidence for the protected Control Store transition."""

    job: ControlJobRecord
    scope: ControlJobExecutionScope
    checkpoint: ModelInputUseActionCheckpoint
    running: _ControlJobLifecycleSourceEventRecord
    failure: _ControlJobLifecycleSourceEventRecord
    verify_precommit: Callable[[], int]


def _require_native_model_input_use_cas_refs(
    store: ArtifactStore, refs: tuple[ArtifactRef, ...]
) -> None:
    from polisyos.core.artifacts import artifact_ref_for_manifest, artifact_ref_identity_key

    from ..model_input_successor_action import ModelInputSuccessorActionError

    for ref in {artifact_ref_identity_key(ref): ref for ref in refs}.values():
        if (
            ref.manifest_profile_sha256 is None
            or artifact_ref_for_manifest(store.get_manifest(ref)) != ref
            or not store.verify(ref).ok
        ):
            raise ModelInputSuccessorActionError(
                "native_model_input_use_custody_artifact_withdrawn"
            )


def _prepare_native_model_input_use_historical_approval(
    action_service: AcquisitionActionService,
    *,
    identity: ModelInputSuccessorIdentity,
    scope: ControlJobExecutionScope,
    decision_ref: ArtifactRef,
    started_at: datetime,
    completed_at: datetime,
) -> Callable[[], None]:
    """Verify original DS9 and PA2 against the actual physical time coordinates."""
    from polisyos.core.artifacts import artifact_ref_for_manifest, load_core_json_artifact
    from polisyos.runtime.quality.agent_action_authority import AgentActionAuthorityDecision
    from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
        DelegationContract,
        HumanDecisionRecord,
    )

    from ..model_input_successor_action import ModelInputSuccessorActionError

    refused = "native_model_input_use_custody_original_approval_not_established"
    provider = action_service._require_model_input_use_authority_provider()
    human = provider._human_decisions
    store = action_service.control_service._artifact_store
    database = action_service.control_service._control_store
    # The shared replay has already authenticated this exact allow and creation actor.
    decision = AgentActionAuthorityDecision.model_validate(
        load_core_json_artifact(store, decision_ref)
    )
    record_ref = decision.human_decision_record_ref
    if (
        human is None
        or record_ref is None
        or decision.contract_ref is None
        or decision.human_decision_request is None
    ):
        raise ModelInputSuccessorActionError(refused)
    signed = human._read_record_custody(
        record_ref, tenant_id=identity.tenant_id, run_id=identity.run_id
    )
    record = signed.model
    if (
        type(record) is not HumanDecisionRecord
        or record.source_ref is None
        or record.recorded_at is None
        or record.valid_from is None
        or record.valid_until is None
        or not (
            record.valid_from
            <= record.decided_at
            <= record.recorded_at
            <= decision.decided_at
            <= started_at
            <= completed_at
            < record.valid_until
        )
        or record.decision_action_exercised != "approve"
        or not record.active_choice
        or not record.five_rights_check.all_pass()
        or record.responsibility_integrity.status != "pass"
        or record.basis_ref != decision.contract_ref
        or record.basis_digest != decision.contract_content_hash
    ):
        raise ModelInputSuccessorActionError(refused)
    contract_ref = artifact_ref_for_manifest(store.get_manifest(decision.contract_ref))
    contract = DelegationContract.model_validate(load_core_json_artifact(store, contract_ref))
    envelopes = tuple(
        row for row in contract.action_envelopes if row.envelope_id == decision.envelope_id
    )
    if len(envelopes) != 1:
        raise ModelInputSuccessorActionError(refused)
    (envelope,) = envelopes
    adapter = provider._human_adapter(record, record_ref, envelope, decision.operation_id)
    # Reopen signed source, mandate, reviewer, presentation and exposure at work time.
    authority = human._revalidate_record_inputs(record, adapter, now=completed_at)
    source = authority.source
    if (
        source.outcome != "refused"
        or source.refusal_reasons != ("human_decision_missing",)
        or source.action_kind != decision.action_kind
        or source.operation_content_hash != decision.operation_content_hash
        or source.invocation_content_hash != decision.invocation_content_hash
        or source.intent_content_hash != decision.intent_content_hash
        or source.permission_snapshot != decision.permission_snapshot
        or source.admission_bundle_ref != decision.admission_bundle_ref
        or source.contract_ref != decision.contract_ref
        or source.envelope_ref != decision.envelope_ref
        or source.effect_binding_id != decision.effect_binding_id
        or source.effect_binding_digest != decision.effect_binding_digest
        or source.human_decision_request != decision.human_decision_request
        or authority.envelope != envelope
        or not envelope.valid_from <= started_at <= completed_at < envelope.valid_until
    ):
        raise ModelInputSuccessorActionError(refused)

    def read_reservation() -> _ReservationRecord | None:
        return human._sink.get_reservation_generation(
            tenant_id=identity.tenant_id,
            governed_action_key=record.governed_action_key or "",
            reservation_version=record.reservation_version or 0,
        )

    reservation = read_reservation()
    if (
        reservation is None
        or reservation.state != "committed"
        or reservation.reservation_id != record.reservation_id
        or reservation.record_ref != record_ref
        or reservation.record_sha256 != record_ref
        or reservation.binding_sha256 != record.binding_sha256
        or reservation.durable_event_id != signed.durable_event_id
        or reservation.committed_at is None
        or not record.recorded_at <= reservation.committed_at <= started_at
        or reservation.record_valid_until <= completed_at
    ):
        raise ModelInputSuccessorActionError(refused)
    events = database.list_diagnostic_events(event_id=signed.durable_event_id, limit=2)
    if len(events) != 1:
        raise ModelInputSuccessorActionError(refused)

    def verify() -> None:
        # Reopen the bounded signed DS9 packet at the same original instant,
        # including each exposure event and the bytes actually delivered.
        action_service.require_model_input_use_decision_history(
            identity=identity,
            decision_ref=str(decision_ref.artifact_id),
            execution_scope=scope,
        )
        if (
            human._read_record_custody(
                record_ref, tenant_id=identity.tenant_id, run_id=identity.run_id
            )
            != signed
            or human._revalidate_record_inputs(record, adapter, now=completed_at) != authority
            or database.list_diagnostic_events(event_id=signed.durable_event_id, limit=2) != events
            or read_reservation() != reservation
        ):
            raise ModelInputSuccessorActionError(refused)

    return verify


def _native_model_input_use_history_job(
    control_service: ControlPlaneService,
    *,
    action_service: AcquisitionActionService,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    action_job_id: str,
) -> tuple[ControlJobRecord, ControlJobExecutionScope]:
    from ..acquisition_action_service import AcquisitionActionService
    from ..model_input_successor_action import ModelInputSuccessorActionError
    from .run_lifecycle import ControlPlaneService

    if (
        type(control_service) is not ControlPlaneService
        or type(action_service) is not AcquisitionActionService
        or action_service.control_service is not control_service
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_owner_missing")
    database = control_service._control_store
    job = database.get_job(action_job_id)
    if (
        type(job) is not ControlJobRecord
        or job.job_id != action_job_id
        or job.run_id != run_id
        or job.kind != "acquisition"
        or job.payload_ref is None
    ):
        raise KeyError(action_job_id)
    scope, _ = database._reconcile_control_job_creation_envelope(job)
    if scope.status != "established" or (scope.tenant_id, scope.cell_id) != (tenant_id, cell_id):
        raise KeyError(action_job_id)
    return job, scope


def _failed_native_model_input_use_stage(
    database: ControlPlaneStore,
    job: ControlJobRecord,
    *,
    expected_attempt: int,
) -> tuple[
    ModelInputUseActionCheckpoint,
    _ControlJobLifecycleSourceEventRecord,
    _ControlJobLifecycleSourceEventRecord,
]:
    """Select the original lease and the exact stage preserved by its failure outbox."""
    from ..control_plane_store import _json_values_equal_strict
    from ..model_input_successor_action import (
        ModelInputSuccessorActionError,
        ModelInputUseActionCheckpoint,
    )

    refused = "native_model_input_use_custody_failed_attempt_not_established"
    if (
        type(expected_attempt) is not int
        or expected_attempt < 1
        or job.attempt != expected_attempt
        or job.state != "failed"
        or job.finished_at is None
        or job.lease_owner is not None
        or job.lease_expires_at is not None
    ):
        raise ModelInputSuccessorActionError(refused)
    running = database._latest_control_job_lifecycle_event_record(
        job_id=job.job_id, event_type="job_running"
    )
    failure = database.get_job_terminal_source_event_record(job.job_id)
    worker_id = running.payload.get("lease_owner")
    outbox = database._get_outbox_event_by_key(
        topic="control.job.failed", event_key=f"{job.job_id}:job_failed:attempt:{expected_attempt}"
    ) or database._get_outbox_event_by_key(
        topic="control.job.failed", event_key=f"{job.job_id}:job_failed"
    )
    if (
        running.payload.get("state") != "running"
        or not isinstance(worker_id, str)
        or not worker_id
        or failure.event_type != "job_failed"
        or failure.payload.get("state") != "failed"
        or failure.payload.get("lease_owner") != worker_id
        or failure.payload.get("error_message") != job.error_message
        or any(
            type(row.payload.get("attempt")) is not int
            or row.payload["attempt"] != expected_attempt
            for row in (running, failure)
        )
        or running.event_id >= failure.event_id
        or running.created_at > failure.created_at
        or job.finished_at > failure.created_at
        or outbox is None
        or (outbox.job_id, outbox.run_id) != (job.job_id, job.run_id)
        or any(
            not _json_values_equal_strict(outbox.payload.get(key), value)
            for key, value in failure.payload.items()
        )
        or not _json_values_equal_strict(outbox.payload.get("progress"), job.progress)
    ):
        raise ModelInputSuccessorActionError(refused)
    raw_checkpoint = job.progress.get("model_input_use")
    checkpoint = ModelInputUseActionCheckpoint.model_validate(raw_checkpoint)
    if (
        checkpoint.schema_version is not None
        or checkpoint.execution_ref is not None
        or checkpoint.result_ref is not None
        or not _json_values_equal_strict(
            raw_checkpoint, checkpoint.model_dump(mode="json", exclude_none=True)
        )
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_stage_not_established")
    return checkpoint, running, failure


def prepare_native_model_input_use_terminal_custody(
    control_service: ControlPlaneService,
    *,
    action_service: AcquisitionActionService,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    action_job_id: str,
    failed_attempt: int,
    phase_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    execution_ref: ArtifactRef,
) -> PreparedNativeModelInputUseTerminalCustody:
    """Verify an explicitly selected completed result inside one original failed attempt."""
    from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5ExecutionV3,
        parse_generic_cycle_simulation_n5_execution,
    )

    from ..model_input_successor_action import (
        ModelInputSuccessorActionError,
        ModelInputUseActionCheckpoint,
    )

    job, scope = _native_model_input_use_history_job(
        control_service,
        action_service=action_service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        action_job_id=action_job_id,
    )
    database = control_service._control_store
    stage, running, failure = _failed_native_model_input_use_stage(
        database, job, expected_attempt=failed_attempt
    )
    if (
        not scope.actor_authenticated
        or not scope.actor_subject
        or scope.actor_subject != job.submitted_by
        or stage.phase_ref != phase_ref
        or stage.semantic_successor_ref != semantic_successor_ref
        or type(execution_ref) is not ArtifactRef
        or execution_ref.kind != "runtime.quality.generic_cycle_simulation_n5_execution"
        or execution_ref.media_type != "application/json"
        or execution_ref.manifest_profile_sha256 is None
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_selection_mismatch")
    execution = parse_generic_cycle_simulation_n5_execution(
        load_core_json_artifact(control_service._artifact_store, execution_ref)
    )
    if (
        type(execution) is not GenericCycleSimulationN5ExecutionV3
        or execution.status != "joint_simulated"
        or execution.result_ref is None
        or (
            execution.job_id,
            execution.run_id,
            execution.tenant_id,
            execution.cell_id,
        )
        != (action_job_id, run_id, tenant_id, cell_id)
    ):
        raise ModelInputSuccessorActionError(
            "native_model_input_use_custody_execution_not_selected"
        )
    checkpoint = ModelInputUseActionCheckpoint(
        phase_ref=phase_ref,
        semantic_successor_ref=semantic_successor_ref,
        execution_ref=execution_ref,
        result_ref=execution.result_ref,
    )
    _, verify_precommit = _replay_native_model_input_use_n5_result(
        control_service,
        action_service=action_service,
        job=job,
        scope=scope,
        checkpoint=checkpoint,
        started_at=running.created_at,
        work_terminal=failure,
    )
    if (
        verify_precommit is None
        or database.get_job(action_job_id) != job
        or _failed_native_model_input_use_stage(database, job, expected_attempt=failed_attempt)
        != (stage, running, failure)
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_changed_during_read")
    return PreparedNativeModelInputUseTerminalCustody(
        job=job,
        scope=scope,
        checkpoint=checkpoint,
        running=running,
        failure=failure,
        verify_precommit=verify_precommit,
    )


def _native_model_input_use_work_terminal(
    database: ControlPlaneStore,
    terminal: _ControlJobLifecycleSourceEventRecord,
    checkpoint: ModelInputUseActionCheckpoint,
) -> tuple[_ControlJobLifecycleSourceEventRecord, int | None]:
    """Recover the original failure and owner-sealed ledger revision for cold replay."""
    from ..control_plane_store import _json_values_equal_strict
    from ..model_input_successor_action import ModelInputSuccessorActionError

    marker = database.get_native_model_input_use_result_custody_event(terminal.job_id)
    marker_id = terminal.payload.get("native_result_custody_event_id")
    if marker is None and marker_id is None:
        return terminal, None
    if (
        marker is None
        or type(marker_id) is not int
        or marker.event_id != marker_id
        or marker.event_id >= terminal.event_id
        or not _json_values_equal_strict(
            marker.payload.get("checkpoint"),
            checkpoint.model_dump(mode="json", exclude_none=True),
        )
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_marker_mismatch")
    cut_revision = marker.payload.get("original_work_cut_revision")
    if type(cut_revision) is not int or cut_revision < 1:
        raise ModelInputSuccessorActionError("native_model_input_use_custody_cut_not_established")
    failure = database.get_job_lifecycle_event_record(
        job_id=terminal.job_id,
        event_id=marker.payload["original_failed_event_id"],
        expected_event_type="job_failed",
    )
    return failure, cut_revision


def read_completed_native_model_input_use_n5_result(
    control_service: ControlPlaneService,
    *,
    action_service: AcquisitionActionService,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    action_job_id: str,
) -> RunModelInputUseN5SuccessorProjection:
    """Read one terminal Native candidate result through its immutable owners."""
    from ..model_input_successor_action import ModelInputSuccessorActionError

    job, scope = _native_model_input_use_history_job(
        control_service,
        action_service=action_service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        action_job_id=action_job_id,
    )
    database = control_service._control_store
    checkpoint, terminal, started_at = _closed_native_model_input_use_checkpoint(database, job)
    work_terminal, cut_revision = _native_model_input_use_work_terminal(
        database, terminal, checkpoint
    )
    projection, _ = _replay_native_model_input_use_n5_result(
        control_service,
        action_service=action_service,
        job=job,
        scope=scope,
        checkpoint=checkpoint,
        started_at=started_at,
        work_terminal=work_terminal,
        original_work_cut_revision=cut_revision,
    )
    if (
        database.get_job(action_job_id) != job
        or _closed_native_model_input_use_checkpoint(database, job)
        != (checkpoint, terminal, started_at)
        or _native_model_input_use_work_terminal(database, terminal, checkpoint)
        != (work_terminal, cut_revision)
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_changed_during_read")
    return projection


def _replay_native_model_input_use_n5_result(
    control_service: ControlPlaneService,
    *,
    action_service: AcquisitionActionService,
    job: ControlJobRecord,
    scope: ControlJobExecutionScope,
    checkpoint: ModelInputUseActionCheckpoint,
    started_at: datetime,
    work_terminal: _ControlJobLifecycleSourceEventRecord,
    original_work_cut_revision: int | None = None,
) -> tuple[RunModelInputUseN5SuccessorProjection, Callable[[], int] | None]:
    """Reconcile a Native result without requiring or minting a current work grant."""
    from polisyos.core.artifacts import (
        artifact_ref_for_manifest,
        artifact_ref_identity_key,
        load_core_json_artifact,
    )
    from polisyos.core.contracts.runtime import (
        RunGenericCycleSimulationN5ResultBody,
        RunModelInputUseBlockedSourceProjection,
        RunModelInputUseN5SuccessorProjection,
    )
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
    from polisyos.runtime.quality.acquisition_world_growth import (
        replay_native_derivation_input_collection,
    )
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
    from polisyos.runtime.quality.generation_source import NATIVE_REQUALIFIED_SOURCE_SCHEMA
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5ProgramGraphRequestProfileV4,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5ExecutionV3,
        GenericCycleSimulationN5InputV1,
        GenericN5ExecutionJoinExpectation,
        parse_generic_cycle_simulation_n5_execution,
    )
    from polisyos.runtime.quality.model_input_successor_selection import (
        read_model_input_use_action_phase,
    )
    from polisyos.runtime.quality.native_generic_context import (
        _use_checkpoint_event_id,
        replay_native_model_input_use_world_selection,
    )
    from polisyos.runtime.quality.substrate_registry import run_catalog_source_call
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    from ..acquisition_n5_projection import (
        n5_numerical_body_payload,
        read_selected_n5_result_manifest,
    )
    from ..model_input_successor_action import (
        ModelInputSuccessorActionError,
        _expected_phase,
        _read_checkpoint_selection,
        _resolve_action_budget_window,
        resolve_model_input_successor_history,
        unwrap_native_model_input_use_request,
    )

    database = control_service._control_store
    store = control_service._artifact_store
    tenant_id, cell_id = scope.tenant_id, scope.cell_id
    run_id, action_job_id = job.run_id, job.job_id
    if not tenant_id or not cell_id or not run_id or job.payload_ref is None:
        raise ModelInputSuccessorActionError("native_model_input_use_history_identity_mismatch")
    execution_ref, result_ref = checkpoint.execution_ref, checkpoint.result_ref
    if execution_ref is None or result_ref is None:
        raise ModelInputSuccessorActionError("native_model_input_use_terminal_checkpoint_missing")
    phase = read_model_input_use_action_phase(store, checkpoint.phase_ref)
    raw_payload = control_service._load_payload_ref(
        job.payload_ref, kind="runtime.control_job_payload.acquisition"
    )
    request = unwrap_native_model_input_use_request(raw_payload, phase=phase)
    identity = resolve_model_input_successor_history(
        control_service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        request=request,
        checkpoint=checkpoint,
    )
    if (identity.job_id, identity.route_id) != (action_job_id, phase.route_id):
        raise ModelInputSuccessorActionError("native_model_input_use_history_identity_mismatch")
    decision_ref = str(phase.authority_decision_ref.artifact_id)
    action_service.require_model_input_use_decision_history(
        identity=identity, decision_ref=decision_ref, execution_scope=scope
    )
    selected = _read_checkpoint_selection(
        store,
        selection=identity,
        checkpoint=checkpoint,
        phase=_expected_phase(
            store, identity, action_payload_ref=job.payload_ref, authority_decision_ref=decision_ref
        ),
    )
    if (
        selected.schema_version != "polisyos.runtime.ModelInputSuccessorSelection@1.0"
        or selected.action_attempt != job.attempt
        or selected.action_worker_id != work_terminal.payload["lease_owner"]
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_worker_mismatch")

    execution = parse_generic_cycle_simulation_n5_execution(
        load_core_json_artifact(store, execution_ref)
    )
    if (
        type(execution) is not GenericCycleSimulationN5ExecutionV3
        or execution.status != "joint_simulated"
        or execution.result_ref != result_ref
        or execution_ref == request.blocked_execution_ref
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_execution_not_selected")
    n5_input_ref = execution.input_ref
    n5_input = GenericCycleSimulationN5InputV1.model_validate(
        load_core_json_artifact(store, n5_input_ref)
    )
    n5_profile = n5_input.n5
    world_ref = n5_input.native_world_checkpoint_ref
    if world_ref is None:
        raise ModelInputSuccessorActionError("native_model_input_use_world_checkpoint_missing")
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    owner.bind_native_world_history(
        control_store=database, event_log=control_service._diagnostic_event_log
    )
    world = replay_native_model_input_use_world_selection(owner, checkpoint_ref=world_ref)
    source = world.source_selection.historical_selection
    origin = identity.origin
    original = source.original_generic_input
    n4_manifest = store.get_manifest(n5_input.n4_source_ref)
    if (
        world.phase != phase
        or world.successor_selection != selected
        or world.checkpoint.model_input_use_phase_ref != checkpoint.phase_ref
        or world.checkpoint.model_input_successor_selection_ref != checkpoint.semantic_successor_ref
        or world.checkpoint.predecessor_terminal_ref != request.native_use.predecessor_terminal_ref
        or source.checkpoint_ref != request.native_use.world_checkpoint_ref
        or source.original_generic_execution_ref != request.blocked_execution_ref
        or source.original_generic_input_ref != n5_input.original_generic_input_ref
        or n5_input.source_run_id != original.source_run_id
        or n5_input.cycle_index != original.cycle_index
        or n5_input.outcome_variable != original.outcome_variable
        or type(n5_profile) is not GenericCycleN5ProgramGraphRequestProfileV4
        or n5_profile != original.n5
        or n5_profile.invocation_purpose != "standard"
        or n4_manifest.artifact_schema is None
        or n4_manifest.artifact_schema.name != NATIVE_REQUALIFIED_SOURCE_SCHEMA
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_selection_mismatch")

    predecessor_ref = request.native_use.predecessor_terminal_ref
    pending = source.pending_action_phase
    old_head = database.get_acquisition_action_head_by_receipt(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=origin.source_job_id,
        route_id=pending.route_id,
        action_generation=pending.action_generation,
        receipt_ref=str(predecessor_ref.artifact_id),
    )
    if (
        old_head is None
        or old_head.job_id != pending.job_id
        or old_head.receipt_phase != "terminal"
        or old_head.receipt_manifest_profile_sha256 != predecessor_ref.manifest_profile_sha256
    ):
        raise ModelInputSuccessorActionError(
            "native_model_input_use_history_predecessor_not_selected"
        )
    prior = control_service.acquisition_route_sink.verify_action_head(old_head).latest_receipt
    if (
        type(prior) is not AcquisitionRouteLoopReceipt
        or prior.schema_version != "AcquisitionRouteLoopReceipt@1.2"
        or prior.terminal_outcome != "reentry_completed"
        or prior.predecessor_receipt_ref != str(source.pending_action_phase_ref.artifact_id)
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_history_predecessor_mismatch")

    outcome, resolved = owner.resolve_n5_execution_join_with_result(
        execution_ref,
        expected=GenericN5ExecutionJoinExpectation(
            input_ref=n5_input_ref,
            result_ref=result_ref,
            status="joint_simulated",
            model_input_obligation_set_ref=None,
            n4_source_ref=n5_input.n4_source_ref,
            context_job_ref=world.checkpoint.context_job_ref,
            profile_ref=source.original_profile_ref,
            child_family_ref=None,
            child_set_ref=None,
            profile_selection_ref=source.original_profile.profile_selection_ref,
            profile=source.original_profile,
            design_problem_ref=cycle_job_design_problem_ref(source.problem),
            outcome_variable=original.outcome_variable,
            cycle_index=original.cycle_index,
            candidate_id=n5_input.candidate_id,
            candidate_atom_hash=n5_input.candidate_atom_hash,
            world_model_record_content_hash=source.world_model_record.content_hash,
            job_id=action_job_id,
            run_id=run_id,
            source_run_id=original.source_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        ),
    )
    if (
        outcome.status != "resolved"
        or outcome.execution != execution
        or outcome.input_record != n5_input
        or resolved is None
        or _joint_simulation_port_outcome(resolved.result, request=resolved.request)[0]
        != "joint_simulated"
    ):
        raise ModelInputSuccessorActionError(
            outcome.code or "native_model_input_use_n5_result_not_verified"
        )
    window = _resolve_action_budget_window(
        control_service, selection=identity, phase_ref=checkpoint.phase_ref, open_if_missing=False
    )
    if (
        window.window_id != selected.reentry_budget_window_id
        or window.record_digest != selected.reentry_budget_window_digest
    ):
        raise ModelInputSuccessorActionError(
            "native_model_input_use_history_budget_window_mismatch"
        )
    _verify_native_model_input_use_completed_work(
        control_service,
        resolved=resolved,
        input_record=n5_input,
        window=window,
        started_at=started_at,
        finished_at=work_terminal.created_at,
        require_failed_attempt_cut=work_terminal.event_type == "job_failed",
        original_work_cut_revision=original_work_cut_revision,
    )
    manifest = read_selected_n5_result_manifest(
        store, result_ref, tenant_id=tenant_id, cell_id=cell_id
    )
    limitations = resolved.result.verified_semantic_input_limitation_codes
    if artifact_ref_for_manifest(manifest) != result_ref or limitations is None:
        raise ModelInputSuccessorActionError(
            "native_model_input_use_result_limitations_not_verified"
        )
    body = RunGenericCycleSimulationN5ResultBody.model_validate(
        n5_numerical_body_payload(
            ref=result_ref,
            manifest=manifest,
            result=resolved.result,
            authority_purpose="cycle_input_candidate_only",
            store=store,
            request=resolved.request,
        )
    )
    projection = RunModelInputUseN5SuccessorProjection(
        run_id=run_id,
        action_job_id=action_job_id,
        action_status="completed",
        result_status="resolved",
        blocked_source=RunModelInputUseBlockedSourceProjection(
            run_id=run_id,
            source_job_id=origin.source_job_id,
            design_problem_ref=origin.source_cycle.design_problem_ref,
            cycle_index=origin.source_cycle.cycle_index,
            candidate_id=origin.source_cycle.selected_candidate_ref,
            candidate_content_hash=origin.source_cycle.selected_candidate_content_hash,
            blocked_execution_ref=origin.n5_execution_ref,
            model_input_obligation_set_ref=origin.routing_report.obligation_set_ref,
            routing_report_ref=origin.routing_report_ref,
        ),
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        n5_execution_ref=execution_ref,
        simulation_result_ref=result_ref,
        result_body=body,
        semantic_input_limitation_codes=limitations,
    )
    if work_terminal.event_type != "job_failed":
        return projection, None
    (physical,) = resolved.result.physical_work_observations
    verify_approval = _prepare_native_model_input_use_historical_approval(
        action_service,
        identity=identity,
        scope=scope,
        decision_ref=phase.authority_decision_ref,
        started_at=physical.started_at,
        completed_at=physical.completed_at,
    )
    exact_refs = (
        phase.action_payload_ref,
        checkpoint.phase_ref,
        checkpoint.semantic_successor_ref,
        execution_ref,
        n5_input_ref,
        result_ref,
        world_ref,
        source.checkpoint_ref,
        source.pending_action_phase_ref,
        predecessor_ref,
        n5_input.n4_source_ref,
        world.checkpoint.context_job_ref,
        world.checkpoint.original_generic_input_ref,
        world.checkpoint.original_profile_ref,
        world.checkpoint.world_model_ref,
        world.checkpoint.native_input_bindings_ref,
    )
    catalog_source = control_service.catalog_serving_source
    collection_ref = world.checkpoint.native_input_collection_ref
    selected_collection = world.source_selection.input_collection_replay
    plans = resolved.request.engine_plan
    if len(plans) != 1:
        raise ModelInputSuccessorActionError("native_model_input_use_custody_graph_not_selected")
    (plan,) = plans
    if (
        plan.engine_kind != "program_graph"
        or plan.program_compilation_ref is None
        or plan.program_graph_ref is None
        or plan.exec_plan_ref is None
    ):
        raise ModelInputSuccessorActionError("native_model_input_use_custody_graph_not_selected")
    world_record = source.world_model_record
    expected_graph = (
        artifact_ref_identity_key(plan.program_compilation_ref),
        artifact_ref_identity_key(plan.program_graph_ref),
        artifact_ref_identity_key(plan.exec_plan_ref),
        artifact_ref_identity_key(world_model_artifact_views(world_record).registry_bundle_ref),
    )
    world_event_id = _use_checkpoint_event_id(world.checkpoint)
    world_events = database.list_diagnostic_events(event_id=world_event_id, limit=2)
    if len(world_events) != 1:
        raise ModelInputSuccessorActionError("native_model_input_use_custody_world_event_missing")

    def verify_precommit() -> int:
        _require_native_model_input_use_cas_refs(store, exact_refs)
        if control_service.catalog_serving_source is not catalog_source:
            raise ModelInputSuccessorActionError("native_model_input_use_custody_catalog_changed")
        try:
            replayed_collection = run_catalog_source_call(
                catalog_source, replay_native_derivation_input_collection, store, collection_ref
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ModelInputSuccessorActionError(
                "native_model_input_use_custody_collection_withdrawn"
            ) from exc
        if replayed_collection != selected_collection:
            raise ModelInputSuccessorActionError(
                "native_model_input_use_custody_collection_withdrawn"
            )
        try:
            graph = run_catalog_source_call(
                catalog_source, owner._read_selected_program_graph, n5_profile, world_record
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ModelInputSuccessorActionError(
                "native_model_input_use_custody_graph_withdrawn"
            ) from exc
        if (
            tuple(
                artifact_ref_identity_key(ref)
                for ref in (
                    graph.compile_report_ref,
                    graph.graph_ref,
                    graph.exec_plan_ref,
                    graph.registry_bundle_ref,
                )
            )
            != expected_graph
        ):
            raise ModelInputSuccessorActionError("native_model_input_use_custody_graph_withdrawn")
        if (
            database.list_diagnostic_events(event_id=world_event_id, limit=2) != world_events
            or database.get_acquisition_action_head_by_receipt(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=origin.source_job_id,
                route_id=pending.route_id,
                action_generation=pending.action_generation,
                receipt_ref=str(predecessor_ref.artifact_id),
            )
            != old_head
        ):
            raise ModelInputSuccessorActionError("native_model_input_use_custody_history_withdrawn")
        verify_approval()
        budget = control_service._llm_producer_settlement_store
        if budget is None or budget.resolve_reentry_budget_window_safe(window.scope) != window:
            raise ModelInputSuccessorActionError("native_model_input_use_custody_window_changed")
        return _verify_native_model_input_use_completed_work(
            control_service,
            resolved=resolved,
            input_record=n5_input,
            window=window,
            started_at=started_at,
            finished_at=work_terminal.created_at,
            require_failed_attempt_cut=True,
        )

    return projection, verify_precommit


class _ModelInputUseJobCompletion(dict[str, Any]):
    """Carry completion inputs for owner replay, without asserting verified authority.

    Only progress is mapping data. The completer reopens the selected inputs
    under its actual worker fence before passing an ephemeral CAS to the store.
    """

    __slots__ = (
        "action_payload_ref",
        "authority_decision_ref",
        "checkpoint",
        "currentness_resolver",
        "selection",
    )

    def __init__(
        self,
        *,
        progress: dict[str, Any],
        selection: SelectedModelInputSuccessorAction,
        checkpoint: ModelInputUseActionCheckpoint,
        action_payload_ref: str,
        authority_decision_ref: str,
        currentness_resolver: Callable[[], bool],
    ) -> None:
        from ..model_input_successor_action import (
            ModelInputUseActionCheckpoint,
            SelectedModelInputSuccessorAction,
        )

        if (
            type(selection) is not SelectedModelInputSuccessorAction
            or type(checkpoint) is not ModelInputUseActionCheckpoint
            or checkpoint.schema_version != "polisyos.runtime.ModelInputUseActionCheckpoint@2.0"
            or not callable(currentness_resolver)
        ):
            raise TypeError("model_input_use_completion_inputs_untyped")
        super().__init__(progress)
        self.selection = selection
        self.checkpoint = checkpoint
        self.action_payload_ref = action_payload_ref
        self.authority_decision_ref = authority_decision_ref
        self.currentness_resolver = currentness_resolver


class _DiagnosticExecutionScopeRecord(BaseModel):
    """Typed source and establishment state for one durable diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.control_execution_scope.v1"] = (
        "polisyos.runtime.control_execution_scope.v1"
    )
    status: Literal["established", "not_established"]
    source: Literal["job_admission", "authenticated_request"]
    limitation_code: Literal["control_job_execution_scope_not_established"] | None = None


class _ControlJobExecutionBinding(BaseModel):
    """Bind a diagnostic to its persisted control-job lifecycle source."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.runtime.control_job_execution_binding.v1"] = (
        "polisyos.runtime.control_job_execution_binding.v1"
    )
    binding_status: Literal["established"] = "established"
    proof_phase: Literal["job_admission", "running", "completed", "failed"]
    control_job_id: str
    control_run_id: str | None
    source_event_job_state: Literal["pending", "running", "completed", "failed"]
    control_worker_id: str | None
    control_worker_attempt: int | None
    source_event_id: int
    source_event_type: Literal["job_created", "job_running", "job_completed", "job_failed"]
    source_event_created_at: datetime
    source_event_payload_sha256: str
    bound_job_record_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_phase_binding(self) -> _ControlJobExecutionBinding:
        digest = self.source_event_payload_sha256
        if (
            not digest.startswith("sha256:")
            or len(digest) != 71
            or any(character not in "0123456789abcdef" for character in digest[7:])
        ):
            raise ValueError("control_job_execution_binding_payload_digest_invalid")
        if self.proof_phase == "job_admission":
            if (
                self.source_event_type != "job_created"
                or self.control_worker_id is not None
                or self.control_worker_attempt is not None
                or self.source_event_job_state not in {"pending", "failed"}
            ):
                raise ValueError("control_job_execution_binding_admission_invalid")
            return self
        if (
            self.source_event_type != f"job_{self.proof_phase}"
            or self.source_event_job_state != self.proof_phase
            or not isinstance(self.control_worker_id, str)
            or not self.control_worker_id.strip()
            or type(self.control_worker_attempt) is not int
            or self.control_worker_attempt < 1
        ):
            raise ValueError("control_job_execution_binding_worker_attempt_invalid")
        return self


@dataclass(frozen=True, slots=True)
class _DiagnosticEventEmission:
    """Report whether a diagnostic persisted and what its scope allows."""

    event_id: str | None
    status: Literal[
        "persisted",
        "candidate_diagnostic",
        "authority_withheld",
        "not_persisted",
    ]
    scope_status: Literal["established", "not_established"]
    limitation_code: str | None = None


class ControlJobDiagnosticsMixin:
    """Own one control-job lifecycle facet without changing service entrypoints."""

    @staticmethod
    def _diagnostic_scope_record(
        scope: ControlJobExecutionScope | AccessScope,
    ) -> tuple[_DiagnosticExecutionScopeRecord, str, str]:
        """Resolve diagnostic attribution only from admitted or request scope."""
        if isinstance(scope, ControlJobExecutionScope):
            source = "job_admission"
            tenant_id = scope.tenant_id
            cell_id = scope.cell_id
            subject = scope.actor_subject
            established = scope.status == "established"
        elif isinstance(scope, AccessScope):
            source = "authenticated_request"
            tenant_id = scope.tenant_id
            cell_id = scope.cell_id
            subject = scope.user_sub or scope.spiffe_id
            established = True
        else:
            raise TypeError("runtime_diagnostic_execution_scope_type_invalid")

        sentinels = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }

        def usable(value: object) -> bool:
            return (
                isinstance(value, str)
                and bool(value.strip())
                and value.strip().casefold() not in sentinels
            )

        established = established and usable(tenant_id) and usable(cell_id) and usable(subject)
        if established:
            record = _DiagnosticExecutionScopeRecord(status="established", source=source)
            return record, str(tenant_id).strip(), str(cell_id).strip()

        record = _DiagnosticExecutionScopeRecord(
            status="not_established",
            source=source,
            limitation_code="control_job_execution_scope_not_established",
        )
        return record, "tenant-unknown", "cell-unknown"

    def _build_runtime_diagnostic_event(
        self,
        *,
        job_id: str,
        run_id: str | None,
        execution_profile: str,
        phase: str,
        event_type: str,
        state_before: str | None = None,
        state_after: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_payload: Mapping[str, Any] | None = None,
        artifact_refs: list[str] | tuple[str, ...] | None = None,
        input_refs: list[str] | tuple[str, ...] | None = None,
        blocking_status: str | None = None,
        authority_bearing_payload: bool = False,
        producer_component: str = "polisyos.runtime.control",
        parent_span_id: str | None = None,
        execution_scope: ControlJobExecutionScope | AccessScope,
    ) -> tuple[
        DiagnosticEvent,
        _DiagnosticExecutionScopeRecord,
        dict[str, Any],
        Mapping[str, Any],
        bool,
        bool,
    ]:
        """Build one detached diagnostic candidate without storage or source publication."""

        trace = self._job_trace_context(
            job_id=job_id,
            payload=payload,
            parent_span_id=parent_span_id,
        )
        scope_record, tenant_id, cell_id = self._diagnostic_scope_record(execution_scope)
        caller_event_payload = dict(event_payload or {})
        scope_payload = scope_record.model_dump(mode="json")
        scope_established = scope_record.status == "established"
        authority_withheld = authority_bearing_payload and not scope_established
        persisted_event_type = (
            "polisyos.runtime.diagnostic.scope_limited.v1" if authority_withheld else event_type
        )
        if authority_withheld:
            persisted_event_payload: Mapping[str, Any] = {
                "execution_scope": scope_payload,
                "withheld_event_type": event_type,
                "authority_status": "withheld",
                "limitation_code": "control_job_execution_scope_not_established",
            }
            persisted_state_after = "not_established"
            persisted_artifact_refs: tuple[str, ...] = ()
            persisted_input_refs: tuple[str, ...] = ()
        else:
            persisted_event_payload = {
                **caller_event_payload,
                "execution_scope": scope_payload,
            }
            persisted_state_after = state_after
            persisted_artifact_refs = tuple(artifact_refs or ())
            persisted_input_refs = tuple(input_refs or ())
        event = DiagnosticEvent(
            event_id=f"evt_{uuid.uuid4().hex[:24]}",
            event_source="polisyos.runtime.control",
            event_type=persisted_event_type,
            event_time=datetime.now(UTC).replace(microsecond=0),
            event_subject=f"run/{run_id or 'run-unknown'}/job/{job_id}/phase/{phase}",
            schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
            schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
            trace_id=str(trace["trace_id"]),
            span_id=str(trace["span_id"]),
            parent_span_id=(str(trace["parent_span_id"]) if trace.get("parent_span_id") else None),
            run_id=str(run_id or "run-unknown"),
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            producer_component=producer_component,
            producer_version="2026.05.15+hds-phase2.2",
            execution_profile=execution_profile,
            phase=phase,
            state_before=state_before,
            state_after=persisted_state_after,
            payload_ref=None,
            artifact_refs=persisted_artifact_refs,
            input_refs=persisted_input_refs,
            blocking_status=("blocking" if authority_withheld else blocking_status),
            redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
            duplicate_of=None,
            dedupe_key=None,
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
        return (
            event,
            scope_record,
            caller_event_payload,
            persisted_event_payload,
            authority_withheld,
            scope_established,
        )

    def _emit_runtime_diagnostic_event(
        self,
        *,
        job_id: str,
        run_id: str | None,
        execution_profile: str,
        phase: str,
        event_type: str,
        state_before: str | None = None,
        state_after: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_payload: Mapping[str, Any] | None = None,
        artifact_refs: list[str] | tuple[str, ...] | None = None,
        input_refs: list[str] | tuple[str, ...] | None = None,
        blocking_status: str | None = None,
        authority_bearing_payload: bool = False,
        producer_component: str = "polisyos.runtime.control",
        parent_span_id: str | None = None,
        execution_scope: ControlJobExecutionScope | AccessScope,
    ) -> _DiagnosticEventEmission:
        """Persist a diagnostic with typed owner attribution or a scoped limitation."""

        (
            event,
            scope_record,
            caller_event_payload,
            persisted_event_payload,
            authority_withheld,
            scope_established,
        ) = self._build_runtime_diagnostic_event(
            job_id=job_id,
            run_id=run_id,
            execution_profile=execution_profile,
            phase=phase,
            event_type=event_type,
            state_before=state_before,
            state_after=state_after,
            payload=payload,
            event_payload=event_payload,
            artifact_refs=artifact_refs,
            input_refs=input_refs,
            blocking_status=blocking_status,
            authority_bearing_payload=authority_bearing_payload,
            producer_component=producer_component,
            parent_span_id=parent_span_id,
            execution_scope=execution_scope,
        )
        try:
            # The top-level `attempt` name is reserved for this control-worker path.
            # Domain/evaluation attempts remain in their nested step payloads.
            if _CONTROL_JOB_EXECUTION_BINDING_KEY in caller_event_payload:
                raise ControlJobLeaseLostError(
                    "runtime diagnostic caller supplied a reserved worker binding"
                )
            if "attempt" in caller_event_payload and not isinstance(
                execution_scope, ControlJobExecutionScope
            ):
                raise ControlJobLeaseLostError(
                    "runtime diagnostic attempt lacks a control-job worker proof"
                )
            payload_policy = DiagnosticEventPayloadPolicy(
                authority_bearing=authority_bearing_payload and scope_established
            )
            if isinstance(execution_scope, ControlJobExecutionScope):
                selected_job = self._control_store.get_job(job_id)
                if selected_job is None:
                    raise ControlJobLeaseLostError("runtime diagnostic source job is not present")
                if phase == "job_admission":
                    proof_purpose: Literal["execution", "completed_proof", "failed_proof"] = (
                        "execution"
                    )
                elif selected_job.state == "completed":
                    proof_purpose = "completed_proof"
                elif selected_job.state == "failed":
                    proof_purpose = "failed_proof"
                else:
                    proof_purpose = "execution"

                def source_in_transaction() -> _ControlJobExecutionLifecycleProof:
                    if phase == "job_admission":
                        self._control_store._lock_job_state(job_id)
                        current = self._control_store.get_job(job_id)
                        if current is None:
                            raise ControlJobLeaseLostError("runtime diagnostic source job missing")
                        source = self._control_store._get_job_created_source_event_record(job_id)
                        proof = _ControlJobExecutionLifecycleProof(
                            record=current,
                            proof_phase="job_admission",
                            worker_id=None,
                            attempt=None,
                            source_event=source,
                        )
                    elif proof_purpose == "completed_proof":
                        proof = self._control_store._current_execution_completed_job_proof()
                    elif proof_purpose == "failed_proof":
                        proof = self._control_store._current_execution_failed_job_proof()
                    else:
                        proof = self._control_store._current_execution_running_job_proof()
                    scope, admission_manifest = (
                        self._control_store._reconcile_control_job_creation_envelope(proof.record)
                    )
                    if phase == "job_admission" and (
                        proof.record.capability_manifest_ref != admission_manifest
                    ):
                        raise ControlJobLeaseLostError(
                            "runtime admission diagnostic manifest changed"
                        )
                    if (
                        proof.record.job_id != job_id
                        or proof.record.run_id != run_id
                        or scope != execution_scope
                    ):
                        raise ControlJobLeaseLostError("runtime diagnostic source scope changed")
                    return proof

                def read_source() -> _ControlJobExecutionLifecycleProof:
                    with self._control_store._job_transaction(purpose=proof_purpose):
                        return source_in_transaction()

                snapshot = run_guarded_dependency_operation(self._control_store, read_source)
                append_payload = self._control_job_bound_diagnostic_payload(
                    persisted_payload=persisted_event_payload,
                    caller_payload=caller_event_payload,
                    proof=snapshot,
                )
                # Preparation enforces that no caller-owned SQL transaction is
                # active. CAS/registry work occurs before the fresh write proof.
                prepared = self._diagnostic_event_log.prepare(
                    event, payload=append_payload, payload_policy=payload_policy
                )
                prepared_event, prepared_payload = prepared.publication_values()
                if prepared_payload is None:
                    raise ControlJobLeaseLostError("runtime diagnostic prepared payload missing")
                expected_binding = prepared_payload[_CONTROL_JOB_EXECUTION_BINDING_KEY]

                def append_reconciled_event() -> ControlDiagnosticEventRecord:
                    with self._control_store._job_transaction(purpose=proof_purpose):
                        current_proof = source_in_transaction()
                        current_payload = self._control_job_bound_diagnostic_payload(
                            persisted_payload={},
                            caller_payload=caller_event_payload,
                            proof=current_proof,
                        )
                        if current_payload[_CONTROL_JOB_EXECUTION_BINDING_KEY] != expected_binding:
                            raise ControlJobLeaseLostError(
                                "runtime diagnostic source changed after I/O"
                            )
                        return self._control_store.append_diagnostic_event(
                            event=prepared_event,
                            payload_ref=prepared.payload_ref,
                            payload_inline=(prepared_payload if prepared.inline_payload else None),
                            payload_sha256=prepared.payload_sha256,
                        )

                record = run_guarded_dependency_operation(
                    self._control_store, append_reconciled_event
                )
            else:
                record = self._diagnostic_event_log.append(
                    event,
                    payload=persisted_event_payload,
                    payload_policy=payload_policy,
                )
        except Exception as exc:  # pragma: no cover - diagnostics cannot mask dev jobs
            if execution_profile.strip().casefold() in SERIOUS_EXECUTION_PROFILES:
                raise RuntimeError(
                    f"runtime_diagnostic_event_persistence_failed:{job_id}:{phase}"
                ) from exc
            logger.debug(
                "Failed to persist runtime diagnostic event for job %s phase %s: %s",
                job_id,
                phase,
                exc,
            )
            return _DiagnosticEventEmission(
                event_id=None,
                status="not_persisted",
                scope_status=scope_record.status,
                limitation_code=(
                    scope_record.limitation_code or "runtime_diagnostic_event_persistence_failed"
                ),
            )
        if authority_withheld:
            status: Literal[
                "persisted",
                "candidate_diagnostic",
                "authority_withheld",
                "not_persisted",
            ] = "authority_withheld"
        elif not scope_established:
            status = "candidate_diagnostic"
        else:
            status = "persisted"
        return _DiagnosticEventEmission(
            event_id=str(record.event.event_id),
            status=status,
            scope_status=scope_record.status,
            limitation_code=scope_record.limitation_code,
        )

    @staticmethod
    def _control_job_bound_diagnostic_payload(
        *,
        persisted_payload: Mapping[str, Any],
        caller_payload: Mapping[str, Any],
        proof: _ControlJobExecutionLifecycleProof,
    ) -> dict[str, Any]:
        """Attach a strict binding recomputed from one persisted lifecycle proof."""
        if "attempt" in caller_payload and (
            proof.attempt is None
            or type(caller_payload["attempt"]) is not int
            or caller_payload["attempt"] != proof.attempt
        ):
            raise ControlJobLeaseLostError(
                "runtime diagnostic attempt does not match control worker proof"
            )
        source_state = proof.source_event.payload.get("state")
        if source_state not in {"pending", "running", "completed", "failed"}:
            raise ControlJobLeaseLostError(
                "runtime diagnostic source event has no recognized state"
            )
        source = proof.source_event
        binding = _ControlJobExecutionBinding(
            proof_phase=proof.proof_phase,
            control_job_id=proof.record.job_id,
            control_run_id=proof.record.run_id,
            source_event_job_state=source_state,
            control_worker_id=proof.worker_id,
            control_worker_attempt=proof.attempt,
            source_event_id=source.event_id,
            source_event_type=source.event_type,
            source_event_created_at=source.created_at,
            source_event_payload_sha256=source.payload_sha256,
            bound_job_record_refs=tuple(
                ref
                for ref in (
                    proof.record.payload_ref,
                    proof.record.capability_manifest_ref,
                )
                if ref is not None
            ),
        )
        return {
            **dict(persisted_payload),
            _CONTROL_JOB_EXECUTION_BINDING_KEY: binding.model_dump(mode="json"),
        }

    @staticmethod
    def _execution_scope_for_policy(
        policy: ResolvedExecutionPolicy,
    ) -> ControlJobExecutionScope:
        """Freeze complete authenticated identity from route policy at job admission."""
        actor = policy.actor
        if not isinstance(actor, Mapping):
            return ControlJobExecutionScope(
                status="not_established",
                tenant_id=None,
                cell_id=None,
                actor_subject=None,
                actor_authenticated=False,
                actor_roles=(),
            )
        subject = actor.get("subject")
        tenant_id = actor.get("tenant_id")
        cell_id = actor.get("cell_id")
        authenticated = actor.get("authenticated") is True
        roles_raw = actor.get("roles")
        sentinel_values = {
            "unknown",
            "tenant-unknown",
            "cell-unknown",
            "anonymous",
            "none",
            "null",
        }

        def established_text(value: object) -> bool:
            return (
                type(value) is str
                and bool(value)
                and value == value.strip()
                and value.casefold() not in sentinel_values
            )

        canonical_roles = (
            type(roles_raw) is list
            and all(type(role) is str and bool(role) and role == role.strip() for role in roles_raw)
            and roles_raw == sorted(set(roles_raw))
        )

        if (
            authenticated
            and established_text(subject)
            and established_text(tenant_id)
            and established_text(cell_id)
            and canonical_roles
        ):
            return ControlJobExecutionScope(
                status="established",
                tenant_id=tenant_id,
                cell_id=cell_id,
                actor_subject=subject,
                actor_authenticated=True,
                actor_roles=tuple(roles_raw),
            )
        return ControlJobExecutionScope(
            status="not_established",
            tenant_id=None,
            cell_id=None,
            actor_subject=None,
            actor_authenticated=False,
            actor_roles=(),
        )

    @staticmethod
    def _policy_with_execution_scope(
        policy: ResolvedExecutionPolicy,
        scope: ControlJobExecutionScope,
    ) -> ResolvedExecutionPolicy:
        """Bind submitted principal and persisted execution scope to one identity."""
        actor = dict(policy.actor)
        if scope.status == "established":
            actor.update(
                subject=scope.actor_subject,
                authenticated=True,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                roles=list(scope.actor_roles),
            )
        else:
            actor.update(
                subject="anonymous",
                authenticated=False,
                tenant_id=None,
                cell_id=None,
                roles=[],
            )
        return replace(policy, actor=actor)

    def _attach_job_actor_scope(
        self,
        payload: dict[str, Any],
        *,
        policy: ResolvedExecutionPolicy,
    ) -> dict[str, Any]:
        scoped_payload = dict(payload)
        scoped_payload.pop("tenant_id", None)
        scoped_payload.pop("cell_id", None)
        execution_scope = self._execution_scope_for_policy(policy)
        if execution_scope.status == "established":
            scoped_payload["tenant_id"] = execution_scope.tenant_id
            scoped_payload["cell_id"] = execution_scope.cell_id
        return scoped_payload

    @contextmanager
    def _control_job_span(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
    ) -> Iterator[None]:
        telemetry = payload.get("_telemetry") if isinstance(payload, dict) else None
        request_id = None
        token = None
        if isinstance(telemetry, dict):
            request_id = telemetry.get("request_id")
            carrier = telemetry.get("trace_context")
            extract_context = getattr(self._tracer, "extract_context", None)
            if isinstance(carrier, dict) and carrier and callable(extract_context):
                token = attach(
                    cast(
                        "Any",
                        extract_context({str(key): str(value) for key, value in carrier.items()}),
                    )
                )
        queue_lag_seconds = max(
            (datetime.now(UTC) - job.created_at).total_seconds(),
            0.0,
        )
        started = time.perf_counter()
        status = "success"
        with self._tracer.start_as_current_span(
            "runtime.control.job.execute",
            attributes={
                "runtime.control.job_id": job.job_id,
                "runtime.control.job_kind": job.kind,
                "runtime.control.run_id": job.run_id or "",
                "runtime.control.pipeline_id": job.pipeline_id or "",
                "runtime.control.request_id": str(request_id or ""),
            },
        ):
            try:
                yield
            except Exception:
                status = "error"
                raise
            finally:
                _record_control_plane_job_execution_metric(
                    metrics=self._metrics,
                    job_kind=job.kind,
                    status=status,
                    duration_seconds=time.perf_counter() - started,
                    queue_lag_seconds=queue_lag_seconds,
                )
                if token is not None:
                    detach(token)

    def _persist_capability_manifest(
        self,
        *,
        policy: ResolvedExecutionPolicy,
        job_id: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload_ref: str | None,
        observed_fallbacks: list[str] | None = None,
    ) -> str:
        payload = build_capability_manifest_payload(
            policy=policy,
            job_id=job_id,
            run_id=run_id,
            pipeline_id=pipeline_id,
            payload_ref=payload_ref,
            observed_fallbacks=observed_fallbacks,
        )
        return self._put_json_artifact(
            payload,
            kind="runtime.capability_manifest",
            schema_name="polisyos.runtime.CapabilityManifest",
        )

    def _enqueue_job(
        self,
        *,
        job_id: str,
        job_kind: str,
        run_id: str | None,
        pipeline_id: str | None,
        payload: dict[str, Any],
        policy: ResolvedExecutionPolicy,
        request_id: str | None = None,
        pre_admission_attempt_id: str | None = None,
        prepared_acquisition_action_head: _PreparedAcquisitionActionHeadPublication | None = None,
        native_step_up_expires_at: int | None = None,
    ) -> ControlJobRecord:
        started = time.perf_counter()
        execution_scope = self._execution_scope_for_policy(policy)
        policy = self._policy_with_execution_scope(policy, execution_scope)
        submitted_by = execution_scope.actor_subject or "anonymous"
        payload = self._attach_job_actor_scope(payload, policy=policy)
        payload = self._enrich_job_payload(payload, request_id=request_id)
        if prepared_acquisition_action_head is not None:
            publication = prepared_acquisition_action_head
            request_value = payload.get("request")
            if (
                type(publication) is not _PreparedAcquisitionActionHeadPublication
                or job_kind != "acquisition"
                or publication.job_id != job_id
                or publication.run_id != run_id
                or payload.get("action_kind") != publication.action_kind
                or payload.get("tenant_id") != publication.tenant_id
                or payload.get("cell_id") != publication.cell_id
                or payload.get("run_id") != publication.run_id
                or payload.get("route_id") != publication.route_id
                or payload.get("decision_ref") != publication.decision_ref
                or not isinstance(request_value, dict)
                or json.dumps(request_value, sort_keys=True, separators=(",", ":"))
                != publication.request_json
            ):
                raise ValueError("prepared_acquisition_action_payload_mismatch")
            if publication.action_kind == "runtime.evidence.candidate_experiment.reuse":
                from polisyos.runtime.quality.candidate_experiment_reuse import (
                    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
                    CandidateExperimentReuseActionSelection,
                )

                selected_payload = payload.get("reuse_selection")
                if type(selected_payload) is not dict:
                    raise ValueError("candidate_experiment_reuse_prepared_job_binding_mismatch")
                try:
                    selection = CandidateExperimentReuseActionSelection.model_validate(
                        selected_payload,
                        strict=True,
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "candidate_experiment_reuse_prepared_job_binding_mismatch"
                    ) from exc
                selection_json = selection.model_dump(mode="json")
                request_json = json.dumps(
                    selection.request.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if (
                    selected_payload != selection_json
                    or publication.action_kind != CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
                    or selection.action_job_id != job_id
                    or selection.action_job_id != publication.job_id
                    or selection.action_generation != publication.action_generation
                    or selection.tenant_id != publication.tenant_id
                    or selection.cell_id != publication.cell_id
                    or selection.run_id != publication.run_id
                    or selection.source_job_id != publication.source_job_id
                    or selection.route_id != publication.route_id
                    or payload.get("tenant_id") != publication.tenant_id
                    or payload.get("cell_id") != publication.cell_id
                    or payload.get("run_id") != publication.run_id
                    or payload.get("route_id") != publication.route_id
                    or payload.get("decision_ref") != publication.decision_ref
                    or type(request_value) is not dict
                    or request_value != selection.request.model_dump(mode="json")
                    or request_json != publication.request_json
                    or publication.expected_previous_terminal_ref
                    != str(selection.predecessor_terminal_ref.artifact_id)
                    or publication.expected_previous_terminal_manifest_profile_sha256
                    != selection.predecessor_terminal_ref.manifest_profile_sha256
                ):
                    raise ValueError("candidate_experiment_reuse_prepared_job_binding_mismatch")
        initially_refused = False
        if job_kind == "natural_language_run":
            payload[_EXECUTION_INTENT_BINDING_KEY] = _build_control_execution_intent_binding(
                payload,
                job_id=job_id,
                run_id=str(run_id or ""),
                actor=policy.actor,
            )
            initially_refused = (
                payload[_EXECUTION_INTENT_BINDING_KEY]["admission_status"] != "established"
            )
        try:
            selected_nl_payload_ref = None
            if job_kind == "natural_language_run" and (
                "temporal_scope" in payload
                or payload.get("joint_interaction_candidate_intent")
                == "authored_joint_components.v1"
            ):
                selected_nl_payload_ref = self._put_json_artifact_ref(
                    payload,
                    kind="runtime.control_job_payload.natural_language_run",
                    schema_name="polisyos.runtime.ControlJobPayload",
                    schema_version="1.1",
                )
                payload_ref = str(selected_nl_payload_ref.artifact_id)
            else:
                payload_ref = self._persist_job_payload(job_kind=job_kind, payload=payload)
            if prepared_acquisition_action_head is not None:
                prepared_acquisition_action_head = replace(
                    prepared_acquisition_action_head, payload_ref=payload_ref
                )
            capability_manifest_ref = self._persist_capability_manifest(
                policy=policy,
                job_id=job_id,
                run_id=run_id,
                pipeline_id=pipeline_id,
                payload_ref=payload_ref,
            )
            creation_event_payload = {
                **self._job_created_event_payload(
                    job_id=job_id,
                    job_kind=job_kind,
                    run_id=run_id,
                    pipeline_id=pipeline_id,
                    payload_ref=payload_ref,
                    submitted_by=submitted_by,
                    requested_execution_profile=policy.requested_profile,
                    effective_execution_profile=policy.effective_profile,
                    policy_flags=policy.policy_flags.model_dump(mode="json"),
                    capability_manifest_ref=capability_manifest_ref,
                    execution_scope=execution_scope,
                ),
                **(
                    {
                        _EXECUTION_INTENT_BINDING_KEY: payload[_EXECUTION_INTENT_BINDING_KEY],
                        "intent_digest": payload[_EXECUTION_INTENT_BINDING_KEY]["intent_digest"],
                    }
                    if job_kind == "natural_language_run"
                    else {}
                ),
                **(
                    {
                        "nl_request_payload_artifact_ref": selected_nl_payload_ref.model_dump(
                            mode="json"
                        )
                    }
                    if selected_nl_payload_ref is not None
                    else {}
                ),
                **(
                    {
                        _OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY: dict(
                            payload[_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY]
                        )
                    }
                    if job_kind == "workflow_run"
                    and isinstance(payload.get(_OBSERVATIONAL_METHOD_INTENT_PAYLOAD_KEY), Mapping)
                    else {}
                ),
            }
            creation_basis = self._control_store.prepare_job_creation(
                job_id=job_id,
                initial_state="failed" if initially_refused else "pending",
                creation_event_payload=creation_event_payload,
            )
            candidates = (
                self._build_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.cas_write.v1",
                    state_after="payload_persisted",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "artifact_ref": payload_ref,
                        "artifact_kind": f"runtime.control_job_payload.{job_kind}",
                        "projection_authority": "runtime_event_only",
                    },
                    artifact_refs=[payload_ref],
                    authority_bearing_payload=(
                        policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                    ),
                ),
                self._build_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.cas_write.v1",
                    state_after="capability_manifest_persisted",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "artifact_ref": capability_manifest_ref,
                        "artifact_kind": "runtime.capability_manifest",
                        "projection_authority": "runtime_event_only",
                    },
                    artifact_refs=[capability_manifest_ref],
                    input_refs=[payload_ref],
                    authority_bearing_payload=(
                        policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                    ),
                ),
                self._build_runtime_diagnostic_event(
                    job_id=job_id,
                    run_id=run_id,
                    execution_profile=policy.effective_profile,
                    phase="job_admission",
                    event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                    state_after="failed" if initially_refused else "pending",
                    payload=payload,
                    execution_scope=execution_scope,
                    event_payload={
                        "job_kind": job_kind,
                        "pipeline_id": pipeline_id,
                        "failure_code": (
                            "nl_job_execution_intent_not_established" if initially_refused else None
                        ),
                        "projection_authority": "progress_reference_only",
                    },
                ),
            )
            prepared_diagnostics: list[_PreparedDiagnosticEvent] = []
            preparation_failed = False
            for event, _scope_record, caller_payload, event_payload, _, established in candidates:
                if (
                    "attempt" in caller_payload
                    or _CONTROL_JOB_EXECUTION_BINDING_KEY in caller_payload
                ):
                    raise ControlJobLeaseLostError("runtime diagnostic reserved admission binding")
                # These are unpublished candidate bytes. Only create_job may
                # reconcile them with an actual row/event/outbox and emit them.
                binding = _ControlJobAdmissionDiagnosticBinding(
                    control_job_id=job_id,
                    control_run_id=run_id,
                    source_event_job_state="failed" if initially_refused else "pending",
                    source_event_payload_sha256=creation_basis.source_payload_sha256,
                    prepared_at=creation_basis.prepared_at,
                    bound_job_record_refs=tuple(
                        ref for ref in (payload_ref, capability_manifest_ref) if ref is not None
                    ),
                )
                bound_payload = {
                    **dict(event_payload),
                    _CONTROL_JOB_EXECUTION_BINDING_KEY: binding.model_dump(mode="json"),
                }
                try:
                    prepared_diagnostics.append(
                        self._diagnostic_event_log.prepare(
                            event,
                            payload=bound_payload,
                            payload_policy=DiagnosticEventPayloadPolicy(
                                authority_bearing=(
                                    policy.effective_profile in _SERIOUS_EXECUTION_PROFILES
                                    and established
                                )
                            ),
                        )
                    )
                except Exception as exc:
                    if policy.effective_profile in _SERIOUS_EXECUTION_PROFILES:
                        raise RuntimeError(
                            f"runtime_diagnostic_event_persistence_failed:{job_id}:job_admission"
                        ) from exc
                    # Preserve the existing dev best-effort rule. No omitted
                    # event ID is advertised; the limitation is initial progress.
                    preparation_failed = True
                    logger.debug("Admission diagnostic preparation failed for %s: %s", job_id, exc)
            try:
                record = self._control_store.create_job(
                    job_id=job_id,
                    kind=_coerce_control_job_kind(job_kind),
                    run_id=run_id,
                    pipeline_id=pipeline_id,
                    requested_execution_profile=policy.requested_profile,
                    effective_execution_profile=policy.effective_profile,
                    policy_flags=policy.policy_flags.model_dump(mode="json"),
                    capability_manifest_ref=capability_manifest_ref,
                    payload_ref=payload_ref,
                    submitted_by=submitted_by,
                    creation_event_payload=creation_event_payload,
                    initial_state="failed" if initially_refused else "pending",
                    initial_error_message=(
                        "nl_job_execution_intent_not_established" if initially_refused else None
                    ),
                    initial_progress={
                        "state": "failed" if initially_refused else "pending",
                        "phase": "job_admission",
                        **(
                            {
                                "status": "not_established",
                                "failure_code": "nl_job_execution_intent_not_established",
                                "execution_intent_binding": payload[_EXECUTION_INTENT_BINDING_KEY],
                            }
                            if initially_refused
                            else {}
                        ),
                    },
                    creation_basis=creation_basis,
                    prepared_admission_diagnostics=tuple(prepared_diagnostics),
                    diagnostic_preparation_failed=preparation_failed,
                    pre_admission_attempt_id=pre_admission_attempt_id,
                    pre_admission_outcome=(
                        ("refused" if initially_refused else "admitted")
                        if pre_admission_attempt_id is not None
                        else None
                    ),
                    prepared_acquisition_action_head=prepared_acquisition_action_head,
                    native_step_up_expires_at=native_step_up_expires_at,
                )
            except Exception:
                if prepared_acquisition_action_head is None:
                    raise
                recovered = self._control_store.get_job(job_id)
                if (
                    recovered is None
                    or recovered.kind != "acquisition"
                    or recovered.run_id != run_id
                    or recovered.payload_ref != payload_ref
                    or recovered.state not in {"pending", "running", "completed"}
                ):
                    raise
                try:
                    self._control_store._reconcile_control_job_creation_envelope(recovered)
                    sink = getattr(self, "acquisition_route_sink", None)
                    if sink is None:
                        raise RuntimeError("candidate_experiment_publication_owner_missing")
                    sink.verify_prepared_experiment_requested_phase(
                        replace(prepared_acquisition_action_head, payload_ref=payload_ref),
                        allow_terminal=recovered.state == "completed",
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    raise
                record = recovered
            if self._worker is not None:
                self._worker.wake()
        except Exception:
            _record_control_plane_job_admission_metric(
                metrics=self._metrics,
                job_kind=job_kind,
                effective_profile=policy.effective_profile,
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise
        _record_control_plane_job_admission_metric(
            metrics=self._metrics,
            job_kind=job_kind,
            effective_profile=policy.effective_profile,
            status="success",
            duration_seconds=time.perf_counter() - started,
        )
        return record

    def _emit_control_job_start_event(
        self,
        *,
        job: ControlJobRecord,
        payload: Mapping[str, Any],
        execution_scope: ControlJobExecutionScope,
        execution_intent_binding: Mapping[str, Any] | None,
    ) -> None:
        """Emit the accepted job-start diagnostic with its admitted intent view."""
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            state_before=job.state,
            state_after="running",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "attempt": job.attempt,
                "projection_authority": "runtime_event_only",
                **(
                    {
                        "execution_intent_band": execution_intent_binding["intent_band"],
                        "execution_intent_limitation_code": (
                            "data_trust_owner_not_established"
                            if execution_intent_binding["intent_band"]
                            == ExecutionIntentBand.DATA_TRUST_REQUIRED.value
                            else None
                        ),
                    }
                    if execution_intent_binding is not None
                    else {}
                ),
            },
        )

    def _complete_acquisition_control_job(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
        capability_manifest_ref: str,
    ) -> None:
        """Run the configured acquisition handler and publish its terminal event."""
        from polisyos.runtime.quality.agent_action_authority import MODEL_INPUT_USE_ACTION_KIND

        from ..control_plane_store import _json_values_equal_strict
        from ..model_input_successor_action import (
            ModelInputUseActionCheckpoint,
            NativeModelInputUseJobCompletion,
            model_input_use_terminal_progress,
        )

        handler = self._acquisition_job_handler
        if handler is None:
            raise RuntimeError("acquisition_job_handler_missing")

        def require_canonical_handler() -> None:
            from ..acquisition_action_service import AcquisitionActionService

            owner = getattr(handler, "__self__", None)
            if (
                type(handler) is not MethodType
                or handler.__func__ is not AcquisitionActionService.handle_job
                or type(owner) is not AcquisitionActionService
                or owner.control_service is not self
            ):
                raise ValueError("model_input_use_completion_owner_not_established")

        request = payload.get("request")
        native = (
            payload.get("action_kind") == MODEL_INPUT_USE_ACTION_KIND
            and isinstance(request, Mapping)
            and "native_use" in request
        )
        if native:
            require_canonical_handler()
        result = handler(job, payload, execution_scope)
        if not isinstance(result, dict):
            raise TypeError("acquisition_job_completion_progress_untyped")
        if isinstance(result, _ModelInputUseJobCompletion) and type(result) is not (
            _ModelInputUseJobCompletion
        ):
            raise TypeError("model_input_use_completion_inputs_untyped")
        progress = dict(result)
        if {
            "generic_model_input_current_use",
            "generic_model_input_frontier_cas",
        } & progress.keys():
            raise ValueError("model_input_use_completion_projection_not_owner_produced")
        completion_options: dict[str, Any] = {}
        if native or isinstance(result, NativeModelInputUseJobCompletion):
            if not native or type(result) is not NativeModelInputUseJobCompletion:
                raise ValueError("native_model_input_use_completion_owner_not_established")
            if type(result.checkpoint) is not ModelInputUseActionCheckpoint or not callable(
                result.currentness_resolver
            ):
                raise TypeError("native_model_input_use_completion_inputs_untyped")
            admission = self._control_store.current_execution_job_admission()
            stage = ModelInputUseActionCheckpoint(
                phase_ref=result.checkpoint.phase_ref,
                semantic_successor_ref=result.checkpoint.semantic_successor_ref,
            )
            if (
                not admission.same_execution_identity(result.admission)
                or not admission.matches_job_record(job)
                or admission.scope != execution_scope
                or admission.scope.status != "established"
                or admission.scope.actor_authenticated is not True
                or not admission.scope.actor_subject
                or admission.job.capability_manifest_ref != capability_manifest_ref
                or result.checkpoint.schema_version is not None
                or result.checkpoint.execution_ref is None
                or result.checkpoint.result_ref is None
                or not _json_values_equal_strict(
                    admission.job.progress.get("model_input_use"),
                    stage.model_dump(mode="json", exclude_none=True),
                )
                or any(
                    not _json_values_equal_strict(progress.get(key), value)
                    for key, value in model_input_use_terminal_progress(result.checkpoint).items()
                )
            ):
                raise ValueError("native_model_input_use_completion_checkpoint_mismatch")
            if result.currentness_resolver() is not True:
                raise ValueError("native_model_input_use_completion_authority_not_current")
            completion_options = {
                "expected_lease_owner": job.lease_owner,
                "expected_attempt": job.attempt,
            }
        elif type(result) is _ModelInputUseJobCompletion:
            from ..model_input_successor_action import prepare_model_input_use_frontier_completion

            require_canonical_handler()
            expected_progress = model_input_use_terminal_progress(result.checkpoint)
            if any(progress.get(key) != value for key, value in expected_progress.items()):
                raise ValueError("model_input_use_completion_checkpoint_progress_mismatch")
            frontier_cas = prepare_model_input_use_frontier_completion(
                self,
                selection=result.selection,
                checkpoint=result.checkpoint,
                action_payload_ref=result.action_payload_ref,
                authority_decision_ref=result.authority_decision_ref,
            )
            if type(frontier_cas) is not GenericModelInputEvaluationFrontierCAS:
                raise TypeError("model_input_use_completion_frontier_untyped")
            if result.currentness_resolver() is not True:
                raise ValueError("model_input_use_completion_authority_not_current")
            completion_options = {
                "generic_model_input_frontier_cas": frontier_cas,
                "expected_lease_owner": job.lease_owner,
                "expected_attempt": job.attempt,
            }
        else:
            checkpoint = progress.get("model_input_use")
            if isinstance(checkpoint, dict) and checkpoint.get("schema_version") == (
                "polisyos.runtime.ModelInputUseActionCheckpoint@2.0"
            ):
                raise ValueError("model_input_use_completion_owner_not_established")
        self._control_store.complete_job(
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            capability_manifest_ref=capability_manifest_ref,
            progress=progress,
            **completion_options,
        )
        artifact_refs = [capability_manifest_ref]
        terminal_receipt_ref = progress.get("terminal_receipt_ref")
        if isinstance(terminal_receipt_ref, str):
            artifact_refs.append(terminal_receipt_ref)
        self._emit_runtime_diagnostic_event(
            execution_scope=execution_scope,
            job_id=job.job_id,
            run_id=str(job.run_id or ""),
            execution_profile=job.effective_execution_profile,
            phase="job_execution",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "receipt_phase": progress.get("receipt_phase"),
            },
            artifact_refs=artifact_refs,
        )
        return
