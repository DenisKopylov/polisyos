from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    LegacySearchServiceAdapter,
    OrchestratorFunnelService,
)
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations


class _Objective:
    @property
    def name(self) -> str:
        return "quadratic"

    def evaluate(self, results):
        value = float(results.get("objective_value", 0.0))
        return ObjectiveValue(
            name=self.name,
            raw_value=value,
            direction=OptimizationDirection.MINIMIZE,
        )


class _Generator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "candidate_legacy", "x": 1.0, "semantic": {"interventions": []}}


def test_legacy_search_service_adapter_exposes_ask_tell() -> None:
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_Objective()]),
        ),
        candidate_generator=_Generator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"objective_value": 1.0},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    adapter = LegacySearchServiceAdapter(controller)

    proposals = adapter.ask(goal=None, search_space=None, context={"run_id": "R_contract"})

    assert len(proposals) == 1
    assert proposals[0].candidate_id == "candidate_legacy"

    result = adapter.tell(
        proposals[0].candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=True,
            stage_b_result={"simulation_results": {"objective_value": 1.0}},
        ),
    )

    assert result.history_length == 1
    assert result.best_candidate == proposals[0].payload
    assert result.best_objective == 1.0


def test_orchestrator_funnel_service_submits_and_reads_outcome() -> None:
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = 0
    stage.stage_name = "L0"
    stage.estimated_cost_usd = 0.0
    stage.evaluate.return_value = FunnelStageResult(
        policy_candidate={"candidate_id": "candidate_funnel"},
        objective_value=0.1,
        is_promising=True,
        stage_name="L0",
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        fidelity_level=0,
    )
    service = OrchestratorFunnelService(FunnelOrchestrator([stage]))

    ticket = service.submit(
        CandidateProposal(
            candidate_id="candidate_funnel",
            payload={"candidate_id": "candidate_funnel"},
        ),
        context={"run_id": "R_contract"},
    )
    outcome = service.get_result(ticket)

    assert outcome.final_result.stage_name == "L0"
    assert outcome.final_result.objective_value == 0.1
    stage.evaluate.assert_called_once()


def test_shared_run_types_preserve_the_legacy_import_identity() -> None:
    from polisyos.scientist.methods.search.contracts import (
        GenerationTransition,
        SearchIteration,
        SearchResult,
        SearchStatus,
        _EvaluationDisposition,
        _EvaluationTransition,
    )
    from polisyos.scientist.methods.search.controller import (
        SearchIteration as ControllerSearchIteration,
    )
    from polisyos.scientist.methods.search.controller import (
        SearchResult as ControllerSearchResult,
    )
    from polisyos.scientist.methods.search.controller import (
        SearchStatus as ControllerSearchStatus,
    )
    from polisyos.scientist.methods.search.run_state import (
        GenerationTransition as RunStateGenerationTransition,
    )
    from polisyos.scientist.methods.search.run_state import (
        _EvaluationDisposition as RunStateEvaluationDisposition,
    )
    from polisyos.scientist.methods.search.run_state import (
        _EvaluationTransition as RunStateEvaluationTransition,
    )

    assert SearchStatus is ControllerSearchStatus
    assert SearchIteration is ControllerSearchIteration
    assert SearchResult is ControllerSearchResult
    assert GenerationTransition is RunStateGenerationTransition
    assert _EvaluationDisposition is RunStateEvaluationDisposition
    assert _EvaluationTransition is RunStateEvaluationTransition
    assert SearchStatus.__module__ == "polisyos.scientist.methods.search.controller"
    assert GenerationTransition.__module__ == "polisyos.scientist.methods.search.run_state"


