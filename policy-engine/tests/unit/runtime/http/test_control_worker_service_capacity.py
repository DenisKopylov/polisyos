"""Process-isolated control lease and result custody under saturated compute."""

from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from queue import Empty
from typing import Any

import pytest


def _capacity_witness_child(
    sqlite_path: str,
    cas_path: str,
    results: multiprocessing.Queue,
    *,
    route_control_to_compute: bool,
    cancel_queued: bool,
) -> None:
    """Exercise an actual worker, guarded store, and CAS in a fresh process."""
    from polisyos.common import async_tools
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.runtime.http import resilience
    from polisyos.runtime.http.errors import (
        RuntimeDependencyTimeoutError,
        RuntimeDependencyUnavailableError,
    )
    from polisyos.runtime.http.services import control_plane_store as store_module
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobLeaseLostError,
        ControlPlaneStore,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker

    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=1,
            queue_capacity=1,
            revision="c11-service-capacity-v2",
        )
    )
    executor = async_tools.get_shared_executor()
    raw = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    clock = [datetime(2026, 10, 27, tzinfo=UTC)]
    store_module._utc_now = lambda: clock[0]
    raw.create_job(
        job_id="job-service-capacity",
        kind="workflow_run",
        run_id="run-service-capacity",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="c11-witness",
    )
    leased = raw.lease_next_job(worker_id="worker-old", lease_seconds=2)
    assert leased is not None and leased.attempt == 1
    initial_expiry = leased.lease_expires_at
    assert initial_expiry is not None

    guard = resilience.build_runtime_control_store_guard()
    if route_control_to_compute:
        # Preserve the selected timeout, breaker and exception policy. Only the
        # executor route changes; this is the semantic removal control.
        shared_guard = resilience.BlockingDependencyGuard(
            dependency_name=guard._dependency_name,
            timeout_seconds=guard._timeout_seconds,
            breaker=guard._breaker,
            executor=executor,
            unavailable_exception_types=guard._unavailable_exception_types,
            unavailable_exception_predicate=guard._unavailable_exception_predicate,
        )
        guard.close()
        guard = shared_guard
    store = resilience.GuardedDependencyProxy(target=raw, guard=guard)
    cas = FileSystemCAS(Path(cas_path))
    allow_renewal = threading.Event()
    renewal_attempted = threading.Event()
    renewal_finished = threading.Event()
    handler_entered = threading.Event()
    resume_handler = threading.Event()
    compute_started = threading.Event()
    release_compute = threading.Event()
    queued_started = threading.Event()
    observation: dict[str, Any] = {}
    thread_errors: list[BaseException] = []

    class _ObservedStore:
        """Observe the real guarded call without replacing its result."""

        def __getattr__(self, name: str) -> Any:
            return getattr(store, name)

        def renew_job_lease(self, **kwargs: Any) -> bool:
            if not renewal_finished.is_set():
                assert allow_renewal.wait(timeout=10), "renewal was never released"
                renewal_attempted.set()
                try:
                    result = store.renew_job_lease(**kwargs)
                    observation["renewal_return"] = result
                    return result
                except (
                    RuntimeDependencyTimeoutError,
                    RuntimeDependencyUnavailableError,
                ) as exc:
                    observation["renewal_error"] = type(exc).__name__
                    raise
                finally:
                    renewal_finished.set()
            return store.renew_job_lease(**kwargs)

    def _old_handler(job: Any) -> None:
        # The worker has entered the genuine attempt-1 execution-fence context
        # before this barrier. That context remains live across takeover.
        handler_entered.set()
        assert resume_handler.wait(timeout=15), "old handler was not released"
        if not observation.get("takeover"):
            return
        stale_ref = cas.put_json(
            {"job_id": job.job_id, "attempt": 1, "result": "stale"},
            ArtifactWriteOptions(
                kind="runtime_quality.c11_result",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.test.C11Result", version="1.0"),
            ),
        )
        stale_id = str(stale_ref.artifact_id)
        for name, operation in (
            (
                "manifest",
                lambda: store.update_manifest_ref(
                    job_id=job.job_id,
                    capability_manifest_ref=stale_id,
                ),
            ),
            (
                "terminal",
                lambda: store.complete_job(
                    job_id=job.job_id,
                    progress={"result_ref": stale_id},
                ),
            ),
        ):
            try:
                operation()
            except ControlJobLeaseLostError:
                observation[f"stale_{name}_refused"] = True
            else:
                observation[f"stale_{name}_refused"] = False

    old_worker = ControlWorker(
        store=_ObservedStore(),
        handler=_old_handler,
        worker_id="worker-old",
        lease_seconds=2,
    )
    old_worker._heartbeat_interval_s = 0.05

    def _run_old() -> None:
        try:
            old_worker._run_with_lease_heartbeat(leased)
        except BaseException as exc:
            thread_errors.append(exc)

    old_thread = threading.Thread(target=_run_old, name="c11-old-handler")
    running = None
    queued = None
    try:
        old_thread.start()
        # Initial heartbeat and bound handler entry happen before saturation,
        # so the removal must reach the actual renewal operation.
        assert handler_entered.wait(timeout=10), "worker did not enter its handler"
        running = executor.submit(
            lambda: (compute_started.set(), release_compute.wait(), "running")[2]
        )
        assert compute_started.wait(timeout=5)
        queued = executor.submit(lambda: (queued_started.set(), "queued")[1])
        if cancel_queued:
            assert queued.cancel()
        clock[0] += timedelta(seconds=1)
        allow_renewal.set()
        assert renewal_attempted.wait(timeout=5), "real renewal was not attempted"
        assert renewal_finished.wait(timeout=5), "real renewal did not return"
        current = raw.get_job(leased.job_id)
        assert current is not None
        observation.update(
            running_unfinished=not running.done(),
            queued_body_unstarted=not queued_started.is_set(),
            state_while_compute_held=current.state,
            renewed=current.lease_expires_at is not None
            and current.lease_expires_at > initial_expiry,
        )

        if not route_control_to_compute and observation.get("renewal_return") is True:
            assert observation["renewal_return"] is True
            assert observation["renewed"] is True
            assert observation["running_unfinished"] is True
            assert observation["queued_body_unstarted"] is True
            assert observation["state_while_compute_held"] == "running"
            assert current.lease_expires_at is not None
            clock[0] = current.lease_expires_at + timedelta(seconds=1)
            replacement = store.lease_next_job(worker_id="worker-new", lease_seconds=5)
            assert replacement is not None and replacement.attempt == 2
            observation["takeover"] = True
            resume_handler.set()
            old_thread.join(timeout=5)
            assert not old_thread.is_alive(), "old handler did not finish after takeover"
            assert not thread_errors
            assert observation["stale_manifest_refused"] is True
            assert observation["stale_terminal_refused"] is True

            def _new_handler(job: Any) -> None:
                result_ref = cas.put_json(
                    {"job_id": job.job_id, "attempt": 2, "result": "current"},
                    ArtifactWriteOptions(
                        kind="runtime_quality.c11_result",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.test.C11Result", version="1.0"),
                    ),
                )
                result_id = str(result_ref.artifact_id)
                manifest_ref = cas.put_json(
                    {"job_id": job.job_id, "attempt": 2, "result_ref": result_id},
                    ArtifactWriteOptions(
                        kind="runtime.capability_manifest",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.test.C11Manifest", version="1.0"),
                    ),
                )
                store.update_manifest_ref(
                    job_id=job.job_id,
                    capability_manifest_ref=str(manifest_ref.artifact_id),
                )
                store.complete_job(job_id=job.job_id, progress={"result_ref": result_id})

            new_worker = ControlWorker(
                store=store,
                handler=_new_handler,
                worker_id="worker-new",
                lease_seconds=5,
            )
            new_worker._run_with_lease_heartbeat(replacement)
            # Materialization through terminal persistence must finish while
            # the original computation is physically held, not after a timeout.
            assert not running.done()
            assert not queued_started.is_set()
            reader = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
            try:
                final = reader.get_job(leased.job_id)
                assert final is not None
                response = final.to_response()
                fresh_cas = FileSystemCAS(Path(cas_path))
                result_id = response.progress["result_ref"]
                result = json.loads(fresh_cas.get_bytes(result_id))
                assert response.capability_manifest_ref is not None
                manifest = json.loads(
                    fresh_cas.get_bytes(str(response.capability_manifest_ref.artifact_id))
                )
                completed_outbox = [
                    event
                    for event in reader.list_outbox_events(state=None, limit=100)
                    if event.job_id == leased.job_id and event.topic == "control.job.completed"
                ]
                with sqlite3.connect(sqlite_path) as db:
                    terminal_events = db.execute(
                        "SELECT event_type, payload_json FROM control_job_events "
                        "WHERE job_id = ? AND event_type IN ('job_completed', 'job_failed')",
                        (leased.job_id,),
                    ).fetchall()
                assert len(terminal_events) == 1
                event_name, event_payload = terminal_events[0]
                assert event_name == "job_completed"
                assert json.loads(event_payload)["lease_owner"] == "worker-new"
                assert json.loads(event_payload)["attempt"] == 2
                assert len(completed_outbox) == 1
                assert final.state == "completed" and final.attempt == 2
                assert result == {
                    "job_id": leased.job_id,
                    "attempt": 2,
                    "result": "current",
                }
                assert manifest == {
                    "job_id": leased.job_id,
                    "attempt": 2,
                    "result_ref": result_id,
                }
                observation["fresh_consumer_current_result"] = True
                observation["single_terminal_event"] = True
            finally:
                reader.close()
        else:
            # Keep the same positive assertion below available to the caller:
            # this is a red witness, not a substitute heartbeat failure.
            assert observation.get("renewal_error") in {
                "RuntimeDependencyTimeoutError",
                "RuntimeDependencyUnavailableError",
            }
    finally:
        allow_renewal.set()
        release_compute.set()
        resume_handler.set()
        old_thread.join(timeout=5)
        assert not old_thread.is_alive(), "old worker did not shut down"
        if running is not None:
            running.result(timeout=5)
        if queued is not None and not cancel_queued:
            queued.result(timeout=5)
        guard.close()
        raw.close()
        executor.shutdown(wait=True, cancel_futures=True)
    results.put(observation)


