"""Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

This package boundary owns the `ArtifactID` wire format, manifest/reference
models, filesystem CAS implementation, dependency-graph reconstruction, and
detached-signature contracts. Runtime and governance layers should depend on
this facade instead of importing private artifact internals.
"""

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
from .protocol import ArtifactStore, AsyncArtifactStore, SignatureVerifyingArtifactStore
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


def artifact_manifest_profile_projection(manifest: ArtifactManifest) -> dict[str, object]:
    """Return the canonical, versioned CAS projection for a manifest view."""
    return ManifestLifecycle.profile_projection(manifest)


def artifact_manifest_profile_sha256(manifest: ArtifactManifest) -> str:
    """Return the canonical, versioned CAS digest for a manifest view."""
    return ManifestLifecycle.profile_sha256(manifest)


__all__ = [
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
    "ensure_private_key_permissions",
    "fsync_directory",
    "input_ref_from_artifact_ref",
    "resolve_dependency_graph",
]
