"""Scoped factory calls fence unresolved producer cost before another dispatch."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from polisyos.core.llm import LLMSettlementOwnershipError
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    BudgetLedgerSettlementOutcomeUnknownError,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    _gateway_cache_reuse_scope,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReusePrincipal,
    InMemoryPromptCache,
)
from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _owner(run: str) -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id=run,
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="dev",
        control_job_id=f"job-{run}",
    )


@contextmanager
def _runtime_scope(
    middleware: BudgetMiddleware, binding: BudgetLedgerProducerRunBinding, *, attempt: int = 1
) -> Iterator[None]:
    with (
        middleware.producer_run_binding_scope(binding, control_job_attempt=attempt),
        _gateway_cache_reuse_scope(
            authorizer=None,
            principal=None,
            context=None,
            cache=None,
            run_id=binding.run_id,
            settlement_store=middleware,
            reuse_guard=lambda operation: operation(),
            validate_admission=lambda: None,
        ),
    ):
        yield


def _client(*, cache: bool = False):
    client = create_traced_gateway_client(
        model_name="fixture-model",
        config=GatewayLLMConfig(
            base_url="http://127.0.0.1:9/v1",
            api_key="fixture-key",
            cache_maxsize=128 if cache else 0,
            enable_prompt_sanitizer=False,
        ),
    )
    assert client is not None
    return client


def _reply(cost: float) -> GatewayLLMResponse:
    return GatewayLLMResponse(
        content="provider answer",
        usage=GatewayUsage(prompt_tokens=2, completion_tokens=1, cost_usd=cost),
        model="fixture-model",
        provider="simulated_gateway",
    )


@pytest.mark.asyncio
async def test_failed_settlement_fences_fresh_scoped_factory_until_exact_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        return _reply(0.02)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    original_settle = middleware.settle_producer_event_safe

    def unavailable(*_args, **_kwargs):
        raise OSError("settlement unavailable")

    with _runtime_scope(middleware, binding):
        first_client = _client()
        monkeypatch.setattr(middleware, "settle_producer_event_safe", unavailable)
        response = await first_client.generate(user="first")
        event = response.settlement.event
        assert response.content == "provider answer"
        assert response.settlement.ack.status == "unknown"
        assert event.amount == Decimal("0.02")
        monkeypatch.setattr(middleware, "settle_producer_event_safe", original_settle)

        # A newly created client must not lose the same run's pending cost.
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
            await _client().generate(user="must not dispatch")
        assert calls == ["first"]
        pending = FileBudgetLedger(path).snapshot().producer_settlements[event.event_id]
        assert pending.status == "pending"
        assert pending.amount is None

        settled = original_settle(
            event.event_id,
            event.request_digest,
            event.payload_digest,
            key=f"nl-run:{binding.run_id}",
            model=event.model,
            provider=event.provider,
            amount=event.amount,
            cost_origin=event.cost_origin,
        )
        assert settled.status == "committed"
        await _client().generate(user="after reconciliation")

    snapshot = FileBudgetLedger(path).snapshot()
    assert calls == ["first", "after reconciliation"]
    assert snapshot.state.spent[f"nl-run:{binding.run_id}"] == Decimal("0.04")
    assert len(snapshot.spend_receipts) == 2


@pytest.mark.asyncio
async def test_terminal_unknown_cost_blocks_same_run_even_after_owner_reopens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        return _reply(-1.0 if user == "unknown" else 0.02)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    with _runtime_scope(middleware, binding):
        response = await _client().generate(user="unknown")
        assert response.settlement.ack.status == "unknown"
        assert response.settlement.event.amount is None

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    with _runtime_scope(reopened, binding):
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
            await _client().generate(user="blocked after restart")
    with _runtime_scope(reopened, _owner("run-b")):
        await _client().generate(user="other run")

    snapshot = FileBudgetLedger(path).snapshot()
    assert calls == ["unknown", "other run"]
    assert snapshot.state.spent.get(f"nl-run:{binding.run_id}") is None
    assert snapshot.state.spent["nl-run:run-b"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_live_shielded_attempt_allows_another_same_owner_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    entered, release = asyncio.Event(), asyncio.Event()
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        if user == "first":
            entered.set()
            await release.wait()
        return _reply(0.02)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    with _runtime_scope(middleware, _owner("run-a")):
        first = asyncio.create_task(_client().generate(user="first"))
        await entered.wait()
        first.cancel()
        try:
            await asyncio.sleep(0)
            assert not first.done()
            await _client().generate(user="second while first is live")
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await first

    snapshot = FileBudgetLedger(path).snapshot()
    assert calls == ["first", "second while first is live"]
    assert {record.status for record in snapshot.producer_settlements.values()} == {"committed"}
    assert snapshot.state.spent["nl-run:run-a"] == Decimal("0.04")


@pytest.mark.asyncio
async def test_verified_reuse_preserves_unknown_origin_without_a_new_physical_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        return GatewayLLMResponse(
            content="provider answer",
            usage=GatewayUsage(),
            model="fixture-model",
            provider="simulated_gateway",
        )

    class Owner:
        def authorize_reuse(self, request):
            assert request.evidence[0].content == b"materialized fixture"
            return CacheReuseDecision(
                issuer="fixture-owner",
                epoch="epoch-1",
                actor_id=request.actor_id,
                tenant=request.tenant,
                scope=request.scope,
                purpose=request.purpose,
                model=request.model,
                parameters_digest=request.parameters_digest,
                evidence=request.evidence,
            )

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    content = b"materialized fixture"
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    with (
        middleware.producer_run_binding_scope(binding, control_job_attempt=1),
        _gateway_cache_reuse_scope(
            authorizer=Owner(),
            principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
            context={
                "tenant": "tenant-a",
                "scope": "tenant-a/cell-a",
                "purpose": "fixture-candidate",
                "snapshot": {
                    "ref": digest,
                    "version": "fixture-v1",
                    "immutable": True,
                    "content": content,
                    "content_hash": digest,
                },
            },
            cache=InMemoryPromptCache(),
            run_id=binding.run_id,
            settlement_store=middleware,
            reuse_guard=lambda operation: operation(),
            validate_admission=lambda: None,
        ),
    ):
        client = _client(cache=True)
        first = await client.generate(user="same", temperature=0)
        assert first.settlement.event.amount is None
        assert first.settlement.ack.status == "unknown"
        reused = await client.generate(user="same", temperature=0)
        assert reused.settlement.event.cost_origin == "reuse"
        assert reused.settlement.event.amount == Decimal(0)
        assert reused.settlement.event.origin_event_id == first.settlement.event.event_id
        assert reused.settlement.ack.status == "committed"
        reuse_event = reused.settlement.event
        before_forgery = path.read_bytes()
        for offered_event, offered_request in (
            ("different-event", reuse_event.request_digest),
            (reuse_event.event_id, "a" * 64),
        ):
            with pytest.raises(LLMSettlementOwnershipError, match="reuse_proof_not_established"):
                with middleware._scoped_producer_admission(
                    required=True,
                    reuse_session=client._cache_settlement_session,
                    reuse_response=reused.response,
                    reuse_event_id=offered_event,
                    reuse_request_digest=offered_request,
                ):
                    raise AssertionError("an unbound proof must not be admitted")
            assert path.read_bytes() == before_forgery
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
            await client.generate(user="different physical input", temperature=0)

    snapshot = FileBudgetLedger(path).snapshot()
    assert calls == ["same"]
    assert snapshot.state.spent.get("nl-run:run-a", Decimal(0)) == Decimal(0)
    assert snapshot.producer_settlements[first.settlement.event.event_id].amount is None


@pytest.mark.asyncio
async def test_old_live_attempt_does_not_authorize_a_new_takeover_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    entered, release = asyncio.Event(), asyncio.Event()
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        if user == "old attempt":
            entered.set()
            await release.wait()
        return _reply(0.02)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    with _runtime_scope(middleware, binding, attempt=1):
        old = asyncio.create_task(_client().generate(user="old attempt"))
        await entered.wait()
        try:
            with _runtime_scope(middleware, binding, attempt=2):
                with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
                    await _client().generate(user="premature takeover")
            assert calls == ["old attempt"]
        finally:
            release.set()
            await old

    with _runtime_scope(middleware, binding, attempt=2):
        await _client().generate(user="settled takeover")
    assert calls == ["old attempt", "settled takeover"]
    snapshot = FileBudgetLedger(path).snapshot()
    assert {row.control_job_attempt for row in snapshot.producer_settlements.values()} == {1, 2}
    assert snapshot.state.spent["nl-run:run-a"] == Decimal("0.04")


def test_failed_settlement_completion_does_not_wait_for_other_ledger_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    provider_entered = threading.Event()
    provider_release = threading.Event()
    second_begin_entered = threading.Event()
    second_begin_release = threading.Event()
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        provider_entered.set()
        assert provider_release.wait(5)
        return _reply(0.02)

    def unavailable(*_args, **_kwargs):
        raise OSError("settlement unavailable")

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    ledger = FileBudgetLedger(path)
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    monkeypatch.setattr(middleware, "settle_producer_event_safe", unavailable)
    monkeypatch.setattr(middleware, "resolve_producer_event_safe", lambda _event: None)
    with _runtime_scope(middleware, _owner("run-a")), ThreadPoolExecutor(max_workers=2) as pool:
        first_client, second_client = _client(), _client()
        first_context, second_context = contextvars.copy_context(), contextvars.copy_context()
        first = pool.submit(
            first_context.run, lambda: asyncio.run(first_client.generate(user="first"))
        )
        assert provider_entered.wait(5)
        original_begin = ledger._begin_producer_event

        def blocked_begin(*args, **kwargs):
            second_begin_entered.set()
            assert second_begin_release.wait(5)
            return original_begin(*args, **kwargs)

        monkeypatch.setattr(ledger, "_begin_producer_event", blocked_begin)
        second = pool.submit(
            second_context.run, lambda: asyncio.run(second_client.generate(user="second"))
        )
        try:
            assert second_begin_entered.wait(5)
            provider_release.set()
            response = first.result(timeout=3)
            assert response.settlement.ack.status == "unknown"
        finally:
            provider_release.set()
            second_begin_release.set()
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
            second.result(timeout=5)

    assert calls == ["first"]
    pending = tuple(FileBudgetLedger(path).snapshot().producer_settlements.values())
    assert len(pending) == 1 and pending[0].status == "pending"


@pytest.mark.asyncio
async def test_attributed_provider_preflight_cannot_bypass_unknown_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.orchestration.llm import provider_verification

    calls: list[str] = []
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")

    async def unknown_cost(_self, *, user=None, **_kwargs):
        calls.append(user)
        return _reply(-1.0)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", unknown_cost)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    with _runtime_scope(middleware, binding):
        first = await _client().generate(user="unknown first cost")
    assert first.settlement.event.amount is None

    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE")
    monkeypatch.setattr(provider_verification, "_PREFLIGHT_CACHE", {})

    async def fetch(url, **_kwargs):
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/models"):
            return {"data": [{"id": "fixture-model"}]}
        if url.endswith("/api/models/capabilities"):
            return {"models": [{"model": "fixture-model"}]}
        if url.endswith("/api/pricing"):
            return {"fixture-model": {"per_token": 0.0}}
        raise AssertionError(url)

    class Provider:
        async def generate(self, **_kwargs):
            calls.append("preflight dispatched")
            return _reply(0.02)

        async def aclose(self):
            return None

    report = await provider_verification.run_provider_preflight(
        models=["fixture-model"],
        base_url="https://proxy.gonka.gg/v1",
        provider="fixture-provider",
        api_key="sk-test-provider-key",
        fetch_json=fetch,
        client_factory=lambda **_kwargs: Provider(),
        producer_settlement_store=middleware,
        producer_run_binding=binding,
        producer_budget_key=f"nl-run:{binding.run_id}",
        pre_admission_attempt_id="a" * 32,
        require_producer_settlement=True,
    )
    assert report.status == "unknown"
    assert report.producer_completion_observation == "unavailable"
    assert calls == ["unknown first cost"]
    assert len(FileBudgetLedger(path).snapshot().producer_settlements) == 1


def test_independent_ledger_owners_cannot_both_admit_unproven_live_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    path = tmp_path / "ledger.json"
    first_store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    second_store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    start = threading.Barrier(2)
    provider_entered, provider_release = threading.Event(), threading.Event()
    errors: queue.Queue[Exception] = queue.Queue()
    calls: list[str] = []

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        provider_entered.set()
        assert provider_release.wait(5)
        return _reply(0.02)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)

    def run(store: BudgetMiddleware, label: str):
        try:
            with _runtime_scope(store, binding):
                client = _client()
                start.wait(timeout=5)
                return asyncio.run(client.generate(user=label))
        except Exception as exc:
            errors.put(exc)
            raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = (pool.submit(run, first_store, "first"), pool.submit(run, second_store, "second"))
        try:
            assert provider_entered.wait(5)
            denied = errors.get(timeout=5)
            assert isinstance(denied, BudgetLedgerSettlementOutcomeUnknownError)
        finally:
            provider_release.set()
        for result in results:
            try:
                result.result(timeout=5)
            except BudgetLedgerSettlementOutcomeUnknownError:
                pass

    snapshot = FileBudgetLedger(path).snapshot()
    assert len(calls) == 1
    assert len(snapshot.producer_settlements) == 1
    assert snapshot.state.spent["nl-run:run-a"] == Decimal("0.02")


def test_live_verified_reuse_receipt_does_not_block_other_physical_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    calls: list[str] = []
    reuse_entered, reuse_release = threading.Event(), threading.Event()

    async def complete(_self, *, user=None, **_kwargs):
        calls.append(user)
        return _reply(0.02)

    class Owner:
        def authorize_reuse(self, request):
            assert request.evidence[0].content == b"materialized fixture"
            return CacheReuseDecision(
                issuer="fixture-owner",
                epoch="epoch-1",
                actor_id=request.actor_id,
                tenant=request.tenant,
                scope=request.scope,
                purpose=request.purpose,
                model=request.model,
                parameters_digest=request.parameters_digest,
                evidence=request.evidence,
            )

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", complete)
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    content = b"materialized fixture"
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    original_settle = middleware.settle_producer_event_safe

    def pause_reuse(*args, **kwargs):
        if kwargs.get("cost_origin") == "reuse":
            reuse_entered.set()
            assert reuse_release.wait(5)
        return original_settle(*args, **kwargs)

    with (
        middleware.producer_run_binding_scope(binding, control_job_attempt=1),
        _gateway_cache_reuse_scope(
            authorizer=Owner(),
            principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
            context={
                "tenant": "tenant-a",
                "scope": "tenant-a/cell-a",
                "purpose": "fixture-candidate",
                "snapshot": {
                    "ref": digest,
                    "version": "fixture-v1",
                    "immutable": True,
                    "content": content,
                    "content_hash": digest,
                },
            },
            cache=InMemoryPromptCache(),
            run_id=binding.run_id,
            settlement_store=middleware,
            reuse_guard=lambda operation: operation(),
            validate_admission=lambda: None,
        ),
    ):
        client = _client(cache=True)
        first = asyncio.run(client.generate(user="same", temperature=0))
        assert first.settlement.ack.status == "committed"
        monkeypatch.setattr(middleware, "settle_producer_event_safe", pause_reuse)
        context = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            reuse = pool.submit(
                context.run, lambda: asyncio.run(client.generate(user="same", temperature=0))
            )
            try:
                assert reuse_entered.wait(5)
                second = asyncio.run(client.generate(user="different", temperature=0))
                assert second.settlement.ack.status == "committed"
            finally:
                reuse_release.set()
            hit = reuse.result(timeout=5)
            assert hit.settlement.event.cost_origin == "reuse"

    snapshot = FileBudgetLedger(path).snapshot()
    assert calls == ["same", "different"]
    assert snapshot.state.spent["nl-run:run-a"] == Decimal("0.04")
    assert len(snapshot.producer_settlements) == 3


def test_reuse_admission_refuses_a_forged_nonphysical_claim(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    binding = _owner("run-a")
    with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
        with pytest.raises(LLMSettlementOwnershipError, match="reuse_proof_not_established"):
            with middleware._scoped_producer_admission(
                required=True,
                reuse_response=object(),
                reuse_event_id="forged",
                reuse_request_digest="a" * 64,
            ):
                middleware.begin_producer_event_safe(
                    "forged",
                    "a" * 64,
                    key="nl-run:run-a",
                    model="fixture-model",
                    provider="fixture-provider",
                )
    assert not FileBudgetLedger(path).snapshot().producer_settlements
