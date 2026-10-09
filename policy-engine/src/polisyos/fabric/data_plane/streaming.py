"""Event-driven streaming runtime, checkpointing, and CDC helpers."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import deque
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import floor
from typing import TYPE_CHECKING, Any, Literal, cast

from polisyos.common.async_tools import run_blocking_async
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
    is_async_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts.cursor import (
    CursorState,
    StreamCheckpoint,
    StreamLifecycleState,
    WatermarkType,
    WindowStrategy,
)
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.pool import BackpressureLevel, ConnectionPool, PoolConfig
from polisyos.fabric.data_plane.cursor_store import (
    AsyncCursorStoreAdapter,
    CursorStore,
    CursorStoreConflict,
    CursorStoreError,
    _cursor_id,
)
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    persist_quarantine_record,
)
from polisyos.fabric.data_plane.temporal import parse_datetime_utc
from polisyos.fabric.data_plane.watermark import WindowAssignment, WindowPolicy
from polisyos.fabric.quality.processing_guarantees import (
    BackpressureStrategy,
    CDCSchemaCompatibility,
    OutOfOrderHandling,
    ProcessingGuaranteeContract,
    classify_cdc_schema_change,
    processing_contract_snapshot,
    stream_processing_contract,
)
from polisyos.ir.connectors import FetchRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.fabric.connectors.contracts import ConnectorSchemaContract, DataSchema
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.types import DataChunk
else:
    AsyncIterator = Any
    Callable = Any
    DataChunk = Any
    ConnectorRegistryProvider = Any

if TYPE_CHECKING:
    ConnectorRegistryProvider = Callable[[], ConnectorRegistry]


class StreamCapacityError(RuntimeError):
    """Refuse a stream capacity transition without advancing its frontier.

    These limits cover retained operator rows, runtime input materialization,
    and retained output references. They do not describe process RSS or the
    connector's allocation before returning a chunk.
    """

    def __init__(
        self,
        *,
        stage: Literal["restore", "operator", "input", "output"],
        rows: int,
        bytes_size: int,
        max_rows: int,
        max_bytes: int,
        strategy: str,
    ) -> None:
        self.stage = stage
        self.rows = rows
        self.bytes_size = bytes_size
        self.max_rows = max_rows
        self.max_bytes = max_bytes
        self.strategy = strategy
        super().__init__(
            f"stream capacity unsupported at {stage}: rows={rows}/{max_rows} "
            f"bytes={bytes_size}/{max_bytes}; {strategy} cannot enlarge the "
            "budget without a staged spill reader"
        )


class StreamDedupeUnsupported(RuntimeError):
    """Refuse unsupported event-key or persisted ingestion-horizon semantics."""


class _DedupeHorizon:
    """Exact keys retained from first admitted UTC ingestion until expiry.

    Key semantics remain the source owner's responsibility. This index never
    substitutes entity IDs or payload hashes for a configured event/version
    key, and never evicts a live key merely to meet a count budget.
    """

    def __init__(
        self, scope: tuple[str, str, str], fields: tuple[str, ...], seconds: int, cap: int
    ):
        self.scope = scope
        self.fields = fields
        self.seconds = seconds
        self.cap = cap
        self.entries: dict[str, datetime] = {}

    def expire(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.seconds)
        self.entries = {key: at for key, at in self.entries.items() if at > cutoff}

    def remember(self, key: str, now: datetime) -> bool:
        self.expire(now)
        if key in self.entries:
            return False
        if len(self.entries) >= self.cap:
            raise StreamDedupeUnsupported(
                "live event-key capacity exceeded; refusing before eviction; "
                "a durable spill index/reader is not installed"
            )
        self.entries[key] = now
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": 1,
            "scope": list(self.scope),
            "fields": list(self.fields),
            "window_seconds": self.seconds,
            "entries": {key: at.isoformat() for key, at in self.entries.items()},
        }

    def restore(self, state: Any, now: datetime) -> None:
        if (
            not isinstance(state, dict)
            or type(state.get("version")) is not int
            or state["version"] != 1
            or state.get("scope") != list(self.scope)
            or state.get("fields") != list(self.fields)
            or state.get("window_seconds") != self.seconds
            or not isinstance(state.get("entries"), dict)
        ):
            raise StreamDedupeUnsupported("dedupe UTC horizon/scope contract is unavailable")
        for key, raw_at in state["entries"].items():
            try:
                at = datetime.fromisoformat(raw_at)
            except (TypeError, ValueError) as exc:
                raise StreamDedupeUnsupported("invalid persisted UTC ingestion time") from exc
            if not isinstance(key, str) or at.utcoffset() != timedelta(0) or at > now:
                raise StreamDedupeUnsupported("invalid persisted UTC ingestion time or key")
            self.entries[key] = at
        self.expire(now)
        if len(self.entries) > self.cap:
            raise StreamDedupeUnsupported("restored live event-key capacity exceeded")


def _ingestion_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class StreamRuntimeOptions:
    """Runtime controls for bounded, resumable stream processing."""

    partition_key: str = "default"
    batch_size: int = 1_000
    checkpoint_every_chunks: int = 1
    dedupe_key_fields: tuple[str, ...] = ("_message_id",)
    max_dedupe_keys: int = 4_096
    max_buffered_rows: int = 10_000
    max_buffered_bytes: int = 16 * 1024 * 1024
    max_input_rows: int | None = None
    max_input_bytes: int | None = None
    max_output_refs: int = 4_096
    pause_seconds: float = 0.01
    window_policy: WindowPolicy = field(default_factory=WindowPolicy)
    processing_contract: ProcessingGuaranteeContract = field(
        default_factory=stream_processing_contract
    )

    def __post_init__(self) -> None:
        for name in (
            "batch_size",
            "checkpoint_every_chunks",
            "max_dedupe_keys",
            "max_buffered_rows",
            "max_buffered_bytes",
            "max_input_rows",
            "max_input_bytes",
            "max_output_refs",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{name} must be a positive integer")


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
    out_of_order_rows: int = 0
    late_rows_dropped: int = 0
    late_rows_quarantined: int = 0
    processing_guarantee: str = ""
    final_checkpoint: StreamCheckpoint | None = None
    final_cursor: CursorState | None = None
    final_checkpoint_ref: str | None = None
    final_cursor_ref: str | None = None


@dataclass(frozen=True, slots=True)
class StreamSchemaBinding:
    """Frozen source-schema identity carried through one stream run."""

    contract_id: str
    contract_version: str
    contract_content_hash: str
    schema_id: str
    schema_version: str
    schema_content_hash: str
    registry_revision: int
    schema: DataSchema

    @classmethod
    def from_contract(
        cls,
        contract: ConnectorSchemaContract,
        *,
        registry_revision: int,
    ) -> StreamSchemaBinding:
        """Freeze contract and schema identity at stream admission."""
        return cls(
            contract_id=contract.contract_id,
            contract_version=str(contract.schema_version),
            contract_content_hash=contract.content_hash,
            schema_id=contract.schema.schema_id,
            schema_version=str(contract.schema.version),
            schema_content_hash=contract.schema.content_hash,
            registry_revision=registry_revision,
            schema=contract.schema,
        )

    def snapshot(self) -> dict[str, Any]:
        """Return the persisted identity without duplicating the schema body."""
        return {
            "status": "bound",
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "contract_content_hash": self.contract_content_hash,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "schema_content_hash": self.schema_content_hash,
            "registry_revision": self.registry_revision,
        }

    @property
    def fingerprint(self) -> str:
        """Return the contract identity used for checkpoint binding."""
        return self.contract_content_hash


def normalize_connection_config(
    config: ConnectionConfig | dict[str, Any] | None,
) -> ConnectionConfig | None:
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
        registry: ConnectorRegistry | None = None,
    ) -> None:
        self.connector_id = connector_id
        self.dataset_id = dataset_id
        self.partition_key = partition_key
        self.pool = pool
        self.request = request
        self._registry = registry
        self.connector: Any | None = None
        self.handle: Any | None = None
        self._generator: AsyncIterator[DataChunk[Any]] | None = None
        self._subscription: Any = None
        self._paused = False
        self._closed = False
        self._cleanup_pending = False
        self._stream_close_complete = False
        self._close_lock = asyncio.Lock()
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
            registry=resolved_registry,
        )
        try:
            await session.subscribe()
        except BaseException as exc:
            try:
                await session.close()
            except BaseException as cleanup_exc:
                # Startup owns this session until cleanup succeeds.  A second
                # physical cleanup failure is deliberately fail-closed: the
                # original startup error remains authoritative and the note
                # records that the pool owner is still pending.
                exc.add_note(
                    f"stream session startup cleanup remains pending after retry: {cleanup_exc!r}"
                )
            if session._cleanup_pending or session.handle is not None:
                session._retain_cleanup_owner(exc)
            raise
        return session

    async def subscribe(self) -> None:
        """Open the stream subscription and prepare polling."""
        connector, handle = await self.pool.acquire_with_connector()
        self.connector = connector
        self.handle = handle
        try:
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
        except BaseException as exc:
            cleanup_complete = False
            try:
                await self.pool.close_all()
            except BaseException as cleanup_exc:
                exc.add_note(f"stream subscription pool close failed: {cleanup_exc!r}")
                # close_all() deliberately retains the acquired permit when
                # disconnect cannot be confirmed.  Retry through release so a
                # transient physical failure can still complete startup
                # cleanup without making the owner unreachable.
                try:
                    await self.pool.release(handle)
                except BaseException as release_exc:
                    exc.add_note(f"stream subscription release failed: {release_exc!r}")
                else:
                    cleanup_complete = True
            else:
                cleanup_complete = True

            if cleanup_complete:
                self.connector = None
                self.handle = None
                self._closed = True
                self._cleanup_pending = False
            else:
                # Keep the physical handle attached to this session. ``close()`` can
                # retry the pool-owned transition after the primary subscription error.
                self._closed = False
                self._cleanup_pending = True
            self._generator = None
            self._subscription = None
            raise

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
        chunk: DataChunk[Any] | None = None,
        use_observed_chunk: bool = True,
        dedupe_keys: tuple[str, ...] = (),
        schema_fingerprint: str | None = None,
        lifecycle_state: StreamLifecycleState = StreamLifecycleState.ACTIVE,
    ) -> StreamCheckpoint:
        """Build a checkpoint from an explicitly processed or observed position.

        Callers that have durably persisted a chunk pass it explicitly.  The
        fallback to ``_last_chunk`` remains for compatibility with direct
        session users, but it must not be used as an error-handler frontier.
        """
        last_chunk = chunk if chunk is not None or not use_observed_chunk else self._last_chunk
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
                datetime.now(UTC) if lifecycle_state == StreamLifecycleState.CLOSED else None
            ),
        )

    async def commit(self, checkpoint: StreamCheckpoint) -> None:
        """Commit one checkpoint to the source if the connector supports it."""
        if (
            self.connector is not None
            and self.handle is not None
            and hasattr(
                self.connector,
                "commit_stream",
            )
        ):
            await self.connector.commit_stream(self.handle, checkpoint)

    async def rewind(self, checkpoint: StreamCheckpoint) -> None:
        """Rewind the stream to one earlier checkpoint."""
        if (
            self.connector is not None
            and self.handle is not None
            and hasattr(
                self.connector,
                "rewind_stream",
            )
        ):
            await self.connector.rewind_stream(self.handle, checkpoint)
            return

        await self._reconnect()
        resume_offset = checkpoint.offset
        if checkpoint.metadata.get("frontier_committed") is False:
            # The cursor model cannot encode -1.  A diagnostic checkpoint
            # created before the first durable chunk therefore carries an
            # explicit empty-frontier marker and must replay chunk zero.
            resume_offset = -1
        while True:
            chunk = await self.poll()
            if chunk is None:
                break
            if int(chunk.chunk_index) > resume_offset:
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
        if (
            self.connector is not None
            and self.handle is not None
            and hasattr(
                self.connector,
                "pause_stream",
            )
        ):
            await self.connector.pause_stream(self.handle, reason=reason)

    async def resume(self) -> None:
        """Resume polling after backpressure."""
        self._paused = False
        self.pool.clear_backpressure(
            source=f"{self.connector_id}:{self.dataset_id}:{self.partition_key}",
        )
        if (
            self.connector is not None
            and self.handle is not None
            and hasattr(
                self.connector,
                "resume_stream",
            )
        ):
            await self.connector.resume_stream(self.handle)

    def _retain_cleanup_owner(self, error: BaseException) -> None:
        """Keep the exact private pool reachable by the registry's retry owner."""
        if self._registry is None:
            # Directly constructed sessions retain their caller-owned pool.
            return
        try:
            self._registry._retain_pending_startup_cleanup(self.connector_id, self.pool)
        except BaseException as transfer_exc:
            error.add_note(f"stream session cleanup owner transfer failed: {transfer_exc!r}")

    async def close(self) -> None:
        """Close owned resources or retain them for production cleanup retry."""
        async with self._close_lock:
            if self._closed and not self._cleanup_pending:
                return
            try:
                if (
                    self.connector is not None
                    and self.handle is not None
                    and hasattr(self.connector, "close_stream")
                    and not self._stream_close_complete
                    and not self._cleanup_pending
                ):
                    await self.connector.close_stream(self.handle)
                    self._stream_close_complete = True

                if self.handle is not None:
                    await self.pool.release(self.handle)
                    self.connector = None
                    self.handle = None
                await self.pool.close_all()
            except BaseException as exc:
                # Failure and cancellation must leave the same pool/handle under
                # an owner after the process consumer has unwound. No replacement
                # handle, permit release or observer rescue completes this cleanup.
                self._closed = False
                self._cleanup_pending = True
                self._retain_cleanup_owner(exc)
                raise
            self._closed = True
            self._cleanup_pending = False
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
        self._stream_close_complete = False
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


