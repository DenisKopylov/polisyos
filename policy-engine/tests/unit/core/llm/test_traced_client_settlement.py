"""Provider outcomes remain durable through the traced-client boundary."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.llm.settlement import (
    LLMProducerEvent,
    LLMSettledResponse,
    LLMSettlementIntegrityError,
    LLMSettlementOwnershipError,
)
from polisyos.core.llm.traced_client import TracedLLMClient, _settlement_ack
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)


class _Span:
    def set_attribute(self, _name: str, _value: object) -> None:
        pass

    def set_status(self, _status: object) -> None:
        pass

    def record_exception(self, _error: BaseException) -> None:
        pass


class _Tracer:
    @contextmanager
    def start_as_current_span(self, *_args: object, **_kwargs: object):
        yield _Span()


class _Metrics:
    def record_llm_call(self, **_kwargs: object) -> None:
        pass


def test_malformed_settlement_discriminators_fail_closed() -> None:
    event = LLMProducerEvent(
        event_id="event-1",
        request_digest="request-digest",
        response_digest="response-digest",
        model="configured-model",
        provider="configured-route",
        amount=Decimal("0.25"),
        cost_origin="reported",
    )

    for raw_status in ([], {}, 3, True, None, "malformed"):
        ack = _settlement_ack(
            event,
            {
                "event_id": event.event_id,
                "payload_digest": event.payload_digest,
                "status": raw_status,
                "durability": [],
                "receipts": {},
            },
            required=True,
        )
        assert ack.status == "unknown"
        assert ack.durability == "none"
        assert ack.receipts == ()


@pytest.mark.parametrize("origin_event_id", [None, ""])
def test_reuse_producer_event_requires_a_nonempty_origin_id(
    origin_event_id: str | None,
) -> None:
    with pytest.raises(ValueError, match="reuse events require an origin event ID"):
        LLMProducerEvent(
            event_id="reuse-event",
            request_digest="request-digest",
            response_digest="response-digest",
            model="configured-model",
            provider="configured-route",
            amount=Decimal(0),
            cost_origin="reuse",
            kind="reuse",
            origin_event_id=origin_event_id,
        )


class _Provider:
    provider = "fixture"
    model = "fixture-model"

    def __init__(self, *, cost: float | None, blocked: bool = False) -> None:
        self.cost = cost
        self.calls = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        if not blocked:
            self.release.set()

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, *_args: object, **_kwargs: object) -> GatewayLLMResponse:
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return GatewayLLMResponse(
            content="answer",
            usage=GatewayUsage(prompt_tokens=2, completion_tokens=1, cost_usd=self.cost),
            model=self.model,
            provider=self.provider,
            request_id="provider-request-1",
        )


def _middleware(path: Path) -> BudgetMiddleware:
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    return BudgetMiddleware(state, ledger=FileBudgetLedger(path))


def test_producer_request_digest_binds_current_tenant_and_cell() -> None:
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        first = TracedLLMClient._request_digest((), {"user": "policy question"})
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
        second = TracedLLMClient._request_digest((), {"user": "policy question"})

    assert first != second


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cost", "expected_origin", "expected_amount"),
    [(0.0, "reported", Decimal("0")), (-1.0, "unknown", None)],
)
async def test_traced_provider_settlement_preserves_zero_and_invalid_cost(
    tmp_path: Path,
    cost: float,
    expected_origin: str,
    expected_amount: Decimal | None,
) -> None:
    middleware = _middleware(tmp_path / "ledger.json")
    events: list[dict[str, object]] = []
    client = TracedLLMClient(
        _Provider(cost=cost),
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    response = await client.generate(user="policy question")

    event = response.settlement.event
    stored = (
        FileBudgetLedger(tmp_path / "ledger.json").snapshot().producer_settlements[event.event_id]
    )
    assert event.cost_origin == expected_origin
    assert event.amount == expected_amount
    assert response.settlement.ack.status == (
        "committed" if expected_amount is not None else "unknown"
    )
    assert stored.status == response.settlement.ack.status
    assert stored.amount == expected_amount
    observed = [item for item in events if item.get("event_id") == event.event_id]
    assert len(observed) == 1
    assert observed[0]["cost_origin"] == expected_origin
    assert observed[0]["amount"] == expected_amount
    assert observed[0]["settlement_status"] == response.settlement.ack.status
    assert middleware.budget_state.spent.get("run", Decimal(0)) == Decimal(0)


@pytest.mark.asyncio
async def test_cancelled_caller_waits_for_provider_settlement_before_exiting(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    provider = _Provider(cost=0.02, blocked=True)
    events: list[dict[str, object]] = []
    client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    task = asyncio.create_task(client.generate(user="policy question"))
    await provider.entered.wait()
    pending = FileBudgetLedger(ledger_path).snapshot().producer_settlements
    assert len(pending) == 1
    assert next(iter(pending.values())).status == "pending"

    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    provider.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    settled = FileBudgetLedger(ledger_path).snapshot()
    assert len(settled.producer_settlements) == 1
    record = next(iter(settled.producer_settlements.values()))
    assert record.status == "committed"
    assert record.cost_origin == "reported"
    assert record.amount == Decimal("0.02")
    assert settled.state.spent["run"] == Decimal("0.02")
    assert len(settled.spend_receipts) == 1
    observed = [item for item in events if item.get("event_id") == record.event_id]
    assert len(observed) == 1
    assert observed[0]["cost_origin"] == "reported"
    assert observed[0]["settlement_status"] == "committed"
    assert observed[0]["durability"] == "ledger"


@pytest.mark.asyncio
async def test_missing_provider_cost_is_an_estimate_in_durable_observation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    events: list[dict[str, object]] = []
    client = TracedLLMClient(
        _Provider(cost=None),
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    response = await client.generate(user="policy question")

    record = (
        FileBudgetLedger(ledger_path)
        .snapshot()
        .producer_settlements[response.settlement.event.event_id]
    )
    assert record.cost_origin == "estimated"
    assert record.amount == Decimal("0.00005")
    assert record.status == "committed"
    assert len(events) == 1
    assert events[0]["cost_origin"] == "estimated"
    assert events[0]["amount"] == Decimal("0.00005")
    assert events[0]["estimated_cost_usd"] == pytest.approx(0.00005)


@pytest.mark.asyncio
async def test_provider_self_labels_cannot_rebind_durable_route_or_estimate_model(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    events: list[dict[str, object]] = []
    provider = _Provider(cost=None)
    provider.provider = "response-declared-provider"
    provider.model = "response-declared-model"
    client = TracedLLMClient(
        provider,
        model_name="configured-model",
        provider_name="configured-logical-route",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    response = await client.generate(user="policy question")

    event = response.settlement.event
    record = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
    assert event.model == record.model == "configured-model"
    assert event.provider == record.provider == "configured-logical-route"
    assert event.cost_origin == record.cost_origin == "estimated"
    assert event.amount == record.amount == Decimal("0.00005")
    assert events[0]["model"] == "configured-model"
    assert events[0]["provider"] == "configured-logical-route"


@pytest.mark.asyncio
async def test_response_declared_labels_do_not_change_estimate_basis_or_pinned_identity(
    tmp_path: Path,
) -> None:
    outcomes: list[tuple[str, str, Decimal | None]] = []
    for index, (declared_model, declared_provider) in enumerate(
        (("spoof-model-a", "spoof-provider-a"), ("spoof-model-b", "spoof-provider-b"))
    ):
        ledger_path = tmp_path / f"ledger-{index}.json"
        provider = _Provider(cost=None)
        provider.model = declared_model
        provider.provider = declared_provider
        client = TracedLLMClient(
            provider,
            model_name="configured-model",
            provider_name="configured-logical-route",
            tracer=_Tracer(),
            metrics=_Metrics(),
            producer_settlement_store=_middleware(ledger_path),
        )

        response = await client.generate(user="same selected request")
        outcomes.append(
            (
                response.settlement.event.model,
                response.settlement.event.provider,
                response.settlement.event.amount,
            )
        )

    assert outcomes == [
        ("configured-model", "configured-logical-route", Decimal("0.00005")),
        ("configured-model", "configured-logical-route", Decimal("0.00005")),
    ]


@pytest.mark.asyncio
async def test_lost_settlement_ack_resolves_exact_durable_event(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    events: list[dict[str, object]] = []

    class _LostAckStore:
        def begin_producer_event_safe(self, *args: object, **kwargs: object):
            return middleware.begin_producer_event_safe(*args, **kwargs)

        def settle_producer_event_safe(self, *args: object, **kwargs: object):
            middleware.settle_producer_event_safe(*args, **kwargs)
            raise OSError("settlement acknowledgment lost after durable write")

        def resolve_producer_event_safe(self, event_id: str):
            return middleware.resolve_producer_event_safe(event_id)

    client = TracedLLMClient(
        _Provider(cost=0.02),
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=_LostAckStore(),
    )

    response = await client.generate(user="policy question")

    event = response.settlement.event
    stored = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
    assert response.settlement.ack.status == "committed"
    assert response.settlement.ack.durability == "ledger"
    assert response.settlement.ack.receipts == (event.event_id,)
    assert stored.payload_digest == event.payload_digest
    assert stored.amount == event.amount == Decimal("0.02")
    assert len(events) == 1
    assert events[0]["durability"] == "ledger"
    assert events[0]["settlement_status"] == "committed"


@pytest.mark.asyncio
async def test_failed_settlement_keeps_exact_durable_begin_pending(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    events: list[dict[str, object]] = []

    class _FailedSettlementStore:
        def begin_producer_event_safe(self, *args: object, **kwargs: object):
            return middleware.begin_producer_event_safe(*args, **kwargs)

        def settle_producer_event_safe(self, *_args: object, **_kwargs: object):
            raise OSError("settlement write did not finish")

        def resolve_producer_event_safe(self, event_id: str):
            return middleware.resolve_producer_event_safe(event_id)

    client = TracedLLMClient(
        _Provider(cost=0.02),
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=_FailedSettlementStore(),
    )

    response = await client.generate(user="policy question")

    event = response.settlement.event
    stored = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
    assert response.settlement.ack.status == "unknown"
    assert response.settlement.ack.durability == "none"
    assert stored.status == "pending"
    assert stored.payload_digest is None and stored.amount is None
    # The run reader serves the exact pending ledger intent; it must not also
    # receive a contradictory response-shaped event under that same ID.
    assert events == []


@pytest.mark.asyncio
async def test_generic_mapping_null_cost_cannot_fall_through_to_alias_estimate(
    tmp_path: Path,
) -> None:
    class _MappingProvider:
        provider = "fixture"
        model = "fixture-model"

        async def generate(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "content": "answer",
                "model": self.model,
                "provider": self.provider,
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_cost_usd": None,
                    "cost_usd": 0.25,
                },
            }

    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    client = TracedLLMClient(
        _MappingProvider(),
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )

    response = await client.generate(user="policy question")

    record = (
        FileBudgetLedger(ledger_path)
        .snapshot()
        .producer_settlements[response.settlement.event.event_id]
    )
    assert response.settlement.event.cost_origin == "unknown"
    assert response.settlement.event.amount is None
    assert record.cost_origin == "unknown"
    assert record.amount is None
    assert record.status == "unknown"


@pytest.mark.asyncio
async def test_cancelled_cache_owner_settles_and_observes_provider_before_reuse(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    provider = _Provider(cost=0.02, blocked=True)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=30),
        model="fixture-model",
        ttl_s=30,
        inflight_timeout_s=2,
    )
    events: list[dict[str, object]] = []
    client = TracedLLMClient(
        cached,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    owner = asyncio.create_task(client.generate(user="same policy question", temperature=0))
    await provider.entered.wait()
    flight = next(iter(cached._inflight.values()))
    follower = asyncio.create_task(client.generate(user="same policy question", temperature=0))
    for _ in range(100):
        if len(flight.registrations) == 2:
            break
        await asyncio.sleep(0)
    assert len(flight.registrations) == 2

    owner.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner
    provider.release.set()
    reused = await follower

    snapshot = FileBudgetLedger(ledger_path).snapshot()
    provider_event = snapshot.producer_settlements[flight.origin_event_id]
    reuse_event = snapshot.producer_settlements[reused.settlement.event.event_id]
    assert provider.calls == 1
    assert provider_event.cost_origin == "reported"
    assert provider_event.amount == Decimal("0.02")
    assert reuse_event.cost_origin == "reuse"
    assert reuse_event.amount == Decimal(0)
    assert reuse_event.origin_event_id == provider_event.event_id
    assert snapshot.state.spent["run"] == Decimal("0.02")
    observed_by_id = {str(item["event_id"]): item for item in events}
    assert set(observed_by_id) == {provider_event.event_id, reuse_event.event_id}
    assert observed_by_id[provider_event.event_id]["cost_origin"] == "reported"
    assert observed_by_id[provider_event.event_id]["settlement_status"] == "committed"
    assert observed_by_id[reuse_event.event_id]["cost_origin"] == "reuse"


@pytest.mark.asyncio
async def test_admitted_cache_reuse_is_a_separate_durable_zero_event(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    provider = _Provider(cost=0.02)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=30),
        model="fixture-model",
        ttl_s=30,
        inflight_timeout_s=2,
    )
    events: list[dict[str, object]] = []
    client = TracedLLMClient(
        cached,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    first = await client.generate(user="same policy question", temperature=0)
    second = await client.generate(user="same policy question", temperature=0)

    snapshot = FileBudgetLedger(ledger_path).snapshot()
    provider_record = snapshot.producer_settlements[first.settlement.event.event_id]
    reuse_record = snapshot.producer_settlements[second.settlement.event.event_id]
    assert provider.calls == 1
    assert provider_record.cost_origin == "reported"
    assert provider_record.amount == Decimal("0.02")
    assert reuse_record.cost_origin == "reuse"
    assert reuse_record.amount == Decimal(0)
    assert reuse_record.origin_event_id == provider_record.event_id
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert events[0]["settlement_status"] == "committed"
    assert events[1]["cost_origin"] == "reuse"
    assert events[1]["settlement_status"] == "committed"


@pytest.mark.asyncio
async def test_shared_cache_keeps_origin_across_request_local_clients(tmp_path: Path) -> None:
    """A later wrapper reuses the cache owner's origin without stealing hooks."""
    ledger_path = tmp_path / "shared.json"
    cache = InMemoryPromptCache(maxsize=7, default_ttl_s=30)
    provider = _Provider(cost=0.02)

    def request_client(ledger_path: Path) -> TracedLLMClient:
        cached = CachingLLMClient(
            provider,
            cache=cache,
            model="fixture-model",
            ttl_s=30,
            inflight_timeout_s=2,
        )
        return TracedLLMClient(
            cached,
            model_name="fixture-model",
            tracer=_Tracer(),
            metrics=_Metrics(),
            producer_settlement_store=_middleware(ledger_path),
        )

    first = await request_client(ledger_path).generate(user="same policy question", temperature=0)
    second = await request_client(ledger_path).generate(user="same policy question", temperature=0)

    assert provider.calls == 1
    assert first.settlement.event.cost_origin == "reported"
    assert second.settlement.event.cost_origin == "reuse"
    assert second.settlement.event.origin_event_id == first.settlement.event.event_id
    second_record = (
        FileBudgetLedger(ledger_path)
        .snapshot()
        .producer_settlements[second.settlement.event.event_id]
    )
    assert second_record.amount == Decimal(0)
    assert second_record.origin_event_id == first.settlement.event.event_id


