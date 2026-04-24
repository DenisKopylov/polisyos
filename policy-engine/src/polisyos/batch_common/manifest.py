"""Manifest writers for raw/stage/publish artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.batch_common.hashing import sha256_file

if TYPE_CHECKING:
    from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


@dataclass(frozen=True)
class ArtifactRef:
    """Artifact metadata with optional SHA256 hash."""

    path: str
    sha256: str = ""


@dataclass
class StageManifest:
    """Stage execution metadata."""

    stage: str
    status: str
    started_at: str
    finished_at: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)


def write_raw_manifest(
    *,
    manifest_path: Path,
    source: str,
    endpoint: str,
    payload_path: Path,
    count: int,
    filters: dict[str, Any] | None = None,
    parser_version: str = "1",
    fetched_at: str | None = None,
) -> Path:
    """Write per-source raw fetch manifest."""
    payload = {
        "kind": "raw",
        "source": source,
        "endpoint": endpoint,
        "fetched_at": fetched_at or _utc_now_iso(),
        "count": int(count),
        "payload": str(payload_path),
        "sha256": sha256_file(payload_path) if payload_path.exists() else "",
        "filters": filters or {},
        "parser_version": parser_version,
    }
    return _write_json(manifest_path, payload)


def write_stage_manifest(
    *,
    manifest_path: Path,
    stage: str,
    status: str,
    metrics: dict[str, Any] | None = None,
    artifacts: list[Path] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> Path:
    """Write stage-level manifest with artifact checksums."""
    refs: list[dict[str, str]] = []
    for artifact in artifacts or []:
        refs.append(
            {
                "path": str(artifact),
                "sha256": sha256_file(artifact) if artifact.exists() else "",
            }
        )

    payload = {
        "kind": "stage",
        "stage": stage,
        "status": status,
        "started_at": started_at or _utc_now_iso(),
        "finished_at": finished_at or _utc_now_iso(),
        "metrics": metrics or {},
        "artifacts": refs,
    }
    return _write_json(manifest_path, payload)


def write_publish_manifest(
    *,
    manifest_path: Path,
    pipeline: str,
    artifacts: list[Path],
    qc_report_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write final publish manifest for one pipeline."""
    artifact_refs = [
        {
            "path": str(path),
            "sha256": sha256_file(path) if path.exists() else "",
        }
        for path in artifacts
    ]

    payload: dict[str, Any] = {
        "kind": "publish",
        "pipeline": pipeline,
        "published_at": _utc_now_iso(),
        "artifacts": artifact_refs,
        "qc_report": str(qc_report_path) if qc_report_path else "",
    }
    if extra:
        payload["extra"] = extra
    return _write_json(manifest_path, payload)