@dataclass(frozen=True)
class _WindowEmission:
    """One emitted window and the raw chunks that contributed its rows."""

    assignment: WindowAssignment
    contributor_refs: tuple[str, ...]


@dataclass(frozen=True)
class _RowRefEntry:
    """Contributor refs bound to the concrete row object, not only its id."""

    row: dict[str, Any]
    refs: tuple[str, ...]


class StreamWindowAccumulator:
    """Incremental window accumulator that keeps buffers bounded."""

    _STATE_VERSION = 1

    def __init__(
        self,
        policy: WindowPolicy,
        *,
        max_rows: int | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self.policy = policy
        self._max_rows = max_rows
        self._max_bytes = max_bytes
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
        # Contributor refs follow the row object through each bounded buffer.
        # They are intentionally kept out of the row payload: input rows are
        # source data, while refs are runtime provenance for the emitted window.
        self._row_refs: dict[int, _RowRefEntry] = {}

    def add_rows(self, rows: list[dict[str, Any]]) -> list[WindowAssignment]:
        assignments: list[WindowAssignment] = []
        for row in rows:
            self._ensure_row_ref_entry(row)
            assignments.extend(self._add_row(row))
        return assignments

    def add_rows_with_refs(
        self,
        rows: list[dict[str, Any]],
        contributor_refs: tuple[str, ...],
    ) -> list[_WindowEmission]:
        """Add rows and return assignments with their actual source refs."""
        return list(self.iter_rows_with_refs(rows, contributor_refs))

    def iter_rows_with_refs(
        self,
        rows: list[dict[str, Any]],
        contributor_refs: tuple[str, ...],
    ) -> Iterator[_WindowEmission]:
        """Emit each window before retaining the next input row's windows."""
        refs = self._validate_refs(contributor_refs)
        for row in rows:
            self._set_row_refs(row, refs)
            for assignment in self._add_row(row):
                yield _WindowEmission(
                    assignment=assignment,
                    contributor_refs=self._refs_for_assignment(assignment),
                )
            self._prune_row_refs()

    def _admit_append(self, row: dict[str, Any]) -> None:
        if self._max_rows is None or self._max_bytes is None:
            return
        _admit_stream_capacity(
            stage="operator",
            rows=self.buffered_rows() + 1,
            bytes_size=self.buffered_bytes() + _estimate_row_bytes(row),
            max_rows=self._max_rows,
            max_bytes=self._max_bytes,
            strategy=self.policy.strategy.value,
        )

    def admit_rows(self, rows: list[dict[str, Any]]) -> int:
        """Exercise the actual transition before publishing its input artifact.

        The preview owns separate bounded containers, sharing the already
        admitted immutable input row objects. It neither copies row payloads
        nor changes this accumulator. No output or frontier is published here.
        """
        preview = copy(self)
        for name, value in vars(self).items():
            if isinstance(value, list | dict | deque | set):
                setattr(preview, name, copy(value))
        return sum(1 for _ in preview.iter_rows_with_refs(rows, ()))

    def flush(self, *, _retain_refs: bool = False) -> list[WindowAssignment]:
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
            self._sliding_time_rows.clear()
            self._next_slide_at = None
        if strategy == WindowStrategy.SLIDING and self._sliding_rows:
            # Count-based sliding windows only emit complete windows during
            # ingestion.  Closing drops the incomplete tail, but it must not
            # remain in the committed operator state and emit again on replay.
            self._sliding_rows.clear()
            self._rows_since_emit = 0
        if not _retain_refs:
            self._prune_row_refs()
        return assignments

    def flush_with_refs(self) -> list[_WindowEmission]:
        """Flush pending windows while retaining all contributor refs."""
        assignments = self.flush(_retain_refs=True)
        emissions = [
            _WindowEmission(
                assignment=assignment,
                contributor_refs=self._refs_for_assignment(assignment),
            )
            for assignment in assignments
        ]
        self._prune_row_refs()
        return emissions

    def snapshot(self) -> dict[str, Any]:
        """Return the versioned operator state required for committed replay."""
        return {
            "version": self._STATE_VERSION,
            "policy": self._policy_snapshot(),
            "ordinal": self._ordinal,
            "rows_since_emit": self._rows_since_emit,
            "bucket_key": self._bucket_key,
            "session_start": (
                self._session_start.isoformat() if self._session_start is not None else None
            ),
            "previous_ts": (
                self._previous_ts.isoformat() if self._previous_ts is not None else None
            ),
            "next_slide_at": (
                self._next_slide_at.isoformat() if self._next_slide_at is not None else None
            ),
            "count_buffer": [self._row_entry(row) for row in self._count_buffer],
            "sliding_rows": [self._row_entry(row) for row in self._sliding_rows],
            "bucket_rows": [self._row_entry(row) for row in self._bucket_rows],
            "session_rows": [self._row_entry(row) for row in self._session_rows],
            "sliding_time_rows": [
                {
                    "row": row,
                    "timestamp": timestamp.isoformat(),
                    "refs": list(self._refs_for_row(row)),
                }
                for row, timestamp in self._sliding_time_rows
            ],
        }

    def restore(self, state: dict[str, Any]) -> None:
        """Restore a committed state or fail closed on an incomplete state."""
        try:
            if not isinstance(state, dict) or state.get("version") != self._STATE_VERSION:
                raise ValueError("unsupported stream operator state version")
            if state.get("policy") != self._policy_snapshot():
                raise ValueError("stream operator policy does not match checkpoint")

            self._row_refs = {}
            self._ordinal = int(state["ordinal"])
            self._rows_since_emit = int(state["rows_since_emit"])
            bucket_key = state["bucket_key"]
            if bucket_key is not None and not isinstance(bucket_key, int):
                raise TypeError("bucket_key must be an integer or null")
            self._bucket_key = bucket_key
            self._session_start = self._parse_state_timestamp(state["session_start"])
            self._previous_ts = self._parse_state_timestamp(state["previous_ts"])
            self._next_slide_at = self._parse_state_timestamp(state["next_slide_at"])
            self._count_buffer = self._restore_row_entries(state["count_buffer"])
            self._sliding_rows = deque(self._restore_row_entries(state["sliding_rows"]))
            self._bucket_rows = self._restore_row_entries(state["bucket_rows"])
            self._session_rows = self._restore_row_entries(state["session_rows"])

            sliding_time_rows: list[tuple[dict[str, Any], datetime]] = []
            raw_sliding_time_rows = state["sliding_time_rows"]
            if not isinstance(raw_sliding_time_rows, list):
                raise TypeError("sliding_time_rows must be a list")
            for entry in raw_sliding_time_rows:
                if not isinstance(entry, dict) or not isinstance(entry.get("row"), dict):
                    raise TypeError("invalid sliding-time row entry")
                row = dict(entry["row"])
                refs = self._validate_refs(entry.get("refs"))
                self._set_row_refs(row, refs)
                timestamp = self._parse_state_timestamp(entry.get("timestamp"))
                if timestamp is None:
                    raise ValueError("sliding-time row is missing timestamp")
                sliding_time_rows.append((row, timestamp))
            self._sliding_time_rows = deque(sliding_time_rows)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("corrupt stream operator state") from exc

    def _policy_snapshot(self) -> dict[str, Any]:
        return {
            "strategy": self.policy.strategy.value,
            "size": self.policy.size,
            "slide": self.policy.slide,
            "session_gap_seconds": self.policy.session_gap_seconds,
            "timestamp_field": self.policy.timestamp_field,
        }

    def _row_entry(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "row": row,
            "refs": list(self._refs_for_row(row)),
        }

    def _restore_row_entries(self, entries: Any) -> list[dict[str, Any]]:
        if not isinstance(entries, list):
            raise TypeError("row entries must be a list")
        rows: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("row"), dict):
                raise TypeError("invalid row entry")
            row = dict(entry["row"])
            self._set_row_refs(row, self._validate_refs(entry.get("refs")))
            rows.append(row)
        return rows

    @staticmethod
    def _validate_refs(refs: Any) -> tuple[str, ...]:
        if not isinstance(refs, list | tuple):
            raise TypeError("row contributor refs must be a list")
        if any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError("row contributor refs cannot be empty")
        return tuple(dict.fromkeys(refs))

    @staticmethod
    def _parse_state_timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        return parse_datetime_utc(str(value), what="stream operator timestamp")

    def _refs_for_assignment(self, assignment: WindowAssignment) -> tuple[str, ...]:
        refs: list[str] = []
        for row in assignment.rows:
            for ref in self._refs_for_row(row):
                if ref not in refs:
                    refs.append(ref)
        return tuple(refs)

    def _ensure_row_ref_entry(self, row: dict[str, Any]) -> None:
        entry = self._row_refs.get(id(row))
        if not isinstance(entry, _RowRefEntry) or entry.row is not row:
            self._row_refs[id(row)] = _RowRefEntry(row=row, refs=())

    def _set_row_refs(self, row: dict[str, Any], refs: tuple[str, ...]) -> None:
        self._row_refs[id(row)] = _RowRefEntry(row=row, refs=refs)

    def _refs_for_row(self, row: dict[str, Any]) -> tuple[str, ...]:
        entry = self._row_refs.get(id(row))
        if not isinstance(entry, _RowRefEntry) or entry.row is not row:
            return ()
        return entry.refs

    def _prune_row_refs(self) -> None:
        live_rows = {id(row): row for row in self._buffered_row_objects()}
        self._row_refs = {
            row_id: entry
            for row_id, entry in self._row_refs.items()
            if isinstance(entry, _RowRefEntry) and live_rows.get(row_id) is entry.row
        }

    def _buffered_row_objects(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._count_buffer)
        rows.extend(self._bucket_rows)
        rows.extend(self._session_rows)
        rows.extend(self._sliding_rows)
        rows.extend(row for row, _timestamp in self._sliding_time_rows)
        return rows

    def buffered_rows(self) -> int:
        return (
            len(self._count_buffer)
            + len(self._bucket_rows)
            + len(self._session_rows)
            + len(self._sliding_rows)
            + len(self._sliding_time_rows)
        )

    def buffered_bytes(self) -> int:
        rows: list[dict[str, Any]] = []
        rows.extend(self._count_buffer)
        rows.extend(self._bucket_rows)
        rows.extend(self._session_rows)
        rows.extend(self._sliding_rows)
        rows.extend(row for row, _ts in self._sliding_time_rows)
        return sum(_estimate_row_bytes(row) for row in rows)

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
        self._admit_append(row)
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
            self._bucket_rows = []
            self._admit_append(row)
            self._bucket_rows = [row]
            self._bucket_key = bucket_key
            return [assignment]
        self._admit_append(row)
        self._bucket_rows.append(row)
        return []

    def _emit_bucket_window(self) -> WindowAssignment:
        if self._bucket_key is None:
            raise RuntimeError("cannot emit a bucket window before assigning a bucket key")
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
            self._admit_append(row)
            self._session_rows.append(row)
            return []
        gap_seconds = float(self.policy.session_gap_seconds or self.policy.size or 60.0)
        if self._session_start is None:
            self._session_start = ts
        if self._previous_ts is not None and (ts - self._previous_ts).total_seconds() > gap_seconds:
            assignment = self._emit_session_window()
            self._session_rows = []
            self._admit_append(row)
            self._session_rows = [row]
            self._session_start = ts
            self._previous_ts = ts
            return [assignment]
        self._admit_append(row)
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
        while len(self._sliding_rows) >= size:
            self._sliding_rows.popleft()
        self._admit_append(row)
        self._sliding_rows.append(row)
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
        while (
            self._sliding_time_rows
            and (ts - self._sliding_time_rows[0][1]).total_seconds() > window_seconds
        ):
            self._sliding_time_rows.popleft()
        self._admit_append(row)
        self._sliding_time_rows.append((row, ts))
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


