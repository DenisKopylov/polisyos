from __future__ import annotations

from typing import List, TYPE_CHECKING

from polisyos.scientist.governance.passes.base import (
    ComplianceIssue,
    PassContext,
    ValidatorPass,
)
from polisyos.scientist.governance.profiles import ProfileLevel
from polisyos.scientist.governance.legal.backends.stub import StubBackend

if TYPE_CHECKING:
    from polisyos.ir.norm_pack import NormPack
    from polisyos.scientist.governance.legal.backends.base import RuleBackend


class LegalPass(ValidatorPass):
    """
    Validates policy against legal norms.

    Default behavior: Only runs in STRICT profile.
    Can be force-enabled via constructor for testing.

    Delegates actual rule evaluation to injected RuleBackend.
    """

    def __init__(
        self,
        backend: "RuleBackend | None" = None,
        enabled: bool = False,
    ):
        """
        Args:
            backend: Rule evaluation backend (defaults to StubBackend)
            enabled: Force enable regardless of profile
        """
        self._backend = backend or StubBackend()
        self._enabled = enabled

    @property
    def pass_id(self) -> str:
        return "legal"

    @property
    def estimated_cost_ms(self) -> int:
        return 100

    @property
    def requires_data(self) -> bool:
        return True

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        if not self._enabled and ctx.profile.level != ProfileLevel.STRICT:
            return []

        norm_pack = self._resolve_norms(ctx)
        if norm_pack is None:
            return []

        backend_issues = self._backend.evaluate(norm_pack, ctx.state)

        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=issue.path,
                message=issue.message,
                severity=issue.severity,
                code=issue.code,
                suggestion=issue.suggestion,
                input_value=issue.input_value,
            )
            for issue in backend_issues
        ]

    def _resolve_norms(self, ctx: PassContext) -> "NormPack | None":
        """
        Resolve applicable NormPack from context.

        Phase 10: Simple state lookup
        Phase 18+: Will resolve from NormCorpus based on jurisdiction
        """
        return ctx.state.get("norm_pack")


__all__ = ["LegalPass"]
