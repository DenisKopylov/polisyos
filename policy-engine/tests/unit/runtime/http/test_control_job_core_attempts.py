from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.adapters.core_run import (
    load_completed_control_job_core_run_source,
)
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
)


class _NoOpRetrievalService:
    def list_promotion_candidates(self) -> list[object]:
        return []


class _CoreOnlyRegistry:
    def query_entries(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    def get(self, _registry_id: str) -> None:
        return None

    def list_all(self) -> list[Any]:
        return []

    def list_by_family(self, _family: str) -> list[Any]:
        return []


def _core_only_registry_providers() -> ControlRegistryProviders:
    """Supply inert registries; this witness exercises only the Core owner."""

    registry = _CoreOnlyRegistry()
    return ControlRegistryProviders(
        connectors=registry,
        source_profiles=registry,
        binding_profiles=registry,
        model_profiles=registry,
    )


def _create_attempt_job(store: ControlPlaneStore):
    job_id = "job-core-attempt-retry"
    control_run_id = "run-core-attempt-retry"
    actor = "fixture-core-attempt-worker"
    execution_scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": "tenant-core-attempt",
        "cell_id": "cell-core-attempt",
        "actor_subject": actor,
        "actor_authenticated": True,
        "actor_roles": ["analyst"],
    }
    creation_event = {
        "job_id": job_id,
        "run_id": control_run_id,
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": "sha256:" + "a" * 64,
        "submitted_by": actor,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {},
        "capability_manifest_ref": None,
        "execution_scope": execution_scope,
    }
    job = store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=control_run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref="sha256:" + "a" * 64,
        submitted_by=actor,
        creation_event_payload=creation_event,
    )
    return job, control_run_id


def _build_control_service(tmp_path, *, artifact_store, guarded_control_store):
    control_path = tmp_path / "control.sqlite3"
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=str(control_path),
        postgres_dsn=None,
    )
    return ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "core-runs",
        artifact_store=artifact_store,
        control_store=guarded_control_store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=_core_only_registry_providers(),
    )


def _fixture_proposal(artifact_store: FileSystemCAS, *, attempt: int):
    """Persist an honestly test-typed output, not a claimed compiled N4 run."""

    return artifact_store.put_json(
        {
            "schema_version": "tests.control_job_candidate_proposal.v1",
            "fixture_only": True,
            "lease_attempt": attempt,
        },
        ArtifactWriteOptions(
            kind="tests.control_job_candidate_proposal",
            media_type="application/json",
            schema=SchemaInfo(
                name="tests.ControlJobCandidateProposal",
                version="1.0.0",
            ),
        ),
    )


