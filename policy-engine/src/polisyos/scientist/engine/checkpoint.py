"""Checkpoint, locking, and resume primitives for Scientist workflow execution."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    infer_artifact_store_config,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.error_semantics import emit_degraded_path

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.scientist.engine.workflow_spec import WorkflowSpec

logger = get_logger(__name__)


CHECKPOINT_KIND = "scientist.checkpoint"
CHECKPOINT_SCHEMA_VERSION = "1.1"
CHECKPOINT_HEAD_FILENAME = "checkpoint_head.json"
CHECKPOINT_HISTORY_FILENAME = "checkpoint_history.json"
RUN_LOCK_FILENAME = "run.lock"
_CHECKPOINT_OP_KEY = "__checkpoint_op__"
_CHECKPOINT_OP_CHILDREN = "children"
_CHECKPOINT_OP_VALUE = "value"
_CHECKPOINT_OP_DELETE = "delete"
_CHECKPOINT_OP_PATCH = "patch"
_CHECKPOINT_OP_REPLACE = "replace"
_NO_DIFF = object()
_CHECKPOINT_CACHE_DISABLED_NODE_IDS = frozenset(
    {
        "scientist.node_noop@1.0.0",
        "scientist.node_set_state@1.0.0",
        "scientist.node_emit_artifact@1.0.0",
        "scientist.node_enrich_knowledge@1.0.0",
        "scientist.node_enrich_knowledge@1.1.0",
    }
)
_CHECKPOINT_OPERATION_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

CheckpointPolicy = Literal["off", "strict", "best_effort"]
CheckpointResumeStrategy = Literal["require_cache_seed", "allow_replay"]
CheckpointSnapshotMode = Literal["full", "incremental"]


class CheckpointRegistry(Protocol):
    """Minimal registry contract needed by checkpoint resume flows."""

    def get(self, node_id: object) -> Any: ...


@dataclass(frozen=True)
class CheckpointResumeRequest:
    """Typed resume parameters for checkpoint recovery."""

    run_id: str
    workflow: WorkflowSpec | None = None
    registry: CheckpointRegistry | None = None
    registry_bundle_ref: ArtifactRef | None = None
    checkpoint_policy: CheckpointPolicy = "strict"
    resume_strategy: CheckpointResumeStrategy = "require_cache_seed"
    force_lock: bool = False
    run_dir: Path | None = None


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


class CheckpointMetadataConflictError(CheckpointCorruptedError):
    """Local checkpoint metadata files disagree on the latest committed state."""


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
    snapshot_mode: CheckpointSnapshotMode = "full"
    changed_paths: list[str] = Field(default_factory=list)
    chain_depth: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    writer_pid: int = Field(default_factory=os.getpid, ge=1)
    writer_hostname: str = Field(default_factory=socket.gethostname)
    trace_id: str | None = None
    span_id: str | None = None
    research_dag_ref: ArtifactRef | None = None


class CheckpointArtifact(BaseModel):
    """Checkpoint artifact public type."""

    model_config = ConfigDict(extra="forbid")

    metadata: CheckpointMetadata
    state: dict[str, Any] | None = None
    base_checkpoint_ref: ArtifactRef | None = None
    state_delta: dict[str, Any] | None = None


def checkpoint_research_dag_status(research_dag_ref: ArtifactRef | str | None) -> str:
    """Return checkpoint rendering status for runs created before Phase 1.2."""

    return "available" if research_dag_ref is not None else "legacy_missing"


class CheckpointHead(BaseModel):
    """Checkpoint head public type."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    checkpoint_ref: ArtifactRef
    sequence_number: int = Field(ge=0)
    node_alias: str
    snapshot_mode: CheckpointSnapshotMode = "full"
    base_checkpoint_ref: ArtifactRef | None = None
    chain_depth: int = Field(default=0, ge=0)
    writer_pid: int = Field(ge=1)
    writer_hostname: str
    updated_at: datetime


