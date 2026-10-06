"""Real PostgreSQL stale worker generations and atomic terminal publication.

Each case retains a unique schema in the task-owned database. These controls
assert database effects; they do not claim exactly-once external side effects.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

import polisyos.runtime.http.services.control as _control_facade  # noqa: F401
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker

_WORKER_CHILD = r"""
import json, os, sys
from pathlib import Path
import polisyos.runtime.http.services.control
from polisyos.runtime.http.services import control_plane_store as sm, control_worker as wm
expected = Path(os.environ["E02_B38_EXPECTED_SOURCE"])
assert Path(sm.__file__).resolve().is_relative_to(expected)
assert Path(wm.__file__).resolve().is_relative_to(expected)
store = sm.ControlPlaneStore(backend="postgres", sqlite_path="unused.sqlite3",
                            postgres_dsn=os.environ["E02_B38_CHILD_DSN"])
job_id, action = sys.argv[1:]
if action == "takeover":
    job = store.lease_next_job(worker_id="worker-B", lease_seconds=300)
    assert job is not None and job.job_id == job_id and job.attempt == 2
else:
    def handler(job):
        admitted = store.current_execution_job_record()
        assert admitted.lease_owner == "worker-B" and admitted.attempt == 2
        store.update_progress_state(job_id=job.job_id, state="running",
                                    progress={"phase":"current-B"})
        store.complete_job(job_id=job.job_id, progress={"phase":"completed-B"})
    job = store.get_job(job_id)
    assert job.lease_owner == "worker-B" and job.attempt == 2
    worker = wm.ControlWorker(store=store, handler=handler, worker_id="worker-B",
                              lease_seconds=300)
    worker._run_with_lease_heartbeat(job)
    job = store.get_job(job_id)
print(json.dumps({"state":job.state,"attempt":job.attempt,"lease_owner":job.lease_owner,
                  "progress":job.progress}))
