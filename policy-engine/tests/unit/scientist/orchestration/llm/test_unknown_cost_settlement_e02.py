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
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.llm import response, settlement, traced_client
from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.settlement import _settlement_owner_context, producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.engine import budget_ledger, budget_middleware
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm import budget_enforcer, gateway_client, prompt_cache
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    GatewayLLMResponse,
    GatewayUsage,
)
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)

_UNKNOWN = (
    "sdk-missing-usage",
    "sdk-invalid-usage",
    "raw-none-default-usage",
    "none-response",
    "negative-cost",
    "nan-cost",
    "infinite-cost",
    "fractional-usage",
    "boolean-usage",
    "cost-accessor-fault",
    "positive-cost-underflow",
    "negative-cost-underflow",
    "input-token-accessor-fault",
)
_KNOWN = (
    "reported-positive",
    "reported-zero",
    "priced-known-usage",
    "priced-free-usage",
    "priced-known-zero-usage",
)


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
    if kind == "input-token-accessor-fault":

        class UnavailableInput:
            content = "actual completed response"
            provider = "synthetic-operation"
            request_id = "actual-provider-request"
            completion_tokens = 3
            raw = None

            @property
            def input_tokens(self) -> int:
                raise OSError("obtained input-token evidence is inaccessible")

        actual = UnavailableInput()
        actual.model = model
        return actual
    if kind == "cost-accessor-fault":

        class UnavailableCost:
            prompt_tokens = 7
            completion_tokens = 3

            @property
            def total_cost_usd(self) -> float:
                raise OSError("obtained provider cost evidence is inaccessible")

        return SimpleNamespace(
            content="actual completed response",
            model=model,
            provider="synthetic-operation",
            request_id="actual-provider-request",
            usage=UnavailableCost(),
            raw=None,
        )
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
    elif kind in {
        "reported-positive",
        "priced-known-usage",
        "priced-free-usage",
        "negative-cost",
        "nan-cost",
        "infinite-cost",
        "fractional-usage",
        "boolean-usage",
        "positive-cost-underflow",
        "negative-cost-underflow",
    }:
        payload["usage"] = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
        if kind == "reported-positive":
            payload["usage"]["cost_usd"] = 0.02
        elif kind in {
            "negative-cost",
            "nan-cost",
            "infinite-cost",
            "positive-cost-underflow",
            "negative-cost-underflow",
        }:
            payload["usage"]["cost_usd"] = {
                "negative-cost": -0.02,
                "nan-cost": "NaN",
                "infinite-cost": "Infinity",
                "positive-cost-underflow": "1e-1000",
                "negative-cost-underflow": "-1e-1000",
            }[kind]
        elif kind == "fractional-usage":
            payload["usage"]["prompt_tokens"] = 1.5
        elif kind == "boolean-usage":
            payload["usage"]["completion_tokens"] = True
    elif kind == "priced-known-zero-usage":
        payload["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
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

    def _write_actual_work(self, kwargs: dict[str, Any]) -> None:
        self.calls += 1
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"call": self.calls, "request": kwargs}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _complete(self) -> Any:
        if self.kind == "entered-provider-error":
            raise RuntimeError("provider completion unavailable after actual work")
        self.response = _actual_response(self.kind, self.model)
        parsed = extract_llm_response_data(self.response)
        self.input_summary = {
            "response_type": type(self.response).__name__,
            "prompt_tokens": parsed.prompt_tokens,
            "completion_tokens": parsed.completion_tokens,
            "cost_usd": parsed.cost_usd,
            "usage_status": parsed.usage_status,
            "cost_status": parsed.cost_status,
            "model": parsed.model,
            "provider": parsed.provider,
            "raw_is_none": getattr(self.response, "raw", None) is None,
        }
        return self.response

    async def generate(self, **kwargs: Any) -> Any:
        self._write_actual_work(kwargs)
        self.started.set()
        await self.release.wait()
        return self._complete()

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        self._write_actual_work({"prompt": prompt, **kwargs})
        return self._complete()

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        return await self.generate(prompt=prompt, **kwargs)


def _event_view(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "amount": str(event.amount) if event.amount is not None else None,
        "cost_origin": event.cost_origin,
        "kind": event.kind,
        "payload_digest": event.payload_digest,
        "request_digest": event.request_digest,
        "model": event.model,
        "provider": event.provider,
    }


