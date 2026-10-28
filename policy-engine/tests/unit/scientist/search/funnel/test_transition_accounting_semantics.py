"""Organizational reuse must retain one physical result and a fresh request identity."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

import pytest

from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.objective import GDPGrowthObjective, ObjectiveScoreStatus
from polisyos.scientist.methods.search.sentinels import SENTINEL_METADATA_KEY
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _serialize_funnel_outcome,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState


class _CountingScoreStage(FunnelStage):
    """Execute the real score contract over a declared compact fixture source."""

    def __init__(self, level: int = 0) -> None:
        self.calls = 0
        self.level = level

    @property
    def fidelity_level(self) -> int:
        return self.level

    @property
    def stage_name(self) -> str:
        return f"score-fixture-{self.level}"

    @property
    def estimated_cost_usd(self) -> float:
        return 0.2

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        del context
        self.calls += 1
        source = {
            "gdp_change": 0.0,
            "metric_units": {"gdp_change": "fixture-unit"},
        }
        assessment = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source)
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=assessment.raw_value,
            is_promising=True,
            score_status=assessment.score_status,
            score_assessment=assessment.score_assessment,
            simulation_results=source,
            feedback={"verdict": "APPROVE"},
            stage_name=self.stage_name,
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
            cheap_signal=(CheapSignalVector(expected_value_proxy=0.5) if self.level == 2 else None),
            fidelity_level=self.level,
            compute_cost_usd=0.2,
            compute_cost_origin="estimated",
        )


def test_terminal_reuse_has_a_fresh_complete_lineage_without_new_physical_work() -> None:
    stage = _CountingScoreStage()
    runtime = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "same-scientific-subject"}
    context = {"dataset_version": "dataset-v1", "evaluation_scope": "bounded"}

    first = runtime.submit(candidate, context)
    first_outcome = runtime.advance(first)
    source_results = deepcopy(first.stage_results)
    source_trace = deepcopy(first.trace)
    second = runtime.submit(candidate, context)
    second_outcome = runtime.advance(second)
    third = runtime.submit(candidate, context)
    third_outcome = runtime.advance(third)

    assert first_outcome.final_action == second_outcome.final_action == "complete"
    assert third_outcome.final_action == "complete"
    assert len({first.ticket_id, second.ticket_id, third.ticket_id}) == 3
    assert first.lineage == (first.ticket_id,)
    assert second.parent_ticket_id == first.ticket_id
    assert third.parent_ticket_id == second.ticket_id
    assert second.lineage == (first.ticket_id, second.ticket_id)
    assert third.lineage == (first.ticket_id, second.ticket_id, third.ticket_id)
    assert second.result_reuse_source_ticket_id == first.ticket_id
    assert third.result_reuse_source_ticket_id == first.ticket_id
    assert first.stage_results == source_results
    assert first.trace == source_trace
    assert second.stage_results[0] is not first.stage_results[0]
    assert third.stage_results[0] is not second.stage_results[0]
    assert stage.calls == 1
    # The retained trace describes the source execution. No new charge or
    # measured-zero cost is inferred for either new organizational request.
    assert first_outcome.compute_cost_usd == 0.2
    assert second_outcome.compute_cost_usd is None
    assert second_outcome.compute_cost_origin == "unknown"
    assert third_outcome.compute_cost_usd is None
    assert third_outcome.trace[0].compute_cost_usd == 0.2
    assert third_outcome.final_result is not None
    assert third_outcome.final_result.feedback["funnel_result_reuse"] == {
        "request_ticket_id": third.ticket_id,
        "result_source_ticket_id": first.ticket_id,
        "new_physical_work": False,
        "executed_work_status": "unavailable",
    }
    payload = _serialize_funnel_outcome(third_outcome)
    assert payload["ticket_id"] == third.ticket_id
    assert payload["parent_ticket_id"] == second.ticket_id
    assert payload["lineage"] == list(third.lineage)
    assert payload["result_reuse_source_ticket_id"] == first.ticket_id
    assert payload["compute_cost_usd"] is None


@pytest.mark.parametrize(
    "public_path", ["get_outcome", "advance", "evaluate", "stage_a", "stage_b"]
)
def test_fresh_reuse_score_reconciliation_preserves_the_execution_trace(public_path: str) -> None:
    stage = _CountingScoreStage()
    runtime = FunnelOrchestrator([stage])
    candidate: dict[str, Any] = {"candidate_id": "history"}
    first = runtime.submit(candidate, {})
    runtime.advance(first)
    second = runtime.submit(candidate, {})
    historical_trace = deepcopy(second.trace)
    second.stage_results[0].simulation_results["gdp_change"] = 0.3

    if public_path in {"get_outcome", "advance"}:
        refused = getattr(runtime, public_path)(second)
        assert refused.final_action == "reject"
        assert refused.final_result is not None
        assert refused.final_result.score_status is ObjectiveScoreStatus.INVALID
        assert refused.trace == historical_trace
    elif public_path == "evaluate":
        result = runtime.evaluate(candidate, {})
        assert result.score_status is ObjectiveScoreStatus.INVALID
        assert result.feedback["funnel_action"] == "reject"
        assert result.feedback["verdict"] == "REJECT"
    elif public_path == "stage_a":
        bundle = runtime.as_stage_a_callable()(candidate, {})
        assert bundle.score_status is ObjectiveScoreStatus.INVALID
        assert bundle.stage_a_passed is False
        assert bundle.metadata["funnel_action"] == "reject"
    else:
        payload = runtime.as_stage_b_callable()(candidate, {})
        assert payload["_funnel_result"].score_status is ObjectiveScoreStatus.INVALID
        assert payload["feedback"]["verdict"] == "REJECT"
        assert payload["_funnel_outcome"].trace == historical_trace

    assert all(ticket.trace == historical_trace for ticket in runtime._tickets.values())
    assert first.stage_results[0].simulation_results["gdp_change"] == 0.0
    assert stage.calls == 1


def test_live_split_request_retains_its_ticket_and_executes_only_the_remaining_stage() -> None:
    early = _CountingScoreStage(0)
    later = _CountingScoreStage(1)
    runtime = FunnelOrchestrator([early, later], stage_a_max_level=0)
    candidate = {"candidate_id": "split-subject"}
    context = {"dataset_version": "dataset-v1"}

    ticket = runtime.submit(candidate, context)
    partial = runtime.advance(ticket, policy="stage_a")
    same_live_ticket = runtime.submit(candidate, context)
    completed = runtime.advance(same_live_ticket)

    assert partial.evaluation_status == "partial"
    assert same_live_ticket is ticket
    assert completed.ticket_id == ticket.ticket_id
    assert completed.result_reuse_source_ticket_id is None
    assert completed.lineage == (ticket.ticket_id,)
    assert early.calls == later.calls == 1


def test_unexecuted_empty_and_capped_results_stay_unavailable_in_the_native_projection() -> None:
    empty_runtime = FunnelOrchestrator([])
    empty = empty_runtime.advance(empty_runtime.submit({}, {}))
    stage = _CountingScoreStage(4)
    capped_runtime = FunnelOrchestrator([stage], max_level=2)
    capped = capped_runtime.advance(capped_runtime.submit({}, {}))

    for runtime, outcome in ((empty_runtime, empty), (capped_runtime, capped)):
        result = runtime._compatibility_result(outcome, runtime._empty_result({}))
        assert result.objective_value is None
        assert result.is_promising is False
        assert result.feedback["verdict"] == "NOT_EVALUATED"
        assert outcome.compute_cost_usd is None
        payload = _serialize_funnel_outcome(outcome)
        assert payload["stage_results"] == {}
        assert payload["final_action"] == "defer"
        assert payload["compute_cost_usd"] is None
    assert stage.calls == 0


def test_partial_native_projection_keeps_the_stage_verdict_below_the_final_decision() -> None:
    early, later = _CountingScoreStage(0), _CountingScoreStage(1)
    runtime = FunnelOrchestrator([early, later], stage_a_max_level=0)
    partial = runtime.advance(runtime.submit({}, {}), policy="stage_a")
    assert partial.final_result is not None
    projected = runtime._compatibility_result(partial, partial.final_result)

    assert projected.objective_value == 0.0
    assert projected.feedback["stage_verdict"] == "APPROVE"
    assert projected.feedback["verdict"] == "DEFER"
    assert projected.feedback["funnel_evaluation_status"] == "partial"
    assert projected.is_promising is False
    assert early.calls == 1
    assert later.calls == 0


@pytest.mark.parametrize(
    "changed_key", ["dataset_version", "model_version", "access_scope", "replicate_id"]
)
def test_completed_result_reuse_keeps_effective_context_boundaries(changed_key: str) -> None:
    stage = _CountingScoreStage()
    runtime = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "effective-context"}
    context = {
        "dataset_version": "data-v1",
        "model_version": "model-v1",
        "access_scope": "access-v1",
        "replicate_id": "replica-v1",
    }
    first = runtime.submit(candidate, context)
    runtime.advance(first)
    changed = runtime.submit(candidate, {**context, changed_key: "new-selection"})
    runtime.advance(changed)

    assert changed.ticket_id != first.ticket_id
    assert changed.result_reuse_source_ticket_id is None
    assert first.context == context
    assert stage.calls == 2


def test_sentinel_request_executes_without_relabeling_ordinary_history() -> None:
    stage = _CountingScoreStage()
    runtime = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "same-subject"}
    ordinary = runtime.submit(candidate, {"dataset_version": "data-v1"})
    runtime.advance(ordinary)
    ordinary_results = deepcopy(ordinary.stage_results)
    sentinel = runtime.submit(
        {**candidate, SENTINEL_METADATA_KEY: {"sentinel_id": "independent-control"}},
        {"dataset_version": "data-v1"},
    )
    runtime.advance(sentinel)

    assert sentinel.ticket_id != ordinary.ticket_id
    assert sentinel.result_reuse_source_ticket_id is None
    assert sentinel.context["is_sentinel"] is True
    assert "is_sentinel" not in ordinary.context
    assert ordinary.stage_results == ordinary_results
    assert stage.calls == 2


def test_split_api_checks_the_existing_budget_edge_before_the_next_stage() -> None:
    def route(split: bool):
        early, later = _CountingScoreStage(2), _CountingScoreStage(3)
        budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))})
        runtime = FunnelOrchestrator([early, later], budget_state=budget)
        ticket = runtime.submit({"candidate": "budget-edge"}, {})
        if split:
            runtime.advance(ticket, policy="stage_a")
        outcome = runtime.advance(ticket)
        return early, later, outcome, budget

    full_early, full_later, full, full_budget = route(False)
    split_early, split_later, split, split_budget = route(True)

    assert full.final_action == split.final_action
    assert full.final_action in {"defer", "retry_cheaper", "reject"}
    assert full_early.calls == split_early.calls == 1
    assert full_later.calls == split_later.calls == 0
    assert [step.fidelity_level for step in full.trace] == [2]
    assert [step.fidelity_level for step in split.trace] == [2]
    assert full.last_scheduling_decision is not None
    assert split.last_scheduling_decision is not None
    assert (
        full.last_scheduling_decision.next_level == split.last_scheduling_decision.next_level == 3
    )
    # This is the existing scheduling snapshot, not a durable fiscal receipt.
    assert full_budget.spent == split_budget.spent == {}


def test_unchanged_budget_does_not_resume_but_changed_basis_has_a_linked_successor() -> None:
    early, later = _CountingScoreStage(2), _CountingScoreStage(3)
    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))})
    runtime = FunnelOrchestrator([early, later], budget_state=budget)
    candidate, context = {"candidate": "budget-continuation"}, {"dataset_version": "v1"}
    first = runtime.submit(candidate, context)
    before = runtime.advance(first)
    original_trace = deepcopy(first.trace)
    original_results = deepcopy(first.stage_results)
    repeated = runtime.submit(candidate, context)
    unchanged = runtime.advance(repeated)

    assert repeated is first
    assert unchanged.final_action == before.final_action
    assert first.trace == original_trace
    assert early.calls == 1
    assert later.calls == 0
    budget.limits["run"] = BudgetLimit(key="run", max_usd=Decimal("1"))
    successor = runtime.submit(candidate, context)
    resumed = runtime.advance(successor)

    assert successor.ticket_id != first.ticket_id
    assert successor.parent_ticket_id == first.ticket_id
    assert successor.lineage == (first.ticket_id, successor.ticket_id)
    assert successor.result_reuse_source_ticket_id is None
    assert first.stage_results == original_results
    assert first.trace == original_trace
    assert early.calls == later.calls == 1
    assert resumed.final_action == "complete"
    assert [step.fidelity_level for step in resumed.trace] == [2, 3]
