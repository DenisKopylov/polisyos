"""Current DUR-02 real worker generations and persisted-effect handover controls.

The backend collaborator is a concrete fixture implementation, not an external
service status or idempotency contract. Fallback/local execution and the
filesystem/SQLite effect path are real production consumers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.http.services.control as _control_facade  # noqa: F401
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult, WorkflowReport
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
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
    cas = FileSystemCAS(tmp_path / "cas")
    options = ArtifactWriteOptions(
        kind="fixture.dur02.effect", media_type="application/octet-stream"
    )
    original_ref = cas.put_bytes(b"current admitted evidence", options)
    stale_ref = cas.put_bytes(b"stale result retained only for diagnostics", options)
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
    assert cas.get_bytes(stale_ref) == b"stale result retained only for diagnostics"


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


@pytest.mark.parametrize(
    "operation",
    [
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
    ],
)
def test_actual_stale_bound_handler_cannot_publish_through_sibling_mutation_inlets(
    tmp_path: Path,
    operation: str,
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
        with pytest.raises(ControlJobLeaseLostError):
            operations[operation]()
        assert _database_rows(database) == before
        observed.append(operation)

    worker = ControlWorker(store=store, handler=handler, worker_id="worker-A", lease_seconds=300)
    assert worker.dispatch_once()
    assert observed == [operation]
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


class _PersistedEffectNode:
    """A real registered fixture producer with deliberately non-idempotent SQLite effects."""

    def __init__(self, database: Path) -> None:
        self.database = database
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_dur02_effect@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="DUR02 persisted fixture effect",
                description="Real SQLite/CAS effect",
                tags=["fixture"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.backend"],
            state_writes=["params.effect_ref"],
            produces=[],
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE effects (operation_id TEXT, backend TEXT, artifact_ref TEXT)"
            )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        backend = str(state.params["backend"])
        payload = {"operation_id": "fixture-operation-1", "backend": backend}
        ref = ctx.store.put_json(
            payload,
            ArtifactWriteOptions(kind="fixture.dur02.effect", media_type="application/json"),
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO effects VALUES (?, ?, ?)",
                (payload["operation_id"], backend, ref.model_dump_json()),
            )
        changed = state.model_copy(deep=True)
        changed.params["effect_ref"] = ref.model_dump(mode="json")
        return NodeOutcome(status="ok", state=changed, artifacts=[ref])


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


def _effects(path: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT operation_id, backend, artifact_ref FROM effects"
        ).fetchall()


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
