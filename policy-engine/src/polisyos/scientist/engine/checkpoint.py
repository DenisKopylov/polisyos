"""Checkpoint, locking, and resume primitives for Scientist workflow execution."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import WorkflowSpec

logger = get_logger(__name__)


CHECKPOINT_KIND = "scientist.checkpoint"
CHECKPOINT_SCHEMA_VERSION = "1.0"
CHECKPOINT_HEAD_FILENAME = "checkpoint_head.json"
RUN_LOCK_FILENAME = "run.lock"

CheckpointPolicy = Literal["off", "strict", "best_effort"]


class CheckpointError(PolicyOSError):
    """Base class for checkpoint/resume errors."""

    default_stage = "scientist.checkpoint"
    default_category = ErrorCategory.FATAL


class CheckpointNotFoundError(CheckpointError):
    """No checkpoint exists for a run_id."""

    default_category = ErrorCategory.TRANSIENT


class CheckpointCorruptedError(CheckpointError):
    """Checkpoint payload failed integrity or validation checks."""

    default_category = ErrorCategory.FATAL


class WorkflowMismatchError(CheckpointError):
    """Current workflow is incompatible with checkpoint metadata."""

    default_category = ErrorCategory.VALIDATION


class RunLockError(CheckpointError):
    """Run lock acquisition/release failed."""

    default_category = ErrorCategory.TRANSIENT


class CheckpointSchemaError(CheckpointCorruptedError):
    """Checkpoint schema version is incompatible with current engine."""


class CheckpointMetadata(BaseModel):
    """Replay metadata recorded after a node commits a recoverable workflow transition."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(CHECKPOINT_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    run_id: str
    sequence_number: int = Field(ge=0)
    completed_node_alias: str
    completed_node_id: str
    completed_nodes: list[str] = Field(default_factory=list)
    workflow_id: str
    workflow_fingerprint: str = Field(min_length=64, max_length=64)
    fsm_phase: str
    cache_entry_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    writer_pid: int = Field(default_factory=os.getpid, ge=1)
    writer_hostname: str = Field(default_factory=socket.gethostname)
    trace_id: str | None = None
    span_id: str | None = None


class CheckpointArtifact(BaseModel):
    """Checkpoint artifact public type."""
    model_config = ConfigDict(extra="forbid")

    metadata: CheckpointMetadata
    state: dict[str, Any]


