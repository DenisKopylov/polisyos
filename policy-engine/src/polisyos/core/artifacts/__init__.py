"""Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

This package boundary owns the `ArtifactID` wire format, manifest/reference
models, filesystem CAS implementation, dependency-graph reconstruction, and
detached-signature contracts. Runtime and governance layers should depend on
this facade instead of importing private artifact internals.
"""

from ._integrity_ops import ArtifactIntegrityError, VerificationReport
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
from .manifest_profile import (
    artifact_manifest_profile_projection,
    artifact_manifest_profile_sha256,
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
    "ensure_private_key_permissions",
    "input_ref_from_artifact_ref",
    "resolve_dependency_graph",
]
