"""GCS-backed content-addressable artifact store."""

from __future__ import annotations

import importlib
import threading
from typing import TYPE_CHECKING, Any

from polisyos.core.canon import content_hash
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes
from polisyos.core.observability import get_metrics

from .._integrity_ops import (
    ArtifactIntegrityError,
    VerificationReport,
    validate_manifest_identity,
    validate_read_integrity,
    verify_loaded_artifact,
)
from .._manifest_lifecycle import ManifestLifecycle
from ..ids import ArtifactID
from ..manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    artifact_reference_parts,
)
from ..store import PutOptions

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.observability import MetricsRegistry

    from .config import ArtifactStoreConfig


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


class GCSArtifactStore:
    """CAS backed by a Google Cloud Storage bucket.

    Key layout mirrors ``FileSystemCAS``::

        <prefix>/sha256/<ab>/<cd>/<hex>.blob
        <prefix>/sha256/<ab>/<cd>/<hex>.manifest.json

    ``google-cloud-storage`` is imported lazily.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "polisyos-cas",
        local_cache_dir: Path | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._bucket_name = bucket
        self._prefix = prefix.rstrip("/")
        self._local_cache_dir = local_cache_dir
        self._bucket: Any = None
        self._lock = threading.Lock()
        self._metrics = metrics if metrics is not None else _default_metrics()

    # -- lazy client ---------------------------------------------------

    def _gcs_bucket(self) -> Any:
        if self._bucket is not None:
            return self._bucket
        with self._lock:
            if self._bucket is None:
                gcs_module = importlib.import_module("google.cloud.storage")
                client = gcs_module.Client()
                self._bucket = client.bucket(self._bucket_name)
        return self._bucket

    # -- key helpers ---------------------------------------------------

    def _key(self, artifact_id: ArtifactID, suffix: str) -> str:
        h = artifact_id.hex
        return f"{self._prefix}/sha256/{h[:2]}/{h[2:4]}/{h}{suffix}"

    def _blob_key(self, artifact_id: ArtifactID) -> str:
        return self._key(artifact_id, ".blob")

    @staticmethod
    def _view_suffix(profile_sha256: str | None, suffix: str) -> str:
        if profile_sha256 is None:
            return suffix
        prefix, separator, digest = profile_sha256.partition(":")
        if (
            prefix != "sha256"
            or not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("manifest profile selector must be sha256:<64 lowercase hex>")
        return f".view.{digest}{suffix}"

    def _manifest_key(
        self,
        artifact_id: ArtifactID,
        profile_sha256: str | None = None,
    ) -> str:
        return self._key(
            artifact_id,
            self._view_suffix(profile_sha256, ".manifest.json"),
        )

    def _manifest_cache_suffix(self, profile_sha256: str | None) -> str:
        return self._view_suffix(profile_sha256, ".manifest.json")

    # -- local cache ---------------------------------------------------

    def _cache_path(self, artifact_id: ArtifactID, suffix: str) -> Path | None:
        if self._local_cache_dir is None:
            return None
        h = artifact_id.hex
        return self._local_cache_dir / h[:2] / h[2:4] / f"{h}{suffix}"

    def _cache_read(self, artifact_id: ArtifactID, suffix: str) -> bytes | None:
        p = self._cache_path(artifact_id, suffix)
        if p is not None and p.exists():
            return p.read_bytes()
        return None

    def _cache_write(self, artifact_id: ArtifactID, suffix: str, data: bytes) -> None:
        p = self._cache_path(artifact_id, suffix)
        if p is None:
            return
        with self._lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def _record_integrity_failure(self, *, reason: str) -> None:
        recorder = getattr(self._metrics, "record_artifact_integrity_failure", None)
        if callable(recorder):
            recorder(backend="gcs", reason=reason)

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Return declarative config needed to rebuild this store instance."""
        from .config import ArtifactStoreConfig

        return ArtifactStoreConfig(
            backend="gcs",
            bucket=self._bucket_name,
            prefix=self._prefix,
            local_cache_dir=(
                str(self._local_cache_dir) if self._local_cache_dir is not None else None
            ),
        )

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        aid, profile_sha256, ref = artifact_reference_parts(artifact_id)
        if (
            self._cache_read(aid, ".blob") is not None
            and self._cache_read(aid, self._manifest_cache_suffix(profile_sha256)) is not None
        ):
            if ref is not None:
                try:
                    self.get_manifest(ref)
                except (FileNotFoundError, ValueError):
                    return False
            return True
        blob = self._gcs_bucket().blob(self._blob_key(aid))
        manifest = self._gcs_bucket().blob(self._manifest_key(aid, profile_sha256))
        exists = bool(blob.exists() and manifest.exists())
        if exists and ref is not None:
            try:
                self.get_manifest(ref)
            except (FileNotFoundError, ValueError):
                return False
        return exists

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or aid
        cached = self._cache_read(aid, ".blob")
        if cached is not None:
            data = cached
        else:
            blob = self._gcs_bucket().blob(self._blob_key(aid))
            data = blob.download_as_bytes()
            self._cache_write(aid, ".blob", data)
        manifest = self.get_manifest(selected)
        try:
            validate_read_integrity(aid, data, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return data

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        aid, profile_sha256, ref = artifact_reference_parts(artifact_id)
        cache_suffix = self._manifest_cache_suffix(profile_sha256)
        cached = self._cache_read(aid, cache_suffix)
        if cached is not None:
            manifest = ArtifactManifest.model_validate_json(cached.decode("utf-8"))
        else:
            blob = self._gcs_bucket().blob(self._manifest_key(aid, profile_sha256))
            raw = blob.download_as_bytes()
            self._cache_write(aid, cache_suffix, raw)
            manifest = ArtifactManifest.model_validate_json(raw.decode("utf-8"))
        try:
            validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None and ManifestLifecycle.profile_sha256(manifest) != (
                profile_sha256
            ):
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

    @staticmethod
    def _is_precondition_error(exc: Exception) -> bool:
        code = getattr(exc, "code", None)
        code = code() if callable(code) else code
        response = getattr(exc, "response", {})
        if isinstance(response, dict):
            code = response.get("code", code)
        return code == 412 or str(code) in {"412", "PreconditionFailed"}

    def _upload_once(self, blob: Any, data: bytes, *, content_type: str) -> bytes:
        try:
            blob.upload_from_string(
                data,
                content_type=content_type,
                if_generation_match=0,
            )
            return data
        except Exception as exc:
            if not self._is_precondition_error(exc):
                raise
            return blob.download_as_bytes()

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)

        blob_obj = self._gcs_bucket().blob(self._blob_key(aid))
        persisted_blob = self._upload_once(blob_obj, data, content_type=opts.media_type)
        if content_hash(persisted_blob) != sha:
            raise ArtifactIntegrityError(f"Existing GCS blob does not match content ID {aid}")
        self._cache_write(aid, ".blob", persisted_blob)

        manifest = ManifestLifecycle.build(artifact_id=aid, data=data, sha=sha, opts=opts)
        manifest_bytes = ManifestLifecycle.to_bytes(manifest)
        profile_sha256 = ManifestLifecycle.profile_sha256(manifest)

        manifest_obj = self._gcs_bucket().blob(self._manifest_key(aid))
        if not manifest_obj.exists():
            persisted_default = self._upload_once(
                manifest_obj,
                manifest_bytes,
                content_type="application/json",
            )
        else:
            persisted_default = manifest_obj.download_as_bytes()
        default_manifest = ArtifactManifest.model_validate_json(persisted_default)
        validate_manifest_identity(aid, default_manifest)
        validate_read_integrity(aid, persisted_blob, default_manifest)
        default_profile_sha256 = ManifestLifecycle.profile_sha256(default_manifest)
        self._cache_write(aid, ".manifest.json", persisted_default)

        view_suffix = self._manifest_cache_suffix(profile_sha256)
        view_obj = self._gcs_bucket().blob(self._manifest_key(aid, profile_sha256))
        persisted_view = self._upload_once(
            view_obj,
            manifest_bytes,
            content_type="application/json",
        )
        selected_manifest = ArtifactManifest.model_validate_json(persisted_view)
        validate_manifest_identity(aid, selected_manifest)
        validate_read_integrity(aid, persisted_blob, selected_manifest)
        if ManifestLifecycle.profile_sha256(selected_manifest) != profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        self._cache_write(aid, view_suffix, persisted_view)

        return ArtifactRef(
            artifact_id=aid,
            kind=opts.kind,
            media_type=opts.media_type,
            manifest_profile_sha256=(
                profile_sha256 if profile_sha256 != default_profile_sha256 else None
            ),
        )

    def put_json(
        self,
        obj: Any,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
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
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or aid
        return verify_loaded_artifact(
            aid,
            load_bytes=lambda _aid: self.get_bytes(selected),
            load_manifest=lambda _aid: self.get_manifest(selected),
        )

    def iter_artifact_ids(self) -> list[ArtifactID]:
        ids: list[ArtifactID] = []
        prefix = f"{self._prefix}/sha256/"
        for blob in self._gcs_bucket().list_blobs(prefix=prefix):
            if blob.name.endswith(".manifest.json"):
                name = blob.name.rsplit("/", 1)[-1]
                hex64 = name.removesuffix(".manifest.json")
                if len(hex64) == 64:
                    ids.append(ArtifactID.from_sha256_hex(hex64))
        return ids
