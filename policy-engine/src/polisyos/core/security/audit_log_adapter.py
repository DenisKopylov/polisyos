"""Adapter: wraps ``ChainedAuditSink`` to expose the ``AuditLog`` protocol."""

from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef

from .audit_models import AuditActor, AuditCorrelation, AuditEventType, AuditResource


class ChainedAuditLog:
    """Bridges the simple ``AuditLog.append()`` interface to the
    ``ChainedAuditSink.log_audit_event()`` method.
    """

    # Map well-known action strings to AuditEventType.  Unknown actions
    # fall back to AUDIT_ACTION.
    _ACTION_MAP: dict[str, AuditEventType] = {
        "NODE_STARTED": AuditEventType.AUDIT_ACTION,
        "NODE_COMPLETED": AuditEventType.AUDIT_ACTION,
        "NODE_FAILED": AuditEventType.AUDIT_ACTION,
        "CHECKPOINT_CREATED": AuditEventType.AUDIT_ACTION,
        "CHECKPOINT_RESUMED": AuditEventType.AUDIT_ACTION,
        "BUDGET_CHECK": AuditEventType.AUDIT_ACTION,
        "BUDGET_EXCEEDED": AuditEventType.AUDIT_ACTION,
        "TOOL_INVOKED": AuditEventType.AUDIT_ACTION,
        "TOOL_COMPLETED": AuditEventType.AUDIT_ACTION,
        "TOOL_FAILED": AuditEventType.AUDIT_ACTION,
        "GOVERNANCE_DECISION": AuditEventType.GOVERNANCE_DECISION,
    }

    def __init__(self, sink: Any) -> None:
        self._sink = sink

    def append(
        self,
        *,
        run_id: str,
        actor: str,
        action: str,
        artifact_refs: list[ArtifactRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event_type = self._ACTION_MAP.get(action, AuditEventType.AUDIT_ACTION)
        payload: dict[str, Any] = {"action": action}
        if metadata:
            payload.update(metadata)
        if artifact_refs:
            payload["artifact_refs"] = [
                {"artifact_id": str(r.artifact_id), "kind": r.kind}
                for r in artifact_refs
            ]

        self._sink.log_audit_event(
            event_type=event_type,
            payload=payload,
            actor=AuditActor(identity=actor),
            resource=AuditResource(type="run", id=run_id),
            correlation=AuditCorrelation(run_id=run_id),
        )

    def close(self) -> None:
        if hasattr(self._sink, "shutdown"):
            self._sink.shutdown()
