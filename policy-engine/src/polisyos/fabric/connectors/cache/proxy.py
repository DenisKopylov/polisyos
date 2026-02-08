"""CachingConnectorProxy wraps a SourceConnector with cache behavior."""
from __future__ import annotations

import time
from typing import Any, Callable, Generic, TypeVar

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)
from polisyos.ir.connectors import ConnectorCapability

from .store import ConnectorCacheStore

logger = get_logger(__name__)

DataT = TypeVar("DataT")


class CachingConnectorProxy(Generic[DataT]):
    """Transparent caching wrapper for any SourceConnector."""

    def __init__(
        self,
        connector: SourceConnector[DataT],
        cache: ConnectorCacheStore,
        enable_prefetch: bool = True,
        schema_hash_provider: Callable[[FetchRequest, FetchResult[DataT]], str | None] | None = None,
    ) -> None:
        self._connector = connector
        self._cache = cache
        self._enable_prefetch = enable_prefetch
        self._schema_hash_provider = schema_hash_provider
        self._hits = 0
        self._misses = 0
        self._metrics = get_metrics()

    # Delegate all non-fetch methods
    @property
    def connector_id(self) -> str:
        return self._connector.connector_id

    @property
    def capabilities(self) -> ConnectorCapability:
        return self._connector.capabilities

    @property
    def metadata(self) -> Any:
        return self._connector.metadata

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return await self._connector.connect(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        await self._connector.disconnect(handle)

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return await self._connector.health_check(handle)

    async def list_datasets(self, handle: ConnectionHandle):
        async for dataset in self._connector.list_datasets(handle):
            yield dataset

    async def fetch_stream(self, handle: ConnectionHandle, request: FetchRequest):
        async for chunk in self._connector.fetch_stream(handle, request):
            yield chunk

    async def check_freshness(self, handle: ConnectionHandle, dataset_id: str, cached_version):
        return await self._connector.check_freshness(handle, dataset_id, cached_version)

    async def get_dataset_schema(self, handle: ConnectionHandle, dataset_id: str):
        return await self._connector.get_dataset_schema(handle, dataset_id)

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[DataT]:
        start_time = time.perf_counter()

        cached = self._cache.get(request, connector_id=self.connector_id)
        if cached:
            self._hits += 1
            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Cache HIT",
                cache_key=request.cache_key[:16],
                dataset_id=request.dataset_id,
                latency_ms=latency_ms,
                connector_id=self.connector_id,
            )
            self._record_metrics("hit", latency_ms / 1000)
            return cached.result

        self._misses += 1
        logger.info(
            "Cache MISS",
            cache_key=request.cache_key[:16],
            dataset_id=request.dataset_id,
            connector_id=self.connector_id,
        )
        self._record_metrics("miss", None)

        fetch_start = time.perf_counter()
        result = await self._connector.fetch(handle, request)
        fetch_duration_ms = (time.perf_counter() - fetch_start) * 1000

        schema_hash = None
        if self._schema_hash_provider is not None:
            try:
                schema_hash = self._schema_hash_provider(request, result)
            except Exception:
                schema_hash = None

        try:
            self._cache.put(
                request,
                result,
                connector_id=self.connector_id,
                schema_hash=schema_hash,
            )
        except Exception as exc:
            logger.warning(
                "Cache storage failed",
                error=str(exc),
                cache_key=request.cache_key[:16],
            )

        total_latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Fetch completed",
            cache_key=request.cache_key[:16],
            fetch_duration_ms=fetch_duration_ms,
            total_latency_ms=total_latency_ms,
        )
        self._record_metrics("miss", total_latency_ms / 1000)

        return result

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connector, name)

    def _record_metrics(self, status: str, latency_seconds: float | None) -> None:
        if not self._metrics:
            return
        if getattr(self._metrics, "connector_cache_operations_total", None):
            self._metrics.connector_cache_operations_total.add(
                1,
                {
                    "operation": "fetch",
                    "status": status,
                    "connector_id": self.connector_id,
                },
            )  # type: ignore[union-attr]
        if latency_seconds is not None and getattr(self._metrics, "connector_cache_latency_seconds", None):
            self._metrics.connector_cache_latency_seconds.record(
                latency_seconds,
                {"operation": "fetch"},
            )  # type: ignore[union-attr]
