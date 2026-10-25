from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.catalog.batch.checkpoints import (
    build_output_inventory,
    write_json,
)
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    current_content_stage_receipt,
    run_content_stage_with_receipt,
)


def _seed_snapshot(tmp_path: Path) -> DatasetBatchConfig:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        active_countries=("UA",),
        active_year_window=(2020, 2022),
        max_datasets_per_source=2,
        run_profile="preflight_core",
        fail_fast_qc=False,
    )
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text(
        '{"title":"Controlled WVS rows","description":"Small receipt fixture"}\n',
        encoding="utf-8",
    )
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    config.manifests_dir.mkdir(parents=True, exist_ok=True)
    (config.manifests_dir / "core_sources_ingest.json").write_text(
        '{"kind":"core_sources_ingest","status":"complete"}\n', encoding="utf-8"
    )

    con = duckdb.connect(str(config.db_path))
    con.execute(
        "CREATE TABLE ds_distributions ("
        "id VARCHAR, dataset_id VARCHAR, url VARCHAR, parser_supported BOOLEAN, "
        "machine_readable BOOLEAN, format VARCHAR)"
    )
    con.execute(
        "CREATE TABLE ds_datasets ("
        "id VARCHAR PRIMARY KEY, source VARCHAR, dataset_id VARCHAR, source_dataset_id VARCHAR, "
        "title VARCHAR, description VARCHAR, publisher VARCHAR, spatial VARCHAR, "
        "temporal_start VARCHAR, temporal_end VARCHAR, coverage_time_start VARCHAR, "
        "coverage_time_end VARCHAR, coverage_countries VARCHAR[], coverage_regions VARCHAR[], "
        "coverage_granularity VARCHAR, execution_tier VARCHAR, "
        "quality_execution_readiness_score DOUBLE)"
    )
    con.execute(
        "CREATE TABLE ds_observations ("
        "observation_id VARCHAR PRIMARY KEY, dataset_id VARCHAR NOT NULL, "
        "raw_variable VARCHAR NOT NULL, canonical_var VARCHAR NOT NULL, "
        "country_code VARCHAR NOT NULL, year INTEGER, survey_year INTEGER, wave INTEGER, "
        "value DOUBLE, condition_json VARCHAR, acquisition_method VARCHAR, "
        "source_watermark VARCHAR, dataset_version VARCHAR)"
    )
    con.execute(
        "INSERT INTO ds_datasets VALUES "
        "('catalog-wvs-7', 'wvs', 'A165', 'A165', 'WVS wave 7', 'controlled', 'WVS', "
        "'UA', NULL, NULL, NULL, NULL, NULL, NULL, 'wave', 'transport_ready', 0.9), "
        "('catalog-wvs-8', 'wvs', 'B165', 'B165', 'WVS wave 8', 'controlled', 'WVS', "
        "'UA', NULL, NULL, NULL, NULL, NULL, NULL, 'wave', 'transport_ready', 0.9)"
    )
    con.execute(
        "INSERT INTO ds_observations VALUES "
        "('obs-wvs-7-ua-2020', 'catalog-wvs-7', 'A165', 'social_trust', 'UA', "
        "2020, 2020, 7, 0.333, '{\"sex\":\"women\"}', 'local_bulk_file', '2026-10-22', 'A165'), "
        "('obs-wvs-8-ua-2022', 'catalog-wvs-8', 'B165', 'social_trust', 'UA', "
        "2022, 2022, 8, 0.500, '{\"sex\":\"men\"}', 'local_bulk_file', '2026-10-22', 'B165'), "
        "('obs-orphan-ua-2021', 'missing-catalog-row', 'C165', 'social_trust', 'UA', "
        "2021, 2021, 7, 0.250, '{\"sex\":\"all\"}', 'local_bulk_file', '2026-10-22', 'C165'), "
        "('obs-wvs-null-ua-2021', 'catalog-wvs-7', 'D165', 'social_trust', 'UA', "
        "2021, 2021, 7, NULL, '{\"sex\":\"all\"}', 'local_bulk_file', '2026-10-22', 'D165')"
    )
    con.execute("CHECKPOINT")
    con.close()
    return config


