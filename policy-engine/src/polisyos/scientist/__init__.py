"""Public entrypoints for Scientist workflows."""

from __future__ import annotations

import warnings
import uuid
from typing import Any, Mapping

from opentelemetry.trace import Status, StatusCode

from polisyos.core.observability import get_metrics, get_tracer

__all__ = ["build_workflow", "run_experiment", "deprecated_import"]


def deprecated_import(message: str) -> None:
    """Emit a uniform DeprecationWarning for legacy Scientist APIs."""
    warnings.warn(message, DeprecationWarning, stacklevel=2)


def run_experiment(state: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    workflow = build_workflow()
    tracer = get_tracer()
    metrics = get_metrics()

    initial_state = dict(state or {})
    run_id = initial_state.get("run_id") or f"R_{uuid.uuid4().hex[:8]}"
    initial_state["run_id"] = run_id

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
            final_state = workflow.invoke(initial_state)

            feedback = final_state.get("feedback") if isinstance(final_state, dict) else None
            verdict = feedback.get("verdict") if isinstance(feedback, dict) else None
            if verdict:
                root_span.set_attribute("polisyos.workflow.final_verdict", verdict)
            if not final_state.get("_workflow_metrics_recorded"):
                status = "success" if verdict == "APPROVE" else "failure"
                metrics.record_workflow_run(status, "DECIDE", "orchestrator")

            root_span.set_status(Status(StatusCode.OK))
            return final_state
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
    from polisyos.scientist.orchestrator.workflow import build_workflow as _build_workflow

    return _build_workflow()
