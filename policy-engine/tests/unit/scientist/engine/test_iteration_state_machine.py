from __future__ import annotations

import pytest
from polisyos.core.contracts.execution_plan import IterationState
from polisyos.scientist.engine.iteration_state_machine import (
    IterationTransitionError,
    can_transition,
    derive_terminal_state_from_verdict,
    transition,
)


def test_iteration_state_machine_happy_path() -> None:
    state = IterationState(run_id="R_smoke")
    state = transition(state, "start_preflight")
    state = transition(state, "preflight_ready")
    state = transition(state, "start_execute")
    state = transition(state, "execute_done")
    state = transition(state, "approve", verdict="APPROVE", stop_reason="approved")
    assert state.lifecycle_state == "approved"
    assert state.stop_reason == "approved"
    assert state.last_verdict == "APPROVE"


def test_iteration_state_machine_rejects_invalid_transition() -> None:
    state = IterationState(run_id="R_invalid")
    assert can_transition(state.lifecycle_state, "approve") is False
    with pytest.raises(IterationTransitionError):
        transition(state, "approve")


def test_iteration_state_machine_rejects_unknown_event() -> None:
    with pytest.raises(IterationTransitionError, match="Unsupported transition event"):
        can_transition("plan_created", "teleport")


def test_terminal_state_mapping() -> None:
    assert derive_terminal_state_from_verdict("APPROVE") == ("approved", "approved")
    assert derive_terminal_state_from_verdict("STOP_BUDGET") == (
        "stopped_budget",
        "budget_exhausted",
    )
