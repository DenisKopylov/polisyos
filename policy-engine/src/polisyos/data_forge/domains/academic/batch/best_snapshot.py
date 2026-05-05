"""Assemble runtime-first academic snapshots from existing source snapshots."""

from __future__ import annotations

import contextlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.batch.benchmark import run_benchmark
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.embedder import run_embed
from polisyos.data_forge.domains.academic.batch.graph_builder import run_graph_index
from polisyos.data_forge.domains.academic.batch.publish import run_publish
from polisyos.data_forge.domains.academic.batch.qc import run_qc
from polisyos.data_forge.domains.academic.batch.transport_score import run_transport_score
from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    finalize_skg_version,
    next_skg_version,
)
from polisyos.data_forge.kernel.io import sha256_file
from polisyos.scientist.cross_graph.feedback import AcademicBenchmarkSuite, load_benchmark_suite

logger = get_logger(__name__)

_TIMESTAMP_FMT = "%Y%m%dT%H%M%SZ"

_REQUIRED_RUNTIME_FILES = (
    "graph/scholar_knowledge.duckdb",
    "ac_work_embeddings.npz",
    "ac_work_index.hnsw",
    "benchmark_suite.json",
    "benchmark_report.json",
    "runtime_demand_backlog.jsonl",
    "qc_report.json",
    "edge_synthesis_report.json",
    "canonical_review_queue.jsonl",
    "transport_scores.jsonl",
    "publish/manifest.json",
    "publish/academic_pipeline_readiness.json",
    "manifests/graph_index.json",
    "manifests/transport_score.json",
    "manifests/embed.json",
    "manifests/benchmark.json",
    "manifests/qc.json",
    "manifests/publish.json",
)

_REQUIRED_EVIDENCE_FILES = (
    "topic_selection/topics_catalog.jsonl",
    "topic_selection/selected_topic_works.jsonl",
    "topic_selection/selected_global_works.jsonl",
    "merged/all_records.jsonl",
    "merged/topic_links.jsonl",
    "fulltext_metadata_cache.jsonl",
    "fulltext_resolved.jsonl",
    "resolve_extract_final_results.jsonl",
    "article_extraction_results.jsonl",
    "context_attributes.jsonl",
    "context_attributes_clean.jsonl",
    "moderation_edges.jsonl",
    "moderation_edges_clean.jsonl",
    "simulation_ready_numeric_estimates.jsonl",
    "claim_adjudication_passes.jsonl",
    "claim_adjudications.jsonl",
    "claim_consensus_report.json",
    "claim_sets.jsonl",
    "conflict_sets.jsonl",
    "conflict_resolutions.jsonl",
    "raw_claim_candidates_final.jsonl",
    "published_claims_final.jsonl",
)

_ORIGINAL_COPY_FILES = _REQUIRED_EVIDENCE_FILES

_REMAP_COPY_FILES = (
    "canonical_review_queue.jsonl",
    "edge_synthesis_report.json",
)

_DIAGNOSTIC_COPY_SPECS = (
    ("original_root", "pipeline.log", "pipeline.log"),
    ("original_root", "pipeline_remaining.log", "pipeline_remaining.log"),
    ("remap_root", "auto_approve.log", "auto_approve.log"),
    ("original_component", "fulltext_fetch_log.jsonl", "fulltext_fetch_log.jsonl"),
    ("original_component", "llm_request_log.jsonl", "llm_request_log.jsonl"),
    ("original_component", "resolve_extract_errors.jsonl", "resolve_extract_errors.jsonl"),
    ("original_component", "resolve_extract_progress.json", "resolve_extract_progress.json"),
)

_ORIGINAL_DB_TABLES = (
    "ac_works",
    "ac_work_concepts",
    "ac_parameter_estimates",
    "ac_causal_claims_raw",
    "ac_claim_adjudications",
    "ac_causal_claims",
    "ac_runs",
    "ac_topics",
    "ac_topic_selections",
    "ac_article_extractions",
    "ac_boundary_conditions",
    "ac_ingest_errors",
    "ac_skg_articles",
    "ac_skg_edges",
    "ac_skg_edge_evidence",
    "ac_skg_context_attributes",
    "ac_skg_moderation_edges",
)

_REMAP_DB_TABLES = (
    "ac_skg_family_edges",
    "ac_skg_contested_edges",
    "ac_skg_parameters",
    "ac_skg_simulation_parameters",
)

_HYBRID_DB_TABLES = (
    "ac_skg_variables",
    "ac_skg_variable_synonyms",
    "ac_skg_canonization_cache",
)

_REBUILT_DB_TABLES = (
    "ac_skg_context_profiles",
    "ac_skg_transport_scores",
    "ac_skg_versions",
)

_VERSION_NORMALIZED_TABLES = frozenset(
    {
        "ac_skg_articles",
        "ac_skg_edge_evidence",
        "ac_skg_context_attributes",
        "ac_skg_moderation_edges",
    }
)

_RUNTIME_BEST_STAGES = frozenset(
    {"graph_index", "transport_score", "embed", "benchmark", "qc", "publish"}
)

_PROMOTION_GAIN_FLOORS = {
    "parameter_supported_ratio": 0.2632,
    "scholar_query_coverage_ratio": 0.2632,
    "causal_supported_plus_mixed_ratio": 0.2632,
    "non_default_transport_evidence_ratio": 0.2632,
    "family_edge_count": 15945.0,
    "review_queue_count": 94.0,
    "global_canonical_resolution_rate_pct": 98.604,
    "runtime_demanded_canonical_resolution_rate_pct": 100.0,
}


@dataclass(frozen=True)
class AcademicSnapshotSource:
    """Resolved paths for an existing academic snapshot source."""

    label: str
    snapshot_root: Path

    @property
    def component_dir(self) -> Path:
        return self.snapshot_root / "academic"

    @property
    def db_path(self) -> Path:
        return self.component_dir / "graph" / "scholar_knowledge.duckdb"

    @property
    def manifests_dir(self) -> Path:
        return self.component_dir / "manifests"

    @property
    def publish_manifest_path(self) -> Path:
        return self.component_dir / "publish" / "manifest.json"

    @property
    def readiness_report_path(self) -> Path:
        return self.component_dir / "publish" / "academic_pipeline_readiness.json"


@dataclass(frozen=True)
class RuntimeFirstSnapshotResult:
    """Result of assembling a runtime-first academic snapshot."""

    timestamp: str
    candidate_root: Path
    final_root: Path
    best_root: Path | None
    promoted: bool
    snapshot_version_id: int
    promotion_report_path: Path
    runtime_evidence_sources_path: Path


