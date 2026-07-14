"""Focused checks for the GY-N10 depth-N universality harness."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from decimal import Decimal
from importlib import import_module
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import tools.quality.validation.universality_preflight as universality_preflight_module
from tools.quality.validation.universality_preflight import (
    assert_universality_preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

# This assertion intentionally precedes every PolicyOS owner import. Fresh child processes below
# prove that a foreign checkout, base interpreter, or missing CG substrate cannot enter a proof
# producer through pytest's already-imported parent process.
assert_universality_preflight(REPO_ROOT)

from polisyos.pdc import (
    ArtifactRef,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    gy_content_hash,
)  # noqa: E402
from polisyos.runtime.quality.design_axes.coupling_composition import (
    build_coupling_graph,
    classify_coupling,
    derive_recursive_design_graph,
)  # noqa: E402
from polisyos.runtime.quality.design_problem import (  # noqa: E402
    DesignProblem,
    DesignProblemAuthorityError,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
)  # noqa: E402
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    intervention_atom_content_hash,
)  # noqa: E402
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
    RecursiveGenerationCycleError,
    RecursiveGenerationCycleRun,
    build_default_recursive_generation_cycle_controller,
    recompute_depth_n_strangle_receipt,
)  # noqa: E402
from polisyos.scientist.orchestration.engine.budget import (  # noqa: E402
    BudgetLimit,
    BudgetState,
)


def _recursive_problem(node_ref: str) -> DesignProblem:
    payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
        ).read_text(encoding="utf-8")
    )["design_problem"]
    problem = DesignProblem.model_validate(payload)
    return problem.model_copy(
        update={
            "design_problem_id": "recursive_" + node_ref.rsplit("/", 1)[-1],
            "objectives": [
                problem.objectives[0].model_copy(
                    update={"metric_id": "final_queue_length"}
                )
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


class _Lane0GenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> SimpleNamespace:
        del problem, cycle_index
        atom = SimpleNamespace(
            intervention_id="lane0_intervention",
            content_hash="sha256:" + "4" * 64,
            status="candidate_unverified",
            world_model_record_ref="world_model_record_lane0",
            target_world_slots=("final_queue_length",),
        )
        candidate = SimpleNamespace(
            candidate_id="candidate_lane0_recursive",
            atom=atom,
            diversity_key=("queue", "claims", "lane0", "baseline"),
            status="candidate_unverified",
        )
        ranking = SimpleNamespace(
            candidate_id=candidate.candidate_id,
            score=0.2,
            voi_estimate=0.1,
            trust_level="search_guiding",
            promotion_allowed=False,
        )
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(ranking,),
            grounding_dispositions=(),
        )


class _Lane0GroundingPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> CandidateGroundingObservation:
        del kwargs
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2,
            issue_codes=("lane0_grounding_gap",),
            current_valid=False,
        )


class _Lane0SimulationPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> SimulationPortObservation:
        del kwargs
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="simulation_pending_n5",
            authority_blockers=("lane0_joint_request_not_leaf_owned",),
        )


class _Lane0PromotionPort:
    def __call__(self, **kwargs: Any) -> PromotionPortObservation:
        del kwargs
        return PromotionPortObservation()


def _lane0_cycle_controller_factory(
    node_ref: str,
    problem: DesignProblem,
) -> GenerationCycleController:
    del node_ref, problem
    return GenerationCycleController(
        generation_port=_Lane0GenerationPort(),
        grounding_port=_Lane0GroundingPort(),
        simulation_port=_Lane0SimulationPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_Lane0PromotionPort(),
        repo_root=REPO_ROOT,
    )


def _lane0_leaf_terminal() -> SearchTerminalState:
    return SearchTerminalState(
        kind=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=["lane0_grounding_gap", "value_gate_pending_n8"],
    )


def _recursive_budget_state() -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
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
            )
        }
    )


def _lane0_subdesigns(
    *,
    parent_ref: str,
    child_refs: tuple[str, str],
) -> tuple[SubDesignContract, ...]:
    module = import_module(
        "tools.quality.validation.check_layer3_gy_composition_artifacts"
    )
    factory = cast("Any", module)._synthetic_composition_subdesigns
    originals = factory(artifact_ref_factory=ArtifactRef.from_payload)
    return tuple(
        child.model_copy(
            update={
                "workspace_id": child_ref,
                "parent_workspace_id": parent_ref,
                "search_exit": child.search_exit.model_copy(
                    update={
                        "workspace_id": child_ref,
                        "terminal_state": _lane0_leaf_terminal(),
                    }
                ),
            }
        )
        for child, child_ref in zip(originals, child_refs, strict=True)
    )


def test_missing_coupling_evidence_defaults_toward_entanglement() -> None:
    graph = build_coupling_graph(
        design_ref="design://missing-coupling/root",
        module_refs=("module://a", "module://b"),
        module_discovery_ref=None,
        interaction_edges=(),
        rule_version_ref="repo://rules/gy-n10",
    )

    classification = classify_coupling(graph)

    assert graph.evidence_state == "absent"
    assert classification.defaulted_to_more_coupling is True
    assert classification.coupling_regime != "modular"
    observed_but_empty = graph.model_copy(
        update={
            "evidence_state": "observed",
            "module_discovery_ref": "discovery://empty-boundary",
        }
    )
    empty_classification = classify_coupling(observed_but_empty)
    assert empty_classification.defaulted_to_more_coupling is True, (
        "empty_coupling_without_observed_boundary_must_default_entangled"
    )
    assert empty_classification.coupling_regime != "modular"


@pytest.mark.asyncio
async def test_coupled_parent_runs_real_n5_and_records_interactions() -> None:
    root = "design://coupled/root"
    child_refs = ("design://coupled/a", "design://coupled/b")
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/gy-n10-coupled",
    )
    problems = {
        node_ref: _recursive_problem(node_ref)
        for node_ref in (root, *child_refs)
    }
    request = _lane0_coupled_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=problems[root],
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    result = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
        joint_simulation_requests_by_node={root: request},
        subdesign_contracts_by_node={
            root: _lane0_subdesigns(parent_ref=root, child_refs=child_refs)
        },
    )

    assert result.joint_simulation_receipts
    assert result.joint_simulation_receipts[0].trajectory_count > 0
    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert root_node.joint_simulation is not None
    assert root_node.joint_simulation.interaction_terms
    assert (
        root_node.joint_simulation.world_credal_state_before
        == root_node.joint_simulation.world_credal_state_after
    )
    assert root_node.composition_certificate is not None
    assert root_node.composition_certificate.claim_refs
    assert root_node.composition_certificate.target_policy_program_ref == root
    assert root_node.composition_certificate.emergent_claims == []
    assert root_node.composition_certificate.coupling_gate.invalid_reason == (
        "shared_resource_requires_capacity_aggregation"
    )
    assert result.authority_scope == "contract_testing"

    missing_n5 = result.model_dump(mode="json")
    missing_n5_root = next(
        node for node in missing_n5["nodes"] if node["node_ref"] == root
    )
    missing_n5_root["joint_simulation"] = None
    missing_n5_content = {
        key: value for key, value in missing_n5.items() if key != "content_hash"
    }
    missing_n5["content_hash"] = gy_content_hash(missing_n5_content)
    with pytest.raises(
        ValueError,
        match="recursive_composition_requires_joint_simulation",
    ):
        RecursiveGenerationCycleRun.model_validate(missing_n5)

    missing_certificate = result.model_dump(mode="json")
    missing_certificate_root = next(
        node for node in missing_certificate["nodes"] if node["node_ref"] == root
    )
    missing_certificate_root["composition_certificate"] = None
    missing_certificate_content = {
        key: value
        for key, value in missing_certificate.items()
        if key != "content_hash"
    }
    missing_certificate["content_hash"] = gy_content_hash(
        missing_certificate_content
    )
    with pytest.raises(
        ValueError,
        match="recursive_supported_n5_requires_composition",
    ):
        RecursiveGenerationCycleRun.model_validate(missing_certificate)

    cross_parent = result.model_dump(mode="json")
    cross_parent_root = next(
        node for node in cross_parent["nodes"] if node["node_ref"] == root
    )
    cross_parent_root["composition_certificate"]["parent_workspace_id"] = (
        "design://another-parent"
    )
    cross_parent_content = {
        key: value for key, value in cross_parent.items() if key != "content_hash"
    }
    cross_parent["content_hash"] = gy_content_hash(cross_parent_content)
    with pytest.raises(
        ValueError,
        match="recursive_composition_parent_binding_mismatch",
    ):
        RecursiveGenerationCycleRun.model_validate(cross_parent)


@pytest.mark.asyncio
async def test_cross_branch_n5_evidence_is_refused_before_owner_run() -> None:
    root = "design://binding/root"
    child_refs = ("design://binding/a", "design://binding/b")
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/gy-n10-binding",
    )
    problems = {
        node_ref: _recursive_problem(node_ref) for node_ref in (root, *child_refs)
    }
    transplanted = _lane0_coupled_request(
        parent_ref="design://another-world/root",
        child_refs=child_refs,
        problem=problems[root],
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    result = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
        joint_simulation_requests_by_node={root: transplanted},
        subdesign_contracts_by_node={
            root: _lane0_subdesigns(parent_ref=root, child_refs=child_refs)
        },
    )

    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert root_node.joint_simulation is None
    assert root_node.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root_node.terminal.blocking_obligations == [
        "recursive_coupling_design_ref_mismatch"
    ]


@pytest.mark.asyncio
async def test_missing_subdesign_denominator_refuses_before_n5() -> None:
    root = "design://missing-subdesign/root"
    child_refs = (
        "design://missing-subdesign/a",
        "design://missing-subdesign/b",
    )
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/gy-n10-missing-subdesign",
    )
    problems = {
        node_ref: _recursive_problem(node_ref) for node_ref in (root, *child_refs)
    }
    request = _lane0_coupled_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=problems[root],
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    result = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
        joint_simulation_requests_by_node={root: request},
        subdesign_contracts_by_node={root: ()},
    )

    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert root_node.joint_simulation is None
    assert root_node.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root_node.terminal.blocking_obligations == [
        "subdesign_contract_denominator_missing"
    ]


@pytest.mark.asyncio
async def test_contract_testing_leaf_cannot_drop_verified_substrate_context() -> None:
    second_domain_pack = import_module(
        "tools.quality.validation.check_layer3_gy_second_domain_pack"
    )
    bundle = cast("Any", second_domain_pack)._load_frozen_bundle(REPO_ROOT)
    problem = DesignProblem.model_validate(bundle["smoke_problem"]["design_problem"])
    context = cast("Any", second_domain_pack)._build_frozen_cycle_substrate_context(
        REPO_ROOT,
        bundle=bundle,
        design_problem=problem,
    )
    root = "design://context/root"
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="repo://rules/gy-n10-context",
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    with pytest.raises(
        RecursiveGenerationCycleError,
        match="recursive_contract_testing_context_not_consumed",
    ):
        await controller.run(
            graph,
            problems_by_node={root: problem},
            budget_state=_recursive_budget_state(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=2,
            ),
            cycle_substrate_contexts_by_node={root: context},
        )


@pytest.mark.asyncio
async def test_unsupported_n5_coupling_folds_to_typed_recursive_block() -> None:
    root = "design://unsupported/root"
    child_refs = ("design://unsupported/a", "design://unsupported/b")
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/gy-n10-unsupported",
    )
    problems = {
        node_ref: _recursive_problem(node_ref) for node_ref in (root, *child_refs)
    }
    request = _lane0_coupled_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=problems[root],
    )
    n5_contract = import_module(
        "tools.quality.validation.check_layer3_gy_joint_simulation_horizon_contract"
    )
    unsupported = request.model_copy(
        update={"engine_plan": cast("Any", n5_contract)._request().engine_plan}
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    result = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=1,
            max_nodes=3,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
        joint_simulation_requests_by_node={root: unsupported},
        subdesign_contracts_by_node={
            root: _lane0_subdesigns(parent_ref=root, child_refs=child_refs)
        },
    )

    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert root_node.joint_simulation is not None
    assert root_node.joint_simulation.receipt.calibration_status == (
        "unsupported_coupling_gated"
    )
    assert not root_node.joint_simulation.trajectories
    assert root_node.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root_node.terminal.blocking_obligations == [
        "unsupported_coupling_gated"
    ]


def test_gy_g_strangle_receipt_has_no_production_fixture_callers() -> None:
    receipt = recompute_depth_n_strangle_receipt(REPO_ROOT)

    assert receipt.status == "strangled"
    assert receipt.production_fixture_callers == ()
    assert receipt.production_default_routes
    assert receipt.default_controller.endswith("RecursiveGenerationCycleController")


def test_default_recursive_router_carries_selected_model_to_leaf_owner() -> None:
    controller = build_default_recursive_generation_cycle_controller(
        repo_root=REPO_ROOT,
        model_id="registry-selected-model",
    )

    assert controller._leaf_model_id == "registry-selected-model"


@pytest.mark.asyncio
async def test_recursive_router_executes_observed_depth_above_two() -> None:
    root = "design://depth/root"
    node_refs = (
        root,
        "design://depth/one",
        "design://depth/two",
        "design://depth/three",
    )
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=node_refs[1:],
        parent_child_edges=tuple(pairwise(node_refs)),
        rule_version_ref="repo://rules/gy-n10-depth",
    )
    problems = {node_ref: _recursive_problem(node_ref) for node_ref in node_refs}
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )

    result = await controller.run(
        graph,
        problems_by_node=problems,
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=3,
            max_nodes=4,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
    )

    assert result.observed_max_depth == 3
    assert {node.depth for node in result.nodes} == {0, 1, 2, 3}
    assert len(result.leaf_nodes) == 1
    assert all(node.cycle_run is not None and node.cycle_run.cycles for node in result.leaf_nodes)
    assert all(
        node.cycle_run.controller_ref.endswith("GenerationCycleController")
        for node in result.leaf_nodes
        if node.cycle_run is not None
    )
    assert result.root_design_problem_ref == gy_content_hash(
        problems[root].model_dump(mode="json")
    )
    payload = result.model_dump(mode="json")
    payload["terminal"] = SearchTerminalState(
        kind=SearchTerminalKind.GROUNDED_ADMISSIBLE,
        reason="Fabricated positive root terminal.",
    ).model_dump(mode="json")
    content_payload = {key: value for key, value in payload.items() if key != "content_hash"}
    payload["content_hash"] = gy_content_hash(content_payload)
    with pytest.raises(ValueError, match="recursive_run_terminal_not_root_derived"):
        RecursiveGenerationCycleRun.model_validate(payload)

    graph_tamper = result.model_dump(mode="json")
    graph_tamper["recursive_graph_ref"] = "pdc://fabricated/recursive-graph"
    graph_tamper["recursive_graph_content_hash"] = "sha256:" + "0" * 64
    graph_tamper_payload = {
        key: value for key, value in graph_tamper.items() if key != "content_hash"
    }
    graph_tamper["content_hash"] = gy_content_hash(graph_tamper_payload)
    with pytest.raises(ValueError, match="recursive_run_graph_binding_mismatch"):
        RecursiveGenerationCycleRun.model_validate(graph_tamper)

    leaf_terminal_tamper = result.model_dump(mode="json")
    leaf = next(node for node in leaf_terminal_tamper["nodes"] if not node["child_refs"])
    leaf["terminal"] = SearchTerminalState(
        kind=SearchTerminalKind.GROUNDED_ADMISSIBLE,
        reason="Fabricated leaf terminal.",
    ).model_dump(mode="json")
    leaf_terminal_content = {
        key: value
        for key, value in leaf_terminal_tamper.items()
        if key != "content_hash"
    }
    leaf_terminal_tamper["content_hash"] = gy_content_hash(
        leaf_terminal_content
    )
    with pytest.raises(
        ValueError,
        match="recursive_run_leaf_terminal_not_owner_derived",
    ):
        RecursiveGenerationCycleRun.model_validate(leaf_terminal_tamper)


@pytest.mark.asyncio
async def test_recursive_content_hash_excludes_nested_operational_clocks() -> None:
    """Keep N7/generated-at and N8 wall times outside recursive semantic identity."""

    root = "design://clock/root"
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="repo://rules/gy-n10-clock",
    )
    problem = _recursive_problem(root)
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=REPO_ROOT,
    )
    result = await controller.run(
        graph,
        problems_by_node={root: problem},
        budget_state=_recursive_budget_state(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
    )
    payload = result.model_dump(mode="json")
    cycle_run = payload["nodes"][0]["cycle_run"]
    cycle_run["value_port"]["wall_time_ms"] = 9876.5
    cycle_run["cycles"][0]["value_port"]["wall_time_ms"] = 9876.5

    replayed = RecursiveGenerationCycleRun.model_validate(payload)

    assert replayed.content_hash == result.content_hash


def _create_wrong_checkout_package(tmp_path: Path) -> Path:
    """Create a standalone adversarial ``polisyos`` package and return its source root."""

    wrong_src = (tmp_path / "wrong-checkout" / "policy-engine" / "src").resolve()
    package_root = wrong_src / "polisyos"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text(
        '"""Standalone wrong-checkout sentinel package."""\n',
        encoding="utf-8",
    )
    return wrong_src


def _run_universality_preflight_with_pythonpath(
    pythonpath: Path,
    *,
    producer_sentinel: Path,
    block_ortools: bool = False,
    python_executable: str = sys.executable,
    force_base_prefixes: bool = False,
    force_base_exec_prefix: bool = False,
    force_repository_base_prefix: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the universality preflight before a sentinel validator producer."""

    script = f"""
import sys
from pathlib import Path

repo_root = Path({REPO_ROOT.as_posix()!r})
producer_sentinel = Path({producer_sentinel.as_posix()!r})

if {force_base_prefixes!r}:
    sys.prefix = sys.base_prefix
    sys.exec_prefix = sys.base_exec_prefix
if {force_base_exec_prefix!r}:
    sys.exec_prefix = sys.base_exec_prefix
if {force_repository_base_prefix!r}:
    sys.base_prefix = str((repo_root / ".venv").resolve())

from tools.quality.validation.universality_preflight import assert_universality_preflight

if {block_ortools!r}:
    class BlockOrtools:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "ortools" or fullname.startswith("ortools."):
                raise ModuleNotFoundError("blocked_by_n10_preflight_test")
            return None

    sys.meta_path.insert(0, BlockOrtools())

resolved_package_path, backend = assert_universality_preflight(repo_root)

def sentinel_validator_producer() -> None:
    producer_sentinel.write_text("producer_reached", encoding="utf-8")

sys.stdout.write(f"checkout_resolved:{{resolved_package_path}}\\n")
sys.stdout.write(f"cg_backend:{{backend.required_backend_status}}\\n")
sentinel_validator_producer()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath.as_posix()
    return subprocess.run(
        [python_executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_interpreter_accepts_current_repository_venv() -> None:
    """Accept the repository venv even when its interpreter binary resolves to the base."""

    expected_prefix = (REPO_ROOT / ".venv").resolve()

    assert (
        universality_preflight_module.assert_repository_interpreter(REPO_ROOT)
        == expected_prefix
    )


def test_fresh_checkout_harness_resolves_current_checkout(tmp_path: Path) -> None:
    """Prove checkout and required CG backend resolution in a fresh process."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
    )
    expected_package_path = (REPO_ROOT / "src/polisyos/__init__.py").resolve()

    assert result.returncode == 0
    assert result.stdout == (
        f"checkout_resolved:{expected_package_path}\n"
        "cg_backend:available\n"
    )
    assert producer_sentinel.read_text(encoding="utf-8") == "producer_reached"


