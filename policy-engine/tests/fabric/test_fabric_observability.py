from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pandas as pd

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import HealthStatus
from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
from polisyos.fabric.connectors.transform import TransformContext, TransformPipeline
from polisyos.fabric.observability import FABRIC_TRACE_NAMES, build_fabric_health_snapshot
from polisyos.fabric.provenance.lineage import FabricLineageTracker


class _CollectingAlertSink:
    def __init__(self) -> None:
        self.alerts = []

    def emit(self, alert) -> None:  # noqa: ANN001
        self.alerts.append(alert)


def test_build_fabric_health_snapshot_reports_reasons_and_metrics(
    in_memory_exporter,
    tmp_path,
) -> None:
    del in_memory_exporter
    cache_store = ConnectorCacheStore(
        FileSystemCAS(tmp_path / ".polisyos"),
        TTLPolicy(ttl=timedelta(hours=1)),
    )
    cache_store.close()

    registry = SimpleNamespace(
        _connectors={
            "healthy": SimpleNamespace(
                fqid="connector.healthy",
                health_status=HealthStatus(healthy=True, message="ok"),
            ),
            "degraded": SimpleNamespace(
                fqid="connector.degraded",
                health_status=HealthStatus(healthy=False, message="timeout"),
            ),
        }
    )
    cursor_store = SimpleNamespace(list_cursors=lambda: [{"cursor": "a"}])
    retrieval_service = SimpleNamespace(
        get_index_stats=lambda: SimpleNamespace(
            index_docs_total=4,
            index_size_bytes=128,
            indexed_sources=2,
        )
    )
    sink = _CollectingAlertSink()

    snapshot = build_fabric_health_snapshot(
        registry=registry,
        cache_store=cache_store,
        fact_log_root=tmp_path,
        cursor_store=cursor_store,
        retrieval_service=retrieval_service,
        alert_sink=sink,
    )

    assert not snapshot.healthy
    assert any("connector.degraded: timeout" in reason for reason in snapshot.reasons)
    assert any("cache store is closed" in reason for reason in snapshot.reasons)
    assert [component.name for component in snapshot.components] == [
        "connectors",
        "cache",
        "world",
        "data_plane",
        "retrieval",
    ]
    assert [alert.component for alert in sink.alerts] == ["connectors", "cache"]

    metrics = get_metrics()
    assert metrics.fabric_segment_count is not None
    assert list(metrics.fabric_segment_count._values.values()) == [0.0]
    assert metrics.fabric_dlq_entries is not None
    assert list(metrics.fabric_dlq_entries._values.values()) == [0.0]


def test_transform_pipeline_emits_fabric_stage_span_and_lineage_metrics(
    in_memory_exporter,
) -> None:
    tracker = FabricLineageTracker("graph.transform.test")
    tracker.register_source_dataset(
        connector_id="demo.connector",
        dataset_id="demo.dataset",
        fields=["A"],
        schema_id="schema.demo",
    )
    pipeline = TransformPipeline().normalize(field_mappings={"A": "a"})

    result = pipeline.apply(
        pd.DataFrame({"A": [1, 2]}),
        TransformContext(
            evidence_refs=("evidence.bundle.test",),
            metadata={"lineage_tracker": tracker},
        ),
    )

    assert list(result.data.columns) == ["a"]

    spans = [
        span
        for span in in_memory_exporter.get_finished_spans()
        if span.name == FABRIC_TRACE_NAMES["transform_stage"]
    ]
    assert spans
    assert any(
        "normalize" in str(span.attributes.get("transform.stage_name", ""))
        for span in spans
    )

    metrics = get_metrics()
    assert metrics.fabric_lineage_graph_nodes is not None
    assert metrics.fabric_lineage_graph_edges is not None
    assert any(value >= 4.0 for value in metrics.fabric_lineage_graph_nodes._values.values())
    assert any(value >= 3.0 for value in metrics.fabric_lineage_graph_edges._values.values())
