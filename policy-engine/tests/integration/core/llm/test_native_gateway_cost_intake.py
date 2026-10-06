"""Native raw decoder -> cost intake -> measured ledger, without billing authority."""

from copy import deepcopy
from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    GatewayLLMResponse,
    GatewayUsage,
)


class RawGateway(GatewayLLMClient):
    """Decoded payload is controlled; the separate text probe covers JSON lexemes."""

    def __init__(self, payload):
        super().__init__(
            base_url="https://fixture.invalid",
            api_key="",
            model="test-model",
            provider_hint="provider-a",
        )
        self.payload = payload
        self.calls = 0
        self.normalized_response = None

    async def _post_json(self, **kwargs):
        self.calls += 1
        return deepcopy(self.payload)

    async def generate(self, **kwargs):
        self.normalized_response = await super().generate(**kwargs)
        return self.normalized_response


def raw_payload(usage):
    return {
        "choices": [{"message": {"content": "observed response"}}],
        "provider": "provider-a",
        "_gateway_request_id": "request-1",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, **usage},
    }


def build(tmp_path, client):
    path = tmp_path / "ledger.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    enforcer = LLMBudgetEnforcer(
        client=client,
        budget_state=state,
        budget_keys=["run"],
        run_id="run-1",
        model_name="test-model",
        budget_middleware=owner,
    )
    return path, enforcer


async def invoke(enforcer):
    return await enforcer.generate(
        user="hello",
        max_tokens=1,
        _prompt_tokens_estimate=1,
        _evaluation_id="native-raw-cost",
    )


def assert_no_receipt_after_invalid_intake(path):
    """B1.1 releases anonymous capacity on invalid intake.

    No persisted owner/attempt reconciliation record is asserted or supplied.
    """
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.spend_receipts == {}
    assert snapshot.state.spent == {}
    assert snapshot.state.reserved["run"] == 0


@pytest.mark.asyncio
async def test_native_raw_negative_cannot_settle_a_normalized_zero(tmp_path):
    gateway = RawGateway(raw_payload({"cost_usd": -1}))
    path, enforcer = build(tmp_path, gateway)
    with pytest.raises(ValueError, match="provider cost"):
        await invoke(enforcer)
    assert gateway.calls == 1
    assert gateway.normalized_response.usage.cost_usd == 0.0
    assert gateway.normalized_response.raw["usage"]["cost_usd"] == -1
    assert_no_receipt_after_invalid_intake(path)


@pytest.mark.parametrize("source", ["usage", "payload"])
@pytest.mark.parametrize(
    "field", ["total_cost_usd", "cost_usd", "cost", "base_cost_usd", "platform_fee_usd"]
)
@pytest.mark.parametrize(
    "invalid", [-1, float("nan"), float("inf"), float("-inf"), True, False, "bad", {}, [1]]
)
@pytest.mark.asyncio
async def test_native_raw_invalid_alternate_never_uses_a_valid_normalized_marker(
    tmp_path, source, field, invalid
):
    payload = raw_payload({"total_cost_usd": 1, "cost_usd": 1})
    target = payload["usage"] if source == "usage" else payload
    target[field] = invalid
    gateway = RawGateway(payload)
    path, enforcer = build(tmp_path, gateway)
    with pytest.raises(ValueError, match="provider cost"):
        await invoke(enforcer)
    assert gateway.calls == 1
    if source == "payload" or field != "total_cost_usd":
        assert gateway.normalized_response.usage.cost_usd == 1
    assert_no_receipt_after_invalid_intake(path)


@pytest.mark.parametrize("source", ["usage", "payload"])
@pytest.mark.asyncio
async def test_native_raw_component_overflow_refused_with_normalized_marker_retained(
    tmp_path, source
):
    payload = raw_payload({"total_cost_usd": 1})
    target = payload["usage"] if source == "usage" else payload
    target.update(base_cost_usd="1e308", platform_fee_usd="1e308")
    gateway = RawGateway(payload)
    path, enforcer = build(tmp_path, gateway)
    with pytest.raises(ValueError, match="provider cost"):
        await invoke(enforcer)
    assert gateway.calls == 1 and gateway.normalized_response.usage.cost_usd == 1
    assert_no_receipt_after_invalid_intake(path)


@pytest.mark.parametrize("amount", [0, 1])
@pytest.mark.asyncio
async def test_native_raw_finite_zero_and_paid_receipt_settle_exact_amount(tmp_path, amount):
    gateway = RawGateway(raw_payload({"cost_usd": amount}))
    path, enforcer = build(tmp_path, gateway)
    response = await invoke(enforcer)
    assert response.raw["usage"]["cost_usd"] == amount and gateway.calls == 1
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal(amount)
    assert snapshot.state.remaining("run") == Decimal(5 - amount)
    assert snapshot.state.reserved["run"] == 0
    receipt = next(iter(snapshot.spend_receipts.values()))
    assert receipt.amount == Decimal(amount)
    assert receipt.key == "run" and receipt.provider == "provider-a"
    assert len(receipt.payload_digest) == 64


@pytest.mark.asyncio
async def test_native_raw_conflicting_zero_and_paid_alias_refused_after_falsy_normalization(
    tmp_path,
):
    gateway = RawGateway(raw_payload({"total_cost_usd": 0, "cost_usd": 4}))
    path, enforcer = build(tmp_path, gateway)
    with pytest.raises(ValueError, match="conflicting provider cost"):
        await invoke(enforcer)
    assert gateway.normalized_response.usage.cost_usd == 4
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {} and snapshot.spend_receipts == {}


@pytest.mark.parametrize("normalized_amount", [None, 1])
@pytest.mark.asyncio
async def test_raw_unavailable_is_distinct_from_invalid_raw_receipt(
    tmp_path, monkeypatch, normalized_amount
):
    class SDKWithoutRaw:
        async def generate(self, **kwargs):
            return GatewayLLMResponse(
                content="observed SDK response",
                usage=GatewayUsage(cost_usd=normalized_amount),
                provider="provider-a",
                request_id="request-1",
                raw=None,
            )

    path, enforcer = build(tmp_path, SDKWithoutRaw())
    events = []
    original = enforcer._settle_event

    def observe(event, *args):
        events.append(event)
        return original(event, *args)

    monkeypatch.setattr(enforcer, "_settle_event", observe)
    await invoke(enforcer)
    snapshot = FileBudgetLedger(path).snapshot()
    receipt = next(iter(snapshot.spend_receipts.values()))
    assert len(events) == 1
    assert events[0].cost_origin == ("estimated" if normalized_amount is None else "reported")
    assert snapshot.state.spent["run"] == receipt.amount == events[0].amount
    if normalized_amount is not None:
        assert receipt.amount == Decimal(1)
