"""Focused checks for the GY-N10 depth-N universality harness."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from importlib import import_module
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

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
    GyComparisonAdmission,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    build_gy_comparison_projection_plan,
    gy_content_hash,
    gy_recorded_content_hash,
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
    CandidateSummary,
    GenerationCycleController,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
)  # noqa: E402
from polisyos.runtime.quality.grounding_relation import (  # noqa: E402
    GroundingCandidateAtom,
    MechanisticSignature,
)
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


def test_governed_depth_n_controller_uses_isolated_verification_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A governed recursive replay cannot observe the authority ledger's history."""

    depth_n = import_module(
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract"
    )
    confidence_ledger = import_module(
        "polisyos.runtime.quality.confidence_ledger"
    )

    def reject_authority_state(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("depth-n opened ConfidenceLedgerSession.from_repo")

    monkeypatch.setattr(
        confidence_ledger.ConfidenceLedgerSession,
        "from_repo",
        reject_authority_state,
    )
    problem = _recursive_problem("design://verification/root")
    controller = depth_n._governed_verification_recursive_controller(
        REPO_ROOT,
        expected_problem=problem,
        model_id="registry-selected-model",
        cycle_substrate_context=None,
        n4_generation_port=None,
        state_root=tmp_path,
    )
    factory = controller._cycle_controller_factory
    assert factory is not None
    leaf = factory("design://verification/root", problem)
    summary = CandidateSummary(
        candidate_id="verification_candidate",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="grounding_gap",
        grounding_score=0.2,
        current_valid=False,
        front="research",
        high_proxy=False,
        low_grounding=True,
    )

    observation = leaf._promotion_port(summaries=(summary,), problem=problem)
    receipt = observation.receipts[0]

    monkeypatch.setattr(
        depth_n,
        "_domain_evidence_witness",
        lambda **kwargs: {
            "kind": "verification_boundary_probe",
            "decision_grade": "blocked",
        },
    )
    grounding = SimpleNamespace(
        status="grounding_gap",
        grounding_source="verification_probe",
        grounding_disposition="gap",
        issue_codes=("verification_probe",),
        model_dump=lambda *, mode: {
            "status": "grounding_gap",
            "grounding_source": "verification_probe",
        },
    )
    value = SimpleNamespace(
        status="value_blocked",
        authority_blockers=("verification_probe",),
        decision_grade="blocked",
        selected_method_fqn=None,
        acquisition_requirement=None,
        method_selection_receipt=None,
        model_dump=lambda *, mode, exclude: {
            "status": "value_blocked",
            "authority_blockers": ["verification_probe"],
        },
    )
    cycle = SimpleNamespace(
        selected_candidate_ref="verification_candidate",
        grounding=grounding,
        simulation=SimpleNamespace(
            status="simulation_blocked",
            authority_blockers=("verification_probe",),
            world_model_record=None,
            k_world_ref_before=None,
            k_world_ref_after=None,
        ),
        value_port=value,
        acquisition_routing_report=None,
    )
    terminal = _lane0_leaf_terminal()
    cycle_run = SimpleNamespace(
        cycles=(cycle,),
        promotion_port=observation,
        run_id="verification-projection-run",
    )
    recursive_run = SimpleNamespace(
        nodes=(
            SimpleNamespace(
                node_ref="design://verification/root",
                cycle_run=cycle_run,
            ),
        ),
        authority_scope="contract_testing",
        terminal=terminal,
        content_hash="sha256:" + "3" * 64,
    )
    compiled = SimpleNamespace(
        recursive_run=recursive_run,
        design_problem=problem,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
    )
    projected = depth_n._project_domain_run(
        REPO_ROOT,
        role="unseen",
        raw_request="verification boundary probe",
        compiler_recording={
            "model_id": "registry-selected-model",
            "raw_request_content_hash": "sha256:" + "4" * 64,
            "recording_content_hash": "sha256:" + "5" * 64,
        },
        compiled=compiled,
        generation_projection={
            "status": "generated",
            "generation_owner": "verification_probe",
            "generation_channel": "n4_owner",
            "grounding_dispositions": [],
            "proposed_interventions": [],
            "prompt_slice_operator_kinds": [],
        },
        cycle_substrate_context=None,
        recording_content_hash="sha256:" + "6" * 64,
    )
    compiled_authority = depth_n._compiled_authority_source_projection(
        {
            "recursive_run": {
                "authority_scope": "contract_testing",
                "nodes": [
                    {
                        "node_ref": "design://verification/root",
                        "cycle_run": {
                            "promotion_port": observation.model_dump(mode="json")
                        },
                    }
                ],
            }
        }
    )["promotions"][0]
    stage_authority = projected["stage_trace"]["promotion"]

    assert controller._authority_scope == "contract_testing"
    assert observation.reason == "verification_n9_sequence_non_consumer"
    assert receipt["confidence_ledger_projection"]["authority_provenance"] == (
        "verification"
    )
    assert receipt["consumer_promotable"] is False
    assert {
        key: stage_authority[key]
        for key in (
            "status",
            "reason",
            "receipt_count",
            "authority_provenance",
            "all_receipts_non_consumer",
            "certified_candidate_ids",
        )
    } == {
        key: compiled_authority[key]
        for key in (
            "status",
            "reason",
            "receipt_count",
            "authority_provenance",
            "all_receipts_non_consumer",
            "certified_candidate_ids",
        )
    }


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


def test_cycle_context_intake_is_world_and_owner_evidence_driven() -> None:
    """Task 13 must not select fiscal/education evidence by role or label."""

    validator = _universality_contract_validator()
    n4_contract = import_module(
        "tools.quality.validation.check_layer3_gy_design_generation_contract"
    )
    n10a = import_module(
        "tools.quality.validation.check_layer3_gy_second_domain_pack"
    )
    fiscal = n4_contract._design_problem(
        {
            "design_problem_id": "world_context_fiscal",
            "domain": "synonym economic-policy label",
        }
    )
    fiscal_context = validator._cycle_context_for_problem(
        REPO_ROOT,
        problem=fiscal,
    )

    frozen = n10a._load_frozen_bundle(REPO_ROOT)
    education = DesignProblem.model_validate(
        frozen["smoke_problem"]["design_problem"]
    ).model_copy(update={"domain": "learning systems synonym"})
    education_context = validator._cycle_context_for_problem(
        REPO_ROOT,
        problem=education,
    )
    unseen = education.model_copy(
        update={
            "domain": "unseen energy system",
            "jurisdiction_time": education.jurisdiction_time.model_copy(
                update={"region": "unseen-energy-target"}
            ),
            "outcome_of_interest": education.outcome_of_interest.model_copy(
                update={
                    "target_variable": "heat_wave_environmental_equity_burden",
                    "metric_id": "heat_wave_environmental_equity_burden",
                }
            ),
        }
    )
    unseen_context = validator._cycle_context_for_problem(
        REPO_ROOT,
        problem=unseen,
    )

    assert fiscal_context is not None
    assert fiscal_context.world_model_record.policy_domain == "fiscal_credit"
    assert fiscal_context.intervention_substrate is not None
    assert not fiscal_context.candidate_levers
    assert education_context is not None
    assert education_context.domain == "learning systems synonym"
    assert education_context.candidate_levers
    assert unseen_context is None


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
    assert report["prompt_hashes"]["binding_mode"] in {
        "exact_live_capture",
        "verified_historical_replay",
    }
    if report["prompt_hashes"]["binding_mode"] == "exact_live_capture":
        assert report["prompt_hashes"]["owner_projection"] == report[
            "prompt_hashes"
        ]["journal"]
    else:
        assert report["prompt_hashes"]["owner_projection"] != report[
            "prompt_hashes"
        ]["journal"]
    assert report["composition_ref"]["status"] == "bound"


def _complete_universality_payload() -> tuple[Any, dict[str, Any]]:
    """Load the frozen capstone; the validator owns the single behavioral rederive."""

    validator = _universality_contract_validator()
    payload = json.loads(
        (REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8")
    )
    return validator, payload


def _recording_receipts(recording: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the complete ordered receipt denominator from one recording fixture."""

    return [
        receipt
        for node in recording["compiled_run"]["recursive_run"]["nodes"]
        for receipt in node["cycle_run"]["promotion_port"]["receipts"]
    ]


def _fixture_receipt_semantic_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    """Project either side of the governed v1-to-v2 fixture transition.

    The production owner never admits v1 without a live migrator. These
    structural recording tests deliberately isolate the root walker from that
    separately exercised promotion-owner seam while the frozen artifact is v1.
    """

    promotion = import_module("polisyos.runtime.quality.promotion_sequence")
    if receipt.get("confidence_ledger_semantic_projection") is None:
        return promotion._canonical_promotion_receipt_legacy_semantic_projection(
            receipt
        )
    return promotion.canonical_promotion_receipt_semantic_projection(receipt)


def _manual_receipt_comparison_admissions(
    recording: dict[str, Any],
) -> tuple[GyComparisonAdmission, ...]:
    """Mint test tokens with the exact canonical owner vocabulary."""

    promotion = import_module("polisyos.runtime.quality.promotion_sequence")
    owner = promotion.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_OWNER_RULE
    return tuple(
        GyComparisonAdmission(
            owner_rule=promotion.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_RULE,
            source_content_hash=gy_recorded_content_hash(receipt),
            projector=_fixture_receipt_semantic_projection,
            action=owner.action,
            predicate_provenance=owner.predicate_provenance,
        )
        for receipt in _recording_receipts(recording)
    )


def _allow_manual_receipt_proofs_for_projection_test(
    monkeypatch: pytest.MonkeyPatch,
    validator: Any,
) -> None:
    """Isolate structural projection tests from the separately tested owner capability."""

    def _unwrap(value: object) -> GyComparisonAdmission:
        if not isinstance(value, GyComparisonAdmission):
            raise ValueError("test_receipt_proof_invalid")
        return value

    monkeypatch.setattr(
        validator,
        "canonical_promotion_comparison_admission_from_proof",
        _unwrap,
    )
    monkeypatch.setattr(
        validator,
        "canonical_promotion_receipt_semantic_projection",
        _fixture_receipt_semantic_projection,
    )


def _refresh_recording_hashes(recording: dict[str, Any]) -> None:
    """Refresh the four typed enclosing identities after a receipt-fixture change."""

    recursive_run = recording["compiled_run"]["recursive_run"]
    recursive_run["content_hash"] = gy_content_hash(
        {
            key: value
            for key, value in recursive_run.items()
            if key != "content_hash"
        }
    )
    compiled_run = recording["compiled_run"]
    compiled_run["content_hash"] = gy_content_hash(
        {
            key: value
            for key, value in compiled_run.items()
            if key != "content_hash"
        }
    )
    recording["compiled_run_content_hash"] = compiled_run["content_hash"]
    recording["recording_content_hash"] = gy_content_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )


def _change_all_operational_clocks(value: object) -> None:
    """Perturb each clock without changing the fixture's structural shape."""

    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_at") and isinstance(item, str):
                value[key] = "2026-08-12T12:00:00Z"
            elif key.endswith("_wall_time_ms") and isinstance(item, (int, float)):
                value[key] = 999.0
            else:
                _change_all_operational_clocks(item)
    elif isinstance(value, list):
        for item in value:
            _change_all_operational_clocks(item)


def _verification_lineage_variant(recording: dict[str, Any]) -> dict[str, Any]:
    """Return a strictly valid recording with only session lineage and clocks changed."""

    changed = copy.deepcopy(recording)
    promotion = import_module("polisyos.runtime.quality.promotion_sequence")
    for index, receipt in enumerate(_recording_receipts(changed), start=1):
        expected_projection = _fixture_receipt_semantic_projection(receipt)
        certificate = receipt["confidence_ledger_projection"]
        certificate["deployment_identity"] = (
            "policy-engine-deployment:sha256:" + str(index) * 64
        )
        certificate["projection_hash"] = gy_content_hash(
            {
                key: value
                for key, value in certificate.items()
                if key != "projection_hash"
            }
        )
        receipt["gate_outcome_hash"] = "sha256:" + str(index + 1) * 64
        if receipt["trace_content_hash"] is not None:
            receipt["trace_content_hash"] = "sha256:" + str(index + 2) * 64
        assert (
            _fixture_receipt_semantic_projection(receipt)
            == expected_projection
        )
    _change_all_operational_clocks(changed)
    _refresh_recording_hashes(changed)
    return changed


def test_controlled_recording_comparison_preserves_full_frozen_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session lineage and clocks compare equal while complete custody bytes survive."""

    validator, payload = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    frozen_full = copy.deepcopy(payload["proof_recordings"]["first_vertical"])
    frozen = validator._without_authority_source_migration_receipt(frozen_full)
    live = _verification_lineage_variant(frozen)
    live_receipt_proofs = _manual_receipt_comparison_admissions(live)

    live_admission = validator._admit_controlled_recording_for_comparison(
        live,
        role="first_vertical",
        receipt_proofs=live_receipt_proofs,
    )
    live_plan = build_gy_comparison_projection_plan(
        live,
        admissions=(live_admission,),
    )
    reconciled = validator._reconcile_controlled_recording(
        frozen,
        live,
        comparison_plan=live_plan,
        role="first_vertical",
        admission_arm="migrated",
    )
    frozen_admission = validator._admit_controlled_recording_for_comparison(
        live,
        role="first_vertical",
        receipt_proofs=live_receipt_proofs,
        aligned_recording=frozen,
    )
    frozen_plan = build_gy_comparison_projection_plan(
        frozen,
        admissions=(frozen_admission,),
    )
    full_admission = validator._admit_controlled_recording_for_comparison(
        live,
        role="first_vertical",
        receipt_proofs=live_receipt_proofs,
        aligned_recording=frozen_full,
    )
    full_plan = build_gy_comparison_projection_plan(
        frozen_full,
        admissions=(full_admission,),
    )

    assert live_plan.project(live) == frozen_plan.project(frozen)
    assert reconciled == frozen
    assert json.dumps(reconciled, sort_keys=True) == json.dumps(
        frozen,
        sort_keys=True,
    )
    assert full_plan.preserve_admitted_blocks(frozen_full, frozen_full) == frozen_full
    assert full_plan.project(frozen_full)["authority_source_admission"]
    assert _recording_receipts(reconciled)
    assert all(
        receipt["confidence_ledger_projection"]["authority_provenance"]
        == "verification"
        for receipt in _recording_receipts(reconciled)
    )


def test_aligned_recording_migration_uses_proof_bound_receipt_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact reconciliation reuses the live receipts proven before alignment."""

    validator, payload = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    frozen = validator._without_authority_source_migration_receipt(
        payload["proof_recordings"]["first_vertical"]
    )
    live = _verification_lineage_variant(frozen)
    promotion = import_module("polisyos.runtime.quality.promotion_sequence")
    owner = promotion.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_OWNER_RULE
    strict_proofs: list[GyComparisonAdmission] = []
    for receipt in _recording_receipts(live):
        proof_bound = copy.deepcopy(receipt)

        def _migrate(
            previous: dict[str, object],
            current: dict[str, object],
            *,
            expected: dict[str, object] = proof_bound,
        ) -> dict[str, object]:
            if current != expected:
                raise ValueError("live_receipt_drift")
            return copy.deepcopy(previous)

        strict_proofs.append(
            GyComparisonAdmission(
                owner_rule=promotion.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_RULE,
                source_content_hash=gy_recorded_content_hash(receipt),
                projector=_fixture_receipt_semantic_projection,
                action=owner.action,
                predicate_provenance=owner.predicate_provenance,
                legacy_migrator=_migrate,
            )
        )

    recording_admission = validator._admit_controlled_recording_for_comparison(
        live,
        role="first_vertical",
        receipt_proofs=tuple(strict_proofs),
        aligned_recording=frozen,
    )
    plan = build_gy_comparison_projection_plan(
        frozen,
        admissions=(recording_admission,),
    )

    assert plan.preserve_admitted_blocks(frozen, frozen) == frozen
    forged_current = copy.deepcopy(frozen)
    _change_all_operational_clocks(forged_current)
    _refresh_recording_hashes(forged_current)
    with pytest.raises(
        ValueError,
        match="controlled_recording_legacy_comparison_semantic_mismatch",
    ) as exc_info:
        plan.preserve_admitted_blocks(frozen, forged_current)
    assert exc_info.value.__cause__ is not None
    assert str(exc_info.value.__cause__) == "controlled_recording_aligned_current_drift"


def test_artifact_reconciliation_reissues_recording_authority_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root migration must rebind its authority envelope and sibling route."""

    validator, frozen = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    role = "first_vertical"
    live = copy.deepcopy(frozen)
    live_recording = _verification_lineage_variant(
        live["proof_recordings"][role]
    )
    live["proof_recordings"][role] = live_recording
    owner = validator._DEPTH_CONTROLLED_RECORDING_COMPARISON_OWNER_RULE
    recording_admission = GyComparisonAdmission(
        owner_rule=validator._DEPTH_CONTROLLED_RECORDING_COMPARISON_RULE,
        source_content_hash=gy_recorded_content_hash(live_recording),
        projector=validator._controlled_recording_verification_semantic_projection,
        action=owner.action,
        predicate_provenance=owner.predicate_provenance,
        legacy_migrator=lambda _previous, current: copy.deepcopy(dict(current)),
    )
    plan = build_gy_comparison_projection_plan(
        live,
        admissions=(recording_admission,),
    )

    stale_issues = validator._authority_source_admission_issues(
        live_recording,
        replayed_domain_run=live["domain_runs"][role],
        expected_role=role,
    )
    assert "authority_source_recording_base_binding_mismatch" in stale_issues
    assert "authority_source_admission_compiled_binding_mismatch" in stale_issues

    reconciled = validator._reconcile_artifact_records(frozen, live, plan)
    reconciled_recording = reconciled["proof_recordings"][role]
    reconciled_route = reconciled["domain_runs"][role]

    assert reconciled_recording["recording_content_hash"] == (
        reconciled_route["recording_content_hash"]
    )
    assert not validator._authority_source_admission_issues(
        reconciled_recording,
        replayed_domain_run=reconciled_route,
        expected_role=role,
    )
    assert not validator.validate_payload(reconciled)["issues"]


def test_controlled_recording_comparison_keeps_governing_input_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An admitted verification projection cannot hide a governing input change."""

    validator, payload = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    frozen = validator._without_authority_source_migration_receipt(
        payload["proof_recordings"]["first_vertical"]
    )
    live = copy.deepcopy(frozen)
    live["compiler_recording"]["raw_request"] += " governing change"
    _refresh_recording_hashes(live)
    admission = validator._admit_controlled_recording_for_comparison(
        live,
        role="first_vertical",
        receipt_proofs=_manual_receipt_comparison_admissions(live),
    )
    plan = build_gy_comparison_projection_plan(live, admissions=(admission,))

    with pytest.raises(
        validator.UniversalityContractError,
        match="authority_source_controlled_replay_recording_drift",
    ):
        validator._reconcile_controlled_recording(
            frozen,
            live,
            comparison_plan=plan,
            role="first_vertical",
            admission_arm="migrated",
        )


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param(None, id="absent"),
        pytest.param([], id="malformed"),
        pytest.param(["verification", "canonical_repo"], id="mixed"),
        pytest.param("unknown", id="unrecognized"),
    ],
)
def test_controlled_recording_comparison_declaration_fails_closed(
    declaration: object,
) -> None:
    """Absent, malformed, mixed, or unrecognized provenance cannot mint admission."""

    validator, payload = _complete_universality_payload()
    recording = validator._without_authority_source_migration_receipt(
        payload["proof_recordings"]["first_vertical"]
    )
    receipt = _recording_receipts(recording)[0]
    certificate = receipt["confidence_ledger_projection"]
    if declaration is None:
        certificate.pop("authority_provenance")
    else:
        certificate["authority_provenance"] = declaration
    certificate["projection_hash"] = gy_content_hash(
        {
            key: value
            for key, value in certificate.items()
            if key != "projection_hash"
        }
    )
    _refresh_recording_hashes(recording)

    with pytest.raises((ValidationError, ValueError)):
        validator._admit_controlled_recording_for_comparison(
            recording,
            role="first_vertical",
            receipt_proofs=_manual_receipt_comparison_admissions(recording),
        )


def test_controlled_recording_rejects_self_rehashed_detached_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coherent self-rehash cannot reuse an admission bound to different raw bytes."""

    validator, payload = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    frozen = validator._without_authority_source_migration_receipt(
        payload["proof_recordings"]["first_vertical"]
    )
    frozen_admissions = _manual_receipt_comparison_admissions(frozen)
    forged = _verification_lineage_variant(frozen)

    with pytest.raises(ValueError, match="gy_comparison_live_admission_unbound"):
        validator._admit_controlled_recording_for_comparison(
            forged,
            role="first_vertical",
            receipt_proofs=frozen_admissions,
        )


def test_controlled_recording_rejects_manually_minted_receipt_admission() -> None:
    """Canonical-looking public admission metadata is not live owner proof."""

    validator, payload = _complete_universality_payload()
    recording = validator._without_authority_source_migration_receipt(
        payload["proof_recordings"]["first_vertical"]
    )

    with pytest.raises(
        ValueError,
        match="canonical_promotion_comparison_proof_invalid",
    ):
        validator._admit_controlled_recording_for_comparison(
            recording,
            role="first_vertical",
            receipt_proofs=_manual_receipt_comparison_admissions(recording),
        )


def test_depth_receipt_proofs_delegate_to_live_canonical_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Depth bridge cannot replace the canonical receipt proof factory."""

    validator, payload = _complete_universality_payload()
    control = import_module(
        "polisyos.runtime.http.services.control.generation_cycle"
    )
    compiled = control.CompiledRecursiveGenerationCycleRun.model_validate(
        payload["proof_recordings"]["first_vertical"]["compiled_run"]
    )
    sessions = {node.node_ref: object() for node in compiled.recursive_run.nodes}
    calls: list[tuple[object, object, object]] = []

    def _prove(
        receipt: object,
        *,
        repo_root: Path,
        confidence_ledger_session: object,
        candidate_summary: object,
        value_receipt: object,
    ) -> object:
        assert repo_root == REPO_ROOT
        assert candidate_summary.candidate_id == receipt.candidate_id
        assert value_receipt == candidate_summary.value_receipt
        proof = object()
        calls.append((proof, confidence_ledger_session, candidate_summary))
        return proof

    monkeypatch.setattr(
        validator,
        "prove_canonical_promotion_receipt_for_comparison",
        _prove,
    )

    proofs = validator._depth_compiled_receipt_comparison_proofs(
        compiled,
        sessions_by_node_ref=sessions,
        repo_root=REPO_ROOT,
    )

    assert proofs == tuple(call[0] for call in calls)
    assert len(proofs) == 3
    assert {call[1] for call in calls} == set(sessions.values())


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
    real_governed_controller = validator._governed_verification_recursive_controller

    def _governed_controller(*args: Any, **kwargs: Any) -> object:
        captured["leaf_model_id"] = kwargs["model_id"]
        return real_governed_controller(*args, **kwargs)

    monkeypatch.setattr(
        validator,
        "_governed_verification_recursive_controller",
        _governed_controller,
    )

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

        def model_dump(self, *, mode: str) -> dict[str, Any]:
            assert mode == "json"
            return {
                "compiled": "run",
                "recursive_run": {
                    "authority_scope": "contract_testing",
                    "nodes": [
                        {
                            "node_ref": "design://controlled-capture",
                            "cycle_run": {
                                "promotion_port": {
                                    "status": "not_promoted",
                                    "reason": (
                                        "verification_n9_sequence_non_consumer"
                                    ),
                                    "certified_candidate_ids": [],
                                    "receipts": [
                                        {
                                            "consumer_promotable": False,
                                            "confidence_ledger_projection": {
                                                "authority_provenance": "verification"
                                            },
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                },
            }

    async def _compile(**kwargs: Any) -> _Compiled:
        captured.update(kwargs)
        return _Compiled()

    async def _n4_recording(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("no-context capture invoked the Scientist N4 replay")

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
    monkeypatch.setattr(
        validator,
        "_assert_no_context_cycle_binding",
        lambda *args: None,
    )

    compiler_recording = {
        "raw_request": "plain language",
        "context": {},
        "model_id": "owner-selected-compiler-model",
        "span_model_id": "span-model",
        "span_calls": [],
        "raw_request_content_hash": "sha256:" + "3" * 64,
    }
    recording = await validator._capture_domain_run(
        tmp_path,
        role="future_role",
        compiler_recording=compiler_recording,
        problem=_Problem(),
    )

    assert captured["model_name"] == "owner-selected-compiler-model"
    assert captured["controller"] is not None
    assert captured["controller"]._authority_scope == "contract_testing"
    assert captured["leaf_model_id"] == validator.PROOF_MODEL_ID
    assert recording["cycle_substrate_context_content_hash"] is None
    assert recording["schema_version"] == (
        "policyos.layer3.gy.n10.domain_run_recording.v2"
    )
    assert recording["authority_source_admission"]["admission_kind"] == (
        "controlled_at_capture"
    )
    assert recording["n4_recording"]["status"] == (
        "cycle_substrate_context_unavailable"
    )
    assert "responses" not in recording["n4_recording"]
    assert "owner_result_projection" not in recording["n4_recording"]


@pytest.mark.parametrize(
    ("validation_reason", "historical_rederive_allowed"),
    [
        ("recursive_generation_cycle_content_hash_mismatch", True),
        ("recursive_run_graph_binding_mismatch", False),
    ],
)
@pytest.mark.asyncio
async def test_domain_recording_rederives_downstream_owners_from_recorded_n4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validation_reason: str,
    historical_rederive_allowed: bool,
) -> None:
    """Cached proof replay runs N6/N5/N8/N9 instead of trusting the captured DTO."""

    validator = _universality_contract_validator()
    expected_problem_ref = gy_content_hash({"problem": "compiled"})
    context_hash = "sha256:" + "1" * 64
    live_hash = "sha256:" + "3" * 64
    calls: dict[str, Any] = {}
    legacy_migration_calls = 0

    class _Problem:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"problem": "compiled"}

    problem = _Problem()
    context = SimpleNamespace(content_hash=context_hash)
    live_recursive = {
        "authority_scope": "contract_testing",
        "nodes": [
            {
                "node_ref": "design://controlled",
                "cycle_run": {
                    "cycles": [
                        {
                            "acquisition_routing_report": {
                                "generated_at": "2026-08-09T10:33:22Z"
                            },
                            "value_port": {"wall_time_ms": 1.0},
                        }
                    ],
                    "value_port": {"wall_time_ms": 1.0},
                    "promotion_port": {
                        "status": "not_promoted",
                        "reason": "verification_n9_sequence_non_consumer",
                        "certified_candidate_ids": [],
                        "receipts": [
                            {
                                "consumer_promotable": False,
                                "confidence_ledger_projection": {
                                    "authority_provenance": "verification"
                                },
                            }
                        ],
                    }
                },
                "terminal": {
                    "costed_plan": {
                        "canonical_planner_report": {
                            "generated_at": "2026-08-09T10:33:22Z"
                        }
                    }
                },
            }
        ],
        "terminal": {
            "costed_plan": {
                "canonical_planner_report": {
                    "generated_at": "2026-08-09T10:33:22Z"
                }
            }
        },
    }
    live_payload = {
        "content_hash": live_hash,
        "recursive_run": live_recursive,
    }
    live_compiled = SimpleNamespace(
        design_problem=problem,
        cycle_substrate_context_ref=context_hash,
        content_hash=live_hash,
        design_problem_ref=expected_problem_ref,
        model_dump=lambda *, mode: copy.deepcopy(live_payload),
    )

    async def _replay_compiler(recording: dict[str, Any]) -> _Problem:
        del recording
        return problem

    async def _replay_n4(*args: Any, **kwargs: Any) -> object:
        del args, kwargs
        return object()

    async def _compile_and_run(**kwargs: Any) -> object:
        calls.update(kwargs)
        return live_compiled

    def _project(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args
        assert kwargs["compiled"] is live_compiled
        payload = {
            "domain_role": kwargs["role"],
            "compiler_receipt": {"design_problem_ref": expected_problem_ref},
            "recording_content_hash": kwargs["recording_content_hash"],
            "recursive_run_content_hash": live_hash,
            "stage_trace": {
                "promotion": {
                    "attempted": True,
                    "owner": "canonical-n9",
                    "authority_scope": "contract_testing",
                    "authority_provenance": ["verification"],
                    "status": "not_promoted",
                    "reason": "verification_n9_sequence_non_consumer",
                    "receipt_count": 1,
                    "all_receipts_non_consumer": True,
                    "certified_candidate_ids": [],
                }
            },
        }
        payload["content_hash"] = validator._semantic_hash(payload)
        return payload

    control = import_module(
        "polisyos.runtime.http.services.control.generation_cycle"
    )
    compiled_type = control.CompiledRecursiveGenerationCycleRun

    recursive_payload: dict[str, Any] = {
        "root_design_problem_ref": expected_problem_ref,
        "authority_scope": "production",
        "nodes": [
            {
                "node_ref": "design://historical",
                "cycle_run": {
                    "promotion_port": {
                        "status": "not_promoted",
                        "reason": "canonical_n9_sequence_returned_shadow",
                        "certified_candidate_ids": [],
                        "receipts": [{"consumer_promotable": False}],
                    }
                },
            }
        ],
    }
    recursive_payload["content_hash"] = gy_content_hash(recursive_payload)
    captured_payload: dict[str, Any] = {
        "schema_version": "policyos.test.compiled.v1",
        "design_problem_ref": expected_problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": context_hash,
        "recursive_run": recursive_payload,
    }
    captured_payload["content_hash"] = gy_content_hash(captured_payload)

    def _validate_compiled(payload: dict[str, Any]) -> object:
        if payload.get("schema_version") != "policyos.test.compiled.v1":
            return live_compiled
        raise ValidationError.from_exception_data(
            "CompiledRecursiveGenerationCycleRun",
            [
                {
                    "type": "value_error",
                    "loc": ("recursive_run",),
                    "input": payload.get("recursive_run"),
                    "ctx": {"error": ValueError(validation_reason)},
                }
            ],
        )

    monkeypatch.setattr(
        compiled_type,
        "model_validate",
        staticmethod(_validate_compiled),
    )
    monkeypatch.setattr(
        control,
        "compile_and_run_recursive_generation_cycle",
        _compile_and_run,
    )
    monkeypatch.setattr(validator, "_replay_compiler_recording", _replay_compiler)
    monkeypatch.setattr(
        validator,
        "_cycle_context_for_problem",
        lambda *args, **kwargs: context,
    )
    monkeypatch.setattr(validator, "_replay_n4_recording", _replay_n4)
    monkeypatch.setattr(validator, "_n4_owner_projection", lambda value: {})
    monkeypatch.setattr(validator, "_assert_n4_cycle_binding", lambda *args: None)
    monkeypatch.setattr(validator, "_project_domain_run", _project)
    pdc_module = import_module("polisyos.pdc")

    def _fixture_recording_projector(value: dict[str, object]) -> object:
        return pdc_module.strip_gy_volatile_fields(value)

    def _fixture_recording_admission(
        source_recording: dict[str, Any],
        *,
        role: str,
        receipt_proofs: tuple[object, ...],
        aligned_recording: dict[str, Any] | None = None,
    ) -> GyComparisonAdmission:
        del role, receipt_proofs
        target = aligned_recording or source_recording

        def _migrate_once(
            previous: dict[str, object],
            current: dict[str, object],
        ) -> dict[str, object]:
            del current
            nonlocal legacy_migration_calls
            legacy_migration_calls += 1
            if legacy_migration_calls > 1:
                raise ValueError("depth_recording_legacy_migrator_called_twice")
            return copy.deepcopy(previous)

        return GyComparisonAdmission(
            owner_rule="test.depth.recording_projection.v1",
            source_content_hash=gy_recorded_content_hash(target),
            projector=_fixture_recording_projector,
            legacy_migrator=_migrate_once,
        )

    monkeypatch.setattr(
        validator,
        "_depth_compiled_receipt_comparison_proofs",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        validator,
        "_admit_controlled_recording_for_comparison",
        _fixture_recording_admission,
    )

    recording: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.domain_run_recording.v1",
        "role": "education",
        "compiler_recording": {},
        "n4_recording": {"model_id": validator.PROOF_MODEL_ID, "responses": []},
        "cycle_substrate_context_content_hash": context_hash,
        "compiled_run": captured_payload,
        "compiled_run_content_hash": captured_payload["content_hash"],
        "design_problem_ref": expected_problem_ref,
    }
    recording["recording_content_hash"] = validator._semantic_hash(recording)
    monkeypatch.setitem(
        validator._AUTHORITY_SOURCE_REQUIRED_PREDECESSOR_RECORDING_HASHES,
        "education",
        recording["recording_content_hash"],
    )

    if not historical_rederive_allowed:
        with pytest.raises(ValidationError, match=validation_reason):
            await validator._domain_run_from_recording(
                tmp_path,
                role="education",
                recording=recording,
            )
        assert calls == {}
        return

    historical_run = {
        "domain_role": "education",
        "compiler_receipt": {"design_problem_ref": expected_problem_ref},
        "recording_content_hash": recording["recording_content_hash"],
        "recursive_run_content_hash": captured_payload["content_hash"],
        "stage_trace": {
            "promotion": {
                "attempted": True,
                "owner": "canonical-n9",
                "status": "not_promoted",
                "certified_candidate_ids": [],
            }
        },
    }
    historical_run["content_hash"] = validator._semantic_hash(historical_run)
    domain_run, normalized, _ = await validator._domain_run_and_normalized_recording(
        tmp_path,
        role="education",
        recording=recording,
        historical_domain_run=historical_run,
    )

    assert "root_n4_generation_port" not in calls
    assert calls["controller"] is not None
    assert calls["controller"]._authority_scope == "contract_testing"
    assert calls["cycle_substrate_context"] is context
    assert normalized["compiled_run"] == live_payload
    assert normalized["compiled_run_content_hash"] == live_hash
    assert normalized["n4_recording"] == recording["n4_recording"]
    assert not validator._authority_source_migration_receipt_issues(
        normalized,
        replayed_domain_run=domain_run,
    )

    live_cycle = live_payload["recursive_run"]["nodes"][0]["cycle_run"]
    live_cycle["cycles"][0]["acquisition_routing_report"]["generated_at"] = (
        "2026-08-09T10:49:01Z"
    )
    live_cycle["cycles"][0]["value_port"]["wall_time_ms"] = 99.0
    live_cycle["value_port"]["wall_time_ms"] = 99.0
    live_payload["recursive_run"]["nodes"][0]["terminal"]["costed_plan"][
        "canonical_planner_report"
    ]["generated_at"] = "2026-08-09T10:49:01Z"
    live_payload["recursive_run"]["terminal"]["costed_plan"][
        "canonical_planner_report"
    ]["generated_at"] = "2026-08-09T10:49:01Z"

    replayed_domain_run, replayed_recording, _ = (
        await validator._domain_run_and_normalized_recording(
            tmp_path,
            role="education",
            recording=normalized,
            historical_domain_run=domain_run,
        )
    )

    assert replayed_recording == normalized
    assert replayed_domain_run == domain_run
    assert legacy_migration_calls == 1

    live_payload["recursive_run"]["nodes"][0]["node_ref"] = "design://changed-secret"
    legacy_migration_calls = 0
    with pytest.raises(validator.UniversalityContractError) as exc_info:
        await validator._domain_run_and_normalized_recording(
            tmp_path,
            role="education",
            recording=normalized,
            historical_domain_run=domain_run,
        )

    message = str(exc_info.value)
    assert message.startswith("authority_source_controlled_replay_recording_drift:")
    report = json.loads(message[message.index("{") :])
    assert report["admission_arm"] == "migrated"
    assert report["recording_role"] == "education"
    assert report["expected_frozen"]["operand_role"] == "expected_frozen"
    assert report["live_replayed"]["operand_role"] == "live_replayed"
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        report["expected_frozen"]["content_identity"],
    )
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        report["live_replayed"]["content_identity"],
    )
    assert (
        report["expected_frozen"]["content_identity"]
        != report["live_replayed"]["content_identity"]
    )
    leaves = {leaf["path"]: leaf for leaf in report["changed_leaves"]}
    changed = leaves["/compiled_run/recursive_run/nodes/0/node_ref"]
    assert changed["operational"] is False
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        changed["expected_frozen"]["content_identity"],
    )
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        changed["live_replayed"]["content_identity"],
    )
    assert "design://controlled" not in message
    assert "design://changed-secret" not in message


def test_historical_compiled_envelope_rejects_tampered_recursive_payload() -> None:
    """A stale receipt may be replayed only after its recorded bytes verify exactly."""

    validator = _universality_contract_validator()
    problem_payload = {"problem": "compiled"}
    problem_ref = gy_content_hash(problem_payload)
    context_hash = "sha256:" + "1" * 64

    class _Problem:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return problem_payload

    recursive_payload: dict[str, Any] = {
        "root_design_problem_ref": problem_ref,
        "nodes": [],
    }
    recursive_payload["content_hash"] = gy_content_hash(recursive_payload)
    compiled_payload: dict[str, Any] = {
        "schema_version": "policyos.test.compiled.v1",
        "design_problem_ref": problem_ref,
        "design_problem": problem_payload,
        "cycle_substrate_context_ref": context_hash,
        "recursive_run": recursive_payload,
    }
    compiled_payload["content_hash"] = gy_content_hash(compiled_payload)
    recording = {
        "compiled_run": compiled_payload,
        "compiled_run_content_hash": compiled_payload["content_hash"],
        "design_problem_ref": problem_ref,
    }
    recursive_payload["nodes"].append({"forged": True})

    with pytest.raises(
        validator.UniversalityContractError,
        match="domain_run_historical_recursive_receipt_tampered",
    ):
        validator._verify_historical_compiled_envelope(
            recording=recording,
            problem=_Problem(),
            observed_context_hash=context_hash,
        )


def _historical_projection_rebind_fixture() -> tuple[
    Any,
    dict[str, Any],
    dict[str, Any],
]:
    """Build one certificate-only historical N4 projection delta."""

    validator = _universality_contract_validator()
    raw = '{"candidate":"owner-recorded"}'
    raw_hash = gy_content_hash(raw)
    prompt_hash = "sha256:" + "1" * 64
    historical_projection = {
        "status": "generated",
        "exact_call_prompt_hashes": [prompt_hash],
        "raw_response_hashes": [raw_hash],
        "grounding_dispositions": [
            {
                "disposition": "novel_cg3",
                "reason": "cg2_revalidation_failed",
                "lever_resolution": {
                    "lever_id": "cash_transfer",
                    "content_hash": "sha256:" + "1" * 64,
                    "context_binding_hash": "sha256:" + "1" * 64,
                    "substrate_input_content_hash": "sha256:" + "1" * 64,
                },
                "bridge_missing_records": [
                    {
                        "record_id": "cg5_ticket_" + "2" * 16,
                        "content_hash": "sha256:" + "2" * 64,
                    }
                ],
                "certificate_chain": {
                    "cg1_certificate_id": "cg1_cert_" + "3" * 16,
                    "cg1_content_hash": "sha256:" + "3" * 64,
                },
            }
        ],
    }
    replayed_projection = copy.deepcopy(historical_projection)
    bridge = replayed_projection["grounding_dispositions"][0][
        "bridge_missing_records"
    ][0]
    bridge["record_id"] = "cg5_ticket_" + "4" * 16
    bridge["content_hash"] = "sha256:" + "4" * 64
    chain = replayed_projection["grounding_dispositions"][0][
        "certificate_chain"
    ]
    chain["cg1_certificate_id"] = "cg1_cert_" + "5" * 16
    chain["cg1_content_hash"] = "sha256:" + "5" * 64
    recording: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.n4_recording.v1",
        "recording_source": "live_gateway_call_journal_replayed_through_n4_owner",
        "role": "first_vertical",
        "model_id": validator.PROOF_MODEL_ID,
        "effective_environment": {},
        "cycle_substrate_context_content_hash": "sha256:" + "9" * 64,
        "responses": [
            {
                "prompt_hash": prompt_hash,
                "raw_response": raw,
                "raw_llm_response": raw,
                "raw_response_hash": raw_hash,
            }
        ],
        "owner_result_projection": historical_projection,
    }
    recording["recording_content_hash"] = validator._semantic_hash(recording)
    return validator, recording, replayed_projection


def test_historical_n4_projection_rebind_is_exact_and_content_bound() -> None:
    """Certificate-only provenance may rebind once through a verified receipt."""

    validator, recording, replayed_projection = (
        _historical_projection_rebind_fixture()
    )
    normalized = validator._normalize_replayed_n4_recording(
        recording,
        replayed_projection=replayed_projection,
    )

    receipt = normalized["historical_projection_rebind_receipt"]
    assert receipt["eligible_issue_set"] == [
        "proof_n4_owner_projection_replay_drift"
    ]
    assert receipt["historical_owner_result_projection"] == recording[
        "owner_result_projection"
    ]
    assert normalized["owner_result_projection"] == replayed_projection
    assert (
        validator._historical_n4_projection_rebind_receipt_issues(normalized)
        == ()
    )


def test_historical_n4_projection_rebind_rejects_tamper_and_nonidentity() -> None:
    """Raw-byte or semantic drift cannot use the historical exception."""

    validator, recording, replayed_projection = (
        _historical_projection_rebind_fixture()
    )
    semantic_drift = copy.deepcopy(replayed_projection)
    semantic_drift["grounding_dispositions"][0]["disposition"] = "shadow_bound"
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_owner_projection_replay_drift",
    ):
        validator._build_historical_n4_projection_rebind_receipt(
            recording,
            replayed_projection=semantic_drift,
        )

    normalized = validator._normalize_replayed_n4_recording(
        recording,
        replayed_projection=replayed_projection,
    )
    normalized["responses"][0]["raw_response"] += " tampered"
    normalized["responses"][0]["raw_llm_response"] = normalized["responses"][
        0
    ]["raw_response"]
    assert "proof_n4_recording_raw_response_hash_mismatch" in (
        validator._historical_n4_projection_rebind_receipt_issues(normalized)
    )


