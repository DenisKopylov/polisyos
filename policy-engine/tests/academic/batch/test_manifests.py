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


def test_publish_manifest_contains_pipeline_name(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.db_path.write_text("db", encoding="utf-8")
    config.qc_report_path.write_text("{}", encoding="utf-8")

    manifest_path = run_publish(config)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["pipeline"] == "academic"
    assert manifest_path.exists()
