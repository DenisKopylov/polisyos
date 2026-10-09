"""Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

This package boundary owns the `ArtifactID` wire format, manifest/reference
models, filesystem CAS implementation, dependency-graph reconstruction, and
detached-signature contracts. Runtime and governance layers should depend on
this facade instead of importing private artifact internals.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ._atomic_write import (
    AtomicFileDurabilityError,
    ensure_directory_durable,
    fsync_directory,
)
from ._integrity_ops import ArtifactIntegrityError, VerificationReport
from ._manifest_lifecycle import ManifestLifecycle
from ._transfer_ops import ExportReport, ImportReport
from .async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
)
from .backends.config import ArtifactStoreConfig, build_artifact_store
from .cas_integrity_report import CASIntegrityReport, build_cas_integrity_report
from .graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    NodeStatus,
    resolve_dependency_graph,
)
from .ids import ArtifactID
from .manifest import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    EnvInfo,
    GitInfo,
    InputRef,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from .ownership import ArtifactOwnershipError, ArtifactOwnershipIndex
from .protocol import (
    AUTHORITY_ENVELOPE_ARTIFACT_KIND,
    AUTHORITY_ENVELOPE_SCHEMA_NAME,
    AUTHORITY_ENVELOPE_SCHEMA_VERSION,
    ArtifactStore,
    AsyncArtifactStore,
    SignatureVerifyingArtifactStore,
    resolve_authority_envelope_ref,
    resolve_manifest_by_profile,
)
from .registry import RegistryBundle
from .signing import (
    ArtifactSigner,
    ArtifactSigningResult,
    ArtifactVerifier,
    BulkSigningReport,
    BulkVerificationReport,
    DetachedSignature,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureStatement,
    SignatureVerificationResult,
    SignatureVerificationStatus,
    SigningConfig,
    compute_key_id,
    ensure_private_key_permissions,
)
from .store import FileSystemCAS, PutOptions
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from .ir_adapter import ensure_ir_artifact_store as ensure_ir_artifact_store


def __getattr__(name: str) -> Any:
    """Resolve optional artifact adapters without introducing package cycles."""
    if name == "ensure_ir_artifact_store":
        from .ir_adapter import ensure_ir_artifact_store

        return ensure_ir_artifact_store
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def artifact_manifest_profile_projection(manifest: ArtifactManifest) -> dict[str, object]:
    """Return the canonical, versioned CAS projection for a manifest view."""
    return ManifestLifecycle.profile_projection(manifest)


def artifact_manifest_profile_sha256(manifest: ArtifactManifest) -> str:
    """Return the canonical, versioned CAS digest for a manifest view."""
    return ManifestLifecycle.profile_sha256(manifest)


def expected_artifact_manifest_for_write(
    *,
    artifact_id: ArtifactID,
    data: bytes,
    opts: ArtifactWriteOptions,
    created_at: datetime,
) -> ArtifactManifest:
    """Reconstruct the exact current manifest emitted for a CAS write.

    Args:
        artifact_id: Content address of ``data``.
        data: Exact bytes supplied to the writer.
        opts: Complete write profile supplied to the writer.
        created_at: Persisted manifest creation timestamp.

    Returns:
        The current manifest model reconstructed from the write inputs.

    Raises:
        ValueError: If ``artifact_id`` does not match the supplied payload bytes.
    """
    return ManifestLifecycle.expected_for_write(
        artifact_id=artifact_id,
        data=data,
        opts=opts,
        created_at=created_at,
    )


__all__ = [
    "AUTHORITY_ENVELOPE_ARTIFACT_KIND",
    "AUTHORITY_ENVELOPE_SCHEMA_NAME",
    "AUTHORITY_ENVELOPE_SCHEMA_VERSION",
    "ArtifactGovernanceInfo",
    "ArtifactID",
    "ArtifactIntegrityError",
    "ArtifactManifest",
    "ArtifactOwnershipError",
    "ArtifactOwnershipIndex",
    "ArtifactRef",
    "ArtifactSigner",
    "ArtifactSigningResult",
    "ArtifactStore",
    "ArtifactStoreConfig",
    "ArtifactVerifier",
    "ArtifactWriteOptions",
    "AsyncArtifactStore",
    "AsyncArtifactStoreAdapter",
    "AsyncFileSystemArtifactStore",
    "AtomicFileDurabilityError",
    "BulkSigningReport",
    "BulkVerificationReport",
    "CASIntegrityReport",
    "CanonInfo",
    "DependencyEdge",
    "DependencyGraph",
    "DependencyNode",
    "DetachedSignature",
    "Ed25519Signer",
    "Ed25519Verifier",
    "EnvInfo",
    "ExportReport",
    "FileSystemCAS",
    "GitInfo",
    "ImportReport",
    "InputRef",
    "IntegrityInfo",
    "KeyPair",
    "NodeStatus",
    "ProducerInfo",
    "PutOptions",
    "RegistryBundle",
    "SchemaInfo",
    "SignatureStatement",
    "SignatureVerificationResult",
    "SignatureVerificationStatus",
    "SignatureVerifyingArtifactStore",
    "SigningConfig",
    "VerificationReport",
    "WarningRecord",
    "artifact_manifest_profile_projection",
    "artifact_manifest_profile_sha256",
    "artifact_ref_identity_key",
    "build_artifact_store",
    "build_cas_integrity_report",
    "compute_key_id",
    "ensure_async_artifact_store",
    "ensure_directory_durable",
    "ensure_ir_artifact_store",
    "ensure_private_key_permissions",
    "expected_artifact_manifest_for_write",
    "fsync_directory",
    "input_ref_from_artifact_ref",
    "resolve_authority_envelope_ref",
    "resolve_dependency_graph",
    "resolve_manifest_by_profile",
]
