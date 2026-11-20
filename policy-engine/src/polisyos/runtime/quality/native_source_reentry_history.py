"""Select and replay Native continuation cuts through existing action owners.

This extends the CAS/event/Control checkpoint mechanism used by
``candidate_source_reentry_history``. Recorded members are historical facts;
only the coordinator's separate current Native admission permits continuation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.runtime.quality.candidate_source_reentry_history import _n5_checkpoint_event
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    CandidateGroundingObservation,
    CandidateSummary,
    SimulationPortObservation,
)
from polisyos.scientist import SchedulingDecision

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlDiagnosticEventRecord,
    )
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        NativeDerivedWorldSelection,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import GenerationCycleRun
    from polisyos.runtime.quality.generation_source import GenerationSourceHandoff
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        GenericN5ResolvedResult,
    )

_CANON = canon.CanonSpec(forbid_floats=False)
_PRODUCER = "polisyos.runtime.acquisition_world_growth"
_KIND = "runtime_quality.native_source_reentry_checkpoint"
_HASH = r"^sha256:[0-9a-f]{64}$"
Member = Literal["prepared", "n5_claimed", "n5_completed", "tail_claimed", "cycle_completed"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class NativeSourceReentrySubject(_Strict):
    """Keep Native current-use identity separate from original configuration."""

    pending_action_ref: artifacts.ArtifactRef
    native_world_checkpoint_ref: artifacts.ArtifactRef
    native_input_collection_ref: artifacts.ArtifactRef
    original_generic_input_ref: artifacts.ArtifactRef
    original_profile_ref: artifacts.ArtifactRef
    context_job_ref: artifacts.ArtifactRef
    original_profile_selection_ref: str = Field(pattern=_HASH)
    current_profile_selection_ref: str = Field(pattern=_HASH)
    originating_attempt: int = Field(ge=1)
    execution_profile: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=0)
    route_id: str = Field(pattern=_HASH)
    source_run_id: str = Field(min_length=1)
    stable_design_problem_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    cycle_index: int = Field(ge=1)

    @model_validator(mode="after")
    def _selected(self) -> NativeSourceReentrySubject:
        for ref in self.parents().values():
            if ref.manifest_profile_sha256 is None or ref.media_type != "application/json":
                raise ValueError("native_reentry_selected_parent_required")
        return self

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Return the complete selected reference denominator for this subject."""
        return {
            "pending_native_action_phase": self.pending_action_ref,
            "native_world_checkpoint": self.native_world_checkpoint_ref,
            "native_input_collection": self.native_input_collection_ref,
            "original_generic_input": self.original_generic_input_ref,
            "original_profile": self.original_profile_ref,
            "native_context_job": self.context_job_ref,
        }


class _Member(_Strict):
    authority_purpose: Literal["native_candidate_reentry_only"] = "native_candidate_reentry_only"
    subject: NativeSourceReentrySubject
    MEMBER: ClassVar[Member]

    @model_validator(mode="after")
    def _selected_parents(self) -> _Member:
        if any(
            ref.manifest_profile_sha256 is None or ref.media_type != "application/json"
            for ref in self.parents().values()
        ):
            raise ValueError("native_reentry_selected_parent_required")
        return self

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Return selected references whose identities determine this member."""
        return self.subject.parents()


class NativeSourceReentryPrepared(_Member):
    """Actual N4, CGF, schedule and input, selected before numerical dispatch."""

    schema_version: Literal["NativeSourceReentryPrepared@1.0"] = "NativeSourceReentryPrepared@1.0"
    MEMBER = "prepared"
    n4_source_ref: artifacts.ArtifactRef
    n5_input_ref: artifacts.ArtifactRef
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str = Field(pattern=_HASH)
    grounding_observations: tuple[CandidateGroundingObservation, ...] = Field(min_length=1)
    candidate_summaries: tuple[CandidateSummary, ...] = Field(min_length=1)
    schedule: SchedulingDecision

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Bind the actual selected source and pre-dispatch Generic input."""
        return {**super().parents(), "n4_source": self.n4_source_ref, "n5_input": self.n5_input_ref}


class NativeSourceReentryN5Completed(_Member):
    """An exact Generic result whose full physical work was independently reopened."""

    schema_version: Literal["NativeSourceReentryN5Completed@1.0"] = (
        "NativeSourceReentryN5Completed@1.0"
    )
    MEMBER = "n5_completed"
    prepared_ref: artifacts.ArtifactRef
    n5_execution_ref: artifacts.ArtifactRef
    n5_result_ref: artifacts.ArtifactRef
    simulation: SimulationPortObservation

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Keep completed work selected by its exact prepared input."""
        return {
            **super().parents(),
            "prepared": self.prepared_ref,
            "n5_execution": self.n5_execution_ref,
            "n5_result": self.n5_result_ref,
        }


class NativeSourceReentryCycleCompleted(_Member):
    """The actual returned cycle and complete summary census before final publication."""

    schema_version: Literal["NativeSourceReentryCycleCompleted@1.0"] = (
        "NativeSourceReentryCycleCompleted@1.0"
    )
    MEMBER = "cycle_completed"
    n5_completed_ref: artifacts.ArtifactRef
    receipt: AcquisitionOverlayReentryReceipt

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Retain the selected numerical predecessor of the completed cycle."""
        return {**super().parents(), "n5_completed": self.n5_completed_ref}


class NativeSourceReentryClaim(_Member):
    """An at-most-once start fence, not evidence that its following work completed."""

    schema_version: Literal["NativeSourceReentryClaim@1.0"] = "NativeSourceReentryClaim@1.0"
    MEMBER = "n5_claimed"
    member: Literal["n5_claimed", "tail_claimed"]
    predecessor_ref: artifacts.ArtifactRef

    def parents(self) -> dict[str, artifacts.ArtifactRef]:
        """Bind a claim to the immediately preceding selected checkpoint."""
        return {**super().parents(), "predecessor": self.predecessor_ref}


NativeCheckpoint = (
    NativeSourceReentryPrepared | NativeSourceReentryN5Completed | NativeSourceReentryCycleCompleted
)


@dataclass(frozen=True, slots=True)
class NativeSourceReentryProgress:
    """Verified selected cuts; their presence alone grants no new execution right."""

    prepared: tuple[artifacts.ArtifactRef, NativeSourceReentryPrepared] | None = None
    n5_completed: tuple[artifacts.ArtifactRef, NativeSourceReentryN5Completed] | None = None
    cycle_completed: tuple[artifacts.ArtifactRef, NativeSourceReentryCycleCompleted] | None = None
    n5_claimed: bool = False
    tail_claimed: bool = False