class CheckpointHistoryEntry(BaseModel):
    """One retained checkpoint pointer kept for local GC and diagnostics."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    checkpoint_ref: ArtifactRef
    sequence_number: int = Field(ge=0)
    node_alias: str
    snapshot_mode: CheckpointSnapshotMode = "full"
    base_checkpoint_ref: ArtifactRef | None = None
    chain_depth: int = Field(default=0, ge=0)
    writer_pid: int = Field(ge=1)
    writer_hostname: str
    updated_at: datetime


class CheckpointHistory(BaseModel):
    """Serializable history of local checkpoint heads."""

    model_config = ConfigDict(extra="forbid")

    entries: list[CheckpointHistoryEntry] = Field(default_factory=list)


@dataclass(frozen=True)
class CheckpointWriteResult:
    """Summary of a checkpoint write, including the persisted artifact ref and latency."""

    checkpoint_ref: ArtifactRef
    sequence_number: int
    duration_ms: int
    snapshot_mode: CheckpointSnapshotMode
    base_checkpoint_ref: ArtifactRef | None = None
    chain_depth: int = 0
    changed_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreatedCheckpoint:
    """Detailed checkpoint write result used internally by checkpoint hooks."""

    checkpoint_ref: ArtifactRef
    duration_ms: int
    snapshot_mode: CheckpointSnapshotMode
    base_checkpoint_ref: ArtifactRef | None
    chain_depth: int
    changed_paths: tuple[str, ...]


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
    ) -> CheckpointWriteResult | None: ...


class AsyncCheckpointHook(Protocol):
    """Async checkpoint hook contract for non-blocking executor integrations."""

    async def on_node_complete_async(
        self,
        *,
        state: ExperimentState,
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow_id: str,
        workflow_fingerprint: str,
        cache_entry_ref: ArtifactRef | None,
    ) -> CheckpointWriteResult | None: ...


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
        except ImportError as exc:  # pragma: no cover
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
    max_incremental_chain: int = Field(default=6, ge=1, le=100)


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
            snapshot_mode=head.snapshot_mode,
            base_checkpoint_ref=head.base_checkpoint_ref,
            chain_depth=head.chain_depth,
            writer_pid=head.writer_pid,
            writer_hostname=head.writer_hostname,
        )

    def read_head(self, run_id: str) -> CheckpointHead | None:
        return load_checkpoint_head(self._run_dir)


def _validate_checkpoint_schema(
    checkpoint_version: str,
    current_version: str,
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


def _replace_op(value: Any) -> dict[str, Any]:
    return {
        _CHECKPOINT_OP_KEY: _CHECKPOINT_OP_REPLACE,
        _CHECKPOINT_OP_VALUE: deepcopy(value),
    }


def _delete_op() -> dict[str, str]:
    return {_CHECKPOINT_OP_KEY: _CHECKPOINT_OP_DELETE}


def _patch_op(children: dict[str, Any]) -> dict[str, Any]:
    return {
        _CHECKPOINT_OP_KEY: _CHECKPOINT_OP_PATCH,
        _CHECKPOINT_OP_CHILDREN: children,
    }


def _is_checkpoint_op(value: Any, kind: str) -> bool:
    return isinstance(value, dict) and value.get(_CHECKPOINT_OP_KEY) == kind


def _build_state_delta(
    previous: Any, current: Any
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    delta, changed_paths = _diff_checkpoint_value(previous, current, path="")
    if delta is _NO_DIFF:
        return None, ()
    if not isinstance(delta, dict):
        raise CheckpointCorruptedError("checkpoint diff root must be a structured op")
    return delta, tuple(changed_paths)


def _diff_checkpoint_value(previous: Any, current: Any, *, path: str) -> tuple[Any, list[str]]:
    if isinstance(previous, dict) and isinstance(current, dict):
        children: dict[str, Any] = {}
        changed_paths: list[str] = []
        for key in sorted(set(previous) | set(current)):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in current:
                children[key] = _delete_op()
                changed_paths.append(child_path)
                continue
            if key not in previous:
                children[key] = _replace_op(current[key])
                changed_paths.append(child_path)
                continue
            child_delta, child_changed = _diff_checkpoint_value(
                previous[key], current[key], path=child_path
            )
            if child_delta is _NO_DIFF:
                continue
            children[key] = child_delta
            changed_paths.extend(child_changed)
        if not children:
            return _NO_DIFF, []
        return _patch_op(children), changed_paths

    if previous == current:
        return _NO_DIFF, []
    return _replace_op(current), [path or "$"]


def _apply_state_delta(base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    return _apply_checkpoint_op(base, delta, root=True)


def _apply_checkpoint_op(value: Any, op: dict[str, Any], *, root: bool = False) -> Any:
    if _is_checkpoint_op(op, _CHECKPOINT_OP_REPLACE):
        return deepcopy(op.get(_CHECKPOINT_OP_VALUE))
    if _is_checkpoint_op(op, _CHECKPOINT_OP_DELETE):
        if root:
            raise CheckpointCorruptedError("checkpoint delta cannot delete the root state")
        return _NO_DIFF
    if not _is_checkpoint_op(op, _CHECKPOINT_OP_PATCH):
        raise CheckpointCorruptedError("checkpoint delta contains an unknown op")
    if not isinstance(value, dict):
        raise CheckpointCorruptedError("checkpoint patch expected dict base state")
    children = op.get(_CHECKPOINT_OP_CHILDREN)
    if not isinstance(children, dict):
        raise CheckpointCorruptedError("checkpoint patch op is missing children")
    patched = deepcopy(value)
    for key, child_op in children.items():
        if not isinstance(child_op, dict):
            raise CheckpointCorruptedError("checkpoint child op must be a dict")
        if _is_checkpoint_op(child_op, _CHECKPOINT_OP_DELETE):
            patched.pop(key, None)
            continue
        current_child = patched.get(key)
        if _is_checkpoint_op(child_op, _CHECKPOINT_OP_PATCH) and (
            key not in patched or not isinstance(current_child, dict)
        ):
            raise CheckpointCorruptedError(f"checkpoint patch expected existing dict at {key!r}")
        new_value = _apply_checkpoint_op(current_child, child_op)
        if new_value is _NO_DIFF:
            patched.pop(key, None)
        else:
            patched[key] = new_value
    return patched


def gc_checkpoints(
    run_dir: Path,
    *,
    policy: CheckpointGCPolicy,
    current_head_ref: ArtifactRef | None = None,
) -> int:
    """Trim local checkpoint history exceeding *policy* and return deletion count."""
    history = load_checkpoint_history(run_dir)
    if history is None or not history.entries:
        return 0

    cutoff = datetime.now(UTC) - timedelta(hours=float(policy.max_age_hours))
    keep_ref_id = str(current_head_ref.artifact_id) if current_head_ref is not None else None

    entry_by_ref = {str(entry.checkpoint_ref.artifact_id): entry for entry in history.entries}

    retained: list[CheckpointHistoryEntry] = []
    retained_non_head = 0
    for entry in sorted(
        history.entries,
        key=lambda item: (item.updated_at, item.sequence_number),
        reverse=True,
    ):
        entry_ref_id = str(entry.checkpoint_ref.artifact_id)
        must_keep = keep_ref_id is not None and entry_ref_id == keep_ref_id
        within_age = entry.updated_at >= cutoff
        within_count = retained_non_head < policy.max_checkpoints
        if must_keep or (within_age and within_count):
            retained.append(entry)
            if not must_keep:
                retained_non_head += 1

    retained_ids = {str(entry.checkpoint_ref.artifact_id) for entry in retained}
    pending_ids = list(retained_ids)
    while pending_ids:
        current_id = pending_ids.pop()
        current_entry = entry_by_ref.get(current_id)
        if current_entry is None or current_entry.base_checkpoint_ref is None:
            continue
        base_id = str(current_entry.base_checkpoint_ref.artifact_id)
        if base_id in retained_ids:
            continue
        base_entry = entry_by_ref.get(base_id)
        if base_entry is None:
            continue
        retained.append(base_entry)
        retained_ids.add(base_id)
        pending_ids.append(base_id)

    retained.sort(key=lambda item: (item.updated_at, item.sequence_number))
    removed = len(history.entries) - len(retained)
    if removed <= 0:
        return 0
    write_checkpoint_history(run_dir, CheckpointHistory(entries=retained))
    return removed


class CASCheckpointHook:
    """Persists checkpoints after successful node completion."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        run_dir: Path,
        store_config: ArtifactStoreConfig | None = None,
        sequence_start: int = 0,
        checkpoint_policy: CheckpointPolicy = "strict",
        initial_cache_entry_refs: list[ArtifactRef] | None = None,
        initial_completed_nodes: list[str] | None = None,
        gc_policy: CheckpointGCPolicy | None = None,
        checkpoint_store: CheckpointStore | None = None,
        initial_checkpoint_ref: ArtifactRef | None = None,
        initial_state: dict[str, Any] | None = None,
        initial_chain_depth: int = 0,
    ) -> None:
        self._store = store
        self._store_config = store_config or infer_artifact_store_config(store)
        self._async_store = ensure_async_artifact_store(store)
        self._run_dir = run_dir
        self._sequence = sequence_start
        self._policy = normalize_checkpoint_policy(checkpoint_policy)
        self._cache_entry_refs: list[ArtifactRef] = list(initial_cache_entry_refs or [])
        self._completed_nodes: list[str] = _dedupe_aliases(initial_completed_nodes or [])
        self._gc_policy = gc_policy or CheckpointGCPolicy()
        self._checkpoint_store = checkpoint_store
        self._previous_checkpoint_ref = initial_checkpoint_ref
        self._previous_state = deepcopy(initial_state) if initial_state is not None else None
        self._previous_chain_depth = max(0, int(initial_chain_depth))

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
        current_state = state.model_dump(mode="python", by_alias=True, exclude_none=False)
        merged_completed_nodes = _dedupe_aliases([*self._completed_nodes, *completed_nodes])
        try:
            created = create_checkpoint(
                self._store,
                run_id=state.run_id,
                state=current_state,
                sequence_number=sequence_number,
                completed_node_alias=alias,
                completed_node_id=node_id,
                completed_nodes=merged_completed_nodes,
                workflow_id=workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                fsm_phase=str(state.params.get("phase", "UNKNOWN")),
                cache_entry_refs=list(self._cache_entry_refs),
                previous_state=self._previous_state,
                previous_checkpoint_ref=self._previous_checkpoint_ref,
                previous_chain_depth=self._previous_chain_depth,
                max_incremental_chain=self._gc_policy.max_incremental_chain,
            )
            update_checkpoint_head(
                self._run_dir,
                run_id=state.run_id,
                checkpoint_ref=created.checkpoint_ref,
                sequence_number=sequence_number,
                node_alias=alias,
                snapshot_mode=created.snapshot_mode,
                base_checkpoint_ref=created.base_checkpoint_ref,
                chain_depth=created.chain_depth,
                writer_pid=os.getpid(),
                writer_hostname=socket.gethostname(),
            )
            self._previous_checkpoint_ref = created.checkpoint_ref
            self._previous_state = deepcopy(current_state)
            self._previous_chain_depth = created.chain_depth
            self._completed_nodes = list(merged_completed_nodes)
            self._sequence += 1
            result = CheckpointWriteResult(
                checkpoint_ref=created.checkpoint_ref,
                sequence_number=sequence_number,
                duration_ms=created.duration_ms,
                snapshot_mode=created.snapshot_mode,
                base_checkpoint_ref=created.base_checkpoint_ref,
                chain_depth=created.chain_depth,
                changed_paths=created.changed_paths,
            )
        except (*_CHECKPOINT_OPERATION_ERRORS, CheckpointError) as exc:
            if self._policy == "best_effort":
                emit_degraded_path(
                    component="scientist.checkpoint",
                    operation="write_checkpoint",
                    reason="best_effort_checkpoint_write_failed",
                    exc=exc,
                    retryable=True,
                    details={
                        "run_id": state.run_id,
                        "alias": alias,
                        "node_id": node_id,
                        "sequence_number": sequence_number,
                    },
                    log=logger,
                )
                return None
            raise
        if self._gc_policy is not None:
            try:
                gc_checkpoints(
                    self._run_dir,
                    policy=self._gc_policy,
                    current_head_ref=result.checkpoint_ref,
                )
            except (*_CHECKPOINT_OPERATION_ERRORS, CheckpointError) as exc:
                emit_degraded_path(
                    component="scientist.checkpoint",
                    operation="gc_checkpoints",
                    reason="checkpoint_gc_failed",
                    exc=exc,
                    retryable=True,
                    details={
                        "run_id": state.run_id,
                        "sequence_number": sequence_number,
                        "checkpoint_ref": str(result.checkpoint_ref.artifact_id),
                    },
                    log=logger,
                )
        return result

    async def on_node_complete_async(
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
        current_state = state.model_dump(mode="python", by_alias=True, exclude_none=False)
        merged_completed_nodes = _dedupe_aliases([*self._completed_nodes, *completed_nodes])
        try:
            created = await create_checkpoint_async(
                self._async_store,
                run_id=state.run_id,
                state=current_state,
                sequence_number=sequence_number,
                completed_node_alias=alias,
                completed_node_id=node_id,
                completed_nodes=merged_completed_nodes,
                workflow_id=workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                fsm_phase=str(state.params.get("phase", "UNKNOWN")),
                cache_entry_refs=list(self._cache_entry_refs),
                previous_state=self._previous_state,
                previous_checkpoint_ref=self._previous_checkpoint_ref,
                previous_chain_depth=self._previous_chain_depth,
                max_incremental_chain=self._gc_policy.max_incremental_chain,
            )
            await run_blocking_async(
                update_checkpoint_head,
                self._run_dir,
                run_id=state.run_id,
                checkpoint_ref=created.checkpoint_ref,
                sequence_number=sequence_number,
                node_alias=alias,
                snapshot_mode=created.snapshot_mode,
                base_checkpoint_ref=created.base_checkpoint_ref,
                chain_depth=created.chain_depth,
                writer_pid=os.getpid(),
                writer_hostname=socket.gethostname(),
            )
            self._previous_checkpoint_ref = created.checkpoint_ref
            self._previous_state = deepcopy(current_state)
            self._previous_chain_depth = created.chain_depth
            self._completed_nodes = list(merged_completed_nodes)
            self._sequence += 1
            result = CheckpointWriteResult(
                checkpoint_ref=created.checkpoint_ref,
                sequence_number=sequence_number,
                duration_ms=created.duration_ms,
                snapshot_mode=created.snapshot_mode,
                base_checkpoint_ref=created.base_checkpoint_ref,
                chain_depth=created.chain_depth,
                changed_paths=created.changed_paths,
            )
        except (*_CHECKPOINT_OPERATION_ERRORS, CheckpointError, TimeoutError) as exc:
            if self._policy == "best_effort":
                emit_degraded_path(
                    component="scientist.checkpoint",
                    operation="write_checkpoint_async",
                    reason="best_effort_checkpoint_write_failed",
                    exc=exc,
                    retryable=True,
                    details={
                        "run_id": state.run_id,
                        "alias": alias,
                        "node_id": node_id,
                        "sequence_number": sequence_number,
                    },
                    log=logger,
                )
                return None
            raise
        if self._gc_policy is not None:
            try:
                await run_blocking_async(
                    gc_checkpoints,
                    self._run_dir,
                    policy=self._gc_policy,
                    current_head_ref=result.checkpoint_ref,
                )
            except (*_CHECKPOINT_OPERATION_ERRORS, CheckpointError, TimeoutError) as exc:
                emit_degraded_path(
                    component="scientist.checkpoint",
                    operation="gc_checkpoints_async",
                    reason="checkpoint_gc_failed",
                    exc=exc,
                    retryable=True,
                    details={
                        "run_id": state.run_id,
                        "sequence_number": sequence_number,
                        "checkpoint_ref": str(result.checkpoint_ref.artifact_id),
                    },
                    log=logger,
                )
        return result

    def export_runtime_metadata(self) -> dict[str, Any] | None:
        """Return serializable metadata needed to reconstruct this hook remotely."""
        if self._store_config is None:
            return None
        metadata: dict[str, Any] = {
            "store_config": self._store_config.model_dump(mode="json"),
        }
        if self._store_config.backend == "filesystem" and self._store_config.root:
            metadata.update(
                {
                    "store_backend": "filesystem",
                    "store_root": self._store_config.root,
                }
            )
        return {
            **metadata,
            "run_dir": str(self._run_dir),
            "sequence_start": self._sequence,
            "checkpoint_policy": self._policy,
            "cache_entry_refs": [ref.model_dump(mode="json") for ref in self._cache_entry_refs],
            "completed_nodes": list(self._completed_nodes),
            "gc_policy": self._gc_policy.model_dump(mode="json"),
            "previous_checkpoint_ref": (
                self._previous_checkpoint_ref.model_dump(mode="json")
                if self._previous_checkpoint_ref is not None
                else None
            ),
            "previous_state": deepcopy(self._previous_state),
            "previous_chain_depth": self._previous_chain_depth,
        }


def serialize_checkpoint_hook_runtime_metadata(
    checkpoint_hook: CheckpointHook | Any | None,
) -> dict[str, Any] | None:
    """Serialize a checkpoint hook for distributed execution when supported."""
    if checkpoint_hook is None:
        return None
    exporter = getattr(checkpoint_hook, "export_runtime_metadata", None)
    if not callable(exporter):
        return None
    metadata = exporter()
    return metadata if isinstance(metadata, dict) else None


def restore_checkpoint_hook_from_runtime_metadata(
    metadata: dict[str, Any] | None,
) -> CASCheckpointHook | None:
    """Reconstruct a CAS checkpoint hook from serialized runtime metadata."""
    if not isinstance(metadata, dict):
        return None

    run_dir = metadata.get("run_dir")
    if not isinstance(run_dir, str) or not run_dir.strip():
        return None

    store_config_raw = metadata.get("store_config")
    store_config: ArtifactStoreConfig | None = None
    if isinstance(store_config_raw, dict):
        try:
            store_config = ArtifactStoreConfig.model_validate(store_config_raw)
        except (ValidationError, TypeError, ValueError):
            return None
    else:
        store_root = metadata.get("store_root")
        if metadata.get("store_backend") != "filesystem":
            return None
        if not isinstance(store_root, str) or not store_root.strip():
            return None
        store_config = ArtifactStoreConfig(backend="filesystem", root=store_root)

    gc_policy_raw = metadata.get("gc_policy")
    gc_policy = (
        CheckpointGCPolicy.model_validate(gc_policy_raw)
        if isinstance(gc_policy_raw, dict)
        else CheckpointGCPolicy()
    )

    cache_entry_refs: list[ArtifactRef] = []
    for raw_ref in metadata.get("cache_entry_refs", []):
        if not isinstance(raw_ref, dict):
            continue
        cache_entry_refs.append(ArtifactRef.model_validate(raw_ref))

    previous_checkpoint_ref_raw = metadata.get("previous_checkpoint_ref")
    previous_checkpoint_ref = (
        ArtifactRef.model_validate(previous_checkpoint_ref_raw)
        if isinstance(previous_checkpoint_ref_raw, dict)
        else None
    )

    return CASCheckpointHook(
        store=build_artifact_store(store_config),
        run_dir=Path(run_dir),
        store_config=store_config,
        sequence_start=max(0, int(metadata.get("sequence_start", 0) or 0)),
        checkpoint_policy=normalize_checkpoint_policy(metadata.get("checkpoint_policy", "strict")),
        initial_cache_entry_refs=cache_entry_refs,
        initial_completed_nodes=list(metadata.get("completed_nodes", [])),
        gc_policy=gc_policy,
        initial_checkpoint_ref=previous_checkpoint_ref,
        initial_state=metadata.get("previous_state"),
        initial_chain_depth=max(0, int(metadata.get("previous_chain_depth", 0) or 0)),
    )


def normalize_checkpoint_policy(value: str | None) -> CheckpointPolicy:
    """Normalize user-facing checkpoint policy strings into engine-supported literals."""
    raw = (value or "strict").strip().lower()
    if raw not in {"off", "strict", "best_effort"}:
        raise ValueError("checkpoint_policy must be one of: off, strict, best_effort")
    return cast("CheckpointPolicy", raw)


def normalize_checkpoint_resume_strategy(value: str | None) -> CheckpointResumeStrategy:
    """Normalize checkpoint resume strategy strings."""
    raw = (value or "require_cache_seed").strip().lower()
    if raw not in {"require_cache_seed", "allow_replay"}:
        raise ValueError(
            "checkpoint resume_strategy must be one of: require_cache_seed, allow_replay"
        )
    return cast("CheckpointResumeStrategy", raw)


def _resolve_run_dir(
    *,
    store: ArtifactStore,
    run_id: str,
    run_dir: Path | None,
) -> Path:
    if run_dir is not None:
        return run_dir
    root = getattr(store, "root", None)
    if isinstance(root, Path):
        return root / "runs" / run_id
    if isinstance(root, str):
        return Path(root) / "runs" / run_id
    return Path(".") / "runs" / run_id


def _dedupe_aliases(aliases: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        ordered.append(alias)
    return ordered


def _build_resume_workflow_spec(
    workflow: WorkflowSpec,
    *,
    completed_nodes: list[str],
) -> WorkflowSpec:
    if not completed_nodes:
        return workflow
    invocation_aliases = {inv.alias for inv in workflow.nodes}
    unknown = [alias for alias in completed_nodes if alias not in invocation_aliases]
    if unknown:
        raise CheckpointCorruptedError(
            "checkpoint completed_nodes contain aliases missing from current workflow: "
            + ", ".join(sorted(unknown))
        )
    completed_set = set(completed_nodes)
    if len(completed_set) == len(invocation_aliases):
        return workflow.model_copy(update={"nodes": []})
    resumed_nodes = [
        inv.model_copy(
            update={"depends_on": [dep for dep in inv.depends_on if dep not in completed_set]}
        )
        for inv in workflow.nodes
        if inv.alias not in completed_set
    ]
    return workflow.model_copy(update={"nodes": resumed_nodes})


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
    run_id: str,
    state: dict[str, Any] | None,
    *,
    sequence_number: int,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow_id: str,
    workflow_fingerprint: str,
    fsm_phase: str,
    cache_entry_refs: list[ArtifactRef],
    snapshot_mode: CheckpointSnapshotMode,
    changed_paths: tuple[str, ...],
    chain_depth: int,
    base_checkpoint_ref: ArtifactRef | None = None,
    state_delta: dict[str, Any] | None = None,
) -> CheckpointArtifact:
    return CheckpointArtifact(
        metadata=CheckpointMetadata(
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            run_id=run_id,
            sequence_number=sequence_number,
            completed_node_alias=completed_node_alias,
            completed_node_id=completed_node_id,
            completed_nodes=completed_nodes,
            workflow_id=workflow_id,
            workflow_fingerprint=workflow_fingerprint,
            fsm_phase=fsm_phase,
            cache_entry_refs=cache_entry_refs,
            snapshot_mode=snapshot_mode,
            changed_paths=list(changed_paths),
            chain_depth=chain_depth,
        ),
        state=deepcopy(state) if state is not None else None,
        base_checkpoint_ref=base_checkpoint_ref,
        state_delta=deepcopy(state_delta) if state_delta is not None else None,
    )


def create_checkpoint(
    store: ArtifactStore,
    *,
    run_id: str,
    state: dict[str, Any],
    sequence_number: int,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow_id: str,
    workflow_fingerprint: str,
    fsm_phase: str,
    cache_entry_refs: list[ArtifactRef],
    previous_state: dict[str, Any] | None = None,
    previous_checkpoint_ref: ArtifactRef | None = None,
    previous_chain_depth: int = 0,
    max_incremental_chain: int = 6,
) -> CreatedCheckpoint:
    """Create checkpoint."""
    t0 = time.perf_counter()
    snapshot_mode: CheckpointSnapshotMode = "full"
    base_checkpoint_ref: ArtifactRef | None = None
    state_payload: dict[str, Any] | None = state
    state_delta: dict[str, Any] | None = None
    changed_paths: tuple[str, ...] = ()
    chain_depth = 0

    if (
        previous_state is not None
        and previous_checkpoint_ref is not None
        and previous_chain_depth < max(1, int(max_incremental_chain))
    ):
        state_delta, changed_paths = _build_state_delta(previous_state, state)
        if state_delta is not None:
            snapshot_mode = "incremental"
            base_checkpoint_ref = previous_checkpoint_ref
            state_payload = None
            chain_depth = previous_chain_depth + 1
        else:
            changed_paths = ()

    checkpoint = _checkpoint_payload(
        run_id,
        state_payload,
        sequence_number=sequence_number,
        completed_node_alias=completed_node_alias,
        completed_node_id=completed_node_id,
        completed_nodes=completed_nodes,
        workflow_id=workflow_id,
        workflow_fingerprint=workflow_fingerprint,
        fsm_phase=fsm_phase,
        cache_entry_refs=cache_entry_refs,
        snapshot_mode=snapshot_mode,
        changed_paths=changed_paths,
        chain_depth=chain_depth,
        base_checkpoint_ref=base_checkpoint_ref,
        state_delta=state_delta,
    )
    ref = store.put_json(
        checkpoint.model_dump(mode="python", by_alias=True, exclude_none=False),
        ArtifactWriteOptions(
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
    return CreatedCheckpoint(
        checkpoint_ref=ref,
        duration_ms=duration_ms,
        snapshot_mode=snapshot_mode,
        base_checkpoint_ref=base_checkpoint_ref,
        chain_depth=chain_depth,
        changed_paths=changed_paths,
    )


async def create_checkpoint_async(
    store: AsyncArtifactStore,
    *,
    run_id: str,
    state: dict[str, Any],
    sequence_number: int,
    completed_node_alias: str,
    completed_node_id: str,
    completed_nodes: list[str],
    workflow_id: str,
    workflow_fingerprint: str,
    fsm_phase: str,
    cache_entry_refs: list[ArtifactRef],
    previous_state: dict[str, Any] | None = None,
    previous_checkpoint_ref: ArtifactRef | None = None,
    previous_chain_depth: int = 0,
    max_incremental_chain: int = 6,
) -> CreatedCheckpoint:
    """Create a checkpoint without blocking the active event loop."""
    t0 = time.perf_counter()
    snapshot_mode: CheckpointSnapshotMode = "full"
    base_checkpoint_ref: ArtifactRef | None = None
    state_payload: dict[str, Any] | None = state
    state_delta: dict[str, Any] | None = None
    changed_paths: tuple[str, ...] = ()
    chain_depth = 0

    if (
        previous_state is not None
        and previous_checkpoint_ref is not None
        and previous_chain_depth < max(1, int(max_incremental_chain))
    ):
        state_delta, changed_paths = _build_state_delta(previous_state, state)
        if state_delta is not None:
            snapshot_mode = "incremental"
            base_checkpoint_ref = previous_checkpoint_ref
            state_payload = None
            chain_depth = previous_chain_depth + 1
        else:
            changed_paths = ()

    checkpoint = _checkpoint_payload(
        run_id,
        state_payload,
        sequence_number=sequence_number,
        completed_node_alias=completed_node_alias,
        completed_node_id=completed_node_id,
        completed_nodes=completed_nodes,
        workflow_id=workflow_id,
        workflow_fingerprint=workflow_fingerprint,
        fsm_phase=fsm_phase,
        cache_entry_refs=cache_entry_refs,
        snapshot_mode=snapshot_mode,
        changed_paths=changed_paths,
        chain_depth=chain_depth,
        base_checkpoint_ref=base_checkpoint_ref,
        state_delta=state_delta,
    )
    ref = await store.put_json(
        checkpoint.model_dump(mode="python", by_alias=True, exclude_none=False),
        ArtifactWriteOptions(
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
    return CreatedCheckpoint(
        checkpoint_ref=ref,
        duration_ms=duration_ms,
        snapshot_mode=snapshot_mode,
        base_checkpoint_ref=base_checkpoint_ref,
        chain_depth=chain_depth,
        changed_paths=changed_paths,
    )


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
    snapshot_mode: CheckpointSnapshotMode = "full",
    base_checkpoint_ref: ArtifactRef | None = None,
    chain_depth: int = 0,
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
        snapshot_mode=snapshot_mode,
        base_checkpoint_ref=base_checkpoint_ref,
        chain_depth=chain_depth,
        writer_pid=writer_pid,
        writer_hostname=writer_hostname,
        updated_at=datetime.now(UTC),
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
    append_checkpoint_history(run_dir, head)


def _history_path(run_dir: Path) -> Path:
    return run_dir / CHECKPOINT_HISTORY_FILENAME


def _load_local_checkpoint_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckpointCorruptedError(f"{label} at {path} could not be read: {exc}") from exc
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CheckpointCorruptedError(f"{label} at {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CheckpointCorruptedError(f"{label} at {path} must decode to a JSON object")
    return raw


def load_checkpoint_history(run_dir: Path) -> CheckpointHistory | None:
    """Load local checkpoint history if present."""
    history_path = _history_path(run_dir)
    if not history_path.exists():
        return None
    raw = _load_local_checkpoint_json(history_path, label="checkpoint history")
    try:
        return CheckpointHistory.model_validate(raw)
    except ValidationError as exc:
        raise CheckpointCorruptedError(
            f"checkpoint history at {history_path} failed schema validation: {exc}"
        ) from exc


def write_checkpoint_history(run_dir: Path, history: CheckpointHistory) -> None:
    """Atomically persist local checkpoint history."""
    run_dir.mkdir(parents=True, exist_ok=True)
    history_path = _history_path(run_dir)
    payload = history.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(
        prefix=".checkpoint_history_",
        suffix=".tmp",
        dir=str(run_dir),
    )
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(tmp_path, str(history_path))
    _fsync_dir(run_dir)


def append_checkpoint_history(run_dir: Path, head: CheckpointHead) -> None:
    """Append or refresh one checkpoint history entry for *head*."""
    history = load_checkpoint_history(run_dir) or CheckpointHistory()
    ref_id = str(head.checkpoint_ref.artifact_id)
    filtered = [
        entry for entry in history.entries if str(entry.checkpoint_ref.artifact_id) != ref_id
    ]
    filtered.append(
        CheckpointHistoryEntry(
            run_id=head.run_id,
            checkpoint_ref=head.checkpoint_ref,
            sequence_number=head.sequence_number,
            node_alias=head.node_alias,
            snapshot_mode=head.snapshot_mode,
            base_checkpoint_ref=head.base_checkpoint_ref,
            chain_depth=head.chain_depth,
            writer_pid=head.writer_pid,
            writer_hostname=head.writer_hostname,
            updated_at=head.updated_at,
        )
    )
    write_checkpoint_history(run_dir, CheckpointHistory(entries=filtered))


def _history_entry_from_head(head: CheckpointHead) -> CheckpointHistoryEntry:
    return CheckpointHistoryEntry(
        run_id=head.run_id,
        checkpoint_ref=head.checkpoint_ref,
        sequence_number=head.sequence_number,
        node_alias=head.node_alias,
        snapshot_mode=head.snapshot_mode,
        base_checkpoint_ref=head.base_checkpoint_ref,
        chain_depth=head.chain_depth,
        writer_pid=head.writer_pid,
        writer_hostname=head.writer_hostname,
        updated_at=head.updated_at,
    )


def _checkpoint_head_matches_history_entry(
    head: CheckpointHead,
    entry: CheckpointHistoryEntry,
) -> bool:
    return (
        head.run_id == entry.run_id
        and str(head.checkpoint_ref.artifact_id) == str(entry.checkpoint_ref.artifact_id)
        and head.sequence_number == entry.sequence_number
        and head.node_alias == entry.node_alias
        and head.snapshot_mode == entry.snapshot_mode
        and head.base_checkpoint_ref == entry.base_checkpoint_ref
        and head.chain_depth == entry.chain_depth
    )


def _checkpoint_history_entry_identity(
    entry: CheckpointHistoryEntry,
) -> tuple[str, str, str, str | None, int]:
    return (
        str(entry.checkpoint_ref.artifact_id),
        entry.node_alias,
        entry.snapshot_mode,
        None if entry.base_checkpoint_ref is None else str(entry.base_checkpoint_ref.artifact_id),
        entry.chain_depth,
    )


def _latest_history_entry(
    history: CheckpointHistory,
    *,
    run_id: str,
) -> CheckpointHistoryEntry | None:
    entries: list[CheckpointHistoryEntry] = []
    for entry in history.entries:
        if entry.run_id != run_id:
            raise CheckpointMetadataConflictError(
                "checkpoint history contains entries for a different run_id"
            )
        entries.append(entry)
    if not entries:
        return None
    max_sequence = max(entry.sequence_number for entry in entries)
    latest_entries = [entry for entry in entries if entry.sequence_number == max_sequence]
    latest_identities = {_checkpoint_history_entry_identity(entry) for entry in latest_entries}
    if len(latest_identities) > 1:
        raise CheckpointMetadataConflictError(
            "checkpoint history contains multiple conflicting latest entries"
        )
    return max(latest_entries, key=lambda item: item.updated_at)


def _checkpoint_head_artifact_mismatches(
    head: CheckpointHead,
    checkpoint: CheckpointArtifact,
) -> tuple[str, ...]:
    mismatches: list[str] = []
    if checkpoint.metadata.completed_node_alias != head.node_alias:
        mismatches.append("node_alias")
    if checkpoint.metadata.snapshot_mode != head.snapshot_mode:
        mismatches.append("snapshot_mode")
    if checkpoint.metadata.chain_depth != head.chain_depth:
        mismatches.append("chain_depth")
    head_base = (
        None if head.base_checkpoint_ref is None else str(head.base_checkpoint_ref.artifact_id)
    )
    checkpoint_base = (
        None
        if checkpoint.base_checkpoint_ref is None
        else str(checkpoint.base_checkpoint_ref.artifact_id)
    )
    if head_base != checkpoint_base:
        mismatches.append("base_checkpoint_ref")
    return tuple(mismatches)


def _reconcile_checkpoint_history(
    run_dir: Path,
    *,
    head: CheckpointHead,
) -> CheckpointHistory:
    expected_entry = _history_entry_from_head(head)
    history = load_checkpoint_history(run_dir)
    if history is None:
        repaired = CheckpointHistory(entries=[expected_entry])
        write_checkpoint_history(run_dir, repaired)
        return repaired

    latest = _latest_history_entry(history, run_id=head.run_id)
    if latest is None:
        repaired = CheckpointHistory(entries=[expected_entry])
        write_checkpoint_history(run_dir, repaired)
        return repaired

    if latest.sequence_number > head.sequence_number:
        raise CheckpointMetadataConflictError(
            "checkpoint history is newer than checkpoint_head.json; resume would use stale metadata"
        )

    if latest.sequence_number == head.sequence_number:
        if not _checkpoint_head_matches_history_entry(head, latest):
            raise CheckpointMetadataConflictError(
                "checkpoint head/history disagree on the latest committed checkpoint"
            )
        return history

    repaired_entries = [
        entry
        for entry in history.entries
        if str(entry.checkpoint_ref.artifact_id) != str(head.checkpoint_ref.artifact_id)
    ]
    repaired_entries.append(expected_entry)
    repaired = CheckpointHistory(entries=repaired_entries)
    write_checkpoint_history(run_dir, repaired)
    return repaired


def load_checkpoint_head(run_dir: Path) -> CheckpointHead | None:
    """Load checkpoint head."""
    head_path = run_dir / CHECKPOINT_HEAD_FILENAME
    if not head_path.exists():
        return None
    raw = _load_local_checkpoint_json(head_path, label="checkpoint head")
    try:
        return CheckpointHead.model_validate(raw)
    except ValidationError as exc:
        raise CheckpointCorruptedError(
            f"checkpoint head at {head_path} failed schema validation: {exc}"
        ) from exc


def load_checkpoint(store: ArtifactStore, checkpoint_ref: ArtifactRef) -> CheckpointArtifact:
    """Load checkpoint."""
    raw = store.get_bytes(checkpoint_ref.artifact_id)
    payload = from_canonical_bytes(raw)
    return CheckpointArtifact.model_validate(payload)


def materialize_checkpoint_state(
    store: ArtifactStore,
    checkpoint_ref: ArtifactRef,
    *,
    _seen_refs: set[str] | None = None,
) -> dict[str, Any]:
    """Resolve full state for a checkpoint, following any incremental chain."""

    seen_refs = set() if _seen_refs is None else _seen_refs
    ref_id = str(checkpoint_ref.artifact_id)
    if ref_id in seen_refs:
        raise CheckpointCorruptedError("checkpoint chain contains a cycle")
    seen_refs.add(ref_id)

    verification = store.verify(checkpoint_ref.artifact_id)
    if not verification.ok:
        raise CheckpointCorruptedError(
            f"checkpoint artifact failed integrity verification: {verification.error}"
        )

    try:
        checkpoint = load_checkpoint(store, checkpoint_ref)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CheckpointCorruptedError(f"checkpoint artifact payload is invalid: {exc}") from exc

    if checkpoint.metadata.snapshot_mode == "full":
        if checkpoint.state is None:
            raise CheckpointCorruptedError("full checkpoint is missing state payload")
        return deepcopy(checkpoint.state)

    if checkpoint.base_checkpoint_ref is None:
        raise CheckpointCorruptedError("incremental checkpoint is missing base_checkpoint_ref")
    if checkpoint.state_delta is None:
        raise CheckpointCorruptedError("incremental checkpoint is missing state_delta")

    base_state = materialize_checkpoint_state(
        store,
        checkpoint.base_checkpoint_ref,
        _seen_refs=seen_refs,
    )
    return _apply_state_delta(base_state, checkpoint.state_delta)


def resolve_latest_checkpoint(
    store: ArtifactStore,
    run_id: str,
    *,
    run_dir: Path | None = None,
) -> tuple[CheckpointHead, CheckpointArtifact] | None:
    """Resolve latest checkpoint."""
    run_dir = _resolve_run_dir(store=store, run_id=run_id, run_dir=run_dir)
    head = load_checkpoint_head(run_dir)
    if head is None:
        return None
    _reconcile_checkpoint_history(run_dir, head=head)

    try:
        checkpoint = load_checkpoint(store, head.checkpoint_ref)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CheckpointCorruptedError(f"checkpoint artifact payload is invalid: {exc}") from exc
    if checkpoint.metadata.run_id != run_id:
        raise CheckpointCorruptedError(
            f"checkpoint run_id mismatch: expected={run_id} got={checkpoint.metadata.run_id}"
        )
    if checkpoint.metadata.sequence_number != head.sequence_number:
        raise CheckpointCorruptedError(
            "checkpoint sequence mismatch between checkpoint_head.json and artifact"
        )
    mismatches = _checkpoint_head_artifact_mismatches(head, checkpoint)
    if mismatches:
        raise CheckpointCorruptedError(
            "checkpoint metadata mismatch between checkpoint_head.json and artifact: "
            + ", ".join(mismatches)
        )
    materialized_state = materialize_checkpoint_state(store, head.checkpoint_ref)
    return head, checkpoint.model_copy(update={"state": materialized_state})


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
    except ImportError as exc:  # pragma: no cover
        raise RunLockError("fcntl is unavailable on this platform") from exc

    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / RUN_LOCK_FILENAME

    for attempt in range(max(1, max_attempts)):
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            current = read_run_lock_metadata(lock_path)
            if force and current is not None:
                same_host = current.get("hostname") == socket.gethostname()
                stale = (
                    same_host
                    and isinstance(current.get("pid"), int)
                    and not _pid_exists(int(current["pid"]))
                )
                if stale:
                    logger.warning(
                        "Run lock metadata for %s appears stale but the OS lock is held",
                        run_id,
                    )
            os.close(fd)
            if attempt < max_attempts - 1:
                delay = retry_delay_s * (2**attempt)
                logger.info(
                    "Lock for run %s held; retrying in %.1fs (attempt %d/%d)",
                    run_id,
                    delay,
                    attempt + 1,
                    max_attempts,
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
        "started_at": datetime.now(UTC).isoformat(),
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
    run_id: str | CheckpointResumeRequest,
    *,
    workflow: WorkflowSpec | None = None,
    registry: CheckpointRegistry | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    resume_strategy: CheckpointResumeStrategy = "require_cache_seed",
    force_lock: bool = False,
    run_dir: Path | None = None,
) -> Any:
    # Local imports avoid circular dependency at module import time.
    """Resume a run from its latest checkpoint after lock, schema, and workflow checks."""
    from polisyos.scientist.engine.executor import (
        WorkflowExecutionResult,
        WorkflowReport,
    )
    from polisyos.scientist.engine.runner.config import (
        WorkflowRunnerConfig,
        build_workflow_runner,
    )
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_REGISTRY_BUNDLE_REF
    from polisyos.scientist.workflows.builder import (
        build_default_registry,
        build_execution_context,
        build_registry_with_builtin_nodes,
    )
    from polisyos.scientist.workflows.default import default_workflow_spec

    if isinstance(run_id, CheckpointResumeRequest):
        request = run_id
        run_id = request.run_id
        workflow = request.workflow
        registry = request.registry
        registry_bundle_ref = request.registry_bundle_ref
        checkpoint_policy = request.checkpoint_policy
        resume_strategy = request.resume_strategy
        force_lock = request.force_lock
        run_dir = request.run_dir

    policy = normalize_checkpoint_policy(checkpoint_policy)
    checkpoint_resume_strategy = normalize_checkpoint_resume_strategy(resume_strategy)
    run_dir = _resolve_run_dir(store=store, run_id=run_id, run_dir=run_dir)
    lock = acquire_run_lock(run_dir, run_id=run_id, mode="resume", force=force_lock)
    try:
        resolved = resolve_latest_checkpoint(store, run_id, run_dir=run_dir)
        if resolved is None:
            raise CheckpointNotFoundError(f"no checkpoint found for run_id={run_id}")
        head, checkpoint = resolved

        _validate_checkpoint_schema(
            checkpoint.metadata.schema_version,
            CHECKPOINT_SCHEMA_VERSION,
        )

        restored_state = ExperimentState.model_validate(checkpoint.state)

        workflow_spec = workflow or default_workflow_spec()
        current_fingerprint = compute_workflow_fingerprint(workflow_spec)
        if checkpoint.metadata.workflow_fingerprint != current_fingerprint:
            raise WorkflowMismatchError(
                "checkpoint workflow fingerprint does not match current workflow spec"
            )
        resumed_workflow = _build_resume_workflow_spec(
            workflow_spec,
            completed_nodes=checkpoint.metadata.completed_nodes,
        )
        invocations = {inv.alias: inv for inv in workflow_spec.nodes}
        cacheable_completed = [
            alias
            for alias in checkpoint.metadata.completed_nodes
            if alias in invocations
            and str(invocations[alias].node_id) not in _CHECKPOINT_CACHE_DISABLED_NODE_IDS
        ]
        if checkpoint_resume_strategy == "require_cache_seed" and len(
            checkpoint.metadata.cache_entry_refs
        ) < len(cacheable_completed):
            raise CheckpointCorruptedError(
                "checkpoint resume requires cache seed refs for completed cacheable nodes; "
                "pass resume_strategy='allow_replay' only if re-running completed nodes is safe"
            )
        if checkpoint_resume_strategy == "allow_replay" and len(
            checkpoint.metadata.cache_entry_refs
        ) < len(cacheable_completed):
            emit_degraded_path(
                component="scientist.checkpoint",
                operation="resume",
                reason="checkpoint_resume_replay_allowed",
                message="Resuming with incomplete cache seed refs may re-run completed nodes",
                retryable=False,
                details={
                    "run_id": run_id,
                    "completed_cacheable_nodes": len(cacheable_completed),
                    "cache_entry_refs": len(checkpoint.metadata.cache_entry_refs),
                },
                log=logger,
            )

        registry_bundle_ref = registry_bundle_ref or restored_state.inputs.get(
            INPUT_REGISTRY_BUNDLE_REF
        )
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
            initial_completed_nodes=checkpoint.metadata.completed_nodes,
            initial_checkpoint_ref=head.checkpoint_ref,
            initial_state=checkpoint.state,
            initial_chain_depth=head.chain_depth,
        )

        runner_config = WorkflowRunnerConfig.from_env()
        resolved_registry = registry or build_registry_with_builtin_nodes()
        if len(resumed_workflow.nodes) == 0:
            return WorkflowExecutionResult(
                state=restored_state,
                report=WorkflowReport(
                    schema_version="1.0",
                    workflow_id=workflow_spec.workflow_id,
                    run_id=run_id,
                    error_policy=workflow_spec.error_policy,
                    status="ok",
                    nodes=[],
                ),
            )

        try:
            runner = build_workflow_runner(runner_config)
        except (ImportError, RuntimeError, ValueError) as exc:
            if runner_config.backend != "local":
                emit_degraded_path(
                    component="scientist.checkpoint",
                    operation="resume",
                    reason="distributed_resume_local_fallback",
                    exc=exc,
                    message=(
                        "Configured distributed runner is unavailable during resume; "
                        "falling back to the local runner"
                    ),
                    retryable=False,
                    details={
                        "run_id": run_id,
                        "configured_backend": runner_config.backend,
                    },
                    log=logger,
                )
                runner = build_workflow_runner(
                    runner_config.model_copy(update={"backend": "local"})
                )
            else:
                raise
        execution_coro = runner.execute_workflow(
            resumed_workflow,
            restored_state,
            ctx,
            resolved_registry,
            checkpoint_hook=hook,
            checkpoint_cache_seed_refs=checkpoint.metadata.cache_entry_refs,
            max_parallelism=runner_config.max_parallelism,
        )
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is not None and running_loop.is_running():
            return run_coro_sync(execution_coro)
        return asyncio.run(execution_coro)
    finally:
        lock.release()


__all__ = [
    "CHECKPOINT_HEAD_FILENAME",
    "CHECKPOINT_HISTORY_FILENAME",
    "CHECKPOINT_KIND",
    "CHECKPOINT_SCHEMA_VERSION",
    "RUN_LOCK_FILENAME",
    "CASCheckpointHook",
    "CheckpointArtifact",
    "CheckpointCorruptedError",
    "CheckpointError",
    "CheckpointGCPolicy",
    "CheckpointHead",
    "CheckpointHistory",
    "CheckpointHistoryEntry",
    "CheckpointHook",
    "CheckpointMetadata",
    "CheckpointMetadataConflictError",
    "CheckpointNotFoundError",
    "CheckpointPolicy",
    "CheckpointResumeStrategy",
    "CheckpointSchemaError",
    "CheckpointSnapshotMode",
    "CheckpointStore",
    "CheckpointWriteResult",
    "CreatedCheckpoint",
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
    "load_checkpoint_history",
    "materialize_checkpoint_state",
    "normalize_checkpoint_policy",
    "normalize_checkpoint_resume_strategy",
    "read_run_lock_metadata",
    "resolve_latest_checkpoint",
    "restore_checkpoint_hook_from_runtime_metadata",
    "resume_from_checkpoint",
    "serialize_checkpoint_hook_runtime_metadata",
    "update_checkpoint_head",
]
