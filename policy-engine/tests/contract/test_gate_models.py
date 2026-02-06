from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.gate import GateContext, GateDecision, GateRequest, GateVerdict


def test_gate_request_roundtrip() -> None:
    context = GateContext(
        workflow_id="scientist_default",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
    )
    request = GateRequest(
        request_id="abc123",
        run_id="R_test",
        reason="manual review required",
        context=context,
    )

    dumped = request.model_dump(mode="json")
    restored = GateRequest.model_validate(dumped)

    assert restored.request_id == "abc123"
    assert restored.context.node_alias == "run_governance"


def test_gate_context_iteration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        GateContext(
            workflow_id="scientist_default",
            node_alias="run_governance",
            phase="POSTFLIGHT_GOV",
            iteration=0,
        )


def test_gate_decision_requires_typed_verdict() -> None:
    decision = GateDecision(
        request_id="abc123",
        run_id="R_test",
        verdict=GateVerdict.REJECT,
        approver_id="ops.admin",
        reason_codes=["LEGAL_BLOCKER"],
    )
    assert decision.verdict == GateVerdict.REJECT
