from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    CandidateSummary,
    GenerationCycleController,
    PromotionPortObservation,
    SimulationPortObservation,
    ValuePortObservation,
    _n7_reentered_summaries,
)
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
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


def _public_problem() -> DesignProblem:
    return DesignProblem(
        design_problem_id="cyc_04_public_run",
        problem_statement="Improve firm survival with grounded support under fiscal constraints.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Improve firm survival with grounded support.",
            source_surface="test_cyc_04",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only research mandate",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "tax_relief"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which data grounds this effect?",
                    required_for="A-side grounding",
                )
            ]
        ),
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


class _NoPromotion:
    def __call__(
        self,
        *,
        summaries: object,
        problem: object,
    ) -> PromotionPortObservation:
        del summaries, problem
        return PromotionPortObservation(status="not_promoted", reason="test_only")


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


@pytest.mark.asyncio
async def test_public_run_retains_blocked_first_reason_after_executing_second() -> None:
    simulation = _RecordingSimulation()
    controller = GenerationCycleController(
        generation_port=_TwoCandidateGenerator(),
        grounding_port=_GroundingWithFirstBlocker(),
        simulation_port=simulation,
        value_port=lambda **_: ValuePortObservation(),
        promotion_port=_NoPromotion(),
        authority_scope="contract_testing",
        repo_root=Path(__file__).resolve().parents[3],
    )

    run = await controller.run(
        _public_problem(),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    assert simulation.calls == ["usable-second"]
    assert run.cycles[0].selected_candidate_ref == "usable-second"
    assert run.cycles[0].candidate_ids == ("blocked-first", "usable-second")
    blocked = next(
        summary for summary in run.candidate_summaries if summary.candidate_id == "blocked-first"
    )
    assert blocked.grounding_status == "grounding_unavailable"
    assert blocked.grounding_issue_codes == ("missing_owner_input",)
    assert blocked.grounding_report_ref == "grounding://blocked-first"


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


def test_n7_reentry_replaces_grounding_reason_and_report_ref() -> None:
    old_summary = CandidateSummary(
        candidate_id="reentered-candidate",
        content_hash="sha256:" + "4" * 64,
        cycle_index=0,
        proxy_score=0.2,
        voi_estimate=0.4,
        grounding_status="grounding_unavailable",
        grounding_source="grounding_unavailable",
        grounding_issue_codes=("old_missing_owner_input",),
        grounding_report_ref="grounding://old",
        grounding_score=0.0,
        current_valid=False,
        front="research",
        high_proxy=False,
        low_grounding=True,
    )
    rederived = CandidateGroundingObservation(
        candidate_id="reentered-candidate",
        status="current_valid",
        grounding_score=0.95,
        issue_codes=("owner_input_revalidated",),
        evidence_refs=("evidence://revalidated",),
        current_valid=True,
        report_ref="grounding://new",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
    )

    updated = _n7_reentered_summaries(
        (old_summary,),
        candidate_id="reentered-candidate",
        grounding=rederived,
        low_grounding_threshold=0.5,
    )[0]

    assert updated.grounding_issue_codes == ("owner_input_revalidated",)
    assert updated.grounding_report_ref == "grounding://new"
    assert updated.grounding_issue_codes != old_summary.grounding_issue_codes
    assert updated.grounding_report_ref != old_summary.grounding_report_ref


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
