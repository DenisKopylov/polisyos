from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.pdc import AgentDecisionRecord, OperationClass
from polisyos.runtime.quality.workspace.agent_proposal_bridge import (
    AgentEventBridge,
    normalize_agent_voi_scores,
)
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
from polisyos.scientist.agent.tools.knowledge_tools_adapter import build_knowledge_tool_registry


class _DeterministicToolClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs):
        assert kwargs["tools"]
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                content="",
                usage=SimpleNamespace(total_tokens=11),
                tool_calls=[
                    SimpleNamespace(
                        id="tool-call-1",
                        name="search_datasets",
                        arguments={"query": "credit guarantees"},
                    )
                ],
            )
        return SimpleNamespace(
            content="candidate uses recorded dataset evidence",
            usage=SimpleNamespace(total_tokens=7),
            tool_calls=None,
        )


class _DeterministicToolkit:
    def search_datasets(self, query: str) -> dict[str, object]:
        """Return deterministic recorded dataset matches."""

        return {
            "query": query,
            "matches": [
                {
                    "dataset_id": "ua-production-calibration-observation-panel-monthly",
                    "source": "recorded_rows",
                }
            ],
        }


def test_knowledge_tool_registry_exposes_all_core_toolkit_tools() -> None:
    registry = build_knowledge_tool_registry(KnowledgeToolkit())

    assert len(registry.list_definitions()) == 20
    assert {definition.name for definition in registry.list_definitions()} >= {
        "search_datasets",
        "find_causal_evidence",
        "assemble_legal_candidate_pack",
        "recall",
    }


def test_agent_event_bridge_persists_tool_loop_as_ring1_candidate_event() -> None:
    bridge = AgentEventBridge()
    event = bridge.record_tool_loop(
        workspace_id="ws-phase2",
        invocation_id="invoke-agent",
        role="tool_loop",
        selected_proposal_ref="method-plan-1",
        tool_calls=["search_datasets"],
        candidate_operations=[OperationClass.ESTIMATE],
    )

    assert isinstance(event.decision_record, AgentDecisionRecord)
    assert event.decision_record.candidate_only is True
    assert event.method_plan.admission_state == "candidate_only"
    assert event.method_plan.proposed_by_ref == event.decision_record.decision_id
    assert event.ledger_event.decision_record_ref == event.decision_record.decision_id
    assert event.invocation.tool_calls == ["search_datasets"]


def test_agent_event_bridge_persists_ring1_event_bundle_to_cas(store) -> None:
    event = AgentEventBridge().record_tool_loop(
        workspace_id="ws-phase2",
        invocation_id="invoke-agent",
        role="tool_loop",
        selected_proposal_ref="method-plan-1",
        tool_calls=["search_datasets"],
        candidate_operations=[OperationClass.ESTIMATE],
    )

    refs = AgentEventBridge().persist_event_bundle(store=store, bundle=event)

    assert {ref.artifact_type for ref in refs} == {
        "AgentDecisionRecord",
        "OperationInvocationRecord",
        "SearchLedgerEvent",
        "MethodPlan",
    }


@pytest.mark.asyncio
async def test_agent_event_bridge_wires_existing_run_tool_loop(monkeypatch) -> None:
    called = {"run_tool_loop": False}

    async def _fake_run_tool_loop(**kwargs):
        called["run_tool_loop"] = True
        assert kwargs["client"] == object_client
        assert kwargs["max_iterations"] == 1
        return SimpleNamespace(tool_calls=[SimpleNamespace(name="search_datasets")])

    object_client = object()
    monkeypatch.setattr(
        "polisyos.scientist.agent.tools.tool_loop.run_tool_loop",
        _fake_run_tool_loop,
    )

    event = await AgentEventBridge().run_tool_loop_proposal(
        workspace_id="ws-phase2",
        invocation_id="invoke-agent",
        client=object_client,
        system="system",
        user="user",
        candidate_operations=[OperationClass.ESTIMATE],
        max_iterations=1,
    )

    assert called["run_tool_loop"] is True
    assert event.decision_record.candidate_only is True
    assert event.invocation.tool_calls == ["search_datasets"]


@pytest.mark.asyncio
async def test_agent_event_bridge_persists_unmocked_tool_loop_event_bundle(store) -> None:
    client = _DeterministicToolClient()

    event = await AgentEventBridge().run_tool_loop_proposal(
        workspace_id="ws-phase2",
        invocation_id="invoke-agent-unmocked",
        client=client,
        system="Use tools before proposing.",
        user="Find recorded datasets for credit guarantees.",
        toolkit=_DeterministicToolkit(),
        candidate_operations=[OperationClass.ESTIMATE],
        max_iterations=2,
    )

    assert client.calls == 2
    assert event.decision_record.candidate_only is True
    assert event.invocation.tool_calls == ["search_datasets"]
    refs = AgentEventBridge().persist_event_bundle(store=store, bundle=event)
    assert {ref.artifact_type for ref in refs} == {
        "AgentDecisionRecord",
        "OperationInvocationRecord",
        "SearchLedgerEvent",
        "MethodPlan",
    }


def test_agent_no_client_run_blocks_without_synthetic_audit() -> None:
    blocked = AgentEventBridge().no_client_blocker(
        workspace_id="ws-phase2",
        invocation_id="invoke-agent",
    )

    assert blocked.blocker.missing_input == "agent_client"
    assert blocked.synthetic_audit_created is False


def test_agent_ring2_write_is_rejected_by_contract() -> None:
    with pytest.raises(ValidationError, match="candidate-only"):
        AgentDecisionRecord(
            decision_id="agent-decision-bad",
            workspace_id="ws-phase2",
            invocation_id="invoke-agent",
            role="critic",
            observed_refs=[],
            candidate_operations=[OperationClass.VERIFY],
            selected_proposal_ref=None,
            tool_calls=[],
            candidate_only=False,
            status="completed",
            rationale="bad",
        )


def test_agent_voi_scores_are_clipped_or_rejected_before_gy_h_selection() -> None:
    audit = normalize_agent_voi_scores(
        workspace_id="ws-phase2",
        selected_terminal="search_ceiling_repair_required",
        agent_scores={
            "phase2.acquire": 1.7,
            "phase2.refine": -0.4,
            "phase2.nan": float("nan"),
            "phase2.unsupported": 0.8,
        },
        supported_action_refs={"phase2.acquire", "phase2.refine"},
    )

    assert audit.normalized_scores == {"phase2.acquire": 1.0, "phase2.refine": 0.0}
    assert {item["action_ref"] for item in audit.rejected_or_clipped_inputs} == {
        "phase2.acquire",
        "phase2.refine",
        "phase2.nan",
        "phase2.unsupported",
    }
