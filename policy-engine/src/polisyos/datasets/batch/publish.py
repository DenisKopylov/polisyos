"""Stage 8: publish dataset pipeline artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb

from polisyos.batch_common.manifest import write_publish_manifest, write_stage_manifest
from polisyos.datasets.batch.benchmark import readiness_thresholds_for_profile

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.datasets.batch.config import DatasetBatchConfig


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


def _write_consumer_readiness_manifest(config: DatasetBatchConfig) -> tuple[Path, dict[str, bool]]:
    qc_payload = _load_json(config.qc_report_path)
    benchmark_payload = _load_json(config.benchmark_report_path)
    benchmark_metrics = (
        benchmark_payload.get("metrics")
        if isinstance(benchmark_payload.get("metrics"), dict)
        else {}
    )
    evaluation_mode = (
        str(benchmark_payload.get("evaluation_mode") or "full-ready").strip() or "full-ready"
    )
    qc_passed = bool(qc_payload.get("passed")) if qc_payload else False
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
    blocking_source_statuses = {
        str(case.get("source") or ""): str(case.get("status") or "")
        for case in source_preflight_cases
        if isinstance(case, dict) and str(case.get("source") or "").strip()
    }
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
        "evaluation_mode": evaluation_mode,
        "publish_mode": (
            "full-ready"
            if readiness["full_publish_ready"]
            else ("core-ready" if readiness["consumer_ready"] else "blocked")
        ),
        "bulk_equivalence_mismatch_rate": bulk_equivalence_mismatch_rate,
        "bulk_equivalence_blocking_sources_total": bulk_equivalence_blocking_sources_total,
    }
    config.consumer_readiness_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.consumer_readiness_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return config.consumer_readiness_path, readiness


def run_publish(config: DatasetBatchConfig) -> Path:
    """Write publish manifest with final dataset artifacts and checksums."""
    started_at = datetime.now(UTC).isoformat()
    consumer_readiness_path, readiness = _write_consumer_readiness_manifest(config)
    if not readiness["consumer_ready"]:
        failed = sorted(name for name, passed in readiness.items() if not passed)
        raise RuntimeError(
            f"Dataset publish blocked: consumer readiness failed ({', '.join(failed)})"
        )

    artifacts = [
        config.db_path,
        config.index_dir / "ds_dataset_embeddings.npz",
        config.index_dir / "ds_dataset_index.hnsw",
        config.merged_records_path,
        config.duplicates_report_path,
        config.benchmark_report_path,
        config.qc_report_path,
        consumer_readiness_path,
    ]
    existing = [path for path in artifacts if path.exists()]

    readiness_summary: dict[str, object] = {}
    source_publish_blocking: dict[str, bool] = {}
    rest_rows_by_source: dict[str, int] = {}
    rest_bytes_by_source: dict[str, int] = {}
    blocking_source_statuses: dict[str, str] = {}
    if config.qc_report_path.exists():
        with open(config.qc_report_path, encoding="utf-8") as fh:
            qc_payload = json.load(fh)
        metrics = qc_payload.get("metrics") if isinstance(qc_payload, dict) else {}
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
    benchmark_payload = _load_json(config.benchmark_report_path)
    evaluation_mode = (
        str(benchmark_payload.get("evaluation_mode") or "full-ready").strip() or "full-ready"
    )
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
