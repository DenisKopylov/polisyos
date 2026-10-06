"""Protected local audit failure keeps an obtained provider response accounted for.

This profile supplies a real ChainedAuditLog, not the permitted NoopAuditLog.
The fault is a real filesystem refusal at its local COMMITTED append. Ledger
amount knowledge and protected audit publication are measured separately.
"""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from polisyos.core.llm.settlement import producer_settlement

from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.core.security.audit_log_adapter import ChainedAuditLog
from polisyos.core.security.audit_sink import ChainedAuditSink
from polisyos.core.security.audit_verifier import ChainVerifier
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage

if TYPE_CHECKING:
    from pathlib import Path


class _PhysicalProvider:
    """Supported typed provider whose real work is recorded before returning."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.responses: list[GatewayLLMResponse] = []

    def _complete(self, request: dict[str, Any]) -> GatewayLLMResponse:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(request, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        response = GatewayLLMResponse(
            content="actual provider response",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, cost_usd=0.02),
            model="default",
            provider="physical-test-provider",
            request_id=f"provider-attempt-{len(self.responses) + 1}",
            raw=None,
        )
        self.responses.append(response)
        return response

    def invoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return self._complete({"prompt": prompt, **kwargs})

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        return self._complete(kwargs)


class _CommitFaultAuditLog(ChainedAuditLog):
    """Delegate to the actual protected sink with one physical target fault."""

    def __init__(self, sink: ChainedAuditSink, path: Path, *, fail: bool) -> None:
        super().__init__(sink)
        self.path = path
        self.fail_next_commit = fail
        self.failure: OSError | None = None
        self.attempted_actions: list[str] = []

    def append(self, **kwargs: Any) -> None:
        action = kwargs["action"]
        self.attempted_actions.append(action)
        if action != "BUDGET_COMMITTED" or not self.fail_next_commit:
            return super().append(**kwargs)
        self.fail_next_commit = False
        # Preserve prior actual records, then make the very same filesystem
        # append target a directory. No production write/settlement method is
        # replaced. Restoring the target does not reconcile the missing act.
        previous = self.path.with_suffix(".fault-prefix.jsonl")
        self.path.rename(previous)
        self.path.mkdir()
        try:
            super().append(**kwargs)
        except OSError as error:
            self.failure = error
            raise
        finally:
            self.path.rmdir()
            previous.rename(self.path)


def _call(enforcer: LLMBudgetEnforcer, route: str) -> Any:
    # This finite accounting oracle supplies the supported admission estimate;
    # unrelated tokenizer downloads cannot establish its provider/audit premise.
    kwargs = {"max_tokens": 4, "_prompt_tokens_estimate": 3}
    if route == "sync-invoke":
        return enforcer.invoke("nonempty physical request", **kwargs)
    return asyncio.run(enforcer.generate(user="nonempty physical request", **kwargs))


def _observation(path: Path, ledger_path: Path, provider_path: Path) -> dict[str, Any]:
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    return {
        "provider_requests": [json.loads(line) for line in provider_path.read_text().splitlines()],
        "fresh_reopened_snapshot": snapshot.model_dump(mode="json"),
        "audit_entries": entries,
        "audit_chain": vars(ChainVerifier().verify_jsonl_file(path)),
    }


@pytest.mark.parametrize("route", ["sync-invoke", "async-generate"])
@pytest.mark.parametrize("fail_commit", [False, True], ids=["healthy", "protected-commit-fault"])
def test_protected_audit_reconciliation_precedes_next_provider(
    tmp_path: Path, route: str, fail_commit: bool
) -> None:
    audit_path = tmp_path / "protected-audit.jsonl"
    ledger_path = tmp_path / "ledger.json"
    provider_path = tmp_path / "actual-provider.jsonl"
    initial = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    middleware = BudgetMiddleware(initial, ledger=FileBudgetLedger(ledger_path))
    # Explicit bootstrap precedes the tested reservation and real provider.
    assert FileBudgetLedger(ledger_path).snapshot().state.spent == {}
    sink = ChainedAuditSink(chain_id="B65:protected-local", local_path=audit_path)
    audit = _CommitFaultAuditLog(sink, audit_path, fail=fail_commit)
    provider = _PhysicalProvider(provider_path)
    enforcer = LLMBudgetEnforcer(
        client=TracedLLMClient(provider, model_name="default", run_id="B65-real-audit"),
        budget_state=initial,
        budget_keys=["run"],
        budget_middleware=middleware,
        audit_log=audit,
        run_id="B65-real-audit",
    )
    try:
        first_error = None
        first_response = None
        try:
            first_response = _call(enforcer, route)
        except LLMAccountingError as error:
            first_error = error
        first = _observation(audit_path, ledger_path, provider_path)
        print("B65_FIRST " + json.dumps({"route": route, "fault": fail_commit, **first}))
        assert len(first["provider_requests"]) == 1
        snapshot = FileBudgetLedger(ledger_path).snapshot()
        assert snapshot.state.spent["run"] == Decimal("0.02")
        assert snapshot.state.reserved["run"] == Decimal("0")
        assert len(snapshot.spend_receipts) == 1
        assert next(iter(snapshot.spend_receipts.values())).amount == Decimal("0.02")
        assert first["audit_chain"]["chain_intact"]
        assert audit.attempted_actions[:3] == ["BUDGET_RESERVED", "BUDGET_CHECK", "BUDGET_RELEASED"]
        if not fail_commit:
            assert first_error is None
            settlement = producer_settlement(first_response)
            assert settlement is not None
            assert settlement.ack.status == "committed"
            assert settlement.event.amount == Decimal("0.02")
            assert first["audit_entries"][-1]["payload"]["action"] == "BUDGET_COMMITTED"
            second_response = _call(enforcer, route)
            assert producer_settlement(second_response).ack.status == "committed"
            final = _observation(audit_path, ledger_path, provider_path)
            print("B65_FINAL " + json.dumps({"route": route, "fault": False, **final}))
            assert len(final["provider_requests"]) == 2
            assert final["audit_chain"]["chain_intact"]
            assert FileBudgetLedger(ledger_path).load().spent["run"] == Decimal("0.04")
            return
        assert first_error is not None
        assert first_error.response is provider.responses[0]
        assert first_error.cause is audit.failure
        assert isinstance(audit.failure, IsADirectoryError)
        assert first_error.event["producer_event"].amount == Decimal("0.02")
        assert not any(e["payload"]["action"] == "BUDGET_COMMITTED" for e in first["audit_entries"])
        second_error = None
        try:
            _call(enforcer, route)
        except LLMAccountingError as error:
            second_error = error
        final = _observation(audit_path, ledger_path, provider_path)
        final.update(
            second_error_type=type(second_error).__name__ if second_error is not None else None,
            first_error_cause=type(first_error.cause).__name__,
            first_error_response_content=first_error.response.content,
            attempted_actions=audit.attempted_actions,
        )
        print("B65_FINAL " + json.dumps({"route": route, "fault": True, **final}))
        assert len(final["provider_requests"]) == 1, (
            "a received, known-cost provider result still lacks its mandatory protected "
            "COMMITTED audit; restoring the file alone must not admit another spend"
        )
        assert second_error is not None
    finally:
        sink.close()