class CheckpointHead(BaseModel):
    """Checkpoint head public type."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    checkpoint_ref: ArtifactRef
    sequence_number: int = Field(ge=0)
    node_alias: str
    writer_pid: int = Field(ge=1)
    writer_hostname: str
    updated_at: datetime


@dataclass(frozen=True)
class CheckpointWriteResult:
    """Summary of a checkpoint write, including the persisted artifact ref and latency."""
    checkpoint_ref: ArtifactRef
    sequence_number: int
    duration_ms: int


class CheckpointHook(Protocol):
    """Checkpoint hook public type."""
    def on_node_complete(
        self,
        *,
        state: ExperimentState,
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow_id: str,
        workflow_fingerprint: str,
        cache_entry_ref: ArtifactRef | None,
    ) -> CheckpointWriteResult | None:
        ...


@dataclass
class RunLockHandle:
    """Run lock handle public type."""
    run_id: str
    path: Path
    fd: int
    metadata: dict[str, Any]

    def release(self) -> None:
        try:
            import fcntl
        except Exception as exc:  # pragma: no cover
            raise RunLockError("fcntl is unavailable on this platform") from exc

        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)


class CheckpointGCPolicy(BaseModel):
    """Garbage-collection policy for old checkpoints."""

    model_config = ConfigDict(extra="forbid")

    max_checkpoints: int = Field(default=10, ge=1, le=100)
    max_age_hours: float = Field(default=72.0, ge=1.0, le=720.0)


class CheckpointStore(Protocol):
    """Abstraction for checkpoint head persistence (local or distributed)."""

    def write_head(self, run_id: str, head: CheckpointHead) -> None: ...
    def read_head(self, run_id: str) -> CheckpointHead | None: ...


class FileSystemCheckpointStore:
    """Default :class:`CheckpointStore` backed by local filesystem."""

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def write_head(self, run_id: str, head: CheckpointHead) -> None:
        update_checkpoint_head(
            self._run_dir,
            run_id=head.run_id,
            checkpoint_ref=head.checkpoint_ref,
            sequence_number=head.sequence_number,
            node_alias=head.node_alias,
            writer_pid=head.writer_pid,
            writer_hostname=head.writer_hostname,
        )

    def read_head(self, run_id: str) -> CheckpointHead | None:
        return load_checkpoint_head(self._run_dir)


def _validate_checkpoint_schema(
    checkpoint_version: str, current_version: str,
) -> None:
    """Validate that *checkpoint_version* is compatible with *current_version*."""
    try:
        cp_major, cp_minor = (int(p) for p in checkpoint_version.split("."))
        cur_major, cur_minor = (int(p) for p in current_version.split("."))
    except (ValueError, TypeError) as exc:
        raise CheckpointSchemaError(
            f"Invalid schema version format: checkpoint={checkpoint_version}, "
            f"current={current_version}",
        ) from exc

    if cp_major != cur_major:
        raise CheckpointSchemaError(
            f"Checkpoint schema {checkpoint_version} incompatible with current "
            f"{current_version} (major version mismatch)",
        )
    if cp_minor > cur_minor:
        logger.warning(
            "Checkpoint schema %s is newer than current %s; proceeding with best-effort",
            checkpoint_version,
            current_version,
        )


def gc_checkpoints(
    run_dir: Path,
    *,
    policy: CheckpointGCPolicy,
    current_head_ref: ArtifactRef | None = None,
) -> int:
    """Remove checkpoint head files exceeding *policy*.  Returns deletion count.

    Only manages files in *run_dir* that match the checkpoint head naming
    pattern.  Never deletes the checkpoint identified by *current_head_ref*.
    """
    head_path = run_dir / CHECKPOINT_HEAD_FILENAME
    if not head_path.exists():
        return 0

    # Currently only one head file exists.  This function is a placeholder
    # for future multi-checkpoint cleanup when checkpoint history is persisted.
    return 0


class CASCheckpointHook:
    """Persists checkpoints after successful node completion."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        run_dir: Path,
        sequence_start: int = 0,
        checkpoint_policy: CheckpointPolicy = "strict",
        initial_cache_entry_refs: list[ArtifactRef] | None = None,
        gc_policy: CheckpointGCPolicy | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        self._store = store
        self._run_dir = run_dir
        self._sequence = sequence_start
        self._policy = normalize_checkpoint_policy(checkpoint_policy)
        self._cache_entry_refs: list[ArtifactRef] = list(initial_cache_entry_refs or [])
        self._gc_policy = gc_policy
        self._checkpoint_store = checkpoint_store

    def on_node_complete(
        self,
        *,
        state: ExperimentState,
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow_id: str,
        workflow_fingerprint: str,
        cache_entry_ref: ArtifactRef | None,
    ) -> CheckpointWriteResult | None:
        if self._policy == "off":
            return None

        if cache_entry_ref is not None and cache_entry_ref.kind == "scientist.node_cache_entry":
            self._cache_entry_refs.append(cache_entry_ref)

        sequence_number = self._sequence
        try:
            checkpoint_ref, duration_ms = create_checkpoint(
                self._store,
                state,
                sequence_number=sequence_number,
                completed_node_alias=alias,
                completed_node_id=node_id,
                completed_nodes=list(completed_nodes),
                workflow_id=workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                fsm_phase=str(state.params.get("phase", "UNKNOWN")),
                cache_entry_refs=list(self._cache_entry_refs),
            )
            update_checkpoint_head(
                self._run_dir,
                run_id=state.run_id,
                checkpoint_ref=checkpoint_ref,
                sequence_number=sequence_number,
                node_alias=alias,
                writer_pid=os.getpid(),
                writer_hostname=socket.gethostname(),
            )
            self._sequence += 1
            return CheckpointWriteResult(
                checkpoint_ref=checkpoint_ref,
                sequence_number=sequence_number,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            if self._policy == "best_effort":
                logger.debug(
                    "Checkpoint write failed (best_effort): %s", exc,
                )
                return None
            raise


def normalize_checkpoint_policy(value: str | None) -> CheckpointPolicy:
    """Normalize user-facing checkpoint policy strings into engine-supported literals."""
    raw = (value or "strict").strip().lower()
    if raw not in {"off", "strict", "best_effort"}:
        raise ValueError("checkpoint_policy must be one of: off, strict, best_effort")
    return raw  # type: ignore[return-value]


def compute_workflow_fingerprint(workflow: WorkflowSpec) -> str:
    """Hash the functional workflow shape used to validate checkpoint compatibility."""
    payload = workflow.model_dump(mode="python", by_alias=True, exclude_none=False)
    # Exclude operational fields (retry, timeout_s) from fingerprint —
    # they don't affect functional outputs and contain floats that violate
    # canonical JSON's forbid_floats constraint.
    for node in payload.get("nodes", []):
        node.pop("retry", None)
        node.pop("timeout_s", None)
    canonical = to_canonical_bytes(payload)
    return content_hash(canonical)


def _checkpoint_payload(
    state: ExperimentState,
    *,
    sequence_number: int,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow_id: str,
    workflow_fingerprint: str,
    fsm_phase: str,
    cache_entry_refs: list[ArtifactRef],
) -> CheckpointArtifact:
    return CheckpointArtifact(
        metadata=CheckpointMetadata(
            run_id=state.run_id,
            sequence_number=sequence_number,
            completed_node_alias=completed_node_alias,
            completed_node_id=completed_node_id,
            completed_nodes=completed_nodes,
            workflow_id=workflow_id,
            workflow_fingerprint=workflow_fingerprint,
            fsm_phase=fsm_phase,
            cache_entry_refs=cache_entry_refs,
        ),
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
    )


def create_checkpoint(
    store: ArtifactStore,
    state: ExperimentState,
    *,
    sequence_number: int,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow_id: str,
    workflow_fingerprint: str,
    fsm_phase: str,
    cache_entry_refs: list[ArtifactRef],
) -> tuple[ArtifactRef, int]:
    """Create checkpoint."""
    t0 = time.perf_counter()
    checkpoint = _checkpoint_payload(
        state,
        sequence_number=sequence_number,
        completed_node_alias=completed_node_alias,
        completed_node_id=completed_node_id,
        completed_nodes=completed_nodes,
        workflow_id=workflow_id,
        workflow_fingerprint=workflow_fingerprint,
        fsm_phase=fsm_phase,
        cache_entry_refs=cache_entry_refs,
    )
    ref = store.put_json(
        checkpoint.model_dump(mode="python", by_alias=True, exclude_none=False),
        PutOptions(
            kind=CHECKPOINT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.checkpoint.CheckpointArtifact",
                version=CHECKPOINT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return ref, duration_ms


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def update_checkpoint_head(
    run_dir: Path,
    *,
    run_id: str,
    checkpoint_ref: ArtifactRef,
    sequence_number: int,
    node_alias: str,
    writer_pid: int,
    writer_hostname: str,
) -> None:
    """Atomically rewrite the local checkpoint head pointer for the latest completed node."""
    run_dir.mkdir(parents=True, exist_ok=True)
    head = CheckpointHead(
        run_id=run_id,
        checkpoint_ref=checkpoint_ref,
        sequence_number=sequence_number,
        node_alias=node_alias,
        writer_pid=writer_pid,
        writer_hostname=writer_hostname,
        updated_at=datetime.now(timezone.utc),
    )

    head_path = run_dir / CHECKPOINT_HEAD_FILENAME
    payload = head.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(prefix=".checkpoint_head_", suffix=".tmp", dir=str(run_dir))
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(tmp_path, str(head_path))
    _fsync_dir(run_dir)


def load_checkpoint_head(run_dir: Path) -> CheckpointHead | None:
    """Load checkpoint head."""
    head_path = run_dir / CHECKPOINT_HEAD_FILENAME
    if not head_path.exists():
        return None
    raw = json.loads(head_path.read_text(encoding="utf-8"))
    return CheckpointHead.model_validate(raw)


def load_checkpoint(store: ArtifactStore, checkpoint_ref: ArtifactRef) -> CheckpointArtifact:
    """Load checkpoint."""
    raw = store.get_bytes(checkpoint_ref.artifact_id)
    payload = from_canonical_bytes(raw)
    return CheckpointArtifact.model_validate(payload)


def resolve_latest_checkpoint(
    store: ArtifactStore,
    run_id: str,
    *,
    run_dir: Path | None = None,
) -> tuple[CheckpointHead, CheckpointArtifact] | None:
    """Resolve latest checkpoint."""
    if run_dir is None:
        run_dir = getattr(store, "root", Path(".")) / "runs" / run_id
    head = load_checkpoint_head(run_dir)
    if head is None:
        return None

    verification = store.verify(head.checkpoint_ref.artifact_id)
    if not verification.ok:
        raise CheckpointCorruptedError(
            f"checkpoint artifact failed integrity verification: {verification.error}"
        )

    try:
        checkpoint = load_checkpoint(store, head.checkpoint_ref)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CheckpointCorruptedError(
            f"checkpoint artifact payload is invalid: {exc}"
        ) from exc
    if checkpoint.metadata.run_id != run_id:
        raise CheckpointCorruptedError(
            f"checkpoint run_id mismatch: expected={run_id} got={checkpoint.metadata.run_id}"
        )
    if checkpoint.metadata.sequence_number != head.sequence_number:
        raise CheckpointCorruptedError(
            "checkpoint sequence mismatch between checkpoint_head.json and artifact"
        )
    return head, checkpoint


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_run_lock(
    run_dir: Path,
    *,
    run_id: str,
    mode: str,
    force: bool = False,
    max_attempts: int = 1,
    retry_delay_s: float = 1.0,
) -> RunLockHandle:
    """Acquire the per-run filesystem lock that prevents concurrent execute or resume workers."""
    try:
        import fcntl
    except Exception as exc:  # pragma: no cover
        raise RunLockError("fcntl is unavailable on this platform") from exc

    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / RUN_LOCK_FILENAME

    last_exc: Exception | None = None
    for attempt in range(max(1, max_attempts)):
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            last_exc = exc
            current = read_run_lock_metadata(lock_path)
            if force and current is not None:
                same_host = current.get("hostname") == socket.gethostname()
                stale = same_host and isinstance(current.get("pid"), int) and not _pid_exists(int(current["pid"]))
                if stale:
                    pass
            os.close(fd)
            if attempt < max_attempts - 1:
                delay = retry_delay_s * (2 ** attempt)
                logger.info(
                    "Lock for run %s held; retrying in %.1fs (attempt %d/%d)",
                    run_id, delay, attempt + 1, max_attempts,
                )
                time.sleep(delay)
                continue
            holder = ""
            if current:
                holder = (
                    f" holder_pid={current.get('pid')}"
                    f" holder_host={current.get('hostname')}"
                    f" holder_mode={current.get('mode')}"
                )
            raise RunLockError(f"run {run_id} is already active.{holder}") from exc
        else:
            # Lock acquired
            break
    else:
        raise RunLockError(  # pragma: no cover
            f"Failed to acquire lock after {max_attempts} attempts",
        )

    metadata = {
        "run_id": run_id,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, json.dumps(metadata, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    os.fsync(fd)

    return RunLockHandle(run_id=run_id, path=lock_path, fd=fd, metadata=metadata)


def read_run_lock_metadata(lock_path: Path) -> dict[str, Any] | None:
    """Read best-effort metadata describing the process currently holding a run lock."""
    if not lock_path.exists():
        return None
    try:
        raw = lock_path.read_text("utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def resume_from_checkpoint(
    store: ArtifactStore,
    run_id: str,
    *,
    workflow: WorkflowSpec | None = None,
    registry: Any | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    run_dir: Path | None = None,
):
    # Local imports avoid circular dependency at module import time.
    """Resume a run from its latest checkpoint after lock, schema, and workflow checks."""
    from polisyos.scientist.engine.executor import WorkflowExecutor
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_REGISTRY_BUNDLE_REF
    from polisyos.scientist.workflows.builder import (
        build_default_registry,
        build_execution_context,
        build_registry_with_builtin_nodes,
    )
    from polisyos.scientist.workflows.default import default_workflow_spec


    policy = normalize_checkpoint_policy(checkpoint_policy)
    if run_dir is None:
        run_dir = getattr(store, "root", Path(".")) / "runs" / run_id
    lock = acquire_run_lock(run_dir, run_id=run_id, mode="resume", force=force_lock)
    try:
        resolved = resolve_latest_checkpoint(store, run_id, run_dir=run_dir)
        if resolved is None:
            raise CheckpointNotFoundError(f"no checkpoint found for run_id={run_id}")
        head, checkpoint = resolved

        _validate_checkpoint_schema(
            checkpoint.metadata.schema_version, CHECKPOINT_SCHEMA_VERSION,
        )

        restored_state = ExperimentState.model_validate(checkpoint.state)

        workflow_spec = workflow or default_workflow_spec()
        current_fingerprint = compute_workflow_fingerprint(workflow_spec)
        if checkpoint.metadata.workflow_fingerprint != current_fingerprint:
            raise WorkflowMismatchError(
                "checkpoint workflow fingerprint does not match current workflow spec"
            )

        registry_bundle_ref = registry_bundle_ref or restored_state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
        if registry_bundle_ref is None:
            registry_bundle_ref = build_default_registry(store)

        ctx = build_execution_context(
            store,
            registry_bundle_ref,
            run_id=run_id,
        )

        ctx.run.emit(
            "scientist.checkpoint",
            "CHECKPOINT_RESUMED",
            metrics={
                "resumed_from_sequence": head.sequence_number,
                "completed_nodes_count": len(checkpoint.metadata.completed_nodes),
            },
        )

        hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=head.sequence_number + 1,
            checkpoint_policy=policy,
            initial_cache_entry_refs=checkpoint.metadata.cache_entry_refs,
        )

        executor = WorkflowExecutor(
            ctx,
            registry or build_registry_with_builtin_nodes(),
            checkpoint_hook=hook,
            checkpoint_cache_seed_refs=checkpoint.metadata.cache_entry_refs,
        )
        return executor.execute(workflow_spec, restored_state)
    finally:
        lock.release()


__all__ = [
    "CHECKPOINT_HEAD_FILENAME",
    "CHECKPOINT_KIND",
    "CHECKPOINT_SCHEMA_VERSION",
    "RUN_LOCK_FILENAME",
    "CASCheckpointHook",
    "CheckpointArtifact",
    "CheckpointCorruptedError",
    "CheckpointError",
    "CheckpointGCPolicy",
    "CheckpointHead",
    "CheckpointHook",
    "CheckpointMetadata",
    "CheckpointNotFoundError",
    "CheckpointPolicy",
    "CheckpointSchemaError",
    "CheckpointStore",
    "CheckpointWriteResult",
    "FileSystemCheckpointStore",
    "RunLockError",
    "RunLockHandle",
    "WorkflowMismatchError",
    "acquire_run_lock",
    "compute_workflow_fingerprint",
    "create_checkpoint",
    "gc_checkpoints",
    "load_checkpoint",
    "load_checkpoint_head",
    "normalize_checkpoint_policy",
    "read_run_lock_metadata",
    "resolve_latest_checkpoint",
    "resume_from_checkpoint",
    "update_checkpoint_head",
]
