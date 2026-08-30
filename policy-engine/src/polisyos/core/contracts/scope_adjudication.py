"""Typed, content-bound scope adjudication for the PolicyOS custody boundary.

The module owns the neutral record and persistence mechanics. It does not infer
predicate truth from prose or appoint a verifier. A caller must inject an evidence
resolver whose appointment is itself content-bound; consumers independently replay
the exact evidence and four-way rule before accepting a ruling.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    ArtifactWriteOptions,
    CanonInfo,
    InputRef,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.chronology import Digest, PredicateClass

SCOPE_ADJUDICATION_AUTHORITY_PURPOSE: Literal["scope_adjudication"] = "scope_adjudication"
SCOPE_PREDICATE_EVIDENCE_KIND = "core.scope_predicate_evidence"
SCOPE_PREDICATE_EVIDENCE_SCHEMA_NAME = "polisyos.core.ScopePredicateEvidence"
SCOPE_PREDICATE_EVIDENCE_SCHEMA_VERSION = "1.0"
SCOPE_ADJUDICATION_RECORD_KIND = "core.scope_adjudication_record"
SCOPE_ADJUDICATION_RECORD_SCHEMA_NAME = "polisyos.core.ScopeAdjudicationRecord"
SCOPE_ADJUDICATION_RECORD_SCHEMA_VERSION = "1.0"

SCOPE_ADJUDICATION_CANON_SPEC = CanonSpec(
    name="polisyos.canon.json",
    version="0.2.0",
    forbid_floats=True,
    forbid_nan_inf=True,
    exclude_none=False,
    max_depth=128,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)

ScopeAdjudicationAudience = Literal["internal_governance", "audit", "public_projection"]
ScopeAdjudicationAuthorityPurpose = Literal["scope_adjudication"]
ScopeAdjudicationNonReceiptCode = Literal[
    "scope_predicate_resolution_not_established",
    "scope_predicate_denominator_mismatch",
    "scope_predicate_profile_mismatch",
    "scope_predicate_binding_mismatch",
    "scope_predicate_plane_mismatch",
    "scope_predicate_not_established",
    "scope_ruling_contract_mismatch",
    "scope_adjudication_persistence_not_established",
]

_ADMITTED_PREDICATE_CLASSES = frozenset({"recomputed", "independently_reconciled"})


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScopeAdjudicationPlane(StrEnum):
    """One plane in the external-act-to-public-projection custody chain."""

    EXTERNAL_INSTITUTIONAL_ACT = "external_institutional_act"
    EXTERNAL_EVIDENCE_EMISSION = "external_evidence_emission"
    EVIDENCE_ADMISSION = "policyos_receipt_verification_admission"
    SCOPED_CLAIM_REACTION = "policyos_scoped_claim_reaction"
    PUBLIC_PROJECTION = "public_projection"


class ScopeAdjudicationPredicate(StrEnum):
    """The three ordered predicates in the ratified four-way boundary test."""

    ABSENCE_MAKES_OUR_PUBLISHED_CLAIM_FALSE = (
        "absence_makes_policyos_published_claim_silently_false"
    )
    OUTPUT_CHANGES_OUR_CLAIM_VALIDITY = "output_changes_policyos_claim_validity"
    CHANGES_ONLY_WHO_ANSWERS_FOR_OUR_CLAIMS = (
        "changes_only_who_answers_for_policyos_claim"
    )


class ScopeAdjudicationRuling(StrEnum):
    """The exhaustive positive outcomes of the ordered boundary test."""

    OWN = "own"
    INTEGRATE = "integrate"
    OBSERVE = "observe"
    OUT_OF_SCOPE = "out_of_scope"


class ScopeAdjudicationDisposition(StrEnum):
    """The operational consequence derived from one scope ruling."""

    BUILD_AND_OPERATE = "build_and_operate"
    CONSUME_TYPED_EVIDENCE_FAIL_CLOSED = "consume_typed_evidence_fail_closed"
    TRACK_AUTHORITY_ASSIGNMENT_ONLY = "track_authority_assignment_only"
    STOP_AND_NAME_EXTERNAL_CONTRACT = "stop_and_name_external_contract"


_PREDICATE_ORDER = (
    ScopeAdjudicationPredicate.ABSENCE_MAKES_OUR_PUBLISHED_CLAIM_FALSE,
    ScopeAdjudicationPredicate.OUTPUT_CHANGES_OUR_CLAIM_VALIDITY,
    ScopeAdjudicationPredicate.CHANGES_ONLY_WHO_ANSWERS_FOR_OUR_CLAIMS,
)
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
_DISPOSITION_BY_RULING = {
    ScopeAdjudicationRuling.OWN: ScopeAdjudicationDisposition.BUILD_AND_OPERATE,
    ScopeAdjudicationRuling.INTEGRATE: (
        ScopeAdjudicationDisposition.CONSUME_TYPED_EVIDENCE_FAIL_CLOSED
    ),
    ScopeAdjudicationRuling.OBSERVE: (
        ScopeAdjudicationDisposition.TRACK_AUTHORITY_ASSIGNMENT_ONLY
    ),
    ScopeAdjudicationRuling.OUT_OF_SCOPE: (
        ScopeAdjudicationDisposition.STOP_AND_NAME_EXTERNAL_CONTRACT
    ),
}


class ScopeAdjudicationRequest(_StrictFrozenModel):
    """One candidate, one plane, and one exact rule version to adjudicate."""

    schema_version: Literal["polisyos.core.scope-adjudication-request.v1"] = (
        "polisyos.core.scope-adjudication-request.v1"
    )
    candidate_function_id: str = Field(min_length=1)
    candidate_description: str = Field(min_length=1)
    target_ref: ArtifactRef
    target_content_hash: Digest
    plane: ScopeAdjudicationPlane
    authority_purpose: ScopeAdjudicationAuthorityPurpose = (
        SCOPE_ADJUDICATION_AUTHORITY_PURPOSE
    )
    rule_version_ref: ArtifactRef
    rule_version_content_hash: Digest
    rule_source_path: str = Field(min_length=1)
    rule_coordinate: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    rule_effective_at: datetime
    valid_at: datetime
    reconsider_on: datetime
    audiences: tuple[ScopeAdjudicationAudience, ...] = Field(min_length=1)
    external_owner: str | None = None
    integration_contract_ref: ArtifactRef | None = None
    integration_contract_content_hash: Digest | None = None
    prior_record_ref: ArtifactRef | None = None
    prior_record_content_hash: Digest | None = None

    @model_validator(mode="after")
    def _bindings_are_explicit(self) -> ScopeAdjudicationRequest:
        _require_ref_hash(
            self.target_ref,
            self.target_content_hash,
            code="scope_target_content_hash_mismatch",
        )
        _require_ref_hash(
            self.rule_version_ref,
            self.rule_version_content_hash,
            code="scope_rule_content_hash_mismatch",
        )
        _require_optional_ref_hash(
            self.integration_contract_ref,
            self.integration_contract_content_hash,
            code="scope_integration_contract_binding_mismatch",
        )
        _require_optional_ref_hash(
            self.prior_record_ref,
            self.prior_record_content_hash,
            code="scope_prior_record_binding_mismatch",
        )
        _require_aware(self.rule_effective_at, field="rule_effective_at")
        _require_aware(self.valid_at, field="valid_at")
        _require_aware(self.reconsider_on, field="reconsider_on")
        if self.rule_effective_at > self.valid_at:
            raise ValueError("scope_rule_not_effective_at_valid_time")
        if self.reconsider_on <= self.valid_at:
            raise ValueError("scope_reconsider_on_must_follow_valid_at")
        if len(self.audiences) != len(set(self.audiences)):
            raise ValueError("scope_audience_denominator_duplicate")
        external_contract_pair = (
            self.external_owner is not None,
            self.integration_contract_ref is not None,
        )
        if external_contract_pair[0] != external_contract_pair[1]:
            raise ValueError("scope_external_owner_contract_pair_incomplete")
        if self.external_owner is not None and not self.external_owner.strip():
            raise ValueError("scope_external_owner_blank")
        return self


class ScopePredicateEvidence(_StrictFrozenModel):
    """One verifier-emitted, content-bound truth value for the four-way test."""

    schema_version: Literal["polisyos.core.scope-predicate-evidence.v1"] = (
        "polisyos.core.scope-predicate-evidence.v1"
    )
    candidate_function_id: str = Field(min_length=1)
    target_ref: ArtifactRef
    target_content_hash: Digest
    plane: ScopeAdjudicationPlane
    predicate: ScopeAdjudicationPredicate
    outcome: bool
    predicate_class: PredicateClass
    evidence_ref: ArtifactRef
    evidence_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    verifier_provenance_content_hash: Digest
    rule_version_ref: ArtifactRef
    rule_version_content_hash: Digest
    authority_purpose: ScopeAdjudicationAuthorityPurpose = (
        SCOPE_ADJUDICATION_AUTHORITY_PURPOSE
    )
    observed_at: datetime

    @model_validator(mode="after")
    def _content_bindings_match_refs(self) -> ScopePredicateEvidence:
        for ref, content_hash, code in (
            (self.target_ref, self.target_content_hash, "scope_target_content_hash_mismatch"),
            (self.evidence_ref, self.evidence_content_hash, "scope_evidence_hash_mismatch"),
            (
                self.verifier_provenance_ref,
                self.verifier_provenance_content_hash,
                "scope_verifier_provenance_hash_mismatch",
            ),
            (
                self.rule_version_ref,
                self.rule_version_content_hash,
                "scope_rule_content_hash_mismatch",
            ),
        ):
            _require_ref_hash(ref, content_hash, code=code)
        _require_aware(self.observed_at, field="observed_at")
        return self


class PersistedScopePredicateEvidence(_StrictFrozenModel):
    """Exact predicate-evidence bytes paired with their parsed statement."""

    predicate_evidence_ref: ArtifactRef
    predicate_evidence_content_hash: Digest
    statement: ScopePredicateEvidence

    @model_validator(mode="after")
    def _handle_hash_matches_ref(self) -> PersistedScopePredicateEvidence:
        _require_ref_hash(
            self.predicate_evidence_ref,
            self.predicate_evidence_content_hash,
            code="scope_predicate_evidence_handle_hash_mismatch",
        )
        return self


class ScopePredicateEvidenceResolver(Protocol):
    """Appointed resolver for the complete three-predicate evidence denominator."""

    def resolve_scope_predicate_evidence(
        self,
        *,
        request: ScopeAdjudicationRequest,
    ) -> tuple[PersistedScopePredicateEvidence, ...]:
        """Return exact evidence handles for the requested target and plane."""
        ...


class ScopeAdjudicationAuthorityBoundary(_StrictFrozenModel):
    """The precise authority granted to a verified scope record."""

    authoritative_for: tuple[Literal["scope_adjudication"], ...] = (
        "scope_adjudication",
    )
    may_not_use_for: tuple[
        Literal[
            "institutional_execution",
            "publication_authorization",
            "claim_evidence_authority",
        ],
        ...,
    ] = (
        "institutional_execution",
        "publication_authorization",
        "claim_evidence_authority",
    )


class ScopeAdjudicationRecord(_StrictFrozenModel):
    """Persisted, replayable result of the ordered four-way boundary test."""

    schema_version: Literal["polisyos.core.scope-adjudication-record.v1"] = (
        "polisyos.core.scope-adjudication-record.v1"
    )
    record_id: str = Field(pattern=r"^scope_adjudication_[0-9a-f]{24}$")
    candidate_function_id: str = Field(min_length=1)
    candidate_description: str = Field(min_length=1)
    target_ref: ArtifactRef
    target_content_hash: Digest
    plane: ScopeAdjudicationPlane
    ruling: ScopeAdjudicationRuling
    disposition: ScopeAdjudicationDisposition
    predicate_evidence_refs: tuple[ArtifactRef, ...] = Field(min_length=3, max_length=3)
    predicate_evidence_content_hashes: tuple[Digest, ...] = Field(
        min_length=3,
        max_length=3,
    )
    appointed_verifier_provenance_ref: ArtifactRef
    appointed_verifier_provenance_content_hash: Digest
    producer_provenance_ref: ArtifactRef
    producer_provenance_content_hash: Digest
    authority_purpose: ScopeAdjudicationAuthorityPurpose = (
        SCOPE_ADJUDICATION_AUTHORITY_PURPOSE
    )
    authority_boundary: ScopeAdjudicationAuthorityBoundary = Field(
        default_factory=ScopeAdjudicationAuthorityBoundary
    )
    rule_version_ref: ArtifactRef
    rule_version_content_hash: Digest
    rule_source_path: str = Field(min_length=1)
    rule_coordinate: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    rule_effective_at: datetime
    source_observed_at: datetime
    valid_at: datetime
    recorded_at: datetime
    reconsider_on: datetime
    audiences: tuple[ScopeAdjudicationAudience, ...] = Field(min_length=1)
    external_owner: str | None = None
    integration_contract_ref: ArtifactRef | None = None
    integration_contract_content_hash: Digest | None = None
    prior_record_ref: ArtifactRef | None = None
    prior_record_content_hash: Digest | None = None

    @model_validator(mode="after")
    def _semantic_fields_are_derived(self) -> ScopeAdjudicationRecord:
        if self.disposition is not _DISPOSITION_BY_RULING[self.ruling]:
            raise ValueError("scope_disposition_ruling_mismatch")
        for ref, content_hash, code in (
            (self.target_ref, self.target_content_hash, "scope_target_content_hash_mismatch"),
            (
                self.appointed_verifier_provenance_ref,
                self.appointed_verifier_provenance_content_hash,
                "scope_verifier_provenance_hash_mismatch",
            ),
            (
                self.producer_provenance_ref,
                self.producer_provenance_content_hash,
                "scope_producer_provenance_hash_mismatch",
            ),
            (
                self.rule_version_ref,
                self.rule_version_content_hash,
                "scope_rule_content_hash_mismatch",
            ),
        ):
            _require_ref_hash(ref, content_hash, code=code)
        for ref, content_hash in zip(
            self.predicate_evidence_refs,
            self.predicate_evidence_content_hashes,
            strict=True,
        ):
            _require_ref_hash(
                ref,
                content_hash,
                code="scope_predicate_evidence_hash_mismatch",
            )
        if len({str(ref.artifact_id) for ref in self.predicate_evidence_refs}) != 3:
            raise ValueError("scope_predicate_evidence_denominator_duplicate")
        _require_optional_ref_hash(
            self.integration_contract_ref,
            self.integration_contract_content_hash,
            code="scope_integration_contract_binding_mismatch",
        )
        _require_optional_ref_hash(
            self.prior_record_ref,
            self.prior_record_content_hash,
            code="scope_prior_record_binding_mismatch",
        )
        for field_name, value in (
            ("rule_effective_at", self.rule_effective_at),
            ("source_observed_at", self.source_observed_at),
            ("valid_at", self.valid_at),
            ("recorded_at", self.recorded_at),
            ("reconsider_on", self.reconsider_on),
        ):
            _require_aware(value, field=field_name)
        if self.rule_effective_at > self.valid_at:
            raise ValueError("scope_rule_not_effective_at_valid_time")
        if self.source_observed_at > self.valid_at:
            raise ValueError("scope_predicate_observed_after_valid_time")
        if self.reconsider_on <= self.valid_at:
            raise ValueError("scope_reconsider_on_must_follow_valid_at")
        if len(self.audiences) != len(set(self.audiences)):
            raise ValueError("scope_audience_denominator_duplicate")
        has_external_contract = (
            self.external_owner is not None and self.integration_contract_ref is not None
        )
        if self.ruling is ScopeAdjudicationRuling.OWN and has_external_contract:
            raise ValueError("scope_own_ruling_cannot_delegate_authority")
        if self.ruling is not ScopeAdjudicationRuling.OWN and not has_external_contract:
            raise ValueError("scope_external_ruling_requires_owner_contract")
        return self


class PersistedScopeAdjudicationRecord(_StrictFrozenModel):
    """Exact scope-record bytes paired with their parsed record."""

    record_ref: ArtifactRef
    record_content_hash: Digest
    record: ScopeAdjudicationRecord

    @model_validator(mode="after")
    def _handle_hash_matches_ref(self) -> PersistedScopeAdjudicationRecord:
        _require_ref_hash(
            self.record_ref,
            self.record_content_hash,
            code="scope_adjudication_record_handle_hash_mismatch",
        )
        return self


class ScopeAdjudicationNonReceipt(_StrictFrozenModel):
    """Typed refusal that never carries a four-way ruling."""

    result_kind: Literal["non_receipt"] = "non_receipt"
    status: Literal["not_established", "rejected"]
    code: ScopeAdjudicationNonReceiptCode
    candidate_function_id: str = Field(min_length=1)
    plane: ScopeAdjudicationPlane
    reason: str = Field(min_length=1)
    decisive_evidence_refs: tuple[ArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True)
class ScopeAdjudicationProducer:
    """Compose verified predicate evidence into one persisted scope record."""

    store: ArtifactStore
    evidence_resolver: ScopePredicateEvidenceResolver
    appointed_verifier_provenance_ref: ArtifactRef
    producer_provenance_ref: ArtifactRef

    def produce(
        self,
        *,
        request: ScopeAdjudicationRequest,
    ) -> PersistedScopeAdjudicationRecord | ScopeAdjudicationNonReceipt:
        """Resolve evidence, derive the ordered ruling, persist, and read it back."""

        try:
            _verify_bound_ref(
                self.store,
                request.target_ref,
                request.target_content_hash,
            )
            _verify_bound_ref(
                self.store,
                request.rule_version_ref,
                request.rule_version_content_hash,
            )
            _verify_bound_ref(
                self.store,
                self.appointed_verifier_provenance_ref,
                str(self.appointed_verifier_provenance_ref.artifact_id),
            )
            _verify_bound_ref(
                self.store,
                self.producer_provenance_ref,
                str(self.producer_provenance_ref.artifact_id),
            )
            if request.integration_contract_ref is not None:
                if request.integration_contract_content_hash is None:
                    raise ValueError("scope_integration_contract_binding_mismatch")
                _verify_bound_ref(
                    self.store,
                    request.integration_contract_ref,
                    request.integration_contract_content_hash,
                )
            if request.prior_record_ref is not None:
                if request.prior_record_content_hash is None:
                    raise ValueError("scope_prior_record_binding_mismatch")
                _verify_bound_ref(
                    self.store,
                    request.prior_record_ref,
                    request.prior_record_content_hash,
                )
            supplied = self.evidence_resolver.resolve_scope_predicate_evidence(
                request=request
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return _non_receipt(
                request,
                code="scope_predicate_resolution_not_established",
                status="not_established",
                reason=f"Predicate evidence resolution failed: {type(exc).__name__}",
            )

        resolved = self._resolve_denominator(request=request, supplied=supplied)
        if isinstance(resolved, ScopeAdjudicationNonReceipt):
            return resolved
        evidence_rows = resolved
        ruling = _derive_ruling(evidence_rows)
        if isinstance(ruling, ScopeAdjudicationNonReceiptCodeMarker):
            return _non_receipt(
                request,
                code=ruling.code,
                status="not_established",
                reason="A predicate required to reach the ruling is not established.",
                decisive_evidence_refs=tuple(
                    row.predicate_evidence_ref for row in evidence_rows
                ),
            )
        if not _ruling_contract_is_complete(request, ruling):
            return _non_receipt(
                request,
                code="scope_ruling_contract_mismatch",
                status="rejected",
                reason="The ruling and external-owner contract fields do not compose.",
                decisive_evidence_refs=tuple(
                    row.predicate_evidence_ref for row in evidence_rows
                ),
            )

        recorded_at = datetime.now(UTC)
        record = ScopeAdjudicationRecord(
            record_id=_record_id(request=request, evidence_rows=evidence_rows, ruling=ruling),
            candidate_function_id=request.candidate_function_id,
            candidate_description=request.candidate_description,
            target_ref=request.target_ref,
            target_content_hash=request.target_content_hash,
            plane=request.plane,
            ruling=ruling,
            disposition=_DISPOSITION_BY_RULING[ruling],
            predicate_evidence_refs=tuple(
                row.predicate_evidence_ref for row in evidence_rows
            ),
            predicate_evidence_content_hashes=tuple(
                row.predicate_evidence_content_hash for row in evidence_rows
            ),
            appointed_verifier_provenance_ref=self.appointed_verifier_provenance_ref,
            appointed_verifier_provenance_content_hash=str(
                self.appointed_verifier_provenance_ref.artifact_id
            ),
            producer_provenance_ref=self.producer_provenance_ref,
            producer_provenance_content_hash=str(self.producer_provenance_ref.artifact_id),
            rule_version_ref=request.rule_version_ref,
            rule_version_content_hash=request.rule_version_content_hash,
            rule_source_path=request.rule_source_path,
            rule_coordinate=request.rule_coordinate,
            rule_version=request.rule_version,
            rule_effective_at=request.rule_effective_at,
            source_observed_at=max(row.statement.observed_at for row in evidence_rows),
            valid_at=request.valid_at,
            recorded_at=recorded_at,
            reconsider_on=request.reconsider_on,
            audiences=request.audiences,
            external_owner=request.external_owner,
            integration_contract_ref=request.integration_contract_ref,
            integration_contract_content_hash=request.integration_contract_content_hash,
            prior_record_ref=request.prior_record_ref,
            prior_record_content_hash=request.prior_record_content_hash,
        )
        try:
            return _persist_scope_adjudication_record(self.store, record)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return _non_receipt(
                request,
                code="scope_adjudication_persistence_not_established",
                status="not_established",
                reason=f"Scope adjudication persistence failed: {type(exc).__name__}",
                decisive_evidence_refs=tuple(
                    row.predicate_evidence_ref for row in evidence_rows
                ),
            )

    def _resolve_denominator(
        self,
        *,
        request: ScopeAdjudicationRequest,
        supplied: tuple[PersistedScopePredicateEvidence, ...],
    ) -> tuple[PersistedScopePredicateEvidence, ...] | ScopeAdjudicationNonReceipt:
        if len(supplied) != len(_PREDICATE_ORDER):
            return _non_receipt(
                request,
                code="scope_predicate_denominator_mismatch",
                status="rejected",
                reason="The resolver did not return the complete three-predicate denominator.",
            )
        resolved: list[PersistedScopePredicateEvidence] = []
        try:
            for handle in supplied:
                live = _load_scope_predicate_evidence(
                    self.store,
                    handle.predicate_evidence_ref,
                )
                if live != handle:
                    raise _ScopeFailureError("scope_predicate_profile_mismatch")
                resolved.append(live)
        except (OSError, RuntimeError, TypeError, ValueError, _ScopeFailureError) as exc:
            code: ScopeAdjudicationNonReceiptCode = "scope_predicate_profile_mismatch"
            if isinstance(exc, _ScopeFailureError):
                code = exc.code
            return _non_receipt(
                request,
                code=code,
                status="rejected",
                reason="Predicate evidence could not be independently re-resolved.",
                decisive_evidence_refs=tuple(
                    row.predicate_evidence_ref for row in supplied
                ),
            )

        by_predicate = {row.statement.predicate: row for row in resolved}
        if tuple(by_predicate) != _PREDICATE_ORDER:
            return _non_receipt(
                request,
                code="scope_predicate_denominator_mismatch",
                status="rejected",
                reason="Predicate identities or order do not match the ratified denominator.",
                decisive_evidence_refs=tuple(
                    row.predicate_evidence_ref for row in resolved
                ),
            )
        for row in resolved:
            statement = row.statement
            if statement.plane is not request.plane:
                return _non_receipt(
                    request,
                    code="scope_predicate_plane_mismatch",
                    status="rejected",
                    reason="One predicate crosses into a different custody plane.",
                    decisive_evidence_refs=(row.predicate_evidence_ref,),
                )
            if (
                statement.candidate_function_id != request.candidate_function_id
                or statement.target_ref != request.target_ref
                or statement.target_content_hash != request.target_content_hash
                or statement.rule_version_ref != request.rule_version_ref
                or statement.rule_version_content_hash != request.rule_version_content_hash
                or statement.authority_purpose != request.authority_purpose
                or statement.verifier_provenance_ref
                != self.appointed_verifier_provenance_ref
                or statement.verifier_provenance_content_hash
                != str(self.appointed_verifier_provenance_ref.artifact_id)
                or statement.observed_at > request.valid_at
            ):
                return _non_receipt(
                    request,
                    code="scope_predicate_binding_mismatch",
                    status="rejected",
                    reason="Predicate evidence does not bind the requested adjudication.",
                    decisive_evidence_refs=(row.predicate_evidence_ref,),
                )
        return tuple(resolved)


@dataclass(frozen=True, slots=True)
class ScopeAdjudicationNonReceiptCodeMarker:
    """Internal marker for a required but unestablished predicate."""

    code: ScopeAdjudicationNonReceiptCode


class _ScopeFailureError(ValueError):
    def __init__(self, code: ScopeAdjudicationNonReceiptCode) -> None:
        super().__init__(code)
        self.code = code


def persist_scope_predicate_evidence(
    store: ArtifactStore,
    statement: ScopePredicateEvidence,
) -> PersistedScopePredicateEvidence:
    """Persist and independently reload one verifier-emitted predicate statement.

    Args:
        store: Content-addressed artifact store shared with the adjudication producer.
        statement: Strict predicate statement emitted by the appointed verifier.

    Returns:
        Content-bound evidence handle after manifest and byte-level readback.
    """

    for ref, content_hash in (
        (statement.target_ref, statement.target_content_hash),
        (statement.evidence_ref, statement.evidence_content_hash),
        (
            statement.verifier_provenance_ref,
            statement.verifier_provenance_content_hash,
        ),
        (statement.rule_version_ref, statement.rule_version_content_hash),
    ):
        _verify_bound_ref(store, ref, content_hash)
    inputs = _predicate_inputs(statement)
    ref = store.put_json(
        statement,
        ArtifactWriteOptions(
            kind=SCOPE_PREDICATE_EVIDENCE_KIND,
            media_type="application/json",
            schema=_predicate_schema(),
            inputs=inputs,
            canon=CanonInfo.from_spec(SCOPE_ADJUDICATION_CANON_SPEC),
        ),
        canon_spec=SCOPE_ADJUDICATION_CANON_SPEC,
    )
    persisted = _load_scope_predicate_evidence(store, ref)
    if persisted.statement != statement:
        raise ValueError("scope_predicate_evidence_readback_mismatch")
    return persisted


def consume_scope_adjudication_record(
    store: ArtifactStore,
    persisted: PersistedScopeAdjudicationRecord,
    *,
    expected_candidate_function_id: str,
    expected_target_ref: ArtifactRef,
    expected_target_content_hash: Digest,
    expected_plane: ScopeAdjudicationPlane,
    expected_rule_version_ref: ArtifactRef,
    expected_authority_purpose: ScopeAdjudicationAuthorityPurpose,
    appointed_verifier_provenance_ref: ArtifactRef,
    valid_at_time: datetime,
    as_known_at: datetime,
) -> ScopeAdjudicationRecord:
    """Re-resolve and replay an exact scope record before authority-grade use.

    Args:
        store: Content-addressed store holding the record and all direct evidence.
        persisted: Producer handle; its parsed sidecar is not trusted without reload.
        expected_candidate_function_id: Exact candidate identity expected by the consumer.
        expected_target_ref: Current target artifact reference.
        expected_target_content_hash: Current target byte identity.
        expected_plane: Single custody plane expected by the consumer.
        expected_rule_version_ref: Exact ratified rule artifact expected by the consumer.
        expected_authority_purpose: Purpose for which the ruling will be consumed.
        appointed_verifier_provenance_ref: Verifier appointment trusted by the consumer.
        valid_at_time: World-valid time at which the ruling must be applicable.
        as_known_at: Knowledge cutoff by which the persisted ruling must have existed.

    Returns:
        The independently re-resolved record.

    Raises:
        ValueError: If any profile, content, scope, rule, time, or replay binding differs.
    """

    _require_aware(valid_at_time, field="valid_at_time")
    _require_aware(as_known_at, field="as_known_at")
    live = _load_scope_adjudication_record(store, persisted.record_ref)
    if live != persisted:
        raise ValueError("scope_adjudication_record_handle_mismatch")
    record = live.record
    if (
        record.candidate_function_id != expected_candidate_function_id
        or record.target_ref != expected_target_ref
        or record.target_content_hash != expected_target_content_hash
        or record.plane is not expected_plane
        or record.rule_version_ref != expected_rule_version_ref
        or record.authority_purpose != expected_authority_purpose
        or record.appointed_verifier_provenance_ref
        != appointed_verifier_provenance_ref
        or not (record.valid_at <= valid_at_time < record.reconsider_on)
        or record.recorded_at > as_known_at
    ):
        raise ValueError("scope_adjudication_consumer_binding_mismatch")
    _verify_bound_ref(store, record.target_ref, record.target_content_hash)
    _verify_bound_ref(store, record.rule_version_ref, record.rule_version_content_hash)
    _verify_bound_ref(
        store,
        record.appointed_verifier_provenance_ref,
        record.appointed_verifier_provenance_content_hash,
    )
    _verify_bound_ref(
        store,
        record.producer_provenance_ref,
        record.producer_provenance_content_hash,
    )
    if record.integration_contract_ref is not None:
        if record.integration_contract_content_hash is None:
            raise ValueError("scope_integration_contract_binding_mismatch")
        _verify_bound_ref(
            store,
            record.integration_contract_ref,
            record.integration_contract_content_hash,
        )
    if record.prior_record_ref is not None:
        if record.prior_record_content_hash is None:
            raise ValueError("scope_prior_record_binding_mismatch")
        _verify_bound_ref(
            store,
            record.prior_record_ref,
            record.prior_record_content_hash,
        )

    evidence_rows = tuple(
        _load_scope_predicate_evidence(store, ref)
        for ref in record.predicate_evidence_refs
    )
    if tuple(row.predicate_evidence_content_hash for row in evidence_rows) != (
        record.predicate_evidence_content_hashes
    ):
        raise ValueError("scope_adjudication_predicate_hash_denominator_mismatch")
    for row in evidence_rows:
        statement = row.statement
        if (
            statement.candidate_function_id != record.candidate_function_id
            or statement.target_ref != record.target_ref
            or statement.target_content_hash != record.target_content_hash
            or statement.plane is not record.plane
            or statement.rule_version_ref != record.rule_version_ref
            or statement.rule_version_content_hash != record.rule_version_content_hash
            or statement.verifier_provenance_ref
            != record.appointed_verifier_provenance_ref
            or statement.verifier_provenance_content_hash
            != record.appointed_verifier_provenance_content_hash
            or statement.authority_purpose != record.authority_purpose
        ):
            raise ValueError("scope_adjudication_predicate_binding_mismatch")
    replayed_ruling = _derive_ruling(evidence_rows)
    if (
        isinstance(replayed_ruling, ScopeAdjudicationNonReceiptCodeMarker)
        or replayed_ruling is not record.ruling
        or _DISPOSITION_BY_RULING[record.ruling] is not record.disposition
    ):
        raise ValueError("scope_adjudication_ruling_replay_mismatch")
    return record


def _derive_ruling(
    evidence_rows: tuple[PersistedScopePredicateEvidence, ...],
) -> ScopeAdjudicationRuling | ScopeAdjudicationNonReceiptCodeMarker:
    by_predicate = {row.statement.predicate: row.statement for row in evidence_rows}
    for predicate in _PREDICATE_ORDER:
        statement = by_predicate[predicate]
        if statement.predicate_class not in _ADMITTED_PREDICATE_CLASSES:
            return ScopeAdjudicationNonReceiptCodeMarker(
                code="scope_predicate_not_established"
            )
        if statement.outcome:
            return _RULING_BY_TRUE_PREDICATE[predicate]
    return ScopeAdjudicationRuling.OUT_OF_SCOPE


def _ruling_contract_is_complete(
    request: ScopeAdjudicationRequest,
    ruling: ScopeAdjudicationRuling,
) -> bool:
    has_external_contract = (
        request.external_owner is not None and request.integration_contract_ref is not None
    )
    if ruling is ScopeAdjudicationRuling.OWN:
        return not has_external_contract
    return has_external_contract


def _record_id(
    *,
    request: ScopeAdjudicationRequest,
    evidence_rows: tuple[PersistedScopePredicateEvidence, ...],
    ruling: ScopeAdjudicationRuling,
) -> str:
    payload = {
        "request": request,
        "predicate_evidence_refs": [
            row.predicate_evidence_ref for row in evidence_rows
        ],
        "ruling": ruling,
    }
    digest = hashlib.sha256(
        to_canonical_bytes(payload, SCOPE_ADJUDICATION_CANON_SPEC)
    ).hexdigest()[:24]
    return f"scope_adjudication_{digest}"


def _persist_scope_adjudication_record(
    store: ArtifactStore,
    record: ScopeAdjudicationRecord,
) -> PersistedScopeAdjudicationRecord:
    ref = store.put_json(
        record,
        ArtifactWriteOptions(
            kind=SCOPE_ADJUDICATION_RECORD_KIND,
            media_type="application/json",
            schema=_record_schema(),
            inputs=_record_inputs(record),
            canon=CanonInfo.from_spec(SCOPE_ADJUDICATION_CANON_SPEC),
        ),
        canon_spec=SCOPE_ADJUDICATION_CANON_SPEC,
    )
    persisted = _load_scope_adjudication_record(store, ref)
    if persisted.record != record:
        raise ValueError("scope_adjudication_record_readback_mismatch")
    return persisted


def _load_scope_predicate_evidence(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> PersistedScopePredicateEvidence:
    statement, manifest = _load_profiled_model(
        store,
        ref,
        expected_kind=SCOPE_PREDICATE_EVIDENCE_KIND,
        expected_schema=_predicate_schema(),
        model=ScopePredicateEvidence,
        mismatch_code="scope_predicate_profile_mismatch",
    )
    if not isinstance(statement, ScopePredicateEvidence):
        raise ValueError("scope_predicate_profile_mismatch")
    if manifest.inputs != _predicate_inputs(statement):
        raise ValueError("scope_predicate_profile_mismatch")
    return PersistedScopePredicateEvidence(
        predicate_evidence_ref=ref,
        predicate_evidence_content_hash=str(ref.artifact_id),
        statement=statement,
    )


def _load_scope_adjudication_record(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> PersistedScopeAdjudicationRecord:
    record, manifest = _load_profiled_model(
        store,
        ref,
        expected_kind=SCOPE_ADJUDICATION_RECORD_KIND,
        expected_schema=_record_schema(),
        model=ScopeAdjudicationRecord,
        mismatch_code="scope_adjudication_record_profile_mismatch",
    )
    if not isinstance(record, ScopeAdjudicationRecord):
        raise ValueError("scope_adjudication_record_profile_mismatch")
    if manifest.inputs != _record_inputs(record):
        raise ValueError("scope_adjudication_record_profile_mismatch")
    return PersistedScopeAdjudicationRecord(
        record_ref=ref,
        record_content_hash=str(ref.artifact_id),
        record=record,
    )


def _load_profiled_model(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    expected_kind: str,
    expected_schema: SchemaInfo,
    model: type[ScopePredicateEvidence] | type[ScopeAdjudicationRecord],
    mismatch_code: str,
) -> tuple[ScopePredicateEvidence | ScopeAdjudicationRecord, ArtifactManifest]:
    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    expected_canon = CanonInfo.from_spec(SCOPE_ADJUDICATION_CANON_SPEC)
    if (
        not report.ok
        or observed_hash != str(ref.artifact_id)
        or ref.kind != expected_kind
        or ref.media_type != "application/json"
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema != expected_schema
        or manifest.canon != expected_canon
    ):
        raise ValueError(mismatch_code)
    parsed = model.model_validate(from_canonical_bytes(raw))
    if to_canonical_bytes(parsed, SCOPE_ADJUDICATION_CANON_SPEC) != raw:
        raise ValueError(mismatch_code)
    return parsed, manifest


def _verify_bound_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    expected_content_hash: str,
) -> None:
    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    if (
        not report.ok
        or expected_content_hash != str(ref.artifact_id)
        or observed_hash != expected_content_hash
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
    ):
        raise ValueError("scope_bound_artifact_profile_mismatch")


def _predicate_inputs(statement: ScopePredicateEvidence) -> list[InputRef]:
    return [
        InputRef(artifact_id=statement.target_ref.artifact_id, role="scope_target"),
        InputRef(artifact_id=statement.evidence_ref.artifact_id, role="predicate_evidence"),
        InputRef(
            artifact_id=statement.verifier_provenance_ref.artifact_id,
            role="verifier_provenance",
        ),
        InputRef(artifact_id=statement.rule_version_ref.artifact_id, role="rule_version"),
    ]


def _record_inputs(record: ScopeAdjudicationRecord) -> list[InputRef]:
    inputs = [
        InputRef(artifact_id=record.target_ref.artifact_id, role="scope_target"),
        InputRef(artifact_id=record.rule_version_ref.artifact_id, role="rule_version"),
        InputRef(
            artifact_id=record.appointed_verifier_provenance_ref.artifact_id,
            role="appointed_verifier_provenance",
        ),
        InputRef(
            artifact_id=record.producer_provenance_ref.artifact_id,
            role="producer_provenance",
        ),
        *(
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"predicate_evidence[{index}]",
            )
            for index, ref in enumerate(record.predicate_evidence_refs)
        ),
    ]
    if record.integration_contract_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=record.integration_contract_ref.artifact_id,
                role="integration_contract",
            )
        )
    if record.prior_record_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=record.prior_record_ref.artifact_id,
                role="prior_scope_adjudication",
            )
        )
    return inputs


def _predicate_schema() -> SchemaInfo:
    return SchemaInfo(
        name=SCOPE_PREDICATE_EVIDENCE_SCHEMA_NAME,
        version=SCOPE_PREDICATE_EVIDENCE_SCHEMA_VERSION,
    )


def _record_schema() -> SchemaInfo:
    return SchemaInfo(
        name=SCOPE_ADJUDICATION_RECORD_SCHEMA_NAME,
        version=SCOPE_ADJUDICATION_RECORD_SCHEMA_VERSION,
    )


def _non_receipt(
    request: ScopeAdjudicationRequest,
    *,
    code: ScopeAdjudicationNonReceiptCode,
    status: Literal["not_established", "rejected"],
    reason: str,
    decisive_evidence_refs: tuple[ArtifactRef, ...] = (),
) -> ScopeAdjudicationNonReceipt:
    return ScopeAdjudicationNonReceipt(
        status=status,
        code=code,
        candidate_function_id=request.candidate_function_id,
        plane=request.plane,
        reason=reason,
        decisive_evidence_refs=decisive_evidence_refs,
    )


def _require_ref_hash(ref: ArtifactRef, content_hash: str, *, code: str) -> None:
    if content_hash != str(ref.artifact_id):
        raise ValueError(code)


def _require_optional_ref_hash(
    ref: ArtifactRef | None,
    content_hash: str | None,
    *,
    code: str,
) -> None:
    if (ref is None) != (content_hash is None):
        raise ValueError(code)
    if ref is not None and content_hash != str(ref.artifact_id):
        raise ValueError(code)


def _require_aware(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"scope_{field}_must_be_timezone_aware")


__all__ = [
    "SCOPE_ADJUDICATION_AUTHORITY_PURPOSE",
    "SCOPE_ADJUDICATION_CANON_SPEC",
    "SCOPE_ADJUDICATION_RECORD_KIND",
    "SCOPE_ADJUDICATION_RECORD_SCHEMA_NAME",
    "SCOPE_ADJUDICATION_RECORD_SCHEMA_VERSION",
    "SCOPE_PREDICATE_EVIDENCE_KIND",
    "SCOPE_PREDICATE_EVIDENCE_SCHEMA_NAME",
    "SCOPE_PREDICATE_EVIDENCE_SCHEMA_VERSION",
    "PersistedScopeAdjudicationRecord",
    "PersistedScopePredicateEvidence",
    "ScopeAdjudicationAuthorityBoundary",
    "ScopeAdjudicationDisposition",
    "ScopeAdjudicationNonReceipt",
    "ScopeAdjudicationPlane",
    "ScopeAdjudicationPredicate",
    "ScopeAdjudicationProducer",
    "ScopeAdjudicationRecord",
    "ScopeAdjudicationRequest",
    "ScopeAdjudicationRuling",
    "ScopePredicateEvidence",
    "ScopePredicateEvidenceResolver",
    "consume_scope_adjudication_record",
    "persist_scope_predicate_evidence",
]
