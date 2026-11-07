from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.benchmarks import (
    benchmark_partitioned_ingestion,
    benchmark_query_execution,
    benchmark_stream_processing,
    benchmark_world_materialization,
    persist_fabric_benchmark_report,
)
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import (
    IngestionResult,
    build_partitioned_ingestion_plan,
)
from polisyos.fabric.data_plane.streaming import StreamDedupeUnsupported, StreamingSourceSession
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.store import (
    append_world_segment_index,
    emit_world_node_facts,
    load_world_fact_manifests,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.world.abi import NodeKind
from tests._helpers.source_progress import finite_source_reader


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
    assert set(report.latency_quantiles_ms) == {"p50", "p95", "p99"}
    assert report.correctness_counters["partitions_succeeded"] == 2

    store = FileSystemCAS(tmp_path / ".reports")
    ref = persist_fabric_benchmark_report(store, report)
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    assert payload["benchmark_kind"] == "partitioned_ingestion"
    assert payload["labels"]["connector_id"] == "stream.jsonl"
    assert payload["latency_quantiles_ms"]["p95"] >= 0.0
    assert payload["correctness_counters"]["partitions_succeeded"] == 2


@pytest_asyncio.fixture
async def stream_registry():
    existing = ConnectorRegistry.get_instance(bootstrap=False)
    await existing.shutdown_async()
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    try:
        yield registry
    finally:
        await registry.shutdown_async()
        ConnectorRegistry.reset_instance()


def _stream_input(tmp_path: Path, registry: ConnectorRegistry):
    rows = [
        {"event_id": "m1", "source_version": 1, "value": 1},
        {"event_id": "m1", "source_version": 2, "value": 2},
        {"event_id": "m2", "source_version": 1, "value": 3},
        {"event_id": "m1", "source_version": 1, "value": 99},
    ]
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="stream.jsonl",
        dataset_id="events",
        schema_id="benchmark.events",
        snapshots=[("fixture-current", rows[:3])],
        transport_path=stream_path,
    )
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(url=stream_path.as_uri(), headers={"X-Stream-ChunkSize": "2"}),
    )
    return reader


@pytest.mark.asyncio
async def test_benchmark_stream_processing_reports_memory_and_throughput(
    tmp_path: Path, stream_registry: ConnectorRegistry
):
    reader = _stream_input(tmp_path, stream_registry)
    store = FileSystemCAS(tmp_path / ".polisyos")
    result, report = await benchmark_stream_processing(
        connector_id="stream.jsonl",
        dataset_id="events",
        store=store,
        cursor_store=CursorStore(store),
        sanitize_rows=_valid_rows,
        source_progress_readers=(reader,),
    )

    assert result.rows_emitted == 3
    assert result.dedupe_dropped == 1
    assert report.benchmark_kind == "stream_processing"
    assert report.units_processed == 3
    assert report.unit_name == "rows"
    assert report.metadata["chunks_processed"] == 2
    assert report.metadata["processing_guarantee"] == "replay_only"
    assert report.correctness_counters["rows_emitted"] == 3
    assert report.correctness_counters["dedupe_dropped"] == 1
    assert report.throughput_per_second >= 0.0
    assert report.peak_memory_bytes >= 0
    persisted = [
        row
        for ref in result.chunk_refs
        for row in from_canonical_bytes(store.get_bytes(ref.artifact_id))["data"]
    ]
    assert [(row["event_id"], row["source_version"], row["value"]) for row in persisted] == [
        ("m1", 1, 1),
        ("m1", 2, 2),
        ("m2", 1, 3),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("unowned_transport", [False, True])
async def test_benchmark_stream_refuses_missing_owner_or_unowned_transport_before_effects(
    tmp_path: Path, stream_registry: ConnectorRegistry, unowned_transport: bool
):
    reader = _stream_input(tmp_path, stream_registry)
    if unowned_transport:
        copied = tmp_path / "unowned.jsonl"
        copied.write_bytes(reader.transport_path.read_bytes())
        stream_registry.set_default_config("stream.jsonl", ConnectionConfig(url=copied.as_uri()))
    store = FileSystemCAS(tmp_path / ".polisyos")
    cursors = CursorStore(store)
    before = set(store.iter_artifact_ids())
    with pytest.raises(StreamDedupeUnsupported):
        await benchmark_stream_processing(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=cursors,
            sanitize_rows=_valid_rows,
            source_progress_readers=(reader,) if unowned_transport else (),
        )
    assert set(store.iter_artifact_ids()) == before
    assert cursors.find_latest_stream_checkpoint("stream.jsonl", "events") is None
    assert cursors.find_latest_cursor("stream.jsonl", "events") is None


@pytest.mark.asyncio
async def test_benchmark_stream_recovers_committed_owner_frontier_after_process_loss(
    tmp_path: Path, stream_registry: ConnectorRegistry, monkeypatch: pytest.MonkeyPatch
):
    reader = _stream_input(tmp_path, stream_registry)
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    original_poll = StreamingSourceSession.poll
    polls = 0

    class ProcessLoss(BaseException):
        pass

    async def crash_before_second_chunk(session):
        nonlocal polls
        if polls == 1:
            raise ProcessLoss()
        polls += 1
        return await original_poll(session)

    monkeypatch.setattr(StreamingSourceSession, "poll", crash_before_second_chunk)
    with pytest.raises(ProcessLoss):
        await benchmark_stream_processing(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=_valid_rows,
            source_progress_readers=(reader,),
        )
    prior = CursorStore(store).find_latest_stream_checkpoint("stream.jsonl", "events")
    assert prior is not None
    monkeypatch.setattr(StreamingSourceSession, "poll", original_poll)
    reopened = FileSystemCAS(cas_root)
    result, report = await benchmark_stream_processing(
        connector_id="stream.jsonl",
        dataset_id="events",
        store=reopened,
        cursor_store=CursorStore(reopened),
        sanitize_rows=_valid_rows,
        source_progress_readers=(reader,),
    )
    assert result.rows_emitted == 1
    assert result.dedupe_dropped == 1
    assert report.correctness_counters["rows_emitted"] == 1
    checkpoint = CursorStore(reopened).find_latest_stream_checkpoint("stream.jsonl", "events")
    assert checkpoint is not None
    assert checkpoint.checkpoint_id != prior.checkpoint_id
    rows = [
        row
        for artifact_id in reopened.iter_artifact_ids()
        if reopened.get_manifest(artifact_id).kind == "fabric.stream_chunk"
        for row in from_canonical_bytes(reopened.get_bytes(artifact_id))["data"]
    ]
    assert sorted((row["event_id"], row["source_version"]) for row in rows) == [
        ("m1", 1),
        ("m1", 2),
        ("m2", 1),
    ]


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
    assert report.correctness_counters["segments_applied"] == 1


def test_benchmark_query_execution_reports_quantiles_and_correctness() -> None:
    result, report = benchmark_query_execution(
        query_id="fabric.world.preview",
        operation=lambda: [{"id": "a"}, {"id": "b"}],
        labels={"surface": "world_query"},
    )

    assert len(result) == 2
    assert report.benchmark_kind == "query"
    assert report.unit_name == "rows"
    assert report.units_processed == 2
    assert report.labels["surface"] == "world_query"
    assert set(report.latency_quantiles_ms) == {"p50", "p95", "p99"}
    assert report.correctness_counters == {
        "rows_returned": 2,
        "non_empty_result": 1,
    }