def _phase(member: Member) -> str:
    return "native_source_reentry_" + member


def _event_id(subject: NativeSourceReentrySubject, member: Member) -> str:
    return _event_id_for_selection(
        subject.pending_action_ref, subject.native_world_checkpoint_ref, member
    )


def _event_id_for_selection(
    pending_ref: artifacts.ArtifactRef, world_ref: artifacts.ArtifactRef, member: Member
) -> str:
    identity = {
        "pending": pending_ref.model_dump(mode="json"),
        "world": world_ref.model_dump(mode="json"),
        "member": member,
    }
    digest = hashlib.sha256(canon.to_canonical_bytes(identity)).hexdigest()
    return "evt_native_source_reentry_" + digest


def _options(value: _Member) -> artifacts.ArtifactWriteOptions:
    parents = value.parents()
    if any(ref.manifest_profile_sha256 is None for ref in parents.values()):
        raise ValueError("native_reentry_selected_parent_required")
    return artifacts.ArtifactWriteOptions(
        kind=_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name="polisyos.runtime." + type(value).__name__, version="1.0"),
        producer=artifacts.ProducerInfo(component=_PRODUCER, version="1.0"),
        canon=artifacts.CanonInfo.from_spec(_CANON),
        governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
        tenant_context=artifacts.ArtifactTenantContextInfo(
            tenant_id=value.subject.tenant_id, cell_id=value.subject.cell_id
        ),
        inputs=[
            artifacts.input_ref_from_artifact_ref(ref, role=role) for role, ref in parents.items()
        ],
    )


def _same_subject(left: NativeSourceReentrySubject, right: NativeSourceReentrySubject) -> bool:
    return left.originating_attempt <= right.originating_attempt and left.model_dump(
        mode="json", exclude={"originating_attempt"}
    ) == right.model_dump(mode="json", exclude={"originating_attempt"})


def read_native_source_reentry_member(
    *,
    store: artifacts.ArtifactStore,
    events: RuntimeDiagnosticEventLog,
    subject: NativeSourceReentrySubject,
    member: Member,
) -> tuple[artifacts.ArtifactRef, _Member] | None:
    """Read one selected recorded member without acquiring current permission.

    This checks its exact event, body, manifest, and subject. Semantic Native
    source and physical-work replay belong to the coordinator below.
    """
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    if type(events) is not RuntimeDiagnosticEventLog or events.artifact_store is not store:
        raise TypeError("native_reentry_history_owner_required")
    head = events._store.get_acquisition_action_head_by_receipt(
        tenant_id=subject.tenant_id,
        cell_id=subject.cell_id,
        run_id=subject.run_id,
        source_job_id=subject.source_job_id,
        route_id=subject.route_id,
        action_generation=subject.action_generation,
        receipt_ref=str(subject.pending_action_ref.artifact_id),
    )
    if (
        head is None
        or head.receipt_phase != "world_committed_reentry_pending"
        or head.job_id != subject.action_job_id
        or head.receipt_manifest_profile_sha256
        != subject.pending_action_ref.manifest_profile_sha256
    ):
        raise ValueError("native_reentry_recorded_head_missing")
    rows = events.list_events(event_id=_event_id(subject, member), limit=2)
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("native_reentry_checkpoint_event_ambiguous")
    (row,) = rows
    event = row.event
    phase = _phase(member)
    prefix = f"run/{subject.run_id}/job/{subject.action_job_id}/phase/{phase}/selected-manifest/"
    if (
        not event.event_subject.startswith(prefix)
        or event.payload_ref is None
        or row.payload_ref != event.payload_ref
        or row.payload_inline is not None
        or event.artifact_refs != (event.payload_ref,)
        or (event.tenant_id, event.cell_id, event.run_id, event.job_id)
        != (subject.tenant_id, subject.cell_id, subject.run_id, subject.action_job_id)
    ):
        raise ValueError("native_reentry_checkpoint_event_mismatch")
    ref = artifacts.ArtifactRef(
        artifact_id=event.payload_ref,
        kind=_KIND,
        media_type="application/json",
        manifest_profile_sha256=event.event_subject.removeprefix(prefix),
    )
    model = {
        "prepared": NativeSourceReentryPrepared,
        "n5_claimed": NativeSourceReentryClaim,
        "n5_completed": NativeSourceReentryN5Completed,
        "tail_claimed": NativeSourceReentryClaim,
        "cycle_completed": NativeSourceReentryCycleCompleted,
    }[member]
    payload = artifacts.load_core_json_artifact(store, ref)
    value = model.model_validate_json(json.dumps(payload))
    if not _same_subject(value.subject, subject) or (
        isinstance(value, NativeSourceReentryClaim) and value.member != member
    ):
        raise ValueError("native_reentry_checkpoint_subject_mismatch")
    options = _options(value)
    manifest = store.get_manifest(ref)
    if (
        not store.verify(ref).ok
        or payload != value.model_dump(mode="json")
        or manifest.artifact_schema != options.schema
        or manifest.producer != options.producer
        or manifest.canon != options.canon
        or manifest.governance != options.governance
        or manifest.tenant_context != options.tenant_context
        or manifest.inputs != options.inputs
        or manifest.authority is not None
        or manifest.same_input_closure is not None
        or event
        != _n5_checkpoint_event(
            head=head,
            ref=ref,
            options=options,
            event_id=_event_id(subject, member),
            event_time=event.event_time,
            execution_profile=value.subject.execution_profile,
            phase=phase,
        )
    ):
        raise ValueError("native_reentry_checkpoint_selected_profile_mismatch")
    return ref, value


