"""Canonical connector contracts for the data fabric layer.

These contracts define the interface boundary between external data sources and
PolicyOS fabric connectors. All connectors must produce artifacts conforming to
these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, Flag, IntEnum, auto
from functools import cached_property
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.canon import content_hash, to_canonical_bytes
from polisyos.ir.refs import EvidenceBundleRef


class ConnectorCapability(Flag):
    """Advertise which fetch, filtering, metadata, and resilience behaviors exist.

    Connector orchestration uses this bitmask to decide whether requests can be
    pushed down to the source, resumed incrementally, or require client-side
    fallback logic. Store the combined mask in ``ConnectorMetadataSpec.capabilities``.
    """

    # Data access patterns
    CATALOG_BROWSE = auto()  # Can list available datasets
    FULL_FETCH = auto()  # Can fetch entire dataset
    INCREMENTAL_FETCH = auto()  # Can fetch only changes since timestamp
    STREAMING = auto()  # Supports streaming large datasets

    # Filtering capabilities (server-side pushdown)
    DATE_RANGE_FILTER = auto()  # Server-side date filtering
    DIMENSION_FILTER = auto()  # Server-side dimension filtering
    CUSTOM_QUERY = auto()  # Supports query language (SQL, GraphQL, SDMX)

    # Metadata capabilities
    SCHEMA_INTROSPECTION = auto()  # Can describe data schema
    FRESHNESS_CHECK = auto()  # Can check staleness without full fetch
    PROVENANCE_METADATA = auto()  # Provides source/methodology info

    # Quality capabilities
    REVISION_HISTORY = auto()  # Provides historical revisions
    CONFIDENCE_INTERVALS = auto()  # Provides uncertainty bounds

    # Operational capabilities
    RATE_LIMIT_AWARE = auto()  # Reports rate limit status
    RESUMABLE = auto()  # Supports resuming interrupted fetches


class VersionStrategy(str, Enum):
    """Versioning strategies for cached data."""

    ETAG = "etag"
    TIMESTAMP = "timestamp"
    REVISION = "revision"
    CONTENT_HASH = "content_hash"


class TrustLevel(IntEnum):
    """Rank source provenance for connector admission and downstream governance.

    Higher tiers represent institutionally backed or authoritative sources and
    can be used by query filters, evidence scoring, and manual review tooling.
    """

    UNVERIFIED = 0  # Unknown source, requires manual validation
    LOW = 1  # User-provided, no institutional backing
    MEDIUM = 2  # Known organization, standard quality
    HIGH = 3  # Authoritative source (central bank, NSO)
    AUTHORITATIVE = 4  # Official government/regulatory source


class QualityTier(IntEnum):
    """Data quality classification aligned with existing QualityIndicators."""

    UNVERIFIED = 0
    BRONZE = 1  # Raw data, minimal validation
    SILVER = 2  # Cleaned, schema-validated
    GOLD = 3  # Reconciled, cross-validated
    PLATINUM = 4  # Production-ready, full evidence chain


class DataVersion(BaseModel):
    """Version identifier for cached data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: VersionStrategy = Field(
        description="Versioning strategy used for this data",
    )
    value: str = Field(
        description="Strategy-specific version value (ETag, timestamp ISO, revision, or hash)",
    )
    timestamp: datetime = Field(
        description="When this version was recorded (UTC)",
    )
    content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="CAS-compatible content hash for Law D compliance",
    )

    @field_validator("timestamp", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def is_newer_than(self, other: DataVersion) -> bool:
        """Compare versions to determine if refresh is needed."""
        if self.strategy != other.strategy:
            return self.timestamp > other.timestamp

        if self.strategy == VersionStrategy.ETAG:
            return self.value != other.value
        if self.strategy == VersionStrategy.TIMESTAMP:
            return self.timestamp > other.timestamp
        if self.strategy == VersionStrategy.REVISION:
            try:
                return int(self.value) > int(other.value)
            except ValueError:
                return self.timestamp > other.timestamp
        if self.strategy == VersionStrategy.CONTENT_HASH:
            if self.value != other.value:
                return self.timestamp > other.timestamp
            return False

        return self.timestamp > other.timestamp


DataT = TypeVar("DataT")


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
    _query_key: str = field(init=False, repr=False, compare=False)
    _request_key: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "date_start", _coerce_datetime(self.date_start))
        object.__setattr__(self, "date_end", _coerce_datetime(self.date_end))
        object.__setattr__(self, "as_of", _coerce_datetime(self.as_of))
        object.__setattr__(self, "filters", _normalize_filters(self.filters))
        object.__setattr__(self, "_query_key", _hash_request_payload(self._query_payload()))
        object.__setattr__(self, "_request_key", _hash_request_payload(self._request_payload()))

    def _incremental_dump(self) -> dict[str, Any] | None:
        if self.incremental_since is None:
            return None
        return self.incremental_since.model_dump(mode="json")

    def _query_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "as_of": self.as_of,
            "filters": {key: list(values) for key, values in self.filters},
            "incremental_since": self._incremental_dump(),
            "min_quality_tier": self.min_quality_tier.value,
        }

    def _request_payload(self) -> dict[str, Any]:
        return {
            **self._query_payload(),
            "include_metadata": self.include_metadata,
            "include_schema": self.include_schema,
            "page_size": self.page_size,
            "page_token": self.page_token,
        }

    @property
    def query_key(self) -> str:
        """Hash identifying the logical data request (pagination excluded)."""
        return self._query_key

    @property
    def request_key(self) -> str:
        """Hash for the full request (includes pagination and output prefs)."""
        return self._request_key

    @property
    def cache_key(self) -> str:
        """CAS-compatible cache key for the full request."""
        return self.request_key

    def with_pagination(
        self,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> FetchRequest:
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

    def with_filter(self, field: str, *values: str) -> FetchRequest:
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


class PIIDetectedEntity(BaseModel):
    """Single redacted PII detection result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: str = Field(description="Detected entity type (Presidio/custom)")
    severity: str = Field(description="PII severity level")
    score: float = Field(ge=0.0, le=1.0)
    column: str = ""
    start: int = Field(ge=0, default=0)
    end: int = Field(ge=0, default=0)
    redacted_text: str = "***"


class PIIScanSummary(BaseModel):
    """Aggregated PII scan summary attached to connector fetch results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_records_scanned: int = Field(default=0, ge=0)
    total_entities_found: int = Field(default=0, ge=0)
    max_severity: str = "none"
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    entities_by_severity: dict[str, int] = Field(default_factory=dict)
    entities: list[PIIDetectedEntity] = Field(default_factory=list)
    scan_duration_ms: float = Field(default=0.0, ge=0.0)
    sampled: bool = False
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class FetchSchemaDescriptor(BaseModel):
    """Schema boundary for a fetch payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_id: str
    schema_version: str


class FetchProvenanceEnvelope(BaseModel):
    """Versioning and evidence metadata attached to a fetch payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: DataVersion
    fetched_at: datetime
    source_updated_at: datetime | None = None
    evidence_ref: EvidenceBundleRef | None = None


class FetchQualityEnvelope(BaseModel):
    """Quality assessment boundary for a fetch payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completeness: float
    quality_tier: QualityTier
    quality_flags: frozenset[str] = frozenset()


class FetchPaginationEnvelope(BaseModel):
    """Pagination boundary for chunked fetch operations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    has_more: bool = False
    next_page_token: str | None = None
    total_count: int | None = None


class FetchTransferEnvelope(BaseModel):
    """Transport/runtime metrics for one fetch invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fetch_duration_ms: float = 0.0
    bytes_transferred: int = 0
    not_modified: bool = False
    resilience: ResilienceInfo | None = None
    pii_scan: PIIScanSummary | None = None


class FetchResult[DataT](BaseModel):
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
    pii_scan: PIIScanSummary | None = Field(
        default=None,
        description="Optional PII scan summary produced during ingestion",
    )

    @field_validator("fetched_at", "source_updated_at", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
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

    @cached_property
    def schema(self) -> FetchSchemaDescriptor:
        """Structured schema boundary view for the fetched payload."""
        return FetchSchemaDescriptor(
            schema_id=self.schema_id,
            schema_version=self.schema_version,
        )

    @cached_property
    def provenance(self) -> FetchProvenanceEnvelope:
        """Structured provenance boundary view for the fetched payload."""
        return FetchProvenanceEnvelope(
            version=self.version,
            fetched_at=self.fetched_at,
            source_updated_at=self.source_updated_at,
            evidence_ref=self.evidence_ref,
        )

    @cached_property
    def quality(self) -> FetchQualityEnvelope:
        """Structured quality boundary view for the fetched payload."""
        return FetchQualityEnvelope(
            completeness=self.completeness,
            quality_tier=self.quality_tier,
            quality_flags=self.quality_flags,
        )

    @cached_property
    def pagination(self) -> FetchPaginationEnvelope:
        """Structured pagination boundary view for the fetched payload."""
        return FetchPaginationEnvelope(
            has_more=self.has_more,
            next_page_token=self.next_page_token,
            total_count=self.total_count,
        )

    @cached_property
    def transfer(self) -> FetchTransferEnvelope:
        """Structured transport/runtime boundary view for the fetched payload."""
        return FetchTransferEnvelope(
            fetch_duration_ms=self.fetch_duration_ms,
            bytes_transferred=self.bytes_transferred,
            not_modified=self.not_modified,
            resilience=self.resilience,
            pii_scan=self.pii_scan,
        )


class ConnectorIdentitySpec(BaseModel):
    """Stable connector identity tuple."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_id: str
    version: str
    namespace: str


class ConnectorSourceSpec(BaseModel):
    """Human-readable source provenance for a connector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: str
    source_organization: str
    source_url: str | None = None


class ConnectorGovernanceProfile(BaseModel):
    """Trust/quality/capability profile advertised by a connector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trust_level: TrustLevel
    quality_tier: QualityTier
    capabilities: int
    owner: str = "@fabric-owners"
    data_classification: str = "public"
    column_classification: dict[str, str] = Field(default_factory=dict)
    quality_contract_id: str | None = None


class ConnectorOperationalProfile(BaseModel):
    """Operational and freshness metadata for a connector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resilience_config: dict[str, Any] | None = None
    last_updated: datetime | None = None
    observed_latency_ms: float | None = None
    sla: ConnectorSLASpec | None = None


class ConnectorSchemaGovernanceSpec(BaseModel):
    """Schema metadata used by registry, inventory, and compatibility gates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_id: str | None = Field(
        default=None,
        description="Stable default schema id when the connector has a curated schema",
    )
    schema_id_template: str | None = Field(
        default=None,
        description="Stable schema id template for dataset-dependent schemas",
    )
    schema_registry_ref: str = Field(
        default="schemas/snapshots/fabric/connector_contract_registry.json",
        description="Repository artifact governing schema compatibility evidence",
    )


class ConnectorQualityGovernanceSpec(BaseModel):
    """Quality metadata used by Fabric validation and Scientist governance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quality_tier: QualityTier
    quality_contract_id: str | None = None
    quality_contract_ref: str | None = None
    finite_values_required: bool = True


class ConnectorSLASpec(BaseModel):
    """Connector-level SLO/SLA metadata for Phase 4 governance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    availability_target: float = Field(
        default=0.99,
        ge=0.0,
        le=1.0,
        description="Rolling fetch success target for the connector",
    )
    freshness_slo_seconds: int = Field(
        default=86_400,
        ge=0,
        description="Maximum expected age for decision-bearing data",
    )
    p95_latency_ms: float = Field(
        default=2_000.0,
        ge=0.0,
        description="Default p95 fetch latency target",
    )
    replay_success_target: float = Field(
        default=0.99,
        ge=0.0,
        le=1.0,
        description="Replay determinism target for recorded fixtures",
    )


class ConnectorDocumentationSpec(BaseModel):
    """Documentation boundary for connector discoverability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str
    documentation_url: str | None = None


class ConnectorMetadataSpec(BaseModel):
    """Define the immutable IR contract that registers one external data connector.

    The fabric layer reads this metadata before issuing fetch requests, while
    governance/reporting layers consume ``trust_level``, ``quality_tier``, and
    ``capabilities`` to decide whether a connector is eligible for a requested
    data view or evidence ingestion workflow.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity
    connector_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Unique identifier within namespace",
        examples=["wdi", "fred_api", "eurostat_sdmx"],
    )
    version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version of the connector",
        examples=["1.0.0", "2.1.3"],
    )
    namespace: str = Field(
        pattern=r"^[a-z][a-z0-9_.]*$",
        description="Organizational namespace for the connector",
        examples=["worldbank", "imf.sdmx", "gov.ua.stats"],
    )

    # Source metadata
    source_name: str = Field(
        min_length=1,
        max_length=256,
        description="Human-readable source name",
    )
    source_organization: str = Field(
        min_length=1,
        max_length=256,
        description="Organization providing the data",
    )
    source_url: str | None = Field(
        default=None,
        description="Primary URL for the data source",
    )

    # Trust and quality
    trust_level: TrustLevel = Field(
        default=TrustLevel.UNVERIFIED,
        description="Default trust level for data from this connector",
    )
    quality_tier: QualityTier = Field(
        default=QualityTier.UNVERIFIED,
        description="Default quality tier for data from this connector",
    )
    data_classification: str = Field(
        default="public",
        description="Governance classification propagated into cache/query layers",
    )
    column_classification: dict[str, str] = Field(
        default_factory=dict,
        description="Optional per-column governance classification mapping",
    )
    owner: str = Field(
        default="@fabric-owners",
        min_length=1,
        max_length=128,
        description="Owning team or handle for connector governance and incidents",
    )
    schema_id: str | None = Field(
        default=None,
        description="Stable default schema id for curated-schema connectors",
    )
    schema_id_template: str | None = Field(
        default=None,
        description="Stable schema id template for dataset-dependent connectors",
    )
    schema_registry_ref: str = Field(
        default="schemas/snapshots/fabric/connector_contract_registry.json",
        description="Schema-governance artifact for compatibility checks",
    )
    quality_contract_id: str | None = Field(
        default=None,
        description="Declarative quality contract identifier applied by default",
    )
    quality_contract_ref: str | None = Field(
        default=None,
        description="Optional repository path or URI for the declarative quality contract",
    )
    sla: ConnectorSLASpec = Field(
        default_factory=ConnectorSLASpec,
        description="Connector SLO/SLA defaults used by Fabric reliability policy",
    )

    # Capabilities
    capabilities: int = Field(
        default=0,
        ge=0,
        description="Bitmask of ConnectorCapability flags",
    )

    # Resilience configuration (optional, connector-level)
    resilience_config: dict[str, Any] | None = Field(
        default=None,
        description="Optional resilience configuration for connector fetch operations",
    )

    # Observability and freshness hints
    last_updated: datetime | None = Field(
        default=None,
        description="Timestamp of last known data update (UTC recommended)",
    )
    observed_latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Observed average latency in milliseconds",
    )

    # Documentation
    description: str = Field(
        default="",
        max_length=4096,
        description="Detailed description of the connector",
    )
    documentation_url: str | None = Field(
        default=None,
        description="URL to connector documentation",
    )

    @property
    def fully_qualified_id(self) -> str:
        """Get the fully qualified connector identifier."""
        return f"{self.namespace}.{self.connector_id}@{self.version}"

    @property
    def capability_flags(self) -> ConnectorCapability:
        """Get capabilities as a ConnectorCapability Flag."""
        return ConnectorCapability(self.capabilities)

    def has_capability(self, cap: ConnectorCapability) -> bool:
        """Check if connector has a specific capability."""
        return bool(self.capabilities & cap.value)

    @field_validator("last_updated", mode="after")
    @classmethod
    def _ensure_last_updated_tz(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @field_validator("data_classification", mode="after")
    @classmethod
    def _validate_data_classification(cls, value: str) -> str:
        normalized = str(value or "public").strip().lower()
        allowed = {
            "public",
            "internal",
            "confidential",
            "regulated_pii",
            "sensitive_policy_legal_signal",
        }
        if normalized not in allowed:
            raise ValueError(f"Unsupported data classification: {value}")
        return normalized

    @field_validator("column_classification", mode="after")
    @classmethod
    def _validate_column_classification(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {
            "public",
            "internal",
            "confidential",
            "regulated_pii",
            "sensitive_policy_legal_signal",
        }
        normalized: dict[str, str] = {}
        for column, classification in value.items():
            column_name = str(column).strip()
            if not column_name:
                raise ValueError("column classification names must be non-empty")
            token = str(classification or "public").strip().lower()
            if token not in allowed:
                raise ValueError(f"Unsupported column classification: {classification}")
            normalized[column_name] = token
        return normalized

    @field_validator("schema_id", "schema_id_template", mode="after")
    @classmethod
    def _validate_schema_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = str(value).strip()
        if not token:
            return None
        return token

    @field_validator("quality_contract_id", mode="after")
    @classmethod
    def _validate_quality_contract_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = str(value).strip()
        if not token:
            return None
        return token

    @model_validator(mode="after")
    def _fill_phase4_governance_defaults(self) -> ConnectorMetadataSpec:
        if self.schema_id is None and self.schema_id_template is None:
            object.__setattr__(
                self,
                "schema_id_template",
                f"{self.namespace}.{self.connector_id}.*",
            )
        if self.quality_contract_id is None:
            object.__setattr__(
                self,
                "quality_contract_id",
                f"fabric.quality.{self.namespace}.{self.connector_id}.default.v1",
            )
        return self

    def with_capabilities(self, *caps: ConnectorCapability) -> ConnectorMetadataSpec:
        """Create a new spec with additional capabilities."""
        new_caps = self.capabilities
        for cap in caps:
            new_caps |= cap.value
        return self.model_copy(update={"capabilities": new_caps})

    @cached_property
    def identity(self) -> ConnectorIdentitySpec:
        """Structured identity boundary for registry/discovery code."""
        return ConnectorIdentitySpec(
            connector_id=self.connector_id,
            version=self.version,
            namespace=self.namespace,
        )

    @cached_property
    def source(self) -> ConnectorSourceSpec:
        """Structured source boundary for provenance/discovery code."""
        return ConnectorSourceSpec(
            source_name=self.source_name,
            source_organization=self.source_organization,
            source_url=self.source_url,
        )

    @cached_property
    def governance(self) -> ConnectorGovernanceProfile:
        """Structured governance profile for admission and filtering."""
        return ConnectorGovernanceProfile(
            trust_level=self.trust_level,
            quality_tier=self.quality_tier,
            capabilities=self.capabilities,
            owner=self.owner,
            data_classification=self.data_classification,
            column_classification=self.column_classification,
            quality_contract_id=self.quality_contract_id,
        )

    @cached_property
    def operations(self) -> ConnectorOperationalProfile:
        """Structured operational profile for freshness/resilience logic."""
        return ConnectorOperationalProfile(
            resilience_config=self.resilience_config,
            last_updated=self.last_updated,
            observed_latency_ms=self.observed_latency_ms,
            sla=self.sla,
        )

    @cached_property
    def schema_governance(self) -> ConnectorSchemaGovernanceSpec:
        """Structured schema-governance profile for contracts and docs."""
        return ConnectorSchemaGovernanceSpec(
            schema_id=self.schema_id,
            schema_id_template=self.schema_id_template,
            schema_registry_ref=self.schema_registry_ref,
        )

    @cached_property
    def quality_governance(self) -> ConnectorQualityGovernanceSpec:
        """Structured quality-governance profile for validation and Scientist gates."""
        return ConnectorQualityGovernanceSpec(
            quality_tier=self.quality_tier,
            quality_contract_id=self.quality_contract_id,
            quality_contract_ref=self.quality_contract_ref,
        )

    @cached_property
    def documentation(self) -> ConnectorDocumentationSpec:
        """Structured documentation boundary for catalog UIs and tooling."""
        return ConnectorDocumentationSpec(
            description=self.description,
            documentation_url=self.documentation_url,
        )


type CapabilitySet = int | ConnectorCapability


def capabilities_from_flags(*flags: ConnectorCapability) -> int:
    """Convert ConnectorCapability flags to a bitmask integer."""
    result = 0
    for flag in flags:
        result |= flag.value
    return result


def flags_from_capabilities(bitmask: int) -> list[ConnectorCapability]:
    """Convert a bitmask integer to a list of ConnectorCapability flags."""
    result: list[ConnectorCapability] = []
    for cap in ConnectorCapability:
        if bitmask & cap.value:
            result.append(cap)
    return result


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
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


def _hash_request_payload(canonical_data: dict[str, Any]) -> str:
    canonical_bytes = to_canonical_bytes(canonical_data)
    return f"sha256:{content_hash(canonical_bytes)}"


FetchResult.model_rebuild()
