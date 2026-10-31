"""Actual guarded control-owner handoff for a private child computation."""

from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING

import pytest

import polisyos.common.async_tools as async_tools
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    GuardedDependencyProxy,
    build_runtime_control_store_guard,
    guard_runtime_control_store,
)
from polisyos.runtime.http.services.control.child_execution_budget import (
    ChildExecutionBudgetPolicy,
    _require_attempt_budget,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
from tests.unit.runtime.http.test_child_control_authorization import _job
from tests.unit.runtime.http.test_child_guarded_read_owner import _exercise_job

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from polisyos.common.borrowed_execution import _BorrowedExecutionGrant


@pytest.mark.parametrize(
    ("budgeted", "transition"),
    [(True, None), (False, None), (True, "cas"), (True, "control"), (True, "budget")],
)
def test_legacy_workflow_uses_the_actual_budgeted_parent_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budgeted: bool, transition: str | None
) -> None:
    """The real legacy route carries only a live worker-appointed parent owner."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.run import worker_lifecycle
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.scientist import api

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, kind="workflow_run")
    job = control.get_job("job-a")
    assert job is not None
    guarded_control = guard_runtime_control_store(control)
    guarded_cas = guard_runtime_cas(FileSystemCAS(tmp_path / "served", ownership_enforced=False))
    shared = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", shared)
    service = object.__new__(ControlPlaneService)
    service._artifact_store = guarded_cas
    service._control_store = guarded_control
    service._epoch_certificate_issuance_owner = None
    service._evaluation_safety_admission_verifier = None
    monkeypatch.setattr(service, "_legacy_scientist_final_state_ref", lambda **_: None)
    observed: list[tuple[object, bool, object]] = []

    def observe_actual_route(_state, *, store, foundry, **_kwargs):
        getter = getattr(worker_lifecycle, "_current_runtime_child_parent", lambda: None)
        owner = getter()
        if owner is not None:
            owner._require_current()
            assert not hasattr(owner, "grant")
            with (
                pytest.raises(ValueError, match="child_runtime_parent_scope_nested"),
                worker_lifecycle._runtime_child_parent_scope(owner),
            ):
                pytest.fail("a node replaced the Runtime parent")
            failures: list[BaseException] = []

            def use_from_foreign_thread():
                try:
                    owner._require_current()
                except BaseException as exc:
                    failures.append(exc)

            foreign = threading.Thread(target=use_from_foreign_thread)
            foreign.start()
            foreign.join(timeout=5)
            assert not foreign.is_alive()
            assert len(failures) == 1
            assert isinstance(failures[0], (RuntimeError, ValueError))
            with pytest.raises(AttributeError, match="scope is immutable"):
                foundry._delegate = object()
            if transition == "budget":
                event = control._child_event_row("job-a", f"child.budget.attempt.{attempt}")
                assert event is not None
                original = str(event["payload_json"])
                changed = json.loads(original)
                changed["duration_seconds"] += 1
                with control._job_transaction():
                    control._execute(
                        "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
                        (json.dumps(changed), event["event_id"]),
                    )
                try:
                    with pytest.raises(
                        ValueError, match="runtime_child_parent_budget_claim_changed"
                    ):
                        owner._require_current()
                finally:
                    with control._job_transaction():
                        control._execute(
                            "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
                            (original, event["event_id"]),
                        )
            elif transition is not None:
                from polisyos.runtime.http import resilience

                registry, proxy = (
                    (resilience._RUNTIME_FILESYSTEM_GUARDS, guarded_cas)
                    if transition == "cas"
                    else (resilience._RUNTIME_CONTROL_STORE_GUARDS, guarded_control)
                )
                original = registry.pop(proxy)
                registry[proxy] = original
                with pytest.raises(ValueError, match="guard_binding_changed"):
                    owner._require_current()
        observed.append((owner, async_tools.owns_shared_executor_slot(shared), foundry))
        assert store is guarded_cas
        return {"run_id": "run-a", "artifacts_index": {}}

    monkeypatch.setattr(api, "run_experiment", observe_actual_route)
    worker = ControlWorker(
        store=guarded_control,
        handler=lambda actual: service._run_legacy_scientist_workflow({}, job=actual),
        worker_id="worker-a",
        child_execution_budget_policy=(
            ChildExecutionBudgetPolicy("child-test", "1", 30) if budgeted else None
        ),
    )
    try:
        worker._run_with_lease_heartbeat(job)
        assert len(observed) == 1
        owner, on_shared_worker, foundry = observed[0]
        assert (owner is not None, on_shared_worker) == (budgeted, False)
        assert type(foundry).__name__ == "_RuntimeOriginCapturingFoundryPort"
        if budgeted:
            assert control.read_child_attempt_budget("job-a", attempt) is not None
            with pytest.raises((RuntimeError, ValueError)):
                owner._require_current()
        else:
            assert control.read_child_attempt_budget("job-a", attempt) is None
    finally:
        guarded_cas.close()
        guarded_control.close()
        shared.shutdown(wait=True)


def test_core_runtime_parent_scope_refuses_a_lookalike_owner() -> None:
    """A callable currentness marker cannot appoint the Runtime parent."""
    from polisyos.core.run.worker_lifecycle import _runtime_child_parent_scope

    class Lookalike:
        def _require_current(self):
            return None

    with (
        pytest.raises(ValueError, match="child_runtime_parent_origin_not_established"),
        _runtime_child_parent_scope(Lookalike()),
    ):
        pytest.fail("lookalike parent entered Core scope")


def test_control_test_dispatch_forwards_an_explicit_child_budget(tmp_path: Path) -> None:
    """The shared fixture can appoint the real worker's durable budget explicitly."""
    from tests._helpers.control_worker import dispatch_one_control_job

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    _job(control, kind="workflow_run")
    with control._job_transaction():
        control._execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", "job-a"),
        )
    guarded = guard_runtime_control_store(control)
    seen = []

    def handler(job):
        budget = _require_attempt_budget(job.job_id, "run-a", job.attempt)
        seen.append(budget.claim)

    try:
        selected = dispatch_one_control_job(
            store=guarded,
            handler=handler,
            expected_job_id="job-a",
            child_execution_budget_policy=ChildExecutionBudgetPolicy("fixture-compute", "1", 30),
        )
        assert selected == "job-a"
        assert len(seen) == 1
        claim = control.read_child_attempt_budget("job-a", seen[0].attempt)
        assert claim == seen[0]
        assert (claim.policy_id, claim.policy_version, claim.duration_seconds) == (
            "fixture-compute",
            "1",
            30,
        )
    finally:
        guarded.close()