def test_retry_selects_only_winning_attempt_core_trace_and_manifest(tmp_path) -> None:
    """A stale handler cannot finalize or publish after the next lease owns the job.

    This is a component witness for attempt-scoped Core custody and guarded-store
    lease propagation. Its output is a test-typed proposal fixture; it makes no
    claim about N4 compilation, production grounding, N9, S8, or publication.
    """

    raw_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    guarded_store = guard_runtime_control_store(raw_store)
    artifact_store = FileSystemCAS(tmp_path / "artifacts").with_ambient_ownership_enforcement()
    service = _build_control_service(
        tmp_path,
        artifact_store=artifact_store,
        guarded_control_store=guarded_store,
    )
    job, control_run_id = _create_attempt_job(raw_store)
    first_lease = guarded_store.lease_next_job(
        worker_id="worker-core-attempt-1",
        lease_seconds=60,
    )
    assert first_lease is not None
    assert first_lease.job_id == job.job_id
    assert first_lease.run_id == control_run_id
    assert first_lease.attempt == 1

    first_core_started = threading.Event()
    let_first_finalize = threading.Event()
    first_attempt_observation: dict[str, Any] = {}
    winning_attempt_observation: dict[str, Any] = {}

    def _stale_attempt_worker() -> None:
        with guarded_store.job_execution_fence(
            job_id=first_lease.job_id,
            worker_id="worker-core-attempt-1",
            attempt=first_lease.attempt,
        ):
            admission = guarded_store.current_execution_job_admission()
            first_job = admission.job
            with service._install_execution_scope(admission.scope):
                first_core_run_id, first_context = service._start_generation_run_context(
                    job=first_job,
                    execution_scope=admission.scope,
                )
                first_trace_path = first_context.trace_path
                assert first_trace_path is not None
                first_trace_bytes = first_trace_path.read_bytes()
                first_attempt_observation.update(
                    {
                        "job": first_job,
                        "core_run_id": first_core_run_id,
                        "context": first_context,
                        "trace_path": first_trace_path,
                        "trace_bytes": first_trace_bytes,
                    }
                )
                first_core_started.set()
                assert let_first_finalize.wait(timeout=30), "retry did not release stale handler"

                with pytest.raises(ControlJobLeaseLostError):
                    service._finish_generation_run_context(
                        job=first_job,
                        execution_scope=admission.scope,
                        core_run_id=first_core_run_id,
                        context=first_context,
                        outputs=[],
                        status="ok",
                    )
                assert first_trace_path.read_bytes() == first_trace_bytes

                winning_manifest_ref = winning_attempt_observation["manifest_ref"]
                assert hasattr(winning_manifest_ref, "model_dump")
                stale_progress = {
                    "state": "completed",
                    "phase": "natural_language_run",
                    "run_id": control_run_id,
                    "core_run_id": first_core_run_id,
                    "core_run_attempt": first_lease.attempt,
                    "core_manifest_artifact_ref": winning_manifest_ref.model_dump(mode="json"),
                    "manifest_ref": str(winning_manifest_ref.artifact_id),
                }
                with pytest.raises(ControlJobLeaseLostError):
                    guarded_store.complete_job(
                        job_id=first_lease.job_id,
                        run_id=control_run_id,
                        progress=stale_progress,
                    )

                persisted = raw_store.get_job(first_lease.job_id)
                assert persisted is not None
                assert persisted.state == "completed"
                assert persisted.progress == winning_attempt_observation["progress"]
                first_attempt_observation["stale_finalize_refused"] = True
                first_attempt_observation["stale_publish_refused"] = True

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        first_future = executor.submit(_stale_attempt_worker)
        assert first_core_started.wait(timeout=30), "attempt one did not start Core"

        first_job = first_attempt_observation["job"]
        first_core_run_id = first_attempt_observation["core_run_id"]
        first_trace_path = first_attempt_observation["trace_path"]
        assert first_job.attempt == 1
        assert first_trace_path.is_file()

        # Make expiry deterministic while retaining the store's actual
        # expired-lease selection and retry increment behavior.
        affected = raw_store._execute(
            "UPDATE control_jobs SET lease_expires_at = ? "
            "WHERE job_id = ? AND state = 'running' AND lease_owner = ? AND attempt = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                job.job_id,
                "worker-core-attempt-1",
                first_lease.attempt,
            ),
        )
        assert affected == 1
        second_lease = guarded_store.lease_next_job(
            worker_id="worker-core-attempt-2",
            lease_seconds=60,
        )
        assert second_lease is not None
        assert second_lease.job_id == job.job_id
        assert second_lease.run_id == control_run_id
        assert second_lease.attempt == 2

        with guarded_store.job_execution_fence(
            job_id=second_lease.job_id,
            worker_id="worker-core-attempt-2",
            attempt=second_lease.attempt,
        ):
            admission = guarded_store.current_execution_job_admission()
            assert admission.attempt == second_lease.attempt
            second_job = admission.job
            with service._install_execution_scope(admission.scope):
                second_core_run_id, second_context = service._start_generation_run_context(
                    job=second_job,
                    execution_scope=admission.scope,
                )
                assert second_core_run_id != first_core_run_id
                assert second_context.trace_path != first_trace_path
                proposal_ref = _fixture_proposal(
                    artifact_store,
                    attempt=second_lease.attempt,
                )
                second_manifest_ref = service._finish_generation_run_context(
                    job=second_job,
                    execution_scope=admission.scope,
                    core_run_id=second_core_run_id,
                    context=second_context,
                    outputs=[proposal_ref],
                    status="ok",
                )
                progress = {
                    "state": "completed",
                    "phase": "natural_language_run",
                    "status": "simulation_only",
                    "run_id": control_run_id,
                    **service._core_run_progress_fields(
                        job=second_job,
                        core_run_id=second_core_run_id,
                        manifest_ref=second_manifest_ref,
                    ),
                }
                guarded_store.complete_job(
                    job_id=second_job.job_id,
                    run_id=control_run_id,
                    progress=progress,
                )
                completed = guarded_store.current_execution_completed_job_record()
                assert completed.attempt == 2
                selected = load_completed_control_job_core_run_source(
                    store=artifact_store,
                    core_runs_root=service._core_runs_root,
                    job=completed,
                    expected_control_run_id=control_run_id,
                    tenant_id=admission.scope.tenant_id,
                    cell_id=admission.scope.cell_id,
                )
                assert selected.run_id == second_core_run_id
                assert selected.manifest_ref == second_manifest_ref
                assert selected.manifest.outputs == [proposal_ref]
                winning_attempt_observation.update(
                    {
                        "manifest_ref": second_manifest_ref,
                        "progress": completed.progress,
                        "core_run_id": second_core_run_id,
                        "scope": admission.scope,
                    }
                )

        let_first_finalize.set()
        first_future.result(timeout=30)

        persisted = raw_store.get_job(job.job_id)
        assert persisted is not None
        assert persisted.state == "completed"
        assert persisted.attempt == 2
        assert persisted.progress == winning_attempt_observation["progress"]
        assert persisted.progress["core_run_id"] == winning_attempt_observation["core_run_id"]
        assert persisted.progress["core_run_attempt"] == 2

        first_trace_records = [
            line
            for line in first_trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(first_trace_records) == 1
        assert '"event":"RUN_STARTED"' in first_trace_records[0]
        assert not (first_trace_path.parent / ".finalize-journal.json").exists()
        assert first_attempt_observation["stale_finalize_refused"] is True
        assert first_attempt_observation["stale_publish_refused"] is True

        with service._install_execution_scope(winning_attempt_observation["scope"]):
            selected_after_stale_write = load_completed_control_job_core_run_source(
                store=artifact_store,
                core_runs_root=service._core_runs_root,
                job=persisted,
                expected_control_run_id=control_run_id,
                tenant_id="tenant-core-attempt",
                cell_id="cell-core-attempt",
            )
        assert selected_after_stale_write.run_id == winning_attempt_observation["core_run_id"]
        assert (
            selected_after_stale_write.manifest_ref
            == winning_attempt_observation["manifest_ref"]
        )
    finally:
        let_first_finalize.set()
        executor.shutdown(wait=True)
        service.close()
        guarded_store.close()
