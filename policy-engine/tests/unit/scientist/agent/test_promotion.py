from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.promotion import (
    AgentPromotionCoverageDomain,
    build_agent_capability_promotion_report,
    project_agent_promotion_to_frontier_statuses,
)
from polisyos.scientist.agent.reasoning import ReasoningPolicyGate
from polisyos.scientist.agent.runtime_capabilities import AgentCapabilityId
from polisyos.scientist.agent.supervisor_eval import SupervisorEvalMetrics
from polisyos.scientist.agent.tool_contracts import summarize_tool_contracts
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.orchestration.engine.frontier_runtime import (
    FrontierCapabilityStatus,
    summarize_agent_promotion_frontier_status,
)


def _ref(hex_char: str, kind: str = "scientist.agent.eval") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{hex_char * 64}",
        kind=kind,
        media_type="application/json",
    )


def _strict_tool_summary():
    return summarize_tool_contracts(
        [
            ToolDefinition(
                name="safe_search",
                description="Search safe sources",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                timeout_s=10.0,
                response_max_chars=4096,
            )
        ]
    )


def test_agent_promotion_report_covers_all_known_capabilities_once() -> None:
    report = build_agent_capability_promotion_report()

    assert [item.capability_id for item in report.capabilities] == list(AgentCapabilityId)
    assert len(report.capabilities) == len(AgentCapabilityId)
    assert set(report.coverage_domains) == set(AgentPromotionCoverageDomain)
    assert [item.domain for item in report.coverage] == list(AgentPromotionCoverageDomain)
    assert all(isinstance(item.status, FrontierCapabilityStatus) for item in report.capabilities)
    assert report.default_enable_eligible is False


def test_default_enable_requested_without_benchmark_pack_returns_blocker() -> None:
    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=_ref("a"),
        tool_contract_summary=_strict_tool_summary(),
    )

    assert report.default_enable_eligible is False
    assert "missing_benchmark_pack_ref" in report.blockers


def test_tool_loop_can_become_available_offline_with_valid_evidence() -> None:
    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
        tool_contract_summary=_strict_tool_summary(),
    )

    tool_loop = next(
        item for item in report.capabilities if item.capability_id == AgentCapabilityId.TOOL_LOOP
    )

    assert tool_loop.status == FrontierCapabilityStatus.AVAILABLE_OFFLINE
    assert tool_loop.default_enable_eligible is True
    assert report.default_enable_eligible is True
    assert summarize_agent_promotion_frontier_status(report) == (
        FrontierCapabilityStatus.AVAILABLE_OFFLINE
    )


def test_agent_promotion_report_marks_context_and_provider_coverage_missing() -> None:
    report = build_agent_capability_promotion_report(
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
    )

    context = next(
        item
        for item in report.coverage
        if item.domain == AgentPromotionCoverageDomain.CONTEXT_MEMORY
    )
    provider = next(
        item
        for item in report.coverage
        if item.domain == AgentPromotionCoverageDomain.PROVIDER_BEHAVIOR
    )

    assert context.status == FrontierCapabilityStatus.OFFLINE_GATED
    assert "missing_context_memory_eval_ref" in context.blockers
    assert provider.status == FrontierCapabilityStatus.OFFLINE_GATED
    assert "missing_provider_behavior_eval_ref" in provider.blockers


def test_invalid_tool_schema_cannot_become_default_eligible() -> None:
    unsafe_summary = summarize_tool_contracts(
        [
            ToolDefinition(
                name="open_tool",
                description="Unsafe open schema",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "additionalProperties": True,
                },
                response_max_chars=None,
            )
        ]
    )

    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
        tool_contract_summary=unsafe_summary,
    )

    tool_loop = next(
        item for item in report.capabilities if item.capability_id == AgentCapabilityId.TOOL_LOOP
    )
    assert tool_loop.default_enable_eligible is False
    assert "tool_schema_not_ready" in report.blockers


def test_supervisor_worker_cannot_become_eligible_without_handoff_eval() -> None:
    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.SUPERVISOR_WORKER],
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
        supervisor_eval=SupervisorEvalMetrics(
            case_count=5,
            delegation_success_rate=1.0,
            quorum_consistency_rate=0.95,
            citation_coverage=0.9,
            budget_violation_rate=0.0,
        ),
    )

    assert report.default_enable_eligible is False
    assert "missing_supervisor_handoff_eval_ref" in report.blockers


def test_deep_research_cannot_become_eligible_without_citation_faithfulness_eval() -> None:
    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.DEEP_RESEARCH_SUBGRAPH],
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
        deep_research_eval_ref=_ref("c", "scientist.deep_research_eval"),
    )

    assert report.default_enable_eligible is False
    assert "missing_citation_faithfulness_eval_ref" in report.blockers


def test_reasoning_status_uses_existing_gate_and_comparative_report() -> None:
    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TREE_OF_THOUGHT],
        offline_validation_ref=_ref("a"),
        benchmark_pack_ref=_ref("b", "scientist.benchmark_pack"),
        reasoning_gate=ReasoningPolicyGate(
            enabled=True, offline_validation_ref=f"sha256:{'c' * 64}"
        ),
        agent_policy_report=SimpleNamespace(
            offline_validation_ref=f"sha256:{'c' * 64}",
            release_gate_passed=True,
            rollout_status="default_enable_eligible",
            passed=True,
            default_enable_eligible=True,
            blockers=[],
        ),
    )

    statuses = project_agent_promotion_to_frontier_statuses(report)

    assert statuses["tree_of_thought"] == FrontierCapabilityStatus.AVAILABLE_OFFLINE
    assert report.default_enable_eligible is True
