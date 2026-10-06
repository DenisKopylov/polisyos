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
from polisyos.core.security.audit_models import ChainedLogEntry
from polisyos.core.security.audit_sink import ChainedAuditSink, LocalJsonlBackend
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

    def __init__(
        self,
        sink: ChainedAuditSink,
        path: Path,
        *,
        fail: bool,
        fail_action: str = "BUDGET_COMMITTED",
    ) -> None:
        super().__init__(sink)
        self.path = path
        self.fail_next_commit = fail
        self.fail_action = fail_action
        self.failure: OSError | None = None
        self.attempted_actions: list[str] = []

    def append(self, **kwargs: Any) -> None:
        action = kwargs["action"]
        self.attempted_actions.append(action)
        if action != self.fail_action or not self.fail_next_commit:
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


class _ObservedAuditSink(ChainedAuditSink):
    """Observe exact attempted entries; execute the unchanged real sink effect."""

    def __init__(self, path: Path) -> None:
        self.failed_entry: ChainedLogEntry | None = None
        super().__init__(chain_id="B65:retained-owner", local_path=path)

    def _append_and_enqueue(self, entry: ChainedLogEntry) -> None:
        try:
            super()._append_and_enqueue(entry)
        except OSError:
            self.failed_entry = entry
            raise


class _RequiredAuditResolver:
    """A constructor-bound owner checks/replays an exact definitely missing act.

    The existing protected sink has no public reconciliation receipt API. This
    finite trusted composition observes the failed actual entry and uses the
    public real backend to replay precisely that entry. Its reference reports
    observed bytes, not a signature or a financial authority grant.
    """

    def __init__(self, sink: _ObservedAuditSink, path: Path, ledger_path: Path) -> None:
        self.sink = sink
        self.path = path
        self.ledger_path = ledger_path
        self.entry_override: ChainedLogEntry | None = None
        self.calls = 0
        self.writes = 0

    def __call__(self, obligation: Any) -> Any:
        from polisyos.core.llm.settlement import LLMAuditResolution

        self.calls += 1
        entry = self.entry_override or self.sink.failed_entry
        if entry is None:
            raise ValueError("original owner did not retain an observed failed entry")
        expected_payload = json.loads(
            json.dumps({"action": obligation.action, **dict(obligation.metadata)})
        )
        actual_payload = json.loads(entry.model_dump_json())["payload"]
        # JSON bytes preserve false/zero, null and nested types. Merely equal
        # Python objects, a nonempty string, or matching action names do not bind
        # the original protected act.
        if (
            entry.compute_hash() != entry.entry_hash
            or entry.chain_id != "B65:retained-owner"
            or entry.actor.id != obligation.actor
            or entry.resource.id != obligation.run_id
            or entry.correlation.run_id != obligation.run_id
            or json.dumps(actual_payload, sort_keys=True)
            != json.dumps(expected_payload, sort_keys=True)
        ):
            raise ValueError("failed protected entry does not bind exact owner/run/act/payload")
        if obligation.event is not None:
            if obligation.charge_ack is None or obligation.charge_ack.status != "committed":
                raise ValueError("observed provider charge acknowledgement was lost")
            for receipt in obligation.charge_ack.receipts:
                if FileBudgetLedger(self.ledger_path).resolve_spend(receipt.event_id) != receipt:
                    raise ValueError("known local charge does not match fresh exact ledger receipt")
        prefix = [
            ChainedLogEntry.model_validate_json(line) for line in self.path.read_text().splitlines()
        ]
        if any(item.entry_id == entry.entry_id for item in prefix):
            raise ValueError("this definite-noappend resolver cannot blindly duplicate an act")
        if not ChainVerifier().verify_segment([*prefix, entry]).chain_intact:
            raise ValueError("retained entry does not continue the actual same-owner prefix")
        LocalJsonlBackend(self.path).write(entry)
        self.writes += 1
        verified = ChainVerifier().verify_jsonl_file(self.path)
        persisted = [
            ChainedLogEntry.model_validate_json(line) for line in self.path.read_text().splitlines()
        ]
        if not verified.chain_intact or persisted[-1] != entry:
            raise ValueError("protected exact entry is not present in the fresh complete chain")
        import hashlib

        return LLMAuditResolution(
            obligation_digest=obligation.payload_digest,
            status="committed",
            evidence_ref=f"sha256:{hashlib.sha256(self.path.read_bytes()).hexdigest()}#entry={entry.entry_hash}",
        )


