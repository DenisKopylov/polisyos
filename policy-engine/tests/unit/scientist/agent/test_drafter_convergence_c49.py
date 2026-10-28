"""Exercise the real drafter -> traced producer -> current-observation consumer."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.scientist.agent.drafter import LLMDrafterAgent, MultiPassConfig, MultiPassLLMDrafter
from polisyos.scientist.agent.drafter_models import _ConsolidationPayload, _CritiquePayload
from polisyos.scientist.agent.protocols import ProblemFrame
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


def test_configured_real_drafter_consumes_fresh_critique_and_stops_as_candidate():
    provider = WireProvider([_draft(), '{"findings":[],"confidence_adjustment":0.001}'])
    result = asyncio.run(_agent(provider).draft_policy(_problem()))
    assert len(provider.calls) == 2
    assert result.narrative == "Useful candidate"
    state = result.convergence_state
    assert state.should_stop and state.stop_kind == "heuristic_stability"
    assert state.observation_status == "current_candidate_observation"
    assert not state.scientific_converged
    assert (
        state.last_checked_observation.producer_event_id
        == result.confidence_observation.producer_event_id
    )
    assert state.last_checked_observation.pass_number == 2
    assert state.last_checked_observation.value_derivation == "candidate_after_checks"


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
