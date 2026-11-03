"""Current quota observation and replayable terminal exhaustion evidence."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
    BudgetLedgerInvocationReservation,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _binding(run: str = "run-a") -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id=run,
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="profile-a",
        control_job_id=f"job-{run}",
    )


def _owner(
    path: Path, *, total: int = 3, protected: int = 1
) -> tuple[FileBudgetLedger, BudgetMiddleware, ProducerBudgetObserver]:
    ledger = FileBudgetLedger(path)
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    profile = BudgetLedgerInvocationProfile.from_policy(
        _binding(),
        BudgetInvocationQuotaPolicy(
            allocation_id="configured", total_units=total, protected_units=protected
        ),
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_quota_profile=profile,
    )
    return ledger, middleware, observer


def _consume(observer: ProducerBudgetObserver, name: str, outcome: str = "completed"):
    record = observer.reserve_invocation(_digest(name), _digest(name + "-request"))
    assert record is not None
    observer.finish_invocation(record.operation_id, record.request_digest, outcome)
    return record.operation_id


def _observe(observer: ProducerBudgetObserver):
    method = getattr(observer, "observe_standard_invocation_capacity", None)
    assert callable(method), "canonical owner must expose a read-only quota observation"
    return method()


def _verify(observer: ProducerBudgetObserver, witness: object) -> bool:
    method = getattr(observer, "verify_standard_invocation_exhaustion", None)
    assert callable(method), "canonical owner must replay terminal exhaustion witnesses"
    return method(witness)


def test_terminal_exhaustion_is_read_only_and_replays_after_later_work(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, _middleware, observer = _owner(path)
    first = _consume(observer, "first")
    second = _consume(observer, "second", "failed")
    before = path.read_bytes()
    observation = _observe(observer)
    assert path.read_bytes() == before
    assert observation.status == "exhausted"
    assert observation.standard_remaining_units == 0
    assert observation.protected_remaining_units == 1
    assert observation.not_a_permit is True
    assert {entry[0] for entry in observation.terminal_witnesses} == {first, second}
    witness = observation.exhaustion_witness
    assert witness is not None and _verify(observer, witness) is True

    profile = observer.invocation_quota_profile
    assert profile is not None
    extra, created = ledger.reserve_invocation(
        _digest("diagnostic"),
        _digest("diagnostic-request"),
        profile=profile,
        purpose="diagnostic",
    )
    assert created
    ledger.finish_invocation(
        extra.operation_id, extra.request_digest, profile=profile, outcome="completed"
    )
    assert ledger.snapshot().revision > observation.source_revision
    assert _verify(observer, witness) is True


def test_available_is_current_advice_never_a_reservation_or_replayable_stop(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, _middleware, observer = _owner(path)
    _consume(observer, "first")
    before = path.read_bytes()
    observation = _observe(observer)
    assert observation.status == "available" and observation.standard_remaining_units == 1
    assert observation.not_a_permit is True and path.read_bytes() == before
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, observation.exhaustion_witness)
    profile = observer.invocation_quota_profile
    assert profile is not None
    ledger.reserve_invocation(
        _digest("concurrent"),
        _digest("concurrent-request"),
        profile=profile,
        purpose="standard",
    )
    with pytest.raises(BudgetExhaustedError):
        observer.reserve_invocation(_digest("later"), _digest("later-request"))


@pytest.mark.parametrize("case", ["zero", "pending", "unknown", "no_profile", "selection_pending"])
def test_unknown_or_unproven_capacity_never_becomes_a_historical_stop(
    tmp_path: Path, case: str
) -> None:
    path = tmp_path / "ledger.json"
    if case in {"no_profile", "selection_pending"}:
        ledger = FileBudgetLedger(path)
        middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
        state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
        observer = ProducerBudgetObserver(
            settlement_store=middleware,
            producer_run_binding=_binding(),
            budget_state=state,
            invocation_selection_pending=case == "selection_pending",
        )
    else:
        _ledger, _middleware, observer = _owner(path, total=0 if case == "zero" else 2, protected=0)
        if case in {"pending", "unknown"}:
            record = observer.reserve_invocation(_digest("one"), _digest("one-request"))
            assert record is not None
            if case == "unknown":
                observer.finish_invocation(record.operation_id, record.request_digest, "unknown")
    before = path.read_bytes()
    observation = _observe(observer)
    assert path.read_bytes() == before
    assert observation.status == "not_established"
    assert observation.standard_remaining_units is None
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, observation.exhaustion_witness)


def test_source_unavailability_is_not_misreported_as_exhaustion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ledger, middleware, observer = _owner(tmp_path / "ledger.json")

    def unavailable():
        raise OSError("controlled owner read failure")

    monkeypatch.setattr(middleware, "_continuation_state", unavailable)
    observation = _observe(observer)
    assert observation.status == "not_established"
    assert observation.standard_remaining_units is None


@pytest.mark.parametrize("target", ["middleware", "ledger", "ledger_load", "observer"])
def test_instance_shadow_cannot_forge_an_independently_reconciled_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    ledger, middleware, observer = _owner(tmp_path / "ledger.json", total=1, protected=0)
    owner, resource, anchor, snapshot = middleware._continuation_state()
    profile = observer.invocation_quota_profile
    assert profile is not None and snapshot.invocation_reservations == {}
    fake = BudgetLedgerInvocationReservation(
        operation_id=_digest("forged"),
        request_digest=_digest("forged-request"),
        run_id=profile.run_binding.run_id,
        profile_digest=profile.profile_digest,
        purpose="standard",
        status="completed",
        revision=anchor[0] + 1,
    )
    forged_snapshot = snapshot.model_copy(
        update={"revision": fake.revision, "invocation_reservations": {fake.operation_id: fake}}
    )

    def counterfeit():
        return owner, resource, (fake.revision, "0" * 64), forged_snapshot

    if target == "middleware":
        monkeypatch.setattr(middleware, "_continuation_state", counterfeit)
    elif target == "ledger":
        monkeypatch.setattr(ledger, "_continuation_state", counterfeit)
    elif target == "ledger_load":
        monkeypatch.setattr(ledger, "_load_snapshot", lambda: forged_snapshot)
    else:
        monkeypatch.setattr(observer, "_capacity_owner_snapshot", counterfeit)
    observation = _observe(observer)
    assert observation.status == "not_established"


def test_full_advisory_observation_cannot_masquerade_as_replayable_witness(tmp_path: Path) -> None:
    ledger, _middleware, observer = _owner(tmp_path / "ledger.json", total=2, protected=1)
    _consume(observer, "first")
    observation = _observe(observer)
    assert observation.status == "exhausted"
    profile = observer.invocation_quota_profile
    assert profile is not None
    protected, _created = ledger.reserve_invocation(
        _digest("protected"),
        _digest("protected-request"),
        profile=profile,
        purpose="diagnostic",
    )
    ledger.finish_invocation(
        protected.operation_id, protected.request_digest, profile=profile, outcome="completed"
    )
    forged = observation.model_copy(
        update={"protected_remaining_units": 0, "source_anchor": "0" * 64}
    )
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, forged)
    assert observation.exhaustion_witness == forged.exhaustion_witness
    assert _verify(observer, observation.exhaustion_witness) is True


def test_removed_or_forged_terminal_records_cannot_replay_exhaustion(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _ledger, _middleware, observer = _owner(path, total=1, protected=0)
    operation_id = _consume(observer, "first")
    observation = _observe(observer)
    witness = observation.exhaustion_witness
    assert observation.status == "exhausted" and witness is not None
    assert _verify(observer, witness) is True
    forged = witness.model_copy(update={"terminal_witnesses": ((_digest("foreign"), 1),)})
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, forged)
    forged = witness.model_copy(update={"source_revision": 0})
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, forged)

    original = path.read_bytes()
    wire = json.loads(original)
    del wire["invocation_reservations"][operation_id]
    path.write_text(json.dumps(wire))
    with pytest.raises(ProducerBudgetSourceError):
        _verify(observer, witness)
    path.write_bytes(original)
    assert _verify(observer, witness) is True


def test_foreign_run_or_different_profile_cannot_reuse_exhaustion_witness(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware, first = _owner(path, total=1, protected=0)
    _consume(first, "one")
    observation = _observe(first)
    other_binding = _binding("run-b")
    other_profile = BudgetLedgerInvocationProfile.from_policy(
        other_binding,
        BudgetInvocationQuotaPolicy(allocation_id="other", total_units=1, protected_units=0),
    )
    other_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    other = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=other_binding,
        budget_state=other_state,
        invocation_quota_profile=other_profile,
    )
    assert ledger.snapshot().invocation_profiles["run-b"] == other_profile
    with pytest.raises(ProducerBudgetSourceError):
        _verify(other, observation.exhaustion_witness)
