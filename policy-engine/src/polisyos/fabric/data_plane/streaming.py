"""Event-driven streaming runtime, checkpointing, and CDC helpers."""
from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import floor
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_blocking_async
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
    is_async_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash
from polisyos.core.contracts.cursor import (
    CursorState,
    StreamCheckpoint,
    StreamLifecycleState,
    WatermarkType,
    WindowStrategy,
)
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.pool import BackpressureLevel, ConnectionPool, PoolConfig
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.data_plane.watermark import WindowAssignment, WindowPolicy
from polisyos.fabric.temporal import parse_datetime_utc
from polisyos.ir.connectors import FetchRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.types import DataChunk
else:
    AsyncIterator = Any
    Callable = Any
    DataChunk = Any
    ConnectorRegistryProvider = Any

if TYPE_CHECKING:
    ConnectorRegistryProvider = Callable[[], ConnectorRegistry]


@dataclass(frozen=True)
class StreamRuntimeOptions:
    """Runtime controls for bounded, resumable stream processing."""

    partition_key: str = "default"
    batch_size: int = 1_000
    checkpoint_every_chunks: int = 1
    dedupe_key_fields: tuple[str, ...] = ("_message_id", "message_id", "id")
    max_dedupe_keys: int = 4_096
    max_buffered_rows: int = 10_000
    max_buffered_bytes: int = 16 * 1024 * 1024
    pause_seconds: float = 0.01
    window_policy: WindowPolicy = field(default_factory=WindowPolicy)


