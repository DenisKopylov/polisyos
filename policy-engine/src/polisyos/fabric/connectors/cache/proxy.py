"""CachingConnectorProxy wraps a SourceConnector with cache behavior."""

from __future__ import annotations

import time
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from polisyos.core.observability import MetricsRegistry
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        DatasetDescriptor,
        FetchRequest,
        FetchResult,
        HealthStatus,
        SourceConnector,
    )
    from polisyos.fabric.connectors.types import DataChunk, FreshnessResult
    from polisyos.ir.connectors import ConnectorCapability

    from .store import ConnectorCacheStore

logger = get_logger(__name__)

DataT = TypeVar("DataT")


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


async def _resolve_async_iterator[T](
    candidate: AsyncIterator[T] | Awaitable[AsyncIterator[T]],
) -> AsyncIterator[T]:
    resolved = await candidate if isawaitable(candidate) else candidate
    return resolved


class CachingConnectorProxy[DataT]:
    """Transparent caching wrapper for any SourceConnector."""

    def __init__(
        self,
        connector: SourceConnector[DataT],
        cache: ConnectorCacheStore,
        enable_prefetch: bool = True,
        schema_hash_provider: Callable[[FetchRequest, FetchResult[DataT]], str | None]
        | None = None,
        *,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._connector = connector
        self._cache = cache
        self._enable_prefetch = enable_prefetch
        self._schema_hash_provider = schema_hash_provider
        self._hits = 0
        self._misses = 0
        self._metrics = metrics if metrics is not None else _default_metrics()

    # Delegate all non-fetch methods
    @property
    def connector_id(self) -> str:
        return str(self._connector.connector_id)

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

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        datasets = await _resolve_async_iterator(self._connector.list_datasets(handle))
        async for dataset in datasets:
            yield dataset

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[DataT]]:
        chunks = await _resolve_async_iterator(self._connector.fetch_stream(handle, request))
        async for chunk in chunks:
            yield chunk

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: Any,
    ) -> FreshnessResult:
        return await self._connector.check_freshness(handle, dataset_id, cached_version)

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            await self._connector.get_dataset_schema(handle, dataset_id),
        )

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
            connector_metadata = getattr(self._connector, "metadata", None)
            self._cache.put(
                request,
                result,
                connector_id=self.connector_id,
                schema_hash=schema_hash,
                classification=getattr(connector_metadata, "data_classification", None),
                column_classification=getattr(connector_metadata, "column_classification", None),
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
        operations_total = getattr(self._metrics, "connector_cache_operations_total", None)
        if operations_total is not None:
            operations_total.add(
                1,
                {
                    "operation": "fetch",
                    "status": status,
                    "connector_id": self.connector_id,
                },
            )
        latency_metric = getattr(self._metrics, "connector_cache_latency_seconds", None)
        if latency_seconds is not None and latency_metric is not None:
            latency_metric.record(
                latency_seconds,
                {"operation": "fetch"},
            )
