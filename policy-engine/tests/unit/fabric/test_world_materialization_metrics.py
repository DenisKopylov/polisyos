from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from polisyos.core.observability import _metrics_registry_base as registry_base
from polisyos.core.observability._metrics_registry_base import MetricsRegistryBase
from polisyos.core.observability.config import MetricsExporterType, OTelConfig, ResourceConfig
from polisyos.core.observability.metrics_parts import MetricsRegistry
from polisyos.fabric.world.materialize import duckdb as materialize_duckdb
from polisyos.ir.loading.fact_log import FactSegmentManifest


def _make_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MetricsRegistry, InMemoryMetricReader, MeterProvider]:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    config = OTelConfig(enabled=True, metrics_exporter=MetricsExporterType.NONE)
    monkeypatch.setattr(registry_base, "get_default_config", lambda: config)
    monkeypatch.setattr(
        registry_base,
        "get_resource_config",
        lambda _: ResourceConfig(service_name="polisyos-test", service_version="test"),
    )
    monkeypatch.setattr(otel_metrics, "get_meter", provider.get_meter)
    monkeypatch.setattr(otel_metrics, "set_meter_provider", lambda _: None)
    monkeypatch.setattr(MetricsRegistryBase, "_instance", None)
    monkeypatch.setattr(MetricsRegistryBase, "_initialized", False)
    return MetricsRegistry(), reader, provider


def _manifest(
    label: str,
    time_end: str | int | None,
    *,
    tenant_id: str | None = None,
) -> FactSegmentManifest:
    stats = {"tenant_id": tenant_id} if tenant_id is not None else {}
    return FactSegmentManifest(
        segment_id=f"segment.{label}",
        path="unused.parquet",
        row_count=0,
        sha256="0" * 64,
        time_end=time_end,
        stats=stats,
    )


def _metric_points(
    reader: InMemoryMetricReader,
    metric_name: str,
) -> list[tuple[dict[str, Any], float]]:
    data = reader.get_metrics_data()
    if data is None:
        return []
    return [
        (dict(point.attributes), float(point.value))
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == metric_name
        for point in metric.data.data_points
    ]


def test_materialization_age_requires_every_selected_valid_time_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        materialize_duckdb,
        "utc_now",
        lambda: datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
    )
    recent = _manifest("recent", "2026-10-26T11:59:55Z")
    older = _manifest("older", "2026-10-26T11:00:00Z")

    assert materialize_duckdb._materialization_lag_seconds([older, recent]) == pytest.approx(5.0)
    assert materialize_duckdb._materialization_lag_seconds([]) is None
    for index, invalid_end in enumerate(
        (
            None,
            0,
            "",
            "not-a-time",
            "0001-01-01T00:00:00+23:59",
            "9999-12-31T23:59:00-23:59",
        )
    ):
        invalid = _manifest(f"invalid-{index}", invalid_end)
        assert materialize_duckdb._materialization_lag_seconds([recent, invalid]) is None


