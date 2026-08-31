"""Promotion-independent attempted-evaluation safety contracts and procedures.

The module owns only safety admission.  It contains no evaluation callback,
scheduler, transport, persistence adapter, or institutional appointment.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
from pydantic_core import to_jsonable_python

from polisyos.core import components as core_components  # noqa: TC001
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    Digest,
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvalSafetyVerifierPort,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    EvaluationMode,
    EvaluationModeResolution,
    NamespacedEvalSafetyId,
    PredicateProvenance,
    _ProducedEvalSafetyConsumerAdmissionReceipt,
    evaluation_execution_context_hash,
    evaluation_safety_consumer_admission_is_verified,
    recompute_attempt_class,
)
from polisyos.runtime.quality.evaluation_modes import (
    resolve_evaluation_mode,
)

if TYPE_CHECKING:
    from polisyos.core import contracts as core_contracts
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSummary,
        PromotionPortObservation,
        ValueGateReceipt,
    )
    from polisyos.runtime.quality.open_world_risk import OpenWorldRiskArtifactResolver
    from polisyos.runtime.quality.semantic_epoch import (
        SemanticFacetDenominatorReceipt,
        SemanticFacetRegistry,
    )

AuthorityAttestationRole = Literal[
    "producer_statement",
    "independent_verification",
]
AuthoritySubjectPurpose = Literal[
    "attempted_evaluation_mode_basis",
    "certificate_revision_issue",
    "certificate_revision_supersede",
    "certificate_revision_revoke",
]

_BLOCKER_PREFIX = "polisyos.eval_safety"
_PRODUCER_TOKEN = object()


def _blocker(name: str) -> str:
    return f"{_BLOCKER_PREFIX}.{name}@1.0.0"


def _content_hash(
    value: BaseModel | dict[str, object],
    *,
    exclude: set[str] | None = None,
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude=exclude or set())
    else:
        payload = to_jsonable_python(value)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _identity(ref: ArtifactRef) -> tuple[str, str]:
    return (ref.artifact_id, ref.content_hash)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class _ProducerOwned:
    """Private capability bound to the exact canonical public bytes."""

    _producer_token: object | None = PrivateAttr(default=None)
    _producer_fingerprint: str | None = PrivateAttr(default=None)


def _mark_produced(value: _ProducerOwned) -> None:
    value._producer_token = _PRODUCER_TOKEN
    value._producer_fingerprint = _content_hash(value)


def _is_produced(value: object, expected_type: type[object]) -> bool:
    return (
        type(value) is expected_type
        and getattr(value, "_producer_token", None) is _PRODUCER_TOKEN
        and getattr(value, "_producer_fingerprint", None) == _content_hash(value)
    )


class EvalSafetyFacetValueRequirement(_FrozenModel):
    """Require one exact value from the complete semantic-facet denominator."""

    facet_id: NamespacedEvalSafetyId
    source_binding_ref: ArtifactRef
    expected_semantic_value_hash: Digest


class EvalSafetyAllApplicability(_FrozenModel):
    """Universal applicability reserved for independently verified mode bases."""

    kind: Literal["all"] = "all"


class EvalSafetyFacetApplicability(_FrozenModel):
    """Conjunctive applicability over an existing semantic-facet denominator."""

    kind: Literal["semantic_facet_all_of"] = "semantic_facet_all_of"
    semantic_facet_registry_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    all_of: tuple[EvalSafetyFacetValueRequirement, ...] = Field(min_length=1)


EvalSafetyApplicabilityScope = Annotated[
    EvalSafetyAllApplicability | EvalSafetyFacetApplicability,
    Field(discriminator="kind"),
]


class EvalSafetyRequirement(_FrozenModel):
    """Open, namespaced safety requirement supplied by a verified basis or pack."""

    requirement_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    authority_purpose: Literal["attempted_evaluation_safety"]
    applicability_scope: EvalSafetyApplicabilityScope
    warning_expires_after: timedelta | None


class EvalSafetyModeProfile(_FrozenModel):
    """Generic all-of requirement profile for one canonical mode."""

    mode: EvaluationMode
    all_of: tuple[EvalSafetyRequirement, ...]

    @model_validator(mode="after")
    def _unique_requirements(self) -> Self:
        ids = tuple(row.requirement_id for row in self.all_of)
        if len(ids) != len(set(ids)):
            raise ValueError("eval_safety_profile_requirement_duplicate")
        return self


class EvalSafetyModeBasis(_FrozenModel):
    """Content-addressed ratified minimum profiles, not engine conditionals."""

    schema_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    profiles: tuple[EvalSafetyModeProfile, ...]
    producer_authority_ref: ArtifactRef
    verifier_receipt_ref: ArtifactRef
    valid_from: datetime
    valid_until: datetime | None
    content_hash: Digest

    @classmethod
    def build(cls, **values: object) -> EvalSafetyModeBasis:
        """Build a basis with a recomputed canonical content hash."""

        return cls(**values, content_hash=_content_hash(values))

    @model_validator(mode="after")
    def _verify_basis(self) -> Self:
        modes = tuple(profile.mode for profile in self.profiles)
        if len(modes) != len(set(modes)):
            raise ValueError("eval_safety_mode_profile_duplicate")
        if any(
            not isinstance(requirement.applicability_scope, EvalSafetyAllApplicability)
            for profile in self.profiles
            for requirement in profile.all_of
        ):
            raise ValueError("eval_safety_basis_applicability_not_universal")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("eval_safety_mode_basis_time_invalid")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_mode_basis_content_hash_mismatch")
        return self


class _ProducedEvalSafetyModeBasis(_ProducerOwned, EvalSafetyModeBasis):
    """Mode basis admitted only through independent authority resolution."""


class EvalSafetyAuthorityResolution(_FrozenModel):
    """Typed resolution of one authority-bearing artifact reference."""

    status: Literal["verified", "blocked"]
    artifact_ref: ArtifactRef
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    resolved_at: datetime
    attestation_role: AuthorityAttestationRole | None = None
    subject_refs: tuple[ArtifactRef, ...] = ()
    subject_schema_version: str | None = None
    subject_rule_version: str | None = None
    subject_purpose: AuthoritySubjectPurpose | None = None
    subject_effective_at: datetime | None = None
    subject_valid_until: datetime | None = None
    attesting_component_id: core_components.ComponentId | None = None

    @model_validator(mode="after")
    def _verify_resolution_shape(self) -> Self:
        trusted = bool(self.predicate_provenance) and all(
            row in {"recomputed", "independently_reconciled"}
            for row in self.predicate_provenance
        )
        verified_shape = bool(
            not self.blocker_codes
            and trusted
            and self.attestation_role is not None
            and self.subject_refs
            and self.subject_schema_version
            and self.subject_purpose is not None
            and self.subject_effective_at is not None
            and self.attesting_component_id is not None
        )
        if (self.status == "verified") is not verified_shape:
            raise ValueError("eval_safety_authority_resolution_incoherent")
        return self


class EvalSafetyAuthorityResolver(Protocol):
    """Resolve and verify a content-addressed authority artifact."""

    def resolve(self, artifact_ref: ArtifactRef) -> EvalSafetyAuthorityResolution:
        """Return an exact resolution for ``artifact_ref``."""


def verify_evaluation_safety_mode_basis(
    *,
    basis_ref: ArtifactRef,
    basis: EvalSafetyModeBasis,
    authority_resolver: EvalSafetyAuthorityResolver,
    verified_at: datetime,
) -> EvalSafetyModeBasis | None:
    """Admit a mode basis only after both authority artifacts verify exactly."""

    if basis_ref.content_hash != basis.content_hash or not (
        basis.valid_from <= verified_at
        and (basis.valid_until is None or verified_at < basis.valid_until)
    ):
        return None
    attestation_refs = (basis.producer_authority_ref, basis.verifier_receipt_ref)
    if len({_identity(basis_ref), *map(_identity, attestation_refs)}) != 3:
        return None
    resolutions: list[EvalSafetyAuthorityResolution] = []
    for artifact_ref, role in zip(
        attestation_refs,
        ("producer_statement", "independent_verification"),
        strict=True,
    ):
        resolution = authority_resolver.resolve(artifact_ref)
        if (
            resolution.status != "verified"
            or resolution.artifact_ref != artifact_ref
            or resolution.attestation_role != role
            or resolution.subject_refs != (basis_ref,)
            or resolution.subject_schema_version != basis.schema_version
            or resolution.subject_rule_version != basis.rule_version
            or resolution.subject_purpose != "attempted_evaluation_mode_basis"
            or resolution.subject_effective_at != basis.valid_from
            or resolution.subject_valid_until != basis.valid_until
            or resolution.resolved_at > verified_at
        ):
            return None
        resolutions.append(resolution)
    if resolutions[0].attesting_component_id == resolutions[1].attesting_component_id:
        return None
    produced = _ProducedEvalSafetyModeBasis.model_validate(basis.model_dump(mode="python"))
    _mark_produced(produced)
    return produced


class EvalSafetyVerifierAppointment(_FrozenModel):
    """Verified appointment of an independent evidence verifier."""

    appointment_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    verifier_component_id: core_components.ComponentId
    component_discovery_manifest_ref: ArtifactRef
    appointing_authority_ref: ArtifactRef
    appointment_verification_receipt_ref: ArtifactRef
    valid_from: datetime
    valid_until: datetime | None

    @model_validator(mode="after")
    def _verify_appointment_time(self) -> Self:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("eval_safety_verifier_appointment_time_invalid")
        return self


class DomainEvalSafetyPack(_FrozenModel):
    """Strict domain-owned extension of a ratified safety mode basis."""

    schema_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    pack_component_id: core_components.ComponentId
    source_pack_ref: ArtifactRef
    mode_basis_ref: ArtifactRef
    semantic_facet_registry_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    verifier_appointment_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    profiles: tuple[EvalSafetyModeProfile, ...] = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime | None
    content_hash: Digest

    @classmethod
    def build(cls, **values: object) -> DomainEvalSafetyPack:
        """Build a domain pack with its content hash recomputed."""

        return cls(**values, content_hash=_content_hash(values))

    @model_validator(mode="after")
    def _verify_pack(self) -> Self:
        modes = tuple(profile.mode for profile in self.profiles)
        if len(modes) != len(set(modes)):
            raise ValueError("eval_safety_mode_profile_duplicate")
        if any(not profile.all_of for profile in self.profiles):
            raise ValueError("eval_safety_mode_profile_empty")
        if any(
            not isinstance(requirement.applicability_scope, EvalSafetyFacetApplicability)
            for profile in self.profiles
            for requirement in profile.all_of
        ):
            raise ValueError("eval_safety_domain_pack_universal_applicability_forbidden")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("eval_safety_domain_pack_time_invalid")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_domain_pack_content_hash_mismatch")
        return self


class EvalSafetyPackAdmissionReceipt(_FrozenModel):
    """Pure admission result for a resolved mode basis and domain pack."""

    pack_ref: ArtifactRef
    mode_basis_ref: ArtifactRef
    status: Literal["admitted", "refused"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    resolved_appointment_refs: tuple[ArtifactRef, ...]
    effective_profile: EvalSafetyModeProfile | None
    admitted_at: datetime
    content_hash: Digest

    @classmethod
    def admitted(
        cls,
        *,
        pack_ref: ArtifactRef,
        mode_basis_ref: ArtifactRef,
        resolved_appointment_refs: tuple[ArtifactRef, ...],
        effective_profile: EvalSafetyModeProfile,
        admitted_at: datetime,
    ) -> EvalSafetyPackAdmissionReceipt:
        """Build a positive receipt from independently resolved appointments."""

        values = {
            "pack_ref": pack_ref,
            "mode_basis_ref": mode_basis_ref,
            "status": "admitted",
            "blocker_codes": (),
            "resolved_appointment_refs": resolved_appointment_refs,
            "effective_profile": effective_profile,
            "admitted_at": admitted_at,
        }
        return cls(**values, content_hash=_content_hash(values))

    @classmethod
    def refused(
        cls,
        *,
        pack_ref: ArtifactRef,
        mode_basis_ref: ArtifactRef,
        blocker_codes: tuple[str, ...],
        admitted_at: datetime,
    ) -> EvalSafetyPackAdmissionReceipt:
        """Build a typed refusal without inventing an appointment."""

        values = {
            "pack_ref": pack_ref,
            "mode_basis_ref": mode_basis_ref,
            "status": "refused",
            "blocker_codes": blocker_codes,
            "resolved_appointment_refs": (),
            "effective_profile": None,
            "admitted_at": admitted_at,
        }
        return cls(**values, content_hash=_content_hash(values))

    @model_validator(mode="after")
    def _verify_receipt(self) -> Self:
        if (self.status == "admitted") == bool(self.blocker_codes):
            raise ValueError("eval_safety_pack_admission_status_incoherent")
        if self.status == "admitted" and not self.resolved_appointment_refs:
            raise ValueError("eval_safety_pack_appointment_missing")
        if (self.status == "admitted") != (self.effective_profile is not None):
            raise ValueError("eval_safety_pack_effective_profile_incoherent")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_pack_admission_hash_mismatch")
        return self


class _ProducedEvalSafetyPackAdmissionReceipt(_ProducerOwned, EvalSafetyPackAdmissionReceipt):
    """Owner-produced positive pack admission; public base DTOs carry no authority."""


class EvaluationAttemptIntake(_FrozenModel):
    """Audit-safe envelope retained even when strict parsing fails."""

    attempt_id: str = Field(min_length=1)
    evaluator_owner_id: core_components.ComponentId
    design_problem_ref: Digest
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    requested_mode_token: str | None
    mode_resolution: EvaluationModeResolution
    domain_hint: str | None
    domain_pack_ref: ArtifactRef | None
    target_population_scope_ref: ArtifactRef
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evaluation_input_provenance: tuple[EvaluationInputProvenance, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    requested_at: datetime
    intended_start_at: datetime
    requested_rule_version: str | None
    external_executor_identity_ref: ArtifactRef | None


class EvaluationAttemptRequest(_FrozenModel):
    """Canonical non-simulation request after strict intake resolution."""

    intake_ref: ArtifactRef
    attempt_id: str = Field(min_length=1)
    evaluator_owner_id: core_components.ComponentId
    design_problem_ref: Digest
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    evaluation_mode: EvaluationMode
    domain_pack_ref: ArtifactRef
    semantic_facet_denominator_receipt_ref: ArtifactRef
    target_population_scope_ref: ArtifactRef
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evaluation_input_provenance: tuple[EvaluationInputProvenance, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    requested_at: datetime
    intended_start_at: datetime
    rule_version: str = Field(min_length=1)
    external_executor_identity_ref: ArtifactRef | None


class EvalSafetyRequirementResult(_FrozenModel):
    """One independently verified, attempt-bound requirement outcome."""

    requirement_id: NamespacedEvalSafetyId
    evidence_contract_id: NamespacedEvalSafetyId
    request_ref: ArtifactRef
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    evaluation_mode: EvaluationMode
    target_population_scope_ref: ArtifactRef
    rule_version: str
    intended_start_at: datetime
    evidence_ref: ArtifactRef
    evidence_producer_component_id: core_components.ComponentId
    verifier_component_id: core_components.ComponentId
    verification_receipt_ref: ArtifactRef
    status: Literal["passed", "blocked"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    evaluated_at: datetime
    valid_until: datetime | None
    content_hash: str

    @classmethod
    def build(cls, **values: object) -> EvalSafetyRequirementResult:
        """Build a requirement result with a recomputed content hash."""

        return cls(**values, content_hash=_content_hash(values))

    @model_validator(mode="after")
    def _verify_result(self) -> Self:
        if self.evidence_producer_component_id == self.verifier_component_id:
            raise ValueError("eval_safety_evidence_self_verified")
        if (self.status == "passed") == bool(self.blocker_codes):
            raise ValueError("eval_safety_requirement_status_incoherent")
        if self.status == "passed" and (
            not self.predicate_provenance
            or any(
                row not in {"recomputed", "independently_reconciled"}
                for row in self.predicate_provenance
            )
        ):
            raise ValueError("eval_safety_requirement_provenance_unverified")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_requirement_content_hash_mismatch")
        return self


class _ProducedEvalSafetyRequirementResult(_ProducerOwned, EvalSafetyRequirementResult):
    """Owner-produced verifier result; identical public DTO markers are insufficient."""


class EvaluationSafetyDecisionCore(_FrozenModel):
    """Promotion-free safety decision frozen before optional classification."""

    intake_ref: ArtifactRef
    request_ref: ArtifactRef | None
    evaluator_owner_id: core_components.ComponentId
    requested_mode_token: str | None
    evaluation_mode: EvaluationMode | None
    attempt_class: Literal["simulation", "non_simulation", "not_established"]
    attempt_class_provenance: PredicateProvenance
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evaluation_input_provenance: tuple[EvaluationInputProvenance, ...]
    status: Literal["passed", "blocked"]
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    requirement_results: tuple[EvalSafetyRequirementResult, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    evaluated_at: datetime
    valid_until: datetime | None
    certificate_eligible: bool
    safety_semantic_hash: Digest

    @model_validator(mode="after")
    def _verify_core(self) -> Self:
        if (self.status == "blocked") != bool(self.blocker_codes):
            raise ValueError("eval_safety_core_status_incoherent")
        expected_eligibility = self.status == "passed" and self.evaluation_mode != "simulate_only"
        if self.certificate_eligible is not expected_eligibility:
            raise ValueError("eval_safety_core_certificate_eligibility_incoherent")
        if self.attempt_class == "not_established":
            if self.attempt_class_provenance != "not_established":
                raise ValueError("eval_safety_core_attempt_class_provenance_incoherent")
        elif self.attempt_class_provenance != "recomputed":
            raise ValueError("eval_safety_core_attempt_class_provenance_incoherent")
        if self.safety_semantic_hash != _content_hash(
            self, exclude={"safety_semantic_hash"}
        ):
            raise ValueError("eval_safety_core_semantic_hash_mismatch")
        return self


class _ProducedEvaluationSafetyDecisionCore(_ProducerOwned, EvaluationSafetyDecisionCore):
    """Owner-produced core; identical public DTO markers carry no authority."""


class EvalSafetyNearMissClassificationOffer(_FrozenModel):
    """Post-core offer binding every canonical N9 replay dependency."""

    promotion_receipt_ref: ArtifactRef
    canonical_promotion_input_ref: ArtifactRef
    design_problem_binding_ref: ArtifactRef
    value_receipt_ref: ArtifactRef
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    promotion_rule_version: str
    open_world_resolver_basis_ref: ArtifactRef
    epoch_resolver_basis_ref: ArtifactRef
    safety_semantic_hash: Digest
    offered_at: datetime
    content_hash: Digest

    @model_validator(mode="after")
    def _verify_offer_hash(self) -> Self:
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_classification_offer_hash_mismatch")
        return self


@dataclass(frozen=True, init=False)
class VerifiedNearMissClassification:
    """Opaque result emitted only by canonical post-core verification."""

    offer_ref: ArtifactRef
    validation_basis_ref: ArtifactRef
    promotion_safe_facet: bool
    safety_semantic_hash: Digest
    _producer_token: object | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _producer_fingerprint: str | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )


def _classification_fingerprint(value: VerifiedNearMissClassification) -> str:
    return _content_hash(
        {
            "offer_ref": value.offer_ref,
            "validation_basis_ref": value.validation_basis_ref,
            "promotion_safe_facet": value.promotion_safe_facet,
            "safety_semantic_hash": value.safety_semantic_hash,
        }
    )


def _classification_is_produced(
    value: object,
    core: EvaluationSafetyDecisionCore,
) -> bool:
    if not isinstance(value, VerifiedNearMissClassification):
        return False
    try:
        return bool(
            value._producer_token is _PRODUCER_TOKEN
            and value._producer_fingerprint == _classification_fingerprint(value)
            and value.safety_semantic_hash == core.safety_semantic_hash
        )
    except AttributeError:
        return False


class EvaluationSafetyDecisionEvent(_FrozenModel):
    """Decision event whose optional classification cannot change its core ID."""

    decision_id: str
    safety: EvaluationSafetyDecisionCore
    classification_offer_ref: ArtifactRef | None
    promotion_validation_basis_ref: ArtifactRef | None
    promotion_safe_facet: bool | None
    near_miss: bool
    content_hash: Digest

    @model_validator(mode="after")
    def _verify_event(self) -> Self:
        if self.decision_id != evaluation_safety_decision_id(self.safety):
            raise ValueError("eval_safety_decision_id_mismatch")
        if self.near_miss is not (
            self.safety.status == "blocked" and self.promotion_safe_facet is True
        ):
            raise ValueError("eval_safety_near_miss_incoherent")
        absent = (
            self.classification_offer_ref is None
            and self.promotion_validation_basis_ref is None
            and self.promotion_safe_facet is None
        )
        verified_classification = (
            self.classification_offer_ref is not None
            and self.promotion_validation_basis_ref is not None
            and self.promotion_safe_facet is not None
        )
        if not (absent or verified_classification):
            raise ValueError("eval_safety_classification_binding_incoherent")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_decision_event_hash_mismatch")
        return self


class _ProducedEvaluationSafetyDecisionEvent(_ProducerOwned, EvaluationSafetyDecisionEvent):
    """Owner-produced event that preserves the frozen core byte-for-byte."""


class EvalSafetyCertificate(_FrozenModel):
    """Purpose-bound certificate for one passed non-simulation attempt."""

    decision_ref: ArtifactRef
    request_ref: ArtifactRef
    evaluator_owner_id: core_components.ComponentId
    evaluation_mode: EvaluationMode
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    domain_pack_ref: ArtifactRef
    target_population_scope_ref: ArtifactRef
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evaluation_input_provenance: tuple[EvaluationInputProvenance, ...]
    rule_version: str
    revision_lineage_id: str
    valid_from: datetime
    valid_until: datetime
    authoritative_for: Literal["attempted_evaluation_admission"]
    may_not_use_for: tuple[
        Literal[
            "promotion",
            "simulation_safety",
            "attempted_evaluation_occurred",
            "deployment_execution",
            "realized_effect",
            "implementation_status",
            "appeal_outcome",
        ],
        ...,
    ]
    content_hash: Digest

    @model_validator(mode="after")
    def _verify_certificate_hash(self) -> Self:
        denied = {
            "promotion",
            "simulation_safety",
            "attempted_evaluation_occurred",
            "deployment_execution",
            "realized_effect",
            "implementation_status",
            "appeal_outcome",
        }
        if set(self.may_not_use_for) != denied or len(self.may_not_use_for) != len(denied):
            raise ValueError("eval_safety_certificate_denied_use_set_incomplete")
        if self.valid_until <= self.valid_from:
            raise ValueError("eval_safety_certificate_time_invalid")
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_certificate_content_hash_mismatch")
        return self


class _ProducedEvalSafetyCertificate(_ProducerOwned, EvalSafetyCertificate):
    """Owner-produced certificate; public DTO construction is inspectable only."""


class EvalSafetyCertificateRevision(_FrozenModel):
    """Content-bound issue, supersede, or revoke node in a certificate lineage."""

    revision_id: str
    revision_lineage_id: str
    predecessor_ref: ArtifactRef | None
    action: Literal["issue", "supersede", "revoke"]
    certificate_ref: ArtifactRef
    verified_cause_ref: ArtifactRef
    effective_at: datetime
    predicate_provenance: PredicateProvenance
    content_hash: Digest

    @classmethod
    def issue(
        cls,
        *,
        revision_lineage_id: str,
        certificate_ref: ArtifactRef,
        verified_cause_ref: ArtifactRef,
        cause_resolver: EvalSafetyAuthorityResolver,
        effective_at: datetime,
    ) -> EvalSafetyCertificateRevision:
        """Create the unique issue head for a certificate lineage."""

        resolution = cause_resolver.resolve(verified_cause_ref)
        if not _revision_cause_resolution_matches(
            resolution=resolution,
            cause_ref=verified_cause_ref,
            subject_refs=(certificate_ref,),
            purpose="certificate_revision_issue",
            effective_at=effective_at,
        ):
            raise ValueError("eval_safety_revision_cause_unverified")
        values = {
            "revision_id": "eval-safety-revision:" + certificate_ref.content_hash,
            "revision_lineage_id": revision_lineage_id,
            "predecessor_ref": None,
            "action": "issue",
            "certificate_ref": certificate_ref,
            "verified_cause_ref": verified_cause_ref,
            "effective_at": effective_at,
            "predicate_provenance": "independently_reconciled",
        }
        return _produce_certificate_revision(values)

    @classmethod
    def transition(
        cls,
        *,
        revision_lineage_id: str,
        predecessor_ref: ArtifactRef,
        action: Literal["supersede", "revoke"],
        certificate_ref: ArtifactRef,
        verified_cause_ref: ArtifactRef,
        cause_resolver: EvalSafetyAuthorityResolver,
        effective_at: datetime,
    ) -> EvalSafetyCertificateRevision:
        """Create a content-bound successor revision."""

        resolution = cause_resolver.resolve(verified_cause_ref)
        if not _revision_cause_resolution_matches(
            resolution=resolution,
            cause_ref=verified_cause_ref,
            subject_refs=(predecessor_ref, certificate_ref),
            purpose=f"certificate_revision_{action}",
            effective_at=effective_at,
        ):
            raise ValueError("eval_safety_revision_cause_unverified")
        values = {
            "revision_id": (
                f"eval-safety-revision:{action}:"
                f"{hashlib.sha256((predecessor_ref.content_hash + certificate_ref.content_hash).encode()).hexdigest()}"  # noqa: E501
            ),
            "revision_lineage_id": revision_lineage_id,
            "predecessor_ref": predecessor_ref,
            "action": action,
            "certificate_ref": certificate_ref,
            "verified_cause_ref": verified_cause_ref,
            "effective_at": effective_at,
            "predicate_provenance": "independently_reconciled",
        }
        return _produce_certificate_revision(values)

    @model_validator(mode="after")
    def _verify_revision_hash(self) -> Self:
        if self.content_hash != _content_hash(self, exclude={"content_hash"}):
            raise ValueError("eval_safety_revision_content_hash_mismatch")
        if (self.action == "issue") != (self.predecessor_ref is None):
            raise ValueError("eval_safety_revision_predecessor_invalid")
        return self


class _ProducedEvalSafetyCertificateRevision(
    _ProducerOwned, EvalSafetyCertificateRevision
):
    """Owner-produced revision node; parsed public nodes carry no authority."""


def _revision_cause_resolution_matches(
    *,
    resolution: EvalSafetyAuthorityResolution,
    cause_ref: ArtifactRef,
    subject_refs: tuple[ArtifactRef, ...],
    purpose: Literal[
        "certificate_revision_issue",
        "certificate_revision_supersede",
        "certificate_revision_revoke",
    ],
    effective_at: datetime,
) -> bool:
    return bool(
        resolution.status == "verified"
        and resolution.artifact_ref == cause_ref
        and resolution.attestation_role == "independent_verification"
        and resolution.subject_refs == subject_refs
        and resolution.subject_schema_version
        == "polisyos.eval_safety.certificate_revision.v1"
        and resolution.subject_rule_version is None
        and resolution.subject_purpose == purpose
        and resolution.subject_effective_at == effective_at
        and resolution.subject_valid_until is None
        and resolution.resolved_at <= effective_at
        and _identity(cause_ref) not in {_identity(ref) for ref in subject_refs}
    )


def _produce_certificate_revision(
    values: dict[str, object],
) -> EvalSafetyCertificateRevision:
    result = _ProducedEvalSafetyCertificateRevision(
        **values, content_hash=_content_hash(values)
    )
    _mark_produced(result)
    return result


def reconcile_evaluation_safety_revisions(
    *,
    revisions: tuple[EvalSafetyCertificateRevision, ...],
    cause_resolver: EvalSafetyAuthorityResolver,
) -> tuple[EvalSafetyCertificateRevision, ...]:
    """Replay persisted public revision DTOs through the canonical producer."""

    remaining = list(revisions)
    produced_by_hash: dict[str, EvalSafetyCertificateRevision] = {}
    while remaining:
        progressed = False
        for raw in tuple(remaining):
            if raw.action == "issue":
                if raw.predecessor_ref is not None:
                    return ()
                rebuilt = EvalSafetyCertificateRevision.issue(
                    revision_lineage_id=raw.revision_lineage_id,
                    certificate_ref=raw.certificate_ref,
                    verified_cause_ref=raw.verified_cause_ref,
                    cause_resolver=cause_resolver,
                    effective_at=raw.effective_at,
                )
            else:
                predecessor = raw.predecessor_ref
                if predecessor is None:
                    return ()
                if predecessor.content_hash not in produced_by_hash:
                    continue
                rebuilt = EvalSafetyCertificateRevision.transition(
                    revision_lineage_id=raw.revision_lineage_id,
                    predecessor_ref=predecessor,
                    action=raw.action,
                    certificate_ref=raw.certificate_ref,
                    verified_cause_ref=raw.verified_cause_ref,
                    cause_resolver=cause_resolver,
                    effective_at=raw.effective_at,
                )
            if rebuilt.model_dump(mode="json") != raw.model_dump(mode="json"):
                return ()
            produced_by_hash[rebuilt.content_hash] = rebuilt
            remaining.remove(raw)
            progressed = True
        if not progressed:
            return ()
    return tuple(produced_by_hash[row.content_hash] for row in revisions)


class EvalSafetyCertificateRevisionNode(_FrozenModel):
    """One persisted revision artifact paired with its external CAS identity."""

    revision_ref: ArtifactRef
    revision: EvalSafetyCertificateRevision

    @model_validator(mode="after")
    def _bind_revision_ref(self) -> Self:
        if self.revision_ref.content_hash != self.revision.content_hash:
            raise ValueError("eval_safety_revision_ref_content_mismatch")
        return self


class EvalSafetyAppointmentResolution(_FrozenModel):
    """Resolution of one independently verified appointment artifact."""

    status: Literal["verified", "blocked"]
    appointment_ref: ArtifactRef
    appointment: EvalSafetyVerifierAppointment | None
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    predicate_provenance: tuple[PredicateProvenance, ...]
    verified_at: datetime

    @model_validator(mode="after")
    def _verify_resolution_shape(self) -> Self:
        verified_shape = self.appointment is not None and not self.blocker_codes
        if (self.status == "verified") is not verified_shape:
            raise ValueError("eval_safety_appointment_resolution_incoherent")
        return self


class EvalSafetyVerifierAppointmentResolver(Protocol):
    """Resolve appointment evidence without appointing an institution."""

    def resolve(self, appointment_ref: ArtifactRef) -> EvalSafetyAppointmentResolution:
        """Resolve and verify one appointment reference."""


class EvidenceVerifier(Protocol):
    """Independently verify evidence for one open contract ID."""

    @property
    def component_id(self) -> core_components.ComponentId:
        """Return the verifier component identity."""

    def verify(
        self,
        *,
        requirement: EvalSafetyRequirement,
        request: EvaluationAttemptRequest,
        request_ref: ArtifactRef,
        evidence_ref: ArtifactRef,
        appointment: EvalSafetyVerifierAppointment,
        evaluated_at: datetime,
    ) -> EvalSafetyRequirementResult:
        """Return a content-bound requirement result."""


class EvalSafetyVerifierRegistry(Protocol):
    """Resolve an evidence verifier by open namespaced contract ID."""

    def resolve(self, evidence_contract_id: str) -> EvidenceVerifier | None:
        """Return the registered verifier, or ``None`` fail-closed."""


def admit_domain_evaluation_safety_pack(
    *,
    pack_ref: ArtifactRef,
    pack: DomainEvalSafetyPack | None,
    request: EvaluationAttemptRequest,
    mode_basis_ref: ArtifactRef,
    mode_basis: EvalSafetyModeBasis | None,
    facet_registry: SemanticFacetRegistry | None,
    facet_denominator: SemanticFacetDenominatorReceipt | None,
    appointment_resolver: EvalSafetyVerifierAppointmentResolver,
    verifier_registry: EvalSafetyVerifierRegistry,
    admitted_at: datetime,
) -> EvalSafetyPackAdmissionReceipt:
    """Resolve, bind, and independently verify one generic domain safety pack."""

    blockers: list[str] = []
    resolved_refs: list[ArtifactRef] = []
    mode = request.evaluation_mode
    if pack is None:
        blockers.append(_blocker("domain_pack_missing"))
    elif (
        pack.content_hash != pack_ref.content_hash
        or pack_ref != request.domain_pack_ref
        or pack.rule_version != request.rule_version
        or pack.semantic_facet_denominator_receipt_ref
        != request.semantic_facet_denominator_receipt_ref
    ):
        blockers.append(_blocker("domain_pack_binding_mismatch"))
    if mode_basis is None:
        blockers.append(_blocker("mode_basis_missing"))
    elif not _is_produced(mode_basis, _ProducedEvalSafetyModeBasis):
        blockers.append(_blocker("mode_basis_unverified"))
    elif mode_basis.content_hash != mode_basis_ref.content_hash:
        blockers.append(_blocker("mode_basis_binding_mismatch"))
    elif mode_basis.rule_version != request.rule_version:
        blockers.append(_blocker("mode_basis_rule_mismatch"))
    if pack is not None and _identity(pack.mode_basis_ref) != _identity(mode_basis_ref):
        blockers.append(_blocker("mode_basis_binding_mismatch"))
    if facet_registry is None or facet_denominator is None:
        blockers.append(_blocker("semantic_facet_denominator_missing"))
    elif (
        facet_denominator.status != "resolved"
        or facet_denominator.predicate_class != "independently_reconciled"
        or facet_denominator.facet_registry_content_hash != facet_registry.registry_content_hash
    ):
        blockers.append(_blocker("semantic_facet_denominator_invalid"))
    elif pack is not None and (
        pack.semantic_facet_registry_ref.content_hash != facet_registry.registry_content_hash
        or pack.semantic_facet_denominator_receipt_ref.content_hash
        != facet_denominator.denominator_hash
    ):
        blockers.append(_blocker("semantic_facet_binding_mismatch"))

    basis_profile = None
    pack_profile = None
    effective_profile = None
    if mode_basis is not None:
        rows = tuple(row for row in mode_basis.profiles if row.mode == mode)
        if len(rows) == 1:
            basis_profile = rows[0]
        else:
            blockers.append(_blocker("mode_profile_missing"))
    if pack is not None:
        rows = tuple(row for row in pack.profiles if row.mode == mode)
        if len(rows) == 1:
            pack_profile = rows[0]
        else:
            blockers.append(_blocker("mode_profile_missing"))
    if basis_profile is not None and pack_profile is not None:
        basis_requirement_ids = {row.requirement_id for row in basis_profile.all_of}
        pack_requirement_ids = {row.requirement_id for row in pack_profile.all_of}
        if basis_requirement_ids.intersection(pack_requirement_ids):
            blockers.append(_blocker("profile_basis_invalid"))
        else:
            effective_profile = EvalSafetyModeProfile(
                mode=mode,
                all_of=basis_profile.all_of + pack_profile.all_of,
            )

    if pack_profile is not None and facet_registry is not None and facet_denominator is not None:
        registered = {row.facet_id: row for row in facet_registry.registrations}
        values = {row.facet_id: row for row in facet_denominator.values}
        for requirement in pack_profile.all_of:
            scope = requirement.applicability_scope
            if not isinstance(scope, EvalSafetyFacetApplicability):
                blockers.append(_blocker("domain_pack_applicability_invalid"))
                continue
            if (
                _identity(scope.semantic_facet_registry_ref)
                != _identity(pack.semantic_facet_registry_ref)  # type: ignore[union-attr]
                or _identity(scope.semantic_facet_denominator_receipt_ref)
                != _identity(pack.semantic_facet_denominator_receipt_ref)  # type: ignore[union-attr]
            ):
                blockers.append(_blocker("semantic_facet_binding_mismatch"))
            for expected in scope.all_of:
                actual = values.get(expected.facet_id)
                if expected.facet_id not in registered or actual is None:
                    blockers.append(_blocker("semantic_facet_unresolved"))
                elif (
                    actual.status != "resolved"
                    or actual.semantic_value_hash != expected.expected_semantic_value_hash
                    or actual.source_record_content_hash != expected.source_binding_ref.content_hash
                ):
                    blockers.append(_blocker("semantic_facet_value_mismatch"))

    appointments: dict[str, EvalSafetyVerifierAppointment] = {}
    if pack is not None:
        for appointment_ref in pack.verifier_appointment_refs:
            resolution = appointment_resolver.resolve(appointment_ref)
            appointment = resolution.appointment
            if (
                resolution.status != "verified"
                or appointment is None
                or resolution.appointment_ref != appointment_ref
                or not resolution.predicate_provenance
                or any(
                    row not in {"recomputed", "independently_reconciled"}
                    for row in resolution.predicate_provenance
                )
                or admitted_at < appointment.valid_from
                or (
                    appointment.valid_until is not None
                    and admitted_at >= appointment.valid_until
                )
            ):
                blockers.append(_blocker("verifier_unappointed"))
                continue
            if (
                appointment.verifier_component_id == pack.pack_component_id
                or _identity(appointment_ref)
                in {
                    _identity(appointment.appointing_authority_ref),
                    _identity(appointment.appointment_verification_receipt_ref),
                }
                or _identity(appointment.appointing_authority_ref)
                == _identity(appointment.appointment_verification_receipt_ref)
            ):
                blockers.append(_blocker("verifier_independence_invalid"))
                continue
            verifier = verifier_registry.resolve(appointment.evidence_contract_id)
            if verifier is None or verifier.component_id != appointment.verifier_component_id:
                blockers.append(_blocker("verifier_unresolved"))
                continue
            if appointment.evidence_contract_id in appointments:
                blockers.append(_blocker("verifier_appointment_duplicate"))
                continue
            appointments[appointment.evidence_contract_id] = appointment
            resolved_refs.append(appointment_ref)
    if effective_profile is not None:
        for requirement in effective_profile.all_of:
            if requirement.evidence_contract_id not in appointments:
                blockers.append(_blocker("verifier_unappointed"))

    if pack is not None and (
        admitted_at < pack.valid_from
        or (pack.valid_until is not None and admitted_at >= pack.valid_until)
    ):
        blockers.append(_blocker("domain_pack_stale"))
    if mode_basis is not None and (
        admitted_at < mode_basis.valid_from
        or (mode_basis.valid_until is not None and admitted_at >= mode_basis.valid_until)
    ):
        blockers.append(_blocker("mode_basis_stale"))

    unique = tuple(sorted(set(blockers)))
    if unique:
        return EvalSafetyPackAdmissionReceipt.refused(
            pack_ref=pack_ref,
            mode_basis_ref=mode_basis_ref,
            blocker_codes=unique,
            admitted_at=admitted_at,
        )
    produced = EvalSafetyPackAdmissionReceipt.admitted(
        pack_ref=pack_ref,
        mode_basis_ref=mode_basis_ref,
        resolved_appointment_refs=tuple(resolved_refs),
        effective_profile=effective_profile,  # type: ignore[arg-type]
        admitted_at=admitted_at,
    )
    result = _ProducedEvalSafetyPackAdmissionReceipt.model_validate(
        produced.model_dump(mode="python")
    )
    _mark_produced(result)
    return result


def verify_evaluation_safety_requirements(
    *,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef,
    admitted_pack: EvalSafetyPackAdmissionReceipt,
    evidence_by_contract: dict[str, ArtifactRef],
    appointment_resolver: EvalSafetyVerifierAppointmentResolver,
    verifier_registry: EvalSafetyVerifierRegistry,
    evaluated_at: datetime,
) -> tuple[EvalSafetyRequirementResult, ...]:
    """Invoke every appointed verifier and retain only fully bound positive results."""

    accepted: list[EvalSafetyRequirementResult] = []
    profile = admitted_pack.effective_profile
    if (
        admitted_pack.status != "admitted"
        or not _is_produced(
            admitted_pack, _ProducedEvalSafetyPackAdmissionReceipt
        )
        or profile is None
        or profile.mode != request.evaluation_mode
    ):
        return ()
    appointments: dict[str, EvalSafetyVerifierAppointment] = {}
    for appointment_ref in admitted_pack.resolved_appointment_refs:
        resolution = appointment_resolver.resolve(appointment_ref)
        if (
            resolution.status != "verified"
            or resolution.appointment is None
            or resolution.appointment_ref != appointment_ref
            or not resolution.predicate_provenance
            or any(
                row not in {"recomputed", "independently_reconciled"}
                for row in resolution.predicate_provenance
            )
        ):
            continue
        appointment = resolution.appointment
        if evaluated_at < appointment.valid_from or (
            appointment.valid_until is not None and evaluated_at >= appointment.valid_until
        ):
            continue
        if appointment.evidence_contract_id in appointments:
            continue
        appointments[appointment.evidence_contract_id] = appointment
    for requirement in profile.all_of:
        evidence_ref = evidence_by_contract.get(requirement.evidence_contract_id)
        appointment = appointments.get(requirement.evidence_contract_id)
        verifier = verifier_registry.resolve(requirement.evidence_contract_id)
        if evidence_ref is None or appointment is None or verifier is None:
            continue
        if verifier.component_id != appointment.verifier_component_id:
            continue
        result = verifier.verify(
            requirement=requirement,
            request=request,
            request_ref=request_ref,
            evidence_ref=evidence_ref,
            appointment=appointment,
            evaluated_at=evaluated_at,
        )
        if (
            result.verifier_component_id != verifier.component_id
            or result.evidence_ref != evidence_ref
            or not _result_matches_request(
                result, requirement, request, request_ref, evaluated_at
            )
        ):
            continue
        produced = _ProducedEvalSafetyRequirementResult.model_validate(
            result.model_dump(mode="python")
        )
        _mark_produced(produced)
        accepted.append(produced)
    return tuple(accepted)


class EvalSafetySurfaceDisposition(_FrozenModel):
    """One informational-only surface disposition."""

    surface: Literal["run", "artifact", "lineage", "dashboard"]
    purpose: Literal["runtime_closeout_authority", "dashboard_display"]
    status: Literal["allow"]
    authority_result: Literal["informational_projection_only"]
    consumed_boundary_id: str
    projection_scope: Literal["faithful_eval_safety_projection"]
    may_not_use_for: tuple[
        Literal["attempted_evaluation_admission", "promotion", "evaluation_execution"], ...
    ]


class EvalSafetyAuthoritySurfacePacket(_FrozenModel):
    """Exact existing-surface packet for an informational projection."""

    schema_version: Literal["policyos.runtime.eval_safety_surface_packet.v1"]
    boundary: AuthorityBoundary
    surfaces: dict[
        Literal["run", "artifact", "lineage", "dashboard"], EvalSafetySurfaceDisposition
    ]


@dataclass(frozen=True, slots=True)
class EvaluationSafetyArtifactIdentity:
    """Immutable identity for one persisted evaluation-safety artifact family."""

    key: str
    kind: str
    schema: str
    reader_contract: str
    evidence_class: Literal["authority_bearing", "diagnostic_supporting"]
    authority_role: Literal[
        "producer_authority", "projection_only", "not_authoritative"
    ]


def _evaluation_safety_artifact_identity(key: str) -> EvaluationSafetyArtifactIdentity:
    stem = f"policyos.runtime.eval_safety.{key}"
    authority_bearing = key in {
        "pack_admission",
        "decision",
        "certificate",
        "certificate_revision",
    }
    return EvaluationSafetyArtifactIdentity(
        key=key,
        kind=stem,
        schema=f"{stem}.v1",
        reader_contract=f"{stem}.reader",
        evidence_class=(
            "authority_bearing" if authority_bearing else "diagnostic_supporting"
        ),
        authority_role=(
            "projection_only"
            if key == "metrics_projection"
            else ("producer_authority" if authority_bearing else "not_authoritative")
        ),
    )


EVALUATION_SAFETY_ARTIFACT_IDENTITIES = MappingProxyType(
    {
        key: _evaluation_safety_artifact_identity(key)
        for key in (
            "pack_admission",
            "intake",
            "request",
            "classification_offer",
            "decision",
            "certificate",
            "certificate_revision",
            "metrics_projection",
        )
    }
)


@dataclass(frozen=True, slots=True)
class EvaluationSafetyProjectionReadIdentity:
    """Typed identity required by generic projection egress."""

    kind: str
    schema_name: str
    schema_version: Literal["1.0"]
    purpose: Literal["runtime_closeout_authority", "dashboard_display"]


def evaluation_safety_metrics_projection_identity(
    surface: Literal["run", "artifact", "lineage", "dashboard"],
) -> EvaluationSafetyProjectionReadIdentity:
    """Return the canonical metrics-projection identity for one read surface."""

    row = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["metrics_projection"]
    return EvaluationSafetyProjectionReadIdentity(
        kind=row.kind,
        schema_name=row.schema,
        schema_version="1.0",
        purpose=(
            "dashboard_display" if surface == "dashboard" else "runtime_closeout_authority"
        ),
    )


class EvalSafetyMetricsProjection(_FrozenModel):
    """Complete-denominator informational metrics projection contract."""

    attempt_disposition: Literal["passed", "blocked"]
    selected_decision_artifact_refs: tuple[ArtifactRef, ...]
    reconciled_decision_artifact_refs: tuple[ArtifactRef, ...]
    unreconciled_decision_artifact_refs: tuple[ArtifactRef, ...]
    conflicting_decision_artifact_refs: tuple[ArtifactRef, ...]
    denominator_decision_ids: tuple[str, ...]
    unsafe_attempt_blocked_count: int = Field(ge=0)
    near_miss_count: int = Field(ge=0)
    near_miss_classification_status: Literal["complete", "partial", "not_established"]
    unclassified_blocked_decision_ids: tuple[str, ...]
    reconciliation_status: Literal["complete", "not_established"]
    generated_at: datetime
    source_event_refs: tuple[ArtifactRef, ...]
    authority_boundary: AuthorityBoundary
    authority_surface_packet: EvalSafetyAuthoritySurfacePacket

    @model_validator(mode="after")
    def _reconciliation_status_matches_complete_selection(self) -> Self:
        selected = {_identity(ref) for ref in self.selected_decision_artifact_refs}
        reconciled = {_identity(ref) for ref in self.reconciled_decision_artifact_refs}
        unreconciled = {_identity(ref) for ref in self.unreconciled_decision_artifact_refs}
        conflicting = {_identity(ref) for ref in self.conflicting_decision_artifact_refs}
        complete = selected == reconciled and not unreconciled and not conflicting
        if (self.reconciliation_status == "complete") is not complete:
            raise ValueError("eval_safety_metrics_reconciliation_status_incoherent")
        if (unreconciled | conflicting) - selected:
            raise ValueError("eval_safety_metrics_findings_outside_selected_denominator")
        expected_surfaces = {"run", "artifact", "lineage", "dashboard"}
        if set(self.authority_surface_packet.surfaces) != expected_surfaces:
            raise ValueError("eval_safety_surface_set_incomplete")
        if self.authority_surface_packet.boundary != self.authority_boundary:
            raise ValueError("eval_safety_surface_boundary_mismatch")
        boundary_id = self.authority_boundary.boundary_id
        if boundary_id is None:
            raise ValueError("eval_safety_surface_boundary_id_missing")
        expected_denials = {
            "attempted_evaluation_admission",
            "promotion",
            "evaluation_execution",
        }
        for key, disposition in self.authority_surface_packet.surfaces.items():
            expected_purpose = (
                "dashboard_display" if key == "dashboard" else "runtime_closeout_authority"
            )
            if (
                disposition.surface != key
                or disposition.purpose != expected_purpose
                or disposition.consumed_boundary_id != boundary_id
                or set(disposition.may_not_use_for) != expected_denials
                or len(disposition.may_not_use_for) != len(expected_denials)
            ):
                raise ValueError("eval_safety_surface_disposition_invalid")
        return self


def decide_evaluation_safety_core(
    *,
    intake: EvaluationAttemptIntake,
    intake_ref: ArtifactRef,
    request: EvaluationAttemptRequest | None,
    request_ref: ArtifactRef | None,
    admitted_pack: EvalSafetyPackAdmissionReceipt | None,
    mode_basis: EvalSafetyModeBasis | None,
    requirement_results: tuple[EvalSafetyRequirementResult, ...],
    evaluated_at: datetime,
) -> EvaluationSafetyDecisionCore:
    """Compose one safety decision exclusively from safety-domain inputs."""

    blockers: list[str] = []
    verified_results = requirement_results
    attempt_class = recompute_attempt_class(
        intake.evaluation_input_refs, intake.evaluation_input_provenance
    )
    recomputed_mode = resolve_evaluation_mode(intake.requested_mode_token)
    mode = recomputed_mode.canonical_mode
    if intake.mode_resolution != recomputed_mode:
        blockers.append(_blocker("evaluation_mode_resolution_mismatch"))
    if recomputed_mode.status != "accepted" or mode is None:
        blockers.append(recomputed_mode.blocker_code or _blocker("evaluation_mode_invalid"))
    if attempt_class == "not_established":
        blockers.append(_blocker("attempt_class_not_established"))
    if mode == "simulate_only":
        if attempt_class != "simulation":
            blockers.append(_blocker("simulation_provenance_mismatch"))
    else:
        if request is None:
            blockers.append(_blocker("request_missing"))
        elif not _request_matches_intake(request, intake, intake_ref):
            blockers.append(_blocker("request_binding_mismatch"))
        if request is not None and request_ref is None:
            blockers.append(_blocker("request_ref_missing"))
        if admitted_pack is None:
            blockers.append(_blocker("domain_pack_missing"))
        elif (
            admitted_pack.status == "admitted"
            and not _is_produced(admitted_pack, _ProducedEvalSafetyPackAdmissionReceipt)
        ):
            blockers.append(_blocker("domain_pack_admission_unverified"))
        elif admitted_pack.status != "admitted":
            blockers.extend(admitted_pack.blocker_codes)
        elif request is not None and _identity(admitted_pack.pack_ref) != _identity(
            request.domain_pack_ref
        ):
            blockers.append(_blocker("domain_pack_binding_mismatch"))
        if mode_basis is None:
            blockers.append(_blocker("mode_basis_missing"))
        elif not _is_produced(mode_basis, _ProducedEvalSafetyModeBasis):
            blockers.append(_blocker("mode_basis_unverified"))
        elif request is not None:
            if any(
                not _is_produced(row, _ProducedEvalSafetyRequirementResult)
                for row in verified_results
            ):
                blockers.append(_blocker("requirement_result_set_unverified"))
            blockers.extend(
                _basis_and_result_blockers(
                    mode_basis,
                    admitted_pack.effective_profile if admitted_pack is not None else None,
                    request,
                    request_ref,
                    verified_results,
                    evaluated_at,
                )
            )
    blockers = sorted(set(blockers))
    status: Literal["passed", "blocked"] = "blocked" if blockers else "passed"
    valid_until_values = [row.valid_until for row in verified_results if row.valid_until]
    valid_until = min(valid_until_values) if valid_until_values else None
    payload: dict[str, object] = {
        "intake_ref": intake_ref,
        "request_ref": request_ref if request is not None else None,
        "evaluator_owner_id": intake.evaluator_owner_id,
        "requested_mode_token": intake.requested_mode_token,
        "evaluation_mode": mode,
        "attempt_class": attempt_class,
        "attempt_class_provenance": (
            "recomputed" if attempt_class != "not_established" else "not_established"
        ),
        "evaluation_input_refs": intake.evaluation_input_refs,
        "evaluation_input_provenance": intake.evaluation_input_provenance,
        "status": status,
        "blocker_codes": tuple(blockers),
        "requirement_results": verified_results,
        "predicate_provenance": (
            ("recomputed", "independently_reconciled")
            if status == "passed" and mode != "simulate_only"
            else ("recomputed",)
        ),
        "evaluated_at": evaluated_at,
        "valid_until": valid_until,
        "certificate_eligible": status == "passed" and mode != "simulate_only",
    }
    result = _ProducedEvaluationSafetyDecisionCore(
        **payload, safety_semantic_hash=_content_hash(payload)
    )
    _mark_produced(result)
    return result


def _request_matches_intake(
    request: EvaluationAttemptRequest,
    intake: EvaluationAttemptIntake,
    intake_ref: ArtifactRef,
) -> bool:
    return bool(
        request.intake_ref == intake_ref
        and request.attempt_id == intake.attempt_id
        and request.evaluator_owner_id == intake.evaluator_owner_id
        and request.design_problem_ref == intake.design_problem_ref
        and request.candidate_ref == intake.candidate_ref
        and request.world_model_record_ref == intake.world_model_record_ref
        and request.evaluation_mode == intake.mode_resolution.canonical_mode
        and request.domain_pack_ref == intake.domain_pack_ref
        and request.target_population_scope_ref == intake.target_population_scope_ref
        and request.evaluation_input_refs == intake.evaluation_input_refs
        and request.evaluation_input_provenance == intake.evaluation_input_provenance
        and request.evidence_refs == intake.evidence_refs
        and request.requested_at == intake.requested_at
        and request.intended_start_at == intake.intended_start_at
        and request.rule_version == intake.requested_rule_version
        and request.external_executor_identity_ref == intake.external_executor_identity_ref
    )


def _basis_and_result_blockers(
    basis: EvalSafetyModeBasis,
    effective_profile: EvalSafetyModeProfile | None,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef | None,
    results: tuple[EvalSafetyRequirementResult, ...],
    evaluated_at: datetime,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if basis.rule_version != request.rule_version:
        blockers.append(_blocker("mode_basis_rule_mismatch"))
    if evaluated_at < basis.valid_from or (
        basis.valid_until is not None and evaluated_at >= basis.valid_until
    ):
        blockers.append(_blocker("mode_basis_stale"))
    basis_profiles = tuple(row for row in basis.profiles if row.mode == request.evaluation_mode)
    if len(basis_profiles) != 1:
        blockers.append(_blocker("mode_profile_missing"))
        return tuple(blockers)
    if effective_profile is None or effective_profile.mode != request.evaluation_mode:
        blockers.append(_blocker("effective_profile_missing"))
        return tuple(blockers)
    basis_keys = {
        (row.requirement_id, row.evidence_contract_id) for row in basis_profiles[0].all_of
    }
    effective_keys = {
        (row.requirement_id, row.evidence_contract_id) for row in effective_profile.all_of
    }
    if not basis_keys <= effective_keys:
        blockers.append(_blocker("profile_basis_invalid"))
    requirements = effective_profile.all_of
    counts = Counter(row.requirement_id for row in results)
    for requirement in requirements:
        if counts[requirement.requirement_id] != 1:
            blockers.append(_blocker("requirement_result_missing"))
            continue
        result = next(row for row in results if row.requirement_id == requirement.requirement_id)
        if request_ref is None or not _result_matches_request(
            result, requirement, request, request_ref, evaluated_at
        ):
            blockers.append(_blocker("requirement_result_binding_mismatch"))
        blockers.extend(result.blocker_codes)
    if set(counts) != {row.requirement_id for row in requirements}:
        blockers.append(_blocker("requirement_result_set_mismatch"))
    return tuple(blockers)


def _result_matches_request(
    result: EvalSafetyRequirementResult,
    requirement: EvalSafetyRequirement,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef,
    evaluated_at: datetime,
) -> bool:
    return bool(
        result.requirement_id == requirement.requirement_id
        and result.evidence_contract_id == requirement.evidence_contract_id
        and result.request_ref == request_ref
        and result.candidate_ref == request.candidate_ref
        and result.world_model_record_ref == request.world_model_record_ref
        and result.evaluation_mode == request.evaluation_mode
        and result.target_population_scope_ref == request.target_population_scope_ref
        and result.rule_version == request.rule_version
        and result.intended_start_at == request.intended_start_at
        and result.evidence_ref in request.evidence_refs
        and result.status == "passed"
        and (result.valid_until is None or evaluated_at < result.valid_until)
    )


def evaluation_safety_core_bytes(core: EvaluationSafetyDecisionCore) -> bytes:
    """Return deterministic canonical JSON bytes for a frozen safety core."""

    return json.dumps(
        core.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()


def evaluation_safety_decision_id(core: EvaluationSafetyDecisionCore) -> str:
    """Return the promotion-independent deterministic decision identity."""

    return "eval-safety-decision:" + hashlib.sha256(evaluation_safety_core_bytes(core)).hexdigest()


def build_evaluation_safety_decision_event(
    *,
    core: EvaluationSafetyDecisionCore,
    classification: VerifiedNearMissClassification | None,
) -> EvaluationSafetyDecisionEvent:
    """Wrap a frozen core; accept only opaque canonical classification output."""

    if not _is_produced(core, _ProducedEvaluationSafetyDecisionCore):
        raise ValueError("eval_safety_decision_core_unreconciled")
    admitted = (
        classification
        if _classification_is_produced(classification, core)
        else None
    )
    facet = admitted.promotion_safe_facet if admitted is not None else None
    values = {
        "decision_id": evaluation_safety_decision_id(core),
        "safety": core,
        "classification_offer_ref": admitted.offer_ref if admitted is not None else None,
        "promotion_validation_basis_ref": (
            admitted.validation_basis_ref if admitted is not None else None
        ),
        "promotion_safe_facet": facet,
        "near_miss": core.status == "blocked" and facet is True,
    }
    result = _ProducedEvaluationSafetyDecisionEvent(
        **values, content_hash=_content_hash(values)
    )
    _mark_produced(result)
    return result


def verify_near_miss_classification(
    *,
    offer: EvalSafetyNearMissClassificationOffer,
    offer_ref: ArtifactRef,
    validation_basis_ref: ArtifactRef,
    canonical_promotion_input_ref: ArtifactRef,
    design_problem_binding_ref: ArtifactRef,
    value_receipt_ref: ArtifactRef,
    candidate_ref: ArtifactRef,
    world_model_record_ref: ArtifactRef,
    promotion_rule_version: str,
    current_open_world_resolver_basis_ref: ArtifactRef,
    current_epoch_resolver_basis_ref: ArtifactRef,
    promotion: PromotionPortObservation,
    candidate_summary: CandidateSummary,
    design_problem: DesignProblem,
    value_receipt: ValueGateReceipt,
    open_world_resolver: OpenWorldRiskArtifactResolver,
    epoch_validity_resolver: core_contracts.EpochValidityN9EvidenceResolver,
    core: EvaluationSafetyDecisionCore,
) -> VerifiedNearMissClassification | None:
    """Produce an opaque post-core classification only after canonical N9 replay."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.promotion_sequence import (
        CanonicalPromotionReceipt,
        promotion_receipt_allows_decision_front,
        validate_canonical_promotion_receipt,
    )

    parsed_receipts: list[CanonicalPromotionReceipt] = []
    for payload in promotion.receipts:
        try:
            parsed = CanonicalPromotionReceipt.model_validate(payload)
        except (TypeError, ValueError):
            continue
        if parsed.candidate_id == candidate_summary.candidate_id:
            parsed_receipts.append(parsed)
    if len(parsed_receipts) != 1:
        return None
    receipt = parsed_receipts[0]
    owner = receipt.owner_projection
    open_world = owner.open_world_gate
    epoch = owner.epoch_validity_projection
    if open_world is None or epoch is None:
        return None
    receipt_hash = gy_content_hash(receipt.model_dump(mode="json"))
    design_hash = gy_content_hash(owner.design_problem_binding.model_dump(mode="json"))
    exact_bindings = (
        _is_produced(core, _ProducedEvaluationSafetyDecisionCore),
        offer.content_hash == offer_ref.content_hash,
        offer.safety_semantic_hash == core.safety_semantic_hash,
        offer.promotion_receipt_ref.content_hash == receipt_hash,
        offer.canonical_promotion_input_ref == canonical_promotion_input_ref,
        offer.canonical_promotion_input_ref.content_hash == owner.projection_hash,
        offer.design_problem_binding_ref == design_problem_binding_ref,
        offer.design_problem_binding_ref.content_hash == design_hash,
        offer.value_receipt_ref == value_receipt_ref,
        offer.candidate_ref == candidate_ref,
        offer.world_model_record_ref == world_model_record_ref,
        offer.promotion_rule_version == promotion_rule_version == receipt.schema_version,
        offer.open_world_resolver_basis_ref == current_open_world_resolver_basis_ref,
        offer.open_world_resolver_basis_ref == open_world.vector_artifact_ref,
        offer.epoch_resolver_basis_ref == current_epoch_resolver_basis_ref,
        offer.epoch_resolver_basis_ref == epoch.gate_receipt_ref,
        validation_basis_ref.content_hash == owner.projection_hash,
        offer.candidate_ref.artifact_id == candidate_summary.candidate_id,
        offer.candidate_ref.content_hash == candidate_summary.content_hash,
        offer.value_receipt_ref.content_hash == value_receipt.value_ref,
        offer.world_model_record_ref.content_hash == value_receipt.world_model_record_content_hash,
    )
    if not all(exact_bindings):
        return None
    if validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=candidate_summary,
        design_problem=design_problem,
        value_receipt=value_receipt,
        open_world_resolver=open_world_resolver,
        epoch_validity_resolver=epoch_validity_resolver,
    ):
        return None
    safe = promotion_receipt_allows_decision_front(
        promotion,
        candidate_summary,
        design_problem=design_problem,
        open_world_resolver=open_world_resolver,
        epoch_validity_resolver=epoch_validity_resolver,
    )
    result = object.__new__(VerifiedNearMissClassification)
    object.__setattr__(result, "offer_ref", offer_ref)
    object.__setattr__(result, "validation_basis_ref", validation_basis_ref)
    object.__setattr__(result, "promotion_safe_facet", safe)
    object.__setattr__(result, "safety_semantic_hash", core.safety_semantic_hash)
    object.__setattr__(result, "_producer_token", _PRODUCER_TOKEN)
    object.__setattr__(result, "_producer_fingerprint", _classification_fingerprint(result))
    return result


