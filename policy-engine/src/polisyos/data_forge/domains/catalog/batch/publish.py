"""Stage 8: publish dataset pipeline artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb

from polisyos.data_forge.kernel.embeddings import embedding_generation_manifest
from polisyos.data_forge.kernel.pipeline.manifests import (
    write_publish_manifest,
    write_stage_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

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


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _write_consumer_readiness_manifest(
    config: DatasetBatchConfig,
    report_basis: Mapping[str, object],
) -> tuple[Path, dict[str, bool]]:
    """Emit readiness only from the admitted canonical benchmark/QC report basis."""
    qc_payload = report_basis.get("qc_payload")
    benchmark_payload = report_basis.get("benchmark_payload")
    if (
        report_basis.get("state") != "current"
        or not isinstance(qc_payload, dict)
        or not isinstance(benchmark_payload, dict)
    ):
        raise RuntimeError("Dataset publish blocked: current benchmark/QC report basis required")
    benchmark_metrics = benchmark_payload.get("metrics")
    if not isinstance(benchmark_metrics, dict):
        raise RuntimeError("Dataset publish blocked: admitted benchmark metrics are unavailable")
    from polisyos.data_forge.domains.catalog.batch.pipeline import _derive_catalog_readiness

    derived = _derive_catalog_readiness(config, report_basis)
    readiness = derived["readiness"]
    thresholds = derived["thresholds"]
    blocking_source_statuses = derived["blocking_source_statuses"]
    evaluation_mode = str(report_basis["evaluation_mode"])
    bulk_equivalence_mismatch_rate = float(
        benchmark_metrics["benchmark_bulk_equivalence_mismatch_rate"]
    )
    bulk_equivalence_blocking_sources_total = int(
        benchmark_metrics["benchmark_bulk_equivalence_blocking_sources_total"]
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
        "evaluation_mode": evaluation_mode,
        "publish_mode": (
            "full-ready"
            if readiness["full_publish_ready"]
            else ("core-ready" if readiness["consumer_ready"] else "blocked")
        ),
        "bulk_equivalence_mismatch_rate": bulk_equivalence_mismatch_rate,
        "bulk_equivalence_blocking_sources_total": bulk_equivalence_blocking_sources_total,
        "report_basis": {
            key: report_basis[key]
            for key in (
                "state",
                "schema_version",
                "digest",
                "run_profile",
                "evaluation_mode",
                "benchmark_stage",
                "qc_stage",
            )
        },
    }
    config.consumer_readiness_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.consumer_readiness_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return config.consumer_readiness_path, readiness


def run_publish(config: DatasetBatchConfig) -> Path:
    """Write publish manifest with final dataset artifacts and checksums."""
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_catalog_report_basis,
    )

    started_at = datetime.now(UTC).isoformat()
    report_basis = current_catalog_report_basis(config)
    if report_basis.get("state") != "current":
        state = str(report_basis.get("state") or "not_established")
        reason = str(report_basis.get("reason") or "report_basis_not_current")
        raise RuntimeError(f"Dataset publish blocked: benchmark/QC report basis {state} ({reason})")
    consumer_readiness_path, readiness = _write_consumer_readiness_manifest(
        config,
        report_basis,
    )
    if not readiness["consumer_ready"]:
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
        consumer_readiness_path,
    ]
    artifacts.extend(generation_artifacts)
    existing = [path for path in artifacts if path.exists()]

    readiness_summary: dict[str, object] = {}
    source_publish_blocking: dict[str, bool] = {}
    rest_rows_by_source: dict[str, int] = {}
    rest_bytes_by_source: dict[str, int] = {}
    blocking_source_statuses: dict[str, str] = {}
    qc_payload = report_basis["qc_payload"]
    if isinstance(qc_payload, dict):
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
            source_publish_blocking = {
                str(key): bool(value)
                for key, value in (metrics.get("source_publish_blocking") or {}).items()
            }
            rest_rows_by_source = {
                str(key): int(value)
                for key, value in (metrics.get("rest_rows_by_source") or {}).items()
            }
            rest_bytes_by_source = {
                str(key): int(value)
                for key, value in (metrics.get("rest_bytes_by_source") or {}).items()
            }
    benchmark_payload = report_basis["benchmark_payload"]
    evaluation_mode = str(report_basis["evaluation_mode"])
    source_preflight_payload = (
        benchmark_payload.get("source_preflight")
        if isinstance(benchmark_payload.get("source_preflight"), dict)
        else {}
    )
    source_cases = (
        source_preflight_payload.get("sources")
        if isinstance(source_preflight_payload.get("sources"), list)
        else []
    )
    blocking_source_statuses = {
        str(case.get("source") or ""): str(case.get("status") or "")
        for case in source_cases
        if isinstance(case, dict) and str(case.get("source") or "").strip()
    }

    manifest_path = write_publish_manifest(
        manifest_path=config.publish_manifest_path,
        pipeline="datasets",
        artifacts=existing,
        qc_report_path=config.qc_report_path if config.qc_report_path.exists() else None,
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
            "consumer_readiness_manifest": str(consumer_readiness_path),
            "benchmark_report": str(config.benchmark_report_path)
            if config.benchmark_report_path.exists()
            else "",
            "consumer_ready": readiness["consumer_ready"],
            "full_publish_ready": readiness["full_publish_ready"],
            "evaluation_mode": evaluation_mode,
            "report_basis": {
                key: report_basis[key]
                for key in (
                    "state",
                    "schema_version",
                    "digest",
                    "run_profile",
                    "evaluation_mode",
                    "benchmark_stage",
                    "qc_stage",
                )
            },
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
