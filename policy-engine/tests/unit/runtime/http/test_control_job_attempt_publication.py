"""Issued candidate failure progress retains original errors and attempt custody."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.runtime.http.services.control import job_attempt_publication as publication
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    _WorkflowExecutionNonAuthorityError,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionScope,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.generation_cycle import GenerationCycleError
from tests.unit.runtime.http.test_control_worker_custody import job as _worker_custody_job
from tests.unit.runtime.http.test_cycle_substrate_job_execution_binding import (
    _create_execution_scoped_job,
)
from tests.unit.runtime.quality.test_cycle_substrate import _authenticated_tenant_scope

job = _worker_custody_job


@pytest.fixture
def execution_scope() -> ControlJobExecutionScope:
    return ControlJobExecutionScope(
        status="established",
        tenant_id="tenant-failure-progress",
        cell_id="cell-failure-progress",
        actor_subject="fixture-actor",
        actor_authenticated=True,
        actor_roles=(),
    )


def _failure_progress(job: ControlJobRecord, error: GenerationCycleError) -> dict[str, Any]:
    return {
        "state": "failed",
        "phase": "value_projection",
        "runtime_state": "candidate_only",
        "job_id": job.job_id,
        "run_id": job.run_id,
        "attempt": job.attempt,
        "failure": {
            "code": error.code,
            "exception_type": type(error).__name__,
            "message": str(error),
            "phase": "value_projection",
        },
    }


def test_issued_failure_progress_preserves_original_error_and_existing_cause(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope
) -> None:
    """Issuing progress changes neither the original error nor its causal chain."""
    cause = LookupError("preexisting cause")
    error = GenerationCycleError("controlled_late_value_failure", "value projection failed")
    error.__cause__ = cause
    original = (
        type(error),
        error.code,
        str(error),
        error.__cause__,
        error.__context__,
        error.__suppress_context__,
    )
    progress = _failure_progress(job, error)
    assert (
        publication._attach_original_error_candidate_progress(
            error, progress=progress, job=job, execution_scope=execution_scope
        )
        is True
    )
    packet = getattr(error, publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE)
    assert type(packet) is _WorkflowExecutionNonAuthorityError
    assert getattr(packet, publication._ORIGINAL_ERROR_ATTRIBUTE) is error
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        == progress
    )
    assert (
        type(error),
        error.code,
        str(error),
        error.__cause__,
        error.__context__,
        error.__suppress_context__,
    ) == original
    assert error.__cause__ is cause
    # A returned mapping is a projection, not the packet's mutable top-level map.
    projected = publication._original_error_candidate_progress(
        error, job=job, execution_scope=execution_scope
    )
    assert projected is not None and projected is not progress
    projected["state"] = "completed"
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        == progress
    )


def test_matching_failure_packet_without_owner_issuance_is_rejected(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope
) -> None:
    """Matching class, original-error pointer and binding are insufficient to issue progress."""
    error = GenerationCycleError("controlled_late_failure", "late failure")
    fake = _WorkflowExecutionNonAuthorityError(str(error), progress=_failure_progress(job, error))
    setattr(fake, publication._ORIGINAL_ERROR_ATTRIBUTE, error)
    setattr(
        fake,
        publication._ORIGINAL_ERROR_PROGRESS_BINDING_ATTRIBUTE,
        publication._candidate_progress_owner_binding(job, execution_scope),
    )
    setattr(error, publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE, fake)
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is None
    )
    setattr(fake, publication._ORIGINAL_ERROR_PROGRESS_ISSUER_ATTRIBUTE, object())
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is None
    )
    publication._attach_original_error_candidate_progress(
        error, progress=_failure_progress(job, error), job=job, execution_scope=execution_scope
    )
    issued = getattr(error, publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE)
    different_error = GenerationCycleError(error.code, "late failure")
    setattr(different_error, publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE, issued)
    assert (
        publication._original_error_candidate_progress(
            different_error, job=job, execution_scope=execution_scope
        )
        is None
    )


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"job_id": "job-foreign"}, id="job"),
        pytest.param({"run_id": "run-foreign"}, id="run"),
        pytest.param({"attempt": 2}, id="attempt"),
        pytest.param({"lease_owner": "worker-foreign"}, id="worker"),
        pytest.param({"effective_execution_profile": "research"}, id="effective-profile"),
        pytest.param({"requested_execution_profile": "research"}, id="requested-profile"),
    ],
)
def test_issued_failure_progress_refuses_changed_attempt_owner(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope, changed: dict[str, Any]
) -> None:
    """An issued packet belongs to every original job and execution-profile coordinate."""
    error = GenerationCycleError("controlled_late_failure", "late failure")
    publication._attach_original_error_candidate_progress(
        error, progress=_failure_progress(job, error), job=job, execution_scope=execution_scope
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is not None
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=replace(job, **changed), execution_scope=execution_scope
        )
        is None
    )


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"tenant_id": "tenant-foreign"}, id="tenant"),
        pytest.param({"cell_id": "cell-foreign"}, id="cell"),
    ],
)
def test_issued_failure_progress_refuses_changed_tenant_or_cell(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope, changed: dict[str, Any]
) -> None:
    error = GenerationCycleError("controlled_late_failure", "late failure")
    publication._attach_original_error_candidate_progress(
        error, progress=_failure_progress(job, error), job=job, execution_scope=execution_scope
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=replace(execution_scope, **changed)
        )
        is None
    )


def test_failure_progress_clear_revokes_reused_error_before_another_attempt(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope
) -> None:
    """Reusing an exception cannot retain a previous attempt's issued progress."""
    error = GenerationCycleError("controlled_late_failure", "reused original failure")
    publication._attach_original_error_candidate_progress(
        error, progress=_failure_progress(job, error), job=job, execution_scope=execution_scope
    )
    publication._clear_original_error_candidate_progress(error)
    publication._clear_original_error_candidate_progress(error)
    next_job = replace(job, attempt=job.attempt + 1, lease_owner="next-worker")
    for owner in (job, next_job):
        assert (
            publication._original_error_candidate_progress(
                error, job=owner, execution_scope=execution_scope
            )
            is None
        )
    next_progress = _failure_progress(next_job, error)
    publication._attach_original_error_candidate_progress(
        error, progress=next_progress, job=next_job, execution_scope=execution_scope
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is None
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=next_job, execution_scope=execution_scope
        )
        == next_progress
    )
    publication._clear_original_error_candidate_progress(error)
    assert (
        publication._original_error_candidate_progress(
            error, job=next_job, execution_scope=execution_scope
        )
        is None
    )


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"job_id": "wrong"}, id="job"),
        pytest.param({"run_id": "wrong"}, id="run"),
        pytest.param({"attempt": 2}, id="attempt"),
    ],
)
def test_failure_progress_cannot_be_issued_with_mismatched_progress_identity(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope, changed: dict[str, Any]
) -> None:
    error = GenerationCycleError("controlled_late_failure", "late failure")
    with pytest.raises(ValueError, match="original_error_candidate_progress_scope_mismatch"):
        publication._attach_original_error_candidate_progress(
            error,
            progress={**_failure_progress(job, error), **changed},
            job=job,
            execution_scope=execution_scope,
        )
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is None
    )


