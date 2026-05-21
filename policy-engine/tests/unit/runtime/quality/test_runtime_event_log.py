from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _event(**overrides: object) -> DiagnosticEvent:
    payload = {
        "event_id": "evt-001",
        "event_source": "polisyos.runtime.producer",
        "event_type": "polisyos.runtime.diagnostic.producer_execution.v1",
        "event_time": datetime(2026, 5, 15, 9, 0, tzinfo=UTC),
        "event_subject": "run/run-001/job/job-001/phase/foundry",
        "schema_name": "polisyos.runtime.quality.diagnostic_event",
        "schema_version": "1.0",
        "trace_id": "trace-001",
        "span_id": "span-001",
        "parent_span_id": None,
        "run_id": "run-001",
        "job_id": "job-001",
        "tenant_id": "tenant-001",
        "cell_id": "cell-a",
        "producer_component": "runtime.producer",
        "producer_version": "2026.05.15",
        "execution_profile": "production",
        "phase": "foundry",
        "state_before": "running",
        "state_after": "persisted",
        "payload_ref": None,
        "artifact_refs": [_sha("2")],
        "input_refs": [_sha("3")],
        "blocking_status": None,
        "redaction_policy_ref": "redaction-policy/runtime-diagnostics-v1",
        "duplicate_of": None,
        "dedupe_key": "job-001:foundry:producer",
        "sampling_decision": "always_record",
        "sampling_rate": 1.0,
    }
    payload.update(overrides)
    return DiagnosticEvent.model_validate(payload)


def _event_log(tmp_path) -> RuntimeDiagnosticEventLog:
    store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    return RuntimeDiagnosticEventLog(
        store=store,
        artifact_store=FileSystemCAS(tmp_path / "cas"),
    )


def test_authority_event_payload_goes_through_cas_and_preserves_trace(tmp_path) -> None:
    event_log = _event_log(tmp_path)

    record = event_log.append(
        _event(),
        payload={"decision": "accepted", "hidden_answer": "redacted"},
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )

    assert record.event.payload_ref is not None
    assert record.payload_inline is None
    assert record.payload_ref == record.event.payload_ref
    assert record.event.trace_id == "trace-001"
    assert record.event.span_id == "span-001"
    assert event_log.artifact_store.has(record.event.payload_ref)


def test_small_non_sensitive_event_payload_can_be_stored_inline(tmp_path) -> None:
    event_log = _event_log(tmp_path)

    record = event_log.append(
        _event(event_id="evt-inline", execution_profile="dev", sampling_rate=None),
        payload={"progress": "started"},
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=False),
    )

    assert record.event.payload_ref is None
    assert record.payload_ref is None
    assert record.payload_inline == {"progress": "started"}


@pytest.mark.parametrize("action", ["supersede", "withdraw", "reconcile", "quarantine"])
def test_corrective_actions_append_events_without_mutating_history(tmp_path, action: str) -> None:
    event_log = _event_log(tmp_path)
    original = event_log.append(
        _event(event_id=f"evt-original-{action}", state_after="persisted"),
        payload={"decision": "accepted"},
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )

    correction = event_log.append_correction(
        original_event_id=original.event.event_id,
        action=action,
        reason=f"{action} after reconciliation",
        trace_id=original.event.trace_id,
        run_id=original.event.run_id,
        job_id=original.event.job_id,
        tenant_id=original.event.tenant_id,
        cell_id=original.event.cell_id,
        execution_profile=original.event.execution_profile,
        phase="reconciliation",
    )

    records = event_log.list_events(event_id=original.event.event_id)
    assert len(records) == 1
    assert records[0].event.state_after == "persisted"
    assert correction.event.event_id != original.event.event_id
    assert correction.event.duplicate_of == original.event.event_id
    assert correction.event.event_type == "polisyos.runtime.diagnostic.reconciliation_result.v1"
    assert correction.payload_ref is not None
    assert correction.payload_inline is None
