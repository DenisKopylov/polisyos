from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.batch_common.manifest import write_raw_manifest
from polisyos.datasets.batch.benchmark import READINESS_THRESHOLDS
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.qc import _url_is_reachable, run_qc


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


def test_qc_writes_coverage_heatmap_when_observations_exist(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "worldbank" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"NY.GDP.PCAP.CD"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="worldbank",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc","source":"worldbank"}\n', encoding="utf-8"
    )

    con = duckdb.connect(str(config.db_path))
    con.execute(
        "CREATE TABLE ds_distributions (url VARCHAR, dataset_id VARCHAR, parser_supported BOOLEAN)"
    )
    con.execute(
        "CREATE TABLE ds_datasets (id VARCHAR, source VARCHAR, execution_tier VARCHAR, "
        "coverage_time_start VARCHAR, coverage_time_end VARCHAR, temporal_start VARCHAR, temporal_end VARCHAR, "
        "coverage_countries VARCHAR[], coverage_regions VARCHAR[], spatial VARCHAR, "
        "quality_execution_readiness_score DOUBLE)"
    )
    con.execute(
        "CREATE TABLE ds_observations (dataset_id VARCHAR, canonical_var VARCHAR, country_code VARCHAR, year INTEGER, survey_year INTEGER, value DOUBLE)"
    )
    con.execute(
        "INSERT INTO ds_datasets VALUES ('ds-gdp', 'worldbank', 'transport_ready', '2020', '2020', NULL, NULL, ['UA'], [], 'UA', 0.9)"
    )
    con.execute(
        "INSERT INTO ds_observations VALUES ('ds-gdp', 'gdp_per_capita', 'UA', 2020, NULL, 1000.0)"
    )
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)

    assert "observation_coverage_pct" in report.metrics
    assert Path(report.metrics["coverage_heatmap_path"]).exists()


def test_qc_supports_legacy_dataset_schema_without_coverage_columns(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "unesco_uis" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"EDU_001"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="unesco_uis",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc","source":"unesco_uis"}\n', encoding="utf-8"
    )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE ds_distributions (url VARCHAR, dataset_id VARCHAR, format VARCHAR)")
    con.execute(
        "CREATE TABLE ds_datasets ("
        "id VARCHAR, source VARCHAR, title VARCHAR, description VARCHAR, spatial VARCHAR, "
        "temporal_start VARCHAR, temporal_end VARCHAR, polisyos_metrics VARCHAR[], variables VARCHAR[], "
        "keywords VARCHAR[], themes VARCHAR[], formats VARCHAR[], updated_at TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO ds_datasets VALUES ("
        "'ds-uis', 'unesco_uis', 'Education', 'Legacy schema dataset', 'UA', "
        "'2000', '2022', ['education_outcomes'], ['EDU_001'], [], [], ['CSV'], CURRENT_TIMESTAMP)"
    )
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)

    assert "datasets_with_temporal_coverage_pct" in report.metrics
    assert "datasets_with_geographic_coverage_pct" in report.metrics
    assert "execution_readiness_score_avg" in report.metrics


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
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
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


