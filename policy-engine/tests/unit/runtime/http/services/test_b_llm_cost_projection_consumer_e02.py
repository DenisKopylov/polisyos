"""B66 producer/ledger truth and the A-owned optional-spend projection seam.

Two independent physical calls exercise the optional served tracing profile and
the mandatory ledger profile. This is not a served HTTP admission receipt.
"""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.runtime.http.services.control.response_shapes import _sum_call_events
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient


class _FileProvider:
    def __init__(self, path: Path, kind: str) -> None:
        self.path = path
        self.kind = kind
        self.calls = 0

    async def generate(self, **kwargs: Any) -> Any:
        self.calls += 1
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"call": self.calls, "request": kwargs}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        payload: dict[str, Any] = {
            "model": "gpt-4o",
            "provider": "physical-file-oracle",
            "choices": [{"message": {"content": "obtained response"}}],
        }
        if self.kind != "unknown":
            payload["usage"] = {"prompt_tokens": 7, "completion_tokens": 3}
            if self.kind != "estimated":
                payload["usage"]["cost_usd"] = 0.0 if self.kind == "reported-zero" else 0.02
        sdk = GatewayLLMClient(base_url="https://oracle.invalid", api_key="fixture", model="gpt-4o")
        return sdk._parse_completion_payload(payload)


def _traced(provider: _FileProvider, events: list[dict[str, Any]]) -> TracedLLMClient:
    return TracedLLMClient(
        provider,
        model_name="gpt-4o",
        run_id="projection-consumer",
        call_observer=events.append,
        metrics=SimpleNamespace(record_llm_call=lambda **_kwargs: None),
    )


async def _exercise(tmp_path: Path, kind: str) -> dict[str, Any]:
    optional_provider = _FileProvider(tmp_path / "optional-provider.jsonl", kind)
    optional_events: list[dict[str, Any]] = []
    optional_result = await _traced(optional_provider, optional_events).generate(user="optional")
    assert optional_result.content == "obtained response"
    assert optional_provider.calls == len(optional_events) == 1
    optional_event = optional_events[0]
    projection = _sum_call_events(optional_events)

    mandatory_provider = _FileProvider(tmp_path / "mandatory-provider.jsonl", kind)
    mandatory_events: list[dict[str, Any]] = []
    path = tmp_path / "budget.json"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))}),
        ledger=FileBudgetLedger(path, ledger_id="projection-ledger"),
    )
    enforcer = LLMBudgetEnforcer(
        client=_traced(mandatory_provider, mandatory_events),
        budget_state=middleware.budget_state,
        budget_middleware=middleware,
        budget_keys=["run"],
        model_name="gpt-4o",
        run_id="projection-consumer",
    )
    ack = None
    if kind == "unknown":
        with pytest.raises(LLMAccountingError) as caught:
            await enforcer.generate(user="mandatory", max_tokens=2, _prompt_tokens_estimate=1)
        event = caught.value.event["producer_event"]
        assert event.amount is None and event.cost_origin == "unknown"
        snapshot = FileBudgetLedger(path, ledger_id="projection-ledger").snapshot()
        assert not snapshot.spend_receipts
        pending = [r for r in snapshot.completion_obligations.values() if r.phase == "cost_unknown"]
        assert len(pending) == 1 and pending[0].event_digest == event.payload_digest
        fresh = BudgetMiddleware(
            BudgetState(), ledger=FileBudgetLedger(path, ledger_id="projection-ledger")
        )
        sibling = LLMBudgetEnforcer(
            client=_traced(mandatory_provider, []),
            budget_state=fresh.budget_state,
            budget_middleware=fresh,
            budget_keys=["run"],
            model_name="gpt-4o",
            run_id="fresh-reader",
        )
        with pytest.raises(LLMAccountingError):
            await sibling.generate(user="must-not-enter", max_tokens=2, _prompt_tokens_estimate=1)
        assert mandatory_provider.calls == 1
        assert mandatory_events == []  # Required settlement refuses before optional emission.
    else:
        result = await enforcer.generate(user="mandatory", max_tokens=2, _prompt_tokens_estimate=1)
        settled = producer_settlement(result)
        assert settled is not None
        event, ack = settled.event, settled.ack
        assert ack.status == "committed" and ack.durability == "ledger"
        assert ack.event_id == event.event_id and ack.payload_digest == event.payload_digest
        snapshot = FileBudgetLedger(path, ledger_id="projection-ledger").snapshot()
        assert len(ack.receipts) == len(snapshot.spend_receipts) == 1
        assert snapshot.state.spent["run"] == event.amount
        assert next(iter(snapshot.spend_receipts.values())).event_id == ack.receipts[0].event_id
        assert len(mandatory_events) == mandatory_provider.calls == 1
    expected_origin = (
        "unknown" if kind == "unknown" else "estimated" if kind == "estimated" else "reported"
    )
    assert event.cost_origin == optional_event["cost_origin"] == expected_origin
    assert optional_event["cost_usd"] == (float(event.amount) if event.amount is not None else None)
    assert optional_event["provider_call"] is True and optional_event["cache_hit"] is False
    physical = {
        label: [json.loads(line) for line in provider.path.read_text().splitlines()]
        for label, provider in (("optional", optional_provider), ("mandatory", mandatory_provider))
    }
    assert all(len(rows) == 1 for rows in physical.values())
    return {
        "kind": kind,
        "physical_work": physical,
        "optional_actual_observer_event": optional_event,
        "actual_A_projection": projection,
        "mandatory_event": {
            "event_id": event.event_id,
            "amount": str(event.amount) if event.amount is not None else None,
            "cost_origin": event.cost_origin,
            "kind": event.kind,
            "payload_digest": event.payload_digest,
            "request_digest": event.request_digest,
        },
        "mandatory_ack": {
            "event_id": ack.event_id,
            "status": ack.status,
            "durability": ack.durability,
            "receipts": [r.model_dump(mode="json") for r in ack.receipts],
        }
        if ack is not None
        else None,
        "fresh_ledger_snapshot": snapshot.model_dump(mode="json"),
        "route_scope": "optional tracing versus independent mandatory accounting; not HTTP",
    }


@pytest.mark.parametrize("kind", ["unknown", "reported-zero", "reported-positive", "estimated"])
def test_producer_ledger_truth_survives_a_optional_projection(tmp_path: Path, kind: str) -> None:
    observed = asyncio.run(_exercise(tmp_path, kind))
    print("B_A_CONSUMER_ACTUAL " + json.dumps(observed, sort_keys=True))
    expected = observed["optional_actual_observer_event"]["cost_usd"]
    assert observed["actual_A_projection"]["cost_usd"] == expected, (
        "A projection must distinguish unknown provider cost from reported or estimated zero"
    )
