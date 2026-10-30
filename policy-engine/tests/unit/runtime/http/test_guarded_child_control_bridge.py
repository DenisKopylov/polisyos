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


def test_control_guard_registration_binds_actual_factory_and_executor(tmp_path: Path) -> None:
    """A lookalike proxy cannot establish the control executor's origin."""
    from polisyos.runtime.http.resilience import _require_runtime_control_store_guard

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    registered = guard_runtime_control_store(control)
    lookalike = GuardedDependencyProxy(target=control, guard=build_runtime_control_store_guard())
    try:
        binding = _require_runtime_control_store_guard(registered)
        assert binding.backend is control
        assert binding.guard is registered._guard
        assert binding.executor is registered._guard._executor
        with pytest.raises(ValueError, match="registered_control_guard_binding_not_established"):
            _require_runtime_control_store_guard(lookalike)
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


@pytest.mark.parametrize("probe", ["normal", "scope", "suspend_inflight", "timeout"])
def test_registered_control_guard_preserves_child_owner_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """Run the real job, custody, scope and fresh reader through the control guard."""
    _run_owned_fixture(tmp_path, monkeypatch, probe)


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
