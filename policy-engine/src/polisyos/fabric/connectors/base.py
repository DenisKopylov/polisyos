"""Connector protocol, connection contracts, and shared runtime models.

This module defines the capability boundary for all Fabric connectors: concrete implementations
must expose ``SourceConnector`` semantics and may extend ``BaseConnector`` while planners and
profile resolvers pass immutable ``ConnectionConfig`` / ``ConnectionHandle`` objects at runtime.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    FetchRequest,
    FetchResult,
)
from polisyos.ir.connectors import (
    QualityTier as QualityTier,
)
from polisyos.ir.connectors import (
    ResilienceInfo as ResilienceInfo,
)

if TYPE_CHECKING:
    from polisyos.fabric.connectors.types import (
        DataChunk,
        DatasetDescriptor,
        FreshnessResult,
        ValidationResult,
    )


DataT = TypeVar("DataT")


def _freeze_nested(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_nested(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_nested(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_nested(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_nested(item) for item in value)
    return value


class ConnectionState:
    """Mutable runtime state owner hidden behind immutable handle snapshots."""

    __slots__ = ("_data", "_lock")

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def setdefault(self, key: str, default: Any) -> Any:
        with self._lock:
            return self._data.setdefault(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.pop(key, default)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def snapshot(self) -> Mapping[str, Any]:
        with self._lock:
            return _freeze_nested(self._data)


# ============================================================================
# Connection Configuration
# ============================================================================


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Immutable runtime connection settings for one connector endpoint.

    ``ConnectionConfig`` carries transport/auth/retry/rate-limit knobs only; planner-facing
    capability semantics live in ``SourceExecutionPolicy`` and connector ``capabilities``.
    """

    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    auth_method: str | None = None
    auth_credentials: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_rps: float | None = None

    # Connection pooling
    max_connections: int = 10
    keepalive_seconds: int = 30

    # SSL/TLS settings
    verify_ssl: bool = True
    ca_bundle_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", _freeze_nested(dict(self.headers)))
        object.__setattr__(self, "auth_credentials", _freeze_nested(dict(self.auth_credentials)))

    def redacted(self) -> ConnectionConfig:
        """Return config with sensitive fields redacted for logging."""
        redacted_headers = {
            key: "***"
            if any(tok in key.lower() for tok in ("auth", "key", "token", "secret", "password"))
            else value
            for key, value in self.headers.items()
        }
        redacted_creds = dict.fromkeys(self.auth_credentials, "***")

        return ConnectionConfig(
            url=self.url,
            headers=redacted_headers,
            auth_method=self.auth_method,
            auth_credentials=redacted_creds,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            retry_delay_seconds=self.retry_delay_seconds,
            rate_limit_rps=self.rate_limit_rps,
            max_connections=self.max_connections,
            keepalive_seconds=self.keepalive_seconds,
            verify_ssl=self.verify_ssl,
            ca_bundle_path=self.ca_bundle_path,
        )

    def to_dict(self, redact: bool = True) -> dict[str, Any]:
        """Convert to dictionary, optionally redacting sensitive fields."""
        config = self.redacted() if redact else self
        return {
            "url": config.url,
            "headers": dict(config.headers),
            "auth_method": config.auth_method,
            "auth_credentials": dict(config.auth_credentials),
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
            "retry_delay_seconds": config.retry_delay_seconds,
            "rate_limit_rps": config.rate_limit_rps,
            "max_connections": config.max_connections,
            "keepalive_seconds": config.keepalive_seconds,
            "verify_ssl": config.verify_ssl,
            "ca_bundle_path": config.ca_bundle_path,
        }


