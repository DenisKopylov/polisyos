"""Protected admission acts retain every actual budget coordinate.

This profile uses the real filesystem ledger and chained local audit sink. The
limited and unlimited dimensions belong to one atomic provider intent. No-charge
audit records preserve their coordinates without manufacturing a monetary event.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.core.security.audit_log_adapter import ChainedAuditLog
from polisyos.core.security.audit_models import ChainedLogEntry
from polisyos.core.security.audit_sink import ChainedAuditSink
from polisyos.core.security.audit_verifier import ChainVerifier
from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage

if TYPE_CHECKING:
    from pathlib import Path

_KEYS = ("run", "unlimited")
_RUN = "B65-all-key-admission"


class _PhysicalProvider:
    """Perform the actual file effect before returning supported cost evidence."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _complete(self, request: dict[str, Any]) -> GatewayLLMResponse:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(request, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return GatewayLLMResponse(
            content="physically completed",
            usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, cost_usd=0.02),
            model="default",
            provider="physical-admission-provider",
            raw=None,
        )

    def invoke(self, prompt: str, **kwargs: Any) -> GatewayLLMResponse:
        return self._complete({"prompt": prompt, **kwargs})

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        return self._complete(kwargs)


class _ObservedSink(ChainedAuditSink):
    """Observe a failed exact entry while delegating the unchanged local write."""

    def __init__(self, path: Path) -> None:
        self.failed_entry: ChainedLogEntry | None = None
        super().__init__(chain_id="B65:all-key-admission", local_path=path)

    def _append_and_enqueue(self, entry: ChainedLogEntry) -> None:
        try:
            super()._append_and_enqueue(entry)
        except OSError:
            self.failed_entry = entry
            raise


class _DirectoryFaultLog(ChainedAuditLog):
    """Refuse one real append by making its actual target a directory."""

    def __init__(self, sink: _ObservedSink, path: Path, action: str | None) -> None:
        super().__init__(sink)
        self.path = path
        self.fail_action = action
        self.failure: OSError | None = None
        self.attempted: list[str] = []

    def append(self, **kwargs: Any) -> None:
        self.attempted.append(kwargs["action"])
        if kwargs["action"] != self.fail_action:
            return super().append(**kwargs)
        self.fail_action = None
        prefix = self.path.with_suffix(".preserved-prefix.jsonl")
        self.path.rename(prefix)
        self.path.mkdir()
        try:
            super().append(**kwargs)
        except OSError as error:
            self.failure = error
            raise
        finally:
            self.path.rmdir()
            prefix.rename(self.path)


def _call(enforcer: LLMBudgetEnforcer, route: str) -> Any:
    kwargs = {"max_tokens": 4, "_prompt_tokens_estimate": 3}
    if route == "sync-invoke":
        return enforcer.invoke("nonempty actual request", **kwargs)
    return asyncio.run(enforcer.generate(user="nonempty actual request", **kwargs))


def _enforcer(
    provider: _PhysicalProvider,
    middleware: BudgetMiddleware,
    audit: _DirectoryFaultLog,
) -> LLMBudgetEnforcer:
    return LLMBudgetEnforcer(
        client=TracedLLMClient(provider, model_name="default", run_id=_RUN),
        budget_state=middleware.budget_state,
        budget_keys=list(_KEYS),
        budget_middleware=middleware,
        audit_log=audit,
        run_id=_RUN,
    )


def _snapshot(ledger_path: Path, audit_path: Path, provider_path: Path) -> dict[str, Any]:
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    return {
        "snapshot": snapshot.model_dump(mode="json"),
        "provider_effects": [json.loads(line) for line in provider_path.read_text().splitlines()],
        "audit_entries": [json.loads(line) for line in audit_path.read_text().splitlines()],
        "audit_chain": asdict(ChainVerifier().verify_jsonl_file(audit_path)),
    }


