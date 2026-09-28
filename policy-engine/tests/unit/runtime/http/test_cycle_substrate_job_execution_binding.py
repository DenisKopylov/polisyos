from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.resilience import (
    guard_runtime_cas,
    guard_runtime_control_store,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextOwnerError,
)
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _cycle_context,
    _design_problem,
    _registry,
    _world_record,
)


def test_cycle_substrate_context_owner_uses_guarded_current_job_execution(
    tmp_path: Any,
) -> None:
    """The persisted served-job lease, not supplied IDs, binds context replay."""

    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        registry=registry,
        world_model_record=world,
    )
    raw_control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )
    control_store = guard_runtime_control_store(raw_control_store)
    raw_artifact_store = FileSystemCAS(
        tmp_path / "cycle-context-cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    artifact_store = guard_runtime_cas(raw_artifact_store)
    owner = CycleSubstrateContextArtifactOwner(
        store=artifact_store,
        control_store=control_store,
    )

    def _create_and_lease(job_id: str, run_id: str, worker_id: str) -> Any:
        control_store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref="payload:" + job_id,
            submitted_by="test-worker",
        )
        leased = control_store.lease_next_job(
            worker_id=worker_id,
            lease_seconds=60,
        )
        assert leased is not None and leased.job_id == job_id
        return leased

    lease_a = _create_and_lease("job-a", "run-a", "worker-a")
    lease_b = _create_and_lease("job-b", "run-b", "worker-b")
    try:
        with _authenticated_tenant_scope(
            tenant_id="tenant-context-owner", cell_id="cell-context-owner"
        ):
            with control_store.job_execution_fence(
                job_id=lease_a.job_id,
                worker_id=lease_a.lease_owner,
                attempt=lease_a.attempt,
            ):
                ref_a = owner.persist_for_current_job(context, problem=problem)
                resolved_a = owner.resolve_for_current_job(ref_a, problem=problem)
                assert resolved_a.profile_admission_status == "not_established"
                assert resolved_a.s8_status == "blocked"

                changed_problem = problem.model_copy(
                    update={
                        "problem_statement": (
                            problem.problem_statement + " Preserve the same display identity."
                        )
                    }
                )
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_binding_mismatch",
                ):
                    owner.resolve_for_current_job(ref_a, problem=changed_problem)

            with control_store.job_execution_fence(
                job_id=lease_b.job_id,
                worker_id=lease_b.lease_owner,
                attempt=lease_b.attempt,
            ):
                # The consumer cannot replay A by presenting A's IDs: the API
                # derives identity from B's current persisted execution fence.
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_binding_mismatch",
                ):
                    owner.resolve_for_current_job(ref_a, problem=problem)
                ref_b = owner.persist_for_current_job(context, problem=problem)
                resolved_b = owner.resolve_for_current_job(ref_b, problem=problem)

        assert resolved_a.job_id == lease_a.job_id
        assert resolved_a.run_id == lease_a.run_id
        assert resolved_b.job_id == lease_b.job_id
        assert resolved_b.run_id == lease_b.run_id
    finally:
        artifact_store.close()
        control_store.close()
