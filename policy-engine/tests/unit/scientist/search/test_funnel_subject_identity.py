"""Funnel admission and reuse must bind actual candidate and context inputs."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    CandidateStrategyContext,
)
from polisyos.scientist.methods.search.frontier import (
    invoke_candidate_evaluator,
    strategy_candidate_payload,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
)
from polisyos.scientist.methods.search.objective import GDPGrowthObjective


class _InputStage(FunnelStage):
    def __init__(self) -> None:
        self.observed: list[tuple[dict[str, Any], float]] = []

    @property
    def fidelity_level(self) -> int:
        return 0

    @property
    def stage_name(self) -> str:
        return "input-semantic-probe"

    @property
    def estimated_cost_usd(self) -> float:
        return 0.1

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        value = context["model_config"]["valid_at"]
        self.observed.append((candidate, value))
        source = {"gdp_change": value, "metric_units": {"gdp_change": "fixture-unit"}}
        score = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source)
        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=score.raw_value,
            score_status=score.score_status,
            score_assessment=score.score_assessment,
            simulation_results=source,
            is_promising=True,
            feedback={"verdict": "APPROVE"},
            stage_name=self.stage_name,
            fidelity_level=self.fidelity_level,
            compute_cost_usd=self.estimated_cost_usd,
            compute_cost_origin="estimated",
        )


def _proposal(identifier: str) -> CandidateProposal:
    context = CandidateStrategyContext(
        subject={"x": 1.0}, strategy_fields={"candidate_id": identifier}
    )
    return CandidateProposal(
        candidate_id=identifier,
        payload=strategy_candidate_payload(context),
        strategy_context=context,
    )


def test_funnel_hides_producer_context_and_runs_independent_requests_fresh() -> None:
    stage = _InputStage()
    runtime = FunnelOrchestrator([stage])
    stage_b = runtime.as_stage_b_callable()
    first, second = _proposal("first"), _proposal("second")
    context = {"model_config": {"valid_at": 0.1}}
    invoke_candidate_evaluator(stage_b, first.payload, context, first)
    invoke_candidate_evaluator(stage_b, second.payload, context, second)
    assert stage.observed == [(first.payload, 0.1), (second.payload, 0.1)]
    assert "_strategy_metadata" not in stage.observed[0][0]
    changed = {"model_config": {"valid_at": 0.2}}
    invoke_candidate_evaluator(stage_b, second.payload, changed, second)
    assert stage.observed == [(first.payload, 0.1), (second.payload, 0.1), (second.payload, 0.2)]


def test_opaque_context_executes_fresh_instead_of_reuse() -> None:
    stage = _InputStage()
    runtime = FunnelOrchestrator([stage])
    proposal = _proposal("same")
    context = {"model_config": {"valid_at": 0.1}, "opaque_owner": object()}
    first = runtime.submit(proposal.payload, context, candidate_proposal=proposal)
    runtime.advance(first)
    second = runtime.submit(proposal.payload, context, candidate_proposal=proposal)
    runtime.advance(second)
    assert len(stage.observed) == 2
    assert first.ticket_id != second.ticket_id


def test_real_funnel_lifecycle_history_round_trips_selected_source(tmp_path) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
    from polisyos.scientist.methods.search.objective import (
        CompositeObjective,
        configured_objective_rule_spec,
    )
    from polisyos.scientist.methods.search.stopping import MaxIterations
    from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
    from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
    from polisyos.scientist.methods.search.strategies.space import SearchSpace
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import ParameterBounds

    space = SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)])
    objective = GDPGrowthObjective(expected_unit="fixture-unit")
    fingerprint = RunFingerprint(
        run_id="provided",
        space_hash=space.sobol_space_fingerprint(),
        objective_names=[objective.name],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={objective.name: "fixture-unit"},
        origin="fixture",
        tenant_id="fixture",
        objective_directions={objective.name: objective.direction.value},
        objective_rule_specs={objective.name: configured_objective_rule_spec(objective) or ""},
    )
    manager = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    funnel = FunnelOrchestrator([_InputStage()])
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([objective]),
            transfer_manager=manager,
            transfer_fingerprint=fingerprint,
        ),
        candidate_generator=StrategyAdapter(RandomSearchStrategy(space=space, seed=1), space),
        stage_a_evaluator=funnel.as_stage_a_callable(),
        stage_b_evaluator=funnel.as_stage_b_callable(),
    )
    result = controller.run({"model_config": {"valid_at": 0.1}})
    receipt = result.telemetry["transfer_history"]
    assert receipt["status"] == "persisted"
    source = RunFingerprint.model_validate(receipt["fingerprint"]).model_copy(
        update={"history_ref": ArtifactRef.model_validate(receipt["history_ref"])}
    )
    target = source.model_copy(update={"run_id": "fresh-target"})
    fresh = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    [evaluation] = fresh.get_warm_start_evaluations([source], target_fingerprint=target)
    assert evaluation.stage_b_result is not None
    projection = evaluation.stage_b_result["funnel_outcome_projection"]
    assert all(isinstance(level, str) for level in projection["stage_results"])
    assert evaluation.stage_b_result["simulation_results"]["gdp_change"] == 0.1
    assert evaluation.metadata["funnel_source_binding"] == "not_established"


def test_opaque_split_exposes_both_physical_attempt_traces() -> None:
    from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
    from polisyos.scientist.methods.search.objective import CompositeObjective
    from polisyos.scientist.methods.search.stopping import MaxIterations
    from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
    from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
    from polisyos.scientist.methods.search.strategies.space import SearchSpace
    from polisyos.scientist.methods.search.strategies.types import ParameterBounds

    space = SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)])
    stage = _InputStage()
    funnel = FunnelOrchestrator([stage])
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([GDPGrowthObjective(expected_unit="fixture-unit")]),
        ),
        candidate_generator=StrategyAdapter(RandomSearchStrategy(space=space, seed=1), space),
        stage_a_evaluator=funnel.as_stage_a_callable(),
        stage_b_evaluator=funnel.as_stage_b_callable(),
    )
    result = controller.run({"model_config": {"valid_at": 0.1}, "opaque_owner": object()})
    assert len(stage.observed) == 2
    outcome = result.history[0].stage_b_result["_funnel_outcome"]
    assert outcome.prior_attempt_ticket_id is not None
    assert outcome.prior_attempt_ticket_id != outcome.ticket_id
    assert outcome.prior_attempt_ticket_id in outcome.lineage
    assert len(outcome.prior_attempt_trace) == 1
    assert len(outcome.trace) == 1
    assert outcome.prior_attempt_trace[0].compute_cost_usd == 0.1
    assert outcome.trace[0].compute_cost_usd == 0.1


def test_generic_evaluator_receives_no_hidden_proposal_or_prior_ticket() -> None:
    first = _proposal("first")
    seen: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def evaluator(candidate: dict[str, Any], context: dict[str, Any]) -> None:
        seen.append((candidate, context))

    original_context = {"_search_candidate_proposal": {"meaning": "caller semantic"}}
    invoke_candidate_evaluator(
        evaluator, first.payload, original_context, first, prior_ticket_id="not-a-ticket"
    )
    assert seen == [(first.payload, original_context)]
    assert "_funnel_stage_a_ticket_id" not in seen[0][1]
    assert "_strategy_metadata" not in seen[0][0]


class _BasisStage(_InputStage):
    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        basis = context["_funnel_method_metric_projection_basis"]
        value = basis["value"] if isinstance(basis, dict) else basis.value
        observed_context = {**context, "model_config": {"valid_at": value}}
        return super().evaluate(candidate, observed_context)


def test_method_metric_basis_that_stage_reads_changes_cache_and_opaque_runs_fresh() -> None:
    stage = _BasisStage()
    runtime = FunnelOrchestrator([stage])
    proposal = _proposal("basis")
    base = {"model_config": {"valid_at": 0.0}}
    for value in (0.1, 0.2):
        context = {**base, "_funnel_method_metric_projection_basis": {"value": value}}
        ticket = runtime.submit(proposal.payload, context, candidate_proposal=proposal)
        runtime.advance(ticket)
    assert [value for _, value in stage.observed] == [0.1, 0.2]

    class OpaqueBasis:
        value = 0.3

    opaque = {**base, "_funnel_method_metric_projection_basis": OpaqueBasis()}
    for _ in range(2):
        ticket = runtime.submit(proposal.payload, opaque, candidate_proposal=proposal)
        runtime.advance(ticket)
    assert [value for _, value in stage.observed] == [0.1, 0.2, 0.3, 0.3]


def test_changed_cacheable_context_links_both_physical_attempts() -> None:
    from polisyos.scientist.methods.search.frontier import funnel_prior_ticket_id

    stage = _InputStage()
    funnel = FunnelOrchestrator([stage])
    stage_a = funnel.as_stage_a_callable()
    stage_b = funnel.as_stage_b_callable()
    proposal = _proposal("changed-context")
    first_context = {"model_config": {"valid_at": 0.1}}
    first = invoke_candidate_evaluator(stage_a, proposal.payload, first_context, proposal)
    prior_id = funnel_prior_ticket_id(stage_a, stage_b, first)
    assert prior_id is not None
    changed = {**first_context, "candidate_only_transfer": {"source_run_id": "old"}}
    second = invoke_candidate_evaluator(
        stage_b, proposal.payload, changed, proposal, prior_ticket_id=prior_id
    )
    outcome = second["_funnel_outcome"]
    assert len(stage.observed) == 2
    assert outcome.prior_attempt_ticket_id == prior_id
    assert len(outcome.prior_attempt_trace) == len(outcome.trace) == 1
    assert (
        outcome.prior_attempt_trace[0].compute_cost_usd == outcome.trace[0].compute_cost_usd == 0.1
    )


def test_mutating_stage_cannot_relabel_its_score_with_pre_stage_hash() -> None:
    class MutatingStage(_InputStage):
        def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
            candidate["x"] = 99.0
            return super().evaluate(candidate, context)

    funnel = FunnelOrchestrator([MutatingStage()])
    original = {"x": 1.0}
    ticket = funnel.submit(original, {"model_config": {"valid_at": 0.1}})
    outcome = funnel.advance(ticket)
    assert original == ticket.candidate == {"x": 1.0}
    assert outcome.final_action == "defer"
    assert outcome.continuation_reason == "evaluated_subject_mutated"
    assert outcome.trace[-1].objective_value is None
    assert outcome.trace[-1].score_status.value == "invalid"
    assert not outcome.trace[-1].is_promising
    assert outcome.trace[-1].compute_cost_usd == 0.1


def test_live_split_rechecks_changed_owner_on_same_ticket_and_retains_cost() -> None:
    from polisyos.scientist.methods.search.frontier import funnel_prior_ticket_id

    class LessonOwner:
        value = 0.1

    class LessonReadingStage(_InputStage):
        def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
            value = context["lesson_registry"].value
            return super().evaluate(candidate, {**context, "model_config": {"valid_at": value}})

    owner, stage = LessonOwner(), LessonReadingStage()
    funnel = FunnelOrchestrator([stage], lesson_registry=owner)
    proposal = _proposal("owner-changes")
    context = {"model_config": {"valid_at": 0.0}}
    stage_a, stage_b = funnel.as_stage_a_callable(), funnel.as_stage_b_callable()
    first = invoke_candidate_evaluator(stage_a, proposal.payload, context, proposal)
    prior = funnel_prior_ticket_id(stage_a, stage_b, first)
    assert prior is not None
    owner.value = 0.2
    second = invoke_candidate_evaluator(
        stage_b, proposal.payload, context, proposal, prior_ticket_id=prior
    )
    outcome = second["_funnel_outcome"]
    assert outcome.ticket_id == prior
    assert [value for _, value in stage.observed] == [0.1, 0.2]
    assert len(outcome.trace) == 2
    assert sum(step.compute_cost_usd or 0.0 for step in outcome.trace) == 0.2
    assert outcome.continuation_reason == "live_split_gates_rechecked"


def test_live_split_rechecks_real_l1_after_lesson_registry_changes(tmp_path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.frontier import funnel_prior_ticket_id
    from polisyos.scientist.methods.search.funnel.level1_heuristic import Level1CheapHeuristic
    from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind, LessonRegistry

    registry = LessonRegistry(root=tmp_path / "lessons", store=FileSystemCAS(tmp_path / "cas"))
    candidate = {
        "semantic": {
            "interventions": [{"type": "tax_reform", "parameters": {"income_tax_rate": 0.25}}],
            "objectives": [{"name": "gdp_growth", "variable": "gdp"}],
        }
    }
    funnel = FunnelOrchestrator([Level1CheapHeuristic()], lesson_registry=registry)
    stage_a, stage_b = funnel.as_stage_a_callable(), funnel.as_stage_b_callable()
    first = invoke_candidate_evaluator(stage_a, candidate, {}, None)
    prior = funnel_prior_ticket_id(stage_a, stage_b, first)
    assert prior is not None
    registry.record(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="A real prior lesson for this pattern.",
            failure_type="transport_failure",
            stage_name="funnel_L1_heuristic",
            fidelity_level=1,
            candidate_hash="pattern",
            source_run_id="run-1",
            tags=["tax_reform", "gdp_growth"],
        )
    )
    second = invoke_candidate_evaluator(stage_b, candidate, {}, None, prior_ticket_id=prior)
    outcome = second["_funnel_outcome"]
    assert outcome.ticket_id == prior
    assert len(outcome.trace) == 2
    assert any(card.failure_type == "lesson_registry_match" for card in outcome.failure_cards)


def test_live_split_rechecks_real_l5_after_correlation_ban_changes() -> None:
    from polisyos.scientist.methods.search.frontier import funnel_prior_ticket_id
    from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
        Level5RefutationGovernanceStage,
    )

    class Tracker:
        ban = False

        def routing_mode(self) -> str:
            return "no_promotion" if self.ban else "normal"

        def compute_metrics(self) -> dict[str, object]:
            return {"promotion_ban_active": self.ban, "routing_mode": self.routing_mode()}

    tracker = Tracker()
    funnel = FunnelOrchestrator(
        [Level5RefutationGovernanceStage(require_hidden_holdout=False)],
        stage_a_max_level=5,
        correlation_tracker=tracker,
    )
    stage_a, stage_b = funnel.as_stage_a_callable(), funnel.as_stage_b_callable()
    candidate = {"semantic": {"interventions": [], "objectives": []}}
    first = invoke_candidate_evaluator(stage_a, candidate, {}, None)
    prior = funnel_prior_ticket_id(stage_a, stage_b, first)
    assert prior is not None
    tracker.ban = True
    second = invoke_candidate_evaluator(stage_b, candidate, {}, None, prior_ticket_id=prior)
    outcome = second["_funnel_outcome"]
    assert outcome.ticket_id == prior
    assert len(outcome.trace) == 2
    assert any(
        card.failure_type == "calibration_drift_promotion_ban" for card in outcome.failure_cards
    )


def test_typed_policy_producers_deliver_the_same_canonical_input_to_real_funnel() -> None:
    from polisyos.scientist.methods.search.frontier import policy_candidate_hash

    from .test_pareto_transfer import _candidate

    class SemanticReadingStage(_InputStage):
        def __init__(self) -> None:
            super().__init__()
            self.semantic_seen: list[bool] = []

        def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
            present = "semantic" in candidate
            self.semantic_seen.append(present)
            return super().evaluate(
                candidate, {**context, "model_config": {"valid_at": 0.2 if present else 0.1}}
            )

    candidate = _candidate()
    subject = candidate.model_dump(mode="json", exclude_none=True)
    contexts = (
        CandidateStrategyContext(
            producer="strategy_adapter", subject=subject, policy_schema=True, policy_transport=True
        ),
        CandidateStrategyContext(
            producer="policy_design", subject=subject, policy_schema=True, policy_transport=True
        ),
    )
    proposals = [
        CandidateProposal(
            candidate_id=candidate.candidate_id,
            payload=strategy_candidate_payload(item),
            strategy_context=item,
        )
        for item in contexts
    ]
    assert policy_candidate_hash(proposals[0]) == policy_candidate_hash(proposals[1])
    assert proposals[0].payload == proposals[1].payload
    stage = SemanticReadingStage()
    stage_b = FunnelOrchestrator([stage]).as_stage_b_callable()
    for proposal in proposals:
        invoke_candidate_evaluator(stage_b, proposal.payload, {}, proposal)
    assert stage.semantic_seen == [False, False]
    assert [value for _, value in stage.observed] == [0.1, 0.1]


def test_blueprint_enriched_subject_keeps_canonical_candidate_and_effective_input_distinct() -> (
    None
):
    """The native blueprint's state-dependent semantic input remains in its ticket identity."""
    from polisyos.scientist.methods.search.frontier import policy_candidate_hash
    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_strategy import (
        _candidate_search_payload,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    from .test_pareto_transfer import _candidate

    class GraphReadingStage(_InputStage):
        def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
            value = candidate["semantic"]["causal_graph"]["weight"]
            return super().evaluate(candidate, {**context, "model_config": {"valid_at": value}})

    candidate = _candidate()
    payloads = [
        _candidate_search_payload(
            candidate,
            ExperimentState(run_id="same-run", params={"causal_graph": {"weight": value}}),
        )
        for value in (0.1, 0.2)
    ]
    assert (
        payloads[0]["candidate_hash"] == payloads[1]["candidate_hash"] == candidate.candidate_hash()
    )
    assert policy_candidate_hash(payloads[0]) != policy_candidate_hash(payloads[1])
    stage = GraphReadingStage()
    funnel = FunnelOrchestrator([stage])
    tickets = [funnel.submit(payload, {}) for payload in payloads]
    outcomes = [funnel.advance(ticket) for ticket in tickets]
    assert outcomes[0].candidate_hash != outcomes[1].candidate_hash
    assert [value for _, value in stage.observed] == [0.1, 0.2]


def test_three_linked_attempts_retain_each_owner_trace_in_serialized_history() -> None:
    import json

    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
        _serialize_funnel_outcome,
    )

    stage = _InputStage()
    funnel = FunnelOrchestrator([stage])
    candidate = {"subject": "same"}
    tickets = []
    outcomes = []
    for value in (0.1, 0.2, 0.3):
        ticket = funnel.submit(
            candidate,
            {"model_config": {"valid_at": value}},
            _prior_attempt_id=tickets[-1].ticket_id if tickets else None,
        )
        tickets.append(ticket)
        outcomes.append(funnel.advance(ticket))
    result = outcomes[-1]
    assert len({ticket.ticket_id for ticket in tickets}) == 3
    assert result.prior_attempt_history_status == "complete"
    assert [attempt.ticket_id for attempt in result.prior_attempt_history] == [
        tickets[0].ticket_id,
        tickets[1].ticket_id,
    ]
    assert [attempt.trace[0].objective_value for attempt in result.prior_attempt_history] == [
        0.1,
        0.2,
    ]
    assert result.trace[0].objective_value == 0.3
    assert [attempt.trace[0].compute_cost_usd for attempt in result.prior_attempt_history] == [
        0.1,
        0.1,
    ]
    projection = json.loads(json.dumps(_serialize_funnel_outcome(result)))
    assert [item["ticket_id"] for item in projection["prior_attempt_history"]] == [
        tickets[0].ticket_id,
        tickets[1].ticket_id,
    ]
    assert [
        item["trace"][0]["compute_cost_usd"] for item in projection["prior_attempt_history"]
    ] == [0.1, 0.1]
    assert projection["prior_attempt_history_status"] == "complete"

    # If an ancestor is unavailable, retain what is still known and expose the
    # missing history rather than silently presenting the chain as complete.
    del funnel._tickets[tickets[0].ticket_id]
    incomplete = funnel.get_outcome(tickets[-1])
    assert incomplete.prior_attempt_history_status == "verification_missing"
    assert [attempt.ticket_id for attempt in incomplete.prior_attempt_history] == [
        tickets[1].ticket_id
    ]
    assert (
        _serialize_funnel_outcome(incomplete)["prior_attempt_history_status"]
        == "verification_missing"
    )
