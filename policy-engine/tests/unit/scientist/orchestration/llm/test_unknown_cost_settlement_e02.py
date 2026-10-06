"""B66: unknown provider usage cannot acquire a durable zero-cost receipt.

The synthetic provider performs one real, gated operation. The normalizer,
tracing, cache, middleware and initialized filesystem ledger are canonical.
Known reported zero and known priced usage remain legitimate controls.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.llm import response, settlement, traced_client
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.engine import budget_ledger, budget_middleware
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm import budget_enforcer, gateway_client, prompt_cache
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

_UNKNOWN = ("sdk-missing-usage", "sdk-invalid-usage", "raw-none-default-usage", "none-response")
_KNOWN = ("reported-positive", "reported-zero", "priced-known-usage", "priced-free-usage")


class _Span:
    def __enter__(self) -> _Span:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def set_attribute(self, *_args: Any) -> None:
        return None

    def set_status(self, *_args: Any) -> None:
        return None

    def record_exception(self, *_args: Any) -> None:
        return None


def _assert_source_custody() -> list[dict[str, Any]]:
    default_root = Path(__file__).resolve().parents[5].parent
    root = Path(os.environ.get("E02_B66_TARGET_ROOT", str(default_root))).resolve()
    expected_sha = os.environ.get("E02_B66_TARGET_SHA")
    if expected_sha is not None:
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True)
        assert head.strip() == expected_sha
    rows = []
    for module in (
        response,
        settlement,
        traced_client,
        budget_enforcer,
        prompt_cache,
        gateway_client,
        budget_ledger,
        budget_middleware,
    ):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root / "policy-engine" / "src"), path
        data = path.read_bytes()
        if expected_sha is not None:
            expected = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{expected_sha}:{path.relative_to(root)}"]
            )
            assert data == expected, path
        rows.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return rows


def _actual_response(kind: str, model: str) -> Any:
    if kind == "none-response":
        return None
    if kind == "reported-zero":
        return GatewayLLMResponse(
            content="actual completed response",
            model=model,
            provider="synthetic-operation",
            usage=GatewayUsage(cost_usd=0.0),
            raw=None,
        )
    payload: dict[str, Any] = {
        "choices": [{"message": {"content": "actual completed response"}}],
        "model": model,
        "provider": "synthetic-operation",
    }
    if kind == "sdk-invalid-usage":
        payload["usage"] = {
            "prompt_tokens": "invalid",
            "completion_tokens": None,
            "cost_usd": "invalid",
        }
    elif kind in {"reported-positive", "priced-known-usage", "priced-free-usage"}:
        payload["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
        if kind == "reported-positive":
            payload["usage"]["cost_usd"] = 0.02
    # Exercise the real supported gateway payload decoder, not a copied parser.
    sdk = GatewayLLMClient(base_url="https://oracle.invalid/v1", api_key="fixture", model=model)
    actual = sdk._parse_completion_payload(payload)
    if kind in {"reported-positive", "raw-none-default-usage"}:
        actual.raw = None
    return actual


class _PhysicalProvider:
    def __init__(self, root: Path, kind: str, model: str) -> None:
        self.path = root / "actual-provider-work.jsonl"
        self.kind = kind
        self.model = model
        self.calls = 0
        self.response: Any = None
        self.input_summary: dict[str, Any] = {}
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, **kwargs: Any) -> Any:
        self.calls += 1
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"call": self.calls, "request": kwargs}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.started.set()
        await self.release.wait()
        self.response = _actual_response(self.kind, self.model)
        parsed = extract_llm_response_data(self.response)
        self.input_summary = {
            "response_type": type(self.response).__name__,
            "prompt_tokens": parsed.prompt_tokens,
            "completion_tokens": parsed.completion_tokens,
            "cost_usd": parsed.cost_usd,
            "raw_is_none": getattr(self.response, "raw", None) is None,
        }
        return self.response


def _event_view(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "amount": str(event.amount),
        "cost_origin": event.cost_origin,
        "kind": event.kind,
        "payload_digest": event.payload_digest,
    }


async def _exercise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, cancelled: bool
) -> tuple[Any, dict[str, Any]]:
    source_origins = _assert_source_custody()
    model = "configured-free-model" if kind == "priced-free-usage" else "gpt-4o"
    if kind == "priced-free-usage":
        # Public pricing configuration is a legitimate known-price-zero control.
        monkeypatch.setenv("POLISYOS_LLM_DEFAULT_INPUT_USD", "0")
        monkeypatch.setenv("POLISYOS_LLM_DEFAULT_OUTPUT_USD", "0")
    provider = _PhysicalProvider(tmp_path, kind, model)
    cache = CachingLLMClient(provider, cache=InMemoryPromptCache(), model=model)
    records: list[dict[str, Any]] = []
    traced = TracedLLMClient(
        cache,
        model_name=model,
        cache_reuse_owner=cache._cache_reuse_owner,
        tracer=SimpleNamespace(start_as_current_span=lambda *_args, **_kwargs: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_kwargs: None),
        required_accounting=lambda event: records.append(dict(event)),
    )
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path, ledger_id="ledger:unknown-cost-oracle")
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}), ledger=ledger
    )
    enforcer = LLMBudgetEnforcer(
        client=traced,
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name=model,
        run_id="unknown-cost-oracle",
    )
    events, acks = [], []
    actual_settle = enforcer._settle_event

    def observe_settlement(event, actual_response, reservation, run_id):
        events.append(_event_view(event))
        ack = actual_settle(event, actual_response, reservation, run_id)
        acks.append(
            {
                "status": ack.status,
                "durability": ack.durability,
                "event_id": ack.event_id,
                "receipts": [receipt.model_dump(mode="json") for receipt in ack.receipts],
            }
        )
        return ack

    monkeypatch.setattr(enforcer, "_settle_event", observe_settlement)
    caller = asyncio.create_task(
        enforcer.generate(
            user="nonempty actual request", max_tokens=2, _prompt_tokens_estimate=1, temperature=0.0
        )
    )
    await asyncio.wait_for(provider.started.wait(), timeout=2)
    owned = tuple(enforcer._owned_calls)
    assert len(owned) == 1
    reserved_before = middleware.budget_state.reserved.get("run", Decimal(0))
    if kind in _UNKNOWN:
        assert reserved_before > 0
    if cancelled:
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
    provider.release.set()
    completed = await asyncio.gather(*owned, return_exceptions=True)
    result = completed[0]
    if not cancelled:
        await asyncio.gather(caller, return_exceptions=True)
    snapshot = FileBudgetLedger(path, ledger_id="ledger:unknown-cost-oracle").snapshot()
    work = [json.loads(line) for line in provider.path.read_text().splitlines()]
    output = {
        "profile": kind,
        "caller_cancelled": cancelled,
        "source_origins": source_origins,
        "provider_calls": provider.calls,
        "actual_provider_work": work,
        "input_normalization": provider.input_summary,
        "reserved_before_completion": str(reserved_before),
        "result_exception": type(result).__name__ if isinstance(result, BaseException) else None,
        "observed_events": events,
        "actual_acks": acks,
        "required_callback_events": len(records),
        "cache_entries": cache._cache.size,
        "fresh_ledger_snapshot": snapshot.model_dump(mode="json"),
    }
    print("B66_ACTUAL " + json.dumps(output, sort_keys=True))
    assert provider.calls == len(work) == 1
    assert not enforcer._owned_calls and not traced._owned_calls and not cache._inflight
    return result, output


@pytest.mark.parametrize("kind", _UNKNOWN)
@pytest.mark.parametrize("cancelled", [False, True])
def test_unknown_usage_cannot_publish_zero_ack_after_actual_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, cancelled: bool
) -> None:
    result, output = asyncio.run(_exercise(tmp_path, monkeypatch, kind, cancelled))
    assert isinstance(result, LLMAccountingError), output
    assert result.event["settlement_status"] == "unknown"
    assert not output["actual_acks"]
    assert output["cache_entries"] == 0
    assert not output["fresh_ledger_snapshot"]["spend_receipts"]
    assert Decimal(output["fresh_ledger_snapshot"]["state"]["reserved"]["run"]) > 0


@pytest.mark.parametrize("kind", _KNOWN)
@pytest.mark.parametrize("cancelled", [False, True])
def test_known_usage_and_price_preserve_legitimate_charge_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, cancelled: bool
) -> None:
    result, output = asyncio.run(_exercise(tmp_path, monkeypatch, kind, cancelled))
    assert not isinstance(result, BaseException), output
    settled = producer_settlement(result)
    assert settled is not None
    assert settled.ack.status == "committed" and settled.ack.durability == "ledger"
    assert settled.event.kind == "provider" and len(settled.ack.receipts) == 1
    assert output["cache_entries"] == 1
    assert Decimal(output["fresh_ledger_snapshot"]["state"]["reserved"]["run"]) == 0
    if kind == "reported-positive":
        assert settled.event.amount == Decimal("0.02") and settled.event.cost_origin == "reported"
    elif kind == "reported-zero":
        assert settled.event.amount == 0 and settled.event.cost_origin == "reported"
    else:
        assert settled.event.cost_origin == "estimated"
        assert (settled.event.amount == 0) is (kind == "priced-free-usage")
    assert settled.ack.receipts[0].amount == settled.event.amount
    assert Decimal(output["fresh_ledger_snapshot"]["state"]["spent"]["run"]) == settled.event.amount
