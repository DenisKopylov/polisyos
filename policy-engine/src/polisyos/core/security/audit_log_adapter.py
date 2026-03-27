"""Adapter: wraps ``ChainedAuditSink`` to expose the ``AuditLog`` protocol."""

from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef

from .audit_models import AuditActor, AuditCorrelation, AuditEventType, AuditResource


def _get_current_trace_context() -> tuple[str, str]:
    """Extract trace_id and span_id from current OTel span, if available."""
    try:
        from opentelemetry import trace as otel_trace

        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:  # noqa: BLE001
        pass
    return "", ""


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

        trace_id, span_id = _get_current_trace_context()
        self._sink.log_audit_event(
            event_type=event_type,
            payload=payload,
            actor=AuditActor(identity=actor),
            resource=AuditResource(type="run", id=run_id),
            correlation=AuditCorrelation(
                run_id=run_id, trace_id=trace_id, span_id=span_id,
            ),
        )

    def close(self) -> None:
        if hasattr(self._sink, "shutdown"):
            self._sink.shutdown()
