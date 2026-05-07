from __future__ import annotations

from polisyos.scientist.agent.promotion import build_agent_capability_promotion_report
from polisyos.scientist.agent.runtime_capabilities import AgentCapabilityId
from polisyos.scientist.agent.tool_contracts import summarize_tool_contracts
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.orchestration.engine.frontier_runtime import (
    FrontierRuntimeConfig,
    build_frontier_runtime_report,
)
from polisyos.scientist.evals.authority import BenchmarkAuthority, PromotionEvidenceRequest
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry

from .test_authority import _ref


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


def test_agent_promotion_can_require_benchmark_authority_verdict(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
    blocked_verdict = BenchmarkAuthority(registry).verdict(
        PromotionEvidenceRequest(
            family="policy_design",
            claim_mode="estimation",
            loop_id="loop-a",
        )
    )

    report = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=_ref("offline", kind="scientist.agent.offline_validation"),
        benchmark_pack_ref=_ref("pack", kind="scientist.benchmark_pack"),
        tool_contract_summary=_strict_tool_summary(),
        benchmark_authority_verdict=blocked_verdict,
        require_benchmark_authority=True,
    )

    assert report.default_enable_eligible is False
    assert "benchmark_authority_not_allowed" in report.blockers
    assert "benchmark_authority" in report.metadata


def test_frontier_runtime_can_require_benchmark_authority_for_default_enable() -> None:
    report = build_frontier_runtime_report(
        FrontierRuntimeConfig(
            enable_proximal_causal=True,
            offline_validation_ref="sha256:" + "a" * 64,
            benchmark_pack_ref="sha256:" + "b" * 64,
            default_enable_requested=True,
            allow_baseline_replacement=True,
            require_benchmark_authority=True,
            benchmark_authority_default_enable_allowed=False,
        )
    )

    assert report.default_enable_eligible is False
    assert "benchmark_authority_not_allowed" in report.default_enable_blockers
