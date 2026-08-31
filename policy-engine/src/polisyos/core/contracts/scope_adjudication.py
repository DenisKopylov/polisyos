"""Candidate-band record for the ratified four-way scope test.

The artifact preserves one plane, source bindings, time roles, and the ordered
predicate observations. It never appoints a predicate resolver and never acts as
a scope ruling or claim-lifecycle command; those missing production capabilities
remain explicit limitations on every record.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes

SCOPE_ADJUDICATION_CANDIDATE_SCHEMA_VERSION = (
    "polisyos.core.scope-adjudication-candidate.v1"
)
SCOPE_ADJUDICATION_AUTHORITY_PURPOSE: Literal["scope_adjudication"] = (
    "scope_adjudication"
)

ScopeDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)]
ScopePredicateClass = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]
ScopeAdjudicationProhibitedUse = Literal[
    "scope_ruling",
    "claim_lifecycle_transition",
    "claim_head_advance",
    "publication_authorization",
    "institutional_execution",
]

SCOPE_ADJUDICATION_PROHIBITED_USES: tuple[
    ScopeAdjudicationProhibitedUse, ...
] = (
    "scope_ruling",
    "claim_lifecycle_transition",
    "claim_head_advance",
    "publication_authorization",
    "institutional_execution",
)

_ADMITTED_PREDICATE_CLASSES = frozenset(
    {"recomputed", "independently_reconciled"}
)
_CANON_SPEC = CanonSpec(
    name="polisyos.canon.json",
    version="0.2.0",
    forbid_floats=True,
    forbid_nan_inf=True,
    exclude_none=False,
    max_depth=64,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScopeAdjudicationPlane(StrEnum):
    """One plane in the external-act to public-projection custody chain."""

    EXTERNAL_INSTITUTIONAL_ACT = "external_institutional_act"
    EXTERNAL_EVIDENCE_EMISSION = "external_evidence_emission"
    EVIDENCE_ADMISSION = "policyos_receipt_verification_admission"
    SCOPED_CLAIM_REACTION = "policyos_scoped_claim_reaction"
    PUBLIC_PROJECTION = "public_projection"


class ScopeAdjudicationPredicate(StrEnum):
    """The three predicates in the ratified, order-sensitive four-way test."""

    ABSENCE_MAKES_OUR_PUBLISHED_CLAIM_FALSE = (
        "absence_makes_policyos_published_claim_silently_false"
    )
    OUTPUT_CHANGES_OUR_CLAIM_VALIDITY = "output_changes_policyos_claim_validity"
    CHANGES_ONLY_WHO_ANSWERS_FOR_OUR_CLAIMS = (
        "changes_only_who_answers_for_policyos_claim"
    )


class ScopeAdjudicationRuling(StrEnum):
    """A candidate proposal from the ordered four-way test, never authority."""

    OWN = "own"
    INTEGRATE = "integrate"
    OBSERVE = "observe"
    OUT_OF_SCOPE = "out_of_scope"


_PREDICATE_ORDER = tuple(ScopeAdjudicationPredicate)
_RULING_BY_TRUE_PREDICATE = {
    ScopeAdjudicationPredicate.ABSENCE_MAKES_OUR_PUBLISHED_CLAIM_FALSE: (
        ScopeAdjudicationRuling.OWN
    ),
    ScopeAdjudicationPredicate.OUTPUT_CHANGES_OUR_CLAIM_VALIDITY: (
        ScopeAdjudicationRuling.INTEGRATE
    ),
    ScopeAdjudicationPredicate.CHANGES_ONLY_WHO_ANSWERS_FOR_OUR_CLAIMS: (
        ScopeAdjudicationRuling.OBSERVE
    ),
}


class ScopePredicateObservation(_StrictFrozenModel):
    """One content-bound candidate observation for one scope predicate."""

    plane: ScopeAdjudicationPlane
    predicate: ScopeAdjudicationPredicate
    value: bool | None
    predicate_class: ScopePredicateClass
    evidence_ref: ArtifactRef | None
    evidence_content_digest: ScopeDigest | None
    limitation_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_evidence_and_establishment(self) -> ScopePredicateObservation:
        if (self.evidence_ref is None) != (self.evidence_content_digest is None):
            raise ValueError("scope_evidence_binding_pair_incomplete")
        if (
            self.evidence_ref is not None
            and self.evidence_content_digest != str(self.evidence_ref.artifact_id)
        ):
            raise ValueError("scope_evidence_content_digest_mismatch")
        if self.value is None and self.predicate_class != "not_established":
            raise ValueError("scope_missing_value_must_be_not_established")
        if self.predicate_class in _ADMITTED_PREDICATE_CLASSES:
            if self.value is None or self.evidence_ref is None:
                raise ValueError("scope_admitted_predicate_requires_bound_evidence")
            if self.limitation_code is not None:
                raise ValueError("scope_admitted_predicate_cannot_carry_limitation")
        elif self.limitation_code is None:
            raise ValueError("scope_unestablished_predicate_requires_limitation")
        return self


class ScopeAdjudicationCandidate(_StrictFrozenModel):
    """Content-bound proposal that explicitly has no authority or closure effect."""

    schema_version: Literal[
        "polisyos.core.scope-adjudication-candidate.v1"
    ] = SCOPE_ADJUDICATION_CANDIDATE_SCHEMA_VERSION
    candidate_function_id: str = Field(min_length=1)
    candidate_description: str = Field(min_length=1)
    plane: ScopeAdjudicationPlane
    subject_ref: ArtifactRef
    subject_content_digest: ScopeDigest
    rule_ref: ArtifactRef
    rule_content_digest: ScopeDigest
    rule_version: str = Field(min_length=1)
    rule_effective_at: datetime
    valid_at: datetime
    known_at: datetime
    authority_purpose: Literal["scope_adjudication"] = (
        SCOPE_ADJUDICATION_AUTHORITY_PURPOSE
    )
    observations: tuple[ScopePredicateObservation, ...] = Field(
        min_length=3, max_length=3
    )
    proposed_ruling: ScopeAdjudicationRuling | None
    status: Literal["candidate_only"] = "candidate_only"
    authority_effect: Literal["none"] = "none"
    closure_effect: Literal["none"] = "none"
    authoritative_for: tuple[str, ...] = Field(default=(), max_length=0)
    may_not_use_for: tuple[ScopeAdjudicationProhibitedUse, ...] = (
        SCOPE_ADJUDICATION_PROHIBITED_USES
    )
    limitations: tuple[str, ...] = Field(min_length=2)
    payload_digest: ScopeDigest

    @model_validator(mode="after")
    def _validate_candidate_bindings(self) -> ScopeAdjudicationCandidate:
        _require_bound_ref(
            self.subject_ref,
            self.subject_content_digest,
            code="scope_subject_content_digest_mismatch",
        )
        _require_bound_ref(
            self.rule_ref,
            self.rule_content_digest,
            code="scope_rule_content_digest_mismatch",
        )
        for field_name, value in (
            ("rule_effective_at", self.rule_effective_at),
            ("valid_at", self.valid_at),
            ("known_at", self.known_at),
        ):
            _require_aware(value, field_name=field_name)
        if self.rule_effective_at > self.valid_at:
            raise ValueError("scope_rule_not_effective_at_valid_time")
        if tuple(observation.predicate for observation in self.observations) != (
            _PREDICATE_ORDER
        ):
            raise ValueError("scope_candidate_predicate_order_mismatch")
        if any(observation.plane is not self.plane for observation in self.observations):
            raise ValueError("scope_candidate_mixed_plane")
        if self.proposed_ruling is not _derive_proposed_ruling(self.observations):
            raise ValueError("scope_candidate_proposed_ruling_mismatch")
        if self.limitations != _derive_limitations(self.observations):
            raise ValueError("scope_candidate_limitation_set_mismatch")
        if self.may_not_use_for != SCOPE_ADJUDICATION_PROHIBITED_USES:
            raise ValueError("scope_candidate_authority_boundary_mismatch")
        if self.payload_digest != scope_adjudication_candidate_digest(self):
            raise ValueError("scope_candidate_payload_digest_mismatch")
        return self


def build_scope_adjudication_candidate(
    *,
    candidate_function_id: str,
    candidate_description: str,
    plane: ScopeAdjudicationPlane,
    subject_ref: ArtifactRef,
    subject_content_digest: ScopeDigest,
    rule_ref: ArtifactRef,
    rule_content_digest: ScopeDigest,
    rule_version: str,
    rule_effective_at: datetime,
    valid_at: datetime,
    known_at: datetime,
    observations: tuple[ScopePredicateObservation, ...],
) -> ScopeAdjudicationCandidate:
    """Build one deterministic candidate record without appointing authority."""

    values = {
        "schema_version": SCOPE_ADJUDICATION_CANDIDATE_SCHEMA_VERSION,
        "candidate_function_id": candidate_function_id,
        "candidate_description": candidate_description,
        "plane": plane,
        "subject_ref": subject_ref,
        "subject_content_digest": subject_content_digest,
        "rule_ref": rule_ref,
        "rule_content_digest": rule_content_digest,
        "rule_version": rule_version,
        "rule_effective_at": rule_effective_at,
        "valid_at": valid_at,
        "known_at": known_at,
        "authority_purpose": SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
        "observations": observations,
        "proposed_ruling": _derive_proposed_ruling(observations),
        "status": "candidate_only",
        "authority_effect": "none",
        "closure_effect": "none",
        "authoritative_for": (),
        "may_not_use_for": SCOPE_ADJUDICATION_PROHIBITED_USES,
        "limitations": _derive_limitations(observations),
    }
    draft = ScopeAdjudicationCandidate.model_construct(
        **values,
        payload_digest="sha256:" + "0" * 64,
    )
    payload_digest = scope_adjudication_candidate_digest(draft)
    return ScopeAdjudicationCandidate.model_validate(
        {**values, "payload_digest": payload_digest}
    )


def scope_adjudication_candidate_digest(
    candidate: ScopeAdjudicationCandidate,
) -> ScopeDigest:
    """Recompute the candidate digest from every semantic field."""

    return _digest_mapping(
        candidate.model_dump(mode="json", exclude={"payload_digest"})
    )


def verify_scope_adjudication_candidate(
    candidate: ScopeAdjudicationCandidate,
) -> ScopeAdjudicationCandidate:
    """Re-parse and content-verify one candidate artifact."""

    return ScopeAdjudicationCandidate.model_validate(candidate.model_dump(mode="python"))


def _derive_proposed_ruling(
    observations: tuple[ScopePredicateObservation, ...],
) -> ScopeAdjudicationRuling | None:
    if len(observations) != 3 or any(item.value is None for item in observations):
        return None
    for observation in observations:
        if observation.value:
            return _RULING_BY_TRUE_PREDICATE[observation.predicate]
    return ScopeAdjudicationRuling.OUT_OF_SCOPE


def _derive_limitations(
    observations: tuple[ScopePredicateObservation, ...],
) -> tuple[str, ...]:
    limitations = [
        "scope_predicate_resolver_unappointed",
        "scope_adjudication_claim_lifecycle_consumer_unappointed",
    ]
    limitations.extend(
        f"scope_predicate_not_established:{observation.predicate.value}"
        for observation in observations
        if observation.value is None
        or observation.predicate_class not in _ADMITTED_PREDICATE_CLASSES
    )
    return tuple(limitations)


def _digest_mapping(value: object) -> ScopeDigest:
    canonical = to_canonical_bytes(value, _CANON_SPEC)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _require_bound_ref(ref: ArtifactRef, digest: str, *, code: str) -> None:
    if digest != str(ref.artifact_id):
        raise ValueError(code)


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"scope_{field_name}_must_be_timezone_aware")


__all__ = [
    "SCOPE_ADJUDICATION_AUTHORITY_PURPOSE",
    "SCOPE_ADJUDICATION_CANDIDATE_SCHEMA_VERSION",
    "SCOPE_ADJUDICATION_PROHIBITED_USES",
    "ScopeAdjudicationCandidate",
    "ScopeAdjudicationPlane",
    "ScopeAdjudicationPredicate",
    "ScopeAdjudicationRuling",
    "ScopePredicateObservation",
    "build_scope_adjudication_candidate",
    "scope_adjudication_candidate_digest",
    "verify_scope_adjudication_candidate",
]