@pytest.mark.parametrize("foreign", ["cas", "control"])
def test_legacy_child_parent_rejects_unregistered_guards_before_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: str
) -> None:
    """A matching proxy shape cannot substitute for a live Runtime registration."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.http.resilience import build_runtime_cas_guard, guard_runtime_cas
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control.workspace_loop_transition import (
        _LegacyScientistWorkflowError,
    )
    from polisyos.scientist import api

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    _job(control, kind="workflow_run")
    job = control.get_job("job-a")
    assert job is not None
    guarded_control = guard_runtime_control_store(control)
    guarded_cas = guard_runtime_cas(FileSystemCAS(tmp_path / "served", ownership_enforced=False))
    fake = GuardedDependencyProxy(
        target=object(),
        guard=(
            build_runtime_cas_guard() if foreign == "cas" else build_runtime_control_store_guard()
        ),
    )
    service = object.__new__(ControlPlaneService)
    service._artifact_store = fake if foreign == "cas" else guarded_cas
    service._control_store = fake if foreign == "control" else guarded_control
    service._epoch_certificate_issuance_owner = None
    service._evaluation_safety_admission_verifier = None
    monkeypatch.setattr(service, "_legacy_scientist_final_state_ref", lambda **_: None)
    calls: list[object] = []

    def produce(*args, **kwargs):
        calls.append(args)
        return {"run_id": "run-a", "artifacts_index": {}}

    monkeypatch.setattr(api, "run_experiment", produce)
    worker = ControlWorker(
        store=guarded_control,
        handler=lambda actual: service._run_legacy_scientist_workflow({}, job=actual),
        worker_id="worker-a",
        child_execution_budget_policy=ChildExecutionBudgetPolicy("child-test", "1", 30),
    )
    try:
        reason = (
            "registered_sql_guard_binding_not_established"
            if foreign == "cas"
            else "runtime_child_parent_not_established"
        )
        with pytest.raises(_LegacyScientistWorkflowError, match=reason):
            worker._run_with_lease_heartbeat(job)
        assert not calls
    finally:
        fake.close()
        guarded_cas.close()
        guarded_control.close()


def test_control_guard_registration_binds_actual_factory_and_executor(tmp_path: Path) -> None:
    """A lookalike proxy cannot establish the control executor's origin."""
    from polisyos.runtime.http.resilience import (
        _require_runtime_child_job_verifier,
        _require_runtime_control_store_guard,
    )

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    registered = guard_runtime_control_store(control)
    lookalike = GuardedDependencyProxy(target=control, guard=build_runtime_control_store_guard())
    try:
        binding = _require_runtime_control_store_guard(registered)
        assert binding.backend is control
        assert binding.guard is registered._guard
        assert binding.executor is registered._guard._executor
        verifier = _require_runtime_child_job_verifier(registered)
        assert verifier is binding.child_verifier
        assert _require_runtime_child_job_verifier(registered) is verifier
        with pytest.raises(ValueError, match="registered_control_guard_binding_not_established"):
            _require_runtime_control_store_guard(lookalike)
        with pytest.raises(ValueError, match="registered_control_guard_binding_not_established"):
            _require_runtime_child_job_verifier(lookalike)
    finally:
        lookalike.close()
        registered.close()


