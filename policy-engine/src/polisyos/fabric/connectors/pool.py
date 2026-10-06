"""Connection Pool for Data Source Connectors.

Manages ConnectionHandle objects with lifecycle management, health checks, and
configurable pool sizing. Integrates with OpenTelemetry for observability.

Design Principles:
- Thread-safe for concurrent access from async contexts
- Health check integration with automatic stale connection eviction
- Configurable pool sizes with backpressure (semaphore-based)
- Connection reuse to minimize latency and resource usage
"""

from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import uuid4

from polisyos.common.logger import get_logger

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        HealthStatus,
        SourceConnector,
    )
    from polisyos.fabric.connectors.resilience import CircuitBreaker

logger = get_logger(__name__)

ConnectorT = TypeVar("ConnectorT", bound="SourceConnector")
SettlementT = TypeVar("SettlementT")


class PoolExhaustedError(Exception):
    """Raised when pool cannot provide a connection within timeout."""

    def __init__(self, pool_id: str, timeout_seconds: float) -> None:
        self.pool_id = pool_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Connection pool '{pool_id}' exhausted. "
            f"Could not acquire connection within {timeout_seconds}s"
        )


class PoolClosedError(Exception):
    """Raised when attempting to use a closed pool."""

    def __init__(self, pool_id: str) -> None:
        self.pool_id = pool_id
        super().__init__(f"Connection pool '{pool_id}' is closed")


