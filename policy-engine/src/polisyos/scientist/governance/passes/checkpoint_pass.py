"""Governance pass: validate calibration checkpoint evidence."""

from __future__ import annotations

from typing import Any, List

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class CheckpointPass(ValidatorPass):
    """Validate that checkpoint evidence exists for audit/replay.

    Calibration governance uses this pass as a lightweight audit hook:
    it only verifies that a checkpoint reference or explicit checkpoint
    payload exists when the run declares checkpoint evidence mandatory.
    Legacy ``checkpoints`` payloads are still accepted for compatibility
    with reproducibility judge inputs.
    """

    @property
    def pass_id(self) -> str:
        return "checkpoint"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        state = ctx.state
        checkpoint_required = _checkpoint_required(state)
        checkpoint_evidence = _has_checkpoint_evidence(state)

        checkpoints = state.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            checkpoints = []

        if not checkpoint_evidence:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "last_checkpoint_ref"],
                    message="Missing checkpoint evidence for this run.",
                    severity=(
                        IssueSeverity.BLOCKER if checkpoint_required else IssueSeverity.WARNING
                    ),
                    code="CHECKPOINT_MISSING",
                    suggestion=(
                        "Attach last_checkpoint_ref or calibration checkpoint payload "
                        "before governance evaluation."
                    ),
                )
            )

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


def _checkpoint_required(state: dict[str, Any]) -> bool:
    if bool(state.get("checkpoint_required")):
        return True
    policy = str(state.get("checkpoint_policy") or "").strip().lower()
    return policy in {"strict", "required"}


def _has_checkpoint_evidence(state: dict[str, Any]) -> bool:
    for key in (
        "last_checkpoint_ref",
        "checkpoint_ref",
        "calibration_checkpoint",
        "calibration_checkpoint_payload",
    ):
        if state.get(key) is not None:
            return True
    checkpoints = state.get("checkpoints")
    return isinstance(checkpoints, list) and len(checkpoints) > 0