def build_runtime_first_snapshot(
    *,
    original_root: Path,
    remap_root: Path,
    backup_root: Path,
    output_root: Path,
    timestamp: str | None = None,
    benchmark_suite_path: Path | None = None,
    run_id: str | None = None,
    pass_name: str = "runtime_first_best",
    transport_target_context_id: str = "",
    transport_target_country_codes: tuple[str, ...] = ("UA",),
    transport_target_time_period: str = "",
    embedding_model: str = "intfloat/multilingual-e5-large",
    embedding_dimension: int = 1024,
    embedding_batch_size: int = 32,
    embedding_device: str = "mps",
    thermal: bool = False,
    promote_on_pass: bool = True,
) -> RuntimeFirstSnapshotResult:
    """Assemble a runtime-first academic snapshot and promote it when gates pass."""

    timestamp_value = str(timestamp or datetime.now(UTC).strftime(_TIMESTAMP_FMT)).strip()
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    candidate_root = output_root / f"policyos_academic_candidate_{timestamp_value}"
    best_root = output_root / f"policyos_academic_best_{timestamp_value}"
    if candidate_root.exists():
        raise FileExistsError(f"Candidate snapshot already exists: {candidate_root}")
    if best_root.exists():
        raise FileExistsError(f"Best snapshot already exists: {best_root}")

    sources = {
        "original": AcademicSnapshotSource(label="original", snapshot_root=Path(original_root)),
        "remap": AcademicSnapshotSource(label="remap", snapshot_root=Path(remap_root)),
        "backup": AcademicSnapshotSource(label="backup", snapshot_root=Path(backup_root)),
    }
    _validate_sources(sources)

    candidate_root.mkdir(parents=True, exist_ok=True)
    candidate_meta_dir = candidate_root / "meta"
    candidate_diag_dir = candidate_root / "diagnostics"
    candidate_meta_dir.mkdir(parents=True, exist_ok=True)
    candidate_diag_dir.mkdir(parents=True, exist_ok=True)

    candidate_config = AcademicBatchConfig(
        snapshot_root=candidate_root,
        stages=_RUNTIME_BEST_STAGES,
        run_id=str(run_id or timestamp_value),
        pass_name=pass_name,
        transport_target_context_id=transport_target_context_id,
        transport_target_country_codes=transport_target_country_codes,
        transport_target_time_period=transport_target_time_period,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_batch_size=embedding_batch_size,
        embedding_device=embedding_device,
        fail_fast_qc=False,
    )

    assembly_entries: list[dict[str, Any]] = []
    _copy_runtime_files(candidate_config, sources["original"], sources["remap"], assembly_entries)
    suite_source = _materialize_benchmark_suite(
        candidate_config=candidate_config,
        original_source=sources["original"],
        backup_source=sources["backup"],
        explicit_suite_path=Path(benchmark_suite_path)
        if benchmark_suite_path is not None
        else None,
        assembly_entries=assembly_entries,
    )
    _copy_source_manifests(candidate_root, sources, assembly_entries)
    _copy_diagnostics(candidate_root, sources["original"], sources["remap"], assembly_entries)

    snapshot_version_id = _assemble_duckdb(
        candidate_db_path=candidate_config.db_path,
        original_db_path=sources["original"].db_path,
        remap_db_path=sources["remap"].db_path,
        assembly_entries=assembly_entries,
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/graph/scholar_knowledge.duckdb",
        source_snapshot="assembled",
        authoritative_for_runtime=True,
        notes=f"rebuilt from table-level sources with normalized skg_version={snapshot_version_id}",
    )

    _seal_snapshot(candidate_config, thermal=thermal, assembly_entries=assembly_entries)

    candidate_functional_checks = _run_functional_checks(
        candidate_config, expected_version_id=snapshot_version_id
    )
    candidate_manifest_consistency = _validate_publish_manifest(
        candidate_config.publish_manifest_path
    )
    candidate_comparison = _build_snapshot_comparison(
        candidate_config=candidate_config,
        original_source=sources["original"],
        backup_source=sources["backup"],
        candidate_manifest_consistency=candidate_manifest_consistency,
    )
    promotion_report = _evaluate_promotion(
        candidate_comparison=candidate_comparison,
        functional_checks=candidate_functional_checks,
        manifest_consistency=candidate_manifest_consistency,
        promote_on_pass=promote_on_pass,
    )

    if promotion_report["promoted"]:
        logger.info("Promotion gates passed; promoting candidate snapshot to %s", best_root)
        candidate_root.rename(best_root)
        _rewrite_json_tree(best_root, old_root=candidate_root, new_root=best_root)

        best_config = AcademicBatchConfig(
            snapshot_root=best_root,
            stages=_RUNTIME_BEST_STAGES,
            run_id=str(run_id or timestamp_value),
            pass_name=pass_name,
            transport_target_context_id=transport_target_context_id,
            transport_target_country_codes=transport_target_country_codes,
            transport_target_time_period=transport_target_time_period,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            embedding_batch_size=embedding_batch_size,
            embedding_device=embedding_device,
            fail_fast_qc=False,
        )
        # Refresh path-bearing reports and dependent manifest hashes under the final root.
        run_benchmark(best_config)
        run_qc(best_config, fail_fast=False)
        run_publish(best_config)

        final_functional_checks = _run_functional_checks(
            best_config, expected_version_id=snapshot_version_id
        )
        final_manifest_consistency = _validate_publish_manifest(best_config.publish_manifest_path)
        final_comparison = _build_snapshot_comparison(
            candidate_config=best_config,
            original_source=sources["original"],
            backup_source=sources["backup"],
            candidate_manifest_consistency=final_manifest_consistency,
        )
        promotion_report = _evaluate_promotion(
            candidate_comparison=final_comparison,
            functional_checks=final_functional_checks,
            manifest_consistency=final_manifest_consistency,
            promote_on_pass=True,
        )
        promotion_report["promoted"] = bool(promotion_report["promoted"])
        promotion_report["promoted_to"] = str(best_root)
        final_root = best_root
        final_config = best_config
        final_manifest_consistency_payload = final_manifest_consistency
        final_functional_checks_payload = final_functional_checks
        final_comparison_payload = final_comparison
    else:
        promotion_report["promoted_to"] = ""
        final_root = candidate_root
        final_config = candidate_config
        final_manifest_consistency_payload = candidate_manifest_consistency
        final_functional_checks_payload = candidate_functional_checks
        final_comparison_payload = candidate_comparison

    promotion_report["final_root"] = str(final_root)
    promotion_report["snapshot_version_id"] = snapshot_version_id
    promotion_report["suite_source"] = suite_source
    promotion_report["functional_checks"] = final_functional_checks_payload
    promotion_report["manifest_consistency"] = final_manifest_consistency_payload
    promotion_report["comparison"] = final_comparison_payload

    _write_meta_files(
        final_root=final_root,
        final_config=final_config,
        sources=sources,
        snapshot_version_id=snapshot_version_id,
        suite_source=suite_source,
        assembly_entries=assembly_entries,
        promotion_report=promotion_report,
    )

    return RuntimeFirstSnapshotResult(
        timestamp=timestamp_value,
        candidate_root=candidate_root,
        final_root=final_root,
        best_root=(final_root if final_root == best_root else None),
        promoted=bool(promotion_report["promoted"]),
        snapshot_version_id=snapshot_version_id,
        promotion_report_path=final_root / "meta" / "promotion_report.json",
        runtime_evidence_sources_path=final_root / "meta" / "runtime_evidence_sources.json",
    )


def _validate_sources(sources: dict[str, AcademicSnapshotSource]) -> None:
    for label, source in sources.items():
        if not source.snapshot_root.exists():
            raise FileNotFoundError(f"{label} snapshot root does not exist: {source.snapshot_root}")
        if not source.component_dir.exists():
            raise FileNotFoundError(
                f"{label} academic component is missing: {source.component_dir}"
            )
    if not sources["original"].db_path.exists():
        raise FileNotFoundError(f"Original DB is missing: {sources['original'].db_path}")
    if not sources["remap"].db_path.exists():
        raise FileNotFoundError(f"Remap DB is missing: {sources['remap'].db_path}")


def _copy_runtime_files(
    candidate_config: AcademicBatchConfig,
    original_source: AcademicSnapshotSource,
    remap_source: AcademicSnapshotSource,
    assembly_entries: list[dict[str, Any]],
) -> None:
    for rel in _ORIGINAL_COPY_FILES:
        _copy_file(
            src=original_source.component_dir / rel,
            dst=candidate_config.component_dir / rel,
            path_in_snapshot=f"academic/{rel}",
            source_snapshot=original_source.label,
            authoritative_for_runtime=rel.endswith(".jsonl") or rel.endswith(".json"),
            notes="copied from original evidence/provenance layer",
            required=True,
            assembly_entries=assembly_entries,
        )
    for rel in _REMAP_COPY_FILES:
        _copy_file(
            src=remap_source.component_dir / rel,
            dst=candidate_config.component_dir / rel,
            path_in_snapshot=f"academic/{rel}",
            source_snapshot=remap_source.label,
            authoritative_for_runtime=True,
            notes="copied from remap runtime-improvement layer",
            required=True,
            assembly_entries=assembly_entries,
        )


