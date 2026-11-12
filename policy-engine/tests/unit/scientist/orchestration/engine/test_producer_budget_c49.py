"""Read the real durable owner; never equate physical work with USD."""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    N5DiagnosticCapacityObservation,
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _owner(tmp_path, *, cap="1"):
    ledger = FileBudgetLedger(tmp_path / "ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    binding = BudgetLedgerProducerRunBinding(
        run_id="run-current",
        tenant_id="tenant-current",
        cell_id="cell-current",
        profile_id="profile-current",
        control_job_id="job-current",
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(cap))})
    return middleware, binding, state


def _settle(middleware, binding, name, amount, origin="reported"):
    with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
        return middleware.settle_producer_event_safe(
            name,
            _digest("request-" + name),
            _digest("response-" + name),
            key=f"nl-run:{binding.run_id}",
            model="fixture-model",
            provider="fixture-provider",
            amount=Decimal(amount) if amount is not None else None,
            cost_origin=origin,
        )


def _diagnostic_owner(
    tmp_path, *, total=3, protected=2, purpose="diagnostic", pending=False, missing=False
):
    ledger = FileBudgetLedger(tmp_path / "diagnostic-ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    binding = BudgetLedgerProducerRunBinding(
        run_id="run-current",
        tenant_id="tenant-current",
        cell_id="cell-current",
        profile_id="profile-current",
        control_job_id="job-current",
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="diagnostic-capacity-test",
        total_units=total,
        protected_units=protected,
    )
    profile = BudgetLedgerInvocationProfile.from_policy(binding, policy)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=None if pending or missing else profile,
        invocation_purpose=purpose,
        invocation_selection_pending=pending,
    )
    return ledger, middleware, binding, policy, observer


def _finish_invocation(observer, policy, name, purpose, outcome="completed"):
    with observer.invocation_purpose_scope_from_selected_owner(policy, purpose=purpose):
        reservation = observer.reserve_invocation(_digest(name), _digest(name + "-request"))
        assert reservation is not None
        observer.finish_invocation(reservation.operation_id, reservation.request_digest, outcome)
    return reservation


def _diagnostic_capacity(observer):
    method = getattr(observer, "observe_diagnostic_invocation_capacity", None)
    assert callable(method), "canonical owner must expose diagnostic capacity observation"
    return method()


def test_invocation_only_diagnostic_never_invents_a_usd_settlement(tmp_path):
    middleware, binding, state = _owner(tmp_path, cap="0")
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="diagnostic-only", total_units=2, protected_units=2
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=BudgetLedgerInvocationProfile.from_policy(binding, policy),
        invocation_purpose="diagnostic",
    )
    capacity = observer.admit_diagnostic_invocation_only()
    assert capacity.protected_remaining_units == 2
    assert middleware.snapshot_safe().producer_settlements == {}
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    reservation = observer.reserve_invocation(_digest("one"), _digest("one-request"))
    assert reservation is not None
    with pytest.raises(ProducerBudgetSourceError, match="capacity_unavailable"):
        observer.admit_diagnostic_invocation_only()
    observer.finish_invocation(reservation.operation_id, reservation.request_digest, "completed")
    assert observer.admit_diagnostic_invocation_only().protected_remaining_units == 1
    second = observer.reserve_invocation(_digest("two"), _digest("two-request"))
    assert second is not None
    observer.finish_invocation(second.operation_id, second.request_digest, "completed")
    with pytest.raises(ProducerBudgetSourceError, match="capacity_unavailable"):
        observer.admit_diagnostic_invocation_only()
    state.limits["run"] = BudgetLimit(key="run", max_usd=Decimal("1"))
    with pytest.raises(ProducerBudgetSourceError, match="run_limit_changed"):
        observer.admit_diagnostic_invocation_only()


@pytest.mark.parametrize("case", ["standard", "positive_cap", "standard_pool", "zero_quota"])
def test_invocation_only_diagnostic_refuses_inapplicable_profiles(tmp_path, case):
    middleware, binding, state = _owner(tmp_path, cap="1" if case == "positive_cap" else "0")
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="wrong-diagnostic",
        total_units=0 if case == "zero_quota" else 2,
        protected_units=0 if case == "zero_quota" else 1 if case == "standard_pool" else 2,
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=BudgetLedgerInvocationProfile.from_policy(binding, policy),
        invocation_purpose="standard" if case == "standard" else "diagnostic",
    )
    with pytest.raises(ProducerBudgetSourceError, match="invocation_only_not_established"):
        observer.admit_diagnostic_invocation_only()
    if case == "positive_cap":
        with pytest.raises(ProducerBudgetSourceError, match="producer_events_not_established"):
            observer.admit()


