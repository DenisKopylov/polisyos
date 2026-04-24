"""Data structures for the ConnectorRegistry."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.ir.connectors import ConnectorCapability, ConnectorMetadataSpec, TrustLevel

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        HealthStatus,
        SourceConnector,
    )
    from polisyos.fabric.connectors.types import DatasetDescriptor

__all__ = [
    "ConnectorEntry",
    "ConnectorPreferences",
    "RegistryMetrics",
    "RegistryStats",
]


@dataclass
class ConnectorEntry:
    """
    Registry entry for a connector.

    Separates metadata (immutable) from runtime state (mutable).
    Factory function enables lazy instantiation with instance caching.
    """

    metadata: ConnectorMetadataSpec
    capabilities: ConnectorCapability
    connector_class: type[SourceConnector]
    factory: Callable[[], SourceConnector]
    default_config: ConnectionConfig | None = None

    # Runtime state (updated by registry operations)
    instance: SourceConnector | None = None
    loaded: bool = False
    known_datasets: frozenset[str] = field(default_factory=frozenset)
    dataset_descriptors: tuple[DatasetDescriptor, ...] = field(default_factory=tuple)
    last_health_check: datetime | None = None
    health_status: HealthStatus | None = None
    consecutive_failures: int = 0
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    _instance_lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    @property
    def fqid(self) -> str:
        """Fully qualified connector ID."""
        return self.metadata.fully_qualified_id

    @property
    def short_id(self) -> str:
        """Short connector ID without version."""
        return f"{self.metadata.namespace}.{self.metadata.connector_id}"


@dataclass
class ConnectorPreferences:
    """
    User preferences for connector selection during dataset resolution.

    Used by find_connectors_for_dataset() to rank candidates.
    """

    trust_weight: float = 0.3
    freshness_weight: float = 0.2
    capability_weight: float = 0.2
    reliability_weight: float = 0.3

    preferred_namespaces: list[str] = field(default_factory=list)
    excluded_connectors: set[str] = field(default_factory=set)
    min_trust_level: TrustLevel = TrustLevel.LOW

    def __post_init__(self) -> None:
        total = (
            self.trust_weight
            + self.freshness_weight
            + self.capability_weight
            + self.reliability_weight
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Preference weights must sum to 1.0, got {total}")


@dataclass
class RegistryStats:
    """Snapshot statistics for observability and monitoring."""

    registered_connectors: int
    loaded_connectors: int
    registrations_total: int
    queries_total: int
    get_calls_total: int
    active_pools: int
    namespaces: list[str]
    capabilities_distribution: dict[str, int]


@dataclass
class RegistryMetrics:
    """Monotonic counters suitable for metrics backends (snapshot)."""

    registrations_total: int
    queries_total: int
    get_calls_total: int
    pools_total: int
    pool_acquires_total: int
    pool_releases_total: int
    pool_creates_total: int
    pool_closes_total: int
    pool_health_checks_total: int
    pool_failed_health_checks_total: int
    pool_acquire_wait_time_total_ms: float