def _materialize_benchmark_suite(
    *,
    candidate_config: AcademicBatchConfig,
    original_source: AcademicSnapshotSource,
    backup_source: AcademicSnapshotSource,
    explicit_suite_path: Path | None,
    assembly_entries: list[dict[str, Any]],
) -> str:
    target_path = candidate_config.benchmark_suite_path
    if explicit_suite_path is not None:
        _copy_file(
            src=explicit_suite_path,
            dst=target_path,
            path_in_snapshot="academic/benchmark_suite.json",
            source_snapshot="explicit",
            authoritative_for_runtime=True,
            notes="copied from explicit benchmark suite override",
            required=True,
            assembly_entries=assembly_entries,
        )
        return "explicit"
    for source in (original_source, backup_source):
        suite_path = source.component_dir / "benchmark_suite.json"
        if suite_path.exists():
            _copy_file(
                src=suite_path,
                dst=target_path,
                path_in_snapshot="academic/benchmark_suite.json",
                source_snapshot=source.label,
                authoritative_for_runtime=True,
                notes="copied benchmark suite for no-regression comparison",
                required=True,
                assembly_entries=assembly_entries,
            )
            return source.label

    # Let the benchmark stage use the same default suite logic as the runtime pipeline.
    suite = _load_default_suite()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(suite.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/benchmark_suite.json",
        source_snapshot="default",
        authoritative_for_runtime=True,
        notes="materialized current default academic benchmark suite",
    )
    return "default"


def _load_default_suite() -> AcademicBenchmarkSuite:
    from polisyos.data_forge.domains.academic.batch.benchmark import _default_suite

    return _default_suite()


def _copy_source_manifests(
    candidate_root: Path,
    sources: dict[str, AcademicSnapshotSource],
    assembly_entries: list[dict[str, Any]],
) -> None:
    meta_root = candidate_root / "meta" / "source_manifests"
    for label, source in sources.items():
        dest_dir = meta_root / label
        dest_dir.mkdir(parents=True, exist_ok=True)
        if source.manifests_dir.exists():
            for src_file in sorted(source.manifests_dir.glob("*.json")):
                rel = Path("meta") / "source_manifests" / label / "manifests" / src_file.name
                _copy_file(
                    src=src_file,
                    dst=candidate_root / rel,
                    path_in_snapshot=str(rel).replace("\\", "/"),
                    source_snapshot=label,
                    authoritative_for_runtime=False,
                    notes="reference-only source stage manifest",
                    required=False,
                    assembly_entries=assembly_entries,
                )
        for src_file, file_name in (
            (source.publish_manifest_path, "publish_manifest.json"),
            (source.readiness_report_path, "academic_pipeline_readiness.json"),
        ):
            if src_file.exists():
                rel = Path("meta") / "source_manifests" / label / file_name
                _copy_file(
                    src=src_file,
                    dst=candidate_root / rel,
                    path_in_snapshot=str(rel).replace("\\", "/"),
                    source_snapshot=label,
                    authoritative_for_runtime=False,
                    notes="reference-only source publish metadata",
                    required=False,
                    assembly_entries=assembly_entries,
                )


def _copy_diagnostics(
    candidate_root: Path,
    original_source: AcademicSnapshotSource,
    remap_source: AcademicSnapshotSource,
    assembly_entries: list[dict[str, Any]],
) -> None:
    for source_kind, source_rel, dest_rel in _DIAGNOSTIC_COPY_SPECS:
        if source_kind == "original_root":
            src = original_source.snapshot_root / source_rel
        elif source_kind == "remap_root":
            src = remap_source.snapshot_root / source_rel
        elif source_kind == "original_component":
            src = original_source.component_dir / source_rel
        else:
            raise ValueError(f"Unsupported diagnostic source kind: {source_kind}")
        dst = candidate_root / "diagnostics" / dest_rel
        _copy_file(
            src=src,
            dst=dst,
            path_in_snapshot=f"diagnostics/{dest_rel}",
            source_snapshot="original" if "original" in source_kind else "remap",
            authoritative_for_runtime=False,
            notes="reference-only diagnostic artifact",
            required=False,
            assembly_entries=assembly_entries,
        )


def _copy_file(
    *,
    src: Path,
    dst: Path,
    path_in_snapshot: str,
    source_snapshot: str,
    authoritative_for_runtime: bool,
    notes: str,
    required: bool,
    assembly_entries: list[dict[str, Any]],
) -> None:
    if not src.exists():
        if required:
            raise FileNotFoundError(f"Required source artifact is missing: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assembly_entries.append(
        {
            "path": path_in_snapshot,
            "mode": "copied",
            "source_snapshot": source_snapshot,
            "source_path": str(src),
            "authoritative_for_runtime": authoritative_for_runtime,
            "notes": notes,
        }
    )


def _assemble_duckdb(
    *,
    candidate_db_path: Path,
    original_db_path: Path,
    remap_db_path: Path,
    assembly_entries: list[dict[str, Any]],
) -> int:
    candidate_db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(candidate_db_path))
    try:
        ensure_skg_schema(con)
        _attach_database(con, alias="original_src", db_path=original_db_path)
        _attach_database(con, alias="remap_src", db_path=remap_db_path)

        version_id = next_skg_version(con, description="policyos academic runtime-first assembly")

        for table_name in _ORIGINAL_DB_TABLES:
            if table_name.startswith("ac_skg_"):
                _replace_table_contents(
                    con,
                    target_table=table_name,
                    source_alias="original_src",
                    source_table=table_name,
                    version_id=version_id if table_name in _VERSION_NORMALIZED_TABLES else None,
                )
            else:
                _clone_non_skg_table(
                    con,
                    source_alias="original_src",
                    table_name=table_name,
                )
            assembly_entries.append(
                {
                    "path": f"academic/graph/scholar_knowledge.duckdb::table/{table_name}",
                    "mode": "rebuilt",
                    "source_snapshot": "original",
                    "source_path": f"{original_db_path}::{table_name}",
                    "authoritative_for_runtime": True,
                    "notes": (
                        f"copied table with normalized skg_version={version_id}"
                        if table_name in _VERSION_NORMALIZED_TABLES
                        else "copied table as authoritative original corpus/search layer"
                    ),
                }
            )

        for table_name in _REMAP_DB_TABLES:
            _replace_table_contents(
                con,
                target_table=table_name,
                source_alias="remap_src",
                source_table=table_name,
                version_id=None,
            )
            assembly_entries.append(
                {
                    "path": f"academic/graph/scholar_knowledge.duckdb::table/{table_name}",
                    "mode": "rebuilt",
                    "source_snapshot": "remap",
                    "source_path": f"{remap_db_path}::{table_name}",
                    "authoritative_for_runtime": True,
                    "notes": "copied table as authoritative remap canonical/runtime-improvement layer",
                }
            )

        hybrid_stats = _rebuild_hybrid_runtime_tables(
            con,
            original_alias="original_src",
            remap_alias="remap_src",
        )
        for table_name in _HYBRID_DB_TABLES:
            table_stats = hybrid_stats.get(table_name, {})
            stats_note = ", ".join(f"{key}={value}" for key, value in sorted(table_stats.items()))
            assembly_entries.append(
                {
                    "path": f"academic/graph/scholar_knowledge.duckdb::table/{table_name}",
                    "mode": "rebuilt",
                    "source_snapshot": "hybrid(original+remap)",
                    "source_path": f"{original_db_path}::{table_name};{remap_db_path}::{table_name}",
                    "authoritative_for_runtime": True,
                    "notes": (
                        "rebuilt hybrid canonical/runtime table from original+remap"
                        + (f" ({stats_note})" if stats_note else "")
                    ),
                }
            )

        for table_name in _REBUILT_DB_TABLES:
            if table_name == "ac_skg_versions":
                continue
            con.execute(f'DELETE FROM "{table_name}"')
            assembly_entries.append(
                {
                    "path": f"academic/graph/scholar_knowledge.duckdb::table/{table_name}",
                    "mode": "rebuilt",
                    "source_snapshot": "candidate_runtime",
                    "source_path": "",
                    "authoritative_for_runtime": True,
                    "notes": "left empty for downstream rebuild stage",
                }
            )

        finalize_skg_version(
            con,
            version_id=version_id,
            n_articles=_table_count(con, "ac_skg_articles"),
            n_edges=_table_count(con, "ac_skg_edges"),
            n_variables=_table_count(con, "ac_skg_variables"),
        )
        con.execute("CHECKPOINT")
        return version_id
    finally:
        with contextlib.suppress(duckdb.Error):
            con.execute("DETACH remap_src")
        with contextlib.suppress(duckdb.Error):
            con.execute("DETACH original_src")
        con.close()