def test_funnel_contract_keeps_full_historical_dto_surface_and_pickle_identity() -> None:
    import pickle
    from dataclasses import fields
    from importlib import import_module

    from polisyos.scientist.methods.search.contracts import FunnelService
    from polisyos.scientist.methods.search.funnel.orchestrator import (
        FunnelOutcome,
        FunnelTicket,
        FunnelTraceStep,
    )
    from polisyos.scientist.methods.search.stage_contracts import (
        SearchStage as SharedSearchStage,
    )
    from polisyos.scientist.methods.search.stage_contracts import (
        StageResult as SharedStageResult,
    )
    from polisyos.scientist.methods.search.stages import SearchStage, StageResult

    historical_module = import_module("polisyos.scientist.methods.search.funnel.orchestrator")
    assert historical_module.FunnelTicket is FunnelTicket
    assert historical_module.FunnelOutcome is FunnelOutcome
    assert historical_module.FunnelTraceStep is FunnelTraceStep
    assert FunnelTicket.__module__ == historical_module.__name__
    assert FunnelOutcome.__module__ == historical_module.__name__
    assert FunnelTraceStep.__module__ == historical_module.__name__
    assert SharedSearchStage is SearchStage
    assert SharedStageResult is StageResult
    assert SearchStage.__module__ == "polisyos.scientist.methods.search.stages"
    assert StageResult.__module__ == "polisyos.scientist.methods.search.stages"
    assert FunnelService.submit.__annotations__["return"] == "FunnelTicket"
    assert FunnelService.get_result.__annotations__["return"] == "FunnelOutcome"

    expected_fields = {
        FunnelTicket: (
            "ticket_id",
            "candidate_hash",
            "candidate",
            "context",
            "submitted_via_cache",
            "stage_results",
            "trace",
            "current_level",
            "next_level",
            "final_action",
            "degradation_mode",
            "is_terminal",
            "last_scheduling_decision",
            "lesson_refs",
            "correlation_recorded",
            "lessons_finalized",
            "cache_key",
            "parent_ticket_id",
            "lineage",
            "continuation_reason",
            "terminal_basis",
        ),
        FunnelOutcome: (
            "ticket_id",
            "candidate_hash",
            "trace",
            "stage_results",
            "final_result",
            "failure_cards",
            "uncertainty_envelope",
            "compute_cost_usd",
            "compute_cost_origin",
            "degradation_mode",
            "final_action",
            "completed",
            "last_scheduling_decision",
            "lesson_refs",
            "audit_refs",
            "actionable_side_information_refs",
            "parent_ticket_id",
            "lineage",
            "continuation_reason",
            "evaluation_status",
            "current_uncertainty_envelope",
            "uncertainty_observation_refs",
            "uncertainty_intake_failures",
        ),
        FunnelTraceStep: (
            "fidelity_level",
            "stage_name",
            "objective_value",
            "is_promising",
            "duration_seconds",
            "compute_cost_usd",
            "compute_cost_origin",
            "executed_work_packet_ref",
            "executed_work_packet_status",
            "routing_decision",
            "voi_action",
            "voi_priority",
            "failure_count",
            "blocker_count",
        ),
    }
    assert {
        dto_type: tuple(field.name for field in fields(dto_type)) for dto_type in expected_fields
    } == expected_fields

    ticket = FunnelTicket(ticket_id="t", candidate_hash="h", candidate={}, context={})
    outcome = FunnelOutcome(
        ticket_id="t",
        candidate_hash="h",
        trace=[],
        stage_results={},
        final_result=None,
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        compute_cost_usd=None,
        compute_cost_origin="unknown",
        degradation_mode="normal",
        final_action="advance",
        completed=False,
    )
    trace_step = FunnelTraceStep(
        fidelity_level=0,
        stage_name="L0",
        objective_value=0.0,
        is_promising=False,
        duration_seconds=0.0,
        compute_cost_usd=None,
        compute_cost_origin="unknown",
    )
    stage_result = StageResult(
        policy_candidate={"candidate_id": "stage-contract"},
        objective_value=0.0,
        is_promising=True,
        stage_name="contract-test",
    )
    for instance in (ticket, outcome, trace_step, stage_result):
        serialized = pickle.dumps(instance)
        restored = pickle.loads(serialized)  # noqa: S301 -- locally built DTO round-trip
        assert type(restored) is type(instance)
        assert restored == instance
