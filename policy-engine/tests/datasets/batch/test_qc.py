from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.datasets.batch.benchmark import READINESS_THRESHOLDS
from polisyos.batch_common.manifest import write_raw_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.qc import run_qc


def test_qc_report_passes_on_minimal_valid_snapshot(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"title": "Dataset", "description": "Desc"}) + "\n")

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=True)
    assert report.passed is True
    assert config.qc_report_path.exists()
    assert "zero_row_sources" in report.metrics


def test_qc_fail_fast_raises_on_manifest_mismatch(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=payload,
        count=2,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"title":"a","description":"b"}\n', encoding="utf-8")

    try:
        run_qc(config, fail_fast=True)
    except RuntimeError as exc:
        assert "manifest_count_parity" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for fail-fast QC")


def test_qc_loads_benchmark_thresholds(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 60.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 90.0,
                    "benchmark_foundry_fitness_pct": 90.0,
                },
                "thresholds": READINESS_THRESHOLDS,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    failures = {check.name: check for check in report.checks if not check.passed}

    assert report.passed is False
    assert "benchmark_search_top5_relevance_pct" in failures


def test_qc_detects_source_anomaly_against_previous_snapshot(tmp_path) -> None:
    previous_root = tmp_path / "policyos_snapshot_20260218"
    current_root = tmp_path / "policyos_snapshot_20260219"
    previous_config = DatasetBatchConfig(snapshot_root=previous_root)
    current_config = DatasetBatchConfig(snapshot_root=current_root)

    prev_raw_dir = previous_config.raw_dir / "oecd" / "20260218T000000Z"
    prev_raw_dir.mkdir(parents=True, exist_ok=True)
    prev_payload = prev_raw_dir / "payload.jsonl"
    prev_payload.write_text('{"id":"1"}\n{"id":"2"}\n{"id":"3"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=prev_raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=prev_payload,
        count=3,
    )

    cur_raw_dir = current_config.raw_dir / "oecd" / "20260219T000000Z"
    cur_raw_dir.mkdir(parents=True, exist_ok=True)
    cur_payload = cur_raw_dir / "payload.jsonl"
    cur_payload.write_text("", encoding="utf-8")
    write_raw_manifest(
        manifest_path=cur_raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=cur_payload,
        count=0,
    )

    current_config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    con = duckdb.connect(str(current_config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(current_config, fail_fast=False)
    failures = {check.name: check for check in report.checks if not check.passed}

    assert report.metrics["source_anomalies_total"] >= 1
    assert "source_anomaly_oecd_zero_after_nonzero" in failures


def test_qc_skips_source_anomaly_detection_for_sampled_run(tmp_path) -> None:
    previous_root = tmp_path / "policyos_snapshot_20260218"
    current_root = tmp_path / "policyos_snapshot_20260219"
    previous_config = DatasetBatchConfig(snapshot_root=previous_root)
    current_config = DatasetBatchConfig(snapshot_root=current_root, max_datasets_per_source=2)

    prev_raw_dir = previous_config.raw_dir / "oecd" / "20260218T000000Z"
    prev_raw_dir.mkdir(parents=True, exist_ok=True)
    prev_payload = prev_raw_dir / "payload.jsonl"
    prev_payload.write_text('{"id":"1"}\n{"id":"2"}\n{"id":"3"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=prev_raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=prev_payload,
        count=3,
    )

    cur_raw_dir = current_config.raw_dir / "oecd" / "20260219T000000Z"
    cur_raw_dir.mkdir(parents=True, exist_ok=True)
    cur_payload = cur_raw_dir / "payload.jsonl"
    cur_payload.write_text("", encoding="utf-8")
    write_raw_manifest(
        manifest_path=cur_raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=cur_payload,
        count=0,
    )

    current_config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    con = duckdb.connect(str(current_config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(current_config, fail_fast=False)
    failures = {check.name for check in report.checks if not check.passed}

    assert report.metrics["source_anomaly_checks_skipped"] == 1
    assert "source_anomaly_oecd_zero_after_nonzero" not in failures


def test_qc_does_not_flag_first_time_source_onboarding_as_anomaly(tmp_path) -> None:
    previous_root = tmp_path / "policyos_snapshot_20260218"
    current_root = tmp_path / "policyos_snapshot_20260219"
    previous_config = DatasetBatchConfig(snapshot_root=previous_root)
    current_config = DatasetBatchConfig(snapshot_root=current_root)

    prev_raw_dir = previous_config.raw_dir / "oecd" / "20260218T000000Z"
    prev_raw_dir.mkdir(parents=True, exist_ok=True)
    prev_payload = prev_raw_dir / "payload.jsonl"
    prev_payload.write_text('{"id":"1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=prev_raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=prev_payload,
        count=1,
    )

    cur_raw_dir = current_config.raw_dir / "data_gov_ro_broad" / "20260219T000000Z"
    cur_raw_dir.mkdir(parents=True, exist_ok=True)
    cur_payload = cur_raw_dir / "payload.jsonl"
    cur_payload.write_text('{"id":"ro-1"}\n{"id":"ro-2"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=cur_raw_dir / "manifest.json",
        source="data_gov_ro_broad",
        endpoint="https://data.gov.ro/api/3/action/package_search",
        payload_path=cur_payload,
        count=2,
    )

    current_config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    con = duckdb.connect(str(current_config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(current_config, fail_fast=False)
    failures = {check.name for check in report.checks if not check.passed}

    assert report.metrics["source_anomalies_total"] == 0
    assert "source_anomaly_data_gov_ro_broad_zero_after_nonzero" not in failures


def test_qc_relaxes_search_threshold_for_sampled_text_only_benchmark(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=5)

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_vector_index_available": 0,
                    "benchmark_search_top5_relevance_pct": 50.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 90.0,
                    "benchmark_foundry_fitness_pct": 90.0,
                },
                "thresholds": READINESS_THRESHOLDS,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    failures = {check.name: check for check in report.checks if not check.passed}

    assert "benchmark_search_top5_relevance_pct" not in failures


def test_qc_counts_promoted_alignment_on_execution_grade_internal_ids(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        promoted_sources=("oecd",),
    )

    raw_dir = config.raw_dir / "oecd" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"DF_TEST"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="oecd",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text('{"title":"Dataset","description":"Desc"}\n', encoding="utf-8")
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 90.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 90.0,
                    "benchmark_foundry_fitness_pct": 90.0,
                },
                "thresholds": READINESS_THRESHOLDS,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    con = duckdb.connect(str(config.db_path))
    con.execute(
        """
        CREATE TABLE ds_datasets (
            id VARCHAR,
            source VARCHAR,
            dataset_id VARCHAR,
            source_dataset_id VARCHAR,
            execution_tier VARCHAR,
            coverage_time_start VARCHAR,
            coverage_time_end VARCHAR,
            temporal_start VARCHAR,
            temporal_end VARCHAR,
            coverage_countries VARCHAR[],
            coverage_regions VARCHAR[],
            spatial VARCHAR,
            quality_execution_readiness_score DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_distributions (
            dataset_id VARCHAR,
            parser_supported BOOLEAN,
            url VARCHAR
        )
        """
    )
    con.execute("CREATE TABLE ds_metric_bindings (dataset_id VARCHAR)")
    con.execute("CREATE TABLE ds_variable_alignments (dataset_id VARCHAR)")
    con.execute(
        "INSERT INTO ds_datasets VALUES ("
        " 'catalog-oecd-1', 'oecd', 'DF_TEST', 'DF_TEST', 'fetchable',"
        " '2020', '2022', NULL, NULL, ['UA'], [], NULL, 0.9"
        ")"
    )
    con.execute(
        "INSERT INTO ds_distributions VALUES ('catalog-oecd-1', TRUE, 'https://example.test/data.csv')"
    )
    con.execute("INSERT INTO ds_metric_bindings VALUES ('catalog-oecd-1')")
    con.execute("INSERT INTO ds_variable_alignments VALUES ('catalog-oecd-1')")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    checks = {check.name: check for check in report.checks}

    assert checks["promoted_oecd_transport_ready_alignment_pct"].passed is True
    assert checks["promoted_oecd_transport_ready_alignment_pct"].value == 100.0