@pytest.mark.parametrize("probe", ["target", "guard", "closed", "registry"])
def test_control_guard_registration_does_not_revive_after_aba(tmp_path: Path, probe: str) -> None:
    """Restoring the original values does not revive one guard incarnation."""
    from polisyos.runtime.http import resilience

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    registered = guard_runtime_control_store(control)
    try:
        if probe == "target":
            registered._target = ControlPlaneStore(
                backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"
            )
            registered._target = control
        elif probe == "guard":
            original = registered._guard._timeout_seconds
            registered._guard._timeout_seconds = original + 1
            registered._guard._timeout_seconds = original
        elif probe == "closed":
            registered._guard._closed = True
            registered._guard._closed = False
        else:
            binding = resilience._RUNTIME_CONTROL_STORE_GUARDS.pop(registered)
            resilience._RUNTIME_CONTROL_STORE_GUARDS[registered] = binding
        with pytest.raises(ValueError, match="registered_control_guard_binding_changed"):
            resilience._require_runtime_control_store_guard(registered)
    finally:
        registered.close()


def _run_owned_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe: str,
    *,
    before_session: Callable[..., None] | None = None,
) -> None:
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, kind="workflow_run")
    job = control.get_job("job-a")
    assert job is not None
    if probe in {"head_expired_during_write", "head_expired_during_stat"}:
        monkeypatch.setenv("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", "6")
    guarded_control = guard_runtime_control_store(control)
    shared = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", shared)
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "1" if probe == "timeout" else "5")
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_BREAKER_FAILURE_THRESHOLD", "1")
    guard = BlockingDependencyGuard(
        dependency_name="parent",
        timeout_seconds=60,
        breaker=CircuitBreaker("test-parent"),
        executor=shared,
    )

    def handler(_job_record: object) -> None:
        budget = _require_attempt_budget("job-a", "run-a", attempt)
        completion = guard.create_parent_completion(guarded_control, budget)

        def run(grant: _BorrowedExecutionGrant) -> None:
            from polisyos.runtime.http.resilience import _bootstrap_guarded_child_control_fence

            _exercise_job(
                tmp_path,
                guarded_control,
                grant,
                monkeypatch,
                probe,
                fence_factory=_bootstrap_guarded_child_control_fence,
                before_session=before_session,
            )

        guard.run_with_parent_admission(
            run, deadline_monotonic=budget.deadline_monotonic, completion=completion
        )

    worker = ControlWorker(
        store=guarded_control,
        handler=handler,
        worker_id="worker-a",
        child_execution_budget_policy=ChildExecutionBudgetPolicy("child-test", "1", 60),
    )

    try:
        worker._run_with_lease_heartbeat(job)
    finally:
        guard.close()
        shared.shutdown(wait=True)
        guarded_control.close()


