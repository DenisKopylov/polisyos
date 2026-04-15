"""Tests for the Scientist starter eval harness."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.scientist.agent.eval_harness import (
    AgentEvalCaseResult,
    AgentEvalReport,
    AgentPolicyRolloutStatus,
    compare_agent_eval_reports,
    run_starter_eval_harness,
)


@pytest.mark.asyncio
async def test_starter_eval_harness_runs_local_proxy_suite(tmp_path):
    report = await run_starter_eval_harness(
        cas_root=tmp_path,
        include_live_provider=False,
    )

    assert report.summary["total_cases"] == 4
    assert report.summary["passed_cases"] == 4
    assert report.summary["release_gates"]["passed"] is True
    assert {case.suite for case in report.cases} == {
        "tool_calling",
        "search",
        "swarm",
        "reflexion",
    }


@pytest.mark.asyncio
async def test_starter_eval_harness_uses_injected_artifact_store_factory(tmp_path) -> None:
    seen_roots: list[str] = []

    def _factory(root):
        seen_roots.append(str(root))
        return build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(root))
        )

    report = await run_starter_eval_harness(
        cas_root=tmp_path,
        include_live_provider=False,
        artifact_store_factory=_factory,
    )

    assert report.summary["passed_cases"] == 4
    assert seen_roots == [
        str(tmp_path / "cas_search"),
        str(tmp_path / "cas_swarm"),
    ]


def test_agent_policy_comparison_requires_offline_validation_ref() -> None:
    baseline = AgentEvalReport(
        cases=[AgentEvalCaseResult(suite="reflexion", case_id="b", passed=True)],
        summary={
            "metrics": {
                "task_success_rate": 0.8,
                "citation_coverage": 0.8,
                "search_precision_proxy": 0.7,
                "invalid_tool_call_rate": 0.0,
                "reflexion_recovery_rate": 0.6,
            }
        },
    )
    candidate = AgentEvalReport(
        cases=[AgentEvalCaseResult(suite="tree_reasoning", case_id="c", passed=True)],
        summary={
            "metrics": {
                "task_success_rate": 1.0,
                "citation_coverage": 0.9,
                "search_precision_proxy": 0.8,
                "invalid_tool_call_rate": 0.0,
                "reflexion_recovery_rate": 0.8,
            }
        },
    )

    blocked = compare_agent_eval_reports(baseline, candidate)
    allowed = compare_agent_eval_reports(
        baseline,
        candidate,
        offline_validation_ref="sha256:" + "b" * 64,
    )

    assert blocked.default_enable_eligible is False
    assert blocked.rollout_status == AgentPolicyRolloutStatus.OFFLINE_GATED
    assert "missing_offline_validation_ref" in blocked.blockers
    assert allowed.default_enable_eligible is True
    assert allowed.rollout_status == AgentPolicyRolloutStatus.DEFAULT_ENABLE_ELIGIBLE
    assert allowed.deltas["task_success_rate"] > 0


def test_agent_policy_comparison_marks_failed_candidate_as_release_gated() -> None:
    baseline = AgentEvalReport(
        cases=[AgentEvalCaseResult(suite="reflexion", case_id="b", passed=True)],
        summary={
            "metrics": {
                "task_success_rate": 0.95,
                "citation_coverage": 0.9,
                "search_precision_proxy": 0.8,
                "invalid_tool_call_rate": 0.0,
                "reflexion_recovery_rate": 0.7,
            }
        },
    )
    candidate = AgentEvalReport(
        cases=[AgentEvalCaseResult(suite="tree_reasoning", case_id="c", passed=False)],
        summary={
            "metrics": {
                "task_success_rate": 0.7,
                "citation_coverage": 0.7,
                "search_precision_proxy": 0.5,
                "invalid_tool_call_rate": 0.1,
                "reflexion_recovery_rate": 0.4,
            }
        },
    )

    report = compare_agent_eval_reports(
        baseline,
        candidate,
        offline_validation_ref="sha256:" + "c" * 64,
    )

    assert report.default_enable_eligible is False
    assert report.rollout_status == AgentPolicyRolloutStatus.RELEASE_GATED
    assert report.release_gate_passed is False
    assert "task_success_rate" in report.blockers
