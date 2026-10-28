"""Tests for prompt cache."""

from __future__ import annotations

import asyncio
import hashlib
import time

import pytest

from polisyos.scientist.agent.pi import LLMPIAgent
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayToolCall,
    GatewayUsage,
)
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
    compute_cache_key,
)


def _make_response(content: str = "cached") -> GatewayLLMResponse:
    return GatewayLLMResponse(content=content, usage=GatewayUsage(), raw={})


class _FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, *args, **kwargs):
        self.calls.append((args, dict(kwargs)))
        prompt = str(args[0]) if args else str(kwargs.get("user") or kwargs.get("prompt") or "")
        return _make_response(f"answer:{prompt}")


def _frozen_snapshot_metadata(
    *,
    tenant: str = "tenant-a",
    scope: str = "policy-a",
    content: bytes = b"frozen evidence bytes",
) -> dict[str, object]:
    """Return the explicit immutable-snapshot permission used by B67 tests."""

    content_hash = "sha256:" + hashlib.sha256(content).hexdigest()
    return {
        "cache_reuse": {
            "snapshot": {
                "ref": "artifact://evidence/policy-a",
                "content": content,
                "content_hash": content_hash,
                "version": "snapshot-v1",
                "immutable": True,
            },
            "permission": {
                "allowed": True,
                "tenant": tenant,
                "scope": scope,
            },
            "tenant": tenant,
            "scope": scope,
        }
    }


