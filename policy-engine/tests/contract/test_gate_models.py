from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.ir.governance.gate import GateContext, GateDecision, GateRequest, GateVerdict


def test_gate_request_roundtrip() -> None:
    context = GateContext(
        workflow_id="scientist_default",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
        policy_summary="Policy with 1 intervention(s)",
        simulation_results={"gdp_change": 1},
        issue_summary={"requested_items": 2},
        artifact_refs={"causal_report_ref": "sha256:" + ("a" * 64)},
        transport_summary={"status": "transportable"},
        replay_summary={"readiness": "partial"},
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
    assert restored.schema_version == "1.1"
    assert restored.context.node_alias == "run_governance"
    assert restored.context.policy_summary == "Policy with 1 intervention(s)"
    assert restored.context.replay_summary == {"readiness": "partial"}


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
