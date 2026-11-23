"""Route acquisition research intents and replay a bounded local sampling design.

The acquisition-evaluation basis owns effective input comparison. Declared
intents confer no authority. The controlled replica verifier computes a
candidate-only result over a server-selected sampling plan and exact source
views that the acquisition owner has already admitted.
"""

from __future__ import annotations

import base64
import json
from fractions import Fraction
from hashlib import sha256
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.design_problem import DesignConstraint

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore, VerifiableArtifactReader
    from polisyos.runtime.quality.acquisition_executor import LiveSourceExecutionEvidence

type AcquisitionEvidenceTransitionKind = Literal[
    "model", "method", "constraint", "independent_replica"
]
type _Text = Annotated[str, Field(min_length=1)]
type _Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
type _DispatchStatus = Literal["verification_required", "not_supported"]
type _RouteKey = tuple[_Text, _Text, _Text, _Digest]
type _SampleBlock = Annotated[tuple[tuple[_Text, int], ...], Field(min_length=1, max_length=64)]

_MODEL_VERIFIER = (
    "polisyos.runtime.quality.acquisition_model_transition.resolve_candidate_model_revision"
)
_CONTROLLED_PRODUCER = ProducerInfo(
    component="polisyos.runtime.quality.acquisition_evidence_transition", version="1.0"
)
CONTROLLED_REPLICA_RESPONSE_HEADER = "X-PolicyOS-Controlled-Replica"
_CONTROLLED_CAPTURE_MAX_BYTES = 3_072


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AcquisitionEvidenceTransitionBasis(_Strict):
    """Declare exact selected dependency views for existing-owner replay.

    Full manifest selectors are required, but their presence does not prove
    that the artifacts exist, match the request, or establish a difference.
    Before N5 only the previous and prospective bases exist. The selected
    basis stays explicitly absent until the real execution emits it; the
    post-execution verifier must then reopen all three complete bases.
    """

    evaluation_decision_ref: ArtifactRef
    previous_basis_ref: ArtifactRef
    prospective_basis_ref: ArtifactRef
    selected_basis_ref: ArtifactRef | None = None
    selected_basis_status: Literal["not_established", "declared_for_replay"] = "not_established"

    @model_validator(mode="after")
    def _selected_views(self) -> AcquisitionEvidenceTransitionBasis:
        if (self.selected_basis_ref is None) != (self.selected_basis_status == "not_established"):
            raise ValueError("acquisition_transition_selected_basis_stage_mismatch")
        for name, kind in (
            ("evaluation_decision_ref", "runtime_quality.acquisition_evaluation_decision"),
            ("previous_basis_ref", "runtime_quality.acquisition_evaluation_basis"),
            ("prospective_basis_ref", "runtime_quality.acquisition_evaluation_basis"),
            ("selected_basis_ref", "runtime_quality.acquisition_evaluation_basis"),
        ):
            ref = getattr(self, name)
            if ref is None and name == "selected_basis_ref":
                continue
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("acquisition_transition_basis_selected_view_required")
        return self