async def _exercise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    cancelled: bool,
    *,
    reopened_owner: bool = False,
    direct_cache: bool = False,
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
        BudgetState(
            limits={key: BudgetLimit(key=key, max_usd=Decimal("10")) for key in ("run", "other")}
        ),
        ledger=ledger,
    )
    enforcer = LLMBudgetEnforcer(
        client=cache if direct_cache else traced,
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
    reopened = None
    if reopened_owner:
        fresh_middleware = BudgetMiddleware(
            BudgetState(limits={}),
            ledger=FileBudgetLedger(path, ledger_id="ledger:unknown-cost-oracle"),
        )
        sibling = LLMBudgetEnforcer(
            client=traced,
            budget_state=fresh_middleware.budget_state,
            budget_middleware=fresh_middleware,
            budget_keys=["run"],
            model_name=model,
            run_id="different-run-cannot-erase-same-budget-obligation",
        )
        try:
            await sibling.generate(user="new request", max_tokens=2, _prompt_tokens_estimate=1)
        except Exception as exc:
            sibling_error = type(exc).__name__
        else:
            sibling_error = None
        other_root = tmp_path / "other-budget-operation"
        other_root.mkdir()
        other_provider = _PhysicalProvider(other_root, "reported-positive", model)
        other_provider.release.set()
        other_client = TracedLLMClient(
            other_provider,
            model_name=model,
            tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
            metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
        )
        other = LLMBudgetEnforcer(
            client=other_client,
            budget_state=fresh_middleware.budget_state,
            budget_middleware=fresh_middleware,
            budget_keys=["other"],
            model_name=model,
            run_id="nonintersecting-budget-control",
        )
        other_result = await other.generate(
            user="other key", _prompt_tokens_estimate=1, max_tokens=2
        )
        other_settlement = producer_settlement(other_result)
        reopened = {
            "same_key_result_exception": sibling_error,
            "same_key_actual_provider_calls": provider.calls,
            "different_key_provider_calls": other_provider.calls,
            "different_key_charge": str(other_settlement.event.amount),
            "different_key_ack_status": other_settlement.ack.status,
        }
    snapshot = FileBudgetLedger(path, ledger_id="ledger:unknown-cost-oracle").snapshot()
    work = [json.loads(line) for line in provider.path.read_text().splitlines()]
    output = {
        "profile": kind,
        "caller_cancelled": cancelled,
        "direct_cache_without_traced": direct_cache,
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
        "reopened_owner": reopened,
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
        assert (settled.event.amount == 0) is (
            kind in {"priced-free-usage", "priced-known-zero-usage"}
        )
    assert settled.ack.receipts[0].amount == settled.event.amount
    assert Decimal(output["fresh_ledger_snapshot"]["state"]["spent"]["run"]) == settled.event.amount


@pytest.mark.parametrize("profile", ["required-accounting", "active-settlement", "unmanaged"])
def test_factory_streaming_cannot_bypass_configured_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    work = tmp_path / "stream-provider-work.jsonl"

    async def physical_stream(_client: Any, **kwargs: Any):
        with work.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(kwargs) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield "actual unmanaged stream"

    monkeypatch.setattr(GatewayLLMClient, "generate_stream", physical_stream)
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    client = create_traced_gateway_client(
        model_name="gpt-4o",
        config=GatewayLLMConfig(
            base_url="https://oracle.invalid/v1",
            api_key="fixture",
            cache_maxsize=0,
            enable_prompt_sanitizer=False,
        ),
        required_accounting=(lambda _event: None) if profile == "required-accounting" else None,
        tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
    )
    assert client is not None

    def unexpected_settlement(*_args: Any) -> None:
        raise AssertionError("unsupported streaming must refuse before provider/settlement")

    async def consume() -> list[Any]:
        context = (
            _settlement_owner_context(("trusted-test-composition",), unexpected_settlement)
            if profile == "active-settlement"
            else nullcontext()
        )
        with context:
            return [item async for item in client.generate_stream(user="actual stream request")]

    if profile == "unmanaged":
        assert asyncio.run(consume()) == ["actual unmanaged stream"]
        assert len(work.read_text().splitlines()) == 1
    else:
        with pytest.raises(NotImplementedError, match="settlement contract"):
            asyncio.run(consume())
        assert not work.exists()
    print(
        "B66_STREAM_ADMISSION "
        + json.dumps({"profile": profile, "actual_provider_work": work.exists()})
    )


@pytest.mark.parametrize("kind", _UNKNOWN)
@pytest.mark.parametrize("cancelled", [False, True])
def test_unknown_completion_blocks_reopened_intersecting_owner_before_actual_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, cancelled: bool
) -> None:
    result, output = asyncio.run(
        _exercise(tmp_path, monkeypatch, kind, cancelled, reopened_owner=True)
    )
    assert isinstance(result, LLMAccountingError)
    reopened = output["reopened_owner"]
    assert reopened["same_key_result_exception"] == "LLMAccountingError"
    assert reopened["same_key_actual_provider_calls"] == 1
    assert reopened["different_key_provider_calls"] == 1
    assert reopened["different_key_charge"] == "0.02"
    assert reopened["different_key_ack_status"] == "committed"
    assert not output["actual_acks"] and not output["fresh_ledger_snapshot"]["state"]["spent"].get(
        "run"
    )


@pytest.mark.parametrize("kind", _UNKNOWN)
@pytest.mark.parametrize("cancelled", [False, True])
def test_direct_cache_unknown_error_retires_owned_intent_into_pending_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, cancelled: bool
) -> None:
    result, output = asyncio.run(
        _exercise(tmp_path, monkeypatch, kind, cancelled, reopened_owner=True, direct_cache=True)
    )
    assert isinstance(result, LLMAccountingError)
    assert result.response is not None or kind == "none-response"
    assert result.event["producer_event"].amount is None
    assert output["cache_entries"] == 0 and not output["actual_acks"]
    pending = output["fresh_ledger_snapshot"]["completion_obligations"]
    assert len(pending) == 1
    assert next(iter(pending.values()))["phase"] == "cost_unknown"
    assert output["reopened_owner"]["same_key_actual_provider_calls"] == 1
    assert output["reopened_owner"]["same_key_result_exception"] == "LLMAccountingError"