def build_evaluation_safety_certificate(
    *,
    core: EvaluationSafetyDecisionCore,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef,
    decision: EvaluationSafetyDecisionEvent,
    decision_ref: ArtifactRef,
) -> EvalSafetyCertificate:
    """Issue an in-memory certificate only for an eligible frozen core."""

    if (
        not _is_produced(core, _ProducedEvaluationSafetyDecisionCore)
        or not core.certificate_eligible
        or core.status != "passed"
    ):
        raise ValueError("eval_safety_certificate_ineligible")
    if (
        core.request_ref != request_ref
        or core.evaluator_owner_id != request.evaluator_owner_id
        or core.evaluation_input_refs != request.evaluation_input_refs
        or core.evaluation_input_provenance != request.evaluation_input_provenance
        or core.evaluation_mode != request.evaluation_mode
        or not _is_produced(decision, _ProducedEvaluationSafetyDecisionEvent)
        or decision.safety != core
        or decision_ref.content_hash != decision.content_hash
        or not core.requirement_results
        or any(
            row.request_ref != request_ref
            or row.candidate_ref != request.candidate_ref
            or row.world_model_record_ref != request.world_model_record_ref
            or row.evaluation_mode != request.evaluation_mode
            or row.target_population_scope_ref != request.target_population_scope_ref
            or row.rule_version != request.rule_version
            or row.intended_start_at != request.intended_start_at
            for row in core.requirement_results
        )
    ):
        raise ValueError("eval_safety_certificate_core_request_binding_mismatch")
    valid_until = core.valid_until or (core.evaluated_at + timedelta(hours=1))
    values = {
        "decision_ref": decision_ref,
        "request_ref": request_ref,
        "evaluator_owner_id": request.evaluator_owner_id,
        "evaluation_mode": request.evaluation_mode,
        "candidate_ref": request.candidate_ref,
        "world_model_record_ref": request.world_model_record_ref,
        "domain_pack_ref": request.domain_pack_ref,
        "target_population_scope_ref": request.target_population_scope_ref,
        "evaluation_input_refs": request.evaluation_input_refs,
        "evaluation_input_provenance": request.evaluation_input_provenance,
        "rule_version": request.rule_version,
        "revision_lineage_id": "eval-safety-lineage:" + core.safety_semantic_hash,
        "valid_from": core.evaluated_at,
        "valid_until": valid_until,
        "authoritative_for": "attempted_evaluation_admission",
        "may_not_use_for": (
            "promotion",
            "simulation_safety",
            "attempted_evaluation_occurred",
            "deployment_execution",
            "realized_effect",
            "implementation_status",
            "appeal_outcome",
        ),
    }
    result = _ProducedEvalSafetyCertificate(**values, content_hash=_content_hash(values))
    _mark_produced(result)
    return result