@pytest.mark.parametrize(
    "probe",
    [
        "normal",
        "scope",
        "runtime_core_appointment",
        "runtime_core_bootstrap",
        "runtime_core_bootstrap_registration_transition",
        "runtime_cas_service",
        "runtime_cas_service_registry_aba",
        "runtime_job_verifier",
        "runtime_job_verifier_registry_aba",
        "runtime_job_verifier_scope",
        "runtime_job_verifier_release",
        "suspend_inflight",
        "timeout",
        "lost_commit_ack",
        "head_parent_sync_failure",
        "head_timeout",
        "head_timeout_after_replace",
        "head_lease_contention",
        "head_expired_during_write",
        "head_expired_during_stat",
        "head_staging_lease_change",
        "head_staging_parent_revocation",
        "head_control_proxy",
        "head_control_guard",
        "head_control_registry",
    ],
)
def test_registered_control_guard_preserves_child_owner_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """Run the real job, custody, scope and fresh reader through the control guard."""
    _run_owned_fixture(tmp_path, monkeypatch, probe)


@pytest.mark.parametrize("transition", ["owner", "completed", "trace", "basis", "older_snapshot"])
def test_managed_read_reconciles_the_actual_admitted_parent_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transition: str
) -> None:
    """A prior successful read cannot outlive changed parent source or bytes."""
    from polisyos.core.artifacts import ArtifactWriteOptions
    from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
    from polisyos.core.run.context import _FinalizeRecoveryError
    from polisyos.runtime.http.resilience import _require_runtime_filesystem_guard

    def change_parent(root, _control, custody, _reader, _fence, _grant, binding):
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, _fence.begin_session(intent))
        managed = custody.parent_store(binding, input_refs=())
        selected = managed.put_json(
            {"candidate": True},
            ArtifactWriteOptions(kind="tests.child.source", media_type="application/json"),
            return_selected_profile=True,
        )
        assert managed.get_bytes(selected)
        if transition == "owner":
            root.update_manifest(execution_profile="changed-profile")
        elif transition == "completed":
            attempt = next(
                item
                for item in root.read_runtime_invocation_attempts()
                if item.basis_ref == binding.parent_basis_ref
            )
            root._record_runtime_invocation_completed(
                attempt_id=attempt.basis.attempt_id,
                attempt_number=attempt.basis.attempt_number,
                basis_ref=attempt.basis_ref,
                status="ok",
                outcome_state_ref=attempt.basis.input_state_ref,
                output_refs=[],
            )
        elif transition == "trace":
            assert root.trace_path is not None
            with root.trace_path.open("ab") as stream:
                stream.write(b"not-a-trace-record\n")
        else:
            backend = _require_runtime_filesystem_guard(root.store).backend
            ref = binding.parent_basis_ref
            if transition == "older_snapshot":
                from polisyos.core.trace.record import TraceRecord

                assert root.trace_path is not None
                initial = TraceRecord.model_validate_json(
                    root.trace_path.read_text().splitlines()[0]
                )
                ref = initial.refs.outputs[0]
                assert ref != root._owner_snapshot_ref
            blob, _manifest = backend._paths(ref.artifact_id)
            blob.write_bytes(b"corrupted-parent-basis")
        with pytest.raises((ChildReleaseUnavailableError, _FinalizeRecoveryError)):
            managed.get_bytes(selected)

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=change_parent)


