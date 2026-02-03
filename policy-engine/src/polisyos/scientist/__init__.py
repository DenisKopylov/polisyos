"""Public entrypoints for Scientist workflows."""

from __future__ import annotations

import warnings
from typing import Any, Mapping

from opentelemetry.trace import Status, StatusCode

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.run.context import new_run_id
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.workflows.builder import run_default_workflow

__all__ = ["build_workflow", "run_experiment", "run_experiment_langgraph", "deprecated_import"]


def deprecated_import(message: str) -> None:
    """Emit a uniform DeprecationWarning for legacy Scientist APIs."""
    warnings.warn(message, DeprecationWarning, stacklevel=2)


def run_experiment(state: Mapping[str, Any] | ExperimentState | None = None) -> dict[str, Any]:
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

    if isinstance(state, ExperimentState):
        initial_state = state
    elif isinstance(state, Mapping):
        extra_keys = set(state.keys()) - set(ExperimentState.model_fields.keys())
        if extra_keys:
            return run_experiment_langgraph(state)
        initial_state = ExperimentState.model_validate(state or {"run_id": ""})
        if not initial_state.run_id:
            initial_state = ExperimentState.model_validate({**(state or {}), "run_id": new_run_id()})
    else:
        initial_state = ExperimentState.model_validate(state or {"run_id": ""})
        if not initial_state.run_id:
            initial_state = ExperimentState.model_validate({**(state or {}), "run_id": new_run_id()})

    with tracer.start_as_current_span(
        "experiment.workflow",
        attributes={
            "polisyos.run_id": run_id,
            "polisyos.workflow.type": "scientist",
            "polisyos.phase": "INTAKE",
        },
    ) as root_span:
        metrics.increment_active_runs()
        try:
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


def build_workflow():
    """
    Lazy import wrapper for the Scientist workflow builder.

    This keeps lightweight modules (e.g. orchestrator artifacts) importable even if optional
    orchestration dependencies (like langgraph) are not installed in the current environment.
    """
    deprecated_import(
        "polisyos.scientist.build_workflow() is deprecated; use engine workflows in polisyos.scientist.workflows."
    )
    from polisyos.scientist.orchestrator.workflow import build_workflow as _build_workflow

    return _build_workflow()


def run_experiment_langgraph(state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Legacy LangGraph-based Scientist entrypoint (deprecated)."""
    deprecated_import(
        "polisyos.scientist.run_experiment_langgraph() is deprecated; use polisyos.scientist.run_experiment()."
    )
    workflow = build_workflow()
    initial_state = dict(state or {})
    if "run_id" not in initial_state:
        initial_state["run_id"] = "R_legacy"
    return workflow.invoke(initial_state)