def test_historical_n4_atom_readdress_is_owner_recomputed_not_whitelisted() -> None:
    """A WMR reissue proves both CG0 preimages and one stable causal key."""

    validator = _universality_contract_validator()
    old_wmr = "sha256:" + "1" * 64
    new_wmr = "sha256:" + "2" * 64
    old_wmr_id = "world_model_record_" + old_wmr.removeprefix("sha256:")[:16]
    new_wmr_id = "world_model_record_" + new_wmr.removeprefix("sha256:")[:16]
    edge_prefix = "WMR_POLICY_SLOT_MAP::"
    current_signature = MechanisticSignature(
        op="budget_allocation_multiplier",
        X_do=("government.balance",),
        x_do={"domain": {"kind": "range", "unit": None}},
        sign="increase",
        params={"domain": {"kind": "range", "unit": None}},
        scope="global",
        unit="usd",
        population="all",
        time="current_reference_epoch",
        outcome=("government.balance",),
        effect_path=(
            "budget_allocation_multiplier",
            "government.balance",
            "government.balance",
        ),
        estimand="average_treatment_effect",
        admissibility="passed",
        wm_version=new_wmr,
        evidence=(
            "L6_KNOB_OPERATOR::budget_allocation_multiplier",
            edge_prefix + new_wmr_id + ":government.balance",
        ),
    )
    current_scope = tuple(current_signature.evidence)
    current_hash = gy_content_hash(
        {
            "edge_scope": sorted(current_scope),
            "signature": current_signature.model_dump(mode="json"),
        }
    )
    current_atom = GroundingCandidateAtom(
        atom_id="cg0_atom_" + current_hash.removeprefix("sha256:")[:16],
        signature=current_signature,
        edge_scope=current_scope,
    )
    historical_signature = current_signature.model_copy(
        update={
            "wm_version": old_wmr,
            "evidence": tuple(
                item.replace(new_wmr_id, old_wmr_id)
                for item in current_signature.evidence
            ),
        }
    )
    historical_scope = tuple(
        item.replace(new_wmr_id, old_wmr_id) for item in current_scope
    )
    historical_hash = gy_content_hash(
        {
            "edge_scope": sorted(historical_scope),
            "signature": historical_signature.model_dump(mode="json"),
        }
    )
    historical_id = "cg0_atom_" + historical_hash.removeprefix("sha256:")[:16]
    historical_projection = {
        "grounding_dispositions": [
            {
                "proposal_id": "gy_n4.owner_recorded",
                "identified_atom_id": historical_id,
                "disposition": "novel_cg3",
                "status": "candidate_unverified",
                "selected_relation": "novel-candidate",
                "rejected_cause": {
                    "cg1_critical_contradictions": ["op", "sign"],
                    "cg2_decision": "abstain",
                    "cg2_open_obligations": ["no_unresolved_critical_axis"],
                },
            }
        ]
    }
    replayed_projection = copy.deepcopy(historical_projection)
    replayed_projection["grounding_dispositions"][0]["identified_atom_id"] = (
        current_atom.atom_id
    )
    registry = {
        "schema_version": "policyos.layer3.gy.n10.wmr_reissue_registry.v1",
        "reissues": [
            {
                "historical_wmr_content_hash": old_wmr,
                "reissued_wmr_content_hash": new_wmr,
                "owner": "production_composed_world_model_record",
                "reason": "unit_owner_reissue",
            }
        ],
    }

    witnesses = validator._build_n4_atom_readdress_witnesses(
        historical_projection,
        replayed_projection,
        current_atoms={current_atom.atom_id: current_atom},
        reissue_registry=registry,
    )

    assert witnesses[0]["historical_atom_binding"]["atom_id"] == historical_id
    assert witnesses[0]["reissued_atom_binding"]["atom_id"] == current_atom.atom_id
    assert validator._n4_atom_readdress_witness_issues(
        historical_projection,
        replayed_projection,
        witnesses=witnesses,
        current_atoms={current_atom.atom_id: current_atom},
        reissue_registry=registry,
    ) == ()

    forged = copy.deepcopy(witnesses)
    forged[0]["historical_atom_binding"]["signature"]["unit"] = "index"
    forged[0]["witness_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in forged[0].items()
            if key != "witness_content_hash"
        }
    )
    assert "proof_n4_atom_readdress_historical_preimage_mismatch" in (
        validator._n4_atom_readdress_witness_issues(
            historical_projection,
            replayed_projection,
            witnesses=forged,
            current_atoms={current_atom.atom_id: current_atom},
            reissue_registry=registry,
        )
    )

    no_veto = copy.deepcopy(replayed_projection)
    no_veto["grounding_dispositions"][0]["rejected_cause"][
        "cg1_critical_contradictions"
    ] = []
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_atom_readdress_authority_growth",
    ):
        validator._build_n4_atom_readdress_witnesses(
            historical_projection,
            no_veto,
            current_atoms={current_atom.atom_id: current_atom},
            reissue_registry=registry,
        )

    no_open_obligations = copy.deepcopy(replayed_projection)
    no_open_obligations["grounding_dispositions"][0]["rejected_cause"][
        "cg2_open_obligations"
    ] = []
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_atom_readdress_authority_growth",
    ):
        validator._build_n4_atom_readdress_witnesses(
            historical_projection,
            no_open_obligations,
            current_atoms={current_atom.atom_id: current_atom},
            reissue_registry=registry,
        )


