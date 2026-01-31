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
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Generic, TypeVar
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

    connector: "SourceConnector"
    handle: "ConnectionHandle"
    pool_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health_check: datetime | None = None
    consecutive_failures: int = 0
    use_count: int = 0

    @property
    def age_seconds(self) -> float:
        """Time since connection was created."""
        now = datetime.now(timezone.utc)
        return (now - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Time since connection was last used."""
        now = datetime.now(timezone.utc)
        return (now - self.last_used_at).total_seconds()

    def mark_used(self) -> None:
        """Update last_used_at and increment use count."""
        self.last_used_at = datetime.now(timezone.utc)
        self.use_count += 1

    def mark_healthy(self) -> None:
        """Record successful health check."""
        self.last_health_check = datetime.now(timezone.utc)
        self.consecutive_failures = 0

    def mark_unhealthy(self) -> None:
        """Record failed health check."""
        self.last_health_check = datetime.now(timezone.utc)
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
        config: "ConnectionConfig",
        pool_config: PoolConfig | None = None,
        pool_id: str | None = None,
        circuit_breaker: "CircuitBreaker | None" = None,
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
        self._pool_id = pool_id or f"pool-{uuid4().hex[:8]}"
        self._circuit_breaker = circuit_breaker

        # Connection storage
        self._idle: deque[PooledConnection] = deque()
        self._in_use: dict[str, PooledConnection] = {}

        # Synchronization primitives
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self._config.max_size)
        self._closed = False

        # Statistics
        self._stats_lock = threading.Lock()
        self._total_acquires = 0
        self._total_releases = 0
        self._total_creates = 0
        self._total_closes = 0
        self._total_health_checks = 0
        self._failed_health_checks = 0
        self._acquire_wait_time_total_ms = 0.0
        self._created_at = datetime.now(timezone.utc)

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

    async def acquire(self) -> "ConnectionHandle":
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
        if self._closed:
            raise PoolClosedError(self._pool_id)

        if self._circuit_breaker is not None and self._circuit_breaker.is_open():
            from polisyos.fabric.connectors.resilience import CircuitOpenError

            opened_at = self._circuit_breaker.opened_at or datetime.now(timezone.utc)
            raise CircuitOpenError(
                self._circuit_breaker.circuit_id,
                opened_at,
                self._circuit_breaker.config.timeout_seconds,
            )

        start_time = datetime.now(timezone.utc)

        try:
            # Wait for available slot with timeout
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._config.acquire_timeout_seconds,
            )
            if not acquired:
                raise PoolExhaustedError(
                    self._pool_id, self._config.acquire_timeout_seconds
                )
        except asyncio.TimeoutError:
            raise PoolExhaustedError(
                self._pool_id, self._config.acquire_timeout_seconds
            )

        try:
            async with self._lock:
                # Try to get an idle connection
                pooled = await self._get_idle_connection()

                if pooled is None:
                    # Create new connection
                    pooled = await self._create_connection()

                # Mark as in-use
                pooled.mark_used()
                self._in_use[pooled.handle.session_id] = pooled

                # Update statistics
                with self._stats_lock:
                    self._total_acquires += 1
                    elapsed = datetime.now(timezone.utc) - start_time
                    self._acquire_wait_time_total_ms += elapsed.total_seconds() * 1000

                logger.debug(
                    "Connection acquired",
                    pool_id=self._pool_id,
                    session_id=pooled.handle.session_id,
                    idle_count=len(self._idle),
                    in_use_count=len(self._in_use),
                )

                return pooled.handle
        except Exception:
            # Release semaphore if we failed to get a connection
            self._semaphore.release()
            raise

    async def release(self, handle: "ConnectionHandle") -> None:
        """
        Release a connection back to the pool.

        The connection may be returned to the idle pool for reuse,
        or closed if it has exceeded lifecycle limits.

        Args:
            handle: ConnectionHandle to release
        """
        if self._closed:
            async with self._lock:
                pooled = self._in_use.pop(handle.session_id, None)
            if pooled is not None:
                await self._close_connection(pooled)
                self._semaphore.release()
            else:
                await self._close_connection_handle(handle)
            return

        async with self._lock:
            pooled = self._in_use.pop(handle.session_id, None)

            if pooled is None:
                logger.warning(
                    "Released unknown connection",
                    pool_id=self._pool_id,
                    session_id=handle.session_id,
                )
                self._semaphore.release()
                return

            with self._stats_lock:
                self._total_releases += 1

            # Check if connection should be retired
            if self._should_retire(pooled):
                await self._retire_connection(pooled)
            else:
                # Optionally validate before returning to pool
                if self._config.validate_on_release:
                    healthy = await self._validate_connection(pooled)
                    if not healthy:
                        await self._retire_connection(pooled)
                        self._semaphore.release()
                        return

                # Return to idle pool
                self._idle.append(pooled)
                logger.debug(
                    "Connection released to pool",
                    pool_id=self._pool_id,
                    session_id=handle.session_id,
                    idle_count=len(self._idle),
                )

            self._semaphore.release()

    async def _get_idle_connection(self) -> PooledConnection | None:
        """
        Get a valid idle connection from the pool.

        Evicts stale connections and validates before returning.
        """
        while self._idle:
            pooled = self._idle.popleft()

            # Check if connection should be retired
            if self._should_retire(pooled):
                await self._retire_connection(pooled)
                continue

            # Optionally validate the connection
            if self._config.validate_on_acquire:
                healthy = await self._validate_connection(pooled)
                if not healthy:
                    await self._retire_connection(pooled)
                    continue

            return pooled

        return None

    async def _create_connection(self) -> PooledConnection:
        """Create a new connection via the connector factory."""
        connector = self._connector_factory()

        try:
            handle = await asyncio.wait_for(
                connector.connect(self._connection_config),
                timeout=self._config.connection_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                "Connection creation timed out after "
                f"{self._config.connection_timeout_seconds}s"
            )

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
            since_check = (
                datetime.now(timezone.utc) - pooled.last_health_check
            ).total_seconds()
            if since_check < self._config.health_check_interval_seconds:
                return pooled.consecutive_failures == 0

        try:
            with self._stats_lock:
                self._total_health_checks += 1

            health: "HealthStatus" = await asyncio.wait_for(
                pooled.connector.health_check(pooled.handle),
                timeout=10.0,  # Quick health check timeout
            )

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
        if pooled.consecutive_failures >= self._config.max_consecutive_failures:
            return True

        return False

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
        await self._close_connection(pooled)

    async def _close_connection(self, pooled: PooledConnection) -> None:
        """Close a pooled connection using its connector instance."""
        try:
            await pooled.connector.disconnect(pooled.handle)
            with self._stats_lock:
                self._total_closes += 1
        except Exception as e:
            logger.warning(
                "Error closing connection",
                pool_id=self._pool_id,
                session_id=pooled.handle.session_id,
                error=str(e),
            )

    async def _close_connection_handle(self, handle: "ConnectionHandle") -> None:
        """Close a connection handle using a fresh connector instance."""
        connector = self._connector_factory()

        try:
            await connector.disconnect(handle)
            with self._stats_lock:
                self._total_closes += 1
        except Exception as e:
            logger.warning(
                "Error closing connection",
                pool_id=self._pool_id,
                session_id=handle.session_id,
                error=str(e),
            )

    async def close_all(self) -> None:
        """
        Close all connections and mark pool as closed.

        After calling this, the pool cannot be used.
        """
        self._closed = True

        async with self._lock:
            # Close idle connections
            while self._idle:
                pooled = self._idle.popleft()
                await self._close_connection(pooled)

            # Close in-use connections
            for pooled in list(self._in_use.values()):
                await self._close_connection(pooled)
            self._in_use.clear()

        logger.info(
            "Connection pool closed",
            pool_id=self._pool_id,
            total_creates=self._total_creates,
            total_closes=self._total_closes,
        )

    async def __aenter__(self) -> "ConnectionPool[ConnectorT]":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close all connections."""
        await self.close_all()

    class _ConnectionContext:
        """Context manager for a single connection."""

        def __init__(self, pool: "ConnectionPool", handle: "ConnectionHandle") -> None:
            self._pool = pool
            self._handle = handle

        async def __aenter__(self) -> "ConnectionHandle":
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