@dataclass(frozen=True)
class EvaluationSafetyAuthorityReplay:
    """Producer-owned in-memory authority reconstructed from persisted DTOs."""

    mode_basis: EvalSafetyModeBasis
    pack_admission: EvalSafetyPackAdmissionReceipt
    decision_requirement_results: tuple[EvalSafetyRequirementResult, ...]
    current_requirement_results: tuple[EvalSafetyRequirementResult, ...]
    decision_core: EvaluationSafetyDecisionCore
    decision: EvaluationSafetyDecisionEvent
    certificate: EvalSafetyCertificate
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...]


def replay_evaluation_safety_authority(
    *,
    intake_ref: ArtifactRef,
    intake: EvaluationAttemptIntake,
    request_ref: ArtifactRef,
    request: EvaluationAttemptRequest,
    mode_basis_ref: ArtifactRef,
    mode_basis: EvalSafetyModeBasis,
    pack_ref: ArtifactRef,
    pack: DomainEvalSafetyPack,
    facet_registry: SemanticFacetRegistry,
    facet_denominator: SemanticFacetDenominatorReceipt,
    authority_resolver: EvalSafetyAuthorityResolver,
    appointment_resolver: EvalSafetyVerifierAppointmentResolver,
    verifier_registry: EvalSafetyVerifierRegistry,
    evidence_by_contract: dict[str, ArtifactRef],
    classification: VerifiedNearMissClassification | None,
    decision_ref: ArtifactRef,
    decision: EvaluationSafetyDecisionEvent,
    certificate_ref: ArtifactRef,
    certificate: EvalSafetyCertificate,
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...],
    decision_evaluated_at: datetime,
    revalidated_at: datetime,
) -> EvaluationSafetyAuthorityReplay | None:
    """Re-run every producer after CAS parsing; never restore private markers."""

    admitted_basis = verify_evaluation_safety_mode_basis(
        basis_ref=mode_basis_ref,
        basis=mode_basis,
        authority_resolver=authority_resolver,
        verified_at=revalidated_at,
    )
    if admitted_basis is None:
        return None
    admitted_pack = admit_domain_evaluation_safety_pack(
        pack_ref=pack_ref,
        pack=pack,
        request=request,
        mode_basis_ref=mode_basis_ref,
        mode_basis=admitted_basis,
        facet_registry=facet_registry,
        facet_denominator=facet_denominator,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        admitted_at=revalidated_at,
    )
    if admitted_pack.status != "admitted":
        return None
    decision_results = verify_evaluation_safety_requirements(
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted_pack,
        evidence_by_contract=evidence_by_contract,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        evaluated_at=decision_evaluated_at,
    )
    core = decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted_pack,
        mode_basis=admitted_basis,
        requirement_results=decision_results,
        evaluated_at=decision_evaluated_at,
    )
    if core.status != "passed" or not core.certificate_eligible:
        return None
    rebuilt_decision = build_evaluation_safety_decision_event(
        core=core,
        classification=classification,
    )
    if (
        decision_evaluated_at != decision.safety.evaluated_at
        or
        rebuilt_decision.model_dump(mode="json") != decision.model_dump(mode="json")
        or decision_ref.content_hash != rebuilt_decision.content_hash
    ):
        return None
    rebuilt_certificate = build_evaluation_safety_certificate(
        core=core,
        request=request,
        request_ref=request_ref,
        decision=rebuilt_decision,
        decision_ref=decision_ref,
    )
    if (
        rebuilt_certificate.model_dump(mode="json")
        != certificate.model_dump(mode="json")
        or certificate_ref.content_hash != rebuilt_certificate.content_hash
    ):
        return None
    revisions = reconcile_evaluation_safety_revisions(
        revisions=tuple(node.revision for node in revision_nodes),
        cause_resolver=authority_resolver,
    )
    if len(revisions) != len(revision_nodes) or any(
        node.revision_ref.content_hash != rebuilt.content_hash
        for node, rebuilt in zip(revision_nodes, revisions, strict=True)
    ):
        return None
    replayed_nodes = tuple(
        EvalSafetyCertificateRevisionNode(
            revision_ref=node.revision_ref,
            revision=rebuilt,
        )
        for node, rebuilt in zip(revision_nodes, revisions, strict=True)
    )
    current_results = verify_evaluation_safety_requirements(
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted_pack,
        evidence_by_contract=evidence_by_contract,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        evaluated_at=revalidated_at,
    )
    return EvaluationSafetyAuthorityReplay(
        mode_basis=admitted_basis,
        pack_admission=admitted_pack,
        decision_requirement_results=decision_results,
        current_requirement_results=current_results,
        decision_core=core,
        decision=rebuilt_decision,
        certificate=rebuilt_certificate,
        revision_nodes=replayed_nodes,
    )


