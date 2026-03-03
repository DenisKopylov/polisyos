from __future__ import annotations

import json
import os
import re
import shutil
import tarfile
import threading
import time
import uuid
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from polisyos.common.serialization import fast_json_dumps, fast_json_dumps_bytes

from ..canon import content_hash
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
from .signing import (
    ArtifactSigningResult,
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


@dataclass(frozen=True)
class ExportReport:
    exported_artifacts: int
    total_bytes: int
    output_path: Path
    missing_artifacts: list[str]
    missing_manifests: list[str]


@dataclass(frozen=True)
class ImportReport:
    imported_files: int
    imported_artifacts: int
    total_bytes: int
    source: Path
    skipped_entries: list[str]
    verification_failed: list[str]


class FileSystemCAS:
    """
    CAS layout:
      <root>/artifacts/sha256/ab/cd/<hex>.blob
      <root>/artifacts/sha256/ab/cd/<hex>.manifest.json
    """

    CONNECTOR_CACHE_NAMESPACE = "connector_cache"

    def __init__(
        self,
        root: Path,
        *,
        signing_config: SigningConfig | None = None,
    ):
        self.root = root
        self.base = root / "artifacts" / "sha256"
        self.base.mkdir(parents=True, exist_ok=True)
        self._hpc_enabled = is_hpc_observability_enabled()
        self._tracer = get_tracer() if self._hpc_enabled else None
        self._metrics = get_metrics() if self._hpc_enabled else None
        self._signing_config = signing_config or SigningConfig.from_env()
        self._default_signer: Ed25519Signer | None = None
        self._signer_lock = threading.Lock()

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        hex64 = artifact_id.hex
        d1, d2 = hex64[:2], hex64[2:4]
        dirp = self.base / d1 / d2
        blob = dirp / f"{hex64}.blob"
        manifest = dirp / f"{hex64}.manifest.json"
        return blob, manifest

    def get_paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        """Public path helper for CAS tooling."""
        return self._paths(artifact_id)

    def _sig_path(self, artifact_id: ArtifactID) -> Path:
        hex64 = artifact_id.hex
        d1, d2 = hex64[:2], hex64[2:4]
        return self.base / d1 / d2 / f"{hex64}.sig"

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
                return
            raise SigningError(f"Failed to sign artifact on put: {exc}") from exc

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

    def get_manifest_bytes(self, artifact_id: ArtifactID) -> bytes:
        _, manp = self._paths(artifact_id)
        return manp.read_bytes()

    def put_signature(self, artifact_id: ArtifactID, signature: DetachedSignature) -> Path:
        if signature.artifact_id != str(artifact_id):
            raise ValueError("signature artifact_id mismatch")
        path = self._sig_path(artifact_id)
        payload = signature.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=2,
        ).encode("utf-8")
        self._atomic_write(path, payload)
        return path

    def get_signature(self, artifact_id: ArtifactID) -> DetachedSignature | None:
        path = self._sig_path(artifact_id)
        if not path.exists():
            return None
        return DetachedSignature.model_validate_json(path.read_text("utf-8"))

    def has_signature(self, artifact_id: ArtifactID) -> bool:
        return self._sig_path(artifact_id).exists()

    def sign_artifact(
        self,
        artifact_id: ArtifactID,
        signer: Ed25519Signer,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        blob_data = self.get_bytes(artifact_id)
        manifest_data = self.get_manifest_bytes(artifact_id)
        signature = signer.sign(
            artifact_id,
            blob_data,
            manifest_data,
            signer_identity=signer_identity,
        )
        self.put_signature(artifact_id, signature)
        return signature

    def verify_signature(
        self,
        artifact_id: ArtifactID,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        integrity = self.verify(artifact_id)
        if not integrity.ok:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                message=f"Artifact integrity verification failed: {integrity.error}",
            )
        try:
            signature = self.get_signature(artifact_id)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                message=f"Invalid signature sidecar format: {exc}",
            )
        if signature is None:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.UNSIGNED,
                artifact_id=str(artifact_id),
                message="No detached signature sidecar found",
            )
        try:
            blob_data = self.get_bytes(artifact_id)
            manifest_data = self.get_manifest_bytes(artifact_id)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=f"Artifact read error: {exc}",
            )
        return verifier.verify(
            artifact_id,
            blob_data,
            manifest_data,
            signature,
            strict_identity=strict_identity,
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
        ids = list(artifact_ids) if artifact_ids is not None else self.iter_artifact_ids()
        details: list[ArtifactSigningResult] = []
        signer_lock = threading.Lock()

        def _sign_one(aid: ArtifactID) -> ArtifactSigningResult:
            if only_unsigned and self.has_signature(aid):
                return ArtifactSigningResult(
                    artifact_id=str(aid),
                    status="skipped",
                    message="already signed",
                )
            try:
                blob_data = self.get_bytes(aid)
                manifest_data = self.get_manifest_bytes(aid)
                with signer_lock:
                    signature = signer.sign(
                        aid,
                        blob_data,
                        manifest_data,
                        signer_identity=signer_identity,
                    )
                self.put_signature(aid, signature)
                return ArtifactSigningResult(
                    artifact_id=str(aid),
                    status="signed",
                    key_id=signature.key_id,
                )
            except Exception as exc:
                return ArtifactSigningResult(
                    artifact_id=str(aid),
                    status="error",
                    message=str(exc),
                )

        workers = max(1, int(max_workers))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for result in executor.map(_sign_one, ids):
                details.append(result)

        signed = sum(1 for item in details if item.status == "signed")
        skipped = sum(1 for item in details if item.status == "skipped")
        errors = sum(1 for item in details if item.status == "error")
        return BulkSigningReport(
            total=len(ids),
            signed=signed,
            skipped=skipped,
            errors=errors,
            details=details,
        )

    def verify_all_signatures(
        self,
        verifier: Ed25519Verifier,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        max_workers: int = 8,
        strict_identity: bool | None = None,
    ) -> BulkVerificationReport:
        ids = list(artifact_ids) if artifact_ids is not None else self.iter_artifact_ids()
        details: list[SignatureVerificationResult] = []

        def _verify_one(aid: ArtifactID) -> SignatureVerificationResult:
            return self.verify_signature(aid, verifier, strict_identity=strict_identity)

        workers = max(1, int(max_workers))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for result in executor.map(_verify_one, ids):
                details.append(result)

        valid = sum(1 for item in details if item.status == SignatureVerificationStatus.VALID)
        unsigned = sum(1 for item in details if item.status == SignatureVerificationStatus.UNSIGNED)
        invalid = sum(1 for item in details if item.status == SignatureVerificationStatus.INVALID)
        untrusted = sum(
            1 for item in details if item.status == SignatureVerificationStatus.UNTRUSTED
        )
        revoked = sum(1 for item in details if item.status == SignatureVerificationStatus.REVOKED)
        errors = sum(1 for item in details if item.status == SignatureVerificationStatus.ERROR)
        return BulkVerificationReport(
            total=len(ids),
            valid=valid,
            unsigned=unsigned,
            invalid=invalid,
            untrusted=untrusted,
            revoked=revoked,
            errors=errors,
            details=details,
        )

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        sha = content_hash(data)
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

            self._maybe_sign_on_put(aid)
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
            actual = content_hash(data)
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

    def iter_artifact_ids(self) -> list[ArtifactID]:
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
        missing_artifacts: list[str] = []
        missing_manifests: list[str] = []
        total_bytes = 0
        exported = 0

        sorted_ids = sorted(list(artifact_ids), key=lambda aid: aid.hex)
        if compress:
            archive_path = self._normalize_archive_path(target)
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
                for artifact_id in sorted_ids:
                    blob_path, manifest_path = self._paths(artifact_id)
                    if not blob_path.exists():
                        missing_artifacts.append(str(artifact_id))
                        continue
                    arc_blob = str(blob_path.relative_to(self.root))
                    tar.add(blob_path, arcname=arc_blob, recursive=False)
                    total_bytes += blob_path.stat().st_size

                    if include_manifests:
                        if not manifest_path.exists():
                            missing_manifests.append(str(artifact_id))
                        else:
                            arc_manifest = str(manifest_path.relative_to(self.root))
                            tar.add(manifest_path, arcname=arc_manifest, recursive=False)
                            total_bytes += manifest_path.stat().st_size
                    sig_path = self._sig_path(artifact_id)
                    if sig_path.exists():
                        arc_sig = str(sig_path.relative_to(self.root))
                        tar.add(sig_path, arcname=arc_sig, recursive=False)
                        total_bytes += sig_path.stat().st_size
                    exported += 1

                meta_payload = {
                    "schema_version": "1.0",
                    "cas_layout": "artifacts/sha256/ab/cd/<hex>.(blob|manifest.json|sig)",
                    "exported_artifacts": exported,
                    "requested_artifacts": len(sorted_ids),
                }
                meta_bytes = fast_json_dumps_bytes(meta_payload, sort_keys=True)
                info = tarfile.TarInfo(name="export_manifest.json")
                info.size = len(meta_bytes)
                info.mtime = 0
                tar.addfile(info, BytesIO(meta_bytes))
                total_bytes += len(meta_bytes)
            output_path = archive_path
        else:
            target.mkdir(parents=True, exist_ok=True)
            for artifact_id in sorted_ids:
                blob_path, manifest_path = self._paths(artifact_id)
                if not blob_path.exists():
                    missing_artifacts.append(str(artifact_id))
                    continue
                dst_blob = target / blob_path.relative_to(self.root)
                dst_blob.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(blob_path, dst_blob)
                total_bytes += blob_path.stat().st_size

                if include_manifests:
                    if not manifest_path.exists():
                        missing_manifests.append(str(artifact_id))
                    else:
                        dst_manifest = target / manifest_path.relative_to(self.root)
                        dst_manifest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(manifest_path, dst_manifest)
                        total_bytes += manifest_path.stat().st_size
                sig_path = self._sig_path(artifact_id)
                if sig_path.exists():
                    dst_sig = target / sig_path.relative_to(self.root)
                    dst_sig.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sig_path, dst_sig)
                    total_bytes += sig_path.stat().st_size
                exported += 1

            meta_path = target / "export_manifest.json"
            meta_path.write_text(
                fast_json_dumps(
                    {
                        "schema_version": "1.0",
                        "cas_layout": "artifacts/sha256/ab/cd/<hex>.(blob|manifest.json|sig)",
                        "exported_artifacts": exported,
                        "requested_artifacts": len(sorted_ids),
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            total_bytes += meta_path.stat().st_size
            output_path = target

        return ExportReport(
            exported_artifacts=exported,
            total_bytes=total_bytes,
            output_path=output_path,
            missing_artifacts=missing_artifacts,
            missing_manifests=missing_manifests,
        )

    def import_subgraph(
        self,
        source: Path,
        *,
        verify_integrity: bool = False,
    ) -> ImportReport:
        imported_files = 0
        imported_artifacts: set[str] = set()
        total_bytes = 0
        skipped_entries: list[str] = []
        verification_failed: list[str] = []

        if source.is_dir():
            for path in sorted(source.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(source)
                if rel.parts and rel.parts[0] == "export_manifest.json":
                    continue
                dst = self.root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dst)
                imported_files += 1
                total_bytes += path.stat().st_size
                artifact_id = self._artifact_id_from_member(str(rel))
                if artifact_id is not None:
                    imported_artifacts.add(str(artifact_id))
        else:
            with tarfile.open(source, "r:*") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    safe_path = self._safe_member_path(member.name)
                    if safe_path is None:
                        skipped_entries.append(member.name)
                        continue
                    if safe_path == PurePosixPath("export_manifest.json"):
                        continue
                    dst = self.root / Path(*safe_path.parts)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        skipped_entries.append(member.name)
                        continue
                    with extracted, dst.open("wb") as handle:
                        shutil.copyfileobj(extracted, handle)
                    imported_files += 1
                    total_bytes += int(member.size)
                    artifact_id = self._artifact_id_from_member(str(safe_path))
                    if artifact_id is not None:
                        imported_artifacts.add(str(artifact_id))

        if verify_integrity:
            for artifact_ref in sorted(imported_artifacts):
                report = self.verify(ArtifactID.model_validate(artifact_ref))
                if not report.ok:
                    verification_failed.append(artifact_ref)

        return ImportReport(
            imported_files=imported_files,
            imported_artifacts=len(imported_artifacts),
            total_bytes=total_bytes,
            source=source,
            skipped_entries=skipped_entries,
            verification_failed=verification_failed,
        )

    @staticmethod
    def _normalize_archive_path(path: Path) -> Path:
        suffixes = path.suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]:
            return path
        if path.suffix == ".tar":
            return path.with_suffix(".tar.gz")
        return Path(f"{path}.tar.gz")

    @staticmethod
    def _safe_member_path(name: str) -> PurePosixPath | None:
        rel = PurePosixPath(name)
        if rel.is_absolute():
            return None
        if any(part in ("..", "") for part in rel.parts):
            return None
        return rel

    @staticmethod
    def _artifact_id_from_member(path: str) -> ArtifactID | None:
        file_name = Path(path).name
        if file_name.endswith(".blob"):
            hex64 = file_name[: -len(".blob")]
        elif file_name.endswith(".manifest.json"):
            hex64 = file_name[: -len(".manifest.json")]
        elif file_name.endswith(".sig"):
            hex64 = file_name[: -len(".sig")]
        else:
            return None
        if not re.fullmatch(r"[0-9a-f]{64}", hex64):
            return None
        return ArtifactID.from_sha256_hex(hex64)