def _attach_database(con: duckdb.DuckDBPyConnection, *, alias: str, db_path: Path) -> None:
    escaped = str(db_path).replace("'", "''")
    con.execute(f"ATTACH '{escaped}' AS {alias}")


def _clone_non_skg_table(
    con: duckdb.DuckDBPyConnection,
    *,
    source_alias: str,
    table_name: str,
) -> None:
    if not _table_exists(con, f"{source_alias}.{table_name}"):
        raise FileNotFoundError(f"Missing source table: {source_alias}.{table_name}")
    con.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM {source_alias}."{table_name}"')


def _replace_table_contents(
    con: duckdb.DuckDBPyConnection,
    *,
    target_table: str,
    source_alias: str,
    source_table: str,
    version_id: int | None,
) -> None:
    if not _table_exists(con, f"{source_alias}.{source_table}"):
        raise FileNotFoundError(f"Missing source table: {source_alias}.{source_table}")
    if not _table_exists(con, target_table):
        raise FileNotFoundError(f"Missing target table schema: {target_table}")

    source_columns = set(_table_columns(con, f"{source_alias}.{source_table}"))
    target_columns = _table_columns(con, target_table)
    insert_columns: list[str] = []
    select_exprs: list[str] = []
    for column_name in target_columns:
        if column_name == "skg_version" and version_id is not None:
            insert_columns.append(column_name)
            select_exprs.append(f"{int(version_id)} AS skg_version")
        elif column_name in source_columns:
            insert_columns.append(column_name)
            select_exprs.append(f'{source_alias}."{source_table}"."{column_name}"')

    con.execute(f'DELETE FROM "{target_table}"')
    if not insert_columns:
        raise RuntimeError(
            f"No compatible columns found when copying {source_alias}.{source_table} -> {target_table}"
        )
    insert_sql = ", ".join(f'"{name}"' for name in insert_columns)
    select_sql = ", ".join(select_exprs)
    con.execute(
        f'INSERT INTO "{target_table}" ({insert_sql}) SELECT {select_sql} FROM {source_alias}."{source_table}"'
    )


def _rebuild_hybrid_runtime_tables(
    con: duckdb.DuckDBPyConnection,
    *,
    original_alias: str,
    remap_alias: str,
) -> dict[str, dict[str, int]]:
    variable_stats, final_variable_rows = _rebuild_hybrid_variables(
        con,
        original_alias=original_alias,
        remap_alias=remap_alias,
    )
    synonym_stats, final_synonym_rows = _rebuild_hybrid_variable_synonyms(
        con,
        original_alias=original_alias,
        remap_alias=remap_alias,
        valid_canonical_names={
            _clean_text(row.get("canonical_name"))
            for row in final_variable_rows
            if _clean_text(row.get("canonical_name"))
        },
    )
    cache_stats = _rebuild_hybrid_canonization_cache(
        con,
        original_alias=original_alias,
        remap_alias=remap_alias,
        final_variable_rows=final_variable_rows,
        final_synonym_rows=final_synonym_rows,
    )
    return {
        "ac_skg_variables": variable_stats,
        "ac_skg_variable_synonyms": synonym_stats,
        "ac_skg_canonization_cache": cache_stats,
    }


