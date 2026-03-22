from __future__ import annotations

import json
from pathlib import Path

from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.pipeline import run_dataset_pipeline_sync


def test_pipeline_writes_telemetry_when_qc_fails(monkeypatch, tmp_path) -> None:
    def _boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("qc exploded")

    monkeypatch.setattr("polisyos.datasets.batch.qc.run_qc", _boom)
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

    try:
        run_dataset_pipeline_sync(config)
    except RuntimeError as exc:
        assert "qc exploded" in str(exc)
    else:
        raise AssertionError("Expected pipeline to propagate QC failure")

    assert config.telemetry_path.exists()
    with open(config.telemetry_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert payload["pipeline_status"] == "failed"
    assert payload["current_stage"] == "qc"
    assert "qc exploded" in payload["error"]
