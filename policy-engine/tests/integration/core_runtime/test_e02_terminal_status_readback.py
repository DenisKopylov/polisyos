"""Bounded N6 status projection and persisted-history readback.

This covers the N6 producer and its typed history reader. The Depth-N Cycle
Board does not yet enumerate persisted recursive N6 runs, so this test does not
claim that the board or ordinary run-details API displays these nested statuses.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
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
    _AlwaysLowGrounding,
    _budget,
    _BudgetExhaustedValuePort,
    _CounterexampleAwareGenerator,
    _problem,
    _ReadyValuePort,
    _StableShadowGrounding,
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
    tmp_path: Path,
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
    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v4"
    assert run.source_custody_limitation is not None

    # Exercise the current versioned N6 history reader on a persisted JSON
    # representation, then inspect the parsed consumer result rather than the
    # source DTO. This file is a test fixture, not an artifact-store authority.
    persisted_path = tmp_path / "generation-cycle-run.json"
    persisted_path.write_text(json.dumps(run.model_dump(mode="json")), encoding="utf-8")
    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "policyos.runtime.generation_cycle_controller.v4"
    assert persisted["source_custody_limitation"] is not None
    history_issues = validate_generation_cycle_run_history(persisted)
    assert history_issues == (), history_issues
    replayed = GenerationCycleRun.from_persisted_payload(persisted)
    replayed_cycle = replayed.cycles[0]
    assert replayed_cycle.terminal_kind == expected_terminal
    assert replayed_cycle.refinement_decision.decision == expected_decision
    assert replayed_cycle.search_iteration.status == expected_iteration

    # Current-source history must reject a real producer record when one valid
    # sibling projection changes while the other terminal projections remain
    # untouched. Frozen historical v1/v2 fixtures are exercised separately.

    def flip_iteration_status(cycle: dict[str, Any]) -> None:
        cycle["search_iteration"]["status"] = (
            "abstained" if expected_iteration == "stopped" else "stopped"
        )

    def flip_refinement_decision(cycle: dict[str, Any]) -> None:
        cycle["refinement_decision"]["decision"] = (
            "abstain" if expected_decision == "stop" else "stop"
        )

    def diverge_terminal_from_voi(cycle: dict[str, Any]) -> None:
        cycle["terminal_kind"] = (
            "budget_exhausted" if expected_terminal != "budget_exhausted" else "frontier_stable"
        )

    mismatched_projections = (
        (
            "search-iteration status",
            "generation_cycle_terminal_projection_mismatch",
            flip_iteration_status,
        ),
        (
            "refinement decision",
            "generation_cycle_terminal_projection_mismatch",
            flip_refinement_decision,
        ),
        (
            "terminal kind versus VOI terminal",
            "voi_cycle_identity_mismatch",
            diverge_terminal_from_voi,
        ),
    )
    for projection_name, expected_issue, mutate_cycle in mismatched_projections:
        mismatched_projection = json.loads(persisted_path.read_text(encoding="utf-8"))
        mutate_cycle(mismatched_projection["cycles"][0])
        refusal = validate_generation_cycle_run_history(mismatched_projection)
        assert any(issue.get("code") == expected_issue for issue in refusal), (
            f"history replay did not report {expected_issue!r} after changing only "
            f"the {projection_name} projection: {refusal!r}"
        )


@pytest.mark.asyncio
async def test_repeated_candidate_hash_stop_block_projection_survives_history_readback(
    tmp_path: Path,
) -> None:
    """A repeated-hash block may supersede the final cycle's real stop."""

    class _RepeatedHashGenerator:
        def __init__(self) -> None:
            self._delegate = _CounterexampleAwareGenerator()
            self._first_content_hash: str | None = None

        async def __call__(self, problem: Any, *, cycle_index: int) -> Any:
            generated = await self._delegate(problem, cycle_index=cycle_index)
            if cycle_index == 0:
                self._first_content_hash = generated.candidates[0].atom.content_hash
                return generated
            assert self._first_content_hash is not None
            repeated_candidates = tuple(
                replace(
                    candidate,
                    atom=replace(
                        candidate.atom,
                        content_hash=self._first_content_hash,
                    ),
                )
                for candidate in generated.candidates
            )
            return replace(generated, candidates=repeated_candidates)

    class _RepairThenStableGrounding:
        def __init__(self) -> None:
            self._repair = _AlwaysLowGrounding()
            self._stable = _StableShadowGrounding()

        def __call__(self, **kwargs: Any) -> Any:
            grounding = self._repair if kwargs["cycle_index"] == 0 else self._stable
            return grounding(**kwargs)

    run = await GenerationCycleController(
        generation_port=_RepeatedHashGenerator(),
        grounding_port=_RepairThenStableGrounding(),
        value_port=PendingN8ValuePort(),
    ).run(
        _problem("e02_b29_repeated_candidate_stop_block"),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=2,
    )

    # This fixture repeats the candidate content hash only; it does not claim
    # that the full candidate payload bytes match. The source-limited record is
    # not evidence of N9 promotion or candidate authority.
    assert len(run.cycles) == 2
    assert run.schema_version == "policyos.runtime.generation_cycle_controller.v4"
    assert run.source_custody_limitation is not None
    assert run.promotion_port.status == "not_promoted"
    assert run.cycles[0].voi_decision.next_action == "advance"
    final_cycle = run.cycles[-1]
    assert (
        final_cycle.selected_candidate_content_hash == run.cycles[0].selected_candidate_content_hash
    )
    assert final_cycle.voi_decision.next_action == "stop"
    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "fake_cycle_same_candidate_repeated"
    assert final_cycle.refinement_decision.decision == "block_candidate"
    assert final_cycle.refinement_decision.reason == run.blocked_reason
    assert final_cycle.search_iteration.status == "blocked_no_retry"

    persisted_path = tmp_path / "repeated-candidate-blocked-run.json"
    persisted_path.write_text(json.dumps(run.model_dump(mode="json")), encoding="utf-8")
    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
    history_issues = validate_generation_cycle_run_history(persisted)
    history_issue_codes = {issue.get("code") for issue in history_issues}
    assert history_issue_codes == {"fake_cycle_same_candidate_repeated"}, history_issues
    assert "generation_cycle_terminal_projection_mismatch" not in history_issue_codes
    replayed = GenerationCycleRun.from_persisted_payload(persisted)
    assert replayed.terminal_status == "blocked"
    assert replayed.cycles[-1].voi_decision.next_action == "stop"
    assert replayed.cycles[-1].refinement_decision.decision == "block_candidate"
    assert replayed.cycles[-1].search_iteration.status == "blocked_no_retry"

    mismatched_block_projections = (
        (
            "blocked terminal projection",
            "generation_cycle_blocked_terminal_projection_mismatch",
            lambda cycle: cycle["refinement_decision"].__setitem__("decision", "stop"),
        ),
        (
            "blocked reason projection",
            "generation_cycle_blocked_reason_projection_mismatch",
            lambda cycle: cycle["refinement_decision"].__setitem__("reason", "forged_block_reason"),
        ),
    )
    for projection_name, expected_issue, mutate_cycle in mismatched_block_projections:
        corrupted = json.loads(persisted_path.read_text(encoding="utf-8"))
        mutate_cycle(corrupted["cycles"][-1])
        refusal = validate_generation_cycle_run_history(corrupted)
        assert any(issue.get("code") == expected_issue for issue in refusal), (
            f"history replay did not report {expected_issue!r} for the corrupted "
            f"{projection_name}: {refusal!r}"
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