def test_invocation_only_diagnostic_rejects_changed_ledger_owner(tmp_path):
    middleware, binding, state = _owner(tmp_path, cap="0")
    policy = BudgetInvocationQuotaPolicy(allocation_id="owner", total_units=1, protected_units=1)
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=BudgetLedgerInvocationProfile.from_policy(binding, policy),
        invocation_purpose="diagnostic",
    )
    observer._owner = ("foreign-ledger", "foreign-contract", "foreign-mode")
    with pytest.raises(ProducerBudgetSourceError, match="capacity_unavailable"):
        observer.admit_diagnostic_invocation_only()


def test_diagnostic_observation_reads_shared_protected_units_without_writing(tmp_path):
    path = tmp_path / "diagnostic-ledger.json"
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(
        tmp_path, total=4, protected=3
    )
    _finish_invocation(observer, _policy, "standard", "standard", "failed")
    _finish_invocation(observer, _policy, "diagnostic", "diagnostic")
    _finish_invocation(observer, _policy, "counterevidence", "counterevidence", "failed")
    before = path.read_bytes()

    observation = _diagnostic_capacity(observer)

    assert path.read_bytes() == before
    assert type(observation) is N5DiagnosticCapacityObservation
    assert observation.status == "available"
    assert observation.protected_limit_units == 3
    assert observation.protected_remaining_units == 1
    assert observation.not_a_permit is True
    assert observation.reason_code is None
    assert observation.predicate_basis == "independently_reconciled"


def test_diagnostic_observation_allows_zero_standard_partition_and_reports_exhaustion(tmp_path):
    path = tmp_path / "diagnostic-ledger.json"
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(
        tmp_path, total=2, protected=2
    )
    _finish_invocation(observer, _policy, "diagnostic-a", "diagnostic")
    _finish_invocation(observer, _policy, "counterevidence-b", "counterevidence", "failed")
    before = path.read_bytes()

    observation = _diagnostic_capacity(observer)

    assert path.read_bytes() == before
    assert observation.status == "exhausted"
    assert observation.protected_limit_units == 2
    assert observation.protected_remaining_units == 0
    assert not hasattr(observation, "exhaustion_witness")


def test_zero_protected_pool_is_reconciled_as_exhausted_not_missing(tmp_path):
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(
        tmp_path, total=2, protected=0
    )
    observation = _diagnostic_capacity(observer)
    assert observation.status == "exhausted"
    assert observation.protected_limit_units == 0
    assert observation.protected_remaining_units == 0
    assert observation.predicate_basis == "independently_reconciled"


@pytest.mark.parametrize(
    ("purpose", "pending", "expected"),
    [
        ("standard", False, "diagnostic_purpose_not_selected"),
        ("diagnostic", True, "quota_profile_not_established"),
    ],
)
def test_diagnostic_capacity_requires_selected_purpose_and_complete_profile(
    tmp_path, purpose, pending, expected
):
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(
        tmp_path, purpose=purpose, pending=pending
    )
    if purpose == "standard":
        with observer.invocation_purpose_scope_from_selected_owner(_policy, purpose="diagnostic"):
            observation = _diagnostic_capacity(observer)
    else:
        observation = _diagnostic_capacity(observer)
    assert observation.status == "not_established"
    assert observation.reason_code == expected
    assert observation.protected_remaining_units is None


@pytest.mark.parametrize("pending", [False, True])
def test_diagnostic_capacity_without_profile_is_unknown(tmp_path, pending):
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(
        tmp_path,
        purpose="standard" if not pending else "diagnostic",
        pending=pending,
        missing=not pending,
    )
    observation = _diagnostic_capacity(observer)
    assert observation.status == "not_established"
    assert observation.reason_code == "quota_profile_not_established"


def test_unresolved_invocation_makes_diagnostic_capacity_unknown_without_writes(tmp_path):
    path = tmp_path / "diagnostic-ledger.json"
    _ledger, _middleware, _binding, _policy, observer = _diagnostic_owner(tmp_path)
    with observer.invocation_purpose_scope_from_selected_owner(_policy, purpose="diagnostic"):
        reservation = observer.reserve_invocation(_digest("pending"), _digest("pending-request"))
    assert reservation is not None
    before = path.read_bytes()
    observation = _diagnostic_capacity(observer)
    assert path.read_bytes() == before
    assert observation.status == "not_established"
    assert observation.reason_code == "quota_invocation_unresolved"


@pytest.mark.parametrize("target", ["owner", "middleware"])
def test_diagnostic_capacity_rejects_shadowed_or_changed_current_source(
    tmp_path, monkeypatch, target
):
    _ledger, middleware, _binding, _policy, observer = _diagnostic_owner(tmp_path)
    if target == "owner":
        monkeypatch.setattr(
            observer,
            "_capacity_owner_snapshot",
            lambda: (_ for _ in ()).throw(OSError()),
        )
    else:
        monkeypatch.setattr(
            middleware,
            "_continuation_state",
            lambda: (_ for _ in ()).throw(OSError()),
        )
    observation = _diagnostic_capacity(observer)
    assert observation.status == "not_established"
    assert observation.reason_code == "quota_source_not_established"


