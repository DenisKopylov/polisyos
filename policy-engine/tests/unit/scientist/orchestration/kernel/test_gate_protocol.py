"""Tests for polisyos.scientist.orchestration.kernel.gate_protocol — HumanGateProtocol."""

from __future__ import annotations

import pytest
from polisyos.ir.governance.gate import (
    GateContext,
    GateDecision,
    GateEventType,
    GatePriority,
    GateRequest,
    GateVerdict,
)
from polisyos.scientist.orchestration.kernel.gate_protocol import (
    HumanGateProtocol,
    _extract_trace_correlation,
    _priority_to_int,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_gate_context(**overrides) -> GateContext:
    defaults = dict(
        workflow_id="wf_test",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
    )
    defaults.update(overrides)
    return GateContext(**defaults)


@pytest.fixture
def protocol(mock_run_context):
    return HumanGateProtocol(mock_run_context)


# ---------------------------------------------------------------------------
# request_gate
# ---------------------------------------------------------------------------


class TestRequestGate:
    def test_returns_gate_request_and_ref(self, protocol, mock_store):
        ctx = _make_gate_context()
        request, ref = protocol.request_gate(
            run_id="run-1",
            reason="needs review",
            context=ctx,
        )
        assert isinstance(request, GateRequest)
        assert request.run_id == "run-1"
        assert request.reason == "needs review"
        assert request.priority == GatePriority.NORMAL
        assert request.requested_by == "system"
        assert ref == mock_store.put_json.return_value

    def test_deterministic_request_id(self, protocol):
        ctx = _make_gate_context()
        req1, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        req2, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        assert req1.request_id == req2.request_id

    def test_different_context_different_id(self, protocol):
        ctx1 = _make_gate_context(iteration=1)
        ctx2 = _make_gate_context(iteration=2)
        req1, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx1)
        req2, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx2)
        assert req1.request_id != req2.request_id

    def test_custom_priority(self, protocol):
        ctx = _make_gate_context()
        request, _ = protocol.request_gate(
            run_id="run-1",
            reason="urgent",
            context=ctx,
            priority=GatePriority.CRITICAL,
        )
        assert request.priority == GatePriority.CRITICAL

    def test_custom_timeout(self, protocol):
        ctx = _make_gate_context()
        request, _ = protocol.request_gate(
            run_id="run-1",
            reason="r",
            context=ctx,
            timeout_seconds=300,
        )
        assert request.timeout_seconds == 300

    def test_custom_requested_by(self, protocol):
        ctx = _make_gate_context()
        request, _ = protocol.request_gate(
            run_id="run-1",
            reason="r",
            context=ctx,
            requested_by="admin",
        )
        assert request.requested_by == "admin"

    def test_store_put_json_called(self, protocol, mock_store):
        ctx = _make_gate_context()
        protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        mock_store.put_json.assert_called_once()
        call_args = mock_store.put_json.call_args
        payload = call_args[0][0]
        assert payload["run_id"] == "run-1"
        assert payload["reason"] == "r"

    def test_event_emitted(self, protocol, mock_run_context):
        ctx = _make_gate_context()
        protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        mock_run_context.emit.assert_called_once()
        call_kwargs = mock_run_context.emit.call_args
        assert (
            call_kwargs[1]["event"] == GateEventType.GATE_REQUESTED.value
            or call_kwargs[0][1] == GateEventType.GATE_REQUESTED.value
        )


# ---------------------------------------------------------------------------
# record_decision
# ---------------------------------------------------------------------------


class TestRecordDecision:
    def test_returns_decision_and_ref(self, protocol, mock_store):
        ctx = _make_gate_context()
        request, request_ref = protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        mock_store.put_json.reset_mock()

        decision, ref = protocol.record_decision(
            request,
            verdict=GateVerdict.APPROVE,
            approver_id="user-1",
        )
        assert isinstance(decision, GateDecision)
        assert decision.verdict == GateVerdict.APPROVE
        assert decision.approver_id == "user-1"
        assert decision.request_id == request.request_id
        assert decision.run_id == "run-1"

    def test_optional_fields(self, protocol):
        ctx = _make_gate_context()
        request, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx)

        decision, _ = protocol.record_decision(
            request,
            verdict=GateVerdict.REJECT,
            approver_id="admin",
            reason_codes=["R1", "R2"],
            comment="Not compliant",
            evidence_refs=["ref-1"],
        )
        assert decision.reason_codes == ["R1", "R2"]
        assert decision.comment == "Not compliant"
        assert decision.evidence_refs == ["ref-1"]

    def test_default_optional_fields(self, protocol):
        ctx = _make_gate_context()
        request, _ = protocol.request_gate(run_id="run-1", reason="r", context=ctx)

        decision, _ = protocol.record_decision(
            request,
            verdict=GateVerdict.APPROVE,
            approver_id="u",
        )
        assert decision.reason_codes == []
        assert decision.comment is None
        assert decision.evidence_refs == []


# ---------------------------------------------------------------------------
# persist_decision
# ---------------------------------------------------------------------------


class TestPersistDecision:
    def test_persist_calls_store(self, protocol, mock_store):
        ctx = _make_gate_context()
        request, request_ref = protocol.request_gate(run_id="run-1", reason="r", context=ctx)
        decision = GateDecision(
            request_id=request.request_id,
            run_id="run-1",
            verdict=GateVerdict.APPROVE,
            approver_id="user-1",
        )
        mock_store.put_json.reset_mock()

        ref = protocol.persist_decision(decision, request_ref=request_ref)
        mock_store.put_json.assert_called_once()
        call_args = mock_store.put_json.call_args
        opts = call_args[0][1]
        assert opts.kind == "ir.gate_decision"

    def test_persist_without_request_ref(self, protocol, mock_store):
        decision = GateDecision(
            request_id="req-1",
            run_id="run-1",
            verdict=GateVerdict.REJECT,
            approver_id="u",
        )
        mock_store.put_json.reset_mock()
        protocol.persist_decision(decision)
        mock_store.put_json.assert_called_once()


# ---------------------------------------------------------------------------
# _extract_trace_correlation
# ---------------------------------------------------------------------------


class TestExtractTraceCorrelation:
    def test_no_valid_span_returns_none(self):
        result = _extract_trace_correlation()
        assert "trace_id" in result
        assert "span_id" in result


# ---------------------------------------------------------------------------
# _priority_to_int
# ---------------------------------------------------------------------------


class TestPriorityToInt:
    @pytest.mark.parametrize(
        "priority,expected",
        [
            (GatePriority.LOW, 0),
            (GatePriority.NORMAL, 1),
            (GatePriority.HIGH, 2),
            (GatePriority.CRITICAL, 3),
        ],
    )
    def test_mapping(self, priority, expected):
        assert _priority_to_int(priority) == expected
