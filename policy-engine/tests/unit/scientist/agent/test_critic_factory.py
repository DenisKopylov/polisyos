from __future__ import annotations

import json

import pytest

from polisyos.scientist.agent.critic import (
    LLMCriticAgent,
    MockCriticAgent,
    create_critic_agent,
    create_mock_problem_frame,
)
from polisyos.scientist.agent.formalizer import MockFormalizerAgent, create_mock_draft
from polisyos.scientist.agent.informed_critic import InformedCriticAgent
from polisyos.scientist.agent.protocols import CritiqueSeverity
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage


class StubLLM:
    async def generate(self, **kwargs):
        del kwargs
        return type("Resp", (), {"content": "{}"})()


class JSONLLM:
    def __init__(self, payload: dict[str, object] | str) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=(self.payload if isinstance(self.payload, str) else json.dumps(self.payload)),
            usage=GatewayUsage(),
            raw={},
        )


class FailingLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        raise RuntimeError("provider unavailable")


def test_create_critic_agent_returns_base_llm_critic_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, LLMCriticAgent)


def test_create_critic_agent_wraps_informed_critic_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, InformedCriticAgent)


def test_create_critic_agent_honors_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")
    monkeypatch.setenv("POLISYOS_CRITIC_MODE", "mock")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, MockCriticAgent)


@pytest.mark.asyncio
async def test_llm_critic_suppresses_stale_schema_blockers_from_valid_bundle() -> None:
    draft = create_mock_draft(
        interventions=[
            {
                "intervention_id": "adaptive_support",
                "kind": "adaptive_agent",
                "params": {
                    "observation_space": ["agents.income", "agents.skill_level"],
                    "action_space": {
                        "type": "continuous",
                        "affects": ["agents.income"],
                    },
                    "utility": "maximize_survival_and_fairness",
                    "learning_rate": "0.05",
                    "stochastic": True,
                },
            }
        ]
    )
    bundle = await MockFormalizerAgent().formalize(draft)
    llm = JSONLLM(
        {
            "verdict": "REJECT",
            "issues": [
                {
                    "issue_id": "stale_problem_frame_ref",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Missing required policy_spec.problem_frame_ref",
                    "location": "policy_spec.problem_frame_ref",
                },
                {
                    "issue_id": "stale_adaptive_agent",
                    "category": "COMPLIANCE",
                    "severity": "BLOCKER",
                    "message": "adaptive_agent is unsupported by the runtime",
                    "location": "policy_spec.interventions[0].kind",
                },
                {
                    "issue_id": "stale_weight",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Objective weight must be numeric, not a string",
                    "location": "problem_frame.objectives[0].weight",
                },
                {
                    "issue_id": "stale_target",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Objective target cannot be null",
                    "location": "problem_frame.objectives[0].target",
                },
                {
                    "issue_id": "stale_success_criteria",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "success_criteria is an empty array and must be omitted",
                    "location": "problem_frame.success_criteria",
                },
                {
                    "issue_id": "stale_boundary_assumption",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "assumption_type boundary is invalid; allowed values are structural",
                    "location": "model_spec.assumptions[2].assumption_type",
                },
                {
                    "issue_id": "stale_tax_subsidy_semantics",
                    "category": "COMPLIANCE",
                    "severity": "BLOCKER",
                    "message": (
                        "Multiple interventions use tax_subsidy for non-tax "
                        "instruments; use direct_transfer."
                    ),
                    "location": "policy_spec.interventions[1].kind",
                },
                {
                    "issue_id": "high_rate",
                    "category": "FEASIBILITY",
                    "severity": "WARNING",
                    "message": "Subsidy rate may be fiscally aggressive",
                    "location": "policy_spec.interventions[0].params.rate",
                },
            ],
            "alignment_score": 0.82,
            "completeness_score": 0.85,
            "overall_quality": 0.8,
            "reflexion_hint": "Fix schema blockers first.",
        }
    )

    report = await LLMCriticAgent(llm).critique(bundle, create_mock_problem_frame())

    assert report.verdict == "APPROVE"
    assert report.metadata["suppressed_stale_contract_issue_count"] == 7
    assert [issue.issue_id for issue in report.issues] == ["high_rate"]
    assert not any(issue.severity == CritiqueSeverity.BLOCKER for issue in report.issues)


@pytest.mark.asyncio
async def test_llm_critic_falls_back_when_gateway_fails(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_CRITIC_LLM_TIMEOUT_S", "1")
    draft = create_mock_draft()
    bundle = await MockFormalizerAgent().formalize(draft)
    llm = FailingLLM()

    report = await LLMCriticAgent(llm).critique(bundle, create_mock_problem_frame())

    assert llm.calls
    assert llm.calls[0]["timeout"] == 1.0
    assert report.report_id.startswith("critique_")
    assert report.problem_frame_ref
    assert report.metadata["generator_path"] == "degraded_mock_fallback"
    assert report.metadata["degraded_reason"] == "llm_call_failed"


@pytest.mark.asyncio
async def test_llm_critic_parses_think_prefixed_json() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())
    raw = "<think>critic reasoning</think>" + json.dumps(
        {
            "report_id": "critique_think_prefixed",
            "verdict": "APPROVE",
            "issues": [],
            "alignment_score": 0.9,
            "completeness_score": 0.8,
            "overall_quality": 0.85,
        }
    )

    report = await LLMCriticAgent(JSONLLM(raw)).critique(
        bundle,
        create_mock_problem_frame(),
    )

    assert report.report_id == "critique_think_prefixed"
    assert report.verdict == "APPROVE"
    assert report.metadata["generator_path"] == "model_generated"
    assert report.metadata["raw_llm_response"] == raw


@pytest.mark.asyncio
async def test_llm_critic_invalid_json_returns_conservative_parse_error() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())

    report = await LLMCriticAgent(JSONLLM("no object exists")).critique(
        bundle,
        create_mock_problem_frame(),
    )

    assert report.verdict == "NEEDS_REVISION"
    assert [issue.issue_id for issue in report.issues] == ["parse_error"]
    assert report.metadata["generator_path"] == "degraded_mock_fallback"
    assert report.metadata["degraded_reason"] == "llm_parse_failed"
    assert report.metadata["raw_llm_response"] == "no object exists"


@pytest.mark.asyncio
async def test_explicit_mock_critic_is_stamped_non_promotable() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())

    report = await MockCriticAgent().critique(bundle, create_mock_problem_frame())

    assert report.metadata["generator_path"] == "degraded_mock_fallback"
