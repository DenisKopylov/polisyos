"""S3-backed content-addressable artifact store."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from polisyos.core.canon import content_hash
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

from ..ids import ArtifactID
from ..manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    IntegrityInfo,
)
from ..store import PutOptions, VerificationReport


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
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._region = region
        self._local_cache_dir = local_cache_dir
        self._client: Any = None
        self._lock = threading.Lock()

    # -- lazy client ---------------------------------------------------

    def _s3(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                import boto3

                self._client = boto3.client("s3", region_name=self._region)
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

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID) -> bool:
        # Check local cache first
        if self._cache_read(artifact_id, ".blob") is not None:
            return True
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._blob_key(artifact_id))
            return True
        except self._s3().exceptions.ClientError:
            return False

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        cached = self._cache_read(artifact_id, ".blob")
        if cached is not None:
            return cached
        resp = self._s3().get_object(Bucket=self._bucket, Key=self._blob_key(artifact_id))
        data = resp["Body"].read()
        self._cache_write(artifact_id, ".blob", data)
        return data

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        cached = self._cache_read(artifact_id, ".manifest.json")
        if cached is not None:
            return ArtifactManifest.model_validate_json(cached.decode("utf-8"))
        resp = self._s3().get_object(
            Bucket=self._bucket, Key=self._manifest_key(artifact_id)
        )
        raw = resp["Body"].read()
        self._cache_write(artifact_id, ".manifest.json", raw)
        return ArtifactManifest.model_validate_json(raw.decode("utf-8"))

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
            self._s3().head_object(
                Bucket=self._bucket, Key=self._manifest_key(aid)
            )
        except Exception:
            manifest = ArtifactManifest(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                byte_size=len(data),
                artifact_schema=opts.schema,
                canon=opts.canon,
                inputs=list(opts.inputs or []),
                producer=opts.producer,
                env=opts.env,
                integrity=IntegrityInfo(sha256=sha),
            )
            man_bytes = manifest.model_dump_json(
                by_alias=True, exclude_none=True, indent=None
            ).encode("utf-8")
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
        )
        return self.put_bytes(data, opts2)

    def verify(self, artifact_id: ArtifactID) -> VerificationReport:
        try:
            data = self.get_bytes(artifact_id)
        except Exception as exc:
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                error=str(exc),
            )
        actual = hashlib.sha256(data).hexdigest()
        ok = actual == artifact_id.hex
        return VerificationReport(
            ok=ok,
            artifact_id=str(artifact_id),
            expected_sha256_hex=artifact_id.hex,
            actual_sha256_hex=actual,
            byte_size=len(data),
            error=None if ok else "SHA256 mismatch",
        )

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