def test_cg_substrate_unavailable_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject a missing owner-required CG backend before proof production."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        block_ortools=True,
    )

    assert result.returncode == 1
    assert (
        "cg_substrate_unavailable:ortools_cp_sat:ModuleNotFoundError"
        in result.stderr
    )
    assert not producer_sentinel.exists()


def test_bare_base_interpreter_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject the real base interpreter selected by ``sys._base_executable``."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        python_executable=sys._base_executable,
    )

    assert result.returncode == 1
    assert "wrong_interpreter_resolved:" in result.stderr
    assert f"expected_prefix={(REPO_ROOT / '.venv').resolve()}" in result.stderr
    assert "observed_prefix=" in result.stderr
    assert "sys_executable=" in result.stderr
    assert "base_prefix=" in result.stderr
    assert not producer_sentinel.exists()


def test_deterministic_wrong_prefix_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject base prefixes injected into an otherwise valid repository-venv child."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        force_base_prefixes=True,
    )

    assert result.returncode == 1
    assert "wrong_interpreter_resolved:" in result.stderr
    assert f"observed_prefix={Path(sys.base_prefix).resolve()}" in result.stderr
    assert f"expected_prefix={(REPO_ROOT / '.venv').resolve()}" in result.stderr
    assert not producer_sentinel.exists()


