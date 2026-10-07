"""Bounded N6 status projection and persisted-history readback.

This covers the N6 producer and its typed history reader. The Depth-N Cycle
Board does not yet enumerate persisted recursive N6 runs, so this test does not
claim that the board or ordinary run-details API displays these nested statuses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from polisyos.pdc import RefinementDecision, SearchIteration, SearchTerminalKind
from polisyos.runtime.quality import generation_cycle as generation
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleRun,
    PendingN8ValuePort,
    validate_generation_cycle_run_history,
)
from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
from tests.unit.runtime.quality.test_generation_cycle import (
    _BudgetExhaustedValuePort,
    _CounterexampleAwareGenerator,
    _ReadyValuePort,
    _StableShadowGrounding,
    _budget,
    _problem,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value_port", "expected_terminal", "expected_decision", "expected_iteration"),
    [
        (_ReadyValuePort, "frontier_stable", "stop", "stopped"),
        (_BudgetExhaustedValuePort, "budget_exhausted", "stop", "stopped"),
        (PendingN8ValuePort, "grounded_abstention", "abstain", "abstained"),
    ],
    ids=("frontier-stable", "budget-exhausted", "actual-abstention"),
)
async def test_n6_terminal_decision_and_iteration_survive_history_readback(
    value_port: type[Any],
    expected_terminal: str,
    expected_decision: str,
    expected_iteration: str,
) -> None:
    """A real bounded N6 run retains each terminal's distinct typed projection."""

    problem = _problem(f"e02_b29_{expected_terminal}")
    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_StableShadowGrounding(),
        value_port=value_port(),
    ).run(problem, budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert cycle.terminal_kind == expected_terminal
    assert cycle.voi_decision.next_action == "stop"
    assert cycle.refinement_decision.decision == expected_decision
    assert cycle.search_iteration.status == expected_iteration
    assert run.schema_version == generation.GENERATION_CYCLE_SCHEMA_VERSION

    # Exercise the current versioned N6 history reader on the producer's JSON
    # wire, then inspect the parsed consumer result rather than the source DTO.
    persisted = json.loads(json.dumps(run.model_dump(mode="json")))
    history_issues = validate_generation_cycle_run_history(persisted)
    assert history_issues == (), history_issues
    replayed = GenerationCycleRun.from_persisted_payload(persisted)
    replayed_cycle = replayed.cycles[0]
    assert replayed_cycle.terminal_kind == expected_terminal
    assert replayed_cycle.refinement_decision.decision == expected_decision
    assert replayed_cycle.search_iteration.status == expected_iteration

    # Current-source history must reject a real producer record whose terminal
    # and refinement are unchanged but whose sibling search projection is flipped.
    # Historical v1/v2/v3 fixtures remain governed by their frozen replay tests.
    mismatched_projection = json.loads(json.dumps(persisted))
    mismatched_projection["cycles"][0]["search_iteration"]["status"] = (
        "abstained" if expected_iteration == "stopped" else "stopped"
    )
    refusal = validate_generation_cycle_run_history(mismatched_projection)
    assert refusal, (
        "history replay accepted a producer-owned terminal whose SearchIteration status "
        f"was changed from {expected_iteration!r}"
    )


@pytest.mark.asyncio
async def test_workspace_partial_admissible_projects_as_stop_not_abstention() -> None:
    """A WorkspaceLoop-owned partial terminal remains a stop in N6's projection."""

    workspace_exit = WorkspaceLoop().run_fixture("ua_msme_credit_worldbank_measurement")
    terminal_kind = workspace_exit.terminal_state.kind
    assert terminal_kind is SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE

    problem = _problem("e02_b29_workspace_partial_admissible")
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_StableShadowGrounding(),
        value_port=_ReadyValuePort(),
    )
    n6_run = await controller.run(problem, budget_state=_budget(), max_cycles=1)
    cycle = n6_run.cycles[0]

    # The terminal is supplied by the real WorkspaceLoop owner. N6 selects the
    # next action and runs its production projection functions; this is not a
    # claim that N6's current terminal selector emits grounded_partial_admissible.
    next_action = controller.decide_next_action(
        candidate_id=cycle.selected_candidate_ref,
        proxy_score=0.93,
        voi_estimate=0.82,
        prior_terminal_kind=terminal_kind.value,
        budget_state=_budget(),
    )
    assert next_action.next_action == "stop"
    assert next_action.terminal_kind == terminal_kind.value

    decision = generation._refinement_decision(
        problem=problem,
        cycle_index=cycle.cycle_index,
        candidate_id=cycle.selected_candidate_ref,
        counterexample=cycle.counterexample,
        revision=cycle.revision_request,
        next_action=next_action,
    )
    iteration = generation._search_iteration(
        problem=problem,
        cycle_index=cycle.cycle_index,
        candidate_id=cycle.selected_candidate_ref,
        counterexample=cycle.counterexample,
        decision=decision,
        next_action=next_action,
    )

    assert decision.decision == "stop"
    assert iteration.status == "stopped"
    assert RefinementDecision.model_validate(decision.model_dump(mode="json")) == decision
    assert SearchIteration.model_validate(iteration.model_dump(mode="json")) == iteration
