"""Publish manifest writer for Lex artifacts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb

from polisyos.batch_common.manifest import write_publish_manifest

if TYPE_CHECKING:
    from pathlib import Path


def _table_count(db_path: Path, table_name: str) -> int:
    if not db_path.exists():
        return 0
    with duckdb.connect(str(db_path), read_only=True) as con:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()[0]
        if not exists:
            return 0
        return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _write_consumer_readiness_manifest(*, output_dir: Path, require_embeddings: bool) -> Path:
    db_path = output_dir / "lex_knowledge_graph.duckdb"
    embedding_artifacts = [
        output_dir / "lex_entity_embeddings.npz",
        output_dir / "lex_entity_index.hnsw",
        output_dir / "lex_fact_embeddings.npz",
        output_dir / "lex_fact_index.hnsw",
        output_dir / "lex_provision_embeddings.npz",
        output_dir / "lex_provision_index.hnsw",
    ]
    tables = {
        "lex_fact_candidates": _table_count(db_path, "lex_fact_candidates"),
        "lex_fact_grounded": _table_count(db_path, "lex_fact_grounded"),
        "lex_normative_facts": _table_count(db_path, "lex_normative_facts"),
        "lex_normative_ready_facts": _table_count(db_path, "lex_normative_ready_facts"),
        "lex_high_confidence_norms": _table_count(db_path, "lex_high_confidence_norms"),
        "lex_reference_edges": _table_count(db_path, "lex_reference_edges"),
        "lex_doc_versions": _table_count(db_path, "lex_doc_versions"),
    }
    readiness = {
        "db_ready": db_path.exists(),
        "embeddings_ready": all(path.exists() for path in embedding_artifacts),
        "candidate_layer_ready": tables["lex_fact_candidates"] > 0,
        "grounded_layer_ready": tables["lex_fact_grounded"] > 0,
        "normative_layer_ready": tables["lex_normative_facts"] > 0,
        "reference_edges_ready": tables["lex_reference_edges"] > 0,
        "doc_versions_ready": tables["lex_doc_versions"] > 0,
    }
    readiness["consumer_ready"] = readiness["db_ready"] and readiness["grounded_layer_ready"]
    if require_embeddings:
        readiness["consumer_ready"] = readiness["consumer_ready"] and readiness["embeddings_ready"]

    qc_payload = _load_json(output_dir / "qc_report.json")
    benchmark_payload = _load_json(output_dir / "benchmark_report.json")
    smoke_payload = _load_json(output_dir / "smoke" / "smoke_report.json")
    benchmark_readiness = (
        benchmark_payload.get("readiness", {})
        if isinstance(benchmark_payload.get("readiness"), dict)
        else {}
    )
    quality_metrics = (
        qc_payload.get("metrics", {}) if isinstance(qc_payload.get("metrics"), dict) else {}
    )
    qc_failed_checks = list(quality_metrics.get("qc_failed_checks", []))
    release_failed_checks = list(quality_metrics.get("release_failed_checks", []))
    if not require_embeddings:
        qc_failed_checks = [
            check for check in qc_failed_checks if check != "embedding_artifacts_present"
        ]
        release_failed_checks = [
            check for check in release_failed_checks if check != "embedding_artifacts_present"
        ]
    family_breakdown = (
        quality_metrics.get("doc_family_breakdown", {})
        if isinstance(quality_metrics.get("doc_family_breakdown"), dict)
        else {}
    )
    subtype_breakdown = (
        quality_metrics.get("legal_unit_subtype_breakdown", {})
        if isinstance(quality_metrics.get("legal_unit_subtype_breakdown"), dict)
        else {}
    )
    top_problem_subtypes = (
        quality_metrics.get("top_problem_subtypes", [])
        if isinstance(quality_metrics.get("top_problem_subtypes"), list)
        else []
    )
    top_unresolved_subtype_families = (
        quality_metrics.get("top_unresolved_subtype_families", [])
        if isinstance(quality_metrics.get("top_unresolved_subtype_families"), list)
        else []
    )
    top_gap_fill_subtypes = (
        quality_metrics.get("top_gap_fill_subtypes", [])
        if isinstance(quality_metrics.get("top_gap_fill_subtypes"), list)
        else []
    )
    top_gap_fill_families = (
        quality_metrics.get("top_gap_fill_families", [])
        if isinstance(quality_metrics.get("top_gap_fill_families"), list)
        else []
    )
    top_timeout_gap_fill_families = (
        quality_metrics.get("top_timeout_gap_fill_families", [])
        if isinstance(quality_metrics.get("top_timeout_gap_fill_families"), list)
        else []
    )
    top_problem_doc_groups = (
        smoke_payload.get("top_problem_doc_groups", [])
        if isinstance(smoke_payload.get("top_problem_doc_groups"), list)
        else []
    )
    top_problem_docs = (
        smoke_payload.get("top_problem_docs", [])
        if isinstance(smoke_payload.get("top_problem_docs"), list)
        else []
    )
    quality_gate_passed = bool(
        quality_metrics.get("quality_gate_passed", qc_payload.get("passed", False))
    )
    qc_passed = not qc_failed_checks
    benchmark_passed = bool(benchmark_readiness.get("passed", False))
    release_passed = bool(quality_gate_passed and qc_passed)
    release_ready = readiness["consumer_ready"] and release_passed

    manifest_path = output_dir / "publish" / "consumer_readiness.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "consumer_readiness",
                "component_dir": str(output_dir),
                "readiness": readiness,
                "release_readiness": {
                    "release_ready": release_ready,
                    "quality_gate_passed": quality_gate_passed,
                    "qc_passed": qc_passed,
                    "benchmark_passed": benchmark_passed,
                    "release_passed": release_passed,
                    "quality_gate_failed_checks": quality_metrics.get(
                        "quality_gate_failed_checks", []
                    ),
                    "quality_hotspot_failed_checks": quality_metrics.get(
                        "quality_hotspot_failed_checks", []
                    ),
                    "qc_failed_checks": qc_failed_checks,
                    "benchmark_failed_checks": benchmark_readiness.get("failed_checks", []),
                    "release_failed_checks": release_failed_checks,
                },
                "table_counts": tables,
                "require_embeddings": require_embeddings,
                "quality_summary": {
                    "passed": quality_gate_passed,
                    "quality_gate_passed": quality_gate_passed,
                    "qc_passed": qc_passed,
                    "release_passed": release_passed,
                    "metrics": quality_metrics,
                    "family_breakdown": family_breakdown,
                    "subtype_breakdown": subtype_breakdown,
                    "top_problem_subtypes": top_problem_subtypes,
                    "top_unresolved_subtype_families": top_unresolved_subtype_families,
                    "top_gap_fill_subtypes": top_gap_fill_subtypes,
                    "top_gap_fill_families": top_gap_fill_families,
                    "top_timeout_gap_fill_families": top_timeout_gap_fill_families,
                    "top_problem_doc_groups": top_problem_doc_groups,
                    "top_problem_docs": top_problem_docs[:10],
                    "quality_gate_failed_checks": quality_metrics.get(
                        "quality_gate_failed_checks", []
                    ),
                    "quality_hotspot_failed_checks": quality_metrics.get(
                        "quality_hotspot_failed_checks", []
                    ),
                    "quality_gate_warning_failed_checks": quality_metrics.get(
                        "quality_gate_warning_failed_checks", []
                    ),
                    "quality_gate_skipped_checks": quality_metrics.get(
                        "quality_gate_skipped_checks", []
                    ),
                    "high_confidence_norms_total": quality_metrics.get(
                        "high_confidence_norms", tables["lex_high_confidence_norms"]
                    ),
                    "normative_ready_total": quality_metrics.get(
                        "normative_ready_total", tables["lex_normative_ready_facts"]
                    ),
                    "normative_ready_share_pct": quality_metrics.get(
                        "normative_ready_share_pct", 0.0
                    ),
                    "llm_gap_fill_metrics": {
                        "llm_gap_fill_sent_total": quality_metrics.get(
                            "llm_gap_fill_sent_total", 0
                        ),
                        "llm_gap_fill_added_statements_total": quality_metrics.get(
                            "llm_gap_fill_added_statements_total", 0
                        ),
                        "baseline_vs_gap_fill_added_statements_total": quality_metrics.get(
                            "baseline_vs_gap_fill_added_statements_total", 0
                        ),
                        "llm_gap_fill_timeout_fallback_total": quality_metrics.get(
                            "llm_gap_fill_timeout_fallback_total", 0
                        ),
                        "llm_gap_fill_empty_responses_total": quality_metrics.get(
                            "llm_gap_fill_empty_responses_total", 0
                        ),
                        "gap_fill_null_yield_total": quality_metrics.get(
                            "gap_fill_null_yield_total", 0
                        ),
                        "gap_fill_null_yield_pct": quality_metrics.get(
                            "gap_fill_null_yield_pct", 0.0
                        ),
                        "gap_fill_null_yield_persisted_empty_total": quality_metrics.get(
                            "gap_fill_null_yield_persisted_empty_total", 0
                        ),
                        "gap_fill_null_yield_preserved_baseline_total": quality_metrics.get(
                            "gap_fill_null_yield_preserved_baseline_total", 0
                        ),
                        "llm_gap_fill_gain_rate_pct": quality_metrics.get(
                            "llm_gap_fill_gain_rate_pct", 0.0
                        ),
                        "primary_llm_saved_pct": quality_metrics.get("primary_llm_saved_pct", 0.0),
                        "llm_saved_pct_legacy": quality_metrics.get("llm_saved_pct", 0.0),
                        "gap_fill_trigger_counts": quality_metrics.get(
                            "gap_fill_trigger_counts", {}
                        ),
                        "audit_miss_rate_pct_before_gap_fill_baseline": quality_metrics.get(
                            "audit_miss_rate_pct_before_gap_fill_baseline", 0.0
                        ),
                        "audit_miss_rate_pct_after_gap_fill": quality_metrics.get(
                            "audit_miss_rate_pct_after_gap_fill", 0.0
                        ),
                    },
                },
                "benchmark_summary": {
                    "passed": benchmark_passed,
                    "metrics": benchmark_payload.get("metrics", {}),
                    "failed_checks": benchmark_readiness.get("failed_checks", []),
                    "advisory_failed_checks": benchmark_readiness.get("advisory_failed_checks", []),
                },
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    return manifest_path


def run_publish(output_dir: Path, *, require_embeddings: bool = True) -> Path:
    """Run publish."""
    consumer_manifest = _write_consumer_readiness_manifest(
        output_dir=output_dir,
        require_embeddings=require_embeddings,
    )
    artifacts = [
        output_dir / "lex_knowledge_graph.duckdb",
        output_dir / "lex_entity_embeddings.npz",
        output_dir / "lex_entity_index.hnsw",
        output_dir / "lex_fact_embeddings.npz",
        output_dir / "lex_fact_index.hnsw",
        output_dir / "lex_provision_embeddings.npz",
        output_dir / "lex_provision_index.hnsw",
        output_dir / "qc_report.json",
        output_dir / "benchmark_report.json",
        output_dir / "manifests" / "llm_gate.json",
        output_dir / "llm_gate_audit.jsonl",
        output_dir / "claim_exports" / "normative_claims.jsonl",
        output_dir / "claim_exports" / "normative_claims_summary.json",
        output_dir / "claim_exports" / "normative_claim_sets_summary.json",
        consumer_manifest,
    ]
    existing = [path for path in artifacts if path.exists()]

    manifest_path = output_dir / "publish" / "manifest.json"
    return write_publish_manifest(
        manifest_path=manifest_path,
        pipeline="lex",
        artifacts=existing,
        qc_report_path=(output_dir / "qc_report.json")
        if (output_dir / "qc_report.json").exists()
        else None,
        extra={
            "component_dir": str(output_dir),
            "consumer_readiness_manifest": str(consumer_manifest),
            "require_embeddings": require_embeddings,
        },
    )
