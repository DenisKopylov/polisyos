"""Negative-only obligation coverage derived from verified ledger identities.

This module never asserts completeness.  It distinguishes an unresolved open
world from a concrete omission admitted through a content-addressed verifier
receipt, and binds both states to one prospective protected action.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import Ed25519Verifier, FileSystemCAS
from polisyos.core.canon import CanonSpec, content_hash, fingerprint
from polisyos.pdc import PromotionObligationClass
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    ConfidenceRiskBudgetScope,
    RationalSpec,
)

COVERAGE_SCHEMA_VERSION = "policyos.runtime.obligation_coverage.v1"
WITNESS_SCHEMA_VERSION = "policyos.runtime.obligation_coverage.witness.v1"
WITNESS_SOURCE_SCHEMA_VERSION = (
    "policyos.runtime.obligation_coverage.witness-source.v1"
)
WITNESS_REPLAY_RULE_VERSION = (
    "policyos.runtime.obligation_coverage.witness-replay.v1"
)
COVERAGE_RULE_VERSION = "policyos.runtime.obligation_coverage.negative.v1"
DECLARED_SET_RIDER = "≤ δ relative to the declared obligation set"
LOCALITY_RIDER = (
    "Local accounting for this exact confidence scope; no family or sequence-level "
    "claim is asserted."
)
_WITNESS_KIND = "obligation_coverage_witness_verification"
_WITNESS_SCHEMA_NAME = "polisyos.runtime.obligation-coverage-witness-verification"
_WITNESS_SCHEMA_VERSION = "1.0.0"
_WITNESS_VERIFIER = "polisyos.pdc.coverage-witness-verifier"
_WITNESS_SOURCE_KIND = "obligation_coverage_witness_source"
_WITNESS_SOURCE_SCHEMA_NAME = "polisyos.runtime.obligation-coverage-witness-source"
_WITNESS_SOURCE_SCHEMA_VERSION = "1.0.0"
_CANON = CanonSpec(exclude_none=False)


class _StrictModel(BaseModel):
    """Strict immutable base for public C01 contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CoverageAssessment(StrEnum):
    """The two negative coverage states available to a protected action."""

    KNOWN_INCOMPLETE = "known_incomplete"
    OPEN_WORLD_UNRESOLVED = "open_world_unresolved"


class CoverageReasonCode(StrEnum):
    """Closed reasons derived from a valid negative coverage envelope."""

    OPEN_WORLD = "DS17-COVERAGE-OPEN-WORLD"
    KNOWN_INCOMPLETE = "DS17-COVERAGE-KNOWN-INCOMPLETE"
    SEARCH_NOT_ESTABLISHED = "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED"
    EXCLUSIONS_NOT_ESTABLISHED = "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED"
    INDEPENDENCE_MISSING = "DS17-COVERAGE-INDEPENDENCE-MISSING"


class CoverageSourceIdentity(_StrictModel):
    """Explicit content and verifier identity for one validated source."""

    source_role: Literal["canonical_registry", "semantic_ledger"]
    source_ref: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_ref: str = Field(min_length=1)
    availability_state: Literal["available_typed_input"]
    admission_state: Literal[
        "canonical_registry_validated",
        "worker_admission_not_established",
    ]

    @model_validator(mode="after")
    def _role_has_honest_admission(self) -> Self:
        expected = (
            "canonical_registry_validated"
            if self.source_role == "canonical_registry"
            else "worker_admission_not_established"
        )
        if self.admission_state != expected:
            raise ValueError("coverage_source_role_admission_mismatch")
        return self


class CoverageUnknownRemainder(_StrictModel):
    """Honest nonnumeric statement of what has not been searched or calibrated."""

    kind: Literal["independent_coverage_producer_missing"]
    cardinality: Literal["not_estimated"]
    probability: Literal["not_calibrated"]


