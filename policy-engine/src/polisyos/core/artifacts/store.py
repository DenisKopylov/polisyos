from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..canon.canon_json import CanonSpec, to_canonical_bytes
from ..observability import get_metrics, get_tracer
from ..observability.config import is_hpc_observability_enabled
from .ids import ArtifactID
from .manifest import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    EnvInfo,
    InputRef,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
)


@dataclass(frozen=True)
class PutOptions:
    kind: str
    media_type: str
    schema: SchemaInfo | None = None
    producer: ProducerInfo | None = None
    env: EnvInfo | None = None
    inputs: list[InputRef] | None = None
    canon: CanonInfo | None = None


class VerificationReport(BaseModel):
    ok: bool
    artifact_id: str
    expected_sha256_hex: str
    actual_sha256_hex: str | None = None
    byte_size: int | None = None
    error: str | None = None


class FileSystemCAS:
    """
    CAS layout:
      <root>/artifacts/sha256/ab/cd/<hex>.blob
      <root>/artifacts/sha256/ab/cd/<hex>.manifest.json
    """

    CONNECTOR_CACHE_NAMESPACE = "connector_cache"

    def __init__(self, root: Path):
        self.root = root
        self.base = root / "artifacts" / "sha256"
        self.base.mkdir(parents=True, exist_ok=True)
        self._hpc_enabled = is_hpc_observability_enabled()
        self._tracer = get_tracer() if self._hpc_enabled else None
        self._metrics = get_metrics() if self._hpc_enabled else None

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        hex64 = artifact_id.hex
        d1, d2 = hex64[:2], hex64[2:4]
        dirp = self.base / d1 / d2
        blob = dirp / f"{hex64}.blob"
        manifest = dirp / f"{hex64}.manifest.json"
        return blob, manifest

    def has(self, artifact_id: ArtifactID) -> bool:
        blob, manifest = self._paths(artifact_id)
        exists = blob.exists() and manifest.exists()
        if self._hpc_enabled and self._metrics:
            if exists and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "existence_check"})
            elif not exists and self._metrics.artifact_cache_misses_total:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "existence_check"})
        return exists

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        blob, _ = self._paths(artifact_id)
        if not self._hpc_enabled or self._tracer is None:
            return blob.read_bytes()

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

            data = blob.read_bytes()
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
        _, manp = self._paths(artifact_id)
        return ArtifactManifest.model_validate_json(manp.read_text("utf-8"))

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = hashlib.sha256(data).hexdigest()
        aid = ArtifactID.from_sha256_hex(sha)
        blob, manp = self._paths(aid)
        blob.parent.mkdir(parents=True, exist_ok=True)

        if not self._hpc_enabled or self._tracer is None:
            if not blob.exists():
                self._atomic_write(blob, data)

            if not manp.exists():
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
                    by_alias=True,
                    exclude_none=True,
                    indent=None,
                ).encode("utf-8")
                self._atomic_write(manp, man_bytes)

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
            deduplicated = blob.exists()

            if not deduplicated:
                self._atomic_write(blob, data)

            if not manp.exists():
                manifest = ArtifactManifest(
                    artifact_id=aid,
                    kind=opts.kind,
                    media_type=opts.media_type,
                    byte_size=byte_size,
                    artifact_schema=opts.schema,
                    canon=opts.canon,
                    inputs=list(opts.inputs or []),
                    producer=opts.producer,
                    env=opts.env,
                    integrity=IntegrityInfo(sha256=sha),
                )
                man_bytes = manifest.model_dump_json(
                    by_alias=True,
                    exclude_none=True,
                    indent=None,
                ).encode("utf-8")
                self._atomic_write(manp, man_bytes)

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
        if not self._hpc_enabled or self._tracer is None:
            return self._verify_impl(artifact_id)

        short_id = f"{artifact_id.hex[:16]}..."
        with self._tracer.start_as_current_span(
            "cas.verify",
            attributes={"cas.artifact_id": short_id},
        ) as span:
            report = self._verify_impl(artifact_id)
            span.set_attribute("cas.verified", report.ok)
            if report.byte_size is not None:
                span.set_attribute("cas.byte_size", report.byte_size)
            return report

    def _verify_impl(self, artifact_id: ArtifactID) -> VerificationReport:
        try:
            blob, manp = self._paths(artifact_id)
            if not blob.exists():
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    error="blob missing",
                )
            if not manp.exists():
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    error="manifest missing",
                )

            data = blob.read_bytes()
            actual = hashlib.sha256(data).hexdigest()
            if actual != artifact_id.hex:
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    actual_sha256_hex=actual,
                    byte_size=len(data),
                    error="sha256 mismatch",
                )

            try:
                manifest = ArtifactManifest.model_validate_json(manp.read_text("utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    actual_sha256_hex=actual,
                    byte_size=len(data),
                    error=f"manifest invalid: {exc}",
                )

            if manifest.integrity.sha256 != artifact_id.hex:
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    actual_sha256_hex=actual,
                    byte_size=len(data),
                    error="manifest integrity mismatch",
                )

            if manifest.byte_size != len(data):
                return VerificationReport(
                    ok=False,
                    artifact_id=str(artifact_id),
                    expected_sha256_hex=artifact_id.hex,
                    actual_sha256_hex=actual,
                    byte_size=len(data),
                    error="byte_size mismatch",
                )

            return VerificationReport(
                ok=True,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                actual_sha256_hex=actual,
                byte_size=len(data),
            )
        except Exception as exc:  # pragma: no cover - defensive
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                error=str(exc),
            )

    def _atomic_write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