def verify_evaluation_safety_consumer_admission(
    *,
    context: EvaluationExecutionContext,
    challenge: EvalSafetyAdmissionChallenge,
    intake: EvaluationAttemptIntake,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef,
    certificate_ref: ArtifactRef | None,
    certificate: EvalSafetyCertificate | None,
    decision_ref: ArtifactRef | None,
    decision: EvaluationSafetyDecisionEvent | None,
    decision_core: EvaluationSafetyDecisionCore | None,
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...],
    current_requirement_results: tuple[EvalSafetyRequirementResult, ...],
    verified_at: datetime,
) -> EvalSafetyConsumerAdmissionReceipt:
    """Verify exact binding, currentness, and the unique certificate revision head."""

    blockers: list[str] = []
    if challenge.consumer_component_id != context.evaluator_owner_id:
        blockers.append(_blocker("consumer_challenge_binding_mismatch"))
    if (
        context.evaluation_mode != intake.mode_resolution.canonical_mode
        or context.evaluator_owner_id != intake.evaluator_owner_id
        or context.design_problem_ref != intake.design_problem_ref
        or context.candidate_ref != intake.candidate_ref
        or context.world_model_record_ref != intake.world_model_record_ref
        or context.target_population_scope_ref != intake.target_population_scope_ref
        or context.rule_version != intake.requested_rule_version
        or context.intended_start_at != intake.intended_start_at
        or context.evaluation_input_refs != intake.evaluation_input_refs
        or context.evaluation_input_provenance != intake.evaluation_input_provenance
        or context.attempt_class != recompute_attempt_class(
            intake.evaluation_input_refs, intake.evaluation_input_provenance
        )
        or context.attempt_class != "non_simulation"
    ):
        blockers.append(_blocker("execution_context_binding_mismatch"))
    if certificate_ref is None or certificate is None:
        blockers.append(_blocker("certificate_missing"))
    elif (
        not _is_produced(certificate, _ProducedEvalSafetyCertificate)
        or not _is_produced(decision, _ProducedEvaluationSafetyDecisionEvent)
        or not _is_produced(decision_core, _ProducedEvaluationSafetyDecisionCore)
        or not decision_core.certificate_eligible
    ):
        blockers.append(_blocker("decision_unreconciled"))
    else:
        if (
            certificate_ref.content_hash != certificate.content_hash
            or decision_ref is None
            or decision is None
            or decision_ref.content_hash != decision.content_hash
            or decision.safety != decision_core
            or certificate.decision_ref != decision_ref
            or certificate.request_ref != request_ref
            or request.intake_ref != context.intake_ref
            or request.evaluator_owner_id != context.evaluator_owner_id
            or request.design_problem_ref != context.design_problem_ref
            or decision_core.evaluator_owner_id != context.evaluator_owner_id
            or certificate.evaluator_owner_id != context.evaluator_owner_id
            or certificate.evaluation_mode != context.evaluation_mode
            or certificate.evaluation_mode != request.evaluation_mode
            or certificate.candidate_ref != context.candidate_ref
            or certificate.candidate_ref != request.candidate_ref
            or certificate.world_model_record_ref != context.world_model_record_ref
            or certificate.world_model_record_ref != request.world_model_record_ref
            or certificate.domain_pack_ref != request.domain_pack_ref
            or certificate.target_population_scope_ref != context.target_population_scope_ref
            or certificate.target_population_scope_ref != request.target_population_scope_ref
            or request.evaluation_input_refs != context.evaluation_input_refs
            or request.evaluation_input_provenance != context.evaluation_input_provenance
            or decision_core.evaluation_input_refs != context.evaluation_input_refs
            or decision_core.evaluation_input_provenance
            != context.evaluation_input_provenance
            or certificate.evaluation_input_refs != context.evaluation_input_refs
            or certificate.evaluation_input_provenance
            != context.evaluation_input_provenance
            or certificate.rule_version != context.rule_version
            or certificate.rule_version != request.rule_version
            or context.intended_start_at != request.intended_start_at
        ):
            blockers.append(_blocker("certificate_binding_mismatch"))
        if verified_at < certificate.valid_from or verified_at >= certificate.valid_until:
            blockers.append(_blocker("certificate_stale"))
        blockers.extend(
            _revision_head_blockers(
                certificate=certificate,
                certificate_ref=certificate_ref,
                revision_nodes=revision_nodes,
                verified_at=verified_at,
            )
        )
        current_by_requirement = {
            row.requirement_id: row for row in current_requirement_results
        }
        if (
            len(current_by_requirement) != len(current_requirement_results)
            or set(current_by_requirement)
            != {row.requirement_id for row in decision_core.requirement_results}
            or any(
            not _is_produced(row, _ProducedEvalSafetyRequirementResult)
            for row in current_requirement_results
            )
            or any(
                not _current_result_matches_original(
                    current_by_requirement[original.requirement_id],
                    original,
                    request,
                    request_ref,
                    verified_at,
                )
                for original in decision_core.requirement_results
            )
        ):
            blockers.append(_blocker("certificate_evidence_head_invalid"))
    current_head_ref = (
        _current_revision_head_ref(revision_nodes, verified_at)
        if not blockers
        else None
    )
    if (
        not blockers
        and current_head_ref != context.eval_safety_revision_head_ref
    ):
        blockers.append(_blocker("certificate_revision_head_binding_mismatch"))
        current_head_ref = None
    result = _ProducedEvalSafetyConsumerAdmissionReceipt(
        status="blocked" if blockers else "verified",
        intake_ref=context.intake_ref,
        certificate_ref=certificate_ref,
        current_revision_head_ref=current_head_ref,
        execution_context_hash=evaluation_execution_context_hash(context),
        challenge=challenge,
        blocker_codes=tuple(sorted(set(blockers))),
        verified_at=verified_at,
    )
    if not blockers:
        result._mark_produced()
    return result


