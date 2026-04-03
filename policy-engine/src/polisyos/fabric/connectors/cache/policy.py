"""Cache policy system for connector cache entries."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    def is_valid(self, metadata: "CacheMetadata") -> bool:
        raise NotImplementedError

    @abstractmethod
    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime | None:
        raise NotImplementedError

    def should_evict(self, metadata: "CacheMetadata", context: EvictionContext) -> bool:
        return False


class TTLPolicy(CachePolicy):
    """Simple time-to-live policy."""

    def __init__(self, ttl: timedelta, policy_id: str = "ttl_default") -> None:
        self._ttl = ttl
        self._policy_id = policy_id

    @property
    def policy_id(self) -> str:
        return self._policy_id

    def is_valid(self, metadata: "CacheMetadata") -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(timezone.utc) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        return datetime.now(timezone.utc) + self._ttl


class StaticDataPolicy(CachePolicy):
    """Policy for data that never expires."""

    policy_id = "static_eternal"

    def is_valid(self, metadata: "CacheMetadata") -> bool:
        return True

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None


class VolatileDataPolicy(CachePolicy):
    """Policy for highly volatile data."""

    policy_id = "volatile_shortlived"

    def __init__(self, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)

    def is_valid(self, metadata: "CacheMetadata") -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(timezone.utc) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        return datetime.now(timezone.utc) + self._ttl


class SmartExpiryPolicy(CachePolicy):
    """Adaptive TTL based on data characteristics."""

    policy_id = "smart_adaptive"

    def is_valid(self, metadata: "CacheMetadata") -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(timezone.utc) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> datetime:
        now = datetime.now(timezone.utc)

        if request.date_end:
            delta_days = (now - request.date_end).days
            if delta_days <= 7:
                return now + timedelta(hours=6)
            if delta_days <= 365:
                return now + timedelta(days=30)

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
        return datetime.now(timezone.utc) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None

    def should_evict(self, metadata: "CacheMetadata", context: EvictionContext) -> bool:
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

    def is_valid(self, metadata: "CacheMetadata") -> bool:
        if metadata.expires_at is None:
            return True
        return datetime.now(timezone.utc) < metadata.expires_at

    def compute_expiry(self, request: FetchRequest, result: FetchResult[Any]) -> None:
        return None

    def should_evict(self, metadata: "CacheMetadata", context: EvictionContext) -> bool:
        return context.total_size_bytes > self.max_size_bytes


class PolicyRegistry:
    """Maps connectors/datasets to cache policies."""

    def __init__(self, default_policy: CachePolicy | None = None) -> None:
        default_policy = default_policy or TTLPolicy(ttl=timedelta(hours=24))
        self._policies: dict[str, CachePolicy] = {
            default_policy.policy_id: default_policy,
            "default": default_policy,
            "static": StaticDataPolicy(),
            "volatile": VolatileDataPolicy(ttl_minutes=5),
            "smart": SmartExpiryPolicy(),
        }
        self._connector_policies: dict[str, str] = {}
        self._dataset_policies: dict[str, str] = {}

    def register_policy(self, policy: CachePolicy) -> None:
        self._policies[policy.policy_id] = policy

    def set_connector_policy(self, connector_id: str, policy_id: str) -> None:
        if policy_id not in self._policies:
            raise KeyError(f"Unknown policy_id: {policy_id}")
        self._connector_policies[connector_id] = policy_id

    def set_dataset_policy(self, dataset_id: str, policy_id: str) -> None:
        if policy_id not in self._policies:
            raise KeyError(f"Unknown policy_id: {policy_id}")
        self._dataset_policies[dataset_id] = policy_id

    def get_policy(self, request: FetchRequest, *, connector_id: str | None = None) -> CachePolicy:
        if request.dataset_id in self._dataset_policies:
            return self._policies[self._dataset_policies[request.dataset_id]]

        if connector_id and connector_id in self._connector_policies:
            return self._policies[self._connector_policies[connector_id]]

        return self._policies["default"]

    def get_policy_by_id(self, policy_id: str) -> CachePolicy | None:
        return self._policies.get(policy_id) or self._policies.get("default")
