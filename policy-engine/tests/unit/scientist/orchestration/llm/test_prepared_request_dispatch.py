"""Run immutable call and effective-dispatch cache controls over actual local HTTP."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from aiohttp import web

from polisyos.scientist.orchestration.llm.fallback_router import EndpointConfig, FallbackRouter
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.prepared_request import (
    freeze_wire_object,
    prepare_call_values,
    thaw_wire_object,
)
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
    prepare_cached_request,
)


@asynccontextmanager
async def _http(handler: Any) -> Any:
    app = web.Application()
    app.router.add_post("/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


def _completion(content: str) -> web.Response:
    return web.json_response(
        {
            "model": "fixture-model",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.01},
        }
    )


@pytest.mark.asyncio
async def test_nested_caller_mutation_cannot_change_a_prepared_physical_request() -> None:
    bodies: list[dict[str, Any]] = []
    headers: list[str | None] = []

    async def completion(request: web.Request) -> web.Response:
        body = await request.json()
        bodies.append(body)
        headers.append(request.headers.get("x-caller-policy"))
        return _completion(json.dumps(body, sort_keys=True))

    async with _http(completion) as url:
        provider = GatewayLLMClient(
            base_url=url,
            api_key="fixture",
            model="fixture-model",
            extra_headers={"x-caller-policy": "A"},
        )
        cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
        entered, release = asyncio.Event(), asyncio.Event()

        async def begin(*_args: Any) -> None:
            entered.set()
            await release.wait()

        cached.set_producer_settlement_hooks(
            begin=begin, settle=lambda *_args: None, unknown=lambda *_args: None
        )
        call = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "A"}]}],
            "metadata": {"cache_buster": "A", "nested": {"policy_at": "A"}},
            "response_format": {"type": "json_schema", "json_schema": {"name": "A"}},
            "plugins": [{"id": "fixture", "config": {"policy_at": "A"}}],
            "temperature": 0,
        }
        original = json.loads(json.dumps(call))
        producing = asyncio.create_task(cached.generate(**call))
        try:
            # This is after key preparation and before the actual physical send.
            await asyncio.wait_for(entered.wait(), timeout=3)
            call["messages"][0]["content"][0]["text"] = "B"
            call["metadata"]["cache_buster"] = "B"
            call["metadata"]["nested"]["policy_at"] = "B"
            call["response_format"]["json_schema"]["name"] = "B"
            call["plugins"][0]["config"]["policy_at"] = "B"
            provider.extra_headers["x-caller-policy"] = "B"
            provider.model = "changed-after-prepare"
        finally:
            release.set()
        first = await asyncio.wait_for(producing, timeout=3)
        provider.extra_headers["x-caller-policy"] = "A"
        provider.model = "fixture-model"
        second = await cached.generate(**original)
        third = await cached.generate(**call)
        assert len(bodies) == 2 and headers == ["A", "A"]
        assert bodies[0] == {"model": "fixture-model", **original}
        assert bodies[1] == {"model": "fixture-model", **call}
        assert first.content == second.content and third.content != first.content
        assert second.raw["_polisyos_cache"]["status"] == "hit"
        await provider.aclose()


@pytest.mark.asyncio
async def test_endpoint_health_recovery_reselects_the_actual_head_before_reuse() -> None:
    calls: list[str] = []
    primary_live = False

    async def completion(request: web.Request) -> web.Response:
        endpoint = request.path.split("/")[1]
        calls.append(endpoint)
        if endpoint == "A" and not primary_live:
            return web.json_response({"error": {"message": "offline"}}, status=503)
        return _completion(endpoint)

    async with _http(completion) as url:
        provider = FallbackRouter(
            [
                EndpointConfig(url=url + "/A", model="fixture-model", max_retries=0),
                EndpointConfig(url=url + "/B", model="fixture-model", max_retries=0, priority=1),
            ],
            failure_threshold=1,
            recovery_timeout_s=60,
        )
        cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
        first = await cached.generate(user="same", temperature=0)
        assert first.content == "B" and first.raw["_polisyos_cache"]["status"] == "uncached"
        assert first.raw["_polisyos_cache"]["provider_call"] is True
        second = await cached.generate(user="same", temperature=0)
        third = await cached.generate(user="same", temperature=0)
        assert second.content == third.content == "B"
        assert third.raw["_polisyos_cache"]["status"] == "hit"
        primary_live = True
        # Advance the actual failed endpoint's recovery clock only; its
        # unhealthy state above was produced by the real failed HTTP request.
        provider._states[0].last_failure_time -= 61
        fourth = await cached.generate(user="same", temperature=0)
        fifth = await cached.generate(user="same", temperature=0)
        assert fourth.content == fifth.content == "A"
        assert fifth.raw["_polisyos_cache"]["status"] == "hit"
        assert calls == ["A", "B", "B", "A"]


@pytest.mark.asyncio
async def test_negotiated_plain_response_cannot_fill_a_requested_format_origin() -> None:
    supports_format = False
    bodies: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        body = await request.json()
        bodies.append(body)
        if "response_format" in body and not supports_format:
            return web.json_response(
                {"error": {"message": "response_format json_object unavailable"}}, status=400
            )
        return _completion("formatted" if "response_format" in body else "plain")

    async with _http(completion) as url:
        cache = InMemoryPromptCache()
        first_provider = GatewayLLMClient(
            base_url=url, api_key="fixture", model="fixture-model", max_retries=0
        )
        first = CachingLLMClient(first_provider, cache=cache, model="fixture-model")
        kwargs = {"user": "same", "temperature": 0, "response_format": {"type": "json_object"}}
        origin = await first.generate(**kwargs)
        assert origin.content == "plain" and origin.raw["_polisyos_cache"]["status"] == "uncached"
        assert origin.raw["_polisyos_cache"]["provider_call"] is True
        # The same adapter now has an explicit plain-mode dispatch state.
        # It may retain that exact request, but a fresh format-requesting adapter
        # must not read the plain result from the application cache.
        plain = await first.generate(**kwargs)
        plain_hit = await first.generate(**kwargs)
        assert plain.content == plain_hit.content == "plain"
        assert plain_hit.raw["_polisyos_cache"]["status"] == "hit"
        supports_format = True
        second_provider = GatewayLLMClient(
            base_url=url, api_key="fixture", model="fixture-model", max_retries=0
        )
        second = CachingLLMClient(second_provider, cache=cache, model="fixture-model")
        fresh = await second.generate(**kwargs)
        hit = await second.generate(**kwargs)
        assert fresh.content == hit.content == "formatted"
        assert hit.raw["_polisyos_cache"]["status"] == "hit"
        assert ["response_format" in body for body in bodies] == [True, False, False, True]
        await first_provider.aclose()
        await second_provider.aclose()


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), object(), datetime(2026, 10, 28, tzinfo=UTC)]
)
def test_wire_projection_rejects_raw_unknown_and_nonfinite_values(value: object) -> None:
    with pytest.raises(ValueError):
        freeze_wire_object({"nested": {"candidate": value}})


@pytest.mark.asyncio
async def test_prepared_cache_plan_binds_one_actual_client_and_one_logical_call() -> None:
    bodies: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        bodies.append(await request.json())
        return _completion("actual prepared body")

    async with _http(completion) as url:
        cache = InMemoryPromptCache()
        provider = GatewayLLMClient(base_url=url, api_key="fixture", model="fixture-model")
        original = {"user": "same", "temperature": 0, "metadata": {"nested": {"policy_at": "A"}}}
        planned = prepare_cached_request(provider, model="fixture-model", kwargs=original)
        original["metadata"]["nested"]["policy_at"] = "B"
        provider.model = "changed-after-prepare"
        client = CachingLLMClient(
            provider, cache=cache, model="fixture-model", prepared_request=planned
        )
        with pytest.raises(ValueError, match="already_bound"):
            CachingLLMClient(provider, cache=cache, model="fixture-model", prepared_request=planned)
        with pytest.raises(ValueError, match="call_mismatch"):
            await client.generate(**original)
        actual_begins: list[str] = []
        client.set_producer_settlement_hooks(
            begin=lambda _event, digest, _provider: actual_begins.append(digest),
            settle=lambda *_args: None,
            unknown=lambda *_args: None,
        )
        args, values = planned.call_values()
        first = await client.generate(*args, **values)
        assert actual_begins == [planned.request_digest]
        assert bodies[0]["model"] == "fixture-model"
        assert bodies[0]["metadata"]["nested"]["policy_at"] == "A"
        with pytest.raises(ValueError, match="already_consumed"):
            await client.generate(*args, **values)
        provider.model = "fixture-model"
        fresh = prepare_cached_request(provider, model="fixture-model", kwargs=values)
        second_client = CachingLLMClient(
            provider, cache=cache, model="fixture-model", prepared_request=fresh
        )
        second = await second_client.generate(*args, **values)
        assert first.content == second.content and second.raw["_polisyos_cache"]["status"] == "hit"
        assert len(bodies) == 1
        await provider.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("original", "different"),
    [
        (("native", [1]), ["native", [1]]),
        (b"bytes", bytearray(b"bytes")),
        (True, 1),
        (1, 1.0),
        (0.0, -0.0),
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
    ],
)
async def test_prebound_call_identity_preserves_native_type_and_value(
    original: Any, different: Any
) -> None:
    # These values are legal to a Python adapter; JSON transport has a separate owner.
    from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call

    class Provider:
        def __init__(self) -> None:
            self.values: list[Any] = []

        def prepare_cache_request(self, *args: Any, **kwargs: Any) -> Any:
            return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

        async def generate(self, **kwargs: Any) -> str:
            self.values.append(kwargs["adapter_value"])
            return "physical-only tool result"

    provider = Provider()
    values = {"user": "same", "tools": [{"type": "function"}], "adapter_value": original}
    plan = prepare_cached_request(provider, model="fixture", kwargs=values)
    client = CachingLLMClient(
        provider, cache=InMemoryPromptCache(), model="fixture", prepared_request=plan
    )
    with pytest.raises(ValueError, match="call_mismatch"):
        await client.generate(**{**values, "adapter_value": different})
    assert not provider.values
    assert await client.generate(**values) == "physical-only tool result"
    assert len(provider.values) == 1 and type(provider.values[0]) is type(original)
    assert provider.values[0] == original


@pytest.mark.asyncio
async def test_actual_gateway_keeps_json_arrays_and_rejects_unknown_before_dispatch() -> None:
    bodies: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        bodies.append(await request.json())
        return _completion("actual JSON transport")

    async with _http(completion) as url:
        provider = GatewayLLMClient(base_url=url, api_key="fixture", model="fixture-model")
        client = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
        for invalid in [object(), datetime(2026, 10, 28, tzinfo=UTC), float("nan")]:
            with pytest.raises(ValueError):
                await client.generate(user="same", tools=[{"type": "function"}], extra=invalid)
        assert not bodies and provider._session is None
        await client.generate(
            user="same", tools=[{"type": "function"}], adapter_options=("a", ("b",))
        )
        assert len(bodies) == 1 and bodies[0]["adapter_options"] == ["a", ["b"]]
        await provider.aclose()


def test_opaque_prebound_request_refuses_unestablished_equality_without_dispatch() -> None:
    from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call

    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def prepare_cache_request(self, *args: Any, **kwargs: Any) -> Any:
            return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

        async def generate(self, **kwargs: Any) -> str:
            self.calls += 1
            return "opaque physical result"

    provider = Provider()
    planned = prepare_cached_request(
        provider, model="fixture", kwargs={"user": "same", "adapter_value": object()}
    )
    assert planned.provider_request.reusable is False
    with pytest.raises(ValueError, match="input_not_bound"):
        CachingLLMClient(
            provider, cache=InMemoryPromptCache(), model="fixture", prepared_request=planned
        )
    assert provider.calls == 0


def test_prepared_values_use_the_real_strict_decoder_contract() -> None:
    expected = {"messages": [{"role": "user", "content": "A"}], "temperature": 0}
    assert thaw_wire_object(freeze_wire_object(expected)) == expected
    native = prepare_call_values((), {"adapter_options": ("tuple", ["nested-list"])})
    args, kwargs = native.call_values()
    assert args == () and type(kwargs["adapter_options"]) is tuple
    assert type(kwargs["adapter_options"][1]) is list
    assert kwargs["adapter_options"] == ("tuple", ["nested-list"])


@pytest.mark.parametrize(
    "raw",
    [b"\xff", b'{"same":1,"same":2}', b'{"value":NaN}', b'{"value":1e1000}', b"[]", b'{"missing":'],
)
def test_prepared_decoder_preserves_strict_refusal_with_stable_source(raw: bytes) -> None:
    with pytest.raises(ValueError) as failure:
        thaw_wire_object(raw)
    assert "prepared LLM request" in str(failure.value)
    assert "polisyos.scientist.orchestration.llm.prepared_request" in str(failure.value)
