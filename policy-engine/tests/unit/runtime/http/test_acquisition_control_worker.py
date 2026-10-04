from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread, get_ident, local

import pytest

import polisyos.runtime.http.services.control.run_lifecycle as run_lifecycle_module
import polisyos.runtime.http.services.control_plane_store as control_plane_store_module
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionOwnerExecutionResult,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.runtime.quality.acquisition_movement import AcquisitionMovementService
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests._helpers.control_worker import dispatch_one_control_job
from tests.unit.runtime.http.test_control_service_di import _build_control_service

_R8_THREAD_LOCAL_FENCE_REMOVAL_ENV = "POLISYOS_R8_THREAD_LOCAL_FENCE_REMOVAL"
_THREAD_LOCAL_UNSET = object()


class _ThreadLocalFenceToken:
    def __init__(self, *, carrier: _ThreadLocalFenceCarrier, previous: object) -> None:
        self.carrier = carrier
        self.thread_id = get_ident()
        self.previous = previous
        self.used = False


class _ThreadLocalFenceCarrier:
    """Thread-affine ContextVar-shaped carrier used only by the removal probe."""

    def __init__(self) -> None:
        self._local = local()

    def get(self, default: object = _THREAD_LOCAL_UNSET) -> object:
        value = getattr(self._local, "value", _THREAD_LOCAL_UNSET)
        if value is _THREAD_LOCAL_UNSET:
            return None if default is _THREAD_LOCAL_UNSET else default
        return value

    def set(self, value: object) -> _ThreadLocalFenceToken:
        previous = getattr(self._local, "value", _THREAD_LOCAL_UNSET)
        token = _ThreadLocalFenceToken(carrier=self, previous=previous)
        self._local.value = value
        return token

    def reset(self, token: _ThreadLocalFenceToken) -> None:
        if token.carrier is not self or token.thread_id != get_ident() or token.used:
            raise ValueError("thread-local fence token cannot be reset in this context")
        token.used = True
        if token.previous is _THREAD_LOCAL_UNSET:
            del self._local.value
        else:
            self._local.value = token.previous


