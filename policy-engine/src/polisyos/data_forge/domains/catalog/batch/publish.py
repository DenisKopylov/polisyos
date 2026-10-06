"""Stage 8: publish dataset pipeline artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from polisyos.data_forge.domains.catalog.batch.benchmark import readiness_thresholds_for_profile
from polisyos.data_forge.kernel.embeddings import embedding_generation_manifest
from polisyos.data_forge.kernel.io import atomic_write_bytes, sha256_bytes
from polisyos.data_forge.kernel.pipeline.manifests import (
    write_publish_manifest,
    write_stage_manifest,
)

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig


def _table_count(db_path: Path, table_name: str) -> int:
    if not db_path.exists():
        return 0
    with duckdb.connect(str(db_path), read_only=True) as con:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchone()[0]
        if not exists:
            return 0
        return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


@dataclass(frozen=True)
class _VerifiedReportSnapshot:
    """Immutable report bytes admitted against a current producer receipt."""

    content: bytes
    payload: dict[str, object]


def _capture_current_report_snapshots(
    config: DatasetBatchConfig,
) -> tuple[dict[str, dict[str, object]], dict[str, _VerifiedReportSnapshot]]:
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_content_stage_receipt,
    )

    receipts: dict[str, dict[str, object]] = {}
    snapshots: dict[str, _VerifiedReportSnapshot] = {}
    reports = {
        "benchmark": config.benchmark_report_path,
        "qc": config.qc_report_path,
    }
    for stage, path in reports.items():
        receipt = current_content_stage_receipt(config, stage)
        if receipt is None:
            raise RuntimeError(f"Dataset publish blocked: no current {stage} content-bound receipt")
        inventory = receipt.get("output_inventory")
        entries = inventory.get("entries") if isinstance(inventory, dict) else None
        matching_entries = [
            entry
            for entry in entries or []
            if isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and Path(str(entry["path"])).resolve() == path.resolve()
        ]
        if len(matching_entries) != 1:
            raise RuntimeError(
                f"Dataset publish blocked: {stage} receipt does not uniquely bind its report"
            )
        entry = matching_entries[0]
        expected_digest = entry.get("sha256")
        expected_size = entry.get("size")
        if (
            entry.get("exists") is not True
            or not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)
            or type(expected_size) is not int
            or expected_size < 0
        ):
            raise RuntimeError(
                f"Dataset publish blocked: {stage} receipt has no complete report inventory"
            )
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"Dataset publish blocked: cannot read current {stage} report bytes"
            ) from exc
        if len(content) != expected_size or sha256_bytes(content) != expected_digest:
            raise RuntimeError(
                f"Dataset publish blocked: {stage} report bytes differ from its producer receipt"
            )
        try:
            decoded = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Dataset publish blocked: invalid {stage} report JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError(f"Dataset publish blocked: {stage} report must be a JSON object")
        receipts[stage] = receipt
        snapshots[stage] = _VerifiedReportSnapshot(content=content, payload=decoded)
    return receipts, snapshots


def _require_current_report_receipts(
    config: DatasetBatchConfig,
    expected_receipts: dict[str, dict[str, object]],
) -> None:
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_content_stage_receipt,
    )

    for stage, expected in expected_receipts.items():
        if current_content_stage_receipt(config, stage) != expected:
            raise RuntimeError(
                f"Dataset publish blocked: {stage} content-bound receipt changed before publication"
            )


def _build_consumer_readiness(
    config: DatasetBatchConfig,
    *,
    qc_payload: dict[str, object],
    benchmark_payload: dict[str, object],
) -> tuple[dict[str, object], dict[str, bool], dict[str, str]]:
    benchmark_metrics = (
        benchmark_payload.get("metrics")
        if isinstance(benchmark_payload.get("metrics"), dict)
        else {}
    )
    evaluation_mode = (
        str(benchmark_payload.get("evaluation_mode") or "full-ready").strip() or "full-ready"
    )
    qc_passed = qc_payload.get("passed") is True
    thresholds = readiness_thresholds_for_profile(config.run_profile)
    source_preflight_payload = (
        benchmark_payload.get("source_preflight")
        if isinstance(benchmark_payload.get("source_preflight"), dict)
        else {}
    )
    source_preflight_cases = (
        source_preflight_payload.get("sources")
        if isinstance(source_preflight_payload.get("sources"), list)
        else []
    )
    blocking_specs = [
        spec
        for spec in config.load_registry().sources
        if spec.enabled and spec.publish_blocking and spec.run_lane == "empirical"
    ]
    blocking_source_names = {spec.name for spec in blocking_specs}
    blocking_source_statuses: dict[str, str] = {}
    blocking_source_readiness: dict[str, bool] = {}
    for index, case in enumerate(source_preflight_cases):
        if not isinstance(case, dict):
            raise RuntimeError(f"Dataset publish blocked: invalid source preflight row {index}")
        source = case.get("source")
        status = case.get("status")
        if not isinstance(source, str) or not source.strip():
            raise RuntimeError(f"Dataset publish blocked: invalid source identity in row {index}")
        if source not in blocking_source_names:
            raise RuntimeError(
                f"Dataset publish blocked: unexpected blocking source status ({source})"
            )
        if source in blocking_source_statuses:
            raise RuntimeError(
                f"Dataset publish blocked: duplicate blocking source status ({source})"
            )
        if not isinstance(status, str) or not status.strip():
            raise RuntimeError(
                f"Dataset publish blocked: invalid blocking source status ({source})"
            )
        blocking_source_statuses[source] = status
        blocking_source_readiness[source] = case.get("ready") is True
    missing_blocking_statuses = sorted(
        spec.name for spec in blocking_specs if spec.name not in blocking_source_statuses
    )
    if missing_blocking_statuses:
        raise RuntimeError(
            "Dataset publish blocked: missing blocking source statuses "
            f"({', '.join(missing_blocking_statuses)})"
        )

    bulk_equivalence_mismatch_rate = float(
        benchmark_metrics.get("benchmark_bulk_equivalence_mismatch_rate", 0.0) or 0.0
    )
    bulk_equivalence_blocking_sources_total = int(
        benchmark_metrics.get("benchmark_bulk_equivalence_blocking_sources_total", 0) or 0
    )

    readiness = {
        "qc_ready": qc_passed,
        "benchmark_ready": bool(benchmark_metrics),
        "search_ready": float(
            benchmark_metrics.get("benchmark_search_top5_relevance_pct", 0.0) or 0.0
        )
        >= thresholds["benchmark_search_top5_relevance_pct"],
        "fetchability_ready": float(
            benchmark_metrics.get("benchmark_retrieval_ready_pct", 0.0) or 0.0
        )
        >= thresholds["benchmark_retrieval_ready_pct"],
        "transportability_ready": float(
            benchmark_metrics.get("benchmark_transport_ready_pct", 0.0) or 0.0
        )
        >= thresholds["benchmark_transport_ready_pct"],
        "foundry_ready": float(benchmark_metrics.get("benchmark_foundry_fitness_pct", 0.0) or 0.0)
        >= thresholds["benchmark_foundry_fitness_pct"],
        "source_preflight_ready": float(
            benchmark_metrics.get("benchmark_source_preflight_ready_pct", 0.0) or 0.0
        )
        >= thresholds["benchmark_source_preflight_ready_pct"],
        "evaluation_ready": evaluation_mode in {"core-ready", "full-ready"},
        "equivalence_ready": (
            bulk_equivalence_mismatch_rate <= 2.0 and bulk_equivalence_blocking_sources_total <= 0
        ),
        "blocking_sources_ready": (
            set(blocking_source_statuses) == blocking_source_names
            and all(blocking_source_readiness.get(name) is True for name in blocking_source_names)
        ),
    }
    readiness["consumer_ready"] = all(readiness.values())
    readiness["full_publish_ready"] = (
        readiness["consumer_ready"] and evaluation_mode == "full-ready"
    )

    table_counts = {
        "datasets": _table_count(config.db_path, "ds_datasets"),
        "distributions": _table_count(config.db_path, "ds_distributions"),
        "metric_bindings": _table_count(config.db_path, "ds_metric_bindings"),
        "schema_profiles": _table_count(config.db_path, "ds_schema_profiles"),
        "registry_datasets": _table_count(config.db_path, "ds_registry_datasets"),
        "variable_alignments": _table_count(config.db_path, "ds_variable_alignments"),
        "observations": _table_count(config.db_path, "ds_observations"),
        "entity_mappings": _table_count(config.db_path, "ds_entity_mappings"),
        "alignment_hints": _table_count(config.db_path, "ds_alignment_hints"),
    }

    payload = {
        "kind": "consumer_readiness",
        "snapshot_root": str(config.snapshot_root),
        "component_dir": str(config.component_dir),
        "thresholds": thresholds,
        "readiness": readiness,
        "benchmark_metrics": {key: benchmark_metrics.get(key, 0.0) for key in thresholds},
        "table_counts": table_counts,
        "promoted_sources": list(config.promoted_sources),
        "run_profile": config.run_profile,
        "blocking_source_statuses": blocking_source_statuses,
        "blocking_source_readiness": blocking_source_readiness,
        "evaluation_mode": evaluation_mode,
        "publish_mode": (
            "full-ready"
            if readiness["full_publish_ready"]
            else ("core-ready" if readiness["consumer_ready"] else "blocked")
        ),
        "bulk_equivalence_mismatch_rate": bulk_equivalence_mismatch_rate,
        "bulk_equivalence_blocking_sources_total": bulk_equivalence_blocking_sources_total,
    }

    return payload, readiness, blocking_source_statuses


def _calculate_consumer_readiness_snapshot(
    config: DatasetBatchConfig,
    content_stage_receipts: dict[str, dict[str, object]],
    report_snapshots: dict[str, _VerifiedReportSnapshot],
) -> tuple[dict[str, object], dict[str, bool], dict[str, str], bytes]:
    payload, readiness, blocking_source_statuses = _build_consumer_readiness(
        config,
        qc_payload=report_snapshots["qc"].payload,
        benchmark_payload=report_snapshots["benchmark"].payload,
    )
    payload["content_stage_receipts"] = content_stage_receipts
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return payload, readiness, blocking_source_statuses, content


def run_publish(config: DatasetBatchConfig) -> Path:
    """Write publish manifest with final dataset artifacts and checksums."""
    started_at = datetime.now(UTC).isoformat()
    content_stage_receipts, report_snapshots = _capture_current_report_snapshots(config)
    _readiness_payload, readiness, blocking_source_statuses, readiness_bytes = (
        _calculate_consumer_readiness_snapshot(
            config,
            content_stage_receipts,
            report_snapshots,
        )
    )
    if not readiness["consumer_ready"]:
        _require_current_report_receipts(config, content_stage_receipts)
        atomic_write_bytes(config.consumer_readiness_path, readiness_bytes)
        failed = sorted(name for name, passed in readiness.items() if not passed)
        raise RuntimeError(
            f"Dataset publish blocked: consumer readiness failed ({', '.join(failed)})"
        )

    generation = embedding_generation_manifest(
        config.index_dir,
        legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
    )
    generation_metadata = generation[0] if generation else None
    generation_artifacts = generation[1] if generation else ()

    artifacts = [
        config.db_path,
        config.merged_records_path,
        config.duplicates_report_path,
        config.benchmark_report_path,
        config.qc_report_path,
        config.consumer_readiness_path,
    ]
    artifacts.extend(generation_artifacts)
    captured_artifact_bytes = {
        config.benchmark_report_path: report_snapshots["benchmark"].content,
        config.qc_report_path: report_snapshots["qc"].content,
        config.consumer_readiness_path: readiness_bytes,
    }
    existing = [path for path in artifacts if path.exists() or path in captured_artifact_bytes]

    readiness_summary: dict[str, object] = {}
    source_publish_blocking: dict[str, bool] = {}
    rest_rows_by_source: dict[str, int] = {}
    rest_bytes_by_source: dict[str, int] = {}
    qc_payload = report_snapshots["qc"].payload
    metrics = qc_payload.get("metrics")
    if isinstance(metrics, dict):
        readiness_summary = {
            key: metrics[key]
            for key in (
                "machine_readable_distribution_pct",
                "parser_supported_distribution_pct",
                "datasets_with_metric_binding_pct",
                "datasets_with_schema_profile_pct",
                "transport_ready_var_coverage_pct",
                "execution_readiness_score_avg",
                "observations_attempted",
                "observations_inserted",
                "observations_replaced",
                "history_budget_exceeded_sources",
                "benchmark_search_top5_relevance_pct",
                "benchmark_retrieval_ready_pct",
                "benchmark_transport_ready_pct",
                "benchmark_foundry_fitness_pct",
            )
            if key in metrics
        }
        rest_rows_by_source = {
            str(key): int(value)
            for key, value in (metrics.get("rest_rows_by_source") or {}).items()
        }
        rest_bytes_by_source = {
            str(key): int(value)
            for key, value in (metrics.get("rest_bytes_by_source") or {}).items()
        }
    benchmark_payload = report_snapshots["benchmark"].payload
    evaluation_mode = (
        str(benchmark_payload.get("evaluation_mode") or "full-ready").strip() or "full-ready"
    )
    source_publish_blocking = {
        spec.name: spec.publish_blocking for spec in config.load_registry().sources
    }

    _require_current_report_receipts(config, content_stage_receipts)
    atomic_write_bytes(config.consumer_readiness_path, readiness_bytes)
    manifest_path = write_publish_manifest(
        manifest_path=config.publish_manifest_path,
        pipeline="datasets",
        artifacts=existing,
        captured_artifact_bytes=captured_artifact_bytes,
        qc_report_path=config.qc_report_path,
        extra={
            "snapshot_root": str(config.snapshot_root),
            "component_dir": str(config.component_dir),
            "promoted_sources": list(config.promoted_sources),
            "run_profile": config.run_profile,
            "readiness_summary": readiness_summary,
            "source_publish_blocking": source_publish_blocking,
            "rest_rows_by_source": rest_rows_by_source,
            "rest_bytes_by_source": rest_bytes_by_source,
            "blocking_source_statuses": blocking_source_statuses,
            "consumer_readiness_manifest": str(config.consumer_readiness_path),
            "benchmark_report": str(config.benchmark_report_path),
            "consumer_ready": readiness["consumer_ready"],
            "full_publish_ready": readiness["full_publish_ready"],
            "evaluation_mode": evaluation_mode,
            "embedding_generation": generation_metadata or {},
        },
    )

    write_stage_manifest(
        manifest_path=config.manifests_dir / "publish.json",
        stage="publish",
        status="ok",
        metrics={"artifacts": len(existing)},
        artifacts=[manifest_path],
        started_at=started_at,
    )
    return manifest_path