class _SlowLLMClient(_FakeLLMClient):
    def __init__(self, *, fail_first: bool = False) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.fail_first = fail_first

    async def generate(self, *args, **kwargs):
        self.calls.append((args, dict(kwargs)))
        self.started.set()
        await self.release.wait()
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("provider failed")
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
    async def test_pi_distinct_operations_do_not_reuse_same_content_response(self):
        class _PIResponseClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []
                self.responses = [
                    '{"problem_frame":{"frame_id":"pf-1","problem_statement":"Improve access"}}',
                    '{"sub_tasks":[{"task_id":"task-1","description":"Map access barriers"}]}',
                ]

            def prepare_cache_request(self, *args, **kwargs):
                return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

            async def generate(self, **kwargs):
                self.calls.append(dict(kwargs))
                return GatewayLLMResponse(
                    content=self.responses[len(self.calls) - 1],
                    usage=GatewayUsage(),
                    raw={},
                )

        provider = _PIResponseClient()
        cached = CachingLLMClient(
            provider,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        agent = LLMPIAgent(cached)

        frame = await agent.create_problem_frame("Improve access")
        tasks = await agent.decompose_task("Improve access")

        assert frame.problem_statement == "Improve access"
        assert [(task.task_id, task.description) for task in tasks] == [
            ("task-1", "Map access barriers")
        ]
        assert len(provider.calls) == 2
        assert all("cacheable" not in call.get("metadata", {}) for call in provider.calls)
        assert cached._cache.stats()["skip_reasons"] == {"cache_disabled_by_metadata": 2}

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
            adapter_options=("tuple", ["nested-list"], ("nested-tuple",)),
        )
        await client.generate(
            user="Use https://example.org/fresh report",
            metadata={"retrieved_at": "2026-04-04T00:00:00Z"},
            temperature=0.0,
        )

        assert len(base_client.calls) == 2
        observed = base_client.calls[0][1]["adapter_options"]
        assert type(observed) is tuple
        assert type(observed[1]) is list and type(observed[2]) is tuple
        assert observed == ("tuple", ["nested-list"], ("nested-tuple",))
        assert cache.size == 0
        assert cache.stats()["skips"] == 2
        assert cache.stats()["skip_reasons"] == {
            "retrieval_freshness_guard": 1,
            "tools_present": 1,
        }

    @pytest.mark.asyncio
    async def test_frozen_snapshot_without_authorizer_does_not_reuse(self):
        base_client = _FakeLLMClient()
        client = CachingLLMClient(
            base_client,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        metadata = _frozen_snapshot_metadata()

        first = await client.generate(
            user="Use https://example.org/frozen report with uncertainty_notes",
            metadata=metadata,
            temperature=0.0,
        )
        second = await client.generate(
            user="Use https://example.org/frozen report with uncertainty_notes",
            metadata=metadata,
            temperature=0.0,
        )

        assert first.content == second.content
        assert len(base_client.calls) == 2
        assert client._cache.stats()["hits"] == 0
        for _, call_kwargs in base_client.calls:
            forwarded_metadata = call_kwargs["metadata"]
            assert "content" not in forwarded_metadata["cache_reuse"]["snapshot"]
            assert forwarded_metadata["cache_reuse"]["snapshot"]["content_hash"].startswith(
                "sha256:"
            )

    @pytest.mark.asyncio
    async def test_changed_snapshot_bytes_or_hash_cannot_hit(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(base_client, cache=cache, model="m", ttl_s=3600)

        original = _frozen_snapshot_metadata(content=b"original")
        changed = _frozen_snapshot_metadata(content=b"changed")
        stale_hash = _frozen_snapshot_metadata(content=b"changed")
        stale_hash["cache_reuse"]["snapshot"]["content_hash"] = original["cache_reuse"]["snapshot"][
            "content_hash"
        ]

        await client.generate(
            user="Use https://example.org/frozen report",
            metadata=original,
            temperature=0.0,
        )
        await client.generate(
            user="Use https://example.org/frozen report",
            metadata=changed,
            temperature=0.0,
        )
        await client.generate(
            user="Use https://example.org/frozen report",
            metadata=stale_hash,
            temperature=0.0,
        )

        assert len(base_client.calls) == 3
        assert cache.size == 0
        for _, call_kwargs in base_client.calls:
            assert "content" not in call_kwargs["metadata"]["cache_reuse"]["snapshot"]

    @pytest.mark.asyncio
    async def test_lost_permission_and_model_change_cannot_hit(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(base_client, cache=cache, model="m", ttl_s=3600)
        other_model = CachingLLMClient(
            base_client,
            cache=cache,
            model="other-model",
            ttl_s=3600,
        )
        allowed = _frozen_snapshot_metadata()
        lost_permission = _frozen_snapshot_metadata()
        lost_permission["cache_reuse"]["permission"]["allowed"] = False

        await client.generate(
            user="Use https://example.org/frozen report",
            metadata=allowed,
            temperature=0.0,
        )
        await client.generate(
            user="Use https://example.org/frozen report",
            metadata=lost_permission,
            temperature=0.0,
        )
        await other_model.generate(
            user="Use https://example.org/frozen report",
            metadata=allowed,
            temperature=0.0,
        )

        assert len(base_client.calls) == 3

    @pytest.mark.asyncio
    async def test_live_url_without_snapshot_skips(self):
        base_client = _FakeLLMClient()
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=3600)
        client = CachingLLMClient(base_client, cache=cache, model="m", ttl_s=3600)

        await client.generate(user="Use https://example.org/live report", temperature=0.0)
        await client.generate(user="Use https://example.org/live report", temperature=0.0)

        assert len(base_client.calls) == 2
        assert cache.size == 0
        assert cache.stats()["skips"] == 2

    @pytest.mark.asyncio
    async def test_four_identical_ordinary_misses_single_flight(self):
        base_client = _SlowLLMClient()
        client = CachingLLMClient(
            base_client,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        tasks = [
            asyncio.create_task(client.generate(user="ordinary prompt", temperature=0.0))
            for _ in range(4)
        ]
        await asyncio.wait_for(base_client.started.wait(), timeout=1.0)
        base_client.release.set()
        responses = await asyncio.gather(*tasks)

        assert len(base_client.calls) == 1
        assert [response.content for response in responses] == ["answer:ordinary prompt"] * 4

    @pytest.mark.asyncio
    async def test_different_seed_and_tenant_are_separate_flights(self):
        base_client = _SlowLLMClient()
        client = CachingLLMClient(
            base_client,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        first = asyncio.create_task(
            client.generate(
                user="same prompt",
                seed=1,
                metadata=_frozen_snapshot_metadata(tenant="tenant-a"),
                temperature=0.0,
            )
        )
        await asyncio.wait_for(base_client.started.wait(), timeout=1.0)
        second = asyncio.create_task(
            client.generate(
                user="same prompt",
                seed=2,
                metadata=_frozen_snapshot_metadata(tenant="tenant-b"),
                temperature=0.0,
            )
        )
        await asyncio.sleep(0)
        base_client.release.set()
        await asyncio.gather(first, second)

        assert len(base_client.calls) == 2

    @pytest.mark.asyncio
    async def test_cancelled_ordinary_follower_does_not_cancel_owner(self):
        base_client = _SlowLLMClient()
        client = CachingLLMClient(
            base_client,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        owner = asyncio.create_task(client.generate("same prompt", temperature=0.0))
        await asyncio.wait_for(base_client.started.wait(), timeout=1.0)
        follower = asyncio.create_task(client.generate("same prompt", temperature=0.0))
        await asyncio.sleep(0)
        follower.cancel()
        with pytest.raises(asyncio.CancelledError):
            await follower

        base_client.release.set()
        response = await owner

        assert response.content == "answer:same prompt"
        assert len(base_client.calls) == 1

    @pytest.mark.asyncio
    async def test_failed_ordinary_owner_clears_inflight_entry(self):
        base_client = _SlowLLMClient(fail_first=True)
        client = CachingLLMClient(
            base_client,
            cache=InMemoryPromptCache(maxsize=10, default_ttl_s=3600),
            model="m",
            ttl_s=3600,
        )
        first = asyncio.create_task(client.generate("same prompt", temperature=0.0))
        await asyncio.wait_for(base_client.started.wait(), timeout=1.0)
        follower = asyncio.create_task(client.generate("same prompt", temperature=0.0))
        await asyncio.sleep(0)
        base_client.release.set()
        results = await asyncio.gather(first, follower, return_exceptions=True)

        assert all(isinstance(result, RuntimeError) for result in results)
        assert len(base_client.calls) == 1

        base_client.started.clear()
        base_client.release.clear()
        retry = asyncio.create_task(client.generate("same prompt", temperature=0.0))
        await asyncio.wait_for(base_client.started.wait(), timeout=1.0)
        base_client.release.set()
        response = await retry

        assert response.content == "answer:same prompt"
        assert len(base_client.calls) == 2


@pytest.mark.asyncio
async def test_distinct_wrappers_share_the_same_physical_cache_flight() -> None:
    """Per-request settlement hooks do not turn a shared cache into two producers."""
    from polisyos.core.llm.response import extract_llm_response_data

    cache = InMemoryPromptCache(maxsize=2, default_ttl_s=30)
    provider = _SlowLLMClient()
    first = CachingLLMClient(provider, cache=cache, model="fixture-model")
    second = CachingLLMClient(provider, cache=cache, model="fixture-model")
    producing = asyncio.create_task(first.generate(user="same", temperature=0))
    await provider.started.wait()
    following = asyncio.create_task(second.generate(user="same", temperature=0))
    await asyncio.sleep(0)
    assert len(provider.calls) == 1
    flight = next(iter(first._inflight.values()))

    def replace_cache_head(_task: object) -> None:
        # An unrelated publication between completion and follower scheduling
        # must not relabel this flight's exact response body or origin.
        replacement = _make_response("unrelated later cache head")
        replacement.producer_event_id = "other-physical-origin"
        cache.put(flight.cache_key, replacement)

    flight.task.add_done_callback(replace_cache_head)
    provider.release.set()
    origin, reused = await asyncio.gather(producing, following)
    assert origin.content == reused.content == "answer:same"
    evidence = extract_llm_response_data(
        reused, cache_settlement_session=second._cache_settlement_session
    )
    assert evidence.cache_hit
    assert evidence.origin_event_id == origin.producer_event_id
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_cache_owner_bookkeeping_follows_entry_lifetime() -> None:
    """Hits release request state; LRU/TTL/clear release retained origin state."""
    from polisyos.core.llm.cache_settlement import _owner_for

    cache = InMemoryPromptCache(maxsize=2, default_ttl_s=30)
    provider = _FakeLLMClient()
    client = CachingLLMClient(provider, cache=cache, model="fixture-model", ttl_s=30)
    for key in range(5):
        await client.generate(user=str(key), temperature=0)
        for _ in range(5):
            await client.generate(user=str(key), temperature=0)
        owner = _owner_for(client._cache_settlement_session)
        assert owner is not None
        assert not owner._registrations
        assert not owner._registration_handles
        assert not owner._outcomes
        assert len(owner._published) == cache.size <= 2
    assert len(provider.calls) == 5
    cache.clear()
    assert not owner._published
    await client.generate(user="after-clear", temperature=0)
    assert len(provider.calls) == 6

    expiring_cache = InMemoryPromptCache(maxsize=2, default_ttl_s=0)
    expiring = CachingLLMClient(provider, cache=expiring_cache, model="fixture-model", ttl_s=0)
    await expiring.generate(user="expires", temperature=0)
    await expiring.generate(user="expires", temperature=0)
    expiring_owner = _owner_for(expiring._cache_settlement_session)
    assert expiring_owner is not None
    assert len(expiring_owner._published) <= expiring_cache.size <= 1
    assert len(provider.calls) == 8


@pytest.mark.asyncio
async def test_legacy_cache_without_eviction_hooks_still_has_bounded_core_retention() -> None:
    """A get/put-only adapter cannot grow Core origin history beyond its bound."""
    from polisyos.core.llm.cache_settlement import _owner_for

    class LegacyCache:
        def __init__(self):
            self.entries = InMemoryPromptCache(maxsize=2, default_ttl_s=30)

        def get(self, key):
            return self.entries.get(key)

        def put(self, key, response, ttl_s):
            self.entries.put(key, response, ttl_s)

    cache = LegacyCache()
    provider = _FakeLLMClient()
    client = CachingLLMClient(
        provider, cache=cache, model="fixture-model", ttl_s=30, origin_retention_limit=2
    )
    for number in range(8):
        await client.generate(user=str(number), temperature=0)
        owner = _owner_for(client._cache_settlement_session)
        assert owner is not None and len(owner._published) <= 2
    reused = await client.generate(user="7", temperature=0)
    assert reused.content == "answer:7"
    assert len(provider.calls) == 8
    assert not owner._registrations and not owner._outcomes


def test_shared_cache_flight_can_be_consumed_from_two_event_loops() -> None:
    """The cache owner has one physical flight even across request worker loops."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    class ThreadProvider:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()
            self.calls = 0
            self.lock = threading.Lock()

        def prepare_cache_request(self, *args, **kwargs):
            return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

        async def generate(self, **kwargs):
            with self.lock:
                self.calls += 1
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0.001)
            return _make_response("one physical response")

    class WitnessCache(InMemoryPromptCache):
        def __init__(self):
            super().__init__(maxsize=2, default_ttl_s=30)
            self.second_miss = threading.Event()
            self.misses = 0
            self.witness_lock = threading.Lock()

        def get(self, key):
            response = super().get(key)
            if response is None:
                with self.witness_lock:
                    self.misses += 1
                    if self.misses == 2:
                        self.second_miss.set()
            return response

    provider = ThreadProvider()
    cache = WitnessCache()
    first = CachingLLMClient(provider, cache=cache, model="fixture-model")
    second = CachingLLMClient(provider, cache=cache, model="fixture-model")

    def request(client):
        return asyncio.run(client.generate(user="same", temperature=0))

    with ThreadPoolExecutor(max_workers=2) as executor:
        producing = executor.submit(request, first)
        try:
            assert provider.started.wait(3)
            following = executor.submit(request, second)
            # Both consumers actually observed a miss while the first
            # physical producer was blocked. The final provider count is the
            # independent oracle; no private field/marker establishes it.
            assert cache.second_miss.wait(3)
        finally:
            provider.release.set()
        produced, reused = producing.result(timeout=3), following.result(timeout=3)
    assert produced.content == reused.content == "one physical response"
    assert reused.producer_event_id == produced.producer_event_id
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_configured_provider_route_is_part_of_shared_cache_identity() -> None:
    """The same model/request on a different logical route is a physical miss."""
    cache = InMemoryPromptCache(maxsize=4, default_ttl_s=30)
    first_provider, changed_provider = _FakeLLMClient(), _FakeLLMClient()
    first_provider.provider, changed_provider.provider = "route-a", "route-b"
    first = CachingLLMClient(first_provider, cache=cache, model="same-model")
    changed = CachingLLMClient(changed_provider, cache=cache, model="same-model")
    await first.generate(user="same", temperature=0)
    await changed.generate(user="same", temperature=0)
    await first.generate(user="same", temperature=0)
    assert len(first_provider.calls) == len(changed_provider.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("declares_preparation", [False, True])
@pytest.mark.parametrize(
    "original_shape", ["object", "alias", "cycle", "view", "subclass", "nonfinite", "deep"]
)
async def test_opaque_python_call_preserves_original_values_after_admission(
    declares_preparation: bool,
    original_shape: str,
) -> None:
    class OriginalValue:
        def __deepcopy__(self, _memo):
            raise AssertionError("opaque values must not invoke copying hooks")

        def __str__(self):
            raise AssertionError("opaque values must not be stringified")

    class Provider:
        def __init__(self):
            self.calls = []

        async def generate(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return _make_response("opaque physical result")

    class DeclaredProvider(Provider):
        def prepare_cache_request(self, *args, **kwargs):
            return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    provider = DeclaredProvider() if declares_preparation else Provider()
    cache = InMemoryPromptCache()
    client = CachingLLMClient(provider, cache=cache, model="m")
    shared = ["shared native value"]
    cycle = []
    cycle.append(cycle)

    class ListSubclass(list):
        pass

    if original_shape == "object":
        original = OriginalValue()
    elif original_shape == "alias":
        original = (shared, shared)
    elif original_shape == "cycle":
        original = cycle
    elif original_shape == "view":
        original = memoryview(b"native bytes")
    elif original_shape == "subclass":
        original = ListSubclass(["native subclass value"])
    elif original_shape == "nonfinite":
        original = float("nan")
    else:
        original = []
        for _ in range(130):
            original = [original]
    values = {
        "user": "same",
        "temperature": 0.0,
        "tools": [{"type": "function", "function": {"name": "x"}}],
        "adapter_options": original,
        "metadata": {
            "caller_annotation": original if original_shape == "object" else "physical-only"
        },
    }

    async def refuse(*_args):
        assert not provider.calls
        raise RuntimeError("current producer begin refused")

    client.set_producer_settlement_hooks(
        begin=refuse, settle=lambda *_args: None, unknown=lambda *_args: None
    )
    with pytest.raises(RuntimeError, match="current producer begin refused"):
        await client.generate(**values)
    assert not provider.calls and cache.size == 0

    begins = []

    def begin(_event, digest, _provider):
        assert len(provider.calls) == len(begins)
        begins.append(digest)

    client.set_producer_settlement_hooks(
        begin=begin, settle=lambda *_args: None, unknown=lambda *_args: None
    )
    await client.generate(**values)
    await client.generate(**values)
    assert len(provider.calls) == len(begins) == 2 and cache.size == 0
    assert begins[0] != begins[1]
    for _args, kwargs in provider.calls:
        observed = kwargs["adapter_options"]
        assert observed is original
        if original_shape == "alias":
            assert observed[0] is shared and observed[1] is shared
        if original_shape == "cycle":
            assert observed[0] is cycle
        if original_shape == "object":
            assert kwargs["metadata"]["caller_annotation"] is original
