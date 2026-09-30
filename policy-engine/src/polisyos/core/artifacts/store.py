"""Implement the filesystem CAS boundary for blobs, manifests, lineage, and signatures."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal

from pydantic import ValidationError

from ..canon import content_hash
from ..canon.canon_json import CanonSpec, to_canonical_bytes
from ..observability import get_metrics, get_tracer
from ..observability.config import is_hpc_observability_enabled
from . import _atomic_write as _atomic_write_module
from ._atomic_write import (
    AtomicFileDurabilityError as _AtomicFileDurabilityError,
)
from ._atomic_write import (
    AtomicFileWriter as _AtomicFileWriter,
)
from ._atomic_write import (
    ensure_directory_durable as _ensure_directory_durable,
)
from ._integrity_ops import (
    ArtifactIntegrityError,
)
from ._integrity_ops import (
    VerificationReport as VerificationReport,
)
from ._integrity_ops import (
    VerifiedArtifactSnapshot as _VerifiedArtifactSnapshot,
)
from ._integrity_ops import (
    load_verified_artifact_snapshot as _load_verified_artifact_snapshot,
)
from ._integrity_ops import (
    read_verified_blob as _read_verified_blob,
)
from ._integrity_ops import (
    validate_manifest_identity as _validate_manifest_identity,
)
from ._integrity_ops import (
    validate_read_integrity as _validate_read_integrity,
)
from ._integrity_ops import (
    verify_filesystem_artifact as _verify_filesystem_artifact,
)
from ._layout import CASPathLayout as _CASPathLayout
from ._manifest_lifecycle import ManifestLifecycle as _ManifestLifecycle
from ._signature_ops import (
    sign_all_artifacts as _sign_all_artifacts,
)
from ._signature_ops import (
    sign_artifact as _sign_artifact,
)
from ._signature_ops import (
    verify_all_signatures as _verify_all_signatures,
)
from ._signature_ops import (
    verify_signature as _verify_signature,
)
from ._transfer_ops import (
    ExportReport,
    ImportReport,
)
from ._transfer_ops import (
    artifact_id_from_member as _artifact_id_from_member,
)
from ._transfer_ops import (
    export_subgraph as _export_subgraph,
)
from ._transfer_ops import (
    import_subgraph as _import_subgraph,
)
from ._transfer_ops import (
    member_profile_sha256 as _member_profile_sha256,
)
from ._transfer_ops import (
    normalize_archive_path as _normalize_archive_path,
)
from ._transfer_ops import (
    safe_member_path as _safe_member_path,
)
from .ids import ArtifactID
from .manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    _coerce_input_ref,
)
from .manifest import (
    artifact_reference_parts as _artifact_reference,
)
from .ownership import (
    ArtifactOwnershipError,
    ArtifactOwnershipIndex,
    ArtifactTransactionPendingError,
    _ArtifactTransactionLease,
)
from .signing import (
    BulkSigningReport,
    BulkVerificationReport,
    DetachedSignature,
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
    SignatureVerificationStatus,
    SigningConfig,
    SigningError,
    load_signer_from_config,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from ..observability import MetricsRegistry, PolicyOSTracer
    from .backends.config import ArtifactStoreConfig


PutOptions = ArtifactWriteOptions
ArtifactMemberKind = Literal["blob", "manifest", "signature"]

_TRANSACTION_INTENT_SCHEMA = "policyos.artifact_ownership_transaction_intent.v2"
_TRANSACTION_INTENT_SCHEMA_V3 = "policyos.artifact_ownership_transaction_intent.v3"


@dataclass(frozen=True, slots=True)
class ArtifactMemberReceipt:
    """Content identity for bytes streamed from one selected CAS member."""

    member: str
    sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class CASInventoryEntry:
    """One exact selected artifact view in a stable CAS inventory."""

    artifact_ref: ArtifactID | ArtifactRef
    manifest: ArtifactManifest
    blob_sha256: str
    blob_byte_size: int
    manifest_sha256: str
    manifest_byte_size: int


@dataclass(frozen=True, slots=True)
class CASInventorySnapshot:
    """Three-valued inventory verdict with declared scope and evidence inputs."""

    verdict: Literal["pass", "fail", "UNRUN"]
    inputs: tuple[str, ...]
    unresolved_by_construction: tuple[str, ...]
    owner_generation_sha256: str | None
    entries: tuple[CASInventoryEntry, ...]
    reason: str | None = None


class _VerifiedCASMemberStream:
    """Read-only bounded stream that verifies bytes as its owner consumes them."""

    _CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        raw: BinaryIO,
        *,
        member: str,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        self._raw = raw
        self._member = member
        self._expected_sha256 = expected_sha256
        self._expected_size = expected_size
        self._digest = hashlib.sha256()
        self._byte_size = 0
        self._receipt: ArtifactMemberReceipt | None = None

    @property
    def size(self) -> int:
        """Return the size recorded for this member while its lease is held."""
        return self._expected_size

    @property
    def receipt(self) -> ArtifactMemberReceipt:
        """Return the verified content receipt after the complete stream is read."""
        if self._receipt is None:
            raise RuntimeError("cas_member_stream_not_verified")
        return self._receipt

    def read(self, size: int = -1) -> bytes:
        """Read at most one MiB and update the member digest."""
        if self._receipt is not None:
            return b""
        if size == 0:
            return b""
        limit = self._CHUNK_SIZE if size is None or size < 0 else min(size, self._CHUNK_SIZE)
        payload = self._raw.read(limit)
        if payload:
            self._digest.update(payload)
            self._byte_size += len(payload)
        else:
            self.finish()
        return payload

    def finish(self) -> ArtifactMemberReceipt:
        """Drain and verify the stream before releasing the artifact lease."""
        if self._receipt is not None:
            return self._receipt
        while payload := self._raw.read(self._CHUNK_SIZE):
            self._digest.update(payload)
            self._byte_size += len(payload)
        actual = self._digest.hexdigest()
        if self._byte_size != self._expected_size or actual != self._expected_sha256:
            raise ArtifactIntegrityError(f"CAS member changed while streaming: {self._member}")
        self._receipt = ArtifactMemberReceipt(
            member=self._member,
            sha256=actual,
            byte_size=self._byte_size,
        )
        return self._receipt


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _file_content_hash(path: Path) -> str:
    """Hash a CAS blob from disk without buffering the complete payload."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_access_scope() -> object | None:
    try:
        from polisyos.core.security.tenant_context import get_current_access_scope_or_none
    except ImportError:
        return None
    return get_current_access_scope_or_none()


def _current_tenant_id() -> str | None:
    try:
        from polisyos.core.security.tenant_context import get_current_tenant_id_or_none
    except ImportError:
        return None
    return get_current_tenant_id_or_none()


def _current_cell_id() -> str | None:
    try:
        from polisyos.core.security.tenant_context import get_current_cell_id
    except ImportError:
        return None
    return get_current_cell_id()


