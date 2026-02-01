"""SourceConnector Protocol and core abstractions."""
from __future__ import annotations

import hashlib
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
    QualityTier,
)

if TYPE_CHECKING:
    from polisyos.core.contracts.fabric import EvidenceBundleRef
    from polisyos.fabric.connectors.types import (
        DataChunk,
        DatasetDescriptor,
        FreshnessResult,
        ValidationResult,
    )

try:
    from polisyos.core.contracts.fabric import EvidenceBundleRef
except Exception:  # pragma: no cover - optional at runtime
    EvidenceBundleRef = Any  # type: ignore[assignment]


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
# Fetch Request & Result
# ============================================================================


@dataclass(frozen=True, slots=True)
class FetchRequest:
    """Immutable, hashable fetch request specification."""

    dataset_id: str

    # Temporal bounds
    date_start: datetime | None = None
    date_end: datetime | None = None
    as_of: datetime | None = None

    # Dimension filters (immutable mapping)
    filters: tuple[tuple[str, tuple[str, ...]], ...] = ()

    # Incremental fetch
    incremental_since: DataVersion | None = None

    # Output preferences
    include_metadata: bool = True
    include_schema: bool = True

    # Pagination
    page_size: int | None = None
    page_token: str | None = None

    # Quality requirements
    min_quality_tier: QualityTier = QualityTier.UNVERIFIED

    # Execution hints
    retryable: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "date_start", _coerce_datetime(self.date_start))
        object.__setattr__(self, "date_end", _coerce_datetime(self.date_end))
        object.__setattr__(self, "as_of", _coerce_datetime(self.as_of))
        object.__setattr__(self, "filters", _normalize_filters(self.filters))

    @property
    def query_key(self) -> str:
        """Hash identifying the logical data request (pagination excluded)."""
        from polisyos.core.canon import to_canonical_bytes

        incremental_dump = (
            self.incremental_since.model_dump(mode="json")
            if self.incremental_since
            else None
        )
        canonical_data = {
            "dataset_id": self.dataset_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "as_of": self.as_of,
            "filters": {key: list(values) for key, values in self.filters},
            "incremental_since": incremental_dump,
            "min_quality_tier": self.min_quality_tier.value,
        }
        canonical_bytes = to_canonical_bytes(canonical_data)
        hash_hex = hashlib.sha256(canonical_bytes).hexdigest()
        return f"sha256:{hash_hex}"

    @property
    def request_key(self) -> str:
        """Hash for the full request (includes pagination and output prefs)."""
        from polisyos.core.canon import to_canonical_bytes

        incremental_dump = (
            self.incremental_since.model_dump(mode="json")
            if self.incremental_since
            else None
        )
        canonical_data = {
            "dataset_id": self.dataset_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "as_of": self.as_of,
            "filters": {key: list(values) for key, values in self.filters},
            "incremental_since": incremental_dump,
            "min_quality_tier": self.min_quality_tier.value,
            "include_metadata": self.include_metadata,
            "include_schema": self.include_schema,
            "page_size": self.page_size,
            "page_token": self.page_token,
        }
        canonical_bytes = to_canonical_bytes(canonical_data)
        hash_hex = hashlib.sha256(canonical_bytes).hexdigest()
        return f"sha256:{hash_hex}"

    @property
    def cache_key(self) -> str:
        """CAS-compatible cache key for the full request."""
        return self.request_key

    def with_pagination(
        self,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> "FetchRequest":
        """Create a new request with updated pagination parameters."""
        return FetchRequest(
            dataset_id=self.dataset_id,
            date_start=self.date_start,
            date_end=self.date_end,
            as_of=self.as_of,
            filters=self.filters,
            incremental_since=self.incremental_since,
            include_metadata=self.include_metadata,
            include_schema=self.include_schema,
            page_size=page_size if page_size is not None else self.page_size,
            page_token=page_token,
            min_quality_tier=self.min_quality_tier,
            retryable=self.retryable,
        )

    def with_filter(self, field: str, *values: str) -> "FetchRequest":
        """Create a new request with an additional or replaced filter."""
        current = {key: list(vals) for key, vals in self.filters}
        current[field] = list(values)
        new_filters = tuple((key, tuple(vals)) for key, vals in current.items())
        return FetchRequest(
            dataset_id=self.dataset_id,
            date_start=self.date_start,
            date_end=self.date_end,
            as_of=self.as_of,
            filters=new_filters,
            incremental_since=self.incremental_since,
            include_metadata=self.include_metadata,
            include_schema=self.include_schema,
            page_size=self.page_size,
            page_token=self.page_token,
            min_quality_tier=self.min_quality_tier,
            retryable=self.retryable,
        )


class ResilienceInfo(BaseModel):
    """Metadata describing resilience behavior applied to a fetch result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fallback_used: bool = Field(
        default=False,
        description="Whether a fallback strategy produced this result",
    )
    fallback_strategy: str | None = Field(
        default=None,
        description="Name of fallback strategy that succeeded",
    )
    retry_attempts: int | None = Field(
        default=None,
        ge=1,
        description="Retry attempt number that succeeded (if any)",
    )
    rate_limited: bool | None = Field(
        default=None,
        description="Whether a rate limiter delayed the request",
    )
    circuit_state: str | None = Field(
        default=None,
        description="Circuit breaker state observed during execution",
    )


class FetchResult(BaseModel, Generic[DataT]):
    """Immutable result of a fetch operation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    # Data payload
    data: DataT = Field(description="The fetched data (type depends on connector)")
    row_count: int = Field(ge=0, description="Number of rows in the result")

    # Schema
    schema_id: str = Field(description="Identifier of the data schema")
    schema_version: str = Field(
        pattern=r"^\d+\.\d+(\.\d+)?$",
        description="Version of the data schema",
    )

    # Version & provenance
    version: DataVersion = Field(description="Version information for this data snapshot")
    fetched_at: datetime = Field(description="When the fetch was performed (UTC)")
    source_updated_at: datetime | None = Field(
        default=None,
        description="When the source data was last updated",
    )

    # Evidence (Law E)
    evidence_ref: EvidenceBundleRef | None = Field(
        default=None,
        description="Reference to evidence bundle for provenance tracking",
    )

    # Quality indicators
    completeness: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of requested data that was returned",
    )
    quality_tier: QualityTier = Field(
        default=QualityTier.UNVERIFIED,
        description="Quality tier of the returned data",
    )
    quality_flags: frozenset[str] = Field(
        default=frozenset(),
        description="Quality issue flags",
    )

    # Pagination
    has_more: bool = Field(
        default=False,
        description="Whether more pages are available",
    )
    next_page_token: str | None = Field(
        default=None,
        description="Token for fetching the next page",
    )
    total_count: int | None = Field(
        default=None,
        description="Total number of rows (if known)",
    )

    # Performance metrics
    fetch_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken to fetch data in milliseconds",
    )
    bytes_transferred: int = Field(
        default=0,
        ge=0,
        description="Number of bytes transferred",
    )
    not_modified: bool = Field(
        default=False,
        description="True when the source signaled no changes (e.g., HTTP 304)",
    )

    resilience: ResilienceInfo | None = Field(
        default=None,
        description="Resilience metadata (fallbacks, retries, etc.)",
    )

    @field_validator("fetched_at", "source_updated_at", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def is_complete(self) -> bool:
        """Check if this result contains all available data."""
        return not self.has_more

    @property
    def is_high_quality(self) -> bool:
        """Check if data meets high quality standards."""
        return (
            self.quality_tier >= QualityTier.SILVER
            and self.completeness >= 0.95
            and len(self.quality_flags) == 0
        )

    def validate_against_schema(
        self,
        registry: "SchemaRegistry",
        strict: bool = False,
    ) -> list[str]:
        """
        Validate fetched data against its declared schema.

        Args:
            registry: Schema registry to look up schema
            strict: If True, fail on extra columns

        Returns:
            List of validation errors (empty if valid)
        """
        import pandas as pd

        from polisyos.fabric.connectors.contracts import (
            SchemaRegistry,
            SchemaVersion,
            validate_dataframe_against_schema,
        )

        if not isinstance(registry, SchemaRegistry):
            raise TypeError("registry must be a SchemaRegistry instance")

        schema = registry.get(
            self.schema_id,
            SchemaVersion.parse(self.schema_version),
        )

        if isinstance(self.data, pd.DataFrame):
            df = self.data
        elif isinstance(self.data, list):
            df = pd.DataFrame(self.data)
        else:
            return [
                "Cannot validate: data is not a DataFrame or list of dicts",
            ]

        return validate_dataframe_against_schema(df, schema, strict)

    def coerce_against_schema(
        self,
        registry: "SchemaRegistry",
        *,
        strict: bool = False,
        normalize_columns: bool = True,
        drop_extra: bool = False,
    ) -> "CoercionResult":
        """
        Coerce fetched data to its declared schema.

        Returns a CoercionResult with the coerced DataFrame and any issues.
        """
        import pandas as pd

        from polisyos.fabric.connectors.contracts import (
            CoercionResult,
            SchemaRegistry,
            SchemaVersion,
            coerce_dataframe_to_schema,
        )

        if not isinstance(registry, SchemaRegistry):
            raise TypeError("registry must be a SchemaRegistry instance")

        schema = registry.get(
            self.schema_id,
            SchemaVersion.parse(self.schema_version),
        )

        if isinstance(self.data, pd.DataFrame):
            df = self.data
        elif isinstance(self.data, list):
            df = pd.DataFrame(self.data)
        else:
            return CoercionResult(
                dataframe=pd.DataFrame(),
                errors=("Cannot coerce: data is not a DataFrame or list of dicts",),
                warnings=(),
                coerced_columns=(),
                dropped_columns=(),
            )

        return coerce_dataframe_to_schema(
            df,
            schema,
            strict=strict,
            normalize_columns=normalize_columns,
            drop_extra=drop_extra,
        )


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


# ============================================================================
# Internal helpers
# ============================================================================


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalize_filters(
    filters: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Normalize filters into a sorted, de-duplicated mapping-like tuple."""
    if not filters:
        return ()

    merged: dict[str, set[str]] = {}
    for key, values in filters:
        key = str(key)
        merged.setdefault(key, set()).update(str(v) for v in values)

    normalized = []
    for key in sorted(merged.keys()):
        normalized.append((key, tuple(sorted(merged[key]))))

    return tuple(normalized)


FetchResult.model_rebuild()
