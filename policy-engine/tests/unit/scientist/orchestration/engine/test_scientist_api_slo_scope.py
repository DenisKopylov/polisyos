"""Controlled API and engine scope for Scientist SLO instruments."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import get_tracer

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.observability.config import MetricsExporterType, OTelConfig, ResourceConfig
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.builtins.noop import NoopNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.fan_out import FanOutConfig, FanOutNode
from polisyos.scientist.orchestration.engine.metrics_otel import OTelEngineMetrics
from polisyos.scientist.orchestration.engine.protocol import NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

REPO_ROOT = Path(__file__).resolve().parents[5]
_TASK_ID = "test.scientist_api_scope_task@1.0.0"


class _BoundTask:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.spec = _task_spec()

    def execute(self, ctx: ExecutionContext, state):
        if self.fail:
            raise RuntimeError("controlled task failure")
        return NoopNode().execute(ctx, state)


class _Task:
    def __init__(self) -> None:
        self.spec = _task_spec()

    def bind(self, params: dict[str, Any]) -> _BoundTask:
        return _BoundTask(fail=params.get("item") == "explode")

    def execute(self, ctx: ExecutionContext, state):
        raise RuntimeError("Controlled task must be bound before execution")


def _task_spec() -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(_TASK_ID),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Controlled Scientist SLO task",
            description="A source-controlled task for API and engine measurement scope.",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=[],
        state_writes=[],
        produces=[],
    )


def _collect_metrics(reader: InMemoryMetricReader) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for resource in reader.get_metrics_data().resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name not in {
                    "polisyos_slo_dag_runs_total",
                    "polisyos_slo_dag_duration_seconds",
                }:
                    continue
                points: list[dict[str, Any]] = []
                for point in metric.data.data_points:
                    row: dict[str, Any] = {
                        "attributes": {
                            str(key): str(value) for key, value in point.attributes.items()
                        }
                    }
                    if hasattr(point, "value"):
                        row["value"] = int(point.value)
                    if hasattr(point, "count"):
                        row["count"] = int(point.count)
                    points.append(row)
                collected.append({"name": metric.name, "points": points})
    return collected


def _setup_metrics(monkeypatch: pytest.MonkeyPatch, *, environment: str = "test"):
    from polisyos.core.observability import _metrics_registry_base as registry_base
    from polisyos.core.observability.metrics_parts import MetricsRegistry

    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=Resource.create({"service.name": "polisyos-controlled-test"}),
        metric_readers=[reader],
    )
    config = OTelConfig(
        enabled=True,
        metrics_exporter=MetricsExporterType.NONE,
        environment=environment,
    )
    monkeypatch.setattr(registry_base, "get_default_config", lambda: config)
    monkeypatch.setattr(
        registry_base,
        "get_resource_config",
        lambda _: ResourceConfig(
            service_name="polisyos-controlled-test",
            service_version="test",
            deployment_environment=environment,
        ),
    )
    monkeypatch.setattr(otel_metrics, "get_meter", provider.get_meter)
    monkeypatch.setattr(otel_metrics, "set_meter_provider", lambda _: None)
    monkeypatch.setattr(registry_base.MetricsRegistryBase, "_instance", None)
    monkeypatch.setattr(registry_base.MetricsRegistryBase, "_initialized", False)
    return reader, provider, MetricsRegistry()


@pytest.mark.parametrize("environment", ["test", "staging"])
def test_scientist_api_and_engine_observations_have_distinct_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
) -> None:
    from polisyos.scientist.api import run_experiment
    from polisyos.scientist.orchestration.engine import fan_out as fan_out_module
    from polisyos.scientist.orchestration.workflows import builder

    reader, provider, metrics = _setup_metrics(monkeypatch, environment=environment)
    helper_calls: list[str] = []
    original_helper = fan_out_module.run_blocking_async

    async def observed_helper(fn, *args, **kwargs):
        helper_calls.append(getattr(fn, "__qualname__", type(fn).__name__))
        return await original_helper(fn, *args, **kwargs)

    monkeypatch.setattr(fan_out_module, "run_blocking_async", observed_helper)

    def controlled_dispatch(initial_state, *, tracer, metrics, **_kwargs):
        run_id = initial_state.run_id
        store = FileSystemCAS(tmp_path / run_id / "cas")
        bundle = build_default_registry_bundle(store, return_selected_profile=True)
        run = RunContext.start(
            store=store,
            registry_bundle=bundle.bundle_ref,
            run_id=run_id,
            run_dir=tmp_path / run_id / "run",
        )
        registry = NodeRegistry()
        registry.register(_Task())
        fan_out = FanOutNode(
            FanOutConfig(
                items_state_path="params.items",
                task_node_id=_TASK_ID,
                item_param_key="item",
                item_index_key="item_index",
                result_state_path="params.results",
                max_parallelism=1,
                continue_on_item_failure=False,
            ),
            registry,
            alias="controlled",
        )
        registry.register(fan_out)
        spec = WorkflowSpec(
            workflow_id="scientist_default",
            nodes=[
                NodeInvocation(
                    alias="controlled_fan_out", node_id=str(fan_out.spec.metadata.component_id)
                )
            ],
        )
        context = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("controlled_scientist_api_scope"),
            tracer=tracer,
            metrics=OTelEngineMetrics(metrics=metrics),
        )
        return asyncio.run(
            AsyncWorkflowExecutor(context, registry, max_parallelism=1).execute(spec, initial_state)
        )

    monkeypatch.setattr(builder, "run_selected_workflow", controlled_dispatch)
    tracer = get_tracer("controlled-scientist-api-scope")
    with pytest.raises(ValueError, match="Unsupported Scientist state keys"):
        run_experiment(
            {"run_id": "invalid-before-workflow-resolution", "not_a_state_field": True},
            tracer=tracer,
            metrics=metrics,
        )

    success = run_experiment(
        {
            "run_id": "scope-success",
            "params": {"workflow_id": "scientist_default", "items": ["ok"]},
        },
        tracer=tracer,
        metrics=metrics,
    )
    failure = run_experiment(
        {
            "run_id": "scope-failure",
            "params": {"workflow_id": "scientist_default", "items": ["explode"]},
        },
        tracer=tracer,
        metrics=metrics,
    )
    assert success["run_id"] == "scope-success"
    assert failure["run_id"] == "scope-failure"
    assert len(helper_calls) == 2

    from polisyos.common import async_tools

    selected_profile = async_tools.get_shared_executor_profile()
    selected_executor = async_tools.get_shared_executor()
    assert selected_executor._max_workers == selected_profile.capacity
    assert selected_executor._max_queued == selected_profile.queue_capacity
    profile_receipt = {
        "revision": selected_profile.revision,
        "capacity": selected_profile.capacity,
        "queue_capacity": selected_profile.queue_capacity,
        "source": selected_profile.source,
        "authority": selected_profile.authority,
    }
    receipt_path = tmp_path / "selected-process-profile.json"
    receipt_path.write_text(json.dumps(profile_receipt, sort_keys=True), encoding="utf-8")
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == profile_receipt

    rows = _collect_metrics(reader)
    runs = next(row for row in rows if row["name"] == "polisyos_slo_dag_runs_total")
    durations = next(row for row in rows if row["name"] == "polisyos_slo_dag_duration_seconds")
    api_counts: dict[str, int] = {}
    engine_counts: dict[str, int] = {}
    for point in runs["points"]:
        attrs = point["attributes"]
        value = point.get("value", 0)
        if attrs.get("measurement_scope") == "scientist_api":
            assert attrs.get("env") == environment
            assert attrs.get("workflow_id") == "scientist_default"
            assert attrs.get("status") in {"success", "error"}
            api_counts[attrs["status"]] = api_counts.get(attrs["status"], 0) + value
        elif attrs.get("measurement_scope") == "scientist_engine":
            assert attrs.get("env") == environment
            assert attrs.get("workflow_id") == "scientist_default"
            assert attrs.get("status") in {"ok", "fail"}
            engine_counts[attrs["status"]] = engine_counts.get(attrs["status"], 0) + value
        else:
            pytest.fail(f"unexpected Scientist DAG metric scope: {attrs}")
    assert api_counts == {"success": 1, "error": 1}
    assert engine_counts == {"ok": 1, "fail": 1}

    api_duration_count = 0
    engine_duration_count = 0
    for point in durations["points"]:
        attrs = point["attributes"]
        if attrs.get("measurement_scope") == "scientist_api":
            assert attrs.get("env") == environment
            assert attrs.get("workflow_id") == "scientist_default"
            api_duration_count += point.get("count", 0)
        elif attrs.get("measurement_scope") == "scientist_engine":
            assert attrs.get("env") == environment
            assert attrs.get("workflow_id") == "scientist_default"
            assert attrs.get("node_count") is not None
            engine_duration_count += point.get("count", 0)
        else:
            pytest.fail(f"unexpected Scientist DAG duration scope: {attrs}")
    assert api_duration_count == 2
    assert engine_duration_count == 2
    provider.shutdown()