def _verify_native_source_reentry_prepared(
    *,
    store: artifacts.ArtifactStore,
    owner: GenericCycleSimulationAdmissionOwner,
    value: NativeSourceReentryPrepared,
) -> GenerationSourceHandoff:
    """Reopen the recorded Native source, candidate census and selected input."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
    )

    record = GenericCycleSimulationN5InputV1.model_validate(
        artifacts.load_core_json_artifact(store, value.n5_input_ref)
    )
    owner.resolve_n5_input(value.n5_input_ref, expected=record)
    source, candidate, _, _ = owner._replay_n5_input_sources(record)
    subject = value.subject
    if (
        record.schema_version != "policyos.runtime.generic_cycle_simulation_n5_input.v2"
        or record.source_run_id != subject.source_run_id
        or record.cycle_index != subject.cycle_index
        or record.design_problem_ref != subject.design_problem_ref
        or artifacts.artifact_ref_identity_key(record.n4_source_ref)
        != artifacts.artifact_ref_identity_key(value.n4_source_ref)
        or artifacts.artifact_ref_identity_key(record.context_job_ref)
        != artifacts.artifact_ref_identity_key(subject.context_job_ref)
        or record.candidate_id != value.candidate_id
        or record.candidate_atom_hash != value.candidate_content_hash
        or value.schedule.candidate_id != value.candidate_id
        or record.native_world_checkpoint_ref is None
        or artifacts.artifact_ref_identity_key(record.native_world_checkpoint_ref)
        != artifacts.artifact_ref_identity_key(subject.native_world_checkpoint_ref)
        or record.original_generic_input_ref is None
        or artifacts.artifact_ref_identity_key(record.original_generic_input_ref)
        != artifacts.artifact_ref_identity_key(subject.original_generic_input_ref)
        or artifacts.artifact_ref_identity_key(record.profile_ref)
        != artifacts.artifact_ref_identity_key(subject.original_profile_ref)
        or record.profile.profile_selection_ref != subject.original_profile_selection_ref
        or record.native_current_profile_selection_ref != subject.current_profile_selection_ref
        or (record.tenant_id, record.cell_id, record.run_id, record.job_id)
        != (subject.tenant_id, subject.cell_id, subject.run_id, subject.action_job_id)
    ):
        raise ValueError("native_reentry_prepared_source_mismatch")
    candidates = tuple(source.generation_result.candidates)
    identities = {(item.candidate_id, item.atom.content_hash) for item in candidates}
    grounding = {item.candidate_id: item for item in value.grounding_observations}
    summaries = {(item.candidate_id, item.content_hash) for item in value.candidate_summaries}
    if (
        len(identities) != len(candidates)
        or summaries != identities
        or len(value.candidate_summaries) != len(candidates)
        or set(grounding) != {item.candidate_id for item in candidates}
        or len(grounding) != len(value.grounding_observations)
        or any(item.cycle_index != subject.cycle_index for item in value.candidate_summaries)
        or (candidate.candidate_id, candidate.atom.content_hash) not in identities
    ):
        raise ValueError("native_reentry_prepared_census_mismatch")
    return source


def _verify_native_source_reentry_n5(
    *,
    store: artifacts.ArtifactStore,
    owner: GenericCycleSimulationAdmissionOwner,
    world_model_record_content_hash: str,
    prepared: NativeSourceReentryPrepared,
    value: NativeSourceReentryN5Completed,
) -> GenericN5ResolvedResult:
    """Verify one stored Generic result and its complete physical-work observation."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_generic_program_graph_n5_content_observation,
    )

    record = GenericCycleSimulationN5InputV1.model_validate(
        artifacts.load_core_json_artifact(store, prepared.n5_input_ref)
    )
    simulation = value.simulation
    if (
        simulation.status != "joint_simulated"
        or simulation.candidate_id != prepared.candidate_id
        or any(
            left is None
            or artifacts.artifact_ref_identity_key(left)
            != artifacts.artifact_ref_identity_key(right)
            for left, right in (
                (simulation.generic_n5_input_ref, prepared.n5_input_ref),
                (simulation.generic_n5_execution_ref, value.n5_execution_ref),
                (simulation.simulation_result_ref, value.n5_result_ref),
                (simulation.generic_n4_source_ref, prepared.n4_source_ref),
                (simulation.generic_context_job_ref, record.context_job_ref),
                (simulation.cycle_substrate_context_job_ref, record.context_job_ref),
                (simulation.generic_profile_ref, record.profile_ref),
            )
        )
        or simulation.generic_profile_selection_ref != record.profile.profile_selection_ref
        or simulation.generic_n4_child_profile_family_ref is not None
        or simulation.generic_n4_child_profile_set_ref is not None
        or simulation.model_input_obligation_set_ref is not None
    ):
        raise ValueError("native_reentry_n5_selection_mismatch")
    join, result = owner.resolve_n5_execution_join_with_result(
        value.n5_execution_ref,
        expected=GenericN5ExecutionJoinExpectation(
            input_ref=prepared.n5_input_ref,
            result_ref=value.n5_result_ref,
            status="joint_simulated",
            model_input_obligation_set_ref=None,
            n4_source_ref=prepared.n4_source_ref,
            context_job_ref=record.context_job_ref,
            profile_ref=record.profile_ref,
            child_family_ref=None,
            child_set_ref=None,
            profile_selection_ref=record.profile.profile_selection_ref,
            profile=record.profile,
            design_problem_ref=record.design_problem_ref,
            outcome_variable=record.outcome_variable,
            cycle_index=record.cycle_index,
            candidate_id=record.candidate_id,
            candidate_atom_hash=record.candidate_atom_hash,
            world_model_record_content_hash=world_model_record_content_hash,
            job_id=record.job_id,
            run_id=record.run_id,
            source_run_id=record.source_run_id,
            tenant_id=record.tenant_id,
            cell_id=record.cell_id,
        ),
    )
    if join.status != "resolved" or result is None:
        raise ValueError("native_reentry_n5_owner_not_established")
    from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome

    status, blockers = _joint_simulation_port_outcome(result.result, request=result.request)
    blockers = tuple(dict.fromkeys((*blockers, "simulation_only_k_sim_not_world_evidence")))
    world = result.request.world_model_record
    expected_diagnostics = {
        "engine_decisions": [
            item.model_dump(mode="json") for item in result.result.engine_decisions
        ],
        "trajectory_count": len(result.result.trajectories),
        "interaction_count": len(result.result.interaction_terms),
        "simulation_result_ref": str(value.n5_result_ref.artifact_id),
        "world_model_record_id": world.world_model_record_id,
        "world_model_record_content_hash": world.content_hash,
        "program_binding_failures": {},
    }
    if (
        status != "joint_simulated"
        or simulation.simulation_ref != result.result.receipt.payload_hash
        or simulation.uncertainty_kind != result.result.uncertainty_kind
        or simulation.authority_blockers != blockers
        or simulation.diagnostics != expected_diagnostics
        or simulation.k_world_ref_before != world.content_hash
        or simulation.k_world_ref_after != world.content_hash
    ):
        raise ValueError("native_reentry_n5_observation_mismatch")
    observation = read_generic_program_graph_n5_content_observation(
        result.result,
        input_ref=prepared.n5_input_ref,
        expected_request=result.request,
        current_method_input_bindings_ref=(
            result.initial_method_input.current_method_input_bindings_ref
            if result.initial_method_input is not None
            else None
        ),
        store=store,
    )
    if (
        observation.completion.status != "recomputed"
        or result.result.diagnostics.get("physical_work_capture_status") != "observed"
        or not result.result.physical_work_observations
        or any(item.status != "completed" for item in result.result.physical_work_observations)
        or "physical_work_interruption" in result.result.diagnostics
    ):
        raise ValueError("native_reentry_n5_physical_completion_not_established")

    return result


