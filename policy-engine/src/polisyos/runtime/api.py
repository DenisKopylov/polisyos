"""Write and finalize lightweight run manifests and artifact references on disk."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.common.serialization import fast_json_dumps
from polisyos.core.contracts.foundry import EnvironmentManifestRef
from polisyos.runtime.manifest import ArtifactRef, RunManifest

logger = get_logger(__name__)
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_MANIFEST_LOCKS: dict[Path, threading.RLock] = {}
_MANIFEST_LOCKS_GUARD = threading.Lock()
_MANIFEST_JOURNAL_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class RuntimeArtifactWrite:
    """Batchable run-local artifact write request."""

    artifact_type: str
    payload: Any
    media_type: str = "application/json"
    schema_version: str | None = None
    step: str | None = None
    filename: str | None = None


def _run_dir(base_dir: Path, run_id: str) -> Path:
    return base_dir / _safe_path_component(run_id, field_name="run_id")


def _manifest_path(base_dir: Path, run_id: str) -> Path:
    return _run_dir(base_dir, run_id) / "manifest.json"


def _manifest_journal_path(base_dir: Path, run_id: str) -> Path:
    return _run_dir(base_dir, run_id) / ".manifest-journal.json"


def _audit_path(base_dir: Path, run_id: str) -> Path:
    return _run_dir(base_dir, run_id) / "audit.jsonl"


def _manifest_lock(path: Path) -> threading.RLock:
    key = path.resolve()
    with _MANIFEST_LOCKS_GUARD:
        lock = _MANIFEST_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _MANIFEST_LOCKS[key] = lock
        return lock


def _safe_path_component(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if value in {".", ".."} or not _SAFE_COMPONENT_RE.fullmatch(value):
        raise ValueError(f"{field_name} contains unsafe path characters")
    return value


def _safe_artifact_filename(filename: str) -> str:
    candidate = Path(filename)
    if candidate.is_absolute() or len(candidate.parts) != 1:
        raise ValueError("filename must be a single relative path component")
    return _safe_path_component(candidate.name, field_name="filename")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_manifest_from_disk(base_dir: Path, run_id: str) -> RunManifest:
    return RunManifest.model_validate_json(
        _manifest_path(base_dir, run_id).read_text(encoding="utf-8")
    )


def _audit_ref(base_dir: Path, run_id: str) -> ArtifactRef:
    audit_path = _audit_path(base_dir, run_id)
    rel_path = audit_path.relative_to(base_dir)
    return ArtifactRef(
        artifact_type="audit_trail",
        path=str(rel_path),
        relative_path=str(rel_path),
        media_type="application/json",
    )


def _artifact_ref_identity(ref: ArtifactRef) -> tuple[str, str | None, str | None]:
    return (ref.artifact_type, ref.relative_path, ref.path)


def _manifest_has_ref(manifest: RunManifest, ref: ArtifactRef) -> bool:
    ref_id = _artifact_ref_identity(ref)
    return any(_artifact_ref_identity(existing) == ref_id for existing in manifest.artifacts)


def _merge_manifest_ref(manifest: RunManifest, ref: ArtifactRef) -> bool:
    if _manifest_has_ref(manifest, ref):
        return False
    manifest.artifacts.append(ref)
    return True


def _ensure_audit_file(base_dir: Path, run_id: str) -> Path:
    audit_path = _audit_path(base_dir, run_id)
    if not audit_path.exists():
        _write_text_atomic(audit_path, "")
    return audit_path


def _append_audit_line(audit_path: Path, line: str) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _audit_file_has_trailing_line(audit_path: Path, line: str) -> bool:
    if not audit_path.exists():
        return False
    line_bytes = line.encode("utf-8")
    if not line_bytes:
        return True
    with audit_path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size < len(line_bytes):
            return False
        handle.seek(size - len(line_bytes))
        return handle.read() == line_bytes


def _write_manifest_journal(base_dir: Path, run_id: str, payload: dict[str, Any]) -> None:
    journal_payload = {
        "schema_version": _MANIFEST_JOURNAL_SCHEMA_VERSION,
        **payload,
    }
    _write_text_atomic(
        _manifest_journal_path(base_dir, run_id),
        fast_json_dumps(journal_payload, sort_keys=True),
    )


def _clear_manifest_journal(base_dir: Path, run_id: str) -> None:
    journal_path = _manifest_journal_path(base_dir, run_id)
    try:
        journal_path.unlink()
    except FileNotFoundError:
        return


def _apply_environment_metadata_if_changed(manifest: RunManifest, payload: Any) -> bool:
    before_environment = (
        manifest.environment_ref.model_dump(mode="json")
        if manifest.environment_ref is not None
        else None
    )
    before_fingerprint = manifest.environment_fingerprint
    _apply_environment_ref_metadata(manifest, payload)
    after_environment = (
        manifest.environment_ref.model_dump(mode="json")
        if manifest.environment_ref is not None
        else None
    )
    return (
        before_environment != after_environment
        or before_fingerprint != manifest.environment_fingerprint
    )


def _recover_manifest_journal(base_dir: Path, run_id: str) -> None:
    journal_path = _manifest_journal_path(base_dir, run_id)
    if not journal_path.exists():
        return

    run_dir = _run_dir(base_dir, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning(
            "Ignoring unreadable manifest journal for run %s at %s: %s",
            run_id,
            journal_path,
            exc,
        )
        return

    try:
        manifest = _load_manifest_from_disk(base_dir, run_id)
    except FileNotFoundError:
        manifest = RunManifest(
            schema_version="1.0",
            run_id=run_id,
            run_root=str(base_dir),
        )
    manifest.run_root = manifest.run_root or str(base_dir)

    changed = False
    operation = str(journal.get("operation", "")).strip()
    if operation == "append_artifacts":
        for item in journal.get("items", []):
            if not isinstance(item, dict):
                continue
            try:
                ref = ArtifactRef.model_validate(item.get("ref"))
            except Exception as exc:
                logger.warning(
                    "Skipping invalid manifest journal ref for run %s: %s",
                    run_id,
                    exc,
                )
                continue
            artifact_path = resolve_artifact_path(ref, base_dir=base_dir)
            if not artifact_path.exists():
                logger.warning(
                    "Skipping missing journaled artifact for run %s: %s",
                    run_id,
                    artifact_path,
                )
                continue
            changed = _merge_manifest_ref(manifest, ref) or changed
            if ref.artifact_type == "environment_ref" and "environment_payload" in item:
                changed = (
                    _apply_environment_metadata_if_changed(
                        manifest,
                        item.get("environment_payload"),
                    )
                    or changed
                )
    elif operation == "append_audit":
        line = journal.get("record_line")
        if isinstance(line, str):
            audit_path = _ensure_audit_file(base_dir, run_id)
            if not _audit_file_has_trailing_line(audit_path, line):
                _append_audit_line(audit_path, line)
        try:
            audit_ref = ArtifactRef.model_validate(journal.get("audit_ref"))
        except Exception as exc:
            logger.warning(
                "Skipping invalid audit journal reference for run %s: %s",
                run_id,
                exc,
            )
        else:
            changed = _merge_manifest_ref(manifest, audit_ref) or changed
    else:
        logger.warning(
            "Ignoring unsupported manifest journal operation for run %s: %s",
            run_id,
            operation or "<missing>",
        )

    if changed:
        _write_manifest(base_dir, manifest)
    _clear_manifest_journal(base_dir, run_id)


def _load_manifest(base_dir: Path, run_id: str) -> RunManifest:
    _recover_manifest_journal(base_dir, run_id)
    try:
        return _load_manifest_from_disk(base_dir, run_id)
    except FileNotFoundError:
        _ensure_audit_file(base_dir, run_id)
        manifest = RunManifest(
            schema_version="1.0",
            run_id=run_id,
            run_root=str(base_dir),
            artifacts=[_audit_ref(base_dir, run_id)],
        )
        _write_manifest(base_dir, manifest)
        return manifest


def _write_manifest(base_dir: Path, manifest: RunManifest) -> Path:
    run_dir = _run_dir(base_dir, manifest.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    if manifest.run_root is None:
        manifest.run_root = str(base_dir)
    path = _manifest_path(base_dir, manifest.run_id)
    _write_text_atomic(
        path,
        fast_json_dumps(manifest.model_dump(mode="json"), sort_keys=True),
    )
    return path


def start_run(
    *,
    run_id: str | None = None,
    parent_run_id: str | None = None,
    generator: dict[str, str] | None = None,
    budgets: dict[str, float] | None = None,
    base_dir: Path = Path("runs"),
) -> RunManifest:
    """Create a new run manifest under `base_dir` and return the persisted model.

    Args:
        run_id: Optional caller-supplied run identifier. When omitted, a short
            UUID-based ID is generated.
        parent_run_id: Optional parent run for replay/resume lineage.
        generator: Optional producer metadata stored in the manifest.
        budgets: Optional budget limits copied into the new manifest.
        base_dir: Root directory where run state is stored.

    Returns:
        The initialized `RunManifest` persisted to `<base_dir>/<run_id>/manifest.json`.
    """
    run_id = run_id or str(uuid.uuid4())[:8]
    _ensure_audit_file(base_dir, run_id)
    manifest = RunManifest(
        schema_version="1.0",
        run_id=run_id,
        parent_run_id=parent_run_id,
        generator=generator or {},
        budgets=budgets or {},
        budget_usage={},
        run_root=str(base_dir),
        artifacts=[_audit_ref(base_dir, run_id)],
    )
    with _manifest_lock(_manifest_path(base_dir, run_id)):
        _write_manifest(base_dir, manifest)
    return manifest


def _write_artifact_file(
    *,
    run_id: str,
    artifact_type: str,
    payload: Any,
    media_type: str,
    filename: str | None,
    base_dir: Path,
) -> ArtifactRef:
    safe_artifact_type = _safe_path_component(artifact_type, field_name="artifact_type")
    run_dir = _run_dir(base_dir, run_id)
    artifact_dir = run_dir / "artifacts" / safe_artifact_type
    artifact_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".json" if media_type == "application/json" else ".txt"
    safe_name = (
        _safe_artifact_filename(filename)
        if filename is not None
        else (
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}_{safe_artifact_type}{suffix}"
        )
    )
    path = artifact_dir / safe_name
    _ensure_path_within(path, run_dir)

    if media_type == "application/json":
        _write_text_atomic(path, fast_json_dumps(payload, sort_keys=False))
    else:
        _write_text_atomic(path, str(payload))

    rel_path = path.relative_to(base_dir)
    return ArtifactRef(
        artifact_type=safe_artifact_type,
        path=str(rel_path),
        relative_path=str(rel_path),
        media_type=media_type,
    )


def _apply_environment_ref_metadata(manifest: RunManifest, payload: Any) -> None:
    try:
        payload_dict = payload if isinstance(payload, dict) else {}
        env_payload = payload_dict.get("environment_ref", payload)
        manifest.environment_ref = EnvironmentManifestRef.model_validate(env_payload)
        fingerprint = payload_dict.get("fingerprint")
        if isinstance(fingerprint, str):
            manifest.environment_fingerprint = fingerprint
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug("Failed to process environment_ref in artifact metadata: %s", exc)


def log_artifact(
    *,
    run_id: str,
    artifact_type: str,
    payload: Any,
    media_type: str = "application/json",
    schema_version: str | None = None,
    step: str | None = None,
    filename: str | None = None,
    base_dir: Path = Path("runs"),
) -> ArtifactRef:
    """Write a run-local artifact file and append its reference to the manifest.

    Raises:
        OSError: If the artifact directory or file cannot be created.
        ValueError: If `environment_ref` payload metadata is malformed.
    """
    entry = RuntimeArtifactWrite(
        artifact_type=artifact_type,
        payload=payload,
        media_type=media_type,
        schema_version=schema_version,
        step=step,
        filename=filename,
    )
    return log_artifacts(run_id=run_id, entries=[entry], base_dir=base_dir)[0]


def log_artifacts(
    *,
    run_id: str,
    entries: Iterable[RuntimeArtifactWrite],
    base_dir: Path = Path("runs"),
) -> list[ArtifactRef]:
    """Write many run-local artifacts while loading/writing the manifest once."""
    manifest_path = _manifest_path(base_dir, run_id)
    refs: list[ArtifactRef] = []
    journal_items: list[dict[str, Any]] = []
    with _manifest_lock(manifest_path):
        manifest = _load_manifest(base_dir, run_id)
        manifest.run_root = manifest.run_root or str(base_dir)
        for entry in entries:
            ref = _write_artifact_file(
                run_id=run_id,
                artifact_type=entry.artifact_type,
                payload=entry.payload,
                media_type=entry.media_type,
                filename=entry.filename,
                base_dir=base_dir,
            ).model_copy(
                update={
                    "schema_version": entry.schema_version,
                    "step": entry.step,
                }
            )
            refs.append(ref)
            journal_item: dict[str, Any] = {
                "ref": ref.model_dump(mode="json"),
            }
            if ref.artifact_type == "environment_ref":
                journal_item["environment_payload"] = entry.payload
            journal_items.append(journal_item)
        if journal_items:
            _write_manifest_journal(
                base_dir,
                run_id,
                {
                    "operation": "append_artifacts",
                    "items": journal_items,
                },
            )
        for item in journal_items:
            ref = ArtifactRef.model_validate(item["ref"])
            _merge_manifest_ref(manifest, ref)
            if ref.artifact_type == "environment_ref":
                _apply_environment_ref_metadata(manifest, item.get("environment_payload"))
        if journal_items:
            _write_manifest(base_dir, manifest)
            _clear_manifest_journal(base_dir, run_id)
    return refs


def append_audit(
    *,
    run_id: str,
    record: dict[str, Any],
    base_dir: Path = Path("runs"),
) -> None:
    """Append one JSONL audit record and ensure the manifest references the audit trail."""
    manifest_path = _manifest_path(base_dir, run_id)
    with _manifest_lock(manifest_path):
        manifest = _load_manifest(base_dir, run_id)
        audit_ref = _audit_ref(base_dir, run_id)
        record_line = fast_json_dumps(record, sort_keys=False) + "\n"
        _write_manifest_journal(
            base_dir,
            run_id,
            {
                "operation": "append_audit",
                "audit_ref": audit_ref.model_dump(mode="json"),
                "record_line": record_line,
            },
        )
        audit_path = _ensure_audit_file(base_dir, run_id)
        _append_audit_line(audit_path, record_line)

        if _merge_manifest_ref(manifest, audit_ref):
            _write_manifest(base_dir, manifest)
        _clear_manifest_journal(base_dir, run_id)


def update_budget_usage(
    *,
    run_id: str,
    budget_usage: dict[str, float],
    base_dir: Path = Path("runs"),
) -> None:
    """Update budget usage helper."""
    with _manifest_lock(_manifest_path(base_dir, run_id)):
        manifest = _load_manifest(base_dir, run_id)
        manifest.budget_usage = dict(budget_usage)
        _write_manifest(base_dir, manifest)


def finalize_run(
    *,
    run_id: str,
    status: str,
    pruning_reason: dict[str, Any] | None = None,
    base_dir: Path = Path("runs"),
) -> None:
    """Mark the run terminal, persist finish time, and store an optional pruning reason."""
    with _manifest_lock(_manifest_path(base_dir, run_id)):
        manifest = _load_manifest(base_dir, run_id)
        manifest.status = status
        manifest.finished_at = datetime.now(UTC).isoformat()
        manifest.pruning_reason = pruning_reason
        _write_manifest(base_dir, manifest)


def resolve_artifact_path(
    ref: ArtifactRef,
    *,
    base_dir: Path = Path("runs"),
    run_root: Path | None = None,
    allow_absolute: bool = False,
) -> Path:
    """Resolve a run artifact reference to an absolute filesystem path.

    Resolution order:
    1. `ref.relative_path` joined with `run_root` or `base_dir`
    2. `ref.path` as-is when absolute, otherwise joined with `run_root` or
       `base_dir`

    Raises:
        ValueError: If the reference does not contain either path field.
    """
    if ref.relative_path:
        root = run_root or base_dir
        return _ensure_path_within(root / ref.relative_path, root)
    if ref.path:
        root = run_root or base_dir
        p = Path(ref.path)
        if p.is_absolute():
            if not allow_absolute:
                raise ValueError("Absolute artifact paths are not allowed by default")
            return _ensure_path_within(p, root)
        return _ensure_path_within(root / p, root)
    raise ValueError("ArtifactRef is missing path information")


def _ensure_path_within(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Resolved artifact path escapes the run root")
    return resolved_path
