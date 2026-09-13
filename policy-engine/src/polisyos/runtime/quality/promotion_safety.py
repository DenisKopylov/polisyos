"""Custody for protected-promotion requests, without an invented safety policy.

The N9 owner invokes this producer for a protected evaluation mode. Candidate
source signatures establish attribution only. The promotion-purpose rule and
appointed authority remain typed and empty; no result here can authorize promotion.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon

PROMOTION_SAFETY_REQUEST_KIND = "runtime.promotion_safety_request"
PROMOTION_SAFETY_REQUEST_SCHEMA = "policyos.runtime.promotion_safety_request.v1"
PROMOTION_SAFETY_CANDIDATE_KIND = "runtime.promotion_safety_candidate_evidence"
PROMOTION_SAFETY_CANDIDATE_SCHEMA = "policyos.runtime.promotion_safety_candidate_evidence.v1"
PROMOTION_SAFETY_REQUEST_TYPE = "PromotionSafetyRequest"
PROTECTED_PROMOTION_MODES = frozenset({"sandbox_pilot", "field_pilot", "deployment"})
_OWNER = "polisyos.runtime.quality.promotion_safety"
_UNRESOLVED = (
    "promotion_purpose_policy_not_established",
    "promotion_authority_appointment_not_established",
    "candidate_evidence_semantics_not_admitted",
    "candidate_evidence_references_not_read",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromotionSafetyScope(_StrictModel):
    """Exact candidate, problem, value evidence and requested protected operation."""

    purpose: Literal["protected_promotion_safety"] = "protected_promotion_safety"
    design_problem_id: str = Field(min_length=1)
    problem_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_summary_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    value_receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evaluation_mode: Literal["sandbox_pilot", "field_pilot", "deployment"]
    promotion_schema_version: str = Field(min_length=1)


class PromotionSafetyAcceptanceSlot(_StrictModel):
    """The unanswered deciding rule and appointment; source signatures cannot fill it."""

    purpose: Literal["protected_promotion_safety"] = "protected_promotion_safety"
    promotion_rule_ref: None = None
    appointed_authority_ref: None = None
    independently_verified_acceptance_ref: None = None
    status: Literal["not_established"] = "not_established"


class PromotionSafetySourcePrincipal(_StrictModel):
    """Owner-configured source attribution, granting no promotion-purpose authority."""

    identity: str = Field(min_length=1)
    public_key_pem: str = Field(min_length=1)


class PromotionSafetySourceTrust(_StrictModel):
    """Immutable source trust installed separately from candidate context."""

    principals: tuple[PromotionSafetySourcePrincipal, ...] = ()
    purpose: Literal["candidate_source_attribution_only"] = "candidate_source_attribution_only"


class PromotionSafetyCandidateEvidence(_StrictModel):
    """Signed candidate evidence references, with no declared deciding predicate."""

    schema_version: Literal["policyos.runtime.promotion_safety_candidate_evidence.v1"] = (
        PROMOTION_SAFETY_CANDIDATE_SCHEMA
    )
    purpose: Literal["promotion_safety_candidate_evidence"] = "promotion_safety_candidate_evidence"
    scope: PromotionSafetyScope
    evidence_refs: tuple[str, ...] = ()
    authority_status: Literal["candidate_only"] = "candidate_only"


class PromotionSafetyRead(_StrictModel):
    """An actual CAS read or failed attempt; digests distinguish bytes from projections."""

    source_ref: str
    operation: Literal["blob", "parsed_manifest", "signature_verification"]
    status: Literal["read", "unreadable"]
    content_hash: str | None = None
    detail: str | None = None


class PromotionSafetySourceAttempt(_StrictModel):
    """Current source custody assessment; no evidence semantics are inferred."""

    source_ref: str
    status: Literal[
        "candidate_custody_verified",
        "source_unresolved",
        "source_content_invalid",
        "source_scope_mismatch",
        "source_signature_unverified",
    ]
    signer_identity: str | None = None
    inputs_read: tuple[PromotionSafetyRead, ...]


class PromotionSafetyRequest(_StrictModel):
    """Persisted promotion-purpose request and complete attempted source population."""

    schema_version: Literal["policyos.runtime.promotion_safety_request.v1"] = (
        PROMOTION_SAFETY_REQUEST_SCHEMA
    )
    scope: PromotionSafetyScope
    acceptance_slot: PromotionSafetyAcceptanceSlot = Field(
        default_factory=PromotionSafetyAcceptanceSlot
    )
    source_refs: tuple[str, ...] = ()
    source_input_error: str | None = None
    source_trust_content_hash: str
    source_attempts: tuple[PromotionSafetySourceAttempt, ...] = ()
    inputs_read: tuple[PromotionSafetyRead, ...] = ()
    unresolved_by_construction: tuple[str, ...] = _UNRESOLVED
    authoritative_for: Literal["promotion_request_custody"] = "promotion_request_custody"
    promotion_authority_status: Literal["not_established"] = "not_established"


class PromotionSafetyResolution(_StrictModel):
    """Current independent request replay, always below promotion authority."""

    custody_status: Literal["verified", "not_established"] = "not_established"
    request_ref: str | None = None
    limitation_code: str
    source_attempts: tuple[PromotionSafetySourceAttempt, ...] = ()
    inputs_read: tuple[PromotionSafetyRead, ...] = ()
    unresolved_by_construction: tuple[str, ...] = _UNRESOLVED
    promotion_authority_status: Literal["not_established"] = "not_established"


def _hash(raw: bytes) -> str:
    return "sha256:" + canon.content_hash(raw)


def _projection_hash(value: BaseModel) -> str:
    return _hash(canon.to_canonical_bytes(value.model_dump(mode="json")))


class PromotionSafetyOwner:
    """Persist and replay requests through the existing CAS and signature verifier."""

    def __init__(
        self, *, store: artifacts.ArtifactStore, trust: PromotionSafetySourceTrust | None = None
    ) -> None:
        self._store = store
        self._trust = trust if trust is not None else PromotionSafetySourceTrust()
        if type(self._trust) is not PromotionSafetySourceTrust:
            raise TypeError("promotion_safety_trust_must_be_owner_configured")
        self._verifier = artifacts.Ed25519Verifier(strict_identity=True)
        self._principals: dict[str, str] = {}
        for principal in self._trust.principals:
            key_id = self._verifier.load_trusted_key_pem(
                principal.public_key_pem.encode(), identity=principal.identity
            )
            if key_id in self._principals:
                raise ValueError("promotion_safety_source_key_alias")
            self._principals[key_id] = principal.identity

    def _read(self, ref: str, *, kind: str, schema: str, reads: list[PromotionSafetyRead]) -> bytes:
        operation: Literal["blob", "parsed_manifest"] = "blob"
        try:
            raw = self._store.get_bytes(ref)
            reads.append(
                PromotionSafetyRead(
                    source_ref=ref, operation="blob", status="read", content_hash=_hash(raw)
                )
            )
            operation = "parsed_manifest"
            manifest = self._store.get_manifest(ref)
            reads.append(
                PromotionSafetyRead(
                    source_ref=ref,
                    operation=operation,
                    status="read",
                    content_hash=_projection_hash(manifest),
                    detail="canonical_parsed_manifest_projection_not_raw_manifest_bytes",
                )
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reads.append(
                PromotionSafetyRead(
                    source_ref=ref,
                    operation=operation,
                    status="unreadable",
                    detail=type(exc).__name__,
                )
            )
            raise
        if (
            _hash(raw) != ref
            or str(manifest.artifact_id) != ref
            or manifest.byte_size != len(raw)
            or manifest.integrity.sha256 != ref.removeprefix("sha256:")
            or manifest.kind != kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema != artifacts.SchemaInfo(name=kind, version=schema)
        ):
            raise ValueError("promotion_safety_content_or_manifest_mismatch")
        return raw

    def _source_attempt(
        self, ref: str, scope: PromotionSafetyScope
    ) -> PromotionSafetySourceAttempt:
        reads: list[PromotionSafetyRead] = []
        status = "source_unresolved"
        signer = None
        try:
            raw = self._read(
                ref,
                kind=PROMOTION_SAFETY_CANDIDATE_KIND,
                schema=PROMOTION_SAFETY_CANDIDATE_SCHEMA,
                reads=reads,
            )
            status = "source_content_invalid"
            candidate = PromotionSafetyCandidateEvidence.model_validate_json(raw)
            if candidate.scope != scope:
                status = "source_scope_mismatch"
            else:
                status = "source_signature_unverified"
                verify = getattr(self._store, "verify_signature", None)
                if not callable(verify):
                    reads.append(
                        PromotionSafetyRead(
                            source_ref=ref,
                            operation="signature_verification",
                            status="unreadable",
                            detail="signature_port_unavailable",
                        )
                    )
                else:
                    result = verify(ref, self._verifier, strict_identity=True)
                    reads.append(
                        PromotionSafetyRead(
                            source_ref=ref,
                            operation="signature_verification",
                            status="read",
                            detail=f"current_exact_blob_manifest_sidecar:{result.status.value}",
                        )
                    )
                    if (
                        result.status is artifacts.SignatureVerificationStatus.VALID
                        and result.signer_identity is not None
                        and self._principals.get(result.key_id or "") == result.signer_identity
                    ):
                        signer = result.signer_identity
                        status = "candidate_custody_verified"
        except (OSError, ValueError, TypeError, KeyError):
            if reads and all(item.status == "read" for item in reads):
                status = "source_content_invalid"
        return PromotionSafetySourceAttempt(
            source_ref=ref, status=status, signer_identity=signer, inputs_read=tuple(reads)
        )

    def _request(
        self,
        *,
        scope: PromotionSafetyScope,
        source_refs: tuple[str, ...],
        source_input_error: str | None,
    ) -> PromotionSafetyRequest:
        attempts = tuple(self._source_attempt(ref, scope) for ref in source_refs)
        unresolved = list(_UNRESOLVED)
        if any(read.status == "unreadable" for row in attempts for read in row.inputs_read):
            unresolved.append("source_evidence_unreadable")
        if source_input_error is not None:
            unresolved.append("source_reference_input_invalid")
        return PromotionSafetyRequest(
            scope=scope,
            source_refs=source_refs,
            source_input_error=source_input_error,
            source_trust_content_hash=_projection_hash(self._trust),
            source_attempts=attempts,
            inputs_read=tuple(read for row in attempts for read in row.inputs_read),
            unresolved_by_construction=tuple(unresolved),
        )

    def produce(
        self,
        *,
        scope: PromotionSafetyScope,
        source_refs: tuple[str, ...] = (),
        source_input_error: str | None = None,
    ) -> artifacts.ArtifactRef:
        """Persist real attempted source custody, retaining the unfilled semantic slot."""
        request = self._request(
            scope=scope, source_refs=source_refs, source_input_error=source_input_error
        )
        return self._store.put_json(
            request.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind=PROMOTION_SAFETY_REQUEST_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=PROMOTION_SAFETY_REQUEST_KIND, version=PROMOTION_SAFETY_REQUEST_SCHEMA
                ),
                producer=artifacts.ProducerInfo(component=_OWNER, version="1"),
            ),
        )

    def resolve(
        self, *, request_ref: str, scope: PromotionSafetyScope
    ) -> PromotionSafetyResolution:
        """Resolve bytes, rebind scope and repeat source verification before custody is consumed."""
        reads: list[PromotionSafetyRead] = []
        limitation = "promotion_safety_request_unresolved"
        attempts: tuple[PromotionSafetySourceAttempt, ...] = ()
        unresolved = _UNRESOLVED
        try:
            raw = self._read(
                request_ref,
                kind=PROMOTION_SAFETY_REQUEST_KIND,
                schema=PROMOTION_SAFETY_REQUEST_SCHEMA,
                reads=reads,
            )
            request = PromotionSafetyRequest.model_validate_json(raw)
            if request.scope != scope:
                limitation = "promotion_safety_request_scope_mismatch"
            else:
                current = self._request(
                    scope=scope,
                    source_refs=request.source_refs,
                    source_input_error=request.source_input_error,
                )
                reads.extend(current.inputs_read)
                attempts = current.source_attempts
                unresolved = current.unresolved_by_construction
                if current != request:
                    limitation = "promotion_safety_request_source_drift"
                else:
                    return PromotionSafetyResolution(
                        custody_status="verified",
                        request_ref=request_ref,
                        limitation_code="promotion_safety_policy_and_authority_not_established",
                        source_attempts=attempts,
                        inputs_read=tuple(reads),
                        unresolved_by_construction=unresolved,
                    )
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if any(row.status == "unreadable" for row in reads):
            unresolved = (*unresolved, "request_or_source_evidence_unreadable")
        return PromotionSafetyResolution(
            limitation_code=limitation,
            source_attempts=attempts,
            inputs_read=tuple(reads),
            unresolved_by_construction=unresolved,
        )
