"""Native re-entry budget selector mechanics over real durable budget owners.

This unit reuses the real FileBudgetLedger, BudgetMiddleware and action-selector
fixture from the candidate window tests. Only current Native action/profile
resolution and the final preflight call are scripted. It does not establish a
genuine Control lease, Native Source/N5 authority, or transport permission.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.quality import acquisition_world_growth as growth


def _ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _native_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Reuse the canonical budget/selector fixture and script Native readers."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _unit_window,
    )

    case = _unit_window(tmp_path, monkeypatch)
    case.native_profile_ref = _ref("original-native-profile-selection")
    case.n5_profile = object()

    def current_action(*, closure: Any, action_phase_ref: str) -> tuple[Any, ...]:
        assert closure is case.closure
        assert action_phase_ref
        return case.boundary.selection, case.boundary.phase, case.boundary.admission

    def selected_profile(closure: Any) -> tuple[object, str]:
        assert closure is case.closure
        return case.n5_profile, case.native_profile_ref

    case.native_current_action = current_action
    monkeypatch.setattr(case.bridge, "_current_native_reentry_action", current_action)
    monkeypatch.setattr(case.bridge, "_native_derivation_budget_profile", selected_profile)
    return case


def _native_window(
    case: SimpleNamespace, *, create: bool, action_phase_ref: str | None = None
) -> Any:
    return case.bridge._native_derivation_budget_window(
        closure=case.closure,
        action_phase_ref=action_phase_ref or case.boundary.phase_ref,
        create=create,
    )


def _native_selector(case: SimpleNamespace) -> growth.AcquisitionWorldGrowthActionOutcomeSelector:
    _pointer, selector = case.bridge._load_action_selector(
        case.boundary.selection, case.boundary.phase_ref
    )
    assert selector is not None
    return selector


def _open_count(case: SimpleNamespace) -> int:
    return sum(
        row.operation == "open_reentry_budget_window"
        for row in case.ledger.snapshot().recent_mutations
    )


def test_native_window_persists_issuing_before_open_and_reopens_exact_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native uses its own 1.3 selector fields and never resamples on retry."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _no_new_open,
        _settle,
    )

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-window-history", Decimal("0.02"))
    store = case.service._llm_producer_settlement_store
    real_open = store.open_reentry_budget_window_safe
    observed: list[str] = []

    def observe_open(*args: Any, **kwargs: Any) -> Any:
        selector = _native_selector(case)
        assert selector.schema_version == "AcquisitionWorldGrowthActionOutcomeSelector@1.3"
        assert selector.native_budget_window_state == "issuing"
        assert selector.native_budget_window_id is None
        assert selector.native_budget_window_digest is None
        assert selector.candidate_budget_window_state is None
        observed.append(selector.native_budget_window_state)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(store, "open_reentry_budget_window_safe", observe_open)
    window = _native_window(case, create=True)
    assert observed == ["issuing"]
    selector = _native_selector(case)
    assert selector.native_budget_window_state == "selected"
    assert selector.native_budget_window_id == window.window_id
    assert selector.native_budget_window_digest == window.record_digest
    assert selector.candidate_budget_window_state is None
    assert window.scope.profile_selection_ref == case.native_profile_ref
    assert window.scope.source_payload_ref == case.closure.source_payload_ref
    assert case.ledger.snapshot().reentry_budget_windows == {window.window_id: window}

    monkeypatch.setattr(store, "open_reentry_budget_window_safe", _no_new_open)
    assert _native_window(case, create=True) == window
    assert _native_window(case, create=False) == window
    assert _open_count(case) == 1


@pytest.mark.parametrize("selector_stage", ["issuing", "selected"])
@pytest.mark.parametrize("ledger_loss", ["rollback", "missing"])
def test_native_issuing_or_selected_marker_never_reopens_a_lost_ledger_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector_stage: str,
    ledger_loss: str,
) -> None:
    """A durable Native marker makes a lost baseline fail closed."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _no_new_open,
        _settle,
    )

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-lost-window-history", Decimal("0.02"))
    before_open = case.ledger_path.read_bytes()
    window = _native_window(case, create=True)
    if selector_stage == "issuing":
        selector = _native_selector(case)
        case.bridge._write_action_selector(
            case.pointer,
            growth.AcquisitionWorldGrowthActionOutcomeSelector.model_validate(
                {
                    **selector.model_dump(mode="python"),
                    "native_budget_window_id": None,
                    "native_budget_window_digest": None,
                    "native_budget_window_state": "issuing",
                }
            ),
        )

    if ledger_loss == "rollback":
        case.ledger_path.write_bytes(before_open)
    else:
        case.ledger_path.unlink()
    monkeypatch.setattr(
        case.service._llm_producer_settlement_store,
        "open_reentry_budget_window_safe",
        _no_new_open,
    )

    with pytest.raises(ValueError):
        _native_window(case, create=True)
    selector = _native_selector(case)
    assert selector.native_budget_window_state == selector_stage
    assert (
        selector.native_budget_window_id is None and selector.native_budget_window_digest is None
    ) == (selector_stage == "issuing")
    if ledger_loss == "rollback":
        assert case.ledger_path.read_bytes() == before_open
        assert case.ledger.snapshot().reentry_budget_windows == {}
    else:
        assert not case.ledger_path.exists()
    assert window.scope.profile_selection_ref == case.native_profile_ref


