from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    SimulationPortObservation,
    ValuePortObservation,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState


@dataclass(frozen=True)
class _Atom:
    content_hash: str
    target_world_slots: tuple[str, ...] = ("firm_survival",)


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]


def _candidate(candidate_id: str, fill: str) -> _Candidate:
    return _Candidate(
        candidate_id=candidate_id,
        atom=_Atom(content_hash=f"sha256:{fill * 64}"),
    )


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


class _TwoCandidateGenerator:
    async def __call__(self, problem: object, *, cycle_index: int) -> _GenerationResult:
        del problem, cycle_index
        return _GenerationResult(
            status="generated",
            candidates=(
                _candidate("blocked-first", "1"),
                _candidate("usable-second", "2"),
            ),
            surrogate_rankings=(
                _Ranking("blocked-first", score=0.95, voi_estimate=0.1),
                _Ranking("usable-second", score=0.2, voi_estimate=0.9),
            ),
        )


class _GroundingWithFirstBlocker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        candidate: _Candidate,
        problem: object,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        self.calls.append(candidate.candidate_id)
        if candidate.candidate_id == "blocked-first":
            return CandidateGroundingObservation(
                candidate_id=candidate.candidate_id,
                status="grounding_unavailable",
                grounding_score=0.0,
                issue_codes=("missing_owner_input",),
                report_ref="grounding://blocked-first",
            )
        return CandidateGroundingObservation(
            candidate_id=candidate.candidate_id,
            status="grounded_shadow",
            grounding_score=0.8,
            evidence_refs=("evidence://usable-second",),
            report_ref="grounding://usable-second",
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


class _RecordingSimulation:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        candidate: _Candidate,
        problem: object,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        self.calls.append(candidate.candidate_id)
        return SimulationPortObservation(
            candidate_id=candidate.candidate_id,
            status="joint_simulated",
            simulation_ref="sha256:" + "3" * 64,
        )


def _grounded_two_candidate_state(
    *,
    simulation_port: object | None = None,
    budget_state: BudgetState | None = None,
) -> tuple[GenerationCycleController, dict[str, Any], _GroundingWithFirstBlocker]:
    grounding_port = _GroundingWithFirstBlocker()
    controller = GenerationCycleController(
        generation_port=_TwoCandidateGenerator(),
        grounding_port=grounding_port,
        simulation_port=simulation_port or _RecordingSimulation(),
        value_port=lambda **_: ValuePortObservation(),
        authority_scope="contract_testing",
    )
    return controller, {
        "problem": object(),
        "cycle_index": 0,
        "budget_state": budget_state or _budget(),
        "previous_cycle": None,
        "value_port_override": None,
        "stable_design_problem_ref": None,
    }, grounding_port


@pytest.mark.asyncio
async def test_generation_cycle_executes_next_grounded_candidate_after_first_blocker() -> None:
    controller, state, _ = _grounded_two_candidate_state()
    generated = await controller._generate_node(state)
    grounded = controller._ground_node(generated)
    finished = controller._joint_value_node(grounded)

    assert grounded["selected_candidate"].candidate_id == "usable-second"
    assert finished["simulation"].candidate_id == "usable-second"
    assert finished["simulation"].status == "joint_simulated"


def test_blocked_candidate_remains_in_history_with_typed_reason() -> None:
    controller, state, grounding_port = _grounded_two_candidate_state()

    # The test drives the synchronous grounding node with the exact generated
    # denominator used by the async generation node.
    candidates = state["candidates"] = (
        _candidate("blocked-first", "1"),
        _candidate("usable-second", "2"),
    )
    grounded = controller._ground_node(
        {
            **state,
            "generation_result": _GenerationResult(
                status="generated",
                candidates=candidates,
                surrogate_rankings=(
                    _Ranking("blocked-first", score=0.95, voi_estimate=0.1),
                    _Ranking("usable-second", score=0.2, voi_estimate=0.9),
                ),
            ),
            "generation_channel": "n4_owner",
            "candidates": candidates,
            "rankings": {
                "blocked-first": (0.95, 0.1),
                "usable-second": (0.2, 0.9),
            },
            "selected_candidate": candidates[0],
        }
    )

    assert grounding_port.calls == ["blocked-first", "usable-second"]
    assert grounded["grounding_by_candidate"]["blocked-first"].status == (
        "grounding_unavailable"
    )
    assert grounded["grounding_by_candidate"]["blocked-first"].issue_codes == (
        "missing_owner_input",
    )
    assert tuple(summary.candidate_id for summary in grounded["candidate_summaries"]) == (
        "blocked-first",
        "usable-second",
    )
    assert grounded["selected_candidate"].candidate_id == "usable-second"


def test_informative_candidate_is_not_rejected_by_unknown_monetary_proxy_inside_budget() -> None:
    controller, _, _ = _grounded_two_candidate_state()

    decision = controller.decide_next_action(
        candidate_id="informative-candidate",
        proxy_score=0.0,
        voi_estimate=0.8,
        prior_terminal_kind="search_ceiling_repair_required",
        budget_state=_budget(),
    )

    assert decision.scheduler_action == "advance"
    assert decision.next_action == "advance"
    assert decision.scheduler_reason == "advance_by_information_value"


def test_actual_budget_exhaustion_stops_alternative_execution() -> None:
    class _MustNotRun:
        def __call__(self, **kwargs: Any) -> SimulationPortObservation:
            del kwargs
            raise AssertionError("budget-exhausted alternative was executed")

    controller, state, _ = _grounded_two_candidate_state(
        simulation_port=_MustNotRun(),
        budget_state=_budget("0.0"),
    )
    candidate = _candidate("usable-second", "2")
    state.update(
        {
            "selected_candidate": candidate,
            "rankings": {candidate.candidate_id: (0.0, 0.8)},
        }
    )

    finished = controller._joint_value_node(state)

    assert finished["simulation"].status == "simulation_blocked"
    assert "budget_exhausted_for_next_level" in finished["simulation"].authority_blockers
    assert finished["value_port"].status == "value_blocked"
    assert finished["value_port"].authority_blockers == (
        "budget_exhausted_for_next_level",
    )