@pytest.mark.asyncio
async def test_nested_traced_client_preserves_the_inner_settlement_without_double_counting(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    provider = _Provider(cost=0.02)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=30),
        model="fixture-model",
        ttl_s=30,
        inflight_timeout_s=2,
    )
    events: list[dict[str, object]] = []
    accounting_events: list[str] = []

    def account(event: dict[str, object]) -> None:
        accounting_events.append(str(event["event_id"]))

    inner = TracedLLMClient(
        cached,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        required_accounting=account,
        call_observer=events.append,
        producer_settlement_store=middleware,
    )
    outer = TracedLLMClient(
        inner,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        required_accounting=account,
        call_observer=events.append,
        producer_settlement_store=middleware,
    )

    first = await outer.generate(user="same policy question", temperature=0)
    second = await outer.generate(user="same policy question", temperature=0)

    snapshot = FileBudgetLedger(ledger_path).snapshot()
    first_event = first.settlement.event
    second_event = second.settlement.event
    assert provider.calls == 1
    assert first_event.cost_origin == "reported"
    assert first_event.amount == Decimal("0.02")
    assert second_event.cost_origin == "reuse"
    assert second_event.amount == Decimal(0)
    assert second_event.origin_event_id == first_event.event_id
    assert set(snapshot.producer_settlements) == {first_event.event_id, second_event.event_id}
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert outer._observed_call_event_ids == set()
    assert inner._observed_call_event_ids == {first_event.event_id, second_event.event_id}
    assert events[0]["producer_event"] is first_event
    assert events[1]["producer_event"] is second_event
    assert [(item["event_id"], item["cost_origin"]) for item in events] == [
        (first_event.event_id, "reported"),
        (second_event.event_id, "reuse"),
    ]
    assert accounting_events == [first_event.event_id, second_event.event_id]
    assert {str(item["event_id"]) for item in events} == {
        first_event.event_id,
        second_event.event_id,
    }


