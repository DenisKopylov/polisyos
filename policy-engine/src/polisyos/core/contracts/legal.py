"""
Legal compliance contracts for Policy OS.

Exports stable types for the legal validation subsystem.
Use these imports in consuming modules to avoid coupling
to internal implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Protocol, runtime_checkable

from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType


class IssueSeverity(Enum):
    """Severity levels for compliance issues."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


@dataclass(frozen=True)
class ComplianceIssue:
    """
    Immutable compliance issue from a validation pass.

    Attributes:
        pass_id: Identifier of the pass that raised this issue
        path: JSON path to the problematic field
        message: Human-readable description of the issue
        severity: Issue severity level
        code: Machine-readable error code
        suggestion: Optional fix suggestion
        input_value: The actual value that caused the issue
    """

    pass_id: str
    path: List[str | int]
    message: str
    severity: IssueSeverity
    code: Optional[str] = None
    suggestion: Optional[str] = None
    input_value: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with GovernorFeedback."""
        return {
            "loc": self.path,
            "message": self.message,
            "error_type": self.pass_id,
            "input_value": self.input_value,
            "severity": self.severity.value,
            "code": self.code,
            "suggestion": self.suggestion,
        }


@runtime_checkable
class RuleBackend(Protocol):
    """
    Protocol for legal rule evaluation backends.

    Implementations MUST:
    - Return ComplianceIssue objects (not custom types)
    - Set pass_id="legal" on all issues
    - Handle None/empty NormPack gracefully
    - Be stateless (no side effects between calls)
    """

    @property
    def backend_id(self) -> str:
        """Unique identifier for this backend."""
        ...

    def evaluate(
        self,
        norm_pack: "NormPack",
        context: dict,
    ) -> List[ComplianceIssue]:
        """
        Evaluate norms against context.

        Args:
            norm_pack: Collection of norms to evaluate
            context: State dictionary containing policy/IR data

        Returns:
            List of ComplianceIssue objects for any violations/info
        """
        ...


__all__ = [
    "NormPack",
    "NormRule",
    "NormRef",
    "RuleType",
    "RuleBackend",
    "ComplianceIssue",
    "IssueSeverity",
]
