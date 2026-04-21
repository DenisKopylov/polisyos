"""Persistence helpers for external cross-backend equivalence certificates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes
from polisyos.core.security.slsa.models import (
    BuildDefinition,
    BuildMetadata,
    BuilderInfo,
    DigestSet,
    InTotoStatement,
    ResourceDescriptor,
    RunDetails,
    SLSAProvenancePredicate,
    Subject,
)
from polisyos.foundry.methods.equivalence.protocol import (
    CrossBackendEquivalenceCertificate,
    EQUIVALENCE_CERTIFICATE_KIND,
    EQUIVALENCE_CERTIFICATE_SCHEMA,
    EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import InputRef, ProducerInfo


EQUIVALENCE_ATTESTATION_KIND = "foundry.cross_backend_equivalence_attestation"
EQUIVALENCE_ATTESTATION_SCHEMA = "polisyos.foundry.cross_backend_equivalence_attestation"
EQUIVALENCE_ATTESTATION_SCHEMA_VERSION = "0.1.0"
EQUIVALENCE_ATTESTATION_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
EQUIVALENCE_BUILDER_ID = "https://polisyos.io/builders/backend-equivalence"


@dataclass(frozen=True, slots=True)
class PersistedEquivalenceArtifacts:
    """References produced when a certificate is persisted with attestations."""

    certificate_ref: ArtifactRef
    attestation_ref: ArtifactRef | None = None
    signature_key_id: str | None = None
    signer_identity: str | None = None


def persist_equivalence_certificate(
    *,
    store: ArtifactStore,
    certificate: CrossBackendEquivalenceCertificate,
    producer: "ProducerInfo | None" = None,
    inputs: list["InputRef"] | None = None,
) -> ArtifactRef:
    """Persist a certificate as an external CAS artifact."""

    return store.put_json(
        certificate.as_dict(),
        ArtifactWriteOptions(
            kind=EQUIVALENCE_CERTIFICATE_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=EQUIVALENCE_CERTIFICATE_SCHEMA,
                version=EQUIVALENCE_CERTIFICATE_SCHEMA_VERSION,
            ),
            producer=producer,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_equivalence_certificate(
    *,
    store: ArtifactStore,
    ref: str | ArtifactRef | ArtifactID,
) -> CrossBackendEquivalenceCertificate:
    """Load one persisted certificate from an artifact reference or ID string."""

    artifact_id = _coerce_artifact_id(ref)
    payload = from_canonical_bytes(store.get_bytes(artifact_id))
    if not isinstance(payload, dict):
        raise TypeError("equivalence certificate payload must be a mapping")
    return CrossBackendEquivalenceCertificate.from_dict(payload)


def persist_attested_equivalence_certificate(
    *,
    store: FileSystemCAS,
    certificate: CrossBackendEquivalenceCertificate,
    producer: "ProducerInfo | None" = None,
    inputs: list["InputRef"] | None = None,
    signer: Ed25519Signer | None = None,
    signer_identity: str | None = None,
    builder_id: str = EQUIVALENCE_BUILDER_ID,
) -> PersistedEquivalenceArtifacts:
    """Persist a certificate and emit companion attestation/signature artifacts."""

    certificate_ref = persist_equivalence_certificate(
        store=store,
        certificate=certificate,
        producer=producer,
        inputs=inputs,
    )

    signature_key_id: str | None = None
    if signer is not None:
        signature = store.sign_artifact(
            certificate_ref.artifact_id,
            signer,
            signer_identity=signer_identity,
        )
        signature_key_id = signature.key_id

    attestation = _build_equivalence_attestation(
        certificate=certificate,
        certificate_ref=certificate_ref,
        inputs=inputs or [],
        builder_id=builder_id,
        signer_identity=signer_identity,
        signature_key_id=signature_key_id,
    )
    attestation_ref = store.put_json(
        attestation.model_dump(mode="python", by_alias=False),
        ArtifactWriteOptions(
            kind=EQUIVALENCE_ATTESTATION_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=EQUIVALENCE_ATTESTATION_SCHEMA,
                version=EQUIVALENCE_ATTESTATION_SCHEMA_VERSION,
            ),
            producer=producer,
            inputs=inputs or [],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PersistedEquivalenceArtifacts(
        certificate_ref=certificate_ref,
        attestation_ref=attestation_ref,
        signature_key_id=signature_key_id,
        signer_identity=signer_identity,
    )


def verify_persisted_equivalence_certificate(
    *,
    store: FileSystemCAS,
    ref: str | ArtifactRef | ArtifactID,
    verifier: Ed25519Verifier,
    strict_identity: bool | None = None,
) -> SignatureVerificationResult:
    """Verify the detached CAS signature for one persisted certificate."""

    artifact_id = _coerce_artifact_id(ref)
    return store.verify_signature(
        artifact_id,
        verifier,
        strict_identity=strict_identity,
    )


def _build_equivalence_attestation(
    *,
    certificate: CrossBackendEquivalenceCertificate,
    certificate_ref: ArtifactRef,
    inputs: list["InputRef"],
    builder_id: str,
    signer_identity: str | None,
    signature_key_id: str | None,
) -> InTotoStatement:
    created_at = _coerce_timestamp(certificate.created_at)
    finished_at = created_at or datetime.now(UTC).replace(microsecond=0)
    dependencies = [
        ResourceDescriptor(
            uri=f"cas://sha256:{input_ref.artifact_id.hex}",
            digest=DigestSet(sha256=input_ref.artifact_id.hex),
            name=input_ref.role,
            annotations={},
        )
        for input_ref in inputs
    ]
    internal_parameters: dict[str, Any] = {
        "certificate_id": certificate.certificate_id,
        "method_fqn": certificate.method_fqn,
        "comparator_version": certificate.comparator_version,
        "global_verdict": (
            None if certificate.global_verdict is None else certificate.global_verdict.value
        ),
        "runtime_envelope": certificate.runtime_envelope.as_dict(),
    }
    if signer_identity is not None:
        internal_parameters["signer_identity"] = signer_identity
    if signature_key_id is not None:
        internal_parameters["signature_key_id"] = signature_key_id

    external_parameters: dict[str, Any] = {
        "confidence": certificate.confidence,
        "test_vectors": dict(certificate.test_vectors),
        "provenance": dict(certificate.provenance),
    }

    return InTotoStatement(
        subject=[
            Subject(
                name=f"cas://sha256:{certificate_ref.artifact_id.hex}",
                digest=DigestSet(sha256=certificate_ref.artifact_id.hex),
            )
        ],
        predicate=SLSAProvenancePredicate(
            buildDefinition=BuildDefinition(
                build_type="https://polisyos.io/BackendEquivalenceCertificate/v1",
                external_parameters=external_parameters,
                internal_parameters=internal_parameters,
                resolved_dependencies=dependencies,
            ),
            runDetails=RunDetails(
                builder=BuilderInfo(
                    id=builder_id,
                    version={"polisyos.xbeq": certificate.comparator_version},
                ),
                metadata=BuildMetadata(
                    invocation_id=certificate.certificate_id,
                    started_on=finished_at,
                    finished_on=finished_at,
                ),
            ),
        ),
    )


def _coerce_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _coerce_artifact_id(ref: str | ArtifactRef | ArtifactID) -> ArtifactID:
    if isinstance(ref, ArtifactID):
        return ref
    if isinstance(ref, ArtifactRef):
        return ref.artifact_id
    return ArtifactID.model_validate(ref)


__all__ = [
    "EQUIVALENCE_ATTESTATION_KIND",
    "EQUIVALENCE_ATTESTATION_PREDICATE_TYPE",
    "EQUIVALENCE_ATTESTATION_SCHEMA",
    "EQUIVALENCE_ATTESTATION_SCHEMA_VERSION",
    "PersistedEquivalenceArtifacts",
    "load_equivalence_certificate",
    "persist_attested_equivalence_certificate",
    "persist_equivalence_certificate",
    "verify_persisted_equivalence_certificate",
]