def _transactional_read(
    *,
    profile_argument_index: int | None = None,
    signature_surface: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Hold a shared artifact lease across an entire public CAS read."""

    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(method)
        def wrapped(
            self: FileSystemCAS,
            artifact_id: ArtifactID | ArtifactRef | str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            aid, profile_sha256, _ref = _artifact_reference(artifact_id)
            if profile_argument_index is not None:
                profile_sha256 = kwargs.get(
                    "manifest_profile_sha256",
                    args[profile_argument_index]
                    if len(args) > profile_argument_index
                    else profile_sha256,
                )
            with self._coordinator.artifact_lease(aid, exclusive=False):
                self._ownership_index.require_no_pending_transaction(
                    aid,
                    manifest_profile_sha256=profile_sha256,
                    signature_profile=(profile_sha256 or "default") if signature_surface else None,
                )
                return method(self, artifact_id, *args, **kwargs)

        return wrapped

    return decorate


class FileSystemCAS:
    """Store immutable artifacts in a sharded filesystem content-addressed store.

    The stable on-disk ABI is:
    - `<root>/artifacts/sha256/ab/cd/<hex>.blob`
    - `<root>/artifacts/sha256/ab/cd/<hex>.manifest.json`
    - `<root>/artifacts/sha256/ab/cd/<hex>.sig` for optional detached signatures

    `put_json` and `put_bytes` derive `ArtifactID` from payload bytes, persist an
    `ArtifactManifest` sidecar, and optionally sign on write according to
    `SigningConfig`. Read/verify helpers raise standard Python IO/validation
    exceptions for missing or malformed artifacts.
    """

    CONNECTOR_CACHE_NAMESPACE = "connector_cache"

    def __init__(
        self,
        root: Path,
        *,
        signing_config: SigningConfig | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        ownership_enforced: bool | None = None,
        ownership_requires_scope: bool = True,
        ownership_index: ArtifactOwnershipIndex | None = None,
    ) -> None:
        requested_root = Path(root)
        requested_root.mkdir(parents=True, exist_ok=True)
        canonical_root = requested_root.resolve(strict=True)
        self._ownership_index = ownership_index or ArtifactOwnershipIndex(canonical_root)
        if self._ownership_index.root != canonical_root:
            raise ValueError("filesystem_cas_ownership_root_mismatch")
        self.root = canonical_root
        self._coordinator = self._ownership_index._coordinator
        self._layout = _CASPathLayout(self.root)
        self.base = self._layout.base
        self.base.mkdir(parents=True, exist_ok=True)
        self._files = _AtomicFileWriter()
        self._manifests = _ManifestLifecycle()
        observability_enabled = is_hpc_observability_enabled()
        self._tracer = (
            tracer if tracer is not None else (_default_tracer() if observability_enabled else None)
        )
        self._metrics = (
            metrics
            if metrics is not None
            else (_default_metrics() if observability_enabled else None)
        )
        self._hpc_enabled = self._tracer is not None or self._metrics is not None
        self._signing_config = signing_config or SigningConfig.from_env()
        self._default_signer: Ed25519Signer | None = None
        self._signer_lock = threading.Lock()
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        self._ownership_enforced = (
            tenant_id is not None if ownership_enforced is None else bool(ownership_enforced)
        )
        self._ownership_requires_scope = bool(ownership_requires_scope)
        self._ownership_index.recover_orphan_stages()

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        return self._layout.paths(artifact_id)

    def _member_path(
        self,
        artifact_id: ArtifactID,
        member: ArtifactMemberKind,
        manifest_profile_sha256: str | None,
    ) -> Path:
        if member == "blob":
            return self._paths(artifact_id)[0]
        if member == "manifest":
            return self._manifest_path_for_ref(artifact_id, manifest_profile_sha256)
        if member == "signature":
            return self._sig_path(artifact_id, manifest_profile_sha256)
        raise ValueError("cas_member_kind_invalid")

    def _member_name(
        self,
        artifact_id: ArtifactID,
        member: ArtifactMemberKind,
        manifest_profile_sha256: str | None,
    ) -> str:
        """Return a stable archive locator without exposing the local path."""
        path = self._member_path(artifact_id, member, manifest_profile_sha256)
        return path.relative_to(self.root).as_posix()

    @contextmanager
    def open_member(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: ArtifactMemberKind,
    ) -> Iterator[_VerifiedCASMemberStream]:
        """Stream one selected member under its read lease with bounded memory.

        The context yields a read-only object with no filesystem path or file
        descriptor interface. The complete member is hashed before the lease is
        released, even if the caller reads only a prefix.
        """
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        with self._coordinator.artifact_lease(aid, exclusive=False):
            self._ownership_index.require_no_pending_transaction(
                aid,
                manifest_profile_sha256=profile_sha256,
                signature_profile=(profile_sha256 or "default") if member == "signature" else None,
            )
            self._require_blob_owner(aid, operation=f"read_{member}")
            if profile_sha256 is None:
                self._require_default_manifest_access(aid, operation=f"read_{member}")
            else:
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation=f"read_{member}_manifest",
                )

            manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
            if self._ownership_index._path_has_symlink_component(manifest_path):
                raise ArtifactIntegrityError("CAS manifest path crosses a symlink")
            manifest_bytes = manifest_path.read_bytes()
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if ref is not None and (
                ref.kind != manifest.kind or ref.media_type != manifest.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )

            selected_path = self._member_path(aid, member, profile_sha256)
            if self._ownership_index._path_has_symlink_component(selected_path):
                raise ArtifactIntegrityError("CAS member path crosses a symlink")
            descriptor = os.open(
                selected_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                opened_stat = os.fstat(descriptor)
                if not stat.S_ISREG(opened_stat.st_mode):
                    raise ArtifactIntegrityError("CAS member is not a regular file")

                if member == "blob":
                    expected_sha256 = aid.hex
                    expected_size = manifest.byte_size
                elif member == "manifest":
                    expected_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
                    expected_size = len(manifest_bytes)
                elif member == "signature":
                    if opened_stat.st_size > 1024 * 1024:
                        raise ArtifactIntegrityError("CAS signature member exceeds its size bound")
                    signature_bytes = os.read(descriptor, opened_stat.st_size + 1)
                    if len(signature_bytes) != opened_stat.st_size:
                        raise ArtifactIntegrityError("CAS signature changed while opening")
                    signature = DetachedSignature.model_validate_json(signature_bytes)
                    if (
                        signature.artifact_id != str(aid)
                        or signature.statement.blob_sha256 != aid.hex
                        or signature.statement.manifest_sha256
                        != hashlib.sha256(manifest_bytes).hexdigest()
                    ):
                        raise ArtifactIntegrityError(f"Signature binding mismatch for {aid}")
                    expected_sha256 = hashlib.sha256(signature_bytes).hexdigest()
                    expected_size = len(signature_bytes)
                    os.lseek(descriptor, 0, os.SEEK_SET)
                else:
                    raise ValueError("cas_member_kind_invalid")

                if opened_stat.st_size != expected_size:
                    raise ArtifactIntegrityError(f"CAS member size mismatch: {aid} {member}")
                raw = os.fdopen(descriptor, "rb")
                descriptor = -1
                stream = _VerifiedCASMemberStream(
                    raw,
                    member=self._member_name(aid, member, profile_sha256),
                    expected_sha256=expected_sha256,
                    expected_size=expected_size,
                )
                try:
                    yield stream
                except BaseException:
                    raw.close()
                    raise
                else:
                    try:
                        stream.finish()
                    finally:
                        raw.close()
            finally:
                if descriptor >= 0:
                    os.close(descriptor)

    def copy_member_to(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: ArtifactMemberKind,
        destination: BinaryIO,
    ) -> ArtifactMemberReceipt:
        """Copy a complete owner-verified member to a caller-owned stream."""
        with self.open_member(artifact_id, member) as source:
            while payload := source.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                destination.write(payload)
            return source.receipt

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Return declarative config needed to rebuild this store instance."""
        from .backends.config import ArtifactStoreConfig

        return ArtifactStoreConfig(backend="filesystem", root=str(self.root))

    def for_tenant(self, tenant_id: str, cell_id: str | None = None) -> FileSystemCAS:
        """Return a tenant-scoped view over the same immutable CAS root."""
        return FileSystemCAS(
            self.root,
            signing_config=self._signing_config,
            metrics=self._metrics,
            tracer=self._tracer,
            tenant_id=tenant_id,
            cell_id=cell_id,
            ownership_enforced=True,
            ownership_requires_scope=True,
            ownership_index=self._ownership_index,
        )

    def with_ambient_ownership_enforcement(self) -> FileSystemCAS:
        """Return a shared-CAS view that enforces ownership when a tenant scope exists."""
        if self._ownership_enforced:
            return self
        return FileSystemCAS(
            self.root,
            signing_config=self._signing_config,
            metrics=self._metrics,
            tracer=self._tracer,
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            ownership_enforced=True,
            ownership_requires_scope=False,
            ownership_index=self._ownership_index,
        )

    def record_artifact_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        writer: str | None = None,
    ) -> None:
        """Record a tenant ownership claim without changing the artifact ID."""
        if isinstance(artifact_id, str):
            artifact_id = ArtifactID.model_validate(artifact_id)
        owner_tenant, owner_cell = self._resolve_owner(
            tenant_id=tenant_id,
            cell_id=cell_id,
            required=True,
        )
        with self._coordinator.artifact_lease(artifact_id, exclusive=True) as lease:
            self._ownership_index.require_no_pending_transaction(artifact_id)
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=owner_tenant,
                cell_id=owner_cell,
                writer=writer,
                _lease=lease,
            )

    def ownership_evidence(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> dict[str, object]:
        """Return ownership-index evidence for debug and canary bundles."""
        owner_tenant, owner_cell = self._resolve_owner(
            tenant_id=tenant_id,
            cell_id=cell_id,
            required=False,
        )
        return self._ownership_index.evidence(
            tenant_id=owner_tenant,
            cell_id=owner_cell,
        )

    def _manifest_path_for_ref(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
    ) -> Path:
        if manifest_profile_sha256 is None:
            return self._paths(artifact_id)[1]
        return self._layout.view_manifest_path(artifact_id, manifest_profile_sha256)

    def _sig_path(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None = None,
    ) -> Path:
        if manifest_profile_sha256 is not None:
            return self._layout.view_sig_path(artifact_id, manifest_profile_sha256)
        return self._layout.sig_path(artifact_id)

    def _record_integrity_failure(self, *, reason: str) -> None:
        recorder = getattr(self._metrics, "record_artifact_integrity_failure", None)
        if callable(recorder):
            recorder(backend="filesystem", reason=reason)

    def _resolve_owner(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        required: bool,
    ) -> tuple[str | None, str | None]:
        owner_tenant = tenant_id or self._tenant_id
        owner_cell = cell_id if cell_id is not None else self._cell_id
        if owner_tenant is None:
            access_scope = _current_access_scope()
            if access_scope is not None:
                owner_tenant = getattr(access_scope, "tenant_id", None)
                owner_cell = owner_cell or getattr(access_scope, "cell_id", None)
        if owner_tenant is None:
            owner_tenant = _current_tenant_id()
            owner_cell = owner_cell or _current_cell_id()
        if required and not owner_tenant:
            raise ArtifactOwnershipError(
                "Tenant-scoped artifact operation requires an active tenant owner"
            )
        return owner_tenant, owner_cell

    def _require_artifact_owner(self, artifact_id: ArtifactID, *, operation: str) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            self._require_unclaimed_without_owner(artifact_id, operation=operation)
            return
        self._ownership_index.require_owner(
            artifact_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_blob_owner(self, artifact_id: ArtifactID, *, operation: str) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            self._require_unclaimed_without_owner(artifact_id, operation=operation)
            return
        self._ownership_index.require_blob_reader(
            artifact_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_manifest_view_owner(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
        *,
        operation: str,
    ) -> None:
        if manifest_profile_sha256 is None:
            self._require_artifact_owner(artifact_id, operation=operation)
            return
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            self._require_unclaimed_without_owner(artifact_id, operation=operation)
            return
        self._ownership_index.require_view_owner(
            artifact_id,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_unclaimed_without_owner(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
    ) -> None:
        if self._ownership_index.has_any_tenant_claim(artifact_id):
            raise ArtifactOwnershipError(
                f"Artifact {artifact_id} has tenant ownership claims; an active owner "
                f"is required for {operation}"
            )

    def _require_default_manifest_access(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
    ) -> None:
        """Authorize a default-view read using ownership evidence only."""
        self._require_artifact_owner(artifact_id, operation=operation)

    def _record_write_owner(
        self,
        artifact_id: ArtifactID,
        *,
        default_view_created: bool,
        lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            return
        if default_view_created:
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                writer="FileSystemCAS",
                _lease=lease,
            )
        else:
            self._ownership_index.record_blob_reader(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                writer="FileSystemCAS",
                _lease=lease,
            )

    def _record_write_view_owner(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str,
        *,
        lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            return
        self._ownership_index.record_view_owner(
            artifact_id,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            writer="FileSystemCAS",
            _lease=lease,
        )

    def _require_input_owners(self, opts: PutOptions) -> None:
        if not self._ownership_enforced:
            return
        for input_ref in opts.inputs or []:
            input_ref = _coerce_input_ref(input_ref)
            self._require_blob_owner(
                input_ref.artifact_id,
                operation=f"write input:{input_ref.role}",
            )
            self._require_manifest_view_owner(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
                operation=f"write input manifest:{input_ref.role}",
            )

    def _require_unclaimed_target_if_unscoped(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, _cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            self._require_unclaimed_without_owner(artifact_id, operation=operation)

    def _ensure_default_signer(self) -> Ed25519Signer:
        if self._default_signer is not None:
            return self._default_signer
        with self._signer_lock:
            if self._default_signer is None:
                self._default_signer = load_signer_from_config(self._signing_config)
        return self._default_signer

    def _maybe_sign_on_put(self, artifact_ref: ArtifactRef) -> None:
        config = self._signing_config
        if not (config.enabled and config.sign_on_put):
            return
        try:
            if self.has_signature(artifact_ref):
                return
            signer = self._ensure_default_signer()
            self.sign_artifact(
                artifact_ref,
                signer,
                signer_identity=config.default_identity,
            )
        except Exception as exc:
            if config.sign_on_put_policy.strip().lower() == "warn":
                raise SigningError(
                    f"Artifact write completed but sign_on_put failed under warn policy: {exc}"
                ) from exc
            raise SigningError(f"Failed to sign artifact on put: {exc}") from exc

    @_transactional_read()
    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether the blob and selected manifest view exist."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        blob, _ = self._paths(aid)
        manifest = self._manifest_path_for_ref(aid, profile_sha256)
        exists = blob.exists() and manifest.exists()
        if exists and self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            if tenant_id is None:
                exists = not self._ownership_index.has_any_tenant_claim(aid)
            else:
                exists = self._ownership_index.is_view_owned_by(
                    aid,
                    profile_sha256,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ) if profile_sha256 is not None else self._ownership_index.is_owned_by(
                    aid,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
        if ref is not None and exists:
            try:
                self.get_manifest(ref)
            except (FileNotFoundError, ValueError, ArtifactOwnershipError):
                exists = False
        if self._hpc_enabled and self._metrics:
            if exists and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "existence_check"})
            elif not exists and self._metrics.artifact_cache_misses_total:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "existence_check"})
        return exists

    @_transactional_read(profile_argument_index=0)
    def has_manifest_view(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> bool:
        """Return whether an exact manifest view is present and owned by this store.

        This optional cache-admission probe does not infer metadata access from
        shared blob ownership.
        """
        aid = (
            ArtifactID.model_validate(artifact_id)
            if isinstance(artifact_id, str)
            else artifact_id
        )
        if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
            raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
        blob_path, _default_manifest_path = self._paths(aid)
        view_manifest_path = self._layout.view_manifest_path(aid, manifest_profile_sha256)
        if not blob_path.is_file() or not view_manifest_path.is_file():
            return False
        try:
            self._require_blob_owner(aid, operation="has_manifest_view")
            self._require_manifest_view_owner(
                aid,
                manifest_profile_sha256,
                operation="has_manifest_view",
            )
        except ArtifactOwnershipError:
            return False
        manifest = self._manifests.read(view_manifest_path)
        _validate_manifest_identity(aid, manifest)
        if self._manifests.profile_sha256(manifest) != manifest_profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        return True

    @_transactional_read()
    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Read artifact blob bytes and emit CAS read metrics/traces when enabled.

        Raises:
            FileNotFoundError: If the blob file is missing.
            OSError: If the blob file cannot be read.
        """
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        self._require_blob_owner(aid, operation="read")
        if profile_sha256 is not None:
            self._require_manifest_view_owner(aid, profile_sha256, operation="read_manifest")
        blob, _ = self._paths(aid)
        if not self._hpc_enabled or self._tracer is None:
            return self._read_verified_blob(aid, blob, manifest_ref=ref)

        short_id = f"{aid.hex[:16]}..."
        with self._tracer.start_as_current_span(
            "cas.get_bytes",
            attributes={
                "cas.artifact_id": short_id,
                "cas.operation": "read",
            },
        ) as span:
            start = time.perf_counter()
            if not blob.exists():
                duration = time.perf_counter() - start
                if self._metrics and self._metrics.artifact_cache_misses_total:
                    self._metrics.artifact_cache_misses_total.add(1, {"kind": "blob"})
                if self._metrics and self._metrics.artifact_io_duration_seconds:
                    self._metrics.artifact_io_duration_seconds.record(
                        duration,
                        {"operation": "read", "kind": "blob", "cache_hit": "false"},
                    )
                span.set_attribute("cas.cache_hit", False)
                span.set_attribute("cas.duration_seconds", duration)
                raise FileNotFoundError(f"Artifact not found: {aid.hex}")

            data = self._read_verified_blob(aid, blob, manifest_ref=ref)
            duration = time.perf_counter() - start
            byte_size = len(data)

            if self._metrics and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "blob"})
            if self._metrics and self._metrics.artifact_io_bytes:
                self._metrics.artifact_io_bytes.record(
                    byte_size, {"operation": "read", "kind": "blob"}
                )
            if self._metrics and self._metrics.artifact_io_duration_seconds:
                self._metrics.artifact_io_duration_seconds.record(
                    duration,
                    {"operation": "read", "kind": "blob", "cache_hit": "true"},
                )

            span.set_attribute("cas.cache_hit", True)
            span.set_attribute("cas.byte_size", byte_size)
            span.set_attribute("cas.duration_seconds", duration)

            return data

    def import_exact_view(
        self,
        data: bytes,
        manifest_bytes: bytes,
        *,
        artifact_id: ArtifactID | ArtifactRef | str,
        signature_bytes: bytes | None = None,
    ) -> ArtifactRef:
        """Cache one already-owned CAS view without reconstructing signed bytes.

        The manifest and optional detached signature are validated and copied as
        their original bytes. An existing selector-free default is immutable; if
        it differs, the imported view is stored under its exact profile selector.
        Publication uses the same durable intent and owner-generation transaction
        as archive imports.
        """
        aid, requested_profile, ref = _artifact_reference(artifact_id)
        if content_hash(data) != aid.hex:
            raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")

        manifest = ArtifactManifest.model_validate_json(manifest_bytes)
        _validate_manifest_identity(aid, manifest)
        _validate_read_integrity(aid, data, manifest)
        profile_sha256 = self._manifests.profile_sha256(manifest)
        if requested_profile is not None and requested_profile != profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        if ref is not None and (ref.kind != manifest.kind or ref.media_type != manifest.media_type):
            raise ArtifactIntegrityError(
                f"Artifact reference type does not match selected manifest for {aid}"
            )

        if signature_bytes is not None:
            signature = DetachedSignature.model_validate_json(signature_bytes)
            if signature.artifact_id != str(aid):
                raise ArtifactIntegrityError(f"Signature artifact ID mismatch for {aid}")
            if signature.statement.blob_sha256 != aid.hex:
                raise ArtifactIntegrityError(f"Signature blob digest mismatch for {aid}")
            if signature.statement.manifest_sha256 != hashlib.sha256(manifest_bytes).hexdigest():
                raise ArtifactIntegrityError(f"Signature manifest digest mismatch for {aid}")

        prefix = (
            f"artifacts/sha256/{aid.hex[:2]}/{aid.hex[2:4]}/{aid.hex}"
        )
        blob_member = f"{prefix}.blob"
        manifest_member = (
            f"{prefix}.manifest.json"
            if requested_profile is None
            else f"{prefix}.view.{profile_sha256.removeprefix('sha256:')}.manifest.json"
        )
        members = {blob_member, manifest_member}
        if signature_bytes is not None:
            members.add(manifest_member.removesuffix(".manifest.json") + ".sig")

        staging_root = Path(tempfile.mkdtemp(prefix=".cas-import-exact-", dir=self.root))

        def write_staged_member(member: str, payload: bytes) -> None:
            safe_path = _safe_member_path(member)
            if safe_path is None or safe_path.as_posix() != member:
                raise ArtifactIntegrityError("CAS exact import member path is unsafe")
            target = staging_root / Path(*safe_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                target,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())

        try:
            write_staged_member(blob_member, data)
            write_staged_member(manifest_member, manifest_bytes)
            if signature_bytes is not None:
                signature_member = manifest_member.removesuffix(".manifest.json") + ".sig"
                write_staged_member(signature_member, signature_bytes)
            imported = self._publish_staged_import(
                staging_root,
                members,
                {str(aid)},
            )
        finally:
            if staging_root.exists() and not staging_root.is_symlink():
                shutil.rmtree(staging_root)

        expected_profile = requested_profile or profile_sha256
        selected = next(
            (
                imported_ref
                for imported_ref in imported
                if imported_ref.manifest_profile_sha256 == expected_profile
            ),
            None,
        )
        if requested_profile is None:
            selected = next(
                (
                    imported_ref
                    for imported_ref in imported
                    if imported_ref.manifest_profile_sha256 is None
                ),
                selected,
            )
        if selected is None:
            raise ArtifactIntegrityError("CAS exact import did not publish its selected view")
        return selected

    @_transactional_read()
    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        """Load and validate the default or explicitly selected manifest view.

        Raises:
            FileNotFoundError: If the manifest file is missing.
            ValueError: If the manifest JSON does not match `ArtifactManifest`.
        """
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        if profile_sha256 is not None:
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="read_manifest",
            )
        else:
            self._require_default_manifest_access(
                aid,
                operation="read_manifest",
            )
        manp = self._manifest_path_for_ref(aid, profile_sha256)
        manifest = self._manifests.read(manp)
        try:
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None:
                actual_profile = self._manifests.profile_sha256(manifest)
                if actual_profile != profile_sha256:
                    raise ArtifactIntegrityError(
                        f"Selected manifest profile mismatch for {aid}"
                    )
            if ref is not None and (
                ref.kind != manifest.kind or ref.media_type != manifest.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return manifest

    @_transactional_read()
    def get_manifest_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Return raw selected-manifest bytes through the owner read boundary."""
        with self.open_member(artifact_id, "manifest") as stream:
            chunks: list[bytes] = []
            while chunk := stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                chunks.append(chunk)
        return b"".join(chunks)

    def _resume_signature_transaction(
        self,
        *,
        intent: dict[str, Any],
        signature_bytes: bytes,
        artifact_id: ArtifactID,
        signature_selector: str,
        owner: dict[str, str | None] | None,
        lease: _ArtifactTransactionLease,
    ) -> None:
        """Resume only an exact selected-view signature request."""
        signature_specs = intent.get("signatures", [])
        if (
            intent["schema_version"] != _TRANSACTION_INTENT_SCHEMA_V3
            or intent["mode"] != "signature"
            or intent["owner"] != owner
            or intent["blob_sha256"] != f"sha256:{artifact_id.hex}"
            or len(signature_specs) != 1
            or signature_specs[0]["selector"] != signature_selector
            or signature_specs[0]["signature_sha256"]
            != content_hash(signature_bytes, prefix=True)
        ):
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )
        view_specs = [view for view in intent["views"] if view["selector"] == signature_selector]
        if len(view_specs) != 1:
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )
        view_spec = view_specs[0]
        manifest_path = self._manifest_path_for_ref(
            artifact_id,
            None if signature_selector == "default" else signature_selector,
        )
        manifest_bytes = manifest_path.read_bytes()
        if content_hash(manifest_bytes, prefix=True) != view_spec["manifest_sha256"]:
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )

        signature_path = self._sig_path(
            artifact_id,
            None if signature_selector == "default" else signature_selector,
        )
        stage = self._ensure_transaction_stage(
            operation_id=intent["operation_id"],
            name="signature.stage",
            recorded_path=signature_specs[0]["signature_stage"],
            data=signature_bytes,
            expected_sha256=signature_specs[0]["signature_sha256"],
            final_path=signature_path,
        )
        self._publish_transaction_member(
            stage,
            signature_path,
            expected_sha256=signature_specs[0]["signature_sha256"],
        )
        if not self._ownership_index._intent_completion_is_recomputed(intent):
            raise ArtifactIntegrityError("artifact_transaction_signature_not_recomputed")
        committed = dict(intent)
        committed["status"] = "committed"
        self._ownership_index.write_transaction_intent(
            artifact_id,
            committed,
            lease=lease,
        )
        self._ownership_index.remove_transaction_intent(artifact_id, lease=lease)
        self._remove_transaction_stage(intent["operation_id"])

    def put_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        signature: DetachedSignature,
    ) -> None:
        """Transactionally publish one immutable detached-signature sidecar."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        signature_selector = profile_sha256 or "default"
        signature_bytes = signature.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=2,
        ).encode("utf-8")
        if signature.artifact_id != str(aid):
            raise ValueError("signature artifact_id mismatch")

        with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(
                    required=self._ownership_requires_scope
                )
            owner = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            pending = self._ownership_index._read_transaction_intent(aid)
            if pending is not None:
                if self._ownership_index._committed_intent_matches_current_state(pending):
                    self._ownership_index.remove_transaction_intent(aid, lease=lease)
                    self._remove_transaction_stage(pending["operation_id"])
                elif pending["mode"] == "signature":
                    return self._resume_signature_transaction(
                        intent=pending,
                        signature_bytes=signature_bytes,
                        artifact_id=aid,
                        signature_selector=signature_selector,
                        owner=owner,
                        lease=lease,
                    )
                else:
                    raise ArtifactTransactionPendingError(aid, surface="artifact")

            self._ownership_index.require_no_pending_transaction(aid)
            self._require_blob_owner(aid, operation="put_signature")
            if profile_sha256 is None:
                self._require_default_manifest_access(aid, operation="put_signature")
            else:
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation="put_signature",
                )
            blob_path, _default_manifest = self._paths(aid)
            manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
            if (
                self._ownership_index._path_has_symlink_component(blob_path)
                or self._ownership_index._path_has_symlink_component(manifest_path)
            ):
                raise ArtifactIntegrityError("CAS signature binding crosses a symlink")
            manifest_bytes = manifest_path.read_bytes()
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if _file_content_hash(blob_path) != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")
            if (
                signature.statement.blob_sha256 != aid.hex
                or signature.statement.manifest_sha256
                != hashlib.sha256(manifest_bytes).hexdigest()
            ):
                raise ValueError("signature statement does not match the selected artifact view")

            signature_path = self._sig_path(aid, profile_sha256)
            self._prepare_import_destination(signature_path, member=signature_path.name)
            if signature_path.exists():
                existing = signature_path.read_bytes()
                if existing != signature_bytes:
                    raise ArtifactIntegrityError("immutable signature sidecar conflicts")
                return None

            claims = self._ownership_index._transaction_claims_for(
                aid,
                tenant_id=tenant_id if owner is not None else None,
                cell_id=cell_id,
                manifest_profile_sha256=self._manifests.profile_sha256(manifest),
            )
            if owner is None and self._ownership_index.has_any_tenant_claim(aid):
                raise ArtifactOwnershipError(
                    f"Artifact {aid} signature write requires its current tenant owner"
                )
            operation_id = uuid.uuid4().hex
            signature_sha256 = content_hash(signature_bytes, prefix=True)
            intent: dict[str, Any] = {
                "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                "status": "pending",
                "mode": "signature",
                "operation_id": operation_id,
                "artifact_id": str(aid),
                "owner": owner,
                "blob_sha256": "sha256:" + aid.hex,
                "blob_stage": None,
                "views": [
                    {
                        "selector": signature_selector,
                        "manifest_profile_sha256": self._manifests.profile_sha256(manifest),
                        "manifest_sha256": content_hash(manifest_bytes, prefix=True),
                        "manifest_stage": None,
                    }
                ],
                "claims": claims,
                "affected": {
                    "ambient_artifact": False,
                    "manifest_profiles": [],
                    "signature_profiles": [signature_selector],
                },
                "manifest_created_at": manifest.created_at.isoformat(),
                "signatures": [
                    {
                        "selector": signature_selector,
                        "signature_sha256": signature_sha256,
                        "signature_stage": self._transaction_stage_relative(
                            operation_id,
                            "signature.stage",
                        ),
                    }
                ],
                "request_sha256": "",
            }
            intent["request_sha256"] = self._ownership_index._transaction_request_digest(intent)
            self._ownership_index.write_transaction_intent(aid, intent, lease=lease)
            stage_path = self._stage_transaction_member(
                operation_id,
                "signature.stage",
                signature_bytes,
            )
            self._publish_transaction_member(
                stage_path,
                signature_path,
                expected_sha256=signature_sha256,
            )
            if not self._ownership_index._intent_completion_is_recomputed(intent):
                raise ArtifactIntegrityError("artifact_transaction_signature_not_recomputed")
            committed = dict(intent)
            committed["status"] = "committed"
            self._ownership_index.write_transaction_intent(aid, committed, lease=lease)
            self._ownership_index.remove_transaction_intent(aid, lease=lease)
            self._remove_transaction_stage(operation_id)

    @_transactional_read(signature_surface=True)
    def get_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> DetachedSignature | None:
        """Load a detached signature sidecar or return `None` when unsigned."""
        try:
            return DetachedSignature.model_validate_json(self.get_signature_bytes(artifact_id))
        except FileNotFoundError:
            return None

    @_transactional_read(signature_surface=True)
    def get_signature_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        """Return the exact detached-signature bytes for the selected manifest view."""
        aid, _profile_sha256, _ref = _artifact_reference(artifact_id)
        try:
            with self.open_member(artifact_id, "signature") as stream:
                chunks: list[bytes] = []
                while chunk := stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                    chunks.append(chunk)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Signature not found for artifact {aid}") from exc
        return b"".join(chunks)

    @_transactional_read(signature_surface=True)
    def has_signature(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether a detached signature sidecar exists for `artifact_id`."""
        try:
            self.get_signature_bytes(artifact_id)
        except FileNotFoundError:
            return False
        return True

    def sign_artifact(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        signer: Ed25519Signer,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        """Sign one stored artifact's blob+manifest pair and persist its sidecar."""
        aid, _profile_sha256, ref = _artifact_reference(artifact_id)
        selected: ArtifactID | ArtifactRef = ref or aid
        return _sign_artifact(
            artifact_id=aid,
            signer=signer,
            signer_identity=signer_identity,
            read_blob=lambda selected_id: self.get_bytes(selected),
            read_manifest_bytes=lambda selected_id: self.get_manifest_bytes(selected),
            write_signature=lambda selected_id, signature: self.put_signature(
                selected, signature
            ),
            load_snapshot=lambda selected_id: self._load_verified_snapshot(selected),
        )

    @_transactional_read(signature_surface=True)
    def verify_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        """Verify content integrity and detached signature trust/revocation/identity state."""
        try:
            aid, _profile_sha256, ref = _artifact_reference(artifact_id)
        except ValidationError:
            supplied_id = getattr(artifact_id, "artifact_id", artifact_id)
            if isinstance(supplied_id, ArtifactID):
                supplied_id = supplied_id.root
            result_id = (
                supplied_id
                if isinstance(supplied_id, str)
                else "<malformed-artifact-id>"
            )
            message = (
                "Malformed artifact reference"
                if isinstance(artifact_id, ArtifactRef)
                else "Malformed artifact ID"
            )
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=result_id,
                message=message,
            )
        selected: ArtifactID | ArtifactRef = ref or aid
        return _verify_signature(
            artifact_id=aid,
            verifier=verifier,
            strict_identity=strict_identity,
            verify_integrity=self.verify,
            load_signature=lambda selected_id: self.get_signature(selected),
            read_blob=lambda selected_id: self.get_bytes(selected),
            read_manifest_bytes=lambda selected_id: self.get_manifest_bytes(selected),
            load_snapshot=lambda selected_id: self._load_verified_snapshot(selected),
        )

    def sign_all_artifacts(
        self,
        signer: Ed25519Signer,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        signer_identity: str | None = None,
        only_unsigned: bool = True,
        max_workers: int = 8,
        pending_window: int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> BulkSigningReport:
        """Sign many artifacts concurrently and summarize signed/skipped/error counts."""
        ids = tuple(
            sorted(
                set(artifact_ids)
                if artifact_ids is not None
                else self._bulk_inventory_artifact_ids(),
                key=lambda artifact_id: artifact_id.hex,
            )
        )
        return _sign_all_artifacts(
            signer=signer,
            artifact_ids=ids,
            signer_identity=signer_identity,
            only_unsigned=only_unsigned,
            max_workers=max_workers,
            has_signature_for_artifact=self.has_signature,
            read_blob=self.get_bytes,
            read_manifest_bytes=self.get_manifest_bytes,
            write_signature=self.put_signature,
            pending_window=pending_window,
            cancel_event=cancel_event,
            load_snapshot=self._load_verified_snapshot,
        )

    def verify_all_signatures(
        self,
        verifier: Ed25519Verifier,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        max_workers: int = 8,
        strict_identity: bool | None = None,
        pending_window: int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> BulkVerificationReport:
        """Verify many artifact signatures concurrently and summarize verifier outcomes."""
        ids = tuple(
            sorted(
                set(artifact_ids)
                if artifact_ids is not None
                else self._bulk_inventory_artifact_ids(),
                key=lambda artifact_id: artifact_id.hex,
            )
        )
        return _verify_all_signatures(
            verifier=verifier,
            artifact_ids=ids,
            max_workers=max_workers,
            strict_identity=strict_identity,
            verify_one=lambda aid, v, strict: self.verify_signature(
                aid,
                v,
                strict_identity=strict,
            ),
            pending_window=pending_window,
            cancel_event=cancel_event,
        )

    def _transaction_stage_relative(self, operation_id: str, name: str) -> str:
        return (
            self._coordinator.transaction_root / "stage" / operation_id / name
        ).relative_to(self.root).as_posix()

    def _ensure_transaction_stage(
        self,
        *,
        operation_id: str,
        name: str,
        recorded_path: object,
        data: bytes,
        expected_sha256: str,
        final_path: Path,
    ) -> Path | None:
        expected_relative = self._transaction_stage_relative(operation_id, name)
        if recorded_path != expected_relative:
            raise ArtifactIntegrityError("CAS transaction stage reference mismatch")
        stage_path = self.root / expected_relative
        if self._ownership_index._path_has_symlink_component(stage_path):
            raise ArtifactIntegrityError("CAS transaction stage path crosses a symlink")
        if stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS transaction stage member is a symlink")
        if stage_path.exists():
            if not stage_path.is_file() or _file_content_hash(stage_path) != (
                expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError("CAS transaction stage digest mismatch")
            return stage_path
        if final_path.exists():
            if final_path.is_symlink() or not final_path.is_file() or _file_content_hash(
                final_path
            ) != expected_sha256.removeprefix("sha256:"):
                raise ArtifactIntegrityError("CAS transaction final member mismatch")
            return None
        return self._stage_transaction_member(operation_id, name, data)

    def _record_transaction_claims(
        self,
        artifact_id: ArtifactID,
        intent: dict[str, Any],
        *,
        lease: _ArtifactTransactionLease,
    ) -> None:
        owner = intent["owner"]
        if owner is None:
            return
        claims = intent["claims"]
        if claims["default_owner"]:
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )
        if claims["blob_reader"]:
            self._ownership_index.record_blob_reader(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )
        for profile_sha256 in claims["view_owners"]:
            self._ownership_index.record_view_owner(
                artifact_id,
                profile_sha256,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )

    def _resume_publish_transaction(
        self,
        *,
        intent: dict[str, Any],
        data: bytes,
        opts: PutOptions,
        artifact_id: ArtifactID,
        sha: str,
        owner: dict[str, str | None] | None,
        lease: _ArtifactTransactionLease,
    ) -> tuple[bool, str | None]:
        """Resume only the exact owner, content, and manifest-profile request."""
        if (
            intent["schema_version"]
            not in {
                "policyos.artifact_ownership_transaction_intent.v2",
                _TRANSACTION_INTENT_SCHEMA_V3,
            }
            or intent["mode"] != "publish"
            or intent["owner"] != owner
            or intent["blob_sha256"] != "sha256:" + sha
        ):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        created_at = datetime.fromisoformat(intent["manifest_created_at"])
        manifest = self._manifests.build(
            artifact_id=artifact_id,
            data=data,
            sha=sha,
            opts=opts,
            created_at=created_at,
        )
        manifest_bytes = self._manifests.to_bytes(manifest)
        profile_sha256 = self._manifests.profile_sha256(manifest)
        views = intent["views"]
        selected = [view for view in views if view["selector"] == profile_sha256]
        if len(selected) != 1 or selected[0]["manifest_profile_sha256"] != profile_sha256:
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
        selected_spec = selected[0]
        manifest_sha256 = content_hash(manifest_bytes, prefix=True)
        default_specs = [view for view in views if view["selector"] == "default"]
        if len(default_specs) > 1 or len(views) != 1 + len(default_specs):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
        default_spec = default_specs[0] if default_specs else None

        for spec in views:
            if spec["manifest_stage"] is None:
                continue
            if (
                spec["manifest_profile_sha256"] != profile_sha256
                or spec["manifest_sha256"] != manifest_sha256
            ):
                raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        claims = intent["claims"]
        if owner is None:
            expected_claims = {
                "default_owner": False,
                "blob_reader": False,
                "view_owners": [],
            }
        else:
            default_was_created = (
                default_spec is not None and default_spec["manifest_stage"] is not None
            )
            already_default_owner = self._ownership_index.is_owned_by(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
            )
            expected_claims = {
                "default_owner": bool(default_was_created or already_default_owner),
                "blob_reader": not default_was_created,
                "view_owners": [profile_sha256],
            }
        expected_affected = {
            "ambient_artifact": bool(
                intent["blob_stage"] is not None
                or (default_spec is not None and default_spec["manifest_stage"] is not None)
            ),
            "manifest_profiles": (
                [profile_sha256]
                if selected_spec["manifest_stage"] is not None or owner is not None
                else []
            ),
            "signature_profiles": [],
        }
        if claims != expected_claims or intent["affected"] != expected_affected:
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        blob_path, default_manifest_path = self._paths(artifact_id)
        blob_stage = self._ensure_transaction_stage(
            operation_id=intent["operation_id"],
            name="blob.stage",
            recorded_path=intent["blob_stage"],
            data=data,
            expected_sha256="sha256:" + sha,
            final_path=blob_path,
        ) if intent["blob_stage"] is not None else None
        if intent["blob_stage"] is None and not blob_path.is_file():
            raise ArtifactIntegrityError("CAS transaction blob stage is unavailable")
        self._publish_transaction_member(
            blob_stage,
            blob_path,
            expected_sha256="sha256:" + sha,
        )

        for spec in views:
            selector = spec["selector"]
            if selector == "default":
                final_path = default_manifest_path
                stage_name = "manifest-default.stage"
            else:
                final_path = self._layout.view_manifest_path(artifact_id, profile_sha256)
                stage_name = "manifest-view.stage"
            self._prepare_import_destination(
                final_path,
                member=final_path.relative_to(self.root).as_posix(),
            )
            recorded_stage = spec["manifest_stage"]
            stage_path: Path | None = None
            if recorded_stage is not None:
                stage_path = self._ensure_transaction_stage(
                    operation_id=intent["operation_id"],
                    name=stage_name,
                    recorded_path=recorded_stage,
                    data=manifest_bytes,
                    expected_sha256=spec["manifest_sha256"],
                    final_path=final_path,
                )
            elif not final_path.is_file():
                raise ArtifactIntegrityError("CAS transaction manifest stage is unavailable")
            self._publish_transaction_member(
                stage_path,
                final_path,
                expected_sha256=spec["manifest_sha256"],
            )

        self._record_transaction_claims(artifact_id, intent, lease=lease)
        if not self._ownership_index._intent_completion_is_recomputed(intent):
            raise ArtifactIntegrityError(
                "artifact_transaction_owner_generation_or_bytes_unverified"
            )
        committed_intent = dict(intent)
        committed_intent["status"] = "committed"
        self._ownership_index.write_transaction_intent(
            artifact_id,
            committed_intent,
            lease=lease,
        )
        self._ownership_index.remove_transaction_intent(artifact_id, lease=lease)
        self._remove_transaction_stage(intent["operation_id"])

        if default_spec is None or default_spec["manifest_profile_sha256"] != profile_sha256:
            reference_profile = profile_sha256
        else:
            reference_profile = None
        return intent["blob_stage"] is None, reference_profile

    def _put_blob_and_manifest_once(
        self,
        *,
        data: bytes,
        opts: PutOptions,
        aid: ArtifactID,
        sha: str,
    ) -> tuple[bool, str | None]:
        """Publish one blob/view under its durable deny-only owner intent."""
        blob_path, default_manifest_path = self._paths(aid)
        with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
            # Input ownership is mutable owner-generation state. Re-evaluate it
            # under the publication lease immediately before deriving selectors
            # and durable claims; the earlier public-boundary check is only a
            # fast rejection path.
            self._require_input_owners(opts)
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(
                    required=self._ownership_requires_scope
                )
            owner = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            prior_intent = self._ownership_index._read_transaction_intent(aid)
            if prior_intent is not None:
                if self._ownership_index._committed_intent_matches_current_state(prior_intent):
                    self._ownership_index.remove_transaction_intent(aid, lease=lease)
                    self._remove_transaction_stage(prior_intent["operation_id"])
                else:
                    return self._resume_publish_transaction(
                        intent=prior_intent,
                        data=data,
                        opts=opts,
                        artifact_id=aid,
                        sha=sha,
                        owner=owner,
                        lease=lease,
                    )
            self._ownership_index.require_no_pending_transaction(aid)
            self._require_unclaimed_target_if_unscoped(aid, operation="write")
            self._prepare_import_destination(blob_path, member=blob_path.name)
            self._prepare_import_destination(
                default_manifest_path,
                member=default_manifest_path.name,
            )

            blob_preexisted = blob_path.exists()
            if blob_preexisted and _file_content_hash(blob_path) != sha:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")

            manifest = self._manifests.build(
                artifact_id=aid,
                data=data,
                sha=sha,
                opts=opts,
            )
            manifest_bytes = self._manifests.to_bytes(manifest)
            profile_sha256 = self._manifests.profile_sha256(manifest)

            default_owner_admitted = False
            skip_default_manifest = False
            if owner is not None:
                default_owner_admitted = self._ownership_index.is_owned_by(
                    aid,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                skip_default_manifest = (
                    not default_owner_admitted
                    and (
                        default_manifest_path.exists()
                        or self._ownership_index.has_any_tenant_claim(aid)
                    )
                )

            default_bytes: bytes | None = None
            default_profile_sha256: str | None = None
            if not skip_default_manifest and default_manifest_path.exists():
                default_bytes = default_manifest_path.read_bytes()
                default_manifest = self._manifests.read(default_manifest_path)
                _validate_manifest_identity(aid, default_manifest)
                _validate_read_integrity(aid, data, default_manifest)
                default_profile_sha256 = self._manifests.profile_sha256(default_manifest)

            view_path = self._layout.view_manifest_path(aid, profile_sha256)
            self._prepare_import_destination(view_path, member=view_path.name)
            view_bytes: bytes | None = None
            if view_path.exists():
                view_bytes = view_path.read_bytes()
                existing_view = self._manifests.read(view_path)
                _validate_manifest_identity(aid, existing_view)
                _validate_read_integrity(aid, data, existing_view)
                if self._manifests.profile_projection(existing_view) != (
                    self._manifests.profile_projection(manifest)
                ):
                    raise ArtifactIntegrityError(
                        f"Manifest profile digest collision for {aid}"
                    )

            will_create_default = not skip_default_manifest and default_bytes is None
            will_create_view = view_bytes is None
            operation_id = uuid.uuid4().hex
            blob_stage_rel = (
                None if blob_preexisted else self._transaction_stage_relative(
                    operation_id,
                    "blob.stage",
                )
            )
            default_stage_rel = (
                self._transaction_stage_relative(operation_id, "manifest-default.stage")
                if will_create_default
                else None
            )
            view_stage_rel = (
                self._transaction_stage_relative(operation_id, "manifest-view.stage")
                if will_create_view
                else None
            )
            intent_views: list[dict[str, object]] = []
            if not skip_default_manifest:
                expected_default_bytes = default_bytes or manifest_bytes
                intent_views.append(
                    {
                        "selector": "default",
                        "manifest_profile_sha256": (
                            default_profile_sha256 or profile_sha256
                        ),
                        "manifest_sha256": content_hash(expected_default_bytes, prefix=True),
                        "manifest_stage": default_stage_rel,
                    }
                )
            expected_view_bytes = view_bytes or manifest_bytes
            intent_views.append(
                {
                    "selector": profile_sha256,
                    "manifest_profile_sha256": profile_sha256,
                    "manifest_sha256": content_hash(expected_view_bytes, prefix=True),
                    "manifest_stage": view_stage_rel,
                }
            )
            if owner is None:
                claims: dict[str, object] = {
                    "default_owner": False,
                    "blob_reader": False,
                    "view_owners": [],
                }
            else:
                claims = {
                    "default_owner": bool(will_create_default or default_owner_admitted),
                    "blob_reader": not will_create_default,
                    "view_owners": [profile_sha256],
                }
            affected_profiles = (
                [profile_sha256]
                if will_create_view or owner is not None
                else []
            )
            intent: dict[str, object] = {
                "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                "status": "pending",
                "mode": "publish",
                "operation_id": operation_id,
                "artifact_id": str(aid),
                "owner": owner,
                "blob_sha256": "sha256:" + sha,
                "blob_stage": blob_stage_rel,
                "views": intent_views,
                "claims": claims,
                "affected": {
                    "ambient_artifact": bool(not blob_preexisted or will_create_default),
                    "manifest_profiles": affected_profiles,
                    "signature_profiles": [],
                },
                "manifest_created_at": manifest.created_at.isoformat(),
                "signatures": [],
                "request_sha256": "",
            }
            intent["request_sha256"] = self._ownership_index._transaction_request_digest(
                intent
            )
            self._ownership_index.write_transaction_intent(aid, intent, lease=lease)

            try:
                blob_stage = (
                    self._stage_transaction_member(operation_id, "blob.stage", data)
                    if blob_stage_rel is not None
                    else None
                )
                default_stage = (
                    self._stage_transaction_member(
                        operation_id,
                        "manifest-default.stage",
                        manifest_bytes,
                    )
                    if default_stage_rel is not None
                    else None
                )
                view_stage = (
                    self._stage_transaction_member(
                        operation_id,
                        "manifest-view.stage",
                        manifest_bytes,
                    )
                    if view_stage_rel is not None
                    else None
                )
                self._publish_transaction_member(
                    blob_stage,
                    blob_path,
                    expected_sha256="sha256:" + sha,
                )
                if not skip_default_manifest:
                    self._publish_transaction_member(
                        default_stage,
                        default_manifest_path,
                        expected_sha256=str(intent_views[0]["manifest_sha256"]),
                    )
                self._publish_transaction_member(
                    view_stage,
                    view_path,
                    expected_sha256=str(intent_views[-1]["manifest_sha256"]),
                )
                self._record_transaction_claims(aid, intent, lease=lease)
                if not self._ownership_index._intent_completion_is_recomputed(intent):
                    raise ArtifactIntegrityError(
                        "artifact_transaction_owner_generation_or_bytes_unverified"
                    )
                committed_intent = dict(intent)
                committed_intent["status"] = "committed"
                self._ownership_index.write_transaction_intent(
                    aid,
                    committed_intent,
                    lease=lease,
                )
                self._ownership_index.remove_transaction_intent(aid, lease=lease)
                self._remove_transaction_stage(operation_id)
            except BaseException:
                # Keep the durable pending intent; visible state is never rolled back.
                raise

            if skip_default_manifest:
                reference_profile = profile_sha256
            elif default_profile_sha256 is None:
                reference_profile = None
            else:
                reference_profile = (
                    profile_sha256 if profile_sha256 != default_profile_sha256 else None
                )
            return blob_preexisted, reference_profile

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        """Store raw bytes under their content hash and create the immutable manifest sidecar."""
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        self._require_input_owners(opts)

        if not self._hpc_enabled or self._tracer is None:
            _deduplicated, ref_profile_sha256 = (
                self._put_blob_and_manifest_once(data=data, opts=opts, aid=aid, sha=sha)
            )
            ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=ref_profile_sha256,
            )
            self._maybe_sign_on_put(ref)
            return ref

        short_id = f"{aid.hex[:16]}..."
        byte_size = len(data)
        with self._tracer.start_as_current_span(
            "cas.put",
            attributes={
                "cas.artifact_id": short_id,
                "cas.operation": "write",
                "cas.kind": opts.kind,
                "cas.byte_size": byte_size,
            },
        ) as span:
            start = time.perf_counter()
            deduplicated, ref_profile_sha256 = self._put_blob_and_manifest_once(
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
            )

            duration = time.perf_counter() - start

            if self._metrics and self._metrics.artifact_operations_total:
                self._metrics.artifact_operations_total.add(
                    1, {"operation": "write", "kind": opts.kind}
                )
            if self._metrics and self._metrics.artifact_cache_hits_total and deduplicated:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "dedup"})
            if self._metrics and self._metrics.artifact_cache_misses_total and not deduplicated:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "dedup"})
            if self._metrics and self._metrics.artifact_io_bytes:
                self._metrics.artifact_io_bytes.record(
                    byte_size, {"operation": "write", "kind": opts.kind}
                )
            if self._metrics and self._metrics.artifact_io_duration_seconds:
                self._metrics.artifact_io_duration_seconds.record(
                    duration,
                    {
                        "operation": "write",
                        "kind": opts.kind,
                        "cache_hit": "true" if deduplicated else "false",
                    },
                )

            span.set_attribute("cas.deduplicated", deduplicated)
            span.set_attribute("cas.duration_seconds", duration)

            ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=ref_profile_sha256,
            )
            self._maybe_sign_on_put(ref)
            return ref

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Canonicalize a JSON-like payload, persist it as CAS bytes, and return its ref."""
        canon_spec = canon_spec or CanonSpec()
        data = to_canonical_bytes(obj, canon_spec)
        canon = opts.canon or CanonInfo.from_spec(canon_spec)
        opts2 = PutOptions(
            kind=opts.kind,
            media_type="application/json",
            schema=opts.schema,
            producer=opts.producer,
            env=opts.env,
            inputs=opts.inputs,
            canon=canon,
            governance=getattr(opts, "governance", None),
            tenant_context=getattr(opts, "tenant_context", None),
            same_input_closure=getattr(opts, "same_input_closure", None),
            authority=getattr(opts, "authority", None),
            warnings=getattr(opts, "warnings", None),
        )
        return self.put_bytes(data, opts2)

    @_transactional_read()
    def verify(self, artifact_id: ArtifactID | ArtifactRef | str) -> VerificationReport:
        """Check blob and exact selected manifest view integrity."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        if profile_sha256 is None:
            self._require_artifact_owner(aid, operation="verify")
        else:
            self._require_blob_owner(aid, operation="verify")
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="verify_manifest",
            )
        blob, _default_manifest = self._paths(aid)
        manp = self._manifest_path_for_ref(aid, profile_sha256)
        if not self._hpc_enabled or self._tracer is None:
            report = _verify_filesystem_artifact(aid, blob_path=blob, manifest_path=manp)
        else:
            short_id = f"{aid.hex[:16]}..."
            with self._tracer.start_as_current_span(
                "cas.verify",
                attributes={"cas.artifact_id": short_id},
            ) as span:
                report = _verify_filesystem_artifact(
                    aid,
                    blob_path=blob,
                    manifest_path=manp,
                )
                span.set_attribute("cas.verified", report.ok)
                if report.byte_size is not None:
                    span.set_attribute("cas.byte_size", report.byte_size)

        if report.ok and ref is not None:
            try:
                self.get_manifest(ref)
            except (OSError, ValueError) as exc:
                return report.model_copy(update={"ok": False, "error": str(exc)})
        return report

    def _verify_staged_artifact(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        staging_root: Path,
    ) -> VerificationReport:
        """Verify one staged pair while retaining this store's failure telemetry."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        blob, _default_manifest = self._paths(aid)
        manifest = self._manifest_path_for_ref(aid, profile_sha256)
        staged_blob = staging_root / blob.relative_to(self.root)
        staged_manifest = staging_root / manifest.relative_to(self.root)
        actual_sha = None
        byte_size = None
        try:
            if staged_blob.is_symlink() or staged_manifest.is_symlink():
                raise ArtifactIntegrityError("staged CAS member crosses a symlink")
            if not staged_blob.is_file() or not staged_manifest.is_file():
                raise FileNotFoundError("staged CAS member missing")
            actual_sha = _file_content_hash(staged_blob)
            byte_size = staged_blob.stat().st_size
            manifest_bytes = staged_manifest.read_bytes()
            manifest_model = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest_model)
            if actual_sha != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")
            if manifest_model.byte_size != byte_size:
                raise ArtifactIntegrityError(f"Manifest byte size mismatch for {aid}")
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest_model) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if ref is not None and (
                ref.kind != manifest_model.kind or ref.media_type != manifest_model.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            return VerificationReport(
                ok=False,
                artifact_id=str(aid),
                expected_sha256_hex=aid.hex,
                actual_sha256_hex=actual_sha,
                byte_size=byte_size,
                error=str(exc),
            )
        return VerificationReport(
            ok=True,
            artifact_id=str(aid),
            expected_sha256_hex=aid.hex,
            actual_sha256_hex=actual_sha,
            byte_size=byte_size,
        )

    def _prepare_import_destination(self, path: Path, *, member: str) -> None:
        """Create safe parent components and reject symlinked CAS paths."""
        if self.root.is_symlink():
            raise ArtifactIntegrityError("CAS root must not be a symlink")
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError(f"CAS member escapes root: {member}") from exc

        current = self.root
        for component in relative.parts[:-1]:
            current = current / component
            if current.is_symlink():
                raise ArtifactIntegrityError(f"CAS member crosses a symlink: {member}")
            if current.exists():
                if not current.is_dir():
                    raise ArtifactIntegrityError(f"CAS member parent is not a directory: {member}")
            else:
                try:
                    current.mkdir()
                except FileExistsError:
                    if not current.is_dir():
                        raise ArtifactIntegrityError(
                            f"CAS member parent is not a directory: {member}"
                        ) from None
                _atomic_write_module.fsync_directory(current.parent)
                if current.is_symlink() or not current.is_dir():
                    raise ArtifactIntegrityError(f"CAS member parent is unsafe: {member}")

        if path.is_symlink():
            raise ArtifactIntegrityError(f"CAS member must not be a symlink: {member}")
        if path.exists() and not path.is_file():
            raise ArtifactIntegrityError(f"CAS member is not a regular file: {member}")

    @staticmethod
    def _import_manifest_profile(manifest: ArtifactManifest) -> dict[str, object]:
        """Return immutable manifest profile fields, excluding identity/time fields."""
        return manifest.model_dump(
            mode="json",
            by_alias=True,
            exclude={"artifact_id", "byte_size", "created_at", "integrity"},
        )

    def _stage_transaction_member(
        self,
        operation_id: str,
        name: str,
        data: bytes,
    ) -> Path:
        """Write one fsynced member beneath an owner-private same-filesystem stage."""
        stage_directory = self._coordinator.transaction_root / "stage" / operation_id
        if self._ownership_index._path_has_symlink_component(stage_directory):
            raise ArtifactIntegrityError("CAS transaction stage path crosses a symlink")
        _ensure_directory_durable(stage_directory)
        stage_path = stage_directory / name
        if stage_path.is_symlink() or stage_path.exists():
            raise ArtifactIntegrityError("CAS transaction stage path already exists")
        self._files.write_once(stage_path, data, durable_parent=True)
        if not stage_path.is_file() or stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS transaction stage member is unsafe")
        if stage_path.stat().st_dev != self.root.stat().st_dev:
            raise ArtifactIntegrityError("CAS transaction stage is on another filesystem")
        return stage_path

    def _publish_transaction_member(
        self,
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        """Publish one immutable staged member and require its parent sync."""
        member = final_path.relative_to(self.root).as_posix()
        self._prepare_import_destination(final_path, member=member)
        if stage_path is not None:
            if (
                stage_path.is_symlink()
                or not stage_path.is_file()
                or stage_path.stat().st_dev != final_path.parent.stat().st_dev
            ):
                raise ArtifactIntegrityError("CAS transaction stage member is unsafe")
            if _file_content_hash(stage_path) != expected_sha256.removeprefix("sha256:"):
                raise ArtifactIntegrityError("CAS transaction stage digest mismatch")

        created = False
        if final_path.exists():
            if _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:"):
                raise ArtifactIntegrityError(f"Immutable CAS member conflicts: {member}")
        else:
            if stage_path is None:
                raise ArtifactIntegrityError(f"CAS transaction stage is missing: {member}")
            try:
                os.link(stage_path, final_path)
                created = True
            except FileExistsError:
                if (
                    final_path.is_symlink()
                    or not final_path.is_file()
                    or _file_content_hash(final_path)
                    != expected_sha256.removeprefix("sha256:")
                ):
                    raise ArtifactIntegrityError(
                        f"Immutable CAS member conflicts: {member}"
                    ) from None

        try:
            # This sync is strict even for a pre-existing member: a new owner
            # generation must not outrun the directory entry it relies on.
            _atomic_write_module.fsync_directory(final_path.parent)
        except OSError as exc:
            raise _AtomicFileDurabilityError(
                "CAS member exists but its parent directory sync failed",
                replaced=True,
            ) from exc
        if (
            final_path.is_symlink()
            or not final_path.is_file()
            or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
        ):
            raise ArtifactIntegrityError(f"CAS member digest mismatch: {member}")
        return created

    def _remove_transaction_stage(self, operation_id: str) -> None:
        stage_root = self._coordinator.transaction_root / "stage"
        stage_directory = stage_root / operation_id
        if stage_directory.is_symlink() or not stage_directory.exists():
            return
        if not stage_directory.is_dir():
            return
        if self._ownership_index._walk_private_regular_files(stage_directory) is None:
            return
        shutil.rmtree(stage_directory)
        _atomic_write_module.fsync_directory(stage_root)

    def _stage_import_source(
        self,
        *,
        operation_id: str,
        recorded_path: object,
        source_path: Path,
        final_path: Path,
        expected_sha256: str,
        resume: bool,
    ) -> Path | None:
        """Adopt one verified importer stage by hard link after durable intent."""
        if not isinstance(recorded_path, str):
            raise ArtifactIntegrityError("CAS import transaction stage reference missing")
        self._ownership_index._validate_transaction_stage_path(recorded_path, operation_id)
        stage_path = self.root / recorded_path
        if self._ownership_index._path_has_symlink_component(stage_path):
            raise ArtifactIntegrityError("CAS import transaction stage crosses a symlink")
        self._prepare_import_destination(stage_path, member=recorded_path)
        if stage_path.exists() and stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS import transaction stage is a symlink")

        if final_path.exists():
            if (
                final_path.is_symlink()
                or not final_path.is_file()
                or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError("CAS import final member digest mismatch")
            return None

        try:
            source_path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS import source escaped its owner root") from exc
        if (
            self._ownership_index._path_has_symlink_component(source_path)
            or source_path.is_symlink()
            or not source_path.is_file()
        ):
            raise ArtifactIntegrityError("CAS import source stage is not a regular file")
        source_stat = source_path.stat()
        if source_stat.st_uid != os.geteuid() or source_stat.st_dev != self.root.stat().st_dev:
            raise ArtifactIntegrityError("CAS import source stage is not owner-controlled")

        if stage_path.exists():
            if not stage_path.is_file() or _file_content_hash(stage_path) != (
                expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError(
                    "CAS import stage differs from the exact retry request"
                    if resume
                    else "CAS import stage already exists"
                )
        else:
            try:
                os.link(source_path, stage_path, follow_symlinks=False)
            except FileExistsError:
                if (
                    stage_path.is_symlink()
                    or not stage_path.is_file()
                    or _file_content_hash(stage_path)
                    != expected_sha256.removeprefix("sha256:")
                ):
                    raise ArtifactIntegrityError("CAS import stage publication conflict") from None
            if stage_path.is_symlink() or not stage_path.is_file():
                raise ArtifactIntegrityError("CAS import stage publication is unsafe")
            _atomic_write_module.fsync_directory(stage_path.parent)

        if (
            stage_path.stat().st_dev != self.root.stat().st_dev
            or _file_content_hash(stage_path) != expected_sha256.removeprefix("sha256:")
        ):
            raise ArtifactIntegrityError("CAS import staged member digest mismatch")
        return stage_path

    def _publish_staged_import(
        self,
        staging_root: Path,
        members: set[str],
        artifact_refs: set[str],
    ) -> tuple[ArtifactRef, ...]:
        """Publish each imported artifact through its durable owner transaction."""
        try:
            staging_root.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS import stage escaped its owner root") from exc
        if self._ownership_index._path_has_symlink_component(staging_root):
            raise ArtifactIntegrityError("CAS import staging root crosses a symlink")

        staged_by_artifact: dict[str, set[str]] = {}
        for member in sorted(members):
            safe_path = _safe_member_path(member)
            if safe_path is None or safe_path.as_posix() != member:
                raise ArtifactIntegrityError(f"Unsafe staged member: {member}")
            artifact_id = _artifact_id_from_member(member)
            if artifact_id is None:
                raise ArtifactIntegrityError(f"Staged member is not a CAS artifact: {member}")
            staged_by_artifact.setdefault(str(artifact_id), set()).add(member)
        if set(staged_by_artifact) != set(artifact_refs):
            raise ArtifactIntegrityError("Staged artifact set does not match transfer inventory")

        artifact_ids = tuple(
            ArtifactID.model_validate(value) for value in sorted(artifact_refs)
        )
        source_by_artifact: dict[str, dict[str, Any]] = {}
        lock_ids: dict[str, ArtifactID] = {aid.hex: aid for aid in artifact_ids}
        for artifact_id in artifact_ids:
            artifact_members = staged_by_artifact[str(artifact_id)]
            prefix = (
                f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                f"/{artifact_id.hex}"
            )
            blob_member = f"{prefix}.blob"
            if blob_member not in artifact_members:
                raise ArtifactIntegrityError(f"Import is missing blob for {artifact_id}")
            blob_source = staging_root / Path(*blob_member.split("/"))
            if (
                self._ownership_index._path_has_symlink_component(blob_source)
                or blob_source.is_symlink()
                or not blob_source.is_file()
            ):
                raise ArtifactIntegrityError("CAS import blob stage is unsafe")
            blob_sha, blob_size = self._stream_file_digest(blob_source)
            if blob_sha != artifact_id.hex:
                raise ArtifactIntegrityError(f"Staged blob content does not match {artifact_id}")

            manifest_members = sorted(
                member for member in artifact_members if member.endswith(".manifest.json")
            )
            if not manifest_members:
                raise ArtifactIntegrityError(f"Import is missing manifest views for {artifact_id}")
            source_views: list[dict[str, Any]] = []
            for manifest_member in manifest_members:
                manifest_source = staging_root / Path(*manifest_member.split("/"))
                if (
                    self._ownership_index._path_has_symlink_component(manifest_source)
                    or manifest_source.is_symlink()
                    or not manifest_source.is_file()
                ):
                    raise ArtifactIntegrityError("CAS import manifest stage is unsafe")
                if manifest_source.stat().st_size > 8 * 1024 * 1024:
                    raise ArtifactIntegrityError("CAS import manifest exceeds its size bound")
                manifest_data = manifest_source.read_bytes()
                manifest = ArtifactManifest.model_validate_json(manifest_data)
                _validate_manifest_identity(artifact_id, manifest)
                if manifest.byte_size != blob_size:
                    raise ArtifactIntegrityError(f"Manifest byte size mismatch for {artifact_id}")
                profile_sha256 = self._manifests.profile_sha256(manifest)
                encoded_profile = _member_profile_sha256(manifest_member)
                if encoded_profile is not None and encoded_profile != profile_sha256:
                    raise ArtifactIntegrityError(
                        f"Selected manifest profile mismatch for {artifact_id}"
                    )
                for raw_input_ref in manifest.inputs:
                    input_ref = _coerce_input_ref(raw_input_ref)
                    lock_ids[input_ref.artifact_id.hex] = input_ref.artifact_id

                signature_member = manifest_member.removesuffix(".manifest.json") + ".sig"
                signature_bytes: bytes | None = None
                if signature_member in artifact_members:
                    signature_source = staging_root / Path(*signature_member.split("/"))
                    if (
                        self._ownership_index._path_has_symlink_component(signature_source)
                        or signature_source.is_symlink()
                        or not signature_source.is_file()
                        or signature_source.stat().st_size > 1024 * 1024
                    ):
                        raise ArtifactIntegrityError("CAS import signature stage is unsafe")
                    signature_bytes = signature_source.read_bytes()
                    signature = DetachedSignature.model_validate_json(signature_bytes)
                    if (
                        signature.artifact_id != str(artifact_id)
                        or signature.statement.blob_sha256 != artifact_id.hex
                        or signature.statement.manifest_sha256
                        != hashlib.sha256(manifest_data).hexdigest()
                    ):
                        raise ArtifactIntegrityError(
                            f"Imported signature does not bind manifest view {artifact_id}"
                        )
                source_views.append(
                    {
                        "member": manifest_member,
                        "source": manifest_source,
                        "manifest": manifest,
                        "manifest_data": manifest_data,
                        "profile": profile_sha256,
                        "signature_data": signature_bytes,
                    }
                )
            source_by_artifact[artifact_id.hex] = {
                "artifact_id": artifact_id,
                "blob_source": blob_source,
                "blob_sha256": f"sha256:{blob_sha}",
                "source_views": source_views,
                "members": artifact_members,
            }

        published_views: dict[tuple[str, str | None], ArtifactRef] = {}
        with self._coordinator.artifact_leases(lock_ids.values(), exclusive=True) as leases:
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(
                    required=self._ownership_requires_scope
                )
            owner = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            if self._ownership_enforced:
                for source_info in source_by_artifact.values():
                    for source_view in source_info["source_views"]:
                        for raw_input_ref in source_view["manifest"].inputs:
                            input_ref = _coerce_input_ref(raw_input_ref)
                            input_id = input_ref.artifact_id
                            if owner is None:
                                self._require_blob_owner(
                                    input_id,
                                    operation=f"import input:{input_ref.role}",
                                )
                                self._require_manifest_view_owner(
                                    input_id,
                                    input_ref.manifest_profile_sha256,
                                    operation=f"import input manifest:{input_ref.role}",
                                )
                                continue

                            if self._ownership_index.has_any_tenant_claim(input_id):
                                self._ownership_index.require_blob_reader(
                                    input_id,
                                    tenant_id=owner["tenant_id"],
                                    cell_id=owner["cell_id"],
                                    operation=f"import input:{input_ref.role}",
                                )
                                if input_ref.manifest_profile_sha256 is None:
                                    self._ownership_index.require_owner(
                                        input_id,
                                        tenant_id=owner["tenant_id"],
                                        cell_id=owner["cell_id"],
                                        operation=f"import input manifest:{input_ref.role}",
                                    )
                                else:
                                    self._ownership_index.require_view_owner(
                                        input_id,
                                        input_ref.manifest_profile_sha256,
                                        tenant_id=owner["tenant_id"],
                                        cell_id=owner["cell_id"],
                                        operation=f"import input manifest:{input_ref.role}",
                                    )
                                continue

                            imported_input = source_by_artifact.get(input_id.hex)
                            if imported_input is None:
                                raise ArtifactOwnershipError(
                                    "Unclaimed import input "
                                    f"{input_id} is not part of the same import"
                                )
                            source_profiles = {
                                view["profile"] for view in imported_input["source_views"]
                            }
                            has_default_view = any(
                                view["member"].endswith(
                                    f"{input_id.hex}.manifest.json"
                                )
                                for view in imported_input["source_views"]
                            )
                            if input_ref.manifest_profile_sha256 is None:
                                input_is_in_import = has_default_view
                            else:
                                input_is_in_import = (
                                    input_ref.manifest_profile_sha256 in source_profiles
                                )
                            if not input_is_in_import:
                                raise ArtifactOwnershipError(
                                    f"Import does not carry the selected input view for {input_id}"
                                )

            for artifact_id in artifact_ids:
                self._require_unclaimed_target_if_unscoped(artifact_id, operation="import")
                source_info = source_by_artifact[artifact_id.hex]
                blob_path, default_manifest_path = self._paths(artifact_id)
                self._prepare_import_destination(blob_path, member=blob_path.name)
                if blob_path.exists() and _file_content_hash(blob_path) != artifact_id.hex:
                    raise ArtifactIntegrityError(f"Existing CAS blob conflicts for {artifact_id}")
                blob_needs_stage = not blob_path.exists()

                has_claims = (
                    self._ownership_enforced
                    and self._ownership_index.has_any_tenant_claim(artifact_id)
                )
                default_owned = bool(
                    owner is not None
                    and self._ownership_index.is_owned_by(
                        artifact_id,
                        tenant_id=owner["tenant_id"],
                        cell_id=owner["cell_id"],
                    )
                )
                default_existing_profile: str | None = None
                if default_manifest_path.exists():
                    self._prepare_import_destination(
                        default_manifest_path,
                        member=default_manifest_path.name,
                    )
                    existing_default = ArtifactManifest.model_validate_json(
                        default_manifest_path.read_bytes()
                    )
                    _validate_manifest_identity(artifact_id, existing_default)
                    default_existing_profile = self._manifests.profile_sha256(existing_default)

                desired_views: dict[str, dict[str, Any]] = {}
                desired_signatures: dict[str, dict[str, Any]] = {}
                for source_view in source_info["source_views"]:
                    profile_sha256 = source_view["profile"]
                    is_source_default = source_view["member"].endswith(
                        f"{artifact_id.hex}.manifest.json"
                    )
                    can_use_default = (
                        is_source_default
                        and (default_owned or not has_claims)
                        and (
                            default_existing_profile is None
                            or default_existing_profile == profile_sha256
                        )
                    )
                    view_targets = (
                        [default_manifest_path]
                        if can_use_default
                        else []
                    )
                    selected_view_path = self._layout.view_manifest_path(
                        artifact_id,
                        profile_sha256,
                    )
                    if not can_use_default or is_source_default:
                        view_targets.append(selected_view_path)

                    for target_path in view_targets:
                        selector = (
                            "default"
                            if target_path == default_manifest_path
                            else profile_sha256
                        )
                        self._prepare_import_destination(
                            target_path,
                            member=target_path.relative_to(self.root).as_posix(),
                        )
                        source_manifest = source_view["manifest"]
                        source_bytes = source_view["manifest_data"]
                        if target_path.exists():
                            manifest_data = target_path.read_bytes()
                            manifest = ArtifactManifest.model_validate_json(manifest_data)
                            _validate_manifest_identity(artifact_id, manifest)
                            if self._manifests.profile_sha256(manifest) != profile_sha256:
                                raise ArtifactIntegrityError(
                                    f"Existing manifest profile conflicts for {artifact_id}"
                                )
                        else:
                            manifest_data = source_bytes
                            manifest = source_manifest
                        digest = content_hash(manifest_data, prefix=True)
                        entry = {
                            "selector": selector,
                            "path": target_path,
                            "manifest": manifest,
                            "manifest_data": manifest_data,
                            "profile": profile_sha256,
                            "manifest_sha256": digest,
                            "needs_stage": not target_path.exists(),
                        }
                        previous = desired_views.get(selector)
                        if previous is not None and (
                            previous["manifest_sha256"] != digest
                            or previous["path"] != target_path
                        ):
                            raise ArtifactIntegrityError(
                                f"Conflicting imported manifest views for {artifact_id}"
                            )
                        desired_views[selector] = entry

                        signature_bytes = source_view["signature_data"]
                        if signature_bytes is None:
                            continue
                        if (
                            DetachedSignature.model_validate_json(signature_bytes)
                            .statement.manifest_sha256
                            != hashlib.sha256(manifest_data).hexdigest()
                        ):
                            raise ArtifactIntegrityError(
                                f"Imported signature does not bind selected view {artifact_id}"
                            )
                        signature_path = self._sig_path(
                            artifact_id,
                            None if selector == "default" else profile_sha256,
                        )
                        self._prepare_import_destination(
                            signature_path,
                            member=signature_path.relative_to(self.root).as_posix(),
                        )
                        if (
                            signature_path.exists()
                            and signature_path.read_bytes() != signature_bytes
                        ):
                            raise ArtifactIntegrityError(
                                f"Existing signature conflicts for {artifact_id}"
                            )
                        signature_entry = {
                            "selector": selector,
                            "path": signature_path,
                            "data": signature_bytes,
                            "sha256": content_hash(signature_bytes, prefix=True),
                            "needs_stage": not signature_path.exists(),
                        }
                        existing_signature = desired_signatures.get(selector)
                        if existing_signature is not None and (
                            existing_signature["sha256"] != signature_entry["sha256"]
                        ):
                            raise ArtifactIntegrityError(
                                f"Conflicting imported signatures for {artifact_id}"
                            )
                        desired_signatures[selector] = signature_entry

                if not desired_views:
                    raise ArtifactIntegrityError(
                        f"Import has no destination views for {artifact_id}"
                    )

                current_claims = self._ownership_index._transaction_claims_for(
                    artifact_id,
                    tenant_id=owner["tenant_id"] if owner is not None else None,
                    cell_id=owner["cell_id"] if owner is not None else None,
                    manifest_profile_sha256=next(
                        iter(entry["profile"] for entry in desired_views.values())
                    ),
                )
                default_claim = bool(
                    owner is not None
                    and ("default" in desired_views or current_claims["default_owner"])
                )
                blob_reader_claim = bool(
                    owner is not None
                    and (not default_claim or current_claims["blob_reader"])
                )
                profile_claims = sorted(
                    {
                        entry["profile"]
                        for entry in desired_views.values()
                    }
                ) if owner is not None else []
                missing_profile_claims = set()
                for profile in profile_claims:
                    profile_claim = self._ownership_index._transaction_claims_for(
                        artifact_id,
                        tenant_id=owner["tenant_id"] if owner is not None else None,
                        cell_id=owner["cell_id"] if owner is not None else None,
                        manifest_profile_sha256=profile,
                    )
                    if profile not in profile_claim["view_owners"]:
                        missing_profile_claims.add(profile)

                claims = {
                    "default_owner": default_claim,
                    "blob_reader": blob_reader_claim,
                    "view_owners": profile_claims,
                }
                affected_profiles = sorted(
                    profile
                    for profile, entry in (
                        (value["profile"], value) for value in desired_views.values()
                    )
                    if (
                        entry["needs_stage"]
                        or (entry["selector"] != "default" and profile in missing_profile_claims)
                    )
                )
                affected_profiles = list(dict.fromkeys(affected_profiles))
                ambient_affected = bool(
                    blob_needs_stage
                    or desired_views.get("default", {}).get("needs_stage", False)
                    or (default_claim and not current_claims["default_owner"])
                    or (blob_reader_claim and not current_claims["blob_reader"])
                )
                signature_specs = []
                affected_signature_profiles = []
                for selector, entry in sorted(desired_signatures.items()):
                    signature_specs.append(
                        {
                            "selector": selector,
                            "signature_sha256": entry["sha256"],
                            "signature_stage": None,
                        }
                    )
                    if entry["needs_stage"]:
                        affected_signature_profiles.append(selector)

                blob_member_sha = source_info["blob_sha256"]
                default_created_at = next(
                    iter(source_view["manifest"].created_at.isoformat()
                         for source_view in source_info["source_views"])
                )
                operation_id = uuid.uuid4().hex
                stage_names = {
                    selector: (
                        "manifest-default.stage"
                        if selector == "default"
                        else f"manifest-view-{selector.removeprefix('sha256:')}.stage"
                    )
                    for selector in desired_views
                }
                intent_views = [
                    {
                        "selector": selector,
                        "manifest_profile_sha256": entry["profile"],
                        "manifest_sha256": entry["manifest_sha256"],
                        "manifest_stage": (
                            self._transaction_stage_relative(operation_id, stage_names[selector])
                            if entry["needs_stage"]
                            else None
                        ),
                    }
                    for selector, entry in sorted(desired_views.items())
                ]
                for signature_spec in signature_specs:
                    selector = signature_spec["selector"]
                    if (
                        signature_spec["signature_stage"] is None
                        and desired_signatures[selector]["needs_stage"]
                    ):
                        stage_name = (
                            "signature-default.stage"
                            if selector == "default"
                            else f"signature-view-{selector.removeprefix('sha256:')}.stage"
                        )
                        signature_spec["signature_stage"] = self._transaction_stage_relative(
                            operation_id,
                            stage_name,
                        )
                affected = {
                    "ambient_artifact": ambient_affected,
                    "manifest_profiles": affected_profiles,
                    "signature_profiles": affected_signature_profiles,
                }
                if owner is None and self._ownership_index.has_any_tenant_claim(artifact_id):
                    raise ArtifactOwnershipError(
                        f"Artifact {artifact_id} import requires its current tenant owner"
                    )

                request_intent: dict[str, Any] = {
                    "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                    "status": "pending",
                    "mode": "import",
                    "operation_id": operation_id,
                    "artifact_id": str(artifact_id),
                    "owner": owner,
                    "blob_sha256": blob_member_sha,
                    "blob_stage": (
                        self._transaction_stage_relative(operation_id, "blob.stage")
                        if blob_needs_stage
                        else None
                    ),
                    "views": intent_views,
                    "claims": claims,
                    "affected": affected,
                    "manifest_created_at": default_created_at,
                    "signatures": signature_specs,
                    "request_sha256": "",
                }
                prior = self._ownership_index._read_transaction_intent(artifact_id)
                committed_prior = (
                    prior is not None
                    and self._ownership_index._committed_intent_matches_current_state(prior)
                )
                if committed_prior:
                    self._ownership_index.remove_transaction_intent(
                        artifact_id,
                        lease=leases[artifact_id.hex],
                    )
                    self._remove_transaction_stage(prior["operation_id"])
                    prior = None
                if prior is not None:
                    prior_views = {
                        spec["selector"]: spec for spec in prior["views"]
                    }
                    prior_signature_specs = {
                        spec["selector"]: spec
                        for spec in prior.get("signatures", [])
                    }
                    if (
                        prior["mode"] != "import"
                        or prior["owner"] != owner
                        or set(prior_views) != set(desired_views)
                        or set(prior_signature_specs) != set(desired_signatures)
                    ):
                        raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

                    retry_intent = dict(request_intent)
                    retry_intent["claims"] = prior["claims"]
                    retry_intent["affected"] = prior["affected"]
                    retry_intent["blob_stage"] = prior["blob_stage"]
                    retry_intent["views"] = [
                        {
                            "selector": selector,
                            "manifest_profile_sha256": entry["profile"],
                            "manifest_sha256": entry["manifest_sha256"],
                            "manifest_stage": prior_views[selector]["manifest_stage"],
                        }
                        for selector, entry in sorted(desired_views.items())
                    ]
                    retry_intent["signatures"] = [
                        {
                            "selector": selector,
                            "signature_sha256": entry["sha256"],
                            "signature_stage": prior_signature_specs[selector][
                                "signature_stage"
                            ],
                        }
                        for selector, entry in sorted(desired_signatures.items())
                    ]
                    retry_intent["request_sha256"] = (
                        self._ownership_index._transaction_request_digest(retry_intent)
                    )
                    if retry_intent["request_sha256"] != prior["request_sha256"]:
                        raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
                    intent = prior
                    operation_id = prior["operation_id"]
                    for selector, spec in prior_views.items():
                        desired = desired_views[selector]
                        if (
                            desired["manifest_sha256"] != spec["manifest_sha256"]
                            or desired["profile"] != spec["manifest_profile_sha256"]
                        ):
                            raise ArtifactTransactionPendingError(
                                artifact_id,
                                surface=f"manifest:{selector}",
                            )
                    for selector, spec in prior_signature_specs.items():
                        if desired_signatures[selector]["sha256"] != spec[
                            "signature_sha256"
                        ]:
                            raise ArtifactTransactionPendingError(
                                artifact_id,
                                surface=f"signature:{selector}",
                            )
                    signature_specs = list(prior_signature_specs.values())
                else:
                    request_intent["request_sha256"] = (
                        self._ownership_index._transaction_request_digest(request_intent)
                    )
                    intent = request_intent
                    if (
                        intent["blob_stage"] is None
                        and not any(view["manifest_stage"] for view in intent["views"])
                        and not any(
                            signature["signature_stage"]
                            for signature in intent["signatures"]
                        )
                        and not ambient_affected
                        and not affected_profiles
                    ):
                        for selector, entry in desired_views.items():
                            selected_profile = (
                                None if selector == "default" else entry["profile"]
                            )
                            reference = ArtifactRef(
                                artifact_id=artifact_id,
                                kind=entry["manifest"].kind,
                                media_type=entry["manifest"].media_type,
                                manifest_profile_sha256=selected_profile,
                            )
                            published_views[(str(artifact_id), selected_profile)] = reference
                        continue
                    self._ownership_index.write_transaction_intent(
                        artifact_id,
                        intent,
                        lease=leases[artifact_id.hex],
                    )

                signature_by_selector = {
                    signature["selector"]: signature for signature in intent.get("signatures", [])
                }
                blob_stage = None
                if intent["blob_stage"] is not None:
                    blob_stage = self._stage_import_source(
                        operation_id=operation_id,
                        recorded_path=intent["blob_stage"],
                        source_path=source_info["blob_source"],
                        final_path=blob_path,
                        expected_sha256=intent["blob_sha256"],
                        resume=prior is not None,
                    )
                self._publish_transaction_member(
                    blob_stage,
                    blob_path,
                    expected_sha256=intent["blob_sha256"],
                )
                for selector, entry in sorted(desired_views.items()):
                    spec = next(view for view in intent["views"] if view["selector"] == selector)
                    manifest_stage = None
                    if spec["manifest_stage"] is not None:
                        source_member = entry.get("source_member")
                        if source_member is None:
                            source_member = next(
                                source_view["member"]
                                for source_view in source_info["source_views"]
                                if source_view["profile"] == entry["profile"]
                            )
                        source_manifest_path = staging_root / Path(*source_member.split("/"))
                        manifest_stage = self._stage_import_source(
                            operation_id=operation_id,
                            recorded_path=spec["manifest_stage"],
                            source_path=source_manifest_path,
                            final_path=entry["path"],
                            expected_sha256=spec["manifest_sha256"],
                            resume=prior is not None,
                        )
                    self._publish_transaction_member(
                        manifest_stage,
                        entry["path"],
                        expected_sha256=spec["manifest_sha256"],
                    )
                for selector, spec in sorted(signature_by_selector.items()):
                    entry = desired_signatures[selector]
                    signature_stage = None
                    if spec["signature_stage"] is not None:
                        source_signature = next(
                            source_view
                            for source_view in source_info["source_views"]
                            if source_view["signature_data"] == entry["data"]
                        )
                        source_member = source_signature["member"].removesuffix(
                            ".manifest.json"
                        ) + ".sig"
                        signature_source = staging_root / Path(*source_member.split("/"))
                        signature_stage = self._stage_import_source(
                            operation_id=operation_id,
                            recorded_path=spec["signature_stage"],
                            source_path=signature_source,
                            final_path=entry["path"],
                            expected_sha256=spec["signature_sha256"],
                            resume=prior is not None,
                        )
                    self._publish_transaction_member(
                        signature_stage,
                        entry["path"],
                        expected_sha256=spec["signature_sha256"],
                    )

                self._record_transaction_claims(
                    artifact_id,
                    intent,
                    lease=leases[artifact_id.hex],
                )
                if not self._ownership_index._intent_completion_is_recomputed(intent):
                    raise ArtifactIntegrityError(
                        "artifact_import_owner_generation_or_bytes_unverified"
                    )
                committed = dict(intent)
                committed["status"] = "committed"
                self._ownership_index.write_transaction_intent(
                    artifact_id,
                    committed,
                    lease=leases[artifact_id.hex],
                )
                self._ownership_index.remove_transaction_intent(
                    artifact_id,
                    lease=leases[artifact_id.hex],
                )
                self._remove_transaction_stage(operation_id)
                for selector, entry in desired_views.items():
                    selected_profile = None if selector == "default" else entry["profile"]
                    reference = ArtifactRef(
                        artifact_id=artifact_id,
                        kind=entry["manifest"].kind,
                        media_type=entry["manifest"].media_type,
                        manifest_profile_sha256=selected_profile,
                    )
                    published_views[(str(artifact_id), selected_profile)] = reference

        return tuple(
            published_views[key]
            for key in sorted(published_views, key=lambda item: (item[0], item[1] or ""))
        )

    @staticmethod
    def _stream_file_digest(path: Path) -> tuple[str, int]:
        """Hash a regular file with bounded memory."""
        digest = hashlib.sha256()
        byte_size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                byte_size += len(chunk)
        return digest.hexdigest(), byte_size

    def _bulk_inventory_artifact_ids(self) -> tuple[ArtifactID, ...]:
        """Freeze the default-view IDs from one verified owner inventory."""
        snapshot = self.inventory_snapshot()
        if snapshot.verdict != "pass":
            raise ArtifactIntegrityError(
                "bulk_cas_inventory_not_established:"
                f"{snapshot.verdict}:{snapshot.reason or 'no_reason'}"
            )
        return tuple(
            sorted(
                {
                    entry.artifact_ref
                    for entry in snapshot.entries
                    if isinstance(entry.artifact_ref, ArtifactID)
                },
                key=lambda artifact_id: artifact_id.hex,
            )
        )

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """List default-view IDs from one verified, stable CAS inventory."""
        return list(self._bulk_inventory_artifact_ids())

    def _owner_generation_token(self) -> str:
        evidence = self._ownership_index.evidence()
        generation = evidence.get("ownership_index_generation_sha256")
        if isinstance(generation, str):
            return generation
        payload_sha = str(evidence.get("ownership_index_digest") or "")
        signature_sha = str(evidence.get("ownership_index_signature_digest") or "")
        token = hashlib.sha256(f"{payload_sha}:{signature_sha}".encode()).hexdigest()
        return f"sha256:{token}"

    def _capture_inventory_membership(
        self,
    ) -> tuple[
        tuple[str, ...],
        tuple[tuple[ArtifactID, str | None, Path, ArtifactManifest, bytes], ...],
        str,
    ]:
        """Capture member names, exact manifest views, and owner generation under root lock."""
        names: set[str] = set()
        walk_errors: list[OSError] = []

        def onerror(error: OSError) -> None:
            walk_errors.append(error)

        for directory, children, files in os.walk(
            self.base,
            topdown=True,
            followlinks=False,
            onerror=onerror,
        ):
            parent = Path(directory)
            if any((parent / child).is_symlink() for child in children):
                raise ArtifactIntegrityError("cas_inventory_symlink_directory")
            for filename in files:
                path = parent / filename
                if path.is_symlink() or not path.is_file():
                    raise ArtifactIntegrityError("cas_inventory_nonregular_member")
                names.add(path.relative_to(self.base).as_posix())
        if walk_errors:
            raise walk_errors[0]

        members: dict[tuple[str, str], Path] = {}
        member_pattern = re.compile(
            r"^(?P<artifact>[0-9a-f]{64})(?:\.view\.(?P<profile>[0-9a-f]{64}))?"
            r"\.(?P<kind>blob|manifest\.json|sig)$"
        )
        for name in names:
            relative = Path(name)
            if len(relative.parts) != 3:
                raise ArtifactIntegrityError("cas_inventory_member_path_invalid")
            shard_a, shard_b, filename = relative.parts
            match = member_pattern.fullmatch(filename)
            if (
                match is None
                or shard_a != match.group("artifact")[:2]
                or shard_b != match.group("artifact")[2:4]
            ):
                raise ArtifactIntegrityError("cas_inventory_member_name_invalid")
            selector = match.group("profile") or "default"
            kind = match.group("kind")
            key = (match.group("artifact"), f"{selector}:{kind}")
            if key in members:
                raise ArtifactIntegrityError("cas_inventory_duplicate_member")
            members[key] = self.base / relative

        artifacts = {artifact_hex for artifact_hex, _member_key in members}
        for artifact_hex in artifacts:
            if (artifact_hex, "default:blob") not in members:
                raise ArtifactIntegrityError("cas_inventory_blob_missing")
            if not any(
                key[0] == artifact_hex and key[1].endswith(":manifest.json")
                for key in members
            ):
                raise ArtifactIntegrityError("cas_inventory_manifest_missing")
            for member_key, _path in (
                (key[1], path) for key, path in members.items() if key[0] == artifact_hex
            ):
                selector, kind = member_key.split(":", 1)
                if kind == "sig" and (artifact_hex, f"{selector}:manifest.json") not in members:
                    raise ArtifactIntegrityError("cas_inventory_signature_view_missing")

        visible_views: list[tuple[ArtifactID, str | None, Path, ArtifactManifest, bytes]] = []
        tenant_id: str | None = None
        cell_id: str | None = None
        if self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)

        for (artifact_hex, selector_kind), manifest_path in sorted(members.items()):
            selector, kind = selector_kind.split(":", 1)
            if kind != "manifest.json":
                continue
            artifact_id = ArtifactID.from_sha256_hex(artifact_hex)
            profile_sha256 = None if selector == "default" else f"sha256:{selector}"
            if self._ownership_enforced:
                if tenant_id is None:
                    if self._ownership_index.has_any_tenant_claim(artifact_id):
                        continue
                elif profile_sha256 is None:
                    if not self._ownership_index.is_owned_by(
                        artifact_id,
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    ):
                        continue
                elif not self._ownership_index.is_view_owned_by(
                    artifact_id,
                    profile_sha256,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ):
                    continue
            manifest_bytes = manifest_path.read_bytes()
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(artifact_id, manifest)
            actual_profile = self._manifests.profile_sha256(manifest)
            if profile_sha256 is not None and actual_profile != profile_sha256:
                raise ArtifactIntegrityError("cas_inventory_manifest_profile_mismatch")
            visible_views.append(
                (artifact_id, profile_sha256, manifest_path, manifest, manifest_bytes)
            )

        return tuple(sorted(names)), tuple(visible_views), self._owner_generation_token()

    def inventory_snapshot(self) -> CASInventorySnapshot:
        """Verify a stable store-visible artifact/ref inventory in bounded memory.

        The snapshot covers cooperating local CAS blob, manifest, reference, and
        owner-generation state. Detached signature bytes and non-cooperating
        filesystem actors remain explicitly unresolved by construction.
        """
        inputs = (
            "canonical CAS root member names",
            "selected manifest bytes and profiles",
            "blob bytes streamed under artifact read leases",
            "signed ownership-index generation",
        )
        unresolved = (
            "detached signature contents",
            "direct filesystem writers outside the CAS lease protocol",
            "other tenant views hidden by the active tenant scope",
        )
        try:
            with self._coordinator.root_exclusive():
                names_before, views, generation_before = self._capture_inventory_membership()
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=f"inventory_capture_unavailable:{type(exc).__name__}",
            )

        entries: list[CASInventoryEntry] = []
        try:
            for artifact_id, profile_sha256, _manifest_path, manifest, manifest_bytes in views:
                ref: ArtifactID | ArtifactRef = artifact_id
                if profile_sha256 is not None:
                    ref = ArtifactRef(
                        artifact_id=artifact_id,
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        manifest_profile_sha256=profile_sha256,
                    )
                with self.open_member(ref, "blob") as blob_stream:
                    while blob_stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                        pass
                blob_receipt = blob_stream.receipt
                with self.open_member(ref, "manifest") as manifest_stream:
                    while manifest_stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                        pass
                manifest_receipt = manifest_stream.receipt
                if manifest_receipt.sha256 != hashlib.sha256(manifest_bytes).hexdigest():
                    raise ArtifactIntegrityError("cas_inventory_manifest_changed_during_scan")
                entries.append(
                    CASInventoryEntry(
                        artifact_ref=ref,
                        manifest=manifest,
                        blob_sha256="sha256:" + blob_receipt.sha256,
                        blob_byte_size=blob_receipt.byte_size,
                        manifest_sha256="sha256:" + manifest_receipt.sha256,
                        manifest_byte_size=manifest_receipt.byte_size,
                    )
                )
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError, ArtifactOwnershipError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=f"inventory_verify_unavailable:{type(exc).__name__}",
            )

        try:
            with self._coordinator.root_exclusive():
                names_after, _views_after, generation_after = self._capture_inventory_membership()
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=f"inventory_recheck_unavailable:{type(exc).__name__}",
            )
        if names_before != names_after or generation_before != generation_after:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_after,
                entries=tuple(entries),
                reason="inventory_changed_during_scan",
            )
        return CASInventorySnapshot(
            verdict="pass",
            inputs=inputs,
            unresolved_by_construction=unresolved,
            owner_generation_sha256=generation_after,
            entries=tuple(entries),
        )

    def _iter_artifact_ids_lazy(self) -> Iterator[ArtifactID]:
        """Compatibility iterator over a single verified inventory generation."""
        yield from self._bulk_inventory_artifact_ids()

    def export_subgraph(
        self,
        artifact_ids: Iterable[ArtifactID | ArtifactRef | str],
        target: Path,
        *,
        compress: bool = True,
        include_manifests: bool = True,
    ) -> ExportReport:
        """Export a CAS subgraph to a tarball or directory using the stable CAS layout."""
        artifact_ids = list(artifact_ids)
        for artifact_id in artifact_ids:
            aid, profile_sha256, _ref = _artifact_reference(artifact_id)
            if profile_sha256 is None:
                self._require_artifact_owner(aid, operation="export")
            else:
                self._require_blob_owner(aid, operation="export")
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation="export_manifest",
                )
        def member_name(request: ArtifactID | ArtifactRef, member: str) -> str:
            aid, profile_sha256, _ref = _artifact_reference(request)
            return self._member_name(aid, member, profile_sha256)

        return _export_subgraph(
            open_member=self.open_member,
            member_name=member_name,
            artifact_ids=artifact_ids,
            target=target,
            compress=compress,
            include_manifests=include_manifests,
        )

    def import_subgraph(
        self,
        source: Path,
        *,
        verify_integrity: bool = False,
    ) -> ImportReport:
        """Import a CAS export from a directory/tarball and optionally re-verify integrity."""
        return _import_subgraph(
            root=self.root,
            verify_artifact=self._verify_staged_artifact,
            publish_staged=self._publish_staged_import,
            source=source,
            verify_integrity=verify_integrity,
        )

    @staticmethod
    def _normalize_archive_path(path: Path) -> Path:
        return _normalize_archive_path(path)

    @staticmethod
    def _safe_member_path(name: str) -> object:
        return _safe_member_path(name)

    @staticmethod
    def _artifact_id_from_member(path: str) -> ArtifactID | None:
        return _artifact_id_from_member(path)

    def _read_verified_blob(
        self,
        artifact_id: ArtifactID,
        blob_path: Path,
        *,
        manifest_ref: ArtifactRef | None = None,
    ) -> bytes:
        return _read_verified_blob(
            artifact_id,
            blob_path,
            load_manifest=lambda selected_id: self.get_manifest(manifest_ref or selected_id),
            record_integrity_failure=self._record_integrity_failure,
        )

    @_transactional_read()
    def _load_verified_snapshot(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> _VerifiedArtifactSnapshot:
        """Load one owned, integrity-checked bytes/manifest snapshot."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        self._require_blob_owner(aid, operation="verify")
        self.get_manifest(artifact_id)
        blob, _default_manifest = self._paths(aid)
        manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
        snapshot = _load_verified_artifact_snapshot(
            aid,
            blob_path=blob,
            manifest_path=manifest_path,
            record_integrity_failure=self._record_integrity_failure,
        )
        manifest = ArtifactManifest.model_validate_json(snapshot.manifest_bytes)
        _validate_manifest_identity(aid, manifest)
        if profile_sha256 is not None and (
            self._manifests.profile_sha256(manifest) != profile_sha256
        ):
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        if ref is not None and (ref.kind != manifest.kind or ref.media_type != manifest.media_type):
            raise ArtifactIntegrityError(
                f"Artifact reference type does not match selected manifest for {aid}"
            )
        return snapshot
