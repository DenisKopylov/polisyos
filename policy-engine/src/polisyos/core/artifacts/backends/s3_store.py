"""S3-backed content-addressable artifact store."""

from __future__ import annotations

import hashlib
import importlib
import threading
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.serialization import fast_json_dumps_bytes
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
from ..ids import ArtifactID
from ..manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    IntegrityInfo,
)
from ..store import PutOptions

if TYPE_CHECKING:
    from pathlib import Path

    from .config import ArtifactStoreConfig
    from polisyos.core.observability import MetricsRegistry


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

    def _manifest_key(self, artifact_id: ArtifactID) -> str:
        return self._key(artifact_id, ".manifest.json")

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

    def artifact_store_config(self) -> "ArtifactStoreConfig":
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

    def has(self, artifact_id: ArtifactID) -> bool:
        # Check local cache first
        if (
            self._cache_read(artifact_id, ".blob") is not None
            and self._cache_read(artifact_id, ".manifest.json") is not None
        ):
            return True
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._blob_key(artifact_id))
            self._s3().head_object(Bucket=self._bucket, Key=self._manifest_key(artifact_id))
            return True
        except self._s3().exceptions.ClientError as exc:
            if self._is_missing_error(exc):
                return False
            raise

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        cached = self._cache_read(artifact_id, ".blob")
        if cached is None:
            resp = self._s3().get_object(Bucket=self._bucket, Key=self._blob_key(artifact_id))
            data = cast(bytes, resp["Body"].read())
            self._cache_write(artifact_id, ".blob", data)
        else:
            data = cached
        manifest = self.get_manifest(artifact_id)
        try:
            validate_read_integrity(artifact_id, data, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        self._cache_write(artifact_id, ".blob", data)
        return data

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        cached = self._cache_read(artifact_id, ".manifest.json")
        if cached is not None:
            manifest = ArtifactManifest.model_validate_json(cached.decode("utf-8"))
            try:
                validate_manifest_identity(artifact_id, manifest)
            except ArtifactIntegrityError as exc:
                self._record_integrity_failure(reason=type(exc).__name__)
                raise
            return manifest
        resp = self._s3().get_object(
            Bucket=self._bucket, Key=self._manifest_key(artifact_id)
        )
        raw = resp["Body"].read()
        self._cache_write(artifact_id, ".manifest.json", raw)
        manifest = ArtifactManifest.model_validate_json(raw.decode("utf-8"))
        try:
            validate_manifest_identity(artifact_id, manifest)
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return manifest

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)

        # Idempotent: skip if blob already exists
        if not self.has(aid):
            self._s3().put_object(
                Bucket=self._bucket,
                Key=self._blob_key(aid),
                Body=data,
                ContentType=opts.media_type,
                ChecksumSHA256=_b64_sha256(data),
            )
            self._cache_write(aid, ".blob", data)

        # Write manifest if missing
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._manifest_key(aid))
        except self._s3().exceptions.ClientError as exc:
            if not self._is_missing_error(exc):
                raise
            manifest = ArtifactManifest.model_validate(
                {
                    "artifact_id": aid,
                    "kind": opts.kind,
                    "media_type": opts.media_type,
                    "byte_size": len(data),
                    "schema": opts.schema,
                    "canon": opts.canon,
                    "inputs": list(opts.inputs or []),
                    "producer": opts.producer,
                    "env": opts.env,
                    "governance": getattr(opts, "governance", None),
                    "integrity": IntegrityInfo(sha256=sha),
                }
            )
            man_bytes = fast_json_dumps_bytes(
                manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
                sort_keys=True,
            )
            self._s3().put_object(
                Bucket=self._bucket,
                Key=self._manifest_key(aid),
                Body=man_bytes,
                ContentType="application/json",
            )
            self._cache_write(aid, ".manifest.json", man_bytes)

        return ArtifactRef(artifact_id=aid, kind=opts.kind, media_type=opts.media_type)

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
        )
        return self.put_bytes(data, opts2)

    def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        return verify_loaded_artifact(
            artifact_id,
            load_bytes=self.get_bytes,
            load_manifest=self.get_manifest,
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

    def iter_artifact_ids(self) -> list[ArtifactID]:
        ids: list[ArtifactID] = []
        paginator = self._s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self._bucket, Prefix=f"{self._prefix}/sha256/"
        ):
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