@pytest.mark.asyncio
async def test_outer_durable_owner_covers_unmanaged_inner_and_accounts_once(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "outer-owner.json"
    middleware = _middleware(ledger_path)
    provider = _Provider(cost=0.02)
    accounting_calls: list[str] = []

    def account(event: dict[str, object]) -> None:
        accounting_calls.append(str(event["event_id"]))

    inner = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        required_accounting=account,
    )
    outer = TracedLLMClient(
        inner,
        model_name="fixture-model",
        tracer=_Tracer(),
        required_accounting=account,
        producer_settlement_store=middleware,
    )

    response = await outer.generate(user="one physical call")

    event = response.settlement.event
    reopened = FileBudgetLedger(ledger_path).snapshot()
    assert provider.calls == 1
    assert response.settlement.ack.status == "committed"
    assert set(reopened.producer_settlements) == {event.event_id}
    assert reopened.producer_settlements[event.event_id].payload_digest == event.payload_digest
    assert accounting_calls == [event.event_id]


@pytest.mark.asyncio
async def test_independent_nested_client_uses_its_own_durable_owner(
    tmp_path: Path,
) -> None:
    inner_path = tmp_path / "nested-client-owner.json"
    outer_path = tmp_path / "outer-client-owner.json"
    inner_store = _middleware(inner_path)
    outer_store = _middleware(outer_path)
    inner_provider = _Provider(cost=0.01)
    inner_client = TracedLLMClient(
        inner_provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        producer_settlement_store=inner_store,
    )

    class _ProviderCallingIndependentClient:
        provider = "fixture"
        model = "fixture-model"

        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, **_kwargs: object) -> GatewayLLMResponse:
            self.calls += 1
            await inner_client.generate(user="nested independent provider call")
            return GatewayLLMResponse(
                content="outer answer",
                usage=GatewayUsage(prompt_tokens=2, completion_tokens=1, cost_usd=0.02),
                model=self.model,
                provider=self.provider,
            )

    outer_provider = _ProviderCallingIndependentClient()
    outer_client = TracedLLMClient(
        outer_provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        producer_settlement_store=outer_store,
    )

    outer_response = await outer_client.generate(user="outer provider call")

    assert outer_provider.calls == 1
    assert inner_provider.calls == 1
    assert outer_response.settlement.ack.status == "committed"
    assert len(FileBudgetLedger(inner_path).snapshot().producer_settlements) == 1
    assert len(FileBudgetLedger(outer_path).snapshot().producer_settlements) == 1