def _recovery_fixture(tmp_path: Path, action: str) -> tuple[Any, ...]:
    audit_path = tmp_path / "original-protected.jsonl"
    ledger_path = tmp_path / "original-ledger.json"
    provider = _PhysicalProvider(tmp_path / "original-provider.jsonl")
    initial = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    middleware = BudgetMiddleware(initial, ledger=FileBudgetLedger(ledger_path))
    sink = _ObservedAuditSink(audit_path)
    audit = _CommitFaultAuditLog(sink, audit_path, fail=True, fail_action=action)
    resolver = _RequiredAuditResolver(sink, audit_path, ledger_path)
    enforcer = LLMBudgetEnforcer(
        client=TracedLLMClient(provider, model_name="default", run_id="B65-owner-recovery"),
        budget_state=initial,
        budget_keys=["run"],
        budget_middleware=middleware,
        audit_log=audit,
        audit_reconciler=resolver,
        run_id="B65-owner-recovery",
    )
    return enforcer, sink, audit, resolver, provider, audit_path, ledger_path


@pytest.mark.parametrize("route", ["sync-invoke", "async-generate"])
@pytest.mark.parametrize("action", ["BUDGET_RESERVED", "BUDGET_RELEASED", "BUDGET_COMMITTED"])
def test_same_protected_owner_replays_exact_missing_act_before_unblocking(
    tmp_path: Path, route: str, action: str
) -> None:
    enforcer, sink, audit, resolver, provider, audit_path, ledger_path = _recovery_fixture(
        tmp_path, action
    )
    try:
        with pytest.raises(LLMAccountingError) as first:
            _call(enforcer, route)
        error = first.value
        obligation = error.event["audit_obligation"]
        before = FileBudgetLedger(ledger_path).snapshot()
        print(
            "B65_PENDING "
            + json.dumps(
                {
                    "route": route,
                    "action": action,
                    "act_id": obligation.act_id,
                    "obligation_digest": obligation.payload_digest,
                    "provider_calls": len(provider.responses),
                    "original_cause": type(error.cause).__name__,
                    "settlement_status": error.event["settlement_status"],
                    "captured_entry": sink.failed_entry.model_dump(mode="json"),
                    "fresh_ledger": before.model_dump(mode="json"),
                }
            )
        )
        assert error.event["required_audit_status"] == "pending"
        assert obligation.action == action
        assert error.cause is audit.failure and isinstance(error.cause, IsADirectoryError)
        original_metadata = json.dumps(dict(obligation.metadata), sort_keys=True)
        original_digest = obligation.payload_digest
        detached_metadata = dict(obligation.metadata)
        if "budget_keys" in detached_metadata:
            detached_metadata["budget_keys"].append("different-caller-key")
        else:
            detached_metadata["payload_digest"] = "sha256:" + "0" * 64
        print(
            "B65_DETACHED_METADATA "
            + json.dumps(
                {
                    "route": route,
                    "action": action,
                    "original_metadata": json.loads(original_metadata),
                    "mutated_caller_view": detached_metadata,
                    "retained_metadata": dict(obligation.metadata),
                    "original_digest": original_digest,
                    "retained_digest": obligation.payload_digest,
                }
            )
        )
        assert json.dumps(dict(obligation.metadata), sort_keys=True) == original_metadata
        assert obligation.payload_digest == original_digest
        initial_calls = len(provider.responses)
        assert initial_calls == (0 if action == "BUDGET_RESERVED" else 1)
        if initial_calls:
            assert error.response is provider.responses[0]
            assert obligation.event is not None and obligation.event.amount == Decimal("0.02")
            assert obligation.charge_ack is not None and obligation.charge_ack.status == "committed"
            assert error.event["settlement_status"] == "committed"
            assert before.state.spent["run"] == Decimal("0.02")
        else:
            assert error.response is None and obligation.event is None
            assert obligation.charge_ack is None
            assert not before.spend_receipts
            assert before.state.reserved["run"] > Decimal("0")
        assert before.completion_obligations
        with pytest.raises(LLMAccountingError):
            _call(enforcer, route)
        assert len(provider.responses) == initial_calls
        # A new constructor reopens the actual ledger with a distinct live
        # owner epoch. It must discover the persisted obligation, even though
        # this owner has never seen the original in-memory accounting error.
        reopened_initial = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}
        )
        reopened = LLMBudgetEnforcer(
            client=TracedLLMClient(provider, model_name="default", run_id="B65-owner-recovery"),
            budget_state=reopened_initial,
            budget_keys=["run"],
            budget_middleware=BudgetMiddleware(
                reopened_initial, ledger=FileBudgetLedger(ledger_path)
            ),
            audit_log=audit,
            audit_reconciler=resolver,
            run_id="B65-owner-recovery",
        )
        ledger_before_reopened_call = ledger_path.read_bytes()
        audit_before_reopened_call = audit_path.read_bytes()
        with pytest.raises(LLMAccountingError) as reopened_error:
            _call(reopened, route)
        retained = reopened_error.value.event["completion_obligation"]
        print(
            "B65_REOPENED_PENDING "
            + json.dumps(
                {
                    "route": route,
                    "action": action,
                    "provider_calls": len(provider.responses),
                    "retained_completion": retained.model_dump(mode="json"),
                    "audit_bytes_unchanged": audit_path.read_bytes() == audit_before_reopened_call,
                    "ledger_bytes_unchanged": ledger_path.read_bytes()
                    == ledger_before_reopened_call,
                    "fresh_ledger": FileBudgetLedger(ledger_path)
                    .snapshot()
                    .model_dump(mode="json"),
                }
            )
        )
        assert retained.obligation_id in before.completion_obligations
        assert audit_path.read_bytes() == audit_before_reopened_call
        assert ledger_path.read_bytes() == ledger_before_reopened_call
        assert len(provider.responses) == initial_calls
        ack = enforcer.reconcile_required_audit(obligation.act_id)
        after = FileBudgetLedger(ledger_path).snapshot()
        print(
            "B65_AUDIT_RECONCILED "
            + json.dumps(
                {
                    "route": route,
                    "action": action,
                    "act_id": obligation.act_id,
                    "provider_calls": len(provider.responses),
                    "resolver_writes": resolver.writes,
                    "ack_status": ack.status,
                    "before": before.model_dump(mode="json"),
                    "after": after.model_dump(mode="json"),
                    "fresh_chain": vars(ChainVerifier().verify_jsonl_file(audit_path)),
                }
            )
        )
        assert after.state.spent == before.state.spent
        assert after.spend_receipts == before.spend_receipts
        assert after.state.reserved.get("run", Decimal("0")) == Decimal("0")
        assert not after.completion_obligations
        assert len(provider.responses) == initial_calls
        assert resolver.calls == resolver.writes == 1
        if obligation.charge_ack is not None:
            assert ack == obligation.charge_ack
        else:
            assert ack.status == "unmanaged"
        assert ChainVerifier().verify_jsonl_file(audit_path).chain_intact
        result = _call(reopened, route)
        assert producer_settlement(result).ack.status == "committed"
        assert len(provider.responses) == initial_calls + 1
        print(
            "B65_RECOVERED "
            + json.dumps(
                {
                    "route": route,
                    "action": action,
                    "act_id": obligation.act_id,
                    "obligation_digest": obligation.payload_digest,
                    "retained_entry": sink.failed_entry.model_dump(mode="json"),
                    "resolver_writes": resolver.writes,
                    "before": before.model_dump(mode="json"),
                    "after": after.model_dump(mode="json"),
                    "final": _observation(audit_path, ledger_path, provider.path),
                }
            )
        )
    finally:
        sink.close()


