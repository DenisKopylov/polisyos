"""Focused checks for the GY-N10 depth-N universality harness."""

from __future__ import annotations

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
from polisyos.pdc import (
    ArtifactRef,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    gy_content_hash,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    build_coupling_graph,
    classify_coupling,
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
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
    RecursiveGenerationCycleError,
    RecursiveGenerationCycleRun,
    build_default_recursive_generation_cycle_controller,
    recompute_depth_n_strangle_receipt,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tools.quality.validation.universality_preflight import (
    assert_universality_preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

# This preserves local import ordering only. Fresh child processes below provide the authority proof
# because pytest startup plugins may already have imported ``polisyos.*`` in this parent process.
assert_universality_preflight(REPO_ROOT)


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