def test_wrong_exec_prefix_alone_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject a base exec prefix while the ordinary prefix remains repository-owned."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        force_base_exec_prefix=True,
    )
    expected_prefix = (REPO_ROOT / ".venv").resolve()

    assert result.returncode == 1
    assert "WrongInterpreterResolvedError: wrong_interpreter_resolved:" in result.stderr
    assert f"observed_prefix={expected_prefix}" in result.stderr
    assert f"observed_exec_prefix={Path(sys.base_exec_prefix).resolve()}" in result.stderr
    assert f"expected_prefix={expected_prefix}" in result.stderr
    assert not producer_sentinel.exists()


def test_repository_base_prefix_is_rejected_before_proof_execution(
    tmp_path: Path,
) -> None:
    """Reject a base prefix equal to the repository while both runtime prefixes remain valid."""

    producer_sentinel = tmp_path / "producer-reached"
    result = _run_universality_preflight_with_pythonpath(
        REPO_ROOT / "src",
        producer_sentinel=producer_sentinel,
        force_repository_base_prefix=True,
    )
    expected_prefix = (REPO_ROOT / ".venv").resolve()

    assert result.returncode == 1
    assert "WrongInterpreterResolvedError: wrong_interpreter_resolved:" in result.stderr
    assert f"observed_prefix={expected_prefix}" in result.stderr
    assert f"observed_exec_prefix={expected_prefix}" in result.stderr
    assert f"base_prefix={expected_prefix}" in result.stderr
    assert not producer_sentinel.exists()


def test_adversarial_checkout_package_is_independent_of_repository_ancestry(
    tmp_path: Path,
) -> None:
    """Create the adversarial package without deriving a checkout from repository parents."""

    simulated_repo_root = tmp_path / "normal-checkout/policy-engine"
    wrong_src = _create_wrong_checkout_package(tmp_path)

    assert wrong_src == (tmp_path / "wrong-checkout/policy-engine/src").resolve()
    assert not wrong_src.is_relative_to(simulated_repo_root)
    assert not wrong_src.is_relative_to(REPO_ROOT)


def test_wrong_checkout_is_rejected_before_proof_execution(tmp_path: Path) -> None:
    """Reject a standalone wrong checkout before its sentinel producer can execute."""

    producer_sentinel = tmp_path / "producer-reached"
    wrong_src = _create_wrong_checkout_package(tmp_path)
    result = _run_universality_preflight_with_pythonpath(
        wrong_src,
        producer_sentinel=producer_sentinel,
    )

    assert result.returncode == 1
    assert f"wrong_checkout_resolved:{wrong_src / 'polisyos/__init__.py'}" in result.stderr
    assert not producer_sentinel.exists()


def test_wrong_checkout_precedes_wrong_interpreter_prefix(tmp_path: Path) -> None:
    """Report checkout failure before inspecting an invalid interpreter prefix."""

    producer_sentinel = tmp_path / "producer-reached"
    wrong_src = _create_wrong_checkout_package(tmp_path)
    result = _run_universality_preflight_with_pythonpath(
        wrong_src,
        producer_sentinel=producer_sentinel,
        force_base_prefixes=True,
    )

    assert result.returncode == 1
    assert f"wrong_checkout_resolved:{wrong_src / 'polisyos/__init__.py'}" in result.stderr
    assert "wrong_interpreter_resolved:" not in result.stderr
    assert not producer_sentinel.exists()


def _universality_contract_validator() -> Any:
    """Import the Task-12 validator only after the universality preflight."""

    return import_module(
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract"
    )


