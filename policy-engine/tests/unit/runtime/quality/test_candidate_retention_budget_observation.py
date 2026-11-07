"""Candidate retention observes the real ledger, not just a USD projection.

The bridge's unrelated lease/action preflight is adapted as in the existing
budget-window unit fixture. This does not establish a protected action or N5.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateAcquisitionEvaluationCurrentOwner,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
    _prepare,
    _settle,
    _unit_window,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )


def test_candidate_budget_snapshot_detects_zero_cost_event_and_runtime_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "first-physical-event", Decimal("0.20"))
    window = _prepare(case)

    def real_observer(*, closure: object, budget_state: object, reentry_budget_scope: object):
        assert closure is case.closure
        observer = ProducerBudgetObserver(
            settlement_store=case.service._llm_producer_settlement_store,
            producer_run_binding=case.binding,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )
        return observer

    monkeypatch.setattr(
        case.service, "build_acquisition_source_budget_observer", real_observer, raising=False
    )

    def physical_reentry_not_needed(**_kwargs: object) -> None:
        pytest.fail("retained local budget observation invoked physical reentry admission")

    monkeypatch.setattr(
        case.bridge, "candidate_source_reentry_preflight", physical_reentry_not_needed
    )
    owner = CandidateAcquisitionEvaluationCurrentOwner(
        bridge=case.bridge,
        closure=case.closure,
        candidate_action_ref=cast("ArtifactRef", None),
        candidate_world_intent_ref=cast("ArtifactRef", None),
        current_basis_ref=cast("ArtifactRef", None),
        decision_ref=cast("ArtifactRef", None),
        prior=cast("ResolvedAcquisitionEvaluation", None),
        prepared_n5_configuration=cast("PreparedJointSimulationConfiguration", None),
    )
    state, before = owner._budget_snapshot(window)
    same_state, unchanged = owner._budget_snapshot(window, budget_state=state)
    assert same_state is state
    assert unchanged == before
    initial_state = exact_n5_content_bytes(state)

    # A new settled zero-cost event leaves the amount unchanged but changes
    # both the canonical event set and the owner ledger revision.
    _settle(case, "new-zero-cost-event", Decimal("0"))
    same_state, changed = owner._budget_snapshot(window, budget_state=state)
    assert same_state is state
    assert exact_n5_content_bytes(state) == initial_state
    assert changed.producer_spent_usd == before.producer_spent_usd
    assert changed.ledger_revision > before.ledger_revision
    assert changed.source_basis_digest != before.source_basis_digest
    assert changed.producer_events != before.producer_events
    assert changed != before

    # An allocation on the exact scheduler state is observed separately; it
    # does not assert anything about allocation held by another runtime state.
    state.spent["run"] += Decimal("0.01")
    _, allocated = owner._budget_snapshot(window, budget_state=state)
    assert allocated.runtime_allocation_usd == Decimal("0.01")
    assert allocated.remaining_usd < changed.remaining_usd
    assert "n5_usd_price_not_established" in allocated.limitations
    assert "remaining_allocation_is_not_a_per_call_cost_reservation" in allocated.limitations
