"""Unit-scoped bridge recovery over real budget and action-selector files.

Only the current-action/phase resolver and source-control service are local
adapters. They do not establish a genuine Control lease, source admission,
transport fetch, or authority. The bridge's selector writer/reader, filesystem
fence, FileBudgetLedger and exact BudgetMiddleware remain real. Reported costs
are controlled producer inputs, not independently reconciled provider invoices.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.quality import acquisition_world_growth as growth
from polisyos.runtime.quality import candidate_acquisition_action as action_owner
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRoutePhaseReceipt
from polisyos.scientist.orchestration.engine import budget_ledger as ledger_owner
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    BudgetLedgerReentryBudgetWindow,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref(value: str) -> str:
    return "sha256:" + _digest(value)


@dataclass(frozen=True)
class _UnitJob:
    job_id: str = "unit-acquisition-action"
    lease_owner: str = "unit-worker-one"


@dataclass(frozen=True)
class _UnitAdmission:
    job: _UnitJob = _UnitJob()
    attempt: int = 1
    scope: tuple[str, str] = ("unit-tenant", "unit-cell")


@dataclass
class _UnitActionBoundary:
    """Supply only unit action/worker snapshots to the real budget bridge."""

    selection: growth.AcquisitionCandidateSourceRoute
    phase: AcquisitionRoutePhaseReceipt
    admission: _UnitAdmission
    phase_ref: str
    failure: str | None = None

    def current(self, _bridge: Any, _closure: Any, phase_ref: str) -> tuple[Any, ...]:
        if self.failure is not None:
            raise ValueError(self.failure)
        assert phase_ref == self.phase_ref
        return self.selection, self.phase, self.admission

    def validate_phase(self, _closure: Any, _selection: Any, phase_ref: str) -> Any:
        assert phase_ref == self.phase_ref
        return self.phase


@dataclass
class _UnitSourceControl:
    """Keep the real settlement owner while adapting the unrelated Control boundary."""

    _llm_producer_settlement_store: BudgetMiddleware
    binding: BudgetLedgerProducerRunBinding
    global_limit: Decimal = Decimal("1")

    def verify_acquisition_source_budget_owner(self, *, closure: Any) -> Any:
        assert closure.run_id == self.binding.run_id
        return self.binding

    def acquisition_source_global_budget_usd(self, *, closure: Any) -> Decimal:
        assert closure.run_id == self.binding.run_id
        return self.global_limit


def _unit_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Build actual durable owners; bypass only unavailable unit action admission."""
    binding = BudgetLedgerProducerRunBinding(
        run_id="unit-budget-run",
        tenant_id="unit-tenant",
        cell_id="unit-cell",
        profile_id="unit-producer-profile",
        control_job_id="unit-source-job",
    )
    ledger_path = tmp_path / "producer-ledger.json"
    ledger = FileBudgetLedger(ledger_path)
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    selected = growth.AcquisitionCandidateSourceRoute(
        tenant_id=binding.tenant_id,
        cell_id=binding.cell_id,
        run_id=binding.run_id,
        route_id=_ref("route"),
        design_problem_ref=_ref("problem"),
        compiled_requirement_ref="unit-compiled-requirement",
        requirement_id="unit-requirement",
        candidate_digest=_ref("candidate"),
        profile_selection_ref=_ref("candidate-profile"),
        canonical_variable_id="unit-variable",
        target_slot_id="unit-target",
        country_code="GBR",
        year=2024,
        population="declared-unit-population",
        reentry_budget_usd=Decimal("0.10"),
    )
    phase = AcquisitionRoutePhaseReceipt(
        receipt_id="unit-executing-phase",
        tenant_id=binding.tenant_id,
        cell_id=binding.cell_id,
        run_id=binding.run_id,
        source_job_id=binding.control_job_id,
        route_id=selected.route_id,
        action_generation=1,
        job_id="unit-acquisition-action",
        compiled_ref=_ref("compiled"),
        planner_report_hash=_ref("planner"),
        cost_basis_hash=_ref("cost-basis"),
        decision_ref=_ref("decision"),
        coarse_phase="executing",
        receipt_phase="executing",
        recovery_state="none",
        predecessor_receipt_ref=_ref("unit-requested-predecessor-phase"),
        generated_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )
    boundary = _UnitActionBoundary(selected, phase, _UnitAdmission(), _ref("executing-phase"))
    service = _UnitSourceControl(middleware, binding)
    # The production constructor binds a real Control service. That authority
    # boundary is explicitly outside this unit; the tested methods remain real.
    bridge = growth.AcquisitionWorldGrowthBridge.__new__(growth.AcquisitionWorldGrowthBridge)
    bridge.runtime_root = tmp_path / "runtime"
    bridge._source_control_service = service
    monkeypatch.setattr(action_owner, "_current_action", boundary.current)
    monkeypatch.setattr(bridge, "_validate_action_phase", boundary.validate_phase)
    closure = SimpleNamespace(run_id=binding.run_id, source_payload_ref=_ref("source-payload"))
    pointer = bridge._action_selector_path(selected, boundary.phase_ref)
    bridge._write_action_selector(
        pointer,
        growth.AcquisitionWorldGrowthActionOutcomeSelector(
            route_id=selected.route_id, action_phase_ref=boundary.phase_ref, state="executing"
        ),
    )
    return SimpleNamespace(
        bridge=bridge,
        boundary=boundary,
        service=service,
        closure=closure,
        ledger=ledger,
        ledger_path=ledger_path,
        pointer=pointer,
        binding=binding,
    )


