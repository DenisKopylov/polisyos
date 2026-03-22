from __future__ import annotations

import json
from pathlib import Path

from polisyos.datasets.batch.benchmark import READINESS_THRESHOLDS
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.batch.publish import run_publish
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord


def _write_test_registry(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: worldbank",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/worldbank",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _build_publish_fixture(config: DatasetBatchConfig) -> None:
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-gdp",
                    title="GDP per capita",
                    source="worldbank",
                    dataset_id="NY.GDP.PCAP.CD",
                    source_dataset_id="NY.GDP.PCAP.CD",
                    execution_tier="transport_ready",
                    polisyos_metrics=["gdp_per_capita"],
                    preferred_distribution_id="dist-gdp",
                    distributions=[
                        DistributionRecord(
                            id="dist-gdp",
                            connector_type="worldbank.wdi",
                            source_locator="NY.GDP.PCAP.CD",
                            parser_supported=True,
                            machine_readable=True,
                        )
                    ],
                )
            ]
        ),
        db_path=config.db_path,
    )


def _write_qc_and_benchmark(
    config: DatasetBatchConfig,
    *,
    search=100.0,
    retrieval=100.0,
    transport=100.0,
    foundry=100.0,
    source_preflight=100.0,
    qc_passed=True,
    source_status: str = "complete",
) -> None:
    with open(config.qc_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "scope": "datasets",
                "passed": qc_passed,
                "metrics": {
                    "machine_readable_distribution_pct": 100.0,
                    "parser_supported_distribution_pct": 100.0,
                    "datasets_with_metric_binding_pct": 100.0,
                    "datasets_with_schema_profile_pct": 100.0,
                    "transport_ready_var_coverage_pct": 100.0,
                    "execution_readiness_score_avg": 0.9,
                    "benchmark_search_top5_relevance_pct": search,
                    "benchmark_retrieval_ready_pct": retrieval,
                    "benchmark_transport_ready_pct": transport,
                    "benchmark_foundry_fitness_pct": foundry,
                    "benchmark_source_preflight_ready_pct": source_preflight,
                },
                "checks": [],
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": search,
                    "benchmark_retrieval_ready_pct": retrieval,
                    "benchmark_transport_ready_pct": transport,
                    "benchmark_foundry_fitness_pct": foundry,
                    "benchmark_source_preflight_ready_pct": source_preflight,
                },
                "thresholds": READINESS_THRESHOLDS,
                "source_preflight": {
                    "sources": [
                        {
                            "source": "worldbank",
                            "status": source_status,
                            "ready": source_preflight >= READINESS_THRESHOLDS["benchmark_source_preflight_ready_pct"],
                        }
                    ]
                },
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )


def test_run_publish_writes_consumer_readiness_manifest(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    config.merged_records_path.write_text('{"title":"GDP per capita","description":"desc"}\n', encoding="utf-8")
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    _write_qc_and_benchmark(config)

    manifest_path = run_publish(config)

    assert manifest_path.exists()
    assert config.consumer_readiness_path.exists()

    with open(config.consumer_readiness_path, "r", encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest_payload = json.load(fh)

    assert readiness_payload["readiness"]["consumer_ready"] is True
    assert manifest_payload["extra"]["consumer_ready"] is True


def test_run_publish_blocks_when_consumer_readiness_fails(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, search=50.0)

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected publish readiness gate to block")


def test_run_publish_blocks_when_blocking_source_status_is_missing(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    with open(config.qc_report_path, "w", encoding="utf-8") as fh:
        json.dump({"scope": "datasets", "passed": True, "metrics": {}, "checks": []}, fh, ensure_ascii=False, indent=2)
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 100.0,
                    "benchmark_retrieval_ready_pct": 100.0,
                    "benchmark_transport_ready_pct": 100.0,
                    "benchmark_foundry_fitness_pct": 100.0,
                    "benchmark_source_preflight_ready_pct": 100.0,
                },
                "thresholds": READINESS_THRESHOLDS,
                "source_preflight": {"sources": []},
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "missing blocking source statuses" in str(exc)
    else:
        raise AssertionError("Expected missing source status gate to block")
