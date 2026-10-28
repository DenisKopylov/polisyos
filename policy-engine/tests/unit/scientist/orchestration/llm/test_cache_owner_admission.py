"""Exercise cache eligibility, physical wire emission, and exact hit intake."""

from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiohttp import web

from polisyos.core.llm import LLMSettlementOwnershipError
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    _gateway_cache_reuse_scope,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.fallback_router import EndpointConfig, FallbackRouter
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    GatewayLLMResponse,
    GatewayUsage,
)
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReusePrincipal,
    CachingLLMClient,
    InMemoryPromptCache,
)


class _Owner:
    """Component fixture; the served integration test supplies the actual lease fence."""

    def __init__(self, active: bool = True) -> None:
        self.active = active

    def authorize_reuse(self, request: Any) -> CacheReuseDecision | None:
        if not self.active:
            return None
        return CacheReuseDecision(
            issuer="component-fixture",
            epoch="epoch-1",
            actor_id=request.actor_id,
            tenant=request.tenant,
            scope=request.scope,
            purpose=request.purpose,
            model=request.model,
            parameters_digest=request.parameters_digest,
            evidence=request.evidence,
        )


def _context() -> dict[str, Any]:
    content = b"fixture evidence"
    return {
        "tenant": "tenant-a",
        "scope": "tenant-a/cell-a",
        "purpose": "fixture-candidate",
        "snapshot": {
            "ref": "sha256:" + hashlib.sha256(content).hexdigest(),
            "version": "selected-profile-1",
            "immutable": True,
            "content": content,
            "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
        },
    }


class _Provider:
    """An unknown-default provider changes its answer on every physical call."""

    provider = "fixture-provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=f"answer-{len(self.calls)}",
            model="fixture-model",
            provider=self.provider,
            usage=GatewayUsage(cost_usd=0.01),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("temperature", [None, False, "0", float("nan"), 0.5, 0, 0.0])
async def test_unknown_default_never_establishes_deterministic_reuse(temperature: Any) -> None:
    provider = _Provider()
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
    kwargs = {"user": "same request", "temperature": temperature}
    if isinstance(temperature, float) and temperature != temperature:
        with pytest.raises(ValueError):
            await cached.generate(**kwargs)
        assert not provider.calls
        return
    await cached.generate(**kwargs)
    await cached.generate(**kwargs)
    eligible = type(temperature) in (int, float) and temperature == 0
    assert len(provider.calls) == (1 if eligible else 2)


@pytest.mark.asyncio
async def test_omitted_temperature_is_uncached_for_an_unknown_provider() -> None:
    provider = _Provider()
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
    first = await cached.generate(user="same request")
    second = await cached.generate(user="same request")
    assert len(provider.calls) == 2
    assert first.content != second.content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    ["allowed", "denied", "tool", "disabled", "unknown", "seed", "fallback", "wire_variation"],
)
async def test_injected_cache_selectors_never_reach_actual_gateway_wire(route: str) -> None:
    bodies: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        bodies.append(await request.json())
        return web.json_response(
            {
                "model": "fixture-model",
                "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    async def unavailable(request: web.Request) -> web.Response:
        bodies.append(await request.json())
        return web.json_response({"error": {"message": "fixture unavailable"}}, status=500)

    app = web.Application()
    app.router.add_post("/chat/completions", completion)
    app.router.add_post("/unavailable/chat/completions", unavailable)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None
    port = site._server.sockets[0].getsockname()[1]
    provider: GatewayLLMClient | FallbackRouter = GatewayLLMClient(
        base_url=f"http://127.0.0.1:{port}", api_key="local-fixture", model="fixture-model"
    )
    if route == "fallback":
        provider = FallbackRouter(
            [
                EndpointConfig(
                    url=f"http://127.0.0.1:{port}/unavailable", model="fixture-model", max_retries=0
                ),
                EndpointConfig(
                    url=f"http://127.0.0.1:{port}", model="fixture-model", priority=1, max_retries=0
                ),
            ]
        )
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(),
        model="fixture-model",
        reuse_authorizer=_Owner(active=route != "denied"),
        reuse_principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
        reuse_context=_context(),
        require_reuse_authorization=True,
        reuse_guard=lambda operation: operation(),
    )
    kwargs: dict[str, Any] = {
        "user": "same request",
        "temperature": None if route == "unknown" else 0,
        "metadata": {
            "producer_tag": "preserve",
            "tenant": "caller-selected",
            "cache_buster": "old",
            "nested": {"policy_at": "old"},
        },
    }
    if route == "disabled":
        kwargs["metadata"]["cacheable"] = False
    if route == "tool":
        kwargs["tools"] = [{"type": "function", "function": {"name": "fixture"}}]
    if route == "seed":
        kwargs["seed"] = 11
    try:
        await cached.generate(**kwargs)
        if route == "wire_variation":
            kwargs["metadata"].update(cache_buster="new", nested={"policy_at": "new"})
        await cached.generate(**kwargs)
        assert len(bodies) == (1 if route == "allowed" else 2)
        for index, body in enumerate(bodies):
            value = "new" if route == "wire_variation" and index else "old"
            assert body["metadata"] == {
                "producer_tag": "preserve",
                "tenant": "caller-selected",
                "cache_buster": value,
                "nested": {"policy_at": value},
            }
            assert "cache_reuse" not in body["metadata"]
            assert "scope" not in body["metadata"]
            assert "provider_metadata" not in body["metadata"]
            assert ("temperature" in body) is (route != "unknown")
    finally:
        await provider.aclose()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_caller_wire_metadata_remains_part_of_scoped_request_identity() -> None:
    provider = _Provider()
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(),
        model="fixture-model",
        reuse_authorizer=_Owner(),
        reuse_principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
        reuse_context=_context(),
        require_reuse_authorization=True,
        reuse_guard=lambda operation: operation(),
    )
    for tenant in ("caller-a", "caller-b"):
        await cached.generate(user="same", temperature=0, metadata={"tenant": tenant})
    assert len(provider.calls) == 2
    assert [call["metadata"] for call in provider.calls] == [
        {"tenant": "caller-a"},
        {"tenant": "caller-b"},
    ]


