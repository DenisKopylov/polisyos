"""CYC-02 witnesses for durable N5 output and conditional N8 use."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.generation_cycle import (
    SimulationPortObservation,
    ValuePortObservation,
    load_joint_simulation_result,
    simulation_evaluation_input_ref,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from tests.unit.runtime.quality.test_depth_n_universality import (
    _lane0_coupled_request,
    _lane0_cycle_controller_factory,
    _lane0_subdesigns,
    _recursive_budget_state,
    _recursive_problem,
)


def test_k_sim_limitation_remains_a_usable_simulation_input() -> None:
    """K_sim limits authority, but does not make the real N5 input disappear."""

    simulation = SimulationPortObservation(
        candidate_id="candidate-cyc-02",
        status="joint_simulated",
        simulation_ref="sha256:" + "1" * 64,
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
    )

    input_ref = simulation_evaluation_input_ref(simulation)

    assert input_ref is not None
    assert input_ref.content_hash == simulation.simulation_ref


def test_conditional_n8_status_is_not_authority_ready() -> None:
    """The simulation-only value state is explicit and cannot carry N8 receipts."""

    observation = ValuePortObservation(
        status="value_conditional",
        candidate_id="candidate-cyc-02",
        value_ref="artifact://n5/result",
        authority_blockers=("simulation_only_k_sim_not_world_evidence",),
        reason="Conditional simulation output; not empirical or action authority.",
        decision_grade="low",
    )

    assert observation.status == "value_conditional"
    assert observation.value_receipt is None
    assert observation.method_selection_receipt is None


@pytest.mark.asyncio
async def test_recursive_n5_result_has_reopenable_cas_reference(tmp_path: Path) -> None:
    """The recursive parent keeps a typed CAS ref to the complete N5 result."""

    root = "design://cyc-02/root"
    child_refs = ("design://cyc-02/a", "design://cyc-02/b")
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-02-cas-result",
    )
    problems = {node_ref: _recursive_problem(node_ref) for node_ref in (root, *child_refs)}
    request = _lane0_coupled_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=problems[root],
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=_lane0_cycle_controller_factory,
        repo_root=tmp_path,
    )

    run = await controller.run(
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

    root_node = next(node for node in run.nodes if node.node_ref == root)
    result_ref = root_node.joint_simulation_ref
    assert result_ref is not None
    assert result_ref.kind == "polisyos.runtime.joint_simulation_result"

    store = FileSystemCAS(tmp_path / ".polisyos" / "cas")
    manifest = store.get_manifest(result_ref.artifact_id)
    payload = json.loads(store.get_bytes(result_ref.artifact_id))
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "policyos.runtime.n5.joint_simulation_result"
    assert payload["receipt"]["payload_hash"] == root_node.joint_simulation.receipt.payload_hash
    assert payload["trajectories"]

    reopened = load_joint_simulation_result(
        result_ref,
        repo_root=tmp_path,
        expected_world_model_record_content_hash=(
            root_node.joint_simulation.world_model_record_content_hash
        ),
    )
    assert reopened.trajectories == root_node.joint_simulation.trajectories
    assert reopened.world_model_record_content_hash == (
        root_node.joint_simulation.world_model_record_content_hash
    )
