"""Bounded recursion checkpoint and sibling-status contract tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.pdc import SearchTerminalKind, gy_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveCycleNode,
    RecursiveCyclePendingNode,
    RecursiveGenerationCycleController,
    RecursiveGenerationCyclePartialRunV2,
    RecursiveGenerationCycleRun,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.runtime.quality.test_depth_n_universality import (
    _lane0_coupled_request,
    _recursive_problem,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


class _ScriptedCandidateGeneration:
    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> SimpleNamespace:
        del cycle_index
        candidate_id = f"candidate_{problem.design_problem_id}"
        atom = SimpleNamespace(
            intervention_id=f"intervention_{problem.design_problem_id}",
            content_hash=gy_content_hash(
                {
                    "problem_ref": gy_content_hash(problem.model_dump(mode="json")),
                    "candidate_id": candidate_id,
                }
            ),
            status="candidate_unverified",
            world_model_record_ref="world_model_record_contract_testing",
            target_world_slots=(problem.outcome_of_interest.target_variable,),
        )
        candidate = SimpleNamespace(
            candidate_id=candidate_id,
            atom=atom,
            diversity_key=("recursive-frontier", problem.design_problem_id),
            status="candidate_unverified",
        )
        ranking = SimpleNamespace(
            candidate_id=candidate_id,
            score=0.93,
            voi_estimate=0.82,
            trust_level="search_guiding",
            promotion_allowed=False,
        )
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(ranking,),
            grounding_dispositions=(),
        )


class _StableShadowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        candidate_id = str(candidate.candidate_id)
        return CandidateGroundingObservation(
            candidate_id=candidate_id,
            status="grounded_shadow",
            grounding_score=0.8,
            evidence_refs=("evidence://recursive-frontier/stable-shadow",),
            current_valid=False,
            report_ref="grounding://recursive-frontier/stable-shadow",
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


class _PendingSimulation:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        candidate_id = str(candidate.candidate_id)
        self.calls.append(candidate_id)
        return SimulationPortObservation(
            candidate_id=candidate_id,
            status="simulation_pending_n5",
            authority_blockers=("contract_fixture_does_not_run_n5",),
        )


class _RecordingPendingN8:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self._pending = PendingN8ValuePort()

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(str(kwargs["candidate"].candidate_id))
        return self._pending(**kwargs)


class _PendingN9:
    def __call__(self, **kwargs: Any) -> PromotionPortObservation:
        del kwargs
        return PromotionPortObservation()


class _CycleControllerFactory:
    def __init__(self) -> None:
        self.visited_node_refs: list[str] = []
        self.simulation_calls: list[str] = []
        self.value_calls: list[str] = []

    def __call__(self, node_ref: str, problem: DesignProblem) -> GenerationCycleController:
        del problem
        self.visited_node_refs.append(node_ref)
        return GenerationCycleController(
            generation_port=_ScriptedCandidateGeneration(),
            grounding_port=_StableShadowGrounding(),
            simulation_port=_PendingSimulation(self.simulation_calls),
            value_port=_RecordingPendingN8(self.value_calls),
            promotion_port=_PendingN9(),
            authority_scope="contract_testing",
            repo_root=REPO_ROOT,
        )


def _recursive_fixture() -> tuple[
    str,
    tuple[str, str],
    dict[str, DesignProblem],
    Any,
    Any,
]:
    root_ref = "design://e02/recursive-budget/root"
    child_refs = (
        "design://e02/recursive-budget/child-a",
        "design://e02/recursive-budget/child-b",
    )
    problems = {
        node_ref: _recursive_problem(node_ref)
        for node_ref in (root_ref, *child_refs)
    }
    request = _lane0_coupled_request(
        parent_ref=root_ref,
        child_refs=child_refs,
        problem=problems[root_ref],
    )
    coupling_graph = request.coupling_graph
    assert coupling_graph is not None
    typed_dependency_edges = tuple(
        {
            "boundary_ref": edge.boundary_ref,
            "source_module_ref": edge.source_module_ref,
            "target_module_ref": edge.target_module_ref,
            "relation": edge.relation,
            "interaction_strength": str(edge.interaction_strength),
            "evidence_ref": edge.evidence_ref,
        }
        for edge in coupling_graph.interaction_edges
    )
    recursive_graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=child_refs,
        parent_child_edges=((root_ref, child_refs[0]), (root_ref, child_refs[1])),
        typed_dependency_edges=typed_dependency_edges,
        rule_version_ref="repo://rules/e02-recursive-frontier-contract-test",
    )
    return root_ref, child_refs, problems, request, recursive_graph


async def _run_recursive_fixture(
    *,
    budget_state: BudgetState,
) -> tuple[
    RecursiveGenerationCycleRun | RecursiveGenerationCyclePartialRunV2,
    tuple[str, str],
    Any,
    _CycleControllerFactory,
]:
    root_ref, child_refs, problems, request, recursive_graph = _recursive_fixture()
    factory = _CycleControllerFactory()
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=factory,
        repo_root=REPO_ROOT,
    )
    result = await controller.run(
        recursive_graph,
        problems_by_node=problems,
        budget_state=budget_state,
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
        joint_simulation_requests_by_node={root_ref: request},
        # This candidate-only intent bypasses the N9 ownership check without
        # granting the scripted N6 contract fixture authority.
        execution_intents_by_node=dict.fromkeys(child_refs, "candidate_only"),
    )
    return result, child_refs, request, factory


@pytest.mark.asyncio
async def test_canonical_child_budget_stop_keeps_completed_child_and_pending_sibling() -> None:
    """A canonical N6 budget terminal checkpoints the graph before sibling execution."""

    result, child_refs, request, factory = await _run_recursive_fixture(
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))}
        )
    )

    assert isinstance(result, RecursiveGenerationCyclePartialRunV2)
    assert result.schema_version == "policyos.runtime.recursive_generation_cycle.partial.v2"
    assert result.traversal_status == "budget_stopped"
    assert result.traversal_stop_reason == "child_budget_exhausted"
    assert result.budget_stop_node_ref == child_refs[0]
    assert result.frontier_node_refs == (child_refs[1],)
    assert result.terminal is None
    assert set(result.recursive_graph.node_refs) == {
        node.node_ref for node in result.nodes
    }

    by_ref = {node.node_ref: node for node in result.nodes}
    root_node = by_ref[result.root_node_ref]
    budget_child = by_ref[child_refs[0]]
    pending_sibling = by_ref[child_refs[1]]
    assert isinstance(root_node, RecursiveCyclePendingNode)
    assert isinstance(budget_child, RecursiveCycleNode)
    assert budget_child.cycle_run is not None
    assert budget_child.terminal.kind is SearchTerminalKind.BUDGET_EXHAUSTED
    cycle = budget_child.cycle_run.cycles[-1]
    assert cycle.simulation.status == "simulation_blocked"
    assert cycle.simulation.authority_blockers == ("budget_exhausted_for_next_level",)
    assert cycle.voi_decision.scheduler_action == "defer"
    assert cycle.voi_decision.scheduler_reason == "budget_exhausted_for_next_level"
    assert isinstance(pending_sibling, RecursiveCyclePendingNode)
    assert factory.visited_node_refs == [child_refs[0]]
    assert factory.simulation_calls == []
    assert factory.value_calls == []

    coupling_graph = request.coupling_graph
    assert coupling_graph is not None
    assert coupling_graph.evidence_state == "observed"
    assert len(coupling_graph.interaction_edges) == 1
    edge = coupling_graph.interaction_edges[0]
    assert (edge.source_module_ref, edge.target_module_ref) == child_refs
    assert result.recursive_graph.typed_dependency_edges == [
        {
            "boundary_ref": edge.boundary_ref,
            "source_module_ref": edge.source_module_ref,
            "target_module_ref": edge.target_module_ref,
            "relation": edge.relation,
            "interaction_strength": str(edge.interaction_strength),
            "evidence_ref": edge.evidence_ref,
        }
    ]

    # This is an artifact-level JSON readback only; the served CAS/API consumer
    # remains a separate root-owned bridge.
    persisted = RecursiveGenerationCyclePartialRunV2.model_validate(
        result.model_dump(mode="json")
    )
    assert persisted.content_hash == result.content_hash
    forged = persisted.model_dump(mode="json")
    forged["budget_stop_node_ref"] = child_refs[1]
    forged_payload = {key: value for key, value in forged.items() if key != "content_hash"}
    forged["content_hash"] = gy_content_hash(forged_payload)
    with pytest.raises(ValidationError, match="recursive_partial_budget_stop_not_owner_derived"):
        RecursiveGenerationCyclePartialRunV2.model_validate(forged)


@pytest.mark.asyncio
async def test_epistemic_abstention_does_not_truncate_recursive_sibling() -> None:
    """N8 pending abstention stays distinct from a controller budget stop."""

    result, child_refs, _request, factory = await _run_recursive_fixture(
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}
        )
    )

    assert type(result) is RecursiveGenerationCycleRun
    leaves = {node.node_ref: node for node in result.leaf_nodes}
    assert set(leaves) == set(child_refs)
    assert all(
        leaves[child_ref].terminal.kind is SearchTerminalKind.GROUNDED_ABSTENTION
        for child_ref in child_refs
    )
    assert factory.visited_node_refs == list(child_refs)
    assert len(factory.simulation_calls) == 2
    assert len(factory.value_calls) == 2
    root = next(node for node in result.nodes if node.node_ref == result.root_node_ref)
    assert root.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root.terminal.blocking_obligations == ["subdesign_contract_denominator_missing"]
    assert root.joint_simulation is None
