"""Native row movement from supplier custody through separate GY admission.

This family owns no acquisition execution or institutional signing. It replays
the supplier chain, qualifies an exact one-movement prefix through the shared
chronology owner, and projects only a freshly requalified persisted result.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves the source clock.
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon, contracts, security
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.chronology_qualification import QualificationConsumer
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.epoch_deployment import EpochDeployment, build_epoch_deployment
from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange
from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

contract = contracts.chronology
_FAMILY = "acquisition_movement"
_PURPOSE = "per_row_acquisition_movement"
_PROFILE = "policyos.runtime.acquisition_movement.v1"
_OWNER = "polisyos.runtime.quality.acquisition_movement"
_READ_ERRORS = (KeyError, OSError, RuntimeError, TypeError, ValueError)
_DIGEST = r"^sha256:[0-9a-f]{64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcquisitionMovementArtifact(_Strict):
    """Supplier-derived facts, still a candidate until distinct GY admission."""

    schema_version: Literal["policyos.runtime.acquisition_movement.v1"] = _PROFILE
    row_id: str = Field(min_length=1)
    gap_id: Literal["GY-GAP6"] = "GY-GAP6"
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    generation_cycle_run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=_DIGEST)
    supplier_receipt_ref: str = Field(pattern=_DIGEST)
    supplier_terminal_event_id: str = Field(min_length=1)
    source_terminal_event_id: str = Field(min_length=1)
    phase_receipt_refs: tuple[str, ...]
    compiled_ref: str = Field(pattern=_DIGEST)
    route_id: str = Field(pattern=_DIGEST)
    action_generation: int = Field(ge=1)
    reentry_receipt_ref: str = Field(pattern=_DIGEST)
    deeper_terminal_event_id: str = Field(min_length=1)
    source_cycle_index: int = Field(ge=0)
    new_cycle_index: int = Field(ge=1)
    terminal_kind: str = Field(min_length=1)
    overlay_receipt_ref: str = Field(pattern=_DIGEST)
    semantic_epoch_ref: str = Field(pattern=_DIGEST)
    semantic_epoch_production_receipt_ref: str = Field(pattern=_DIGEST)
    epoch_id: int = Field(gt=0)
    admitted_observation_count: int = Field(gt=0)
    supplier_generated_at: datetime
    synthetic: bool | None


class MovementOwnerAdmission(_Strict):
    """GY relation whose exact bytes a separate signed policy admission binds."""

    schema_version: Literal["policyos.runtime.movement_owner_admission.v1"] = (
        "policyos.runtime.movement_owner_admission.v1"
    )
    query: contract.NativeChronologyQuery
    policy_ref: artifacts.ArtifactRef
    movement_artifact_ref: artifacts.ArtifactRef
    supplier_receipt_ref: str = Field(pattern=_DIGEST)
    native_head_role: Literal["gy_movement_admission"] = "gy_movement_admission"


class MovementRecord(_Strict):
    """One admitted movement with separate supplier, GY head, and proof refs."""

    movement_artifact_ref: str = Field(pattern=_DIGEST)
    movement: AcquisitionMovementArtifact
    gy_admission_ref: str = Field(pattern=_DIGEST)
    qualification_ref: str = Field(pattern=_DIGEST)
    chronology_bundle_ref: str = Field(pattern=_DIGEST)
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class _MovementIntake(_Strict):
    schema_version: Literal["policyos.runtime.movement_intake.v1"] = (
        "policyos.runtime.movement_intake.v1"
    )
    status: Literal["admitted", "refused"]
    reason: str | None
    supplier_receipt_ref: str
    candidate_ref: str | None = None
    query: contract.NativeChronologyQuery | None = None
    movement_record: MovementRecord | None = None


class MovementIntakeResult(_MovementIntake):
    """Read-back intake receipt; its CAS address is outside its own payload."""

    receipt_ref: str = Field(pattern=_DIGEST)


class MovementRowProjection(_Strict):
    """Exact row projection, explicitly bounded by the diagnostic read window."""

    status: Literal["available", "not_established", "invalid_source"]
    reason: str | None
    policy_status: Literal["configured", "policy_admission_missing"]
    records: tuple[MovementRecord, ...] = ()
    intake_receipt_refs: tuple[str, ...] = ()
    source_content_hash: str = Field(pattern=_DIGEST)
    scope: Literal["exact_row_observed_supplier_movements"] = (
        "exact_row_observed_supplier_movements"
    )
    exhaustive: Literal[False] = False


def _hash(value: object) -> str:
    return security.raw_content_hash(
        canon.to_canonical_bytes(value, canon.CanonSpec(forbid_floats=False))
    )


def _model_bytes(value: BaseModel) -> bytes:
    return canon.to_canonical_bytes(
        value.model_dump(mode="json"), canon.CanonSpec(forbid_floats=False)
    )


def _scope(movement: AcquisitionMovementArtifact) -> dict[str, object]:
    return {
        key: getattr(movement, key)
        for key in (
            "row_id",
            "gap_id",
            "tenant_id",
            "cell_id",
            "generation_cycle_run_id",
            "design_problem_ref",
        )
    }


class _MovementAdapter:
    def __init__(self, candidate: contract.NativeChronologyCandidate) -> None:
        self.candidate = candidate

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        if request != self.candidate.query:
            raise ValueError("movement_query_mismatch")
        return self.candidate


class AcquisitionMovementService:
    """Produce, persist, admit and revalidate one native acquisition movement."""

    def __init__(
        self,
        *,
        control_store: ControlPlaneStore,
        artifact_store: artifacts.ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        epoch_deployment: EpochDeployment | None = None,
    ) -> None:
        self._control_store = control_store
        self._store = artifact_store
        self._events = event_log
        self._evidence_owner = epoch_deployment or build_epoch_deployment(None)
        self._deployment = build_epoch_deployment(
            self._evidence_owner._state().config,
            native_policy_verifier=_MovementNativePolicyVerifier(self),
            _runtime_store_affiliates=(self._evidence_owner,),
        )

    def _put(
        self, value: BaseModel | dict[str, object], kind: str, *, owner_input: bool = False
    ) -> artifacts.ArtifactRef:
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        ref = self._store.put_json(
            payload,
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        if canon.from_canonical_bytes(self._store.get_bytes(str(ref.artifact_id))) != payload:
            raise ValueError("movement_persistence_readback_failed")
        if owner_input and self._evidence_owner._state().store is not None:
            with self._evidence_owner.composition_scope(runtime_artifact_store=self._store):
                owner_bytes = self._evidence_owner._runtime_repository().read_raw(artifact_ref=ref)
            if owner_bytes != self._read(str(ref.artifact_id)):
                raise ValueError("movement_owner_input_transfer_mismatch")
        return ref

    def _read(self, ref: str, kind: str | None = None) -> bytes:
        raw = self._store.get_bytes(ref)
        if security.raw_content_hash(raw) != ref:
            raise ValueError("movement_source_hash_mismatch")
        if kind is not None and self._store.get_manifest(ref).kind != kind:
            raise ValueError("movement_source_kind_mismatch")
        return raw

    def _supplier(self, ref: str) -> AcquisitionRouteLoopReceipt:
        receipt = AcquisitionRouteLoopReceipt.model_validate(
            canon.from_canonical_bytes(
                self._read(ref, "runtime_quality.acquisition_route_loop_receipt")
            )
        )
        reconcile_authority_ref(
            artifact_store=self._store,
            event_log=self._events,
            cas_ref=ref,
            expected_tenant_id=receipt.tenant_id,
            expected_cell_id=receipt.cell_id,
            expected_run_id=receipt.run_id,
            expected_job_id=receipt.job_id,
        )
        return receipt

    def _derive_movement(self, ref: str) -> AcquisitionMovementArtifact:
        supplier = self._supplier(ref)
        if supplier.terminal_outcome != "reentry_completed" or supplier.reentry_receipt_ref is None:
            raise ValueError("supplier_no_reentry")
        head = self._control_store.get_acquisition_action_head(
            **{
                name: getattr(supplier, name)
                for name in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "route_id",
                    "action_generation",
                )
            }
        )
        if head is None or head.receipt_ref != ref or head.receipt_phase != "terminal":
            raise ValueError("supplier_terminal_head_not_current")
        identity_names = (
            "tenant_id",
            "cell_id",
            "run_id",
            "source_job_id",
            "route_id",
            "action_generation",
            "job_id",
            "compiled_ref",
            "planner_report_hash",
            "cost_basis_hash",
            "decision_ref",
        )
        phase_refs = []
        predecessor = supplier.predecessor_receipt_ref
        previous_time = supplier.generated_at
        for phase_name in ("world_committed_reentry_pending", "executing", "requested"):
            phase = AcquisitionRoutePhaseReceipt.model_validate(
                canon.from_canonical_bytes(
                    self._read(predecessor, "runtime_quality.acquisition_route_phase_receipt")
                )
            )
            reconcile_authority_ref(
                artifact_store=self._store,
                event_log=self._events,
                cas_ref=predecessor,
                expected_tenant_id=supplier.tenant_id,
                expected_cell_id=supplier.cell_id,
                expected_run_id=supplier.run_id,
                expected_job_id=supplier.job_id,
            )
            if (
                phase.receipt_phase != phase_name
                or phase.generated_at > previous_time
                or any(getattr(phase, name) != getattr(supplier, name) for name in identity_names)
                or (
                    phase_name == "world_committed_reentry_pending"
                    and phase.owner_receipt_refs != supplier.owner_receipt_refs
                )
            ):
                raise ValueError("supplier_phase_chain_mismatch")
            phase_refs.append(predecessor)
            predecessor = phase.predecessor_receipt_ref
            previous_time = phase.generated_at
        if predecessor is not None:
            raise ValueError("supplier_phase_chain_incomplete")
        closure = AcquisitionRouteLoop(
            control_store=self._control_store,
            artifact_store=self._store,
            event_log=self._events,
            tenant_id=supplier.tenant_id,
            cell_id=supplier.cell_id,
        ).resolve_current_route(run_id=supplier.run_id)
        if (
            supplier.route_id != closure.route_id
            or supplier.source_job_id != closure.source_job_id
            or supplier.compiled_ref != closure.compiled_ref
            or supplier.cost_basis_hash != closure.cost_basis_hash
            or supplier.planner_report_hash != _hash(closure.planner_report.model_dump(mode="json"))
        ):
            raise ValueError("supplier_source_closure_mismatch")
        reentry = AcquisitionOverlayReentryReceipt.model_validate(
            canon.from_canonical_bytes(
                self._read(
                    supplier.reentry_receipt_ref,
                    "runtime_quality.acquisition_overlay_reentry_receipt",
                )
            )
        )
        if (
            reentry.source_run_id != closure.generation_run.run_id
            or reentry.design_problem_ref != closure.design_problem_ref
            or reentry.source_cycle_index != closure.source_cycle.cycle_index
            or reentry.source_candidate_ref != closure.source_cycle.selected_candidate_ref
            or reentry.new_cycle.cycle_index != reentry.source_cycle_index + 1
            or reentry.new_cycle.design_problem_ref != closure.design_problem_ref
            or reentry.new_cycle.terminal_kind is None
        ):
            raise ValueError("supplier_reentry_binding_mismatch")
        growth_refs = tuple(
            ref
            for ref in supplier.owner_receipt_refs
            if self._store.get_manifest(ref).kind
            == "runtime_quality.acquisition_world_growth_receipt"
        )
        if len(growth_refs) != 1:
            raise ValueError("movement_growth_receipt_missing_or_ambiguous")
        growth = AcquisitionWorldGrowthReceipt.model_validate(
            canon.from_canonical_bytes(
                self._read(growth_refs[0], "runtime_quality.acquisition_world_growth_receipt")
            )
        )
        if (
            growth.selection.key
            != (supplier.tenant_id, supplier.cell_id, supplier.run_id, supplier.route_id)
            or growth.selection.design_problem_ref != closure.design_problem_ref
            or str(growth.activation.overlay_admission_receipt_ref.artifact_id)
            != reentry.overlay_receipt_ref
            or str(growth.activation.semantic_epoch_production_receipt_ref.artifact_id)
            != reentry.semantic_epoch_production_receipt_ref
            or growth.passport_id != reentry.passport_id
            or growth.previously_active_observations + growth.admitted_observation_delta
            != reentry.admitted_observation_count
        ):
            raise ValueError("movement_growth_reentry_mismatch")
        for owner_ref in (growth_refs[0], supplier.reentry_receipt_ref):
            owner_report = reconcile_authority_ref(
                artifact_store=self._store,
                event_log=self._events,
                cas_ref=owner_ref,
                expected_tenant_id=supplier.tenant_id,
                expected_cell_id=supplier.cell_id,
                expected_run_id=supplier.run_id,
                expected_job_id=closure.source_job_id,
            )
            manifest = self._store.get_manifest(owner_ref)
            if (
                manifest.producer is None
                or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
            ):
                raise ValueError("movement_growth_producer_mismatch")
        terminal_rows = self._events.list_events(event_id=owner_report.durable_event_id, limit=2)
        if len(terminal_rows) != 1:
            raise ValueError("deeper_terminal_event_missing_or_ambiguous")
        terminal = terminal_rows[0]
        if (
            terminal.event.event_type != "polisyos.runtime.diagnostic.producer_execution.v1"
            or terminal.event.phase != "reentry_terminal"
            or terminal.event.state_after != "reentry_terminal"
            or terminal.event.event_source != "polisyos.runtime.acquisition_world_growth"
            or terminal.event.producer_component != "polisyos.runtime.acquisition_world_growth"
            or supplier.reentry_receipt_ref not in terminal.event.artifact_refs
            or terminal.event.event_id in {head.durable_event_id, closure.terminal_event_id}
            or terminal.event.tenant_id != supplier.tenant_id
            or terminal.event.cell_id != supplier.cell_id
            or terminal.event.event_time > supplier.generated_at
        ):
            raise ValueError("deeper_terminal_event_binding_mismatch")
        return AcquisitionMovementArtifact(
            row_id=closure.design_problem.design_problem_id,
            tenant_id=supplier.tenant_id,
            cell_id=supplier.cell_id,
            run_id=supplier.run_id,
            generation_cycle_run_id=closure.generation_run.run_id,
            job_id=supplier.job_id,
            design_problem_ref=closure.design_problem_ref,
            supplier_receipt_ref=ref,
            supplier_terminal_event_id=head.durable_event_id,
            source_terminal_event_id=closure.terminal_event_id,
            phase_receipt_refs=tuple(reversed(phase_refs)),
            compiled_ref=closure.compiled_ref,
            route_id=supplier.route_id,
            action_generation=supplier.action_generation,
            reentry_receipt_ref=supplier.reentry_receipt_ref,
            deeper_terminal_event_id=terminal.event.event_id,
            source_cycle_index=reentry.source_cycle_index,
            new_cycle_index=reentry.new_cycle.cycle_index,
            terminal_kind=reentry.new_cycle.terminal_kind,
            overlay_receipt_ref=reentry.overlay_receipt_ref,
            semantic_epoch_ref=reentry.semantic_epoch_ref,
            semantic_epoch_production_receipt_ref=reentry.semantic_epoch_production_receipt_ref,
            epoch_id=reentry.epoch_id,
            admitted_observation_count=reentry.admitted_observation_count,
            supplier_generated_at=supplier.generated_at,
            synthetic=reentry.synthetic,
        )

    def _candidate(
        self, movement: AcquisitionMovementArtifact
    ) -> contract.NativeChronologyCandidate:
        member_ref = self._put(movement, "runtime_quality.acquisition_movement", owner_input=True)
        context = {"scope": _scope(movement), "supplier_receipt_ref": movement.supplier_receipt_ref}
        context_ref = self._put(context, "runtime_quality.movement_query_context", owner_input=True)
        context_hash = _hash({"movement_query_context_v1": context})
        query = contract.NativeChronologyQuery(
            domain=contract.ChronologyProofDomain(
                format=contract.FULL_PREFIX_FORMAT,
                profile=contract.FULL_PREFIX_PROFILE,
                proof_domain=_FAMILY,
                family=_FAMILY,
                scope_ref=_hash(_scope(movement)),
                authority_purpose=_PURPOSE,
            ),
            requested_cutoff_ref=movement.supplier_receipt_ref,
            requested_query_context_ref=context_hash,
        )
        denominator = {"scope": _scope(movement), "member_refs": [str(member_ref.artifact_id)]}
        denominator_ref = self._put(
            denominator, "runtime_quality.movement_denominator", owner_input=True
        )
        denominator_hash = _hash({"movement_denominator_v1": denominator})
        selection_key = contract.PredicatePolicySelectionKey(
            **query.domain.model_dump(exclude={"format", "profile"}),
            requested_cutoff_ref=query.requested_cutoff_ref,
        )
        try:
            heads = EpochEvidenceExchange(self._evidence_owner).enumerate_admission_refs(
                key=selection_key
            )
        except _READ_ERRORS:
            heads = ()
        native_head_refs = tuple(str(ref.artifact_id) for ref in heads) if len(heads) == 1 else ()
        member = contract.ChronologyMemberInput(
            member_ref=str(member_ref.artifact_id),
            native_artifact_ref=member_ref,
            native_content_hash=contract._native_content_hash(_model_bytes(movement)),
            native_schema_profile=_PROFILE,
            native_bytes=_model_bytes(movement),
            member_admission_basis_ref=movement.supplier_receipt_ref,
            member_admission_context_ref=context_hash,
        )
        return contract.NativeChronologyCandidate(
            query=query,
            declared_denominator_ref=denominator_hash,
            native_denominator_artifact_ref=denominator_ref,
            native_denominator_content_hash=denominator_hash,
            query_context_artifact_ref=context_ref,
            query_context_content_hash=context_hash,
            ordered_members=(member,),
            member_predicates=(
                contract.MemberPredicateDisposition(
                    member_ref=member.member_ref,
                    disposition=contract.PredicateDisposition(
                        predicate_id="supplier_reentry_binding",
                        predicate_class="recomputed",
                        status="satisfied",
                        evidence_ref=member_ref,
                        failure_code=None,
                    ),
                ),
            ),
            query_predicates=(
                contract.QueryPredicateDisposition(
                    requested_query_context_ref=context_hash,
                    disposition=contract.PredicateDisposition(
                        predicate_id="exact_row_scope",
                        predicate_class="recomputed",
                        status="satisfied",
                        evidence_ref=context_ref,
                        failure_code=None,
                    ),
                ),
            ),
            exterior_limitation_code=None,
            native_authority_head_refs=native_head_refs,
        )

    def _evaluate(
        self, supplier_receipt_ref: str
    ) -> tuple[_MovementIntake, AcquisitionMovementArtifact | None]:
        try:
            movement = self._derive_movement(supplier_receipt_ref)
            candidate = self._candidate(movement)
        except _READ_ERRORS as exc:
            return _MovementIntake(
                status="refused", reason=str(exc), supplier_receipt_ref=supplier_receipt_ref
            ), None
        candidate_ref = self._put(candidate, "runtime_quality.movement_candidate")
        result = QualificationConsumer.from_deployment(
            self._deployment, runtime_artifact_store=self._store
        ).qualify(
            request=candidate.query,
            adapter=_MovementAdapter(candidate),
        )
        record = None
        if isinstance(result, contract.NativeChronologyQualified):
            qualification_ref = self._put(result, "runtime_quality.movement_qualification")
            record = MovementRecord(
                movement_artifact_ref=candidate.ordered_members[0].member_ref,
                movement=movement,
                gy_admission_ref=candidate.native_authority_head_refs[0],
                qualification_ref=str(qualification_ref.artifact_id),
                chronology_bundle_ref=str(result.persisted_proof.artifact_ref.artifact_id),
            )
        failure = getattr(result, "failure", result)
        return _MovementIntake(
            status="admitted" if record else "refused",
            reason=None if record else getattr(failure, "code", result.result_kind),
            supplier_receipt_ref=supplier_receipt_ref,
            candidate_ref=str(candidate_ref.artifact_id),
            query=candidate.query,
            movement_record=record,
        ), movement

    def consume_terminal(self, *, supplier_receipt_ref: str) -> MovementIntakeResult:
        """Persist a separate GY admission/refusal without changing supplier closure."""
        intake, movement = self._evaluate(supplier_receipt_ref)
        ref = self._put(intake, "runtime_quality.movement_intake")
        try:
            supplier = self._supplier(supplier_receipt_ref)
        except _READ_ERRORS:
            supplier = None
        if supplier is not None:
            receipt_ref = str(ref.artifact_id)
            event_id = "movement-" + receipt_ref.removeprefix("sha256:")
            if not self._events.list_events(event_id=event_id, limit=2):
                self._events.append(
                    DiagnosticEvent(
                        event_id=event_id,
                        event_source="polisyos.runtime",
                        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
                        event_time=supplier.generated_at,
                        event_subject=receipt_ref,
                        schema_name="polisyos.runtime.quality.diagnostic_event",
                        schema_version="1.0",
                        trace_id=f"trace-{supplier.job_id}",
                        span_id=event_id,
                        parent_span_id=None,
                        run_id=movement.generation_cycle_run_id if movement else supplier.run_id,
                        job_id=supplier.job_id,
                        tenant_id=supplier.tenant_id,
                        cell_id=supplier.cell_id,
                        producer_component=_OWNER,
                        producer_version=_PROFILE,
                        execution_profile="governed",
                        phase="movement_admission",
                        state_before=None,
                        state_after=intake.status,
                        payload_ref=None,
                        artifact_refs=(receipt_ref,),
                        input_refs=(supplier_receipt_ref,),
                        blocking_status="non_blocking"
                        if intake.status == "admitted"
                        else "blocking",
                        redaction_policy_ref=None,
                        duplicate_of=None,
                        dedupe_key=event_id,
                    )
                )
        return MovementIntakeResult(**intake.model_dump(), receipt_ref=str(ref.artifact_id))

    def project_row(
        self, *, row_id: str, run_id: str, design_problem_ref: str
    ) -> MovementRowProjection:
        """Reload and requalify observed intake receipts for exactly this board row."""
        policy_status = (
            "configured"
            if self._evidence_owner._state().config.predicate_policy_admission_refs
            else "policy_admission_missing"
        )
        rows = self._events.list_events(run_id=run_id, limit=1000)
        refs: list[str] = []
        records: dict[str, MovementRecord] = {}
        reason = "movement_supplier_missing"
        invalid = len(rows) >= 1000
        if invalid:
            reason = "movement_event_window_incomplete"
        for row in rows if not invalid else ():
            if row.event.producer_component != _OWNER or row.event.phase != "movement_admission":
                continue
            try:
                if len(row.event.artifact_refs) != 1:
                    raise ValueError("movement_intake_event_binding_mismatch")
                ref = row.event.artifact_refs[0]
                intake = _MovementIntake.model_validate(
                    canon.from_canonical_bytes(self._read(ref, "runtime_quality.movement_intake"))
                )
                if row.event.input_refs != (intake.supplier_receipt_ref,):
                    raise ValueError("movement_intake_event_binding_mismatch")
                if intake.movement_record is not None:
                    saved = intake.movement_record
                    qualification = contract.NativeChronologyQualified.model_validate(
                        canon.from_canonical_bytes(
                            self._read(
                                saved.qualification_ref, "runtime_quality.movement_qualification"
                            )
                        )
                    )
                    if (
                        str(qualification.persisted_proof.artifact_ref.artifact_id)
                        != saved.chronology_bundle_ref
                        or str(
                            qualification.reconciliation.owner_context.policy_admission_ref.artifact_id
                        )
                        != saved.gy_admission_ref
                    ):
                        raise ValueError("movement_qualification_binding_mismatch")
                    # Read prior custody before qualification can reconstruct derived artifacts.
                    for proof_ref in (
                        qualification.persisted_proof.artifact_ref,
                        qualification.persisted_proof.verifier_result_ref,
                        qualification.projection_receipt.artifact_ref,
                    ):
                        with self._evidence_owner.composition_scope(
                            runtime_artifact_store=self._store
                        ):
                            proof_bytes = self._evidence_owner._runtime_repository().read_raw(
                                artifact_ref=proof_ref
                            )
                        if security.raw_content_hash(proof_bytes) != str(proof_ref.artifact_id):
                            raise ValueError("movement_qualification_custody_missing")
                current, movement = self._evaluate(intake.supplier_receipt_ref)
                if movement is None:
                    raise ValueError(current.reason)
                if (
                    movement.row_id,
                    movement.generation_cycle_run_id,
                    movement.design_problem_ref,
                ) != (row_id, run_id, design_problem_ref):
                    continue
                if (row.event.tenant_id, row.event.cell_id) != (
                    movement.tenant_id,
                    movement.cell_id,
                ):
                    raise ValueError("movement_row_scope_mismatch")
                refs.append(ref)
                if current.movement_record is not None and current == intake:
                    saved = current.movement_record
                    records[intake.supplier_receipt_ref] = saved
                elif current.status == "refused":
                    reason = current.reason
                else:
                    reason = "movement_readmission_required"
            except _READ_ERRORS as exc:
                invalid = True
                reason = str(exc)
        result_records = tuple(records.values()) if not invalid else ()
        material = {
            "row_id": row_id,
            "run_id": run_id,
            "design_problem_ref": design_problem_ref,
            "records": [r.model_dump(mode="json") for r in result_records],
            "refs": refs,
            "reason": None if result_records else reason,
            "policy_status": policy_status,
        }
        return MovementRowProjection(
            status="invalid_source"
            if invalid
            else "available"
            if result_records
            else "not_established",
            reason=None if result_records else reason,
            policy_status=policy_status,
            records=result_records,
            intake_receipt_refs=tuple(refs),
            source_content_hash=_hash(material),
        )


class _MovementNativePolicyVerifier:
    """Recompute native semantics after exact independently signed owner intake."""

    def __init__(self, service: AcquisitionMovementService) -> None:
        self._service = service

    def verify_owner_relation(
        self,
        *,
        query: contract.NativeChronologyQuery,
        admission: contract.PredicatePolicyAdmissionStatement,
        policy: contract.PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: contract.NativeChronologyCandidate,
    ) -> (
        contract.VerifiedPredicatePolicyOwnerRelation | contract.PredicatePolicyOwnerRelationFailure
    ):
        failure = contract.PolicyOwnerRelationNotEstablished(
            code="policy_owner_relation_not_established",
            status="not_established",
            key=admission.key,
            requested_query_context_ref=query.requested_query_context_ref,
            owner_relation_ref=admission.owner_relation_ref,
        )
        service = self._service
        owner = service._evidence_owner
        try:
            if (
                query.domain.family != _FAMILY
                or query.domain.authority_purpose != _PURPOSE
                or len(candidate.ordered_members) != 1
            ):
                return failure
            actual = service._derive_movement(query.requested_cutoff_ref)
            if candidate != service._candidate(actual):
                return failure
            expected_rules = {("member", "supplier_reentry_binding"), ("query", "exact_row_scope")}
            if (
                {(r.subject_kind, r.predicate_id) for r in policy.statement.rules} != expected_rules
                or policy.statement.native_schema_profile != _PROFILE
                or policy.statement.required_native_head_role != "gy_movement_admission"
                or len(candidate.native_authority_head_refs) != 1
            ):
                return failure
            relation = security.parse_canonical_statement(
                owner_relation_bytes, MovementOwnerAdmission
            )
            if relation != MovementOwnerAdmission(
                query=query,
                policy_ref=policy.policy_ref,
                movement_artifact_ref=candidate.ordered_members[0].native_artifact_ref,
                supplier_receipt_ref=actual.supplier_receipt_ref,
            ):
                return failure
            matches = []
            for ref in owner._state().config.predicate_owner_verification_refs:
                receipt, record, _ = owner._signed_model(
                    ref,
                    contract.VerifiedPredicatePolicyOwnerRelation,
                    "predicate_owner_verification",
                )
                if (
                    receipt.query == query
                    and receipt.owner_relation_ref == admission.owner_relation_ref
                ):
                    if record.signer_provenance_ref != receipt.owner_verifier_provenance_ref:
                        return failure
                    matches.append(receipt)
            if len(matches) != 1:
                return failure
            receipt = matches[0]
            contract.OwnerQualifiedNativeCandidate(
                candidate=candidate,
                candidate_content_hash=contract._native_candidate_content_hash(candidate),
                owner_relation_verification=receipt,
            )
            provenance = receipt.policy_owner_provenance
            if (
                provenance.policy_ref != policy.policy_ref
                or provenance.policy_content_hash != policy.policy_content_hash
                or provenance.owner_provenance_ref != policy.statement.owner_provenance_ref
                or provenance.owner_provenance_content_hash
                != policy.statement.owner_provenance_content_hash
                or receipt.owner_relation_content_hash != admission.owner_relation_content_hash
                or owner._repository().read_raw(artifact_ref=provenance.owner_provenance_ref)
                != policy_owner_provenance_bytes
                or owner._repository().read_raw(artifact_ref=admission.owner_relation_ref)
                != owner_relation_bytes
            ):
                return failure
            subjects = (receipt.denominator_identity, receipt.query_context_identity)
            for subject in subjects:
                if (
                    security.raw_content_hash(
                        owner._runtime_repository().read_raw(artifact_ref=subject.artifact_ref)
                    )
                    != subject.raw_cas_hash
                ):
                    return failure
            expected_evidence = {
                (
                    "member",
                    candidate.ordered_members[0].member_ref,
                    "supplier_reentry_binding",
                ): candidate.ordered_members[0].native_artifact_ref,
                (
                    "query",
                    query.requested_query_context_ref,
                    "exact_row_scope",
                ): candidate.query_context_artifact_ref,
            }
            if {
                (r.subject_kind, r.subject_ref, r.predicate_id) for r in receipt.predicate_evidence
            } != set(expected_evidence):
                return failure
            for row in receipt.predicate_evidence:
                expected_ref = expected_evidence[
                    (row.subject_kind, row.subject_ref, row.predicate_id)
                ]
                if (
                    row.evidence_ref != expected_ref
                    or row.predicate_class != "recomputed"
                    or row.status != "satisfied"
                    or row.evidence_content_hash
                    != security.raw_content_hash(
                        owner._runtime_repository().read_raw(artifact_ref=expected_ref)
                    )
                    or row.evidence_verifier_provenance_ref != receipt.owner_verifier_provenance_ref
                ):
                    return failure
            for ref, expected_hash in (
                (receipt.verification_receipt_ref, receipt.verification_receipt_content_hash),
                (provenance.trust_snapshot_ref, provenance.trust_snapshot_content_hash),
                (provenance.verification_receipt_ref, provenance.verification_receipt_content_hash),
            ):
                if (
                    security.raw_content_hash(owner._repository().read_raw(artifact_ref=ref))
                    != expected_hash
                ):
                    return failure
            for ref in (receipt.owner_verifier_provenance_ref, provenance.verifier_provenance_ref):
                owner._repository().read_raw(artifact_ref=ref)
            return receipt
        except _READ_ERRORS:
            return failure


__all__ = [
    "AcquisitionMovementArtifact",
    "AcquisitionMovementService",
    "MovementIntakeResult",
    "MovementOwnerAdmission",
    "MovementRecord",
    "MovementRowProjection",
]
