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
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.core.run.context import new_run_id

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


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _estimate_run_cost_usd(state: "ExperimentState") -> float | None:
    params = state.params

    direct = _as_float(params.get("run_cost_usd"))
    if direct is not None:
        return max(direct, 0.0)

    direct = _as_float(params.get("llm_cost_usd"))
    if direct is not None:
        return max(direct, 0.0)

    variants = params.get("llm_model_variants")
    if isinstance(variants, list):
        total_variant_cost = 0.0
        found_variant_cost = False
        for variant in variants:
            if not isinstance(variant, Mapping):
                continue
            variant_cost = _as_float(variant.get("cost_usd"))
            if variant_cost is None:
                continue
            total_variant_cost += max(variant_cost, 0.0)
            found_variant_cost = True
        if found_variant_cost:
            return total_variant_cost

    model = str(params.get("llm_selected_model") or params.get("llm_model", "default"))
    prompt_tokens = _as_int(params.get("llm_prompt_tokens"))
    if prompt_tokens is None:
        prompt_tokens = _as_int(params.get("llm_tokens_prompt"))
    completion_tokens = _as_int(params.get("llm_completion_tokens"))
    if completion_tokens is None:
        completion_tokens = _as_int(params.get("llm_tokens_completion"))
    if prompt_tokens is None and completion_tokens is None:
        return None

    return estimate_llm_cost_usd(
        model=model,
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
    )


def _resolve_observability() -> tuple[Any, Any]:
    """
    Resolve tracer/metrics from scientist facade first.

    This keeps monkeypatching via `polisyos.scientist.get_metrics/get_tracer`
    effective in contract tests and external wrappers.
    """
    try:
        import polisyos.scientist as scientist_facade

        metrics_factory = getattr(scientist_facade, "get_metrics", get_metrics)
        tracer_factory = getattr(scientist_facade, "get_tracer", get_tracer)
    except Exception:
        metrics_factory = get_metrics
        tracer_factory = get_tracer
    return tracer_factory(), metrics_factory()


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
    tracer, metrics = _resolve_observability()
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
    from polisyos.scientist.workflows.builder import resolve_workflow_id, run_selected_workflow

    workflow_id = resolve_workflow_id(initial_state)

    with tracer.start_as_current_span(
        "experiment.workflow",
        attributes={
            "polisyos.run_id": initial_state.run_id,
            "polisyos.workflow.type": "scientist",
            "polisyos.phase": "INTAKE",
            "polisyos.workflow_id": workflow_id,
        },
    ) as root_span:
        metrics.increment_active_runs()
        try:
            with metrics.time_slo_dag({"workflow_id": workflow_id}):
                result = run_selected_workflow(initial_state)
            final_state = result.state
            status = "success" if result.report.status == "ok" else "error"
            metrics.record_workflow_run(status, "EXECUTE", "orchestrator")
            metrics.record_slo_dag_run(status, workflow_id=workflow_id)

            cost_usd = _estimate_run_cost_usd(final_state)
            if cost_usd is not None:
                metrics.record_slo_run_cost(cost_usd, workflow_id=workflow_id)

            if status == "success":
                root_span.set_status(Status(StatusCode.OK))
            else:
                root_span.set_status(
                    Status(StatusCode.ERROR, "Workflow report status indicates failure")
                )
            return final_state.model_dump()
        except Exception as exc:
            root_span.set_status(Status(StatusCode.ERROR, str(exc)))
            root_span.record_exception(exc)
            metrics.record_workflow_run("error", "UNKNOWN", "orchestrator")
            metrics.record_slo_dag_run("error", workflow_id=workflow_id)
            raise
        finally:
            metrics.decrement_active_runs()


__all__ = ["run_experiment"]
