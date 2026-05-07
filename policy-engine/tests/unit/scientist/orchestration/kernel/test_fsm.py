"""Tests for polisyos.scientist.orchestration.kernel.fsm — Phase FSM, ReflexionGuard, KernelState."""

from __future__ import annotations

import pytest
from polisyos.scientist.orchestration.kernel.fsm import (
    ALLOWED_TRANSITIONS,
    KernelState,
    Phase,
    ReflexionGuard,
    TransitionEvent,
)

# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------


class TestPhase:
    def test_all_phases_exist(self):
        expected = {
            "INTAKE",
            "FRAME",
            "PREFLIGHT_GOV",
            "PLAN",
            "EXECUTE",
            "POSTFLIGHT_GOV",
            "DECIDE",
            "PUBLISH",
            "ARCHIVE",
            "SEARCH_INIT",
            "SEARCH_ITERATE",
            "SEARCH_COMPLETE",
            "REFLEXION",
        }
        assert {p.name for p in Phase} == expected

    def test_phase_count(self):
        assert len(Phase) == 13

    def test_phase_is_string_enum(self):
        assert isinstance(Phase.INTAKE, str)
        assert Phase.INTAKE == "INTAKE"

    def test_phase_value_matches_name(self):
        for p in Phase:
            assert p.value == p.name


# ---------------------------------------------------------------------------
# ALLOWED_TRANSITIONS
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    def test_all_phases_have_transitions(self):
        for p in Phase:
            assert p in ALLOWED_TRANSITIONS, f"Phase {p} missing from ALLOWED_TRANSITIONS"

    @pytest.mark.parametrize(
        "src,dst",
        [
            (Phase.INTAKE, Phase.FRAME),
            (Phase.INTAKE, Phase.SEARCH_INIT),
            (Phase.FRAME, Phase.PREFLIGHT_GOV),
            (Phase.FRAME, Phase.PLAN),
            (Phase.FRAME, Phase.DECIDE),
            (Phase.FRAME, Phase.REFLEXION),
            (Phase.FRAME, Phase.FRAME),
            (Phase.PREFLIGHT_GOV, Phase.PLAN),
            (Phase.PREFLIGHT_GOV, Phase.REFLEXION),
            (Phase.PLAN, Phase.EXECUTE),
            (Phase.PLAN, Phase.REFLEXION),
            (Phase.PLAN, Phase.DECIDE),
            (Phase.PLAN, Phase.PLAN),
            (Phase.EXECUTE, Phase.POSTFLIGHT_GOV),
            (Phase.EXECUTE, Phase.FRAME),
            (Phase.EXECUTE, Phase.REFLEXION),
            (Phase.EXECUTE, Phase.DECIDE),
            (Phase.EXECUTE, Phase.EXECUTE),
            (Phase.POSTFLIGHT_GOV, Phase.DECIDE),
            (Phase.POSTFLIGHT_GOV, Phase.REFLEXION),
            (Phase.REFLEXION, Phase.FRAME),
            (Phase.REFLEXION, Phase.PLAN),
            (Phase.REFLEXION, Phase.DECIDE),
            (Phase.DECIDE, Phase.PUBLISH),
            (Phase.DECIDE, Phase.ARCHIVE),
            (Phase.PUBLISH, Phase.ARCHIVE),
            (Phase.ARCHIVE, Phase.ARCHIVE),
            (Phase.SEARCH_INIT, Phase.SEARCH_ITERATE),
            (Phase.SEARCH_INIT, Phase.DECIDE),
            (Phase.SEARCH_ITERATE, Phase.SEARCH_ITERATE),
            (Phase.SEARCH_ITERATE, Phase.SEARCH_COMPLETE),
            (Phase.SEARCH_ITERATE, Phase.FRAME),
            (Phase.SEARCH_COMPLETE, Phase.DECIDE),
        ],
    )
    def test_valid_transition(self, src: Phase, dst: Phase):
        assert dst in ALLOWED_TRANSITIONS[src]

    @pytest.mark.parametrize(
        "src,dst",
        [
            (Phase.INTAKE, Phase.EXECUTE),
            (Phase.INTAKE, Phase.DECIDE),
            (Phase.INTAKE, Phase.ARCHIVE),
            (Phase.DECIDE, Phase.INTAKE),
            (Phase.DECIDE, Phase.EXECUTE),
            (Phase.PUBLISH, Phase.INTAKE),
            (Phase.ARCHIVE, Phase.INTAKE),
            (Phase.SEARCH_COMPLETE, Phase.SEARCH_ITERATE),
        ],
    )
    def test_invalid_transition(self, src: Phase, dst: Phase):
        assert dst not in ALLOWED_TRANSITIONS[src]


# ---------------------------------------------------------------------------
# ReflexionGuard
# ---------------------------------------------------------------------------


