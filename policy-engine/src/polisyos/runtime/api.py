from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from polisyos.common.serialization import fast_json_dumps
from polisyos.core.contracts.foundry import EnvironmentManifestRef
from polisyos.runtime.manifest import ArtifactRef, RunManifest


def _run_dir(base_dir: Path, run_id: str) -> Path:
    return base_dir / run_id


def _manifest_path(base_dir: Path, run_id: str) -> Path:
    return _run_dir(base_dir, run_id) / "manifest.json"


def _load_manifest(base_dir: Path, run_id: str) -> RunManifest:
    path = _manifest_path(base_dir, run_id)
    try:
        return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        manifest = RunManifest(run_id=run_id, run_root=str(base_dir))
        _write_manifest(base_dir, manifest)
        return manifest


def _write_manifest(base_dir: Path, manifest: RunManifest) -> Path:
    run_dir = _run_dir(base_dir, manifest.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    if manifest.run_root is None:
        manifest.run_root = str(base_dir)
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
        run_root=str(base_dir),
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
    safe_name = filename or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{artifact_type}{suffix}"
    path = artifact_dir / safe_name

    if media_type == "application/json":
        path.write_text(
            fast_json_dumps(payload, sort_keys=False),
            encoding="utf-8",
        )
    else:
        path.write_text(str(payload), encoding="utf-8")

    rel_path = path.relative_to(base_dir)
    ref = ArtifactRef(
        artifact_type=artifact_type,
        path=str(rel_path),
        relative_path=str(rel_path),
        media_type=media_type,
        schema_version=schema_version,
        step=step,
    )

    manifest = _load_manifest(base_dir, run_id)
    manifest.run_root = manifest.run_root or str(base_dir)
    manifest.artifacts.append(ref)
    if artifact_type == "environment_ref":
        try:
            payload_dict = payload if isinstance(payload, dict) else {}
            env_payload = payload_dict.get("environment_ref", payload)
            manifest.environment_ref = EnvironmentManifestRef.model_validate(env_payload)
            fingerprint = payload_dict.get("fingerprint")
            if isinstance(fingerprint, str):
                manifest.environment_fingerprint = fingerprint
        except Exception:
            pass
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
        f.write(fast_json_dumps(record, sort_keys=False) + "\n")

    manifest = _load_manifest(base_dir, run_id)
    if not any(ref.artifact_type == "audit_trail" for ref in manifest.artifacts):
        manifest.artifacts.append(
            ArtifactRef(
                artifact_type="audit_trail",
                path=str(audit_path.relative_to(base_dir)),
                relative_path=str(audit_path.relative_to(base_dir)),
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
    manifest.finished_at = datetime.now(timezone.utc).isoformat()
    manifest.pruning_reason = pruning_reason
    _write_manifest(base_dir, manifest)


def resolve_artifact_path(
    ref: ArtifactRef, *, base_dir: Path = Path("runs"), run_root: Optional[Path] = None
) -> Path:
    """
    Возвращает абсолютный путь к артефакту, опираясь на relative_path/path и run_root.

    Приоритет:
    1. ref.relative_path, собранный с run_root или base_dir
    2. ref.path, если он абсолютный — возвращаем как есть
       если относительный — собираем с run_root или base_dir
    """
    if ref.relative_path:
        root = run_root or base_dir
        return (root / ref.relative_path).resolve()
    if ref.path:
        p = Path(ref.path)
        if p.is_absolute():
            return p
        root = run_root or base_dir
        return (root / p).resolve()
    raise ValueError("ArtifactRef is missing path information")