def _run_universality_validator_with_pythonpath(
    pythonpath: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the real validator CLI with a caller-controlled PolicyOS package root."""

    validator_path = (
        REPO_ROOT
        / "tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((pythonpath.as_posix(), REPO_ROOT.as_posix()))
    return subprocess.run(
        [sys.executable, str(validator_path), *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_stage4_provenance_stability_binds_current_owner_graph() -> None:
    """Bind N4, Fork-B, N8, N10a, prompt, and composition owner evidence."""

    validator = _universality_contract_validator()
    report = validator.check_provenance_stability(REPO_ROOT)

    assert report["status"] == "stable"
    assert report["issues"] == []
    assert report["census_ref"]["n4_artifact_sha256"] == report["source_refs"][
        "n4_artifact_sha256"
    ]
    assert report["census_ref"]["content_hash"] == report["n8_fork_b_ref"][
        "content_hash"
    ]
    assert report["census_ref"]["raw_full_table_content_hash"] == report[
        "n8_fork_b_ref"
    ]["raw_full_table_content_hash"]
    assert report["first_vertical_refs"]["n8_design_problem_ref"] in report[
        "first_vertical_refs"
    ]["n4_generation_design_problem_refs"]
    assert report["first_vertical_refs"]["semantic_projection_hash"] == report[
        "first_vertical_refs"
    ]["n10a_comparator_hash"]
    assert len(set(report["design_problem_refs"].values())) == 1
    assert report["prompt_hashes"]["owner_projection"] == report["prompt_hashes"][
        "responses"
    ]
    assert report["prompt_hashes"]["owner_projection"] == report["prompt_hashes"][
        "journal"
    ]
    assert report["composition_ref"]["status"] == "bound"


def _complete_universality_payload() -> tuple[Any, dict[str, Any]]:
    """Re-derive the completed capstone from content-addressed owner recordings."""

    validator = _universality_contract_validator()
    return validator, validator.build_live_payload(REPO_ROOT, lane="cached")


_PLAIN_LANGUAGE_PROOF_REQUESTS = {
    "first_vertical": (
        "Design a policy to improve average household income and MSME survival in "
        "Ukraine under wartime fiscal constraints, considering a state-backed credit "
        "guarantee, and identify every evidence gap before recommendation."
    ),
    "education": (
        "Increase years of schooling and tertiary enrollment using evidence-backed "
        "teaching or learning interventions; do not assume that an education ministry "
        "can write to any simulation lever."
    ),
    "unseen": (
        "Reduce residential peak electricity demand and particulate emissions during "
        "heat waves without shifting costs onto low-income renters."
    ),
}


@pytest.mark.asyncio
async def test_compiler_recording_replays_through_canonical_owner_lane0() -> None:
    """Exercise the content-addressed compiler recorder without claiming proof authority."""

    validator = _universality_contract_validator()
    simulated = import_module(
        "polisyos.scientist.orchestration.llm.simulated_gateway"
    ).SimulatedGatewayLLMClient(
        model=validator.PROOF_MODEL_ID,
        supported_model_ids=(validator.PROOF_MODEL_ID,),
    )
    gateway = validator._RecordingGateway(simulated)
    span_gateway = validator._RecordingGateway(
        import_module(
            "polisyos.scientist.orchestration.llm.simulated_gateway"
        ).SimulatedGatewayLLMClient(
            model=validator.PROOF_MODEL_ID,
            supported_model_ids=(validator.PROOF_MODEL_ID,),
        )
    )
    problem, recording = await validator._capture_compiler_recording(
        role="unseen",
        raw_request=_PLAIN_LANGUAGE_PROOF_REQUESTS["unseen"],
        model_id=validator.PROOF_MODEL_ID,
        gateway=gateway,
        span_gateway=span_gateway,
    )

    replayed = await validator._replay_compiler_recording(recording)

    assert replayed == problem
    assert recording["recording_source"] == (
        "live_gateway_canonical_design_problem_compiler"
    )
    assert recording["calls"]
    assert recording["calls"][0]["response"]["tool_calls"][0]["name"] == (
        "emit_design_problem"
    )
    tampered = json.loads(json.dumps(recording))
    tampered["calls"][0]["request_content_hash"] = "sha256:" + "0" * 64
    stable = {
        key: value
        for key, value in tampered.items()
        if key != "recording_content_hash"
    }
    tampered["recording_content_hash"] = validator._semantic_hash(stable)
    with pytest.raises(
        validator.UniversalityContractError,
        match="compiler_recording_request_drift",
    ):
        await validator._replay_compiler_recording(tampered)


@pytest.mark.asyncio
async def test_characterization_gateway_varies_only_request_parameters() -> None:
    """Characterization may alter the request but must return provider bytes unchanged."""

    validator = _universality_contract_validator()
    sentinel = object()

    class _Inner:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
            del timeout
            return ["MiniMaxAI/MiniMax-M2.7"]

        async def generate(self, **kwargs: Any) -> object:
            self.calls.append(kwargs)
            return sentinel

    inner = _Inner()
    gateway = validator._CompilerCharacterizationGateway(
        inner,
        request_parameters={
            "max_tokens": 16384,
            "reasoning_split": True,
            "seed": 42,
        },
        system_suffix=(
            "Do not strengthen cited source meaning with unstated consequences."
        ),
    )

    assert await gateway.list_model_ids(timeout=1.0) == ["MiniMaxAI/MiniMax-M2.7"]
    observed = await gateway.generate(
        system="unchanged-system",
        user="unchanged-user",
        temperature=0.0,
    )

    assert observed is sentinel
    assert inner.calls == [
        {
            "system": (
                "unchanged-system\n\n"
                "Do not strengthen cited source meaning with unstated consequences."
            ),
            "user": "unchanged-user",
            "temperature": 0.0,
            "max_tokens": 16384,
            "reasoning_split": True,
            "seed": 42,
        }
    ]


def test_structured_capability_matrix_is_finite_and_carrier_complete() -> None:
    """Capability probing distinguishes constrained carriers from schema-shaped claims."""

    validator = _universality_contract_validator()
    rows = list(validator.STRUCTURED_COMPILER_CAPABILITY_MATRIX)

    assert len(rows) == 10
    assert {row["model_id"] for row in rows} == {
        "moonshotai/Kimi-K2.6",
        "MiniMaxAI/MiniMax-M2.7",
    }
    assert {row["mode"] for row in rows} == {
        "loose_tool",
        "strict_tool",
        "response_format_json_schema",
        "response_format_json_schema_with_tool",
        "structured_outputs_json_with_tool",
    }
    assert len({row["probe_id"] for row in rows}) == len(rows)
    assert not any(
        key in {"role", "domain", "jurisdiction"}
        for row in rows
        for key in row
    )


def test_structured_capability_request_uses_provider_native_controls_only() -> None:
    """Every variant changes the provider request and never installs a response carrier shim."""

    validator = _universality_contract_validator()

    strict_tool = validator._structured_capability_request("strict_tool")
    combined = validator._structured_capability_request(
        "response_format_json_schema_with_tool"
    )
    native = validator._structured_capability_request(
        "structured_outputs_json_with_tool"
    )

    assert strict_tool["tools"][0]["function"]["strict"] is True
    assert "response_format" not in strict_tool
    assert combined["response_format"]["type"] == "json_schema"
    assert combined["tools"][0]["function"]["name"] == "emit_conformance_probe"
    assert native["structured_outputs"] == {
        "json": validator.STRUCTURED_CAPABILITY_SCHEMA
    }
    assert native["tool_choice"] == {
        "type": "function",
        "function": {"name": "emit_conformance_probe"},
    }


def test_structured_capability_classifier_requires_real_tool_carrier() -> None:
    """Content JSON and response-format fallback cannot masquerade as tool conformance."""

    validator = _universality_contract_validator()
    valid = {
        "probe": "policyos",
        "time_semantics": {
            "frequency": "Q",
            "start_date": "2026-07-14",
            "step_count": 1,
        },
    }
    tool_response = SimpleNamespace(
        content="",
        raw={"choices": [{"finish_reason": "tool_calls"}]},
        tool_calls=[
            SimpleNamespace(
                name="emit_conformance_probe",
                arguments=valid,
                error_envelope=None,
            )
        ],
    )
    content_response = SimpleNamespace(
        content=json.dumps(valid),
        raw={"choices": [{"finish_reason": "stop"}]},
        tool_calls=[],
    )
    degraded_response = SimpleNamespace(
        content="",
        raw={
            "choices": [{"finish_reason": "tool_calls"}],
            "_gateway_degraded_events": [
                {"reason": "response_format_unsupported_retry_plain_json"}
            ],
        },
        tool_calls=tool_response.tool_calls,
    )

    assert validator._classify_structured_capability_response(tool_response) == {
        "carrier_kind": "tool_arguments",
        "constraint_status": "pass",
        "usable_for_compiler": True,
        "degraded_reasons": [],
    }
    assert validator._classify_structured_capability_response(content_response) == {
        "carrier_kind": "assistant_content",
        "constraint_status": "pass",
        "usable_for_compiler": False,
        "degraded_reasons": [],
    }
    assert validator._classify_structured_capability_response(degraded_response) == {
        "carrier_kind": "tool_arguments",
        "constraint_status": "response_format_degraded",
        "usable_for_compiler": False,
        "degraded_reasons": ["response_format_unsupported_retry_plain_json"],
    }


@pytest.mark.asyncio
async def test_characterization_overlay_applies_full_provider_schema_to_request() -> None:
    """Full-schema characterization changes only request controls and preserves the response."""

    validator = _universality_contract_validator()
    sentinel = SimpleNamespace(raw={}, tool_calls=[], content="")

    class _Inner:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def generate(self, **kwargs: Any) -> object:
            self.calls.append(kwargs)
            return sentinel

    inner = _Inner()
    gateway = validator._CompilerCharacterizationGateway(
        inner,
        request_parameters={"max_tokens": 8192, "seed": 1},
        provider_schema_mode="response_format_json_schema_with_tool",
    )
    response = await gateway.generate(
        system="canonical-system",
        user="canonical-user",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "emit_design_problem",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_choice={
            "type": "function",
            "function": {"name": "emit_design_problem"},
        },
        temperature=0.0,
    )

    assert response is sentinel
    request = inner.calls[0]
    provider_schema = request["tools"][0]["function"]["parameters"]
    assert request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "policyos_design_problem",
            "strict": True,
            "schema": provider_schema,
        },
    }
    time_object = provider_schema["properties"]["jurisdiction_time"]["properties"][
        "time_semantics"
    ]["anyOf"][0]
    assert time_object["anyOf"] == [
        {
            "required": ["step_count"],
            "properties": {"step_count": {"type": "integer", "minimum": 1}},
        },
        {
            "required": ["end_date"],
            "properties": {"end_date": {"type": "string", "minLength": 1}},
        },
    ]


@pytest.mark.asyncio
async def test_characterization_overlay_refuses_response_format_fallback() -> None:
    """A provider retry without response_format is measured as refusal, never conformance."""

    validator = _universality_contract_validator()

    class _Inner:
        async def generate(self, **kwargs: Any) -> object:
            del kwargs
            return SimpleNamespace(
                raw={
                    "_gateway_degraded_events": [
                        {"reason": "response_format_unsupported_retry_plain_json"}
                    ]
                }
            )

    gateway = validator._CompilerCharacterizationGateway(
        _Inner(),
        request_parameters={"max_tokens": 8192},
        provider_schema_mode="response_format_json_schema_with_tool",
    )

    with pytest.raises(
        validator.UniversalityContractError,
        match="compiler_structured_output_degraded",
    ):
        await gateway.generate(
            system="canonical-system",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "emit_design_problem",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        )


def test_characterization_matrix_is_finite_and_domain_agnostic() -> None:
    """The sweep spans supported models/controls without domain-keyed behavior."""

    validator = _universality_contract_validator()
    rows = list(validator.COMPILER_CHARACTERIZATION_MATRIX)

    assert len(rows) == 21
    assert {row["model_id"] for row in rows} == {
        "moonshotai/Kimi-K2.6",
        "MiniMaxAI/MiniMax-M2.7",
    }
    assert {row["request_parameters"]["max_tokens"] for row in rows} == {
        8192,
        16384,
        32768,
    }
    assert sum(
        row["request_parameters"].get("reasoning_split") is True for row in rows
    ) == 6
    assert {row["prompt_variant"] for row in rows} == {
        "generic_collection_invariant_v1",
        "source_semantics_non_strengthening_v1",
        "optional_structure_completeness_v1",
    }
    seeded = [
        row
        for row in rows
        if row["prompt_variant"] == "optional_structure_completeness_v1"
    ]
    assert {row["request_parameters"]["seed"] for row in seeded} == {0, 1, 42}
    assert {row["confirmation_repetitions"] for row in seeded} == {2}
    assert not any(
        key in {"role", "domain", "jurisdiction"}
        for row in rows
        for key in row["request_parameters"]
    )


def test_compiler_recording_preserves_provider_finish_reason() -> None:
    """Replay must retain the provider evidence used by the truncation fence."""

    validator = _universality_contract_validator()
    gateway_module = import_module(
        "polisyos.scientist.orchestration.llm.gateway_client"
    )
    response = gateway_module.GatewayLLMResponse(
        content="",
        model="moonshotai/Kimi-K2.6",
        provider="test",
        raw={"choices": [{"finish_reason": "length"}]},
        tool_calls=[],
    )

    normalized = validator._normalized_gateway_response(response)
    replayed = validator._gateway_response_from_payload(normalized)

    assert normalized["finish_reason"] == "length"
    assert replayed.raw == {"choices": [{"finish_reason": "length"}]}


def test_compiler_characterization_classifies_without_cleaning_output() -> None:
    """Classification observes strict-owner evidence; it never repairs a response."""

    validator = _universality_contract_validator()
    reasoning_wrapped = {
        "finish_reason": "tool_calls",
        "tool_calls": [
            {
                "name": "emit_design_problem",
                "arguments": {},
                "error_envelope": {
                    "reason": "tool_call_arguments_parse_error",
                    "details": {"arguments_preview": "<think>derive fields first"},
                },
            }
        ],
    }

    assert validator._classify_compiler_characterization_outcome(
        error_code=None,
        response_payload={"finish_reason": "tool_calls", "tool_calls": []},
    ) == "clean_complete_schema_valid_entailment_pass"
    assert validator._classify_compiler_characterization_outcome(
        error_code="design_problem_output_truncated",
        response_payload={"finish_reason": "length", "tool_calls": []},
    ) == "truncated"
    assert validator._classify_compiler_characterization_outcome(
        error_code="design_problem_validation_failed",
        response_payload=reasoning_wrapped,
    ) == "reasoning_wrapped"
    assert validator._classify_compiler_characterization_outcome(
        error_code="design_problem_validation_failed",
        response_payload={"finish_reason": "tool_calls", "tool_calls": []},
    ) == "schema_invalid"
    assert validator._classify_compiler_characterization_outcome(
        error_code="gateway_http_error",
        response_payload={},
    ) == "provider_refused"


@pytest.mark.asyncio
async def test_characterization_reuses_completed_matrix_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restarting characterization may spend only rows absent from the local journal."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", Path("capture"))
    matrix = (
        {
            "probe_id": "already-measured",
            "model_id": "model-a",
            "prompt_variant": "generic_collection_invariant_v1",
            "system_suffix": None,
            "request_parameters": {"max_tokens": 8192},
        },
        {
            "probe_id": "new-row",
            "model_id": "model-b",
            "prompt_variant": "generic_collection_invariant_v1",
            "system_suffix": None,
            "request_parameters": {"max_tokens": 16384},
        },
    )
    monkeypatch.setattr(validator, "COMPILER_CHARACTERIZATION_MATRIX", matrix)
    journal = tmp_path / "capture" / "characterization.jsonl"
    journal.parent.mkdir(parents=True)
    prior = {
        "event": "compiler_characterization_probe_completed",
        "phase": "matrix",
        "probe_id": "already-measured",
        "model_id": "model-a",
        "prompt_variant": "generic_collection_invariant_v1",
        "request_parameters": {"max_tokens": 8192},
        "outcome": "schema_invalid",
    }
    journal.write_text(json.dumps(prior) + "\n", encoding="utf-8")
    spent: list[str] = []

    async def _probe(
        repo_root: Path,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        spent.append(str(kwargs["probe_id"]))
        return {
            "event": "compiler_characterization_probe_completed",
            "phase": "matrix",
            "probe_id": kwargs["probe_id"],
            "model_id": kwargs["model_id"],
            "prompt_variant": kwargs["prompt_variant"],
            "request_parameters": kwargs["request_parameters"],
            "outcome": "schema_invalid",
        }

    monkeypatch.setattr(validator, "_characterize_compiler_probe", _probe)

    report = await validator._characterize_compiler_conformance(tmp_path)

    assert report["status"] == "fail"
    assert spent == ["new-row"]
    assert {row["probe_id"] for row in report["rows"]} == {
        "already-measured",
        "new-row",
    }


@pytest.mark.parametrize(("stable", "expected_status"), [(True, "pass"), (False, "fail")])
@pytest.mark.asyncio
async def test_characterization_requires_repeated_stable_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stable: bool,
    expected_status: str,
) -> None:
    """One clean response cannot select a config whose repeated carrier drifts."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", Path("capture"))
    matrix = (
        {
            "probe_id": "seeded-candidate",
            "model_id": "model-a",
            "prompt_variant": "optional_structure_completeness_v1",
            "request_parameters": {"max_tokens": 8192, "seed": 42},
            "confirmation_repetitions": 2,
        },
    )
    monkeypatch.setattr(validator, "COMPILER_CHARACTERIZATION_MATRIX", matrix)
    monkeypatch.setattr(validator, "_SUPERSEDED_CHARACTERIZATION_PROBE_IDS", frozenset())

    async def _probe(
        repo_root: Path,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        probe_id = str(kwargs["probe_id"])
        role = str(kwargs["role"])
        repetition = probe_id.rpartition("-r")[2]
        response_hash = f"sha256:{role}-stable"
        if not stable and role == "unseen" and repetition == "2":
            response_hash = "sha256:unseen-drift"
        return {
            "event": "compiler_characterization_probe_completed",
            "phase": kwargs["phase"],
            "probe_id": probe_id,
            "role": role,
            "model_id": kwargs["model_id"],
            "prompt_variant": kwargs["prompt_variant"],
            "request_parameters": kwargs["request_parameters"],
            "outcome": "clean_complete_schema_valid_entailment_pass",
            "completion_tokens": 5000,
            "response_content_hash": response_hash,
        }

    monkeypatch.setattr(validator, "_characterize_compiler_probe", _probe)
    monkeypatch.setattr(
        validator,
        "_characterization_system_suffix",
        lambda _variant: "generic optional completeness",
    )

    report = await validator._characterize_compiler_conformance(tmp_path)

    assert report["status"] == expected_status
    if stable:
        assert report["winning_config"]["confirmation_repetitions"] == 2
    else:
        assert report["winning_config"] is None


@pytest.mark.asyncio
async def test_structured_conformance_prunes_degraded_mode_then_proves_all_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deterministic carrier refusal is measured once; a viable mode proves every seed/role."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", Path("capture"))
    calls: list[dict[str, Any]] = []

    async def _probe(repo_root: Path, **kwargs: Any) -> dict[str, Any]:
        assert repo_root == tmp_path
        calls.append(dict(kwargs))
        mode = str(kwargs["provider_schema_mode"])
        role = str(kwargs["role"])
        seed = int(kwargs["request_parameters"]["seed"])
        if mode == "response_format_json_schema_with_tool":
            return {
                "event": "compiler_characterization_probe_completed",
                "probe_id": kwargs["probe_id"],
                "role": role,
                "model_id": kwargs["model_id"],
                "prompt_variant": kwargs["prompt_variant"],
                "provider_schema_mode": mode,
                "request_parameters": kwargs["request_parameters"],
                "outcome": "schema_invalid",
                "error_code": "compiler_structured_output_degraded",
                "response_content_hash": "sha256:degraded",
            }
        return {
            "event": "compiler_characterization_probe_completed",
            "probe_id": kwargs["probe_id"],
            "role": role,
            "model_id": kwargs["model_id"],
            "prompt_variant": kwargs["prompt_variant"],
            "provider_schema_mode": mode,
            "request_parameters": kwargs["request_parameters"],
            "outcome": "clean_complete_schema_valid_entailment_pass",
            "error_code": None,
            "completion_tokens": 5000,
            "response_content_hash": f"sha256:{mode}:{role}:{seed}",
        }

    monkeypatch.setattr(validator, "_characterize_compiler_probe", _probe)

    report = await validator._characterize_structured_compiler_conformance(tmp_path)

    assert report["status"] == "pass"
    assert report["winning_config"]["role_modes"] == dict.fromkeys(
        validator.PLAIN_LANGUAGE_PROOF_REQUESTS,
        "provider_tool_schema",
    )
    assert report["winning_config"]["selection_scope"] == "universal"
    assert report["winning_config"]["mode"] == "provider_tool_schema"
    assert sum(
        call["provider_schema_mode"]
        == "response_format_json_schema_with_tool"
        for call in calls
    ) == 1
    assert sum(
        call["provider_schema_mode"] == "provider_tool_schema"
        for call in calls
    ) == 18


