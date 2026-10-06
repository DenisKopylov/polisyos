import json
import tempfile
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.pipeline import (
    _stage_input_basis,
    current_content_stage_receipt,
    run_content_stage_with_receipt,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_raw_manifest

with tempfile.TemporaryDirectory(prefix="dfi-qc-readset-") as scratch:
    config = DatasetBatchConfig(snapshot_root=Path(scratch) / "snapshot")
    raw_dir = config.raw_dir / "oecd" / "20261006T000000Z"
    raw_dir.mkdir(parents=True)
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
    config.merged_records_path.write_text(
        json.dumps({"title": "Dataset", "description": "Desc", "source": "oecd"}) + "\n",
        encoding="utf-8",
    )
    config.duplicates_report_path.write_text(
        "source,dedup_key,kept_id,dropped_id\noecd,key,keep,drop\n",
        encoding="utf-8",
    )
    with duckdb.connect(str(config.db_path)) as con:
        con.execute("CREATE TABLE IF NOT EXISTS ds_distributions (url VARCHAR)")
        con.execute("CHECKPOINT")

    qc_report = run_content_stage_with_receipt(config, "qc")
    before_basis = _stage_input_basis(config, "qc")
    before_receipt = current_content_stage_receipt(config, "qc")
    report_payload = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    saved_duplicate_ratio = report_payload["metrics"]["duplicate_ratio_pct"]

    config.merged_records_path.write_text(
        json.dumps({"title": "Dataset", "description": "Desc", "source": "oecd"}) + "\n"
        + json.dumps({"title": "Second", "description": "Desc", "source": "oecd"}) + "\n",
        encoding="utf-8",
    )
    config.duplicates_report_path.write_text(
        "source,dedup_key,kept_id,dropped_id\n",
        encoding="utf-8",
    )
    after_basis = _stage_input_basis(config, "qc")
    after_receipt = current_content_stage_receipt(config, "qc")
    current_duplicate_ratio = 0.0

    print(json.dumps({
        "qc_producer_passed": bool(qc_report.passed),
        "receipt_before_mutation": before_receipt is not None,
        "basis_digest_before": before_basis["basis_digest"],
        "basis_digest_after": after_basis["basis_digest"],
        "basis_unchanged_after_mutating_qc_read_files": before_basis == after_basis,
        "receipt_still_accepted_after_mutating_qc_read_files": after_receipt is not None,
        "saved_qc_duplicate_ratio_pct": saved_duplicate_ratio,
        "ratio_for_current_merged_and_duplicate_inputs_pct": current_duplicate_ratio,
        "changed_inputs": ["merged_records_path", "duplicates_report_path"],
    }, sort_keys=True))
