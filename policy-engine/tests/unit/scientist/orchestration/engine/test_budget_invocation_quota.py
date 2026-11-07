"""Native, durable non-USD N5 invocation allocation and owner controls."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
    BudgetLedgerInvocationQuotaExhaustedError,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerSettlementOutcomeUnknownError,
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


def _profile(
    *, total: int = 4, protected: int = 2, run: str = "run-a"
) -> BudgetLedgerInvocationProfile:
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="fixture-allocation", total_units=total, protected_units=protected
    )
    return BudgetLedgerInvocationProfile.from_policy(_binding(run), policy)


def _owner(path: Path) -> tuple[FileBudgetLedger, BudgetMiddleware]:
    ledger = FileBudgetLedger(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    return ledger, BudgetMiddleware(state, ledger=ledger)


def test_actual_v16_writer_fixture_is_read_without_rewrite_then_upgrades(tmp_path: Path) -> None:
    # Written by the real 1.6 owner at 7b84873a4, using synthetic input.
    fixture = Path(__file__).parent / "fixtures" / "budget-ledger-1.6-actual.json"
    payload = fixture.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == (
        "973d8cd388af564c4fff453b7df4f005c4bb6afa1b6369fdde7ead3824bcd806"
    )
    path = tmp_path / "legacy.json"
    path.write_bytes(payload)
    ledger = FileBudgetLedger(path)
    assert ledger.load().spent["run"] == Decimal("0.25")
    assert path.read_bytes() == payload
    assert ledger.snapshot().invocation_profiles == {}
    assert path.read_bytes() == payload
    ledger.configure_invocation_profile(_profile())
    assert json.loads(path.read_bytes())["schema_version"] == "1.8"
    fresh = FileBudgetLedger(path).snapshot()
    assert fresh.state.spent["run"] == Decimal("0.25")
    assert fresh.state.provider_spent["fixture-provider"] == Decimal("0.25")
    assert fresh.invocation_profiles["run-a"] == _profile()


def test_exact_legacy_continuation_anchor_survives_until_real_upgrade(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "budget-ledger-1.6-actual.json"
    payload = fixture.read_bytes()
    path = tmp_path / "anchored-legacy.json"
    path.write_bytes(payload)
    owner, resource, _new_projection = FileBudgetLedger(path).continuation_binding()
    # Emitted by the actual 1.6 owner's _snapshot_anchor on this exact fixture.
    old_anchor = (1, "a8f0dd608386e3ee131a32ad5992a00c1d1ac0087eaf7a8a3779e484644a4750")
    continuation = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(path),
        continuation_owner_identity=owner,
        continuation_resource_identity=resource,
        continuation_snapshot_anchor=old_anchor,
    )
    assert continuation.budget_state.spent["run"] == Decimal("0.25")
    assert path.read_bytes() == payload
    continuation.configure_invocation_profile_safe(_profile())
    assert json.loads(path.read_bytes())["schema_version"] == "1.8"
    with pytest.raises(ValueError, match="snapshot_anchor_mismatch"):
        BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(path),
            continuation_owner_identity=owner,
            continuation_resource_identity=resource,
            continuation_snapshot_anchor=old_anchor,
        )


def test_old_version_cannot_hide_nonempty_new_quota_fields(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "budget-ledger-1.6-actual.json"
    wire = json.loads(fixture.read_bytes())
    wire["invocation_profiles"] = {"run-a": _profile().model_dump(mode="json")}
    path = tmp_path / "forged-version.json"
    path.write_text(json.dumps(wire))
    with pytest.raises(ValueError, match="invocation_fields_require_version_1_7"):
        FileBudgetLedger(path).snapshot()


def test_reservation_is_replay_safe_and_failure_consumes_one_unit(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile(total=2, protected=0)
    middleware.configure_invocation_profile_safe(profile)
    first, created = middleware.reserve_invocation_safe(
        _digest("op-1"), _digest("request-1"), profile=profile, purpose="standard"
    )
    assert created and first.status == "reserved" and first.units == 1
    again, created = FileBudgetLedger(path).reserve_invocation(
        _digest("op-1"), _digest("request-1"), profile=profile, purpose="standard"
    )
    assert not created and again == first
    with pytest.raises(ValueError, match="identity_conflict"):
        ledger.reserve_invocation(
            _digest("op-1"), _digest("changed request"), profile=profile, purpose="standard"
        )
    failed = middleware.finish_invocation_safe(
        _digest("op-1"), _digest("request-1"), profile=profile, outcome="failed"
    )
    assert failed.status == "failed"
    assert (
        middleware.finish_invocation_safe(
            _digest("op-1"), _digest("request-1"), profile=profile, outcome="failed"
        )
        == failed
    )
    with pytest.raises(ValueError, match="outcome_conflict"):
        middleware.finish_invocation_safe(
            _digest("op-1"), _digest("request-1"), profile=profile, outcome="completed"
        )
    middleware.reserve_invocation_safe(
        _digest("op-2"), _digest("request-2"), profile=profile, purpose="standard"
    )
    with pytest.raises(BudgetLedgerInvocationQuotaExhaustedError):
        middleware.reserve_invocation_safe(
            _digest("op-3"), _digest("request-3"), profile=profile, purpose="standard"
        )
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {} and snapshot.state.reserved == {}
    assert len(snapshot.invocation_reservations) == 2
    assert snapshot.invocation_profiles["run-a"].price_origin == "unknown"


def test_purpose_partition_protects_diagnostic_units_and_stops_at_their_cap(tmp_path: Path) -> None:
    ledger, middleware = _owner(tmp_path / "ledger.json")
    profile = _profile(total=4, protected=2)
    middleware.configure_invocation_profile_safe(profile)
    for name in ("standard-1", "standard-2"):
        middleware.reserve_invocation_safe(
            _digest(name), _digest(name), profile=profile, purpose="standard"
        )
    with pytest.raises(BudgetLedgerInvocationQuotaExhaustedError):
        middleware.reserve_invocation_safe(
            _digest("standard-3"), _digest("standard-3"), profile=profile, purpose="standard"
        )
    for purpose in ("diagnostic", "counterevidence"):
        record, created = middleware.reserve_invocation_safe(
            _digest(purpose), _digest(purpose), profile=profile, purpose=purpose
        )
        assert created and record.purpose == purpose
    with pytest.raises(BudgetLedgerInvocationQuotaExhaustedError):
        middleware.reserve_invocation_safe(
            _digest("diagnostic-3"), _digest("diagnostic-3"), profile=profile, purpose="diagnostic"
        )
    assert len(ledger.snapshot().invocation_reservations) == 4


def test_owner_and_profile_identity_are_not_caller_replaceable(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile()
    middleware.configure_invocation_profile_safe(profile)
    other = profile.model_copy(
        update={"run_binding": _binding().model_copy(update={"tenant_id": "other"})}
    )
    with pytest.raises(ValueError, match="profile_conflict"):
        ledger.configure_invocation_profile(other)
    record, _ = ledger.reserve_invocation(
        _digest("one"), _digest("request"), profile=profile, purpose="standard"
    )
    with pytest.raises(ValueError, match="missing_or_conflicting"):
        ledger.finish_invocation(
            record.operation_id, record.request_digest, profile=other, outcome="completed"
        )
    with pytest.raises(ValueError, match="profile_not_current"):
        ledger.resolve_invocation(record.operation_id, profile=other)
    with pytest.raises(ValidationError):
        BudgetInvocationQuotaPolicy(allocation_id="bad", total_units=1, protected_units=2)
    with pytest.raises(ValidationError):
        BudgetInvocationQuotaPolicy(allocation_id="bad", total_units=True, protected_units=0)


def test_zero_allocation_stops_all_and_absence_is_no_guarantee(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    unconfigured = ProducerBudgetObserver(
        settlement_store=middleware, producer_run_binding=_binding(), budget_state=state
    )
    assert unconfigured.invocation_guarantee == "no_guarantee"
    assert unconfigured.reserve_invocation(_digest("free"), _digest("request")) is None
    assert FileBudgetLedger(path).snapshot().invocation_profiles == {}
    zero = _profile(total=0, protected=0, run="zero-run")
    zero_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    configured = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding("zero-run"),
        budget_state=zero_state,
        invocation_quota_profile=zero,
    )
    assert configured.invocation_guarantee == "no_guarantee"
    with pytest.raises(BudgetExhaustedError):
        configured.reserve_invocation(_digest("blocked"), _digest("request"))
    with pytest.raises(ValueError, match="already_unconfigured"):
        middleware.configure_invocation_profile_safe(_profile())
    assert FileBudgetLedger(path).snapshot().invocation_unconfigured_runs["run-a"] == _binding()


def test_omitted_profile_cannot_bypass_a_configured_run_or_restart(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    stale = ProducerBudgetObserver(
        settlement_store=middleware, producer_run_binding=_binding(), budget_state=state
    )
    profile = _profile(total=0, protected=0)
    middleware.configure_invocation_profile_safe(profile)
    with pytest.raises(ProducerBudgetSourceError):
        stale.reserve_invocation(_digest("stale"), _digest("request"))
    _, reopened_store = _owner(path)
    reopened = ProducerBudgetObserver(
        settlement_store=reopened_store, producer_run_binding=_binding(), budget_state=state
    )
    with pytest.raises(ProducerBudgetSourceError):
        reopened.reserve_invocation(_digest("reopened"), _digest("request"))
    assert FileBudgetLedger(path).snapshot().invocation_reservations == {}


def test_unconfigured_admission_and_configuration_are_atomic(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware, producer_run_binding=_binding(), budget_state=state
    )
    profile = _profile(total=1, protected=0)
    barrier = threading.Barrier(2)

    def configure() -> bool:
        barrier.wait(timeout=5)
        try:
            FileBudgetLedger(path).configure_invocation_profile(profile)
        except ValueError:
            return False
        return True

    def admit() -> bool:
        barrier.wait(timeout=5)
        try:
            observer.reserve_invocation(_digest("unconfigured"), _digest("request"))
        except ProducerBudgetSourceError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        configured = pool.submit(configure)
        admitted = pool.submit(admit)
        assert configured.result() != admitted.result()


def test_pending_selection_binds_only_the_resolved_owner_and_survives_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="owner-selection", total_units=1, protected_units=0
    )
    pending = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    with pytest.raises(ProducerBudgetSourceError, match="selection_pending"):
        pending.reserve_invocation(_digest("before"), _digest("request"))
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.invocation_profiles == {} and snapshot.invocation_unconfigured_runs == {}
    bound = pending.bind_invocation_policy_from_selected_owner(policy)
    assert bound == BudgetLedgerInvocationProfile.from_policy(_binding(), policy)
    assert pending.bind_invocation_policy_from_selected_owner(policy) == bound
    with pytest.raises(ProducerBudgetSourceError, match="selection_conflict"):
        pending.bind_invocation_policy_from_selected_owner(None)
    assert pending.reserve_invocation(_digest("once"), _digest("request")) is not None
    _, reopened_store = _owner(path)
    reopened = ProducerBudgetObserver(
        settlement_store=reopened_store,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    with pytest.raises(ProducerBudgetSourceError, match="selection_failed"):
        reopened.bind_invocation_policy_from_selected_owner(None)
    assert reopened.bind_invocation_policy_from_selected_owner(policy) == bound
    with pytest.raises(BudgetExhaustedError):
        reopened.reserve_invocation(_digest("twice"), _digest("request"))


@pytest.mark.parametrize("stored_selection", ["missing", "foreign", "drift"])
def test_read_only_selection_refuses_missing_foreign_or_drifted_profile_without_repair(
    tmp_path: Path,
    stored_selection: str,
) -> None:
    path = tmp_path / f"{stored_selection}.json"
    ledger, middleware = _owner(path)
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="fixture-allocation", total_units=4, protected_units=2
    )
    if stored_selection == "foreign":
        foreign_binding = _binding().model_copy(update={"tenant_id": "foreign-tenant"})
        ledger.configure_invocation_profile(
            BudgetLedgerInvocationProfile.from_policy(foreign_binding, policy)
        )
    elif stored_selection == "drift":
        ledger.configure_invocation_profile(
            BudgetLedgerInvocationProfile.from_policy(
                _binding(),
                BudgetInvocationQuotaPolicy(
                    allocation_id="different-allocation", total_units=5, protected_units=2
                ),
            )
        )
    before = path.read_bytes()
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        invocation_selection_pending=True,
    )

    with pytest.raises(ProducerBudgetSourceError, match="selection_not_current"):
        observer.bind_existing_invocation_policy_from_selected_owner(policy)

    assert path.read_bytes() == before
    assert ledger.snapshot().invocation_profiles.get("run-a") != _profile()


def test_read_only_selection_reopens_capacity_after_profile_removal(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile()
    middleware.configure_invocation_profile_safe(profile)
    before = path.read_bytes()
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        invocation_selection_pending=True,
    )

    assert observer.bind_existing_invocation_policy_from_selected_owner(
        BudgetInvocationQuotaPolicy(
            allocation_id=profile.allocation_id,
            total_units=profile.total_units,
            protected_units=profile.protected_units,
        )
    ) == profile
    assert path.read_bytes() == before
    capacity = observer.observe_standard_invocation_capacity()
    assert capacity.status == "available"
    assert capacity.profile_digest == profile.profile_digest

    current = ledger.snapshot()
    ledger._persist_snapshot(current.model_copy(update={"invocation_profiles": {}}))
    changed = observer.observe_standard_invocation_capacity()
    assert changed.status == "not_established"
    assert changed.reason_code == "quota_owner_basis_not_established"
    assert ledger.snapshot().invocation_profiles == {}


@pytest.mark.parametrize("boundary_fault", ["shadowed_reader", "missing_lock"])
def test_read_only_selection_refuses_shadowed_reader_or_missing_lock_without_repair(
    tmp_path: Path,
    boundary_fault: str,
) -> None:
    path = tmp_path / f"{boundary_fault}.json"
    ledger, middleware = _owner(path)
    profile = _profile()
    middleware.configure_invocation_profile_safe(profile)
    policy = BudgetInvocationQuotaPolicy(
        allocation_id=profile.allocation_id,
        total_units=profile.total_units,
        protected_units=profile.protected_units,
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        invocation_selection_pending=True,
    )
    if boundary_fault == "shadowed_reader":
        observer._capacity_owner_snapshot = lambda: pytest.fail(
            "shadowed capacity reader was invoked"
        )
    else:
        ledger._lock_path.unlink()
    before = path.read_bytes()

    with pytest.raises(ProducerBudgetSourceError, match="selection_source_unavailable"):
        observer.bind_existing_invocation_policy_from_selected_owner(policy)

    assert path.read_bytes() == before
    if boundary_fault == "missing_lock":
        assert not ledger._lock_path.exists()


def test_unconfigured_mode_is_durable_and_rejects_foreign_binding(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    pending = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    assert pending.bind_invocation_policy_from_selected_owner(None) is None
    assert pending.reserve_invocation(_digest("first"), _digest("request")) is None
    ledger.record_spend("run", Decimal("0.25"))
    reopened = FileBudgetLedger(path)
    assert reopened.snapshot().invocation_unconfigured_runs["run-a"] == _binding()
    with pytest.raises(ValueError, match="already_unconfigured"):
        reopened.configure_invocation_profile(_profile())
    foreign = _binding().model_copy(update={"tenant_id": "foreign"})
    with pytest.raises(ValueError, match="binding_mismatch"):
        reopened.select_unconfigured_invocations(foreign)
    assert reopened.configure_invocation_profile(_profile(run="other-run"))


def test_observer_counts_once_and_requires_its_exact_run(tmp_path: Path) -> None:
    _, middleware = _owner(tmp_path / "ledger.json")
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    profile = _profile(total=2, protected=1)
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_quota_profile=profile,
        invocation_purpose="diagnostic",
    )
    assert observer.invocation_guarantee == "protected_invocations"
    record = observer.reserve_invocation(_digest("operation"), _digest("request"))
    assert record is not None and record.purpose == "diagnostic"
    with pytest.raises(ProducerBudgetSourceError, match="already_issued"):
        observer.reserve_invocation(_digest("operation"), _digest("request"))
    observer.finish_invocation(_digest("operation"), _digest("request"), "unknown")
    with pytest.raises(BudgetExhaustedError):
        observer.reserve_invocation(_digest("another"), _digest("request2"))
    with pytest.raises(ValueError, match="owner_binding_mismatch"):
        ProducerBudgetObserver(
            settlement_store=middleware,
            producer_run_binding=_binding("another-run"),
            budget_state=state,
            invocation_quota_profile=profile,
        )


def test_owner_selected_diagnostic_observer_retains_pool_after_standard_exhaustion(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    profile = _profile(total=2, protected=1)
    standard = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_quota_profile=profile,
        invocation_purpose="standard",
    )
    assert standard.reserve_invocation(_digest("normal"), _digest("request")) is not None
    with pytest.raises(BudgetExhaustedError):
        standard.reserve_invocation(_digest("normal-over"), _digest("request"))
    diagnostic = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_quota_profile=profile,
        invocation_purpose="diagnostic",
    )
    protected = diagnostic.reserve_invocation(_digest("diagnostic"), _digest("request"))
    assert protected is not None and protected.purpose == "diagnostic"
    with pytest.raises(BudgetExhaustedError):
        diagnostic.reserve_invocation(_digest("protected-over"), _digest("request"))
    fresh = FileBudgetLedger(path).snapshot()
    assert {item.purpose for item in fresh.invocation_reservations.values()} == {
        "standard",
        "diagnostic",
    }


def test_purpose_observers_reconcile_shared_usd_state_once_across_wrappers(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    _, reopened_store = _owner(path)
    state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
    )
    profile = _profile(total=3, protected=2)

    def settle(name: str, amount: str) -> None:
        with middleware.producer_run_binding_scope(_binding(), control_job_attempt=1):
            middleware.settle_producer_event_safe(
                name,
                _digest(name + "-request"),
                _digest(name + "-response"),
                key="nl-run:run-a",
                model="controlled-model",
                provider="controlled-provider",
                amount=Decimal(amount),
                cost_origin="reported",
            )

    settle("first", "0.2")
    observers = [
        ProducerBudgetObserver(
            settlement_store=store,
            producer_run_binding=_binding(),
            budget_state=state,
            invocation_quota_profile=profile,
            invocation_purpose=purpose,
        )
        for store, purpose in (
            (middleware, "standard"),
            (reopened_store, "diagnostic"),
            (middleware, "counterevidence"),
        )
    ]
    state.record_spend("run", Decimal("0.4"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = list(pool.map(lambda observer: observer.observe(), observers))
    assert {row.runtime_allocation_usd for row in first} == {Decimal("0.4")}
    assert state.spent["run"] == Decimal("0.6")
    settle("second", "0.3")
    with ThreadPoolExecutor(max_workers=3) as pool:
        second = list(pool.map(lambda observer: observer.observe(), observers))
    assert {row.producer_spent_usd for row in second} == {Decimal("0.5")}
    assert {row.runtime_allocation_usd for row in second} == {Decimal("0.4")}
    assert state.spent["run"] == Decimal("0.9")
    state.record_spend("run", Decimal("0.1"))
    assert observers[0].observe().runtime_allocation_usd == Decimal("0.5")
    assert state.spent["run"] == Decimal("1.0")
    with pytest.raises(ProducerBudgetSourceError, match="state.*owner|owner.*state"):
        ProducerBudgetObserver(
            settlement_store=middleware,
            producer_run_binding=_binding("foreign-run"),
            budget_state=state,
        )
    for restored in (
        state.model_copy(deep=True),
        BudgetState.model_validate_json(state.model_dump_json()),
    ):
        with pytest.raises(ProducerBudgetSourceError, match="projection_basis_not_established"):
            ProducerBudgetObserver(
                settlement_store=middleware,
                producer_run_binding=_binding(),
                budget_state=restored,
            )
    copied = tmp_path / "copied-ledger.json"
    copied.write_bytes(path.read_bytes())
    copied_store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(copied))
    with pytest.raises(ProducerBudgetSourceError, match="state.*owner|owner.*state"):
        ProducerBudgetObserver(
            settlement_store=copied_store,
            producer_run_binding=_binding(),
            budget_state=state,
        )


def test_replacing_live_ledger_lock_refuses_subsequent_quota_admission(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_quota_profile=_profile(total=2, protected=0),
    )
    replacement = tmp_path / "replacement-lock"
    replacement.touch()
    os.replace(replacement, ledger._lock_path)
    with pytest.raises(ProducerBudgetSourceError):
        observer.reserve_invocation(_digest("after-replace"), _digest("request"))


def test_same_observer_scopes_owner_selected_purpose_without_cross_task_leak(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    _, middleware = _owner(path)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    policy = BudgetInvocationQuotaPolicy(allocation_id="owner", total_units=2, protected_units=1)
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    with pytest.raises(ProducerBudgetSourceError):
        with observer.invocation_purpose_scope_from_selected_owner(policy, purpose="diagnostic"):
            pytest.fail("pending selection admitted purpose")
    observer.bind_invocation_policy_from_selected_owner(policy)
    barrier = threading.Barrier(2)

    def invoke(purpose: str):
        with observer.invocation_purpose_scope_from_selected_owner(policy, purpose=purpose):
            barrier.wait(timeout=5)
            assert observer.invocation_purpose == purpose
            return observer.reserve_invocation(_digest(purpose), _digest(purpose))

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(invoke, ("standard", "diagnostic")))
    assert {record.purpose for record in records if record is not None} == {
        "standard",
        "diagnostic",
    }
    assert observer.invocation_purpose == "standard"
    with pytest.raises(RuntimeError, match="controlled"):
        with observer.invocation_purpose_scope_from_selected_owner(policy, purpose="diagnostic"):
            raise RuntimeError("controlled scope failure")
    assert observer.invocation_purpose == "standard"
    changed = policy.model_copy(update={"protected_units": 0})
    with pytest.raises(ProducerBudgetSourceError):
        with observer.invocation_purpose_scope_from_selected_owner(changed, purpose="diagnostic"):
            pytest.fail("changed allocation admitted purpose")
    with pytest.raises(ProducerBudgetSourceError):
        with observer.invocation_purpose_scope_from_selected_owner(None, purpose="diagnostic"):
            pytest.fail("omitted allocation admitted purpose")
    assert len(FileBudgetLedger(path).snapshot().invocation_reservations) == 2


def test_async_tasks_keep_selected_purposes_isolated_on_one_observer(tmp_path: Path) -> None:
    _, middleware = _owner(tmp_path / "ledger.json")
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    policy = BudgetInvocationQuotaPolicy(allocation_id="owner", total_units=2, protected_units=1)
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    observer.bind_invocation_policy_from_selected_owner(policy)

    async def invoke(purpose: str):
        with observer.invocation_purpose_scope_from_selected_owner(policy, purpose=purpose):
            await asyncio.sleep(0)
            assert observer.invocation_purpose == purpose
            return observer.reserve_invocation(_digest(purpose), _digest(purpose))

    async def run():
        return await asyncio.gather(invoke("standard"), invoke("diagnostic"))

    records = asyncio.run(run())
    assert {record.purpose for record in records if record is not None} == {
        "standard",
        "diagnostic",
    }
    assert observer.invocation_purpose == "standard"


def test_selected_no_guarantee_allows_standard_but_never_protected_scope(tmp_path: Path) -> None:
    _, middleware = _owner(tmp_path / "ledger.json")
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=_binding(),
        budget_state=state,
        invocation_selection_pending=True,
    )
    with pytest.raises(ProducerBudgetSourceError):
        observer.bind_invocation_policy_from_selected_owner(None, purpose="diagnostic")
    observer.bind_invocation_policy_from_selected_owner(None)
    with observer.invocation_purpose_scope_from_selected_owner(None, purpose="standard"):
        assert observer.reserve_invocation(_digest("standard"), _digest("request")) is None
    for purpose in ("diagnostic", "counterevidence"):
        with pytest.raises(ProducerBudgetSourceError):
            with observer.invocation_purpose_scope_from_selected_owner(None, purpose=purpose):
                pytest.fail("no-guarantee scope admitted a protected purpose")


def test_independent_writers_cannot_overbook_one_unit(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile(total=1, protected=0)
    middleware.configure_invocation_profile_safe(profile)
    barrier = threading.Barrier(3)

    def reserve(name: str):
        other = FileBudgetLedger(path)
        barrier.wait(timeout=5)
        try:
            return other.reserve_invocation(
                _digest(name), _digest(name), profile=profile, purpose="standard"
            )
        except BudgetLedgerInvocationQuotaExhaustedError:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(reserve, ("a", "b", "c")))
    assert sum(result is not None for result in results) == 1
    assert len(ledger.snapshot().invocation_reservations) == 1


@pytest.mark.parametrize("race", ["unit", "mode"])
def test_process_writers_serialize_unit_and_mode_admission(tmp_path: Path, race: str) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile(total=1, protected=0)
    if race == "unit":
        middleware.configure_invocation_profile_safe(profile)
    ready, start = tmp_path / "ready", tmp_path / "start"
    script = """