def test_materialization_age_metric_clears_unknown_and_replaced_scope_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, reader, provider = _make_registry(monkeypatch)
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(materialize_duckdb, "utc_now", lambda: now)
    monkeypatch.setattr(materialize_duckdb, "ensure_world_schema", lambda _db: None)
    selected: list[FactSegmentManifest] = []
    monkeypatch.setattr(
        materialize_duckdb,
        "_load_applied_segments",
        lambda _db: {item.segment_id: item.sha256 for item in selected},
    )
    tracer = SimpleNamespace(start_as_current_span=lambda *_args, **_kwargs: nullcontext())

    def measure(manifests: list[FactSegmentManifest]) -> None:
        selected[:] = manifests
        materialize_duckdb.ensure_world_materialized(
            SimpleNamespace(),
            SimpleNamespace(),
            manifests,
            tracer=tracer,
            metrics=registry,
        )

    valid_alpha = _manifest("valid-alpha", "2026-10-26T11:59:55Z", tenant_id="alpha")
    invalid_alpha = _manifest("invalid-alpha", "bad-time", tenant_id="alpha")
    invalid_beta = _manifest("invalid-beta", 123, tenant_id="beta")
    valid_beta = _manifest("valid-beta", "2026-10-26T11:59:55Z", tenant_id="beta")
    age_name = "polisyos_fabric_materialization_lag_seconds"
    complete_name = "polisyos_fabric_materialization_valid_time_age_complete"

    overflow_lower = _manifest(
        "overflow-lower",
        "0001-01-01T00:00:00+23:59",
        tenant_id="alpha",
    )
    overflow_upper = _manifest(
        "overflow-upper",
        "9999-12-31T23:59:00-23:59",
        tenant_id="alpha",
    )

    measure([valid_alpha])
    assert _metric_points(reader, age_name) == [({"scope": "world", "tenant_id": "alpha"}, 5.0)]
    assert _metric_points(reader, complete_name) == [
        ({"scope": "world", "tenant_id": "alpha"}, 1.0)
    ]

    measure([valid_alpha, invalid_alpha])
    assert _metric_points(reader, age_name) == []
    assert _metric_points(reader, complete_name) == [
        ({"scope": "world", "tenant_id": "alpha"}, 0.0)
    ]

    measure([invalid_alpha])
    assert _metric_points(reader, age_name) == []
    assert _metric_points(reader, complete_name) == [
        ({"scope": "world", "tenant_id": "alpha"}, 0.0)
    ]

    measure([valid_alpha])
    assert _metric_points(reader, age_name) == [({"scope": "world", "tenant_id": "alpha"}, 5.0)]
    assert _metric_points(reader, complete_name) == [
        ({"scope": "world", "tenant_id": "alpha"}, 1.0)
    ]

    for overflow in (overflow_lower, overflow_upper):
        measure([valid_alpha, overflow])
        assert _metric_points(reader, age_name) == []
        assert _metric_points(reader, complete_name) == [
            ({"scope": "world", "tenant_id": "alpha"}, 0.0)
        ]

    measure([valid_alpha, valid_beta])
    assert _metric_points(reader, age_name) == [({"scope": "world"}, 5.0)]
    assert _metric_points(reader, complete_name) == [({"scope": "world"}, 1.0)]

    measure([valid_alpha, invalid_beta])
    assert _metric_points(reader, age_name) == []
    assert _metric_points(reader, complete_name) == [({"scope": "world"}, 0.0)]

    measure([valid_beta])
    assert _metric_points(reader, age_name) == [({"scope": "world", "tenant_id": "beta"}, 5.0)]
    assert _metric_points(reader, complete_name) == [({"scope": "world", "tenant_id": "beta"}, 1.0)]

    measure([])
    assert _metric_points(reader, age_name) == []
    assert _metric_points(reader, complete_name) == [({"scope": "world"}, 0.0)]

    provider.shutdown()


def test_projection_backup_cleanup_warning_preserves_primary_restore_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingConnection:
        def execute(self, statement: str) -> None:
            if statement.startswith("DELETE FROM"):
                raise RuntimeError("primary restore failure")
            if statement.startswith("DROP TABLE"):
                raise RuntimeError("secondary cleanup failure")

    warnings: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(
        materialize_duckdb.logger,
        "warning",
        lambda message, **fields: warnings.append((message, fields)),
    )

    with pytest.raises(RuntimeError, match="primary restore failure"):
        materialize_duckdb._restore_projection_tables(
            SimpleNamespace(conn=_FailingConnection()),
            {"world.world_nodes": "tmp_world_nodes_backup"},
        )

    assert len(warnings) == 1
    assert warnings[0][1]["backup_table"] == "tmp_world_nodes_backup"
    assert warnings[0][1]["error"] == "secondary cleanup failure"
