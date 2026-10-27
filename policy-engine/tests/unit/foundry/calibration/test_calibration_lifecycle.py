"""Behavioral tests for calibration execution lifecycle telemetry."""

from __future__ import annotations

from unittest.mock import MagicMock

import jax.numpy as jnp
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource

import polisyos.core.observability._metrics_registry_base as registry_base
import polisyos.core.observability.metrics_parts as metrics_parts
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.core.observability.config import (
    MetricsExporterType,
    OTelConfig,
    ResourceConfig,
)
from polisyos.foundry.calibration import calibrator as calibrator_module
from polisyos.foundry.calibration.calibrator import (
    CalibrationMetricsCollector,
    Calibrator,
    CalibratorInputs,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _metric_points(reader: InMemoryMetricReader, name: str):
    data = reader.get_metrics_data()
    if data is None:
        return []
    points = []
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == name:
                    points.extend(
                        (dict(point.attributes), point) for point in metric.data.data_points
                    )
    return points


@pytest.fixture
def metrics_capture(monkeypatch: pytest.MonkeyPatch):
    reader = InMemoryMetricReader()
    provider = MeterProvider(resource=Resource.create({}), metric_readers=[reader])
    monkeypatch.setattr(registry_base, "MeterProvider", lambda **_kwargs: provider)
    monkeypatch.setattr(registry_base.metrics, "set_meter_provider", lambda _provider: None)
    monkeypatch.setattr(
        registry_base.metrics,
        "get_meter",
        lambda name, version=None: provider.get_meter(name, version),
    )
    monkeypatch.setattr(
        registry_base,
        "get_default_config",
        lambda: OTelConfig(
            enabled=True,
            metrics_exporter=MetricsExporterType.NONE,
            environment="test",
        ),
    )
    monkeypatch.setattr(
        registry_base,
        "get_resource_config",
        lambda _config: ResourceConfig(service_name="test", service_version="test"),
    )
    monkeypatch.setattr(registry_base._MetricsRegistryBase, "_instance", None)
    monkeypatch.setattr(metrics_parts.MetricsRegistry, "_instance", None)
    monkeypatch.setattr(registry_base._MetricsRegistryBase, "_initialized", False)
    monkeypatch.setattr(metrics_parts, "_metrics_registry", None)
    monkeypatch.setattr(calibrator_module, "get_metrics", metrics_parts.get_metrics)
    registry = metrics_parts.get_metrics()
    yield registry, reader
    provider.shutdown()


def _metric_value(reader: InMemoryMetricReader, name: str, **labels: str) -> float | None:
    for attributes, point in _metric_points(reader, name):
        if attributes == labels:
            return float(point.value)
    return None


def test_oldest_active_calibration_cannot_be_masked_by_progressing_sibling(
    metrics_capture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registry, reader = metrics_capture
    now = [100.0]
    monkeypatch.setattr(
        registry_base._MetricsRegistryBase,
        "_calibration_monotonic_seconds",
        lambda _self: now[0],
    )
    stale = CalibrationMetricsCollector(optimizer_name="adam", enabled=True)
    sibling = CalibrationMetricsCollector(optimizer_name="adam", enabled=True)
    stale.start()
    now[0] = 110.0
    sibling.start()

    now[0] = 200.0
    sibling.record_step(0, 0.01, 1.0, 0.2, is_warmup=False)
    expected_labels = {"optimizer": "adam", "env": "test"}
    assert _metric_value(reader, "polisyos_calibration_active_runs", **expected_labels) == 2
    assert (
        _metric_value(
            reader,
            "polisyos_calibration_oldest_progress_age_seconds",
            **expected_labels,
        )
        == 100.0
    )
    for attributes, _point in _metric_points(
        reader,
        "polisyos_calibration_oldest_progress_age_seconds",
    ):
        assert "run_id" not in attributes

    now[0] = 210.0
    stale.finish("failed")
    assert _metric_value(reader, "polisyos_calibration_active_runs", **expected_labels) == 1
    assert (
        _metric_value(
            reader,
            "polisyos_calibration_oldest_progress_age_seconds",
            **expected_labels,
        )
        == 10.0
    )

    sibling.finish("completed")
    assert _metric_points(reader, "polisyos_calibration_active_runs") == []
    assert _metric_points(reader, "polisyos_calibration_oldest_progress_age_seconds") == []
    lifecycle = {
        attributes["status"]: int(point.value)
        for attributes, point in _metric_points(reader, "polisyos_calibration_runs_total")
    }
    assert lifecycle == {"started": 2, "failed": 1, "completed": 1}


def test_calibrator_preflight_failure_is_failed_and_preserves_primary_exception(
    metrics_capture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registry, reader = metrics_capture
    monkeypatch.setattr(calibrator_module, "is_hpc_observability_enabled", lambda: True)
    inputs = CalibratorInputs(
        config=CalibrationConfig(),
        program_graph=MagicMock(),
        exec_plan=MagicMock(),
        base_state=MagicMock(),
        mechanism_registry=MagicMock(),
        slot_registry=MagicMock(),
        merge_registry=MagicMock(),
        selector_field_registry=None,
        parameter_loader=lambda _node: {},
    )
    calibrator = Calibrator(inputs)
    primary = RuntimeError("primary preflight failure")
    monkeypatch.setattr(calibrator, "_build_bundle", lambda: (_ for _ in ()).throw(primary))

    with pytest.raises(RuntimeError) as caught:
        calibrator.run()
    assert caught.value is primary
    labels = {"optimizer": "adam", "env": "test"}
    assert _metric_value(reader, "polisyos_calibration_active_runs", **labels) is None
    lifecycle = {
        attributes["status"]: int(point.value)
        for attributes, point in _metric_points(reader, "polisyos_calibration_runs_total")
    }
    assert lifecycle == {"started": 1, "failed": 1}


def _build_graph() -> tuple[ProgramGraph, ExecPlan]:
    artifact_id = ArtifactID.from_sha256_hex("0" * 64)
    policy_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    program_ref = ProgramGraphRef(artifact_id=artifact_id)
    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    return (
        ProgramGraph(ir_ref=policy_ref, nodes=[node], edges=[], entrypoints=[]),
        ExecPlan(program_ref=program_ref, order=[node.node_id]),
    )


class _RecordingSpan:
    def __init__(self, name: str, attributes: dict[str, object]) -> None:
        self.name = name
        self.attributes = attributes

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[_RecordingSpan] = []

    def start_as_current_span(self, name: str, attributes=None) -> _RecordingSpan:
        span = _RecordingSpan(name, dict(attributes or {}))
        self.spans.append(span)
        return span


def test_real_calibrator_run_emits_step_and_completed_lifecycle(
    metrics_capture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registry, reader = metrics_capture
    monkeypatch.setattr(calibrator_module, "is_hpc_observability_enabled", lambda: True)
    tracer = _RecordingTracer()
    monkeypatch.setattr(calibrator_module, "get_tracer", lambda: tracer)
    initial_state = GlobalState.empty(n_agents=1, n_firms=1)
    state = initial_state.replace(
        agents=initial_state.agents.replace(
            income=jnp.array([100.0]),
            reported_income=jnp.array([100.0]),
        ),
        government_balance=jnp.array(0.0),
    )
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        max_steps=1,
        seed=0,
        hessian={"enabled": False},
    )
    program_graph, exec_plan = _build_graph()
    calibrator = Calibrator(
        CalibratorInputs(
            config=config,
            program_graph=program_graph,
            exec_plan=exec_plan,
            base_state=state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            selector_field_registry=None,
            parameter_loader=lambda _node: {
                "params": {"rate": 0.3},
                "schedule": {"start_step": 0, "end_step": 10},
            },
            raw_targets={"gov_balance": jnp.array([50.0], dtype=jnp.float32)},
            controls_seq=jnp.arange(1),
        )
    )

    calibrator.run()

    duration_points = _metric_points(reader, "polisyos_calibration_step_duration_seconds")
    assert sum(point.count for _attributes, point in duration_points) == 1
    lifecycle = {
        attributes["status"]: int(point.value)
        for attributes, point in _metric_points(reader, "polisyos_calibration_runs_total")
    }
    assert lifecycle == {"started": 1, "completed": 1}
    assert _metric_points(reader, "polisyos_calibration_active_runs") == []
    assert _metric_points(reader, "polisyos_calibration_oldest_progress_age_seconds") == []
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.name == "calibration.run"
    run_id = span.attributes["calibration.run_id"]
    assert isinstance(run_id, str) and run_id
    for metric_name in (
        "polisyos_calibration_runs_total",
        "polisyos_calibration_step_duration_seconds",
    ):
        for attributes, _point in _metric_points(reader, metric_name):
            assert "run_id" not in attributes
