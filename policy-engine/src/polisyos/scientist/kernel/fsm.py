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
    Phase.FRAME: {Phase.FRAME, Phase.PREFLIGHT_GOV, Phase.PLAN},
    Phase.PREFLIGHT_GOV: {Phase.PLAN},
    Phase.PLAN: {Phase.PLAN, Phase.EXECUTE},
    Phase.EXECUTE: {Phase.EXECUTE, Phase.POSTFLIGHT_GOV},
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
