"""Regression witnesses for DUR-02 worker fencing and backend handover."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import the eager compatibility facade first.  It initializes the split
# control modules before the store reaches ``response_shapes`` and avoids the
# ``control.py`` shim import cycle in this standalone remediation module.
import_module("polisyos.runtime.http.services.control")
import_module("polisyos.runtime.http.services.control_worker")
from polisyos.common.job_execution_interrupt import (
    JobExecutionInterrupted,
    raise_if_job_execution_interrupted,
    require_current_job_execution_owner,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.scientist.orchestration.engine.runner import fallback_runner as fallback_runner_module
from polisyos.scientist.orchestration.engine.runner.fallback_runner import (
    FallbackNotAuthorizedError,
    FallbackWorkflowRunner,
    HealthFailureDisposition,
    PrimaryExecutionOutcomeUnknownError,
)
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth


def _health_sample(
    health: RunnerHealth,
    disposition: HealthFailureDisposition,
    probe_id: int,
) -> object:
    """Build the private backend witness without making it public test API."""

    sample_type = getattr(fallback_runner_module, "_HealthFailureSample", None)
    if sample_type is None:
        return SimpleNamespace(
            health=health,
            disposition=disposition,
            probe_id=probe_id,
        )
    return sample_type(health=health, disposition=disposition, probe_id=probe_id)


def _make_store(tmp_path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _create_job(store: ControlPlaneStore, job_id: str) -> None:
    store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id=f"run-{job_id}",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="dur-02-test",
    )


def _take_over_job(
    store: ControlPlaneStore,
    job_id: str,
) -> tuple[object, object]:
    first = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert first is not None
    assert first.job_id == job_id

    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    store._execute(
        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
        (expired_at, job_id),
    )
    second = store.lease_next_job(worker_id="worker-b", lease_seconds=30)
    assert second is not None
    assert second.job_id == job_id
    return first, second


@pytest.mark.parametrize("failure_kind", ["timeout", "unavailable", "not_renewed"])
@pytest.mark.parametrize("during_shutdown", [False, True])
def test_terminal_heartbeat_loss_interrupts_bound_handler(
    tmp_path, monkeypatch, failure_kind: str, during_shutdown: bool
) -> None:
    """A stopped renewal cannot leave its existing handler guard permitted."""
    store = _make_store(tmp_path)
    _create_job(store, "dur02-heartbeat-loss")
    job = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert job is not None
    renewed = threading.Event()
    observations: list[str] = []

    def handler(_job) -> None:
        assert renewed.wait(2), "heartbeat never attempted renewal"
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            try:
                raise_if_job_execution_interrupted()
            except JobExecutionInterrupted:
                observations.append("interrupted")
                raise
            threading.Event().wait(0.005)
        observations.append("incorrectly-permitted")

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-a")
    worker._heartbeat_interval_s = 0.005

    def fail_renewal(**_kwargs):
        if during_shutdown:
            worker._stop.set()
        renewed.set()
        if failure_kind == "not_renewed":
            return False
        error_type = (
            RuntimeDependencyTimeoutError
            if failure_kind == "timeout"
            else RuntimeDependencyUnavailableError
        )
        raise error_type("fixture control store renewal failure")

    monkeypatch.setattr(store, "renew_job_lease", fail_renewal)
    worker._run_with_lease_heartbeat(job)
    assert observations == ["interrupted"]
    assert not any(
        thread.name == "worker-a-heartbeat" and thread.is_alive()
        for thread in threading.enumerate()
    )
    current = store.get_job(job.job_id)
    assert current is not None and current.state == "running"


@pytest.mark.parametrize("failure", ["expired", "takeover", "timeout", "unavailable"])
def test_live_dispatch_guard_refuses_before_the_next_heartbeat(
    tmp_path, monkeypatch, failure: str
) -> None:
    """A real initialized SQL owner is rechecked at use, not on a pulse schedule."""
    store = _make_store(tmp_path)
    admin = _make_store(tmp_path)
    _create_job(store, "dur02-live-owner")
    job = store.lease_next_job(worker_id="worker-a", lease_seconds=300)
    assert job is not None
    observed = []

    def handler(_job) -> None:
        require_current_job_execution_owner(job.job_id)
        observed.append("initial-owner-established")
        if failure in {"expired", "takeover"}:
            admin._execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job.job_id),
            )
            if failure == "takeover":
                replacement = admin.lease_next_job(worker_id="worker-b", lease_seconds=300)
                assert replacement is not None and replacement.attempt == 2
        else:
            error_type = (
                RuntimeDependencyTimeoutError
                if failure == "timeout"
                else RuntimeDependencyUnavailableError
            )

            def unavailable():
                raise error_type("actual live owner lookup unavailable")

            monkeypatch.setattr(store, "current_execution_job_record", unavailable)

        def produce() -> None:
            require_current_job_execution_owner(job.job_id)
            observed.append("incorrect-effect")

        with pytest.raises(JobExecutionInterrupted):
            produce()
        with pytest.raises(JobExecutionInterrupted):
            raise_if_job_execution_interrupted()

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-a")
    worker._heartbeat_interval_s = 60
    worker._run_with_lease_heartbeat(job)
    assert observed == ["initial-owner-established"]
    current = store.get_job(job.job_id)
    assert current is not None and current.state == "running"
    if failure == "takeover":
        assert current.lease_owner == "worker-b" and current.attempt == 2
    assert not any(
        thread.name == "worker-a-heartbeat" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_successful_heartbeat_preserves_own_handler_and_unrelated_worker(
    tmp_path, monkeypatch
) -> None:
    """One worker's renewal loss does not revoke another execution context."""
    store = _make_store(tmp_path)
    _create_job(store, "dur02-heartbeat-current")
    job = store.lease_next_job(worker_id="worker-current", lease_seconds=30)
    assert job is not None
    renewed = threading.Event()
    real_renewal = store.renew_job_lease

    def renew(**kwargs):
        result = real_renewal(**kwargs)
        renewed.set()
        return result

    observations: list[str] = []

    def handler(current_job) -> None:
        assert renewed.wait(2)
        raise_if_job_execution_interrupted()
        store.complete_job(job_id=current_job.job_id)
        observations.append("completed")

    monkeypatch.setattr(store, "renew_job_lease", renew)
    worker = ControlWorker(store=store, handler=handler, worker_id="worker-current")
    worker._heartbeat_interval_s = 0.005
    worker._run_with_lease_heartbeat(job)
    raise_if_job_execution_interrupted()
    assert observations == ["completed"]
    completed = store.get_job(job.job_id)
    assert completed is not None and completed.state == "completed"