def test_historical_raised_non_authority_error_still_exposes_its_progress(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope
) -> None:
    progress = {"state": "failed", "phase": "historical-workspace", "job_id": job.job_id}
    historical = _WorkflowExecutionNonAuthorityError("historical failure", progress=progress)
    with pytest.raises(_WorkflowExecutionNonAuthorityError) as raised:
        raise historical
    assert raised.value is historical
    projected = publication._original_error_candidate_progress(
        raised.value, job=job, execution_scope=execution_scope
    )
    assert projected == progress and projected is not progress


def test_hostile_error_attributes_preserve_issued_progress_and_original_failure(
    job: ControlJobRecord, execution_scope: ControlJobExecutionScope
) -> None:
    """Issued diagnostics use real storage despite hostile Python attribute hooks."""

    class AttributeRefusingError(RuntimeError):
        @property
        def __dict__(self) -> dict[str, Any]:
            raise RuntimeError("instance dictionary is unreadable")

        def __getattribute__(self, name: str) -> Any:
            if name in {publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE, "__dict__"}:
                raise RuntimeError("progress attribute is unreadable")
            return super().__getattribute__(name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE, "__dict__"}:
                raise RuntimeError("progress attribute is unwritable")
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name in {publication._NON_AUTHORITY_FAILURE_PROGRESS_ATTRIBUTE, "__dict__"}:
                raise RuntimeError("progress attribute cannot be cleared")
            super().__delattr__(name)

    cause = LookupError("original hostile-error cause")
    error = AttributeRefusingError("original hostile-error text")
    error.__cause__ = cause
    original = (type(error), str(error), error.__cause__, error.__context__)
    progress = {"job_id": job.job_id, "run_id": job.run_id, "attempt": job.attempt}
    assert (
        publication._attach_original_error_candidate_progress(
            error,
            progress=progress,
            job=job,
            execution_scope=execution_scope,
        )
        is True
    )
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        == progress
    )
    publication._clear_original_error_candidate_progress(error)
    assert (
        publication._original_error_candidate_progress(
            error, job=job, execution_scope=execution_scope
        )
        is None
    )
    assert (type(error), str(error), error.__cause__, error.__context__) == original
    with pytest.raises(AttributeRefusingError) as raised:
        raise error
    assert raised.value is error and raised.value.__cause__ is cause


