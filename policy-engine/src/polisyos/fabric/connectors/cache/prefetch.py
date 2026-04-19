"""Predictive prefetching scheduler for connector cache."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from random import SystemRandom
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, SourceConnector

    from .store import CacheMetadata, ConnectorCacheStore

logger = get_logger(__name__)
_JITTER = SystemRandom()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


@dataclass(order=True, frozen=True, slots=True)
class PrefetchJob:
    """Prefetch job public type."""
    sort_key: tuple[int, float] = field(init=False, repr=False)
    dataset_id: str
    connector_id: str
    request: FetchRequest
    priority: int = 0
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    triggered_by: str = "expiry_prediction"
    cache_key: str | None = None
    retries: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "sort_key", (self.priority, self.scheduled_at.timestamp()))

    @property
    def dedupe_key(self) -> str:
        if self.cache_key:
            return self.cache_key
        return str(self.request.cache_key)

    def with_retry(self, *, scheduled_at: datetime) -> PrefetchJob:
        return PrefetchJob(
            dataset_id=self.dataset_id,
            connector_id=self.connector_id,
            request=self.request,
            priority=self.priority,
            scheduled_at=scheduled_at,
            triggered_by=self.triggered_by,
            cache_key=self.cache_key,
            retries=self.retries + 1,
        )


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
        max_queued_jobs: int = 1024,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._cache = cache
        self._registry = registry
        self._prefetch_window = timedelta(minutes=prefetch_window_minutes)
        self._scheduler_interval = scheduler_interval_seconds
        bounded_queue_size = max(1, max_queued_jobs)
        self._queue: asyncio.PriorityQueue[tuple[tuple[int, float], PrefetchJob]] = (
            asyncio.PriorityQueue(maxsize=bounded_queue_size)
        )
        self._running = False
        self._scheduler_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._requeue_tasks: set[asyncio.Task[None]] = set()
        self._queue_keys: set[str] = set()
        self._inflight_keys: set[str] = set()
        self._lock = asyncio.Lock()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._max_in_flight = max_in_flight_per_connector
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._max_queued_jobs = bounded_queue_size
        self._metrics = metrics if metrics is not None else _default_metrics()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._running = False
        tasks = [
            task
            for task in (self._scheduler_task, self._worker_task)
            if task is not None
        ]
        tasks.extend(self._requeue_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._scheduler_task = None
        self._worker_task = None
        self._requeue_tasks.clear()
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._queue.task_done()
        async with self._lock:
            self._queue_keys.clear()
            self._inflight_keys.clear()
        if getattr(self._metrics, "set_fabric_prefetch_backlog", None):
            self._metrics.set_fabric_prefetch_backlog(0)
        self._semaphores.clear()

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
        now = datetime.now(UTC)

        for metadata in expiring:
            if not metadata.expires_at:
                continue
            if metadata.expires_at <= now:
                continue
            if not metadata.connector_id:
                continue

            request = self._cache.get_request(metadata.cache_key)
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
                cache_key=metadata.cache_key,
            )
            if await self._enqueue_job(job):
                self._record_prefetch_metric("scheduled", metadata.connector_id)

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                _, job = await self._queue.get()
            except asyncio.CancelledError:
                return
            if getattr(self._metrics, "set_fabric_prefetch_backlog", None):
                self._metrics.set_fabric_prefetch_backlog(self._queue.qsize())

            dedupe_key = job.dedupe_key

            async with self._lock:
                self._queue_keys.discard(dedupe_key)
                if dedupe_key in self._inflight_keys:
                    self._queue.task_done()
                    continue
                self._inflight_keys.add(dedupe_key)

            sem = self._semaphores.setdefault(
                job.connector_id, asyncio.Semaphore(self._max_in_flight)
            )

            try:
                async with sem:
                    await self._run_job(job)
            finally:
                async with self._lock:
                    self._inflight_keys.discard(dedupe_key)
                self._queue.task_done()

    async def _run_job(self, job: PrefetchJob) -> None:
        # Skip if cache already refreshed and not expiring soon
        cached_meta = self._cache.get_metadata(job.dedupe_key)
        if cached_meta and cached_meta.expires_at:
            remaining = cached_meta.expires_at - datetime.now(UTC)
            if remaining > self._prefetch_window:
                self._record_prefetch_metric("skipped", job.connector_id)
                return

        try:
            connector = cast("SourceConnector[Any]", self._registry.get(job.connector_id))
            handle = cast(
                "ConnectionHandle",
                await self._registry.get_connection(job.connector_id),
            )
        except Exception as exc:
            logger.warning("Prefetch connect failed", connector_id=job.connector_id, error=str(exc))
            await self._maybe_retry(job)
            return

        try:
            result = await connector.fetch(handle, job.request)
            connector_metadata = getattr(connector, "metadata", None)
            self._cache.put(
                job.request,
                result,
                connector_id=job.connector_id,
                classification=getattr(connector_metadata, "data_classification", None),
                column_classification=getattr(connector_metadata, "column_classification", None),
            )
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

        retry_job = job.with_retry(scheduled_at=datetime.now(UTC))
        delay = self._backoff_seconds * (2 ** (retry_job.retries - 1))
        delay += _JITTER.uniform(0.0, self._backoff_seconds)

        async def _requeue() -> None:
            await asyncio.sleep(delay)
            await self._enqueue_job(
                PrefetchJob(
                    dataset_id=retry_job.dataset_id,
                    connector_id=retry_job.connector_id,
                    request=retry_job.request,
                    priority=retry_job.priority,
                    scheduled_at=datetime.now(UTC),
                    triggered_by=retry_job.triggered_by,
                    cache_key=retry_job.cache_key,
                    retries=retry_job.retries,
                )
            )

        task = asyncio.create_task(_requeue())
        self._requeue_tasks.add(task)
        task.add_done_callback(self._requeue_tasks.discard)
        self._record_prefetch_metric("retry", job.connector_id)

    async def _enqueue_job(self, job: PrefetchJob) -> bool:
        dedupe_key = job.dedupe_key
        async with self._lock:
            if dedupe_key in self._queue_keys or dedupe_key in self._inflight_keys:
                return False
            if len(self._queue_keys) >= self._max_queued_jobs or self._queue.full():
                self._record_prefetch_metric("dropped", job.connector_id)
                return False
            self._queue_keys.add(dedupe_key)
        try:
            self._queue.put_nowait((job.sort_key, job))
        except asyncio.QueueFull:
            async with self._lock:
                self._queue_keys.discard(dedupe_key)
            self._record_prefetch_metric("dropped", job.connector_id)
            return False
        if getattr(self._metrics, "set_fabric_prefetch_backlog", None):
            self._metrics.set_fabric_prefetch_backlog(self._queue.qsize())
        return True

    def _compute_priority(self, metadata: CacheMetadata) -> int:
        if not metadata.expires_at:
            return 100
        time_until_expiry = (metadata.expires_at - datetime.now(UTC)).total_seconds()
        urgency = max(0, 100 - int(time_until_expiry / 60))
        payload_size_bytes = int(metadata.payload_size_bytes)
        access_count = int(metadata.access_count)
        size_penalty = int(min(payload_size_bytes / (1024 * 1024), 50))
        hotness = min(access_count, 50)
        return 100 - urgency + size_penalty - hotness

    def _record_prefetch_metric(self, status: str, connector_id: str) -> None:
        metric = getattr(self._metrics, "connector_cache_prefetch_jobs_total", None)
        if metric is None:
            return
        metric.add(
            1,
            {"status": status, "connector_id": connector_id},
        )