@pytest.mark.asyncio
async def test_nested_distinct_durable_stores_refuse_before_provider_dispatch(
    tmp_path: Path,
) -> None:
    provider = _Provider(cost=0.02)
    inner_path = tmp_path / "inner-owner.json"
    outer_path = tmp_path / "outer-owner.json"
    inner_store = _middleware(inner_path)
    outer_store = _middleware(outer_path)
    inner = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        producer_settlement_store=inner_store,
    )
    outer = TracedLLMClient(
        inner,
        model_name="fixture-model",
        tracer=_Tracer(),
        producer_settlement_store=outer_store,
    )

    with pytest.raises(LLMSettlementOwnershipError, match="producer_settlement_owner_conflict"):
        await outer.generate(user="must not dispatch")

    assert provider.calls == 0
    assert FileBudgetLedger(inner_path).snapshot().producer_settlements == {}
    assert FileBudgetLedger(outer_path).snapshot().producer_settlements == {}


@pytest.mark.asyncio
async def test_nested_settlement_refuses_response_bytes_outside_event_digest(
    tmp_path: Path,
) -> None:
    class _MutatingTracedClient(TracedLLMClient):
        async def generate(self, **kwargs: object) -> object:
            envelope = await super().generate(**kwargs)
            original = envelope.response
            changed = SimpleNamespace(
                content="changed after the event was settled",
                usage=original.usage,
                model=original.model,
                provider=original.provider,
                request_id=original.request_id,
            )
            return LLMSettledResponse(changed, envelope.settlement)

    middleware = _middleware(tmp_path / "response-binding.json")
    inner = _MutatingTracedClient(
        _Provider(cost=0.02),
        model_name="fixture-model",
        tracer=_Tracer(),
        producer_settlement_store=middleware,
    )
    outer = TracedLLMClient(
        inner,
        model_name="fixture-model",
        tracer=_Tracer(),
    )

    with pytest.raises(LLMSettlementIntegrityError, match="producer_response_digest_mismatch"):
        await outer.generate(user="content binding")


