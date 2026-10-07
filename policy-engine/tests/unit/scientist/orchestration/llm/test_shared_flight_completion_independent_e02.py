"""Independent physical-flight and undispatched-intent consumer controls.

The provider's operation and completion are real fsynced local files. The
canonical cache, traced wrapper, budget middleware and initialized file ledger
decide settlement. Configured in-process owner trust is a finite premise, not
external billing or institutional authority.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from polisyos.core.llm.settlement import _CacheReuseOwner

from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
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


def _append(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class _FileProvider:
    def __init__(self, root: Path, *, unknown: bool = False, suppress: bool = False) -> None:
        self.requests = root / "provider-requests.jsonl"
        self.completions = root / "provider-completions.jsonl"
        self.unknown = unknown
        self.suppress = suppress
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancel_seen = asyncio.Event()
        self.responses: list[GatewayLLMResponse] = []
        self.calls = 0

    def _begin(self, request: dict[str, Any]) -> int:
        self.calls += 1
        _append(self.requests, {"attempt": self.calls, "request": request})
        self.started.set()
        return self.calls

    def _finish(self, attempt: int) -> GatewayLLMResponse:
        if self.unknown:
            parser = GatewayLLMClient(base_url="http://unused.invalid", api_key="", model="e02")
            response = parser._parse_completion_payload(
                {
                    "id": f"physical-{attempt}",
                    "model": "e02",
                    "choices": [{"message": {"content": "physical completion"}}],
                }
            )
        else:
            response = GatewayLLMResponse(
                content="physical completion",
                usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, cost_usd=0.02),
                model="e02",
                provider="local-fsync-provider",
                request_id=f"physical-{attempt}",
                raw=None,
            )
        _append(
            self.completions,
            {"attempt": attempt, "content": response.content, "unknown_usage": self.unknown},
        )
        self.responses.append(response)
        return response

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        attempt = self._begin(kwargs)
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            if not self.suppress:
                raise
            self.cancel_seen.set()
            await self.release.wait()
        return self._finish(attempt)

    def invoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return self._finish(self._begin({"prompt": prompt, **kwargs}))

    async def ainvoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return await self.generate(prompt=prompt, **kwargs)


def _stack(
    root: Path,
    provider: _FileProvider,
    *,
    direct: bool = False,
    enforcer_type: type[LLMBudgetEnforcer] = LLMBudgetEnforcer,
) -> tuple[CachingLLMClient, LLMBudgetEnforcer]:
    cache = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="e02")
    client = (
        cache
        if direct
        else TracedLLMClient(cache, model_name="e02", cache_reuse_owner=cache._cache_reuse_owner)
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    middleware = BudgetMiddleware(state, ledger=FileBudgetLedger(root / "ledger.json"))
    assert FileBudgetLedger(root / "ledger.json").snapshot().state.spent == {}
    enforcer = enforcer_type(
        client=client,
        budget_state=state,
        budget_keys=["run"],
        budget_middleware=middleware,
        model_name="e02",
        run_id="independent-flight",
    )
    return cache, enforcer


def _read(root: Path, provider: _FileProvider) -> dict[str, Any]:
    snapshot = FileBudgetLedger(root / "ledger.json").snapshot()
    rows = {
        "snapshot": snapshot.model_dump(mode="json"),
        "requests": [json.loads(line) for line in provider.requests.read_text().splitlines()],
        "completions": [json.loads(line) for line in provider.completions.read_text().splitlines()],
    }
    print("INDEPENDENT_FLIGHT " + json.dumps(rows, sort_keys=True))
    return rows


async def _joined_calls(
    cache: CachingLLMClient,
    enforcer: LLMBudgetEnforcer,
    provider: _FileProvider,
    monkeypatch: pytest.MonkeyPatch,
    *,
    expired: bool,
) -> list[Any]:
    joined = asyncio.Event()
    actual_join = _CacheReuseOwner.join

    def observe_join(owner: Any, *args: Any) -> None:
        actual_join(owner, *args)
        if owner is cache._cache_reuse_owner:
            joined.set()

    # Observer delegates the actual membership check; it cannot create a join.
    monkeypatch.setattr(_CacheReuseOwner, "join", observe_join)
    arguments = {"user": "same physical request", "temperature": 0.0, "_prompt_tokens_estimate": 3}
    leader = asyncio.create_task(enforcer.generate(**arguments))
    await provider.started.wait()
    follower = asyncio.create_task(enforcer.generate(**arguments))
    await joined.wait()
    if expired:
        await provider.cancel_seen.wait()
    provider.release.set()
    return await asyncio.gather(leader, follower, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True], ids=["traced", "direct-cache"])
async def test_known_physical_completion_survives_shared_emission_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, direct: bool
) -> None:
    provider = _FileProvider(tmp_path, suppress=True)
    cache, enforcer = _stack(tmp_path, provider, direct=direct)
    cache._inflight_timeout_s = 0.03
    results = await _joined_calls(cache, enforcer, provider, monkeypatch, expired=True)
    rows = _read(tmp_path, provider)
    snapshot = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert all(isinstance(result, TimeoutError) for result in results)
    assert len(rows["requests"]) == len(rows["completions"]) == provider.calls == 1
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert snapshot.state.reserved["run"] == 0
    assert len(snapshot.spend_receipts) == 1
    assert FileBudgetLedger(tmp_path / "ledger.json").list_completion_obligations(("run",)) == ()
    assert cache._cache.size == 0 and cache._inflight == {}
    cache._inflight_timeout_s = None
    await enforcer.generate(user="new real request", _prompt_tokens_estimate=3)
    assert len(provider.requests.read_text().splitlines()) == 2
    assert len(provider.completions.read_text().splitlines()) == 2
    assert FileBudgetLedger(tmp_path / "ledger.json").load().spent["run"] == Decimal("0.04")


@pytest.mark.asyncio
async def test_shared_unknown_keeps_only_original_physical_obligation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _FileProvider(tmp_path, unknown=True)
    cache, enforcer = _stack(tmp_path, provider)
    results = await _joined_calls(cache, enforcer, provider, monkeypatch, expired=False)
    rows = _read(tmp_path, provider)
    assert len(rows["requests"]) == len(rows["completions"]) == provider.calls == 1
    assert all(isinstance(result, LLMAccountingError) for result in results)
    assert results[0] is results[1]
    original = results[0].event["producer_event"]
    assert original.amount is None and original.cost_origin == "unknown"
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    pending = ledger.list_completion_obligations(("run",))
    state = ledger.load()
    assert len(pending) == 1 and pending[0].phase == "cost_unknown"
    assert pending[0].event_payload["event_id"] == original.event_id
    assert state.spent.get("run", Decimal(0)) == 0
    assert state.reserved["run"] == pending[0].reserved_amounts["run"] > 0
    assert cache._cache.size == 0
    reopened_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    reopened = LLMBudgetEnforcer(
        client=enforcer._client,
        budget_state=reopened_state,
        budget_keys=["run"],
        budget_middleware=BudgetMiddleware(
            reopened_state, ledger=FileBudgetLedger(tmp_path / "ledger.json")
        ),
        model_name="e02",
        run_id="independent-flight",
    )
    with pytest.raises(LLMAccountingError):
        await reopened.generate(user="must not dispatch", _prompt_tokens_estimate=3)
    assert len(provider.requests.read_text().splitlines()) == 1
    assert (
        FileBudgetLedger(tmp_path / "ledger.json").list_completion_obligations(("run",)) == pending
    )


class _ProofCheckingEnforcer(LLMBudgetEnforcer):
    """Feed altered copies of a genuinely registered terminal join to its receiver."""

    refused_fields: list[str]

    def _observe_flight(self, reservation: Any, run_id: str, outcome: Any) -> None:
        if outcome.role == "joined":
            ledger = self._budget_middleware._ledger
            before = ledger._path.read_bytes()
            actual_pending = ledger.list_completion_obligations(("run",))
            assert any(record.obligation_id == reservation.attempt_id for record in actual_pending)
            other_cache = CachingLLMClient(object(), cache=InMemoryPromptCache(), model="e02")
            substitutions = {
                "owner": other_cache._cache_reuse_owner,
                "request_digest": outcome.request_digest + ":different-request",
                "scope_key": (*outcome.scope_key, "different-owner-scope"),
                "receiver_attempt_id": outcome.producer_attempt_id,
                "producer_attempt_id": reservation.attempt_id,
            }
            self.refused_fields = []
            for field, value in substitutions.items():
                with pytest.raises(RuntimeError):
                    super()._observe_flight(reservation, run_id, replace(outcome, **{field: value}))
                assert reservation.provider_started
                assert ledger._path.read_bytes() == before
                self.refused_fields.append(field)
            print("INDEPENDENT_WRONG_PROOF " + json.dumps(self.refused_fields))
        super()._observe_flight(reservation, run_id, outcome)


@pytest.mark.asyncio
async def test_wrong_genuine_join_proof_cannot_abort_another_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _FileProvider(tmp_path, suppress=True)
    cache, enforcer = _stack(tmp_path, provider, enforcer_type=_ProofCheckingEnforcer)
    cache._inflight_timeout_s = 0.03
    results = await _joined_calls(cache, enforcer, provider, monkeypatch, expired=True)
    _read(tmp_path, provider)
    assert all(isinstance(result, TimeoutError) for result in results)
    assert enforcer.refused_fields == [
        "owner",
        "request_digest",
        "scope_key",
        "receiver_attempt_id",
        "producer_attempt_id",
    ]
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    assert ledger.load().spent["run"] == Decimal("0.02") and ledger.load().reserved["run"] == 0
    assert ledger.list_completion_obligations(("run",)) == ()
    assert provider.calls == 1


class _RequiredFileCallback:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir()

    def __call__(self, event: dict[str, Any]) -> None:
        _append(self.path, event)


@pytest.mark.asyncio
@pytest.mark.parametrize("port", ["generate", "invoke", "ainvoke"])
async def test_traced_preflight_refusal_does_not_reuse_old_response_as_new_work(
    tmp_path: Path, port: str
) -> None:
    provider = _FileProvider(tmp_path)
    provider.release.set()
    callback = _RequiredFileCallback(tmp_path / "mandatory-events.jsonl")
    traced = TracedLLMClient(provider, model_name="e02", required_accounting=callback)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    enforcer = LLMBudgetEnforcer(
        client=traced,
        budget_state=state,
        budget_keys=["run"],
        budget_middleware=BudgetMiddleware(state, ledger=ledger),
        model_name="e02",
        run_id="independent-preflight",
    )

    async def call() -> Any:
        arguments = {"_prompt_tokens_estimate": 3, "max_tokens": 4}
        if port == "invoke":
            return enforcer.invoke("actual request", **arguments)
        if port == "ainvoke":
            return await enforcer.ainvoke("actual request", **arguments)
        return await enforcer.generate(user="actual request", **arguments)

    with pytest.raises(LLMAccountingError) as first:
        await call()
    assert isinstance(first.value.cause, IsADirectoryError)
    assert first.value.response is provider.responses[0]
    initial = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert initial.state.spent["run"] == Decimal("0.02") and initial.state.reserved["run"] == 0
    assert len(initial.spend_receipts) == 1
    with pytest.raises(LLMAccountingError) as refused:
        await call()
    assert refused.value is first.value
    _read(tmp_path, provider)
    after = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert after.state.spent == initial.state.spent
    assert after.state.reserved["run"] == 0
    assert after.spend_receipts == initial.spend_receipts
    assert ledger.list_completion_obligations(("run",)) == ()
    assert provider.calls == len(provider.requests.read_text().splitlines()) == 1
    callback.path.rmdir()
    identity = str(first.value.event["event_identity"])
    traced.reconcile_accounting(identity)
    assert len(callback.path.read_text().splitlines()) == 1
    assert json.loads(callback.path.read_text())["event_identity"] == identity
    await call()
    assert provider.calls == len(provider.requests.read_text().splitlines()) == 2
    final = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert final.state.spent["run"] == Decimal("0.04") and final.state.reserved["run"] == 0
    assert len(final.spend_receipts) == 2 and ledger.list_completion_obligations(("run",)) == ()