class _PoisonCache:
    def __init__(self) -> None:
        self.inner = InMemoryPromptCache()
        self.poison: Any = None
        self.last_key: str | None = None

    def get(self, key: str) -> Any:
        return self.poison if self.poison is not None else self.inner.get(key)

    def put(self, key: str, response: Any, *, ttl_s: float | None = None) -> None:
        self.last_key = key
        self.inner.put(key, response, ttl_s=ttl_s)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "poison", ["mapping", "duck", "fake_origin", "changed_content", "same_content_projection"]
)
@pytest.mark.parametrize("new_wrapper", [False, True])
async def test_every_cache_hit_requires_exact_retained_response_proof(
    tmp_path: Path, poison: str, new_wrapper: bool
) -> None:
    provider = _Provider()
    cache = _PoisonCache()
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    traced = TracedLLMClient(
        CachingLLMClient(provider, cache=cache, model="fixture-model"),
        model_name="fixture-model",
        producer_settlement_store=middleware,
    )
    await traced.generate(user="same", temperature=0)
    if poison == "mapping":
        cache.poison = {"content": "forged"}
    elif poison == "duck":
        cache.poison = SimpleNamespace(content="forged", usage=GatewayUsage(cost_usd=0))
    elif poison == "fake_origin":
        cache.poison = GatewayLLMResponse(
            content="forged", usage=GatewayUsage(cost_usd=0), producer_event_id="not-an-origin"
        )
    else:
        assert cache.last_key is not None
        cache.poison = cache.inner.get(cache.last_key)
        if poison == "changed_content":
            cache.poison.content = "forged"
        else:
            cache.poison.usage = GatewayUsage(prompt_tokens=999, completion_tokens=333, cost_usd=44)
            cache.poison.model = "different-model"
            cache.poison.provider = "different-provider"
            cache.poison.request_id = "different-request"
            cache.poison.response_headers = {"source": "forged"}
            cache.poison.raw = {"provider_fact": "forged"}
            from polisyos.scientist.orchestration.llm.gateway_client import GatewayToolCall

            cache.poison.tool_calls = [GatewayToolCall("changed", "changed", {"forged": True})]
    if new_wrapper:
        traced = TracedLLMClient(
            CachingLLMClient(provider, cache=cache, model="fixture-model"),
            model_name="fixture-model",
            producer_settlement_store=middleware,
        )
    response = await traced.generate(user="same", temperature=0)
    assert response.content == "answer-2"
    assert len(provider.calls) == 2
    rows = tuple(ledger.snapshot().producer_settlements.values())
    assert len(rows) == 2
    assert all(row.cost_origin == "reported" and row.amount == Decimal("0.01") for row in rows)


