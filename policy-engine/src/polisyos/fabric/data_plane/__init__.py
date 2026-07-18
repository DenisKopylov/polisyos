"""Data Plane facade for orchestration, quarantine, snapshots, shape, and time."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AppendOnlyEvidenceJournal",
    "EvidenceJournalError",
    "FabricBenchmarkReport",
    "HarnessAuthorizationEvidence",
    "JournalEventRef",
    "LiveAttemptTerminal",
    "LiveExecutionAuthorization",
    "LiveHttpBudget",
    "LiveTransportTrace",
    "QuarantineRecord",
    "QuarantineReport",
    "QuarantineReprocessResult",
    "StreamDatasetRunResult",
    "StreamRuntimeOptions",
    "StreamingSourceSession",
    "benchmark_partitioned_ingestion",
    "benchmark_query_execution",
    "benchmark_stream_processing",
    "benchmark_world_materialization",
    "build_live_execution_authorization",
    "build_quarantine_report",
    "canonical_json_bytes",
    "compare_historical_rows",
    "content_sha256",
    "derive_harness_authorization_evidence",
    "derive_live_http_budget",
    "iter_record_batches",
    "list_quarantine_records",
    "load_quarantine_payload",
    "load_quarantine_record",
    "payload_to_dataframe",
    "persist_cdc_schema_change_event",
    "persist_fabric_benchmark_report",
    "persist_historical_semantic_diff_report",
    "persist_quarantine_record",
    "process_stream_dataset",
    "quarantine_index_path",
    "query_world_table",
    "register_quarantine_reprocessor",
    "reprocess_quarantine_records",
    "require_authorized_execution",
    "require_dataframe",
    "resolve_journal_event_ref",
    "resolve_linked_request_event",
    "resolve_live_attempt_terminal",
    "resolve_live_attempt_terminals",
    "resolve_live_transport_trace",
    "resolve_raw_response_body",
    "run_orchestrated_ingestion",
    "verify_journal_event_ref",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AppendOnlyEvidenceJournal": (
        "polisyos.fabric.data_plane.evidence_journal",
        "AppendOnlyEvidenceJournal",
    ),
    "EvidenceJournalError": (
        "polisyos.fabric.data_plane.evidence_journal",
        "EvidenceJournalError",
    ),
    "HarnessAuthorizationEvidence": (
        "polisyos.fabric.data_plane.evidence_journal",
        "HarnessAuthorizationEvidence",
    ),
    "JournalEventRef": (
        "polisyos.fabric.data_plane.evidence_journal",
        "JournalEventRef",
    ),
    "LiveAttemptTerminal": (
        "polisyos.fabric.data_plane.evidence_journal",
        "LiveAttemptTerminal",
    ),
    "LiveExecutionAuthorization": (
        "polisyos.fabric.data_plane.evidence_journal",
        "LiveExecutionAuthorization",
    ),
    "LiveHttpBudget": (
        "polisyos.fabric.data_plane.evidence_journal",
        "LiveHttpBudget",
    ),
    "LiveTransportTrace": (
        "polisyos.fabric.data_plane.evidence_journal",
        "LiveTransportTrace",
    ),
    "build_live_execution_authorization": (
        "polisyos.fabric.data_plane.evidence_journal",
        "build_live_execution_authorization",
    ),
    "derive_harness_authorization_evidence": (
        "polisyos.fabric.data_plane.evidence_journal",
        "derive_harness_authorization_evidence",
    ),
    "derive_live_http_budget": (
        "polisyos.fabric.data_plane.evidence_journal",
        "derive_live_http_budget",
    ),
    "content_sha256": (
        "polisyos.fabric.data_plane.evidence_journal",
        "content_sha256",
    ),
    "canonical_json_bytes": (
        "polisyos.fabric.data_plane.evidence_journal",
        "canonical_json_bytes",
    ),
    "require_authorized_execution": (
        "polisyos.fabric.data_plane.evidence_journal",
        "require_authorized_execution",
    ),
    "resolve_journal_event_ref": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_journal_event_ref",
    ),
    "resolve_linked_request_event": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_linked_request_event",
    ),
    "resolve_live_attempt_terminal": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_live_attempt_terminal",
    ),
    "resolve_live_attempt_terminals": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_live_attempt_terminals",
    ),
    "resolve_live_transport_trace": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_live_transport_trace",
    ),
    "resolve_raw_response_body": (
        "polisyos.fabric.data_plane.evidence_journal",
        "resolve_raw_response_body",
    ),
    "verify_journal_event_ref": (
        "polisyos.fabric.data_plane.evidence_journal",
        "verify_journal_event_ref",
    ),
    "FabricBenchmarkReport": ("polisyos.fabric.data_plane.benchmarks", "FabricBenchmarkReport"),
    "benchmark_partitioned_ingestion": (
        "polisyos.fabric.data_plane.benchmarks",
        "benchmark_partitioned_ingestion",
    ),
    "benchmark_query_execution": (
        "polisyos.fabric.data_plane.benchmarks",
        "benchmark_query_execution",
    ),
    "benchmark_stream_processing": (
        "polisyos.fabric.data_plane.benchmarks",
        "benchmark_stream_processing",
    ),
    "benchmark_world_materialization": (
        "polisyos.fabric.data_plane.benchmarks",
        "benchmark_world_materialization",
    ),
    "persist_fabric_benchmark_report": (
        "polisyos.fabric.data_plane.benchmarks",
        "persist_fabric_benchmark_report",
    ),
    "QuarantineRecord": ("polisyos.fabric.data_plane.quarantine", "QuarantineRecord"),
    "QuarantineReport": ("polisyos.fabric.data_plane.quarantine", "QuarantineReport"),
    "QuarantineReprocessResult": (
        "polisyos.fabric.data_plane.quarantine",
        "QuarantineReprocessResult",
    ),
    "build_quarantine_report": (
        "polisyos.fabric.data_plane.quarantine",
        "build_quarantine_report",
    ),
    "list_quarantine_records": (
        "polisyos.fabric.data_plane.quarantine",
        "list_quarantine_records",
    ),
    "load_quarantine_payload": (
        "polisyos.fabric.data_plane.quarantine",
        "load_quarantine_payload",
    ),
    "load_quarantine_record": (
        "polisyos.fabric.data_plane.quarantine",
        "load_quarantine_record",
    ),
    "persist_quarantine_record": (
        "polisyos.fabric.data_plane.quarantine",
        "persist_quarantine_record",
    ),
    "quarantine_index_path": (
        "polisyos.fabric.data_plane.quarantine",
        "quarantine_index_path",
    ),
    "register_quarantine_reprocessor": (
        "polisyos.fabric.data_plane.quarantine",
        "register_quarantine_reprocessor",
    ),
    "reprocess_quarantine_records": (
        "polisyos.fabric.data_plane.quarantine",
        "reprocess_quarantine_records",
    ),
    "compare_historical_rows": (
        "polisyos.fabric.data_plane.semantic_diff",
        "compare_historical_rows",
    ),
    "persist_historical_semantic_diff_report": (
        "polisyos.fabric.data_plane.semantic_diff",
        "persist_historical_semantic_diff_report",
    ),
    "StreamDatasetRunResult": (
        "polisyos.fabric.data_plane.streaming",
        "StreamDatasetRunResult",
    ),
    "StreamingSourceSession": (
        "polisyos.fabric.data_plane.streaming",
        "StreamingSourceSession",
    ),
    "StreamRuntimeOptions": ("polisyos.fabric.data_plane.streaming", "StreamRuntimeOptions"),
    "iter_record_batches": ("polisyos.fabric.data_plane.streaming", "iter_record_batches"),
    "persist_cdc_schema_change_event": (
        "polisyos.fabric.data_plane.streaming",
        "persist_cdc_schema_change_event",
    ),
    "process_stream_dataset": ("polisyos.fabric.data_plane.streaming", "process_stream_dataset"),
    "payload_to_dataframe": ("polisyos.fabric.data_plane.tabular", "payload_to_dataframe"),
    "require_dataframe": ("polisyos.fabric.data_plane.tabular", "require_dataframe"),
    "run_orchestrated_ingestion": (
        "polisyos.fabric.data_plane.orchestrator",
        "run_orchestrated_ingestion",
    ),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr = _LAZY_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module 'polisyos.fabric.data_plane' has no attribute {name!r}"
        ) from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_IMPORTS))
