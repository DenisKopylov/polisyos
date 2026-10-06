"""Real LLM accounting consumer, prompt cache, and durable settlement boundary.

The transport fixture returns provider bytes, not a billing-service attestation.
No tariff or duration is used as the expected measured amount.
"""

from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prompt_cache import CachingLLMClient, InMemoryPromptCache


class ProviderTransport:
    """Deterministic provider transport; each physical request has its own ID."""

    def __init__(self, cost=1.0):
        self.calls = 0
        self.cost = cost

    def invoke(self, prompt, **kwargs):
        assert all(not key.startswith("_") for key in kwargs)
        self.calls += 1
        return GatewayLLMResponse(
            content="observed response",
            provider="provider-a",
            request_id=f"request-{self.calls}",
            usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, cost_usd=self.cost),
        )

    async def generate(self, **kwargs):
        return self.invoke(kwargs.get("user", ""), **kwargs)


def build(tmp_path, transport):
    path = tmp_path / "ledger.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    middleware = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    enforcer = LLMBudgetEnforcer(
        client=transport,
        budget_state=state,
        budget_keys=["run"],
        run_id="run-1",
        model_name="test-model",
        budget_middleware=middleware,
    )
    return path, middleware, enforcer


def test_sync_real_caller_settles_full_receipt_and_fresh_reopen(tmp_path):
    transport = ProviderTransport()
    path, middleware, enforcer = build(tmp_path, transport)
    enforcer.invoke("hello", _prompt_tokens_estimate=1, max_tokens=1, _evaluation_id="evaluation-1")
    assert transport.calls == 1
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {"run": Decimal("1")}
    assert snapshot.state.remaining("run") == Decimal("4")
    assert snapshot.state.reserved["run"] == 0
    assert enforcer.budget_state == middleware.budget_state == snapshot.state
    receipt = next(iter(snapshot.resource_events.values()))
    assert receipt.request_id == "request-1"
    assert receipt.evaluation_id == "evaluation-1"
    assert receipt.source == "provider_reported"


@pytest.mark.asyncio
async def test_actual_cache_reuse_is_zero_new_charge_and_retry_is_new_charge(tmp_path):
    transport = ProviderTransport()
    cached = CachingLLMClient(transport, cache=InMemoryPromptCache(), model="test-model")
    path, _, enforcer = build(tmp_path, cached)
    for user in ("one", "one", "two"):
        await enforcer.generate(user=user, temperature=0, _prompt_tokens_estimate=1, max_tokens=1)
    snapshot = FileBudgetLedger(path).snapshot()
    assert transport.calls == 2
    assert snapshot.state.spent["run"] == Decimal("2")
    assert snapshot.state.remaining("run") == Decimal("3")
    assert snapshot.state.reserved["run"] == 0
    assert sorted(event.amount_usd for event in snapshot.resource_events.values()) == [
        Decimal("0"),
        Decimal("1"),
        Decimal("1"),
    ]
    reuse = [event for event in snapshot.resource_events.values() if event.source == "cache_reuse"]
    assert len(reuse) == 1 and reuse[0].reuse_event_id


@pytest.mark.parametrize("missing", ["cost", "request", "provider"])
def test_missing_provider_measurement_is_pending_not_estimated_spend(tmp_path, missing):
    class MissingTransport(ProviderTransport):
        def invoke(self, prompt, **kwargs):
            result = super().invoke(prompt, **kwargs)
            if missing == "cost":
                result.usage.cost_usd = None
            elif missing == "request":
                result.request_id = None
            else:
                result.provider = None
            return result

    path, _, enforcer = build(tmp_path, MissingTransport())
    with pytest.raises(ValueError, match="measured provider"):
        enforcer.invoke("hello", _prompt_tokens_estimate=1, max_tokens=1)
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {}
    assert snapshot.state.reserved["run"] > 0
    assert not snapshot.resource_events
    assert next(iter(snapshot.resource_reservations.values())).status == "reconciliation_required"


def test_paid_call_remains_settled_when_later_consumer_fails(tmp_path):
    path, _, enforcer = build(tmp_path, ProviderTransport())

    def consume_then_fail():
        enforcer.invoke("hello", _prompt_tokens_estimate=1, max_tokens=1)
        raise RuntimeError("downstream failure")

    with pytest.raises(RuntimeError, match="downstream failure"):
        consume_then_fail()
    assert FileBudgetLedger(path).load().spent["run"] == Decimal("1")
    assert FileBudgetLedger(path).load().reserved["run"] == 0