def _verify_native_source_reentry_cycle(
    *,
    source_generation_run: GenerationCycleRun,
    prepared: NativeSourceReentryPrepared,
    n5_ref: artifacts.ArtifactRef,
    n5: NativeSourceReentryN5Completed,
    value: NativeSourceReentryCycleCompleted,
) -> None:
    """Reconcile the selected returned cycle with its source and numerical cut."""
    from polisyos.runtime.quality.generation_cycle import (
        validate_acquisition_overlay_continuation,
    )

    receipt = value.receipt
    validate_acquisition_overlay_continuation(source_generation_run, receipt)
    cycle = receipt.new_cycle
    if (
        artifacts.artifact_ref_identity_key(value.n5_completed_ref)
        != artifacts.artifact_ref_identity_key(n5_ref)
        or cycle.cycle_index != value.subject.cycle_index
        or cycle.design_problem_ref != value.subject.stable_design_problem_ref
        or cycle.selected_candidate_ref != prepared.candidate_id
        or cycle.selected_candidate_content_hash != prepared.candidate_content_hash
        or cycle.simulation.model_dump(mode="json") != n5.simulation.model_dump(mode="json")
        or {(item.candidate_id, item.content_hash) for item in receipt.candidate_summaries}
        != {(item.candidate_id, item.content_hash) for item in prepared.candidate_summaries}
        or len(receipt.candidate_summaries) != len(prepared.candidate_summaries)
        or any(
            item.cycle_index != value.subject.cycle_index for item in receipt.candidate_summaries
        )
        or cycle.candidate_ids != tuple(item.candidate_id for item in prepared.candidate_summaries)
        or cycle.grounding.model_dump(mode="json")
        != next(
            item.model_dump(mode="json")
            for item in prepared.grounding_observations
            if item.candidate_id == prepared.candidate_id
        )
    ):
        raise ValueError("native_reentry_cycle_selection_mismatch")


def _verify_native_source_reentry_progress(
    *,
    store: artifacts.ArtifactStore,
    owner: GenericCycleSimulationAdmissionOwner,
    source_generation_run: GenerationCycleRun,
    world_model_record_content_hash: str,
    prepared: tuple[artifacts.ArtifactRef, _Member] | None,
    n5: tuple[artifacts.ArtifactRef, _Member] | None,
    cycle: tuple[artifacts.ArtifactRef, _Member] | None,
    n5_claim: tuple[artifacts.ArtifactRef, _Member] | None,
    tail_claim: tuple[artifacts.ArtifactRef, _Member] | None,
) -> tuple[NativeSourceReentryProgress, GenericN5ResolvedResult | None]:
    """Apply the same selected-member and semantic closure law to both readers."""
    if prepared is None:
        if any(item is not None for item in (n5, cycle, n5_claim, tail_claim)):
            raise ValueError("native_reentry_prepared_checkpoint_missing")
        return NativeSourceReentryProgress(), None
    prepared_ref, value = prepared
    if type(value) is not NativeSourceReentryPrepared:
        raise TypeError("native_reentry_prepared_checkpoint_untyped")
    _verify_native_source_reentry_prepared(store=store, owner=owner, value=value)
    if any(
        item is not None and type(item[1]) is not NativeSourceReentryClaim
        for item in (n5_claim, tail_claim)
    ):
        raise TypeError("native_reentry_claim_untyped")
    if n5_claim is not None and artifacts.artifact_ref_identity_key(
        n5_claim[1].predecessor_ref
    ) != artifacts.artifact_ref_identity_key(prepared_ref):
        raise ValueError("native_reentry_claim_predecessor_mismatch")
    if n5 is None:
        if n5_claim is not None or cycle is not None or tail_claim is not None:
            raise ValueError("native_reentry_n5_completion_not_established")
        return NativeSourceReentryProgress(prepared=(prepared_ref, value)), None
    n5_ref, completed = n5
    if type(completed) is not NativeSourceReentryN5Completed or n5_claim is None:
        raise ValueError("native_reentry_n5_claim_missing")
    if artifacts.artifact_ref_identity_key(
        completed.prepared_ref
    ) != artifacts.artifact_ref_identity_key(prepared_ref):
        raise ValueError("native_reentry_n5_predecessor_mismatch")
    resolved_result = _verify_native_source_reentry_n5(
        store=store,
        owner=owner,
        world_model_record_content_hash=world_model_record_content_hash,
        prepared=value,
        value=completed,
    )
    if tail_claim is not None and artifacts.artifact_ref_identity_key(
        tail_claim[1].predecessor_ref
    ) != artifacts.artifact_ref_identity_key(n5_ref):
        raise ValueError("native_reentry_claim_predecessor_mismatch")
    if cycle is None:
        if tail_claim is not None:
            raise ValueError("native_reentry_cycle_completion_not_established")
        return NativeSourceReentryProgress(
            prepared=(prepared_ref, value), n5_completed=(n5_ref, completed), n5_claimed=True
        ), resolved_result
    cycle_ref, finished = cycle
    if type(finished) is not NativeSourceReentryCycleCompleted or tail_claim is None:
        raise ValueError("native_reentry_tail_claim_missing")
    _verify_native_source_reentry_cycle(
        source_generation_run=source_generation_run,
        prepared=value,
        n5_ref=n5_ref,
        n5=completed,
        value=finished,
    )
    return NativeSourceReentryProgress(
        prepared=(prepared_ref, value),
        n5_completed=(n5_ref, completed),
        cycle_completed=(cycle_ref, finished),
        n5_claimed=True,
        tail_claimed=True,
    ), resolved_result


