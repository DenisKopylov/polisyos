"""Prove lease fencing while the installed shared compute executor stays full."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sqlite3
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest

from polisyos.common import async_tools
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    guard_runtime_control_store,
)
from polisyos.runtime.http.services import control_plane_store as store_module
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker

_ROW_LIMIT = 32


def _limited_rows(db: sqlite3.Connection, query: str, job_id: str) -> list[dict[str, Any]]:
    """Read one job's complete bounded row set, failing if the bound is exceeded."""
    rows = db.execute(query + f" LIMIT {_ROW_LIMIT + 1}", (job_id,)).fetchall()
    assert len(rows) <= _ROW_LIMIT, "generated job exceeded the bounded evidence row set"
    return [dict(row) for row in rows]


def _persisted_snapshot(reader: ControlPlaneStore, job_id: str) -> dict[str, Any]:
    """Read every persisted job, event, and outbox column through a fresh connection."""
    with sqlite3.connect(reader._sqlite_path) as db:
        db.row_factory = sqlite3.Row
        jobs = _limited_rows(db, "SELECT * FROM control_jobs WHERE job_id = ?", job_id)
        progress = _limited_rows(db, "SELECT * FROM control_job_progress WHERE job_id = ?", job_id)
        progress = _limited_rows(db, "SELECT * FROM control_job_progress WHERE job_id = ?", job_id)
        events = _limited_rows(
            db,
            "SELECT * FROM control_job_events WHERE job_id = ? ORDER BY event_id",
            job_id,
        )
        outbox = _limited_rows(
            db,
            "SELECT * FROM control_outbox_events WHERE job_id = ? ORDER BY event_id",
            job_id,
        )
    assert len(jobs) == 1
    return {"job_rows": jobs, "job_progress": progress, "job_events": events, "job_outbox": outbox}


def _queue_snapshot(
    executor: Any, running: Any, queued: Any, queued_body_calls: list[int]
) -> dict[str, Any]:
    """Return actual admission counters for the installed bounded executor."""
    with executor._admission_lock:
        return {
            "capacity": executor._max_workers,
            "queue_capacity": executor._max_queued,
            "physical_workers": executor._physical_workers,
            "queued_jobs": executor._queued_jobs,
            "outstanding_jobs": executor._outstanding_jobs,
            "running_physical": running.running() and not running.done(),
            "queued_pending": not queued.done() and not queued.running(),
            "queued_body_calls": len(queued_body_calls),
        }