def _settle(case: SimpleNamespace, event: str, amount: Decimal) -> None:
    with case.service._llm_producer_settlement_store.producer_run_binding_scope(
        case.binding, control_job_attempt=1
    ):
        case.service._llm_producer_settlement_store.settle_producer_event_safe(
            event,
            _digest(event + "-request"),
            _digest(event + "-response"),
            key="nl-run:" + case.binding.run_id,
            model="controlled-unit-model",
            provider="controlled-unit-provider",
            amount=amount,
            cost_origin="reported",
        )


def _prepare(case: SimpleNamespace) -> BudgetLedgerReentryBudgetWindow:
    return case.bridge.prepare_candidate_source_budget_window(
        closure=case.closure, action_phase_ref=case.boundary.phase_ref
    )


def _resolve(case: SimpleNamespace) -> BudgetLedgerReentryBudgetWindow:
    return case.bridge._resolve_candidate_source_budget_window(
        closure=case.closure, action_phase_ref=case.boundary.phase_ref
    )


def _selector(case: SimpleNamespace) -> growth.AcquisitionWorldGrowthActionOutcomeSelector:
    _path, selected = case.bridge._load_action_selector(
        case.boundary.selection, case.boundary.phase_ref
    )
    assert selected is not None
    return selected


def _no_new_open(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("a retry must resolve the issued window, never choose another baseline")


@pytest.mark.parametrize(
    ("global_limit", "effective_limit"),
    [("1", "0.30"), ("0.25", "0.25"), ("0.10", "0.10")],
)
def test_real_selector_is_durable_before_open_and_preserves_fresh_global_minimum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    global_limit: str,
    effective_limit: str,
) -> None:
    """Observe real fsyncs and ledger open; external source fetching is out of scope."""
    case = _unit_window(tmp_path, monkeypatch)
    case.service.global_limit = Decimal(global_limit)
    _settle(case, "historic", Decimal("0.20"))
    before = case.ledger.snapshot()
    trace: list[tuple[str, str | None]] = []
    real_fsync = os.fsync
    real_open = case.service._llm_producer_settlement_store.open_reentry_budget_window_safe

    def observe_fsync(fd: int) -> None:
        real_fsync(fd)
        opened = os.fstat(fd)
        temporary = case.pointer.with_suffix(".tmp")
        if temporary.exists():
            selected_file = temporary.stat()
            if (opened.st_dev, opened.st_ino) == (selected_file.st_dev, selected_file.st_ino):
                trace.append(
                    (
                        "file_fsync",
                        json.loads(temporary.read_text()).get("candidate_budget_window_state"),
                    )
                )
        directory = case.pointer.parent.stat()
        if stat.S_ISDIR(opened.st_mode) and (opened.st_dev, opened.st_ino) == (
            directory.st_dev,
            directory.st_ino,
        ):
            trace.append(
                (
                    "directory_fsync",
                    json.loads(case.pointer.read_text()).get("candidate_budget_window_state"),
                )
            )

    def observe_open(*args: Any, **kwargs: Any) -> BudgetLedgerReentryBudgetWindow:
        assert _selector(case).candidate_budget_window_state == "issuing"
        assert ("file_fsync", "issuing") in trace
        assert ("directory_fsync", "issuing") in trace
        trace.append(("ledger_open", None))
        return real_open(*args, **kwargs)

    monkeypatch.setattr(growth.os, "fsync", observe_fsync)
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", observe_open
    )
    window = _prepare(case)
    assert window.baseline_total_usd == Decimal("0.20")
    assert window.baseline_revision == before.revision
    assert window.effective_limit_usd == Decimal(effective_limit)
    assert window.fresh_limit_usd == Decimal("0.10")
    assert window.global_limit_usd == Decimal(global_limit)
    assert window.scope.source_payload_ref == case.closure.source_payload_ref
    assert window.scope.profile_selection_ref == case.boundary.selection.profile_selection_ref
    selected = _selector(case)
    assert selected.candidate_budget_window_state == "selected"
    assert selected.candidate_budget_window_id == window.window_id
    assert selected.candidate_budget_window_digest == window.record_digest
    assert trace.index(("directory_fsync", "issuing")) < trace.index(("ledger_open", None))
    assert trace.index(("ledger_open", None)) < trace.index(("file_fsync", "selected"))
    assert ("directory_fsync", "selected") in trace
    assert FileBudgetLedger(case.ledger_path).snapshot().reentry_budget_windows == {
        window.window_id: window
    }
    assert _resolve(case) == window


