"""Producer completion and authority falsifiers on the canonical LLM stack."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import contextmanager, nullcontext
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReuseDeniedError,
    CachingLLMClient,
    InMemoryPromptCache,
)


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
            content="provider value",
            model="e02",
            provider="synthetic",
            request_id=f"request-{self.calls}",
            usage=GatewayUsage(prompt_tokens=7, completion_tokens=3, cost_usd=0.02),
        )


def _stack(gateway: _Gateway, events: list, *, tracer=None):
    cache = CachingLLMClient(gateway, cache=InMemoryPromptCache(), model="e02")
    traced = TracedLLMClient(
        cache,
        model_name="e02",
        tracer=tracer or _Tracer(),
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
    metadata = {
        "cache_reuse": {
            "snapshot": {
                "ref": "artifact://evidence",
                "version": "v1",
                "immutable": True,
                "content": content,
                "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
            },
            "permission": {"allowed": True, "tenant": "tenant-a", "scope": "scope-a"},
            "tenant": "tenant-a",
            "scope": "scope-a",
        }
    }
    cache = CachingLLMClient(gateway, cache=InMemoryPromptCache(), model="e02")
    await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
    await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
    assert gateway.calls == 2


def _durable_stack(tmp_path, *, gateway=None, client=None, name="budget"):
    gateway = gateway or _Gateway()
    events = []
    cache, traced = _stack(gateway, events)
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(tmp_path / f"{name}.json", ledger_id=f"ledger:{name}"),
    )
    enforcer = LLMBudgetEnforcer(
        client=client or traced,
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="e02",
        run_id="run-e02",
    )
    return gateway, cache, enforcer, middleware, events


@pytest.mark.asyncio
async def test_cancelled_initiator_settles_actual_ledger_before_cache_publication(tmp_path):
    gateway, cache, enforcer, middleware, events = _durable_stack(tmp_path)
    caller = asyncio.create_task(
        enforcer.generate(user="durable", temperature=0.0, _prompt_tokens_estimate=1)
    )
    await gateway.started.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert middleware.budget_state.reserved["run"] > 0
    gateway.release.set()
    await asyncio.gather(*list(enforcer._owned_calls))
    assert middleware.budget_state.spent["run"] == Decimal("0.02")
    result = await enforcer.generate(user="durable", temperature=0.0, _prompt_tokens_estimate=1)
    assert result.content == "provider value"
    assert gateway.calls == 1
    assert len([event for event in events if event["provider_call"]]) == 1
    assert cache._cache.size == 1
    charged = next(event for event in events if event["provider_call"])
    # Reopen the actual filesystem consumer and resolve the producer-bound receipt.
    reopened = FileBudgetLedger(tmp_path / "budget.json", ledger_id="ledger:budget")
    event_id, digest = (
        enforcer._ledger_event_identity(charged["producer_event"], "run")
        if ("producer_event" in charged)
        else (None, None)
    )
    settled = producer_settlement(result)
    assert settled is not None
    origin = settled.event.origin_event_id
    assert origin is not None
    key_id = f"{origin}:budget:{hashlib.sha256(b'run').hexdigest()}"
    receipt = reopened.resolve_spend(key_id)
    assert receipt.amount == Decimal("0.02")
    assert reopened.load().reserved["run"] == 0
    assert reopened.load().spent["run"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_lost_actual_ack_is_unknown_and_blocks_reuse_until_reconciled(tmp_path, monkeypatch):
    gateway, cache, enforcer, middleware, _ = _durable_stack(tmp_path)
    gateway.release.set()
    actual_settle = middleware.settle_spend_safe

    def lose_ack(*args, **kwargs):
        actual_settle(*args, **kwargs)
        raise OSError("durable publication succeeded; ACK transport unavailable")

    monkeypatch.setattr(middleware, "settle_spend_safe", lose_ack)
    with pytest.raises(LLMAccountingError) as failure:
        await enforcer.generate(user="unknown", temperature=0.0, _prompt_tokens_estimate=1)
    event = failure.value.event["producer_event"]
    assert failure.value.event["settlement_status"] == "unknown"
    assert middleware.budget_state.spent["run"] == Decimal("0.02")
    assert middleware.budget_state.reserved["run"] > 0
    assert cache._cache.size == 0
    with pytest.raises(LLMAccountingError):
        await enforcer.generate(user="unknown", temperature=0.0, _prompt_tokens_estimate=1)
    assert gateway.calls == 1
    monkeypatch.setattr(middleware, "settle_spend_safe", actual_settle)
    ack = enforcer.reconcile_settlement(event)
    assert ack.status == "committed" and ack.durability == "ledger"
    assert (
        actual_settle(
            ack.receipts[0].event_id,
            "run",
            Decimal("0.02"),
            provider="synthetic",
            payload_digest=ack.receipts[0].payload_digest,
        )
        == ack.receipts[0]
    )
    assert middleware.budget_state.spent["run"] == Decimal("0.02")
    assert middleware.budget_state.reserved["run"] == 0


@pytest.mark.asyncio
async def test_different_actual_budget_owners_cannot_join_first_owners_flight(tmp_path):
    gateway = _Gateway()
    cache, traced = _stack(gateway, [])
    _, _, first, first_budget, _ = _durable_stack(tmp_path, client=traced, name="first")
    _, _, second, second_budget, _ = _durable_stack(tmp_path, client=traced, name="second")
    requests = [
        asyncio.create_task(owner.generate(user="same", temperature=0.0, _prompt_tokens_estimate=1))
        for owner in (first, second)
    ]
    await gateway.started.wait()
    # Wait on the actual owned task queue, then release physical producer work.
    await asyncio.sleep(0)
    gateway.release.set()
    await asyncio.gather(*requests)
    assert gateway.calls == 2
    assert first_budget.budget_state.spent["run"] == Decimal("0.02")
    assert second_budget.budget_state.spent["run"] == Decimal("0.02")
    assert cache._cache.size == 2


@contextmanager
def _principal(actor="spiffe://local/e02/owner", tenant="tenant-a"):
    token = set_current_access_scope(
        AccessScope.for_service(tenant_id=tenant, cell_id="cell-a", spiffe_id=actor)
    )
    try:
        with tenant_scope(None, tenant_id=tenant, cell_id="cell-a"):
            yield
    finally:
        reset_current_access_scope(token)


class _DeploymentReuseOwner:
    """Versioned local owner policy, independently backed by actual CAS bytes."""

    def __init__(self, store, ref, content):
        self.store, self.ref, self.content = store, ref, content
        self.epoch = "policy-1"
        self.granted_actor = "spiffe://local/e02/owner"
        self.allowed = True
        self.decisions = []

    def authorize_reuse(self, request):
        self.decisions.append(request)
        if (
            not self.allowed
            or request.actor_id != self.granted_actor
            or request.tenant != "tenant-a"
            or request.scope != "scope-a"
            or request.purpose != "llm_snapshot_reuse"
            or len(request.evidence) != 1
        ):
            return None
        evidence = request.evidence[0]
        if evidence.ref != str(self.ref.artifact_id) or evidence.version != "snapshot-v1":
            return None
        actual = self.store.get_bytes(self.ref)
        if (
            actual != self.content
            or evidence.content != actual
            or evidence.content_hash != "sha256:" + hashlib.sha256(actual).hexdigest()
        ):
            return None
        return CacheReuseDecision(
            issuer="deployment-owner:local-fixture",
            epoch=self.epoch,
            actor_id=request.actor_id,
            tenant=request.tenant,
            scope=request.scope,
            purpose=request.purpose,
            model=request.model,
            parameters_digest=request.parameters_digest,
            evidence=request.evidence,
        )


def _reuse_fixture(tmp_path):
    content = b"actual owner-pinned immutable evidence"
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    ref = store.put_bytes(content, PutOptions(kind="e02.reuse", media_type="text/plain"))
    owner = _DeploymentReuseOwner(store, ref, content)
    metadata = {
        "cache_reuse": {
            "tenant": "tenant-a",
            "scope": "scope-a",
            "snapshot": {
                "ref": str(ref.artifact_id),
                "version": "snapshot-v1",
                "immutable": True,
                "content": content,
                "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
            },
        }
    }
    return owner, metadata


@pytest.mark.asyncio
async def test_actual_owner_permission_rechecked_actor_epoch_and_exact_cas_ref(tmp_path):
    with _principal():
        owner, metadata = _reuse_fixture(tmp_path)
        gateway = _Gateway()
        gateway.release.set()
        cache = CachingLLMClient(
            gateway, cache=InMemoryPromptCache(), model="e02", reuse_authorizer=owner
        )
        await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 1
        owner.epoch = "policy-2"
        await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 2
        owner.allowed = False
        await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 3
        owner.allowed = True
        with _principal(actor="spiffe://local/e02/foreign"):
            await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 4
        metadata["cache_reuse"]["snapshot"]["ref"] = "artifact://readable-but-not-granted"
        await cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 5


@pytest.mark.asyncio
async def test_owner_revocation_while_follower_waits_prevents_shared_consumption(tmp_path):
    with _principal():
        owner, metadata = _reuse_fixture(tmp_path)
        gateway = _Gateway()
        cache = CachingLLMClient(
            gateway, cache=InMemoryPromptCache(), model="e02", reuse_authorizer=owner
        )
        caller = asyncio.create_task(
            cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        )
        await gateway.started.wait()
        follower = asyncio.create_task(
            cache.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        )
        await asyncio.sleep(0)
        owner.allowed = False
        gateway.release.set()
        assert (await caller).content == "provider value"
        with pytest.raises(CacheReuseDeniedError):
            await follower
        assert gateway.calls == 1 and cache._cache.size == 0


@pytest.mark.asyncio
async def test_canonical_factory_consumes_actual_owner_decision(tmp_path, monkeypatch):
    with _principal():
        owner, metadata = _reuse_fixture(tmp_path)
        gateway = _Gateway()
        gateway.release.set()
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.llm.factory.GatewayLLMClient",
            lambda **kwargs: gateway,
        )
        client = create_traced_gateway_client(
            model_name="e02",
            cache_reuse_authorizer=owner,
            config=GatewayLLMConfig(
                base_url="https://synthetic.invalid",
                api_key="fixture",
                enable_prompt_sanitizer=False,
            ),
            tracer=_Tracer(),
            metrics=SimpleNamespace(record_llm_call=lambda **kw: None),
        )
        await client.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        await client.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 1 and len(owner.decisions) >= 3
        owner.allowed = False
        await client.generate(user="https://source.invalid", metadata=metadata, temperature=0.0)
        assert gateway.calls == 2


@pytest.mark.asyncio
async def test_ainvoke_cancellation_and_sync_invoke_use_exact_durable_owner(tmp_path):
    gateway = _Gateway()

    class InvokeProvider:
        async def ainvoke(self, prompt, **kwargs):
            return await gateway.generate(user=prompt, **kwargs)

        def invoke(self, prompt, **kwargs):
            return GatewayLLMResponse(
                content=prompt, model="e02", provider="synthetic", usage=GatewayUsage(cost_usd=0.03)
            )

    traced = TracedLLMClient(
        InvokeProvider(),
        model_name="e02",
        tracer=_Tracer(),
        metrics=SimpleNamespace(record_llm_call=lambda **kw: None),
    )
    _, _, enforcer, middleware, _ = _durable_stack(tmp_path, client=traced)
    caller = asyncio.create_task(enforcer.ainvoke("owned invoke", _prompt_tokens_estimate=1))
    await gateway.started.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    gateway.release.set()
    results = await asyncio.gather(*list(enforcer._owned_calls))
    assert producer_settlement(results[0]).ack.durability == "ledger"
    result = enforcer.invoke("sync invoke", _prompt_tokens_estimate=1)
    assert producer_settlement(result).ack.durability == "ledger"
    assert middleware.budget_state.spent["run"] == Decimal("0.05")
    assert middleware.budget_state.reserved["run"] == 0
