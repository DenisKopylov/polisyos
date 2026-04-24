"""Benchmark helpers for Fabric streaming, ingestion, and world materialization paths."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.orchestrator import (
    ExecutionBackend,
    IngestionResult,
    PartitionedIngestionPlan,
    PartitionExecutionResult,
    run_partitioned_ingestion,
)
from polisyos.fabric.data_plane.streaming import (
    StreamDatasetRunResult,
    StreamRuntimeOptions,
    process_stream_dataset,
)
from polisyos.fabric.world.materialize import (
    WorldMaterializationPolicy,
    WorldMaterializeStats,
    ensure_world_materialized,
)


@dataclass(frozen=True)
class FabricBenchmarkReport:
    """Portable throughput/memory baseline for one Fabric execution path."""

    benchmark_id: str
    benchmark_kind: str
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    peak_memory_bytes: int
    units_processed: int
    unit_name: str
    throughput_per_second: float
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_kind": self.benchmark_kind,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
            "peak_memory_bytes": self.peak_memory_bytes,
            "units_processed": self.units_processed,
            "unit_name": self.unit_name,
            "throughput_per_second": self.throughput_per_second,
            "labels": dict(self.labels),
            "metadata": dict(self.metadata),
        }


def benchmark_partitioned_ingestion(
    *,
    plan: PartitionedIngestionPlan,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Any,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    backend: ExecutionBackend | str = "local_async",
    partition_handler: Callable[[Any], IngestionResult] | None = None,
) -> tuple[list[PartitionExecutionResult], FabricBenchmarkReport]:
    """Run partitioned ingestion and capture throughput/memory baseline."""

    def _run() -> list[PartitionExecutionResult]:
        return run_partitioned_ingestion(
            plan=plan,
            connector_manifest=connector_manifest,
            source=source,
            license_name=license_name,
            cas_root=cas_root,
            connection_config=connection_config,
            produce_snapshot=produce_snapshot,
            backend=backend,
            partition_handler=partition_handler,
        )

    results, started_at, elapsed_seconds, peak_memory_bytes = _capture_sync(_run)
    succeeded = [result for result in results if result.status == "succeeded"]
    expected_rows = sum(
        int(partition.expected_cardinality or 0)
        for partition in plan.partitions
        if partition.partition_id in {result.partition_id for result in succeeded}
    )
    unit_name = "rows" if expected_rows > 0 else "partitions"
    units_processed = expected_rows or len(succeeded)
    report = _build_report(
        benchmark_kind="partitioned_ingestion",
        started_at=started_at,
        elapsed_seconds=elapsed_seconds,
        peak_memory_bytes=peak_memory_bytes,
        units_processed=units_processed,
        unit_name=unit_name,
        labels={
            "connector_id": plan.connector_id,
            "dataset_id": plan.dataset_id,
            "backend": backend.backend_id if not isinstance(backend, str) else backend,
        },
        metadata={
            "plan_id": plan.plan_id,
            "partition_count": len(plan.partitions),
            "succeeded_partitions": len(succeeded),
            "failed_partitions": sum(1 for result in results if result.status == "failed"),
            "skipped_partitions": sum(1 for result in results if result.status == "skipped"),
        },
    )
    return results, report


async def benchmark_stream_processing(
    *,
    connector_id: str,
    dataset_id: str,
    store: FileSystemCAS,
    cursor_store: CursorStore,
    sanitize_rows: Callable[..., tuple[list[dict[str, Any]], list[str], int]],
    runtime_options: StreamRuntimeOptions | None = None,
    connection_config: Any | None = None,
) -> tuple[StreamDatasetRunResult, FabricBenchmarkReport]:
    """Run one event-driven stream and capture throughput/memory baseline."""

    async def _run() -> StreamDatasetRunResult:
        return await process_stream_dataset(
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=sanitize_rows,
            runtime_options=runtime_options,
            connection_config=connection_config,
        )

    result, started_at, elapsed_seconds, peak_memory_bytes = await _capture_async(_run)
    units_processed = int(result.rows_emitted or result.chunks_processed)
    report = _build_report(
        benchmark_kind="stream_processing",
        started_at=started_at,
        elapsed_seconds=elapsed_seconds,
        peak_memory_bytes=peak_memory_bytes,
        units_processed=units_processed,
        unit_name="rows" if result.rows_emitted else "chunks",
        labels={
            "connector_id": connector_id,
            "dataset_id": dataset_id,
            "partition_key": result.partition_key,
        },
        metadata={
            "chunks_processed": result.chunks_processed,
            "rows_emitted": result.rows_emitted,
            "window_count": len(result.window_refs),
            "cdc_event_count": len(result.cdc_event_refs),
            "quarantined_rows": result.quarantined_rows,
            "dedupe_dropped": result.dedupe_dropped,
            "backpressure_events": result.backpressure_events,
        },
    )
    return result, report


def benchmark_world_materialization(
    *,
    db: Any,
    cas: FileSystemCAS,
    fact_manifests: Sequence[Any],
    refresh_policy: WorldMaterializationPolicy | None = None,
) -> tuple[WorldMaterializeStats, FabricBenchmarkReport]:
    """Run world materialization and capture throughput/memory baseline."""

    def _run() -> WorldMaterializeStats:
        return ensure_world_materialized(
            db,
            cas,
            fact_manifests,
            refresh_policy=refresh_policy,
        )

    stats, started_at, elapsed_seconds, peak_memory_bytes = _capture_sync(_run)
    units_processed = int(stats.facts_inserted or stats.segments_applied or stats.segments_total)
    report = _build_report(
        benchmark_kind="world_materialization",
        started_at=started_at,
        elapsed_seconds=elapsed_seconds,
        peak_memory_bytes=peak_memory_bytes,
        units_processed=units_processed,
        unit_name="facts" if stats.facts_inserted else "segments",
        labels={
            "trigger": (
                refresh_policy.trigger.value
                if refresh_policy is not None
                else WorldMaterializationPolicy().trigger.value
            ),
        },
        metadata={
            "segments_total": stats.segments_total,
            "segments_applied": stats.segments_applied,
            "segments_skipped": stats.segments_skipped,
            "facts_inserted": stats.facts_inserted,
            "nodes_touched": stats.nodes_touched,
            "edges_inserted": stats.edges_inserted,
            "projections_updated": stats.projections_updated,
        },
    )
    return stats, report


def persist_fabric_benchmark_report(
    store: FileSystemCAS,
    report: FabricBenchmarkReport,
    *,
    input_refs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    """Persist one benchmark baseline report as a CAS artifact."""
    return store.put_json(
        report.to_payload(),
        PutOptions(
            kind="fabric.scale_benchmark_report",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.ScaleBenchmarkReport", version="1.0"),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role="benchmark_input") for ref in input_refs
            ]
            or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _capture_sync(
    operation: Callable[[], Any],
) -> tuple[Any, datetime, float, int]:
    started_at = datetime.now(UTC)
    tracing_before = tracemalloc.is_tracing()
    baseline_peak = tracemalloc.get_traced_memory()[1] if tracing_before else 0
    if not tracing_before:
        tracemalloc.start()
    started = time.perf_counter()
    try:
        result = operation()
    finally:
        elapsed_seconds = time.perf_counter() - started
        current, peak = tracemalloc.get_traced_memory()
        del current
        if not tracing_before:
            tracemalloc.stop()
    peak_memory_bytes = max(0, int(peak - baseline_peak)) if tracing_before else int(peak)
    return result, started_at, elapsed_seconds, peak_memory_bytes


async def _capture_async(
    operation: Callable[[], Any],
) -> tuple[Any, datetime, float, int]:
    started_at = datetime.now(UTC)
    tracing_before = tracemalloc.is_tracing()
    baseline_peak = tracemalloc.get_traced_memory()[1] if tracing_before else 0
    if not tracing_before:
        tracemalloc.start()
    started = time.perf_counter()
    try:
        result = await operation()
    finally:
        elapsed_seconds = time.perf_counter() - started
        current, peak = tracemalloc.get_traced_memory()
        del current
        if not tracing_before:
            tracemalloc.stop()
    peak_memory_bytes = max(0, int(peak - baseline_peak)) if tracing_before else int(peak)
    return result, started_at, elapsed_seconds, peak_memory_bytes


def _build_report(
    *,
    benchmark_kind: str,
    started_at: datetime,
    elapsed_seconds: float,
    peak_memory_bytes: int,
    units_processed: int,
    unit_name: str,
    labels: dict[str, str],
    metadata: dict[str, Any],
) -> FabricBenchmarkReport:
    finished_at = datetime.now(UTC)
    throughput = (
        float(units_processed) / elapsed_seconds
        if elapsed_seconds > 0 and units_processed > 0
        else 0.0
    )
    return FabricBenchmarkReport(
        benchmark_id=(f"{benchmark_kind}:{started_at.strftime('%Y%m%d%H%M%S%f')}"),
        benchmark_kind=benchmark_kind,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=float(elapsed_seconds),
        peak_memory_bytes=max(0, int(peak_memory_bytes)),
        units_processed=max(0, int(units_processed)),
        unit_name=str(unit_name),
        throughput_per_second=throughput,
        labels=dict(labels),
        metadata=dict(metadata),
    )


__all__ = [
    "FabricBenchmarkReport",
    "benchmark_partitioned_ingestion",
    "benchmark_stream_processing",
    "benchmark_world_materialization",
    "persist_fabric_benchmark_report",
]