@pytest.mark.parametrize("crash_point", ["before_open", "after_open"])
def test_issuing_marker_distinguishes_crash_before_and_after_actual_ledger_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_point: str
) -> None:
    """Recovery never resamples a baseline after a durable issuing intent."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    store = case.service._llm_producer_settlement_store
    real_open = store.open_reentry_budget_window_safe
    issued: list[BudgetLedgerReentryBudgetWindow] = []

    def interrupted_open(*args: Any, **kwargs: Any) -> Any:
        assert _selector(case).candidate_budget_window_state == "issuing"
        if crash_point == "after_open":
            issued.append(real_open(*args, **kwargs))
        raise OSError("unit interruption between issuing and selected selector")

    with monkeypatch.context() as crash:
        crash.setattr(store, "open_reentry_budget_window_safe", interrupted_open)
        with pytest.raises(OSError, match="unit interruption"):
            _prepare(case)
    assert _selector(case).candidate_budget_window_state == "issuing"
    assert _selector(case).candidate_budget_window_id is None
    assert _selector(case).candidate_budget_window_digest is None
    _settle(case, "after-interruption", Decimal("0.03"))
    # A fresh owner object must resolve the already-issued window from disk.
    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(case.ledger_path))
    case.service._llm_producer_settlement_store = reopened
    monkeypatch.setattr(reopened, "open_reentry_budget_window_safe", _no_new_open)
    if crash_point == "before_open":
        with pytest.raises(ValueError, match="candidate_source_budget_window_binding_mismatch"):
            _prepare(case)
        with pytest.raises(ValueError, match="candidate_source_budget_window_not_selected"):
            _resolve(case)
        assert case.ledger.snapshot().reentry_budget_windows == {}
        assert _selector(case).candidate_budget_window_state == "issuing"
    else:
        original = issued[0]
        assert original.baseline_total_usd == Decimal("0.20")
        assert _prepare(case) == _resolve(case) == original
        assert _selector(case).candidate_budget_window_id == original.window_id
        for attempt in (2, 3):
            # The action adapter declares a stable retry at this same phase.
            # Its genuine Control admission is outside the unit test boundary.
            case.boundary.admission = replace(case.boundary.admission, attempt=attempt)
            assert _prepare(case) == _resolve(case) == original
            assert original.scope.action_phase_ref == case.boundary.phase_ref
            assert _selector(case).candidate_budget_window_id == original.window_id
            assert _selector(case).candidate_budget_window_digest == original.record_digest
        snapshot = case.ledger.snapshot()
        assert snapshot.reentry_budget_windows == {original.window_id: original}
        assert (
            sum(row.operation == "open_reentry_budget_window" for row in snapshot.recent_mutations)
            == 1
        )


@pytest.mark.parametrize("selector_stage", ["issuing", "selected"])
@pytest.mark.parametrize("ledger_loss", ["rollback", "missing"])
def test_lost_ledger_window_never_creates_another_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector_stage: str,
    ledger_loss: str,
) -> None:
    """Both recovery markers refuse a rolled-back or absent real ledger window."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    before_open = case.ledger_path.read_bytes()
    window = _prepare(case)
    if selector_stage == "issuing":
        selected = _selector(case)
        case.bridge._write_action_selector(
            case.pointer,
            selected.model_copy(
                update={
                    "candidate_budget_window_id": None,
                    "candidate_budget_window_digest": None,
                    "candidate_budget_window_state": "issuing",
                }
            ),
        )
    if ledger_loss == "rollback":
        case.ledger_path.write_bytes(before_open)
        expected = "candidate_source_budget_window_binding_mismatch"
    else:
        case.ledger_path.unlink()
        expected = "budget_ledger_identity_not_established"
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", _no_new_open
    )
    with pytest.raises(ValueError, match=expected):
        _prepare(case)
    assert _selector(case).candidate_budget_window_state == selector_stage
    if ledger_loss == "rollback":
        assert case.ledger_path.read_bytes() == before_open
        assert case.ledger.snapshot().reentry_budget_windows == {}
    else:
        assert not case.ledger_path.exists()
    assert window.baseline_total_usd == Decimal("0.20")