def test_heartbeat_loss_does_not_interrupt_concurrent_unrelated_job(tmp_path, monkeypatch) -> None:
    """The worker-owned interrupt remains scoped to its exact job attempt."""
    store = _make_store(tmp_path)
    _create_job(store, "dur02-losing-job")
    first = store.lease_next_job(worker_id="worker-losing", lease_seconds=30)
    _create_job(store, "dur02-unrelated-job")
    second = store.lease_next_job(worker_id="worker-unrelated", lease_seconds=30)
    assert first is not None and second is not None
    lost_renewal = threading.Event()
    losing_finished = threading.Event()
    failures: list[BaseException] = []
    observations: list[str] = []
    real_renewal = store.renew_job_lease

    def renew(**kwargs):
        if kwargs["worker_id"] == "worker-losing":
            lost_renewal.set()
            raise RuntimeDependencyUnavailableError("fixture control store")
        return real_renewal(**kwargs)

    def losing_handler(_job) -> None:
        assert lost_renewal.wait(2)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            raise_if_job_execution_interrupted()
            threading.Event().wait(0.005)
        raise AssertionError("losing job remained permitted")

    losing = ControlWorker(store=store, handler=losing_handler, worker_id="worker-losing")
    losing._heartbeat_interval_s = 0.005

    def run_losing() -> None:
        try:
            losing._run_with_lease_heartbeat(first)
        except BaseException as error:
            failures.append(error)
        finally:
            losing_finished.set()

    def unrelated_handler(job) -> None:
        assert losing_finished.wait(2)
        raise_if_job_execution_interrupted()
        store.complete_job(job_id=job.job_id)
        observations.append("unrelated-completed")

    monkeypatch.setattr(store, "renew_job_lease", renew)
    unrelated = ControlWorker(store=store, handler=unrelated_handler, worker_id="worker-unrelated")
    unrelated._heartbeat_interval_s = 0.005
    thread = threading.Thread(target=run_losing, name="dur02-losing-handler")
    thread.start()
    try:
        unrelated._run_with_lease_heartbeat(second)
    finally:
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert not failures
    assert observations == ["unrelated-completed"]
    completed = store.get_job(second.job_id)
    assert completed is not None and completed.state == "completed"


