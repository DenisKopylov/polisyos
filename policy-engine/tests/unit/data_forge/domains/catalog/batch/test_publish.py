from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.data_forge.domains.catalog.batch.benchmark import READINESS_THRESHOLDS
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.publish import run_publish
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord

if TYPE_CHECKING:
    from pathlib import Path


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
    qc_passed: object = True,
    source_status: str = "complete",
    source_cases: list[dict[str, object]] | None = None,
    evaluation_mode: str = "full-ready",
    mismatch_rate: float = 0.0,
    blocking_mismatch_sources: int = 0,
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
                "evaluation_mode": evaluation_mode,
                "metrics": {
                    "benchmark_search_top5_relevance_pct": search,
                    "benchmark_retrieval_ready_pct": retrieval,
                    "benchmark_transport_ready_pct": transport,
                    "benchmark_foundry_fitness_pct": foundry,
                    "benchmark_source_preflight_ready_pct": source_preflight,
                    "benchmark_bulk_equivalence_mismatch_rate": mismatch_rate,
                    "benchmark_bulk_equivalence_blocking_sources_total": blocking_mismatch_sources,
                },
                "thresholds": READINESS_THRESHOLDS,
                "source_preflight": {
                    "sources": source_cases
                    if source_cases is not None
                    else [
                        {
                            "source": "worldbank",
                            "status": source_status,
                            "ready": source_preflight
                            >= READINESS_THRESHOLDS["benchmark_source_preflight_ready_pct"],
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
    config.merged_records_path.write_text(
        '{"title":"GDP per capita","description":"desc"}\n', encoding="utf-8"
    )
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    _write_qc_and_benchmark(config)

    manifest_path = run_publish(config)

    assert manifest_path.exists()
    assert config.consumer_readiness_path.exists()

    with open(config.consumer_readiness_path, encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    with open(manifest_path, encoding="utf-8") as fh:
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
        json.dump(
            {"scope": "datasets", "passed": True, "metrics": {}, "checks": []},
            fh,
            ensure_ascii=False,
            indent=2,
        )
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


def test_run_publish_blocks_unready_blocking_source_below_percentage_gate(tmp_path) -> None:
    source_names = tuple(f"blocking_{index:02d}" for index in range(12))
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        + "".join(
            f"  - name: {source_name}\n"
            "    family: fixture\n"
            "    wave: A\n"
            f"    endpoint: https://example.test/{source_name}\n"
            "    enabled: true\n"
            "    execution_tier: transport_ready\n"
            "    run_lane: empirical\n"
            "    publish_blocking: true\n"
            for source_name in source_names
        ),
        encoding="utf-8",
    )
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    ready_sources = source_names[:-1]
    readiness_pct = round(len(ready_sources) * 100 / len(source_names), 2)
    _write_qc_and_benchmark(
        config,
        source_preflight=readiness_pct,
        source_cases=[
            {
                "source": source_name,
                "status": "complete" if source_name in ready_sources else "failed_with_manifest",
                "ready": source_name in ready_sources,
            }
            for source_name in source_names
        ],
    )

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected one unready blocking source to prevent publish")

    with open(config.consumer_readiness_path, encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    assert readiness_payload["readiness"]["source_preflight_ready"] is True
    assert readiness_payload["readiness"]["blocking_sources_ready"] is False
    assert readiness_payload["readiness"]["consumer_ready"] is False


@pytest.mark.parametrize(
    ("qc_passed", "source_ready"),
    [("false", True), (True, "false")],
)
def test_run_publish_requires_boolean_admission_values(
    tmp_path,
    qc_passed: object,
    source_ready: object,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(
        config,
        qc_passed=qc_passed,
        source_preflight=100.0,
        source_cases=[
            {
                "source": "worldbank",
                "status": "complete",
                "ready": source_ready,
            }
        ],
    )

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected malformed boolean admission to prevent publish")


@pytest.mark.parametrize(
    ("source_cases", "expected_reason"),
    [
        (
            [
                {"source": "worldbank", "status": "complete", "ready": True},
                {"source": "worldbank", "status": "complete", "ready": True},
            ],
            "duplicate blocking source status",
        ),
        (
            [
                {"source": "worldbank", "status": "complete", "ready": True},
                {"source": "unregistered", "status": "complete", "ready": True},
            ],
            "unexpected blocking source status",
        ),
    ],
)
def test_run_publish_requires_exact_blocking_source_membership(
    tmp_path,
    source_cases: list[dict[str, object]],
    expected_reason: str,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, source_cases=source_cases)

    with pytest.raises(RuntimeError, match=expected_reason):
        run_publish(config)


def test_run_publish_allows_core_ready_snapshot(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, evaluation_mode="core-ready")

    manifest_path = run_publish(config)

    with open(config.consumer_readiness_path, encoding="utf-8") as fh:
        readiness_payload = json.load(fh)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest_payload = json.load(fh)

    assert readiness_payload["readiness"]["consumer_ready"] is True
    assert readiness_payload["readiness"]["full_publish_ready"] is False
    assert readiness_payload["publish_mode"] == "core-ready"
    assert manifest_payload["extra"]["evaluation_mode"] == "core-ready"


def test_run_publish_blocks_partial_eval_even_if_thresholds_pass(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    _write_test_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", registry_path=registry_path)
    _build_publish_fixture(config)
    _write_qc_and_benchmark(config, evaluation_mode="partial-eval")

    try:
        run_publish(config)
    except RuntimeError as exc:
        assert "consumer readiness failed" in str(exc)
    else:
        raise AssertionError("Expected partial-eval publish to stay blocked")
