"""Tests for ChainedAuditLog adapter and NoopAuditLog."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.security.audit_log_adapter import ChainedAuditLog
from polisyos.core.security.audit_models import AuditActor, AuditEventType, AuditResource
from polisyos.core.security.audit_protocol import AuditLog, NoopAuditLog

_FAKE_ID = "sha256:" + "bb" * 32


class TestNoopAuditLog:
    def test_satisfies_protocol(self):
        noop = NoopAuditLog()
        assert isinstance(noop, AuditLog)

    def test_append_is_noop(self):
        noop = NoopAuditLog()
        noop.append(run_id="r", actor="a", action="X")  # no exception

    def test_close_is_noop(self):
        noop = NoopAuditLog()
        noop.close()  # no exception


class TestChainedAuditLog:
    def test_satisfies_protocol(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        assert isinstance(log, AuditLog)

    def test_append_calls_sink(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        log.append(
            run_id="run-001",
            actor="engine",
            action="NODE_COMPLETED",
            metadata={"alias": "plan", "duration_ms": 42},
        )
        sink.log_audit_event.assert_called_once()
        kwargs = sink.log_audit_event.call_args[1]
        assert kwargs["event_type"] == AuditEventType.AUDIT_ACTION
        assert kwargs["payload"]["action"] == "NODE_COMPLETED"
        assert kwargs["payload"]["alias"] == "plan"
        assert kwargs["actor"] == AuditActor(identity="engine")
        assert kwargs["resource"] == AuditResource(type="run", id="run-001")

    def test_append_with_artifact_refs(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        ref = ArtifactRef(artifact_id=_FAKE_ID, kind="checkpoint", media_type="application/json")
        log.append(
            run_id="run-002",
            actor="engine",
            action="CHECKPOINT_CREATED",
            artifact_refs=[ref],
        )
        payload = sink.log_audit_event.call_args[1]["payload"]
        assert "artifact_refs" in payload
        assert payload["artifact_refs"][0]["kind"] == "checkpoint"

    def test_governance_decision_mapping(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        log.append(
            run_id="run-003",
            actor="governance",
            action="GOVERNANCE_DECISION",
        )
        kwargs = sink.log_audit_event.call_args[1]
        assert kwargs["event_type"] == AuditEventType.GOVERNANCE_DECISION

    def test_unknown_action_falls_back(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        log.append(
            run_id="run-004",
            actor="custom",
            action="CUSTOM_EVENT",
        )
        kwargs = sink.log_audit_event.call_args[1]
        assert kwargs["event_type"] == AuditEventType.AUDIT_ACTION

    def test_close_calls_shutdown(self):
        sink = MagicMock()
        log = ChainedAuditLog(sink)
        log.close()
        sink.shutdown.assert_called_once()

    def test_close_no_shutdown_method(self):
        sink = MagicMock(spec=[])  # no methods at all
        log = ChainedAuditLog(sink)
        log.close()  # should not raise