"""


@dataclass(frozen=True)
class _PostgresFixture:
    dsn: str
    schema: str
    store: ControlPlaneStore
    driver: Any

    def rows(self) -> dict[str, tuple[tuple[Any, ...], ...]]:
        """Read every native table through an independent PostgreSQL connection."""
        with self.driver.connect(self.dsn) as connection:
            tables = connection.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = %s "
                "ORDER BY tablename",
                (self.schema,),
            ).fetchall()
            result = {}
            for (table,) in tables:
                query = self.driver.sql.SQL("SELECT * FROM {}.{}").format(
                    self.driver.sql.Identifier(self.schema),
                    self.driver.sql.Identifier(table),
                )
                result[table] = tuple(
                    sorted(connection.execute(query).fetchall(), key=repr)
                )
            assert "control_jobs" in result and "control_job_events" in result
            return result


@pytest.fixture
def postgres_fixture(
    tmp_path: Path, record_property: Callable[[str, object], None]
) -> _PostgresFixture:
    dsn = os.environ.get("E02_B38_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Task-owned PostgreSQL DSN is not configured; no PostgreSQL proof")
    driver = pytest.importorskip("psycopg")
    from psycopg.conninfo import make_conninfo

    schema = "e02_b38_" + uuid4().hex
    with driver.connect(dsn, autocommit=True) as connection:
        connection.execute(
            driver.sql.SQL("CREATE SCHEMA {}").format(driver.sql.Identifier(schema))
        )
        identity = connection.execute(
            "SELECT version(), current_database(), inet_server_addr()::text, inet_server_port()"
        ).fetchone()
    scoped_dsn = make_conninfo(dsn, options="-csearch_path=" + schema)
    store = ControlPlaneStore(
        backend="postgres",
        sqlite_path=tmp_path / "unused.sqlite3",
        postgres_dsn=scoped_dsn,
    )
    fixture = _PostgresFixture(scoped_dsn, schema, store, driver)
    record_property("postgres_identity", json.dumps(identity))
    record_property("postgres_schema", schema)
    record_property("driver_version", driver.__version__)
    record_property("driver_origin", driver.__file__)
    record_property("table_denominator", json.dumps(sorted(fixture.rows())))
    return fixture


def _create_job(store: ControlPlaneStore, job_id: str) -> None:
    store.create_job(
        job_id=job_id,
        kind="workflow_run",
        run_id="e02-b38-postgres-run",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="e02-b38-postgres-native-fixture",
    )


def _current_child(
    fixture: _PostgresFixture, job_id: str, action: str
) -> dict[str, Any]:
    import polisyos.runtime.http.services.control_plane_store as store_module

    source = Path(store_module.__file__).resolve().parents[4]
    child = subprocess.run(
        [sys.executable, "-c", _WORKER_CHILD, job_id, action],
        env={
            **os.environ,
            "E02_B38_CHILD_DSN": fixture.dsn,
            "E02_B38_EXPECTED_SOURCE": str(source),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    return json.loads(child.stdout)


def _assert_terminal(fixture: _PostgresFixture, job_id: str, terminal: str) -> None:
    store = fixture.store
    record = store.get_job(job_id)
    assert record is not None
    assert record.state == terminal and record.attempt == 2
    assert record.lease_owner is None and record.lease_expires_at is None
    assert record.progress == {"phase": terminal + "-B"}
    event_type = "job_completed" if terminal == "completed" else "job_failed"
    with fixture.driver.connect(fixture.dsn) as connection:
        events = connection.execute(
            "SELECT payload_json FROM control_job_events WHERE job_id = %s AND event_type = %s",
            (job_id, event_type),
        ).fetchall()
    assert len(events) == 1
    payload = json.loads(events[0][0])
    assert payload["state"] == terminal
    assert payload["lease_owner"] == "worker-B" and payload["attempt"] == 2
    outbox = [
        event
        for event in store.list_outbox_events(state=None, limit=500)
        if event.event_key == job_id + ":" + event_type
    ]
    assert len(outbox) == 1
    assert outbox[0].payload["state"] == terminal
    assert outbox[0].payload["lease_owner"] == "worker-B"
    assert outbox[0].payload["attempt"] == 2
    assert outbox[0].payload["progress"] == record.progress
    dead_letters = store.list_dead_letter_jobs(acknowledged=None)
    assert [row.job_id for row in dead_letters] == (
        [job_id] if terminal == "failed" else []
    )


@pytest.mark.parametrize("current_state", ["running", "completed"])
def test_postgres_stale_bound_worker_cannot_mutate_any_table(
    postgres_fixture: _PostgresFixture,
    current_state: str,
    record_property: Callable[[str, object], None],
) -> None:
    fixture = postgres_fixture
    store = fixture.store
    job_id = "current-job"
    _create_job(store, job_id)
    observed = []

    def stale_handler(job: Any) -> None:
        assert store.current_execution_job_record().attempt == 1
        with fixture.driver.connect(fixture.dsn) as connection:
            connection.execute(
                "UPDATE control_jobs SET lease_expires_at = %s WHERE job_id = %s",
                (datetime.now(UTC) - timedelta(seconds=1), job.job_id),
            )
        takeover = _current_child(fixture, job.job_id, "takeover")
        assert takeover["attempt"] == 2 and takeover["lease_owner"] == "worker-B"
        if current_state == "completed":
            assert _current_child(fixture, job.job_id, "finish")["state"] == "completed"
        admin = ControlPlaneStore(
            backend="postgres", sqlite_path="unused.sqlite3", postgres_dsn=fixture.dsn
        )
        _create_job(admin, "pending-child")
        before = fixture.rows()
        instant = datetime.now(UTC)
        operations = {
            "complete": lambda: store.complete_job(
                job_id=job.job_id, progress={"stale": True}
            ),
            "fail": lambda: store.fail_job(job_id=job.job_id, error_message="stale"),
            "progress": lambda: store.update_progress_state(
                job_id=job.job_id, state="failed", progress={"stale": True}
            ),
            "manifest": lambda: store.update_manifest_ref(
                job_id=job.job_id, capability_manifest_ref="sha256:" + "a" * 64
            ),
            "current_record": store.current_execution_job_record,
            "upsert": lambda: store.upsert_progress(
                job_id=job.job_id, progress={"stale": True}
            ),
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
            "create": lambda: _create_job(store, "stale-created-child"),
            "mark_running": lambda: store.mark_running(
                job_id=job.job_id, worker_id="worker-A"
            ),
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
                assertion_id="stale-assertion",
                expires_at=int(instant.timestamp()) + 300,
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
            assert fixture.rows() == before, name
            observed.append(name)
        assert len(observed) == len(operations)

    worker = ControlWorker(
        store=store, handler=stale_handler, worker_id="worker-A", lease_seconds=300
    )
    worker._heartbeat_interval_s = (
        60  # Fixture renewal must not race the persisted expiry input.
    )
    assert worker.dispatch_once()
    if current_state == "running":
        assert _current_child(fixture, job_id, "finish")["state"] == "completed"
    _assert_terminal(fixture, job_id, "completed")
    record_property("stale_rejected_inlets", json.dumps(observed))
    record_property("unchanged_rows_after_each_rejection", True)


@pytest.mark.parametrize("terminal", ["completed", "failed"])
def test_postgres_current_worker_publishes_coherent_terminal_generation(
    postgres_fixture: _PostgresFixture, terminal: str
) -> None:
    fixture = postgres_fixture
    store = fixture.store
    _create_job(store, "current-job")
    first = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert first is not None
    with fixture.driver.connect(fixture.dsn) as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = %s WHERE job_id = %s",
            (datetime.now(UTC) - timedelta(seconds=1), first.job_id),
        )
    assert _current_child(fixture, first.job_id, "takeover")["attempt"] == 2

    def handler(job: Any) -> None:
        assert store.current_execution_job_record().attempt == 2
        store.update_progress_state(
            job_id=job.job_id, state="running", progress={"phase": "active"}
        )
        if terminal == "completed":
            store.complete_job(job_id=job.job_id, progress={"phase": "completed-B"})
            assert store.current_execution_completed_job_record().attempt == 2
        else:
            store.fail_job(
                job_id=job.job_id,
                error_message="fixture failure",
                progress={"phase": "failed-B"},
            )
        with pytest.raises(ControlJobLeaseLostError):
            store.append_event(
                job_id=job.job_id, event_type="after-terminal", payload={}
            )

    current = store.get_job(first.job_id)
    assert current is not None and current.lease_owner == "worker-B"
    worker = ControlWorker(
        store=store, handler=handler, worker_id="worker-B", lease_seconds=300
    )
    worker._run_with_lease_heartbeat(current)
    _assert_terminal(fixture, first.job_id, terminal)


@pytest.mark.parametrize("terminal", ["completed", "failed"])
@pytest.mark.parametrize("fault_boundary", ["event", "outbox"])
def test_postgres_real_statement_fault_rolls_back_all_terminal_rows(
    postgres_fixture: _PostgresFixture, terminal: str, fault_boundary: str
) -> None:
    fixture = postgres_fixture
    store = fixture.store
    _create_job(store, "fault-job")
    job = store.lease_next_job(worker_id="worker-A", lease_seconds=300)
    assert job is not None
    event_type = "job_completed" if terminal == "completed" else "job_failed"
    table = (
        "control_job_events" if fault_boundary == "event" else "control_outbox_events"
    )
    column = "event_type" if fault_boundary == "event" else "event_key"
    value = event_type if fault_boundary == "event" else "fault-job:" + event_type
    with fixture.driver.connect(fixture.dsn) as connection:
        connection.execute(
            "CREATE FUNCTION e02_b38_abort_publication() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'e02 B38 actual PostgreSQL publication fault'; END; $$"
        )
        connection.execute(
            fixture.driver.sql.SQL(
                "CREATE TRIGGER e02_b38_terminal_fault BEFORE INSERT ON {} "
                "FOR EACH ROW WHEN (NEW.{} = {}) EXECUTE FUNCTION e02_b38_abort_publication()"
            ).format(
                fixture.driver.sql.Identifier(table),
                fixture.driver.sql.Identifier(column),
                fixture.driver.sql.Literal(value),
            )
        )
    before = fixture.rows()
    with (
        store.job_execution_fence(
            job_id=job.job_id, worker_id="worker-A", attempt=job.attempt
        ),
        pytest.raises(
            fixture.driver.errors.RaiseException, match="actual PostgreSQL publication"
        ),
    ):
        if terminal == "completed":
            store.complete_job(job_id=job.job_id, progress={"phase": "must-rollback"})
        else:
            store.fail_job(
                job_id=job.job_id,
                error_message="must-rollback",
                progress={"phase": "must-rollback"},
            )
    assert fixture.rows() == before
    reopened = ControlPlaneStore(
        backend="postgres", sqlite_path="unused.sqlite3", postgres_dsn=fixture.dsn
    )
    record = reopened.get_job(job.job_id)
    assert record is not None and record.state == "running" and record.attempt == 1
    assert record.lease_owner == "worker-A" and record.finished_at is None
    assert terminal not in reopened.list_job_state_transitions(job.job_id)
