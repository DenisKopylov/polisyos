"""Actual reused bytes must bind the observed producer receipt and request."""

from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.llm.settlement import producer_settlement
from polisyos.scientist.methods.search.funnel.types import funnel_resource_receipt_context

_root = Path(__file__).resolve().parents[4]
_owner = run_path(str(_root / "tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py"))
_text = run_path(str(Path(__file__).with_name("test_gateway_response_text_cost.py")))


@pytest.mark.parametrize("alteration", ["content", "missing-receipt", "foreign-request"])
@pytest.mark.asyncio
async def test_native_http_cached_payload_cannot_borrow_unbound_paid_receipt(tmp_path, alteration):
    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", "1"))
    _, cache, enforcer, middleware, _ = _owner["_durable_stack"](tmp_path, gateway=gateway)
    first = await enforcer.generate(
        user="original request", temperature=0.0, _prompt_tokens_estimate=1
    )
    original_settlement = producer_settlement(first)
    key = next(iter(cache._cache._store))  # Observe actual runtime key; no private write.
    cached = cache._cache.get(key)
    if alteration == "content":
        cached.content = "altered output with retained producer receipt"
    elif alteration == "missing-receipt":
        cached._polisyos_settlement = None
    else:
        other = await enforcer.generate(
            user="foreign request", temperature=0.0, _prompt_tokens_estimate=1
        )
        cached._polisyos_settlement = producer_settlement(other)
    # Public cache supplier stores its immutable serialized response normally.
    # This preserves cache-owner markers and exercises admission on actual get.
    cache._cache.put(key, cached)
    failure = None
    with funnel_resource_receipt_context(middleware):
        try:
            result = await enforcer.generate(
                user="original request", temperature=0.0, _prompt_tokens_estimate=1
            )
        except ValueError as exc:
            failure = exc
    if failure is not None:
        assert "cache reuse" in str(failure)
        assert middleware.budget_state.spent["run"] == gateway.transport.calls
        return
    actual = producer_settlement(result)
    if actual.event.kind == "reuse":
        # A free grant must consume the original response bytes and request.
        assert result.content == first.content
        assert actual.event.response_digest == original_settlement.event.response_digest
        assert actual.event.origin_event_id == original_settlement.event.event_id
    else:
        assert actual.event.kind == "provider" and actual.event.amount == 1
        assert gateway.transport.calls == (3 if alteration == "foreign-request" else 2)
        assert middleware.budget_state.spent["run"] == gateway.transport.calls


@pytest.mark.asyncio
async def test_native_http_unchanged_cache_payload_has_actual_origin_receipt(tmp_path):
    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", "1"))
    _, _, enforcer, middleware, _ = _owner["_durable_stack"](tmp_path, gateway=gateway)
    first = await enforcer.generate(
        user="original request", temperature=0.0, _prompt_tokens_estimate=1
    )
    with funnel_resource_receipt_context(middleware):
        second = await enforcer.generate(
            user="original request", temperature=0.0, _prompt_tokens_estimate=1
        )
    original, reused = producer_settlement(first), producer_settlement(second)
    assert original.event.kind == "provider" and reused.event.kind == "reuse"
    assert reused.event.origin_event_id == original.event.event_id
    assert (
        second.content == first.content
        and reused.event.response_digest == original.event.response_digest
    )
    assert reused.event.request_digest == original.event.request_digest
    for receipt in original.ack.receipts:
        assert middleware.resolve_spend_safe(receipt.event_id) == receipt
    assert gateway.transport.calls == 1 and middleware.budget_state.spent["run"] == 1


@pytest.mark.parametrize("removal", ["resolver", "receipt-type", "readback"])
@pytest.mark.asyncio
async def test_native_http_free_reuse_refuses_missing_verification_with_markers_retained(
    tmp_path, monkeypatch, removal
):
    from dataclasses import replace
    from types import SimpleNamespace

    from polisyos.core.llm.settlement import LLMProducerSettlement

    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", "1"))
    _, cache, enforcer, middleware, _ = _owner["_durable_stack"](tmp_path, gateway=gateway)
    await enforcer.generate(user="original request", temperature=0.0, _prompt_tokens_estimate=1)
    if removal == "receipt-type":
        key = next(iter(cache._cache._store))
        cached = cache._cache.get(key)
        origin = producer_settlement(cached)
        lookalike = SimpleNamespace(**origin.ack.receipts[0].model_dump())
        cached._polisyos_settlement = LLMProducerSettlement(
            origin.event, replace(origin.ack, receipts=(lookalike,))
        )
        cache._cache.put(key, cached)
    if removal == "readback":
        monkeypatch.setattr(middleware, "resolve_spend_safe", lambda event_id: None)
    with (
        funnel_resource_receipt_context(None if removal == "resolver" else middleware),
        pytest.raises(ValueError, match="cache reuse"),
    ):
        await enforcer.generate(user="original request", temperature=0.0, _prompt_tokens_estimate=1)
    assert gateway.transport.calls == 1 and middleware.budget_state.spent["run"] == 1
