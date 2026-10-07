"""Native cache issuer -> D funnel intake -> fresh canonical ledger controls.

Only the HTTP exchange is controlled. This bounded configured caller does not
appoint an invoice authority, production blueprint caller or promotion issuer.
"""

import asyncio
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from typing import ClassVar

import pytest

from polisyos.core.llm.settlement import (
    LLMProducerEvent,
    LLMProducerSettlement,
    LLMSettledResponse,
    LLMSettlementAck,
    producer_settlement,
)
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.methods.search.funnel import types as funnel_types
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import observe_funnel_resource_response
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine


def _funnel(tmp_path, evaluate):
    path = tmp_path / "budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))

    def step(runtime):
        evaluate(owner)
        return {
            **runtime,
            "simulation_results": {"gdp_change": 0, "bootstrap": {"ci_width": 0}},
            "feedback": {"verdict": "APPROVE"},
        }

    engine = SimpleLoopEngine([("evaluate", step)], "evaluate")
    funnel = FunnelOrchestrator([Level3MediumFidelity(engine)], budget_middleware=owner)
    ticket = funnel.submit({"candidate_id": "candidate-1"}, {"run_id": "run-1"})
    return path, owner, funnel, ticket


@pytest.mark.parametrize(
    ("amount", "cost_origin", "origin"),
    [
        ("0", "reuse", None),
        ("0", "reuse", "unresolved-paid-origin"),
        ("1", "reported", None),
        ("1", "reported", "unresolved-paid-origin"),
        ("1", "reuse", "unresolved-paid-origin"),
    ],
)
def test_typed_reuse_marker_without_real_cache_issuer_is_rejected(
    tmp_path, amount, cost_origin, origin
):
    def evaluate(owner):
        content = "same markers, no cache owner or origin receipt"
        event = LLMProducerEvent(
            "forged-reuse",
            "arbitrary-request",
            "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
            "fixture-model",
            "fixture-provider",
            Decimal(amount),
            cost_origin,
            kind="reuse",
            origin_event_id=origin,
        )
        ack = LLMSettlementAck(event.event_id, event.payload_digest, "committed", (), "ledger")
        response = SimpleNamespace(
            content=content,
            model="fixture-model",
            provider="fixture-provider",
            usage=None,
            _polisyos_cache_hit=True,
            _polisyos_reuse_event_id=event.event_id,
        )
        observe_funnel_resource_response(
            LLMSettledResponse(response, LLMProducerSettlement(event, ack))
        )

    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert outcome.final_action == "reject"
    assert outcome.provider_spend_usd is None
    assert outcome.resource_event_ids == ()
    assert snapshot.state.spent == {} and snapshot.spend_receipts == {}


def _configured_cached_calls(monkeypatch, *, after_paid=None, after_reuse=None):
    calls = []
    returned = []

    class HTTPResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"x-request-id": "fixture-paid-origin"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def text(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": "content-bound native response"}}],
                    "model": "fixture-model",
                    "provider": "fixture-provider",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 1},
                }
            )

    class HTTPSession:
        def post(self, *args, **kwargs):
            calls.append(kwargs["json"])
            return HTTPResponse()

        async def close(self):
            pass

    async def transport_only(self, timeout_s):
        return HTTPSession()

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "https://fixture.invalid")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-fixture-native-transport")
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "false")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "16")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "3600")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    monkeypatch.setattr(GatewayLLMClient, "_ensure_session", transport_only)

    def evaluate(owner):
        client = create_traced_gateway_client(model_name="fixture-model", run_id="run-1")
        assert client is not None
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=owner.budget_state,
            budget_middleware=owner,
            budget_keys=["run"],
            model_name="fixture-model",
            run_id="run-1",
        )

        async def generate():
            first = await enforcer.generate(
                user="identical request", max_tokens=1, _prompt_tokens_estimate=1
            )
            returned.append(first)
            observe_funnel_resource_response(first)
            if after_paid is not None:
                after_paid(owner, first)
            reused = await enforcer.generate(
                user="identical request", max_tokens=1, _prompt_tokens_estimate=1
            )
            returned.append(reused)
            if after_reuse is not None:
                after_reuse(reused)
            # At this real returned-response seam the cache receiver context is
            # closed. Only the earlier verified event may be repeated here.
            observe_funnel_resource_response(reused)

        asyncio.run(generate())

    return evaluate, calls, returned


