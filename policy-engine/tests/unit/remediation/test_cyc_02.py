"""CYC-02 witnesses for durable N5 output and conditional N8 use."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleError,
    JointSimulationPort,
    _DefaultSimulationBoundFoundryValuePort,
    simulation_evaluation_input_ref,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
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
from tests.unit.runtime.quality.test_generation_cycle import _cyc01_owner_bound_n5_case
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def _real_n5_observation(tmp_path: Path):
    """Run the canonical N5 producer through the real generation-cycle adapter."""

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    request = _request(
        record=context.world_model_record,
        world_model_record_ref=context.world_model_record.world_model_record_id,
    )
    problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "joint_simulation_request": request,
            }
        }
    )
    producer = JointSimulationHorizonController()
    produced_results: list[object] = []

    class _RecordingN5Controller:
        def run(self, concrete_request):
            result = producer.run(concrete_request)
            produced_results.append(result)
            return result

    observation = JointSimulationPort(
        controller=_RecordingN5Controller(),
        repo_root=tmp_path,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)
    assert observation.status == "joint_simulated"
    assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
    assert len(produced_results) == 1
    return problem, context, candidate, observation, produced_results[0]


def test_k_sim_limitation_remains_a_usable_simulation_input(tmp_path: Path) -> None:
    """K_sim limits authority, but does not make the real N5 input disappear."""

    _problem, _context, _candidate, simulation, _produced = _real_n5_observation(tmp_path)

    input_ref = simulation_evaluation_input_ref(simulation)

    assert input_ref is not None
    assert input_ref.content_hash == simulation.simulation_ref
    assert simulation.simulation_result_ref is not None


def test_conditional_n8_status_is_not_authority_ready(tmp_path: Path) -> None:
    """The simulation-only value state is explicit and cannot carry N8 receipts."""

    problem, context, candidate, simulation, produced = _real_n5_observation(tmp_path)
    observation = _DefaultSimulationBoundFoundryValuePort(
        repo_root=tmp_path,
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_conditional", observation.model_dump(mode="json")
    assert observation.value_receipt is None
    assert observation.method_selection_receipt is None
    assert "simulation_only_k_sim_not_world_evidence" in observation.authority_blockers
    assert simulation.simulation_result_ref is not None
    assert isinstance(simulation.simulation_result_ref, CASArtifactRef)
    assert observation.value_ref == str(simulation.simulation_result_ref.artifact_id)

    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    reopened = load_joint_simulation_result(
        simulation.simulation_result_ref,
        repo_root=tmp_path,
        expected_world_model_record_content_hash=context.world_model_record.content_hash,
    )
    outcome = problem.outcome_of_interest.target_variable
    trajectory = next(
        trajectory
        for trajectory in reopened.trajectories
        if trajectory.points and outcome in trajectory.points[0].effect
    )
    effect = trajectory.points[0].effect[outcome]
    assert isinstance(effect, float)
    produced_trajectory = next(
        candidate_trajectory
        for candidate_trajectory in produced.trajectories
        if candidate_trajectory.run_level == trajectory.run_level
        and candidate_trajectory.atom_ids == trajectory.atom_ids
        and candidate_trajectory.points
        and outcome in candidate_trajectory.points[0].effect
    )
    assert effect == produced_trajectory.points[0].effect[outcome]


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

    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    reopened = load_joint_simulation_result(
        result_ref,
        repo_root=tmp_path,
        expected_world_model_record_content_hash=(
            root_node.joint_simulation.world_model_record_content_hash
        ),
        expected_atom_ids=root_node.joint_simulation.atom_ids,
    )
    assert reopened.trajectories == root_node.joint_simulation.trajectories
    assert reopened.world_model_record_content_hash == (
        root_node.joint_simulation.world_model_record_content_hash
    )

    missing_ref = CASArtifactRef(
        artifact_id="sha256:" + "f" * 64,
        kind=result_ref.kind,
        media_type=result_ref.media_type,
    )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_unavailable"):
        load_joint_simulation_result(missing_ref, repo_root=tmp_path)

    blob_path, manifest_path = store.get_paths(result_ref.artifact_id)
    original_blob = blob_path.read_bytes()
    blob_path.write_bytes(original_blob + b"tampered")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, repo_root=tmp_path)
    finally:
        blob_path.write_bytes(original_blob)

    original_manifest = manifest_path.read_bytes()
    manifest_path.write_bytes(b"{}")
    try:
        with pytest.raises(
            GenerationCycleError,
            match="joint_simulation_result_integrity_invalid",
        ):
            load_joint_simulation_result(result_ref, repo_root=tmp_path)
    finally:
        manifest_path.write_bytes(original_manifest)

    with pytest.raises(GenerationCycleError, match="joint_simulation_result_wmr_mismatch"):
        load_joint_simulation_result(
            result_ref,
            repo_root=tmp_path,
            expected_world_model_record_content_hash="sha256:" + "e" * 64,
        )
    with pytest.raises(GenerationCycleError, match="joint_simulation_result_atom_binding"):
        load_joint_simulation_result(
            result_ref,
            repo_root=tmp_path,
            expected_atom_ids=("foreign-model-atom",),
        )