def _estimate_row_bytes(row: object) -> int:
    return len(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))


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


@dataclass
class _StreamOrderingState:
    max_event_time: datetime | None = None


def _stream_operator_state(
    accumulator: StreamWindowAccumulator,
    ordering_state: _StreamOrderingState,
) -> dict[str, Any]:
    """Capture the window and ordering state at one durable frontier."""
    return {
        "version": 1,
        "accumulator": accumulator.snapshot(),
        "max_event_time": (
            ordering_state.max_event_time.isoformat()
            if ordering_state.max_event_time is not None
            else None
        ),
    }


def _restore_stream_operator_state(
    state: Any,
    *,
    accumulator: StreamWindowAccumulator,
    ordering_state: _StreamOrderingState,
) -> None:
    """Restore a complete operator state, rejecting missing/corrupt state."""
    if not isinstance(state, dict) or state.get("version") != 1:
        raise CursorStoreError("missing or unsupported stream operator state")
    try:
        accumulator.restore(state["accumulator"])
        if "max_event_time" not in state:
            raise CursorStoreError("stream operator state is missing max_event_time")
        max_event_time = state["max_event_time"]
        ordering_state.max_event_time = (
            parse_datetime_utc(str(max_event_time), what="stream ordering watermark")
            if max_event_time is not None
            else None
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CursorStoreError("corrupt stream operator state") from exc


def _empty_stream_operator_state(policy: WindowPolicy) -> dict[str, Any]:
    """Build an explicit empty state for a stream with no committed rows."""
    return _stream_operator_state(
        StreamWindowAccumulator(policy),
        _StreamOrderingState(),
    )


def _stream_checkpoint_metadata(
    *,
    accumulator: StreamWindowAccumulator,
    ordering_state: _StreamOrderingState,
    previous_schema: tuple[str, ...] | None,
    visible_schema: tuple[str, ...] | None,
    schema_binding: StreamSchemaBinding | None,
    result: StreamDatasetRunResult,
    processing_contract: ProcessingGuaranteeContract,
    dedupe_horizon: _DedupeHorizon,
) -> dict[str, Any]:
    """Build metadata whose operator state matches the committed outputs."""
    return {
        "schema_fields": list(previous_schema or ()),
        "declared_schema_fields": list(
            schema_binding.schema.field_names() if schema_binding is not None else ()
        ),
        "visible_fields": list(visible_schema or previous_schema or ()),
        "schema_binding": (
            schema_binding.snapshot()
            if schema_binding is not None
            else {"status": "not_established"}
        ),
        "rows_emitted": result.rows_emitted,
        "window_count": len(result.window_refs),
        "cdc_event_count": len(result.cdc_event_refs),
        "processing": processing_contract_snapshot(processing_contract),
        "out_of_order_rows": result.out_of_order_rows,
        "late_rows_dropped": result.late_rows_dropped,
        "late_rows_quarantined": result.late_rows_quarantined,
        "operator_state_required": True,
        "operator_state": _stream_operator_state(accumulator, ordering_state),
        "frontier_committed": True,
        "dedupe_horizon": dedupe_horizon.snapshot(),
    }


def _stream_cursor_for_checkpoint(
    *,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    checkpoint: StreamCheckpoint,
    result: StreamDatasetRunResult,
    processing_contract: ProcessingGuaranteeContract,
    window_policy: WindowPolicy,
) -> CursorState:
    """Build the cursor paired with one durable stream checkpoint."""
    return CursorState(
        cursor_id=_cursor_id(
            connector_id,
            dataset_id,
            partition_key=partition_key,
        ),
        connector_id=connector_id,
        dataset_id=dataset_id,
        watermark_type=WatermarkType.OFFSET,
        watermark_value=str(checkpoint.offset),
        created_at=datetime.now(UTC),
        metadata={
            "partition_key": partition_key,
            "window_strategy": window_policy.strategy.value,
            "rows_emitted": result.rows_emitted,
            "window_count": len(result.window_refs),
            "cdc_event_count": len(result.cdc_event_refs),
            "backpressure_events": result.backpressure_events,
            "out_of_order_rows": result.out_of_order_rows,
            "late_rows_dropped": result.late_rows_dropped,
            "late_rows_quarantined": result.late_rows_quarantined,
            "processing": processing_contract_snapshot(processing_contract),
        },
    )


_STREAM_FRONTIER_INTENT_VERSION = 1


def _stream_frontier_digest(
    checkpoint: StreamCheckpoint,
    cursor: CursorState,
) -> str:
    """Hash the stable target identity independent of intent lifecycle bytes."""
    checkpoint_payload = checkpoint.model_dump(mode="json")
    for field_name in ("created_at", "committed_at", "lifecycle_state"):
        checkpoint_payload.pop(field_name, None)
    metadata = dict(checkpoint_payload.get("metadata", {}))
    for field_name in (
        "frontier_intent",
        "frontier_committed",
        "error",
        "observed_offset",
        "observed_resume_token",
    ):
        metadata.pop(field_name, None)
    checkpoint_payload["metadata"] = metadata
    return fingerprint(
        {
            "checkpoint": checkpoint_payload,
            "cursor": cursor.model_dump(mode="json"),
        },
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _stream_frontier_intent(
    *,
    checkpoint: StreamCheckpoint,
    cursor: CursorState,
    previous_checkpoint: StreamCheckpoint | None,
    previous_cursor: CursorState | None,
) -> dict[str, Any]:
    """Describe one source/local frontier promotion attempt."""
    target_digest = _stream_frontier_digest(checkpoint, cursor)
    prior_digest = (
        _stream_frontier_digest(previous_checkpoint, previous_cursor)
        if previous_checkpoint is not None and previous_cursor is not None
        else None
    )
    return {
        "version": _STREAM_FRONTIER_INTENT_VERSION,
        "state": "prepared",
        "intent_id": f"{checkpoint.stream_id}:{checkpoint.checkpoint_id}:{target_digest}",
        "prior_checkpoint_id": (
            previous_checkpoint.checkpoint_id if previous_checkpoint is not None else None
        ),
        "prior_cursor_id": previous_cursor.cursor_id if previous_cursor is not None else None,
        "prior_digest": prior_digest,
        "target_checkpoint_id": checkpoint.checkpoint_id,
        "target_cursor_id": cursor.cursor_id,
        "target_digest": target_digest,
    }


def _stream_frontier_marker(
    checkpoint: StreamCheckpoint,
    *,
    intent: dict[str, Any],
    state: str,
    error: BaseException | None = None,
) -> StreamCheckpoint:
    """Apply one prepared/unresolved/committed intent state to a checkpoint."""
    metadata = dict(checkpoint.metadata)
    metadata["frontier_intent"] = {**intent, "state": state}
    metadata["frontier_committed"] = state == "committed"
    if error is not None:
        metadata["error"] = str(error)
    return checkpoint.model_copy(
        update={
            "lifecycle_state": (
                checkpoint.lifecycle_state if state == "committed" else StreamLifecycleState.PAUSED
            ),
            "committed_at": (checkpoint.committed_at if state == "committed" else None),
            "metadata": metadata,
        }
    )


def _empty_stream_frontier_checkpoint(
    session: StreamingSourceSession,
    *,
    operator_state: dict[str, Any],
) -> StreamCheckpoint:
    """Build an explicit empty frontier for source compensation."""
    checkpoint = session.checkpoint(
        chunk=None,
        use_observed_chunk=False,
        dedupe_keys=(),
        schema_fingerprint="",
        lifecycle_state=StreamLifecycleState.PAUSED,
    )
    return checkpoint.model_copy(
        update={
            "metadata": {
                "schema_fields": [],
                "rows_emitted": 0,
                "window_count": 0,
                "cdc_event_count": 0,
                "operator_state_required": True,
                "operator_state": operator_state,
                "frontier_committed": False,
            }
        }
    )


async def _prepare_stream_frontier(
    *,
    async_cursor_store: AsyncCursorStoreAdapter,
    checkpoint: StreamCheckpoint,
    cursor: CursorState,
    previous_checkpoint: StreamCheckpoint | None,
    previous_cursor: CursorState | None,
) -> tuple[StreamCheckpoint, dict[str, Any]]:
    """Durably record a prepared marker before touching the source."""
    intent = _stream_frontier_intent(
        checkpoint=checkpoint,
        cursor=cursor,
        previous_checkpoint=previous_checkpoint,
        previous_cursor=previous_cursor,
    )
    prepared = _stream_frontier_marker(
        checkpoint,
        intent=intent,
        state="prepared",
    )
    await async_cursor_store.save_stream_checkpoint(prepared)
    return prepared, intent


async def _save_unresolved_frontier(
    *,
    async_cursor_store: AsyncCursorStoreAdapter,
    base_checkpoint: StreamCheckpoint,
    intent: dict[str, Any],
    error: BaseException,
) -> None:
    """Best-effort persist of an unresolved intent that blocks silent resume."""
    unresolved = _stream_frontier_marker(
        base_checkpoint,
        intent=intent,
        state="unresolved",
        error=error,
    )
    try:
        await async_cursor_store.save_stream_checkpoint(unresolved)
    except Exception as marker_exc:
        error.add_note(f"unresolved stream frontier marker could not be persisted: {marker_exc!r}")


async def _verify_prepared_frontier(
    *,
    async_cursor_store: AsyncCursorStoreAdapter,
    checkpoint: StreamCheckpoint,
    cursor: CursorState,
    intent: dict[str, Any],
) -> None:
    """Verify both local latest indices still point at the prepared target."""
    latest_checkpoint = await async_cursor_store.find_latest_stream_checkpoint(
        checkpoint.connector_id,
        checkpoint.dataset_id,
        partition_key=checkpoint.partition_key,
    )
    latest_cursor = await async_cursor_store.find_latest_cursor(
        cursor.connector_id,
        cursor.dataset_id,
        partition_key=checkpoint.partition_key,
    )
    expected_intent = {**intent, "state": "prepared"}
    if latest_checkpoint is None or latest_cursor is None:
        raise CursorStoreError("prepared stream frontier is missing a local side")
    if latest_checkpoint.checkpoint_id != checkpoint.checkpoint_id:
        raise CursorStoreError("prepared stream checkpoint identity changed")
    if latest_cursor.cursor_id != cursor.cursor_id:
        raise CursorStoreError("prepared stream cursor identity changed")
    if latest_cursor.watermark_value != str(checkpoint.offset):
        raise CursorStoreError("prepared stream cursor offset changed")
    if latest_checkpoint.metadata.get("frontier_intent") != expected_intent:
        raise CursorStoreError("prepared stream frontier intent changed")
    if latest_checkpoint.metadata.get("frontier_committed") is not False:
        raise CursorStoreError("prepared stream frontier was promoted early")
    if _stream_frontier_digest(latest_checkpoint, latest_cursor) != intent["target_digest"]:
        raise CursorStoreError("prepared stream frontier digest changed")


def _validated_frontier_intent(
    checkpoint: StreamCheckpoint,
) -> dict[str, Any] | None:
    """Validate the versioned intent marker before source recovery."""
    raw_intent = checkpoint.metadata.get("frontier_intent")
    if raw_intent is None:
        return None
    if not isinstance(raw_intent, dict):
        raise CursorStoreError("corrupt stream frontier intent")
    required = {
        "version",
        "state",
        "intent_id",
        "prior_checkpoint_id",
        "prior_cursor_id",
        "prior_digest",
        "target_checkpoint_id",
        "target_cursor_id",
        "target_digest",
    }
    if raw_intent.get("version") != _STREAM_FRONTIER_INTENT_VERSION or not required <= set(
        raw_intent
    ):
        raise CursorStoreError("corrupt stream frontier intent")
    state = raw_intent["state"]
    if state != "committed" or checkpoint.metadata.get("frontier_committed") is not True:
        raise CursorStoreError("unresolved stream frontier intent")
    if raw_intent["target_checkpoint_id"] != checkpoint.checkpoint_id:
        raise CursorStoreError("stream frontier intent target mismatch")
    return dict(raw_intent)


async def _verify_committed_frontier(
    *,
    async_cursor_store: AsyncCursorStoreAdapter,
    checkpoint: StreamCheckpoint,
    intent: dict[str, Any],
) -> None:
    """Verify a committed marker still has its paired local cursor."""
    cursor = await async_cursor_store.find_latest_cursor(
        checkpoint.connector_id,
        checkpoint.dataset_id,
        partition_key=checkpoint.partition_key,
    )
    if cursor is None:
        raise CursorStoreError("committed stream frontier is missing its cursor")
    if cursor.cursor_id != intent["target_cursor_id"]:
        raise CursorStoreError("committed stream frontier cursor identity mismatch")
    if cursor.watermark_value != str(checkpoint.offset):
        raise CursorStoreError("committed stream frontier cursor offset mismatch")
    if _stream_frontier_digest(checkpoint, cursor) != intent["target_digest"]:
        raise CursorStoreError("committed stream frontier digest mismatch")


async def _restore_local_frontier(
    *,
    async_cursor_store: AsyncCursorStoreAdapter,
    previous_checkpoint: StreamCheckpoint | None,
    previous_cursor: CursorState | None,
    target_cursor: CursorState,
    target_checkpoint: StreamCheckpoint,
    empty_frontier: StreamCheckpoint,
) -> None:
    """Restore the last local pair, or the explicit empty frontier."""
    await async_cursor_store.restore_stream_frontier(
        expected_cursor=target_cursor,
        expected_checkpoint=target_checkpoint,
        restore_cursor=previous_cursor,
        restore_checkpoint=previous_checkpoint or empty_frontier,
    )


async def _commit_stream_frontier(
    *,
    session: StreamingSourceSession,
    async_cursor_store: AsyncCursorStoreAdapter,
    cursor: CursorState,
    checkpoint: StreamCheckpoint,
    prepared_checkpoint: StreamCheckpoint,
    intent: dict[str, Any],
    previous_checkpoint: StreamCheckpoint | None,
    previous_cursor: CursorState | None,
    empty_frontier: StreamCheckpoint,
) -> tuple[ArtifactRef, ArtifactRef | None, StreamCheckpoint]:
    """Promote a prepared frontier with fail-closed source compensation.

    The prepared marker remains latest through source commit, local pair
    persistence, and verification.  Only after both local sides are verified
    is a committed marker written.  This is at-least-once with dedupe, not a
    cross-system exactly-once transaction.
    """
    try:
        # Source adapters receive the source-neutral prepared representation;
        # the local ``frontier_committed`` marker is promoted only after both
        # local indices are persisted and verified.
        await session.commit(prepared_checkpoint)
    except Exception as exc:
        await _save_unresolved_frontier(
            async_cursor_store=async_cursor_store,
            base_checkpoint=previous_checkpoint or empty_frontier,
            intent=intent,
            error=exc,
        )
        exc.add_note("local stream frontier was not promoted after source commit failure")
        raise

    try:
        refs = await async_cursor_store.commit_stream_progress(
            cursor=cursor,
            checkpoint=prepared_checkpoint,
        )
        await _verify_prepared_frontier(
            async_cursor_store=async_cursor_store,
            checkpoint=checkpoint,
            cursor=cursor,
            intent=intent,
        )
    except Exception as exc:
        compensation_checkpoint = previous_checkpoint or empty_frontier
        try:
            await session.rewind(compensation_checkpoint)
            await _restore_local_frontier(
                async_cursor_store=async_cursor_store,
                previous_checkpoint=previous_checkpoint,
                previous_cursor=previous_cursor,
                target_cursor=cursor,
                target_checkpoint=prepared_checkpoint,
                empty_frontier=empty_frontier,
            )
        except CursorStoreConflict as compensation_exc:
            exc.add_note(
                "source compensation found a changed cursor/checkpoint pair; "
                f"newer local frontier preserved: {compensation_exc!r}"
            )
        except Exception as compensation_exc:
            await _save_unresolved_frontier(
                async_cursor_store=async_cursor_store,
                base_checkpoint=prepared_checkpoint,
                intent=intent,
                error=compensation_exc,
            )
            exc.add_note(
                f"source compensation or local frontier restore failed: {compensation_exc!r}"
            )
        else:
            exc.add_note("source compensation rewind restored the previous local frontier")
        raise

    committed_checkpoint = _stream_frontier_marker(
        checkpoint,
        intent=intent,
        state="committed",
    )
    try:
        committed_ref = await async_cursor_store.save_stream_checkpoint(committed_checkpoint)
    except Exception as exc:
        await _save_unresolved_frontier(
            async_cursor_store=async_cursor_store,
            base_checkpoint=prepared_checkpoint,
            intent=intent,
            error=exc,
        )
        exc.add_note("committed stream frontier marker could not be persisted")
        raise
    return refs[0], committed_ref, committed_checkpoint


def _window_policy_snapshot(
    policy: WindowPolicy | None,
    *,
    fallback_strategy: WindowStrategy,
) -> dict[str, Any]:
    """Return a versioned window-policy identity for emitted artifacts."""
    return {
        "version": 1,
        "strategy": (policy.strategy if policy is not None else fallback_strategy).value,
        "size": policy.size if policy is not None else None,
        "slide": policy.slide if policy is not None else None,
        "session_gap_seconds": policy.session_gap_seconds if policy is not None else None,
        "timestamp_field": policy.timestamp_field if policy is not None else None,
    }


def _effective_processing_contract(
    options: StreamRuntimeOptions,
) -> ProcessingGuaranteeContract:
    idempotency = options.processing_contract.idempotency.model_copy(
        update={
            "key_fields": tuple(options.dedupe_key_fields),
            "max_dedupe_keys": max(1, int(options.max_dedupe_keys)),
            "missing_key_action": "reject",
        }
    )
    backpressure = options.processing_contract.backpressure.model_copy(
        update={
            "max_buffered_rows": max(1, int(options.max_buffered_rows)),
            "max_buffered_bytes": max(1, int(options.max_buffered_bytes)),
            "pause_seconds": max(0.0, float(options.pause_seconds)),
        }
    )
    return options.processing_contract.model_copy(
        update={
            "idempotency": idempotency,
            "backpressure": backpressure,
        }
    )


def _apply_out_of_order_policy(
    rows: list[dict[str, Any]],
    *,
    policy: Any,
    state: _StreamOrderingState,
) -> tuple[list[dict[str, Any]], list[str], int, int, int]:
    if not rows:
        return [], [], 0, 0, 0
    accepted: list[tuple[dict[str, Any], datetime | None]] = []
    warnings: list[str] = []
    dropped = 0
    quarantined = 0
    out_of_order = 0

    for row in rows:
        ts = _row_event_time(row, policy.timestamp_field)
        late = False
        too_late = False
        if ts is not None and state.max_event_time is not None and ts < state.max_event_time:
            late = True
            out_of_order += 1
            too_late = (state.max_event_time - ts).total_seconds() > float(
                policy.max_lateness_seconds
            )
        if ts is not None and (state.max_event_time is None or ts > state.max_event_time):
            state.max_event_time = ts

        if not late:
            accepted.append((row, ts))
            continue

        handling = OutOfOrderHandling(policy.handling)
        action = (
            OutOfOrderHandling(policy.late_event_action)
            if handling == OutOfOrderHandling.WATERMARK and too_late
            else handling
        )
        if action == OutOfOrderHandling.DROP:
            dropped += 1
            warnings.append("out-of-order event dropped")
            continue
        if action == OutOfOrderHandling.QUARANTINE:
            quarantined += 1
            warnings.append("out-of-order event quarantined")
            continue
        accepted.append((row, ts))

    if OutOfOrderHandling(policy.handling) == OutOfOrderHandling.REORDER:
        accepted.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=UTC))
    return [row for row, _ts in accepted], warnings, dropped, quarantined, out_of_order


