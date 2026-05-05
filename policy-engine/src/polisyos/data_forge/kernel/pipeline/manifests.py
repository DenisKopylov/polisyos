"""Shadow-compatible manifest helpers for Data Forge shared-kernel migration."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import atomic_write_json, sha256_file

if TYPE_CHECKING:
    from polisyos.data_forge.kernel.observability import TraceContext

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ManifestArtifact(DataForgeModel):
    """Artifact entry stored inside legacy-compatible manifests."""

    path: str = Field(min_length=1)
    sha256: str = Field(default="", pattern=r"^$|[0-9a-f]{64}")


class ChecksumValidationResult(DataForgeModel):
    """Checksum validation result for one manifest artifact."""

    path: str = Field(min_length=1)
    exists: bool
    expected_sha256: str = Field(default="", pattern=r"^$|[0-9a-f]{64}")
    observed_sha256: str = Field(default="", pattern=r"^$|[0-9a-f]{64}")

    @property
    def passed(self) -> bool:
        """Return whether the artifact exists and matches the expected checksum."""
        if not self.exists:
            return False
        if not self.expected_sha256:
            return True
        return self.expected_sha256 == self.observed_sha256


@dataclass(frozen=True)
class ArtifactRef:
    """Legacy manifest artifact reference retained for batch_common compatibility."""

    path: str
    sha256: str = ""


@dataclass
class StageManifest:
    """Legacy stage execution metadata retained for compatibility."""

    stage: str
    status: str
    started_at: str
    finished_at: str
    metrics: dict[str, object] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)


def utc_now_iso() -> str:
    """Return the timestamp format used by legacy batch manifests."""
    return datetime.now(UTC).isoformat()


def _utc_now_iso() -> str:
    return utc_now_iso()


def read_manifest(path: str | pathlib.Path) -> dict[str, object]:
    """Read a JSON manifest object."""
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected manifest JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def write_raw_manifest(
    *,
    manifest_path: str | pathlib.Path,
    source: str,
    endpoint: str,
    payload_path: str | pathlib.Path,
    count: int,
    filters: dict[str, object] | None = None,
    parser_version: str = "1",
    fetched_at: str | None = None,
    trace_context: TraceContext | None = None,
) -> pathlib.Path:
    """Write a legacy-compatible raw fetch manifest."""
    payload = pathlib.Path(payload_path)
    manifest = {
        "kind": "raw",
        "source": source,
        "endpoint": endpoint,
        "fetched_at": fetched_at or utc_now_iso(),
        "count": int(count),
        "payload": str(payload),
        "sha256": sha256_file(payload) if payload.exists() else "",
        "filters": filters or {},
        "parser_version": parser_version,
    }
    manifest.update(_trace_fields(trace_context))
    return _write_json(manifest_path, manifest)


def write_stage_manifest(
    *,
    manifest_path: str | pathlib.Path,
    stage: str,
    status: str,
    metrics: dict[str, object] | None = None,
    artifacts: list[str | pathlib.Path] | tuple[str | pathlib.Path, ...] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    trace_context: TraceContext | None = None,
) -> pathlib.Path:
    """Write a legacy-compatible stage manifest."""
    manifest = {
        "kind": "stage",
        "stage": stage,
        "status": status,
        "started_at": started_at or utc_now_iso(),
        "finished_at": finished_at or utc_now_iso(),
        "metrics": metrics or {},
        "artifacts": [_artifact_ref(pathlib.Path(artifact)) for artifact in artifacts or ()],
    }
    manifest.update(_trace_fields(trace_context))
    return _write_json(manifest_path, manifest)


def write_publish_manifest(
    *,
    manifest_path: str | pathlib.Path,
    pipeline: str,
    artifacts: list[str | pathlib.Path] | tuple[str | pathlib.Path, ...] | None = None,
    qc_report_path: str | pathlib.Path | None = None,
    extra: dict[str, object] | None = None,
    published_at: str | None = None,
    trace_context: TraceContext | None = None,
) -> pathlib.Path:
    """Write a legacy-compatible final publish manifest."""
    manifest: dict[str, object] = {
        "kind": "publish",
        "pipeline": pipeline,
        "published_at": published_at or utc_now_iso(),
        "artifacts": [_artifact_ref(pathlib.Path(artifact)) for artifact in artifacts or ()],
        "qc_report": str(qc_report_path) if qc_report_path else "",
    }
    if extra:
        manifest["extra"] = extra
    manifest.update(_trace_fields(trace_context))
    return _write_json(manifest_path, manifest)


def validate_manifest_artifacts(
    manifest_path: str | pathlib.Path,
    *,
    root: str | pathlib.Path | None = None,
) -> tuple[ChecksumValidationResult, ...]:
    """Validate artifact checksums listed in a manifest without mutating artifacts."""
    manifest = read_manifest(manifest_path)
    base = pathlib.Path(root) if root is not None else pathlib.Path(manifest_path).parent
    results: list[ChecksumValidationResult] = []
    for item in _list_value(manifest.get("artifacts")):
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path") or "")
        path = _resolve_path(base, raw_path)
        observed = sha256_file(path) if path.exists() else ""
        results.append(
            ChecksumValidationResult(
                path=str(path),
                exists=path.exists(),
                expected_sha256=str(item.get("sha256") or ""),
                observed_sha256=observed,
            )
        )
    return tuple(results)


def _artifact_ref(path: pathlib.Path) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": sha256_file(path) if path.exists() else "",
    }


def _write_json(path: str | pathlib.Path, payload: dict[str, object]) -> pathlib.Path:
    return atomic_write_json(path, payload)


def _trace_fields(trace_context: TraceContext | None) -> dict[str, str]:
    if trace_context is None:
        return {}
    return {
        "trace_id": trace_context.trace_id,
        "span_id": trace_context.span_id,
    }


def _resolve_path(base: pathlib.Path, raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if path.is_absolute():
        return path
    return base / path


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value


__all__ = [
    "ArtifactRef",
    "ChecksumValidationResult",
    "ManifestArtifact",
    "StageManifest",
    "read_manifest",
    "utc_now_iso",
    "validate_manifest_artifacts",
    "write_publish_manifest",
    "write_raw_manifest",
    "write_stage_manifest",
]