@dataclass(frozen=True, slots=True)
class NativeSourceReentryHistory:
    """Verified recorded cuts and result, without a current-use capability."""

    progress: NativeSourceReentryProgress
    input_record: GenericCycleSimulationN5InputV1
    selection: NativeDerivedWorldSelection
    result: GenericN5ResolvedResult


def read_native_source_reentry_history(
    *,
    store: artifacts.ArtifactStore,
    events: RuntimeDiagnosticEventLog,
    owner: GenericCycleSimulationAdmissionOwner,
    input_ref: artifacts.ArtifactRef,
    source_generation_run: GenerationCycleRun,
    receipt: AcquisitionOverlayReentryReceipt,
    expected_action_job_id: str,
    expected_action_generation: int,
    expected_source_job_id: str,
    expected_route_id: str,
    expected_run_id: str,
    expected_tenant_id: str,
    expected_cell_id: str,
) -> NativeSourceReentryHistory:
    """Reopen one completed Native continuation as historical candidate evidence.

    The stored event selects the full manifest profile, and the recorded Native
    world owner reconstructs the immutable input scope. Current action/lease
    permission remains exclusively in ``NativeSourceReentryCoordinator``.
    """
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
    )
    from polisyos.runtime.quality.native_generic_context import _selection_for_input

    if (
        type(owner) is not GenericCycleSimulationAdmissionOwner
        or owner.store is not store
        or type(events) is not RuntimeDiagnosticEventLog
        or events.artifact_store is not store
        or owner._native_action_control_store is not events._store
        or owner._native_action_event_log is not events
    ):
        raise TypeError("native_reentry_history_owner_required")
    if (
        input_ref.kind != "runtime.quality.generic_cycle_simulation_n5_input"
        or input_ref.media_type != "application/json"
        or input_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("native_reentry_history_input_unselected")
    record = GenericCycleSimulationN5InputV1.model_validate(
        artifacts.load_core_json_artifact(store, input_ref)
    )
    selection = _selection_for_input(owner, record)
    phase, checkpoint = selection.pending_action_phase, selection.checkpoint
    if (
        (record.job_id, record.run_id, record.tenant_id, record.cell_id)
        != (expected_action_job_id, expected_run_id, expected_tenant_id, expected_cell_id)
        or (checkpoint.source_job_id, checkpoint.route_id, phase.action_generation)
        != (expected_source_job_id, expected_route_id, expected_action_generation)
        or record.source_run_id != source_generation_run.run_id
        or receipt.source_run_id != source_generation_run.run_id
        or record.cycle_index != receipt.new_cycle.cycle_index
        or record.cycle_index != receipt.source_cycle_index + 1
        or len(checkpoint.collection_refs) != 1
    ):
        raise ValueError("native_reentry_history_source_scope_mismatch")
    # Only the canonical selected event locates the prepared subject. Untrusted
    # body values never choose a default manifest or establish current rights.
    rows = events.list_events(
        event_id=_event_id_for_selection(
            selection.pending_action_phase_ref, selection.checkpoint_ref, "prepared"
        ),
        limit=2,
    )
    if len(rows) != 1:
        raise ValueError("native_reentry_prepared_checkpoint_missing")
    event = rows[0].event
    prefix = (
        f"run/{expected_run_id}/job/{expected_action_job_id}"
        "/phase/native_source_reentry_prepared/selected-manifest/"
    )
    if event.payload_ref is None or not event.event_subject.startswith(prefix):
        raise ValueError("native_reentry_checkpoint_event_mismatch")
    seed_ref = artifacts.ArtifactRef(
        artifact_id=event.payload_ref,
        kind=_KIND,
        media_type="application/json",
        manifest_profile_sha256=event.event_subject.removeprefix(prefix),
    )
    seed = NativeSourceReentryPrepared.model_validate_json(
        json.dumps(artifacts.load_core_json_artifact(store, seed_ref))
    )
    action_job = events._store.get_job(expected_action_job_id)
    if (
        action_job is None
        or action_job.kind != "acquisition"
        or action_job.run_id != expected_run_id
        or seed.subject.originating_attempt > action_job.attempt
        or seed.subject.execution_profile != action_job.effective_execution_profile
    ):
        raise ValueError("native_reentry_history_action_job_mismatch")
    expected_subject = NativeSourceReentrySubject(
        pending_action_ref=selection.pending_action_phase_ref,
        native_world_checkpoint_ref=selection.checkpoint_ref,
        native_input_collection_ref=checkpoint.collection_refs[0],
        original_generic_input_ref=selection.original_generic_input_ref,
        original_profile_ref=selection.original_profile_ref,
        context_job_ref=record.context_job_ref,
        original_profile_selection_ref=selection.original_profile.profile_selection_ref,
        current_profile_selection_ref=record.native_current_profile_selection_ref,
        originating_attempt=action_job.attempt,
        execution_profile=action_job.effective_execution_profile,
        tenant_id=expected_tenant_id,
        cell_id=expected_cell_id,
        run_id=expected_run_id,
        source_job_id=expected_source_job_id,
        action_job_id=expected_action_job_id,
        action_generation=expected_action_generation,
        route_id=expected_route_id,
        source_run_id=source_generation_run.run_id,
        stable_design_problem_ref=source_generation_run.design_problem_ref,
        design_problem_ref=record.design_problem_ref,
        cycle_index=record.cycle_index,
    )
    if not _same_subject(seed.subject, expected_subject) or artifacts.artifact_ref_identity_key(
        seed.n5_input_ref
    ) != artifacts.artifact_ref_identity_key(input_ref):
        raise ValueError("native_reentry_history_subject_mismatch")
    selected = {
        member: read_native_source_reentry_member(
            store=store, events=events, subject=expected_subject, member=member
        )
        for member in ("prepared", "n5_completed", "cycle_completed", "n5_claimed", "tail_claimed")
    }
    prepared = selected["prepared"]
    if prepared is None or artifacts.artifact_ref_identity_key(
        prepared[0]
    ) != artifacts.artifact_ref_identity_key(seed_ref):
        raise ValueError("native_reentry_history_prepared_selection_mismatch")
    progress, resolved = _verify_native_source_reentry_progress(
        store=store,
        owner=owner,
        source_generation_run=source_generation_run,
        world_model_record_content_hash=selection.world_model_record.content_hash,
        prepared=prepared,
        n5=selected["n5_completed"],
        cycle=selected["cycle_completed"],
        n5_claim=selected["n5_claimed"],
        tail_claim=selected["tail_claimed"],
    )
    if (
        progress.cycle_completed is None
        or progress.n5_completed is None
        or resolved is None
        or progress.cycle_completed[1].receipt != receipt
    ):
        raise ValueError("native_reentry_history_completion_not_established")
    if any(
        read_native_source_reentry_member(
            store=store, events=events, subject=expected_subject, member=member
        )
        != value
        for member, value in selected.items()
    ):
        raise ValueError("native_reentry_history_selection_changed")
    return NativeSourceReentryHistory(progress, record, selection, resolved)


type _SelectedMember = tuple[artifacts.ArtifactRef, _Member]
type _SelectedIdentity = tuple[str, str, str, str | None]
type _SelectedVector = tuple[tuple[Member, _SelectedIdentity | None], ...]


def _selected_member_identity(member: _SelectedMember | None) -> _SelectedIdentity | None:
    return artifacts.artifact_ref_identity_key(member[0]) if member is not None else None


@dataclass(frozen=True, slots=True)
class _NativeTransitionCut:
    """Bind one exact live owner and selected member vector for a single transition."""

    head: AcquisitionActionHeadRecord
    subject: NativeSourceReentrySubject
    target: Member
    predecessors: _SelectedVector
    target_identity: _SelectedIdentity | None

    def selection(self, published: artifacts.ArtifactRef | None = None) -> _SelectedVector:
        target = (
            artifacts.artifact_ref_identity_key(published)
            if published is not None
            else self.target_identity
        )
        return (*self.predecessors, (self.target, target))


class NativeSourceReentryCoordinator:
    """Fence every selected Native phase by its real current action owner."""

    def __init__(
        self,
        *,
        bridge: AcquisitionWorldGrowthBridge,
        closure: VerifiedAcquisitionRouteClosure,
        handoff: GenericCycleNativeWorldContextHandoffV1,
        collection_ref: artifacts.ArtifactRef,
    ) -> None:
        self.bridge = bridge
        self.closure = closure
        self.handoff = handoff
        self.collection_ref = collection_ref
        self._current()

    def _current(self) -> tuple[AcquisitionActionHeadRecord, NativeSourceReentrySubject]:
        from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
        from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
        from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleNativeWorldContextHandoffV1,
            GenericCycleSimulationAdmissionOwner,
        )
        from polisyos.runtime.quality.native_generic_context import (
            _resolve_native_world_handoff_selection,
        )

        bridge, closure, handoff = self.bridge, self.closure, self.handoff
        if (
            type(bridge) is not AcquisitionWorldGrowthBridge
            or type(closure) is not VerifiedAcquisitionRouteClosure
            or type(handoff) is not GenericCycleNativeWorldContextHandoffV1
            or bridge.control_store is None
            or bridge.action_head_sink is None
            or bridge._source_control_service is None
        ):
            raise TypeError("native_reentry_current_owner_required")
        owner = bridge._source_control_service._generic_cycle_simulation_admission_owner
        if (
            type(owner) is not GenericCycleSimulationAdmissionOwner
            or owner.store is not bridge.artifact_store
        ):
            raise ValueError("native_reentry_current_owner_mismatch")
        selection = _resolve_native_world_handoff_selection(
            owner,
            handoff=handoff,
            problem=closure.design_problem_basis,
            expected_bridge=bridge,
            expected_closure=closure,
        )
        pending_ref = selection.pending_action_phase_ref
        if tuple(
            artifacts.artifact_ref_identity_key(ref) for ref in selection.checkpoint.collection_refs
        ) != (artifacts.artifact_ref_identity_key(self.collection_ref),):
            raise ValueError("native_reentry_current_selection_mismatch")
        snapshot = bridge.action_head_sink.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        admission = bridge.control_store.current_execution_job_admission()
        if (
            snapshot is None
            or snapshot.head.receipt_phase != "world_committed_reentry_pending"
            or snapshot.head.job_id != handoff.job_id
            or snapshot.head.receipt_ref != str(pending_ref.artifact_id)
            or snapshot.head.receipt_manifest_profile_sha256 != pending_ref.manifest_profile_sha256
            or admission.job.kind != "acquisition"
            or admission.job.state != "running"
            or admission.scope.status != "established"
            or not admission.scope.actor_authenticated
            or (
                admission.scope.tenant_id,
                admission.scope.cell_id,
                admission.job.run_id,
                admission.job.job_id,
            )
            != (closure.tenant_id, closure.cell_id, closure.run_id, handoff.job_id)
        ):
            raise ValueError("native_reentry_current_head_mismatch")
        head = snapshot.head
        subject = NativeSourceReentrySubject(
            pending_action_ref=pending_ref,
            native_world_checkpoint_ref=handoff.native_world_checkpoint_ref,
            native_input_collection_ref=self.collection_ref,
            original_generic_input_ref=handoff.original_generic_input_ref,
            original_profile_ref=handoff.profile_ref,
            context_job_ref=handoff.context_job_ref,
            original_profile_selection_ref=handoff.profile.profile_selection_ref,
            current_profile_selection_ref=handoff.current_profile_selection_ref,
            originating_attempt=admission.attempt,
            execution_profile=admission.job.effective_execution_profile,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            action_job_id=head.job_id,
            action_generation=head.action_generation,
            route_id=closure.route_id,
            source_run_id=closure.generation_run.run_id,
            stable_design_problem_ref=closure.generation_run.design_problem_ref,
            design_problem_ref=cycle_job_design_problem_ref(closure.design_problem_basis),
            cycle_index=closure.source_cycle.cycle_index + 1,
        )
        return head, subject

    @property
    def owner(self) -> GenericCycleSimulationAdmissionOwner:
        """Return the already bound real Native Generic owner, never a new grant."""
        return self.bridge._source_control_service._generic_cycle_simulation_admission_owner

    def _read_selected(
        self, subject: NativeSourceReentrySubject, member: Member
    ) -> tuple[artifacts.ArtifactRef, _Member] | None:
        return read_native_source_reentry_member(
            store=self.bridge.artifact_store,
            events=self.bridge.event_log,
            subject=subject,
            member=member,
        )

    def _read(self, member: Member) -> tuple[artifacts.ArtifactRef, _Member] | None:
        _, subject = self._current()
        result = self._read_selected(subject, member)
        self._current()
        return result

    def _start_transition(
        self, target: Member, *predecessors: Member
    ) -> tuple[_NativeTransitionCut, dict[Member, _SelectedMember | None]]:
        head, live_subject = self._current()
        subject = live_subject.model_copy(deep=True)
        selected = {
            member: self._read_selected(subject, member) for member in (*predecessors, target)
        }
        cut = _NativeTransitionCut(
            head=head,
            subject=subject,
            target=target,
            predecessors=tuple(
                (member, _selected_member_identity(selected[member])) for member in predecessors
            ),
            target_identity=_selected_member_identity(selected[target]),
        )
        return cut, selected

    def _reopen_transition_members(
        self, cut: _NativeTransitionCut, *, published: artifacts.ArtifactRef | None = None
    ) -> _SelectedMember | None:
        for member, expected in cut.predecessors:
            if _selected_member_identity(self._read_selected(cut.subject, member)) != expected:
                raise ValueError("native_reentry_checkpoint_selection_changed")
        target = self._read_selected(cut.subject, cut.target)
        if _selected_member_identity(target) != cut.selection(published)[-1][1]:
            if published is not None:
                raise ValueError("native_reentry_checkpoint_selection_missing")
            if cut.target in {"n5_claimed", "tail_claimed"} and target is not None:
                raise ValueError("native_reentry_uncommitted_claim_not_established")
            raise ValueError("native_reentry_checkpoint_selection_changed")
        return target

    def _selected_events(
        self, subject: NativeSourceReentrySubject, selection: _SelectedVector
    ) -> tuple[ControlDiagnosticEventRecord, ...]:
        events: list[ControlDiagnosticEventRecord] = []
        for member, expected in selection:
            rows = self.bridge.event_log.list_events(event_id=_event_id(subject, member), limit=2)
            if expected is None:
                if rows:
                    raise ValueError("native_reentry_checkpoint_selection_changed")
                continue
            artifact_id, _kind, _media_type, profile = expected
            event_subject = (
                f"run/{subject.run_id}/job/{subject.action_job_id}/phase/{_phase(member)}"
                f"/selected-manifest/{profile}"
            )
            if (
                len(rows) != 1
                or rows[0].payload_ref != artifact_id
                or rows[0].event.event_subject != event_subject
            ):
                raise ValueError("native_reentry_checkpoint_selection_changed")
            events.append(rows[0])
        return tuple(events)

    def _require_current_cut(
        self,
        head: AcquisitionActionHeadRecord,
        subject: NativeSourceReentrySubject,
        selection: _SelectedVector,
    ) -> None:
        events = self._selected_events(subject, selection)
        # All CAS/member reopens precede this complete Catalog/source sweep.
        # Follow it only with SQL, so selection drift during the sweep is
        # observed without opening a new expensive window after currentness.
        if self._current() != (head, subject):
            raise ValueError("native_reentry_current_head_changed")
        if self._selected_events(subject, selection) != events:
            raise ValueError("native_reentry_checkpoint_selection_changed")
        self._require_live_head(head, subject)

    def _publish(self, value: _Member, cut: _NativeTransitionCut) -> artifacts.ArtifactRef:
        head, subject, member = cut.head, cut.subject, cut.target
        value_member = value.member if isinstance(value, NativeSourceReentryClaim) else value.MEMBER
        if value_member != member or not _same_subject(value.subject, subject):
            raise ValueError("native_reentry_checkpoint_subject_mismatch")
        existing = self._reopen_transition_members(cut)
        if existing is not None:
            if member in {"n5_claimed", "tail_claimed"}:
                raise ValueError("native_reentry_uncommitted_claim_not_established")
            ref, previous = existing
            if previous.model_dump(mode="json") != value.model_dump(mode="json"):
                raise ValueError("native_reentry_checkpoint_conflict")
            self._reopen_transition_members(cut)
            self._require_current_cut(head, subject, cut.selection())
            return ref
        if value.subject.originating_attempt != subject.originating_attempt:
            raise ValueError("native_reentry_checkpoint_attempt_mismatch")
        options = _options(value)
        store = self.bridge.artifact_store
        ref = store.put_json(
            value.model_dump(mode="json"), options, _CANON, return_selected_profile=True
        )
        if artifacts.load_core_json_artifact(store, ref) != value.model_dump(mode="json"):
            raise ValueError("native_reentry_checkpoint_readback_mismatch")

        self._reopen_transition_members(cut)
        self._require_current_cut(head, subject, cut.selection())
        event = _n5_checkpoint_event(
            head=head,
            ref=ref,
            options=options,
            event_id=_event_id(subject, member),
            event_time=datetime.now(UTC),
            execution_profile=subject.execution_profile,
            phase=_phase(member),
        )
        self.bridge.control_store.append_native_source_reentry_checkpoint(
            pending_head=head,
            prepared_event=self.bridge.event_log.prepare(event),
        )

        self._reopen_transition_members(cut, published=ref)
        self._reopen_transition_members(cut, published=ref)
        self._require_current_cut(head, subject, cut.selection(ref))
        return ref

    def _verify_prepared(self, value: NativeSourceReentryPrepared) -> GenerationSourceHandoff:
        return _verify_native_source_reentry_prepared(
            store=self.bridge.artifact_store, owner=self.owner, value=value
        )

    def progress(self) -> NativeSourceReentryProgress:
        """Read one member vector across two independent current action cuts."""
        head, live_subject = self._current()
        # The subject borrows selected references from the handoff. Detach
        # the opening values before comparing them to independently read ones.
        subject = live_subject.model_copy(deep=True)
        members: tuple[Member, ...] = (
            "prepared",
            "n5_completed",
            "cycle_completed",
            "n5_claimed",
            "tail_claimed",
        )
        selected = {member: self._read_selected(subject, member) for member in members}
        progress, _result = _verify_native_source_reentry_progress(
            store=self.bridge.artifact_store,
            owner=self.owner,
            source_generation_run=self.closure.generation_run,
            world_model_record_content_hash=self.handoff.context.world_model_record_content_hash,
            prepared=selected["prepared"],
            n5=selected["n5_completed"],
            cycle=selected["cycle_completed"],
            n5_claim=selected["n5_claimed"],
            tail_claim=selected["tail_claimed"],
        )
        if any(
            self._read_selected(subject, member) != original
            for member, original in selected.items()
        ):
            raise ValueError("native_reentry_checkpoint_selection_changed")
        selection = tuple(
            (member, _selected_member_identity(value)) for member, value in selected.items()
        )
        self._require_current_cut(head, subject, selection)
        return progress

    def _require_live_head(
        self, head: AcquisitionActionHeadRecord, subject: NativeSourceReentrySubject
    ) -> None:
        # Selected-member readback can outlast the lease or overlap a new head.
        control = self.bridge.control_store
        admission = control.current_execution_job_admission()
        heads = control.list_acquisition_action_heads(
            tenant_id=head.tenant_id,
            cell_id=head.cell_id,
            run_id=head.run_id,
            source_job_id=head.source_job_id,
            route_id=head.route_id,
        )
        if (
            not heads
            or heads[-1] != head
            or admission.attempt != subject.originating_attempt
            or admission.job.job_id != head.job_id
        ):
            raise ValueError("native_reentry_current_head_changed")

    def prepare(
        self,
        *,
        n4_source_ref: artifacts.ArtifactRef,
        input_ref: artifacts.ArtifactRef,
        candidate_id: str,
        candidate_hash: str,
        grounding: tuple[CandidateGroundingObservation, ...],
        summaries: tuple[CandidateSummary, ...],
        schedule: SchedulingDecision,
    ) -> artifacts.ArtifactRef:
        """Select actual completed preparation before any N5 claim."""
        cut, _selected = self._start_transition("prepared")
        value = NativeSourceReentryPrepared(
            subject=cut.subject,
            n4_source_ref=n4_source_ref,
            n5_input_ref=input_ref,
            candidate_id=candidate_id,
            candidate_content_hash=candidate_hash,
            grounding_observations=grounding,
            candidate_summaries=summaries,
            schedule=schedule,
        )
        self._verify_prepared(value)
        return self._publish(value, cut)

    def claim(
        self, member: Literal["n5_claimed", "tail_claimed"], predecessor_ref: artifacts.ArtifactRef
    ) -> None:
        """Select one start; an already claimed incomplete operation never restarts."""
        predecessor = "prepared" if member == "n5_claimed" else "n5_completed"
        cut, selected = self._start_transition(member, predecessor)
        if selected[member] is not None:
            raise ValueError("native_reentry_uncommitted_claim_not_established")
        previous = selected[predecessor]
        if previous is None or artifacts.artifact_ref_identity_key(
            previous[0]
        ) != artifacts.artifact_ref_identity_key(predecessor_ref):
            raise ValueError("native_reentry_claim_predecessor_mismatch")
        value = NativeSourceReentryClaim(
            subject=cut.subject, member=member, predecessor_ref=predecessor_ref
        )
        self._publish(value, cut)

    def complete_n5(
        self, prepared_ref: artifacts.ArtifactRef, simulation: SimulationPortObservation
    ) -> artifacts.ArtifactRef:
        """Select only a reopened, fully completed Generic physical result."""
        cut, selected = self._start_transition("n5_completed", "prepared", "n5_claimed")
        prepared = selected["prepared"]
        if (
            prepared is None
            or type(prepared[1]) is not NativeSourceReentryPrepared
            or artifacts.artifact_ref_identity_key(prepared[0])
            != artifacts.artifact_ref_identity_key(prepared_ref)
        ):
            raise ValueError("native_reentry_prepared_checkpoint_missing")
        claim = selected["n5_claimed"]
        if (
            claim is None
            or type(claim[1]) is not NativeSourceReentryClaim
            or artifacts.artifact_ref_identity_key(claim[1].predecessor_ref)
            != artifacts.artifact_ref_identity_key(prepared_ref)
        ):
            raise ValueError("native_reentry_n5_claim_missing")
        if simulation.generic_n5_execution_ref is None or simulation.simulation_result_ref is None:
            raise ValueError("native_reentry_n5_completion_not_established")
        value = NativeSourceReentryN5Completed(
            subject=cut.subject,
            prepared_ref=prepared_ref,
            n5_execution_ref=simulation.generic_n5_execution_ref,
            n5_result_ref=simulation.simulation_result_ref,
            simulation=SimulationPortObservation.model_validate_json(simulation.model_dump_json()),
        )
        self._verify_n5(prepared[1], value)
        return self._publish(value, cut)

    def _verify_n5(
        self, prepared: NativeSourceReentryPrepared, value: NativeSourceReentryN5Completed
    ) -> None:
        _verify_native_source_reentry_n5(
            store=self.bridge.artifact_store,
            owner=self.owner,
            world_model_record_content_hash=self.handoff.context.world_model_record_content_hash,
            prepared=prepared,
            value=value,
        )

    def _verify_cycle(
        self,
        prepared: NativeSourceReentryPrepared,
        n5_ref: artifacts.ArtifactRef,
        n5: NativeSourceReentryN5Completed,
        value: NativeSourceReentryCycleCompleted,
    ) -> None:
        _verify_native_source_reentry_cycle(
            source_generation_run=self.closure.generation_run,
            prepared=prepared,
            n5_ref=n5_ref,
            n5=n5,
            value=value,
        )

    def complete_cycle(
        self,
        n5_ref: artifacts.ArtifactRef,
        receipt: AcquisitionOverlayReentryReceipt,
    ) -> artifacts.ArtifactRef:
        """Select actual returned ports before the final existing receipt publisher."""
        cut, selected = self._start_transition(
            "cycle_completed", "prepared", "n5_completed", "tail_claimed"
        )
        prepared, n5 = selected["prepared"], selected["n5_completed"]
        if (
            prepared is None
            or type(prepared[1]) is not NativeSourceReentryPrepared
            or n5 is None
            or type(n5[1]) is not NativeSourceReentryN5Completed
            or artifacts.artifact_ref_identity_key(n5[0])
            != artifacts.artifact_ref_identity_key(n5_ref)
        ):
            raise ValueError("native_reentry_n5_completion_not_established")
        claim = selected["tail_claimed"]
        if (
            claim is None
            or type(claim[1]) is not NativeSourceReentryClaim
            or artifacts.artifact_ref_identity_key(claim[1].predecessor_ref)
            != artifacts.artifact_ref_identity_key(n5_ref)
        ):
            raise ValueError("native_reentry_tail_claim_missing")
        value = NativeSourceReentryCycleCompleted(
            subject=cut.subject, n5_completed_ref=n5_ref, receipt=receipt
        )
        self._verify_cycle(prepared[1], n5_ref, n5[1], value)
        return self._publish(value, cut)
