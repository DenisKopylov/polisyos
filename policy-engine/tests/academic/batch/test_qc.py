from __future__ import annotations

import json

import duckdb

from polisyos.batch_common.manifest import write_raw_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.qc import run_qc


def test_academic_qc_passes_minimal_snapshot(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "W1", "abstract": "Some abstract", "estimates": [{"value": 0.2}]}) + "\n")
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=True)
    assert report.passed is True
    assert config.qc_report_path.exists()


def test_academic_qc_fail_fast_on_manifest_mismatch(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=2,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"id":"W1","abstract":"x","estimates":[]}\n', encoding="utf-8")
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    try:
        run_qc(config, fail_fast=True)
    except RuntimeError as exc:
        assert "manifest_count_parity" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for fail-fast QC")
