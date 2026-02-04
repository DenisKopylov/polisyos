"""Public entrypoints for Scientist workflows."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping

try:
    from opentelemetry.trace import Status, StatusCode
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class StatusCode(str, Enum):
        OK = "OK"
        ERROR = "ERROR"

    class Status:  # type: ignore[override]
        def __init__(self, status_code: StatusCode, description: str | None = None) -> None:
            self.status_code = status_code
            self.description = description

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.run.context import new_run_id

__all__ = ["ExperimentState", "run_experiment"]

if TYPE_CHECKING:
    from polisyos.scientist.engine.state import ExperimentState


def _experiment_state_cls():
    from polisyos.scientist.engine.state import ExperimentState

    return ExperimentState


def _prepare_initial_state(state: Mapping[str, Any] | "ExperimentState" | None) -> "ExperimentState":
    ExperimentState = _experiment_state_cls()
    if isinstance(state, ExperimentState):
        initial_state = state
    elif isinstance(state, Mapping):
        payload = dict(state)
        payload.setdefault("run_id", "")
        initial_state = ExperimentState.model_validate(payload)
    else:
        initial_state = ExperimentState.model_validate(state or {"run_id": ""})

    if not initial_state.run_id:
        payload: dict[str, Any] = {}
        if isinstance(state, Mapping):
            payload.update(state)
        payload["run_id"] = new_run_id()
        initial_state = ExperimentState.model_validate(payload)
    return initial_state


def run_experiment(
    state: Mapping[str, Any] | "ExperimentState" | None = None,
) -> dict[str, Any]:
    """
    Official entrypoint to execute the Scientist workflow.

    Parameters
    ----------
    state:
        Initial experiment state (keys match ExperimentState). If None, starts from
        an empty state.
    Returns
    -------
    dict[str, Any]
        Final ExperimentState produced by the workflow.
    """
    tracer = get_tracer()
    metrics = get_metrics()
    ExperimentState = _experiment_state_cls()

    if isinstance(state, Mapping):
        extra_keys = sorted(set(state.keys()) - set(ExperimentState.model_fields.keys()))
        if extra_keys:
            raise ValueError(
                "Unsupported Scientist state keys detected. "
                f"Unsupported keys: {extra_keys}. "
                "Migrate payload to scientist.engine.ExperimentState schema."
            )

    initial_state = _prepare_initial_state(state)

    with tracer.start_as_current_span(
        "experiment.workflow",
        attributes={
            "polisyos.run_id": initial_state.run_id,
            "polisyos.workflow.type": "scientist",
            "polisyos.phase": "INTAKE",
        },
    ) as root_span:
        metrics.increment_active_runs()
        try:
            from polisyos.scientist.workflows.builder import run_default_workflow
            result = run_default_workflow(initial_state)
            final_state = result.state
            root_span.set_status(Status(StatusCode.OK))
            return final_state.model_dump()
        except Exception as exc:
            root_span.set_status(Status(StatusCode.ERROR, str(exc)))
            root_span.record_exception(exc)
            metrics.record_workflow_run("error", "UNKNOWN", "orchestrator")
            raise
        finally:
            metrics.decrement_active_runs()


def __getattr__(name: str):
    if name == "ExperimentState":
        from polisyos.scientist.engine.state import ExperimentState

        return ExperimentState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
