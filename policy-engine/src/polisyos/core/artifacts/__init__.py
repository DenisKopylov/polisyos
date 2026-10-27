"""Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

This package boundary owns the `ArtifactID` wire format, manifest/reference
models, filesystem CAS implementation, dependency-graph reconstruction, and
detached-signature contracts. Runtime and governance layers should depend on
this facade instead of importing private artifact internals.
"""

from datetime import datetime
from importlib import import_module
from pathlib import Path as _Path
from typing import TYPE_CHECKING, Any

from ._atomic_write import (
    AtomicFileDurabilityError,
    ensure_directory_durable,
    fsync_directory,
)
from ._atomic_write import (
    AtomicFileWriter as _AtomicFileWriter,
)
from ._integrity_ops import (
    ArtifactBoundedManifestRead,
    ArtifactBoundedManifestReadError,
    ArtifactIntegrityError,
    ArtifactMemberReadBoundsError,
    ArtifactMemberReadIntegrityError,
    ArtifactReadBoundsError,
    ArtifactStoreReadUsage,
    VerificationReport,
)
from ._manifest_lifecycle import ManifestLifecycle as ManifestLifecycle
from ._profiled_ref import profile_bound_ref
from ._transfer_ops import ExportReport, ImportReport
from .async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
)
from .backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    with_ambient_ownership_enforcement_if_supported,
)
from .batch_control import BatchAuthorizationLossSignal
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
    ArtifactAuthorityInfo as ArtifactAuthorityInfo,
)
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
    artifact_reference_parts,
    input_ref_from_artifact_ref,
)
from .manifest import (
    ArtifactSameInputClosureInfo as ArtifactSameInputClosureInfo,
)
from .manifest import (
    ArtifactTenantContextInfo as ArtifactTenantContextInfo,
)
from .ownership import (
    OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1 as OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1,
)
from .ownership import (
    OWNERSHIP_INDEX_SCHEMA_VERSION as OWNERSHIP_INDEX_SCHEMA_VERSION,
)
from .ownership import (
    ArtifactOwnershipError,
    ArtifactOwnershipIndex,
    ArtifactReadOnlyUnavailableError,
)
from .protocol import (
    AUTHORITY_ENVELOPE_ARTIFACT_KIND,
    AUTHORITY_ENVELOPE_SCHEMA_NAME,
    AUTHORITY_ENVELOPE_SCHEMA_VERSION,
    ArtifactReader,
    ArtifactStore,
    AsyncArtifactStore,
    AsyncRawManifestBytesReader,
    CoreJSONArtifactBoundedInputManifestReader,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedManifestReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    CoreJSONArtifactBoundedMemberAttempt,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactBoundedMemberStream,
    CoreJSONArtifactMemberStream,
    CoreJSONArtifactProfileReader,
    CoreJSONArtifactStore,
    CoreJSONArtifactStreamingReader,
    RawManifestBytesReader,
    SignatureVerifyingArtifactStore,
    matches_runtime_protocol,
    matches_runtime_protocol_definition,
    require_return_selected_profile_writer,
    resolve_authority_envelope_ref,
    resolve_manifest_by_profile,
    validate_return_selected_profile,
)
from .protocol import (
    RootedArtifactStore as RootedArtifactStore,
)
from .registry import RegistryBundle
from .registry import RegistryBundlePayload as RegistryBundlePayload
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
from .store import (
    ArtifactMemberReceipt as ArtifactMemberReceipt,
)
from .store import (
    FileSystemCAS,
    PutOptions,
    ReadOnlyFileSystemCAS,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from .canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonManifestBoundedRead,
        CoreJsonReadBoundsRefusalError,
        CoreJsonReadLimits,
        aload_core_json_artifact,
        artifact_ref_for_manifest,
        decode_core_json_payload,
        load_core_json_artifact,
        load_core_json_frame_records,
        read_core_input_manifest_profile_bounded,
        read_core_json_artifact,
        read_core_json_artifact_bounded,
        read_core_json_artifact_bytes,
        read_core_manifest_profile,
        read_core_manifest_profile_bounded,
        validate_core_model_bounded_read,
        validate_core_model_json_artifact,
    )
    from .ir_adapter import (
        CoreToIRArtifactStoreAdapter,
        matches_artifact_store_protocol,
    )
    from .ir_adapter import ensure_ir_artifact_store as ensure_ir_artifact_store
    from .owned_json import (
        CoreArtifactOwnerProfile,
        CoreOwnedModelRead,
        validate_owned_core_model_json_artifact,
    )