def test_qc_uses_preflight_threshold_contract(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", run_profile="preflight_core")

    raw_dir = config.raw_dir / "worldbank" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"NY.GDP.PCAP.CD"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="worldbank",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 90.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 10.0,
                    "benchmark_foundry_fitness_pct": 10.0,
                    "benchmark_source_preflight_ready_pct": 100.0,
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
    failures = {check.name for check in report.checks if not check.passed}

    assert report.passed is True
    assert "benchmark_transport_ready_pct" not in failures
    assert "benchmark_foundry_fitness_pct" not in failures


def test_qc_marks_transport_failures_as_diagnostic_for_partial_eval(tmp_path) -> None:
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
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "evaluation_mode": "partial-eval",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 90.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 0.0,
                    "benchmark_foundry_fitness_pct": 90.0,
                    "benchmark_source_preflight_ready_pct": 0.0,
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
    checks = {check.name: check for check in report.checks}

    assert report.passed is True
    assert checks["benchmark_transport_ready_pct"].group == "empirical-transport-health"
    assert checks["benchmark_transport_ready_pct"].severity == "warning"
    assert checks["benchmark_transport_ready_pct"].status == "blocked"
    assert checks["benchmark_source_preflight_ready_pct"].severity == "warning"
    assert report.metrics["qc_evaluation_mode"] == "partial-eval"


def test_qc_skips_coverage_and_spread_as_blocking_checks_for_preflight(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", run_profile="preflight_core")

    raw_dir = config.raw_dir / "worldbank" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"NY.GDP.PCAP.CD"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="worldbank",
        endpoint="https://example.test",
        payload_path=payload,
        count=1,
    )
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc","source":"worldbank"}\n',
        encoding="utf-8",
    )
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "datasets_benchmark",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 90.0,
                    "benchmark_retrieval_ready_pct": 90.0,
                    "benchmark_transport_ready_pct": 10.0,
                    "benchmark_foundry_fitness_pct": 10.0,
                    "benchmark_source_preflight_ready_pct": 100.0,
                },
                "thresholds": READINESS_THRESHOLDS,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    con = duckdb.connect(str(config.db_path))
    con.execute(
        "CREATE TABLE ds_distributions (url VARCHAR, dataset_id VARCHAR, parser_supported BOOLEAN)"
    )
    con.execute(
        "CREATE TABLE ds_datasets (id VARCHAR, source VARCHAR, execution_tier VARCHAR, "
        "coverage_time_start VARCHAR, coverage_time_end VARCHAR, temporal_start VARCHAR, temporal_end VARCHAR, "
        "coverage_countries VARCHAR[], coverage_regions VARCHAR[], spatial VARCHAR, "
        "quality_execution_readiness_score DOUBLE)"
    )
    con.execute(
        "CREATE TABLE ds_observations (dataset_id VARCHAR, canonical_var VARCHAR, country_code VARCHAR, year INTEGER, survey_year INTEGER, value DOUBLE)"
    )
    con.execute(
        "INSERT INTO ds_datasets VALUES "
        "('ds-gdp-a', 'worldbank', 'transport_ready', '2020', '2020', NULL, NULL, ['UA'], [], 'UA', 0.9), "
        "('ds-gdp-b', 'oecd', 'transport_ready', '2020', '2020', NULL, NULL, ['UA'], [], 'UA', 0.9)"
    )
    con.execute(
        "INSERT INTO ds_observations VALUES "
        "('ds-gdp-a', 'gdp_per_capita', 'UA', 2020, NULL, 1000.0), "
        "('ds-gdp-b', 'gdp_per_capita', 'UA', 2020, NULL, 1400.0)"
    )
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    checks = {check.name: check for check in report.checks}

    assert report.passed is True
    assert checks["observation_coverage_pct"].passed is True
    assert checks["observation_coverage_pct"].severity == "info"
    assert checks["cross_source_value_spread"].passed is True
    assert checks["cross_source_value_spread"].severity == "info"


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

    current_config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
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

    current_config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
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

    current_config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
    con = duckdb.connect(str(current_config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(current_config, fail_fast=False)
    failures = {check.name for check in report.checks if not check.passed}

    assert report.metrics["source_anomalies_total"] == 0
    assert "source_anomaly_data_gov_ro_broad_zero_after_nonzero" not in failures


def test_qc_resets_wvs_anomaly_baseline_after_local_file_cutover(tmp_path) -> None:
    previous_root = tmp_path / "policyos_snapshot_20260218"
    current_root = tmp_path / "policyos_snapshot_20260219"
    previous_config = DatasetBatchConfig(snapshot_root=previous_root)
    current_config = DatasetBatchConfig(snapshot_root=current_root)

    prev_raw_dir = previous_config.raw_dir / "wvs" / "20260218T000000Z"
    prev_raw_dir.mkdir(parents=True, exist_ok=True)
    prev_payload = prev_raw_dir / "payload.jsonl"
    prev_payload.write_text('{"id":"A165"}\n{"id":"A173"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=prev_raw_dir / "manifest.json",
        source="wvs",
        endpoint="https://example.test",
        payload_path=prev_payload,
        count=2,
    )

    cur_raw_dir = current_config.raw_dir / "wvs" / "20260219T000000Z"
    cur_raw_dir.mkdir(parents=True, exist_ok=True)
    cur_payload = cur_raw_dir / "payload.jsonl"
    cur_payload.write_text("".join('{"id":"A165"}\n' for _ in range(20)), encoding="utf-8")
    write_raw_manifest(
        manifest_path=cur_raw_dir / "manifest.json",
        source="wvs",
        endpoint="https://example.test",
        payload_path=cur_payload,
        count=20,
    )

    current_config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
    con = duckdb.connect(str(current_config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(current_config, fail_fast=False)
    failures = {check.name for check in report.checks if not check.passed}

    assert report.metrics["source_anomaly_baseline_resets_total"] == 1
    assert "source_anomaly_wvs_count_spike_pct" not in failures


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
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
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
    config.merged_records_path.write_text(
        '{"title":"Dataset","description":"Desc"}\n', encoding="utf-8"
    )
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


def test_qc_description_gate_ignores_metadata_sparse_empirical_sources(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.raw_dir / "data_gov_ua_broad" / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"pkg-1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="data_gov_ua_broad",
        endpoint="https://data.gov.ua/api/3/action/package_search",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"source": "eurostat", "title": "Eurostat dataset", "description": ""})
            + "\n"
        )
        fh.write(
            json.dumps(
                {
                    "source": "data_gov_ua_broad",
                    "title": "Municipal budget",
                    "description": "Budget dataset",
                }
            )
            + "\n"
        )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=True)

    assert report.passed is True
    assert report.metrics["description_qc_total"] == 1
    assert report.metrics["empty_description_pct"] == 0.0


def test_url_reachability_uses_get_fallback_when_head_is_rejected(monkeypatch) -> None:
    class _Response:
        def __init__(self, status: int) -> None:
            self.status = status

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def _fake_urlopen(request, timeout=10):
        if request.get_method() == "HEAD":
            raise RuntimeError("HEAD not supported")
        return _Response(status=206)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    assert _url_is_reachable("https://example.test/resource") is True
