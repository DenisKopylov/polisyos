"""Implement the filesystem CAS boundary for blobs, manifests, lineage, and signatures."""
from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING

from ..canon import content_hash
from ..canon.canon_json import CanonSpec, to_canonical_bytes
from ..observability import get_metrics, get_tracer
from ..observability.config import is_hpc_observability_enabled
from ._atomic_write import AtomicFileWriter as _AtomicFileWriter
from ._integrity_ops import (
    ArtifactIntegrityError,
    VerificationReport as VerificationReport,
)
from ._integrity_ops import (
    read_verified_blob as _read_verified_blob,
)
from ._integrity_ops import (
    validate_manifest_identity as _validate_manifest_identity,
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
)
from .signing import (
    BulkSigningReport,
    BulkVerificationReport,
    DetachedSignature,
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
    SigningConfig,
    SigningError,
    load_signer_from_config,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .backends.config import ArtifactStoreConfig
    from ..observability import MetricsRegistry, PolicyOSTracer


PutOptions = ArtifactWriteOptions


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


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
    ) -> None:
        self.root = root
        self._layout = _CASPathLayout(root)
        self.base = self._layout.base
        self.base.mkdir(parents=True, exist_ok=True)
        self._files = _AtomicFileWriter()
        self._manifests = _ManifestLifecycle(self._files)
        observability_enabled = is_hpc_observability_enabled()
        self._tracer = tracer if tracer is not None else (
            _default_tracer() if observability_enabled else None
        )
        self._metrics = metrics if metrics is not None else (
            _default_metrics() if observability_enabled else None
        )
        self._hpc_enabled = self._tracer is not None or self._metrics is not None
        self._signing_config = signing_config or SigningConfig.from_env()
        self._default_signer: Ed25519Signer | None = None
        self._signer_lock = threading.Lock()
        self._artifact_locks: dict[str, threading.Lock] = {}
        self._artifact_locks_guard = threading.Lock()

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        return self._layout.paths(artifact_id)

    def get_paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        """Return deterministic blob/manifest paths for external CAS tooling."""
        return self._paths(artifact_id)

    def artifact_store_config(self) -> "ArtifactStoreConfig":
        """Return declarative config needed to rebuild this store instance."""
        from .backends.config import ArtifactStoreConfig

        return ArtifactStoreConfig(backend="filesystem", root=str(self.root))

    def _sig_path(self, artifact_id: ArtifactID) -> Path:
        return self._layout.sig_path(artifact_id)

    def _artifact_lock(self, artifact_id: ArtifactID) -> threading.Lock:
        with self._artifact_locks_guard:
            lock = self._artifact_locks.get(artifact_id.hex)
            if lock is None:
                lock = threading.Lock()
                self._artifact_locks[artifact_id.hex] = lock
            return lock

    def _record_integrity_failure(self, *, reason: str) -> None:
        recorder = getattr(self._metrics, "record_artifact_integrity_failure", None)
        if callable(recorder):
            recorder(backend="filesystem", reason=reason)

    def _ensure_default_signer(self) -> Ed25519Signer:
        if self._default_signer is not None:
            return self._default_signer
        with self._signer_lock:
            if self._default_signer is None:
                self._default_signer = load_signer_from_config(self._signing_config)
        return self._default_signer

    def _maybe_sign_on_put(self, artifact_id: ArtifactID) -> None:
        config = self._signing_config
        if not (config.enabled and config.sign_on_put):
            return
        try:
            if self.has_signature(artifact_id):
                return
            signer = self._ensure_default_signer()
            self.sign_artifact(
                artifact_id,
                signer,
                signer_identity=config.default_identity,
            )
        except Exception as exc:
            if config.sign_on_put_policy.strip().lower() == "warn":
                raise SigningError(
                    f"Artifact write completed but sign_on_put failed under warn policy: {exc}"
                ) from exc
            raise SigningError(f"Failed to sign artifact on put: {exc}") from exc

    def has(self, artifact_id: ArtifactID) -> bool:
        """Return whether both the blob and manifest sidecar exist for `artifact_id`."""
        blob, manifest = self._paths(artifact_id)
        exists = blob.exists() and manifest.exists()
        if self._hpc_enabled and self._metrics:
            if exists and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "existence_check"})
            elif not exists and self._metrics.artifact_cache_misses_total:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "existence_check"})
        return exists

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        """Read artifact blob bytes and emit CAS read metrics/traces when enabled.

        Raises:
            FileNotFoundError: If the blob file is missing.
            OSError: If the blob file cannot be read.
        """
        blob, _ = self._paths(artifact_id)
        if not self._hpc_enabled or self._tracer is None:
            return self._read_verified_blob(artifact_id, blob)

        short_id = f"{artifact_id.hex[:16]}..."
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

            data = self._read_verified_blob(artifact_id, blob)
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

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        """Load and validate the manifest sidecar for one artifact.

        Raises:
            FileNotFoundError: If the manifest file is missing.
            ValueError: If the manifest JSON does not match `ArtifactManifest`.
        """
        _, manp = self._paths(artifact_id)
        manifest = self._manifests.read(manp)
        try:
            _validate_manifest_identity(artifact_id, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return manifest

    def get_manifest_bytes(self, artifact_id: ArtifactID) -> bytes:
        """Return raw manifest bytes for signature verification/export paths."""
        _, manp = self._paths(artifact_id)
        return manp.read_bytes()

    def put_signature(self, artifact_id: ArtifactID, signature: DetachedSignature) -> Path:
        """Write a detached signature sidecar after validating the artifact binding.

        Raises:
            ValueError: If `signature.artifact_id` does not match `artifact_id`.
            OSError: If the sidecar cannot be written atomically.
        """
        return _put_signature(
            artifact_id=artifact_id,
            signature=signature,
            sig_path_for_artifact=self._sig_path,
            atomic_write=self._atomic_write,
        )

    def get_signature(self, artifact_id: ArtifactID) -> DetachedSignature | None:
        """Load a detached signature sidecar or return `None` when unsigned."""
        return _get_signature(
            artifact_id=artifact_id,
            sig_path_for_artifact=self._sig_path,
        )

    def has_signature(self, artifact_id: ArtifactID) -> bool:
        """Return whether a detached signature sidecar exists for `artifact_id`."""
        return _has_signature(
            artifact_id=artifact_id,
            sig_path_for_artifact=self._sig_path,
        )

    def sign_artifact(
        self,
        artifact_id: ArtifactID,
        signer: Ed25519Signer,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        """Sign one stored artifact's blob+manifest pair and persist its sidecar."""
        return _sign_artifact(
            artifact_id=artifact_id,
            signer=signer,
            signer_identity=signer_identity,
            read_blob=self.get_bytes,
            read_manifest_bytes=self.get_manifest_bytes,
            write_signature=self.put_signature,
        )

    def verify_signature(
        self,
        artifact_id: ArtifactID,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        """Verify content integrity and detached signature trust/revocation/identity state."""
        return _verify_signature(
            artifact_id=artifact_id,
            verifier=verifier,
            strict_identity=strict_identity,
            verify_integrity=self.verify,
            load_signature=self.get_signature,
            read_blob=self.get_bytes,
            read_manifest_bytes=self.get_manifest_bytes,
        )

    def sign_all_artifacts(
        self,
        signer: Ed25519Signer,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        signer_identity: str | None = None,
        only_unsigned: bool = True,
        max_workers: int = 8,
    ) -> BulkSigningReport:
        """Sign many artifacts concurrently and summarize signed/skipped/error counts."""
        ids = artifact_ids if artifact_ids is not None else self.iter_artifact_ids()
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
        )

    def verify_all_signatures(
        self,
        verifier: Ed25519Verifier,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        max_workers: int = 8,
        strict_identity: bool | None = None,
    ) -> BulkVerificationReport:
        """Verify many artifact signatures concurrently and summarize verifier outcomes."""
        ids = artifact_ids if artifact_ids is not None else self.iter_artifact_ids()
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
        )

    def _put_blob_and_manifest_once(
        self,
        *,
        data: bytes,
        opts: PutOptions,
        aid: ArtifactID,
        sha: str,
    ) -> bool:
        """Persist immutable blob/manifest pair and return whether blob was deduplicated."""
        blob, manp = self._paths(aid)
        with self._artifact_lock(aid):
            blob_preexisted = blob.exists()
            if not blob_preexisted:
                self._files.write_once(blob, data)

            if manp.exists():
                _validate_manifest_identity(aid, self._manifests.read(manp))
            else:
                manifest = self._manifests.build(
                    artifact_id=aid,
                    data=data,
                    sha=sha,
                    opts=opts,
                )
                self._manifests.write_once(manp, manifest)

        return blob_preexisted

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        """Store raw bytes under their content hash and create the immutable manifest sidecar."""
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        blob, _manp = self._paths(aid)
        blob.parent.mkdir(parents=True, exist_ok=True)

        if not self._hpc_enabled or self._tracer is None:
            self._put_blob_and_manifest_once(data=data, opts=opts, aid=aid, sha=sha)
            self._maybe_sign_on_put(aid)
            return ArtifactRef(artifact_id=aid, kind=opts.kind, media_type=opts.media_type)

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
            deduplicated = self._put_blob_and_manifest_once(
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

            self._maybe_sign_on_put(aid)
            return ArtifactRef(artifact_id=aid, kind=opts.kind, media_type=opts.media_type)

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
        )
        return self.put_bytes(data, opts2)

    def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        """Check blob presence, manifest presence, content digest, and manifest integrity."""
        if not self._hpc_enabled or self._tracer is None:
            blob, manp = self._paths(artifact_id)
            return _verify_filesystem_artifact(
                artifact_id,
                blob_path=blob,
                manifest_path=manp,
            )

        short_id = f"{artifact_id.hex[:16]}..."
        with self._tracer.start_as_current_span(
            "cas.verify",
            attributes={"cas.artifact_id": short_id},
        ) as span:
            blob, manp = self._paths(artifact_id)
            report = _verify_filesystem_artifact(
                artifact_id,
                blob_path=blob,
                manifest_path=manp,
            )
            span.set_attribute("cas.verified", report.ok)
            if report.byte_size is not None:
                span.set_attribute("cas.byte_size", report.byte_size)
            return report

    def _atomic_write(self, path: Path, data: bytes) -> None:
        self._files.write_atomic(path, data)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """List all artifact IDs that have manifest sidecars under this CAS root."""
        ids: list[ArtifactID] = []
        for manifest_path in sorted(self.base.rglob("*.manifest.json")):
            name = manifest_path.name
            if not name.endswith(".manifest.json"):
                continue
            hex64 = name[: -len(".manifest.json")]
            if not re.fullmatch(r"[0-9a-f]{64}", hex64):
                continue
            ids.append(ArtifactID.from_sha256_hex(hex64))
        return ids

    def export_subgraph(
        self,
        artifact_ids: Iterable[ArtifactID],
        target: Path,
        *,
        compress: bool = True,
        include_manifests: bool = True,
    ) -> ExportReport:
        """Export a CAS subgraph to a tarball or directory using the stable CAS layout."""
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
            verify_artifact=self.verify,
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

    def _read_verified_blob(self, artifact_id: ArtifactID, blob_path: Path) -> bytes:
        return _read_verified_blob(
            artifact_id,
            blob_path,
            load_manifest=self.get_manifest,
            record_integrity_failure=self._record_integrity_failure,
        )