def _row_event_time(row: dict[str, Any], timestamp_field: str) -> datetime | None:
    value = (
        row.get(timestamp_field)
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
        parse_datetime_utc(str(value), what="stream ordering timestamp"),
    )


def _cdc_handling_action(
    compatibility: CDCSchemaCompatibility,
    processing_contract: ProcessingGuaranteeContract,
) -> str:
    policy = processing_contract.cdc_schema_changes
    if compatibility == CDCSchemaCompatibility.COMPATIBLE_ADDITIVE:
        return policy.additive_change_action
    if compatibility == CDCSchemaCompatibility.INCOMPATIBLE_BREAKING:
        return policy.breaking_change_action
    if compatibility == CDCSchemaCompatibility.METADATA_ONLY:
        return policy.metadata_only_action
    return "review"


def _should_quarantine_cdc_schema_change(
    compatibility: CDCSchemaCompatibility,
    handling_action: str,
) -> bool:
    return (
        compatibility == CDCSchemaCompatibility.INCOMPATIBLE_BREAKING
        and handling_action == "quarantine"
    )


def _should_fail_closed_cdc_schema_change(
    compatibility: CDCSchemaCompatibility,
    handling_action: str,
) -> bool:
    return (
        compatibility == CDCSchemaCompatibility.INCOMPATIBLE_BREAKING
        and handling_action == "fail_closed"
    )


