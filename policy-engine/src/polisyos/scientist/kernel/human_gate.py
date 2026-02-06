from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.gate import (
    GateContext,
    GateDecision as IRGateDecision,
    GatePriority,
    GateRequest as IRGateRequest,
    GateVerdict,
)

warnings.warn(
    "polisyos.scientist.kernel.human_gate is deprecated; use polisyos.ir.gate instead.",
    DeprecationWarning,
    stacklevel=2,
)


class GateRequest(BaseModel):
    """Legacy gate request model kept for compatibility."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    reason: str
    details: dict[str, Any] | None = None

    def to_ir_request(self, *, context: GateContext) -> IRGateRequest:
        return IRGateRequest(
            request_id="legacy",
            run_id=self.run_id,
            reason=self.reason,
            context=context,
            priority=GatePriority.NORMAL,
            requested_by="legacy",
        )


class GateDecision(BaseModel):
    """Legacy gate decision model kept for compatibility."""

    model_config = ConfigDict(extra="forbid")

    approved: bool
    actor: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    notes: str | None = None

    def to_ir_decision(self, *, request_id: str, run_id: str) -> IRGateDecision:
        verdict = GateVerdict.APPROVE if self.approved else GateVerdict.REJECT
        return IRGateDecision(
            request_id=request_id,
            run_id=run_id,
            verdict=verdict,
            approver_id=self.actor or "legacy",
            reason_codes=self.reason_codes,
            comment=self.notes,
        )


__all__ = [
    "GateContext",
    "GatePriority",
    "GateRequest",
    "GateDecision",
    "GateVerdict",
    "IRGateRequest",
    "IRGateDecision",
]