def test_configured_native_cache_reuse_binds_paid_origin_and_fresh_readback(tmp_path, monkeypatch):
    evaluate, calls, returned = _configured_cached_calls(monkeypatch)
    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    original, reused = [producer_settlement(response) for response in returned]
    assert outcome.final_action == "complete"
    assert outcome.provider_spend_usd == Decimal("1")
    assert outcome.compute_cost_source == "provider_reported_only"
    assert len(calls) == 1 and len(snapshot.spend_receipts) == 1
    assert snapshot.state.spent["run"] == 1 and snapshot.state.reserved["run"] == 0
    assert original.event.kind == "provider" and reused.event.kind == "reuse"
    assert reused.event.amount == 0 and reused.event.origin_event_id == original.event.event_id
    assert tuple(snapshot.spend_receipts.values()) == original.ack.receipts
    assert outcome.resource_event_ids == (original.event.event_id, reused.event.event_id)


@pytest.mark.parametrize(
    "changed", ["content", "origin_receipts", "origin_amount", "origin_request"]
)
def test_returned_cache_tamper_rejects_after_original_issuer_check(tmp_path, monkeypatch, changed):
    def tamper(reused):
        # Keep the outer issuer seal, kind, IDs, ACK and raw cache markers.
        if changed == "content":
            reused.response.content = "changed returned content"
            return
        original = producer_settlement(reused.response)
        if changed == "origin_receipts":
            ack = replace(original.ack, receipts=())
            event = original.event
        else:
            event = replace(
                original.event,
                **(
                    {"amount": Decimal("0")}
                    if changed == "origin_amount"
                    else {"request_digest": "changed-request"}
                ),
            )
            ack = replace(original.ack, payload_digest=event.payload_digest)
        reused.response._polisyos_settlement = LLMProducerSettlement(event, ack)

    evaluate, calls, returned = _configured_cached_calls(monkeypatch, after_reuse=tamper)
    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert outcome.final_action == "reject"
    assert len(calls) == 1 and len(returned) == 2
    assert snapshot.state.spent["run"] == 1 and len(snapshot.spend_receipts) == 1
    assert producer_settlement(returned[1]).event.kind == "reuse"
    assert returned[1].raw["_polisyos_cache"]["status"] == "hit"


def test_real_paid_receipt_without_cache_issuer_cannot_grant_free_reuse(tmp_path, monkeypatch):
    def unissued_reuse(owner, first):
        original = producer_settlement(first)
        event = replace(
            original.event,
            event_id="forged-reuse-with-real-origin",
            amount=Decimal("0"),
            cost_origin="reuse",
            kind="reuse",
            origin_event_id=original.event.event_id,
        )
        ack = LLMSettlementAck(event.event_id, event.payload_digest, "committed", (), "ledger")
        # Genuine paid content and receipts, no runtime cache issuer capability.
        observe_funnel_resource_response(
            LLMSettledResponse(first, LLMProducerSettlement(event, ack))
        )

    evaluate, calls, returned = _configured_cached_calls(monkeypatch, after_paid=unissued_reuse)
    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert outcome.final_action == "reject"
    assert len(calls) == 1 and len(returned) == 1
    assert outcome.resource_event_ids == (producer_settlement(returned[0]).event.event_id,)
    assert snapshot.state.spent["run"] == 1 and len(snapshot.spend_receipts) == 1


def test_receiver_proof_removal_keeps_markers_but_refuses_new_reuse(tmp_path, monkeypatch):
    actual_observer = funnel_types.observe_funnel_resource_response

    def remove_live_receiver_observation(response):
        if producer_settlement(response).event.kind != "reuse":
            actual_observer(response)

    # Remove D's early consumer bridge, retain the real cache issue/ACK and
    # later native response observation. No new issuer is supplied by the test.
    monkeypatch.setattr(
        funnel_types, "observe_funnel_resource_response", remove_live_receiver_observation
    )
    evaluate, calls, returned = _configured_cached_calls(monkeypatch)
    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert outcome.final_action == "reject"
    assert len(calls) == 1 and len(returned) == 2
    assert producer_settlement(returned[1]).event.kind == "reuse"
    assert returned[1].raw["_polisyos_cache"]["status"] == "hit"
    assert len(outcome.resource_event_ids) == 1
    assert snapshot.state.spent["run"] == 1 and len(snapshot.spend_receipts) == 1


