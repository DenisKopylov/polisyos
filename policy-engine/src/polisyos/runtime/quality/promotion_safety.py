"""Custody for protected-promotion requests, without an invented safety policy.

The N9 owner invokes this producer for a protected evaluation mode. Candidate
source signatures establish attribution only. The promotion-purpose rule and
appointed authority remain typed and empty; no result here can authorize promotion.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon
from polisyos.runtime.http.errors import RuntimeDependencyError

PROMOTION_SAFETY_REQUEST_KIND = "runtime.promotion_safety_request"
PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA = "policyos.runtime.promotion_safety_request.v1"
PROMOTION_SAFETY_REQUEST_SCHEMA = "policyos.runtime.promotion_safety_request.v2"
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
    signature_verification_outcome: Literal[
        "malformed_reference",
        "capability_unavailable",
        "backend_unavailable",
        "verifier_raised",
        "result_artifact_id_mismatch",
        "signature_rejected",
        "verified",
    ] | None = None


class _LegacyPromotionSafetySourceAttemptV1(_StrictModel):
    """Frozen attempt projection written by request schema v1."""

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


class _LegacyPromotionSafetyRequestV1(_StrictModel):
    """Historical v1 request shape retained for exact replay only."""

    schema_version: Literal["policyos.runtime.promotion_safety_request.v1"] = (
        PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA
    )
    scope: PromotionSafetyScope
    acceptance_slot: PromotionSafetyAcceptanceSlot = Field(
        default_factory=PromotionSafetyAcceptanceSlot
    )
    source_refs: tuple[str, ...] = ()
    source_input_error: str | None = None
    source_trust_content_hash: str
    source_attempts: tuple[_LegacyPromotionSafetySourceAttemptV1, ...] = ()
    inputs_read: tuple[PromotionSafetyRead, ...] = ()
    unresolved_by_construction: tuple[str, ...] = _UNRESOLVED
    authoritative_for: Literal["promotion_request_custody"] = "promotion_request_custody"
    promotion_authority_status: Literal["not_established"] = "not_established"


class PromotionSafetyRequest(_StrictModel):
    """Persisted promotion-purpose request and complete attempted source population."""

    schema_version: Literal["policyos.runtime.promotion_safety_request.v2"] = (
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


def _historical_v1_request_projection(request: PromotionSafetyRequest) -> dict[str, object]:
    """Serialize current request state using the immutable v1 persisted shape."""
    payload = request.model_dump(mode="json")
    payload["schema_version"] = PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA
    attempts = payload.get("source_attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if isinstance(attempt, dict):
                attempt.pop("signature_verification_outcome", None)
    return _LegacyPromotionSafetyRequestV1.model_validate(payload).model_dump(mode="json")


class PromotionSafetyOwner:
    """Persist and replay requests through the existing CAS and signature verifier."""

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        trust: PromotionSafetySourceTrust | None = None,
        signature_verifier: artifacts.SignatureVerifyingArtifactStore | None = None,
    ) -> None:
        self._store = store
        if signature_verifier is not None and signature_verifier.guarded_store is not store:
            raise ValueError("promotion_safety_signature_verifier_store_mismatch")
        self._signature_verifier = signature_verifier
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

    def _read(
        self,
        artifact_id: artifacts.ArtifactID,
        *,
        presented_ref: str,
        kind: str,
        schemas: tuple[str, ...],
        reads: list[PromotionSafetyRead],
    ) -> tuple[bytes, str]:
        operation: Literal["blob", "parsed_manifest"] = "blob"
        canonical_ref = str(artifact_id)
        try:
            raw = self._store.get_bytes(artifact_id)
            reads.append(
                PromotionSafetyRead(
                    source_ref=presented_ref,
                    operation="blob",
                    status="read",
                    content_hash=_hash(raw),
                )
            )
            operation = "parsed_manifest"
            manifest = self._store.get_manifest(artifact_id)
            reads.append(
                PromotionSafetyRead(
                    source_ref=presented_ref,
                    operation=operation,
                    status="read",
                    content_hash=_projection_hash(manifest),
                    detail="canonical_parsed_manifest_projection_not_raw_manifest_bytes",
                )
            )
        except (RuntimeDependencyError, OSError, ValueError, TypeError, KeyError) as exc:
            reads.append(
                PromotionSafetyRead(
                    source_ref=presented_ref,
                    operation=operation,
                    status="unreadable",
                    detail=type(exc).__name__,
                )
            )
            raise
        schema = manifest.artifact_schema
        schema_version = schema.version if schema is not None else ""
        if (
            _hash(raw) != canonical_ref
            or str(manifest.artifact_id) != canonical_ref
            or manifest.byte_size != len(raw)
            or manifest.integrity.sha256 != artifact_id.hex
            or manifest.kind != kind
            or manifest.media_type != "application/json"
            or schema is None
            or schema.name != kind
            or schema_version not in schemas
        ):
            raise ValueError("promotion_safety_content_or_manifest_mismatch")
        return raw, schema_version

    def _source_attempt(
        self, ref: str, scope: PromotionSafetyScope
    ) -> PromotionSafetySourceAttempt:
        reads: list[PromotionSafetyRead] = []
        status = "source_unresolved"
        signer = None
        outcome: Literal[
            "malformed_reference",
            "capability_unavailable",
            "backend_unavailable",
            "verifier_raised",
            "result_artifact_id_mismatch",
            "signature_rejected",
            "verified",
        ] | None = None
        try:
            requested_id = artifacts.ArtifactID.model_validate(ref)
        except (ValueError, TypeError):
            outcome = "malformed_reference"
            return PromotionSafetySourceAttempt(
                source_ref=ref,
                status=status,
                signer_identity=None,
                inputs_read=(),
                signature_verification_outcome=outcome,
            )

        try:
            raw, _schema_version = self._read(
                requested_id,
                presented_ref=ref,
                kind=PROMOTION_SAFETY_CANDIDATE_KIND,
                schemas=(PROMOTION_SAFETY_CANDIDATE_SCHEMA,),
                reads=reads,
            )
            status = "source_content_invalid"
            candidate = PromotionSafetyCandidateEvidence.model_validate_json(raw)
            if candidate.scope != scope:
                status = "source_scope_mismatch"
            else:
                status = "source_signature_unverified"
                if self._signature_verifier is None:
                    outcome = "capability_unavailable"
                    reads.append(
                        PromotionSafetyRead(
                            source_ref=ref,
                            operation="signature_verification",
                            status="unreadable",
                            detail="signature_port_unavailable",
                        )
                    )
                else:
                    try:
                        result = self._signature_verifier.verify_signature(
                            requested_id, self._verifier, strict_identity=True
                        )
                    except (RuntimeDependencyError, OSError, TimeoutError, ConnectionError):
                        outcome = "backend_unavailable"
                        reads.append(
                            PromotionSafetyRead(
                                source_ref=ref,
                                operation="signature_verification",
                                status="unreadable",
                                detail=outcome,
                            )
                        )
                    except Exception:
                        outcome = "verifier_raised"
                        reads.append(
                            PromotionSafetyRead(
                                source_ref=ref,
                                operation="signature_verification",
                                status="unreadable",
                                detail=outcome,
                            )
                        )
                    else:
                        if not isinstance(result, artifacts.SignatureVerificationResult):
                            outcome = "verifier_raised"
                            reads.append(
                                PromotionSafetyRead(
                                    source_ref=ref,
                                    operation="signature_verification",
                                    status="unreadable",
                                    detail=outcome,
                                )
                            )
                        else:
                            if result.artifact_id != str(requested_id):
                                outcome = "result_artifact_id_mismatch"
                                detail = outcome
                            elif (
                                result.status is artifacts.SignatureVerificationStatus.VALID
                                and result.signer_identity is not None
                                and self._principals.get(result.key_id or "")
                                == result.signer_identity
                            ):
                                signer = result.signer_identity
                                status = "candidate_custody_verified"
                                outcome = "verified"
                                detail = (
                                    "current_exact_blob_manifest_sidecar:"
                                    f"{result.status.value}"
                                )
                            else:
                                outcome = "signature_rejected"
                                detail = (
                                    "current_exact_blob_manifest_sidecar:"
                                    f"{result.status.value}"
                                )
                            reads.append(
                                PromotionSafetyRead(
                                    source_ref=ref,
                                    operation="signature_verification",
                                    status="read",
                                    detail=detail,
                                )
                            )
        except (RuntimeDependencyError, TimeoutError, ConnectionError):
            outcome = "backend_unavailable"
            if reads and all(item.status == "read" for item in reads):
                status = "source_content_invalid"
        except (OSError, ValueError, TypeError, KeyError):
            if reads and all(item.status == "read" for item in reads):
                status = "source_content_invalid"
        return PromotionSafetySourceAttempt(
            source_ref=ref,
            status=status,
            signer_identity=signer,
            inputs_read=tuple(reads),
            signature_verification_outcome=outcome,
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
        """Replay a schema-versioned request and reverify every source reference."""
        reads: list[PromotionSafetyRead] = []
        limitation = "promotion_safety_request_unresolved"
        attempts: tuple[PromotionSafetySourceAttempt, ...] = ()
        unresolved = _UNRESOLVED
        try:
            request_id = artifacts.ArtifactID.model_validate(request_ref)
            raw, request_schema = self._read(
                request_id,
                presented_ref=request_ref,
                kind=PROMOTION_SAFETY_REQUEST_KIND,
                schemas=(
                    PROMOTION_SAFETY_REQUEST_SCHEMA,
                    PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA,
                ),
                reads=reads,
            )
            if request_schema == PROMOTION_SAFETY_REQUEST_SCHEMA:
                request: PromotionSafetyRequest | _LegacyPromotionSafetyRequestV1 = (
                    PromotionSafetyRequest.model_validate_json(raw)
                )
            else:
                request = _LegacyPromotionSafetyRequestV1.model_validate_json(raw)
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
                if request_schema == PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA:
                    current_v1 = _historical_v1_request_projection(current)
                    replay_matches = canon.to_canonical_bytes(current_v1) == raw
                else:
                    replay_matches = current == request
                if not replay_matches:
                    limitation = "promotion_safety_request_source_drift"
                else:
                    return PromotionSafetyResolution(
                        custody_status="verified",
                        request_ref=str(request_id),
                        limitation_code="promotion_safety_policy_and_authority_not_established",
                        source_attempts=attempts,
                        inputs_read=tuple(reads),
                        unresolved_by_construction=unresolved,
                    )
        except (RuntimeDependencyError, OSError, ValueError, TypeError, KeyError):
            pass
        if any(row.status == "unreadable" for row in reads):
            unresolved = (*unresolved, "request_or_source_evidence_unreadable")
        return PromotionSafetyResolution(
            limitation_code=limitation,
            source_attempts=attempts,
            inputs_read=tuple(reads),
            unresolved_by_construction=unresolved,
        )