def test_historical_n4_projection_rebind_chains_only_for_context_identity() -> None:
    """A later path-only context rebase preserves the prior N4 proof chain."""

    validator, recording, first_projection = (
        _historical_projection_rebind_fixture()
    )
    first = validator._normalize_replayed_n4_recording(
        recording,
        replayed_projection=first_projection,
    )
    context_projection = copy.deepcopy(first_projection)
    context_projection["exact_call_prompt_hashes"][0] = "sha256:" + "6" * 64
    context_projection["lever_space_prompt_slice_content_hash"] = (
        "sha256:" + "7" * 64
    )
    bridge = context_projection["grounding_dispositions"][0][
        "bridge_missing_records"
    ][0]
    bridge["record_id"] = "cg5_ticket_" + "8" * 16
    bridge["content_hash"] = "sha256:" + "8" * 64
    lever_resolution = context_projection["grounding_dispositions"][0][
        "lever_resolution"
    ]
    lever_resolution["content_hash"] = "sha256:" + "8" * 64
    lever_resolution["context_binding_hash"] = "sha256:" + "8" * 64
    lever_resolution["substrate_input_content_hash"] = "sha256:" + "8" * 64

    chained = validator._normalize_replayed_n4_recording(
        first,
        replayed_projection=context_projection,
        context_rebind=("sha256:" + "9" * 64, "sha256:" + "a" * 64),
    )

    receipt = chained["historical_projection_rebind_receipt"]
    assert receipt["eligible_issue_set"] == [
        "domain_run_context_binding_drift",
        "proof_n4_owner_projection_replay_drift",
    ]
    assert receipt["prior_receipt"]["receipt_content_hash"] == first[
        "historical_projection_rebind_receipt"
    ]["receipt_content_hash"]
    assert receipt["historical_context_content_hash"] == "sha256:" + "9" * 64
    assert receipt["replayed_context_content_hash"] == "sha256:" + "a" * 64
    assert validator._historical_n4_projection_rebind_receipt_issues(chained) == ()
    assert validator._recompute_historical_n4_recording_content_hash(chained) == (
        first["recording_content_hash"]
    )

    second_context_projection = copy.deepcopy(context_projection)
    second_context_projection["exact_call_prompt_hashes"][0] = (
        "sha256:" + "b" * 64
    )
    second_context_projection["lever_space_prompt_slice_content_hash"] = (
        "sha256:" + "c" * 64
    )
    second_bridge = second_context_projection["grounding_dispositions"][0][
        "bridge_missing_records"
    ][0]
    second_bridge["record_id"] = "cg5_ticket_" + "d" * 16
    second_bridge["content_hash"] = "sha256:" + "d" * 64
    second_lever = second_context_projection["grounding_dispositions"][0][
        "lever_resolution"
    ]
    second_lever["content_hash"] = "sha256:" + "d" * 64
    second_lever["context_binding_hash"] = "sha256:" + "d" * 64
    second_lever["substrate_input_content_hash"] = "sha256:" + "d" * 64
    twice_chained = validator._normalize_replayed_n4_recording(
        chained,
        replayed_projection=second_context_projection,
        context_rebind=("sha256:" + "a" * 64, "sha256:" + "e" * 64),
    )
    assert (
        twice_chained["historical_projection_rebind_receipt"]["prior_receipt"]
        ["receipt_content_hash"]
        == chained["historical_projection_rebind_receipt"]
        ["receipt_content_hash"]
    )
    assert (
        validator._historical_n4_projection_rebind_receipt_issues(twice_chained)
        == ()
    )

    semantic_drift = copy.deepcopy(context_projection)
    semantic_drift["grounding_dispositions"][0]["disposition"] = "shadow_bound"
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_owner_projection_replay_drift",
    ):
        validator._normalize_replayed_n4_recording(
            first,
            replayed_projection=semantic_drift,
            context_rebind=(
                "sha256:" + "9" * 64,
                "sha256:" + "a" * 64,
            ),
        )

    lever_drift = copy.deepcopy(context_projection)
    lever_drift["grounding_dispositions"][0]["lever_resolution"][
        "lever_id"
    ] = "education_grant"
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_owner_projection_replay_drift",
    ):
        validator._normalize_replayed_n4_recording(
            first,
            replayed_projection=lever_drift,
            context_rebind=(
                "sha256:" + "9" * 64,
                "sha256:" + "a" * 64,
            ),
        )


