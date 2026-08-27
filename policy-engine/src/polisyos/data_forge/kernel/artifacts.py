"""Governed artifact references for Data Forge publication boundaries."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, TypeVar

from pydantic import Field, field_validator

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import from_canonical_bytes
from polisyos.data_forge.errors import LexValidationError
from polisyos.fabric.world import validate_doc_meta_ids
from polisyos.ir.world.doc import DocMeta

from ._base import DataForgeModel

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

_E = TypeVar("_E", bound=Exception)

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


def load_json_artifact[E: Exception](
    cas: FileSystemCAS,
    artifact_id: str,
    *,
    error_cls: type[_E] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
) -> dict:
    """Load a JSON-object artifact with caller-selected error semantics."""
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
    except Exception as exc:
        if not wrap_read_errors:
            raise
        prefix = read_error_prefix or f"failed to read {payload_label}"
        raise error_cls(f"{prefix} {artifact_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise error_cls(f"{payload_label} {artifact_id} payload must be a JSON object")
    return payload


def load_doc_meta_artifact[E: Exception](
    cas: FileSystemCAS,
    artifact_id: str,
    *,
    error_cls: type[_E] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
    validate_ids: bool = False,
) -> DocMeta:
    """Load a document metadata artifact with optional identity validation."""
    payload = load_json_artifact(
        cas,
        artifact_id,
        error_cls=error_cls,
        payload_label=payload_label,
        wrap_read_errors=wrap_read_errors,
        read_error_prefix=read_error_prefix,
    )
    meta = DocMeta.model_validate(payload)
    if validate_ids:
        validate_doc_meta_ids(meta)
    return meta


__all__ = [
    "ArtifactRef",
    "PIILevel",
    "ProducerVersion",
    "RetentionClass",
    "load_doc_meta_artifact",
    "load_json_artifact",
]
