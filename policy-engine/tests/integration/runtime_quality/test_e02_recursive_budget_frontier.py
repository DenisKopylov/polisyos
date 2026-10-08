"""Bounded recursion checkpoint and sibling-status contract tests."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

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
    GenerationCycleRun,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
    generation_cycle_terminal_state,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    intervention_atom_content_hash,
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

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


# These pure bounded helpers come from exact A8bfea70 supplier bytes.
def _recursive_problem(node_ref: str) -> DesignProblem:
    payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
        ).read_text(encoding="utf-8")
    )["design_problem"]
    problem = DesignProblem.model_validate(payload)
    design_problem_suffix = re.sub(
        r"[^a-z0-9_]+",
        "_",
        node_ref.rsplit("/", 1)[-1].lower(),
    ).strip("_")
    return problem.model_copy(
        update={
            "design_problem_id": f"recursive_{design_problem_suffix}",
            "objectives": [
                problem.objectives[0].model_copy(update={"metric_id": "final_queue_length"})
            ],
            "outcome_of_interest": problem.outcome_of_interest.model_copy(
                update={
                    "target_variable": "final_queue_length",
                    "metric_id": "final_queue_length",
                    "estimand": "effect on the final claims queue length",
                    "direction": "minimize",
                }
            ),
        }
    )


def _lane0_coupled_request(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
    problem: DesignProblem,
) -> Any:
    module = import_module(
        "tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract"
    )
    request = cast("Any", module)._coupled_request()
    graph = request.coupling_graph
    assert graph is not None
    edges = tuple(
        edge.model_copy(
            update={
                "source_module_ref": child_refs[0],
                "target_module_ref": child_refs[1],
            }
        )
        for edge in graph.interaction_edges
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    atoms: list[InterventionAtomBinding] = []
    for atom in request.intervention_atoms:
        draft = atom.model_copy(update={"problem_frame_ref": problem_ref})
        content_hash = intervention_atom_content_hash(draft)
        bound = draft.model_copy(
            update={
                "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
                "content_hash": content_hash,
            }
        )
        atoms.append(InterventionAtomBinding.model_validate(bound.model_dump(mode="python")))
    return request.model_copy(
        update={
            "intervention_atoms": tuple(atoms),
            "coupling_graph": graph.model_copy(
                update={
                    "design_ref": parent_ref,
                    "module_refs": child_refs,
                    "interaction_edges": edges,
                    "evidence_state": "observed",
                }
            ),
        }
    )


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
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def __call__(self, **kwargs: Any) -> PromotionPortObservation:
        self.calls.append(str(kwargs["problem"].design_problem_id))
        return PromotionPortObservation()


class _CycleControllerFactory:
    def __init__(self) -> None:
        self.visited_node_refs: list[str] = []
        self.node_ref_by_problem_id: dict[str, str] = {}
        self.simulation_calls: list[str] = []
        self.value_calls: list[str] = []
        self.promotion_calls: list[str] = []

    def __call__(self, node_ref: str, problem: DesignProblem) -> GenerationCycleController:
        self.visited_node_refs.append(node_ref)
        self.node_ref_by_problem_id[problem.design_problem_id] = node_ref
        return GenerationCycleController(
            generation_port=_ScriptedCandidateGeneration(),
            grounding_port=_StableShadowGrounding(),
            simulation_port=_PendingSimulation(self.simulation_calls),
            value_port=_RecordingPendingN8(self.value_calls),
            promotion_port=_PendingN9(self.promotion_calls),
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
    problems = {node_ref: _recursive_problem(node_ref) for node_ref in (root_ref, *child_refs)}
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


def _assert_leaf_n9_observations_match_calls(
    result: RecursiveGenerationCycleRun | RecursiveGenerationCyclePartialRunV2,
    factory: _CycleControllerFactory,
) -> None:
    """Reconcile each recorded leaf-port call with its emitted observation."""

    leaves = {node.node_ref: node for node in result.leaf_nodes}
    called_node_refs = tuple(
        factory.node_ref_by_problem_id[problem_id] for problem_id in factory.promotion_calls
    )
    assert set(called_node_refs).issubset(leaves)
    assert len(called_node_refs) == len(set(called_node_refs))
    for node_ref, node in leaves.items():
        assert node.cycle_run is not None
        promotion = node.cycle_run.promotion_port
        if node_ref in called_node_refs:
            assert promotion.status == "promotion_pending_n9"
        else:
            assert promotion.status == "not_promoted"
            assert not promotion.certified_candidate_ids
            assert not promotion.receipts


@pytest.mark.asyncio
async def test_budget_stopped_child_keeps_completed_child_and_pending_sibling() -> None:
    """A canonical N6 budget terminal checkpoints the graph before sibling execution."""

    result, child_refs, request, factory = await _run_recursive_fixture(
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))})
    )

    assert isinstance(result, RecursiveGenerationCyclePartialRunV2)
    assert result.schema_version == "policyos.runtime.recursive_generation_cycle.partial.v2"
    assert result.traversal_status == "budget_stopped"
    assert result.traversal_stop_reason == "child_budget_exhausted"
    assert result.budget_stop_node_ref == child_refs[0]
    assert result.frontier_node_refs == (child_refs[1],)
    assert result.terminal is None
    assert set(result.recursive_graph.node_refs) == {node.node_ref for node in result.nodes}

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
    _assert_leaf_n9_observations_match_calls(result, factory)

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
    persisted = RecursiveGenerationCyclePartialRunV2.model_validate(result.model_dump(mode="json"))
    assert persisted.content_hash == result.content_hash
    assert tuple(node.node_ref for node in persisted.leaf_nodes) == (child_refs[0],)

    pending_without_frontier = persisted.model_dump(mode="json")
    pending_without_frontier["frontier_node_refs"] = []
    pending_payload = {
        key: value for key, value in pending_without_frontier.items() if key != "content_hash"
    }
    pending_without_frontier["content_hash"] = gy_content_hash(pending_payload)
    with pytest.raises(
        ValidationError,
        match="recursive_partial_frontier_denominator_mismatch",
    ):
        RecursiveGenerationCyclePartialRunV2.model_validate(pending_without_frontier)

    fake_completed_sibling = persisted.model_dump(mode="json")
    sibling_index = next(
        index
        for index, node in enumerate(fake_completed_sibling["nodes"])
        if node["node_ref"] == child_refs[1]
    )
    fake_completed_sibling["nodes"][sibling_index] = {
        "node_ref": child_refs[1],
        "parent_ref": result.root_node_ref,
        "depth": 1,
        "child_refs": [],
        "design_problem_ref": by_ref[child_refs[1]].design_problem_ref,
        "cycle_run": None,
        "terminal": budget_child.terminal.model_dump(mode="json"),
    }
    fake_completed_payload = {
        key: value for key, value in fake_completed_sibling.items() if key != "content_hash"
    }
    fake_completed_sibling["content_hash"] = gy_content_hash(fake_completed_payload)
    # This pre-existing RecursiveCycleNode parser rule rejects the zero-child
    # no-run leaf; this probe records inheritance, not a new V2 leaf fix.
    with pytest.raises(ValidationError, match="recursive_leaf_requires_generation_cycle"):
        RecursiveGenerationCyclePartialRunV2.model_validate(fake_completed_sibling)

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
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    )

    assert type(result) is RecursiveGenerationCycleRun
    persisted_v1 = RecursiveGenerationCycleRun.model_validate(result.model_dump(mode="json"))
    assert persisted_v1.model_dump_json() == result.model_dump_json()
    _assert_leaf_n9_observations_match_calls(result, factory)
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


@pytest.mark.asyncio
async def test_partial_v2_rejects_self_asserted_internal_parent_terminal() -> None:
    """A completed uncomposed parent can retain only a conservative blocked fold."""

    full_result, leaf_refs, _request, _full_factory = await _run_recursive_fixture(
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    )
    assert type(full_result) is RecursiveGenerationCycleRun
    full_nodes = {node.node_ref: node for node in full_result.nodes}

    internal_ref = "design://e02/recursive-budget/completed-parent"
    budget_node_ref = "design://e02/recursive-budget/budget-stopped-leaf"
    pending_node_ref = "design://e02/recursive-budget/pending-leaf"
    budget_problem = _recursive_problem(budget_node_ref)
    budget_problem_ref = gy_content_hash(budget_problem.model_dump(mode="json"))
    budget_factory = _CycleControllerFactory()
    budget_leaf_controller = budget_factory(budget_node_ref, budget_problem)
    budget_cycle_run: GenerationCycleRun = await budget_leaf_controller.run(
        budget_problem,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))}),
        min_cycles=1,
        max_cycles=1,
        stable_design_problem_ref=budget_problem_ref,
    )
    assert generation_cycle_terminal_state(budget_cycle_run).kind is (
        SearchTerminalKind.BUDGET_EXHAUSTED
    )
    assert len(budget_factory.promotion_calls) <= 1
    assert bool(budget_factory.promotion_calls) == (
        budget_cycle_run.promotion_port.status == "promotion_pending_n9"
    )

    root_problem = _recursive_problem(full_result.root_node_ref)
    root_problem_ref = gy_content_hash(root_problem.model_dump(mode="json"))
    internal_problem = _recursive_problem(internal_ref)
    internal_problem_ref = gy_content_hash(internal_problem.model_dump(mode="json"))
    pending_problem = _recursive_problem(pending_node_ref)
    pending_problem_ref = gy_content_hash(pending_problem.model_dump(mode="json"))
    module_refs = (
        internal_ref,
        *leaf_refs,
        budget_node_ref,
        pending_node_ref,
    )
    graph = derive_recursive_design_graph(
        design_ref=full_result.root_node_ref,
        module_refs=module_refs,
        parent_child_edges=(
            (full_result.root_node_ref, internal_ref),
            (full_result.root_node_ref, budget_node_ref),
            (full_result.root_node_ref, pending_node_ref),
            (internal_ref, leaf_refs[0]),
            (internal_ref, leaf_refs[1]),
        ),
        typed_dependency_edges=(),
        rule_version_ref="repo://rules/e02-recursive-internal-parent-contract-test",
    )
    routed_leaves = tuple(
        full_nodes[leaf_ref].model_copy(update={"parent_ref": internal_ref, "depth": 2})
        for leaf_ref in leaf_refs
    )
    internal_parent = RecursiveCycleNode(
        node_ref=internal_ref,
        parent_ref=full_result.root_node_ref,
        depth=1,
        child_refs=leaf_refs,
        design_problem_ref=internal_problem_ref,
        # The code is a route-emitted diagnostic. V2 only preserves a blocked
        # shape here; it does not recompute the missing-subdesign predicate.
        terminal=full_nodes[full_result.root_node_ref].terminal,
    )
    budget_stop = RecursiveCycleNode(
        node_ref=budget_node_ref,
        parent_ref=full_result.root_node_ref,
        depth=1,
        design_problem_ref=budget_problem_ref,
        cycle_run=budget_cycle_run,
        terminal=generation_cycle_terminal_state(budget_cycle_run),
    )
    root_pending = RecursiveCyclePendingNode(
        node_ref=full_result.root_node_ref,
        parent_ref=None,
        depth=0,
        child_refs=(internal_ref, budget_node_ref, pending_node_ref),
        design_problem_ref=root_problem_ref,
    )
    frontier_pending = RecursiveCyclePendingNode(
        node_ref=pending_node_ref,
        parent_ref=full_result.root_node_ref,
        depth=1,
        design_problem_ref=pending_problem_ref,
    )
    nodes = (
        root_pending,
        internal_parent,
        *routed_leaves,
        budget_stop,
        frontier_pending,
    )
    recursive_budget = RecursiveCycleBudget(
        max_depth=2,
        max_nodes=len(graph.node_refs),
        min_cycles_per_leaf=1,
        max_cycles_per_leaf=1,
    )
    payload: dict[str, object] = {
        "schema_version": "policyos.runtime.recursive_generation_cycle.partial.v2",
        "run_id": f"recursive:{graph.graph_id}",
        "controller_ref": full_result.controller_ref,
        "authority_scope": full_result.authority_scope,
        "recursive_graph": graph.model_dump(mode="json"),
        "recursive_graph_ref": graph.graph_ref,
        "recursive_graph_content_hash": gy_content_hash(graph.model_dump(mode="json")),
        "root_node_ref": full_result.root_node_ref,
        "root_design_problem_ref": root_problem_ref,
        "recursive_budget": recursive_budget.model_dump(mode="json"),
        "observed_max_depth": 2,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "traversal_status": "budget_stopped",
        "traversal_stop_reason": "child_budget_exhausted",
        "budget_stop_node_ref": budget_node_ref,
        "frontier_node_refs": [pending_node_ref],
        "terminal": None,
    }
    checkpoint = RecursiveGenerationCyclePartialRunV2.model_validate(
        {
            **payload,
            "nodes": nodes,
            "content_hash": gy_content_hash(payload),
        }
    )
    assert checkpoint.leaf_nodes
    assert checkpoint.budget_stop_node_ref == budget_node_ref
    assert internal_parent.child_refs == leaf_refs
    assert internal_parent.cycle_run is None
    assert internal_parent.joint_simulation is None
    assert internal_parent.composition_certificate is None
    assert internal_parent.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED

    for forged_terminal, expected_error in (
        (
            routed_leaves[0].terminal.model_dump(mode="json"),
            "recursive_parent_not_conservatively_blocked",
        ),
        (
            {
                **internal_parent.terminal.model_dump(mode="json"),
                "budget_kind": "recursive",
            },
            "recursive_parent_terminal_not_owner_derived",
        ),
    ):
        forged = checkpoint.model_dump(mode="json")
        internal_index = next(
            index for index, node in enumerate(forged["nodes"]) if node["node_ref"] == internal_ref
        )
        forged["nodes"][internal_index]["terminal"] = forged_terminal
        forged_payload = {key: value for key, value in forged.items() if key != "content_hash"}
        forged["content_hash"] = gy_content_hash(forged_payload)
        with pytest.raises(ValidationError, match=expected_error):
            RecursiveGenerationCyclePartialRunV2.model_validate(forged)


@pytest.mark.asyncio
async def test_complete_uncomposed_parent_refuses_rehashed_positive_or_budget_terminal() -> None:
    """Original independent b6c3201 falsifier, applied to complete history.

    A content hash is integrity evidence; it cannot establish N5/composition
    authority absent from the artifact. Both complete and partial histories
    share the same conservative no-evidence parent invariant.
    """
    run, *_ = await _run_recursive_fixture(
        budget_state=BudgetState(limits={
            "run": BudgetLimit(key="run", max_usd=Decimal("5")),
        }),
    )
    assert type(run) is RecursiveGenerationCycleRun
    ordinary = run.model_dump(mode="json")
    root = next(row for row in ordinary["nodes"] if row["node_ref"] == run.root_node_ref)
    assert root["child_refs"]
    assert root["joint_simulation"] is None
    assert root["composition_certificate"] is None
    assert root["terminal"]["kind"] == SearchTerminalKind.RECURSIVE_BLOCKED.value
    assert RecursiveGenerationCycleRun.model_validate(ordinary).model_dump(mode="json") == ordinary
    for forged, expected_error in (
        (
            {
                **root["terminal"],
                "kind": SearchTerminalKind.GROUNDED_ADMISSIBLE.value,
                "reason": "Source-independent forged root outcome",
                "blocking_obligations": [],
                "budget_kind": None,
                "costed_plan": None,
                "data_need_spec": None,
            },
            "recursive_parent_not_conservatively_blocked",
        ),
        (
            {**root["terminal"], "budget_kind": "recursive"},
            "recursive_parent_terminal_not_owner_derived",
        ),
    ):
        payload = run.model_dump(mode="json")
        node = next(row for row in payload["nodes"] if row["node_ref"] == run.root_node_ref)
        node["terminal"] = forged
        payload["terminal"] = forged
        payload["content_hash"] = gy_content_hash({
            key: value for key, value in payload.items() if key != "content_hash"
        })
        with pytest.raises(ValidationError, match=expected_error):
            RecursiveGenerationCycleRun.model_validate(payload)
