from __future__ import annotations

import json

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.dedup import merge_and_dedup
from polisyos.academic.batch.publish import run_publish


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

    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.db_path.write_text("db", encoding="utf-8")
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

    manifest_path = run_publish(config)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["pipeline"] == "academic"
    assert config.readiness_report_path.exists()
    assert payload["extra"]["readiness_report"] == str(config.readiness_report_path)
    assert manifest_path.exists()