@pytest.mark.asyncio
async def test_unattested_shared_follower_performs_its_own_physical_call() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class OpaqueProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, **_kwargs: Any) -> Any:
            self.calls += 1
            entered.set()
            await release.wait()
            return SimpleNamespace(content=f"physical-{self.calls}")

    provider = OpaqueProvider()
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
    first = asyncio.create_task(cached.generate(user="same", temperature=0))
    await entered.wait()
    second = asyncio.create_task(cached.generate(user="same", temperature=0))
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(first, second, return_exceptions=True)
    # An opaque result has no reuse proof: each successful consumer requires
    # its own physical call, or the consumer must explicitly refuse it.
    assert sum(not isinstance(result, BaseException) for result in results) <= provider.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_guard", [True, False])
async def test_matching_callback_cannot_replace_a_missing_or_refusing_owner_fence(
    missing_guard: bool,
) -> None:
    provider = _Provider()

    def refusing_guard(_operation: Any) -> Any:
        raise RuntimeError("fixture live owner was lost")

    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(),
        model="fixture-model",
        reuse_authorizer=_Owner(),
        reuse_principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
        reuse_context=_context(),
        require_reuse_authorization=True,
        reuse_guard=None if missing_guard else refusing_guard,
    )
    with pytest.raises((LLMSettlementOwnershipError, RuntimeError)):
        await cached.generate(user="same", temperature=0)
    assert not provider.calls


def _fixture_binding(run_id: str) -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id=run_id,
        control_job_id="job-" + run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="fixture-profile",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_kind", ["normal", "error", "cancel"])
async def test_closed_factory_scope_cannot_serve_a_retained_hit(
    monkeypatch: Any,
    tmp_path: Path,
    exit_kind: str,
) -> None:
    """Exercise scope lifetime; the HTTP tests exercise the server's real lease fence."""
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    config = GatewayLLMConfig(base_url="http://fixture.invalid", api_key="fixture")
    cache = InMemoryPromptCache()
    ledger = FileBudgetLedger(tmp_path / "scope.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    binding = _fixture_binding("scope-run")
    clients: list[Any] = []
    children: list[asyncio.Task[Any]] = []
    late = asyncio.Event()
    ready = asyncio.Event()

    async def work() -> None:
        with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
            with _gateway_cache_reuse_scope(
                authorizer=_Owner(),
                principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
                context=_context(),
                cache=cache,
                run_id=binding.run_id,
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
            ):
                client = create_traced_gateway_client(model_name="fixture", config=config)
                assert client is not None
                clients.append(client)

                async def retained_child() -> Any:
                    await late.wait()
                    return await client.generate(user="stable", temperature=0)

                children.append(asyncio.create_task(retained_child()))
                await client.generate(user="stable", temperature=0)
                ready.set()
                if exit_kind == "error":
                    raise RuntimeError("fixture exit")
                if exit_kind == "cancel":
                    await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await asyncio.wait_for(ready.wait(), timeout=3)
    if exit_kind == "cancel":
        task.cancel()
    results = await asyncio.gather(task, return_exceptions=True)
    if exit_kind == "error":
        assert isinstance(results[0], RuntimeError)
    elif exit_kind == "cancel":
        assert isinstance(results[0], asyncio.CancelledError)
    else:
        assert results == [None]
    client = clients[0]
    with pytest.raises(LLMSettlementOwnershipError, match="scope_closed"):
        await client.generate(user="stable", temperature=0)
    with pytest.raises(LLMSettlementOwnershipError, match="scope_closed"):
        await client.list_model_ids()
    late.set()
    child_results = await asyncio.gather(*children, return_exceptions=True)
    assert all(isinstance(result, LLMSettlementOwnershipError) for result in child_results)
    assert len(client.unwrap().calls) == 1
    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "scope.json"))
    rows = reopened.list_producer_events_for_run_safe(binding)
    assert len(rows) == 1 and rows[0].control_job_attempt == 1
    outside = create_traced_gateway_client(model_name="fixture", run_id="outside", config=config)
    assert outside is not None and outside._run_id == "outside"
    assert (await outside.generate(user="outside", temperature=0)).content


