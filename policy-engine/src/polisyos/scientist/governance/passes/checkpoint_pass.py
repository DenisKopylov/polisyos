"""Governance pass: validate execution checkpoints are present and complete."""

from __future__ import annotations

from typing import Any, List

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class CheckpointPass(ValidatorPass):
    """Validate that required execution checkpoints have been recorded.

    Checks that the workflow has produced checkpoint events at critical
    stages (data loading, estimation, inference) so the run can be
    audited and reproduced.
    """

    @property
    def pass_id(self) -> str:
        return "checkpoint_integrity"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        state = ctx.state

        checkpoints = state.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            checkpoints = []

        required_stages = {"data_loaded", "estimation_complete"}
        recorded_stages = {
            cp.get("stage") for cp in checkpoints if isinstance(cp, dict) and cp.get("stage")
        }

        missing = required_stages - recorded_stages
        if missing:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "checkpoints"],
                    message=f"Missing required checkpoints: {sorted(missing)}",
                    severity=IssueSeverity.WARNING,
                    code="CHECKPOINT_MISSING",
                    suggestion="Ensure all workflow stages emit checkpoint events",
                )
            )

        # Verify checkpoint ordering
        timestamps = [
            cp.get("timestamp", "")
            for cp in checkpoints
            if isinstance(cp, dict)
        ]
        if timestamps and timestamps != sorted(timestamps):
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "checkpoints"],
                    message="Checkpoint timestamps are not monotonically ordered",
                    severity=IssueSeverity.INFO,
                    code="CHECKPOINT_ORDER",
                    suggestion="Review checkpoint emission order in workflow",
                )
            )

        return issues