def test_span_capture_uses_fresh_client_inside_each_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent an aiohttp session created by the compiler loop entering verifier loops."""

    validator = _universality_contract_validator()
    gateway_module = import_module(
        "polisyos.scientist.orchestration.llm.gateway_client"
    )
    factory_module = import_module(
        "polisyos.scientist.orchestration.llm.factory"
    )
    clients: list[Any] = []

    class _LoopBoundClient:
        def __init__(self) -> None:
            self.loop = asyncio.get_running_loop()
            self.closed = False

        async def generate(self, **kwargs: Any) -> Any:
            del kwargs
            assert asyncio.get_running_loop() is self.loop
            return gateway_module.GatewayLLMResponse(
                content="",
                model="loop-bound-span-model",
                provider="test",
                tool_calls=[
                    gateway_module.GatewayToolCall(
                        id="span",
                        name="layer3_gy_record_span_support_judgment",
                        arguments={
                            "decision": "entails",
                            "confidence": 0.95,
                            "rationale": "loop-bound test",
                        },
                    )
                ],
            )

        async def aclose(self) -> None:
            assert asyncio.get_running_loop() is self.loop
            self.closed = True

    def _factory(**kwargs: Any) -> _LoopBoundClient:
        del kwargs
        client = _LoopBoundClient()
        clients.append(client)
        return client

    monkeypatch.setattr(factory_module, "create_traced_gateway_client", _factory)
    recorder = validator._FreshRecordingSpanGateway(model_id="span-model")

    asyncio.run(recorder.generate(messages=[], tools=[]))
    asyncio.run(recorder.generate(messages=[], tools=[]))

    assert len(clients) == 2
    assert all(client.closed for client in clients)
    assert len(recorder.calls) == 2


@pytest.mark.asyncio
async def test_proof_capture_reuses_successful_local_owner_recordings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later lane failure must not spend an already-admitted provider result again."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", "capture-cache")
    expected: dict[str, dict[str, str]] = {}
    for role, raw_request in _PLAIN_LANGUAGE_PROOF_REQUESTS.items():
        compiler = {
            "role": role,
            "raw_request": raw_request,
            "model_id": "owner-selected-compiler-model",
        }
        domain = {"role": role, "recording_content_hash": f"sha256:{role}"}
        validator._write_local_recording(
            validator._local_recording_path(
                tmp_path,
                role=role,
                kind="compiler",
            ),
            compiler,
        )
        validator._write_local_recording(
            validator._local_recording_path(
                tmp_path,
                role=role,
                kind="domain",
            ),
            domain,
        )
        expected[role] = domain

    async def _replay_compiler(recording: dict[str, str]) -> SimpleNamespace:
        return SimpleNamespace(role=recording["role"])

    async def _replay_domain(
        repo_root: Path,
        *,
        role: str,
        recording: dict[str, str],
    ) -> dict[str, str]:
        assert repo_root == tmp_path
        assert recording["role"] == role
        return {"role": role}

    factory_module = import_module(
        "polisyos.scientist.orchestration.llm.factory"
    )

    def _provider_must_not_run(**kwargs: Any) -> None:
        raise AssertionError(f"successful local cache was ignored: {kwargs}")

    monkeypatch.setattr(validator, "_replay_compiler_recording", _replay_compiler)
    monkeypatch.setattr(validator, "_domain_run_from_recording", _replay_domain)
    monkeypatch.setattr(
        factory_module,
        "create_traced_gateway_client",
        _provider_must_not_run,
    )

    observed = await validator._capture_proof_recordings(tmp_path)

    assert observed == expected


@pytest.mark.asyncio
async def test_proof_capture_advances_model_once_after_typed_compiler_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A predetermined alternate gets one attempt; the refused model is not retried."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", "capture-cache")
    monkeypatch.setattr(
        validator,
        "PROOF_COMPILER_MODEL_PLAN",
        ("compiler-model-a", "compiler-model-b"),
    )
    for key in (
        "POLISYOS_LLM_GATEWAY_TIMEOUT_S",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES",
        "POLISYOS_LLM_CACHE_TTL_S",
        "POLISYOS_LLM_CACHE_MAXSIZE",
    ):
        monkeypatch.delenv(key, raising=False)
    created_models: list[str] = []
    attempts: list[tuple[str, str]] = []
    closed_models: list[str] = []

    class _Client:
        def __init__(self, model_id: str) -> None:
            self.model_id = model_id

        async def aclose(self) -> None:
            closed_models.append(self.model_id)

    factory_module = import_module(
        "polisyos.scientist.orchestration.llm.factory"
    )

    def _factory(*, model_name: str, **kwargs: Any) -> _Client:
        del kwargs
        assert os.environ["POLISYOS_LLM_GATEWAY_TIMEOUT_S"] == "600"
        assert os.environ["POLISYOS_LLM_GATEWAY_MAX_RETRIES"] == "3"
        assert os.environ["POLISYOS_LLM_CACHE_TTL_S"] == "0"
        assert os.environ["POLISYOS_LLM_CACHE_MAXSIZE"] == "0"
        created_models.append(model_name)
        return _Client(model_name)

    async def _capture_compiler(
        *,
        role: str,
        raw_request: str,
        model_id: str,
        gateway: Any,
        span_gateway: Any,
    ) -> tuple[SimpleNamespace, dict[str, Any]]:
        del gateway, span_gateway
        assert raw_request == _PLAIN_LANGUAGE_PROOF_REQUESTS[role]
        attempts.append((role, model_id))
        if role == "first_vertical" and model_id == validator.PROOF_COMPILER_MODEL_PLAN[0]:
            raise DesignProblemAuthorityError("design_problem_validation_failed")
        if role == "education" and model_id == validator.PROOF_COMPILER_MODEL_PLAN[0]:
            raise RuntimeError("Failed LLM gateway call after TimeoutError")
        return SimpleNamespace(role=role), {
            "role": role,
            "raw_request": raw_request,
            "model_id": model_id,
            "recording_content_hash": "sha256:" + "7" * 64,
        }

    async def _capture_domain(
        repo_root: Path,
        *,
        role: str,
        compiler_recording: dict[str, Any],
        problem: SimpleNamespace,
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert problem.role == role
        return {
            "role": role,
            "compiler_model_id": compiler_recording["model_id"],
            "recording_content_hash": "sha256:" + "8" * 64,
        }

    async def _replay_domain(
        repo_root: Path,
        *,
        role: str,
        recording: dict[str, Any],
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert recording["role"] == role
        return {"role": role}

    monkeypatch.setattr(factory_module, "create_traced_gateway_client", _factory)
    monkeypatch.setattr(validator, "_capture_compiler_recording", _capture_compiler)
    monkeypatch.setattr(validator, "_capture_domain_run", _capture_domain)
    monkeypatch.setattr(validator, "_domain_run_from_recording", _replay_domain)

    observed = await validator._capture_proof_recordings(tmp_path)

    assert attempts[:2] == [
        ("first_vertical", validator.PROOF_COMPILER_MODEL_PLAN[0]),
        ("first_vertical", validator.PROOF_COMPILER_MODEL_PLAN[1]),
    ]
    assert attempts.count(
        ("first_vertical", validator.PROOF_COMPILER_MODEL_PLAN[0])
    ) == 1
    assert attempts[2:4] == [
        ("education", validator.PROOF_COMPILER_MODEL_PLAN[0]),
        ("education", validator.PROOF_COMPILER_MODEL_PLAN[1]),
    ]
    assert set(observed) == set(_PLAIN_LANGUAGE_PROOF_REQUESTS)
    assert created_models == closed_models
    journal_rows = [
        json.loads(line)
        for line in (
            tmp_path / "capture-cache" / "capture.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert any(
        row.get("event") == "compiler_capture_attempt_refused"
        and row.get("role") == "first_vertical"
        and row.get("model_id") == validator.PROOF_COMPILER_MODEL_PLAN[0]
        for row in journal_rows
    )
    assert any(
        row.get("event") == "compiler_capture_attempt_refused"
        and row.get("role") == "education"
        and row.get("model_id") == validator.PROOF_COMPILER_MODEL_PLAN[0]
        and row.get("error_code") == "proof_compiler_gateway_failed"
        and "TimeoutError" in str(row.get("error"))
        for row in journal_rows
    )
    assert "POLISYOS_LLM_GATEWAY_TIMEOUT_S" not in os.environ
    assert "POLISYOS_LLM_GATEWAY_MAX_RETRIES" not in os.environ
    assert "POLISYOS_LLM_CACHE_TTL_S" not in os.environ
    assert "POLISYOS_LLM_CACHE_MAXSIZE" not in os.environ


@pytest.mark.asyncio
async def test_proof_capture_resumes_without_second_cold_closeout_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A process restart continues the journaled cold run instead of minting another."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", "capture-cache")
    roles = tuple(_PLAIN_LANGUAGE_PROOF_REQUESTS)
    for role, raw_request in _PLAIN_LANGUAGE_PROOF_REQUESTS.items():
        validator._write_local_recording(
            validator._local_recording_path(
                tmp_path,
                role=role,
                kind="compiler",
            ),
            {
                "role": role,
                "raw_request": raw_request,
                "model_id": "cached-compiler",
            },
        )
    validator._write_local_recording(
        validator._local_recording_path(
            tmp_path,
            role=roles[0],
            kind="domain",
        ),
        {"role": roles[0], "recording_content_hash": "sha256:" + "4" * 64},
    )
    validator._append_capture_journal(
        tmp_path,
        {
            "event": "cold_domain_closeout_started",
            "roles": list(roles),
            "artifact_write": "not_started",
        },
    )

    async def _replay_compiler(recording: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(role=recording["role"])

    async def _capture_domain(
        repo_root: Path,
        *,
        role: str,
        compiler_recording: dict[str, Any],
        problem: SimpleNamespace,
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert compiler_recording["role"] == problem.role == role
        return {"role": role, "recording_content_hash": "sha256:" + "5" * 64}

    async def _replay_domain(
        repo_root: Path,
        *,
        role: str,
        recording: dict[str, Any],
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert recording["role"] == role
        return {"role": role}

    factory_module = import_module(
        "polisyos.scientist.orchestration.llm.factory"
    )
    monkeypatch.setattr(
        factory_module,
        "create_traced_gateway_client",
        lambda **kwargs: pytest.fail(f"provider rerun on resume: {kwargs}"),
    )
    monkeypatch.setattr(validator, "_replay_compiler_recording", _replay_compiler)
    monkeypatch.setattr(validator, "_capture_domain_run", _capture_domain)
    monkeypatch.setattr(validator, "_domain_run_from_recording", _replay_domain)

    await validator._capture_proof_recordings(tmp_path)

    rows = [
        json.loads(line)
        for line in (
            tmp_path / "capture-cache" / "capture.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert sum(
        row.get("event") == "cold_domain_closeout_started" for row in rows
    ) == 1
    assert sum(
        row.get("event") == "cold_domain_closeout_resumed" for row in rows
    ) == 1


@pytest.mark.asyncio
async def test_domain_capture_separates_compiler_model_from_n4_controller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compiler replay uses its recorded model while N4 keeps its production model."""

    validator = _universality_contract_validator()
    monkeypatch.setattr(validator, "_PROOF_CAPTURE_JOURNAL_DIR", "capture-cache")
    captured: dict[str, Any] = {}

    class _Replay:
        def __init__(self, recording: dict[str, Any]) -> None:
            del recording

        def assert_exhausted(self) -> None:
            return None

    class _Problem:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"problem": "compiled"}

    class _Compiled:
        design_problem = _Problem()
        content_hash = "sha256:" + "1" * 64

        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"compiled": "run"}

    async def _compile(**kwargs: Any) -> _Compiled:
        captured.update(kwargs)
        return _Compiled()

    async def _n4_recording(
        repo_root: Path,
        **kwargs: Any,
    ) -> tuple[dict[str, str], object]:
        assert repo_root == tmp_path
        del kwargs
        return {"recording_content_hash": "sha256:" + "2" * 64}, object()

    generation_cycle_module = import_module(
        "polisyos.runtime.http.services.control.generation_cycle"
    )
    monkeypatch.setattr(
        generation_cycle_module,
        "compile_and_run_recursive_generation_cycle",
        _compile,
    )
    monkeypatch.setattr(validator, "_ReplayGateway", _Replay)
    monkeypatch.setattr(
        validator,
        "_cycle_context_for_problem",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(validator, "_n4_recording_from_journal", _n4_recording)
    monkeypatch.setattr(validator, "_assert_n4_cycle_binding", lambda *args: None)

    compiler_recording = {
        "raw_request": "plain language",
        "context": {},
        "model_id": "owner-selected-compiler-model",
        "span_model_id": "span-model",
        "span_calls": [],
        "raw_request_content_hash": "sha256:" + "3" * 64,
    }
    await validator._capture_domain_run(
        tmp_path,
        role="unseen",
        compiler_recording=compiler_recording,
        problem=_Problem(),
    )

    assert captured["model_name"] == "owner-selected-compiler-model"
    assert captured["controller"] is not None
    assert captured["controller"]._leaf_model_id == validator.PROOF_MODEL_ID


def test_universality_task13_payload_is_complete_and_fork_b_honest() -> None:
    """Freeze three real runs without reviving the hollow non-panel positive."""

    _, payload = _complete_universality_payload()

    assert payload["proof_status"] == "complete"
    assert set(payload["domain_runs"]) == set(_PLAIN_LANGUAGE_PROOF_REQUESTS)
    assert payload["capability_reality"] == {
        "producer": "implemented",
        "artifact": "implemented",
        "semantic_test": "implemented",
    }
    assert payload["non_panel_evidence"]["fork"] == "B"
    assert payload["non_panel_evidence"]["status"] == "acquisition_required"
    assert payload["non_panel_evidence"]["supported_native_families"] == 6
    assert payload["non_panel_evidence"]["fork_a_candidate_count"] == 0
    assert payload["education_refusal"]["status"] == "value_blocked"
    assert payload["education_refusal"]["authority_blockers"] == [
        "method_estimand_binding_mismatch"
    ]
    assert payload["depth_evidence"]["observed_max_depth"] > 2
    assert payload["gy_g_strangle_receipt"]["status"] == "strangled"
    assert payload["gy_g_strangle_receipt"]["production_fixture_callers"] == []


def test_three_runs_are_compiled_from_exact_plain_language_by_canonical_owner() -> None:
    """Bind each run to the HTTP compiler owner rather than a committed fixture DTO."""

    _, payload = _complete_universality_payload()

    for role, raw_request in _PLAIN_LANGUAGE_PROOF_REQUESTS.items():
        run = payload["domain_runs"][role]
        receipt = run["compiler_receipt"]
        problem = DesignProblem.model_validate(run["design_problem"])
        assert run["raw_request"] == raw_request
        assert problem.nl_provenance.raw_request == raw_request
        assert receipt["owner"] == (
            "polisyos.runtime.http.services.control.nl_pipeline."
            "build_design_problem_from_nl_request"
        )
        assert receipt["tool_name"] == "emit_design_problem"
        assert receipt["used_committed_fixture"] is False
        assert receipt["design_problem_ref"] == gy_content_hash(
            problem.model_dump(mode="json")
        )
        assert receipt["raw_request_content_hash"] == gy_content_hash(
            {"raw_request": raw_request}
        )
        assert receipt["recording_content_hash"].startswith("sha256:")


def test_first_vertical_run_reaches_owner_data_gap_and_n7_route() -> None:
    """Require the first vertical's real Fork-B degradation, not a fabricated value pass."""

    _, payload = _complete_universality_payload()
    run = payload["domain_runs"]["first_vertical"]
    stages = run["stage_trace"]

    assert stages["generation"]["attempted"] is True
    assert stages["grounding"]["attempted"] is True
    assert stages["simulation"]["attempted"] is True
    assert stages["value"]["attempted"] is True
    assert stages["value"]["status"] == "value_blocked"
    assert "acquire_data:value_panel_data_missing" in stages["value"][
        "authority_blockers"
    ]
    assert stages["acquisition"]["attempted"] is True
    assert stages["acquisition"]["route_kind"] == "n7_requirement_gap"
    assert run["promotion_reached"] is False
    assert run["terminal_distribution"]["terminal_kind"]
    assert run["terminal_distribution"]["evidence_kind"] == "owner_data_gap"
    assert run["terminal_distribution"]["decision_grade"] == "blocked"


def test_education_run_uses_pack_levers_and_refuses_unwritable_estimand() -> None:
    """Require material progress past N10a while preserving writability-zero honesty."""

    _, payload = _complete_universality_payload()
    run = payload["domain_runs"]["education"]
    stages = run["stage_trace"]
    pack = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_second_domain_pack.json")
        .read_text(encoding="utf-8")
    )
    expected_levers = {
        row["lever_id"]
        for row in pack["components"]["lever_vocabulary"]["entries"]
    }

    assert set(stages["generation"]["proposed_lever_ids"]) == expected_levers
    assert stages["grounding"]["attempted"] is True
    assert stages["grounding"]["dispositions"]
    assert stages["value"]["attempted"] is True
    assert stages["value"]["status"] == "value_blocked"
    assert stages["value"]["authority_blockers"] == [
        "method_estimand_binding_mismatch"
    ]
    assert stages["value"]["advisor_selection_receipt_content_hash"].startswith(
        "sha256:"
    )
    assert stages["acquisition"]["attempted"] is True
    assert run["promotion_reached"] is False
    assert run["terminal_distribution"] == {
        "terminal_kind": run["terminal"]["kind"],
        "evidence_kind": "estimand_binding_refusal",
        "decision_grade": "blocked",
        "count": 1,
    }


