"""Provider outcomes remain durable through the traced-client boundary."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.llm.settlement import LLMProducerEvent
from polisyos.core.llm.traced_client import TracedLLMClient, _settlement_ack
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
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