def test_historical_context_rebind_allows_only_content_identity_drift() -> None:
    """A context rebind cannot hide a terminal or owner-status change."""

    validator = _universality_contract_validator()
    historical = {
        "content_hash": "sha256:" + "1" * 64,
        "cycle_substrate_context_ref": "sha256:" + "2" * 64,
        "recursive_run_content_hash": "sha256:" + "3" * 64,
        "generation_cycle_run_id": "generation_cycle_" + "4" * 16,
        "stage_trace": {
            "generation": {
                "status": "generated",
                "prompt_slice_content_hash": "sha256:" + "5" * 64,
            },
            "grounding": {
                "requirement_gap_id": "gap_" + "1" * 16,
                "evidence_refs": ["sha256:" + "2" * 64],
                "metric_id": "employment_rate",
            },
        },
        "terminal_distribution": {
            "terminal_kind": "acquisition_required",
            "evidence_kind": "owner_acquisition_route",
            "decision_grade": "blocked",
            "count": 1,
        },
    }
    replayed = copy.deepcopy(historical)
    replayed.update(
        {
            "content_hash": "sha256:" + "6" * 64,
            "cycle_substrate_context_ref": "sha256:" + "7" * 64,
            "recursive_run_content_hash": "sha256:" + "8" * 64,
            "generation_cycle_run_id": "generation_cycle_" + "9" * 16,
        }
    )
    replayed["stage_trace"]["generation"]["prompt_slice_content_hash"] = (
        "sha256:" + "a" * 64
    )
    replayed["stage_trace"]["grounding"]["requirement_gap_id"] = (
        "gap_" + "b" * 16
    )
    replayed["stage_trace"]["grounding"]["evidence_refs"][0] = (
        "sha256:" + "c" * 64
    )

    assert validator._context_rebind_semantic_diff_paths(
        historical,
        replayed,
    ) == ()

    replayed["terminal_distribution"]["terminal_kind"] = "grounded_admissible"
    assert validator._context_rebind_semantic_diff_paths(
        historical,
        replayed,
    ) == ("terminal_distribution.terminal_kind",)
    replayed["terminal_distribution"]["terminal_kind"] = "acquisition_required"
    replayed["stage_trace"]["grounding"]["metric_id"] = "unemployment_rate"
    assert validator._context_rebind_semantic_diff_paths(
        historical,
        replayed,
    ) == ("stage_trace.grounding.metric_id",)


