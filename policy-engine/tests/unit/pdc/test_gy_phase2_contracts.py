from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import (
    AgentDecisionRecord,
    ArtifactRef,
    MethodOutputConsumptionRecord,
    MethodPlan,
    OperationClass,
    SearchBlockerRecord,
)


def _ref(artifact_id: str, artifact_type: str = "Estimate") -> ArtifactRef:
    return ArtifactRef.from_payload(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        payload={"artifact_id": artifact_id, "artifact_type": artifact_type},
        schema_ref="policyos.gy.phase2.test.v1",
        uri=f"cas://{artifact_id}",
        version="v1",
    )


def test_phase2_search_blocker_contract_carries_frontier_and_repair_context() -> None:
    blocker = SearchBlockerRecord(
        blocker_id="blocker-bounds",
        workspace_id="ws-phase2",
        operation_class=OperationClass.REFINE,
        blocked_port="bounds.lower",
        missing_input="lower_bound",
        reason="Optional bounds cannot be coerced to zero.",
        frontier_snapshot_ref="frontier-phase2",
        applicability_result_ref="applicability-refine",
        repair_options=[
            {"operation_class": OperationClass.ACQUIRE.value, "reason": "Collect lower bound."}
        ],
        producer_missing_label="producer_missing",
    )

    assert blocker.blocked_port == "bounds.lower"
    assert blocker.producer_missing_label == "producer_missing"
    assert blocker.repair_options[0]["operation_class"] == "ACQUIRE"


def test_agent_decision_record_is_ring1_candidate_only() -> None:
    record = AgentDecisionRecord(
        decision_id="agent-decision-tool-loop",
        workspace_id="ws-phase2",
        invocation_id="invoke-agent",
        role="tool_loop",
        observed_refs=[_ref("observed-ref", "BaseDataset")],
        candidate_operations=[OperationClass.ESTIMATE],
        selected_proposal_ref="method-plan-1",
        tool_calls=["search_datasets"],
        candidate_only=True,
        status="completed",
        rationale="Agent proposed a method plan; verifier owns promotion.",
    )

    assert record.candidate_only is True
    assert record.role == "tool_loop"

    with pytest.raises(ValidationError, match="candidate-only"):
        AgentDecisionRecord(
            decision_id="agent-decision-bad",
            workspace_id="ws-phase2",
            invocation_id="invoke-agent",
            role="pi",
            observed_refs=[],
            candidate_operations=[OperationClass.VERIFY],
            selected_proposal_ref=None,
            tool_calls=[],
            candidate_only=False,
            status="completed",
            rationale="bad",
        )


def test_method_plan_never_carries_authority_state() -> None:
    plan = MethodPlan(
        plan_id="method-plan-1",
        workspace_id="ws-phase2",
        proposed_by_ref="agent-decision-tool-loop",
        operation_classes=[OperationClass.ESTIMATE, OperationClass.VERIFY],
        method_refs=["causal.inference.synthetic_control@1.0.0"],
        consumes=[{"port_id": "observational_data_ref"}],
        produces=[{"port_id": "causal_report_ref"}],
        authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
        admission_state="candidate_only",
    )

    assert plan.admission_state == "candidate_only"

    with pytest.raises(ValidationError, match="candidate"):
        MethodPlan(
            plan_id="method-plan-bad",
            workspace_id="ws-phase2",
            proposed_by_ref="agent-decision-tool-loop",
            operation_classes=[OperationClass.ESTIMATE],
            method_refs=[],
            consumes=[],
            produces=[],
            authority_transform={"kind": "preserves"},
            admission_state="authority",
        )


def test_method_output_consumption_requires_real_consumed_outputs() -> None:
    result_ref = _ref("method-result", "FoundryMethodResult")
    evidence_ref = _ref("method-evidence", "FoundryMethodEvidence")
    record = MethodOutputConsumptionRecord(
        consumption_id="consume-foundry-output",
        workspace_id="ws-phase2",
        operation_invocation_id="invoke-estimate",
        operation_class=OperationClass.ESTIMATE,
        consumed_method_output_refs=[result_ref],
        consumed_method_evidence_refs=[evidence_ref],
        dag_consumed_method_outputs_count=1,
        measurement_root_refs=[_ref("measurement-root", "MeasurementRoot")],
        constraint_store_ref="constraint-store-phase2",
    )

    assert record.dag_consumed_method_outputs_count == 1
    assert record.consumed_method_output_refs[0].artifact_type == "FoundryMethodResult"

    with pytest.raises(ValidationError, match="at least one"):
        MethodOutputConsumptionRecord(
            consumption_id="consume-empty",
            workspace_id="ws-phase2",
            operation_invocation_id="invoke-estimate",
            operation_class=OperationClass.ESTIMATE,
            consumed_method_output_refs=[],
            consumed_method_evidence_refs=[],
            dag_consumed_method_outputs_count=0,
            measurement_root_refs=[],
            constraint_store_ref=None,
        )
