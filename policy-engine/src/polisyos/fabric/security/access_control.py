"""Fabric data-governance primitives for classification, row policies, and access audit."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel


class DataClassification(str, Enum):
    """Fabric-wide data classification taxonomy."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    REGULATED_PII = "regulated_pii"
    SENSITIVE_POLICY_LEGAL_SIGNAL = "sensitive_policy_legal_signal"


_CLASSIFICATION_CEILING: dict[DataClassification, PIIAccessLevel] = {
    DataClassification.PUBLIC: PIIAccessLevel.NONE,
    DataClassification.INTERNAL: PIIAccessLevel.LOW,
    DataClassification.CONFIDENTIAL: PIIAccessLevel.MEDIUM,
    DataClassification.REGULATED_PII: PIIAccessLevel.CRITICAL,
    DataClassification.SENSITIVE_POLICY_LEGAL_SIGNAL: PIIAccessLevel.HIGH,
}

_PII_LEVEL_ORDER: tuple[PIIAccessLevel, ...] = (
    PIIAccessLevel.NONE,
    PIIAccessLevel.LOW,
    PIIAccessLevel.MEDIUM,
    PIIAccessLevel.HIGH,
    PIIAccessLevel.CRITICAL,
)


def normalize_classification(
    value: DataClassification | str | None,
    *,
    default: DataClassification = DataClassification.PUBLIC,
) -> DataClassification:
    """Normalize a classification token into the Fabric enum."""

    if value is None:
        return default
    if isinstance(value, DataClassification):
        return value
    token = str(value).strip().lower()
    if not token:
        return default
    return DataClassification(token)


def classification_allowed(
    scope: AccessScope | None,
    classification: DataClassification | str | None,
    *,
    purpose_of_use: str = "",
) -> tuple[bool, str]:
    """Return whether a scope may access one classification tier."""

    resolved = normalize_classification(classification)
    if scope is None:
        return (resolved == DataClassification.PUBLIC, "missing_access_scope")

    required = _CLASSIFICATION_CEILING[resolved]
    if _PII_LEVEL_ORDER.index(scope.max_pii_tier) < _PII_LEVEL_ORDER.index(required):
        return (False, f"classification {resolved.value} exceeds scope ceiling")

    if (
        resolved in {DataClassification.CONFIDENTIAL, DataClassification.REGULATED_PII}
        and not purpose_of_use.strip()
    ):
        return (False, "purpose_of_use is required for confidential or regulated access")
    return (True, "")


@dataclass(frozen=True, slots=True)
class RowAccessPolicy:
    """Mandatory row filters injected by governance."""

    tenant_id: str | None = None
    enforced_filters: Mapping[str, Any] = field(default_factory=dict)

    def normalized_filters(self, *, tenant_column: str | None = None) -> dict[str, Any]:
        merged = {str(key): value for key, value in self.enforced_filters.items()}
        if self.tenant_id is not None and tenant_column:
            merged.setdefault(tenant_column, self.tenant_id)
        return merged


class AccessAuditEvent(BaseModel):
    """One Fabric access-control decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor: str = ""
    tenant: str = ""
    table: str
    query: str = ""
    columns: tuple[str, ...] = Field(default=())
    classification: DataClassification = DataClassification.PUBLIC
    decision: str
    denied_reason: str = ""
    masking: tuple[str, ...] = Field(default=())
    cardinality_bucket: str = "0"
    purpose_of_use: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("created_at", mode="after")
    @classmethod
    def _ensure_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class JsonlAccessAuditLog:
    """Small JSONL audit sink for world-query access decisions."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: AccessAuditEvent) -> None:
        line = json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n"
        with self._lock, open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line)


def current_trace_id() -> str:
    """Best-effort trace identifier for access audit correlation."""

    try:
        from opentelemetry import trace as otel_trace

        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        pass
    return ""


def cardinality_bucket(row_count: int) -> str:
    """Bucket row counts into low-cardinality audit labels."""

    if row_count <= 0:
        return "0"
    if row_count <= 10:
        return "1_10"
    if row_count <= 100:
        return "11_100"
    if row_count <= 1_000:
        return "101_1000"
    return "1001_plus"


__all__ = [
    "AccessAuditEvent",
    "DataClassification",
    "JsonlAccessAuditLog",
    "RowAccessPolicy",
    "cardinality_bucket",
    "classification_allowed",
    "current_trace_id",
    "normalize_classification",
]