@pytest.mark.asyncio
async def test_optional_metrics_failure_preserves_response_and_durable_budget_consumer(
    tmp_path: Path,
) -> None:
    import hashlib

    from polisyos.runtime.http.services.control.run_lifecycle import (
        _build_control_nl_producer_budget_reconciler,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )

    response_content = "provider-response:b65-optional-metrics-failure"
    response_cost = 0.02
    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    binding = BudgetLedgerProducerRunBinding(
        run_id="b65-metrics-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-metrics-job",
    )

    class _ResponseProvider:
        provider = "fixture"
        model = "fixture-model"

        def __init__(self) -> None:
            self.calls = 0
            self.response: GatewayLLMResponse | None = None

        async def generate(self, *_args: object, **_kwargs: object) -> GatewayLLMResponse:
            self.calls += 1
            self.response = GatewayLLMResponse(
                content=response_content,
                usage=GatewayUsage(
                    prompt_tokens=2,
                    completion_tokens=3,
                    cost_usd=response_cost,
                ),
                model=self.model,
                provider=self.provider,
                request_id="b65-provider-request",
            )
            return self.response

    class _FailingMetrics:
        def __init__(self) -> None:
            self.calls = 0

        def record_llm_call(self, **_kwargs: object) -> None:
            self.calls += 1
            raise RuntimeError("optional metrics sink unavailable")

    class _RecordingSpan(_Span):
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}

        def set_attribute(self, name: str, value: object) -> None:
            self.attributes[name] = value

    class _RecordingSpanContext:
        def __init__(self, span: _RecordingSpan) -> None:
            self.span = span

        def __enter__(self) -> _RecordingSpan:
            return self.span

        def __exit__(self, *_args: object) -> None:
            return None

    class _RecordingTracer:
        def __init__(self) -> None:
            self.span = _RecordingSpan()

        def start_as_current_span(self, *_args: object, **_kwargs: object) -> _RecordingSpanContext:
            return _RecordingSpanContext(self.span)

    provider = _ResponseProvider()
    metrics = _FailingMetrics()
    tracer = _RecordingTracer()
    observer_event_ids: list[str] = []

    def failing_observer(event: dict[str, object]) -> None:
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            observer_event_ids.append(event_id)
        raise RuntimeError("optional observer unavailable")

    client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        provider_name="fixture",
        tracer=tracer,
        metrics=metrics,
        call_observer=failing_observer,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{binding.run_id}",
    )

    with middleware.producer_run_binding_scope(binding):
        response = await client.generate(user="policy question")

    expected_response = provider.response
    assert expected_response is not None
    assert type(response) is LLMSettledResponse
    assert response.response is expected_response
    assert response.content == response_content
    assert provider.calls == 1
    assert metrics.calls == 1
    assert tracer.span.attributes["polisyos.llm.metrics_status"] == "degraded"
    event = response.settlement.event
    assert event.response_digest == hashlib.sha256(response_content.encode("utf-8")).hexdigest()
    assert event.cost_origin == "reported"
    assert event.amount == Decimal(str(response_cost))
    assert response.settlement.ack.status == "committed"
    assert response.settlement.ack.durability == "ledger"
    assert response.settlement.ack.receipts == (event.event_id,)
    assert observer_event_ids == [event.event_id]

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    records = reopened.list_producer_events_for_run_safe(binding)
    assert len(records) == 1
    record = records[0]
    assert record.event_id == event.event_id
    assert record.payload_digest == event.payload_digest
    assert record.run_binding == binding
    assert record.status == "committed"
    assert record.amount == event.amount

    budget_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    reconciler = _build_control_nl_producer_budget_reconciler(
        settlement_store=reopened,
        producer_run_binding=binding,
        budget_state=budget_state,
    )
    controller = GenerationCycleController(
        model_id="b65-optional-metrics-consumer",
        authority_scope="contract_testing",
        voi_scheduler=SimpleVOIScheduler(
            stage_costs={3: 0.01},
            min_roi_threshold=0.0,
        ),
        _producer_budget_reconciler=reconciler,
    )
    controller._schedule_candidate_for_execution(
        candidate_id="b65-settled-provider-response",
        proxy_score=1.0,
        voi_estimate=1.0,
        budget_state=budget_state,
    )
    assert budget_state.spent["run"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_unsettled_provider_response_blocks_budget_consumer_until_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _build_control_nl_producer_budget_reconciler,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )

    ledger_path = tmp_path / "ledger.json"
    middleware = _middleware(ledger_path)
    binding = BudgetLedgerProducerRunBinding(
        run_id="b65-unsettled-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-unsettled-job",
    )
    original_settle = middleware.settle_producer_event_safe

    def fail_settlement(*_args: object, **_kwargs: object) -> None:
        raise OSError("required producer settlement write unavailable")

    monkeypatch.setattr(middleware, "settle_producer_event_safe", fail_settlement)
    provider = _Provider(cost=0.02)
    observed: list[dict[str, object]] = []
    client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        call_observer=observed.append,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{binding.run_id}",
    )

    with middleware.producer_run_binding_scope(binding):
        response = await client.generate(user="policy question")

    assert type(response) is LLMSettledResponse
    assert response.content == "answer"
    assert provider.calls == 1
    event = response.settlement.event
    assert event.cost_origin == "reported"
    assert event.amount == Decimal("0.02")
    assert response.settlement.ack.status == "unknown"
    assert response.settlement.ack.durability == "none"
    assert observed == []

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    pending = reopened.list_producer_events_for_run_safe(binding)
    assert len(pending) == 1
    assert pending[0].event_id == event.event_id
    assert pending[0].request_digest == event.request_digest
    assert pending[0].status == "pending"
    assert pending[0].payload_digest is None
    assert pending[0].amount is None

    budget_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    reconciler = _build_control_nl_producer_budget_reconciler(
        settlement_store=reopened,
        producer_run_binding=binding,
        budget_state=budget_state,
    )
    controller = GenerationCycleController(
        model_id="b65-unsettled-provider-response",
        authority_scope="contract_testing",
        voi_scheduler=SimpleVOIScheduler(
            stage_costs={3: 0.01},
            min_roi_threshold=0.0,
        ),
        _producer_budget_reconciler=reconciler,
    )
    with pytest.raises(
        GenerationCycleError,
        match="control_nl_budget_producer_event_not_settled",
    ):
        controller._schedule_candidate_for_execution(
            candidate_id="blocked-unsettled-provider-response",
            proxy_score=1.0,
            voi_estimate=1.0,
            budget_state=budget_state,
        )
    assert budget_state.spent == {}

    monkeypatch.setattr(middleware, "settle_producer_event_safe", original_settle)
    settled = original_settle(
        event.event_id,
        event.request_digest,
        event.payload_digest,
        key=f"nl-run:{binding.run_id}",
        model=event.model,
        provider=event.provider,
        amount=event.amount,
        cost_origin=event.cost_origin,
        origin_event_id=event.origin_event_id,
    )
    assert settled.status == "committed"
    assert settled.payload_digest == event.payload_digest
    controller._schedule_candidate_for_execution(
        candidate_id="trusted-reconciled-provider-response",
        proxy_score=1.0,
        voi_estimate=1.0,
        budget_state=budget_state,
    )
    assert budget_state.spent["run"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_provider_error_metrics_failure_preserves_primary_error_and_sibling_budget_isolation(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _build_control_nl_producer_budget_reconciler,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )

    class _ProviderFailureError(RuntimeError):
        pass

    provider_failure = _ProviderFailureError("unique-b65-provider-error-sentinel")

    class _ConcurrentProvider:
        provider = "fixture"
        model = "fixture-model"

        def __init__(self) -> None:
            self.calls: dict[str, int] = {}
            self.responses: dict[str, GatewayLLMResponse] = {}
            self.started = 0
            self.both_started = asyncio.Event()

        async def generate(self, *_args: object, **kwargs: object) -> GatewayLLMResponse:
            user = kwargs.get("user")
            assert isinstance(user, str)
            self.calls[user] = self.calls.get(user, 0) + 1
            self.started += 1
            if self.started == 2:
                self.both_started.set()
            await asyncio.wait_for(self.both_started.wait(), timeout=3)
            if user == "b65-provider-error":
                raise provider_failure
            response = GatewayLLMResponse(
                content="sibling-valid-provider-response",
                usage=GatewayUsage(
                    prompt_tokens=2,
                    completion_tokens=3,
                    cost_usd=0.03,
                ),
                model=self.model,
                provider=self.provider,
                request_id="b65-sibling-valid-request",
            )
            self.responses[user] = response
            return response

    class _ErrorMetricsFailure:
        def __init__(self) -> None:
            self.attempts: list[dict[str, object]] = []
            self.successes: list[dict[str, object]] = []

        def record_llm_call(self, **event: object) -> None:
            self.attempts.append(dict(event))
            if event.get("status") == "error":
                raise RuntimeError("optional error metrics sink unavailable")
            self.successes.append(dict(event))

    ledger_path = tmp_path / "sibling-error-metrics.json"
    middleware = _middleware(ledger_path)
    failed_binding = BudgetLedgerProducerRunBinding(
        run_id="b65-error-sibling-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-error-sibling-job",
    )
    valid_binding = BudgetLedgerProducerRunBinding(
        run_id="b65-valid-sibling-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-valid-sibling-job",
    )
    provider = _ConcurrentProvider()
    metrics = _ErrorMetricsFailure()
    failed_observer_events: list[dict[str, object]] = []
    valid_observer_events: list[dict[str, object]] = []
    failed_client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics,
        call_observer=failed_observer_events.append,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{failed_binding.run_id}",
    )
    valid_client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics,
        call_observer=valid_observer_events.append,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{valid_binding.run_id}",
    )

    async def _invoke(
        client: TracedLLMClient,
        binding: BudgetLedgerProducerRunBinding,
        user: str,
    ) -> object:
        with middleware.producer_run_binding_scope(binding):
            return await client.generate(user=user)

    failed_result, valid_result = await asyncio.gather(
        _invoke(failed_client, failed_binding, "b65-provider-error"),
        _invoke(valid_client, valid_binding, "b65-valid-sibling"),
        return_exceptions=True,
    )

    assert provider.both_started.is_set()
    assert provider.calls == {"b65-provider-error": 1, "b65-valid-sibling": 1}
    assert failed_result is provider_failure
    assert type(valid_result) is LLMSettledResponse
    assert valid_result.response is provider.responses["b65-valid-sibling"]
    assert [event.get("status") for event in metrics.attempts].count("error") == 1
    assert [event.get("status") for event in metrics.attempts].count("success") == 1
    assert len(metrics.successes) == 1
    assert len(failed_observer_events) == 1
    assert failed_observer_events[0]["status"] == "error"
    assert failed_observer_events[0]["settlement_status"] == "unknown"
    assert len(valid_observer_events) == 1
    assert valid_observer_events[0]["settlement_status"] == "committed"

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    failed_records = reopened.list_producer_events_for_run_safe(failed_binding)
    valid_records = reopened.list_producer_events_for_run_safe(valid_binding)
    assert len(failed_records) == len(valid_records) == 1
    failed_record = failed_records[0]
    valid_record = valid_records[0]
    assert failed_record.event_id != valid_record.event_id
    assert failed_record.run_binding == failed_binding
    assert failed_record.status == "unknown"
    assert failed_record.cost_origin == "unknown"
    assert failed_record.amount is None
    assert failed_record.payload_digest is not None
    assert valid_record.run_binding == valid_binding
    assert valid_record.status == "committed"
    assert valid_record.cost_origin == "reported"
    assert valid_record.amount == Decimal("0.03")
    assert valid_record.payload_digest == valid_result.settlement.event.payload_digest

    failed_budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    failed_reconciler = _build_control_nl_producer_budget_reconciler(
        settlement_store=reopened,
        producer_run_binding=failed_binding,
        budget_state=failed_budget,
    )
    failed_controller = GenerationCycleController(
        model_id="b65-error-sibling-consumer",
        authority_scope="contract_testing",
        voi_scheduler=SimpleVOIScheduler(stage_costs={3: 0.01}, min_roi_threshold=0.0),
        _producer_budget_reconciler=failed_reconciler,
    )
    with pytest.raises(
        GenerationCycleError,
        match="control_nl_budget_producer_event_not_settled",
    ):
        failed_controller._schedule_candidate_for_execution(
            candidate_id="blocked-provider-error-sibling",
            proxy_score=1.0,
            voi_estimate=1.0,
            budget_state=failed_budget,
        )
    assert failed_budget.spent == {}

    valid_budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    valid_reconciler = _build_control_nl_producer_budget_reconciler(
        settlement_store=reopened,
        producer_run_binding=valid_binding,
        budget_state=valid_budget,
    )
    valid_controller = GenerationCycleController(
        model_id="b65-valid-sibling-consumer",
        authority_scope="contract_testing",
        voi_scheduler=SimpleVOIScheduler(stage_costs={3: 0.01}, min_roi_threshold=0.0),
        _producer_budget_reconciler=valid_reconciler,
    )
    valid_controller._schedule_candidate_for_execution(
        candidate_id="admitted-valid-sibling",
        proxy_score=1.0,
        voi_estimate=1.0,
        budget_state=valid_budget,
    )
    assert valid_budget.spent["run"] == Decimal("0.03")