def _rebuild_hybrid_variables(
    con: duckdb.DuckDBPyConnection,
    *,
    original_alias: str,
    remap_alias: str,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    original_rows = _fetch_table_rows(con, f'{original_alias}."ac_skg_variables"')
    remap_rows = _fetch_table_rows(con, f'{remap_alias}."ac_skg_variables"')

    original_by_name = {
        canonical_name: row
        for row in original_rows
        if (canonical_name := _clean_text(row.get("canonical_name")))
    }
    remap_by_name = {
        canonical_name: row
        for row in remap_rows
        if (canonical_name := _clean_text(row.get("canonical_name")))
    }

    final_names = set(remap_by_name)
    changed = True
    while changed:
        changed = False
        for canonical_name, row in original_by_name.items():
            if canonical_name in final_names:
                continue
            approved_target = _non_self_approved_target(row)
            if approved_target and approved_target in final_names:
                final_names.add(canonical_name)
                changed = True

    final_rows: list[dict[str, Any]] = []
    override_count = 0
    for canonical_name in sorted(remap_by_name):
        row = dict(remap_by_name[canonical_name])
        original_row = original_by_name.get(canonical_name)
        original_target = _non_self_approved_target(original_row)
        remap_target = _non_self_approved_target(row)
        if original_target and not remap_target and original_target in final_names:
            row["approved_canonical_name"] = original_target
            override_count += 1
        final_rows.append(row)

    inserted_count = 0
    for canonical_name in sorted(final_names):
        if canonical_name in remap_by_name:
            continue
        original_row = original_by_name.get(canonical_name)
        approved_target = _non_self_approved_target(original_row)
        if original_row is None or not approved_target or approved_target not in final_names:
            continue
        final_rows.append(dict(original_row))
        inserted_count += 1

    _insert_dict_rows(con, "ac_skg_variables", final_rows)
    return (
        {
            "remap_rows_kept": len(remap_by_name),
            "original_bridge_overrides_applied": override_count,
            "original_only_bridge_rows_inserted": inserted_count,
            "final_row_count": len(final_rows),
        },
        final_rows,
    )


def _rebuild_hybrid_variable_synonyms(
    con: duckdb.DuckDBPyConnection,
    *,
    original_alias: str,
    remap_alias: str,
    valid_canonical_names: set[str],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    original_rows = _fetch_table_rows(con, f'{original_alias}."ac_skg_variable_synonyms"')
    remap_rows = _fetch_table_rows(con, f'{remap_alias}."ac_skg_variable_synonyms"')

    remap_by_key = {
        key: row
        for row in remap_rows
        if (key := _synonym_key(row)) is not None and key[1] in valid_canonical_names
    }
    original_by_key = {
        key: row
        for row in original_rows
        if (key := _synonym_key(row)) is not None and key[1] in valid_canonical_names
    }

    final_rows = [dict(remap_by_key[key]) for key in sorted(remap_by_key)]
    inserted_count = 0
    for key in sorted(original_by_key):
        if key in remap_by_key:
            continue
        final_rows.append(dict(original_by_key[key]))
        inserted_count += 1

    _insert_dict_rows(con, "ac_skg_variable_synonyms", final_rows)
    return (
        {
            "remap_rows_kept": len(remap_by_key),
            "original_only_synonym_rows_inserted": inserted_count,
            "final_row_count": len(final_rows),
        },
        final_rows,
    )


def _rebuild_hybrid_canonization_cache(
    con: duckdb.DuckDBPyConnection,
    *,
    original_alias: str,
    remap_alias: str,
    final_variable_rows: list[dict[str, Any]],
    final_synonym_rows: list[dict[str, Any]],
) -> dict[str, int]:
    original_rows = _fetch_table_rows(con, f'{original_alias}."ac_skg_canonization_cache"')
    remap_rows = _fetch_table_rows(con, f'{remap_alias}."ac_skg_canonization_cache"')
    final_variables_by_name = {
        canonical_name: row
        for row in final_variable_rows
        if (canonical_name := _clean_text(row.get("canonical_name")))
    }

    rows_by_raw: dict[str, dict[str, Any]] = {}
    self_inserted = 0
    for canonical_name in sorted(final_variables_by_name):
        if _upsert_cache_row(
            rows_by_raw,
            raw_name=canonical_name,
            canonical_name=canonical_name,
            approved=True,
            source_row={},
            valid_canonical_names=set(final_variables_by_name),
        ):
            self_inserted += 1

    synonym_inserted = 0
    for row in final_synonym_rows:
        if not bool(row.get("approved")):
            continue
        raw_name = _clean_text(row.get("synonym"))
        canonical_name = _clean_text(row.get("canonical_name"))
        if raw_name in rows_by_raw:
            continue
        if _upsert_cache_row(
            rows_by_raw,
            raw_name=raw_name,
            canonical_name=canonical_name,
            approved=bool(row.get("approved")),
            source_row=row,
            valid_canonical_names=set(final_variables_by_name),
        ):
            synonym_inserted += 1

    original_overlay_count = 0
    for row in original_rows:
        raw_name = _clean_text(row.get("raw_name"))
        canonical_name = _clean_text(row.get("canonical_name"))
        if not raw_name or not canonical_name:
            continue
        current = rows_by_raw.get(raw_name)
        if current is not None and _clean_text(current.get("canonical_name")) == canonical_name:
            continue
        if not _cache_overlay_allowed(canonical_name, final_variables_by_name):
            continue
        if _upsert_cache_row(
            rows_by_raw,
            raw_name=raw_name,
            canonical_name=canonical_name,
            approved=bool(row.get("approved")),
            source_row=row,
            valid_canonical_names=set(final_variables_by_name),
        ):
            original_overlay_count += 1

    remap_fill_count = 0
    for row in remap_rows:
        raw_name = _clean_text(row.get("raw_name"))
        canonical_name = _clean_text(row.get("canonical_name"))
        if not raw_name or raw_name in rows_by_raw:
            continue
        if _upsert_cache_row(
            rows_by_raw,
            raw_name=raw_name,
            canonical_name=canonical_name,
            approved=bool(row.get("approved")),
            source_row=row,
            valid_canonical_names=set(final_variables_by_name),
        ):
            remap_fill_count += 1

    final_rows = [rows_by_raw[raw_name] for raw_name in sorted(rows_by_raw)]
    _insert_dict_rows(con, "ac_skg_canonization_cache", final_rows)
    return {
        "self_rows_inserted": self_inserted,
        "approved_synonym_rows_inserted": synonym_inserted,
        "original_cache_overlays_applied": original_overlay_count,
        "remap_cache_fill_rows_inserted": remap_fill_count,
        "final_row_count": len(final_rows),
    }


def _fetch_table_rows(
    con: duckdb.DuckDBPyConnection,
    qualified_table: str,
) -> list[dict[str, Any]]:
    if not _table_exists(con, qualified_table):
        return []
    cursor = con.execute(f"SELECT * FROM {qualified_table}")
    columns = [str(column[0]) for column in cursor.description or []]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _insert_dict_rows(
    con: duckdb.DuckDBPyConnection,
    target_table: str,
    rows: list[dict[str, Any]],
) -> None:
    if not _table_exists(con, target_table):
        raise FileNotFoundError(f"Missing target table schema: {target_table}")
    target_columns = _table_columns(con, target_table)
    con.execute(f'DELETE FROM "{target_table}"')
    if not rows:
        return
    insert_columns = [column for column in target_columns if any(column in row for row in rows)]
    if not insert_columns:
        raise RuntimeError(f"No compatible columns found when inserting into {target_table}")
    placeholders = ", ".join(["?"] * len(insert_columns))
    insert_sql = ", ".join(f'"{name}"' for name in insert_columns)
    values = [tuple(row.get(column) for column in insert_columns) for row in rows]
    con.executemany(
        f'INSERT INTO "{target_table}" ({insert_sql}) VALUES ({placeholders})',
        values,
    )


def _synonym_key(row: dict[str, Any]) -> tuple[str, str] | None:
    synonym = _clean_text(row.get("synonym"))
    canonical_name = _clean_text(row.get("canonical_name"))
    if not synonym or not canonical_name:
        return None
    return (synonym, canonical_name)


def _upsert_cache_row(
    rows_by_raw: dict[str, dict[str, Any]],
    *,
    raw_name: str,
    canonical_name: str,
    approved: bool,
    source_row: dict[str, Any],
    valid_canonical_names: set[str],
) -> bool:
    if not raw_name or not canonical_name or canonical_name not in valid_canonical_names:
        return False
    row = dict(source_row)
    row["raw_name"] = raw_name
    row["canonical_name"] = canonical_name
    row["approved"] = bool(approved)
    rows_by_raw[raw_name] = row
    return True


def _cache_overlay_allowed(
    canonical_name: str,
    final_variables_by_name: dict[str, dict[str, Any]],
) -> bool:
    row = final_variables_by_name.get(canonical_name)
    return bool(_non_self_approved_target(row))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _non_self_approved_target(row: dict[str, Any] | None) -> str:
    if row is None:
        return ""
    canonical_name = _clean_text(row.get("canonical_name"))
    approved_target = _clean_text(row.get("approved_canonical_name"))
    if not approved_target or approved_target == canonical_name:
        return ""
    return approved_target


def _table_exists(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"SELECT * FROM {qualified_table} LIMIT 0")
    except duckdb.Error:
        return False
    return True


def _table_columns(con: duckdb.DuckDBPyConnection, qualified_table: str) -> list[str]:
    cursor = con.execute(f"SELECT * FROM {qualified_table} LIMIT 0")
    return [str(column[0]) for column in cursor.description or []]


def _table_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    return int(con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])


def _seal_snapshot(
    config: AcademicBatchConfig,
    *,
    thermal: bool,
    assembly_entries: list[dict[str, Any]],
) -> None:
    run_graph_index(config)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/graph_index.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during graph_index sealing",
    )

    run_transport_score(config)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/transport_scores.jsonl",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="transport scores rebuilt from assembled DB",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/transport_score.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during transport_score sealing",
    )

    run_embed(config, thermal=thermal)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/ac_work_embeddings.npz",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="embeddings rebuilt from assembled ac_works table",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/ac_work_index.hnsw",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="HNSW index rebuilt from assembled ac_works table",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/embed.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during embed sealing",
    )

    run_benchmark(config)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/benchmark_report.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="benchmark report rebuilt against assembled runtime snapshot",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/runtime_demand_backlog.jsonl",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="runtime demand backlog rebuilt from benchmark suite",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/benchmark.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during benchmark sealing",
    )

    run_qc(config, fail_fast=False)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/qc_report.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="QC report rebuilt against assembled runtime snapshot",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/qc.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during qc sealing",
    )

    run_publish(config)
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/publish/academic_pipeline_readiness.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="readiness manifest rebuilt against assembled runtime snapshot",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/publish/manifest.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="publish manifest rebuilt against assembled runtime snapshot",
    )
    _record_rebuilt_entry(
        assembly_entries,
        path="academic/manifests/publish.json",
        source_snapshot="candidate_runtime",
        authoritative_for_runtime=True,
        notes="stage manifest rebuilt during publish sealing",
    )