def _resolve_stream_schema_binding(
    registry: ConnectorRegistry | None,
    *,
    connector_id: str,
    dataset_id: str,
) -> StreamSchemaBinding | None:
    """Resolve one frozen contract binding without creating a second registry."""
    if registry is None:
        return None
    resolver = getattr(registry, "resolve_schema_contract", None)
    if resolver is None:
        return None
    contract, revision = resolver(connector_id=connector_id, dataset_id=dataset_id)
    if contract is None:
        return None
    return StreamSchemaBinding.from_contract(
        contract,
        registry_revision=int(revision),
    )


def _stream_schema_fingerprint(
    schema_binding: StreamSchemaBinding | None,
    fields: tuple[str, ...] | None,
) -> str:
    """Return a stable contract fingerprint, retaining legacy unknown fallback."""
    if schema_binding is not None:
        return schema_binding.fingerprint
    return "|".join(fields or ())


def _assert_stream_schema_binding_current(
    registry: ConnectorRegistry | None,
    schema_binding: StreamSchemaBinding | None,
    *,
    connector_id: str,
    dataset_id: str,
) -> None:
    """Reject a registry change instead of committing mixed-contract output."""
    if registry is None or schema_binding is None:
        return
    current = _resolve_stream_schema_binding(
        registry,
        connector_id=connector_id,
        dataset_id=dataset_id,
    )
    if current is None or current.snapshot() != schema_binding.snapshot():
        raise CursorStoreError(
            "stream schema binding changed during processing; refusing mixed-contract commit"
        )


def _admit_stream_capacity(
    *,
    stage: Literal["restore", "operator", "input", "output"],
    rows: int,
    bytes_size: int,
    max_rows: int,
    max_bytes: int,
    strategy: str,
) -> None:
    if rows > max_rows or bytes_size > max_bytes:
        raise StreamCapacityError(
            stage=stage,
            rows=rows,
            bytes_size=bytes_size,
            max_rows=max_rows,
            max_bytes=max_bytes,
            strategy=strategy,
        )