@dataclass
class StreamDatasetRunResult:
    """Materialized outputs and counters for one streamed dataset."""

    connector_id: str
    dataset_id: str
    partition_key: str
    chunk_refs: list[ArtifactRef] = field(default_factory=list)
    window_refs: list[ArtifactRef] = field(default_factory=list)
    cdc_event_refs: list[ArtifactRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_emitted: int = 0
    chunks_processed: int = 0
    quarantined_rows: int = 0
    dedupe_dropped: int = 0
    backpressure_events: int = 0
    final_checkpoint: StreamCheckpoint | None = None
    final_cursor: CursorState | None = None
    final_checkpoint_ref: str | None = None
    final_cursor_ref: str | None = None


def normalize_connection_config(config: ConnectionConfig | dict[str, Any] | None) -> ConnectionConfig | None:
    """Normalize connection config inputs for one stream session."""
    if config is None or isinstance(config, ConnectionConfig):
        return config
    return ConnectionConfig(**dict(config))


async def iter_record_batches(
    payload: Any,
    *,
    batch_size: int,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield record batches without blocking the event loop on large DataFrames."""
    if hasattr(payload, "iloc") and hasattr(payload, "to_dict"):
        total_rows = len(payload.index)

        def _slice_to_dict(start: int) -> list[dict[str, Any]]:
            return cast(
                "list[dict[str, Any]]",
                payload.iloc[start : start + batch_size].to_dict(orient="records"),
            )

        for start in range(0, total_rows, batch_size):
            yield await run_blocking_async(_slice_to_dict, start)
            await asyncio.sleep(0)
        return

    if isinstance(payload, list):
        for start in range(0, len(payload), batch_size):
            chunk = payload[start : start + batch_size]
            normalized = [dict(item) if isinstance(item, dict) else item for item in chunk]
            yield normalized
            await asyncio.sleep(0)
        return

    if isinstance(payload, dict):
        yield [dict(payload)]
        return

    yield [payload]


class StreamingSourceSession:
    """Generic adapter that upgrades fetch_stream() into a resumable stream protocol."""

    def __init__(
        self,
        *,
        connector_id: str,
        dataset_id: str,
        pool: ConnectionPool[Any],
        request: FetchRequest,
        partition_key: str = "default",
    ) -> None:
        self.connector_id = connector_id
        self.dataset_id = dataset_id
        self.partition_key = partition_key
        self.pool = pool
        self.request = request
        self.connector: Any | None = None
        self.handle: Any | None = None
        self._generator: AsyncIterator[DataChunk[Any]] | None = None
        self._subscription: Any = None
        self._paused = False
        self._closed = False
        self._last_chunk: DataChunk[Any] | None = None
        self._prefetched_chunk: DataChunk[Any] | None = None

    @classmethod
    async def create(
        cls,
        *,
        connector_id: str,
        dataset_id: str,
        connection_config: ConnectionConfig | dict[str, Any] | None = None,
        request: FetchRequest | None = None,
        partition_key: str = "default",
        registry: ConnectorRegistry | None = None,
        registry_provider: ConnectorRegistryProvider | None = None,
    ) -> StreamingSourceSession:
        resolved_registry = _resolve_connector_registry(
            registry=registry,
            registry_provider=registry_provider,
        )
        entry = resolved_registry.get_entry(connector_id)
        config = normalize_connection_config(connection_config) or entry.default_config
        if config is None:
            raise ValueError(f"No connection config available for {connector_id!r}")
        pool = ConnectionPool(
            connector_factory=entry.factory,
            config=config,
            pool_config=PoolConfig(max_size=max(1, int(config.max_connections or 1))),
            pool_id=f"stream-{connector_id}-{dataset_id}",
        )
        session = cls(
            connector_id=connector_id,
            dataset_id=dataset_id,
            pool=pool,
            request=request or FetchRequest(dataset_id=dataset_id),
            partition_key=partition_key,
        )
        await session.subscribe()
        return session

    async def subscribe(self) -> None:
        """Open the stream subscription and prepare polling."""
        connector, handle = await self.pool.acquire_with_connector()
        self.connector = connector
        self.handle = handle
        if hasattr(connector, "subscribe_stream"):
            self._subscription = await cast(
                "Any",
                connector,
            ).subscribe_stream(handle, self.request)
        else:
            stream = cast("Any", connector).fetch_stream(handle, self.request)
            if hasattr(stream, "__await__"):
                stream = await stream
            self._generator = cast("AsyncIterator[DataChunk[Any]]", stream)

    async def poll(self) -> DataChunk[Any] | None:
        """Read the next stream chunk."""
        if self._closed:
            return None
        while self._paused:
            await asyncio.sleep(0.01)
        if self._prefetched_chunk is not None:
            chunk = self._prefetched_chunk
            self._prefetched_chunk = None
            self._last_chunk = chunk
            return chunk
        if self.connector is None or self.handle is None:
            raise RuntimeError("stream session is not subscribed")
        if hasattr(self.connector, "poll_stream"):
            chunk = await self.connector.poll_stream(self.handle, self._subscription)
        else:
            if self._generator is None:
                raise RuntimeError("stream generator not initialized")
            try:
                chunk = await anext(self._generator)
            except StopAsyncIteration:
                return None
        self._last_chunk = chunk
        return chunk

    def checkpoint(
        self,
        *,
        dedupe_keys: tuple[str, ...] = (),
        schema_fingerprint: str | None = None,
        lifecycle_state: StreamLifecycleState = StreamLifecycleState.ACTIVE,
    ) -> StreamCheckpoint:
        """Build a checkpoint from the last observed stream position."""
        last_chunk = self._last_chunk
        offset = int(last_chunk.chunk_index) if last_chunk is not None else 0
        resume_token = last_chunk.resume_token if last_chunk is not None else None
        return StreamCheckpoint(
            checkpoint_id=f"{self.connector_id}:{self.dataset_id}:{self.partition_key}:{offset}",
            stream_id=f"{self.connector_id}:{self.dataset_id}:{self.partition_key}",
            connector_id=self.connector_id,
            dataset_id=self.dataset_id,
            partition_key=self.partition_key,
            offset=offset,
            resume_token=resume_token,
            lifecycle_state=lifecycle_state,
            dedupe_keys=dedupe_keys,
            schema_fingerprint=schema_fingerprint,
            created_at=datetime.now(UTC),
            committed_at=(
                datetime.now(UTC)
                if lifecycle_state == StreamLifecycleState.CLOSED
                else None
            ),
        )

    async def commit(self, checkpoint: StreamCheckpoint) -> None:
        """Commit one checkpoint to the source if the connector supports it."""
        if self.connector is not None and self.handle is not None and hasattr(
            self.connector,
            "commit_stream",
        ):
            await self.connector.commit_stream(self.handle, checkpoint)

    async def rewind(self, checkpoint: StreamCheckpoint) -> None:
        """Rewind the stream to one earlier checkpoint."""
        if self.connector is not None and self.handle is not None and hasattr(
            self.connector,
            "rewind_stream",
        ):
            await self.connector.rewind_stream(self.handle, checkpoint)
            return

        await self._reconnect()
        while True:
            chunk = await self.poll()
            if chunk is None:
                break
            if int(chunk.chunk_index) > checkpoint.offset:
                self._prefetched_chunk = chunk
                self._last_chunk = None
                break

    async def pause(self, *, reason: str = "") -> None:
        """Pause polling and propagate backpressure to the connector when supported."""
        self._paused = True
        self.pool.register_backpressure(
            source=f"{self.connector_id}:{self.dataset_id}:{self.partition_key}",
            level=BackpressureLevel.PAUSED,
            reason=reason or "stream paused",
        )
        if self.connector is not None and self.handle is not None and hasattr(
            self.connector,
            "pause_stream",
        ):
            await self.connector.pause_stream(self.handle, reason=reason)

    async def resume(self) -> None:
        """Resume polling after backpressure."""
        self._paused = False
        self.pool.clear_backpressure(
            source=f"{self.connector_id}:{self.dataset_id}:{self.partition_key}",
        )
        if self.connector is not None and self.handle is not None and hasattr(
            self.connector,
            "resume_stream",
        ):
            await self.connector.resume_stream(self.handle)

    async def close(self) -> None:
        """Release the current stream handle and close owned pool resources."""
        if self._closed:
            return
        self._closed = True
        if self.connector is not None and self.handle is not None and hasattr(
            self.connector,
            "close_stream",
        ):
            await self.connector.close_stream(self.handle)
        if self.handle is not None:
            await self.pool.release(self.handle)
        await self.pool.close_all()
        self.connector = None
        self.handle = None
        self._generator = None
        self._subscription = None

    async def _reconnect(self) -> None:
        if self.handle is not None:
            await self.pool.release(self.handle)
        self.connector = None
        self.handle = None
        self._generator = None
        self._subscription = None
        self._prefetched_chunk = None
        await self.subscribe()

    @property
    def last_chunk(self) -> DataChunk[Any] | None:
        return self._last_chunk


def _resolve_connector_registry(
    *,
    registry: ConnectorRegistry | None = None,
    registry_provider: ConnectorRegistryProvider | None = None,
) -> ConnectorRegistry:
    if registry is not None:
        return registry
    if registry_provider is not None:
        return registry_provider()
    return _default_connector_registry()


def _default_connector_registry() -> ConnectorRegistry:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return ConnectorRegistry.get_instance()


class StreamWindowAccumulator:
    """Incremental window accumulator that keeps buffers bounded."""

    def __init__(self, policy: WindowPolicy) -> None:
        self.policy = policy
        self._ordinal = 0
        self._count_buffer: list[dict[str, Any]] = []
        self._sliding_rows: deque[dict[str, Any]] = deque()
        self._rows_since_emit = 0
        self._bucket_key: int | None = None
        self._bucket_rows: list[dict[str, Any]] = []
        self._session_rows: list[dict[str, Any]] = []
        self._session_start: datetime | None = None
        self._previous_ts: datetime | None = None
        self._next_slide_at: datetime | None = None
        self._sliding_time_rows: deque[tuple[dict[str, Any], datetime]] = deque()

    def add_rows(self, rows: list[dict[str, Any]]) -> list[WindowAssignment]:
        assignments: list[WindowAssignment] = []
        for row in rows:
            assignments.extend(self._add_row(row))
        return assignments

    def flush(self) -> list[WindowAssignment]:
        strategy = self.policy.strategy
        assignments: list[WindowAssignment] = []
        if strategy in {WindowStrategy.COUNT, WindowStrategy.TUMBLING} and self._count_buffer:
            assignments.append(self._emit_count_window(strategy, self._count_buffer))
            self._count_buffer = []
        if strategy == WindowStrategy.TUMBLING and self._bucket_rows:
            assignments.append(self._emit_bucket_window())
            self._bucket_rows = []
            self._bucket_key = None
        if strategy == WindowStrategy.SESSION and self._session_rows:
            assignments.append(self._emit_session_window())
            self._session_rows = []
            self._session_start = None
            self._previous_ts = None
        if strategy == WindowStrategy.SLIDING and self._sliding_time_rows:
            batch = tuple(row for row, _ts in self._sliding_time_rows)
            if batch:
                assignments.append(
                    WindowAssignment(
                        window_id=f"sliding:{self._ordinal}",
                        strategy=WindowStrategy.SLIDING,
                        row_count=len(batch),
                        rows=batch,
                        start_at=self._sliding_time_rows[0][1].isoformat(),
                        end_at=self._sliding_time_rows[-1][1].isoformat(),
                        ordinal=self._next_ordinal(),
                    )
                )
        return assignments

    def buffered_rows(self) -> int:
        return (
            len(self._count_buffer)
            + len(self._bucket_rows)
            + len(self._session_rows)
            + len(self._sliding_rows)
            + len(self._sliding_time_rows)
        )

    def _add_row(self, row: dict[str, Any]) -> list[WindowAssignment]:
        strategy = self.policy.strategy
        if strategy == WindowStrategy.COUNT:
            return self._count_add(row, WindowStrategy.COUNT)
        if strategy == WindowStrategy.TUMBLING:
            ts = self._timestamp(row)
            if ts is None:
                return self._count_add(row, WindowStrategy.TUMBLING)
            return self._tumbling_time_add(row, ts)
        if strategy == WindowStrategy.SESSION:
            return self._session_add(row)
        return self._sliding_add(row)

    def _count_add(
        self,
        row: dict[str, Any],
        strategy: WindowStrategy,
    ) -> list[WindowAssignment]:
        self._count_buffer.append(row)
        size = max(1, int(self.policy.size))
        if len(self._count_buffer) < size:
            return []
        assignment = self._emit_count_window(strategy, self._count_buffer[:size])
        self._count_buffer = self._count_buffer[size:]
        return [assignment]

    def _emit_count_window(
        self,
        strategy: WindowStrategy,
        rows: list[dict[str, Any]],
    ) -> WindowAssignment:
        assignment = WindowAssignment(
            window_id=f"{strategy.value}:{self._ordinal}",
            strategy=strategy,
            row_count=len(rows),
            rows=tuple(rows),
            ordinal=self._next_ordinal(),
        )
        return assignment

    def _tumbling_time_add(
        self,
        row: dict[str, Any],
        ts: datetime,
    ) -> list[WindowAssignment]:
        bucket_seconds = max(1, int(self.policy.size))
        bucket_key = floor(ts.timestamp() / bucket_seconds)
        if self._bucket_key is None:
            self._bucket_key = bucket_key
        if bucket_key != self._bucket_key and self._bucket_rows:
            assignment = self._emit_bucket_window()
            self._bucket_rows = [row]
            self._bucket_key = bucket_key
            return [assignment]
        self._bucket_rows.append(row)
        return []

    def _emit_bucket_window(self) -> WindowAssignment:
        assert self._bucket_key is not None
        bucket_seconds = max(1, int(self.policy.size))
        start_at = datetime.fromtimestamp(self._bucket_key * bucket_seconds, tz=UTC)
        end_at = datetime.fromtimestamp((self._bucket_key + 1) * bucket_seconds, tz=UTC)
        return WindowAssignment(
            window_id=f"tumbling:{self._bucket_key}",
            strategy=WindowStrategy.TUMBLING,
            row_count=len(self._bucket_rows),
            rows=tuple(self._bucket_rows),
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            ordinal=self._next_ordinal(),
        )

    def _session_add(self, row: dict[str, Any]) -> list[WindowAssignment]:
        ts = self._timestamp(row)
        if ts is None:
            self._session_rows.append(row)
            return []
        gap_seconds = float(self.policy.session_gap_seconds or self.policy.size or 60.0)
        if self._session_start is None:
            self._session_start = ts
        if self._previous_ts is not None and (ts - self._previous_ts).total_seconds() > gap_seconds:
            assignment = self._emit_session_window()
            self._session_rows = [row]
            self._session_start = ts
            self._previous_ts = ts
            return [assignment]
        self._session_rows.append(row)
        self._previous_ts = ts
        return []

    def _emit_session_window(self) -> WindowAssignment:
        end_at = self._previous_ts or self._session_start
        return WindowAssignment(
            window_id=f"session:{self._ordinal}",
            strategy=WindowStrategy.SESSION,
            row_count=len(self._session_rows),
            rows=tuple(self._session_rows),
            start_at=self._session_start.isoformat() if self._session_start is not None else None,
            end_at=end_at.isoformat() if end_at is not None else None,
            ordinal=self._next_ordinal(),
        )

    def _sliding_add(self, row: dict[str, Any]) -> list[WindowAssignment]:
        ts = self._timestamp(row)
        if ts is None:
            return self._sliding_count_add(row)
        return self._sliding_time_add(row, ts)

    def _sliding_count_add(self, row: dict[str, Any]) -> list[WindowAssignment]:
        size = max(1, int(self.policy.size))
        slide = max(1, int(self.policy.slide or 1))
        self._sliding_rows.append(row)
        while len(self._sliding_rows) > size:
            self._sliding_rows.popleft()
        self._rows_since_emit += 1
        if len(self._sliding_rows) < size or self._rows_since_emit < slide:
            return []
        self._rows_since_emit = 0
        return [
            WindowAssignment(
                window_id=f"sliding:{self._ordinal}",
                strategy=WindowStrategy.SLIDING,
                row_count=len(self._sliding_rows),
                rows=tuple(self._sliding_rows),
                ordinal=self._next_ordinal(),
            )
        ]

    def _sliding_time_add(self, row: dict[str, Any], ts: datetime) -> list[WindowAssignment]:
        window_seconds = max(1, int(self.policy.size))
        slide_seconds = max(1, int(self.policy.slide or self.policy.size))
        self._sliding_time_rows.append((row, ts))
        while self._sliding_time_rows and (
            ts - self._sliding_time_rows[0][1]
        ).total_seconds() > window_seconds:
            self._sliding_time_rows.popleft()
        if self._next_slide_at is None:
            self._next_slide_at = ts
        if ts < self._next_slide_at:
            return []
        assignment = WindowAssignment(
            window_id=f"sliding:{self._ordinal}",
            strategy=WindowStrategy.SLIDING,
            row_count=len(self._sliding_time_rows),
            rows=tuple(item[0] for item in self._sliding_time_rows),
            start_at=self._sliding_time_rows[0][1].isoformat(),
            end_at=self._sliding_time_rows[-1][1].isoformat(),
            ordinal=self._next_ordinal(),
        )
        self._next_slide_at = ts + timedelta(seconds=slide_seconds)
        return [assignment]

    def _timestamp(self, row: dict[str, Any]) -> datetime | None:
        value = (
            row.get(self.policy.timestamp_field)
            or row.get("timestamp")
            or row.get("event_time")
            or row.get("observed_at")
        )
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return cast(
            "datetime",
            parse_datetime_utc(str(value), what="stream event timestamp"),
        )

    def _next_ordinal(self) -> int:
        ordinal = self._ordinal
        self._ordinal += 1
        return ordinal


def _ensure_async_store(
    store: ArtifactStore | AsyncArtifactStore,
    *,
    timeout_seconds: float | None = 5.0,
) -> AsyncArtifactStore:
    return ensure_async_artifact_store(store, timeout_seconds=timeout_seconds)


def _resolve_sync_store(
    store: ArtifactStore | AsyncArtifactStore,
    async_store: AsyncArtifactStore,
) -> ArtifactStore | None:
    if isinstance(async_store, AsyncArtifactStoreAdapter | AsyncFileSystemArtifactStore):
        return async_store.store
    if is_async_artifact_store(store):
        return None
    return cast("ArtifactStore", store)


def _ensure_async_cursor_store(
    cursor_store: CursorStore | AsyncCursorStoreAdapter,
    *,
    timeout_seconds: float | None = 5.0,
) -> AsyncCursorStoreAdapter:
    if isinstance(cursor_store, AsyncCursorStoreAdapter):
        return cursor_store
    return AsyncCursorStoreAdapter(cursor_store, timeout_seconds=timeout_seconds)


async def process_stream_dataset(
    *,
    connector_id: str,
    dataset_id: str,
    store: ArtifactStore | AsyncArtifactStore,
    cursor_store: CursorStore | AsyncCursorStoreAdapter,
    sanitize_rows: Callable[..., tuple[list[dict[str, Any]], list[str], int]],
    runtime_options: StreamRuntimeOptions | None = None,
    connection_config: ConnectionConfig | dict[str, Any] | None = None,
    registry: ConnectorRegistry | None = None,
    registry_provider: ConnectorRegistryProvider | None = None,
) -> StreamDatasetRunResult:
    """Process one streamed dataset with checkpoint recovery and bounded buffering."""
    options = runtime_options or StreamRuntimeOptions()
    async_store = _ensure_async_store(store)
    sync_store = _resolve_sync_store(store, async_store)
    if sync_store is None:
        raise TypeError(
            "process_stream_dataset requires a sync ArtifactStore companion for row sanitization"
        )
    async_cursor_store = _ensure_async_cursor_store(cursor_store)
    session = await StreamingSourceSession.create(
        connector_id=connector_id,
        dataset_id=dataset_id,
        connection_config=connection_config,
        partition_key=options.partition_key,
        registry=registry,
        registry_provider=registry_provider,
    )
    result = StreamDatasetRunResult(
        connector_id=connector_id,
        dataset_id=dataset_id,
        partition_key=options.partition_key,
    )
    accumulator = StreamWindowAccumulator(options.window_policy)
    dedupe_keys: deque[str] = deque(maxlen=max(1, int(options.max_dedupe_keys)))
    dedupe_seen: set[str] = set()
    latest_checkpoint = await async_cursor_store.find_latest_stream_checkpoint(
        connector_id,
        dataset_id,
        partition_key=options.partition_key,
    )
    if latest_checkpoint is not None:
        dedupe_keys.extend(latest_checkpoint.dedupe_keys)
        dedupe_seen.update(latest_checkpoint.dedupe_keys)
        await session.rewind(latest_checkpoint)

    previous_schema: tuple[str, ...] | None = (
        tuple(str(field) for field in latest_checkpoint.metadata.get("schema_fields", ()))
        if latest_checkpoint is not None
        else None
    )

    try:
        while True:
            if accumulator.buffered_rows() >= options.max_buffered_rows:
                result.backpressure_events += 1
                await session.pause(reason="window buffer above threshold")
                await asyncio.sleep(options.pause_seconds)
                await session.resume()

            chunk = await session.poll()
            if chunk is None:
                break

            result.chunks_processed += 1
            clean_rows: list[dict[str, Any]] = []
            chunk_warnings: list[str] = []
            chunk_quarantined = 0
            async for batch in iter_record_batches(chunk.data, batch_size=max(1, int(options.batch_size))):
                valid_rows, warnings, quarantined = sanitize_rows(
                    batch,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    store=sync_store,
                    chunk_index=int(chunk.chunk_index),
                )
                chunk_warnings.extend(warnings)
                chunk_quarantined += quarantined
                for row in valid_rows:
                    dedupe_key = resolve_dedupe_key(row, fields=options.dedupe_key_fields)
                    if dedupe_key in dedupe_seen:
                        result.dedupe_dropped += 1
                        continue
                    dedupe_seen.add(dedupe_key)
                    dedupe_keys.append(dedupe_key)
                    clean_rows.append(row)

            result.warnings.extend(chunk_warnings)
            result.quarantined_rows += chunk_quarantined
            if not clean_rows:
                continue

            current_schema = tuple(sorted({str(key) for row in clean_rows for key in row}))
            if previous_schema is not None and current_schema != previous_schema:
                cdc_ref = await _persist_cdc_schema_change_event_async(
                    store=async_store,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    partition_key=options.partition_key,
                    previous_fields=previous_schema,
                    current_fields=current_schema,
                    observed_at=datetime.now(UTC),
                )
                result.cdc_event_refs.append(cdc_ref)
                result.warnings.append(
                    f"CDC schema change detected for {connector_id}:{dataset_id}: "
                    f"{sorted(set(current_schema) - set(previous_schema)) or ['no added fields']}"
                )
            previous_schema = current_schema

            chunk_ref = await _persist_stream_chunk_async(
                store=async_store,
                connector_id=connector_id,
                dataset_id=dataset_id,
                partition_key=options.partition_key,
                chunk=chunk,
                rows=clean_rows,
                dedupe_dropped=result.dedupe_dropped,
            )
            result.chunk_refs.append(chunk_ref)
            result.rows_emitted += len(clean_rows)

            for assignment in accumulator.add_rows(clean_rows):
                result.window_refs.append(
                    await _persist_stream_window_async(
                        store=async_store,
                        connector_id=connector_id,
                        dataset_id=dataset_id,
                        partition_key=options.partition_key,
                        assignment=assignment,
                        input_ref=chunk_ref,
                    )
                )

            if result.chunks_processed % max(1, int(options.checkpoint_every_chunks)) == 0:
                checkpoint = session.checkpoint(
                    dedupe_keys=tuple(dedupe_keys),
                    schema_fingerprint="|".join(previous_schema),
                )
                checkpoint = checkpoint.model_copy(
                    update={
                        "metadata": {
                            **checkpoint.metadata,
                            "schema_fields": list(previous_schema),
                            "rows_emitted": result.rows_emitted,
                            "window_count": len(result.window_refs),
                            "cdc_event_count": len(result.cdc_event_refs),
                        },
                        "committed_at": datetime.now(UTC),
                    }
                )
                await async_cursor_store.save_stream_checkpoint(checkpoint)
                await session.commit(checkpoint)
                result.final_checkpoint = checkpoint

        for assignment in accumulator.flush():
            result.window_refs.append(
                await _persist_stream_window_async(
                    store=async_store,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    partition_key=options.partition_key,
                    assignment=assignment,
                    input_ref=result.chunk_refs[-1] if result.chunk_refs else None,
                )
            )

        final_checkpoint = session.checkpoint(
            dedupe_keys=tuple(dedupe_keys),
            schema_fingerprint="|".join(previous_schema or ()),
            lifecycle_state=StreamLifecycleState.CLOSED,
        )
        final_checkpoint = final_checkpoint.model_copy(
            update={
                "metadata": {
                    **final_checkpoint.metadata,
                    "schema_fields": list(previous_schema or ()),
                    "rows_emitted": result.rows_emitted,
                    "window_count": len(result.window_refs),
                    "cdc_event_count": len(result.cdc_event_refs),
                },
                "committed_at": datetime.now(UTC),
            }
        )
        final_cursor = CursorState(
            cursor_id=f"{connector_id}:{dataset_id}",
            connector_id=connector_id,
            dataset_id=dataset_id,
            watermark_type=WatermarkType.OFFSET,
            watermark_value=str(final_checkpoint.offset),
            created_at=datetime.now(UTC),
            metadata={
                "partition_key": options.partition_key,
                "window_strategy": options.window_policy.strategy.value,
                "rows_emitted": result.rows_emitted,
                "window_count": len(result.window_refs),
                "cdc_event_count": len(result.cdc_event_refs),
                "backpressure_events": result.backpressure_events,
            },
        )
        cursor_ref, checkpoint_ref = await async_cursor_store.commit_stream_progress(
            cursor=final_cursor,
            checkpoint=final_checkpoint,
        )
        await session.commit(final_checkpoint)
        result.final_checkpoint = final_checkpoint
        result.final_cursor = final_cursor
        result.final_cursor_ref = str(cursor_ref.artifact_id)
        result.final_checkpoint_ref = (
            str(checkpoint_ref.artifact_id) if checkpoint_ref is not None else None
        )
        return result
    except Exception as exc:
        if session.last_chunk is not None:
            checkpoint = session.checkpoint(
                dedupe_keys=tuple(dedupe_keys),
                schema_fingerprint="|".join(previous_schema or ()),
                lifecycle_state=StreamLifecycleState.PAUSED,
            )
            checkpoint = checkpoint.model_copy(
                update={
                    "metadata": {
                        **checkpoint.metadata,
                        "schema_fields": list(previous_schema or ()),
                        "error": str(exc),
                        "rows_emitted": result.rows_emitted,
                    },
                }
            )
            checkpoint_ref = await async_cursor_store.save_stream_checkpoint(checkpoint)
            result.final_checkpoint = checkpoint
            result.final_checkpoint_ref = str(checkpoint_ref.artifact_id)
        raise
    finally:
        await session.close()


async def _persist_stream_chunk_async(
    *,
    store: AsyncArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    chunk: DataChunk[Any],
    rows: list[dict[str, Any]],
    dedupe_dropped: int,
) -> ArtifactRef:
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "chunk_index": int(chunk.chunk_index),
        "row_count": len(rows),
        "bytes_size": int(getattr(chunk, "bytes_size", 0) or 0),
        "resume_token": getattr(chunk, "resume_token", None),
        "is_first": bool(getattr(chunk, "is_first", False)),
        "is_last": bool(getattr(chunk, "is_last", False)),
        "dedupe_dropped": int(dedupe_dropped),
        "data": rows,
    }
    return await store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.stream_chunk",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamChunk", version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


async def _persist_stream_window_async(
    *,
    store: AsyncArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    assignment: WindowAssignment,
    input_ref: ArtifactRef | None,
) -> ArtifactRef:
    inputs = [InputRef(artifact_id=input_ref.artifact_id, role="stream_chunk")] if input_ref is not None else None
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "window_id": assignment.window_id,
        "strategy": assignment.strategy.value,
        "row_count": assignment.row_count,
        "start_at": assignment.start_at,
        "end_at": assignment.end_at,
        "ordinal": assignment.ordinal,
        "data": list(assignment.rows),
    }
    return await store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.stream_window",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamWindow", version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def resolve_dedupe_key(row: dict[str, Any], *, fields: tuple[str, ...]) -> str:
    """Resolve a deterministic dedupe key for exactly-once/effectively-once semantics."""
    for field_name in fields:
        value = row.get(field_name)
        if value not in (None, ""):
            return f"{field_name}:{value!s}"
    return cast(
        "str",
        content_hash(json.dumps(row, sort_keys=True, default=str).encode("utf-8")),
    )


def persist_stream_chunk(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    chunk: DataChunk[Any],
    rows: list[dict[str, Any]],
    dedupe_dropped: int,
) -> ArtifactRef:
    """Persist one cleaned stream chunk as a deterministic CAS artifact."""
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "chunk_index": int(chunk.chunk_index),
        "row_count": len(rows),
        "bytes_size": int(getattr(chunk, "bytes_size", 0) or 0),
        "resume_token": getattr(chunk, "resume_token", None),
        "is_first": bool(getattr(chunk, "is_first", False)),
        "is_last": bool(getattr(chunk, "is_last", False)),
        "dedupe_dropped": int(dedupe_dropped),
        "data": rows,
    }
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.stream_chunk",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamChunk", version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_stream_window(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    assignment: WindowAssignment,
    input_ref: ArtifactRef | None,
) -> ArtifactRef:
    """Persist one logical stream window."""
    inputs = [InputRef(artifact_id=input_ref.artifact_id, role="stream_chunk")] if input_ref is not None else None
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "window_id": assignment.window_id,
        "strategy": assignment.strategy.value,
        "row_count": assignment.row_count,
        "start_at": assignment.start_at,
        "end_at": assignment.end_at,
        "ordinal": assignment.ordinal,
        "data": list(assignment.rows),
    }
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.stream_window",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamWindow", version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


async def _persist_cdc_schema_change_event_async(
    *,
    store: AsyncArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    previous_fields: tuple[str, ...],
    current_fields: tuple[str, ...],
    observed_at: datetime,
) -> ArtifactRef:
    previous = set(previous_fields)
    current = set(current_fields)
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "observed_at": observed_at.isoformat(),
        "previous_fields": list(previous_fields),
        "current_fields": list(current_fields),
        "added_fields": sorted(current - previous),
        "removed_fields": sorted(previous - current),
        "lineage": {
            "source": f"connector.stream:{connector_id}:{dataset_id}",
            "event_type": "schema_change",
        },
        "impact_analysis": {
            "downstream_impacts": [
                "connector_cache",
                "evidence_bundle",
                "data_snapshot",
                "world.materialize",
            ],
            "requires_projection_refresh": True,
            "requires_world_materialization_review": True,
        },
    }
    return await store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.cdc_schema_change",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.CDCSchemaChange", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_cdc_schema_change_event(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    previous_fields: tuple[str, ...],
    current_fields: tuple[str, ...],
    observed_at: datetime,
) -> ArtifactRef:
    """Persist one schema-change event with lineage/impact payloads."""
    previous = set(previous_fields)
    current = set(current_fields)
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "observed_at": observed_at.isoformat(),
        "previous_fields": list(previous_fields),
        "current_fields": list(current_fields),
        "added_fields": sorted(current - previous),
        "removed_fields": sorted(previous - current),
        "lineage": {
            "source": f"connector.stream:{connector_id}:{dataset_id}",
            "event_type": "schema_change",
        },
        "impact_analysis": {
            "downstream_impacts": [
                "connector_cache",
                "evidence_bundle",
                "data_snapshot",
                "world.materialize",
            ],
            "requires_projection_refresh": True,
            "requires_world_materialization_review": True,
        },
    }
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="fabric.cdc_schema_change",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.CDCSchemaChange", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = [
    "StreamDatasetRunResult",
    "StreamRuntimeOptions",
    "StreamingSourceSession",
    "iter_record_batches",
    "normalize_connection_config",
    "persist_cdc_schema_change_event",
    "persist_stream_chunk",
    "persist_stream_window",
    "process_stream_dataset",
    "resolve_dedupe_key",
]