def test_historical_context_rebind_receipt_binds_route_and_raw_evidence() -> None:
    """The one-time context migration is replay proof, not a pinned exception."""

    validator = _universality_contract_validator()
    old_context = "sha256:" + "1" * 64
    new_context = "sha256:" + "2" * 64
    recording = {
        "cycle_substrate_context_content_hash": old_context,
        "compiled_run_content_hash": "sha256:" + "3" * 64,
        "compiler_recording": {
            "recording_content_hash": "sha256:" + "4" * 64,
        },
        "n4_recording": {
            "recording_content_hash": "sha256:" + "5" * 64,
        },
    }
    historical = {
        "domain_role": "education",
        "cycle_substrate_context_ref": old_context,
        "stage_trace": {"value": {"status": "acquisition_required"}},
        "terminal_distribution": {
            "terminal_kind": "acquisition_required",
            "evidence_kind": "owner_acquisition_route",
            "decision_grade": "blocked",
            "count": 1,
        },
        "content_hash": "sha256:" + "6" * 64,
    }
    replayed = copy.deepcopy(historical)
    replayed["cycle_substrate_context_ref"] = new_context
    replayed["content_hash"] = "sha256:" + "7" * 64

    receipt = validator._build_historical_context_rebind_receipt(
        recording,
        historical_domain_run=historical,
        replayed_domain_run=replayed,
        replayed_context_content_hash=new_context,
        replayed_compiled_run_content_hash="sha256:" + "8" * 64,
        replayed_n4_recording_content_hash="sha256:" + "9" * 64,
    )

    assert receipt["eligible_issue_set"] == ["domain_run_context_binding_drift"]
    assert receipt["historical_context_content_hash"] == old_context
    assert receipt["replayed_context_content_hash"] == new_context
    assert receipt["compiler_recording_content_hash"] == "sha256:" + "4" * 64
    assert receipt["historical_n4_recording_content_hash"] == (
        "sha256:" + "5" * 64
    )
    assert receipt["replayed_n4_recording_content_hash"] == (
        "sha256:" + "9" * 64
    )
    assert receipt["changed_identity_paths"] == [
        "content_hash",
        "cycle_substrate_context_ref",
    ]
    normalized_recording = copy.deepcopy(recording)
    normalized_recording["cycle_substrate_context_content_hash"] = new_context
    normalized_recording["compiled_run_content_hash"] = "sha256:" + "8" * 64
    normalized_recording["n4_recording"]["recording_content_hash"] = (
        "sha256:" + "9" * 64
    )
    normalized_recording["historical_context_rebind_receipt"] = receipt
    assert validator._historical_context_rebind_receipt_issues(
        normalized_recording,
        replayed_domain_run=replayed,
    ) == ()

    next_context = "sha256:" + "a" * 64
    next_replayed = copy.deepcopy(replayed)
    next_replayed["cycle_substrate_context_ref"] = next_context
    next_replayed["content_hash"] = "sha256:" + "b" * 64
    chained_receipt = validator._build_historical_context_rebind_receipt(
        normalized_recording,
        historical_domain_run=replayed,
        replayed_domain_run=next_replayed,
        replayed_context_content_hash=next_context,
        replayed_compiled_run_content_hash="sha256:" + "c" * 64,
        replayed_n4_recording_content_hash="sha256:" + "d" * 64,
    )
    assert chained_receipt["prior_receipt"]["receipt_content_hash"] == receipt[
        "receipt_content_hash"
    ]
    chained_recording = copy.deepcopy(normalized_recording)
    chained_recording["cycle_substrate_context_content_hash"] = next_context
    chained_recording["compiled_run_content_hash"] = "sha256:" + "c" * 64
    chained_recording["n4_recording"]["recording_content_hash"] = (
        "sha256:" + "d" * 64
    )
    chained_recording["historical_context_rebind_receipt"] = chained_receipt
    assert validator._historical_context_rebind_receipt_issues(
        chained_recording,
        replayed_domain_run=next_replayed,
    ) == ()

    forged_chain = copy.deepcopy(chained_recording)
    forged_prior = forged_chain["historical_context_rebind_receipt"][
        "prior_receipt"
    ]
    forged_prior["eligible_issue_set"] = []
    forged_prior["receipt_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in forged_prior.items()
            if key != "receipt_content_hash"
        }
    )
    forged_top = forged_chain["historical_context_rebind_receipt"]
    forged_top["receipt_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in forged_top.items()
            if key != "receipt_content_hash"
        }
    )
    assert "domain_run_context_rebind_issue_set_mismatch" in (
        validator._historical_context_rebind_receipt_issues(
            forged_chain,
            replayed_domain_run=next_replayed,
        )
    )

    semantic_drift = copy.deepcopy(replayed)
    semantic_drift["terminal_distribution"]["decision_grade"] = "admissible"
    with pytest.raises(
        validator.UniversalityContractError,
        match="domain_run_context_rebind_semantic_drift",
    ):
        validator._build_historical_context_rebind_receipt(
            recording,
            historical_domain_run=historical,
            replayed_domain_run=semantic_drift,
            replayed_context_content_hash=new_context,
            replayed_compiled_run_content_hash="sha256:" + "8" * 64,
            replayed_n4_recording_content_hash="sha256:" + "9" * 64,
        )


    tampered = copy.deepcopy(normalized_recording)
    tampered_receipt = tampered["historical_context_rebind_receipt"]
    tampered_receipt["historical_route_projection"]["terminal_distribution"][
        "decision_grade"
    ] = "admissible"
    tampered_receipt["historical_route_projection_content_hash"] = (
        validator._semantic_hash(
            tampered_receipt["historical_route_projection"]
        )
    )
    tampered_receipt["receipt_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered_receipt.items()
            if key != "receipt_content_hash"
        }
    )
    assert "domain_run_context_rebind_semantic_drift" in (
        validator._historical_context_rebind_receipt_issues(
            tampered,
            replayed_domain_run=replayed,
        )
    )


def test_normalized_recording_replaces_ambient_compiled_run_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controlled bytes supersede ambient bytes through an append-only receipt."""

    validator = _universality_contract_validator()
    problem_payload = {"problem": "controlled-verification"}
    old_context = "sha256:" + "3" * 64
    current_context = "sha256:" + "4" * 64
    compiler_recording = {"recording_content_hash": "sha256:" + "1" * 64}
    n4_recording = {"recording_content_hash": "sha256:" + "2" * 64}
    historical_compiled_payload = {
        "content_hash": "sha256:" + "5" * 64,
        "recursive_run": {
            "authority_scope": "production",
            "nodes": [
                {
                    "node_ref": "design://historical",
                    "cycle_run": {
                        "promotion_port": {
                            "status": "not_promoted",
                            "reason": "canonical_n9_sequence_returned_shadow",
                            "certified_candidate_ids": [],
                            "receipts": [
                                {"consumer_promotable": False}
                            ],
                        }
                    },
                }
            ],
        },
    }
    controlled_compiled_payload = {
        "content_hash": "sha256:" + "6" * 64,
        "recursive_run": {
            "authority_scope": "contract_testing",
            "nodes": [
                {
                    "node_ref": "design://historical",
                    "cycle_run": {
                        "promotion_port": {
                            "status": "not_promoted",
                            "reason": "verification_n9_sequence_non_consumer",
                            "certified_candidate_ids": [],
                            "receipts": [
                                {
                                    "consumer_promotable": False,
                                    "confidence_ledger_projection": {
                                        "authority_provenance": "verification"
                                    },
                                }
                            ],
                        }
                    },
                }
            ],
        },
    }
    compiled = SimpleNamespace(
        content_hash=controlled_compiled_payload["content_hash"],
        design_problem=SimpleNamespace(
            model_dump=lambda *, mode: problem_payload,
        ),
        model_dump=lambda *, mode: copy.deepcopy(controlled_compiled_payload),
    )
    before_context = {
        "domain_role": "education",
        "cycle_substrate_context_ref": old_context,
        "recording_content_hash": "sha256:" + "7" * 64,
        "recursive_run_content_hash": "sha256:" + "8" * 64,
        "stage_trace": {
            "promotion": {
                "attempted": True,
                "owner": "canonical-n9",
                "status": "not_promoted",
                "certified_candidate_ids": [],
            }
        },
        "terminal_distribution": {
            "terminal_kind": "acquisition_required",
            "evidence_kind": "owner_acquisition_route",
            "decision_grade": "blocked",
            "count": 1,
        },
    }
    before_context["content_hash"] = validator._semantic_hash(before_context)
    historical_domain_run = copy.deepcopy(before_context)
    historical_domain_run["cycle_substrate_context_ref"] = current_context
    historical_domain_run["recording_content_hash"] = "sha256:" + "9" * 64
    historical_domain_run["recursive_run_content_hash"] = "sha256:" + "a" * 64
    historical_domain_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in historical_domain_run.items()
            if key != "content_hash"
        }
    )
    prior_recording = {
        "compiler_recording": compiler_recording,
        "n4_recording": n4_recording,
        "cycle_substrate_context_content_hash": old_context,
        "compiled_run_content_hash": historical_compiled_payload["content_hash"],
    }
    prior_context_receipt = validator._build_historical_context_rebind_receipt(
        prior_recording,
        historical_domain_run=before_context,
        replayed_domain_run=historical_domain_run,
        replayed_context_content_hash=current_context,
        replayed_compiled_run_content_hash=historical_compiled_payload["content_hash"],
        replayed_n4_recording_content_hash=n4_recording["recording_content_hash"],
    )
    historical_recording = {
        "schema_version": "policyos.layer3.gy.n10.domain_run_recording.v1",
        "role": "education",
        "compiler_recording": compiler_recording,
        "n4_recording": n4_recording,
        "cycle_substrate_context_content_hash": current_context,
        "compiled_run": historical_compiled_payload,
        "compiled_run_content_hash": historical_compiled_payload["content_hash"],
        "design_problem_ref": gy_content_hash(problem_payload),
        "historical_context_rebind_receipt": prior_context_receipt,
    }
    historical_recording["recording_content_hash"] = validator._semantic_hash(
        historical_recording
    )
    monkeypatch.setitem(
        validator._AUTHORITY_SOURCE_REQUIRED_PREDECESSOR_RECORDING_HASHES,
        "education",
        historical_recording["recording_content_hash"],
    )
    historical_domain_run["recording_content_hash"] = historical_recording[
        "recording_content_hash"
    ]
    historical_domain_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in historical_domain_run.items()
            if key != "content_hash"
        }
    )
    assert not validator._historical_context_rebind_receipt_issues(
        historical_recording,
        replayed_domain_run=historical_domain_run,
    )

    refreshed = validator._refresh_domain_run_recording(
        historical_recording,
        n4_recording=n4_recording,
        cycle_substrate_context=SimpleNamespace(content_hash=current_context),
        compiled=compiled,
    )
    replayed_domain_run = copy.deepcopy(historical_domain_run)
    replayed_domain_run["recording_content_hash"] = refreshed[
        "recording_content_hash"
    ]
    replayed_domain_run["recursive_run_content_hash"] = "sha256:" + "b" * 64
    replayed_domain_run["stage_trace"]["promotion"].update(
        {
            "authority_scope": "contract_testing",
            "authority_provenance": ["verification"],
            "reason": "verification_n9_sequence_non_consumer",
            "receipt_count": 1,
            "all_receipts_non_consumer": True,
        }
    )
    replayed_domain_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in replayed_domain_run.items()
            if key != "content_hash"
        }
    )

    normalized = validator._attach_authority_source_migration_receipt(
        historical_recording=historical_recording,
        refreshed_recording=refreshed,
        historical_domain_run=historical_domain_run,
        replayed_domain_run=replayed_domain_run,
        expected_role="education",
    )
    replayed_domain_run["recording_content_hash"] = normalized[
        "recording_content_hash"
    ]
    replayed_domain_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in replayed_domain_run.items()
            if key != "content_hash"
        }
    )
    receipt = normalized["authority_source_migration_receipt"]

    assert normalized["schema_version"] == (
        "policyos.layer3.gy.n10.domain_run_recording.v2"
    )
    assert normalized["authority_source_admission"]["admission_kind"] == (
        "migrated"
    )
    assert normalized["compiled_run"] == controlled_compiled_payload
    assert normalized["compiled_run_content_hash"] == controlled_compiled_payload[
        "content_hash"
    ]
    assert normalized["design_problem_ref"] == gy_content_hash(problem_payload)
    assert historical_recording["compiled_run"] == historical_compiled_payload
    assert receipt["historical_recording"]["recording_content_hash"] == (
        historical_recording["recording_content_hash"]
    )
    assert receipt["prior_context_rebind_receipt_content_hash"] == (
        prior_context_receipt["receipt_content_hash"]
    )
    assert not validator._authority_source_migration_receipt_issues(
        normalized,
        replayed_domain_run=replayed_domain_run,
    )
    assert not validator._authority_source_admission_issues(
        normalized,
        replayed_domain_run=replayed_domain_run,
        expected_role="education",
    )

    missing_receipt = copy.deepcopy(normalized)
    missing_receipt.pop("authority_source_migration_receipt")
    missing_receipt["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in missing_receipt.items()
            if key != "recording_content_hash"
        }
    )
    missing_receipt_run = copy.deepcopy(replayed_domain_run)
    missing_receipt_run["recording_content_hash"] = missing_receipt[
        "recording_content_hash"
    ]
    missing_receipt_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in missing_receipt_run.items()
            if key != "content_hash"
        }
    )
    assert "authority_source_migration_receipt_missing" in (
        validator._authority_source_admission_issues(
            missing_receipt,
            replayed_domain_run=missing_receipt_run,
            expected_role="education",
        )
    )

    missing_admission = copy.deepcopy(normalized)
    missing_admission.pop("authority_source_migration_receipt")
    missing_admission.pop("authority_source_admission")
    missing_admission["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in missing_admission.items()
            if key != "recording_content_hash"
        }
    )
    missing_admission_run = copy.deepcopy(replayed_domain_run)
    missing_admission_run["recording_content_hash"] = missing_admission[
        "recording_content_hash"
    ]
    missing_admission_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in missing_admission_run.items()
            if key != "content_hash"
        }
    )
    assert validator._authority_source_admission_issues(
        missing_admission,
        replayed_domain_run=missing_admission_run,
        expected_role="education",
    ) == ("authority_source_admission_missing",)

    relabeled_capture = copy.deepcopy(normalized)
    relabeled_capture.pop("authority_source_migration_receipt")
    relabeled_admission = relabeled_capture["authority_source_admission"]
    relabeled_admission["admission_kind"] = "controlled_at_capture"
    relabeled_admission["migration_receipt_content_hash"] = None
    relabeled_admission["predicate_provenance"] = (
        validator._authority_source_admission_predicate_provenance(
            "controlled_at_capture",
            predecessor_required=True,
        )
    )
    relabeled_admission["admission_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in relabeled_admission.items()
            if key != "admission_content_hash"
        }
    )
    relabeled_capture["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in relabeled_capture.items()
            if key != "recording_content_hash"
        }
    )
    relabeled_run = copy.deepcopy(replayed_domain_run)
    relabeled_run["recording_content_hash"] = relabeled_capture[
        "recording_content_hash"
    ]
    relabeled_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in relabeled_run.items()
            if key != "content_hash"
        }
    )
    assert "authority_source_required_migration_missing" in (
        validator._authority_source_admission_issues(
            relabeled_capture,
            replayed_domain_run=relabeled_run,
            expected_role="education",
        )
    )

    self_selected_role = copy.deepcopy(normalized)
    self_selected_role.pop("authority_source_migration_receipt")
    self_selected_role["role"] = "future_role"
    self_selected_admission = self_selected_role["authority_source_admission"]
    self_selected_admission["admission_kind"] = "controlled_at_capture"
    self_selected_admission["governed_role"] = "future_role"
    self_selected_admission["migration_receipt_content_hash"] = None
    self_selected_admission["required_predecessor_recording_content_hash"] = None
    self_selected_admission["predicate_provenance"] = (
        validator._authority_source_admission_predicate_provenance(
            "controlled_at_capture",
            predecessor_required=False,
        )
    )
    self_selected_admission["controlled_recording_base_content_hash"] = (
        validator._semantic_hash(
            validator._authority_source_recording_base(self_selected_role)
        )
    )
    self_selected_admission["admission_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in self_selected_admission.items()
            if key != "admission_content_hash"
        }
    )
    self_selected_role["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in self_selected_role.items()
            if key != "recording_content_hash"
        }
    )
    self_selected_run = copy.deepcopy(replayed_domain_run)
    self_selected_run["domain_role"] = "future_role"
    self_selected_run["recording_content_hash"] = self_selected_role[
        "recording_content_hash"
    ]
    self_selected_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in self_selected_run.items()
            if key != "content_hash"
        }
    )
    self_selected_issues = validator._authority_source_admission_issues(
        self_selected_role,
        replayed_domain_run=self_selected_run,
        expected_role="education",
    )
    assert "authority_source_recording_role_mismatch" in self_selected_issues
    assert "authority_source_domain_role_mismatch" in self_selected_issues
    assert "authority_source_required_migration_missing" in self_selected_issues

    tampered = copy.deepcopy(normalized)
    tampered_receipt = tampered["authority_source_migration_receipt"]
    tampered_historical = tampered_receipt["historical_recording"]
    tampered_historical["compiler_recording"]["forged"] = True
    tampered_historical["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered_historical.items()
            if key != "recording_content_hash"
        }
    )
    tampered_receipt["historical_recording_content_hash"] = tampered_historical[
        "recording_content_hash"
    ]
    tampered_route = tampered_receipt["historical_route_projection"]
    tampered_route["recording_content_hash"] = tampered_historical[
        "recording_content_hash"
    ]
    tampered_route["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered_route.items()
            if key != "content_hash"
        }
    )
    tampered_receipt["historical_route_projection_content_hash"] = (
        validator._semantic_hash(
            validator._authority_source_stable_projection(tampered_route)
        )
    )
    tampered_receipt["receipt_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered_receipt.items()
            if key != "receipt_content_hash"
        }
    )
    tampered["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered.items()
            if key != "recording_content_hash"
        }
    )
    tampered_replayed = copy.deepcopy(replayed_domain_run)
    tampered_replayed["recording_content_hash"] = tampered[
        "recording_content_hash"
    ]
    tampered_replayed["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in tampered_replayed.items()
            if key != "content_hash"
        }
    )
    assert "authority_source_compiler_evidence_drift" in (
        validator._authority_source_migration_receipt_issues(
            tampered,
            replayed_domain_run=tampered_replayed,
        )
    )


def test_static_recording_check_requires_authority_source_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frozen checks invoke admission even when the marker is absent."""

    validator, payload = _complete_universality_payload()
    monkeypatch.setattr(
        validator,
        "_authority_source_admission_issues",
        lambda *args, **kwargs: ("authority_source_static_sentinel",),
    )

    issues = validator._static_proof_recording_issues(payload)

    assert {issue["code"] for issue in issues} >= {
        "authority_source_static_sentinel"
    }


