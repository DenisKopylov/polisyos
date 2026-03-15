"""Cache invalidation strategies and orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.fabric.connectors.base import ConnectionHandle, SourceConnector
from polisyos.fabric.connectors.contracts import ConnectorSchemaContract, EvolutionReport
from polisyos.fabric.connectors.types import FreshnessStatus
from polisyos.ir.connectors import ConnectorCapability, DataVersion

from .store import ConnectorCacheStore

logger = get_logger(__name__)


class InvalidationStrategy(str, Enum):
    HARD_DELETE = "hard_delete"
    SOFT_MARK = "soft_mark"
    REFRESH_ASYNC = "refresh_async"


@dataclass(frozen=True, slots=True)
class InvalidationEvent:
    trigger_type: str
    dataset_id: str
    timestamp: datetime
    reason: str
    metadata: dict[str, Any]


class InvalidationTrigger:
    """Detects when cache invalidation is needed."""

    async def check_for_updates(
        self,
        connector: SourceConnector[Any],
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion | None,
        cached_metadata: dict[str, Any] | None = None,
    ) -> InvalidationEvent | None:
        if ConnectorCapability.FRESHNESS_CHECK in connector.capabilities and cached_version:
            try:
                freshness = await connector.check_freshness(handle, dataset_id, cached_version)
            except Exception as exc:
                logger.warning("Freshness check failed", dataset_id=dataset_id, error=str(exc))
                return None

            if freshness.status == FreshnessStatus.STALE or freshness.new_version_available:
                return InvalidationEvent(
                    trigger_type="freshness_check",
                    dataset_id=dataset_id,
                    timestamp=datetime.now(timezone.utc),
                    reason=freshness.message or "Source reported stale",
                    metadata={
                        "status": freshness.status,
                        "new_version_hint": freshness.new_version_hint,
                    },
                )

        # File-based heuristic: compare mtime/size if dataset_id is a local path
        try:
            path = Path(dataset_id)
            if path.exists() and path.is_file():
                stat = path.stat()
                source_mtime = stat.st_mtime
                source_size = stat.st_size
                cached_sig = (cached_metadata or {}).get("source_signature")
                if cached_sig:
                    if cached_sig.get("mtime") != source_mtime or cached_sig.get("size") != source_size:
                        return InvalidationEvent(
                            trigger_type="file_signature",
                            dataset_id=dataset_id,
                            timestamp=datetime.now(timezone.utc),
                            reason="File signature changed",
                            metadata={"mtime": source_mtime, "size": source_size},
                        )
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

        return None


class SchemaChangeInvalidationTrigger:
    """
    Cache invalidation callback for connector schema contract updates.

    Register this callback in ContractRegistry.register_callback().
    """

    def __init__(self, cache_store: ConnectorCacheStore) -> None:
        self._cache_store = cache_store

    def on_contract_registered(
        self,
        contract: ConnectorSchemaContract,
        report: EvolutionReport | None,
    ) -> int:
        if report is None or not report.changes:
            return 0

        invalidated = self._cache_store.invalidate_by_schema_hash(
            connector_id=contract.connector_id,
            exclude_hash=contract.content_hash,
        )
        logger.info(
            "Schema-aware cache invalidation",
            connector_id=contract.connector_id,
            contract_id=contract.contract_id,
            invalidated_entries=invalidated,
            change_count=len(report.changes),
            breaking_count=len(report.breaking_changes),
        )
        return invalidated


class InvalidationOrchestrator:
    """Coordinates cache invalidation across the system."""

    def __init__(
        self,
        cache: ConnectorCacheStore,
        registry: Any,
        trigger: InvalidationTrigger | None = None,
    ) -> None:
        self._cache = cache
        self._registry = registry
        self._trigger = trigger or InvalidationTrigger()

    async def invalidate_dataset(
        self,
        dataset_id: str,
        strategy: InvalidationStrategy = InvalidationStrategy.SOFT_MARK,
    ) -> int:
        return self._cache.invalidate(strategy.value, dataset_id=dataset_id)

    async def invalidate_date_range(
        self,
        dataset_id: str,
        start: datetime,
        end: datetime,
        strategy: InvalidationStrategy = InvalidationStrategy.SOFT_MARK,
    ) -> int:
        return self._cache.invalidate(
            strategy.value,
            dataset_id=dataset_id,
            date_start=start,
            date_end=end,
        )

    async def scan_and_invalidate(self) -> list[InvalidationEvent]:
        events: list[InvalidationEvent] = []
        for connector_id, dataset_id in self._cache.list_dataset_connectors():
            if not connector_id:
                continue
            try:
                connector = self._registry.get(connector_id)
                handle = await self._registry.get_connection(connector_id)
            except Exception as exc:
                logger.warning("Failed to acquire connector", connector_id=connector_id, error=str(exc))
                continue

            cached_meta = self._cache.get_latest_metadata(dataset_id)
            cached_version = cached_meta.source_version if cached_meta else None

            try:
                event = await self._trigger.check_for_updates(
                    connector,
                    handle,
                    dataset_id,
                    cached_version,
                    cached_metadata={"source_signature": None},
                )
            finally:
                try:
                    await self._registry.release_connection(connector_id, handle)
                except Exception as exc:
                    logger.debug("Ignored exception: %s", exc)

            if event:
                await self.invalidate_dataset(dataset_id, InvalidationStrategy.SOFT_MARK)
                events.append(event)

        return events
