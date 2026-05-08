"""Example pass exposed through `polisyos.scientist_governance_passes`."""

from __future__ import annotations

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)


class ExampleAuditMarkerPass(ValidatorPass):
    """Tiny deterministic governance pass for extension authors."""

    @property
    def pass_id(self) -> str:
        return "example_audit_marker"

    @property
    def estimated_cost_ms(self) -> int:
        return 1

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.state.get("example_governance_approved") is True:
            return []
        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["state", "example_governance_approved"],
                message="Example governance approval marker is missing.",
                severity=IssueSeverity.WARNING,
                code="example.audit_marker.missing_approval",
                suggestion="Set state.example_governance_approved=true in the smoke fixture.",
            )
        ]


def audit_marker_pass_factory() -> ExampleAuditMarkerPass:
    """Return a fresh validator instance for entry-point loading."""
    return ExampleAuditMarkerPass()


__all__ = ["ExampleAuditMarkerPass", "audit_marker_pass_factory"]
