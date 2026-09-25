"""S3-backed content-addressable artifact store."""

from __future__ import annotations

import hashlib
import importlib
import threading
from typing import TYPE_CHECKING, Any, cast

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


class S3ArtifactStore:
    """CAS backed by an S3 bucket.

    Key layout mirrors ``FileSystemCAS``::

        <prefix>/sha256/<ab>/<cd>/<hex>.blob
        <prefix>/sha256/<ab>/<cd>/<hex>.manifest.json

    ``boto3`` is imported lazily so the module can be loaded even when
    the SDK is not installed (e.g. in local-only test environments).
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "polisyos-cas",
        region: str = "us-east-1",
        local_cache_dir: Path | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._region = region
        self._local_cache_dir = local_cache_dir
        self._client: Any = None
        self._lock = threading.Lock()
        self._metrics = metrics if metrics is not None else _default_metrics()

    # -- lazy client ---------------------------------------------------

    def _s3(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                boto3_module = importlib.import_module("boto3")
                self._client = boto3_module.client("s3", region_name=self._region)
        return self._client

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
        suffix = self._view_suffix(profile_sha256, ".manifest.json")
        return self._key(artifact_id, suffix)

    def _manifest_cache_suffix(self, profile_sha256: str | None) -> str:
        return self._view_suffix(profile_sha256, ".manifest.json")

    # -- local cache helpers -------------------------------------------

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
            recorder(backend="s3", reason=reason)

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Return declarative config needed to rebuild this store instance."""
        from .config import ArtifactStoreConfig

        return ArtifactStoreConfig(
            backend="s3",
            bucket=self._bucket,
            prefix=self._prefix,
            region=self._region,
            local_cache_dir=(
                str(self._local_cache_dir) if self._local_cache_dir is not None else None
            ),
        )

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        aid, profile_sha256, ref = artifact_reference_parts(artifact_id)
        manifest_suffix = self._manifest_cache_suffix(profile_sha256)
        # Check local cache first
        if (
            self._cache_read(aid, ".blob") is not None
            and self._cache_read(aid, manifest_suffix) is not None
        ):
            if ref is not None:
                self.get_manifest(ref)
            return True
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._blob_key(aid))
            self._s3().head_object(
                Bucket=self._bucket,
                Key=self._manifest_key(aid, profile_sha256),
            )
            if ref is not None:
                self.get_manifest(ref)
            return True
        except self._s3().exceptions.ClientError as exc:
            if self._is_missing_error(exc):
                return False
            raise

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        aid, _profile_sha256, ref = artifact_reference_parts(artifact_id)
        selected = ref or aid
        cached = self._cache_read(aid, ".blob")
        if cached is None:
            resp = self._s3().get_object(Bucket=self._bucket, Key=self._blob_key(aid))
            data = cast("bytes", resp["Body"].read())
            self._cache_write(aid, ".blob", data)
        else:
            data = cached
        manifest = self.get_manifest(selected)
        try:
            validate_read_integrity(aid, data, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        self._cache_write(aid, ".blob", data)
        return data

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        aid, profile_sha256, ref = artifact_reference_parts(artifact_id)
        cache_suffix = self._manifest_cache_suffix(profile_sha256)
        cached = self._cache_read(aid, cache_suffix)
        if cached is not None:
            manifest = ArtifactManifest.model_validate_json(cached.decode("utf-8"))
            try:
                validate_manifest_identity(aid, manifest)
                self._validate_selected_manifest(aid, profile_sha256, ref, manifest)
            except ArtifactIntegrityError as exc:
                self._record_integrity_failure(reason=type(exc).__name__)
                raise
            return manifest
        resp = self._s3().get_object(
            Bucket=self._bucket,
            Key=self._manifest_key(aid, profile_sha256),
        )
        raw = resp["Body"].read()
        self._cache_write(aid, cache_suffix, raw)
        manifest = ArtifactManifest.model_validate_json(raw.decode("utf-8"))
        try:
            validate_manifest_identity(aid, manifest)
            self._validate_selected_manifest(aid, profile_sha256, ref, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return manifest

    @staticmethod
    def _validate_selected_manifest(
        artifact_id: ArtifactID,
        profile_sha256: str | None,
        ref: ArtifactRef | None,
        manifest: ArtifactManifest,
    ) -> None:
        if profile_sha256 is not None and ManifestLifecycle.profile_sha256(manifest) != (
            profile_sha256
        ):
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {artifact_id}")
        if ref is not None and (ref.kind != manifest.kind or ref.media_type != manifest.media_type):
            raise ArtifactIntegrityError(
                f"Artifact reference type does not match selected manifest for {artifact_id}"
            )

    def _put_immutable_once(self, *, key: str, data: bytes, content_type: str) -> bytes:
        try:
            self._s3().put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                IfNoneMatch="*",
            )
            return data
        except self._s3().exceptions.ClientError as exc:
            if not self._is_precondition_error(exc):
                raise
            response = self._s3().get_object(Bucket=self._bucket, Key=key)
            return cast("bytes", response["Body"].read())

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        persisted_blob = self._put_immutable_once(
            key=self._blob_key(aid),
            data=data,
            content_type=opts.media_type,
        )
        if content_hash(persisted_blob) != sha:
            raise ArtifactIntegrityError(f"Existing S3 blob does not match content ID {aid}")
        self._cache_write(aid, ".blob", persisted_blob)

        manifest = ManifestLifecycle.build(artifact_id=aid, data=data, sha=sha, opts=opts)
        manifest_bytes = ManifestLifecycle.to_bytes(manifest)
        profile_sha256 = ManifestLifecycle.profile_sha256(manifest)

        # Retain the first manifest as the historical ID-only default.
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._manifest_key(aid))
        except self._s3().exceptions.ClientError as exc:
            if not self._is_missing_error(exc):
                raise
            persisted_default = self._put_immutable_once(
                key=self._manifest_key(aid),
                data=manifest_bytes,
                content_type="application/json",
            )
        else:
            persisted_default = cast(
                "bytes",
                self._s3().get_object(
                    Bucket=self._bucket,
                    Key=self._manifest_key(aid),
                )["Body"].read(),
            )
        default_manifest = ArtifactManifest.model_validate_json(persisted_default)
        validate_manifest_identity(aid, default_manifest)
        validate_read_integrity(aid, persisted_blob, default_manifest)
        default_profile_sha256 = ManifestLifecycle.profile_sha256(default_manifest)
        self._cache_write(aid, ".manifest.json", persisted_default)

        view_suffix = self._manifest_cache_suffix(profile_sha256)
        persisted_view = self._put_immutable_once(
            key=self._manifest_key(aid, profile_sha256),
            data=manifest_bytes,
            content_type="application/json",
        )
        selected_manifest = ArtifactManifest.model_validate_json(persisted_view)
        validate_manifest_identity(aid, selected_manifest)
        validate_read_integrity(aid, persisted_blob, selected_manifest)
        self._validate_selected_manifest(aid, profile_sha256, None, selected_manifest)
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

    @staticmethod
    def _is_missing_error(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        code = str(error.get("Code", "")).strip()
        status_code = None
        metadata = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
        if isinstance(metadata, dict):
            status_code = metadata.get("HTTPStatusCode")
        return code in {"404", "NotFound", "NoSuchKey"} or status_code == 404

    @staticmethod
    def _is_precondition_error(exc: Exception) -> bool:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        metadata = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
        status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
        code = str(error.get("Code", "")).strip() if isinstance(error, dict) else ""
        return status == 412 or code in {"412", "PreconditionFailed", "ConditionalRequestConflict"}

    def iter_artifact_ids(self) -> list[ArtifactID]:
        ids: list[ArtifactID] = []
        paginator = self._s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=f"{self._prefix}/sha256/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".manifest.json"):
                    name = key.rsplit("/", 1)[-1]
                    hex64 = name.removesuffix(".manifest.json")
                    if len(hex64) == 64:
                        ids.append(ArtifactID.from_sha256_hex(hex64))
        return ids


def _b64_sha256(data: bytes) -> str:
    """Base64-encoded SHA256 for S3 ChecksumSHA256 header."""
    import base64

    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
