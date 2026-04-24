from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.benchmarks import (
    benchmark_partitioned_ingestion,
    benchmark_stream_processing,
    benchmark_world_materialization,
    persist_fabric_benchmark_report,
)
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import (
    IngestionResult,
    build_partitioned_ingestion_plan,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_world_node_facts,
    load_world_fact_manifests,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.world.abi import NodeKind


def _valid_rows(batch, **kwargs):
    del kwargs
    return [dict(row) for row in batch if isinstance(row, dict)], [], 0


def test_benchmark_partitioned_ingestion_publishes_baseline(tmp_path: Path):
    plan = build_partitioned_ingestion_plan(
        connector_id="stream.jsonl",
        dataset_id="events",
        partition_key="region",
        partitions=[
            {"partition_id": "p0", "bounds": {"region": "ua"}, "expected_cardinality": 3},
            {"partition_id": "p1", "bounds": {"region": "pl"}, "expected_cardinality": 5},
        ],
    )

    def handler(partition) -> IngestionResult:
        return IngestionResult(
            datasets_fetched=1,
            cursor_ref=f"cursor:{partition.partition_id}",
        )

    results, report = benchmark_partitioned_ingestion(
        plan=plan,
        connector_manifest={"datasets": []},
        source="test",
        license_name="open",
        cas_root=tmp_path / ".polisyos",
        partition_handler=handler,
        produce_snapshot=False,
    )

    assert [result.status for result in results] == ["succeeded", "succeeded"]
    assert report.benchmark_kind == "partitioned_ingestion"
    assert report.units_processed == 8
    assert report.unit_name == "rows"
    assert report.throughput_per_second >= 0.0
    assert report.peak_memory_bytes >= 0
    assert report.labels["backend"] == "local_async"

    store = FileSystemCAS(tmp_path / ".reports")
    ref = persist_fabric_benchmark_report(store, report)
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    assert payload["benchmark_kind"] == "partitioned_ingestion"
    assert payload["labels"]["connector_id"] == "stream.jsonl"


@pytest.mark.asyncio
async def test_benchmark_stream_processing_reports_memory_and_throughput(tmp_path: Path):
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"_message_id":"m1","value":1}',
                '{"_message_id":"m2","value":2}',
                '{"_message_id":"m3","value":3}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2"},
        ),
    )

    store = FileSystemCAS(tmp_path / ".polisyos")
    cursor_store = CursorStore(store)
    result, report = await benchmark_stream_processing(
        connector_id="stream.jsonl",
        dataset_id="events",
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=_valid_rows,
    )

    assert result.rows_emitted == 3
    assert report.benchmark_kind == "stream_processing"
    assert report.units_processed == 3
    assert report.unit_name == "rows"
    assert report.metadata["chunks_processed"] == 2
    assert report.throughput_per_second >= 0.0
    assert report.peak_memory_bytes >= 0


def test_benchmark_world_materialization_reports_baseline(tmp_path: Path):
    provenance = stable_world_provenance_v1()
    facts = emit_world_node_facts(
        node_id="doc.source",
        kind=NodeKind.DOC_SOURCE,
        label="Doc",
        artifact_id=None,
        props_ref=None,
        provenance=provenance,
    )
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="bench-world",
    ).model_copy(update={"stats": {"tenant_id": "tenant-a", "dataset_id": "world"}})
    append_world_segment_index(manifest, fact_log_root=tmp_path)
    manifests = load_world_fact_manifests(tmp_path)

    db = SimulationDB(db_path=str(tmp_path / "benchmark.duckdb"))
    cas = FileSystemCAS(tmp_path / "cas")
    stats, report = benchmark_world_materialization(
        db=db,
        cas=cas,
        fact_manifests=manifests,
    )

    assert stats.segments_applied == 1
    assert report.benchmark_kind == "world_materialization"
    assert report.unit_name in {"facts", "segments"}
    assert report.units_processed >= 1
    assert report.labels["trigger"] == "on_segment_arrival"
    assert report.metadata["segments_total"] == 1
