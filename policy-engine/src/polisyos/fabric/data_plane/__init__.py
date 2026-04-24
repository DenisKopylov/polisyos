"""Data Plane — orchestration layer for ingestion, quarantine, and snapshots."""

from .benchmarks import (
    FabricBenchmarkReport,
    benchmark_partitioned_ingestion,
    benchmark_stream_processing,
    benchmark_world_materialization,
    persist_fabric_benchmark_report,
)
from .quarantine import (
    QuarantineRecord,
    QuarantineReport,
    QuarantineReprocessResult,
    build_quarantine_report,
    list_quarantine_records,
    load_quarantine_payload,
    load_quarantine_record,
    persist_quarantine_record,
    quarantine_index_path,
    register_quarantine_reprocessor,
    reprocess_quarantine_records,
)
from .semantic_diff import compare_historical_rows, persist_historical_semantic_diff_report
from .streaming import (
    StreamDatasetRunResult,
    StreamingSourceSession,
    StreamRuntimeOptions,
    iter_record_batches,
    persist_cdc_schema_change_event,
    process_stream_dataset,
)

__all__ = [
    "FabricBenchmarkReport",
    "QuarantineRecord",
    "QuarantineReport",
    "QuarantineReprocessResult",
    "StreamDatasetRunResult",
    "StreamRuntimeOptions",
    "StreamingSourceSession",
    "benchmark_partitioned_ingestion",
    "benchmark_stream_processing",
    "benchmark_world_materialization",
    "build_quarantine_report",
    "compare_historical_rows",
    "iter_record_batches",
    "list_quarantine_records",
    "load_quarantine_payload",
    "load_quarantine_record",
    "persist_cdc_schema_change_event",
    "persist_fabric_benchmark_report",
    "persist_historical_semantic_diff_report",
    "persist_quarantine_record",
    "process_stream_dataset",
    "quarantine_index_path",
    "register_quarantine_reprocessor",
    "reprocess_quarantine_records",
]