@pytest.mark.parametrize(
    "probe",
    [
        "fake_proxy",
        "fake_service",
        "callback",
        "worker_receipt",
        "wrong_profile",
        "wrong_cas",
        "foreign_thread",
    ],
)
def test_child_control_owner_rejects_unbound_inputs_before_session_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """Fake or mismatched inputs do not issue the Core operation."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.run.context import _FinalizeRecoveryError
    from polisyos.core.run.worker_lifecycle import ChildRuntimeCapability, WorkerLifecycleCapability
    from polisyos.runtime.http.resilience import (
        _bootstrap_guarded_child_control_fence,
        guard_runtime_cas,
    )

    def refuse(root, control, custody, _reader, fence, grant, binding) -> None:
        if probe == "fake_proxy":
            other = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
            fake = GuardedDependencyProxy(target=other, guard=build_runtime_control_store_guard())
            try:
                with pytest.raises(
                    ValueError, match="registered_control_guard_binding_not_established"
                ):
                    _bootstrap_guarded_child_control_fence(root, fake, grant, binding)
            finally:
                fake.close()
        elif probe == "wrong_profile":
            ref = binding.parent_basis_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "f" * 64}
            )
            altered = binding.model_copy(update={"parent_basis_ref": ref})
            with pytest.raises(RuntimeError, match="borrowed_execution_parent_binding_mismatch"):
                _bootstrap_guarded_child_control_fence(root, control, grant, altered)
        elif probe == "wrong_cas":
            original = root.store
            other = guard_runtime_cas(FileSystemCAS(tmp_path / "other-served"))
            root.store = other
            try:
                with pytest.raises((FileNotFoundError, ValueError, _FinalizeRecoveryError)):
                    _bootstrap_guarded_child_control_fence(root, control, grant, binding)
            finally:
                root.store = original
                other.close()
        elif probe == "foreign_thread":
            observed: list[BaseException] = []

            def call_from_foreign_thread() -> None:
                try:
                    _bootstrap_guarded_child_control_fence(root, control, grant, binding)
                except BaseException as exc:
                    observed.append(exc)

            worker = threading.Thread(target=call_from_foreign_thread)
            worker.start()
            worker.join(timeout=5)
            assert not worker.is_alive() and len(observed) == 1
            assert "borrowed_execution_admission_not_current" in str(observed[0])
        else:
            custody.job_session_intent(binding)
            if probe == "fake_service":

                class Lookalike(type(fence)):
                    pass

                fake_owner = object.__new__(Lookalike)
            elif probe == "worker_receipt":
                fake_owner = WorkerLifecycleCapability.for_parent(root)
            else:

                class FakeCallback:
                    def _require_parent(self) -> None:
                        return None

                fake_owner = FakeCallback()
            custody._fence = fake_owner
            try:
                with pytest.raises(
                    ValueError, match="child_runtime_control_origin_not_established"
                ):
                    ChildRuntimeCapability.for_parent(
                        root, session=custody, runtime_control=fake_owner
                    )
            finally:
                custody._fence = fence
        assert (
            control.find_child_job_session(
                job_id="job-a",
                run_id="run-a",
                parent_attempt_id=binding.parent_attempt_id,
                parent_basis_ref=binding.parent_basis_ref,
            )
            is None
        )

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=refuse)


def test_child_control_rejects_a_session_handle_as_a_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual Core owner does not reinterpret one decision as another."""
    from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
    from polisyos.core.run.worker_lifecycle import ChildRuntimeCapability

    def refuse(root, control, custody, _reader, fence, _grant, binding) -> None:
        intent = custody.job_session_intent(binding)
        capability = ChildRuntimeCapability.for_parent(root, session=custody, runtime_control=fence)
        with pytest.raises(ValueError, match="child_runtime_session_owner_changed"):
            capability._issue_scope_operation(intent)
        with pytest.raises(ChildReleaseUnavailableError, match="control_operation_owner_mismatch"):
            custody._issue_control_operation(intent, fence, kind="scope")
        assert (
            control.find_child_job_session(
                job_id="job-a",
                run_id="run-a",
                parent_attempt_id=binding.parent_attempt_id,
                parent_basis_ref=binding.parent_basis_ref,
            )
            is None
        )

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=refuse)


