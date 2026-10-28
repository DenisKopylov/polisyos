"""Configured capture is one intake; unknown identity never becomes a fallback call."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from pydantic import TypeAdapter

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.agent._drafter_observations import confidence_request_ref
from polisyos.scientist.agent.drafter import LLMDrafterAgent, MultiPassConfig, MultiPassLLMDrafter
from polisyos.scientist.agent.drafter_factory import create_drafter_agent
from polisyos.scientist.agent.protocols import DraftResult
from polisyos.scientist.orchestration.engine.convergence import ConvergenceConfig
from tests.unit.scientist.agent.test_drafter_convergence_c49 import (
    WireProvider,
    _agent,
    _draft,
    _problem,
)


def test_existing_default_factory_does_not_emit_unrequested_observation_ids():
    provider = WireProvider([_draft()])
    agent = create_drafter_agent(
        provider,
        model_name="fixture-model",
        multipass_mode="active",
        config=MultiPassConfig(max_passes=1),
    )
    result = asyncio.run(agent.draft_policy(_problem()))
    assert len(provider.calls) == 1
    assert result.confidence == 0.2
    assert result.confidence_status == "not_established"
    assert result.confidence_observation is None and result.convergence_state is None
    projected = TypeAdapter(DraftResult).dump_python(result, mode="json")
    assert "confidence_observation" not in projected
    assert "confidence_request_ref" not in projected
    assert "confidence_status" not in projected
    assert "convergence_state" not in projected


def test_configured_wrapper_uses_same_core_owner_and_names_both_request_identities():
    events = []
    provider = WireProvider([_draft(), '{"findings":[],"confidence_adjustment":0.001}'])
    traced = TracedLLMClient(provider, model_name="fixture-model", call_observer=events.append)
    inner = LLMDrafterAgent(traced)
    agent = MultiPassLLMDrafter(
        inner,
        config=MultiPassConfig(
            max_passes=3,
            early_exit_confidence=1.0,
            enable_memory_logging=False,
            convergence=ConvergenceConfig(),
        ),
    )
    result = asyncio.run(agent.draft_policy(_problem()))
    observation = result.convergence_state.last_checked_observation
    assert len(provider.calls) == 2
    selected = [item for item in events if item.get("event_id") == observation.producer_event_id]
    assert len(selected) == 1
    assert observation.producer_request_ref == selected[0]["producer_event"].request_digest
    assert observation.source_ref == selected[0]["producer_event"].response_digest
    actual = provider.calls[-1]
    assert observation.request_ref == confidence_request_ref(
        system=actual["system"],
        user=actual["user"],
    )
    # The original reusable inner retains its default; a configured wrapper did
    # not change another caller's profile or create another traced client owner.
    assert inner._capture_convergence_observations is False
    assert agent._inner._llm is traced


def test_unserializable_semantic_identity_keeps_candidate_and_never_calls_fallback():
    provider = WireProvider([_draft()])
    problem = replace(_problem(), success_criteria={"unestablished": float("nan")})
    try:
        result = asyncio.run(
            _agent(
                provider,
                min_iterations=1,
                max_iterations=1,
            ).draft_policy(problem)
        )
    finally:
        assert len(provider.calls) == 1, "unknown observation identity triggered a fallback call"
    assert result.narrative == "Useful candidate"
    assert result.confidence_observation is None
    assert "candidate_convergence_subject_not_established" in result.grounding_notes
    assert result.convergence_state.observation_status == "semantic_subject_not_established"
    assert result.convergence_state.stop_kind == "resource_limit"
    assert not result.convergence_state.scientific_converged


def test_configured_invalid_confidence_is_explicit_unknown_without_mock_substitution():
    provider = WireProvider([_draft("not-a-number")])
    result = asyncio.run(
        _agent(
            provider,
            min_iterations=1,
            max_iterations=1,
        ).draft_policy(_problem())
    )
    assert len(provider.calls) == 1
    assert result.narrative == "Useful candidate"
    assert result.confidence_status == "not_established"
    assert result.confidence_observation is None
    assert result.convergence_state.stop_kind == "resource_limit"
    assert not result.convergence_state.scientific_converged


def test_actual_sanitized_restoration_retains_grade_with_named_unestablished_relation():
    import json
    import re
    from types import SimpleNamespace

    from polisyos.core.llm.sanitization import PromptSanitizer

    class RestoringWire:
        def __init__(self):
            self.calls = []
            self.produced = ""

        async def generate(self, **kwargs):
            self.calls.append(kwargs)
            placeholder = re.search(r"\[POLISYOS_SECRET_EMAIL_[a-f0-9]+\]", kwargs["user"])
            assert placeholder is not None
            payload = json.loads(_draft())
            payload["narrative"] = "Contact " + placeholder.group(0)
            self.produced = json.dumps(payload)
            return SimpleNamespace(
                content=self.produced,
                model_version="fixture-weights-1",
                cost_usd=0.001,
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    provider = RestoringWire()
    events = []
    traced = TracedLLMClient(
        provider,
        model_name="fixture-model",
        prompt_sanitizer=PromptSanitizer(),
        call_observer=events.append,
    )
    problem = replace(_problem(), problem_statement="Contact fixture.user@example.org")
    agent = MultiPassLLMDrafter(
        LLMDrafterAgent(traced),
        config=MultiPassConfig(
            max_passes=3,
            convergence=ConvergenceConfig(min_iterations=1, max_iterations=1),
            enable_memory_logging=False,
        ),
    )
    result = asyncio.run(agent.draft_policy(problem))
    view = result.convergence_state.last_checked_observation
    import hashlib

    assert len(provider.calls) == 1
    assert result.narrative == "Contact fixture.user@example.org"
    assert view.value == result.confidence
    assert view.producer_request_ref == events[0]["producer_event"].request_digest
    assert view.producer_response_ref == hashlib.sha256(provider.produced.encode()).hexdigest()
    assert view.source_ref == hashlib.sha256(result.raw_llm_response.encode()).hexdigest()
    assert view.response_binding_status == "not_established"
    assert view.producer_response_ref != view.source_ref
    assert (
        result.convergence_state.observation_status
        == "producer_consumer_response_relation_not_established"
    )
    assert result.convergence_state.stop_kind == "resource_limit"
    assert not result.convergence_state.scientific_converged


def test_actual_drafter_budget_pressure_without_admitted_signal_keeps_final_reason_and_metric():
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

    class Span:
        def __init__(self, owner):
            self.owner = owner

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def set_attribute(self, name, value):
            self.owner.attributes[name] = value

        def set_status(self, value):
            pass

        def record_exception(self, error):
            pass

    class Trace:
        def __init__(self):
            self.attributes = {}

        def start_as_current_span(self, *args, **kwargs):
            return Span(self)

    class Metrics:
        def __init__(self):
            self.runs = []

        def record_drafter_multipass_run(self, **kwargs):
            self.runs.append(kwargs)

        def record_drafter_multipass_pass(self, **kwargs):
            pass

    for spent, pressured in (("0.96", True), ("0.20", False)):
        provider = WireProvider([_draft()], version=None)
        trace, metrics = Trace(), Metrics()
        state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
            spent={"run": Decimal(spent)},
        )
        agent = MultiPassLLMDrafter(
            LLMDrafterAgent(provider),
            config=MultiPassConfig(
                max_passes=1,
                constitution_enabled=False,
                enable_memory_logging=False,
                convergence=ConvergenceConfig(budget_key="run"),
            ),
            convergence_budget_state=state,
            tracer=trace,
            metrics=metrics,
        )
        result = asyncio.run(agent.draft_policy(_problem()))
        assert len(provider.calls) == 1 and result.narrative == "Useful candidate"
        assert result.convergence_state.observation_status == "model_version_not_established"
        assert not result.convergence_state.scientific_converged
        assert metrics.runs[-1]["budget_stop"] is pressured
        if pressured:
            assert result.convergence_state.stop_kind == "resource_limit"
            assert result.convergence_state.reason == "budget_pressure"
            assert (
                trace.attributes["polisyos.drafter.stop_reason"] == "resource_limit:budget_pressure"
            )
        else:
            assert not result.convergence_state.should_stop
            assert result.convergence_state.stop_kind == "none"


def test_restored_response_layers_cannot_form_an_admitted_stability_window():
    import json
    import re
    from types import SimpleNamespace

    from polisyos.core.llm.sanitization import PromptSanitizer

    class RestoringWire:
        def __init__(self):
            self.calls = []

        async def generate(self, **kwargs):
            self.calls.append(kwargs)
            placeholder = re.search(
                r"\[POLISYOS_SECRET_EMAIL_[a-f0-9]+\]",
                str(kwargs.get("system", "")) + str(kwargs.get("user", "")),
            )
            assert placeholder is not None
            if "Generate a draft JSON object" in kwargs["user"]:
                payload = json.loads(_draft())
                payload["narrative"] = "Contact " + placeholder.group(0)
            else:
                payload = {
                    "findings": [],
                    "confidence_adjustment": 0.001,
                    "note": placeholder.group(0),
                }
            return SimpleNamespace(
                content=json.dumps(payload),
                model_version="fixture-weights-1",
                cost_usd=0.001,
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    provider = RestoringWire()
    traced = TracedLLMClient(
        provider, model_name="fixture-model", prompt_sanitizer=PromptSanitizer()
    )
    problem = replace(_problem(), problem_statement="Contact fixture.user@example.org")
    result = asyncio.run(
        MultiPassLLMDrafter(
            LLMDrafterAgent(traced),
            config=MultiPassConfig(
                max_passes=2,
                early_exit_confidence=1.0,
                enable_memory_logging=False,
                convergence=ConvergenceConfig(),
            ),
        ).draft_policy(problem)
    )
    assert len(provider.calls) == 2
    assert result.narrative == "Contact fixture.user@example.org"
    assert not result.convergence_state.should_stop
    assert (
        result.convergence_state.observation_status
        == "producer_consumer_response_relation_not_established"
    )
    assert not result.convergence_state.scientific_converged