def _python_origin_map() -> dict[str, Any]:
    """Bind loaded PolicyOS/test modules to their real source paths and bytes."""
    product_root = Path(__file__).resolve().parents[4]
    source_roots = {
        "polisyos": product_root / "src" / "polisyos",
        "tests": product_root / "tests",
    }
    modules: list[dict[str, Any]] = []
    foreign: list[dict[str, str]] = []
    for name, module in sorted(sys.modules.items()):
        if name != "polisyos" and not name.startswith(("polisyos.", "tests.")):
            continue
        origin = getattr(module, "__file__", None)
        if isinstance(origin, str) and origin.endswith(".py"):
            path = Path(origin).resolve()
            namespace = (
                "polisyos" if name == "polisyos" or name.startswith("polisyos.") else "tests"
            )
            if not path.is_relative_to(source_roots[namespace]):
                foreign.append({"module": name, "path": str(path)})
                continue
            data = path.read_bytes()
            modules.append(
                {
                    "module": name,
                    "path": str(path),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        for location in getattr(module, "__path__", ()):
            path = Path(location).resolve()
            namespace = (
                "polisyos" if name == "polisyos" or name.startswith("polisyos.") else "tests"
            )
            if not path.is_relative_to(source_roots[namespace]):
                foreign.append({"module": name, "path": str(path)})
    return {"pid": os.getpid(), "modules": modules, "foreign": foreign}


def _run_fencing_case(
    observation_path: str,
    remove_control_capacity: bool,
    expected_test_sha256: str,
    parent_context: dict[str, Any],
) -> None:
    """Exercise one fresh process and persist actual state for the pytest parent."""
    observation: dict[str, Any] = {
        "pid": os.getpid(),
        "remove_control_capacity": remove_control_capacity,
        "stage": "setup",
        "parent_context": parent_context,
        "source": {
            "test_path": str(Path(__file__).resolve()),
            "test_bytes": len(Path(__file__).read_bytes()),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "expected_test_sha256": expected_test_sha256,
        },
    }
    assert observation["source"]["test_sha256"] == expected_test_sha256
    tmp_root = Path(observation_path).parent
    tmp_root.mkdir(parents=True, exist_ok=True)
    executor: Any = None
    raw: ControlPlaneStore | None = None
    store: Any = None
    reader: ControlPlaneStore | None = None
    original_guard: Any = None
    removed_guard: Any = None
    first: Any = None
    queued: Any = None
    compute_started = Event()
    release_compute = Event()
    handler_entered = Event()
    release_a = Event()
    thread: Thread | None = None
    thread_errors: list[str] = []
    stale_refusals: list[str] = []
    queued_body_calls: list[int] = []
    monkeypatch = pytest.MonkeyPatch()
    try:
        profile = async_tools.SharedExecutorProfile(
            capacity=1,
            queue_capacity=1,
            revision="e02-c120-installed-canonical-pool-r1",
        )
        async_tools.configure_shared_executor_profile(profile)
        executor = async_tools.get_shared_executor()
        assert executor is async_tools.get_shared_executor()
        assert isinstance(executor, async_tools._SharedExecutor)
        assert async_tools.get_shared_executor_profile() == profile
        observation["canonical_executor"] = {
            "identity_rechecked": True,
            "type": type(executor).__module__ + "." + type(executor).__qualname__,
            "id": id(executor),
            "profile": {
                "capacity": profile.capacity,
                "queue_capacity": profile.queue_capacity,
                "revision": profile.revision,
            },
        }

        database = tmp_root / "control.sqlite3"
        raw = ControlPlaneStore(backend="sqlite", sqlite_path=database)
        store = guard_runtime_control_store(raw)
        reader = ControlPlaneStore(backend="sqlite", sqlite_path=database)
        original_guard = store._guard
        clock = [datetime(2026, 10, 28, tzinfo=UTC)]
        monkeypatch.setattr(store_module, "_utc_now", lambda: clock[0])
        job_id = "job-c120-canonical-saturation"
        store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id="run-c120-canonical-saturation",
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref="manifest-before",
            payload_ref=None,
            submitted_by="test",
        )
        attempt_a = store.lease_next_job(worker_id="owner-a", lease_seconds=5)
        assert attempt_a is not None and attempt_a.attempt == 1
        assert attempt_a.lease_expires_at is not None

        def stale_handler(job: Any) -> None:
            handler_entered.set()
            assert release_a.wait(timeout=20), "stale owner was not released after takeover"
            operations = (
                (
                    "progress",
                    lambda: store.update_progress_state(
                        job_id=job.job_id,
                        state="running",
                        progress={"owner": "a", "attempt": 1},
                    ),
                ),
                (
                    "manifest",
                    lambda: store.update_manifest_ref(
                        job_id=job.job_id,
                        capability_manifest_ref="manifest-owner-a",
                    ),
                ),
                (
                    "terminal",
                    lambda: store.complete_job(
                        job_id=job.job_id,
                        progress={"owner": "a", "attempt": 1},
                    ),
                ),
            )
            for name, operation in operations:
                try:
                    operation()
                except ControlJobLeaseLostError:
                    stale_refusals.append(name)
                else:
                    raise AssertionError(f"stale attempt A {name} write was accepted")

        worker_a = ControlWorker(
            store=store,
            handler=stale_handler,
            worker_id="owner-a",
            lease_seconds=5,
        )
        worker_a._heartbeat_interval_s = 60.0

        def run_a() -> None:
            try:
                worker_a._run_with_lease_heartbeat(attempt_a)
            except BaseException as exc:  # returned to parent as execution evidence
                thread_errors.append(f"{type(exc).__name__}: {exc}")

        thread = Thread(target=run_a, name="c120-expired-owner-a", daemon=True)
        thread.start()
        assert handler_entered.wait(timeout=5)
        owner_before_hold = reader.get_job(job_id)
        assert owner_before_hold is not None
        assert (
            owner_before_hold.state,
            owner_before_hold.lease_owner,
            owner_before_hold.attempt,
        ) == (
            "running",
            "owner-a",
            1,
        )

        def compute() -> str:
            compute_started.set()
            assert release_compute.wait(timeout=30), "held compute was not released in cleanup"
            return "event-held synthetic callable"

        first = executor.submit(compute)
        assert compute_started.wait(timeout=5)
        queued = executor.submit(lambda: queued_body_calls.append(os.getpid()))
        assert not queued.done() and not queued.running()
        with pytest.raises(async_tools.SharedExecutorBackpressureError) as overflow:
            executor.submit(lambda: None)
        assert overflow.value.code == "shared_executor_queue_full"
        queue = _queue_snapshot(executor, first, queued, queued_body_calls)
        assert queue == {
            "capacity": 1,
            "queue_capacity": 1,
            "physical_workers": 1,
            "queued_jobs": 1,
            "outstanding_jobs": 2,
            "running_physical": True,
            "queued_pending": True,
            "queued_body_calls": 0,
        }
        observation["queue_at_full"] = queue
        observation["overflow"] = {
            "code": overflow.value.code,
            "capacity": overflow.value.capacity,
            "queue_capacity": overflow.value.queue_capacity,
            "queue_depth": overflow.value.queue_depth,
        }

        assert executor is async_tools.get_shared_executor()
        observation["control_executor"] = {
            "is_separate_from_compute": original_guard._executor is not executor,
            "id": id(original_guard._executor),
        }
        observation["stage"] = "renew_under_held_compute"
        before_renewal = _persisted_snapshot(reader, job_id)
        if remove_control_capacity:
            removed_guard = BlockingDependencyGuard(
                dependency_name=original_guard._dependency_name,
                timeout_seconds=original_guard._timeout_seconds,
                breaker=original_guard._breaker,
                executor=executor,
                unavailable_exception_types=original_guard._unavailable_exception_types,
                unavailable_exception_predicate=original_guard._unavailable_exception_predicate,
            )
            assert removed_guard._executor is executor
            store._guard = removed_guard
            with pytest.raises(RuntimeDependencyUnavailableError) as removal_error:
                store.renew_job_lease(
                    job_id=job_id,
                    worker_id="owner-a",
                    lease_seconds=30,
                    expected_attempt=1,
                )
            exc = removal_error.value
            cause = exc.__cause__
            assert exc.dependency == "control_plane_store"
            assert exc.code == "control_plane_store_unavailable"
            assert isinstance(cause, async_tools.SharedExecutorBackpressureError)
            assert cause.code == "shared_executor_queue_full"
            observation["removal_failure"] = {
                "dependency": exc.dependency,
                "code": exc.code,
                "cause_type": type(cause).__name__,
                "cause_code": cause.code,
                "actual_control_call": "renew_job_lease",
            }
            after_removal = _persisted_snapshot(reader, job_id)
            assert after_removal == before_renewal
            observation["removal_state_unchanged"] = after_removal == before_renewal
            store._guard = original_guard
            removed_guard.close()
            removed_guard = None

        assert store._guard._executor is not executor
        assert (
            store.renew_job_lease(
                job_id=job_id,
                worker_id="owner-a",
                lease_seconds=30,
                expected_attempt=1,
            )
            is True
        )
        renewed = reader.get_job(job_id)
        assert renewed is not None and renewed.lease_expires_at is not None
        assert renewed.lease_expires_at > attempt_a.lease_expires_at
        observation["renewal"] = {
            "under_held_compute": True,
            "before": attempt_a.lease_expires_at.isoformat(),
            "after": renewed.lease_expires_at.isoformat(),
            "persisted": True,
        }
        queue_after_renewal = _queue_snapshot(executor, first, queued, queued_body_calls)
        assert queue_after_renewal["running_physical"] is True
        assert queue_after_renewal["queued_pending"] is True
        assert queue_after_renewal["outstanding_jobs"] == 2
        assert queue_after_renewal["queued_body_calls"] == 0

        clock[0] = renewed.lease_expires_at + timedelta(seconds=1)
        assert (
            store.renew_job_lease(
                job_id=job_id,
                worker_id="owner-a",
                lease_seconds=30,
                expected_attempt=1,
            )
            is False
        )
        attempt_b = store.lease_next_job(worker_id="owner-b", lease_seconds=20)
        assert attempt_b is not None
        assert (attempt_b.state, attempt_b.lease_owner, attempt_b.attempt) == (
            "running",
            "owner-b",
            2,
        )
        baseline_after_b = _persisted_snapshot(reader, job_id)
        typed_after_b = reader.get_job(job_id)
        assert typed_after_b is not None
        assert (typed_after_b.state, typed_after_b.lease_owner, typed_after_b.attempt) == (
            "running",
            "owner-b",
            2,
        )
        observation["stage"] = "stale_a_fenced"
        release_a.set()
        assert thread is not None
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert thread_errors == []
        assert stale_refusals == ["progress", "manifest", "terminal"]
        after_stale_a = _persisted_snapshot(reader, job_id)
        assert after_stale_a == baseline_after_b
        observation["stale_a"] = {
            "refused_operations": stale_refusals,
            "all_job_row_event_outbox_columns_unchanged": after_stale_a == baseline_after_b,
            "job_rows": after_stale_a["job_rows"],
            "job_event_count": len(after_stale_a["job_events"]),
            "job_outbox_count": len(after_stale_a["job_outbox"]),
        }

        def current_handler(job: Any) -> None:
            store.update_manifest_ref(
                job_id=job.job_id,
                capability_manifest_ref="manifest-owner-b",
            )
            store.update_progress_state(
                job_id=job.job_id,
                state="running",
                progress={"owner": "b", "attempt": 2},
            )
            store.complete_job(
                job_id=job.job_id,
                progress={"owner": "b", "attempt": 2},
            )

        worker_b = ControlWorker(
            store=store,
            handler=current_handler,
            worker_id="owner-b",
            lease_seconds=20,
        )
        worker_b._heartbeat_interval_s = 60.0
        worker_b._run_with_lease_heartbeat(attempt_b)
        completed = reader.get_job(job_id)
        assert completed is not None
        assert (
            completed.state,
            completed.attempt,
            completed.lease_owner,
            completed.capability_manifest_ref,
        ) == ("completed", 2, None, "manifest-owner-b")
        assert completed.progress["owner"] == "b"
        assert completed.progress["attempt"] == 2

        final = _persisted_snapshot(reader, job_id)
        assert len(final["job_progress"]) == 1
        final_progress = json.loads(final["job_progress"][0]["progress_json"])
        assert (final_progress["owner"], final_progress["attempt"]) == ("b", 2)
        assert len(final["job_progress"]) == 1
        final_progress = json.loads(final["job_progress"][0]["progress_json"])
        assert (final_progress["owner"], final_progress["attempt"]) == ("b", 2)
        terminal_rows = [
            row
            for row in final["job_events"]
            if row["event_type"] in {"job_completed", "job_failed"}
        ]
        assert len(terminal_rows) == 1
        assert terminal_rows[0]["event_type"] == "job_completed"
        terminal_payload = json.loads(terminal_rows[0]["payload_json"])
        assert (terminal_payload["lease_owner"], terminal_payload["attempt"]) == ("owner-b", 2)
        completion_rows = [
            row for row in final["job_outbox"] if row["topic"] == "control.job.completed"
        ]
        assert len(completion_rows) == 1
        completion_payload = json.loads(completion_rows[0]["payload_json"])
        assert (completion_payload["lease_owner"], completion_payload["attempt"]) == (
            "owner-b",
            2,
        )
        terminal = reader.get_job_terminal_source_event_record(job_id)
        outbox = reader.get_job_completed_outbox_event(job_id)
        assert terminal.event_id == terminal_rows[0]["event_id"]
        assert outbox is not None and outbox.event_id == completion_rows[0]["event_id"]
        observation["current_owner_terminal"] = {
            "state": completed.state,
            "owner": "owner-b",
            "attempt": completed.attempt,
            "terminal_event_count": len(terminal_rows),
            "terminal_event_id": terminal.event_id,
            "completion_outbox_count": len(completion_rows),
            "completion_outbox_event_id": outbox.event_id,
        }

        final_queue = _queue_snapshot(executor, first, queued, queued_body_calls)
        assert final_queue["running_physical"] is True
        assert final_queue["queued_pending"] is True
        assert final_queue["outstanding_jobs"] == 2
        assert final_queue["queued_body_calls"] == 0
        observation["queue_through_readback"] = final_queue
        observation["imports"] = _python_origin_map()
        assert observation["imports"]["foreign"] == []
        observation["stage"] = "complete"
    except BaseException as exc:
        observation["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        raise
    finally:
        release_a.set()
        if thread is not None:
            thread.join(timeout=5)
            observation["stale_thread_stopped"] = not thread.is_alive()
        release_compute.set()
        if first is not None:
            try:
                first.result(timeout=5)
                observation["held_compute_released"] = True
            except BaseException as exc:
                observation["held_compute_cleanup_error"] = f"{type(exc).__name__}: {exc}"
        if queued is not None and not queued.cancelled():
            try:
                queued.result(timeout=5)
            except BaseException as exc:
                observation["queued_compute_cleanup_error"] = f"{type(exc).__name__}: {exc}"
        if executor is not None and first is not None and queued is not None:
            observation["queue_after_release"] = _queue_snapshot(
                executor, first, queued, queued_body_calls
            )
        if store is not None and original_guard is not None:
            store._guard = original_guard
        if removed_guard is not None:
            removed_guard.close()
        if reader is not None:
            reader.close()
        if store is not None:
            store.close()
        elif raw is not None:
            raw.close()
        monkeypatch.undo()
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        Path(observation_path).write_text(
            json.dumps(observation, sort_keys=True, indent=2, default=str) + "\n"
        )


def _run_and_assert_capacity_case(
    tmp_path: Path, remove_control_capacity: bool, request: pytest.FixtureRequest
) -> None:
    """Keep renewal/fencing/terminal ownership on control while compute is truly full."""
    observation_path = tmp_path / "observation.json"
    context = multiprocessing.get_context("spawn")
    source_path = Path(__file__).resolve()
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    plugin_names = sorted(name for name, _ in request.config.pluginmanager.list_name_plugin())
    parent_context = {
        "pid": os.getpid(),
        "pytest_version": pytest.__version__,
        "rootpath": str(request.config.rootpath),
        "inipath": str(request.config.inipath) if request.config.inipath else None,
        "plugins": plugin_names,
        "sys_path": sys.path,
        "imports": _python_origin_map(),
    }
    assert parent_context["imports"]["foreign"] == []
    process = context.Process(
        target=_run_fencing_case,
        args=(str(observation_path), remove_control_capacity, source_sha256, parent_context),
    )
    process.start()
    process.join(timeout=90)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("event-held fencing child exceeded its protective deadline")
    assert observation_path.is_file(), "child returned no persisted observation"
    observed = json.loads(observation_path.read_text())
    assert process.exitcode == 0, json.dumps(observed, sort_keys=True)
    assert observed["stage"] == "complete", json.dumps(observed, sort_keys=True)
    assert observed["source"]["test_sha256"] == source_sha256
    assert observed["imports"]["foreign"] == []
    assert observed["canonical_executor"]["identity_rechecked"] is True
    assert observed["queue_at_full"]["running_physical"] is True
    assert observed["queue_at_full"]["queued_pending"] is True
    assert observed["overflow"]["code"] == "shared_executor_queue_full"
    assert observed["renewal"]["under_held_compute"] is True
    assert observed["renewal"]["persisted"] is True
    assert observed["stale_a"]["refused_operations"] == ["progress", "manifest", "terminal"]
    assert observed["stale_a"]["all_job_row_event_outbox_columns_unchanged"] is True
    assert observed["current_owner_terminal"]["terminal_event_count"] == 1
    assert observed["current_owner_terminal"]["completion_outbox_count"] == 1
    assert observed["current_owner_terminal"]["owner"] == "owner-b"
    assert observed["current_owner_terminal"]["attempt"] == 2
    assert observed["queue_through_readback"]["outstanding_jobs"] == 2
    assert observed["queue_after_release"]["queued_jobs"] == 0
    assert observed["queue_after_release"]["outstanding_jobs"] == 0
    assert observed["queue_after_release"]["queued_body_calls"] == 1
    if remove_control_capacity:
        assert observed["removal_failure"]["actual_control_call"] == "renew_job_lease"
        assert observed["removal_failure"]["cause_code"] == "shared_executor_queue_full"
        assert observed["removal_state_unchanged"] is True
    assert observed["stale_thread_stopped"] is True
    assert observed["held_compute_released"] is True


@pytest.mark.parametrize(
    "remove_control_capacity",
    [False, True],
    ids=["reserved-control-pool", "removed-control-capacity"],
)
def test_saturated_compute_fences_expired_attempt_and_accepts_current_owner_terminal_once(
    tmp_path: Path, remove_control_capacity: bool, request: pytest.FixtureRequest
) -> None:
    """Run the positive and property-specific removal control independently."""
    _run_and_assert_capacity_case(
        tmp_path,
        remove_control_capacity,
        request,
    )
