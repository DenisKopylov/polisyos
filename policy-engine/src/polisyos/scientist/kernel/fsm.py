from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Set


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
    REFLEXION = "REFLEXION"


ALLOWED_TRANSITIONS: Dict[Phase, Set[Phase]] = {
    Phase.INTAKE: {Phase.FRAME},
    # FRAME can short-circuit to DECIDE when the policy is rejected/pruned early.
    Phase.FRAME: {Phase.FRAME, Phase.REFLEXION, Phase.PREFLIGHT_GOV, Phase.PLAN, Phase.DECIDE},
    Phase.PREFLIGHT_GOV: {Phase.PLAN, Phase.REFLEXION},
    # PLAN can also short-circuit to DECIDE (e.g. compilation yields REJECT/pruned).
    Phase.PLAN: {Phase.PLAN, Phase.EXECUTE, Phase.REFLEXION, Phase.DECIDE},
    # Self-healing loop: execution-time feedback can require reframing/repairing the IR.
    # This enables edges like compile_model/run_sim -> repair_ir in the workflow graph.
    # EXECUTE can short-circuit to DECIDE when the run is pruned early.
    Phase.EXECUTE: {
        Phase.EXECUTE,
        Phase.POSTFLIGHT_GOV,
        Phase.FRAME,
        Phase.REFLEXION,
        Phase.DECIDE,
    },
    Phase.POSTFLIGHT_GOV: {Phase.DECIDE, Phase.REFLEXION},
    Phase.REFLEXION: {Phase.FRAME, Phase.PLAN, Phase.DECIDE},
    Phase.DECIDE: {Phase.PUBLISH},
    Phase.PUBLISH: {Phase.ARCHIVE},
    Phase.ARCHIVE: {Phase.ARCHIVE},
}


@dataclass
class ReflexionGuard:
    """
    Guard conditions for entering/exiting REFLEXION phase.
    """

    max_reflexion_cycles: int = 3
    require_failure_card: bool = True

    def can_enter_reflexion(self, state: Dict) -> bool:
        if self.require_failure_card:
            if state.get("current_failure_card") is None:
                return False

        reflexion_count = state.get("reflexion_cycle_count", 0)
        if reflexion_count >= self.max_reflexion_cycles:
            return False

        return True

    def can_exit_to_frame(self, state: Dict) -> bool:
        decision = state.get("reflexion_decision")
        return decision in ["return_to_formalizer", "return_to_drafter"]

    def can_exit_to_decide(self, state: Dict) -> bool:
        decision = state.get("reflexion_decision")
        return decision in ["abort_with_report", "escalate_to_human"]


@dataclass
class KernelState:
    phase: Phase = Phase.INTAKE
    reflexion_guard: Optional[ReflexionGuard] = None

    def __post_init__(self) -> None:
        if self.reflexion_guard is None:
            self.reflexion_guard = ReflexionGuard()

    def can_transition(self, next_phase: Phase) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.phase, set())
        return next_phase in allowed or next_phase == self.phase

    def is_reflexion_eligible(self, state: Dict) -> bool:
        return self.can_transition(Phase.REFLEXION) and self.reflexion_guard.can_enter_reflexion(state)


class TransitionEvent(str, Enum):
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    COMPILATION_PASSED = "compilation_passed"
    COMPILATION_FAILED = "compilation_failed"
    SIMULATION_PASSED = "simulation_passed"
    SIMULATION_FAILED = "simulation_failed"
    GOVERNOR_APPROVED = "governor_approved"
    GOVERNOR_REJECTED = "governor_rejected"
    REFLEXION_RETRY = "reflexion_retry"
    REFLEXION_ABORT = "reflexion_abort"
    REFLEXION_ESCALATE = "reflexion_escalate"
    BUDGET_EXHAUSTED = "budget_exhausted"