@pytest.mark.parametrize(
    "changed", ["fresh_cap", "global_cap", "source", "profile", "window_id", "window_digest"]
)
def test_selected_window_refuses_changed_cap_source_profile_or_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    """Changing the current request cannot renew the selected action allowance."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    window = _prepare(case)
    before = case.ledger.snapshot()
    if changed == "fresh_cap":
        case.boundary.selection = case.boundary.selection.model_copy(
            update={"reentry_budget_usd": Decimal("0.20")}
        )
    elif changed == "global_cap":
        case.service.global_limit = Decimal("0.90")
    elif changed == "source":
        case.closure.source_payload_ref = _ref("other-source-payload")
    elif changed == "profile":
        case.boundary.selection = case.boundary.selection.model_copy(
            update={"profile_selection_ref": _ref("other-profile")}
        )
    elif changed == "window_id":
        case.bridge._write_action_selector(
            case.pointer,
            _selector(case).model_copy(update={"candidate_budget_window_id": "a" * 64}),
        )
    else:
        case.bridge._write_action_selector(
            case.pointer,
            _selector(case).model_copy(update={"candidate_budget_window_digest": "a" * 64}),
        )
    expected = (
        "reentry_budget_window_conflict"
        if changed in {"source", "profile"}
        else "candidate_source_budget_window_binding_mismatch"
    )
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", _no_new_open
    )
    for reopen in (_prepare, _resolve):
        with pytest.raises(ValueError, match=expected):
            reopen(case)
    assert case.ledger.snapshot() == before
    assert before.reentry_budget_windows == {window.window_id: window}


def test_same_window_id_cannot_hide_a_coherently_changed_baseline_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid later producer prefix cannot replace the action's original record."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    original = _prepare(case)
    _settle(case, "later", Decimal("0.03"))
    snapshot = case.ledger.snapshot()
    total, prefix = ledger_owner._reentry_prefix(snapshot, case.binding, cutoff=snapshot.revision)
    assert total == Decimal("0.23")
    altered = original.model_copy(
        update={
            "baseline_total_usd": total,
            "baseline_revision": snapshot.revision,
            "baseline_prefix_digest": prefix,
            "revision": snapshot.revision + 1,
        }
    )
    # Adversarially replace only this temporary ledger's window with a complete
    # record over genuine producer entries. The real ledger reader must accept
    # its internal prefix before the bridge's independently stored digest fails.
    payload = json.loads(case.ledger_path.read_text())
    payload["revision"] = altered.revision
    payload["reentry_budget_windows"][original.window_id] = altered.model_dump(mode="json")
    case.ledger_path.write_text(json.dumps(payload, sort_keys=True) + "\n")
    resolved = FileBudgetLedger(case.ledger_path).resolve_reentry_budget_window(original.scope)
    assert resolved == altered
    assert resolved.window_id == original.window_id
    assert resolved.record_digest != original.record_digest
    assert resolved.effective_limit_usd == Decimal("0.33")
    assert _selector(case).candidate_budget_window_digest == original.record_digest
    unchanged_ledger = case.ledger_path.read_bytes()
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", _no_new_open
    )
    for reopen in (_prepare, _resolve):
        with pytest.raises(ValueError, match="candidate_source_budget_window_binding_mismatch"):
            reopen(case)
    assert case.ledger_path.read_bytes() == unchanged_ledger
    assert _selector(case).candidate_budget_window_id == original.window_id
    assert _selector(case).candidate_budget_window_digest == original.record_digest


@pytest.mark.parametrize("movement", ["lease_owner", "attempt", "scope", "phase", "lease_lost"])
def test_inflight_worker_or_phase_movement_refuses_selection_without_resetting_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, movement: str
) -> None:
    """The real bridge re-reads the unit action boundary after durable ledger open."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    store = case.service._llm_producer_settlement_store
    real_open = store.open_reentry_budget_window_safe
    original_admission, original_phase = case.boundary.admission, case.boundary.phase
    issued: list[BudgetLedgerReentryBudgetWindow] = []

    def move_after_real_open(*args: Any, **kwargs: Any) -> BudgetLedgerReentryBudgetWindow:
        window = real_open(*args, **kwargs)
        issued.append(window)
        if movement == "lease_owner":
            case.boundary.admission = replace(
                original_admission,
                job=replace(original_admission.job, lease_owner="unit-worker-two"),
            )
        elif movement == "attempt":
            case.boundary.admission = replace(original_admission, attempt=2)
        elif movement == "scope":
            case.boundary.admission = replace(
                original_admission, scope=("other-tenant", "unit-cell")
            )
        elif movement == "phase":
            case.boundary.phase = original_phase.model_copy(
                update={"receipt_id": "other-unit-phase"}
            )
        else:
            case.boundary.failure = "unit_current_worker_lease_lost"
        return window

    with monkeypatch.context() as movement_patch:
        movement_patch.setattr(store, "open_reentry_budget_window_safe", move_after_real_open)
        expected = (
            "unit_current_worker_lease_lost"
            if movement == "lease_lost"
            else "candidate_source_budget_action_changed"
        )
        with pytest.raises(ValueError, match=expected):
            _prepare(case)
    original = issued[0]
    assert _selector(case).candidate_budget_window_state == "issuing"
    assert _selector(case).candidate_budget_window_id is None
    assert case.ledger.snapshot().reentry_budget_windows == {original.window_id: original}
    case.boundary.admission, case.boundary.phase = original_admission, original_phase
    case.boundary.failure = None
    _settle(case, "after-movement", Decimal("0.04"))
    monkeypatch.setattr(store, "open_reentry_budget_window_safe", _no_new_open)
    assert _prepare(case) == _resolve(case) == original
    assert original.baseline_total_usd == Decimal("0.20")