@pytest.mark.parametrize("route", ["sync-invoke", "async-generate"])
@pytest.mark.parametrize("action", ["BUDGET_CHECK", "BUDGET_EXCEEDED"])
@pytest.mark.parametrize("fault", [False, True], ids=["healthy", "real-directory-refusal"])
def test_all_key_protected_admission(tmp_path: Path, route: str, action: str, fault: bool) -> None:
    ledger_path = tmp_path / "ledger.json"
    audit_path = tmp_path / "protected.jsonl"
    provider_path = tmp_path / "provider.jsonl"
    # An empty real local file allows EXCEEDED's first append to reach the
    # actual backend open instead of failing inside the fault fixture rename.
    audit_path.write_text("")
    provider_path.write_text("")
    denied = action == "BUDGET_EXCEEDED"
    initial = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(0) if denied else Decimal(10))}
    )
    middleware = BudgetMiddleware(initial, ledger=FileBudgetLedger(ledger_path))
    sink = _ObservedSink(audit_path)
    audit = _DirectoryFaultLog(sink, audit_path, action if fault else None)
    provider = _PhysicalProvider(provider_path)
    owner = _enforcer(provider, middleware, audit)
    try:
        error = None
        response = None
        try:
            response = _call(owner, route)
        except (LLMAccountingError, BudgetExhaustedError) as caught:
            error = caught
        actual = _snapshot(ledger_path, audit_path, provider_path)
        print(
            "B65_ADMISSION_ACTUAL "
            + json.dumps({"route": route, "action": action, "fault": fault, **actual})
        )
        fresh = FileBudgetLedger(ledger_path).snapshot()
        assert actual["audit_chain"]["chain_intact"]
        if not fault:
            assert fresh.completion_obligations == {}
            assert all(fresh.state.reserved.get(key, Decimal(0)) == 0 for key in _KEYS)
            if denied:
                assert isinstance(error, BudgetExhaustedError)
                assert actual["provider_effects"] == []
                assert fresh.spend_receipts == {}
                assert all(fresh.state.spent.get(key, Decimal(0)) == 0 for key in _KEYS)
                assert audit.attempted == ["BUDGET_EXCEEDED"]
            else:
                assert error is None
                assert len(actual["provider_effects"]) == 1
                settlement = producer_settlement(response)
                assert settlement is not None
                assert settlement.event.amount == Decimal("0.02")
                assert settlement.ack.status == "committed"
                assert len(settlement.ack.receipts) == len(_KEYS)
                assert len(fresh.spend_receipts) == len(_KEYS)
                assert all(fresh.state.spent[key] == Decimal("0.02") for key in _KEYS)
                assert audit.attempted == [
                    "BUDGET_RESERVED",
                    "BUDGET_CHECK",
                    "BUDGET_RELEASED",
                    "BUDGET_COMMITTED",
                ]
            assert [
                entry["payload"]["action"] for entry in actual["audit_entries"]
            ] == audit.attempted
            return

        assert isinstance(error, LLMAccountingError)
        assert error.response is None
        assert error.cause is audit.failure
        assert isinstance(audit.failure, IsADirectoryError)
        obligation = error.event["audit_obligation"]
        assert obligation.action == action
        assert obligation.event is None
        assert obligation.charge_ack is None
        assert error.event["producer_event"] is None
        assert error.event["charge_ack"] is None
        assert sink.failed_entry is not None
        assert sink.failed_entry.compute_hash() == sink.failed_entry.entry_hash
        assert sink.failed_entry.actor.identity == obligation.actor
        assert sink.failed_entry.payload == {"action": action, **dict(obligation.metadata)}
        assert sink.failed_entry.correlation.run_id == obligation.run_id == _RUN
        retained = fresh.completion_obligations[obligation.act_id]
        assert retained.phase == "protected_audit_pending"
        assert tuple(retained.budget_keys) == _KEYS
        assert set(retained.reserved_amounts) == set(_KEYS)
        assert retained.reserved_amounts["unlimited"] == 0
        assert retained.event_payload["kind"] == "budget_audit"
        assert retained.event_payload["amount"] is None
        assert retained.known_receipt_ids == ()
        assert retained.required_action == {
            "run_id": _RUN,
            "actor": obligation.actor,
            "action": action,
            "metadata": dict(obligation.metadata),
        }
        assert fresh.spend_receipts == {}
        assert actual["provider_effects"] == []
        assert all(fresh.state.spent.get(key, Decimal(0)) == 0 for key in _KEYS)
        if denied:
            assert retained.reserved_amounts["run"] == 0
            assert all(fresh.state.reserved.get(key, Decimal(0)) == 0 for key in _KEYS)
            assert len(fresh.completion_obligations) == 1
        else:
            assert retained.reserved_amounts["run"] > 0
            assert fresh.state.reserved["run"] == retained.reserved_amounts["run"]
            assert any(
                record.phase == "provider_in_flight"
                for record in fresh.completion_obligations.values()
            )

        sibling = _enforcer(provider, middleware, audit)
        reopened = BudgetMiddleware(initial, ledger=FileBudgetLedger(ledger_path))
        new_owner = _enforcer(provider, reopened, audit)
        before = {path: path.read_bytes() for path in (ledger_path, audit_path, provider_path)}
        attempts_before = tuple(audit.attempted)
        for caller in (owner, sibling, new_owner):
            with pytest.raises(LLMAccountingError):
                _call(caller, route)
            assert {path: path.read_bytes() for path in before} == before
            assert tuple(audit.attempted) == attempts_before
        print(
            "B65_ADMISSION_REFUSED "
            + json.dumps(
                {
                    "act_id": obligation.act_id,
                    "act_digest": obligation.payload_digest,
                    "retained_record_digest": retained.payload_digest,
                    "same_live_and_reopened_refusals": 3,
                    "actual_file_hashes": {
                        path.name: hashlib.sha256(data).hexdigest() for path, data in before.items()
                    },
                }
            )
        )
    finally:
        sink.close()
