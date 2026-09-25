"""Implement the filesystem CAS boundary for blobs, manifests, lineage, and signatures."""

from __future__ import annotations

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
    InputRef,
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


def _coerce_input_ref(value: object) -> InputRef:
    if isinstance(value, InputRef):
        return value
    if isinstance(value, dict):
        return InputRef.model_validate(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return InputRef.model_validate(model_dump(mode="python"))
    artifact_id = getattr(value, "artifact_id", None)
    role = getattr(value, "role", None)
    return InputRef.model_validate({"artifact_id": artifact_id, "role": role})


def _artifact_reference(
    value: ArtifactID | ArtifactRef | str,
) -> tuple[ArtifactID, str | None, ArtifactRef | None]:
    """Split a blob identifier or typed reference without discarding its view selector."""
    if isinstance(value, ArtifactRef):
        return value.artifact_id, value.manifest_profile_sha256, value
    if isinstance(value, str):
        return ArtifactID.model_validate(value), None, None
    return value, None, None


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

    def get_paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        """Return deterministic blob/manifest paths for external CAS tooling."""
        return self._paths(artifact_id)

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
                raise FileNotFoundError(f"Artifact not found: {artifact_id.hex}")

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
    ) -> tuple[bool, bool, str]:
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

        return blob_preexisted, default_view_created, profile_sha256

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        """Store raw bytes under their content hash and create the immutable manifest sidecar."""
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        self._require_input_owners(opts)
        blob, _manp = self._paths(aid)
        blob.parent.mkdir(parents=True, exist_ok=True)

        if not self._hpc_enabled or self._tracer is None:
            _deduplicated, default_view_created, profile_sha256 = (
                self._put_blob_and_manifest_once(data=data, opts=opts, aid=aid, sha=sha)
            )
            self._record_write_owner(aid, default_view_created=default_view_created)
            self._record_write_view_owner(aid, profile_sha256)
            ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=profile_sha256,
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
            deduplicated, default_view_created, profile_sha256 = self._put_blob_and_manifest_once(
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
            )
            self._record_write_owner(aid, default_view_created=default_view_created)
            self._record_write_view_owner(aid, profile_sha256)

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
                manifest_profile_sha256=profile_sha256,
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
        artifact_id: ArtifactID,
        staging_root: Path,
    ) -> VerificationReport:
        """Verify one staged pair while retaining this store's failure telemetry."""
        blob, manifest = self._paths(artifact_id)
        staged_blob = staging_root / blob.relative_to(self.root)
        staged_manifest = staging_root / manifest.relative_to(self.root)
        report = _verify_filesystem_artifact(
            artifact_id,
            blob_path=staged_blob,
            manifest_path=staged_manifest,
        )
        if not report.ok:
            self._record_integrity_failure(reason=report.error or "verification_failed")
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
    ) -> None:
        """Publish one verified import generation through store ownership/locks."""
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
        plans: list[dict[str, object]] = []
        new_artifacts: list[ArtifactID] = []

        def write_once_owned(path: Path, data: bytes, *, member: str) -> None:
            self._prepare_import_destination(path, member=member)
            won = self._files.write_once(path, data)
            if won:
                created.append((path, data))
                return
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise ArtifactIntegrityError(f"Concurrent CAS write conflicts with {member}")

        def rollback() -> None:
            for path, data in reversed(created):
                try:
                    if (
                        path.is_file()
                        and not path.is_symlink()
                        and path.read_bytes() == data
                    ):
                        path.unlink()
                except OSError:
                    continue

        with ExitStack() as stack:
            for lock in sorted(locks.values(), key=id):
                stack.enter_context(lock)

            for artifact_ref in sorted(artifact_refs):
                artifact_id = ArtifactID.model_validate(artifact_ref)
                artifact_members = staged_by_artifact[artifact_ref]
                blob_member = (
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.blob"
                )
                manifest_member = (
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.manifest.json"
                )
                signature_member = (
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.sig"
                )
                if not {blob_member, manifest_member}.issubset(artifact_members):
                    raise ArtifactIntegrityError(
                        f"Transfer is missing an immutable pair for {artifact_id}"
                    )

                staged_blob = staging_root / Path(*blob_member.split("/"))
                staged_manifest = staging_root / Path(*manifest_member.split("/"))
                staged_blob_data = staged_blob.read_bytes()
                staged_manifest_data = staged_manifest.read_bytes()
                staged_manifest_model = ArtifactManifest.model_validate_json(staged_manifest_data)
                _validate_manifest_identity(artifact_id, staged_manifest_model)
                _validate_read_integrity(
                    artifact_id,
                    staged_blob_data,
                    staged_manifest_model,
                )

                blob, manifest = self._paths(artifact_id)
                signature = self._sig_path(artifact_id)
                self._prepare_import_destination(blob, member=blob_member)
                self._prepare_import_destination(manifest, member=manifest_member)
                self._prepare_import_destination(signature, member=signature_member)
                blob_exists = blob.exists()
                manifest_exists = manifest.exists()
                if blob_exists != manifest_exists:
                    raise ArtifactIntegrityError(
                        f"Existing CAS generation is incomplete for {artifact_id}"
                    )

                existing_signature = signature.read_bytes() if signature.exists() else None
                staged_signature = (
                    staging_root / Path(*signature_member.split("/"))
                    if signature_member in artifact_members
                    else None
                )
                staged_signature_data = (
                    staged_signature.read_bytes() if staged_signature is not None else None
                )
                if (
                    existing_signature is not None
                    and staged_signature_data is not None
                    and existing_signature != staged_signature_data
                ):
                    raise ValueError(
                        f"Existing detached signature conflicts for {artifact_id}"
                    )

                if blob_exists:
                    self._require_artifact_owner(artifact_id, operation="import")
                    existing_data = blob.read_bytes()
                    existing_manifest = self._manifests.read(manifest)
                    _validate_read_integrity(artifact_id, existing_data, existing_manifest)
                    if self._import_manifest_profile(existing_manifest) != (
                        self._import_manifest_profile(staged_manifest_model)
                    ):
                        raise ValueError(
                            f"Existing artifact manifest profile conflict for {artifact_id}"
                        )
                elif self._ownership_enforced:
                    self._resolve_owner(required=self._ownership_requires_scope)

                plans.append(
                    {
                        "artifact_id": artifact_id,
                        "blob": blob,
                        "manifest": manifest,
                        "signature": signature,
                        "blob_data": staged_blob_data,
                        "manifest_data": staged_manifest_data,
                        "signature_data": staged_signature_data,
                        "existing": blob_exists,
                    }
                )
                if not blob_exists:
                    new_artifacts.append(artifact_id)

            try:
                for plan in plans:
                    artifact_id = plan["artifact_id"]
                    if not isinstance(artifact_id, ArtifactID):
                        raise ArtifactIntegrityError("Invalid staged artifact identity")
                    blob = plan["blob"]
                    manifest = plan["manifest"]
                    signature = plan["signature"]
                    if not isinstance(blob, Path) or not isinstance(manifest, Path):
                        raise ArtifactIntegrityError("Invalid staged artifact paths")
                    if not isinstance(signature, Path):
                        raise ArtifactIntegrityError("Invalid staged signature path")
                    blob_data = plan["blob_data"]
                    manifest_data = plan["manifest_data"]
                    signature_data = plan["signature_data"]
                    if not isinstance(blob_data, bytes) or not isinstance(manifest_data, bytes):
                        raise ArtifactIntegrityError("Invalid staged artifact bytes")
                    if not plan["existing"]:
                        write_once_owned(
                            blob,
                            blob_data,
                            member=(
                                f"artifacts/sha256/{artifact_id.hex[:2]}"
                                f"/{artifact_id.hex[2:4]}/{artifact_id.hex}.blob"
                            ),
                        )
                        write_once_owned(
                            manifest,
                            manifest_data,
                            member=(
                                f"artifacts/sha256/{artifact_id.hex[:2]}"
                                f"/{artifact_id.hex[2:4]}/{artifact_id.hex}.manifest.json"
                            ),
                        )
                    if isinstance(signature_data, bytes) and not signature.exists():
                        write_once_owned(
                            signature,
                            signature_data,
                            member=(
                                f"artifacts/sha256/{artifact_id.hex[:2]}"
                                f"/{artifact_id.hex[2:4]}/{artifact_id.hex}.sig"
                            ),
                        )
                for artifact_id in new_artifacts:
                    self._record_write_owner(artifact_id)
            except Exception:
                rollback()
                raise

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
        artifact_ids: Iterable[ArtifactID],
        target: Path,
        *,
        compress: bool = True,
        include_manifests: bool = True,
    ) -> ExportReport:
        """Export a CAS subgraph to a tarball or directory using the stable CAS layout."""
        artifact_ids = list(artifact_ids)
        for artifact_id in artifact_ids:
            self._require_artifact_owner(artifact_id, operation="export")
        return _export_subgraph(
            root=self.root,
            get_paths=self._paths,
            get_sig_path=self._sig_path,
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
