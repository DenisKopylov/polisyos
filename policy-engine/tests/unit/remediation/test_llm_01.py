"""Regression coverage for the LLM-01 response/tracing/cache boundary."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayUsage,
)
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, *_args: Any) -> None:
        return None

    def record_exception(self, *_args: Any) -> None:
        return None


class _SpanContext:
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, *_args: Any) -> bool:
        return False


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_as_current_span(self, *_args: Any, **_kwargs: Any) -> _SpanContext:
        span = _Span()
        self.spans.append(span)
        return _SpanContext(span)


class _Metrics:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict[str, Any]] = []

    def record_llm_call(self, **event: Any) -> None:
        if self.fail:
            raise RuntimeError("optional metrics sink unavailable")
        self.events.append(event)


class _PromptProvider:
    def __init__(self, *, raw: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raw = raw

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=f"answer:{kwargs.get('prompt') or kwargs.get('user') or ''}",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5, cost_usd=0.02),
            request_id="provider-request-1",
            raw=self.raw,
        )


def _traced(provider: Any, *, metrics: Any | None = None, **kwargs: Any) -> TracedLLMClient:
    return TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics if metrics is not None else _Metrics(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_duplicate_prompt_is_normalized_to_one_provider_argument() -> None:
    provider = _PromptProvider()
    traced = _traced(provider)

    response = await traced.generate("hello", prompt="hello")

    assert response.content == "answer:hello"
    assert provider.calls == [{"prompt": "hello"}]


@pytest.mark.asyncio
async def test_conflicting_prompt_forms_are_rejected_before_provider_call() -> None:
    provider = _PromptProvider()
    traced = _traced(provider)

    with pytest.raises(TypeError, match="conflicting prompt"):
        await traced.generate("positional", prompt="named")

    assert provider.calls == []


@pytest.mark.asyncio
async def test_optional_metrics_failure_preserves_provider_result_and_no_retry() -> None:
    provider = _PromptProvider()
    traced = _traced(provider, metrics=_Metrics(fail=True))

    response = await traced.generate(user="hello")

    assert response.content == "answer:hello"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_mandatory_accounting_failure_exposes_received_response() -> None:
    provider = _PromptProvider()

    def fail_accounting(_event: dict[str, Any]) -> None:
        raise RuntimeError("accounting ledger unavailable")

    traced = _traced(provider, required_accounting=fail_accounting)

    with pytest.raises(LLMAccountingError) as raised:
        await traced.generate(user="hello")

    assert raised.value.response.content == "answer:hello"
    assert raised.value.event["provider_call"] is True
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_cache_hits_emit_reuse_without_duplicate_provider_usage() -> None:
    provider = _PromptProvider(raw=None)
    metrics = _Metrics()
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=3600),
        model="fixture-model",
        ttl_s=3600,
    )
    traced = _traced(cached, metrics=metrics)

    first = await traced.generate(user="hello")
    second = await traced.generate(user="hello")
    third = await traced.generate(user="hello")

    assert len(provider.calls) == 1
    assert [event["status"] for event in metrics.events] == ["success", "cache_hit", "cache_hit"]
    assert metrics.events[0]["prompt_tokens"] == 3
    assert metrics.events[0]["cost_usd"] == pytest.approx(0.02)
    assert metrics.events[1]["prompt_tokens"] == 0
    assert metrics.events[1]["completion_tokens"] == 0
    assert metrics.events[1]["cost_usd"] == 0.0
    assert first.usage.prompt_tokens == second.usage.prompt_tokens == third.usage.prompt_tokens == 3
    assert second.raw["_polisyos_cache"]["status"] == "hit"
    assert second.raw["_polisyos_cache"]["cache_key"]
    assert second.raw is not third.raw