def test_guarded_session_lost_ack_recovers_without_reissuing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A committed intent is read freshly; the one-use operation is not replaced."""
    from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
    from polisyos.core.run.child_custody import ChildSessionAdmissionUnknown

    def lose_ack(_root, _control, custody, _reader, fence, _grant, binding) -> None:
        intent = custody.job_session_intent(binding)
        read_row = ControlPlaneStore._child_event_row

        def lose_fresh_read(store, job_id, event_type):
            if (
                event_type.startswith("child.release.session.")
                and not store._has_active_job_transaction()
            ):
                raise OSError("lost session acknowledgement")
            return read_row(store, job_id, event_type)

        with monkeypatch.context() as patch:
            patch.setattr(ControlPlaneStore, "_child_event_row", lose_fresh_read)
            with pytest.raises(ChildSessionAdmissionUnknown) as unknown:
                fence.begin_session(intent)
        assert unknown.value.recovery is not None
        fresh = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        recovered = fresh.find_child_job_session(
            job_id="job-a",
            run_id="run-a",
            parent_attempt_id=binding.parent_attempt_id,
            parent_basis_ref=binding.parent_basis_ref,
        )
        assert recovered is not None
        with pytest.raises(ChildReleaseUnavailableError, match="control_operation_already_issued"):
            fence.begin_session(intent)
        assert (
            fresh.find_child_job_session(
                job_id="job-a",
                run_id="run-a",
                parent_attempt_id=binding.parent_attempt_id,
                parent_basis_ref=binding.parent_basis_ref,
            )
            == recovered
        )
        row = fresh._fetchone(
            "SELECT COUNT(*) AS n FROM control_job_events WHERE job_id = ? "
            "AND event_type LIKE 'child.release.session.%'",
            ("job-a",),
        )
        assert row is not None and row["n"] == 1

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=lose_ack)


def test_guarded_scope_lost_ack_recovers_without_reissuing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconcile a committed scope once when its fresh-read acknowledgement is lost."""
    from polisyos.core.artifacts.child_release import (
        ChildJobScopeClaim,
        ChildReleaseUnavailableError,
    )
    from polisyos.core.run.child_custody import ChildScopeAdmissionUnknown

    def lose_ack(_root, _control, custody, _reader, fence, _grant, binding) -> None:
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        child_binding = binding.model_copy(update={"child_invocation_id": "child"})
        prepared = custody.prepare_scope(child_binding, input_refs=())
        expected = prepared.recompute()

        def lose_fresh_read(_store, _locator, _claim):
            raise OSError("lost scope acknowledgement")

        with monkeypatch.context() as patch:
            patch.setattr(ControlPlaneStore, "verify_scope", lose_fresh_read)
            with pytest.raises(ChildScopeAdmissionUnknown) as unknown:
                fence.admit_prepared_scope(prepared)

        assert unknown.value.recovery is not None
        assert unknown.value.scope_locator is not None
        claim = ChildJobScopeClaim.model_validate_json(unknown.value.scope_claim_json)
        assert claim == expected
        fresh = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        fresh.verify_scope(unknown.value.scope_locator, claim)
        with pytest.raises(ChildReleaseUnavailableError):
            fence.admit_prepared_scope(prepared)
        fresh.verify_scope(unknown.value.scope_locator, claim)
        row = fresh._fetchone(
            "SELECT COUNT(*) AS n FROM control_job_events WHERE job_id = ? "
            "AND event_type LIKE 'child.release.scope.%'",
            ("job-a",),
        )
        assert row is not None and row["n"] == 1

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=lose_ack)


