"""GCS-backed content-addressable artifact store."""

from __future__ import annotations

import hashlib
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
    ) -> None:
        self._bucket_name = bucket
        self._prefix = prefix.rstrip("/")
        self._local_cache_dir = local_cache_dir
        self._bucket: Any = None
        self._lock = threading.Lock()

    # -- lazy client ---------------------------------------------------

    def _gcs_bucket(self) -> Any:
        if self._bucket is not None:
            return self._bucket
        with self._lock:
            if self._bucket is None:
                from google.cloud import storage as gcs

                client = gcs.Client()
                self._bucket = client.bucket(self._bucket_name)
        return self._bucket

    # -- key helpers ---------------------------------------------------

    def _key(self, artifact_id: ArtifactID, suffix: str) -> str:
        h = artifact_id.hex
        return f"{self._prefix}/sha256/{h[:2]}/{h[2:4]}/{h}{suffix}"

    def _blob_key(self, artifact_id: ArtifactID) -> str:
        return self._key(artifact_id, ".blob")

    def _manifest_key(self, artifact_id: ArtifactID) -> str:
        return self._key(artifact_id, ".manifest.json")

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

    # -- ArtifactStore protocol ----------------------------------------

    def has(self, artifact_id: ArtifactID) -> bool:
        if self._cache_read(artifact_id, ".blob") is not None:
            return True
        blob = self._gcs_bucket().blob(self._blob_key(artifact_id))
        return blob.exists()

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        cached = self._cache_read(artifact_id, ".blob")
        if cached is not None:
            return cached
        blob = self._gcs_bucket().blob(self._blob_key(artifact_id))
        data = blob.download_as_bytes()
        self._cache_write(artifact_id, ".blob", data)
        return data

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        cached = self._cache_read(artifact_id, ".manifest.json")
        if cached is not None:
            return ArtifactManifest.model_validate_json(cached.decode("utf-8"))
        blob = self._gcs_bucket().blob(self._manifest_key(artifact_id))
        raw = blob.download_as_bytes()
        self._cache_write(artifact_id, ".manifest.json", raw)
        return ArtifactManifest.model_validate_json(raw.decode("utf-8"))

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)

        blob_obj = self._gcs_bucket().blob(self._blob_key(aid))
        if not blob_obj.exists():
            blob_obj.upload_from_string(data, content_type=opts.media_type)
            self._cache_write(aid, ".blob", data)

        manifest_obj = self._gcs_bucket().blob(self._manifest_key(aid))
        if not manifest_obj.exists():
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
            manifest_obj.upload_from_string(man_bytes, content_type="application/json")
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
        prefix = f"{self._prefix}/sha256/"
        for blob in self._gcs_bucket().list_blobs(prefix=prefix):
            if blob.name.endswith(".manifest.json"):
                name = blob.name.rsplit("/", 1)[-1]
                hex64 = name.removesuffix(".manifest.json")
                if len(hex64) == 64:
                    ids.append(ArtifactID.from_sha256_hex(hex64))
        return ids