def _admit_restored_operator_state(
    state: Any,
    *,
    options: StreamRuntimeOptions,
    contract: ProcessingGuaranteeContract,
) -> None:
    """Inspect persisted rows before copying them into a live accumulator."""
    if not isinstance(state, dict):
        raise ValueError("corrupt stream operator state")
    accumulator = state.get("accumulator")
    if not isinstance(accumulator, dict):
        raise ValueError("corrupt stream operator state")
    rows = bytes_size = 0
    refs: set[str] = set()
    for name in (
        "count_buffer",
        "sliding_rows",
        "bucket_rows",
        "session_rows",
        "sliding_time_rows",
    ):
        entries = accumulator.get(name)
        if not isinstance(entries, list):
            raise ValueError("corrupt stream operator state")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("row"), dict):
                raise ValueError("corrupt stream operator state")
            rows += 1
            bytes_size += _estimate_row_bytes(entry["row"])
            refs.update(StreamWindowAccumulator._validate_refs(entry.get("refs")))
            _admit_stream_capacity(
                stage="restore",
                rows=rows,
                bytes_size=bytes_size,
                max_rows=contract.backpressure.max_buffered_rows,
                max_bytes=contract.backpressure.max_buffered_bytes,
                strategy=str(contract.backpressure.strategy),
            )
            _admit_stream_capacity(
                stage="output",
                rows=len(refs),
                bytes_size=0,
                max_rows=options.max_output_refs,
                max_bytes=1,
                strategy=str(contract.backpressure.strategy),
            )


def _admit_stream_input(payload: Any, options: StreamRuntimeOptions) -> None:
    """Bound the returned source payload before runtime batch materialization.

    Source allocation before returning the payload is outside this boundary.
    Counts come from the actual payload, never DataChunk's declared counters.
    """
    max_rows = options.max_input_rows or options.max_buffered_rows
    max_bytes = options.max_input_bytes or options.max_buffered_bytes
    if hasattr(payload, "itertuples") and hasattr(payload, "columns"):
        count = len(payload.index)
        _admit_stream_capacity(
            stage="input",
            rows=count,
            bytes_size=0,
            max_rows=max_rows,
            max_bytes=max_bytes,
            strategy="bounded_input",
        )
        names = tuple(str(name) for name in payload.columns)
        source_rows = (
            dict(zip(names, row, strict=True)) for row in payload.itertuples(index=False, name=None)
        )
    elif isinstance(payload, list):
        _admit_stream_capacity(
            stage="input",
            rows=len(payload),
            bytes_size=0,
            max_rows=max_rows,
            max_bytes=max_bytes,
            strategy="bounded_input",
        )
        source_rows = iter(payload)
    else:
        source_rows = iter((payload,))
    bytes_size = 0
    for ordinal, row in enumerate(source_rows, 1):
        bytes_size += _estimate_row_bytes(row)
        _admit_stream_capacity(
            stage="input",
            rows=ordinal,
            bytes_size=bytes_size,
            max_rows=max_rows,
            max_bytes=max_bytes,
            strategy="bounded_input",
        )


