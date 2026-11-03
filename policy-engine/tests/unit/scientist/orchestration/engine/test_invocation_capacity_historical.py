"""Historical N5 exhaustion replay against the actual durable quota owner."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine import producer_budget
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _binding(run_id: str = "original-run") -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id=run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="profile-a",
        control_job_id=f"job-{run_id}",
    )


def _exhausted(path: Path):
    binding = _binding()
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="selected-policy", total_units=2, protected_units=1
    )
    ledger = FileBudgetLedger(path)
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        invocation_quota_profile=BudgetLedgerInvocationProfile.from_policy(binding, policy),
    )
    record = observer.reserve_invocation(_hash("first"), _hash("first-request"))
    assert record is not None
    observer.finish_invocation(record.operation_id, record.request_digest, "completed")
    witness = observer.observe_standard_invocation_capacity().exhaustion_witness
    assert witness is not None
    return ledger, middleware, binding, policy, witness


def _verify(*, store, binding, policy, witness):
    method = getattr(producer_budget, "verify_standard_invocation_exhaustion_historical", None)
    assert callable(method), "completed-job replay requires a read-only historical owner API"
    return method(
        settlement_store=store,
        expected_run_binding=binding,
        expected_policy=policy,
        witness=witness,
    )


def test_fresh_historical_owner_replays_without_configure_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.json"
    ledger, store, binding, policy, witness = _exhausted(path)
    owner, resource, anchor = store.continuation_binding()
    fresh_ledger = FileBudgetLedger(path)
    fresh = BudgetMiddleware(
        BudgetState(),
        ledger=fresh_ledger,
        continuation_owner_identity=owner,
        continuation_resource_identity=resource,
        continuation_snapshot_anchor=anchor,
    )
    before = path.read_bytes()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("historical verification attempted configuration or observer creation")

    monkeypatch.setattr(BudgetMiddleware, "configure_invocation_profile_safe", forbidden)
    monkeypatch.setattr(ProducerBudgetObserver, "__init__", forbidden)
    assert _verify(store=fresh, binding=binding, policy=policy, witness=witness) is True
    assert path.read_bytes() == before
    assert ledger.snapshot().revision == anchor[0]


def test_historical_replay_requires_independently_selected_exact_policy_and_run(
    tmp_path: Path,
) -> None:
    _ledger, store, binding, policy, witness = _exhausted(tmp_path / "budget.json")
    wrong_policy = policy.model_copy(update={"allocation_id": "different-owner-selection"})
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=wrong_policy, witness=witness)
    invalid_policy = policy.model_copy(update={"protected_units": -1})
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=invalid_policy, witness=witness)
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=_binding("other-run"), policy=policy, witness=witness)
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=None, witness=witness)
    assert _verify(store=store, binding=binding, policy=policy, witness=witness) is True


def test_historical_replay_refuses_removed_terminal_record(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    _ledger, store, binding, policy, witness = _exhausted(path)
    original = path.read_bytes()
    wire = json.loads(original)
    del wire["invocation_reservations"][witness.terminal_witnesses[0][0]]
    path.write_text(json.dumps(wire))
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=policy, witness=witness)
    path.write_bytes(original)
    assert _verify(store=store, binding=binding, policy=policy, witness=witness) is True


def test_historical_replay_refuses_another_real_ledger_owner(tmp_path: Path) -> None:
    _ledger, _store, binding, policy, witness = _exhausted(tmp_path / "first.json")
    _other_ledger, other_store, _binding2, _policy2, _other_witness = _exhausted(
        tmp_path / "other.json"
    )
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=other_store, binding=binding, policy=policy, witness=witness)


@pytest.mark.parametrize("target", ["middleware", "ledger", "ledger_load"])
def test_historical_replay_refuses_shadowed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    ledger, store, binding, policy, witness = _exhausted(tmp_path / "budget.json")
    if target == "middleware":
        monkeypatch.setattr(store, "_continuation_state", lambda: None)
    elif target == "ledger":
        monkeypatch.setattr(ledger, "_continuation_state", lambda: None)
    else:
        monkeypatch.setattr(ledger, "_load_snapshot", lambda: None)
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=policy, witness=witness)


def test_missing_historical_lock_is_not_recreated_by_verification(tmp_path: Path) -> None:
    ledger, store, binding, policy, witness = _exhausted(tmp_path / "budget.json")
    lock = ledger._lock_path
    moved_lock = lock.with_name(lock.name + ".retained")
    lock.rename(moved_lock)
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=policy, witness=witness)
    assert not lock.exists()
    assert moved_lock.exists()


def test_historical_lock_symlink_cannot_replace_original_owner(tmp_path: Path) -> None:
    ledger, store, binding, policy, witness = _exhausted(tmp_path / "budget.json")
    lock = ledger._lock_path
    moved_lock = lock.with_name(lock.name + ".retained")
    lock.rename(moved_lock)
    lock.symlink_to(moved_lock.name)
    with pytest.raises(ProducerBudgetSourceError):
        _verify(store=store, binding=binding, policy=policy, witness=witness)
    assert lock.is_symlink()
    assert moved_lock.exists()
