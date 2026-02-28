"""Publish manifest writer for Lex artifacts."""

from __future__ import annotations

from pathlib import Path

from polisyos.batch_common.manifest import write_publish_manifest


def run_publish(output_dir: Path) -> Path:
    artifacts = [
        output_dir / "lex_knowledge_graph.duckdb",
        output_dir / "lex_entity_embeddings.npz",
        output_dir / "lex_entity_index.hnsw",
        output_dir / "lex_fact_embeddings.npz",
        output_dir / "lex_fact_index.hnsw",
        output_dir / "lex_provision_embeddings.npz",
        output_dir / "lex_provision_index.hnsw",
        output_dir / "qc_report.json",
        output_dir / "manifests" / "llm_gate.json",
        output_dir / "llm_gate_audit.jsonl",
    ]
    existing = [path for path in artifacts if path.exists()]

    manifest_path = output_dir / "publish" / "manifest.json"
    return write_publish_manifest(
        manifest_path=manifest_path,
        pipeline="lex",
        artifacts=existing,
        qc_report_path=(output_dir / "qc_report.json") if (output_dir / "qc_report.json").exists() else None,
        extra={"component_dir": str(output_dir)},
    )