@pytest.fixture(autouse=True)
def _optional_r8_thread_local_fence_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove cross-thread fence propagation only under an explicit opt-in."""
    setting = os.environ.get(_R8_THREAD_LOCAL_FENCE_REMOVAL_ENV)
    if setting is None:
        return
    if setting != "1":
        pytest.fail(
            f"{_R8_THREAD_LOCAL_FENCE_REMOVAL_ENV} must be unset or exactly '1'",
            pytrace=False,
        )

    original_init = ControlPlaneStore.__init__

    def _thread_local_init(
        self: ControlPlaneStore,
        *,
        backend: str,
        sqlite_path: str | Path,
        postgres_dsn: str | None = None,
    ) -> None:
        original_init(
            self,
            backend=backend,
            sqlite_path=sqlite_path,
            postgres_dsn=postgres_dsn,
        )
        self._job_execution_fence = _ThreadLocalFenceCarrier()

    monkeypatch.setattr(ControlPlaneStore, "__init__", _thread_local_init)


@dataclass
class _Port:
    service: AcquisitionActionService
    closure: object
    calls: list[str]
    owner_ref: str
    disposition: str = "quarantined_no_growth"
    admitted_observation_delta: int = 0
    overlay_admission_receipt_ref: str | None = None
    post_epoch_event_ref: str | None = None
    reentry_ref: str | None = None

    def execute(self, closure):
        assert closure == self.closure
        seed = self.service._phase_receipt(
            closure=closure,
            job_id="job-acquisition",
            decision_ref="sha256:" + "9" * 64,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        head = self.service.control_service.acquisition_route_sink.get_head(seed)
        assert head is not None
        assert head.receipt_phase == "executing"
        self.calls.append("effect")
        return AcquisitionOwnerExecutionResult(
            disposition=self.disposition,
            owner_receipt_refs=(self.owner_ref,),
            admitted_observation_delta=self.admitted_observation_delta,
            overlay_admission_receipt_ref=self.overlay_admission_receipt_ref,
            post_epoch_event_ref=self.post_epoch_event_ref,
        )

    def reenter(self, closure, result):
        del closure, result
        if self.reentry_ref is None:
            raise AssertionError("re-entry must be explicitly configured")
        return self.reentry_ref

    def resume_reentry(self, closure, owner_receipt_refs):  # pragma: no cover
        del closure, owner_receipt_refs
        raise AssertionError("quarantine cannot recover re-entry")


class _Gateway:
    def __init__(self, *, calls: list[str], effect_handler, decision_missing: bool) -> None:
        self._calls = calls
        self._effect_handler = effect_handler
        self._decision_missing = decision_missing

    def load_persisted_decision(self, decision_ref: str):
        self._calls.append("load-decision")
        assert decision_ref == "sha256:" + "9" * 64
        if self._decision_missing:
            raise RuntimeError("durable decision missing")
        return object()

    def execute_bound_effect(self, *, operation, invocation, intent, persisted):
        del operation, intent, persisted
        self._calls.append("execute-bound-effect")
        return self._effect_handler(invocation)


class _Provider:
    def __init__(self, *, calls: list[str], decision_missing: bool) -> None:
        self._calls = calls
        self._decision_missing = decision_missing

    def for_job(self, *, effect_handler, **_kwargs):
        return _Gateway(
            calls=self._calls,
            effect_handler=effect_handler,
            decision_missing=self._decision_missing,
        )

    def for_request(self, **_kwargs):  # pragma: no cover - worker-only harness
        raise AssertionError("worker cannot recreate HTTP authority")


async def _worker_harness(
    tmp_path: Path,
    *,
    decision_missing: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_store = FileSystemCAS(tmp_path / ".polisyos").with_ambient_ownership_enforcement()
    control = _build_control_service(tmp_path, artifact_store=artifact_store)
    install_fixture_wdi_cost_basis(monkeypatch)
    fixture_closure, _source_request = await persist_wdi_route(
        control,
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-ds15",
        job_id="job-natural-language",
    )

    service = object.__new__(AcquisitionActionService)
    service.control_service = control
    service.human_decision_service = object()
    calls: list[str] = []
    service._authority_provider = _Provider(calls=calls, decision_missing=decision_missing)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        closure = service._resolve(
            tenant_id="tenant-a", cell_id="cell-a", run_id="run-ds15"
        )
        assert closure.source_job_id == fixture_closure.source_job_id
        assert closure.compiled_ref == fixture_closure.compiled_ref
        owner_ref = control._put_json_artifact(
            {"disposition": "quarantined_no_growth"},
            kind="runtime_quality.acquisition_owner_receipt",
            schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
        )
    service._execution_port = _Port(
        service=service,
        closure=closure,
        calls=calls,
        owner_ref=owner_ref,
    )
    control.bind_acquisition_job_handler(service.handle_job)
    projection = service._projection(closure)
    request = AcquisitionRouteMutationRequest(
        route_projection_hash=projection.route_projection_hash,
        planner_report_hash=projection.planner_report_hash,
        replay_pins=projection.replay_pins,
        idempotency_key="worker-order",
        human_decision_record_ref="sha256:" + "8" * 64,
    )
    operation, invocation, intent = service._action_tuple(closure, request)
    payload = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-ds15",
        "route_id": closure.route_id,
        "decision_ref": "sha256:" + "9" * 64,
        "request": request.model_dump(mode="json"),
        "operation": operation.model_dump(mode="json"),
        "invocation": invocation.model_dump(mode="json"),
        "intent": intent.model_dump(mode="json"),
    }
    # Queue and phase writers persist actual payload/manifest/receipt bytes.
    # Keep their complete write and readback sequence inside the caller's
    # tenant scope; the worker itself later installs the admitted job scope.
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        queued = control.enqueue_acquisition_job(
            job_id="job-acquisition",
            run_id="run-ds15",
            payload=payload,
            principal=RuntimePrincipal(
                subject="tester",
                tenant_id="tenant-a",
                cell_id="cell-a",
                authenticated=True,
                roles=frozenset({"analyst"}),
            ),
        )
        requested = service._phase_receipt(
            closure=closure,
            job_id="job-acquisition",
            decision_ref="sha256:" + "9" * 64,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        requested_head = control.acquisition_route_sink.persist_phase(requested)

        persisted_job = control._control_store.get_job("job-acquisition")
        assert persisted_job is not None
        assert persisted_job.payload_ref == queued.payload_ref
        assert persisted_job.capability_manifest_ref == queued.capability_manifest_ref
        assert queued.payload_ref is not None
        assert queued.capability_manifest_ref is not None
        owned_refs = (
            queued.payload_ref,
            queued.capability_manifest_ref,
            requested_head.receipt_ref,
        )
        expected_kinds = (
            "runtime.control_job_payload.acquisition",
            "runtime.capability_manifest",
            "runtime_quality.acquisition_route_phase_receipt",
        )
        for artifact_ref, expected_kind in zip(owned_refs, expected_kinds, strict=True):
            manifest = artifact_store.get_manifest(artifact_ref)
            assert manifest.kind == expected_kind
            assert artifact_store.get_bytes(artifact_ref)

        assert control.acquisition_route_sink.resolve_action_generation(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id=requested.run_id,
            source_job_id=requested.source_job_id,
            route_id=requested.route_id,
            job_id=requested.job_id,
        ) == requested.action_generation

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        for artifact_ref in owned_refs:
            with pytest.raises(ArtifactOwnershipError):
                artifact_store.get_bytes(artifact_ref)
    return control, service, calls, requested, artifact_store


@pytest.mark.asyncio
async def test_worker_missing_durable_decision_fails_before_owner_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, _service, calls, requested, _artifact_store = await _worker_harness(
        tmp_path,
        decision_missing=True,
        monkeypatch=monkeypatch,
    )
    try:
        job = control._control_store.get_job("job-acquisition")
        assert job is not None

        dispatch_one_control_job(
            store=control._control_store,  # noqa: SLF001
            handler=control._process_control_job,  # noqa: SLF001
            expected_job_id=job.job_id,
        )

        failed = control._control_store.get_job("job-acquisition")
        assert failed is not None
        assert failed.state == "failed"
        assert calls == ["load-decision"]
        head = control.acquisition_route_sink.get_head(requested)
        assert head is not None
        assert head.receipt_phase == "executing"
    finally:
        control.close()


@pytest.mark.asyncio
async def test_worker_loads_durable_decision_before_sealed_effect_and_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, _service, calls, requested, _artifact_store = await _worker_harness(
        tmp_path,
        decision_missing=False,
        monkeypatch=monkeypatch,
    )
    try:
        job = control._control_store.get_job("job-acquisition")
        assert job is not None

        store = control._control_store
        job = store.lease_next_job(worker_id="worker-current", lease_seconds=30)
        assert job is not None and job.job_id == "job-acquisition"
        worker = ControlWorker(
            store=store,
            handler=control._process_control_job,
            worker_id="worker-current",
            lease_seconds=30,
        )
        worker._heartbeat_interval_s = 60.0
        worker._run_with_lease_heartbeat(job)

        completed = store.get_job("job-acquisition")
        assert completed is not None
        assert completed.state == "completed"
        assert calls == ["load-decision", "execute-bound-effect", "effect"]
        head = control.acquisition_route_sink.get_head(requested)
        assert head is not None
        assert head.receipt_phase == "terminal"
        assert head.recovery_state == "complete"
    finally:
        control.close()

def _new_lease_fence_job(store, *, job_id: str = "job-lease-fence"):
    store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="run-lease-fence",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref="manifest-before",
        payload_ref=None,
        submitted_by="test",
    )


def _start_paused_worker(store, job, *, worker_id: str, write_after_resume):
    entered = Event()
    resume = Event()
    errors: list[BaseException] = []

    def _handler(_job) -> None:
        entered.set()
        if not resume.wait(timeout=5):
            raise TimeoutError("worker test barrier was not released")
        write_after_resume(_job)

    worker = ControlWorker(
        store=store,
        handler=_handler,
        worker_id=worker_id,
        lease_seconds=5,
    )
    # Keep the pulse asleep while the test transfers the expired lease to B.
    worker._heartbeat_interval_s = 60.0

    def _run() -> None:
        try:
            worker._run_with_lease_heartbeat(job)
        except BaseException as exc:  # surfaced in the test thread below
            errors.append(exc)

    thread = Thread(target=_run, name=f"test-{worker_id}")
    thread.start()
    assert entered.wait(timeout=3), "worker did not enter its fenced handler"
    return thread, resume, errors


def _wait_worker(thread: Thread, resume: Event) -> None:
    resume.set()
    thread.join(timeout=5)
    assert not thread.is_alive(), "worker thread did not finish"


@pytest.mark.parametrize(
    ("guarded", "mutation"),
    [
        (False, "complete"),
        (True, "complete"),
        (True, "manifest"),
    ],
    ids=["raw-store-completion", "guarded-store-completion", "guarded-store-manifest"],
)
def test_stale_worker_cannot_write_after_guarded_store_takeover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    guarded: bool,
    mutation: str,
) -> None:
    """A's worker context cannot commit a job write after B acquires attempt 2."""
    raw = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    store = guard_runtime_control_store(raw) if guarded else raw
    clock = [datetime.now(UTC).replace(microsecond=0)]
    monkeypatch.setattr(control_plane_store_module, "_utc_now", lambda: clock[0])
    _new_lease_fence_job(store)
    job = store.lease_next_job(worker_id="worker-a", lease_seconds=5)
    assert job is not None and job.attempt == 1

    def _write(_job) -> None:
        if mutation == "complete":
            store.complete_job(job_id=_job.job_id, progress={"state": "completed"})
        else:
            store.update_manifest_ref(
                job_id=_job.job_id,
                capability_manifest_ref="manifest-from-stale-worker",
            )

    thread, resume, errors = _start_paused_worker(
        store,
        job,
        worker_id="worker-a",
        write_after_resume=_write,
    )
    try:
        clock[0] += timedelta(seconds=6)
        replacement = store.lease_next_job(worker_id="worker-b", lease_seconds=20)
        assert replacement is not None
        assert replacement.attempt == 2
        assert replacement.lease_owner == "worker-b"
        _wait_worker(thread, resume)

        assert len(errors) == 1
        assert isinstance(errors[0], ControlJobLeaseLostError)
        current = raw.get_job(job.job_id)
        assert current is not None
        assert current.state == "running"
        assert current.lease_owner == "worker-b"
        assert current.attempt == 2
        if mutation == "manifest":
            assert current.capability_manifest_ref == "manifest-before"
    finally:
        _wait_worker(thread, resume)
        if guarded:
            store.close()
        raw.close()