@pytest.mark.parametrize("changed", ["window_id", "window_digest", "profile", "source"])
def test_native_selected_window_refuses_id_digest_profile_or_source_grafts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    """A selected ledger record cannot be rebound to changed Native inputs."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _no_new_open,
        _settle,
    )

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-graft-history", Decimal("0.02"))
    window = _native_window(case, create=True)
    before = case.ledger.snapshot()
    if changed in {"window_id", "window_digest"}:
        selector = _native_selector(case)
        field = (
            "native_budget_window_id" if changed == "window_id" else "native_budget_window_digest"
        )
        case.bridge._write_action_selector(
            case.pointer,
            selector.model_copy(update={field: "a" * 64}),
        )
    elif changed == "profile":
        case.native_profile_ref = _ref("foreign-native-profile-selection")
    else:
        case.closure.source_payload_ref = _ref("changed-native-source-payload")

    monkeypatch.setattr(
        case.service._llm_producer_settlement_store,
        "open_reentry_budget_window_safe",
        _no_new_open,
    )
    with pytest.raises(ValueError):
        _native_window(case, create=False)
    assert case.ledger.snapshot() == before
    assert before.reentry_budget_windows == {window.window_id: window}


def test_native_selected_window_refuses_action_phase_graft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second phase cannot resolve this action's selected budget window."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import _settle

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-phase-graft-history", Decimal("0.02"))
    window = _native_window(case, create=True)
    before = case.ledger.snapshot()
    other_phase_ref = _ref("grafted-native-action-phase")

    def validate_phase(_closure: Any, _selected: Any, _phase_ref: str) -> Any:
        return case.boundary.phase

    monkeypatch.setattr(case.bridge, "_validate_action_phase", validate_phase)
    with pytest.raises(ValueError, match="acquisition_owner_outcome_not_established"):
        _native_window(case, create=False, action_phase_ref=other_phase_ref)
    assert case.ledger.snapshot() == before
    assert before.reentry_budget_windows == {window.window_id: window}

    payload = json.loads(case.pointer.read_text())
    payload["action_phase_ref"] = other_phase_ref
    case.pointer.write_text(json.dumps(payload, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="acquisition_action_outcome_selector_binding_mismatch"):
        _native_window(case, create=False)
    assert case.ledger.snapshot() == before


@pytest.mark.parametrize("movement", ["lease_owner", "attempt", "scope"])
def test_native_action_movement_after_open_leaves_selector_issuing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    movement: str,
) -> None:
    """The post-open current-worker check fences lease and admission changes."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import _settle

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-action-movement-history", Decimal("0.02"))
    original_current = case.native_current_action
    current_calls = 0

    def move_after_issue(*, closure: Any, action_phase_ref: str) -> tuple[Any, ...]:
        nonlocal current_calls
        current_calls += 1
        if current_calls == 2:
            admission = case.boundary.admission
            if movement == "lease_owner":
                job = replace(admission.job, lease_owner="unit-worker-two")
                case.boundary.admission = replace(admission, job=job)
            elif movement == "attempt":
                case.boundary.admission = replace(admission, attempt=admission.attempt + 1)
            else:
                case.boundary.admission = replace(admission, scope=("other-tenant", "other-cell"))
        return original_current(closure=closure, action_phase_ref=action_phase_ref)

    monkeypatch.setattr(case.bridge, "_current_native_reentry_action", move_after_issue)
    with pytest.raises(ValueError, match="native_source_budget_action_changed"):
        _native_window(case, create=True)
    assert current_calls == 2
    selector = _native_selector(case)
    assert selector.native_budget_window_state == "issuing"
    assert selector.native_budget_window_id is None
    assert selector.native_budget_window_digest is None
    assert len(case.ledger.snapshot().reentry_budget_windows) == 1
    assert _open_count(case) == 1


