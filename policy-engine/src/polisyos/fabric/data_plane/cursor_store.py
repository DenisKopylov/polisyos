"""CAS-backed cursor, stream-checkpoint, and partition-state persistence."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import (
    CursorState,
    PartitionCursorState,
    StreamCheckpoint,
    StreamLifecycleState,
)
from polisyos.fabric.io.atomic import (
    atomic_write_json,
    cleanup_orphan_tmp_files,
    file_lock,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

logger = get_logger(__name__)


class CursorStoreError(ValueError):
    """Raised when the cursor index cannot be safely loaded or persisted."""


class CursorStore:
    """Read/write cursor/checkpoint artifacts to CAS with lightweight indices."""

    _INDEX_FILE = "cursor_index.json"
    _LOCK_FILE = "cursor_index.lock"
    _STREAM_INDEX_FILE = "stream_checkpoint_index.json"
    _STREAM_LOCK_FILE = "stream_checkpoint_index.lock"
    _PARTITION_INDEX_FILE = "partition_state_index.json"
    _PARTITION_LOCK_FILE = "partition_state_index.lock"

    def __init__(self, store: ArtifactStore, *, index_root: str | Path | None = None) -> None:
        self._store = store
        self._index_root = self._resolve_index_root(store, index_root=index_root)
        self._index_path = self._index_root / self._INDEX_FILE
        self._lock_path = self._index_root / self._LOCK_FILE
        self._stream_index_path = self._index_root / self._STREAM_INDEX_FILE
        self._stream_lock_path = self._index_root / self._STREAM_LOCK_FILE
        self._partition_index_path = self._index_root / self._PARTITION_INDEX_FILE
        self._partition_lock_path = self._index_root / self._PARTITION_LOCK_FILE
        self._lock = threading.RLock()
        with (
            self._lock,
            file_lock(self._lock_path),
            file_lock(self._stream_lock_path),
            file_lock(self._partition_lock_path),
        ):
            cleanup_orphan_tmp_files(self._index_path.parent)
            self._index: dict[str, str] = self._load_index_unlocked()
            self._stream_index: dict[str, str] = self._load_stream_index_unlocked()
            self._partition_index: dict[str, str] = self._load_partition_index_unlocked()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_cursor(self, cursor: CursorState) -> ArtifactRef:
        """Persist cursor state to CAS and update index."""
        ref = self._store.put_json(
            cursor.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="fabric.cursor_state",
                media_type="application/json",
                schema=SchemaInfo(name="cursor_state", version="1.0"),
            ),
        )
        with self._lock, file_lock(self._lock_path):
            latest = self._load_index_unlocked()
            latest[cursor.cursor_id] = str(ref.artifact_id)
            self._save_index_unlocked(latest)
            self._index = latest
        return ref

    def save_stream_checkpoint(self, checkpoint: StreamCheckpoint) -> ArtifactRef:
        """Persist one stream checkpoint and update the latest index."""
        ref = self._store.put_json(
            checkpoint.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="fabric.stream_checkpoint",
                media_type="application/json",
                schema=SchemaInfo(name="stream_checkpoint", version="1.0"),
            ),
        )
        with self._lock, file_lock(self._stream_lock_path):
            latest = self._load_stream_index_unlocked()
            latest[checkpoint.stream_id] = str(ref.artifact_id)
            self._save_stream_index_unlocked(latest)
            self._stream_index = latest
        return ref

    def save_partition_state(self, state: PartitionCursorState) -> ArtifactRef:
        """Persist one partition resume record and update the latest index."""
        ref = self._store.put_json(
            state.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="fabric.partition_cursor_state",
                media_type="application/json",
                schema=SchemaInfo(name="partition_cursor_state", version="1.0"),
            ),
        )
        with self._lock, file_lock(self._partition_lock_path):
            latest = self._load_partition_index_unlocked()
            key = self._partition_index_key(state.plan_id, state.partition_id)
            latest[key] = str(ref.artifact_id)
            self._save_partition_index_unlocked(latest)
            self._partition_index = latest
        return ref

    def commit_stream_progress(
        self,
        *,
        cursor: CursorState,
        checkpoint: StreamCheckpoint | None = None,
    ) -> tuple[ArtifactRef, ArtifactRef | None]:
        """Atomically update latest cursor and optional stream checkpoint indices."""
        cursor_ref = self._store.put_json(
            cursor.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="fabric.cursor_state",
                media_type="application/json",
                schema=SchemaInfo(name="cursor_state", version="1.0"),
            ),
        )
        checkpoint_ref: ArtifactRef | None = None
        if checkpoint is not None:
            checkpoint_ref = self._store.put_json(
                checkpoint.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind="fabric.stream_checkpoint",
                    media_type="application/json",
                    schema=SchemaInfo(name="stream_checkpoint", version="1.0"),
                ),
            )

        with self._lock, file_lock(self._lock_path), file_lock(self._stream_lock_path):
            latest_cursor_index = self._load_index_unlocked()
            latest_cursor_index[cursor.cursor_id] = str(cursor_ref.artifact_id)
            self._save_index_unlocked(latest_cursor_index)
            self._index = latest_cursor_index

            if checkpoint is not None and checkpoint_ref is not None:
                latest_stream_index = self._load_stream_index_unlocked()
                latest_stream_index[checkpoint.stream_id] = str(checkpoint_ref.artifact_id)
                self._save_stream_index_unlocked(latest_stream_index)
                self._stream_index = latest_stream_index

        return cursor_ref, checkpoint_ref

    def load_cursor(self, artifact_id: ArtifactID) -> CursorState:
        """Load cursor state from CAS by artifact ID."""
        raw = self._store.get_bytes(artifact_id)
        data = from_canonical_bytes(raw)
        return CursorState.model_validate(data)

    def load_stream_checkpoint(self, artifact_id: ArtifactID) -> StreamCheckpoint:
        """Load stream checkpoint from CAS by artifact ID."""
        raw = self._store.get_bytes(artifact_id)
        data = from_canonical_bytes(raw)
        return StreamCheckpoint.model_validate(data)

    def load_partition_state(self, artifact_id: ArtifactID) -> PartitionCursorState:
        """Load partition cursor state from CAS by artifact ID."""
        raw = self._store.get_bytes(artifact_id)
        data = from_canonical_bytes(raw)
        return PartitionCursorState.model_validate(data)

    def find_latest_cursor(
        self, connector_id: str, dataset_id: str,
    ) -> CursorState | None:
        """Find the most recent cursor for a connector:dataset pair."""
        cursor_id = f"{connector_id}:{dataset_id}"
        with self._lock:
            self._index = self._load_index()
            artifact_id_str = self._index.get(cursor_id)
        if not artifact_id_str:
            return None
        try:
            aid = ArtifactID.model_validate(artifact_id_str)
            return self.load_cursor(aid)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            logger.debug(
                "Failed to load cursor for %s:%s (artifact=%s)",
                connector_id, dataset_id, artifact_id_str, exc_info=True,
            )
            return None

    def list_cursors(self) -> list[CursorState]:
        """List all known cursors from the index."""
        result: list[CursorState] = []
        with self._lock:
            self._index = self._load_index()
            items = list(self._index.items())
        for cursor_id, artifact_id_str in items:
            try:
                aid = ArtifactID.model_validate(artifact_id_str)
                result.append(self.load_cursor(aid))
            except (FileNotFoundError, OSError, TypeError, ValueError):
                logger.debug(
                    "Failed to load cursor %s (artifact=%s)",
                    cursor_id, artifact_id_str, exc_info=True,
                )
                continue
        return result

    def find_latest_stream_checkpoint(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
    ) -> StreamCheckpoint | None:
        """Find the most recent checkpoint for one stream partition."""
        stream_id = self._stream_id(connector_id, dataset_id, partition_key=partition_key)
        with self._lock:
            self._stream_index = self._load_stream_index()
            artifact_id_str = self._stream_index.get(stream_id)
        if not artifact_id_str:
            return None
        try:
            aid = ArtifactID.model_validate(artifact_id_str)
            return self.load_stream_checkpoint(aid)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            logger.debug(
                "Failed to load stream checkpoint for %s (artifact=%s)",
                stream_id, artifact_id_str, exc_info=True,
            )
            return None

    def list_stream_checkpoints(self) -> list[StreamCheckpoint]:
        """List all latest stream checkpoints."""
        result: list[StreamCheckpoint] = []
        with self._lock:
            self._stream_index = self._load_stream_index()
            items = list(self._stream_index.items())
        for stream_id, artifact_id_str in items:
            try:
                aid = ArtifactID.model_validate(artifact_id_str)
                result.append(self.load_stream_checkpoint(aid))
            except (FileNotFoundError, OSError, TypeError, ValueError):
                logger.debug(
                    "Failed to load stream checkpoint %s (artifact=%s)",
                    stream_id, artifact_id_str, exc_info=True,
                )
                continue
        return result

    def pause_stream(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> StreamCheckpoint:
        """Mark one stream checkpoint as paused."""
        return self._update_stream_lifecycle(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key=partition_key,
            lifecycle_state=StreamLifecycleState.PAUSED,
            metadata=metadata,
        )

    def resume_stream(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> StreamCheckpoint:
        """Mark one stream checkpoint as active again."""
        return self._update_stream_lifecycle(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key=partition_key,
            lifecycle_state=StreamLifecycleState.ACTIVE,
            metadata=metadata,
        )

    def close_stream(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> StreamCheckpoint:
        """Mark one stream checkpoint as closed."""
        return self._update_stream_lifecycle(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key=partition_key,
            lifecycle_state=StreamLifecycleState.CLOSED,
            metadata=metadata,
        )

    def rewind_stream(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
        offset: int | None = None,
        resume_token: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StreamCheckpoint:
        """Rewind one stream to an earlier committed checkpoint."""
        checkpoint = self.find_latest_stream_checkpoint(
            connector_id,
            dataset_id,
            partition_key=partition_key,
        )
        if checkpoint is None:
            raise CursorStoreError(
                "cannot rewind missing stream checkpoint for "
                f"{connector_id}:{dataset_id}:{partition_key}"
            )
        updated = checkpoint.model_copy(
            update={
                "offset": max(0, offset if offset is not None else checkpoint.offset),
                "resume_token": (
                    resume_token
                    if resume_token is not None
                    else checkpoint.resume_token
                ),
                "lifecycle_state": StreamLifecycleState.ACTIVE,
                "committed_at": None,
                "metadata": {
                    **checkpoint.metadata,
                    **(metadata or {}),
                    "rewound": True,
                },
            }
        )
        self.save_stream_checkpoint(updated)
        return updated

    def find_partition_state(
        self,
        plan_id: str,
        partition_id: str,
    ) -> PartitionCursorState | None:
        """Find one persisted partition state."""
        key = self._partition_index_key(plan_id, partition_id)
        with self._lock:
            self._partition_index = self._load_partition_index()
            artifact_id_str = self._partition_index.get(key)
        if not artifact_id_str:
            return None
        try:
            aid = ArtifactID.model_validate(artifact_id_str)
            return self.load_partition_state(aid)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            logger.debug(
                "Failed to load partition state %s (artifact=%s)",
                key, artifact_id_str, exc_info=True,
            )
            return None

    def list_partition_states(self, *, plan_id: str | None = None) -> list[PartitionCursorState]:
        """List all latest partition states, optionally filtered by plan_id."""
        result: list[PartitionCursorState] = []
        with self._lock:
            self._partition_index = self._load_partition_index()
            items = list(self._partition_index.items())
        for key, artifact_id_str in items:
            if plan_id is not None and not key.startswith(f"{plan_id}:"):
                continue
            try:
                aid = ArtifactID.model_validate(artifact_id_str)
                result.append(self.load_partition_state(aid))
            except (FileNotFoundError, OSError, TypeError, ValueError):
                logger.debug(
                    "Failed to load partition state %s (artifact=%s)",
                    key, artifact_id_str, exc_info=True,
                )
                continue
        return result

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, str]:
        with self._lock, file_lock(self._lock_path):
            return self._load_index_unlocked()

    def _load_stream_index(self) -> dict[str, str]:
        with self._lock, file_lock(self._stream_lock_path):
            return self._load_stream_index_unlocked()

    def _load_partition_index(self) -> dict[str, str]:
        with self._lock, file_lock(self._partition_lock_path):
            return self._load_partition_index_unlocked()

    def _load_index_unlocked(self) -> dict[str, str]:
        if self._index_path.exists():
            try:
                raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise CursorStoreError(
                    f"failed to load cursor index {self._index_path}: {exc}"
                ) from exc
            return self._validate_index_payload(raw)
        return {}

    def _load_stream_index_unlocked(self) -> dict[str, str]:
        if self._stream_index_path.exists():
            try:
                raw = json.loads(self._stream_index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise CursorStoreError(
                    f"failed to load stream checkpoint index {self._stream_index_path}: {exc}"
                ) from exc
            return self._validate_index_payload(raw)
        return {}

    def _load_partition_index_unlocked(self) -> dict[str, str]:
        if self._partition_index_path.exists():
            try:
                raw = json.loads(self._partition_index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise CursorStoreError(
                    f"failed to load partition cursor index {self._partition_index_path}: {exc}"
                ) from exc
            return self._validate_index_payload(raw)
        return {}

    def _save_index_unlocked(self, index: dict[str, str]) -> None:
        def _validate_tmp(tmp_path: Path) -> None:
            self._validate_index_payload(json.loads(tmp_path.read_text(encoding="utf-8")))

        atomic_write_json(
            self._index_path,
            index,
            validate_tmp=_validate_tmp,
        )

    def _save_stream_index_unlocked(self, index: dict[str, str]) -> None:
        def _validate_tmp(tmp_path: Path) -> None:
            self._validate_index_payload(json.loads(tmp_path.read_text(encoding="utf-8")))

        atomic_write_json(
            self._stream_index_path,
            index,
            validate_tmp=_validate_tmp,
        )

    def _save_partition_index_unlocked(self, index: dict[str, str]) -> None:
        def _validate_tmp(tmp_path: Path) -> None:
            self._validate_index_payload(json.loads(tmp_path.read_text(encoding="utf-8")))

        atomic_write_json(
            self._partition_index_path,
            index,
            validate_tmp=_validate_tmp,
        )

    def _update_stream_lifecycle(
        self,
        *,
        connector_id: str,
        dataset_id: str,
        partition_key: str,
        lifecycle_state: StreamLifecycleState,
        metadata: dict[str, Any] | None = None,
    ) -> StreamCheckpoint:
        checkpoint = self.find_latest_stream_checkpoint(
            connector_id,
            dataset_id,
            partition_key=partition_key,
        )
        if checkpoint is None:
            raise CursorStoreError(
                f"missing stream checkpoint for {connector_id}:{dataset_id}:{partition_key}"
            )
        updated = checkpoint.model_copy(
            update={
                "lifecycle_state": lifecycle_state,
                "metadata": {
                    **checkpoint.metadata,
                    **(metadata or {}),
                },
            }
        )
        self.save_stream_checkpoint(updated)
        return updated

    @staticmethod
    def _stream_id(connector_id: str, dataset_id: str, *, partition_key: str = "default") -> str:
        return f"{connector_id}:{dataset_id}:{partition_key}"

    @staticmethod
    def _partition_index_key(plan_id: str, partition_id: str) -> str:
        return f"{plan_id}:{partition_id}"

    @staticmethod
    def _resolve_index_root(
        store: ArtifactStore,
        *,
        index_root: str | Path | None,
    ) -> Path:
        if index_root is not None:
            return Path(index_root)
        root_value = getattr(store, "root", None)
        if root_value is None:
            raise CursorStoreError(
                "CursorStore requires index_root when the artifact store does not "
                "expose a local root"
            )
        return Path(root_value)

    @staticmethod
    def _validate_index_payload(payload: object) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise CursorStoreError("cursor index must be a JSON object")
        validated: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not key:
                raise CursorStoreError("cursor index contains an invalid cursor id")
            if not isinstance(value, str) or not value:
                raise CursorStoreError(
                    f"cursor index contains an invalid artifact id for {key}"
                )
            ArtifactID.model_validate(value)
            validated[key] = value
        return validated


@dataclass(frozen=True, slots=True)
class AsyncCursorStoreAdapter:
    """Shared-executor async wrapper for ``CursorStore``."""

    store: CursorStore
    timeout_seconds: float | None = None

    async def save_cursor(self, cursor: CursorState) -> ArtifactRef:
        return await run_blocking_async(
            self.store.save_cursor,
            cursor,
            timeout_seconds=self.timeout_seconds,
        )

    async def save_stream_checkpoint(self, checkpoint: StreamCheckpoint) -> ArtifactRef:
        return await run_blocking_async(
            self.store.save_stream_checkpoint,
            checkpoint,
            timeout_seconds=self.timeout_seconds,
        )

    async def save_partition_state(self, state: PartitionCursorState) -> ArtifactRef:
        return await run_blocking_async(
            self.store.save_partition_state,
            state,
            timeout_seconds=self.timeout_seconds,
        )

    async def commit_stream_progress(
        self,
        *,
        cursor: CursorState,
        checkpoint: StreamCheckpoint | None = None,
    ) -> tuple[ArtifactRef, ArtifactRef | None]:
        return cast(
            "tuple[ArtifactRef, ArtifactRef | None]",
            await run_blocking_async(
            self.store.commit_stream_progress,
            cursor=cursor,
            checkpoint=checkpoint,
            timeout_seconds=self.timeout_seconds,
            ),
        )

    async def find_latest_cursor(
        self,
        connector_id: str,
        dataset_id: str,
    ) -> CursorState | None:
        return await run_blocking_async(
            self.store.find_latest_cursor,
            connector_id,
            dataset_id,
            timeout_seconds=self.timeout_seconds,
        )

    async def find_latest_stream_checkpoint(
        self,
        connector_id: str,
        dataset_id: str,
        *,
        partition_key: str = "default",
    ) -> StreamCheckpoint | None:
        return await run_blocking_async(
            self.store.find_latest_stream_checkpoint,
            connector_id,
            dataset_id,
            partition_key=partition_key,
            timeout_seconds=self.timeout_seconds,
        )

    async def list_partition_states(
        self,
        *,
        plan_id: str | None = None,
    ) -> list[PartitionCursorState]:
        return cast(
            "list[PartitionCursorState]",
            await run_blocking_async(
                self.store.list_partition_states,
                plan_id=plan_id,
                timeout_seconds=self.timeout_seconds,
            ),
        )

    async def find_partition_state(
        self,
        plan_id: str,
        partition_id: str,
    ) -> PartitionCursorState | None:
        return await run_blocking_async(
            self.store.find_partition_state,
            plan_id,
            partition_id,
            timeout_seconds=self.timeout_seconds,
        )

__all__ = ["AsyncCursorStoreAdapter", "CursorStore", "CursorStoreError"]