def test_qc_projects_exact_sparse_points_without_rewriting_declared_coverage(tmp_path) -> None:
    config = _seed_snapshot(tmp_path)

    run_content_stage_with_receipt(config, "qc")

    artifact_path = config.component_dir / "observed_support.json"
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "policyos.catalog.qc.observed_support.v1"
    assert payload["record_set"] == "non_null_value_rows"
    receipt = current_content_stage_receipt(config, "qc")
    assert receipt is not None
    assert payload["producer_snapshot"]["stage_input_basis_digest"] == receipt["input_basis_digest"]
    assert payload["producer_snapshot"]["graph_database_sha256"]

    points = payload["points"]
    assert points == [
        {
            "dataset_id": "catalog-wvs-7",
            "dataset_binding": "resolved",
            "source": "wvs",
            "raw_variable": "A165",
            "canonical_var": "social_trust",
            "country_code": "UA",
            "year": 2020,
            "survey_year": 2020,
            "wave": 7,
            "condition_sha256": hashlib.sha256(b'{"sex":"women"}').hexdigest(),
            "producer_provenance": {
                "acquisition_method": "local_bulk_file",
                "source_watermark": "2026-10-22",
                "dataset_version": "A165",
            },
            "observation_count": 1,
        },
        {
            "dataset_id": "catalog-wvs-8",
            "dataset_binding": "resolved",
            "source": "wvs",
            "raw_variable": "B165",
            "canonical_var": "social_trust",
            "country_code": "UA",
            "year": 2022,
            "survey_year": 2022,
            "wave": 8,
            "condition_sha256": hashlib.sha256(b'{"sex":"men"}').hexdigest(),
            "producer_provenance": {
                "acquisition_method": "local_bulk_file",
                "source_watermark": "2026-10-22",
                "dataset_version": "B165",
            },
            "observation_count": 1,
        },
        {
            "dataset_id": "missing-catalog-row",
            "dataset_binding": "unresolved",
            "source": None,
            "raw_variable": "C165",
            "canonical_var": "social_trust",
            "country_code": "UA",
            "year": 2021,
            "survey_year": 2021,
            "wave": 7,
            "condition_sha256": hashlib.sha256(b'{"sex":"all"}').hexdigest(),
            "producer_provenance": {
                "acquisition_method": "local_bulk_file",
                "source_watermark": "2026-10-22",
                "dataset_version": "C165",
            },
            "observation_count": 1,
        },
    ]

    con = duckdb.connect(str(config.db_path), read_only=True)
    declared_coverage = con.execute(
        "SELECT coverage_time_start, coverage_time_end FROM ds_datasets WHERE id = 'catalog-wvs-7'"
    ).fetchone()
    con.close()
    assert declared_coverage == (None, None)

    con = duckdb.connect(str(config.db_path))
    con.execute(
        "DELETE FROM ds_observations WHERE dataset_id = 'catalog-wvs-7' AND year = 2020 "
        'AND wave = 7 AND condition_json = \'{"sex":"women"}\''
    )
    con.execute("CHECKPOINT")
    con.close()
    run_content_stage_with_receipt(config, "qc")
    updated = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert [(point["dataset_id"], point["wave"]) for point in updated["points"]] == [
        ("catalog-wvs-8", 8),
        ("missing-catalog-row", 7),
    ]
    assert current_content_stage_receipt(config, "qc") is not None


def test_qc_stage_receipt_invalidates_when_heatmap_or_support_artifact_changes(tmp_path) -> None:
    config = _seed_snapshot(tmp_path)
    run_content_stage_with_receipt(config, "qc")
    assert current_content_stage_receipt(config, "qc") is not None

    support_path = config.component_dir / "observed_support.json"
    support_path.unlink()
    assert current_content_stage_receipt(config, "qc") is None

    run_content_stage_with_receipt(config, "qc")
    heatmap_path = config.component_dir / "coverage_heatmap.json"
    heatmap_path.write_bytes(heatmap_path.read_bytes() + b"\n")
    assert current_content_stage_receipt(config, "qc") is None


def test_qc_projects_observations_as_unresolved_when_catalog_table_is_absent(tmp_path) -> None:
    config = _seed_snapshot(tmp_path)
    con = duckdb.connect(str(config.db_path))
    con.execute("DROP TABLE ds_datasets")
    con.execute("CHECKPOINT")
    con.close()

    run_content_stage_with_receipt(config, "qc")

    payload = json.loads((config.component_dir / "observed_support.json").read_text())
    assert payload["observation_table_present"] is True
    assert payload["required_columns_present"] is True
    assert payload["missing_required_columns"] == []
    assert [
        (
            point["dataset_id"],
            point["year"],
            point["wave"],
            point["dataset_binding"],
            point["source"],
        )
        for point in payload["points"]
    ] == [
        ("catalog-wvs-7", 2020, 7, "unresolved", None),
        ("catalog-wvs-8", 2022, 8, "unresolved", None),
        ("missing-catalog-row", 2021, 7, "unresolved", None),
    ]
    assert current_content_stage_receipt(config, "qc") is not None


def test_qc_marks_malformed_observation_schema_present_but_unestablished(tmp_path) -> None:
    config = _seed_snapshot(tmp_path)
    con = duckdb.connect(str(config.db_path))
    con.execute("ALTER TABLE ds_observations DROP COLUMN condition_json")
    con.execute("CHECKPOINT")
    con.close()

    run_content_stage_with_receipt(config, "qc")

    payload = json.loads((config.component_dir / "observed_support.json").read_text())
    assert payload["observation_table_present"] is True
    assert payload["required_columns_present"] is False
    assert payload["missing_required_columns"] == ["condition_json"]
    assert payload["points"] == []
    assert current_content_stage_receipt(config, "qc") is not None


def test_qc_receipt_rejects_self_consistent_inventory_missing_support_entry(tmp_path) -> None:
    config = _seed_snapshot(tmp_path)
    run_content_stage_with_receipt(config, "qc")
    assert current_content_stage_receipt(config, "qc") is not None

    support_path = config.component_dir / "observed_support.json"
    state = json.loads(config.stage_state_path.read_text(encoding="utf-8"))
    saved_inventory = state["qc"]["output_inventory"]
    entries = saved_inventory["entries"]
    support_entry = next(entry for entry in entries if entry["path"] == str(support_path.resolve()))
    assert support_entry["exists"] is True
    output_paths = [Path(str(entry["path"])) for entry in entries]
    assert support_path.resolve() in [path.resolve() for path in output_paths]
    before_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths}

    subset_paths = [path for path in output_paths if path.resolve() != support_path.resolve()]
    assert len(subset_paths) == len(output_paths) - 1
    state["qc"]["output_inventory"] = build_output_inventory(subset_paths)
    write_json(config.stage_state_path, state)

    assert all(path.is_file() for path in output_paths)
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths
    } == before_hashes
    assert current_content_stage_receipt(config, "qc") is None