class CoverageOmissionIssue(_StrictModel):
    """One source-owned decisive omission identity."""

    code: Literal["decisive_obligation_omitted"]
    obligation_instance_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CoverageWitnessSourceArtifact(_StrictModel):
    """Resolved source facts replayed before an omission witness is admitted."""

    schema_version: Literal[WITNESS_SOURCE_SCHEMA_VERSION]
    risk_scope: ConfidenceRiskBudgetScope
    assessment_key: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    protected_action_id: str | None = Field(default=None, min_length=1)
    authority_issue_codes: tuple[Literal["decisive_obligation_omitted"], ...]
    authority_issues: tuple[CoverageOmissionIssue, ...]
    authority_status: Literal["red"]
    class_denominator_count: int = Field(gt=0)
    class_denominator_status: Literal["green"]
    mutation_id: str = Field(min_length=1)
    removed_instance_count: Literal[1]
    removed_obligation_instance_id: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$"
    )
    removed_obligation_role: Literal["decisive_predicate"]
    removed_source_obligation_ref: str = Field(min_length=1)
    verification_session_provenance: Literal["verification"]
    producer_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _source_denominator_and_issue_are_exact(self) -> Self:
        if (
            self.class_denominator_count != len(PromotionObligationClass)
            or self.authority_issue_codes != ("decisive_obligation_omitted",)
            or len(self.authority_issues) != 1
            or self.authority_issues[0].obligation_instance_id
            != self.removed_obligation_instance_id
        ):
            raise ValueError("coverage_witness_source_issue_binding_invalid")
        return self


class CoverageWitnessVerificationReceipt(_StrictModel):
    """Verifier-produced admission receipt for one decisive omission."""

    schema_version: Literal[WITNESS_SCHEMA_VERSION]
    assessment_key: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    owner_scope_key: str = Field(min_length=1)
    protected_action_id: str = Field(min_length=1)
    issue_code: Literal["decisive_obligation_omitted"]
    obligation_instance_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replay_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_provenance_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    producer_ref: str = Field(min_length=1)
    verifier_ref: Literal[_WITNESS_VERIFIER]
    verification_provenance: Literal["independent_recompute"]
    challengeable: Literal[True]
    verified: Literal[True]

    @model_validator(mode="after")
    def _independent_verifier(self) -> Self:
        if self.producer_ref == self.verifier_ref:
            raise ValueError("coverage_witness_producer_verifier_not_independent")
        return self