def test_failed_job_records_original_message_and_issued_progress_without_outputs(
    tmp_path: Path, execution_scope: ControlJobExecutionScope
) -> None:
    """Actual failure publication persists the original message under a real job fence."""

    class FailureHost(publication.ControlJobAttemptPublicationMixin):
        def __init__(self, store: ControlPlaneStore) -> None:
            self._control_store = store
            self.events: list[dict[str, Any]] = []

        def _emit_runtime_diagnostic_event(self, **kwargs: Any) -> None:
            self.events.append(kwargs)

        def _finish_generation_run_context(self, **_kwargs: Any) -> Any:
            pytest.fail("failure without a Core context must not synthesize outputs")

    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        job = _create_execution_scoped_job(
            store,
            job_id="job-real-failure-progress",
            run_id="run-real-failure-progress",
            tenant_id=str(execution_scope.tenant_id),
            cell_id=str(execution_scope.cell_id),
            actor_subject=str(execution_scope.actor_subject),
            kind="natural_language_run",
        )
        cause = LookupError("original cause")
        error = GenerationCycleError("controlled_late_failure", "original late failure")
        error.__cause__ = cause
        progress = _failure_progress(job, error)
        publication._attach_original_error_candidate_progress(
            error, progress=progress, job=job, execution_scope=execution_scope
        )
        host = FailureHost(store)
        with (
            _authenticated_tenant_scope(
                tenant_id=str(execution_scope.tenant_id), cell_id=str(execution_scope.cell_id)
            ),
            store.job_execution_fence(
                job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
            ),
        ):
            host._fail_control_job_attempt(
                job=job,
                execution_scope=execution_scope,
                payload={},
                capability_manifest_ref=None,
                core_run_id=None,
                core_run_context=None,
                exc=error,
                logger=logging.getLogger(__name__),
            )
        failed = store.get_job(job.job_id)
        assert failed is not None and failed.state == "failed"
        assert failed.error_message == str(error)
        expected_progress = {
            **progress,
            "execution_owner_binding": {
                "job_id": job.job_id,
                "run_id": job.run_id,
                "attempt": job.attempt,
                "lease_owner": job.lease_owner,
                "requested_execution_profile": job.requested_execution_profile,
                "effective_execution_profile": job.effective_execution_profile,
                "tenant_id": execution_scope.tenant_id,
                "cell_id": execution_scope.cell_id,
            },
        }
        for key, value in expected_progress.items():
            assert key in failed.progress and failed.progress[key] == value
        assert failed.progress["quality_scorecard"] == {
            "job_id": job.job_id,
            "run_id": job.run_id,
        }
        assert failed.progress["failure"]["exception_type"] == type(error).__name__
        assert failed.progress["failure"]["code"] == error.code
        assert (
            "outputs" not in failed.progress and "core_manifest_artifact_ref" not in failed.progress
        )
        assert error.__cause__ is cause
        assert host.events[0]["event_payload"]["error"] == str(error)
        assert host.events[0]["state_after"] == "failed"
    finally:
        store.close()


