"""QueryValidationReport IR — structured schema for causal query validation results.

Used by Track F (CausalQueryValidator) and any pre-flight checks that verify
a causal query is well-formed before identification and estimation begin.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValidationSeverity(str, Enum):
    """Severity level of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """Base class for a single validation issue (error or warning).

    Not instantiated directly — use ValidationError or ValidationWarning.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    """Machine-readable issue code (e.g. 'GRAPH_CYCLE', 'MISSING_TREATMENT', 'S_NODE_DANGLING')."""

    message: str
    """Human-readable description of the issue."""

    severity: ValidationSeverity
    """Severity level of this issue."""

    context: dict[str, Any] = {}
    """Optional structured context (variable names, node ids, etc.)."""


class ValidationError(ValidationIssue):
    """A fatal validation error that makes the query non-executable."""

    severity: ValidationSeverity = ValidationSeverity.ERROR


class ValidationWarning(ValidationIssue):
    """A non-fatal validation warning — query can proceed but may give unreliable results."""

    severity: ValidationSeverity = ValidationSeverity.WARNING


class QueryValidationReport(BaseModel):
    """Schema for the result of validating a causal query against a graph and knowledge base.

    Produced by CausalQueryValidator (Track F). Consumed by the causal engine
    pre-flight check and the scientist agent before scheduling estimation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool
    """True if there are no errors (warnings are allowed)."""

    errors: tuple[ValidationError, ...] = ()
    """Fatal errors — if non-empty, is_valid must be False."""

    warnings: tuple[ValidationWarning, ...] = ()
    """Non-fatal warnings."""

    query_str: str = ""
    """The causal query string that was validated."""

    checked_at: str = ""
    """ISO 8601 timestamp when the validation was performed."""

    def has_errors(self) -> bool:
        """Return True if there are any fatal errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Return True if there are any warnings."""
        return len(self.warnings) > 0

    def to_summary(self) -> str:
        """Return a concise human-readable summary."""
        status = "VALID" if self.is_valid else "INVALID"
        parts = [f"QueryValidation[{status}]"]
        if self.errors:
            parts.append(f"{len(self.errors)} error(s): " + "; ".join(e.code for e in self.errors))
        if self.warnings:
            parts.append(
                f"{len(self.warnings)} warning(s): " + "; ".join(w.code for w in self.warnings)
            )
        return " | ".join(parts)


__all__ = [
    "QueryValidationReport",
    "ValidationError",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationWarning",
]