def test_unseen_domain_reaches_typed_terminal_without_vertical_contamination() -> None:
    """Fail closed for a no-pack energy problem without borrowing known-domain vocabulary."""

    _, payload = _complete_universality_payload()
    run = payload["domain_runs"]["unseen"]
    serialized = json.dumps(run, sort_keys=True).casefold()

    assert run["cycle_substrate_context_ref"] is None
    assert run["terminal"]["kind"] in {
        "acquisition_required",
        "abstained",
        "search_ceiling_repair_required",
        "spec_gap",
        "recursive_blocked",
    }
    assert run["terminal_distribution"]["count"] == 1
    assert run["terminal_distribution"]["decision_grade"] in {
        "blocked",
        "limited",
        "abstained",
    }
    for forbidden in (
        "education_spending",
        "school_quality",
        "teaching_method",
        "tax_relief_rate",
        "ua_msme_cgf_decisive_capture",
    ):
        assert forbidden not in serialized


def test_pinned_fixture_replacement_is_rejected_after_hash_recompute() -> None:
    """Make committed-fixture substitution behaviorally RED, not merely hash-invalid."""

    validator, payload = _complete_universality_payload()
    smoke = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/"
            "layer3_gy_second_domain_smoke_design_problem.json"
        ).read_text(encoding="utf-8")
    )["design_problem"]
    payload["domain_runs"]["unseen"]["design_problem"] = smoke
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    report = validator.validate_payload(payload)

    assert any(
        issue["code"] == "cycle_driven_by_pinned_fixture"
        for issue in report["issues"]
    )


