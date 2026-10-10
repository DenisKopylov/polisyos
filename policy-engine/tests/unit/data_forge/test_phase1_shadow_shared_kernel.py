from __future__ import annotations

import json
import sys

import pytest

from polisyos.data_forge.kernel.io import sha256_file
from polisyos.data_forge.kernel.pipeline import (
    read_manifest,
    validate_manifest_artifacts,
    write_publish_manifest,
    write_raw_manifest,
    write_stage_manifest,
)
from polisyos.data_forge.kernel.quality import (
    QCCheck,
    QCReport,
    evaluate_fail_fast,
    write_qc_report,
)
from polisyos.data_forge.kernel.snapshot import finalize_snapshot


def test_shadow_manifest_writers_match_legacy_shapes_without_legacy_imports(tmp_path) -> None:
    before = {
        name
        for name in sys.modules
        if name.startswith("polisyos.batch_common") or name.startswith("polisyos.batch_snapshot")
    }
    payload_path = tmp_path / "payload.jsonl"
    payload_path.write_text('{"id": 1}\n', encoding="utf-8")

    raw_path = write_raw_manifest(
        manifest_path=tmp_path / "manifests" / "raw.json",
        source="fixture",
        endpoint="file://fixture",
        payload_path=payload_path,
        count=1,
        filters={"status": "current"},
        parser_version="test",
        fetched_at="2026-04-24T00:00:00+00:00",
    )
    stage_path = write_stage_manifest(
        manifest_path=tmp_path / "manifests" / "stage.json",
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=(payload_path,),
        started_at="2026-04-24T00:00:00+00:00",
        finished_at="2026-04-24T00:00:01+00:00",
    )
    publish_path = write_publish_manifest(
        manifest_path=tmp_path / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=(payload_path, stage_path),
        qc_report_path=tmp_path / "qc_report.json",
        extra={"consumer_ready": True},
        published_at="2026-04-24T00:00:02+00:00",
    )

    raw = read_manifest(raw_path)
    assert raw == {
        "kind": "raw",
        "source": "fixture",
        "endpoint": "file://fixture",
        "fetched_at": "2026-04-24T00:00:00+00:00",
        "count": 1,
        "payload": str(payload_path),
        "sha256": sha256_file(payload_path),
        "filters": {"status": "current"},
        "parser_version": "test",
    }

    stage = read_manifest(stage_path)
    assert stage["kind"] == "stage"
    assert stage["stage"] == "normalize"
    assert stage["status"] == "ok"
    assert stage["metrics"] == {"rows": 1}
    assert stage["artifacts"] == [{"path": str(payload_path), "sha256": sha256_file(payload_path)}]

    publish = read_manifest(publish_path)
    assert publish["kind"] == "publish"
    assert publish["pipeline"] == "academic"
    assert publish["qc_report"] == str(tmp_path / "qc_report.json")
    assert publish["extra"] == {"consumer_ready": True}
    assert len(publish["artifacts"]) == 2
    assert all(result.passed for result in validate_manifest_artifacts(publish_path))

    after = {
        name
        for name in sys.modules
        if name.startswith("polisyos.batch_common") or name.startswith("polisyos.batch_snapshot")
    }
    assert after == before


def test_shadow_qc_report_matches_legacy_shape_and_fail_fast(tmp_path) -> None:
    report = QCReport(
        scope="catalog",
        checks=(
            QCCheck(name="critical_ok", passed=True, value=1, threshold=1),
            QCCheck(name="warning_failed", passed=False, severity="warning", message="advisory"),
        ),
        metrics={"rows": 2},
    )

    assert report.passed is True
    out_path = write_qc_report(tmp_path / "qc_report.json", report)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["scope"] == "catalog"
    assert payload["passed"] is True
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][1]["status"] == "failed"

    failing = QCReport(scope="catalog", checks=(QCCheck(name="critical_failed", passed=False),))
    with pytest.raises(RuntimeError, match="critical_failed"):
        evaluate_fail_fast(failing, fail_fast=True)


def test_shadow_snapshot_finalize_aggregates_publish_manifests(tmp_path) -> None:
    snapshot_root = tmp_path / "snapshot"
    for pipeline in ("datasets", "academic", "lex"):
        pipeline_root = snapshot_root / pipeline
        artifact_path = pipeline_root / "artifact.txt"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{pipeline}\n", encoding="utf-8")
        write_publish_manifest(
            manifest_path=pipeline_root / "publish" / "manifest.json",
            pipeline=pipeline,
            artifacts=(artifact_path,),
            published_at="2026-04-24T00:00:02+00:00",
        )

    out_path = finalize_snapshot(snapshot_root, update_latest_symlink=False)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["kind"] == "snapshot"
    assert payload["snapshot_root"] == str(snapshot_root)
    assert set(payload["pipelines"]) == {"datasets", "academic", "lex"}
    assert [item["pipeline"] for item in payload["artifacts"]] == [
        "datasets",
        "academic",
        "lex",
    ]
    assert all(item["sha256"] for item in payload["artifacts"])
