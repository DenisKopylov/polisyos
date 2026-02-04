from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.governance.profiles import ValidationProfile

from polisyos.core.contracts.legal import ComplianceIssue, IssueSeverity


@dataclass
class PassContext:
    """
    Context passed to each validation pass.

    Provides access to the IR, experiment state, registry bundle,
    validation profile, and run identification.
    """

    ir: Optional["TrinityBundle"]
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
