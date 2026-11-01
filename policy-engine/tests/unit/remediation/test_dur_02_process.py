"""Current DUR-02 real worker generations and persisted-effect handover controls.

The backend collaborator is a concrete fixture implementation, not an external
service status or idempotency contract. Fallback/local execution and the
filesystem/SQLite effect path are real production consumers.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.http.services.control as _control_facade  # noqa: F401
from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import read_runtime_invocation_attempts
from polisyos.core.run.context import RunContext
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointCorruptedError,
    CheckpointError,
    CheckpointHistory,
    create_checkpoint,
    load_checkpoint,
    load_checkpoint_head,
    load_checkpoint_history,
    resume_from_checkpoint,
    update_checkpoint_head,
    write_checkpoint_history,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult, WorkflowReport
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.runner.fallback_runner import (
    FallbackNotAuthorizedError,
    FallbackWorkflowRunner,
    HealthFailureDisposition,
    PrimaryExecutionOutcomeUnknownError,
)
from polisyos.scientist.orchestration.engine.runner.protocol import (
    RunnerHealth,
    WorkflowRunnerBackend,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from tests._helpers.dur02_effects import (
    _CheckpointedEffectNode,
    _confirmed_effect_receipt,
    _CostedRetryEffectNode,
    _effects,
    _LostCheckpointReply,
    _PersistedEffectNode,
    _RemainingEffectNode,
    _UnbudgetedEffectNode,
    _UnbudgetedRemainingEffectNode,
)

_WORKER_CHILD = r"""
import json,sys
from pathlib import Path
import polisyos.runtime.http.services.control
from polisyos.runtime.http.services import control_plane_store as sm, control_worker as wm
assert Path(sm.__file__).resolve().is_relative_to(Path(sys.argv[3]))
assert Path(wm.__file__).resolve().is_relative_to(Path(sys.argv[3]))
store = sm.ControlPlaneStore(backend="sqlite",sqlite_path=Path(sys.argv[1]))
if sys.argv[2] == "takeover":
    job = store.lease_next_job(worker_id="worker-B",lease_seconds=300)
    assert job is not None and job.attempt == 2
else:
    def handler(job):
        admitted = store.current_execution_job_record()
        assert admitted.lease_owner == "worker-B" and admitted.attempt == 2
        store.update_progress_state(job_id=job.job_id,state="running",progress={"phase":"current-B"})
        store.complete_job(job_id=job.job_id,progress={"phase":"completed-B"})
    worker = wm.ControlWorker(store=store,handler=handler,worker_id="worker-B",lease_seconds=300)
    job = store.get_job("dur02-current-job")
    if job.lease_owner == "worker-B":
        worker._run_with_lease_heartbeat(job)
    else:
        assert worker.dispatch_once()
    job = store.get_job("dur02-current-job")
assert job is not None
print(json.dumps({"state":job.state,"attempt":job.attempt,"lease_owner":job.lease_owner,
                  "progress":job.progress,"capability_manifest_ref":job.capability_manifest_ref}))