def _admit_output_ref(
    result: StreamDatasetRunResult,
    options: StreamRuntimeOptions,
    *,
    additional_count: int = 1,
) -> None:
    count = len(result.chunk_refs) + len(result.window_refs) + len(result.cdc_event_refs)
    _admit_stream_capacity(
        stage="output",
        rows=count + additional_count,
        bytes_size=0,
        max_rows=options.max_output_refs,
        max_bytes=1,
        strategy="retained_output_refs",
    )


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
    schema_binding: StreamSchemaBinding | None = None,
) -> StreamDatasetRunResult:
    """Process one streamed dataset with checkpoint recovery and bounded buffering."""
    options = runtime_options or StreamRuntimeOptions()
    processing_contract = _effective_processing_contract(options)
    async_store = _ensure_async_store(store)
    sync_store = _resolve_sync_store(store, async_store)
    if sync_store is None:
        raise TypeError(
            "process_stream_dataset requires a sync ArtifactStore companion for row sanitization"
        )
    async_cursor_store = _ensure_async_cursor_store(cursor_store)
    if schema_binding is None:
        schema_binding = _resolve_stream_schema_binding(
            registry,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
    session = await StreamingSourceSession.create(
        connector_id=connector_id,
        dataset_id=dataset_id,
        connection_config=connection_config,
        partition_key=options.partition_key,
        registry=registry,
        registry_provider=registry_provider,
    )
    try:
        result = StreamDatasetRunResult(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key=options.partition_key,
            processing_guarantee=processing_contract.guarantee_value,
        )
        accumulator = StreamWindowAccumulator(
            options.window_policy,
            max_rows=processing_contract.backpressure.max_buffered_rows,
            max_bytes=processing_contract.backpressure.max_buffered_bytes,
        )
        ordering_state = _StreamOrderingState()
        dedupe_horizon = _DedupeHorizon(
            (connector_id, dataset_id, options.partition_key),
            processing_contract.idempotency.key_fields,
            processing_contract.idempotency.dedupe_window_seconds,
            processing_contract.idempotency.max_dedupe_keys,
        )
        previous_schema: tuple[str, ...] | None = None
        visible_schema: tuple[str, ...] | None = None
        committed_checkpoint: StreamCheckpoint | None = None
        committed_cursor: CursorState | None = None
        empty_frontier = _empty_stream_frontier_checkpoint(
            session,
            operator_state=_empty_stream_operator_state(options.window_policy),
        )
        pending_frontier: StreamCheckpoint | None = None
        latest_checkpoint = await async_cursor_store.find_latest_stream_checkpoint(
            connector_id,
            dataset_id,
            partition_key=options.partition_key,
        )
        if latest_checkpoint is not None:
            stored_binding = latest_checkpoint.metadata.get("schema_binding")
            if schema_binding is not None and stored_binding is None:
                raise CursorStoreError(
                    "stream schema binding is missing from recovered checkpoint; "
                    "refusing mixed-contract recovery"
                )
            if stored_binding is not None:
                current_binding = (
                    schema_binding.snapshot()
                    if schema_binding is not None
                    else {"status": "not_established"}
                )
                if stored_binding != current_binding:
                    raise CursorStoreError(
                        "stream schema binding changed before resume; "
                        "refusing mixed-contract recovery"
                    )
            frontier_intent = _validated_frontier_intent(latest_checkpoint)
            latest_cursor: CursorState | None = None
            if frontier_intent is not None:
                await _verify_committed_frontier(
                    async_cursor_store=async_cursor_store,
                    checkpoint=latest_checkpoint,
                    intent=frontier_intent,
                )
                latest_cursor = await async_cursor_store.find_latest_cursor(
                    connector_id,
                    dataset_id,
                    partition_key=options.partition_key,
                )
            if frontier_intent is None:
                latest_cursor = await async_cursor_store.find_latest_cursor(
                    connector_id,
                    dataset_id,
                    partition_key=options.partition_key,
                )
            horizon_state = latest_checkpoint.metadata.get("dedupe_horizon")
            if horizon_state is not None:
                dedupe_horizon.restore(horizon_state, _ingestion_utc())
            elif latest_checkpoint.dedupe_keys:
                raise StreamDedupeUnsupported(
                    "legacy dedupe keys have no persisted UTC ingestion time; "
                    "refusing to manufacture a retention horizon"
                )
            operator_state = latest_checkpoint.metadata.get("operator_state")
            if operator_state is None:
                # Checkpoints produced before ING-02 did not carry operator
                # state.  They remain resumable only when the record proves an
                # empty active frontier.  PAUSED/CLOSED lifecycle, a nonzero
                # offset, dedupe keys, observed offset/token, or output counts
                # are evidence that restoring an empty operator would lose
                # state, so recovery fails closed.
                has_frontier_evidence = (
                    latest_checkpoint.offset > 0
                    or bool(latest_checkpoint.dedupe_keys)
                    or latest_checkpoint.lifecycle_state != StreamLifecycleState.ACTIVE
                    or any(
                        latest_checkpoint.metadata.get(name)
                        for name in (
                            "observed_offset",
                            "observed_resume_token",
                            "rows_emitted",
                            "window_count",
                            "cdc_event_count",
                        )
                    )
                )
                if latest_checkpoint.metadata.get("operator_state_required") or (
                    has_frontier_evidence
                ):
                    raise CursorStoreError(
                        "missing stream operator state for a non-empty checkpoint"
                    )
            else:
                _admit_restored_operator_state(
                    operator_state,
                    options=options,
                    contract=processing_contract,
                )
                _restore_stream_operator_state(
                    operator_state,
                    accumulator=accumulator,
                    ordering_state=ordering_state,
                )
            # Admission precedes rewind: a fallback rewind polls the source,
            # and an over-cap predecessor must remain entirely unadvanced.
            await session.rewind(latest_checkpoint)
            committed_checkpoint = latest_checkpoint
            committed_cursor = latest_cursor

        if schema_binding is not None:
            previous_schema = tuple(sorted(schema_binding.schema.field_names()))
        elif latest_checkpoint is not None:
            previous_schema = tuple(
                str(field) for field in latest_checkpoint.metadata.get("schema_fields", ())
            )
        visible_schema = (
            tuple(str(field) for field in latest_checkpoint.metadata.get("visible_fields", ()))
            if latest_checkpoint is not None
            else None
        )

        while True:
            buffered_rows = accumulator.buffered_rows()
            buffered_bytes = accumulator.buffered_bytes()
            _admit_stream_capacity(
                stage="operator",
                rows=buffered_rows,
                bytes_size=buffered_bytes,
                max_rows=processing_contract.backpressure.max_buffered_rows,
                max_bytes=processing_contract.backpressure.max_buffered_bytes,
                strategy=str(processing_contract.backpressure.strategy),
            )
            chunk = await session.poll()
            if chunk is None:
                break
            if buffered_rows >= processing_contract.backpressure.max_buffered_rows or (
                buffered_bytes >= processing_contract.backpressure.max_buffered_bytes
            ):
                result.backpressure_events += 1
                max_backpressure_events = processing_contract.backpressure.max_backpressure_events
                if (
                    max_backpressure_events is not None
                    and result.backpressure_events > max_backpressure_events
                ):
                    raise RuntimeError("stream backpressure event budget exceeded")
                # A full window may release its old rows on this input. Refuse
                # only if the actual post-transition retention exceeds its cap.
                # No strategy authorizes exceeding it or asserts a spill reader.
                if processing_contract.backpressure.strategy in (
                    BackpressureStrategy.PAUSE,
                    BackpressureStrategy.THROTTLE,
                ):
                    await session.pause(
                        reason=(
                            "window buffer at threshold "
                            f"rows={buffered_rows} bytes={buffered_bytes}"
                        )
                    )
                    await asyncio.sleep(processing_contract.backpressure.pause_seconds)
                    await session.resume()

            _admit_stream_input(chunk.data, options)

            result.chunks_processed += 1
            clean_rows: list[dict[str, Any]] = []
            clean_rows_bytes = 0
            chunk_warnings: list[str] = []
            chunk_quarantined = 0
            async for batch in iter_record_batches(
                chunk.data, batch_size=max(1, int(options.batch_size))
            ):
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
                    if processing_contract.idempotency.enabled:
                        dedupe_key = resolve_dedupe_key(
                            row,
                            fields=processing_contract.idempotency.key_fields,
                            missing_key_action="reject",
                        )
                        if not dedupe_horizon.remember(dedupe_key, _ingestion_utc()):
                            result.dedupe_dropped += 1
                            continue
                    row_bytes = _estimate_row_bytes(row)
                    _admit_stream_capacity(
                        stage="input",
                        rows=len(clean_rows) + 1,
                        bytes_size=clean_rows_bytes + row_bytes,
                        max_rows=options.max_input_rows or options.max_buffered_rows,
                        max_bytes=options.max_input_bytes or options.max_buffered_bytes,
                        strategy="bounded_input",
                    )
                    clean_rows_bytes += row_bytes
                    clean_rows.append(row)

            result.warnings.extend(chunk_warnings)
            result.quarantined_rows += chunk_quarantined
            if not clean_rows:
                continue

            (
                clean_rows,
                order_warnings,
                late_dropped,
                late_quarantined,
                out_of_order_rows,
            ) = _apply_out_of_order_policy(
                clean_rows,
                policy=processing_contract.out_of_order,
                state=ordering_state,
            )
            result.warnings.extend(order_warnings)
            result.late_rows_dropped += late_dropped
            result.late_rows_quarantined += late_quarantined
            result.out_of_order_rows += out_of_order_rows
            result.quarantined_rows += late_quarantined
            if not clean_rows:
                continue

            # Run the same window transition against isolated containers before
            # any chunk/CDC publication. Refusal cannot leave a rejected raw
            # chunk in CAS or move the live accumulator beyond its predecessor.
            pending_window_count = accumulator.admit_rows(clean_rows)
            visible_schema = tuple(sorted({str(key) for row in clean_rows for key in row}))
            declared_schema = (
                set(schema_binding.schema.field_names()) if schema_binding is not None else set()
            )
            # The declared schema is the stable CDC baseline, while observed
            # extras remain visible and can still produce an explicit additive
            # diagnostic.  Optional absence therefore cannot look like removal,
            # but unknown fields are not silently hidden from CDC.
            current_schema = tuple(sorted(declared_schema | set(visible_schema)))
            _admit_output_ref(
                result,
                options,
                additional_count=1
                + pending_window_count
                + int(previous_schema is not None and current_schema != previous_schema),
            )
            if previous_schema is not None and current_schema != previous_schema:
                compatibility = classify_cdc_schema_change(
                    previous_schema,
                    current_schema,
                )
                handling_action = _cdc_handling_action(
                    compatibility,
                    processing_contract,
                )
                _admit_output_ref(result, options)
                cdc_ref = await _persist_cdc_schema_change_event_async(
                    store=async_store,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    partition_key=options.partition_key,
                    previous_fields=previous_schema,
                    current_fields=current_schema,
                    compatibility=compatibility,
                    handling_action=handling_action,
                    observed_at=datetime.now(UTC),
                    processing_contract=processing_contract,
                    schema_binding=schema_binding,
                    visible_fields=visible_schema,
                )
                result.cdc_event_refs.append(cdc_ref)
                result.warnings.append(
                    f"CDC schema change detected for {connector_id}:{dataset_id}: "
                    f"{sorted(set(current_schema) - set(previous_schema)) or ['no added fields']}"
                )

                if _should_fail_closed_cdc_schema_change(
                    compatibility,
                    handling_action,
                ):
                    raise RuntimeError(
                        "CDC schema change failed closed for "
                        f"{connector_id}:{dataset_id}: {compatibility.value}"
                    )
                if _should_quarantine_cdc_schema_change(
                    compatibility,
                    handling_action,
                ):
                    result.quarantined_rows += len(clean_rows)
                    result.warnings.append("CDC incompatible breaking change quarantined")
                    persist_quarantine_record(
                        sync_store,
                        record=QuarantineRecord.new(
                            reason="cdc_schema_change_incompatible_breaking",
                            severity="P1",
                            source=f"stream:{connector_id}:{dataset_id}",
                            schema_version="fabric.CDCSchemaChange:1.0",
                            downstream_impacts=(
                                "connector_cache",
                                "evidence_bundle",
                                "data_snapshot",
                                "world.materialize",
                            ),
                            context={
                                "partition_key": options.partition_key,
                                "previous_fields": list(previous_schema),
                                "current_fields": list(current_schema),
                                "compatibility": compatibility.value,
                                "handling_action": handling_action,
                                "cdc_event_ref": str(cdc_ref.artifact_id),
                            },
                        ),
                        raw_payload=clean_rows,
                        input_artifact_ids=(str(cdc_ref.artifact_id),),
                    )
                    continue
            previous_schema = current_schema

            _admit_output_ref(result, options)
            chunk_ref = await _persist_stream_chunk_async(
                store=async_store,
                connector_id=connector_id,
                dataset_id=dataset_id,
                partition_key=options.partition_key,
                chunk=chunk,
                rows=clean_rows,
                dedupe_dropped=result.dedupe_dropped,
                processing_contract=processing_contract,
                schema_binding=schema_binding,
                visible_fields=visible_schema,
            )
            result.chunk_refs.append(chunk_ref)
            result.rows_emitted += len(clean_rows)

            for emission in accumulator.iter_rows_with_refs(
                clean_rows,
                (str(chunk_ref.artifact_id),),
            ):
                _admit_output_ref(result, options)
                result.window_refs.append(
                    await _persist_stream_window_async(
                        store=async_store,
                        connector_id=connector_id,
                        dataset_id=dataset_id,
                        partition_key=options.partition_key,
                        assignment=emission.assignment,
                        input_refs=emission.contributor_refs,
                        processing_contract=processing_contract,
                        window_policy=options.window_policy,
                    )
                )

            if result.chunks_processed % max(1, int(options.checkpoint_every_chunks)) == 0:
                _assert_stream_schema_binding_current(
                    registry,
                    schema_binding,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                )
                checkpoint = session.checkpoint(
                    chunk=chunk,
                    dedupe_keys=tuple(dedupe_horizon.entries),
                    schema_fingerprint=_stream_schema_fingerprint(
                        schema_binding,
                        previous_schema,
                    ),
                )
                checkpoint = checkpoint.model_copy(
                    update={
                        "metadata": {
                            **checkpoint.metadata,
                            **_stream_checkpoint_metadata(
                                accumulator=accumulator,
                                ordering_state=ordering_state,
                                previous_schema=previous_schema,
                                visible_schema=visible_schema,
                                schema_binding=schema_binding,
                                result=result,
                                processing_contract=processing_contract,
                                dedupe_horizon=dedupe_horizon,
                            ),
                        },
                        "committed_at": datetime.now(UTC),
                    }
                )
                cursor = _stream_cursor_for_checkpoint(
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    partition_key=options.partition_key,
                    checkpoint=checkpoint,
                    result=result,
                    processing_contract=processing_contract,
                    window_policy=options.window_policy,
                )
                prepared_checkpoint, intent = await _prepare_stream_frontier(
                    async_cursor_store=async_cursor_store,
                    checkpoint=checkpoint,
                    cursor=cursor,
                    previous_checkpoint=committed_checkpoint,
                    previous_cursor=committed_cursor,
                )
                pending_frontier = prepared_checkpoint
                _, _, committed_checkpoint = await _commit_stream_frontier(
                    session=session,
                    async_cursor_store=async_cursor_store,
                    cursor=cursor,
                    checkpoint=checkpoint,
                    prepared_checkpoint=prepared_checkpoint,
                    intent=intent,
                    previous_checkpoint=committed_checkpoint,
                    previous_cursor=committed_cursor,
                    empty_frontier=empty_frontier,
                )
                pending_frontier = None
                committed_cursor = cursor
                result.final_checkpoint = committed_checkpoint

        for emission in accumulator.flush_with_refs():
            _admit_output_ref(result, options)
            result.window_refs.append(
                await _persist_stream_window_async(
                    store=async_store,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    partition_key=options.partition_key,
                    assignment=emission.assignment,
                    input_refs=emission.contributor_refs,
                    processing_contract=processing_contract,
                    window_policy=options.window_policy,
                )
            )

        _assert_stream_schema_binding_current(
            registry,
            schema_binding,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        if session.last_chunk is None and committed_checkpoint is not None:
            final_checkpoint = committed_checkpoint.model_copy(
                update={"lifecycle_state": StreamLifecycleState.CLOSED}
            )
        else:
            final_checkpoint = session.checkpoint(
                dedupe_keys=tuple(dedupe_horizon.entries),
                schema_fingerprint=_stream_schema_fingerprint(
                    schema_binding,
                    previous_schema,
                ),
                lifecycle_state=StreamLifecycleState.CLOSED,
            )
        final_checkpoint = final_checkpoint.model_copy(
            update={
                "metadata": {
                    **final_checkpoint.metadata,
                    **_stream_checkpoint_metadata(
                        accumulator=accumulator,
                        ordering_state=ordering_state,
                        previous_schema=previous_schema,
                        visible_schema=visible_schema,
                        schema_binding=schema_binding,
                        result=result,
                        processing_contract=processing_contract,
                        dedupe_horizon=dedupe_horizon,
                    ),
                },
                "committed_at": datetime.now(UTC),
            }
        )
        final_cursor = _stream_cursor_for_checkpoint(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key=options.partition_key,
            checkpoint=final_checkpoint,
            result=result,
            processing_contract=processing_contract,
            window_policy=options.window_policy,
        )
        prepared_checkpoint, intent = await _prepare_stream_frontier(
            async_cursor_store=async_cursor_store,
            checkpoint=final_checkpoint,
            cursor=final_cursor,
            previous_checkpoint=committed_checkpoint,
            previous_cursor=committed_cursor,
        )
        pending_frontier = prepared_checkpoint
        cursor_ref, checkpoint_ref, committed_checkpoint = await _commit_stream_frontier(
            session=session,
            async_cursor_store=async_cursor_store,
            cursor=final_cursor,
            checkpoint=final_checkpoint,
            prepared_checkpoint=prepared_checkpoint,
            intent=intent,
            previous_checkpoint=committed_checkpoint,
            previous_cursor=committed_cursor,
            empty_frontier=empty_frontier,
        )
        pending_frontier = None
        result.final_checkpoint = committed_checkpoint
        result.final_cursor = final_cursor
        result.final_cursor_ref = str(cursor_ref.artifact_id)
        result.final_checkpoint_ref = (
            str(checkpoint_ref.artifact_id) if checkpoint_ref is not None else None
        )
        return result
    except Exception as exc:
        if isinstance(exc, StreamCapacityError | StreamDedupeUnsupported):
            # Capacity refusal is not a new frontier. Preserve the exact
            # predecessor rather than publishing a diagnostic over it.
            raise
        if pending_frontier is not None:
            raise
        if session.last_chunk is not None:
            if committed_checkpoint is not None:
                checkpoint = committed_checkpoint.model_copy(
                    update={
                        "lifecycle_state": StreamLifecycleState.PAUSED,
                        "created_at": datetime.now(UTC),
                        "committed_at": None,
                    }
                )
                frontier_metadata = dict(committed_checkpoint.metadata)
                frontier_metadata.pop("frontier_intent", None)
            else:
                checkpoint = session.checkpoint(
                    chunk=None,
                    use_observed_chunk=False,
                    dedupe_keys=(),
                    schema_fingerprint="",
                    lifecycle_state=StreamLifecycleState.PAUSED,
                )
                frontier_metadata = {}

            if "operator_state" not in frontier_metadata:
                frontier_metadata["operator_state_required"] = True
                frontier_metadata["operator_state"] = _empty_stream_operator_state(
                    options.window_policy
                )
            frontier_metadata.setdefault("frontier_committed", committed_checkpoint is not None)
            frontier_metadata.setdefault(
                "schema_binding",
                (
                    schema_binding.snapshot()
                    if schema_binding is not None
                    else {"status": "not_established"}
                ),
            )
            frontier_schema = tuple(
                str(field) for field in frontier_metadata.get("schema_fields", ())
            )
            frontier_rows = int(frontier_metadata.get("rows_emitted", 0) or 0)
            checkpoint = checkpoint.model_copy(
                update={
                    "metadata": {
                        **checkpoint.metadata,
                        **frontier_metadata,
                        "schema_fields": list(frontier_schema),
                        "error": str(exc),
                        "observed_offset": int(session.last_chunk.chunk_index),
                        "observed_resume_token": session.last_chunk.resume_token,
                        "rows_emitted": frontier_rows,
                        "processing": processing_contract_snapshot(processing_contract),
                    },
                }
            )
            checkpoint_ref = await async_cursor_store.save_stream_checkpoint(checkpoint)
            result.final_checkpoint = checkpoint
            result.final_checkpoint_ref = str(checkpoint_ref.artifact_id)
        raise
    finally:
        primary_exc = sys.exc_info()[1]
        try:
            await session.close()
        except BaseException as cleanup_exc:
            if primary_exc is None:
                raise
            primary_exc.add_note(f"stream session final cleanup failed: {cleanup_exc!r}")


async def _persist_stream_chunk_async(
    *,
    store: AsyncArtifactStore,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    chunk: DataChunk[Any],
    rows: list[dict[str, Any]],
    dedupe_dropped: int,
    processing_contract: ProcessingGuaranteeContract,
    schema_binding: StreamSchemaBinding | None = None,
    visible_fields: tuple[str, ...] | None = None,
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
        "schema_binding": (
            schema_binding.snapshot()
            if schema_binding is not None
            else {"status": "not_established"}
        ),
        "visible_fields": list(visible_fields or ()),
        "processing": processing_contract_snapshot(processing_contract),
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
    processing_contract: ProcessingGuaranteeContract,
    window_policy: WindowPolicy,
    input_ref: ArtifactRef | None = None,
    input_refs: tuple[ArtifactRef | str, ...] | None = None,
) -> ArtifactRef:
    if input_ref is not None and input_refs is not None:
        raise ValueError("provide input_ref or input_refs, not both")
    resolved_refs: tuple[ArtifactRef | str, ...] = input_refs or (
        (input_ref,) if input_ref is not None else ()
    )
    inputs = [
        InputRef(
            artifact_id=(ref.artifact_id if isinstance(ref, ArtifactRef) else ref),
            role="stream_chunk",
        )
        for ref in dict.fromkeys(
            str(ref.artifact_id) if isinstance(ref, ArtifactRef) else str(ref)
            for ref in resolved_refs
        )
    ] or None
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
        "window_policy": _window_policy_snapshot(
            window_policy,
            fallback_strategy=assignment.strategy,
        ),
        "processing": processing_contract_snapshot(processing_contract),
        "lineage": {
            "contributor_chunk_refs": [
                str(ref.artifact_id) if isinstance(ref, ArtifactRef) else str(ref)
                for ref in resolved_refs
            ]
        },
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


def resolve_dedupe_key(
    row: dict[str, Any],
    *,
    fields: tuple[str, ...],
    missing_key_action: str = "reject",
) -> str:
    """Encode exact configured event/version components without a payload fallback.

    The source owner must establish their meaning; names alone do not prove
    source ownership. Every configured component and its primitive type matter.
    """
    del missing_key_action
    if not fields or any(
        field_name not in row or type(row[field_name]) not in (str, int) or row[field_name] == ""
        for field_name in fields
    ):
        raise StreamDedupeUnsupported("source event/version key is missing or unsupported")
    return json.dumps(
        [(field_name, row[field_name]) for field_name in fields],
        ensure_ascii=False,
        separators=(",", ":"),
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
    processing_contract: ProcessingGuaranteeContract | None = None,
    schema_binding: StreamSchemaBinding | None = None,
    visible_fields: tuple[str, ...] | None = None,
) -> ArtifactRef:
    """Persist one cleaned stream chunk as a deterministic CAS artifact."""
    contract = processing_contract or stream_processing_contract()
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
        "schema_binding": (
            schema_binding.snapshot()
            if schema_binding is not None
            else {"status": "not_established"}
        ),
        "visible_fields": list(visible_fields or ()),
        "processing": processing_contract_snapshot(contract),
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
    processing_contract: ProcessingGuaranteeContract | None = None,
    window_policy: WindowPolicy | None = None,
    input_ref: ArtifactRef | None = None,
    input_refs: tuple[ArtifactRef | str, ...] | None = None,
) -> ArtifactRef:
    """Persist one logical stream window."""
    contract = processing_contract or stream_processing_contract()
    if input_ref is not None and input_refs is not None:
        raise ValueError("provide input_ref or input_refs, not both")
    resolved_refs: tuple[ArtifactRef | str, ...] = input_refs or (
        (input_ref,) if input_ref is not None else ()
    )
    unique_refs = tuple(
        dict.fromkeys(
            str(ref.artifact_id) if isinstance(ref, ArtifactRef) else str(ref)
            for ref in resolved_refs
        )
    )
    inputs = [InputRef(artifact_id=ref, role="stream_chunk") for ref in unique_refs] or None
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
        "window_policy": _window_policy_snapshot(
            window_policy,
            fallback_strategy=assignment.strategy,
        ),
        "processing": processing_contract_snapshot(contract),
        "lineage": {"contributor_chunk_refs": list(unique_refs)},
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
    compatibility: CDCSchemaCompatibility,
    handling_action: str,
    observed_at: datetime,
    processing_contract: ProcessingGuaranteeContract,
    schema_binding: StreamSchemaBinding | None = None,
    visible_fields: tuple[str, ...] | None = None,
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
        "visible_fields": list(visible_fields or current_fields),
        "added_fields": sorted(current - previous),
        "removed_fields": sorted(previous - current),
        "schema_binding": (
            schema_binding.snapshot()
            if schema_binding is not None
            else {"status": "not_established"}
        ),
        "compatibility": compatibility.value,
        "handling_action": handling_action,
        "processing": processing_contract_snapshot(processing_contract),
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
    compatibility: CDCSchemaCompatibility | None = None,
    handling_action: str | None = None,
    processing_contract: ProcessingGuaranteeContract | None = None,
    schema_binding: StreamSchemaBinding | None = None,
    visible_fields: tuple[str, ...] | None = None,
) -> ArtifactRef:
    """Persist one schema-change event with lineage/impact payloads."""
    previous = set(previous_fields)
    current = set(current_fields)
    resolved_compatibility = compatibility or classify_cdc_schema_change(
        previous_fields,
        current_fields,
    )
    contract = processing_contract or stream_processing_contract()
    payload = {
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "partition_key": partition_key,
        "observed_at": observed_at.isoformat(),
        "previous_fields": list(previous_fields),
        "current_fields": list(current_fields),
        "visible_fields": list(visible_fields or current_fields),
        "added_fields": sorted(current - previous),
        "removed_fields": sorted(previous - current),
        "schema_binding": (
            schema_binding.snapshot()
            if schema_binding is not None
            else {"status": "not_established"}
        ),
        "compatibility": resolved_compatibility.value,
        "handling_action": handling_action or "review",
        "processing": processing_contract_snapshot(contract),
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
    "StreamCapacityError",
    "StreamDatasetRunResult",
    "StreamDedupeUnsupported",
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
