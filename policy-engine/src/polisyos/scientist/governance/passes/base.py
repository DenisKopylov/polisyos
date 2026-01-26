from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.ir.surface import PolicySurfaceIR
    from polisyos.scientist.governance.profiles import ValidationProfile


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


@dataclass
class PassContext:
    """
    Context passed to each validation pass.

    Provides access to the IR, experiment state, registry bundle,
    validation profile, and run identification.
    """

    ir: Optional["PolicySurfaceIR"]
    state: dict
    registry_bundle: Optional[object]
    profile: "ValidationProfile"
    run_id: str

    def get_budget(self, key: str, default: float = 0.0) -> float:
        """Retrieve a budget value from state."""
        budget = self.state.get("budget") or {}
        return float(budget.get(key, default))

    def get_usage(self, key: str, default: float = 0.0) -> float:
        """Retrieve current usage value from state."""
        usage = self.state.get("budget_usage") or {}
        return float(usage.get(key, default))


class ValidatorPass(ABC):
    """
    Abstract base class for validation passes.

    Follows the pattern established in fabric/udf/passes/ but adapted
    for governance validation with severity-based issue reporting.
    """

    @property
    @abstractmethod
    def pass_id(self) -> str:
        """Unique identifier for this pass (e.g., 'schema', 'safety')."""
        raise NotImplementedError

    @property
    def estimated_cost_ms(self) -> int:
        """Estimated execution time in milliseconds. Override for expensive passes."""
        return 10

    @property
    def requires_data(self) -> bool:
        """Whether this pass requires external data access (registry, UDF)."""
        return False

    @abstractmethod
    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        """
        Execute validation and return discovered issues.

        Args:
            ctx: PassContext with IR, state, and profile information

        Returns:
            List of ComplianceIssue objects (empty if validation passes)
        """
        raise NotImplementedError
