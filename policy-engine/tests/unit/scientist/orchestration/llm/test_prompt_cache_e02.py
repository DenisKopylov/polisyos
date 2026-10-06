"""Producer completion and authority falsifiers on the canonical LLM stack."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import CachingLLMClient, InMemoryPromptCache


class _Span:
    def set_attribute(self, *args):
        pass

    def set_status(self, *args):
        pass

    def record_exception(self, *args):
        pass


class _Tracer:
    def start_as_current_span(self, *args, **kwargs):
        return nullcontext(_Span())


class _Gateway:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, **kwargs):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return GatewayLLMResponse(
            content="provider value", model="e02", provider="synthetic",
            request_id=f"request-{self.calls}",
            usage=GatewayUsage(prompt_tokens=7, completion_tokens=3, cost_usd=0.02),
        )


def _stack(gateway: _Gateway, events: list, *, tracer=None):
    cache = CachingLLMClient(gateway, cache=InMemoryPromptCache(), model="e02")
    traced = TracedLLMClient(
        cache, model_name="e02", tracer=tracer or _Tracer(),
        metrics=SimpleNamespace(record_llm_call=lambda **kwargs: None),
        required_accounting=events.append,
    )
    return cache, traced


@pytest.mark.asyncio
async def test_initiator_cancellation_cannot_erase_provider_completion() -> None:
    gateway = _Gateway()
    events = []
    cache, client = _stack(gateway, events)
    initiator = asyncio.create_task(client.generate(user="deterministic", temperature=0.0))
    await gateway.started.wait()
    initiator.cancel()
    with pytest.raises(asyncio.CancelledError):
        await initiator
    gateway.release.set()
    # Await the real producer, not a marker or arbitrary settling sleep.
    await asyncio.gather(*list(cache._inflight.values()))
    reused = await client.generate(user="deterministic", temperature=0.0)
    assert reused.content == "provider value"
    assert gateway.calls == 1
    charged = [event for event in events if event["provider_call"]]
    assert len(charged) == 1
    assert charged[0]["cost_usd"] == 0.02
    assert len([event for event in events if not event["provider_call"]]) == 1


@pytest.mark.asyncio
async def test_optional_tracing_failure_preserves_actual_provider_result() -> None:
    class BrokenTracer:
        def start_as_current_span(self, *args, **kwargs):
            raise RuntimeError("optional tracing unavailable")

    gateway = _Gateway()
    gateway.release.set()
    events = []
    _, client = _stack(gateway, events, tracer=BrokenTracer())
    result = await client.generate(user="trace independent", temperature=0.0)
    assert result.content == "provider value"
    assert len(events) == 1
    assert events[0]["cost_usd"] == 0.02


@pytest.mark.asyncio
async def test_metadata_permission_cannot_authorize_snapshot_reuse() -> None:
    gateway = _Gateway()
    gateway.release.set()
    content = b"real snapshot bytes"
    metadata = {"cache_reuse": {
        "snapshot": {
            "ref": "artifact://evidence", "version": "v1", "immutable": True,
            "content": content, "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
        },
        "permission": {"allowed": True, "tenant": "tenant-a", "scope": "scope-a"},
        "tenant": "tenant-a", "scope": "scope-a",
    }}
    cache = CachingLLMClient(gateway, cache=InMemoryPromptCache(), model="e02")
    await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
    await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
    assert gateway.calls == 2