class TestReflexionGuard:
    def test_defaults(self):
        g = ReflexionGuard()
        assert g.max_reflexion_cycles == 3
        assert g.require_failure_card is True

    def test_can_enter_reflexion_with_failure_card(self):
        g = ReflexionGuard()
        state = {"current_failure_card": {"some": "data"}, "reflexion_cycle_count": 0}
        assert g.can_enter_reflexion(state) is True

    def test_cannot_enter_reflexion_without_failure_card(self):
        g = ReflexionGuard()
        state = {"reflexion_cycle_count": 0}
        assert g.can_enter_reflexion(state) is False

    def test_cannot_enter_reflexion_when_none_failure_card(self):
        g = ReflexionGuard()
        state = {"current_failure_card": None, "reflexion_cycle_count": 0}
        assert g.can_enter_reflexion(state) is False

    def test_can_enter_reflexion_without_requiring_failure_card(self):
        g = ReflexionGuard(require_failure_card=False)
        state = {"reflexion_cycle_count": 0}
        assert g.can_enter_reflexion(state) is True

    def test_cannot_enter_reflexion_at_max_cycles(self):
        g = ReflexionGuard(max_reflexion_cycles=2)
        state = {"current_failure_card": {}, "reflexion_cycle_count": 2}
        assert g.can_enter_reflexion(state) is False

    def test_cannot_enter_reflexion_above_max_cycles(self):
        g = ReflexionGuard(max_reflexion_cycles=2)
        state = {"current_failure_card": {}, "reflexion_cycle_count": 5}
        assert g.can_enter_reflexion(state) is False

    def test_can_enter_reflexion_below_max_cycles(self):
        g = ReflexionGuard(max_reflexion_cycles=3)
        state = {"current_failure_card": {}, "reflexion_cycle_count": 2}
        assert g.can_enter_reflexion(state) is True

    def test_missing_cycle_count_defaults_to_zero(self):
        g = ReflexionGuard()
        state = {"current_failure_card": {}}
        assert g.can_enter_reflexion(state) is True

    def test_can_exit_to_frame_return_to_formalizer(self):
        g = ReflexionGuard()
        assert g.can_exit_to_frame({"reflexion_decision": "return_to_formalizer"}) is True

    def test_can_exit_to_frame_return_to_drafter(self):
        g = ReflexionGuard()
        assert g.can_exit_to_frame({"reflexion_decision": "return_to_drafter"}) is True

    def test_cannot_exit_to_frame_abort(self):
        g = ReflexionGuard()
        assert g.can_exit_to_frame({"reflexion_decision": "abort_with_report"}) is False

    def test_cannot_exit_to_frame_escalate(self):
        g = ReflexionGuard()
        assert g.can_exit_to_frame({"reflexion_decision": "escalate_to_human"}) is False

    def test_cannot_exit_to_frame_no_decision(self):
        g = ReflexionGuard()
        assert g.can_exit_to_frame({}) is False

    def test_can_exit_to_decide_abort(self):
        g = ReflexionGuard()
        assert g.can_exit_to_decide({"reflexion_decision": "abort_with_report"}) is True

    def test_can_exit_to_decide_escalate(self):
        g = ReflexionGuard()
        assert g.can_exit_to_decide({"reflexion_decision": "escalate_to_human"}) is True

    def test_cannot_exit_to_decide_return_to_formalizer(self):
        g = ReflexionGuard()
        assert g.can_exit_to_decide({"reflexion_decision": "return_to_formalizer"}) is False

    def test_cannot_exit_to_decide_no_decision(self):
        g = ReflexionGuard()
        assert g.can_exit_to_decide({}) is False


# ---------------------------------------------------------------------------
# KernelState
# ---------------------------------------------------------------------------


class TestKernelState:
    def test_default_phase(self):
        ks = KernelState()
        assert ks.phase == Phase.INTAKE

    def test_default_creates_reflexion_guard(self):
        ks = KernelState()
        assert ks.reflexion_guard is not None
        assert isinstance(ks.reflexion_guard, ReflexionGuard)

    def test_custom_guard_preserved(self):
        guard = ReflexionGuard(max_reflexion_cycles=5)
        ks = KernelState(reflexion_guard=guard)
        assert ks.reflexion_guard.max_reflexion_cycles == 5

    def test_can_transition_valid(self):
        ks = KernelState(phase=Phase.INTAKE)
        assert ks.can_transition(Phase.FRAME) is True

    def test_can_transition_invalid(self):
        ks = KernelState(phase=Phase.INTAKE)
        assert ks.can_transition(Phase.EXECUTE) is False

    def test_can_transition_self_always(self):
        for p in Phase:
            ks = KernelState(phase=p)
            assert ks.can_transition(p) is True, f"Self-transition failed for {p}"

    def test_is_reflexion_eligible_from_valid_phase(self):
        ks = KernelState(phase=Phase.FRAME)
        state = {"current_failure_card": {}, "reflexion_cycle_count": 0}
        assert ks.is_reflexion_eligible(state) is True

    def test_is_reflexion_eligible_from_invalid_phase(self):
        ks = KernelState(phase=Phase.INTAKE)
        state = {"current_failure_card": {}, "reflexion_cycle_count": 0}
        assert ks.is_reflexion_eligible(state) is False

    def test_is_reflexion_eligible_guard_blocks(self):
        ks = KernelState(phase=Phase.FRAME)
        state = {"reflexion_cycle_count": 0}  # no failure card
        assert ks.is_reflexion_eligible(state) is False


# ---------------------------------------------------------------------------
# TransitionEvent enum
# ---------------------------------------------------------------------------


class TestTransitionEvent:
    def test_all_events_exist(self):
        expected = {
            "VALIDATION_PASSED",
            "VALIDATION_FAILED",
            "COMPILATION_PASSED",
            "COMPILATION_FAILED",
            "SIMULATION_PASSED",
            "SIMULATION_FAILED",
            "GOVERNOR_APPROVED",
            "GOVERNOR_REJECTED",
            "REFLEXION_RETRY",
            "REFLEXION_ABORT",
            "REFLEXION_ESCALATE",
            "BUDGET_EXHAUSTED",
        }
        assert {e.name for e in TransitionEvent} == expected

    def test_event_count(self):
        assert len(TransitionEvent) == 12

    def test_event_is_string_enum(self):
        assert isinstance(TransitionEvent.VALIDATION_PASSED, str)
