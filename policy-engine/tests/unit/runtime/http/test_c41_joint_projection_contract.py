"""Candidate-only joint parent status cannot be promoted by container shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationN5Observation,
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
