"""Tests for prompt cache."""

from __future__ import annotations

import time

import pytest

from polisyos.scientist.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayToolCall,
    GatewayUsage,
)
from polisyos.scientist.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
    compute_cache_key,
)


def _make_response(content: str = "cached") -> GatewayLLMResponse:
    return GatewayLLMResponse(content=content, usage=GatewayUsage(), raw={})


class _FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def generate(self, *args, **kwargs):
        self.calls.append((args, dict(kwargs)))
        prompt = str(args[0]) if args else str(kwargs.get("user") or kwargs.get("prompt") or "")
        return _make_response(f"answer:{prompt}")


class TestComputeCacheKey:
    def test_deterministic(self):
        k1 = compute_cache_key(system="sys", user="usr", model="m")
        k2 = compute_cache_key(system="sys", user="usr", model="m")
        assert k1 == k2

    def test_different_params_different_keys(self):
        k1 = compute_cache_key(system="sys", user="a", model="m")
        k2 = compute_cache_key(system="sys", user="b", model="m")
        assert k1 != k2

    def test_temperature_affects_key(self):
        k1 = compute_cache_key(user="hi", model="m", temperature=0.0)
        k2 = compute_cache_key(user="hi", model="m", temperature=1.0)
        assert k1 != k2

    def test_messages_and_positional_prompt_affect_key(self):
        k1 = compute_cache_key(
            prompt="hello",
            messages=[{"role": "user", "content": "hello"}],
            model="m",
            seed=7,
        )
        k2 = compute_cache_key(
            prompt="hello",
            messages=[{"role": "user", "content": "hello again"}],
            model="m",
            seed=7,
        )
        k3 = compute_cache_key(
            prompt="hello there",
            messages=[{"role": "user", "content": "hello"}],
            model="m",
            seed=7,
        )
        assert k1 != k2
        assert k1 != k3

    def test_volatile_metadata_is_excluded_from_key(self):
        k1 = compute_cache_key(
            user="hello",
            model="m",
            metadata={
                "tenant": "acme",
                "trace_id": "trace-1",
                "nested": {"generated_at": "2026-04-11T10:00:00Z"},
            },
            extra_payload={"request_id": "req-1", "semantic": {"tier": "strict"}},
        )
        k2 = compute_cache_key(
            user="hello",
            model="m",
            metadata={
                "tenant": "acme",
                "trace_id": "trace-2",
                "nested": {"generated_at": "2026-04-11T10:01:00Z"},
            },
            extra_payload={"request_id": "req-2", "semantic": {"tier": "strict"}},
        )
        k3 = compute_cache_key(
            user="hello",
            model="m",
            metadata={"tenant": "acme"},
            extra_payload={"semantic": {"tier": "fast"}},
        )

        assert k1 == k2
        assert k1 != k3


class TestInMemoryPromptCache:
    def test_hit(self):
        cache = InMemoryPromptCache(maxsize=10)
        resp = _make_response()
        cache.put("key1", resp)
        cached = cache.get("key1")
        assert cached is not resp
        assert cached.content == resp.content

    def test_put_stores_isolated_snapshot(self):
        cache = InMemoryPromptCache(maxsize=10)
        resp = _make_response()
        cache.put("key1", resp)

        resp.raw["mutated"] = True
        cached = cache.get("key1")

        assert "mutated" not in cached.raw

    def test_cached_tool_calls_and_raw_payloads_are_clone_isolated(self):
        cache = InMemoryPromptCache(maxsize=10)
        resp = GatewayLLMResponse(
            content="with-tool",
            usage=GatewayUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            raw={"nested": [{"value": "cached"}]},
            tool_calls=[
                GatewayToolCall(
                    id="call_1",
                    name="lookup",
                    arguments={"items": ["cached"]},
                    error_envelope={"warnings": ["cached"]},
                )
            ],
        )
        cache.put("key1", resp)

        first = cache.get("key1")
        assert first is not None
        first.raw["nested"][0]["value"] = "mutated"
        first.tool_calls[0].arguments["items"].append("mutated")
        first.tool_calls[0].error_envelope["warnings"].append("mutated")

        second = cache.get("key1")

        assert second is not None
        assert second.raw["nested"][0]["value"] == "cached"
        assert second.tool_calls[0].arguments["items"] == ["cached"]
        assert second.tool_calls[0].error_envelope["warnings"] == ["cached"]

    def test_miss(self):
        cache = InMemoryPromptCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=0.05)
        cache.put("key1", _make_response())
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_maxsize_eviction(self):
        cache = InMemoryPromptCache(maxsize=2, default_ttl_s=3600)
        cache.put("a", _make_response("a"))
        cache.put("b", _make_response("b"))
        cache.put("c", _make_response("c"))
        # "a" should be evicted (oldest)
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_size_property(self):
        cache = InMemoryPromptCache(maxsize=10)
        assert cache.size == 0
        cache.put("a", _make_response())
        assert cache.size == 1
        cache.clear()
        assert cache.size == 0

    def test_stats_track_hits_misses_puts_and_skips(self):
        cache = InMemoryPromptCache(maxsize=2, default_ttl_s=3600)
        cache.put("a", _make_response("a"))
        assert cache.get("a") is not None
        assert cache.get("b") is None
        cache.record_skip("tools_present")

        stats = cache.stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["puts"] == 1
        assert stats["skips"] == 1
        assert stats["skip_reasons"] == {"tools_present": 1}


class TestCachingLLMClient:
    @pytest.mark.asyncio
    async def test_caches_deterministic_positional_prompt_calls(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(
            base_client,
            cache=cache,
            model="m",
            ttl_s=3600,
        )

        first = await client.generate("hello", temperature=0.0)
        second = await client.generate("hello", temperature=0.0)

        assert first.content == "answer:hello"
        assert second.content == "answer:hello"
        assert len(base_client.calls) == 1
        assert cache.stats()["hits"] == 1
        assert first.raw["_polisyos_cache"]["cache_key"]
        assert second.raw["_polisyos_cache"]["status"] == "hit"
        assert first is not second

    @pytest.mark.asyncio
    async def test_cache_hits_do_not_share_mutable_response_state(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(
            base_client,
            cache=cache,
            model="m",
            ttl_s=3600,
        )

        first = await client.generate("hello", temperature=0.0)
        first.raw["nested"] = {"status": "changed-by-caller"}
        first.content = "overwritten"
        second = await client.generate("hello", temperature=0.0)

        assert second.content == "answer:hello"
        assert second.raw["_polisyos_cache"]["status"] == "hit"
        assert second.raw.get("nested") is None
        assert len(base_client.calls) == 1

    @pytest.mark.asyncio
    async def test_skips_cache_for_tool_calls_and_freshness_sensitive_inputs(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(
            base_client,
            cache=cache,
            model="m",
            ttl_s=3600,
        )

        await client.generate(
            user="hello",
            tools=[{"type": "function", "function": {"name": "x"}}],
            temperature=0.0,
        )
        await client.generate(
            user="Use https://example.org/fresh report",
            metadata={"retrieved_at": "2026-04-04T00:00:00Z"},
            temperature=0.0,
        )

        assert len(base_client.calls) == 2
        assert cache.size == 0
        assert cache.stats()["skips"] == 2
        assert cache.stats()["skip_reasons"] == {
            "retrieval_freshness_guard": 1,
            "tools_present": 1,
        }
