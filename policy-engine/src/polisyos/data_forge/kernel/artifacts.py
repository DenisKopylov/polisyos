"""Governed artifact references for Data Forge publication boundaries."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator

from ._base import DataForgeModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
TRACE_ID_PATTERN = r"^[0-9a-f]{32}$"
SPAN_ID_PATTERN = r"^[0-9a-f]{16}$"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"


class PIILevel(str, Enum):
    """PII classification carried by a published artifact."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RetentionClass(str, Enum):
    """Storage lifecycle class for a published artifact."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    EPHEMERAL = "ephemeral"


class ProducerVersion(DataForgeModel):
    """Version tuple identifying the code/model/config that produced an artifact."""

    code_version: str = Field(min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    lockfile_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)


class ArtifactRef(DataForgeModel):
    """Stable reference to an artifact published by a Data Forge asset."""

    uri: str = Field(pattern=r"^polisyos://[a-z0-9_.-]+/[a-z0-9_./-]+@[a-z0-9_.:-]+$")
    sha256: str = Field(pattern=SHA256_PATTERN)
    producer: str = Field(min_length=1)
    producer_version: ProducerVersion
    trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    span_id: str = Field(pattern=SPAN_ID_PATTERN)
    config_hash: str = Field(pattern=SHA256_PATTERN)
    owner: str = Field(min_length=1)
    license: str = Field(min_length=1)
    regeneration_command: str = Field(min_length=1)
    pii_level: PIILevel
    retention_class: RetentionClass
    freshness_sla_seconds: int = Field(ge=0)
    schema_id: str = Field(min_length=1)
    schema_version: str = Field(pattern=SCHEMA_VERSION_PATTERN)
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def _uri_must_have_snapshot(cls, value: str) -> str:
        if value.endswith("@"):
            raise ValueError("artifact uri must include a snapshot id after '@'")
        return value

    @property
    def snapshot_id(self) -> str:
        """Return the snapshot id embedded in the logical artifact URI."""
        return self.uri.rsplit("@", 1)[1]


__all__ = [
    "ArtifactRef",
    "PIILevel",
    "ProducerVersion",
    "RetentionClass",
]
