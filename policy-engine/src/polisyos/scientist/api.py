"""Public orchestration entrypoints for running Scientist workflow DAGs.

This module owns the stable top-level `run_experiment()` API exposed by the
package facade. It normalizes caller-provided state payloads, routes to the
workflow builder selected by `ExperimentState`/`params`, and wraps the run with
OpenTelemetry metrics/tracing so downstream adapters can stay pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.core.run.context import new_run_id

Status: Any
StatusCode: Any

try:
    from opentelemetry import trace as _otel_trace
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency

    class _FallbackStatusCode(str, Enum):
        OK = "OK"
        ERROR = "ERROR"

    class _FallbackStatus:
        def __init__(
            self,
            status_code: _FallbackStatusCode,
            description: str | None = None,
        ) -> None:
            self.status_code = status_code
            self.description = description

    Status = _FallbackStatus
    StatusCode = _FallbackStatusCode
else:
    Status = _otel_trace.Status
    StatusCode = _otel_trace.StatusCode

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.governance.passes.base import ValidatorPass
    from polisyos.scientist.governance.pipeline import ValidationPipeline
    from polisyos.scientist.orchestration.engine.metrics_protocol import EngineMetricsCollector
    from polisyos.scientist.orchestration.engine.registry import NodeBootstrapReport, NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows.builder import QuotaRegistry


def _experiment_state_cls() -> type[ExperimentState]:
    from polisyos.scientist.orchestration.engine.state import ExperimentState as _ExperimentState

    return cast("type[ExperimentState]", _ExperimentState)


def _prepare_initial_state(state: Mapping[str, Any] | ExperimentState | None) -> ExperimentState:
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
        initial_payload: dict[str, Any] = {}
        if isinstance(state, Mapping):
            initial_payload.update(state)
        initial_payload["run_id"] = new_run_id()
        initial_state = ExperimentState.model_validate(initial_payload)
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


def _estimate_run_cost_usd(state: ExperimentState) -> float | None:
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

    return float(
        estimate_llm_cost_usd(
            model=model,
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
        )
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


def load_governance_passes() -> list[ValidatorPass]:
    """Load Scientist governance passes from entry points plus builtin fallbacks."""
    from polisyos.scientist.governance.pass_registry import load_governance_passes as _load

    return _load()


def build_governance_pipeline() -> ValidationPipeline:
    """Build the governance validation pipeline from discovered pass providers."""
    from polisyos.scientist.governance.pass_registry import (
        build_governance_pipeline as _build,
    )

    return _build()


def discover_scientist_nodes(
    registry: NodeRegistry | None = None,
    *,
    include_dev_scan: bool = True,
) -> tuple[NodeRegistry, NodeBootstrapReport]:
    """Discover builtin and external node providers for the Scientist DAG runtime."""
    from polisyos.scientist.nodes import discover_scientist_nodes as _discover

    return _discover(registry, include_dev_scan=include_dev_scan)


def run_experiment(
    state: Mapping[str, Any] | ExperimentState | None = None,
    *,
    tracer: Any | None = None,
    metrics: Any | None = None,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    quota_registry: QuotaRegistry | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> dict[str, Any]:
    """Execute the Scientist workflow selected by the initial state contract.

    `state.params["workflow_id"]`, `state.execution_profile`, and input bundle
    presence determine whether the run uses `scientist_default`,
    `scientist_causal_full`, `scientist_policy_verified`, `scientist_policy_design`,
    or `scientist_discovery`. Unknown top-level keys are rejected before any node
    executes so the facade stays schema-stable.

    Args:
        state: Mapping or `ExperimentState` payload to seed the run. When `None`,
            a fresh run id and empty state container are generated.

    Returns:
        Final `ExperimentState` serialized as a JSON-compatible dictionary with
        updated `params`, `inputs`, `artifacts_index`, and `reports_index`.

    Raises:
        ValueError: If the mapping contains keys outside `ExperimentState`.
        Exception: Propagates workflow construction or node execution failures
            after recording an error span and metrics.

    Example:
        ```python
        from polisyos.scientist import run_experiment

        final_state = run_experiment(
            {
                "run_id": "R_demo",
                "params": {"workflow_id": "scientist_discovery"},
                "inputs": {"registry_bundle_ref": {"artifact_id": "artifact:..."}},
            }
        )
        ```
    """
    resolved_tracer = tracer
    resolved_metrics = metrics
    if resolved_tracer is None or resolved_metrics is None:
        default_tracer, default_metrics = _resolve_observability()
        if resolved_tracer is None:
            resolved_tracer = default_tracer
        if resolved_metrics is None:
            resolved_metrics = default_metrics
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
    from polisyos.scientist.orchestration.workflows.builder import (
        resolve_workflow_id,
        run_selected_workflow,
    )

    workflow_id = resolve_workflow_id(initial_state)

    if resolved_tracer is None or resolved_metrics is None:
        raise RuntimeError("Scientist observability providers could not be resolved")

    with resolved_tracer.start_as_current_span(
        "experiment.workflow",
        attributes={
            "polisyos.run_id": initial_state.run_id,
            "polisyos.workflow.type": "scientist",
            "polisyos.phase": "INTAKE",
            "polisyos.workflow_id": workflow_id,
        },
    ) as root_span:
        resolved_metrics.increment_active_runs()
        try:
            with resolved_metrics.time_slo_dag({"workflow_id": workflow_id}):
                result = run_selected_workflow(
                    initial_state,
                    store=store,
                    store_factory=store_factory,
                    tracer=resolved_tracer,
                    metrics=resolved_metrics,
                    quota_registry=quota_registry,
                    engine_metrics_factory=engine_metrics_factory,
                )
            final_state = result.state
            status = "success" if result.report.status == "ok" else "error"
            resolved_metrics.record_workflow_run(status, "EXECUTE", "orchestrator")
            resolved_metrics.record_slo_dag_run(status, workflow_id=workflow_id)

            cost_usd = _estimate_run_cost_usd(final_state)
            if cost_usd is not None:
                resolved_metrics.record_slo_run_cost(cost_usd, workflow_id=workflow_id)

            if status == "success":
                root_span.set_status(Status(StatusCode.OK))
            else:
                root_span.set_status(
                    Status(StatusCode.ERROR, "Workflow report status indicates failure")
                )
            return cast("dict[str, Any]", final_state.model_dump())
        except Exception as exc:
            root_span.set_status(Status(StatusCode.ERROR, str(exc)))
            root_span.record_exception(exc)
            resolved_metrics.record_workflow_run("error", "UNKNOWN", "orchestrator")
            resolved_metrics.record_slo_dag_run("error", workflow_id=workflow_id)
            raise
        finally:
            resolved_metrics.decrement_active_runs()


__all__ = [
    "build_governance_pipeline",
    "discover_scientist_nodes",
    "load_governance_passes",
    "run_experiment",
]
