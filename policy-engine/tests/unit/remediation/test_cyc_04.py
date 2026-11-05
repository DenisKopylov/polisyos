from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

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
from polisyos.runtime.quality.generation_cycle import (
    CandidateEvaluationAttempt,
    CandidateGroundingObservation,
    CandidateSummary,
    GenerationCycleController,
    GenerationCycleError,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
    ValuePortObservation,
    _candidate_evaluation_attempt_ref,
    _n7_reentered_summaries,
    load_joint_simulation_result,
    validate_generation_cycle_run_history,
)
from polisyos.runtime.quality.intervention_substrate import InterventionSubstrateError
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.runtime.quality.test_generation_cycle import (
    REPO_ROOT,
    _owner_program_graph_n5_witness,
)


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
    return (
        controller,
        {
            "problem": _public_problem(),
            "cycle_index": 0,
            "budget_state": budget_state or _budget(),
            "previous_cycle": None,
            "value_port_override": None,
            "stable_design_problem_ref": None,
        },
        grounding_port,
    )


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
async def test_untyped_design_problem_is_refused_before_generation() -> None:
    controller, state, _ = _grounded_two_candidate_state()

    with pytest.raises(
        GenerationCycleError,
        match="generation_cycle_design_problem_untyped",
    ):
        await controller._generate_node({**state, "problem": object()})


