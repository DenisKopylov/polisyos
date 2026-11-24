"""Exercise the real drafter -> traced producer -> current-observation consumer."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.agent.drafter import LLMDrafterAgent, MultiPassConfig, MultiPassLLMDrafter
from polisyos.scientist.agent.drafter_models import _ConsolidationPayload, _CritiquePayload
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame
from polisyos.scientist.agent.workers import draft_from_payload
from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceValidationError,
)


class WireProvider:
    """Only the external wire is substituted; producer/parser/controller stay real."""

    model_name = "fixture-model"

    def __init__(self, responses, *, version="fixture-weights-1"):
        self.responses = responses
        self.version = version
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responses[len(self.calls) - 1]
        return SimpleNamespace(
            content=content,
            model_version=self.version,
            cost_usd=0.001,
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def _problem():
    return ProblemFrame(
        frame_id="c49-current-problem",
        domain="fixture",
        problem_statement="A portable policy question",
        actors=("public",),
        goals=("reduce harm",),
        constraints=(),
        success_criteria={},
        assumptions=(),
        created_at=datetime.now(UTC),
    )


def _draft(confidence=0.2):
    return json.dumps(
        {
            "draft_id": "c49-candidate",
            "problem_frame_ref": "c49-current-problem",
            "narrative": "Useful candidate",
            "interventions": [],
            "rationale": "Candidate rationale",
            "confidence": confidence,
        }
    )


def _agent(provider, **profile):
    return MultiPassLLMDrafter(
        LLMDrafterAgent(provider, model_name="fixture-model"),
        config=MultiPassConfig(
            max_passes=3,
            early_exit_confidence=1.0,
            enable_memory_logging=False,
            convergence=ConvergenceConfig(**profile),
        ),
    )


@pytest.mark.parametrize("second_version", ["fixture-weights-1", "fixture-weights-2"])
def test_configured_real_drafter_consumes_fresh_critique_on_one_model_basis(
    second_version: str,
) -> None:
    class VersionedWire(WireProvider):
        async def generate(self, **kwargs: Any) -> SimpleNamespace:
            response = await super().generate(**kwargs)
            if len(self.calls) == 2:
                response.model_version = second_version
            return response

    provider = VersionedWire([_draft(), '{"findings":[],"confidence_adjustment":0.001}'])
    events: list[dict[str, Any]] = []
    traced = TracedLLMClient(provider, model_name=provider.model_name, call_observer=events.append)
    drafter = MultiPassLLMDrafter(
        LLMDrafterAgent(traced),
        config=MultiPassConfig(
            max_passes=2,
            early_exit_confidence=1.0,
            enable_memory_logging=False,
            convergence=ConvergenceConfig(),
        ),
    )
    result = asyncio.run(drafter.draft_policy(_problem()))
    assert len(provider.calls) == len(events) == 2
    assert result.narrative == "Useful candidate"
    state = result.convergence_state
    assert state is not None
    same_basis = second_version == "fixture-weights-1"
    assert state.should_stop is same_basis
    assert state.stop_kind == ("heuristic_stability" if same_basis else "none")
    assert state.history == ([0.2, 0.201] if same_basis else [0.201])
    assert state.observation_status == "current_candidate_observation"
    assert not state.scientific_converged
    observation = state.last_checked_observation
    assert observation is not None and observation == result.confidence_observation
    selected = events[-1]["producer_event"]
    assert observation.producer_event_id == selected.event_id
    assert observation.producer_request_ref == selected.request_digest
    assert observation.source_ref == selected.response_digest
    assert observation.source_ref == hashlib.sha256(provider.responses[-1].encode()).hexdigest()
    assert observation.pass_number == 2 and observation.model_version == second_version
    assert observation.value_derivation == "candidate_after_checks"

    reopened = draft_from_payload(json.loads(TypeAdapter(DraftResult).dump_json(result)))
    assert reopened == result


def test_real_drafter_prompt_cache_reuse_preserves_bytes_without_admitting_a_fresh_pass() -> None:
    from polisyos.scientist.orchestration.llm.prompt_cache import (
        CachingLLMClient,
        InMemoryPromptCache,
    )
    from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient

    simulator = SimulatedGatewayLLMClient(model="fixture-simulated")
    cache = InMemoryPromptCache()
    events: list[dict[str, Any]] = []
    traced = TracedLLMClient(
        CachingLLMClient(simulator, cache=cache, model=simulator.model),
        model_name=simulator.model,
        call_observer=events.append,
    )
    drafter = MultiPassLLMDrafter(
        LLMDrafterAgent(traced),
        config=MultiPassConfig(
            max_passes=1,
            enable_memory_logging=False,
            constitution_enabled=False,
            convergence=ConvergenceConfig(),
        ),
    )
    problem = _problem()

    async def draft_twice() -> tuple[DraftResult, DraftResult]:
        return await drafter.draft_policy(problem), await drafter.draft_policy(problem)

    first, second = asyncio.run(draft_twice())
    assert len(simulator.calls) == cache.size == 1
    [provider_event, reuse_event] = [row["producer_event"] for row in events]
    assert provider_event.kind == "provider" and reuse_event.kind == "reuse"
    assert reuse_event.origin_event_id == provider_event.event_id
    assert second.raw_llm_response == first.raw_llm_response
    assert second.narrative and second.narrative == first.narrative
    assert second.confidence_observation is not None
    assert second.confidence_observation.producer_event_id == reuse_event.event_id
    assert second.confidence_observation.producer_kind == "reuse"
    state = second.convergence_state
    assert state is not None
    assert state.observation_status == "reused_response_is_not_a_fresh_observation"
    assert state.history == [] and state.last_checked_observation is None
    assert state.stop_kind == "none" and not state.scientific_converged

    reopened = draft_from_payload(json.loads(TypeAdapter(DraftResult).dump_json(second)))
    assert reopened == second


@pytest.mark.parametrize(
    "second", ["not JSON", '{"findings":[]}', '{"findings":[],"confidence_adjustment":true}']
)
def test_parse_failure_missing_or_malformed_assessment_does_not_reuse_prior_scalar(second):
    provider = WireProvider([_draft(), second, '{"findings":[],"confidence_adjustment":0.001}'])
    result = asyncio.run(_agent(provider).draft_policy(_problem()))
    assert len(provider.calls) == 3
    assert not result.convergence_state.should_stop
    assert result.convergence_state.last_checked_observation.pass_number in {1, 3}


def test_absent_provider_version_keeps_candidate_without_claiming_stability():
    provider = WireProvider(
        [
            _draft(),
            '{"findings":[],"confidence_adjustment":0.001}',
            '{"findings":[],"confidence_adjustment":0.001}',
        ],
        version=None,
    )
    result = asyncio.run(_agent(provider).draft_policy(_problem()))
    assert len(provider.calls) == 3 and result.narrative == "Useful candidate"
    assert result.convergence_state.observation_status == "model_version_not_established"
    assert not result.convergence_state.should_stop


def test_real_drafter_resource_cap_is_not_heuristic_or_scientific_convergence():
    provider = WireProvider([_draft()], version=None)
    result = asyncio.run(
        _agent(provider, min_iterations=1, max_iterations=1).draft_policy(_problem())
    )
    assert len(provider.calls) == 1
    assert result.convergence_state.should_stop
    assert result.convergence_state.stop_kind == "resource_limit"
    assert result.convergence_state.reason == "max_iterations"
    assert not result.convergence_state.scientific_converged


def test_invalid_configured_budget_profile_is_typed_refusal_before_any_fallback_call():
    provider = WireProvider([_draft()])
    with pytest.raises(ConvergenceValidationError):
        asyncio.run(_agent(provider, budget_key="run").draft_policy(_problem()))
    assert provider.calls == []


@pytest.mark.parametrize("value", [True, "0.1", float("nan"), float("inf"), 2.0])
def test_parser_profiles_reject_non_numeric_or_nonfinite_assessments(value):
    with pytest.raises(ValidationError):
        _CritiquePayload.model_validate({"findings": [], "confidence_adjustment": value})
    with pytest.raises(ValidationError):
        _ConsolidationPayload.model_validate({"confidence": value})
