from __future__ import annotations

# ruff: noqa: S101
import hashlib
import json
from datetime import UTC, datetime

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)


def test_nested_secret_forces_exact_small_payload_through_cas(tmp_path) -> None:
    payload = {"request": {"api_key": "short-secret-value"}, "phase": "started"}
    expected_bytes = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    log = RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "control.sqlite3",
        ),
        artifact_store=FileSystemCAS(tmp_path / "cas"),
    )
    event = DiagnosticEvent(
        event_id="evt-nested-secret",
        event_source="polisyos.runtime.test",
        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
        event_time=datetime(2026, 10, 10, 9, 0, tzinfo=UTC),
        event_subject="run/run-1/job/job-1/phase/test",
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id="trace-secret",
        span_id="span-secret",
        parent_span_id=None,
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
        producer_component="runtime-quality-test",
        producer_version="test",
        execution_profile="dev",
        phase="test",
        state_before="running",
        state_after="persisted",
        payload_ref=None,
        artifact_refs=(),
        input_refs=(),
        blocking_status=None,
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key="evt-nested-secret",
        sampling_decision="always_record",
        sampling_rate=None,
    )

    record = log.append(
        event,
        payload=payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=False),
    )

    assert len(expected_bytes) < 2048
    assert record.payload_inline is None
    assert record.payload_ref == record.event.payload_ref
    assert record.payload_ref is not None
    stored_bytes = log.artifact_store.get_bytes(ArtifactID.model_validate(record.payload_ref))
    assert stored_bytes == expected_bytes
    assert json.loads(stored_bytes) == payload
    assert record.payload_sha256 == "sha256:" + hashlib.sha256(expected_bytes).hexdigest()
