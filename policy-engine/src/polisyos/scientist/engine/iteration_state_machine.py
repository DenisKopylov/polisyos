"""Public engine iteration state machine module API."""
from __future__ import annotations

from datetime import datetime, timezone

from polisyos.core.contracts.execution_plan import (
    EvaluatorVerdict,
    IterationLifecycleState,
    IterationState,
    StopReason,
)
from polisyos.core.errors import ErrorCategory
from polisyos.scientist.engine.errors import EngineError

TransitionEvent = str

_ALLOWED: dict[IterationLifecycleState, frozenset[TransitionEvent]] = {
    "plan_created": frozenset({"start_preflight"}),
    "preflight_running": frozenset({"preflight_ready", "preflight_failed"}),
    "preflight_failed": frozenset({"replan"}),
    "ready_to_run": frozenset({"start_execute"}),
    "executing": frozenset({"execute_done"}),
    "evaluating": frozenset(
        {"approve", "replan", "stop_budget", "stop_no_delta", "stop_guardrail"},
    ),
    "replanning": frozenset({"start_preflight"}),
    "approved": frozenset(),
    "stopped_budget": frozenset(),
    "stopped_no_delta": frozenset(),
    "stopped_guardrail": frozenset(),
}
_KNOWN_EVENTS = frozenset(
    event
    for allowed_events in _ALLOWED.values()
    for event in allowed_events
)


class IterationTransitionError(EngineError):
    """Raised when lifecycle transition inputs are invalid."""

    default_stage = "scientist.engine.iteration_state_machine"
    default_category = ErrorCategory.VALIDATION


def can_transition(state: IterationLifecycleState, event: TransitionEvent) -> bool:
    """Can transition helper."""
    _validate_transition_inputs(state, event)
    return event in _ALLOWED[state]


def transition(
    state: IterationState,
    event: TransitionEvent,
    *,
    verdict: EvaluatorVerdict | None = None,
    stop_reason: StopReason | None = None,
    notes: list[str] | None = None,
) -> IterationState:
    """Transition helper."""
    current = state.lifecycle_state
    if not can_transition(current, event):
        raise IterationTransitionError(
            f"Invalid transition: state={current!r}, event={event!r}",
            code="invalid_transition",
            details={"state": current, "event": event},
        )
    next_state = _next_state(current, event)
    now = datetime.now(timezone.utc)
    merged_notes = list(state.notes)
    merged_notes.append(f"event:{event}")
    merged_notes.extend(notes or [])
    update: dict[str, object] = {
        "lifecycle_state": next_state,
        "updated_at": now,
        "notes": merged_notes,
    }
    if verdict is not None:
        update["last_verdict"] = verdict
    if stop_reason is not None:
        update["stop_reason"] = stop_reason
    return state.model_copy(update=update)


def derive_terminal_state_from_verdict(
    verdict: EvaluatorVerdict,
) -> tuple[IterationLifecycleState, StopReason | None]:
    """Derive terminal state from verdict helper."""
    if verdict == "APPROVE":
        return "approved", "approved"
    if verdict == "STOP_BUDGET":
        return "stopped_budget", "budget_exhausted"
    if verdict in {"REPLAN_DATA", "REPLAN_METHOD", "REPLAN_PARAMS"}:
        return "replanning", None
    raise IterationTransitionError(
        f"Unsupported evaluator verdict: {verdict!r}",
        code="unsupported_verdict",
        details={"verdict": verdict},
    )


def _next_state(state: IterationLifecycleState, event: TransitionEvent) -> IterationLifecycleState:
    if event == "start_preflight":
        return "preflight_running"
    if event == "preflight_ready":
        return "ready_to_run"
    if event == "preflight_failed":
        return "preflight_failed"
    if event == "replan":
        return "replanning"
    if event == "start_execute":
        return "executing"
    if event == "execute_done":
        return "evaluating"
    if event == "approve":
        return "approved"
    if event == "stop_budget":
        return "stopped_budget"
    if event == "stop_no_delta":
        return "stopped_no_delta"
    if event == "stop_guardrail":
        return "stopped_guardrail"
    if event == "replan_params":
        return "replanning"
    raise IterationTransitionError(
        f"Unsupported transition event: {event!r}",
        code="unsupported_event",
        details={"state": state, "event": event},
    )


def _validate_transition_inputs(
    state: IterationLifecycleState,
    event: TransitionEvent,
) -> None:
    if state not in _ALLOWED:
        raise IterationTransitionError(
            f"Unsupported lifecycle state: {state!r}",
            code="unsupported_state",
            details={"state": state},
        )
    if event not in _KNOWN_EVENTS:
        raise IterationTransitionError(
            f"Unsupported transition event: {event!r}",
            code="unsupported_event",
            details={"state": state, "event": event},
        )


__all__ = [
    "TransitionEvent",
    "IterationTransitionError",
    "can_transition",
    "transition",
    "derive_terminal_state_from_verdict",
]