def _current_result_matches_original(
    current: EvalSafetyRequirementResult,
    original: EvalSafetyRequirementResult,
    request: EvaluationAttemptRequest,
    request_ref: ArtifactRef,
    verified_at: datetime,
) -> bool:
    return bool(
        current.requirement_id == original.requirement_id
        and current.evidence_contract_id == original.evidence_contract_id
        and current.evidence_ref == original.evidence_ref
        and current.verifier_component_id == original.verifier_component_id
        and current.request_ref == request_ref
        and current.candidate_ref == request.candidate_ref
        and current.world_model_record_ref == request.world_model_record_ref
        and current.evaluation_mode == request.evaluation_mode
        and current.target_population_scope_ref == request.target_population_scope_ref
        and current.rule_version == request.rule_version
        and current.intended_start_at == request.intended_start_at
        and current.status == "passed"
        and (current.valid_until is None or verified_at < current.valid_until)
    )


def _revision_head_blockers(
    *,
    certificate: EvalSafetyCertificate,
    certificate_ref: ArtifactRef,
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...],
    verified_at: datetime,
) -> tuple[str, ...]:
    if not revision_nodes:
        return (_blocker("certificate_revision_head_invalid"),)
    revisions = tuple(node.revision for node in revision_nodes)
    if any(
        node.revision_ref.content_hash != node.revision.content_hash
        for node in revision_nodes
    ):
        return (_blocker("certificate_revision_ref_content_mismatch"),)
    if any(
        not _is_produced(row, _ProducedEvalSafetyCertificateRevision)
        for row in revisions
    ):
        return (_blocker("certificate_revision_unverified"),)
    if any(row.revision_lineage_id != certificate.revision_lineage_id for row in revisions):
        return (_blocker("certificate_revision_lineage_mismatch"),)
    by_ref = {_identity(node.revision_ref): node for node in revision_nodes}
    if len(by_ref) != len(revision_nodes) or len(
        {node.revision.content_hash for node in revision_nodes}
    ) != len(revision_nodes):
        return (_blocker("certificate_revision_duplicate"),)
    for start in revision_nodes:
        seen: set[tuple[str, str]] = set()
        cursor = start
        while cursor.revision.predecessor_ref is not None:
            cursor_identity = _identity(cursor.revision_ref)
            if cursor_identity in seen:
                return (_blocker("certificate_revision_cyclic"),)
            seen.add(cursor_identity)
            predecessor_identity = _identity(cursor.revision.predecessor_ref)
            if predecessor_identity not in by_ref:
                break
            cursor = by_ref[predecessor_identity]
    roots = tuple(
        node for node in revision_nodes if node.revision.predecessor_ref is None
    )
    if len(roots) != 1 or roots[0].revision.action != "issue":
        return (_blocker("certificate_revision_root_invalid"),)
    successors: dict[
        tuple[str, str], list[EvalSafetyCertificateRevisionNode]
    ] = {
        key: [] for key in by_ref
    }
    for node in revision_nodes:
        if node.revision.predecessor_ref is None:
            continue
        predecessor_identity = _identity(node.revision.predecessor_ref)
        if predecessor_identity not in by_ref:
            return (_blocker("certificate_revision_predecessor_missing"),)
        if (
            node.revision.effective_at
            < by_ref[predecessor_identity].revision.effective_at
        ):
            return (_blocker("certificate_revision_time_nonmonotone"),)
        successors[predecessor_identity].append(node)
    if any(len(rows) > 1 for rows in successors.values()):
        return (_blocker("certificate_revision_forked"),)
    if any(
        node.revision.action == "revoke" and successors[_identity(node.revision_ref)]
        for node in revision_nodes
    ):
        return (_blocker("certificate_revoked"),)
    visited: set[tuple[str, str]] = set()
    ordered: list[EvalSafetyCertificateRevisionNode] = []
    cursor = roots[0]
    while _identity(cursor.revision_ref) not in visited:
        cursor_identity = _identity(cursor.revision_ref)
        visited.add(cursor_identity)
        ordered.append(cursor)
        rows = successors[cursor_identity]
        if not rows:
            break
        cursor = rows[0]
    if (
        _identity(cursor.revision_ref) in visited
        and successors[_identity(cursor.revision_ref)]
    ):
        return (_blocker("certificate_revision_cyclic"),)
    if visited != set(by_ref):
        return (_blocker("certificate_revision_disconnected"),)
    active = tuple(
        node for node in ordered if node.revision.effective_at <= verified_at
    )
    if not active:
        return (_blocker("certificate_revision_not_effective"),)
    current = active[-1]
    if current.revision.action == "revoke":
        return (_blocker("certificate_revoked"),)
    if current.revision.certificate_ref != certificate_ref:
        return (_blocker("certificate_superseded"),)
    if current.revision.predicate_provenance not in {
        "recomputed",
        "independently_reconciled",
    }:
        return (_blocker("certificate_revision_unverified"),)
    return ()


