"""Regression witnesses for DUR-02 worker fencing and backend handover."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import the worker facade first, matching the established control-plane test
# order and avoiding the compatibility ``control.py`` shim import cycle.
import polisyos.runtime.http.services.control_worker as _control_worker_module

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.scientist.orchestration.engine.runner.fallback_runner import (
    FallbackWorkflowRunner,
)
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth


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

    with pytest.raises(RuntimeError, match="outcome"):
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
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    result = asyncio.run(runner.execute_workflow("wf", "state", "ctx", "registry"))

    assert result == "local-result"
    primary.execute_workflow.assert_not_awaited()
    fallback.assert_awaited_once()


def test_access_or_contract_probe_failure_does_not_grant_fallback_authority() -> None:
    """Access/contract failures are limited, not permission to execute elsewhere."""

    primary = MagicMock()
    primary.health_check = AsyncMock(
        return_value=RunnerHealth(
            backend="remote",
            healthy=False,
            message="probe failed: tenant access denied by contract",
        )
    )
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    fallback = AsyncMock(return_value="local-result")
    runner._fallback = SimpleNamespace(execute_workflow=fallback)

    with pytest.raises(RuntimeError, match="fallback"):
        asyncio.run(runner.execute_workflow("wf", "state", "ctx", "registry"))

    fallback.assert_not_awaited()
