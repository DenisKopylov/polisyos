from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set


class Phase(str, Enum):
    INTAKE = "INTAKE"
    FRAME = "FRAME"
    PREFLIGHT_GOV = "PREFLIGHT_GOV"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    POSTFLIGHT_GOV = "POSTFLIGHT_GOV"
    DECIDE = "DECIDE"
    PUBLISH = "PUBLISH"
    ARCHIVE = "ARCHIVE"


ALLOWED_TRANSITIONS: Dict[Phase, Set[Phase]] = {
    Phase.INTAKE: {Phase.FRAME},
    # FRAME can short-circuit to DECIDE when the policy is rejected/pruned early.
    Phase.FRAME: {Phase.FRAME, Phase.PREFLIGHT_GOV, Phase.PLAN, Phase.DECIDE},
    Phase.PREFLIGHT_GOV: {Phase.PLAN},
    # PLAN can also short-circuit to DECIDE (e.g. compilation yields REJECT/pruned).
    Phase.PLAN: {Phase.PLAN, Phase.EXECUTE, Phase.DECIDE},
    # Self-healing loop: execution-time feedback can require reframing/repairing the IR.
    # This enables edges like compile_model/run_sim -> repair_ir in the workflow graph.
    # EXECUTE can short-circuit to DECIDE when the run is pruned early.
    Phase.EXECUTE: {Phase.EXECUTE, Phase.POSTFLIGHT_GOV, Phase.FRAME, Phase.DECIDE},
    Phase.POSTFLIGHT_GOV: {Phase.DECIDE},
    Phase.DECIDE: {Phase.PUBLISH},
    Phase.PUBLISH: {Phase.ARCHIVE},
    Phase.ARCHIVE: {Phase.ARCHIVE},
}


@dataclass
class KernelState:
    phase: Phase = Phase.INTAKE

    def can_transition(self, next_phase: Phase) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.phase, set())
        return next_phase in allowed or next_phase == self.phase
