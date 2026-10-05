"""Item-bound E02 reuse identity, deadline and accounting discriminators."""

from __future__ import annotations

import asyncio
import copy
import hashlib
from typing import Any

import pytest

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import CachingLLMClient, InMemoryPromptCache


class _Provider:
    def __init__(self, *, gated: bool = False, fail_first: bool = False) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.proceed = asyncio.Event()
        self.gated = gated
        self.fail_first = fail_first

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls += 1
        call = self.calls
        self.started.set()
        if self.gated:
            await self.proceed.wait()
        if self.fail_first and call == 1:
            raise OSError("injected provider failure before response")
        return GatewayLLMResponse(
            content=f"answer-{call}",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, cost_usd=0.02),
        )


def _packet() -> dict[str, Any]:
    content = b"independent frozen evidence"
    return {
        "cache_reuse": {
            "snapshot": {
                "content": content,
                "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
                "ref": "artifact://e02/evidence",
                "version": "v1",
                "immutable": True,
            },
            "permission": {"allowed": True, "tenant": "t1", "scope": "s1"},
            "tenant": "t1",
            "scope": "s1",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ["version", "scope", "permission", "seed", "params", "model"])
async def test_reuse_requires_same_packet_and_substantive_context(axis: str) -> None:
    """Material/context changes reach a provider while the exact packet reuses."""
    provider = _Provider()
    cache = InMemoryPromptCache()
    client = CachingLLMClient(provider, cache=cache, model="m1")
    kwargs = {"user": "Read https://e02.invalid/frozen", "metadata": _packet(), "seed": 1}
    first = await client.generate(**kwargs)
    repeated = await client.generate(**kwargs)
    assert first.content == repeated.content
    assert provider.calls == 1

    changed = copy.deepcopy(kwargs)
    context = changed["metadata"]["cache_reuse"]
    if axis == "version":
        context["snapshot"]["version"] = "v2"
    elif axis == "scope":
        context["scope"] = context["permission"]["scope"] = "s2"
    elif axis == "permission":
        context["permission"]["allowed"] = False
    elif axis == "seed":
        changed["seed"] = 2
    elif axis == "params":
        changed["max_tokens"] = 99
    else:
        client = CachingLLMClient(provider, cache=cache, model="m2")
    result = await client.generate(**changed)
    assert result.content == "answer-2"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_singleflight_deadline_clears_task_and_permits_real_retry() -> None:
    """A timed-out physical provider does not remain the owner of later calls."""
    provider = _Provider(gated=True)
    client = CachingLLMClient(
        provider, cache=InMemoryPromptCache(), model="m", inflight_timeout_s=0.03
    )
    waits = [asyncio.create_task(client.generate(user="hello")) for _ in range(4)]
    await asyncio.wait_for(provider.started.wait(), timeout=0.5)
    results = await asyncio.gather(*waits, return_exceptions=True)
    assert all(isinstance(result, TimeoutError) for result in results)
    assert provider.calls == 1
    assert client._inflight == {}
    provider.proceed.set()
    response = await client.generate(user="hello")
    assert response.content == "answer-2"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_cancelled_initiator_preserves_follower_and_clears_owner_task() -> None:
    """Cancellation of the initiating request cannot cancel remaining demand."""
    provider = _Provider(gated=True)
    client = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="m")
    owner = asyncio.create_task(client.generate(user="hello"))
    await asyncio.wait_for(provider.started.wait(), timeout=0.5)
    follower = asyncio.create_task(client.generate(user="hello"))
    await asyncio.sleep(0)
    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner
    provider.proceed.set()
    response = await asyncio.wait_for(follower, timeout=0.5)
    assert response.content == "answer-1"
    assert provider.calls == 1
    assert client._inflight == {}


class _Metrics:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record_llm_call(self, **event: Any) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_provider_failure_retry_and_reuse_charge_received_usage_once() -> None:
    """Only the successful retry incurs received-response usage and cost."""
    provider = _Provider(fail_first=True)
    metrics = _Metrics()
    client = TracedLLMClient(
        CachingLLMClient(provider, cache=InMemoryPromptCache(), model="m"),
        model_name="m",
        metrics=metrics,
    )
    with pytest.raises(OSError, match="injected provider"):
        await client.generate(user="hello")
    response = await client.generate(user="hello")
    reuse = await client.generate(user="hello")
    assert provider.calls == 2
    assert response.usage.prompt_tokens == reuse.usage.prompt_tokens == 3
    assert [event["status"] for event in metrics.events] == ["error", "success", "cache_hit"]
    assert sum(event.get("cost_usd") or 0.0 for event in metrics.events) == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_cancelled_initiator_cannot_erase_actual_provider_cost() -> None:
    """Physical success must have one accounting owner even if its caller cancels."""
    provider = _Provider(gated=True)
    metrics = _Metrics()
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="m")
    client = TracedLLMClient(cached, model_name="m", metrics=metrics)
    owner = asyncio.create_task(client.generate(user="hello"))
    await asyncio.wait_for(provider.started.wait(), timeout=0.5)
    follower = asyncio.create_task(client.generate(user="hello"))
    await asyncio.sleep(0)
    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner
    provider.proceed.set()
    response = await asyncio.wait_for(follower, timeout=0.5)
    assert provider.calls == 1
    assert response.usage.cost_usd == 0.02
    assert sum(event.get("cost_usd") or 0.0 for event in metrics.events) == pytest.approx(0.02)