def __getattr__(name: str) -> Any:
    """Resolve optional adapters and profile readers without package cycles."""
    if name in {
        "CoreToIRArtifactStoreAdapter",
        "ensure_ir_artifact_store",
        "matches_artifact_store_protocol",
    }:
        ir_adapter = import_module(".ir_adapter", __name__)
        return getattr(ir_adapter, name)
    if name in {
        "CoreJsonArtifactBoundedRead",
        "CoreJsonManifestBoundedRead",
        "CoreJsonReadBoundsRefusalError",
        "CoreJsonReadLimits",
        "aload_core_json_artifact",
        "artifact_ref_for_manifest",
        "decode_core_json_payload",
        "load_core_json_artifact",
        "load_core_json_frame_records",
        "read_core_json_artifact",
        "read_core_json_artifact_bounded",
        "read_core_json_artifact_bytes",
        "read_core_input_manifest_profile_bounded",
        "read_core_manifest_profile",
        "read_core_manifest_profile_bounded",
        "validate_core_model_bounded_read",
        "validate_core_model_json_artifact",
    }:
        canonical_profile = import_module(".canonical_profile", __name__)
        return getattr(canonical_profile, name)
    if name in {
        "CoreArtifactOwnerProfile",
        "CoreOwnedModelRead",
        "validate_owned_core_model_json_artifact",
    }:
        owned_json = import_module(".owned_json", __name__)
        return getattr(owned_json, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def artifact_manifest_profile_projection(
    manifest: ArtifactManifest,
) -> dict[str, object]:
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


def write_bytes_atomic(
    path: _Path,
    data: bytes,
    *,
    durable_parent: bool = False,
) -> None:
    """Atomically replace a local file using the existing Core writer.

    Args:
        path: Destination path to create or replace.
        data: Exact bytes to publish.
        durable_parent: Whether to require a successful parent-directory fsync.

    Raises:
        AtomicFileDurabilityError: If durable parent synchronization fails after
            the replacement has been published.
        OSError: If the underlying local filesystem write or replace fails.
    """
    _AtomicFileWriter.write_atomic(path, data, durable_parent=durable_parent)


def write_bytes_once(
    path: _Path,
    data: bytes,
    *,
    durable_parent: bool = False,
) -> bool:
    """Atomically create a file without replacing an existing path.

    Args:
        path: Destination path to create.
        data: Exact bytes to publish.
        durable_parent: Whether to require a successful parent-directory fsync.

    Returns:
        ``True`` when this call created the path, or ``False`` when the path
        already existed. A false result does not establish that existing bytes
        equal ``data``; callers that require idempotent reuse must compare them.

    Raises:
        AtomicFileDurabilityError: If durable parent synchronization fails after
            the file has been published.
    """
    return _AtomicFileWriter.write_once(path, data, durable_parent=durable_parent)


__all__ = [
    "AUTHORITY_ENVELOPE_ARTIFACT_KIND",
    "AUTHORITY_ENVELOPE_SCHEMA_NAME",
    "AUTHORITY_ENVELOPE_SCHEMA_VERSION",
    "OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1",
    "OWNERSHIP_INDEX_SCHEMA_VERSION",
    "ArtifactAuthorityInfo",
    "ArtifactBoundedManifestRead",
    "ArtifactBoundedManifestReadError",
    "ArtifactGovernanceInfo",
    "ArtifactID",
    "ArtifactIntegrityError",
    "ArtifactManifest",
    "ArtifactMemberReadBoundsError",
    "ArtifactMemberReadIntegrityError",
    "ArtifactMemberReceipt",
    "ArtifactOwnershipError",
    "ArtifactOwnershipIndex",
    "ArtifactReadBoundsError",
    "ArtifactReadOnlyUnavailableError",
    "ArtifactReader",
    "ArtifactRef",
    "ArtifactSameInputClosureInfo",
    "ArtifactSigner",
    "ArtifactSigningResult",
    "ArtifactStore",
    "ArtifactStoreConfig",
    "ArtifactStoreReadUsage",
    "ArtifactTenantContextInfo",
    "ArtifactVerifier",
    "ArtifactWriteOptions",
    "AsyncArtifactStore",
    "AsyncArtifactStoreAdapter",
    "AsyncFileSystemArtifactStore",
    "AsyncRawManifestBytesReader",
    "AtomicFileDurabilityError",
    "BatchAuthorizationLossSignal",
    "BulkSigningReport",
    "BulkVerificationReport",
    "CASIntegrityReport",
    "CanonInfo",
    "CoreArtifactOwnerProfile",
    "CoreJSONArtifactBoundedInputManifestReader",
    "CoreJSONArtifactBoundedInputManifestReceiptReader",
    "CoreJSONArtifactBoundedManifestReader",
    "CoreJSONArtifactBoundedManifestReceiptReader",
    "CoreJSONArtifactBoundedMemberAttempt",
    "CoreJSONArtifactBoundedMemberReader",
    "CoreJSONArtifactBoundedMemberStream",
    "CoreJSONArtifactMemberStream",
    "CoreJSONArtifactProfileReader",
    "CoreJSONArtifactStore",
    "CoreJSONArtifactStreamingReader",
    "CoreJsonArtifactBoundedRead",
    "CoreJsonManifestBoundedRead",
    "CoreJsonReadBoundsRefusalError",
    "CoreJsonReadLimits",
    "CoreOwnedModelRead",
    "CoreToIRArtifactStoreAdapter",
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
    "RawManifestBytesReader",
    "ReadOnlyFileSystemCAS",
    "RegistryBundle",
    "RegistryBundlePayload",
    "RootedArtifactStore",
    "SchemaInfo",
    "SignatureStatement",
    "SignatureVerificationResult",
    "SignatureVerificationStatus",
    "SignatureVerifyingArtifactStore",
    "SigningConfig",
    "VerificationReport",
    "WarningRecord",
    "aload_core_json_artifact",
    "artifact_manifest_profile_projection",
    "artifact_manifest_profile_sha256",
    "artifact_ref_for_manifest",
    "artifact_ref_identity_key",
    "artifact_reference_parts",
    "build_artifact_store",
    "build_cas_integrity_report",
    "compute_key_id",
    "decode_core_json_payload",
    "ensure_async_artifact_store",
    "ensure_directory_durable",
    "ensure_ir_artifact_store",
    "ensure_private_key_permissions",
    "expected_artifact_manifest_for_write",
    "fsync_directory",
    "input_ref_from_artifact_ref",
    "load_core_json_artifact",
    "load_core_json_frame_records",
    "matches_artifact_store_protocol",
    "matches_runtime_protocol",
    "matches_runtime_protocol_definition",
    "profile_bound_ref",
    "read_core_input_manifest_profile_bounded",
    "read_core_json_artifact",
    "read_core_json_artifact_bounded",
    "read_core_json_artifact_bytes",
    "read_core_manifest_profile",
    "read_core_manifest_profile_bounded",
    "require_return_selected_profile_writer",
    "resolve_authority_envelope_ref",
    "resolve_dependency_graph",
    "resolve_manifest_by_profile",
    "validate_core_model_bounded_read",
    "validate_core_model_json_artifact",
    "validate_owned_core_model_json_artifact",
    "validate_return_selected_profile",
    "with_ambient_ownership_enforcement_if_supported",
    "write_bytes_atomic",
    "write_bytes_once",
]
