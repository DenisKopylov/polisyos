from __future__ import annotations

import json
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.observability import get_metrics
from polisyos.fabric.data_plane.cli import main as quarantine_cli_main
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    build_quarantine_report,
    list_quarantine_records,
    persist_quarantine_record,
    reprocess_quarantine_records,
)


def test_quarantine_roundtrip_report_and_reprocess(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    first = persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="transform_error",
            severity="error",
            source="connector.transform:test.conn:demo",
            schema_version="1.0.0",
            downstream_impacts=("connector_cache", "evidence_bundle"),
        ),
        raw_payload={"row": 1},
    )
    persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="non_finite_metric",
            severity="warning",
            source="connector.fetch:test.conn:demo",
            schema_version="1.0.0",
            downstream_impacts=("data_snapshot",),
        ),
        raw_payload={"value": "inf"},
    )

    records = list_quarantine_records(store)
    report = build_quarantine_report(records)

    assert len(records) == 2
    assert report.total_records == 2
    assert report.by_reason["transform_error"] == 1
    assert report.by_reason["non_finite_metric"] == 1
    assert report.downstream_impacts["connector_cache"] == 1
    assert report.downstream_impacts["data_snapshot"] == 1

    result = reprocess_quarantine_records(
        store,
        artifact_ids=[str(first.artifact_id)],
        handler=lambda payload, record: {
            "row": payload["row"] + 1,
            "reason": record.reason,
        },
    )

    assert result.attempted == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert len(result.result_refs) == 1


def test_quarantine_cli_report_and_reprocess(tmp_path, monkeypatch, capsys):
    store = FileSystemCAS(tmp_path / "cas")
    persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="poison_stream_message",
            severity="error",
            source="connector.stream:test.conn:demo",
            schema_version="1.0.0",
            downstream_impacts=("streaming_windowed", "data_snapshot"),
        ),
        raw_payload={"message": "bad"},
    )

    handler_module = tmp_path / "dlq_handler.py"
    handler_module.write_text(
        "def replay(payload, record):\n"
        "    return {'record_id': record.record_id, 'message': payload['message']}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    exit_code = quarantine_cli_main(["--cas-root", str(store.root), "report"])
    report_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report_payload["total_records"] == 1
    assert report_payload["by_reason"]["poison_stream_message"] == 1

    exit_code = quarantine_cli_main(
        [
            "--cas-root",
            str(store.root),
            "reprocess",
            "--handler",
            "dlq_handler:replay",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert replay_payload["attempted"] == 1
    assert replay_payload["succeeded"] == 1


def test_quarantine_cli_uses_artifact_store_factory(tmp_path, monkeypatch, capsys):
    backing_store = FileSystemCAS(tmp_path / "cas")
    persist_quarantine_record(
        backing_store,
        record=QuarantineRecord.new(
            reason="factory_path",
            severity="warning",
            source="connector.fetch:test.conn:factory",
            schema_version="1.0.0",
        ),
        raw_payload={"value": 1},
    )

    seen: dict[str, Any] = {}

    def _fake_build_artifact_store(config):
        seen["config"] = config
        return backing_store

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.cli.build_artifact_store",
        _fake_build_artifact_store,
    )

    exit_code = quarantine_cli_main(["--cas-root", str(backing_store.root), "report"])
    report_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert report_payload["total_records"] == 1
    assert seen["config"].backend == "filesystem"
    assert seen["config"].root == str(backing_store.root)


def test_persist_quarantine_record_uses_injected_metrics(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas")
    metrics = get_metrics()
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.quarantine.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics fallback should not be used")),
    )

    ref = persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="typed_guard",
            severity="warning",
            source="connector.fetch:test.conn:typed",
            schema_version="1.0.0",
        ),
        raw_payload={"value": "nan"},
        metrics=metrics,
    )

    assert str(ref.artifact_id)
    records = list_quarantine_records(store)
    assert len(records) == 1
