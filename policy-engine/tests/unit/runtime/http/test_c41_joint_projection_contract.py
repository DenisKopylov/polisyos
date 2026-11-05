"""Candidate-only joint parent status cannot be promoted by container shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import (
    RunCandidateEvaluationAttemptProjection,
    RunCandidateSimulationN5Observation,
    RunGenericCycleSimulationN5Observation,
    RunGenericCycleSimulationProjection,
)


def test_joint_parent_resolution_refuses_blocked_result_even_with_scope_markers() -> None:
    """A blocked parent with scope fields is not a resolved numerical parent."""
    code = "parent_joint_request_binding_not_established"
    row = RunCandidateSimulationN5Observation(
        node_ref="design-problem://" + "a" * 64,
        design_problem_ref="sha256:" + "a" * 64,
        status="simulation_blocked",
        n8_status="value_pending_n8",
        n8_joint_scope_status="not_established",
        n8_joint_scope_limitation_code=code,
        n8_authority_blockers=(code,),
    )
    with pytest.raises(ValidationError, match="run_generic_projection_parent_binding_invalid"):
        RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v5",
            run_id="run-test",
            artifact_status="resolved",
            source_ref=ArtifactRef(
                artifact_id="sha256:" + "b" * 64,
                kind="runtime.compiled_recursive_generation_cycle",
                media_type="application/json",
            ),
            source_content_hash="sha256:" + "c" * 64,
            child_profile_status="not_established",
            child_profile_limitation_code="synthetic_unavailable",
            joint_parent_status="resolved",
            joint_parent_observations=(row,),
        )


def _generic_root_only_projection_payload() -> dict[str, object]:
    """Build one resolved root observation with no configured child profile family."""

    def ref(kind: str, digit: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id="sha256:" + digit * 64,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + digit * 64,
        )

    root_node = "design-problem://" + "a" * 64
    problem_ref = "sha256:" + "a" * 64
    context_ref = ref("runtime.quality.cycle_substrate_context_job", "b")
    profile_ref = ref("runtime.quality.generic_cycle_simulation_profile", "c")
    source_ref = ref("runtime.generation_source_handoff", "d")
    result_ref = ref("polisyos.runtime.joint_simulation_result", "e")
    root_observation = RunGenericCycleSimulationN5Observation(
        node_ref=root_node,
        design_problem_ref=problem_ref,
        cycle_index=0,
        candidate_id="root-candidate",
        status="joint_simulated",
        simulation_result_ref=result_ref,
        simulation_result_body_status="not_established",
        simulation_result_body_limitation_code=(
            "generic_n5_result_body_request_binding_not_established"
        ),
        n4_source_ref=source_ref,
        context_job_ref=context_ref,
        profile_ref=profile_ref,
        child_profile_family_ref=None,
        child_profile_set_ref=None,
        n5_input_ref=ref("runtime.quality.generic_cycle_simulation_n5_input", "6"),
        n5_execution_ref=ref("runtime.quality.generic_cycle_simulation_n5_execution", "7"),
        n5_owner_join_status="resolved",
        n5_request_binding_status="resolved",
        n5_request_content_hash="sha256:" + "8" * 64,
        profile_selection_ref="sha256:" + "9" * 64,
        world_model_record_content_hash="sha256:" + "1" * 64,
        n8_status="value_pending_n8",
        n8_lineage_status="not_established",
        n8_authority_blockers=("value_gate_pending_n8",),
        n8_limitation_code="value_gate_pending_n8",
    )
    first_local_failure = RunCandidateEvaluationAttemptProjection(
        node_ref=root_node,
        candidate_id="first-local-failure",
        candidate_content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        problem_ref=problem_ref,
        attempt_ref="sha256:" + "3" * 64,
        failure_stage="n5",
        simulation_status="simulation_blocked",
        value_status="value_pending_n8",
    )
    return {
        "schema_version": "policyos.runtime.run_generic_cycle_simulation_projection.v5",
        "run_id": "root-only",
        "artifact_status": "resolved",
        "source_ref": ref("runtime.compiled_recursive_generation_cycle", "4"),
        "source_content_hash": "sha256:" + "5" * 64,
        "n4_source_ref": source_ref,
        "n4_source_status": "resolved",
        "parent_context_job_ref": context_ref,
        "parent_profile_ref": profile_ref,
        "parent_profile_id": "root-profile",
        "child_profile_status": "not_established",
        "child_profile_limitation_code": "generic_n4_child_profile_family_not_established",
        "child_profile_bindings": (),
        "n5_observations": (root_observation,),
        "candidate_evaluation_attempts": (first_local_failure,),
    }


def test_root_only_resolved_n5_keeps_child_profile_limitation_and_local_failure() -> None:
    """A resolved root owner join does not establish a child profile family."""
    projection = RunGenericCycleSimulationProjection.model_validate(
        _generic_root_only_projection_payload()
    )

    assert projection.child_profile_status == "not_established"
    assert projection.child_profile_limitation_code == (
        "generic_n4_child_profile_family_not_established"
    )
    assert projection.child_profile_family_ref is None
    assert projection.child_profile_set_ref is None
    assert projection.child_profile_bindings == ()
    assert len(projection.n5_observations) == 1
    observation = projection.n5_observations[0]
    assert observation.node_ref == "design-problem://" + "a" * 64
    assert observation.n4_source_ref == projection.n4_source_ref
    assert observation.context_job_ref == projection.parent_context_job_ref
    assert observation.profile_ref == projection.parent_profile_ref
    assert observation.child_profile_family_ref is None
    assert observation.child_profile_set_ref is None
    assert observation.n5_owner_join_status == "resolved"
    assert observation.n5_request_binding_status == "resolved"
    assert projection.candidate_evaluation_attempts[0].node_ref == observation.node_ref
    assert projection.candidate_evaluation_attempts[0].cycle_index == observation.cycle_index
    assert projection.candidate_evaluation_attempts[0].failure_stage == "n5"
    assert projection.candidate_evaluation_attempts[0].simulation_status == "simulation_blocked"
    assert projection.candidate_evaluation_attempts[0].failure_scope == "candidate_local"


def test_root_only_observation_refuses_an_unpaired_child_family_reference() -> None:
    """A child family ref cannot appear without its matched set ref."""
    payload = _generic_root_only_projection_payload()
    observations = payload["n5_observations"]
    assert isinstance(observations, tuple)
    observation = observations[0]
    assert isinstance(observation, RunGenericCycleSimulationN5Observation)
    malformed = observation.model_dump(mode="python")
    malformed["child_profile_family_ref"] = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.generic_cycle_simulation_child_profile_family",
        media_type="application/json",
    )

    with pytest.raises(ValidationError, match="run_generic_n5_child_family_set_pair_invalid"):
        RunGenericCycleSimulationProjection.model_validate(
            {**payload, "n5_observations": (malformed,)}
        )