class _Intent(_Strict):
    purpose: _Text
    dependency_basis: AcquisitionEvidenceTransitionBasis
    authority_purpose: Literal["candidate_transition_intent_only"] = (
        "candidate_transition_intent_only"
    )
    publication_authority: Literal[False] = False

    @field_validator("purpose")
    @classmethod
    def _declared_purpose(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("acquisition_transition_purpose_missing")
        return value


class AcquisitionModelTransitionIntent(_Intent):
    """Request the existing coefficient-only candidate model revision profile."""

    kind: Literal["model"] = "model"
    changed_field: Literal["outcome_per_target_unit"] = "outcome_per_target_unit"


class AcquisitionMethodTransitionIntent(_Intent):
    """Preserve a requested method change whose acquisition bridge is absent."""

    kind: Literal["method"] = "method"
    previous_method_fqn: _Text
    requested_method_fqn: _Text


class AcquisitionConstraintTransitionIntent(_Intent):
    """Preserve actual DesignProblem constraint declarations without admitting them."""

    kind: Literal["constraint"] = "constraint"
    previous_constraints: tuple[DesignConstraint, ...]
    requested_constraints: tuple[DesignConstraint, ...]


class DeclaredAcquisitionReplicaObservation(_Strict):
    """Keep one declared measurement/sample occurrence and its distinct time role.

    A seed, UUID, independence group, positive sample size, or equal scalar is
    not evidence of independent sampling. These fields remain caller-declared;
    no effective independent sample count is calculated from them.
    """

    observation_id: _Text
    measurement_id: _Text
    sample_id: _Text
    independence_group_id: _Text
    observed_at: AwareDatetime
    sample_size: int = Field(ge=1)
    seed: int = Field(ge=0)
    scalar_value: float = Field(allow_inf_nan=False)
    independence_basis_refs: tuple[ArtifactRef, ...] = ()
    independence_status: Literal["declared_not_verified"] = "declared_not_verified"


class AcquisitionIndependentReplicaTransitionIntent(_Intent):
    """Request a scientific sample or technical retry without asserting independence."""

    kind: Literal["independent_replica"] = "independent_replica"
    attempt_kind: Literal["new_scientific_sample", "technical_retry"]
    previous_observation: DeclaredAcquisitionReplicaObservation
    requested_observation: DeclaredAcquisitionReplicaObservation


class ControlledAcquisitionReplicaFrame(_Strict):
    """Two eligible blocks of measured local units at one declared frame time.

    The controlled source provisions each frame and a separate stream seed
    before observation selection. Blocks consist of stable unit keys and their
    exact integer measurements in the candidate variable's canonical units.
    """

    epoch_id: int = Field(ge=1)
    observed_at: AwareDatetime
    stream_seed: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocks: tuple[_SampleBlock, _SampleBlock]

    @model_validator(mode="after")
    def _fixed_sample_size(self) -> ControlledAcquisitionReplicaFrame:
        if len(self.blocks[0]) != len(self.blocks[1]):
            raise ValueError("controlled_replica_variable_frame_denominator")
        return self


class ControlledAcquisitionReplicaPlan(_Strict):
    """Preassigned controlled sampling design for one exact candidate refresh."""

    ARTIFACT_KIND: ClassVar[str] = "runtime_quality.controlled_acquisition_replica_plan"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "ControlledAcquisitionReplicaPlan"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    route_key: _RouteKey
    profile_selection_ref: _Digest
    canonical_variable_id: _Text
    target_slot_id: _Text
    canonical_unit: _Text
    frames: tuple[ControlledAcquisitionReplicaFrame, ControlledAcquisitionReplicaFrame]

    @model_validator(mode="after")
    def _separate_design(self) -> ControlledAcquisitionReplicaPlan:
        previous, selected = self.frames
        if (
            previous.epoch_id >= selected.epoch_id
            or previous.observed_at >= selected.observed_at
            or previous.stream_seed == selected.stream_seed
        ):
            raise ValueError("controlled_replica_frames_not_separate")
        unit_ids = [
            unit_id for frame in self.frames for block in frame.blocks for unit_id, _ in block
        ]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("controlled_replica_frame_membership_overlap")
        return self


class ControlledAcquisitionReplicaSource(_Strict):
    """Bind one controlled frame to an owner-reopened admitted occurrence."""

    route_key: _RouteKey
    profile_selection_ref: _Digest
    canonical_variable_id: _Text
    target_slot_id: _Text
    canonical_unit: _Text
    epoch_id: int = Field(ge=1)
    action_generation: int = Field(ge=1)
    growth_ref: ArtifactRef
    passport_ref: ArtifactRef
    raw_source_ref: ArtifactRef
    admitted_source_ref: ArtifactRef
    capture_ref: ArtifactRef
    scalar_value: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def _selected_source_views(self) -> ControlledAcquisitionReplicaSource:
        if self.admitted_source_ref.manifest_profile_sha256 is None or any(
            ref.manifest_profile_sha256 is None or ref.kind != kind
            for ref, kind in (
                (self.growth_ref, "runtime_quality.acquisition_world_growth_receipt"),
                (self.passport_ref, "epoch.acquisition_passport_snapshot"),
                (self.raw_source_ref, "fabric.acquisition.raw_evidence"),
                (self.capture_ref, ControlledAcquisitionReplicaCapture.ARTIFACT_KIND),
            )
        ):
            raise ValueError("controlled_replica_selected_view_required")
        return self


class ControlledAcquisitionReplicaSample(_Strict):
    """The actual selected members, measurement time, denominator and aggregate."""

    sample_id: _Digest
    observed_at: AwareDatetime
    members: _SampleBlock
    sample_size: int = Field(ge=1)
    scalar_value: float = Field(allow_inf_nan=False)

    @property
    def member_ids(self) -> tuple[str, ...]:
        """Return the stable identities of the selected local units."""
        return tuple(unit_id for unit_id, _ in self.members)


class ControlledAcquisitionReplicaCapture(_Strict):
    """An observed draw separately produced before the corresponding admission."""

    ARTIFACT_KIND: ClassVar[str] = "runtime_quality.controlled_acquisition_replica_capture"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "ControlledAcquisitionReplicaCapture"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    sampling_rule: Literal["controlled-separate-frame-block-draw/v1"] = (
        "controlled-separate-frame-block-draw/v1"
    )
    plan_ref: ArtifactRef
    epoch_id: int = Field(ge=1)
    sample: ControlledAcquisitionReplicaSample


class ControlledAcquisitionReplicaBinding(_Strict):
    """The server-selected local plan and actually emitted draw for one action."""

    plan_ref: ArtifactRef
    capture_ref: ArtifactRef

    @model_validator(mode="after")
    def _selected_captures(self) -> ControlledAcquisitionReplicaBinding:
        if any(
            ref.manifest_profile_sha256 is None or ref.kind != model.ARTIFACT_KIND
            for ref, model in (
                (self.plan_ref, ControlledAcquisitionReplicaPlan),
                (self.capture_ref, ControlledAcquisitionReplicaCapture),
            )
        ):
            raise ValueError("controlled_replica_selected_view_required")
        return self


class ControlledAcquisitionReplicaProof(_Strict):
    """Candidate-only proof of distinct samples under the bounded local design."""

    plan_ref: ArtifactRef
    previous_source: ControlledAcquisitionReplicaSource
    selected_source: ControlledAcquisitionReplicaSource
    previous_sample: ControlledAcquisitionReplicaSample
    selected_sample: ControlledAcquisitionReplicaSample
    predicate_provenance: Literal["recomputed"] = "recomputed"
    authority_purpose: Literal["controlled_local_sampling_only"] = "controlled_local_sampling_only"
    publication_authority: Literal[False] = False


def _draw_controlled_replica(
    plan_ref: ArtifactRef, plan: ControlledAcquisitionReplicaPlan, epoch_id: int
) -> ControlledAcquisitionReplicaCapture:
    frame = next((frame for frame in plan.frames if frame.epoch_id == epoch_id), None)
    if frame is None:
        raise ValueError("controlled_replica_frame_not_selected")
    # With two eligible blocks, a bit from each preassigned stream chooses one
    # whole block. Replay does not consult the retained scalar to choose members.
    block = frame.blocks[sha256(bytes.fromhex(frame.stream_seed)).digest()[0] & 1]
    return ControlledAcquisitionReplicaCapture(
        plan_ref=plan_ref,
        epoch_id=frame.epoch_id,
        sample=ControlledAcquisitionReplicaSample(
            sample_id="sha256:" + sha256(frame.model_dump_json().encode()).hexdigest(),
            observed_at=frame.observed_at,
            members=block,
            sample_size=len(block),
            scalar_value=float(Fraction(sum(value for _, value in block), len(block))),
        ),
    )


def _replica_artifact_options(
    model: type[ControlledAcquisitionReplicaPlan] | type[ControlledAcquisitionReplicaCapture],
    plan_ref: ArtifactRef | None = None,
) -> ArtifactWriteOptions:
    inputs = (
        [input_ref_from_artifact_ref(plan_ref, role="controlled_replica_plan")]
        if plan_ref is not None
        else []
    )
    return ArtifactWriteOptions(
        kind=model.ARTIFACT_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=model.ARTIFACT_SCHEMA_NAME, version=model.ARTIFACT_SCHEMA_VERSION),
        producer=_CONTROLLED_PRODUCER,
        inputs=inputs,
    )