def test_revoked_parent_cannot_consume_a_committed_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recovery handle cannot transfer a scope after parent revocation."""
    from contextlib import contextmanager

    from polisyos.core.run.child_custody import ChildScopeAdmissionUnknown

    def revoke_before_commit(_root, _control, custody, _reader, fence, grant, binding) -> None:
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        child_binding = binding.model_copy(update={"child_invocation_id": "child"})
        prepared = custody.prepare_scope(child_binding, input_refs=())
        claim = prepared.recompute()
        original = ControlPlaneStore._job_transaction

        @contextmanager
        def transaction(store, *, purpose="execution", commit_admission=None):
            if commit_admission is None:
                with original(store, purpose=purpose):
                    yield
                return

            def revoke() -> None:
                grant._attempt.revoke()
                commit_admission()

            with original(store, purpose=purpose, commit_admission=revoke):
                yield

        with monkeypatch.context() as patch:
            patch.setattr(ControlPlaneStore, "_job_transaction", transaction)
            with pytest.raises(ChildScopeAdmissionUnknown) as unknown:
                fence.admit_prepared_scope(prepared)
        locator = unknown.value.scope_locator
        assert locator is not None
        fresh = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        fresh.verify_scope(locator, claim)
        with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
            prepared.complete(locator)

    _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=revoke_before_commit)


def test_revoked_parent_cannot_publish_after_authorization_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later revocation prevents release even when the job event committed."""
    from polisyos.core.artifacts.child_release import _ChildReleaseLedger
    from polisyos.core.run.child_custody import ChildParentSettlementError
    from polisyos.runtime.http import resilience

    bootstrap = resilience._bootstrap_guarded_child_control_fence
    verify = ControlPlaneStore.verify_release
    retained: dict[str, object] = {}
    revoked = threading.Event()

    def capture(root, control, grant, binding):
        retained["grant"] = grant
        return bootstrap(root, control, grant, binding)

    def revoke(store, locator, claim):
        if not revoked.is_set():
            head = _ChildReleaseLedger(
                tmp_path / "served", claim.release_id, claim.root_run_id
            ).head()
            assert head.status == "pending"
            retained["grant"]._attempt.revoke()
            revoked.set()
        return verify(store, locator, claim)

    with monkeypatch.context() as patch:
        patch.setattr(resilience, "_bootstrap_guarded_child_control_fence", capture)
        patch.setattr(ControlPlaneStore, "verify_release", revoke)
        with pytest.raises(ChildParentSettlementError) as unknown:
            _run_owned_fixture(tmp_path, monkeypatch, "normal")
    assert revoked.is_set()
    receipt = unknown.value.receipt
    head = _ChildReleaseLedger(tmp_path / "served", receipt.release_id, receipt.root_run_id).head()
    assert head.status == "pending"