import hashlib, sys, time
from pathlib import Path
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerInvocationProfile, BudgetLedgerInvocationQuotaExhaustedError, FileBudgetLedger,
)
path, ready, start, race, wire = sys.argv[1:]
profile = BudgetLedgerInvocationProfile.model_validate_json(wire)
ledger = FileBudgetLedger(Path(path))
Path(ready).touch()
deadline = time.monotonic() + 20
while not Path(start).exists():
    if time.monotonic() > deadline:
        raise TimeoutError('parent did not start race')
    time.sleep(.01)
try:
    if race == 'unit':
        digest = hashlib.sha256(b'child').hexdigest()
        ledger.reserve_invocation(digest, digest, profile=profile, purpose='standard')
    else:
        ledger.select_unconfigured_invocations(profile.run_binding)
    print('admitted')
except (BudgetLedgerInvocationQuotaExhaustedError, ValueError):
    print('refused')
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(path),
            str(ready),
            str(start),
            race,
            profile.model_dump_json(),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), process.communicate(timeout=5)
        start.touch()
        try:
            if race == "unit":
                ledger.reserve_invocation(
                    _digest("parent"), _digest("parent"), profile=profile, purpose="standard"
                )
            else:
                ledger.configure_invocation_profile(profile)
            parent = "admitted"
        except (BudgetLedgerInvocationQuotaExhaustedError, ValueError):
            parent = "refused"
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        assert {parent, stdout.strip()} == {"admitted", "refused"}
        snapshot = FileBudgetLedger(path).snapshot()
        if race == "unit":
            assert len(snapshot.invocation_reservations) == 1
        else:
            assert bool(snapshot.invocation_profiles) != bool(snapshot.invocation_unconfigured_runs)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_uncertain_publication_or_restart_never_grants_reexecution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile(total=1, protected=0)
    middleware.configure_invocation_profile_safe(profile)
    original_confirm = ledger._confirm_snapshot_durability

    def refuse_readback(*_args, **_kwargs):
        raise OSError("controlled readback failure")

    monkeypatch.setattr(ledger, "_confirm_snapshot_durability", refuse_readback)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        ledger.reserve_invocation(
            _digest("one"), _digest("request"), profile=profile, purpose="standard"
        )
    monkeypatch.setattr(ledger, "_confirm_snapshot_durability", original_confirm)
    reopened = FileBudgetLedger(path)
    record = reopened.resolve_invocation(_digest("one"), profile=profile)
    assert record is not None and record.status == "reserved"
    same, created = reopened.reserve_invocation(
        _digest("one"), _digest("request"), profile=profile, purpose="standard"
    )
    assert same == record and not created
    with pytest.raises(BudgetLedgerInvocationQuotaExhaustedError):
        reopened.reserve_invocation(
            _digest("different"), _digest("request2"), profile=profile, purpose="standard"
        )


def test_usd_and_producer_mutations_keep_the_unit_journal(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, middleware = _owner(path)
    profile = _profile(total=2, protected=1)
    middleware.configure_invocation_profile_safe(profile)
    original, _ = ledger.reserve_invocation(
        _digest("unit"), _digest("request"), profile=profile, purpose="standard"
    )
    ledger.record_spend("run", Decimal("0.25"), provider="fixture")
    ledger.reserve_compute("usd-compute", _digest("usd-request"), "run", Decimal("0.5"))
    ledger.settle_compute(
        "usd-compute", _digest("usd-request"), _digest("usd-outcome"), Decimal("0.4")
    )
    ledger.begin_producer_event("producer", _digest("producer-request"), "run", "m", "p")
    ledger.settle_producer_event(
        "producer",
        _digest("producer-request"),
        _digest("producer-output"),
        "run",
        "m",
        "p",
        Decimal("0.02"),
        "reported",
    )
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.invocation_reservations[original.operation_id] == original
    assert snapshot.invocation_profiles["run-a"] == profile
    assert snapshot.state.spent["run"] == Decimal("0.67")
    assert snapshot.state.provider_spent["fixture"] == Decimal("0.25")