def _run_capacity_witness(
    tmp_path: Path,
    *,
    route_control_to_compute: bool = False,
    cancel_queued: bool = False,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    process = context.Process(
        target=_capacity_witness_child,
        args=(str(tmp_path / "control.sqlite3"), str(tmp_path / "cas"), results),
        kwargs={
            "route_control_to_compute": route_control_to_compute,
            "cancel_queued": cancel_queued,
        },
    )
    process.start()
    process.join(timeout=45)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
        pytest.fail("service-capacity witness exceeded 45 seconds")
    assert process.exitcode == 0
    try:
        return results.get(timeout=1)
    except Empty:
        pytest.fail("service-capacity witness returned no persisted observation")


def _assert_persisted_renewal_under_held_compute(observed: dict[str, Any]) -> None:
    assert observed.get("renewal_return") is True
    assert observed["renewed"] is True
    assert observed["running_unfinished"] is True
    assert observed["queued_body_unstarted"] is True
    assert observed["state_while_compute_held"] == "running"


@pytest.mark.parametrize("cancel_queued", [False, True], ids=["queued", "cancelled-queued"])
def test_control_lease_and_fencing_keep_reserved_capacity_under_saturated_compute(
    tmp_path: Path,
    cancel_queued: bool,
) -> None:
    removal = os.environ.get("POLISYOS_C11_REMOVE_SERVICE_CAPACITY")
    if removal not in (None, "1"):
        raise ValueError("POLISYOS_C11_REMOVE_SERVICE_CAPACITY must be unset or 1")
    observed = _run_capacity_witness(
        tmp_path, route_control_to_compute=removal == "1", cancel_queued=cancel_queued
    )
    _assert_persisted_renewal_under_held_compute(observed)
    assert observed["stale_manifest_refused"] is True
    assert observed["stale_terminal_refused"] is True
    assert observed["fresh_consumer_current_result"] is True
    assert observed["single_terminal_event"] is True


def test_control_lease_witness_fails_when_routed_to_saturated_compute(
    tmp_path: Path,
) -> None:
    observed = _run_capacity_witness(tmp_path, route_control_to_compute=True)
    assert observed["running_unfinished"] is True
    assert observed["queued_body_unstarted"] is True
    with pytest.raises(AssertionError):
        _assert_persisted_renewal_under_held_compute(observed)