@pytest.mark.asyncio
async def test_live_recording_replay_requires_authority_source_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rehashed v2 recording cannot reach owners without its admission union."""

    validator, payload = _complete_universality_payload()
    role = "education"
    recording = copy.deepcopy(payload["proof_recordings"][role])
    historical_run = copy.deepcopy(payload["domain_runs"][role])
    recording["schema_version"] = (
        "policyos.layer3.gy.n10.domain_run_recording.v2"
    )
    recording.pop("authority_source_admission", None)
    recording.pop("authority_source_migration_receipt", None)
    recording["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )
    historical_run["recording_content_hash"] = recording[
        "recording_content_hash"
    ]
    historical_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in historical_run.items()
            if key != "content_hash"
        }
    )

    async def _unexpected_owner(*args: Any, **kwargs: Any) -> object:
        del args, kwargs
        raise AssertionError("missing admission reached compiler replay")

    monkeypatch.setattr(
        validator,
        "_replay_compiler_recording",
        _unexpected_owner,
    )

    with pytest.raises(
        validator.UniversalityContractError,
        match="authority_source_admission_missing",
    ):
        await validator._domain_run_and_normalized_recording(
            REPO_ROOT,
            role=role,
            recording=recording,
            historical_domain_run=historical_run,
        )


@pytest.mark.asyncio
async def test_authority_migration_rejects_forged_prior_chain_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rehashed predecessor forgery cannot be laundered into fresh bytes."""

    validator, payload = _complete_universality_payload()
    recording = copy.deepcopy(payload["proof_recordings"]["education"])
    historical_run = copy.deepcopy(payload["domain_runs"]["education"])
    prior = recording["historical_context_rebind_receipt"]
    prior["eligible_issue_set"] = []
    prior["receipt_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in prior.items()
            if key != "receipt_content_hash"
        }
    )
    recording["recording_content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )
    monkeypatch.setitem(
        validator._AUTHORITY_SOURCE_REQUIRED_PREDECESSOR_RECORDING_HASHES,
        "education",
        recording["recording_content_hash"],
    )
    historical_run["recording_content_hash"] = recording[
        "recording_content_hash"
    ]
    historical_run["content_hash"] = validator._semantic_hash(
        {
            key: value
            for key, value in historical_run.items()
            if key != "content_hash"
        }
    )

    async def _unexpected_replay(*args: Any, **kwargs: Any) -> object:
        del args, kwargs
        raise AssertionError("forged predecessor reached compiler replay")

    monkeypatch.setattr(
        validator,
        "_replay_compiler_recording",
        _unexpected_replay,
    )

    with pytest.raises(
        validator.UniversalityContractError,
        match=r"authority_source_prior_context_receipt_invalid:.*issue_set",
    ):
        await validator._domain_run_and_normalized_recording(
            REPO_ROOT,
            role="education",
            recording=recording,
            historical_domain_run=historical_run,
        )


def test_no_context_recording_supersedes_model_output_and_verifies_legacy_bytes() -> None:
    """No-context proof evidence is a typed refusal; stale raw bytes remain checksummed."""

    validator, payload = _complete_universality_payload()
    problem = DesignProblem.model_validate(
        payload["domain_runs"]["unseen"]["design_problem"]
    )
    canonical = validator._no_context_generation_recording(problem)

    assert canonical["schema_version"] == (
        "policyos.layer3.gy.n10.no_context_generation_recording.v1"
    )
    assert canonical["status"] == "cycle_substrate_context_unavailable"
    assert canonical["cycle_substrate_context_content_hash"] is None
    assert "responses" not in canonical
    assert "owner_result_projection" not in canonical
    validator._verify_superseded_no_context_n4_recording(
        canonical,
        problem=problem,
    )

    raw = '{"candidate":"historical-only"}'
    legacy: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.n4_recording.v1",
        "recording_source": "superseded_live_gateway_call_journal",
        "role": "unseen",
        "model_id": validator.PROOF_MODEL_ID,
        "design_problem_ref": canonical["design_problem_ref"],
        "cycle_substrate_context_content_hash": None,
        "responses": [
            {
                "raw_response": raw,
                "raw_llm_response": raw,
                "raw_response_hash": gy_content_hash(raw),
            }
        ],
        "owner_result_projection": {"status": "historical_only"},
    }
    legacy["recording_content_hash"] = validator._semantic_hash(legacy)
    validator._verify_superseded_no_context_n4_recording(
        legacy,
        problem=problem,
    )

    tampered = copy.deepcopy(legacy)
    tampered["responses"][0]["raw_response"] += " "
    stable = {
        key: value
        for key, value in tampered.items()
        if key != "recording_content_hash"
    }
    tampered["recording_content_hash"] = validator._semantic_hash(stable)
    with pytest.raises(
        validator.UniversalityContractError,
        match="proof_n4_recorded_raw_response_hash_mismatch",
    ):
        validator._verify_superseded_no_context_n4_recording(
            tampered,
            problem=problem,
        )


@pytest.mark.asyncio
async def test_complete_payload_persists_normalized_recordings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The capstone writer cannot copy a superseded no-context recording forward."""

    validator = _universality_contract_validator()
    source = {
        role: {"role": role, "recording_content_hash": f"legacy-{role}"}
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    }
    historical = {
        role: {"domain_role": role}
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    }

    async def _rederive(
        repo_root: Path,
        *,
        role: str,
        recording: dict[str, Any],
        historical_domain_run: dict[str, Any] | None = None,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        tuple[GyComparisonAdmission, ...],
    ]:
        assert repo_root == tmp_path
        assert recording is not source[role]
        assert historical_domain_run == historical[role]
        run = {
            "terminal_distribution": {
                "terminal_kind": "acquisition_required",
                "evidence_kind": f"owner-{role}",
                "decision_grade": "blocked",
                "count": 1,
            }
        }
        normalized = {
            "role": role,
            "recording_content_hash": f"normalized-{role}",
        }
        admission = GyComparisonAdmission(
            owner_rule="test.normalized.recording.v1",
            source_content_hash=gy_recorded_content_hash(normalized),
            projector=lambda value: dict(value),
        )
        return run, normalized, (admission,)

    monkeypatch.setattr(
        validator,
        "_build_pending_payload",
        lambda *args, **kwargs: {"runtime_metrics": {"lane": "cached"}},
    )
    monkeypatch.setattr(
        validator,
        "_domain_run_and_normalized_recording",
        _rederive,
    )
    monkeypatch.setattr(
        validator,
        "_controlled_recording_receipt_blocks",
        lambda *args, **kwargs: (("/fixture", {}),),
    )
    monkeypatch.setattr(
        validator,
        "_depth_summary_comparison_admissions",
        lambda *args, **kwargs: (),
    )

    payload, _ = await validator._complete_payload_from_recordings(
        tmp_path,
        recordings=source,
        historical_domain_runs=historical,
    )

    assert {
        role: recording["recording_content_hash"]
        for role, recording in payload["proof_recordings"].items()
    } == {
        role: f"normalized-{role}"
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    }


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


def test_first_vertical_run_reaches_measured_grounding_gap_and_n7_route() -> None:
    """Record the cold run's real grounding gap rather than transplanting Stage 2."""

    _, payload = _complete_universality_payload()
    run = payload["domain_runs"]["first_vertical"]
    stages = run["stage_trace"]

    assert stages["generation"]["attempted"] is True
    assert stages["grounding"]["attempted"] is True
    assert stages["simulation"]["attempted"] is True
    assert stages["value"]["attempted"] is True
    assert stages["value"]["status"] == "value_blocked"
    assert stages["acquisition"]["attempted"] is True
    assert stages["acquisition"]["route_kind"] == "n7_requirement_gap"
    assert stages["acquisition"]["planner_report_content_hash"].startswith(
        "sha256:"
    )
    assert run["promotion_reached"] is False
    assert run["terminal_distribution"]["terminal_kind"] == "acquisition_required"
    assert run["terminal_distribution"]["evidence_kind"] == "owner_acquisition_route"
    assert run["terminal_distribution"]["decision_grade"] == "blocked"


