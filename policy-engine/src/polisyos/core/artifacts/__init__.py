"""Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

This package boundary owns the `ArtifactID` wire format, manifest/reference
models, filesystem CAS implementation, dependency-graph reconstruction, and
detached-signature contracts. Runtime and governance layers should depend on
this facade instead of importing private artifact internals.
"""

from ._integrity_ops import VerificationReport
from ._transfer_ops import ExportReport, ImportReport
from .async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
)
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
)
from .ownership import ArtifactOwnershipError, ArtifactOwnershipIndex
from .protocol import ArtifactStore, AsyncArtifactStore
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

__all__ = [
    "ArtifactID",
    "ArtifactManifest",
    "ArtifactOwnershipError",
    "ArtifactOwnershipIndex",
    "ArtifactRef",
    "ArtifactSigner",
    "ArtifactSigningResult",
    "ArtifactStore",
    "ArtifactVerifier",
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
    "SigningConfig",
    "VerificationReport",
    "WarningRecord",
    "build_cas_integrity_report",
    "compute_key_id",
    "ensure_async_artifact_store",
    "ensure_private_key_permissions",
    "resolve_dependency_graph",
]