@pytest.mark.asyncio
async def test_required_accounting_error_is_not_replaced_by_configured_metrics_failure(
    tmp_path: Path,
) -> None:
    from polisyos.core.llm.traced_client import LLMAccountingError
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )

    accounting_failure = RuntimeError("unique-b65-required-accounting-sentinel")

    class _CapturingProvider:
        provider = "fixture"
        model = "fixture-model"

        def __init__(self) -> None:
            self.calls = 0
            self.response: GatewayLLMResponse | None = None

        async def generate(self, *_args: object, **_kwargs: object) -> GatewayLLMResponse:
            self.calls += 1
            self.response = GatewayLLMResponse(
                content="b65-accounting-failure-response",
                usage=GatewayUsage(
                    prompt_tokens=2,
                    completion_tokens=3,
                    cost_usd=0.04,
                ),
                model=self.model,
                provider=self.provider,
                request_id="b65-accounting-failure-request",
            )
            return self.response

    class _MetricsThatWouldFail:
        def __init__(self) -> None:
            self.calls = 0

        def record_llm_call(self, **_event: object) -> None:
            self.calls += 1
            raise RuntimeError("optional metrics sink unavailable")

    def fail_required_accounting(_event: dict[str, object]) -> object:
        raise accounting_failure

    ledger_path = tmp_path / "accounting-error-metrics.json"
    middleware = _middleware(ledger_path)
    binding = BudgetLedgerProducerRunBinding(
        run_id="b65-accounting-error-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-accounting-error-job",
    )
    provider = _CapturingProvider()
    metrics = _MetricsThatWouldFail()
    client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics,
        required_accounting=fail_required_accounting,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{binding.run_id}",
    )

    with middleware.producer_run_binding_scope(binding):
        with pytest.raises(LLMAccountingError) as raised:
            await client.generate(user="required accounting must remain primary")

    assert raised.value.cause is accounting_failure
    assert raised.value.__cause__ is accounting_failure
    assert provider.calls == 1
    assert provider.response is not None
    assert raised.value.response is provider.response
    assert raised.value.event["provider_call"] is True
    assert raised.value.event["amount"] == Decimal("0.04")
    # The typed accounting-error branch precedes optional metrics; its configured
    # sink would raise if reached, but it must not replace the required failure.
    assert metrics.calls == 0

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    records = reopened.list_producer_events_for_run_safe(binding)
    assert len(records) == 1
    record = records[0]
    assert record.event_id == raised.value.event["event_id"]
    assert record.run_binding == binding
    assert record.status == "committed"
    assert record.cost_origin == "reported"
    assert record.amount == Decimal("0.04")
    assert record.payload_digest is not None


