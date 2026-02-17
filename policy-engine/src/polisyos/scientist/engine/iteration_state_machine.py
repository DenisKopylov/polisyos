from __future__ import annotations

from datetime import datetime, timezone

from polisyos.core.contracts.execution_plan import (
    EvaluatorVerdict,
    IterationLifecycleState,
    IterationState,
    StopReason,
)

TransitionEvent = str

_ALLOWED: dict[IterationLifecycleState, frozenset[TransitionEvent]] = {
    "plan_created": frozenset({"start_preflight"}),
    "preflight_running": frozenset({"preflight_ready", "preflight_failed"}),
    "preflight_failed": frozenset({"replan"}),
    "ready_to_run": frozenset({"start_execute"}),
    "executing": frozenset({"execute_done"}),
    "evaluating": frozenset({"approve", "replan", "stop_budget", "stop_no_delta", "stop_guardrail"}),
    "replanning": frozenset({"start_preflight"}),
    "approved": frozenset(),
    "stopped_budget": frozenset(),
    "stopped_no_delta": frozenset(),
    "stopped_guardrail": frozenset(),
}


def can_transition(state: IterationLifecycleState, event: TransitionEvent) -> bool:
    return event in _ALLOWED.get(state, frozenset())


def transition(
    state: IterationState,
    event: TransitionEvent,
    *,
    verdict: EvaluatorVerdict | None = None,
    stop_reason: StopReason | None = None,
    notes: list[str] | None = None,
) -> IterationState:
    current = state.lifecycle_state
    if not can_transition(current, event):
        raise ValueError(f"Invalid transition: state={current!r}, event={event!r}")
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
    if verdict == "APPROVE":
        return "approved", "approved"
    if verdict == "STOP_BUDGET":
        return "stopped_budget", "budget_exhausted"
    return "replanning", None


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
    return state


__all__ = [
    "TransitionEvent",
    "can_transition",
    "transition",
    "derive_terminal_state_from_verdict",
]