def test_native_prepare_selects_window_before_preflight_and_real_observer_reopens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preflight receives the selected scope; the real observer binds it."""
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
        ProducerBudgetObserver,
    )
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import _settle

    case = _native_case(tmp_path, monkeypatch)
    _settle(case, "native-preflight-history", Decimal("0.02"))
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="native-reentry-unit-profile",
        total_units=3,
        protected_units=1,
    )
    case.n5_profile = SimpleNamespace(invocation_quota_policy=policy)
    observed: list[tuple[Any, Any, Any]] = []

    def script_preflight(*, closure: Any, budget_state: Any, reentry_budget_scope: Any) -> None:
        assert closure is case.closure
        selector = _native_selector(case)
        assert selector.native_budget_window_state == "selected"
        selected_window = case.ledger.snapshot().reentry_budget_windows[
            selector.native_budget_window_id
        ]
        assert reentry_budget_scope == selected_window.scope
        assert budget_state.limits["run"].max_usd == selected_window.effective_limit_usd
        observed.append((budget_state, reentry_budget_scope, case.n5_profile))

    monkeypatch.setattr(case.bridge, "native_derivation_reentry_preflight", script_preflight)
    assert (
        case.bridge.prepare_native_derivation_reentry_budget(
            closure=case.closure, action_phase_ref=case.boundary.phase_ref
        )
        is None
    )
    assert len(observed) == 1
    budget_state, reentry_scope, selected_n5 = observed[0]
    assert selected_n5.invocation_quota_policy == policy
    assert reentry_scope.profile_selection_ref == case.native_profile_ref

    selected_profile = BudgetLedgerInvocationProfile.from_policy(case.binding, policy)
    observer = ProducerBudgetObserver(
        settlement_store=case.service._llm_producer_settlement_store,
        producer_run_binding=case.binding,
        budget_state=budget_state,
        invocation_quota_profile=selected_profile,
        reentry_budget_scope=reentry_scope,
    )
    ProducerBudgetObserver.require_bound_state(observer, budget_state)
    assert observer.admit().remaining_usd > Decimal(0)
    capacity = observer.observe_standard_invocation_capacity()
    assert capacity.status == "available"
    assert capacity.profile_digest == selected_profile.profile_digest


def test_candidate_window_keeps_existing_selector_schema_and_default_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Native selector extension leaves the existing candidate path intact."""
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _prepare,
        _settle,
        _unit_window,
    )

    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "candidate-compatibility-history", Decimal("0.02"))
    window = _prepare(case)
    selector = case.bridge._load_action_selector(case.boundary.selection, case.boundary.phase_ref)[
        1
    ]
    assert selector is not None
    assert selector.schema_version == "AcquisitionWorldGrowthActionOutcomeSelector@1.2"
    assert selector.candidate_budget_window_state == "selected"
    assert selector.candidate_budget_window_id == window.window_id
    assert selector.native_budget_window_state is None
    assert selector.native_budget_window_id is None
    assert selector.native_budget_window_digest is None
