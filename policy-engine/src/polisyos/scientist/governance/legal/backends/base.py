from __future__ import annotations

from typing import List, Protocol, TYPE_CHECKING, runtime_checkable

from polisyos.scientist.governance.passes.base import ComplianceIssue

if TYPE_CHECKING:
    from polisyos.ir.norm_pack import NormPack


@runtime_checkable
class RuleBackend(Protocol):
    """
    Protocol for legal rule evaluation backends.

    Implementations MUST:
    - Return ComplianceIssue objects (not custom types)
    - Set pass_id="legal" on all issues
    - Handle None/empty NormPack gracefully
    - Be stateless (no side effects between calls)

    Future backends (Phase 18+):
    - ASTBackend: Evaluates condition_expr using safe AST interpreter
    - LLMBackend: Uses Claude for complex textual rule interpretation
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


__all__ = ["RuleBackend"]