@pytest.mark.asyncio
async def test_cancelled_provider_waiter_settles_real_cost_despite_observer_failure(
    tmp_path: Path,
) -> None:
    import hashlib

    from polisyos.runtime.http.services.control.run_lifecycle import (
        _build_control_nl_producer_budget_reconciler,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )

    ledger_path = tmp_path / "cancelled-provider-observer.json"
    middleware = _middleware(ledger_path)
    binding = BudgetLedgerProducerRunBinding(
        run_id="b65-cancelled-provider-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
        profile_id="dev",
        control_job_id="b65-cancelled-provider-job",
    )
    provider = _Provider(cost=0.02, blocked=True)

    class _MetricsThatWouldFail:
        def __init__(self) -> None:
            self.calls = 0

        def record_llm_call(self, **_event: object) -> None:
            self.calls += 1
            raise RuntimeError("optional metrics sink unavailable")

    metrics = _MetricsThatWouldFail()
    observed: list[dict[str, object]] = []
    observer_event_ids: list[str] = []

    def failing_observer(event: dict[str, object]) -> None:
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            observer_event_ids.append(event_id)
        observed.append(event)
        raise RuntimeError("optional settlement observer unavailable")

    client = TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics,
        call_observer=failing_observer,
        producer_settlement_store=middleware,
        producer_budget_key=f"nl-run:{binding.run_id}",
    )

    with middleware.producer_run_binding_scope(binding):
        task = asyncio.create_task(client.generate(user="cancel after provider dispatch"))
        await provider.entered.wait()
        before_cancel = FileBudgetLedger(ledger_path).snapshot().producer_settlements
        assert len(before_cancel) == 1
        pending = next(iter(before_cancel.values()))
        assert pending.status == "pending"
        assert pending.run_binding == binding
        assert pending.payload_digest is None
        assert pending.amount is None

        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        provider.release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert provider.calls == 1
    assert metrics.calls == 0
    assert len(observed) == 1
    event = observed[0]["producer_event"]
    assert type(event) is LLMProducerEvent
    assert observer_event_ids == [event.event_id]
    assert event.cost_origin == "reported"
    assert event.amount == Decimal("0.02")
    assert event.response_digest == hashlib.sha256(b"answer").hexdigest()

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    records = reopened.list_producer_events_for_run_safe(binding)
    assert len(records) == 1
    record = records[0]
    assert record.event_id == event.event_id
    assert record.run_binding == binding
    assert record.status == "committed"
    assert record.cost_origin == "reported"
    assert record.amount == Decimal("0.02")
    assert record.payload_digest == event.payload_digest
    ledger_snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert len(ledger_snapshot.spend_receipts) == 1
    assert ledger_snapshot.state.spent["nl-run:" + binding.run_id] == Decimal("0.02")

    budget_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    reconciler = _build_control_nl_producer_budget_reconciler(
        settlement_store=reopened,
        producer_run_binding=binding,
        budget_state=budget_state,
    )
    controller = GenerationCycleController(
        model_id="b65-cancelled-provider-consumer",
        authority_scope="contract_testing",
        voi_scheduler=SimpleVOIScheduler(stage_costs={3: 0.01}, min_roi_threshold=0.0),
        _producer_budget_reconciler=reconciler,
    )
    controller._schedule_candidate_for_execution(
        candidate_id="admitted-after-cancelled-waiter-provider-return",
        proxy_score=1.0,
        voi_estimate=1.0,
        budget_state=budget_state,
    )
    assert budget_state.spent["run"] == Decimal("0.02")