def test_universality_contract_content_hash_rejects_corruption() -> None:
    """Reject a semantic mutation whose content hash was not recomputed."""

    validator = _universality_contract_validator()
    payload = validator.build_live_payload(REPO_ROOT, lane="lane0")
    payload["proof_status"] = "complete"

    report = validator.validate_payload(payload)

    assert any(
        issue["code"] == "contract_content_hash_mismatch"
        for issue in report["issues"]
    )


def test_universality_write_is_byte_stable(tmp_path: Path) -> None:
    """Write the incomplete Task-12 payload only to an explicit noncanonical path."""

    validator = _universality_contract_validator()
    output = tmp_path / "proof.json"

    first = validator.write_payload(REPO_ROOT, output)
    second = validator.write_payload(REPO_ROOT, output)

    assert first == second == output.read_bytes()


def test_universality_validator_refuses_wrong_checkout(tmp_path: Path) -> None:
    """Refuse a foreign PolicyOS package before parsing a proof mode or writing output."""

    wrong_src = _create_wrong_checkout_package(tmp_path)
    canonical_output = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
    )
    assert not canonical_output.exists()

    result = _run_universality_validator_with_pythonpath(wrong_src, "--write")

    assert result.returncode == 1
    assert "wrong_checkout_resolved" in result.stdout + result.stderr
    assert not canonical_output.exists()


def test_universality_json_cli_is_one_machine_readable_document() -> None:
    """Keep owner import diagnostics outside the validator's JSON surface."""

    result = _run_universality_validator_with_pythonpath(
        REPO_ROOT / "src",
        "--check",
        "--output-format",
        "json",
    )

    payload = json.loads(result.stdout)
    wall_time_seconds = payload.pop("wall_time_seconds")
    assert result.returncode == 1
    assert isinstance(wall_time_seconds, float)
    assert wall_time_seconds > 0.0
    assert payload == {
        "issues": [{"code": "universality_contract_artifact_missing"}],
        "status": "fail",
    }
    assert result.stderr == ""