"""


def _worker_child(path: Path, action: str) -> dict[str, Any]:
    source_root = Path(__file__).resolve().parents[3] / "src"
    result = subprocess.run(
        [sys.executable, "-c", _WORKER_CHILD, str(path), action, str(source_root)],
        env={**os.environ, "PYTHONPATH": str(source_root)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("after_expiry", ["expired", "new_running", "new_completed"])
def test_actual_handler_loses_every_protected_write_after_expiry_and_takeover(
    tmp_path: Path,
    after_expiry: str,
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    cas = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    options = ArtifactWriteOptions(
        kind="fixture.dur02.effect", media_type="application/octet-stream"
    )
    with tenant_scope(None, tenant_id="dur02-tenant", cell_id="dur02-cell"):
        original_ref = cas.put_bytes(
            b"current admitted evidence", options, return_selected_profile=True
        )
        stale_ref = cas.put_bytes(
            b"stale result retained only for diagnostics", options, return_selected_profile=True
        )
    original_id, stale_id = str(original_ref.artifact_id), str(stale_ref.artifact_id)
    store.create_job(
        job_id="dur02-current-job",
        kind="workflow_run",
        run_id="dur02-current-run",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=original_id,
        payload_ref=None,
        submitted_by="dur02-process-fixture",
    )
    observed = []

    def handler(job: Any) -> None:
        assert store.current_execution_job_record().attempt == 1
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job.job_id),
            )
        assert not store.renew_job_lease(
            job_id=job.job_id, worker_id="worker-A", lease_seconds=300, expected_attempt=1
        )
        if after_expiry == "new_running":
            assert _worker_child(database, "takeover")["lease_owner"] == "worker-B"
        elif after_expiry == "new_completed":
            assert _worker_child(database, "finish")["state"] == "completed"
        before = store.get_job(job.job_id)
        history = store.list_job_state_transitions(job.job_id)
        outbox = store.list_outbox_events(state=None, limit=100)
        operations = {
            "complete": lambda: store.complete_job(
                job_id=job.job_id,
                capability_manifest_ref=stale_id,
                progress={"phase": "stale-complete"},
            ),
            "fail": lambda: store.fail_job(
                job_id=job.job_id,
                error_message="stale failure",
                capability_manifest_ref=stale_id,
                progress={"phase": "stale-fail"},
            ),
            "progress": lambda: store.update_progress_state(
                job_id=job.job_id, state="failed", progress={"phase": "stale-progress"}
            ),
            "manifest": lambda: store.update_manifest_ref(
                job_id=job.job_id, capability_manifest_ref=stale_id
            ),
            "current_record": store.current_execution_job_record,
        }
        for name, operation in operations.items():
            with pytest.raises(ControlJobLeaseLostError):
                operation()
            assert store.get_job(job.job_id) == before, name
            assert store.list_job_state_transitions(job.job_id) == history, name
            assert store.list_outbox_events(state=None, limit=100) == outbox, name
            observed.append(name)

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-A", lease_seconds=300)
    assert worker.dispatch_once()
    assert observed == ["complete", "fail", "progress", "manifest", "current_record"]
    completed = (
        store.get_job("dur02-current-job")
        if after_expiry == "new_completed"
        else _worker_child(database, "finish")
    )
    if isinstance(completed, dict):
        assert completed["state"] == "completed" and completed["attempt"] == 2
        assert completed["capability_manifest_ref"] == original_id
    else:
        assert completed is not None and completed.state == "completed" and completed.attempt == 2
        assert completed.capability_manifest_ref == original_id
    fresh = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="dur02-tenant", cell_id="dur02-cell"):
        assert fresh.get_bytes(stale_ref) == b"stale result retained only for diagnostics"
        assert fresh.get_bytes(original_ref) == b"current admitted evidence"
    with (
        tenant_scope(None, tenant_id="foreign-tenant", cell_id="dur02-cell"),
        pytest.raises(ArtifactOwnershipError),
    ):
        fresh.get_bytes(stale_ref)


def _create_control_job(store: ControlPlaneStore, job_id: str) -> None:
    store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id="dur02-current-run",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="dur02-fixture",
    )


def _database_rows(database: Path) -> list[str]:
    with sqlite3.connect(database) as connection:
        return list(connection.iterdump())


def test_actual_stale_bound_handler_cannot_publish_through_sibling_mutation_inlets(
    tmp_path: Path,
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    observed = []

    def handler(job: Any) -> None:
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job.job_id),
            )
        assert _worker_child(database, "takeover")["attempt"] == 2
        admin = ControlPlaneStore(backend="sqlite", sqlite_path=database)
        _create_control_job(admin, "pending-child")
        before = _database_rows(database)
        instant = datetime.now(UTC)
        operations = {
            "upsert": lambda: store.upsert_progress(job_id=job.job_id, progress={"stale": True}),
            "event": lambda: store.append_event(
                job_id=job.job_id, event_type="stale", payload={"stale": True}
            ),
            "outbox": lambda: store.enqueue_outbox_event(
                topic="stale", payload={"stale": True}, job_id=job.job_id
            ),
            "child_event": lambda: store.append_event(
                job_id="pending-child", event_type="stale", payload={"stale": True}
            ),
            "child_outbox": lambda: store.enqueue_outbox_event(
                topic="stale", payload={"stale": True}, job_id="pending-child"
            ),
            "create": lambda: _create_control_job(store, "stale-created-child"),
            "mark_running": lambda: store.mark_running(job_id=job.job_id, worker_id="worker-A"),
            "lease_next": lambda: store.lease_next_job(worker_id="worker-A"),
            "scenario": lambda: store.compare_and_set_scenario_head(
                scenario_id="stale",
                baseline_run_id="run",
                expected_revision=0,
                new_revision=1,
                artifact_ref="sha256:" + "a" * 64,
                manifest_hash="b" * 64,
            ),
            "step_up": lambda: store.consume_step_up_assertion(
                assertion_id="stale-assertion", expires_at=int(instant.timestamp()) + 300
            ),
            "human_reservation": lambda: store.reserve_human_decision_action(
                tenant_id="fixture",
                governed_action_key="sha256:" + "a" * 64,
                reservation_id="stale",
                binding_sha256="sha256:" + "b" * 64,
                now=instant,
                lease_seconds=300,
                record_valid_until=instant + timedelta(hours=1),
            ),
            "worker_heartbeat": lambda: store.heartbeat_worker(
                worker_id="worker-A", state="running", lease_seconds=300
            ),
            "worker_release": lambda: store.release_worker(worker_id="worker-A"),
        }
        for name, operation in operations.items():
            with pytest.raises(ControlJobLeaseLostError):
                operation()
            assert _database_rows(database) == before, name
            observed.append(name)

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-A", lease_seconds=300)
    assert worker.dispatch_once()
    assert observed == [
        "upsert",
        "event",
        "outbox",
        "child_event",
        "child_outbox",
        "create",
        "mark_running",
        "lease_next",
        "scenario",
        "step_up",
        "human_reservation",
        "worker_heartbeat",
        "worker_release",
    ]
    assert _worker_child(database, "finish")["state"] == "completed"


@pytest.mark.parametrize("terminal", ["complete", "fail"])
def test_current_bound_terminal_publication_preserves_internal_and_admin_paths(
    tmp_path: Path,
    terminal: str,
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")

    def handler(job: Any) -> None:
        store.upsert_progress(job_id=job.job_id, progress={"phase": "active"})
        store.append_event(job_id=job.job_id, event_type="fixture", payload={"phase": "active"})
        store.enqueue_outbox_event(topic="fixture", payload={"phase": "active"}, job_id=job.job_id)
        if terminal == "complete":
            store.complete_job(job_id=job.job_id, progress={"phase": "complete"})
            completed = store.current_execution_completed_job_record()
            store.publish_completed_job_proof(
                job_id=job.job_id,
                expected_progress=completed.progress,
                proof_ref="sha256:" + "a" * 64,
                proof_payload={
                    "job_id": job.job_id,
                    "run_id": completed.run_id,
                    "worker_id": "worker-A",
                    "control_store_state_transitions": store.list_job_state_transitions(job.job_id),
                },
            )
        else:
            store.fail_job(
                job_id=job.job_id, error_message="fixture failure", progress={"phase": "fail"}
            )
        with pytest.raises(ControlJobLeaseLostError):
            store.append_event(job_id=job.job_id, event_type="after-terminal", payload={})

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-A", lease_seconds=300)
    assert worker.dispatch_once()
    record = store.get_job("dur02-current-job")
    assert record is not None and record.state == (
        "completed" if terminal == "complete" else "failed"
    )
    assert record.lease_owner is None and record.lease_expires_at is None
    store.upsert_progress(job_id=record.job_id, progress={"admin_projection": True})
    assert store.get_job(record.job_id).progress == {"admin_projection": True}


@pytest.mark.parametrize("terminal", ["complete", "fail"])
def test_bound_terminal_event_fault_rolls_back_state_progress_history_and_outbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert job is not None
    original_append = store.append_event

    def fail_terminal_event(**kwargs: Any) -> None:
        if kwargs["event_type"] in {"job_completed", "job_failed"}:
            raise OSError("actual publication boundary fault")
        original_append(**kwargs)

    monkeypatch.setattr(store, "append_event", fail_terminal_event)
    before = _database_rows(database)

    def operation() -> None:
        if terminal == "complete":
            store.complete_job(job_id=job.job_id, progress={"terminal": terminal})
        else:
            store.fail_job(
                job_id=job.job_id, error_message="fixture", progress={"terminal": terminal}
            )

    with (
        store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt),
        pytest.raises(OSError, match="publication boundary"),
    ):
        operation()
    assert _database_rows(database) == before


@pytest.mark.parametrize("terminal", ["complete", "fail"])
def test_bound_terminal_commit_fault_rolls_back_all_native_sqlite_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    """A fault at the actual final commit rolls back every pending publication."""
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert job is not None
    native_connection = store._sqlite_connection
    observations: list[str] = []

    class CommitFaultConnection:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def __getattr__(self, name: str) -> Any:
            return getattr(self.connection, name)

        def commit(self) -> None:
            rows = self.connection.execute(
                "SELECT state FROM control_jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()
            assert rows["state"] == ("completed" if terminal == "complete" else "failed")
            observations.append("commit-fault")
            raise sqlite3.OperationalError("fixture native commit failure")

        def rollback(self) -> None:
            observations.append("rollback")
            self.connection.rollback()

    @contextmanager
    def faulting_connection() -> Iterator[CommitFaultConnection]:
        with native_connection() as connection:
            yield CommitFaultConnection(connection)

    def operation() -> None:
        if terminal == "complete":
            store.complete_job(job_id=job.job_id, progress={"terminal": terminal})
        else:
            store.fail_job(
                job_id=job.job_id,
                error_message="fixture",
                progress={"terminal": terminal},
            )

    before = _database_rows(database)
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt),
        monkeypatch.context() as patch,
    ):
        patch.setattr(store, "_sqlite_connection", faulting_connection)
        with pytest.raises(sqlite3.OperationalError, match="native commit failure"):
            operation()
    assert observations == ["commit-fault", "rollback"]
    assert _database_rows(database) == before


def test_actual_lease_expiry_during_publication_rolls_back_all_rows(tmp_path: Path) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=1)
    assert job is not None and job.lease_expires_at is not None
    before = _database_rows(database)

    def delayed_publication() -> None:
        with store._job_transaction():
            store.upsert_progress(job_id=job.job_id, progress={"too_late": True})
            store.append_event(job_id=job.job_id, event_type="too_late", payload={})
            store.enqueue_outbox_event(topic="too_late", payload={}, job_id=job.job_id)
            time.sleep(max(0, (job.lease_expires_at - datetime.now(UTC)).total_seconds()) + 0.1)

    with (
        store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt),
        pytest.raises(ControlJobLeaseLostError, match="expired"),
    ):
        delayed_publication()
    assert _database_rows(database) == before


def test_current_source_lease_can_publish_existing_child_job_api(tmp_path: Path) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert job is not None
    with store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt):
        _create_control_job(store, "child")
        store.upsert_progress(job_id="child", progress={"source_job": job.job_id})
        store.append_event(job_id="child", event_type="fixture_child", payload={})
        store.enqueue_outbox_event(topic="fixture_child", payload={}, job_id="child")
        assert store.current_execution_job_record().job_id == job.job_id
    child = store.get_job("child")
    assert child is not None and child.state == "pending"
    assert child.progress == {"source_job": job.job_id}


def test_same_transaction_actual_lease_renewal_allows_publication_after_initial_expiry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=2)
    assert job is not None and job.lease_expires_at is not None
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt),
        store._job_transaction(),
    ):
        assert store.renew_job_lease(
            job_id=job.job_id, worker_id="worker-A", expected_attempt=job.attempt, lease_seconds=300
        )
        time.sleep(max(0, (job.lease_expires_at - datetime.now(UTC)).total_seconds()) + 0.1)
        store.upsert_progress(job_id=job.job_id, progress={"renewed": True})
        store.append_event(job_id=job.job_id, event_type="renewed", payload={})
    current = store.get_job(job.job_id)
    assert current is not None and current.lease_expires_at > job.lease_expires_at
    assert current.progress == {"renewed": True}


@pytest.mark.parametrize("rewrite", ["self_generation", "unproven_terminal"])
def test_bound_handler_cannot_forge_a_new_transaction_admission(
    tmp_path: Path, rewrite: str
) -> None:
    database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=database)
    _create_control_job(store, "dur02-current-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert job is not None
    before = _database_rows(database)

    def rewrite_identity() -> None:
        if rewrite == "self_generation":
            store.mark_running(job_id=job.job_id, worker_id="worker-A", lease_seconds=300)
        else:
            store._execute(
                "UPDATE control_jobs SET state='completed', lease_owner=NULL, lease_expires_at=NULL WHERE job_id=?",
                (job.job_id,),
            )

    with (
        store.job_execution_fence(job_id=job.job_id, worker_id="worker-A", attempt=job.attempt),
        pytest.raises(ControlJobLeaseLostError),
    ):
        rewrite_identity()
    assert _database_rows(database) == before


class _FixturePrimary:
    """Concrete typed fixture backend; it provides no external reconciliation authority."""

    def __init__(
        self, *, health: str = "healthy", execution_error: BaseException | None = None
    ) -> None:
        self.health = health
        self.execution_error = execution_error

    async def health_check(self) -> RunnerHealth:
        if self.health == "connection":
            raise ConnectionError("pre-dispatch transport unavailable")
        if self.health == "permission":
            raise PermissionError("access denied")
        if self.health == "message_only":
            raise RuntimeError("connection refused; text alone is not authority")
        return RunnerHealth(backend="fixture-primary", healthy=self.health == "healthy")

    async def execute_workflow(
        self,
        workflow: WorkflowSpec,
        state: ExperimentState,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        **kwargs: Any,
    ) -> WorkflowExecutionResult:
        del kwargs
        admitted = state.model_copy(deep=True)
        admitted.params["backend"] = "primary"
        outcome = registry.get(workflow.nodes[0].node_id).execute(ctx, admitted)
        if self.execution_error is not None:
            raise self.execution_error
        return WorkflowExecutionResult(
            state=outcome.state,
            report=WorkflowReport(
                workflow_id=workflow.workflow_id,
                run_id=state.run_id,
                error_policy="fail_fast",
                status="ok",
            ),
        )


def _handover_inputs(tmp_path: Path) -> tuple[Any, ...]:
    cas = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(cas)
    run = RunContext.start(
        store=cas,
        registry_bundle=bundle.bundle_ref,
        run_id="dur02-persisted-handover",
        run_dir=tmp_path / "run",
    )
    ctx = ExecutionContext(store=cas, run=run, logger=logging.getLogger("dur02-persisted"))
    database = tmp_path / "effects.sqlite3"
    node = _PersistedEffectNode(database)
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="dur02_handover",
        nodes=[NodeInvocation(alias="effect", node_id=node.spec.metadata.component_id)],
    )
    state = ExperimentState(run_id=run.run_manifest.run_id, params={"backend": "local"})
    return workflow, state, ctx, registry, database, cas


@pytest.mark.parametrize(
    "error", [RuntimeError("lost response after effect"), OSError("lost transport acknowledgment")]
)
def test_persisted_primary_effect_lost_response_is_unknown_without_real_local_replay(
    tmp_path: Path,
    error: BaseException,
) -> None:
    workflow, state, ctx, registry, database, cas = _handover_inputs(tmp_path)
    primary = _FixturePrimary(execution_error=error)
    assert isinstance(primary, WorkflowRunnerBackend)
    runner = FallbackWorkflowRunner(primary, health_ttl_s=0)
    with pytest.raises(PrimaryExecutionOutcomeUnknownError) as caught:
        asyncio.run(runner.execute_workflow(workflow, state, ctx, registry))
    assert caught.value.__cause__ is error
    rows = _effects(database)
    assert len(rows) == 1 and rows[0][:2] == ("fixture-operation-1", "primary")
    ref = ArtifactRef.model_validate_json(rows[0][2])
    assert json.loads(cas.get_bytes(ref)) == {
        "operation_id": "fixture-operation-1",
        "backend": "primary",
    }


@pytest.mark.parametrize(
    ("health", "expected"),
    [("healthy", "primary"), ("unhealthy", "local"), ("connection", "local")],
)
def test_typed_predispatch_permission_runs_one_actual_registered_producer(
    tmp_path: Path,
    health: str,
    expected: str,
) -> None:
    workflow, state, ctx, registry, database, _cas = _handover_inputs(tmp_path)
    runner = FallbackWorkflowRunner(
        _FixturePrimary(health=health),
        health_ttl_s=0,
        health_failure_classifier=lambda _health: HealthFailureDisposition.ALLOW,
    )
    result = asyncio.run(runner.execute_workflow(workflow, state, ctx, registry))
    assert isinstance(result, WorkflowExecutionResult) and result.report.status == "ok"
    rows = _effects(database)
    assert len(rows) == 1 and rows[0][1] == expected


@pytest.mark.parametrize("health", ["permission", "message_only"])
def test_access_failure_or_network_message_cannot_authorize_real_local_producer(
    tmp_path: Path,
    health: str,
) -> None:
    workflow, state, ctx, registry, database, _cas = _handover_inputs(tmp_path)
    runner = FallbackWorkflowRunner(
        _FixturePrimary(health=health),
        health_ttl_s=0,
        health_failure_classifier=lambda _health: HealthFailureDisposition.ALLOW,
    )
    with pytest.raises(FallbackNotAuthorizedError):
        asyncio.run(runner.execute_workflow(workflow, state, ctx, registry))
    assert _effects(database) == []


class _PrimaryCheckpointHook(CASCheckpointHook):
    def __init__(self, *, lose_after_first: bool, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.lose_after_first = lose_after_first

    async def on_tier_complete_async(self, **kwargs: Any) -> Any:
        result = await super().on_tier_complete_async(**kwargs)
        if self.lose_after_first and kwargs["completed_nodes"] == ["effect"]:
            raise _LostCheckpointReply("actual first-tier checkpoint published; reply lost")
        return result


class _CheckpointPrimary:
    """A real in-process primary runner with a controlled lost response boundary."""

    def __init__(self, hook: CASCheckpointHook, middleware: BudgetMiddleware | None = None) -> None:
        self.hook = hook
        self.middleware = middleware
        self.calls = 0

    async def health_check(self) -> RunnerHealth:
        return RunnerHealth(backend="fixture-checkpoint-primary", healthy=True)

    async def execute_workflow(
        self,
        workflow: WorkflowSpec,
        state: ExperimentState,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        **_kwargs: Any,
    ) -> WorkflowExecutionResult:
        self.calls += 1
        executor = AsyncWorkflowExecutor(
            ctx,
            registry,
            checkpoint_hook=self.hook,
            max_parallelism=1,
            workflow_timeout_s=30,
            budget_middleware=self.middleware,
            strict_budget_attempts=self.middleware is not None,
            capture_workflow_execution_admission=True,
        )
        try:
            result = await executor.execute(workflow, state)
        except _LostCheckpointReply as error:
            raise OSError("controlled reply loss after native primary work") from error
        raise AssertionError(
            "fixture did not reach reply-loss boundary: " + result.report.model_dump_json()
        )


@pytest.mark.parametrize(
    "continuation",
    [
        "remaining",
        "ambiguous",
        "expired",
        "exhausted",
        "stale_ledger",
        "missing_ledger",
        "tampered_state",
        "known_retry",
        "completed",
        "missing_receipt",
        "changed_receipt",
        "copied_ledger",
    ],
)
def test_actual_checkpoint_handover_preserves_operation_budget_and_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, continuation: str
) -> None:
    """Strict current-owner continuation consumes native completed work once."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    job_id, run_id = "dur02-checkpoint-job", "dur02-checkpoint-operation"
    known_retry = continuation == "known_retry"
    completed = continuation == "completed"
    budget_path = tmp_path / "budget.json"
    limit = Decimal(7) if continuation == "exhausted" else Decimal(10)
    ledger = FileBudgetLedger(budget_path)
    middleware = BudgetMiddleware(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=limit)}, spent={"run": Decimal(5)}
        ),
        ledger=ledger,
        invocation_settlement_profile="single_owner_local_v1",
    )
    initial_ledger_bytes = budget_path.read_bytes()
    original_budget_identity = middleware.settlement_owner_identity
    database = tmp_path / "effects.sqlite3"
    effect = (
        _CostedRetryEffectNode(database, mode="retry")
        if known_retry
        else _CheckpointedEffectNode(database, operation_id=run_id)
    )
    remaining = _RemainingEffectNode(
        database, expected_spend=Decimal(8) if known_retry else Decimal(7)
    )
    registry = NodeRegistry()
    registry.register(effect)
    registry.register(remaining)
    workflow = WorkflowSpec(
        workflow_id="dur02_reconciled_handover",
        nodes=[
            NodeInvocation(
                alias="effect",
                node_id=effect.spec.metadata.component_id,
                retry=(
                    RetryPolicy(max_retries=1, jitter="none", backoff_base_s=0.1)
                    if known_retry
                    else None
                ),
            ),
        ]
        + (
            []
            if completed
            else [
                NodeInvocation(
                    alias="remaining",
                    node_id=remaining.spec.metadata.component_id,
                    depends_on=["effect"],
                ),
            ]
        ),
    )
    control_database = tmp_path / "control.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=control_database)
    admin = ControlPlaneStore(backend="sqlite", sqlite_path=control_database)
    store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="dur02-native-fixture",
    )
    cas_root, run_dir = tmp_path / "cas", tmp_path / "run"
    cas = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
    access_scope = AccessScope.for_service(
        tenant_id="dur02-tenant",
        cell_id="dur02-cell",
        spiffe_id="spiffe://polisyos-test/dur02-native-handover",
    )

    @contextmanager
    def operation_scope() -> Iterator[None]:
        token = set_current_access_scope(access_scope)
        try:
            with tenant_scope(None, tenant_id="dur02-tenant", cell_id="dur02-cell"):
                yield
        finally:
            reset_current_access_scope(token)

    with operation_scope():
        bundle = build_default_registry_bundle(cas, return_selected_profile=True)
        run = RunContext.start(
            store=cas,
            registry_bundle=bundle.bundle_ref,
            run_id=run_id,
            run_dir=run_dir,
            tenant_id="dur02-tenant",
            cell_id="dur02-cell",
            access_scope=access_scope,
        )
        run.update_manifest(control_job_id=job_id, execution_profile="dev")
    ctx = ExecutionContext(store=cas, run=run, logger=logging.getLogger("dur02-handover"))
    state = ExperimentState(
        run_id=run_id,
        control_job_id=job_id,
        params={"backend": "primary", "lose_remaining_reply": continuation == "ambiguous"},
        budgets={"run_spent_usd": Decimal(5), "run_max_usd": limit},
    )
    with operation_scope():
        hook = _PrimaryCheckpointHook(
            store=cas,
            run_dir=run_dir,
            lose_after_first=continuation != "ambiguous",
        )
    primary = _CheckpointPrimary(hook, middleware)
    fallback = FallbackWorkflowRunner(primary, health_ttl_s=0)
    observed: dict[str, Any] = {}

    def primary_handler(job: Any) -> None:
        with operation_scope():
            with pytest.raises(PrimaryExecutionOutcomeUnknownError):
                asyncio.run(fallback.execute_workflow(workflow, state, ctx, registry))
            head = load_checkpoint_head(run_dir)
            assert head is not None
            checkpoint = load_checkpoint(cas, head.checkpoint_ref)
            assert checkpoint.metadata.completed_nodes == ["effect"]
            assert checkpoint.metadata.execution_budget_contract == "admitted_workflow_budget_v1"
            observed["deadline"] = checkpoint.metadata.execution_deadline_at
            assert observed["deadline"] is not None
            observed["effect_ref"] = checkpoint.state["params"]["effect_ref"]
            observed["checkpoint"] = checkpoint
            observed["head"] = head
            assert Decimal(checkpoint.state["budgets"]["run_spent_usd"]) == (
                Decimal(8) if known_retry else Decimal(7)
            )
            assert "failed_body" not in checkpoint.state["params"]
            receipt = _confirmed_effect_receipt(cas, run_dir, run_id)
            assert receipt is not None
            assert receipt.amount == (Decimal(1) if known_retry else Decimal(2))
            assert middleware.resolve_spend_safe(receipt.event_id) == receipt
            observed["receipt"] = receipt
            effect_attempts = [
                item
                for item in read_runtime_invocation_attempts(
                    cas, run_dir / "trace.jsonl", run_id=run_id
                )
                if item.basis.node_alias == "effect"
            ]
            receipts = []
            for item in effect_attempts:
                assert item.outcome is not None and item.outcome.budget_receipt_ref is not None
                receipts.append(
                    BudgetLedgerSpendReceipt.model_validate(
                        read_core_json_artifact(cas, item.outcome.budget_receipt_ref).value
                    )
                )
            assert [item.amount for item in receipts] == (
                [Decimal(2), Decimal(1)] if known_retry else [Decimal(2)]
            )
            observed["all_receipts"] = receipts
            assert middleware.settlement_owner_identity == original_budget_identity
        with sqlite3.connect(control_database) as connection:
            connection.execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job.job_id),
            )
        replacement = admin.lease_next_job(worker_id="worker-B", lease_seconds=300)
        assert replacement is not None and replacement.attempt == 2
        observed["replacement"] = replacement
        with pytest.raises(ControlJobLeaseLostError):
            store.complete_job(job_id=job.job_id, progress={"stale": True})

    worker_a = ControlWorker(
        store=store, handler=primary_handler, worker_id="worker-A", lease_seconds=300
    )
    assert worker_a.dispatch_once()
    assert primary.calls == 1

    def assert_primary_effect_count() -> None:
        if known_retry:
            with sqlite3.connect(database) as connection:
                rows = connection.execute(
                    "SELECT attempt_number FROM costed_effects ORDER BY rowid"
                ).fetchall()
            assert rows == [(1,), (2,)]
        else:
            assert len(_effects(database)) == 1

    assert_primary_effect_count()
    copied_budget_path = tmp_path / "copied-ledger" / "budget.json"
    if continuation == "stale_ledger":
        # Model an authentic earlier same-owner restore, not malformed bytes.
        budget_path.write_bytes(initial_ledger_bytes)
    if continuation in {"missing_receipt", "changed_receipt"}:
        current_snapshot = json.loads(budget_path.read_text())
        event_id = observed["receipt"].event_id
        assert event_id in current_snapshot["spend_receipts"]
        if continuation == "missing_receipt":
            del current_snapshot["spend_receipts"][event_id]
        else:
            original_digest = current_snapshot["spend_receipts"][event_id]["payload_digest"]
            replacement_digest = "0" * 64 if original_digest != "0" * 64 else "1" * 64
            current_snapshot["spend_receipts"][event_id]["payload_digest"] = replacement_digest
        budget_path.write_text(json.dumps(current_snapshot))
    if continuation == "copied_ledger":
        # Identical owner, receipt, revision and bytes are not the original
        # physical local resource and stable lock configured by A.
        copied_budget_path.parent.mkdir()
        copied_budget_path.write_bytes(budget_path.read_bytes())
    if continuation == "tampered_state":
        # A valid new selected checkpoint and history retain the owner/budget
        # bindings but change a field the real producer never wrote. Keep the
        # original sequence/prior pointer so a pointer rejection cannot mask
        # the independent full-state reconciliation oracle.
        original = observed["checkpoint"]
        tampered = copy.deepcopy(original.state)
        tampered["params"]["lose_remaining_reply"] = True
        metadata = original.metadata
        with operation_scope():
            replacement = create_checkpoint(
                cas,
                run_id=run_id,
                state=tampered,
                sequence_number=observed["head"].sequence_number,
                completed_node_alias=metadata.completed_node_alias,
                completed_node_id=metadata.completed_node_id,
                completed_nodes=metadata.completed_nodes,
                completed_node_status_contract=metadata.completed_node_status_contract,
                workflow_id=metadata.workflow_id,
                workflow_fingerprint=metadata.workflow_fingerprint,
                origin_workflow_fingerprint=metadata.origin_workflow_fingerprint,
                fsm_phase=metadata.fsm_phase,
                cache_entry_refs=metadata.cache_entry_refs,
                tenant_id=metadata.tenant_id,
                cell_id=metadata.cell_id,
                execution_budget_contract=metadata.execution_budget_contract,
                execution_deadline_at=metadata.execution_deadline_at,
            )
            update_checkpoint_head(
                run_dir,
                run_id=run_id,
                checkpoint_ref=replacement.checkpoint_ref,
                sequence_number=observed["head"].sequence_number,
                node_alias=metadata.completed_node_alias,
                writer_pid=os.getpid(),
                writer_hostname=socket.gethostname(),
            )
            history = load_checkpoint_history(run_dir)
            assert history is not None
            selected_entries = [
                entry
                for entry in history.entries
                if entry.checkpoint_ref == replacement.checkpoint_ref
            ]
            assert len(selected_entries) == 1
            # Replace this fixture's selected generation coherently. Keeping
            # both same-sequence heads would test history conflict instead.
            write_checkpoint_history(run_dir, CheckpointHistory(entries=selected_entries))
    if continuation == "expired":
        delay = (observed["deadline"] - datetime.now(UTC)).total_seconds()
        if delay > 0:
            time.sleep(delay + 0.02)

    def resume_handler(job: Any) -> None:
        current = admin.current_execution_job_record()
        assert current.job_id == job_id and current.run_id == run_id and current.attempt == 2
        fresh = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
        fresh_registry = NodeRegistry()
        fresh_registry.register(
            _CostedRetryEffectNode(database, mode="retry")
            if known_retry
            else _CheckpointedEffectNode(database, operation_id=run_id)
        )
        fresh_registry.register(
            _RemainingEffectNode(database, expected_spend=Decimal(8) if known_retry else Decimal(7))
        )
        with operation_scope():
            continuation_ledger = (
                None
                if continuation == "missing_ledger"
                else FileBudgetLedger(
                    copied_budget_path if continuation == "copied_ledger" else budget_path
                )
            )
            if continuation not in {"remaining", "exhausted", "known_retry", "completed"}:
                rejection = CheckpointError if continuation == "ambiguous" else WorkflowTimeoutError
                if continuation in {
                    "stale_ledger",
                    "missing_ledger",
                    "tampered_state",
                    "missing_receipt",
                    "changed_receipt",
                    "copied_ledger",
                }:
                    rejection = CheckpointError
                pattern = (
                    "checkpoint_attempt_state_not_reconciled"
                    if continuation == "tampered_state"
                    else None
                )
                with pytest.raises(rejection, match=pattern):
                    resume_from_checkpoint(
                        fresh,
                        run_id,
                        workflow=workflow,
                        registry=fresh_registry,
                        registry_bundle_ref=bundle.bundle_ref,
                        run_dir=run_dir,
                        require_reconciled_attempts=True,
                        expected_control_job_id=job_id,
                        continuation_ledger=continuation_ledger,
                    )
                return
            result = resume_from_checkpoint(
                fresh,
                run_id,
                workflow=workflow,
                registry=fresh_registry,
                registry_bundle_ref=bundle.bundle_ref,
                run_dir=run_dir,
                require_reconciled_attempts=True,
                expected_control_job_id=job_id,
                continuation_ledger=continuation_ledger,
            )
            if continuation == "exhausted":
                assert result.report.status == "fail"
                assert any(
                    node.error is not None and node.error.code == "node.budget_exhausted"
                    for node in result.report.nodes
                )
                return
            assert result.report.status == "ok"
            assert result.state.budgets["run_spent_usd"] == (
                Decimal(9) if known_retry else Decimal(7) if completed else Decimal(8)
            )
            assert "failed_body" not in result.state.params
            assert result.state.params["effect_ref"] == observed["effect_ref"]
            head = load_checkpoint_head(run_dir)
            assert head is not None
            if completed:
                assert head.checkpoint_ref == observed["head"].checkpoint_ref
            checkpoint = load_checkpoint(fresh, head.checkpoint_ref)
            assert checkpoint.metadata.completed_nodes == (
                ["effect"] if completed else ["effect", "remaining"]
            )
            assert checkpoint.metadata.execution_deadline_at == observed["deadline"]
            assert json.loads(
                fresh.get_bytes(ArtifactRef.model_validate(observed["effect_ref"]))
            ) == {
                "operation_id": run_id,
                "backend": "primary",
            }
        admin.complete_job(job_id=job.job_id, progress={"phase": "reconciled-completed"})

    worker_b = ControlWorker(
        store=admin, handler=resume_handler, worker_id="worker-B", lease_seconds=300
    )
    worker_b._run_with_lease_heartbeat(observed["replacement"])
    assert_primary_effect_count()
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT operation_id, ref FROM remaining_effects").fetchall()
    assert len(rows) == (1 if continuation in {"remaining", "ambiguous", "known_retry"} else 0)
    if rows:
        assert rows[0][0] == run_id
    if continuation not in {"stale_ledger", "missing_receipt", "changed_receipt"}:
        reopened = FileBudgetLedger(budget_path)
        expected_spend = (
            Decimal(9)
            if known_retry
            else Decimal(8)
            if continuation in {"remaining", "ambiguous"}
            else Decimal(7)
        )
        assert reopened.load().spent["run"] == expected_spend
        assert reopened.resolve_spend(observed["receipt"].event_id) == observed["receipt"]
        for receipt in observed["all_receipts"]:
            assert reopened.resolve_spend(receipt.event_id) == receipt
        assert reopened.settlement_owner_identity == original_budget_identity
    final_job = admin.get_job(job_id)
    assert final_job is not None and final_job.attempt == 2
    assert final_job.state == (
        "completed" if continuation in {"remaining", "known_retry", "completed"} else "running"
    )