@pytest.mark.asyncio
@pytest.mark.parametrize("logical_route", [None, "configured-logical-route"])
async def test_authorized_shared_cache_reuse_survives_distinct_run_bindings(
    tmp_path: Path, logical_route: str | None
) -> None:
    """The receiver records a zero edge to the original event, never reissues it."""
    import hashlib

    from polisyos.scientist.orchestration.engine.budget_ledger import BudgetLedgerProducerRunBinding
    from polisyos.scientist.orchestration.llm.prompt_cache import (
        CacheReuseDecision,
        CacheReusePrincipal,
    )

    class CurrentOwner:
        def authorize_reuse(self, request):
            assert request.evidence[0].content == b"fixed local fixture"
            return CacheReuseDecision(
                issuer="local-test-owner",
                epoch="epoch-1",
                actor_id=request.actor_id,
                tenant=request.tenant,
                scope=request.scope,
                purpose=request.purpose,
                model=request.model,
                parameters_digest=request.parameters_digest,
                evidence=request.evidence,
            )

    path = tmp_path / "cross-run-ledger.json"
    middleware = _middleware(path)
    cache = InMemoryPromptCache(maxsize=2, default_ttl_s=30)
    provider = _Provider(cost=0.02)
    context = {
        "tenant": "tenant-a",
        "scope": "tenant-a/cell-a",
        "purpose": "fixture-policy",
        "snapshot": {
            "ref": "artifact://local-fixture",
            "version": "v1",
            "immutable": True,
            "content": b"fixed local fixture",
            "content_hash": "sha256:" + hashlib.sha256(b"fixed local fixture").hexdigest(),
        },
    }

    def client_and_binding(run_id):
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            control_job_id="job-" + run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            profile_id="test-profile",
        )
        cached = CachingLLMClient(
            provider,
            cache=cache,
            model="fixture-model",
            ttl_s=30,
            reuse_authorizer=CurrentOwner(),
            reuse_principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
            reuse_context=context,
            require_reuse_authorization=True,
            # This test isolates settlement mechanics; served tests use the real lease guard.
            reuse_guard=lambda operation: operation(),
        )
        traced = TracedLLMClient(
            cached,
            model_name="fixture-model",
            tracer=_Tracer(),
            metrics=_Metrics(),
            producer_settlement_store=middleware,
            provider_name=logical_route,
            producer_budget_key="nl-run:" + run_id,
        )
        return traced, binding

    first, first_binding = client_and_binding("source-run")
    with middleware.producer_run_binding_scope(first_binding, control_job_attempt=1):
        produced = await first.generate(user="same policy", temperature=0)
    before = FileBudgetLedger(path).snapshot()
    second, second_binding = client_and_binding("receiver-run")
    with middleware.producer_run_binding_scope(second_binding, control_job_attempt=1):
        reused = await second.generate(user="same policy", temperature=0)
    reopened = FileBudgetLedger(path).snapshot()
    source = reopened.producer_settlements[produced.settlement.event.event_id]
    receiver = reopened.producer_settlements[reused.settlement.event.event_id]
    assert provider.calls == 1
    assert produced.settlement.ack.status == reused.settlement.ack.status == "committed"
    assert source == before.producer_settlements[source.event_id]
    assert source.key != receiver.key and source.run_binding != receiver.run_binding
    assert source.provider == receiver.provider == (logical_route or provider.provider)
    assert receiver.run_binding == second_binding
    assert source.run_binding == first_binding
    assert receiver.cost_origin == "reuse" and receiver.amount == Decimal(0)
    assert receiver.origin_event_id == source.event_id
    assert receiver.reuse_admission.issuer == "local-test-owner"
    assert receiver.reuse_admission.epoch == "epoch-1"
    assert reopened.state.spent["nl-run:source-run"] == Decimal("0.02")
    assert reopened.state.spent["nl-run:receiver-run"] == Decimal(0)

    # A matching string-shaped edge without the live Core response proof must
    # still fail; cross-run compatibility alone is never authorization.
    with middleware.producer_run_binding_scope(second_binding, control_job_attempt=1):
        with pytest.raises(ValueError, match="cross_run_admission_missing"):
            middleware.settle_producer_event_safe(
                "forged-reuse",
                source.request_digest,
                receiver.payload_digest,
                key=receiver.key,
                model=source.model,
                provider=source.provider,
                amount=Decimal(0),
                cost_origin="reuse",
                origin_event_id=source.event_id,
            )
    assert "forged-reuse" not in FileBudgetLedger(path).snapshot().producer_settlements

    # Present-but-fake control: copying a genuine response preserves the
    # attestation object and all fields, but does not preserve its exact
    # response binding. Even a retry of an existing event must verify intake.
    import copy

    counterfeit = copy.copy(reused.response)
    with middleware.producer_run_binding_scope(second_binding, control_job_attempt=1):
        with pytest.raises(ValueError, match="invalid_core_response"):
            middleware.settle_producer_event_safe(
                receiver.event_id,
                receiver.request_digest,
                receiver.payload_digest,
                key=receiver.key,
                model=receiver.model,
                provider=receiver.provider,
                amount=Decimal(0),
                cost_origin="reuse",
                origin_event_id=source.event_id,
                cache_reuse_session=second._cache_settlement_session,
                cache_reuse_response=counterfeit,
            )
    assert FileBudgetLedger(path).snapshot() == reopened


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage", [None, {}, {"prompt_tokens": 2}, {"prompt_tokens": 0, "completion_tokens": 0}]
)
async def test_recorded_unknown_usage_cannot_settle_as_an_estimated_zero(
    tmp_path: Path, usage
) -> None:
    from tests._helpers.acquisition_chain import load_served_wdi_generation_recording
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        RecordedGenerationReplayClient,
    )

    recording = load_served_wdi_generation_recording()
    recording["responses"][0]["usage"] = usage
    middleware = _middleware(tmp_path / "unknown-recorded-usage.json")
    client = TracedLLMClient(
        RecordedGenerationReplayClient(recording),
        model_name=recording["model_id"],
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    response = await client.generate(user="unknown recorded usage")
    event = response.settlement.event
    assert event.cost_origin == "unknown"
    assert event.amount is None
    assert response.settlement.ack.status == "unknown"
    record = (
        FileBudgetLedger(tmp_path / "unknown-recorded-usage.json")
        .snapshot()
        .producer_settlements[event.event_id]
    )
    assert record.status == "unknown" and record.amount is None


@pytest.mark.asyncio
async def test_real_cache_reuse_capture_cannot_be_replayed_as_a_new_estimated_zero(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality._n4_usage_capture import capture_call_usage
    from polisyos.runtime.quality.design_generation import RecordingLLMClient
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        RecordedGenerationReplayClient,
    )
    from tools.quality.validation.generation_replay_input import build_replay_capture

    live_ledger_path = tmp_path / "live-cache.json"
    middleware = _middleware(live_ledger_path)
    provider = _Provider(cost=0.02)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=30),
        model="fixture-model",
        ttl_s=30,
        inflight_timeout_s=2,
    )
    client = TracedLLMClient(
        cached,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=middleware,
    )
    recorder = RecordingLLMClient(client, model_id="fixture-model")
    with capture_call_usage() as captured:
        await recorder.generate(user="same policy question", temperature=0)
        await recorder.generate(user="same policy question", temperature=0)
    assert provider.calls == 1
    assert captured.evidence[1].observation.source_was_reuse
    assert captured.evidence[1].observation.billable_usage.prompt_tokens == 0
    assert captured.evidence[1].observation.normalized_origin_usage.prompt_tokens == 2
    assert captured.evidence[1].observation.normalized_origin_usage.completion_tokens == 1
    assert captured.evidence[1].observation.reuse_verification == "verified_live_core_session"
    envelope = build_replay_capture(
        metadata={"model_id": "fixture-model", "recorded_at": "fixture"},
        calls=captured.calls,
        evidence=captured.evidence,
    )
    replay = RecordedGenerationReplayClient(envelope)
    await replay.generate(user="first recorded row")
    fresh_ledger_path = tmp_path / "fresh-replay.json"
    fresh = TracedLLMClient(
        replay,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=_Metrics(),
        producer_settlement_store=_middleware(fresh_ledger_path),
    )
    response = await fresh.generate(user="reuse bytes are not a current reuse capability")
    assert response.settlement.event.cost_origin == "unknown"
    assert response.settlement.event.amount is None
    assert response.settlement.ack.status == "unknown"
    row = (
        FileBudgetLedger(fresh_ledger_path)
        .snapshot()
        .producer_settlements[response.settlement.event.event_id]
    )
    assert row.cost_origin == "unknown" and row.amount is None
    # Falsify the producer/reuse premise while retaining all other evidence.
    changed = envelope.model_dump(mode="json")
    changed["call_usage"][1]["observation"]["source_was_reuse"] = False
    from polisyos.pdc import gy_content_hash

    changed["content_hash"] = gy_content_hash(
        {key: value for key, value in changed.items() if key != "content_hash"}
    )
    with pytest.raises(ValueError, match="reuse_downgraded_to_provider"):
        type(envelope).model_validate(changed)