def test_guarded_current_worker_can_update_manifest_and_complete(tmp_path: Path) -> None:
    """A bound current attempt may update its manifest and complete normally."""
    raw = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    store = guard_runtime_control_store(raw)
    try:
        _new_lease_fence_job(store)
        job = store.lease_next_job(worker_id="worker-current", lease_seconds=30)
        assert job is not None

        def _handler(current) -> None:
            store.update_manifest_ref(
                job_id=current.job_id,
                capability_manifest_ref="manifest-current-worker",
            )
            store.complete_job(
                job_id=current.job_id,
                progress={"state": "completed"},
            )

        worker = ControlWorker(
            store=store,
            handler=_handler,
            worker_id="worker-current",
            lease_seconds=30,
        )
        worker._heartbeat_interval_s = 60.0
        worker._run_with_lease_heartbeat(job)
        current = raw.get_job(job.job_id)
        assert current is not None
        assert current.state == "completed"
        assert current.capability_manifest_ref == "manifest-current-worker"
    finally:
        store.close()
        raw.close()


@pytest.mark.asyncio
async def test_stale_guarded_worker_terminal_evidence_does_not_advance_head_after_takeover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A visible stale terminal artifact/event is not current in the acquisition head."""
    control, service, calls, requested, _artifact_store = await _worker_harness(
        tmp_path,
        decision_missing=False,
        monkeypatch=monkeypatch,
    )
    service._execution_port.disposition = "world_committed"
    service._execution_port.admitted_observation_delta = 1
    service._execution_port.overlay_admission_receipt_ref = service._execution_port.owner_ref
    service._execution_port.post_epoch_event_ref = service._execution_port.owner_ref
    service._execution_port.reentry_ref = "sha256:" + "a" * 64

    clock = [datetime.now(UTC).replace(microsecond=0)]
    monkeypatch.setattr(control_plane_store_module, "_utc_now", lambda: clock[0])
    entered = Event()
    resume = Event()
    errors: list[BaseException] = []
    terminal_refs: list[str] = []
    original_writer = run_lifecycle_module.write_runtime_authority_artifact

    def _persist_terminal_then_pause(*args, **kwargs):
        result = original_writer(*args, **kwargs)
        if kwargs.get("event_type") == "polisyos.runtime.acquisition.route_loop.v1":
            terminal_refs.append(str(result.cas_ref.artifact_id))
            entered.set()
            assert resume.wait(timeout=5), "test did not release the terminal evidence barrier"
        return result

    monkeypatch.setattr(
        run_lifecycle_module,
        "write_runtime_authority_artifact",
        _persist_terminal_then_pause,
    )
    store = control._control_store
    job = store.lease_next_job(worker_id="worker-a", lease_seconds=5)
    assert job is not None and job.attempt == 1
    worker = ControlWorker(
        store=store,
        handler=control._process_control_job,
        worker_id="worker-a",
        lease_seconds=5,
    )
    worker._heartbeat_interval_s = 60.0

    def _run() -> None:
        try:
            worker._run_with_lease_heartbeat(job)
        except BaseException as exc:  # surfaced in the test thread below
            errors.append(exc)

    thread = Thread(target=_run, name="test-worker-a-acquisition")
    thread.start()
    try:
        assert entered.wait(timeout=5), (
            "terminal authority artifact/event did not reach the barrier"
        )
        pending = control.acquisition_route_sink.get_head(requested)
        assert pending is not None
        assert pending.receipt_phase == "world_committed_reentry_pending"
        assert len(terminal_refs) == 1

        # At this exact barrier the CAS artifact and authority event have been
        # durably written, while the action-head append has not yet run.
        event_rows = control._diagnostic_event_log.list_events(
            run_id="run-ds15",
            job_id="job-acquisition",
        )
        terminal_events = [
            row
            for row in event_rows
            if row.event.event_type == "polisyos.runtime.acquisition.route_loop.v1"
            and row.event.state_after == "terminal"
        ]
        assert len(terminal_events) == 1
        orphan_ref = terminal_events[0].event.payload_ref
        assert orphan_ref is not None and orphan_ref == terminal_refs[0]
        control._artifact_store.get_bytes(orphan_ref)

        clock[0] += timedelta(seconds=6)
        replacement = store.lease_next_job(worker_id="worker-b", lease_seconds=20)
        assert replacement is not None
        assert replacement.attempt == 2
        assert replacement.lease_owner == "worker-b"

        resume.set()
        thread.join(timeout=10)
        assert not thread.is_alive(), "stale acquisition worker did not finish"
        assert len(errors) == 1
        assert isinstance(errors[0], ControlJobLeaseLostError)
        current = store.get_job(job.job_id)
        assert current is not None
        assert (current.state, current.lease_owner, current.attempt) == (
            "running",
            "worker-b",
            2,
        )
        head = control.acquisition_route_sink.get_head(requested)
        assert head is not None
        assert head.receipt_phase == "world_committed_reentry_pending"
        assert head.receipt_ref == pending.receipt_ref
        assert head.receipt_ref != orphan_ref
        assert calls == ["load-decision", "execute-bound-effect", "effect"]

        movement = AcquisitionMovementService(
            control_store=store,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
        )
        movement.bind_completed_control_job_core_source_resolver(
            control.resolve_completed_control_job_core_run_source
        )
        projection = movement.consume_terminal(supplier_receipt_ref=orphan_ref)
        assert projection.status == "refused"
        assert projection.reason == "supplier_terminal_head_not_current"
        assert projection.movement_record is None
    finally:
        resume.set()
        thread.join(timeout=10)
        control.close()
