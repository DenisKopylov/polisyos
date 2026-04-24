"""Public backends stub module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity

if TYPE_CHECKING:
    from polisyos.ir.norm_pack import NormPack


class StubBackend:
    """
    Stub backend that returns NOT_IMPLEMENTED for all norms.

    Use case: Validates LegalPass integration without rule engine.
    All norms produce INFO-level issues indicating pending implementation.
    """

    @property
    def backend_id(self) -> str:
        return "stub"

    def evaluate(
        self,
        norm_pack: NormPack | None,
        context: dict[str, Any],
    ) -> list[ComplianceIssue]:
        """Always returns INFO-level 'not implemented' issues."""
        if norm_pack is None:
            return []

        return [
            ComplianceIssue(
                pass_id="legal",
                path=["norm_pack", norm.norm_id],
                message=(
                    f"Norm '{norm.norm_id}' evaluation not implemented "
                    f"(type: {norm.rule_type.value})"
                ),
                severity=IssueSeverity.INFO,
                code="NORM_NOT_IMPLEMENTED",
                suggestion=(
                    f"Implement {norm.rule_type.value} evaluator or use AST backend (Phase 18)"
                ),
            )
            for norm in norm_pack.norms
        ]


__all__ = ["StubBackend"]