@pytest.mark.parametrize("poison_identity", [False, True])
def test_failed_job_persists_sanitized_real_dependency_wait_diagnostic(
    tmp_path: Path, execution_scope: ControlJobExecutionScope, poison_identity: bool
) -> None:
    """A real guard timeout reaches the existing job progress without source payloads."""

    class FailureHost(publication.ControlJobAttemptPublicationMixin):
        def __init__(self, store: ControlPlaneStore) -> None:
            self._control_store = store

        def _emit_runtime_diagnostic_event(self, **_kwargs: Any) -> None:
            pass

        def _finish_generation_run_context(self, **_kwargs: Any) -> Any:
            pytest.fail("failure without a Core context must not synthesize outputs")

    release = threading.Event()
    entered = threading.Event()
    guard = BlockingDependencyGuard(
        dependency_name="content_addressed_storage",
        timeout_seconds=0.15,
        breaker=CircuitBreaker(
            circuit_id="test-progress-cas",
            config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
        ),
    )

    def backend_operation() -> None:
        entered.set()
        release.wait(timeout=5)

    if poison_identity:
        backend_operation.__module__ = "payload=secret"
        backend_operation.__qualname__ = "payload=secret"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        with pytest.raises(RuntimeDependencyTimeoutError) as caught:
            guard.run(backend_operation)
        assert entered.is_set()
        error = caught.value
        job = _create_execution_scoped_job(
            store,
            job_id="job-cas-wait-diagnostic",
            run_id="run-cas-wait-diagnostic",
            tenant_id=str(execution_scope.tenant_id),
            cell_id=str(execution_scope.cell_id),
            actor_subject=str(execution_scope.actor_subject),
            kind="natural_language_run",
        )
        host = FailureHost(store)
        with (
            _authenticated_tenant_scope(
                tenant_id=str(execution_scope.tenant_id), cell_id=str(execution_scope.cell_id)
            ),
            store.job_execution_fence(
                job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
            ),
        ):
            host._fail_control_job_attempt(
                job=job,
                execution_scope=execution_scope,
                payload={},
                capability_manifest_ref=None,
                core_run_id=None,
                core_run_context=None,
                exc=error,
                logger=logging.getLogger(__name__),
            )
        failed = store.get_job(job.job_id)
        assert failed is not None and failed.state == "failed"
        assert failed.error_message == "content_addressed_storage timed out"
        failure = failed.progress["failure"]
        assert failure["code"] == "content_addressed_storage_timeout"
        assert failure["retryable"] is True
        wait = failure["blocking_wait"]
        assert wait["timeout_seconds"] == 0.15
        assert wait["wait_disposition"] == "running_at_observation"
        assert wait["caller"]["qualname"].endswith(
            "test_failed_job_persists_sanitized_real_dependency_wait_diagnostic"
        )
        if poison_identity:
            assert wait["operation"] == {
                "module": "not_established",
                "qualname": "not_established",
            }
        else:
            assert wait["operation"]["qualname"].endswith(".backend_operation")
        assert "payload=secret" not in str(wait)
    finally:
        release.set()
        guard.close()
        store.close()