def _current_revision_head_ref(
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...],
    verified_at: datetime,
) -> ArtifactRef | None:
    active = tuple(
        node
        for node in revision_nodes
        if node.revision.effective_at <= verified_at
    )
    if not active:
        return None
    predecessor_identities = {
        _identity(node.revision.predecessor_ref)
        for node in active
        if node.revision.predecessor_ref is not None
    }
    heads = tuple(
        node
        for node in active
        if _identity(node.revision_ref) not in predecessor_identities
    )
    if len(heads) != 1:
        return None
    return heads[0].revision_ref


def verifier_port_is_verification_only(port_type: type[object]) -> bool:
    """Return whether a port exposes only the single admission operation."""

    public = {
        name
        for name, value in inspect.getmembers(port_type)
        if not name.startswith("_") and callable(value)
    }
    return public == {"require_admission"}


__all__ = [
    "EVALUATION_SAFETY_ARTIFACT_IDENTITIES",
    "DomainEvalSafetyPack",
    "EvalSafetyAdmissionChallenge",
    "EvalSafetyAllApplicability",
    "EvalSafetyAppointmentResolution",
    "EvalSafetyAuthorityResolution",
    "EvalSafetyAuthorityResolver",
    "EvalSafetyAuthoritySurfacePacket",
    "EvalSafetyCertificate",
    "EvalSafetyCertificateRevision",
    "EvalSafetyCertificateRevisionNode",
    "EvalSafetyConsumerAdmissionReceipt",
    "EvalSafetyFacetApplicability",
    "EvalSafetyFacetValueRequirement",
    "EvalSafetyMetricsProjection",
    "EvalSafetyModeBasis",
    "EvalSafetyModeProfile",
    "EvalSafetyNearMissClassificationOffer",
    "EvalSafetyPackAdmissionReceipt",
    "EvalSafetyRequirement",
    "EvalSafetyRequirementResult",
    "EvalSafetySurfaceDisposition",
    "EvalSafetyVerifierAppointment",
    "EvalSafetyVerifierAppointmentResolver",
    "EvalSafetyVerifierPort",
    "EvalSafetyVerifierRegistry",
    "EvaluationAttemptIntake",
    "EvaluationAttemptRequest",
    "EvaluationExecutionContext",
    "EvaluationInputProvenance",
    "EvaluationSafetyArtifactIdentity",
    "EvaluationSafetyAuthorityReplay",
    "EvaluationSafetyDecisionCore",
    "EvaluationSafetyDecisionEvent",
    "EvaluationSafetyProjectionReadIdentity",
    "EvidenceVerifier",
    "NamespacedEvalSafetyId",
    "VerifiedNearMissClassification",
    "admit_domain_evaluation_safety_pack",
    "build_evaluation_safety_certificate",
    "build_evaluation_safety_decision_event",
    "decide_evaluation_safety_core",
    "evaluation_execution_context_hash",
    "evaluation_safety_consumer_admission_is_verified",
    "evaluation_safety_core_bytes",
    "evaluation_safety_decision_id",
    "evaluation_safety_metrics_projection_identity",
    "recompute_attempt_class",
    "reconcile_evaluation_safety_revisions",
    "replay_evaluation_safety_authority",
    "verifier_port_is_verification_only",
    "verify_evaluation_safety_consumer_admission",
    "verify_evaluation_safety_mode_basis",
    "verify_evaluation_safety_requirements",
    "verify_near_miss_classification",
]