@pytest.mark.asyncio
async def test_candidate_local_refusal_retries_existing_grounded_candidate_with_owner_n5(
    tmp_path: Path,
) -> None:
    """Controlled local refusal queues one real owner N5 candidate without regenerating."""
    from polisyos.core.security.tenant_context import tenant_scope

    witness = _owner_program_graph_n5_witness(
        tmp_path,
        income_values=(1000.0, 2000.0),
    )
    first = _candidate("controlled-local-refusal", "3")
    second_id = str(witness.candidate.candidate_id)
    first_id = first.candidate_id

    async def run_case_async(
        mode: str,
    ) -> tuple[Any, tuple[str, ...], tuple[str, ...], int]:
        simulation_calls: list[str] = []
        owner_n5_calls: list[str] = []
        generation_calls: list[int] = []

        class _WitnessTwoCandidateGenerator:
            async def __call__(
                self,
                problem: object,
                *,
                cycle_index: int,
            ) -> _GenerationResult:
                del problem, cycle_index
                generation_calls.append(1)
                return _GenerationResult(
                    status="generated",
                    candidates=(first, witness.candidate),  # type: ignore[arg-type]
                    surrogate_rankings=(
                        _Ranking(first_id, score=0.95, voi_estimate=0.95),
                        _Ranking(second_id, score=0.75, voi_estimate=0.75),
                    ),
                )

        class _GroundBothCandidates:
            def __call__(
                self,
                *,
                candidate: object,
                problem: object,
                cycle_index: int,
                generation_result: object,
            ) -> CandidateGroundingObservation:
                del problem, cycle_index, generation_result
                candidate_id = str(candidate.candidate_id)
                return CandidateGroundingObservation(
                    candidate_id=candidate_id,
                    status="grounded_shadow",
                    grounding_score=0.9,
                    evidence_refs=(f"evidence://controlled/{candidate_id}",),
                    report_ref=f"grounding://controlled/{candidate_id}",
                    grounding_source="cgf_firewall",
                    grounding_disposition="shadow_bound",
                )

        class _LocalRefusalThenOwnerSimulation:
            def __call__(
                self,
                *,
                candidate: object,
                problem: object,
                cycle_index: int,
            ) -> SimulationPortObservation:
                del problem, cycle_index
                candidate_id = str(candidate.candidate_id)
                simulation_calls.append(candidate_id)
                if candidate_id != first_id:
                    if mode == "all_local_refusals":
                        return GenerationCycleController._candidate_scenario_refusal(
                            candidate_id=second_id,
                            code="candidate_scenario_value_outside_profile_domain",
                            status="simulation_blocked",
                            candidate_local_exception=InterventionSubstrateError(
                                "candidate_scenario_value_outside_profile_domain"
                            ),
                        )
                    owner_n5_calls.append(candidate_id)
                    return witness.port(
                        candidate=candidate,
                        problem=witness.problem,
                        cycle_index=0,
                    )
                refusal = GenerationCycleController._candidate_scenario_refusal(
                    candidate_id=first_id,
                    code=(
                        "shared_context_currentness_unknown"
                        if mode == "shared"
                        else "candidate_scenario_value_outside_profile_domain"
                    ),
                    status="simulation_blocked",
                    candidate_local_exception=(
                        None
                        if mode == "shared"
                        else InterventionSubstrateError(
                            "candidate_scenario_value_outside_profile_domain"
                        )
                    ),
                )
                if mode == "stripped_marker":
                    refusal._candidate_local_failure_issuer = None
                return refusal

        controller = GenerationCycleController(
            generation_port=_WitnessTwoCandidateGenerator(),
            grounding_port=_GroundBothCandidates(),
            simulation_port=_LocalRefusalThenOwnerSimulation(),
            value_port=PendingN8ValuePort(),
            promotion_port=_NoPromotion(),
            authority_scope="contract_testing",
            repo_root=REPO_ROOT,
            cycle_substrate_context=witness.context,
            artifact_store=witness.store,
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            run = await controller.run(
                witness.problem,
                budget_state=_budget("0.0" if mode == "shared_budget" else "5.0"),
                min_cycles=1,
                max_cycles=1,
            )
        return run, tuple(simulation_calls), tuple(owner_n5_calls), len(generation_calls)

    try:
        local_result, local_calls, local_owner_n5_calls, local_generation_count = (
            await run_case_async("local")
        )

        assert local_generation_count == 1
        assert local_calls == (first_id, second_id)
        assert local_owner_n5_calls == (second_id,)
        assert local_result.cycles[0].selected_candidate_ref == second_id
        assert local_result.cycles[0].simulation.candidate_id == second_id
        assert local_result.cycles[0].simulation.status == "joint_simulated"
        assert local_result.cycles[0].simulation.simulation_result_ref is not None
        failed_first = next(
            summary
            for summary in local_result.candidate_summaries
            if summary.candidate_id == first_id
        )
        assert failed_first.evaluation_attempt is not None
        assert failed_first.evaluation_attempt.failure_stage == "n5"
        assert failed_first.evaluation_attempt.simulation.status == "simulation_blocked"
        assert failed_first.evaluation_attempt.simulation.authority_blockers == (
            "candidate_scenario_value_outside_profile_domain",
        )
        assert failed_first.value_status == "value_pending_n8"
        assert failed_first.value_blockers == (
            "candidate_scenario_value_outside_profile_domain",
            "value_gate_pending_n8",
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            persisted = load_joint_simulation_result(
                local_result.cycles[0].simulation.simulation_result_ref,
                store=witness.store,
                expected_world_model_record_content_hash=(
                    witness.world_model_build.record.content_hash
                ),
            )
        assert persisted.world_model_record_content_hash == (
            witness.world_model_build.record.content_hash
        )

        valid_wire = local_result.model_dump(mode="json")
        assert validate_generation_cycle_run_history(valid_wire) == ()
        served_run = type(local_result).model_validate(valid_wire)
        expected_candidate_occurrences = (first_id, second_id)
        assert served_run.cycles[0].candidate_ids == expected_candidate_occurrences
        assert tuple(
            summary.candidate_id for summary in served_run.candidate_summaries
        ) == expected_candidate_occurrences
        assert served_run.cycles[0].selected_candidate_ref == second_id
        served_first = next(
            summary
            for summary in served_run.candidate_summaries
            if summary.candidate_id == first_id
        )
        served_second = next(
            summary
            for summary in served_run.candidate_summaries
            if summary.candidate_id == second_id
        )
        assert served_first.evaluation_attempt == failed_first.evaluation_attempt
        assert served_first.evaluation_attempt is not None
        assert served_first.evaluation_attempt.failure_stage == "n5"
        assert served_first.evaluation_attempt.simulation.authority_blockers == (
            "candidate_scenario_value_outside_profile_domain",
        )
        assert served_second.evaluation_attempt is None
        assert served_run.cycles[0].simulation.simulation_result_ref is not None
        failed_index = next(
            index
            for index, summary in enumerate(local_result.candidate_summaries)
            if summary.candidate_id == first_id
        )
        original_attempt = failed_first.evaluation_attempt
        assert original_attempt is not None

        foreign_problem_ref = "sha256:" + "f" * 64
        foreign_attempt_ref = _candidate_evaluation_attempt_ref(
            candidate_id=original_attempt.candidate_id,
            candidate_content_hash=original_attempt.candidate_content_hash,
            cycle_index=original_attempt.cycle_index,
            problem_ref=foreign_problem_ref,
            failure_stage=original_attempt.failure_stage,
            simulation=original_attempt.simulation,
            value=original_attempt.value,
        )
        foreign_attempt = CandidateEvaluationAttempt.model_validate(
            {
                **original_attempt.model_dump(mode="python"),
                "problem_ref": foreign_problem_ref,
                "attempt_ref": foreign_attempt_ref,
            }
        )
        foreign_summary = failed_first.model_copy(update={"evaluation_attempt": foreign_attempt})
        foreign_wire = dict(valid_wire)
        foreign_summaries = list(valid_wire["candidate_summaries"])
        foreign_summaries[failed_index] = foreign_summary.model_dump(mode="json")
        foreign_wire["candidate_summaries"] = foreign_summaries
        foreign_issues = validate_generation_cycle_run_history(foreign_wire)
        assert any(
            issue.get("code") == "candidate_evaluation_attempt_problem_basis_mismatch"
            for issue in foreign_issues
        )

        inconsistent_summary = failed_first.model_copy(
            update={
                "value_status": "value_blocked",
                "value_ref": "sha256:" + "a" * 64,
                "value_blockers": ("summary_projection_changed",),
            }
        )
        inconsistent_wire = dict(valid_wire)
        inconsistent_summaries = list(valid_wire["candidate_summaries"])
        inconsistent_summaries[failed_index] = inconsistent_summary.model_dump(mode="json")
        inconsistent_wire["candidate_summaries"] = inconsistent_summaries
        inconsistent_issues = validate_generation_cycle_run_history(inconsistent_wire)
        assert any(
            issue.get("code") == "candidate_evaluation_attempt_summary_mismatch"
            for issue in inconsistent_issues
        )

        # Shared/unknown admission and removal of the issued marker are controls:
        # neither may queue the otherwise grounded second candidate.
        (
            shared_result,
            shared_calls,
            shared_owner_n5_calls,
            shared_generation_count,
        ) = await run_case_async("shared")
        (
            stripped_result,
            stripped_calls,
            stripped_owner_n5_calls,
            stripped_generation_count,
        ) = await run_case_async("stripped_marker")
        for result, calls, owner_n5_calls, generation_count, expected_blocker in (
            (
                shared_result,
                shared_calls,
                shared_owner_n5_calls,
                shared_generation_count,
                "shared_context_currentness_unknown",
            ),
            (
                stripped_result,
                stripped_calls,
                stripped_owner_n5_calls,
                stripped_generation_count,
                "candidate_scenario_value_outside_profile_domain",
            ),
        ):
            assert generation_count == 1
            assert calls == (first_id,)
            assert owner_n5_calls == ()
            assert result.cycles[0].selected_candidate_ref == first_id
            assert result.cycles[0].simulation.status == "simulation_blocked"
            assert result.cycles[0].simulation.authority_blockers == (expected_blocker,)
            assert all(summary.evaluation_attempt is None for summary in result.candidate_summaries)
            refusal_wire = result.model_dump(mode="json")
            assert validate_generation_cycle_run_history(refusal_wire) == ()
            served_refusal = type(result).model_validate(refusal_wire)
            assert served_refusal.cycles[0].candidate_ids == expected_candidate_occurrences
            assert tuple(
                summary.candidate_id for summary in served_refusal.candidate_summaries
            ) == expected_candidate_occurrences
            assert served_refusal.cycles[0].selected_candidate_ref == first_id

        # A real shared scheduler stop must suppress both the simulation call
        # and any candidate-local sibling retry.
        (
            budget_result,
            budget_calls,
            budget_owner_n5_calls,
            budget_generation_count,
        ) = await run_case_async("shared_budget")
        assert budget_generation_count == 1
        assert budget_calls == ()
        assert budget_owner_n5_calls == ()
        assert budget_result.cycles[0].selected_candidate_ref == first_id
        assert budget_result.cycles[0].simulation.status == "simulation_blocked"
        assert "budget_exhausted_for_next_level" in (
            budget_result.cycles[0].simulation.authority_blockers
        )
        assert all(
            summary.evaluation_attempt is None for summary in budget_result.candidate_summaries
        )
        budget_wire = budget_result.model_dump(mode="json")
        assert validate_generation_cycle_run_history(budget_wire) == ()
        served_budget_refusal = type(budget_result).model_validate(budget_wire)
        assert served_budget_refusal.cycles[0].candidate_ids == expected_candidate_occurrences
        assert tuple(
            summary.candidate_id for summary in served_budget_refusal.candidate_summaries
        ) == expected_candidate_occurrences
        assert served_budget_refusal.cycles[0].selected_candidate_ref == first_id

        # This all-local control uses the owner classifier on a controlled
        # second refusal. It bounds the queue loop; it is not evidence of a
        # second persisted configured-N4 materialization.
        (
            all_local_result,
            all_local_calls,
            all_local_owner_n5_calls,
            all_local_generation_count,
        ) = await run_case_async("all_local_refusals")
        assert all_local_generation_count == 1
        assert all_local_calls == (first_id, second_id)
        assert all_local_owner_n5_calls == ()
        assert len(all_local_result.cycles) == 1
        assert all_local_result.cycles[0].selected_candidate_ref == second_id
        assert all_local_result.cycles[0].simulation.status == "simulation_blocked"
        assert all_local_result.cycles[0].simulation.authority_blockers == (
            "candidate_scenario_value_outside_profile_domain",
        )
    finally:
        witness.store.close()


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
    assert grounded["grounding_by_candidate"]["blocked-first"].status == ("grounding_unavailable")
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
    assert finished["value_port"].authority_blockers == ("budget_exhausted_for_next_level",)
