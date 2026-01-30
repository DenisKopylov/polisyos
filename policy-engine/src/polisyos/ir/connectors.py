"""Canonical connector contracts for the data fabric layer.

These contracts define the interface boundary between external data sources and
PolicyOS fabric connectors. All connectors must produce artifacts conforming to
these contracts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, Flag, IntEnum, auto
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectorCapability(Flag):
    """Declarative capabilities that connectors can advertise."""

    # Data access patterns
    CATALOG_BROWSE = auto()      # Can list available datasets
    FULL_FETCH = auto()          # Can fetch entire dataset
    INCREMENTAL_FETCH = auto()   # Can fetch only changes since timestamp
    STREAMING = auto()           # Supports streaming large datasets

    # Filtering capabilities (server-side pushdown)
    DATE_RANGE_FILTER = auto()   # Server-side date filtering
    DIMENSION_FILTER = auto()    # Server-side dimension filtering
    CUSTOM_QUERY = auto()        # Supports query language (SQL, GraphQL, SDMX)

    # Metadata capabilities
    SCHEMA_INTROSPECTION = auto()  # Can describe data schema
    FRESHNESS_CHECK = auto()       # Can check staleness without full fetch
    PROVENANCE_METADATA = auto()   # Provides source/methodology info

    # Quality capabilities
    REVISION_HISTORY = auto()    # Provides historical revisions
    CONFIDENCE_INTERVALS = auto() # Provides uncertainty bounds

    # Operational capabilities
    RATE_LIMIT_AWARE = auto()    # Reports rate limit status
    RESUMABLE = auto()           # Supports resuming interrupted fetches


class VersionStrategy(str, Enum):
    """Versioning strategies for cached data."""

    ETAG = "etag"
    TIMESTAMP = "timestamp"
    REVISION = "revision"
    CONTENT_HASH = "content_hash"


class TrustLevel(IntEnum):
    """Trust levels for data sources."""

    UNVERIFIED = 0   # Unknown source, requires manual validation
    LOW = 1          # User-provided, no institutional backing
    MEDIUM = 2       # Known organization, standard quality
    HIGH = 3         # Authoritative source (central bank, NSO)
    AUTHORITATIVE = 4  # Official government/regulatory source


class QualityTier(IntEnum):
    """Data quality classification aligned with existing QualityIndicators."""

    UNVERIFIED = 0
    BRONZE = 1       # Raw data, minimal validation
    SILVER = 2       # Cleaned, schema-validated
    GOLD = 3         # Reconciled, cross-validated
    PLATINUM = 4     # Production-ready, full evidence chain


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
            return value.replace(tzinfo=timezone.utc)
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


class ConnectorMetadataSpec(BaseModel):
    """Immutable connector metadata specification (IR-level contract)."""

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

    # Capabilities
    capabilities: int = Field(
        default=0,
        ge=0,
        description="Bitmask of ConnectorCapability flags",
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

    def with_capabilities(self, *caps: ConnectorCapability) -> ConnectorMetadataSpec:
        """Create a new spec with additional capabilities."""
        new_caps = self.capabilities
        for cap in caps:
            new_caps |= cap.value
        return self.model_copy(update={"capabilities": new_caps})


CapabilitySet: TypeAlias = int | ConnectorCapability


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
