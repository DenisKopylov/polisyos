"""Predictive prefetching scheduler for connector cache."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, SourceConnector

from .store import CacheMetadata, ConnectorCacheStore

logger = get_logger(__name__)


@dataclass(order=True)
class PrefetchJob:
    sort_key: tuple[int, float] = field(init=False, repr=False)
    dataset_id: str
    connector_id: str
    request: FetchRequest
    priority: int = 0
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_by: str = "expiry_prediction"
    cache_key: str | None = None
    retries: int = 0

    def __post_init__(self) -> None:
        self.sort_key = (self.priority, self.scheduled_at.timestamp())


class PrefetchScheduler:
    """Background scheduler for predictive cache warming."""

    def __init__(
        self,
        cache: ConnectorCacheStore,
        registry: Any,
        prefetch_window_minutes: int = 30,
        scheduler_interval_seconds: int = 300,
        max_in_flight_per_connector: int = 2,
        max_retries: int = 3,
        backoff_seconds: float = 30.0,
    ) -> None:
        self._cache = cache
        self._registry = registry
        self._prefetch_window = timedelta(minutes=prefetch_window_minutes)
        self._scheduler_interval = scheduler_interval_seconds
        self._queue: asyncio.PriorityQueue[tuple[tuple[int, float], PrefetchJob]] = (
            asyncio.PriorityQueue()
        )
        self._running = False
        self._scheduler_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._queue_keys: set[str] = set()
        self._inflight_keys: set[str] = set()
        self._lock = asyncio.Lock()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._max_in_flight = max_in_flight_per_connector
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._metrics = get_metrics()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                await self._schedule_expiring_entries()
            except Exception as exc:
                logger.warning("Prefetch scheduler scan failed", error=str(exc))
            await asyncio.sleep(self._scheduler_interval)

    async def _schedule_expiring_entries(self) -> None:
        window_seconds = self._prefetch_window.total_seconds()
        expiring = self._cache.list_expiring_entries(window_seconds)
        now = datetime.now(timezone.utc)

        for metadata in expiring:
            if not metadata.expires_at:
                continue
            if metadata.expires_at <= now:
                continue
            if not metadata.connector_id:
                continue

            cache_key = metadata.cache_key
            async with self._lock:
                if cache_key in self._queue_keys or cache_key in self._inflight_keys:
                    continue

            request = self._cache.get_request(cache_key)
            if request is None:
                continue

            priority = self._compute_priority(metadata)
            job = PrefetchJob(
                dataset_id=metadata.dataset_id,
                connector_id=metadata.connector_id,
                request=request,
                priority=priority,
                scheduled_at=now,
                triggered_by="expiry_prediction",
                cache_key=cache_key,
            )

            async with self._lock:
                self._queue_keys.add(cache_key)
            await self._queue.put((job.sort_key, job))
            self._record_prefetch_metric("scheduled", metadata.connector_id)

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                _, job = await self._queue.get()
            except asyncio.CancelledError:
                return

            cache_key = job.cache_key or job.request.cache_key

            async with self._lock:
                self._queue_keys.discard(cache_key)
                if cache_key in self._inflight_keys:
                    self._queue.task_done()
                    continue
                self._inflight_keys.add(cache_key)

            sem = self._semaphores.setdefault(
                job.connector_id, asyncio.Semaphore(self._max_in_flight)
            )

            try:
                async with sem:
                    await self._run_job(job)
            finally:
                async with self._lock:
                    self._inflight_keys.discard(cache_key)
                self._queue.task_done()

    async def _run_job(self, job: PrefetchJob) -> None:
        # Skip if cache already refreshed and not expiring soon
        cache_key = job.cache_key or job.request.cache_key
        cached_meta = self._cache.get_metadata(cache_key)
        if cached_meta and cached_meta.expires_at:
            remaining = cached_meta.expires_at - datetime.now(timezone.utc)
            if remaining > self._prefetch_window:
                self._record_prefetch_metric("skipped", job.connector_id)
                return

        try:
            connector: SourceConnector[Any] = self._registry.get(job.connector_id)
            handle: ConnectionHandle = await self._registry.get_connection(job.connector_id)
        except Exception as exc:
            logger.warning("Prefetch connect failed", connector_id=job.connector_id, error=str(exc))
            await self._maybe_retry(job)
            return

        try:
            result = await connector.fetch(handle, job.request)
            self._cache.put(job.request, result, connector_id=job.connector_id)
            self._record_prefetch_metric("success", job.connector_id)
        except Exception as exc:
            logger.warning("Prefetch fetch failed", connector_id=job.connector_id, error=str(exc))
            await self._maybe_retry(job)
        finally:
            try:
                await self._registry.release_connection(job.connector_id, handle)
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

    async def _maybe_retry(self, job: PrefetchJob) -> None:
        if job.retries >= self._max_retries:
            self._record_prefetch_metric("error", job.connector_id)
            return

        job.retries += 1
        delay = self._backoff_seconds * (2 ** (job.retries - 1))
        delay += random.uniform(0, self._backoff_seconds)

        async def _requeue() -> None:
            await asyncio.sleep(delay)
            job.scheduled_at = datetime.now(timezone.utc)
            job.sort_key = (job.priority, job.scheduled_at.timestamp())
            async with self._lock:
                if job.cache_key and job.cache_key in self._queue_keys:
                    return
            await self._queue.put((job.sort_key, job))
            async with self._lock:
                if job.cache_key:
                    self._queue_keys.add(job.cache_key)

        asyncio.create_task(_requeue())
        self._record_prefetch_metric("retry", job.connector_id)

    def _compute_priority(self, metadata: CacheMetadata) -> int:
        if not metadata.expires_at:
            return 100
        time_until_expiry = (metadata.expires_at - datetime.now(timezone.utc)).total_seconds()
        urgency = max(0, 100 - int(time_until_expiry / 60))
        size_penalty = int(min(metadata.payload_size_bytes / (1024 * 1024), 50))
        hotness = min(metadata.access_count, 50)
        return 100 - urgency + size_penalty - hotness

    def _record_prefetch_metric(self, status: str, connector_id: str) -> None:
        if not self._metrics or not getattr(self._metrics, "connector_cache_prefetch_jobs_total", None):
            return
        self._metrics.connector_cache_prefetch_jobs_total.add(
            1,
            {"status": status, "connector_id": connector_id},
        )  # type: ignore[union-attr]