def test_changed_job_lease_cannot_publish_after_authorization_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A durable lease change wins before the release head is published."""
    from contextlib import contextmanager

    from polisyos.core.artifacts.child_release import _ChildReleaseLedger
    from polisyos.core.run.child_custody import ChildParentSettlementError
    from polisyos.runtime.http import resilience

    consume = resilience._RuntimeGuardedChildFence.local_consumption
    changed = threading.Event()

    @contextmanager
    def change_lease(fence):
        if not changed.is_set():
            fresh = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
            event = fresh._fetchone(
                "SELECT event_id FROM control_job_events WHERE job_id = ? "
                "AND event_type LIKE 'child.release.authorization.%'",
                ("job-a",),
            )
            if event is not None:
                assert (
                    fresh._execute(
                        "UPDATE control_jobs SET lease_owner = ? WHERE job_id = ?",
                        ("other-worker", "job-a"),
                    )
                    == 1
                )
                changed.set()
        with consume(fence):
            yield

    with monkeypatch.context() as patch:
        patch.setattr(resilience._RuntimeGuardedChildFence, "local_consumption", change_lease)
        with pytest.raises(ChildParentSettlementError) as unknown:
            _run_owned_fixture(tmp_path, monkeypatch, "normal")
    assert changed.is_set()
    receipt = unknown.value.receipt
    head = _ChildReleaseLedger(tmp_path / "served", receipt.release_id, receipt.root_run_id).head()
    assert head.status == "pending"


@pytest.mark.parametrize("operation", ["scope", "release"])
def test_parent_revoked_at_local_consumption_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """Revoke after the fresh preflight but before the short local decision."""
    from contextlib import contextmanager

    from polisyos.core.artifacts.child_release import _ChildReleaseLedger
    from polisyos.core.run.child_custody import (
        ChildParentSettlementError,
        ChildScopeAdmissionUnknown,
    )
    from polisyos.runtime.http import resilience

    original = resilience._RuntimeGuardedChildFence.local_consumption
    entered = threading.Event()

    @contextmanager
    def revoke_before_decision(fence):
        fresh = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        event = fresh._fetchone(
            "SELECT event_id FROM control_job_events WHERE job_id = ? AND event_type LIKE ?",
            ("job-a", f"child.release.{'scope' if operation == 'scope' else 'authorization'}.%"),
        )
        if event is not None and not entered.is_set():
            entered.set()
            fence._grant._attempt.revoke()
        with original(fence):
            yield

    with monkeypatch.context() as patch:
        patch.setattr(
            resilience._RuntimeGuardedChildFence, "local_consumption", revoke_before_decision
        )
        if operation == "scope":

            def admit(_root, _control, custody, _reader, fence, _grant, binding) -> None:
                intent = custody.job_session_intent(binding)
                custody.bind_job_intent(intent, fence.begin_session(intent))
                child_binding = binding.model_copy(update={"child_invocation_id": "child"})
                prepared = custody.prepare_scope(child_binding, input_refs=())
                with pytest.raises(ChildScopeAdmissionUnknown):
                    fence.admit_prepared_scope(prepared)

            _run_owned_fixture(tmp_path, monkeypatch, "normal", before_session=admit)
        else:
            with pytest.raises(ChildParentSettlementError) as unknown:
                _run_owned_fixture(tmp_path, monkeypatch, "normal")
            receipt = unknown.value.receipt
            head = _ChildReleaseLedger(
                tmp_path / "served", receipt.release_id, receipt.root_run_id
            ).head()
            assert head.status == "pending"
    assert entered.is_set()


def test_parent_grant_is_not_usable_on_the_control_guard_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control executor cannot consume the parent's thread-bound grant."""
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    guarded_control = guard_runtime_control_store(control)
    shared = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", shared)
    guard = BlockingDependencyGuard(
        dependency_name="parent",
        timeout_seconds=10,
        breaker=CircuitBreaker("test-parent"),
        executor=shared,
    )
    basis = json.dumps(
        {
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "tests.parent_basis",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    parent = {"run_id": "run-a", "job_id": "job-a", "attempt_id": "attempt-a", "basis_ref": basis}
    retained = []

    def run(grant: _BorrowedExecutionGrant) -> None:
        grant.check_current()
        grant.bind_parent(**parent)
        liveness = grant._control_liveness(**parent)
        retained.append(liveness)
        assert guarded_control.run_operation(liveness._require_current) is None
        with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
            guarded_control.run_operation(grant.check_current)
        with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
            guarded_control.run_operation(lambda: grant._control_liveness(**parent))
        grant.check_current()

    try:
        guard.run_with_parent_admission(run, deadline_monotonic=time.monotonic() + 10)
        with pytest.raises(RuntimeError, match="borrowed_execution_admission_not_current"):
            retained[0]._require_current()
    finally:
        guard.close()
        shared.shutdown(wait=True)
        guarded_control.close()