@pytest.mark.parametrize("mode", ["retry", "lost_ack", "unknown", "exhausted_retry"])
def test_actual_async_attempt_settlement_preserves_cost_and_unknown_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Real retry execution owns distinct costs; same-attempt ACK recovery is not a new effect."""
    cas = FileSystemCAS(tmp_path / "cas")
    run_id, run_dir = f"dur02-costed-{mode}", tmp_path / "run"
    bundle = build_default_registry_bundle(cas, return_selected_profile=True)
    run = RunContext.start(
        store=cas, registry_bundle=bundle.bundle_ref, run_id=run_id, run_dir=run_dir
    )
    ctx = ExecutionContext(store=cas, run=run, logger=logging.getLogger("dur02-costed"))
    budget_path = tmp_path / "budget.json"
    middleware = BudgetMiddleware(
        BudgetState(
            limits={
                "run": BudgetLimit(
                    key="run", max_usd=Decimal(7) if mode == "exhausted_retry" else Decimal(10)
                )
            },
            spent={"run": Decimal(5)},
        ),
        ledger=FileBudgetLedger(budget_path),
        invocation_settlement_profile="single_owner_local_v1",
    )
    database = tmp_path / "effects.sqlite3"
    node = _CostedRetryEffectNode(database, mode="retry" if mode == "exhausted_retry" else mode)
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="dur02_costed_retry",
        nodes=[
            NodeInvocation(
                alias="costed",
                node_id=node.spec.metadata.component_id,
                retry=RetryPolicy(
                    max_retries=1,
                    jitter="none",
                    backoff_base_s=0.1,
                    retry_on=["node.exception", "node.budget_settlement_outcome_unknown"],
                ),
            )
        ],
    )
    lost_receipt_acks = []
    if mode in {"lost_ack", "unknown"}:
        put_json = cas.put_json

        def commit_then_lose_receipt_ack(
            obj: object,
            opts: ArtifactWriteOptions,
            canon_spec: CanonSpec | None = None,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            ref = put_json(
                obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
            )
            if opts.kind == "scientist.budget_spend_receipt" and (
                mode == "unknown" or not lost_receipt_acks
            ):
                lost_receipt_acks.append(ref)
                raise OSError("actual selected receipt committed; response lost")
            return ref

        monkeypatch.setattr(cas, "put_json", commit_then_lose_receipt_ack)
    result = asyncio.run(
        AsyncWorkflowExecutor(
            ctx,
            registry,
            max_parallelism=1,
            budget_middleware=middleware,
            strict_budget_attempts=True,
        ).execute(
            workflow,
            ExperimentState(run_id=run_id, budgets={"run_spent_usd": Decimal(5)}),
        )
    )
    with sqlite3.connect(database) as connection:
        calls = connection.execute(
            "SELECT run_id, attempt_number FROM costed_effects ORDER BY rowid"
        ).fetchall()
    expected_attempts = 2 if mode == "retry" else 1
    assert calls == [(run_id, number) for number in range(1, expected_attempts + 1)]
    history = read_runtime_invocation_attempts(cas, run_dir / "trace.jsonl", run_id=run_id)
    snapshot = FileBudgetLedger(budget_path).snapshot()
    assert snapshot.state.spent["run"] == (Decimal(8) if mode == "retry" else Decimal(7))
    assert len(snapshot.spend_receipts) == expected_attempts
    assert "failed_body" not in result.state.params
    if mode == "exhausted_retry":
        assert history and history[0].outcome is not None
        assert history[0].outcome.budget_receipt_ref is not None
        assert result.report.status == "fail"
        assert result.report.nodes[0].error is not None
        assert result.report.nodes[0].error.code == "node.budget_exhausted"
        assert result.state.budgets["run_spent_usd"] == Decimal(7)
        return
    assert len(history) == expected_attempts
    if mode == "unknown":
        assert result.report.status == "fail"
        assert result.report.nodes[0].error is not None
        assert result.report.nodes[0].error.code == "node.budget_settlement_outcome_unknown"
        assert lost_receipt_acks
        return
    assert result.report.status == "ok"
    assert result.state.budgets["run_spent_usd"] == snapshot.state.spent["run"]
    if mode == "lost_ack":
        assert len(lost_receipt_acks) == 1
    receipts = []
    statuses = []
    for attempt in history:
        assert attempt.outcome is not None
        statuses.append(attempt.outcome.status)
        ref = attempt.outcome.budget_receipt_ref
        assert ref is not None and ref.manifest_profile_sha256 is not None
        receipt = BudgetLedgerSpendReceipt.model_validate(read_core_json_artifact(cas, ref).value)
        assert snapshot.spend_receipts[receipt.event_id] == receipt
        assert attempt.basis.budget_start_revision is not None
        assert receipt.revision > attempt.basis.budget_start_revision
        receipts.append(receipt)
    assert [item.amount for item in receipts] == (
        [Decimal(2), Decimal(1)] if mode == "retry" else [Decimal(2)]
    )
    assert len({item.event_id for item in receipts}) == expected_attempts
    if mode == "retry":
        assert [item.basis.budget_start_revision for item in history] == [0, 1]
        assert statuses == ["fail", "ok"]


@pytest.mark.parametrize("residual_mode", ["unchanged", "changed_definition", "missing_handoff"])
def test_actual_unbudgeted_checkpoint_handover_reconciles_fresh_residual_definition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, residual_mode: str
) -> None:
    """A no-ledger owner remains no-ledger; a changed B definition never executes."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    changed_residual = residual_mode == "changed_definition"
    missing_handoff = residual_mode == "missing_handoff"
    job_id, run_id = "dur02-unbudgeted-job", "dur02-unbudgeted-operation"
    control_path = tmp_path / "control.sqlite3"
    control = ControlPlaneStore(backend="sqlite", sqlite_path=control_path)
    admin = ControlPlaneStore(backend="sqlite", sqlite_path=control_path)
    control.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="dur02-native-fixture",
    )
    cas_root, run_dir = tmp_path / "cas", tmp_path / "run"
    cas = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
    scope = AccessScope.for_service(
        tenant_id="dur02-tenant",
        cell_id="dur02-cell",
        spiffe_id="spiffe://polisyos-test/dur02-unbudgeted-handover",
    )

    @contextmanager
    def operation_scope() -> Iterator[None]:
        token = set_current_access_scope(scope)
        try:
            with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
                yield
        finally:
            reset_current_access_scope(token)

    database, wrong_database = tmp_path / "effects.sqlite3", tmp_path / "wrong-effects.sqlite3"
    effect = _UnbudgetedEffectNode(database, operation_id=run_id, invalid_handoff=missing_handoff)
    remaining = _UnbudgetedRemainingEffectNode(database)
    registry = NodeRegistry()
    registry.register(effect)
    registry.register(remaining)
    workflow = WorkflowSpec(
        workflow_id="dur02_unbudgeted_handover",
        nodes=[
            NodeInvocation(alias="effect", node_id=effect.spec.metadata.component_id),
            NodeInvocation(
                alias="remaining",
                node_id=remaining.spec.metadata.component_id,
                depends_on=["effect"],
            ),
        ],
    )
    with operation_scope():
        bundle = build_default_registry_bundle(cas, return_selected_profile=True)
        run = RunContext.start(
            store=cas,
            registry_bundle=bundle.bundle_ref,
            run_id=run_id,
            run_dir=run_dir,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            access_scope=scope,
        )
        run.update_manifest(control_job_id=job_id, execution_profile="dev")
        ctx = ExecutionContext(store=cas, run=run, logger=logging.getLogger("dur02-unbudgeted"))
        hook = _PrimaryCheckpointHook(store=cas, run_dir=run_dir, lose_after_first=True)
    runner = FallbackWorkflowRunner(_CheckpointPrimary(hook), health_ttl_s=0)
    original = {}

    def primary_handler(job) -> None:
        with operation_scope():
            with pytest.raises(PrimaryExecutionOutcomeUnknownError):
                asyncio.run(
                    runner.execute_workflow(
                        workflow,
                        ExperimentState(run_id=run_id, params={"backend": "primary"}),
                        ctx,
                        registry,
                    )
                )
            original["head"] = load_checkpoint_head(run_dir)
            assert original["head"] is not None
            checkpoint = load_checkpoint(cas, original["head"].checkpoint_ref)
            assert checkpoint.metadata.completed_nodes == ["effect"]
            assert checkpoint.metadata.execution_budget_contract == "admitted_workflow_budget_v1"
            original["deadline"] = checkpoint.metadata.execution_deadline_at
            assert original["deadline"] is not None
            history = read_runtime_invocation_attempts(cas, run_dir / "trace.jsonl", run_id=run_id)
            assert history[0].basis.budget_middleware_active is False
            assert history[0].basis.budget_owner_identity is None
            if missing_handoff:
                missing = ArtifactRef.model_validate(
                    checkpoint.state["artifacts_index"]["effect_ref"]
                )
                with pytest.raises(ArtifactOwnershipError, match="payload is not readable"):
                    cas.verify(missing)
                assert history[0].outcome is not None
                assert all(cas.verify(ref).ok for ref in history[0].outcome.output_refs)
                assert all(
                    ref.artifact_id != missing.artifact_id for ref in history[0].outcome.output_refs
                )

    worker_a = ControlWorker(store=control, handler=primary_handler, worker_id="worker-A")
    assert worker_a.dispatch_once()
    with sqlite3.connect(control_path) as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job_id),
        )
    fresh_registry = NodeRegistry()
    fresh_registry.register(
        _UnbudgetedEffectNode(database, operation_id=run_id, invalid_handoff=missing_handoff)
    )
    fresh_registry.register(
        _UnbudgetedRemainingEffectNode(wrong_database if changed_residual else database)
    )
    observed = []

    def replacement_handler(job) -> None:
        with operation_scope():
            fresh_cas = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()

            def resume():
                return resume_from_checkpoint(
                    fresh_cas,
                    run_id,
                    workflow=workflow,
                    registry=fresh_registry,
                    registry_bundle_ref=bundle.bundle_ref,
                    run_dir=run_dir,
                    require_reconciled_attempts=True,
                    expected_control_job_id=job_id,
                )

            if changed_residual:
                with pytest.raises(
                    CheckpointError, match="checkpoint_residual_implementation_not_established"
                ):
                    resume()
                observed.append("changed-definition-refused")
                return
            if missing_handoff:
                with pytest.raises(CheckpointCorruptedError, match=r"artifacts_index\.effect_ref"):
                    resume()
                observed.append("missing-handoff-refused")
                return
            result = resume()
            assert result.report.status == "ok" and result.state.budgets == {}
            head = load_checkpoint_head(run_dir)
            assert head is not None
            checkpoint = load_checkpoint(fresh_cas, head.checkpoint_ref)
            assert checkpoint.metadata.completed_nodes == ["effect", "remaining"]
            assert checkpoint.metadata.execution_deadline_at == original["deadline"]
            observed.append("remaining-only")
        admin.complete_job(job_id=job.job_id, progress={"unbudgeted_reconciled": True})

    worker_b = ControlWorker(store=admin, handler=replacement_handler, worker_id="worker-B")
    assert worker_b.dispatch_once()
    expected = (
        "changed-definition-refused"
        if changed_residual
        else "missing-handoff-refused"
        if missing_handoff
        else "remaining-only"
    )
    assert observed == [expected]
    assert len(_effects(database)) == 1
    for path in (database, wrong_database) if changed_residual else (database,):
        with sqlite3.connect(path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM remaining_effects").fetchone()[0]
        assert count == (0 if changed_residual or missing_handoff else 1)
    current = admin.get_job(job_id)
    assert current is not None and current.attempt == 2
    assert current.state == ("running" if changed_residual or missing_handoff else "completed")
    with (
        pytest.raises(ControlJobLeaseLostError),
        control.job_execution_fence(job_id=job_id, worker_id="worker-A", attempt=1),
    ):
        control.complete_job(job_id=job_id)
    assert admin.get_job(job_id) == current
    assert not (tmp_path / "budget.json").exists()
