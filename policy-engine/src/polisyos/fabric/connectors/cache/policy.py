"""Cache policy system for connector cache entries."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from polisyos.fabric.connectors.base import FetchRequest, FetchResult

if TYPE_CHECKING:
    from .store import CacheMetadata


@dataclass(frozen=True, slots=True)
class EvictionContext:
    """Eviction context public type."""

    total_entries: int
    total_size_bytes: int
    recently_accessed_keys: set[str]


class CachePolicy(ABC):
    """Base class for cache policies."""

    @property
    @abstractmethod
    def policy_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_valid(self, metadata: CacheMetadata) -> bool:
        raise NotImplementedError

    @abstractmethod
    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime | None:
        raise NotImplementedError

    def should_evict(self, metadata: CacheMetadata, context: EvictionContext) -> bool:
        return False


class TTLPolicy(CachePolicy):
    """Simple time-to-live policy."""

    def __init__(
        self,
        ttl: timedelta,
        policy_id: str = "ttl_default",
        *,
        max_entries: int | None = 10000,
    ) -> None:
        self._ttl = ttl
        self._policy_id = policy_id
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries

    @property
    def policy_id(self) -> str:
        return self._policy_id

    def is_valid(self, metadata: CacheMetadata) -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(UTC) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        return datetime.now(UTC) + self._ttl


class StaticDataPolicy(CachePolicy):
    """Policy for data that never expires."""

    policy_id = "static_eternal"

    def __init__(self, *, max_entries: int | None = 10000) -> None:
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries

    def is_valid(self, metadata: CacheMetadata) -> bool:
        return True

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None


class VolatileDataPolicy(CachePolicy):
    """Policy for highly volatile data."""

    policy_id = "volatile_shortlived"

    def __init__(self, ttl_minutes: int = 5, *, max_entries: int | None = 10000) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries

    def is_valid(self, metadata: CacheMetadata) -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(UTC) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        return datetime.now(UTC) + self._ttl


class SmartExpiryPolicy(CachePolicy):
    """Adaptive TTL based on data characteristics."""

    policy_id = "smart_adaptive"

    def __init__(self, *, max_entries: int | None = 10000) -> None:
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries

    def is_valid(self, metadata: CacheMetadata) -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(UTC) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        now = datetime.now(UTC)

        if request.date_end:
            if request.date_end > now:
                return now + timedelta(minutes=5)

            if request.date_start and request.date_start <= request.date_end:
                window_span = request.date_end - request.date_start
                if request.date_end >= now - timedelta(hours=1) and window_span <= timedelta(
                    days=7
                ):
                    return now + timedelta(minutes=5)

            delta = now - request.date_end
            if delta <= timedelta(days=7):
                return now + timedelta(hours=6)
            if delta <= timedelta(days=365):
                return now + timedelta(days=30)
            return now + timedelta(days=365)

        # Real-time / no date bounds
        return now + timedelta(minutes=5)


class LRUPolicy(CachePolicy):
    """Least Recently Used eviction policy."""

    def __init__(self, max_entries: int = 10000, policy_id: str = "lru_default") -> None:
        self.max_entries = max_entries
        self._policy_id = policy_id

    @property
    def policy_id(self) -> str:
        return self._policy_id

    def is_valid(self, metadata: CacheMetadata) -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(UTC) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None

    def should_evict(self, metadata: CacheMetadata, context: EvictionContext) -> bool:
        if context.total_entries <= self.max_entries:
            return False
        return metadata.cache_key not in context.recently_accessed_keys


class SizeBoundedPolicy(CachePolicy):
    """Size-based eviction policy."""

    def __init__(self, max_size_gb: float = 10.0, policy_id: str = "size_bounded") -> None:
        self.max_size_bytes = int(max_size_gb * 1024**3)
        self._policy_id = policy_id

    @property
    def policy_id(self) -> str:
        return self._policy_id

    def is_valid(self, metadata: CacheMetadata) -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(UTC) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None

    def should_evict(self, metadata: CacheMetadata, context: EvictionContext) -> bool:
        return context.total_size_bytes > self.max_size_bytes


class PolicyRegistry:
    """Maps connectors/datasets to cache policies."""

    def __init__(
        self,
        default_policy: CachePolicy | None = None,
        *,
        max_connector_policy_mappings: int = 4096,
        max_dataset_policy_mappings: int = 4096,
    ) -> None:
        default_policy = default_policy or TTLPolicy(ttl=timedelta(hours=24))
        self._policies: dict[str, CachePolicy] = {
            default_policy.policy_id: default_policy,
            "default": default_policy,
            "static": StaticDataPolicy(),
            "volatile": VolatileDataPolicy(ttl_minutes=5),
            "smart": SmartExpiryPolicy(),
        }
        self._connector_policies: OrderedDict[str, str] = OrderedDict()
        self._dataset_policies: OrderedDict[str, str] = OrderedDict()
        self._max_connector_policy_mappings = self._validate_mapping_limit(
            "max_connector_policy_mappings",
            max_connector_policy_mappings,
        )
        self._max_dataset_policy_mappings = self._validate_mapping_limit(
            "max_dataset_policy_mappings",
            max_dataset_policy_mappings,
        )
        self._lock = threading.RLock()

    def register_policy(self, policy: CachePolicy) -> None:
        with self._lock:
            self._policies[policy.policy_id] = policy

    def set_connector_policy(self, connector_id: str, policy_id: str) -> None:
        with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Unknown policy_id: {policy_id}")
            self._connector_policies[connector_id] = policy_id
            self._connector_policies.move_to_end(connector_id)
            self._trim_mapping_locked(
                self._connector_policies,
                self._max_connector_policy_mappings,
            )

    def set_dataset_policy(self, dataset_id: str, policy_id: str) -> None:
        with self._lock:
            if policy_id not in self._policies:
                raise KeyError(f"Unknown policy_id: {policy_id}")
            self._dataset_policies[dataset_id] = policy_id
            self._dataset_policies.move_to_end(dataset_id)
            self._trim_mapping_locked(
                self._dataset_policies,
                self._max_dataset_policy_mappings,
            )

    def get_policy(self, request: FetchRequest, *, connector_id: str | None = None) -> CachePolicy:
        with self._lock:
            if request.dataset_id in self._dataset_policies:
                self._dataset_policies.move_to_end(request.dataset_id)
                return self._policies[self._dataset_policies[request.dataset_id]]

            if connector_id and connector_id in self._connector_policies:
                self._connector_policies.move_to_end(connector_id)
                return self._policies[self._connector_policies[connector_id]]

            return self._policies["default"]

    def get_policy_by_id(self, policy_id: str) -> CachePolicy | None:
        with self._lock:
            return self._policies.get(policy_id) or self._policies.get("default")

    @staticmethod
    def _validate_mapping_limit(name: str, value: int) -> int:
        limit = int(value)
        if limit < 1:
            raise ValueError(f"{name} must be >= 1")
        return limit

    @staticmethod
    def _trim_mapping_locked(mapping: OrderedDict[str, str], limit: int) -> None:
        while len(mapping) > limit:
            mapping.popitem(last=False)
