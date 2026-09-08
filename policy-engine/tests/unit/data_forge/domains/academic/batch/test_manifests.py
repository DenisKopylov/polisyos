from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.dedup import merge_and_dedup
from polisyos.data_forge.domains.academic.batch.publish import run_publish
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    skg_materialized_schema_identity,
    skg_schema_generation_basis,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest


def _materialize_current_skg(config: AcademicBatchConfig) -> None:
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(config.db_path)) as connection:
        ensure_skg_schema(connection)


def test_merge_stage_writes_manifest(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    parsed = config.parsed_dir / "minimum_wage.jsonl"
    parsed.write_text(
        "\n".join(
            [
                json.dumps({"id": "W1", "title": "A"}),
                json.dumps({"id": "W1", "title": "A-dup"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stats = merge_and_dedup(config)
    assert stats["merged_records"] == 1
    assert (config.manifests_dir / "merge_dedup.json").exists()


def test_merge_stage_keeps_parsed_records_when_extracted_exists(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    parsed = config.parsed_dir / "minimum_wage.jsonl"
    parsed.write_text(
        json.dumps(
            {
                "id": "W1",
                "title": "Parsed title",
                "abstract": "Parsed abstract",
                "extraction_mode": "deterministic",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    extracted = config.extracted_dir / "resolve_extract.jsonl"
    extracted.write_text(
        json.dumps(
            {
                "id": "W1",
                "title": "Extracted title",
                "extraction_mode": "resolve_extract",
                "causal_claims": [{"cause": "tax_rate", "effect": "employment"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    stats = merge_and_dedup(config)
    assert stats["parsed_files"] == 2
    rows = [
        json.loads(line)
        for line in config.merged_records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["abstract"] == "Parsed abstract"
    assert rows[0]["extraction_mode"] == "resolve_extract"


def test_publish_manifest_contains_pipeline_name(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    _materialize_current_skg(config)
    config.qc_report_path.write_text(
        json.dumps(
            {"metrics": {"runtime_demanded_canonical_resolution_rate_pct": 95.0}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config.benchmark_report_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "parameter_supported_ratio": 0.7,
                    "causal_supported_ratio": 0.6,
                    "causal_supported_plus_mixed_ratio": 0.9,
                    "scholar_query_coverage_ratio": 0.8,
                    "non_default_transport_evidence_ratio": 0.7,
                    "family_edge_coverage_ratio": 0.5,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config.runtime_demand_backlog_path.write_text(
        json.dumps({"need_id": "scenario:param:x"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (config.manifests_dir / "resolve_extract.json").write_text(
        json.dumps(
            {"metrics": {"records": 10, "provider_timeout_count": 1, "watchdog_timeout_count": 0}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={
            "schema_generation": skg_schema_generation_basis().to_dict(),
            "materialized_schema_identity": skg_materialized_schema_identity(
                config.db_path
            ),
        },
        artifacts=[config.db_path],
    )

    manifest_path = run_publish(config)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    readiness_payload = json.loads(config.readiness_report_path.read_text(encoding="utf-8"))

    assert payload["pipeline"] == "academic"
    assert config.readiness_report_path.exists()
    assert payload["extra"]["readiness_report"] == str(config.readiness_report_path)
    assert readiness_payload["schema_generation"] == skg_schema_generation_basis().to_dict()
    assert readiness_payload["readiness"]["schema_generation_current"] is True
    assert manifest_path.exists()


def test_publish_does_not_mint_a_schema_generation_without_graph_receipt(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    run_publish(config)

    readiness_payload = json.loads(config.readiness_report_path.read_text(encoding="utf-8"))
    assert readiness_payload["readiness"]["schema_generation_current"] is False
    assert "schema_generation" not in readiness_payload


def test_publish_rejects_a_schema_changed_after_graph_materialization(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _materialize_current_skg(config)
    materialized_identity = skg_materialized_schema_identity(config.db_path)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={
            "schema_generation": skg_schema_generation_basis().to_dict(),
            "materialized_schema_identity": materialized_identity,
        },
        artifacts=[config.db_path],
    )
    with duckdb.connect(str(config.db_path)) as connection:
        connection.execute("DROP TABLE ac_skg_span_grounded_claims")

    run_publish(config)

    readiness_payload = json.loads(config.readiness_report_path.read_text(encoding="utf-8"))
    assert readiness_payload["readiness"]["schema_generation_current"] is False
    assert readiness_payload["materialized_schema_identity"] == materialized_identity