def test_missing_paid_origin_readback_cannot_admit_free_reuse(tmp_path, monkeypatch):
    def remove_readback(owner, first):
        monkeypatch.setattr(owner, "resolve_spend_safe", lambda event_id: None)

    evaluate, calls, returned = _configured_cached_calls(monkeypatch, after_paid=remove_readback)
    path, _, funnel, ticket = _funnel(tmp_path, evaluate)
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert outcome.final_action == "reject"
    assert len(calls) == 1 and len(returned) == 1
    assert outcome.provider_spend_usd == 1
    assert snapshot.state.spent["run"] == 1 and len(snapshot.spend_receipts) == 1
    assert tuple(snapshot.spend_receipts.values()) == producer_settlement(returned[0]).ack.receipts


@pytest.mark.parametrize("remove_readback", [False, True])
def test_standalone_configured_enforcer_binds_native_cache_to_fresh_paid_receipt(
    tmp_path, monkeypatch, remove_readback
):
    path = tmp_path / "budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))

    def after_paid(owner, response):
        if remove_readback:
            monkeypatch.setattr(owner, "resolve_spend_safe", lambda event_id: None)

    evaluate, calls, returned = _configured_cached_calls(monkeypatch, after_paid=after_paid)
    # No external funnel receipt context: the ordinary enforcer supplies its
    # configured owner's existing exact readback port for native cache intake.
    if remove_readback:
        with pytest.raises(LLMAccountingError):
            evaluate(owner)
    else:
        evaluate(owner)
    snapshot = FileBudgetLedger(path).snapshot()
    assert len(calls) == 1 and len(snapshot.spend_receipts) == 1
    original = producer_settlement(returned[0])
    assert original.event.kind == "provider" and original.event.amount == 1
    assert tuple(snapshot.spend_receipts.values()) == original.ack.receipts
    assert snapshot.state.spent == {"run": Decimal("1")}
    if not remove_readback:
        reused = producer_settlement(returned[1])
        assert reused.event.kind == "reuse" and reused.event.amount == 0
        assert reused.event.origin_event_id == original.event.event_id
        assert snapshot.state.reserved["run"] == 0 and snapshot.completion_obligations == {}
    else:
        assert len(returned) == 1


def test_supported_invoke_adapter_runs_native_response_decoder_and_reopens_paid_receipt(tmp_path):
    from pathlib import Path
    from runpy import run_path

    root = Path(__file__).resolve().parents[6]
    text = run_path(str(root / "tests/integration/core/llm/test_gateway_response_text_cost.py"))

    class NativeInvokeHTTP(text["TextGateway"]):
        # Supported invoke SDK shape; Gateway's default factory exposes
        # generate only. The actual _post_json and decoder remain unchanged.
        def invoke(self, prompt, **kwargs):
            return asyncio.run(self.generate(user=prompt, **kwargs))

    gateway = NativeInvokeHTTP(text["response_text"]("usage", "cost_usd", "1"))
    path = tmp_path / "budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    enforcer = LLMBudgetEnforcer(
        client=TracedLLMClient(gateway, model_name="test-model"),
        budget_state=state,
        budget_middleware=owner,
        budget_keys=["run"],
        model_name="test-model",
        run_id="invoke-run",
    )
    response = enforcer.invoke("actual request", max_tokens=1, _prompt_tokens_estimate=1)
    settlement = producer_settlement(response)
    snapshot = FileBudgetLedger(path).snapshot()
    assert gateway.transport.calls == 1 and gateway.normalized_response.usage.cost_usd == 1
    assert settlement.event.kind == "provider" and settlement.event.amount == 1
    assert snapshot.state.spent == {"run": Decimal("1")}
    assert snapshot.state.reserved["run"] == 0 and snapshot.completion_obligations == {}
    assert tuple(snapshot.spend_receipts.values()) == settlement.ack.receipts
    assert (
        BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path)).resolve_spend_safe(
            settlement.ack.receipts[0].event_id
        )
        == settlement.ack.receipts[0]
    )
