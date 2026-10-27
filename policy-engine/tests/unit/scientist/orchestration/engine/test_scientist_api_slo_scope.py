"""Controlled source-bound API/Common execution witness for Scientist SLOs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanContext

from polisyos.common import async_tools
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
from tools.ops_runners.release.check_operability_release_gates import (
    _binding_package_role_errors,
    _binding_rows,
    _dependent_binding,
    _objective_instrument_contract,
    _operation_code,
    _package_contracts,
    _promql_metric_selectors,
    _resolve_operation_reference,
    validate_dependent_binding_graph,
    verify_controlled_dependent_execution,
)

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


def _binding_id_for_consumer(consumer: Any) -> str:
    contracts = _package_contracts(REPO_ROOT)
    rows = _binding_rows(contracts)
    matches = [
        binding
        for _, _, binding in rows
        if binding.get("consumer_operation", {}).get("module") == consumer.__module__
        and binding.get("consumer_operation", {}).get("symbol") == consumer.__name__
    ]
    if len(matches) != 1:
        raise ValueError("consumer_binding_not_unique")
    return str(matches[0]["id"])


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


def _setup_metrics(monkeypatch: pytest.MonkeyPatch, *, environment: str):
    from polisyos.core.observability import _metrics_registry_base as registry_base
    from polisyos.core.observability.metrics_parts import MetricsRegistry

    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(
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
    monkeypatch.setattr(otel_metrics, "get_meter", meter_provider.get_meter)
    monkeypatch.setattr(otel_metrics, "set_meter_provider", lambda _: None)
    monkeypatch.setattr(registry_base.MetricsRegistryBase, "_instance", None)
    monkeypatch.setattr(registry_base.MetricsRegistryBase, "_initialized", False)
    return reader, meter_provider, MetricsRegistry()


def _new_trace(environment: str):
    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "polisyos-controlled-test",
                "deployment.environment": environment,
            }
        )
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider, provider.get_tracer("scientist-operability-controlled")


def _profile_payload(profile: Any) -> dict[str, Any]:
    return {
        "revision": profile.revision,
        "capacity": profile.capacity,
        "queue_capacity": profile.queue_capacity,
        "source": profile.source,
        "authority": profile.authority,
    }


def _artifact_ref_payload(value: Any) -> dict[str, Any]:
    from polisyos.core.artifacts.manifest import ArtifactRef

    payload = ArtifactRef.model_validate(value).model_dump(mode="json")
    if type(payload) is not dict:
        raise TypeError("CAS reference did not serialize to an object")
    return payload


def _receipt(
    *,
    binding_id: str,
    run_state: dict[str, Any],
    run_ref: Any,
    observations: tuple[Any, ...],
    report_status: str,
) -> dict[str, Any]:
    from polisyos.scientist.orchestration.engine.component_identity import _code_sha256

    binding = _dependent_binding(REPO_ROOT, binding_id)
    shared, _, source = _resolve_operation_reference(REPO_ROOT, binding["shared_operation"])
    callsite, _, _ = _resolve_operation_reference(REPO_ROOT, binding["callsite_operation"])
    callsite_code = _operation_code(binding["callsite_operation"], callsite)
    related = tuple(item for item in observations if item.caller_code is callsite_code)
    success = report_status == str(binding["outcome_success_report_status"])
    status = str(
        binding["outcome_success_metric_status"]
        if success
        else binding["outcome_failure_metric_status"]
    )
    return {
        "schema_version": binding["schema_version"],
        "binding_id": binding_id,
        "run_id": str(run_state["run_id"]),
        "workflow_id": "scientist_default",
        "objective_names": [str(item["name"]) for item in binding["objective"]],
        "helper_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "helper_code_sha256": _code_sha256(shared),
        "callsite_code_sha256": _code_sha256(callsite),
        "call_ids": sorted(item.call_id for item in related),
        "profile": _profile_payload(
            related[0].profile if related else async_tools.get_shared_executor_profile()
        ),
        "report_status": report_status,
        "metric_status": status,
        "counter_count": 1,
        "duration_count": 1,
        "cas_report_ref": _artifact_ref_payload(run_state["reports_index"]["workflow_report"]),
        "run_manifest_ref": _artifact_ref_payload(run_ref),
        "evidence_scope": "ephemeral_controlled_runtime_capture",
        "deployment_receipt": False,
    }


def _run_case(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
    item: str,
    environment: str,
    forged_shim: bool = False,
    items: tuple[str, ...] | None = None,
    nested_other_api_root: bool = False,
):
    from polisyos.scientist.api import run_experiment
    from polisyos.scientist.orchestration.engine import fan_out as fan_out_module
    from polisyos.scientist.orchestration.workflows import builder

    reader, meter_provider, metrics = _setup_metrics(monkeypatch, environment=environment)
    span_exporter, trace_provider, tracer = _new_trace(environment)
    binding_id = _binding_id_for_consumer(run_experiment)
    dispatch_results: dict[str, Any] = {}
    artifact_stores: dict[str, FileSystemCAS] = {}
    dispatch_observations: dict[str, tuple[Any, ...]] = {}
    dispatch_metric_baselines: dict[str, Any] = {}
    nested_dispatch_started = False

    def controlled_dispatch(initial_state, *, tracer, metrics, **_kwargs):
        nonlocal nested_dispatch_started
        selected_run_id = initial_state.run_id
        if nested_other_api_root and selected_run_id == run_id and not nested_dispatch_started:
            nested_dispatch_started = True
            other_run_id = f"{run_id}-other-api-root"
            run_experiment(
                {
                    "run_id": other_run_id,
                    "params": {
                        "workflow_id": "scientist_policy_design",
                        "items": ["other-root-call"],
                    },
                },
                tracer=tracer,
                metrics=metrics,
            )
            dispatch_metric_baselines[selected_run_id] = reader.get_metrics_data()

        store = FileSystemCAS(tmp_path / selected_run_id / "cas")
        bundle = build_default_registry_bundle(store, return_selected_profile=True)
        run = RunContext.start(
            store=store,
            registry_bundle=bundle.bundle_ref,
            run_id=selected_run_id,
            run_dir=tmp_path / selected_run_id / "run",
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
            workflow_id=str(initial_state.params.get("workflow_id", "scientist_default")),
            nodes=[
                NodeInvocation(
                    alias="controlled_fan_out",
                    node_id=str(fan_out.spec.metadata.component_id),
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
        with async_tools.capture_shared_executor_observations() as dispatch_collector:
            result = asyncio.run(
                AsyncWorkflowExecutor(context, registry, max_parallelism=1).execute(
                    spec, initial_state
                )
            )
        dispatch_observations[selected_run_id] = dispatch_collector.snapshot()
        dispatch_results[selected_run_id] = result
        artifact_stores[selected_run_id] = store
        return result

    monkeypatch.setattr(builder, "run_selected_workflow", controlled_dispatch)
    if forged_shim:
        original = async_tools.run_blocking_async
        common_module = async_tools
        binding = _dependent_binding(REPO_ROOT, binding_id)
        callsite, _, _ = _resolve_operation_reference(REPO_ROOT, binding["callsite_operation"])
        callsite_code = _operation_code(binding["callsite_operation"], callsite)
        executor = async_tools.get_shared_executor()
        profile = async_tools.get_shared_executor_profile()
        caller_source_sha256 = hashlib.sha256(
            Path(_operation_code(binding["callsite_operation"], callsite).co_filename).read_bytes()
        ).hexdigest()

        async def shim(func, *args, **kwargs):
            caller = sys._getframe(1)
            if caller.f_code is not callsite_code:
                raise AssertionError("forged_shim_callsite_changed")

            def run_elsewhere():
                return func(*args, **kwargs), threading.get_ident()

            value, worker_ident = await asyncio.to_thread(run_elsewhere)
            trace.get_current_span().add_event(
                common_module.SHARED_EXECUTOR_CALL_EVENT_NAME,
                {
                    "call_id": uuid.uuid4().hex,
                    "helper_module": binding["shared_operation"]["module"],
                    "helper_code_object_id": hex(id(original.__code__)),
                    "helper_source_sha256": hashlib.sha256(
                        Path(common_module.__file__).read_bytes()
                    ).hexdigest(),
                    "caller_module": callsite.__module__,
                    "caller_code_object_id": hex(id(caller.f_code)),
                    "caller_source_sha256": caller_source_sha256,
                    "profile_revision": profile.revision,
                    "profile_capacity": profile.capacity,
                    "profile_queue_capacity": profile.queue_capacity,
                    "executor_capacity": executor._max_workers,
                    "executor_queue_capacity": executor._max_queued,
                    "worker_thread_ident": worker_ident,
                    "worker_is_executor": True,
                    "status": "success",
                },
            )
            return value

        shim.__name__ = original.__name__
        shim.__qualname__ = original.__qualname__
        monkeypatch.setattr(fan_out_module, "run_blocking_async", shim)
    else:
        monkeypatch.setattr(
            fan_out_module,
            "run_blocking_async",
            async_tools.run_blocking_async,
        )

    metrics_before = reader.get_metrics_data()
    with async_tools.capture_shared_executor_observations() as collector:
        state = run_experiment(
            {
                "run_id": run_id,
                "params": {
                    "workflow_id": "scientist_default",
                    "items": list(items) if items is not None else [item],
                },
            },
            tracer=tracer,
            metrics=metrics,
        )
    observed_by_call_id = {item.call_id: item for item in collector.snapshot()}
    for captured in dispatch_observations.values():
        observed_by_call_id.update((item.call_id, item) for item in captured)
    observations = tuple(observed_by_call_id.values())
    selected_observations = dispatch_observations[run_id]
    result = dispatch_results[run_id]
    store = artifact_stores[run_id]
    receipt_path = tmp_path / f"{run_id}-dependent-execution.json"
    receipt_path.write_text(
        json.dumps(
            _receipt(
                binding_id=binding_id,
                run_state=state,
                run_ref=result.run_ref,
                observations=selected_observations,
                report_status=result.report.status,
            ),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        "state": state,
        "binding_id": binding_id,
        "result": result,
        "store": store,
        "run_ref": result.run_ref,
        "receipt_path": receipt_path,
        "observations": observations,
        "selected_observations": selected_observations,
        "nested_other_api_root": nested_other_api_root,
        "reader": reader,
        "metrics_before": dispatch_metric_baselines.get(run_id, metrics_before),
        "metrics": metrics,
        "span_exporter": span_exporter,
        "trace_provider": trace_provider,
        "meter_provider": meter_provider,
        "consumer": run_experiment,
    }


@pytest.mark.parametrize("environment", ["test", "staging"])
def test_controlled_dependent_coverage_recomputes_actual_runtime_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
) -> None:
    success = _run_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id=f"dependent-success-{environment}",
        item="ok",
        environment=environment,
    )
    try:
        verified = verify_controlled_dependent_execution(
            REPO_ROOT,
            binding_id=success["binding_id"],
            receipt_path=success["receipt_path"],
            observations=success["observations"],
            span_exporter=success["span_exporter"],
            metric_reader=success["reader"],
            metrics_registry=success["metrics"],
            metrics_before=success["metrics_before"],
            consumer_operation=success["consumer"],
            run_state=success["state"],
            run_ref=success["run_ref"],
            artifact_store=success["store"],
            expected_environment=environment,
        )
        assert verified["status"] == "controlled_witness_verified"
        assert verified["runtime_admission"] == "not_established"

        binding = __import__(
            "tools.ops_runners.release.check_operability_release_gates",
            fromlist=["_dependent_binding"],
        )._dependent_binding(REPO_ROOT, success["binding_id"])
        callsite, _, _ = __import__(
            "tools.ops_runners.release.check_operability_release_gates",
            fromlist=["_resolve_operation_reference"],
        )._resolve_operation_reference(REPO_ROOT, binding["callsite_operation"])
        callsite_code = _operation_code(binding["callsite_operation"], callsite)
        observation = next(
            item for item in success["observations"] if item.caller_code is callsite_code
        )

        mutated = dict(json.loads(success["receipt_path"].read_text(encoding="utf-8")))
        mutated["schema_version"] = "9.9"
        bad = tmp_path / "wrong-schema.json"
        bad.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(
            ValueError, match="controlled_receipt_does_not_match_recomputed_sources"
        ):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=bad,
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )

        mutated = dict(json.loads(success["receipt_path"].read_text(encoding="utf-8")))
        mutated["objective_names"] = ["invented-objective"]
        bad.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="recomputed"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=bad,
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )

        mutated = dict(json.loads(success["receipt_path"].read_text(encoding="utf-8")))
        mutated["counter_count"] = 99
        bad.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="recomputed"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=bad,
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )
        mutated["unverified_status"] = "covered"
        bad.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="schema"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=bad,
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )

        mutated = dict(json.loads(success["receipt_path"].read_text(encoding="utf-8")))
        mutated["helper_source_sha256"] = "0" * 64
        bad.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="recomputed"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=bad,
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )

        bad_observation = replace(observation, source_sha256="0" * 64)
        with pytest.raises(ValueError, match="identity"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=success["receipt_path"],
                observations=tuple(
                    bad_observation if item is observation else item
                    for item in success["observations"]
                ),
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )
        wrong_profile = replace(observation, profile=replace(observation.profile))
        with pytest.raises(ValueError, match="profile"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=success["receipt_path"],
                observations=tuple(
                    wrong_profile if item is observation else item
                    for item in success["observations"]
                ),
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )
        with pytest.raises(ValueError, match="environment"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=success["receipt_path"],
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=success["reader"],
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment="wrong-environment",
            )

        missing = InMemoryMetricReader()
        with pytest.raises(ValueError, match="observation"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=success["receipt_path"],
                observations=success["observations"],
                span_exporter=success["span_exporter"],
                metric_reader=missing,
                metrics_registry=success["metrics"],
                metrics_before=success["metrics_before"],
                consumer_operation=success["consumer"],
                run_state=success["state"],
                run_ref=success["run_ref"],
                artifact_store=success["store"],
                expected_environment=environment,
            )

        failure = _run_case(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            run_id=f"dependent-failure-{environment}",
            item="explode",
            environment=environment,
        )
        try:
            verified_failure = verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=success["binding_id"],
                receipt_path=failure["receipt_path"],
                observations=failure["observations"],
                span_exporter=failure["span_exporter"],
                metric_reader=failure["reader"],
                metrics_registry=failure["metrics"],
                metrics_before=failure["metrics_before"],
                consumer_operation=failure["consumer"],
                run_state=failure["state"],
                run_ref=failure["run_ref"],
                artifact_store=failure["store"],
                expected_environment=environment,
            )
            assert verified_failure["status"] == "controlled_witness_verified"
            assert verified_failure["run_id"] == failure["state"]["run_id"]
            mutated = dict(json.loads(failure["receipt_path"].read_text(encoding="utf-8")))
            mutated["metric_status"] = "success"
            bad.write_text(json.dumps(mutated), encoding="utf-8")
            with pytest.raises(ValueError, match="recomputed"):
                verify_controlled_dependent_execution(
                    REPO_ROOT,
                    binding_id=success["binding_id"],
                    receipt_path=bad,
                    observations=failure["observations"],
                    span_exporter=failure["span_exporter"],
                    metric_reader=failure["reader"],
                    metrics_registry=failure["metrics"],
                    metrics_before=failure["metrics_before"],
                    consumer_operation=failure["consumer"],
                    run_state=failure["state"],
                    run_ref=failure["run_ref"],
                    artifact_store=failure["store"],
                    expected_environment=environment,
                )
        finally:
            failure["trace_provider"].shutdown()
            failure["meter_provider"].shutdown()

        forged = _run_case(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            run_id=f"dependent-forged-span-{environment}",
            item="ok",
            environment=environment,
            forged_shim=True,
        )
        try:
            assert any(
                span.name == "experiment.workflow"
                for span in forged["span_exporter"].get_finished_spans()
            )
            with pytest.raises(ValueError, match="observation|callsite|bijective"):
                verify_controlled_dependent_execution(
                    REPO_ROOT,
                    binding_id=success["binding_id"],
                    receipt_path=forged["receipt_path"],
                    observations=forged["observations"],
                    span_exporter=forged["span_exporter"],
                    metric_reader=forged["reader"],
                    metrics_registry=forged["metrics"],
                    metrics_before=forged["metrics_before"],
                    consumer_operation=forged["consumer"],
                    run_state=forged["state"],
                    run_ref=forged["run_ref"],
                    artifact_store=forged["store"],
                    expected_environment=environment,
                )
        finally:
            forged["trace_provider"].shutdown()
            forged["meter_provider"].shutdown()
    finally:
        success["trace_provider"].shutdown()
        success["meter_provider"].shutdown()


def test_multiple_common_calls_on_one_api_root_span_reconcile_events_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _run_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id="dependent-multiple-items",
        item="unused-single-item",
        items=("ok-first", "ok-second"),
        environment="test",
    )
    try:
        binding = _dependent_binding(REPO_ROOT, case["binding_id"])
        callsite, _, callsite_source = _resolve_operation_reference(
            REPO_ROOT, binding["callsite_operation"]
        )
        code = _operation_code(binding["callsite_operation"], callsite)
        observations = [item for item in case["observations"] if item.caller_code is code]
        assert len(observations) == 2
        span_keys = {(item.trace_id, item.span_id) for item in observations}
        assert len(span_keys) == 1
        assert all(item.profile is observations[0].profile for item in observations)

        span_key = next(iter(span_keys))
        spans = tuple(case["span_exporter"].get_finished_spans())
        target = next(
            span for span in spans if (span.context.trace_id, span.context.span_id) == span_key
        )
        assert target.name == binding["trace"]["api_span_name"]
        api_root_attributes = dict(target.attributes or {})
        assert (
            api_root_attributes[binding["trace"]["api_run_id_attribute"]] == case["state"]["run_id"]
        )
        assert (
            api_root_attributes[binding["trace"]["api_workflow_id_attribute"]]
            == case["result"].report.workflow_id
        )
        call_events = tuple(
            event for event in target.events if event.name == binding["trace"]["event_name"]
        )
        observations_by_id = {
            item.call_id: item
            for item in case["observations"]
            if (item.trace_id, item.span_id) == span_key
        }
        event_ids = [str(dict(event.attributes or {}).get("call_id", "")) for event in call_events]
        assert len(event_ids) == len(set(event_ids))
        assert set(event_ids) == set(observations_by_id)
        selected_event_ids: set[str] = set()
        proven_other_event_ids: set[str] = set()
        expected_callsite_sha256 = hashlib.sha256(callsite_source.read_bytes()).hexdigest()
        for event in call_events:
            attributes = dict(event.attributes or {})
            call_id = str(attributes.get("call_id", ""))
            observed = observations_by_id[call_id]
            caller_source = Path(observed.caller_source_path).resolve(strict=True)
            assert caller_source == Path(observed.caller_code.co_filename).resolve(strict=True)
            assert (
                hashlib.sha256(caller_source.read_bytes()).hexdigest()
                == observed.caller_source_sha256
            )
            assert attributes.get("caller_module") == observed.caller_module
            assert attributes.get("caller_code_object_id") == hex(id(observed.caller_code))
            assert attributes.get("caller_source_sha256") == observed.caller_source_sha256
            assert attributes.get("helper_module") == observed.helper_function.__module__
            assert attributes.get("helper_code_object_id") == hex(id(observed.helper_code))
            assert attributes.get("helper_source_sha256") == observed.source_sha256
            assert attributes.get("profile_revision") == observed.profile.revision
            assert attributes.get("profile_capacity") == observed.profile.capacity
            assert attributes.get("profile_queue_capacity") == observed.profile.queue_capacity
            assert attributes.get("worker_thread_ident") == observed.worker_thread_ident
            assert attributes.get("worker_is_executor") is observed.worker_is_executor is True
            assert attributes.get("status") == observed.status
            if observed.caller_code is code:
                assert observed.caller_module == callsite.__module__
                assert observed.caller_source_sha256 == expected_callsite_sha256
                selected_event_ids.add(call_id)
            else:
                assert observed.caller_code is not code
                assert (
                    observed.caller_source_sha256 != expected_callsite_sha256
                    or observed.caller_module != callsite.__module__
                )
                proven_other_event_ids.add(call_id)
        assert selected_event_ids == {item.call_id for item in observations}
        assert proven_other_event_ids == set(observations_by_id) - selected_event_ids
        assert proven_other_event_ids

        def verify(exporter: Any = case["span_exporter"]) -> dict[str, Any]:
            return verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=case["binding_id"],
                receipt_path=case["receipt_path"],
                observations=case["observations"],
                span_exporter=exporter,
                metric_reader=case["reader"],
                metrics_registry=case["metrics"],
                metrics_before=case["metrics_before"],
                consumer_operation=case["consumer"],
                run_state=case["state"],
                run_ref=case["run_ref"],
                artifact_store=case["store"],
                expected_environment="test",
            )

        verified = verify()
        assert verified["status"] == "controlled_witness_verified"
        assert verified["call_count"] == 2

        root_run_attribute = binding["trace"]["api_run_id_attribute"]
        root_workflow_attribute = binding["trace"]["api_workflow_id_attribute"]
        api_root = next(
            span
            for span in spans
            if span.name == binding["trace"]["api_span_name"]
            and span.context.trace_id == span_key[0]
            and str(dict(span.attributes or {}).get(root_run_attribute, ""))
            == case["state"]["run_id"]
            and str(dict(span.attributes or {}).get(root_workflow_attribute, ""))
            == case["result"].report.workflow_id
        )
        second_root_span_id = 1
        while any(
            span.context.trace_id == api_root.context.trace_id
            and span.context.span_id == second_root_span_id
            for span in spans
        ):
            second_root_span_id += 1
        second_root_context = SpanContext(
            trace_id=api_root.context.trace_id,
            span_id=second_root_span_id,
            is_remote=False,
            trace_flags=api_root.context.trace_flags,
            trace_state=api_root.context.trace_state,
        )
        second_root = _span_with_parent(api_root, None, events=(), context=second_root_context)
        assert verify(_FinishedSpanSnapshot((*spans, second_root)))["call_count"] == 2

        missing_span = _span_with_parent(
            target,
            target.parent,
            events=tuple(
                event
                for event in target.events
                if all(event is not call_event for call_event in call_events)
            ),
        )
        missing_spans = tuple(missing_span if span is target else span for span in spans)
        with pytest.raises(ValueError, match="span_events_and_live_calls_not_bijective"):
            verify(_FinishedSpanSnapshot(missing_spans))

        selected_call_event = next(
            event
            for event in call_events
            if str(dict(event.attributes or {}).get("call_id", "")) in selected_event_ids
        )
        occupied_span_ids = {
            span.context.span_id
            for span in spans
            if span.context.trace_id == api_root.context.trace_id
        }
        wrong_span_id = 1
        while wrong_span_id in occupied_span_ids:
            wrong_span_id += 1
        wrong_span_context = SpanContext(
            trace_id=api_root.context.trace_id,
            span_id=wrong_span_id,
            is_remote=False,
            trace_flags=api_root.context.trace_flags,
            trace_state=api_root.context.trace_state,
        )
        synthetic_wrong_span = _span_with_parent(
            api_root,
            api_root.context,
            events=(selected_call_event,),
            context=wrong_span_context,
            attributes={},
            name="polisyos.common.call_wrong_span_control",
        )
        with pytest.raises(ValueError, match="common_call_event_attached_to_wrong_span"):
            verify(_FinishedSpanSnapshot((*spans, synthetic_wrong_span)))

        selected_call_events = tuple(
            event
            for event in call_events
            if str(dict(event.attributes or {}).get("call_id", "")) in selected_event_ids
        )
        assert len(selected_call_events) == len(selected_event_ids) == 2
        insertion_index = len(call_events) // 2
        interleaved_events = (
            *call_events[:insertion_index],
            SimpleNamespace(name="unrelated-workflow-event", attributes={}),
            *call_events[insertion_index:],
        )
        interleaved_span = _span_with_parent(target, target.parent, events=interleaved_events)
        interleaved_spans = tuple(interleaved_span if span is target else span for span in spans)
        assert verify(_FinishedSpanSnapshot(interleaved_spans))["call_count"] == 2

        duplicate_events = (*interleaved_events, selected_call_events[0])
        duplicate_span = _span_with_parent(target, target.parent, events=duplicate_events)
        duplicate_spans = tuple(duplicate_span if span is target else span for span in spans)
        with pytest.raises(ValueError, match="duplicate_actual_common_call_event"):
            verify(_FinishedSpanSnapshot(duplicate_spans))
    finally:
        case["trace_provider"].shutdown()
        case["meter_provider"].shutdown()


def test_call_event_join_uses_selected_api_root_ancestry_truth_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _run_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id="dependent-root-ancestry-matrix",
        item="ok",
        environment="test",
        nested_other_api_root=True,
    )
    try:
        binding = _dependent_binding(REPO_ROOT, case["binding_id"])
        spans = tuple(case["span_exporter"].get_finished_spans())
        callsite, _, _ = _resolve_operation_reference(REPO_ROOT, binding["callsite_operation"])
        callsite_code = _operation_code(binding["callsite_operation"], callsite)
        api_span_name = str(binding["trace"]["api_span_name"])
        selected_run = str(case["state"]["run_id"])
        selected_workflow = str(case["result"].report.workflow_id)
        root_run_attribute = str(binding["trace"]["api_run_id_attribute"])
        root_workflow_attribute = str(binding["trace"]["api_workflow_id_attribute"])

        def root_for_observation(item: Any) -> Any:
            target_span = next(
                span
                for span in spans
                if (span.context.trace_id, span.context.span_id) == (item.trace_id, item.span_id)
            )
            root_id = _ancestor_root_id(target_span, spans, api_span_name)
            return next(
                span
                for span in spans
                if span.context.trace_id == item.trace_id and span.context.span_id == root_id
            )

        observation = next(
            item
            for item in case["observations"]
            if item.caller_code is callsite_code
            and str(dict(root_for_observation(item).attributes or {}).get(root_run_attribute, ""))
            == selected_run
            and str(
                dict(root_for_observation(item).attributes or {}).get(root_workflow_attribute, "")
            )
            == selected_workflow
        )
        other_observation = next(
            item
            for item in case["observations"]
            if item.caller_code is callsite_code
            and str(dict(root_for_observation(item).attributes or {}).get(root_run_attribute, ""))
            == f"{selected_run}-other-api-root"
        )
        selected_root = root_for_observation(observation)
        other_root = root_for_observation(other_observation)
        assert selected_root.context.trace_id == other_root.context.trace_id
        assert selected_root.context.span_id != other_root.context.span_id
        other_span = next(
            span
            for span in spans
            if (span.context.trace_id, span.context.span_id)
            == (other_observation.trace_id, other_observation.span_id)
        )
        assert any(
            event.name == binding["trace"]["event_name"]
            and str(dict(event.attributes or {}).get("call_id")) == other_observation.call_id
            for event in other_span.events
        )
        target = next(
            span
            for span in spans
            if (span.context.trace_id, span.context.span_id)
            == (observation.trace_id, observation.span_id)
        )
        call_event = next(
            event
            for event in target.events
            if event.name == binding["trace"]["event_name"]
            and str(dict(event.attributes or {}).get("call_id")) == observation.call_id
        )
        selected_root = root_for_observation(observation)
        selected_trace_id = selected_root.context.trace_id
        root_attributes = dict(selected_root.attributes or {})
        other_run = f"{selected_run}-unselected-root"
        other_workflow = f"{selected_workflow}-unselected-root"
        next_span_id = [1]
        occupied = {(span.context.trace_id, span.context.span_id) for span in spans}

        def new_context(trace_id: int, *, remote: bool = False) -> SpanContext:
            while (trace_id, next_span_id[0]) in occupied:
                next_span_id[0] += 1
            span_id = next_span_id[0]
            next_span_id[0] += 1
            occupied.add((trace_id, span_id))
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                is_remote=remote,
                trace_flags=selected_root.context.trace_flags,
                trace_state=selected_root.context.trace_state,
            )

        def verify_snapshot(
            snapshot: tuple[Any, ...],
            observation_rows: tuple[Any, ...] | None = None,
        ) -> dict[str, Any]:
            return verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=case["binding_id"],
                receipt_path=case["receipt_path"],
                observations=case["observations"] if observation_rows is None else observation_rows,
                span_exporter=_FinishedSpanSnapshot(snapshot),
                metric_reader=case["reader"],
                metrics_registry=case["metrics"],
                metrics_before=case["metrics_before"],
                consumer_operation=case["consumer"],
                run_state=case["state"],
                run_ref=case["run_ref"],
                artifact_store=case["store"],
                expected_environment="test",
            )

        def event_with_call_id(call_id: str) -> Any:
            attributes = dict(call_event.attributes or {})
            attributes["call_id"] = call_id
            return SimpleNamespace(name=call_event.name, attributes=attributes)

        root_trace_cases = (
            ("selected", "same"),
            ("selected", "other"),
            ("other", "same"),
            ("other", "other"),
        )
        parent_cases = ("valid", "missing", "cycle")
        assert str(dict(other_root.attributes or {}).get(root_run_attribute, "")) != selected_run
        other_trace_id = (
            selected_trace_id + 1 if selected_trace_id < (1 << 128) - 1 else selected_trace_id - 1
        )

        def root_for_case(
            root_relation: str, trace_relation: str
        ) -> tuple[Any, tuple[Any, ...], int]:
            trace_id = selected_trace_id if trace_relation == "same" else other_trace_id
            template = selected_root if root_relation == "selected" else other_root
            if trace_relation == "same":
                root = template
                root_rows: tuple[Any, ...] = ()
            else:
                root = _span_with_parent(
                    template,
                    None,
                    events=(),
                    context=new_context(trace_id),
                    attributes=dict(template.attributes or {}),
                    name=api_span_name,
                )
                root_rows = (root,)
            assert root.context.trace_id == trace_id
            return root, root_rows, trace_id

        ancestry_cases = 0
        for root_relation, trace_relation in root_trace_cases:
            root, root_rows, trace_id = root_for_case(root_relation, trace_relation)
            for parent_case in parent_cases:
                child_context = new_context(trace_id)
                if parent_case == "valid":
                    parent = root.context
                elif parent_case == "missing":
                    parent = new_context(trace_id, remote=True)
                else:
                    parent = child_context
                event = event_with_call_id(
                    f"unobserved-{root_relation}-{trace_relation}-{parent_case}"
                )
                synthetic_span = _span_with_parent(
                    target,
                    parent,
                    context=child_context,
                    attributes={},
                    events=(event,),
                    name="polisyos.common.call_ancestry_control",
                )
                rows = (*spans, *root_rows, synthetic_span)

                expected_error: str | None = None
                if root_relation == "selected":
                    expected_error = (
                        "unobserved_common_call_event"
                        if parent_case == "valid"
                        else "api_root_parent"
                    )
                elif trace_relation == "same" and parent_case != "valid":
                    expected_error = "api_root_parent"

                if expected_error is None:
                    assert verify_snapshot(rows)["status"] == "controlled_witness_verified"
                else:
                    with pytest.raises(ValueError, match=expected_error):
                        verify_snapshot(rows)
                ancestry_cases += 1

        wrong_span_cases = 0
        for root_relation, trace_relation in root_trace_cases:
            root, root_rows, trace_id = root_for_case(root_relation, trace_relation)
            wrong_span = _span_with_parent(
                target,
                root.context,
                context=new_context(trace_id),
                attributes={},
                events=(call_event,),
                name="polisyos.common.call_wrong_span_control",
            )
            with pytest.raises(ValueError, match="common_call_event_attached_to_wrong_span"):
                verify_snapshot((*spans, *root_rows, wrong_span))
            wrong_span_cases += 1

        duplicate_target = _span_with_parent(
            target,
            target.parent,
            events=(*target.events, call_event),
        )
        duplicate_snapshot = tuple(duplicate_target if span is target else span for span in spans)
        with pytest.raises(ValueError, match="duplicate_actual_common_call_event"):
            verify_snapshot(duplicate_snapshot)
        duplicate_controls = 1
        assert ancestry_cases == len(root_trace_cases) * len(parent_cases)
        assert wrong_span_cases == len(root_trace_cases)

        unrelated_trace_id = (
            selected_trace_id + 2 if selected_trace_id < (1 << 128) - 2 else selected_trace_id - 2
        )
        unrelated_context = new_context(unrelated_trace_id)
        additional_ancestry_controls = 0
        unrelated_duplicate = _span_with_parent(
            target, None, context=unrelated_context, attributes={}, events=()
        )
        assert (
            verify_snapshot((*spans, unrelated_duplicate, unrelated_duplicate))["call_count"] == 1
        )
        additional_ancestry_controls += 1

        proven_other_attributes = dict(other_root.attributes or {})
        assert (
            str(proven_other_attributes.get(root_run_attribute, "")) != selected_run
            or str(proven_other_attributes.get(root_workflow_attribute, "")) != selected_workflow
        )
        proven_other_event = event_with_call_id("unobserved-proven-other-api-root")
        assert str(dict(proven_other_event.attributes or {}).get("call_id", "")) not in {
            item.call_id for item in case["observations"]
        }
        proven_other_event_span = _span_with_parent(
            target,
            other_root.context,
            context=new_context(selected_trace_id),
            attributes={},
            events=(proven_other_event,),
            name="polisyos.common.call_proven_other_root_control",
        )
        assert verify_snapshot((*spans, proven_other_event_span))["call_count"] == 1
        additional_ancestry_controls += 1

        with pytest.raises(ValueError, match="selected_api_root_identity_ambiguous"):
            verify_snapshot((*spans, target))
        additional_ancestry_controls += 1

        unknown_event_root = _span_with_parent(
            selected_root,
            None,
            context=new_context(selected_trace_id),
            events=(event_with_call_id("unobserved-unknown-api-root"),),
            attributes={},
        )
        with pytest.raises(ValueError, match="api_root_membership_not_established"):
            verify_snapshot((*spans, unknown_event_root))
        additional_ancestry_controls += 1

        unknown_observation_root = _span_with_parent(
            selected_root,
            None,
            context=new_context(selected_trace_id),
            events=(),
            attributes={},
        )
        unknown_observation_context = new_context(selected_trace_id)
        target_events_without_observation = tuple(
            event
            for event in target.events
            if str(dict(event.attributes or {}).get("call_id", "")) != observation.call_id
        )
        target_without_observation_event = _span_with_parent(
            target,
            target.parent,
            events=target_events_without_observation,
        )
        unknown_observation_span_attributes = {
            str(binding["trace"]["node_run_id_attribute"]): selected_run,
            str(binding["trace"]["node_workflow_id_attribute"]): selected_workflow,
        }
        unknown_observation_span = _span_with_parent(
            target,
            unknown_observation_root.context,
            context=unknown_observation_context,
            events=(call_event,),
            attributes=unknown_observation_span_attributes,
            name="polisyos.common.call_ancestry_control",
        )
        unknown_root_attributes = dict(unknown_observation_root.attributes or {})
        assert unknown_observation_root.name == api_span_name
        assert unknown_observation_root.context.trace_id == selected_trace_id
        assert unknown_observation_root.context.span_id != selected_root.context.span_id
        assert root_run_attribute not in unknown_root_attributes
        assert root_workflow_attribute not in unknown_root_attributes
        assert unknown_observation_span.name != api_span_name
        assert unknown_observation_span.context.trace_id == selected_trace_id
        assert unknown_observation_span.parent == unknown_observation_root.context
        assert (
            unknown_observation_span_attributes[str(binding["trace"]["node_run_id_attribute"])]
            == selected_run
        )
        assert (
            unknown_observation_span_attributes[str(binding["trace"]["node_workflow_id_attribute"])]
            == selected_workflow
        )
        unknown_observation_snapshot = (
            *(target_without_observation_event if span is target else span for span in spans),
            unknown_observation_root,
            unknown_observation_span,
        )
        unknown_root_observations = tuple(
            replace(item, span_id=unknown_observation_context.span_id)
            if item is observation
            else item
            for item in case["observations"]
        )
        with pytest.raises(ValueError, match="api_root_membership_not_established"):
            verify_snapshot(unknown_observation_snapshot, unknown_root_observations)
        additional_ancestry_controls += 1
        assert additional_ancestry_controls == 5
        assert (
            ancestry_cases + wrong_span_cases + duplicate_controls + additional_ancestry_controls
            == len(root_trace_cases) * len(parent_cases)
            + len(root_trace_cases)
            + 1
            + additional_ancestry_controls
        )
    finally:
        case["trace_provider"].shutdown()
        case["meter_provider"].shutdown()


def _ancestor_root_id(span: Any, spans: tuple[Any, ...], root_name: str) -> int:
    by_context = {(item.context.trace_id, item.context.span_id): item for item in spans}
    current = span
    visited: set[tuple[int, int]] = set()
    while True:
        key = (current.context.trace_id, current.context.span_id)
        if key in visited:
            raise AssertionError("fixture parent cycle")
        visited.add(key)
        if current.name == root_name:
            return current.context.span_id
        parent = current.parent
        if parent is None:
            raise AssertionError("fixture API root not found")
        current = by_context[(parent.trace_id, parent.span_id)]


class _FinishedSpanSnapshot:
    def __init__(self, spans: tuple[Any, ...]) -> None:
        self._spans = spans

    def get_finished_spans(self) -> tuple[Any, ...]:
        return self._spans


def _span_with_parent(
    span: Any,
    parent: Any,
    *,
    events: tuple[Any, ...] | None = None,
    context: Any | None = None,
    attributes: dict[str, Any] | None = None,
    name: str | None = None,
) -> ReadableSpan:
    return ReadableSpan(
        name=span.name if name is None else name,
        context=span.context if context is None else context,
        parent=parent,
        resource=span.resource,
        attributes=span.attributes if attributes is None else attributes,
        events=span.events if events is None else events,
        links=span.links,
        kind=span.kind,
        instrumentation_info=getattr(span, "instrumentation_info", None),
        status=span.status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=getattr(span, "instrumentation_scope", None),
    )


@pytest.mark.asyncio
async def test_shared_call_reflection_is_skipped_without_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_reflection(_func: Any) -> None:
        raise AssertionError("uncaptured call performed target reflection")

    monkeypatch.setattr(async_tools, "_observed_target_function", fail_reflection)
    assert await async_tools.run_blocking_async(lambda: "ordinary-call") == "ordinary-call"


def test_dependent_binding_graph_rejects_cycles() -> None:
    contracts = _package_contracts(REPO_ROOT)
    rows = _binding_rows(contracts)
    assert validate_dependent_binding_graph(rows) == []
    cycle_binding = {
        "dependent_package": "common",
    }
    assert validate_dependent_binding_graph(
        [*rows, ("scientist", contracts["scientist"][1], cycle_binding)]
    )


@pytest.mark.parametrize("parent_case", ["detached", "missing", "cycle"])
def test_unobserved_common_call_event_requires_api_root_parentage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parent_case: str,
) -> None:
    case = _run_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        run_id=f"parentage-{parent_case}",
        item="ok",
        environment="test",
    )
    try:
        binding = _dependent_binding(REPO_ROOT, case["binding_id"])
        callsite, _, _ = _resolve_operation_reference(REPO_ROOT, binding["callsite_operation"])
        code = _operation_code(binding["callsite_operation"], callsite)
        observation = next(item for item in case["observations"] if item.caller_code is code)
        spans = tuple(case["span_exporter"].get_finished_spans())
        key = (observation.trace_id, observation.span_id)
        target = next(
            span for span in spans if (span.context.trace_id, span.context.span_id) == key
        )
        api_span_name = str(binding["trace"]["api_span_name"])
        api_run_attribute = str(binding["trace"]["api_run_id_attribute"])
        api_workflow_attribute = str(binding["trace"]["api_workflow_id_attribute"])
        selected_workflow = str(case["result"].report.workflow_id)
        api_root = next(
            span
            for span in spans
            if span.name == api_span_name
            and str(dict(span.attributes or {}).get(api_run_attribute, ""))
            == case["state"]["run_id"]
            and str(dict(span.attributes or {}).get(api_workflow_attribute, ""))
            == selected_workflow
        )
        assert _ancestor_root_id(target, spans, api_span_name) == api_root.context.span_id
        event = next(
            event
            for event in target.events
            if event.name == binding["trace"]["event_name"]
            and str(dict(event.attributes or {}).get("call_id")) == observation.call_id
        )
        event_attributes = dict(event.attributes or {})
        event_attributes["call_id"] = f"unobserved-parentage-{parent_case}"
        malformed_event = SimpleNamespace(name=event.name, attributes=event_attributes)
        occupied = {
            (span.context.trace_id, span.context.span_id) for span in spans if span.context.is_valid
        }
        next_span_id = 1

        def fresh_context(*, remote: bool = False) -> SpanContext:
            nonlocal next_span_id
            while (target.context.trace_id, next_span_id) in occupied:
                next_span_id += 1
            span_id = next_span_id
            next_span_id += 1
            occupied.add((target.context.trace_id, span_id))
            return SpanContext(
                trace_id=target.context.trace_id,
                span_id=span_id,
                is_remote=remote,
                trace_flags=target.context.trace_flags,
                trace_state=target.context.trace_state,
            )

        child_context = fresh_context()
        if parent_case == "detached":
            parent = None
        elif parent_case == "cycle":
            parent = child_context
        else:
            parent = fresh_context(remote=True)
        malformed_child = _span_with_parent(
            target,
            parent,
            context=child_context,
            events=(malformed_event,),
            attributes={},
            name="polisyos.common.call_parentage_control",
        )
        altered = (*spans, malformed_child)
        with pytest.raises(ValueError, match="api_root_parent"):
            verify_controlled_dependent_execution(
                REPO_ROOT,
                binding_id=case["binding_id"],
                receipt_path=case["receipt_path"],
                observations=case["observations"],
                span_exporter=_FinishedSpanSnapshot(altered),
                metric_reader=case["reader"],
                metrics_registry=case["metrics"],
                metrics_before=case["metrics_before"],
                consumer_operation=case["consumer"],
                run_state=case["state"],
                run_ref=case["run_ref"],
                artifact_store=case["store"],
                expected_environment="test",
            )
    finally:
        case["trace_provider"].shutdown()
        case["meter_provider"].shutdown()


def test_binding_operation_roles_follow_declared_package_owners() -> None:
    contracts = _package_contracts(REPO_ROOT)
    rows = _binding_rows(contracts)
    owner, _, binding = next(
        row for row in rows if row[2].get("id") == "common-scientist-api-fanout"
    )
    mutated = json.loads(json.dumps(binding))
    mutated["callsite_operation"]["package"] = owner
    assert _binding_package_role_errors(owner, mutated, contracts)


def test_objective_resolution_rejects_markers_duplicates_and_runbook_drift(
    tmp_path: Path,
) -> None:
    import yaml

    binding = _dependent_binding(REPO_ROOT, "common-scientist-api-fanout")
    dependent = _package_contracts(REPO_ROOT)[str(binding["dependent_package"])][1]
    relative_slo = binding["objective"][0]["path"]
    source_path = REPO_ROOT / relative_slo
    source = source_path.read_text(encoding="utf-8")

    def call_on(document: str, root_name: str = "fixture") -> None:
        root = tmp_path / root_name
        path = root / relative_slo
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
        _objective_instrument_contract(
            root,
            [binding["objective"][0]],
            dependent_contract=dependent,
            binding_runbooks=binding["runbook_paths"],
        )

    parsed = yaml.safe_load(source)
    selected = next(
        row for row in parsed["objectives"] if row["name"] == binding["objective"][0]["name"]
    )
    selected["sli"] = '# polisyos_fake_total{measurement_scope="scientist_api"}'
    selected["runbook_note"] = binding["objective"][0]["runbook_path"]
    with pytest.raises(ValueError, match="objective_sli_has_no_supported_metric_selectors"):
        call_on(yaml.safe_dump(parsed), "comment-marker")

    parsed = yaml.safe_load(source)
    selected = next(
        row for row in parsed["objectives"] if row["name"] == binding["objective"][0]["name"]
    )
    selected["runbook_note"] = binding["objective"][0]["runbook_path"]
    selected["runbook"] = "docs/runbooks/not-the-bound-runbook.md"
    with pytest.raises(ValueError, match="objective_runbook_not_exactly_bound"):
        call_on(yaml.safe_dump(parsed), "runbook-drift")

    parsed = yaml.safe_load(source)
    parsed["objectives"].append(dict(parsed["objectives"][0]))
    with pytest.raises(ValueError, match="objective_name_ambiguous"):
        call_on(yaml.safe_dump(parsed), "duplicate-name")

    duplicate_field = source.replace(
        "    runbook: docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md",
        "    runbook: docs/runbooks/incorrect.md\n"
        "    runbook: docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md",
        1,
    )
    with pytest.raises(ValueError, match="slo_yaml_not_unambiguous"):
        call_on(duplicate_field, "duplicate-field")


def test_scientist_api_p99_runbook_binds_actual_sli_alert_panel_and_actions() -> None:
    import yaml

    binding = _dependent_binding(REPO_ROOT, "common-scientist-api-fanout")
    objective_ref = next(
        item for item in binding["objective"] if item["name"] == "scientist_p99_duration"
    )
    objective_doc = yaml.safe_load((REPO_ROOT / objective_ref["path"]).read_text(encoding="utf-8"))
    objective = next(
        item for item in objective_doc["objectives"] if item["name"] == objective_ref["name"]
    )
    assert objective["runbook"] == objective_ref["runbook_path"]
    assert 'measurement_scope="scientist_api"' in objective["sli"]
    runbook = (REPO_ROOT / objective["runbook"]).read_text(encoding="utf-8")
    alert_doc = yaml.safe_load(
        (REPO_ROOT / "ops/observability/prometheus/slo_alerts.yml").read_text(encoding="utf-8")
    )
    alerts = [rule for group in alert_doc["groups"] for rule in group["rules"]]
    alert = next(rule for rule in alerts if rule["alert"] == "SLO_DagLatencyP99High")
    recording_doc = yaml.safe_load(
        (REPO_ROOT / "ops/observability/prometheus/slo_recording_rules.yml").read_text(
            encoding="utf-8"
        )
    )
    recording_rules = [rule for group in recording_doc["groups"] for rule in group["rules"]]
    recording = next(
        rule
        for rule in recording_rules
        if rule["record"] == "polisyos:slo_dag_p99_latency_seconds:5m"
    )
    recording_expression = " ".join(recording["expr"].split())
    objective_duration_selectors = [
        labels
        for metric, labels in _promql_metric_selectors(objective["sli"])
        if metric == "polisyos_slo_dag_duration_seconds_bucket"
    ]
    recording_duration_selectors = [
        labels
        for metric, labels in _promql_metric_selectors(recording["expr"])
        if metric == "polisyos_slo_dag_duration_seconds_bucket"
    ]
    dashboard = json.loads(
        (REPO_ROOT / "ops/observability/grafana/dashboards/slo-overview.json").read_text(
            encoding="utf-8"
        )
    )
    panel = next(row for row in dashboard["panels"] if row["title"] == "DAG Latency Distribution")
    panel_expression = panel["targets"][0]["expr"]
    assert alert["expr"] == "polisyos:slo_dag_p99_latency_seconds:5m > 300"
    assert alert["for"] == "15m"
    assert objective["window"] == "28d"
    assert "[30m]" in objective["sli"]
    assert objective_duration_selectors == [{"measurement_scope": ("=", "scientist_api")}]
    assert recording_duration_selectors == objective_duration_selectors
    assert "status" not in recording_duration_selectors[0]
    assert "clamp_min" not in recording_expression
    assert "[5m]" in recording_expression
    assert 'measurement_scope="scientist_api"' in panel_expression
    assert "polisyos_slo_dag_duration_seconds_bucket" in panel_expression
    assert "No series or zero eligible traffic is missing evidence" in runbook
    assert "has no executor-profile or helper label" in runbook
    assert "descendant whose full parent chain resolves to that root" in runbook
    assert "record the cause as unclassified" in runbook
    assert "does not establish production causation" in runbook


def test_invalid_state_before_workflow_resolution_emits_no_eligible_slo_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.scientist.api import run_experiment
    from tools.ops_runners.release.check_operability_release_gates import _metric_totals

    reader, meter_provider, metrics = _setup_metrics(monkeypatch, environment="test")
    span_exporter, trace_provider, tracer = _new_trace("test")
    before = reader.get_metrics_data()
    with pytest.raises(ValueError, match="Unsupported Scientist state keys"):
        run_experiment(
            {"run_id": "invalid-before-workflow-resolution", "not_a_state_field": True},
            tracer=tracer,
            metrics=metrics,
        )
    after = reader.get_metrics_data()
    assert _metric_totals(before) == _metric_totals(after) == {}
    assert span_exporter.get_finished_spans() == ()
    trace_provider.shutdown()
    meter_provider.shutdown()