def _read_controlled_replica_artifact[
    Record: (ControlledAcquisitionReplicaPlan, ControlledAcquisitionReplicaCapture)
](
    store: VerifiableArtifactReader,
    ref: ArtifactRef,
    model: type[Record],
    plan_ref: ArtifactRef | None = None,
) -> Record:
    if ref.manifest_profile_sha256 is None or not store.verify(ref).ok:
        raise ValueError("controlled_replica_selected_view_unverified")
    manifest = store.get_manifest(ref)
    options = _replica_artifact_options(model, plan_ref)
    if (
        manifest.producer != options.producer
        or manifest.inputs != options.inputs
        or manifest.media_type != options.media_type
    ):
        raise ValueError("controlled_replica_local_producer_mismatch")
    return validate_core_model_json_artifact(model, store, ref)


def persist_controlled_acquisition_replica_plan(
    store: ArtifactStore, plan: ControlledAcquisitionReplicaPlan
) -> ArtifactRef:
    """Provision the local source's declared plan as an exact selected CAS artifact."""
    return store.put_json(
        plan.model_dump(mode="json"),
        _replica_artifact_options(ControlledAcquisitionReplicaPlan),
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def capture_controlled_acquisition_replica(
    store: ArtifactStore, *, plan_ref: ArtifactRef, epoch_id: int
) -> tuple[ArtifactRef, ControlledAcquisitionReplicaSample]:
    """Draw and persist the local source's actual sample before serving its value."""
    plan = _read_controlled_replica_artifact(store, plan_ref, ControlledAcquisitionReplicaPlan)
    capture = _draw_controlled_replica(plan_ref, plan, epoch_id)
    ref = store.put_json(
        capture.model_dump(mode="json"),
        _replica_artifact_options(ControlledAcquisitionReplicaCapture, plan_ref),
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ref, capture.sample


def read_controlled_acquisition_replica_capture(
    store: VerifiableArtifactReader,
    *,
    plan_ref: ArtifactRef,
    capture_ref: ArtifactRef,
    epoch_id: int,
) -> tuple[ControlledAcquisitionReplicaPlan, ControlledAcquisitionReplicaSample]:
    """Reopen an independently provisioned plan and the actual selected draw."""
    plan = _read_controlled_replica_artifact(store, plan_ref, ControlledAcquisitionReplicaPlan)
    capture = _read_controlled_replica_artifact(
        store, capture_ref, ControlledAcquisitionReplicaCapture, plan_ref
    )
    if capture != _draw_controlled_replica(plan_ref, plan, epoch_id):
        raise ValueError("controlled_replica_capture_mismatch")
    return plan, capture.sample


def controlled_replica_response_header(
    store: VerifiableArtifactReader, capture_ref: ArtifactRef
) -> str:
    """Encode the selected local sample bytes for delivery by the controlled source."""
    if capture_ref.manifest_profile_sha256 is None:
        raise ValueError("controlled_replica_selected_view_required")
    capture_bytes = store.get_bytes(capture_ref)
    if len(capture_bytes) > _CONTROLLED_CAPTURE_MAX_BYTES:
        raise ValueError("controlled_replica_delivery_capture_too_large")
    # The full bytes distinguish the actual sample from a new header label
    # for an old sample. The prefix binds the exact selected CAS interpretation.
    return capture_ref.manifest_profile_sha256 + ":" + base64.b64encode(capture_bytes).decode(
        "ascii"
    )


def verify_controlled_acquisition_replica_delivery(
    store: VerifiableArtifactReader,
    *,
    binding: ControlledAcquisitionReplicaBinding,
    epoch_id: int,
    evidence: LiveSourceExecutionEvidence,
) -> ControlledAcquisitionReplicaPlan:
    """Verify actual sampled units and aggregate against the selected raw response."""
    from polisyos.fabric.data_plane import (
        resolve_journal_event_ref,
        resolve_live_transport_trace,
        resolve_raw_response_body,
    )

    plan, sample = read_controlled_acquisition_replica_capture(
        store, plan_ref=binding.plan_ref, capture_ref=binding.capture_ref, epoch_id=epoch_id
    )
    raw_ref = evidence.raw_artifact_ref
    if raw_ref is None or not store.verify(raw_ref).ok:
        raise ValueError("controlled_replica_delivery_source_unverified")
    raw_event_ref = evidence.raw_evidence_ref
    body = resolve_raw_response_body(raw_event_ref)
    if (
        resolve_live_transport_trace(raw_event_ref) != evidence.transport_trace
        or store.get_bytes(raw_ref) != body
        or "sha256:" + sha256(body).hexdigest() != evidence.raw_body_sha256
    ):
        raise ValueError("controlled_replica_delivery_source_mismatch")
    event = resolve_journal_event_ref(raw_event_ref)
    response = event.get("raw_response")
    if not isinstance(response, dict):
        raise ValueError("controlled_replica_delivery_source_mismatch")
    headers = response.get("response_headers")
    observed = (
        [
            value
            for key, value in headers.items()
            if key.casefold() == CONTROLLED_REPLICA_RESPONSE_HEADER.casefold()
        ]
        if isinstance(headers, dict)
        else []
    )
    if observed != [controlled_replica_response_header(store, binding.capture_ref)]:
        raise ValueError("controlled_replica_delivery_capture_mismatch")
    # Catalog verifies the scope and one-page normalization of these same
    # bytes. This profile additionally binds its single numeric row to the
    # delivered sample before materialization and again at historical replay.
    try:
        rows = json.loads(body)[1]
        value = rows[0]["value"] if isinstance(rows, list) and len(rows) == 1 else None
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("controlled_replica_delivery_observation_missing") from exc
    if type(value) not in {float, int} or value != sample.scalar_value:
        raise ValueError("controlled_replica_aggregate_mismatch")
    return plan


def resolve_controlled_acquisition_replica(
    *,
    store: VerifiableArtifactReader,
    plan_ref: ArtifactRef,
    previous_source: ControlledAcquisitionReplicaSource,
    selected_source: ControlledAcquisitionReplicaSource,
) -> ControlledAcquisitionReplicaProof:
    """Verify two actual emitted local samples against the exact admitted sources.

    The running acquisition owner supplies the configured plan and sources
    built from verified action/passport/occurrence joins. The equal scalar is
    a check on the selected blocks. Currentness, numerical reuse and external
    sampling independence are outside this bounded decision.
    """
    if (
        previous_source.action_generation >= selected_source.action_generation
        or previous_source.epoch_id >= selected_source.epoch_id
        or previous_source.growth_ref.artifact_id == selected_source.growth_ref.artifact_id
        or previous_source.passport_ref.artifact_id == selected_source.passport_ref.artifact_id
        or previous_source.scalar_value != selected_source.scalar_value
        or previous_source.capture_ref.artifact_id == selected_source.capture_ref.artifact_id
    ):
        raise ValueError("controlled_replica_admitted_source_mismatch")
    sources = previous_source, selected_source
    refs = (
        ref
        for source in sources
        for ref in (
            source.growth_ref,
            source.passport_ref,
            source.raw_source_ref,
            source.admitted_source_ref,
        )
    )
    if any(not store.verify(ref).ok for ref in refs):
        raise ValueError("controlled_replica_selected_view_unverified")
    samples: list[ControlledAcquisitionReplicaSample] = []
    for source in sources:
        plan, sample = read_controlled_acquisition_replica_capture(
            store, plan_ref=plan_ref, capture_ref=source.capture_ref, epoch_id=source.epoch_id
        )
        if (
            (
                source.route_key,
                source.profile_selection_ref,
                source.canonical_variable_id,
                source.target_slot_id,
                source.canonical_unit,
            )
            != (
                plan.route_key,
                plan.profile_selection_ref,
                plan.canonical_variable_id,
                plan.target_slot_id,
                plan.canonical_unit,
            )
        ):
            raise ValueError("controlled_replica_admitted_source_mismatch")
        if sample.scalar_value != source.scalar_value:
            raise ValueError("controlled_replica_aggregate_mismatch")
        samples.append(sample)
    return ControlledAcquisitionReplicaProof(
        plan_ref=plan_ref,
        previous_source=previous_source,
        selected_source=selected_source,
        previous_sample=samples[0],
        selected_sample=samples[1],
    )


def replay_controlled_acquisition_replica(
    proof: ControlledAcquisitionReplicaProof | None,
    *,
    store: VerifiableArtifactReader,
    plan_ref: ArtifactRef,
    previous_source: ControlledAcquisitionReplicaSource,
    selected_source: ControlledAcquisitionReplicaSource,
) -> ControlledAcquisitionReplicaProof:
    """Recompute the expected local samples and refuse missing or changed proof."""
    if proof is None:
        raise ValueError("controlled_replica_proof_missing")
    expected = resolve_controlled_acquisition_replica(
        store=store,
        plan_ref=plan_ref,
        previous_source=previous_source,
        selected_source=selected_source,
    )
    if proof != expected:
        raise ValueError("controlled_replica_replay_mismatch")
    return expected


type AcquisitionEvidenceTransitionIntent = Annotated[
    AcquisitionModelTransitionIntent
    | AcquisitionMethodTransitionIntent
    | AcquisitionConstraintTransitionIntent
    | AcquisitionIndependentReplicaTransitionIntent,
    Field(discriminator="kind"),
]


class AcquisitionEvidenceTransitionBudget(_Strict):
    """Profile upper bounds, not an action permit or grant of additional work."""

    acquisition_actions: int = Field(ge=0, le=1)
    n5_evaluations: int = Field(ge=0, le=1)
    new_empirical_samples: Literal[0] = 0


class AcquisitionEvidenceTransitionProfile(_Strict):
    """Name the finite producer/consumer chain or its explicit missing owner."""

    kind: AcquisitionEvidenceTransitionKind
    source: _Text
    producer_refs: tuple[str, ...]
    affected_effective_fields: tuple[str, ...]
    consumer_ref: str | None
    repeated_step_refs: tuple[str, ...]
    required_owner: _Text
    status: _DispatchStatus
    reason_code: _Text
    maximum_budget: AcquisitionEvidenceTransitionBudget
    execution_authority: Literal[False] = False


_ZERO_BUDGET = AcquisitionEvidenceTransitionBudget(acquisition_actions=0, n5_evaluations=0)
_PROFILES = (
    AcquisitionEvidenceTransitionProfile(
        kind="model",
        source="server-configured CandidateSimulationSyntheticModelDeclarationV1",
        producer_refs=(
            "cycle_substrate.ConfiguredCandidateSimulationContextAdmissionOwner.prepare_context_for_acquired_world",
            "generation_source.GenerationSourceRepository.persist_candidate_model_declaration",
            "generation_source.GenerationSourceRepository.persist_candidate_ncm_selected_view",
        ),
        affected_effective_fields=(
            "declared_model.outcome_per_target_unit",
            "selected_native_ncm",
            "actual_live_implementation.selected_engine_values.plan.ncm_spec",
        ),
        consumer_ref=_MODEL_VERIFIER,
        repeated_step_refs=(
            "acquisition_evaluation_dispatch.complete_positive_acquisition_admission",
            "acquisition_world_growth.AcquisitionWorldGrowthBridge.resume",
            "generation_cycle.JointSimulationPort.__call__",
        ),
        required_owner=_MODEL_VERIFIER,
        status="verification_required",
        reason_code="acquisition_model_transition_owner_verification_required",
        maximum_budget=AcquisitionEvidenceTransitionBudget(acquisition_actions=1, n5_evaluations=1),
    ),
    AcquisitionEvidenceTransitionProfile(
        kind="method",
        source="declared change to the selected N5 method",
        producer_refs=(),
        affected_effective_fields=("actual_live_implementation", "n5_execution_configuration"),
        consumer_ref=None,
        repeated_step_refs=(),
        required_owner="owner_not_established: acquisition method-change producer and consumer",
        status="not_supported",
        reason_code="acquisition_method_transition_not_supported",
        maximum_budget=_ZERO_BUDGET,
    ),
    AcquisitionEvidenceTransitionProfile(
        kind="constraint",
        source="design_problem.DesignProblem.constraints",
        producer_refs=(),
        affected_effective_fields=("design_problem.constraints",),
        consumer_ref=None,
        repeated_step_refs=(),
        required_owner="owner_not_established: acquisition constraint-change producer and consumer",
        status="not_supported",
        reason_code="acquisition_constraint_transition_not_supported",
        maximum_budget=_ZERO_BUDGET,
    ),
    AcquisitionEvidenceTransitionProfile(
        kind="independent_replica",
        source="declared measurement/sample occurrence, not admitted independent evidence",
        producer_refs=(),
        affected_effective_fields=(
            "controlled_observation",
            "n5_request_values",
            "n5_execution_configuration",
        ),
        consumer_ref=None,
        repeated_step_refs=(),
        required_owner=(
            "owner_not_established: independent measurement admission and sample verifier"
        ),
        status="not_supported",
        reason_code="acquisition_independent_replica_transition_not_supported",
        maximum_budget=_ZERO_BUDGET,
    ),
)


class AcquisitionEvidenceTransitionDispatch(_Strict):
    """Carry a declared intent and routing result, never a successful evaluation."""

    intent: AcquisitionEvidenceTransitionIntent
    profile: AcquisitionEvidenceTransitionProfile
    replica_request_relation: (
        Literal["technical_retry", "same_declared_sample", "distinct_declared_sample"] | None
    ) = None
    predicate_provenance: Literal["not_established"] = "not_established"
    independence_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_transition_intent_only"] = (
        "candidate_transition_intent_only"
    )
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _declared_route(self) -> AcquisitionEvidenceTransitionDispatch:
        expected = next(row for row in _PROFILES if row.kind == self.intent.kind)
        if self.profile != expected:
            raise ValueError("acquisition_transition_dispatch_profile_mismatch")
        if (self.intent.kind == "independent_replica") != (
            self.replica_request_relation is not None
        ):
            raise ValueError("acquisition_transition_replica_relation_mismatch")
        return self

    @property
    def status(self) -> _DispatchStatus:
        """Return routing support without implying verifier success."""
        return self.profile.status


def acquisition_evidence_transition_profiles() -> tuple[AcquisitionEvidenceTransitionProfile, ...]:
    """Return all four bounded transition profiles, including unavailable chains.

    Returns:
        The immutable finite table. Unsupported rows have no execution chain
        and a zero budget; the model row requires the existing real verifier.
    """
    return _PROFILES


def dispatch_acquisition_evidence_transition(
    intent: AcquisitionEvidenceTransitionIntent,
) -> AcquisitionEvidenceTransitionDispatch:
    """Route a strict declared intent without executing or verifying any work.

    Args:
        intent: One typed request with declared purpose and full dependency views.

    Returns:
        The complete preserved intent and a bounded verification-required or
        not-supported profile. No result is a reuse decision or authorization.

    Raises:
        TypeError: The request is not one of the four exact typed intents.
        ValueError: A request bypassed normal model validation.
    """
    if type(intent) not in (
        AcquisitionModelTransitionIntent,
        AcquisitionMethodTransitionIntent,
        AcquisitionConstraintTransitionIntent,
        AcquisitionIndependentReplicaTransitionIntent,
    ):
        raise TypeError("acquisition_evidence_transition_intent_untyped")
    payload = intent.model_dump(mode="python")
    # model_copy/model_construct can bypass extra='forbid'; preserve unexpected
    # supplied keys for rejection rather than silently dropping a proof claim.
    payload.update(
        {key: value for key, value in vars(intent).items() if key not in type(intent).model_fields}
    )
    declared = type(intent).model_validate(payload, strict=True)
    profile = next(row for row in _PROFILES if row.kind == declared.kind)
    relation: (
        Literal["technical_retry", "same_declared_sample", "distinct_declared_sample"] | None
    ) = None
    if type(declared) is AcquisitionIndependentReplicaTransitionIntent:
        if declared.attempt_kind == "technical_retry":
            relation = "technical_retry"
        elif (
            declared.previous_observation.measurement_id,
            declared.previous_observation.sample_id,
        ) == (
            declared.requested_observation.measurement_id,
            declared.requested_observation.sample_id,
        ):
            relation = "same_declared_sample"
        else:
            relation = "distinct_declared_sample"
    return AcquisitionEvidenceTransitionDispatch(
        intent=declared, profile=profile, replica_request_relation=relation
    )
