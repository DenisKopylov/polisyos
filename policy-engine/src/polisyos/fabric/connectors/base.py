"""SourceConnector Protocol and core abstractions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
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
    ResilienceInfo,
)

if TYPE_CHECKING:
    from polisyos.fabric.connectors.types import (
        DataChunk,
        DatasetDescriptor,
        FreshnessResult,
        ValidationResult,
    )


DataT = TypeVar("DataT")


# ============================================================================
# Connection Configuration
# ============================================================================


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Immutable connection configuration."""

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    auth_method: str | None = None
    auth_credentials: dict[str, str] = field(default_factory=dict)
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

    def redacted(self) -> "ConnectionConfig":
        """Return config with sensitive fields redacted for logging."""
        redacted_headers = {
            key: "***"
            if any(tok in key.lower() for tok in ("auth", "key", "token", "secret", "password"))
            else value
            for key, value in self.headers.items()
        }
        redacted_creds = {key: "***" for key in self.auth_credentials}

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
            "headers": config.headers,
            "auth_method": config.auth_method,
            "auth_credentials": config.auth_credentials,
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
    """Handle representing an active connection."""

    connector_id: str
    config: ConnectionConfig
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = field(default_factory=lambda: str(uuid4()))
    state: dict[str, Any] = field(default_factory=dict, compare=False, hash=False, repr=False)

    @property
    def age_seconds(self) -> float:
        """Get the age of this connection in seconds."""
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds()


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
        default_factory=lambda: datetime.now(timezone.utc),
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
            return value.replace(tzinfo=timezone.utc)
        return value


# ============================================================================
# Source Connector Protocol
# ============================================================================


@runtime_checkable
class SourceConnector(Protocol[DataT]):
    """Protocol for all external data source connectors."""

    connector_id: ClassVar[str]
    capabilities: ClassVar[ConnectorCapability]
    metadata: ClassVar[ConnectorMetadataSpec]

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        ...

    async def disconnect(self, handle: ConnectionHandle) -> None:
        ...

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        ...

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[DataT]:
        ...

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator["DatasetDescriptor"]:
        ...

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator["DataChunk[DataT]"]:
        ...

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> "FreshnessResult":
        ...

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        ...

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> "ValidationResult":
        ...


# ============================================================================
# Base Implementation Helpers
# ============================================================================


class BaseConnector(Generic[DataT]):
    """Base class providing common functionality for connectors."""

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

    def _ensure_overridden(self, method_name: str) -> None:
        if getattr(type(self), method_name) is getattr(BaseConnector, method_name):
            raise NotImplementedError(
                f"{type(self).__name__}.{method_name} must be implemented when "
                f"{method_name} capability is declared"
            )

    def _create_handle(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator["DatasetDescriptor"]:
        self._check_capability(ConnectorCapability.CATALOG_BROWSE)
        self._ensure_overridden("list_datasets")
        if False:  # pragma: no cover
            yield  # type: ignore

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator["DataChunk[DataT]"]:
        self._check_capability(ConnectorCapability.STREAMING)
        self._ensure_overridden("fetch_stream")
        if False:  # pragma: no cover
            yield  # type: ignore

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> "FreshnessResult":
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
    def validate_config(cls, config: ConnectionConfig) -> "ValidationResult":
        from polisyos.fabric.connectors.types import ValidationResult

        return ValidationResult.success()