def _record_rebuilt_entry(
    assembly_entries: list[dict[str, Any]],
    *,
    path: str,
    source_snapshot: str,
    authoritative_for_runtime: bool,
    notes: str,
) -> None:
    assembly_entries.append(
        {
            "path": path,
            "mode": "rebuilt",
            "source_snapshot": source_snapshot,
            "source_path": "",
            "authoritative_for_runtime": authoritative_for_runtime,
            "notes": notes,
        }
    )


def _run_functional_checks(
    config: AcademicBatchConfig,
    *,
    expected_version_id: int,
) -> dict[str, Any]:
    sample = _sample_runtime_targets(config)
    checks: dict[str, dict[str, Any]] = {}

    query = SKGQuery(db_path=config.db_path, index_dir=config.index_dir)
    try:
        checks["query_prior"] = _guarded_check(
            lambda: {
                "estimate_count": len(
                    query.query_prior(variable=sample["parameter_name"]).estimates
                )
            }
        )
        checks["query_parameters"] = _guarded_check(
            lambda: {"candidate_count": len(query.query_parameters(sample["parameter_name"]))}
        )
        checks["query_edge_support"] = _guarded_check(
            lambda: {
                "result_count": len(
                    query.query_edge_support(
                        cause=sample["cause"],
                        effect=sample["effect"],
                        support_mode="hybrid",
                    )
                )
            }
        )
        checks["latest_skg_version_id"] = _guarded_check(
            lambda: {
                "version_id": query.latest_skg_version_id(),
                "expected_version_id": expected_version_id,
                "matches_expected": query.latest_skg_version_id() == expected_version_id,
            },
            require_true_key="matches_expected",
        )
        checks["skg_snapshot_ref"] = _guarded_check(
            lambda: {
                "snapshot_ref": query.skg_snapshot_ref(),
                "matches_expected": query.skg_snapshot_ref()
                == f"duckdb://{config.db_path}#v{expected_version_id}",
            },
            require_true_key="matches_expected",
        )
    finally:
        query.close()

    graph = ScholarKnowledgeGraph(db_path=config.db_path, index_dir=config.index_dir)
    try:
        checks["find_relevant_works"] = _guarded_check(
            lambda: {
                "result_count": len(graph.find_relevant_works(sample["search_query"], top_k=3))
            }
        )
        checks["find_causal_evidence"] = _guarded_check(
            lambda: {
                "result_count": len(
                    graph.find_causal_evidence(
                        sample["cause"],
                        sample["effect"],
                        min_trust=0.0,
                        support_mode="hybrid",
                    )
                )
            }
        )
    finally:
        graph.close()

    all_passed = all(bool(payload.get("passed")) for payload in checks.values())
    return {
        "passed": all_passed,
        "sample": sample,
        "checks": checks,
    }


def _guarded_check(
    fn,
    *,
    require_true_key: str | None = None,
) -> dict[str, Any]:
    try:
        payload = dict(fn())
    except Exception as exc:  # pragma: no cover - defensive reporting path
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    passed = True
    if require_true_key is not None:
        passed = bool(payload.get(require_true_key))
    return {"passed": passed, **payload}


