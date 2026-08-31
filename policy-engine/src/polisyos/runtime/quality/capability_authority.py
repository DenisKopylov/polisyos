"""Capability authority composition and binding-status lattice.

This module implements ADR-0174 C3 for capability bindings: authority is a
minimum across load-bearing factors, with explicit statuses for limitations and
hard authority boundaries. It deliberately consumes the Phase 1
``EvidenceCapability`` contract instead of introducing a parallel capability
shape.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import polisyos.core as core
from polisyos.core.contracts import (
    CapabilityAuthorityPostureResult,
    CapabilityDiscoveryAudience,
    CapabilityTimeSemantics,
)
from polisyos.runtime.quality.capability_index import EvidenceCapability
from polisyos.runtime.quality.evidence_independence import (
    CapabilityIndependenceFactor,
    effective_independence_factor_for_capability,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.approval import ProductionApprovalPacketResolver

CAPABILITY_AUTHORITY_SCHEMA_VERSION = "policyos.capability_binding_result.v1"
CAPABILITY_AUTHORITY_RULE_VERSION = "capability-authority-v1.0"
CAPABILITY_PURPOSE_BINDING_SCHEMA_VERSION = "policyos.capability_purpose_binding.v1"
CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME = (
    "polisyos.runtime.quality.OwnerSignedCapabilityPurposeBinding"
)
CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND = "capability.purpose_binding"
CAPABILITY_PURPOSE_BINDING_PRODUCER_REF = (
    "runtime-quality:capability-purpose-binding-producer"
)
CAPABILITY_PURPOSE_BINDING_VERIFIER_REF = (
    "runtime-quality:capability-purpose-binding-verifier"
)

AuthorityPosture = Literal["research", "governed_pilot", "production"]
AuthorityEnvelopeResult = Literal["admissible", "limited", "contested", "blocked"]
CapabilityBindingStatus = Literal[
    "selected_exact",
    "selected_derived",
    "selected_proxy_with_limitation",
    "selected_with_conflict_marker",
    "selected_context_only",
    "selected_simulation_only",
    "blocked_construct_not_observed",
    "blocked_acquisition_required",
    "blocked_authority_boundary",
    "blocked_rights_boundary",
    "blocked_freshness",
    "blocked_sample_size_below_floor",
    "blocked_schema_regime_mismatch",
    "blocked_construct_validity_below_floor",
    "blocked_resolver_budget_exceeded",
]
CapabilityAuthorityFactorName = Literal[
    "trust_tier",
    "identification_mode",
    "construct_validity",
    "schema_regime",
    "time_scope",
    "legal_authority",
    "rights_access",
    "effective_independence",
    "historical_prior",
]

AUTHORITY_FACTOR_NAMES: tuple[CapabilityAuthorityFactorName, ...] = (
    "trust_tier",
    "identification_mode",
    "construct_validity",
    "schema_regime",
    "time_scope",
    "legal_authority",
    "rights_access",
    "effective_independence",
    "historical_prior",
)

POSTURE_THRESHOLDS: dict[AuthorityPosture, float] = {
    "research": 0.25,
    "governed_pilot": 0.55,
    "production": 0.70,
}

TRUST_TIER_FACTORS = {
    "authoritative_high_coverage": 1.0,
    "authoritative_partial_coverage": 0.85,
    "administrative_noisy": 0.70,
    "derived_proxy": 0.60,
    "weak_anchor": 0.25,
    "context_only": 0.20,
    "simulation_only": 0.10,
    "candidate_unverified": 0.0,
}
IDENTIFICATION_MODE_FACTORS = {
    "point_identified": 1.0,
    "partially_identified": 0.85,
    "partial_identified": 0.85,
    "proxy_identified": 0.60,
    "bounds_only": 0.45,
    "context_only": 0.20,
    "simulation_only": 0.10,
    "candidate_unverified": 0.0,
}
CONSTRUCT_VALIDITY_STATUS_FACTORS = {
    "directly_observed": 1.0,
    "construct_validated": 0.9,
    "proxy_validated": 0.70,
    "face_validated": 0.55,
    "context_only": 0.20,
    "unvalidated": 0.20,
}

_CLAIM_EVIDENCE_USES = frozenset(
    {
        "claim_evidence",
        "claim_evidence_closeout",
        "current_claim_evidence",
        "production_claim_evidence",
    }
)
_DIRECT_OBSERVATION_MODES = frozenset({"observed"})
_DERIVED_MODES = frozenset({"derived", "derived_administrative_with_proxy_validation"})
_PROXY_MODES = frozenset({"proxy_observational", "bounds_only"})
_CONTEXT_ONLY_MODES = frozenset({"context_only"})
_SIMULATION_ONLY_MODES = frozenset({"simulation_only"})
_HISTORICAL_PRIOR_MODES = frozenset({"historical_prior"})
_LLM_CANDIDATE_MODES = frozenset({"candidate_unverified"})
_SCHOLAR_SUPPORT_MODES = frozenset({"scholarly_causal_support"})


class CapabilityAuthorityError(ValueError):
    """Raised when capability authority composition cannot be evaluated."""


class CapabilityPurposeBindingResolutionError(ValueError):
    """Typed refusal from signed capability-purpose production or resolution."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CapabilityPurposeBindingArtifactStore(Protocol):
    """CAS surface required for separately signed capability-purpose bindings."""

    def put_json(
        self,
        obj: object,
        opts: core.artifacts.ArtifactWriteOptions,
    ) -> core.artifacts.ArtifactRef: ...

    def get_bytes(self, artifact_id: core.artifacts.ArtifactID | str) -> bytes: ...

    def get_manifest(
        self,
        artifact_id: core.artifacts.ArtifactID | str,
    ) -> core.artifacts.ArtifactManifest: ...

    def get_signature(
        self,
        artifact_id: core.artifacts.ArtifactID | str,
    ) -> core.artifacts.DetachedSignature | None: ...

    def sign_artifact(
        self,
        artifact_id: core.artifacts.ArtifactID,
        signer: core.artifacts.Ed25519Signer,
        *,
        signer_identity: str | None = None,
    ) -> core.artifacts.DetachedSignature: ...

    def verify_signature(
        self,
        artifact_id: core.artifacts.ArtifactID,
        verifier: core.artifacts.Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> core.artifacts.SignatureVerificationResult: ...


class OwnerSignedCapabilityPurposeBinding(BaseModel):
    """Producer-owned canonical bytes joining one capability to one DS9 purpose."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.capability_purpose_binding.v1"] = (
        CAPABILITY_PURPOSE_BINDING_SCHEMA_VERSION
    )
    producer_ref: Literal["runtime-quality:capability-purpose-binding-producer"] = (
        CAPABILITY_PURPOSE_BINDING_PRODUCER_REF
    )
    capability_ref: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_purpose: str = Field(min_length=1)
    discovery_audience: CapabilityDiscoveryAudience
    approval_packet_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tenant_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    approval_consumer: str = Field(min_length=1)
    approval_audience: str = Field(min_length=1)
    issued_at: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _binding_time_is_scoped_and_aware(self) -> OwnerSignedCapabilityPurposeBinding:
        if self.issued_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("capability-purpose binding times must be timezone-aware")
        if self.valid_until <= self.issued_at:
            raise ValueError("capability-purpose binding validity must follow issuance")
        return self


class CapabilityPurposeBindingProductionReceipt(BaseModel):
    """Receipt proving that the producer persisted and signed exact binding bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding: OwnerSignedCapabilityPurposeBinding
    binding_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signature_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signer_identity: str = Field(min_length=1)
    signing_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CapabilityPurposeBindingVerification(BaseModel):
    """Independent verifier output distinct from the producer's signature act."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding: OwnerSignedCapabilityPurposeBinding
    binding_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signature_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signer_identity: str = Field(min_length=1)
    signing_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    verifier_ref: Literal["runtime-quality:capability-purpose-binding-verifier"] = (
        CAPABILITY_PURPOSE_BINDING_VERIFIER_REF
    )
    verified_at: datetime


class CapabilityPurposeBindingProducer:
    """Persist and sign producer-owned capability-purpose binding bytes."""

    def __init__(
        self,
        *,
        artifact_store: CapabilityPurposeBindingArtifactStore,
        signer: core.artifacts.Ed25519Signer,
        signer_identity: str,
    ) -> None:
        required = ("put_json", "sign_artifact", "get_signature")
        if any(not callable(getattr(artifact_store, method, None)) for method in required):
            raise TypeError("capability-purpose producer requires a signing artifact store")
        if type(signer) is not core.artifacts.Ed25519Signer:
            raise TypeError("capability-purpose producer requires Ed25519Signer")
        if not signer_identity.strip():
            raise ValueError("capability-purpose producer identity is required")
        self._artifact_store = artifact_store
        self._signer = signer
        self._signer_identity = signer_identity

    def issue(
        self,
        *,
        capability_ref: str,
        content_digest: str,
        authority_purpose: str,
        discovery_audience: CapabilityDiscoveryAudience,
        approval_packet_ref: str,
        tenant_id: str,
        run_id: str,
        approval_consumer: str,
        approval_audience: str,
        issued_at: datetime,
        valid_until: datetime,
    ) -> CapabilityPurposeBindingProductionReceipt:
        """Persist exact bytes, perform the signing act, and read back its sidecar."""
        binding = OwnerSignedCapabilityPurposeBinding(
            capability_ref=capability_ref,
            content_digest=content_digest,
            authority_purpose=authority_purpose,
            discovery_audience=discovery_audience,
            approval_packet_ref=approval_packet_ref,
            tenant_id=tenant_id,
            run_id=run_id,
            approval_consumer=approval_consumer,
            approval_audience=approval_audience,
            issued_at=issued_at,
            valid_until=valid_until,
        )
        try:
            artifact_ref = self._artifact_store.put_json(
                binding.model_dump(mode="json"),
                core.artifacts.PutOptions(
                    kind=CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND,
                    media_type="application/json",
                    schema=core.artifacts.SchemaInfo(
                        name=CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME,
                        version=binding.schema_version,
                    ),
                    producer=core.artifacts.ProducerInfo(
                        component=CAPABILITY_PURPOSE_BINDING_PRODUCER_REF,
                        version=binding.schema_version,
                    ),
                ),
            )
            signature = self._artifact_store.sign_artifact(
                artifact_ref.artifact_id,
                self._signer,
                signer_identity=self._signer_identity,
            )
            persisted_signature = self._artifact_store.get_signature(artifact_ref.artifact_id)
        except (OSError, TypeError, ValueError) as exc:
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_signature_production_failed"
            ) from exc
        if (
            type(signature) is not core.artifacts.DetachedSignature
            or persisted_signature != signature
            or signature.artifact_id != str(artifact_ref.artifact_id)
            or signature.key_id != self._signer.key_id
            or signature.signer_identity != self._signer_identity
        ):
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_signature_production_failed"
            )
        return CapabilityPurposeBindingProductionReceipt(
            binding=binding,
            binding_ref=str(artifact_ref.artifact_id),
            signature_ref=_detached_signature_ref(signature),
            signer_identity=self._signer_identity,
            signing_key_id=self._signer.key_id,
        )


class CapabilityPurposeBindingVerifier:
    """Independently verify signed binding bytes and all purpose coordinates."""

    def __init__(
        self,
        *,
        artifact_store: CapabilityPurposeBindingArtifactStore,
        verifier: core.artifacts.Ed25519Verifier,
        expected_signer_identity: str,
    ) -> None:
        required = ("get_bytes", "get_manifest", "get_signature", "verify_signature")
        if any(not callable(getattr(artifact_store, method, None)) for method in required):
            raise TypeError("capability-purpose verifier requires a signed artifact store")
        if type(verifier) is not core.artifacts.Ed25519Verifier:
            raise TypeError("capability-purpose verifier requires Ed25519Verifier")
        if not expected_signer_identity.strip():
            raise ValueError("capability-purpose signer identity is required")
        self._artifact_store = artifact_store
        self._verifier = verifier
        self._expected_signer_identity = expected_signer_identity

    def verify(
        self,
        binding_ref: str,
        *,
        capability_ref: str,
        content_digest: str,
        authority_purpose: str,
        discovery_audience: CapabilityDiscoveryAudience,
        approval_packet_ref: str,
        tenant_id: str,
        run_id: str,
        approval_consumer: str,
        approval_audience: str,
        evaluated_at: datetime,
    ) -> CapabilityPurposeBindingVerification:
        """Verify detached signature, producer manifest, bytes, scope, and expiry."""
        try:
            artifact_id = core.artifacts.ArtifactID.model_validate(binding_ref)
            signature = self._artifact_store.get_signature(artifact_id)
        except (OSError, TypeError, ValueError) as exc:
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_artifact_invalid"
            ) from exc
        if signature is None:
            raise CapabilityPurposeBindingResolutionError("owner_binding_unsigned")
        if type(signature) is not core.artifacts.DetachedSignature:
            raise CapabilityPurposeBindingResolutionError("owner_binding_signature_invalid")
        if signature.signer_identity != self._expected_signer_identity:
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_signer_identity_mismatch"
            )
        try:
            verification = self._artifact_store.verify_signature(
                artifact_id,
                self._verifier,
                strict_identity=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_signature_invalid"
            ) from exc
        if (
            not verification.ok
            or verification.signer_identity != self._expected_signer_identity
            or verification.key_id != signature.key_id
        ):
            raise CapabilityPurposeBindingResolutionError("owner_binding_signature_invalid")
        try:
            manifest = self._artifact_store.get_manifest(artifact_id)
            if (
                manifest.kind != CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND
                or manifest.artifact_schema is None
                or manifest.artifact_schema.name != CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME
                or manifest.artifact_schema.version != CAPABILITY_PURPOSE_BINDING_SCHEMA_VERSION
                or manifest.producer is None
                or str(manifest.producer.component) != CAPABILITY_PURPOSE_BINDING_PRODUCER_REF
            ):
                raise CapabilityPurposeBindingResolutionError(
                    "owner_binding_manifest_invalid"
                )
            binding = OwnerSignedCapabilityPurposeBinding.model_validate_json(
                self._artifact_store.get_bytes(artifact_id)
            )
        except CapabilityPurposeBindingResolutionError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise CapabilityPurposeBindingResolutionError(
                "owner_binding_artifact_invalid"
            ) from exc
        comparisons = (
            (binding.capability_ref, capability_ref, "owner_binding_resource_mismatch"),
            (binding.content_digest, content_digest, "owner_binding_digest_mismatch"),
            (binding.authority_purpose, authority_purpose, "owner_binding_purpose_mismatch"),
            (
                binding.discovery_audience,
                discovery_audience,
                "owner_binding_audience_mismatch",
            ),
            (
                binding.approval_packet_ref,
                approval_packet_ref,
                "owner_binding_currentness_ref_mismatch",
            ),
            (binding.tenant_id, tenant_id, "owner_binding_tenant_mismatch"),
            (binding.run_id, run_id, "owner_binding_run_mismatch"),
            (
                binding.approval_consumer,
                approval_consumer,
                "owner_binding_consumer_mismatch",
            ),
            (
                binding.approval_audience,
                approval_audience,
                "owner_binding_approval_audience_mismatch",
            ),
        )
        for actual, expected, code in comparisons:
            if actual != expected:
                raise CapabilityPurposeBindingResolutionError(code)
        if evaluated_at.tzinfo is None:
            raise CapabilityPurposeBindingResolutionError("owner_binding_evaluation_time_invalid")
        if evaluated_at < binding.issued_at or evaluated_at >= binding.valid_until:
            raise CapabilityPurposeBindingResolutionError("owner_binding_expired")
        return CapabilityPurposeBindingVerification(
            binding=binding,
            binding_ref=binding_ref,
            signature_ref=_detached_signature_ref(signature),
            signer_identity=self._expected_signer_identity,
            signing_key_id=signature.key_id,
            verified_at=evaluated_at,
        )


def _detached_signature_ref(signature: core.artifacts.DetachedSignature) -> str:
    payload = core.canon.to_canonical_bytes(signature.model_dump(mode="json"))
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class CapabilityAuthorityFactor(BaseModel):
    """One load-bearing factor in the authority minimum."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: CapabilityAuthorityFactorName
    value: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    status: Literal["pass", "below_floor"]
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class CapabilityBindingResult(BaseModel):
    """Typed capability binding result consumed by resolvers and projections."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.capability_binding_result.v1"] = (
        CAPABILITY_AUTHORITY_SCHEMA_VERSION
    )
    rule_version_ref: str = CAPABILITY_AUTHORITY_RULE_VERSION
    binding_id: str = Field(min_length=1)
    requirement_id: str | None = None
    status: CapabilityBindingStatus
    selected_capability_ref: str | None = None
    authority_level: AuthorityPosture
    authority_envelope_result: AuthorityEnvelopeResult
    satisfies_claim_evidence: bool
    minimum_factor: CapabilityAuthorityFactor
    factors: tuple[CapabilityAuthorityFactor, ...] = Field(min_length=9)
    binding_reasons: tuple[str, ...] = Field(default=())
    limitations: tuple[str, ...] = Field(default=())
    blocked_reasons: tuple[str, ...] = Field(default=())
    construct_ref: str | None = None
    capability_index_ref: str | None = None
    acquisition_strategies: tuple[dict[str, Any], ...] = Field(default=())
    reviewer_queue: tuple[dict[str, Any], ...] = Field(default=())
    conflict_markers: tuple[dict[str, Any], ...] = Field(default=())
    rejected_alternatives: tuple[dict[str, Any], ...] = Field(default=())
    lineage_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(
        default=(
            "projection_authority",
            "scorecard_authority_without_binding_status",
        )
    )

    @field_validator(
        "binding_reasons",
        "limitations",
        "blocked_reasons",
        "lineage_refs",
        "authoritative_for",
        "may_not_use_for",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    def factor_by_name(
        self,
        name: CapabilityAuthorityFactorName | str,
    ) -> CapabilityAuthorityFactor:
        """Return one composed factor by governed factor name."""

        for factor in self.factors:
            if factor.name == name:
                return factor
        raise KeyError(str(name))


class CapabilityAuthorityContext(BaseModel):
    """DS9 coordinates plus a signed binding ref or an untrusted caller claim.

    ``binding_claim`` remains a negative-only compatibility input. Only
    ``binding_ref`` can enter the independent signature verifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    packet_ref: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    expected_consumer: str = Field(min_length=1)
    expected_audience: CapabilityDiscoveryAudience
    approval_audience: str = Field(default="polisyos-runtime", min_length=1)
    binding_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    binding_claim: dict[str, str] | None = None

    @model_validator(mode="after")
    def _one_binding_input_only(self) -> CapabilityAuthorityContext:
        if self.binding_ref is not None and self.binding_claim is not None:
            raise ValueError(
                "signed binding_ref and untrusted binding_claim are mutually exclusive"
            )
        return self


class CapabilityDiscoveryAuthorityResolver:
    """Join independently verified producer signing with sealed DS9 currentness."""

    def __init__(
        self,
        *,
        production_approval_resolver: ProductionApprovalPacketResolver | None,
        binding_verifier: CapabilityPurposeBindingVerifier | None = None,
    ) -> None:
        self._production_approval_resolver = production_approval_resolver
        self._binding_verifier = binding_verifier

    def resolve(
        self,
        *,
        capability_ref: str,
        content_digest: str,
        authority_purpose: str,
        audience: CapabilityDiscoveryAudience,
        context: CapabilityAuthorityContext | None = None,
        observed_at: datetime | None = None,
    ) -> CapabilityAuthorityPostureResult:
        """Admit only when both independent producer evidence streams resolve."""
        checked_at = observed_at or datetime.now(UTC)
        reasons: list[str] = []
        provenance_refs = [CAPABILITY_AUTHORITY_RULE_VERSION]
        currentness_ref: str | None = None
        binding: CapabilityPurposeBindingVerification | None = None
        if context is None:
            reasons.append("production_approval_context_missing")
            reasons.append("owner_binding_artifact_missing")
        else:
            if context.expected_audience != audience:
                reasons.append("approval_audience_mismatch")
            if context.binding_claim is not None:
                reasons.append("owner_binding_not_independently_verified")
                reasons.extend(
                    _binding_claim_negative_reasons(
                        context.binding_claim,
                        capability_ref=capability_ref,
                        content_digest=content_digest,
                        authority_purpose=authority_purpose,
                        expected_consumer=context.expected_consumer,
                        expected_audience=audience,
                        evaluated_at=checked_at,
                    )
                )
            elif context.binding_ref is None:
                reasons.append("owner_binding_artifact_missing")
            elif self._binding_verifier is None:
                reasons.append("owner_binding_verifier_missing")
            else:
                try:
                    binding = self._binding_verifier.verify(
                        context.binding_ref,
                        capability_ref=capability_ref,
                        content_digest=content_digest,
                        authority_purpose=authority_purpose,
                        discovery_audience=audience,
                        approval_packet_ref=context.packet_ref,
                        tenant_id=context.tenant_id,
                        run_id=context.run_id,
                        approval_consumer=context.expected_consumer,
                        approval_audience=context.approval_audience,
                        evaluated_at=checked_at,
                    )
                except CapabilityPurposeBindingResolutionError as exc:
                    reasons.append(exc.code)
                else:
                    provenance_refs.extend(
                        (
                            binding.binding_ref,
                            binding.signature_ref,
                            binding.verifier_ref,
                        )
                    )
            resolver = self._production_approval_resolver
            if resolver is None:
                reasons.append("production_approval_resolver_missing")
            else:
                from polisyos.runtime.quality.approval import (
                    ProductionApprovalPacketResolver,
                    ProductionApprovalResolutionError,
                )

                if type(resolver) is not ProductionApprovalPacketResolver:
                    reasons.append("production_approval_resolver_invalid_source")
                else:
                    try:
                        resolver.require_currentness(
                            packet_ref=context.packet_ref,
                            tenant_id=context.tenant_id,
                            run_id=context.run_id,
                            expected_consumer=context.expected_consumer,
                            expected_audience=context.approval_audience,
                            evaluated_at=checked_at,
                        )
                    except ProductionApprovalResolutionError as exc:
                        reasons.append(exc.code)
                    else:
                        currentness_ref = context.packet_ref
                        provenance_refs.append(context.packet_ref)
        if binding is not None and currentness_ref is not None and not reasons:
            return CapabilityAuthorityPostureResult(
                state="admitted_authority",
                producer_ref=CAPABILITY_PURPOSE_BINDING_PRODUCER_REF,
                authority_purpose=authority_purpose,
                binding_ref=binding.binding_ref,
                currentness_ref=currentness_ref,
                reason_codes=(),
                provenance_refs=tuple(dict.fromkeys(provenance_refs)),
                time=CapabilityTimeSemantics(
                    observed_at=checked_at,
                    valid_from=binding.binding.issued_at,
                    valid_until=binding.binding.valid_until,
                    freshness="current",
                ),
            )
        if not reasons:
            reasons.append("not_established")
        elif binding is None and "not_established" not in reasons:
            reasons.insert(0, "not_established")
        state: Literal["bridge_missing", "revalidation_required"] = (
            "revalidation_required" if binding is not None else "bridge_missing"
        )
        time = CapabilityTimeSemantics(
            observed_at=checked_at,
            valid_from=binding.binding.issued_at if binding is not None else checked_at,
            valid_until=binding.binding.valid_until if binding is not None else None,
            freshness="stale" if binding is not None else "unknown",
        )
        return CapabilityAuthorityPostureResult(
            state=state,
            producer_ref="runtime-quality:capability-authority-composer",
            authority_purpose=authority_purpose,
            binding_ref=binding.binding_ref if binding is not None else None,
            currentness_ref=currentness_ref,
            reason_codes=tuple(dict.fromkeys(reasons)),
            provenance_refs=tuple(provenance_refs),
            time=time,
        )


def _binding_claim_negative_reasons(
    claim: Mapping[str, str],
    *,
    capability_ref: str,
    content_digest: str,
    authority_purpose: str,
    expected_consumer: str,
    expected_audience: CapabilityDiscoveryAudience,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    """Diagnose caller claims for negatives without granting them authority."""

    reasons: list[str] = []
    comparisons = (
        ("capability_ref", capability_ref, "owner_binding_resource_mismatch"),
        ("content_digest", content_digest, "owner_binding_digest_mismatch"),
        ("authority_purpose", authority_purpose, "owner_binding_purpose_mismatch"),
        ("expected_consumer", expected_consumer, "owner_binding_consumer_mismatch"),
        ("expected_audience", expected_audience, "owner_binding_audience_mismatch"),
    )
    for field, expected, reason in comparisons:
        if claim.get(field) != expected:
            reasons.append(reason)
    if not claim.get("owner_signature_ref", "").strip():
        reasons.append("owner_binding_unsigned")
    expiry = claim.get("expires_at")
    if not expiry:
        reasons.append("owner_binding_expiry_missing")
    else:
        try:
            expires_at = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            reasons.append("owner_binding_expiry_invalid")
        else:
            if expires_at.tzinfo is None or expires_at <= evaluated_at:
                reasons.append("owner_binding_expired")
    return tuple(reasons)


def compose_capability_authority(
    capability: EvidenceCapability | Mapping[str, Any],
    *,
    posture: AuthorityPosture = "production",
    claim_use: str = "claim_evidence_closeout",
    requirement_id: str | None = None,
    selected_capabilities: Sequence[EvidenceCapability | Mapping[str, Any]] = (),
    independence_map: Mapping[str, Any] | None = None,
    conflict_markers: Sequence[Mapping[str, Any]] = (),
    human_reviewer_admitted_conflicts: bool = False,
    required_schema_regime: str | None = None,
    min_sample_size: int | None = None,
    construct_observed: bool = True,
    acquisition_required: bool = False,
    resolver_budget_exceeded: bool = False,
) -> CapabilityBindingResult:
    """Compose a capability's binding status for a claim use and posture.

    Args:
        capability: Phase 1 capability DTO or equivalent mapping.
        posture: Authority posture whose factor threshold is applied.
        claim_use: Purpose for which the capability is being considered.
        requirement_id: Optional requirement/result bridge identifier.
        selected_capabilities: Already selected evidence in the claim portfolio.
        independence_map: Optional W8.F map with precomputed capability factors.
        conflict_markers: W8.E same-construct conflict markers.
        human_reviewer_admitted_conflicts: Whether a reviewer explicitly admitted
            the conflict marker for this claim/posture.
        required_schema_regime: Required schema regime for the claim scope.
        min_sample_size: Optional sample-size floor from the construct/posture.
        construct_observed: Whether the resolver found this construct observed.
        acquisition_required: Whether the resolver found no adequate current
            capability and routed the requirement to acquisition.
        resolver_budget_exceeded: Whether the resolver exceeded its runtime budget.

    Returns:
        A typed binding result preserving authority factors and limitations.
    """

    model = _capability_model(capability)
    threshold = POSTURE_THRESHOLDS[posture]
    independence = effective_independence_factor_for_capability(
        model,
        selected_capabilities=selected_capabilities,
        independence_map=independence_map,
    )
    factors = _compose_factors(
        model,
        posture=posture,
        threshold=threshold,
        independence=independence,
        claim_use=claim_use,
        required_schema_regime=required_schema_regime,
    )
    minimum_factor = min(factors, key=lambda factor: (factor.value, factor.name))
    below_floor = tuple(factor for factor in factors if factor.value < factor.threshold)
    reasons = _binding_reasons(model, factors)
    limitations = _limitations(
        model,
        factors,
        independence=independence,
        claim_use=claim_use,
    )
    blocked_reasons = _blocked_reasons(
        model,
        factors,
        posture=posture,
        claim_use=claim_use,
    )
    status = _binding_status(
        model,
        posture=posture,
        claim_use=claim_use,
        below_floor=below_floor,
        conflict_markers=conflict_markers,
        human_reviewer_admitted_conflicts=human_reviewer_admitted_conflicts,
        min_sample_size=min_sample_size,
        independence=independence,
        construct_observed=construct_observed,
        acquisition_required=acquisition_required,
        resolver_budget_exceeded=resolver_budget_exceeded,
    )
    normalized_conflicts = _normalize_conflict_markers(conflict_markers)
    if normalized_conflicts:
        reasons = _dedupe(
            [
                *reasons,
                (
                    "conflict_marker_human_reviewer_admitted"
                    if human_reviewer_admitted_conflicts
                    else "construct_conflict_marker_present"
                ),
            ]
        )

    if _sample_size_below_floor(model, min_sample_size):
        blocked_reasons = _dedupe([*blocked_reasons, "sample_size_below_floor"])
    if not construct_observed:
        blocked_reasons = _dedupe([*blocked_reasons, "construct_not_observed"])
    if acquisition_required:
        blocked_reasons = _dedupe([*blocked_reasons, "acquisition_required"])
    if resolver_budget_exceeded:
        blocked_reasons = _dedupe([*blocked_reasons, "resolver_budget_exceeded"])
    if status.startswith("blocked_"):
        authority_result: AuthorityEnvelopeResult = "blocked"
    elif status == "selected_with_conflict_marker" and not human_reviewer_admitted_conflicts:
        authority_result = "contested"
    elif status in {
        "selected_proxy_with_limitation",
        "selected_context_only",
        "selected_simulation_only",
    }:
        authority_result = "limited"
    else:
        authority_result = "admissible"

    satisfies = (
        authority_result == "admissible"
        and status in {"selected_exact", "selected_derived"}
        and not _is_advisory_only_mode(model)
    )
    if _is_claim_evidence_use(claim_use) and status in {
        "selected_context_only",
        "selected_simulation_only",
        "selected_proxy_with_limitation",
        "selected_with_conflict_marker",
    }:
        satisfies = False

    authoritative_for = ("claim_evidence",) if satisfies else ()
    may_not_use_for = _may_not_use_for(
        status=status,
        satisfies_claim_evidence=satisfies,
        claim_use=claim_use,
    )
    return CapabilityBindingResult(
        binding_id=f"binding:{model.capability_id}",
        requirement_id=requirement_id,
        status=status,
        selected_capability_ref=(model.capability_id if status.startswith("selected_") else None),
        authority_level=posture,
        authority_envelope_result=authority_result,
        satisfies_claim_evidence=satisfies,
        minimum_factor=minimum_factor,
        factors=factors,
        binding_reasons=tuple(reasons),
        limitations=tuple(limitations),
        blocked_reasons=tuple(blocked_reasons),
        construct_ref=f"construct:{model.construct_id.removeprefix('construct:')}",
        conflict_markers=tuple(normalized_conflicts),
        lineage_refs=model.lineage_refs,
        authoritative_for=authoritative_for,
        may_not_use_for=may_not_use_for,
    )


def _compose_factors(
    capability: EvidenceCapability,
    *,
    posture: AuthorityPosture,
    threshold: float,
    independence: CapabilityIndependenceFactor,
    claim_use: str,
    required_schema_regime: str | None,
) -> tuple[CapabilityAuthorityFactor, ...]:
    return tuple(
        _factor(
            name=name,
            value=_factor_value(
                capability,
                name,
                posture=posture,
                independence=independence,
                claim_use=claim_use,
                required_schema_regime=required_schema_regime,
            ),
            threshold=threshold,
            source=_factor_source(name),
        )
        for name in AUTHORITY_FACTOR_NAMES
    )


def _factor(
    *,
    name: CapabilityAuthorityFactorName,
    value: float,
    threshold: float,
    source: str,
) -> CapabilityAuthorityFactor:
    clean = _clamp(value)
    return CapabilityAuthorityFactor(
        name=name,
        value=clean,
        threshold=threshold,
        status="pass" if clean >= threshold else "below_floor",
        source=source,
        reason=f"{name}_{'passed' if clean >= threshold else 'below_floor'}",
    )


def _factor_value(
    capability: EvidenceCapability,
    name: CapabilityAuthorityFactorName,
    *,
    posture: AuthorityPosture,
    independence: CapabilityIndependenceFactor,
    claim_use: str,
    required_schema_regime: str | None,
) -> float:
    canonical = _canonical_factor_value(
        capability,
        name,
        posture=posture,
        independence=independence,
        claim_use=claim_use,
        required_schema_regime=required_schema_regime,
    )
    override = _factor_override(capability, name)
    if override is not None:
        return min(canonical, override)
    return canonical


def _canonical_factor_value(
    capability: EvidenceCapability,
    name: CapabilityAuthorityFactorName,
    *,
    posture: AuthorityPosture,
    independence: CapabilityIndependenceFactor,
    claim_use: str,
    required_schema_regime: str | None,
) -> float:
    if name == "trust_tier":
        return TRUST_TIER_FACTORS.get(capability.trust_tier, 0.0)
    if name == "identification_mode":
        return IDENTIFICATION_MODE_FACTORS.get(capability.identification_mode, 0.0)
    if name == "construct_validity":
        return _construct_validity_factor(capability)
    if name == "schema_regime":
        return _schema_regime_factor(capability, required_schema_regime)
    if name == "time_scope":
        return _time_scope_factor(capability, posture=posture)
    if name == "legal_authority":
        return _legal_authority_factor(capability, posture=posture, claim_use=claim_use)
    if name == "rights_access":
        return _rights_access_factor(capability)
    if name == "effective_independence":
        return independence.value
    if name == "historical_prior":
        return _historical_prior_factor(capability, claim_use=claim_use)
    raise AssertionError(f"unhandled authority factor: {name}")


def _factor_override(
    capability: EvidenceCapability,
    name: CapabilityAuthorityFactorName,
) -> float | None:
    metadata = capability.metadata
    factors = metadata.get("authority_factors")
    if isinstance(factors, Mapping) and name in factors:
        return _optional_float(factors.get(name))
    for key in (name, f"{name}_factor"):
        if key in metadata:
            return _optional_float(metadata.get(key))
    return None


def _construct_validity_factor(capability: EvidenceCapability) -> float:
    if "construct_validity" in capability.quality_score.breakdown:
        return float(capability.quality_score.breakdown["construct_validity"])
    status = _text(capability.proxy_validation.get("construct_validity_status"))
    if status:
        return CONSTRUCT_VALIDITY_STATUS_FACTORS.get(status, 0.0)
    return float(capability.quality_score.composite)


def _schema_regime_factor(
    capability: EvidenceCapability,
    required_schema_regime: str | None,
) -> float:
    if required_schema_regime and capability.scope.schema_regime != required_schema_regime:
        return 0.0
    metadata_value = capability.metadata.get("schema_regime_alignment")
    if isinstance(metadata_value, bool):
        return 1.0 if metadata_value else 0.0
    return 1.0


def _time_scope_factor(
    capability: EvidenceCapability,
    *,
    posture: AuthorityPosture,
) -> float:
    freshness = capability.freshness_envelope.freshness_class.casefold()
    if "expired" in freshness or "stale" in freshness:
        return 0.20 if posture == "production" else 0.45
    if "fresh" in freshness or "current" in freshness:
        return 1.0
    if "pilot" in freshness and posture == "production":
        return 0.65
    return 0.85


def _legal_authority_factor(
    capability: EvidenceCapability,
    *,
    posture: AuthorityPosture,
    claim_use: str,
) -> float:
    modes = set(capability.modality)
    if _is_unbacked_llm_candidate(capability):
        return 0.0
    if (
        "historical_pdc_artifact" in modes or capability.evidence_mode in _HISTORICAL_PRIOR_MODES
    ) and _is_claim_evidence_use(claim_use):
        return 0.0
    if _capability_authority_boundary_blocks(
        capability,
        posture=posture,
        claim_use=claim_use,
    ):
        return 0.0
    posture_state = _text(getattr(capability.authority_envelope, posture))
    if posture_state and _authority_state_is_limited(posture_state):
        return 0.65
    return 1.0


def _rights_access_factor(capability: EvidenceCapability) -> float:
    rights = capability.rights_envelope
    restrictions = {item.casefold() for item in rights.restrictions}
    if not rights.claim_evidence_use_allowed:
        return 0.0
    if restrictions & {"claim_evidence_forbidden", "no_claim_evidence_use"}:
        return 0.0
    return 1.0


def _historical_prior_factor(capability: EvidenceCapability, *, claim_use: str) -> float:
    if capability.evidence_mode in _HISTORICAL_PRIOR_MODES or "historical_pdc_artifact" in set(
        capability.modality
    ):
        return 0.0 if _is_claim_evidence_use(claim_use) else 0.25
    return 1.0


def _factor_source(name: CapabilityAuthorityFactorName) -> str:
    return {
        "trust_tier": "capability.trust_tier",
        "identification_mode": "capability.identification_mode",
        "construct_validity": "capability.quality_score.construct_validity",
        "schema_regime": "capability.scope.schema_regime",
        "time_scope": "capability.freshness_envelope",
        "legal_authority": "capability.authority_boundary",
        "rights_access": "capability.rights_envelope",
        "effective_independence": "w8f.effective_independence",
        "historical_prior": "c41.historical_prior_firewall",
    }[name]


def _binding_status(
    capability: EvidenceCapability,
    *,
    posture: AuthorityPosture,
    claim_use: str,
    below_floor: Sequence[CapabilityAuthorityFactor],
    conflict_markers: Sequence[Mapping[str, Any]],
    human_reviewer_admitted_conflicts: bool,
    min_sample_size: int | None,
    independence: CapabilityIndependenceFactor,
    construct_observed: bool,
    acquisition_required: bool,
    resolver_budget_exceeded: bool,
) -> CapabilityBindingStatus:
    if resolver_budget_exceeded:
        return "blocked_resolver_budget_exceeded"
    if not construct_observed:
        return "blocked_construct_not_observed"
    if acquisition_required:
        return "blocked_acquisition_required"
    if _sample_size_below_floor(capability, min_sample_size):
        return "blocked_sample_size_below_floor"
    if _is_simulation_only(capability) and posture == "production":
        return "blocked_authority_boundary"
    if _is_historical_prior(capability) and _is_claim_evidence_use(claim_use):
        return "blocked_authority_boundary"
    if _is_unbacked_llm_candidate(capability):
        return "blocked_authority_boundary"
    if _is_scholar_only_support(capability) and _is_claim_evidence_use(claim_use):
        return "blocked_authority_boundary"
    if _is_historical_prior(capability):
        return "selected_context_only"
    if _is_context_only(capability):
        return "selected_context_only"

    hard_block = _hard_block_status(below_floor)
    if hard_block is not None:
        return hard_block

    if conflict_markers and not human_reviewer_admitted_conflicts:
        return "selected_with_conflict_marker"
    if _independence_collapsed_above_limit(independence):
        return "selected_proxy_with_limitation"
    if _factor_named(below_floor, "effective_independence") is not None:
        return "selected_proxy_with_limitation"
    if _is_proxy_limited(capability):
        return "selected_proxy_with_limitation"
    if _is_simulation_only(capability):
        return "selected_simulation_only"
    if _is_derived(capability):
        return "selected_derived"
    return "selected_exact"


def _hard_block_status(
    below_floor: Sequence[CapabilityAuthorityFactor],
) -> CapabilityBindingStatus | None:
    priority: tuple[tuple[CapabilityAuthorityFactorName, CapabilityBindingStatus], ...] = (
        ("rights_access", "blocked_rights_boundary"),
        ("schema_regime", "blocked_schema_regime_mismatch"),
        ("time_scope", "blocked_freshness"),
        ("construct_validity", "blocked_construct_validity_below_floor"),
        ("legal_authority", "blocked_authority_boundary"),
        ("trust_tier", "blocked_authority_boundary"),
        ("identification_mode", "blocked_authority_boundary"),
        ("historical_prior", "blocked_authority_boundary"),
    )
    for name, status in priority:
        if _factor_named(below_floor, name) is not None:
            return status
    return None


def _binding_reasons(
    capability: EvidenceCapability,
    factors: Sequence[CapabilityAuthorityFactor],
) -> tuple[str, ...]:
    reasons = [
        "construct_match",
        "capability_ref_selected",
        "authority_minimum_passed"
        if all(factor.status == "pass" for factor in factors)
        else "authority_minimum_limited_or_blocked",
    ]
    if _is_derived(capability):
        reasons.append("derived_capability_selected")
    return tuple(reasons)


def _limitations(
    capability: EvidenceCapability,
    factors: Sequence[CapabilityAuthorityFactor],
    *,
    independence: CapabilityIndependenceFactor,
    claim_use: str,
) -> tuple[str, ...]:
    limitations: list[str] = list(capability.limitations)
    if _is_proxy_limited(capability):
        limitations.append(f"{capability.evidence_mode}_selected_with_limitation")
    if _is_context_only(capability) and _is_claim_evidence_use(claim_use):
        limitations.append("context_only_cannot_satisfy_claim_evidence_closeout")
    if _is_simulation_only(capability):
        limitations.append("simulation_only_modeling_support_not_claim_evidence")
    if _is_historical_prior(capability):
        limitations.append("historical_prior_advisory_only")
    if _independence_collapsed_above_limit(independence):
        limitations.append("effective_independence_collapse_above_0_7")
    if _factor_named(factors, "effective_independence") is not None:
        factor = _factor_named(factors, "effective_independence")
        if factor and factor.status == "below_floor":
            limitations.append("effective_independence_below_floor")
            if independence.shared_lineage_refs:
                limitations.append("effective_independence_lineage_collapsed")
    return tuple(_dedupe(limitations))


def _blocked_reasons(
    capability: EvidenceCapability,
    factors: Sequence[CapabilityAuthorityFactor],
    *,
    posture: AuthorityPosture,
    claim_use: str,
) -> tuple[str, ...]:
    reasons = [factor.reason for factor in factors if factor.status == "below_floor"]
    if _is_simulation_only(capability) and posture == "production":
        reasons.append("simulation_only_cannot_satisfy_production_claim_evidence")
    if _is_historical_prior(capability) and _is_claim_evidence_use(claim_use):
        reasons.append("historical_prior_firewall_current_claim_evidence")
    if _is_unbacked_llm_candidate(capability):
        reasons.append("llm_candidate_without_producer_backing")
    if _capability_authority_boundary_blocks(
        capability,
        posture=posture,
        claim_use=claim_use,
    ):
        reasons.append("capability_authority_envelope_blocked")
    if _is_scholar_only_support(capability) and _is_claim_evidence_use(claim_use):
        reasons.append("scholar_only_cannot_satisfy_current_claim_evidence")
    return tuple(_dedupe(reasons))


def _may_not_use_for(
    *,
    status: CapabilityBindingStatus,
    satisfies_claim_evidence: bool,
    claim_use: str,
) -> tuple[str, ...]:
    limits = {
        "projection_authority",
        "scorecard_authority_without_binding_status",
    }
    if not satisfies_claim_evidence:
        limits.update(
            {
                "claim_evidence_closeout",
                "production_claim_evidence",
                "runtime_closeout_authority",
            }
        )
    if status == "selected_with_conflict_marker":
        limits.add("production_escalation_without_human_review")
    return tuple(sorted(limits))


def _capability_authority_boundary_blocks(
    capability: EvidenceCapability,
    *,
    posture: AuthorityPosture,
    claim_use: str,
) -> bool:
    posture_state = _text(getattr(capability.authority_envelope, posture))
    if posture_state and _authority_state_is_blocking(posture_state):
        return True
    may_not = {
        *capability.may_not_use_for,
        *capability.authority_envelope.may_not_use_for,
    }
    requested = _purpose_aliases(claim_use)
    return bool(requested & set(may_not))


def _authority_state_is_blocking(value: str) -> bool:
    normalized = value.casefold()
    return (
        normalized.startswith("blocked")
        or normalized in {"forbidden", "prohibited", "not_admissible"}
        or "forbidden" in normalized
        or "prohibited" in normalized
    )


def _authority_state_is_limited(value: str) -> bool:
    normalized = value.casefold()
    return any(
        marker in normalized
        for marker in ("limitation", "limited", "proxy", "context_only", "simulation_only")
    )


def _purpose_aliases(claim_use: str) -> set[str]:
    normalized = claim_use.strip().casefold()
    aliases = {normalized}
    if normalized in _CLAIM_EVIDENCE_USES:
        aliases.update(
            {
                "claim_evidence",
                "claim_evidence_closeout",
                "current_claim_evidence",
                "production_claim_evidence",
            }
        )
    return aliases


def _normalize_conflict_markers(
    markers: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for marker in markers:
        if not isinstance(marker, Mapping):
            continue
        conflict_id = _text(marker.get("conflict_id")) or _text(marker.get("id"))
        conflict_class = (
            _text(marker.get("conflict_class")) or _text(marker.get("conflict_type")) or "empirical"
        )
        rows.append(
            {
                "conflict_id": conflict_id or f"conflict:{len(rows) + 1}",
                "construct": _text(marker.get("construct")),
                "conflict_class": conflict_class,
                "conflict_resolution_route": (
                    _text(marker.get("conflict_resolution_route"))
                    or _text(marker.get("resolution_route"))
                    or "persistent_contested_state"
                ),
                "capability_refs": _text_values(marker.get("capability_refs")),
                "status": _text(marker.get("status")) or "contested",
            }
        )
    return tuple(rows)


def _sample_size_below_floor(
    capability: EvidenceCapability,
    min_sample_size: int | None,
) -> bool:
    if min_sample_size is None:
        return False
    sample_size = _optional_int(capability.metadata.get("sample_size"))
    return sample_size is not None and sample_size < min_sample_size


def _is_proxy_limited(capability: EvidenceCapability) -> bool:
    return (
        capability.evidence_mode in _PROXY_MODES
        or capability.identification_mode == "proxy_identified"
        or capability.trust_tier == "derived_proxy"
    )


def _is_derived(capability: EvidenceCapability) -> bool:
    return capability.evidence_mode in _DERIVED_MODES or capability.evidence_mode.startswith(
        "derived_"
    )


def _is_context_only(capability: EvidenceCapability) -> bool:
    return capability.evidence_mode in _CONTEXT_ONLY_MODES


def _is_simulation_only(capability: EvidenceCapability) -> bool:
    return capability.evidence_mode in _SIMULATION_ONLY_MODES or "simulation_state" in set(
        capability.modality
    )


def _is_historical_prior(capability: EvidenceCapability) -> bool:
    return capability.evidence_mode in _HISTORICAL_PRIOR_MODES or "historical_pdc_artifact" in set(
        capability.modality
    )


def _is_advisory_only_mode(capability: EvidenceCapability) -> bool:
    return (
        _is_simulation_only(capability)
        or _is_context_only(capability)
        or _is_historical_prior(capability)
        or _is_scholar_only_support(capability)
    )


def _is_scholar_only_support(capability: EvidenceCapability) -> bool:
    modalities = set(capability.modality)
    return capability.evidence_mode in _SCHOLAR_SUPPORT_MODES and modalities <= {"scholar_claim"}


def _is_unbacked_llm_candidate(capability: EvidenceCapability) -> bool:
    modalities = set(capability.modality)
    llm_derived = capability.metadata.get("llm_derived_construct")
    if (
        capability.evidence_mode not in _LLM_CANDIDATE_MODES
        and "llm_candidate" not in modalities
        and llm_derived is not True
    ):
        return False
    producer_backed = capability.metadata.get("producer_backed")
    if isinstance(producer_backed, bool):
        return not (producer_backed and bool(capability.source_assets))
    return not capability.source_assets


def _is_claim_evidence_use(claim_use: str) -> bool:
    return claim_use.strip().casefold() in _CLAIM_EVIDENCE_USES


def _independence_collapsed_above_limit(
    independence: CapabilityIndependenceFactor,
) -> bool:
    return independence.collapse_ratio > 0.7


def _factor_named(
    factors: Iterable[CapabilityAuthorityFactor],
    name: CapabilityAuthorityFactorName,
) -> CapabilityAuthorityFactor | None:
    for factor in factors:
        if factor.name == name:
            return factor
    return None


def _capability_model(capability: EvidenceCapability | Mapping[str, Any]) -> EvidenceCapability:
    if isinstance(capability, EvidenceCapability):
        return capability
    if isinstance(capability, Mapping):
        return EvidenceCapability.model_validate(dict(capability))
    raise CapabilityAuthorityError("capability must be an EvidenceCapability or mapping")


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _text_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        return tuple(
            dict.fromkeys(
                text
                for key in sorted(value)
                for text in [*_text_values(key), *_text_values(value[key])]
            )
        )
    if isinstance(value, Iterable):
        return tuple(dict.fromkeys(text for item in value for text in _text_values(item)))
    return ()


def _text_tuple(value: object) -> tuple[str, ...]:
    return tuple(sorted(_text_values(value)))


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


__all__ = [
    "AUTHORITY_FACTOR_NAMES",
    "CAPABILITY_AUTHORITY_RULE_VERSION",
    "CAPABILITY_AUTHORITY_SCHEMA_VERSION",
    "CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND",
    "CAPABILITY_PURPOSE_BINDING_PRODUCER_REF",
    "CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME",
    "CAPABILITY_PURPOSE_BINDING_SCHEMA_VERSION",
    "CAPABILITY_PURPOSE_BINDING_VERIFIER_REF",
    "POSTURE_THRESHOLDS",
    "AuthorityEnvelopeResult",
    "AuthorityPosture",
    "CapabilityAuthorityContext",
    "CapabilityAuthorityError",
    "CapabilityAuthorityFactor",
    "CapabilityAuthorityFactorName",
    "CapabilityBindingResult",
    "CapabilityBindingStatus",
    "CapabilityDiscoveryAuthorityResolver",
    "CapabilityPurposeBindingArtifactStore",
    "CapabilityPurposeBindingProducer",
    "CapabilityPurposeBindingProductionReceipt",
    "CapabilityPurposeBindingResolutionError",
    "CapabilityPurposeBindingVerification",
    "CapabilityPurposeBindingVerifier",
    "OwnerSignedCapabilityPurposeBinding",
    "compose_capability_authority",
]