def test_diagnostic_capacity_rejects_a_replaced_current_profile(tmp_path, monkeypatch):
    ledger, middleware, binding, policy, observer = _diagnostic_owner(tmp_path)
    changed = BudgetInvocationQuotaPolicy(
        allocation_id=policy.allocation_id + "-replacement",
        total_units=policy.total_units,
        protected_units=policy.protected_units,
    )
    owner, resource, anchor, snapshot = middleware._continuation_state()
    changed_profile = BudgetLedgerInvocationProfile.from_policy(binding, changed)
    changed_snapshot = snapshot.model_copy(
        update={"invocation_profiles": {binding.run_id: changed_profile}}
    )

    def changed_profile_snapshot(_ledger):
        return owner, resource, anchor, changed_snapshot

    monkeypatch.setattr(FileBudgetLedger, "_continuation_state", changed_profile_snapshot)
    observation = _diagnostic_capacity(observer)
    assert observation.status == "not_established"
    assert observation.reason_code == "quota_owner_basis_not_established"
    assert (
        ledger.snapshot().invocation_profiles[binding.run_id] == observer.invocation_quota_profile
    )


def test_actual_snapshot_refresh_exhaustion_and_stable_source_identity(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "first", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    assert first.producer_spent_usd == Decimal("0.2")
    assert first.currency == "USD" and first.remaining_usd == Decimal("0.8")
    assert observer.admit().source_basis_digest == first.source_basis_digest
    # A fresh reader of the same file sees the same canonical owner and event.
    snapshot = FileBudgetLedger(tmp_path / "ledger.json").snapshot()
    assert snapshot.producer_settlements["first"].payload_digest == first.producer_events[0][1]
    _settle(middleware, binding, "second", "0.8")
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    assert observer.last_checked.remaining_usd == Decimal("0")
    assert observer.last_checked.source_basis_digest != first.source_basis_digest
    assert state.spent["run"] == Decimal("1")
    assert "n5_usd_price_not_established" in first.limitations


@pytest.mark.parametrize("kind", ["pending", "unknown", "missing"])
def test_unavailable_producer_cost_never_becomes_free_budget(tmp_path, kind):
    middleware, binding, state = _owner(tmp_path)
    if kind == "pending":
        with middleware.producer_run_binding_scope(binding):
            middleware.begin_producer_event_safe(
                "pending",
                _digest("pending"),
                key=f"nl-run:{binding.run_id}",
                model="m",
                provider="p",
            )
    elif kind == "unknown":
        _settle(middleware, binding, "unknown", None, "unknown")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(ProducerBudgetSourceError):
        observer.admit()
    assert observer.last_checked is None
    assert state.spent == {}


def test_zero_cap_has_independent_refusal_without_inventing_zero_spend(tmp_path):
    middleware, binding, state = _owner(tmp_path, cap="0")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    assert observer.last_checked is None and state.spent == {}


def test_foreign_owner_changed_cap_detached_view_and_snapshot_cannot_authorize(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "first", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    detached = middleware.snapshot_safe()
    detached.producer_settlements.clear()
    assert observer.admit().source_basis_digest == first.source_basis_digest
    with pytest.raises(ProducerBudgetSourceError, match="state_binding_mismatch"):
        observer(state.model_copy(deep=True))
    state.limits["run"].max_usd = Decimal("2")
    with pytest.raises(ProducerBudgetSourceError, match="run_limit_changed"):
        observer.admit()


def test_same_key_foreign_tenant_event_is_not_silently_filtered(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "own", "0.2")
    foreign = binding.model_copy(update={"tenant_id": "foreign-tenant"})
    _settle(middleware, foreign, "foreign", "0.1")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    with pytest.raises(ProducerBudgetSourceError, match="binding_mismatch"):
        observer.admit()
    assert state.spent == {}


def test_unrelated_global_revision_does_not_renew_the_selected_source_basis(tmp_path):
    middleware, binding, state = _owner(tmp_path)
    _settle(middleware, binding, "own", "0.2")
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    first = observer.admit()
    unrelated = binding.model_copy(
        update={"run_id": "unrelated-run", "control_job_id": "unrelated-job"}
    )
    _settle(middleware, unrelated, "unrelated", "0.3")
    current = observer.admit()
    assert current.ledger_revision > first.ledger_revision
    assert current.source_basis_digest == first.source_basis_digest
    assert current.producer_events == first.producer_events


def test_fenced_raw_snapshot_uses_owner_validation_and_rejects_corruption(tmp_path):
    from polisyos.scientist.orchestration.engine import decode_budget_ledger_snapshot

    path = tmp_path / "ledger.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(BudgetState())
    snapshot, raw = ledger.snapshot_with_raw_bytes()
    assert raw == path.read_bytes()
    assert decode_budget_ledger_snapshot(raw) == snapshot
    with pytest.raises(ValueError):
        decode_budget_ledger_snapshot(b"{}")
    path.write_bytes(b"{}")
    with pytest.raises(ValueError):
        ledger.snapshot_with_raw_bytes()
