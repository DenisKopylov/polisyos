"""Tests for gateway client factory wiring."""

from __future__ import annotations

from contextlib import contextmanager

import polisyos.core.llm.traced_client as traced_client_module
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.llm.factory import GatewayLLMConfig, create_traced_gateway_client
from polisyos.scientist.orchestration.llm.fallback_router import FallbackRouter
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient


def test_create_traced_gateway_client_uses_plain_gateway_without_fallback_urls():
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


def test_create_traced_gateway_client_applies_preset_plugins_and_first_party_sanitizer():
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


def test_create_traced_gateway_client_wires_fallback_router_when_urls_present():
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


def test_create_traced_gateway_client_accepts_injected_observability(monkeypatch):
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
