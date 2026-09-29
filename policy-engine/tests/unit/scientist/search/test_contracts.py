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
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)


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


def test_legacy_search_service_tell_rejects_finite_scalar_for_unassessed_vector(
    tmp_path,
) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([_Objective()]),
            pareto_registry=registry,
        ),
        candidate_generator=_Generator(),
        stage_a_evaluator=lambda *_: (0.0, True),
        stage_b_evaluator=lambda *_: {"simulation_results": {"objective_value": 1.0}},
    )
    adapter = LegacySearchServiceAdapter(controller)
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = PolicyEvaluationVector(
        candidate_id=proposal.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.0,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        secondary={
            "quality": ObjectiveChannelValue(
                name="quality",
                kind=ObjectiveKind.SECONDARY,
                value=float("nan"),
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
    )

    result = adapter.tell(
        proposal.candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=True,
            stage_b_result={
                "policy_evaluation": evaluation.model_dump(mode="python"),
                "feedback": {"verdict": "APPROVE"},
            },
        ),
    )

    assert result.best_candidate is None
    assert controller._history[0].policy_evaluation_status == "unassessed"
    assert controller._history[0].policy_evaluation_error is not None
    assert "secondary.quality.value:non_finite" in controller._history[0].policy_evaluation_error
    assert controller._history[0].is_promising is False
    assert controller._pareto_front == []
    persisted = registry.get_snapshot(controller._search_id).entries
    assert len(persisted) == 1
    entry = next(iter(persisted.values()))
    assert entry.policy_evaluation_status == "unassessed"
    assert entry.candidate_id == proposal.candidate_id
    assert entry.policy_evaluation_error is not None


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
