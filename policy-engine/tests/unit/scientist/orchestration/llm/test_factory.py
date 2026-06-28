"""Tests for gateway client factory wiring."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

import polisyos.core.llm.traced_client as traced_client_module
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.agent.critic import LLMCriticAgent
from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
from polisyos.scientist.agent.formalizer import LLMFormalizerAgent
from polisyos.scientist.agent.pi import LLMPIAgent
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.fallback_router import FallbackRouter
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient


class _FakeSpan:
    def set_attribute(self, _name: str, _value: object) -> None:
        return None

    def set_status(self, _status: object) -> None:
        return None

    def record_exception(self, _exc: BaseException) -> None:
        return None


class _FakeTracer:
    @contextmanager
    def start_as_current_span(self, _name: str, *, attributes=None, kind=None):
        _ = attributes, kind
        yield _FakeSpan()


class _FakeMetrics:
    def record_llm_call(self, **_kwargs) -> None:
        return None


@pytest.fixture
def real_gateway_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)


def test_create_traced_gateway_client_uses_plain_gateway_without_fallback_urls(
    real_gateway_mode,
):
    client = create_traced_gateway_client(
        model_name="m",
        config=GatewayLLMConfig(
            base_url="https://api.gonkagate.com/v1",
            api_key="k",
            fallback_urls=(),
        ),
    )

    assert isinstance(client, TracedLLMClient)
    assert isinstance(client.unwrap(), GatewayLLMClient)
    assert client.unwrap().base_url == "https://api.gonkagate.com/v1"


def test_create_traced_gateway_client_applies_preset_plugins_and_first_party_sanitizer(
    real_gateway_mode,
):
    client = create_traced_gateway_client(
        model_name="m",
        config=GatewayLLMConfig(
            base_url="https://api.gonkagate.com/v1",
            api_key="k",
            fallback_urls=(),
            default_preset="agent-stable",
            enable_privacy_sanitization_plugin=True,
            enable_prompt_sanitizer=True,
        ),
    )

    assert isinstance(client, TracedLLMClient)
    raw_client = client.unwrap()
    assert isinstance(raw_client, GatewayLLMClient)
    assert raw_client.preset == "agent-stable"
    assert raw_client.default_plugins == [{"id": "privacy-sanitization"}]
    assert client._prompt_sanitizer is not None


def test_create_traced_gateway_client_wires_fallback_router_when_urls_present(
    real_gateway_mode,
):
    client = create_traced_gateway_client(
        model_name="m",
        provider_hint="gonka",
        config=GatewayLLMConfig(
            base_url="https://primary.example/v1",
            api_key="k",
            fallback_urls=("https://secondary.example/v1",),
            timeout_s=12.0,
            max_retries=2,
        ),
    )

    assert isinstance(client, TracedLLMClient)
    router = client.unwrap()
    assert isinstance(router, FallbackRouter)
    health = router.endpoint_health()
    assert [item["url"] for item in health] == [
        "https://primary.example/v1",
        "https://secondary.example/v1",
    ]


def test_create_traced_gateway_client_accepts_injected_observability(
    monkeypatch,
    real_gateway_mode,
):
    def _fail_get_tracer():
        raise AssertionError("global tracer lookup should not run when tracer is injected")

    def _fail_get_metrics():
        raise AssertionError("global metrics lookup should not run when metrics are injected")

    monkeypatch.setattr(traced_client_module, "get_tracer", _fail_get_tracer)
    monkeypatch.setattr(traced_client_module, "get_metrics", _fail_get_metrics)

    tracer = _FakeTracer()
    metrics = _FakeMetrics()
    client = create_traced_gateway_client(
        model_name="m",
        config=GatewayLLMConfig(
            base_url="https://api.gonkagate.com/v1",
            api_key="k",
            fallback_urls=(),
        ),
        tracer=tracer,
        metrics=metrics,
    )

    assert isinstance(client, TracedLLMClient)
    assert client._tracer is tracer
    assert client._metrics is metrics


def test_gateway_config_from_env_requires_api_key(monkeypatch, real_gateway_mode):
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "https://api.gonkagate.com/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "")

    assert GatewayLLMConfig.from_env() is None
    assert create_traced_gateway_client(model_name="m") is None


def test_gateway_config_from_env_rejects_malformed_proxy_key(monkeypatch, real_gateway_mode):
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "https://proxy.gonka.gg/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "not-a-proxy-key")

    assert GatewayLLMConfig.from_env() is None
    assert create_traced_gateway_client(model_name="m") is None


def test_create_traced_gateway_client_can_use_simulated_llm_mode(monkeypatch):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")

    client = create_traced_gateway_client(
        model_name="sim-model",
        tracer=_FakeTracer(),
        metrics=_FakeMetrics(),
    )

    assert isinstance(client, TracedLLMClient)
    raw_client = client.unwrap()
    assert isinstance(raw_client, SimulatedGatewayLLMClient)
    assert raw_client.model == "sim-model"


@pytest.mark.asyncio
async def test_simulated_gateway_exposes_deterministic_model_catalog() -> None:
    client = SimulatedGatewayLLMClient(
        model="simulated-qwen",
        supported_model_ids=["simulated-qwen"],
    )

    assert await client.list_model_ids() == ["simulated-qwen"]


@pytest.mark.asyncio
async def test_simulated_factory_injects_selected_model_into_preflight_catalog(monkeypatch):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    client = create_traced_gateway_client(
        model_name="simulated-qwen",
        tracer=_FakeTracer(),
        metrics=_FakeMetrics(),
    )
    assert client is not None

    assert "simulated-qwen" in await client.list_model_ids()


@pytest.mark.asyncio
async def test_simulated_llm_mode_exercises_agent_json_contracts(monkeypatch):
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    call_events = []
    client = create_traced_gateway_client(
        model_name="simulated-qwen",
        run_id="R_simulated",
        model_variant_id="simulated_qwen_0",
        call_observer=call_events.append,
        tracer=_FakeTracer(),
        metrics=_FakeMetrics(),
    )
    assert client is not None

    pi = LLMPIAgent(llm_client=client, model_name="simulated-qwen")
    problem_frame = await pi.create_problem_frame(
        "Розроби політику підтримки малого та середнього бізнесу України.",
        domain_hint="Ukraine wartime MSME support policy",
    )
    draft = await LLMDrafterAgent(llm_client=client, model_name="simulated-qwen").draft_policy(
        problem_frame,
    )
    bundle = await LLMFormalizerAgent(
        llm_client=client,
        model_name="simulated-qwen",
    ).formalize(draft)
    critique = await LLMCriticAgent(llm_client=client, model_name="simulated-qwen").critique(
        bundle,
        problem_frame,
    )

    assert problem_frame.frame_id == "pf_wartime_msme_support"
    assert draft.interventions
    assert {objective.metric_id for objective in bundle.problem_frame.objectives} == {
        "avg_income",
        "unemployment_rate",
    }
    assert bundle.policy_spec.interventions
    adaptive = next(
        item for item in bundle.policy_spec.interventions if item.kind == "adaptive_agent"
    )
    assert "adjustment_trigger" not in adaptive.params
    assert {"observation_space", "action_space", "utility"}.issubset(adaptive.params)
    assert critique.verdict == "APPROVE"
    assert call_events
    assert {event["provider"] for event in call_events} == {"simulated_gateway"}