def test_stale_worker_cannot_finalize_new_attempt_but_current_worker_can(tmp_path) -> None:
    """Terminal writes are fenced by the worker's owner/attempt/lease generation."""

    store = _make_store(tmp_path)
    _create_job(store, "job-dur-02-fence")
    stale, current = _take_over_job(store, "job-dur-02-fence")

    stale_worker = ControlWorker(
        store=store,
        handler=lambda job: store.complete_job(job_id=job.job_id),
        worker_id="worker-a",
        lease_seconds=30,
    )
    with pytest.raises(RuntimeError, match="lease"):
        stale_worker._run_with_lease_heartbeat(stale)

    after_stale = store.get_job("job-dur-02-fence")
    assert after_stale is not None
    assert after_stale.state == "running"
    assert after_stale.lease_owner == "worker-b"
    assert after_stale.attempt == 2

    current_worker = ControlWorker(
        store=store,
        handler=lambda job: store.complete_job(job_id=job.job_id),
        worker_id="worker-b",
        lease_seconds=30,
    )
    current_worker._run_with_lease_heartbeat(current)

    completed = store.get_job("job-dur-02-fence")
    assert completed is not None
    assert completed.state == "completed"
    assert completed.lease_owner is None


def test_terminal_status_progress_and_event_are_one_transaction(tmp_path, monkeypatch) -> None:
    """A lifecycle event failure cannot leave terminal state or progress committed."""

    store = _make_store(tmp_path)
    _create_job(store, "job-dur-02-transaction")
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    store.update_progress_state(
        job_id=leased.job_id,
        state="running",
        progress={"phase": "dispatch"},
    )

    def fail_event(*, job_id: str, event_type: str, payload: dict[str, object]) -> None:
        del job_id, event_type, payload
        raise RuntimeError("event persistence failed")

    monkeypatch.setattr(store, "append_event", fail_event)
    with pytest.raises(RuntimeError, match="event persistence failed"):
        store.complete_job(
            job_id=leased.job_id,
            progress={"phase": "completed"},
        )

    unchanged = store.get_job(leased.job_id)
    assert unchanged is not None
    assert unchanged.state == "running"
    assert unchanged.lease_owner == "worker-a"
    assert unchanged.progress["phase"] == "dispatch"
    assert store.list_job_state_transitions(leased.job_id)[-1] == "running"
    assert not any(
        event.topic == "control.job.completed"
        for event in store.list_outbox_events(state=None, limit=100)
    )


def test_post_dispatch_failure_does_not_blindly_replay_locally() -> None:
    """An execution error after primary dispatch is an unknown outcome, not fallback permission."""

    calls: list[str] = []
    primary = MagicMock()
    primary.health_check = AsyncMock(
        return_value=RunnerHealth(backend="remote", healthy=True, message="ready")
    )

    async def execute_primary(*args, **kwargs):
        del args, kwargs
        calls.append("primary-effect")
        raise RuntimeError("lost response after effect")

    primary.execute_workflow = execute_primary
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(PrimaryExecutionOutcomeUnknownError, match="outcome"):
        asyncio.run(runner.execute_workflow("wf", "state", "ctx", "registry"))

    assert calls == ["primary-effect"]
    fallback.assert_not_awaited()


def test_transient_pre_dispatch_probe_failure_allows_local_fallback() -> None:
    """A classified transient health failure before dispatch may use the local backend."""

    primary = MagicMock()
    primary.health_check = AsyncMock(
        return_value=RunnerHealth(
            backend="remote",
            healthy=False,
            message="probe failed: connection refused",
        )
    )
    primary.execute_workflow = AsyncMock()
    health = primary.health_check.return_value
    sample = _health_sample(health, HealthFailureDisposition.ALLOW, probe_id=1)
    primary._get_health_sample = MagicMock(return_value=sample)
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    result = asyncio.run(runner.execute_workflow("wf", "state", "ctx", "registry"))

    assert result == "local-result"
    primary.execute_workflow.assert_not_awaited()
    fallback.assert_awaited_once()


def test_access_or_contract_probe_failure_does_not_grant_fallback_authority() -> None:
    """Access/contract failures are limited, not permission to execute elsewhere."""

    primary = MagicMock()
    health = RunnerHealth(
        backend="remote",
        healthy=False,
        message="probe failed: connection refused; tenant access denied by contract",
    )
    primary.health_check = AsyncMock(return_value=health)
    sample = _health_sample(health, HealthFailureDisposition.BLOCK, probe_id=1)
    primary._get_health_sample = MagicMock(return_value=sample)
    primary.classify_health_failure = MagicMock(return_value=HealthFailureDisposition.ALLOW)
    runner = FallbackWorkflowRunner(
        primary,
        health_ttl_s=0,
    )
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(FallbackNotAuthorizedError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "state", "ctx", "registry"))

    fallback.assert_not_awaited()