@dataclass(frozen=True, slots=True)
class ConnectionHandle:
    """Ephemeral connection/session handle created by ``SourceConnector.connect``."""

    connector_id: str
    config: ConnectionConfig
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    session_id: str = field(default_factory=lambda: str(uuid4()))
    _state: ConnectionState = field(
        default_factory=ConnectionState,
        compare=False,
        hash=False,
        repr=False,
        init=False,
    )

    @property
    def age_seconds(self) -> float:
        """Get the age of this connection in seconds."""
        delta = datetime.now(UTC) - self.created_at
        return delta.total_seconds()

    @property
    def state(self) -> Mapping[str, Any]:
        """Immutable snapshot of runtime state for diagnostics and read-only inspection."""
        return self._state.snapshot()

    def get_state(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        self._state.set(key, value)

    def setdefault_state(self, key: str, default: Any) -> Any:
        return self._state.setdefault(key, default)

    def pop_state(self, key: str, default: Any = None) -> Any:
        return self._state.pop(key, default)

    def clear_state(self) -> None:
        self._state.clear()


class HealthStatus(BaseModel):
    """Health check result for a connector connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    healthy: bool = Field(description="Whether the connection is healthy")
    message: str = Field(default="", description="Status message")
    latency_ms: float | None = Field(
        default=None,
        description="Round-trip latency in milliseconds",
    )
    rate_limit_remaining: int | None = Field(
        default=None,
        description="Remaining API calls before rate limit",
    )
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the health check was performed",
    )

    source_version: str | None = Field(
        default=None,
        description="API/service version reported by source",
    )
    features_available: frozenset[str] = Field(
        default=frozenset(),
        description="Features available on this connection",
    )

    @field_validator("checked_at", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class DatasetCapabilitySnapshot(BaseModel):
    """Connector-provided dataset capability metadata for query planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(description="Logical source name")
    dataset_id: str = Field(description="Dataset identifier requested by the planner")
    resolved_dataset_id: str = Field(description="Transport-resolved dataset identifier")
    preferred_transport: str = Field(default="default", description="Recommended transport mode")
    dimension_order: tuple[str, ...] = Field(
        default=(),
        description="Preferred dimension order for keyed transport APIs",
    )
    allowed_positions: Mapping[str, tuple[str, ...]] = Field(
        default_factory=dict,
        description="Allowed dimension members by dimension id",
    )
    availability_hash: str = Field(
        default="", description="Hash of availability/constraint metadata"
    )
    constraint_hash: str = Field(default="", description="Hash of content constraints")
    estimated_cardinality: int | None = Field(
        default=None,
        description="Estimated number of cells for the dataset or request domain",
    )
    version_hint: str = Field(default="", description="Dataset version or transport revision hint")
    last_checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the snapshot was produced",
    )

    @field_validator("last_checked_at", mode="after")
    @classmethod
    def _ensure_snapshot_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @field_validator("version_hint", mode="before")
    @classmethod
    def _normalize_version_hint(cls, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text

    @field_validator("allowed_positions", mode="before")
    @classmethod
    def _freeze_allowed_positions(cls, value: Any) -> Mapping[str, tuple[str, ...]]:
        if value is None:
            return MappingProxyType({})
        if not isinstance(value, Mapping):
            raise TypeError("allowed_positions must be a mapping")
        normalized = {
            str(key): tuple(str(item) for item in values) for key, values in value.items()
        }
        return MappingProxyType(normalized)


class AsyncFetchLease(BaseModel):
    """Lease describing an asynchronous or deferred connector fetch job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lease_id: str = Field(description="Stable lease identifier for resume/poll")
    connector_id: str = Field(description="Connector that owns the lease")
    dataset_id: str = Field(description="Dataset id associated with the async job")
    request_key: str = Field(description="Logical request key")
    status: str = Field(default="pending", description="Lease status")
    poll_after_seconds: float = Field(default=5.0, ge=0.0)
    status_url: str | None = Field(default=None)
    download_url: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the lease was created",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def _ensure_lease_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


# ============================================================================
# Source Connector Protocol
# ============================================================================


@runtime_checkable
class SourceConnector(Protocol[DataT]):
    """Protocol implemented by connector families such as SDMX, CKAN, REST, and Socrata.

    ``capabilities`` is the hard contract planners should inspect before calling optional methods:
    unsupported async, streaming, or schema operations may raise ``CapabilityError``.
    """

    connector_id: ClassVar[str]
    capabilities: ClassVar[ConnectorCapability]
    metadata: ClassVar[ConnectorMetadataSpec]

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle: ...

    async def disconnect(self, handle: ConnectionHandle) -> None: ...

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus: ...

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[DataT]: ...

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]: ...

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[DataT]]: ...

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> FreshnessResult: ...

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]: ...

    async def describe_dataset(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> DatasetCapabilitySnapshot | None: ...

    async def fetch_async(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncFetchLease: ...

    async def poll_async_fetch(
        self,
        handle: ConnectionHandle,
        lease: AsyncFetchLease,
    ) -> AsyncFetchLease | FetchResult[DataT]: ...

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult: ...


# ============================================================================
# Base Implementation Helpers
# ============================================================================


class BaseConnector(Generic[DataT]):
    """Shared connector helpers for capability checks and default dataset descriptions."""

    connector_id: ClassVar[str] = "base.connector"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability(0)
    metadata: ClassVar[ConnectorMetadataSpec]

    def _check_capability(self, required: ConnectorCapability) -> None:
        from polisyos.fabric.connectors.types import CapabilityError

        if not (self.capabilities & required):
            raise CapabilityError(
                connector_id=self.connector_id,
                required=required,
                available=self.capabilities,
            )

    async def describe_dataset(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> DatasetCapabilitySnapshot | None:
        del handle
        return DatasetCapabilitySnapshot(
            source=str(self.connector_id).split(".", 1)[0],
            dataset_id=dataset_id,
            resolved_dataset_id=dataset_id,
        )

    async def fetch_async(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncFetchLease:
        from polisyos.fabric.connectors.types import CapabilityError

        del handle, request
        raise CapabilityError(
            connector_id=self.connector_id,
            required=ConnectorCapability.RESUMABLE,
            available=self.capabilities,
        )

    async def poll_async_fetch(
        self,
        handle: ConnectionHandle,
        lease: AsyncFetchLease,
    ) -> AsyncFetchLease | FetchResult[DataT]:
        from polisyos.fabric.connectors.types import CapabilityError

        del handle, lease
        raise CapabilityError(
            connector_id=self.connector_id,
            required=ConnectorCapability.RESUMABLE,
            available=self.capabilities,
        )

    def _ensure_overridden(self, method_name: str) -> None:
        if getattr(type(self), method_name) is getattr(BaseConnector, method_name):
            raise NotImplementedError(
                f"{type(self).__name__}.{method_name} must be implemented when "
                f"{method_name} capability is declared"
            )

    def _create_handle(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        self._check_capability(ConnectorCapability.CATALOG_BROWSE)
        self._ensure_overridden("list_datasets")
        if False:  # pragma: no cover
            yield  # type: ignore

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[DataT]]:
        self._check_capability(ConnectorCapability.STREAMING)
        self._ensure_overridden("fetch_stream")
        if False:  # pragma: no cover
            yield  # type: ignore

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> FreshnessResult:
        self._check_capability(ConnectorCapability.FRESHNESS_CHECK)
        self._ensure_overridden("check_freshness")
        from polisyos.fabric.connectors.types import FreshnessResult, FreshnessStatus

        return FreshnessResult(status=FreshnessStatus.UNKNOWN)

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        self._check_capability(ConnectorCapability.SCHEMA_INTROSPECTION)
        self._ensure_overridden("get_dataset_schema")
        return {}

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        from polisyos.fabric.connectors.types import ValidationResult

        return ValidationResult.success()