@dataclass
class PooledConnection:
    """
    Wrapper around ConnectionHandle with pool metadata.

    Tracks creation time, last use, and health check results
    for intelligent connection reuse decisions.
    """

    connector: SourceConnector
    handle: ConnectionHandle
    pool_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_health_check: datetime | None = None
    consecutive_failures: int = 0
    use_count: int = 0
    closed: bool = False
    closing: bool = False
    cleanup_task: asyncio.Task[bool] | None = field(default=None, repr=False, compare=False)
    pending_permit: bool = False
    release_in_progress: bool = field(default=False, repr=False, compare=False)

    @property
    def age_seconds(self) -> float:
        """Time since connection was created."""
        now = datetime.now(UTC)
        return (now - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Time since connection was last used."""
        now = datetime.now(UTC)
        return (now - self.last_used_at).total_seconds()

    def mark_used(self) -> None:
        """Update last_used_at and increment use count."""
        self.last_used_at = datetime.now(UTC)
        self.use_count += 1

    def mark_healthy(self) -> None:
        """Record successful health check."""
        self.last_health_check = datetime.now(UTC)
        self.consecutive_failures = 0

    def mark_unhealthy(self) -> None:
        """Record failed health check."""
        self.last_health_check = datetime.now(UTC)
        self.consecutive_failures += 1


@dataclass
class PoolConfig:
    """Configuration for connection pool behavior."""

    # Pool sizing
    max_size: int = 10
    min_idle: int = 1

    # Timeouts
    acquire_timeout_seconds: float = 30.0
    connection_timeout_seconds: float = 30.0

    # Connection lifecycle
    max_connection_age_seconds: float = 3600.0  # 1 hour
    max_idle_seconds: float = 300.0  # 5 minutes
    max_connection_uses: int = 1000
    max_lifecycle_session_ids: int = 4096
    max_backpressure_signals: int = 128

    # Health checks
    health_check_interval_seconds: float = 60.0
    max_consecutive_failures: int = 3

    # Validation
    validate_on_acquire: bool = True
    validate_on_release: bool = False


@dataclass
class PoolStats:
    """Runtime statistics snapshot for observability."""

    pool_id: str
    max_size: int
    total_connections: int
    idle_connections: int
    in_use_connections: int
    total_acquires: int
    total_releases: int
    total_creates: int
    total_closes: int
    total_health_checks: int
    failed_health_checks: int
    acquire_wait_time_total_ms: float
    created_at: datetime


class BackpressureLevel(str, Enum):
    """Severity level for downstream backpressure signals."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    PAUSED = "paused"


@dataclass(frozen=True)
class BackpressureSignal:
    """One downstream pressure signal registered against the pool."""

    source: str
    level: BackpressureLevel
    reason: str
    pause_seconds: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PoolBackpressureSnapshot:
    """Current pool pressure view exposed to upstream pollers."""

    pool_id: str
    level: BackpressureLevel
    utilization: float
    available_slots: int
    suggested_poll_delay_seconds: float
    active_signals: tuple[BackpressureSignal, ...] = ()


class ConnectionPool(Generic[ConnectorT]):
    """
    Thread-safe connection pool for SourceConnector instances.

    Manages a pool of ConnectionHandle objects with:
    - Semaphore-based concurrency control
    - Health check integration
    - Automatic stale connection eviction
    - Comprehensive observability metrics

    Usage:
        pool = ConnectionPool(
            connector_factory=lambda: MyConnector(),
            config=connection_config,
            pool_config=PoolConfig(max_size=5),
        )

        handle = await pool.acquire()
        try:
            # Use handle...
        finally:
            await pool.release(handle)

        # Or use context manager:
        async with await pool.connection() as handle:
            # Use handle...
    """

    def __init__(
        self,
        connector_factory: Callable[[], ConnectorT],
        config: ConnectionConfig,
        pool_config: PoolConfig | None = None,
        pool_id: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """
        Initialize connection pool.

        Args:
            connector_factory: Callable that returns new connector instance
            config: Connection configuration for all connections
            pool_config: Pool behavior configuration
            pool_id: Optional identifier for logging/metrics
        """
        self._connector_factory = connector_factory
        self._connection_config = config
        self._config = pool_config or PoolConfig()
        if self._config.max_size < 1:
            raise ValueError("max_size must be >= 1")
        if self._config.max_lifecycle_session_ids < 1:
            raise ValueError("max_lifecycle_session_ids must be >= 1")
        if self._config.max_backpressure_signals < 1:
            raise ValueError("max_backpressure_signals must be >= 1")
        self._pool_id = pool_id or f"pool-{uuid4().hex[:8]}"
        self._circuit_breaker = circuit_breaker

        # Connection storage
        self._idle: deque[PooledConnection] = deque()
        self._in_use: dict[str, PooledConnection] = {}
        self._pending_cleanup: dict[str, PooledConnection] = {}
        self._released_session_ids: OrderedDict[str, None] = OrderedDict()
        self._closed_session_ids: OrderedDict[str, None] = OrderedDict()

        # Synchronization primitives
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self._config.max_size)
        self._closed = False
        self._generation = 0
        self._active_acquires = 0
        self._active_acquires_done = asyncio.Event()
        self._active_acquires_done.set()
        self._backpressure_lock = threading.Lock()
        self._backpressure_signals: OrderedDict[str, BackpressureSignal] = OrderedDict()

        # Statistics
        self._stats_lock = threading.Lock()
        self._total_acquires = 0
        self._total_releases = 0
        self._total_creates = 0
        self._total_closes = 0
        self._total_health_checks = 0
        self._failed_health_checks = 0
        self._acquire_wait_time_total_ms = 0.0
        self._created_at = datetime.now(UTC)

        logger.info(
            "Connection pool initialized",
            pool_id=self._pool_id,
            max_size=self._config.max_size,
            acquire_timeout=self._config.acquire_timeout_seconds,
        )

    @property
    def pool_id(self) -> str:
        """Unique identifier for this pool."""
        return self._pool_id

    @property
    def is_closed(self) -> bool:
        """Whether the pool has been closed."""
        return self._closed

    async def acquire(self) -> ConnectionHandle:
        """
        Acquire a connection from the pool.

        Returns an existing idle connection if available,
        otherwise creates a new one (within pool limits).

        Returns:
            ConnectionHandle ready for use

        Raises:
            PoolExhaustedError: If no connection available within timeout
            PoolClosedError: If pool has been closed
        """
        self._raise_if_circuit_open()
        _connector, handle = await self._acquire_owned()
        return handle

    async def acquire_with_connector(self) -> tuple[SourceConnector, ConnectionHandle]:
        """Acquire a connection and return both connector instance and handle."""
        self._raise_if_circuit_open()
        return await self._acquire_owned()

    async def _acquire_with_live_permit(
        self,
        permit: object,
        *,
        connector_id: str,
        dataset_id: str,
    ) -> tuple[SourceConnector, ConnectionHandle]:
        """Acquire one governed live handle after consuming its journal permit."""

        return await self._acquire_owned(
            live_acquire_permit=permit,
            live_connector_id=connector_id,
            live_dataset_id=dataset_id,
        )

    def _raise_if_circuit_open(self) -> None:
        """Raise before reserving a pool permit when the circuit is open."""
        if self._circuit_breaker is None or not self._circuit_breaker.is_open():
            return

        from polisyos.fabric.connectors.resilience import CircuitOpenError

        opened_at = self._circuit_breaker.opened_at or datetime.now(UTC)
        raise CircuitOpenError(
            self._circuit_breaker.circuit_id,
            opened_at,
            self._circuit_breaker.config.timeout_seconds,
        )

    def _require_acquire_budget(self, deadline: float) -> None:
        if asyncio.get_running_loop().time() >= deadline:
            raise PoolExhaustedError(self._pool_id, self._config.acquire_timeout_seconds)

    async def _acquire_owned(
        self,
        *,
        live_acquire_permit: object | None = None,
        live_connector_id: str | None = None,
        live_dataset_id: str | None = None,
    ) -> tuple[SourceConnector, ConnectionHandle]:
        """Use one monotonic budget through final handle publication."""
        deadline = asyncio.get_running_loop().time() + self._config.acquire_timeout_seconds
        async with asyncio.timeout_at(deadline) as acquisition_timer:
            try:
                return await self._acquire_owned_before_deadline(
                    deadline=deadline,
                    live_acquire_permit=live_acquire_permit,
                    live_connector_id=live_connector_id,
                    live_dataset_id=live_dataset_id,
                )
            except asyncio.CancelledError as exc:
                if acquisition_timer.expired():
                    raise PoolExhaustedError(
                        self._pool_id, self._config.acquire_timeout_seconds
                    ) from exc
                raise

    async def _acquire_owned_before_deadline(
        self,
        *,
        deadline: float,
        live_acquire_permit: object | None = None,
        live_connector_id: str | None = None,
        live_dataset_id: str | None = None,
    ) -> tuple[SourceConnector, ConnectionHandle]:
        """Acquire and publish one handle while retaining ownership through failures."""
        if live_acquire_permit is not None:
            if live_connector_id is None or live_dataset_id is None:
                raise ValueError("a live acquire permit requires connector and dataset identity")
            from polisyos.fabric.data_plane.evidence_journal import (
                _consume_live_acquire_permit,
            )

            _consume_live_acquire_permit(
                live_acquire_permit,
                connector_id=live_connector_id,
                dataset_id=live_dataset_id,
            )
            self._raise_if_circuit_open()
        elif live_connector_id is not None or live_dataset_id is not None:
            raise ValueError("live connector and dataset identity require a journal permit")
        start_time = datetime.now(UTC)
        permit_acquired = False
        registered = False
        permit_release = False
        published = False
        cleanup_attempted = False
        pooled: PooledConnection | None = None

        try:
            async with self._lock:
                if self._closed:
                    raise PoolClosedError(self._pool_id)
            try:
                self._require_acquire_budget(deadline)
                acquired = await self._semaphore.acquire()
            except TimeoutError as exc:
                raise PoolExhaustedError(
                    self._pool_id,
                    self._config.acquire_timeout_seconds,
                ) from exc
            if not acquired:
                raise PoolExhaustedError(self._pool_id, self._config.acquire_timeout_seconds)
            permit_acquired = True

            async with self._lock:
                if self._closed:
                    permit_release = True
                    raise PoolClosedError(self._pool_id)
                self._require_acquire_budget(deadline)
                self._active_acquires += 1
                registered = True
                self._active_acquires_done.clear()

            while True:
                async with self._lock:
                    self._require_acquire_budget(deadline)
                    if self._closed:
                        permit_release = True
                        raise PoolClosedError(self._pool_id)
                    generation = self._generation
                    pooled = self._idle.popleft() if self._idle else None
                    if pooled is not None:
                        self._register_pending_cleanup(pooled, pending_permit=True)

                if pooled is None:
                    # Connector I/O happens outside the metadata lock. The semaphore remains
                    # the physical-capacity reservation while this connection is being made.
                    connection_deadline = min(
                        deadline,
                        asyncio.get_running_loop().time() + self._config.connection_timeout_seconds,
                    )
                    async with asyncio.timeout_at(connection_deadline) as connection_timer:
                        pooled = await self._create_connection()
                    async with self._lock:
                        self._register_pending_cleanup(pooled, pending_permit=True)
                        self._require_acquire_budget(deadline)
                        if connection_timer.expired():
                            raise TimeoutError(
                                "Connection creation exceeded its configured deadline"
                            )

                if self._should_retire(pooled):
                    cleanup_attempted = True
                    if not await self._cleanup_pooled(pooled):
                        raise RuntimeError(
                            "Connection cleanup is pending before a replacement can be acquired"
                        )
                    pooled = None
                    cleanup_attempted = False
                    continue

                if self._config.validate_on_acquire and live_acquire_permit is None:
                    healthy = await self._validate_connection(pooled)
                    if not healthy:
                        cleanup_attempted = True
                        if not await self._cleanup_pooled(pooled):
                            raise RuntimeError(
                                "Connection cleanup is pending before a replacement can be acquired"
                            )
                        pooled = None
                        cleanup_attempted = False
                        continue

                async with self._lock:
                    self._require_acquire_budget(deadline)
                    if not self._closed and generation == self._generation:
                        pooled.mark_used()
                        self._in_use[pooled.handle.session_id] = pooled
                        self._pending_cleanup.pop(pooled.handle.session_id, None)
                        pooled.pending_permit = False
                        self._released_session_ids.pop(pooled.handle.session_id, None)

                        with self._stats_lock:
                            self._total_acquires += 1
                            elapsed = datetime.now(UTC) - start_time
                            self._acquire_wait_time_total_ms += elapsed.total_seconds() * 1000

                        logger.debug(
                            "Connection acquired",
                            pool_id=self._pool_id,
                            session_id=pooled.handle.session_id,
                            idle_count=len(self._idle),
                            in_use_count=len(self._in_use),
                        )
                        # Publication and registration retirement are one commit.
                        # There is no suspension point after a successful commit.
                        self._active_acquires -= 1
                        registered = False
                        if self._active_acquires == 0:
                            self._active_acquires_done.set()
                        published = True
                        return pooled.connector, pooled.handle

                # close_all won the generation race. The handle remains owned by this
                # transition until its physical disconnect succeeds.
                cleanup_attempted = True
                if not await self._cleanup_pooled(pooled):
                    raise RuntimeError("Connection cleanup is pending for the closed pool")
                pooled = None
                permit_release = True
                raise PoolClosedError(self._pool_id)
        except BaseException as exc:
            if pooled is not None and not published:
                cleanup = asyncio.create_task(
                    self._settle_failed_acquire(pooled, cleanup_attempted, exc)
                )
                permit_release = await self._wait_owned_settlement(cleanup)
            elif not published:
                permit_release = True
            raise
        finally:
            if registered or (permit_acquired and not published and permit_release):
                retirement = asyncio.create_task(
                    self._retire_failed_acquire(
                        registered=registered,
                        release_permit=permit_acquired and not published and permit_release,
                    )
                )
                await self._wait_owned_settlement(retirement)

    async def _settle_failed_acquire(
        self, pooled: PooledConnection, cleanup_attempted: bool, primary: BaseException
    ) -> bool:
        async with self._lock:
            self._register_pending_cleanup(pooled, pending_permit=True)
        if pooled.closed:
            return await self._claim_permit(pooled, True)
        if cleanup_attempted:
            return False
        try:
            cleaned = await self._cleanup_pooled(pooled)
        except BaseException as cleanup_error:
            primary.add_note(f"cleanup during acquire failed: {cleanup_error!r}")
            cleaned = pooled.closed
        return await self._claim_permit(pooled, True) if cleaned else False

    async def _retire_failed_acquire(self, *, registered: bool, release_permit: bool) -> None:
        async with self._lock:
            if registered:
                self._active_acquires -= 1
                if self._active_acquires == 0:
                    self._active_acquires_done.set()
            if release_permit:
                self._semaphore.release()

    @staticmethod
    async def _wait_owned_settlement(task: asyncio.Task[SettlementT]) -> SettlementT:
        # The primary exception remains owned by the caller. Repeated cancellation
        # cannot abandon cleanup or free a physical permit before it settles.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        return task.result()

    async def release(self, handle: ConnectionHandle) -> None:
        """
        Release a connection back to the pool.

        The connection may be returned to the idle pool for reuse,
        or closed if it has exceeded lifecycle limits.

        Args:
            handle: ConnectionHandle to release
        """
        pooled: PooledConnection | None = None
        release_owner: PooledConnection | None = None
        permit_owned = False
        permit_release = False
        cleanup_attempted = False

        try:
            async with self._lock:
                pooled = self._in_use.pop(handle.session_id, None)
                if pooled is None:
                    pooled = self._pending_cleanup.get(handle.session_id)
                    if pooled is None:
                        if handle.session_id not in self._released_session_ids:
                            logger.warning(
                                "Released unknown connection",
                                pool_id=self._pool_id,
                                session_id=handle.session_id,
                            )
                        return
                    if pooled.release_in_progress:
                        # Another release caller owns the transition (including
                        # release-time validation).  Returning here keeps one
                        # physical owner, idle entry, and semaphore permit.
                        return
                    permit_owned = pooled.pending_permit
                else:
                    permit_owned = True
                    pooled.pending_permit = True
                    self._pending_cleanup[handle.session_id] = pooled
                    self._remember_session_id(self._released_session_ids, handle.session_id)
                    with self._stats_lock:
                        self._total_releases += 1

                pooled.release_in_progress = True
                release_owner = pooled
                should_close = self._closed or self._should_retire(pooled)

            if should_close:
                cleanup_attempted = True
                if not await self._cleanup_pooled(pooled):
                    raise RuntimeError("Connection cleanup is pending for the released owner")
                permit_release = await self._claim_permit(pooled, permit_owned)
                pooled = None
                return

            if self._config.validate_on_release:
                healthy = await self._validate_connection(pooled)
                if not healthy:
                    cleanup_attempted = True
                    if not await self._cleanup_pooled(pooled):
                        raise RuntimeError(
                            "Connection cleanup is pending after release validation failed"
                        )
                    permit_release = await self._claim_permit(pooled, permit_owned)
                    pooled = None
                    return

            async with self._lock:
                if self._closed:
                    publish_idle = False
                else:
                    self._idle.append(pooled)
                    self._pending_cleanup.pop(handle.session_id, None)
                    pooled.pending_permit = False
                    publish_idle = True
                    logger.debug(
                        "Connection released to pool",
                        pool_id=self._pool_id,
                        session_id=handle.session_id,
                        idle_count=len(self._idle),
                    )

            if publish_idle:
                permit_release = permit_owned
                pooled = None
            else:
                cleanup_attempted = True
                if not await self._cleanup_pooled(pooled):
                    raise RuntimeError("Connection cleanup is pending after pool closure")
                permit_release = await self._claim_permit(pooled, permit_owned)
                pooled = None
        except BaseException as exc:
            if pooled is not None and permit_owned:
                async with self._lock:
                    self._register_pending_cleanup(pooled, pending_permit=True)
                if pooled.closed:
                    permit_release = await self._claim_permit(pooled, True)
                elif not cleanup_attempted:
                    try:
                        cleaned = await self._cleanup_pooled(pooled)
                    except BaseException as cleanup_exc:
                        if pooled.closed:
                            permit_release = await self._claim_permit(pooled, True)
                        else:
                            exc.add_note(f"cleanup during release failed: {cleanup_exc!r}")
                    else:
                        if cleaned:
                            permit_release = await self._claim_permit(pooled, True)
            raise
        finally:
            if release_owner is not None:
                async with self._lock:
                    release_owner.release_in_progress = False
            if permit_release:
                self._semaphore.release()

    async def _claim_permit(self, pooled: PooledConnection, owned: bool) -> bool:
        """Return a semaphore permit exactly once for one physical owner."""
        if not owned:
            return False
        async with self._lock:
            if not pooled.pending_permit:
                return False
            pooled.pending_permit = False
            return True

    def _register_pending_cleanup(self, pooled: PooledConnection, *, pending_permit: bool) -> None:
        """Publish a physical owner before connector cleanup or close can await."""
        session_id = pooled.handle.session_id
        existing = self._pending_cleanup.get(session_id)
        if existing is None:
            self._pending_cleanup[session_id] = pooled
        pooled.pending_permit = pooled.pending_permit or pending_permit

    def _clear_pending_cleanup(self, pooled: PooledConnection) -> None:
        """Forget an owner only after its physical disconnect succeeds."""
        self._pending_cleanup.pop(pooled.handle.session_id, None)

    async def _cleanup_pooled(self, pooled: PooledConnection) -> bool:
        """Run one shared cleanup task and retain the owner when it remains unresolved."""
        async with self._lock:
            self._register_pending_cleanup(pooled, pending_permit=pooled.pending_permit)
            if pooled.closed:
                self._clear_pending_cleanup(pooled)
                return True
            cleanup_task = pooled.cleanup_task
            if cleanup_task is None or cleanup_task.done():
                cleanup_task = asyncio.create_task(self._close_connection(pooled))
                pooled.cleanup_task = cleanup_task

        cancelled = False
        while True:
            try:
                await asyncio.shield(cleanup_task)
                break
            except asyncio.CancelledError:
                cancelled = True

        try:
            cleaned = bool(cleanup_task.result())
        except BaseException:
            cleaned = False

        async with self._lock:
            if cleaned:
                self._clear_pending_cleanup(pooled)
            elif pooled.cleanup_task is cleanup_task:
                pooled.cleanup_task = None

        if cancelled:
            raise asyncio.CancelledError
        return cleaned

    async def _get_idle_connection(self) -> PooledConnection | None:
        """
        Get a valid idle connection from the pool.

        Validation and retirement are performed outside the metadata lock.
        """
        while True:
            async with self._lock:
                if self._closed or not self._idle:
                    return None
                pooled = self._idle.popleft()
                self._register_pending_cleanup(pooled, pending_permit=True)

            if self._should_retire(pooled):
                if not await self._cleanup_pooled(pooled):
                    raise RuntimeError("Connection cleanup is pending for an idle owner")
                continue

            if self._config.validate_on_acquire:
                healthy = await self._validate_connection(pooled)
                if not healthy:
                    if not await self._cleanup_pooled(pooled):
                        raise RuntimeError("Connection cleanup is pending for an idle owner")
                    continue

            return pooled

        return None

    async def _create_connection(self) -> PooledConnection:
        """Create a new connection via the connector factory."""
        connector = self._connector_factory()

        # The acquiring task owns the actual operation. A child wait_for can
        # hide a cancellation-suppressing connector's late physical handle.
        handle = await connector.connect(self._connection_config)

        pooled = PooledConnection(
            connector=connector,
            handle=handle,
            pool_id=self._pool_id,
        )

        with self._stats_lock:
            self._total_creates += 1

        logger.debug(
            "New connection created",
            pool_id=self._pool_id,
            session_id=handle.session_id,
            connector_id=handle.connector_id,
        )

        return pooled

    async def _validate_connection(self, pooled: PooledConnection) -> bool:
        """
        Validate connection health.

        Returns True if connection is healthy, False otherwise.
        """
        # Skip if recently checked
        if pooled.last_health_check is not None:
            since_check = (datetime.now(UTC) - pooled.last_health_check).total_seconds()
            if since_check < self._config.health_check_interval_seconds:
                return pooled.consecutive_failures == 0

        try:
            with self._stats_lock:
                self._total_health_checks += 1

            async with asyncio.timeout(10.0):
                health: HealthStatus = await pooled.connector.health_check(pooled.handle)

            if health.healthy:
                pooled.mark_healthy()
                return True

            pooled.mark_unhealthy()
            with self._stats_lock:
                self._failed_health_checks += 1
            return False
        except Exception as e:
            pooled.mark_unhealthy()
            with self._stats_lock:
                self._failed_health_checks += 1

            logger.warning(
                "Health check failed",
                pool_id=self._pool_id,
                session_id=pooled.handle.session_id,
                error=str(e),
                consecutive_failures=pooled.consecutive_failures,
            )
            return False

    def _should_retire(self, pooled: PooledConnection) -> bool:
        """Determine if a connection should be retired."""
        # Age exceeded
        if pooled.age_seconds > self._config.max_connection_age_seconds:
            return True

        # Idle too long
        if pooled.idle_seconds > self._config.max_idle_seconds:
            return True

        # Too many uses
        if pooled.use_count >= self._config.max_connection_uses:
            return True

        # Too many failures
        return pooled.consecutive_failures >= self._config.max_consecutive_failures

    async def _retire_connection(self, pooled: PooledConnection) -> None:
        """Retire a connection (close and don't return to pool)."""
        logger.debug(
            "Retiring connection",
            pool_id=self._pool_id,
            session_id=pooled.handle.session_id,
            age_seconds=pooled.age_seconds,
            use_count=pooled.use_count,
            consecutive_failures=pooled.consecutive_failures,
        )
        async with self._lock:
            self._register_pending_cleanup(pooled, pending_permit=pooled.pending_permit)
        if not await self._cleanup_pooled(pooled):
            raise RuntimeError("Connection cleanup is pending for the retired owner")

    async def _close_connection(self, pooled: PooledConnection) -> bool:
        """Close one physical handle after its disconnect succeeds."""
        async with self._lock:
            if pooled.closed or pooled.handle.session_id in self._closed_session_ids:
                return True
            if pooled.closing:
                return False
            pooled.closing = True
        try:
            await pooled.connector.disconnect(pooled.handle)
        except asyncio.CancelledError:
            async with self._lock:
                pooled.closing = False
            raise
        except Exception as e:
            async with self._lock:
                pooled.closing = False
            logger.warning(
                "Error closing connection",
                pool_id=self._pool_id,
                session_id=pooled.handle.session_id,
                error=str(e),
            )
            return False

        async with self._lock:
            pooled.closed = True
            pooled.closing = False
            self._remember_session_id(self._closed_session_ids, pooled.handle.session_id)
            with self._stats_lock:
                self._total_closes += 1
        return True

    async def _close_connection_handle(self, handle: ConnectionHandle) -> bool:
        """Close a connection handle using a fresh connector instance."""
        async with self._lock:
            if handle.session_id in self._closed_session_ids:
                return True
        connector = self._connector_factory()

        try:
            await connector.disconnect(handle)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(
                "Error closing connection",
                pool_id=self._pool_id,
                session_id=handle.session_id,
                error=str(e),
            )
            return False

        async with self._lock:
            self._remember_session_id(self._closed_session_ids, handle.session_id)
            with self._stats_lock:
                self._total_closes += 1
        return True

    async def close_all(self) -> None:
        """
        Close all connections and mark pool as closed.

        After calling this, the pool cannot be used.
        """
        async with self._lock:
            if not self._closed:
                self._closed = True
                self._generation += 1
                while self._idle:
                    pooled = self._idle.popleft()
                    self._register_pending_cleanup(pooled, pending_permit=False)

                for pooled in list(self._in_use.values()):
                    pooled.pending_permit = True
                    self._pending_cleanup[pooled.handle.session_id] = pooled
                    self._remember_session_id(
                        self._released_session_ids,
                        pooled.handle.session_id,
                    )
                self._in_use.clear()
            active_acquires_done = self._active_acquires_done

        cancelled = False
        try:
            await asyncio.shield(active_acquires_done.wait())
        except asyncio.CancelledError:
            cancelled = True
            await asyncio.shield(active_acquires_done.wait())

        async with self._lock:
            cleanup_items = list(self._pending_cleanup.values())

        cleanup_failed = False
        for pooled in cleanup_items:
            try:
                cleaned = await self._cleanup_pooled(pooled)
            except asyncio.CancelledError:
                cancelled = True
                cleaned = pooled.closed

            if cleaned:
                if await self._claim_permit(pooled, pooled.pending_permit):
                    self._semaphore.release()
            else:
                cleanup_failed = True

        logger.info(
            "Connection pool closed",
            pool_id=self._pool_id,
            total_creates=self._total_creates,
            total_closes=self._total_closes,
        )
        if cancelled:
            raise asyncio.CancelledError
        if cleanup_failed:
            raise RuntimeError("Connection cleanup remains pending for the closed pool")

    async def __aenter__(self) -> ConnectionPool[ConnectorT]:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close all connections."""
        await self.close_all()

    class _ConnectionContext:
        """Context manager for a single connection."""

        def __init__(self, pool: ConnectionPool, handle: ConnectionHandle) -> None:
            self._pool = pool
            self._handle = handle

        async def __aenter__(self) -> ConnectionHandle:
            return self._handle

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            await self._pool.release(self._handle)

    async def connection(self) -> _ConnectionContext:
        """
        Acquire a connection as an async context manager.

        Usage:
            async with await pool.connection() as handle:
                # Use handle...
        """
        handle = await self.acquire()
        return self._ConnectionContext(self, handle)

    def register_backpressure(
        self,
        *,
        source: str,
        level: BackpressureLevel,
        reason: str,
        pause_seconds: float = 0.0,
    ) -> None:
        """Register or replace one downstream backpressure signal."""
        with self._backpressure_lock:
            self._backpressure_signals.pop(source, None)
            self._backpressure_signals[source] = BackpressureSignal(
                source=source,
                level=level,
                reason=reason,
                pause_seconds=max(0.0, float(pause_seconds)),
            )
            while len(self._backpressure_signals) > self._config.max_backpressure_signals:
                self._backpressure_signals.popitem(last=False)

    def clear_backpressure(self, *, source: str) -> None:
        """Clear one downstream backpressure signal if present."""
        with self._backpressure_lock:
            self._backpressure_signals.pop(source, None)

    def backpressure_snapshot(self) -> PoolBackpressureSnapshot:
        """Expose a derived pool pressure level for upstream pollers."""
        with self._backpressure_lock:
            signals = tuple(self._backpressure_signals.values())

        pending_permits = sum(
            1 for pooled in self._pending_cleanup.values() if pooled.pending_permit
        )
        occupied_slots = len(self._in_use) + pending_permits
        available_slots = max(0, self._config.max_size - occupied_slots)
        utilization = (
            min(1.0, occupied_slots / self._config.max_size) if self._config.max_size > 0 else 0.0
        )
        level = BackpressureLevel.NORMAL
        suggested_delay = 0.0
        if signals:
            level = max(
                signals,
                key=lambda signal: _BACKPRESSURE_ORDER[signal.level],
            ).level
            suggested_delay = max(signal.pause_seconds for signal in signals)

        if level == BackpressureLevel.NORMAL:
            if utilization >= 0.95:
                level = BackpressureLevel.PAUSED
            elif utilization >= 0.85:
                level = BackpressureLevel.HIGH
            elif utilization >= 0.70:
                level = BackpressureLevel.ELEVATED

        if suggested_delay <= 0.0:
            if level == BackpressureLevel.ELEVATED:
                suggested_delay = 0.01
            elif level == BackpressureLevel.HIGH:
                suggested_delay = 0.05
            elif level == BackpressureLevel.PAUSED:
                suggested_delay = 0.10

        return PoolBackpressureSnapshot(
            pool_id=self._pool_id,
            level=level,
            utilization=utilization,
            available_slots=available_slots,
            suggested_poll_delay_seconds=suggested_delay,
            active_signals=signals,
        )

    def get_stats(self) -> PoolStats:
        """Get current pool statistics."""
        with self._stats_lock:
            return PoolStats(
                pool_id=self._pool_id,
                max_size=self._config.max_size,
                total_connections=self._total_creates - self._total_closes,
                idle_connections=len(self._idle),
                in_use_connections=len(self._in_use),
                total_acquires=self._total_acquires,
                total_releases=self._total_releases,
                total_creates=self._total_creates,
                total_closes=self._total_closes,
                total_health_checks=self._total_health_checks,
                failed_health_checks=self._failed_health_checks,
                acquire_wait_time_total_ms=self._acquire_wait_time_total_ms,
                created_at=self._created_at,
            )

    def _remember_session_id(self, bucket: OrderedDict[str, None], session_id: str) -> None:
        bucket.pop(session_id, None)
        bucket[session_id] = None
        while len(bucket) > self._config.max_lifecycle_session_ids:
            bucket.popitem(last=False)


_BACKPRESSURE_ORDER = {
    BackpressureLevel.NORMAL: 0,
    BackpressureLevel.ELEVATED: 1,
    BackpressureLevel.HIGH: 2,
    BackpressureLevel.PAUSED: 3,
}
