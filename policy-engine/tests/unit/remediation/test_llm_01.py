"""Regression coverage for the LLM-01 response/tracing/cache boundary."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.llm.response import llm_local_receipt_resolver
from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.methods.search.funnel.types import resolve_funnel_local_receipt
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    GatewayLLMResponse,
    GatewayUsage,
)
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
    def __init__(self, *, raw: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raw = raw

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=f"answer:{kwargs.get('prompt') or kwargs.get('user') or ''}",
            model="fixture-model",
            provider="fixture-provider",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5, cost_usd=0.02),
            request_id="provider-request-1",
            raw=self.raw,
        )


def _traced(provider: Any, *, metrics: Any | None = None, **kwargs: Any) -> TracedLLMClient:
    # Explicit trusted fixture composition mirrors the production factory.
    if isinstance(provider, CachingLLMClient):
        kwargs["cache_reuse_owner"] = provider._cache_reuse_owner
    return TracedLLMClient(
        provider,
        model_name="fixture-model",
        tracer=_Tracer(),
        metrics=metrics if metrics is not None else _Metrics(),
        **kwargs,
    )


def _paid_cache_stack(
    tmp_path: Path, *, ttl_s: float, metrics: _Metrics | None = None
) -> tuple[_PromptProvider, CachingLLMClient, LLMBudgetEnforcer, BudgetMiddleware, Path]:
    provider = _PromptProvider(raw=None)
    cached = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(maxsize=4, default_ttl_s=ttl_s),
        model="fixture-model",
        ttl_s=ttl_s,
    )
    ledger_path = tmp_path / "llm-producer-budget.json"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))}),
        ledger=FileBudgetLedger(ledger_path),
    )
    enforcer = LLMBudgetEnforcer(
        client=_traced(cached, metrics=metrics),
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="fixture-model",
    )
    return provider, cached, enforcer, middleware, ledger_path


def _fresh_receipt_owner(ledger_path: Path) -> BudgetMiddleware:
    # Reopen the actual native ledger; this adapter only reads its exact receipt.
    return BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))


def _assert_original_paid_receipt(response: Any, ledger_path: Path) -> Any:
    settlement = producer_settlement(response)
    assert settlement is not None
    assert settlement.event.kind == "provider"
    assert settlement.event.amount == Decimal("0.02")
    assert settlement.ack.status == "committed"
    assert settlement.ack.durability == "ledger"
    assert len(settlement.ack.receipts) == 1
    fresh = FileBudgetLedger(ledger_path)
    assert fresh.resolve_spend(settlement.ack.receipts[0].event_id) == settlement.ack.receipts[0]
    assert fresh.snapshot().state.spent["run"] == Decimal("0.02")
    assert len(fresh.snapshot().spend_receipts) == 1
    return settlement


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
    ) -> dict[str, Any]:
        del endpoint, timeout_s
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
    provider, _, enforcer, middleware, ledger_path = _paid_cache_stack(
        tmp_path, ttl_s=3600, metrics=metrics
    )
    first = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    original = _assert_original_paid_receipt(first, ledger_path)
    reader = _fresh_receipt_owner(ledger_path)
    assert reader.settlement_owner_identity == middleware.settlement_owner_identity
    with llm_local_receipt_resolver(partial(resolve_funnel_local_receipt, reader)):
        second = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
        third = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)

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
    assert snapshot.state.reserved["run"] == 0
    assert list(snapshot.spend_receipts.values()) == list(original.ack.receipts)
    for reused in [second, third]:
        settlement = producer_settlement(reused)
        assert settlement is not None
        assert settlement.event.kind == "reuse"
        assert settlement.event.amount == 0
        assert settlement.event.origin_event_id == original.event.event_id
        assert reused.response._polisyos_settlement == original
    assert producer_settlement(second).event.event_id != producer_settlement(third).event.event_id


@pytest.mark.asyncio
async def test_budget_enforcer_charges_misses_not_cache_reuse_and_charges_after_expiry(
    tmp_path: Path,
) -> None:
    provider, _, enforcer, _, ledger_path = _paid_cache_stack(tmp_path, ttl_s=0.02)
    first = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    original = _assert_original_paid_receipt(first, ledger_path)
    reader = _fresh_receipt_owner(ledger_path)
    with llm_local_receipt_resolver(partial(resolve_funnel_local_receipt, reader)):
        reused = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
        assert FileBudgetLedger(ledger_path).snapshot().state.spent["run"] == Decimal("0.02")
        await asyncio.sleep(0.04)
        expired = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)

    budget_state = FileBudgetLedger(ledger_path).snapshot().state
    assert len(provider.calls) == 2
    assert budget_state.spent["run"] == Decimal("0.04")
    assert budget_state.reserved["run"] == 0
    reused_settlement = producer_settlement(reused)
    expired_settlement = producer_settlement(expired)
    assert reused_settlement.event.kind == "reuse"
    assert reused_settlement.event.origin_event_id == original.event.event_id
    assert expired_settlement.event.kind == "provider"
    assert expired_settlement.event.event_id != original.event.event_id
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert len(snapshot.spend_receipts) == 2
    assert sum(
        (receipt.amount for receipt in snapshot.spend_receipts.values()), Decimal(0)
    ) == Decimal("0.04")


@pytest.mark.asyncio
async def test_paid_cache_reuse_without_local_readback_refuses_without_new_charge(
    tmp_path: Path,
) -> None:
    provider, _, enforcer, _, ledger_path = _paid_cache_stack(tmp_path, ttl_s=3600)
    first = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    original = _assert_original_paid_receipt(first, ledger_path)
    with pytest.raises(ValueError, match="original producer settlement and local receipt readback"):
        await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert len(provider.calls) == 1
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert snapshot.state.reserved["run"] == 0
    assert list(snapshot.spend_receipts.values()) == list(original.ack.receipts)


@pytest.mark.parametrize("invalid_readback", ["missing", "lookalike", "conflicting_amount"])
@pytest.mark.asyncio
async def test_paid_cache_reuse_invalid_readback_refuses_and_preserves_original_receipt(
    tmp_path: Path, invalid_readback: str
) -> None:
    provider, _, enforcer, _, ledger_path = _paid_cache_stack(tmp_path, ttl_s=3600)
    first = await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    original = _assert_original_paid_receipt(first, ledger_path)
    reader = _fresh_receipt_owner(ledger_path)

    def resolver(declared: Any) -> Any:
        actual = resolve_funnel_local_receipt(reader, declared)
        assert actual is not None  # Valid original readback remains present in every negative.
        if invalid_readback == "missing":
            return None
        if invalid_readback == "lookalike":
            return asdict(actual)
        return replace(actual, amount=Decimal("0.04"))

    with (
        llm_local_receipt_resolver(resolver),
        pytest.raises(ValueError, match=r"receipt readback unavailable|conflicts with original"),
    ):
        await enforcer.generate(user="hello", max_tokens=2, _prompt_tokens_estimate=3)
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert len(provider.calls) == 1
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert snapshot.state.reserved["run"] == 0
    assert list(snapshot.spend_receipts.values()) == list(original.ack.receipts)


@pytest.mark.asyncio
async def test_unsettled_cache_origin_cannot_become_paid_reuse_with_a_real_reader(
    tmp_path: Path,
) -> None:
    provider = _PromptProvider()
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="fixture-model")
    traced = _traced(cached)
    first = await traced.generate(user="hello")
    original = producer_settlement(first)
    assert original is not None
    assert original.ack.status == "unmanaged"
    assert original.ack.receipts == ()
    ledger_path = tmp_path / "unpaid-origin-budget.json"
    reader = _fresh_receipt_owner(ledger_path)
    with (
        llm_local_receipt_resolver(partial(resolve_funnel_local_receipt, reader)),
        pytest.raises(ValueError, match="original response content/context and paid receipt"),
    ):
        await traced.generate(user="hello")
    assert len(provider.calls) == 1
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert snapshot.spend_receipts == {}
    assert snapshot.state.spent.get("run", Decimal(0)) == 0
