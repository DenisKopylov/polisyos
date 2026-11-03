"""Declare bounded acquisition research transitions without certifying them.

The existing acquisition-evaluation basis owns effective input comparison.
``acquisition_model_transition.resolve_candidate_model_revision`` is the only
supported verifier here; its real selected-owner replay remains mandatory.
This pure routing helper performs no acquisition, N5 execution, admission,
independence verification, or authority promotion. It extends those canonical
owners rather than adding another execution or evidence engine.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality.design_problem import DesignConstraint

type AcquisitionEvidenceTransitionKind = Literal[
    "model", "method", "constraint", "independent_replica"
]
type _Text = Annotated[str, Field(min_length=1)]
type _DispatchStatus = Literal["verification_required", "not_supported"]

_MODEL_VERIFIER = (
    "polisyos.runtime.quality.acquisition_model_transition.resolve_candidate_model_revision"
)


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