def _sample_runtime_targets(config: AcademicBatchConfig) -> dict[str, str]:
    suite_path = config.benchmark_suite_path
    try:
        suite = load_benchmark_suite(suite_path) if suite_path.exists() else None
    except Exception:
        suite = None

    parameter_name = ""
    cause = ""
    effect = ""
    if suite is not None:
        for scenario in suite.scenarios:
            if not parameter_name and scenario.parameters:
                parameter_name = str(scenario.parameters[0])
            if (not cause or not effect) and scenario.causal_edges:
                cause = str(scenario.causal_edges[0].cause)
                effect = str(scenario.causal_edges[0].effect)
            if parameter_name and cause and effect:
                break

    with duckdb.connect(str(config.db_path), read_only=True) as con:
        if not parameter_name:
            try:
                row = con.execute(
                    "SELECT canonical_name FROM ac_skg_simulation_parameters LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    parameter_name = str(row[0])
            except duckdb.Error:
                parameter_name = ""
        if not parameter_name:
            try:
                row = con.execute(
                    "SELECT variable_name FROM ac_parameter_estimates LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    parameter_name = str(row[0])
            except duckdb.Error:
                parameter_name = ""
        if not cause or not effect:
            try:
                row = con.execute("SELECT src, dst FROM ac_skg_edges LIMIT 1").fetchone()
                if row:
                    cause = cause or str(row[0] or "")
                    effect = effect or str(row[1] or "")
            except duckdb.Error:
                cause = cause or ""
                effect = effect or ""
        if not cause or not effect:
            try:
                row = con.execute(
                    "SELECT src_family, dst_family FROM ac_skg_family_edges LIMIT 1"
                ).fetchone()
                if row:
                    cause = cause or str(row[0] or "")
                    effect = effect or str(row[1] or "")
            except duckdb.Error:
                pass
        try:
            row = con.execute(
                "SELECT title FROM ac_works WHERE title IS NOT NULL AND title != '' LIMIT 1"
            ).fetchone()
            search_query = str(row[0]) if row and row[0] else f"{cause} {effect}".strip()
        except duckdb.Error:
            search_query = f"{cause} {effect}".strip()

    return {
        "parameter_name": parameter_name or "tax_revenue",
        "cause": cause or "tax_revenue",
        "effect": effect or "economic.gdp_growth",
        "search_query": search_query or f"{cause} {effect}".strip() or "policy evidence",
    }


def _build_snapshot_comparison(
    *,
    candidate_config: AcademicBatchConfig,
    original_source: AcademicSnapshotSource,
    backup_source: AcademicSnapshotSource,
    candidate_manifest_consistency: dict[str, Any],
) -> dict[str, Any]:
    candidate_summary = _snapshot_summary(
        snapshot_root=candidate_config.snapshot_root,
        component_dir=candidate_config.component_dir,
        db_path=candidate_config.db_path,
        benchmark_report_path=candidate_config.benchmark_report_path,
        qc_report_path=candidate_config.qc_report_path,
        publish_manifest_path=candidate_config.publish_manifest_path,
        readiness_report_path=candidate_config.readiness_report_path,
        canonical_review_queue_path=candidate_config.canonical_review_queue_path,
        manifest_consistency=candidate_manifest_consistency,
    )
    original_summary = _snapshot_summary(
        snapshot_root=original_source.snapshot_root,
        component_dir=original_source.component_dir,
        db_path=original_source.db_path,
        benchmark_report_path=original_source.component_dir / "benchmark_report.json",
        qc_report_path=original_source.component_dir / "qc_report.json",
        publish_manifest_path=original_source.publish_manifest_path,
        readiness_report_path=original_source.readiness_report_path,
        canonical_review_queue_path=original_source.component_dir / "canonical_review_queue.jsonl",
        manifest_consistency=_validate_publish_manifest(original_source.publish_manifest_path),
    )
    baseline_summary = _snapshot_summary(
        snapshot_root=backup_source.snapshot_root,
        component_dir=backup_source.component_dir,
        db_path=backup_source.db_path,
        benchmark_report_path=backup_source.component_dir / "benchmark_report.json",
        qc_report_path=backup_source.component_dir / "qc_report.json",
        publish_manifest_path=backup_source.publish_manifest_path,
        readiness_report_path=backup_source.readiness_report_path,
        canonical_review_queue_path=backup_source.component_dir / "canonical_review_queue.jsonl",
        manifest_consistency=_validate_publish_manifest(backup_source.publish_manifest_path),
    )
    return {
        "candidate": candidate_summary,
        "original_current": original_summary,
        "baseline_publish": baseline_summary,
    }


def _snapshot_summary(
    *,
    snapshot_root: Path,
    component_dir: Path,
    db_path: Path,
    benchmark_report_path: Path,
    qc_report_path: Path,
    publish_manifest_path: Path,
    readiness_report_path: Path,
    canonical_review_queue_path: Path,
    manifest_consistency: dict[str, Any],
) -> dict[str, Any]:
    benchmark_payload = _load_json_dict(benchmark_report_path)
    qc_payload = _load_json_dict(qc_report_path)
    readiness_payload = _load_json_dict(readiness_report_path)
    benchmark_metrics = (
        benchmark_payload.get("metrics")
        if isinstance(benchmark_payload.get("metrics"), dict)
        else {}
    )
    qc_metrics = qc_payload.get("metrics") if isinstance(qc_payload.get("metrics"), dict) else {}
    readiness = (
        readiness_payload.get("readiness")
        if isinstance(readiness_payload.get("readiness"), dict)
        else {}
    )
    family_edge_count = _coerce_int(
        qc_metrics.get("family_edge_count"),
        default=_query_int(db_path, "SELECT COUNT(*) FROM ac_skg_family_edges", default=0),
    )
    review_queue_count = _line_count(canonical_review_queue_path)
    scenario_statuses = _extract_scenario_statuses(benchmark_payload)
    return {
        "snapshot_root": str(snapshot_root),
        "component_dir": str(component_dir),
        "publish_manifest": str(publish_manifest_path) if publish_manifest_path.exists() else "",
        "readiness_report": str(readiness_report_path) if readiness_report_path.exists() else "",
        "benchmark_metrics": dict(benchmark_metrics),
        "qc_metrics": dict(qc_metrics),
        "readiness": dict(readiness),
        "family_edge_count": family_edge_count,
        "review_queue_count": review_queue_count,
        "scenario_statuses": scenario_statuses,
        "manifest_consistency": manifest_consistency,
    }


def _evaluate_promotion(
    *,
    candidate_comparison: dict[str, Any],
    functional_checks: dict[str, Any],
    manifest_consistency: dict[str, Any],
    promote_on_pass: bool,
) -> dict[str, Any]:
    candidate = candidate_comparison["candidate"]
    original = candidate_comparison["original_current"]

    candidate_bench = candidate.get("benchmark_metrics", {})
    original_bench = original.get("benchmark_metrics", {})
    candidate_qc = candidate.get("qc_metrics", {})
    original_family_edges = _coerce_float(original.get("family_edge_count"), default=0.0)
    candidate_family_edges = _coerce_float(candidate.get("family_edge_count"), default=0.0)
    candidate_review_queue = _coerce_float(candidate.get("review_queue_count"), default=0.0)
    scenario_regressions = _scenario_runtime_regressions(
        candidate.get("scenario_statuses"),
        original.get("scenario_statuses"),
    )
    gain_floor_values = {
        metric_name: _summary_metric_value(candidate, metric_name)
        for metric_name in _PROMOTION_GAIN_FLOORS
    }

    gates = {
        "functional_checks_passed": bool(functional_checks.get("passed")),
        "publish_manifest_consistent": bool(manifest_consistency.get("passed")),
        "scholar_query_coverage_no_regression": _coerce_float(
            candidate_bench.get("scholar_query_coverage_ratio")
        )
        >= _coerce_float(original_bench.get("scholar_query_coverage_ratio")),
        "parameter_supported_no_regression": _coerce_float(
            candidate_bench.get("parameter_supported_ratio")
        )
        >= _coerce_float(original_bench.get("parameter_supported_ratio")),
        "causal_supported_plus_mixed_no_regression": _coerce_float(
            candidate_bench.get("causal_supported_plus_mixed_ratio")
        )
        >= _coerce_float(original_bench.get("causal_supported_plus_mixed_ratio")),
        "runtime_demanded_canonical_resolution_rate_pct": _coerce_float(
            candidate_qc.get("runtime_demanded_canonical_resolution_rate_pct"),
            default=_coerce_float(
                candidate_bench.get("runtime_demanded_canonical_resolution_rate_pct")
            ),
        )
        == 100.0,
        "global_canonical_resolution_rate_pct": _coerce_float(
            candidate_qc.get("global_canonical_resolution_rate_pct")
        )
        >= 95.0,
        "review_queue_bounded": candidate_review_queue <= 100.0,
        "family_edges_improved": candidate_family_edges > original_family_edges,
        "scenario_runtime_no_regression": not scenario_regressions,
        "runtime_files_complete": _paths_exist(candidate["component_dir"], _REQUIRED_RUNTIME_FILES),
        "evidence_files_complete": _paths_exist(
            candidate["component_dir"], _REQUIRED_EVIDENCE_FILES
        ),
        "required_reports_present": all(
            (
                Path(candidate["component_dir"], "benchmark_report.json").exists(),
                Path(candidate["component_dir"], "qc_report.json").exists(),
                Path(
                    candidate["component_dir"], "publish", "academic_pipeline_readiness.json"
                ).exists(),
            )
        ),
    }
    for metric_name, floor in _PROMOTION_GAIN_FLOORS.items():
        gate_name = f"gain_floor__{metric_name}"
        value = gain_floor_values[metric_name]
        if metric_name == "review_queue_count":
            gates[gate_name] = value <= floor
        else:
            gates[gate_name] = value >= floor
    passed = all(gates.values())
    reasons = [name for name, ok in gates.items() if not ok]
    if passed and not promote_on_pass:
        reasons.append("promotion_disabled")
        passed = False
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "promoted": passed,
        "promote_on_pass": bool(promote_on_pass),
        "gates": gates,
        "failed_gates": reasons,
        "gain_floor_values": gain_floor_values,
        "scenario_regressions": scenario_regressions,
    }


def _validate_publish_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "checked": False,
            "passed": False,
            "artifact_count": 0,
            "mismatches": [{"path": str(manifest_path), "reason": "manifest_missing"}],
        }
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "checked": False,
            "passed": False,
            "artifact_count": 0,
            "mismatches": [{"path": str(manifest_path), "reason": f"manifest_invalid:{exc}"}],
        }
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return {
            "checked": False,
            "passed": False,
            "artifact_count": 0,
            "mismatches": [{"path": str(manifest_path), "reason": "artifacts_missing"}],
        }

    mismatches: list[dict[str, Any]] = []
    for entry in artifacts:
        if not isinstance(entry, dict):
            mismatches.append({"path": "", "reason": "artifact_entry_invalid"})
            continue
        artifact_path = Path(str(entry.get("path") or ""))
        expected = str(entry.get("sha256") or "")
        if not artifact_path.exists():
            mismatches.append({"path": str(artifact_path), "reason": "artifact_missing"})
            continue
        actual = sha256_file(artifact_path)
        if expected and actual != expected:
            mismatches.append(
                {
                    "path": str(artifact_path),
                    "reason": "sha256_mismatch",
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                }
            )
    return {
        "checked": True,
        "passed": not mismatches,
        "artifact_count": len(artifacts),
        "mismatches": mismatches,
    }


