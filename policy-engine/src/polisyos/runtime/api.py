from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from polisyos.runtime.manifest import ArtifactRef, RunManifest


def _run_dir(base_dir: Path, run_id: str) -> Path:
    return base_dir / run_id


def _manifest_path(base_dir: Path, run_id: str) -> Path:
    return _run_dir(base_dir, run_id) / "manifest.json"


def _load_manifest(base_dir: Path, run_id: str) -> RunManifest:
    path = _manifest_path(base_dir, run_id)
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _write_manifest(base_dir: Path, manifest: RunManifest) -> Path:
    run_dir = _run_dir(base_dir, manifest.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(base_dir, manifest.run_id)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def start_run(
    *,
    run_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    generator: Optional[Dict[str, str]] = None,
    budgets: Optional[Dict[str, float]] = None,
    base_dir: Path = Path("runs"),
) -> RunManifest:
    run_id = run_id or str(uuid.uuid4())[:8]
    manifest = RunManifest(
        run_id=run_id,
        parent_run_id=parent_run_id,
        generator=generator or {},
        budgets=budgets or {},
        budget_usage={},
    )
    _write_manifest(base_dir, manifest)
    return manifest


def log_artifact(
    *,
    run_id: str,
    artifact_type: str,
    payload: Any,
    media_type: str = "application/json",
    schema_version: Optional[str] = None,
    step: Optional[str] = None,
    filename: Optional[str] = None,
    base_dir: Path = Path("runs"),
) -> ArtifactRef:
    run_dir = _run_dir(base_dir, run_id)
    artifact_dir = run_dir / "artifacts" / artifact_type
    artifact_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".json" if media_type == "application/json" else ".txt"
    safe_name = filename or f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{artifact_type}{suffix}"
    path = artifact_dir / safe_name

    if media_type == "application/json":
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")

    ref = ArtifactRef(
        artifact_type=artifact_type,
        path=str(path),
        media_type=media_type,
        schema_version=schema_version,
        step=step,
    )

    manifest = _load_manifest(base_dir, run_id)
    manifest.artifacts.append(ref)
    _write_manifest(base_dir, manifest)
    return ref


def append_audit(
    *,
    run_id: str,
    record: Dict[str, Any],
    base_dir: Path = Path("runs"),
) -> None:
    run_dir = _run_dir(base_dir, run_id)
    audit_path = run_dir / "audit.jsonl"
    run_dir.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")

    manifest = _load_manifest(base_dir, run_id)
    if not any(ref.artifact_type == "audit_trail" for ref in manifest.artifacts):
        manifest.artifacts.append(
            ArtifactRef(
                artifact_type="audit_trail",
                path=str(audit_path),
                media_type="application/json",
            )
        )
        _write_manifest(base_dir, manifest)


def update_budget_usage(
    *,
    run_id: str,
    budget_usage: Dict[str, float],
    base_dir: Path = Path("runs"),
) -> None:
    manifest = _load_manifest(base_dir, run_id)
    manifest.budget_usage = dict(budget_usage)
    _write_manifest(base_dir, manifest)


def finalize_run(
    *,
    run_id: str,
    status: str,
    pruning_reason: Optional[Dict[str, Any]] = None,
    base_dir: Path = Path("runs"),
) -> None:
    manifest = _load_manifest(base_dir, run_id)
    manifest.status = status
    manifest.finished_at = datetime.utcnow().isoformat()
    manifest.pruning_reason = pruning_reason
    _write_manifest(base_dir, manifest)
