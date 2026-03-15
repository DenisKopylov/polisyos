"""Publish manifest writer for Lex artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.batch_common.manifest import write_publish_manifest


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
    with open(path, "r", encoding="utf-8") as fh:
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
    benchmark_readiness = benchmark_payload.get("readiness", {}) if isinstance(benchmark_payload.get("readiness"), dict) else {}
    quality_metrics = qc_payload.get("metrics", {}) if isinstance(qc_payload.get("metrics"), dict) else {}
    family_breakdown = quality_metrics.get("doc_family_breakdown", {}) if isinstance(quality_metrics.get("doc_family_breakdown"), dict) else {}
    subtype_breakdown = quality_metrics.get("legal_unit_subtype_breakdown", {}) if isinstance(quality_metrics.get("legal_unit_subtype_breakdown"), dict) else {}
    top_problem_subtypes = quality_metrics.get("top_problem_subtypes", []) if isinstance(quality_metrics.get("top_problem_subtypes"), list) else []
    top_unresolved_subtype_families = quality_metrics.get("top_unresolved_subtype_families", []) if isinstance(quality_metrics.get("top_unresolved_subtype_families"), list) else []
    top_problem_doc_groups = smoke_payload.get("top_problem_doc_groups", []) if isinstance(smoke_payload.get("top_problem_doc_groups"), list) else []
    top_problem_docs = smoke_payload.get("top_problem_docs", []) if isinstance(smoke_payload.get("top_problem_docs"), list) else []
    family_failures = [
        str(check.get("name") or "")
        for check in qc_payload.get("checks", [])
        if isinstance(check, dict)
        and not bool(check.get("passed", False))
        and str(check.get("name") or "").startswith("family:")
    ]
    release_ready = (
        readiness["consumer_ready"]
        and bool(qc_payload.get("passed", False))
        and bool(benchmark_readiness.get("passed", False))
        and not family_failures
    )

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
                    "qc_passed": bool(qc_payload.get("passed", False)),
                    "benchmark_passed": bool(benchmark_readiness.get("passed", False)),
                    "family_failures": family_failures,
                },
                "table_counts": tables,
                "require_embeddings": require_embeddings,
                "quality_summary": {
                    "passed": bool(qc_payload.get("passed", False)),
                    "metrics": quality_metrics,
                    "family_breakdown": family_breakdown,
                    "subtype_breakdown": subtype_breakdown,
                    "top_problem_subtypes": top_problem_subtypes,
                    "top_unresolved_subtype_families": top_unresolved_subtype_families,
                    "top_problem_doc_groups": top_problem_doc_groups,
                    "top_problem_docs": top_problem_docs[:10],
                    "quality_gate_failed_checks": quality_metrics.get("quality_gate_failed_checks", []),
                    "quality_gate_warning_failed_checks": quality_metrics.get("quality_gate_warning_failed_checks", []),
                    "quality_gate_skipped_checks": quality_metrics.get("quality_gate_skipped_checks", []),
                },
                "benchmark_summary": {
                    "passed": bool(benchmark_readiness.get("passed", False)),
                    "metrics": benchmark_payload.get("metrics", {}),
                    "failed_checks": benchmark_readiness.get("failed_checks", []),
                },
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    return manifest_path


def run_publish(output_dir: Path, *, require_embeddings: bool = True) -> Path:
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
        qc_report_path=(output_dir / "qc_report.json") if (output_dir / "qc_report.json").exists() else None,
        extra={
            "component_dir": str(output_dir),
            "consumer_readiness_manifest": str(consumer_manifest),
            "require_embeddings": require_embeddings,
        },
    )
