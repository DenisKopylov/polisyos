from __future__ import annotations

import json
from pathlib import Path

import duckdb

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