@pytest.mark.parametrize("route", ["generate", "invoke", "ainvoke"])
@pytest.mark.parametrize("kind", ["sdk-missing-usage", "entered-provider-error", "reported-zero"])
def test_supported_accounting_ports_preserve_actual_work_knowledge_and_owner_gate(
    tmp_path: Path, kind: str, route: str
) -> None:
    _assert_source_custody()
    provider = _PhysicalProvider(tmp_path, kind, "gpt-4o")
    provider.release.set()
    client = TracedLLMClient(
        provider,
        model_name="gpt-4o",
        tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
    )
    path = tmp_path / "port-ledger.json"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(path),
    )
    owner = LLMBudgetEnforcer(
        client=client,
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="gpt-4o",
        run_id="real-port-knowledge",
    )

    def call(target: LLMBudgetEnforcer) -> Any:
        kwargs = {"_prompt_tokens_estimate": 1, "max_tokens": 2}
        if route == "invoke":
            return target.invoke("actual request", **kwargs)
        if route == "ainvoke":
            return asyncio.run(target.ainvoke("actual request", **kwargs))
        return asyncio.run(target.generate(user="actual request", **kwargs))

    if kind == "reported-zero":
        settled = producer_settlement(call(owner))
        assert settled.event.amount == 0 and settled.ack.status == "committed"
    else:
        with pytest.raises(LLMAccountingError) as error:
            call(owner)
        assert error.value.event["producer_event"].amount is None
        sibling = LLMBudgetEnforcer(
            client=client,
            budget_state=middleware.budget_state,
            budget_keys=["run"],
            budget_middleware=middleware,
            model_name="gpt-4o",
            run_id="same-live-owner-sibling",
        )
        with pytest.raises(LLMAccountingError):
            call(sibling)
    snapshot = FileBudgetLedger(path).snapshot()
    print(
        "B66_PUBLIC_PORT "
        + json.dumps(
            {
                "route": route,
                "kind": kind,
                "provider_calls": provider.calls,
                "actual_work": provider.path.read_text(),
                "fresh_ledger": snapshot.model_dump(mode="json"),
            }
        )
    )
    assert provider.calls == len(provider.path.read_text().splitlines()) == 1
    if kind != "reported-zero":
        assert not snapshot.spend_receipts and snapshot.state.reserved["run"] > 0
        assert next(iter(snapshot.completion_obligations.values())).phase == "cost_unknown"


def test_durable_missing_run_refuses_before_work_without_inventing_scope(tmp_path: Path) -> None:
    _assert_source_custody()
    provider = _PhysicalProvider(tmp_path, "reported-positive", "gpt-4o")
    provider.release.set()
    path = tmp_path / "explicit-run-ledger.json"
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(path),
    )
    owner = LLMBudgetEnforcer(
        client=TracedLLMClient(
            provider,
            model_name="gpt-4o",
            tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
            metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
        ),
        budget_state=middleware.budget_state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="gpt-4o",
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="explicit nonempty run_id"):
        asyncio.run(owner.generate(user="no known run", _prompt_tokens_estimate=1, max_tokens=2))
    assert path.read_bytes() == before and provider.calls == 0 and not provider.path.exists()
    result = asyncio.run(
        owner.generate(
            user="explicit actual run",
            _run_id="owner-supplied-run",
            _prompt_tokens_estimate=1,
            max_tokens=2,
        )
    )
    settled = producer_settlement(result)
    assert settled.ack.status == "committed" and settled.event.amount == Decimal("0.02")
    assert provider.calls == 1
    print(
        "B66_EXPLICIT_RUN "
        + json.dumps(
            {
                "before_missing_run_provider_calls": 0,
                "actual_provider_calls": provider.calls,
                "fresh_ledger": FileBudgetLedger(path).snapshot().model_dump(mode="json"),
            }
        )
    )
