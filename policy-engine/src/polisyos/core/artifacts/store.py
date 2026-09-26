"""Implement the filesystem CAS boundary for blobs, manifests, lineage, and signatures."""

from __future__ import annotations

import hashlib
import re
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ..canon import content_hash
from ..canon.canon_json import CanonSpec, to_canonical_bytes
from ..observability import get_metrics, get_tracer
from ..observability.config import is_hpc_observability_enabled
from ._atomic_write import AtomicFileWriter as _AtomicFileWriter
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
    get_signature as _get_signature,
)
from ._signature_ops import (
    has_signature as _has_signature,
)
from ._signature_ops import (
    put_signature as _put_signature,
)
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
from .ownership import ArtifactOwnershipError, ArtifactOwnershipIndex
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
    from collections.abc import Iterable, Iterator

    from ..observability import MetricsRegistry, PolicyOSTracer
    from .backends.config import ArtifactStoreConfig


PutOptions = ArtifactWriteOptions

_ARTIFACT_LOCK_STRIPES = 64


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
        self.root = root
        self._layout = _CASPathLayout(root)
        self.base = self._layout.base
        self.base.mkdir(parents=True, exist_ok=True)
        self._files = _AtomicFileWriter()
        self._manifests = _ManifestLifecycle(self._files)
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
        # Fixed striping bounds resident lock state without ever evicting a
        # lock that may still have holders or waiters.  Collisions serialize
        # unrelated artifact IDs, but preserve the first-writer invariant.
        self._artifact_locks = tuple(
            threading.Lock() for _ in range(_ARTIFACT_LOCK_STRIPES)
        )
        self._artifact_locks_guard = threading.Lock()
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        self._ownership_enforced = (
            tenant_id is not None if ownership_enforced is None else bool(ownership_enforced)
        )
        self._ownership_requires_scope = bool(ownership_requires_scope)
        self._ownership_index = ownership_index or ArtifactOwnershipIndex(root)

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        return self._layout.paths(artifact_id)

    def get_paths(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> tuple[Path, Path]:
        """Return deterministic blob and selected-manifest paths for CAS tooling."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        blob, _default_manifest = self._paths(aid)
        return blob, self._manifest_path_for_ref(aid, profile_sha256)

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
        self._ownership_index.record_owner(
            artifact_id,
            tenant_id=owner_tenant,
            cell_id=owner_cell,
            writer=writer,
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

    def _signature_path_for_ref(self, artifact_id: ArtifactID | ArtifactRef | str) -> Path:
        """Return the signature sidecar selected by a typed or historical ref."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        return self._sig_path(aid, profile_sha256)

    def _artifact_lock(self, artifact_id: ArtifactID) -> threading.Lock:
        with self._artifact_locks_guard:
            # ArtifactID is a validated SHA-256 digest, so using its complete
            # integer value gives a stable in-process stripe selection without
            # relying on Python's randomized string hash.
            stripe = int(artifact_id.hex, 16) % _ARTIFACT_LOCK_STRIPES
            return self._artifact_locks[stripe]

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
            return
        self._ownership_index.require_view_owner(
            artifact_id,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_default_manifest_access(
        self,
        artifact_id: ArtifactID,
        manifest: ArtifactManifest,
        *,
        operation: str,
    ) -> None:
        try:
            self._require_artifact_owner(artifact_id, operation=operation)
            return
        except ArtifactOwnershipError as legacy_error:
            if not self._ownership_enforced:
                raise
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            if tenant_id is None:
                raise legacy_error
            profile_sha256 = self._manifests.profile_sha256(manifest)
            try:
                self._ownership_index.require_view_owner(
                    artifact_id,
                    profile_sha256,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    operation=operation,
                )
            except ArtifactOwnershipError:
                raise legacy_error from None

    def _record_write_owner(
        self,
        artifact_id: ArtifactID,
        *,
        default_view_created: bool,
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
            )
        else:
            self._ownership_index.record_blob_reader(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                writer="FileSystemCAS",
            )

    def _record_write_view_owner(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str,
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

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether the blob and selected manifest view exist."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        blob, _ = self._paths(aid)
        manifest = self._manifest_path_for_ref(aid, profile_sha256)
        exists = blob.exists() and manifest.exists()
        if exists and self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            if tenant_id is not None:
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
        elif ref is None and exists is False and blob.exists() and manifest.exists():
            try:
                self.get_manifest(aid)
                exists = True
            except (FileNotFoundError, ValueError, ArtifactOwnershipError):
                pass
        if self._hpc_enabled and self._metrics:
            if exists and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "existence_check"})
            elif not exists and self._metrics.artifact_cache_misses_total:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "existence_check"})
        return exists

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

        for input_ref in manifest.inputs:
            self._require_blob_owner(
                input_ref.artifact_id,
                operation=f"cache input:{input_ref.role}",
            )
            self._require_manifest_view_owner(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
                operation=f"cache input manifest:{input_ref.role}",
            )

        if signature_bytes is not None:
            signature = DetachedSignature.model_validate_json(signature_bytes)
            if signature.artifact_id != str(aid):
                raise ArtifactIntegrityError(f"Signature artifact ID mismatch for {aid}")
            if signature.statement.blob_sha256 != aid.hex:
                raise ArtifactIntegrityError(f"Signature blob digest mismatch for {aid}")
            if signature.statement.manifest_sha256 != hashlib.sha256(manifest_bytes).hexdigest():
                raise ArtifactIntegrityError(f"Signature manifest digest mismatch for {aid}")

        blob_path, default_manifest_path = self._paths(aid)
        view_manifest_path = self._layout.view_manifest_path(aid, profile_sha256)
        with self._artifact_lock(aid):
            self._prepare_import_destination(
                blob_path,
                member=blob_path.relative_to(self.root).as_posix(),
            )
            if blob_path.exists() and _file_content_hash(blob_path) != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")

            default_manifest_bytes = (
                default_manifest_path.read_bytes() if default_manifest_path.exists() else None
            )
            if default_manifest_bytes is not None:
                default_manifest = ArtifactManifest.model_validate_json(default_manifest_bytes)
                _validate_manifest_identity(aid, default_manifest)
                _validate_read_integrity(aid, data, default_manifest)

            write_default = requested_profile is None and (
                default_manifest_bytes is None or default_manifest_bytes == manifest_bytes
            )
            target_manifest_path = default_manifest_path if write_default else view_manifest_path
            manifest_paths = [target_manifest_path]
            if write_default and view_manifest_path != default_manifest_path:
                manifest_paths.append(view_manifest_path)

            signature_paths = [
                self._sig_path(aid, None if write_default else profile_sha256)
            ]
            if write_default:
                signature_paths.append(self._sig_path(aid, profile_sha256))

            for path in (*manifest_paths, *signature_paths):
                self._prepare_import_destination(
                    path,
                    member=path.relative_to(self.root).as_posix(),
                )
            for path in manifest_paths:
                if path.exists() and path.read_bytes() != manifest_bytes:
                    raise ArtifactIntegrityError(
                        f"Exact manifest bytes conflict for selected view {aid}"
                    )
            if signature_bytes is not None:
                for path in signature_paths:
                    if path.exists() and path.read_bytes() != signature_bytes:
                        raise ArtifactIntegrityError(
                            f"Exact signature bytes conflict for selected view {aid}"
                        )

            if not blob_path.exists():
                self._files.write_once(blob_path, data)
            if _file_content_hash(blob_path) != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")
            for path in manifest_paths:
                self._files.write_once(path, manifest_bytes)
                if path.read_bytes() != manifest_bytes:
                    raise ArtifactIntegrityError(
                        f"Exact manifest bytes conflict for selected view {aid}"
                    )
            if signature_bytes is not None:
                for path in signature_paths:
                    self._files.write_once(path, signature_bytes)
                    if path.read_bytes() != signature_bytes:
                        raise ArtifactIntegrityError(
                            f"Exact signature bytes conflict for selected view {aid}"
                        )

            default_view_created = write_default and default_manifest_bytes is None
            self._record_write_owner(aid, default_view_created=default_view_created)
            self._record_write_view_owner(aid, profile_sha256)

        return ArtifactRef(
            artifact_id=aid,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=None if write_default else profile_sha256,
        )

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
            else:
                self._require_default_manifest_access(
                    aid,
                    manifest,
                    operation="read_manifest",
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

    def get_manifest_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Return raw manifest bytes for signature verification/export paths."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        self.get_manifest(artifact_id)
        manp = self._manifest_path_for_ref(aid, profile_sha256)
        return manp.read_bytes()

    def put_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        signature: DetachedSignature,
    ) -> Path:
        """Write a detached signature sidecar after validating the artifact binding.

        Raises:
            ValueError: If `signature.artifact_id` does not match `artifact_id`.
            OSError: If the sidecar cannot be written atomically.
        """
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        self.get_manifest(artifact_id)
        return _put_signature(
            artifact_id=aid,
            signature=signature,
            sig_path_for_artifact=lambda selected_id: self._sig_path(selected_id, profile_sha256),
            atomic_write=self._atomic_write,
        )

    def get_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> DetachedSignature | None:
        """Load a detached signature sidecar or return `None` when unsigned."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        self.get_manifest(artifact_id)
        return _get_signature(
            artifact_id=aid,
            sig_path_for_artifact=lambda selected_id: self._sig_path(selected_id, profile_sha256),
        )

    def get_signature_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        """Return the exact detached-signature bytes for the selected manifest view."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        self.get_manifest(artifact_id)
        path = self._sig_path(aid, profile_sha256)
        if not path.is_file():
            raise FileNotFoundError(f"Signature not found for artifact {aid}")
        return path.read_bytes()

    def has_signature(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether a detached signature sidecar exists for `artifact_id`."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        self.get_manifest(artifact_id)
        return _has_signature(
            artifact_id=aid,
            sig_path_for_artifact=lambda selected_id: self._sig_path(selected_id, profile_sha256),
        )

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

    def verify_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        """Verify content integrity and detached signature trust/revocation/identity state."""
        if isinstance(artifact_id, str):
            try:
                artifact_id = ArtifactID.model_validate(artifact_id)
            except ValidationError:
                return SignatureVerificationResult(
                    status=SignatureVerificationStatus.ERROR,
                    artifact_id=artifact_id,
                    message="Malformed artifact ID",
                )
        aid, _profile_sha256, ref = _artifact_reference(artifact_id)
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
        ids = artifact_ids if artifact_ids is not None else self._iter_artifact_ids_lazy()
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
        ids = artifact_ids if artifact_ids is not None else self._iter_artifact_ids_lazy()
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

    def _put_blob_and_manifest_once(
        self,
        *,
        data: bytes,
        opts: PutOptions,
        aid: ArtifactID,
        sha: str,
    ) -> tuple[bool, str | None]:
        """Persist one blob and its default plus exact typed-view manifests."""
        blob, default_manifest_path = self._paths(aid)
        with self._artifact_lock(aid):
            blob_preexisted = blob.exists()
            if not blob_preexisted:
                self._files.write_once(blob, data)
            existing_data = blob.read_bytes()
            actual_sha = content_hash(existing_data)
            if actual_sha != sha:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}: {actual_sha}")

            manifest = self._manifests.build(
                artifact_id=aid,
                data=data,
                sha=sha,
                opts=opts,
            )
            manifest_bytes = self._manifests.to_bytes(manifest)
            profile_sha256 = self._manifests.profile_sha256(manifest)
            default_view_created = self._files.write_once(
                default_manifest_path,
                manifest_bytes,
            )
            default_manifest = self._manifests.read(default_manifest_path)
            _validate_manifest_identity(aid, default_manifest)
            _validate_read_integrity(aid, existing_data, default_manifest)
            default_profile_sha256 = self._manifests.profile_sha256(default_manifest)

            view_path = self._layout.view_manifest_path(aid, profile_sha256)
            if not self._files.write_once(view_path, manifest_bytes):
                existing_view = self._manifests.read(view_path)
                _validate_manifest_identity(aid, existing_view)
                _validate_read_integrity(aid, existing_data, existing_view)
                if self._manifests.profile_projection(existing_view) != (
                    self._manifests.profile_projection(manifest)
                ):
                    raise ArtifactIntegrityError(
                        f"Manifest profile digest collision for {aid}"
                    )

            # Record the exact view while still holding the per-blob lock. A second
            # same-tenant writer must observe the first writer's default-view owner
            # before deciding whether its reference can remain selector-free.
            self._record_write_owner(aid, default_view_created=default_view_created)
            self._record_write_view_owner(aid, profile_sha256)

        ref_profile_sha256 = (
            profile_sha256 if profile_sha256 != default_profile_sha256 else None
        )
        if ref_profile_sha256 is None and not default_view_created and self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            if tenant_id is not None and not self._ownership_index.is_owned_by(
                aid,
                tenant_id=tenant_id,
                cell_id=cell_id,
            ):
                # A selector-free ref resolves through default-view ownership. Keep a typed
                # selector when this tenant can read only its separately admitted view.
                ref_profile_sha256 = profile_sha256
        return blob_preexisted, ref_profile_sha256

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        """Store raw bytes under their content hash and create the immutable manifest sidecar."""
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        self._require_input_owners(opts)
        blob, _manp = self._paths(aid)
        blob.parent.mkdir(parents=True, exist_ok=True)

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
        report = _verify_filesystem_artifact(
            aid,
            blob_path=staged_blob,
            manifest_path=staged_manifest,
        )
        if not report.ok:
            self._record_integrity_failure(reason=report.error or "verification_failed")
        if report.ok and ref is not None:
            try:
                manifest_model = self._manifests.read(staged_manifest)
                if self._manifests.profile_sha256(manifest_model) != profile_sha256:
                    raise ArtifactIntegrityError(
                        f"Selected manifest profile mismatch for {aid}"
                    )
                if ref.kind != manifest_model.kind or ref.media_type != manifest_model.media_type:
                    raise ArtifactIntegrityError(
                        f"Artifact reference type does not match selected manifest for {aid}"
                    )
            except (OSError, ValueError) as exc:
                return report.model_copy(update={"ok": False, "error": str(exc)})
        return report

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
                current.mkdir()
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

    def _publish_staged_import(
        self,
        staging_root: Path,
        members: set[str],
        artifact_refs: set[str],
    ) -> tuple[ArtifactRef, ...]:
        """Publish verified default and typed views through store ownership/locks."""
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

        locks: dict[int, threading.Lock] = {}
        for artifact_ref in sorted(artifact_refs):
            lock = self._artifact_lock(ArtifactID.model_validate(artifact_ref))
            locks[id(lock)] = lock

        created: list[tuple[Path, bytes]] = []
        writes: dict[Path, tuple[bytes, str]] = {}
        view_owners: dict[str, set[str]] = {}
        default_view_created: set[str] = set()
        published_views: dict[tuple[str, str | None], ArtifactRef] = {}

        def add_write(path: Path, data: bytes, *, member: str) -> None:
            previous = writes.get(path)
            if previous is not None and previous[0] != data:
                raise ArtifactIntegrityError(
                    f"Transfer contains conflicting immutable views for {member}"
                )
            writes[path] = (data, member)

        def rollback() -> None:
            for path, data in reversed(created):
                try:
                    if path.is_file() and not path.is_symlink() and path.read_bytes() == data:
                        path.unlink()
                except OSError:
                    continue

        with ExitStack() as stack:
            for lock in sorted(locks.values(), key=id):
                stack.enter_context(lock)

            for artifact_ref in sorted(artifact_refs):
                artifact_id = ArtifactID.model_validate(artifact_ref)
                artifact_members = staged_by_artifact[artifact_ref]
                prefix = (
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}"
                )
                blob_member = f"{prefix}.blob"
                if blob_member not in artifact_members:
                    raise ArtifactIntegrityError(
                        f"Transfer is missing the immutable blob for {artifact_id}"
                    )
                manifest_members = sorted(
                    member for member in artifact_members if member.endswith(".manifest.json")
                )
                if not manifest_members:
                    raise ArtifactIntegrityError(
                        f"Transfer is missing every manifest view for {artifact_id}"
                    )

                staged_blob = staging_root / Path(*blob_member.split("/"))
                staged_blob_data = staged_blob.read_bytes()
                if content_hash(staged_blob_data) != artifact_id.hex:
                    raise ArtifactIntegrityError(
                        f"Staged blob content does not match its identity: {artifact_id}"
                    )

                blob, default_manifest_path = self._paths(artifact_id)
                self._prepare_import_destination(blob, member=blob_member)
                if blob.exists():
                    persisted_blob_data = blob.read_bytes()
                    if persisted_blob_data != staged_blob_data:
                        raise ArtifactIntegrityError(
                            f"Existing CAS blob conflicts with {blob_member}"
                        )
                else:
                    persisted_blob_data = staged_blob_data
                    add_write(blob, staged_blob_data, member=blob_member)

                source_views: list[dict[str, object]] = []
                for manifest_member in manifest_members:
                    staged_manifest = staging_root / Path(*manifest_member.split("/"))
                    manifest_data = staged_manifest.read_bytes()
                    manifest = ArtifactManifest.model_validate_json(manifest_data)
                    _validate_manifest_identity(artifact_id, manifest)
                    _validate_read_integrity(artifact_id, persisted_blob_data, manifest)
                    profile_sha256 = self._manifests.profile_sha256(manifest)
                    encoded_profile = _member_profile_sha256(manifest_member)
                    if encoded_profile is not None and encoded_profile != profile_sha256:
                        raise ArtifactIntegrityError(
                            f"Selected manifest profile mismatch for {artifact_id}"
                        )
                    if self._ownership_enforced:
                        tenant_id, cell_id = self._resolve_owner(
                            required=self._ownership_requires_scope
                        )
                        tenant_context = manifest.tenant_context
                        if tenant_id is not None and tenant_context is not None and (
                            tenant_context.tenant_id != tenant_id
                            or (tenant_context.cell_id or None) != (cell_id or None)
                        ):
                            raise ArtifactOwnershipError(
                                f"Manifest view for {artifact_id} is bound to a different tenant"
                            )

                    source_sig_member = manifest_member.removesuffix(".manifest.json") + ".sig"
                    signature_data = None
                    if source_sig_member in artifact_members:
                        signature_data = (
                            staging_root / Path(*source_sig_member.split("/"))
                        ).read_bytes()
                    source_views.append(
                        {
                            "member": manifest_member,
                            "manifest": manifest,
                            "manifest_data": manifest_data,
                            "profile": profile_sha256,
                            "signature_data": signature_data,
                        }
                    )

                desired_views: dict[Path, dict[str, object]] = {}
                for source_view in source_views:
                    manifest = source_view["manifest"]
                    manifest_data = source_view["manifest_data"]
                    profile_sha256 = source_view["profile"]
                    member = source_view["member"]
                    signature_data = source_view["signature_data"]
                    if not isinstance(manifest, ArtifactManifest):
                        raise ArtifactIntegrityError("Invalid staged manifest model")
                    if not isinstance(manifest_data, bytes) or not isinstance(profile_sha256, str):
                        raise ArtifactIntegrityError("Invalid staged manifest view")
                    if not isinstance(member, str):
                        raise ArtifactIntegrityError("Invalid staged manifest member")
                    if member == f"{prefix}.manifest.json":
                        if default_manifest_path.exists():
                            existing_default = self._manifests.read(default_manifest_path)
                            _validate_manifest_identity(artifact_id, existing_default)
                            _validate_read_integrity(
                                artifact_id,
                                persisted_blob_data,
                                existing_default,
                            )
                            if self._manifests.profile_sha256(existing_default) == profile_sha256:
                                destination = default_manifest_path
                            else:
                                destination = self._layout.view_manifest_path(
                                    artifact_id,
                                    profile_sha256,
                                )
                        else:
                            destination = default_manifest_path
                    else:
                        destination = self._layout.view_manifest_path(
                            artifact_id,
                            profile_sha256,
                        )

                    destinations = [destination]
                    # Current writers return typed refs even for the first view. Preserve that
                    # ref when importing a legacy ID-only export by materializing an exact-byte
                    # selector sidecar alongside the historic default path.
                    if member == f"{prefix}.manifest.json":
                        destinations.append(
                            self._layout.view_manifest_path(artifact_id, profile_sha256)
                        )

                    for destination_path in destinations:
                        if destination_path.exists():
                            existing_manifest = self._manifests.read(destination_path)
                            _validate_manifest_identity(artifact_id, existing_manifest)
                            _validate_read_integrity(
                                artifact_id,
                                persisted_blob_data,
                                existing_manifest,
                            )
                            existing_profile = self._manifests.profile_sha256(existing_manifest)
                            if existing_profile != profile_sha256:
                                raise ArtifactIntegrityError(
                                    f"Existing manifest profile conflicts for {artifact_id}"
                                )
                            canonical_data = destination_path.read_bytes()
                        else:
                            canonical_data = manifest_data

                        view_entry = desired_views.get(destination_path)
                        if view_entry is not None and view_entry["manifest_data"] != canonical_data:
                            raise ArtifactIntegrityError(
                                f"Transfer contains conflicting immutable views for {artifact_id}"
                            )
                        if destination_path not in desired_views:
                            desired_views[destination_path] = {
                                "manifest_data": canonical_data,
                                "profile": profile_sha256,
                                "signature_data": signature_data,
                                "source_member": member,
                            }
                        elif signature_data is not None:
                            previous_signature = desired_views[destination_path]["signature_data"]
                            if previous_signature not in (None, signature_data):
                                raise ValueError(
                                    f"Conflicting detached signatures for {artifact_id}"
                                )
                            desired_views[destination_path]["signature_data"] = signature_data

                for destination_path, view in desired_views.items():
                    profile_sha256 = view["profile"]
                    manifest_data = view["manifest_data"]
                    signature_data = view["signature_data"]
                    source_member = view["source_member"]
                    if not isinstance(profile_sha256, str) or not isinstance(manifest_data, bytes):
                        raise ArtifactIntegrityError("Invalid immutable view write plan")
                    if not isinstance(source_member, str):
                        raise ArtifactIntegrityError("Invalid immutable view member")
                    is_default_destination = destination_path == default_manifest_path
                    persisted_manifest = ArtifactManifest.model_validate_json(manifest_data)
                    selector = None if is_default_destination else profile_sha256
                    imported_ref = ArtifactRef(
                        artifact_id=artifact_id,
                        kind=persisted_manifest.kind,
                        media_type=persisted_manifest.media_type,
                        manifest_profile_sha256=selector,
                    )
                    published_views[(str(artifact_id), selector)] = imported_ref
                    signature_path = (
                        self._sig_path(artifact_id)
                        if is_default_destination
                        else self._layout.view_sig_path(artifact_id, profile_sha256)
                    )
                    relative_manifest = destination_path.relative_to(self.root).as_posix()
                    relative_signature = signature_path.relative_to(self.root).as_posix()
                    self._prepare_import_destination(
                        destination_path,
                        member=relative_manifest,
                    )
                    self._prepare_import_destination(
                        signature_path,
                        member=relative_signature,
                    )
                    if destination_path.exists():
                        if self._ownership_enforced:
                            if is_default_destination:
                                self._require_artifact_owner(artifact_id, operation="import")
                            else:
                                self._require_blob_owner(artifact_id, operation="import")
                                self._require_manifest_view_owner(
                                    artifact_id,
                                    profile_sha256,
                                    operation="import_manifest",
                                )
                    else:
                        add_write(
                            destination_path,
                            manifest_data,
                            member=relative_manifest,
                        )
                        if is_default_destination:
                            default_view_created.add(str(artifact_id))
                        view_owners.setdefault(str(artifact_id), set()).add(profile_sha256)

                    if signature_data is not None:
                        if not isinstance(signature_data, bytes):
                            raise ArtifactIntegrityError("Invalid staged signature bytes")
                        signature = DetachedSignature.model_validate_json(signature_data)
                        expected_manifest_digest = hashlib.sha256(manifest_data).hexdigest()
                        if signature.statement.manifest_sha256 != expected_manifest_digest:
                            raise ValueError(
                                f"Detached signature does not bind the persisted manifest view "
                                f"for {artifact_id}"
                            )
                        if signature_path.exists():
                            if signature_path.read_bytes() != signature_data:
                                raise ValueError(
                                    f"Existing detached signature conflicts for {artifact_id}"
                                )
                        else:
                            add_write(
                                signature_path,
                                signature_data,
                                member=relative_signature,
                            )

            try:
                for path, (data, member) in sorted(
                    writes.items(),
                    key=lambda item: (item[0].as_posix(), item[1][1]),
                ):
                    self._prepare_import_destination(path, member=member)
                    won = self._files.write_once(path, data)
                    if won:
                        created.append((path, data))
                    elif path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                        raise ArtifactIntegrityError(
                            f"Concurrent CAS write conflicts with {member}"
                        )
                for artifact_ref in sorted(artifact_refs):
                    artifact_id = ArtifactID.model_validate(artifact_ref)
                    self._record_write_owner(
                        artifact_id,
                        default_view_created=str(artifact_id) in default_view_created,
                    )
                    for profile_sha256 in sorted(view_owners.get(str(artifact_id), set())):
                        self._record_write_view_owner(artifact_id, profile_sha256)
            except Exception:
                rollback()
                raise
        return tuple(
            published_views[key]
            for key in sorted(
                published_views,
                key=lambda item: (item[0], item[1] or ""),
            )
        )

    def _atomic_write(self, path: Path, data: bytes) -> None:
        self._files.write_atomic(path, data)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """List all artifact IDs that have manifest sidecars under this CAS root."""
        return sorted(self._iter_artifact_ids_lazy(), key=lambda artifact_id: artifact_id.hex)

    def _iter_artifact_ids_lazy(self) -> Iterator[ArtifactID]:
        """Yield owned manifest IDs lazily for bounded batch operations."""
        for manifest_path in self.base.rglob("*.manifest.json"):
            name = manifest_path.name
            if not name.endswith(".manifest.json"):
                continue
            hex64 = name[: -len(".manifest.json")]
            if not re.fullmatch(r"[0-9a-f]{64}", hex64):
                continue
            artifact_id = ArtifactID.from_sha256_hex(hex64)
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(
                    required=self._ownership_requires_scope
                )
                if tenant_id is not None and not self._ownership_index.is_owned_by(
                    artifact_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ):
                    continue
            yield artifact_id

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
        return _export_subgraph(
            root=self.root,
            get_paths=self.get_paths,
            get_sig_path=self._signature_path_for_ref,
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