@pytest.mark.parametrize("mismatch", ["event-id", "payload", "log-owner"])
def test_retained_protected_act_wrong_binding_refuses_before_filesystem_effect(
    tmp_path: Path, mismatch: str
) -> None:
    enforcer, sink, _, resolver, provider, audit_path, ledger_path = _recovery_fixture(
        tmp_path, "BUDGET_COMMITTED"
    )
    try:
        with pytest.raises(LLMAccountingError) as first:
            _call(enforcer, "async-generate")
        obligation = first.value.event["audit_obligation"]
        entry = sink.failed_entry
        assert entry is not None
        payload = dict(entry.payload)
        if mismatch == "event-id":
            payload["producer_event_id"] = "other-actual-act"
        elif mismatch == "payload":
            payload["payload_digest"] = "sha256:" + "0" * 64
        altered = entry.model_copy(
            update={
                "payload": payload,
                "chain_id": "different-owner" if mismatch == "log-owner" else entry.chain_id,
            }
        )
        resolver.entry_override = altered.model_copy(update={"entry_hash": altered.compute_hash()})
        audit_before = audit_path.read_bytes()
        ledger_before = ledger_path.read_bytes()
        with pytest.raises(LLMAccountingError):
            enforcer.reconcile_required_audit(obligation.act_id)
        print(
            "B65_BINDING_REFUSAL "
            + json.dumps(
                {
                    "mismatch": mismatch,
                    "act_id": obligation.act_id,
                    "audit_bytes_unchanged": audit_path.read_bytes() == audit_before,
                    "ledger_bytes_unchanged": ledger_path.read_bytes() == ledger_before,
                    "provider_calls": len(provider.responses),
                    "writes": resolver.writes,
                    "retained_original": entry.model_dump(mode="json"),
                    "refused_candidate": resolver.entry_override.model_dump(mode="json"),
                }
            )
        )
        assert audit_path.read_bytes() == audit_before
        assert ledger_path.read_bytes() == ledger_before
        assert resolver.writes == 0
        with pytest.raises(LLMAccountingError):
            _call(enforcer, "async-generate")
        assert len(provider.responses) == 1
        print(
            "B65_WRONG_BINDING "
            + json.dumps(
                {
                    "mismatch": mismatch,
                    "act_id": obligation.act_id,
                    "retained_original": entry.model_dump(mode="json"),
                    "refused_candidate": resolver.entry_override.model_dump(mode="json"),
                    "writes": resolver.writes,
                    "fresh_readback": _observation(audit_path, ledger_path, provider.path),
                }
            )
        )
    finally:
        sink.close()