class ObligationCoverageEnvelope(_StrictModel):
    """Content-bound, negative-only coverage envelope for one protected action."""

    schema_version: Literal[COVERAGE_SCHEMA_VERSION]
    rule_version: Literal[COVERAGE_RULE_VERSION]
    assessment: CoverageAssessment
    reason_codes: tuple[CoverageReasonCode, ...]
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    owner_scope_key: str = Field(min_length=1)
    declared_scope: ConfidenceRiskBudgetScope
    declared_obligation_classes: tuple[PromotionObligationClass, ...]
    authorized_audiences: tuple[Literal["reviewer", "expert", "machine"], ...]
    protected_action_id: str = Field(min_length=1)
    assessment_key: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    delta: RationalSpec
    source_identities: tuple[CoverageSourceIdentity, CoverageSourceIdentity]
    searched_sources: tuple[()] = ()
    search_basis_state: Literal["not_established"] = "not_established"
    exclusions: tuple[()] = ()
    exclusion_basis_state: Literal["not_established"] = "not_established"
    unknown_remainder: CoverageUnknownRemainder
    witness_refs: tuple[str, ...]
    maintained_assumptions: tuple[
        Literal["obligation_completeness", "validator_soundness"], ...
    ]
    obligation_language_version: str = Field(min_length=1)
    obligation_schema_ref: str = Field(min_length=1)
    obligation_rule_ref: str = Field(min_length=1)
    source_cutoff_state: Literal["not_established"]
    review_state: Literal["not_issued"]
    expiry_state: Literal["not_issued"]
    ttl_state: Literal[
        "not_issued_known_incomplete",
        "not_issued_open_world_unresolved",
    ]
    authority_purpose: str = Field(min_length=1)
    authoritative_for: tuple[
        Literal["conditionality_disclosure", "declared_set_accounting"], ...
    ]
    may_not_use_for: tuple[
        Literal[
            "promotion_authority",
            "publication_authority",
            "bounded_completeness",
            "world_completeness",
        ],
        ...,
    ]
    challenge_route_state: Literal["not_established"]
    declared_set_rider: Literal[DECLARED_SET_RIDER]
    locality_rider: Literal[LOCALITY_RIDER]
    envelope_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    envelope_ref: str = Field(pattern=r"^coverage-envelope:sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _negative_state_is_derived(self) -> Self:
        if len({row.source_role for row in self.source_identities}) != 2:
            raise ValueError("coverage_source_identity_denominator_invalid")
        if self.declared_scope.scope_id != self.scope_id:
            raise ValueError("coverage_declared_scope_binding_mismatch")
        if (
            len(self.declared_obligation_classes) != len(PromotionObligationClass)
            or len(set(self.declared_obligation_classes))
            != len(self.declared_obligation_classes)
            or set(self.declared_obligation_classes) != set(PromotionObligationClass)
        ):
            raise ValueError("coverage_declared_obligation_denominator_invalid")
        expected = (
            CoverageAssessment.KNOWN_INCOMPLETE
            if self.witness_refs
            else CoverageAssessment.OPEN_WORLD_UNRESOLVED
        )
        if self.assessment is not expected:
            raise ValueError("coverage_assessment_not_derived")
        expected_reasons = (
            (
                CoverageReasonCode.KNOWN_INCOMPLETE
                if self.witness_refs
                else CoverageReasonCode.OPEN_WORLD
            ),
            CoverageReasonCode.SEARCH_NOT_ESTABLISHED,
            CoverageReasonCode.EXCLUSIONS_NOT_ESTABLISHED,
            CoverageReasonCode.INDEPENDENCE_MISSING,
        )
        if self.reason_codes != expected_reasons:
            raise ValueError("coverage_reason_codes_not_derived")
        expected_ttl = (
            "not_issued_known_incomplete"
            if self.witness_refs
            else "not_issued_open_world_unresolved"
        )
        if self.ttl_state != expected_ttl:
            raise ValueError("coverage_ttl_arm_mismatch")
        body = self.model_dump(mode="json", exclude={"envelope_hash", "envelope_ref"})
        expected_hash = fingerprint(body, prefix=True, canon_spec=_CANON)
        if self.envelope_hash != expected_hash:
            raise ValueError("coverage_envelope_hash_mismatch")
        if self.envelope_ref != f"coverage-envelope:{expected_hash}":
            raise ValueError("coverage_envelope_ref_mismatch")
        return self


class ProtectedActionEvaluation(_StrictModel):
    """Fail-closed result for a protected action under negative coverage."""

    action_id: str = Field(min_length=1)
    presented_claim_scope: str = Field(min_length=1)
    status: Literal["blocked"]
    assessment: CoverageAssessment
    coverage_envelope_ref: str = Field(
        pattern=r"^coverage-envelope:sha256:[0-9a-f]{64}$"
    )


def build_coverage_envelope(
    *,
    registry: ConfidenceLedgerRegistry,
    semantic_ledger: ConfidenceLedgerSemanticReceiptProjection,
    semantic_source_ref: str,
    semantic_source_verifier_ref: str,
    protected_action_id: str,
    witness_store: FileSystemCAS | None = None,
    witness_verifier: Ed25519Verifier | None = None,
    witness_refs: tuple[str, ...] = (),
) -> ObligationCoverageEnvelope:
    """Derive one negative envelope from typed sources and verified CAS witnesses."""

    if not isinstance(registry, ConfidenceLedgerRegistry):
        raise TypeError("coverage_registry_must_be_typed")
    if not isinstance(semantic_ledger, ConfidenceLedgerSemanticReceiptProjection):
        raise TypeError("coverage_semantic_ledger_must_be_typed")
    if semantic_ledger.registry_content_hash != registry.content_hash:
        raise ValueError("coverage_registry_semantic_binding_mismatch")
    if semantic_ledger.scope_id != semantic_ledger.risk_scope.scope_id:
        raise ValueError("coverage_scope_binding_mismatch")
    if not protected_action_id:
        raise ValueError("coverage_protected_action_missing")
    if not semantic_source_ref or not semantic_source_verifier_ref:
        raise ValueError("coverage_semantic_source_identity_missing")

    sources = (
        CoverageSourceIdentity(
            source_role="canonical_registry",
            source_ref="architecture/production_quality/confidence_ledger.toml",
            content_hash=registry.content_hash,
            verifier_ref="polisyos.runtime.quality.confidence_ledger.load_confidence_ledger_registry",
            availability_state="available_typed_input",
            admission_state="canonical_registry_validated",
        ),
        CoverageSourceIdentity(
            source_role="semantic_ledger",
            source_ref=semantic_source_ref,
            content_hash=semantic_ledger.projection_hash,
            verifier_ref=semantic_source_verifier_ref,
            availability_state="available_typed_input",
            admission_state="worker_admission_not_established",
        ),
    )
    assessment_key = _derive_assessment_key(
        scope_id=semantic_ledger.scope_id,
        owner_scope_key=semantic_ledger.risk_scope.owner_scope_key,
        protected_action_id=protected_action_id,
        sources=sources,
    )
    admitted = _resolve_witnesses(
        store=witness_store,
        verifier=witness_verifier,
        refs=witness_refs,
        assessment_key=assessment_key,
        scope_id=semantic_ledger.scope_id,
        owner_scope_key=semantic_ledger.risk_scope.owner_scope_key,
        protected_action_id=protected_action_id,
    )
    body = {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "rule_version": COVERAGE_RULE_VERSION,
        "assessment": (
            CoverageAssessment.KNOWN_INCOMPLETE
            if admitted
            else CoverageAssessment.OPEN_WORLD_UNRESOLVED
        ),
        "reason_codes": (
            CoverageReasonCode.KNOWN_INCOMPLETE
            if admitted
            else CoverageReasonCode.OPEN_WORLD,
            CoverageReasonCode.SEARCH_NOT_ESTABLISHED,
            CoverageReasonCode.EXCLUSIONS_NOT_ESTABLISHED,
            CoverageReasonCode.INDEPENDENCE_MISSING,
        ),
        "scope_id": semantic_ledger.scope_id,
        "owner_scope_key": semantic_ledger.risk_scope.owner_scope_key,
        "declared_scope": semantic_ledger.risk_scope,
        "declared_obligation_classes": tuple(registry.obligation_weights),
        "authorized_audiences": ("reviewer", "expert", "machine"),
        "protected_action_id": protected_action_id,
        "assessment_key": assessment_key,
        "delta": registry.policy.delta,
        "source_identities": sources,
        "searched_sources": (),
        "search_basis_state": "not_established",
        "exclusions": (),
        "exclusion_basis_state": "not_established",
        "unknown_remainder": CoverageUnknownRemainder(
            kind="independent_coverage_producer_missing",
            cardinality="not_estimated",
            probability="not_calibrated",
        ),
        "witness_refs": admitted,
        "maintained_assumptions": semantic_ledger.maintained_assumptions,
        "obligation_language_version": registry.schema_version,
        "obligation_schema_ref": semantic_ledger.risk_scope.schema_ref
        or registry.schema_version,
        "obligation_rule_ref": semantic_ledger.risk_scope.rule_ref
        or COVERAGE_RULE_VERSION,
        "source_cutoff_state": "not_established",
        "review_state": "not_issued",
        "expiry_state": "not_issued",
        "ttl_state": (
            "not_issued_known_incomplete"
            if admitted
            else "not_issued_open_world_unresolved"
        ),
        "authority_purpose": semantic_ledger.risk_scope.authority_purpose,
        "authoritative_for": (
            "conditionality_disclosure",
            "declared_set_accounting",
        ),
        "may_not_use_for": (
            "promotion_authority",
            "publication_authority",
            "bounded_completeness",
            "world_completeness",
        ),
        "challenge_route_state": "not_established",
        "declared_set_rider": DECLARED_SET_RIDER,
        "locality_rider": LOCALITY_RIDER,
    }
    envelope_hash = fingerprint(body, prefix=True, canon_spec=_CANON)
    return ObligationCoverageEnvelope.model_validate(
        {
            **body,
            "envelope_hash": envelope_hash,
            "envelope_ref": f"coverage-envelope:{envelope_hash}",
        }
    )


def evaluate_protected_action(
    *, envelope: ObligationCoverageEnvelope, action_id: str, presented_claim_scope: str
) -> ProtectedActionEvaluation:
    """Block a negative envelope; narrowing never changes the admitted action."""

    if not isinstance(envelope, ObligationCoverageEnvelope):
        raise TypeError("coverage_envelope_must_be_typed")
    if action_id != envelope.protected_action_id:
        raise ValueError("coverage_action_requires_new_prospective_envelope")
    return ProtectedActionEvaluation(
        action_id=action_id,
        presented_claim_scope=presented_claim_scope,
        status="blocked",
        assessment=envelope.assessment,
        coverage_envelope_ref=envelope.envelope_ref,
    )


def reauthenticate_coverage_envelope(
    *,
    envelope: ObligationCoverageEnvelope,
    witness_store: FileSystemCAS | None = None,
    witness_verifier: Ed25519Verifier | None = None,
) -> ObligationCoverageEnvelope:
    """Re-resolve every witness before a downstream boundary trusts its arm."""

    if not isinstance(envelope, ObligationCoverageEnvelope):
        raise TypeError("coverage_envelope_must_be_typed")
    expected_key = _derive_assessment_key(
        scope_id=envelope.scope_id,
        owner_scope_key=envelope.owner_scope_key,
        protected_action_id=envelope.protected_action_id,
        sources=envelope.source_identities,
    )
    if envelope.assessment_key != expected_key:
        raise ValueError("coverage_envelope_assessment_key_mismatch")
    admitted = _resolve_witnesses(
        store=witness_store,
        verifier=witness_verifier,
        refs=envelope.witness_refs,
        assessment_key=expected_key,
        scope_id=envelope.scope_id,
        owner_scope_key=envelope.owner_scope_key,
        protected_action_id=envelope.protected_action_id,
    )
    if admitted != envelope.witness_refs:
        raise ValueError("coverage_envelope_witness_admission_mismatch")
    return envelope


def _derive_assessment_key(
    *,
    scope_id: str,
    owner_scope_key: str,
    protected_action_id: str,
    sources: tuple[CoverageSourceIdentity, CoverageSourceIdentity],
) -> str:
    return fingerprint(
        {
            "rule_version": COVERAGE_RULE_VERSION,
            "scope_id": scope_id,
            "owner_scope_key": owner_scope_key,
            "protected_action_id": protected_action_id,
            "sources": [row.model_dump(mode="json") for row in sources],
        },
        prefix=True,
        canon_spec=_CANON,
    )


def _resolve_witnesses(
    *,
    store: FileSystemCAS | None,
    verifier: Ed25519Verifier | None,
    refs: tuple[str, ...],
    assessment_key: str,
    scope_id: str,
    owner_scope_key: str,
    protected_action_id: str,
) -> tuple[str, ...]:
    if (
        not isinstance(refs, tuple)
        or any(not isinstance(ref, str) for ref in refs)
        or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", ref) for ref in refs)
    ):
        raise TypeError("coverage_witness_references_must_be_string_tuple")
    if len(refs) != len(set(refs)):
        raise ValueError("coverage_witness_duplicate_reference")
    if refs and not isinstance(store, FileSystemCAS):
        raise TypeError("coverage_witness_CAS_resolver_required")
    if refs and not isinstance(verifier, Ed25519Verifier):
        raise TypeError("coverage_witness_signature_verifier_required")
    if not refs:
        return ()
    if store is None:  # narrowed above; retained as a runtime boundary.
        raise TypeError("coverage_witness_CAS_resolver_required")
    if verifier is None:  # narrowed above; retained as a runtime boundary.
        raise TypeError("coverage_witness_signature_verifier_required")
    admitted: list[str] = []
    for ref in refs:
        report = store.verify(ref)
        if not report.ok:
            raise ValueError("coverage_witness_CAS_verification_failed")
        receipt_signature = store.verify_signature(
            ref,
            verifier,
            strict_identity=True,
        )
        if (
            not receipt_signature.ok
            or receipt_signature.expected_identity != _WITNESS_VERIFIER
            or receipt_signature.signer_identity != _WITNESS_VERIFIER
        ):
            raise ValueError("coverage_witness_verifier_signature_invalid")
        manifest = store.get_manifest(ref)
        producer = manifest.producer
        schema = manifest.artifact_schema
        if (
            manifest.kind != _WITNESS_KIND
            or schema is None
            or schema.name != _WITNESS_SCHEMA_NAME
            or schema.version != _WITNESS_SCHEMA_VERSION
            or producer is None
            or str(producer.component) != _WITNESS_VERIFIER
        ):
            raise ValueError("coverage_witness_verifier_provenance_invalid")
        receipt = CoverageWitnessVerificationReceipt.model_validate(
            json.loads(store.get_bytes(ref))
        )
        if (
            receipt.assessment_key != assessment_key
            or receipt.scope_id != scope_id
            or receipt.owner_scope_key != owner_scope_key
            or receipt.protected_action_id != protected_action_id
        ):
            raise ValueError("coverage_witness_scope_or_assessment_mismatch")
        if receipt.verifier_ref != str(producer.component):
            raise ValueError("coverage_witness_manifest_verifier_mismatch")
        try:
            source_report = store.verify(receipt.source_artifact_ref)
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise ValueError("coverage_witness_source_CAS_verification_failed") from exc
        if not source_report.ok:
            raise ValueError("coverage_witness_source_CAS_verification_failed")
        source_manifest = store.get_manifest(receipt.source_artifact_ref)
        source_schema = source_manifest.artifact_schema
        source_producer = source_manifest.producer
        if (
            source_manifest.kind != _WITNESS_SOURCE_KIND
            or source_schema is None
            or source_schema.name != _WITNESS_SOURCE_SCHEMA_NAME
            or source_schema.version != _WITNESS_SOURCE_SCHEMA_VERSION
            or source_producer is None
        ):
            raise ValueError("coverage_witness_source_provenance_invalid")
        source_bytes = store.get_bytes(receipt.source_artifact_ref)
        resolved_source_hash = content_hash(source_bytes, prefix=True)
        if receipt.source_content_hash != resolved_source_hash:
            raise ValueError("coverage_witness_source_content_hash_mismatch")
        source = CoverageWitnessSourceArtifact.model_validate(json.loads(source_bytes))
        source_signature = store.verify_signature(
            receipt.source_artifact_ref,
            verifier,
            strict_identity=True,
        )
        if (
            not source_signature.ok
            or source_signature.expected_identity != source.producer_ref
            or source_signature.signer_identity != source.producer_ref
        ):
            raise ValueError("coverage_witness_source_signature_invalid")
        if (
            source.producer_ref != str(source_producer.component)
            or receipt.producer_ref != source.producer_ref
        ):
            raise ValueError("coverage_witness_source_producer_binding_mismatch")
        if (
            source.assessment_key != assessment_key
            or source.risk_scope.scope_id != scope_id
            or source.risk_scope.owner_scope_key != owner_scope_key
            or source.protected_action_id != protected_action_id
            or source.removed_obligation_instance_id
            != receipt.obligation_instance_id
            or source.authority_issue_codes != (receipt.issue_code,)
        ):
            raise ValueError("coverage_witness_source_scope_or_assessment_mismatch")
        expected_replay_hash = fingerprint(
            {
                "rule_version": WITNESS_REPLAY_RULE_VERSION,
                "source_artifact_ref": receipt.source_artifact_ref,
                "source_content_hash": resolved_source_hash,
                "source": source.model_dump(mode="json"),
            },
            prefix=True,
            canon_spec=_CANON,
        )
        if receipt.replay_hash != expected_replay_hash:
            raise ValueError("coverage_witness_source_replay_hash_mismatch")
        expected_verifier_provenance_hash = fingerprint(
            {
                "verifier_ref": _WITNESS_VERIFIER,
                "rule_version": WITNESS_REPLAY_RULE_VERSION,
                "resolution": "filesystem_cas_verified_source_replay",
                "source_artifact_ref": receipt.source_artifact_ref,
                "source_content_hash": resolved_source_hash,
                "replay_hash": expected_replay_hash,
            },
            prefix=True,
            canon_spec=_CANON,
        )
        if receipt.verifier_provenance_hash != expected_verifier_provenance_hash:
            raise ValueError("coverage_witness_verifier_provenance_hash_mismatch")
        admitted.append(ref)
    return tuple(admitted)
