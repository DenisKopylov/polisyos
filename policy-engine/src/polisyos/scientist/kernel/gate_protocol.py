from __future__ import annotations

import hashlib

try:
    from opentelemetry import trace
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class _NoopSpanContext:
        is_valid = False
        trace_id = 0
        span_id = 0

    class _NoopSpan:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def is_recording(self) -> bool:
            return False

        def add_event(self, _name: str, _attrs=None) -> None:
            return None

        def get_span_context(self) -> _NoopSpanContext:
            return _NoopSpanContext()

    class _NoopTracer:
        def start_as_current_span(self, _name: str):
            return _NoopSpan()

    class _NoopTraceModule:
        def get_tracer(self, _name: str) -> _NoopTracer:
            return _NoopTracer()

        def get_current_span(self) -> _NoopSpan:
            return _NoopSpan()

    trace = _NoopTraceModule()  # type: ignore[assignment]

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.run.context import RunContext
from polisyos.ir.gate import (
    GateContext,
    GateDecision,
    GateEvent,
    GateEventType,
    GatePriority,
    GateRequest,
    GateVerdict,
)


class HumanGateProtocol:
    """Typed gate lifecycle with CAS + trace audit integration."""

    def __init__(self, run_ctx: RunContext) -> None:
        self._run_ctx = run_ctx
        self._store = run_ctx.store
        self._tracer = trace.get_tracer("polisyos.scientist.gate")

    def request_gate(
        self,
        *,
        run_id: str,
        reason: str,
        context: GateContext,
        priority: GatePriority = GatePriority.NORMAL,
        timeout_seconds: int | None = None,
        requested_by: str = "system",
    ) -> tuple[GateRequest, ArtifactRef]:
        request_id = self._generate_deterministic_request_id(run_id=run_id, context=context)
        request = GateRequest(
            request_id=request_id,
            run_id=run_id,
            reason=reason,
            context=context,
            priority=priority,
            timeout_seconds=timeout_seconds,
            requested_by=requested_by,
        )

        request_ref = self._store.put_json(
            request.model_dump(mode="json"),
            PutOptions(
                kind="ir.gate_request",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.GateRequest", version=request.schema_version),
                producer=ProducerInfo(component="ir.gate_protocol", version="1.0.0"),
            ),
        )

        event = GateEvent(
            event_type=GateEventType.GATE_REQUESTED,
            run_id=run_id,
            request_id=request.request_id,
            payload=request.model_dump(mode="json"),
            **_extract_trace_correlation(),
        )
        self._emit_gate_event(
            event,
            outputs=[request_ref],
            metrics={"gate_priority": _priority_to_int(request.priority)},
        )
        return request, request_ref

    def record_decision(
        self,
        request: GateRequest,
        *,
        verdict: GateVerdict,
        approver_id: str,
        reason_codes: list[str] | None = None,
        comment: str | None = None,
        evidence_refs: list[str] | None = None,
        request_ref: ArtifactRef | None = None,
    ) -> tuple[GateDecision, ArtifactRef]:
        decision = GateDecision(
            request_id=request.request_id,
            run_id=request.run_id,
            verdict=verdict,
            approver_id=approver_id,
            reason_codes=reason_codes or [],
            comment=comment,
            evidence_refs=evidence_refs or [],
        )
        decision_ref = self.persist_decision(decision, request_ref=request_ref)
        return decision, decision_ref

    def persist_decision(
        self,
        decision: GateDecision,
        *,
        request_ref: ArtifactRef | None = None,
    ) -> ArtifactRef:
        inputs = []
        if request_ref is not None:
            inputs.append(InputRef(artifact_id=request_ref.artifact_id, role="gate_request"))

        decision_ref = self._store.put_json(
            decision.model_dump(mode="json"),
            PutOptions(
                kind="ir.gate_decision",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.GateDecision", version=decision.schema_version),
                producer=ProducerInfo(component="ir.gate_protocol", version="1.0.0"),
                inputs=inputs,
            ),
        )

        event = GateEvent(
            event_type=GateEventType.GATE_DECIDED,
            run_id=decision.run_id,
            request_id=decision.request_id,
            payload=decision.model_dump(mode="json"),
            **_extract_trace_correlation(),
        )
        self._emit_gate_event(event, outputs=[decision_ref])
        return decision_ref

    def _emit_gate_event(
        self,
        event: GateEvent,
        *,
        outputs: list[ArtifactRef] | None = None,
        metrics: dict[str, int | float] | None = None,
    ) -> None:
        self._run_ctx.emit(
            phase="governance.gate",
            event=event.event_type.value,
            outputs=outputs,
            metrics=metrics,
        )

        with self._tracer.start_as_current_span("human_gate.event") as span:
            if span.is_recording():
                span.add_event(
                    event.event_type.value,
                    {
                        "gate.request_id": event.request_id,
                        "gate.run_id": event.run_id,
                    },
                )

    def _generate_deterministic_request_id(
        self,
        *,
        run_id: str,
        context: GateContext,
    ) -> str:
        key = f"{run_id}:{context.phase}:{context.node_alias}:{context.iteration}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _extract_trace_correlation() -> dict[str, str | None]:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.is_valid:
        return {"trace_id": None, "span_id": None}
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


def _priority_to_int(priority: GatePriority) -> int:
    mapping: dict[GatePriority, int] = {
        GatePriority.LOW: 0,
        GatePriority.NORMAL: 1,
        GatePriority.HIGH: 2,
        GatePriority.CRITICAL: 3,
    }
    return mapping.get(priority, 1)
