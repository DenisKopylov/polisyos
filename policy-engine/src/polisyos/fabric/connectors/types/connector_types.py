"""Connector types, errors, and supporting data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.connectors import ConnectorCapability

# ============================================================================
# Exception Hierarchy
# ============================================================================


class ConnectorError(Exception):
    """Base exception for all connector-related errors."""

    def __init__(
        self,
        message: str,
        connector_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.connector_id = connector_id
        self.message = message
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.connector_id:
            return f"[{self.connector_id}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert error to a dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "connector_id": self.connector_id,
            "message": self.message,
            "details": self.details,
        }


class CapabilityError(ConnectorError):
    """Raised when a connector lacks required capability."""

    def __init__(
        self,
        connector_id: str,
        required: ConnectorCapability,
        available: ConnectorCapability | None = None,
        message: str | None = None,
    ) -> None:
        self.required = required
        self.available = available

        resolved_message = message or f"Missing required capability: {required.name}"
        if message is None and available is not None:
            resolved_message += f" (available: {available})"

        super().__init__(
            message=resolved_message,
            connector_id=connector_id,
            details={
                "required_capability": required.name,
                "required_value": required.value,
                "available_capabilities": str(available) if available else None,
            },
        )


class ConfigurationError(ConnectorError):
    """Raised when connector configuration is invalid."""

    def __init__(
        self,
        message: str,
        connector_id: str | None = None,
        field: str | None = None,
        value: Any = None,
        expected: str | None = None,
    ) -> None:
        self.field = field
        self.value = value
        self.expected = expected

        details: dict[str, Any] = {}
        if field:
            details["field"] = field
        if value is not None:
            if isinstance(value, str) and len(value) > 4:
                details["value"] = f"{value[:2]}...{value[-2:]}"
            else:
                details["value"] = str(value)
        if expected:
            details["expected"] = expected

        super().__init__(message=message, connector_id=connector_id, details=details)


class ConnectionError(ConnectorError):
    """Raised when connection to data source fails."""

    def __init__(
        self,
        message: str,
        connector_id: str | None = None,
        url: str | None = None,
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.retry_after = retry_after

        details: dict[str, Any] = {}
        if url:
            details["url"] = url
        if status_code is not None:
            details["status_code"] = status_code
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after

        super().__init__(message=message, connector_id=connector_id, details=details)


class RateLimitError(ConnectionError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        connector_id: str,
        retry_after: int | None = None,
        limit_remaining: int = 0,
        limit_total: int | None = None,
    ) -> None:
        self.limit_remaining = limit_remaining
        self.limit_total = limit_total

        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"

        super().__init__(
            message=message,
            connector_id=connector_id,
            retry_after=retry_after,
        )
        self.details["limit_remaining"] = limit_remaining
        if limit_total is not None:
            self.details["limit_total"] = limit_total


class FetchError(ConnectorError):
    """Raised when data fetch operation fails."""

    def __init__(
        self,
        message: str,
        connector_id: str | None = None,
        dataset_id: str | None = None,
        request_params: dict[str, Any] | None = None,
    ) -> None:
        self.dataset_id = dataset_id
        self.request_params = request_params

        details: dict[str, Any] = {}
        if dataset_id:
            details["dataset_id"] = dataset_id
        if request_params:
            safe_params: dict[str, Any] = {}
            for key, value in request_params.items():
                if any(
                    tok in key.lower() for tok in ("auth", "key", "token", "secret", "password")
                ):
                    continue
                safe_params[key] = value
            details["request_params"] = safe_params

        super().__init__(message=message, connector_id=connector_id, details=details)


class SchemaError(ConnectorError):
    """Raised when schema validation or introspection fails."""

    def __init__(
        self,
        message: str,
        connector_id: str | None = None,
        schema_id: str | None = None,
        expected_version: str | None = None,
        actual_version: str | None = None,
    ) -> None:
        self.schema_id = schema_id
        self.expected_version = expected_version
        self.actual_version = actual_version

        details: dict[str, Any] = {}
        if schema_id:
            details["schema_id"] = schema_id
        if expected_version:
            details["expected_version"] = expected_version
        if actual_version:
            details["actual_version"] = actual_version

        super().__init__(message=message, connector_id=connector_id, details=details)


# ============================================================================
# Supporting Data Structures
# ============================================================================


DataT = TypeVar("DataT")


class FreshnessStatus(str, Enum):
    """Status of cached data freshness check."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    """Result of a freshness check operation."""

    status: FreshnessStatus
    message: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_updated_at: datetime | None = None

    new_version_available: bool = False
    new_version_hint: str | None = None

    @property
    def needs_refresh(self) -> bool:
        return self.status == FreshnessStatus.STALE


@dataclass(frozen=True, slots=True)
class DatasetDescriptor:
    """Description of an available dataset from catalog browsing."""

    dataset_id: str
    name: str
    description: str = ""

    # Temporal coverage
    date_start: datetime | None = None
    date_end: datetime | None = None
    update_frequency: str | None = None

    # Size hints
    estimated_rows: int | None = None
    estimated_bytes: int | None = None

    # Schema reference
    schema_id: str | None = None

    # Planner hints
    supports_filters: tuple[str, ...] = ()
    filter_schema: dict[str, Any] = field(default_factory=dict)
    latency_class: str | None = None
    rate_limit_class: str | None = None

    # Additional metadata
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DataChunk(Generic[DataT]):
    """A chunk of data from streaming fetch."""

    data: DataT
    chunk_index: int
    row_count: int
    bytes_size: int = 0

    is_first: bool = False
    is_last: bool = False
    total_chunks: int | None = None

    resume_token: str | None = None


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation issue from configuration checking."""

    severity: ValidationSeverity
    message: str
    field: str | None = None
    code: str | None = None
    suggestion: str | None = None


class ValidationResult(BaseModel):
    """Result of configuration validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool = Field(description="True if configuration passes all required checks")
    issues: tuple[ValidationIssue, ...] = Field(
        default=(),
        description="List of validation issues found",
    )

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(valid=True, issues=())

    @classmethod
    def failure(cls, *issues: ValidationIssue) -> ValidationResult:
        return cls(valid=False, issues=tuple(issues))

    def with_issue(self, issue: ValidationIssue) -> ValidationResult:
        new_issues = (*self.issues, issue)
        new_valid = self.valid and issue.severity != ValidationSeverity.ERROR
        return ValidationResult(valid=new_valid, issues=new_issues)


# ============================================================================
# Rate Limit Tracking
# ============================================================================


@dataclass(frozen=True, slots=True)
class RateLimitStatus:
    """Current rate limit status for a connector."""

    requests_remaining: int
    requests_limit: int
    reset_at: datetime | None = None

    endpoint_limits: dict[str, int] = field(default_factory=dict)

    @property
    def utilization(self) -> float:
        if self.requests_limit == 0:
            return 1.0
        return 1.0 - (self.requests_remaining / self.requests_limit)

    @property
    def is_exhausted(self) -> bool:
        return self.requests_remaining <= 0

    @property
    def seconds_until_reset(self) -> int | None:
        if self.reset_at is None:
            return None
        reset_at = self.reset_at
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=UTC)
        delta = reset_at - datetime.now(UTC)
        return max(0, int(delta.total_seconds()))
