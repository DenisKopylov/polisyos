"""Owner-bound fresh reentry budget over the real producer ledger."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    BudgetLedgerReentryBudgetScope,
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


def _ref(value: str) -> str:
    return "sha256:" + _digest(value)


def _binding() -> BudgetLedgerProducerRunBinding:
    return BudgetLedgerProducerRunBinding(
        run_id="run-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="profile-a",
        control_job_id="job-run-a",
    )


def _scope() -> BudgetLedgerReentryBudgetScope:
    return BudgetLedgerReentryBudgetScope(
        run_binding=_binding(),
        action_job_id="acquisition-job",
        route_id=_ref("route"),
        action_generation=1,
        action_phase_ref=_ref("executing-phase"),
        source_payload_ref=_ref("source-payload"),
        profile_selection_ref=_ref("selected-profile"),
    )


def _owner(path: Path) -> tuple[FileBudgetLedger, BudgetMiddleware]:
    ledger = FileBudgetLedger(path)
    return ledger, BudgetMiddleware(BudgetState(), ledger=ledger)


def _settle(store: BudgetMiddleware, event: str, amount: Decimal | None) -> None:
    with store.producer_run_binding_scope(_binding(), control_job_attempt=1):
        store.settle_producer_event_safe(
            event,
            _digest(event + "-request"),
            _digest(event + "-response"),
            key="nl-run:run-a",
            model="controlled-model",
            provider="controlled-provider",
            amount=amount,
            cost_origin="unknown" if amount is None else "reported",
        )


def _pending(store: BudgetMiddleware, event: str) -> None:
    with store.producer_run_binding_scope(_binding(), control_job_attempt=1):
        store.begin_producer_event_safe(
            event,
            _digest(event + "-request"),
            key="nl-run:run-a",
            model="controlled-model",
            provider="controlled-provider",
        )


def _observer(store: BudgetMiddleware, scope: BudgetLedgerReentryBudgetScope):
    window = store.resolve_reentry_budget_window_safe(scope)
    assert window is not None
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)})
    return ProducerBudgetObserver(
        settlement_store=store,
        producer_run_binding=_binding(),
        budget_state=state,
        reentry_budget_scope=scope,
    )


def test_fresh_allowance_counts_new_spend_without_erasing_historical_cost(tmp_path: Path) -> None:
    ledger, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    scope = _scope()
    window = store.open_reentry_budget_window_safe(
        scope, fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    assert window.baseline_total_usd == Decimal("0.20")
    assert window.effective_limit_usd == Decimal("0.30")
    assert len(window.record_digest) == 64
    observer = _observer(store, scope)
    assert observer.admit().remaining_usd == Decimal("0.10")
    _settle(store, "new-five", Decimal("0.05"))
    current = observer.admit()
    assert current.producer_spent_usd == Decimal("0.25")
    assert current.remaining_usd == Decimal("0.05")
    _settle(store, "new-six", Decimal("0.06"))
    with pytest.raises(BudgetExhaustedError):
        observer.admit()
    assert observer.last_checked.producer_spent_usd == Decimal("0.31")
    assert FileBudgetLedger(ledger._path).snapshot().reentry_budget_windows[window.window_id] == (
        window
    )


def test_global_cap_can_be_tighter_than_the_fresh_allowance(tmp_path: Path) -> None:
    _, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    window = store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("0.23")
    )
    assert window.effective_limit_usd == Decimal("0.23")
    observer = _observer(store, _scope())
    assert observer.admit().remaining_usd == Decimal("0.03")
    _settle(store, "new", Decimal("0.05"))
    with pytest.raises(BudgetExhaustedError):
        observer.admit()


def test_new_run_spend_counts_conservatively_against_concurrent_action_windows(
    tmp_path: Path,
) -> None:
    _, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    first, second = _scope(), _scope().model_copy(update={"action_job_id": "other-action"})
    for scope in (first, second):
        store.open_reentry_budget_window_safe(
            scope, fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )
    observers = [_observer(store, scope) for scope in (first, second)]
    _settle(store, "other-action-spend", Decimal("0.08"))
    assert [observer.admit().remaining_usd for observer in observers] == [
        Decimal("0.02"),
        Decimal("0.02"),
    ]
    _settle(store, "further-spend", Decimal("0.03"))
    for observer in observers:
        with pytest.raises(BudgetExhaustedError):
            observer.admit()


def test_inexact_decimal_cannot_round_up_a_new_fresh_budget(tmp_path: Path) -> None:
    ledger, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    with pytest.raises(ValueError, match="reentry_budget_arithmetic_not_established"):
        store.open_reentry_budget_window_safe(
            _scope(),
            fresh_limit_usd=Decimal("0.10000000000000000000000000009"),
            global_limit_usd=Decimal("1"),
        )
    assert ledger.snapshot().reentry_budget_windows == {}


def test_inexact_historical_or_new_producer_sum_never_authorizes(tmp_path: Path) -> None:
    _, store = _owner(tmp_path / "historical.json")
    _settle(store, "historic", Decimal("0.20"))
    _settle(store, "precise-old", Decimal("0.10000000000000000000000000009"))
    with pytest.raises(ValueError, match="reentry_budget_arithmetic_not_established"):
        store.open_reentry_budget_window_safe(
            _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )

    _, later_store = _owner(tmp_path / "later.json")
    _settle(later_store, "historic", Decimal("0.20"))
    later_store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.50"), global_limit_usd=Decimal("1")
    )
    observer = _observer(later_store, _scope())
    assert observer.admit().producer_spent_usd == Decimal("0.20")
    _settle(later_store, "precise-new", Decimal("0.10000000000000000000000000009"))
    with pytest.raises(
        ProducerBudgetSourceError, match="reentry_budget_arithmetic_not_established"
    ):
        observer.admit()
    assert observer.last_checked.producer_spent_usd == Decimal("0.20")


def test_one_live_budget_state_cannot_switch_between_window_and_unbounded_modes(
    tmp_path: Path,
) -> None:
    _, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    window = store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )

    def state() -> BudgetState:
        return BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
        )

    ordinary_state = state()
    ordinary = ProducerBudgetObserver(
        settlement_store=store, producer_run_binding=_binding(), budget_state=ordinary_state
    )
    assert ordinary.admit().producer_spent_usd == Decimal("0.20")
    with pytest.raises(ProducerBudgetSourceError, match="state_owner_binding_mismatch"):
        ProducerBudgetObserver(
            settlement_store=store,
            producer_run_binding=_binding(),
            budget_state=ordinary_state,
            reentry_budget_scope=_scope(),
        )

    window_state = state()
    window_observer = ProducerBudgetObserver(
        settlement_store=store,
        producer_run_binding=_binding(),
        budget_state=window_state,
        reentry_budget_scope=_scope(),
    )
    assert window_observer.admit().remaining_usd == Decimal("0.10")
    with pytest.raises(ProducerBudgetSourceError, match="state_owner_binding_mismatch"):
        ProducerBudgetObserver(
            settlement_store=store, producer_run_binding=_binding(), budget_state=window_state
        )
    other = _scope().model_copy(update={"action_job_id": "different-action"})
    store.open_reentry_budget_window_safe(
        other, fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    with pytest.raises(ProducerBudgetSourceError, match="state_owner_binding_mismatch"):
        ProducerBudgetObserver(
            settlement_store=store,
            producer_run_binding=_binding(),
            budget_state=window_state,
            reentry_budget_scope=other,
        )


def test_retry_new_phase_reuses_original_baseline_and_rejects_changed_basis(tmp_path: Path) -> None:
    ledger, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    original = store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    _settle(store, "after-baseline", Decimal("0.03"))
    retry = _scope().model_copy(update={"action_phase_ref": _ref("new-attempt-phase")})
    assert retry.window_id == original.window_id
    same = FileBudgetLedger(ledger._path).open_reentry_budget_window(
        retry, fresh_limit_usd=Decimal("0.100"), global_limit_usd=Decimal("1.0")
    )
    assert same == original and same.baseline_total_usd == Decimal("0.20")
    assert same.record_digest == original.record_digest
    changed_record = original.model_copy(update={"baseline_total_usd": Decimal("0.21")})
    assert changed_record.window_id == original.window_id
    assert changed_record.record_digest != original.record_digest
    assert _observer(store, retry).admit().remaining_usd == Decimal("0.07")
    for altered in (
        retry.model_copy(update={"source_payload_ref": _ref("foreign-payload")}),
        retry.model_copy(update={"profile_selection_ref": _ref("foreign-profile")}),
    ):
        with pytest.raises(ValueError, match="window_conflict"):
            store.resolve_reentry_budget_window_safe(altered)
    with pytest.raises(ValueError, match="window_conflict"):
        store.open_reentry_budget_window_safe(
            retry, fresh_limit_usd=Decimal("0.20"), global_limit_usd=Decimal("1")
        )


@pytest.mark.parametrize("status", ["pending", "unknown", "empty"])
def test_unresolved_or_missing_history_never_becomes_a_zero_baseline(
    tmp_path: Path, status: str
) -> None:
    ledger, store = _owner(tmp_path / "ledger.json")
    if status != "empty":
        _settle(store, "historic", Decimal("0.20"))
        if status == "pending":
            _pending(store, "unresolved")
        else:
            _settle(store, "unresolved", None)
    with pytest.raises(ValueError, match="producer_(prefix|outcome)_not_established"):
        store.open_reentry_budget_window_safe(
            _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )
    assert ledger.snapshot().reentry_budget_windows == {}


def test_later_pending_blocks_then_exact_settlement_recovers_same_window(tmp_path: Path) -> None:
    _, store = _owner(tmp_path / "ledger.json")
    _settle(store, "historic", Decimal("0.20"))
    window = store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    observer = _observer(store, _scope())
    _pending(store, "later")
    with pytest.raises(ProducerBudgetSourceError, match="producer_event_not_settled"):
        observer.admit()
    _settle(store, "later", Decimal("0.05"))
    assert observer.admit().remaining_usd == Decimal("0.05")
    assert store.resolve_reentry_budget_window_safe(_scope()) == window


def test_unacknowledged_window_write_reopens_the_same_owner_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ledger.json"
    ledger, store = _owner(path)
    _settle(store, "historic", Decimal("0.20"))

    def refuse_readback(*_args, **_kwargs):
        raise OSError("controlled readback failure")

    monkeypatch.setattr(ledger, "_confirm_snapshot_durability", refuse_readback)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        ledger.open_reentry_budget_window(
            _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )
    reopened = FileBudgetLedger(path)
    original = reopened.resolve_reentry_budget_window(_scope())
    assert original is not None and original.baseline_total_usd == Decimal("0.20")
    assert (
        reopened.open_reentry_budget_window(
            _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )
        == original
    )


def test_two_independent_writers_cannot_choose_different_baselines(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _, store = _owner(path)
    _settle(store, "historic", Decimal("0.20"))
    barrier = threading.Barrier(2)

    def issue(_index: int):
        ledger = FileBudgetLedger(path)
        barrier.wait(timeout=5)
        return ledger.open_reentry_budget_window(
            _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(issue, range(2))
    assert first == second and first.baseline_total_usd == Decimal("0.20")
    assert len(FileBudgetLedger(path).snapshot().reentry_budget_windows) == 1


def test_tampered_prefix_or_foreign_owner_never_authorizes(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger, store = _owner(path)
    _settle(store, "historic", Decimal("0.20"))
    window = store.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    foreign = _scope().model_copy(
        update={"run_binding": _binding().model_copy(update={"tenant_id": "foreign"})}
    )
    assert ledger.resolve_reentry_budget_window(foreign) is None
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)})
    with pytest.raises((ValueError, ProducerBudgetSourceError)):
        ProducerBudgetObserver(
            settlement_store=store,
            producer_run_binding=_binding(),
            budget_state=state,
            reentry_budget_scope=foreign,
        )
    wire = json.loads(path.read_bytes())
    wire["reentry_budget_windows"][window.window_id]["baseline_total_usd"] = "0.90"
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(json.dumps(wire))
    with pytest.raises(ValueError, match="window_prefix_mismatch"):
        FileBudgetLedger(corrupt).snapshot()


def test_actual_v17_snapshot_and_anchor_reopen_then_upgrade(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "budget-ledger-1.7-actual.json"
    payload = fixture.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == (
        "409933fefa538a7915135dd7ad7c860ecae23f36119b13e9d90168c43ea945c5"
    )
    path = tmp_path / "legacy.json"
    path.write_bytes(payload)
    ledger = FileBudgetLedger(path)
    owner, resource, _new_anchor = ledger.continuation_binding()
    legacy_anchor = (3, "b832ae267fbf17754dea684ae302dc9a6ff5c175838311b36f2e90d78a6bbef3")
    continuation = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(path),
        continuation_owner_identity=owner,
        continuation_resource_identity=resource,
        continuation_snapshot_anchor=legacy_anchor,
    )
    assert path.read_bytes() == payload
    assert continuation.snapshot_safe().producer_settlements["legacy-event"].amount == Decimal(
        "0.20"
    )
    continuation.open_reentry_budget_window_safe(
        _scope(), fresh_limit_usd=Decimal("0.10"), global_limit_usd=Decimal("1")
    )
    assert json.loads(path.read_bytes())["schema_version"] == "1.8"
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.producer_settlements["legacy-event"].amount == Decimal("0.20")
    assert len(snapshot.invocation_reservations) == 1
    with pytest.raises(ValueError, match="snapshot_anchor_mismatch"):
        BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(path),
            continuation_owner_identity=owner,
            continuation_resource_identity=resource,
            continuation_snapshot_anchor=legacy_anchor,
        )