def _write_meta_files(
    *,
    final_root: Path,
    final_config: AcademicBatchConfig,
    sources: dict[str, AcademicSnapshotSource],
    snapshot_version_id: int,
    suite_source: str,
    assembly_entries: list[dict[str, Any]],
    promotion_report: dict[str, Any],
) -> None:
    meta_dir = final_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    runtime_sources_payload = {
        "snapshot_root": str(final_root),
        "academic_component_dir": str(final_config.component_dir),
        "academic_db_path": str(final_config.db_path),
        "academic_index_dir": str(final_config.index_dir),
        "benchmark_suite_path": str(final_config.benchmark_suite_path),
        "benchmark_report_path": str(final_config.benchmark_report_path),
        "academic_demand_backlog_path": str(final_config.runtime_demand_backlog_path),
        "publish_manifest_path": str(final_config.publish_manifest_path),
        "readiness_report_path": str(final_config.readiness_report_path),
        "skg_snapshot_ref": f"duckdb://{final_config.db_path}#v{snapshot_version_id}",
    }

    assembly_payload = {
        "kind": "policyos_academic_best_assembly",
        "generated_at": datetime.now(UTC).isoformat(),
        "snapshot_root": str(final_root),
        "component_dir": str(final_config.component_dir),
        "snapshot_version_id": snapshot_version_id,
        "suite_source": suite_source,
        "entries": _dedupe_entries(assembly_entries),
    }
    source_lineage_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "snapshot_root": str(final_root),
        "sources": {
            label: {
                "snapshot_root": str(source.snapshot_root),
                "component_dir": str(source.component_dir),
                "db_path": str(source.db_path),
                "publish_manifest_path": str(source.publish_manifest_path)
                if source.publish_manifest_path.exists()
                else "",
                "readiness_report_path": str(source.readiness_report_path)
                if source.readiness_report_path.exists()
                else "",
            }
            for label, source in sources.items()
        },
        "db_table_sources": {
            **dict.fromkeys(_ORIGINAL_DB_TABLES, "original"),
            **dict.fromkeys(_REMAP_DB_TABLES, "remap"),
            **dict.fromkeys(_HYBRID_DB_TABLES, "hybrid(original+remap)"),
            **dict.fromkeys(_REBUILT_DB_TABLES, "rebuilt"),
        },
        "file_sources": {
            **dict.fromkeys(_ORIGINAL_COPY_FILES, "original"),
            **dict.fromkeys(_REMAP_COPY_FILES, "remap"),
            "benchmark_suite.json": suite_source,
        },
        "diagnostics": {
            "diagnostics_dir": str(final_root / "diagnostics"),
            "copied_specs": list(_DIAGNOSTIC_COPY_SPECS),
        },
    }

    for path, payload in (
        (meta_dir / "assembly_manifest.json", assembly_payload),
        (meta_dir / "source_lineage.json", source_lineage_payload),
        (meta_dir / "promotion_report.json", promotion_report),
        (meta_dir / "runtime_evidence_sources.json", runtime_sources_payload),
    ):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        dedup[str(entry.get("path") or "")] = dict(entry)
    return [dedup[key] for key in sorted(dedup)]


def _rewrite_json_tree(root: Path, *, old_root: Path, new_root: Path) -> None:
    old_text = str(old_root)
    new_text = str(new_root)
    for path in root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rewritten = _rewrite_json_value(payload, old_text=old_text, new_text=new_text)
        if rewritten != payload:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rewritten, fh, ensure_ascii=False, indent=2)


def _rewrite_json_value(value: Any, *, old_text: str, new_text: str) -> Any:
    if isinstance(value, str):
        return value.replace(old_text, new_text)
    if isinstance(value, list):
        return [_rewrite_json_value(item, old_text=old_text, new_text=new_text) for item in value]
    if isinstance(value, dict):
        return {
            key: _rewrite_json_value(item, old_text=old_text, new_text=new_text)
            for key, item in value.items()
        }
    return value


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _query_int(db_path: Path, sql: str, *, default: int) -> int:
    if not db_path.exists():
        return default
    try:
        with duckdb.connect(str(db_path), read_only=True) as con:
            row = con.execute(sql).fetchone()
    except duckdb.Error:
        return default
    if not row or row[0] is None:
        return default
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return default


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary_metric_value(summary: dict[str, Any], metric_name: str) -> float:
    if metric_name in summary:
        return _coerce_float(summary.get(metric_name))
    benchmark_metrics = summary.get("benchmark_metrics")
    if isinstance(benchmark_metrics, dict) and metric_name in benchmark_metrics:
        return _coerce_float(benchmark_metrics.get(metric_name))
    qc_metrics = summary.get("qc_metrics")
    if isinstance(qc_metrics, dict) and metric_name in qc_metrics:
        return _coerce_float(qc_metrics.get(metric_name))
    return 0.0


def _extract_scenario_statuses(benchmark_payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    scenarios = benchmark_payload.get("scenarios")
    if not isinstance(scenarios, list):
        return {}
    extracted: dict[str, dict[str, str]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_id = _clean_text(scenario.get("scenario_id"))
        if not scenario_id:
            continue
        extracted[scenario_id] = {
            "causal_status": _scenario_causal_status(scenario),
            "scholar_status": _scenario_scholar_status(scenario),
        }
    return extracted


def _scenario_causal_status(scenario_payload: dict[str, Any]) -> str:
    edges = scenario_payload.get("causal_edges")
    if not isinstance(edges, list) or not edges:
        return "unknown"
    statuses = [_clean_text(edge.get("status")).lower() for edge in edges if isinstance(edge, dict)]
    if any(status == "supported" for status in statuses):
        return "supported"
    if any(status == "mixed" for status in statuses):
        return "mixed"
    return "unsupported"


def _scenario_scholar_status(scenario_payload: dict[str, Any]) -> str:
    scholar_queries = scenario_payload.get("scholar_queries")
    if not isinstance(scholar_queries, list) or not scholar_queries:
        return "unknown"
    supports = [
        bool(query.get("supported")) for query in scholar_queries if isinstance(query, dict)
    ]
    if not supports:
        return "unknown"
    if all(supports):
        return "supported"
    if any(supports):
        return "mixed"
    return "unsupported"


def _scenario_runtime_regressions(
    candidate_statuses: Any,
    original_statuses: Any,
) -> list[dict[str, str]]:
    if not isinstance(candidate_statuses, dict) or not isinstance(original_statuses, dict):
        return []
    regressions: list[dict[str, str]] = []
    for scenario_id, original_payload in sorted(original_statuses.items()):
        if not isinstance(original_payload, dict):
            continue
        candidate_payload = candidate_statuses.get(scenario_id)
        if not isinstance(candidate_payload, dict):
            continue
        original_causal = _clean_text(original_payload.get("causal_status")).lower()
        candidate_causal = _clean_text(candidate_payload.get("causal_status")).lower()
        if original_causal in {"supported", "mixed"} and candidate_causal == "unsupported":
            regressions.append(
                {
                    "scenario_id": scenario_id,
                    "surface": "causal",
                    "original_status": original_causal,
                    "candidate_status": candidate_causal,
                }
            )
        original_scholar = _clean_text(original_payload.get("scholar_status")).lower()
        candidate_scholar = _clean_text(candidate_payload.get("scholar_status")).lower()
        if original_scholar == "supported" and candidate_scholar == "unsupported":
            regressions.append(
                {
                    "scenario_id": scenario_id,
                    "surface": "scholar",
                    "original_status": original_scholar,
                    "candidate_status": candidate_scholar,
                }
            )
    return regressions


def _paths_exist(component_dir: str | Path, relative_paths: tuple[str, ...]) -> bool:
    root = Path(component_dir)
    return all((root / rel).exists() for rel in relative_paths)


__all__ = [
    "AcademicSnapshotSource",
    "RuntimeFirstSnapshotResult",
    "build_runtime_first_snapshot",
]