def test_universality_terminal_gate_measures_routes_and_rejects_relabeling() -> None:
    """Recompute frozen owner witnesses and reject fake hashes or label transplants."""

    validator, payload = _complete_universality_payload()
    domain_runs = copy.deepcopy(payload["domain_runs"])

    assert validator._domain_terminal_honesty_issues(
        domain_runs,
        expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
    ) == []

    fabricated_route = copy.deepcopy(domain_runs)
    fabricated_route["first_vertical"]["stage_trace"]["acquisition"][
        "planner_report_content_hash"
    ] = "sha256:" + "0" * 64
    assert "domain_acquisition_route_unverified" in {
        issue["code"]
        for issue in validator._domain_terminal_honesty_issues(
            fabricated_route,
            expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
        )
    }

    relabeled = copy.deepcopy(domain_runs)
    relabeled["first_vertical"]["terminal_distribution"][
        "evidence_kind"
    ] = "owner_data_gap"
    assert "domain_degradation_class_mismatch" in {
        issue["code"]
        for issue in validator._domain_terminal_honesty_issues(
            relabeled,
            expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
        )
    }

    fabricated_terminal = copy.deepcopy(domain_runs)
    fabricated_terminal["first_vertical"]["terminal"]["kind"] = (
        "grounded_admissible"
    )
    fabricated_terminal["first_vertical"]["terminal_distribution"][
        "terminal_kind"
    ] = "grounded_admissible"
    assert "domain_terminal_not_honest_degradation" in {
        issue["code"]
        for issue in validator._domain_terminal_honesty_issues(
            fabricated_terminal,
            expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
        )
    }

    monoculture = {
        role: copy.deepcopy(domain_runs["first_vertical"])
        for role in domain_runs
    }
    assert "domain_degradation_class_denominator_missing" in {
        issue["code"]
        for issue in validator._domain_terminal_honesty_issues(
            monoculture,
            expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
        )
    }


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        (
            "authority_scope",
            "production",
            "domain_promotion_authority_scope_invalid",
        ),
        (
            "reason",
            "confidence_ledger_refused:ledger_scope_binding_mismatch",
            "domain_promotion_reason_invalid",
        ),
        (
            "authority_provenance",
            ["not_established"],
            "domain_promotion_authority_provenance_invalid",
        ),
    ],
)
def test_domain_promotion_boundary_corruptions_fail_named(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    """Authority-source fields fail independently after outer hashes are valid."""

    validator, payload = _complete_universality_payload()
    domain_runs = copy.deepcopy(payload["domain_runs"])
    for run in domain_runs.values():
        run["stage_trace"]["promotion"].update(
            {
                "authority_scope": "contract_testing",
                "authority_provenance": ["verification"],
                "reason": "verification_n9_sequence_non_consumer",
                "receipt_count": 1,
                "all_receipts_non_consumer": True,
            }
        )
    domain_runs["education"]["stage_trace"]["promotion"][field] = value

    assert expected_code in {
        issue["code"]
        for issue in validator._domain_terminal_honesty_issues(
            domain_runs,
            expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
        )
    }


def test_compiled_authority_projection_rejects_unestablished_consumer_posture() -> None:
    """A missing per-receipt consumer fact cannot collapse to non-consumer."""

    validator = _universality_contract_validator()
    projection = validator._compiled_authority_source_projection(
        {
            "recursive_run": {
                "authority_scope": "contract_testing",
                "nodes": [
                    {
                        "node_ref": "design://verification/root",
                        "cycle_run": {
                            "promotion_port": {
                                "status": "not_promoted",
                                "reason": "verification_n9_sequence_non_consumer",
                                "certified_candidate_ids": [],
                                "receipts": [
                                    {
                                        "confidence_ledger_projection": {
                                            "authority_provenance": "verification"
                                        }
                                    }
                                ],
                            }
                        },
                    }
                ],
            }
        }
    )

    assert validator._controlled_authority_source_projection_issues(projection) == (
        "authority_source_promotion_0_consumer_posture_invalid",
    )


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


def test_education_terminal_precedence_uses_deep_advisor_refusal() -> None:
    """The real advisor refusal outranks the earlier grounding acquisition route."""

    validator, payload = _complete_universality_payload()
    education = payload["domain_runs"]["education"]

    assert education["stage_trace"]["acquisition"]["attempted"] is True
    assert education["stage_trace"]["grounding"]["owner_observation"][
        "acquisition_requirement"
    ] is not None
    assert education["stage_trace"]["value"]["owner_observation"][
        "method_selection_receipt"
    ]["selection_authority"] == "foundry_registry_advisor"
    assert education["evidence_witness"]["kind"] == "estimand_binding_refusal"
    assert validator._domain_terminal_honesty_issues(
        payload["domain_runs"],
        expectation=validator.UNIVERSALITY_TERMINAL_EXPECTATION,
    ) == []


def test_education_advisor_denominator_is_recomputed_from_live_catalog() -> None:
    """A content-valid receipt from a forged catalog denominator stays non-authoritative."""

    validator, payload = _complete_universality_payload()
    education = payload["domain_runs"]["education"]
    value_stage = education["stage_trace"]["value"]
    observation = value_stage["owner_observation"]
    receipt = observation["method_selection_receipt"]
    receipt["denominator"] = sorted(
        [*receipt["denominator"], "forged.family.outside_live_catalog@9.9.9"]
    )
    receipt["content_hash"] = validator._semantic_hash(
        {key: value for key, value in receipt.items() if key != "content_hash"}
    )
    value_stage["advisor_selection_receipt_content_hash"] = receipt["content_hash"]
    value_stage["owner_observation_content_hash"] = validator._semantic_hash(
        observation
    )
    education["content_hash"] = validator._semantic_hash(
        {key: value for key, value in education.items() if key != "content_hash"}
    )
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    report = validator.validate_payload(payload)

    assert "domain_owner_observation_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_value_owner_observation_cannot_be_transplanted_across_candidates() -> None:
    """A real advisor receipt from another candidate is not evidence for this run."""

    validator, payload = _complete_universality_payload()
    education = payload["domain_runs"]["education"]
    value_stage = education["stage_trace"]["value"]
    observation = value_stage["owner_observation"]
    observation["candidate_id"] = "candidate_transplanted_from_another_run"
    value_stage["owner_observation_content_hash"] = validator._semantic_hash(
        observation
    )
    education["content_hash"] = validator._semantic_hash(
        {key: value for key, value in education.items() if key != "content_hash"}
    )
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    report = validator.validate_payload(payload)

    assert "domain_owner_observation_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_education_refusal_rejects_transplanted_early_acquisition_report() -> None:
    """Deep refusal precedence does not excuse a forged earlier N7 route."""

    validator, payload = _complete_universality_payload()
    education = payload["domain_runs"]["education"]
    report = education["terminal"]["costed_plan"]["canonical_planner_report"]
    report["acquisition_records"][0]["requirement_gap_ref"] = (
        "requirement-gap:data_requirement:transplanted"
    )
    report_hash = validator._semantic_hash(report)
    education["stage_trace"]["acquisition"][
        "planner_report_content_hash"
    ] = report_hash
    witness = education["evidence_witness"]
    witness["grounding_route"]["planner_report_content_hash"] = report_hash
    witness["content_hash"] = validator._semantic_hash(
        {key: value for key, value in witness.items() if key != "content_hash"}
    )
    education["content_hash"] = validator._semantic_hash(
        {key: value for key, value in education.items() if key != "content_hash"}
    )
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    validation = validator.validate_payload(payload)

    assert "domain_owner_observation_invalid" in {
        issue["code"] for issue in validation["issues"]
    }


def test_terminal_evidence_requires_typed_owner_observations() -> None:
    """Blocker strings and matching labels cannot substitute for owner artifacts."""

    validator, payload = _complete_universality_payload()
    education = payload["domain_runs"]["education"]
    education["stage_trace"]["grounding"].pop("owner_observation", None)
    education["stage_trace"]["grounding"].pop(
        "owner_observation_content_hash", None
    )
    education["stage_trace"]["value"].pop("owner_observation", None)
    education["stage_trace"]["value"].pop(
        "owner_observation_content_hash", None
    )
    education["content_hash"] = validator._semantic_hash(
        {key: value for key, value in education.items() if key != "content_hash"}
    )
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    report = validator.validate_payload(payload)

    assert "domain_owner_observation_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_unseen_domain_reaches_typed_terminal_without_vertical_contamination() -> None:
    """Fail closed for a no-pack energy problem without borrowing known-domain vocabulary."""

    _, payload = _complete_universality_payload()
    run = payload["domain_runs"]["unseen"]
    recording = payload["proof_recordings"]["unseen"]
    serialized = json.dumps(
        {"run": run, "proof_recording": recording},
        sort_keys=True,
    ).casefold()

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
    assert recording["n4_recording"]["status"] == (
        "cycle_substrate_context_unavailable"
    )
    assert "responses" not in recording["n4_recording"]
    assert "owner_result_projection" not in recording["n4_recording"]
    owner_vocab: set[str] = set()
    for known_role in ("first_vertical", "education"):
        known_recording = payload["proof_recordings"][known_role]
        projection = known_recording["n4_recording"]["owner_result_projection"]
        for proposed in projection["proposed_interventions"]:
            owner_vocab.update(
                str(proposed.get(field) or "").casefold()
                for field in ("operator_kind", "trinity_kind")
                if proposed.get(field)
            )
        known_problem = payload["domain_runs"][known_role]["design_problem"]
        owner_vocab.add(
            str(known_problem["outcome_of_interest"]["target_variable"]).casefold()
        )
    for forbidden in sorted(owner_vocab):
        assert forbidden not in serialized


def test_pinned_fixture_replacement_is_rejected_after_hash_recompute() -> None:
    """Make committed-fixture substitution behaviorally RED, not merely hash-invalid."""

    validator = _universality_contract_validator()
    payload = json.loads(
        (REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8")
    )
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


def test_unseen_vertical_contamination_is_rejected_after_hash_recompute() -> None:
    """A recomputed capstone cannot borrow pack, WMR, or lever vocabulary."""

    validator = _universality_contract_validator()
    baseline = json.loads(
        (REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8")
    )
    owner_vocabulary = validator._known_vertical_vocabulary(baseline)
    assert "tax_relief_rate" in owner_vocabulary
    assert "school_quality" in owner_vocabulary
    assert "household_cells.disposable_income" in owner_vocabulary

    for borrowed_token in (
        "tax_relief_rate",
        "school_quality",
        "household_cells.disposable_income",
    ):
        payload = copy.deepcopy(baseline)
        unseen = payload["domain_runs"]["unseen"]
        unseen["fabricated_diagnostic"] = borrowed_token
        stable_run = {
            key: value for key, value in unseen.items() if key != "content_hash"
        }
        unseen["content_hash"] = validator._semantic_hash(stable_run)
        payload["contract_content_hash"] = validator._contract_content_hash(payload)

        report = validator.validate_payload(payload)

        assert "unseen_domain_vertical_contamination" in {
            issue["code"] for issue in report["issues"]
        }


def test_n10_source_flip_denominator_covers_every_local_decisive_property() -> None:
    """Freeze the N10-local mutation denominator; owner harnesses remain additive."""

    validator = _universality_contract_validator()

    assert [case.mutation_id for case in validator._n10_source_flip_cases()] == [
        "domain_pinned_in_engine",
        "cycle_driven_by_pinned_fixture",
        "unseen_domain_honesty_removed",
        "no_context_generation_authority_fence_removed",
        "acquisition_route_verification_removed",
        "canonical_route_recompute_removed",
        "degradation_class_relabel_accepted",
        "fabricated_terminal_accepted",
        "degradation_class_denominator_weakened",
        "education_refusal_precedence_removed",
        "live_advisor_denominator_verification_removed",
        "value_owner_candidate_binding_removed",
        "historical_receipt_verification_removed",
        "controlled_replay_drift_reporting_removed",
        "operational_clock_preservation_removed",
        "unbound_estimand_authority_fence_removed",
        "n7_design_problem_authority_removed",
        "lex_reference_mount_path_independence_removed",
    ]


def test_controlled_replay_drift_reporting_source_flip_turns_red() -> None:
    """Deleting computed diagnostics while retaining markers fails behaviorally."""

    validator = _universality_contract_validator()
    case = next(
        case
        for case in validator._n10_source_flip_cases()
        if case.mutation_id == "controlled_replay_drift_reporting_removed"
    )

    result = validator._run_n10_source_flip(REPO_ROOT, case)

    assert result["result"] == "RED", result


def test_n10_gap_reconciliation_closes_five_seams_and_retains_two_residuals() -> None:
    """Freeze the full-denominator gap triage with owner-bound seam evidence."""

    report = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json"
        ).read_text(encoding="utf-8")
    )
    gaps = {row["gap_id"]: row for row in report["gaps"]}
    closed = {
        "s0_to_n4_l6_bridge_missing",
        "s0_to_n5_wmr_bridge_missing",
        "s0_to_l6_world_slot_bridge_missing",
        "n8_transport_tuple_hardcode",
        "n6_single_terminal_validation_gap",
    }
    residual = {
        "owner_registration_derivation_missing",
        "journal_raw_evidence_persistence_missing",
    }

    assert set(gaps) == closed | residual
    for gap_id in closed:
        gap = gaps[gap_id]
        assert gap["status"] == "closed"
        assert gap["capability_label"] == "closed"
        assert gap["disposition"] == "closed_by_live_behavioral_receipt"
        witness = gap["owner_evidence"]["seam_witness"]
        assert witness["segment_content_hash"].startswith("sha256:")
        assert witness["source_path"].startswith("src/polisyos/")
    for gap_id in residual:
        gap = gaps[gap_id]
        assert gap["status"] == "typed_residual"
        assert gap["capability_label"] == "artifact_missing"
        assert "acquisition infrastructure" in gap["disposition"]


def test_n10_ledger_lands_only_after_s2_and_gyg_strangles() -> None:
    """Reconcile GY-N10 only when both DELETE owners are behaviorally strangled."""

    ledger = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/"
            "layer3_gy_generation_cycle_disposition_ledger.json"
        ).read_text(encoding="utf-8")
    )
    owners = {row["owner_id"]: row for row in ledger["owners"]}
    capstone = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/"
            "layer3_gy_depth_n_universality_contract.json"
        ).read_text(encoding="utf-8")
    )
    gaps = {
        row["gap_id"]: row
        for row in json.loads(
            (
                REPO_ROOT
                / "architecture/policy_design_case/"
                "layer3_gy_second_domain_free_grow_gaps.json"
            ).read_text(encoding="utf-8")
        )["gaps"]
    }

    assert ledger["tasks"]["GY-N10"]["status"] == "landed"
    for owner_id in (
        "s2_fixed_candidate_as_generator",
        "gy_g_s3_fixture_only_demonstrations",
    ):
        receipt = owners[owner_id]["strangle_receipt"]
        assert receipt["status"] == "strangled"
        assert receipt["remaining_callers"] == []
    s2_parallel = next(
        row
        for row in ledger["parallel_world_reconciliation"]
        if row["parallel_world"] == "S2 shadow design search"
    )
    assert s2_parallel["status"] == "pending_strangle_under_GY-N6"
    assert capstone["gy_g_strangle_receipt"]["status"] == "strangled"
    assert capstone["gy_g_strangle_receipt"]["production_fixture_callers"] == []
    education = capstone["domain_runs"]["education"]
    assert education["promotion_reached"] is False
    assert education["stage_trace"]["promotion"]["certified_candidate_ids"] == []
    assert gaps["s0_to_l6_world_slot_bridge_missing"]["owner_evidence"][
        "positive_writable_count"
    ] == 0


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