@pytest.mark.asyncio
async def test_overlapping_scoped_clients_keep_distinct_principals_and_producer_bindings(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Exercise actual factory/producer concurrency without treating fixtures as authority."""
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    config = GatewayLLMConfig(base_url="http://fixture.invalid", api_key="fixture")
    cache = InMemoryPromptCache()
    ledger = FileBudgetLedger(tmp_path / "parallel.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    entered = [asyncio.Event(), asyncio.Event()]

    async def job(index: int) -> Any:
        binding = _fixture_binding(f"run-{index}")
        with middleware.producer_run_binding_scope(binding, control_job_attempt=index + 1):
            with _gateway_cache_reuse_scope(
                authorizer=_Owner(),
                principal=CacheReusePrincipal(f"actor-{index}", "tenant-a", "tenant-a/cell-a"),
                context=_context(),
                cache=cache,
                run_id=binding.run_id,
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
            ):
                client = create_traced_gateway_client(model_name="fixture", config=config)
                assert client is not None
                entered[index].set()
                await entered[1 - index].wait()
                first = await client.generate(user="same", temperature=0)
                second = await client.generate(user="same", temperature=0)
                assert first.settlement.event.cost_origin == "reported"
                assert second.settlement.event.cost_origin == "reuse"
                return client, binding

    runs = await asyncio.gather(job(0), job(1))
    for client, binding in runs:
        assert client._run_id == binding.run_id
        rows = middleware.list_producer_events_for_run_safe(binding)
        assert len(rows) == 2
        assert all(row.run_binding == binding for row in rows)
        assert all(
            row.control_job_attempt == (1 if binding.run_id == "run-0" else 2) for row in rows
        )
        assert len(client.unwrap().calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unavailable", "timeout"])
async def test_actual_dependency_guard_failure_never_dispatches(failure: str) -> None:
    from polisyos.runtime.http.errors import (
        RuntimeDependencyTimeoutError,
        RuntimeDependencyUnavailableError,
    )

    provider = _Provider()
    error = (
        RuntimeDependencyUnavailableError
        if failure == "unavailable"
        else RuntimeDependencyTimeoutError
    )("control_plane_store")

    def refuse(_operation: Any) -> Any:
        raise error

    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(),
        model="fixture-model",
        reuse_authorizer=_Owner(),
        reuse_principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
        reuse_context=_context(),
        require_reuse_authorization=True,
        reuse_guard=refuse,
    )
    for kwargs in ({"temperature": 0}, {"temperature": None}, {"temperature": 0, "tools": [{}]}):
        with pytest.raises(type(error)):
            await cached.generate(user="same", **kwargs)
    assert not provider.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_kind", ["normal", "error", "cancel"])
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_started_producer_keeps_exact_owner_after_scope_close(
    monkeypatch: Any,
    tmp_path: Path,
    exit_kind: str,
    outcome: str,
) -> None:
    from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    entered, release, ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = SimulatedGatewayLLMClient.generate

    async def provider(client: Any, **kwargs: Any) -> Any:
        entered.set()
        await release.wait()
        if outcome == "error":
            raise RuntimeError("physical fixture error")
        if outcome == "cancel":
            raise asyncio.CancelledError()
        return await original(client, **kwargs)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", provider)
    ledger_path = tmp_path / "inflight.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    binding = _fixture_binding("inflight")
    pending: list[asyncio.Task[Any]] = []
    intents: list[Any] = []

    async def admitted() -> None:
        with middleware.producer_run_binding_scope(binding, control_job_attempt=7):
            with _gateway_cache_reuse_scope(
                authorizer=_Owner(),
                principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
                context=_context(),
                cache=InMemoryPromptCache(),
                run_id=binding.run_id,
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
                intent_observer=lambda intent, receipt: intents.append((intent, receipt)),
            ):
                client = create_traced_gateway_client(
                    model_name="fixture",
                    config=GatewayLLMConfig(base_url="http://fixture.invalid", api_key="fixture"),
                )
                assert client is not None
                pending.append(asyncio.create_task(client.generate(user="stable", temperature=0)))
                await asyncio.wait_for(entered.wait(), timeout=3)
                ready.set()
                if exit_kind == "error":
                    raise RuntimeError("scope fixture error")
                if exit_kind == "cancel":
                    await asyncio.Event().wait()

    task = asyncio.create_task(admitted())
    await asyncio.wait_for(ready.wait(), timeout=3)
    if exit_kind == "cancel":
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert len(intents) == 1
    before = FileBudgetLedger(ledger_path).list_producer_events_for_run(binding)
    assert len(before) == 1 and before[0].control_job_attempt == 7 and before[0].status == "pending"
    assert intents[0][1] == before[0]
    assert intents[0][1].run_binding == binding
    release.set()
    result = (await asyncio.gather(*pending, return_exceptions=True))[0]
    if outcome == "success":
        assert not isinstance(result, BaseException)
    else:
        assert isinstance(result, BaseException)
    fresh = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    rows = fresh.list_producer_events_for_run_safe(binding)
    assert len(rows) == 1 and rows[0].event_id == intents[0][0].event_id
    assert rows[0].run_binding == binding and rows[0].control_job_attempt == 7
    assert rows[0].status == ("committed" if outcome == "success" else "unknown")


@pytest.mark.asyncio
async def test_shared_follower_uses_the_whole_actual_flight_projection(tmp_path: Path) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    class Provider(_Provider):
        async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
            self.calls.append(dict(kwargs))
            entered.set()
            await release.wait()
            return GatewayLLMResponse(
                content="same content",
                model="fixture-model",
                provider="actual-provider",
                usage=GatewayUsage(prompt_tokens=12, completion_tokens=4, cost_usd=0.01),
                request_id="actual-request",
                response_headers={"source": "actual"},
                raw={"source": "actual"},
            )

    provider, cache = Provider(), _PoisonCache()
    ledger = FileBudgetLedger(tmp_path / "follower.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    first_cache = CachingLLMClient(provider, cache=cache, model="fixture-model")
    second_cache = CachingLLMClient(provider, cache=cache, model="fixture-model")
    first = TracedLLMClient(
        first_cache, model_name="fixture-model", producer_settlement_store=middleware
    )
    second = TracedLLMClient(
        second_cache, model_name="fixture-model", producer_settlement_store=middleware
    )
    producing = asyncio.create_task(first.generate(user="same", temperature=0))
    await asyncio.wait_for(entered.wait(), timeout=3)
    following = asyncio.create_task(second.generate(user="same", temperature=0))
    flight = next(iter(first_cache._inflight.values()))

    async def joined() -> None:
        while len(flight.registrations) < 2:
            await asyncio.sleep(0)

    await asyncio.wait_for(joined(), timeout=3)

    def poison_head(_task: Any) -> None:
        assert cache.last_key is not None
        cache.poison = cache.inner.get(cache.last_key)
        cache.poison.usage = GatewayUsage(prompt_tokens=999, completion_tokens=999, cost_usd=999)
        cache.poison.provider = "forged-provider"
        cache.poison.model = "forged-model"
        cache.poison.raw = {"source": "forged"}

    flight.task.add_done_callback(poison_head)
    release.set()
    origin, follower = await asyncio.wait_for(asyncio.gather(producing, following), timeout=3)
    assert len(provider.calls) == 1
    assert origin.settlement.event.cost_origin == "reported"
    assert follower.settlement.event.cost_origin == "reuse"
    assert follower.settlement.event.origin_event_id == origin.settlement.event.event_id
    assert follower.usage.prompt_tokens == 12 and follower.usage.completion_tokens == 4
    assert follower.model == "fixture-model" and follower.provider == "actual-provider"
    assert follower.request_id == "actual-request"
    assert follower.response_headers == {"source": "actual"}
    assert follower.raw["source"] == "actual"
    rows = FileBudgetLedger(tmp_path / "follower.json").snapshot().producer_settlements
    assert len(rows) == 2 and {row.cost_origin for row in rows.values()} == {"reported", "reuse"}


def test_scope_close_refuses_a_late_begin_without_waiting_for_worker(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import contextvars
    import threading
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    path = tmp_path / "late-begin.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _fixture_binding("late-begin")
    entered, release = threading.Event(), threading.Event()
    original = middleware.begin_producer_event_safe

    def paused_begin(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(middleware, "begin_producer_event_safe", paused_begin)
    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            with middleware.producer_run_binding_scope(binding, control_job_attempt=9):
                with _gateway_cache_reuse_scope(
                    authorizer=_Owner(),
                    principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
                    context=_context(),
                    cache=InMemoryPromptCache(),
                    run_id=binding.run_id,
                    settlement_store=middleware,
                    reuse_guard=lambda operation: operation(),
                ):
                    client = create_traced_gateway_client(
                        model_name="fixture",
                        config=GatewayLLMConfig(
                            base_url="http://fixture.invalid", api_key="fixture"
                        ),
                    )
                    assert client is not None
                    context = contextvars.copy_context()
                    producing = executor.submit(
                        context.run,
                        lambda: asyncio.run(client.generate(user="stable", temperature=0)),
                    )
                    assert entered.wait(3)
            # Closure must return before the blocked worker is released.
            assert not producing.done()
            assert not client.unwrap().calls
        finally:
            release.set()
        with pytest.raises(LLMSettlementOwnershipError, match="scope_closed"):
            producing.result(timeout=3)
    # A late durable begin may remain pending. It never creates a physical call
    # or a falsely committed owned event after the binding was closed.
    rows = FileBudgetLedger(path).snapshot().producer_settlements.values()
    assert len(rows) == 1 and all(row.status == "pending" for row in rows)
    assert not client.unwrap().calls