def test_new_phase_without_verified_ancestry_refuses_the_existing_action_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new phase key cannot select an old window as a newly issued allowance."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    original = _prepare(case)
    _settle(case, "after-original", Decimal("0.03"))
    case.boundary.phase_ref = _ref("retry-phase-without-ancestry")
    case.boundary.phase = case.boundary.phase.model_copy(update={"receipt_id": "retry-unit-phase"})
    case.pointer = case.bridge._action_selector_path(
        case.boundary.selection, case.boundary.phase_ref
    )
    case.bridge._write_action_selector(
        case.pointer,
        growth.AcquisitionWorldGrowthActionOutcomeSelector(
            route_id=case.boundary.selection.route_id,
            action_phase_ref=case.boundary.phase_ref,
            state="executing",
        ),
    )
    with pytest.raises(ValueError, match="candidate_source_budget_window_binding_mismatch"):
        _prepare(case)
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", _no_new_open
    )
    with pytest.raises(ValueError, match="candidate_source_budget_window_binding_mismatch"):
        _prepare(case)
    assert _selector(case).candidate_budget_window_state == "issuing"
    assert case.ledger.snapshot().reentry_budget_windows == {original.window_id: original}
    assert original.baseline_total_usd == Decimal("0.20")


@pytest.mark.parametrize("after_issue", [False, True])
def test_missing_real_action_selector_refuses_without_opening_a_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_issue: bool
) -> None:
    """Neither creation nor recovery substitutes for the missing selected action file."""
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "historic", Decimal("0.20"))
    original = _prepare(case) if after_issue else None
    before = case.ledger.snapshot()
    case.pointer.unlink()
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store, "open_reentry_budget_window_safe", _no_new_open
    )
    for reopen in (_prepare, _resolve):
        with pytest.raises(ValueError, match="acquisition_owner_outcome_not_established"):
            reopen(case)
    assert not case.pointer.exists()
    assert case.ledger.snapshot() == before
    assert len(before.reentry_budget_windows) == int(after_issue)
    if original is not None:
        assert before.reentry_budget_windows[original.window_id] == original