def test_content_hash_exclusion_declaration_is_canonical() -> None:
    """The artifact cannot redefine which operational fields escape identity."""

    validator, payload = _complete_universality_payload()
    payload["content_hash_excluded_fields"] = []
    payload["contract_content_hash"] = validator._contract_content_hash(payload)

    report = validator.validate_payload(payload)

    assert "content_hash_exclusion_declaration_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_corrupt_drift_uses_frozen_payload_without_live_rederive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A static corruption probe must not enter live async owner lanes."""

    validator = _universality_contract_validator()
    output = tmp_path / validator.OUTPUT_PATH
    payload = json.loads(
        (REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8")
    )
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        validator,
        "build_live_payload",
        lambda *args, **kwargs: pytest.fail("corrupt drift entered live rederive"),
    )

    report = validator.corrupt_field_drift_check(tmp_path)

    assert report["status"] == "fail"
    assert [case["mutation_id"] for case in report["cases"]] == [
        "stale_contract_hash",
        "evidence_kind_relabel",
        "evidence_witness_forgery",
        "planner_report_semantic_drift",
        "forged_route_hash",
        "promotion_authority_scope",
        "promotion_reason",
        "promotion_authority_provenance",
        "promotion_receipt_count",
        "authority_source_migration_receipt",
        "authority_source_admission_relabel",
        "authority_source_role_rule_relabel",
        "compiler_response_bytes",
        "n4_response_bytes",
        "compiled_recursive_bytes",
        "compiled_schema_rehashed",
        "terminal_distribution_projection",
        "fabricated_terminal",
    ]
    assert {case["status"] for case in report["cases"]} == {"red"}
    promotion_scope = next(
        case
        for case in report["cases"]
        if case["mutation_id"] == "promotion_authority_scope"
    )
    assert promotion_scope["detection_phase"] == "identity_recomputation"
    assert promotion_scope["observed_issue_codes"] == [
        "depth_verification_summary_shape_invalid"
    ]


def test_corrupt_drift_refuses_missing_or_invalid_baseline(tmp_path: Path) -> None:
    """A missing or already-red base cannot masquerade as mutation evidence."""

    validator = _universality_contract_validator()
    missing = validator.corrupt_field_drift_check(tmp_path)
    assert missing["status"] == "fail"
    assert missing["issues"] == [
        {"code": "universality_contract_artifact_missing"}
    ]

    output = tmp_path / validator.OUTPUT_PATH
    output.parent.mkdir(parents=True)
    payload = json.loads(
        (REPO_ROOT / validator.OUTPUT_PATH).read_text(encoding="utf-8")
    )
    payload["proof_status"] = "proof_runs_pending"
    output.write_text(json.dumps(payload), encoding="utf-8")

    invalid = validator.corrupt_field_drift_check(tmp_path)
    assert invalid["status"] == "fail"
    assert invalid["cases"] == []
    assert invalid["issues"][0]["code"] == "corrupt_field_drift_baseline_invalid"


def test_universality_write_is_byte_stable(tmp_path: Path) -> None:
    """Write the incomplete Task-12 payload only to an explicit noncanonical path."""

    validator = _universality_contract_validator()
    output = tmp_path / "proof.json"

    first = validator.write_payload(REPO_ROOT, output)
    second = validator.write_payload(REPO_ROOT, output)

    assert first == second == output.read_bytes()


def test_canonical_writer_preserves_operational_values_on_semantic_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equal semantic content retains prior clocks instead of churning bytes."""

    validator = _universality_contract_validator()
    output = tmp_path / validator.OUTPUT_PATH
    comparison_plan = validator.GyComparisonProjectionPlan(entries=())
    prior = {
        "domain_runs": {
            "first_vertical": {
                "generated_at": "2026-07-15T00:00:00Z",
                "wall_time_ms": 1.0,
                "terminal": "acquisition_required",
            }
        },
        "runtime_metrics": {"lane": "cached", "elapsed_seconds": 2.0},
    }
    validator._set_artifact_identities(prior, comparison_plan)
    current = copy.deepcopy(prior)
    current["domain_runs"]["first_vertical"]["generated_at"] = "2026-07-15T01:00:00Z"
    current["domain_runs"]["first_vertical"]["wall_time_ms"] = 99.0
    current["runtime_metrics"]["elapsed_seconds"] = 100.0
    validator._set_artifact_identities(current, comparison_plan)
    output.parent.mkdir(parents=True)
    output.write_text(validator._canonical_json(prior) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        validator,
        "_build_live_payload_with_plan",
        lambda *args, **kwargs: (copy.deepcopy(current), comparison_plan),
    )
    monkeypatch.setattr(
        validator,
        "validate_payload",
        lambda payload: {"status": "pass", "issues": []},
    )

    data = validator.write_payload(tmp_path, output)

    assert data == (validator._canonical_json(prior) + "\n").encode()


def test_canonical_writer_does_not_carry_clocks_across_semantic_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A semantic delta takes the full rewrite branch and keeps current clocks."""

    validator = _universality_contract_validator()
    output = tmp_path / validator.OUTPUT_PATH
    comparison_plan = validator.GyComparisonProjectionPlan(entries=())
    prior = {
        "domain_runs": {
            "first_vertical": {
                "generated_at": "2026-07-15T00:00:00Z",
                "terminal": "acquisition_required",
            }
        },
    }
    validator._set_artifact_identities(prior, comparison_plan)
    current = {
        "domain_runs": {
            "first_vertical": {
                "generated_at": "2026-07-16T00:00:00Z",
                "terminal": "grounded_abstention",
            }
        },
    }
    validator._set_artifact_identities(current, comparison_plan)
    output.parent.mkdir(parents=True)
    output.write_text(validator._canonical_json(prior) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        validator,
        "_build_live_payload_with_plan",
        lambda *args, **kwargs: (copy.deepcopy(current), comparison_plan),
    )
    monkeypatch.setattr(
        validator,
        "validate_payload",
        lambda payload: {"status": "pass", "issues": []},
    )

    data = validator.write_payload(tmp_path, output)
    written = json.loads(data)

    assert written["domain_runs"]["first_vertical"] == current["domain_runs"]["first_vertical"]


def test_rederive_audit_compares_semantics_without_clock_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioral replay ignores only canonical operational-value movement."""

    validator = _universality_contract_validator()
    output = tmp_path / validator.OUTPUT_PATH
    comparison_plan = validator.GyComparisonProjectionPlan(entries=())
    committed = {
        "domain_runs": {
            "first_vertical": {
                "generated_at": "2026-07-15T00:00:00Z",
                "terminal": "acquisition_required",
            }
        },
    }
    validator._set_artifact_identities(committed, comparison_plan)
    live = copy.deepcopy(committed)
    live["domain_runs"]["first_vertical"]["generated_at"] = "2026-07-15T01:00:00Z"
    validator._set_artifact_identities(live, comparison_plan)
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(committed), encoding="utf-8")
    monkeypatch.setattr(
        validator,
        "check_provenance_stability",
        lambda root: {"status": "stable", "issues": []},
    )
    monkeypatch.setattr(
        validator,
        "_build_live_payload_with_plan",
        lambda *args, **kwargs: (copy.deepcopy(live), comparison_plan),
    )
    monkeypatch.setattr(
        validator,
        "validate_payload",
        lambda payload: {"status": "pass", "issues": []},
    )

    assert validator._rederive_audit(tmp_path) == {
        "status": "pass",
        "issues": [],
    }


def test_depth_n_verification_summary_shape_fails_closed() -> None:
    validator = _universality_contract_validator()
    summary = validator._with_depth_promotion_summary_identity(
        {
            "node_ref": "node://verification",
            "status": "not_promoted",
            "reason": "verification_n9_sequence_non_consumer",
            "receipt_count": 1,
            "authority_provenance": ["verification"],
            "all_receipts_non_consumer": True,
            "certified_candidate_ids": [],
        },
        projection_scope="depth_n_compiled_verification_promotion_summary",
    )
    assert validator._depth_verification_summary_shape_valid(summary)

    mixed = copy.deepcopy(summary)
    mixed["authority_provenance"] = ["verification", "canonical_repo"]
    assert not validator._depth_verification_summary_shape_valid(mixed)

    unrecognized = copy.deepcopy(summary)
    unrecognized["authority_provenance"] = ["untrusted_verification_extension"]
    assert not validator._depth_verification_summary_shape_valid(unrecognized)

    absent = copy.deepcopy(summary)
    absent.pop("authority_provenance")
    assert not validator._depth_verification_summary_shape_valid(absent)


def test_depth_n_summary_admission_requires_parent_projection_and_receipt_denominator() -> None:
    """A summary cannot self-attest past its validated full-receipt parents."""

    validator = _universality_contract_validator()
    payload: dict[str, object] = {"domain_runs": {}, "proof_recordings": {}}
    counts: dict[str, int] = {}
    for index, role in enumerate(validator.PLAIN_LANGUAGE_PROOF_REQUESTS):
        node_ref = f"node://{role}/{index}"
        compiled_run = {
            "recursive_run": {
                "authority_scope": "contract_testing",
                "nodes": [
                    {
                        "node_ref": node_ref,
                        "cycle_run": {
                            "promotion_port": {
                                "status": "not_promoted",
                                "reason": "verification_n9_sequence_non_consumer",
                                "receipts": [
                                    {
                                        "consumer_promotable": False,
                                        "confidence_ledger_projection": {
                                            "authority_provenance": "verification"
                                        },
                                    }
                                ],
                                "certified_candidate_ids": [],
                            }
                        },
                    }
                ],
            }
        }
        compiled_projection = validator._compiled_authority_source_projection(compiled_run)
        stage_summary = {
            "all_receipts_non_consumer": True,
            "attempted": True,
            "authority_provenance": ["verification"],
            "authority_scope": "contract_testing",
            "certified_candidate_ids": [],
            "owner": "polisyos.runtime.quality.promotion_sequence.CanonicalN9PromotionPort",
            "reason": "verification_n9_sequence_non_consumer",
            "receipt_count": 1,
            "status": "not_promoted",
        }
        payload["proof_recordings"][role] = {
            "compiled_run": compiled_run,
            "authority_source_admission": {
                "authority_projection": copy.deepcopy(compiled_projection)
            },
            "authority_source_migration_receipt": {
                "replayed_authority_projection": copy.deepcopy(compiled_projection)
            },
        }
        payload["domain_runs"][role] = {"stage_trace": {"promotion": stage_summary}}
        counts[role] = 1

    admissions = validator._depth_summary_comparison_admissions(
        payload,
        receipt_counts_by_role=counts,
    )
    assert len(admissions) == len(validator.PLAIN_LANGUAGE_PROOF_REQUESTS)
    assert all(admission.action == "exclude" for admission in admissions)
    assert all(
        admission.predicate_provenance == "independently_reconciled"
        for admission in admissions
    )

    first_role = next(iter(validator.PLAIN_LANGUAGE_PROOF_REQUESTS))
    parent_shift = copy.deepcopy(payload)
    parent_shift["proof_recordings"][first_role]["authority_source_admission"][
        "authority_projection"
    ]["promotions"][0]["receipt_count"] = 2
    with pytest.raises(
        validator.UniversalityContractError,
        match="depth_summary_parent_receipt_binding_invalid",
    ):
        validator._depth_summary_comparison_admissions(
            parent_shift,
            receipt_counts_by_role=counts,
        )

    wrong_counts = {**counts, first_role: 2}
    with pytest.raises(
        validator.UniversalityContractError,
        match="depth_summary_receipt_denominator_mismatch",
    ):
        validator._depth_summary_comparison_admissions(
            payload,
            receipt_counts_by_role=wrong_counts,
        )


def test_depth_outer_plan_composes_recording_roots_with_stage_summaries_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root admission owns embedded summaries; only stage summaries remain siblings."""

    validator, payload = _complete_universality_payload()
    _allow_manual_receipt_proofs_for_projection_test(monkeypatch, validator)
    recording_admissions = []
    receipt_counts: dict[str, int] = {}
    for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS:
        recording = payload["proof_recordings"][role]
        receipt_counts[role] = len(_recording_receipts(recording))
        recording_admissions.append(
            validator._admit_controlled_recording_for_comparison(
                recording,
                role=role,
                receipt_proofs=_manual_receipt_comparison_admissions(recording),
            )
        )
    summary_admissions = validator._depth_summary_comparison_admissions(
        payload,
        receipt_counts_by_role=receipt_counts,
    )

    plan = build_gy_comparison_projection_plan(
        payload,
        admissions=tuple(recording_admissions) + summary_admissions,
    )
    projected = plan.project(payload)

    assert len(plan.manifest) == 2 * len(validator.PLAIN_LANGUAGE_PROOF_REQUESTS)
    assert all(
        "promotions"
        not in projected["proof_recordings"][role]["authority_source_admission"][
            "authority_projection"
        ]
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    )
    assert all(
        "promotions"
        not in projected["proof_recordings"][role][
            "authority_source_migration_receipt"
        ]["replayed_authority_projection"]
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    )
    assert all(
        not validator._CONTROLLED_RECORDING_ADMISSION_COMPARISON_IDENTITIES
        & set(projected["proof_recordings"][role]["authority_source_admission"])
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    )
    assert all(
        not validator._CONTROLLED_RECORDING_MIGRATION_COMPARISON_IDENTITIES
        & set(
            projected["proof_recordings"][role][
                "authority_source_migration_receipt"
            ]
        )
        for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS
    )
    assert plan.preserve_admitted_blocks(payload, payload) == payload

    first_role = next(iter(validator.PLAIN_LANGUAGE_PROOF_REQUESTS))
    tampered = copy.deepcopy(payload["proof_recordings"][first_role])
    tampered["authority_source_admission"]["authority_projection"]["promotions"][
        0
    ]["receipt_count"] += 1
    _refresh_recording_hashes(tampered)
    with pytest.raises(
        ValueError,
        match="controlled_recording_summary_admission_binding_invalid",
    ):
        validator._admit_controlled_recording_for_comparison(
            tampered,
            role=first_role,
            receipt_proofs=_manual_receipt_comparison_admissions(tampered),
        )


def test_universality_validator_refuses_wrong_checkout(tmp_path: Path) -> None:
    """Refuse a foreign PolicyOS package before parsing a proof mode or writing output."""

    wrong_src = _create_wrong_checkout_package(tmp_path)
    canonical_output = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
    )
    before = canonical_output.read_bytes()

    result = _run_universality_validator_with_pythonpath(wrong_src, "--write")

    assert result.returncode == 1
    assert "wrong_checkout_resolved" in result.stdout + result.stderr
    assert canonical_output.read_bytes() == before


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
    assert result.returncode == 0
    assert isinstance(wall_time_seconds, float)
    assert wall_time_seconds > 0.0
    assert payload == {
        "issues": [],
        "outputs": [
            "architecture/policy_design_case/"
            "layer3_gy_depth_n_universality_contract.json"
        ],
        "status": "pass",
    }
    assert result.stderr == ""
