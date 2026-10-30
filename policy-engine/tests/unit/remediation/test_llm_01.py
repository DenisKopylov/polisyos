"""Regression coverage for the LLM-01 response/tracing/cache boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.llm.settlement import LLMProducerEvent, LLMSettledResponse
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm import prompt_cache as prompt_cache_module
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    GatewayLLMResponse,
    GatewayUsage,
)
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, *_args: Any) -> None:
        return None

    def record_exception(self, *_args: Any) -> None:
        return None


class _SpanContext:
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, *_args: Any) -> bool:
        return False


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_as_current_span(self, *_args: Any, **_kwargs: Any) -> _SpanContext:
        span = _Span()
        self.spans.append(span)
        return _SpanContext(span)


class _Metrics:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict[str, Any]] = []

    def record_llm_call(self, **event: Any) -> None:
        if self.fail:
            raise RuntimeError("optional metrics sink unavailable")
        self.events.append(event)


class _PromptProvider:
    provider = "fixture-provider"

    def __init__(self, *, raw: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raw = raw

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=f"answer:{kwargs.get('prompt') or kwargs.get('user') or ''}",
            model="fixture-model",
            provider=self.provider,
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5, cost_usd=0.02),
            request_id="provider-request-1",
            raw=self.raw,
        )


def _traced(provider: Any, *, metrics: Any | None = None, **kwargs: Any) -> TracedLLMClient:
    return TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics if metrics is not None else _Metrics(),
        **kwargs,
    )


def _paid_cache_client(
    ledger_path: Path, *, ttl_s: float, metrics: _Metrics | None = None
) -> tuple[_PromptProvider, TracedLLMClient]:
    """Compose the public cache consumer with the durable local producer ledger."""
    provider = _PromptProvider(raw=None)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=ttl_s),
        model="fixture-model",
        ttl_s=ttl_s,
    )
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))}),
        ledger=FileBudgetLedger(ledger_path),
    )
    return provider, _traced(
        cached,
        metrics=metrics,
        provider_name="fixture-provider",
        producer_settlement_store=middleware,
    )


def _assert_paid_origin(response: LLMSettledResponse, ledger_path: Path) -> LLMProducerEvent:
    """Reopen both durable rows that identify this locally charged event."""
    event = response.settlement.event
    ack = response.settlement.ack
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    record = snapshot.producer_settlements[event.event_id]
    receipt = snapshot.spend_receipts[event.event_id]
    assert event.kind == "provider" and event.cost_origin == "reported"
    assert event.amount == Decimal("0.02")
    assert ack.status == "committed" and ack.durability == "ledger"
    assert ack.receipts == (event.event_id,)
    assert record.payload_digest == event.payload_digest == receipt.payload_digest
    assert record.key == receipt.key == "run"
    assert record.provider == receipt.provider == "fixture-provider"
    assert record.amount == receipt.amount == Decimal("0.02")
    return event


@pytest.mark.asyncio
async def test_duplicate_prompt_is_normalized_to_one_provider_argument() -> None:
    provider = _PromptProvider()
    traced = _traced(provider)

    response = await traced.generate("hello", prompt="hello")

    assert response.content == "answer:hello"
    assert provider.calls == [{"prompt": "hello"}]


@pytest.mark.asyncio
async def test_gateway_prompt_form_maps_to_supported_user_message_once() -> None:
    gateway = GatewayLLMClient(
        base_url="https://fixture.invalid/v1",
        api_key="fixture-key",
        model="fixture-model",
    )
    requests: list[dict[str, Any]] = []

    async def fake_post_json(
        *,
        endpoint: str,
        payload: dict[str, Any],
        timeout_s: float,
        _prepared_transport: bytes | None = None,
        _on_success: Callable[[bytes], None] | None = None,
        _producer_emission: object | None = None,
    ) -> dict[str, Any]:
        assert endpoint == "/chat/completions"
        assert timeout_s > 0
        assert _prepared_transport is not None
        assert _on_success is not None
        del _producer_emission
        requests.append(payload)
        return {
            "model": "fixture-model",
            "choices": [{"message": {"content": "answer:hello"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    gateway._post_json = fake_post_json  # type: ignore[method-assign]
    traced = _traced(gateway)

    response = await traced.generate(prompt="hello", system="sys")

    assert response.content == "answer:hello"
    assert requests[0]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    assert "prompt" not in requests[0]


@pytest.mark.asyncio
async def test_conflicting_prompt_forms_are_rejected_before_provider_call() -> None:
    provider = _PromptProvider()
    traced = _traced(provider)

    with pytest.raises(TypeError, match="conflicting prompt"):
        await traced.generate("positional", prompt="named")

    assert provider.calls == []


@pytest.mark.asyncio
async def test_optional_metrics_failure_preserves_provider_result_and_no_retry() -> None:
    provider = _PromptProvider()
    traced = _traced(provider, metrics=_Metrics(fail=True))

    response = await traced.generate(user="hello")

    assert response.content == "answer:hello"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_provider_raw_cache_marker_cannot_forge_reuse_billing() -> None:
    provider = _PromptProvider(raw={"_polisyos_cache": {"status": "hit"}})
    metrics = _Metrics()
    traced = _traced(provider, metrics=metrics)

    response = await traced.generate(user="hello")

    assert response.content == "answer:hello"
    assert len(provider.calls) == 1
    assert metrics.events[0]["status"] == "success"
    assert metrics.events[0]["cost_usd"] == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_mandatory_accounting_failure_exposes_received_response() -> None:
    provider = _PromptProvider()

    def fail_accounting(_event: dict[str, Any]) -> None:
        raise RuntimeError("accounting ledger unavailable")

    traced = _traced(provider, required_accounting=fail_accounting)

    with pytest.raises(LLMAccountingError) as raised:
        await traced.generate(user="hello")

    assert raised.value.response.content == "answer:hello"
    assert raised.value.event["provider_call"] is True
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_cache_hits_emit_reuse_without_duplicate_provider_usage(tmp_path: Path) -> None:
    metrics = _Metrics()
    ledger_path = tmp_path / "producer-budget.json"
    provider, traced = _paid_cache_client(ledger_path, ttl_s=3600, metrics=metrics)

    first = await traced.generate(user="hello", temperature=0)
    original = _assert_paid_origin(first, ledger_path)
    second = await traced.generate(user="hello", temperature=0)
    third = await traced.generate(user="hello", temperature=0)

    assert len(provider.calls) == 1
    assert [event["status"] for event in metrics.events] == ["success", "cache_hit", "cache_hit"]
    assert metrics.events[0]["prompt_tokens"] == 3
    assert metrics.events[0]["cost_usd"] == pytest.approx(0.02)
    assert metrics.events[1]["prompt_tokens"] == 0
    assert metrics.events[1]["completion_tokens"] == 0
    assert metrics.events[1]["cost_usd"] == 0.0
    assert first.usage.prompt_tokens == second.usage.prompt_tokens == third.usage.prompt_tokens == 3
    assert second.raw["_polisyos_cache"]["status"] == "hit"
    assert second.raw["_polisyos_cache"]["cache_key"]
    assert second.raw is not third.raw
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert snapshot.state.reserved.get("run", Decimal(0)) == 0
    assert len(snapshot.spend_receipts) == 3
    reuse_ids = set()
    for reused in (second, third):
        event, ack = reused.settlement.event, reused.settlement.ack
        reuse_ids.add(event.event_id)
        assert event.kind == "reuse" and event.cost_origin == "reuse"
        assert event.amount == 0 and event.origin_event_id == original.event_id
        assert ack.status == "committed" and ack.durability == "ledger"
        assert ack.receipts == (event.event_id,)
        assert snapshot.producer_settlements[event.event_id].origin_event_id == original.event_id
        assert snapshot.spend_receipts[event.event_id].amount == 0
    assert len(reuse_ids) == 2


@pytest.mark.asyncio
async def test_budget_enforcer_charges_misses_not_cache_reuse_and_charges_after_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [100.0]
    monkeypatch.setattr(prompt_cache_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    ledger_path = tmp_path / "producer-budget.json"
    provider, traced = _paid_cache_client(ledger_path, ttl_s=30)
    budget_state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
    )
    enforcer = LLMBudgetEnforcer(
        client=traced,
        budget_state=budget_state,
        budget_keys=["run"],
        model_name="fixture-model",
    )

    first = await enforcer.generate(
        user="hello", temperature=0, max_tokens=2, _prompt_tokens_estimate=3
    )
    original = _assert_paid_origin(first, ledger_path)
    reused = await enforcer.generate(
        user="hello", temperature=0, max_tokens=2, _prompt_tokens_estimate=3
    )
    assert reused.settlement.event.origin_event_id == original.event_id
    assert reused.settlement.ack.status == "committed"
    clock[0] += 31
    expired = await enforcer.generate(
        user="hello", temperature=0, max_tokens=2, _prompt_tokens_estimate=3
    )

    assert len(provider.calls) == 2
    assert budget_state.spent["run"] == Decimal("0.04")
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("0.04")
    assert expired.settlement.event.kind == "provider"
    assert expired.settlement.event.event_id != original.event_id
    assert expired.settlement.ack.status == "committed"
    assert sum(
        (receipt.amount for receipt in snapshot.spend_receipts.values()), Decimal(0)
    ) == Decimal("0.04")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("missing_origin", "producer_reuse_origin_missing"),
        ("missing_receipt", "committed producer outcome requires its exact spend receipt"),
        ("conflicting_amount", "committed producer outcome requires its exact spend receipt"),
        ("conflicting_digest", "producer settlement and spend receipt digest disagree"),
        ("conflicting_provider", "committed producer outcome requires its exact spend receipt"),
        ("conflicting_key", "committed producer outcome requires its exact spend receipt"),
    ],
)
async def test_paid_cache_reuse_withholds_ledger_ack_when_original_custody_conflicts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, damage: str, reason: str
) -> None:
    ledger_path = tmp_path / "producer-budget.json"
    provider, traced = _paid_cache_client(ledger_path, ttl_s=3600)
    first = await traced.generate(user="hello", temperature=0)
    origin = _assert_paid_origin(first, ledger_path)
    valid_hit = await traced.generate(user="hello", temperature=0)
    assert valid_hit.settlement.ack.status == "committed"
    assert valid_hit.settlement.event.origin_event_id == origin.event_id

    original = ledger_path.read_bytes()
    payload = json.loads(original)
    if damage == "missing_origin":
        del payload["producer_settlements"][origin.event_id]
    elif damage == "missing_receipt":
        del payload["spend_receipts"][origin.event_id]
    elif damage == "conflicting_amount":
        payload["spend_receipts"][origin.event_id]["amount"] = "0.04"
    elif damage == "conflicting_digest":
        payload["spend_receipts"][origin.event_id]["payload_digest"] = "0" * 64
    elif damage == "conflicting_provider":
        payload["spend_receipts"][origin.event_id]["provider"] = None
    else:
        payload["spend_receipts"][origin.event_id]["key"] = "other"
        payload["state"]["spent"]["other"] = "0.02"
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")
    damaged = ledger_path.read_bytes()
    try:
        candidate = await traced.generate(user="hello", temperature=0)
        assert candidate.settlement.event.kind == "reuse"
        assert candidate.settlement.event.origin_event_id == origin.event_id
        assert candidate.settlement.ack.status == "unknown"
        assert candidate.settlement.ack.receipts == ()
        assert len(provider.calls) == 1
        assert ledger_path.read_bytes() == damaged
        assert any(
            record.exc_info is not None and reason in str(record.exc_info[1])
            for record in caplog.records
        )
    finally:
        ledger_path.write_bytes(original)
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert snapshot.producer_settlements[origin.event_id].amount == Decimal("0.02")
    assert snapshot.state.spent["run"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_unmanaged_cache_origin_cannot_acquire_a_paid_ledger_ack(tmp_path: Path) -> None:
    provider = _PromptProvider(raw=None)
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
    first = await _traced(cached).generate(user="hello", temperature=0)
    assert first.settlement.ack.status == "unmanaged"

    ledger_path = tmp_path / "new-ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    traced = _traced(cached, provider_name="fixture-provider", producer_settlement_store=middleware)
    candidate = await traced.generate(user="hello", temperature=0)

    assert candidate.settlement.event.kind == "reuse"
    assert candidate.settlement.event.origin_event_id == first.settlement.event.event_id
    assert candidate.settlement.ack.status == "unknown"
    assert candidate.settlement.ack.receipts == ()
    assert len(provider.calls) == 1
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert first.settlement.event.event_id not in snapshot.producer_settlements
    assert snapshot.state.spent.get("run", Decimal(0)) == 0
